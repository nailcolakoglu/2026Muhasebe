# supervisor/models/system_metric.py

import sys
import os
from app.extensions import db
from datetime import datetime


class SystemMetric(db.Model):
    """
    Sistem Metrikleri (Monitoring)
    
    Her dakika (veya 5 dakika) toplanan metrikler: 
    - CPU kullanımı
    - RAM kullanımı
    - Disk kullanımı
    - Firebird bağlantı sayısı
    - Aktif kullanıcı sayısı
    """
    __tablename__ = 'system_metrics'
    __bind_key__ = 'supervisor'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Sistem Metrikleri
    cpu_percent = db.Column(db.Float)  # 0-100
    memory_percent = db.Column(db.Float)  # 0-100
    memory_used_mb = db.Column(db.Float)
    memory_total_mb = db.Column(db.Float)
    
    disk_percent = db.Column(db.Float)  # 0-100
    disk_used_gb = db.Column(db.Float)
    disk_total_gb = db.Column(db.Float)
    
    # Uygulama Metrikleri
    active_tenants = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    active_sessions = db.Column(db.Integer, default=0)
    
    # Veritabanı
    firebird_connections = db.Column(db.Integer, default=0)
    firebird_active_queries = db.Column(db.Integer, default=0)
    
    # Performans
    avg_response_time_ms = db.Column(db.Float)  # Ortalama yanıt süresi
    slow_queries_count = db.Column(db.Integer, default=0)  # >2 saniye sürenler
    
    # Celery (Arka Plan Görevleri)
    celery_active_tasks = db.Column(db.Integer, default=0)
    celery_pending_tasks = db.Column(db.Integer, default=0)
    celery_failed_tasks = db.Column(db.Integer, default=0)
    
    # Zaman
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    @staticmethod
    def collect():
        """
        Sistem metriklerini topla ve kaydet
        
        Bu fonksiyon Celery task tarafından her dakika çağrılır
        """
        import psutil
        
        # Sistem metrikleri
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Uygulama metrikleri (örnek - gerçek değerler hesaplanmalı)
        active_tenants = 0  # TODO: Gerçek değeri hesapla
        active_users = 0
        active_sessions = 0
        
        metric = SystemMetric(
            cpu_percent=cpu,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_total_mb=memory.total / (1024 * 1024),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024 * 1024 * 1024),
            disk_total_gb=disk.total / (1024 * 1024 * 1024),
            active_tenants=active_tenants,
            active_users=active_users,
            active_sessions=active_sessions
        )
        
        try: 
            db.session.add(metric)
            db.session.commit()
        except Exception as e:
            print(f"⚠️ SystemMetric kaydedilemedi:  {e}")
            db.session.rollback()
        
        return metric
    
    @staticmethod
    def cleanup_old_metrics(days=7):
        """Eski metrikleri temizle (günlük çalıştırılır)"""
        from datetime import timedelta
        
        threshold = datetime.utcnow() - timedelta(days=days)
        
        deleted = SystemMetric.query.filter(
            SystemMetric.created_at < threshold
        ).delete()
        
        db.session.commit()
        
        return deleted
    
    def __repr__(self):
        return f'<SystemMetric CPU:{self.cpu_percent}% MEM:{self.memory_percent}%>'