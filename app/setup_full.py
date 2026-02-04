# setup_full.py (PROJE ANA DİZİNİNDE OLMALI)

import os
import sys
from sqlalchemy import create_engine, text, inspect
from datetime import datetime, timedelta

# Import hatalarını önlemek için proje kök dizinini yola ekle (Garanti olsun)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ✅ Importlar artık 'app.' ile başlamalı
from app.app import create_app
from app.extensions import db
from app.models.master import User, Tenant, UserTenantRole, License

# ✅ Firebird Modelleri (app.modules...)
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.cari.models import CariHesap
from app.modules.stok.models import StokKart
from app.modules.firmalar.models import Firma, Donem, Sube, Depo
from app.modules.kullanici.models import Kullanici
# Buraya diğer modüllerini de ekleyebilirsin: app.modules.kasa.models vb.

app = create_app()

def create_firebird_generators(engine):
    """Firebird için Generator ve Triggerları oluşturur"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    with engine.connect() as conn:
        print("⚙️  Firebird Generator ve Triggerları oluşturuluyor...")
        for table in tables:
            gen_name = f"GEN_{table}_ID"[:31] 
            
            try:
                conn.execute(text(f"CREATE GENERATOR {gen_name};"))
                conn.execute(text(f"SET GENERATOR {gen_name} TO 0;"))
                
                trigger_sql = f"""
                CREATE TRIGGER TR_{table[:24]}_BI FOR {table}
                ACTIVE BEFORE INSERT POSITION 0
                AS
                BEGIN
                  IF (NEW.ID IS NULL) THEN
                    NEW.ID = GEN_ID({gen_name}, 1);
                END
                """
                conn.execute(text(trigger_sql))
                print(f"  ✅ {table} -> Generator Eklendi")
            except Exception as e:
                pass
        conn.commit()

def setup_tenant_database(tenant):
    """Tenant için Firebird DB oluşturur"""
    print(f"\n🔥 Firebird Kurulumu Başlıyor: {tenant.unvan}")
    
    # ⚠️ Firebird veritabanı klasörü (Config'den çekmek daha iyi olur ama burda sabit verelim)
    db_path = r'd:/Firebird/Data/Muhasebe'
    full_path = os.path.join(db_path, tenant.db_name)
    
    if not os.path.exists(db_path):
        os.makedirs(db_path)
    
    # 1. Firebird Dosyasını Oluştur
    if not os.path.exists(full_path):
        try:
            import fdb
            conn = fdb.create_database(
                dsn=f"localhost:{full_path}",
                user='SYSDBA',
                password=tenant.get_db_password(),
                page_size=16384,
                charset='UTF8'
            )
            conn.close()
            print(f"  ✅ Dosya oluşturuldu: {full_path}")
        except Exception as e:
            print(f"  ❌ Dosya oluşturma hatası: {e}")
            return
    else:
        print(f"  ℹ️ Dosya zaten var: {full_path}")

    # 2. Tabloları Oluştur
    connection_string = f"firebird+firebird://SYSDBA:{tenant.get_db_password()}@localhost:3050/{full_path}?charset=UTF8"
    tenant_engine = create_engine(connection_string)
    
    try:
        db.metadata.create_all(bind=tenant_engine)
        print("  ✅ Tablolar oluşturuldu (SQLAlchemy)")
        
        create_firebird_generators(tenant_engine)
        
        # 3. Varsayılan Verileri Ekle
        from sqlalchemy.orm import Session
        with Session(tenant_engine) as session:
            # Firma
            yeni_firma = Firma(kod=tenant.kod, unvan=tenant.unvan, vergi_no=tenant.vergi_no, aktif=True)
            session.add(yeni_firma)
            session.flush() 
            
            # Dönem
            yeni_donem = Donem(
                firma_id=yeni_firma.id, yil=datetime.now().year,
                baslangic=datetime(datetime.now().year, 1, 1),
                bitis=datetime(datetime.now().year, 12, 31), aktif=True
            )
            session.add(yeni_donem)
            
            # Şube
            yeni_sube = Sube(firma_id=yeni_firma.id, kod='MERKEZ', ad='Merkez Şube', aktif=True)
            session.add(yeni_sube)
            session.flush()
            
            # Depo
            yeni_depo = Depo(firma_id=yeni_firma.id, sube_id=yeni_sube.id, kod='ANA', ad='Ana Depo', aktif=True)
            session.add(yeni_depo)
            
            # Admin Kullanıcı Eşitleme (UUID)
            # Setup'ta kullandığımız sabit UUID'yi kullanıyoruz
            fb_admin = Kullanici(
                id="550e8400-e29b-41d4-a716-446655440000",
                ad_soyad='Sistem Yöneticisi',
                email='admin@muhasebe.com',
                firma_id=yeni_firma.id,
                sube_id=yeni_sube.id,
                aktif=True
            )
            session.add(fb_admin)
            
            session.commit()
            print("  ✅ Varsayılan veriler eklendi")
            
    except Exception as e:
        print(f"  ❌ Tablo oluşturma hatası: {e}")

def main():
    with app.app_context():
        print("🚀 MASTER DB (MySQL/SQLite) Kuruluyor...")
        
        # ⚠️ drop_all kullanırken dikkatli ol, verileri siler!
        db.drop_all() 
        db.create_all()
        
        # 1. Tenant
        tenant = Tenant(
            id="11111111-1111-1111-1111-111111111111",
            kod='MUHASEBE',
            unvan='Muhasebe Firması A.Ş.',
            db_name='MUHASEBEDB.FDB',
            vergi_no='1234567890',
            is_active=True
        )
        tenant.set_db_password('masterkey')
        db.session.add(tenant)
        
        # 2. Lisans
        license = License(
            tenant_id=tenant.id,
            license_type='enterprise',
            valid_from=datetime.now(),
            valid_until=datetime.now() + timedelta(days=365),
            max_users=100,
            is_active=True
        )
        license.generate_license_key()
        db.session.add(license)
        
        # 3. Admin User
        admin_uuid = "550e8400-e29b-41d4-a716-446655440000"
        admin = User(
            id=admin_uuid,
            email='admin@muhasebe.com',
            full_name='Sistem Yöneticisi',
            is_active=True,
            is_superadmin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # 4. Yetki
        role = UserTenantRole(
            user_id=admin.id,
            tenant_id=tenant.id,
            role='admin',
            is_default=True,
            is_active=True
        )
        db.session.add(role)
        
        db.session.commit()
        print("✅ Master DB Tamamlandı.")

        # 5. Firebird Kurulumunu Tetikle
        setup_tenant_database(tenant)

        print("\n" + "="*50)
        print("✅ TÜM SİSTEM (MASTER + FIREBIRD) HAZIR")
        print("="*50)

if __name__ == "__main__":
    main()