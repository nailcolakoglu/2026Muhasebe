# app/modules/cari/models.py
# MySQL Optimized + AI Enhanced Version

from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import (
    Numeric, func, ForeignKey, String, Date, DateTime, Boolean, Text,
    Integer, UniqueConstraint, Index, CheckConstraint, and_, or_, event
)
from sqlalchemy.dialects.mysql import CHAR, JSON, LONGTEXT, ENUM
from app.enums import CariTipi, CariIslemTuru, ParaBirimi
import uuid
import logging

logger = logging.getLogger(__name__)

# ========================================
# UUID GENERATOR (MySQL CHAR(36) uyumlu)
# ========================================
def generate_uuid():
    """MySQL CHAR(36) için UUID string üret"""
    return str(uuid.uuid4())


# ========================================
# CARİ HESAP MODEL (AI + MySQL Optimized)
# ========================================
class CariHesap(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'cari_hesaplar'
    query_class = FirmaFilteredQuery
    
    # ========================================
    # PRIMARY KEY (MySQL CHAR(36) - Index Friendly)
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
    
    # ========================================
    # KİMLİK BİLGİLERİ (Arama için INDEX'li)
    # ========================================
    kod = db.Column(
        db.String(20), 
        nullable=False, 
        index=True,
        comment='Cari kodu (C-0001 formatında)'
    )
    
    unvan = db.Column(
        db.String(200), 
        nullable=False, 
        index=True,
        comment='Ticari ünvan veya ad-soyad'
    )
    
    vergi_no = db.Column(
        db.String(20), 
        index=True,
        comment='10 haneli VKN'
    )
    
    vergi_dairesi = db.Column(db.String(50))
    
    tc_kimlik_no = db.Column(
        db.String(11), 
        index=True,
        comment='11 haneli TC kimlik no'
    )
    
    # ========================================
    # ADRES VE İLETİŞİM
    # ========================================
    adres = db.Column(db.String(500))  # 255 → 500 (daha uzun adresler)
    
    sehir_id = db.Column(
        CHAR(36), 
        db.ForeignKey('sehirler.id'), 
        nullable=True, 
        index=True
    )
    
    ilce_id = db.Column(
        CHAR(36), 
        db.ForeignKey('ilceler.id'), 
        nullable=True,
        index=True  # ✅ YENİ INDEX
    )
    
    telefon = db.Column(db.String(20))
    eposta = db.Column(db.String(100), index=True)  # ✅ Email araması için index
    web_site = db.Column(db.String(150))
    
    # ========================================
    # LOKASYON (AI Rota Optimizasyonu)
    # ========================================
    enlem = db.Column(
        Numeric(10, 8), 
        nullable=True,
        comment='GPS Latitude (-90 to 90)'
    )
    
    boylam = db.Column(
        Numeric(11, 8), 
        nullable=True,
        comment='GPS Longitude (-180 to 180)'
    )
    
    konum = db.Column(
        db.String(100),
        comment='Manuel girilmiş konum açıklaması'
    )
    
    # ========================================
    # FİNANSAL DURUM
    # ========================================
    doviz_turu = db.Column(
        ENUM('TL', 'USD', 'EUR', 'GBP', name='para_birimi_enum'),
        default='TL',
        nullable=False,
        index=True
    )
    
    borc_bakiye = db.Column(
        Numeric(18, 4), 
        default=Decimal('0.0000'),
        nullable=False,
        comment='Toplam borç bakiyesi'
    )
    
    alacak_bakiye = db.Column(
        Numeric(18, 4), 
        default=Decimal('0.0000'),
        nullable=False,
        comment='Toplam alacak bakiyesi'
    )
    
    bakiye = db.Column(
        Numeric(18, 4), 
        default=Decimal('0.0000'),
        nullable=False,
        index=True,  # ✅ Bakiye sıralama için index
        comment='Net bakiye (borc - alacak)'
    )
    
    # ========================================
    # MUHASEBE ENTEGRASYONU
    # ========================================
    alis_muhasebe_hesap_id = db.Column(
        CHAR(36), 
        db.ForeignKey('hesap_plani.id'), 
        nullable=True,
        index=True
    )
    
    satis_muhasebe_hesap_id = db.Column(
        CHAR(36), 
        db.ForeignKey('hesap_plani.id'), 
        nullable=True,
        index=True
    )
    
    # ========================================
    # RİSK YÖNETİMİ
    # ========================================
    risk_limiti = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        comment='Maksimum açılabilir cari hesap limiti'
    )
    
    risk_durumu = db.Column(
        db.String(20), 
        default='NORMAL',
        index=True,  # ✅ Risk filtreleme için index
        comment='NORMAL, DİKKAT, RİSKLİ, KARA_LİSTE'
    )
    
    risk_skoru = db.Column(
        db.Integer, 
        default=50,
        index=True,  # ✅ Risk skoruna göre sıralama
        comment='0-100 arası AI risk skoru'
    )
    
    teminat_tutari = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        comment='Alınan çek/senet/teminat mektubu toplamı'
    )
    
    acik_hesap_limiti = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00')
    )
    
    # ========================================
    # TİCARİ ANALİZ METRİKLERİ
    # ========================================
    ilk_siparis_tarihi = db.Column(
        db.DateTime, 
        nullable=True,
        comment='İlk alışveriş tarihi (LTV hesabı için)'
    )
    
    son_siparis_tarihi = db.Column(
        db.DateTime, 
        nullable=True,
        index=True,  # ✅ Son aktivite sorguları için
        comment='Son sipariş tarihi (Churn analizi için)'
    )
    
    toplam_siparis_sayisi = db.Column(
        db.Integer, 
        default=0,
        nullable=False
    )
    
    toplam_ciro = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        nullable=False,
        index=True,  # ✅ En değerli müşteriler için
        comment='Tüm zamanların toplam satış tutarı'
    )
    
    ortalama_siparis_tutari = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        comment='Ortalama sepet büyüklüğü'
    )
    
    ortalama_odeme_gunu = db.Column(
        db.Integer, 
        default=0,
        comment='Ortalama kaç günde ödeme yapıyor'
    )
    
    ortalama_odeme_suresi = db.Column(
        db.Integer, 
        default=0,
        comment='Fatura-ödeme arası ortalama gün'
    )
    
    gecikme_sikligi = db.Column(
        Numeric(5, 2), 
        default=Decimal('0.00'),
        comment='Ödemelerin yüzde kaçı gecikiyor (%)'
    )
    
    # ========================================
    # CRM & SEGMENTASYON
    # ========================================
    aktif = db.Column(
        db.Boolean, 
        default=True, 
        nullable=False,
        index=True  # ✅ Aktif/pasif filtreleme için
    )
    
    cari_tipi = db.Column(
        ENUM('BIREYSEL', 'KURUMSAL', 'KAMU', name='cari_tipi_enum'),
        default='BIREYSEL',
        nullable=False,
        index=True
    )
    
    sektor = db.Column(
        db.String(100),
        index=True,  # ✅ Sektör bazlı analizler için
        comment='Gıda, İnşaat, Tekstil, Teknoloji, vb.'
    )
    
    musteri_grubu = db.Column(
        db.String(50),
        index=True,
        comment='VIP, Toptancı, Perakende, Kara Liste'
    )
    
    segment = db.Column(
        db.String(50), 
        default='STANDART',
        index=True,
        comment='AI segmentasyonu: VIP, RİSKLİ, POTANSİYEL, STANDART'
    )
    
    odeme_performansi = db.Column(
        db.String(20),
        index=True,
        comment='HIZLI, NORMAL, YAVAS, GECİKMELİ'
    )
    
    # ========================================
    # YAPAY ZEKA ALANLARI (MySQL JSON Native)
    # ========================================
    ai_ozeti = db.Column(
        LONGTEXT,
        nullable=True,
        comment='LLM tarafından oluşturulan müşteri özeti'
    )
    
    ai_metadata = db.Column(
        JSON,  # ✅ MySQL Native JSON
        nullable=True,
        comment='AI analizleri için esnek veri yapısı'
    )
    # Örnek ai_metadata yapısı:
    # {
    #     "churn_ihtimali": 0.85,
    #     "oneri_urunler": ["Ürün A", "Ürün B"],
    #     "duygu_durumu": "mutsuz",
    #     "son_sikayet_tarihi": "2024-01-15",
    #     "otomatik_aksiyonlar": [
    #         {"tip": "iskonto", "oran": 10, "sebep": "sadakat"}
    #     ]
    # }
    
    churn_riski = db.Column(
        Numeric(5, 2), 
        default=Decimal('0.00'),
        index=True,  # ✅ Yüksek churn riski sorguları için
        comment='Müşteriyi kaybetme riski (0-100%)'
    )
    
    sadakat_skoru = db.Column(
        db.Integer, 
        default=50,
        index=True,
        comment='Müşteri sadakat puanı (0-100)'
    )
    
    tahmini_yasam_boyu_degeri = db.Column(
        Numeric(18, 2),
        default=Decimal('0.00'),
        index=True,  # ✅ LTV sıralaması için
        comment='Customer Lifetime Value (LTV) tahmini'
    )
    
    # ========================================
    # BİREYSEL MÜŞTERİ DETAYLARI
    # ========================================
    dogum_tarihi = db.Column(
        db.Date,
        nullable=True,
        comment='Doğum günü kampanyaları için'
    )
    
    cinsiyet = db.Column(
        ENUM('ERKEK', 'KADIN', 'DİĞER', 'BELİRTMEDİ', name='cinsiyet_enum'),
        nullable=True
    )
    
    son_iletisim_tarihi = db.Column(
        db.Date,
        nullable=True,
        index=True,  # ✅ İletişim takibi için
        comment='Son telefon/email iletişim tarihi'
    )
    
    # ========================================
    # ÖDEME PLANI
    # ========================================
    odeme_plani_id = db.Column(
        CHAR(36), 
        db.ForeignKey('odeme_planlari.id'), 
        nullable=True,
        index=True
    )
    
    # ========================================
    # SİSTEM ALANLARI (Geçici, silinecek)
    # ========================================
    kaynak_turu = db.Column(
        db.String(20),
        comment='DEPRECATED: Kullanılmıyor, silinecek'
    )
    kaynak_id = db.Column(
        CHAR(36),
        comment='DEPRECATED: Kullanılmıyor, silinecek'
    )

    # ========================================
    # İLİŞKİLER
    # ========================================
    sehir = db.relationship('Sehir', foreign_keys=[sehir_id], lazy='joined')
    ilce = db.relationship('Ilce', foreign_keys=[ilce_id], lazy='joined')
    odeme_plani_rel = db.relationship('OdemePlani', foreign_keys=[odeme_plani_id], lazy='select')
    
    # Reverse relationships
    faturalar = db.relationship(
        'Fatura', 
        back_populates='cari', 
        lazy='dynamic',
        cascade='all, delete-orphan'  # Cari silinirse faturaları da sil
    )
    
    siparisler = db.relationship(
        'Siparis', 
        back_populates='cari', 
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    cekler = db.relationship(
        'CekSenet', 
        back_populates='cari', 
        lazy='dynamic'
    )
    
    crm_kayitlari = db.relationship(
        'CRMHareket', 
        back_populates='cari', 
        lazy='dynamic',
        order_by='CRMHareket.tarih.desc()'
    )
    
    hareketler = db.relationship(
        'CariHareket',
        back_populates='cari',
        lazy='dynamic',
        order_by='CariHareket.tarih.desc()'
    )
    
    # ========================================
    # 🔥 MYSQL COMPOSITE INDEXES (SÜPER ÖNEMLİ!)
    # ========================================
    __table_args__ = (
        # --- PRIMARY INDEXES ---
        # 1. Firma bazlı sorgular (Multi-tenant temel)
        Index('idx_cari_firma_aktif', 'firma_id', 'aktif'),
        Index('idx_cari_firma_kod', 'firma_id', 'kod'),
        
        # 2. Arama ve filtreleme
        Index('idx_cari_kod_unvan', 'kod', 'unvan'),
        Index('idx_cari_vergi_no', 'vergi_no'),
        Index('idx_cari_tc_no', 'tc_kimlik_no'),
        Index('idx_cari_eposta', 'eposta'),
        
        # --- CRM & SEGMENTATION INDEXES ---
        # 3. Müşteri segmentasyonu
        Index('idx_cari_tipi_segment', 'cari_tipi', 'segment'),
        Index('idx_cari_sektor_aktif', 'sektor', 'aktif'),
        Index('idx_cari_musteri_grubu', 'musteri_grubu'),
        
        # 4. Risk yönetimi
        Index('idx_cari_risk_durumu', 'risk_durumu'),
        Index('idx_cari_risk_skoru', 'risk_skoru'),
        Index('idx_cari_churn_riski', 'churn_riski'),
        
        # --- FINANCIAL INDEXES ---
        # 5. Finansal sorgular
        Index('idx_cari_bakiye', 'bakiye'),
        Index('idx_cari_toplam_ciro', 'toplam_ciro'),
        Index('idx_cari_ltv', 'tahmini_yasam_boyu_degeri'),
        
        # 6. Aktivite bazlı
        Index('idx_cari_son_siparis', 'son_siparis_tarihi'),
        Index('idx_cari_son_iletisim', 'son_iletisim_tarihi'),
        
        # --- LOCATION INDEXES ---
        # 7. Coğrafi sorgular (AI Rota)
        Index('idx_cari_lokasyon', 'enlem', 'boylam'),
        Index('idx_cari_sehir_ilce', 'sehir_id', 'ilce_id'),
        
        # --- COMBINED BUSINESS LOGIC INDEXES ---
        # 8. Borçlu müşteriler
        Index('idx_cari_borclu', 'firma_id', 'bakiye', 'aktif'),
        
        # 9. VIP müşteriler
        Index('idx_cari_vip', 'segment', 'toplam_ciro', 'aktif'),
        
        # 10. Churn riski yüksek müşteriler
        Index('idx_cari_churn_alarm', 'churn_riski', 'son_siparis_tarihi'),
        
        # --- FULL-TEXT SEARCH (MySQL Özel) ---
        # 11. Metin araması
        Index('idx_cari_fulltext', 'unvan', 'adres', mysql_prefix='FULLTEXT'),
        
        # --- UNIQUE CONSTRAINTS ---
        # 12. İş kuralları
        UniqueConstraint('firma_id', 'kod', name='uq_cari_firma_kod'),
        UniqueConstraint('firma_id', 'vergi_no', name='uq_cari_firma_vkn'),
        UniqueConstraint('firma_id', 'tc_kimlik_no', name='uq_cari_firma_tc'),
        
        # --- CHECK CONSTRAINTS ---
        # 13. Veri bütünlüğü
        CheckConstraint('risk_skoru >= 0 AND risk_skoru <= 100', name='chk_risk_skoru'),
        CheckConstraint('churn_riski >= 0 AND churn_riski <= 100', name='chk_churn_riski'),
        CheckConstraint('sadakat_skoru >= 0 AND sadakat_skoru <= 100', name='chk_sadakat'),
        CheckConstraint('enlem >= -90 AND enlem <= 90', name='chk_enlem'),
        CheckConstraint('boylam >= -180 AND boylam <= 180', name='chk_boylam'),
        
        # Tablo yorumu
        {'comment': 'Cari hesaplar - AI destekli müşteri yönetimi'}
    )
    
    # ========================================
    # HYBRID PROPERTIES (SQL Sorgularında Kullanılabilir)
    # ========================================
    @hybrid_property
    def net_bakiye(self):
        """Net bakiye: Borç - Alacak"""
        borc = self.borc_bakiye or Decimal('0.00')
        alacak = self.alacak_bakiye or Decimal('0.00')
        return borc - alacak
    
    @net_bakiye.expression
    def net_bakiye(cls):
        """SQL sorgularında kullanılabilir"""
        return cls.borc_bakiye - cls.alacak_bakiye
    
    @hybrid_property
    def yas(self):
        """Müşteri yaşı (bireysel müşteriler için)"""
        if not self.dogum_tarihi:
            return None
        bugun = date.today()
        return bugun.year - self.dogum_tarihi.year - (
            (bugun.month, bugun.day) < (self.dogum_tarihi.month, self.dogum_tarihi.day)
        )
    
    @hybrid_property
    def aktif_gun_sayisi(self):
        """İlk siparişten bu yana geçen gün"""
        if not self.ilk_siparis_tarihi:
            return 0
        return (datetime.now() - self.ilk_siparis_tarihi).days
    
    @hybrid_property
    def hareketsiz_gun_sayisi(self):
        """Son siparişten bu yana geçen gün"""
        if not self.son_siparis_tarihi:
            return None
        return (datetime.now() - self.son_siparis_tarihi).days
    
    # ========================================
    # INSTANCE METHODS
    # ========================================
    @property
    def bakiye_durumu_html(self):
        """Şablonlarda kullanmak için renkli HTML"""
        net = self.net_bakiye
        if net > 0:
            return f'<span class="text-danger fw-bold">{net:,.2f} ₺ (B)</span>'
        elif net < 0:
            return f'<span class="text-success fw-bold">{abs(net):,.2f} ₺ (A)</span>'
        else:
            return '<span class="text-muted">0.00 ₺</span>'
    
    @property
    def risk_badge_html(self):
        """Risk durumu için badge"""
        badges = {
            'NORMAL': '<span class="badge bg-success">Normal</span>',
            'DİKKAT': '<span class="badge bg-warning">Dikkat</span>',
            'RİSKLİ': '<span class="badge bg-danger">Riskli</span>',
            'KARA_LİSTE': '<span class="badge bg-dark">Kara Liste</span>'
        }
        return badges.get(self.risk_durumu, '<span class="badge bg-secondary">Bilinmiyor</span>')
    
    def muhasebeden_bakiye_hesapla(self):
        """Muhasebe fişlerinden bakiye hesapla"""
        hesap_ids = [h for h in [self.alis_muhasebe_hesap_id, self.satis_muhasebe_hesap_id] if h]
        if not hesap_ids:
            return Decimal('0.00')
        
        from app.modules.muhasebe.models import MuhasebeFisiDetay
        
        borc_toplam = db.session.query(func.sum(MuhasebeFisiDetay.borc))\
            .filter(MuhasebeFisiDetay.hesap_id.in_(hesap_ids)).scalar() or 0
        
        alacak_toplam = db.session.query(func.sum(MuhasebeFisiDetay.alacak))\
            .filter(MuhasebeFisiDetay.hesap_id.in_(hesap_ids)).scalar() or 0
        
        return Decimal(str(borc_toplam)) - Decimal(str(alacak_toplam))
    
    def ai_analiz_guncelle(self):
        """AI analizlerini güncelle (background task'te çalıştırılmalı)"""
        try:
            # 1. Churn riski hesapla
            if self.hareketsiz_gun_sayisi:
                if self.hareketsiz_gun_sayisi > 180:
                    self.churn_riski = min(90 + (self.hareketsiz_gun_sayisi - 180) / 10, 100)
                elif self.hareketsiz_gun_sayisi > 90:
                    self.churn_riski = 50 + (self.hareketsiz_gun_sayisi - 90) / 3
                else:
                    self.churn_riski = max(0, self.hareketsiz_gun_sayisi / 3)
            
            # 2. LTV hesapla
            if self.aktif_gun_sayisi > 0:
                gunluk_ortalama = float(self.toplam_ciro) / self.aktif_gun_sayisi
                self.tahmini_yasam_boyu_degeri = Decimal(str(gunluk_ortalama * 365 * 3))  # 3 yıllık tahmin
            
            # 3. Risk skoru
            risk_faktörleri = []
            
            if float(self.net_bakiye) > float(self.risk_limiti):
                risk_faktörleri.append(30)
            
            if self.gecikme_sikligi > 30:
                risk_faktörleri.append(25)
            
            if self.hareketsiz_gun_sayisi and self.hareketsiz_gun_sayisi > 120:
                risk_faktörleri.append(20)
            
            self.risk_skoru = min(sum(risk_faktörleri), 100)
            
            # 4. Segment güncelle
            if self.risk_skoru > 70:
                self.segment = 'RİSKLİ'
            elif float(self.toplam_ciro) > 100000:
                self.segment = 'VIP'
            elif self.churn_riski > 60:
                self.segment = 'POTANSİYEL'
            else:
                self.segment = 'STANDART'
            
            logger.info(f"AI analiz güncellendi: {self.unvan}")
            
        except Exception as e:
            logger.error(f"AI analiz hatası ({self.unvan}): {e}")
    
    def __repr__(self):
        return f'<Cari {self.kod} - {self.unvan}>'

# ========================================
# CARİ HAREKET MODEL (Transaction Table - Yüksek Performans)
# ========================================
class CariHareket(db.Model, TimestampMixin):
    __tablename__ = 'cari_hareket'
    
    # ========================================
    # PRIMARY KEY
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
        db.ForeignKey('subeler.id', ondelete='SET NULL'), 
        nullable=True,
        index=True
    )
    
    cari_id = db.Column(
        CHAR(36), 
        db.ForeignKey('cari_hesaplar.id', ondelete='CASCADE'), 
        nullable=False, 
        index=True,
        comment='İlişkili cari hesap'
    )
    
    # ========================================
    # İŞLEM DETAYLARI
    # ========================================
    tarih = db.Column(
        db.Date, 
        nullable=False, 
        default=datetime.now,
        index=True,  # ✅ Tarih sorgularında kritik
        comment='İşlem tarihi'
    )
    
    vade_tarihi = db.Column(
        db.Date,
        nullable=True,
        index=True,  # ✅ Vadesi geçen borçlar için
        comment='Ödeme vade tarihi'
    )
    
    islem_turu = db.Column(
        ENUM(
            'FATURA', 'TAHSILAT', 'TEDIYE', 'VIRMAN', 
            'ACILIS', 'DEVIR', 'DUZELTME', 'CEK', 'SENET',
            name='cari_islem_turu_enum'
        ),
        nullable=False,
        index=True,
        comment='İşlem türü'
    )
    
    belge_no = db.Column(
        db.String(50), 
        nullable=True,
        index=True,  # ✅ Belge numarası araması için
        comment='Fatura/Fiş/Makbuz numarası'
    )
    
    aciklama = db.Column(
        db.String(500),  # 255 → 500 (daha detaylı açıklamalar)
        nullable=True
    )
    
    # ========================================
    # TUTARLAR (Precision: 18,2)
    # ========================================
    borc = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        nullable=False,
        comment='Borç tutarı (Müşteri bize borçlanıyor)'
    )
    
    alacak = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        nullable=False,
        comment='Alacak tutarı (Müşteriden tahsilat)'
    )
    
    # ========================================
    # DÖVİZ İŞLEMLERİ
    # ========================================
    doviz_kodu = db.Column(
        ENUM('TL', 'USD', 'EUR', 'GBP', name='doviz_kodu_enum'),
        default='TL',
        nullable=False,
        index=True
    )
    
    kur = db.Column(
        Numeric(10, 6), 
        default=Decimal('1.000000'),
        nullable=False,
        comment='Döviz kuru (TL karşılığı)'
    )
    
    dovizli_tutar = db.Column(
        Numeric(18, 2), 
        default=Decimal('0.00'),
        comment='Döviz cinsinden tutar'
    )
    
    # ========================================
    # KAYNAK BELGE İZLEME (Document Tracking)
    # ========================================
    fatura_id = db.Column(
        CHAR(36), 
        db.ForeignKey('faturalar.id', ondelete='SET NULL'), 
        nullable=True,
        index=True
    )
    
    cek_id = db.Column(
        CHAR(36), 
        db.ForeignKey('cek_senetler.id', ondelete='SET NULL'), 
        nullable=True,
        index=True
    )
    
    kasa_hareket_id = db.Column(
        CHAR(36), 
        db.ForeignKey('kasa_hareketleri.id', ondelete='SET NULL'), 
        nullable=True,
        index=True
    )
    
    banka_hareket_id = db.Column(
        CHAR(36), 
        db.ForeignKey('banka_hareketleri.id', ondelete='SET NULL'), 
        nullable=True,
        index=True
    )
    
    # Generic source tracking (eski sistem uyumluluğu)
    kaynak_turu = db.Column(
        db.String(20),
        index=True,
        comment='FATURA, TAHSILAT, CEK, SENET, vb.'
    )
    
    kaynak_id = db.Column(
        CHAR(36),
        index=True,
        comment='Kaynak belgenin ID\'si'
    )
    
    # ========================================
    # YAPAY ZEKA VE OTOMATİK KATEGORİZASYON
    # ========================================
    ai_risk_skoru = db.Column(
        db.Integer, 
        default=0,
        index=True,
        comment='Bu işlem için AI risk skoru (0-100)'
    )
    
    ai_kategori = db.Column(
        db.String(50), 
        nullable=True,
        index=True,
        comment='AI tarafından otomatik kategorize edilmiş (RUTIN, ŞÜPHELI, YÜKSEK_DEGER)'
    )
    
    ai_metadata = db.Column(
        JSON,
        nullable=True,
        comment='AI analizleri için esnek veri'
    )
    # Örnek ai_metadata:
    # {
    #     "tahmin_edilen_odeme_tarihi": "2024-02-15",
    #     "tahsilat_olasiligi": 0.85,
    #     "anomali_tespiti": false,
    #     "benzer_islemler": ["id1", "id2"]
    # }
    
    # ========================================
    # SİSTEM ALANLARI
    # ========================================
    olusturan_id = db.Column(
        CHAR(36), 
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'), 
        nullable=True,
        index=True
    )
    
    olusturma_tarihi = db.Column(
        db.DateTime, 
        default=datetime.now,
        nullable=False
    )
    
    guncelleyen_id = db.Column(
        CHAR(36),
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'),
        nullable=True
    )
    
    guncelleme_tarihi = db.Column(
        db.DateTime,
        onupdate=datetime.now
    )
    
    onaylayan_id = db.Column(
        CHAR(36),
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'),
        nullable=True,
        comment='İşlemi onaylayan yetkili'
    )
    
    onay_tarihi = db.Column(
        db.DateTime,
        nullable=True
    )
    
    durum = db.Column(
        ENUM('TASLAK', 'ONAYLANDI', 'İPTAL', name='hareket_durum_enum'),
        default='ONAYLANDI',
        nullable=False,
        index=True
    )
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    cari = db.relationship(
        'CariHesap',
        back_populates='hareketler',
        lazy='joined'  # Cari bilgilerini her zaman yükle
    )
    
    fatura = db.relationship('Fatura', lazy='select')
    cek = db.relationship('CekSenet', lazy='select')
    kasa_hareket = db.relationship('KasaHareket', lazy='select')
    banka_hareket = db.relationship('BankaHareket', lazy='select')
    
    olusturan = db.relationship('Kullanici', foreign_keys=[olusturan_id], lazy='select')
    guncelleyen = db.relationship('Kullanici', foreign_keys=[guncelleyen_id], lazy='select')
    onaylayan = db.relationship('Kullanici', foreign_keys=[onaylayan_id], lazy='select')
    
    # ========================================
    # 🔥 COMPOSITE INDEXES (TRANSACTION TABLE - KRİTİK!)
    # ========================================
    __table_args__ = (
        # --- PRIMARY TRANSACTION INDEXES ---
        # 1. Ekstre sorguları (EN ÖNEMLİ!)
        Index('idx_hareket_cari_tarih', 'cari_id', 'tarih', 'durum'),
        Index('idx_hareket_cari_vade', 'cari_id', 'vade_tarihi', 'durum'),
        
        # 2. Firma bazlı sorgular
        Index('idx_hareket_firma_tarih', 'firma_id', 'tarih'),
        Index('idx_hareket_firma_donem', 'firma_id', 'donem_id', 'tarih'),
        
        # 3. Dönem kapanış sorguları
        Index('idx_hareket_donem_tarih', 'donem_id', 'tarih'),
        
        # --- DOCUMENT TRACKING INDEXES ---
        # 4. Belge numarası ve kaynak izleme
        Index('idx_hareket_belge_no', 'belge_no', 'firma_id'),
        Index('idx_hareket_kaynak', 'kaynak_turu', 'kaynak_id'),
        Index('idx_hareket_fatura', 'fatura_id'),
        Index('idx_hareket_cek', 'cek_id'),
        
        # --- FINANCIAL ANALYSIS INDEXES ---
        # 5. İşlem türü bazlı analizler
        Index('idx_hareket_tur_tarih', 'islem_turu', 'tarih'),
        Index('idx_hareket_tur_cari', 'islem_turu', 'cari_id'),
        
        # 6. Döviz işlemleri
        Index('idx_hareket_doviz', 'doviz_kodu', 'tarih'),
        
        # 7. Vadesi geçen borçlar (KRİTİK!)
        Index('idx_hareket_vade_alarm', 'vade_tarihi', 'durum', 'cari_id'),
        
        # --- AI & RISK INDEXES ---
        # 8. AI analizleri
        Index('idx_hareket_ai_risk', 'ai_risk_skoru', 'tarih'),
        Index('idx_hareket_ai_kategori', 'ai_kategori'),
        
        # --- AUDIT INDEXES ---
        # 9. Kullanıcı işlemleri
        Index('idx_hareket_olusturan', 'olusturan_id', 'olusturma_tarihi'),
        Index('idx_hareket_durum', 'durum', 'tarih'),
        
        # --- COMBINED BUSINESS LOGIC ---
        # 10. Tahsilat bekleyen faturalar
        Index('idx_hareket_tahsilat', 'cari_id', 'islem_turu', 'vade_tarihi'),
        
        # 11. Dönemsel cari mizan
        Index('idx_hareket_mizan', 'firma_id', 'donem_id', 'cari_id', 'tarih'),
        
        # --- UNIQUE CONSTRAINTS ---
        # 12. Aynı belge tekrar girilmesin
        UniqueConstraint(
            'firma_id', 'belge_no', 'kaynak_turu', 'tarih',
            name='uq_hareket_belge'
        ),
        
        # --- CHECK CONSTRAINTS ---
        CheckConstraint(
            '(borc > 0 AND alacak = 0) OR (alacak > 0 AND borc = 0) OR (borc = 0 AND alacak = 0)',
            name='chk_borc_alacak_mutex'
        ),
        CheckConstraint('kur > 0', name='chk_kur_pozitif'),
        
        {'comment': 'Cari hareketler - Yüksek hacimli transaction table'}
    )
    
    # ========================================
    # HYBRID PROPERTIES
    # ========================================
    @hybrid_property
    def bakiye_etkisi(self):
        """Bu işlemin bakiyeye etkisi"""
        return self.borc - self.alacak
    
    @bakiye_etkisi.expression
    def bakiye_etkisi(cls):
        return cls.borc - cls.alacak
    
    @hybrid_property
    def tl_tutar(self):
        """TL karşılığı tutar"""
        if self.doviz_kodu == 'TL':
            return self.borc if self.borc > 0 else self.alacak
        else:
            return self.dovizli_tutar * self.kur
    
    @hybrid_property
    def gecikme_gun_sayisi(self):
        """Vade geçmiş ise kaç gün gecikmiş"""
        if not self.vade_tarihi or self.durum != 'ONAYLANDI':
            return 0
        
        bugun = date.today()
        if bugun > self.vade_tarihi:
            return (bugun - self.vade_tarihi).days
        return 0
    
    # ========================================
    # INSTANCE METHODS
    # ========================================
    def onayla(self, onaylayan_user):
        """İşlemi onayla ve bakiyeyi güncelle"""
        if self.durum == 'ONAYLANDI':
            raise ValueError('İşlem zaten onaylı')
        
        self.durum = 'ONAYLANDI'
        self.onaylayan_id = onaylayan_user.id
        self.onay_tarihi = datetime.now()
        
        # Cari bakiyesini güncelle
        cari = self.cari
        cari.borc_bakiye += self.borc
        cari.alacak_bakiye += self.alacak
        cari.bakiye = cari.borc_bakiye - cari.alacak_bakiye
        
        logger.info(f"Cari hareket onaylandı: {self.belge_no}")
    
    def iptal_et(self, iptal_eden_user, iptal_nedeni):
        """İşlemi iptal et ve bakiyeyi düzelt"""
        if self.durum == 'İPTAL':
            raise ValueError('İşlem zaten iptal edilmiş')
        
        # Bakiyeyi eski haline getir
        cari = self.cari
        cari.borc_bakiye -= self.borc
        cari.alacak_bakiye -= self.alacak
        cari.bakiye = cari.borc_bakiye - cari.alacak_bakiye
        
        self.durum = 'İPTAL'
        self.guncelleyen_id = iptal_eden_user.id
        self.guncelleme_tarihi = datetime.now()
        self.aciklama += f" [İPTAL: {iptal_nedeni}]"
        
        logger.warning(f"Cari hareket iptal edildi: {self.belge_no} - {iptal_nedeni}")
    
    def __repr__(self):
        return f"<CariHareket {self.belge_no} - {self.borc}/{self.alacak}>"


