# extensions.py (FİNAL VERSİYON - ÇOK FİRMA DESTEKLİ)

import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from flask import g, session
from app.config import Config

from flask_caching import Cache  # 👈 MENU İÇİN EKLENDİ    
    
# ========================================
# MASTER DB (SQLite)
# ========================================
db = SQLAlchemy()

# ========================================
# CACHE MANAGER (Redis / Simple)
# ========================================
cache = Cache()  # 👈 EKLENDİ

# ========================================
# LOGIN MANAGER
# ========================================
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Lütfen giriş yapın.'
login_manager.login_message_category = 'warning'


# ========================================
# TENANT FIREBIRD BAĞLANTISI
# ========================================
def get_tenant_db():
    """
    Firebird Veritabanı Bağlantı Yöneticisi
    Supervisor'dan gelen ve lisans dosyasına mühürlenen dinamik şifreyi kullanır.
    """
    
    if 'tenant_db' in g:
        return g.tenant_db

    db_path = session.get('active_db_yolu')
    db_pass = session.get('active_db_sifre')

    if not db_path or not db_pass:
        return None

    try:
        # Config'den gelen base path ile tam yol oluşturulur
        from app.config import Config
        full_path = os.path.join(Config.TENANT_DB_BASE_PATH, db_path).replace('/', '\\')
        
        connection_string = f"firebird+firebird://SYSDBA:{db_pass}@localhost:3050/{full_path}?charset=UTF8"
        engine = create_engine(connection_string, pool_pre_ping=True, pool_recycle=300)
        
        session_factory = sessionmaker(bind=engine)
        g.tenant_db = scoped_session(session_factory)
        return g.tenant_db
    except Exception as e:
        print(f"❌ Firebird Bağlantı Hatası: {e}")
        return None
            
def close_tenant_db(e=None):
    """
    İstek sonunda Tenant DB bağlantısını kapat
    
    Flask'ın teardown_appcontext ile otomatik çalışır
    
    Args:
        e:  Exception (varsa)
    """
    tenant_db = g.pop('tenant_db', None)
    
    if tenant_db is not None:
        try: 
            # 1. Session'ı temizle
            tenant_db.remove() 
            # 2. Engine'i bul ve dispose et (Bağlantı havuzunu boşaltır)
            engine = tenant_db.get_bind()
            if engine:
                engine.dispose()
        except Exception: 
            pass


# ========================================
# EXTENSIONS BAŞLATICI
# ========================================
def init_extensions(app):
    """
    Tüm extension'ları Flask uygulamasına bağlar
    
    Args:
        app: Flask application instance
    """
    # Master DB (SQLite) başlat
    db.init_app(app)
    
    # Login Manager başlat
    login_manager.init_app(app)
    
    # 👇 CACHE BAŞLATMA
    cache.init_app(app)
    
    # Teardown handler (Her request sonunda Firebird bağlantısını kapat)
    app.teardown_appcontext(close_tenant_db)
    
    print("✅ Extensions başlatıldı (Master DB + Login Manager + Firebird Teardown)")


# ========================================
# USER LOADER (Master DB için)
# ========================================
@login_manager.user_loader
def load_user(user_id):
    if user_id is None or user_id == 'None':
        return None
        
    from app.models.master.user import User
    return db.session.get(User, user_id)
    
# ========================================
# YARDIMCI FONKSİYONLAR
# ========================================
def get_tenant_engine():
    """
    Aktif tenant'ın Firebird Engine'ini döner
    
    Nadiren kullanılır (Genelde session yeterli)
    
    Returns:
        Engine: SQLAlchemy Engine objesi veya None
    """
    return g.get('tenant_engine', None)


def is_tenant_connected():
    """
    Tenant DB bağlantısı var mı kontrol eder
    
    Returns: 
        bool: Bağlantı varsa True
    """
    return hasattr(g, 'tenant_db') and g.tenant_db is not None


def get_tenant_info():
    """
    Aktif tenant bilgilerini döner.
    Performans için statik verileri Cache (Redis)'ten okur.
    
    Returns:
        dict: Tenant bilgileri (firma_id dahil)
    """
    # 1. Session'dan ID'yi al
    tenant_id = session.get('tenant_id')
    
    if not tenant_id:
        return {
            'connected': False, 
            'tenant_id': None, 
            'firma_id': None, 
            'tenant_name': None
        }
    
    # 2. Cache Anahtarı Oluştur
    cache_key = f"tenant_info:{tenant_id}"
    
    # 3. Cache'ten çekmeyi dene
    cached_info = cache.get(cache_key)
    
    if cached_info:
        info = cached_info
    else:
        # 4. Cache'te yoksa Master DB'den sorgula
        # Import'u burada yapıyoruz (Circular import önlemi)
        # Model yolunuz projenize göre değişebilir, user_loader'daki yapıya sadık kaldım:
        from app.models.master import Tenant 
        
        tenant = db.session.get(Tenant, tenant_id)
        
        if tenant:
            info = {
                'tenant_id': tenant_id,
                'firma_id': tenant_id,  # İsteğin üzerine eklendi
                'tenant_name': tenant.unvan,
                'db_name': tenant.db_name
            }
            # 1 Saatlik (3600 sn) Cache'e at
            cache.set(cache_key, info, timeout=3600)
        else:
            # ID var ama DB'de yoksa (silinmişse)
            return {'connected': False, 'tenant_id': tenant_id, 'firma_id': None}

    # 5. Bağlantı durumunu ANLIK kontrol et (Bu cache'lenmemeli!)
    # Cache'ten gelen sözlüğün kopyasını alıp 'connected' ekliyoruz
    # (Doğrudan cache objesini değiştirirsek sonraki isteklerde hatalı true/false kalabilir)
    final_info = info.copy()
    final_info['connected'] = is_tenant_connected()
    
    return final_info