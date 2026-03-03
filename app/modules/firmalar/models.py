# app/modules/firmalar/models.py
"""
Firma ve Dönem Modelleri (UUID VERSİYON)
"""
from datetime import datetime
from sqlalchemy import Integer, String, Boolean, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin, JSONText
from markupsafe import Markup

# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

# --- 1. FIRMA SINIFI ---
class Firma(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'firmalar'
    
    # ID artık Integer değil, String(36) ve varsayılan olarak UUID üretiyor
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    
    kod = db.Column(db.String(20), nullable=False, unique=True, default='01')    
    unvan = db.Column(db.String(100), nullable=False)
    
    tenant_db_name = db.Column(db.String(64), unique=True)  # erp_firma_001
    
    # İletişim & Vergi
    vergi_dairesi = db.Column(db.String(50))
    vergi_no = db.Column(db.String(20))
    adres = db.Column(db.String(255))
    konum = db.Column(db.String(50), nullable=True)
    telefon = db.Column(db.String(20))
    email = db.Column(db.String(100))
    logo_path = db.Column(db.String(255))
    
    # Meta
    olusturma_tarihi = db.Column(db.DateTime, server_default=func.now())
    aktif = db.Column(db.Boolean, default=True)
    
    # --- E-DEFTER ---
    ticaret_sicil_no = db.Column(db.String(50))
    mersis_no = db.Column(db.String(50))
    nace_kodu = db.Column(db.String(20)) 
    e_defter_baslangic = db.Column(db.Date)
    
    # --- MALİ MÜŞAVİR ---
    sm_unvan = db.Column(db.String(100))
    sm_tc_vkn = db.Column(db.String(20))
    sm_sozlesme_no = db.Column(db.String(50))
    sm_sozlesme_tarihi = db.Column(db.Date)
    sm_telefon = db.Column(db.String(20))
    sm_email = db.Column(db.String(100))    
    
    # İlişkiler
    kullanicilar = db.relationship('Kullanici', back_populates='firma', lazy=True, overlaps="db_kullanicilari")
    donemler = db.relationship('Donem', back_populates='firma', lazy=True) 
    subeler = db.relationship('Sube', back_populates='firma', lazy=True)

    def __repr__(self):
        return f"<Firma {self.kod} - {self.unvan}>"

# --- 2. DONEM SINIFI ---
class Donem(db.Model, TimestampMixin):
    __tablename__ = 'donemler'
    query_class = FirmaFilteredQuery
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid) # Dönem ID'si Integer kalabilir veya istersen UUID yapabilirsin.
    
    # FOREIGN KEY GÜNCELLEMESİ: Integer -> String(36)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    yil = db.Column(db.Integer, nullable=False)
    ad = db.Column(db.String(50), nullable=False)
    
    baslangic = db.Column(db.Date)
    bitis = db.Column(db.Date)
    aktif = db.Column(db.Boolean, default=False)

    son_yevmiye_tarihi = db.Column(db.Date, nullable=True)
    son_madde_no = db.Column(db.Integer, default=0)    
    
    firma = db.relationship('Firma', back_populates='donemler')

    def __repr__(self):
        return f"<Donem {self.ad}>"

class SystemMenu(db.Model):
    __tablename__ = 'menu_items'
    __table_args__ = {'extend_existing': True}
    __mapper_args__ = {
        'confirm_deleted_rows': False
    }
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    parent_id = db.Column(db.String(36), db.ForeignKey('menu_items.id'), nullable=True)
    
    baslik = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50)) # bi bi-house
    
    # Yönlendirme: Ya endpoint (url_for) ya da statik URL
    endpoint = db.Column(db.String(100)) # 'stok.index'
    url = db.Column(db.String(255)) # '/ozel-link'
    
    yetkili_roller = db.Column(db.String(255)) # "admin,muhasebe" (Virgülle ayrılmış)
    sira = db.Column(db.Integer, default=0)
    aktif = db.Column(db.Boolean, default=True)
    
    # Hiyerarşi İlişkisi
    children = db.relationship('SystemMenu', 
                             backref=db.backref('parent', remote_side=[id]),
                             lazy='dynamic',
                             cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SystemMenu {self.baslik}>"

    @property
    def gorunum_baslik(self):
        """DataGrid için İkonlu Başlık Döndürür"""
        icon_html = f'<i class="{self.icon} me-2 text-primary"></i>' if self.icon else ''
        return Markup(f'{icon_html} {self.baslik}')
        
    @property
    def gorunum_ust_menu(self):
        """Üst Menü varsa adını, yoksa tire döndürür"""
        return self.parent.baslik if self.parent else "-"
        
    @property
    def gorunum_hedef(self):
        """Endpoint veya URL hangisi doluysa onu gösterir"""
        if self.endpoint:
            return Markup(f'<span class="badge bg-light text-dark border">Rota: {self.endpoint}</span>')
        return Markup(f'<span class="badge bg-light text-dark border">URL: {self.url}</span>')

    @property
    def url_target(self):
        """URL'i dinamik olarak çözer"""
        from flask import url_for
        if self.endpoint:
            try:
                return url_for(self.endpoint)
            except:
                return "#"
        return self.url or "#"

