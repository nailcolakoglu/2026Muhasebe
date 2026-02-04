# app/modules/cek/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from sqlalchemy import or_ # or_ importu eklendi
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.enums import PortfoyTipi, VadeGrubu, ParaBirimi, CekDurumu, RiskSeviyesi, CekSonucDurumu
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class CekSenet(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'cek_senetler'
    query_class = FirmaFilteredQuery

    # ======================
    # 1.TEMEL KİMLİK ve BELGE
    # ======================
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    
    # Belge No
    belge_no = db.Column(db.String(50), nullable=False, comment='Sistem Takip No (Portföy No)')
    seri_no = db.Column(db.String(50), nullable=True, comment='Şirket İçi Seri No')
    
    # Türler
    portfoy_tipi = db.Column(db.Enum(PortfoyTipi), default=PortfoyTipi.ALINAN, index=True) 
    tur = db.Column(db.String(10), default='cek') 
    
    # ======================
    # 2.İLİŞKİLER
    # ======================
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True, index=True)
    
    # 👇 DÜZELTİLEN SATIR BURASI (finans_islemleri -> finans_islemler) 👇
    finans_islem_id = db.Column(db.String(36), db.ForeignKey('finans_islemleri.id'), nullable=True)
    
    # ======================
    # 3.ZAMAN ve VADE
    # ======================
    duzenleme_tarihi = db.Column(db.Date, default=datetime.now)
    vade_tarihi = db.Column(db.Date, nullable=False, index=True)
    tahsil_tarihi = db.Column(db.Date, index=True)
    
    kalan_gun = db.Column(db.Integer) 
    vade_grubu = db.Column(db.Enum(VadeGrubu), default=VadeGrubu.GECIKMIS)

    # ======================
    # 4.FİNANSAL BİLGİLER
    # ======================
    tutar = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    doviz_turu = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL)
    kur = db.Column(Numeric(15, 4), default=Decimal('1.0000'))
    
    iskonto_orani = db.Column(Numeric(5, 2), default=Decimal('0.00'))
    net_tahsilat_tutari = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    banka_komisyonu = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    protesto_masrafi = db.Column(Numeric(18, 2), default=Decimal('0.00'))

    # ======================
    # 5.BANKA ve ÇEK DETAYLARI
    # ======================
    banka_adi = db.Column(db.String(100))
    sube_adi = db.Column(db.String(100))
    hesap_no = db.Column(db.String(50))
    iban = db.Column(db.String(34))
    cek_no = db.Column(db.String(50), nullable=True, comment='Fiziksel Çek/Senet No')
    cek_durumu = db.Column(db.Enum(CekDurumu), default=CekDurumu.PORTFOYDE)

    # ======================
    # 6.TARAFLAR
    # ======================
    kesideci_unvan = db.Column(db.String(200))
    kesideci_tc_vkn = db.Column(db.String(20)) 
    kefil = db.Column(db.String(100)) 
    ciranta_adi = db.Column(db.String(200)) 
    ciranta_sayisi = db.Column(db.Integer, default=0)

    # ======================
    # 7.AI TAHMİN ve RİSK
    # ======================
    risk_seviyesi = db.Column(db.Enum(RiskSeviyesi), default=RiskSeviyesi.ORTA)
    risk_puani = db.Column(db.Integer, default=50)
    
    tahsilat_tahmini_tarihi = db.Column(db.Date)
    tahsilat_olasiligi = db.Column(Numeric(5, 3), default=Decimal('0.000'))
    ai_onerisi = db.Column(db.Text)
    
    gecikme_gunu = db.Column(db.Integer, default=0)
    sonuc_durumu = db.Column(db.Enum(CekSonucDurumu), default=CekSonucDurumu.BEKLIYOR)

    # ======================
    # 8.DİĞER
    # ======================
    resim_on_path = db.Column(db.String(255))
    resim_arka_path = db.Column(db.String(255))
    ocr_ham_veri = db.Column(db.Text)
    fiziksel_yeri = db.Column(db.String(100))

    aciklama = db.Column(db.String(255))
    aktif = db.Column(db.Boolean, default=True)
    olusturma_tarihi = db.Column(db.DateTime, server_default=func.now())

    ai_guven_skoru = db.Column(db.Integer, default=50)
    ocr_dogruluk_orani = db.Column(Numeric(5, 2))
    sektor_etiketi = db.Column(db.String(50))

    # İlişkiler
    cari = db.relationship('CariHesap', back_populates='cekler')
    # FinansIslem ilişkisi FinansIslem modelindeki backref='cek_senetler' ile sağlanır.

    __table_args__ = (
        UniqueConstraint('firma_id', 'belge_no', 'portfoy_tipi', name='uq_cek_belge_no'),
        Index('ix_vade_analizi', 'vade_tarihi', 'cek_durumu', 'risk_seviyesi'),
    )
    
    def risk_analizi_yap(self):
        """Risk Hesaplama Motoru"""
        from datetime import datetime, timedelta
        
        skor = 50

        # 1.Cari Risk Skoru Etkisi
        if self.cari and hasattr(self.cari, 'risk_skoru') and self.cari.risk_skoru:
            skor += (self.cari.risk_skoru - 50) 

        # 2.Keşideci Geçmişi
        if self.kesideci_tc_vkn:
            sorunlu_cek_sayisi = db.session.query(func.count(CekSenet.id)).filter(
                CekSenet.kesideci_tc_vkn == self.kesideci_tc_vkn,
                or_(
                    CekSenet.cek_durumu == CekDurumu.KARSILIKSIZ,
                    CekSenet.sonuc_durumu == CekSonucDurumu.KARSILIKSIZ
                )
            ).scalar()

            if sorunlu_cek_sayisi > 0:
                skor -= 40
                self.ai_onerisi = f"DİKKAT: Keşidecinin {sorunlu_cek_sayisi} adet karşılıksız çeki var!"

        # 3.Skoru Sıkıştır ve Ata
        self.risk_puani = max(0, min(100, skor))

        if self.risk_puani < 30:
            self.risk_seviyesi = RiskSeviyesi.YUKSEK
        elif self.risk_puani < 70:
            self.risk_seviyesi = RiskSeviyesi.ORTA
        else:
            self.risk_seviyesi = RiskSeviyesi.DUSUK

        # 4.Tahmini Tarih
        gecikme = self.cari.ortalama_odeme_gunu if self.cari and hasattr(self.cari, 'ortalama_odeme_gunu') else 0
        if self.vade_tarihi:
            self.tahsilat_tahmini_tarihi = self.vade_tarihi + timedelta(days=gecikme)