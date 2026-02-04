# supervisor/modules/licenses/routes.py

"""
Supervisor Licenses (Lisans Yönetimi) Routes
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import sys
import os
import uuid

# ========================================
# PATH VE IMPORT AYARLARI (GÜVENLİ)
# ========================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SUPERVISOR_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
PROJECT_DIR = os.path.abspath(os.path.join(SUPERVISOR_DIR, '..'))
APP_DIR = os.path.join(PROJECT_DIR, 'app')

# Ana uygulama dizinini yola ekle ki 'app.extensions' görülebilsin
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# 🚨 DÜZELTME: 'extensions' yerine 'app.extensions' kullanılmalı.
# Modeller (License, Tenant) ana uygulamadaki db nesnesine bağlıdır.
# Buradaki db ile modellerin db'si aynı olmazsa "Not registered" hatası alınır.
try:
    from app.extensions import db
except ImportError:
    # Fallback (Eğer sys.path çalışmazsa)
    from extensions import db

from supervisor_config import SupervisorConfig
# Audit ve Extended modellerinin de doğru db'yi kullandığından emin olunmalı
# Eğer bunlar yerel extensions kullanıyorsa, kodun geri kalanında çakışma olabilir.
# Ancak genelde Master DB tek bir instance üzerinden yönetilir.
from models.audit import AuditLog as SupervisorAuditLog
from models.license_extended import LicenseExtended

# Forms ve Servis
from .forms import LicenseForm
from services.license_service import LicenseService

# Master Modeller (Güvenli Import)
try:
    from models.master import Tenant, License
except ImportError:
    models_path = os.path.join(APP_DIR, 'models')
    if models_path not in sys.path:
        sys.path.insert(0, models_path)
    try:
        from master import Tenant, License
    except ImportError as e:
        print(f"❌ Modeller yüklenemedi: {e}")
        # Kodun çökmemesi için dummy sınıflar (Sadece debug için)
        class Tenant: pass
        class License: pass

licenses_bp = Blueprint('licenses', __name__)


# ========================================
# LİSTELEME
# ========================================

@licenses_bp.route('/')
@login_required
def index():
    """Lisans listesi"""
    
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    license_type = request.args.get('type', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = License.query.order_by(License.created_at.desc())
    
    # Filtreler
    if status == 'active':
        query = query.filter(License.is_active == True, License.valid_until >= datetime.utcnow())
    elif status == 'expired':
        query = query.filter(License.valid_until < datetime.utcnow())
    elif status == 'expiring':
        query = query.filter(
            License.is_active == True,
            License.valid_until >= datetime.utcnow(),
            License.valid_until <= datetime.utcnow() + timedelta(days=30)
        )
    
    if license_type != 'all':
        query = query.filter_by(license_type=license_type)
        
    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Veri Hazırlama
    licenses_data = []
    for lic in pagination.items:
        try:
            tenant = Tenant.query.get(lic.tenant_id)
            extended = LicenseExtended.query.get(lic.id)
            
            # UTC naive/aware kontrolü yaparak hesapla
            now = datetime.utcnow()
            # valid_until None kontrolü
            if lic.valid_until:
                remaining = (lic.valid_until - now).days
            else:
                remaining = 0
            
            licenses_data.append({
                'license': lic,
                'tenant': tenant,
                'extended': extended,
                'remaining_days': remaining
            })
        except Exception as e:
            print(f"Hata (Lisans ID: {lic.id}): {e}")
            continue
            
    # Config'den tipleri al
    available_types = []
    if hasattr(SupervisorConfig, 'LICENSE_TYPES'):
        available_types = list(SupervisorConfig.LICENSE_TYPES.keys())
        
    return render_template('licenses/index.html',
        licenses=licenses_data,
        pagination=pagination,
        status=status,
        license_type=license_type,
        search=search,
        available_types=available_types
    )


# ========================================
# YENİ LİSANS (NEW)
# ========================================

@licenses_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Yeni lisans oluştur"""
    form = LicenseForm()
    
    # Firmaları doldur
    tenants = Tenant.query.filter_by(is_active=True).order_by(Tenant.unvan).all()
    form.tenant_id.choices = [('', 'Firma Seçin...')] + [(t.id, f"{t.unvan} ({t.kod})") for t in tenants]
    
    if form.validate_on_submit():
        data = {
            'tenant_id': form.tenant_id.data,
            'license_type': form.license_type.data,
            'duration_days': form.duration_days.data,
            'max_users': form.max_users.data,
            'monthly_fee': form.monthly_fee.data,
            'billing_cycle': form.billing_cycle.data,
            'notes': form.notes.data
        }
        
        result = LicenseService.create_license(data, current_user)
        
        if result['success']:
            flash(result['message'], 'success')
            return redirect(url_for('licenses.detail', license_id=result['license_id']))
        else:
            flash(f"Hata: {result['message']}", 'danger')
            
    return render_template('licenses/form.html', form=form, tenants=tenants, title="Yeni Lisans")


# ========================================
# DETAY (DETAIL)
# ========================================

