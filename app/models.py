# models.py (YENİ - Sadece 10 satır)

"""
DEPRECATED:  Bu dosya geriye dönük uyumluluk için korunuyor.
Yeni kodlarda:  from models import Firma kullanın.
"""

from models import *

# Geriye dönük uyumluluk için
__all__ = ['db', 'Firma', 'CariHesap', 'Fatura', 'StokKart', 
           'ensure_firebird_database', 'FirmaFilteredQuery']