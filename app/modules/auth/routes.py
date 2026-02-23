# app/modules/auth/routes.py
"""
Authentication Routes - Güvenli Multi-Tenant Login (Remember YOK)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import logging
import uuid
from datetime import datetime, timezone

from app.extensions import db
from app.models.master import User, Tenant, UserTenantRole, License
from app.utils.tenant_security import has_tenant_access, get_user_tenants
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


# ========================================
# 1. LOGIN - EMAIL + PASSWORD
# ========================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Kullanıcı girişi (Email + Şifre)
    """
    
    # ✅ DÜZELTİLDİ: Authenticated ama tenant yok durumu
    if current_user.is_authenticated:
        tenant_id = session.get('tenant_id')
        
        # Tenant seçili mi?
        if tenant_id:
            # Tenant var → Ana sayfaya
            return redirect(url_for('main.index'))
        else:
            # Tenant yok → Logout yap ve tekrar login ekranına
            logger.warning(f"⚠️ Authenticated ama tenant yok: user={current_user.id}")
            logout_user()
            session.clear()
            flash('⚠️ Oturum bilgileri eksik. Lütfen tekrar giriş yapın.', 'warning')
            # Login sayfasını göster (redirect etme!)
    
    # Form oluştur
    from .forms import create_login_form
    form = create_login_form()
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        # ✅ Form Builder validation kullan (manuel validation kaldırıldı)
        if not email or not password:
            flash('❌ Email ve şifre gereklidir.', 'danger')
            return render_template('auth/login.html', form=form)
        
        # Kullanıcı kontrolü
        user = User.query.filter_by(email=email).first()
        
        if not user:
            logger.warning(f"⚠️ Başarısız login: {email} (kullanıcı yok)")
            flash('❌ Hatalı e-posta veya şifre.', 'danger')
            return render_template('auth/login.html', form=form)
        
        # Şifre kontrolü
        if not check_password_hash(user.password_hash, password):
            logger.warning(f"⚠️ Başarısız login: {email} (yanlış şifre)")
            flash('❌ Hatalı e-posta veya şifre.', 'danger')
            return render_template('auth/login.html', form=form)
        
        # Kullanıcı aktif mi?
        if not user.is_active:
            logger.warning(f"⚠️ Pasif kullanıcı: {email}")
            flash('❌ Hesabınız devre dışı. Yöneticinizle iletişime geçin.', 'danger')
            return render_template('auth/login.html', form=form)
        
        # ✅ Kullanıcının aktif firmalarını bul
        active_roles = UserTenantRole.query.filter_by(
            user_id=user.id,
            is_active=True
        ).join(Tenant).filter(
            Tenant.is_active == True
        ).all()
        
        if not active_roles:
            logger.warning(f"⚠️ Aktif firma yok: {email}")
            flash('⚠️ Hesabınıza tanımlı aktif bir firma bulunamadı.', 'warning')
            return render_template('auth/login.html', form=form)
        
        # SENARYO 1: Tek firma var → Otomatik giriş
        if len(active_roles) == 1:
            role_entry = active_roles[0]
            logger.info(f"✅ Tek firma ile giriş: {email} → {role_entry.tenant.unvan}")
            return finalize_login(user, role_entry.tenant_id, role_entry.role)
        
        # SENARYO 2: Çok firma var → Seçim ekranı
        else:
            logger.info(f"🔀 Çok firma: {email} ({len(active_roles)} firma)")
            
            # ✅ GÜVENLİK: Geçici token
            temp_token = str(uuid.uuid4())
            session['temp_login_token'] = temp_token
            session['temp_user_id'] = user.id
            session['temp_login_time'] = datetime.now(timezone.utc).isoformat()
            
            return redirect(url_for('auth.select_tenant'))
    
    return render_template('auth/login.html', form=form)
    
# ========================================
# 2. TENANT SELECTION
# ========================================

