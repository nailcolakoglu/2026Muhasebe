# create_manual_lic.py

from services.license_client import LicenseClient
import json

def create_manual_license():
    lic = LicenseClient()
    
    # Manuel olarak girmek istediğin lisans verileri
    manual_data = {
        'valid': True,
        'license_id': 'manual-dev-001',
        'tenant_id': 'cbe25c34-b156-4775-9b12-9c0cfffa00d5', # Senin loglarındaki ID
        'tenant_name': 'S.S. İZYUK TÜKETİM KOOP.',
        'db_name': 'MUHASEBEDB.FDB',
        'db_password': 'masterkey', # Buraya Supervisor'daki şifreyi yaz
        'license_key': 'V7KP-6600-54KO-NDJ2',
        'valid_until': '2027-01-06 16:59:56',
        'type': 'enterprise',
        'limits': {
            'max_users': 1,
            'max_branches': 50
        },
        'check_date': '2026-01-08 10:54:25'
    }
    
    # LicenseClient içindeki şifreleme mekanizmasını kullanarak dosyayı kaydet
    try:
        lic._save_local_license(manual_data)
        print("✅ license.lic dosyası başarıyla ve şifreli olarak oluşturuldu.")
    except Exception as e:
        print(f"❌ Dosya oluşturma hatası: {e}")

if __name__ == "__main__":
    create_manual_license()
	