# supervisor/models/setting.py

from app.extensions import db
from datetime import datetime

class Setting(db.Model):
    """Sistem Ayarları (Key-Value Store)"""
    __tablename__ = 'settings'
    __bind_key__ = 'supervisor'
    
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text) # JSON veya düz metin
    description = db.Column(db.String(200))
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        setting = Setting.query.get(key)
        return setting.value if setting else default

    @staticmethod
    def set(key, value, description=None):
        setting = Setting.query.get(key)
        if not setting:
            setting = Setting(key=key)
            db.session.add(setting)
        
        setting.value = str(value)
        if description:
            setting.description = description
        
        db.session.commit()
        return setting