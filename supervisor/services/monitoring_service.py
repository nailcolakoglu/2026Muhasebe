import psutil
import platform
import fdb
from datetime import datetime
import os   

class MonitoringService:
    @staticmethod
    def get_system_stats():
        """Sunucu kaynak kullanım bilgilerini döner"""
        # CPU ve RAM bilgileri
        cpu_usage = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        
        # Disk Bilgisi (Yedeklerin tutulduğu ana sürücü)
        disk = psutil.disk_usage('/') 
        
        # Uptime (Çalışma Süresi)
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(datetime.now() - boot_time).split('.')[0]
        
        return {
            'cpu': cpu_usage,
            'ram_percent': ram.percent,
            'ram_used': round(ram.used / (1024**3), 2),
            'ram_total': round(ram.total / (1024**3), 2),
            'disk_percent': disk.percent,
            'disk_free': round(disk.free / (1024**3), 2),
            'disk_total': round(disk.total / (1024**3), 2),
            'uptime': uptime,
            'os': f"{platform.system()} {platform.release()}",
            'processor': platform.processor()
        }

# supervisor/services/monitoring_service.py

    @staticmethod
    def get_active_db_connections(tenant_list):
        """Firmaların veritabanlarındaki aktif kullanıcıları sayar"""
        active_connections = []
        
        for tenant in tenant_list:
            # 💡 Modelindeki gerçek isim: db_name
            db_path = tenant.db_name 
            
            if not db_path:
                continue
                
            conn = None
            try:
                # 💡 Şifreleme kullandığın için modeldeki metodu çağırıyoruz
                # Eğer MonitoringService MasterBase'e erişemiyorsa varsayılan 'masterkey' kullanılır
                try:
                    db_pass = tenant.get_db_password()
                except:
                    db_pass = 'masterkey'

                dsn = db_path
                if not (":" in dsn):
                    dsn = f"localhost:{dsn}"

                conn = fdb.connect(
                    dsn=dsn,
                    user='SYSDBA', 
                    password=db_pass,
                    charset='UTF8'
                )
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT MON$USER, MON$REMOTE_ADDRESS, MON$TIMESTAMP, MON$REMOTE_PROCESS
                    FROM MON$ATTACHMENTS 
                    WHERE MON$ATTACHMENT_ID <> CURRENT_CONNECTION
                    AND MON$REMOTE_PROCESS IS NOT NULL
                """)
                rows = cur.fetchall()
                
                if rows:
                    active_connections.append({
                        'unvan': tenant.unvan,
                        'count': len(rows),
                        'details': [
                            {
                                'user': r[0].strip(), 
                                'ip': r[1] if r[1] else 'Localhost', 
                                'time': r[2].strftime('%H:%M:%S'),
                                'process': r[3].split('\\')[-1] if r[3] else 'Bilinmiyor'
                            } for r in rows
                        ]
                    })
            except Exception as e:
                print(f"⚠️ {tenant.unvan} Bağlantı Hatası: {e}")
                continue
            finally:
                if conn: conn.close()
                
        return active_connections

    @staticmethod
    def get_active_db_connections(tenant_list):
        active_connections = []
        # Sabit veri dizinimiz
        BASE_DB_DIR = r"D:\Firebird\Data"
        
        for tenant in tenant_list:
            # Modelindeki db_name sadece dosya adını tutuyorsa (Örn: MUHASEBEDB.FDB)
            db_file = tenant.db_name
            if not db_file: continue
            
            # Tam yolu oluştur: D:\Firebird\Data\Muhasebe\MUHASEBEDB.FDB
            full_path = os.path.join(BASE_DB_DIR, db_file)
            dsn = f"localhost:{full_path}"
            
            conn = None
            try:
                db_pass = tenant.get_db_password()
                conn = fdb.connect(dsn=dsn, user='SYSDBA', password=db_pass, charset='UTF8')
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT MON$USER, MON$REMOTE_ADDRESS, MON$TIMESTAMP, MON$REMOTE_PROCESS
                    FROM MON$ATTACHMENTS 
                    WHERE MON$ATTACHMENT_ID <> CURRENT_CONNECTION
                    AND MON$REMOTE_PROCESS IS NOT NULL
                """)
                rows = cur.fetchall()
                
                if rows:
                    active_connections.append({
                        'unvan': tenant.unvan,
                        'count': len(rows),
                        'details': [
                            {
                                'user': r[0].strip(), 
                                'ip': r[1] if r[1] else 'Localhost', 
                                'time': r[2].strftime('%H:%M:%S'),
                                'process': r[3].split('\\')[-1] if r[3] else 'Bilinmiyor'
                            } for r in rows
                        ]
                    })
            except Exception as e:
                print(f"⚠️ {tenant.unvan} Bağlantı Hatası: {e}")
                continue
            finally:
                if conn:
                    conn.close()
                
        return active_connections
        
        