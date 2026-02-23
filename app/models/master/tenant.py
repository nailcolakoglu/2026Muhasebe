# app/models/master/tenant.py

from sqlalchemy import event
from app.utils.validators import SecurityValidator
import logging

logger = logging.getLogger(__name__)

from app.extensions import db
from datetime import datetime
from cryptography.fernet import Fernet
import os
import uuid  # ✅ EKLENDI

class Tenant(db.Model):
    """Firma (Tenant) Bilgileri"""
    __tablename__ = 'tenants'
    __bind_key__ = None
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # ✅ Artık çalışır
    kod = db.Column(db.String(20), unique=True, nullable=False, index=True)
    unvan = db.Column(db.String(200), nullable=False)
    
    vergi_no = db.Column(db.String(20))
    vergi_dairesi = db.Column(db.String(100))
    
    db_name = db.Column(db.String(100), unique=True, nullable=True)
    db_password_encrypted = db.Column(db.String(255))
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    licenses = db.relationship('License', back_populates='tenant', lazy='dynamic')
    user_roles = db.relationship('UserTenantRole', back_populates='tenant', lazy='dynamic')
    
    @staticmethod
    def _get_encryption_key():
        """Şifreleme anahtarını al"""
        key = os.environ.get('TENANT_DB_ENCRYPTION_KEY')
        
        if not key:
            new_key = Fernet.generate_key().decode()
            
            print("\n" + "="*60)
            print("⚠️  ŞİFRELEME ANAHTARI OLUŞTURULDU!")
            print("="*60)
            print(f"TENANT_DB_ENCRYPTION_KEY={new_key}")
            print("="*60)
            print("⚠️  Bu anahtarı .env dosyasına ekleyin!")
            print("="*60 + "\n")
            
            return new_key.encode()
        
        return key.encode() if isinstance(key, str) else key
    
    def set_db_password(self, password):
        """Firebird şifresini şifrele"""
        if not password:
            self.db_password_encrypted = None
            return
        
        try:
            key = self._get_encryption_key()
            cipher = Fernet(key)
            encrypted = cipher.encrypt(password.encode())
            self.db_password_encrypted = encrypted.decode()
        except Exception as e:
            print(f"❌ Şifreleme hatası: {e}")
            self.db_password_encrypted = password
    
    def get_db_password(self):
        """Şifreyi çöz"""
        if not self.db_password_encrypted:
            return 'masterkey'
        
        try:
            key = self._get_encryption_key()
            cipher = Fernet(key)
            decrypted = cipher.decrypt(self.db_password_encrypted.encode())
            return decrypted.decode()
        except Exception as e:
            print(f"❌ Şifre çözme hatası: {e}")
            return self.db_password_encrypted
    
    def __repr__(self):
        return f'<Tenant {self.kod} - {self.unvan}>'
    
    
# ============================================
# EVENT LISTENER: Kayıt Öncesi Validation
# ============================================

@event.listens_for(Tenant, 'before_insert')
@event.listens_for(Tenant, 'before_update')
def validate_tenant_before_save(mapper, connection, target):
    """
    Tenant kaydı öncesi güvenlik kontrolü
    
    Args:
        target (Tenant): Kaydedilecek tenant
    
    Raises:
        ValueError: Validation başarısız
    """
    # 1. Tenant code validation
    is_valid_code, error = SecurityValidator.validate_tenant_code(target.kod)
    if not is_valid_code:
        logger.error(f"❌ Tenant validation hatası (kod): {target.kod} - {error}")
        raise ValueError(f"Geçersiz tenant kodu: {error}")
    
    # 2. Database name validation (eğer varsa)
    if target.db_name:
        is_valid_db, error = SecurityValidator.validate_db_name(target.db_name)
        if not is_valid_db:
            logger.error(f"❌ Tenant validation hatası (db_name): {target.db_name} - {error}")
            raise ValueError(f"Geçersiz database adı: {error}")
    
    logger.debug(f"✅ Tenant validation başarılı: {target.kod}")
    