# supervisor/tasks/backup_tasks.py

from extensions import celery, db
from services.backup_engine import BackupEngine
from flask import current_app

@celery.task(bind=True, name='backup.perform')
def task_perform_backup(self, backup_id):
    """
    Arka planda yedekleme işlemini başlatır.
    """
    # Flask context içinde çalıştır
    # Not: Celery worker'da app context otomatik olmayabilir
    
    engine = BackupEngine(backup_id)
    engine.perform_backup()
    return f"Backup {backup_id} completed"

@celery.task(bind=True, name='backup.restore_sandbox')
def task_restore_sandbox(self, backup_id):
    """
    Arka planda sandbox restore işlemi (Uzun sürerse async yapılmalı)
    Ancak kullanıcıyı hemen yönlendirmek için şimdilik senkron da çağrılabilir.
    """
    engine = BackupEngine(backup_id)
    result = engine.restore_to_sandbox()
    return result