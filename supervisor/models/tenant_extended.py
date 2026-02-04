# supervisor/models/tenant_extended.py

import sys
import os

# ==========================================
# PATH AYARLARI (GÜVENLİ)
# ==========================================
# Mevcut: supervisor/models/tenant_extended.py
# Hedef: Proje Kök Dizini (MuhMySQL/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '../../'))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ✅ TEKİL DB NESNESİ
from app.extensions import db
from datetime import datetime

class TenantExtended(db.Model):
    """
    Tenant Genişletilmiş Bilgiler (Supervisor için)
    Ana Tenant tablosu ile ilişkili
    """
    __tablename__ = 'tenant_extended'
    __bind_key__ = 'supervisor'
    
    id = db.Column(db.String(36), primary_key=True)  # Tenant ID (Foreign Key)
    
    # İstatistikler (Cache)
    total_users = db.Column(db.Integer, default=0)
    active_sessions = db.Column(db.Integer, default=0)
    total_invoices = db.Column(db.Integer, default=0)
    total_customers = db.Column(db.Integer, default=0)
    total_products = db.Column(db.Integer, default=0)
    storage_used_mb = db.Column(db.Float, default=0.0)
    
    # Kullanım İstatistikleri (Aylık)
    monthly_invoice_count = db.Column(db.Integer, default=0)
    monthly_transaction_count = db.Column(db.Integer, default=0)
    last_stats_update = db.Column(db.DateTime)
    stats_reset_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Aktivite
    last_activity_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    last_backup_at = db.Column(db.DateTime)
    
    # Notlar (Supervisor için)
    notes = db.Column(db.Text)
    tags = db.Column(db.String(255))
    
    # Özel Ayarlar
    custom_settings = db.Column(db.Text)
    
    # Tarihler
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TenantExtended {self.id}>'