"""
Form Builder - Validation API
Server-side validasyon ve AJAX (Async) endpoint'leri
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from sqlalchemy import text
from app.extensions import get_tenant_db
from app.form_builder.validation_rules import Validator

# Blueprint oluştur
validation_bp = Blueprint('validation', __name__, url_prefix='/api')

def ajax_required(f):
    """Sadece AJAX (Fetch/XHR) isteklerini kabul eden güvenlik kalkanı"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Frontend'de fetch atarken headers içine 'X-Requested-With': 'XMLHttpRequest' eklenmiş olmalı
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Erişim reddedildi. Bu API sadece asenkron (AJAX) istekler içindir.'
            }), 403
        return f(*args, **kwargs)
    return decorated_function


@validation_bp.route('/validate-field', methods=['POST'])
@ajax_required
def validate_field():
    """
    Tekil bir alanı anında doğrulamak için kullanılır.
    Merkezi Validator (validation_rules.py) motorunu kullanır.
    """
    data = request.get_json() or {}
    val = data.get('value')
    rule_name = data.get('rule') # Örn: "EMAIL", "IBAN" veya özel kural "STRONG_PASS"
    
    if not rule_name:
        return jsonify({'valid': False, 'message': 'Kural belirtilmedi.'})
        
    # ✨ BÜYÜ BURADA: Tüm yükü az önce yazdığımız Merkezi Motor'a verdik!
    is_valid, msg = Validator.validate(val, rule_name)
    
    return jsonify({
        'valid': is_valid,
        'message': msg if not is_valid else ""
    })


@validation_bp.route('/check-unique', methods=['POST'])
@ajax_required
def check_unique():
    """
    Benzersizlik kontrolü (Email, Kullanıcı Adı, Vergi No vb.)
    SaaS mimarisine uygun olarak o anki aktif firmanın (Tenant) veritabanında arama yapar.
    
    Beklenen JSON: { "field": "email", "value": "test@test.com", "table": "b2b_kullanicilari", "exclude_id": "123" }
    """
    try:
        data = request.get_json() or {}
        
        field = str(data.get('field', ''))
        value = str(data.get('value', ''))
        table_name = str(data.get('table', ''))
        exclude_id = data.get('exclude_id')
        
        if not all([field, value, table_name]):
            return jsonify({'valid': False, 'message': 'Eksik parametre.'}), 400

        # ✨ GÜVENLİK KALKANI: SQL Injection'ı önlemek için sadece izin verilen tablolarda aramaya izin ver
        ALLOWED_TABLES = ['kullanicilar', 'b2b_kullanicilari', 'cari_hesaplar', 'stok_kartlari']
        if table_name not in ALLOWED_TABLES:
            return jsonify({'valid': False, 'message': 'Güvenlik ihlali: Bu tabloda arama yapılamaz.'}), 403
            
        # Sadece harf, rakam ve alt çizgiye izin ver (Güvenlik)
        import re
        if not re.match(r'^\w+$', field):
            return jsonify({'valid': False, 'message': 'Geçersiz alan adı.'}), 400

        tenant_db = get_tenant_db()
        if not tenant_db:
            return jsonify({'valid': False, 'message': 'Veritabanı bağlantısı yok.'}), 500

        # ✨ DİNAMİK VE GÜVENLİ SQL SORGUSU
        query = f"SELECT id FROM {table_name} WHERE {field} = :value AND deleted_at IS NULL"
        params = {"value": value}
        
        if exclude_id:
            query += " AND id != :exclude_id"
            params["exclude_id"] = str(exclude_id)
            
        result = tenant_db.execute(text(query), params).fetchone()
        
        is_unique = result is None
        
        return jsonify({
            'valid': is_unique,
            'message': 'Bu değer zaten kullanımda.' if not is_unique else 'Kullanılabilir.'
        })

    except Exception as e:
        import logging
        logging.error(f"Unique Check Hatası: {str(e)}")
        return jsonify({
            'valid': False,
            'message': 'Sunucu hatası oluştu.'
        }), 500