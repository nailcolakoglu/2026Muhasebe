# app/modules/kullanici/models.py

from app.extensions import db
from app.models.base import TimestampMixin, SoftDeleteMixin

class Kullanici(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Firebird Kullanıcı Modeli (Gölge Tablo)
    """
    __tablename__ = 'kullanicilar'
    
    id = db.Column(db.String(36), primary_key=True) 
    
    ad_soyad = db.Column(db.String(100))
    email = db.Column(db.String(120))
    
    # 1. ForeignKey (Veritabanı Bağlantısı - ŞART)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=True)
    sube_id = db.Column(db.String(36), db.ForeignKey('subeler.id'), nullable=True)
    
    aktif = db.Column(db.Boolean, default=True)
    
    # 2. Relationship (Nesne İlişkisi - ŞART)
    # Firma modelinden bu modele erişilirken hata almamak için bunu geri ekliyoruz.
    # 'overlaps' parametresi, eğer Firma modelinde de benzer bir tanım varsa çakışmayı önler.
    firma = db.relationship('Firma', backref='db_kullanicilari', foreign_keys=[firma_id])
    
    # Şube ilişkisi
    sube = db.relationship('Sube', backref='sube_calisanlari', foreign_keys=[sube_id])

    def __repr__(self):
        return f"<FB_User {self.ad_soyad}>"