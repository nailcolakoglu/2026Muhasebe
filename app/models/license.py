# models/master/license.py (YENİ DOSYA)

from extensions import db
from app.models.master.base import MasterBase
from datetime import datetime, timedelta
import secrets
import hashlib
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class License(MasterBase):
    """Firma Lisans Yönetimi"""
    __tablename__ = 'licenses'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    
    # Lisans Bilgileri
    license_key = db.Column(db.String(64), unique=True, nullable=False)
    license_hash = db.Column(db.String(128), nullable=False)
    license_type = db.Column(db.String(50), nullable=False, default='trial')
    
    # Geçerlilik
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Limitler
    max_users = db.Column(db.Integer, default=5)
    max_monthly_invoices = db.Column(db.Integer, default=100)
    
    # Modüller (JSON - Text olarak sakla)
    _enabled_modules = db.Column('enabled_modules', db.Text, default='[]')
    
    @property
    def enabled_modules(self):
        import json
        try:
            return json.loads(self._enabled_modules) if self._enabled_modules else []
        except:
            return []
    
    @enabled_modules.setter
    def enabled_modules(self, value):
        import json
        self._enabled_modules = json.dumps(value) if value else '[]'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_valid(self):
        """Lisans geçerli mi?"""
        if not self.is_active:
            return False, "Lisans pasif"
        
        if datetime.utcnow() > self.valid_until:
            return False, "Lisans süresi dolmuş"
        
        if not self.verify_license_key():
            return False, "Lisans anahtarı geçersiz"
        
        return True, "Geçerli"
    
    def verify_license_key(self):
        """Hash kontrolü"""
        expected = hashlib.sha256(self.license_key.encode()).hexdigest()
        return self.license_hash == expected
    
    @staticmethod
    def generate_license_key():
        """Yeni anahtar oluştur"""
        return secrets.token_urlsafe(48)[:64]
    
    @staticmethod
    def create_license(tenant, license_type='trial'):
        """Yeni lisans oluştur"""
        key = License.generate_license_key()
        hash_val = hashlib.sha256(key.encode()).hexdigest()
        
        # Tip bazlı ayarlar
        limits = {
            'trial': {
                'days': 30,
                'users': 3,
                'invoices': 50,
                'modules': ['dashboard', 'fatura', 'cari', 'stok']
            },
            'basic': {
                'days': 365,
                'users': 5,
                'invoices': 200,
                'modules': ['dashboard', 'fatura', 'cari', 'stok', 'kasa', 'banka']
            },
            'professional': {
                'days': 365,
                'users': 20,
                'invoices': 1000,
                'modules': ['dashboard', 'fatura', 'cari', 'stok', 'kasa', 'banka', 'muhasebe', 'rapor']
            }
        }
        
        config = limits.get(license_type, limits['trial'])
        
        license = License(
            tenant_id=tenant.id,
            license_key=key,
            license_hash=hash_val,
            license_type=license_type,
            valid_until=datetime.utcnow() + timedelta(days=config['days']),
            max_users=config['users'],
            max_monthly_invoices=config['invoices']
        )
        
        license.enabled_modules = config['modules']
        
        return license
    
    def __repr__(self):
        return f'<License {self.license_type}>'