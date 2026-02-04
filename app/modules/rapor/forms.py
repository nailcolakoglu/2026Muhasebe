from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from app.modules.cari.models import CariHesap
from app.modules.kategori.models import StokKategori
from flask_login import current_user
from datetime import datetime, timedelta
from flask import url_for

def create_tarih_filtre_form():
    """Genel Tarih Aralığı Filtresi"""
    form = Form(name="filtre_form", title=_("Rapor Filtresi"), method="GET", submit_text=_("Raporla"), ajax=False) # Raporlar genelde GET ile çalışır
    layout = FormLayout()

    bugun = datetime.now().date()
    baslangic = bugun.replace(day=1) # Ayın başı
    
    baslangic_tarihi = FormField('baslangic', FieldType.DATE, _('Başlangıç'), value=baslangic)
    bitis_tarihi = FormField('bitis', FieldType.DATE, _('Bitiş'), value=bugun)

    layout.add_row(baslangic_tarihi, bitis_tarihi)
    
    form.set_layout_html(layout.render())
    form.add_fields(baslangic_tarihi, bitis_tarihi)
    return form

def create_cari_ekstre_form():
    """Cari Seçimli Filtre"""
    form = Form(name="cari_ekstre_form", title=_("Cari Ekstre Filtresi"), method="GET", submit_text=_("Raporu Getir"), ajax=False)
    layout = FormLayout()

    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
    cari_opts = [(c.id, f"{c.unvan}") for c in cariler]

    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=cari_opts, required=True, select2_config={'placeholder': 'Cari Seçiniz', 'search': True})
    
    bugun = datetime.now().date()
    yil_basi = bugun.replace(month=1, day=1)
    
    baslangic = FormField('baslangic', FieldType.DATE, _('Başlangıç'), value=yil_basi)
    bitis = FormField('bitis', FieldType.DATE, _('Bitiş'), value=bugun)

    layout.add_row(cari_id)
    layout.add_row(baslangic, bitis)

    form.set_layout_html(layout.render())
    form.add_fields(cari_id, baslangic, bitis)
    return form

def create_rapor_filtre_form():
    """Tarih aralığı filtreleme formu"""
    # Varsayılan: Bu ayın başından bugüne
    bugun = datetime.today()
    ay_basi = bugun.replace(day=1)
    
    # GET metodu kullanıyoruz ki linki paylaşabilsinler (rapor?baslangic=...&bitis=...)
    form = Form(name="rapor_filtre", title="", method="GET", submit_text=_("Raporu Getir"), submit_class="btn btn-info text-white", ajax=False)
    layout = FormLayout()

    baslangic = FormField('baslangic', FieldType.DATE, _('Başlangıç'), default_value=ay_basi.strftime('%Y-%m-%d'))
    bitis = FormField('bitis', FieldType.DATE, _('Bitiş'), default_value=bugun.strftime('%Y-%m-%d'))

    layout.add_row(baslangic, bitis)
    form.set_layout_html(layout.render())
    form.add_fields(baslangic, bitis)
    
    return form

def create_stok_rapor_form():
    """Kategori Filtreli Stok Raporu"""
    form = Form(name="stok_rapor_form", title=_("Stok Rapor Filtresi"), method="GET", submit_text=_("Listele"), ajax=False)
    layout = FormLayout()

    kategoriler = StokKategori.query.filter_by(firma_id=current_user.firma_id).all()
    kat_opts = [(0, 'Tüm Kategoriler')] + [(k.id, k.ad) for k in kategoriler]

    kategori_id = FormField('kategori_id', FieldType.SELECT, _('Kategori'), options=kat_opts, value=0)
    
    # Kritik seviye filtresi
    sadece_kritik = FormField('sadece_kritik', FieldType.SWITCH, _('Sadece Kritik Seviyenin Altındakiler'), value=False)

    layout.add_row(kategori_id, sadece_kritik)

    form.set_layout_html(layout.render())
    form.add_fields(kategori_id, sadece_kritik)
    return form   

