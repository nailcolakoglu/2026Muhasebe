# test_master_db.py (İLK 30 SATIR)

import sys
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

# ✅ Önce Flask app oluştur
from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# ✅ Extensions'ı başlat
from extensions import master_db, init_extensions
init_extensions(app)

# ✅ ARTIK modelleri import et (app context içinde)
with app.app_context():
    from models.master import Tenant, User, UserTenantRole, License, AuditLog


def run_all_tests():
    """Tüm testleri çalıştır"""
    print("="*60)
    print("🚀 MASTER DATABASE TEST")
    print("="*60)
    
    with app.app_context():
        # Test kodları buraya
        print(f"\n✅ Master database oluşturuluyor...")
        master_db.create_all()
        
        print(f"✅ Database:  {Config.MASTER_DB_PATH}")
        
        # Tenant oluştur
        print("\n🔄 Tenant oluşturuluyor...")
        tenant = Tenant(
            kod='01',
            unvan='Test Ticaret A.Ş.',
            vergi_no='1234567890',
            db_name='TEST_AS.FDB'
        )
        tenant.db_password = 'masterkey'
        
        master_db.session.add(tenant)
        master_db.session.commit()
        
        print(f"✅ Tenant:   {tenant.unvan} (ID: {tenant.id})")
        
        # Lisans oluştur
        print("\n🔄 Lisans oluşturuluyor...")
        license = License.create_license(tenant, 'trial')
        master_db.session.add(license)
        master_db.session.commit()
        
        print(f"✅ Lisans:  {license.license_type}")
        print(f"   Key: {license.license_key[: 20]}...")
        print(f"   Geçerlilik: {license.valid_until.strftime('%d.%m.%Y')}")
        
        is_valid, msg = license.is_valid()
        print(f"   Durum:  {'✅' if is_valid else '❌'} {msg}")
        
        # User oluştur
        print("\n🔄 Kullanıcı oluşturuluyor...")
        user = User(
            email='admin@test.com.tr',
            full_name='Test Admin',
            is_active=True,
            email_verified=True
        )
        user.set_password('123456')
        
        master_db.session.add(user)
        master_db.session.flush()
        
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=tenant.id,
            role='admin',
            is_default=True
        )
        master_db.session.add(role)
        master_db.session.commit()
        
        print(f"✅ Kullanıcı: {user.email}")
        print(f"   Şifre testi: {'✅' if user.check_password('123456') else '❌'}")
        
        # Audit log
        AuditLog.log(
            action='test_init',
            user_id=user.id,
            tenant_id=tenant.id,
            status='success',
            extra_data={'test':   True, 'version': '1.0'}  # ✅ metadata → extra_data
        )
        print("✅ Audit log kaydedildi")

        
        # İstatistikler
        print("\n" + "="*60)
        print("📊 SONUÇLAR")
        print("="*60)
        print(f"Tenant:  {Tenant.query.count()}")
        print(f"User: {User.query.count()}")
        print(f"License: {License.query.count()}")
        print(f"Audit Log: {AuditLog.query.count()}")
        
        print("\n🔐 GİRİŞ BİLGİLERİ:")
        print(f"Email: admin@test.com.tr")
        print(f"Şifre: 123456")
        print(f"Firma: Test Ticaret A.Ş.")

if __name__ == '__main__':
    run_all_tests()