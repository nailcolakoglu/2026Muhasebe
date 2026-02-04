from app.form_builder import Form, FormField, FieldType, FormLayout, MasterDetailField
from flask import url_for
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.muhasebe.models import HesapPlani
from app.modules.muhasebe.utils import get_muhasebe_hesaplari
from datetime import datetime
from app.enums import MuhasebeFisTuru, HesapSinifi, BelgeTuru, OdemeYontemi, BakiyeTuru, OzelHesapTipi
from app.extensions import get_tenant_db # GOLDEN RULE

def create_muhasebe_fis_form(fis=None):    
    is_edit = fis is not None
    action_url = f"/muhasebe/duzenle/{fis.id}" if is_edit else "/muhasebe/ekle"
    
    form_color = "primary" 
    title = _("Yeni Muhasebe Fişi")
    
    # Enum Value Handle
    fis_turu_val = fis.fis_turu.value if fis and hasattr(fis.fis_turu, 'value') else (fis.fis_turu if fis else None)
    
    if fis:
        title = f"Fiş Düzenle: {fis.fis_no}"
        if fis_turu_val == 'tahsil': form_color = "success"
        elif fis_turu_val == 'tediye': form_color = "danger"
        elif fis_turu_val == 'kapanis': form_color = "dark"
    
    form = Form(name="muhasebe_form", title=title, action=action_url, method="POST", 
                submit_text=_("Fişi Kaydet"), ajax=True, show_title=False)
    
    form.extra_context = {'card_color': form_color, 'fis_id': fis.id if fis else None}

    layout = FormLayout()

    # --- HESAP LİSTESİ (Tenant DB) ---
    tenant_db = get_tenant_db()
    muavinler = tenant_db.query(HesapPlani).filter_by(
        firma_id=current_user.firma_id, 
    ).order_by(HesapPlani.kod).all()
    
    # Sadece muavinleri filtrele (Python tarafında garanti olsun)
    hesap_opts = []
    for h in muavinler:
        htip = h.hesap_tipi.value if hasattr(h.hesap_tipi, 'value') else h.hesap_tipi
        if str(htip) == 'muavin':
            hesap_opts.append((h.id, f"{h.kod} - {h.ad}"))

    turler = [
        (MuhasebeFisTuru.MAHSUP.value, 'Mahsup Fişi'),
        (MuhasebeFisTuru.TAHSIL.value, 'Tahsil Fişi'),
        (MuhasebeFisTuru.TEDIYE.value, 'Tediye Fişi'),
        (MuhasebeFisTuru.ACILIS.value, 'Açılış Fişi'),
        (MuhasebeFisTuru.KAPANIS.value, 'Kapanış Fişi')
    ]

    fis_no = FormField('fis_no', FieldType.AUTO_NUMBER, _('Fiş No'), 
                       required=True, 
                       value=fis.fis_no if fis else '', 
                       endpoint='/muhasebe/api/siradaki-no',
                       icon='bi bi-qr-code')

    bugun = datetime.now().strftime('%Y-%m-%d')
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=fis.tarih if fis else bugun)
    
    fis_turu = FormField('fis_turu', FieldType.SELECT, _('Fiş Türü'), 
                         options=turler, required=True, 
                         value=fis_turu_val if fis else MuhasebeFisTuru.MAHSUP.value)

    aciklama = FormField('aciklama', FieldType.TEXT, _('Genel Açıklama'), value=fis.aciklama if fis else '', placeholder="Fişin genel açıklaması...")

    baslik_html = """
    <div class="d-flex align-items-center mb-2 mt-4">
        <h6 class="fw-bold mb-0 text-secondary"><i class="bi bi-list-check me-2"></i>Fiş Hareketleri & e-Defter Detayları</h6>
        <div class="ms-auto">
             <small class="text-muted fst-italic me-2" style="font-size: 0.8rem;">(F2: Yeni Satır)</small>
        </div>
    </div>
    <hr class="mt-0 mb-2 text-muted">
    """
    grid_header = FormField('grid_header', FieldType.HTML, label="", value=baslik_html)

    satirlar = FormField('detaylar', FieldType.MASTER_DETAIL, label="Fiş Hareketleri", required=True)
    
    belge_turleri = [("", "Belge Yok")]
    belge_turleri.append((BelgeTuru.FATURA.value, "Fatura"))
    belge_turleri.append((BelgeTuru.CEK.value, "Çek"))
    belge_turleri.append((BelgeTuru.MAKBUZ.value, "Makbuz"))
    belge_turleri.append((BelgeTuru.SENET.value, "Senet"))
    belge_turleri.append((BelgeTuru.DIGER.value, "Diğer"))

    odeme_yontemleri = [("", "Seçiniz")]
    odeme_yontemleri.append((OdemeYontemi.NAKIT.value, "Nakit (Kasa)"))
    odeme_yontemleri.append((OdemeYontemi.BANKA.value, "Banka / EFT"))
    odeme_yontemleri.append((OdemeYontemi.CEK.value, "Çek"))
    odeme_yontemleri.append((OdemeYontemi.SENET.value, "Senet"))
    odeme_yontemleri.append((OdemeYontemi.KREDI_KARTI.value, "Kredi Kartı"))

    satirlar.columns = [
        FormField('hesap_id', FieldType.SELECT, 'Hesap Kodu / Adı', 
                  options=hesap_opts, required=True, 
                  select2_config={'placeholder': 'Hesap Seç', 'search': True},
                  html_attributes={'style': 'min-width: 300px;', 'class': 'hesap-secimi'}),
        
        FormField('aciklama', FieldType.TEXT, 'Satır Açıklaması', 
                  html_attributes={'class': 'form-control-sm', 'placeholder': 'Açıklama', 'style': 'min-width: 200px;'}),
        
        FormField('belge_tarihi', FieldType.DATE, 'Belge Tar.', 
                  html_attributes={'class': 'form-control-sm', 'style': 'width: 110px;'}),

        FormField('belge_no', FieldType.TEXT, 'Belge No', 
                  html_attributes={'class': 'form-control-sm', 'style': 'width: 100px;', 'placeholder': 'A-123'}),
 
        FormField('belge_turu', FieldType.SELECT, 'Belge Türü', 
                  options=belge_turleri, 
                  html_attributes={'class': 'form-select-sm', 'style': 'width: 100px;'}),

        FormField('belge_aciklamasi', FieldType.TEXT, 'Belge Detay', 
                  html_attributes={'class': 'form-control-sm', 'placeholder': 'Örn: Fatura Detayı', 'style': 'width: 120px;'}),          
       
        FormField('odeme_yontemi', FieldType.SELECT, 'Ödeme Yönt.', 
                  options=odeme_yontemleri,
                  html_attributes={'class': 'form-select-sm', 'style': 'width: 100px;'}),
        
        FormField('borc', FieldType.CURRENCY, 'Borç', default_value=0, 
                  html_attributes={'class': 'text-end fw-bold text-success js-borc', 'step': '0.01', 'style': 'width: 120px;'}),
        
        FormField('alacak', FieldType.CURRENCY, 'Alacak', default_value=0, 
                  html_attributes={'class': 'text-end fw-bold text-danger js-alacak', 'step': '0.01', 'style': 'width: 120px;'})
    ]

    if is_edit and fis.detaylar:
        row_data = []
        for d in fis.detaylar:
            row_data.append({
                'hesap_id': d.hesap_id,
                'aciklama': d.aciklama,
                'belge_turu': d.belge_turu.value if hasattr(d.belge_turu, 'value') else d.belge_turu,
                'belge_no': d.belge_no,
                'belge_aciklamasi': d.belge_aciklamasi,
                'belge_tarihi': d.belge_tarihi.strftime('%Y-%m-%d') if d.belge_tarihi else '',
                'odeme_yontemi': d.odeme_yontemi.value if hasattr(d.odeme_yontemi, 'value') else d.odeme_yontemi,
                'borc': float(d.borc),
                'alacak': float(d.alacak),
            })
        satirlar.value = row_data

    layout.add_row(fis_no, tarih, fis_turu)
    layout.add_row(aciklama)
    layout.add_row(grid_header) 
    layout.add_row(satirlar)
    
    form.set_layout_html(layout.render())
    form.add_fields(fis_no, tarih, fis_turu, aciklama, grid_header, satirlar)
    
    return form   

