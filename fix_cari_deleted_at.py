# fix_cari_deleted_at.py (DÜZELTİLMİŞ)

import sys
import os

# Proje root'unu path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from sqlalchemy import create_engine, text
from app.extensions import db
from app.models.master import Tenant

# Flask app oluştur
app = Flask(__name__)
app.config.from_object('app.config.Config')

# DB'yi initialize et
db.init_app(app)

with app.app_context():
    print("🔧 Tenant DB'lerde deleted_at kolonu ekleniyor...\n")
    
    tenants = Tenant.query.filter_by(is_active=True).all()
    
    if not tenants:
        print("⚠️ Aktif tenant bulunamadı!")
        sys.exit(0)
    
    for tenant in tenants:
        print(f"🔧 {tenant.kod} ({tenant.db_name}) düzeltiliyor...")
        
        # Tenant DB URL
        tenant_db_url = (
            f"mysql+pymysql://"
            f"{app.config['TENANT_DB_USER']}:"
            f"{app.config['TENANT_DB_PASSWORD']}"
            f"@{app.config['TENANT_DB_HOST']}:"
            f"{app.config['TENANT_DB_PORT']}"
            f"/{tenant.db_name}?charset=utf8mb4"
        )
        
        engine = create_engine(tenant_db_url)
        
        with engine.connect() as conn:
            try:
                # Önce kolon var mı kontrol et
                check_query = text("""
                    SELECT COUNT(*) 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = :db_name 
                    AND TABLE_NAME = 'cari_hesaplar' 
                    AND COLUMN_NAME = 'deleted_at'
                """)
                
                result = conn.execute(check_query, {'db_name': tenant.db_name}).scalar()
                
                if result > 0:
                    print(f"  ⏭️  {tenant.kod} - deleted_at zaten var, atlanıyor")
                    continue
                
                # Yoksa ekle
                alter_query = text("""
                    ALTER TABLE cari_hesaplar 
                    ADD COLUMN deleted_at DATETIME NULL AFTER updated_at
                """)
                
                conn.execute(alter_query)
                
                # Index ekle
                index_query = text("""
                    ALTER TABLE cari_hesaplar 
                    ADD INDEX idx_deleted_at (deleted_at)
                """)
                
                conn.execute(index_query)
                
                conn.commit()
                
                print(f"  ✅ {tenant.kod} - deleted_at eklendi")
                
            except Exception as e:
                conn.rollback()
                print(f"  ❌ {tenant.kod} hatası: {e}")

print("\n🎉 İşlem tamamlandı!")