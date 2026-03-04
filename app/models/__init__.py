# app/models/__init__.py

"""
Merkezi Model Import Noktası

Tüm modeller buradan import edilir.
Circular import riskini ortadan kaldırır.

Kullanım:
    from models import db, Firma, CariHesap, Fatura
"""

import sys
import os
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

# Import fix
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.extensions import db

# 🚨 Sadece Master modellerini dışarı ver, diğerlerini yorum satırı yap!
from app.models.master.user import User, UserTenantRole
from app.models.master.tenant import Tenant
from app.models.master.license import License
from app.models.master.audit import AuditLog  

# ========================================
# 1.TEMEL SINIFLAR
# ========================================
from app.models.base import (
    #db, 
    FirmaFilteredQuery,     
    TimestampMixin, 
    SoftDeleteMixin,
    FirmaOwnedMixin,
    #ensure_firebird_database, 
    JSONText, 
    PaginationResult, 
    ROLES_PERMISSIONS
)

# ========================================
# 2.ENUM'LAR
# ========================================
from enums import (
    FaturaTuru, StokFisTuru, HareketTuru, 
    IslemDurumu, FinansIslemTuru, BankaIslemTuru,
    SiparisDurumu, CekDurumu, ParaBirimi,
    HesapSinifi, BakiyeTuru, OzelHesapTipi
)

# Form Builder
# from app.form_builder.models import MenuItem
    
# ========================================
# 4.YARDIMCI MODELLER (Modül dışı)
# ========================================

class Sayac(db.Model):
    __tablename__ = 'sayaclar'
    __table_args__ = (
        db.UniqueConstraint('firma_id', 'donem_yili', 'kod', name='uq_sayac_tanimi'),
        {'extend_existing': True}  
    )
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    donem_yili = db.Column(db.Integer, default=2025)
    kod = db.Column(db.String(50), nullable=False)
    on_ek = db.Column(db.String(10), default='')
    son_no = db.Column(db.Integer, default=0)
    hane_sayisi = db.Column(db.Integer, default=6)
    
    def sonraki_numara_str(self):
        yeni = self.son_no + 1
        return f"{self.on_ek}{str(yeni).zfill(self.hane_sayisi)}"

class Hedef(db.Model):
    __tablename__ = 'hedefler'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'))
    donem_id = db.Column(db.String(36), db.ForeignKey('donemler.id'))
    plasiyer_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=True)
    
    hedef_ayi = db.Column(db.Integer)
    hedef_ciro = db.Column(db.Numeric(18, 2), default=0)
    hedef_tahsilat = db.Column(db.Numeric(18, 2), default=0)
    hedef_yeni_musteri = db.Column(db.Integer, default=0)
    
    plasiyer = db.relationship('Kullanici', lazy='select')
    sube = db.relationship('Sube', lazy='select')

class WorkflowDefinition(db.Model):
    #İş Akışı Tanımları
    __tablename__ = 'workflow_definitions'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), unique=True)
    json_definition = db.Column(db.Text)
    trigger_form = db.Column(db.String(50))


class WorkflowInstance(db.Model):
    #İş Akışı Örnekleri
    __tablename__ = 'workflow_instances'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    definition_id = db.Column(db.String(36), db.ForeignKey('workflow_definitions.id'))
    current_step = db.Column(db.String(50))
    status = db.Column(db.String(20))
    context_data = db.Column(db.Text)
    record_id = db.Column(db.String(36))


# ========================================
# 3.MODÜLER MODEL İMPORTLARI
# ========================================

# Lokasyon
from app.modules.lokasyon.models import Sehir, Ilce

# Firma ve Dönem
from app.modules.firmalar.models import Firma, Donem, SystemMenu 

# Bölge
from app.modules.bolge.models import Bolge

# Kullanıcı
from app.modules.kullanici.models import Kullanici

# Şube
from app.modules.sube.models import Sube

# Muhasebe
from app.modules.muhasebe.models import HesapPlani, MuhasebeFisi, MuhasebeFisiDetay

# Kasa
from app.modules.kasa.models import Kasa

# Banka
from app.modules.banka.models import BankaHesap

# Cari
from app.modules.cari.models import CariHesap, CariHareket, CRMHareket

# Depo
from app.modules.depo.models import Depo

