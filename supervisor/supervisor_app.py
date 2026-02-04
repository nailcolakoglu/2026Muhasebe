# supervisor/supervisor_app.py

"""
SUPERVISOR PANEL - Ana Uygulama
(MySQL Uyumlu, Tam Özellikli Versiyon)
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, redirect, url_for, flash, session, request, g
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timezone, timedelta

# =========================================================
# 1. PATH AYARLARI (Kritik Düzeltme)
# =========================================================
# Bu dosyanın olduğu klasör (supervisor/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Proje Kök Dizini (MuhMySQL/) - 'app' klasörünün bir üstü
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))

# Supervisor modüllerinin bulunması için
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Ana uygulamanın (app) paket olarak bulunması için
# Bu sayede 'from app.extensions import db' her yerde aynı nesneyi döndürür
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# =========================================================
# 2. IMPORTS
# =========================================================
# ✅ ORTAK DB NESNESİ (Ana Projeden)
from app.extensions import db

# Supervisor'a özel eklentiler
from supervisor_extensions import supervisor_login_manager, csrf, mail, babel
from services.scheduler_service import SchedulerService

# Config yükle
try:
    from supervisor_config import SupervisorConfig
except ImportError:
    from config import SupervisorConfig

# Modeller (İlişkilerin kurulması için yüklenmeli)
from models.supervisor import Supervisor


# =========================================================
# 3. USER LOADER
# =========================================================
@supervisor_login_manager.user_loader
def load_supervisor(supervisor_id):
    """Supervisor user loader"""
    return db.session.get(Supervisor, supervisor_id)


# =========================================================
# 4. APP FACTORY
# =========================================================
def create_supervisor_app():
    """Supervisor Flask uygulamasını oluştur"""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(SupervisorConfig)
    
    # ---------------------------------------------------
    # A. EXTENSIONS BAŞLAT
    # ---------------------------------------------------
    # Ana DB (SQLAlchemy) başlat - Tek bir havuz kullanır
    db.init_app(app)
    
    # Supervisor Eklentileri
    supervisor_login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    
    # ---------------------------------------------------
    # B. GÜVENLİK & CSRF AYARLARI
    # ---------------------------------------------------
    # API yolları için CSRF muafiyeti (Hook)
    @app.before_request
    def handle_csrf_exemption():
        if request.path.startswith('/api/license/'):
            setattr(request, '_csrf_exempt', True)
    
    # Geliştirme/Test ortamı için opsiyonel CSRF kapatma
    app.config['WTF_CSRF_ENABLED'] = False 

    # ---------------------------------------------------
    # C. SCHEDULER (Zamanlanmış Görevler)
    # ---------------------------------------------------
    app.config['SCHEDULER_API_ENABLED'] = False
    app.config['SCHEDULER_TIMEZONE'] = "Europe/Istanbul"
    SchedulerService.init_app(app)
    print("✅ Supervisor extensions başlatıldı")
    
    # ---------------------------------------------------
    # D. VERİTABANI İLK KURULUM
    # ---------------------------------------------------
    with app.app_context():
        try:
            # Supervisor bind_key'ine sahip tabloları oluştur
            db.create_all(bind_key='supervisor')
            
            # İlk Süper Admin Kontrolü
            if not Supervisor.query.first():
                print("\n" + "="*60)
                print("⚠️  İLK SÜPER ADMİN OLUŞTURULUYOR")
                print("="*60)
                
                first_admin = Supervisor(
                    username='superadmin',
                    email='admin@supervisor.local',
                    full_name='Süper Yönetici',
                    role='super_admin',
                    is_active=True
                )
                first_admin.set_password('admin123')
                
                db.session.add(first_admin)
                db.session.commit()
                
                print(f"✅ Kullanıcı: superadmin")
                print(f"✅ Şifre: admin123")
                print("="*60 + "\n")
        except Exception as e:
            print(f"❌ Veritabanı başlatma hatası: {e}")
            
    # ---------------------------------------------------
    # E. LOGLAMA
    # ---------------------------------------------------
    setup_logging(app)
    
    # ---------------------------------------------------
    # F. GLOBAL DEĞİŞKENLER (Context Processors)
    # ---------------------------------------------------
    @app.context_processor
    def inject_globals():
        """Şablonlarda kullanılacak global değişkenler"""
        
        expiring_soon = 0
        active_tenants = 0
        unread_notifications = 0
        
        # Lisans ve Tenant İstatistikleri
        try:
            # Model importlarını güvenli yap (çakışma olmasın)
            try:
                from app.models.master import License, Tenant
            except ImportError:
                # Yedek yöntem
                sys.path.insert(0, os.path.join(PROJECT_ROOT, 'app', 'models'))
                from master import License, Tenant
            
            # UTC Zamanı
            now_utc = datetime.now(timezone.utc)
            
            # Sorgular
            expiring_soon = License.query.filter(
                License.valid_until <= now_utc + timedelta(days=30),
                License.valid_until >= now_utc,
                License.is_active == True
            ).count()
            
            active_tenants = Tenant.query.filter_by(is_active=True).count()
        except Exception:
            # DB hazır değilse veya hata varsa sessiz kal
            pass
            
        # Bildirimler
        if current_user.is_authenticated:
            try:
                from models.notification import Notification
                unread_notifications = Notification.query.filter_by(
                    supervisor_id=current_user.id,
                    is_read=False
                ).count()
            except:
                pass
                
        return {
            'app_name': 'MuhasebeERP Supervisor',
            'app_version': '2.0.0',
            'current_year': datetime.now().year,
            'supervisor': current_user if current_user.is_authenticated else None,
            'expiring_soon': expiring_soon,
            'active_tenants': active_tenants,
            'unread_notifications': unread_notifications
        }

    # ---------------------------------------------------
    # G. HER İSTEK ÖNCESİ (Before Request)
    # ---------------------------------------------------
    @app.before_request
    def before_request():
        if current_user.is_authenticated:
            # Son aktivite zamanını güncelle
            current_user.last_activity = datetime.now(timezone.utc)
            try:
                db.session.commit()
            except:
                db.session.rollback()
        
        # IP Whitelist Kontrolü (Güvenlik)
        if SupervisorConfig.IP_WHITELIST_ENABLED:
            if request.remote_addr not in SupervisorConfig.IP_WHITELIST:
                from flask import abort
                app.logger.warning(f"Yetkisiz IP erişimi engellendi: {request.remote_addr}")
                abort(403)

    # ---------------------------------------------------
    # H. KAYIT FONKSİYONLARI (Blueprints, Errors, CLI)
    # ---------------------------------------------------
    register_blueprints(app)
    register_error_handlers(app)
    register_cli_commands(app)
    
    return app


# =========================================================
# 5. YARDIMCI FONKSİYONLAR
# =========================================================

def setup_logging(app):
    """Loglama yapılandırması"""
    log_dir = SupervisorConfig.LOG_DIR
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass # Yetki yoksa geç
    
    file_handler = RotatingFileHandler(
        SupervisorConfig.LOG_FILE,
        maxBytes=SupervisorConfig.LOG_MAX_BYTES,
        backupCount=SupervisorConfig.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)


def register_blueprints(app):
    """Tüm modülleri (Blueprints) kaydet"""
    
    # (Path, Blueprint Name, URL Prefix)
    blueprints = [
        ('modules.auth.routes', 'auth_bp', '/auth'),
        ('modules.dashboard.routes', 'dashboard_bp', '/'),
        ('modules.tenants.routes', 'tenants_bp', '/tenants'),
        ('modules.licenses.routes', 'licenses_bp', '/licenses'),  
        ('modules.backup.routes', 'backup_bp', '/backup'), 
        ('modules.users.routes', 'users_bp', '/users'),
        ('modules.licenses.api', 'api_bp', '/api/license'),   
        ('modules.monitoring.routes', 'monitoring_bp', '/monitoring'),
        ('modules.audit.routes', 'audit_bp', '/audit'),
    ]
    
    for module_path, bp_name, url_prefix in blueprints:
        try:
            # Dinamik import
            module = __import__(module_path, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)
            
            # Blueprint kaydı
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            print(f"✅ {bp_name} kaydedildi")
            
            # API Blueprint'i için özel CSRF muafiyeti
            if bp_name == 'api_bp':
                for rule in app.url_map.iter_rules():
                    if rule.endpoint.startswith('license_api.'):
                        csrf.exempt(rule.endpoint)
                print(f"🛡️  license_api içindeki tüm rotalar CSRF'den muaf tutuldu.")
                        
        except Exception as e:
            print(f"❌ Blueprint Yükleme Hatası ({bp_name}): {e}")
            import traceback
            traceback.print_exc()


def register_error_handlers(app):
    """Hata yakalayıcılar"""
    
    @app.errorhandler(404)
    def not_found(e):
        return "<h1>404 - Sayfa Bulunamadı</h1><p>Aradığınız sayfa mevcut değil.</p>", 404
    
    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return f"<h1>500 - Sunucu Hatası</h1><p>Lütfen logları kontrol edin.</p>", 500


def register_cli_commands(app):
    """CLI komutları (Gelecekte eklenebilir)"""
    pass


# =========================================================
# 6. BAŞLATMA (MAIN)
# =========================================================
if __name__ == '__main__':
    app = create_supervisor_app()
    
    print("\n" + "="*80)
    print("🚀 SUPERVISOR PANEL BAŞLATILIYOR (V2.0)")
    print("="*80)
    # Hata durumunda config'den okuyamazsa varsayılanı bas
    db_host = getattr(SupervisorConfig, 'DB_HOST', 'localhost')
    print(f"🗄️  DB Host:   {db_host}")
    print(f"🌐 Panel Adresi: http://localhost:{SupervisorConfig.PORT}")
    print(f"🔐 Varsayılan Giriş: superadmin / admin123")
    print("="*80 + "\n")
    
    app.run(
        host=SupervisorConfig.HOST,
        port=SupervisorConfig.PORT,
        debug=SupervisorConfig.DEBUG
    )