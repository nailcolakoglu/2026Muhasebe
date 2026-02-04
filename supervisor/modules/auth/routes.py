# supervisor/modules/auth/routes.py

"""
Supervisor Auth Routes
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime

# Modeller ve Formlar
from .forms import LoginForm  # LoginForm'u buradan çekiyoruz
from models.supervisor import Supervisor
from models.audit import AuditLog
from extensions import db

# Blueprint Tanımı
auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')

# ========================================
# LOGIN (GİRİŞ)
# ========================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username_input = form.username.data
        password_input = form.password.data
        
        # Kullanıcıyı bul
        user = Supervisor.query.filter(
            (Supervisor.username == username_input) | 
            (Supervisor.email == username_input)
        ).first()

        if user:
            print(f"✅ Veritabanında Bulundu: ID={user.id}, User={user.username}")
            
            if user.check_password(password_input):
                # 🚨 DÜZELTİLEN SATIR: 'remember_me' yerine 'remember'
                login_user(user, remember=form.remember.data)
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard.index'))
            else:
                flash('Hatalı şifre.', 'danger')
                print("❌ Şifre eşleşmedi.")
        else:
            flash('Böyle bir kullanıcı bulunamadı.', 'danger')
            print("❌ Kullanıcı veritabanında yok.")
            
    return render_template('auth/login.html', form=form)

# ========================================
# LOGOUT (ÇIKIŞ)
# ========================================

@auth_bp.route('/logout')
@login_required
def logout():
    """Çıkış Yap"""
    
    # Audit Log (Çıkış)
    try:
        AuditLog.log(
            action='user.logout',
            supervisor=current_user,
            description=f'{current_user.full_name} çıkış yaptı.',
            status='success'
        )
    except:
        pass # Log hatası çıkışı engellemesin
    
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('auth.login'))


# ========================================
# YETKİSİZ ERİŞİM
# ========================================

@auth_bp.route('/unauthorized')
def unauthorized():
    """Yetkisiz Erişim Sayfası"""
    return render_template('unauthorized.html'), 403