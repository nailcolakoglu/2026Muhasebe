# app/extensions.py
"""
Flask Extension'ları - MySQL Multi-Tenant + Redis Cache
Enterprise Grade - Production Ready
"""

import os
import logging
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache
from flask_babel import Babel
from werkzeug.exceptions import HTTPException 
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import scoped_session, sessionmaker, DeclarativeBase
from flask import g, session, request, current_app

# Logger
logger = logging.getLogger(__name__)


# ========================================
# 📦 BASE MODEL (SQLAlchemy 2.x)
# ========================================
class Base(DeclarativeBase):
    """SQLAlchemy Base Model (Declarative)"""
    pass


# ========================================
# 🗄️ MASTER DB (MySQL - User, Tenant, License)
# ========================================
db = SQLAlchemy(model_class=Base)


# ========================================
# 🚀 CACHE MANAGER (Redis / FileSystem / Simple)
# ========================================
cache = Cache()


# ========================================
# 🔐 LOGIN MANAGER
# ========================================
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Lütfen giriş yapın.'
login_manager.login_message_category = 'warning'

login_manager.session_protection = 'strong'  # veya 'basic' veya None

# ✅ EKLE: Remember cookie ayarları
login_manager.remember_cookie_duration = timedelta(days=7)
login_manager.remember_cookie_httponly = True
login_manager.remember_cookie_secure = False  # Development'ta False, production'da True


# ========================================
# 🌍 BABEL (i18n - Multi-Language Support)
# ========================================
babel = Babel()


# ========================================
# 🛡️ CSRF PROTECTION
# ========================================
csrf = CSRFProtect()


# ========================================
# 🏢 TENANT DATABASE CONNECTION (MySQL Multi-Tenant)
# ========================================
def get_tenant_db():
    """
    ✅ GÜVENLİ TENANT DB SESSION
    
    Security Features:
        - ✅ Tenant ID validation (UUID format)
        - ✅ Tenant code validation (SQL injection)
        - ✅ Database name validation
        - ✅ Database existence check
        - ✅ Connection pooling
    
    Returns:
        Session: SQLAlchemy session or None
    """
    
    # 1. Cache'de var mı?
    if hasattr(g, 'tenant_db_session'):
        return g.tenant_db_session
    
    # 2. Tenant ID kontrolü
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        logger.debug("⚠️ Tenant ID bulunamadı (session yok)")
        return None
    
    try:
        # 3. ✅ SECURITY: Tenant ID validation (UUID formatı)
        from app.utils.validators import SecurityValidator
        
        is_valid_uuid, error = SecurityValidator.validate_uuid(tenant_id)
        if not is_valid_uuid:
            logger.error(f"❌ Geçersiz tenant ID: {tenant_id} ({error})")
            abort(400, f"Geçersiz firma ID formatı")
        
        # 4. Tenant metadata'sını al (Master DB)
        from app.models.master import Tenant
        tenant = db.session.get(Tenant, tenant_id)
        
        if not tenant:
            logger.error(f"❌ Tenant bulunamadı: {tenant_id}")
            abort(404, "Firma bulunamadı")
        
        # 5. Tenant aktif mi?
        if not tenant.is_active:
            logger.warning(f"⚠️ Pasif tenant erişim denemesi: {tenant_id}")
            abort(403, "Bu firma devre dışı bırakılmış")
        
        # 6. ✅ SECURITY: Tenant code validation
        tenant_code = tenant.kod
        
        is_valid_code, error = SecurityValidator.validate_tenant_code(tenant_code)
        if not is_valid_code:
            logger.error(f"❌ Geçersiz tenant kodu: {tenant_code} ({error})")
            abort(400, f"Geçersiz firma kodu: {error}")
        
        # 7. Database adını belirle
        if hasattr(tenant, 'db_name') and tenant.db_name:
            tenant_db_name = tenant.db_name
            
            # ✅ SECURITY: Database name validation
            is_valid_db, error = SecurityValidator.validate_db_name(tenant_db_name)
            if not is_valid_db:
                logger.error(f"❌ Geçersiz database adı: {tenant_db_name} ({error})")
                abort(400, f"Geçersiz database adı: {error}")
        else:
            # Fallback: kod'dan oluştur
            prefix = current_app.config.get('TENANT_DB_PREFIX', 'erp_tenant_')
            tenant_db_name = f"{prefix}{tenant_code.lower()}"
            
            # ✅ SECURITY: Oluşturulan adı da validate et
            is_valid_db, error = SecurityValidator.validate_db_name(tenant_db_name)
            if not is_valid_db:
                logger.error(f"❌ Oluşturulan database adı geçersiz: {tenant_db_name}")
                abort(500, "Database adı oluşturulamadı")
        
        # 8. ✅ SECURITY: Database existence check
        if not check_database_exists(tenant_db_name):
            logger.error(f"❌ Database bulunamadı: {tenant_db_name}")
            abort(404, f"Firma veritabanı bulunamadı: {tenant_db_name}")
        
        # 9. MySQL connection URL oluştur (artık güvenli!)
        tenant_db_url = current_app.config['TENANT_DB_URL_TEMPLATE'].format(
            tenant_code=tenant_db_name
        )
        
        # 10. Engine oluştur
        engine = create_engine(
            tenant_db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
            echo=False
        )
        
        # 11. Session oluştur
        Session = scoped_session(sessionmaker(bind=engine))
        tenant_db_session = Session()
        
        # 12. g nesnesine kaydet (cache)
        g.tenant_db_session = tenant_db_session
        g.tenant_db_engine = engine
        g.tenant_metadata = {
            'id': tenant.id,
            'kod': tenant.kod,
            'unvan': tenant.unvan,
            'db_name': tenant_db_name
        }
        
        logger.debug(f"✅ Tenant DB bağlantısı: {tenant_db_name}")
        
        return tenant_db_session
    
    except Exception as e:
        logger.error(f"❌ Tenant DB hatası: {e}", exc_info=True)
        
        # Hata türüne göre yönlendirme
        if isinstance(e, HTTPException):
            raise  # abort() hataları direkt fırlat
        
        # Diğer hatalar için 500
        abort(500, "Veritabanı bağlantısı kurulamadı")


