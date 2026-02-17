# modules/rapor/models.py

import uuid
import json 
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin, FirebirdModelMixin
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSON, UUID
from datetime import datetime
import logging 

logger = logging.getLogger(__name__)

def generate_uuid():
    return str(uuid.uuid4())

class YazdirmaSablonu(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'yazdirma_sablonlari'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=True) # Null ise Sistem Varsayılanıdır
    
    # Belge Türü: 'fatura', 'tahsilat', 'tediye', 'stok_fisi', 'cari_ekstre', 'mutabakat'
    belge_turu = db.Column(db.String(50), nullable=False) 
    
    baslik = db.Column(db.String(100), nullable=False) # Örn: "Logolu Fatura Tasarımı"
    
    # HTML ve CSS şablonu (Jinja2 formatında saklanır)
    html_icerik = db.Column(db.Text, nullable=False)
    css_icerik = db.Column(db.Text, nullable=True)
    
    aktif = db.Column(db.Boolean, default=True)
    varsayilan = db.Column(db.Boolean, default=False) # O firmanın varsayılanı mı?

    # İlişki (Firmaya bağla)
    firma = db.relationship('Firma', backref='sablonlar')


# ===================================
# SAVED REPORT (Firebird)
# ===================================
class SavedReport(db.Model, FirebirdModelMixin):
    """
    Kullanıcı tarafından kaydedilen raporlar (Firebird)
    
    Kullanım:
        SavedReport.query_fb().filter_by(user_id=user_id).all()
    """
    
    __tablename__ = 'SAVED_REPORTS'
    __bind_key__ = None
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    model_name = db.Column(db.String(100), nullable=False)
    config_json = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(36), nullable=False)
    
    # ✅ Firebird boolean (SMALLINT 0/1)
    is_public = db.Column(db.SmallInteger, default=0)  # ✅ Boolean yerine SmallInteger
    schedule_enabled = db.Column(db.SmallInteger, default=0)
    
    schedule_cron = db.Column(db.String(100))
    schedule_email_to = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = db.Column(db.DateTime)
    run_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<SavedReport {self.name}>'
    
    @property
    def config(self):
        """JSON string'i dict'e çevir"""
        if not self.config_json:
            return {}
        
        try:
            return json.loads(self.config_json)
        except Exception as e:
            logger.error(f"Config parse hatası (ID={self.id}): {e}")
            return {}
    
    @config.setter
    def config(self, value):
        """Dict'i JSON string'e çevir"""
        if value is None:
            self.config_json = '{}'
            return
        
        try:
            self.config_json = json.dumps(value, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Config set hatası: {e}")
            raise ValueError(f"Config JSON'a çevrilemedi: {e}")
    
    # ✅ Boolean helper property
    @property
    def is_public_bool(self):
        """SmallInteger'ı boolean'a çevir"""
        return bool(self.is_public)
    
    @property
    def schedule_enabled_bool(self):
        """SmallInteger'ı boolean'a çevir"""
        return bool(self.schedule_enabled)
    
    def to_dict(self):
        """API için dict formatı"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'model_name': self.model_name,
            'config': self.config,
            'is_public': self.is_public_bool,  # ✅ Boolean olarak döndür
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'run_count': self.run_count or 0
        }
    
        
    # ===================================
    # KULLANIM ÖRNEKLERİ (DOCSTRING)
    # ===================================
    """
    KULLANIM:
    
    # ❌ YANLIŞ (MySQL session kullanır):
    SavedReport.query.filter_by(user_id=user_id).all()
    
    # ✅ DOĞRU (Firebird session):
    SavedReport.query_fb().filter_by(user_id=user_id).all()
    
    # ✅ ALTERNATİF (Manuel):
    tenant_db = get_tenant_db()
    tenant_db.query(SavedReport).filter_by(user_id=user_id).all()
    """