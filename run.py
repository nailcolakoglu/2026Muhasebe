# app.py
"""
ERP Uygulaması - Ana Flask Uygulaması
Optimize edilmiş context yönetimi, cache ve middleware yapısı

https://github.com/nailcolakoglu/MuhPostgreSQL
"""
import os
import logging
import click
from flask import Flask, g, session, request, redirect, url_for, render_template, flash
from flask_login import login_required, current_user
from datetime import datetime, timezone
from sqlalchemy import text

from app.extensions import db, cache, login_manager, babel, init_extensions, limiter, socketio
from app.context_manager import GlobalContextManager
from config import get_config


# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """
    Flask uygulama factory.
    
    Args:
        config_name (str): Config adı ('development', 'production', 'testing')
        
    Returns:
        Flask: Yapılandırılmış Flask uygulaması
    """
    import os
    
    # Proje kök dizini
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # Flask uygulaması oluştur
    app = Flask(
        __name__,
        template_folder=os.path.join(basedir, 'app', 'templates'),  # ✅ EKLE
        static_folder=os.path.join(basedir, 'app', 'static')        # ✅ EKLE
    )
    
    
    # Config yükleme
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app.config.from_object(get_config(config_name))
    
    from flask import request
    from app.form_builder.menu_manager import MenuManager

    @app.context_processor
    def inject_breadcrumbs():
        # Sadece giriş yapmış kullanıcılar için hesapla
        if current_user.is_authenticated:
            return dict(breadcrumbs=MenuManager.get_breadcrumb(request.path))
        return dict(breadcrumbs=[])
    
    
    logger.info(f"🚀 Uygulama başlatılıyor: {config_name} modu")

    # ✅ Extension'ları başlat
    init_extensions(app)
        
    # Middleware
    register_middleware(app)
    
    # Blueprints
    register_blueprints(app)
    
    # Error handlers
    register_error_handlers(app)
    
    # Shell context
    register_shell_context(app)
    
    # CLI commands
    register_cli_commands(app)
    
    # ============================================
    # CONTEXT PROCESSORS (ÖNEMLİ!)
    # ============================================
    from app.context_processors import inject_global_vars
    
    app.context_processor(inject_global_vars)  # ✅ KAYITLI MI KONTROL ET!
    
    logger.info("✅ Context processor kaydedildi")
    
    
    # ============================================
    # ✅ SQL QUERY LOGGING (DEBUG)
    # ============================================
    if app.debug:
        import logging
        logging.basicConfig()
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        logger.info("✅ SQL query logging aktif (DEBUG mode)")
    
    logger.info("✅ Uygulama başarıyla yapılandırıldı")
    
    return app



def register_middleware(app):
    """
    Middleware kayıtları (before_request, after_request, teardown).
    
    Args:
        app (Flask): Flask uygulaması
    """
    
    @app.before_request
    def load_global_context():
        """
        ✅ MySQL MULTI-TENANT VERSION
        Global context yüklemesi
        """
        
        # 1. Static dosyalar için atla
        skip_paths = ['/static', '/health', '/favicon.ico', '/auth/login', '/auth/select-tenant']
        if any(request.path.startswith(path) for path in skip_paths):
            return
        
        # 2. Request başlangıç zamanı
        g.request_start_time = datetime.now(timezone.utc)
        
        # 3. Modüller (cache'den)
        try:
            g.modules = GlobalContextManager.get_active_modules()
        except Exception as e:
            logger.error(f"Modüller yüklenirken hata: {e}")
            g.modules = []
        
        # 4. Tenant context (MySQL version)
        if 'tenant_id' in session:
            tenant_id = session['tenant_id']
            
            try:
                # Tenant metadata (cache'den)
                g.tenant_metadata = GlobalContextManager.get_tenant_metadata(tenant_id)
                
                if not g.tenant_metadata:
                    logger.warning(f"⚠️ Tenant {tenant_id} bulunamadı")
                    session.clear()
                    return redirect(url_for('auth.login'))
                
                # Lazy tenant data
                g.tenant = GlobalContextManager.get_tenant_data_lazy(tenant_id)
                
                # ✅ MySQL: Database switch (automatic by connection URL)
                # Her tenant için ayrı database var, schema switch gerekmiyor
                
                # Current tenant ID'yi kaydet (filtrelerde kullan)
                g.current_tenant_id = tenant_id
                
                logger.debug(f"🔧 Tenant ayarlandı: {tenant_id}")
            
            except Exception as e:
                logger.error(f"❌ Tenant context hatası: {e}")
                session.clear()
                return redirect(url_for('auth.login'))
        
        # 5. Kullanıcı bilgisi
        if 'user_id' in session:
            g.user_id = session['user_id']
            g.user_name = session.get('user_name', '')
            g.user_email = session.get('user_email', '')
            g.user_role = session.get('user_role', 'user')
    
    
    @app.after_request
    def after_request(response):
        """
        ✅ MySQL VERSION: After request
        
        MySQL'de schema sıfırlama YOK
        """
        
        # Performance tracking (debug modda)
        if app.debug and hasattr(g, 'request_start_time'):
            duration = (datetime.now(timezone.utc) - g.request_start_time).total_seconds()
            response.headers['X-Request-Duration'] = f"{duration:.3f}s"
            
            if duration > 1.0:
                logger.warning(f"⚠️ Yavaş istek: {request.path} - {duration:.2f}s")
        
        # Security headers (production'da)
        if not app.debug:
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response
        
    
    @app.teardown_request
    def teardown_request(exception=None):
        """
        Request sonrası temizlik.
        
        Args:
            exception: Oluşan hata (varsa)
        """
        if exception:
            db.session.rollback()
            logger.error(f"❌ Request hatası: {exception}", exc_info=True)
        
        # DB session'ı kapat
        db.session.remove()
    
    
    @app.context_processor
    def inject_global_vars():
        """
        Template'lere otomatik inject edilecek değişkenler.
        
        Returns:
            dict: Template değişkenleri
        """
        dynamic_menu = []
        try:
            from app.form_builder.menu_manager import MenuManager
            dynamic_menu = MenuManager.get_tree()
        except Exception as e:
            logger.warning(f"⚠️ Menü yüklenirken hata: {e}")
            dynamic_menu = []
        
        return {
            'now': datetime.now(timezone.utc),  # ✅ DÜZELTİLDİ
            'app_name': app.config.get('APP_NAME', 'ERP Sistemi'),
            'app_version': app.config.get('APP_VERSION', '4.25.19'),
            'current_year': datetime.now(timezone.utc).year,  # ✅ DÜZELTİLDİ
            'dynamic_menu': dynamic_menu, 
        }
    
    
def register_blueprints(app):
    """
    Blueprint kayıtları - REPO'DAKİ GERÇEK MODÜLLER
    
    Args:
        app (Flask): Flask uygulaması
    """

    # validation_api modülü (Kimlik doğrulama)
    from app.form_builder.validation_api import validation_bp
    app.register_blueprint(validation_bp, url_prefix='/api')
    
    # ============================================================================
    # TEMEL MODÜLLER
    # ============================================================================
    
    # Auth modülü (Kimlik doğrulama)
    from app.modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    #Main modülü
    from app.modules.main.routes import main_bp
    app.register_blueprint(main_bp, url_prefix='')
    
    # Ana sayfa (index route'ları auth içinde olabilir)
    # Eğer ayrı bir index route'ı varsa burada ekle
    
    # ============================================================================
    # TANIMLAMALAR (Master Data)
    # ============================================================================
    
    # Firma modülü
    from app.modules.firmalar.routes import firmalar_bp
    app.register_blueprint(firmalar_bp, url_prefix='/firmalar')
    
    # Şube modülü
    from app.modules.sube.routes import sube_bp
    app.register_blueprint(sube_bp, url_prefix='/sube')
    
    # Depo modülü
    from app.modules.depo.routes import depo_bp
    app.register_blueprint(depo_bp, url_prefix='/depo')
    
    # Stok modülü
    from app.modules.stok.routes import stok_bp
    app.register_blueprint(stok_bp, url_prefix='/stok')
    
    # Stok-fisi modülü
    from app.modules.stok_fisi.routes import stok_fisi_bp
    app.register_blueprint(stok_fisi_bp, url_prefix='/stok-fisi')
    
    # CRM Modülü
    from app.modules.crm.routes import crm_bp
    app.register_blueprint(crm_bp, url_prefix='/crm')
    
    # Cari modülü
    from app.modules.cari.routes import cari_bp
    app.register_blueprint(cari_bp, url_prefix='/cari')
    
    # Kategori modülü
    from app.modules.kategori.routes import kategori_bp
    app.register_blueprint(kategori_bp, url_prefix='/kategori')
    
    # ABONELİK modülü
    from app.modules.subscription.routes import subscription_bp
    app.register_blueprint(subscription_bp, url_prefix='/paketler')
    
    # Kullanıcı modülü
    from app.modules.kullanici.routes import kullanici_bp
    app.register_blueprint(kullanici_bp, url_prefix='/kullanici')
    
    # ============================================================================
    # OPERASYONEL MODÜLLER
    # ============================================================================
    
    # İrsaliye modülü
    from app.modules.irsaliye.routes import irsaliye_bp
    app.register_blueprint(irsaliye_bp, url_prefix='/irsaliye')
    
    # E-İrsaliye modülü
    from app.modules.eirsaliye.routes import eirsaliye_bp
    app.register_blueprint(eirsaliye_bp, url_prefix='/eirsaliye')
    
    # Fatura modülü
    from app.modules.fatura.routes import fatura_bp
    app.register_blueprint(fatura_bp, url_prefix='/fatura')
        
    # E-fatura modülü    
    from app.modules.efatura.routes import efatura_bp
    app.register_blueprint(efatura_bp, url_prefix='/efatura')
    
    from app.modules.fatura.ocr_routes import fatura_ocr_bp
    app.register_blueprint(fatura_ocr_bp)

    # Doviz modülü
    from app.modules.doviz.routes import doviz_bp
    app.register_blueprint(doviz_bp, url_prefix='/doviz')
    
    # Lokasyon modülü
    from app.modules.lokasyon.routes import lokasyon_bp
    app.register_blueprint(lokasyon_bp, url_prefix='/lokasyon')
    
    # fiyat modülü
    from app.modules.fiyat.routes import fiyat_bp
    app.register_blueprint(fiyat_bp, url_prefix='/fiyat')
    
    # sistem modülü
    from app.modules.sistem.routes import sistem_bp
    app.register_blueprint(sistem_bp, url_prefix='/sistem')
    
    # bolge modülü
    from app.modules.bolge.routes import bolge_bp
    app.register_blueprint(bolge_bp, url_prefix='/bolge')
    
    # Sipariş modülü
    from app.modules.siparis.routes import siparis_bp
    app.register_blueprint(siparis_bp, url_prefix='/siparis')
    
    # Mobile modülü
    from app.modules.mobile.routes import mobile_bp
    app.register_blueprint(mobile_bp, url_prefix='/mobile')
    
    # Finans modülü
    from app.modules.finans.routes import finans_bp
    app.register_blueprint(finans_bp, url_prefix='/finans')
    
    # Kasa modülü
    from app.modules.kasa.routes import kasa_bp
    app.register_blueprint(kasa_bp, url_prefix='/kasa')
    
    # kasa_hareket modülü
    from app.modules.kasa_hareket.routes import kasa_hareket_bp
    app.register_blueprint(kasa_hareket_bp, url_prefix='/kasa-hareket')
    
    # Banka modülü
    from app.modules.banka.routes import banka_bp
    app.register_blueprint(banka_bp, url_prefix='/banka')
    
    # Banka_hareket modülü
    from app.modules.banka_hareket.routes import banka_hareket_bp
    app.register_blueprint(banka_hareket_bp, url_prefix='/banka-hareket')
    
    # Banka_import modülü
    from app.modules.banka_import.routes import banka_import_bp
    app.register_blueprint(banka_import_bp, url_prefix='/banka-import')
    
    # Çek/Senet modülü
    from app.modules.cek.routes import cek_bp
    app.register_blueprint(cek_bp, url_prefix='/cek')
    
    # ============================================================================
    # FİNANS MODÜLLERI
    # ============================================================================
    
    # Muhasebe modülü
    from app.modules.muhasebe.routes import muhasebe_bp
    app.register_blueprint(muhasebe_bp, url_prefix='/muhasebe')
    
    # ============================================================================
    # RAPORLAMA
    # ============================================================================
    
    # Rapor modülü
    from app.modules.rapor.routes import rapor_bp
    app.register_blueprint(rapor_bp, url_prefix='/rapor')
    
    # B2B modülü
    from app.modules.b2b.routes import b2b_bp
    app.register_blueprint(b2b_bp, url_prefix='/b2b')
    from app.modules.b2b.admin_routes import b2b_admin_bp
    app.register_blueprint(b2b_admin_bp, url_prefix='/b2b-yonetim')
    
    
    logger.info(f"📘 {len(app.blueprints)} blueprint kaydedildi")
    
    # Blueprint listesini logla (debug için)
    if app.debug:
        for bp_name, bp in app.blueprints.items():
            logger.debug(f"  - {bp_name}: {bp.url_prefix}")


def register_error_handlers(app):
    """
    Hata yakalayıcıları kaydet.
    
    Args:
        app (Flask): Flask uygulaması
    """
    
    # ✅ YENİ: CSRF Error Handler (400)
    @app.errorhandler(400)
    def bad_request_error(error):
        """400 - Bad Request (CSRF dahil)."""
        from flask_wtf.csrf import CSRFError
        
        # CSRF hatası mı?
        if isinstance(error, CSRFError):
            # ✅ logger yerine app.logger kullan
            app.logger.warning(f"CSRF hatası: {error.description}, IP: {request.remote_addr}")
            
            # AJAX isteği mi?
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {
                    'error': 'CSRF token süresi doldu',
                    'message': 'Lütfen sayfayı yenileyin ve tekrar deneyin.',
                    'code': 'CSRF_EXPIRED'
                }, 400
            
            # Normal istek: Login sayfasına yönlendir
            flash(
                '⚠️ Güvenlik token\'ınızın süresi doldu. Lütfen tekrar giriş yapın.',
                'warning'
            )
            return redirect(url_for('auth.login'))
        
        # Diğer 400 hataları
        app.logger.warning(f"400: {request.url}")
        if request.path.startswith('/api/'):
            return {'error': 'Bad request'}, 400
        
        return render_template('errors/400.html'), 400
    
    
    @app.errorhandler(404)
    def not_found_error(error):
        """404 - Sayfa bulunamadı."""
        app.logger.warning(f"404: {request.url}")  # ✅ logger → app.logger
        
        if request.path.startswith('/api/'):
            return {'error': 'Resource not found'}, 404
        
        return render_template('errors/404.html'), 404
    
    
    @app.errorhandler(500)
    def internal_error(error):
        """500 - Sunucu hatası."""
        app.logger.error(f"500: {error}", exc_info=True)  # ✅ logger → app.logger
        db.session.rollback()
        
        if request.path.startswith('/api/'):
            return {'error': 'Internal server error'}, 500
        
        return render_template('errors/500.html'), 500
    
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """403 - Yetkisiz erişim."""
        app.logger.warning(
            f"403: {request.url} - User: {g.get('user_id', 'Anonymous')}"
        )  # ✅ logger → app.logger
        
        if request.path.startswith('/api/'):
            return {'error': 'Forbidden'}, 403
        
        return render_template('errors/403.html'), 403
    
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Genel hata yakalayıcı."""
        app.logger.error(f"Beklenmeyen hata: {error}", exc_info=True)  # ✅ logger → app.logger
        
        if app.debug:
            # Debug modda hata detaylarını göster
            raise error
        
        db.session.rollback()
        
        if request.path.startswith('/api/'):
            return {'error': 'Internal server error'}, 500
        
        return render_template('errors/500.html'), 500
        
        
