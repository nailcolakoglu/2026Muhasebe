# app/modules/banka_hareket/models.py

from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey
from app.extensions import db
#from app.models import db
from app.enums import BankaIslemTuru
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class BankaHareket(db.Model):
    __tablename__ = 'banka_hareketleri'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=False)
    
    banka_id = db.Column(db.String(36), db.ForeignKey('banka_hesaplari.id'), nullable=False, index=True)
    
    # Karşı Taraf ID'leri
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True)
    karsi_banka_id = db.Column(db.String(36), db.ForeignKey('banka_hesaplari.id'), nullable=True)
    kasa_id = db.Column(db.String(36), db.ForeignKey('kasalar.id'), nullable=True)
    
    islem_turu = db.Column(db.Enum(BankaIslemTuru, name='banka_islem_turu_enum'), nullable=False)
    
    belge_no = db.Column(db.String(50), index=True)
    tarih = db.Column(db.Date, nullable=False)
    tutar = db.Column(Numeric(18, 2), default=Decimal('0.00')) 
    aciklama = db.Column(db.String(255))
    
    brut_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    komisyon_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    komisyon_orani = db.Column(Numeric(5, 2), default=Decimal('0.00'))
    komisyon_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)

    muhasebe_fisi_id = db.Column(db.String(36), db.ForeignKey('muhasebe_fisleri.id'), nullable=True)
    
    # 👇 EKLENECEK ALAN (HATAYI ÇÖZEN KISIM) 👇
    finans_islem_id = db.Column(db.String(36), db.ForeignKey('finans_islemleri.id'), nullable=True)

    # İlişkiler
    banka = db.relationship('BankaHesap', foreign_keys=[banka_id], backref='hareketler')
    karsi_banka = db.relationship('BankaHesap', foreign_keys=[karsi_banka_id], remote_side="BankaHesap.id")
    cari = db.relationship('CariHesap', backref='banka_hareketleri')
    kasa = db.relationship('Kasa', backref='banka_islemleri')
    muhasebe_fisi = db.relationship('MuhasebeFisi')

    def __repr__(self):
        return f"<BankaHareket {self.belge_no} - {self.tutar}>"