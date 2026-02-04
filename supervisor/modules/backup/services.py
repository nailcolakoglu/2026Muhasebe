# supervisor/modules/backup/services.py

import os
import subprocess
import platform
import shutil
from datetime import datetime
from flask import current_app

class BackupService:
    
    @staticmethod
    def make_immutable(file_path):
        """
        Dosyayı 'Değiştirilemez' (Immutable) yapar.
        Ransomware koruması için kritik adımdır.
        """
        system = platform.system()
        
        try:
            if system == 'Windows':
                # Windows'ta dosyayı 'Read-Only' yap ve ACL ile silmeyi zorlaştır
                # 1. Salt Okunur yap
                os.chmod(file_path, 0o444) 
                
                # 2. (İleri Seviye) ICACLS ile "Delete" yetkisini kaldır
                # Bu komut o anki kullanıcıdan silme yetkisini alır.
                # cmd = f'icacls "{file_path}" /deny "Everyone":(DE,DC)'
                # subprocess.run(cmd, shell=True)
                
            else:
                # Linux'ta chattr +i (root yetkisi gerektirir)
                # subprocess.run(['chattr', '+i', file_path])
                os.chmod(file_path, 0o444) # Fallback
                
            return True
        except Exception as e:
            print(f"⚠️ Dosya kilitlenemedi: {e}")
            return False

    @staticmethod
    def backup_database(tenant_db_path, tenant_kod):
        """
        Firebird Veritabanını Yedekle (GBK Formatı)
        """
        # 1. Klasör Hazırlığı
        backup_dir = os.path.join(current_app.config['BACKUP_DIR'], tenant_kod)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f"{tenant_kod}_{timestamp}.gbk")
        log_file = os.path.join(backup_dir, f"{tenant_kod}_{timestamp}.log")
        
        # 2. GBAK Komutu (Firebird Yedekleme Aracı)
        # -b: Backup, -v: Verbose (Detaylı), -t: Transportable, -user SYSDBA -pas masterkey
        gbak_path = r"C:\Program Files\Firebird\Firebird_2_5\bin\gbak.exe" # Firebird yolunu Config'den almalı
        
        # Config'den almayı dene, yoksa varsayılanı kullan
        if hasattr(current_app.config, 'FIREBIRD_BIN_DIR'):
             gbak_path = os.path.join(current_app.config['FIREBIRD_BIN_DIR'], 'gbak.exe')

        cmd = [
            gbak_path,
            '-b', '-v', '-t',
            '-user', 'SYSDBA',
            '-pas', 'masterkey', # Güvenlik için Config'den gelmeli
            tenant_db_path,
            backup_file
        ]
        
        try:
            # Yedekleme işlemini başlat
            with open(log_file, "w") as log:
                process = subprocess.run(cmd, stdout=log, stderr=log, text=True)
            
            if process.returncode == 0:
                # ✅ Yedekleme Başarılı -> ŞİMDİ KİLİTLE (Immutable)
                BackupService.make_immutable(backup_file)

                # 2. Buluta Gönder (YENİ)
                # config nesnesini veritabanından çekmemiz lazım
                from models.master import BackupConfig, Tenant
                tenant = Tenant.query.filter_by(kod=tenant_kod).first()
                config = BackupConfig.query.filter_by(tenant_id=tenant.id).first()
                
                cloud_result = {'success': True, 'message': 'Bulut ayarı yok.'}
                
                if config:
                    from .cloud_service import CloudUploadService
                    cloud_result = CloudUploadService.upload_to_cloud(backup_file, tenant_kod, config)
                    
                return {
                    'success': True, 
                    'file': backup_file, 
                    'cloud_status': cloud_result, # Sonuca ekledik
                    'message': f'Yerel: OK, Bulut: {cloud_result["message"]}'
                }
         
            else:
                return {'success': False, 'message': 'GBAK işlemi hata ile sonlandı. Logu inceleyin.'}
                
        except Exception as e:
            return {'success': False, 'message': f"Sistem hatası: {str(e)}"}