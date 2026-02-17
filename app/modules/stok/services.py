# app/modules/stok/services.py (MySQL + AI + Redis + Babel)

"""
Stok Modülü Servis Katmanı
Enterprise Grade - AI Enhanced - Redis Cached - i18n Ready
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
import logging

from sqlalchemy import select, and_, or_, delete, func, text
from sqlalchemy.orm import joinedload, selectinload
from flask import session
from flask_login import current_user
from flask_babel import gettext as _, lazy_gettext

from app.extensions import db, cache, get_tenant_db
from app.modules.stok.models import (
    StokKart, StokHareketi, StokDepoDurumu,
    StokMuhasebeGrubu, StokKDVGrubu, StokPaketIcerigi
)
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.depo.models import Depo
from app.enums import FaturaTuru, HareketTuru

# Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants
CACHE_TIMEOUT_SHORT = 300  # 5 dakika
CACHE_TIMEOUT_MEDIUM = 1800  # 30 dakika
CACHE_TIMEOUT_LONG = 3600  # 1 saat


# ============================================================
# 🔥 CUSTOM EXCEPTIONS
# ============================================================
class StokValidationError(Exception):
    """Stok Validation Hatası"""
    pass


class StokNotFoundError(Exception):
    """Stok Bulunamadı Hatası"""
    pass


class StokYetersizError(Exception):
    """Yetersiz Stok Hatası"""
    pass


# ============================================================
# 📦 STOK KART SERVİSİ
# ============================================================
class StokKartService:
    """
    Stok Kartı İşlemleri
    
    Özellikler:
    - Redis cache kullanımı
    - AI analiz entegrasyonu
    - Babel i18n desteği
    """
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_MEDIUM)
    def get_by_id(stok_id: str, firma_id: str, tenant_db=None) -> Optional[StokKart]:
        """
        ID'ye göre stok getir (Cached + Eager Loading)
        
        Args:
            stok_id: Stok ID (UUID)
            firma_id: Firma ID (UUID)
            tenant_db: Tenant DB session
        
        Returns:
            StokKart instance veya None
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            stok = tenant_db.query(StokKart).options(
                joinedload(StokKart.kategori),
                joinedload(StokKart.muhasebe_grubu),
                joinedload(StokKart.kdv_grubu),
                joinedload(StokKart.tedarikci),
                selectinload(StokKart.depo_durumlari)
            ).filter(
                StokKart.id == stok_id,
                StokKart.firma_id == firma_id,
                StokKart.deleted_at.is_(None)
            ).first()
            
            return stok
        
        except Exception as e:
            logger.error(f"❌ Stok getirme hatası (ID: {stok_id}): {e}")
            return None
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_LONG)
    def get_by_kod(stok_kodu: str, firma_id: str, tenant_db=None) -> Optional[StokKart]:
        """
        Kod'a göre stok getir (Cached)
        
        Args:
            stok_kodu: Stok kodu
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            StokKart instance veya None
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            stok = tenant_db.query(StokKart).filter(
                StokKart.kod == stok_kodu,
                StokKart.firma_id == firma_id,
                StokKart.deleted_at.is_(None)
            ).first()
            
            return stok
        
        except Exception as e:
            logger.error(f"❌ Stok getirme hatası (Kod: {stok_kodu}): {e}")
            return None
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_SHORT)
    def get_toplam_stok(stok_id: str, firma_id: str, tenant_db=None) -> Decimal:
        """
        Tüm depolardaki toplam stok miktarı (Cached)
        
        Args:
            stok_id: Stok ID
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            Toplam miktar
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # ✅ MySQL Aggregate Query (tek sorgu)
            toplam = tenant_db.execute(text("""
                SELECT COALESCE(SUM(miktar), 0)
                FROM stok_depo_durumu
                WHERE stok_id = :stok_id
                AND firma_id = :firma_id
            """), {
                'stok_id': stok_id,
                'firma_id': firma_id
            }).scalar()
            
            return Decimal(str(toplam))
        
        except Exception as e:
            logger.error(f"❌ Toplam stok hesaplama hatası: {e}")
            return Decimal('0.000000')
    
    @staticmethod
    def save(form_data: Dict[str, Any], stok: Optional[StokKart] = None, tenant_db=None) -> Tuple[bool, str]:
        """
        Stok kartı kaydet/güncelle
        
        Args:
            form_data: Form verisi
            stok: Mevcut StokKart instance (güncelleme için)
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            is_new = (stok is None)
            
            if is_new:
                stok = StokKart()
                stok.firma_id = current_user.firma_id
            
            # Form verilerini doldur
            StokKartService._form_to_model(stok, form_data)
            
            tenant_db.add(stok)
            tenant_db.flush()
            
            # AI analizlerini güncelle
            stok.ai_analiz_guncelle()
            
            tenant_db.commit()
            
            # Cache'i temizle
            StokKartService._invalidate_cache(stok.id, stok.firma_id)
            
            mesaj = _("Yeni stok kartı oluşturuldu") if is_new else _("Stok kartı güncellendi")
            logger.info(f"✅ Stok kaydedildi: {stok.kod} - {stok.ad}")
            
            return True, f"{mesaj}: {stok.kod}"
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Stok kaydetme hatası: {e}", exc_info=True)
            return False, _("Kaydetme başarısız: %(error)s", error=str(e))
    
    @staticmethod
    def _form_to_model(stok: StokKart, form_data: Dict[str, Any]):
        """Form verisini model'e doldur"""
        from app.araclar import para_cevir
        
        stok.kod = form_data.get('kod', '').strip().upper()
        stok.ad = form_data.get('ad', '').strip()
        stok.barkod = form_data.get('barkod', '').strip() or None
        stok.uretici_kodu = form_data.get('uretici_kodu', '').strip() or None
        
        stok.birim = form_data.get('birim', 'ADET')
        stok.tip = form_data.get('tip', 'STANDART')
        
        kategori_id = form_data.get('kategori_id')
        stok.kategori_id = kategori_id if kategori_id else None
        
        stok.alis_fiyati = para_cevir(form_data.get('alis_fiyati', 0))
        stok.satis_fiyati = para_cevir(form_data.get('satis_fiyati', 0))
        stok.doviz_turu = form_data.get('doviz_turu', 'TL')
        
        muhasebe_kod_id = form_data.get('muhasebe_kod_id')
        stok.muhasebe_kod_id = muhasebe_kod_id if muhasebe_kod_id else None
        
        kdv_kod_id = form_data.get('kdv_kod_id')
        stok.kdv_kod_id = kdv_kod_id if kdv_kod_id else None
        
        stok.kritik_seviye = para_cevir(form_data.get('kritik_seviye', 0))
        stok.tedarik_suresi_gun = int(form_data.get('tedarik_suresi_gun', 3))
        stok.raf_omru_gun = int(form_data.get('raf_omru_gun', 0))
        stok.garanti_suresi_ay = int(form_data.get('garanti_suresi_ay', 24))
        stok.agirlik_kg = para_cevir(form_data.get('agirlik_kg', 0))
        stok.desi = para_cevir(form_data.get('desi', 0))
        
        tedarikci_id = form_data.get('tedarikci_id')
        stok.tedarikci_id = tedarikci_id if tedarikci_id else None
        
        stok.mevsimsel_grup = form_data.get('mevsimsel_grup', '')
        
        stok.marka = form_data.get('marka', '').strip() or None
        stok.model = form_data.get('model', '').strip() or None
        stok.mensei = form_data.get('mensei', 'Türkiye')
        
        stok.anahtar_kelimeler = form_data.get('anahtar_kelimeler', '').strip() or None
        stok.aciklama_detay = form_data.get('aciklama_detay', '').strip() or None
        stok.ozel_kod1 = form_data.get('ozel_kod1', '').strip() or None
        stok.ozel_kod2 = form_data.get('ozel_kod2', '').strip() or None
        
        # Aktif durumu
        aktif_raw = form_data.get('aktif')
        stok.aktif = str(aktif_raw).lower() in ['true', '1', 'on', 'yes']
    
    @staticmethod
    def _invalidate_cache(stok_id: str, firma_id: str):
        """Stok ile ilgili cache'leri temizle"""
        try:
            # ID bazlı cache
            cache.delete_memoized(StokKartService.get_by_id, stok_id, firma_id)
            
            # Toplam stok cache
            cache.delete_memoized(StokKartService.get_toplam_stok, stok_id, firma_id)
            
            logger.debug(f"🗑️ Stok cache temizlendi: {stok_id}")
        
        except Exception as e:
            logger.warning(f"⚠️ Cache temizleme hatası: {e}")
    
    @staticmethod
    def sil(stok_id: str, firma_id: str, tenant_db=None) -> Tuple[bool, str]:
        """
        Stok kartını sil (Soft Delete)
        
        Args:
            stok_id: Stok ID
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            stok = tenant_db.query(StokKart).filter_by(
                id=stok_id,
                firma_id=firma_id
            ).first()
            
            if not stok:
                return False, _("Stok bulunamadı")
            
            # Hareket kontrolü
            hareket_sayisi = tenant_db.query(func.count(StokHareketi.id)).filter(
                StokHareketi.stok_id == stok_id
            ).scalar()
            
            if hareket_sayisi > 0:
                return False, _(
                    "Bu stokun %(count)d adet hareketi var. Önce hareketleri temizleyin.",
                    count=hareket_sayisi
                )
            
            # Soft Delete
            stok.deleted_at = datetime.now()
            stok.deleted_by = str(current_user.id)
            
            tenant_db.commit()
            
            # Cache'i temizle
            StokKartService._invalidate_cache(stok_id, firma_id)
            
            logger.info(f"✅ Stok silindi (soft): {stok.kod}")
            return True, _("Stok kartı başarıyla silindi")
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Stok silme hatası: {e}")
            return False, _("Silme işlemi başarısız: %(error)s", error=str(e))


# ============================================================
# 📊 STOK HAREKET SERVİSİ
# ============================================================
class StokHareketService:
    """
    Stok Hareketi İşlemleri
    
    Özellikler:
    - Otomatik depo durumu güncelleme
    - Kaynak belge izlenebilirliği
    - Redis cache invalidation
    """
    
    @staticmethod
    def hareket_ekle(
        stok_id: str,
        hareket_turu: str,
        miktar: Decimal,
        birim_fiyat: Decimal,
        tarih: date,
        belge_no: str,
        giris_depo_id: Optional[str] = None,
        cikis_depo_id: Optional[str] = None,
        kaynak_turu: Optional[str] = None,
        kaynak_id: Optional[str] = None,
        aciklama: Optional[str] = None,
        tenant_db=None
    ) -> Tuple[bool, str]:
        """
        Stok hareketi ekle
        
        Args:
            stok_id: Stok ID
            hareket_turu: Hareket türü (HareketTuru enum)
            miktar: Miktar
            birim_fiyat: Birim fiyat
            tarih: Hareket tarihi
            belge_no: Belge numarası
            giris_depo_id: Giriş depo ID (opsiyonel)
            cikis_depo_id: Çıkış depo ID (opsiyonel)
            kaynak_turu: Kaynak türü (fatura, siparis, vb.)
            kaynak_id: Kaynak ID
            aciklama: Açıklama
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # Validasyon
            if not giris_depo_id and not cikis_depo_id:
                raise StokValidationError(_("En az bir depo belirtilmelidir"))
            
            if miktar <= 0:
                raise StokValidationError(_("Miktar sıfırdan büyük olmalıdır"))
            
            # Hareket oluştur
            hareket = StokHareketi(
                firma_id=current_user.firma_id,
                donem_id=session.get('aktif_donem_id'),
                sube_id=session.get('aktif_sube_id'),
                kullanici_id=str(current_user.id),
                
                stok_id=stok_id,
                giris_depo_id=giris_depo_id,
                cikis_depo_id=cikis_depo_id,
                
                tarih=tarih,
                belge_no=belge_no,
                hareket_turu=hareket_turu,
                aciklama=aciklama,
                
                miktar=miktar,
                birim_fiyat=birim_fiyat,
                
                kaynak_turu=kaynak_turu,
                kaynak_id=kaynak_id
            )
            
            tenant_db.add(hareket)
            tenant_db.flush()
            
            # Depo durumu otomatik güncellenecek (event listener)
            
            tenant_db.commit()
            
            # Cache'i temizle
            cache.delete_memoized(
                StokKartService.get_toplam_stok,
                stok_id,
                current_user.firma_id
            )
            
            logger.info(
                f"✅ Stok hareketi eklendi: {belge_no} "
                f"Stok:{stok_id} Miktar:{miktar}"
            )
            
            return True, _("Stok hareketi başarıyla eklendi")
        
        except StokValidationError as e:
            tenant_db.rollback()
            return False, str(e)
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Stok hareketi ekleme hatası: {e}", exc_info=True)
            return False, _("Hareket eklenemedi: %(error)s", error=str(e))
    
    @staticmethod
    def faturadan_hareket_olustur(fatura_id: str, tenant_db=None) -> Tuple[bool, str]:
        """
        Faturadan stok hareketleri oluştur
        
        Args:
            fatura_id: Fatura ID
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # Faturayı çek
            fatura = tenant_db.query(Fatura).options(
                selectinload(Fatura.kalemler)
            ).filter_by(id=fatura_id).first()
            
            if not fatura:
                return False, _("Fatura bulunamadı")
            
            # Daha önce hareket oluşmuş mu?
            mevcut = tenant_db.query(StokHareketi).filter(
                StokHareketi.kaynak_turu == 'fatura',
                StokHareketi.kaynak_id == fatura_id
            ).first()
            
            if mevcut:
                # Eski hareketleri sil
                tenant_db.query(StokHareketi).filter(
                    StokHareketi.kaynak_turu == 'fatura',
                    StokHareketi.kaynak_id == fatura_id
                ).delete()
                tenant_db.flush()
            
            # Hareket türünü belirle
            if fatura.fatura_turu == 'SATIS':
                hareket_turu = 'SATIS'
                giris_depo_id = None
                cikis_depo_id = str(fatura.depo_id)
            elif fatura.fatura_turu == 'ALIS':
                hareket_turu = 'ALIS'
                giris_depo_id = str(fatura.depo_id)
                cikis_depo_id = None
            elif fatura.fatura_turu == 'SATIS_IADE':
                hareket_turu = 'SATIS_IADE'
                giris_depo_id = str(fatura.depo_id)
                cikis_depo_id = None
            elif fatura.fatura_turu == 'ALIS_IADE':
                hareket_turu = 'ALIS_IADE'
                giris_depo_id = None
                cikis_depo_id = str(fatura.depo_id)
            else:
                return True, _("Hizmet faturası, stok hareketi oluşturulmadı")
            
            # Kalemleri işle
            hareket_sayisi = 0
            
            for kalem in fatura.kalemler:
                # Hizmet stoklarını atla
                stok = tenant_db.query(StokKart).get(kalem.stok_id)
                
                if stok and stok.tip == 'HIZMET':
                    continue
                
                hareket = StokHareketi(
                    firma_id=fatura.firma_id,
                    donem_id=fatura.donem_id,
                    sube_id=fatura.sube_id,
                    kullanici_id=str(current_user.id) if current_user.is_authenticated else None,
                    
                    stok_id=str(kalem.stok_id),
                    giris_depo_id=giris_depo_id,
                    cikis_depo_id=cikis_depo_id,
                    
                    tarih=fatura.tarih,
                    belge_no=fatura.belge_no,
                    hareket_turu=hareket_turu,
                    
                    miktar=kalem.miktar,
                    birim_fiyat=kalem.birim_fiyat,
                    
                    iskonto_orani=kalem.iskonto_orani,
                    iskonto_tutar=kalem.iskonto_tutari,
                    kdv_orani=kalem.kdv_orani,
                    kdv_tutar=kalem.kdv_tutari,
                    net_tutar=kalem.net_tutar,
                    toplam_tutar=kalem.satir_toplami,
                    
                    doviz_turu=fatura.doviz_turu,
                    doviz_kuru=fatura.doviz_kuru,
                    
                    kaynak_turu='fatura',
                    kaynak_id=str(fatura.id),
                    kaynak_belge_detay_id=str(kalem.id),
                    
                    aciklama=f"{fatura.belge_no} nolu fatura hareketi"
                )
                
                tenant_db.add(hareket)
                hareket_sayisi += 1
            
            tenant_db.commit()
            
            logger.info(
                f"✅ Fatura stok hareketleri oluşturuldu: "
                f"{fatura.belge_no} ({hareket_sayisi} adet)"
            )
            
            return True, _(
                "%(count)d adet stok hareketi oluşturuldu",
                count=hareket_sayisi
            )
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Fatura stok hareketi oluşturma hatası: {e}", exc_info=True)
            return False, _("Stok hareketi oluşturulamadı: %(error)s", error=str(e))


# ============================================================
# 🤖 AI ANALİZ SERVİSİ (Redis Cached)
# ============================================================
class StokAIService:
    """
    AI Analiz İşlemleri
    
    Özellikler:
    - Ölü stok analizi
    - Çapraz satış analizi
    - Talep tahmini
    - Redis cache kullanımı
    """
    
    @staticmethod
    @cache.cached(timeout=CACHE_TIMEOUT_LONG, key_prefix='olu_stok_analiz')
    def olu_stok_analizi(firma_id: str, tenant_db=None) -> Dict[str, Any]:
        """
        Ölü stok analizi (Cached)
        
        Args:
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            {
                'toplam_deger': Decimal,
                'urun_sayisi': int,
                'urunler': List[Dict]
            }
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # Son 6 ay
            alti_ay_once = date.today() - timedelta(days=180)
            
            # ✅ MySQL Optimized Query
            results = tenant_db.execute(text("""
                SELECT 
                    sk.id,
                    sk.kod,
                    sk.ad,
                    COALESCE(SUM(sdd.miktar), 0) as toplam_stok,
                    sk.alis_fiyati,
                    COALESCE(SUM(fk.miktar), 0) as son_6_ay_satis
                FROM stok_kartlari sk
                LEFT JOIN stok_depo_durumu sdd ON sdd.stok_id = sk.id
                LEFT JOIN fatura_kalemleri fk ON fk.stok_id = sk.id
                LEFT JOIN faturalar f ON f.id = fk.fatura_id
                    AND f.fatura_turu = 'SATIS'
                    AND f.tarih >= :baslangic_tarih
                WHERE sk.firma_id = :firma_id
                AND sk.deleted_at IS NULL
                AND sk.aktif = 1
                GROUP BY sk.id, sk.kod, sk.ad, sk.alis_fiyati
                HAVING toplam_stok > 0
                AND (son_6_ay_satis = 0 OR toplam_stok > (son_6_ay_satis * 3))
                ORDER BY (toplam_stok * sk.alis_fiyati) DESC
                LIMIT 50
            """), {
                'firma_id': firma_id,
                'baslangic_tarih': alti_ay_once
            }).fetchall()
            
            urunler = []
            toplam_deger = Decimal('0.00')
            
            for row in results:
                stok_deger = row.toplam_stok * row.alis_fiyati
                toplam_deger += stok_deger
                
                urunler.append({
                    'id': str(row.id),
                    'kod': row.kod,
                    'ad': row.ad,
                    'toplam_stok': float(row.toplam_stok),
                    'alis_fiyati': float(row.alis_fiyati),
                    'stok_degeri': float(stok_deger),
                    'son_6_ay_satis': float(row.son_6_ay_satis)
                })
            
            logger.info(
                f"📊 Ölü stok analizi: {len(urunler)} ürün, "
                f"Toplam: {toplam_deger} TL"
            )
            
            return {
                'toplam_deger': float(toplam_deger),
                'urun_sayisi': len(urunler),
                'urunler': urunler
            }
        
        except Exception as e:
            logger.error(f"❌ Ölü stok analizi hatası: {e}")
            return {
                'toplam_deger': 0.0,
                'urun_sayisi': 0,
                'urunler': []
            }
    
    @staticmethod
    @cache.cached(timeout=CACHE_TIMEOUT_LONG, key_prefix='talep_tahmini')
    def talep_tahmini(stok_id: str, firma_id: str, tenant_db=None) -> Dict[str, Any]:
        """
        AI talep tahmini (Cached)
        
        Args:
            stok_id: Stok ID
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            {
                'tahmin_miktar': Decimal,
                'guven_araligi': Decimal,
                'trend': str,
                'onerilir_siparis': Decimal
            }
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # Son 12 aylık satış verisi
            on_iki_ay_once = date.today() - timedelta(days=365)
            
            # ✅ MySQL Aggregate
            aylik_satis = tenant_db.execute(text("""
                SELECT 
                    DATE_FORMAT(f.tarih, '%Y-%m') as ay,
                    SUM(fk.miktar) as toplam_miktar
                FROM fatura_kalemleri fk
                INNER JOIN faturalar f ON f.id = fk.fatura_id
                WHERE fk.stok_id = :stok_id
                AND f.firma_id = :firma_id
                AND f.fatura_turu = 'SATIS'
                AND f.tarih >= :baslangic_tarih
                GROUP BY ay
                ORDER BY ay
            """), {
                'stok_id': stok_id,
                'firma_id': firma_id,
                'baslangic_tarih': on_iki_ay_once
            }).fetchall()
            
            if not aylik_satis or len(aylik_satis) < 3:
                return {
                    'tahmin_miktar': 0.0,
                    'guven_araligi': 0.0,
                    'trend': 'belirsiz',
                    'onerilir_siparis': 0.0
                }
            
            # Basit hareketli ortalama
            miktarlar = [float(row.toplam_miktar) for row in aylik_satis]
            ortalama = sum(miktarlar) / len(miktarlar)
            
            # Trend tespiti
            son_3_ay = miktarlar[-3:]
            ilk_3_ay = miktarlar[:3]
            
            if len(son_3_ay) == 3 and len(ilk_3_ay) == 3:
                son_ort = sum(son_3_ay) / 3
                ilk_ort = sum(ilk_3_ay) / 3
                
                if son_ort > ilk_ort * 1.2:
                    trend = 'yukselis'
                    carpan = 1.3
                elif son_ort < ilk_ort * 0.8:
                    trend = 'dusus'
                    carpan = 0.8
                else:
                    trend = 'sabit'
                    carpan = 1.0
            else:
                trend = 'belirsiz'
                carpan = 1.0
            
            tahmin = ortalama * carpan
            guven = ortalama * 0.2  # %20 güven aralığı
            
            # Önerilen sipariş (stok + tedarik süresi)
            stok = tenant_db.query(StokKart).get(stok_id)
            tedarik_suresi = stok.tedarik_suresi_gun if stok else 7
            
            onerilir_siparis = tahmin * (tedarik_suresi / 30)
            
            return {
                'tahmin_miktar': float(tahmin),
                'guven_araligi': float(guven),
                'trend': trend,
                'onerilir_siparis': float(onerilir_siparis)
            }
        
        except Exception as e:
            logger.error(f"❌ Talep tahmini hatası: {e}")
            return {
                'tahmin_miktar': 0.0,
                'guven_araligi': 0.0,
                'trend': 'hata',
                'onerilir_siparis': 0.0
            }


# ============================================================
# 📦 PAKET ÜRÜN SERVİSİ
# ============================================================
class PaketUrunService:
    """Paket Ürün İşlemleri"""
    
    @staticmethod
    def icerik_kaydet(
        paket_stok_id: str,
        icerik_listesi: List[Dict[str, Any]],
        tenant_db=None
    ) -> Tuple[bool, str]:
        """
        Paket içeriğini kaydet
        
        Args:
            paket_stok_id: Ana ürün ID
            icerik_listesi: [{'alt_stok_id': '...', 'miktar': 2.5}, ...]
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # Eski içeriği temizle
            tenant_db.query(StokPaketIcerigi).filter_by(
                paket_stok_id=paket_stok_id
            ).delete()
            
            # Yeni içeriği ekle
            for i, item in enumerate(icerik_listesi, 1):
                alt_stok_id = item.get('alt_stok_id')
                miktar = Decimal(str(item.get('miktar', 1)))
                
                if not alt_stok_id or miktar <= 0:
                    continue
                
                icerik = StokPaketIcerigi(
                    paket_stok_id=paket_stok_id,
                    alt_stok_id=alt_stok_id,
                    miktar=miktar,
                    sira_no=i
                )
                
                tenant_db.add(icerik)
            
            # Ana ürünün tipini güncelle
            stok = tenant_db.query(StokKart).get(paket_stok_id)
            if stok and stok.tip == 'STANDART':
                stok.tip = 'PAKET'
            
            tenant_db.commit()
            
            logger.info(
                f"✅ Paket içeriği kaydedildi: {paket_stok_id} "
                f"({len(icerik_listesi)} bileşen)"
            )
            
            return True, _("Paket içeriği başarıyla güncellendi")
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Paket içerik kaydetme hatası: {e}")
            return False, _("Kaydetme başarısız: %(error)s", error=str(e))