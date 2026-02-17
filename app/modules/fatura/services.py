# app/modules/fatura/services.py (MySQL + AI Complete)(Redis + Babel Enhanced - Critical Updates)

"""
Fatura Modülü Servis Katmanı
Enterprise Grade - Full Refactored - MySQL + AI Enhanced
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
import logging

from sqlalchemy import select, and_, or_, delete, func, text
from sqlalchemy.orm import joinedload, selectinload
from flask import session
from flask_login import current_user

from app.extensions import db, cache
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.stok.models import StokKart, StokHareketi
from app.modules.cari.models import CariHareket, CariHesap
from app.modules.depo.models import Depo
from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
from app.modules.firmalar.models import Donem
from app.enums import (
    FaturaTuru, HareketTuru, CariIslemTuru, FaturaDurumu,
    ParaBirimi, StokBirimleri
)
from app.araclar import para_cevir, get_doviz_kuru

# Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants
VARSAYILAN_KDV_ORANI = Decimal('20.00')
MIN_FIYAT_LISTESI_ID = 1

from flask_babel import gettext as _, lazy_gettext


# Cache timeout constants
CACHE_TIMEOUT_SHORT = 300  # 5 dakika
CACHE_TIMEOUT_MEDIUM = 1800  # 30 dakika
CACHE_TIMEOUT_LONG = 3600  # 1 saat

# ============================================================
# 🔥 CUSTOM EXCEPTIONS
# ============================================================
class FaturaValidationError(Exception):
    """Fatura Validation Hatası"""
    pass


class FaturaNotFoundError(Exception):
    """Fatura Bulunamadı Hatası"""
    pass


class FaturaBusinessRuleError(Exception):
    """İş Kuralı İhlali"""
    pass


# ============================================================
# 📦 DATA TRANSFER OBJECTS (DTO)
# ============================================================
class FaturaDTO:
    """API Response için temiz data yapısı"""

    def __init__(self, fatura: Fatura):
        self.id = str(fatura.id)
        self.belge_no = fatura.belge_no
        self.tarih = fatura.tarih.isoformat() if fatura.tarih else None
        self.cari_unvan = fatura.cari.unvan if fatura.cari else None
        self.genel_toplam = float(fatura.genel_toplam or 0)
        self.doviz_turu = self._get_enum_value(fatura.doviz_turu)
        self.durum = self._get_enum_value(fatura.durum)

    @staticmethod
    def _get_enum_value(enum_val):
        """Enum veya String değeri güvenli şekilde al"""
        if enum_val is None:
            return None
        return enum_val.value if hasattr(enum_val, 'value') else str(enum_val)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


# ============================================================
# 💰 FİYAT HESAPLAMA SERVİSİ (AI Enhanced)
# ============================================================
class FiyatHesaplamaService:
    """
    Fiyat Hesaplama İşlemleri - AI Enhanced
    
    Özellikler:
    - Çapraz Kur Desteği
    - Fiyat Listesi Entegrasyonu
    - Min Miktar Baremi
    - AI Fiyat Anomali Tespiti
    - Piyasa Fiyat Karşılaştırması
    """
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_SHORT)
    def hesapla(
        stok_id: str,
        fatura_turu: str,
        fatura_para_birimi: str,
        fatura_kuru: Decimal,
        liste_id: Optional[str] = None,
        miktar: Optional[Decimal] = None,
        firma_id: Optional[str] = None,
        tenant_db=None
    ) -> Dict[str, Any]:
        """
        Stok fiyatını hesapla - CACHED  
        Stok fiyatını hesaplar - AI Enhanced
        
        Args:
            stok_id: Stok Kartı ID (UUID)
            fatura_turu: 'SATIS', 'ALIS'
            fatura_para_birimi: TL, USD, EUR
            fatura_kuru: Faturanın anlık kuru (Decimal)
            liste_id: Fiyat Listesi ID (UUID, Opsiyonel)
            miktar: Sipariş Miktarı (Baremli fiyat için)
            firma_id: Firma ID (UUID)
            tenant_db: Tenant DB session
        
        Returns:
            {
                'fiyat': Decimal,
                'iskonto_orani': Decimal,
                'kdv_orani': int,
                'birim': str,
                'kaynak': str,
                'ai_metadata': dict,
                'debug': dict
            }
        """

        if tenant_db is None:
            from app.extensions import get_tenant_db
            tenant_db = get_tenant_db()

        # 1. STOK KARTINI ÇEK (Eager Loading)
        stok = tenant_db.query(StokKart).options(
            joinedload(StokKart.kdv_grubu)
        ).filter(
            StokKart.id == stok_id,
            StokKart.aktif == True
        ).first()

        if not stok:
            raise ValueError(f"Stok bulunamadı: ID {stok_id}")

        # Kur validasyonu
        if not isinstance(fatura_kuru, Decimal):
            fatura_kuru = Decimal(str(fatura_kuru))

        if fatura_kuru <= 0:
            raise ValueError(f"Geçersiz kur değeri: {fatura_kuru}")

        # 2. BAZ FİYAT VE DÖVİZ TESPİTİ
        stok_doviz = getattr(stok, 'doviz_turu', 'TL') or 'TL'

        if fatura_turu in ['ALIS', 'ALIS_IADE']:
            baz_fiyat = Decimal(str(getattr(stok, 'alis_fiyati', 0) or 0))
        else:
            baz_fiyat = Decimal(str(getattr(stok, 'satis_fiyati', 0) or 0))

        iskonto_orani = Decimal('0.00')
        kaynak = f"Stok Kartı ({stok_doviz})"

        # 3. FİYAT LİSTESİ KONTROLÜ
        if liste_id and liste_id != '0':
            liste_detay = FiyatHesaplamaService._fiyat_listesinden_getir(
                liste_id, stok_id, miktar, firma_id, tenant_db
            )

            if liste_detay:
                baz_fiyat = Decimal(str(liste_detay['fiyat']))
                iskonto_orani = Decimal(str(liste_detay['iskonto_orani']))
                stok_doviz = liste_detay['doviz_turu']
                kaynak = f"Fiyat Listesi: {liste_detay['liste_adi']}"

        # 4. ÇAPRAZ KUR HESAPLAMA (TL üzerinden)
        tl_karsiligi = baz_fiyat

        if stok_doviz != 'TL':
            # Cache'ten kur çek
            cache_key = f"doviz_kuru:{stok_doviz}"
            sistem_kuru = cache.get(cache_key)

            if sistem_kuru is None:
                sistem_kuru = Decimal(str(get_doviz_kuru(stok_doviz)))
                cache.set(cache_key, sistem_kuru, timeout=3600)
            else:
                sistem_kuru = Decimal(str(sistem_kuru))

            if sistem_kuru <= 0:
                logger.warning(f"⚠️ Sistem kuru alınamadı ({stok_doviz}), 1.0 kullanılıyor")
                sistem_kuru = Decimal('1.0')

            tl_karsiligi = baz_fiyat * sistem_kuru

        # Fatura dövizine çevir
        nihai_fiyat = (tl_karsiligi / fatura_kuru).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )

        # 5. KDV ORANI
        kdv_orani = FiyatHesaplamaService._kdv_orani_hesapla(stok, fatura_turu)

        # 6. BİRİM
        birim = FiyatHesaplamaService._birim_getir(stok)

        # 7. AI FİYAT ANALİZİ
        ai_metadata = FiyatHesaplamaService._ai_fiyat_analizi(
            stok, nihai_fiyat, fatura_turu, tenant_db
        )

        logger.debug(
            f"💰 Fiyat Hesaplama: Stok={stok.kod}, "
            f"Baz={baz_fiyat} {stok_doviz}, TL={tl_karsiligi}, "
            f"Fatura={nihai_fiyat} {fatura_para_birimi}, Kaynak={kaynak}"
        )

        return {
            'fiyat': nihai_fiyat,
            'iskonto_orani': iskonto_orani,
            'kdv_orani': kdv_orani,
            'birim': birim,
            'kaynak': kaynak,
            'ai_metadata': ai_metadata,
            'debug': {
                'baz_fiyat': float(baz_fiyat),
                'stok_doviz': stok_doviz,
                'tl_karsiligi': float(tl_karsiligi),
                'fatura_kuru': float(fatura_kuru)
            }
        }

    @staticmethod
    def _fiyat_listesinden_getir(
        liste_id: str,
        stok_id: str,
        miktar: Optional[Decimal],
        firma_id: Optional[str],
        tenant_db
    ) -> Optional[Dict[str, Any]]:
        """Fiyat listesinden aktif detayı getirir (Min Miktar Baremli)"""

        bugun = date.today()

        # Liste kontrolü
        liste = tenant_db.query(FiyatListesi).filter(
            FiyatListesi.id == liste_id,
            FiyatListesi.aktif == True,
            or_(
                FiyatListesi.baslangic_tarihi == None,
                FiyatListesi.baslangic_tarihi <= bugun
            ),
            or_(
                FiyatListesi.bitis_tarihi == None,
                FiyatListesi.bitis_tarihi >= bugun
            )
        ).first()

        if not liste:
            return None

        # Detay sorgusu (Miktar baremi dahil)
        detay_query = tenant_db.query(FiyatListesiDetay).filter(
            FiyatListesiDetay.fiyat_listesi_id == liste.id,
            FiyatListesiDetay.stok_id == stok_id
        )

        # Miktar varsa baremli fiyat bul
        if miktar is not None and miktar > 0:
            detay_query = detay_query.filter(
                FiyatListesiDetay.min_miktar <= miktar
            ).order_by(FiyatListesiDetay.min_miktar.desc())
        else:
            detay_query = detay_query.filter(
                FiyatListesiDetay.min_miktar == 0
            )

        detay = detay_query.first()

        if not detay:
            return None

        return {
            'fiyat': detay.fiyat,
            'iskonto_orani': detay.iskonto_orani or 0,
            'doviz_turu': getattr(liste, 'doviz_turu', 'TL'),
            'liste_adi': liste.ad
        }

    @staticmethod
    def _kdv_orani_hesapla(stok: StokKart, fatura_turu: str) -> int:
        """KDV Grubundan oranı hesaplar"""
        varsayilan = int(VARSAYILAN_KDV_ORANI)

        if not stok.kdv_grubu:
            return varsayilan

        try:
            if fatura_turu in ['ALIS', 'ALIS_IADE']:
                return int(getattr(stok.kdv_grubu, 'alis_kdv_orani', varsayilan) or varsayilan)
            else:
                return int(getattr(stok.kdv_grubu, 'satis_kdv_orani', varsayilan) or varsayilan)
        except (AttributeError, ValueError, TypeError):
            return varsayilan

    @staticmethod
    def _birim_getir(stok: StokKart) -> str:
        """Stoktan birim bilgisini güvenli şekilde al"""
        try:
            if hasattr(stok, 'birim') and stok.birim:
                return getattr(stok.birim, 'value', 'ADET')
            return 'ADET'
        except:
            return 'ADET'

    @staticmethod
    def _ai_fiyat_analizi(
        stok: StokKart,
        hesaplanan_fiyat: Decimal,
        fatura_turu: str,
        tenant_db
    ) -> Dict[str, Any]:
        """
        AI Fiyat Anomali Tespiti
        
        Returns:
            {
                'onceki_ortalama': float,
                'fark_yuzde': float,
                'anomali': bool,
                'oneri': str
            }
        """

        try:
            # Son 30 günün ortalama fiyatını bul
            son_30_gun = date.today() - timedelta(days=30)

            # ✅ MySQL Aggregate Query
            stats = tenant_db.execute(text("""
                SELECT 
                    AVG(fk.birim_fiyat) as ort_fiyat,
                    MIN(fk.birim_fiyat) as min_fiyat,
                    MAX(fk.birim_fiyat) as max_fiyat,
                    COUNT(fk.id) as islem_sayisi
                FROM fatura_kalemleri fk
                INNER JOIN faturalar f ON f.id = fk.fatura_id
                WHERE fk.stok_id = :stok_id
                AND f.fatura_turu = :fatura_turu
                AND f.durum = 'ONAYLANDI'
                AND f.tarih >= :baslangic_tarih
                AND f.deleted_at IS NULL
            """), {
                'stok_id': stok.id,
                'fatura_turu': fatura_turu,
                'baslangic_tarih': son_30_gun
            }).fetchone()

            if stats and stats[0] and stats[3] > 0:
                ort_fiyat = Decimal(str(stats[0]))
                min_fiyat = Decimal(str(stats[1]))
                max_fiyat = Decimal(str(stats[2]))

                # Fark hesapla
                fark_yuzde = (
                    (hesaplanan_fiyat - ort_fiyat) / ort_fiyat * 100
                ).quantize(Decimal('0.01'))

                # Anomali kontrolü (±30% sapma)
                anomali = abs(fark_yuzde) > 30

                # Öneri oluştur
                if fark_yuzde > 30:
                    oneri = f"⚠️ Fiyat ortalamanın %{fark_yuzde} üzerinde!"
                elif fark_yuzde < -30:
                    oneri = f"💰 Fiyat ortalamanın %{abs(fark_yuzde)} altında (Fırsat?)"
                else:
                    oneri = "✅ Fiyat normal aralıkta"

                return {
                    'onceki_ortalama': float(ort_fiyat),
                    'min_fiyat': float(min_fiyat),
                    'max_fiyat': float(max_fiyat),
                    'fark_yuzde': float(fark_yuzde),
                    'anomali': anomali,
                    'oneri': oneri,
                    'islem_sayisi': stats[3]
                }

            else:
                return {
                    'onceki_ortalama': None,
                    'fark_yuzde': 0,
                    'anomali': False,
                    'oneri': '📊 Henüz yeterli veri yok',
                    'islem_sayisi': 0
                }

        except Exception as e:
            logger.error(f"❌ AI fiyat analizi hatası: {e}")
            return {
                'onceki_ortalama': None,
                'fark_yuzde': 0,
                'anomali': False,
                'oneri': 'Analiz yapılamadı',
                'islem_sayisi': 0
            }


# ============================================================
# 📝 FATURA KALEMI SERVİSİ
# ============================================================
class FaturaKalemService:
    """Fatura Kalemi İşlemleri (UPSERT + Hesaplama)"""

    @staticmethod
    def toplu_kaydet(
        fatura_id: str,
        form_data: Dict[str, Any],
        mevcut_kalemler: Dict[str, FaturaKalemi],
        tenant_db
    ) -> Tuple[List[FaturaKalemi], Dict[str, Decimal]]:
        """
        Fatura kalemlerini toplu olarak günceller/ekler
        
        Returns:
            (Kalemler Listesi, Toplamlar Dictionary)
        """

        ids = form_data.getlist('kalemler_id[]')
        stok_ids = form_data.getlist('kalemler_stok_id[]')
        miktarlar = form_data.getlist('kalemler_miktar[]')
        birimler = form_data.getlist('kalemler_birim[]')
        fiyatlar = form_data.getlist('kalemler_birim_fiyat[]')
        iskontolar = form_data.getlist('kalemler_indirim_orani[]')
        kdvs = form_data.getlist('kalemler_kdv_orani[]')

        islenen_ids = []
        kaydedilecek_kalemler = []

        toplamlar = {
            'ara_toplam': Decimal('0.00'),
            'iskonto_toplam': Decimal('0.00'),
            'kdv_toplam': Decimal('0.00'),
            'genel_toplam': Decimal('0.00')
        }

        for i in range(len(stok_ids)):
            if not stok_ids[i]:
                continue

            row_id = ids[i] if i < len(ids) and ids[i] and ids[i] != '0' else None

            # UPSERT Mantığı
            if row_id and row_id in mevcut_kalemler:
                kalem = mevcut_kalemler[row_id]
                islenen_ids.append(row_id)
            else:
                kalem = FaturaKalemi(fatura_id=fatura_id)
                kalem.sira_no = i + 1

            # Veriyi doldur
            kalem.stok_id = stok_ids[i]
            kalem.miktar = para_cevir(miktarlar[i])
            kalem.birim = birimler[i] if i < len(birimler) else 'ADET'
            kalem.birim_fiyat = para_cevir(fiyatlar[i])
            kalem.iskonto_orani = para_cevir(iskontolar[i] if i < len(iskontolar) else 0)
            kalem.kdv_orani = para_cevir(kdvs[i] if i < len(kdvs) else 0)

            # Hesaplamalar (before_insert event'te otomatik yapılacak ama burada da yapalım)
            kalem.hesapla()

            # Toplamları akümüle et
            toplamlar['ara_toplam'] += kalem.net_tutar
            toplamlar['iskonto_toplam'] += kalem.iskonto_tutari
            toplamlar['kdv_toplam'] += kalem.kdv_tutari
            toplamlar['genel_toplam'] += kalem.satir_toplami

            kaydedilecek_kalemler.append(kalem)

        # Silinecekleri bul
        silinecekler = [
            k for k_id, k in mevcut_kalemler.items()
            if k_id not in islenen_ids
        ]

        # Bulk Delete
        for k in silinecekler:
            tenant_db.delete(k)

        return kaydedilecek_kalemler, toplamlar


# ============================================================
# 📦 STOK HAREKET SERVİSİ
# ============================================================
class StokHareketService:
    """Stok Hareketi İşlemleri"""

    @staticmethod
    def faturadan_olustur(fatura: Fatura, tenant_db) -> None:
        """Fatura kalemlerinden Stok Hareketleri oluşturur"""

        # Eski hareketleri temizle
        tenant_db.execute(
            delete(StokHareketi).where(
                and_(
                    StokHareketi.firma_id == fatura.firma_id,
                    StokHareketi.kaynak_turu == 'fatura',
                    StokHareketi.kaynak_id == fatura.id
                )
            )
        )

        # Yön tayini
        hareket_yonu = StokHareketService._hareket_yonu_belirle(fatura.fatura_turu)

        # Toplu oluştur
        yeni_hareketler = []

        for kalem in fatura.kalemler:
            hareket = StokHareketService._hareket_objesi_olustur(
                fatura, kalem, hareket_yonu
            )
            yeni_hareketler.append(hareket)

        # Bulk Insert
        tenant_db.bulk_save_objects(yeni_hareketler)

        logger.info(
            f"📦 Stok Hareketi: {len(yeni_hareketler)} kayıt oluşturuldu "
            f"(Fatura: {fatura.belge_no})"
        )

    @staticmethod
    def _hareket_yonu_belirle(fatura_turu: str) -> str:
        """Fatura türüne göre stok hareket yönünü belirler"""

        # Enum değerini al
        if hasattr(fatura_turu, 'value'):
            fatura_turu = fatura_turu.value

        fatura_turu_upper = str(fatura_turu).upper()

        is_satis = ('SATIS' in fatura_turu_upper)
        is_iade = ('IADE' in fatura_turu_upper)

        if is_satis and not is_iade:
            return 'SATIS'
        elif not is_satis and not is_iade:
            return 'ALIS'
        elif is_satis and is_iade:
            return 'SATIS_IADE'
        else:
            return 'ALIS_IADE'

    @staticmethod
    def _hareket_objesi_olustur(
        fatura: Fatura,
        kalem: FaturaKalemi,
        hareket_yonu: str
    ) -> StokHareketi:
        """Tek bir Stok Hareketi objesi oluşturur"""

        sh = StokHareketi()
        sh.firma_id = fatura.firma_id
        sh.donem_id = fatura.donem_id
        sh.sube_id = fatura.sube_id

        # Giriş/Çıkış Depo Tayini
        if hareket_yonu in ['ALIS', 'SATIS_IADE']:
            sh.giris_depo_id = fatura.depo_id
            sh.cikis_depo_id = None
        else:
            sh.giris_depo_id = None
            sh.cikis_depo_id = fatura.depo_id

        sh.stok_id = kalem.stok_id
        sh.tarih = fatura.tarih
        sh.belge_no = fatura.belge_no
        sh.kaynak_turu = 'fatura'
        sh.kaynak_id = str(fatura.id)
        sh.kaynak_belge_detay_id = str(kalem.id)
        sh.hareket_turu = hareket_yonu
        sh.miktar = kalem.miktar
        sh.birim_fiyat = kalem.birim_fiyat
        sh.net_tutar = kalem.net_tutar
        sh.toplam_tutar = kalem.satir_toplami
        sh.doviz_turu = fatura.doviz_turu
        sh.doviz_kuru = fatura.doviz_kuru

        return sh


# ============================================================
# 💳 CARİ HAREKET SERVİSİ
# ============================================================
class CariHareketService:
    """Cari Hareket İşlemleri"""

    @staticmethod
    def faturadan_olustur(fatura: Fatura, tenant_db) -> None:
        """Faturadan Cari Hareket oluşturur"""

        # Eski hareketi temizle
        tenant_db.execute(
            delete(CariHareket).where(
                and_(
                    CariHareket.firma_id == fatura.firma_id,
                    CariHareket.kaynak_turu == 'fatura',
                    CariHareket.kaynak_id == fatura.id
                )
            )
        )

        # Yeni Hareket
        ch = CariHareketService._hareket_objesi_olustur(fatura)
        tenant_db.add(ch)

        bakiye = ch.borc - ch.alacak
        logger.info(
            f"💳 Cari Hareket: {fatura.cari.unvan} "
            f"({bakiye:+.2f} TL)"
        )

    @staticmethod
    def _hareket_objesi_olustur(fatura: Fatura) -> CariHareket:
        """Cari Hareket objesi oluşturur"""

        ch = CariHareket()
        ch.firma_id = fatura.firma_id
        ch.donem_id = fatura.donem_id
        ch.sube_id = fatura.sube_id
        ch.cari_id = fatura.cari_id
        ch.tarih = fatura.tarih
        ch.vade_tarihi = fatura.vade_tarihi
        ch.belge_no = fatura.belge_no
        ch.kaynak_turu = 'fatura'
        ch.kaynak_id = str(fatura.id)

        # İşlem türü tayini
        fatura_turu_str = fatura.fatura_turu.value if hasattr(fatura.fatura_turu, 'value') else str(fatura.fatura_turu)
        is_satis = ('SATIS' in fatura_turu_str.upper())
        is_iade = ('IADE' in fatura_turu_str.upper())

        if is_satis and not is_iade:
            ch.islem_turu = 'SATIS_FATURASI'
        elif not is_satis and not is_iade:
            ch.islem_turu = 'ALIS_FATURASI'
        elif is_satis and is_iade:
            ch.islem_turu = 'SATIS_IADE'
        else:
            ch.islem_turu = 'ALIS_IADE'

        ch.aciklama = fatura.aciklama or f"{fatura_turu_str} Faturası"

        # Borç/Alacak Tayini
        cari_borclanir = (is_satis and not is_iade) or (not is_satis and is_iade)

        if cari_borclanir:
            ch.borc = fatura.genel_toplam
            ch.alacak = Decimal('0.00')
        else:
            ch.borc = Decimal('0.00')
            ch.alacak = fatura.genel_toplam

        return ch


# ============================================================
# 📊 MUHASEBE ENTEGRASYON SERVİSİ
# ============================================================
class MuhasebeEntegrasyonService:
    """Muhasebe Modülü Entegrasyonu (Loose Coupling)"""

    @staticmethod
    def entegre_et_fatura(fatura_id: str, tenant_db) -> Tuple[bool, str]:
        """Faturayı Muhasebe Modülüne entegre eder"""

        try:
            # Lazy Import
            from app.modules.muhasebe.services import MuhasebeService

            fatura = tenant_db.query(Fatura).get(fatura_id)
            if not fatura:
                return False, "Fatura bulunamadı"

            # Muhasebe Fişi Oluştur
            fis = MuhasebeService.faturadan_fis_olustur(fatura)

            # Faturaya Bağla
            fatura.muhasebe_fis_id = str(fis.id)
            tenant_db.flush()

            logger.info(
                f"📊 Muhasebe Fişi: {fis.fis_no} oluşturuldu "
                f"(Fatura: {fatura.belge_no})"
            )
            return True, f"Muhasebe Fişi: {fis.fis_no}"

        except ImportError as e:
            logger.warning(f"⚠️ Muhasebe Modülü yüklenmedi: {e}")
            return False, "Muhasebe modülü bulunamadı"

        except Exception as e:
            logger.error(f"❌ Muhasebe Entegrasyon Hatası: {e}", exc_info=True)
            return False, str(e)


# ============================================================
# 🎯 ANA FATURA SERVİSİ (FACADE PATTERN) CACHE ENHANCEMENT
# ============================================================
class FaturaService:
    """Ana Fatura Servis Katmanı - MySQL + AI Optimized"""

    @staticmethod
    def save(
        form_data: Dict[str, Any],
        fatura: Optional[Fatura] = None,
        user: Any = None,
        tenant_db = None
    ) -> Tuple[bool, str]:
        """
        Fatura oluşturur veya günceller - MySQL Optimized
        
        Args:
            form_data: Form verisi (ImmutableMultiDict)
            fatura: Güncelleme için mevcut Fatura instance'ı
            user: Mevcut kullanıcı (current_user)
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """

        if tenant_db is None:
            from app.extensions import get_tenant_db
            tenant_db = get_tenant_db()

        try:
            is_new = fatura is None

            # 1. BAŞLIK OLUŞTUR/GÜNCELLE
            if is_new:
                fatura = Fatura(firma_id=user.firma_id)
                FaturaService._yeni_fatura_baslat(fatura, user, tenant_db)

            FaturaService._baslik_doldur(fatura, form_data)

            tenant_db.add(fatura)
            tenant_db.flush()

            # 2. KALEMLERI İŞLE (UPSERT)
            mevcut_kalemler = {str(k.id): k for k in fatura.kalemler}

            kaydedilecek_kalemler, toplamlar = FaturaKalemService.toplu_kaydet(
                str(fatura.id), form_data, mevcut_kalemler, tenant_db
            )

            # Bulk Save
            tenant_db.bulk_save_objects(kaydedilecek_kalemler)

            # 3. TOPLAM GÜNCELLEMESİ
            fatura.ara_toplam = toplamlar['ara_toplam']
            fatura.iskonto_toplam = toplamlar['iskonto_toplam']
            fatura.kdv_toplam = toplamlar['kdv_toplam']
            fatura.genel_toplam = toplamlar['genel_toplam']

            if fatura.doviz_kuru > 0:
                fatura.dovizli_toplam = (
                    fatura.genel_toplam / fatura.doviz_kuru
                ).quantize(Decimal('0.01'))

            # 4. DURUM KONTROLÜ
            if is_new or fatura.durum == 'TASLAK':
                fatura.durum = 'ONAYLANDI'

            # 5. AI ANALİZLERİ
            fatura.ai_analiz_guncelle()

            tenant_db.flush()

            # 6. ENTEGRASYONLARI ÇALIŞTIR (sadece onaylıysa)
            if fatura.durum == 'ONAYLANDI':
                FaturaService.faturayi_isleme_al(fatura, tenant_db)

            # 7. COMMIT
            tenant_db.commit()

            logger.info(
                f"✅ Fatura Kaydedildi: {fatura.belge_no} "
                f"({'Yeni' if is_new else 'Güncelleme'}) - "
                f"Toplam: {fatura.genel_toplam} {fatura.doviz_turu}"
            )

            return True, f"Fatura {fatura.belge_no} başarıyla kaydedildi."

        except FaturaValidationError as e:
            tenant_db.rollback()
            logger.warning(f"⚠️ Validasyon Hatası: {e}")
            return False, str(e)

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Fatura Kaydetme Hatası: {e}", exc_info=True)
            return False, f"Beklenmeyen hata: {str(e)}"

    @staticmethod
    def _yeni_fatura_baslat(fatura: Fatura, user: Any, tenant_db) -> None:
        """Yeni fatura için başlangıç değerlerini atar"""

        # Şube Tayini
        if hasattr(user, 'yetkili_subeler') and user.yetkili_subeler:
            fatura.sube_id = str(user.yetkili_subeler[0].id)
        else:
            raise FaturaValidationError("Kullanıcının yetkili şubesi yok")

        # Dönem Tayini
        if 'aktif_donem_id' in session:
            fatura.donem_id = session['aktif_donem_id']
        else:
            aktif_donem = tenant_db.query(Donem).filter(
                Donem.firma_id == user.firma_id,
                Donem.aktif == True
            ).first()

            if aktif_donem:
                fatura.donem_id = str(aktif_donem.id)
            else:
                raise FaturaValidationError("Aktif dönem bulunamadı")

    @staticmethod
    def _baslik_doldur(fatura: Fatura, form_data: Dict[str, Any]) -> None:
        """Form verisinden fatura başlığını doldurur"""

        # Tarih
        tarih_str = form_data.get('tarih')
        if isinstance(tarih_str, str):
            fatura.tarih = datetime.strptime(tarih_str, '%Y-%m-%d').date()
        else:
            fatura.tarih = tarih_str or date.today()

        # Diğer Alanlar
        fatura.belge_no = form_data.get('belge_no')
        fatura.dis_belge_no = form_data.get('dis_belge_no')
        fatura.vade_tarihi = form_data.get('vade_tarihi') or fatura.tarih
        fatura.cari_id = form_data.get('cari_id')
        fatura.depo_id = form_data.get('depo_id')
        fatura.fatura_turu = form_data.get('fatura_turu')
        fatura.aciklama = form_data.get('aciklama')
        fatura.sevk_adresi = form_data.get('sevk_adresi')

        # Fiyat Listesi
        fl_id = form_data.get('fiyat_listesi_id')
        if fl_id and fl_id != '0':
            fatura.fiyat_listesi_id = fl_id
        else:
            fatura.fiyat_listesi_id = None

        # Döviz
        fatura.doviz_turu = form_data.get('doviz_turu', 'TL')
        fatura.doviz_kuru = para_cevir(form_data.get('doviz_kuru', 1))

        # Ödeme Planı
        odeme_plani_id = form_data.get('odeme_plani_id')
        if odeme_plani_id and odeme_plani_id != '0':
            fatura.odeme_plani_id = odeme_plani_id

        # Gün adı (raporlama için)
        if fatura.tarih:
            gun_adlari = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
            fatura.gun_adi = gun_adlari[fatura.tarih.weekday()]

    @staticmethod
    def faturayi_isleme_al(fatura: Fatura, tenant_db) -> None:
        """Faturayı Stok, Cari ve Muhasebe modüllerine entegre eder"""

        # 1. Stok Hareketleri
        StokHareketService.faturadan_olustur(fatura, tenant_db)

        # 2. Cari Hareket
        CariHareketService.faturadan_olustur(fatura, tenant_db)

        # 3. Muhasebe Entegrasyonu
        basari, mesaj = MuhasebeEntegrasyonService.entegre_et_fatura(str(fatura.id), tenant_db)
        if not basari:
            logger.warning(f"⚠️ Muhasebe entegrasyonu atlandı: {mesaj}")

    @staticmethod
    def sil(fatura_id: str, user: Any, tenant_db) -> Tuple[bool, str]:
        """Faturayı ve ilişkili tüm kayıtları siler (Soft Delete)"""

        try:
            fatura = tenant_db.query(Fatura).filter_by(
                id=fatura_id,
                firma_id=user.firma_id
            ).first()

            if not fatura:
                return False, "Fatura bulunamadı"

            # Onaylı Fatura Kontrolü
            if fatura.durum == 'ONAYLANDI':
                logger.warning(
                    f"⚠️ Onaylı Fatura Silme Denemesi: {fatura.belge_no} "
                    f"(Kullanıcı: {user.email})"
                )
                return False, "Onaylı fatura silinemez. Önce iptal edin."

            # Soft Delete
            fatura.deleted_at = datetime.now()
            fatura.deleted_by = str(user.id)

            tenant_db.commit()

            logger.info(
                f"✅ Fatura Silindi (soft): {fatura.belge_no} "
                f"(Kullanıcı: {user.email})"
            )
            return True, "Fatura başarıyla silindi."

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Fatura Silme Hatası: {e}", exc_info=True)
            return False, f"Silme işlemi başarısız: {str(e)}"

    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_MEDIUM)
    def get_by_id(fatura_id: str, firma_id: str, tenant_db=None) -> Optional[Fatura]:
        """
        ID'ye göre fatura getir - CACHED
        
        Args:
            fatura_id: Fatura ID (UUID)
            firma_id: Firma ID (UUID)
            tenant_db: Tenant DB session
        
        Returns:
            Fatura instance veya None
        """
        if tenant_db is None:
            from app.extensions import get_tenant_db
            tenant_db = get_tenant_db()
        
        try:
            # ✅ MySQL Optimized Query (Mevcut kod aynı kalıyor)
            fatura = tenant_db.query(Fatura).options(
                selectinload(Fatura.kalemler).joinedload(FaturaKalemi.stok),
                joinedload(Fatura.cari),
                joinedload(Fatura.depo)
            ).filter(
                Fatura.id == fatura_id,
                Fatura.firma_id == firma_id,
                Fatura.deleted_at.is_(None)
            ).first()
            
            return fatura
        
        except Exception as e:
            logger.error(f"❌ Fatura getirme hatası (ID: {fatura_id}): {e}")
            return None