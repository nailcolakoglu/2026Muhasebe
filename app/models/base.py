# models/base.py - TAMAMEN DÜZELTİLMİŞ VERSİYON

import sys
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

#from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.pagination import Pagination
from sqlalchemy.orm import Query
from sqlalchemy.types import TypeDecorator, Text
from flask_login import current_user
from flask import session, request
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# ========================================
# VERİTABANI NESNESİ
# ========================================
from app.extensions import db, get_tenant_db


# ========================================
# JSON TYPE (SENİNKİ)
# ========================================
class JSONText(TypeDecorator):
    """
    Python tarafında Dict (Sözlük) olarak çalışır,
    Veritabanına (Firebird) kaydederken String (Text) formatına çevirir.
    """
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None: 
            return {}
        try: 
            return json.loads(value)
        except:
            return {}

# ========================================
# ROLES & PERMISSIONS (SENİNKİ)
# ========================================
ROLES_PERMISSIONS = {
    'admin': ['all'],
    'patron': ['all'],
    'finans_muduru': [
        'dashboard_goruntule',
        'banka_goruntule', 'banka_islem', 'banka_ekle',
        'kasa_goruntule', 'kasa_islem', 'kasa_ekle',
        'cek_goruntule', 'cek_islem', 'cek_ekle',
        'cari_goruntule', 'cari_ekle',
        'finans_raporlari'
    ],
    'muhasebe_muduru':  [
        'dashboard_goruntule',
        'fatura_goruntule', 'fatura_duzenle',
        'muhasebe_fis_goruntule', 'muhasebe_fis_ekle', 'muhasebe_fis_duzenle',
        'mizan_gor', 'resmi_defter',
        'cari_goruntule', 'cari_duzenle', 'banka_goruntule', 'kasa_goruntule',
        'entegrasyon_yonetimi'
    ],
    'bolge_muduru': [
        'dashboard_goruntule',
        'satis_raporlari', 'stok_raporlari',
        'fatura_goruntule', 'fatura_onay',
        'sube_performans_izleme'
    ],
    'sube_yoneticisi': [
        'dashboard_goruntule',
        'fatura_ekle', 'fatura_goruntule', 'fatura_iptal',
        'kasa_goruntule', 'kasa_islem',
        'stok_goruntule', 'stok_fis_ekle',
        'cari_ekle'
    ],
    'depo': [
        'stok_goruntule', 'stok_duzenle',
        'stok_fis_ekle', 'stok_fis_goruntule',
        'depo_transfer'
    ],
    'plasiyer': [
        'fatura_ekle',
        'fatura_goruntule',
        'siparis_ekle', 'siparis_goruntule',
        'cari_ekle', 'cari_goruntule',
        'stok_goruntule'
    ],
    'user':  [
        'dashboard_goruntule',
        'fatura_ekle',
        'kasa_ekle'
    ]
}

# ========================================
# PAGINATION (YENİ EKLENEN)
# ========================================
class PaginationResult: 
    def __init__(self, items, page, per_page, total, pages):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = pages
    
    @property
    def has_prev(self):
        return self.page > 1
    
    @property
    def has_next(self):
        return self.page < self.pages
    
    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None
    
    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None
    
    def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge: 
                pass
            elif num >= self.page - left_current and num <= self.page + right_current:
                pass
            elif num > self.pages - right_edge:
                pass
            else:
                if last + 1 != num:
                    yield None
                last = num
                continue
            
            if last + 1 != num: 
                yield None
            yield num
            last = num

