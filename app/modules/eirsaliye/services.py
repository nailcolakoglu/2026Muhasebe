# app/modules/eirsaliye/services.py

import logging
from app.extensions import get_tenant_db
from app.modules.efatura.models import EntegratorAyarlari 
from app.modules.irsaliye.models import Irsaliye
from app.modules.firmalar.models import Firma
from app.modules.efatura.providers.mock_provider import MockProvider
from app.modules.irsaliye.ubl_builder import IrsaliyeUBLBuilder

logger = logging.getLogger(__name__)

class EIrsaliyeService:
    def __init__(self, firma_id):
        self.tenant_db = get_tenant_db()
        self.firma_id = firma_id
        
        self.ayarlar = self.tenant_db.query(EntegratorAyarlari).filter_by(firma_id=firma_id, aktif=True).first()
        if not self.ayarlar:
            self.provider = MockProvider("test", "test", "http://mock.api")
            return

        if self.ayarlar.provider == 'MOCK':
            self.provider = MockProvider(self.ayarlar.username, self.ayarlar.password, self.ayarlar.api_url)
        elif self.ayarlar.provider == 'UYUMSOFT':
            from app.modules.efatura.providers.uyumsoft_provider import UyumsoftProvider
            self.provider = UyumsoftProvider(self.ayarlar.username, self.ayarlar.password, self.ayarlar.api_url)
        else:
            raise ValueError(f"Tanımsız sağlayıcı: {self.ayarlar.provider}")

    def irsaliye_gonder(self, irsaliye_id):
        irsaliye = self.tenant_db.query(Irsaliye).get(irsaliye_id)
        if not irsaliye: return False, "İrsaliye bulunamadı."
        if irsaliye.gib_durum_kodu == 1300: return False, "Zaten GİB'e iletilmiş!"
        if not irsaliye.plaka_arac or not irsaliye.sofor_tc: return False, "Araç plakası ve Şoför TC kimlik numarası zorunludur!"

        try:
            satici = self.tenant_db.query(Firma).get(irsaliye.firma_id)
            cari_vkn = irsaliye.cari.vergi_no or irsaliye.cari.tc_kimlik_no or '11111111111'
            
            # E-İrsaliye için genelde posta kutusu alias'ı "urn:mail:defaultgb@gib.gov.tr" türevidir.
            is_euser, pk_alias = self.provider.is_euser(cari_vkn)
            pk_alias = pk_alias if pk_alias else "urn:mail:defaultpk@gib.gov.tr"

            builder = IrsaliyeUBLBuilder(irsaliye, satici)
            xml_content = builder.build_xml()
            
            basarili, ref_no = self.provider.send_invoice(xml_content, irsaliye.ettn, cari_vkn, pk_alias)
            
            if basarili:
                irsaliye.gib_durum_kodu = 100
                irsaliye.durum = "GÖNDERİLDİ"
                self.tenant_db.commit()
                return True, f"E-İrsaliye kuyruğa alındı. Ref: {ref_no}"
            return False, f"Entegratör Hatası: {ref_no}"
        except Exception as e:
            self.tenant_db.rollback()
            logger.error(f"E-İrsaliye Gönderim Hatası: {str(e)}", exc_info=True)
            return False, str(e)