def get_yevmiye_filter_form(baslangic_def, bitis_def):
    """
    Yevmiye Defteri için filtreleme formunu oluşturur.
    """
    # 1.Formu Başlat
    form = Form(
        name="frm_yevmiye_filter",
        title="Yevmiye Defteri Kriterleri",
        submit_text="<i class='bi bi-file-earmark-check me-2'></i>Raporu Üret",
        submit_class="btn btn-primary w-100 py-2 fw-bold shadow-sm", # Butonu tam genişlik yapalım
        reset_text=None, # Reset butonuna gerek yok
        action=url_for('rapor.yevmiye_defteri'),
        method="POST"
    )

    # 2.Tarih Alanları (Yan yana gelmesi için column_class kullanıyoruz)
    # FormField sınıfınızda 'column_class' desteği var
    f_baslangic = FormField(
        name="baslangic",
        field_type=FieldType.DATE,
        label="Başlangıç Tarihi",
        required=True,
        default_value=baslangic_def,
        column_class="col-md-6" # Bootstrap Grid
    )

    f_bitis = FormField(
        name="bitis",
        field_type=FieldType.DATE,
        label="Bitiş Tarihi",
        required=True,
        default_value=bitis_def,
        column_class="col-md-6"
    )

    # 3.Format Seçimi (Radio Button)
    # 3.Format Seçimi (MODERN RADYO KARTLARI)
    f_format = FormField(
        name="format",
        field_type=FieldType.RADIO,
        label="Rapor Formatı",
        required=True,
        default_value="laser",
        options=[
            # Format: (Değer, Etiket, İkon Sınıfı)
            ('laser', 'Lazer Yazıcı (A4)', 'bi bi-printer-fill'),
            ('dos', 'Nokta Vuruşlu (DOS)', 'bi bi-receipt-cutoff')
        ],
        # BURASI ÖNEMLİ: 'radio-card-group' sınıfı modern görünümü tetikler.
        # 'btn_color': 'info' diyerek mavi (info) temasını seçtik.primary, success vb.olabilir.
        html_attributes={'class': 'radio-card-group', 'btn_color': 'info'}
    )

    # 4.Alanları Forma Ekle
    # add_row metodunuzu kullanarak yan yana ekleyebiliriz
    # Ancak form sınıfınızda doğrudan layout yönetimi yoksa, sıralı ekleriz.
    # Sizin Form sınıfınızda 'add_field' var.Layout'u CSS classlar ile yöneteceğiz.
    
    # Tarihleri bir satıra almak için wrapper kullanabiliriz ama
    # FormBuilder'ınızda 'create_row' mantığı form_layout.py içinde.
    # Basitlik adına direkt ekliyoruz, col-md-6 işi görecektir.
    
    # Form içine Row yapısı eklemek için HTML alanı kullanabiliriz veya
    # alanlara verdiğimiz 'col-md-6' sınıfının çalışması için formu render ederken 
    # bir <div class="row"> içine alabiliriz.
    
    form.add_field(f_baslangic)
    form.add_field(f_bitis)
    form.add_field(f_format)

    return form

from form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _

def create_sablon_form(sablon=None):
    is_edit = sablon is not None
    action_url = f"/rapor/sablon-duzenle/{sablon.id}" if is_edit else "/rapor/sablon-ekle"
    title = _("Şablon Düzenle") if is_edit else _("Yeni Şablon")
    
    form = Form(name="sablon_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- SEÇENEKLER ---
    tur_opts = [
        ('fatura', 'Satış Faturası'),
        ('tahsilat', 'Tahsilat Makbuzu (Giriş)'),
        ('tediye', 'Tediye Makbuzu (Çıkış)'),
        ('stok_fisi', 'Stok Fişi / İrsaliye'),
        ('cari_ekstre', 'Cari Hesap Ekstresi'),
        ('mutabakat', 'Mutabakat Formu (BA/BS)')
    ]

    # --- ALANLAR ---
    baslik = FormField('baslik', FieldType.TEXT, _('Şablon Adı'), required=True, value=sablon.baslik if sablon else '', icon='bi bi-fonts')
    
    belge_turu = FormField('belge_turu', FieldType.SELECT, _('Belge Türü'), options=tur_opts, required=True, value=sablon.belge_turu if sablon else 'fatura')
    
    varsayilan = FormField('varsayilan', FieldType.CHECKBOX, _('Varsayılan Yap'), value='1', checked=(sablon.varsayilan if sablon else False))
    aktif = FormField('aktif', FieldType.CHECKBOX, _('Aktif'), value='1', checked=(sablon.aktif if sablon else True))

    html_icerik = FormField(
        'html_icerik', FieldType.TEXTAREA, _('HTML Tasarımı'), 
        required=True, 
        value=sablon.html_icerik if sablon else '',
        html_attributes={'rows': 20, 'class': 'code-editor', 'style': 'font-family: monospace; font-size: 12px;'}
    )

    css_icerik = FormField(
        'css_icerik', FieldType.TEXTAREA, _('Özel CSS (Opsiyonel)'), 
        value=sablon.css_icerik if sablon else '',
        html_attributes={'rows': 10, 'class': 'code-editor', 'style': 'font-family: monospace; font-size: 12px;'}
    )

    # --- DÜZELTİLEN YERLEŞİM (3 SEKME) ---
    # Kaybolan alanları "Genel Ayarlar" sekmesine taşıdık.
    
    tabs = layout.create_tabs("design_tabs", [
        # 1.SEKME: GENEL AYARLAR (Başlık, Tür vb.)
        ('<i class="bi bi-sliders me-2"></i>Genel Ayarlar', [
            layout.create_row(baslik, belge_turu),
            layout.create_row(varsayilan, aktif)
        ]),
        # 2.SEKME: HTML
        ('<i class="bi bi-filetype-html me-2"></i>HTML Yapısı', [html_icerik]),
        # 3.SEKME: CSS
        ('<i class="bi bi-filetype-css me-2"></i>CSS Stilleri', [css_icerik])
    ])
    
    form.set_layout_html(tabs)
    form.add_fields(baslik, belge_turu, varsayilan, aktif, html_icerik, css_icerik)
    
    return form

