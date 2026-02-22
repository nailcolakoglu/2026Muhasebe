# app/modules/fatura/ocr_routes.py
"""
Fatura OCR HTTP Route Layer
Upload + Parse + Preview + Save
"""

import os
import logging
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_babel import gettext as _
from werkzeug.utils import secure_filename

from app.modules.ai_destek.ocr_service import ocr_service
from app.decorators import tenant_route, permission_required
from app.extensions import db

from app.utils.file_validator import FileValidator

logger = logging.getLogger(__name__)

# Blueprint
fatura_ocr_bp = Blueprint('fatura_ocr', __name__, url_prefix='/fatura/ocr')

# Upload ayarları
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'tiff', 'tif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ========================================
# UPLOAD EKRANI (UI)
# ========================================
@fatura_ocr_bp.route('/upload', methods=['GET'])
@login_required
@tenant_route
@permission_required('fatura_create')
def upload_page():
    """
    Fatura OCR Upload Ekranı
    """
    return render_template('fatura/upload_ocr.html',
                         title=_('Fatura OCR - Görsel Yükleme'),
                         ocr_active=ocr_service.is_active)


# ========================================
# OCR PARSE (AJAX)
# ========================================
@fatura_ocr_bp.route('/parse', methods=['POST'])
@login_required
@tenant_route
@permission_required('fatura_create')
def parse_fatura():
    """
    Yüklenen fatura görselini OCR ile parse eder
    
    Request:
        - file: Fatura görseli (multipart/form-data)
        - fatura_turu: 'satis' veya 'alis'
    
    Response:
        JSON: Parse edilmiş fatura verisi
    """
    file = request.files.get('file')
    
    # ✅ Güvenli validasyon
    validation = FileValidator.validate_file(
        file,
        allowed_extensions={'.jpg', '.jpeg', '.png', '.pdf', '.tiff', '.tif'},
        max_size=10 * 1024 * 1024
    )
    
    if not validation['valid']:
        return jsonify({'success': False, 'error': validation['error']}), 400
    if not ocr_service.is_active:
        return jsonify({
            'success': False,
            'error': 'OCR servisi aktif değil. GEMINI_API_KEY kontrol edin.'
        }), 503
    
    # Dosya kontrolü
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Dosya yüklenmedi'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Dosya seçilmedi'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': f'Geçersiz dosya formatı. İzin verilenler: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    # Dosya boyutu kontrolü
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'success': False,
            'error': f'Dosya çok büyük. Maksimum: {MAX_FILE_SIZE // (1024*1024)}MB'
        }), 400
    
    try:
        # Fatura türü
        fatura_turu = request.form.get('fatura_turu', 'satis')
        
        logger.info(f"📸 OCR Parse başlatıldı: {file.filename} (Tür: {fatura_turu})")
        
        # OCR işlemi
        result = ocr_service.fatura_gorselden_oku(file, fatura_turu)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['data'],
                'confidence': result.get('confidence', 0.0),
                'model': result.get('model', 'unknown'),
                'message': _('Fatura başarıyla okundu!')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Bilinmeyen hata'),
                'raw_text': result.get('raw_text', '')
            }), 500
    
    except Exception as e:
        logger.error(f"❌ OCR Parse Hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================
# FATURA KAYDET (OCR Sonucunu DB'ye)
# ========================================
@fatura_ocr_bp.route('/save', methods=['POST'])
@login_required
@tenant_route
@permission_required('fatura_create')
def save_ocr_fatura():
    """
    OCR'dan gelen parse edilmiş veriyi Fatura olarak kaydeder
    
    Request Body (JSON):
        - ocr_data: Parse edilmiş fatura verisi
    
    Response:
        JSON: Kaydedilen fatura bilgisi
    """
    try:
        ocr_data = request.get_json()
        
        if not ocr_data:
            return jsonify({'success': False, 'error': 'Veri gönderilmedi'}), 400
        
        # Faturayı kaydet
        result = ocr_service.fatura_onayla_ve_kaydet(
            ocr_data=ocr_data,
            firma_id=current_user.firma_id,
            kullanici_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'fatura_id': result['fatura_id'],
                'belge_no': result['belge_no'],
                'message': _('Fatura başarıyla kaydedildi!'),
                'redirect_url': url_for('fatura.duzenle', id=result['fatura_id'])
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Kaydetme hatası')
            }), 500
    
    except Exception as e:
        logger.error(f"❌ Fatura Kaydetme Hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================
# OCR DURUMU (Health Check)
# ========================================
@fatura_ocr_bp.route('/status', methods=['GET'])
@login_required
def ocr_status():
    """
    OCR servisinin durumunu kontrol eder
    """
    return jsonify({
        'active': ocr_service.is_active,
        'model': ocr_service.vision_model._model_name if ocr_service.is_active else None,
        'api_key_set': bool(ocr_service.api_key)
    })