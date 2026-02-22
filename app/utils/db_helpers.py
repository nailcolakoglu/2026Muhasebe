# app/utils/db_helpers.py (YENİ DOSYA)
"""
Database Helper Functions
SQL Injection koruması için yardımcı fonksiyonlar
"""

from sqlalchemy import text
from app.extensions import db
import logging

logger = logging.getLogger(__name__)


def safe_execute(query_str: str, params: dict = None):
    """
    Parameterized query çalıştırır (SQL Injection koruması)
    
    Args:
        query_str: SQL query (parametre olarak :param_name kullan)
        params: Query parametreleri
    
    Returns:
        Result proxy
    
    Example:
        result = safe_execute(
            "SELECT * FROM faturalar WHERE firma_id = :firma_id AND tarih > :tarih",
            {'firma_id': '123', 'tarih': '2025-01-01'}
        )
    """
    try:
        query = text(query_str)
        result = db.session.execute(query, params or {})
        return result
    except Exception as e:
        logger.error(f"❌ Query Hatası: {e}\nQuery: {query_str}\nParams: {params}")
        raise


def validate_column_name(column_name: str, allowed_columns: list) -> bool:
    """
    Dinamik ORDER BY/WHERE için kolon adı validasyonu
    
    Args:
        column_name: Kullanıcıdan gelen kolon adı
        allowed_columns: İzin verilen kolonlar
    
    Returns:
        bool: Geçerli ise True
    
    Example:
        if validate_column_name(request.args.get('sort'), ['tarih', 'belge_no', 'tutar']):
            query = query.order_by(column_name)
    """
    return column_name in allowed_columns


# ❌ YANLIŞ KULLANIM ÖRNEĞİ (SQL Injection riski)
def get_faturalar_WRONG(firma_id: str, tarih: str):
    # ❌ ASLA BÖYLE YAPMAYIN!
    query = f"SELECT * FROM faturalar WHERE firma_id = '{firma_id}' AND tarih = '{tarih}'"
    result = db.session.execute(text(query))
    return result.fetchall()


# ✅ DOĞRU KULLANIM
def get_faturalar_CORRECT(firma_id: str, tarih: str):
    query = text("""
        SELECT * FROM faturalar 
        WHERE firma_id = :firma_id 
        AND tarih = :tarih
        AND deleted_at IS NULL
    """)
    result = db.session.execute(query, {'firma_id': firma_id, 'tarih': tarih})
    return result.fetchall()