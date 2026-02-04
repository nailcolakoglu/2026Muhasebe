# app/modules/stok/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import StokKartTipi, ParaBirimi, HareketTuru
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())
              
class StokKart(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'stok_kartlari'
    query_class = FirmaFilteredQuery

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    # --- Temel Kimlik ---
    kod = db.Column(db.String(50), nullable=False)
    ad = db.Column(db.String(200), nullable=False)
    barkod = db.Column(db.String(50), nullable=True)
    uretici_kodu = db.Column(db.String(50)) # ✅ EKLENDİ: (MPN) Üretici Parça Kodu
    
    # --- Tür ve Yapı ---
    birim = db.Column(db.String(10), default='Adet')
    tip = db.Column(db.Enum(StokKartTipi), default=StokKartTipi.STANDART, nullable=False)
    kategori_id = db.Column(db.String(36), db.ForeignKey('stok_kategorileri.id'))      # Ürün Gruplandırması için
    
    # --- Finansal Veriler ---
    alis_fiyati = db.Column(Numeric(18, 6), default=Decimal('0.00'))    # Bağlı Sermaye Hesaplaması için
    satis_fiyati = db.Column(Numeric(18, 6), default=Decimal('0.00'))    # Kar marjı analizi için
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)

    # --- Muhasebe & Vergi (Grup Yapısı) ---
    muhasebe_kod_id = db.Column(db.String(36), db.ForeignKey('stok_muhasebe_gruplari.id'))
    kdv_kod_id = db.Column(db.String(36), db.ForeignKey('stok_kdv_gruplari.id'))    

    # --- Lojistik & AI Analiz Alanları ---
    kritik_seviye = db.Column(Numeric(18, 6), default=Decimal('0.00'))    # Stok Uyarıları için
    tedarik_suresi_gun = db.Column(db.Integer, default=3) # Bu ürünü sipariş etsek kaç günde gelir? (Stok optimizasyonu)
    raf_omru_gun = db.Column(db.Integer)                  # Gıda/İlaç için (Fire tahmini)
    # 4.Boyutlar (Kargo Maliyeti Tahmini İçin)
    agirlik_kg = db.Column(Numeric(10, 4), default=Decimal('0.0000'))
    desi = db.Column(Numeric(10, 3), default=Decimal('0.000'))
    
    # --- Tedarik Zinciri & Mevsimsellik ---
    tedarikci_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'))         # Tedarikçi Performansı için
    mevsimsel_grup = db.Column(db.String(50))               # Kış, Yaz, Yaz Sonu Vb.

    # --- Segmentasyon ---
    # 1.Segmentasyon ve Gruplama İçin
    marka = db.Column(db.String(100))        # Örn: Samsung, Nike (Marka sadakati analizi için)
    model = db.Column(db.String(100))        # Örn: Galaxy S24 (Ürün yaşam döngüsü analizi için)
    mensei = db.Column(db.String(50))        # Örn: TR, CN, DE (Tedarik risk analizi için)

    # --- Detay ve NLP ---
    # 2.NLP ve Arama İçin
    anahtar_kelimeler = db.Column(db.String(255)) # Örn: "yazlık, pamuklu, spor" (Benzer ürün bulma)
    aciklama_detay = db.Column(db.Text)           # AI'nın ürün açıklaması y#azması veya SEO için
    garanti_suresi_ay = db.Column(db.Integer, default=24) # ✅ EKLENDİ

    # --- Raporlama ---
    ozel_kod1 = db.Column(db.String(50)) # ✅ EKLENDİ
    ozel_kod2 = db.Column(db.String(50)) # ✅ EKLENDİ

    resim_path = db.Column(db.String(255))
    aktif = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, server_default=func.now())
    
    # İlişkiler 
    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_stok_kod'),)

    kategori = db.relationship('StokKategori', backref='urunler')
    tedarikci = db.relationship('CariHesap', foreign_keys=[tedarikci_id], backref='tedarik_edilen_urunler')
    muhasebe_grubu = db.relationship('StokMuhasebeGrubu', backref='stoklar')
    kdv_grubu = db.relationship('StokKDVGrubu', backref='stoklar')
    # 👇 EKSİK OLAN KRİTİK İLİŞKİLER 👇
    # Bu ürünün tüm hareketleri (Giriş/Çıkış)
    hareketler = db.relationship('StokHareketi', backref='stok_rel', lazy='dynamic', cascade="all, delete-orphan")
    
    # Bu ürün hangi depolarda ne kadar var?
    depo_durumlari = db.relationship('StokDepoDurumu', back_populates='stok', lazy='joined', cascade="all, delete-orphan")
    
    # Bu ürün hangi faturaların içinde geçmiş? (Satış analizi için altın değerinde)
    fatura_kalemleri = db.relationship('FaturaKalemi', back_populates='stok', lazy='dynamic')

