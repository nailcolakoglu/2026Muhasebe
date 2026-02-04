# models/master/__init__.py

"""
Master DB Modelleri (SQLite)

- User: Kullanıcılar
- UserTenantRole: Kullanıcı-Firma-Rol ilişkisi
- Tenant:  Firmalar (Multi-tenant)
- License: Lisanslar
- AuditLog: Güvenlik logları
"""

from app.models.master.user import User, UserTenantRole
from app.models.master.tenant import Tenant
from app.models.master.license import License
from app.models.master.audit import AuditLog
from app.models.master.backup_config import BackupConfig
from app.models.master.master_active_session import MasterActiveSession

__all__ = ['User', 'UserTenantRole', 'Tenant', 'License', 'AuditLog', 'BackupConfig', 'MasterActiveSession']