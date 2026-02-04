# models/master/license.py (DÜZELTME)

from app.extensions import db
from datetime import datetime
import uuid
import secrets


class License(db.Model):
    """Lisans Yönetimi"""
    __tablename__ = 'licenses'
    __bind_key__ = None  # Master DB
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False, index=True)
    
    # ✅ license_key artık opsiyonel (nullable=True)
    license_key = db.Column(db.String(100), unique=True, nullable=True)  # DÜZELTME
    license_hash = db.Column(db.String(255), nullable=True)
    
    # 👇 EKLENMESİ GEREKEN ALAN (DONANIM KİLİDİ İÇİN)
    hardware_id = db.Column(db.String(255), nullable=True)
    
    # Lisans Tipi
    license_type = db.Column(db.String(20), nullable=False, default='trial')  # trial, basic, professional, enterprise
    
    # Geçerlilik
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime, nullable=False)
    
    # Durum
    is_active = db.Column(db.Boolean, default=True)
    is_suspended = db.Column(db.Boolean, default=False)
    suspension_reason = db.Column(db.String(255))
    
    # Limitler
    max_users = db.Column(db.Integer, default=5)
    max_monthly_invoices = db.Column(db.Integer, default=100)
    max_monthly_transactions = db.Column(db.Integer, default=1000)
    max_storage_mb = db.Column(db.Integer, default=500)
    max_branches = db.Column(db.Integer, default=1)
    
    # Modül Erişimi (JSON)
    enabled_modules = db.Column(db.String(500), default='[]')  # ['fatura', 'stok', 'cari']
    
    # Online Kontrol
    last_online_check = db.Column(db.DateTime)
    offline_grace_days = db.Column(db.Integer, default=7)
    
    # İstatistikler
    current_user_count = db.Column(db.Integer, default=0)
    current_month_invoice_count = db.Column(db.Integer, default=0)
    current_storage_mb = db.Column(db.Integer, default=0)
    stats_reset_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Tarihler
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(36))
    
    # Notlar
    notes = db.Column(db.Text)
    
    # İlişkiler
    tenant = db.relationship('Tenant', back_populates='licenses')
    
    def __repr__(self):
        return f'<License {self.license_type} - {self.tenant_id}>'
    
    def generate_license_key(self):
        """Lisans anahtarı oluştur"""
        if not self.license_key:
            self.license_key = f"LIC-{secrets.token_hex(16).upper()}"
        return self.license_key
    
    @property
    def is_valid(self):
        """Lisans geçerli mi?"""
        if not self.is_active or self.is_suspended:
            return False
        
        # ✅ Her iki tarih de datetime.now() ile karşılaştırılıyor
        now = datetime.now()  # timezone-naive
        
        # valid_from ve valid_until de timezone-naive olmalı
        return self.valid_from <= now <= self.valid_until

    
    @property
    def days_remaining(self):
        """Kalan gün sayısı"""
        if not self.is_valid:
            return 0
        
        # ✅ Aynı datetime.now() kullan
        delta = self.valid_until - datetime.now()
        return max(0, delta.days)