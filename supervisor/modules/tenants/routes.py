# supervisor/modules/tenants/routes.py

"""
Supervisor Tenants (Firma Yönetimi) Routes
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import sys
import os
import uuid

# ==========================================
# PATH AYARLARI
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '../../..'))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==========================================
# IMPORTS
# ==========================================
from app.extensions import db

# ✅ DOĞRU IMPORT: Services
try:
    from services.firebird_service import FirebirdService
except ImportError:
    try:
        from supervisor.services.firebird_service import FirebirdService
    except ImportError:
        FirebirdService = None

# ✅ GÜVENLİ IMPORT: Supervisor Modelleri
try:
    from models.tenant_extended import TenantExtended
    from models.supervisor import Supervisor
    from models.audit import AuditLog as SupervisorAuditLog
except ImportError:
    sys.path.append(os.path.join(PROJECT_ROOT, 'supervisor'))
    from models.tenant_extended import TenantExtended
    from models.supervisor import Supervisor
    from models.audit import AuditLog as SupervisorAuditLog

# ✅ GÜVENLİ IMPORT: Ana Modeller
# AccountingPeriod hatasını önlemek için try-except bloğuna aldık
from app.models.master import Tenant, User, License, UserTenantRole

try:
    from app.models.master import AccountingPeriod
except ImportError:
    # Model yoksa None yap, kod patlamasın
    AccountingPeriod = None

# Blueprint
tenants_bp = Blueprint('tenants', __name__)


# ========================================
# HELPER
# ========================================
def get_tenant_user_count(tenant_id):
    try:
        return UserTenantRole.query.filter_by(tenant_id=tenant_id).count()
    except: 
        return 0


# ========================================
# INDEX
# ========================================
@tenants_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    query = Tenant.query
    
    if status == 'active': 
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    if search: 
        query = query.filter(
            db.or_(
                Tenant.unvan.ilike(f'%{search}%'),
                Tenant.kod.ilike(f'%{search}%'),
                Tenant.vergi_no.ilike(f'%{search}%')
            )
        )
    
    query = query.order_by(Tenant.created_at.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    
    tenants_data = []
    for tenant in pagination.items:
        # Extended yoksa oluştur (Hata önleyici)
        extended = TenantExtended.query.get(tenant.id)
        if not extended:
            extended = TenantExtended(id=tenant.id)
            db.session.add(extended)
            db.session.commit()
            
        license = License.query.filter_by(tenant_id=tenant.id, is_active=True).first()
        
        tenants_data.append({
            'tenant': tenant,
            'extended': extended,
            'license': license,
            'user_count': get_tenant_user_count(tenant.id)
        })
    
    try:
        expiring_soon = License.query.filter(
            License.valid_until <= datetime.utcnow() + timedelta(days=30),
            License.valid_until >= datetime.utcnow(),
            License.is_active == True
        ).count()
    except:
        expiring_soon = 0
        
    return render_template('tenants/index.html',
        tenants=tenants_data,
        pagination=pagination,
        status=status,
        search=search,
        expiring_soon=expiring_soon
    )


# ========================================
# DETAY
# ========================================
@tenants_bp.route('/<tenant_id>')
@login_required
def detail(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    
    extended = TenantExtended.query.get(tenant.id)
    if not extended:
        extended = TenantExtended(id=tenant.id)
        db.session.add(extended)
        db.session.commit()
        
    licenses = License.query.filter_by(tenant_id=tenant_id).order_by(License.created_at.desc()).all()
    active_license = License.query.filter_by(tenant_id=tenant_id, is_active=True).first()
    
    users = []
    try:
        roles = UserTenantRole.query.filter_by(tenant_id=tenant_id).all()
        users = [r.user for r in roles if r.user]
    except: pass
    
    periods = []
    # ✅ HATA FİKSİ: Eğer AccountingPeriod modeli yoksa sorgu yapma
    if AccountingPeriod:
        try:
            periods = AccountingPeriod.query.filter_by(tenant_id=tenant_id).order_by(AccountingPeriod.start_date.desc()).all()
        except: pass
    
    activities = SupervisorAuditLog.query.filter_by(resource_type='tenant', resource_id=tenant_id)\
        .order_by(SupervisorAuditLog.created_at.desc()).limit(10).all()
        
    return render_template('tenants/detail.html',
        tenant=tenant, extended=extended, licenses=licenses,
        active_license=active_license, users=users, periods=periods,
        recent_activities=activities
    )


# ========================================
# YENİ / DÜZENLE / SİL / İŞLEMLER
# ========================================
@tenants_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        try:
            kod = request.form.get('kod', '').strip().upper()
            unvan = request.form.get('unvan', '').strip()
            db_name = request.form.get('db_name', '').strip()
            
            if Tenant.query.filter_by(kod=kod).first():
                flash('Bu firma kodu zaten kullanılıyor.', 'danger')
                return render_template('tenants/form.html', tenant=None)
            
            # 1. Firebird DB Oluştur
            if FirebirdService:
                fb = FirebirdService()
                res = fb.create_database(kod, db_name)
                if not res['success']:
                    flash(f"Firebird Hatası: {res['error']}", 'danger')
                    return render_template('tenants/form.html', tenant=None)
            
            # 2. Kayıt
            tenant = Tenant(
                id=str(uuid.uuid4()),
                kod=kod, unvan=unvan, db_name=db_name,
                vergi_no=request.form.get('vergi_no'),
                vergi_dairesi=request.form.get('vergi_dairesi'),
                is_active=True
            )
            tenant.set_db_password(request.form.get('db_password', 'masterkey'))
            db.session.add(tenant)
            
            extended = TenantExtended(id=tenant.id)
            db.session.add(extended)
            
            SupervisorAuditLog.log('tenant.create', current_user, 'tenant', tenant.id, f'Firma oluşturuldu: {unvan}')
            db.session.commit()
            
            flash('Firma başarıyla oluşturuldu.', 'success')
            return redirect(url_for('tenants.detail', tenant_id=tenant.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
            
    return render_template('tenants/form.html', tenant=None)

@tenants_bp.route('/<tenant_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    if request.method == 'POST':
        tenant.unvan = request.form.get('unvan')
        tenant.vergi_no = request.form.get('vergi_no')
        tenant.vergi_dairesi = request.form.get('vergi_dairesi')
        
        SupervisorAuditLog.log('tenant.update', current_user, 'tenant', tenant.id, f'Firma güncellendi: {tenant.unvan}')
        db.session.commit()
        flash('Güncellendi.', 'success')
        return redirect(url_for('tenants.detail', tenant_id=tenant.id))
        
    return render_template('tenants/form.html', tenant=tenant)

@tenants_bp.route('/<tenant_id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    tenant.is_active = not tenant.is_active
    db.session.commit()
    flash('Durum değiştirildi.', 'success')
    return redirect(url_for('tenants.detail', tenant_id=tenant.id))

@tenants_bp.route('/<tenant_id>/delete', methods=['POST'])
@login_required
def delete(tenant_id):
    if current_user.role != 'super_admin':
        flash('Yetkisiz işlem.', 'danger')
        return redirect(url_for('tenants.index'))
        
    tenant = Tenant.query.get_or_404(tenant_id)
    
    if request.form.get('confirmation') != tenant.kod:
        flash('Onay kodu hatalı.', 'danger')
        return redirect(url_for('tenants.detail', tenant_id=tenant.id))
        
    try:
        # İlişkili verileri temizle
        TenantExtended.query.filter_by(id=tenant.id).delete()
        License.query.filter_by(tenant_id=tenant.id).delete()
        UserTenantRole.query.filter_by(tenant_id=tenant.id).delete()
        
        db.session.delete(tenant)
        db.session.commit()
        flash('Firma silindi.', 'success')
        return redirect(url_for('tenants.index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Silme hatası: {str(e)}', 'danger')
        return redirect(url_for('tenants.detail', tenant_id=tenant.id))

@tenants_bp.route('/<tenant_id>/update-stats', methods=['POST'])
@login_required
def update_stats(tenant_id):
    extended = TenantExtended.query.get(tenant_id) or TenantExtended(id=tenant_id)
    db.session.add(extended)
    extended.total_users = get_tenant_user_count(tenant_id)
    extended.last_stats_update = datetime.utcnow()
    db.session.commit()
    flash('İstatistikler güncellendi.', 'success')
    return redirect(url_for('tenants.detail', tenant_id=tenant_id))

@tenants_bp.route('/api/list')
@login_required
def api_list():
    """JSON firma listesi"""
    
    draw = request.args.get('draw', type=int, default=1)
    start = request.args.get('start', type=int, default=0)
    length = request.args.get('length', type=int, default=10)
    search_value = request.args.get('search[value]', default='')
    
    query = Tenant.query
    
    if search_value:
        query = query.filter(
            db.or_(
                Tenant.unvan.ilike(f'%{search_value}%'),
                Tenant.kod.ilike(f'%{search_value}%'),
                Tenant.vergi_no.ilike(f'%{search_value}%')
            )
        )
    
    total_records = Tenant.query.count()
    filtered_records = query.count()
    
    query = query.order_by(Tenant.created_at.desc())
    query = query.offset(start).limit(length)
    
    tenants = query.all()
    
    data = []
    for tenant in tenants:
        license = License.query.filter_by(tenant_id=tenant.id, is_active=True).first()
        
        # ✅ Kullanıcı sayısı düzeltildi
        user_count = get_tenant_user_count(tenant.id)
        
        data.append({
            'id': tenant.id,
            'kod': tenant.kod,
            'unvan': tenant.unvan,
            'vergi_no':  tenant.vergi_no or '-',
            'db_name': tenant.db_name,
            'is_active':  tenant.is_active,
            'user_count': user_count,
            'license_type': license.license_type if license else None,
            'license_valid_until': license.valid_until.strftime('%d.%m.%Y') if license else None,
            'created_at': tenant.created_at.strftime('%d.%m.%Y %H:%M')
        })
    
    return jsonify({
        'draw':  draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })