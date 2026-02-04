"""
Fatura Modelleri
Enterprise Grade - Fully Normalized - Firebird Compatible
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Numeric, func, ForeignKey, String, Date, DateTime, Boolean, Text,
    Integer, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from app.extensions import db
# Base modelden gerekli mixinleri ve query sınıfını çekiyoruz
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import (
    FaturaTuru, ParaBirimi, FaturaDurumu, OdemeDurumu,
    EFaturaSenaryo, EFaturaTipi, StokBirimleri
)
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Fatura(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Ana Fatura Modeli (Satış/Alış/İade)
    """
    __tablename__ = 'faturalar'
    query_class = FirmaFilteredQuery
    
    # Primary Key
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    # Foreign Keys (İndeksli)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    donem_id = db.Column(Integer, ForeignKey('donemler.id'), nullable=False, index=True)
    sube_id = db.Column(Integer, ForeignKey('subeler.id'), nullable=False, index=True)
    cari_id = db.Column(Integer, ForeignKey('cari_hesaplar.id'), nullable=False, index=True)
    depo_id = db.Column(Integer, ForeignKey('depolar.id'), nullable=False, index=True)
    
    # Temel Bilgiler
    # Firebird için native_enum=False kullanıyoruz
    fatura_turu = db.Column(db.Enum(FaturaTuru, native_enum=False), default=FaturaTuru.SATIS, nullable=False, index=True)
    belge_no = db.Column(String(50), nullable=False, index=True)
    dis_belge_no = db.Column(String(50))  # Karşı tarafın fatura no
    tarih = db.Column(Date, nullable=False, index=True)
    vade_tarihi = db.Column(Date, index=True)
    fatura_saati = db.Column(DateTime, default=datetime.now)
    gun_adi = db.Column(String(20))  # 'Pazartesi' vs.(Raporlama için)
    
    # Döviz
    doviz_turu = db.Column(db.Enum(ParaBirimi, native_enum=False), default=ParaBirimi.TL)
    doviz_kuru = db.Column(Numeric(10, 4), default=Decimal('1.0000'))
    
    # Kaynak İlişkileri
    kaynak_siparis_id = db.Column(Integer, ForeignKey('siparisler.id'), nullable=True)
    fiyat_listesi_id = db.Column(Integer, ForeignKey('fiyat_listeleri.id'), nullable=True)
    
    # Finansal Tutarlar
    ara_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    kdv_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    iskonto_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    genel_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'), index=True)
    dovizli_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # Personel ve Log (UUID Uyumlu - String 36)
    plasiyer_id = db.Column(String(36), ForeignKey('kullanicilar.id'), nullable=True)
    kaydeden_id = db.Column(String(36), ForeignKey('kullanicilar.id'))
    duzenleyen_id = db.Column(String(36), ForeignKey('kullanicilar.id'))
    
    # Diğer Bilgiler
    sevk_adresi = db.Column(String(255))
    aciklama = db.Column(Text)
    maksimum_iskonto_orani = db.Column(Numeric(5, 2), default=Decimal('0.00'))
    
    # Durum
    odeme_durumu = db.Column(db.Enum(OdemeDurumu, native_enum=False), default=OdemeDurumu.BEKLIYOR, index=True)
    durum = db.Column(db.Enum(FaturaDurumu, native_enum=False), default=FaturaDurumu.TASLAK, nullable=False, index=True)
    aktif = db.Column(Boolean, default=True, index=True)
    
    # Satış Kanalı (CRM)
    satis_kanali = db.Column(String(50))
    musteri_puani = db.Column(Integer)
    
    # İptal
    iptal_mi = db.Column(Boolean, default=False, index=True)
    iptal_nedeni = db.Column(String(200))
    
    # Muhasebe Fişi
    muhasebe_fis_id = db.Column(Integer, ForeignKey('muhasebe_fisleri.id'), nullable=True)
    
    # E-Fatura (GİB Entegrasyonu)
    ettn = db.Column(String(36), unique=True, index=True)  # UUID (E-Fatura Takip No)
    e_fatura_senaryo = db.Column(db.Enum(EFaturaSenaryo, native_enum=False), default=EFaturaSenaryo.TICARIFATURA)
    e_fatura_tipi = db.Column(db.Enum(EFaturaTipi, native_enum=False), default=EFaturaTipi.SATIS)
    gib_durum_kodu = db.Column(Integer, default=0, index=True)  # 0:Hazır, 2:Onaylı, 3:Hata
    gib_durum_aciklama = db.Column(String(255))
    xml_path = db.Column(String(255))
    
    # E-Fatura Detay
    zarf_uuid = db.Column(String(36))
    alici_etiket_pk = db.Column(String(100))
    gonderen_etiket_gb = db.Column(String(100))
    gib_gonderim_tarihi = db.Column(DateTime)
    gib_yanit_tarihi = db.Column(DateTime)
    
    # İade Durumu
    iade_edilen_fatura_no = db.Column(String(50))
    iade_edilen_fatura_tarihi = db.Column(Date)
    
    # İnternet Satışı
    internet_satisi_mi = db.Column(Boolean, default=False)
    web_sitesi_adresi = db.Column(String(255))
    odeme_sekli_detay = db.Column(String(50))
    odeme_plani_id = db.Column(Integer, ForeignKey('odeme_planlari.id'))
    
    # Taşıyıcı Bilgileri (E-İrsaliye)
    tasiyici_vkn_tckn = db.Column(String(20))
    tasiyici_unvan = db.Column(String(200))
    tasiyici_adres = db.Column(String(255))
    gonderim_tarihi_saati = db.Column(DateTime)
    
    # --- İLİŞKİLER ---
    kalemler = relationship('FaturaKalemi', back_populates='fatura', cascade="all, delete-orphan")
    cari = relationship('CariHesap', back_populates='faturalar')
    depo = relationship('Depo')
    
    plasiyer = relationship('Kullanici', foreign_keys=[plasiyer_id], backref='plasiyer_faturalari')
    kaydeden = relationship('Kullanici', foreign_keys=[kaydeden_id], backref='kaydettigi_faturalar')
    duzenleyen = relationship('Kullanici', foreign_keys=[duzenleyen_id], backref='duzenledigi_faturalar')
    
    kaynak_siparis = relationship('Siparis', backref='olusan_faturalar', foreign_keys=[kaynak_siparis_id])
    muhasebe_fisi = relationship('MuhasebeFisi', backref=db.backref('fatura_kaynagi', uselist=False), foreign_keys=[muhasebe_fis_id])
    
    # --- COMPUTED PROPERTIES (TALEP ETTİĞİN KISIMLAR) ---
    @property
    def genel_toplam_yazi_ile(self) -> str:
        """Tutarı yazıya çevirir: 'BİN İKİ YÜZ ELLİ TÜRK LİRASI'"""
        try:
            from app.araclar import sayiyi_yaziya_cevir
            tutar = self.genel_toplam or Decimal('0.00')
            return sayiyi_yaziya_cevir(tutar)
        except ImportError:
            return str(self.genel_toplam)
    
    @property
    def odeme_yuzdesi(self) -> float:
        """Ödeme yüzdesini hesaplar (0-100)"""
        if not self.genel_toplam or self.genel_toplam == 0:
            return 0.0
        
        # Basit mantık: Duruma göre yüzde dön
        if self.odeme_durumu == OdemeDurumu.TAMAMEN: 
            return 100.0
        elif self.odeme_durumu == OdemeDurumu.KISMEN:
            # İleride Cari Hareketlerden gerçek tahsilat toplanarak buraya yazılabilir.
            return 50.0  
        else:
            return 0.0
    
    # --- VALİDASYONLAR ---
    @validates('belge_no')
    def validate_belge_no(self, key, value):
        if not value or not value.strip():
            raise ValueError("Belge numarası boş olamaz")
        return value.strip().upper()
    
    @validates('doviz_kuru')
    def validate_kur(self, key, value):
        if value is None or value <= 0:
            raise ValueError("Döviz kuru 0'dan büyük olmalıdır")
        return value
    
    # --- DATABASE CONSTRAINTS ---
    __table_args__ = (
        UniqueConstraint('firma_id', 'belge_no', 'fatura_turu', name='uq_fatura_no'),
        Index('ix_fatura_tarih_durum', 'tarih', 'durum'),
        Index('ix_fatura_cari_tarih', 'cari_id', 'tarih'),
        CheckConstraint('genel_toplam >= 0', name='ck_fatura_genel_toplam'),
        CheckConstraint('doviz_kuru > 0', name='ck_fatura_doviz_kuru'),
    )
    
    def __repr__(self):
        return f"<Fatura {self.belge_no} - {self.genel_toplam} {self.doviz_turu}>"


