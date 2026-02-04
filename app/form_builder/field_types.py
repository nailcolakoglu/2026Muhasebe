"""
Form Field Types Enum
Desteklenen tüm alan tipleri
"""

from enum import Enum


class FieldType(Enum):
    """Form alanı tipleri - Delphi TFieldType benzeri"""
    
    # Temel Input'lar
    TEXT = "text"
    EMAIL = "email"
    PASSWORD = "password"
    NUMBER = "number"
    TEL = "tel"
    
    # Tarih ve Zaman
    DATE = "date"                   # Native HTML5 date input (YYYY-MM-DD)
    TARIH = "tarih"                 # TR formatında text-based tarih (DD.MM.YYYY)
    DATETIME = "datetime"
    TIME = "time"
    MONTH = "month"
    WEEK = "week"
    
    # Metin Alanları
    TEXTAREA = "textarea"
    RICHTEXT = "richtext"
    
    # Seçim Alanları
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    
    # Modern Web Input'ları
    URL = "url"
    COLOR = "color"
    RANGE = "range"
    RANGE_DUAL = "range-dual"
    FILE = "file"
    SEARCH = "search"
    BUTTON = "button"               # Buton alanı
    
    # Özel Field'lar
    CURRENCY = "currency"           # Para birimi girişi
    RATING = "rating"               # Yıldız puanlama
    SWITCH = "switch"               # Toggle switch
    IMAGE = "image"                 # Resim yükleme (file + preview)
    TAGS = "tags"                   # Etiket girişi
    FILES = "files"                 # Çoklu dosya yükleme (drag&drop)
    SIGNATURE = "signature"         # İmza alanı (canvas)
    JSON_EDITOR = "json"            # JSON düzenleyici
    
    # TR Özel Alanlar
    TCKN = "tckn"                   # Türkiye Cumhuriyeti Kimlik No
    IBAN = "iban"                   # TR IBAN
    VKN = "vkn"                     # Vergi Kimlik No (10 hane)
    DATE_RANGE = "date-range"       # Tarih Aralığı (başlangıç-bitiş)
    
    # Doğrulama
    OTP = "otp"                     # 6 haneli doğrulama kodu (kutucuklar)
    PLATE = "plate"                 # TR Araç Plakası
    
    # Harita
    MAP_POINT = "map_point"         # Harita üzerinden tek nokta seçimi
    
    # Barkod/QR Kod
    BARCODE = "barcode"             # QR/Barkod okuyucu (kamera ile)
    # YENİ EKLEMELER:
    AUTOCOMPLETE = "autocomplete"   # Ajax ile dinamik arama
    SLIDER = "slider"               # noUiSlider ile tek değer
    DATE_TIME_RANGE = "datetime_range"  # Tarih+Saat aralığı
    GEOLOCATION = "geolocation"     # Cihazdan konum alma (GPS)
    AUDIO_RECORDER = "audio"        # Ses kaydı
    VIDEO_RECORDER = "video"        # Video kaydı
    DRAWING = "drawing"             # Çizim alanı (fabric.js)
    COLOR_PICKER_ADVANCED = "color_advanced"  # Gradient/palette
    MARKDOWN = "markdown"           # Markdown editör
    CODE_EDITOR = "code"            # Monaco/CodeMirror
    CAPTCHA = "captcha"             # reCAPTCHA/hCaptcha
    MASK = "mask"                   # İsteğe bağlı maskeli input 
    
    CALC = "calc"                   # Basit hesap makinesi
    
    HIDDEN = "hidden" 
    
    IP = "ip"                       # IP Adresi (IPv4)
    CREDIT_CARD = "credit_card"     # Kredi Kartı (Luhn Algoritması) 
    MASTER_DETAIL = "master_detail" # Fatura satırları gibi dinamik tablo yapısı

    MULTI_FIELD = "multi_field"
    HTML = "html"
    MODAL = "modal"  
    SCRIPT = "script"  
    # --- YENİ EKLENENLER ---
    HR = "hr"         # Ayırıcı Çizgi
    HEADER = "header" # Ara Başlık (H1-H6)
    
    AUTO_NUMBER = "auto_number" # <-- YENİ EKLENEN


    TCKN_VKN ="tckn_vkn"