class StokPaketIcerigi(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Paket ürünlerin içeriğini tutar.
    Örn: 'Yılbaşı Paketi' (Parent) içinde -> 1 Adet 'Kahve' (Child) + 2 Adet 'Çikolata' (Child)
    """
    __tablename__ = 'stok_paket_icerigi'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    # Ana Ürün (Paketin Kendisi) - Tipi 'paket' olmalı
    paket_stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    # İçindeki Ürün - Tipi 'standart' olmalı
    alt_stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    miktar = db.Column(Numeric(15, 4), default=1) # Kaç adet var?
    
    # İlişkiler
    paket = db.relationship('StokKart', foreign_keys=[paket_stok_id], backref='paket_icerigi')
    alt_urun = db.relationship('StokKart', foreign_keys=[alt_stok_id])
    
class StokMuhasebeGrubu(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'stok_muhasebe_gruplari'
    query_class = FirmaFilteredQuery

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    kod = db.Column(db.String(50), nullable=False) 
    ad = db.Column(db.String(100), nullable=False) 
    
    # --- Muhasebe Hesap Bağlantıları ---
    # Stok (Envanter) Hesapları (153)
    alis_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'))       
    # Satış Hasılat Hesapları (600)
    satis_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'))      
    
    # İade Hesapları
    alis_iade_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'))  # 153 Alacak
    satis_iade_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id')) # 610 Borç
    
    # ✅ YENİ: Satılan Malın Maliyeti (621) - Bunu açmanı öneririm
    satilan_mal_maliyeti_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id')) 
    
    aciklama = db.Column(db.String(255))
    aktif = db.Column(db.Boolean, default=True)

    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_stok_muh_kod'),)

class StokKDVGrubu(db.Model):
    __tablename__ = 'stok_kdv_gruplari'
    query_class = FirmaFilteredQuery

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    kod = db.Column(db.String(20), nullable=False) 
    ad = db.Column(db.String(50), nullable=False)  
    
    # Oranlar
    alis_kdv_orani = db.Column(db.Integer, default=20)
    satis_kdv_orani = db.Column(db.Integer, default=20)
    
    # ✅✅✅ KRİTİK EKSİK BURADAYDI: Hesap ID'leri ✅✅✅
    # Bu alanlar olmazsa fişe KDV yazamayız!
    # Muhasebe Hesapları
    alis_kdv_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'))   # 191
    satis_kdv_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'))  # 391
    
    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_stok_kdv_kod'),)

    def __repr__(self):
        return f"<KDVGrubu {self.kod} - %{self.satis_kdv_orani}>"

class StokDepoDurumu(db.Model):
    __tablename__ = 'stok_depo_durumu'
    query_class = FirmaFilteredQuery # 1.Firma bazlı izolasyon için eklendi
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    
    depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=False)
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    miktar = db.Column(Numeric(18, 6), default=Decimal('0.000000'))
    
    # İleride Maliyet Analizi için eklenebilir:
    # ortalama_maliyet = db.Column(Numeric(15, 2), default=0.0)
    
    # 2.Kritik Kural: Bir depoda aynı üründen 2.satır olamaz
    __table_args__ = (UniqueConstraint('depo_id', 'stok_id', name='uq_stok_depo'),)
    
    # 3.İlişkiler (Backref isimleri güncellendi)
    depo = db.relationship('Depo', backref='stok_listesi')
    stok = db.relationship('StokKart', back_populates='depo_durumlari')

class StokHareketi(db.Model):
    __tablename__ = 'stok_hareketleri'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    # --- İLİŞKİLER ---
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=False)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=False)
    kullanici_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))
    
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    # Depo Transferlerinde her iki alan da dolabilir
    giris_depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=True)
    cikis_depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=True)

    # --- HAREKET DETAYLARI ---
    tarih = db.Column(db.Date, nullable=False, index=True)
    belge_no = db.Column(db.String(50), index=True) # Fatura No, Fiş No vb.
    hareket_turu = db.Column(db.Enum(HareketTuru), nullable=False) # alis, satis, devir vb.
    aciklama = db.Column(db.String(255))
    
    # --- MİKTAR VE FİYAT ---
    miktar = db.Column(Numeric(18, 4), default=Decimal('0.0000')) # 1.5000 Adet
    birim_fiyat = db.Column(Numeric(15, 4), default=Decimal('0.0000')) # İskontosuz Ham Fiyat
    
    # --- YENİ EKLENEN FİNANSAL ALANLAR ---
    
    # 1.Döviz Bilgileri
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)
    doviz_kuru = db.Column(Numeric(10, 4), default=Decimal('1.0000'))  # 32.5000 (TL ise 1.0000)
    
    # 2.İskonto Bilgileri (Satır İskontosu)
    iskonto_orani = db.Column(Numeric(5, 2), default=Decimal('0.00')) # %10.00
    iskonto_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00')) # 100 TL (Hesaplanmış)
    
    # 3.KDV Bilgileri
    kdv_orani = db.Column(db.Integer, default=0) # 0, 1, 10, 20
    kdv_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00')) # KDV'nin parasal değeri
    
    # 4.Net Rakamlar (Maliyet Hesabı İçin Kritik)
    # Net Tutar = (Miktar * Birim Fiyat) - İskonto
    net_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00')) 
    
    # Genel Toplam = Net Tutar + KDV
    toplam_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00')) 

    # --- LOG BİLGİLERİ ---
    olusturma_tarihi = db.Column(db.DateTime, server_default=func.now())
    # Hangi kaynaktan geldiği (Fatura ID'si veya Stok Fişi ID'si)
    # Bu, kaydı silerken veya güncellerken çok işe yarar
    kaynak_id = db.Column(db.String(36), nullable=True) 
    kaynak_turu = db.Column(db.String(20)) # 'fatura', 'stok_fisi'  
    kaynak_belge_detay_id = db.Column(db.String(36), nullable=True)
    giris_depo = db.relationship('Depo', foreign_keys=[giris_depo_id], backref='giris_hareketleri')
    cikis_depo = db.relationship('Depo', foreign_keys=[cikis_depo_id], backref='cikis_hareketleri')
    @property
    def yon(self):
        """
        Hareketin stoğa etkisini belirler.
        """
        # Stok Artıranlar (Kesin Girişler)
        if self.hareket_turu in [
            HareketTuru.GIRIS, 
            HareketTuru.DEVIR, 
            HareketTuru.ALIS, 
            HareketTuru.SATIS_IADE, 
            HareketTuru.URETIM,
            HareketTuru.SAYIM_FAZLA
        ]: 
            return 1
            
        # Stok Azaltanlar (Kesin Çıkışlar)
        if self.hareket_turu in [
            HareketTuru.CIKIS, 
            HareketTuru.SATIS, 
            HareketTuru.ALIS_IADE,
            HareketTuru.URETIM_CIKIS,
            HareketTuru.SARF,
            HareketTuru.FIRE,
            HareketTuru.SAYIM_EKSIK
        ]: 
            return -1
            
        # --- DÜZELTİLEN KISIM: TRANSFER ---
        if self.hareket_turu == HareketTuru.TRANSFER:
            # Eğer bu satırda 'giris_depo_id' doluysa, bu depo için Giriş (+1) demektir.
            if self.giris_depo_id:
                return 1
            # Eğer 'cikis_depo_id' doluysa, bu depo için Çıkış (-1) demektir.
            elif self.cikis_depo_id:
                return -1
        
        return 0

    @property
    def etiket(self):
        """Ekranda görünecek Türkçe isim"""
        return {
            'devir': 'Devir',
            'transfer': 'Transfer',
            'alis': 'Alış Faturası',
            'satis': 'Satış Faturası',
            'alis_iade': 'Alış İade',
            'satis_iade': 'Satış İade',
            'uretim': 'Üretim Giriş',
            'uretim_cikis': 'Üretim Çıkış',
            'sarf': 'Sarf',
            'fire': 'Fire',
            'sayim_fazla': 'Sayım Fazlası',
            'sayim_eksik': 'Sayım Eksiği'
        }.get(self.hareket_turu, self.hareket_turu.upper())

class StokFisiDetay(db.Model):
    __tablename__ = 'stok_fis_detaylari'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    fis_id = db.Column(db.String(36), db.ForeignKey('stok_fisleri.id'))
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'))
    miktar = db.Column(Numeric(18, 4),default=Decimal('0.0000'))
    aciklama = db.Column(db.String(100))
    stok = db.relationship('StokKart')