class FaturaKalemi(db.Model):
    """
    Fatura Satır Detayları (Line Items)
    """
    __tablename__ = 'fatura_kalemleri'
    
    # Primary Key
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    # Foreign Keys (İndeksli)
    fatura_id = db.Column(Integer, ForeignKey('faturalar.id'), nullable=False, index=True)
    stok_id = db.Column(Integer, ForeignKey('stok_kartlari.id'), nullable=False, index=True)
    
    # Temel Veriler
    miktar = db.Column(Numeric(18, 4), default=Decimal('1.0000'))
    birim = db.Column(db.Enum(StokBirimleri, native_enum=False), default=StokBirimleri.ADET)
    birim_fiyat = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # İskonto
    iskonto_orani = db.Column(Numeric(5, 2), default=Decimal('0.00'))
    iskonto_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # KDV
    kdv_orani = db.Column(Numeric(5, 2), default=Decimal('20.00'))
    kdv_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # Tutarlar (Hesaplanmış)
    tutar = db.Column(Numeric(18, 2), default=Decimal('0.00'))  # Brüt (Miktar × Fiyat)
    net_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00'))  # Matrah (Tutar - İskonto)
    satir_toplami = db.Column(Numeric(18, 2), default=Decimal('0.00'))  # Yekün (Net + KDV)
    
    # Açıklama
    aciklama = db.Column(String(255))
    
    # Sıra
    sira_no = db.Column(Integer, default=1)
    paket_mi = db.Column(Boolean, default=False)
    
    # Tevkifat (E-Fatura)
    tevkifat_kodu = db.Column(String(10))
    tevkifat_payi = db.Column(Integer, default=0)
    tevkifat_paydasi = db.Column(Integer, default=10)
    
    # Gümrük (İhracat)
    gtip_kodu = db.Column(String(20))
    
    # GİB Baskı Notu
    satir_aciklamasi = db.Column(String(255))
    
    # --- İLİŞKİLER ---
    fatura = relationship('Fatura', back_populates='kalemler')
    stok = relationship('StokKart', back_populates='fatura_kalemleri')
    
    # --- VALİDASYONLAR ---
    @validates('miktar')
    def validate_miktar(self, key, value):
        if value is None or value <= 0:
            raise ValueError("Miktar 0'dan büyük olmalıdır")
        return value
    
    @validates('birim_fiyat')
    def validate_fiyat(self, key, value):
        if value is None or value < 0:
            raise ValueError("Fiyat negatif olamaz")
        return value
    
    # --- DATABASE CONSTRAINTS ---
    __table_args__ = (
        Index('ix_fatura_kalem_fatura_stok', 'fatura_id', 'stok_id'),
        CheckConstraint('miktar > 0', name='ck_kalem_miktar'),
        CheckConstraint('birim_fiyat >= 0', name='ck_kalem_fiyat'),
    )
    
    def __repr__(self):
        return f"<FaturaKalemi Fatura:{self.fatura_id} Stok:{self.stok_id} Miktar:{self.miktar}>"