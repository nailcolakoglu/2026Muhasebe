# supervisor/models/backup.py
from app.extensions import db # ✅ TEMİZ IMPORT
from datetime import datetime
import uuid

class Backup(db.Model):
    __tablename__ = 'backups'
    __bind_key__ = 'supervisor' 

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    created_by = db.Column(db.String(36), db.ForeignKey('supervisors.id'))
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_size = db.Column(db.Integer, default=0)
    file_size_mb = db.Column(db.Float, default=0.0)
    compression_ratio = db.Column(db.Float, default=1.0)
    storage_provider = db.Column(db.String(20), default='local')
    remote_path = db.Column(db.String(500))
    is_immutable = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending')
    progress_percent = db.Column(db.Integer, default=0)
    message = db.Column(db.Text)
    error_message = db.Column(db.Text)
    backup_type = db.Column(db.String(20), default='manual')
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0)
    restore_count = db.Column(db.Integer, default=0)
    last_restored_at = db.Column(db.DateTime)
    cloud_status = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)

    # İlişki
    supervisor = db.relationship('Supervisor', backref='backups')
    
    # ... (Propertyler aynı kalabilir) ...
    def __repr__(self):
        return f'<Backup {self.file_name} - {self.status}>'
    
    # ============================================================
    # YARDIMCI ÖZELLİKLER (PROPERTIES)
    # ============================================================
    
    @property
    def status_badge(self):
        """Bootstrap badge rengini döndürür"""
        status_map = {
            'pending': 'secondary',
            'running': 'info',
            'success': 'success',
            'failed':  'danger'
        }
        return status_map.get(self.status, 'secondary')
    
    @property
    def file_size_formatted(self):
        """Dosya boyutunu okunabilir formata çevirir"""
        if self.file_size_mb:
            if self.file_size_mb < 1:
                return f"{self.file_size_mb * 1024:.2f} KB"
            elif self.file_size_mb < 1024:
                return f"{self.file_size_mb:.2f} MB"
            else:
                return f"{self.file_size_mb / 1024:.2f} GB"
        
        if not self.file_size: return "0 MB"
        
        size = self.file_size
        power = 2**10
        n = 0
        power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}"
        
    @property
    def duration_formatted(self):
        """Süreyi dk:sn formatına çevirir"""
        if not self.duration_seconds: return "-"
        m, s = divmod(self.duration_seconds, 60)
        return f"{m}dk {s}sn" if m > 0 else f"{s}sn"