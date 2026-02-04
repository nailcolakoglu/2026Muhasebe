# modules/doviz/models.py

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

class DovizKuru(db.Model):
    __tablename__ = 'doviz_kurlari'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    tarih = db.Column(db.Date, nullable=False, default=datetime.now)
    
    kod = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL, nullable=False)
    ad = db.Column(db.String(50)) # ABD DOLARI
    
    alis = db.Column(Numeric(10, 4), default=Decimal('0.0000'))      # Forex Buying
    satis = db.Column(Numeric(10, 4), default=Decimal('0.0000'))     # Forex Selling
    efektif_alis = db.Column(Numeric(10, 4), default=Decimal('0.0000')) # Banknote Buying
    efektif_satis = db.Column(Numeric(10, 4), default=Decimal('0.0000')) # Banknote Selling

    # AI Analizi İçin (Kurun o günkü volatilitesi)
    kapanis = db.Column(Numeric(10, 4), nullable=True)

    # Aynı gün aynı para biriminden sadece 1 tane olabilir
    __table_args__ = (UniqueConstraint('tarih', 'kod', name='uq_gunluk_kur'),)