def register_shell_context(app):
    """
    Flask shell için context ekle.
    
    Args:
        app (Flask): Flask uygulaması
    """
    
    @app.shell_context_processor
    def make_shell_context():
        """
        Flask shell için otomatik import'lar
        
        Kullanım:
            flask shell
            >>> User.query.first()
            >>> Tenant.query.all()
        """
        from app.extensions import db
        
        # Master modeller (güvenli import)
        try:
            from app.models.master import User, Tenant, UserTenantRole, License
        except ImportError as e:
            logger.warning(f"⚠️ Master model import hatası: {e}")
            User = Tenant = UserTenantRole = License = None
        
        # Tenant modelleri (opsiyonel)
        try:
            from app.modules.bolge.models import Bolge
        except ImportError:
            Bolge = None
        
        try:
            from app.modules.sube.models import Sube
        except ImportError:
            Sube = None
        
        try:
            from app.modules.firma.models import Firma
        except ImportError:
            Firma = None
        
        try:
            from app.modules.kullanici.models import Kullanici
        except ImportError:
            Kullanici = None
        
        # Validators
        try:
            from app.utils.validators import SecurityValidator
        except ImportError:
            SecurityValidator = None
        
        # Permission Manager
        try:
            from app.services.permission_manager import PermissionManager
        except ImportError:
            PermissionManager = None
        
        return {
            'app': app,
            'db': db,
            # Master
            'User': User,
            'Tenant': Tenant,
            'UserTenantRole': UserTenantRole,
            'License': License,
            # Tenant
            'Bolge': Bolge,
            'Sube': Sube,
            'Firma': Firma,
            'Kullanici': Kullanici,
            # Utils
            'SecurityValidator': SecurityValidator,
            'PermissionManager': PermissionManager
        }


