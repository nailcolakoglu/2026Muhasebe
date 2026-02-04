# signals.py (app.py ile aynı dizinde oluştur)

"""
Flask Signals - Olay Tabanlı İletişim Sistemi

Modüller arası bağımlılığı azaltmak için kullanılır.
Örnek: Sipariş onaylandığında stok modülü otomatik çalışır.
"""

from flask.signals import Namespace

# Namespace oluştur (Organizasyon için)
_signals = Namespace()

# =========================================
# SİPARİŞ SİNYALLERİ
# =========================================

siparis_olusturuldu = _signals.signal('siparis-olusturuldu')
"""
Yeni bir sipariş oluşturulduğunda tetiklenir.

Args:
    sender:  Sipariş nesnesi (Siparis model instance)
    
Örnek kullanım:
    siparis_olusturuldu.send(siparis, kullanici=current_user)
"""

siparis_onaylandi = _signals.signal('siparis-onaylandi')
"""
Sipariş onaylandığında tetiklenir.

Args:
    sender: Sipariş nesnesi
    onaylayan: Onaylayan kullanıcı
"""

siparis_sevk_edildi = _signals.signal('siparis-sevk-edildi')
"""
Sipariş sevk edildiğinde tetiklenir.
Stok düşürme işlemi için kullanılır.

Args:
    sender: Sipariş nesnesi
    sevk_tarihi: datetime
    kargo_takip_no: str (opsiyonel)
    
Örnek kullanım: 
    @siparis_sevk_edildi.connect
    def stok_dus(sender, **kwargs):
        # Stok düşürme mantığı
        pass
"""

siparis_faturalandi = _signals.signal('siparis-faturalandi')
"""
Sipariş faturalandığında tetiklenir.
Otomatik fatura oluşturma için kullanılır.

Args:
    sender: Sipariş nesnesi
    fatura:  Oluşturulan fatura nesnesi (opsiyonel)
    
Örnek kullanım: 
    siparis_faturalandi.send(
        siparis, 
        fatura=yeni_fatura,
        kullanici=current_user
    )
"""

siparis_iptal_edildi = _signals.signal('siparis-iptal-edildi')
"""
Sipariş iptal edildiğinde tetiklenir.
Stok iadesi ve ödeme iadesi için kullanılır.

Args:
    sender: Sipariş nesnesi
    iptal_nedeni: str
"""

siparis_tamamlandi = _signals.signal('siparis-tamamlandi')
"""
Sipariş tamamen teslim edildiğinde tetiklenir.

Args:
    sender: Sipariş nesnesi
    teslim_tarihi: datetime
"""

# =========================================
# FATURA SİNYALLERİ
# =========================================

fatura_olusturuldu = _signals.signal('fatura-olusturuldu')
"""
Yeni fatura oluşturulduğunda tetiklenir.

Args:
    sender: Fatura nesnesi
    fatura_turu: 'alis' veya 'satis'
"""
fatura_guncellendi = _signals.signal('fatura-guncellendi')
"""
fatura Düzeltme işleminde tetiklenir.

Args:
    sender: Fatura nesnesi
    fatura_turu: 'alis' veya 'satis'
"""
fatura_onaylandi = _signals.signal('fatura-onaylandi')
"""
Fatura onaylandığında tetiklenir.
Stok ve cari hareketleri için kullanılır.

Args:
    sender: Fatura nesnesi
"""

fatura_iptal_edildi = _signals.signal('fatura-iptal-edildi')
"""
Fatura iptal edildiğinde tetiklenir.

Args:
    sender: Fatura nesnesi
    iptal_nedeni: str
"""

# =========================================
# STOK SİNYALLERİ
# =========================================

stok_hareket_olusturuldu = _signals.signal('stok-hareket-olusturuldu')
"""
Stok hareketi oluşturulduğunda tetiklenir.

Args:
    sender: StokHareketi nesnesi
    hareket_turu: 'giris' veya 'cikis'
"""

stok_kritik_seviyede = _signals.signal('stok-kritik-seviyede')
"""
Stok kritik seviyenin altına düştüğünde tetiklenir.

Args:
    sender: StokKart nesnesi
    mevcut_miktar: float
    kritik_seviye: float
"""

# =========================================
# CARİ SİNYALLERİ
# =========================================

cari_borc_limiti_asildi = _signals.signal('cari-borc-limiti-asildi')
"""
Cari borç limiti aşıldığında tetiklenir.

Args:
    sender: CariHesap nesnesi
    mevcut_borc:  Decimal
    limit: Decimal
"""

cari_odeme_yapildi = _signals.signal('cari-odeme-yapildi')
"""
Cariye ödeme yapıldığında tetiklenir.

Args:
    sender: CariHesap nesnesi
    tutar: Decimal
    odeme_tipi: 'nakit', 'havale', 'cek'
"""

# =========================================
# FİNANS SİNYALLERİ
# =========================================

tahsilat_yapildi = _signals.signal('tahsilat-yapildi')
"""
Tahsilat işlemi yapıldığında tetiklenir.

Args:
    sender: FinansIslem nesnesi
    kasa_id: int (opsiyonel)
    banka_hesap_id: int (opsiyonel)
"""

tediye_yapildi = _signals.signal('tediye-yapildi')
"""
Tediye (ödeme) işlemi yapıldığında tetiklenir.

Args:
    sender: FinansIslem nesnesi
"""

# =========================================
# ÇEK/SENET SİNYALLERİ
# =========================================

cek_tahsil_edildi = _signals.signal('cek-tahsil-edildi')
"""
Çek tahsil edildiğinde tetiklenir.

Args:
    sender: CekSenet nesnesi
"""

cek_karsiliksiz_cikti = _signals.signal('cek-karsiliksiz-cikti')
"""
Çek karşılıksız çıktığında tetiklenir.
Risk skoru güncellemesi için kullanılır.

Args:
    sender: CekSenet nesnesi
    cari:  CariHesap nesnesi
"""

# =========================================
# KULLANICI/YETKİ SİNYALLERİ
# =========================================

kullanici_giris_yapti = _signals.signal('kullanici-giris-yapti')
"""
Kullanıcı sisteme giriş yaptığında tetiklenir.

Args:
    sender:  Kullanici nesnesi
    ip_adresi: str
"""

yetkisiz_erisim_denemesi = _signals.signal('yetkisiz-erisim-denemesi')
"""
Yetkisiz erişim denemesi olduğunda tetiklenir.

Args:
    sender: Kullanici nesnesi
    erisilen_url: str
"""

# =========================================
# RAPOR/ANALIZ SİNYALLERİ
# =========================================

ai_rapor_olusturuldu = _signals.signal('ai-rapor-olusturuldu')
"""
AI raporu oluşturulduğunda tetiklenir.

Args:
    sender: AIRaporGecmisi nesnesi
"""

anomali_tespit_edildi = _signals.signal('anomali-tespit-edildi')
"""
Sistemde anormal bir durum tespit edildiğinde tetiklenir.

Args:
    sender: str (modül adı)
    anomali_tipi: str
    detay: dict
"""


# =========================================
# ÖRNEK KULLANIM (Test için)
# =========================================

if __name__ == "__main__": 
    """
    Signal sistemini test eder
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
    
    print("\n✅ Signal sistemi çalışıyor!")