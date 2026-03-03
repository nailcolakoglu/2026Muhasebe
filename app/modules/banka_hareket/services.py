# app/modules/banka_hareket/services.py

from typing import Dict, Any, Tuple, Optional, List
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func
import logging

from app.extensions import get_tenant_db # 🔥 SAAS MİMARİSİ İÇİN ŞART
from app.modules.banka.models import BankaHesap
from app.modules.banka_hareket.models import BankaHareket
from app.enums import BankaIslemTuru, CariIslemTuru
from app.araclar import para_cevir, numara_uret

# Muhasebe ve Cari servislerini içerde çağıracağız (Circular import önlemek için)
from app.signals import banka_hareket_olusturuldu

logger = logging.getLogger(__name__)

class BankaHareketService:
    
    @staticmethod
    def get_form_options(firma_id: str) -> Tuple[List, List, List]:
        """
        Form için gerekli olan Banka, Cari ve Kasa listelerini hazırlar (Tenant DB).
        """
        tenant_db = get_tenant_db()
        from app.modules.kasa.models import Kasa
        from app.modules.cari.models import CariHesap
        
        # 1. Bankalar
        bankalar = tenant_db.query(BankaHesap).filter_by(firma_id=firma_id).all()
        
        if not bankalar:
            logger.warning("⚠️ Sistemde kayıtlı banka hesabı bulunamadı!")
            
        b_opts = []
        for b in bankalar:
            doviz = getattr(b, 'doviz_cinsi', 'TL') or 'TL'
            sube = getattr(b, 'sube_adi', '') or ''
            b_opts.append((str(b.id), f"{b.banka_adi} / {sube} ({doviz})"))

        # 2. Cariler
        cariler = tenant_db.query(CariHesap).filter_by(firma_id=firma_id, aktif=True).order_by(CariHesap.unvan).all()
        c_opts = [(str(c.id), f"{c.unvan}") for c in cariler]

        # 3. Kasalar
        kasalar = tenant_db.query(Kasa).filter_by(firma_id=firma_id).all() 
        k_opts = []
        for k in kasalar:
            doviz = getattr(k.doviz_turu, 'name', str(k.doviz_turu)) if hasattr(k, 'doviz_turu') else 'TL'
            k_opts.append((str(k.id), f"{k.ad} ({doviz})"))

        return b_opts, c_opts, k_opts

    @staticmethod
    def get_by_id(hareket_id: str) -> Optional[BankaHareket]:
        tenant_db = get_tenant_db()
        return tenant_db.get(BankaHareket, str(hareket_id))

    @staticmethod
    def bakiye_guncelle(banka_id: str):
        """Banka bakiyesini yeniden hesaplar (Tenant DB)."""
        if not banka_id: return
        
        tenant_db = get_tenant_db()
        
        # Girişler
        girisler = tenant_db.query(func.coalesce(func.sum(BankaHareket.tutar), 0)).filter(
            BankaHareket.banka_id == str(banka_id),
            BankaHareket.islem_turu.in_([
                BankaIslemTuru.TAHSILAT, 
                BankaIslemTuru.VIRMAN_GIRIS,
                BankaIslemTuru.POS_TAHSILAT
            ])
        ).scalar()

        # Çıkışlar
        cikislar = tenant_db.query(func.coalesce(func.sum(BankaHareket.tutar), 0)).filter(
            BankaHareket.banka_id == str(banka_id),
            BankaHareket.islem_turu.in_([
                BankaIslemTuru.TEDIYE, 
                BankaIslemTuru.VIRMAN_CIKIS
            ])
        ).scalar()

        banka = tenant_db.get(BankaHesap, str(banka_id))
        if banka:
            banka.bakiye = Decimal(str(girisler)) - Decimal(str(cikislar))
            tenant_db.commit()

    @staticmethod
    def islem_kaydet(data: Dict[str, Any], user_id: str, hareket_id: str = None) -> Tuple[bool, str]:
        tenant_db = get_tenant_db()
        
        try:
            # 1. TEMEL KONTROLLER
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

            # 2. NESNE OLUŞTURMA
            if hareket_id:
                hareket = tenant_db.get(BankaHareket, str(hareket_id))
                if not hareket: return False, "Hareket bulunamadı."
            else:
                hareket = BankaHareket()
                hareket.belge_no = numara_uret(data['firma_id'], 'BANKA', datetime.now().year, 'DEC-', 6)

            # 3. VERİ ATAMA
            hareket.firma_id = data['firma_id']
            hareket.donem_id = data['donem_id']
            hareket.banka_id = str(data['banka_id'])
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
                hareket.cari_id = str(data['cari_id'])
            elif karsi_taraf == 'kasa' and data.get('kasa_id'):
                hareket.kasa_id = str(data['kasa_id'])
            elif karsi_taraf == 'banka' and data.get('hedef_banka_id'): 
                hareket.karsi_banka_id = str(data['hedef_banka_id'])

            tenant_db.add(hareket)
            tenant_db.flush() # ID'nin oluşması için

            # 4. ENTEGRASYONLAR (Temizlik ve Yeniden Ekleme)
            
            if hareket.id:
                from app.modules.cari.models import CariHareket
                tenant_db.query(CariHareket).filter(
                    CariHareket.kaynak_turu.in_(['BANKA', 'banka']),
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
                    borc=hareket.tutar if c_yon == 'borc' else 0,
                    alacak=hareket.tutar if c_yon == 'alacak' else 0,
                    aciklama=f"Banka: {hareket.aciklama}",
                    kaynak_ref={'tur': 'BANKA', 'id': str(hareket.id)},
                    donem_id=hareket.donem_id
                )

            # B) Virman Entegrasyonları (Aynı işlem Kasa veya Diğer Banka hareketlerine de işlenmeli)
            if hareket.kasa_id:
                BankaHareketService._handle_kasa_pair(hareket, tenant_db)
            
            if hareket.karsi_banka_id:
                BankaHareketService._handle_banka_pair(hareket, tenant_db)

            # C) Muhasebe Entegrasyonu
            from app.modules.muhasebe.services import MuhasebeEntegrasyonService
            basari, mesaj = MuhasebeEntegrasyonService.entegre_et_banka(str(hareket.id))
            if not basari:
                logger.warning(f"⚠️ Banka Muhasebe Uyarısı: {mesaj}")

            tenant_db.commit()
            
            # Bakiyeleri Güncelle
            BankaHareketService.bakiye_guncelle(hareket.banka_id)
            
            # SİNYAL ATEŞLE (Diğer modüller haber alsın)
            banka_hareket_olusturuldu.send(hareket)
            
            msg = "İşlem başarıyla kaydedildi."
            if basari: msg += " (Yevmiye Fişi Kesildi)"
            return True, msg

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ BANKA KAYIT HATASI: {str(e)}", exc_info=True)
            return False, f"Sistem hatası: {str(e)}"

    @staticmethod
    def islem_sil(hareket_id: str) -> Tuple[bool, str]:
        tenant_db = get_tenant_db()
        hareket = tenant_db.get(BankaHareket, str(hareket_id))
        if not hareket: return False, "Kayıt bulunamadı."
        
        try:
            banka_id = hareket.banka_id
            
            # 1.Cari Hareketlerini Sil
            from app.modules.cari.models import CariHareket
            from app.modules.cari.services import CariService
            
            tenant_db.query(CariHareket).filter(
                CariHareket.kaynak_turu.in_(['BANKA', 'banka']), 
                CariHareket.kaynak_id == str(hareket.id)
            ).delete(synchronize_session=False)

            # 2.Virman Karşı Bacaklarını Sil
            if hareket.kasa_id:
                BankaHareketService._delete_kasa_pair(hareket, tenant_db)
            if hareket.karsi_banka_id:
                BankaHareketService._delete_banka_pair(hareket, tenant_db)

            # 3.Muhasebe Fişini Sil
            if hareket.muhasebe_fisi_id:
                from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay
                fis = tenant_db.get(MuhasebeFisi, str(hareket.muhasebe_fisi_id))
                if fis:
                    if fis.resmi_defter_basildi:
                        return False, "Muhasebe fişi resmileştiği için bu banka hareketi silinemez!"
                    tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=fis.id).delete()
                    tenant_db.delete(fis)

            tenant_db.delete(hareket)
            tenant_db.commit()
            
            # Bakiye Güncellemeleri
            BankaHareketService.bakiye_guncelle(banka_id)
            if hareket.cari_id:
                CariService.bakiye_hesapla_ve_guncelle(hareket.cari_id)
                
            return True, "Kayıt silindi."
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Banka Silme Hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    # --- YARDIMCI METODLAR ---

    @staticmethod
    def _handle_kasa_pair(hareket, tenant_db):
        from app.modules.kasa_hareket.models import KasaHareket
        from app.modules.kasa_hareket.services import KasaService 

        k_har = tenant_db.query(KasaHareket).filter_by(
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
        k_har.aciklama = f"Bankadan Virman: {hareket.aciklama}"
        k_har.onaylandi = True
        
        tur_val = str(hareket.islem_turu)
        if 'giris' in tur_val or 'tahsilat' in tur_val:
            from app.enums import BankaIslemTuru as BIT
            k_har.islem_turu = BIT.VIRMAN_CIKIS # Bankaya girdiyse, Kasadan çıkmıştır
            k_har.karsi_banka_id = hareket.banka_id 
        else:
            from app.enums import BankaIslemTuru as BIT
            k_har.islem_turu = BIT.VIRMAN_GIRIS # Bankadan çıktıysa, Kasaya girmiştir
            k_har.karsi_banka_id = hareket.banka_id

        tenant_db.add(k_har)
        tenant_db.flush()
        KasaService.bakiye_guncelle(str(k_har.kasa_id))

    @staticmethod
    def _delete_kasa_pair(hareket, tenant_db):
        from app.modules.kasa_hareket.models import KasaHareket
        from app.modules.kasa_hareket.services import KasaService
        k_har = tenant_db.query(KasaHareket).filter_by(
            kasa_id=hareket.kasa_id, belge_no=hareket.belge_no
        ).first()
        if k_har:
            kid = k_har.kasa_id
            tenant_db.delete(k_har)
            tenant_db.flush()
            KasaService.bakiye_guncelle(str(kid))

    @staticmethod
    def _handle_banka_pair(hareket, tenant_db):
        karsi = tenant_db.query(BankaHareket).filter_by(
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
        karsi.aciklama = f"Bankalar Arası Virman: {hareket.aciklama}"
        
        tur_val = str(hareket.islem_turu)
        if 'giris' in tur_val or 'tahsilat' in tur_val:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_CIKIS # Bu bankaya girdiyse, karşı bankadan çıkmıştır
        else:
            karsi.islem_turu = BankaIslemTuru.VIRMAN_GIRIS
            
        tenant_db.add(karsi)
        tenant_db.flush()
        BankaHareketService.bakiye_guncelle(str(karsi.banka_id))

    @staticmethod
    def _delete_banka_pair(hareket, tenant_db):
        karsi = tenant_db.query(BankaHareket).filter_by(
            banka_id=hareket.karsi_banka_id, belge_no=hareket.belge_no
        ).first()
        if karsi:
            bid = karsi.banka_id
            tenant_db.delete(karsi)
            tenant_db.flush()
            BankaHareketService.bakiye_guncelle(str(bid))

# Alias (Routes.py içinde kullanılıyorsa diye bırakıyoruz)
BankaService = BankaHareketService