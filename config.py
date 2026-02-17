# config.py (MySQL + Multi-Tenant Version)

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration - MySQL + Multi-Tenant"""
    
    # ========================================
    # 🔐 SECRET & CSRF
    # ========================================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-12345'
    
    # CSRF Ayarları
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False  # Development için (Production'da True)
    
    # Session ayarları
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = False  # Production'da True (HTTPS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_REFRESH_EACH_REQUEST = True
    
    # ========================================
    # 🗄️ DATABASE (MySQL Multi-Tenant)
    # ========================================
    
    # Master DB (User, Tenant, License)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'MASTER_DB_URL',
        'mysql+pymysql://root:nc67fo76sice@localhost/erp_master?charset=utf8mb4'
    )
    
    # Supervisor DB (License validation)
    SQLALCHEMY_BINDS = {
        'supervisor': os.environ.get(
            'SUPERVISOR_DB_URL',
            'mysql+pymysql://root:nc67fo76sice@localhost/erp_supervisor?charset=utf8mb4'
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
    
    # Tenant DB Prefix (her firma için ayrı database)
    TENANT_DB_PREFIX = os.environ.get('TENANT_DB_PREFIX', 'erp_tenant_')
    
    # Tenant DB Connection Template
    TENANT_DB_HOST = os.environ.get('TENANT_DB_HOST', 'localhost')
    TENANT_DB_PORT = int(os.environ.get('TENANT_DB_PORT', 3306))
    TENANT_DB_USER = os.environ.get('TENANT_DB_USER', 'root')
    TENANT_DB_PASSWORD = os.environ.get('TENANT_DB_PASSWORD', 'nc67fo76sice')
    TENANT_DB_PREFIX = 'erp_tenant_'
    TENANT_DB_CHARSET = 'utf8mb4'
    
    # Tenant DB URL Template
    # Örnek: erp_tenant_firma1, erp_tenant_firma2
    TENANT_DB_URL_TEMPLATE = (
        f"mysql+pymysql://{TENANT_DB_USER}:{TENANT_DB_PASSWORD}"
        f"@{TENANT_DB_HOST}:{TENANT_DB_PORT}"
        f"/{{tenant_code}}?charset={TENANT_DB_CHARSET}"
    )
    
    # ========================================
    # 🌍 BABEL (i18n)
    # ========================================
    BABEL_DEFAULT_LOCALE = 'tr'
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
    REDIS_URL = os.environ.get('REDIS_URL')  # redis://localhost:6379/0
    
    if REDIS_URL:
        CACHE_TYPE = 'RedisCache'
        CACHE_REDIS_URL = REDIS_URL
        print("🚀 Cache: Redis Aktif")
    else:
        CACHE_TYPE = 'FileSystemCache'
        CACHE_DIR = os.path.join(os.getcwd(), 'cache_data')
        CACHE_THRESHOLD = 1000
        print("📂 Cache: FileSystem Aktif")
    
    CACHE_DEFAULT_TIMEOUT = 300  # 5 dakika
    CACHE_KEY_PREFIX = 'erp:'
    
    # ========================================
    # 📡 SESSION (Redis or Cookie)
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
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
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
    
    # Development'ta simple cache (Redis gerekmez)
    CACHE_TYPE = 'simple'
    
    # CSRF daha esnek
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_CHECK_DEFAULT = True
    WTF_CSRF_LOG = True
    
    # SQL echo (debug için)
    SQLALCHEMY_ECHO = False  # True yaparsanız tüm SQL'ler loglanır


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Production'da Redis zorunlu
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL')
    
    if not CACHE_REDIS_URL:
        raise ValueError("Production'da REDIS_URL zorunludur!")
    
    # CSRF strict
    WTF_CSRF_SSL_STRICT = True
    SESSION_COOKIE_SECURE = True
    
    # SQL echo kapalı
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    
    # Test DB (in-memory SQLite)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # CSRF disabled (test için)
    WTF_CSRF_ENABLED = False
    
    # Cache disabled
    CACHE_TYPE = 'null'