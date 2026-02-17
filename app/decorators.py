# app/decorators.py
"""
Güvenlik ve Yetkilendirme Decorator'ları

Kullanım Örnekleri:
    @login_required
    @tenant_required
    @permission_required('stok.create')
    @role_required(['admin', 'manager'])
    @audit_log('stok', 'create')
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
            # Mevcut URL'i next parametresine ekle (login sonrası dönüş için)
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def tenant_required(f):
    """
    Tenant (firma) seçili olmalı.
    
    Multi-tenant uygulamalarda kritik!
    Session'da 'tenant_id' olmalı.
    
    Kullanım:
        @tenant_required
        def tenant_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Login kontrolü
        if not current_user.is_authenticated:
            flash("⛔ Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        
        # 2. Tenant seçili mi?
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            flash("⚠️ Lütfen bir firma seçin.", "warning")
            return redirect(url_for('auth.select_tenant'))
        
        # 3. Tenant metadata var mı? (cache'den)
        if not hasattr(g, 'tenant_metadata') or not g.tenant_metadata:
            flash("❌ Firma bilgileri yüklenemedi. Lütfen tekrar seçin.", "danger")
            session.pop('tenant_id', None)
            return redirect(url_for('auth.select_tenant'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# 2. YETKİLENDİRME DECORATOR'LARI
# ============================================================================

def permission_required(permission):
    """
    Route'u yetkiye göre korur (İYİLEŞTİRİLMİŞ VERSİYON).
    
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
                flash("⛔ Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
                return redirect(url_for('auth.login', next=request.url))
            
            # 2. Yetki kontrolü (User modelindeki can() metodunu çağırır)
            if not current_user.can(permission):
                logger.warning(
                    f"Yetkisiz erişim: User={current_user.id}, "
                    f"Permission={permission}, URL={request.url}"
                )
                flash(f"⛔ Bu işlem için yetkiniz yok! (Gereken: {permission})", "danger")
                
                # Audit log ekle
                _log_unauthorized_access(permission)
                
                # Geldiği yere geri gönder, yoksa ana sayfaya
                return redirect(request.referrer or url_for('auth.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(allowed_roles):
    """
    Kullanıcı belirli role sahip olmalı.
    
    Kullanım:
        @role_required(['admin', 'manager'])
        @role_required('admin')  # Tek rol
        
    Args:
        allowed_roles (list|str): İzin verilen rol(ler)
        
    Returns:
        function: Korumalı fonksiyon
    """
    # String ise listeye çevir
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Login kontrolü
            if not current_user.is_authenticated:
                flash("⛔ Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
                return redirect(url_for('auth.login', next=request.url))
            
            # 2. Rol kontrolü
            user_role = getattr(current_user, 'role', None)
            if user_role not in allowed_roles:
                logger.warning(
                    f"Yetkisiz rol erişimi: User={current_user.id}, "
                    f"Role={user_role}, Required={allowed_roles}, URL={request.url}"
                )
                flash(f"⛔ Bu sayfaya erişim yetkiniz yok! (Gereken rol: {', '.join(allowed_roles)})", "danger")
                
                # Audit log ekle
                _log_unauthorized_access(f"role:{','.join(allowed_roles)}")
                
                return redirect(request.referrer or url_for('auth.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """
    Sadece admin kullanıcılar erişebilir (kısayol decorator).
    
    Kullanım:
        @admin_required
        def admin_only():
            ...
    """
    @wraps(f)
    @role_required('admin')
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# 3. MODÜL ERİŞİM KONTROL DECORATOR'LARI
# ============================================================================

def module_access_required(module_code):
    """
    Kullanıcının tenant'ında modül aktif olmalı.
    
    Lisans kontrolü için kullanılır.
    
    Kullanım:
        @module_access_required('muhasebe')
        def muhasebe_route():
            ...
        
    Args:
        module_code (str): Modül kodu ('stok', 'cari', 'fatura', vb.)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Login ve tenant kontrolü
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            if 'tenant_id' not in session:
                flash("⚠️ Lütfen bir firma seçin.", "warning")
                return redirect(url_for('auth.select_tenant'))
            
            # 2. Modül aktif mi kontrol et (tenant_metadata'dan)
            tenant_metadata = getattr(g, 'tenant_metadata', {})
            aktif_moduller = tenant_metadata.get('aktif_moduller', [])
            
            if module_code not in aktif_moduller:
                logger.warning(
                    f"Modül erişimi reddedildi: Tenant={session.get('tenant_id')}, "
                    f"Module={module_code}, URL={request.url}"
                )
                flash(
                    f"⛔ '{module_code}' modülü bu firma için aktif değil. "
                    f"Lütfen lisansınızı kontrol edin.",
                    "danger"
                )
                return redirect(url_for('auth.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# 4. AUDİT LOG DECORATOR'I
# ============================================================================

def audit_log(module, action):
    """
    Fonksiyon çağrısını otomatik audit log'a kaydet.
    
    Kullanım:
        @audit_log('stok', 'create')
        def stok_ekle():
            ...
        
        @audit_log('fatura', 'delete')
        def fatura_sil(fatura_id):
            ...
    
    Args:
        module (str): Modül adı
        action (str): Aksiyon ('create', 'update', 'delete', 'view')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Fonksiyonu çalıştır
            result = f(*args, **kwargs)
            
            # Başarılıysa audit log ekle
            try:
                # Record ID'yi kwargs veya args'dan al (varsa)
                record_id = kwargs.get('id') or (args[0] if args else None)
                
                _create_audit_log(
                    module=module,
                    action=action,
                    record_id=str(record_id) if record_id else None,
                    status='success'
                )
            except Exception as e:
                logger.error(f"Audit log eklenemedi: {e}")
            
            return result
        return decorated_function
    return decorator


# ============================================================================
# 5. GÜVENLİK DECORATOR'LARI
# ============================================================================

def ajax_required(f):
    """
    Sadece AJAX isteklerine izin ver.
    
    Kullanım:
        @ajax_required
        def ajax_endpoint():
            return jsonify({...})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            abort(400, "Bu endpoint sadece AJAX isteklerine yanıt verir.")
        return f(*args, **kwargs)
    return decorated_function


def api_key_required(f):
    """
    API key kontrolü (external API için).
    
    Header'da 'X-API-Key' beklenir.
    
    Kullanım:
        @api_key_required
        def api_endpoint():
            return jsonify({...})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            abort(401, "API key gerekli. Header: X-API-Key")
        
        # API key doğrula (config'den veya DB'den)
        valid_keys = current_app.config.get('API_KEYS', [])
        if api_key not in valid_keys:
            logger.warning(f"Geçersiz API key: {api_key}, IP: {request.remote_addr}")
            abort(403, "Geçersiz API key")
        
        return f(*args, **kwargs)
    return decorated_function


def ip_whitelist_required(allowed_ips=None):
    """
    Sadece belirli IP'lerden erişime izin ver.
    
    Kullanım:
        @ip_whitelist_required(['127.0.0.1', '192.168.1.0/24'])
        def sensitive_route():
            ...
    
    Args:
        allowed_ips (list): İzin verilen IP listesi (CIDR notasyonu desteklenir)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            
            # Config'den varsayılan listeyi al
            if allowed_ips is None:
                whitelist = current_app.config.get('IP_WHITELIST', [])
            else:
                whitelist = allowed_ips
            
            # Whitelist boşsa tüm IP'lere izin ver
            if not whitelist:
                return f(*args, **kwargs)
            
            # IP kontrolü
            if client_ip not in whitelist:
                logger.warning(f"IP whitelist engelledi: {client_ip}, URL: {request.url}")
                abort(403, "Bu IP adresinden erişim izniniz yok")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# YARDIMCI FONKSİYONLAR (PRIVATE)
# ============================================================================

def _log_unauthorized_access(permission):
    """
    Yetkisiz erişim denemesini audit log'a kaydet.
    
    Args:
        permission (str): Erişmeye çalıştığı yetki
    """
    try:
        from app.models.master import AuditLog
        from app.extensions import db
        
        log = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            tenant_id=session.get('tenant_id'),
            action='unauthorized_access',
            module='security',
            details=f"Permission: {permission}, URL: {request.url}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            status='failed',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Audit log eklenemedi: {e}")


def _create_audit_log(module, action, record_id=None, status='success'):
    """
    Audit log kaydı oluştur.
    
    Args:
        module (str): Modül adı
        action (str): Aksiyon
        record_id (str): Kayıt ID
        status (str): Durum ('success', 'failed')
    """
    try:
        from app.models.master import AuditLog
        from app.extensions import db
        
        log = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            tenant_id=session.get('tenant_id'),
            action=action,
            module=module,
            record_id=record_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            status=status,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Audit log eklenemedi: {e}")


# ============================================================================
# ÇOKLU DECORATOR KOMBİNASYONLARI (KISA YOLLAR)
# ============================================================================

def tenant_route(f):
    """
    Tenant route için tüm kontroller (kısayol).
    
    = @login_required + @tenant_required
    
    Kullanım:
        @tenant_route
        def my_route():
            ...
    """
    @wraps(f)
    @login_required
    @tenant_required
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


def protected_route(permission):
    """
    Tam korumalı route (kısayol).
    
    = @login_required + @tenant_required + @permission_required
    
    Kullanım:
        @protected_route('stok.create')
        def stok_ekle():
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        @tenant_required
        @permission_required(permission)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    return decorator