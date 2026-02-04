# test_master_db.py (MİNİMAL TEST)

import sys
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from flask import Flask
from config import Config
from extensions import db, init_extensions

def test_minimal():
    """Minimal test"""
    print("="*60)
    print("🚀 MASTER DATABASE TEST (MINIMAL)")
    print("="*60)
    
    # Flask app oluştur
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Extensions başlat
    init_extensions(app)
    
    with app.app_context():
        # Modelleri import et
        from models.master import Tenant, User, UserTenantRole
        
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
        
        print(f"✅ Tenant: {tenant.unvan} (ID: {tenant.id})")
        
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
        
        # Role oluştur
        role = UserTenantRole(
            user_id=user.id,
            tenant_id=tenant.id,
            role='admin',
            is_default=True
        )
        
        db.session.add(role)
        db.session.commit()
        
        print(f"✅ User: {user.email}")
        print(f"   Şifre testi: {'✅' if user.check_password('123456') else '❌'}")
        
        # Doğrulama
        print("\n📊 Veritabanı:")
        print(f"   Tenant sayısı: {Tenant.query.count()}")
        print(f"   User sayısı:  {User.query.count()}")
        print(f"   Role sayısı: {UserTenantRole.query.count()}")
        
        print("\n" + "="*60)
        print("✅ TEST BAŞARILI!")
        print("="*60)

if __name__ == '__main__':
    test_minimal()