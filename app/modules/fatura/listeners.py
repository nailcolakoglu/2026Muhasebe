# app/modules/fatura/listeners.py

"""
Fatura Modülü Event Listeners
Blinker Signals ile Loose Coupling
"""

import logging
from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.enums import FaturaTuru, FaturaDurumu
from .services import FaturaService

logger = logging.getLogger(__name__)


def siparisten_fatura_olustur(sender, siparis, olusan_fatura_id, **kwargs):
    """
    Sipariş -> Fatura Dönüşümü (Signal Handler)
    
    Args:
        sender: Signal gönderen obje
        siparis: Kaynak Sipariş instance'ı
        olusan_fatura_id: Oluşan fatura ID'sini doldurmak için dict (mutable)
        **kwargs: Ekstra parametreler
    """
    
    logger.info(f"📡 SİNYAL: Sipariş {siparis.belge_no} faturaya aktarılıyor...")
    
    try:
        # 1.FATURA BAŞLIK OLUŞTUR
        yeni_fatura = Fatura()
        yeni_fatura.firma_id = siparis.firma_id
        yeni_fatura.sube_id = siparis.sube_id
        yeni_fatura.donem_id = siparis.donem_id
        yeni_fatura.depo_id = siparis.depo_id
        yeni_fatura.cari_id = siparis.cari_id
        yeni_fatura.belge_no = f"FTR-{siparis.belge_no}"
        yeni_fatura.tarih = datetime.now().date()
        yeni_fatura.aciklama = f"Siparişten:  {siparis.belge_no}"
        yeni_fatura.doviz_turu = siparis.doviz_turu
        yeni_fatura.doviz_kuru = siparis.doviz_kuru
        yeni_fatura.fatura_turu = FaturaTuru.SATIS.value
        yeni_fatura.durum = FaturaDurumu.ONAYLANDI.value
        yeni_fatura.sevk_adresi = siparis.sevk_adresi
        yeni_fatura.odeme_plani_id = siparis.odeme_plani_id
        
        # Eğer sipariş modelinde 'fiyat_listesi_id' varsa aktar
        if hasattr(siparis, 'fiyat_listesi_id'):
            yeni_fatura.fiyat_listesi_id = siparis.fiyat_listesi_id
        
        # Eğer modelinizde 'kaynak_siparis_id' varsa bağla
        if hasattr(yeni_fatura, 'kaynak_siparis_id'):
            yeni_fatura.kaynak_siparis_id = siparis.id
        
        db.session.add(yeni_fatura)
        db.session.flush()  # ID'yi al
        
        # 2.DETAYLARI AKTAR
        for satir in siparis.detaylar:
            yeni_kalem = FaturaKalemi()
            yeni_kalem.fatura_id = yeni_fatura.id
            yeni_kalem.stok_id = satir.stok_id
            yeni_kalem.miktar = satir.miktar
            yeni_kalem.birim = satir.birim
            yeni_kalem.birim_fiyat = satir.birim_fiyat
            yeni_kalem.iskonto_orani = satir.iskonto_orani or Decimal('0.00')
            yeni_kalem.iskonto_tutari = satir.iskonto_tutari or Decimal('0.00')
            yeni_kalem.kdv_orani = satir.kdv_orani or Decimal('20.00')
            yeni_kalem.kdv_tutari = satir.kdv_tutari or Decimal('0.00')
            yeni_kalem.net_tutar = satir.net_tutar or Decimal('0.00')
            yeni_kalem.satir_toplami = satir.satir_toplami or Decimal('0.00')
            yeni_kalem.aciklama = satir.aciklama
            
            db.session.add(yeni_kalem)
        
        # 3.TOPLAMLAR (Siparişteki toplamları direkt aktar)
        yeni_fatura.ara_toplam = siparis.ara_toplam or Decimal('0.00')
        yeni_fatura.iskonto_toplam = siparis.iskonto_toplam or Decimal('0.00')
        yeni_fatura.kdv_toplam = siparis.kdv_toplam or Decimal('0.00')
        yeni_fatura.genel_toplam = siparis.genel_toplam or Decimal('0.00')
        yeni_fatura.dovizli_toplam = siparis.dovizli_toplam or Decimal('0.00')
        
        db.session.flush()
        
        # 4.ENTEGRASYON MOTORUNU ÇALIŞTIR
        # (Stok düşümü, cari hareketi, muhasebe kaydı)
        FaturaService.faturayi_isleme_al(yeni_fatura)
        
        # 5.ID'yi Geri Döndür (Mutable Dict ile)
        if olusan_fatura_id is not None:
            olusan_fatura_id['olusan_fatura_id'] = yeni_fatura.id
        
        logger.info(f"✅ Fatura (ID: {yeni_fatura.id}) başarıyla oluşturuldu ve işlendi.")
        
    except Exception as e:
        logger.exception(f"❌ Sipariş -> Fatura dönüşüm hatası: {e}")
        raise e  # Transaction rollback için hata fırlat