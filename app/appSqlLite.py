# app.py (DÜZELTİLMİŞ - MINIMAL VERSİYON)

import os
import sys

from dotenv import load_dotenv 
load_dotenv()
from datetime import datetime
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from flask_login import current_user
from flask_migrate import Migrate
from sqlalchemy import text
from services.license_client import LicenseClient

# Proje kök dizinini tanıt
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from app.config import Config  # ✅ Harici config kullan

# Firebird yamaları
from patches import apply_firebird_patches
apply_firebird_patches()

# Modeller
from app.modules.kullanici.models import Kullanici
#from app.modules.sube.models import Sube
#from app.modules.firmalar.models import Donem




# Araçlar
from app.araclar import sayiyi_yaziya_cevir
from app.form_builder.menu_manager import MenuManager
from app.modules.bolge.models import init_default_data
from flask import Flask, render_template, redirect, url_for, flash, session, request, g
from app.extensions import db, init_extensions, login_manager, get_tenant_db
from app.models.master import User, Tenant, UserTenantRole, License, MasterActiveSession
# ✅ MasterActiveSession modelini buraya ekle:

from datetime import datetime, timedelta
import uuid

def create_app():
    """Flask uygulamasını oluştur"""
    app = Flask(__name__)
    
    # ✅ Config yükle (harici config.py'den)
    app.config.from_object(Config)
    
    # ✅ Extensions başlat (tek seferlik - extensions.py içinde)
    init_extensions(app)
    # migrate = Migrate(app, db)
    # ✅ Master DB tablolarını oluştur (ilk çalıştırmada)
    with app.app_context():
        # Sadece 'master' bind anahtarına sahip tabloları oluştur
        # db.create_all(bind_key='master') 
        # print(f"✅ Master Database Tabloları Güncellendi: {Config.MASTER_DB_PATH}")
        # db.create_all()
        # 🚨 KRİTİK DÜZELTME:
        # 'db.create_all()' tüm tabloları (Şube, Şehir vs.) MySQL'e basmaya çalışır.
        # Biz sadece Master tablolarını (User, Tenant, License) mühürlemek istiyoruz.
        
        from app.models.master import User, Tenant, UserTenantRole, License, MasterActiveSession
        
        # Sadece bu modellerin tablolarını oluştur (Diğer modüllere dokunma)
        # Bu sayede 'subeler.sehir_id' hatası almazsın çünkü Şube tablosu MySQL'de oluşmaz.
        User.__table__.create(db.engine, checkfirst=True)
        Tenant.__table__.create(db.engine, checkfirst=True)
        UserTenantRole.__table__.create(db.engine, checkfirst=True)
        License.__table__.create(db.engine, checkfirst=True)
        MasterActiveSession.__table__.create(db.engine, checkfirst=True)

        print(f"✅ Master Management Tabloları MySQL'de doğrulandı.")


        print(f"✅ Master Database:  {Config.MASTER_DB_PATH}")
    
    # Jinja yardımcıları
    app.jinja_env.globals.update(abs=abs)
    app.jinja_env.filters['yaziyla'] = sayiyi_yaziya_cevir
    
    # CSRF koruması
    csrf = CSRFProtect(app)
    
    """
    # ✅ User loader (Master DB için)
    @login_manager.user_loader
    def load_user(user_id):
        if user_id is None or user_id == 'None':
            return None
            
        uid_str = str(user_id)
        
        # 1. Master DB (SQLite) - UUID Kontrolü
        if "-" in uid_str or len(uid_str) > 20:
            from models.master import User
            return db.session.get(User, uid_str)
        
        # 2. Firebird (Tenant DB) - Integer Kontrolü
        if uid_str.isdigit():
            # Artık get_tenant_db yukarıda import edildiği için hata vermez
            tenant_db = get_tenant_db() 
            if tenant_db:
                from models import Kullanici
                return tenant_db.query(Kullanici).get(int(user_id))
        
        return None
    """
    # Babel
    def get_locale():
        if current_user.is_authenticated and hasattr(current_user, 'dil_tercihi'):
            return current_user.dil_tercihi
        return request.accept_languages.best_match(Config.BABEL_SUPPORTED_LOCALES)
    
    babel = Babel(app, locale_selector=get_locale)
    
    # Context processors
    @app.context_processor
    def inject_menu():
        """Menü enjeksiyonu (güvenli)"""
        try:
            from form_builder.menu_manager import MenuManager
            menu = MenuManager.get_tree()
            return dict(dynamic_menu=menu)
        except Exception as e:
            # Hata olursa boş menü dön
            print(f"⚠️  Menu yükleme hatası: {e}")
            return dict(dynamic_menu=[])

    @app.template_filter('enum_value')
    def enum_value_filter(value):
        return value.value if hasattr(value, 'value') else value
    
    @app.before_request
    def check_app_license():
        """
        Her istekten önce lisansı kontrol et.
        """
        # Hata ayıklama (Gerekirse açın)
        # print(f"🔍 Yol: {request.path} | Endpoint: {request.endpoint}")

        current_path = request.path
        
        # ==========================================
        # 1. GEÇİŞ İZİNLERİ (WHITELIST)
        # ==========================================
        
        # Statik dosyalar
        if current_path.startswith('/static'):
            return

        # Aktivasyon Sayfası (Kritik)
        if current_path.startswith('/activate'):
            return
            
        # 👇 BU KISIM ÇOK ÖNEMLİ: Auth (Login/Logout) serbest olmalı
        if current_path.startswith('/auth'):
            return

        # Setup sayfası (İlk kurulum için gerekebilir)
        if current_path.startswith('/setup'):
            return

        # ==========================================
        # 2. LİSANS KONTROLÜ
        # ==========================================
        try:
            from services.license_client import LicenseClient
            client = LicenseClient()
            status = client.check_license()
            
            # Lisans geçersizse Aktivasyona yönlendir
            if not status['valid']:
                return redirect(url_for('activation.activate'))
                
        except Exception as e:
            print(f"⚠️ Lisans Hatası: {e}")
            return redirect(url_for('activation.activate'))        
        # DİKKAT ELDEN GEÇİR KONTROL ET.
        # Lisans geçerliyse global değişkenlere limitleri atabiliriz
        # g.license_limits = status['data']['limits']
    
    # Global context (middleware)
    @app.before_request
    def load_global_context():
        """
        Global Context (Middleware)
        
        Holding Modeli:
        1.Tenant seçimi (Master DB'den)
        2.Firma seçimi (Firebird'den - Holding içinde)
        3.Dönem seçimi (Aktif dönem)
        4.Şube seçimi (Kullanıcı rolüne göre)
        5.Bölge seçimi (Bölge müdürü için)
        6.Global Context (Middleware) - Session Kurtarma Özellikli
        """
        # Global değişkenleri sıfırla
        # 1. İstisna Yolları (Bypass)
        exempt_endpoints = ['auth.login', 'auth.logout', 'static', 'activation.activate', 'setup']
        if request.endpoint in exempt_endpoints or any(request.path.startswith(p) for p in ['/static', '/auth/login', '/auth/logout', '/activate']):
            return None

        # g nesnesindeki değerleri başlat (AttributeError: firma hatasını önlemek için)
        g.tenant = g.firma = g.donem = g.sube = g.bolge = None

        # 2. Lisans Kontrolü (Loglarda True olduğu görüldü)
        from services.license_client import LicenseClient
        client = LicenseClient()
        status = client.check_license()
        
        if not status or not status.get('valid'):
            return redirect(url_for('activation.activate'))

        # 3. Session Recovery (Lisanstan Session'a veri aktarımı)
        if not session.get('tenant_id'):
            data = status.get('data', {})
            session['tenant_id'] = data.get('tenant_id')
            session['db_name'] = data.get('db_name')
            session['db_password'] = data.get('db_password')
            session.modified = True

        # 4. Giriş Kontrolü
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        # 5. FIREBIRD VERİLERİNİ YÜKLE (Kritik Nokta)
        try:
            tenant_db = get_tenant_db() # Globalden geliyor
            if tenant_db:
                from models import Firma, Donem
                
                # SQLAlchemy 2.0 uyumlu (LegacyAPIWarning hatasını önler)
                firma_id = session.get('active_firma_id')
                if firma_id:
                    # g.firma = tenant_db.query(Firma).get(firma_id) yerine:
                    g.firma = tenant_db.query(Firma).filter_by(id=firma_id).first()
                else:
                    g.firma = tenant_db.query(Firma).filter_by(aktif=True).first()
                
                # Aynı mantık donem için:
                donem_id = session.get('active_donem_id')
                if donem_id:
                    g.donem = tenant_db.query(Donem).filter_by(id=donem_id).first()
                else:
                    g.donem = tenant_db.query(Donem).filter_by(aktif=True).first()
        except Exception as e:
            print(f"⚠️ Context Hatası: {e}")            
            # Hata olsa bile g.firma=None kalır, routes.py'de 'if not g.firma' kontrolü çalışır.

        if current_user.is_authenticated:
            tenant_db = get_tenant_db() # Firebird bağlantısı
            if tenant_db:
                # 1. Lisanstaki limiti oku
                lic_client = LicenseClient()
                l_status = lic_client._load_local_license()
                max_users = l_status.get('limits', {}).get('max_users', 1)
                print("Lisandaki Kullanıcı Sayısı : ", max_users)
                # 2. Firebird'deki aktif kullanıcı sayısını say
                # (Aynı kullanıcı farklı cihazdan giriyorsa 1 sayar)
                active_count = tenant_db.execute(text(
                    "SELECT COUNT(DISTINCT KULLANICI_ID) FROM AKTIF_OTURUMLAR WHERE SON_ISLEM > :t"
                ), {'t': datetime.now() - timedelta(minutes=15)}).scalar()

                # 3. Kendi oturumumuz var mı?
                is_already_in = tenant_db.execute(text(
                    "SELECT 1 FROM AKTIF_OTURUMLAR WHERE KULLANICI_ID = :uid"
                ), {'uid': current_user.id}).first()

                # 4. LİMİT KONTROLÜ: Eğer 1 kişilik lisans varsa ve başkası içerideyse
                if active_count >= max_users and not is_already_in:
                    from flask_login import logout_user
                    logout_user()
                    session.clear()
                    flash(f"Lisans limitiniz ({max_users} kişi) dolmuştur.", "danger")
                    return redirect(url_for('auth.login'))

                # 5. MASTER DB KAYDI (Monitoring için)
                # Eğer Master DB kaydı yoksa oluştur, varsa vaktini güncelle
                try:
                    # Önce bu session_id ile bir kayıt var mı kontrol et
                    s_id = session.get('_id') or session.sid if hasattr(session, 'sid') else str(uuid.uuid4()) #
                    
                    master_session = MasterActiveSession.query.filter_by(session_id=s_id).first() #
                    
                    if master_session:
                        # Varsa sadece son aktivasyon zamanını güncelle
                        master_session.last_activity = datetime.now() #
                        master_session.user_id = current_user.id #
                        master_session.tenant_id = session.get('tenant_id') #
                    else:
                        # Yoksa yeni kayıt oluştur
                        new_m_session = MasterActiveSession(
                            tenant_id=session.get('tenant_id'),
                            user_id=current_user.id,
                            session_id=s_id,
                            login_at=datetime.now(), #
                            last_activity=datetime.now() #
                        )
                        db.session.add(new_m_session) #
                    
                    db.session.commit() # Master DB (SQLite)
                except Exception as master_e:
                    db.session.rollback()
                    print(f"⚠️ Master Session Güncelleme Hatası: {master_e}")
            

        # Kullanıcı sayısını bulma
        if current_user.is_authenticated:
            tenant_db = get_tenant_db()
            if not tenant_db:
                return

            try:
                # 1. TEMİZLİK: Son 15 dakikadır işlem yapmayan oturumları 'ölü' say ve sil
                limit_vakti = datetime.now() - timedelta(minutes=15)
                tenant_db.execute(
                    text("DELETE FROM AKTIF_OTURUMLAR WHERE SON_ISLEM < :limit"),
                    {'limit': limit_vakti}
                )

                # 2. LİMİT KONTROLÜ
                # Lisans dosyasındaki max_users bilgisini al
                lic_client = LicenseClient()
                l_status = lic_client._load_local_license()
                max_allowed = l_status.get('limits', {}).get('max_users', 1)

                # Şu anki aktif farklı kullanıcı sayısını bul
                current_active_users = tenant_db.execute(
                    text("SELECT COUNT(DISTINCT KULLANICI_ID) FROM AKTIF_OTURUMLAR")
                ).scalar()

                # Bu kullanıcı zaten bir oturum açmış mı?
                existing_session = tenant_db.execute(
                    text("SELECT 1 FROM AKTIF_OTURUMLAR WHERE KULLANICI_ID = :uid AND OTURUM_ANAHTARI = :sid"),
                    {'uid': current_user.id, 'sid': session.sid if hasattr(session, 'sid') else str(current_user.id)}
                ).first()

                # Limit dolmuşsa ve kullanıcı yeni geliyorsa içeri alma
                if current_active_users >= max_allowed and not existing_session:
                    from flask_login import logout_user
                    logout_user()
                    session.clear()
                    flash(f"Lisans limitiniz ({max_allowed} kullanıcı) dolmuştur. Lütfen bir oturumu kapatın.", "danger")
                    return redirect(url_for('auth.login'))

                # 3. KAYIT GÜNCELLEME: Kullanıcının son işlem vaktini 'UPDATE OR INSERT' ile yenile
                tenant_db.execute(
                    text("""
                        UPDATE OR INSERT INTO AKTIF_OTURUMLAR (KULLANICI_ID, OTURUM_ANAHTARI, SON_ISLEM, IP_ADRESI)
                        VALUES (:uid, :sid, :now, :ip)
                        MATCHING (KULLANICI_ID, OTURUM_ANAHTARI)
                    """),
                    {
                        'uid': current_user.id,
                        'sid': session.sid if hasattr(session, 'sid') else str(current_user.id),
                        'now': datetime.now(),
                        'ip': request.remote_addr
                    }
                )
                tenant_db.commit()

            except Exception as e:
                tenant_db.rollback()
                print(f"⚠️ Lisans Oturum Hatası: {e}")
        
    @app.context_processor
    def inject_global_vars():
        # --- LİSANS BİLGİLERİNİ ÇEK (YENİ) ---
        license_data = None
        license_days_left = 0
        
        try:
            from services.license_client import LicenseClient
            client = LicenseClient()
            # Yerel dosyayı oku (Hızlıdır, veritabanına gitmez)
            status = client._load_local_license()
            
            if status:
                license_data = status
                # Tarih formatı: YYYY-MM-DD HH:MM:SS
                valid_until_str = status.get('valid_until')
                if valid_until_str:
                    valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d %H:%M:%S')
                    license_days_left = (valid_until - datetime.now()).days
        except Exception as e:
            # Hata olursa (dosya yoksa) sessiz kal, arayüzde gösterme
            print(f"Lisans bilgisi okuma hatası: {e}")
            pass
        # -------------------------------------        
        return dict(
            aktif_tenant=g.get('tenant'),  # ✅ YENİ
            aktif_firma=g.get('firma'),    # ✅ DEĞİŞTİ
            aktif_donem=g.get('donem'),
            aktif_sube=g.get('sube'),
            aktif_bolge=g.get('bolge'),    # ✅ YENİ
            bugun=datetime.now(),
            tenant_name=session.get('tenant_name', ''),
            tenant_role=session.get('tenant_role', ''),
            license_type=session.get('license_type', ''),
            firma_id=g.get('firma_id'),     # ✅ YENİ (Template'lerde kullanılacak)

            app_license=license_data,
            license_days_left=license_days_left
        )

    
    # Blueprints kaydet
    register_blueprints(app)


    from app.modules.lokasyon.models import Sehir, Ilce  
    # Setup route
    @app.route('/setup')
    def setup():
        """İlk kurulum: Test kullanıcısı ve firma oluştur"""
        try:
            # Kullanıcı zaten var mı?
            existing_user = User.query.filter_by(email='admin@test.com').first()
            if existing_user:
                flash('✅ Kurulum zaten tamamlanmış.', 'info')
                return redirect('/auth/login')
            
            # 1.Test Kullanıcısı
            user = User(
                id=str(uuid.uuid4()),
                email='admin@test.com',
                full_name='Admin User',
                is_active=True,
                is_superadmin=True
            )
            user.set_password('123456')
            db.session.add(user)
            db.session.flush()
            
            # 2.Test Tenant
            tenant = Tenant(
                id=str(uuid.uuid4()),
                kod='TEST-01',
                unvan='Test Firma A.Ş.',
                db_name='TEST.FDB',
                vergi_no='0000000000',
                is_active=True
            )
            tenant.set_db_password('masterkey')
            db.session.add(tenant)
            db.session.flush()
            
            # 3.Lisans
            license = License(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                license_type='trial',
                valid_from=datetime.now(),
                valid_until=datetime.utcnow() + timedelta(days=30),
                max_users=5,
                is_active=True
            )
            license.generate_license_key()
            db.session.add(license)
            
            # 4.Yetki
            role = UserTenantRole(
                id=str(uuid.uuid4()),
                user_id=user.id,
                tenant_id=tenant.id,
                role='admin',
                is_default=True,
                is_active=True
            )
            db.session.add(role)
            
            # 5.Kaydet
            db.session.commit()
            
            flash('✅ Kurulum başarılı!  admin@test.com / 123456', 'success')
            return redirect('/auth/login')
            
        except Exception as e: 
            db.session.rollback()
            return f"<h1>❌ Kurulum Hatası</h1><pre>{str(e)}</pre>"
    
    # Hata yönetimi
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500
    
    # Sinyal bağlama (eski sistem için)
    try:
        from signals import siparis_faturalandi
        from app.modules.fatura.listeners import siparisten_fatura_olustur
        siparis_faturalandi.connect(siparisten_fatura_olustur)
        print("🔌 Sinyal Bağlandı: Sipariş -> Fatura")
    except: 
        pass
    
    return app


