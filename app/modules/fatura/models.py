# app/modules/fatura/models.py
"""
Fatura Modelleri - MySQL Optimized + AI Enhanced
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
from app.enums import (
    FaturaTuru, ParaBirimi, FaturaDurumu, OdemeDurumu,
    EFaturaSenaryo, EFaturaTipi, StokBirimleri
)
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
# ANA FATURA MODELİ (AI + MySQL Optimized)
# ========================================
class Fatura(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Ana Fatura Modeli (Satış/Alış/İade)
    
    Özellikler:
    - Multi-tenant (firma_id)
    - Soft delete
    - E-Fatura entegrasyonu
    - AI metadata desteği
    - Composite index'ler
    """
    __tablename__ = 'faturalar'
    query_class = FirmaFilteredQuery
    
    # ========================================
    # PRIMARY KEY (MySQL CHAR(36))
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS (Tümü INDEX'li)
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
    
    cari_id = db.Column(
        CHAR(36),
        db.ForeignKey('cari_hesaplar.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    depo_id = db.Column(
        CHAR(36),
        db.ForeignKey('depolar.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # TEMEL BİLGİLER
    # ========================================
    fatura_turu = db.Column(
        ENUM('SATIS', 'ALIS', 'SATIS_IADE', 'ALIS_IADE', name='fatura_turu_enum'),
        default='SATIS',
        nullable=False,
        index=True,
        comment='Fatura türü'
    )
    
    belge_no = db.Column(
        String(50),
        nullable=False,
        index=True,
        comment='Fatura numarası (FAT-00001)'
    )
    
    dis_belge_no = db.Column(
        String(50),
        index=True,
        comment='Karşı tarafın fatura numarası'
    )
    
    tarih = db.Column(
        Date,
        nullable=False,
        index=True,
        comment='Fatura tarihi'
    )
    
    vade_tarihi = db.Column(
        Date,
        index=True,
        comment='Ödeme vade tarihi'
    )
    
    fatura_saati = db.Column(
        DateTime,
        default=datetime.now,
        comment='Fatura kesim saati'
    )
    
    gun_adi = db.Column(
        String(20),
        comment='Haftanın günü (Raporlama için)'
    )
    
    # ========================================
    # DÖVİZ
    # ========================================
    doviz_turu = db.Column(
        ENUM('TL', 'USD', 'EUR', 'GBP', name='para_birimi_enum'),
        default='TL',
        nullable=False,
        index=True
    )
    
    doviz_kuru = db.Column(
        DECIMAL(10, 4),
        default=Decimal('1.0000'),
        nullable=False
    )
    
    # ========================================
    # KAYNAK İLİŞKİLERİ
    # ========================================
    kaynak_siparis_id = db.Column(
        CHAR(36),
        db.ForeignKey('siparisler.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    fiyat_listesi_id = db.Column(
        CHAR(36),
        db.ForeignKey('fiyat_listeleri.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # ========================================
    # FİNANSAL TUTARLAR
    # ========================================
    ara_toplam = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment='İskonto öncesi toplam (matrah)'
    )
    
    kdv_toplam = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment='Toplam KDV tutarı'
    )
    
    iskonto_toplam = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment='Toplam iskonto tutarı'
    )
    
    genel_toplam = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        nullable=False,
        index=True,
        comment='Genel toplam (KDV dahil)'
    )
    
    dovizli_toplam = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Döviz cinsinden toplam'
    )
    
    # ========================================
    # PERSONEL VE LOG (UUID Uyumlu)
    # ========================================
    plasiyer_id = db.Column(
        CHAR(36),
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    kaydeden_id = db.Column(
        CHAR(36),
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'),
        index=True
    )
    
    duzenleyen_id = db.Column(
        CHAR(36),
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL')
    )
    
    # ========================================
    # DİĞER BİLGİLER
    # ========================================
    sevk_adresi = db.Column(String(500))
    aciklama = db.Column(Text)
    maksimum_iskonto_orani = db.Column(DECIMAL(5, 2), default=Decimal('0.00'))
    
    # ========================================
    # DURUM
    # ========================================
    odeme_durumu = db.Column(
        ENUM('BEKLIYOR', 'KISMEN', 'TAMAMEN', name='odeme_durumu_enum'),
        default='BEKLIYOR',
        nullable=False,
        index=True
    )
    
    durum = db.Column(
        ENUM('TASLAK', 'ONAYLANDI', 'IPTAL', name='fatura_durumu_enum'),
        default='TASLAK',
        nullable=False,
        index=True
    )
    
    aktif = db.Column(Boolean, default=True, nullable=False, index=True)
    
    # ========================================
    # SATIŞ KANALI (CRM)
    # ========================================
    satis_kanali = db.Column(
        String(50),
        index=True,
        comment='Online, Mağaza, Telefon, vb.'
    )
    
    musteri_puani = db.Column(
        Integer,
        comment='Müşteri memnuniyet puanı (1-10)'
    )
    
    # ========================================
    # İPTAL
    # ========================================
    iptal_mi = db.Column(Boolean, default=False, nullable=False, index=True)
    iptal_nedeni = db.Column(String(200))
    iptal_tarihi = db.Column(DateTime)
    iptal_eden_id = db.Column(CHAR(36), db.ForeignKey('kullanicilar.id', ondelete='SET NULL'))
    
    # ========================================
    # MUHASEBE FİŞİ
    # ========================================
    muhasebe_fis_id = db.Column(
        CHAR(36),
        db.ForeignKey('muhasebe_fisleri.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # ========================================
    # E-FATURA (GİB Entegrasyonu)
    # ========================================
    ettn = db.Column(
        CHAR(36),
        unique=True,
        index=True,
        comment='E-Fatura Takip Numarası (UUID)'
    )
    
    e_fatura_senaryo = db.Column(db.String(50), default="TICARIFATURA")
    e_fatura_tipi = db.Column(db.String(50), default="SATIS")
    
    
    gib_durum_kodu = db.Column(
        Integer,
        default=0,
        index=True,
        comment='0:Hazır, 2:Onaylı, 3:Hata'
    )
    
    gib_durum_aciklama = db.Column(String(500))
    xml_path = db.Column(String(500))
    
    # E-Fatura Detay
    zarf_uuid = db.Column(CHAR(36))
    alici_etiket_pk = db.Column(String(100))
    gonderen_etiket_gb = db.Column(String(100))
    gib_gonderim_tarihi = db.Column(DateTime, index=True)
    gib_yanit_tarihi = db.Column(DateTime)
    
    # ========================================
    # İADE DURUMU
    # ========================================
    iade_edilen_fatura_id = db.Column(
        CHAR(36),
        db.ForeignKey('faturalar.id', ondelete='SET NULL'),
        nullable=True
    )
    iade_edilen_fatura_no = db.Column(String(50))
    iade_edilen_fatura_tarihi = db.Column(Date)
    
    # ========================================
    # İNTERNET SATIŞI
    # ========================================
    internet_satisi_mi = db.Column(Boolean, default=False, index=True)
    web_sitesi_adresi = db.Column(String(255))
    odeme_sekli_detay = db.Column(String(50))
    
    odeme_plani_id = db.Column(
        CHAR(36),
        db.ForeignKey('odeme_planlari.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # ========================================
    # TAŞIYICI BİLGİLERİ (E-İrsaliye)
    # ========================================
    tasiyici_vkn_tckn = db.Column(String(20))
    tasiyici_unvan = db.Column(String(200))
    tasiyici_adres = db.Column(String(500))
    gonderim_tarihi_saati = db.Column(DateTime)
    
    # ========================================
    # YAPAY ZEKA METADATA (MySQL JSON Native)
    # ========================================
    ai_metadata = db.Column(
        JSON,
        nullable=True,
        comment='AI analizleri için esnek veri yapısı'
    )
    # Örnek ai_metadata yapısı:
    # {
    #     "anomali_tespiti": false,
    #     "tahsilat_tahmini": {
    #         "tarih": "2024-03-15",
    #         "olasilik": 0.85
    #     },
    #     "fiyat_onerisi": {
    #         "onceki_ortalama": 1250.50,
    #         "piyasa_ortalaması": 1300.00,
    #         "oneri": "normal"
    #     },
    #     "risk_skorları": {
    #         "tahsilat_riski": 15,
    #         "iade_riski": 5
    #     },
    #     "otomatik_etiketler": ["yuksek_deger", "tekrarlayan_musteri"]
    # }
    
    ai_tahsilat_tahmini_tarih = db.Column(
        Date,
        index=True,
        comment='AI tarafından tahmin edilen tahsilat tarihi'
    )
    
    ai_tahsilat_olasiligi = db.Column(
        DECIMAL(5, 2),
        comment='Tahsilatın gerçekleşme olasılığı (0-100%)'
    )
    
    ai_anomali_skoru = db.Column(
        Integer,
        default=0,
        index=True,
        comment='Anomali tespit skoru (0-100)'
    )
    
    ai_kategori = db.Column(
        String(50),
        index=True,
        comment='AI otomatik kategorizasyonu'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    kalemler = relationship(
        'FaturaKalemi',
        back_populates='fatura',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='FaturaKalemi.sira_no'
    )
    
    cari = relationship('CariHesap', back_populates='faturalar', lazy='joined')
    depo = relationship('Depo', lazy='select')
    # ✅ ŞUBE İLİŞKİSİ (Opsiyonel)
    sube = relationship('Sube', foreign_keys=[sube_id], backref='faturalar')
    
    plasiyer = relationship(
        'Kullanici',
        foreign_keys=[plasiyer_id],
        backref='plasiyer_faturalari',
        lazy='select'
    )
    
    kaydeden = relationship(
        'Kullanici',
        foreign_keys=[kaydeden_id],
        backref='kaydettigi_faturalar',
        lazy='select'
    )
    
    duzenleyen = relationship(
        'Kullanici',
        foreign_keys=[duzenleyen_id],
        backref='duzenledigi_faturalar',
        lazy='select'
    )
    
    iptal_eden = relationship(
        'Kullanici',
        foreign_keys=[iptal_eden_id],
        lazy='select'
    )
    
    kaynak_siparis = relationship(
        'Siparis',
        foreign_keys=[kaynak_siparis_id],
        backref='olusan_faturalar',
        lazy='select'
    )
    
    muhasebe_fisi = relationship(
        'MuhasebeFisi',
        foreign_keys=[muhasebe_fis_id],
        backref=backref('fatura_kaynagi', uselist=False),
        lazy='select'
    )
    
    iade_kaynak = relationship(
        'Fatura',
        remote_side=[id],
        foreign_keys=[iade_edilen_fatura_id],
        backref='iade_faturalari',
        lazy='select'
    )
    
    # ========================================
    # 🔥 MYSQL COMPOSITE INDEXES (SÜPER ÖNEMLİ!)
    # ========================================
    __table_args__ = (
        # --- PRIMARY INDEXES ---
        # 1. Firma bazlı sorgular (Multi-tenant)
        Index('idx_fatura_firma_tarih', 'firma_id', 'tarih', 'durum'),
        Index('idx_fatura_firma_belge', 'firma_id', 'belge_no'),
        
        # 2. Tarih bazlı sorgular
        Index('idx_fatura_tarih_durum', 'tarih', 'durum'),
        Index('idx_fatura_tarih_tur', 'tarih', 'fatura_turu'),
        
        # 3. Cari bazlı sorgular
        Index('idx_fatura_cari_tarih', 'cari_id', 'tarih', 'durum'),
        Index('idx_fatura_cari_tutar', 'cari_id', 'genel_toplam'),
        
        # 4. Durum bazlı sorgular
        Index('idx_fatura_durum_tarih', 'durum', 'tarih'),
        Index('idx_fatura_odeme_durum', 'odeme_durumu', 'vade_tarihi'),
        
        # 5. E-Fatura sorgulari
        Index('idx_fatura_gib_durum', 'gib_durum_kodu', 'tarih'),
        Index('idx_fatura_ettn', 'ettn'),
        
        # 6. Dönem & Şube
        Index('idx_fatura_donem_tarih', 'donem_id', 'tarih'),
        Index('idx_fatura_sube_tarih', 'sube_id', 'tarih'),
        
        # 7. Vade takibi
        Index('idx_fatura_vade_alarm', 'vade_tarihi', 'odeme_durumu'),
        
        # 8. AI analizleri
        Index('idx_fatura_ai_anomali', 'ai_anomali_skoru'),
        Index('idx_fatura_ai_kategori', 'ai_kategori'),
        
        # 9. Satış kanalı
        Index('idx_fatura_kanal', 'satis_kanali', 'tarih'),
        
        # --- UNIQUE CONSTRAINTS ---
        # 10. Belge numarası tekil olmalı (firma+tür bazında)
        UniqueConstraint(
            'firma_id', 'belge_no', 'fatura_turu',
            name='uq_fatura_belge_no'
        ),
        
        # 11. E-Fatura ETTN tekil
        UniqueConstraint('ettn', name='uq_fatura_ettn'),
        
        # --- CHECK CONSTRAINTS ---
        CheckConstraint('genel_toplam >= 0', name='chk_fatura_genel_toplam'),
        CheckConstraint('doviz_kuru > 0', name='chk_fatura_doviz_kuru'),
        CheckConstraint('vade_tarihi >= tarih', name='chk_fatura_vade'),
        
        {'comment': 'Faturalar - Ana transaction table (AI destekli)'}
    )
    
    # ========================================
    # HYBRID PROPERTIES
    # ========================================
    @property
    def genel_toplam_yazi_ile(self):
        try:
            from app.araclar import sayiyi_yaziya_cevir
            if self.genel_toplam:
                # DÜZELTME: Sadece sayıyı (1 argüman) gönderiyoruz
                # Döviz türü vb. 2. bir argüman varsa siliyoruz.
                return sayiyi_yaziya_cevir(self.genel_toplam)
            return ""
        except Exception as e:
            # Fonksiyonda başka bir hata olursa sistemi çökertmemesi için can yeleği
            return f"#{self.genel_toplam}#"
    
    @hybrid_property
    def odeme_yuzdesi(self) -> float:
        """Ödeme yüzdesini hesaplar (0-100)"""
        if not self.genel_toplam or self.genel_toplam == 0:
            return 0.0
        
        if self.odeme_durumu == 'TAMAMEN':
            return 100.0
        elif self.odeme_durumu == 'KISMEN':
            # İleride tahsilat hareketlerinden hesaplanabilir
            return 50.0
        else:
            return 0.0
    
    @hybrid_property
    def vade_gecmis_gun_sayisi(self) -> int:
        """Vade geçmiş ise kaç gün geçtiğini döner"""
        if not self.vade_tarihi or self.odeme_durumu == 'TAMAMEN':
            return 0
        
        bugun = date.today()
        if bugun > self.vade_tarihi:
            return (bugun - self.vade_tarihi).days
        return 0
    
    @hybrid_property
    def net_kar(self) -> Decimal:
        """Net kar hesaplama (satış - maliyet)"""
        # Bu hesaplama için kalemlerden maliyet bilgisi gerekir
        toplam_maliyet = Decimal('0.00')
        
        for kalem in self.kalemler:
            if hasattr(kalem, 'stok') and hasattr(kalem.stok, 'maliyet'):
                toplam_maliyet += (kalem.miktar * kalem.stok.maliyet)
        
        return self.genel_toplam - toplam_maliyet
    
    # ========================================
    # VALİDASYONLAR
    # ========================================
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
    
    @validates('genel_toplam')
    def validate_toplam(self, key, value):
        if value is not None and value < 0:
            raise ValueError("Genel toplam negatif olamaz")
        return value
    
    # ========================================
    # INSTANCE METHODS
    # ========================================
    def ai_analiz_guncelle(self):
        """AI analizlerini güncelle"""
        try:
            # 1. Anomali tespiti
            anomali_skoru = 0
            
            # Olağandışı yüksek tutar
            if self.genel_toplam > 100000:
                anomali_skoru += 30
            
            # Hızlı peşpeşe faturalar
            # (Bu hesaplama için veritabanı sorgusu gerekir)
            
            # Olağandışı iskonto
            if self.iskonto_toplam / self.ara_toplam > 0.30:
                anomali_skoru += 25
            
            self.ai_anomali_skoru = min(anomali_skoru, 100)
            
            # 2. Otomatik kategorileme
            if self.genel_toplam > 50000:
                self.ai_kategori = 'YUKSEK_DEGER'
            elif self.internet_satisi_mi:
                self.ai_kategori = 'ONLINE_SATIS'
            else:
                self.ai_kategori = 'STANDART'
            
            # 3. Tahsilat tahmini (basit heuristic)
            if self.vade_tarihi:
                from datetime import timedelta
                
                # Ödeme geçmişine göre tahmin
                if hasattr(self.cari, 'ortalama_odeme_suresi'):
                    gec_sure = self.cari.ortalama_odeme_suresi or 0
                    self.ai_tahsilat_tahmini_tarih = self.vade_tarihi + timedelta(days=gec_sure)
                else:
                    self.ai_tahsilat_tahmini_tarih = self.vade_tarihi
                
                # Olasılık hesaplama
                if hasattr(self.cari, 'risk_skoru'):
                    risk = self.cari.risk_skoru or 0
                    self.ai_tahsilat_olasiligi = max(10, 100 - risk)
                else:
                    self.ai_tahsilat_olasiligi = Decimal('75.00')
            
            logger.info(f"AI analiz güncellendi: {self.belge_no}")
            
        except Exception as e:
            logger.error(f"AI analiz hatası ({self.belge_no}): {e}")
 
    def to_dict(self):
        """JSON serialization"""
        return {
            'id': self.id,
            'belge_no': self.belge_no,
            'tarih': self.tarih.isoformat() if self.tarih else None,
            'cari_unvan': self.cari.unvan if self.cari else None,
            'sube_ad': self.sube.ad if self.sube else None,
            'genel_toplam': float(self.genel_toplam),
            'doviz_turu': self.doviz_turu,
            'durum': self.durum
        }

    def __repr__(self):
        return f"<Fatura {self.belge_no} - {self.genel_toplam} {self.doviz_turu}>"

    @property
    def gib_durum_metni(self):
        if self.gib_durum_kodu == 1300: 
            return 'ONAYLANDI'
        elif self.gib_durum_kodu == 100: 
            return 'KUYRUKTA'
        elif self.ettn: 
            return 'ISLENIYOR'
        return 'GONDERILMEDI'



# ========================================
# FATURA KALEMİ MODELİ (Line Items - AI Enhanced)
# ========================================
class FaturaKalemi(db.Model, TimestampMixin):
    """
    Fatura Satır Detayları (Line Items)
    
    Özellikler:
    - Otomatik hesaplamalar
    - AI fiyat analizi
    - Stok ilişkisi
    - Composite index'ler
    """
    __tablename__ = 'fatura_kalemleri'
    
    # ========================================
    # PRIMARY KEY
    # ========================================
    id = db.Column(CHAR(36), primary_key=True, default=generate_uuid)
    
    # ========================================
    # FOREIGN KEYS
    # ========================================
    fatura_id = db.Column(
        CHAR(36),
        db.ForeignKey('faturalar.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    stok_id = db.Column(
        CHAR(36),
        db.ForeignKey('stok_kartlari.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    
    # ========================================
    # TEMEL VERİLER
    # ========================================
    sira_no = db.Column(
        Integer,
        default=1,
        nullable=False,
        comment='Satır sırası (UI için)'
    )
    
    miktar = db.Column(
        DECIMAL(18, 4),
        default=Decimal('1.0000'),
        nullable=False
    )
    
    birim = db.Column(
        ENUM('ADET', 'KG', 'LT', 'MT', 'M2', 'M3', 'KUTU', 'KOLI', 'PALET', name='stok_birim_enum'),
        default='ADET',
        nullable=False
    )
    
    birim_fiyat = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment='Döviz cinsinden birim fiyat'
    )
    
    # ========================================
    # İSKONTO
    # ========================================
    iskonto_orani = db.Column(
        DECIMAL(5, 2),
        default=Decimal('0.00'),
        comment='İskonto yüzdesi'
    )
    
    iskonto_tutari = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Hesaplanan iskonto tutarı'
    )
    
    # ========================================
    # KDV
    # ========================================
    kdv_orani = db.Column(
        DECIMAL(5, 2),
        default=Decimal('20.00'),
        nullable=False
    )
    
    kdv_tutari = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Hesaplanan KDV tutarı'
    )
    
    # ========================================
    # TUTARLAR (Hesaplanmış)
    # ========================================
    tutar = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Brüt tutar (miktar × fiyat)'
    )
    
    net_tutar = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Matrah (tutar - iskonto)'
    )
    
    satir_toplami = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        index=True,
        comment='Satır toplamı (net + KDV)'
    )
    
    # ========================================
    # AÇIKLAMA
    # ========================================
    aciklama = db.Column(String(500))
    paket_mi = db.Column(Boolean, default=False)
    
    # ========================================
    # TEVKİFAT (E-Fatura)
    # ========================================
    tevkifat_kodu = db.Column(String(10))
    tevkifat_payi = db.Column(Integer, default=0)
    tevkifat_paydasi = db.Column(Integer, default=10)
    tevkifat_tutari = db.Column(DECIMAL(18, 2), default=Decimal('0.00'))
    
    # ========================================
    # GÜMRÜK (İhracat)
    # ========================================
    gtip_kodu = db.Column(
        String(20),
        comment='Gümrük Tarife İstatistik Pozisyonu'
    )
    
    mensei_ulke = db.Column(String(2), comment='ISO 3166-1 alpha-2')
    
    # ========================================
    # GİB BASKI NOTU
    # ========================================
    satir_aciklamasi = db.Column(String(500))
    
    # ========================================
    # MALİYET TAKİBİ
    # ========================================
    maliyet_fiyati = db.Column(
        DECIMAL(18, 2),
        default=Decimal('0.00'),
        comment='Stok maliyeti (kar hesabı için)'
    )
    
    # ========================================
    # YAPAY ZEKA METADATA
    # ========================================
    ai_metadata = db.Column(
        JSON,
        nullable=True,
        comment='AI fiyat analizi'
    )
    # Örnek:
    # {
    #     "onceki_ortalama_fiyat": 125.50,
    #     "piyasa_ortalamasi": 130.00,
    #     "fiyat_farki_yuzde": -3.45,
    #     "onerilen_fiyat": 128.00,
    #     "anomali": false
    # }
    
    ai_fiyat_anomali = db.Column(
        Boolean,
        default=False,
        index=True,
        comment='Fiyat anomalisi tespit edildi mi?'
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    fatura = relationship(
        'Fatura',
        back_populates='kalemler',
        lazy='joined'
    )
    
    stok = relationship(
        'StokKart',
        back_populates='fatura_kalemleri',
        lazy='joined'
    )
    
    # ========================================
    # COMPOSITE INDEXES
    # ========================================
    __table_args__ = (
        # 1. Fatura bazlı sorgular
        Index('idx_kalem_fatura_sira', 'fatura_id', 'sira_no'),
        Index('idx_kalem_fatura_stok', 'fatura_id', 'stok_id'),
        
        # 2. Stok bazlı analizler
        Index('idx_kalem_stok_tutar', 'stok_id', 'satir_toplami'),
        
        # 3. AI anomali tespiti
        Index('idx_kalem_ai_anomali', 'ai_fiyat_anomali'),
        
        # 4. Miktar bazlı sorgular
        Index('idx_kalem_miktar', 'miktar'),
        
        # Check constraints
        CheckConstraint('miktar > 0', name='chk_kalem_miktar'),
        CheckConstraint('birim_fiyat >= 0', name='chk_kalem_fiyat'),
        CheckConstraint('iskonto_orani >= 0 AND iskonto_orani <= 100', name='chk_kalem_iskonto'),
        CheckConstraint('kdv_orani >= 0 AND kdv_orani <= 100', name='chk_kalem_kdv'),
        
        {'comment': 'Fatura kalemleri - AI destekli fiyat analizi'}
    )
    
    # ========================================
    # HYBRID PROPERTIES
    # ========================================
    @hybrid_property
    def kar_tutari(self) -> Decimal:
        """Satır bazında kar hesaplama"""
        if not self.maliyet_fiyati:
            return Decimal('0.00')
        
        toplam_maliyet = self.miktar * self.maliyet_fiyati
        return self.net_tutar - toplam_maliyet
    
    @hybrid_property
    def kar_yuzdesi(self) -> Decimal:
        """Kar marjı yüzdesi"""
        if not self.net_tutar or self.net_tutar == 0:
            return Decimal('0.00')
        
        kar = self.kar_tutari
        return (kar / self.net_tutar * 100).quantize(Decimal('0.01'))
    
    # ========================================
    # VALİDASYONLAR
    # ========================================
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
    
    @validates('iskonto_orani')
    def validate_iskonto(self, key, value):
        if value is not None and (value < 0 or value > 100):
            raise ValueError("İskonto oranı 0-100 arasında olmalıdır")
        return value
    
    # ========================================
    # INSTANCE METHODS
    # ========================================
    def hesapla(self):
        """Satır tutarlarını hesapla"""
        from decimal import ROUND_HALF_UP
        
        # 1. Brüt tutar
        self.tutar = (self.miktar * self.birim_fiyat).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # 2. İskonto tutarı
        self.iskonto_tutari = (
            self.tutar * self.iskonto_orani / Decimal('100')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # 3. Net tutar (matrah)
        self.net_tutar = self.tutar - self.iskonto_tutari
        
        # 4. KDV tutarı
        self.kdv_tutari = (
            self.net_tutar * self.kdv_orani / Decimal('100')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # 5. Satır toplamı
        self.satir_toplami = self.net_tutar + self.kdv_tutari
        
        # 6. Tevkifat varsa
        if self.tevkifat_paydasi and self.tevkifat_paydasi > 0:
            self.tevkifat_tutari = (
                self.kdv_tutari * self.tevkifat_payi / self.tevkifat_paydasi
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def ai_fiyat_analizi_yap(self):
        """AI fiyat anomali tespiti"""
        try:
            if not self.stok:
                return
            
            # Önceki satışlardaki ortalama fiyatı bul
            from sqlalchemy import func
            
            onceki_ort = db.session.query(
                func.avg(FaturaKalemi.birim_fiyat)
            ).join(Fatura).filter(
                FaturaKalemi.stok_id == self.stok_id,
                Fatura.fatura_turu.in_(['SATIS', 'SATIS_IADE']),
                Fatura.durum == 'ONAYLANDI',
                FaturaKalemi.id != self.id
            ).scalar()
            
            if onceki_ort and onceki_ort > 0:
                onceki_ort = Decimal(str(onceki_ort))
                
                # Fiyat farkı hesapla
                fark_yuzde = (
                    (self.birim_fiyat - onceki_ort) / onceki_ort * 100
                ).quantize(Decimal('0.01'))
                
                # Anomali kontrolü (±30% sapma)
                if abs(fark_yuzde) > 30:
                    self.ai_fiyat_anomali = True
                else:
                    self.ai_fiyat_anomali = False
                
                # Metadata kaydet
                self.ai_metadata = {
                    'onceki_ortalama_fiyat': float(onceki_ort),
                    'fiyat_farki_yuzde': float(fark_yuzde),
                    'anomali': self.ai_fiyat_anomali,
                    'analiz_tarihi': datetime.now().isoformat()
                }
                
                logger.debug(
                    f"Fiyat analizi: {self.stok.kod} - "
                    f"Fark: %{fark_yuzde}, Anomali: {self.ai_fiyat_anomali}"
                )
        
        except Exception as e:
            logger.error(f"AI fiyat analizi hatası: {e}")
    
    def __repr__(self):
        return f"<FaturaKalemi Fatura:{self.fatura_id} Stok:{self.stok_id} {self.miktar}>"