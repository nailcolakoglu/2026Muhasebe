# init_mysql.py (Ana dizinde - D:\GitHup\Muhasebe - çalıştırılmalı)
import sys
import os

# 1. Proje ana dizinini path'e ekle
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask
from app.extensions import db

# 🚨 MASTER MODELLER (App dizininden)
# Modül yollarını klasör yapına göre kontrol et
from app.models.master.user import User, UserTenantRole
from app.models.master.tenant import Tenant
from app.models.master.license import License
from app.models.master.accounting_period import AccountingPeriod
from app.models.master.audit import AuditLog
from app.models.master.backup_config import BackupConfig
from app.models.master.master_active_session import MasterActiveSession

# 🚨 SUPERVISOR MODELLER (Supervisor dizininden)
# Dosya adlarınla (supervisor.py, setting.py vb.) tam eşleşmeli
from supervisor.models.supervisor import Supervisor
from supervisor.models.setting import Setting
from supervisor.models.notification import Notification
from supervisor.models.tenant_extended import TenantExtended
from supervisor.models.license_extended import LicenseExtended
from supervisor.models.system_metric import SystemMetric

def init_db():
    app = Flask(__name__)
    
    # MySQL Bağlantı Bilgilerin (Root şifreni buraya yaz)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:SIFRENIZ@localhost/erp_master'
    app.config['SQLALCHEMY_BINDS'] = {
        'supervisor': 'mysql://root:SIFRENIZ@localhost/erp_supervisor'
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        print("⏳ MySQL tabloları oluşturuluyor...")
        try:
            # create_all() tüm bind anahtarlarındaki tabloları oluşturur
            db.create_all()
            print("✅ Tüm tablolar (Master ve Supervisor) başarıyla oluşturuldu!")
        except Exception as e:
            print(f"❌ HATA: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    init_db()