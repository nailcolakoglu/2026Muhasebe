# app/modules/depo/models.py
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

class DepoLokasyon(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Depo içindeki rafları/koridorları tanımlar. (Örn: A-Blok, Kuru Gıda Rafı, Soğuk Hava vb.)
    """
    __tablename__ = 'depo_lokasyonlari'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=False)
    
    kod = db.Column(db.String(20), nullable=False) # Örn: A-01, B-02
    ad = db.Column(db.String(50), nullable=False)  # Örn: A Koridoru 1. Raf
    barkod = db.Column(db.String(50), nullable=True) # Rafa yapıştırılan fiziksel barkod
    
    # Lokasyon Özellikleri
    hacim_m3 = db.Column(db.Float, nullable=True) # Rafın alabileceği max hacim
    tasima_kapasitesi_kg = db.Column(db.Float, nullable=True) # Rafın taşıyabileceği max ağırlık
    
    aktif = db.Column(db.Boolean, default=True)
    
    # İlişkiler
    depo = db.relationship('Depo', backref=db.backref('lokasyonlar', lazy='dynamic'))

    __table_args__ = (UniqueConstraint('depo_id', 'kod', name='uq_depo_lokasyon_kod'),)

    def __repr__(self):
        return f"<Lokasyon {self.kod} - {self.ad}>"


class StokLokasyonBakiye(db.Model, TimestampMixin):
    """
    Hangi ürünün, hangi depoda ve HANGİ LOKASYONDA/RAFTA ne kadar olduğunu tutar.
    WMS sisteminin (El Terminali) kalbidir.
    """
    __tablename__ = 'stok_lokasyon_bakiyeleri'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=False)
    lokasyon_id = db.Column(db.String(36), db.ForeignKey('depo_lokasyonlari.id'), nullable=False)
    
    miktar = db.Column(db.Numeric(18, 4), default=0)
    rezerve_miktar = db.Column(db.Numeric(18, 4), default=0) # Bekleyen siparişler için ayrılan miktar
    
    # İlişkiler
    stok = db.relationship('StokKart')
    depo = db.relationship('Depo')
    lokasyon = db.relationship('DepoLokasyon')
    
    __table_args__ = (UniqueConstraint('stok_id', 'depo_id', 'lokasyon_id', name='uq_stok_lokasyon'),)        