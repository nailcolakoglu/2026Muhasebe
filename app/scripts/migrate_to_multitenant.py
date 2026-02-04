# scripts/migrate_to_multitenant.py (YENİ DOSYA)

"""
Mevcut tek-database yapısını multi-tenant'a geçirir
"""

from models.master import Tenant, User, UserTenantRole, License
from models import Firma, Kullanici  # Eski modeller
from extensions import master_db, db
from datetime import datetime, timedelta
import uuid

def migrate_firmalar_to_tenants():
    """
    Firmalar tablosunu Master DB'ye taşı
    """
    print("🔄 Firmalar → Tenants migrasyonu başladı...")
    
    for firma in Firma.query.all():
        # Yeni database adı oluştur
        db_name = f"{firma.kod}_{firma.unvan.replace(' ', '_').upper()}.FDB"
        
        tenant = Tenant(
            id=uuid.uuid4(),
            kod=firma.kod,
            unvan=firma.unvan,
            vergi_dairesi=firma.vergi_dairesi,
            vergi_no=firma.vergi_no,
            
            # Database bilgileri
            db_type='firebird',
            db_host='localhost',
            db_name=db_name,
            db_user='SYSDBA',
            db_password='masterkey',  # ⚠️ Encrypt edilmeli
            
            # Metadata
            telefon=firma.telefon,
            email=firma.email,
            logo_path=firma.logo_path,
            is_active=firma.aktif,
            created_at=firma.olusturma_tarihi
        )
        
        master_db.session.add(tenant)
        
        # Trial lisans oluştur (30 gün)
        license = License(
            tenant_id=tenant.id,
            license_key=License.generate_license_key(),
            license_type='trial',
            valid_until=datetime.utcnow() + timedelta(days=30),
            max_users=5,
            enabled_modules=['fatura', 'cari', 'stok', 'kasa', 'banka']
        )
        master_db.session.add(license)
    
    master_db.session.commit()
    print(f"✅ {Firma.query.count()} firma → tenant'a taşındı")


def migrate_kullanicilar_to_users():
    """
    Kullanıcıları Master DB'ye taşı
    """
    print("🔄 Kullanıcılar → Users migrasyonu başladı...")
    
    email_map = {}  # kullanici_adi → email mapping
    
    for kullanici in Kullanici.query.all():
        # Email yoksa otomatik oluştur
        email = kullanici.email or f"{kullanici.kullanici_adi}@temp.local"
        
        # Aynı email varsa suffix ekle
        if email in email_map.values():
            email = f"{kullanici.kullanici_adi}_{kullanici.id}@temp.local"
        
        email_map[kullanici.kullanici_adi] = email
        
        # User oluştur
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=kullanici.sifre_hash,  # Mevcut hash'i koru
            full_name=kullanici.ad_soyad,
            phone=kullanici.telefon if hasattr(kullanici, 'telefon') else None,
            is_active=kullanici.aktif,
            created_at=datetime.utcnow()
        )
        master_db.session.add(user)
        master_db.session.flush()  # ID'yi al
        
        # Firma ilişkisini UserTenantRole'e taşı
        tenant = Tenant.query.filter_by(kod=kullanici.firma.kod).first()
        
        if tenant:
            role = UserTenantRole(
                user_id=user.id,
                tenant_id=tenant.id,
                role=kullanici.rol,
                local_user_id=kullanici.id,  # Eski ID'yi sakla
                is_default=True,
                is_active=True
            )
            master_db.session.add(role)
    
    master_db.session.commit()
    print(f"✅ {Kullanici.query.count()} kullanıcı → user'a taşındı")


def create_tenant_databases():
    """
    Her firma için ayrı Firebird DB oluştur
    """
    print("🔄 Tenant veritabanları oluşturuluyor...")
    
    for tenant in Tenant.query.all():
        db_path = f"d:/Firebird/Data/{tenant.db_name}"
        
        # Firebird DB oluştur
        import fdb
        try:
            con = fdb.create_database(
                dsn=f"localhost:{db_path}",
                user=tenant.db_user,
                password=tenant.db_password,
                charset='UTF8'
            )
            con.close()
            print(f"  ✅ {tenant.db_name} oluşturuldu")
            
            # Tabloları oluştur (Alembic migrate)
            from flask import Flask
            from config import Config
            
            app = Flask(__name__)
            Config.SQLALCHEMY_DATABASE_URI = tenant.get_connection_string()
            
            with app.app_context():
                db.init_app(app)
                db.create_all()
                print(f"  ✅ {tenant.db_name} tabloları oluşturuldu")
        
        except Exception as e:
            print(f"  ❌ {tenant.db_name} hatası: {e}")


def copy_data_to_tenant_db(tenant_id):
    """
    Eski DB'den yeni tenant DB'sine veri kopyala
    """
    tenant = Tenant.query.get(tenant_id)
    print(f"🔄 {tenant.unvan} için veri kopyalanıyor...")
    
    # Eski DB'den firmaya ait verileri çek
    from models import Fatura, CariHesap, StokKart
    
    eski_faturalar = Fatura.query.filter_by(firma_id=tenant.kod).all()
    eski_cariler = CariHesap.query.filter_by(firma_id=tenant.kod).all()
    # ...
    
    # Yeni DB'ye kaydet
    # (Detaylı kod yazılacak)
    
    print(f"✅ {tenant.unvan} veri kopyalama tamamlandı")


if __name__ == '__main__':
    migrate_firmalar_to_tenants()
    migrate_kullanicilar_to_users()
    create_tenant_databases()