def check_database_exists(db_name: str) -> bool:
    """
    ✅ GÜVENLİ DATABASE KONTROL
    
    Database var mı kontrol et (SQL injection korumalı)
    
    Args:
        db_name (str): Database adı
    
    Returns:
        bool: Database var mı?
    
    Security:
        - ✅ Parameterized query ile SQL injection koruması
        - ✅ Read-only kontrol (INFORMATION_SCHEMA)
    """
    try:
        from sqlalchemy import text
        
        # ✅ SECURITY: Parameterized query ile SQL injection koruması
        query = text("""
            SELECT SCHEMA_NAME 
            FROM INFORMATION_SCHEMA.SCHEMATA 
            WHERE SCHEMA_NAME = :db_name
        """)
        
        result = db.session.execute(query, {'db_name': db_name}).fetchone()
        
        exists = result is not None
        
        if not exists:
            logger.warning(f"⚠️ Database bulunamadı: {db_name}")
        else:
            logger.debug(f"✅ Database mevcut: {db_name}")
        
        return exists
    
    except Exception as e:
        logger.error(f"❌ Database kontrol hatası: {e}", exc_info=True)
        return False

        
def close_tenant_db(exception=None):
    """
    Tenant DB session'ını güvenli şekilde kapat
    
    ✅ FIX: Engine dispose eklendi
    """
    tenant_db = g.pop('tenant_db_session', None)
    tenant_engine = g.pop('tenant_engine', None)
    
    if tenant_db is not None:
        try:
            # Exception varsa rollback
            if exception:
                tenant_db.rollback()
                logger.debug("🔄 Tenant DB rollback (exception)")
            
            # Session'ı kapat
            tenant_db.close()
            
            logger.debug("✅ Tenant DB session kapatıldı")
        
        except Exception as e:
            logger.debug(f"⚠️ Tenant session kapatma uyarısı: {e}")
    
    # ✅ Engine'i dispose et (connection pool temizle)
    if tenant_engine is not None:
        try:
            tenant_engine.dispose()
            logger.debug("✅ Tenant engine dispose edildi")
        except Exception as e:
            logger.debug(f"⚠️ Engine dispose uyarısı: {e}")


# ========================================
# 📊 TENANT BİLGİ FONKSİYONLARI
# ========================================

