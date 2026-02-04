# models/master/base.py (EN BASİT HALİ)

"""
Master Database Base Model
"""

from app.extensions import db

class MasterBase(db.Model):
    """
    Master DB için base model
    """
    __abstract__ = True