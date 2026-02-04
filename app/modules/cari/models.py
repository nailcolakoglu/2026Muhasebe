# modules/cari/models.py

from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin, JSONText
from sqlalchemy.orm import relationship
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.enums import CariTipi, CariIslemTuru, CariTipi, ParaBirimi
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class CariHesap(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'cari_hesaplar'
    query_class = FirmaFilteredQuery
    # query_class satırını eğer özel bir Query sınıfı kullanıyorsan açabilirsin
    
    # --- 1.KİMLİK VE LOKASYON ---
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    kod = db.Column(db.String(20), nullable=False, index=True) # Index ile arama hızlanır
    unvan = db.Column(db.String(200), nullable=False, index=True)
    
    vergi_no = db.Column(db.String(20))
    vergi_dairesi = db.Column(db.String(50))
    tc_kimlik_no = db.Column(db.String(11))

    # Adres Detayları
    adres = db.Column(db.String(255))
    sehir_id = db.Column(db.String(36), db.ForeignKey('sehirler.id'), nullable=True)
    ilce_id = db.Column(db.String(36), db.ForeignKey('ilceler.id'), nullable=True)
    konum = db.Column(db.String(50))
    # İletişim
    telefon = db.Column(db.String(20))
    eposta = db.Column(db.String(100))
    web_site = db.Column(db.String(100)) # Opsiyonel: AI web sitesinden veri çekebilir

    # --- 2.FİNANSAL DURUM (Veritabanı Sütunları) ---
    # DİKKAT: Bunlar @property DEĞİL, db.Column olmalı ki veri yazabilelim.
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)
    borc_bakiye = db.Column(Numeric(18, 4), default=Decimal('0.0000'))
    alacak_bakiye = db.Column(Numeric(18, 4), default=Decimal('0.0000'))
    
    # Muhasebe Entegrasyonu
    alis_muhasebe_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)
    satis_muhasebe_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)

    risk_limiti = db.Column(db.Numeric(18, 2), default=0)
    risk_durumu = db.Column(db.String(20), default='NORMAL')

    # 🔥 SİZİN YAPINIZA UYGUN ENTEGRASYON ALANLARI 🔥              silinecek
    kaynak_turu = db.Column(db.String(20)) # 'fatura', 'tahsilat', 'cek'
    kaynak_id = db.Column(db.String(36))      # Fatura ID'si

    # --- 3.TİCARİ ANALİZ (Metrikler) ---
    ilk_siparis_tarihi = db.Column(db.DateTime, nullable=True)
    son_siparis_tarihi = db.Column(db.DateTime, nullable=True)
    toplam_siparis_sayisi = db.Column(db.Integer, default=0)
    toplam_ciro = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    ortalama_odeme_gunu = db.Column(db.Integer, default=0) # Örn: 45 gün

    # --- 4.YAPAY ZEKA VE CRM (AI Destekli) ---
    aktif = db.Column(db.Boolean, default=True)
    sektor = db.Column(db.String(100))      # Örn: İnşaat, Tekstil
    cari_tipi = db.Column(db.Enum(CariTipi), default=CariTipi.BIREYSEL) # Kurumsal/Bireysel

    # AI Lojistik İçin (Rota Optimizasyonu)
    enlem = db.Column(Numeric(10, 6), nullable=True) 
    boylam = db.Column(Numeric(10, 6), nullable=True)

    # --- FİNANSAL ZEKA (AI ANALİZ ALANLARI) ---
    bakiye = db.Column(Numeric(18, 2), default=Decimal('0.00')) # Anlık Bakiye

    # Risk Yönetimi
    risk_limiti = db.Column(Numeric(18, 2), default=Decimal('0.00')) # Max açabileceği borç
    teminat_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00')) # Alınan çek/senet/teminat
    acik_hesap_limiti = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # Ödeme Performansı (AI Hesaplayacak)
    ortalama_odeme_suresi = db.Column(db.Integer, default=0) # Gün (Örn: Ort.45 günde ödüyor)
    gecikme_sikligi = db.Column(Numeric(5, 2), default=0) # % (Ödemelerin % kaçı gecikiyor?)
    
    # --- CRM & SEGMENTASYON ---
    cari_tipi = db.Column(db.String(20), default='ALICI') # ALICI, SATICI, PERSONEL
    sektor = db.Column(db.String(50)) # Gıda, İnşaat, Tekstil...
    musteri_grubu = db.Column(db.String(50)) # VIP, Toptancı, Perakende, Kara Liste

    # AI Segmentasyon & Risk
    segment = db.Column(db.String(50), default='STANDART') # VIP, RİSKLİ, POTANSİYEL
    risk_skoru = db.Column(db.Integer, default=0) # 0-100 arası (Mükerrer tanım silindi)
    odeme_performansi = db.Column(db.String(20))  # "Hızlı", "Gecikmeli"
    
    # AI Özeti (LLM ile oluşturulan metin buraya kaydedilir)
    ai_ozeti = db.Column(db.Text, nullable=True) 
    
    # AI için Esnek Veri Alanı (JSON)
    # Buraya { "churn_ihtimali": 85, "duygu_analizi": "mutsuz", "oneri": "İskonto yap" } gibi veri atabilirsin.
    # Firebird 3.0+ JSON destekler veya Text olarak tutulur.SQLAlchemy JSON tipi iş görür.
    ai_metadata = db.Column(JSONText, nullable=True)

    # AI Müşteri Değeri
    churn_riski = db.Column(Numeric(5, 2), default=0) # % (Kaybetme riski)
    sadakat_skoru = db.Column(db.Integer, default=50) # 0-100 arası puan

    # Bireysel Müşteri Detayları
    dogum_tarihi = db.Column(db.Date)
    cinsiyet = db.Column(db.String(10))
    son_iletisim_tarihi = db.Column(db.Date)

    # 2.İSTEK: Müşterinin Varsayılan Ödeme Planı
    odeme_plani_id = db.Column(db.String(36), db.ForeignKey('odeme_planlari.id'), nullable=True)
    
    # İlişki tanımı
    odeme_plani_rel = db.relationship('OdemePlani', foreign_keys=[odeme_plani_id])

    # --- İLİŞKİLER ---
    sehir = db.relationship('Sehir')
    ilce = db.relationship('Ilce')
    
    # Cascade: Cari silinirse faturaları yetim kalmasın (veya silinsin) ayarı
    faturalar = db.relationship('Fatura', back_populates='cari', lazy='dynamic')
    siparisler = db.relationship('Siparis', back_populates='cari', lazy='dynamic')
    cekler = db.relationship('CekSenet', back_populates='cari', lazy='dynamic')
    crm_kayitlari = db.relationship('CRMHareket', back_populates='cari', lazy='dynamic') # CRM Hareket modelin varsa aç

    # --- YARDIMCI ÖZELLİKLER (Properties) ---

    @property
    def net_bakiye(self):
        """
        Anlık net bakiyeyi hesaplar.
        Pozitif (+) ise Cari Borçlu (Bize vereceği var)
        Negatif (-) ise Cari Alacaklı (Bizim ona borcumuz var)
        """
        borc = self.borc_bakiye or Decimal('0.00')
        alacak = self.alacak_bakiye or Decimal('0.00')
        return borc - alacak

    @property
    def bakiye_durumu_html(self):
        """Şablonlarda (Jinja2) kullanmak için renkli durum döner"""
        net = self.net_bakiye
        if net > 0:
            return f'<span class="text-danger fw-bold">{net:,.2f} (B)</span>' # Borçlu
        elif net < 0:
            return f'<span class="text-success fw-bold">{abs(net):,.2f} (A)</span>' # Alacaklı
        else:
            return '<span class="text-muted">-</span>'

    def muhasebeden_bakiye_hesapla(self):
        """
        Eğer bakiyeyi Kasa/Banka hareketlerinden değil de,
        Doğrudan Muhasebe Fişlerinden (Mizan mantığıyla) hesaplamak istersen bunu çağırırsın.
        Bu metod veritabanını güncellemez, sadece anlık hesaplar.
        """
        hesap_ids = [h for h in [self.alis_muhasebe_hesap_id, self.satis_muhasebe_hesap_id] if h]
        if not hesap_ids: return Decimal('0.00')
        
        # MuhasebeFisiDetay modelini import etmen gerekir
        from models import MuhasebeFisiDetay 
        
        borc_toplam = db.session.query(func.sum(MuhasebeFisiDetay.borc))\
            .filter(MuhasebeFisiDetay.hesap_id.in_(hesap_ids)).scalar() or 0
            
        alacak_toplam = db.session.query(func.sum(MuhasebeFisiDetay.alacak))\
            .filter(MuhasebeFisiDetay.hesap_id.in_(hesap_ids)).scalar() or 0
            
        return Decimal(str(borc_toplam)) - Decimal(str(alacak_toplam))

    def __repr__(self):
        return f'<Cari {self.kod} - {self.unvan}>'

