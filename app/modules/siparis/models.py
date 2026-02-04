# modules/siparis/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import ParaBirimi, SiparisDurumu, StokBirimleri
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Siparis(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'siparisler'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    # Organizasyonel Yapı
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'))
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'))
    depo_id = db.Column(db.String(36), db.ForeignKey('depolar.id'), nullable=False)
    
    # İlişkiler (ID'ler)
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=False)
    plasiyer_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))
    
    # Finansal Detaylar
    fiyat_listesi_id = db.Column(db.String(36), db.ForeignKey('fiyat_listeleri.id'))
    odeme_plani_id = db.Column(db.String(36), db.ForeignKey('odeme_planlari.id'))
    
    # Belge Bilgileri
    belge_no = db.Column(db.String(50), nullable=False)
    tarih = db.Column(db.Date, default=datetime.now, nullable=False)
    teslim_tarihi = db.Column(db.Date)
    sevk_adresi = db.Column(db.String(255))
    
    # Durum ve Onay
    durum = db.Column(db.String(20), default=SiparisDurumu.BEKLIYOR.value)
    onaylayan_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))
    onay_tarihi = db.Column(db.DateTime)

    aciklama = db.Column(db.String(255))
    
    # Para Birimi
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL, nullable=False)
    doviz_kuru = db.Column(Numeric(10, 4), default=Decimal('1.0000'))
    
    # Toplamlar
    ara_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    iskonto_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    kdv_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    genel_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    dovizli_toplam = db.Column(Numeric(18, 2), default=Decimal('0.00'))

    # AI ve Analiz Alanları
    kayip_nedeni = db.Column(db.String(255))
    tahmini_karlilik = db.Column(Numeric(18, 2))
    oncelik_skoru = db.Column(db.Integer, default=50)

    # ORM İlişkileri (Tek sefer tanımlandı)
    detaylar = db.relationship('SiparisDetay', backref='siparis', cascade="all, delete-orphan")
    cari = db.relationship('CariHesap', back_populates='siparisler')
    depo = db.relationship('Depo', backref='depo_siparisleri') 

    __table_args__ = (UniqueConstraint('firma_id', 'belge_no', name='uq_siparis_no'),)

    def guncelle_karlilik(self):
        """
        [ONAYLANDI] Siparişin karlılığını hesaplar (Döviz Kuru Destekli).
        Formül: Toplam Satış (TL) - Toplam Maliyet (TL)
        """
        try:
            toplam_satis_tl = Decimal('0.00')
            toplam_maliyet_tl = Decimal('0.00')
            
            kur = Decimal(str(self.doviz_kuru)) if self.doviz_kuru and self.doviz_kuru > 0 else Decimal('1.0')

            for detay in self.detaylar:
                # 1.SATIŞ (CİRO) - TL'ye çevir
                net_tutar = Decimal(str(detay.net_tutar or 0))
                toplam_satis_tl += (net_tutar * kur)

                # 2.MALİYET (Stok kartından TL olarak al)
                if detay.stok:
                    miktar = Decimal(str(detay.miktar or 0))
                    # Stok kartındaki alış fiyatını al (Yoksa 0)
                    birim_maliyet = Decimal(str(detay.stok.alis_fiyati or 0))
                    toplam_maliyet_tl += (miktar * birim_maliyet)

            self.tahmini_karlilik = toplam_satis_tl - toplam_maliyet_tl
            return self.tahmini_karlilik

        except Exception as e:
            print(f"Karlılık Hesaplama Hatası: {e}")
            return Decimal('0.00')

    def skor_hesapla(self):
        """
        [ONAYLANDI] Siparişin önem derecesini (0-100) hesaplar.
        """
        try:
            skor = 50 # Başlangıç Puanı
            
            # 1.Tutar Etkisi
            toplam = float(self.genel_toplam or 0)
            if toplam > 100000: skor += 20
            elif toplam > 50000: skor += 10
            
            # 2.Cari Risk Durumu
            if self.cari and self.cari.risk_durumu == 'RISKLI':
                skor -= 30
            elif self.cari and self.cari.risk_durumu == 'GUVENLI':
                skor += 10
                
            self.oncelik_skoru = max(0, min(100, skor))
            return self.oncelik_skoru
        except:
            return 50

class SiparisDetay(db.Model):
    __tablename__ = 'siparis_detaylari'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    siparis_id = db.Column(db.String(36), db.ForeignKey('siparisler.id'), nullable=False)
    stok_id = db.Column(db.String(36), db.ForeignKey('stok_kartlari.id'), nullable=False)
    
    # Miktar Yönetimi
    miktar = db.Column(Numeric(18, 4), default=Decimal('0.0000'))
    teslim_edilen_miktar = db.Column(Numeric(18, 4), default=Decimal('0.0000')) # İrsaliyeleşen
    faturalanan_miktar = db.Column(Numeric(18, 4), default=Decimal('0.0000'))   # DÜZELTİLDİ: Faturalaşan
    iptal_edilen_miktar = db.Column(Numeric(18, 4), default=Decimal('0.0000'))
    
    birim = db.Column(db.Enum(StokBirimleri), default=StokBirimleri.ADET)
    
    # Fiyatlandırma
    birim_fiyat = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    iskonto_orani = db.Column(Numeric(5, 2), default=Decimal('0.00'))
    kdv_orani = db.Column(Numeric(5, 2), default=Decimal('20.00'))
    
    # Tutarlar
    iskonto_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    kdv_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    net_tutar = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    satir_toplami = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    aciklama = db.Column(db.String(255))
    
    stok = db.relationship('StokKart', backref='siparis_kalemleri')

    @property
    def bekleyen_miktar(self):
        """Hala gönderilmeyi bekleyen miktar"""
        return self.miktar - self.teslim_edilen_miktar - self.iptal_edilen_miktar

class OdemePlani(db.Model):
    __tablename__ = 'odeme_planlari'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    ad = db.Column(db.String(100), nullable=False)
    gun_vadesi = db.Column(db.Integer, default=0)
    aktif = db.Column(db.Boolean, default=True)