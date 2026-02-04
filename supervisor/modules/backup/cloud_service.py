# supervisor/modules/backup/cloud_service.py


import os
import boto3
from botocore.exceptions import NoCredentialsError
from ftplib import FTP
from flask import current_app

class CloudUploadService:
    
    @staticmethod
    def upload_to_cloud(local_file_path, tenant_kod, config):
        """
        Dosyayı firmanın seçtiği sağlayıcıya yükler.
        Args:
            local_file_path: Yüklenecek dosya
            tenant_kod: Firma kodu (Klasörleme için)
            config: BackupConfig modeli (Ayarlar)
        """
        if not config:
            return {'success': False, 'message': 'Yedekleme ayarları bulunamadı.'}

        filename = os.path.basename(local_file_path)
        
        # 1. AWS S3 Yüklemesi
        if config.provider == 'aws_s3':
            return CloudUploadService._upload_to_s3(local_file_path, filename, config)
            
        # 2. FTP Yüklemesi
        elif config.provider == 'ftp':
            return CloudUploadService._upload_to_ftp(local_file_path, filename, config)
            
        # 3. Yerel (Zaten yereldeyse işlem yapma)
        elif config.provider == 'local':
            return {'success': True, 'message': 'Yerel yedekleme tamamlandı (Bulut pasif).'}
            
        return {'success': False, 'message': 'Geçersiz sağlayıcı.'}

    @staticmethod
    def _upload_to_s3(file_path, filename, config):
        try:
            s3 = boto3.client(
                's3',
                aws_access_key_id=config.aws_access_key,
                aws_secret_access_key=config.aws_secret_access_key,
                region_name=config.aws_region
            )
            
            # S3 içindeki yol: TENANT_KODU/2026/01/dosya.gbk
            s3_path = f"{config.tenant.kod}/{filename}"
            
            s3.upload_file(file_path, config.aws_bucket_name, s3_path)
            
            return {'success': True, 'message': f"AWS S3'e yüklendi: {config.aws_bucket_name}"}
            
        except FileNotFoundError:
            return {'success': False, 'message': 'Dosya bulunamadı.'}
        except NoCredentialsError:
            return {'success': False, 'message': 'AWS Kimlik bilgileri hatalı.'}
        except Exception as e:
            return {'success': False, 'message': f"AWS Hatası: {str(e)}"}

    @staticmethod
    def _upload_to_ftp(file_path, filename, config):
        try:
            ftp = FTP()
            ftp.connect(config.ftp_host, config.ftp_port)
            ftp.login(config.ftp_user, config.ftp_password)
            
            # Klasör kontrolü (Tenant adına klasör aç)
            try:
                ftp.cwd(config.tenant.kod)
            except:
                ftp.mkd(config.tenant.kod)
                ftp.cwd(config.tenant.kod)
            
            with open(file_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
            
            ftp.quit()
            return {'success': True, 'message': f"FTP sunucusuna yüklendi: {config.ftp_host}"}
            
        except Exception as e:
            return {'success': False, 'message': f"FTP Hatası: {str(e)}"}