# ========================================
# CUSTOM QUERY (SENİNKİ + PAGINATION)
# ========================================
class FirmaFilteredQuery(Query):
    """
    Bu sınıf veritabanı sorgularına otomatik filtre uygular (Görünmez Güvenlik Duvarı):
    1.Firma Filtresi: A firması B firmasını göremez (SaaS Güvenliği).
    2.Şube Filtresi: Şube müdürü sadece kendi şubesini görür.
    3.Bölge Filtresi: Bölge müdürü sadece kendine bağlı şubeleri ve verileri görür.
    4.Zimmet Filtresi: Kasiyer sadece kendisine zimmetli kasayı görür.
    """

    def get(self, ident):
        obj = super().get(ident)
        if obj and self._check_access(obj):
            return obj
        return None

    def __iter__(self):
        return self._apply_filters().__iter__()

    def _check_access(self, obj):
        """Tekil nesneye erişim yetkisi var mı?"""
        if not current_user.is_authenticated:
            return True
            
        if getattr(current_user, 'is_super_admin', False):
            return True

        if hasattr(obj, 'firma_id') and obj.firma_id != current_user.firma_id:
            return False
            
        merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
        
        if hasattr(current_user, 'rol') and current_user.rol not in merkez_rolleri:
            
            if current_user.rol == 'bolge_muduru':
                aktif_bolge_id = session.get('aktif_bolge_id')
                
                if hasattr(obj, 'bolge_id') and obj.bolge_id is not None:
                    if aktif_bolge_id and obj.bolge_id != int(aktif_bolge_id):
                        return False

            else:
                aktif_sube_id = session.get('aktif_sube_id')
                
                if hasattr(obj, 'sube_id') and obj.sube_id is not None:
                    if aktif_sube_id and obj.sube_id != int(aktif_sube_id):
                        return False

                if current_user.rol in ['kasiyer', 'tezgahtar'] and hasattr(obj, 'kullanici_id'):
                    if obj.kullanici_id and obj.kullanici_id != current_user.id:
                        return False
        
        return True

    def _apply_filters(self):
        """Sorguya otomatik WHERE şartları ekler"""
        query = self
        if current_user.is_authenticated:
            if getattr(current_user, 'is_super_admin', False):
                return query
            
            if not self.column_descriptions:
                return query
            model_class = self.column_descriptions[0]['type']

            if hasattr(model_class, 'firma_id'):
                query = query.filter_by(firma_id=current_user.firma_id)
            
            merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
            
            if hasattr(current_user, 'rol') and current_user.rol not in merkez_rolleri:
                
                if current_user.rol == 'bolge_muduru':
                    aktif_bolge_id = session.get('aktif_bolge_id')
                    
                    if aktif_bolge_id:
                        if hasattr(model_class, 'bolge_id'):
                            query = query.filter_by(bolge_id=aktif_bolge_id)
                        
                        elif hasattr(model_class, 'sube_id'):
                            try:
                                from models import Sube
                            except ImportError:
                                Sube = globals().get('Sube')

                            if Sube: 
                                bagli_subeler = self.session.query(Sube.id).filter(
                                    Sube.firma_id == current_user.firma_id,
                                    Sube.bolge_id == aktif_bolge_id
                                ).all()
                                
                                sube_ids = [s.id for s in bagli_subeler]
                                
                                if not sube_ids:
                                    sube_ids = [-1]
                                    
                                query = query.filter(model_class.sube_id.in_(sube_ids))

                else:
                    aktif_sube_id = session.get('aktif_sube_id')
                    
                    if aktif_sube_id and hasattr(model_class, 'sube_id'):
                        query = query.filter_by(sube_id=aktif_sube_id)

                    if current_user.rol in ['kasiyer', 'tezgahtar'] and hasattr(model_class, 'kullanici_id'):
                        query = query.filter_by(kullanici_id=current_user.id)
        
        return query
    
    # ========================================
    # YENİ EKLENEN:  PAGINATION
    # ========================================
    def paginate(self, page=None, per_page=None, error_out=False, max_per_page=None, **kwargs):
        """Pagination desteği"""
        if page is None: 
            try:
                page = request.args.get('page', 1, type=int)
            except: 
                page = 1
        
        per_page = per_page or 20
        
        if page < 1:
            page = 1
        
        # Filtreleri uygula
        query = self._apply_filters()
        
        # Manuel pagination
        total = query.count()
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        if page > pages > 0:
            page = pages
        
        offset = (page - 1) * per_page
        items = query.limit(per_page).offset(offset).all()
        
        return PaginationResult(
            items=items,
            page=page,
            per_page=per_page,
            total=total,
            pages=pages
        )
    
    def first_or_404(self, description=None):
        obj = self._apply_filters().first()
        if obj is None:
            from werkzeug.exceptions import NotFound
            raise NotFound(description=description)
        return obj
    
    def get_or_404(self, ident, description=None):
        obj = self.get(ident)
        if obj is None:
            from werkzeug.exceptions import NotFound
            raise NotFound(description=description)
        return obj

