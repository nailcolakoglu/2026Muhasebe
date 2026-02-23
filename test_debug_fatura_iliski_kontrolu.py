# test_debug_fatura_iliski_kontrolu.py
# DEBUG: Fatura İlişki Kontrolü
# flask shell


from app.modules.fatura.models import Fatura
from app.extensions import get_tenant_db
from flask import session
from app.models.master import Tenant

# İlişki var mı kontrol et
print(hasattr(Fatura, 'sube'))
True  # ✅ Olmalı

# Relationship mapper kontrolü
from sqlalchemy.orm import class_mapper
mapper = class_mapper(Fatura)
print('sube' in [r.key for r in mapper.relationships])
True  # ✅ Olmalı

# Test query
with app.test_request_context():
    tenant = Tenant.query.first()
    session['tenant_id'] = tenant.id
    
    tenant_db = get_tenant_db()
    
    # Eager loading test
    from sqlalchemy.orm import joinedload
    
    fatura = tenant_db.query(Fatura).options(
        joinedload(Fatura.sube)
    ).first()
    
    if fatura:
        print(f"Fatura: {fatura.belge_no}")
        print(f"Şube: {fatura.sube.ad if fatura.sube else 'Yok'}")
        print(f"Şube ID: {fatura.sube_id}")