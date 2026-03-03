<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:n1="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">

    <xsl:output method="html" encoding="UTF-8" indent="yes"/>

    <xsl:template match="/n1:Invoice">
        <html>
        <head>
            <title>E-Fatura / E-Arşiv - <xsl:value-of select="cbc:ID"/></title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"/>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #e9ecef; padding: 40px 0; }
                .invoice-box { background: #fff; max-width: 900px; margin: auto; padding: 40px; border: 1px solid #ddd; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); border-radius: 10px; }
                .header-line { border-bottom: 3px solid #0d6efd; margin-bottom: 30px; padding-bottom: 20px; }
                .invoice-title { font-size: 2.5rem; color: #0d6efd; font-weight: 800; letter-spacing: -1px; }
                .section-title { font-size: 0.9rem; color: #6c757d; font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 15px; }
                .table th { background-color: #f8f9fa; color: #495057; font-weight: 600; }
                .totals-box { background-color: #f8f9fa; border-radius: 8px; padding: 20px; }
            </style>
        </head>
        <body>
            <div class="invoice-box">
                <div class="row header-line align-items-center">
                    <div class="col-sm-6">
                        <h2 class="invoice-title">
                            <xsl:choose>
                                <xsl:when test="cbc:ProfileID = 'EARSIVFATURA'">E-ARŞİV FATURA</xsl:when>
                                <xsl:otherwise>E-FATURA</xsl:otherwise>
                            </xsl:choose>
                        </h2>
                    </div>
                    <div class="col-sm-6 text-end">
                        <p class="mb-1"><strong>Fatura No: </strong> <span class="fs-5 text-dark"><xsl:value-of select="cbc:ID"/></span></p>
                        <p class="mb-1"><strong>Tarih: </strong> <xsl:value-of select="cbc:IssueDate"/></p>
                        <p class="mb-0 text-muted small"><strong>ETTN: </strong> <xsl:value-of select="cbc:UUID"/></p>
                    </div>
                </div>

                <div class="row mb-5">
                    <div class="col-sm-6">
                        <div class="section-title">SATICı (GÖNDEREN)</div>
                        <h5 class="fw-bold"><xsl:value-of select="cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name"/></h5>
                        <p class="mb-0"><strong>VKN/TCKN:</strong> <xsl:value-of select="cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID"/></p>
                        <p class="mb-0"><strong>Vergi Dairesi:</strong> <xsl:value-of select="cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cac:TaxScheme/cbc:Name"/></p>
                        <p class="mb-0 text-muted"><xsl:value-of select="cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:CityName"/> / <xsl:value-of select="cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cac:Country/cbc:Name"/></p>
                    </div>
                    <div class="col-sm-6 text-end">
                        <div class="section-title">ALICI (MÜŞTERİ)</div>
                        <h5 class="fw-bold"><xsl:value-of select="cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name"/></h5>
                        <p class="mb-0"><strong>VKN/TCKN:</strong> <xsl:value-of select="cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID"/></p>
                        <p class="mb-0 text-muted"><xsl:value-of select="cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cbc:CityName"/> / <xsl:value-of select="cac:AccountingCustomerParty/cac:Party/cac:PostalAddress/cac:Country/cbc:Name"/></p>
                    </div>
                </div>

                <table class="table table-bordered mb-5">
                    <thead>
                        <tr>
                            <th class="text-center" width="5%">#</th>
                            <th width="45%">Mal / Hizmet Cinsi</th>
                            <th class="text-center" width="10%">Miktar</th>
                            <th class="text-end" width="15%">Birim Fiyat</th>
                            <th class="text-end" width="10%">KDV (%)</th>
                            <th class="text-end" width="15%">Tutar</th>
                        </tr>
                    </thead>
                    <tbody>
                        <xsl:for-each select="cac:InvoiceLine">
                            <tr>
                                <td class="text-center"><xsl:value-of select="cbc:ID"/></td>
                                <td><xsl:value-of select="cac:Item/cbc:Name"/></td>
                                <td class="text-center">
                                    <xsl:value-of select="cbc:InvoicedQuantity"/> 
                                    <span class="ms-1 text-muted small"><xsl:value-of select="cbc:InvoicedQuantity/@unitCode"/></span>
                                </td>
                                <td class="text-end"><xsl:value-of select="cac:Price/cbc:PriceAmount"/></td>
                                <td class="text-end"><xsl:value-of select="cac:TaxTotal/cac:TaxSubtotal/cbc:Percent"/></td>
                                <td class="text-end"><xsl:value-of select="cbc:LineExtensionAmount"/> <xsl:value-of select="cbc:LineExtensionAmount/@currencyID"/></td>
                            </tr>
                        </xsl:for-each>
                    </tbody>
                </table>

                <div class="row">
                    <div class="col-sm-7">
                        <xsl:if test="cbc:Note">
                            <div class="p-3 bg-light border rounded">
                                <strong class="d-block mb-1 text-primary">Notlar:</strong>
                                <span class="text-muted"><xsl:value-of select="cbc:Note"/></span>
                            </div>
                        </xsl:if>
                    </div>
                    <div class="col-sm-5">
                        <div class="totals-box border">
                            <table class="table table-sm table-borderless mb-0">
                                <tr>
                                    <td class="text-muted"><strong>Mal/Hizmet Toplamı:</strong></td>
                                    <td class="text-end"><xsl:value-of select="cac:LegalMonetaryTotal/cbc:LineExtensionAmount"/> <xsl:value-of select="cac:LegalMonetaryTotal/cbc:LineExtensionAmount/@currencyID"/></td>
                                </tr>
                                <tr>
                                    <td class="text-muted"><strong>Hesaplanan KDV:</strong></td>
                                    <td class="text-end"><xsl:value-of select="cac:TaxTotal/cbc:TaxAmount"/> <xsl:value-of select="cac:TaxTotal/cbc:TaxAmount/@currencyID"/></td>
                                </tr>
                                <tr class="border-top mt-2 pt-2">
                                    <td class="fs-5 text-dark mt-2"><strong>Genel Toplam:</strong></td>
                                    <td class="text-end fs-5 text-primary"><strong><xsl:value-of select="cac:LegalMonetaryTotal/cbc:PayableAmount"/> <xsl:value-of select="cac:LegalMonetaryTotal/cbc:PayableAmount/@currencyID"/></strong></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="text-center mt-5 pt-4 border-top text-muted small">
                    <p class="mb-1"><i class="bi bi-shield-check"></i> Bu belge elektronik olarak imzalanmış olup, 5070 sayılı Elektronik İmza Kanunu gereği geçerlidir.</p>
                    <p class="mb-0"><strong>MuhasebeERP 2026</strong> - Gelişmiş E-Dönüşüm Modülü</p>
                </div>
            </div>
        </body>
        </html>
    </xsl:template>
</xsl:stylesheet>