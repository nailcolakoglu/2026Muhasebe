# modules/auth/forms.py (YENİ VERSİYON - Form Builder ile)

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _


def create_login_form():
    """
    Giriş formu - Sadece email ve şifre
    
    Returns:
        Form: Form Builder objesi
    """
    form = Form(
        name="login_form",
        title=_("Giriş Yap"),
        action="/auth/login",
        method="POST",
        submit_text=_("Giriş Yap"),
        ajax=False
    )
    
    layout = FormLayout()
    
    # Email
    email = FormField(
        'email',
        FieldType.EMAIL,
        _('Email'),
        required=True,
        placeholder='admin@muhasebe.com',
        icon='bi bi-envelope'
    )
    
    # Şifre
    password = FormField(
        'password',
        FieldType.PASSWORD,
        _('Şifre'),
        required=True,
        placeholder='••••••••',
        icon='bi bi-lock'
    )
    
    layout.add_row(email)
    layout.add_row(password)
    
    form.set_layout_html(layout.render())
    form.add_fields(email, password)
    
    return form

def EmailLoginForm():
    """
    Email Bazlı Kullanıcı Giriş Formu
    Multi-tenant yapı için email + şifre girişi
    """
    form = Form(
        name="email_login_form",
        title=_("Sisteme Giriş"),
        submit_text=_("Giriş Yap"),
        submit_class="btn btn-primary w-100 py-2 fw-bold shadow-sm",
        action="/auth/login",
        method="POST",
        ajax=False  # Login işlemi redirect gerektirir
    )

    # E-posta
    email = FormField(
        'email',
        FieldType.EMAIL,
        _('E-posta Adresi'),
        required=True,
        placeholder='ornek@firma.com',
        icon='bi bi-envelope-fill',
        floating_label=True,
        validators={
            'email': True,
            'minlength': 5,
            'maxlength': 120
        }
    )

    # Şifre
    sifre = FormField(
        'sifre',
        FieldType.PASSWORD,
        _('Şifre'),
        required=True,
        placeholder='••••••••',
        icon='bi bi-key-fill',
        floating_label=True,
        validators={
            'minlength': 6,
            'maxlength':  50
        }
    )

    # Beni Hatırla
    beni_hatirla = FormField(
        'remember_me',
        FieldType.CHECKBOX,
        _('Beni Hatırla'),
        value='1',
        checked=False
    )

    form.add_fields(email, sifre, beni_hatirla)
    
    return form


def SelectTenantForm():
    """
    Firma Seçim Formu
    Çoklu firma erişimi olan kullanıcılar için
    """
    form = Form(
        name="select_tenant_form",
        title=_("Firma Seçin"),
        submit_text=_("Devam Et"),
        submit_class="btn btn-primary w-100 py-2 fw-bold",
        action="/auth/select-tenant",
        method="POST",
        ajax=False
    )
    
    # Not: Firma listesi dinamik olduğu için route'da eklenecek
    # Burada sadece hidden field veya placeholder
    
    return form