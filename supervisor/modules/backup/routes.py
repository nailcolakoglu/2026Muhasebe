# supervisor/modules/backup/routes.py

import os
import sys
import threading
import uuid
import time
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_file, jsonify
from flask_login import login_required, current_user

# ========================================
# 1. GLOBAL PATH VE IMPORT AYARLARI
# ========================================
current_file = os.path.abspath(__file__)
# supervisor/modules/backup/routes.py -> supervisor
supervisor_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
# supervisor -> app (Proje Ana Dizini)
project_root = os.path.dirname(supervisor_root)
app_dir = os.path.join(project_root, 'app')
app_models_dir = os.path.join(app_dir, 'models')

# Supervisor kök dizinini ve App dizinini ekle
if supervisor_root not in sys.path: sys.path.insert(0, supervisor_root)
if app_dir not in sys.path: sys.path.insert(0, app_dir)

# ✅ KRİTİK DÜZELTME: Doğru DB nesnesini çağır
try:
    from app.extensions import db
except ImportError:
    # Fallback
    sys.path.append(project_root)
    from app.extensions import db

# Blueprint Tanımı
backup_bp = Blueprint('backup', __name__, template_folder='../../templates')

# ========================================
# 2. MODEL YÜKLEME (GÜVENLİ)
# ========================================
def get_models():
    """
    Modelleri güvenli bir şekilde getirir.
    Hem Supervisor hem de App modellerini çakışmadan yükler.
    """
    # 1. ÖNCE SUPERVISOR MODELLERİ (Setting, Backup)
    try:
        from models.setting import Setting
        from models.backup import Backup
    except ImportError:
        if supervisor_root not in sys.path: sys.path.insert(0, supervisor_root)
        from models.setting import Setting
        from models.backup import Backup

    # 2. SONRA APP MODELLERİ (Tenant, BackupConfig)
    if app_models_dir not in sys.path:
        sys.path.insert(0, app_models_dir)
    
    try:
        # Doğrudan app.models.master'dan çekmeyi dene
        from app.models.master import Tenant, BackupConfig
    except ImportError:
        # Fallback: doğrudan dosya importu
        try:
            import master
            Tenant = master.Tenant
            BackupConfig = master.BackupConfig
        except ImportError:
            # Dummy sınıflar (Hata vermemesi için)
            class Tenant: pass
            class BackupConfig: pass

    return Tenant, BackupConfig, Backup, Setting

# Form Import
try:
    from .forms import BackupSettingsForm
except ImportError:
    class BackupSettingsForm: pass

from services.backup_engine import BackupEngine
from supervisor_config import SupervisorConfig

# ========================================
# 3. ROTALAR (FULL LİSTE)
# ========================================

@backup_bp.route('/')
@login_required
def index():
    """Yedekleme Listesi"""
    Tenant, _, Backup, _ = get_models()
    
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = getattr(SupervisorConfig, 'ITEMS_PER_PAGE', 20)
    
    # Sıralama
    if hasattr(Backup, 'created_at'):
        query = Backup.query.order_by(Backup.created_at.desc())
    else:
        query = Backup.query
    
    if status != 'all':
        query = query.filter_by(status=status)
        
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    backups_data = []
    for b in pagination.items:
        tenant = db.session.get(Tenant, b.tenant_id)
        backups_data.append({'backup': b, 'tenant': tenant})
        
    return render_template('backup/index.html', 
                           backups=backups_data,
                           pagination=pagination,
                           status=status)

