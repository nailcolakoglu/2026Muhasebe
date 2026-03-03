# app/decorators.py

"""
Güvenlik ve Yetkilendirme Decorator'ları

Kullanım Örnekleri:
    @login_required
    @tenant_route
    @protected_route  # login + tenant
    @permission_required('stok.create')
    @role_required(['admin', 'manager'])
    @audit_log('stok', 'create')
    @superadmin_required
"""

from functools import wraps
from flask import abort, flash, redirect, url_for, request, session, g, current_app
from flask_login import current_user
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# 1. KİMLİK DOĞRULAMA DECORATOR'LARI
# ============================================================================

def login_required(f):
    """
    Kullanıcı login olmalı (Flask-Login ile entegre).
    
    Kullanım:
        @login_required
        def protected_route():
            ...
    
    Returns:
        function: Korumalı fonksiyon
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⛔ Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def tenant_route(f):
    """
    ✅ GÜVENLİ TENANT DECORATOR
    
    ÖNEML İ: Bu decorator içinde login kontrolü var,
    @login_required gereksiz!
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.utils.tenant_security import validate_tenant_session
        from flask_login import current_user
        
        # 1. ✅ Login kontrolü (current_user Flask-Login'den geliyor)
        if not current_user.is_authenticated:
            logger.warning(f"⚠️ Login gerekli: {request.path}")
            flash("⛔ Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        
        # 2. ✅ Tenant validation
        is_valid, error_message = validate_tenant_session()
        
        if not is_valid:
            logger.warning(f"⚠️ Tenant validation başarısız: {error_message}")
            flash(f"⚠️ {error_message}", "danger")
            session.pop('tenant_id', None)
            return redirect(url_for('auth.select_tenant'))
        
        # 3. Tenant metadata kontrolü
        if not hasattr(g, 'tenant_metadata') or not g.tenant_metadata:
            logger.warning(
                f"⚠️ Tenant metadata yok: user={current_user.id}, "
                f"tenant={session.get('tenant_id')}"
            )
            flash("❌ Firma bilgileri yüklenemedi. Lütfen tekrar seçin.", "danger")
            session.pop('tenant_id', None)
            return redirect(url_for('auth.select_tenant'))
        
        return f(*args, **kwargs)
    
    return decorated_function
    
    
# Geriye uyumluluk için alias
tenant_required = tenant_route


# ============================================================================
# 2. YETKİLENDİRME DECORATOR'LARI
# ============================================================================

def permission_required(permission):
    """
    Route'u yetkiye göre korur.
    
    Kullanım:
        @permission_required('stok.create')
        @permission_required('fatura.delete')
        
    Args:
        permission (str): Yetki kodu (format: 'module.action')
        
    Returns:
        function: Korumalı fonksiyon
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Login kontrolü
            if not current_user.is_authenticated:
                abort(401)
            
            # 2. Permission kontrolü
            if not current_user.has_permission(permission):
                logger.warning(
                    f"⚠️ Yetkisiz erişim: user={current_user.id}, "
                    f"permission={permission}, path={request.path}"
                )
                abort(403, f"Bu işlem için '{permission}' yetkisi gerekli!")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(*roles):
    """
    Route'u role göre korur.
    
    Kullanım:
        @role_required('admin', 'manager')
        def yonetim_paneli():
            ...
    
    Args:
        *roles: İzin verilen rol isimleri
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            user_role = session.get('tenant_role', 'user')
            
            if user_role not in roles:
                logger.warning(
                    f"⚠️ Yetkisiz rol erişimi: user={current_user.id}, "
                    f"role={user_role}, required={roles}"
                )
                abort(403, f"Bu sayfa sadece {', '.join(roles)} rollerine açıktır!")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# 3. ROUTE KORUMA DECORATOR'LARI (Alias & Helpers)
# ============================================================================

def protected_route(f):
    """
    Route'u hem login hem de tenant kontrolü ile korur.
    
    ✅ DÜZELTİLDİ: Application context hatası çözüldü
    
    Kullanım:
        @protected_route  # ← Parametre almaz!
        def sube_listesi():
            ...
    
    Equivalent to:
        @login_required
        @tenant_route
        def sube_listesi():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ✅ BURADA current_user kontrol edilir (runtime'da)
        
        # 1. Login kontrolü
        if not current_user.is_authenticated:
            flash("⛔ Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        
        # 2. Tenant kontrolü
        from app.utils.tenant_security import validate_tenant_session
        
        is_valid, error_message = validate_tenant_session()
        
        if not is_valid:
            flash(f"⚠️ {error_message}", "danger")
            session.pop('tenant_id', None)
            return redirect(url_for('auth.select_tenant'))
        
        # 3. Tenant metadata kontrolü
        if not hasattr(g, 'tenant_metadata') or not g.tenant_metadata:
            logger.warning(f"⚠️ Tenant metadata yok: user={current_user.id}, tenant={session.get('tenant_id')}")
            flash("❌ Firma bilgileri yüklenemedi. Lütfen tekrar seçin.", "danger")
            session.pop('tenant_id', None)
            return redirect(url_for('auth.select_tenant'))
        
        return f(*args, **kwargs)
    
    return decorated_function



# ============================================================================
# 4. AUDIT LOG DECORATOR
# ============================================================================

def audit_log(module, action):
    """
    İşlem logunu kaydet (Audit Trail).
    
    Kullanım:
        @audit_log('stok', 'create')
        def stok_ekle():
            ...
    
    Args:
        module (str): Modül adı (örn: 'stok', 'fatura')
        action (str): İşlem türü (örn: 'create', 'update', 'delete')
    
    Logs:
        - Kullanıcı ID
        - Tenant ID
        - Timestamp
        - IP Address
        - User Agent
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # İşlem öncesi log
            log_data = {
                'module': module,
                'action': action,
                'user_id': current_user.id if current_user.is_authenticated else None,
                'tenant_id': session.get('tenant_id'),
                'ip_address': request.remote_addr,
                'user_agent': request.user_agent.string,
                'timestamp': datetime.now(timezone.utc),
                'path': request.path,
                'method': request.method
            }
            
            logger.info(
                f"📝 AUDIT: {module}.{action} | "
                f"User: {log_data['user_id']} | "
                f"Tenant: {log_data['tenant_id']} | "
                f"IP: {log_data['ip_address']}"
            )
            
            # İşlemi çalıştır
            try:
                result = f(*args, **kwargs)
                
                # Başarılı log
                logger.info(f"✅ AUDIT SUCCESS: {module}.{action}")
                
                return result
            
            except Exception as e:
                # Hata logu
                logger.error(
                    f"❌ AUDIT FAILED: {module}.{action} | Error: {e}",
                    exc_info=True
                )
                raise
        
        return decorated_function
    return decorator


# ============================================================================
# 5. SUPERADMIN REQUIRED
# ============================================================================

def superadmin_required(f):
    """
    Sadece superadmin erişebilir.
    
    Kullanım:
        @superadmin_required
        def sistem_ayarlari():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        
        # Superadmin kontrolü
        if not getattr(current_user, 'is_superadmin', False):
            logger.warning(
                f"⚠️ Superadmin erişim denemesi: user={current_user.id}"
            )
            abort(403, "Bu sayfa sadece sistem yöneticilerine açıktır!")
        
        return f(*args, **kwargs)
    return decorated_function