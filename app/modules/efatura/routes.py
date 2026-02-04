from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from app.modules.fatura.models import Fatura
from .services import EntegratorService

efatura_bp = Blueprint('efatura', __name__)

@efatura_bp.route('/gonder/<int:fatura_id>', methods=['POST'])
@login_required
def gonder(fatura_id):
    try:
        service = EntegratorService(current_user.firma_id)
        basari, mesaj = service.fatura_gonder(fatura_id)
        
        if basari:
            return jsonify({'success': True, 'message': mesaj})
        else:
            return jsonify({'success': False, 'message': mesaj})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@efatura_bp.route('/durum/<int:fatura_id>', methods=['POST'])
@login_required
def durum(fatura_id):
    try:
        service = EntegratorService(current_user.firma_id)
        basari, mesaj = service.durum_sorgula(fatura_id)
        return jsonify({'success': basari, 'message': mesaj})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500