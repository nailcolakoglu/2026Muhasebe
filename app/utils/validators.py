# app/utils/validators.py
"""
Güvenlik Validatorları
SQL Injection, XSS ve diğer saldırı korumaları
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Güvenlik validation metodları"""
    
    # ============================================
    # REGEX PATTERN'LERİ
    # ============================================
    
    # Tenant/Database adı: Sadece harf, rakam, underscore
    DB_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')
    
    # UUID formatı
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    # Email formatı (basit)
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    # SQL Injection blacklist
    SQL_INJECTION_PATTERNS = [
        r'(\bDROP\b)',
        r'(\bDELETE\b)',
        r'(\bTRUNCATE\b)',
        r'(\bEXEC\b)',
        r'(\bUNION\b)',
        r'(--)',
        r'(;)',
        r'(\bOR\b\s+1\s*=\s*1)',
        r'(\'\s*OR\s*\')',
        r'(\bAND\b\s+1\s*=\s*1)',
    ]
    
    
    # ============================================
    # TENANT/DATABASE VALİDASYON
    # ============================================
    
    @staticmethod
    def validate_db_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Database/Tenant adı güvenlik kontrolü
        
        Args:
            name (str): Database veya tenant adı
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        
        Kurallar:
            - Sadece harf, rakam, underscore
            - Min 3, max 64 karakter
            - Sayı ile başlamamalı
            - SQL keyword'leri içermemeli
        """
        if not name:
            return False, "Database adı boş olamaz"
        
        # 1. Uzunluk kontrolü
        if len(name) < 3:
            return False, "Database adı minimum 3 karakter olmalı"
        
        if len(name) > 64:
            return False, "Database adı maksimum 64 karakter olabilir"
        
        # 2. Format kontrolü (sadece alphanumeric + underscore)
        if not SecurityValidator.DB_NAME_PATTERN.match(name):
            logger.warning(f"⚠️ Geçersiz database adı karakterleri: {name}")
            return False, "Database adı sadece harf, rakam ve _ içerebilir"
        
        # 3. Sayı ile başlama kontrolü
        if name[0].isdigit():
            return False, "Database adı sayı ile başlayamaz"
        
        # 4. SQL keyword kontrolü
        sql_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'CREATE', 'ALTER', 
                       'EXEC', 'EXECUTE', 'UNION', 'SELECT', 'INSERT']
        
        name_upper = name.upper()
        for keyword in sql_keywords:
            if keyword in name_upper:
                logger.error(f"❌ SQL keyword algılandı: {name} (keyword: {keyword})")
                return False, f"Database adı '{keyword}' içeremez"
        
        # 5. ✅ Geçerli
        return True, None
    
    
    @staticmethod
    def validate_tenant_code(code: str) -> Tuple[bool, Optional[str]]:
        """
        Tenant kodu güvenlik kontrolü
        
        Args:
            code (str): Tenant kodu
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        
        Kurallar:
            - Sadece harf, rakam, tire, underscore
            - Min 2, max 20 karakter
            - Büyük harf zorunlu değil ama öneriliyor
        """
        if not code:
            return False, "Tenant kodu boş olamaz"
        
        # 1. Uzunluk kontrolü
        if len(code) < 2:
            return False, "Tenant kodu minimum 2 karakter olmalı"
        
        if len(code) > 20:
            return False, "Tenant kodu maksimum 20 karakter olabilir"
        
        # 2. Format kontrolü (harf, rakam, tire, underscore)
        if not re.match(r'^[a-zA-Z0-9_-]+$', code):
            return False, "Tenant kodu sadece harf, rakam, - ve _ içerebilir"
        
        # 3. SQL injection kontrolü
        for pattern in SecurityValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                logger.error(f"❌ SQL injection denemesi: {code}")
                return False, "Geçersiz tenant kodu"
        
        # 4. ✅ Geçerli
        return True, None
    
    
    @staticmethod
    def validate_uuid(uuid_str: str) -> Tuple[bool, Optional[str]]:
        """
        UUID format kontrolü
        
        Args:
            uuid_str (str): UUID string
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not uuid_str:
            return False, "UUID boş olamaz"
        
        if not SecurityValidator.UUID_PATTERN.match(uuid_str):
            logger.warning(f"⚠️ Geçersiz UUID formatı: {uuid_str}")
            return False, "Geçersiz UUID formatı"
        
        return True, None
    
    
    # ============================================
    # SQL INJECTION KONTROLÜ
    # ============================================
    
    @staticmethod
    def check_sql_injection(text: str) -> bool:
        """
        SQL injection denemesi var mı?
        
        Args:
            text (str): Kontrol edilecek metin
        
        Returns:
            bool: SQL injection tespit edildi mi?
        """
        if not text:
            return False
        
        for pattern in SecurityValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.error(f"❌ SQL injection algılandı: {text}")
                return True
        
        return False
    
    
    @staticmethod
    def sanitize_input(text: str, max_length: int = 255) -> str:
        """
        Kullanıcı girdisini temizle
        
        Args:
            text (str): Temizlenecek metin
            max_length (int): Maksimum uzunluk
        
        Returns:
            str: Temizlenmiş metin
        """
        if not text:
            return ""
        
        # 1. Strip whitespace
        text = text.strip()
        
        # 2. Uzunluk kontrolü
        if len(text) > max_length:
            text = text[:max_length]
        
        # 3. HTML encode (XSS koruması)
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        
        # 4. SQL escape (basit)
        text = text.replace("'", "''")  # Single quote escape
        
        return text
    
    
    # ============================================
    # EMAIL VALİDASYON
    # ============================================
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """
        Email format kontrol��
        
        Args:
            email (str): Email adresi
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not email:
            return False, "Email boş olamaz"
        
        if not SecurityValidator.EMAIL_PATTERN.match(email):
            return False, "Geçersiz email formatı"
        
        if len(email) > 120:
            return False, "Email maksimum 120 karakter olabilir"
        
        return True, None