# flask shell 
# ÇÖZÜM 3: Dönemin aktif Alanını Kontrol Et

from flask import session
from app.models.master import Tenant
from app.modules.firmalar.models import Donem, Firma
from app.extensions import get_tenant_db

# Test context
with app.test_request_context():
    tenant = Tenant.query.first()
    session['tenant_id'] = tenant.id
    
    tenant_db = get_tenant_db()
    
    # Firma bul
    firma = tenant_db.query(Firma).first()
    print(f"Firma: {firma.unvan} (ID: {firma.id})")
    
    # Tüm dönemleri getir (aktif filtresi YOK)
    donemler = tenant_db.query(Donem).filter_by(firma_id=firma.id).all()
    print(f"Dönem sayısı: {len(donemler)}")
    
    for d in donemler:
        print(f"  - {d.ad} | Yıl: {d.yil} | Aktif: {d.aktif} | ID: {d.id}")