# ========================================
# MIXIN SINIFLARI
# ========================================
class TimestampMixin:
    """Oluşturma ve güncelleme tarihleri"""
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class SoftDeleteMixin:
    """Soft delete (mantıksal silme)"""
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    def soft_delete(self):
        self.deleted_at = datetime.now()
    
    def restore(self):
        self.deleted_at = None


class FirmaOwnedMixin: 
    """Firmaya ait kayıtlar için"""
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False, index=True)


# ========================================
# HELPER FUNCTIONS
# ========================================
def ensure_firebird_database(custom_path=None):
    """Firebird veritabanı dosyasını (.fdb) fiziksel olarak oluşturur"""
    import os
    
    db_path = custom_path or r'd:/Firebird/Data/Muhasebe/MuhasebeDB.fdb'
    db_dir = os.path.dirname(db_path)
    
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            logger.info(f"📁 Klasör oluşturuldu: {db_dir}")
        except OSError as e:
            logger.error(f"❌ Klasör oluşturma hatası: {e}")
            return

    if os.path.exists(db_path):
        logger.info(f"✅ Veritabanı dosyası mevcut: {db_path}")
        return
    
    logger.info(f"⚙️ Veritabanı oluşturuluyor: {db_path}")
    
    try:
        import fdb
        
        con = fdb.create_database(
            dsn=f"localhost:{db_path}",
            user='SYSDBA',
            password='masterkey',
            page_size=16384,
            charset='UTF8'
        )
        con.close()
        
        logger.info("✅ Firebird veritabanı başarıyla oluşturuldu")
        
    except ImportError:
        logger.error("❌ fdb paketi yüklü değil:  pip install fdb")
    except Exception as e:
        logger.error(f"❌ Veritabanı oluşturma hatası: {e}")   


# ÇOK FİRMALI KAYIT İÇİN
from flask import g

class TenantQueryMixin:
    """
    Firebird modellerine eklenecek mixin
    Otomatik olarak tenant_db üzerinden sorgu yapar
    """
    
    @classmethod
    def query_tenant(cls):
        """Tenant DB üzerinden sorgu döner"""
        if g.tenant_db:
            return g.tenant_db.query(cls)
        else:
            raise RuntimeError("Tenant DB bağlantısı yok.Lütfen giriş yapın.")

# ========================================
# MANY-TO-MANY İLİŞKİ TABLOLARI
# ========================================

# Kullanıcı - Şube Yetkilendirme
kullanici_sube_yetki = db.Table('kullanici_sube_yetki',
    db.Column('kullanici_id', db.String(36), db.ForeignKey('kullanicilar.id'), primary_key=True),
    db.Column('sube_id', db.Integer, db.ForeignKey('subeler.id'), primary_key=True),
    extend_existing=True
)


class FirebirdModelMixin:
    """Ticari modeller (Cari, Stok vb.) için sorgu yöneticisi."""
    
    @classmethod
    def query_fb(cls):
        """Bu model için Firebird session'ı üzerinden sorgu başlatır."""
        session = get_tenant_db()
        if not session:
            return None
        return session.query(cls)