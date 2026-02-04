# db_olustur_backupconfig.py

import sqlite3
import os
import uuid
from datetime import datetime

# Veritabanı yolu (Kendi yolunuza göre düzenleyin)
DB_PATH = r"D:\GitHup\Muhasebe\app\master.db"

if not os.path.exists(DB_PATH):
    print(f"❌ Veritabanı bulunamadı: {DB_PATH}")
    exit()

print(f"Veritabanı bağlanıyor: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Tablo oluşturma SQL komutu
create_table_sql = """
CREATE TABLE IF NOT EXISTS backup_configs (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL UNIQUE,
    provider VARCHAR(20) DEFAULT 'local',
    
    -- AWS S3 Ayarları
    aws_access_key VARCHAR(255),
    aws_secret_key VARCHAR(255),
    aws_bucket_name VARCHAR(100),
    aws_region VARCHAR(50) DEFAULT 'eu-central-1',
    
    -- FTP Ayarları
    ftp_host VARCHAR(100),
    ftp_user VARCHAR(100),
    ftp_password VARCHAR(100),
    ftp_port INTEGER DEFAULT 21,
    
    -- Kurallar
    frequency VARCHAR(20) DEFAULT 'daily',
    retention_days INTEGER DEFAULT 30,
    encrypt_backups BOOLEAN DEFAULT 1,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

try:
    cursor.execute(create_table_sql)
    conn.commit()
    print("✅ 'backup_configs' tablosu başarıyla oluşturuldu/doğrulandı.")
    
    # Sütun kontrolü (Eski tablo varsa yeni sütunları eklemek için)
    # Basit bir kontrol mekanizması
    cursor.execute("PRAGMA table_info(backup_configs)")
    columns = [info[1] for info in cursor.fetchall()]
    
    # Eksik sütunları ekle (Migration mantığı)
    expected_columns = {
        'provider': 'VARCHAR(20) DEFAULT "local"',
        'aws_access_key': 'VARCHAR(255)',
        'aws_secret_key': 'VARCHAR(255)',
        'encrypt_backups': 'BOOLEAN DEFAULT 1'
    }
    
    for col_name, col_def in expected_columns.items():
        if col_name not in columns:
            print(f"🛠️ Sütun ekleniyor: {col_name}")
            try:
                cursor.execute(f"ALTER TABLE backup_configs ADD COLUMN {col_name} {col_def}")
                conn.commit()
            except Exception as e:
                print(f"⚠️ Sütun eklenirken uyarı: {e}")

except Exception as e:
    print(f"❌ Hata oluştu: {e}")

conn.close()
print("İşlem tamamlandı.")