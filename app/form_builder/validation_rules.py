# form_builder/validation_rules.py

from flask_babel import lazy_gettext as _l
from enum import Enum
import re
from datetime import datetime
from typing import Tuple, Optional, Any
from .field_types import FieldType

class ValidationRule(Enum):
    REQUIRED = "required"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    NUMBER_RANGE = "number_range"
    LENGTH = "length"
    PATTERN = "pattern"
    TCKN = "tckn"
    VKN = "vkn"
    IBAN = "iban"
    PLATE = "plate"
    OTP = "otp"
    DATE = "date"
    CREDIT_CARD = "credit_card"
    IP = "ip" 
    TCKN_VKN = "tckn_vkn"


class Validator:
    """
    Merkezi Validasyon Mantığı.
    Frontend ve Backend uyumlu doğrulama algoritmaları.
    """
    
    MESSAGES = {
        'required': _l('Bu alan zorunludur.'),
        'email': _l('Geçerli bir e-posta adresi giriniz.'),
        'phone': _l('Geçerli bir telefon numarası giriniz (5xx xxx xx xx).'),
        'url': _l('Geçerli bir web adresi giriniz.'),
        'min_length': _l('En az {min} karakter olmalıdır.'),
        'max_length': _l('En fazla {max} karakter olmalıdır.'),
        'pattern': _l('Geçersiz format.'),
        'credit_card': _l('Geçersiz kredi kartı numarası.'),
        'number_range': _l('Değer {min} ile {max} arasında olmalıdır.'),
        'invalid_date': _l('Geçersiz tarih.Lütfen geçerli bir tarih giriniz.'),
        'date_future': _l('Gelecek bir tarih seçilemez.'), 
        'min_val': _l('Değer {min} veya daha büyük olmalıdır.'),
        'max_val': _l('Değer {max} veya daha küçük olmalıdır.'),
        'tckn': _l('Geçersiz TC Kimlik Numarası.'),
        'vkn': _l('Geçersiz Vergi Kimlik Numarası.'),
        'iban': _l('Geçersiz IBAN.'),
        'plate': _l('Geçersiz plaka formatı (Örn: 34 ABC 123).'),
        'otp': _l('{length} haneli doğrulama kodu giriniz.'),
        'currency': _l('Geçerli bir para değeri giriniz.'),
        'numeric': _l('Sadece rakam giriniz.'),
        'ip': _l('Geçersiz IP adresi.'),
        'tckn_vkn': _l('Geçersiz TC Kimlik veya Vergi Kimkik Numarası.')

    }

    @staticmethod
    def check(field, value) -> Tuple[bool, str]:
        """Ana validasyon kontrol noktası"""
        # None gelirse boş string yap, boşlukları temizle
        val_str = str(value).strip() if value is not None else ""

        # ============================================================
        # 1.MASKE TEMİZLİĞİ (Mask Artifact Cleaning)
        # ============================================================
        
        if field.field_type == FieldType.TEL:
            # Sadece rakamları bırak
            if not re.sub(r'\D', '', val_str): 
                val_str = ""
        
        elif field.field_type == FieldType.IBAN:
            # TR, alt çizgi ve boşlukları sil
            clean = val_str.replace('_', '').replace(' ', '').upper()
            if clean == "TR" or not clean:
                val_str = ""

        elif field.field_type == FieldType.CREDIT_CARD:
            # Sadece rakam yoksa boş say
            if not re.sub(r'\D', '', val_str):
                val_str = ""

        elif field.field_type in [FieldType.TCKN, FieldType.VKN, FieldType.TCKN_VKN]:
            # Sadece rakam yoksa boş say
            if not re.sub(r'\D', '', val_str):
                val_str = ""
        
        elif field.field_type == FieldType.TCKN or field.field_type == FieldType.VKN:
            # Sadece rakam yoksa boş say
            if not re.sub(r'\D', '', val_str):
                val_str = ""
        
        # ============================================================
        # 2.Zorunluluk Kontrolü
        # ============================================================
        if field.required:
            if not val_str and not (isinstance(value, list) and value):
                return False, Validator.MESSAGES['required']

        # ============================================================
        # 3.Boş Değer Kontrolü (Erken Çıkış)
        # ============================================================
        if not val_str and not isinstance(value, list):
            return True, ""

        # ============================================================
        # 4.Kural Bazlı Kontroller
        # ============================================================
        for rule in field.validation_rules:
            is_valid = True
            error_msg = ""

            if rule == ValidationRule.EMAIL:
                is_valid = Validator._is_email(val_str)
                error_msg = Validator.MESSAGES['email']
            
            elif rule == ValidationRule.TCKN:
                is_valid = Validator._is_tckn(val_str)
                error_msg = Validator.MESSAGES['tckn']

            elif rule == ValidationRule.VKN:
                is_valid = Validator._is_vkn(val_str)
                error_msg = Validator.MESSAGES['vkn']

            elif rule == ValidationRule.IBAN:
                is_valid = Validator._is_iban(val_str)
                error_msg = Validator.MESSAGES['iban']

            elif rule == ValidationRule.TCKN_VKN:
                is_valid = Validator._is_tckn_or_vkn(val_str)
                error_msg = Validator.MESSAGES.get('tckn_vkn', 'Geçersiz TC Kimlik veya Vergi Numarası.')

            elif rule == ValidationRule.PHONE:
                is_valid = Validator._is_phone(val_str)
                error_msg = Validator.MESSAGES['phone']
            
            elif rule == ValidationRule.PLATE:
                is_valid = Validator._is_plate(val_str)
                error_msg = Validator.MESSAGES['plate']

            elif rule == ValidationRule.CREDIT_CARD:
                is_valid = Validator._is_luhn(val_str)
                error_msg = Validator.MESSAGES['credit_card']

            elif rule == ValidationRule.IP:
                is_valid = Validator._is_ip(val_str)
                error_msg = Validator.MESSAGES['ip']

            elif rule == ValidationRule.LENGTH:
                is_valid = Validator._check_length(val_str, field.min_length, field.max_length)
                if not is_valid:
                    if field.min_length and len(val_str) < field.min_length:
                        error_msg = Validator.MESSAGES['min_length'].format(min=field.min_length)
                    else:
                        error_msg = Validator.MESSAGES['max_length'].format(max=field.max_length)
            
            elif rule == ValidationRule.NUMBER_RANGE:
                is_valid = Validator._check_range(val_str, field.min_val, field.max_val)
                error_msg = Validator.MESSAGES['number_range'].format(min=field.min_val, max=field.max_val or '∞')

            elif rule == ValidationRule.PATTERN:
                if field.pattern and not re.match(field.pattern, val_str):
                    is_valid = False
                    error_msg = Validator.MESSAGES['pattern']

            elif rule == ValidationRule.DATE:
                is_valid = Validator._is_date(val_str, field.field_type)
                error_msg = Validator.MESSAGES['invalid_date']
            
            elif rule == ValidationRule.OTP:
                length = int(field.html_attributes.get('data-otp-length', 6)) if field.html_attributes else 6
                if not (len(val_str) == length and val_str.isdigit()):
                    is_valid = False
                    error_msg = Validator.MESSAGES['otp'].format(length=length)

            if not is_valid:
                return False, error_msg

        return True, ""

    # ============================================================
    # YARDIMCI ALGORİTMALAR
    # ============================================================

    @staticmethod
    def _is_email(value: str) -> bool:
        """Email validasyonu"""
        return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value) is not None

    @staticmethod
    def _is_phone(val: str) -> bool:
        """
        Türkiye telefon numarası validasyonu
        Geliştirilmiş: 5 ile başlama, 0 ve 90 ön ek temizleme
        """
        # Sadece rakamları al
        clean = re.sub(r'\D', '', val)
        
        # 0 ile başlıyorsa kaldır (0532 -> 532)
        if clean.startswith('0'):
            clean = clean[1:]
        
        # 90 ile başlıyorsa kaldır (+90 532 -> 532)
        if clean.startswith('90'):
            clean = clean[2:]
        
        # 10 hane ve 5 ile başlamalı
        return len(clean) == 10 and clean.startswith('5')

    @staticmethod
    def _is_plate(val: str) -> bool:
        """Türkiye plaka validasyonu"""
        val = val.replace(' ', '').upper()
        # 01-81 arası il kodu + 1-3 harf + 2-4 rakam
        return re.match(r'^(0[1-9]|[1-7][0-9]|8[01])[A-Z]{1,3}\d{2,4}$', val) is not None
    
    @staticmethod
    def _check_length(value: str, min_len: Optional[int], max_len: Optional[int]) -> bool:
        """Karakter uzunluğu kontrolü"""
        val_len = len(value)
        if min_len and val_len < min_len: 
            return False
        if max_len and val_len > max_len: 
            return False
        return True

    @staticmethod
    def _check_range(value: str, min_val: Optional[float], max_val: Optional[float]) -> bool:
        """Sayısal değer aralığı kontrolü"""
        if min_val is None and max_val is None: 
            return True
        try:
            # Para birimi temizliği (1.000,50 -> 1000.50)
            clean_val = value.replace('.', '').replace(',', '.')
            val = float(clean_val)
            
            if min_val is not None and val < min_val: 
                return False
            if max_val is not None and val > max_val: 
                return False
            return True
        except:
            return True 

    @staticmethod
    def _is_date(value: str, field_type: FieldType) -> bool:
        """Tarih formatı validasyonu"""
        if not value: 
            return True
        try:
            if field_type == FieldType.DATE:
                datetime.strptime(value, '%Y-%m-%d')
            elif field_type == FieldType.TARIH:
                datetime.strptime(value, '%d.%m.%Y')
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_tckn(val: str) -> bool:
        """
        TC Kimlik Numarası validasyonu (Tam algoritma)
        - 11 hane
        - 0 ile başlamaz
        - 10.hane: (1,3,5,7,9.hanelerin toplamı * 7 - 2,4,6,8.hanelerin toplamı) mod 10
        - 11.hane: İlk 10 hanenin toplamı mod 10
        """
        if not val.isdigit() or len(val) != 11 or val[0] == '0': 
            return False
        
        d = [int(c) for c in val]
        
        # 10.hane kontrolü
        d10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
        
        # 11.hane kontrolü
        d11 = sum(d[:10]) % 10
        
        return d[9] == d10 and d[10] == d11

    @staticmethod
    def _is_vkn(val: str) -> bool:
        """
        Vergi Kimlik Numarası validasyonu (Tam algoritma)
        - 10 hane
        - Son hane kontrol hanesi (Luhn benzeri algoritma)
        """
        if not val.isdigit() or len(val) != 10: 
            return False
        
        d = [int(c) for c in val]
        total = 0
        
        for i in range(9):
            t = (d[i] + (9 - i)) % 10
            p = (t * pow(2, 9 - i)) % 9 if t != 0 else 0
            if t != 0 and p == 0: 
                p = 9
            total += p
        
        return (10 - (total % 10)) % 10 == d[9]
    
    @staticmethod
    def _is_luhn(val: str) -> bool:
        """
        Luhn algoritması (Kredi kartı validasyonu)
        """
        s = re.sub(r'\D', '', val)
        if len(s) < 13: 
            return False
        
        sum_val = 0
        double = False
        
        for c in reversed(s):
            digit = int(c)
            if double:
                digit *= 2
                if digit > 9: 
                    digit -= 9
            sum_val += digit
            double = not double
        
        return (sum_val % 10) == 0

    @staticmethod
    def _is_iban(val: str) -> bool:
        """
        IBAN validasyonu (Mod-97 algoritması)
        - TR ile başlar
        - 26 karakter
        - Mod-97 kontrolü
        """
        iban = val.replace(' ', '').upper()
        
        if not iban.startswith('TR') or len(iban) != 26: 
            return False
        
        # IBAN'ı sona al (TR26...-> ...TR26)
        moved = iban[4:] + iban[:4]
        
        # Harfleri sayıya çevir (A=10, B=11, ..., Z=35)
        num_str = ''
        for c in moved:
            if c.isdigit(): 
                num_str += c
            else: 
                num_str += str(ord(c) - 55)
        
        try:
            # Mod-97 kontrolü
            return int(num_str) % 97 == 1
        except:
            return False
    
    @staticmethod
    def _is_ip(val: str) -> bool:
        """
        IP adresi validasyonu (IPv4)
        Örnek: 192.168.1.1
        """
        pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return re.match(pattern, val) is not None

    @staticmethod
    def _is_tckn_or_vkn(val: str) -> bool:
        """Değer 10 haneyse VKN, 11 haneyse TCKN kontrolü yapar."""
        if not val.isdigit(): return False
        
        if len(val) == 10:
            return Validator._is_vkn(val)
        elif len(val) == 11:
            return Validator._is_tckn(val)
        
        return False
