# app/modules/fatura/services.py
"""
Fatura Modülü Servis Katmanı
Enterprise Grade - Full Refactored Version
"""
from app.services.n8n_client import N8NClient

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import logging

from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import joinedload, selectinload
from flask import session
from flask_login import current_user

from app.extensions import db
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
from decimal import Decimal, ROUND_HALF_UP

# Logger Configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants
VARSAYILAN_KDV_ORANI = Decimal('20.00')
MIN_FIYAT_LISTESI_ID = 1


# ============================================================
# 🔥 CUSTOM EXCEPTIONS
# ============================================================
class FaturaValidationError(Exception):
    """Fatura Validation Hatası"""
    pass


class FaturaNotFoundError(Exception):
    """Fatura Bulunamadı Hatası"""
    pass


# ============================================================
# 📦 DATA TRANSFER OBJECTS (DTO)
# ============================================================
class FaturaDTO:
    """API Response için temiz data yapısı"""
    
    def __init__(self, fatura:  Fatura):
        self.id = fatura.id
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
# 💰 FİYAT HESAPLAMA SERVİSİ (ÇAPRAZ KUR + FİYAT LİSTESİ)
# ============================================================
class FiyatHesaplamaService:
    """
    Fiyat Hesaplama İşlemleri
    - Çapraz Kur Desteği (Stok USD, Fatura EUR)
    - Fiyat Listesi Desteği (Kampanyalar, Bayi Fiyatları)
    - Min Miktar Baremi Desteği
    """
    
    @staticmethod
    def hesapla(
        stok_id: int,
        fatura_turu: str,
        fatura_para_birimi: str,
        fatura_kuru:  Decimal,
        liste_id: Optional[int] = None,
        miktar: Optional[Decimal] = None,
        firma_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Stok fiyatını hesaplar
        
        Args:
            stok_id:  Stok Kartı ID
            fatura_turu: 'satis', 'alis'
            fatura_para_birimi: TL, USD, EUR
            fatura_kuru: Faturanın anlık kuru
            liste_id:  Fiyat Listesi ID (Opsiyonel)
            miktar: Sipariş Miktarı (Miktar Baremi İçin)
            firma_id:  Firma ID
            
        Returns:
            {
                'fiyat':  Decimal,
                'iskonto_orani': Decimal,
                'kdv_orani': int,
                'birim':  str,
                'kaynak': str,
                'debug': {}
            }
        """
        
        # 1.STOK KARTINI ÇEK (EAGER LOADING)
        stok = db.session.execute(
            select(StokKart)
            .options(joinedload(StokKart.kdv_grubu))
            .where(StokKart.id == stok_id)
            .where(StokKart.aktif == True)
        ).unique().scalar_one_or_none()  # ✅ unique() eklendi
        
        if not stok: 
            raise ValueError(f"Stok bulunamadı: ID {stok_id}")

        if not isinstance(fatura_kuru, Decimal):
            fatura_kuru = Decimal(str(fatura_kuru))

        # Kur Validasyonu
        if fatura_kuru <= 0:
            raise ValueError(f"Geçersiz kur değeri: {fatura_kuru}")
        
        # 2.BAZ FİYAT VE DÖVİZ TESPİTİ
        stok_doviz = getattr(stok, 'doviz_turu', ParaBirimi.TL.value) or ParaBirimi.TL.value
        
        if fatura_turu in ['alis', 'alis_iade']:
            baz_fiyat = Decimal(str(getattr(stok, 'alis_fiyati', 0) or 0))
        else:
            baz_fiyat = Decimal(str(getattr(stok, 'satis_fiyati', 0) or 0))
        
        iskonto_orani = Decimal('0.00')
        kaynak = f"Stok Kartı ({stok_doviz})"
        
        # 3.FİYAT LİSTESİ KONTROLÜ (ÖNCELİKLİ)
        if liste_id and liste_id >= MIN_FIYAT_LISTESI_ID:
            liste_detay = FiyatHesaplamaService._fiyat_listesinden_getir(
                liste_id, stok_id, miktar, firma_id
            )
            
            if liste_detay:
                baz_fiyat = Decimal(str(liste_detay['fiyat']))
                iskonto_orani = Decimal(str(liste_detay['iskonto_orani']))
                stok_doviz = liste_detay['doviz_turu']
                kaynak = f"Fiyat Listesi:  {liste_detay['liste_adi']}"
        
        # 4.ÇAPRAZ KUR HESAPLAMA (TL ÜZERİNDEN)
        tl_karsiligi = baz_fiyat
        
        if stok_doviz != ParaBirimi.TL.value:
            sistem_kuru = Decimal(str(get_doviz_kuru(stok_doviz)))
            if sistem_kuru <= 0:
                logger.warning(f"Sistem kuru alınamadı ({stok_doviz}), 1.0 kullanılıyor")
                sistem_kuru = Decimal('1.0')
            tl_karsiligi = baz_fiyat * sistem_kuru
        
        # Fatura dövizine çevir
        nihai_fiyat = (tl_karsiligi / fatura_kuru).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )
        nihai_fiyat = (tl_karsiligi / fatura_kuru).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )

        # 5.KDV ORANI
        kdv_orani = FiyatHesaplamaService._kdv_orani_hesapla(stok, fatura_turu)
        
        # 6.BİRİM
        birim = FiyatHesaplamaService._birim_getir(stok)
        
        logger.debug(
            f"Fiyat Hesaplama:  Stok={stok.kod}, Baz={baz_fiyat} {stok_doviz}, "
            f"TL={tl_karsiligi}, Fatura={nihai_fiyat} {fatura_para_birimi}, Kaynak={kaynak}"
        )
        
        return {
            'fiyat':  nihai_fiyat,
            'iskonto_orani':  iskonto_orani,
            'kdv_orani': kdv_orani,
            'birim': birim,
            'kaynak': kaynak,
            'debug': {
                'baz_fiyat': float(baz_fiyat),
                'stok_doviz': stok_doviz,
                'tl_karsiligi': float(tl_karsiligi),
                'fatura_kuru': float(fatura_kuru)
            }
        }
    
    @staticmethod
    def _fiyat_listesinden_getir(
        liste_id: int,
        stok_id: int,
        miktar: Optional[Decimal],
        firma_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Fiyat listesinden aktif detayı getirir
        Min Miktar Baremi Destekli
        """
        bugun = date.today()
        
        # Subquery:  Listeyi filtrele
        liste_query = (
            select(FiyatListesi)
            .where(FiyatListesi.id == liste_id)
            .where(FiyatListesi.aktif == True)
            .where(
                or_(
                    FiyatListesi.baslangic_tarihi == None,
                    FiyatListesi.baslangic_tarihi <= bugun
                )
            )
            .where(
                or_(
                    FiyatListesi.bitis_tarihi == None,
                    FiyatListesi.bitis_tarihi >= bugun
                )
            )
        )
        
        liste = db.session.execute(liste_query).scalar_one_or_none()
        
        if not liste:
            return None
        
        # Detay Sorgusu (Miktar Baremi Dahil)
        detay_query = (
            select(FiyatListesiDetay)
            .where(FiyatListesiDetay.fiyat_listesi_id == liste.id)
            .where(FiyatListesiDetay.stok_id == stok_id)
        )
        
        # Miktar varsa min_miktar kontrolü ekle
        if miktar is not None and miktar > 0:
            detay_query = detay_query.where(
                FiyatListesiDetay.min_miktar <= miktar
            ).order_by(FiyatListesiDetay.min_miktar.desc())
        else:
            detay_query = detay_query.where(
                FiyatListesiDetay.min_miktar == 0
            )
        
        detay = db.session.execute(detay_query).scalars().first()
        
        if not detay:
            return None
        
        return {
            'fiyat': detay.fiyat,
            'iskonto_orani': detay.iskonto_orani or 0,
            'doviz_turu': getattr(liste, 'doviz_turu', ParaBirimi.TL.value),
            'liste_adi': liste.ad
        }
    
    @staticmethod
    def _kdv_orani_hesapla(stok: StokKart, fatura_turu: str) -> int:
        """KDV Grubundan oranı hesaplar"""
        varsayilan = int(VARSAYILAN_KDV_ORANI)
        
        if not stok.kdv_grubu:
            return varsayilan
        
        try:
            if fatura_turu in ['alis', 'alis_iade']:
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
                return getattr(stok.birim, 'value', StokBirimleri.ADET.value)
            return StokBirimleri.ADET.value
        except:
            return StokBirimleri.ADET.value


# ============================================================
# 📝 FATURA KALEMI SERVİSİ
# ============================================================
class FaturaKalemService:
    """Fatura Kalemi İşlemleri (UPSERT + Hesaplama)"""
    
    @staticmethod
    def toplu_kaydet(
        fatura_id:  int,
        form_data: Dict[str, Any],
        mevcut_kalemler: Dict[int, FaturaKalemi]
    ) -> Tuple[List[FaturaKalemi], Dict[str, Decimal]]:
        """
        Fatura kalemlerini toplu olarak günceller/ekler
        
        Returns:
            (Kalemler Listesi, Toplamlar Dictionary)
        """
        
        ids = form_data.getlist('kalemler_id[]')
        stok_ids = form_data.getlist('kalemler_stok_id[]')
        miktarlar = form_data.getlist('kalemler_miktar[]')
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
            
            row_id = int(ids[i]) if i < len(ids) and ids[i] and ids[i] != '0' else 0
            
            # UPSERT Mantığı
            if row_id > 0 and row_id in mevcut_kalemler: 
                kalem = mevcut_kalemler[row_id]
                islenen_ids.append(row_id)
            else:
                kalem = FaturaKalemi(fatura_id=fatura_id)
            
            # Veriyi Doldur
            kalem.stok_id = int(stok_ids[i])
            kalem.miktar = para_cevir(miktarlar[i])
            kalem.birim_fiyat = para_cevir(fiyatlar[i])
            kalem.iskonto_orani = para_cevir(iskontolar[i] if i < len(iskontolar) else 0)
            kalem.kdv_orani = para_cevir(kdvs[i] if i < len(kdvs) else 0)
            
            # Hesaplamalar (Decimal ile)
            brut = kalem.miktar * kalem.birim_fiyat
            isk_tutar = (brut * kalem.iskonto_orani / Decimal('100')).quantize(Decimal('0.01'))
            net = brut - isk_tutar
            kdv_tutar = (net * kalem.kdv_orani / Decimal('100')).quantize(Decimal('0.01'))
            satir_top = net + kdv_tutar
            
            kalem.iskonto_tutari = isk_tutar
            kalem.kdv_tutari = kdv_tutar
            kalem.net_tutar = net
            kalem.satir_toplami = satir_top
            
            # Toplamları Akümüle Et
            toplamlar['ara_toplam'] += net
            toplamlar['iskonto_toplam'] += isk_tutar
            toplamlar['kdv_toplam'] += kdv_tutar
            toplamlar['genel_toplam'] += satir_top
            
            kaydedilecek_kalemler.append(kalem)
        
        # Silinecekleri Bul
        silinecekler = [
            k for k_id, k in mevcut_kalemler.items()
            if k_id not in islenen_ids
        ]
        
        # Bulk Delete
        for k in silinecekler: 
            db.session.delete(k)
        
        return kaydedilecek_kalemler, toplamlar


# ============================================================
# 📦 STOK HAREKET SERVİSİ
# ============================================================
class StokHareketService:
    """Stok Hareketi İşlemleri"""
    
    @staticmethod
    def faturadan_olustur(fatura:  Fatura) -> None:
        """Fatura kalemlerinden Stok Hareketleri oluşturur"""
        
        # Eski hareketleri temizle
        db.session.execute(
            delete(StokHareketi).where(
                and_(
                    StokHareketi.firma_id == fatura.firma_id,
                    StokHareketi.kaynak_turu == 'fatura',
                    StokHareketi.kaynak_id == fatura.id
                )
            )
        )
        
        # Yön Tayini
        hareket_yonu = StokHareketService._hareket_yonu_belirle(fatura.fatura_turu)
        
        # Toplu Oluştur
        yeni_hareketler = []
        
        for kalem in fatura.kalemler:
            hareket = StokHareketService._hareket_objesi_olustur(
                fatura, kalem, hareket_yonu
            )
            yeni_hareketler.append(hareket)
        
        # Bulk Insert
        db.session.bulk_save_objects(yeni_hareketler)
        
        logger.info(
            f"Stok Hareketi:  {len(yeni_hareketler)} kayıt oluşturuldu "
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
            return HareketTuru.SATIS.value
        elif not is_satis and not is_iade:
            return HareketTuru.ALIS.value
        elif is_satis and is_iade:
            return HareketTuru.SATIS_IADE.value
        else:
            return HareketTuru.ALIS_IADE.value
    
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
        if hareket_yonu in [HareketTuru.ALIS.value, HareketTuru.SATIS_IADE.value]:
            sh.giris_depo_id = fatura.depo_id
            sh.cikis_depo_id = None
        else:
            sh.giris_depo_id = None
            sh.cikis_depo_id = fatura.depo_id
        
        sh.stok_id = kalem.stok_id
        sh.tarih = fatura.tarih
        sh.belge_no = fatura.belge_no
        sh.kaynak_turu = 'fatura'
        sh.kaynak_id = fatura.id
        sh.kaynak_belge_detay_id = kalem.id
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
    def faturadan_olustur(fatura:  Fatura) -> None:
        """Faturadan Cari Hareket oluşturur"""
        
        # Eski hareketi temizle
        db.session.execute(
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
        db.session.add(ch)
        
        bakiye = ch.borc - ch.alacak
        logger.info(
            f"Cari Hareket: {fatura.cari.unvan} "
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
        ch.kaynak_id = fatura.id
        
        # İşlem Türü Tayini
        fatura_turu_str = fatura.fatura_turu.value if hasattr(fatura.fatura_turu, 'value') else str(fatura.fatura_turu)
        is_satis = ('SATIS' in fatura_turu_str.upper())
        is_iade = ('IADE' in fatura_turu_str.upper())
        
        if is_satis and not is_iade:
            ch.islem_turu = CariIslemTuru.SATIS_FATURASI.value
        elif not is_satis and not is_iade:
            ch.islem_turu = CariIslemTuru.ALIS_FATURASI.value
        elif is_satis and is_iade:
            ch.islem_turu = CariIslemTuru.SATIS_IADE.value
        else:
            ch.islem_turu = CariIslemTuru.ALIS_IADE.value
        
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
    def entegre_et_fatura(fatura_id: int) -> Tuple[bool, str]:
        """
        Faturayı Muhasebe Modülüne entegre eder
        
        Returns: 
            (Başarı durumu, Mesaj)
        """
        
        try:
            # Lazy Import (Circular Import'u Önler)
            from modules.muhasebe.services import MuhasebeService
            
            fatura = db.session.get(Fatura, fatura_id)
            if not fatura:
                return False, "Fatura bulunamadı"
            
            # Muhasebe Fişi Oluştur
            fis = MuhasebeService.faturadan_fis_olustur(fatura)
            
            # Faturaya Bağla
            fatura.muhasebe_fis_id = fis.id
            db.session.flush()
            
            logger.info(
                f"Muhasebe Fişi: {fis.fis_no} oluşturuldu "
                f"(Fatura: {fatura.belge_no})"
            )
            return True, f"Muhasebe Fişi:  {fis.fis_no}"
            
        except ImportError as e:
            logger.warning(
                f"Muhasebe Modülü yüklenmedi (Circular Import olabilir): {e}"
            )
            return False, "Muhasebe modülü bulunamadı"
        
        except Exception as e:
            logger.error(f"Muhasebe Entegrasyon Hatası: {e}", exc_info=True)
            return False, str(e)


# ============================================================
# 🎯 ANA FATURA SERVİSİ (FACADE PATTERN)
# ============================================================
class FaturaService:
    """Ana Fatura Servis Katmanı"""
    
    @staticmethod
    def save(
        form_data: Dict[str, Any],
        fatura:  Optional[Fatura] = None,
        user:  Any = None
    ) -> Tuple[bool, str]:
        """
        Fatura oluşturur veya günceller
        
        Args:
            form_data: Form verisi (ImmutableMultiDict)
            fatura: Güncelleme için mevcut Fatura instance'ı
            user: Mevcut kullanıcı (current_user)
            
        Returns:
            (Başarı durumu, Mesaj)
        """
        
        try:
            is_new = fatura is None
            
            # 1.BAŞLIK OLUŞTUR/GÜNCELLE
            if is_new:
                fatura = Fatura(firma_id=user.firma_id)
                FaturaService._yeni_fatura_baslat(fatura, user)
            
            FaturaService._baslik_doldur(fatura, form_data)
            
            db.session.add(fatura)
            db.session.flush()
            
            # 2.KALEMLERI İŞLE (UPSERT)
            mevcut_kalemler = {k.id: k for k in fatura.kalemler}
            
            kaydedilecek_kalemler, toplamlar = FaturaKalemService.toplu_kaydet(
                fatura.id, form_data, mevcut_kalemler
            )
            
            # Bulk Save
            db.session.bulk_save_objects(kaydedilecek_kalemler)
            
            # 3.TOPLAM GÜNCELLEMESİ
            fatura.ara_toplam = toplamlar['ara_toplam']
            fatura.iskonto_toplam = toplamlar['iskonto_toplam']
            fatura.kdv_toplam = toplamlar['kdv_toplam']
            fatura.genel_toplam = toplamlar['genel_toplam']
            
            if fatura.doviz_kuru > 0:
                fatura.dovizli_toplam = (
                    fatura.genel_toplam / fatura.doviz_kuru
                ).quantize(Decimal('0.01'))
            
            # 4.ONAY DURUMU
            fatura.durum = FaturaDurumu.ONAYLANDI.value
            
            db.session.flush()
            
            # 5.ENTEGRASYONLARı ÇALIŞTIR
            FaturaService.faturayi_isleme_al(fatura)
            
            # 6.COMMIT
            db.session.commit()
            # n8n'i tetikle (WhatsApp mesajı gitmesi için)
            N8NClient.trigger('fatura-onaylandi', {
                'fatura_id': fatura.id,
                'belge_no': fatura.belge_no,
                'cari': fatura.cari.unvan,
                'tutar': float(fatura.genel_toplam),
                'tarih': fatura.tarih.strftime('%Y-%m-%d'),
                'telefon': fatura.cari.telefon  # WhatsApp için
            })

            logger.info(
                f"Fatura Kaydedildi: {fatura.belge_no} "
                f"({'Yeni' if is_new else 'Güncelleme'}) - "
                f"Toplam: {fatura.genel_toplam} TL"
            )
            
            return True, f"Fatura {fatura.belge_no} başarıyla kaydedildi."
        
        except FaturaValidationError as e:
            db.session.rollback()
            logger.warning(f"Validasyon Hatası: {e}")
            return False, str(e)
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Fatura Kaydetme Hatası: {e}", exc_info=True)
            return False, f"Beklenmeyen hata: {str(e)}"
    
    @staticmethod
    def _yeni_fatura_baslat(fatura: Fatura, user:  Any) -> None:
        """Yeni fatura için başlangıç değerlerini atar"""
        
        # Şube Tayini
        if user.yetkili_subeler:
            fatura.sube_id = user.yetkili_subeler[0].id
        else:
            raise FaturaValidationError("Kullanıcının yetkili şubesi yok")
        
        # Dönem Tayini
        if 'aktif_donem_id' in session:
            fatura.donem_id = session['aktif_donem_id']
        else:
            aktif_donem = db.session.execute(
                select(Donem)
                .where(Donem.firma_id == user.firma_id)
                .where(Donem.aktif == True)
            ).scalar_one_or_none()
            
            if aktif_donem:
                fatura.donem_id = aktif_donem.id
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
        fatura.cari_id = int(form_data.get('cari_id'))
        fatura.depo_id = int(form_data.get('depo_id'))
        fatura.fatura_turu = form_data.get('fatura_turu')
        fatura.aciklama = form_data.get('aciklama')
        fatura.sevk_adresi = form_data.get('sevk_adresi')
        
        # Fiyat Listesi
        fl_id = form_data.get('fiyat_listesi_id')
        if fl_id and int(fl_id) >= MIN_FIYAT_LISTESI_ID:
            fatura.fiyat_listesi_id = int(fl_id)
        else:
            fatura.fiyat_listesi_id = None
        
        # Döviz
        fatura.doviz_turu = form_data.get('doviz_turu', ParaBirimi.TL.value)
        fatura.doviz_kuru = para_cevir(form_data.get('doviz_kuru', 1))
        
        # Ödeme Planı
        odeme_plani_id = form_data.get('odeme_plani_id')
        if odeme_plani_id:
            fatura.odeme_plani_id = int(odeme_plani_id)
    
    @staticmethod
    def faturayi_isleme_al(fatura: Fatura) -> None:
        """
        Faturayı Stok, Cari ve Muhasebe modüllerine entegre eder
        
        Not: Bu method Transaction içinde çağrılmalıdır! 
        """
        
        # 1.Stok Hareketleri
        StokHareketService.faturadan_olustur(fatura)
        
        # 2.Cari Hareket
        CariHareketService.faturadan_olustur(fatura)
        
        # 3.Muhasebe Entegrasyonu (Opsiyonel)
        basari, mesaj = MuhasebeEntegrasyonService.entegre_et_fatura(fatura.id)
        if not basari:
            logger.warning(f"Muhasebe entegrasyonu atlandı: {mesaj}")
    
    @staticmethod
    def sil(fatura_id: int, user: Any) -> Tuple[bool, str]:
        """
        Faturayı ve ilişkili tüm kayıtları siler
        
        Args:
            fatura_id: Silinecek fatura ID
            user: Mevcut kullanıcı
            
        Returns:
            (Başarı durumu, Mesaj)
        """
        
        try:
            fatura = db.session.get(Fatura, fatura_id)
            
            if not fatura:
                return False, "Fatura bulunamadı"
            
            if fatura.firma_id != user.firma_id:
                return False, "Yetkisiz erişim"
            
            # Onaylı Fatura Kontrolü
            durum_str = fatura.durum.value if hasattr(fatura.durum, 'value') else str(fatura.durum)
            if durum_str == FaturaDurumu.ONAYLANDI.value:
                logger.warning(
                    f"Onaylı Fatura Silme Denemesi: {fatura.belge_no} "
                    f"(Kullanıcı: {user.username})"
                )
                return False, "Onaylı fatura silinemez.Önce iptal edin."
            
            # İlişkili Kayıtları Temizle
            db.session.execute(
                delete(StokHareketi).where(
                    and_(
                        StokHareketi.firma_id == fatura.firma_id,
                        StokHareketi.kaynak_turu == 'fatura',
                        StokHareketi.kaynak_id == fatura.id
                    )
                )
            )
            
            db.session.execute(
                delete(CariHareket).where(
                    and_(
                        CariHareket.firma_id == fatura.firma_id,
                        CariHareket.kaynak_turu == 'fatura',
                        CariHareket.kaynak_id == fatura.id
                    )
                )
            )
            
            # Muhasebe Fişini Sil (Eğer varsa)
            # Not: MuhasebeFisi importunu buraya taşıdık
            try:
                from models import MuhasebeFisi
                if fatura.muhasebe_fis_id:
                    db.session.execute(
                        delete(MuhasebeFisi).where(
                            MuhasebeFisi.id == fatura.muhasebe_fis_id
                        )
                    )
            except ImportError:
                pass
            
            # Faturayı Sil (Cascade ile kalemler de silinir)
            db.session.delete(fatura)
            db.session.commit()
            
            logger.info(
                f"Fatura Silindi: {fatura.belge_no} "
                f"(Kullanıcı: {user.username})"
            )
            return True, "Fatura başarıyla silindi."
        
        except Exception as e: 
            db.session.rollback()
            logger.error(f"Fatura Silme Hatası: {e}", exc_info=True)
            return False, f"Silme işlemi başarısız: {str(e)}"
    
    @staticmethod
    def get_by_id(fatura_id:  int, firma_id: int) -> Optional[Fatura]: 
        """
        ID'ye göre fatura getirir (Eager Loading ile)
        
        🔥 FIX: SQLAlchemy 1.4+ Syntax
        
        Args:
            fatura_id: Fatura ID
            firma_id: Firma ID (Güvenlik kontrolü için)
            
        Returns: 
            Fatura instance'ı veya None
        """

        try: 
            stmt = (
                select(Fatura)
                .options(
                    selectinload(Fatura.kalemler).joinedload(FaturaKalemi.stok),
                    joinedload(Fatura.cari),
                    joinedload(Fatura.depo),
                )
                .where(Fatura.id == fatura_id)
                .where(Fatura.firma_id == firma_id)
            )

            # Parametreli hali:
            #print(stmt)

            #print("Fatura İd : ", fatura_id, "Firma İd : ", firma_id)
            # 🔥 DÜZELTME: execute() + scalar_one_or_none() kullanımı
            fatura = db.session.execute(
                select(Fatura)
                .options(
                    # Collection için selectinload (Ayrı sorgu, daha hızlı)
                    selectinload(Fatura.kalemler).joinedload(FaturaKalemi.stok),
                    
                    # Tekil ilişkiler için joinedload (Tek sorgu)
                    joinedload(Fatura.cari),
                    joinedload(Fatura.depo)
                )
                .where(Fatura.id == fatura_id)
                .where(Fatura.firma_id == firma_id)
            ).scalar_one_or_none()  # ✅ Bu satır hatayı çözüyor
            #print(fatura.kalemler[0])
            return fatura
            
        except Exception as e: 
            logger.error(
                f"Fatura getirme hatası (ID: {fatura_id}): {e}",
                exc_info=True
            )
            return None