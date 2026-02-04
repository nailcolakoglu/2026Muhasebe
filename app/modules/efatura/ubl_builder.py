# app/modules/efatura/ubl_builder.py

from lxml import etree
import uuid
from datetime import datetime
from decimal import Decimal

class UBLBuilder:
    def __init__(self, fatura, satici_firma):
        self.fatura = fatura
        self.alici = fatura.cari
        self.satici = satici_firma
        
        # GİB Standart Namespace Haritası
        self.nsmap = {
            None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "xades": "http://uri.etsi.org/01903/v1.3.2#",
            "udt": "urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2",
            "ccts": "urn:un:unece:uncefact:documentation:2",
            "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
            "qdt": "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypesSchemaModule:2",
            "ubltr": "urn:oasis:names:specification:ubl:schema:xsd:TurkishCustomizationExtensionComponents",
            "ds": "http://www.w3.org/2000/09/xmldsig#",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance"
        }

    def build_xml(self) -> bytes:
        # 1.Root Element (Invoice)
        invoice = etree.Element("Invoice", nsmap=self.nsmap)
        
        # 2.Extension (İmza Alanı - Entegratör Doldurur)
        self._add_extensions(invoice)

        # 3.Başlık Bilgileri
        self._add_cbc(invoice, "UBLVersionID", "2.1")
        self._add_cbc(invoice, "CustomizationID", "TR1.2")
        
        # Senaryo (TICARIFATURA, TEMELFATURA vb.)
        senaryo = self.fatura.e_fatura_senaryo.name if hasattr(self.fatura.e_fatura_senaryo, 'name') else str(self.fatura.e_fatura_senaryo)
        self._add_cbc(invoice, "ProfileID", senaryo)
        
        self._add_cbc(invoice, "ID", self.fatura.belge_no)
        self._add_cbc(invoice, "CopyIndicator", "false")
        
        # ETTN (UUID) Kontrolü
        if not self.fatura.ettn:
            self.fatura.ettn = str(uuid.uuid4())
        self._add_cbc(invoice, "UUID", self.fatura.ettn)
        
        self._add_cbc(invoice, "IssueDate", self.fatura.tarih.strftime("%Y-%m-%d"))
        
        # Fatura Tipi (SATIS, IADE vb.)
        tip = self.fatura.e_fatura_tipi.name if hasattr(self.fatura.e_fatura_tipi, 'name') else str(self.fatura.e_fatura_tipi)
        self._add_cbc(invoice, "InvoiceTypeCode", tip)
        
        # Para Birimi
        curr = self.fatura.doviz_turu.name if hasattr(self.fatura.doviz_turu, 'name') else str(self.fatura.doviz_turu)
        self._add_cbc(invoice, "DocumentCurrencyCode", curr)
        
        # Notlar
        if self.fatura.aciklama:
            self._add_cbc(invoice, "Note", self.fatura.aciklama)

        # 4.Taraflar (Satıcı ve Alıcı)
        self._add_supplier_party(invoice, self.satici)
        self._add_customer_party(invoice, self.alici)

        # 5.Parasal Toplamlar
        self._add_monetary_totals(invoice, curr)

        # 6.Kalemler
        for idx, kalem in enumerate(self.fatura.kalemler):
            self._add_invoice_line(invoice, kalem, idx + 1, curr)

        return etree.tostring(invoice, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    # --- YARDIMCI METODLAR ---

    def _add_cbc(self, parent, tag, value, attrs=None):
        el = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}}{tag}")
        el.text = str(value)
        if attrs:
            for k, v in attrs.items():
                el.set(k, v)
        return el

    def _add_extensions(self, parent):
        """Entegratörün imzalayacağı boş alan"""
        exts = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}}UBLExtensions")
        ext = etree.SubElement(exts, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}}UBLExtension")
        content = etree.SubElement(ext, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}}ExtensionContent")

    def _add_supplier_party(self, parent, firma):
        """Satıcı Bilgileri"""
        sp = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}AccountingSupplierParty")
        party = etree.SubElement(sp, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Party")
        
        # VKN/TCKN
        pi = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PartyIdentification")
        vkn = firma.vergi_no or firma.tc_kimlik_no
        self._add_cbc(pi, "ID", vkn, {'schemeID': 'VKN' if len(vkn or '') == 10 else 'TCKN'})
        
        # Unvan
        pn = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PartyName")
        self._add_cbc(pn, "Name", firma.unvan)
        
        # Vergi Dairesi
        pt = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PartyTaxScheme")
        ts = etree.SubElement(pt, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxScheme")
        self._add_cbc(ts, "Name", firma.vergi_dairesi or "Bilinmiyor")
        
        # Adres (Basitleştirilmiş)
        pa = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PostalAddress")
        self._add_cbc(pa, "CityName", "Merkez") # Gerçek veriden çekilmeli
        self._add_cbc(pa, "CitySubdivisionName", "Merkez")
        country = etree.SubElement(pa, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Country")
        self._add_cbc(country, "Name", "Türkiye")

    def _add_customer_party(self, parent, cari):
        """Alıcı Bilgileri"""
        cp = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}AccountingCustomerParty")
        party = etree.SubElement(cp, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Party")
        
        pi = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PartyIdentification")
        vkn = cari.vergi_no or cari.tc_kimlik_no or "11111111111"
        self._add_cbc(pi, "ID", vkn, {'schemeID': 'VKN' if len(vkn) == 10 else 'TCKN'})
        
        pn = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PartyName")
        self._add_cbc(pn, "Name", cari.unvan)
        
        # Adres
        pa = etree.SubElement(party, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}PostalAddress")
        self._add_cbc(pa, "CityName", cari.sehir or "Bilinmiyor")
        country = etree.SubElement(pa, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Country")
        self._add_cbc(country, "Name", "Türkiye")

    def _add_monetary_totals(self, parent, curr):
        """Vergi ve Genel Toplamlar"""
        
        # A) TAX TOTAL (Vergi Toplamı)
        tax = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxTotal")
        self._add_cbc(tax, "TaxAmount", f"{self.fatura.kdv_toplam:.2f}", {'currencyID': curr})
        
        # KDV Detayı (Subtotal) - Şimdilik KDV Gruplarını (örn %10, %20) tek kalemde varsayıyoruz
        # Gelişmiş versiyonda burası döngüye alınmalı.
        if self.fatura.kdv_toplam > 0:
            subtax = etree.SubElement(tax, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxSubtotal")
            self._add_cbc(subtax, "TaxableAmount", f"{self.fatura.ara_toplam:.2f}", {'currencyID': curr})
            self._add_cbc(subtax, "TaxAmount", f"{self.fatura.kdv_toplam:.2f}", {'currencyID': curr})
            
            cat = etree.SubElement(subtax, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxCategory")
            sch = etree.SubElement(cat, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxScheme")
            self._add_cbc(sch, "Name", "KDV")
            self._add_cbc(sch, "TaxTypeCode", "0015")

        # B) LEGAL MONETARY TOTAL (Genel Toplamlar)
        lmt = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}LegalMonetaryTotal")
        self._add_cbc(lmt, "LineExtensionAmount", f"{self.fatura.ara_toplam:.2f}", {'currencyID': curr}) # Mal Hizmet
        self._add_cbc(lmt, "TaxExclusiveAmount", f"{self.fatura.ara_toplam:.2f}", {'currencyID': curr}) # Vergiler Hariç
        self._add_cbc(lmt, "TaxInclusiveAmount", f"{self.fatura.genel_toplam:.2f}", {'currencyID': curr}) # Vergiler Dahil
        self._add_cbc(lmt, "PayableAmount", f"{self.fatura.genel_toplam:.2f}", {'currencyID': curr}) # Ödenecek

    def _add_invoice_line(self, parent, kalem, line_id, curr):
        """Fatura Satırı"""
        il = etree.SubElement(parent, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}InvoiceLine")
        self._add_cbc(il, "ID", str(line_id))
        
        # Birim (NIU: Adet, KGM: Kilogram vb.) - Modeldeki Enum'a göre maplenmeli
        birim_kod = "NIU" # Varsayılan Adet
        if kalem.birim and hasattr(kalem.birim, 'name'):
            # Basit mapping (Geliştirilebilir)
            birim_map = {'ADET': 'NIU', 'KG': 'KGM', 'LT': 'LTR', 'M': 'MTR'}
            birim_kod = birim_map.get(kalem.birim.name, 'NIU')
            
        self._add_cbc(il, "InvoicedQuantity", f"{kalem.miktar:.2f}", {'unitCode': birim_kod})
        self._add_cbc(il, "LineExtensionAmount", f"{kalem.satir_toplami:.2f}", {'currencyID': curr})
        
        # Vergi (Satır Bazlı)
        tax = etree.SubElement(il, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxTotal")
        self._add_cbc(tax, "TaxAmount", f"{kalem.kdv_tutari:.2f}", {'currencyID': curr})
        
        subtax = etree.SubElement(tax, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxSubtotal")
        self._add_cbc(subtax, "TaxableAmount", f"{kalem.net_tutar:.2f}", {'currencyID': curr})
        self._add_cbc(subtax, "TaxAmount", f"{kalem.kdv_tutari:.2f}", {'currencyID': curr})
        self._add_cbc(subtax, "Percent", f"{kalem.kdv_orani:.0f}")
        
        cat = etree.SubElement(subtax, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxCategory")
        sch = etree.SubElement(cat, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}TaxScheme")
        self._add_cbc(sch, "Name", "KDV")
        self._add_cbc(sch, "TaxTypeCode", "0015")

        # Ürün Adı
        item = etree.SubElement(il, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Item")
        self._add_cbc(item, "Name", kalem.stok.ad)
        
        # Fiyat
        price = etree.SubElement(il, f"{{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}}Price")
        self._add_cbc(price, "PriceAmount", f"{kalem.birim_fiyat:.2f}", {'currencyID': curr})