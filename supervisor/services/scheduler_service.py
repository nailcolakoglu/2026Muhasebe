# services/scheduler_service.py

import os
import sys
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

# Logging ayarları
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

class SchedulerService:
    scheduler = BackgroundScheduler(daemon=True)
    _app = None  # Flask app referansı

    @staticmethod
    def init_app(app):
        """Uygulama başladığında zamanlayıcıyı kur"""
        SchedulerService._app = app
        
        # Eğer zaten çalışıyorsa tekrar başlatma
        if not SchedulerService.scheduler.running:
            SchedulerService.scheduler.start()
            print("⏰ [Scheduler] Zamanlayıcı servisi başlatıldı.")
            
        # İlk açılışta mevcut görevleri yükle
        SchedulerService.reload_jobs()

    @staticmethod
    def reload_jobs():
        """Veritabanındaki ayarlara göre görevleri yenile"""
        if not SchedulerService._app:
            print("⚠️ [Scheduler] App context bulunamadı!")
            return

        with SchedulerService._app.app_context():
            from extensions import db
            db.session.expire_all()
            
            SchedulerService.scheduler.remove_all_jobs()
            Setting = SchedulerService._get_setting_model()
            
            if not Setting: return

            try:
                is_enabled = Setting.get('backup_enabled') == 'true'
                daily_time = Setting.get('backup_daily_time', '03:00').strip() # Boşlukları temizle
            except Exception as e:
                print(f"⚠️ [Scheduler] Ayarlar okunamadı: {e}")
                return

            if is_enabled:
                try:
                    # Daha güvenli parçalama: Boşlukları temizle ve sayıya çevir
                    time_parts = daily_time.split(':')
                    hour = int(time_parts[0].strip())
                    minute = int(time_parts[1].strip())
                    
                    SchedulerService.scheduler.add_job(
                        func=SchedulerService._run_daily_backup_job,
                        trigger='cron',
                        hour=hour,
                        minute=minute,
                        id='daily_backup',
                        replace_existing=True,
                        args=[SchedulerService._app] # App context'i içeri taşıyalım
                    )
                    print(f"✅ [Scheduler] Otomatik yedekleme kuruldu: {hour:02d}:{minute:02d}")
                except Exception as e:
                    print(f"❌ [Scheduler] Saat ayarlanırken hata (Format: {daily_time}): {e}")
            else:
                print("ℹ️ [Scheduler] Otomatik yedekleme KAPALI.")
                
                
    @staticmethod
    def _run_daily_backup_job(app):
        """
        Asıl Yedekleme Görevi (Her gece çalışacak olan fonksiyon)
        """
        print("\n" + "="*50)
        print("🚀 [Scheduler] OTOMATİK YEDEKLEME BAŞLADI")
        print("="*50)

        # Thread içinde tekrar context açmamız lazım
        with app.app_context():
            try:
                # 1. Gerekli Modelleri Yükle (Vur-Kaç Taktigi)
                models = SchedulerService._safe_import_models()
                if not models:
                    print("❌ [Scheduler] Modeller yüklenemediği için iptal.")
                    return

                Tenant = models['Tenant']
                BackupConfig = models['BackupConfig']
                BackupEngine = models['BackupEngine']
                User = models['User'] # Gerekirse admin kullanıcısını bulmak için
                
                # 2. Aktif Firmaları Bul
                tenants = Tenant.query.filter_by(is_active=True).all()
                print(f"📊 [Scheduler] Toplam {len(tenants)} aktif firma taraniyor...")

                for tenant in tenants:
                    # Firmanın yedekleme ayarını kontrol et
                    config = BackupConfig.query.filter_by(tenant_id=tenant.id).first()
                    
                    # Engine nesnesini her durumda en başta oluşturuyoruz
                    # Böylece temizlik aşamasında 'engine' değişkeni boş kalmaz
                    from services.backup_engine import BackupEngine
                    # Eğer bir backup kaydı yoksa sahte bir ID veya None ile başlatabiliriz 
                    # çünkü temizlik için sadece tenant_id yetiyor
                    temp_engine = BackupEngine(None) 
                    
                    should_backup = True
                    if config and config.frequency == 'manual':
                        should_backup = False
                    
                    if should_backup:
                        print(f"   🔄 Yedekleniyor: {tenant.unvan}")
                        backup_id = BackupEngine.create_db_record(tenant.id, 'daily', None)
                        engine = BackupEngine(backup_id)
                        engine.perform_backup()
                    else:
                        print(f"   ⏭️ Atlandı (Manuel Mod): {tenant.unvan}")

                    # Temizlik işlemi (Artık temp_engine üzerinden güvenle çalışır)
                    if config and config.retention_days:
                        print(f"🧹 [Scheduler] {tenant.unvan} için eski yedekler taranıyor...")
                        temp_engine.clean_old_backups(tenant.id, config.retention_days)
                        
            except Exception as e:
                print(f"❌ [Scheduler] KRİTİK HATA: {e}")
                # KRİTİK SİSTEM HATASI BİLDİRİMİ
                from services.notification_service import NotificationService
                NotificationService.send_backup_report(
                    "nail19@gmail.com", 
                    "SİSTEM GENELİ", 
                    "CRITICAL ERROR", 
                    f"Zamanlayıcı durdu: {str(e)}"
                )
                import traceback
                traceback.print_exc()

    @staticmethod
    def _safe_import_models():
        """Path ayarlarını yapıp modelleri döndüren yardımcı fonksiyon"""
        import sys
        
        # Path Ayarı
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        app_dir = os.path.join(project_root, 'app')
        app_models_dir = os.path.join(app_dir, 'models')

        if app_dir not in sys.path: sys.path.insert(0, app_dir)
        if app_models_dir not in sys.path: sys.path.insert(0, app_models_dir)

        try:
            import master
            from services.backup_engine import BackupEngine
            
            # Temizlik
            if app_models_dir in sys.path: sys.path.remove(app_models_dir)
            
            return {
                'Tenant': master.Tenant,
                'BackupConfig': master.BackupConfig,
                'User': master.User,
                'BackupEngine': BackupEngine
            }
        except ImportError as e:
            print(f"❌ [Scheduler] Import Hatası: {e}")
            return None

    @staticmethod
    def _get_setting_model():
        """Sadece Setting modelini getiren yardımcı"""
        try:
            from models.setting import Setting
            return Setting
        except ImportError:
            # Yedek plan (Path ekle)
            current_file = os.path.abspath(__file__)
            supervisor_dir = os.path.dirname(os.path.dirname(current_file))
            if supervisor_dir not in sys.path: sys.path.insert(0, supervisor_dir)
            try:
                from models.setting import Setting
                return Setting
            except:
                return None