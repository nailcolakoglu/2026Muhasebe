# app/modules/kullanici/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.extensions import get_tenant_db 
from app.modules.sube.models import Sube

def create_kullanici_form(user=None):
    is_edit = user is not None
    
    # ID'yi string olarak URL'ye ekliyoruz
    action_url = f"/kullanici/duzenle/{user.id}" if is_edit else "/kullanici/ekle"
    title = _("Kullanıcı Düzenle") if is_edit else _("Yeni Personel Ekle")
    
    form = Form(name="user_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- ŞUBE LİSTESİ (TENANT DB'DEN ÇEKİLECEK) ---
    tenant_db = get_tenant_db()
    sube_opts = []
    
    if tenant_db:
        try:
            # ✨ DÜZELTME 1: firma_id=1 yerine UUID olan current_user.firma_id kullanıldı
            subeler = tenant_db.query(Sube).filter_by(firma_id=str(current_user.firma_id), aktif=True).all()
            sube_opts = [(str(s.id), s.ad) for s in subeler] # ✨ UUID garantisi
        except Exception as e:
            print(f"Form Sube Hatası: {e}")
            sube_opts = []

    # Roller
    rol_opts = [
        ('kasiyer', 'Kasiyer'),
        ('tezgahtar', 'Tezgahtar'),
        ('depo', 'Depo Sorumlusu'),
        ('plasiyer', 'Plasiyer / Saha'),
        ('sube_yoneticisi', 'Şube Yöneticisi'),
        ('bolge_muduru', 'Bölge Müdürü'),
        ('muhasebe', 'Muhasebe'),
        ('admin', 'Yönetici / Admin')
    ]

    # ALANLAR
    ad_soyad = FormField('ad_soyad', FieldType.TEXT, _('Ad Soyad'), required=True, value=user.ad_soyad if user else '')
    email = FormField('email', FieldType.EMAIL, _('Email'), required=True, value=user.email if user else '')
    
    sifre_req = not is_edit
    sifre = FormField('sifre', FieldType.PASSWORD, _('Şifre'), required=sifre_req)
    
    mevcut_rol = getattr(user, 'rol_kodu', 'kasiyer') if user else 'kasiyer'
    rol = FormField('rol', FieldType.SELECT, _('Rolü'), options=rol_opts, required=True, value=mevcut_rol)

    # Ana Şube Seçimi
    sube_secimi = FormField('sube_id', FieldType.SELECT, _('Bağlı Olduğu Şube'), 
                            options=[('', 'Seçiniz...')] + sube_opts, 
                            required=False,
                            value=str(user.sube_id) if user and user.sube_id else '')
    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif'), value=user.aktif if user else True)
    
    layout.add_row(ad_soyad, email)
    layout.add_row(sifre, rol)
    layout.add_row(sube_secimi)
    layout.add_row(aktif)
    
    form.set_layout_html(layout.render())
    form.add_fields(ad_soyad, email, sifre, rol, sube_secimi, aktif)
    
    return form