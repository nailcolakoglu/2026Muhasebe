# app/signals.py

"""
Flask Signals - Olay Tabanlı İletişim Sistemi (Event-Driven Architecture)
Enterprise Grade - Muhasebe, WMS, SaaS ve AI Destekli
"""

from flask.signals import Namespace

# Namespace oluştur (Organizasyon için)
_signals = Namespace()

# =========================================
# SİPARİŞ SİNYALLERİ
# =========================================

siparis_olusturuldu = _signals.signal('siparis-olusturuldu')
"""Yeni bir sipariş oluşturulduğunda tetiklenir."""

siparis_onaylandi = _signals.signal('siparis-onaylandi')
"""Sipariş onaylandığında tetiklenir."""

siparis_sevk_edildi = _signals.signal('siparis-sevk-edildi')
"""Sipariş sevk edildiğinde (Stok düşürme) tetiklenir."""

siparis_faturalandi = _signals.signal('siparis-faturalandi')
"""Sipariş faturalandığında (Otomatik fatura) tetiklenir."""

siparis_iptal_edildi = _signals.signal('siparis-iptal-edildi')
"""Sipariş iptal edildiğinde tetiklenir."""

siparis_tamamlandi = _signals.signal('siparis-tamamlandi')
"""Sipariş tamamen teslim edildiğinde tetiklenir."""


# =========================================
# FATURA SİNYALLERİ
# =========================================

fatura_olusturuldu = _signals.signal('fatura-olusturuldu')
"""
Yeni fatura oluşturulduğunda tetiklenir.
(Muhasebe entegrasyonunu tetikleyen ana sinyaldir)
"""

fatura_guncellendi = _signals.signal('fatura-guncellendi')
"""Fatura düzeltme/güncelleme işleminde tetiklenir."""

fatura_onaylandi = _signals.signal('fatura-onaylandi')
"""Fatura onaylandığında (Stok/Cari hareketi için) tetiklenir."""

fatura_iptal_edildi = _signals.signal('fatura-iptal-edildi')
"""Fatura iptal edildiğinde (Ters kayıtlar için) tetiklenir."""


# =========================================
# STOK & WMS SİNYALLERİ
# =========================================

stok_hareket_olusturuldu = _signals.signal('stok-hareket-olusturuldu')
"""Manuel veya otomatik stok hareketi oluşturulduğunda tetiklenir."""

stok_kritik_seviyede = _signals.signal('stok-kritik-seviyede')
"""Stok kritik seviyenin altına düştüğünde tetiklenir (AI/Uyarı için)."""

wms_transfer_yapildi = _signals.signal('wms-transfer-yapildi')
"""
WMS el terminali ile raflar arası transfer yapıldığında tetiklenir.
Args: sender, cikis_raf, varis_raf, miktar
"""


# =========================================
# CARİ SİNYALLERİ
# =========================================

cari_borc_limiti_asildi = _signals.signal('cari-borc-limiti-asildi')
"""Cari borç limiti aşıldığında (Risk yönetimi) tetiklenir."""

cari_odeme_yapildi = _signals.signal('cari-odeme-yapildi')
"""Cariye ödeme yapıldığında tetiklenir."""


# =========================================
# KASA & BANKA (FİNANS) SİNYALLERİ
# =========================================

kasa_hareket_olusturuldu = _signals.signal('kasa-hareket-olusturuldu')
"""
Kasa üzerinden tahsilat/tediye yapıldığında tetiklenir.
(Muhasebe fişini otomatik kesmek için kullanılır)
"""

banka_hareket_olusturuldu = _signals.signal('banka-hareket-olusturuldu')
"""
Banka üzerinden virman/EFT/Havale yapıldığında tetiklenir.
(Muhasebe fişini otomatik kesmek için kullanılır)
"""

tahsilat_yapildi = _signals.signal('tahsilat-yapildi')
"""Genel tahsilat işlemi yapıldığında tetiklenir."""

tediye_yapildi = _signals.signal('tediye-yapildi')
"""Genel tediye (ödeme) işlemi yapıldığında tetiklenir."""


# =========================================
# ÇEK/SENET SİNYALLERİ
# =========================================

cek_tahsil_edildi = _signals.signal('cek-tahsil-edildi')
"""Çek başarıyla tahsil edildiğinde tetiklenir."""

cek_karsiliksiz_cikti = _signals.signal('cek-karsiliksiz-cikti')
"""Çek karşılıksız çıktığında (Risk skoru düşürmek için) tetiklenir."""

cek_ciro_edildi = _signals.signal('cek-ciro-edildi')
"""Çek başka bir cariye ciro edildiğinde tetiklenir."""


# =========================================
# SAAS / KURULUM SİNYALLERİ
# =========================================

yeni_tenant_kuruldu = _signals.signal('yeni-tenant-kuruldu')
"""
Yeni bir firma/abonelik satın alınıp DB kurulduğunda tetiklenir.
(Örn: Otomatik TDHP yüklemek veya Hoşgeldin maili atmak için)
"""


# =========================================
# KULLANICI/YETKİ SİNYALLERİ
# =========================================

kullanici_giris_yapti = _signals.signal('kullanici-giris-yapti')
"""Kullanıcı sisteme giriş yaptığında (Loglama için) tetiklenir."""

yetkisiz_erisim_denemesi = _signals.signal('yetkisiz-erisim-denemesi')
"""Yetkisiz sayfa veya işlem denemesinde (Güvenlik için) tetiklenir."""


# =========================================
# RAPOR/ANALIZ (AI) SİNYALLERİ
# =========================================

ai_rapor_olusturuldu = _signals.signal('ai-rapor-olusturuldu')
"""Yapay zeka raporu (CEO Özeti vs.) oluşturulduğunda tetiklenir."""

anomali_tespit_edildi = _signals.signal('anomali-tespit-edildi')
"""AI tarafından anormal bir fiyat, stok veya satış tespit edildiğinde tetiklenir."""


# =========================================
# ÖRNEK KULLANIM (Test için)
# =========================================

if __name__ == "__main__": 
    """
    Signal sistemini test eder (Sadece dosyayı direkt çalıştırırsanız)
    """
    
    # Listener (Dinleyici) tanımla
    @siparis_onaylandi.connect
    def siparis_onay_mesaji(sender, **kwargs):
        print(f"📦 Sipariş onaylandı: {sender}")
        print(f"   Ek bilgiler: {kwargs}")
    
    # Signal gönder (Test)
    class TestSiparis:
        def __init__(self, id, musteri):
            self.id = id
            self.musteri = musteri
        
        def __repr__(self):
            return f"<Siparis #{self.id}>"
    
    test_siparis = TestSiparis(id=123, musteri="Acme Ltd.")
    
    # Sinyali tetikle
    siparis_onaylandi.send(test_siparis, onaylayan="Admin", not_="Test signal")
    
    print("\n✅ Signal sistemi kusursuz çalışıyor!")