class CariHareket(db.Model):
    __tablename__ = 'cari_hareket'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    # DÜZELTME: 'firma.id' -> 'firmalar.id'
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    # DÜZELTME: 'donem.id' -> 'donemler.id'
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=False, index=True)
    # DÜZELTME: 'sube.id' -> 'subeler.id'
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=True) 


    # --- ANA İLİŞKİ ---
    # DÜZELTME: 'cari_hesap.id' -> 'cari_hesaplar.id'
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=False, index=True)
    
    # --- İŞLEM DETAYLARI ---
    tarih = db.Column(db.Date, nullable=False, default=datetime.now)
    islem_turu = db.Column(db.Enum(CariIslemTuru), nullable=False)
    belge_no = db.Column(db.String(50), nullable=True)
    aciklama = db.Column(db.String(255), nullable=True)
    
    # --- TUTARLAR ---
    borc = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    alacak = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # --- DÖVİZ ---
    doviz_kodu = db.Column(db.String(3), default='TL')
    kur = db.Column(Numeric(10, 6), default=Decimal('1.00'))
    dovizli_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00')) 
    
    # --- KAYNAK BELGE İZİ (Tablo isimleri düzeltildi) ---
    fatura_id = db.Column(db.String(36), db.ForeignKey('faturalar.id'), nullable=True)
    cek_id = db.Column(db.String(36), db.ForeignKey('cek_senetler.id'), nullable=True)
    kasa_hareket_id = db.Column(db.String(36), db.ForeignKey('kasa_hareketleri.id'), nullable=True)
    banka_hareket_id = db.Column(db.String(36), db.ForeignKey('banka_hareketleri.id'), nullable=True)
    kaynak_turu = db.Column(db.String(20)) # 'fatura', 'tahsilat'
    kaynak_id = db.Column(db.String(36))      # Fatura ID'si
    # --- AI VE SİSTEM ---
    ai_risk_skoru = db.Column(db.Integer, default=0)
    ai_kategori = db.Column(db.String(50), nullable=True)
    
    # DÜZELTME: 'kullanici.id' -> 'kullanicilar.id'
    olusturan_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.now)

    @property
    def bakiye_etkisi(self):
        return self.borc - self.alacak

    def __repr__(self):
        return f"<CariHareket {self.belge_no} - {self.borc}/{self.alacak}>"
        
class CRMHareket(db.Model):
    __tablename__ = 'crm_hareketleri'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'))
    plasiyer_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))
    
    tarih = db.Column(db.DateTime, server_default=db.func.now())
    islem_turu = db.Column(db.String(20), nullable=False)
    konu = db.Column(db.String(100))
    detay_notu = db.Column(db.Text)
    duygu_durumu = db.Column(db.String(20), default='belirsiz')
    
    # İlişkiler - Lazy import ile circular dependency önlenir
    cari = db.relationship('CariHesap', back_populates='crm_kayitlari', lazy='select')
    plasiyer = db.relationship('Kullanici', lazy='select')
