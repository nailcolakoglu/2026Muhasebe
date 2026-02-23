# config.py - DÜZELTİLMİŞ VERSİYON

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration - MySQL + Multi-Tenant"""
    
    # ========================================
    # 🔐 SECRET & CSRF
    # ========================================
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("❌ Production'da SECRET_KEY zorunludur!")
        SECRET_KEY = 'dev-secret-key-change-in-production-12345'
        print("⚠️  DEV MODE: Geçici SECRET_KEY kullanılıyor")
    
    # CSRF Ayarları
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False  # Development için
    
    # Session ayarları
    SESSION_COOKIE_NAME = 'session'

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = False  # Production'da True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_REFRESH_EACH_REQUEST = True
    
    # ✅ Remember me ayarları
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = False  # Development'ta False
    
    # ========================================
    # 🗄️ DATABASE (MySQL Multi-Tenant)
    # ========================================
    
    # Database Credentials
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASS = os.environ.get('DB_PASS')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    
    # Development fallback
    if not DB_PASS:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("❌ Production'da DB_PASS zorunludur!")
        DB_PASS = 'nc67fo76sice'  # ⚠️ Sadece development için!
        print("⚠️  DEV MODE: Geçici DB şifresi kullanılıyor")
    
    # Master DB
    MASTER_DB_NAME = os.environ.get('MASTER_DB_NAME', 'erp_master')
    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}'
        f'/{MASTER_DB_NAME}?charset=utf8mb4'
    )
    
    # Supervisor DB
    SUPERVISOR_DB_NAME = os.environ.get('SUPERVISOR_DB_NAME', 'erp_supervisor')
    SQLALCHEMY_BINDS = {
        'supervisor': (
            f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}'
            f'/{SUPERVISOR_DB_NAME}?charset=utf8mb4'
        )
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MySQL Engine Options
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'connect_args': {
            'charset': 'utf8mb4',
            'connect_timeout': 10
        }
    }
    
    # ========================================
    # 🏢 TENANT DATABASE (MySQL)
    # ========================================
    
    # Tenant DB Ayarları (Master DB ile aynı sunucu)
    TENANT_DB_HOST = os.environ.get('TENANT_DB_HOST', DB_HOST)
    TENANT_DB_PORT = int(os.environ.get('TENANT_DB_PORT', DB_PORT))
    TENANT_DB_USER = os.environ.get('TENANT_DB_USER', DB_USER)
    TENANT_DB_PASSWORD = os.environ.get('TENANT_DB_PASSWORD', DB_PASS)
    TENANT_DB_PREFIX = os.environ.get('TENANT_DB_PREFIX', 'erp_tenant_')
    TENANT_DB_CHARSET = 'utf8mb4'
    
    # Tenant DB URL Template
    TENANT_DB_URL_TEMPLATE = (
        f"mysql+pymysql://{TENANT_DB_USER}:{TENANT_DB_PASSWORD}"
        f"@{TENANT_DB_HOST}:{TENANT_DB_PORT}"
        f"/{{tenant_code}}?charset={TENANT_DB_CHARSET}"
    )
    
    # ========================================
    # 🌍 BABEL (i18n)
    # ========================================
    BABEL_DEFAULT_LOCALE = os.environ.get('BABEL_DEFAULT_LOCALE', 'tr')
    BABEL_DEFAULT_TIMEZONE = 'Europe/Istanbul'
    BABEL_SUPPORTED_LOCALES = ['tr', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'app/translations'
    LANGUAGES = {
        'tr': 'Türkçe',
        'en': 'English'
    }
    
    # ========================================
    # 🚀 CACHE (Redis or FileSystem)
    # ========================================
    REDIS_URL = os.environ.get('REDIS_URL')
    
    if REDIS_URL:
        CACHE_TYPE = 'RedisCache'
        CACHE_REDIS_URL = REDIS_URL
    else:
        CACHE_TYPE = 'FileSystemCache'
        CACHE_DIR = os.path.join(os.getcwd(), 'cache_data')
        CACHE_THRESHOLD = 1000
    
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_KEY_PREFIX = 'erp:'
    
    # ========================================
    # 📡 SESSION (Redis or Filesystem)
    # ========================================
    if REDIS_URL:
        SESSION_TYPE = 'redis'
        SESSION_REDIS = REDIS_URL
    else:
        SESSION_TYPE = 'filesystem'
        SESSION_FILE_DIR = os.path.join(os.getcwd(), 'flask_session')
    
    # ========================================
    # 🔗 EXTERNAL SERVICES
    # ========================================
    SUPERVISOR_URL = os.environ.get(
        'SUPERVISOR_URL',
        'http://127.0.0.1:5001/api/license/validate'
    )
    
    # ========================================
    # 📁 UPLOAD & STATIC
    # ========================================
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # ========================================
    # 🤖 AI & OCR
    # ========================================
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # ========================================
    # 🔧 APP SETTINGS
    # ========================================
    APP_NAME = 'ERP Sistemi'
    APP_VERSION = '2.0.0'
    HOST = '0.0.0.0'
    PORT = 5000


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    CACHE_TYPE = 'simple'
    WTF_CSRF_TIME_LIMIT = None
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # ❌ BURADA KONTROL YAPMA! (Class yüklenirken hata verir)
    # Bunun yerine __init__ veya validate() methodunda kontrol et
    
    # CSRF strict
    WTF_CSRF_SSL_STRICT = True
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_ECHO = False
    
    @classmethod
    def validate(cls):
        """Production config validasyonu"""
        if not cls.DB_PASS or cls.DB_PASS == 'nc67fo76sice':
            raise ValueError("❌ Production'da gerçek DB_PASS gerekli!")
        
        if not cls.SECRET_KEY or 'dev-secret' in cls.SECRET_KEY:
            raise ValueError("❌ Production'da gerçek SECRET_KEY gerekli!")


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'


# Config seçici
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """
    Environment'a göre config döndürür
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    selected_config = config.get(config_name, DevelopmentConfig)
    
    # Production ise validate et
    if config_name == 'production':
        selected_config.validate()
    
    return selected_config