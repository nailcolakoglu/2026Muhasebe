# app/modules/activation/routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.license_client import LicenseClient
from utils.hardware import get_hardware_id

activation_bp = Blueprint('activation', __name__, template_folder='templates')

@activation_bp.route('/activate', methods=['GET', 'POST'])
def activate():
    if request.method == 'POST':
        key = request.form.get('license_key')
        # 🚨 TARAYICIDAN GELEN ID'Yİ BURADA YAKALIYORUZ
        b_hwid = request.form.get('browser_hwid') 
        
        client = LicenseClient()
        # Yakaladığımız ID'yi activate metoduna gönderiyoruz
        result = client.activate(key, hwid=b_hwid) 
        
        if result.get('success'):
            flash('✅ Yazılım başarıyla aktif edildi!', 'success')
            return redirect('/auth/login')
        else:
            flash(f"❌ Hata: {result.get('message')}", 'danger')
            
    return render_template('activation/activate.html')