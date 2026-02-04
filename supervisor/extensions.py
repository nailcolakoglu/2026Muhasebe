# supervisor/extensions.py

"""
Supervisor Panel Extensions
"""

import sys
import os
import importlib.util

# ✅ Path ayarı: app/extensions.py'ye erişim için
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app'))

# =================================================================
# KRİTİK DÜZELTME: Ana uygulamanın extensions.py dosyasını 
# dosya yolundan manuel olarak yüklüyoruz.
# =================================================================
ext_path = os.path.join(APP_DIR, 'extensions.py')
spec = importlib.util.spec_from_file_location("app_extensions", ext_path)
app_extensions = importlib.util.module_from_spec(spec)
sys.modules["app_extensions"] = app_extensions
spec.loader.exec_module(app_extensions)

# Artık çakışma olmadan db'yi alabiliriz
db = app_extensions.db

# Diğer kütüphaneler
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel
from flask_apscheduler import APScheduler

scheduler = APScheduler()

# ========================================
# SUPERVISOR EXTENSIONS
# ========================================

# Login Manager (Supervisor için ayrı)
supervisor_login_manager = LoginManager()
supervisor_login_manager.login_view = 'auth.login'
supervisor_login_manager.login_message = 'Bu sayfayı görüntülemek için giriş yapmalısınız.'
supervisor_login_manager.login_message_category = 'warning'
supervisor_login_manager.session_protection = 'strong'

# CSRF Protection
csrf = CSRFProtect()

# Mail
mail = Mail()

# Babel (i18n)
babel = Babel()


# ========================================
# USER LOADER (Supervisor için)
# ========================================

@supervisor_login_manager.user_loader
def load_supervisor(supervisor_id):
    """Supervisor user loader"""
    # Import'u fonksiyon içine alarak döngüsel importu engelliyoruz
    try:
        from models.supervisor import Supervisor
    except ImportError:
        from supervisor.models.supervisor import Supervisor
        
    return db.session.get(Supervisor, supervisor_id)


# ========================================
# INIT FUNCTION
# ========================================

def init_supervisor_extensions(app):
    """
    Supervisor extensions'ları başlat
    """
    # Database (app'deki db instance'ını kullan)
    db.init_app(app)
    
    # Login Manager
    supervisor_login_manager.init_app(app)
    
    # CSRF
    csrf.init_app(app)
    
    # Mail
    mail.init_app(app)
    
    # Babel
    babel.init_app(app)