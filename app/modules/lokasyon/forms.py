# app/modules/lokasyon/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from app.modules.lokasyon.models import Sehir
from app.extensions import get_tenant_db # 👈 Firebird

def get_sehir_form(target_url, edit_mode=False, instance=None):
    """
    Şehir (İl) Tanımlama Formu
    """
    title = _("Şehir Düzenle") if edit_mode else _("Yeni Şehir Ekle")
    form = Form(name="sehir_form", title=title, action=target_url, ajax=True)
    
    val = lambda k: getattr(instance, k) if instance else ''

    f_kod = FormField("kod", FieldType.TEXT, _("Plaka Kodu"), required=True, 
                      value=val('kod'), placeholder="Örn: 34", max_length=2).in_row("col-md-4")
    
    f_ad = FormField("ad", FieldType.TEXT, _("Şehir Adı"), required=True, 
                     value=val('ad'), text_transform='uppercase').in_row("col-md-8")

    form.add_fields(f_kod, f_ad)
    
    layout = FormLayout()
    layout.add_row(f_kod, f_ad)
    form.set_layout_html(layout.render())
    return form

def get_ilce_form(target_url, edit_mode=False, instance=None):
    """
    İlçe Tanımlama Formu
    """
    title = _("İlçe Düzenle") if edit_mode else _("Yeni İlçe Ekle")
    form = Form(name="ilce_form", title=title, action=target_url, ajax=True)
    
    # 👈 Şehir Listesini Firebird'den Çek
    tenant_db = get_tenant_db()
    sehir_opts = []
    
    if tenant_db:
        try:
            sehirler = tenant_db.query(Sehir).order_by(Sehir.kod).all()
            sehir_opts = [("", _("Şehir Seçiniz..."))] + [(str(s.id), f"{s.kod} - {s.ad}") for s in sehirler]
        except:
            sehir_opts = []
    
    val = lambda k: getattr(instance, k) if instance else ''

    # Alanlar
    f_sehir = FormField("sehir_id", FieldType.SELECT, _("Bağlı Olduğu İl"), 
                        options=sehir_opts, required=True, 
                        value=val('sehir_id'), 
                        select2_config={'allowClear': True}).in_row("col-md-6")
    
    f_ad = FormField("ad", FieldType.TEXT, _("İlçe Adı"), required=True, 
                     value=val('ad'), text_transform='uppercase').in_row("col-md-6")

    form.add_fields(f_sehir, f_ad)
    
    layout = FormLayout()
    layout.add_row(f_sehir, f_ad)
    
    form.set_layout_html(layout.render())
    return form