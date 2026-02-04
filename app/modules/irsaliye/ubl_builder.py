from lxml import etree
import uuid

class IrsaliyeUBLBuilder:
    def __init__(self, irsaliye, gonderen_firma):
        self.irsaliye = irsaliye
        self.gonderen = gonderen_firma
        self.alici = irsaliye.cari
        
        self.nsmap = {
            None: "urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            # ...diğer standart namespaceler (fatura modülündekiyle aynı) ...
        }

    def build_xml(self):
        root = etree.Element("DespatchAdvice", nsmap=self.nsmap)
        
        # Standart Başlıklar
        self._add_cbc(root, "UBLVersionID", "2.1")
        self._add_cbc(root, "CustomizationID", "TR1.2")
        self._add_cbc(root, "ProfileID", "TEMELIRSALIYE")
        self._add_cbc(root, "ID", self.irsaliye.belge_no)
        self._add_cbc(root, "UUID", self.irsaliye.ettn)
        self._add_cbc(root, "IssueDate", self.irsaliye.tarih.strftime('%Y-%m-%d'))
        self._add_cbc(root, "IssueTime", self.irsaliye.saat.strftime('%H:%M:%S'))
        self._add_cbc(root, "DespatchAdviceTypeCode", "SEVK")

        # Taraflar
        self._add_party(root, "DespatchSupplierParty", self.gonderen)
        self._add_party(root, "DeliveryCustomerParty", self.alici)

        # SEVKİYAT BİLGİLERİ (Shipment) - İrsaliyenin kalbi burasıdır
        shipment = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Shipment")
        self._add_cbc(shipment, "ID", "1")
        
        # Şoför ve Plaka
        if self.irsaliye.plaka_arac:
            transport = etree.SubElement(shipment, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TransportHandlingUnit")
            equip = etree.SubElement(transport, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TransportEquipment")
            self._add_cbc(equip, "ID", self.irsaliye.plaka_arac)
        
        # Kalemler
        for idx, kalem in enumerate(self.irsaliye.kalemler):
            line = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}DespatchLine")
            self._add_cbc(line, "ID", str(idx+1))
            self._add_cbc(line, "DeliveredQuantity", str(kalem.miktar), attrs={'unitCode': 'NIU'}) # NIU=Adet
            
            item = etree.SubElement(line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item")
            self._add_cbc(item, "Name", kalem.stok.ad)

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _add_cbc(self, parent, tag, text, attrs=None):
        el = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}}{tag}")
        el.text = str(text)
        if attrs:
            for k,v in attrs.items(): el.set(k, v)

    def _add_party(self, parent, tag, firma_obj):
        # ...(Fatura modülündeki _add_supplier_party mantığıyla aynı) ...
        pass