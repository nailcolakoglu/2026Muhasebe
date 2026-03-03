# app/modules/b2b/models.py

import uuid
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
from sqlalchemy import Numeric
from werkzeug.security import generate_password_hash, check_password_hash

def generate_uuid():
    return str(uuid.uuid4())

# =======================================================
# 1. B2B PORTAL AYARLARI (Tenant Bazlı)
# =======================================================
class B2BAyar(db.Model, TimestampMixin):
    """
    Her firmanın (Tenant) kendi bayi portalı ayarlarını tuttuğu tablo.
    """
    __tablename__ = 'b2b_ayarlar'
    query_class = FirmaFilteredQuery

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    
    # Portal Açık/Kapalı
    aktif_mi = db.Column(db.Boolean, default=False)
    
    # Görünüm
    portal_baslik = db.Column(db.String(100), default="B2B Bayi Portalı")
    portal_logo_path = db.Column(db.String(255), nullable=True)
    karsilama_metni = db.Column(db.Text, nullable=True)
    
    # İş Kuralları
    minimum_siparis_tutari = db.Column(Numeric(18, 2), default=0.00)
    # Bayiler sipariş verdiğinde doğrudan onaylansın mı, yoksa "Beklemede" mi kalsın?
    oto_siparis_onayi = db.Column(db.Boolean, default=False) 
    
    # B2B'de ürünler gösterilirken hangi fiyat listesi baz alınacak?
    varsayilan_fiyat_listesi_id = db.Column(db.String(36), db.ForeignKey('fiyat_listeleri.id'), nullable=True)

    # İlişkiler
    fiyat_listesi = db.relationship('FiyatListesi')


# =======================================================
# 2. B2B KULLANICILARI (Bayiler / Müşteriler)
# =======================================================
class B2BKullanici(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    ERP Kullanıcılarından bağımsız, portala giriş yapacak Müşteri/Bayi hesapları.
    Mutlaka bir Cari Hesap kartına bağlı olmak zorundadır.
    """
    __tablename__ = 'b2b_kullanicilar'
    query_class = FirmaFilteredQuery

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)
    
    # Hangi Cari'nin personeli/sahibi?
    cari_id = db.Column(db.String(36), db.ForeignKey('cari_hesaplar.id'), nullable=False, index=True)
    
    ad_soyad = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telefon = db.Column(db.String(20))
    sifre_hash = db.Column(db.String(255), nullable=False)
    
    aktif = db.Column(db.Boolean, default=True)
    son_giris_tarihi = db.Column(db.DateTime)
    
    # Alt Yetkilendirmeler (Bayinin personeli sadece sipariş versin ama ekstreyi görmesin vb.)
    yetki_siparis_ver = db.Column(db.Boolean, default=True)
    yetki_ekstre_gor = db.Column(db.Boolean, default=True)
    yetki_kredi_karti_odeme = db.Column(db.Boolean, default=False)

    # İlişkiler
    cari = db.relationship('CariHesap', backref=db.backref('b2b_kullanicilari', lazy='dynamic'))

    def sifre_belirle(self, password):
        self.sifre_hash = generate_password_hash(password)

    def sifre_kontrol(self, password):
        return check_password_hash(self.sifre_hash, password)

    # Flask-Login uyumluluğu için özellikler (Fakat farklı bir session kurgulayacağız)
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.aktif

    @property
    def is_anonymous(self):
        return False

    @property
    def gorunum_cari(self):
        """DataGrid'de cari unvanını göstermek için"""
        return self.cari.unvan if self.cari else '-'

    def get_id(self):
        return str(self.id)
        