"""
Şube Modeli
"""
from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Sube(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'subeler'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    bolge_id = db.Column(db.String(36), db.ForeignKey('bolgeler.id'), nullable=True)
    
    kod = db.Column(db.String(20), nullable=False)
    ad = db.Column(db.String(50), nullable=False)
    
    # Lokasyon bilgileri
    sehir_id = db.Column(db.String(36), db.ForeignKey('sehirler.id'), nullable=True)
    ilce_id = db.Column(db.String(36), db.ForeignKey('ilceler.id'), nullable=True)
    adres = db.Column(db.String(255))
    telefon = db.Column(db.String(20))

    aktif = db.Column(db.Boolean, default=True)
    
    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_sube_kod'),)
    
    # İlişkiler
    firma = db.relationship('Firma', back_populates='subeler')
    
    # Lokasyon İlişkileri (String ref ile)
    sehir = db.relationship('Sehir')
    ilce = db.relationship('Ilce')
    
    # Alt İlişkiler
    depolar = db.relationship('Depo', back_populates='sube', cascade="all, delete-orphan")
    kasalar = db.relationship('Kasa', back_populates='sube')
    
    # NOT: Kullanıcı yetkileri base.py içinde dinamik veya UserTenantRole ile yönetilir.
    
    def __repr__(self):
        return f"<Sube {self.ad}>"