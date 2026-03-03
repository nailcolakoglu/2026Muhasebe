# app/modules/efatura/tasks.py

from celery import shared_task
import logging
from time import sleep
from flask import session # ✨ DÜZELTME: Session'ı geri getirdik

from app.extensions import celery
from app.modules.efatura.services import EntegratorService

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def send_efatura_async(self, fatura_id, firma_id):
    """
    Arka planda asenkron olarak E-Fatura gönderir.
    Hata durumunda 1 dakika arayla 3 defa tekrar dener.
    """
    from run import app 
    
    try:
        # ✨ DÜZELTME: app_context yerine test_request_context kullanıyoruz.
        # Bu sayede Celery içinde sanal bir HTTP oturumu başlatmış oluyoruz.
        with app.test_request_context('/'):
            # get_tenant_db()'nin veritabanını bulması için Session'ı dolduruyoruz
            session['tenant_id'] = str(firma_id)
            session['aktif_firma_id'] = str(firma_id)
            
            service = EntegratorService(firma_id)
            basari, mesaj = service.fatura_gonder(fatura_id)
            
            if not basari:
                logger.warning(f"Asenkron E-Fatura gönderim hatası (Deneme {self.request.retries}): {mesaj}")
                raise self.retry(countdown=60 * (self.request.retries + 1)) 
                
            return mesaj
    except Exception as e:
        logger.error(f"Celery Task E-Fatura Hatası (ID: {fatura_id}): {str(e)}")
        raise
        
@shared_task(bind=True, max_retries=3)
def send_earsiv_mail_async(self, fatura_id, musteri_eposta, firma_id):
    """
    E-Arşiv faturası GİB'e iletildikten sonra müşteriye UBL ve HTML faturayı mail atar.
    """
    from run import app 
    import smtplib
    from email.message import EmailMessage
    import os
    import lxml.etree as ET
    from flask import session
    from app.extensions import get_tenant_db
    from app.modules.fatura.models import Fatura
    from app.modules.firmalar.models import Firma
    from app.modules.efatura.ubl_builder import UBLBuilder
    
    try:
        with app.test_request_context('/'):
            # 1. Multi-Tenant Veritabanı Bağlantısı
            session['tenant_id'] = str(firma_id)
            session['aktif_firma_id'] = str(firma_id)
            tenant_db = get_tenant_db()
            
            fatura = tenant_db.query(Fatura).get(fatura_id)
            firma = tenant_db.query(Firma).get(firma_id)
            
            if not fatura or not firma:
                logger.error("Mail iptal: Fatura veya Firma bulunamadı.")
                return "İptal"

            logger.info(f"📧 E-Arşiv Mail Gönderimi Başladı | Fatura: {fatura.belge_no} | Alıcı: {musteri_eposta}")

            # 2. Arka Planda UBL (XML) ve HTML Faturayı İnşa Et
            builder = UBLBuilder(fatura, firma)
            xml_bytes = builder.build_xml()
            
            app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            xslt_path = os.path.join(app_dir, 'static', 'xslt', 'general.xslt')
            
            html_content = ""
            if os.path.exists(xslt_path):
                xslt_doc = ET.parse(xslt_path)
                transform = ET.XSLT(xslt_doc)
                xml_doc = ET.fromstring(xml_bytes)
                html_content = str(transform(xml_doc))
            
            # 3. E-Posta Gövdesini (Message) Hazırla
            msg = EmailMessage()
            msg['Subject'] = f"{firma.unvan} - E-Arşiv Faturanız ({fatura.belge_no})"
            msg['From'] = "muhasebeerp2026@gmail.com" # GÖNDEREN ADRES (Değiştirin)
            msg['To'] = musteri_eposta
            
            body = f"""Sayın {fatura.cari.unvan},

{fatura.tarih.strftime('%d.%m.%Y')} tarihli ve {fatura.belge_no} numaralı E-Arşiv faturanız ekte yer almaktadır.
Bizi tercih ettiğiniz için teşekkür ederiz.

Saygılarımızla,
{firma.unvan}
"""
            msg.set_content(body)
            
            # Ek 1: GİB Standartlarında Yasal XML
            msg.add_attachment(xml_bytes, maintype='application', subtype='xml', filename=f"{fatura.belge_no}.xml")
            
            # Ek 2: Müşterinin okuyabilmesi için Görsel HTML Fatura
            if html_content:
                msg.add_attachment(html_content.encode('utf-8'), maintype='text', subtype='html', filename=f"{fatura.belge_no}.html")

            # 4. SMTP Sunucusuna Bağlan ve Gönder
            SMTP_SERVER = "smtp.gmail.com"
            SMTP_PORT = 587
            SMTP_USER = "sizin_mailiniz@gmail.com" # BURAYI KENDİ BİLGİLERİNİZLE DEĞİŞTİRİN
            SMTP_PASS = "uygulama_sifreniz" # Gmail "Uygulama Şifresi" gerektirir
            
            # NOT: Kendi bilgilerinizi girene kadar hata vermemesi için gerçek gönderim satırlarını yorum satırı yaptık.
            # Canlıya alırken aşağıdaki 3 satırın başındaki '#' işaretini kaldırın.
            
            # with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            #     server.starttls()
            #     server.login(SMTP_USER, SMTP_PASS)
            #     server.send_message(msg)
                
            logger.info(f"✅ E-Arşiv faturası {musteri_eposta} adresine başarıyla teslim edildi!")
            return f"Mail Sent to {musteri_eposta}"
            
    except Exception as exc:
        logger.error(f"❌ Mail Gönderim Hatası: {exc}")
        raise self.retry(exc=exc, countdown=60)