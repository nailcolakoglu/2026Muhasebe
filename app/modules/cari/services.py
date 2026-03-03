# app/modules/cari/services.py (Redis + Babel Enhanced + AI Secure)

"""
Cari Modülü Servis Katmanı
Enterprise Grade - Redis Cached - i18n Ready
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date
import logging

from sqlalchemy import func, text
from sqlalchemy.orm import joinedload
from flask import session
from flask_login import current_user
from flask_babel import gettext as _

from app.extensions import cache, get_tenant_db
from app.modules.cari.models import CariHesap, CariHareket

logger = logging.getLogger(__name__)

CACHE_TIMEOUT_SHORT = 300  
CACHE_TIMEOUT_MEDIUM = 1800  
CACHE_TIMEOUT_LONG = 3600  

class CariService:
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_MEDIUM)
    def get_by_id(cari_id: str, firma_id: str, tenant_db=None) -> Optional[CariHesap]:
        if tenant_db is None:
            tenant_db = get_tenant_db()
        try:
            # Eager Loading ile Şehir ve İlçe isimlerini baştan alıyoruz (N+1 Sorgu Problemini Engeller)
            return tenant_db.query(CariHesap).options(
                joinedload(CariHesap.sehir),
                joinedload(CariHesap.ilce),
                joinedload(CariHesap.odeme_plani_rel)
            ).filter(
                CariHesap.id == cari_id,
                CariHesap.firma_id == firma_id,
                CariHesap.deleted_at.is_(None)
            ).first()
        except Exception as e:
            logger.error(f"❌ Cari getirme hatası (ID: {cari_id}): {e}")
            return None
    
    @staticmethod
    def save(form_data: Dict[str, Any], cari: Optional[CariHesap] = None, tenant_db=None) -> Tuple[bool, str]:
        if tenant_db is None:
            tenant_db = get_tenant_db()
        try:
            is_new = (cari is None)
            if is_new:
                cari = CariHesap()
                cari.firma_id = current_user.firma_id
            
            # Form verilerini model'e aktar
            cari.kod = form_data.get('kod', '').strip().upper()
            cari.unvan = form_data.get('unvan', '').strip()
            cari.vergi_no = form_data.get('vergi_no', '').strip() or None
            cari.vergi_dairesi = form_data.get('vergi_dairesi', '').strip() or None
            cari.telefon = form_data.get('telefon', '').strip() or None
            cari.eposta = form_data.get('eposta', '').strip() or None
            cari.adres = form_data.get('adres', '').strip() or None
            cari.sehir_id = form_data.get('sehir_id') or None
            cari.ilce_id = form_data.get('ilce_id') or None
            cari.alis_muhasebe_hesap_id = form_data.get('alis_muhasebe_hesap_id') or None
            cari.satis_muhasebe_hesap_id = form_data.get('satis_muhasebe_hesap_id') or None
            
            tenant_db.add(cari)
            tenant_db.flush()
            
            if hasattr(cari, 'ai_analiz_guncelle'):
                cari.ai_analiz_guncelle()
            
            tenant_db.commit()
            CariService._invalidate_cache(cari.id, cari.firma_id)
            
            mesaj = _("Yeni cari hesap oluşturuldu") if is_new else _("Cari hesap güncellendi")
            return True, f"{mesaj}: {cari.kod}"
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Cari kaydetme hatası: {e}", exc_info=True)
            return False, _("Kaydetme başarısız: %(error)s", error=str(e))
            
    @staticmethod
    def _invalidate_cache(cari_id: str, firma_id: str):
        try:
            cache.delete_memoized(CariService.get_by_id, cari_id, firma_id)
            cache.delete(f"cari_bakiye:{cari_id}")
            cache.delete(f"cari_risk_analiz:{firma_id}")
        except Exception:
            pass

    @staticmethod
    def sil(cari_id: str, firma_id: str, tenant_db=None) -> Tuple[bool, str]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            cari = tenant_db.query(CariHesap).filter_by(id=cari_id, firma_id=firma_id).first()
            if not cari: return False, _("Cari bulunamadı")
            
            # Cari üzerinde işlem var mı?
            hareket_sayisi = tenant_db.query(func.count(CariHareket.id)).filter(CariHareket.cari_id == cari_id).scalar()
            if hareket_sayisi > 0:
                return False, _("Bu carinin %(count)d adet hareketi var. Önce hareketleri temizleyin.", count=hareket_sayisi)
            
            cari.deleted_at = datetime.now()
            cari.deleted_by = str(current_user.id)
            tenant_db.commit()
            CariService._invalidate_cache(cari_id, firma_id)
            return True, _("Cari hesap başarıyla silindi")
        except Exception as e:
            tenant_db.rollback()
            return False, _("Silme işlemi başarısız: %(error)s", error=str(e))

    @staticmethod
    def bakiye_hesapla_ve_guncelle(cari_id: str, tenant_db=None):
        """Tüm hareketleri tarayıp bakiyeyi kuruşu kuruşuna yeniden hesaplar (Auto-Correction)"""
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            result = tenant_db.execute(text("""
                SELECT 
                    COALESCE(SUM(borc), 0) as toplam_borc,
                    COALESCE(SUM(alacak), 0) as toplam_alacak
                FROM cari_hareket
                WHERE cari_id = :cari_id AND deleted_at IS NULL
            """), {'cari_id': str(cari_id)}).fetchone()
            
            if result:
                toplam_borc = Decimal(str(result[0]))
                toplam_alacak = Decimal(str(result[1]))
                
                cari = tenant_db.query(CariHesap).get(str(cari_id))
                if cari:
                    cari.borc_bakiye = toplam_borc
                    cari.alacak_bakiye = toplam_alacak
                    
                    if hasattr(cari, 'bakiye'): # Modelde bakiye diye birleşik alan varsa
                        cari.bakiye = toplam_borc - toplam_alacak
                        
                    tenant_db.commit()
                    CariService._invalidate_cache(cari_id, cari.firma_id)
        except Exception as e:
            logger.error(f"❌ Cari bakiye hesaplama hatası: {e}")

    @staticmethod
    def hareket_ekle(
        cari_id: str, islem_turu, belge_no: str, tarih: date, aciklama: str,
        kaynak_ref: Dict[str, Any], borc: Decimal = Decimal('0.00'), alacak: Decimal = Decimal('0.00'),
        vade_tarihi: Optional[date] = None, donem_id: Optional[str] = None, sube_id: Optional[str] = None,
        tenant_db=None
    ) -> Tuple[bool, str]:
        """Diğer modüllerden (Fatura, Kasa, Banka) gelen hareketleri işler ve bakiyeyi günceller."""
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            hareket = CariHareket()
            hareket.cari_id = str(cari_id)
            hareket.firma_id = current_user.firma_id if hasattr(current_user, 'firma_id') else session.get('firma_id')
            hareket.donem_id = donem_id or session.get('aktif_donem_id')
            hareket.sube_id = sube_id or session.get('aktif_sube_id')
            
            # Enum Güvenliği
            hareket.islem_turu = islem_turu.value if hasattr(islem_turu, 'value') else str(islem_turu)
            
            hareket.belge_no = belge_no
            hareket.tarih = tarih if not isinstance(tarih, str) else datetime.strptime(tarih, '%Y-%m-%d').date()
            hareket.vade_tarihi = vade_tarihi or hareket.tarih
            hareket.aciklama = aciklama
            hareket.borc = Decimal(str(borc))
            hareket.alacak = Decimal(str(alacak))
            
            if kaynak_ref:
                hareket.kaynak_turu = kaynak_ref.get('tur')
                hareket.kaynak_id = kaynak_ref.get('id')
            
            tenant_db.add(hareket)
            tenant_db.flush() # Hareket database'e yazıldı (commit bekliyor)
            
            # Bakiyeyi anında yeniden hesapla ve Cari Master tabloya yaz
            CariService.bakiye_hesapla_ve_guncelle(cari_id, tenant_db)
            
            tenant_db.commit()
            return True, _("Cari hareket eklendi")
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Cari hareket ekleme hatası: {e}", exc_info=True)
            return False, _("Hareket eklenemedi: %(error)s", error=str(e))

class CariAIService:
    @staticmethod
    @cache.cached(timeout=CACHE_TIMEOUT_LONG, key_prefix='cari_risk_analiz')
    def risk_analizi(firma_id: str, tenant_db=None) -> Dict[str, Any]:
        """Tüm cariler için AI tabanlı risk (Batık Kredi) analizi"""
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            results = tenant_db.execute(text("""
                SELECT id, kod, unvan, borc_bakiye, alacak_bakiye,
                       (borc_bakiye - alacak_bakiye) as net_bakiye,
                       risk_skoru, risk_durumu
                FROM cari_hesaplar
                WHERE firma_id = :firma_id AND deleted_at IS NULL AND aktif = 1 AND risk_skoru > 40
                ORDER BY risk_skoru DESC, (borc_bakiye - alacak_bakiye) DESC LIMIT 50
            """), {'firma_id': firma_id}).fetchall()
            
            yuksek_riskli, dikkat = [], []
            toplam_risk_tutari = Decimal('0.00')
            
            for row in results:
                net_bakiye = Decimal(str(row.net_bakiye))
                if net_bakiye > 0: toplam_risk_tutari += net_bakiye
                
                cari_data = {
                    'id': str(row.id), 'kod': row.kod, 'unvan': row.unvan,
                    'net_bakiye': float(net_bakiye), 'risk_skoru': row.risk_skoru, 'risk_durumu': row.risk_durumu
                }
                
                if row.risk_skoru > 70: yuksek_riskli.append(cari_data)
                else: dikkat.append(cari_data)
            
            return {'yuksek_riskli': yuksek_riskli, 'dikkat': dikkat, 'toplam_risk_tutari': float(toplam_risk_tutari)}
        except Exception as e:
            logger.error(f"❌ Risk analizi hatası: {e}")
            return {'yuksek_riskli': [], 'dikkat': [], 'toplam_risk_tutari': 0.0}