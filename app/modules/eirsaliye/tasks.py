# app/modules/eirsaliye/tasks.py

import logging
from flask import session
from app.extensions import celery

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def send_eirsaliye_async(self, irsaliye_id, firma_id):
    from run import app 
    from app.modules.eirsaliye.services import EIrsaliyeService
    
    try:
        with app.test_request_context():
            session['tenant_id'] = firma_id 
            session['aktif_firma_id'] = firma_id 
            
            service = EIrsaliyeService(firma_id)
            basari, mesaj = service.irsaliye_gonder(irsaliye_id)
            
            if not basari:
                logger.warning(f"Asenkron E-İrsaliye hatası: {mesaj}")
                raise self.retry(countdown=60 * (self.request.retries + 1)) 
            return mesaj
    except Exception as e:
        logger.error(f"Celery Task E-İrsaliye Hatası: {str(e)}")
        raise