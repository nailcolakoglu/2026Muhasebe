# app/extensions.py
"""
Flask Extension'ları - MySQL Multi-Tenant + Redis Cache
Enterprise Grade - Production Ready
"""

import os
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import create_engine, event
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

# app/extensions.py (get_tenant_db function - LINE 95-180)

def get_tenant_db():
    """
    Tenant DB session'ı getir (MySQL Multi-Tenant)
    
    ✅ FIX: Engine cache kaldırıldı (pickle sorunu çözüldü)
    """
    
    # 1. Cache'de var mı kontrol et
    if hasattr(g, 'tenant_db_session'):
        return g.tenant_db_session
    
    # 2. Tenant ID kontrolü
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        logger.debug("⚠️ Tenant ID bulunamadı (session yok)")
        return None
    
    try:
        # 3. Tenant metadata'sını al (Master DB'den)
        from app.models.master import Tenant
        tenant = db.session.get(Tenant, tenant_id)
        
        if not tenant:
            logger.error(f"❌ Tenant bulunamadı: {tenant_id}")
            return None
        
        # 4. Tenant code alanını al
        tenant_code = tenant.kod
        
        if not tenant_code:
            logger.error(f"❌ Tenant kod alanı boş!")
            return None
        
        # 5. Tenant database adını kontrol et
        if hasattr(tenant, 'db_name') and tenant.db_name:
            tenant_db_name = tenant.db_name
        else:
            # Fallback: db_name yoksa kod'dan oluştur
            tenant_db_name = f"{current_app.config['TENANT_DB_PREFIX']}{tenant_code}"
        
        # 6. MySQL connection URL oluştur
        tenant_db_url = current_app.config['TENANT_DB_URL_TEMPLATE'].format(
            tenant_code=tenant_db_name
        )
        
        # ✅ 7. Engine'i HER SEFERINDE OLUŞTUR (Cache'leme!)
        # Pickle sorunu olduğu için cache kullanmıyoruz
        engine = create_engine(
            tenant_db_url,
            **current_app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {
                'pool_size': 5,           # ✅ Azaltıldı (her request'te engine oluşuyor)
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            })
        )
        
        logger.debug(f"🔧 Tenant DB engine oluşturuldu: {tenant_db_name}")
        
        # 8. Session oluştur (scoped)
        SessionFactory = scoped_session(
            sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )
        )
        
        # 9. Session'ı g'ye kaydet
        g.tenant_db_session = SessionFactory()
        
        # 10. Engine'i de kaydet (teardown'da dispose için)
        g.tenant_engine = engine
        
        # 11. Tenant metadata'sını da kaydet
        g.tenant_metadata = {
            'tenant_id': tenant_id,
            'tenant_code': tenant_code,
            'db_name': tenant_db_name
        }
        
        logger.debug(f"✅ Tenant DB session açıldı: {tenant_db_name}")
        
        return g.tenant_db_session
    
    except Exception as e:
        logger.error(f"❌ Tenant DB bağlantı hatası: {e}", exc_info=True)
        return None


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
    Aktif tenant bilgilerini döner (Cached)
    
    Returns:
        dict: {
            'connected': bool,
            'tenant_id': str,
            'firma_id': str,
            'tenant_name': str,
            'db_name': str
        }
    
    Kullanım:
        info = get_tenant_info()
        if info['connected']:
            print(f"Firma: {info['tenant_name']}")
    """
    
    # 1. Tenant ID kontrolü
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        return {
            'connected': False,
            'tenant_id': None,
            'firma_id': None,
            'tenant_name': None,
            'db_name': None
        }
    
    # 2. Cache'den çekmeyi dene
    cache_key = f"tenant_info:{tenant_id}"
    cached_info = cache.get(cache_key)
    
    if cached_info:
        info = cached_info
    else:
        # 3. Master DB'den sorgula
        from app.models.master import Tenant
        tenant = db.session.get(Tenant, tenant_id)
        
        if not tenant:
            return {
                'connected': False,
                'tenant_id': tenant_id,
                'firma_id': None,
                'tenant_name': None,
                'db_name': None
            }
        
        info = {
            'tenant_id': tenant_id,
            'firma_id': tenant_id,  # Aynı (uyumluluk için)
            'tenant_name': tenant.unvan,
            'db_name': f"{current_app.config['TENANT_DB_PREFIX']}{tenant.code}"
        }
        
        # 1 saatlik cache
        cache.set(cache_key, info, timeout=3600)
    
    # 4. Bağlantı durumunu ekle (real-time)
    info['connected'] = is_tenant_connected()
    
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
    if user_id is None or user_id == 'None':
        return None
    
    try:
        from app.models.master import User
        return db.session.get(User, user_id)
    except Exception as e:
        logger.error(f"❌ User load hatası: {e}")
        return None


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