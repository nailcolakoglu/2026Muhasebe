# app/utils/file_validator.py (YENİ DOSYA)
"""
File Upload Security Validator
MIME type ve content kontrolü
"""

import os
import magic  # python-magic
from werkzeug.utils import secure_filename
from flask import current_app
import logging

logger = logging.getLogger(__name__)


class FileValidator:
    """
    Güvenli dosya yükleme validatörü
    """
    
    # İzin verilen MIME type'lar
    ALLOWED_MIMES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/tiff': ['.tiff', '.tif'],
        'application/pdf': ['.pdf'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
        'application/vnd.ms-excel': ['.xls'],
    }
    
    @staticmethod
    def validate_file(file, allowed_extensions=None, max_size=None):
        """
        Dosyayı kapsamlı kontrol eder
        
        Args:
            file: FileStorage object
            allowed_extensions: İzin verilen uzantılar (set)
            max_size: Maksimum boyut (bytes)
        
        Returns:
            dict: {'valid': bool, 'error': str, 'safe_filename': str}
        """
        result = {'valid': False, 'error': None, 'safe_filename': None}
        
        # 1. Dosya var mı?
        if not file or file.filename == '':
            result['error'] = 'Dosya seçilmedi'
            return result
        
        # 2. Güvenli dosya adı oluştur
        safe_name = secure_filename(file.filename)
        if not safe_name:
            result['error'] = 'Geçersiz dosya adı'
            return result
        
        result['safe_filename'] = safe_name
        
        # 3. Uzantı kontrolü
        file_ext = os.path.splitext(safe_name)[1].lower()
        
        if allowed_extensions and file_ext not in allowed_extensions:
            result['error'] = f'Geçersiz dosya formatı. İzin verilenler: {", ".join(allowed_extensions)}'
            return result
        
        # 4. Dosya boyutu kontrolü
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        max_size = max_size or current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        
        if file_size > max_size:
            result['error'] = f'Dosya çok büyük. Maksimum: {max_size // (1024*1024)}MB'
            return result
        
        # 5. MIME type kontrolü (gerçek dosya içeriği)
        try:
            mime_type = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)
            
            # MIME type izin verilen listede mi?
            if mime_type not in FileValidator.ALLOWED_MIMES:
                result['error'] = f'Desteklenmeyen dosya tipi: {mime_type}'
                return result
            
            # MIME type ile uzantı uyumlu mu?
            expected_extensions = FileValidator.ALLOWED_MIMES[mime_type]
            if file_ext not in expected_extensions:
                result['error'] = (
                    f'Dosya uzantısı ({file_ext}) içerikle uyumsuz. '
                    f'Beklenen: {", ".join(expected_extensions)}'
                )
                return result
            
        except Exception as e:
            logger.error(f"❌ MIME type kontrolü hatası: {e}")
            result['error'] = 'Dosya içeriği doğrulanamadı'
            return result
        
        # ✅ Tüm kontroller başarılı
        result['valid'] = True
        logger.info(f"✅ Dosya doğrulandı: {safe_name} ({file_size} bytes, {mime_type})")
        
        return result


# Kullanım örneği:
"""
from app.utils.file_validator import FileValidator

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    
    validation = FileValidator.validate_file(
        file,
        allowed_extensions={'.jpg', '.png', '.pdf'},
        max_size=10 * 1024 * 1024  # 10MB
    )
    
    if not validation['valid']:
        return jsonify({'error': validation['error']}), 400
    
    # Güvenli dosya adı kullan
    filename = validation['safe_filename']
    file.save(os.path.join(UPLOAD_FOLDER, filename))
"""