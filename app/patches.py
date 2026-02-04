# app/patches.py

import sqlalchemy_firebird.base
import sqlalchemy_firebird.types
from sqlalchemy import event
from sqlalchemy.engine import Engine

def apply_firebird_patches():
    """
    Firebird veritabanı için gerekli olan Monkey Patch işlemlerini uygular.
    1.String Render Problemleri (VARCHAR length)
    2.ENUM Parametre Hatası
    3.RETURNING ID Hatası (SQLCODE: -804)
    """
    print("🔧Firebird yamaları uygulanıyor...")

    # --- fdb Modülünü Yamala ---
    try:
        import sqlalchemy_firebird.fdb
    except ImportError:
        pass

    # 1.String Render Problemleri İçin Yama
    def _safe_string_render(type_, type_name):
        length = getattr(type_, 'length', None)
        if length:
            return f"{type_name}({length})"
        return type_name

    def visit_VARCHAR(self, type_, **kw): return _safe_string_render(type_, "VARCHAR")
    def visit_CHAR(self, type_, **kw): return _safe_string_render(type_, "CHAR")
    def visit_String(self, type_, **kw): return _safe_string_render(type_, "VARCHAR")
    def visit_TEXT(self, type_, **kw): return _safe_string_render(type_, "BLOB SUB_TYPE TEXT")
    def visit_JSON(self, type_, **kw): return "BLOB SUB_TYPE TEXT"
    def patched_render_bind_cast(self, type_, dbapi_type, sqltext): return sqltext

    if hasattr(sqlalchemy_firebird.base, 'FBTypeCompiler'):
        compiler = sqlalchemy_firebird.base.FBTypeCompiler
        compiler.visit_VARCHAR = visit_VARCHAR
        compiler.visit_CHAR = visit_CHAR
        compiler.visit_String = visit_String
        compiler.visit_TEXT = visit_TEXT
        compiler.visit_JSON = visit_JSON

    if hasattr(sqlalchemy_firebird.base, 'FBCompiler'):
        sqlalchemy_firebird.base.FBCompiler.render_bind_cast = patched_render_bind_cast

    # 2.ENUM Parametre Hatası Yaması
    try:
        TargetStringClass = None
        if hasattr(sqlalchemy_firebird.types, '_FBString'): TargetStringClass = sqlalchemy_firebird.types._FBString
        elif hasattr(sqlalchemy_firebird.base, '_FBString'): TargetStringClass = sqlalchemy_firebird.base._FBString
        elif hasattr(sqlalchemy_firebird.types, 'FBString'): TargetStringClass = sqlalchemy_firebird.types.FBString

        if TargetStringClass:
            original_init = TargetStringClass.__init__
            def patched_fbstring_init(self, *args, **kwargs):
                for k in ['_enums', '_disable_warnings', '_create_events', '_adapted_from', 'schema', 'name']:
                    kwargs.pop(k, None)
                original_init(self, *args, **kwargs)
            TargetStringClass.__init__ = patched_fbstring_init
    except Exception as e:
        print(f"⚠️ ENUM Yama hatası: {e}")

    # 3.RETURNING ID HATASI (SQLCODE: -804) - AGRESİF ÇÖZÜM
    sqlalchemy_firebird.base.FBDialect.implicit_returning = False

    if hasattr(sqlalchemy_firebird, 'fdb') and hasattr(sqlalchemy_firebird.fdb, 'FBDialect_fdb'):
        sqlalchemy_firebird.fdb.FBDialect_fdb.implicit_returning = False

    # Her bağlantıda zorla kapat
    @event.listens_for(Engine, "before_cursor_execute", retval=False)
    def _force_disable_returning(conn, cursor, statement, parameters, context, executemany):
        if context and hasattr(context, 'dialect'):
            context.dialect.implicit_returning = False

    print("✅ Firebird yamaları (V69 - DLL + Code Patch) başarıyla uygulandı.")