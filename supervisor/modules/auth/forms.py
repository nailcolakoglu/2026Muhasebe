# supervisor/modules/auth/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length

class LoginForm(FlaskForm):
    """Yönetici Giriş Formu"""
    
    username = StringField('Kullanıcı Adı', validators=[
        DataRequired(message="Kullanıcı adı veya e-posta gereklidir.")
    ])
    
    password = PasswordField('Şifre', validators=[
        DataRequired(message="Şifre gereklidir.")
    ])
    
    remember = BooleanField('Beni Hatırla')