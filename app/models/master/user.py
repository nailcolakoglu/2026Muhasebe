# app/models/master/user.py

"""
Master User Model
Kimlik Doğrulama ve Yetkilendirme Merkezi (MySQL)
"""
from app.extensions import db
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask import session
import uuid
import logging

logger = logging.getLogger(__name__)


class User(UserMixin, db.Model):
    """Kullanıcı (Master DB - Email Bazlı)"""
    __tablename__ = 'users'
    __bind_key__ = None
    __table_args__ = {'extend_existing': True}
    
    # ============================================
    # TEMEL ALANLAR
    # ============================================
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profil
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    
    # Durum
    is_active = db.Column(db.Boolean, default=True)
    is_superadmin = db.Column(db.Boolean, default=False)
    
    # Loglama
    last_login = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
    
    # Zaman
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    tenant_roles = db.relationship('UserTenantRole', back_populates='user', lazy='dynamic')
    
    
    # ============================================
    # ŞİFRE YÖNETİMİ
    # ============================================
    
    def set_password(self, password):
        """Şifreyi hashle"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Şifre kontrolü"""
        return check_password_hash(self.password_hash, password)
    
    
    # ============================================
    # YETKİ KONTROLÜ (PermissionManager Entegrasyonu)
    # ============================================
    
    def has_permission(self, permission):
        """
        ✅ PermissionManager kullanarak yetki kontrolü
        
        Decorator uyumluluğu:
            @permission_required('bolge_guncelle')
            ↓
            current_user.has_permission('bolge_guncelle')
        
        Args:
            permission (str): Yetki kodu
                Örnekler:
                - 'bolge_olustur', 'bolge_guncelle', 'bolge_sil'
                - 'stok.create', 'fatura.view', 'cari.delete'
        
        Returns:
            bool: Yetki var mı?
        """
        from app.services.permission_manager import PermissionManager
        
        # 1. ✅ Superadmin her şeyi yapabilir
        if self.is_superadmin:
            logger.debug(f"✅ Superadmin yetki: {permission}")
            return True
        
        # 2. ✅ Session'daki rol
        current_role = session.get('tenant_role', 'user')
        
        # 3. ✅ PermissionManager'a sor
        has_access = PermissionManager.check(current_role, permission)
        
        if has_access:
            logger.debug(f"✅ Yetki onaylandı: user={self.email}, permission={permission}, role={current_role}")
        else:
            logger.warning(f"⚠️ Yetki reddedildi: user={self.email}, permission={permission}, role={current_role}")
        
        return has_access
    
    
    def can(self, permission):
        """
        ✅ Alias: has_permission() ile aynı
        
        Kullanım (template'lerde):
            {% if current_user.can('fatura.delete') %}
                <button>Sil</button>
            {% endif %}
        
        Args:
            permission (str): Yetki kodu
        
        Returns:
            bool: Yetki var mı?
        """
        return self.has_permission(permission)
    
    
    def get_permissions(self):
        """
        Kullanıcının tüm yetkilerini listeler.
        
        Returns:
            list: Yetki kodları listesi
        """
        from app.services.permission_manager import PermissionManager
        
        if self.is_superadmin:
            return ['*']
        
        current_role = session.get('tenant_role', 'user')
        return PermissionManager.ROLE_DEFINITIONS.get(current_role, [])
    
    
    def can_access_tenant(self, tenant_id):
        """
        Kullanıcının belirli bir tenant'a erişim hakkı var mı?
        
        Args:
            tenant_id (str): Tenant UUID
        
        Returns:
            bool: Erişim hakkı var mı?
        """
        if self.is_superadmin:
            return True
        
        role = self.tenant_roles.filter_by(
            tenant_id=tenant_id,
            is_active=True
        ).first()
        
        return role is not None
    
    
    # ============================================
    # HELPER PROPERTIES (Template & Geriye Uyumluluk)
    # ============================================
    
    @property
    def rol(self):
        """Aktif tenant'daki rol (template için)"""
        if self.is_superadmin:
            return 'admin'
        return session.get('tenant_role', 'user')
    
    @property
    def firma_id(self):
        """Aktif firma ID (tenant_id)"""
        return session.get('tenant_id')
    
    @property
    def ad_soyad(self):
        """Tam ad (geriye uyumluluk)"""
        return self.full_name
    
    @property
    def kullanici_adi(self):
        """Email'den kullanıcı adı"""
        if self.email:
            return self.email.split('@')[0]
        return ""
    
    def is_admin(self):
        """Admin kontrolü (geriye uyumluluk)"""
        return self.is_superadmin or session.get('tenant_role') == 'admin'
    
    
    # ============================================
    # FLASK-LOGIN GEREKLİ METODLARı
    # ============================================
    
    @property
    def is_authenticated(self):
        """Authenticated mı?"""
        return True
    
    @property
    def is_anonymous(self):
        """Anonim mi?"""
        return False
    
    def get_id(self):
        """User ID (Flask-Login için)"""
        return str(self.id)
    
    
    # ============================================
    # YARDIMCI METODLAR
    # ============================================
    
    def update_last_login(self):
        """Son giriş zamanını güncelle"""
        self.last_login = datetime.now(timezone.utc)
        db.session.commit()
    
    def to_dict(self):
        """JSON serialization"""
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_superadmin': self.is_superadmin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f'<User {self.email}>'


# ============================================
# USER TENANT ROLE (İlişki Tablosu)
# ============================================

class UserTenantRole(db.Model):
    """Kullanıcı - Tenant - Rol İlişkisi"""
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
            'admin': 'Yönetici',
            'patron': 'Patron',
            'muhasebe_muduru': 'Muhasebe Müdürü',
            'finans_muduru': 'Finans Müdürü',
            'bolge_muduru': 'Bölge Müdürü',
            'sube_yoneticisi': 'Şube Yöneticisi',
            'muhasebe': 'Muhasebe',
            'muhasebeci': 'Muhasebeci',
            'plasiyer': 'Plasiyer',
            'lojistik': 'Lojistik',
            'kasiyer': 'Kasiyer',
            'depo': 'Depo Sorumlusu',
            'depo_sorumlusu': 'Depo Sorumlusu',
            'satis_temsilcisi': 'Satış Temsilcisi',
            'tezgahtar': 'Tezgahtar',
            'user': 'Kullanıcı',
            'viewer': 'Görüntüleyici'
        }
        return role_map.get(self.role, self.role.title())