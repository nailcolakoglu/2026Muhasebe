# app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'guclu-ve-gizli-bir-anahtar'

    # Master DB (MySQL)
    # Windows'ta path separator sorunları için düzeltme
    MASTER_DB_PATH = r'd:\github\muhasebe\app'
    SQLALCHEMY_DATABASE_URI = 'mysql://root:nc67fo76sice@localhost/erp_master'
  
    # Supervisor Bağlantısı
    SQLALCHEMY_BINDS = {
        'supervisor': 'mysql://root:nc67fo76sice@localhost/erp_supervisor'
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ✅ Firebird Ayarları
    TENANT_DB_HOST = os.environ.get('TENANT_DB_HOST', 'localhost')
    TENANT_DB_USER = os.environ.get('TENANT_DB_USER', 'SYSDBA')
    TENANT_DB_CHARSET = os.environ.get('TENANT_DB_CHARSET', 'UTF8')
    
    raw_path = os.environ.get('TENANT_DB_BASE_PATH', r'D:\Firebird\Data\ERP')
    TENANT_DB_BASE_PATH = raw_path.strip().replace('"', '').replace("'", "").replace('\\', '/')

    # ✅ Babel (Dil Desteği)
    BABEL_DEFAULT_LOCALE = 'tr'
    BABEL_SUPPORTED_LOCALES = ['tr', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    
    # ========================================
    # 🚀 CACHE AYARLARI (PERFORMANS İÇİN)
    # ========================================
    # Eğer Redis URL varsa Redis kullan, yoksa FileSystem (Dosya) kullan.
    # FileSystem, SimpleCache'ten iyidir çünkü restart'ta silinmez.
    
    REDIS_URL = os.environ.get('REDIS_URL') # Örn: redis://localhost:6379/0

    if REDIS_URL:
        CACHE_TYPE = 'RedisCache'
        CACHE_REDIS_URL = REDIS_URL
        print("🚀 Cache: Redis Aktif")
    else:
        # Redis yoksa 'cache' klasörüne dosyaları yazsın
        CACHE_TYPE = 'FileSystemCache'
        CACHE_DIR = os.path.join(os.getcwd(), 'cache_data')
        CACHE_THRESHOLD = 1000 # En fazla 1000 dosya sakla
        print("📂 Cache: FileSystem Aktif (Redis bulunamadı)")

    CACHE_DEFAULT_TIMEOUT = 300 # Varsayılan 5 dakika
    
    # Supervisor API
    SUPERVISOR_URL = 'http://127.0.0.1:5001/api/license/validate'