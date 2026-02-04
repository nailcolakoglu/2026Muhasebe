from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from datetime import datetime

def create_firma_form(firma=None):
    # Firma genellikle tek kayıttır ve düzenlenir
    action_url = f"/firmalar/guncelle/{firma.id}"
    title = _("Şirket Bilgilerim")
    
    form = Form(name="firma_form", title=title, action=action_url, method="POST", submit_text=_("Bilgileri Güncelle"), ajax=True)
    layout = FormLayout()

    # --- ALANLAR ---
    unvan = FormField('unvan', FieldType.TEXT, _('Şirket Ünvanı'), required=True, value=firma.unvan if firma else '', icon='bi bi-building')
    
    vergi_dairesi = FormField('vergi_dairesi', FieldType.TEXT, _('Vergi Dairesi'), value=firma.vergi_dairesi if firma else '')
    vergi_no = FormField('vergi_no', FieldType.TCKN_VKN, _('Vergi / TC No'), value=firma.vergi_no if firma else '')
    
    adres = FormField('adres', FieldType.TEXTAREA, _('Adres'), value=firma.adres if firma else '')
    telefon = FormField('telefon', FieldType.TEL, _('Telefon'), value=firma.telefon if firma else '')
    email = FormField('email', FieldType.EMAIL, _('E-posta'), value=firma.email if firma else '')
    
    # Logo Yükleme (Dosya Yöneticisi Entegre Edilebilir, şimdilik text path)
    # Gelişmiş versiyonda FieldType.FILE kullanılabilir
    
    # --- LAYOUT ---
    layout.add_row(unvan)
    layout.add_row(vergi_dairesi, vergi_no)
    layout.add_row(telefon, email)
    layout.add_row(adres)

    form.set_layout_html(layout.render())
    form.add_fields(unvan, vergi_dairesi, vergi_no, telefon, email, adres)
    
    return form

def create_donem_form(donem=None):
    is_edit = donem is not None
    action_url = f"/firmalar/donem/duzenle/{donem.id}" if is_edit else "/firmalar/donem/ekle"
    title = _("Dönem Düzenle") if is_edit else _("Yeni Mali Dönem")
    
    form = Form(name="donem_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- DEĞİŞİKLİK BURADA: 'yil' ve 'aciklama' yerine sadece 'ad' ---
    varsayilan_ad = f"{datetime.now().year} Dönemi"
    ad = FormField('ad', FieldType.TEXT, _('Dönem Adı'), required=True, value=donem.ad if donem else varsayilan_ad)
    # -----------------------------------------------------------------
    
    aktif = FormField('aktif', FieldType.SWITCH, _('Bu Dönem Aktif Olsun'), value=donem.aktif if donem else False)

    baslangic = FormField('baslangic', FieldType.DATE, _('Başlangıç Tarihi'), required=True, value=donem.baslangic if donem else '')
    bitis = FormField('bitis', FieldType.DATE, _('Bitiş Tarihi'), required=True, value=donem.bitis if donem else '')

    layout.add_row(ad, aktif) # Layout da sadeleşti
    layout.add_row(baslangic, bitis)
    layout.add_alert("Bilgi", "Bir dönemi 'Aktif' yaptığınızda, diğer tüm dönemler otomatik olarak pasif duruma geçer.", "info")

    form.set_layout_html(layout.render())
    form.add_fields(ad, aktif, baslangic, bitis) # yil ve aciklama çıkarıldı
    
    return form