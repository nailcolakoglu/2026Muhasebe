# supervisor/modules/users/routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import sys
import os
import uuid

# Path Ayarları
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')) 
if BASE_DIR not in sys.path: sys.path.insert(0, BASE_DIR)

from app.extensions import db
from app.models.master import Tenant, User, UserTenantRole

try:
    from models.audit import AuditLog
except ImportError:
    sys.path.append(os.path.join(BASE_DIR, 'supervisor'))
    from models.audit import AuditLog

from .forms import UserForm

users_bp = Blueprint('users', __name__)

@users_bp.route('/')
@login_required
def index():
    """Kullanıcı listesi ve Rolleri"""
    # N+1 sorununu önlemek için joinli sorgu yapmak daha performanslıdır ama 
    # şimdilik SQLAlchemy lazy loading ile idare edelim.
    users = User.query.order_by(User.created_at.desc()).limit(100).all()
    return render_template('users/index.html', users=users)

@users_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Yeni Kullanıcı Ekleme"""
    form = UserForm()
    
    tenants = Tenant.query.filter_by(is_active=True).all()
    form.tenant_id.choices = [('', 'Seçiniz...')] + [(t.id, t.unvan) for t in tenants]

    if form.validate_on_submit():
        email = form.email.data.lower()
        target_tenant_id = form.tenant_id.data
        selected_role = form.role.data
        
        try:
            existing_user = User.query.filter_by(email=email).first()
            user = None
            is_new_user = False

            if existing_user:
                user = existing_user
                if target_tenant_id:
                    existing_role = UserTenantRole.query.filter_by(user_id=user.id, tenant_id=target_tenant_id).first()
                    if existing_role:
                        flash(f'Bu kullanıcının seçilen firmada zaten "{existing_role.role}" yetkisi var.', 'warning')
                        return render_template('users/form.html', form=form, title="Yeni Kullanıcı")
                flash(f'Mevcut kullanıcı bulundu ({user.full_name}). Yeni firma yetkisi ekleniyor...', 'info')
            else:
                if not form.password.data:
                    flash('Yeni kullanıcı için şifre belirlemelisiniz.', 'danger')
                    return render_template('users/form.html', form=form, title="Yeni Kullanıcı")

                user = User(id=str(uuid.uuid4()), email=email, full_name=form.full_name.data, is_active=form.is_active.data)
                user.set_password(form.password.data)
                db.session.add(user)
                is_new_user = True
            
            if target_tenant_id:
                role = UserTenantRole(
                    id=str(uuid.uuid4()), user_id=user.id, tenant_id=target_tenant_id, 
                    role=selected_role, is_default=is_new_user
                )
                db.session.add(role)

            action_type = 'user.create' if is_new_user else 'user.assign_role'
            AuditLog.log(action=action_type, supervisor=current_user, resource_type='user', resource_id=user.id, description=f'Kullanıcı işlem: {email}', status='success')
            
            db.session.commit()
            flash('İşlem başarıyla tamamlandı.', 'success')
            return redirect(url_for('users.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Hata oluştu: {str(e)}', 'danger')

    return render_template('users/form.html', form=form, title="Yeni Kullanıcı")

@users_bp.route('/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit(user_id):
    """Kullanıcı Düzenleme ve Rol Yönetimi"""
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    
    tenants = Tenant.query.filter_by(is_active=True).all()
    form.tenant_id.choices = [('', 'Seçiniz...')] + [(t.id, t.unvan) for t in tenants]
    
    # Mevcut rolleri çek (Template'de listelemek için)
    current_roles = UserTenantRole.query.filter_by(user_id=user.id).all()

    if form.validate_on_submit():
        try:
            user.email = form.email.data.lower()
            user.full_name = form.full_name.data
            user.is_active = form.is_active.data
            
            if form.password.data:
                user.set_password(form.password.data)
                AuditLog.log(action='user.password_reset', supervisor=current_user, resource_id=user.id, description=f'Şifre değiştirildi: {user.email}')

            # Eğer formdan firma seçildiyse O firmadaki yetkiyi ekle/güncelle
            if form.tenant_id.data:
                target_tenant_id = form.tenant_id.data
                existing_role_in_tenant = UserTenantRole.query.filter_by(user_id=user.id, tenant_id=target_tenant_id).first()
                
                if existing_role_in_tenant:
                    existing_role_in_tenant.role = form.role.data
                    flash(f'Firma yetkisi güncellendi: {form.role.data}', 'info')
                else:
                    new_role = UserTenantRole(id=str(uuid.uuid4()), user_id=user.id, tenant_id=target_tenant_id, role=form.role.data)
                    db.session.add(new_role)
                    flash(f'Yeni firma yetkisi eklendi: {form.role.data}', 'success')

            AuditLog.log(action='user.update', supervisor=current_user, resource_type='user', resource_id=user.id, description=f'Kullanıcı güncellendi: {user.email}')
            
            db.session.commit()
            return redirect(url_for('users.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Güncelleme hatası: {str(e)}', 'danger')

    return render_template('users/form.html', form=form, title="Kullanıcı Düzenle", current_roles=current_roles)

# ✅ YENİ EKLENEN ROTA: TEKİL YETKİ SİLME
@users_bp.route('/revoke_role/<role_id>')
@login_required
def revoke_role(role_id):
    """Sadece belirli bir firmadaki yetkiyi siler"""
    role = UserTenantRole.query.get_or_404(role_id)
    user_id = role.user_id
    tenant_name = role.tenant.unvan if role.tenant else "Bilinmeyen Firma"
    
    try:
        db.session.delete(role)
        AuditLog.log(action='user.revoke_role', supervisor=current_user, resource_id=user_id, description=f'Yetki alındı: {tenant_name}', status='warning')
        db.session.commit()
        flash(f'{tenant_name} firmasındaki yetki kaldırıldı.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
        
    return redirect(url_for('users.edit', user_id=user_id))

@users_bp.route('/delete/<user_id>')
@login_required
def delete(user_id):
    """Kullanıcıyı komple sil"""
    user = User.query.get_or_404(user_id)
    email = user.email
    try:
        UserTenantRole.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        AuditLog.log(action='user.delete', supervisor=current_user, resource_id=user_id, description=f'Kullanıcı silindi: {email}', status='warning')
        db.session.commit()
        flash('Kullanıcı ve tüm yetkileri silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Silme hatası: {str(e)}', 'danger')
    return redirect(url_for('users.index'))