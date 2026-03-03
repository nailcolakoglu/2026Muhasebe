# models/base.py - MYSQL/POSTGRESQL OPTİMİZE EDİLMİŞ TEMİZ VERSİYON

import sys
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

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
# JSON TYPE (Veritabanı Bağımsız)
# ========================================
class JSONText(TypeDecorator):
    """
    Python tarafında Dict (Sözlük) olarak çalışır,
    Veritabanına kaydederken String (Text) formatına çevirir.
    (MySQL/PostgreSQL Native JSON desteklese de bu yapı uyumluluk sağlar)
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
# ROLES & PERMISSIONS
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
# PAGINATION 
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
# CUSTOM QUERY (SaaS İzolasyon ve Güvenlik Motoru)
# ========================================
class FirmaFilteredQuery(Query):
    """
    Bu sınıf veritabanı sorgularına otomatik filtre uygular (Görünmez Güvenlik Duvarı):
    1.Firma Filtresi: A firması B firmasını göremez (SaaS Güvenliği).
    2.Şube Filtresi: Şube müdürü sadece kendi şubesini görür.
    3.Bölge Filtresi: Bölge müdürü sadece kendine bağlı şubeleri ve verileri görür.
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
                    if aktif_bolge_id and obj.bolge_id != str(aktif_bolge_id): # UUID Düzeltmesi (str)
                        return False

            else:
                aktif_sube_id = session.get('aktif_sube_id')
                
                if hasattr(obj, 'sube_id') and obj.sube_id is not None:
                    if aktif_sube_id and obj.sube_id != str(aktif_sube_id): # UUID Düzeltmesi (str)
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
                                from app.models import Sube # Import yolu düzeltildi
                            except ImportError:
                                Sube = globals().get('Sube')

                            if Sube: 
                                bagli_subeler = self.session.query(Sube.id).filter(
                                    Sube.firma_id == current_user.firma_id,
                                    Sube.bolge_id == aktif_bolge_id
                                ).all()
                                
                                sube_ids = [s.id for s in bagli_subeler]
                                
                                if not sube_ids:
                                    sube_ids = ['-1'] # UUID için -1 string
                                    
                                query = query.filter(model_class.sube_id.in_(sube_ids))

                else:
                    aktif_sube_id = session.get('aktif_sube_id')
                    
                    if aktif_sube_id and hasattr(model_class, 'sube_id'):
                        query = query.filter_by(sube_id=aktif_sube_id)

                    if current_user.rol in ['kasiyer', 'tezgahtar'] and hasattr(model_class, 'kullanici_id'):
                        query = query.filter_by(kullanici_id=current_user.id)
        
        return query
    
    def paginate(self, page=None, per_page=None, error_out=False, max_per_page=None, **kwargs):
        """Pagination desteği"""
        if page is None: 
            try:
                page = request.args.get('page', 1, type=int)
            except: 
                page = 1
        
        per_page = per_page or 20
        if page < 1: page = 1
        
        query = self._apply_filters()
        total = query.count()
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        if page > pages > 0: page = pages
        
        offset = (page - 1) * per_page
        items = query.limit(per_page).offset(offset).all()
        
        return PaginationResult(items=items, page=page, per_page=per_page, total=total, pages=pages)
    
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