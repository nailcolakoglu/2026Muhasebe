# app/modules/fatura/listeners.py (MySQL Optimized)

"""
Fatura Modülü Event Listeners
SQLAlchemy Events + Blinker Signals
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.orm import Session
from blinker import signal

from app.extensions import db
from app.modules.fatura.models import Fatura, FaturaKalemi

logger = logging.getLogger(__name__)

# ========================================
# BLINKER SIGNALS
# ========================================
fatura_onaylandi = signal('fatura-onaylandi')
fatura_iptal_edildi = signal('fatura-iptal-edildi')
fatura_kaydedildi = signal('fatura-kaydedildi')


# ========================================
# SQLALCHEMY EVENT LISTENERS
# ========================================

@event.listens_for(FaturaKalemi, 'before_insert')
@event.listens_for(FaturaKalemi, 'before_update')
def fatura_kalemi_before_save(mapper, connection, target):
    """
    Fatura kalemi kaydedilmeden önce hesaplamaları yap
    
    Args:
        mapper: SQLAlchemy mapper
        connection: DB connection
        target: FaturaKalemi instance
    """
    # Tutarları hesapla
    target.hesapla()
    
    # AI fiyat analizi (sadece yeni kayıtta veya fiyat değiştiğinde)
    if target.birim_fiyat and target.birim_fiyat > 0:
        # Session içinde çalıştığımız için db.session yerine Session kullan
        session = Session.object_session(target)
        if session:
            # AI analizi arka planda yapılmalı (performans için)
            # Burada sadece flag set ediyoruz
            target.ai_metadata = target.ai_metadata or {}
            target.ai_metadata['analiz_gerekli'] = True


@event.listens_for(Fatura, 'before_update')
def fatura_before_update(mapper, connection, target):
    """
    Fatura güncellenmeden önce
    
    - Düzenleyen bilgisini güncelle
    - AI analizlerini tetikle
    """
    from flask_login import current_user
    
    if current_user and current_user.is_authenticated:
        target.duzenleyen_id = str(current_user.id)
        target.updated_at = datetime.now()


@event.listens_for(Fatura, 'after_insert')
@event.listens_for(Fatura, 'after_update')
def fatura_after_save(mapper, connection, target):
    """
    Fatura kaydedildikten sonra
    
    - Blinker signal gönder
    - AI analizlerini başlat (async)
    """
    # Signal gönder (diğer modüller dinleyebilir)
    fatura_kaydedildi.send(target, fatura=target)
    
    logger.info(f"✅ Fatura kaydedildi: {target.belge_no}")


@event.listens_for(Fatura, 'after_delete')
def fatura_after_delete(mapper, connection, target):
    """
    Fatura silindikten sonra
    
    - İlişkili kayıtların temizlendiğinden emin ol
    """
    logger.warning(f"⚠️ Fatura silindi: {target.belge_no}")


# ========================================
# CUSTOM EVENT HANDLERS
# ========================================

def fatura_onayla_handler(fatura: Fatura):
    """
    Fatura onaylandığında çalışır
    
    - Stok hareketi oluştur
    - Cari hareketi oluştur
    - Muhasebe kaydı oluştur
    - Signal gönder
    """
    try:
        # 1. AI Analizlerini güncelle
        fatura.ai_analiz_guncelle()
        
        # 2. Durum güncelle
        fatura.durum = 'ONAYLANDI'
        fatura.updated_at = datetime.now()
        
        # 3. Signal gönder (async işlemler için)
        fatura_onaylandi.send(fatura, fatura=fatura)
        
        db.session.commit()
        
        logger.info(f"✅ Fatura onaylandı: {fatura.belge_no}")
        try:
            from app.modules.efatura.tasks import send_efatura_async
            # Celery'nin .delay() metodu işlemi ana iplikten (main thread) koparıp arka plana atar
            send_efatura_async.delay(str(fatura.id), str(fatura.firma_id))
            logger.info(f"📡 Fatura {fatura.belge_no} GİB gönderimi için arka plan kuyruğuna alındı.")
        except Exception as e:
            logger.error(f"Celery görev tetikleme hatası: {str(e)}")
            
        return True, "Fatura başarıyla onaylandı"
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Fatura onaylama hatası: {e}")
        return False, str(e)


def fatura_iptal_et_handler(fatura: Fatura, iptal_nedeni: str = None):
    """
    Fatura iptal edildiğinde çalışır
    
    - Durumu güncelle
    - İlişkili kayıtları tersine çevir
    - Signal gönder
    """
    try:
        from flask_login import current_user
        
        # 1. Durum güncelle
        fatura.iptal_mi = True
        fatura.durum = 'IPTAL'
        fatura.iptal_nedeni = iptal_nedeni
        fatura.iptal_tarihi = datetime.now()
        
        if current_user and current_user.is_authenticated:
            fatura.iptal_eden_id = str(current_user.id)
        
        # 2. Signal gönder (stok/cari/muhasebe tersine çevirme için)
        fatura_iptal_edildi.send(fatura, fatura=fatura, iptal_nedeni=iptal_nedeni)
        
        db.session.commit()
        
        logger.warning(f"⚠️ Fatura iptal edildi: {fatura.belge_no} - {iptal_nedeni}")
        
        return True, "Fatura başarıyla iptal edildi"
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Fatura iptal hatası: {e}")
        return False, str(e)


# ========================================
# SİPARİŞ → FATURA DÖNÜŞÜMÜ (Signal Handler)
# ========================================

@signal('siparis-onaylandi').connect
def siparisten_fatura_olustur(sender, **kwargs):
    """
    Sipariş onaylandığında otomatik fatura oluştur
    
    Args:
        sender: Sipariş instance
        **kwargs: Ekstra parametreler
    """
    siparis = kwargs.get('siparis')
    olusan_fatura_id = kwargs.get('olusan_fatura_id', {})
    
    if not siparis:
        logger.error("Sipariş bilgisi gönderilmedi")
        return
    
    logger.info(f"📡 Sipariş → Fatura dönüşümü başladı: {siparis.belge_no}")
    
    try:
        # 1. Fatura başlık oluştur
        fatura = Fatura()
        fatura.firma_id = siparis.firma_id
        fatura.sube_id = siparis.sube_id
        fatura.donem_id = siparis.donem_id
        fatura.depo_id = siparis.depo_id
        fatura.cari_id = siparis.cari_id
        
        # Belge bilgileri
        fatura.belge_no = f"FTR-{siparis.belge_no}"
        fatura.tarih = datetime.now().date()
        fatura.vade_tarihi = siparis.termin_tarihi or fatura.tarih
        fatura.aciklama = f"Siparişten oluşturuldu: {siparis.belge_no}"
        
        # Finansal
        fatura.doviz_turu = siparis.doviz_turu
        fatura.doviz_kuru = siparis.doviz_kuru
        fatura.fatura_turu = 'SATIS'
        fatura.durum = 'ONAYLANDI'
        
        # Diğer
        fatura.sevk_adresi = siparis.sevk_adresi
        
        if hasattr(siparis, 'fiyat_listesi_id'):
            fatura.fiyat_listesi_id = siparis.fiyat_listesi_id
        
        if hasattr(siparis, 'odeme_plani_id'):
            fatura.odeme_plani_id = siparis.odeme_plani_id
        
        # İlişki
        fatura.kaynak_siparis_id = str(siparis.id)
        
        db.session.add(fatura)
        db.session.flush()
        
        # 2. Kalemleri aktar
        for sip_detay in siparis.detaylar:
            kalem = FaturaKalemi()
            kalem.fatura_id = str(fatura.id)
            kalem.stok_id = str(sip_detay.stok_id)
            kalem.miktar = sip_detay.miktar
            kalem.birim = sip_detay.birim
            kalem.birim_fiyat = sip_detay.birim_fiyat
            kalem.iskonto_orani = sip_detay.iskonto_orani or Decimal('0.00')
            kalem.kdv_orani = sip_detay.kdv_orani or Decimal('20.00')
            kalem.aciklama = sip_detay.aciklama
            
            # Hesaplamalar otomatik yapılacak (before_insert event)
            db.session.add(kalem)
        
        db.session.flush()
        
        # 3. Toplamları aktar
        fatura.ara_toplam = siparis.ara_toplam or Decimal('0.00')
        fatura.iskonto_toplam = siparis.iskonto_toplam or Decimal('0.00')
        fatura.kdv_toplam = siparis.kdv_toplam or Decimal('0.00')
        fatura.genel_toplam = siparis.genel_toplam or Decimal('0.00')
        fatura.dovizli_toplam = siparis.dovizli_toplam or Decimal('0.00')
        
        # 4. Entegrasyonları çalıştır (stok, cari, muhasebe)
        from app.modules.fatura.services import FaturaService
        FaturaService.faturayi_isleme_al(fatura)
        
        db.session.commit()
        
        # 5. ID'yi döndür
        if olusan_fatura_id is not None:
            olusan_fatura_id['id'] = str(fatura.id)
        
        logger.info(f"✅ Fatura oluşturuldu: {fatura.belge_no} (Sipariş: {siparis.belge_no})")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Sipariş → Fatura dönüşüm hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


# ========================================
# TOPLU HESAPLAMA FONKSİYONU
# ========================================

def fatura_toplamlarini_yeniden_hesapla(fatura_id: str):
    """
    Fatura toplamlarını kalemlerden yeniden hesapla
    
    Args:
        fatura_id: Fatura ID (UUID)
    
    Returns:
        bool: Başarı durumu
    """
    try:
        fatura = db.session.get(Fatura, fatura_id)
        
        if not fatura:
            logger.error(f"Fatura bulunamadı: {fatura_id}")
            return False
        
        # Kalemlerden topla
        ara_toplam = Decimal('0.00')
        iskonto_toplam = Decimal('0.00')
        kdv_toplam = Decimal('0.00')
        genel_toplam = Decimal('0.00')
        
        for kalem in fatura.kalemler:
            # Önce kalemi hesapla
            kalem.hesapla()
            
            ara_toplam += kalem.net_tutar
            iskonto_toplam += kalem.iskonto_tutari
            kdv_toplam += kalem.kdv_tutari
            genel_toplam += kalem.satir_toplami
        
        # Faturayı güncelle
        fatura.ara_toplam = ara_toplam
        fatura.iskonto_toplam = iskonto_toplam
        fatura.kdv_toplam = kdv_toplam
        fatura.genel_toplam = genel_toplam
        
        if fatura.doviz_kuru > 0:
            fatura.dovizli_toplam = (
                genel_toplam / fatura.doviz_kuru
            ).quantize(Decimal('0.01'))
        
        db.session.commit()
        
        logger.info(f"✅ Fatura toplamları yeniden hesaplandı: {fatura.belge_no}")
        
        return True
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Toplam hesaplama hatası: {e}")
        return False