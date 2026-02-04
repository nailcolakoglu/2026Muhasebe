# supervisor/services/license_service.py

import uuid
import secrets
import string
import sys
import os
from datetime import datetime, timedelta
from flask import current_app

# =========================================================
# 1. PATH AYARLARI (IMPORTLARDAN ÖNCE)
# =========================================================
# Bu dosya: supervisor/services/license_service.py konumundadır.
current_dir = os.path.dirname(os.path.abspath(__file__))
supervisor_dir = os.path.dirname(current_dir)     # supervisor/
project_root = os.path.dirname(supervisor_dir)    # root/ (Proje Ana Dizini)

# Ana proje kök dizinini path'e ekle ki 'app' modülü sorunsuz bulunsun
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# =========================================================
# 2. DOĞRU DB NESNESİ (KRİTİK DÜZELTME)
# =========================================================
# 🚨 ESKİSİ: from extensions import db
# ✅ YENİSİ: Ana uygulamanın (başlatılmış olan) db nesnesi
from app.extensions import db 

# Config
try:
    from supervisor_config import SupervisorConfig
except ImportError:
    # Fallback
    from config import SupervisorConfig

# =========================================================
# 3. MODELLER
# =========================================================
# Supervisor'a özgü modeller
# (Not: Bu modellerin içinde de 'from app.extensions import db' kullanıldığından emin olun)
from models.license_extended import LicenseExtended
from models.audit import AuditLog
from models.notification import Notification

# Master Modeller (Güvenli Import)
try:
    from app.models.master import License, Tenant
except ImportError:
    print("❌ LicenseService: Master modeller yüklenemedi!")
    # Kodun çökmemesi için dummy sınıflar
    class License: pass
    class Tenant: pass

class LicenseService:
    
    @staticmethod
    def generate_license_key():
        """
        Okunabilir, güvenli lisans anahtarı üretir.
        Format: XXXX-YYYY-ZZZZ-WWWW
        """
        alphabet = string.ascii_uppercase + string.digits
        key_parts = [
            ''.join(secrets.choice(alphabet) for _ in range(4))
            for _ in range(4)
        ]
        return '-'.join(key_parts)

    @staticmethod
    def create_license(data, user):
        """
        Yeni lisans oluşturur (Transaction güvenli)
        
        Args:
            data (dict): Form verileri
            user (Supervisor): İşlemi yapan yönetici
        """
        # Session başlatılmış mı kontrolü (Debug için)
        # if not current_app.extensions['sqlalchemy'].db: ...
        
        try:
            # 1. Transaction Başlat
            tenant_id = data.get('tenant_id')
            license_type = data.get('license_type')
            
            # Eski aktif lisansları pasife çek
            # (Aynı Tenant ID için aktif olanları kapat)
            License.query.filter_by(
                tenant_id=tenant_id, 
                is_active=True
            ).update({'is_active': False})
            
            # 2. Anahtar ve Limitler
            key = LicenseService.generate_license_key()
            duration = int(data.get('duration_days', 365))
            valid_until = datetime.utcnow() + timedelta(days=duration)
            
            # Config'den limitleri al (Override edilmediyse)
            # SupervisorConfig.LICENSE_TYPES dict yapısında olmayabilir, kontrol et
            config = {}
            if hasattr(SupervisorConfig, 'LICENSE_TYPES'):
                config = SupervisorConfig.LICENSE_TYPES.get(license_type, {})
                
            max_users = data.get('max_users') or config.get('max_users', 5)
            max_branches = config.get('max_branches', 1)
            
            # 3. Master License Kaydı Oluştur
            license_id = str(uuid.uuid4())
            new_license = License(
                id=license_id,
                tenant_id=tenant_id,
                license_key=key,
                license_type=license_type,
                valid_from=datetime.utcnow(),
                valid_until=valid_until,
                max_users=max_users,
                max_branches=max_branches,
                is_active=True,
                created_by=user.id if hasattr(user, 'id') else 'system'
            )
            db.session.add(new_license)
            
            # 4. Extended License Kaydı (Ekstra Bilgiler)
            extended = LicenseExtended(
                id=license_id,
                monthly_fee=float(data.get('monthly_fee', 0)),
                billing_cycle=data.get('billing_cycle', 'monthly'),
                notes=data.get('notes', '')
            )
            db.session.add(extended)
            
            # 5. Audit Log ve Bildirim
            tenant = Tenant.query.get(tenant_id)
            tenant_unvan = tenant.unvan if tenant else "Bilinmeyen Firma"
            
            # Log
            try:
                AuditLog.log(
                    action='license.create',
                    supervisor=user,
                    resource_type='license',
                    resource_id=license_id,
                    description=f'{tenant_unvan} için {license_type.upper()} lisansı oluşturuldu.',
                    status='success'
                )
            except Exception as log_err:
                print(f"⚠️ Log hatası: {log_err}")

            # Bildirim
            try:
                Notification.create(
                    supervisor_id=user.id,
                    tenant_id=tenant_id,
                    type='success',
                    category='license',
                    title='Yeni Lisans Oluşturuldu',
                    message=f"{tenant_unvan} firmasına {license_type} lisansı tanımlandı."
                )
            except Exception as notif_err:
                print(f"⚠️ Bildirim hatası: {notif_err}")
            
            # 6. İşlemi Onayla (Commit)
            db.session.commit()
            
            return {'success': True, 'license_id': license_id, 'message': 'Lisans başarıyla oluşturuldu.'}
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Lisans Oluşturma Hatası: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': str(e)}

    @staticmethod
    def renew_license(license_id, days, user):
        """Lisans süresini uzatır"""
        try:
            lic = License.query.get(license_id)
            if not lic:
                return {'success': False, 'message': 'Lisans bulunamadı.'}
                
            old_date = lic.valid_until
            
            # Eğer zaten süresi dolmuşsa bugünden itibaren ekle, 
            # dolmamışsa bitiş tarihinin üstüne ekle.
            now = datetime.utcnow()
            if lic.valid_until < now:
                base_date = now
            else:
                base_date = lic.valid_until
                
            lic.valid_until = base_date + timedelta(days=days)
            lic.is_active = True # Süresi dolmuşsa tekrar aktif et
            
            # Audit Log
            try:
                AuditLog.log(
                    action='license.renew',
                    supervisor=user,
                    resource_type='license',
                    resource_id=lic.id,
                    description=f'Lisans {days} gün uzatıldı.',
                    changes={'old': str(old_date), 'new': str(lic.valid_until)},
                    status='success'
                )
            except:
                pass
            
            db.session.commit()
            return {'success': True, 'message': f'Lisans {days} gün uzatıldı.'}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}