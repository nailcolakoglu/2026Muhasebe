# test_bolge_debug.py

import sys
import os
import importlib.util

# Proje root
project_root = r'D:\GitHup\2026Muhasebe'
sys.path.insert(0, project_root)

# app.py dosyasını direkt yükle
spec = importlib.util.spec_from_file_location("app_module", os.path.join(project_root, "run.py"))
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

# app instance'ı al
flask_app = app_module.app

print("=" * 60)
print("✅ Flask App Yüklendi!")
print("=" * 60)

# Test et
from app.extensions import get_tenant_db
from app.modules.bolge.models import Bolge
from flask import session

def test_bolge():
    with flask_app.app_context():
        with flask_app.test_request_context():
            # Tenant ID (gerçek tenant ID'nizi girin)
            session['tenant_id'] = '3851b622-74d4-423d-947a-998ec7f27ef3'
            
            tenant_db = get_tenant_db()
            
            if not tenant_db:
                print("❌ Tenant DB bağlantısı yok!")
                return
            
            print("\n📊 BÖLGE LİSTESİ:")
            print("-" * 60)
            
            try:
                bolgeler = tenant_db.query(Bolge).all()
                
                if bolgeler:
                    print(f"✅ Toplam Bölge: {len(bolgeler)}\n")
                    for b in bolgeler:
                        print(f"Kod: {b.kod:<10} | Ad: {b.ad:<30}")
                        print(f"Firma ID: {b.firma_id} | Aktif: {b.aktif}")
                        print("-" * 60)
                else:
                    print("⚠️ Hiç bölge bulunamadı!")
                    print("Önce /bolge sayfasından bölge ekleyin.")
            
            except Exception as e:
                print(f"❌ Hata: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    test_bolge()