# celery_worker.py

from run import app
from app.extensions import celery

# Celery'nin veritabanına erişebilmesi için Flask uygulamasının context'ini içeri aktarıyoruz
app.app_context().push()