def register_cli_commands(app):
    """
    Flask CLI komutları ekle.
    
    Args:
        app (Flask): Flask uygulaması
    """
    
    @app.cli.command('init-db')
    def init_db():
        """Veritabanını başlat (master tablolar)."""
        db.create_all()
        click.echo('✅ Master veritabanı tabloları oluşturuldu.')
    
    @app.cli.command('create-tenant')
    @click.argument('tenant_code')
    def create_tenant_schema(tenant_code):
        """
        Yeni tenant schema oluştur.
        
        Kullanım: flask create-tenant ABC001
        """
        from sqlalchemy import text
        
        schema_name = f'tenant_{tenant_code}'
        
        try:
            # Schema oluştur
            db.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            db.session.commit()
            
            # search_path ayarla
            db.session.execute(text(f"SET search_path TO {schema_name}"))
            
            # Tenant tablolarını oluştur
            db.create_all()
            db.session.commit()
            
            click.echo(f'✅ Tenant schema oluşturuldu: {schema_name}')
            
        except Exception as e:
            db.session.rollback()
            click.echo(f'❌ Hata: {e}', err=True)
    
    @app.cli.command('clear-cache')
    def clear_cache():
        """Cache'i temizle."""
        cache.clear()
        click.echo('✅ Cache temizlendi.')
    
    @app.cli.command('health-check')
    def health_check():
        """Sistem sağlık kontrolü."""
        try:
            # DB bağlantısı
            db.session.execute(text('SELECT 1'))
            click.echo('✅ PostgreSQL: OK')
            
            # Cache bağlantısı
            cache.set('health_check', 'ok', timeout=5)
            result = cache.get('health_check')
            if result == 'ok':
                click.echo('✅ Cache: OK')
            else:
                click.echo('⚠️ Cache: FAIL')
            
        except Exception as e:
            click.echo(f'❌ Hata: {e}', err=True)


