# models/master_active_session.py

from app.extensions import db
from datetime import datetime
import uuid

class MasterActiveSession(db.Model):
    """
    MySQL tarafında aktif oturumları takip eder.
    Aynı lisansın kaç farklı yerden kullanıldığını denetlemek için kullanılır.
    """
    __tablename__ = 'master_active_sessions'
    __bind_key__ = None  # Master DB (MySQL/SQLite) üzerinden çalışır
    
    # ID'yi String(UUID) yapıyoruz, eski int yapısını değiştiriyoruz
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Flask session'daki benzersiz token (Eski session_id yerine bunu kullanıyoruz)
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    
    # Yeni Eklenen Alanlar (Hata veren kısımlar)
    ip_address = db.Column(db.String(45))  # IPv6 desteği için 45
    user_agent = db.Column(db.String(255)) # Tarayıcı bilgisi
    
    login_at = db.Column(db.DateTime, default=datetime.now)
    last_activity = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    user = db.relationship('User', backref='active_sessions', lazy='joined')
    tenant = db.relationship('Tenant', backref='active_sessions', lazy='joined')
    
    def __repr__(self):
        return f"<MasterSession {self.user_id} @ {self.ip_address}>"