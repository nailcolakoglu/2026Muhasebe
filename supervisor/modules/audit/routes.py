# supervisor/modules/audit/routes.py

import sys
import os
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

# Path ayarları
current_file = os.path.abspath(__file__)
supervisor_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
project_root = os.path.dirname(supervisor_root)

if project_root not in sys.path: sys.path.insert(0, project_root)
if supervisor_root not in sys.path: sys.path.insert(0, supervisor_root)

from app.extensions import db
from models.audit import AuditLog
from supervisor_config import SupervisorConfig

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/')
@login_required
def index():
    """Denetim Loglarını Listele"""
    
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user', '')
    date_start = request.args.get('date_start', '')
    date_end = request.args.get('date_end', '')
    
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    
    # --- Filtreleme ---
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
    
    if user_filter:
        query = query.filter(AuditLog.supervisor_username.ilike(f"%{user_filter}%"))
        
    if date_start:
        query = query.filter(AuditLog.created_at >= date_start)
        
    if date_end:
        # Bitiş gününün sonuna kadar (23:59:59)
        query = query.filter(AuditLog.created_at <= f"{date_end} 23:59:59")
    
    # Sayfalama
    per_page = getattr(SupervisorConfig, 'ITEMS_PER_PAGE', 20)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Action Tiplerini Topla (Selectbox için)
    # MySQL 5.7 uyumlu distinct sorgusu
    actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]
    
    return render_template('audit/index.html', 
                           logs=pagination.items, 
                           pagination=pagination,
                           actions=actions,
                           filters={
                               'action': action_filter,
                               'user': user_filter,
                               'date_start': date_start,
                               'date_end': date_end
                           })

@audit_bp.route('/<log_id>')
@login_required
def detail(log_id):
    """Log Detayı ve JSON Değişiklikleri"""
    log = AuditLog.query.get_or_404(log_id)
    
    # Changes JSON string'ini dict'e çevir (Template'de rahat okumak için)
    changes_data = {}
    if log.changes:
        try:
            changes_data = json.loads(log.changes)
        except:
            changes_data = {'raw': log.changes}
            
    return render_template('audit/detail.html', log=log, changes=changes_data)