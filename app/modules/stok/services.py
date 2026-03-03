# app/modules/stok/services.py (MySQL + AI + Redis + Babel)

import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import joinedload, selectinload
from flask import session
from flask_login import current_user
from flask_babel import gettext as _

from app.extensions import cache, get_tenant_db
from app.modules.stok.models import (
    StokKart, StokHareketi, StokDepoDurumu,
    StokMuhasebeGrubu, StokKDVGrubu, StokPaketIcerigi
)
from app.modules.fatura.models import Fatura
from app.signals import stok_hareket_olusturuldu

logger = logging.getLogger(__name__)

CACHE_TIMEOUT_SHORT = 300  
CACHE_TIMEOUT_MEDIUM = 1800  
CACHE_TIMEOUT_LONG = 3600  

class StokValidationError(Exception): pass

class StokKartService:
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_MEDIUM)
    def get_by_id(stok_id: str, firma_id: str, tenant_db=None) -> Optional[StokKart]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            return tenant_db.query(StokKart).options(
                joinedload(StokKart.kategori),
                joinedload(StokKart.muhasebe_grubu),
                joinedload(StokKart.kdv_grubu),
                joinedload(StokKart.tedarikci),
                selectinload(StokKart.depo_durumlari)
            ).filter(
                StokKart.id == str(stok_id),
                StokKart.firma_id == str(firma_id),
                StokKart.deleted_at.is_(None)
            ).first()
        except Exception as e:
            logger.error(f"❌ Stok getirme hatası: {e}")
            return None
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TIMEOUT_SHORT)
    def get_toplam_stok(stok_id: str, firma_id: str, tenant_db=None) -> Decimal:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            toplam = tenant_db.execute(text("""
                SELECT COALESCE(SUM(miktar), 0)
                FROM stok_depo_durumu
                WHERE stok_id = :stok_id AND firma_id = :firma_id
            """), {'stok_id': str(stok_id), 'firma_id': str(firma_id)}).scalar()
            return Decimal(str(toplam))
        except Exception as e:
            return Decimal('0.00')
    
    @staticmethod
    def save(form_data: Dict[str, Any], stok: Optional[StokKart] = None, tenant_db=None) -> Tuple[bool, str]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            is_new = (stok is None)
            if is_new:
                stok = StokKart()
                stok.firma_id = str(current_user.firma_id)
            
            from app.araclar import para_cevir
            
            stok.kod = form_data.get('kod', '').strip().upper()
            stok.ad = form_data.get('ad', '').strip()
            stok.barkod = form_data.get('barkod', '').strip() or None
            stok.uretici_kodu = form_data.get('uretici_kodu', '').strip() or None
            stok.birim = form_data.get('birim', 'ADET')
            stok.tip = form_data.get('tip', 'STANDART')
            
            # String Dönüşümleri (ID Safe)
            stok.kategori_id = str(form_data.get('kategori_id')) if form_data.get('kategori_id') else None
            stok.muhasebe_kod_id = str(form_data.get('muhasebe_kod_id')) if form_data.get('muhasebe_kod_id') else None
            stok.kdv_kod_id = str(form_data.get('kdv_kod_id')) if form_data.get('kdv_kod_id') else None
            stok.tedarikci_id = str(form_data.get('tedarikci_id')) if form_data.get('tedarikci_id') else None
            
            stok.alis_fiyati = para_cevir(form_data.get('alis_fiyati', 0))
            stok.satis_fiyati = para_cevir(form_data.get('satis_fiyati', 0))
            stok.doviz_turu = form_data.get('doviz_turu', 'TL')
            
            stok.kritik_seviye = para_cevir(form_data.get('kritik_seviye', 0))
            stok.tedarik_suresi_gun = int(form_data.get('tedarik_suresi_gun', 3))
            stok.raf_omru_gun = int(form_data.get('raf_omru_gun', 0))
            
            stok.aktif = str(form_data.get('aktif')).lower() in ['true', '1', 'on', 'yes']
            
            tenant_db.add(stok)
            tenant_db.flush()
            
            if hasattr(stok, 'ai_analiz_guncelle'):
                stok.ai_analiz_guncelle()
            
            tenant_db.commit()
            
            try:
                cache.delete_memoized(StokKartService.get_by_id, stok.id, stok.firma_id)
                cache.delete_memoized(StokKartService.get_toplam_stok, stok.id, stok.firma_id)
            except: pass
            
            mesaj = _("Yeni stok kartı oluşturuldu") if is_new else _("Stok kartı güncellendi")
            return True, f"{mesaj}: {stok.kod}"
        
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Stok kaydetme hatası: {e}")
            return False, _("Kaydetme başarısız: %(error)s", error=str(e))

    @staticmethod
    def sil(stok_id: str, firma_id: str, tenant_db=None) -> Tuple[bool, str]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            stok = tenant_db.query(StokKart).filter_by(id=str(stok_id), firma_id=str(firma_id)).first()
            if not stok: return False, _("Stok bulunamadı")
            
            hareket_sayisi = tenant_db.query(func.count(StokHareketi.id)).filter(StokHareketi.stok_id == str(stok_id)).scalar()
            if hareket_sayisi > 0:
                return False, _("Bu stokun %(count)d adet hareketi var. Önce hareketleri temizleyin.", count=hareket_sayisi)
            
            stok.deleted_at = datetime.now()
            stok.deleted_by = str(current_user.id) if current_user else None
            tenant_db.commit()
            
            try:
                cache.delete_memoized(StokKartService.get_by_id, stok_id, firma_id)
            except: pass
            
            return True, _("Stok kartı başarıyla silindi")
        except Exception as e:
            tenant_db.rollback()
            return False, str(e)


