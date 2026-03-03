# app/modules/efatura/providers/uyumsoft_provider.py

import logging
import base64
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.auth import HTTPBasicAuth
from .base import BaseProvider

logger = logging.getLogger(__name__)

class UyumsoftProvider(BaseProvider):
    """
    Uyumsoft E-Fatura SOAP (WCF) Entegrasyonu
    Gereksinim: pip install zeep
    """
    def __init__(self, username, password, api_url):
        super().__init__(username, password, api_url)
        
        try:
            # Uyumsoft Basic Authentication kullanır
            session = Session()
            session.auth = HTTPBasicAuth(self.username, self.password)
            
            # WSDL adresi genelde: https://efatura.uyumsoft.com.tr/Services/Integration?wsdl
            wsdl_url = f"{self.api_url}?wsdl" if not self.api_url.endswith("?wsdl") else self.api_url
            
            self.client = Client(wsdl_url, transport=Transport(session=session))
        except Exception as e:
            logger.error(f"Uyumsoft WSDL Bağlantı Hatası: {str(e)}", exc_info=True)
            raise ValueError("Entegratör servisine bağlanılamadı. API URL'sini kontrol edin.")

    def connect(self):
        """Bağlantı test metodu. Uyumsoft'ta system time okuyarak test edebiliriz."""
        # Sunucudaki tüm geçerli komutları konsola yazdırır!
        print("Uyumsoft Geçerli Komutlar:", dir(self.client.service)) 
        #return True
        try:
            # Sadece bağlantıyı sınamak için küçük bir çağrı
            result = self.client.service.WhoAmI() 
            return bool(result)
        except Exception as e:
            logger.error(f"Uyumsoft Connect Error: {str(e)}")
            return False

    def is_euser(self, vkn):
        """
        Mükellef sorgulama. GİB kayıtlı kullanıcılar listesinde arar.
        """
        try:
            # Uyumsoft QueryUser metodu
            response = self.client.service.QueryUsers(vknTckn=vkn)
            
            if response and len(response) > 0:
                # Birden fazla posta kutusu (PK) olabilir, genelde ilk sıradakini "default" alırız
                ilk_pk = response[0].Alias
                return True, ilk_pk
            return False, None
            
        except Exception as e:
            logger.error(f"Uyumsoft Mükellef Sorgulama Hatası ({vkn}): {str(e)}")
            return False, None

    def send_invoice(self, ubl_xml, ettn, alici_vkn, alici_alias):
        """
        UBL-TR faturasını Uyumsoft'a gönderir (SendDocument)
        Not: UBL verisi Uyumsoft'a base64 veya direkt zip/byte olarak iletilir.
        """
        try:
            # XML içeriğini byte dizisi veya base64'e çeviriyoruz
            if isinstance(ubl_xml, str):
                ubl_xml = ubl_xml.encode('utf-8')
                
            # Uyumsoft Document nesnesini hazırlıyoruz
            # WSDL yapısına göre bu parametreler şekillenir
            document = {
                'DocumentData': ubl_xml, # Zeep byte array'i otomatik ele alır
                'DocumentType': 'Invoice',
                'MimeType': 'application/xml',
                'TargetAlias': alici_alias,
                'TargetTcknVkn': alici_vkn
            }

            # Gerçek Gönderim Çağrısı
            # Geriye genelde (IsSucceeded, Message, Id) içeren bir Result objesi döner
            response = self.client.service.SendInvoice(invoices=[document])
            
            # Yanıt analizi (WSDL şemasına göre objeye erişim)
            if response.IsSucceded:
                # Uyumsoft'un oluşturduğu benzersiz entegratör ID'si (ref_no)
                ref_no = response.Responses[0].Id 
                logger.info(f"Uyumsoft: {ettn} başarıyla gönderildi. Ref: {ref_no}")
                return True, ref_no
            else:
                hata_mesaji = response.Message or "Bilinmeyen Entegratör Hatası"
                logger.error(f"Uyumsoft Ret: {hata_mesaji}")
                return False, hata_mesaji
                
        except Exception as e:
            logger.error(f"Uyumsoft Gönderim Hatası (ETTN: {ettn}): {str(e)}", exc_info=True)
            return False, str(e)

    def check_status(self, ettn):
        """
        Faturanın GİB'deki güncel durumunu sorgular.
        """
        try:
            # 👇 DÜZELTME: QueryDocumentStatus yerine QueryOutboxInvoiceStatus (veya QueryInvoiceStatus)
            # Parametre adı da documentIds yerine invoiceIds olur.
            response = self.client.service.QueryOutboxInvoiceStatus(invoiceIds=[ettn])
            
            if response and len(response) > 0:
                doc_status = response[0]
                gib_kod = doc_status.GibStatusCode
                gib_mesaj = doc_status.GibStatusDescription
                return gib_kod, gib_mesaj
                
            return None, "Kayıt bulunamadı"
            
        except Exception as e:
            logger.error(f"Uyumsoft Durum Sorgulama Hatası: {str(e)}")
            return None, str(e)