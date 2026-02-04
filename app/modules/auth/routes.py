# modules/auth/routes.py (TAM HALİ - ESKİ MANTIK)

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from app.extensions import db, get_tenant_db, close_tenant_db
from app.models.master import User, Tenant, MasterActiveSession, UserTenantRole, License
from app.services.session_service import SessionService

auth_bp = Blueprint('auth', __name__)

# ========================================
# GİRİŞ SAYFASI (SADECE EMAIL + ŞİFRE)
# ========================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Zaten girmişse ana sayfaya
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    from .forms import create_login_form
    form = create_login_form()
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            
            # --- ÇOKLU FİRMA ANALİZİ ---
            # Kullanıcının aktif olan tüm yetkilerini çek
            active_roles = UserTenantRole.query.filter_by(user_id=user.id, is_active=True).join(Tenant).filter(Tenant.is_active==True).all()
            
            if not active_roles:
                flash('Hesabınıza tanımlı aktif bir firma bulunamadı.', 'danger')
                return redirect(url_for('auth.login'))
            
            # SENARYO 1: Sadece 1 Firması Var -> Direkt Gir
            if len(active_roles) == 1:
                role_entry = active_roles[0]
                return finalize_login(user, role_entry.tenant_id, role_entry.role, remember)
            
            # SENARYO 2: Birden Fazla Firması Var -> Seçim Ekranına Git
            else:
                # Kullanıcı ID'sini geçici olarak sakla (henüz login olmadı)
                session['temp_user_id'] = user.id
                session['temp_remember'] = remember
                return redirect(url_for('auth.select_tenant'))
        
        else:
            flash('Hatalı e-posta veya şifre.', 'danger')

    return render_template('auth/login.html', form=form)
    

# ========================================
# FİRMA SEÇİM EKRANI (ÇOK FİRMALI KULLANICILAR İÇİN)
# ========================================
@auth_bp.route('/select-tenant', methods=['GET', 'POST'])
def select_tenant():
    """PROFESYONEL FİRMA SEÇİM EKRANI"""
    
    # Geçici kullanıcı ID'si var mı? Yoksa login'e dön
    temp_user_id = session.get('temp_user_id')
    if not temp_user_id:
        return redirect(url_for('auth.login'))
    
    # Kullanıcıyı ve rollerini çek
    user = User.query.get(temp_user_id)
    roles = UserTenantRole.query.filter_by(user_id=user.id, is_active=True).join(Tenant).filter(Tenant.is_active==True).all()
    
    if request.method == 'POST':
        selected_tenant_id = request.form.get('tenant_id')
        
        # Güvenlik: Kullanıcı gerçekten bu firmaya yetkili mi?
        selected_role = next((r for r in roles if r.tenant_id == selected_tenant_id), None)
        
        if selected_role:
            remember = session.get('temp_remember', False)
            return finalize_login(user, selected_role.tenant_id, selected_role.role, remember)
        else:
            flash("Geçersiz firma seçimi.", "danger")
            
    return render_template('auth/select_tenant.html', tenants=roles, user_name=user.full_name)

def finalize_login(user, tenant_id, role, remember=False):
    """
    Giriş başarılı, session ve Firebird bağlantısını hazırla
    """
    # --- PROFESYONEL KONTROL BAŞLANGIÇ ---
    
    # 1. Lisans Limitini Öğren
    # (Bu import'u fonksiyon içine alabiliriz veya en üstte kalabilir)
    from app.models.master.license import License 
    license_rec = License.query.filter_by(tenant_id=tenant_id, is_active=True).first()
    max_users = license_rec.max_users if license_rec else 1
    
    # 2. Kapı Kontrolü (İçeri girebilir mi?)
    allowed, message = SessionService.can_login(tenant_id, max_users)
    
    if not allowed:
        flash(f'Giriş Başarısız: {message}', 'danger')
        return redirect(url_for('auth.login'))
        
    # --- PROFESYONEL KONTROL BİTİŞ ---

    # Verileri Hazırla
    from app.models.master import Tenant
    tenant = db.session.get(Tenant, tenant_id)

    session['tenant_id'] = tenant.id
    session['tenant_name'] = tenant.unvan
    session['active_db_yolu'] = tenant.db_name
    session['active_db_sifre'] = tenant.get_db_password()
    session['tenant_role'] = role
    
    # Geçici verileri temizle
    session.pop('temp_user_id', None)
    session.pop('temp_remember', None)

    # 👇 2. DÜZELTME: 'remember' bilgisini Flask-Login'e iletiyoruz
    login_user(user, remember=remember)
    
    # Session Kaydı (Token)
    SessionService.register_session(user, tenant.id)
    
    return redirect(url_for('main.index'))

# ========================================
# ÇIKIŞ
# ========================================
@auth_bp.route('/logout')
@login_required
def logout():
    """Çıkış Yap"""
    # DB temizliği
    SessionService.logout()
    logout_user()
    session.clear()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('auth.login'))
    
# ========================================
# FİRMA DEĞİŞTİR (NAVBAR - AJAX)
# ========================================
@auth_bp.route('/change-firma', methods=['POST'])
@login_required
def change_firma():
    """Navbar'dan firma değiştirme (Holding içinde)"""
    from models import Firma
    from extensions import get_tenant_db
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Firebird bağlantısı yok'}), 500
    
    firma_id = request.form.get('firma_id')
    
    if not firma_id: 
        return jsonify({'success': False, 'message': 'Firma ID gerekli'}), 400
    
    firma = tenant_db.query(Firma).get(int(firma_id))
    
    if not firma:
        return jsonify({'success': False, 'message': 'Firma bulunamadı'}), 404
    
    session['aktif_firma_id'] = firma.id
    session.pop('aktif_donem_id', None)
    session.pop('aktif_sube_id', None)
    
    return jsonify({
        'success': True,
        'message': f'{firma.unvan} firması seçildi',
        'redirect': url_for('main.index')
    })