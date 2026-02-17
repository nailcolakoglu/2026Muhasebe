# app/patches.py
"""
Firebird + SQLAlchemy 2.x Uyumluluk Yamaları

Çözülen Sorunlar:
1. VARCHAR/CHAR length render problemi
2. Enum → String adapt sırasında '_enums' parametresi hatası
3. RETURNING ID hatası (SQLCODE: -804)
4. SQLAlchemy 2.x API değişiklikleri
"""
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def apply_firebird_patches():
    """
    Firebird veritabanı için gerekli Monkey Patch işlemlerini uygular.
    
    SQLAlchemy 2.x + Firebird uyumluluğunu sağlar.
    """
    logger.info("🔧 Firebird yamaları uygulanıyor...")
    
    # --- Firebird Modüllerini Import Et ---
    try:
        import sqlalchemy_firebird.base
        import sqlalchemy_firebird.types
    except ImportError as e:
        logger.error(f"❌ Firebird modülleri yüklenemedi: {e}")
        return
    
    # ========================================
    # 1. STRING RENDER PROBLEMLERİ
    # ========================================
    def _safe_string_render(type_, type_name):
        """VARCHAR/CHAR için length parametresini güvenli render et."""
        length = getattr(type_, 'length', None)
        if length:
            return f"{type_name}({length})"
        return type_name
    
    # Type Compiler Yamalar
    if hasattr(sqlalchemy_firebird.base, 'FBTypeCompiler'):
        compiler = sqlalchemy_firebird.base.FBTypeCompiler
        
        compiler.visit_VARCHAR = lambda self, type_, **kw: _safe_string_render(type_, "VARCHAR")
        compiler.visit_CHAR = lambda self, type_, **kw: _safe_string_render(type_, "CHAR")
        compiler.visit_String = lambda self, type_, **kw: _safe_string_render(type_, "VARCHAR")
        compiler.visit_TEXT = lambda self, type_, **kw: "BLOB SUB_TYPE TEXT"
        compiler.visit_JSON = lambda self, type_, **kw: "BLOB SUB_TYPE TEXT"
        
        logger.debug("✅ String render yamaları uygulandı")
    
    # Bind Cast Yamalar
    if hasattr(sqlalchemy_firebird.base, 'FBCompiler'):
        sqlalchemy_firebird.base.FBCompiler.render_bind_cast = lambda self, type_, dbapi_type, sqltext: sqltext
        logger.debug("✅ Bind cast yamaları uygulandı")
    
    # ========================================
    # 2. ENUM PARAMETRE HATASI (ANA SORUN)
    # ========================================
    TargetStringClass = None
    
    # Firebird String sınıfını bul (farklı versiyonlarda farklı yerlerde olabilir)
    search_paths = [
        ('sqlalchemy_firebird.types', '_FBString'),
        ('sqlalchemy_firebird.base', '_FBString'),
        ('sqlalchemy_firebird.types', 'FBString'),
        ('sqlalchemy_firebird.base', 'FBString'),
    ]
    
    for module_name, class_name in search_paths:
        try:
            module = __import__(module_name, fromlist=[class_name])
            if hasattr(module, class_name):
                TargetStringClass = getattr(module, class_name)
                logger.debug(f"✅ Firebird String sınıfı bulundu: {module_name}.{class_name}")
                break
        except (ImportError, AttributeError):
            continue
    
    if TargetStringClass:
        original_init = TargetStringClass.__init__
        
        def patched_fbstring_init(self, *args, **kwargs):
            """
            SQLAlchemy 2.x'in Enum adapt sırasında gönderdiği ekstra parametreleri temizle.
            
            Temizlenen parametreler:
            - _enums: Enum değerleri (Firebird String için gereksiz)
            - _disable_warnings: SQLAlchemy 2.x internal
            - _create_events: SQLAlchemy 2.x internal
            - _adapted_from: Tip adaptasyonu metadata
            - schema: PostgreSQL için (Firebird kullanmaz)
            - name: Tip adı (Firebird'de kullanılmaz)
            - metadata: SQLAlchemy 2.x metadata
            - _variant_mapping: SQLAlchemy 2.x variants
            """
            # ✅ SQLAlchemy 2.x'in tüm internal parametrelerini temizle
            unwanted_params = [
                '_enums',           # Enum → String adapt
                '_disable_warnings',
                '_create_events',
                '_adapted_from',
                'schema',
                'name',
                'metadata',         # SQLAlchemy 2.x
                '_variant_mapping', # SQLAlchemy 2.x
                'inherit_schema',   # SQLAlchemy 2.x
            ]
            
            for param in unwanted_params:
                kwargs.pop(param, None)
            
            # Orijinal __init__ çağır
            try:
                original_init(self, *args, **kwargs)
            except TypeError as e:
                # Hala hata varsa, tüm kwargs'ı temizle ve sadece length'i koru
                logger.warning(f"⚠️ Firebird String init hatası, fallback moda geçiliyor: {e}")
                safe_kwargs = {}
                if 'length' in kwargs:
                    safe_kwargs['length'] = kwargs['length']
                if 'collation' in kwargs:
                    safe_kwargs['collation'] = kwargs['collation']
                original_init(self, *args, **safe_kwargs)
        
        TargetStringClass.__init__ = patched_fbstring_init
        logger.info("✅ Firebird String ENUM yaması uygulandı")
    else:
        logger.warning("⚠️ Firebird String sınıfı bulunamadı, ENUM yaması atlandı")
    
    # ========================================
    # 3. RETURNING ID HATASI (SQLCODE: -804)
    # ========================================
    
    # Dialect seviyesinde kapat
    if hasattr(sqlalchemy_firebird.base, 'FBDialect'):
        sqlalchemy_firebird.base.FBDialect.implicit_returning = False
        logger.debug("✅ FBDialect.implicit_returning = False")
    
    # fdb driver için özel yama
    try:
        import sqlalchemy_firebird.fdb
        if hasattr(sqlalchemy_firebird.fdb, 'FBDialect_fdb'):
            sqlalchemy_firebird.fdb.FBDialect_fdb.implicit_returning = False
            logger.debug("✅ FBDialect_fdb.implicit_returning = False")
    except ImportError:
        pass
    
    # ✅ SQLAlchemy 2.x uyumlu event listener
    @event.listens_for(Engine, "before_cursor_execute", retval=True)
    def _force_disable_returning(conn, cursor, statement, parameters, context, executemany):
        """
        Her sorgu öncesi RETURNING'i kapat.
        
        SQLAlchemy 2.x için retval=True gerekli.
        """
        if context and hasattr(context, 'compiled'):
            dialect = context.compiled.dialect
            if hasattr(dialect, 'implicit_returning'):
                dialect.implicit_returning = False
        
        # Statement'i değiştirmeden döndür (SQLAlchemy 2.x)
        return statement, parameters
    
    logger.info("✅ Firebird RETURNING yaması uygulandı")
    
    # ========================================
    # 4. BAĞLANTI HAVUZU OPTİMİZASYONU
    # ========================================
    @event.listens_for(Engine, "connect")
    def _set_firebird_pragmas(dbapi_conn, connection_record):
        """
        Firebird bağlantısı için optimal ayarlar.
        """
        try:
            # Firebird transaction ayarları
            # (Gerekirse buraya eklemeler yapılabilir)
            pass
        except Exception as e:
            logger.warning(f"⚠️ Firebird pragma ayarları uygulanamadı: {e}")
    
    logger.info("✅ Firebird yamaları (SQLAlchemy 2.x uyumlu) başarıyla uygulandı")

    # ========================================
    # 5. FIREBIRD TERMINATE FIX (YENİ!)
    # ========================================
    
    # do_terminate() metodunu yamala
    if hasattr(sqlalchemy_firebird.base, 'FBDialect'):
        def safe_do_terminate(self, dbapi_connection):
            """
            Firebird bağlantısını güvenli şekilde kapat.
            
            firebird-driver 2.x'te 'terminate()' metodu yok,
            'close()' kullanmalıyız.
            """
            try:
                # Önce transaction'ı rollback et
                if hasattr(dbapi_connection, 'rollback'):
                    try:
                        dbapi_connection.rollback()
                    except Exception:
                        pass
                
                # Sonra bağlantıyı kapat
                if hasattr(dbapi_connection, 'close'):
                    dbapi_connection.close()
                elif hasattr(dbapi_connection, 'detach'):
                    dbapi_connection.detach()
            except Exception as e:
                # Hata olsa bile devam et (shutdown sırasında normal)
                logger.debug(f"Firebird terminate hatası (göz ardı edildi): {e}")
        
        sqlalchemy_firebird.base.FBDialect.do_terminate = safe_do_terminate
        logger.info("✅ Firebird terminate yaması uygulandı")
    
    # ========================================
    # 6. POOL DISPOSE EVENT (YENİ!)
    # ========================================
    
    @event.listens_for(Engine, "close")
    def _safe_close_firebird(dbapi_conn, connection_record):
        """
        Pool kapatılırken bağlantıları güvenli şekilde temizle.
        """
        try:
            if hasattr(dbapi_conn, 'rollback'):
                dbapi_conn.rollback()
            if hasattr(dbapi_conn, 'close'):
                dbapi_conn.close()
        except Exception:
            pass  # Göz ardı et (shutdown sırasında normal)
    
    logger.info("✅ Firebird pool cleanup yaması uygulandı")
    
    logger.info("✅ Firebird yamaları (SQLAlchemy 2.x + Pool Fix) başarıyla uygulandı")


# ========================================
# OTOMATIK YÜKLEME (İSTEĞE BAĞLI)
# ========================================
def init_app(app):
    """
    Flask uygulaması başlatılırken yamaları uygula.
    
    Kullanım:
        from app.patches import init_app
        init_app(app)
    """
    with app.app_context():
        apply_firebird_patches()