# Kategori
from app.modules.kategori.models import StokKategori

# Stok
from app.modules.stok.models import (
    StokKart, StokHareketi, StokPaketIcerigi,
    StokMuhasebeGrubu, StokKDVGrubu, StokDepoDurumu
)

# Fiyat
from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay

# İrsaliye
from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi

# Fatura
from app.modules.fatura.models import Fatura, FaturaKalemi

# E-Fatura
from app.modules.efatura.models import EntegratorAyarlari

# Stok Fişi
from app.modules.stok_fisi.models import StokFisi, StokFisiDetay

# Kasa Hareket
from app.modules.kasa_hareket.models import KasaHareket

# Banka Hareket
from app.modules.banka_hareket.models import BankaHareket

# Finans
from app.modules.finans.models import FinansIslem

# Çek
from app.modules.cek.models import CekSenet

# Sipariş
from app.modules.siparis.models import Siparis, SiparisDetay, OdemePlani

# Döviz
from app.modules.doviz.models import DovizKuru

# Banka Import
from app.modules.banka_import.models import (
    BankaImportSablon, BankaImportKurali, BankaImportGecmisi
)

# Rapor
from app.modules.rapor.models import YazdirmaSablonu, AIRaporAyarlari, AIRaporGecmisi

# CRM
from app.modules.crm.models import AdayMusteri, SatisAsamasi, SatisFirsati, CrmAktivite, CrmHareketi, CrmFirsatLogu

# B2B Portalı
from app.modules.b2b.models import B2BAyar, B2BKullanici

# ========================================
# 5.EXPORT LİSTESİ
# ========================================
__all__ = [
    # Base
    'db', 'FirmaFilteredQuery', 'ensure_firebird_database',
    'TimestampMixin', 'SoftDeleteMixin', 'FirmaOwnedMixin',
    'JSONText', 'PaginationResult',
    'ROLES_PERMISSIONS',

    # Lokasyon
    'Sehir', 'Ilce',
    
    # Firma
    'Firma', 'Donem', 
    
    # Organizasyon
    'Bolge', 'Sube', 'Kullanici',
    
    # Muhasebe
    'HesapPlani', 'MuhasebeFisi', 'MuhasebeFisiDetay',
    
    # Finans
    'Kasa', 'BankaHesap', 'KasaHareket', 'BankaHareket',
    'FinansIslem', 'CekSenet',
    
    # Cari
    'CariHesap', 'CariHareket', 'CRMHareket', 
    
    # Stok
    'Depo', 'StokKategori', 'StokKart', 'StokHareketi',
    'StokPaketIcerigi', 'StokMuhasebeGrubu', 'StokKDVGrubu',
    'StokDepoDurumu', 'StokFisiDetay', 'StokFisi',
    
    # Fiyat
    'FiyatListesi', 'FiyatListesiDetay',
    
    # İrsaliye
    'Irsaliye', 'IrsaliyeKalemi',
    
    # Fatura
    'Fatura', 'FaturaKalemi',
    
    # E-Fatura
    'EntegratorAyarlari',
    
    # Sipariş
    'Siparis', 'SiparisDetay', 'OdemePlani',
    
    # Döviz
    'DovizKuru',
    
    # Banka Import
    'BankaImportSablon', 'BankaImportKurali', 'BankaImportGecmisi',
    
    # 
    'YazdirmaSablonu', 'AIRaporAyarlari', 'AIRaporGecmisi',
    
    # Form BuilderRapor
    # 'MenuItem',
    
    # Diğer
    'Sayac', 'Hedef',
    'AIRaporAyarlari', 'AIRaporGecmisi',
    'WorkflowDefinition', 'WorkflowInstance',

    # CRM Modelleri
    'AdayMusteri', 'SatisAsamasi', 'SatisFirsati', 'CrmAktivite', 'CrmHareketi', 'CrmFirsatLogu',
    
    # B2B Modelleri
    'B2BAyar', 'B2BKullanici',

]  


# ========================================
# 6.EVENT LISTENERS
# ========================================
def init_events():
    #Event listener'ları başlat
    try:
        from .events import setup_event_listeners
        setup_event_listeners()
    except ImportError as e:
        import logging
        logging.warning(f"Event listeners yüklenemedi: {e}")