@auth_bp.route('/select-tenant', methods=['GET', 'POST'])
def select_tenant():
    """Firma seçim ekranı"""
    
    # ✅ DÜZELTİLDİ: Daha detaylı log
    temp_token = session.get('temp_login_token')
    temp_user_id = session.get('temp_user_id')
    
    if not temp_token or not temp_user_id:
        logger.warning(
            f"⚠️ Yetkisiz select-tenant erişimi | "
            f"token={bool(temp_token)}, user_id={bool(temp_user_id)}, "
            f"authenticated={current_user.is_authenticated}"
        )
        
        # ✅ Session tamamen temizle
        session.clear()
        
        # ✅ Eğer authenticated ise logout yap
        if current_user.is_authenticated:
            logout_user()
        
        flash('⚠️ Lütfen tekrar giriş yapın.', 'warning')
        return redirect(url_for('auth.login'))

    
    # ✅ Token timeout (5 dakika)
    temp_login_time_str = session.get('temp_login_time')
    if temp_login_time_str:
        temp_login_time = datetime.fromisoformat(temp_login_time_str)
        elapsed = (datetime.now(timezone.utc) - temp_login_time).total_seconds()
        
        if elapsed > 300:  # 5 dakika
            logger.warning(f"⚠️ Token timeout: user={temp_user_id}")
            session.clear()
            flash('⏱️ Oturum süresi doldu. Lütfen tekrar giriş yapın.', 'warning')
            return redirect(url_for('auth.login'))
    
    # Kullanıcıyı çek
    user = db.session.get(User, temp_user_id)
    
    if not user:
        logger.error(f"❌ Kullanıcı bulunamadı: {temp_user_id}")
        session.clear()
        return redirect(url_for('auth.login'))
    
    # Aktif firmalarını çek
    active_roles = UserTenantRole.query.filter_by(
        user_id=user.id,
        is_active=True
    ).join(Tenant).filter(
        Tenant.is_active == True
    ).all()
    
    if not active_roles:
        logger.warning(f"⚠️ Aktif firma yok: user={user.id}")
        session.clear()
        flash('⚠️ Aktif firma bulunamadı.', 'warning')
        return redirect(url_for('auth.login'))
    
    # POST: Firma seçimi
    if request.method == 'POST':
        selected_tenant_id = request.form.get('tenant_id')
        
        if not selected_tenant_id:
            flash('⚠️ Lütfen bir firma seçin.', 'warning')
            return render_template('auth/select_tenant.html', tenants=active_roles, user_name=user.full_name)
        
        # ✅ GÜVENLİK: Erişim hakkı var mı?
        selected_role = next(
            (r for r in active_roles if r.tenant_id == selected_tenant_id),
            None
        )
        
        if not selected_role:
            logger.warning(f"⚠️ Yetkisiz tenant: user={user.id}, tenant={selected_tenant_id}")
            flash('❌ Geçersiz firma seçimi!', 'danger')
            return render_template('auth/select_tenant.html', tenants=active_roles, user_name=user.full_name)
        
        # Giriş tamamla
        logger.info(f"✅ Firma seçildi: user={user.id}, tenant={selected_tenant_id}")
        return finalize_login(user, selected_role.tenant_id, selected_role.role)
    
    # GET: Firma listesi
    return render_template('auth/select_tenant.html', tenants=active_roles, user_name=user.full_name)


# ========================================
# 3. FINALIZE LOGIN
# ========================================

def finalize_login(user, tenant_id, role):
    """
    Giriş tamamla (Remember YOK)
    
    Args:
        user: User objesi
        tenant_id: Tenant UUID
        role: Kullanıcı rolü
    
    Returns:
        redirect: Ana sayfaya
    """
    logger.info(f"🔵 finalize_login BAŞLADI: user={user.id}, tenant={tenant_id}")
    
    # 1. Tenant bilgileri
    tenant = db.session.get(Tenant, tenant_id)
    logger.info(f"🔵 Tenant bulundu: {tenant.unvan if tenant else 'YOK'}")
    
    if not tenant or not tenant.is_active:
        logger.error(f"❌ Tenant bulunamadı: {tenant_id}")
        flash('❌ Firma bulunamadı veya devre dışı.', 'danger')
        return redirect(url_for('auth.login'))
    
    # 2. ✅ LİSANS LİMİT KONTROLÜ
    license_rec = License.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).first()
    
    max_users = license_rec.max_users if license_rec else 1
    
    allowed, message = SessionService.can_login(tenant_id, max_users)
    
    if not allowed:
        logger.warning(f"⚠️ Lisans limiti: tenant={tenant_id}, {message}")
        flash(f'🚫 {message}', 'danger')
        return redirect(url_for('auth.login'))
    
    # 3. Session hazırla
    session.clear()
    logger.info(f"🔵 Session temizlendi")
    
    session['tenant_id'] = tenant.id
    session['tenant_name'] = tenant.unvan
    session['tenant_code'] = tenant.kod
    session['tenant_role'] = role
    session['user_id'] = user.id
    session['user_name'] = user.full_name
    session['user_email'] = user.email
    
    session.modified = True  # ✅ EKLE
    
    logger.info(f"🔵 Session dolduruldu: tenant_id={session.get('tenant_id')}")
    
        # 4. Flask-Login
    login_success = login_user(user, remember=False)
    logger.info(f"🔵 login_user() sonuç: {login_success}")
    
    from flask_login import current_user
    logger.info(f"🔵 current_user.is_authenticated: {current_user.is_authenticated}")
    
    if not current_user.is_authenticated:
        logger.error(f"❌ Flask-Login başarısız!")
        flash('❌ Giriş başarısız.', 'danger')
        return redirect(url_for('auth.login'))
    
    # 5. Session service
    try:
        SessionService.register_session(user, tenant.id)
        logger.info(f"🔵 SessionService kayıt başarılı")
    except Exception as e:
        logger.error(f"❌ SessionService hatası: {e}", exc_info=True)
    
    # 6. Son kontrol
    logger.info(
        f"✅ Giriş tamamlandı: "
        f"authenticated={current_user.is_authenticated}, "
        f"session_tenant_id={session.get('tenant_id')}, "
        f"user_id={user.id}"
    )
    
    flash(f'✅ Hoş geldiniz, {user.full_name}!', 'success')
    return redirect(url_for('main.index'))