@licenses_bp.route('/<license_id>')
@login_required
def detail(license_id):
    """Lisans detayı"""
    lic = License.query.get_or_404(license_id)
    tenant = Tenant.query.get(lic.tenant_id)
    extended = LicenseExtended.query.get(license_id)
    
    # Kalan gün
    remaining = 0
    if lic.valid_until:
        remaining = (lic.valid_until - datetime.utcnow()).days
    
    # Geçmiş
    history = License.query.filter_by(tenant_id=lic.tenant_id).order_by(License.created_at.desc()).all()
    
    # Aktiviteler
    activities = SupervisorAuditLog.query.filter_by(
        resource_type='license', 
        resource_id=license_id
    ).order_by(SupervisorAuditLog.created_at.desc()).limit(10).all()
    
    return render_template('licenses/detail.html', 
                           license=lic, 
                           tenant=tenant, 
                           extended=extended, 
                           remaining_days=remaining,
                           license_history=history,
                           recent_activities=activities)


# ========================================
# DÜZENLE (EDIT)
# ========================================

@licenses_bp.route('/<license_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(license_id):
    """Lisans düzenle"""
    # 1. Lisans ve Tenant'ı bul (Bunlar 'models.master'dan, yani 'app.extensions.db'ye bağlı)
    license_obj = License.query.get_or_404(license_id)
    tenant = Tenant.query.get(license_obj.tenant_id)
    
    # 2. Extended bilgiyi bul
    extended = LicenseExtended.query.get(license_id)
    
    # Formu doldur
    form = LicenseForm(obj=license_obj)
    
    # Edit modunda tenant değiştirilemez
    form.tenant_id.choices = [(tenant.id, tenant.unvan)]
    
    if request.method == 'GET':
        form.tenant_id.data = tenant.id
        form.license_type.data = license_obj.license_type
        # Extended verileri forma yükle
        if extended:
            form.monthly_fee.data = extended.monthly_fee
            form.billing_cycle.data = extended.billing_cycle
            form.notes.data = extended.notes
            
    if form.validate_on_submit():
        try:
            # 3. Güncelleme İşlemi
            # License ve Tenant -> app.extensions.db
            # LicenseExtended -> (Eğer farklı db ise sorun çıkarır, ama burada aynı kabul ediyoruz)
            
            # Sadece izin verilen alanları güncelle
            license_obj.max_users = form.max_users.data
            # Diğer master alanları gerekirse buraya ekle (örn: max_branches)
            
            # Extended güncelle veya oluştur
            if not extended:
                extended = LicenseExtended(id=license_obj.id)
                db.session.add(extended)
                
            extended.monthly_fee = form.monthly_fee.data
            extended.billing_cycle = form.billing_cycle.data
            extended.notes = form.notes.data
            
            # Süre uzatma
            extend_days = request.form.get('extend_days')
            if extend_days and extend_days.strip():
                try:
                    days_to_add = int(extend_days)
                    if days_to_add > 0:
                        license_obj.valid_until += timedelta(days=days_to_add)
                except ValueError:
                    pass # Sayı değilse görmezden gel
                
            # 4. Commit (Artık doğru 'db' nesnesi kullanılıyor)
            db.session.commit()
            
            # Loglama
            try:
                SupervisorAuditLog.log(
                    action='license.update',
                    supervisor=current_user,
                    resource_type='license',
                    resource_id=license_obj.id,
                    description=f'Lisans güncellendi: {tenant.unvan}',
                    status='success'
                )
            except Exception as log_err:
                print(f"Log Hatası: {log_err}")
            
            flash('Lisans bilgileri güncellendi.', 'success')
            return redirect(url_for('licenses.detail', license_id=license_obj.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Edit Hatası: {e}") # Konsola bas ki görelim
            flash(f'Hata oluştu: {str(e)}', 'danger')
            
    return render_template('licenses/form.html', form=form, license=license_obj, title="Lisans Düzenle")


# ========================================
# YENİLE (RENEW)
# ========================================

@licenses_bp.route('/<license_id>/renew', methods=['POST'])
@login_required
def renew(license_id):
    """Lisans süresi uzat"""
    try:
        days = int(request.form.get('days', 365))
        result = LicenseService.renew_license(license_id, days, current_user)
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'danger')
    except Exception as e:
        flash(f"Hata: {e}", 'danger')
        
    return redirect(url_for('licenses.detail', license_id=license_id))


# ========================================
# DURUM DEĞİŞTİR (TOGGLE)
# ========================================

@licenses_bp.route('/<license_id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(license_id):
    """Aktif/Pasif yap"""
    lic = License.query.get_or_404(license_id)
    try:
        lic.is_active = not lic.is_active
        db.session.commit()
        status_text = "Aktifleştirildi" if lic.is_active else "Pasife alındı"
        flash(f'Lisans {status_text}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {e}', 'danger')
    return redirect(url_for('licenses.detail', license_id=license_id))


# ========================================
# SİL (DELETE)
# ========================================

@licenses_bp.route('/<license_id>/delete', methods=['POST'])
@login_required
def delete(license_id):
    """Lisans sil"""
    if not current_user.is_superadmin: # Role kontrolü yerine property kullanımı daha güvenli
        flash('Yetkisiz işlem.', 'danger')
        return redirect(url_for('licenses.index'))
        
    lic = License.query.get_or_404(license_id)
    try:
        # Önce ilişkili tabloları sil
        LicenseExtended.query.filter_by(id=license_id).delete()
        
        # Sonra lisansı sil
        db.session.delete(lic)
        db.session.commit()
        flash('Lisans silindi.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {e}', 'danger')
        
    return redirect(url_for('licenses.index'))


# ========================================
# API: İSTATİSTİKLER
# ========================================

@licenses_bp.route('/api/stats')
@login_required
def api_stats():
    total = License.query.count()
    active = License.query.filter(License.is_active == True).count()
    return jsonify({'total': total, 'active': active})