# supervisor/models/license_extended.py

import sys
import os
from app.extensions import db
from datetime import datetime

class LicenseExtended(db.Model):
    """
    Lisans Genişletilmiş Bilgiler
    
    Ana License tablosu (app/models/master/license.py) ile ilişkili
    """
    __tablename__ = 'license_extended'
    __bind_key__ = 'supervisor'
    
    id = db.Column(db.String(36), primary_key=True)  # License ID (Foreign Key)
    
    # Faturalama
    monthly_fee = db.Column(db.Float, default=0.0)  # Aylık ücret (TL)
    setup_fee = db.Column(db.Float, default=0.0)  # İlk kurulum ücreti
    discount_percent = db.Column(db.Float, default=0.0)  # İndirim yüzdesi
    
    # Ödeme Bilgileri
    billing_cycle = db.Column(db.String(20), default='monthly')  # monthly, yearly
    next_billing_date = db.Column(db.Date)
    last_payment_date = db.Column(db.Date)
    last_payment_amount = db.Column(db.Float)
    
    # Ödeme Durumu
    payment_status = db.Column(db.String(20), default='paid')  # paid, pending, overdue
    overdue_days = db.Column(db.Integer, default=0)
    
    # Bildirimler
    expiry_notification_sent = db.Column(db.Boolean, default=False)
    expiry_notification_sent_at = db.Column(db.DateTime)
    
    # Otomatik Yenileme
    auto_renew = db.Column(db.Boolean, default=False)
    auto_renew_attempts = db.Column(db.Integer, default=0)
    last_auto_renew_attempt = db.Column(db.DateTime)
    
    # Notlar
    notes = db.Column(db.Text)
    
    # Tarihler
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<LicenseExtended {self.id}>'