from lxml import etree
from datetime import datetime
from app.extensions import db
from app.modules.firmalar.models import Firma, Donem
from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay

class EDefterBuilder:
    def __init__(self, firma_id, donem_id, baslangic, bitis):
        self.firma = Firma.query.get(firma_id)
        self.donem = Donem.query.get(donem_id)
        self.baslangic = baslangic
        self.bitis = bitis
        
        # GİB Standart Namespace Tanımları (Ezberlemeye gerek yok, standarttır)
        self.nsmap = {
            "xbrli": "http://www.xbrl.org/2003/instance",
            "gl-cor": "http://www.xbrl.org/int/gl/cor/2006-10-25",
            "gl-bus": "http://www.xbrl.org/int/gl/bus/2006-10-25",
            "gl-plt": "http://www.xbrl.org/int/gl/plt/2006-10-25",
            "nde": "http://www.gib.gov.tr/vedop/e-defter",
            None: "http://www.xbrl.org/2003/instance" # Default namespace
        }

    def yevmiye_xml_olustur(self):
        """Yevmiye Defteri (xbrl) XML'ini oluşturur."""
        
        # 1.Kök Element (xbrli:xbrl)
        root = etree.Element(f"{{{self.nsmap['xbrli']}}}xbrl", nsmap=self.nsmap)
        
        # 2.Firma Bilgileri (Header)
        self._header_ekle(root)
        
        # 3.Fişleri Çek (Sadece KESİNLEŞMİŞ olanlar!)
        fisler = MuhasebeFisi.query.filter(
            MuhasebeFisi.firma_id == self.firma.id,
            MuhasebeFisi.tarih >= self.baslangic,
            MuhasebeFisi.tarih <= self.bitis,
            MuhasebeFisi.resmi_defter_basildi == True # Sadece kilitli fişler
        ).order_by(MuhasebeFisi.yevmiye_madde_no).all()

        if not fisler:
            raise Exception("Bu tarih aralığında kesinleşmiş (numara verilmiş) fiş bulunamadı!")

        # 4.Hareketleri Dön (AccountingEntries)
        entries_root = etree.SubElement(root, f"{{{self.nsmap['gl-cor']}}}accountingEntries")
        
        for fis in fisler:
            self._fis_ekle(entries_root, fis)

        # XML'i String Olarak Döndür
        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _header_ekle(self, root):
        """Firma ve Müşavir bilgilerini ekler."""
        # GİB Entity Bilgileri
        entity_info = etree.SubElement(root, f"{{{self.nsmap['gl-bus']}}}entityInformation")
        
        # Firma Kimliği
        identifier = etree.SubElement(entity_info, f"{{{self.nsmap['gl-bus']}}}organizationIdentifier")
        identifier.text = self.firma.vergi_no or self.firma.tc_kimlik_no
        
        # Unvan
        org_desc = etree.SubElement(entity_info, f"{{{self.nsmap['gl-bus']}}}organizationDescription")
        org_desc.text = self.firma.unvan

        # Müşavir Bilgileri (Varsa)
        if self.firma.sm_tc_vkn:
            contact = etree.SubElement(entity_info, f"{{{self.nsmap['gl-bus']}}}contactInformation")
            contact_name = etree.SubElement(contact, f"{{{self.nsmap['gl-bus']}}}contactName")
            contact_name.text = self.firma.sm_unvan

    def _fis_ekle(self, parent, fis):
        """Bir fişi (EntryHeader) ve detaylarını XML'e ekler."""
        entry = etree.SubElement(parent, f"{{{self.nsmap['gl-cor']}}}entryHeader")
        
        # Yevmiye Tarihi
        posted_date = etree.SubElement(entry, f"{{{self.nsmap['gl-cor']}}}postedDate")
        posted_date.text = fis.tarih.strftime('%Y-%m-%d')
        
        # Yevmiye Numarası
        entry_num = etree.SubElement(entry, f"{{{self.nsmap['gl-cor']}}}entryNumber")
        entry_num.text = str(fis.yevmiye_madde_no)
        
        # Fiş Açıklaması
        desc = etree.SubElement(entry, f"{{{self.nsmap['gl-cor']}}}entryComment")
        desc.text = fis.aciklama or ""
        
        # Detaylar (Borç/Alacak Satırları)
        for detay in fis.detaylar:
            self._detay_ekle(entry, detay, fis)

    def _detay_ekle(self, entry_header, detay, fis):
        """Yevmiye satırını (EntryDetail) ekler."""
        item = etree.SubElement(entry_header, f"{{{self.nsmap['gl-cor']}}}entryDetail")
        
        # Satır Numarası
        line_num = etree.SubElement(item, f"{{{self.nsmap['gl-cor']}}}lineNumber")
        line_num.text = str(detay.id) # Veya sıralı bir sayaç
        
        # Hesap Bilgileri (Account)
        account = etree.SubElement(item, f"{{{self.nsmap['gl-cor']}}}account")
        main_id = etree.SubElement(account, f"{{{self.nsmap['gl-cor']}}}accountMainID")
        main_id.text = detay.hesap.kod
        
        ac_desc = etree.SubElement(account, f"{{{self.nsmap['gl-cor']}}}accountMainDescription")
        ac_desc.text = detay.hesap.ad
        
        # Tutar (Amount)
        amount = etree.SubElement(item, f"{{{self.nsmap['gl-cor']}}}amount")
        amount.set("decimals", "2")
        amount.set("unitRef", "TRY")
        
        # Borç mu Alacak mı?
        if detay.borc > 0:
            amount.text = f"{detay.borc:.2f}"
            dc = etree.SubElement(item, f"{{{self.nsmap['gl-cor']}}}debitCreditCode")
            dc.text = "D" # Debit (Borç)
        else:
            amount.text = f"{detay.alacak:.2f}"
            dc = etree.SubElement(item, f"{{{self.nsmap['gl-cor']}}}debitCreditCode")
            dc.text = "C" # Credit (Alacak)
            
        # Belge Detayları (DocumentInfo) - GİB İçin En Önemli Kısım!
        if detay.belge_no:
            doc_info = etree.SubElement(item, f"{{{self.nsmap['gl-cor']}}}documentInfo")
            
            # Belge Tipi (invoice, receipt, check vs.)
            doc_type = etree.SubElement(doc_info, f"{{{self.nsmap['gl-cor']}}}documentType")
            doc_type.text = detay.belge_turu or "other"
            
            # Belge Numarası
            doc_num = etree.SubElement(doc_info, f"{{{self.nsmap['gl-cor']}}}documentNumber")
            doc_num.text = detay.belge_no
            
            # Belge Tarihi
            if detay.belge_tarihi:
                doc_date = etree.SubElement(doc_info, f"{{{self.nsmap['gl-cor']}}}documentDate")
                doc_date.text = detay.belge_tarihi.strftime('%Y-%m-%d')