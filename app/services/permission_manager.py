# app/services/permission_manager.py

class PermissionManager:
    """
    Rol ve Yetki Tanımları (Kural Kitabı)
    Hangi rolün sistemde nereye erişebileceğini belirler.
    """
    
    # Hangi rol NELERİ yapabilir?
    ROLE_DEFINITIONS = {
        
        # ==========================================
        # 👑 TEPE YÖNETİM (HEADQUARTERS)
        # ==========================================
        'admin': ['*'], # Patron: Her şeyi yapar, kural tanımaz.
        
        'finans_muduru': [
            'dashboard.view',
            'finans.*',     # Tüm finansal raporlar
            'kasa.*',       # Kasa açma/kapama/transfer
            'banka.*',      # Banka hareketleri
            'cek.*',        # Çek/Senet işlemleri
            'cari.view',    # Carileri görür
            'cari.edit',    # Risk limitlerini güncelleyebilir
            'fatura.view',  # Faturaları görür (düzenleyemez)
            'rapor.finans'  # Özel finans raporları
        ],

        'muhasebe_muduru': [
            'dashboard.view',
            'muhasebe.*',   # Resmi muhasebe fişleri
            'efatura.*',    # E-Fatura gönderim/iptal
            'fatura.*',     # Fatura üzerinde tam yetki
            'cari.*',       # Cari kart açma/düzeltme
            'stok.view',    # Stoğu sadece görür
            'rapor.genel'
        ],

        # ==========================================
        # 🏢 YÖNETİM KADEMESİ (SAHA YÖNETİMİ)
        # ==========================================
        'bolge_muduru': [
            'dashboard.view',      # Bölge özetini görür
            'dashboard.bolge',     # Kendi bölgesindeki tüm şubeler
            'rapor.*',             # Tüm satış/stok raporlarına erişir
            'fatura.view',         # Faturaları inceler
            'fatura.onay',         # İskonto onayı verebilir
            'stok.view',
            'cari.view',
            'personel.performans'  # Plasiyer/Şube hedeflerini görür
        ],

        'sube_yoneticisi': [
            'dashboard.view',     # Sadece kendi şubesini görür
            'fatura.create',      # Satış faturası keser
            'fatura.view',
            'fatura.iptal',       # İade/İptal yetkisi vardır
            'kasa.view',          # Şube kasasını denetler
            'kasa.kapanis',       # Gün sonu Z raporu alır
            'stok.view',
            'stok.request',       # Merkezden ürün talep edebilir
            'irsaliye.view'
        ],

        # ==========================================
        # 🚛 SAHA VE OPERASYON (ZİMMETLİ PERSONEL)
        # ==========================================
        'plasiyer': [
            'mobile.login',       # Mobil uygulamaya girebilir
            'siparis.*',          # Sipariş alır, düzenler
            'cari.create',        # Yeni müşteri (potansiyel) oluşturur
            'cari.view',          # Müşteri bakiyesini görür
            'tahsilat.create',    # Sahada para/çek tahsil edebilir
            'stok.view',          # Ürün fiyat/stok görür
            'ziyaret.create'      # Müşteri ziyareti girer
            # NOT: Fatura silemez, cari silemez.
        ],

        'depo': [
            'dashboard.depo',
            'stok.view',
            'stok.sayim',         # Sayım girebilir
            'irsaliye.*',         # Mal kabul/sevk irsaliyesi keser
            'depo.transfer',      # Şubeler arası transfer yapar
            'etiket.print'        # Raf etiketi basar
            # NOT: Fiyatları göremez (Genelde gizlenir)
        ],

        'lojistik': [
            'irsaliye.view',      # Ne taşıdığını görür
            'sevkiyat.*',         # Sevkiyat planlama/teslimat
            'arac.takip'          # Araç km/yakıt girişi
        ],

        'kasiyer': [
            'kasa.satis',         # Hızlı satış ekranı
            'fatura.create',      # Perakende fatura
            'tahsilat.create',    # Nakit/Kredi kartı tahsilat
            'cari.view',          # Müşteri seçimi için
            'stok.view'           # Fiyat gör
            # NOT: Asla fatura silemez, iade alamaz (Yönetici onayı gerekir)
        ],

        'tezgahtar': [
            'stok.view',          # Fiyat sorma cihazı gibi
            'stok.raf',           # Hangi ürün hangi rafta
            'etiket.request'      # Etiket basılması için talep açar
        ]
    }

    @staticmethod
    def check(user_role, permission_needed):
        """
        Rol ve Yetki Kontrolü
        """
        if not user_role: return False
            
        allowed = PermissionManager.ROLE_DEFINITIONS.get(user_role, [])
        
        # 1. Tam Yetki (*)
        if '*' in allowed: return True
            
        # 2. Tam Eşleşme
        if permission_needed in allowed: return True
            
        # 3. Grup Yetkisi (Wildcard) - Örn: 'fatura.*'
        parts = permission_needed.split('.')
        if len(parts) > 1:
            if f"{parts[0]}.*" in allowed: return True
            
        # 4. Suffix Yetkisi - Örn: '*.view'
        if permission_needed.endswith('.view') and '*.view' in allowed: return True

        return False