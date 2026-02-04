# app/models/backup.py

from app.extensions import db
from datetime import datetime
import uuid

class Backup(db.Model):
    """
    Yedekleme Geçmişi Modeli
    """
    __tablename__ = 'backups'
    __bind_key__ = None # Master DB (Supervisor ve App ortak kullanır)

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    
    # Dosya Bilgileri (Artık Nullable)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    
    # Boyut Bilgileri
    file_size = db.Column(db.Integer, default=0) # Byte cinsinden (Eski sistem için)
    file_size_mb = db.Column(db.Float, default=0.0) # MB cinsinden (Yeni sistem - Hata veren kısım buydu)
    
    # Performans
    compression_ratio = db.Column(db.Float, default=1.0)
    
    # Depolama
    storage_provider = db.Column(db.String(20), default='local')
    remote_path = db.Column(db.String(500))
    is_immutable = db.Column(db.Boolean, default=False)
    
    # Durum: pending, running, success, failed
    status = db.Column(db.String(20), default='pending')
    progress_percent = db.Column(db.Integer, default=0)
    message = db.Column(db.Text) # Hata mesajı veya not
    error_message = db.Column(db.Text)
    
    # Tür: manual, auto, system
    backup_type = db.Column(db.String(20), default='manual')
    
    # Zamanlama
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0)
    
    # Geri Yükleme İstatistikleri
    restore_count = db.Column(db.Integer, default=0)
    last_restored_at = db.Column(db.DateTime)
    
    # Bulut Durumu (Legacy - Eski kodlarla uyum için)
    cloud_status = db.Column(db.String(500))
    
    # Meta
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.String(36)) # İşlemi başlatan kullanıcı ID

    # İlişki
    tenant = db.relationship('Tenant', backref=db.backref('backups', lazy=True))

    def __repr__(self):
        return f'<Backup {self.file_name} - {self.status}>'
    
    # ============================================================
    # ŞABLON (JINJA2) İÇİN YARDIMCI ÖZELLİKLER (PROPERTIES)
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
        """Dosya boyutunu okunabilir formata çevirir (KB, MB, GB)"""
        # Eğer MB değeri varsa onu kullan
        if self.file_size_mb:
            if self.file_size_mb < 1:
                return f"{self.file_size_mb * 1024:.2f} KB"
            elif self.file_size_mb < 1024:
                return f"{self.file_size_mb:.2f} MB"
            else:
                return f"{self.file_size_mb / 1024:.2f} GB"
        
        # Yoksa Byte değerinden hesapla
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