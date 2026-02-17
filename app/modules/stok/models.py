# app/modules/stok/models.py
"""
Stok Modelleri - MySQL Optimized + AI Enhanced
Enterprise Grade - Multi-Tenant - Full Normalized
"""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Numeric, func, ForeignKey, String, Date, DateTime, Boolean, Text,
    Integer, UniqueConstraint, Index, CheckConstraint, and_, or_
)
from sqlalchemy.dialects.mysql import CHAR, JSON, LONGTEXT, ENUM, DECIMAL
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import StokKartTipi, ParaBirimi, HareketTuru
import uuid
import logging

logger = logging.getLogger(__name__)

# ========================================
# UUID GENERATOR
# ========================================
def generate_uuid():
    """MySQL CHAR(36) için UUID string üret"""
    return str(uuid.uuid4())


# ========================================
# STOK KART MODELİ (AI + MySQL Optimized)
# ========================================
class StokKart(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Stok Kartları - Ana Ürün Tanım Tablosu
    
    Özellikler:
    - Multi-tenant (firma_id)
    - Soft delete
    - AI metadata desteği
    - Full-text search
    - Composite index'ler
    - Paket ürün desteği
    """
    __tablename__ = 'stok_kartlari'
    query_class = FirmaFilteredQuery
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    firma_id = db.Column(
        CHAR(36),
        db.ForeignKey('firmalar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # TEMEL KİMLİK
    # ========================================
    kod = db.Column(
        String(50),
        nullable=False,
        index=True,
        comment='Stok kodu (STK-0001)'
    )
    
    ad = db.Column(
        String(200),
        nullable=False,
        index=True,
        comment='Ürün adı'
    )
    
    barkod = db.Column(
        String(50),
        unique=True,
        index=True,
        comment='Barkod numarası (unique)'
    )
    
    uretici_kodu = db.Column(
        String(50),
        index=True,
        comment='Üretici/MPN kodu'
    )
    
    # ========================================
    # TÜR VE YAPI
    # ========================================
    birim = db.Column(
        ENUM('ADET', 'KG', 'LT', 'MT', 'M2', 'M3', 'KUTU', 'KOLI', 'PALET', name='stok_birim_enum'),
        default='ADET',
        nullable=False
    )
    
    tip = db.Column(
        ENUM('STANDART', 'HIZMET', 'PAKET', 'MAMUL', 'YARI_MAMUL', 'HAMMADDE', name='stok_tip_enum'),
        default='STANDART',
        nullable=False,
        index=True
    )
    
    kategori_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kategorileri.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # ========================================
    # FİNANSAL VERİLER
    # ========================================
    alis_fiyati = db.Column(
        DECIMAL(18, 6),
        default=Decimal('0.000000'),
        nullable=False,
        comment='Alış fiyatı (bağlı sermaye için)'
    )
    
    satis_fiyati = db.Column(
        DECIMAL(18, 6),
        default=Decimal('0.000000'),
        nullable=False,
        index=True,
        comment='Satış fiyatı (kar marjı için)'
    )
    
    doviz_turu = db.Column(
        ENUM('TL', 'USD', 'EUR', 'GBP', name='para_birimi_enum'),
        default='TL',
        nullable=False,
        index=True
    )
    
    # ========================================
    # MUHASEBE & VERGİ (Grup Yapısı)
    # ========================================
    muhasebe_kod_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_muhasebe_gruplari.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    kdv_kod_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kdv_gruplari.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # ========================================
    # LOJİSTİK & AI ANALİZ ALANLARI
    # ========================================
    kritik_seviye = db.Column(
        DECIMAL(18, 6),
        default=Decimal('0.000000'),
        comment='Kritik stok seviyesi (AI uyarı için)'
    )
    
    tedarik_suresi_gun = db.Column(
        Integer,
        default=3,
        comment='Tedarik süresi (gün) - AI tahmin için'
    )
    
    raf_omru_gun = db.Column(
        Integer,
        default=0,
        comment='Raf ömrü (gün) - Fire hesabı için'
    )
    
    garanti_suresi_ay = db.Column(
        Integer,
        default=24,
        comment='Garanti süresi (ay)'
    )
    
    # Boyutlar (Kargo maliyeti tahmini)
    agirlik_kg = db.Column(
        DECIMAL(10, 4),
        default=Decimal('0.0000')
    )
    
    desi = db.Column(
        DECIMAL(10, 3),
        default=Decimal('0.000')
    )
    
    # ========================================
    # TEDARİK ZİNCİRİ & MEVSİMSELLİK
    # ========================================
    tedarikci_id = db.Column(
        CHAR(36),
        db.ForeignKey('cari_hesaplar.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    mevsimsel_grup = db.Column(
        ENUM('', 'KIS', 'YAZ', 'ILKBAHAR', 'SONBAHAR', 'OKUL', 'YILBASI', name='mevsim_enum'),
        default='',
        index=True,
        comment='Mevsimsellik (AI tahmin için)'
    )
    
    # ========================================
    # SEGMENTASYON
    # ========================================
    marka = db.Column(
        String(100),
        index=True,
        comment='Marka (segmentasyon için)'
    )
    
    model = db.Column(
        String(100),
        comment='Model'
    )
    
    mensei = db.Column(
        String(50),
        index=True,
        comment='Menşei (tedarik riski için)'
    )
    
    # ========================================
    # DETAY VE NLP
    # ========================================
    anahtar_kelimeler = db.Column(
        String(500),
        comment='Anahtar kelimeler (arama için)'
    )
    
    aciklama_detay = db.Column(
        LONGTEXT,
        comment='Detaylı açıklama (AI/SEO için)'
    )
    
    ozel_kod1 = db.Column(String(50))
    ozel_kod2 = db.Column(String(50))
    
    # ========================================
    # MEDYA
    # ========================================
    resim_path = db.Column(String(500))
    
    # ========================================
    # DURUM
    # ========================================
    aktif = db.Column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )
    
    # ========================================
    # YAPAY ZEKA METADATA
    # ========================================
    ai_metadata = db.Column(
        JSON,
        nullable=True,
        comment='AI analizleri için esnek veri'
    )
    # Örnek ai_metadata:
    # {
    #     "tahmin_edilen_satis": 150,
    #     "mevsimsel_trend": "yukselis",
    #     "olu_stok_riski": false,
    #     "capraz_satis_urunler": ["id1", "id2"],
    #     "kar_marji_yuzde": 35.5,
    #     "stok_devir_hizi": 12.5
    # }
    
    ai_tahmin_miktar = db.Column(
        DECIMAL(18, 4),
        comment='AI tahmini satış miktarı (sonraki ay)'
    )
    
    ai_olu_stok_riski = db.Column(
        Boolean,
        default=False,
        index=True,
        comment='Ölü stok riski var mı?'
    )
    
    ai_stok_devir_hizi = db.Column(
        DECIMAL(10, 2),
        comment='Stok devir hızı (AI hesaplaması)'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    kategori = relationship('StokKategori', backref='urunler', lazy='select')
    tedarikci = relationship('CariHesap', foreign_keys=[tedarikci_id], backref='tedarik_edilen_urunler', lazy='select')
    muhasebe_grubu = relationship('StokMuhasebeGrubu', backref='stoklar', lazy='select')
    kdv_grubu = relationship('StokKDVGrubu', backref='stoklar', lazy='select')
    
    # Hareketler (lazy='dynamic' - sayfalama için)
    hareketler = relationship(
        'StokHareketi',
        backref='stok_rel',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    # Depo durumları
    depo_durumlari = relationship(
        'StokDepoDurumu',
        back_populates='stok',
        lazy='joined',
        cascade='all, delete-orphan'
    )
    
    # Fatura kalemleri (satış analizi için)
    fatura_kalemleri = relationship(
        'FaturaKalemi',
        back_populates='stok',
        lazy='dynamic'
    )
    
    # Paket içeriği
    paket_icerigi = relationship(
        'StokPaketIcerigi',
        foreign_keys='StokPaketIcerigi.paket_stok_id',
        backref='paket',
        lazy='joined',
        cascade='all, delete-orphan'
    )
    
    paket_ana_urun = relationship(
        'StokPaketIcerigi',
        foreign_keys='StokPaketIcerigi.alt_stok_id',
        backref='alt_urun',
        lazy='select'
    )
    
    # ========================================
    # COMPOSITE INDEXES
    # ========================================
    __table_args__ = (
        # --- PRIMARY INDEXES ---
        # 1. Firma bazlı sorgular (Multi-tenant)
        Index('idx_stok_firma_kod', 'firma_id', 'kod'),
        Index('idx_stok_firma_ad', 'firma_id', 'ad'),
        
        # 2. Barkod araması
        Index('idx_stok_barkod', 'barkod'),
        
        # 3. Kategori bazlı
        Index('idx_stok_kategori', 'kategori_id', 'aktif'),
        
        # 4. Fiyat aralığı sorguları
        Index('idx_stok_fiyat', 'satis_fiyati', 'aktif'),
        
        # 5. Marka/Model
        Index('idx_stok_marka', 'marka', 'aktif'),
        
        # 6. Mevsimsellik
        Index('idx_stok_mevsim', 'mevsimsel_grup'),
        
        # 7. Tedarikçi
        Index('idx_stok_tedarikci', 'tedarikci_id'),
        
        # 8. AI analizleri
        Index('idx_stok_ai_olu', 'ai_olu_stok_riski'),
        
        # 9. Tip bazlı
        Index('idx_stok_tip', 'tip', 'aktif'),
        
        # --- FULL-TEXT SEARCH ---
        # 10. Ürün arama (MySQL Full-Text)
        Index('idx_stok_fulltext', 'ad', 'anahtar_kelimeler', 'aciklama_detay', mysql_prefix='FULLTEXT'),
        
        # --- UNIQUE CONSTRAINTS ---
        # 11. Firma + Kod unique
        UniqueConstraint('firma_id', 'kod', name='uq_stok_kod'),
        
        # 12. Barkod unique (global)
        UniqueConstraint('barkod', name='uq_stok_barkod'),
        
        # --- CHECK CONSTRAINTS ---
        CheckConstraint('alis_fiyati >= 0', name='chk_stok_alis_fiyat'),
        CheckConstraint('satis_fiyati >= 0', name='chk_stok_satis_fiyat'),
        CheckConstraint('kritik_seviye >= 0', name='chk_stok_kritik_seviye'),
        
        {'comment': 'Stok kartları - AI destekli ürün yönetimi'}
    )
    
    # ========================================
    # HYBRID PROPERTIES
    # ========================================
    @hybrid_property
    def kar_marji(self) -> Decimal:
        """Kar marjı hesapla (%)"""
        if not self.satis_fiyati or self.satis_fiyati == 0:
            return Decimal('0.00')
        
        kar = self.satis_fiyati - self.alis_fiyati
        return (kar / self.satis_fiyati * 100).quantize(Decimal('0.01'))
    
    @hybrid_property
    def toplam_stok(self) -> Decimal:
        """Tüm depolardaki toplam stok"""
        toplam = Decimal('0.000000')
        for durum in self.depo_durumlari:
            toplam += durum.miktar or Decimal('0.000000')
        return toplam
    
    @hybrid_property
    def kritik_seviye_altinda_mi(self) -> bool:
        """Kritik seviye altında mı?"""
        if not self.kritik_seviye or self.kritik_seviye == 0:
            return False
        return self.toplam_stok < self.kritik_seviye
    
    @hybrid_property
    def paket_mi(self) -> bool:
        """Paket ürün mü?"""
        return self.tip in ['PAKET', 'MAMUL']
    
    # ========================================
    # VALİDASYONLAR
    # ========================================
    @validates('kod')
    def validate_kod(self, key, value):
        if not value or not value.strip():
            raise ValueError("Stok kodu boş olamaz")
        return value.strip().upper()
    
    @validates('ad')
    def validate_ad(self, key, value):
        if not value or not value.strip():
            raise ValueError("Stok adı boş olamaz")
        return value.strip()
    
    @validates('alis_fiyati', 'satis_fiyati')
    def validate_fiyat(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} negatif olamaz")
        return value
    
    # ========================================
    # INSTANCE METHODS
    # ========================================
    def ai_analiz_guncelle(self):
        """AI analizlerini güncelle"""
        try:
            # 1. Kar marjı
            kar_marji = float(self.kar_marji)
            
            # 2. Stok devir hızı (basit hesaplama)
            # Gerçek hesaplama: Son 12 aydaki satış / Ortalama stok
            # Burada basitleştirdik
            self.ai_stok_devir_hizi = Decimal('0.00')  # Servis katmanında hesaplanacak
            
            # 3. Ölü stok riski
            if self.toplam_stok > 0:
                # Son 6 ayda satış var mı kontrol et (servis katmanında)
                self.ai_olu_stok_riski = False  # Varsayılan
            
            # 4. Metadata güncelle
            self.ai_metadata = {
                'kar_marji_yuzde': kar_marji,
                'toplam_stok': float(self.toplam_stok),
                'kritik_seviye_altinda': self.kritik_seviye_altinda_mi,
                'analiz_tarihi': datetime.now().isoformat()
            }
            
            logger.debug(f"AI analiz güncellendi: {self.kod}")
            
        except Exception as e:
            logger.error(f"AI analiz hatası ({self.kod}): {e}")
    
    def __repr__(self):
        return f"<StokKart {self.kod} - {self.ad}>"


# ========================================
# STOK PAKET İÇERİĞİ MODELİ
# ========================================
class StokPaketIcerigi(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Paket ürünlerin içeriğini tutar
    
    Örnek: 'Yılbaşı Paketi' içinde:
    - 1 Adet Kahve
    - 2 Adet Çikolata
    - 1 Adet Kart
    """
    __tablename__ = 'stok_paket_icerigi'
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    paket_stok_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kartlari.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    alt_stok_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kartlari.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # VERİLER
    # ========================================
    miktar = db.Column(
        DECIMAL(15, 4),
        default=Decimal('1.0000'),
        nullable=False
    )
    
    sira_no = db.Column(
        Integer,
        default=1,
        comment='Sıra numarası (UI için)'
    )
    
    # ========================================
    # INDEXES
    # ========================================
    __table_args__ = (
        Index('idx_paket_icerik', 'paket_stok_id', 'alt_stok_id'),
        UniqueConstraint('paket_stok_id', 'alt_stok_id', name='uq_paket_alt_stok'),
        CheckConstraint('miktar > 0', name='chk_paket_miktar'),
        {'comment': 'Paket ürün içerikleri'}
    )
    
    def __repr__(self):
        return f"<PaketIcerik Paket:{self.paket_stok_id} Alt:{self.alt_stok_id} Miktar:{self.miktar}>"


# ========================================
# STOK MUHASEBE GRUBU MODELİ
# ========================================
class StokMuhasebeGrubu(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Stok Muhasebe Grupları
    
    Amaç:
    - Stokları muhasebe hesaplarına bağlamak
    - Toplu hesap değişikliği yapabilmek
    - Raporlamayı kolaylaştırmak
    """
    __tablename__ = 'stok_muhasebe_gruplari'
    query_class = FirmaFilteredQuery
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    firma_id = db.Column(
        CHAR(36),
        db.ForeignKey('firmalar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # TEMEL BİLGİLER
    # ========================================
    kod = db.Column(
        String(50),
        nullable=False,
        index=True
    )
    
    ad = db.Column(
        String(100),
        nullable=False
    )
    
    aciklama = db.Column(String(500))
    aktif = db.Column(Boolean, default=True, nullable=False)
    
    # ========================================
    # MUHASEBE HESAP BAĞLANTILARI
    # ========================================
    # Stok (Envanter) Hesabı (153 - İlk Madde ve Malzeme)
    alis_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='153 - Stok giriş hesabı'
    )
    
    # Satış Hasılat Hesabı (600 - Yurt İçi Satışlar)
    satis_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='600 - Satış gelir hesabı'
    )
    
    # Alış İade Hesabı (153 Alacak)
    alis_iade_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        comment='153 - Alış iade hesabı'
    )
    
    # Satış İade Hesabı (610 - Satıştan İadeler)
    satis_iade_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        comment='610 - Satış iade hesabı'
    )
    
    # Satılan Malın Maliyeti (621)
    satilan_mal_maliyeti_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        comment='621 - Satılan malın maliyeti'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    alis_hesap = relationship(
        'HesapPlani',
        foreign_keys=[alis_hesap_id],
        lazy='select'
    )
    
    satis_hesap = relationship(
        'HesapPlani',
        foreign_keys=[satis_hesap_id],
        lazy='select'
    )
    
    # ========================================
    # INDEXES
    # ========================================
    __table_args__ = (
        Index('idx_muh_grup_firma_kod', 'firma_id', 'kod'),
        UniqueConstraint('firma_id', 'kod', name='uq_stok_muh_kod'),
        {'comment': 'Stok muhasebe grupları'}
    )
    
    def __repr__(self):
        return f"<StokMuhasebeGrubu {self.kod} - {self.ad}>"


# ========================================
# STOK KDV GRUBU MODELİ
# ========================================
class StokKDVGrubu(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Stok KDV Grupları
    
    Amaç:
    - KDV oranlarını merkezi yönetmek
    - KDV değişikliklerinde toplu güncelleme
    - Farklı KDV senaryoları (istisna, tevkifat, vb.)
    """
    __tablename__ = 'stok_kdv_gruplari'
    query_class = FirmaFilteredQuery
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    firma_id = db.Column(
        CHAR(36),
        db.ForeignKey('firmalar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # TEMEL BİLGİLER
    # ========================================
    kod = db.Column(
        String(20),
        nullable=False,
        index=True
    )
    
    ad = db.Column(
        String(50),
        nullable=False
    )
    
    # ========================================
    # KDV ORANLARI
    # ========================================
    alis_kdv_orani = db.Column(
        Integer,
        default=20,
        nullable=False,
        comment='Alış KDV oranı (%)'
    )
    
    satis_kdv_orani = db.Column(
        Integer,
        default=20,
        nullable=False,
        comment='Satış KDV oranı (%)'
    )
    
    # ========================================
    # MUHASEBE HESAPLARI (KRİTİK!)
    # ========================================
    alis_kdv_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='191 - Alış KDV hesabı'
    )
    
    satis_kdv_hesap_id = db.Column(
        CHAR(36),
        db.ForeignKey('hesap_plani.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='391 - Satış KDV hesabı'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    alis_kdv_hesap = relationship(
        'HesapPlani',
        foreign_keys=[alis_kdv_hesap_id],
        lazy='select'
    )
    
    satis_kdv_hesap = relationship(
        'HesapPlani',
        foreign_keys=[satis_kdv_hesap_id],
        lazy='select'
    )
    
    # ========================================
    # INDEXES
    # ========================================
    __table_args__ = (
        Index('idx_kdv_grup_firma_kod', 'firma_id', 'kod'),
        UniqueConstraint('firma_id', 'kod', name='uq_stok_kdv_kod'),
        CheckConstraint('alis_kdv_orani >= 0 AND alis_kdv_orani <= 100', name='chk_kdv_alis_oran'),
        CheckConstraint('satis_kdv_orani >= 0 AND satis_kdv_orani <= 100', name='chk_kdv_satis_oran'),
        {'comment': 'Stok KDV grupları'}
    )
    
    def __repr__(self):
        return f"<StokKDVGrubu {self.kod} - Alış:%{self.alis_kdv_orani} Satış:%{self.satis_kdv_orani}>"


# ========================================
# STOK DEPO DURUMU MODELİ
# ========================================
class StokDepoDurumu(db.Model, TimestampMixin):
    """
    Stok Depo Durumu - Snapshot Table
    
    Amaç:
    - Her depo için anlık stok miktarını tutmak
    - Hızlı sorgu (aggregate query yerine direkt okuma)
    - Trigger ile otomatik güncelleme
    """
    __tablename__ = 'stok_depo_durumu'
    query_class = FirmaFilteredQuery
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    firma_id = db.Column(
        CHAR(36),
        db.ForeignKey('firmalar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    depo_id = db.Column(
        CHAR(36),
        db.ForeignKey('depolar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    stok_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kartlari.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # VERİLER
    # ========================================
    miktar = db.Column(
        DECIMAL(18, 6),
        default=Decimal('0.000000'),
        nullable=False,
        comment='Anlık stok miktarı'
    )
    
    # İleride eklenebilir:
    ortalama_maliyet = db.Column(
        DECIMAL(18, 6),
        default=Decimal('0.000000'),
        comment='Ortalama maliyet (hareketli ortalama)'
    )
    
    son_hareket_tarihi = db.Column(
        Date,
        comment='Son hareket tarihi (performans için)'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    depo = relationship('Depo', backref='stok_listesi', lazy='select')
    stok = relationship('StokKart', back_populates='depo_durumlari', lazy='joined')
    
    # ========================================
    # INDEXES
    # ========================================
    __table_args__ = (
        # 1. Depo bazlı sorgular
        Index('idx_depo_durum_depo', 'depo_id', 'miktar'),
        
        # 2. Stok bazlı sorgular
        Index('idx_depo_durum_stok', 'stok_id', 'depo_id'),
        
        # 3. Firma bazlı
        Index('idx_depo_durum_firma', 'firma_id'),
        
        # 4. Unique constraint (bir depo+stok kombinasyonu sadece 1 satır)
        UniqueConstraint('depo_id', 'stok_id', name='uq_stok_depo'),
        
        CheckConstraint('miktar >= 0', name='chk_depo_miktar'),
        
        {'comment': 'Stok depo durumu - Snapshot table'}
    )
    
    def __repr__(self):
        return f"<StokDepoDurumu Depo:{self.depo_id} Stok:{self.stok_id} Miktar:{self.miktar}>"


# ========================================
# STOK HAREKETİ MODELİ (AI Enhanced)
# ========================================
class StokHareketi(db.Model, TimestampMixin):
    """
    Stok Hareketleri - Transaction Table
    
    Özellikler:
    - Tüm stok giriş/çıkış hareketlerini kaydeder
    - Kaynak belge izlenebilirliği
    - Finansal verilerle entegre
    - AI analiz desteği
    """
    __tablename__ = 'stok_hareketleri'
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    firma_id = db.Column(
        CHAR(36),
        db.ForeignKey('firmalar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    donem_id = db.Column(
        CHAR(36),
        db.ForeignKey('donemler.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    sube_id = db.Column(
        CHAR(36),
        db.ForeignKey('subeler.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    kullanici_id = db.Column(
        CHAR(36),
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    stok_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kartlari.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    # Depo transferlerinde her iki alan da dolabilir
    giris_depo_id = db.Column(
        CHAR(36),
        db.ForeignKey('depolar.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    
    cikis_depo_id = db.Column(
        CHAR(36),
        db.ForeignKey('depolar.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    
    # ========================================
    # HAREKET DETAYLARI
    # ========================================
    tarih = db.Column(
        Date,
        nullable=False,
        index=True,
        comment='Hareket tarihi'
    )
    
    belge_no = db.Column(
        String(50),
        index=True,
        comment='Fatura/Fiş numarası'
    )
    
    hareket_turu = db.Column(
        ENUM(
            'GIRIS', 'CIKIS', 'DEVIR', 'TRANSFER',
            'ALIS', 'SATIS', 'ALIS_IADE', 'SATIS_IADE',
            'URETIM', 'URETIM_CIKIS', 'SARF', 'FIRE',
            'SAYIM_FAZLA', 'SAYIM_EKSIK',
            name='hareket_turu_enum'
        ),
        nullable=False,
        index=True
    )
    
    aciklama = db.Column(String(500))
    
    # ========================================
    # MİKTAR VE FİYAT
    # ========================================
    miktar = db.Column(
        DECIMAL(18, 4),
        default=Decimal('0.0000'),
        nullable=False
    )
    
    birim_fiyat = db.Column(
        DECIMAL(18, 4),
        default=Decimal('0.0000'),
        comment='İskontosuz birim fiyat'
    )
    
    # ========================================
    # FİNANSAL ALANLAR
    # ========================================
    doviz_turu = db.Column(
        ENUM('TL', 'USD', 'EUR', 'GBP', name='para_birimi_enum'),
        default='TL',
        nullable=False
    )
    
    doviz_kuru = db.Column(
        DECIMAL(10, 4),
        default=Decimal('1.0000'),
        nullable=False
    )
    
    # İskonto
    iskonto_orani = db.Column(
        DECIMAL(5, 2),
        default=Decimal('0.00')
    )
    
    iskonto_tutar = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00')
    )
    
    # KDV
    kdv_orani = db.Column(
        Integer,
        default=0
    )
    
    kdv_tutar = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00')
    )
    
    # Net tutarlar
    net_tutar = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Matrah (iskonto sonrası)'
    )
    
    toplam_tutar = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='KDV dahil toplam'
    )
    
    # ========================================
    # KAYNAK İZLEME
    # ========================================
    kaynak_turu = db.Column(
        String(20),
        index=True,
        comment='fatura, stok_fisi, siparis, vb.'
    )
    
    kaynak_id = db.Column(
        CHAR(36),
        index=True,
        comment='Kaynak belge ID'
    )
    
    kaynak_belge_detay_id = db.Column(
        CHAR(36),
        comment='Kaynak belge detay ID (kalem)'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    giris_depo = relationship(
        'Depo',
        foreign_keys=[giris_depo_id],
        backref='giris_hareketleri',
        lazy='select'
    )
    
    cikis_depo = relationship(
        'Depo',
        foreign_keys=[cikis_depo_id],
        backref='cikis_hareketleri',
        lazy='select'
    )
    
    kullanici = relationship('Kullanici', lazy='select')
    
    # ========================================
    # COMPOSITE INDEXES (Transaction Table - KRİTİK!)
    # ========================================
    __table_args__ = (
        # 1. Stok bazlı sorgular (EN ÖNEMLİ!)
        Index('idx_hareket_stok_tarih', 'stok_id', 'tarih', 'hareket_turu'),
        
        # 2. Depo bazlı sorgular
        Index('idx_hareket_depo_giris', 'giris_depo_id', 'tarih'),
        Index('idx_hareket_depo_cikis', 'cikis_depo_id', 'tarih'),
        
        # 3. Firma bazlı
        Index('idx_hareket_firma_tarih', 'firma_id', 'tarih'),
        
        # 4. Dönem bazlı
        Index('idx_hareket_donem', 'donem_id', 'tarih'),
        
        # 5. Belge izleme
        Index('idx_hareket_belge', 'belge_no', 'firma_id'),
        Index('idx_hareket_kaynak', 'kaynak_turu', 'kaynak_id'),
        
        # 6. Hareket türü bazlı
        Index('idx_hareket_tur', 'hareket_turu', 'tarih'),
        
        # 7. Kullanıcı bazlı
        Index('idx_hareket_kullanici', 'kullanici_id', 'tarih'),
        
        CheckConstraint('miktar > 0', name='chk_hareket_miktar'),
        CheckConstraint('doviz_kuru > 0', name='chk_hareket_kur'),
        
        {'comment': 'Stok hareketleri - Yüksek hacimli transaction table'}
    )
    
    # ========================================
    # HYBRID PROPERTIES
    # ========================================
    @hybrid_property
    def yon(self) -> int:
        """
        Hareketin stoğa etkisi
        +1: Stok artar
        -1: Stok azalır
        0: Etkisiz
        """
        # Stok artıranlar
        if self.hareket_turu in [
            'GIRIS', 'DEVIR', 'ALIS', 'SATIS_IADE',
            'URETIM', 'SAYIM_FAZLA'
        ]:
            return 1
        
        # Stok azaltanlar
        if self.hareket_turu in [
            'CIKIS', 'SATIS', 'ALIS_IADE',
            'URETIM_CIKIS', 'SARF', 'FIRE', 'SAYIM_EKSIK'
        ]:
            return -1
        
        # Transfer özel durum
        if self.hareket_turu == 'TRANSFER':
            if self.giris_depo_id:
                return 1  # Giriş yapan depo için
            elif self.cikis_depo_id:
                return -1  # Çıkış yapan depo için
        
        return 0
    
    @hybrid_property
    def etiket(self) -> str:
        """Türkçe etiket"""
        etiketler = {
            'GIRIS': 'Giriş',
            'CIKIS': 'Çıkış',
            'DEVIR': 'Devir',
            'TRANSFER': 'Transfer',
            'ALIS': 'Alış Faturası',
            'SATIS': 'Satış Faturası',
            'ALIS_IADE': 'Alış İade',
            'SATIS_IADE': 'Satış İade',
            'URETIM': 'Üretim Giriş',
            'URETIM_CIKIS': 'Üretim Çıkış',
            'SARF': 'Sarf',
            'FIRE': 'Fire',
            'SAYIM_FAZLA': 'Sayım Fazlası',
            'SAYIM_EKSIK': 'Sayım Eksiği'
        }
        return etiketler.get(self.hareket_turu, str(self.hareket_turu))
    
    def __repr__(self):
        return f"<StokHareketi {self.belge_no} Stok:{self.stok_id} Miktar:{self.miktar}>"


