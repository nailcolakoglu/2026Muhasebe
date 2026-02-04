# supervisor/models/supervisor.py
from app.extensions import db  # ✅ TEMİZ IMPORT
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import uuid
import json

class Supervisor(UserMixin, db.Model):
    __tablename__ = 'supervisors'
    __bind_key__ = 'supervisor'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(255))
    role = db.Column(db.String(20), default='admin')
    permissions = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
    last_activity = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def has_full_access(self):
        return self.role == 'super_admin'
    
    def has_permission(self, permission):
        if self.has_full_access: return True
        if not self.permissions: return False
        try:
            perms = json.loads(self.permissions)
            return permission in perms
        except: return False
    
    def __repr__(self):
        return f'<Supervisor {self.username}>'