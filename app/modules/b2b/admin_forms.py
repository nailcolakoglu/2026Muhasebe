# app/modules/b2b/admin_forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from app.modules.cari.models import CariHesap
from app.extensions import get_tenant_db
from flask_login import current_user

def get_cari_options():
    tenant_db = get_tenant_db()
    # Sadece aktif firmanın carilerini getir
    cariler = tenant_db.query(CariHesap).filter_by(firma_id=current_user.firma_id).all()
    return [('', 'Bağlanacak Cariyi Seçiniz...')] + [(str(c.id), c.unvan) for c in cariler]

def create_b2b_kullanici_form(kullanici=None):
    is_edit = kullanici is not None
    action_url = f"/b2b-yonetim/kullanici/duzenle/{kullanici.id}" if is_edit else "/b2b-yonetim/kullanici/ekle"
    title = "B2B Müşteri Hesabı Düzenle" if is_edit else "Yeni B2B Müşteri Hesabı Oluştur"
    
    form = Form(name="b2b_user_form", title=title, action=action_url, method="POST", ajax=True)
    layout = FormLayout()
    
    cari = FormField('cari_id', FieldType.SELECT, 'Bağlı Cari Hesap', options=get_cari_options(), required=True, value=str(kullanici.cari_id) if kullanici else '', select2_config={'search': True})
    
    ad_soyad = FormField('ad_soyad', FieldType.TEXT, 'Yetkili Ad Soyad', required=True, value=kullanici.ad_soyad if kullanici else '')
    email = FormField('email', FieldType.EMAIL, 'Giriş E-Posta Adresi', required=True, value=kullanici.email if kullanici else '')
    telefon = FormField('telefon', FieldType.TEXT, 'İrtibat Telefonu', value=kullanici.telefon if kullanici else '')
    
    # Düzenlerken şifre zorunlu değildir (Boş bırakırsa değişmez)
    sifre_label = 'Yeni Şifre (Değiştirmeyecekseniz boş bırakın)' if is_edit else 'Giriş Şifresi Belirleyin'
    sifre = FormField('sifre', FieldType.PASSWORD, sifre_label, required=not is_edit)
    
    aktif = FormField('aktif', FieldType.CHECKBOX, 'Portala Girebilir (Aktif)', value=kullanici.aktif if kullanici else True)
    yetki_sip = FormField('yetki_siparis_ver', FieldType.CHECKBOX, 'Sipariş Verebilir', value=kullanici.yetki_siparis_ver if kullanici else True)
    yetki_eks = FormField('yetki_ekstre_gor', FieldType.CHECKBOX, 'Cari Ekstre Görebilir', value=kullanici.yetki_ekstre_gor if kullanici else True)

    layout.add_row(cari)
    layout.add_row(ad_soyad, telefon)
    layout.add_row(email, sifre)
    layout.add_row(aktif, yetki_sip, yetki_eks)
    
    form.set_layout_html(layout.render())
    form.add_fields(cari, ad_soyad, email, telefon, sifre, aktif, yetki_sip, yetki_eks)
    
    return form