def register_blueprints(app):
    """Tüm modülleri kaydet"""
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
            
            if not hasattr(blueprint, 'name'):
                print(f"❌ {bp_name} bir Blueprint değil!")
                continue
            
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            print(f"✅ {bp_name} kaydedildi")
            if bp_name == 'api_bp':
                csrf.exempt(bp_name) # Tüm API modülünü muaf tut
        except ImportError as e:
            # 🛑 HATA GİZLEME: Detaylı bas ki hangi dosya eksik görelim
            print(f"⚠️ {bp_name} MODÜLÜ YÜKLENEMEDİ: {e}")
            # Eksik modül detayını görmek için traceback'i açabiliriz:
            # import traceback; traceback.print_exc()
            
        except Exception as e:
            print(f"❌ {bp_name} KAYIT HATASI: {e}")
            import traceback
            traceback.print_exc()

    from app.modules.activation.routes import activation_bp
    app.register_blueprint(activation_bp)
    

if __name__ == '__main__':
    app = create_app()
    
    print("\n" + "="*60)
    print("🚀 MULTI-TENANT ERP BAŞLATILIYOR")
    print("="*60)
    print(f"📂 Master DB: {Config.MASTER_DB_PATH}")
    print(f"🌐 Login: http://localhost:5000/auth/login")
    print(f"⚙️  Setup: http://localhost:5000/setup")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', debug=True, port=5000)