class StokHareketService:
    
    @staticmethod
    def faturadan_hareket_olustur(fatura_id: str, tenant_db=None) -> Tuple[bool, str]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            fatura = tenant_db.query(Fatura).options(selectinload(Fatura.kalemler)).filter_by(id=str(fatura_id)).first()
            if not fatura: return False, _("Fatura bulunamadı")
            
            tenant_db.query(StokHareketi).filter(StokHareketi.kaynak_turu == 'fatura', StokHareketi.kaynak_id == str(fatura_id)).delete()
            tenant_db.flush()
            
            # ✨ GÜVENLİ ENUM KONTROLÜ
            tur_str = str(fatura.fatura_turu.value).upper() if hasattr(fatura.fatura_turu, 'value') else str(fatura.fatura_turu).upper()
            
            if 'SATIS' in tur_str and 'IADE' not in tur_str:
                hareket_turu, giris_depo_id, cikis_depo_id = 'SATIS', None, str(fatura.depo_id)
            elif 'ALIS' in tur_str and 'IADE' not in tur_str:
                hareket_turu, giris_depo_id, cikis_depo_id = 'ALIS', str(fatura.depo_id), None
            elif 'SATIS' in tur_str and 'IADE' in tur_str:
                hareket_turu, giris_depo_id, cikis_depo_id = 'SATIS_IADE', str(fatura.depo_id), None
            elif 'ALIS' in tur_str and 'IADE' in tur_str:
                hareket_turu, giris_depo_id, cikis_depo_id = 'ALIS_IADE', None, str(fatura.depo_id)
            else:
                return True, _("Hizmet faturası, stok hareketi oluşmadı")
            
            hareketler = []
            for kalem in fatura.kalemler:
                stok = tenant_db.query(StokKart).get(str(kalem.stok_id))
                if stok and stok.tip == 'HIZMET': continue
                
                hareket = StokHareketi(
                    firma_id=str(fatura.firma_id),
                    donem_id=str(fatura.donem_id),
                    sube_id=str(fatura.sube_id),
                    stok_id=str(kalem.stok_id),
                    giris_depo_id=giris_depo_id,
                    cikis_depo_id=cikis_depo_id,
                    tarih=fatura.tarih,
                    belge_no=fatura.belge_no,
                    hareket_turu=hareket_turu,
                    miktar=kalem.miktar,
                    birim_fiyat=kalem.birim_fiyat,
                    kaynak_turu='fatura',
                    kaynak_id=str(fatura.id),
                    kaynak_belge_detay_id=str(kalem.id)
                )
                tenant_db.add(hareket)
                hareketler.append(hareket)
            
            tenant_db.flush() # ID'ler oluşsun
            tenant_db.commit()
            
            # ✨ YENİ EKLENDİ: Tüm hareketler için sinyalleri fırlat
            for h in hareketler:
                stok_hareket_olusturuldu.send(h)
            
            return True, _("%(count)d adet stok hareketi oluşturuldu", count=len(hareketler))
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Fatura stok hareketi oluşturma hatası: {e}")
            return False, str(e)


