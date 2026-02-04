# modules/kasa/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin

from app.enums import ParaBirimi
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Kasa(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'kasalar'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=False)
    
    # 👇 YENİ ALAN: Kasa Sorumlusu (Zimmetli Personel)
    # Nullable=True yapıyoruz ki Genel Kasalar sahipsiz kalabilsin (veya adminlere ortak olsun)
    kullanici_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)

    kod = db.Column(db.String(20), nullable=False)
    ad = db.Column(db.String(100), nullable=False)
    aciklama = db.Column(db.String(255), nullable=True)
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)
    aktif = db.Column(db.Boolean, default=True)
    muhasebe_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)

    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_kasa_kod'),)
    
    sube = db.relationship('Sube', back_populates='kasalar')
    # İlişkiyi tanımla
    sorumlu = db.relationship('Kullanici', foreign_keys=[kullanici_id], backref='zimmetli_kasalar')


