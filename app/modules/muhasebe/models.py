# modules/muhasebe/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.extensions import db
from app.enums import HesapSinifi, BakiyeTuru, OzelHesapTipi, ParaBirimi, MuhasebeFisTuru
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class HesapPlani(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'hesap_plani'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    # Hiyerarşi
    ust_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)
    
    # Kimlik
    kod = db.Column(db.String(50), nullable=False) # 100.01.001
    ad = db.Column(db.String(200), nullable=False) # Merkez Kasa
    
    # --- YENİ EKLENEN PROFESYONEL ALANLAR ---
    
    # 1.Seviye Kontrolü (Mizan Hızı İçin)
    # 100 -> Seviye 1, 100.01 -> Seviye 2, 100.01.001 -> Seviye 3
    seviye = db.Column(db.Integer, default=1) 
    
    # 2.Hesap Sınıfı (Önemli!)
    # Sadece 'muavin' olanlara fiş kesilebilir.Ana hesaplara fiş kesilemez.
    hesap_tipi = db.Column(db.Enum(HesapSinifi), default=HesapSinifi.MUAVIN_HESAP)
    
    # 3.Bakiye Karakteri (Hata Önleme İçin)
    # Kasa hesabı Alacak verirse sistem uyarı verir.
    bakiye_turu = db.Column(db.Enum(BakiyeTuru), default=BakiyeTuru.HER_IKISI)
    
    # 4.Entegrasyon Zekası
    # Bu hesap bir KDV hesabı mı? Kasa mı? Bunu bilirsek otomatik fiş kesebiliriz.
    ozel_hesap_tipi = db.Column(db.Enum(OzelHesapTipi), default=OzelHesapTipi.STANDART)
    
    # 5.Döviz Takibi
    calisma_dovizi = db.Column(db.Enum(ParaBirimi), default=ParaBirimi.TL) # Sadece USD çalışan hesaplar için
    
    # --- BAKİYELER ---
    # Bu alanlar trigger veya periyodik işlemle güncellenir
    borc_bakiye = db.Column(Numeric(15, 2), default=0.0)
    alacak_bakiye = db.Column(Numeric(15, 2), default=0.0)
    
    aktif = db.Column(db.Boolean, default=True)
    aciklama = db.Column(db.String(255))

    __table_args__ = (UniqueConstraint('firma_id', 'kod', name='uq_hesap_kod'),)
    
    # İlişkiler
    ust_hesap = db.relationship('HesapPlani', remote_side=[id], backref='alt_hesaplar')
    
    @property
    def bakiye(self):
        """Net Bakiye: Borç - Alacak"""
        return self.borc_bakiye - self.alacak_bakiye

    @property
    def tam_ad(self):
        """Dropdownlarda görünmesi için: 100.01 - Merkez Kasa"""
        return f"{self.kod} - {self.ad}"

    def hareket_gorebilir_mi(self):
        """Sadece Muavin hesaplara kayıt atılabilir"""
        return self.hesap_tipi == HesapSinifi.MUAVIN_HESAP

class MuhasebeFisi(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'muhasebe_fisleri'
    query_class = FirmaFilteredQuery # 1.Güvenlik eklendi
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'), nullable=False)
    
    # 2.Şube Eklendi (Kritik)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=False) 
    
    fis_turu = db.Column(db.Enum(MuhasebeFisTuru), default=MuhasebeFisTuru.MAHSUP, nullable=False)
    fis_no = db.Column(db.String(50), nullable=False) # Yevmiye No
    tarih = db.Column(db.Date, nullable=False)
    aciklama = db.Column(db.String(255))
    toplam_borc = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    toplam_alacak = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    
    # Kaynak Belge Referansı
    kaynak_modul = db.Column(db.String(50)) # 'fatura', 'kasa', 'banka'
    kaynak_id = db.Column(db.String(36))       

    # Resmi Yevmiye Madde Numarası (Geçici fis_no'dan farklıdır, değiştirilemez)
    yevmiye_madde_no = db.Column(db.Integer, nullable=True, index=True)
    
    # Bu fiş resmi deftere basıldı mı? (Basıldıysa değiştirilemez/silinemez)
    resmi_defter_basildi = db.Column(db.Boolean, default=False)

    detaylar = db.relationship('MuhasebeFisiDetay', backref='fis', cascade="all, delete-orphan")

    # --- E-DEFTER DURUM TAKİBİ ---    
    # Bu fiş hangi e-defter parçasına dahil oldu?
    # Örn: 202501 (2025 Ocak) dönemine ait berat oluşturuldu mu?
    e_defter_donemi = db.Column(db.String(6)) # '202501'
    
    # GİB Durum Kodları
    # 0: Gönderilmedi, 1: Kuyrukta, 2: Onaylandı, 3: Hatalı
    gib_durum_kodu = db.Column(db.Integer, default=0) 
    gib_hata_mesaji = db.Column(db.String(255))
    
    # Kayıt Zaman Damgaları (e-Defter "Zaman Damgası" ister)
    # Oluşturma ve Son Düzenleme saatleri milisaniye hassasiyetinde olabilir
    sistem_kayit_tarihi = db.Column(db.DateTime, default=datetime.now)
    son_duzenleme_tarihi = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Kaydeden Kullanıcı (Audit Log için)
    kaydeden_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))
    duzenleyen_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))

    # 3.Benzersizlik Kuralı: Bir dönemde, aynı türde, aynı numara tekrar edemez.
    __table_args__ = (
        UniqueConstraint('firma_id', 'donem_id', 'fis_turu', 'fis_no', name='uq_muh_fis_no'),
    )

class MuhasebeFisiDetay(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'muhasebe_fis_detaylari'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    fis_id = db.Column(db.String(36), db.ForeignKey('muhasebe_fisleri.id'), nullable=False)
    hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=False)
    
    aciklama = db.Column(db.String(255))
    borc = db.Column(Numeric(18, 2), default=Decimal('0.00'))
    alacak = db.Column(Numeric(18, 2), default=Decimal('0.00'))

    # --- E-DEFTER BELGE DETAYLARI (DocumentType) ---
    # Bu alanlar boş olabilir (Her satırda belge olmaz) ama varsa GİB ister.
    
    # Belge Türü (Fatura, Çek, Senet, Makbuz, Diğer)
    # Enum kullanmak en iyisidir ama string de tutulabilir.
    # Örn: 'invoice', 'receipt', 'check', 'other'
    belge_turu = db.Column(db.String(50)) 
    
    # Belge Tarihi ve Numarası (Faturanın tarihi ve seri/sıra nosu)
    belge_tarihi = db.Column(db.Date)
    belge_no = db.Column(db.String(50))
    
    # Ödeme Yöntemi (PaymentMethod)
    # Sadece Ana Hesaplar (Kasa, Banka) çalıştığında doldurulması tavsiye edilir.
    # 'KASA', 'BANKA', 'CEK', 'SENET', 'KREDI_KARTI'
    odeme_yontemi = db.Column(db.String(50))
    
    # GİB İçin Ek Açıklama (Bazen satır açıklaması yetmez, belge açıklaması gerekir)
    belge_aciklamasi = db.Column(db.String(255))

    hesap = db.relationship('HesapPlani')

