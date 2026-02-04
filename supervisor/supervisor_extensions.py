import sys
import os

# ========================================
# PATH AYARLARI - DÜZELTİLDİ
# ========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# APP_DIR yerine PROJECT_ROOT (Proje Ana Dizini)
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2. Sadece mevcut olan 'db' nesnesini ana uygulamadan al
try:
    # Artık 'app' paketini bulabilir
    from app.extensions import db
except ImportError as e:
    print(f"❌ Ana uygulama extensions (db) yüklenemedi: {e}")
    # Detaylı hata görmek için:
    # import traceback; traceback.print_exc()
    pass # Pass geçiyoruz, çünkü db.init_app aşağıda yapılıyor

from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel

# Supervisor'a özel instance'lar
supervisor_login_manager = LoginManager()
supervisor_login_manager.login_view = 'auth.login'
supervisor_login_manager.login_message = 'Bu sayfayı görüntülemek için giriş yapmalısınız.'
supervisor_login_manager.login_message_category = 'warning'

csrf = CSRFProtect()
mail = Mail()
babel = Babel()

@supervisor_login_manager.user_loader
def load_supervisor(supervisor_id):
    from models.supervisor import Supervisor 
    return db.session.get(Supervisor, supervisor_id)

def init_supervisor_extensions(app):
    db.init_app(app)
    supervisor_login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    babel.init_app(app)