# ========================================
# CRM HAREKET MODELİ (Customer Relationship Management)
# ========================================
class CRMHareket(db.Model, TimestampMixin):
    __tablename__ = 'crm_hareketleri'
    
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
    
    cari_id = db.Column(
        CHAR(36), 
        db.ForeignKey('cari_hesaplar.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='İlgili müşteri'
    )
    
    plasiyer_id = db.Column(
        CHAR(36), 
        db.ForeignKey('kullanicilar.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='Görüşmeyi yapan satış temsilcisi'
    )
    
    # ========================================
    # İŞLEM DETAYLARI
    # ========================================
    tarih = db.Column(
        db.DateTime, 
        server_default=db.func.now(),
        nullable=False,
        index=True
    )
    
    islem_turu = db.Column(
        ENUM(
            'ARAMA', 'ZIYARET', 'EMAIL', 'TOPLANTI', 
            'SIKAYET', 'TALEP', 'TEKLIF', 'NOTLAR',
            name='crm_islem_turu_enum'
        ),
        nullable=False,
        index=True
    )
    
    konu = db.Column(
        db.String(200),
        nullable=True,
        comment='Görüşme konusu başlığı'
    )
    
    detay_notu = db.Column(
        LONGTEXT,
        nullable=True,
        comment='Detaylı görüşme notu'
    )
    
    # ========================================
    # DUYGU ANALİZİ (AI)
    # ========================================
    duygu_durumu = db.Column(
        ENUM('MUTLU', 'NORMAL', 'MUTSUZ', 'SİNİRLİ', 'BELİRSİZ', name='duygu_enum'),
        default='BELİRSİZ',
        index=True,
        comment='AI duygu analizi sonucu'
    )
    
    memnuniyet_skoru = db.Column(
        db.Integer,
        nullable=True,
        comment='1-10 arası memnuniyet puanı'
    )
    
    # ========================================
    # AKSIYONLAR
    # ========================================
    aksiyon_gerekli = db.Column(
        db.Boolean,
        default=False,
        index=True,
        comment='Takip gerekiyor mu?'
    )
    
    aksiyon_tarihi = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
        comment='Takip hatırlatma tarihi'
    )
    
    aksiyon_tamamlandi = db.Column(
        db.Boolean,
        default=False,
        index=True
    )
    
    # ========================================
    # AI METADATA
    # ========================================
    ai_metadata = db.Column(
        JSON,
        nullable=True,
        comment='AI analizleri: anahtar kelimeler, öneriler, vb.'
    )
    # Örnek:
    # {
    #     "anahtar_kelimeler": ["fiyat", "iskonto", "teslim"],
    #     "satiş_firsati": true,
    #     "churn_riski": false,
    #     "oneri": "İskonto teklifi yap"
    # }
    
    # ========================================
    # İLİŞKİLER
    # ========================================
    cari = db.relationship(
        'CariHesap', 
        back_populates='crm_kayitlari',
        lazy='joined'
    )
    
    plasiyer = db.relationship('Kullanici', lazy='select')
    
    # ========================================
    # INDEXES
    # ========================================
    __table_args__ = (
        Index('idx_crm_cari_tarih', 'cari_id', 'tarih'),
        Index('idx_crm_plasiyer_tarih', 'plasiyer_id', 'tarih'),
        Index('idx_crm_tur', 'islem_turu'),
        Index('idx_crm_duygu', 'duygu_durumu'),
        Index('idx_crm_aksiyon', 'aksiyon_gerekli', 'aksiyon_tarihi'),
        Index('idx_crm_firma_tarih', 'firma_id', 'tarih'),
        
        # Full-text search
        Index('idx_crm_fulltext', 'konu', 'detay_notu', mysql_prefix='FULLTEXT'),
        
        {'comment': 'CRM hareketleri - Müşteri iletişim takibi'}
    )
    
    def __repr__(self):
        return f"<CRMHareket {self.islem_turu} - {self.cari.unvan if self.cari else 'N/A'}>"


# ========================================
# EVENT LISTENERS (Otomatik İşlemler)
# ========================================

@event.listens_for(CariHareket, 'after_insert')
def cari_hareket_after_insert(mapper, connection, target):
    """Yeni hareket eklenince cari bakiyesini güncelle"""
    if target.durum == 'ONAYLANDI':
        # Bakiye güncelleme (bulk update - performanslı)
        connection.execute(
            db.update(CariHesap.__table__)
            .where(CariHesap.__table__.c.id == target.cari_id)
            .values(
                borc_bakiye=CariHesap.__table__.c.borc_bakiye + target.borc,
                alacak_bakiye=CariHesap.__table__.c.alacak_bakiye + target.alacak,
                bakiye=CariHesap.__table__.c.bakiye + (target.borc - target.alacak),
                son_siparis_tarihi=target.tarih  # Son aktivite güncelle
            )
        )


@event.listens_for(CariHareket, 'after_update')
def cari_hareket_after_update(mapper, connection, target):
    """Hareket güncellenince bakiyeyi yeniden hesapla"""
    if target.durum == 'İPTAL':
        # İptal edilen hareketi bakiyeden düş
        connection.execute(
            db.update(CariHesap.__table__)
            .where(CariHesap.__table__.c.id == target.cari_id)
            .values(
                borc_bakiye=CariHesap.__table__.c.borc_bakiye - target.borc,
                alacak_bakiye=CariHesap.__table__.c.alacak_bakiye - target.alacak,
                bakiye=CariHesap.__table__.c.bakiye - (target.borc - target.alacak)
            )
        )


@event.listens_for(CariHesap, 'before_insert')
def cari_hesap_before_insert(mapper, connection, target):
    # İlk sipariş tarihi boş kalmalı (sipariş eklenince set edilecek)
    
    # Varsayılan segment
    if not target.segment:
        target.segment = 'STANDART'
    
    # Varsayılan risk skoru
    if target.risk_skoru is None:
        target.risk_skoru = 50

@event.listens_for(CRMHareket, 'after_insert')
def crm_hareket_after_insert(mapper, connection, target):
    """CRM kaydı eklenince cari'nin son iletişim tarihini güncelle"""
    connection.execute(
        db.update(CariHesap.__table__)
        .where(CariHesap.__table__.c.id == target.cari_id)
        .values(son_iletisim_tarihi=target.tarih.date())
    )
    
