# config.py (FIREBIRD YOLU DÜZELTİLDİ)

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'guclu-ve-gizli-bir-anahtar'
    
    # Master DB (SQLite)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    MASTER_DB_PATH = os.path.join(BASE_DIR, 'master.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{MASTER_DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ✅ Firebird Ayarları
    TENANT_DB_HOST = os.environ.get('TENANT_DB_HOST', 'localhost')
    TENANT_DB_USER = os.environ.get('TENANT_DB_USER', 'SYSDBA')
    TENANT_DB_CHARSET = os.environ.get('TENANT_DB_CHARSET', 'UTF8')
    
    # ✅ DOĞRU YOL (Muhasebe klasörü)
    raw_path = os.environ.get('TENANT_DB_BASE_PATH', r'D:\Firebird\Data\ERP')
    TENANT_DB_BASE_PATH = raw_path.strip().replace('"', '').replace("'", "").replace('\\', '/')
    #TENANT_DB_BASE_PATH = os.environ.get('TENANT_DB_BASE_PATH', r'D:\Firebird\Data\ERP')

    # ✅ Babel (Dil Desteği)
    BABEL_DEFAULT_LOCALE = 'tr'
    BABEL_SUPPORTED_LOCALES = ['tr', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'