"""
Form Builder - Validation API
Server-side validasyon endpoint'leri
"""

from flask import Blueprint, request, jsonify
from functools import wraps
import re
from datetime import datetime

# Blueprint oluştur
validation_bp = Blueprint('validation', __name__, url_prefix='/api')


def ajax_required(f):
    """AJAX isteklerini kontrol eden decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Bu endpoint sadece AJAX istekleri için kullanılabilir'
            }), 400
        return f(*args, **kwargs)
    return decorated_function


class ServerValidator:
    """Sunucu tarafı validasyon sınıfı"""
    
    MESSAGES = {
        'required': 'Bu alan zorunludur',
        'email': 'Geçerli bir e-posta adresi giriniz',
        'phone': 'Geçerli bir telefon numarası giriniz',
        'tckn': 'Geçerli bir TC Kimlik Numarası giriniz',
        'vkn': 'Geçerli bir Vergi Kimlik Numarası giriniz',
        'iban': 'Geçerli bir IBAN giriniz',
        'plate': 'Geçerli bir araç plakası giriniz',
        'url': 'Geçerli bir URL giriniz',
        'date': 'Geçerli bir tarih giriniz',
        'number': 'Geçerli bir sayı giriniz',
        'min_length': 'En az {min} karakter girilmelidir',
        'max_length': 'En fazla {max} karakter girilebilir',
        'min_value': 'Değer en az {min} olmalıdır',
        'max_value': 'Değer en fazla {max} olabilir',
        'pattern': 'Geçersiz format',
        'invalid': 'Geçersiz değer'
    }
    
    @staticmethod
    def validate_required(value):
        """Zorunlu alan kontrolü"""
        if value is None:
            return False
        if isinstance(value, str):
            return len(value.strip()) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True
    
    @staticmethod
    def validate_email(value):
        """Email formatı kontrolü"""
        if not value:
            return True
        pattern = r'^[a-zA-Z0-9.! #$%&\'*+/=? ^_`{|}~-]+@[a-zA-Z0-9](? :[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])? )*$'
        return bool(re.match(pattern, str(value).lower()))
    
    @staticmethod
    def validate_phone_tr(value):
        """Türkiye telefon numarası kontrolü"""
        if not value:
            return True
        
        # Temizle
        phone = re.sub(r'[\s\-\(\)\+]', '', str(value))
        
        # Başındaki 90 veya 0'ı kaldır
        if phone.startswith('90'):
            phone = phone[2:]
        if phone.startswith('0'):
            phone = phone[1:]
        
        # 10 hane olmalı
        if len(phone) != 10:
            return False
        
        # 5 ile başlamalı (GSM)
        if not phone.startswith(('5', '2', '3', '4')):
            return False
        
        return True
    
    @staticmethod
    def validate_tckn(value):
        """TC Kimlik No kontrolü"""
        if not value:
            return True
        
        tckn = re.sub(r'\s', '', str(value))
        
        # Uzunluk kontrolü
        if len(tckn) != 11:
            return False
        
        # Sadece rakam
        if not tckn.isdigit():
            return False
        
        # İlk hane 0 olamaz
        if tckn[0] == '0':
            return False
        
        # Tüm rakamlar aynı olamaz
        if len(set(tckn)) == 1:
            return False
        
        digits = [int(d) for d in tckn]
        
        # 10.hane kontrolü
        odd_sum = sum(digits[i] for i in range(0, 9, 2))
        even_sum = sum(digits[i] for i in range(1, 8, 2))
        tenth = (odd_sum * 7 - even_sum) % 10
        
        if digits[9] != tenth:
            return False
        
        # 11.hane kontrolü
        if digits[10] != sum(digits[:10]) % 10:
            return False
        
        return True
    
    @staticmethod
    def validate_vkn(value):
        """Vergi Kimlik No kontrolü"""
        if not value:
            return True
        
        vkn = re.sub(r'\s', '', str(value))
        
        if len(vkn) != 10:
            return False
        
        if not vkn.isdigit():
            return False
        
        digits = [int(d) for d in vkn]
        total = 0
        
        for i in range(9):
            tmp = (digits[i] + (9 - i)) % 10
            total += (tmp * (2 ** (9 - i))) % 9
            if tmp != 0 and (tmp * (2 ** (9 - i))) % 9 == 0:
                total += 9
        
        check_digit = (10 - (total % 10)) % 10
        
        return digits[9] == check_digit
    
    @staticmethod
    def validate_iban(value):
        """IBAN kontrolü (Türkiye)"""
        if not value:
            return True
        
        iban = re.sub(r'[\s\-]', '', str(value)).upper()
        
        # Türkiye IBAN uzunluğu
        if len(iban) != 26:
            return False
        
        # TR ile başlamalı
        if not iban.startswith('TR'):
            return False
        
        # IBAN algoritması
        rearranged = iban[4:] + iban[:4]
        
        numeric_string = ''
        for char in rearranged:
            if char.isalpha():
                numeric_string += str(ord(char) - 55)
            else:
                numeric_string += char
        
        # Mod 97
        remainder = 0
        for digit in numeric_string:
            remainder = (remainder * 10 + int(digit)) % 97
        
        return remainder == 1
    
    @staticmethod
    def validate_plate(value):
        """Araç plakası kontrolü"""
        if not value:
            return True
        
        plate = re.sub(r'\s', '', str(value)).upper()
        
        if len(plate) < 5 or len(plate) > 8:
            return False
        
        patterns = [
            r'^(0[1-9]|[1-7][0-9]|8[01])[A-Z]{1}[0-9]{4}$',
            r'^(0[1-9]|[1-7][0-9]|8[01])[A-Z]{2}[0-9]{3,4}$',
            r'^(0[1-9]|[1-7][0-9]|8[01])[A-Z]{3}[0-9]{2,3}$'
        ]
        
        return any(re.match(p, plate) for p in patterns)
    
    @staticmethod
    def validate_url(value):
        """URL kontrolü"""
        if not value:
            return True
        
        pattern = r'^https? ://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, str(value), re.IGNORECASE))
    
    @staticmethod
    def validate_date(value):
        """Tarih kontrolü"""
        if not value:
            return True
        
        formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']
        
        for fmt in formats:
            try:
                datetime.strptime(str(value), fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    @classmethod
    def validate_field(cls, field_name, value, field_type, **params):
        """
        Tek bir alanı doğrula
        Returns: (is_valid: bool, error_message: str or None)
        """
        errors = []
        
        # Required kontrolü
        if params.get('required') and not cls.validate_required(value):
            return False, cls.MESSAGES['required']
        
        # Boş değer ve zorunlu değilse geç
        if not value and not params.get('required'):
            return True, None
        
        # Tip bazlı validasyon
        type_validators = {
            'email': ('email', cls.validate_email),
            'tel': ('phone', cls.validate_phone_tr),
            'phone': ('phone', cls.validate_phone_tr),
            'tckn': ('tckn', cls.validate_tckn),
            'vkn': ('vkn', cls.validate_vkn),
            'iban': ('iban', cls.validate_iban),
            'plate': ('plate', cls.validate_plate),
            'url': ('url', cls.validate_url),
            'date': ('date', cls.validate_date),
        }
        
        if field_type in type_validators:
            msg_key, validator_fn = type_validators[field_type]
            if not validator_fn(value):
                return False, cls.MESSAGES[msg_key]
        
        # Uzunluk kontrolleri
        if params.get('min_length'):
            min_len = int(params['min_length'])
            if len(str(value)) < min_len:
                return False, cls.MESSAGES['min_length'].format(min=min_len)
        
        if params.get('max_length'):
            max_len = int(params['max_length'])
            if len(str(value)) > max_len:
                return False, cls.MESSAGES['max_length'].format(max=max_len)
        
        # Sayısal kontroller
        if field_type in ['number', 'currency']:
            try:
                # TR formatını temizle
                clean_value = str(value).replace('.', '').replace(',', '.')
                num_value = float(clean_value)
                
                if params.get('min_val') is not None:
                    if num_value < float(params['min_val']):
                        return False, cls.MESSAGES['min_value'].format(min=params['min_val'])
                
                if params.get('max_val') is not None:
                    if num_value > float(params['max_val']):
                        return False, cls.MESSAGES['max_value'].format(max=params['max_val'])
                        
            except (ValueError, TypeError):
                return False, cls.MESSAGES['number']
        
        # Pattern kontrolü
        if params.get('pattern'):
            try:
                if not re.match(params['pattern'], str(value)):
                    return False, cls.MESSAGES['pattern']
            except re.error:
                pass  # Geçersiz regex, atla
        
        return True, None


# ============= API ENDPOINTS =============

@validation_bp.route('/validate-field', methods=['POST'])
@ajax_required
def validate_field():
    """
    Tek bir alanı doğrula
    
    Request JSON:
    {
        "field": "email",
        "value": "test@example.com",
        "type": "email",
        "required": true,
        "min_length": 5,
        ...
    }
    
    Response JSON:
    {
        "valid": true/false,
        "errors": ["Hata mesajı"] or [],
        "field": "email"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'valid': False,
                'errors': ['Geçersiz istek'],
                'field': None
            }), 400
        
        field_name = data.get('field', '')
        value = data.get('value', '')
        field_type = data.get('type', 'text')
        
        # Ek parametreler
        params = {
            'required': data.get('required', False),
            'min_length': data.get('min_length') or data.get('minLength'),
            'max_length': data.get('max_length') or data.get('maxLength'),
            'min_val': data.get('min_val') or data.get('min'),
            'max_val': data.get('max_val') or data.get('max'),
            'pattern': data.get('pattern'),
        }
        
        is_valid, error_message = ServerValidator.validate_field(
            field_name, value, field_type, **params
        )
        
        return jsonify({
            'valid': is_valid,
            'errors': [error_message] if error_message else [],
            'field': field_name
        })
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'errors': ['Sunucu hatası: ' + str(e)],
            'field': None
        }), 500


