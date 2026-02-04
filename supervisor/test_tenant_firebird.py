# test_tenant_firebird.py (supervisor/ klasöründe)

import sys
import os

# Path ayarları
BASE_DIR = os.path.dirname(__file__)
APP_DIR = os.path.join(BASE_DIR, '..', 'app')
sys.path.insert(0, APP_DIR)
sys.path.insert(0, BASE_DIR)

from services.firebird_service import FirebirdService

print("\n" + "="*60)
print("🔵 FİREBİRD TEST BAŞLIYOR")
print("="*60)

# Test parametreleri
test_kod = 'TESTFIRMA'
test_db_name = 'TESTFIRMA_MUHASEBE.FDB'

# Firebird Service
fb_service = FirebirdService()

# Veritabanı oluştur
result = fb_service.create_database(test_kod, test_db_name)

# Sonuç
print("\n" + "="*60)
print("🎯 TEST SONUCU:")
print("="*60)
print(f"✅ Başarılı: {result['success']}")
print(f"📂 DB Path:   {result.get('db_path')}")
print(f"💬 Mesaj:    {result.get('message')}")
print(f"❌ Hata:     {result.get('error')}")
print("="*60)

# Dosya kontrolü
if result['success'] and result.get('db_path'):
    db_path = result['db_path']
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print(f"✅ Dosya mevcut: {db_path}")
        print(f"📊 Boyut:         {file_size / 1024:.2f} KB")
    else:
        print(f"❌ Dosya bulunamadı: {db_path}")

print("\n")