def get_tenant_info():
    """
    Aktif tenant bilgilerini döndürür (cache'li)
    
    Returns:
        dict: {
            'id': str (UUID),
            'kod': str,
            'name': str,
            'db_name': str (erp_tenant_XXX),
            'firma_id': str (UUID),
            'status': str
        }
    """
    if 'tenant_id' not in session:
        logger.debug("❌ Session'da tenant_id yok")
        return None
    
    tenant_id = session['tenant_id']
    
    # Cache'den kontrol et
    cache_key = f"tenant_info:{tenant_id}"
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"📦 Tenant info cache hit: {tenant_id}")
        return cached
    
    # DB'den çek
    from app.models.master.tenant import Tenant
    tenant = Tenant.query.get(tenant_id)
    
    if not tenant:
        logger.warning(f"⚠️ Tenant bulunamadı: {tenant_id}")
        return None
    
    # ✅ Tenant modelinden direkt oku
    info = {
        'id': tenant.id,
        'kod': tenant.kod,
        'name': tenant.unvan,
        'db_name': tenant.db_name,  # ✅ Zaten tam database adı (erp_tenant_XXX)
        'firma_id': tenant.id,  # Tenant ID = Firma ID
        'status': 'active' if tenant.is_active else 'inactive',
        'vergi_no': tenant.vergi_no,
        'vergi_dairesi': tenant.vergi_dairesi
    }
    
    # Cache'e kaydet (5 dakika)
    cache.set(cache_key, info, timeout=300)
    logger.debug(f"💾 Tenant info cache'lendi: {tenant.kod} -> {tenant.db_name}")
    
    return info


def is_tenant_connected():
    """
    Tenant DB bağlantısı var mı kontrol eder
    
    Returns:
        bool: Bağlantı varsa True
    """
    return hasattr(g, 'tenant_db_session') and g.tenant_db_session is not None


def get_tenant_engine():
    """
    Aktif tenant'ın MySQL Engine'ini döner
    
    Nadiren kullanılır (genelde session yeterli)
    
    Returns:
        Engine: SQLAlchemy Engine objesi veya None
    """
    tenant_db = get_tenant_db()
    
    if tenant_db:
        return tenant_db.get_bind()
    
    return None


# ========================================
# 🔐 USER LOADER (Master DB)
# ========================================

@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login user loader callback
    
    Args:
        user_id: User ID (UUID string)
    
    Returns:
        User: User model instance veya None
    """
    
    from app.models.master import User
    
    user = db.session.get(User, user_id)
    
    if user:
        logger.debug(f"✅ User loaded: {user.id}")
    else:
        logger.warning(f"⚠️ User not found: {user_id}")
    
    return user


# ========================================
# 🛡️ CSRF DEBUG LOGGER
# ========================================

def init_csrf_logger(app):
    """
    CSRF hatalarını logla (debug modunda)
    
    Her POST isteğinde CSRF token'ı kontrol eder ve loglar.
    
    Args:
        app: Flask application instance
    
    Kullanım:
        if app.debug:
            init_csrf_logger(app)
    """
    
    @app.before_request
    def log_csrf_token():
        """POST isteklerinde CSRF token'ı logla"""
        
        # Sadece debug modda ve POST isteklerinde
        if not app.debug or request.method != 'POST':
            return
        
        # API route'larını atla (exempt olanlar)
        if request.path.startswith('/api/'):
            return
        
        # CSRF token'ı al
        csrf_token = (
            request.form.get('csrf_token') or
            request.headers.get('X-CSRF-Token')
        )
        
        if csrf_token:
            logger.debug(
                f"📝 CSRF Token OK: {csrf_token[:20]}... "
                f"(POST {request.path})"
            )
        else:
            logger.warning(
                f"⚠️ CSRF Token eksik! "
                f"(POST {request.path}, IP: {request.remote_addr})"
            )


# ========================================
# 🎯 EXTENSION BAŞLATICI (Ana Fonksiyon)
# ========================================