@validation_bp.route('/validate-form', methods=['POST'])
@ajax_required
def validate_form():
    """
    Tüm formu doğrula
    
    Request JSON:
    {
        "fields": {
            "email": {"value": "test@example.com", "type": "email", "required": true},
            "phone": {"value": "5551234567", "type": "tel", "required": false},
            ...
        }
    }
    
    Response JSON:
    {
        "valid": true/false,
        "errors": {
            "email": ["Hata mesajı"],
            "phone": ["Hata mesajı"]
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'fields' not in data:
            return jsonify({
                'valid': False,
                'errors': {'_form': ['Geçersiz istek']}
            }), 400
        
        all_errors = {}
        is_form_valid = True
        
        for field_name, field_data in data['fields'].items():
            value = field_data.get('value', '')
            field_type = field_data.get('type', 'text')
            
            params = {
                'required': field_data.get('required', False),
                'min_length': field_data.get('min_length'),
                'max_length': field_data.get('max_length'),
                'min_val': field_data.get('min_val'),
                'max_val': field_data.get('max_val'),
                'pattern': field_data.get('pattern'),
            }
            
            is_valid, error_message = ServerValidator.validate_field(
                field_name, value, field_type, **params
            )
            
            if not is_valid:
                is_form_valid = False
                all_errors[field_name] = [error_message]
        
        return jsonify({
            'valid': is_form_valid,
            'errors': all_errors
        })
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'errors': {'_form': ['Sunucu hatası: ' + str(e)]}
        }), 500


@validation_bp.route('/check-unique', methods=['POST'])
@ajax_required
def check_unique():
    """
    Benzersizlik kontrolü (email, kullanıcı adı vb.)
    Bu endpoint'i kendi modelinize göre özelleştirin
    
    Request JSON:
    {
        "field": "email",
        "value": "test@example.com",
        "model": "User",
        "exclude_id": 123  # Güncelleme durumunda mevcut kaydı hariç tut
    }
    """
    try:
        data = request.get_json()
        
        field = data.get('field')
        value = data.get('value')
        model_name = data.get('model')
        exclude_id = data.get('exclude_id')
        
        # ÖNEMLİ: Bu kısmı kendi model yapınıza göre düzenleyin
        # Örnek:
        # from models import User
        # exists = User.query.filter_by(email=value).first()
        # if exclude_id:
        #     exists = User.query.filter(User.email == value, User.id != exclude_id).first()
        
        # Şimdilik demo yanıt
        is_unique = True  # Gerçek kontrolü burada yapın
        
        return jsonify({
            'valid': is_unique,
            'errors': [] if is_unique else [f'Bu {field} zaten kullanılıyor'],
            'field': field
        })
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'errors': ['Kontrol yapılamadı'],
            'field': None
        }), 500