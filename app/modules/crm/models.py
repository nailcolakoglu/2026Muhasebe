# app/modules/crm/models.py

import enum
import uuid
from decimal import Decimal
from sqlalchemy import Numeric, JSON  # ✨ DÜZELTME: JSON buraya eklendi
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import CrmAdayDurumu, CrmFirsatAsamasi, CrmAktiviteTipi


class IslemTuruEnum(enum.Enum):
    ARAMA = 'ARAMA'
    ZIYARET = 'ZIYARET'
    EMAIL = 'EMAIL'
    TOPLANTI = 'TOPLANTI'
    SIKAYET = 'SIKAYET'
    TALEP = 'TALEP'
    TEKLIF = 'TEKLIF'
    NOTLAR = 'NOTLAR'

class DuyguDurumuEnum(enum.Enum):
    MUTLU = 'MUTLU'
    NORMAL = 'NORMAL'
    MUTSUZ = 'MUTSUZ'
    SINIRLI = 'SINIRLI'
    BELIRSIZ = 'BELIRSIZ'


def generate_uuid():
    return str(uuid.uuid4())

class AdayMusteri(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'crm_aday_musteriler'
    query_class = FirmaFilteredQuery
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    unvan = db.Column(db.String(200), nullable=False)
    yetkili_kisi = db.Column(db.String(100))
    telefon = db.Column(db.String(20))
    eposta = db.Column(db.String(100))
    sektor = db.Column(db.String(100))
    kaynak = db.Column(db.String(100)) 
    durum = db.Column(db.Enum(CrmAdayDurumu), default=CrmAdayDurumu.YENI, nullable=False)
    temsilci_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    donusturulen_cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True)
    notlar = db.Column(db.Text)

    firsatlar = db.relationship('SatisFirsati', back_populates='aday', lazy='dynamic')

class SatisAsamasi(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'crm_satis_asamalari'
    query_class = FirmaFilteredQuery
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    ad = db.Column(db.String(50), nullable=False)
    sira = db.Column(db.Integer, default=0)
    renk = db.Column(db.String(10), default='#0d6efd')
    
    firsatlar = db.relationship('SatisFirsati', back_populates='asama_obj', lazy='select')

class SatisFirsati(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'crm_satis_firsatlari'
    query_class = FirmaFilteredQuery
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    baslik = db.Column(db.String(200), nullable=False)
    aday_id = db.Column(db.String(36), db.ForeignKey('crm_aday_musteriler.id'), nullable=True)
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True)
    asama_id = db.Column(db.String(36), db.ForeignKey('crm_satis_asamalari.id'), index=True)
    temsilci_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))
    tahmini_tutar = db.Column(Numeric(18, 2), default=0.00)
    para_birimi = db.Column(db.String(5), default='TL')
    kaybedilme_nedeni = db.Column(db.String(255), nullable=True)
    
    # AI Sahaları
    ai_olasilik = db.Column(db.Integer, default=0)
    ai_analiz = db.Column(JSON)
    
    beklenen_kapanis_tarihi = db.Column(db.Date)

    aday = db.relationship('AdayMusteri', back_populates='firsatlar')
    cari = db.relationship('CariHesap', foreign_keys=[cari_id], backref='firsatlar')
    #aday = db.relationship('AdayMusteri', foreign_keys=[aday_id], backref='firsatlar')

    asama_obj = db.relationship('SatisAsamasi', back_populates='firsatlar', lazy='joined')
    aktiviteler = db.relationship('CrmAktivite', back_populates='firsat', cascade='all, delete-orphan')

class CrmAktivite(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'crm_aktiviteler'
    query_class = FirmaFilteredQuery
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    konu = db.Column(db.String(200), nullable=False)
    aktivite_tipi = db.Column(db.Enum(CrmAktiviteTipi), nullable=False)
    tarih = db.Column(db.DateTime, nullable=False)
    tamamlandi = db.Column(db.Boolean, default=False)
    notlar = db.Column(db.Text)
    aday_id = db.Column(db.String(36), db.ForeignKey('crm_aday_musteriler.id'), nullable=True)
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True)
    firsat_id = db.Column(db.String(36), db.ForeignKey('crm_satis_firsatlari.id'), nullable=True)
    kullanici_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=False)

    firsat = db.relationship('SatisFirsati', back_populates='aktiviteler')

class CrmHareketi(db.Model, TimestampMixin):
    __tablename__ = 'crm_hareketleri'
    
    # ✨ ÇÖZÜM: Bu satır tablo çakışmalarını kökten çözer
    __table_args__ = {'extend_existing': True}
    
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=False)
    plasiyer_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=False)
    
    tarih = db.Column(db.DateTime, nullable=False)
    islem_turu = db.Column(db.Enum(IslemTuruEnum), nullable=False)
    konu = db.Column(db.String(200))
    detay_notu = db.Column(db.Text)
    
    # AI ve Analiz Sahaları
    duygu_durumu = db.Column(db.Enum(DuyguDurumuEnum), default=DuyguDurumuEnum.BELIRSIZ)
    memnuniyet_skoru = db.Column(db.Integer, default=5) # 1 ile 10 arası
    
    # Görev/Aksiyon Takibi
    aksiyon_gerekli = db.Column(db.Boolean, default=False)
    aksiyon_tarihi = db.Column(db.DateTime)
    aksiyon_tamamlandi = db.Column(db.Boolean, default=False)
    
    ai_metadata = db.Column(JSON) # İleride AI'dan dönen JSON yanıtlarını buraya gömeceğiz
    
    # İlişkiler
    cari = db.relationship('CariHesap', foreign_keys=[cari_id], backref='etkilesimler')
    plasiyer = db.relationship('Kullanici', foreign_keys=[plasiyer_id])    
    
class CrmFirsatLogu(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'crm_firsat_loglari'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    firsat_id = db.Column(db.String(36), db.ForeignKey('crm_satis_firsatlari.id'), nullable=False, index=True)
    kullanici_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=False)
    
    islem_turu = db.Column(db.String(50), nullable=False) # 'ASAMA_DEGISIMI' vb.
    eski_deger = db.Column(db.String(255), nullable=True)
    yeni_deger = db.Column(db.String(255), nullable=True)
    aciklama = db.Column(db.Text, nullable=True)
    
    firsat = db.relationship('SatisFirsati', backref=db.backref('loglar', lazy='dynamic', cascade='all, delete-orphan'))
    
    