# ========================================
# 4. LOGOUT
# ========================================

@auth_bp.route('/logout')
@login_required
def logout():
    """Kullanıcı çıkışı"""
    
    try:
        SessionService.logout()
        logger.info(f"✅ Çıkış: user={current_user.email}")
    except Exception as e:
        logger.error(f"❌ Logout hatası: {e}", exc_info=True)
    
    logout_user()
    session.clear()
    
    flash('👋 Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('auth.login'))


# ========================================
# 5. CHANGE TENANT (Navbar)
# ========================================

@auth_bp.route('/change-tenant', methods=['POST'])
@login_required
def change_tenant():
    """
    Navbar'dan firma değiştirme (AJAX)
    
    Returns:
        json: {success, message, redirect}
    """
    
    tenant_id = request.form.get('tenant_id')
    
    if not tenant_id:
        return jsonify({'success': False, 'message': 'Firma ID gerekli'}), 400
    
    # ✅ GÜVENLİK: Erişim hakkı var mı?
    if not has_tenant_access(current_user.id, tenant_id):
        logger.warning(f"⚠️ Yetkisiz tenant değiştirme: user={current_user.id}, tenant={tenant_id}")
        return jsonify({'success': False, 'message': 'Bu firmaya erişim yetkiniz yok!'}), 403
    
    # Tenant bilgileri
    tenant = db.session.get(Tenant, tenant_id)
    
    if not tenant or not tenant.is_active:
        return jsonify({'success': False, 'message': 'Firma bulunamadı'}), 404
    
    # Rol bilgisi
    role = db.session.query(UserTenantRole).filter_by(
        user_id=current_user.id,
        tenant_id=tenant_id,
        is_active=True
    ).first()
    
    if not role:
        return jsonify({'success': False, 'message': 'Rol bulunamadı'}), 404
    
    # ✅ LİSANS KONTROLÜ
    license_rec = License.query.filter_by(tenant_id=tenant_id, is_active=True).first()
    max_users = license_rec.max_users if license_rec else 1
    
    allowed, message = SessionService.can_login(tenant_id, max_users)
    
    if not allowed:
        logger.warning(f"⚠️ Firma değiştirme lisans limiti: tenant={tenant_id}")
        return jsonify({'success': False, 'message': message}), 403
    
    # Session güncelle
    old_tenant = session.get('tenant_name')
    
    session['tenant_id'] = tenant.id
    session['tenant_name'] = tenant.name
    session['tenant_code'] = tenant.kod
    session['tenant_role'] = role.role
    
    # Context temizle
    session.pop('aktif_firma_id', None)
    session.pop('aktif_donem_id', None)
    session.pop('aktif_sube_id', None)
    
    # Session kaydı güncelle
    try:
        SessionService.register_session(current_user._get_current_object(), tenant.id)
    except Exception as e:
        logger.error(f"❌ Session kayıt hatası: {e}")
    
    logger.info(f"✅ Firma değiştirildi: user={current_user.email}, {old_tenant} → {tenant.name}")
    
    return jsonify({
        'success': True,
        'message': f'✅ {tenant.name} firmasına geçiş yapıldı',
        'redirect': url_for('main.index')
    })


# ========================================
# 6. INDEX (Login Sonrası)
# ========================================

@auth_bp.route('/index')
@login_required
def index():
    """Login sonrası ana sayfa"""
    
    if not session.get('tenant_id'):
        return redirect(url_for('auth.select_tenant'))
    
    return redirect(url_for('main.index'))