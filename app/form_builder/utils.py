# utils.py

import bleach
import os
import mimetypes
from werkzeug.utils import secure_filename

# Güvenlik notu: Prodüksiyon ortamında 'python-magic' kütüphanesi yüklü olmalıdır.
# pip install python-magic (Windows için pip install python-magic-bin gerekebilir)
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

def sanitize_html(content, allow_data_attrs=True):
    """Zararlı JS kodlarını temizler, genişletilmiş HTML ve data-* desteği sunar."""
    if not content:
        return ""
        
    allowed_tags = [
        'b', 'i', 'u', 'em', 'strong', 'a', 'p', 'br', 'ul', 'li', 
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td' # İleride raporlar için tablo gerekebilir
    ]
    
    # Temel izin verilen özellikler (Senin önerdiğin yapı)
    base_allowed_attrs = {
        'a': ['href', 'title', 'target', 'rel'],  
        'img': ['src', 'alt', 'width', 'height', 'loading'],
        '*': ['class', 'id', 'style'] # Tüm etiketlerde class, id ve style serbest
    }

    # ✨ SİHİRLİ DOKUNUŞ: Bleach için Dinamik Kural Motoru
    def attr_filter(tag, name, value):
        # 1. Her tag için geçerli olanlar (class, id, style)
        if name in base_allowed_attrs.get('*', []):
            return True
            
        # 2. Tag'e özel izinler (Örn: a tag'i için href)
        if name in base_allowed_attrs.get(tag, []):
            return True
            
        # 3. YENİ: data-* wildcard desteği!
        if allow_data_attrs and name.startswith('data-'):
            return True
            
        # Bunlar dışındaki her şeyi (örn: onclick, onmouseover) acımasızca sil!
        return False

    return bleach.clean(
        str(content), 
        tags=allowed_tags, 
        attributes=attr_filter, # Sözlük yerine yukarıdaki akıllı motoru verdik!
        protocols=['http', 'https', 'mailto', 'data'] # img src="data:image..." base64 desteği için 'data' eklendi
    )
    
# İzin verilen MIME tipleri (Magic Bytes kontrolü için)
ALLOWED_MIMES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/plain'],
    'video': ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
    'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg']
}

def validate_file_security(file_storage, allowed_types=None, max_size_mb=10):
    """
    Dosya güvenliğini 3 aşamada kontrol eder:
    1.Dosya boyutu
    2.Dosya uzantısı (secure_filename sonrası)
    3.MIME Type (Magic Bytes - İçerik Kontrolü)
    """
    if not file_storage:
        return False, "Dosya yok."

    # 1.Dosya Adı Güvenliği
    filename = secure_filename(file_storage.filename)
    if not filename:
        return False, "Geçersiz dosya adı."

    # 2.Boyut Kontrolü
    file_storage.seek(0, os.SEEK_END)
    file_size_mb = file_storage.tell() / (1024 * 1024)
    file_storage.seek(0) # Dosyayı okumak için başa sar
    
    if file_size_mb > max_size_mb:
        return False, f"Dosya boyutu çok büyük.(Max: {max_size_mb}MB)"

    # 3.Uzantı ve Tip Kontrolü
    if allowed_types:
        # İzin verilen türleri set haline getir
        target_types = [allowed_types] if isinstance(allowed_types, str) else allowed_types
        
        # A) Magic Bytes ile İçerik Kontrolü (En Güvenli Yöntem)
        if HAS_MAGIC:
            # Dosyanın başından 2048 byte oku
            header = file_storage.read(2048)
            file_storage.seek(0) # Başa sar
            
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_buffer(header)
            
            is_mime_valid = False
            for t in target_types:
                if detected_mime in ALLOWED_MIMES.get(t, []):
                    is_mime_valid = True
                    break
            
            if not is_mime_valid:
                return False, f"Geçersiz dosya formatı.(Algılanan: {detected_mime})"
        else:
            # Fallback: Magic yüklü değilse uzantıya bak (Daha az güvenli ama çalışır)
            print("UYARI: python-magic yüklü değil, sadece uzantı kontrolü yapılıyor.")
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            # (Burada basit uzantı kontrolü mantığı devam edebilir...)

    return True, filename