def create_hesap_form(hesap=None):
    is_edit = hesap is not None
    action_url = f"/muhasebe/hesap/duzenle/{hesap.id}" if is_edit else "/muhasebe/hesap/ekle"
    title = _("Hesap Kartı")
    
    form = Form(name="hesap_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()
    tenant_db = get_tenant_db()

    def safe_val(val):
        if val is None: return ''
        return val.value if hasattr(val, 'value') else val

    # Üst Hesap Seçimi (Tenant DB)
    ust_hesaplar = tenant_db.query(HesapPlani).filter_by(firma_id=current_user.firma_id).order_by(HesapPlani.kod).all()
    
    ust_opts = [(0, '--- Ana Hesap (Yok) ---')]
    for h in ust_hesaplar:
        htip = safe_val(h.hesap_tipi)
        if htip != 'muavin':
            ust_opts.append((h.id, f"{h.kod} - {h.ad}"))

    sinif_opts = [
        (HesapSinifi.MUAVIN_HESAP.value, 'Muavin Hesap (İşlem Gören)'),
        (HesapSinifi.GRUP_HESABI.value, 'Grup Hesabı (Alt Kırılım)'),
        (HesapSinifi.ANA_HESAP.value, 'Ana Hesap (Kebir)')
    ]
    
    bakiye_opts = [
        (BakiyeTuru.HER_IKISI.value, 'Borç ve Alacak (Cari/Banka)'),
        (BakiyeTuru.BORC.value, 'Borç Çalışır (Gider/Varlık)'),
        (BakiyeTuru.ALACAK.value, 'Alacak Çalışır (Gelir/Kaynak)')
    ]
    
    ozel_opts = [
        (OzelHesapTipi.STANDART.value, 'Standart'),
        (OzelHesapTipi.KASA.value, 'Kasa Hesabı (100)'),
        (OzelHesapTipi.BANKA.value, 'Banka Hesabı (102)'),
        (OzelHesapTipi.ALIS_KDV.value, 'Alış KDV (191)'),
        (OzelHesapTipi.SATIS_KDV.value, 'Satış KDV (391)'),
        (OzelHesapTipi.CEK.value, 'Çek/Senet Hesabı')
    ]

    ust_hesap_id = FormField('ust_hesap_id', FieldType.SELECT, _('Bağlı Olduğu Üst Hesap'), 
                             options=ust_opts, required=False, 
                             value=hesap.ust_hesap_id if hesap else 0,
                             select2_config={'placeholder': 'Varsa Üst Hesap Seçiniz', 'search': True})

    kod = FormField('kod', FieldType.TEXT, _('Hesap Kodu'), required=True, value=hesap.kod if hesap else '', placeholder="Örn: 120.01.001")
    ad = FormField('ad', FieldType.TEXT, _('Hesap Adı'), required=True, value=hesap.ad if hesap else '', placeholder="Örn: Yurt İçi Müşteriler")
    
    val_tip = safe_val(hesap.hesap_tipi) if hesap else HesapSinifi.MUAVIN_HESAP.value
    hesap_tipi = FormField('hesap_tipi', FieldType.SELECT, _('Hesap Sınıfı'), options=sinif_opts, required=True, value=val_tip)
    
    val_bakiye = safe_val(hesap.bakiye_turu) if hesap else BakiyeTuru.HER_IKISI.value
    bakiye_turu = FormField('bakiye_turu', FieldType.SELECT, _('Bakiye Karakteri'), options=bakiye_opts, required=True, value=val_bakiye)
    
    val_ozel = safe_val(hesap.ozel_hesap_tipi) if hesap else OzelHesapTipi.STANDART.value
    ozel_tip = FormField('ozel_hesap_tipi', FieldType.SELECT, _('Özel Rolü'), options=ozel_opts, required=True, value=val_ozel)
    
    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), required=False, value=hesap.aciklama if hesap else '')

    layout.add_row(kod, ad)
    layout.add_row(ust_hesap_id, hesap_tipi)
    layout.add_html('<div class="p-3 bg-light border rounded mt-2 mb-2"><h6 class="text-primary"><i class="bi bi-gear"></i> Gelişmiş Ayarlar</h6>')
    layout.add_row(bakiye_turu, ozel_tip)
    layout.add_html('</div>')
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, ust_hesap_id, hesap_tipi, bakiye_turu, ozel_tip, aciklama)
    
    return form