# ============================================================================
# ANA UYGULAMA BAŞLATMA
# ============================================================================

app = create_app()

@app.route('/debug/session')
def debug_session():
    """Session debug (SADECE DEVELOPMENT!)"""
    if not app.debug:
        abort(403)
    
    from flask_login import current_user
    
    return {
        'session': dict(session),
        'authenticated': current_user.is_authenticated,
        'user_id': current_user.id if current_user.is_authenticated else None,
        'user_email': getattr(current_user, 'email', None),
        'cookies': dict(request.cookies),
        # ✅ YENİ: Session'ın gerçekten var olup olmadığını kontrol et
        'session_exists': 'session' in request.cookies,
        'session_keys': list(session.keys()) if session else []
    }


@app.route('/health')
def health():
    """
    Healthcheck endpoint (load balancer için).
    
    Returns:
        dict: Sistem durumu
    """
    try:
        # DB kontrolü
        db.session.execute(text('SELECT 1'))
        db_status = 'ok'
    except Exception as e:
        logger.error(f"Healthcheck DB hatası: {e}")
        db_status = 'error'
    
    try:
        # Cache kontrolü
        cache.set('health_check', 'ok', timeout=5)
        cache_status = 'ok' if cache.get('health_check') == 'ok' else 'error'
    except Exception as e:
        logger.error(f"Healthcheck cache hatası: {e}")
        cache_status = 'error'
    
    status_code = 200 if db_status == 'ok' and cache_status == 'ok' else 503
    
    return {
        'status': 'healthy' if status_code == 200 else 'unhealthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),  # ✅ DÜZELTİLDİ
        'services': {
            'database': db_status,
            'cache': cache_status
        }
    }, status_code
    

