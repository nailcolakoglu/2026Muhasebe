# app/utils/tenant_security.py
"""
Tenant Security Utilities
Multi-tenant güvenlik kontrolleri
"""

import logging
from flask import session, g
from app.extensions import db

logger = logging.getLogger(__name__)


def has_tenant_access(user_id, tenant_id):
    """
    Kullanıcının tenant'a erişim hakkı var mı kontrol eder.
    
    Args:
        user_id (str): Kullanıcı UUID
        tenant_id (str): Tenant UUID
        
    Returns:
        bool: Erişim hakkı var mı?
        
    Security:
        - Master DB'de UserTenantRole tablosundan kontrol eder
        - is_active=True olan kayıtları kabul eder
        - Cache kullanılabilir (opsiyonel)
    """
    try:
        from app.models.master import UserTenantRole
        
        # 1. Kullanıcının bu tenant'a aktif rolü var mı?
        role = db.session.query(UserTenantRole).filter_by(
            user_id=user_id,
            tenant_id=tenant_id,
            is_active=True
        ).first()
        
        if role:
            logger.debug(f"✅ Tenant erişim onaylandı: user={user_id}, tenant={tenant_id}, role={role.role}")
            return True
        else:
            logger.warning(f"⚠️ Yetkisiz tenant erişim denemesi: user={user_id}, tenant={tenant_id}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Tenant erişim kontrolü hatası: {e}", exc_info=True)
        return False


def validate_tenant_session():
    """
    Session'daki tenant_id'nin geçerli olduğunu kontrol eder.
    
    Returns:
        tuple: (is_valid: bool, error_message: str|None)
    """
    from flask_login import current_user
    from flask import session
    
    # 1. Session kontrolü
    tenant_id = session.get('tenant_id')
    if not tenant_id:
        logger.debug("⚠️ Session'da tenant_id yok")
        return False, "Lütfen bir firma seçin."
    
    # 2. ✅ Login kontrolü (current_user Flask context içinde olmalı!)
    if not current_user or not current_user.is_authenticated:
        logger.warning("⚠️ current_user authenticated değil")
        return False, "Lütfen giriş yapın."
    
    # 3. ✅ Yetki kontrolü
    if not has_tenant_access(current_user.id, tenant_id):
        logger.warning(f"⚠️ Tenant erişim hakkı yok: user={current_user.id}, tenant={tenant_id}")
        return False, "Bu firmaya erişim yetkiniz yok!"
    
    # 4. Tenant aktif mi?
    try:
        from app.models.master import Tenant
        from app.extensions import db
        
        tenant = db.session.get(Tenant, tenant_id)
        
        if not tenant:
            logger.error(f"❌ Tenant bulunamadı: {tenant_id}")
            return False, "Firma bulunamadı."
        
        if not tenant.is_active:
            logger.warning(f"⚠️ Tenant pasif: {tenant_id}")
            return False, "Bu firma devre dışı bırakılmış."
    
    except Exception as e:
        logger.error(f"❌ Tenant validation hatası: {e}", exc_info=True)
        return False, "Firma doğrulaması başarısız."
    
    return True, None
    
    
def get_user_tenants(user_id):
    """
    Kullanıcının erişim hakkı olan tenant'ları listeler.
    
    Args:
        user_id (str): Kullanıcı UUID
        
    Returns:
        list: Tenant listesi [{id, name, role}, ...]
    """
    try:
        from app.models.master import UserTenantRole, Tenant
        
        # Kullanıcının aktif tenant rolleri
        roles = db.session.query(UserTenantRole).filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        tenants = []
        for role in roles:
            tenant = db.session.get(Tenant, role.tenant_id)
            if tenant and tenant.aktif:
                tenants.append({
                    'id': tenant.id,
                    'name': tenant.name,
                    'code': tenant.kod,
                    'role': role.role,
                    'role_display': get_role_display_name(role.role)
                })
        
        return tenants
    
    except Exception as e:
        logger.error(f"❌ User tenants listesi hatası: {e}", exc_info=True)
        return []


def get_role_display_name(role_code):
    """Rol kodunu görünen isme çevirir"""
    role_names = {
        'admin': 'Yönetici',
        'manager': 'Müdür',
        'user': 'Kullanıcı',
        'viewer': 'Görüntüleyici',
        'accountant': 'Muhasebeci',
        'warehouse': 'Depo Sorumlusu'
    }
    return role_names.get(role_code, role_code.title())