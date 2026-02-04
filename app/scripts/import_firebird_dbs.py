# scripts/import_firebird_dbs.py (DÜZELTİLMİŞ)

import sys
import os

# ✅ Ana dizini Python path'ine ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.master import Tenant, User, UserTenantRole, License
from datetime import datetime, timedelta
import uuid

app = create_app()

# ✅ Firebird klasörü
FIREBIRD_DIR = r'D:\Firebird\Data'

# ✅ Eklenecek firmalar
firmalar = [
    {'kod':  'MERKEZ', 'unvan': 'Merkez Firma', 'fdb':  'MERKEZ.FDB', 'vergi': '1111111111'},
    {'kod': 'FIRMA-A', 'unvan': 'Firma A Ticaret', 'fdb': 'FIRMA_A.FDB', 'vergi': '2222222222'},
    {'kod': 'ISTANBUL', 'unvan':  'İstanbul Şubesi', 'fdb': 'SUBE_ISTANBUL.FDB', 'vergi':  '3333333333'},
]

with app.app_context():
    user = User.query.filter_by(email='admin@test.com').first()
    
    if not user:
        print("❌ Kullanıcı bulunamadı!  Önce /setup çalıştırın.")
        sys.exit(1)
    
    for idx, firma in enumerate(firmalar):
        # Kontrol: Zaten var mı?
        existing = Tenant.query.filter_by(kod=firma['kod']).first()
        if existing:
            print(f"⏭️  {firma['kod']} zaten kayıtlı")
            continue
        
        # Firebird dosyası var mı? 
        fdb_path = os.path.join(FIREBIRD_DIR, firma['fdb'])
        if not os.path.exists(fdb_path):
            print(f"⚠️  {firma['fdb']} bulunamadı:  {fdb_path}")
            continue
        
        # Tenant oluştur
        tenant = Tenant(
            id=str(uuid.uuid4()),
            kod=firma['kod'],
            unvan=firma['unvan'],
            db_name=firma['fdb'],
            vergi_no=firma['vergi'],
            is_active=True
        )
        tenant.set_db_password('masterkey')
        db.session.add(tenant)
        db.session.flush()
        
        # Lisans
        license = License(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            license_type='professional',
            valid_until=datetime.utcnow() + timedelta(days=365),
            max_users=10,
            is_active=True
        )
        db.session.add(license)
        
        # Yetki
        role = UserTenantRole(
            id=str(uuid.uuid4()),
            user_id=user.id,
            tenant_id=tenant.id,
            role='admin',
            is_default=(idx == 0),  # İlk firma varsayılan
            is_active=True
        )
        db.session.add(role)
        
        print(f"✅ {firma['kod']} eklendi")
    
    db.session.commit()
    print(f"\n🎉 {len(firmalar)} firma Master DB'ye aktarıldı!")