# app/utils/csrf_helpers.py (YENİ DOSYA)
"""
CSRF Token Helpers
AJAX route'ları için CSRF koruması
"""

from functools import wraps
from flask import request, jsonify, current_app
from flask_wtf.csrf import CSRFProtect, CSRFError
import logging

logger = logging.getLogger(__name__)

csrf = CSRFProtect()


def csrf_protect_api(f):
    """
    API route'ları için CSRF decorator
    AJAX isteklerinde X-CSRFToken header'ı kontrol eder
    
    Usage:
        @app.route('/api/fatura', methods=['POST'])
        @csrf_protect_api
        def create_fatura():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Test modunda bypass
        if current_app.config.get('TESTING'):
            return f(*args, **kwargs)
        
        # CSRF token kontrolü
        token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        
        if not token:
            logger.warning(f"⚠️ CSRF token eksik: {request.endpoint}")
            return jsonify({
                'success': False,
                'error': 'CSRF token eksik'
            }), 403
        
        try:
            csrf.protect()
        except CSRFError as e:
            logger.error(f"❌ CSRF validation hatası: {e}")
            return jsonify({
                'success': False,
                'error': 'Geçersiz CSRF token'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


# app.py içinde ekle:
def create_app():
    # ...
    csrf.init_app(app)
    
    # Error handler
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        logger.error(f"CSRF Error: {e.description}")
        
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'CSRF token hatası'
            }), 403
        
        flash('Güvenlik hatası. Sayfayı yenileyin.', 'error')
        return redirect(request.referrer or url_for('main.index'))