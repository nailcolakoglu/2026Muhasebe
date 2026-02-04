# app/models/master/accounting_period.py

"""
Accounting Period Model (Muhasebe Dönemi)
"""

from app.extensions import db
from datetime import datetime
import uuid


class AccountingPeriod(db.Model):
    """Muhasebe Dönemi"""
    __tablename__ = 'accounting_periods'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # İlişkiler
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False, index=True)
    
    # Dönem Bilgileri
    name = db.Column(db.String(100), nullable=False)  # "2024 Dönemi"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    
    # Durum
    is_active = db.Column(db.Boolean, default=True)
    is_closed = db.Column(db.Boolean, default=False)  # Dönem kapatıldı mı?
    closed_at = db.Column(db.DateTime)
    closed_by = db.Column(db.String(36))
    
    # Tarihler
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    tenant = db.relationship('Tenant', backref='accounting_periods')
    
    def __repr__(self):
        return f'<AccountingPeriod {self.name}>'