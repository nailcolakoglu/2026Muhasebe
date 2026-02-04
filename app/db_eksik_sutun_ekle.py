# db_eksik_sutun_ekle.db

import sqlite3
import os

# Veritabanı dosyasının tam yolu
DB_PATH = r"D:\GitHup\Muhasebe\app\master.db"

if not os.path.exists(DB_PATH):
    print(f"❌ HATA: Veritabanı dosyası bulunamadı: {DB_PATH}")
    exit()

print(f"Veritabanı açılıyor: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Eksik kalan sütunlar
new_columns = [
    ("message", "TEXT"),        # Hata mesajı veya genel notlar için
    ("error_message", "TEXT")   # Kritik hata detayları için
]

table_name = "backups"
print(f"🔧 '{table_name}' tablosu eksikler için taranıyor...")

for col_name, col_type in new_columns:
    try:
        # Sütun ekleme komutu
        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
        cursor.execute(alter_query)
        print(f"   ✅ Eklendi: {col_name}")
    except sqlite3.OperationalError as e:
        # Eğer sütun zaten varsa hata verir, sorun yok
        if "duplicate column name" in str(e):
            print(f"   ℹ️ Zaten var: {col_name}")
        else:
            print(f"   ❌ Hata ({col_name}): {e}")

try:
    conn.commit()
    print("\n✅ Veritabanı eksikleri giderildi!")
except Exception as e:
    conn.rollback()
    print(f"\n❌ Kayıt hatası: {e}")

conn.close()
input("Çıkmak için Enter'a basın...")