# supervisor/modules/licenses/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Optional, NumberRange

try:
    from supervisor_config import SupervisorConfig
except ImportError:
    from config import SupervisorConfig

class LicenseForm(FlaskForm):
    """Lisans Yönetim Formu"""
    
    # Seçimler
    tenant_id = SelectField('Firma', validators=[DataRequired()], choices=[])
    
    # Tipleri Config'den al
    type_choices = [(k, v['name']) for k, v in SupervisorConfig.LICENSE_TYPES.items()]
    license_type = SelectField('Paket Tipi', choices=type_choices, validators=[DataRequired()])
    
    # Limitler
    duration_days = SelectField('Süre', choices=[
        ('30', '30 Gün (Deneme)'),
        ('365', '1 Yıl'),
        ('730', '2 Yıl')
    ], default='365')
    
    max_users = IntegerField('Kullanıcı Limiti', validators=[
        DataRequired(), NumberRange(min=1, max=1000)
    ], default=5)
    
    # Finansal
    monthly_fee = FloatField('Aylık Ücret (TL)', default=0.0)
    billing_cycle = SelectField('Fatura Dönemi', choices=[
        ('monthly', 'Aylık'), ('yearly', 'Yıllık')
    ], default='monthly')
    
    notes = TextAreaField('Notlar')