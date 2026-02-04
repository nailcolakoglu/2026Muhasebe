# modules/rapor/models.py


from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class YazdirmaSablonu(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'yazdirma_sablonlari'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=True) # Null ise Sistem Varsayılanıdır
    
    # Belge Türü: 'fatura', 'tahsilat', 'tediye', 'stok_fisi', 'cari_ekstre', 'mutabakat'
    belge_turu = db.Column(db.String(50), nullable=False) 
    
    baslik = db.Column(db.String(100), nullable=False) # Örn: "Logolu Fatura Tasarımı"
    
    # HTML ve CSS şablonu (Jinja2 formatında saklanır)
    html_icerik = db.Column(db.Text, nullable=False)
    css_icerik = db.Column(db.Text, nullable=True)
    
    aktif = db.Column(db.Boolean, default=True)
    varsayilan = db.Column(db.Boolean, default=False) # O firmanın varsayılanı mı?

    # İlişki (Firmaya bağla)
    firma = db.relationship('Firma', backref='sablonlar')

