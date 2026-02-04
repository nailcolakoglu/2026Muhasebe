# app/modules/sube/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from app.extensions import get_tenant_db # 👈 Firebird Bağlantısı
from app.modules.bolge.models import Bolge
from app.modules.lokasyon.models import Sehir, Ilce

def create_sube_form(sube=None):
    is_edit = sube is not None
    action_url = f"/sube/duzenle/{sube.id}" if is_edit else "/sube/ekle"
    title = _("Şube Düzenle") if is_edit else _("Yeni Şube Ekle")
    
    form = Form(name="sube_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # Veritabanı Bağlantısı
    tenant_db = get_tenant_db()
    
    # 1. BÖLGE LİSTESİ (FIREBIRD)
    bolge_opts = []
    if tenant_db:
        try:
            bolgeler = tenant_db.query(Bolge).filter_by(firma_id=1, aktif=True).all()
            bolge_opts = [(b.id, b.ad) for b in bolgeler]
        except:
            bolge_opts = []

    # 2. ŞEHİR LİSTESİ (FIREBIRD) 👈 DÜZELTİLDİ
    sehir_opts = []
    if tenant_db:
        try:
            # MySQL (Sehir.query) yerine Firebird (tenant_db.query)
            sehirler = tenant_db.query(Sehir).order_by(Sehir.ad).all()
            sehir_opts = [(s.id, s.ad) for s in sehirler]
        except:
            sehir_opts = []

    # 3. İLÇE LİSTESİ (FIREBIRD) 👈 DÜZELTİLDİ
    ilce_opts = []
    selected_sehir_id = sube.sehir_id if sube else (sehir_opts[0][0] if sehir_opts else None)
    
    if tenant_db and selected_sehir_id:
        try:
            ilceler = tenant_db.query(Ilce).filter_by(sehir_id=selected_sehir_id).order_by(Ilce.ad).all()
            ilce_opts = [(i.id, i.ad) for i in ilceler]
        except:
            ilce_opts = []

    # ALANLAR
    kod = FormField('kod', FieldType.TEXT, _('Şube Kodu'), required=True, value=sube.kod if sube else '')
    ad = FormField('ad', FieldType.TEXT, _('Şube Adı'), required=True, value=sube.ad if sube else '')
    
    bolge = FormField('bolge_id', FieldType.SELECT, _('Bağlı Olduğu Bölge'), 
                      options=[('', 'Seçiniz...')] + bolge_opts, required=False, 
                      value=sube.bolge_id if sube else '')
                      
    sehir = FormField('sehir_id', FieldType.SELECT, _('Şehir'), options=sehir_opts, required=True, value=sube.sehir_id if sube else '')
    
    # İlçe API Kaynağı
    # Not: API tarafında da sorguların Firebird'e atıldığından emin olunmalıdır.
    ilce = FormField('ilce_id', FieldType.SELECT, _('İlçe'), 
                        options=ilce_opts,
                        value=sube.ilce_id if sube else '',
                        data_source={
                            'url': '/cari/api/get-ilceler', 
                            'method': 'GET',
                            'depends_on': 'sehir_id'
                        },
                        select2_config={'placeholder': 'İlçe Seçiniz', 'search': True})

    adres = FormField('adres', FieldType.TEXTAREA, _('Adres'), value=sube.adres if sube else '')
    telefon = FormField('telefon', FieldType.TEL, _('Telefon'), value=sube.telefon if sube else '')

    layout.add_row(kod, ad)
    layout.add_row(bolge, sehir)
    layout.add_row(ilce, telefon)
    layout.add_row(adres)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, bolge, sehir, ilce, adres, telefon)
    
    return form