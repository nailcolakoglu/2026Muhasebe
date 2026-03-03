# app/modules/kasa_hareket/services.py

from typing import Dict, Any, Tuple, Optional
from decimal import Decimal
from datetime import datetime
import logging
from sqlalchemy import func

from app.extensions import get_tenant_db # 🔥 SAAS MİMARİSİ İÇİN ŞART
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.kasa.models import Kasa
from app.enums import BankaIslemTuru, CariIslemTuru
from app.araclar import para_cevir, numara_uret

# Diğer servisleri fonksiyon içlerinde çağırarak Circular Import (Döngüsel İçe Aktarma) hatalarını önleyeceğiz
from app.signals import kasa_hareket_olusturuldu

logger = logging.getLogger(__name__)

class KasaService:
    
    @staticmethod
    def get_by_id(hareket_id: str) -> Optional[KasaHareket]:
        tenant_db = get_tenant_db()
        return tenant_db.get(KasaHareket, str(hareket_id))

    @staticmethod
    def bakiye_guncelle(kasa_id: str):
        """Kasa bakiyesini tüm hareketleri tarayarak kuruşu kuruşuna yeniden hesaplar"""
        if not kasa_id: return
        tenant_db = get_tenant_db()
        
        giris_turleri = ['TAHSILAT', 'VIRMAN_GIRIS', 'POS_TAHSILAT', 'GIRIS', 'tahsilat', 'virman_giris']
        if hasattr(BankaIslemTuru, 'TAHSILAT'):
            giris_turleri.extend([BankaIslemTuru.TAHSILAT, BankaIslemTuru.VIRMAN_GIRIS])

        cikis_turleri = ['TEDIYE', 'VIRMAN_CIKIS', 'CIKIS', 'tediye', 'virman_cikis']
        if hasattr(BankaIslemTuru, 'TEDIYE'):
            cikis_turleri.extend([BankaIslemTuru.TEDIYE, BankaIslemTuru.VIRMAN_CIKIS])

        girisler = tenant_db.query(func.coalesce(func.sum(KasaHareket.tutar), 0)).filter(
            KasaHareket.kasa_id == str(kasa_id),
            KasaHareket.onaylandi == True,
            KasaHareket.islem_turu.in_(giris_turleri)
        ).scalar() or Decimal('0.00')

        cikislar = tenant_db.query(func.coalesce(func.sum(KasaHareket.tutar), 0)).filter(
            KasaHareket.kasa_id == str(kasa_id),
            KasaHareket.onaylandi == True,
            KasaHareket.islem_turu.in_(cikis_turleri)
        ).scalar() or Decimal('0.00')

        kasa = tenant_db.get(Kasa, str(kasa_id))
        if kasa:
            kasa.bakiye = Decimal(str(girisler)) - Decimal(str(cikislar))
            tenant_db.commit()

    @staticmethod
    def islem_kaydet(data: Dict[str, Any], user_id: str, hareket_id: str = None) -> Tuple[bool, str]:
        tenant_db = get_tenant_db()
        try:
            # 1. TEMEL KONTROLLER
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

            # 2. NESNE OLUŞTURMA VEYA GÜNCELLEME
            if hareket_id:
                hareket = tenant_db.get(KasaHareket, str(hareket_id))
                if not hareket: return False, "Hareket bulunamadı."
            else:
                hareket = KasaHareket()
                hareket.belge_no = numara_uret(data['firma_id'], 'KASA', datetime.now().year, 'MAK-', 6)

            # 3. VERİ ATAMA
            hareket.firma_id = data['firma_id']
            hareket.donem_id = data['donem_id']
            hareket.kasa_id = str(data['kasa_id'])
            hareket.tarih = tarih_val
            hareket.tutar = tutar
            hareket.aciklama = data.get('aciklama', '')
            hareket.plasiyer_id = str(user_id) if user_id else None
            hareket.onaylandi = True

            # Yön ve Taraf
            hedef_turu = data.get('karsi_hesap_turu') or data.get('karsi_taraf') or 'cari'
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
                hareket.cari_id = str(data['cari_id'])
            elif hedef_turu == 'banka' and data.get('banka_id'):
                hareket.banka_id = str(data['banka_id'])
            elif hedef_turu == 'kasa' and data.get('karsi_kasa_id'):
                hareket.karsi_kasa_id = str(data['karsi_kasa_id'])

            tenant_db.add(hareket)
            tenant_db.flush() # ID'nin DB'de oluşması için

            # 4. ENTEGRASYONLAR
            
            # Güncelleme modundaysa eski Cari Hareketleri temizle
            if hareket.id:
                from app.modules.cari.models import CariHareket
                tenant_db.query(CariHareket).filter(
                    CariHareket.kaynak_turu.in_(['KASA', 'kasa']),
                    CariHareket.kaynak_id == str(hareket.id)
                ).delete(synchronize_session=False)

            # A) Cari Entegrasyonu
            if hareket.cari_id:
                from app.modules.cari.services import CariService
                c_yon = 'alacak' if islem_yonu == 'giris' else 'borc'
                c_tur = CariIslemTuru.TAHSILAT if islem_yonu == 'giris' else CariIslemTuru.TEDIYE
                
                CariService.hareket_ekle(
                    cari_id=hareket.cari_id,
                    islem_turu=c_tur,
                    belge_no=hareket.belge_no,
                    tarih=hareket.tarih,
                    borc=hareket.tutar if c_yon == 'borc' else Decimal('0.00'),
                    alacak=hareket.tutar if c_yon == 'alacak' else Decimal('0.00'),
                    aciklama=f"Kasa: {hareket.aciklama}",
                    kaynak_ref={'tur': 'KASA', 'id': str(hareket.id)},
                    donem_id=hareket.donem_id,
                    tenant_db=tenant_db
                )

            # B) Virman Karşı Bacak
            if hareket.karsi_kasa_id:
                KasaService._handle_virman_pair(hareket, user_id, tenant_db)

            # C) Muhasebe Entegrasyonu
            from app.modules.muhasebe.services import MuhasebeEntegrasyonService
            basari, mesaj = MuhasebeEntegrasyonService.entegre_et_kasa(str(hareket.id))
            if not basari:
                logger.warning(f"⚠️ Kasa Muhasebe Entegrasyon Uyarısı: {mesaj}")

            tenant_db.commit()
            
            # İşlem bittikten sonra bakiye güncelle ve sinyal fırlat
            KasaService.bakiye_guncelle(hareket.kasa_id)
            kasa_hareket_olusturuldu.send(hareket)
            
            msg = "İşlem başarıyla kaydedildi."
            if basari: msg += " (Muhasebe Fişi Kesildi)"
            return True, msg

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ KASA KAYIT HATASI: {str(e)}", exc_info=True)
            return False, f"Veritabanı hatası: {str(e)}"

    @staticmethod
    def islem_sil(hareket_id: str) -> Tuple[bool, str]:
        tenant_db = get_tenant_db()
        hareket = tenant_db.get(KasaHareket, str(hareket_id))
        if not hareket: return False, "Kayıt bulunamadı."
        
        try:
            logger.info(f"🗑️ SİLME İŞLEMİ BAŞLADI: KasaHareket #{hareket_id}")
            kasa_id = hareket.kasa_id
            
            # 1. CARİ HAREKETLERİ SİL
            from app.modules.cari.models import CariHareket
            from app.modules.cari.services import CariService
            
            silinen_cari_sayisi = tenant_db.query(CariHareket).filter(
                CariHareket.kaynak_turu.in_(['KASA', 'kasa']), 
                CariHareket.kaynak_id == str(hareket.id)
            ).delete(synchronize_session=False)
            
            logger.debug(f"   -> Silinen Cari Hareket Sayısı: {silinen_cari_sayisi}")

            # 2. VİRMAN SİLME (Karşı Kasa İşlemi)
            if hareket.karsi_kasa_id:
                KasaService._delete_virman_pair(hareket, tenant_db)
            
            # 3. MUHASEBE FİŞİ SİLME
            if hareket.muhasebe_fisi_id:
                logger.debug(f"   -> Muhasebe Fiş ID bulundu: {hareket.muhasebe_fisi_id}")
                from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay
                fis = tenant_db.get(MuhasebeFisi, str(hareket.muhasebe_fisi_id))
                if fis:
                    if fis.resmi_defter_basildi:
                        return False, "Bu işlemin muhasebe fişi resmileştiği için silinemez!"
                    
                    # Detayları ve fişi sil
                    tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=fis.id).delete()
                    tenant_db.delete(fis)
                    logger.debug("   -> Muhasebe Fişi Silindi.")
            
            # 4. KASA HAREKETİ SİLME
            cari_id = hareket.cari_id
            tenant_db.delete(hareket)
            tenant_db.commit()
            logger.info("✅ Kasa silme işlemi commit edildi.")

            # 5. BAKİYE GÜNCELLEMELERİ
            KasaService.bakiye_guncelle(kasa_id)
            if cari_id:
                CariService.bakiye_hesapla_ve_guncelle(cari_id, tenant_db=tenant_db)

            return True, "Kayıt ve bağlı tüm işlemler silindi."
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ KASA SİLME HATASI: {str(e)}", exc_info=True)
            return False, f"Silme hatası: {str(e)}"

    @staticmethod
    def _handle_virman_pair(kaynak: KasaHareket, user_id: str, tenant_db):
        """Kasa'dan Kasa'ya virman yapıldığında hedef kasaya otomatik giriş/çıkış atar."""
        karsi = tenant_db.query(KasaHareket).filter_by(
            kasa_id=kaynak.karsi_kasa_id, 
            karsi_kasa_id=kaynak.kasa_id,
            belge_no=kaynak.belge_no, 
            tarih=kaynak.tarih
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
        karsi.plasiyer_id = str(user_id) if user_id else None
        karsi.onaylandi = True
        
        tur = str(kaynak.islem_turu).lower()
        if 'cikis' in tur or 'tediye' in tur:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_GIRIS
        else:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_CIKIS
            
        tenant_db.add(karsi)
        tenant_db.flush()
        KasaService.bakiye_guncelle(str(karsi.kasa_id))

    @staticmethod
    def _delete_virman_pair(kaynak: KasaHareket, tenant_db):
        karsi = tenant_db.query(KasaHareket).filter_by(
            kasa_id=kaynak.karsi_kasa_id, 
            karsi_kasa_id=kaynak.kasa_id,
            belge_no=kaynak.belge_no
        ).first()
        
        if karsi:
            kid = karsi.kasa_id
            tenant_db.delete(karsi)
            tenant_db.flush()
            KasaService.bakiye_guncelle(str(kid))

# Geriye dönük uyumluluk (Eski kodlarda KasaHareketService olarak çağrılmış olabilir)
KasaHareketService = KasaService