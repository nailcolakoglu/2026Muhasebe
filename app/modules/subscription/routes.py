# app/modules/subscription/routes.py

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
import uuid
import time
from werkzeug.security import generate_password_hash
from app.extensions import db

# Ana modellerimizi (Master DB) içeri aktarıyoruz
from app.models.master import Tenant, License, User, UserTenantRole

try:
    from supervisor.supervisor_config import SupervisorConfig
except ImportError:
    SupervisorConfig = None

subscription_bp = Blueprint('subscription', __name__, url_prefix='/paketler')

def get_paketler():
    if SupervisorConfig and hasattr(SupervisorConfig, 'LICENSE_TYPES'):
        return SupervisorConfig.LICENSE_TYPES
    return {
        'starter': {'name': 'Başlangıç', 'duration_days': 30, 'price': 999},
        'professional': {'name': 'Profesyonel', 'duration_days': 365, 'price': 2499},
        'enterprise': {'name': 'Kurumsal', 'duration_days': 365, 'price': 9999}
    }

@subscription_bp.route('/')
def pricing():
    """Paketlerin listelendiği vitrin sayfası"""
    return render_template('subscription/pricing.html', paketler=get_paketler())

@subscription_bp.route('/satin-al/<string:plan_id>')
def checkout(plan_id):
    """Ödeme formunun (Kredi Kartı) gösterildiği sayfa"""
    paketler = get_paketler()
    if plan_id not in paketler:
        return "Geçersiz Paket", 404
        
    secilen_paket = paketler[plan_id]
    return render_template('subscription/checkout.html', plan_id=plan_id, plan=secilen_paket)

@subscription_bp.route('/api/mock-odeme', methods=['POST'])
def mock_odeme():
    data = request.json
    plan_id = data.get('plan_id')
    firma_adi = data.get('firma_adi')
    email = data.get('email')
    sifre = data.get('sifre')
    
    if not all([plan_id, firma_adi, email, sifre]):
        return jsonify({'success': False, 'message': 'Lütfen tüm alanları doldurun.'})

    
    time.sleep(2) # 1. Banka Ödeme Simülasyonu

    try:
        from app.modules.firmalar.services import FirmaService
        import uuid
        import re # ✨ YENİ EKLENDİ: İstenmeyen karakterleri temizlemek için
            
        # Firma kodunu isimden üret ve sadece Harf/Rakam bırak
        kod_prefix = "".join([w[:3].upper() for w in firma_adi.split()][:2])
        kod_prefix = re.sub(r'[^A-Z0-9]', '', kod_prefix) # ✨ DÜZELTME: Sadece A-Z ve 0-9 kalsın
        if not kod_prefix: kod_prefix = "FRM"
            
        # ✨ DÜZELTME: Aradaki tire (-) işaretini sildik. (Örn: ABC1234 olacak)
        tenant_kod = f"{kod_prefix}{str(uuid.uuid4())[:4].upper()}"
            
        # SENİN KUSURSUZ SERVİSİNİ ÇAĞIRIYORUZ
        basari, mesaj, tenant = FirmaService.firma_olustur(
            kod=tenant_kod,
            unvan=firma_adi,
            vergi_no="1111111111", # Sembolik
            admin_email=email,
            admin_password=sifre
        )
        
        if not basari:
            return jsonify({'success': False, 'message': mesaj})
        
        # 2. Lisansı Ekle (Firma başarıyla kurulduktan sonra)
        paketler = get_paketler()
        secilen_paket = paketler.get(plan_id, {})
        gecerlilik_suresi = secilen_paket.get('duration_days', 365)
        
        from app.models.master import License
        yeni_lisans = License(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            license_key=f"LIC-{tenant.kod}-{str(uuid.uuid4())[:8].upper()}",
            license_type=plan_id,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=gecerlilik_suresi),
            max_users=secilen_paket.get('max_users', 5),
            max_branches=secilen_paket.get('max_branches', 1),
            is_active=True
        )
        db.session.add(yeni_lisans)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Ödeme başarılı! Kurumsal hesabınız saniyeler içinde oluşturuldu.',
            'tenant_kod': tenant.kod
        })
        
    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Kurulum hatası: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Kurulum hatası: {str(e)}'}), 500