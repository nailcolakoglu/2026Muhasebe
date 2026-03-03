# app/modules/cari/listeners.py

import logging
from app.signals import (
    kasa_hareket_olusturuldu, 
    banka_hareket_olusturuldu,
    cek_karsiliksiz_cikti,
    fatura_onaylandi
)
from app.extensions import get_tenant_db
from app.modules.cari.models import CariHesap

logger = logging.getLogger(__name__)

@kasa_hareket_olusturuldu.connect_via(None)
def on_kasa_hareket(sender, **kwargs):
    """
    Kasa hareketi oluştuğunda tetiklenir.
    NOT: Finansal kayıt işlemi (CariHareket) KasaService içinde zaten yapılmıştır!
    Burada sadece yan etkileri (Örn: Müşteriye teşekkür SMS'i) yönetiyoruz.
    """
    hareket = sender
    if hareket.cari_id:
        logger.info(f"🔔 Cari Bildirimi: {hareket.belge_no} nolu Kasa işlemi başarıyla alındı.")
        # İleride eklenebilir: send_sms(cari.telefon, "Ödemeniz alınmıştır. Teşekkürler.")

@banka_hareket_olusturuldu.connect_via(None)
def on_banka_hareket(sender, **kwargs):
    hareket = sender
    if hareket.cari_id:
        logger.info(f"🔔 Cari Bildirimi: {hareket.belge_no} nolu Banka işlemi başarıyla alındı.")

@cek_karsiliksiz_cikti.connect_via(None)
def on_cek_karsiliksiz(sender, cari, **kwargs):
    """
    Kritik Operasyon: Müşterinin çeki karşılıksız çıkarsa, 
    Sinyal burayı tetikler ve müşterinin AI Risk Skoru anında düşürülür!
    """
    if cari:
        try:
            tenant_db = get_tenant_db()
            cari_obj = tenant_db.get(CariHesap, str(cari.id))
            if cari_obj:
                # Risk skorunu 30 puan ceza keserek düşür
                eski_skor = cari_obj.risk_skoru or 100
                yeni_skor = max(0, eski_skor - 30)
                cari_obj.risk_skoru = yeni_skor
                cari_obj.risk_durumu = 'YUKSEK_RISK'
                
                tenant_db.commit()
                logger.warning(
                    f"🚨 AI RİSK UYARISI: {cari_obj.unvan} çeki karşılıksız çıktı! "
                    f"Güvenilirlik Skoru: {eski_skor} -> {yeni_skor}"
                )
        except Exception as e:
            logger.error(f"❌ Risk skoru güncellenirken hata: {e}")

@fatura_onaylandi.connect_via(None)
def on_fatura_onaylandi(sender, **kwargs):
    """Fatura onaylanınca müşterinin Son İşlem Tarihini günceller"""
    fatura = sender
    if fatura.cari_id:
        try:
            tenant_db = get_tenant_db()
            cari = tenant_db.get(CariHesap, str(fatura.cari_id))
            if cari:
                cari.son_siparis_tarihi = fatura.tarih
                tenant_db.commit()
        except Exception:
            pass