# app/modules/kasa_hareket/services.py

from typing import Dict, Any, Tuple, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func
from flask import current_app

from app.extensions import db
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.kasa.models import Kasa
from app.enums import BankaIslemTuru, CariIslemTuru
from app.araclar import para_cevir, numara_uret
from app.modules.cari.services import CariService
from app.modules.muhasebe.services import MuhasebeEntegrasyonService

class KasaService:
    
    @staticmethod
    def get_by_id(hareket_id: int) -> Optional[KasaHareket]:
        return KasaHareket.query.get(hareket_id)

    @staticmethod
    def bakiye_guncelle(kasa_id: int):
        if not kasa_id: return
        
        girisler = db.session.query(func.coalesce(func.sum(KasaHareket.tutar), 0)).filter(
            KasaHareket.kasa_id == kasa_id,
            KasaHareket.onaylandi == True,
            KasaHareket.islem_turu.in_([
                BankaIslemTuru.TAHSILAT, 
                BankaIslemTuru.VIRMAN_GIRIS,
                BankaIslemTuru.POS_TAHSILAT
            ])
        ).scalar()

        cikislar = db.session.query(func.coalesce(func.sum(KasaHareket.tutar), 0)).filter(
            KasaHareket.kasa_id == kasa_id,
            KasaHareket.onaylandi == True,
            KasaHareket.islem_turu.in_([
                BankaIslemTuru.TEDIYE, 
                BankaIslemTuru.VIRMAN_CIKIS
            ])
        ).scalar()

        kasa = Kasa.query.get(kasa_id)
        if kasa:
            kasa.bakiye = Decimal(str(girisler)) - Decimal(str(cikislar))

    @staticmethod
    def islem_kaydet(data: Dict[str, Any], user_id: int, hareket_id: int = None) -> Tuple[bool, str]:
        try:
            # 1.TEMEL KONTROLLER
            if not data.get('kasa_id'): return False, "Kasa seçimi zorunludur."
            
            try:
                tutar = para_cevir(data.get('tutar'))
                if tutar <= 0: return False, "Tutar 0'dan büyük olmalıdır."
            except:
                return False, "Geçersiz tutar formatı."

            # Tarih Dönüşümü
            tarih_val = datetime.now().date()
            if data.get('tarih'):
                try:
                    t_str = str(data['tarih']).strip()
                    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
                        try:
                            tarih_val = datetime.strptime(t_str, fmt).date()
                            break
                        except ValueError: continue
                except: pass

            # 2.NESNE OLUŞTURMA
            if hareket_id:
                hareket = KasaHareket.query.get(hareket_id)
                if not hareket: return False, "Hareket bulunamadı."
            else:
                hareket = KasaHareket()
                hareket.belge_no = numara_uret(data['firma_id'], 'KASA', datetime.now().year, 'MAK-', 6)

            # 3.VERİ ATAMA
            hareket.firma_id = data['firma_id']
            hareket.donem_id = data['donem_id']
            hareket.kasa_id = int(data['kasa_id'])
            hareket.tarih = tarih_val
            hareket.tutar = tutar
            hareket.aciklama = data.get('aciklama', '')
            hareket.plasiyer_id = user_id
            hareket.onaylandi = True

            # Yön ve Taraf
            hedef_turu = data.get('karsi_hesap_turu') or 'cari'
            islem_yonu = data.get('islem_yonu')

            # Enum Belirleme
            if islem_yonu == 'giris':
                hareket.islem_turu = BankaIslemTuru.VIRMAN_GIRIS if hedef_turu == 'kasa' else BankaIslemTuru.TAHSILAT
            else:
                hareket.islem_turu = BankaIslemTuru.VIRMAN_CIKIS if hedef_turu == 'kasa' else BankaIslemTuru.TEDIYE

            # İlişki ID'lerini Temizle
            hareket.cari_id = None
            hareket.banka_id = None
            hareket.karsi_kasa_id = None

            if hedef_turu == 'cari' and data.get('cari_id'):
                hareket.cari_id = int(data['cari_id'])
            elif hedef_turu == 'banka' and data.get('banka_id'):
                hareket.banka_id = int(data['banka_id'])
            elif hedef_turu == 'kasa' and data.get('karsi_kasa_id'):
                hareket.karsi_kasa_id = int(data['karsi_kasa_id'])

            db.session.add(hareket)
            db.session.flush() # ID almak için

            # 4.ENTEGRASYONLAR
            
            # A) Cari Entegrasyonu
            if hareket.cari_id:
                c_yon = 'alacak' if islem_yonu == 'giris' else 'borc'
                c_tur = CariIslemTuru.TAHSILAT if islem_yonu == 'giris' else CariIslemTuru.TEDIYE
                
                CariService.hareket_ekle(
                    cari_id=hareket.cari_id,
                    islem_turu=c_tur,
                    belge_no=hareket.belge_no,
                    tarih=hareket.tarih,
                    borc=hareket.tutar if c_yon == 'borc' else 0,
                    alacak=hareket.tutar if c_yon == 'alacak' else 0,
                    aciklama=f"Kasa: {hareket.aciklama}",
                    kaynak_ref={'tur': 'KASA', 'id': hareket.id},
                    donem_id=hareket.donem_id
                )

            # B) Virman Karşı Bacak
            if hareket.karsi_kasa_id:
                KasaService._handle_virman_pair(hareket, user_id)

            # C) Muhasebe Entegrasyonu
            basari, mesaj = MuhasebeEntegrasyonService.entegre_et_kasa(hareket.id)
            if not basari:
                print(f"⚠️ Muhasebe Entegrasyon Uyarısı: {mesaj}")

            db.session.commit()
            
            KasaService.bakiye_guncelle(hareket.kasa_id)
            return True, "İşlem başarıyla kaydedildi."

        except Exception as e:
            db.session.rollback()
            print(f"❌ KASA KAYIT HATASI: {str(e)}")
            return False, f"Veritabanı hatası: {str(e)}"

    @staticmethod
    def islem_sil(hareket_id: int) -> Tuple[bool, str]:
        hareket = KasaHareket.query.get(hareket_id)
        if not hareket: return False, "Kayıt bulunamadı."
        
        try:
            print(f"🗑️ SİLME İŞLEMİ BAŞLADI: KasaHareket #{hareket_id}")
            kasa_id = hareket.kasa_id
            
            # 1.CARİ HAREKETLERİ SİL (Genişletilmiş Kontrol)
            from modules.cari.models import CariHareket
            
            # Hem 'KASA' hem 'kasa' (büyük/küçük harf) olarak arıyoruz.
            silinen_cari_sayisi = CariHareket.query.filter(
                CariHareket.kaynak_turu.in_(['KASA', 'kasa']), 
                CariHareket.kaynak_id == hareket.id
            ).delete(synchronize_session=False)
            
            print(f"   -> Silinen Cari Hareket Sayısı: {silinen_cari_sayisi}")

            if hareket.cari_id:
                CariService.bakiye_hesapla_ve_guncelle(hareket.cari_id)

            # 2.VİRMAN SİLME
            if hareket.karsi_kasa_id:
                KasaService._delete_virman_pair(hareket)
            
            # 3.MUHASEBE FİŞİ SİLME
            if hareket.muhasebe_fisi_id:
                print(f"   -> Muhasebe Fiş ID bulundu: {hareket.muhasebe_fisi_id}")
                from modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay
                fis = MuhasebeFisi.query.get(hareket.muhasebe_fisi_id)
                if fis:
                    if fis.resmi_defter_basildi:
                        return False, "Bu işlemin muhasebe fişi resmileştiği için silinemez!"
                    
                    # Önce detayları temizle
                    detay_sayisi = MuhasebeFisiDetay.query.filter_by(fis_id=fis.id).delete()
                    print(f"   -> Silinen Fiş Detay Sayısı: {detay_sayisi}")
                    
                    # Sonra fişi sil
                    db.session.delete(fis)
                    print("   -> Muhasebe Fişi Silindi.")
                else:
                    print("   -> Fiş ID var ama veritabanında bulunamadı.")
            else:
                print("   -> Kasa kaydında Muhasebe Fiş ID yok.")

            # 4.KASA HAREKETİ SİLME
            db.session.delete(hareket)
            
            # 5.İŞLEMİ ONAYLA
            db.session.commit()
            print("✅ Silme işlemi Commit edildi.")

            KasaService.bakiye_guncelle(kasa_id)
            return True, "Kayıt ve bağlı tüm işlemler silindi."
        except Exception as e:
            db.session.rollback()
            print(f"❌ SİLME HATASI: {str(e)}")
            return False, str(e)

    @staticmethod
    def _handle_virman_pair(kaynak, user_id):
        # Virman mantığı aynı kalacak
        karsi = KasaHareket.query.filter_by(
            kasa_id=kaynak.karsi_kasa_id, karsi_kasa_id=kaynak.kasa_id,
            belge_no=kaynak.belge_no, tarih=kaynak.tarih
        ).first()
        
        if not karsi: karsi = KasaHareket()
        
        karsi.firma_id = kaynak.firma_id
        karsi.donem_id = kaynak.donem_id
        karsi.kasa_id = kaynak.karsi_kasa_id
        karsi.karsi_kasa_id = kaynak.kasa_id
        karsi.tarih = kaynak.tarih
        karsi.tutar = kaynak.tutar
        karsi.belge_no = kaynak.belge_no
        karsi.aciklama = f"Virman: {kaynak.aciklama}"
        karsi.plasiyer_id = user_id
        karsi.onaylandi = True
        
        tur = str(kaynak.islem_turu)
        if 'cikis' in tur or 'tediye' in tur:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_GIRIS
        else:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_CIKIS
            
        db.session.add(karsi)
        db.session.flush()
        KasaService.bakiye_guncelle(karsi.kasa_id)

    @staticmethod
    def _delete_virman_pair(kaynak):
        karsi = KasaHareket.query.filter_by(
            kasa_id=kaynak.karsi_kasa_id, karsi_kasa_id=kaynak.kasa_id,
            belge_no=kaynak.belge_no
        ).first()
        if karsi:
            kid = karsi.kasa_id
            db.session.delete(karsi)
            KasaService.bakiye_guncelle(kid)

KasaHareketService = KasaService