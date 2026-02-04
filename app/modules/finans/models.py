# app/modules/finans/models.py

from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey, func
#from app.models import db
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import FinansIslemTuru, ParaBirimi, IslemDurumu
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class FinansIslem(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'finans_islemleri'
    query_class = FirmaFilteredQuery
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    # Zorunlu Bağlantılar
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=False)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=False)
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True) # Virman işlemlerinde cari olmayabilir, nullable=True yaptım
    
    # İşlem Detayları
    islem_turu = db.Column(db.Enum(FinansIslemTuru), default=FinansIslemTuru.TAHSILAT, nullable=False)
    belge_no = db.Column(db.String(50), nullable=False, index=True)
    tarih = db.Column(db.Date, nullable=False)
    
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)   
    doviz_kuru = db.Column(Numeric(10, 4), default=Decimal('1.0000')) # Kur hassasiyeti artırıldı
    aciklama = db.Column(db.String(255))

    # Kullanıcılar
    plasiyer_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    onaylayan_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    durum = db.Column(db.Enum(IslemDurumu), default=IslemDurumu.BEKLIYOR)
    
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Toplamlar
    toplam_nakit = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    toplam_cek = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    toplam_senet = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    genel_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # --- İLİŞKİLER ---
    # backref='finans_islemleri' çakışma yaratabilir, unique isim veriyoruz: 'finans_islem_listesi'
    cari = db.relationship('CariHesap', backref='finans_islem_listesi')
    
    # Bu ilişkilerin çalışması için KasaHareket modelinde 'finans_islem_id' alanı MUTLAKA OLMALIDIR.
    # cascade="all, delete-orphan" -> Finans kaydı silinirse, bağlı kasa/banka hareketleri de silinir.
    kasa_hareketleri = db.relationship('KasaHareket', backref='finans_islem_ref', lazy='dynamic', cascade="all, delete-orphan")
    banka_hareketleri = db.relationship('BankaHareket', backref='finans_islem_ref', lazy='dynamic', cascade="all, delete-orphan")
    cek_senetler = db.relationship('CekSenet', backref='finans_islem_ref', lazy='dynamic', cascade="all, delete-orphan")
    kasa_hareketleri = db.relationship(
        'KasaHareket', 
        backref='finans_islem',  # <-- BURAYI GÜNCELLEYİN ('finans_islem_ref' yerine 'finans_islem')
        lazy='dynamic', 
        cascade="all, delete-orphan"
    )
    
    # Aynı şeyi Banka ve Çek için de yapın:
    banka_hareketleri = db.relationship(
        'BankaHareket', 
        backref='finans_islem', 
        lazy='dynamic', 
        cascade="all, delete-orphan"
    )
    
    cek_senetler = db.relationship(
        'CekSenet', 
        backref='finans_islem', 
        lazy='dynamic', 
        cascade="all, delete-orphan"
    )
    def __repr__(self):
        return f"<FinansIslem {self.belge_no} - {self.genel_toplam}>"