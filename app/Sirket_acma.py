from app import create_app
from extensions import db
from models.master import Tenant, User, UserTenantRole, License
from datetime import datetime, timedelta
import uuid

app = create_app()

with app.app_context():
    user = User.query.filter_by(email='admin@test.com').first()
    
    tenant_a = Tenant(id=str(uuid.uuid4()),kod='FIRMA-A', unvan='Firma A Ticaret Ltd.Şti.', db_name='FIRMA_A.FDB', vergi_no='1234567890', is_active=True )
    tenant_a.set_db_password('masterkey')
    db.session.add(tenant_a)
    db.session.flush()
    
    license_a = License(id=str(uuid.uuid4()), tenant_id=tenant_a.id, license_type='professional', valid_until=datetime.utcnow() + timedelta(days=365),      max_users=10,is_active=True    )
    db.session.add(license_a)
    
    role_a = UserTenantRole(id=str(uuid.uuid4()), user_id=user.id, tenant_id=tenant_a.id, role='admin', is_default=False,is_active=True )
    db.session.add(role_a)
    
    db.session.commit()
    print("✅ Firma A eklendi!")

exit()