@app.route('/')
def index():
    """Ana sayfa yönlendirmesi."""
    if 'user_id' in session:
        # Login sonrası ana sayfa (auth içinde olabilir)
        return redirect(url_for('auth.index'))
    return redirect(url_for('auth.login'))


@app.route('/debug/sql', methods=['GET', 'POST'])
@login_required
def debug_sql():
    """Debug SQL Console (SQLAlchemy 2.x uyumlu)"""
    if not app.debug:
        abort(403)
    
    from app.extensions import get_tenant_db, csrf
    from sqlalchemy import text  # ✅ EKLE
    
    result = None
    error = None
    row_count = 0
    
    if request.method == 'POST':
        sql = request.form.get('sql', '').strip()
        
        if not sql:
            error = "SQL sorgusu boş olamaz."
        else:
            try:
                tenant_db = get_tenant_db()
                
                # ✅ text() ile wrap et
                result_proxy = tenant_db.execute(text(sql))
                
                # SELECT sorgusuysa sonuçları al
                if sql.upper().startswith('SELECT'):
                    result = result_proxy.fetchall()
                    row_count = len(result)
                else:
                    # INSERT, UPDATE, DELETE için commit et
                    tenant_db.commit()
                    result = f"✅ Sorgu başarıyla çalıştırıldı. Etkilenen satır: {result_proxy.rowcount}"
                    
            except Exception as e:
                tenant_db.rollback()  # Hata durumunda rollback
                error = str(e)
    
    return f"""
    <html>
    <head>
        <title>SQL Console</title>
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                padding: 20px; 
                background: #0d1117; 
                color: #c9d1d9; 
                margin: 0;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ color: #58a6ff; margin-bottom: 5px; }}
            .subtitle {{ color: #8b949e; margin-bottom: 20px; }}
            textarea {{ 
                width: 100%; 
                background: #161b22; 
                color: #c9d1d9; 
                border: 1px solid #30363d; 
                padding: 12px; 
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                border-radius: 6px;
                resize: vertical;
            }}
            textarea:focus {{ 
                outline: none; 
                border-color: #58a6ff; 
            }}
            button {{ 
                background: #238636; 
                color: white; 
                border: none; 
                padding: 12px 24px; 
                cursor: pointer; 
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                margin-top: 10px;
            }}
            button:hover {{ background: #2ea043; }}
            .result-box {{ 
                background: #161b22; 
                padding: 16px; 
                margin-top: 20px;
                border: 1px solid #30363d;
                border-radius: 6px;
                overflow-x: auto;
            }}
            .result-box h3 {{ margin-top: 0; }}
            pre {{ 
                margin: 0;
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}
            th {{
                background: #21262d;
                padding: 10px;
                text-align: left;
                border: 1px solid #30363d;
                color: #58a6ff;
                font-weight: bold;
            }}
            td {{
                padding: 8px;
                border: 1px solid #30363d;
            }}
            tr:nth-child(even) {{ background: #0d1117; }}
            tr:hover {{ background: #161b22; }}
            .error {{ color: #f85149; }}
            .success {{ color: #3fb950; }}
            .info {{ color: #58a6ff; }}
            hr {{ border-color: #21262d; margin: 30px 0; }}
            code {{ 
                background: #21262d; 
                padding: 2px 6px; 
                border-radius: 3px; 
                color: #79c0ff;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Firebird SQL Console</h1>
            <p class="subtitle">Debug Mode - Tenant Database Query Tool</p>
            
            <form method="POST">
                <textarea name="sql" rows="10" placeholder="SELECT * FROM FIRMALAR FIRST 10" autofocus>{request.form.get('sql', 'SELECT * FROM FIRMALAR FIRST 10')}</textarea>
                <button type="submit">▶ SQL Çalıştır</button>
            </form>
            
            {f'''
            <div class="result-box">
                <h3 class="success">✅ Sorgu Başarılı ({row_count} satır)</h3>
                <table>
                    <thead>
                        <tr>
                            {"".join(f"<th>{col}</th>" for col in result[0].keys()) if result and hasattr(result[0], 'keys') else ""}
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(
                            "<tr>" + "".join(f"<td>{val}</td>" for val in row) + "</tr>"
                            for row in result
                        )}
                    </tbody>
                </table>
            </div>
            ''' if result and isinstance(result, list) else ''}
            
            {f'<div class="result-box"><h3 class="success">{result}</h3></div>' if result and isinstance(result, str) else ''}
            
            {f'<div class="result-box"><h3 class="error">❌ Hata</h3><pre>{error}</pre></div>' if error else ''}
            
            <hr>
            <div style="color: #6e7681; font-size: 13px;">
                <strong class="info">💡 İpuçları:</strong><br>
                • Firebird'de LIMIT yerine <code>SELECT FIRST 10</code> kullanın<br>
                • String değerler için tek tırnak kullanın: <code>WHERE UNVAN = 'ABC'</code><br>
                • Tabloları görmek için: <code>SELECT RDB$RELATION_NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0</code><br>
                • Kolonları görmek için: <code>SELECT RDB$FIELD_NAME FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME = 'FIRMALAR'</code>
                <br><br>
                <strong style="color: #f85149;">⚠️ Uyarı:</strong> Bu konsol sadece development modunda çalışır. Production'da devre dışıdır.
            </div>
        </div>
    </body>
    </html>
    """


# ✅ CSRF'i bu route için kapat (fonksiyon tanımından sonra)
from app.extensions import csrf
csrf.exempt(debug_sql)


if __name__ == '__main__':
    """
    Development modda doğrudan çalıştırma:
    python app.py
    """
    print("=" * 60)
    print("🚀 Development Server Başlatılıyor...")
    print("=" * 60)
    print(f"📍 URL: http://localhost:5000")
    print(f"🔧 Debug Mode: {app.debug}")
    print(f"🌍 Environment: {app.config.get('ENV', 'development')}")
    print("=" * 60)
    
    #app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True )
    
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True, 
        use_reloader=True
    )