class StokAIService:
    @staticmethod
    @cache.cached(timeout=CACHE_TIMEOUT_LONG, key_prefix='olu_stok_analiz')
    def olu_stok_analizi(firma_id: str, tenant_db=None) -> Dict[str, Any]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            alti_ay_once = date.today() - timedelta(days=180)
            results = tenant_db.execute(text("""
                SELECT sk.id, sk.kod, sk.ad, COALESCE(SUM(sdd.miktar), 0) as toplam_stok, sk.alis_fiyati,
                    COALESCE(SUM(fk.miktar), 0) as son_6_ay_satis
                FROM stok_kartlari sk
                LEFT JOIN stok_depo_durumu sdd ON sdd.stok_id = sk.id
                LEFT JOIN fatura_kalemleri fk ON fk.stok_id = sk.id
                LEFT JOIN faturalar f ON f.id = fk.fatura_id AND f.fatura_turu LIKE '%SATIS%' AND f.tarih >= :baslangic
                WHERE sk.firma_id = :firma_id AND sk.deleted_at IS NULL AND sk.aktif = 1
                GROUP BY sk.id, sk.kod, sk.ad, sk.alis_fiyati
                HAVING toplam_stok > 0 AND (son_6_ay_satis = 0 OR toplam_stok > (son_6_ay_satis * 3))
                ORDER BY (toplam_stok * sk.alis_fiyati) DESC LIMIT 50
            """), {'firma_id': str(firma_id), 'baslangic': alti_ay_once}).fetchall()
            
            urunler = [{'id': str(r.id), 'kod': r.kod, 'ad': r.ad, 'toplam_stok': float(r.toplam_stok), 'stok_degeri': float(r.toplam_stok * r.alis_fiyati)} for r in results]
            toplam_deger = sum(u['stok_degeri'] for u in urunler)
            
            return {'toplam_deger': float(toplam_deger), 'urun_sayisi': len(urunler), 'urunler': urunler}
        except Exception:
            return {'toplam_deger': 0.0, 'urun_sayisi': 0, 'urunler': []}

class PaketUrunService:
    @staticmethod
    def icerik_kaydet(paket_stok_id: str, icerik_listesi: List[Dict[str, Any]], tenant_db=None) -> Tuple[bool, str]:
        if tenant_db is None: tenant_db = get_tenant_db()
        try:
            tenant_db.query(StokPaketIcerigi).filter_by(paket_stok_id=str(paket_stok_id)).delete()
            for i, item in enumerate(icerik_listesi, 1):
                if not item.get('alt_stok_id') or Decimal(str(item.get('miktar', 1))) <= 0: continue
                tenant_db.add(StokPaketIcerigi(paket_stok_id=str(paket_stok_id), alt_stok_id=str(item.get('alt_stok_id')), miktar=Decimal(str(item.get('miktar', 1))), sira_no=i))
            
            stok = tenant_db.query(StokKart).get(str(paket_stok_id))
            if stok and stok.tip == 'STANDART': stok.tip = 'PAKET'
            tenant_db.commit()
            return True, _("Paket içeriği güncellendi")
        except Exception as e:
            tenant_db.rollback()
            return False, str(e)