# app/modules/cari/services.py (Redis + Babel Enhanced)

"""
Cari Modülü Servis Katmanı
Enterprise Grade - Redis Cached - i18n Ready
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
import logging

from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import joinedload, selectinload
from flask import session
from flask_login import current_user
from flask_babel import gettext as _, lazy_gettext

from app.extensions import db, cache, get_tenant_db
from app.modules.cari.models import CariHesap, CariHareket, CRMHareket
from app.modules.fatura.models import Fatura
from app.enums import CariIslemTuru

# Logger
logger = logging.getLogger(__name__)

# Constants
CACHE_TIMEOUT_SHORT = 300  # 5 dakika
CACHE_TIMEOUT_MEDIUM = 1800  # 30 dakika
CACHE_TIMEOUT_LONG = 3600  # 1 saat


# ============================================================
# 🔥 CUSTOM EXCEPTIONS
# ============================================================
class CariValidationError(Exception):
    """Cari Validation Hatası"""
    pass


class CariNotFoundError(Exception):
    """Cari Bulunamadı Hatası"""
    pass


# ============================================================
# 💳 CARİ HESAP SERVİSİ
# ============================================================
class CariService:
    """
    Cari Hesap İşlemleri
    
    Özellikler:
    - Redis cache kullanımı
    - AI risk analizi
    - Babel i18n desteği
    """
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_MEDIUM)
    def get_by_id(cari_id: str, firma_id: str, tenant_db=None) -> Optional[CariHesap]:
        """
        ID'ye göre cari getir (Cached + Eager Loading)
        
        Args:
            cari_id: Cari ID (UUID)
            firma_id: Firma ID (UUID)
            tenant_db: Tenant DB session
        
        Returns:
            CariHesap instance veya None
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            cari = tenant_db.query(CariHesap).options(
                joinedload(CariHesap.sehir),
                joinedload(CariHesap.ilce),
                joinedload(CariHesap.odeme_plani_rel)
            ).filter(
                CariHesap.id == cari_id,
                CariHesap.firma_id == firma_id,
                CariHesap.deleted_at.is_(None)
            ).first()
            
            return cari
        
        except Exception as e:
            logger.error(f"❌ Cari getirme hatası (ID: {cari_id}): {e}")
            return None
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_LONG)
    def get_by_kod(cari_kodu: str, firma_id: str, tenant_db=None) -> Optional[CariHesap]:
        """
        Kod'a göre cari getir (Cached)
        
        Args:
            cari_kodu: Cari kodu
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            CariHesap instance veya None
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            cari = tenant_db.query(CariHesap).filter(
                CariHesap.kod == cari_kodu,
                CariHesap.firma_id == firma_id,
                CariHesap.deleted_at.is_(None)
            ).first()
            
            return cari
        
        except Exception as e:
            logger.error(f"❌ Cari getirme hatası (Kod: {cari_kodu}): {e}")
            return None
    
    @staticmethod
    @cache.cached(timeout=CACHE_TIMEOUT_SHORT, key_prefix='cari_bakiye')
    def get_bakiye(cari_id: str, firma_id: str, tenant_db=None) -> Dict[str, Any]:
        """
        Cari bakiye bilgilerini getir (Cached)
        
        Args:
            cari_id: Cari ID
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            {
                'borc': Decimal,
                'alacak': Decimal,
                'net': Decimal,
                'durum': str
            }
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            cari = tenant_db.query(CariHesap).get(cari_id)
            
            if not cari:
                return {
                    'borc': Decimal('0.00'),
                    'alacak': Decimal('0.00'),
                    'net': Decimal('0.00'),
                    'durum': 'DENGELI'
                }
            
            return {
                'borc': cari.borc_bakiye,
                'alacak': cari.alacak_bakiye,
                'net': cari.net_bakiye,
                'durum': cari.bakiye_durumu
            }
        
        except Exception as e:
            logger.error(f"❌ Bakiye getirme hatası: {e}")
            return {
                'borc': Decimal('0.00'),
                'alacak': Decimal('0.00'),
                'net': Decimal('0.00'),
                'durum': 'HATA'
            }
    
    @staticmethod
    def save(form_data: Dict[str, Any], cari: Optional[CariHesap] = None, tenant_db=None) -> Tuple[bool, str]:
        """
        Cari hesap kaydet/güncelle
        
        Args:
            form_data: Form verisi
            cari: Mevcut CariHesap instance (güncelleme için)
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            is_new = (cari is None)
            
            if is_new:
                cari = CariHesap()
                cari.firma_id = current_user.firma_id
            
            # Form verilerini doldur
            CariService._form_to_model(cari, form_data)
            
            tenant_db.add(cari)
            tenant_db.flush()
            
            # AI analizlerini güncelle
            cari.ai_analiz_guncelle()
            
            tenant_db.commit()
            
            # Cache'i temizle
            CariService._invalidate_cache(cari.id, cari.firma_id)
            
            mesaj = _("Yeni cari hesap oluşturuldu") if is_new else _("Cari hesap güncellendi")
            logger.info(f"✅ Cari kaydedildi: {cari.kod} - {cari.unvan}")
            
            return True, f"{mesaj}: {cari.kod}"
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Cari kaydetme hatası: {e}", exc_info=True)
            return False, _("Kaydetme başarısız: %(error)s", error=str(e))
    
    @staticmethod
    def _form_to_model(cari: CariHesap, form_data: Dict[str, Any]):
        """Form verisini model'e doldur"""
        from app.araclar import para_cevir
        
        cari.kod = form_data.get('kod', '').strip().upper()
        cari.unvan = form_data.get('unvan', '').strip()
        cari.vergi_no = form_data.get('vergi_no', '').strip() or None
        cari.vergi_dairesi = form_data.get('vergi_dairesi', '').strip() or None
        
        cari.telefon = form_data.get('telefon', '').strip() or None
        cari.eposta = form_data.get('eposta', '').strip() or None
        cari.adres = form_data.get('adres', '').strip() or None
        
        sehir_id = form_data.get('sehir_id')
        cari.sehir_id = sehir_id if sehir_id else None
        
        ilce_id = form_data.get('ilce_id')
        cari.ilce_id = ilce_id if ilce_id else None
        
        cari.konum = form_data.get('konum', '').strip() or None
        
        alis_hesap = form_data.get('alis_muhasebe_hesap_id')
        cari.alis_muhasebe_hesap_id = alis_hesap if alis_hesap else None
        
        satis_hesap = form_data.get('satis_muhasebe_hesap_id')
        cari.satis_muhasebe_hesap_id = satis_hesap if satis_hesap else None
    
    @staticmethod
    def _invalidate_cache(cari_id: str, firma_id: str):
        """Cari ile ilgili cache'leri temizle"""
        try:
            # ID bazlı cache
            cache.delete_memoized(CariService.get_by_id, cari_id, firma_id)
            
            # Bakiye cache
            cache.delete(f"cari_bakiye:{cari_id}")
            
            # AI metadata cache
            cache.delete(f"cari_ai:{cari_id}")
            
            logger.debug(f"🗑️ Cari cache temizlendi: {cari_id}")
        
        except Exception as e:
            logger.warning(f"⚠️ Cache temizleme hatası: {e}")
    
    @staticmethod
    def sil(cari_id: str, firma_id: str, tenant_db=None) -> Tuple[bool, str]:
        """
        Cari hesabı sil (Soft Delete)
        
        Args:
            cari_id: Cari ID
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            cari = tenant_db.query(CariHesap).filter_by(
                id=cari_id,
                firma_id=firma_id
            ).first()
            
            if not cari:
                return False, _("Cari bulunamadı")
            
            # Hareket kontrolü
            hareket_sayisi = tenant_db.query(func.count(CariHareket.id)).filter(
                CariHareket.cari_id == cari_id
            ).scalar()
            
            if hareket_sayisi > 0:
                return False, _(
                    "Bu carinin %(count)d adet hareketi var. Önce hareketleri temizleyin.",
                    count=hareket_sayisi
                )
            
            # Soft Delete
            cari.deleted_at = datetime.now()
            cari.deleted_by = str(current_user.id)
            
            tenant_db.commit()
            
            # Cache'i temizle
            CariService._invalidate_cache(cari_id, firma_id)
            
            logger.info(f"✅ Cari silindi (soft): {cari.kod}")
            return True, _("Cari hesap başarıyla silindi")
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Cari silme hatası: {e}")
            return False, _("Silme işlemi başarısız: %(error)s", error=str(e))
    
    @staticmethod
    def bakiye_hesapla_ve_guncelle(cari_id: str, tenant_db=None):
        """
        Cari bakiyeyi hareketlerden yeniden hesapla
        
        Args:
            cari_id: Cari ID
            tenant_db: Tenant DB session
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # ✅ MySQL Aggregate Query
            result = tenant_db.execute(text("""
                SELECT 
                    COALESCE(SUM(borc), 0) as toplam_borc,
                    COALESCE(SUM(alacak), 0) as toplam_alacak
                FROM cari_hareket
                WHERE cari_id = :cari_id
            """), {'cari_id': cari_id}).fetchone()
            
            if result:
                toplam_borc = Decimal(str(result[0]))
                toplam_alacak = Decimal(str(result[1]))
                
                # Cari'yi güncelle
                cari = tenant_db.query(CariHesap).get(cari_id)
                if cari:
                    cari.borc_bakiye = toplam_borc
                    cari.alacak_bakiye = toplam_alacak
                    
                    tenant_db.commit()
                    
                    # Cache'i temizle
                    CariService._invalidate_cache(cari_id, cari.firma_id)
                    
                    logger.info(
                        f"✅ Cari bakiye güncellendi: {cari.kod} "
                        f"Borç:{toplam_borc} Alacak:{toplam_alacak}"
                    )
        
        except Exception as e:
            logger.error(f"❌ Bakiye hesaplama hatası: {e}")
    
    @staticmethod
    def hareket_ekle(
        cari_id: str,
        islem_turu: str,
        belge_no: str,
        tarih: date,
        aciklama: str,
        kaynak_ref: Dict[str, Any],
        borc: Decimal = Decimal('0.00'),
        alacak: Decimal = Decimal('0.00'),
        vade_tarihi: Optional[date] = None,
        donem_id: Optional[str] = None,
        sube_id: Optional[str] = None,
        tenant_db=None
    ) -> Tuple[bool, str]:
        """
        Cari hareket ekle
        
        Args:
            cari_id: Cari ID
            islem_turu: İşlem türü
            belge_no: Belge numarası
            tarih: Hareket tarihi
            aciklama: Açıklama
            kaynak_ref: Kaynak belge {'tur': 'fatura', 'id': '...'}
            borc: Borç tutarı
            alacak: Alacak tutarı
            vade_tarihi: Vade tarihi
            donem_id: Dönem ID
            sube_id: Şube ID
            tenant_db: Tenant DB session
        
        Returns:
            (Başarı durumu, Mesaj)
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # Tarih kontrolü
            if isinstance(tarih, str):
                try:
                    tarih = datetime.strptime(tarih, '%Y-%m-%d').date()
                except:
                    tarih = date.today()
            
            # Yeni hareket
            hareket = CariHareket()
            hareket.cari_id = cari_id
            
            # Firma ve kullanıcı
            if current_user and current_user.is_authenticated:
                hareket.firma_id = current_user.firma_id
                hareket.olusturan_id = str(current_user.id)
            else:
                hareket.firma_id = session.get('firma_id')
            
            # Dönem ID
            if donem_id:
                hareket.donem_id = donem_id
            elif session.get('aktif_donem_id'):
                hareket.donem_id = session.get('aktif_donem_id')
            
            # Şube ID
            if sube_id:
                hareket.sube_id = sube_id
            elif session.get('aktif_sube_id'):
                hareket.sube_id = session.get('aktif_sube_id')
            
            # Diğer alanlar
            hareket.islem_turu = islem_turu
            hareket.belge_no = belge_no
            hareket.tarih = tarih
            hareket.vade_tarihi = vade_tarihi or tarih
            hareket.aciklama = aciklama
            
            hareket.borc = Decimal(str(borc))
            hareket.alacak = Decimal(str(alacak))
            
            # Kaynak referansı
            if kaynak_ref:
                hareket.kaynak_turu = kaynak_ref.get('tur')
                hareket.kaynak_id = kaynak_ref.get('id')
            
            tenant_db.add(hareket)
            tenant_db.flush()
            
            # Bakiyeyi güncelle
            CariService.bakiye_hesapla_ve_guncelle(cari_id, tenant_db)
            
            tenant_db.commit()
            
            logger.info(
                f"✅ Cari hareket eklendi: {belge_no} "
                f"Borç:{borc} Alacak:{alacak}"
            )
            
            return True, _("Cari hareket eklendi")
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Cari hareket ekleme hatası: {e}", exc_info=True)
            return False, _("Hareket eklenemedi: %(error)s", error=str(e))


# ============================================================
# 🤖 CARİ AI SERVİSİ (Redis Cached)
# ============================================================
class CariAIService:
    """
    Cari AI Analiz İşlemleri
    
    Özellikler:
    - Risk analizi
    - Churn tahmini
    - Sadakat skoru
    - Redis cache kullanımı
    """
    
    @staticmethod
    @cache.cached(timeout=CACHE_TIMEOUT_LONG, key_prefix='cari_risk_analiz')
    def risk_analizi(firma_id: str, tenant_db=None) -> Dict[str, Any]:
        """
        Tüm cariler için risk analizi (Cached)
        
        Args:
            firma_id: Firma ID
            tenant_db: Tenant DB session
        
        Returns:
            {
                'yuksek_riskli': List[Dict],
                'dikkat': List[Dict],
                'toplam_risk_tutari': Decimal
            }
        """
        if tenant_db is None:
            tenant_db = get_tenant_db()
        
        try:
            # ✅ MySQL Optimized Query
            results = tenant_db.execute(text("""
                SELECT 
                    id,
                    kod,
                    unvan,
                    borc_bakiye,
                    alacak_bakiye,
                    (borc_bakiye - alacak_bakiye) as net_bakiye,
                    risk_skoru,
                    risk_durumu,
                    son_siparis_tarihi
                FROM cari_hesaplar
                WHERE firma_id = :firma_id
                AND deleted_at IS NULL
                AND aktif = 1
                AND risk_skoru > 40
                ORDER BY risk_skoru DESC, (borc_bakiye - alacak_bakiye) DESC
                LIMIT 50
            """), {'firma_id': firma_id}).fetchall()
            
            yuksek_riskli = []
            dikkat = []
            toplam_risk_tutari = Decimal('0.00')
            
            for row in results:
                net_bakiye = Decimal(str(row.net_bakiye))
                risk_skoru = row.risk_skoru
                
                if net_bakiye > 0:
                    toplam_risk_tutari += net_bakiye
                
                cari_data = {
                    'id': str(row.id),
                    'kod': row.kod,
                    'unvan': row.unvan,
                    'net_bakiye': float(net_bakiye),
                    'risk_skoru': risk_skoru,
                    'risk_durumu': row.risk_durumu
                }
                
                if risk_skoru > 70:
                    yuksek_riskli.append(cari_data)
                else:
                    dikkat.append(cari_data)
            
            logger.info(
                f"📊 Cari risk analizi: "
                f"Yüksek:{len(yuksek_riskli)} Dikkat:{len(dikkat)}"
            )
            
            return {
                'yuksek_riskli': yuksek_riskli,
                'dikkat': dikkat,
                'toplam_risk_tutari': float(toplam_risk_tutari)
            }
        
        except Exception as e:
            logger.error(f"❌ Risk analizi hatası: {e}")
            return {
                'yuksek_riskli': [],
                'dikkat': [],
                'toplam_risk_tutari': 0.0
            }