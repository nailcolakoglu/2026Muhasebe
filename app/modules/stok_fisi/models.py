# modules/stok_fisi/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import StokFisTuru
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class StokFisi(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'stok_fisleri'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'))
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'))
    
    fis_turu = db.Column(db.Enum(StokFisTuru), nullable=False)
    belge_no = db.Column(db.String(50))
    tarih = db.Column(db.Date)
    
    giris_depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=True)
    cikis_depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=True)
    aciklama = db.Column(db.String(255))
    
    detaylar = db.relationship('StokFisiDetay', backref='fis', cascade="all, delete-orphan")
    
    cikis_depo = db.relationship('Depo', foreign_keys=[cikis_depo_id], backref='cikis_fisleri_rel')
    giris_depo = db.relationship('Depo', foreign_keys=[giris_depo_id], backref='giris_fisleri_rel')

    __table_args__ = (UniqueConstraint('firma_id', 'belge_no', 'fis_turu', name='uq_stokfis_no'),)


