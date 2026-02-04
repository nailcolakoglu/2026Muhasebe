# app/models/master/user.py

"""
Master User Model
Kimlik Doğrulama ve Yetkilendirme Merkezi (MySQL)
"""
from app.extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask import session
import uuid

# Not: Eski 'ROLES_PERMISSIONS' sözlüğü kaldırıldı.
# Yetkiler artık 'app/services/permission_manager.py' içinden yönetiliyor.

class User(UserMixin, db.Model):
    """Kullanıcı (Master DB - Email Bazlı)"""
    __tablename__ = 'users'
    __bind_key__ = None  # Master DB
    __table_args__ = {'extend_existing': True}
    
    # Kimlik Bilgileri
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profil Bilgileri
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    
    # Durum Bilgileri
    is_active = db.Column(db.Boolean, default=True)
    is_superadmin = db.Column(db.Boolean, default=False)
    
    # Loglama
    last_login = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
    
    # Zaman Damgaları
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    tenant_roles = db.relationship('UserTenantRole', back_populates='user', lazy='dynamic')
    
    # ========================================
    # YENİ PROFESYONEL YETKİ SİSTEMİ (RBAC)
    # ========================================
    def can(self, permission):
        """
        Kullanıcının o anki aktif firmadaki rolüne göre yetkisi var mı?
        Kullanım: if current_user.can('fatura.delete'): ...
        """
        # 1. Süper Admin (SaaS Sahibi) her zaman her şeyi yapar
        if getattr(self, 'is_superadmin', False):
            return True
            
        # 2. Session'dan kullanıcının o firmadaki rolünü al
        # (Login olurken veya firma değiştirirken session'a yazılmıştı)
        from app.services.permission_manager import PermissionManager
        current_role = session.get('tenant_role') # Örn: 'muhasebe', 'depo'
        
        # 3. Manager'a sor: Bu rol, bu işi yapabilir mi?
        return PermissionManager.check(current_role, permission)

    # Eski kod uyumluluğu için (Opsiyonel, silebilirsiniz)
    def is_admin(self):
        return self.is_superadmin or session.get('tenant_role') == 'admin'

    # ========================================
    # STANDART METODLAR
    # ========================================
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def rol(self):
        """Aktif Tenant'daki rolü döndürür (Template helper)"""
        if self.is_superadmin: return 'admin'
        return session.get('tenant_role', 'user')
    
    @property
    def firma_id(self):
        """Firebird tarafındaki firma ID"""
        return session.get('aktif_firma_id')
    
    @property
    def ad_soyad(self):
        return self.full_name
        
    @property
    def kullanici_adi(self):
        if self.email: return self.email.split('@')[0]
        return ""

    def __repr__(self):
        return f'<User {self.email}>'


class UserTenantRole(db.Model):
    """Hangi kullanıcı hangi firmada hangi rolle çalışıyor?"""
    __tablename__ = 'user_tenant_roles'
    __bind_key__ = None
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False, index=True)
    
    role = db.Column(db.String(20), nullable=False, default='user')
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', back_populates='tenant_roles')
    tenant = db.relationship('Tenant', back_populates='user_roles')
    
    def __repr__(self):
        return f'<UserTenantRole {self.user_id} -> {self.tenant_id} ({self.role})>'
    
    @property
    def role_display(self):
        """Rol ismini Türkçe döndür"""
        role_map = {
            'admin':  'Yönetici',
            'patron': 'Patron',
            'muhasebe_muduru': 'Muhasebe Müdürü',
            'finans_muduru': 'Finans Müdürü',
            'bolge_muduru': 'Bölge Müdürü',
            'sube_yoneticisi': 'Şube Yöneticisi',
            'muhasebe': 'Muhasebe',
            'plasiyer': 'Plasiyer',
            'lojistik':  'Lojistik',
            'kasiyer': 'Kasiyer',
            'depo': 'Depo',
            'tezgahtar': 'Tezgahtar',
            'user': 'Kullanıcı'
        }
        return role_map.get(self.role, self.role.title())
