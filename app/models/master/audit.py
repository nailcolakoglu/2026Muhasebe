# models/master/audit.py (DÜZELTİLMİŞ)

from app.extensions import db
from app.models.master.base import MasterBase
from datetime import datetime

class AuditLog(MasterBase):
    """Sistem Güvenlik ve Aktivite Logları"""
    __tablename__ = 'audit_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), index=True)
    
    # Olay
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.String(36))
    
    # HTTP
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    
    # Durum
    status = db.Column(db.String(20), default='success')
    error_message = db.Column(db.Text)
    
    # Zaman
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # İlişkiler
    tenant = db.relationship('Tenant', backref='audit_logs')
    user = db.relationship('User', backref='audit_logs')
    
    @staticmethod
    def log(action, user_id=None, tenant_id=None, resource_type=None,
            resource_id=None, status='success', error_message=None, request=None):
        """
        Log kaydı oluştur
        
        NOT: Flask context dışında çağrılırsa hata vermez, sadece request bilgisi olmaz
        """
        # ✅ Flask context kontrolü
        try:
            from flask import request as flask_request, has_request_context
            
            if has_request_context():
                req = request or flask_request
                ip = req.remote_addr if req else None
                agent = req.headers.get('User-Agent') if req else None
            else:
                ip = None
                agent = None
        except: 
            ip = None
            agent = None
        
        log = AuditLog(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_message=error_message,
            ip_address=ip,
            user_agent=agent
        )
        
        # ✅ Try-except ile güvenli kayıt
        try:
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            # Log kaydedilemezse sessizce devam et (kritik değil)
            print(f"⚠️ AuditLog kaydedilemedi: {e}")
            db.session.rollback()
        
        return log
    
    def __repr__(self):
        return f'<AuditLog {self.action} - {self.status}>'