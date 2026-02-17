# app/context_manager.py
"""
Global context yönetimi - Cache ve lazy loading ile optimize edilmiş
"""
from functools import lru_cache
from flask import g, session
from datetime import datetime, timezone
import pickle
from app.extensions import db, cache
from app.models.master import Tenant  # ✅ Sadece Tenant
from sqlalchemy.orm import joinedload

class GlobalContextManager:
    """
    Global context verilerini cache'leyerek performansı artırır.
    
    Özellikler:
    - LRU cache ile hafıza optimizasyonu
    - Redis cache entegrasyonu
    - Lazy loading
    - TTL (Time To Live) desteği
    """
    
    # Cache süresi (saniye)
    CACHE_TTL = 300  # 5 dakika
    
    @staticmethod
    @cache.memoize(timeout=CACHE_TTL)
    def get_active_modules():
        """
        Aktif modülleri cache'den al veya hardcoded liste döndür.
        
        NOT: Module tablosu olmadığı için statik liste kullanılıyor.
        
        Returns:
            list: Aktif modül listesi
        """
        # ✅ HARDCODED MODÜL LİSTESİ (Module tablosu yok)
        modules = [
            {'kod': 'auth', 'ad': 'Kimlik Doğrulama', 'ikon': 'bi-lock', 'aktif': True, 'sira': 1},
            {'kod': 'main', 'ad': 'Ana Sayfa', 'ikon': 'bi-house', 'aktif': True, 'sira': 2},
            {'kod': 'firmalar', 'ad': 'Firmalar', 'ikon': 'bi-building', 'aktif': True, 'sira': 3},
            {'kod': 'sube', 'ad': 'Şubeler', 'ikon': 'bi-shop', 'aktif': True, 'sira': 4},
            {'kod': 'depo', 'ad': 'Depolar', 'ikon': 'bi-box-seam', 'aktif': True, 'sira': 5},
            {'kod': 'stok', 'ad': 'Stok Kartları', 'ikon': 'bi-boxes', 'aktif': True, 'sira': 6},
            {'kod': 'stok-fisi', 'ad': 'Stok Fişleri', 'ikon': 'bi-receipt', 'aktif': True, 'sira': 7},
            {'kod': 'cari', 'ad': 'Cari Hesaplar', 'ikon': 'bi-people', 'aktif': True, 'sira': 8},
            {'kod': 'kategori', 'ad': 'Kategoriler', 'ikon': 'bi-tags', 'aktif': True, 'sira': 9},
            {'kod': 'kullanici', 'ad': 'Kullanıcılar', 'ikon': 'bi-person-badge', 'aktif': True, 'sira': 10},
            {'kod': 'irsaliye', 'ad': 'İrsaliyeler', 'ikon': 'bi-truck', 'aktif': True, 'sira': 11},
            {'kod': 'fatura', 'ad': 'Faturalar', 'ikon': 'bi-file-earmark-text', 'aktif': True, 'sira': 12},
            {'kod': 'efatura', 'ad': 'E-Fatura', 'ikon': 'bi-envelope-paper', 'aktif': True, 'sira': 13},
            {'kod': 'doviz', 'ad': 'Döviz Kurları', 'ikon': 'bi-currency-exchange', 'aktif': True, 'sira': 14},
            {'kod': 'lokasyon', 'ad': 'Lokasyonlar', 'ikon': 'bi-geo-alt', 'aktif': True, 'sira': 15},
            {'kod': 'fiyat', 'ad': 'Fiyat Listeleri', 'ikon': 'bi-tag', 'aktif': True, 'sira': 16},
            {'kod': 'sistem', 'ad': 'Sistem Ayarları', 'ikon': 'bi-gear', 'aktif': True, 'sira': 17},
            {'kod': 'bolge', 'ad': 'Bölgeler', 'ikon': 'bi-map', 'aktif': True, 'sira': 18},
            {'kod': 'siparis', 'ad': 'Siparişler', 'ikon': 'bi-cart', 'aktif': True, 'sira': 19},
            {'kod': 'mobile', 'ad': 'Mobil', 'ikon': 'bi-phone', 'aktif': True, 'sira': 20},
            {'kod': 'finans', 'ad': 'Finans', 'ikon': 'bi-cash-stack', 'aktif': True, 'sira': 21},
            {'kod': 'kasa', 'ad': 'Kasalar', 'ikon': 'bi-safe', 'aktif': True, 'sira': 22},
            {'kod': 'kasa-hareket', 'ad': 'Kasa Hareketleri', 'ikon': 'bi-arrow-left-right', 'aktif': True, 'sira': 23},
            {'kod': 'banka', 'ad': 'Bankalar', 'ikon': 'bi-bank', 'aktif': True, 'sira': 24},
            {'kod': 'banka-hareket', 'ad': 'Banka Hareketleri', 'ikon': 'bi-credit-card', 'aktif': True, 'sira': 25},
            {'kod': 'banka-import', 'ad': 'Banka Import', 'ikon': 'bi-cloud-upload', 'aktif': True, 'sira': 26},
            {'kod': 'cek', 'ad': 'Çek/Senet', 'ikon': 'bi-wallet2', 'aktif': True, 'sira': 27},
            {'kod': 'muhasebe', 'ad': 'Muhasebe', 'ikon': 'bi-calculator', 'aktif': True, 'sira': 28},
            {'kod': 'rapor', 'ad': 'Raporlar', 'ikon': 'bi-graph-up', 'aktif': True, 'sira': 29},
        ]
        return modules

    
    @staticmethod
    @cache.memoize(timeout=CACHE_TTL)
    def get_tenant_metadata(tenant_id):
        """
        Tenant metadata'sını cache'le (firma, şube, modül izinleri).
        
        Args:
            tenant_id (str): Tenant UUID
            
        Returns:
            dict: Tenant metadata
        """
        # ✅ joinedload KALDIRILDI (lisans ilişkisi yok)
        tenant = Tenant.query.filter_by(id=tenant_id).first()
        
        if not tenant:
            return None
        
        # ✅ Lisans bilgisi varsa al (foreign key kontrolü)
        lisans_bitis = None
        if hasattr(tenant, 'license_id') and tenant.license_id:
            try:
                from app.models.master import License
                lisans = License.query.get(tenant.license_id)
                if lisans and hasattr(lisans, 'bitis_tarihi'):
                    lisans_bitis = lisans.bitis_tarihi.isoformat()
            except Exception:
                pass
            
        return {
            'id': str(tenant.id),
            'kod': tenant.kod if hasattr(tenant, 'kod') else str(tenant.id),
            'unvan': tenant.unvan if hasattr(tenant, 'unvan') else 'Firma',
            'schema_name': f'tenant_{tenant.kod}' if hasattr(tenant, 'kod') else f'tenant_{tenant.id}',
            'aktif_moduller': ['stok', 'cari', 'fatura', 'siparis', 'kasa', 'banka'],  # ✅ Hardcoded
            'lisans_bitis': lisans_bitis,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def get_tenant_data_lazy(tenant_id):
        """
        Tenant verilerini lazy load et (sadece gerektiğinde).
        
        Args:
            tenant_id (str): Tenant UUID
            
        Returns:
            LazyTenantData: Lazy yüklenen veri nesnesi
        """
        return LazyTenantData(tenant_id)
    
    @staticmethod
    def invalidate_cache(pattern='*'):
        """
        Cache'i temizle (veri güncellendiğinde).
        
        Args:
            pattern (str): Temizlenecek cache pattern'i
        """
        if pattern == 'modules':
            cache.delete_memoized(GlobalContextManager.get_active_modules)
        elif pattern == 'tenant':
            # Tüm tenant cache'lerini temizle
            cache.delete_memoized(GlobalContextManager.get_tenant_metadata)
        else:
            cache.clear()


class LazyTenantData:
    """
    Tenant verilerini lazy load eden sınıf.
    Sadece erişildiğinde yükler (örn: g.tenant.firmalar)
    """
    
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self._firmalar = None
        self._subeler = None
        self._kasalar = None
        self._kullanicilar = None
        
    @property
    def firmalar(self):
        """Firmaları lazy load et."""
        if self._firmalar is None:
            # ✅ Güvenli import (circular import önlemi)
            try:
                from app.modules.firma.models import Firma
                self._firmalar = cache.get(f'tenant_{self.tenant_id}_firmalar')
                
                if self._firmalar is None:
                    self._firmalar = Firma.query.filter_by(aktif=True).all()
                    cache.set(f'tenant_{self.tenant_id}_firmalar', self._firmalar, timeout=300)
            except ImportError:
                self._firmalar = []
                
        return self._firmalar
    
    @property
    def subeler(self):
        """Şubeleri lazy load et."""
        if self._subeler is None:
            try:
                from app.modules.sube.models import Sube
                self._subeler = cache.get(f'tenant_{self.tenant_id}_subeler')
                
                if self._subeler is None:
                    self._subeler = Sube.query.filter_by(aktif=True).all()
                    cache.set(f'tenant_{self.tenant_id}_subeler', self._subeler, timeout=300)
            except ImportError:
                self._subeler = []
                
        return self._subeler
    
    @property
    def kasalar(self):
        """Kasaları lazy load et."""
        if self._kasalar is None:
            try:
                from app.modules.kasa.models import Kasa
                self._kasalar = cache.get(f'tenant_{self.tenant_id}_kasalar')
                
                if self._kasalar is None:
                    self._kasalar = Kasa.query.filter_by(aktif=True).all()
                    cache.set(f'tenant_{self.tenant_id}_kasalar', self._kasalar, timeout=300)
            except ImportError:
                self._kasalar = []
                
        return self._kasalar
    
    @property
    def kullanicilar(self):
        """Kullanıcıları lazy load et."""
        if self._kullanicilar is None:
            try:
                from app.models.master import User
                self._kullanicilar = cache.get(f'tenant_{self.tenant_id}_kullanicilar')
                
                if self._kullanicilar is None:
                    self._kullanicilar = User.query.filter_by(aktif=True).all()
                    cache.set(f'tenant_{self.tenant_id}_kullanicilar', self._kullanicilar, timeout=300)
            except ImportError:
                self._kullanicilar = []
                
        return self._kullanicilar