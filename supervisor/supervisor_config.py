# supervisor/supervisor_config.py

import os
from datetime import timedelta

class SupervisorConfig:
    """Supervisor Panel Yapılandırması"""
    
    # ========================================
    # TEMEL AYARLAR
    # ========================================
    SECRET_KEY = os.environ.get('SUPERVISOR_SECRET_KEY') or 'super-secret-key-change-in-production-2024'
    DEBUG = os.environ.get('SUPERVISOR_DEBUG', 'True') == 'True'
    HOST = '0.0.0.0'
    PORT = 5001
    
    # ========================================
    # VERITABANI AYARLARI (MySQL)
    # ========================================
    
    # 1. Veritabanı Kimlik Bilgileri
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASS = os.environ.get('DB_PASS', 'nc67fo76sice') # 👈 BURAYA KENDİ ŞİFRENİ YAZ
    
    # 2. Ana Uygulama Veritabanı (Firmalar, Kullanıcılar burada)
    MASTER_DB_NAME = 'erp_master'
    
    # 3. Supervisor Veritabanı (Loglar, Adminler burada)
    # İstersen bunu da 'erp_master' yapabilirsin ama ayrı olması daha temizdir.
    SUPERVISOR_DB_NAME = 'erp_supervisor' 

    # --------------------------------------------------------
    # SQLALCHEMY YAPILANDIRMASI
    # --------------------------------------------------------
    
    # Ana Bağlantı (Master DB)
    SQLALCHEMY_DATABASE_URI = f"mysql+mysqldb://{DB_USER}:{DB_PASS}@{DB_HOST}/{MASTER_DB_NAME}?charset=utf8mb4"
    
    # Ek Bağlantılar (Bind Keys)
    SQLALCHEMY_BINDS = {
        'supervisor': f"mysql+mysqldb://{DB_USER}:{DB_PASS}@{DB_HOST}/{SUPERVISOR_DB_NAME}?charset=utf8mb4"
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # ========================================
    # FIREBIRD (Tenant DB'ler)
    # ========================================
    FIREBIRD_HOST = 'localhost'
    FIREBIRD_PORT = 3050
    FIREBIRD_USER = 'SYSDBA'
    FIREBIRD_PASSWORD = 'masterkey'
    FIREBIRD_CHARSET = 'UTF8'
    FIREBIRD_DATA_DIR = r'D:\Firebird\Data\ERP'
    FIREBIRD_PATH = r"D:\Program Files\Firebird\Firebird_5_0"
    FIREBIRD_BIN_DIR = FIREBIRD_PATH
    
    # ========================================
    # DİĞER AYARLAR (Aynen Korundu)
    # ========================================
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_NAME = 'supervisor_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    
	# ========================================
    # FLASK-LOGIN
    # ========================================
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_NAME = 'supervisor_remember_token'
    
	# ========================================
    # BABEL (Çoklu Dil)
    # ========================================
    BABEL_DEFAULT_LOCALE = 'tr'
    BABEL_SUPPORTED_LOCALES = ['tr', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    
    
	# ========================================
    # YEDEKLEME
    # ========================================
    BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
    
    # Dizini oluştur
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    BACKUP_RETENTION_DAYS = 30  # Günlük yedekler 30 gün saklanır
    BACKUP_RETENTION_WEEKS = 12  # Haftalık yedekler 12 hafta
    BACKUP_RETENTION_MONTHS = 12  # Aylık yedekler 12 ay
    
    # Yedek depolama
    BACKUP_STORAGE = 'local'  # local, s3, ftp, sftp
    
	# AWS S3 (opsiyonel)
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET')
    AWS_S3_REGION = 'eu-central-1'
    

	# ========================================
    # CELERY (Arka Plan Görevleri)
    # ========================================
    CELERY_BROKER_URL = 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'Europe/Istanbul'
    CELERY_ENABLE_UTC = False
     
	# ========================================
    # EMAIL (Bildirimler)
    # ========================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@muhasebeerp.com')
    
    MONITORING_ENABLED = True
    MONITORING_INTERVAL = 60
    SLOW_QUERY_THRESHOLD = 2.0
    
    LICENSE_TYPES = {
        'trial': {
			'name': 'Deneme',
			'duration_days': 30, 
			'max_users': 3, 
			'max_branches': 1, 
			'max_monthly_invoices': 50, 
			'max_storage_mb': 500, 
            'price': 0,
			'modules': ['stok', 'cari', 'fatura']},
        'starter': {'name': 'Başlangıç', 'duration_days': 365, 'max_users': 5, 'max_branches': 1, 'max_monthly_invoices': 200, 'max_storage_mb': 2000, 'price': 999, 'modules': ['stok', 'cari', 'fatura', 'kasa', 'banka']},
        'professional': {'name': 'Profesyonel', 'duration_days': 365, 'max_users': 20, 'max_branches': 5, 'max_monthly_invoices': 1000, 'max_storage_mb': 10000, 'price': 2499, 'modules': ['stok', 'cari', 'fatura', 'kasa', 'banka', 'muhasebe', 'efatura', 'crm']},
        'enterprise': {'name': 'Kurumsal', 'duration_days': 365, 'max_users': 100, 'max_branches': 50, 'max_monthly_invoices': -1, 'max_storage_mb': 50000, 'price': 9999, 'modules': 'all'}
    }
	
    # ========================================
    # GÜVENLİK
    # ========================================
    # IP Whitelist (Supervisor paneline sadece bu IP'lerden erişim)
    IP_WHITELIST_ENABLED = False
    IP_WHITELIST = ['127.0.0.1', '192.168.1.0/24']
    
	# Brute Force Koruması
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_ATTEMPT_TIMEOUT = 300   # Saniye (5 dakika)
  

	# ========================================
    # LOGLAR
    # ========================================
    LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'supervisor.log')
    LOG_LEVEL = 'INFO'
    LOG_MAX_BYTES = 10 * 1024 * 1024
    LOG_BACKUP_COUNT = 10
 
   
    # ========================================
    # PAGINATION
    # ======================================== 
    ITEMS_PER_PAGE = 50
    MAX_ITEMS_PER_PAGE = 200