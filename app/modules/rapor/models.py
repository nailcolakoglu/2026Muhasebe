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


# ===================================
# SCHEDULED REPORT
# ===================================
class ScheduledReport(db.Model):
    """
    Zamanlanmış raporlar - otomatik çalışıp e-posta gönderir.
    """
    __tablename__ = 'scheduled_reports'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    report_config = db.Column(db.Text, nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    schedule_type = db.Column(db.String(20), nullable=False, default='daily')
    recipients = db.Column(db.Text, nullable=False, default='[]')
    export_format = db.Column(db.String(20), nullable=False, default='excel')
    user_id = db.Column(db.String(36), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime)
    next_run_at = db.Column(db.DateTime)
    run_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f'<ScheduledReport {self.id} ({self.schedule_type})>'

    def to_dict(self) -> dict:
        """API için dict formatı."""
        return {
            'id': self.id,
            'model_name': self.model_name,
            'schedule_type': self.schedule_type,
            'recipients': json.loads(self.recipients or '[]'),
            'export_format': self.export_format,
            'user_id': self.user_id,
            'is_active': self.is_active,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
            'run_count': self.run_count or 0,
        }


# ===================================
# REPORT PERMISSION
# ===================================
class ReportPermission(db.Model):
    """
    Rapor erişim izinleri - hangi kullanıcı hangi raporu görebilir/düzenleyebilir.
    """
    __tablename__ = 'report_permissions'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    report_id = db.Column(db.String(36), db.ForeignKey('saved_reports.id'), nullable=False)
    user_id = db.Column(db.String(36), nullable=False)
    can_view = db.Column(db.Boolean, default=True)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    report = db.relationship('SavedReport', backref='permissions')

    def __repr__(self) -> str:
        return f'<ReportPermission report={self.report_id} user={self.user_id}>'


# ===================================
# REPORT VERSION
# ===================================
class ReportVersion(db.Model):
    """
    Rapor konfigürasyonu versiyon geçmişi.
    """
    __tablename__ = 'report_versions'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    report_id = db.Column(db.String(36), db.ForeignKey('saved_reports.id'), nullable=False)
    config_json = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(36), nullable=False)
    change_note = db.Column(db.String(500), default='')
    version_number = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    report = db.relationship('SavedReport', backref='versions')

    def __repr__(self) -> str:
        return f'<ReportVersion report={self.report_id} v{self.version_number}>'


# ===================================
# REPORT USAGE LOG
# ===================================
class ReportUsageLog(db.Model):
    """
    Rapor kullanım istatistikleri - analytics için.
    """
    __tablename__ = 'report_usage_logs'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    report_id = db.Column(db.String(36), db.ForeignKey('saved_reports.id'), nullable=True)
    user_id = db.Column(db.String(36), nullable=False)
    execution_time = db.Column(db.Float, default=0.0)
    row_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f'<ReportUsageLog report={self.report_id} user={self.user_id}>'