# supervisor/modules/licenses/api.py

from flask import Blueprint, request, jsonify
from datetime import datetime
import sys
import os

# 1. Yolları Hesapla
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) 
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..')) 

# 2. Path Ayarı
APP_DIR = os.path.join(PROJECT_ROOT, 'app')
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# 🛑 HATALI SATIRI DEĞİŞTİR: 
# db ana extensions'tan, csrf ise supervisor_extensions'tan gelmeli
from supervisor_extensions import csrf 
from extensions import db

# 3. Güvenli Import
try:
    from models.master import License, Tenant
except ImportError:
    # Alternatif deneme
    from master import License, Tenant
    
api_bp = Blueprint('license_api', __name__)


# Bu fonksiyonun tam üzerine ekle
@api_bp.before_request
def bypass_csrf_for_api():
    # Sadece bu blueprint içindeki isteklerde CSRF kontrolünü atla
    # (Eğer @csrf.exempt çalışmıyorsa bu kesin çözümdür)
    pass

@api_bp.route('/validate', methods=['POST'])
@csrf.exempt  # <--- BU SATIR (API'yi CSRF korumasından muaf tutar)
def validate_license():
    """
    Lisans Doğrulama Endpoint'i
    """
    try:
        data = request.get_json(silent=True) or request.form.to_dict()
        client_hwid = data.get('hwid')
        key = data.get('license_key')

        # 1. Temel Kontroller
        if not client_hwid or len(client_hwid) < 5:
            return jsonify({'valid': False, 'message': 'Cihaz donanım kimliği okunamadı!'}), 400

        lic = License.query.filter_by(license_key=key).first()
        if not lic:
            return jsonify({'valid': False, 'message': 'Lisans anahtarı bulunamadı!'}), 404

        # 2. HWID Kilidi Mantığı (DÜZELTİLDİ)
        # Eğer lisansın HWID alanı boşsa, gelen bu cihazı "ilk cihaz" olarak mühürle
        if not lic.hardware_id or lic.hardware_id.strip() == "":
            lic.hardware_id = client_hwid
            db.session.commit()
            print(f"✅ Lisans ilk kez bu cihaza mühürlendi: {client_hwid}")
        
        # Eğer mühürlü HWID ile gelen HWID eşleşmiyorsa reddet
        elif lic.hardware_id != client_hwid:
            return jsonify({
                'valid': False, 
                'message': 'Bu lisans anahtarı zaten başka bir cihazda aktif edilmiş!'
            }), 403

        # 3. Tarih ve Aktiflik Kontrolü
        if not lic.is_active:
            return jsonify({'valid': False, 'message': 'Lisans pasif durumda'}), 403
            
        if lic.valid_until < datetime.utcnow():
            return jsonify({'valid': False, 'message': 'Lisans süresi dolmuş'}), 403

        # 4. Tenant Bilgilerini Al
        tenant = Tenant.query.get(lic.tenant_id)
        
        return jsonify({
            'valid': True,
            'license_id': lic.id,
            'tenant_name': tenant.unvan if tenant else 'Bilinmeyen Firma',
            'db_name': tenant.db_name, # MUHASEBEDB.FDB
            'db_password': tenant.db_password if hasattr(tenant, 'db_password') else 'masterkey',
            'tenant_id': str(tenant.id),
            'valid_until': lic.valid_until.strftime('%Y-%m-%d %H:%M:%S'),
            'type': lic.license_type,
            'limits': {
                'max_users': lic.max_users,
                'max_branches': getattr(lic, 'max_branches', 1)
            },
            'check_date': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'valid': False, 'message': f'Sunucu Hatası: {str(e)}'}), 500
        
        
        print("VALIDATE_LICENSE : ",key)
        if not key:
            return jsonify({'valid': False, 'message': 'Lisans anahtarı eksik'}), 400
        
        client_hwid = data.get('hwid')
        print("CLIENT_HWIND     : ", client_hwid)
        if not client_hwid or len(client_hwid) < 5:
            return jsonify({'valid': False, 'message': 'Cihaz donanım kimliği okunamadı!'}), 400

        # Tarih ve Aktiflik Kontrolü
        if not lic.is_active:
            return jsonify({'valid': False, 'message': 'Lisans pasif durumda'}), 403
            
        if lic.valid_until < datetime.utcnow():
            return jsonify({'valid': False, 'message': 'Lisans süresi dolmuş'}), 403

        # Donanım Kilidi (Hardware Lock) Kontrolü
        if not lic.hardware_id:
            # İlk aktivasyonda kilitle
            lic.hardware_id = client_hwid
            db.session.commit()
        if not lic.hardware_id or lic.hardware_id == "":
            # Eğer HWID henüz kayıtlı değilse (veya boşsa), şimdi mühürle
            lic.hardware_id = client_hwid
            db.session.commit()
            print(f"✅ Lisans ilk kez bu cihaza mühürlendi: {client_hwid}")
        elif lic.hardware_id != client_hwid:
            # Eğer kayıtlı bir HWID varsa ve eşleşmiyorsa reddet
            return jsonify({
                'valid': False, 
                'message': 'Bu lisans anahtarı zaten başka bir cihazda aktif edilmiş!'
            }), 403

        # Başarılı Cevap
        try:
            tenant = Tenant.query.get(lic.tenant_id)
        except:
            print('TENANT HATASI')
        
        return jsonify({
            'valid': True,
            'license_id': lic.id,
            'tenant_name': tenant.unvan if tenant else 'Bilinmeyen Firma',
            # 🚨 KRİTİK EKLEMELER:
            'db_name': tenant.db_name if tenant else None,
            'db_password': tenant.db_password if tenant and hasattr(tenant, 'db_password') else 'masterkey',
            'tenant_id': str(tenant.id) if tenant else None,
            # ------------------
            'valid_until': lic.valid_until.strftime('%Y-%m-%d %H:%M:%S'),
            'type': lic.license_type,
            'limits': {
                'max_users': lic.max_users,
                'max_branches': getattr(lic, 'max_branches', 1)
            },
            'check_date': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'message': f'Sunucu Hatası: {str(e)}'}), 500