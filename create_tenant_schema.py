# create_tenant_schema.py (Standalone Script)

import sys
import os

# Projeyi sys.path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from sqlalchemy import create_engine, text

app = create_app()

def create_tenant_schema(tenant_db_name):
    """Tenant schema oluştur"""
    with app.app_context():
        try:
            # Tenant DB URL
            tenant_db_url = (
                f"mysql+pymysql://root:nc67fo76sice"
                f"@localhost:3306"
                f"/{tenant_db_name}?charset=utf8mb4"
            )
            
            # Engine oluştur
            tenant_engine = create_engine(tenant_db_url)
            
            # Bağlantıyı test et
            with tenant_engine.connect() as conn:
                result = conn.execute(text("SELECT DATABASE()")).scalar()
                print(f"✅ Bağlantı: {result}")
            
            # Modelleri import et
            from app.models.tenant import Base
            
            # Manuel import (tüm modeller yüklensin)
            from app.modules.stok.models import StokKart
            from app.modules.cari.models import CariHesap
            from app.modules.fatura.models import Fatura
            # ... (diğer import'lar)
            
            # Tabloları oluştur
            Base.metadata.create_all(bind=tenant_engine, checkfirst=True)
            
            print(f"✅ Schema oluşturuldu: {tenant_db_name}")
            print(f"📊 Tablo sayısı: {len(Base.metadata.tables)}")
            
            return True
        
        except Exception as e:
            print(f"❌ Hata: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Kullanım: python create_tenant_schema.py erp_tenant_ABC001")
        sys.exit(1)
    
    tenant_db_name = sys.argv[1]
    create_tenant_schema(tenant_db_name)