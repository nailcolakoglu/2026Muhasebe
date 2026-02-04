
from app.extensions import db
from datetime import datetime
from sqlalchemy import Numeric, ForeignKey, func
from app.enums import IrsaliyeTuru, IrsaliyeDurumu
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())


class Irsaliye(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'irsaliyeler'
    query_class = FirmaFilteredQuery

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=False)
    
    # 🚨 DÜZELTME: Enum yerine String(50) yapıyoruz ki "Sevk İrsaliyesi" sığsın.
    irsaliye_turu = db.Column(db.String(50), default=IrsaliyeTuru.SEVK.value)
    
    belge_no = db.Column(db.String(50), nullable=False)
    tarih = db.Column(db.Date, nullable=False)
    saat = db.Column(db.Time, nullable=False)
    
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=False)
    depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=False)
    
    aciklama = db.Column(db.String(255))
    durum = db.Column(db.String(20), default=IrsaliyeDurumu.TASLAK.value)
    
    # Bağlantılar
    fatura_id = db.Column(db.String(36), db.ForeignKey('faturalar.id'), nullable=True)
    faturalasti_mi = db.Column(db.Boolean, default=False)

    # E-İrsaliye Alanları
    ettn = db.Column(db.String(36))
    gib_durum_kodu = db.Column(db.Integer, default=0)
    
    sofor_ad = db.Column(db.String(100))
    sofor_soyad = db.Column(db.String(100))
    sofor_tc = db.Column(db.String(11))
    
    plaka_arac = db.Column(db.String(20))
    plaka_dorse = db.Column(db.String(20))
    
    tasiyici_firma_vkn = db.Column(db.String(11))
    tasiyici_firma_unvan = db.Column(db.String(200))

    # İlişkiler
    kalemler = db.relationship('IrsaliyeKalemi', backref='irsaliye', cascade="all, delete-orphan")
    cari = db.relationship('CariHesap')
    depo = db.relationship('Depo')

class IrsaliyeKalemi(db.Model):
    __tablename__ = 'irsaliye_kalemleri'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    irsaliye_id = db.Column(db.String(36), db.ForeignKey('irsaliyeler.id'), nullable=False)
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    miktar = db.Column(Numeric(18, 4), default=0)
    birim = db.Column(db.String(20))
    aciklama = db.Column(db.String(255))
    gtip_kodu = db.Column(db.String(20))
    
    stok = db.relationship('StokKart')