# app/services/license_client.py

from datetime import datetime
from flask import current_app
# Ana uygulamanın modellerini kullanıyoruz
from app.models.master import License, Tenant, User
from app.extensions import db

class LicenseClient:
    """
    Doğrudan Veritabanı Tabanlı Lisans Kontrolü
    (Dosya veya HTTP isteği kullanmaz)
    """
    
    def __init__(self):
        pass

    def check_license(self, tenant_id):
        """
        Verilen firmanın lisans durumunu ve limitlerini kontrol eder.
        
        Dönüş:
            {
                'valid': True/False,
                'reason': '...',
                'limits': { 'max_users': 5, ... }
            }
        """
        if not tenant_id:
            return {'valid': False, 'reason': 'Firma seçilmedi'}

        try:
            # 1. Veritabanından Aktif Lisansı Bul
            #    Hem tenant_id'si tutan hem de 'is_active=True' olan kaydı çek
            license_record = License.query.filter_by(
                tenant_id=tenant_id, 
                is_active=True
            ).first()

            if not license_record:
                return {'valid': False, 'reason': 'Aktif lisans bulunamadı'}

            # 2. Tarih Kontrolü
            now = datetime.now() # UTC yerine yerel saat kullanıyorsan dikkat et
            if license_record.valid_until and license_record.valid_until < now:
                return {'valid': False, 'reason': 'Lisans süresi dolmuş'}

            # 3. Limitleri Hazırla
            limits = {
                'max_users': license_record.max_users,
                'max_branches': license_record.max_branches,
                'type': license_record.license_type,
                'valid_until': license_record.valid_until.strftime('%Y-%m-%d')
            }

            return {
                'valid': True,
                'data': limits  # Standart yapıya uyması için 'data' içinde dönüyoruz
            }

        except Exception as e:
            print(f"❌ Lisans DB Hatası: {e}")
            return {'valid': False, 'reason': 'Lisans kontrol edilemedi (DB Hatası)'}

    def check_user_limit(self, tenant_id):
        """
        Kullanıcı limiti doldu mu?
        """
        check = self.check_license(tenant_id)
        if not check['valid']:
            return False, check['reason']
            
        max_users = check['data'].get('max_users', 0)
        
        # Mevcut kullanıcı sayısını say
        # (UserTenantRole tablosundan saymak daha doğru olurdu ama User tablosu üzerinden gidiyorsak:)
        # Buradaki sorguyu kendi model yapına göre (UserTenantRole vs) özelleştirebilirsin.
        try:
            # Örnek: Bu tenanta bağlı aktif kullanıcı sayısı
            from app.models.master import UserTenantRole
            current_count = UserTenantRole.query.filter_by(tenant_id=tenant_id).count()
            
            # Not: Eğer süper admin vs sayılmayacaksa filtreye ekle
            
            if current_count >= max_users:
                 return False, f"Kullanıcı limiti dolu! (Mevcut: {current_count}, Max: {max_users})"
                 
            return True, "Uygun"
            
        except Exception as e:
             return False, f"Limit kontrol hatası: {e}"