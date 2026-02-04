# supervisor/models/notification.py
from app.extensions import db # ✅ TEMİZ IMPORT
from datetime import datetime
import uuid

class Notification(db.Model):
    __tablename__ = 'notifications'
    __bind_key__ = 'supervisor'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    supervisor_id = db.Column(db.String(36), db.ForeignKey('supervisors.id'), index=True)
    tenant_id = db.Column(db.String(36), index=True)
    type = db.Column(db.String(20), nullable=False, index=True)
    category = db.Column(db.String(30), index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    action_url = db.Column(db.String(255))
    action_text = db.Column(db.String(50))
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime)
    is_dismissed = db.Column(db.Boolean, default=False)
    dismissed_at = db.Column(db.DateTime)
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime)
    sms_sent = db.Column(db.Boolean, default=False)
    sms_sent_at = db.Column(db.DateTime)
    priority = db.Column(db.Integer, default=1)
    extra_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime)
    
    supervisor = db.relationship('Supervisor', backref='notifications')
    
    # ... (Metodlar aynı kalabilir) ...
    @staticmethod
    def create(supervisor_id, type, category, title, message, 
               tenant_id=None, action_url=None, action_text=None, priority=1,
               send_email=False, send_sms=False, extra_data=None):
        """
        Bildirim oluştur
        """
        notification = Notification(
            supervisor_id=supervisor_id,
            tenant_id=tenant_id,
            type=type,
            category=category,
            title=title,
            message=message,
            action_url=action_url,
            action_text=action_text,
            priority=priority,
            extra_data=extra_data
        )
        
        try:
            db.session.add(notification)
            db.session.commit()
            
            # Email gönder (arka planda)
            if send_email:
                from tasks.notification_tasks import send_notification_email
                send_notification_email.delay(notification.id)
            
            # SMS gönder (arka planda)
            if send_sms:
                from tasks.notification_tasks import send_notification_sms
                send_notification_sms.delay(notification.id)
            
        except Exception as e:
            print(f"⚠️ Notification oluşturulamadı:  {e}")
            db.session.rollback()
        
        return notification
    
    @property
    def icon(self):
        """Tip için ikon"""
        icon_map = {
            'info': 'bi-info-circle text-info',
            'warning': 'bi-exclamation-triangle text-warning',
            'error':  'bi-x-circle text-danger',
            'success': 'bi-check-circle text-success'
        }
        return icon_map.get(self.type, 'bi-bell')
    
    @property
    def badge_class(self):
        """Tip için badge class"""
        badge_map = {
            'info': 'info',
            'warning': 'warning',
            'error': 'danger',
            'success': 'success'
        }
        return badge_map.get(self.type, 'secondary')
    
    def mark_as_read(self):
        """Okundu olarak işaretle"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<Notification {self.title}>'