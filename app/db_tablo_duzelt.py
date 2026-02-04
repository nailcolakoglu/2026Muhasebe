# db_tablo_duzelt.py

import sqlite3
import os

# Veritabanı yolu
DB_PATH = r"D:\GitHup\Muhasebe\app\master.db"

if not os.path.exists(DB_PATH):
    print(f"❌ Veritabanı bulunamadı: {DB_PATH}")
    exit()

print(f"Veritabanına bağlanılıyor: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # 1. Eski tabloyu kaldır
    cursor.execute("DROP TABLE IF EXISTS backups")
    print("🗑️  Eski 'backups' tablosu silindi.")

    # 2. Yeni tabloyu (NULLABLE sütunlarla) oluştur
    create_sql = """
    CREATE TABLE backups (
        id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        
        -- ARTIK BOŞ GEÇİLEBİLİR (NULLABLE)
        file_name VARCHAR(255),
        file_path VARCHAR(500),
        
        file_size INTEGER DEFAULT 0,
        
        -- Diğer alanlar
        status VARCHAR(20) DEFAULT 'pending',
        message TEXT,
        backup_type VARCHAR(20) DEFAULT 'manual',
        cloud_status VARCHAR(500),
        
        -- Yeni alanlar (Compression vs.)
        file_size_mb FLOAT DEFAULT 0.0,
        compression_ratio FLOAT DEFAULT 1.0,
        storage_provider VARCHAR(20) DEFAULT 'local',
        remote_path VARCHAR(500),
        is_immutable BOOLEAN DEFAULT 0,
        progress_percent INTEGER DEFAULT 0,
        error_message TEXT,
        
        started_at DATETIME,
        completed_at DATETIME,
        duration_seconds INTEGER DEFAULT 0,
        
        restore_count INTEGER DEFAULT 0,
        last_restored_at DATETIME,
        
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by VARCHAR(36),
        
        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
        FOREIGN KEY(created_by) REFERENCES supervisors(id)
    );
    """
    
    cursor.execute(create_sql)
    print("✅ Yeni 'backups' tablosu oluşturuldu (Nullable Sütunlar ile).")
    
    conn.commit()

except Exception as e:
    print(f"❌ HATA: {e}")
    conn.rollback()

conn.close()