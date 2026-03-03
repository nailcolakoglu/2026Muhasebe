# app/modules/eirsaliye/routes.py

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _
import logging
from app.decorators import tenant_route, permission_required
from app.modules.eirsaliye.tasks import send_eirsaliye_async

logger = logging.getLogger(__name__)
eirsaliye_bp = Blueprint('eirsaliye', __name__, url_prefix='/eirsaliye')

@eirsaliye_bp.route('/gonder/<string:irsaliye_id>', methods=['POST'])
@login_required
@tenant_route
@permission_required('irsaliye_gonder')
def gonder(irsaliye_id):
    try:
        # Doğrudan asenkron Celery görevini tetikliyoruz
        send_eirsaliye_async.delay(str(irsaliye_id), str(current_user.firma_id))
        return jsonify({'success': True, 'message': 'E-İrsaliye arka planda GİB\'e iletilmek üzere kuyruğa alındı!'})
    except Exception as e:
        logger.error(f"E-İrsaliye Kuyruk Hatası: {str(e)}")
        return jsonify({'success': False, 'message': _("Görev kuyruğa alınırken hata oluştu.")}), 500