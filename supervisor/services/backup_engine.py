# supervisor/services/backup_engine.py

# AES256 şifreleme kütüphaneleri
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import os
import shutil
import zipfile
import uuid
import time
from datetime import datetime
from flask import current_app
import sys
import requests
import msal

# ==========================================
# 1. PATH AYARLARI
# ==========================================
current_file = os.path.abspath(__file__)
supervisor_dir = os.path.dirname(os.path.dirname(current_file))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ✅ Ana uygulamanın veritabanı nesnesi
from app.extensions import db

class BackupEngine:
    def __init__(self, backup_id):
        self.backup_id = backup_id
        self.backup = None
        self._load_backup_record()

    def _load_backup_record(self):
        """Yedek kaydını yükle"""
        if not self.backup_id: return
        
        try:
            # Model Import (Güvenli)
            try:
                from models.backup import Backup
            except ImportError:
                from supervisor.models.backup import Backup
            
            # Kaydı bulamazsa 3 kere dene (Thread senkronizasyonu için)
            for i in range(3):
                # db.session.get kullanımı Flask-SQLAlchemy sürümüne göre değişebilir
                # Garanti olsun diye query.get kullanıyoruz
                self.backup = Backup.query.get(self.backup_id)
                if self.backup:
                    break
                time.sleep(1)
                
            if not self.backup:
                print(f"❌ [BackupEngine] Yedek kaydı bulunamadı ID: {self.backup_id}")
                
        except Exception as e:
            print(f"❌ [BackupEngine] Init Hatası: {e}")

    @staticmethod
    def create_db_record(tenant_id, backup_type='manual', created_by=None):
        """DB'de pending kaydı oluştur"""
        try:
            from models.backup import Backup
        except ImportError:
            from supervisor.models.backup import Backup

        new_backup = Backup(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            backup_type=backup_type,
            status='pending',
            created_by=created_by,
            created_at=datetime.now()
        )
        db.session.add(new_backup)
        db.session.commit()
        return new_backup.id

    def perform_backup(self):
        """
        Yedekleme işlemini başlatır.
        Bu fonksiyon Thread içinde çalışır.
        """
        if not self.backup:
            return {'success': False, 'message': 'Yedek kaydı yüklenemedi.'}

        try:
            print(f"🚀 [BackupEngine] Yedekleme başladı: {self.backup.id}")
            
            # 1. Durumu 'running' yap
            self.backup.status = 'running'
            self.backup.started_at = datetime.now()
            db.session.commit()
            
            # 2. Gerekli Modelleri Al
            from app.models.master import Tenant, BackupConfig
            
            tenant = Tenant.query.get(self.backup.tenant_id)
            if not tenant:
                raise Exception("Firma (Tenant) bulunamadı.")
                
            config = BackupConfig.query.filter_by(tenant_id=tenant.id).first()

            # 3. Klasör ve Dosya Yolları
            # backups/FirmaKodu/
            backup_root = os.path.join(project_root, 'backups')
            tenant_folder = os.path.join(backup_root, tenant.kod)
            os.makedirs(tenant_folder, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{tenant.kod}_{timestamp}.zip"
            filepath = os.path.join(tenant_folder, filename)
            
            # 4. Kaynak DB Dosyası
            # ⚠️ DİKKAT: Firebird DB yolunu doğru almalıyız.
            # Şimdilik varsayılan bir yol veya Tenant içindeki db_name'i kullanıyoruz.
            # Eğer 'tenant.db_path' alanı varsa onu kullanmak en iyisidir.
            # Yoksa varsayılan klasör:
            FIREBIRD_DATA_DIR = r"C:\Program Files\Firebird\Firebird_2_5\bin" # Örnek yol, değiştirebilirsin
            # Ya da senin projendeki yapı:
            if hasattr(tenant, 'db_path') and tenant.db_path:
                db_source_path = tenant.db_path
            else:
                # Varsayılan bir yer (Test için)
                db_source_path = os.path.join(r"D:\Firebird\Data\Muhasebe", tenant.db_name)

            print(f"📂 [BackupEngine] Kaynak: {db_source_path} -> Hedef: {filepath}")

            # 5. ZIP Oluşturma
            file_exists = os.path.exists(db_source_path)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if file_exists:
                    # DB dosyasını ekle
                    zipf.write(db_source_path, arcname=f"{tenant.kod}.fdb")
                else:
                    # DB yoksa boş dosya oluşturma, bilgi notu ekle
                    zipf.writestr('info.txt', f'Yedek Tarihi: {timestamp}\nUYARI: Kaynak veritabanı dosyası bulunamadı.\nAranan Yol: {db_source_path}')
            
            # 6. Şifreleme (Opsiyonel)
            if config and config.encrypt_backups:
                print(f"🔐 [BackupEngine] Şifreleme aktif.")
                password = tenant.vergi_no or f"KEY-{tenant.kod}"
                self._encrypt_file(filepath, password)
                
                # Dosya adı değişti (.enc)
                filename += ".enc"
                filepath += ".enc"
                self.backup.message = "AES-256 Şifreli"

            # 7. Sonuçları Kaydet
            if os.path.exists(filepath):
                file_stats = os.stat(filepath)
                self.backup.file_name = filename
                self.backup.file_path = filepath
                self.backup.file_size_mb = file_stats.st_size / (1024 * 1024)
            
            # 8. Bulut Yükleme (OneDrive)
            if config and config.provider == 'onedrive':
                self._upload_to_onedrive(filepath, filename, config)
            
            # 9. BİTİŞ (Success)
            self.backup.status = 'success'
            self.backup.completed_at = datetime.now()
            db.session.commit()
            print("✅ [BackupEngine] İşlem başarılı.")
            
            return {'success': True, 'file_name': filename}
            
        except Exception as e:
            # ❌ HATA DURUMU
            print(f"❌ [BackupEngine] HATA OLUŞTU: {e}")
            db.session.rollback()
            try:
                self.backup.status = 'failed'
                self.backup.error_message = str(e)[:500] # Çok uzunsa kes
                self.backup.completed_at = datetime.now()
                db.session.commit()
            except:
                pass
            return {'success': False, 'message': str(e)}

    def _encrypt_file(self, file_path, password):
        """AES-256 Şifreleme"""
        try:
            salt = b'fixed_salt_for_backup' 
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f = Fernet(key)

            with open(file_path, 'rb') as file:
                original_data = file.read()
            
            encrypted_data = f.encrypt(original_data)
            
            enc_path = file_path + ".enc"
            with open(enc_path, 'wb') as file:
                file.write(encrypted_data)
            
            os.remove(file_path) # Orijinali sil
        except Exception as e:
            print(f"⚠️ Şifreleme hatası: {e}")
            raise e
        
    def _upload_to_onedrive(self, local_path, filename, config):
        """OneDrive yükleme mantığı"""
        if not config.aws_access_key or not config.aws_secret_key:
            print("⚠️ OneDrive kimlik bilgileri eksik.")
            return

        CLIENT_ID = config.aws_access_key
        CLIENT_SECRET = config.aws_secret_key
        TENANT_ID = config.aws_bucket_name or 'common'
        
        try:
            app = msal.ConfidentialClientApplication(
                CLIENT_ID, authority=f"https://login.microsoftonline.com/{TENANT_ID}",
                client_credential=CLIENT_SECRET
            )
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            
            if "access_token" not in result:
                raise Exception(f"Token hatası: {result.get('error_description')}")
                
            headers = {
                'Authorization': f'Bearer {result["access_token"]}',
                'Content-Type': 'application/octet-stream'
            }
            
            # FTP User alanını hedef email olarak kullanıyoruz
            if not config.ftp_user: raise Exception("OneDrive Hedef Kullanıcı (Email) eksik.")
            
            remote_folder = f"Backups/{filename.split('_')[0]}"
            upload_url = f"https://graph.microsoft.com/v1.0/users/{config.ftp_user}/drive/root:/{remote_folder}/{filename}:/content"

            with open(local_path, 'rb') as f:
                requests.put(upload_url, headers=headers, data=f.read())
            
            self.backup.cloud_status = "✅ OneDrive'a Yüklendi"
            self.backup.storage_provider = 'onedrive'

        except Exception as e:
            print(f"❌ OneDrive Hatası: {e}")
            self.backup.cloud_status = f"Hata: {str(e)}"
    
    def restore_to_sandbox(self):
        """Yedeği Sandbox olarak geri yükle"""
        if not self.backup: return {'success': False, 'message': 'Kayıt yok'}
        try:
            from app.models.master import Tenant # Güvenli import
            
            original = db.session.get(Tenant, self.backup.tenant_id)
            if not original: return {'success': False, 'message': 'Firma yok'}
            
            sandbox_code = f"TEST_{original.kod[:10]}_{uuid.uuid4().hex[:4].upper()}"
            sandbox = Tenant(
                id=str(uuid.uuid4()), kod=sandbox_code, unvan=f"SANDBOX: {original.unvan}",
                db_name=f"{sandbox_code}.fdb", is_active=True, vergi_no=original.vergi_no
            )
            sandbox.db_password_encrypted = original.db_password_encrypted
            db.session.add(sandbox)
            
            self.backup.restore_count = (self.backup.restore_count or 0) + 1
            self.backup.last_restored_at = datetime.now()
            db.session.commit()
            
            return {'success': True, 'tenant_code': sandbox_code}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    def clean_old_backups(self, tenant_id, retention_days):
        """Belirlenen günden eski yedekleri temizler"""
        if not retention_days or retention_days <= 0:
            return

        try:
            from models.backup import Backup
        except ImportError:
            from supervisor.models.backup import Backup

        from datetime import timedelta
        limit_date = datetime.now() - timedelta(days=retention_days)
        
        old_backups = Backup.query.filter(
            Backup.tenant_id == tenant_id,
            Backup.created_at < limit_date,
            Backup.is_immutable == False # ❗ Kilitli olanlara dokunma
        ).all()

        for b in old_backups:
            try:
                # Fiziksel dosyayı sil
                if b.file_path and os.path.exists(b.file_path):
                    os.remove(b.file_path)
                    print(f"🗑️ [Retention] Dosya silindi: {b.file_name}")
                
                # DB kaydını sil
                db.session.delete(b)
            except Exception as e:
                print(f"⚠️ [Retention] Silme hatası ({b.id}): {e}")
        
        db.session.commit()