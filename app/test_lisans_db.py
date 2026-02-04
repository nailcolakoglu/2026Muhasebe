# test_master_db.py (License testi eklenmiş)

import sys
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from flask import Flask
from config import Config
from extensions import db, init_extensions

def test_with_license():
    """License dahil test"""
    print("="*60)
    print("🚀 MASTER DATABASE TEST (WITH LICENSE)")
    print("="*60)
    
    app = Flask(__name__)
    app.config.from_object(Config)
    init_extensions(app)
    
    with app.app_context():
        from models.master import Tenant, User, UserTenantRole, License  # ✅ License eklendi
        
        print("\n✅ Modeller yüklendi")
        
        # Database oluştur
        print("\n🔄 Database oluşturuluyor...")
        db.create_all()
        print(f"✅ Database:  {Config.MASTER_DB_PATH}")
        
        # Tenant oluştur
        print("\n🔄 Tenant oluşturuluyor...")
        tenant = Tenant(
            kod='01',
            unvan='Test A.Ş.',
            vergi_no='1234567890',
            db_name='TEST.FDB'
        )
        tenant.db_password = 'masterkey'
        
        db.session.add(tenant)
        db.session.commit()
        
        print(f"✅ Tenant: {tenant.unvan}")
        
        # ✅ License oluştur
        print("\n🔄 Lisans oluşturuluyor...")
        license = License.create_license(tenant, license_type='trial')
        
        db.session.add(license)
        db.session.commit()
        
        print(f"✅ Lisans: {license.license_type}")
        print(f"   Key: {license.license_key[: 20]}...")
        print(f"   Geçerlilik: {license.valid_until.strftime('%d.%m.%Y')}")
        print(f"   Max Users: {license.max_users}")
        print(f"   Modüller: {', '.join(license.enabled_modules)}")
        
        is_valid, msg = license.is_valid()
        print(f"   Durum: {'✅' if is_valid else '❌'} {msg}")
        
        # User oluştur
        print("\n🔄 Kullanıcı oluşturuluyor...")
        user = User(
            email='admin@test.com',
            full_name='Test Admin',
            is_active=True
        )
        user.set_password('123456')
        
        db.session.add(user)
        db.session.flush()
        
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=tenant.id,
            role='admin',
            is_default=True
        )
        
        db.session.add(role)
        db.session.commit()
        
        print(f"✅ User: {user.email}")
        print(f"   Şifre:  {'✅' if user.check_password('123456') else '❌'}")
        
        # İstatistikler
        print("\n📊 Veritabanı:")
        print(f"   Tenant:  {Tenant.query.count()}")
        print(f"   License: {License.query.count()}")
        print(f"   User: {User.query.count()}")
        print(f"   Role: {UserTenantRole.query.count()}")
        
        print("\n" + "="*60)
        print("✅ TEST BAŞARILI!")
        print("="*60)
        print("\n🔐 Giriş Bilgileri:")
        print(f"   Email: admin@test.com")
        print(f"   Şifre: 123456")
        print(f"   Firma: Test A.Ş.")

if __name__ == '__main__':
    test_with_license()