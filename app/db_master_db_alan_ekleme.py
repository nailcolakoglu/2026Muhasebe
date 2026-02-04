# db_yamasi.py
import sqlite3
import os

# Veritabanı dosyasının tam yolunu buraya yaz (Kendi yoluna göre düzenle)
# Örnek: D:\GitHup\Muhasebe\app\master.db
DB_PATH = r"D:\GitHup\Muhasebe\app\master.db"

if not os.path.exists(DB_PATH):
    print(f"❌ HATA: Veritabanı bulunamadı: {DB_PATH}")
    exit()

print(f"Veritabanı bağlanıyor: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Sütun ekleme komutu
    cursor.execute("ALTER TABLE licenses ADD COLUMN hardware_id VARCHAR(255)")
    conn.commit()
    print("✅ BAŞARILI: 'hardware_id' sütunu eklendi.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ BİLGİ: Sütun zaten varmış, işlem yapılmasına gerek yok.")
    else:
        print(f"❌ HATA: {e}")
except Exception as e:
    print(f"❌ BEKLENMEYEN HATA: {e}")

conn.close()