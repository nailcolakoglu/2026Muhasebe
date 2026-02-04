# supervisor/modules/users/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional

class UserForm(FlaskForm):
    """Kullanıcı Ekleme/Düzenleme Formu"""
    
    email = StringField('Email', validators=[
        DataRequired(message="Email zorunludur"),
        Email(message="Geçerli bir email adresi giriniz")
    ])
    
    full_name = StringField('Ad Soyad', validators=[
        DataRequired(message="Ad soyad zorunludur"),
        Length(min=3, max=100)
    ])
    
    # Şifre sadece yeni kayıtta zorunlu, düzenlemede veya mevcut kullanıcıya rol eklerken opsiyonel
    password = PasswordField('Şifre', validators=[
        Optional(),
        Length(min=6, message="Şifre en az 6 karakter olmalı")
    ])
    
    tenant_id = SelectField('Firma', validators=[Optional()])
    
    # ✅ GÜNCELLENDİ: RBAC Sistemindeki Tüm Roller Eklendi
    role = SelectField('Rol', choices=[
        ('user', 'Standart Kullanıcı (Dashboard)'),
        ('admin', 'Firma Sahibi / Admin (Tam Yetki)'),
        
        # Merkez Kadro
        ('finans_muduru', 'Finans Müdürü'),
        ('muhasebe_muduru', 'Muhasebe Müdürü'),
        
        # Yönetim
        ('bolge_muduru', 'Bölge Müdürü'),
        ('sube_yoneticisi', 'Şube Yöneticisi'),
        
        # Saha ve Operasyon
        ('plasiyer', 'Plasiyer / Saha Satış'),
        ('depo', 'Depo Sorumlusu'),
        ('lojistik', 'Lojistik / Sevkiyat'),
        ('kasiyer', 'Kasiyer'),
        ('tezgahtar', 'Tezgahtar')
    ], default='user')
    
    is_active = BooleanField('Aktif Kullanıcı', default=True)