@backup_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Yeni Yedekleme Oluştur"""
    Tenant, _, Backup, _ = get_models()
    
    # Aktif firmaları listele
    tenants = Tenant.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id')
        
        if not tenant_id:
            flash('Lütfen bir firma seçin.', 'warning')
            return redirect(url_for('backup.create'))
            
        try:
            # 1. Bekleyen (Pending) Kayıt Oluştur
            backup_id = BackupEngine.create_db_record(
                tenant_id=tenant_id,
                backup_type='manual',
                created_by=current_user.id
            )
            
            # Kayıt nesnesini çek
            backup = db.session.get(Backup, backup_id)

            # ----------------------------------------------------
            # ARKA PLAN İŞÇİSİ (THREAD)
            # ----------------------------------------------------
            def run_backup(app_obj, backup_id):
                with app_obj.app_context():
                    try:
                        print(f"\n🧵 [Thread] Yedekleme başlatılıyor... ID: {backup_id}")
                        # Servisi import et
                        from services.backup_engine import BackupEngine
                        engine = BackupEngine(backup_id)
                        result = engine.perform_backup()
                        print(f"🧵 [Thread] Sonuç: {result}")
                    except Exception as e:
                        print(f"❌ [Thread] HATA: {e}")
                        # Hatayı DB'ye yaz
                        try:
                            from app.extensions import db
                            # Modeli tekrar yükle
                            if supervisor_root not in sys.path: sys.path.insert(0, supervisor_root)
                            from models.backup import Backup
                            
                            # Yeni session
                            db.session.remove()
                            bkp = db.session.get(Backup, backup_id)
                            if bkp:
                                bkp.status = 'failed'
                                bkp.message = f"Sistem Hatası: {str(e)}"
                                db.session.commit()
                        except: pass

            # Thread'i Başlat
            threading.Thread(target=run_backup, args=(current_app._get_current_object(), backup.id)).start()
            
            flash('Yedekleme işlemi arka planda başlatıldı.', 'info')
            return redirect(url_for('backup.index'))
            
        except Exception as e:
            flash(f'Hata oluştu: {str(e)}', 'danger')
            
    return render_template('backup/create.html', tenants=tenants)


@backup_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    """Otomatik Yedekleme Zamanlayıcı Ayarları"""
    _, _, _, Setting = get_models()
    
    if request.method == 'POST':
        try:
            # HTML (schedule.html) içindeki 'name' değerleri
            is_enabled_form = request.form.get('is_enabled') == 'on'
            daily_time_form = request.form.get('daily_time')
            
            # Veritabanına kaydet
            Setting.set('backup_enabled', 'true' if is_enabled_form else 'false')
            if daily_time_form:
                Setting.set('backup_daily_time', daily_time_form)
            
            db.session.commit()
            
            # Zamanlayıcıyı güncelle
            from services.scheduler_service import SchedulerService
            SchedulerService.reload_jobs()
            
            print(f"🔄 [Scheduler] Ayarlar güncellendi: {'AÇIK' if is_enabled_form else 'KAPALI'} - {daily_time_form}")
            
            flash('Zamanlama ayarları başarıyla güncellendi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {e}', 'danger')
            
        return redirect(url_for('backup.schedule'))

    # Mevcut ayarları çek
    settings_data = {
        'is_enabled': Setting.get('backup_enabled') == 'true',
        'daily_time': Setting.get('backup_daily_time', '03:00')
    }
    
    return render_template('backup/schedule.html', 
                           settings=settings_data, 
                           now=datetime.now().strftime('%H:%M'))    
                           
@backup_bp.route('/<backup_id>')
@login_required
def detail(backup_id):
    """Yedek Detayı"""
    Tenant, _, Backup, _ = get_models()
    backup = Backup.query.get_or_404(backup_id)
    tenant = db.session.get(Tenant, backup.tenant_id)
    return render_template('backup/detail.html', backup=backup, tenant=tenant)

@backup_bp.route('/<backup_id>/delete', methods=['POST'])
@login_required
def delete(backup_id):
    """Yedeği Sil"""
    _, _, Backup, _ = get_models()
    backup = Backup.query.get_or_404(backup_id)
    
    # Kilit Kontrolü
    if getattr(backup, 'is_immutable', False):
        flash('❌ Bu yedek "Kilitli" olduğu için silinemez!', 'warning')
        return redirect(url_for('backup.detail', backup_id=backup_id))
    
    try:
        # Dosyayı sil
        if backup.file_path and os.path.exists(backup.file_path):
            try:
                os.remove(backup.file_path)
            except OSError as os_err:
                print(f"⚠️ Dosya silinemedi: {os_err}")
        
        db.session.delete(backup)
        db.session.commit()
        flash('Yedek silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {e}', 'danger')
        
    return redirect(url_for('backup.index'))

@backup_bp.route('/<backup_id>/download')
@login_required
def download(backup_id):
    """Yedeği İndir"""
    _, _, Backup, _ = get_models()
    backup = Backup.query.get_or_404(backup_id)
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        flash('Dosya bulunamadı.', 'danger')
        return redirect(url_for('backup.detail', backup_id=backup_id))
        
    return send_file(backup.file_path, as_attachment=True, download_name=backup.file_name)

@backup_bp.route('/<backup_id>/toggle-lock', methods=['POST'])
@login_required
def toggle_lock(backup_id):
    """Kilitle / Aç"""
    _, _, Backup, _ = get_models()
    backup = Backup.query.get_or_404(backup_id)
    
    if not hasattr(backup, 'is_immutable'):
        flash('Bu özellik veritabanında aktif değil.', 'warning')
        return redirect(url_for('backup.detail', backup_id=backup_id))

    backup.is_immutable = not backup.is_immutable
    db.session.commit()
    
    msg = 'Kilitlendi' if backup.is_immutable else 'Kilit Açıldı'
    flash(f'{msg}', 'success' if backup.is_immutable else 'warning')
    return redirect(url_for('backup.detail', backup_id=backup_id))

@backup_bp.route('/<backup_id>/restore-sandbox', methods=['POST'])
@login_required
def restore_sandbox(backup_id):
    """Sandbox Testi"""
    try:
        from services.backup_engine import BackupEngine
        engine = BackupEngine(backup_id)
        result = engine.restore_to_sandbox()
        
        if result['success']:
            flash(f"✅ Sandbox Hazır: {result['tenant_code']}", 'success')
        else:
            flash(f"❌ Hata: {result['message']}", 'danger')
    except Exception as e:
        flash(f"Hata: {e}", 'danger')
        
    return redirect(url_for('backup.detail', backup_id=backup_id))

@backup_bp.route('/settings/<tenant_id>', methods=['GET', 'POST'])
@login_required
def settings(tenant_id):
    """Firma Bazlı Ayarlar"""
    Tenant, BackupConfig, _, _ = get_models()
    tenant = Tenant.query.get_or_404(tenant_id)
    
    config = BackupConfig.query.filter_by(tenant_id=tenant.id).first()
    # Config yoksa boş form
    form = BackupSettingsForm(obj=config)
    
    if request.method == 'POST' and form.validate_on_submit():
        if not config:
            config = BackupConfig(tenant_id=tenant.id)
            db.session.add(config)
            
        form.populate_obj(config)
        
        # Local seçildiyse diğer alanları temizle
        if config.provider == 'local':
            config.aws_secret_key = None
            config.ftp_password = None
            
        try:
            db.session.commit()
            flash(f'Ayarlar güncellendi: {tenant.unvan}', 'success')
            return redirect(url_for('tenants.index')) # veya backup.index
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {e}', 'danger')
            
    return render_template('backup/settings.html', form=form, tenant=tenant)
    
@backup_bp.route('/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    """Seçili Yedekleri Toplu Sil"""
    _, _, Backup, _ = get_models()
    
    # 1. Veriyi her iki formattan da yakalamaya çalış
    backup_ids = []
    if request.is_json:
        data = request.get_json()
        backup_ids = data.get('backup_ids', []) or data.get('ids', [])
    else:
        backup_ids = request.form.getlist('ids') or request.form.getlist('backup_ids')

    if not backup_ids:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Seçili yedek yok'}), 400
        flash('Lütfen silinecek yedekleri seçin.', 'warning')
        return redirect(url_for('backup.index'))
    
    deleted_count = 0
    skipped_count = 0
    
    for b_id in backup_ids:
        backup = db.session.get(Backup, b_id)
        if backup:
            # Kilit kontrolü
            if getattr(backup, 'is_immutable', False):
                skipped_count += 1
                continue
                
            try:
                # Fiziksel dosyayı sil
                if backup.file_path and os.path.exists(backup.file_path):
                    os.remove(backup.file_path)
                
                db.session.delete(backup)
                deleted_count += 1
            except Exception as e:
                print(f"❌ Silme hatası ({b_id}): {e}")
                skipped_count += 1
                
    try:
        db.session.commit()
        msg = f"{deleted_count} yedek silindi."
        if skipped_count > 0:
            msg += f" {skipped_count} yedek kilitli olduğu için atlandı."
        
        if request.is_json:
            return jsonify({'success': True, 'message': msg})
        
        flash(msg, 'success' if deleted_count > 0 else 'warning')
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Hata: {e}', 'danger')
        
    return redirect(url_for('backup.index'))