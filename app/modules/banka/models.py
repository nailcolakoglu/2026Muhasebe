# app/modules/banka/models.py

from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin

#from app.models import db    
from app.enums import (BankaHesapTuru, ParaBirimi)
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class BankaHesap(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'banka_hesaplari'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    # Şirketin hangi şubesine ait? (Merkez, Fabrika vs.)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=True) 

    # --- KİMLİK BİLGİLERİ ---
    kod = db.Column(db.String(20), nullable=False)
    banka_adi = db.Column(db.String(50), nullable=False) # Ziraat, Garanti vb.
    sube_adi = db.Column(db.String(100)) # Banka Şubesi (Örn: Kadıköy Şubesi)
    ad = db.Column(db.String(100), nullable=False) # Bizdeki Adı: "Merkez Maaş Hesabı"
    
    # --- TÜR VE DETAY ---
    hesap_turu = db.Column(db.Enum(BankaHesapTuru), default=BankaHesapTuru.VADESIZ, nullable=False)
    
    hesap_no = db.Column(db.String(50))
    iban = db.Column(db.String(34)) # IBAN standart max 34 karakterdir
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)
    
    # --- FİNANSAL DURUM ---
    # Hassasiyeti (18, 4) yaptık.Banka mutabakatlarında kuruş farkı çıkmaz.
    bakiye = db.Column(Numeric(18, 4), default=Decimal('0.0000'))
    
    # Eğer Kredi Kartı ise Limit Takibi için:
    kredi_limiti = db.Column(Numeric(18, 2), default=Decimal('0.00')) 
    
    # Kredi Kartı ise: Her ayın kaçında kesiliyor? (Örn: 15'i)
    hesap_kesim_gunu = db.Column(db.Integer, nullable=True) 
    
    # --- ENTEGRASYON VE İLETİŞİM ---
    aktif = db.Column(db.Boolean, default=True)
    
    # Muhasebe Entegrasyonu (102 BANKALAR veya 300 KREDİLER)
    muhasebe_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)
    
    # Bankadaki Temsilci (Acil durumda aranacak kişi)
    temsilci_adi = db.Column(db.String(100), nullable=True)
    temsilci_tel = db.Column(db.String(20), nullable=True)

    # İlişkiler
    firma = db.relationship('Firma', backref='bankalar')
    sube = db.relationship('Sube', backref='bankalar') # Şirket şubesi
    muhasebe_hesap = db.relationship('HesapPlani', backref='bankalar')
    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_banka_kod'),)
    def __repr__(self):
        return f"<Banka {self.kod} - {self.ad}>"
