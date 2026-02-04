# supervisor/services/backup_service.py

import os
import sys
import shutil
import subprocess
import zipfile
import time
import logging
from datetime import datetime
from werkzeug.utils import secure_filename

# Config erişimi
try:
    from supervisor_config import SupervisorConfig
except ImportError:
    from config import SupervisorConfig

# Bulut Kütüphaneleri (Opsiyonel importlar)
try:
    import boto3
    from botocore.exceptions import NoCredentialsError
except ImportError:
    boto3 = None

try:
    from google.cloud import storage as gcs
except ImportError:
    gcs = None

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None

# Logger yapılandırması
logger = logging.getLogger(__name__)

class BackupService:
    """
    Firebird Yedekleme ve Bulut Senkronizasyon Servisi
    
    Özellikler:
    1. GBAK ile güvenli yedekleme (.fbk)
    2. ZIP sıkıştırma
    3. Bulut entegrasyonu (AWS S3, GCS, Azure)
    4. Eski yedekleri temizleme (Rotasyon)
    """
    
    def __init__(self):
        self.backup_dir = SupervisorConfig.BACKUP_DIR
        self.firebird_bin = self._find_firebird_bin()
        
        # Bulut Ayarları
        self.s3_bucket = getattr(SupervisorConfig, 'AWS_S3_BUCKET', None)
        self.gcs_bucket = getattr(SupervisorConfig, 'GOOGLE_CLOUD_BUCKET', None)
        self.azure_conn = getattr(SupervisorConfig, 'AZURE_STORAGE_CONNECTION_STRING', None)
        self.azure_container = getattr(SupervisorConfig, 'AZURE_STORAGE_CONTAINER', 'backups')
        
    def _find_firebird_bin(self):
        """Firebird 'gbak' aracının yolunu bulur"""
        # 1. Config'den bak
        if hasattr(SupervisorConfig, 'FIREBIRD_BIN_DIR') and SupervisorConfig.FIREBIRD_BIN_DIR:
            return SupervisorConfig.FIREBIRD_BIN_DIR
            
        # 2. Yaygın yolları dene (Windows)
        paths = [
            r"C:\Program Files\Firebird\Firebird_3.0\bin",
            r"C:\Program Files\Firebird\Firebird_2.5\bin",
            r"C:\Program Files (x86)\Firebird\Firebird_2.5\bin",
            r"D:\Firebird\bin" # Senin yapına uygun olabilir
        ]
        
        for path in paths:
            if os.path.exists(os.path.join(path, 'gbak.exe')):
                return path
                
        # Bulunamazsa PATH'de olduğunu varsay
        return ""

    def create_backup(self, tenant, backup_type='manual'):
        """
        Bir firma için yedek oluşturur.
        
        Args:
            tenant: Tenant modeli nesnesi
            backup_type: 'manual', 'daily', 'weekly', 'monthly'
            
        Returns:
            dict: Sonuç bilgileri
        """
        start_time = time.time()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Klasör yapısı: backups/daily/FirmaKodu/
        target_dir = os.path.join(self.backup_dir, backup_type, secure_filename(tenant.kod))
        os.makedirs(target_dir, exist_ok=True)
        
        # Dosya isimleri
        filename_base = f"{tenant.kod}_{timestamp}_{backup_type}"
        fbk_filename = f"{filename_base}.fbk"
        zip_filename = f"{filename_base}.zip"
        
        fbk_path = os.path.join(target_dir, fbk_filename)
        zip_path = os.path.join(target_dir, zip_filename)
        
        # DB Yolu (Firma DB adından tam yolu bul)
        # Not: Tenant modelinde db_path yoksa, varsayılan dizinden türet
        if hasattr(tenant, 'db_path') and tenant.db_path:
            db_source = tenant.db_path
        else:
            db_source = os.path.join(SupervisorConfig.FIREBIRD_DATA_DIR, tenant.db_name)

        result = {
            'success': False,
            'tenant_id': tenant.id,
            'type': backup_type,
            'file_name': zip_filename,
            'file_path': zip_path,
            'file_size': 0,
            'duration': 0,
            'cloud_status': 'skipped',
            'error': None
        }

        try:
            # 1. GBAK ile Yedekle (Subprocess)
            # -------------------------------------------------
            gbak_exe = os.path.join(self.firebird_bin, 'gbak') if self.firebird_bin else 'gbak'
            
            # Komut: gbak -b -v -user SYSDBA -password masterkey db_path fbk_path
            # -b: backup, -v: verify/verbose, -g: garbage collect
            cmd = [
                gbak_exe, 
                '-b', 
                '-user', SupervisorConfig.FIREBIRD_USER, 
                '-password', SupervisorConfig.FIREBIRD_PASSWORD, 
                db_source, 
                fbk_path
            ]
            
            # Windows'ta pencere açılmasını engelle
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                startupinfo=startupinfo
            )
            
            if process.returncode != 0:
                raise Exception(f"GBAK Hatası: {process.stderr}")
            
            # 2. Sıkıştırma (ZIP)
            # -------------------------------------------------
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(fbk_path, fbk_filename)
            
            # Ham .fbk dosyasını sil (yer tasarrufu)
            if os.path.exists(fbk_path):
                os.remove(fbk_path)
                
            # Dosya boyutu
            file_size = os.path.getsize(zip_path)
            result['file_size'] = file_size
            
            # 3. Buluta Yükle
            # -------------------------------------------------
            cloud_res = self.upload_to_cloud(zip_path, f"{backup_type}/{tenant.kod}/{zip_filename}")
            result['cloud_status'] = cloud_res
            
            result['success'] = True
            
        except Exception as e:
            logger.error(f"Yedekleme hatası ({tenant.kod}): {str(e)}")
            result['error'] = str(e)
            # Hata durumunda yarım kalan dosyaları temizle
            if os.path.exists(fbk_path): os.remove(fbk_path)
            if os.path.exists(zip_path): os.remove(zip_path)
            
        finally:
            result['duration'] = round(time.time() - start_time, 2)
            
        return result

    def upload_to_cloud(self, local_path, cloud_path):
        """
        Yapılandırılmış bulut servisine yükler.
        Sırayla AWS -> Google -> Azure kontrol eder.
        """
        
        # AWS S3
        if self.s3_bucket and boto3:
            try:
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=getattr(SupervisorConfig, 'AWS_ACCESS_KEY_ID', None),
                    aws_secret_access_key=getattr(SupervisorConfig, 'AWS_SECRET_ACCESS_KEY', None),
                    region_name=getattr(SupervisorConfig, 'AWS_S3_REGION', None)
                )
                s3.upload_file(local_path, self.s3_bucket, cloud_path)
                return 'uploaded_s3'
            except Exception as e:
                logger.error(f"S3 Upload Error: {e}")
                return f"failed_s3: {str(e)}"

        # Google Cloud Storage
        elif self.gcs_bucket and gcs:
            try:
                # Auth environment variable'dan otomatik alınır (GOOGLE_APPLICATION_CREDENTIALS)
                client = gcs.Client()
                bucket = client.bucket(self.gcs_bucket)
                blob = bucket.blob(cloud_path)
                blob.upload_from_filename(local_path)
                return 'uploaded_gcs'
            except Exception as e:
                logger.error(f"GCS Upload Error: {e}")
                return f"failed_gcs: {str(e)}"

        # Azure Blob Storage
        elif self.azure_conn and BlobServiceClient:
            try:
                blob_service_client = BlobServiceClient.from_connection_string(self.azure_conn)
                blob_client = blob_service_client.get_blob_client(
                    container=self.azure_container, blob=cloud_path
                )
                with open(local_path, "rb") as data:
                    blob_client.upload_blob(data)
                return 'uploaded_azure'
            except Exception as e:
                logger.error(f"Azure Upload Error: {e}")
                return f"failed_azure: {str(e)}"

        return 'skipped_no_config'

    def cleanup_old_backups(self, retention_days=30):
        """Yerel diskteki eski yedekleri temizler"""
        # Bu kısım retention politikasına göre (config'deki BACKUP_RETENTION_DAYS)
        # klasörleri tarayıp tarih kontrolü yaparak silme işlemini yapacak.
        # Basit bir implementasyon:
        now = time.time()
        cutoff = now - (retention_days * 86400)
        
        count = 0
        for root, dirs, files in os.walk(self.backup_dir):
            for file in files:
                if file.endswith('.zip'):
                    file_path = os.path.join(root, file)
                    if os.path.getmtime(file_path) < cutoff:
                        try:
                            os.remove(file_path)
                            count += 1
                        except OSError:
                            pass
        return count