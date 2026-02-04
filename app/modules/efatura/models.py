# modules/efatura/models.py

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


class EntegratorAyarlari(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'entegrator_ayarlari'
    query_class = FirmaFilteredQuery
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    
    provider = db.Column(db.String(50)) # 'UYUMSOFT', 'EDM', 'LOGO' vb.
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))
    api_url = db.Column(db.String(255))
    gb_etiketi = db.Column(db.String(100)) # Gonderici Birim (defaultgb@firma.com)
    pk_etiketi = db.Column(db.String(100)) # Posta Kutusu (defaultpk@firma.com)
    
    aktif = db.Column(db.Boolean, default=True)
