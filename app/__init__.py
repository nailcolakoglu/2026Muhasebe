# app/__init__.py

"""
ERP Application Package
"""

# ÖNEMLI: Circular import'u önlemek için
# sadece gerektiğinde import et

__version__ = '2.0.0'
__all__ = []

# NOT: app.py'den import etme! Circular import olur.
# Bunun yerine app.py'de:
# app = create_app()
# şeklinde tanımla.