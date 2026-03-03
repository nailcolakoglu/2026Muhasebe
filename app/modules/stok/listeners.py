# app/modules/stok/listeners.py (MySQL Optimized & Safe UUID)

"""
Stok Modülü Event Listeners
SQLAlchemy Events + Blinker Signals
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import event
from blinker import signal
from flask_login import current_user

from app.extensions import get_tenant_db
from app.modules.stok.models import StokHareketi, StokDepoDurumu, StokKart
from app.modules.siparis.models import SiparisDetay

logger = logging.getLogger(__name__)

# ========================================
# BLINKER SIGNALS
# ========================================
siparis_sevk_edildi = signal('siparis-sevk-edildi')
stok_kritik_seviye_alti = signal('stok-kritik-seviye-alti')

# ========================================
# SQLALCHEMY EVENT LISTENERS
# ========================================

@event.listens_for(StokHareketi, 'after_insert')
def stok_hareket_after_insert(mapper, connection, target):
    """Stok hareketi eklendikten sonra depo durumunu anında günceller"""
    try:
        yon = getattr(target, 'yon', 0)
        
        # Eğer modelde 'yon' property yoksa manuel hesapla
        if yon == 0 and target.hareket_turu:
            tur = str(target.hareket_turu).upper()
            if 'GIRIS' in tur or 'ALIS' in tur: yon = 1
            elif 'CIKIS' in tur or 'SATIS' in tur or 'FIRE' in tur: yon = -1
            if 'IADE' in tur: yon *= -1
            
        if yon == 0: return

        miktar_degisimi = target.miktar * yon
        
        if target.giris_depo_id:
            _depo_durumu_guncelle(connection, str(target.giris_depo_id), str(target.stok_id), miktar_degisimi, str(target.firma_id))
        
        if target.cikis_depo_id:
            _depo_durumu_guncelle(connection, str(target.cikis_depo_id), str(target.stok_id), -miktar_degisimi, str(target.firma_id))
            
    except Exception as e:
        logger.error(f"❌ Stok hareket after_insert hatası: {e}")

@event.listens_for(StokHareketi, 'after_delete')
def stok_hareket_after_delete(mapper, connection, target):
    """Stok hareketi silinirse deponun dengesini geri yükler"""
    try:
        yon = getattr(target, 'yon', 0)
        
        if yon == 0 and target.hareket_turu:
            tur = str(target.hareket_turu).upper()
            if 'GIRIS' in tur or 'ALIS' in tur: yon = 1
            elif 'CIKIS' in tur or 'SATIS' in tur or 'FIRE' in tur: yon = -1
            if 'IADE' in tur: yon *= -1

        if yon == 0: return
        
        # Hareketin tam tersini (negatifini) uyguluyoruz
        miktar_degisimi = -(target.miktar * yon)
        
        if target.giris_depo_id:
            _depo_durumu_guncelle(connection, str(target.giris_depo_id), str(target.stok_id), miktar_degisimi, str(target.firma_id))
        
        if target.cikis_depo_id:
            _depo_durumu_guncelle(connection, str(target.cikis_depo_id), str(target.stok_id), -miktar_degisimi, str(target.firma_id))
            
    except Exception as e:
        logger.error(f"❌ Stok hareket after_delete hatası: {e}")

def _depo_durumu_guncelle(connection, depo_id: str, stok_id: str, miktar_degisimi: Decimal, firma_id: str):
    """
    ✨ GÜVENLİ UPSERT: Depo durumu satırı yoksa oluşturur, varsa sadece miktarını günceller.
    Python UUID kullanılarak her veritabanı motoruyla (MySQL/MariaDB) %100 uyumlu hale getirildi.
    """
    from sqlalchemy import text
    
    connection.execute(text("""
        INSERT INTO stok_depo_durumu (id, firma_id, depo_id, stok_id, miktar, son_hareket_tarihi)
        VALUES (:id, :firma_id, :depo_id, :stok_id, :miktar, CURDATE())
        ON DUPLICATE KEY UPDATE
            miktar = miktar + :miktar,
            son_hareket_tarihi = CURDATE()
    """), {
        'id': str(uuid.uuid4()),
        'firma_id': firma_id,
        'depo_id': depo_id,
        'stok_id': stok_id,
        'miktar': float(miktar_degisimi)
    })

@event.listens_for(StokDepoDurumu, 'after_update')
def stok_depo_durumu_after_update(mapper, connection, target):
    try:
        from sqlalchemy import select
        stmt = select(StokKart).where(StokKart.id == target.stok_id)
        stok = connection.execute(stmt).fetchone()
        
        if stok and float(stok.kritik_seviye or 0) > 0:
            if float(target.miktar) <= float(stok.kritik_seviye):
                stok_kritik_seviye_alti.send(
                    target, stok_id=target.stok_id, depo_id=target.depo_id,
                    miktar=target.miktar, kritik_seviye=stok.kritik_seviye
                )
    except Exception as e:
        logger.error(f"❌ Kritik seviye kontrolü hatası: {e}")

# ========================================
# BLINKER SIGNAL HANDLERS
# ========================================

@siparis_sevk_edildi.connect
def stok_hareketi_olustur(sender, **kwargs):
    """Sipariş Sevk Sinyalini Dinler ve Stok Hareketi Oluşturur"""
    tenant_db = get_tenant_db()
    if not tenant_db: return
    
    siparis = kwargs.get('siparis')
    sevk_verileri = kwargs.get('sevk_verileri', [])
    cikis_depo_id = str(kwargs.get('cikis_depo_id')) if kwargs.get('cikis_depo_id') else None
    
    if not siparis or not sevk_verileri: return
    
    try:
        from app.signals import stok_hareket_olusturuldu
        
        for veri in sevk_verileri:
            detay_id = str(veri.get('detay_id'))
            miktar = Decimal(str(veri.get('miktar', 0)))
            if miktar <= 0: continue
            
            detay = tenant_db.query(SiparisDetay).get(detay_id)
            if not detay: continue
            
            hareket = StokHareketi(
                firma_id=str(siparis.firma_id),
                donem_id=str(siparis.donem_id),
                sube_id=str(siparis.sube_id),
                kullanici_id=str(current_user.id) if current_user and current_user.is_authenticated else None,
                stok_id=str(detay.stok_id),
                cikis_depo_id=cikis_depo_id,
                tarih=datetime.now().date(),
                belge_no=f"SEVK-{siparis.belge_no}-{datetime.now().strftime('%H%M%S')}",
                hareket_turu='SATIS',
                miktar=miktar,
                birim_fiyat=detay.birim_fiyat,
                doviz_turu=siparis.doviz_turu,
                doviz_kuru=siparis.doviz_kuru,
                kaynak_turu='siparis',
                kaynak_id=str(siparis.id),
                kaynak_belge_detay_id=str(detay.id),
                aciklama=f"Sipariş Sevkiyatı: {siparis.belge_no}"
            )
            tenant_db.add(hareket)
            tenant_db.flush()
            
            # ✨ DÜZELTME: Sinyal Ateşlendi
            stok_hareket_olusturuldu.send(hareket)
            
    except Exception as e:
        logger.error(f"❌ Sipariş Stok hareketi oluşturma hatası: {e}")
        raise

@stok_kritik_seviye_alti.connect
def kritik_stok_bildirimi_gonder(sender, **kwargs):
    """Kritik stok seviyesi alarmı"""
    logger.warning(
        f"🚨 AI BİLDİRİMİ: Stok kritik seviyenin altına düştü! "
        f"Stok:{kwargs.get('stok_id')} Depo:{kwargs.get('depo_id')} "
        f"Miktar:{kwargs.get('miktar')} Kritik:{kwargs.get('kritik_seviye')}"
    )