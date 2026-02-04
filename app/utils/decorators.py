# utils/decorators.py (DÜZELTİLMİŞ)

from functools import wraps
from flask import session, flash, redirect, url_for, abort, current_app, request, g
from flask_login import current_user
from app.services.license_client import LicenseClient

try:
    from app.modules.kullanici.models import Kullanici
    from app.modules.sube.models import Sube
except ImportError:
    pass

def check_license_limit(limit_type):
    """
    Lisans limitlerini kontrol eden dekoratör.
    Sadece POST işlemlerinde (yeni kayıt eklerken) denetler.
    
    Kullanım:
    @check_license_limit('users')
    def yeni_kullanici(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Sadece veri kaydederken (POST) kontrol et
            if request.method == 'POST':
                
                # 1. Lisans Bilgilerini Oku (Yerel Dosyadan)
                client = LicenseClient()
                # Hız için _load_local_license kullanıyoruz (Validate API'ye gitmez)
                status = client._load_local_license()
                
                if not status:
                    flash('Lisans doğrulanamadı. Lütfen aktivasyon yapın.', 'danger')
                    return redirect('/auth/login') # Veya aktivasyon sayfası
                
                # Limitleri al (Varsayılanlar: 1 kullanıcı, 1 şube)
                limits = status.get('limits', {})
                
                # Veritabanı bağlantısı var mı?
                if not hasattr(g, 'tenant_db') or not g.tenant_db:
                    # DB yoksa kontrol yapılamaz, geç (veya hata ver)
                    return f(*args, **kwargs)

                # ==========================================
                # KULLANICI LİMİTİ KONTROLÜ
                # ==========================================
                if limit_type == 'users':
                    max_users = int(limits.get('max_users', 1))
                    
                    # Modeli burada import et (Circular import önlemek için)
                    from models import Kullanici 
                    
                    # Aktif kullanıcı sayısını bul
                    current_count = g.tenant_db.query(Kullanici).filter_by(aktif=True).count()
                    
                    if current_count >= max_users:
                        flash(f'⚠️ Lisans Limitine Ulaşıldı! Mevcut paketinizle en fazla {max_users} kullanıcı oluşturabilirsiniz.', 'warning')
                        # Geldiği sayfaya geri gönder
                        return redirect(request.referrer or '/')

                # ==========================================
                # ŞUBE LİMİTİ KONTROLÜ
                # ==========================================
                elif limit_type == 'branches':
                    max_branches = int(limits.get('max_branches', 1))
                    
                    from app.modules.sube.models import Sube
                    current_count = g.tenant_db.query(Sube).filter_by(aktif=True).count()
                    
                    if current_count >= max_branches:
                        flash(f'⚠️ Şube Limitine Ulaşıldı! Mevcut paketinizle en fazla {max_branches} şube açabilirsiniz.', 'warning')
                        return redirect(request.referrer or '/')

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(*roles):
    """
    Rol bazlı yetkilendirme decorator'ı
    Kullanım: @role_required('admin', 'patron')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Bu sayfayı görüntülemek için giriş yapmalısınız.', 'warning')
                return redirect(url_for('auth.login'))
            
            # ✅ Yeni sistemde rol session'da
            user_role = session.get('tenant_role', 'user')
            
            if user_role not in roles:
                flash('Bu işlem için yetkiniz bulunmuyor.', 'danger')
                return abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission):
    """
    İzin bazlı yetkilendirme (Gelecekte RBAC için)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # TODO: Permission kontrolü implement edilecek
            # Şimdilik sadece login kontrolü
            if not current_user.is_authenticated:
                flash('Giriş yapmalısınız.', 'warning')
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator