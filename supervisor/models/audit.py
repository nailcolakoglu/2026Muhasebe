# supervisor/models/audit.py
from app.extensions import db  # ✅ TEMİZ IMPORT
from datetime import datetime
import uuid
from .supervisor import Supervisor # ✅ MODEL REFERANSI İÇİN

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    __bind_key__ = 'supervisor'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # ✅ String referans artık güvenli çünkü db nesnesi aynı
    supervisor_id = db.Column(db.String(36), db.ForeignKey('supervisors.id'), index=True, nullable=True)
    supervisor_username = db.Column(db.String(80))
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50), index=True)
    resource_id = db.Column(db.String(36), index=True)
    description = db.Column(db.String(500))
    changes = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='success')
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    # İlişki
    supervisor = db.relationship('Supervisor', backref=db.backref('audit_logs', lazy=True))
    
    # ... (Log metodu ve propertyler aynı kalabilir) ...
    @staticmethod
    def log(action, supervisor=None, resource_type=None, resource_id=None, 
            description=None, changes=None, status='success', error_message=None, request=None):
        """Audit log oluşturucu"""
        from flask import request as flask_request, has_request_context
        
        # Request context'i güvenli şekilde al
        if has_request_context():
            req = request or flask_request
            ip = req.remote_addr
            agent = req.headers.get('User-Agent')
            method = req.method
            path = req.path
        else:
            ip = agent = method = path = None
        
        # Changes verisini JSON string'e çevir
        changes_json = None
        if changes:
            try:
                changes_json = json.dumps(changes, ensure_ascii=False)
            except:
                changes_json = str(changes)
        
        log = AuditLog(
            supervisor_id=supervisor.id if supervisor else None,
            supervisor_username=supervisor.username if supervisor else 'system',
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            description=description,
            changes=changes_json,
            ip_address=ip,
            user_agent=agent,
            request_method=method,
            request_path=path,
            status=status,
            error_message=error_message
        )
        
        try:
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"⚠️ AuditLog kaydedilemedi: {e}")
            db.session.rollback()
        
        return log
    
    @property
    def status_badge(self):
        status_map = {'success': 'success', 'failed': 'danger', 'warning': 'warning'}
        return status_map.get(self.status, 'secondary')
    
    @property
    def action_icon(self):
        action_map = {
            'tenant.create': 'bi-plus-circle text-success',
            'tenant.update': 'bi-pencil text-warning',
            'tenant.delete': 'bi-trash text-danger',
            'tenant.suspend': 'bi-pause-circle text-warning',
            'tenant.activate': 'bi-play-circle text-success',
            'license.create': 'bi-key text-success',
            'license.update': 'bi-key text-warning',
            'user.login': 'bi-box-arrow-in-right text-info',
        }
        return action_map.get(self.action, 'bi-circle text-secondary')