def init_extensions(app):
    """
    Tüm Flask extension'larını başlat
    
    Args:
        app: Flask application instance
    
    Sıralama önemli:
        1. DB (Master)
        2. Cache (Redis/FileSystem)
        3. Login Manager
        4. Babel (i18n)
        5. CSRF Protection
        6. Teardown handlers
    """
    
    # 1. Master DB (MySQL)
    db.init_app(app)
    logger.info("✅ Master DB (MySQL) başlatıldı")
    
    # 2. Cache (Redis veya FileSystem)
    cache.init_app(app, config={
        'CACHE_TYPE': app.config.get('CACHE_TYPE', 'simple'),
        'CACHE_REDIS_URL': app.config.get('CACHE_REDIS_URL'),
        'CACHE_DIR': app.config.get('CACHE_DIR'),
        'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300),
        'CACHE_KEY_PREFIX': app.config.get('CACHE_KEY_PREFIX', 'erp:')
    })
    logger.info(f"✅ Cache ({app.config.get('CACHE_TYPE')}) başlatıldı")
    
    # 3. Login Manager
    login_manager.init_app(app)
    logger.info("✅ Flask-Login başlatıldı")
    
    # 4. Babel (i18n)
    def get_locale():
        """Dil seçici"""
        locale = request.args.get('lang')
        if locale in app.config.get('BABEL_SUPPORTED_LOCALES', ['tr', 'en']):
            session['locale'] = locale
            return locale
        
        return session.get('locale', app.config.get('BABEL_DEFAULT_LOCALE', 'tr'))
    
    babel.init_app(app, locale_selector=get_locale)
    logger.info("✅ Flask-Babel (i18n) başlatıldı")
    
    # 5. CSRF Protection
    csrf.init_app(app)
    logger.info("✅ CSRF Protection başlatıldı")
    
    # 6. Teardown handler (Tenant DB cleanup)
    app.teardown_appcontext(close_tenant_db)
    logger.info("✅ Teardown handler kaydedildi")
    
    # 7. CSRF Logger (debug modda)
    if app.debug:
        init_csrf_logger(app)
        logger.info("✅ CSRF Logger aktif (debug mode)")
    
    logger.info("🎉 Tüm extension'lar başarıyla yüklendi!")


# ========================================
# 🔧 YARDIMCI FONKSİYONLAR
# ========================================

def clear_tenant_cache(tenant_id):
    """
    Tenant cache'ini temizle
    
    Args:
        tenant_id: Tenant ID
    
    Kullanım:
        # Tenant bilgileri güncellendiğinde
        clear_tenant_cache(tenant_id)
    """
    cache_keys = [
        f"tenant_info:{tenant_id}",
        f"tenant_engine:{tenant_id}",
        f"tenant_metadata:{tenant_id}"
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    logger.info(f"🗑️ Tenant cache temizlendi: {tenant_id}")


def get_all_tenant_engines():
    """
    Tüm aktif tenant engine'lerini döner (nadiren kullanılır)
    
    Returns:
        dict: {tenant_id: engine}
    """
    # Cache'deki tüm engine'leri topla
    # Redis kullanıyorsanız keys() ile bulabilirsiniz
    # Bu fonksiyon genelde admin panelinde kullanılır
    pass


# ========================================
# 📊 HEALTH CHECK
# ========================================

def health_check():
    """
    Extension'ların sağlık kontrolü
    
    Returns:
        dict: {
            'master_db': 'ok' | 'error',
            'cache': 'ok' | 'error',
            'tenant_db': 'ok' | 'error'
        }
    """
    from sqlalchemy import text
    
    status = {}
    
    # 1. Master DB kontrolü
    try:
        db.session.execute(text('SELECT 1'))
        status['master_db'] = 'ok'
    except Exception as e:
        logger.error(f"❌ Master DB health check hatası: {e}")
        status['master_db'] = 'error'
    
    # 2. Cache kontrolü
    try:
        cache.set('health_check', 'ok', timeout=5)
        result = cache.get('health_check')
        status['cache'] = 'ok' if result == 'ok' else 'error'
    except Exception as e:
        logger.error(f"❌ Cache health check hatası: {e}")
        status['cache'] = 'error'
    
    # 3. Tenant DB kontrolü (varsa)
    if is_tenant_connected():
        try:
            tenant_db = get_tenant_db()
            tenant_db.execute(text('SELECT 1'))
            status['tenant_db'] = 'ok'
        except Exception as e:
            logger.error(f"❌ Tenant DB health check hatası: {e}")
            status['tenant_db'] = 'error'
    else:
        status['tenant_db'] = 'not_connected'
    
    return status