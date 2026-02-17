# app/modules/stok/listeners.py (MySQL Optimized)

"""
Stok Modülü Event Listeners
SQLAlchemy Events + Blinker Signals
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.orm import Session
from blinker import signal
from flask_login import current_user

from app.extensions import db, get_tenant_db
from app.modules.stok.models import (
    StokHareketi, StokDepoDurumu, StokKart
)
from app.modules.siparis.models import SiparisDetay
from app.enums import HareketTuru

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
    """
    Stok hareketi eklendikten sonra depo durumunu güncelle
    
    Args:
        mapper: SQLAlchemy mapper
        connection: DB connection
        target: StokHareketi instance
    """
    try:
        # Hareket yönünü al
        yon = target.yon
        
        if yon == 0:
            return  # Etkisiz hareket
        
        # Miktar değişimi
        miktar_degisimi = target.miktar * yon
        
        # Giriş depo güncelleme
        if target.giris_depo_id:
            _depo_durumu_guncelle(
                connection,
                target.giris_depo_id,
                target.stok_id,
                miktar_degisimi,
                target.firma_id
            )
        
        # Çıkış depo güncelleme
        if target.cikis_depo_id:
            _depo_durumu_guncelle(
                connection,
                target.cikis_depo_id,
                target.stok_id,
                -miktar_degisimi,
                target.firma_id
            )
        
        logger.debug(
            f"📦 Depo durumu güncellendi: "
            f"Stok:{target.stok_id} Miktar:{miktar_degisimi}"
        )
    
    except Exception as e:
        logger.error(f"❌ Stok hareket after_insert hatası: {e}")


@event.listens_for(StokHareketi, 'after_delete')
def stok_hareket_after_delete(mapper, connection, target):
    """
    Stok hareketi silindikten sonra depo durumunu düzelt
    
    Args:
        mapper: SQLAlchemy mapper
        connection: DB connection
        target: StokHareketi instance
    """
    try:
        # Hareket tersine çevrilir
        yon = target.yon
        
        if yon == 0:
            return
        
        miktar_degisimi = -(target.miktar * yon)
        
        if target.giris_depo_id:
            _depo_durumu_guncelle(
                connection,
                target.giris_depo_id,
                target.stok_id,
                miktar_degisimi,
                target.firma_id
            )
        
        if target.cikis_depo_id:
            _depo_durumu_guncelle(
                connection,
                target.cikis_depo_id,
                target.stok_id,
                -miktar_degisimi,
                target.firma_id
            )
        
        logger.warning(f"⚠️ Stok hareketi silindi ve depo düzeltildi: {target.belge_no}")
    
    except Exception as e:
        logger.error(f"❌ Stok hareket after_delete hatası: {e}")


def _depo_durumu_guncelle(
    connection,
    depo_id: str,
    stok_id: str,
    miktar_degisimi: Decimal,
    firma_id: str
):
    """
    Depo durumunu güncelle (Upsert mantığı)
    
    Args:
        connection: SQLAlchemy connection
        depo_id: Depo ID
        stok_id: Stok ID
        miktar_degisimi: Miktar değişimi (+/-)
        firma_id: Firma ID
    """
    from sqlalchemy import text
    
    # ✅ MySQL UPSERT (INSERT ... ON DUPLICATE KEY UPDATE)
    connection.execute(text("""
        INSERT INTO stok_depo_durumu (id, firma_id, depo_id, stok_id, miktar, son_hareket_tarihi)
        VALUES (UUID(), :firma_id, :depo_id, :stok_id, :miktar, CURDATE())
        ON DUPLICATE KEY UPDATE
            miktar = miktar + :miktar,
            son_hareket_tarihi = CURDATE()
    """), {
        'firma_id': firma_id,
        'depo_id': depo_id,
        'stok_id': stok_id,
        'miktar': float(miktar_degisimi)
    })


@event.listens_for(StokDepoDurumu, 'after_update')
def stok_depo_durumu_after_update(mapper, connection, target):
    """
    Depo durumu güncellendikten sonra kritik seviye kontrolü
    
    Args:
        mapper: SQLAlchemy mapper
        connection: DB connection
        target: StokDepoDurumu instance
    """
    try:
        # Stok kartını çek (aynı session içinde)
        from sqlalchemy import select
        
        stmt = select(StokKart).where(StokKart.id == target.stok_id)
        result = connection.execute(stmt)
        stok = result.fetchone()
        
        if stok and stok.kritik_seviye > 0:
            if target.miktar <= stok.kritik_seviye:
                # Signal gönder (async işlemler için)
                stok_kritik_seviye_alti.send(
                    target,
                    stok_id=target.stok_id,
                    depo_id=target.depo_id,
                    miktar=target.miktar,
                    kritik_seviye=stok.kritik_seviye
                )
                
                logger.warning(
                    f"⚠️ KRİTİK STOK: {stok.ad} - "
                    f"Miktar:{target.miktar} Kritik:{stok.kritik_seviye}"
                )
    
    except Exception as e:
        logger.error(f"❌ Kritik seviye kontrolü hatası: {e}")


# ========================================
# BLINKER SIGNAL HANDLERS
# ========================================

@siparis_sevk_edildi.connect
def stok_hareketi_olustur(sender, **kwargs):
    """
    Sipariş sevk edildiğinde stok hareketi oluştur
    
    Args:
        sender: Sipariş instance
        **kwargs: sevk_verileri, cikis_depo_id
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        logger.error("❌ Tenant DB bağlantısı yok")
        return
    
    siparis = kwargs.get('siparis')
    sevk_verileri = kwargs.get('sevk_verileri', [])
    cikis_depo_id = kwargs.get('cikis_depo_id')
    
    if not siparis or not sevk_verileri:
        logger.error("❌ Sipariş veya sevk verileri eksik")
        return
    
    logger.info(
        f"📡 Stok Hareketi Oluşturuluyor: "
        f"Sipariş {siparis.belge_no} ({len(sevk_verileri)} kalem)"
    )
    
    try:
        for veri in sevk_verileri:
            detay_id = veri.get('detay_id')
            miktar = Decimal(str(veri.get('miktar', 0)))
            
            if miktar <= 0:
                continue
            
            # Detay bilgisi
            detay = tenant_db.query(SiparisDetay).get(detay_id)
            
            if not detay:
                logger.warning(f"⚠️ Sipariş detay bulunamadı: {detay_id}")
                continue
            
            # Stok hareketi oluştur
            hareket = StokHareketi(
                firma_id=siparis.firma_id,
                donem_id=siparis.donem_id,
                sube_id=siparis.sube_id,
                kullanici_id=str(current_user.id) if current_user.is_authenticated else None,
                
                stok_id=str(detay.stok_id),
                cikis_depo_id=cikis_depo_id,
                
                tarih=datetime.now().date(),
                belge_no=f"IRS-{siparis.belge_no}-{datetime.now().strftime('%H%M%S')}",
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
        
        # Commit yapan ana fonksiyon olacak (transaction bütünlüğü)
        logger.info(f"✅ {len(sevk_verileri)} adet stok hareketi oluşturuldu")
    
    except Exception as e:
        logger.error(f"❌ Stok hareketi oluşturma hatası: {e}")
        raise


@stok_kritik_seviye_alti.connect
def kritik_stok_bildirimi_gonder(sender, **kwargs):
    """
    Kritik stok seviyesi altına düştüğünde bildirim gönder
    
    Args:
        sender: StokDepoDurumu instance
        **kwargs: stok_id, depo_id, miktar, kritik_seviye
    """
    try:
        stok_id = kwargs.get('stok_id')
        depo_id = kwargs.get('depo_id')
        miktar = kwargs.get('miktar')
        kritik_seviye = kwargs.get('kritik_seviye')
        
        # TODO: Bildirim sistemi entegrasyonu
        # - Email gönder
        # - SMS gönder
        # - Push notification
        # - Slack/Teams webhook
        
        logger.warning(
            f"🚨 KRİTİK STOK BİLDİRİMİ: "
            f"Stok:{stok_id} Depo:{depo_id} "
            f"Miktar:{miktar} Kritik:{kritik_seviye}"
        )
    
    except Exception as e:
        logger.error(f"❌ Kritik stok bildirimi hatası: {e}")