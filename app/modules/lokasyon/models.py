# app/modules/lokasyon/models.py

from app.extensions import db
from datetime import datetime

# ----------------------------------------------------------------
# 1.COĞRAFİ MODELLER (ŞEHİR / İLÇE) - YENİ EKLENDİ
# ----------------------------------------------------------------
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Sehir(db.Model):
    __tablename__ = 'sehirler'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    kod = db.Column(db.String(2), unique=True, nullable=False) # Plaka Kodu (01, 34, 35)
    ad = db.Column(db.String(50), nullable=False)
    
    # İlişki (Bir şehrin birçok ilçesi olur)
    ilceler = db.relationship('Ilce', backref='sehir', lazy='dynamic')

class Ilce(db.Model):
    __tablename__ = 'ilceler'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    sehir_id = db.Column(db.String(36), db.ForeignKey('sehirler.id'), nullable=False)
    ad = db.Column(db.String(50), nullable=False)
