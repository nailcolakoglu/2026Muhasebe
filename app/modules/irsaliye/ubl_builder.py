# app/modules/irsaliye/ubl_builder.py (Geliştirilmiş)

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
        }

    def build_xml(self):
        root = etree.Element("DespatchAdvice", nsmap=self.nsmap)
        
        # Başlık Bilgileri
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

        # Lojistik & Araç Bilgileri
        shipment = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Shipment")
        self._add_cbc(shipment, "ID", "1")
        
        if self.irsaliye.plaka_arac:
            thu = etree.SubElement(shipment, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TransportHandlingUnit")
            te = etree.SubElement(thu, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TransportEquipment")
            self._add_cbc(te, "ID", self.irsaliye.plaka_arac)
            
            # Şoför Bilgisi
            person = etree.SubElement(shipment, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}ShipmentStage")
            transport_means = etree.SubElement(person, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TransportMeans")
            road_transport = etree.SubElement(transport_means, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}RoadTransport")
            self._add_cbc(road_transport, "LicensePlateID", self.irsaliye.plaka_arac)
            
            driver = etree.SubElement(person, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}DriverPerson")
            self._add_cbc(driver, "FirstName", self.irsaliye.sofor_ad)
            self._add_cbc(driver, "FamilyName", self.irsaliye.sofor_soyad)
            self._add_cbc(driver, "ID", self.irsaliye.sofor_tc)

        # Kalemler
        for idx, kalem in enumerate(self.irsaliye.kalemler):
            line = etree.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}DespatchLine")
            self._add_cbc(line, "ID", str(idx+1))
            self._add_cbc(line, "DeliveredQuantity", str(kalem.miktar), attrs={'unitCode': 'NIU'})
            
            item = etree.SubElement(line, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item")
            self._add_cbc(item, "Name", kalem.stok.ad)

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _add_cbc(self, parent, tag, text, attrs=None):
        el = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}}{tag}")
        el.text = str(text)
        if attrs:
            for k,v in attrs.items(): el.set(k, v)

    def _add_party(self, parent, tag, party_obj):
        party_container = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Party")
        # Basitleştirilmiş Party yapısı
        party_name = etree.SubElement(party_container, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName")
        self._add_cbc(party_name, "Name", getattr(party_obj, 'unvan', 'Bilinmeyen Firma'))