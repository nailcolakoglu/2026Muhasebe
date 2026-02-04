# app/modules/banka_hareket/services.py

from typing import Dict, Any, Tuple, Optional, List
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func
from flask import current_app

from app.extensions import db
from app.modules.banka.models import BankaHesap
from app.modules.banka_hareket.models import BankaHareket
from app.enums import BankaIslemTuru, CariIslemTuru
from app.araclar import para_cevir, numara_uret
from app.modules.cari.services import CariService

# Muhasebe Entegrasyonu
from modules.muhasebe.services import MuhasebeEntegrasyonService

class BankaHareketService:
    
    # 👇 EKLENEN METOD (HATAYI ÇÖZEN KISIM) 👇
    @staticmethod
    def get_form_options(firma_id: int) -> Tuple[List, List, List]:
        """
        Form için gerekli olan Banka, Cari ve Kasa listelerini hazırlar.
        Routes.py tarafından çağrılır.
        """
        from modules.kasa.models import Kasa
        from modules.cari.models import CariHesap
        
        # 1.Bankalar (DÜZELTME: aktif=True şartını kaldırdık)
        bankalar = BankaHesap.query.filter_by(firma_id=firma_id).all()
        
        # Eğer hiç banka yoksa manuel bir uyarı ekleyelim
        if not bankalar:
            print("⚠️ UYARI: Sistemde kayıtlı banka hesabı bulunamadı!")
            
        # Format: (ID, "Akbank - Şube (TL)")
        b_opts = []
        for b in bankalar:
            # Doviz veya Şube adı boşsa hata vermesin diye kontrol
            doviz = b.doviz_cinsi if hasattr(b, 'doviz_cinsi') else 'TL'
            sube = b.sube_adi if hasattr(b, 'sube_adi') else ''
            b_opts.append((b.id, f"{b.banka_adi} / {sube} ({doviz})"))

        # 2.Cariler
        cariler = CariHesap.query.filter_by(firma_id=firma_id).order_by(CariHesap.unvan).all()
        c_opts = [(c.id, f"{c.unvan}") for c in cariler]

        # 3.Kasalar
        kasalar = Kasa.query.filter_by(firma_id=firma_id).all() # Buradan da aktif şartını kaldırdık
        k_opts = []
        for k in kasalar:
            doviz = getattr(k.doviz_turu, 'name', str(k.doviz_turu)) if hasattr(k, 'doviz_turu') else 'TL'
            k_opts.append((k.id, f"{k.ad} ({doviz})"))

        return b_opts, c_opts, k_opts

    @staticmethod
    def get_by_id(hareket_id: int) -> Optional[BankaHareket]:
        return BankaHareket.query.get(hareket_id)

    @staticmethod
    def bakiye_guncelle(banka_id: int):
        """Banka bakiyesini yeniden hesaplar."""
        if not banka_id: return
        
        # Girişler
        girisler = db.session.query(func.coalesce(func.sum(BankaHareket.tutar), 0)).filter(
            BankaHareket.banka_id == banka_id,
            BankaHareket.islem_turu.in_([
                BankaIslemTuru.TAHSILAT, 
                BankaIslemTuru.VIRMAN_GIRIS,
                BankaIslemTuru.POS_TAHSILAT
            ])
        ).scalar()

        # Çıkışlar
        cikislar = db.session.query(func.coalesce(func.sum(BankaHareket.tutar), 0)).filter(
            BankaHareket.banka_id == banka_id,
            BankaHareket.islem_turu.in_([
                BankaIslemTuru.TEDIYE, 
                BankaIslemTuru.VIRMAN_CIKIS
            ])
        ).scalar()

        banka = BankaHesap.query.get(banka_id)
        if banka:
            banka.bakiye = Decimal(str(girisler)) - Decimal(str(cikislar))

    @staticmethod
    def islem_kaydet(data: Dict[str, Any], user_id: int, hareket_id: int = None) -> Tuple[bool, str]:
        try:
            # 1.TEMEL KONTROLLER
            if not data.get('banka_id'): return False, "Banka seçimi zorunludur."
            
            try:
                tutar = para_cevir(data.get('tutar'))
                if tutar <= 0: return False, "Tutar 0'dan büyük olmalıdır."
            except:
                return False, "Geçersiz tutar formatı."

            # Tarih
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
                hareket = BankaHareket.query.get(hareket_id)
                if not hareket: return False, "Hareket bulunamadı."
            else:
                hareket = BankaHareket()
                hareket.belge_no = numara_uret(data['firma_id'], 'BANKA', datetime.now().year, 'DEC-', 6)

            # 3.VERİ ATAMA
            hareket.firma_id = data['firma_id']
            hareket.donem_id = data['donem_id']
            hareket.banka_id = int(data['banka_id'])
            hareket.tarih = tarih_val
            hareket.tutar = tutar
            hareket.aciklama = data.get('aciklama', '')
            
            # Yön ve Taraf Analizi
            karsi_taraf = data.get('karsi_taraf') or 'cari' 
            islem_yonu = data.get('islem_yonu')

            if islem_yonu == 'giris':
                hareket.islem_turu = BankaIslemTuru.VIRMAN_GIRIS if karsi_taraf in ['kasa', 'banka'] else BankaIslemTuru.TAHSILAT
            else:
                hareket.islem_turu = BankaIslemTuru.VIRMAN_CIKIS if karsi_taraf in ['kasa', 'banka'] else BankaIslemTuru.TEDIYE

            # İlişkileri Temizle
            hareket.cari_id = None
            hareket.kasa_id = None
            hareket.karsi_banka_id = None

            if karsi_taraf == 'cari' and data.get('cari_id'):
                hareket.cari_id = int(data['cari_id'])
            elif karsi_taraf == 'kasa' and data.get('kasa_id'):
                hareket.kasa_id = int(data['kasa_id'])
            elif karsi_taraf == 'banka' and data.get('hedef_banka_id'): 
                hareket.karsi_banka_id = int(data['hedef_banka_id'])

            db.session.add(hareket)
            db.session.flush()

            # 4.ENTEGRASYONLAR
            # --- 🔥 YENİ EKLENEN KISIM (TEMİZLİK) 🔥 ---
            # Eğer güncelleme yapılıyorsa (hareket_id varsa), 
            # bu banka hareketine bağlı eski cari kayıtlarını temizle.
            # Böylece yeni kayıt eklendiğinde çift kayıt (mükerrer) olmaz.
            if hareket.id:
                from modules.cari.models import CariHareket
                CariHareket.query.filter(
                    CariHareket.kaynak_turu.in_(['BANKA', 'banka']),
                    CariHareket.kaynak_id == hareket.id
                ).delete(synchronize_session=False)
                # Not: Commit yapmıyoruz, transaction sonunda toplu yapılacak.
            # -----------------------------------------------

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
                    aciklama=f"Banka: {hareket.aciklama}",
                    kaynak_ref={'tur': 'BANKA', 'id': hareket.id},
                    donem_id=hareket.donem_id
                )

            # B) Virman Entegrasyonları
            if hareket.kasa_id:
                BankaHareketService._handle_kasa_pair(hareket, user_id)
            
            if hareket.karsi_banka_id:
                BankaHareketService._handle_banka_pair(hareket)

            # C) Muhasebe Entegrasyonu
            basari, mesaj = MuhasebeEntegrasyonService.entegre_et_banka(hareket.id)
            if not basari:
                print(f"⚠️ Banka Muhasebe Uyarısı: {mesaj}")

            db.session.commit()
            
            BankaHareketService.bakiye_guncelle(hareket.banka_id)
            
            msg = "İşlem başarıyla kaydedildi."
            if basari: msg += " (Fiş Kesildi)"
            return True, msg

        except Exception as e:
            db.session.rollback()
            print(f"❌ BANKA KAYIT HATASI: {str(e)}")
            return False, f"Veritabanı hatası: {str(e)}"

    @staticmethod
    def islem_sil(hareket_id: int) -> Tuple[bool, str]:
        hareket = BankaHareket.query.get(hareket_id)
        if not hareket: return False, "Kayıt bulunamadı."
        
        try:
            banka_id = hareket.banka_id
            
            # 1.Cari Hareketlerini Sil
            from modules.cari.models import CariHareket
            CariHareket.query.filter(
                CariHareket.kaynak_turu.in_(['BANKA', 'banka']), 
                CariHareket.kaynak_id == hareket.id
            ).delete(synchronize_session=False)

            if hareket.cari_id:
                CariService.bakiye_hesapla_ve_guncelle(hareket.cari_id)

            # 2.Virman Karşı Bacaklarını Sil
            if hareket.kasa_id:
                BankaHareketService._delete_kasa_pair(hareket)
            if hareket.karsi_banka_id:
                BankaHareketService._delete_banka_pair(hareket)

            # 3.Muhasebe Fişini Sil
            if hareket.muhasebe_fisi_id:
                from modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay
                fis = MuhasebeFisi.query.get(hareket.muhasebe_fisi_id)
                if fis:
                    if fis.resmi_defter_basildi:
                        return False, "Muhasebe fişi resmileştiği için silinemez!"
                    MuhasebeFisiDetay.query.filter_by(fis_id=fis.id).delete()
                    db.session.delete(fis)

            db.session.delete(hareket)
            db.session.commit()
            
            BankaHareketService.bakiye_guncelle(banka_id)
            return True, "Kayıt silindi."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    # --- YARDIMCI METODLAR ---

    @staticmethod
    def _handle_kasa_pair(hareket, user_id):
        from modules.kasa_hareket.models import KasaHareket
        from modules.kasa_hareket.services import KasaService 

        k_har = KasaHareket.query.filter_by(
            kasa_id=hareket.kasa_id,
            belge_no=hareket.belge_no,
            tarih=hareket.tarih
        ).first()

        if not k_har: k_har = KasaHareket()

        k_har.firma_id = hareket.firma_id
        k_har.donem_id = hareket.donem_id
        k_har.kasa_id = hareket.kasa_id
        k_har.tarih = hareket.tarih
        k_har.tutar = hareket.tutar
        k_har.belge_no = hareket.belge_no
        k_har.aciklama = f"Bankadan: {hareket.aciklama}"
        k_har.onaylandi = True
        
        tur_val = str(hareket.islem_turu)
        if 'giris' in tur_val or 'tahsilat' in tur_val:
            from enums import BankaIslemTuru as BIT
            k_har.islem_turu = BIT.VIRMAN_CIKIS
            k_har.karsi_banka_id = None 
            k_har.banka_id = hareket.banka_id 
        else:
            from enums import BankaIslemTuru as BIT
            k_har.islem_turu = BIT.VIRMAN_GIRIS
            k_har.banka_id = hareket.banka_id

        db.session.add(k_har)
        db.session.flush()
        KasaService.bakiye_guncelle(k_har.kasa_id)

    @staticmethod
    def _delete_kasa_pair(hareket):
        from modules.kasa_hareket.models import KasaHareket
        from modules.kasa_hareket.services import KasaService
        k_har = KasaHareket.query.filter_by(
            kasa_id=hareket.kasa_id, belge_no=hareket.belge_no
        ).first()
        if k_har:
            kid = k_har.kasa_id
            db.session.delete(k_har)
            KasaService.bakiye_guncelle(kid)

    @staticmethod
    def _handle_banka_pair(hareket):
        karsi = BankaHareket.query.filter_by(
            banka_id=hareket.karsi_banka_id,
            belge_no=hareket.belge_no
        ).first()

        if not karsi: karsi = BankaHareket()
        
        karsi.firma_id = hareket.firma_id
        karsi.donem_id = hareket.donem_id
        karsi.banka_id = hareket.karsi_banka_id
        karsi.karsi_banka_id = hareket.banka_id
        karsi.tarih = hareket.tarih
        karsi.tutar = hareket.tutar
        karsi.belge_no = hareket.belge_no
        karsi.aciklama = f"Virman: {hareket.aciklama}"
        
        tur_val = str(hareket.islem_turu)
        if 'giris' in tur_val:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_CIKIS
        else:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_GIRIS
            
        db.session.add(karsi)
        db.session.flush()
        BankaHareketService.bakiye_guncelle(karsi.banka_id)

    @staticmethod
    def _delete_banka_pair(hareket):
        karsi = BankaHareket.query.filter_by(
            banka_id=hareket.karsi_banka_id, belge_no=hareket.belge_no
        ).first()
        if karsi:
            bid = karsi.banka_id
            db.session.delete(karsi)
            BankaHareketService.bakiye_guncelle(bid)

# Alias
BankaService = BankaHareketService