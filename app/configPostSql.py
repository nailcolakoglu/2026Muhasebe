# config.py (GÜNCELLENMIŞ VERSİYON)

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'guclu-ve-gizli-bir-anahtar-super-erp-2025-@#$'
    
    # ========================================
    # MASTER DATABASE (PostgreSQL)
    # ========================================
    MASTER_DB_TYPE = os.environ.get('MASTER_DB_TYPE', 'postgresql')  # veya 'sqlite'
    MASTER_DB_USER = os.environ.get('MASTER_DB_USER', 'postgres')
    MASTER_DB_PASSWORD = os.environ.get('MASTER_DB_PASSWORD', 'postgres')
    MASTER_DB_HOST = os.environ.get('MASTER_DB_HOST', 'localhost')
    MASTER_DB_PORT = os.environ.get('MASTER_DB_PORT', '5432')
    MASTER_DB_NAME = os.environ.get('MASTER_DB_NAME', 'erp_master')
    
    # Master DB Connection String
    if MASTER_DB_TYPE == 'postgresql':
        SQLALCHEMY_DATABASE_URI = f'postgresql://{MASTER_DB_USER}:{MASTER_DB_PASSWORD}@{MASTER_DB_HOST}:{MASTER_DB_PORT}/{MASTER_DB_NAME}'
    else: 
        # SQLite (Geliştirme için)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///master.db'
    
    # ========================================
    # TENANT DATABASE (Firebird - Default)
    # ========================================
    # Bu bilgiler sadece setup/migration için
    # Runtime'da session'dan tenant seçimine göre dinamik bağlanılır
    TENANT_DB_HOST = os.environ.get('TENANT_DB_HOST', 'localhost')
    TENANT_DB_USER = os.environ.get('TENANT_DB_USER', 'SYSDBA')
    TENANT_DB_PASSWORD = os.environ.get('TENANT_DB_PASSWORD', 'masterkey')
    TENANT_DB_CHARSET = os.environ.get('TENANT_DB_CHARSET', 'UTF8')
    
    # ========================================
    # SQLALCHEMY AYARLARI
    # ========================================
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Debug için True yapılabilir
    
    # Bindings (Multi-database)
    SQLALCHEMY_BINDS = {
        'master':  SQLALCHEMY_DATABASE_URI,
        # Tenant DB dinamik olarak eklenir
    }
    
    # ========================================
    # SESSION AYARLARI
    # ========================================
    SESSION_COOKIE_NAME = 'erp_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 saat
    
    # ========================================
    # GÜVENLIK AYARLARI
    # ========================================
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    MAX_LOGIN_ATTEMPTS = 5
    ACCOUNT_LOCK_DURATION = 900  # 15 dakika
    
    # ========================================
    # LISANS AYARLARI
    # ========================================
    LICENSE_CHECK_INTERVAL = 86400  # Günde 1 kez
    OFFLINE_GRACE_PERIOD = 7  # 7 gün offline çalışabilir
    
    # ========================================
    # DOSYA YÜKLEME
    # ========================================
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
    
    # ========================================
    # DİL AYARLARI
    # ========================================
    BABEL_DEFAULT_LOCALE = 'tr'
    BABEL_SUPPORTED_LOCALES = ['tr', 'en']