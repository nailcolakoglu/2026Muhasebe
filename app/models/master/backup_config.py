# app/models/master/backup_config.py


from app.extensions import db
from datetime import datetime
import uuid

class BackupConfig(db.Model):
    """
    Her firmanın kendi yedekleme tercihi burada tutulur.
    """
    __tablename__ = 'backup_configs'
    __bind_key__ = None # Master DB

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False, unique=True)
    
    # Sağlayıcı Tipi: 'local', 'aws_s3', 'ftp', 'google_drive'
    provider = db.Column(db.String(20), default='local', nullable=False)
    
    # AWS S3 Ayarları
    aws_access_key = db.Column(db.String(255), nullable=True)
    aws_secret_key = db.Column(db.String(255), nullable=True)
    aws_bucket_name = db.Column(db.String(100), nullable=True)
    aws_region = db.Column(db.String(50), default='eu-central-1') # Frankfurt
    
    # FTP Ayarları
    ftp_host = db.Column(db.String(100), nullable=True)
    ftp_user = db.Column(db.String(100), nullable=True)
    ftp_password = db.Column(db.String(100), nullable=True)
    ftp_port = db.Column(db.Integer, default=21)
    
    # Yedekleme Sıklığı ve Kuralları
    frequency = db.Column(db.String(20), default='daily') # daily, weekly
    retention_days = db.Column(db.Integer, default=30) # Kaç gün saklansın?
    encrypt_backups = db.Column(db.Boolean, default=True) # Şifrele?
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # İlişki
    tenant = db.relationship('Tenant', backref=db.backref('backup_config', uselist=False))