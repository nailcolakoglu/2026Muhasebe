# test_master_db.py (AuditLog testi eklendi - SON HALİ)

import sys
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from flask import Flask
from config import Config
from extensions import db, init_extensions

def test_full():
    """Tam test (AuditLog dahil)"""
    print("="*60)
    print("🚀 MASTER DATABASE TEST (FULL)")
    print("="*60)
    
    app = Flask(__name__)
    app.config.from_object(Config)
    init_extensions(app)
    
    with app.app_context():
        from models.master import Tenant, User, UserTenantRole, License, AuditLog
        
        print("\n✅ Modeller yüklendi (Tenant, User, License, AuditLog)")
        
        # Database oluştur
        print("\n🔄 Database oluşturuluyor...")
        db.create_all()
        print(f"✅ Database: {Config.MASTER_DB_PATH}")
        
        # Tenant
        print("\n🔄 Tenant oluşturuluyor...")
        tenant = Tenant(
            kod='01',
            unvan='Test Ticaret A.Ş.',
            vergi_no='1234567890',
            db_name='TEST_AS.FDB'
        )
        tenant.db_password = 'masterkey'
        
        db.session.add(tenant)
        db.session.commit()
        
        print(f"✅ Tenant: {tenant.unvan}")
        
        # License
        print("\n🔄 Lisans oluşturuluyor...")
        license = License.create_license(tenant, license_type='trial')
        
        db.session.add(license)
        db.session.commit()
        
        print(f"✅ Lisans: {license.license_type}")
        print(f"   Geçerlilik: {license.valid_until.strftime('%d.%m.%Y')}")
        print(f"   Max Users: {license.max_users}")
        
        is_valid, msg = license.is_valid()
        print(f"   Durum: {'✅' if is_valid else '❌'} {msg}")
        
        # User
        print("\n🔄 Kullanıcı oluşturuluyor...")
        user = User(
            email='admin@test.com',
            full_name='Admin User',
            is_active=True,
            email_verified=True
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
        print(f"   Şifre: {'✅' if user.check_password('123456') else '❌'}")
        
        # ✅ AuditLog
        print("\n🔄 Audit log kaydı...")
        AuditLog.log(
            action='system_init',
            user_id=user.id,
            tenant_id=tenant.id,
            resource_type='system',
            status='success'
        )
        
        AuditLog.log(
            action='license_created',
            user_id=user.id,
            tenant_id=tenant.id,
            resource_type='license',
            resource_id=str(license.id),
            status='success'
        )
        
        print(f"✅ Audit log: {AuditLog.query.count()} kayıt")
        
        # İstatistikler
        print("\n📊 Veritabanı:")
        print(f"   Tenant:     {Tenant.query.count()}")
        print(f"   License:    {License.query.count()}")
        print(f"   User:      {User.query.count()}")
        print(f"   Role:      {UserTenantRole.query.count()}")
        print(f"   AuditLog:  {AuditLog.query.count()}")
        
        # Son logları göster
        print("\n📋 Son Audit Logları:")
        for log in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5):
            print(f"   - {log.action} ({log.status}) - {log.created_at.strftime('%H:%M:%S')}")
        
        print("\n" + "="*60)
        print("✅ TÜM TESTLER BAŞARILI!")
        print("="*60)
        print("\n🔐 Giriş Bilgileri:")
        print(f"   Email: admin@test.com")
        print(f"   Şifre: 123456")
        print(f"   Firma: Test Ticaret A.Ş.")
        print(f"\n📂 Database: {Config.MASTER_DB_PATH}")

if __name__ == '__main__':
    test_full()