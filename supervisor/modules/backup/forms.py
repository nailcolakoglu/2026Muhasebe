# supervisor/modules/backup/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class BackupSettingsForm(FlaskForm):
    # Sağlayıcı Seçimi
    provider = SelectField('Yedekleme Yeri', choices=[
        ('local', 'Yerel Disk (Sadece Sunucu)'),
        ('onedrive', 'Microsoft OneDrive'),
        ('aws_s3', 'Amazon AWS S3 (Bulut)'),
        ('ftp', 'Uzak FTP Sunucusu'),
        ('google', 'Google Drive (Yakında)')
    ], validators=[DataRequired()])
    
    # --- AWS S3 Ayarları ---
    aws_access_key = StringField('AWS Access Key', validators=[Optional(), Length(max=255)])
    aws_secret_key = PasswordField('AWS Secret Key', validators=[Optional(), Length(max=255)])
    aws_bucket_name = StringField('Bucket Adı', validators=[Optional(), Length(max=100)])
    aws_region = StringField('Bölge (Region)', default='eu-central-1', validators=[Optional()])
    
    # --- FTP Ayarları ---
    ftp_host = StringField('FTP Sunucu Adresi (Host)', validators=[Optional()])
    ftp_port = IntegerField('Port', default=21, validators=[Optional()])
    ftp_user = StringField('Kullanıcı Adı', validators=[Optional()])
    ftp_password = PasswordField('Şifre', validators=[Optional()])
    
    # --- Genel Ayarlar ---
    frequency = SelectField('Yedekleme Sıklığı', choices=[
        ('daily', 'Her Gün (Gece)'),
        ('weekly', 'Her Hafta (Pazar)'),
        ('manual', 'Sadece Manuel')
    ], default='daily')
    
    retention_days = IntegerField('Saklama Süresi (Gün)', default=30, validators=[DataRequired()])
    encrypt_backups = BooleanField('Yedekleri Şifrele (AES-256)', default=True)
    
    submit = SubmitField('Ayarları Kaydet')