# modules/kategori/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class StokKategori(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'stok_kategorileri'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    ad = db.Column(db.String(100), nullable=False)
    
    # 👇 EKSİK OLAN KISIMLAR EKLENDİ 👇
    ust_kategori_id = db.Column(db.String(36), db.ForeignKey('stok_kategorileri.id'), nullable=True)
    
    # Kendi kendine ilişki (Recursive Relationship)
    ust_kategori = db.relationship('StokKategori', remote_side=[id], backref='alt_kategoriler')
    # ---------------------------------

    __table_args__ = (UniqueConstraint('firma_id', 'ad', name='uq_kategori_ad'),)

