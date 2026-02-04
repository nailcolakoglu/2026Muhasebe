"""
Depo Modeli
"""
from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Depo(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'depolar'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=True)
    
    kod = db.Column(db.String(20), nullable=False) 
    ad = db.Column(db.String(50), nullable=False)
    aktif = db.Column(db.Boolean, default=True)
    
    # UUID Kullanıcı İlişkisi (Plasiyer/Sorumlu)
    plasiyer_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    
    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_depo_kod'),)
    
    # İlişkiler
    sube = db.relationship('Sube', back_populates='depolar')
    
    # Plasiyer/Sorumlu (Kullanici Tablosuna Bağlı)
    plasiyer = db.relationship('Kullanici', foreign_keys=[plasiyer_id])

    def __repr__(self):
        return f"<Depo {self.ad}>"