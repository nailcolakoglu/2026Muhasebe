# app.py (Final Fix: SessionService Heartbeat Update)
# app.py (Final: Caching, Performance & Full Blueprints)

import os
import sys
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv 
load_dotenv()

from flask import Flask, render_template, redirect, url_for, flash, session, request, g
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from flask_login import current_user, logout_user
from flask_migrate import Migrate
from sqlalchemy import text

# ---------------------------------------------------------
# PATH AYARLARI
# ---------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------
# İMPORTLAR
# ---------------------------------------------------------
from app.context_processors import inject_global_vars
from app.config import Config
from app.extensions import db, init_extensions, login_manager, get_tenant_db, cache # 👈 CACHE EKLENDİ

# Servisler
from app.services.license_client import LicenseClient
from app.services.session_service import SessionService

# Firebird Yamaları
from app.patches import apply_firebird_patches
apply_firebird_patches()

# Modeller
from app.modules.kullanici.models import Kullanici
from app.models.master import User, Tenant, UserTenantRole, License, MasterActiveSession
from app.araclar import sayiyi_yaziya_cevir

def create_app():
    """Flask uygulamasını oluştur"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Extensions Başlat
    init_extensions(app)
    
    # ---------------------------------------------------------
    # VERİTABANI İLK KURULUM (Sadece Master Tablolar)
    # ---------------------------------------------------------
    with app.app_context():
        try:
            # Gerekli tabloları oluştur
            User.__table__.create(db.engine, checkfirst=True)
            Tenant.__table__.create(db.engine, checkfirst=True)
            UserTenantRole.__table__.create(db.engine, checkfirst=True)
            License.__table__.create(db.engine, checkfirst=True)
            MasterActiveSession.__table__.create(db.engine, checkfirst=True)
        except Exception as e:
            print(f"⚠️ Tablo doğrulama uyarısı: {e}")

    # Jinja Filtreleri
    app.jinja_env.globals.update(abs=abs)
    app.jinja_env.filters['yaziyla'] = sayiyi_yaziya_cevir
    
    csrf = CSRFProtect(app)
    
    # Babel (Dil Desteği)
    def get_locale():
        if current_user.is_authenticated and hasattr(current_user, 'dil_tercihi'):
            return current_user.dil_tercihi
        return request.accept_languages.best_match(Config.BABEL_SUPPORTED_LOCALES)
    
    babel = Babel(app, locale_selector=get_locale)
    
    # Context Processor: Menü (Cache destekli MenuManager)
    @app.context_processor
    def inject_menu():
        try:
            from app.form_builder.menu_manager import MenuManager
            # MenuManager zaten kendi içinde cache kullanıyor
            menu = MenuManager.get_tree()
            return dict(dynamic_menu=menu)
        except Exception:
            return dict(dynamic_menu=[])

    @app.template_filter('enum_value')
    def enum_value_filter(value):
        return value.value if hasattr(value, 'value') else value
    
    # ---------------------------------------------------------
    # 1. MIDDLEWARE: GLOBAL CONTEXT (PERFORMANS İYİLEŞTİRMELİ)
    # ---------------------------------------------------------
    @app.before_request
    def load_global_context():
        """
        Her istekte çalışan ana fonksiyon.
        Caching mekanizması ile veritabanı yükünü azaltır.
        """
        # Bypass listesi
        exempt_endpoints = ['auth.login', 'auth.logout', 'static', 'setup', 'activation.activate']
        if request.endpoint in exempt_endpoints or any(request.path.startswith(p) for p in ['/static', '/auth', '/activate']):
            return None

        # Global değişkenleri sıfırla
        g.tenant = None
        g.firma = None 
        g.donem = None
        g.sube = None
        g.bolge = None
        
        # Login Kontrolü
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        # -----------------------------------------------------
        # C) HEARTBEAT (NABIZ) KONTROLÜ
        # -----------------------------------------------------
        # Güvenlik nedeniyle bunu cache'lemiyoruz, her an atılabilmeli.
        if session.get('tenant_id') and session.get('_session_token'):
            is_valid_session = SessionService.heartbeat()
            if not is_valid_session:
                SessionService.logout() 
                logout_user()          
                session.clear()
                flash("Güvenlik: Oturumunuz zaman aşımına uğradı.", "warning")
                return redirect(url_for('auth.login'))
        
        elif session.get('tenant_id') and not session.get('_session_token'):
            logout_user()
            session.clear()
            return redirect(url_for('auth.login'))

        # -----------------------------------------------------
        # D) TENANT BELİRLEME (CACHE DESTEKLİ) 🚀
        # -----------------------------------------------------
        tenant_id = session.get('tenant_id')
        
        if not tenant_id:
            # DB'den rol sorgusunu önbelleğe alalım (5 dakika)
            # Cache Key: user_default_tenant_{user_id}
            cache_key = f"user_default_tenant_{current_user.id}"
            role_data = cache.get(cache_key)

            if not role_data:
                try:
                    role = UserTenantRole.query.filter_by(user_id=current_user.id, is_default=True).first()
                    if not role:
                        role = UserTenantRole.query.filter_by(user_id=current_user.id).first()
                    
                    if role:
                        role_data = {'tenant_id': role.tenant_id, 'role': role.role}
                        cache.set(cache_key, role_data, timeout=300) # 5 dk sakla
                except Exception as e:
                    print(f"⚠️ Rol getirme hatası: {e}")

            if role_data:
                tenant_id = role_data['tenant_id']
                session['tenant_id'] = tenant_id
                session['tenant_role'] = role_data['role']
            else:
                flash("Hesabınıza tanımlı bir firma bulunamadı.", "warning")
                return redirect(url_for('auth.login'))

        # -----------------------------------------------------
        # E) LİSANS KONTROLÜ (CACHE DESTEKLİ) 🚀
        # -----------------------------------------------------
        if tenant_id:
            # Her istekte API/DB'ye gitmek yerine CACHE'e soruyoruz.
            # 10 dakikada bir kontrol eder.
            license_cache_key = f"license_check_{tenant_id}"
            license_valid = cache.get(license_cache_key) # True/False döner

            if license_valid is None:
                # Cache'te yoksa mecburen API/DB kontrolü yap
                try:
                    client = LicenseClient()
                    status = client.check_license(tenant_id)
                    
                    if not status['valid']:
                        if status.get('reason') == 'Aktif lisans bulunamadı':
                             return redirect(url_for('activation.activate'))
                        g.license_error = status.get('reason')
                        # Hatalıysa cache'e atma, düzelince hemen algılasın
                    else:
                        # Geçerliyse 10 dakika boyunca bir daha sorma
                        cache.set(license_cache_key, True, timeout=600)
                except Exception as e:
                    print(f"⚠️ Lisans kontrol hatası: {e}")

        # -----------------------------------------------------
        # F) FIREBIRD CONTEXT (CACHE DESTEKLİ) 🚀
        # -----------------------------------------------------
        # Kullanıcının hangi firmada/dönemde olduğu bilgisi
        
        try:
            tenant_db = get_tenant_db()
            if tenant_db:
                # Cache Key: fb_context_{tenant_id}_{user_email}
                fb_cache_key = f"fb_context_{tenant_id}_{current_user.email}"
                fb_context = cache.get(fb_cache_key)

                if not fb_context:
                    # Cache Miss: DB'ye git
                    from app.modules.firmalar.models import Firma, Donem
                    from app.modules.kullanici.models import Kullanici
                    
                    fb_user = tenant_db.query(Kullanici).filter_by(email=current_user.email).first()
                    
                    context_data = {'firma_id': None, 'donem_id': None, 'user_id': None}
                    
                    if fb_user:
                        context_data['user_id'] = fb_user.id
                        if fb_user.firma_id:
                            context_data['firma_id'] = fb_user.firma_id
                            
                        # Aktif dönem (varsayılan)
                        aktif_donem = tenant_db.query(Donem).filter_by(aktif=True).first()
                        if aktif_donem:
                            context_data['donem_id'] = aktif_donem.id
                    
                    cache.set(fb_cache_key, context_data, timeout=300) # 5 dk
                    fb_context = context_data

                # Cache'ten gelen veriyi Global'e (g) yükle
                g.fb_user_id = fb_context.get('user_id')
                
                # Session'da override varsa onu kullan (kullanıcı değiştirdiyse), yoksa cache'tekini
                active_firma_id = session.get('aktif_firma_id') or fb_context.get('firma_id')
                active_donem_id = session.get('aktif_donem_id') or fb_context.get('donem_id')
                active_sube_id = session.get('aktif_sube_id') # Şube ID'sini Session'dan al
                
                # Firma nesnesini yükle (SQLAlchemy Identity Map zaten bunu hızlı yapar)
                if active_firma_id:
                    from app.modules.firmalar.models import Firma
                    g.firma = tenant_db.query(Firma).get(active_firma_id)
                
                if active_donem_id:
                    from app.modules.firmalar.models import Donem
                    g.donem = tenant_db.query(Donem).get(active_donem_id)

                if active_sube_id:
                    from app.modules.sube.models import Sube
                    g.sube = tenant_db.query(Sube).get(active_sube_id)
                else:
                    g.sube = None # Seçili değilse boşalt (Tüm Şubeler modu)
        
        except Exception as e:
            print(f"⚠️ Firebird Context Hatası: {e}")    
        
    # ---------------------------------------------------------
    # 2. TEMPLATE GLOBAL DEĞİŞKENLERİ
    # ---------------------------------------------------------
    app.context_processor(inject_global_vars)
    
    # ---------------------------------------------------------
    # 3. BLUEPRINT KAYITLARI (TAM LİSTE)
    # ---------------------------------------------------------
    register_blueprints(app)
    
    # Setup Route
    @app.route('/setup')
    def setup():
        try:
            if User.query.filter_by(email='admin@test.com').first():
                flash('✅ Kurulum zaten tamamlanmış.', 'info')
                return redirect('/auth/login')
            
            user = User(id=str(uuid.uuid4()), email='admin@test.com', full_name='Admin User', is_active=True, is_superadmin=True)
            user.set_password('123456')
            db.session.add(user)
            
            tenant = Tenant(id=str(uuid.uuid4()), kod='TEST-01', unvan='Test Firma A.Ş.', db_name='TEST.FDB', vergi_no='0000000000', is_active=True)
            tenant.set_db_password('masterkey')
            db.session.add(tenant)
            
            license = License(id=str(uuid.uuid4()), tenant_id=tenant.id, license_type='trial', valid_from=datetime.now(), valid_until=datetime.utcnow() + timedelta(days=30), max_users=5, is_active=True)
            license.generate_license_key()
            db.session.add(license)
            
            role = UserTenantRole(id=str(uuid.uuid4()), user_id=user.id, tenant_id=tenant.id, role='admin', is_default=True, is_active=True)
            db.session.add(role)
            
            db.session.commit()
            flash('✅ Kurulum başarılı! admin@test.com / 123456', 'success')
            return redirect('/auth/login')
            
        except Exception as e: 
            db.session.rollback()
            return f"<h1>❌ Kurulum Hatası</h1><pre>{str(e)}</pre>"
    
    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e): return render_template('500.html'), 500
    
    return app


def register_blueprints(app):
    """Tüm modülleri (Blueprints) kaydet"""
    
    # Modül Listesi (Eksiksiz)
    blueprints = [
        ('app.modules.auth.routes', 'auth_bp', '/auth'),
        ('app.modules.main.routes', 'main_bp', ''),
        ('app.modules.rapor.routes', 'rapor_bp','/rapor'),
        ('app.modules.firmalar.routes', 'firmalar_bp', '/firmalar'),
        ('app.modules.cari.routes', 'cari_bp', '/cari'),
        ('app.modules.depo.routes', 'depo_bp', '/depo'),
        ('app.modules.sube.routes', 'sube_bp', '/sube'),
        ('app.modules.kategori.routes', 'kategori_bp', '/kategori'),
        ('app.modules.kullanici.routes', 'kullanici_bp', '/kullanici'),
        ('app.modules.banka.routes', 'banka_bp', '/banka'),
        ('app.modules.kasa.routes', 'kasa_bp', '/kasa'),
        ('app.modules.stok.routes', 'stok_bp', '/stok'),
        ('app.modules.cek.routes', 'cek_bp', '/cek'),
        ('app.modules.muhasebe.routes', 'muhasebe_bp', '/muhasebe'),
        ('app.modules.fatura.routes', 'fatura_bp', '/fatura'),
        ('app.modules.stok_fisi.routes', 'stok_fisi_bp', '/stok-fisi'),
        ('app.modules.banka_hareket.routes', 'banka_hareket_bp', '/banka-hareket'),
        ('app.modules.kasa_hareket.routes', 'kasa_hareket_bp', '/kasa-hareket'),
        ('app.modules.siparis.routes', 'siparis_bp', '/siparis'),
        ('app.modules.mobile.routes', 'mobile_bp', '/mobile'),
        ('app.modules.finans.routes', 'finans_bp', '/finans'),
        ('app.modules.efatura.routes', 'efatura_bp', '/efatura'),
        ('app.modules.doviz.routes', 'doviz_bp', '/doviz'),
        ('app.modules.lokasyon.routes', 'lokasyon_bp', '/lokasyon'),
        ('app.modules.fiyat.routes', 'fiyat_bp', '/fiyat'),
        ('app.modules.sistem.routes', 'sistem_bp', '/sistem'),
        ('app.modules.bolge.routes', 'bolge_bp', '/bolge'),
        ('app.modules.banka_import.routes', 'banka_import_bp', '/banka-import'),
        ('app.modules.irsaliye.routes', 'irsaliye_bp', '/irsaliye')
    ]

    for module_path, bp_name, url_prefix in blueprints:
        try:
            module = __import__(module_path, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            
            # API Blueprintleri için CSRF muafiyeti
            if bp_name == 'api_bp':
                from app.extensions import csrf
                csrf.exempt(blueprint)
                
        except Exception as e:
            print(f"❌ {bp_name} YÜKLENEMEDİ: {e}")

    # Aktivasyon Modülü
    try:
        from app.modules.activation.routes import activation_bp
        app.register_blueprint(activation_bp)
    except Exception as e:
        print(f"⚠️ Aktivasyon Modülü Yüklenemedi: {e}")
    

if __name__ == '__main__':
    app = create_app()
    
    print("\n" + "="*60)
    print("🚀 MULTI-TENANT ERP BAŞLATILIYOR")
    print("="*60)
    print(f"📂 Master DB: {Config.MASTER_DB_PATH}")
    print(f"🌐 Login: http://localhost:5000/auth/login")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', debug=True, port=5000)