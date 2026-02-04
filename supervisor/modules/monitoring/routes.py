# supervisor/modules/monitoring/routes.py

import os
import sys
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

# ========================================
# 1. PATH VE IMPORT AYARLARI
# ========================================
current_file = os.path.abspath(__file__)
supervisor_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
project_root = os.path.dirname(supervisor_root)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# App Extension ve Modellerini Yükle
try:
    from app.extensions import db
    from app.models.master import MasterActiveSession, Tenant, User
except ImportError:
    # Fallback (Eğer path sorunu olursa)
    sys.path.append(project_root)
    from app.extensions import db
    from app.models.master import MasterActiveSession, Tenant, User

from services.monitoring_service import MonitoringService

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/')
@login_required
def index():
    """Monitoring Dashboard"""
    
    # 1. Sistem İstatistikleri (Mevcut servisinizden)
    # Eğer MonitoringService içinde get_system_stats yoksa hata vermemesi için try-except
    try:
        stats = MonitoringService.get_system_stats()
    except:
        stats = {'cpu': 0, 'ram_percent': 0, 'disk_percent': 0, 'uptime': 'N/A'}

    # 2. CANLI OTURUMLARI ÇEK (JOIN ile Detaylı Bilgi)
    # MasterActiveSession + Tenant + User tablolarını birleştiriyoruz
    try:
        raw_sessions = db.session.query(
            MasterActiveSession,
            Tenant.unvan.label('tenant_name'),
            Tenant.kod.label('tenant_code'),
            User.full_name,
            User.email
        ).join(
            Tenant, MasterActiveSession.tenant_id == Tenant.id
        ).join(
            User, MasterActiveSession.user_id == User.id
        ).order_by(MasterActiveSession.last_activity.desc()).all()

        # Veriyi template için hazırla
        live_sessions = []
        now = datetime.now()
        
        for sess, tenant_name, tenant_code, user_name, user_email in raw_sessions:
            # Boşta kalma süresi (Idle Time)
            idle_seconds = (now - sess.last_activity).total_seconds()
            
            # Durum Belirleme (5 dk'dan az ise Aktif, yoksa Boşta)
            status = 'active' if idle_seconds < 300 else 'idle'
            
            live_sessions.append({
                'token': sess.session_token, # Kill işlemi için token lazım
                'tenant': f"{tenant_name} ({tenant_code})",
                'user': user_name or user_email,
                'ip': sess.ip_address or 'Bilinmiyor',
                'device': _parse_user_agent(sess.user_agent), # Basitleştirilmiş cihaz adı
                'login_at': sess.login_at,
                'last_activity': sess.last_activity,
                'status': status,
                'idle_min': int(idle_seconds / 60)
            })
            
    except Exception as e:
        print(f"❌ Session Çekme Hatası: {e}")
        live_sessions = []

    return render_template('monitoring/index.html', 
                          stats=stats, 
                          sessions=live_sessions)

@monitoring_bp.route('/kill/<token>', methods=['POST'])
@login_required
def kill_session(token):
    """
    Oturumu Zorla Sonlandır (Kick User)
    """
    # Güvenlik: Sadece Süper Admin yapabilsin (Opsiyonel)
    # if not current_user.is_superadmin: ...

    try:
        # Token ile oturumu bul ve sil
        session_to_kill = MasterActiveSession.query.filter_by(session_token=token).first()
        
        if session_to_kill:
            user_name = session_to_kill.user.full_name if session_to_kill.user else "Kullanıcı"
            db.session.delete(session_to_kill)
            db.session.commit()
            flash(f"✅ {user_name} kullanıcısının oturumu başarıyla sonlandırıldı.", "success")
        else:
            flash("⚠️ Oturum bulunamadı veya zaten sonlanmış.", "warning")
            
    except Exception as e:
        db.session.rollback()
        flash(f"Hata: {str(e)}", "danger")

    return redirect(url_for('monitoring.index'))

def _parse_user_agent(ua_string):
    """User Agent stringinden basit cihaz bilgisi çıkarır"""
    if not ua_string: return "?"
    ua = ua_string.lower()
    if 'mobile' in ua: return '📱 Mobil'
    if 'windows' in ua: return '💻 Windows'
    if 'mac os' in ua: return '🍎 Mac'
    if 'linux' in ua: return '🐧 Linux'
    return '🖥️ Masaüstü'