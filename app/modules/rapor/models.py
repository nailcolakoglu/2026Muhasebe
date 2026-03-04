# app/modules/rapor/models.py

import uuid
import json 
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
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

class AIRaporAyarlari(db.Model):
    __tablename__ = 'ai_rapor_ayarlari'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    anahtar = db.Column(db.String(50), nullable=False)
    deger = db.Column(db.String(50), nullable=False)
    aciklama = db.Column(db.String(200))
    
    __table_args__ = (
        db.UniqueConstraint('firma_id', 'anahtar', name='uq_ai_ayar'),
        {'extend_existing': True}
    )


class AIRaporGecmisi(db.Model):
    __tablename__ = 'ai_rapor_gecmisi'
    query_class = FirmaFilteredQuery
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    tarih = db.Column(db.DateTime, server_default=db.func.now())
    rapor_turu = db.Column(db.String(50))
    baslik = db.Column(db.String(200))
    html_icerik = db.Column(db.Text)
    ham_veri_json = db.Column(db.Text)


# ===================================
# SAVED REPORT (MySQL/PostgreSQL Uyumlu)
# ===================================
class SavedReport(db.Model):
    """
    Kullanıcı tarafından kaydedilen raporlar
    """
    __tablename__ = 'saved_reports'
    
    # 🔥 DÜZELTME 1: Proje standardı olan UUID yapısına geçirildi
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    model_name = db.Column(db.String(100), nullable=False)
    config_json = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(36), nullable=False)
    
    # 🔥 DÜZELTME 2: Firebird'ün SmallInteger zorunluluğu kalktı, gerçek Boolean'a dönüldü
    is_public = db.Column(db.Boolean, default=False)
    schedule_enabled = db.Column(db.Boolean, default=False)
    
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
    
    def to_dict(self):
        """API için dict formatı"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'model_name': self.model_name,
            'config': self.config,
            'is_public': self.is_public,  # Dönüştürmeye gerek kalmadı, zaten Boolean
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