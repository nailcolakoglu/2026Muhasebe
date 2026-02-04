# modules/fiyat/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import StokKartTipi, ParaBirimi, HareketTuru
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class FiyatListesi(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Dönemsel veya Özel Fiyat Listeleri
    Örn: '2025 Kış Kampanyası', 'Bayi Fiyat Listesi'
    """
    __tablename__ = 'fiyat_listeleri'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    kod = db.Column(db.String(50), nullable=False) # LST-001
    ad = db.Column(db.String(100), nullable=False) # Perakende Listesi
    
    baslangic_tarihi = db.Column(db.Date)
    bitis_tarihi = db.Column(db.Date)
    
    aktif = db.Column(db.Boolean, default=True)
    varsayilan = db.Column(db.Boolean, default=False) # Genel geçerli liste mi?
    
    # Öncelik (Birden fazla liste çakışırsa hangisi geçerli? Yüksek olan ezer)
    oncelik = db.Column(db.Integer, default=0) 
    
    aciklama = db.Column(db.String(255))
    
    detaylar = db.relationship('FiyatListesiDetay', backref='liste', cascade="all, delete-orphan")
    
    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_fiyat_liste_kod'),)

class FiyatListesiDetay(db.Model):
    """
    Listeye ait ürün fiyatları
    """
    __tablename__ = 'fiyat_listesi_detaylari'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    fiyat_listesi_id = db.Column(db.String(36), db.ForeignKey('fiyat_listeleri.id'), nullable=False)
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    fiyat = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    doviz = db.Column(db.String(3), default='TL')
    
    # Kampanya: Fiyat yerine İskonto oranı da tanımlanabilir
    iskonto_orani = db.Column(Numeric(5, 2), default=Decimal('0.00')) 
    
    # Bu fiyatın geçerli olması için minimum alım adedi (Toptan satışlar için)
    min_miktar = db.Column(Numeric(15, 4), default=Decimal('0.0000'))
    
    stok = db.relationship('StokKart')
    
    # Bir listede aynı stoktan 1 tane olabilir (Miktar baremi yoksa)
    # Eğer baremli fiyat yapacaksak constraint değişmeli.Şimdilik basit tutalım.
    #__table_args__ = (UniqueConstraint('fiyat_listesi_id', 'stok_id', 'min_miktar', name='uq_fiyat_detay'),)
    #__table_args__ = (UniqueConstraint('fiyat_listesi_id', 'stok_id', name='uq_fiyat_detay'),)
    __table_args__ = (UniqueConstraint('fiyat_listesi_id', 'stok_id', 'doviz', 'min_miktar', name='uq_fiyat_detay'),)
    
