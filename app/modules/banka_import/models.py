# app/modules/banka_import/models.py

from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from app.modules.firmalar.models import Firma
from app.modules.cari.models import CariHesap
from app.modules.kullanici.models import Kullanici
from app.modules.muhasebe.models import HesapPlani
from datetime import datetime

# --- ENUM TANIMLARI (Sadece bu modülü ilgilendirenler burada kalabilir) ---
# Eğer genel kullanılacaksa app/enums.py'ye taşınabilir.
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class BankaImportSablon(db.Model):
    __tablename__ = 'banka_import_sablonlari'
    __table_args__ = {'extend_existing': True} # Tekrar yüklemelerde hata almamak için

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    
    banka_adi = db.Column(db.String(50)) 
    baslangic_satiri = db.Column(db.Integer, default=2) 
    
    # Sütun Eşleştirmeleri (Excel'deki sütun başlıkları veya indeksleri)
    col_tarih = db.Column(db.String(50))    
    col_aciklama = db.Column(db.String(50)) 
    col_belge_no = db.Column(db.String(50)) 
    
    # Tutar Yapısı: 'tek' (Giriş/Çıkış +/- ile), 'cift' (Borç/Alacak ayrı sütun)
    tutar_yapis_tipi = db.Column(db.String(10), default='tek') 
    
    col_tutar = db.Column(db.String(50))        
    col_borc = db.Column(db.String(50))         
    col_alacak = db.Column(db.String(50))       
    
    tarih_formati = db.Column(db.String(20), default='%d.%m.%Y')

class BankaImportKurali(db.Model):
    __tablename__ = 'banka_import_kurallari'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    
    anahtar_kelime = db.Column(db.String(100), nullable=False) # Örn: "GEDIZ", "POS"
    
    # Kural Tipi: 'standart', 'pos_net' (Komisyonlu)
    kural_tipi = db.Column(db.String(20), default='standart') 
    
    # Hedef
    hedef_turu = db.Column(db.String(20)) # 'cari', 'muhasebe', 'banka', 'kasa'
    hedef_cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=True)
    hedef_muhasebe_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)
    
    # POS Ayarları
    varsayilan_komisyon_orani = db.Column(db.Numeric(5, 2), default=0.00)
    komisyon_gider_hesap_id = db.Column(db.String(36), db.ForeignKey('hesap_plani.id'), nullable=True)
    
    aciklama_sablonu = db.Column(db.String(255)) 

    # İlişkiler
    hedef_cari = db.relationship('CariHesap', foreign_keys=[hedef_cari_id])
    hedef_muhasebe = db.relationship('HesapPlani', foreign_keys=[hedef_muhasebe_id])
    komisyon_hesabi = db.relationship('HesapPlani', foreign_keys=[komisyon_gider_hesap_id])

class BankaImportGecmisi(db.Model):
    __tablename__ = 'banka_import_gecmisi'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    banka_id = db.Column(db.String(36), db.ForeignKey('banka_hesaplari.id'))
    
    dosya_adi = db.Column(db.String(255))
    dosya_hash = db.Column(db.String(64), index=True) # Mükerrer kontrolü için
    yukleme_tarihi = db.Column(db.DateTime, default=datetime.now)
    satir_sayisi = db.Column(db.Integer)
    kullanici_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'))