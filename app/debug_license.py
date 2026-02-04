# debug_license.py

import os
import sys

# Proje yollarını ekleyelim
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from services.license_client import LicenseClient
    print("✅ LicenseClient modülü başarıyla yüklendi.")
except ImportError as e:
    print(f"❌ Modül yükleme hatası: {e}")
    sys.exit()

def test_license():
    lic = LicenseClient()
    
    # 1. Dosya var mı?
    lic_path = os.path.join(BASE_DIR, '', 'license.lic')
    if os.path.exists(lic_path):
        print(f"✅ Lisans dosyası bulundu: {lic_path}")
    else:
        print(f"❌ Lisans dosyası bulunamadı! Aranan yol: {lic_path}")
        return

    # 2. Dosyayı yükle ve çöz (Senin kullandığın metod ismiyle)
    print("\n🔍 Lisans çözülüyor...")
    # Eğer metod ismin farklıysa (validate_license gibi) burayı güncelle
    result = lic._load_local_license() 
    print(result)
    if result.get('valid'):
        print("🟢 LİSANS GEÇERLİ")
        print("-" * 30)
        # Hassas bilgileri (şifreleri) yıldızlayarak gösterelim
        data = result.get('data', {})
        for key, value in data.items():
            if 'password' in key.lower():
                print(f"📌 {key}: {'*' * len(str(value))} (Veri mevcut)")
            else:
                print(f"📌 {key}: {value}")
        print("-" * 30)
    else:
        print("🔴 LİSANS GEÇERSİZ!")
        print(f"Sebep: {result.get('reason', 'Bilinmeyen hata')}")
        print(f"Dönen veri: {result}")

if __name__ == "__main__":
    test_license()