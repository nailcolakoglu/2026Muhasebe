# app/modules/kasa_hareket/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey
from app.extensions import db
#from app.models import db
from app.enums import BankaIslemTuru
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class KasaHareket(db.Model):
    __tablename__ = 'kasa_hareketleri'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=True) # nullable=True yaptım, hata vermesin
    
    kasa_id = db.Column(db.String(36), db.ForeignKey('kasalar.id'), nullable=False, index=True)
    
    # ...(Diğer alanlar aynen kalıyor) ...
    islem_turu = db.Column(db.Enum(BankaIslemTuru, name='kasa_islem_turu_enum'), nullable=False)
    belge_no = db.Column(db.String(50), index=True)
    tarih = db.Column(db.Date, nullable=False, default=datetime.now)
    tutar = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    aciklama = db.Column(db.String(255))
    
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True)
    banka_id = db.Column(db.String(36), db.ForeignKey('banka_hesaplari.id'), nullable=True)
    karsi_kasa_id = db.Column(db.String(36), db.ForeignKey('kasalar.id'), nullable=True)
    muhasebe_fisi_id = db.Column(db.String(36), db.ForeignKey('muhasebe_fisleri.id'), nullable=True)
    plasiyer_id = db.Column(db.String(36), nullable=True)
    onaylandi = db.Column(db.Boolean, default=False)

    # 👇 EKLENECEK ALAN (Hata Çözümü İçin) 👇
    # Finans modülü eski yapıdan dolayı buraya bağlanmaya çalışıyor.
    finans_islem_id = db.Column(db.String(36), db.ForeignKey('finans_islemleri.id'), nullable=True)

    # İlişkiler
    kasa = db.relationship('Kasa', foreign_keys=[kasa_id], backref='hareketler')
    karsi_kasa = db.relationship('Kasa', foreign_keys=[karsi_kasa_id])
    cari = db.relationship('CariHesap', backref='kasa_hareketleri')
    banka = db.relationship('BankaHesap', backref='kasa_hareketleri')
    muhasebe_fisi = db.relationship('MuhasebeFisi')
    
    # FinansIslem ilişkisi için (Opsiyonel ama önerilir)
    #finans_islem = db.relationship('FinansIslem', backref='kasa_hareketleri_ref')

    def __repr__(self):
        return f"<KasaHareket {self.belge_no} - {self.tutar}>"