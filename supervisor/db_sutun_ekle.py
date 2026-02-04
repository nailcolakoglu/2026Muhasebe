# db_sutun_ekle.py

import sqlite3
import os

# Veritabanı dosyasının tam yolu
# Eğer supervisor.db kullanıyorsa yolu ona göre değiştirin, ama genelde master.db kullanılır.
DB_PATH = r"D:\GitHup\Muhasebe\supervisor\supervisor.db"

if not os.path.exists(DB_PATH):
    print(f"❌ HATA: Veritabanı dosyası bulunamadı: {DB_PATH}")
    exit()

print(f"Veritabanı açılıyor: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Eklenecek sütunlar ve tipleri
new_columns = [
    ("file_size", "INTEGER DEFAULT 0"),
    ("file_size_mb", "FLOAT DEFAULT 0.0"),
    ("compression_ratio", "FLOAT DEFAULT 1.0"),
    ("storage_provider", "VARCHAR(20) DEFAULT 'local'"),
    ("remote_path", "VARCHAR(500)"),
    ("is_immutable", "BOOLEAN DEFAULT 0"),
    ("cloud_status", "VARCHAR(500)"),
    ("restore_count", "INTEGER DEFAULT 0"),
    ("last_restored_at", "DATETIME")
]

table_name = "backups"

print(f"🔧 '{table_name}' tablosu güncelleniyor...")

for col_name, col_type in new_columns:
    try:
        # Sütun ekleme komutu
        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
        cursor.execute(alter_query)
        print(f"   ✅ Eklendi: {col_name}")
    except sqlite3.OperationalError as e:
        # Eğer sütun zaten varsa hata verir, bunu yakalayıp geçiyoruz
        if "duplicate column name" in str(e):
            print(f"   ℹ️ Zaten var: {col_name}")
        else:
            print(f"   ❌ Hata ({col_name}): {e}")

try:
    conn.commit()
    print("\n✅ Veritabanı güncellemesi tamamlandı!")
except Exception as e:
    conn.rollback()
    print(f"\n❌ Kayıt hatası: {e}")

conn.close()
input("Çıkmak için Enter'a basın...")