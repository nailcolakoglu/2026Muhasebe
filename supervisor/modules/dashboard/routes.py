# supervisor/modules/dashboard/routes.py

"""
Supervisor Dashboard Routes
"""

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import sys
import os

# Path ayarları
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
APP_DIR = os.path.join(BASE_DIR, '..', 'app')

# ✅ Path'i önce ekle
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from extensions import db
from models.supervisor import Supervisor
from models.audit import AuditLog
from models.backup import Backup
from models.system_metric import SystemMetric
from models.notification import Notification

# ✅ Ana uygulamanın modelleri (düzeltilmiş import)
try:
    from models.master import Tenant, User, License
except ImportError: 
    # Eğer models.master yoksa, doğrudan import et
    sys.path.insert(0, os.path.join(APP_DIR, 'models'))
    from master import Tenant, User, License

# Blueprint
dashboard_bp = Blueprint('dashboard', __name__)


# ========================================
# DASHBOARD (ANA SAYFA)
# ========================================

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard ana sayfa"""
    
    # ========================================
    # İSTATİSTİKLER
    # ========================================
    
    try:
        # Toplam Firmalar
        total_tenants = Tenant.query.count()
        active_tenants = Tenant.query.filter_by(is_active=True).count()
    except: 
        total_tenants = 0
        active_tenants = 0
    
    try:
        # Toplam Kullanıcılar
        total_users = User.query.count()
    except:
        total_users = 0
    
    try: 
        # Toplam Lisanslar
        total_licenses = License.query.count()
        active_licenses = License.query.filter_by(is_active=True).count()
        
        # Süresi dolmak üzere lisanslar (30 gün içinde)
        expiring_soon = License.query.filter(
            License.valid_until <= datetime.utcnow() + timedelta(days=30),
            License.valid_until >= datetime.utcnow(),
            License.is_active == True
        ).count()
    except:
        total_licenses = 0
        active_licenses = 0
        expiring_soon = 0
    
    try:
        # Son yedekler
        recent_backups = Backup.query.order_by(
            Backup.created_at.desc()
        ).limit(5).all()
        
        # Başarısız yedekler (son 7 gün)
        failed_backups = Backup.query.filter(
            Backup.status == 'failed',
            Backup.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
    except:
        recent_backups = []
        failed_backups = 0
    
    try:
        # Son aktiviteler (Audit Log)
        recent_activities = AuditLog.query.order_by(
            AuditLog.created_at.desc()
        ).limit(10).all()
    except:
        recent_activities = []
    
    try:
        # Okunmamış bildirimler
        unread_notifications = Notification.query.filter_by(
            supervisor_id=current_user.id,
            is_read=False
        ).count()
    except:
        unread_notifications = 0
    
    try:
        # Son sistem metrikleri
        latest_metric = SystemMetric.query.order_by(
            SystemMetric.created_at.desc()
        ).first()
    except:
        latest_metric = None
    
    # ========================================
    # GRAFİK VERİLERİ (Son 7 Gün)
    # ========================================
    
    # Son 7 günün tarihleri
    last_7_days = []
    for i in range(6, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        last_7_days.append(day.strftime('%Y-%m-%d'))
    
    # Günlük aktivite sayıları
    daily_activities = []
    try:
        for day in last_7_days: 
            count = AuditLog.query.filter(
                db.func.date(AuditLog.created_at) == day
            ).count()
            daily_activities.append(count)
    except:
        daily_activities = [0] * 7
    
    # ========================================
    # LİSANS DAĞILIMI
    # ========================================
    try:
        license_distribution = db.session.query(
            License.license_type,
            db.func.count(License.id)
        ).filter_by(is_active=True).group_by(License.license_type).all()
        
        license_labels = [lt[0] for lt in license_distribution]
        license_counts = [lt[1] for lt in license_distribution]
    except: 
        license_labels = []
        license_counts = []
    
    # ========================================
    # TEMPLATE'E GÖNDERİLECEK VERİLER
    # ========================================
    
    return render_template('dashboard/index.html',
        # İstatistikler
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        total_users=total_users,
        total_licenses=total_licenses,
        active_licenses=active_licenses,
        expiring_soon=expiring_soon,
        failed_backups=failed_backups,
        unread_notifications=unread_notifications,
        
        # Listeler
        recent_backups=recent_backups,
        recent_activities=recent_activities,
        
        # Sistem
        latest_metric=latest_metric,
        
        # Grafikler
        last_7_days=last_7_days,
        daily_activities=daily_activities,
        license_labels=license_labels,
        license_counts=license_counts
    )


# ========================================
# API:  REAL-TIME STATS (AJAX)
# ========================================

@dashboard_bp.route('/api/stats')
@login_required
def get_stats():
    """Gerçek zamanlı istatistikler (AJAX)"""
    
    try:
        # Sistem metrikleri
        latest_metric = SystemMetric.query.order_by(
            SystemMetric.created_at.desc()
        ).first()
        
        stats = {
            'active_tenants': Tenant.query.filter_by(is_active=True).count(),
            'total_users': User.query.count(),
            'active_licenses': License.query.filter_by(is_active=True).count(),
            'unread_notifications': Notification.query.filter_by(
                supervisor_id=current_user.id,
                is_read=False
            ).count(),
            'system':  {
                'cpu': latest_metric.cpu_percent if latest_metric else 0,
                'memory': latest_metric.memory_percent if latest_metric else 0,
                'disk':  latest_metric.disk_percent if latest_metric else 0
            } if latest_metric else None
        }
    except Exception as e:
        stats = {
            'error': str(e)
        }
    
    return jsonify(stats)