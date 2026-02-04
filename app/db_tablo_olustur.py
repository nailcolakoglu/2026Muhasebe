# db_tablo_olustur.py

import sqlite3
import os

# Veritabanı yolu (Kendi yoluna göre ayarla)
DB_PATH = r"D:\GitHup\Muhasebe\app\master.db"

if not os.path.exists(DB_PATH):
    print("❌ Veritabanı bulunamadı!")
    exit()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Backups tablosunu oluştur (Eğer yoksa)
sql = """
CREATE TABLE IF NOT EXISTS backups (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    message TEXT,
    backup_type VARCHAR(20) DEFAULT 'manual',
    cloud_status VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(36),
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

try:
    cursor.execute(sql)
    conn.commit()
    print("✅ 'backups' tablosu başarıyla oluşturuldu.")
except Exception as e:
    print(f"❌ Hata: {e}")

conn.close()