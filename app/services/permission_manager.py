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

        'muhasebeci': [
            'dashboard.view',
            'muhasebe.*',
            'fatura.*',
            'cari.*',
            'kasa.*', 'banka.*', 'cek.*',
            'bolge_gor', 'sube_gor', 'stok_gor'
        ],
        
        # ==========================================
        # 🏢 YÖNETİM KADEMESİ (SAHA YÖNETİMİ)
        # ==========================================
        'bolge_muduru': [
            'dashboard.view',      # Bölge özetini görür
            'dashboard.bolge',     # Kendi bölgesindeki tüm şubeler
            'bolge_gor', 'bolge_guncelle',  # ← BURASI EKSİKTİ!
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
        'depo_sorumlusu': [
            'dashboard.depo',
            'stok.*',
            'depo.*',
            'irsaliye.*',
            'stok_fisi.*',
            'sube_gor'
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
        ],
        
        'manager': [
            'dashboard.*',
            'bolge_*', 'sube_*', 'depo_*',
            'stok_*', 'cari_*', 'fatura_*',
            'siparis_*', 'irsaliye_*',
            'kasa.*', 'banka.*',
            'rapor.*'
        ],
        'satis_temsilcisi': [
            'dashboard.view',
            'cari.create', 'cari.view', 'cari.edit',
            'siparis.*',
            'stok.view',
            'fiyat.view',
            'bolge_gor', 'sube_gor'
        ],
        'user': [
            'dashboard.view',
            'bolge_gor', 'sube_gor', 'depo_gor',
            'stok_gor', 'cari_gor',
            'fatura_gor', 'siparis_gor',
            'irsaliye_gor',
            'kasa_gor', 'banka_gor'
        ],
        
        'viewer': [
            'dashboard.view',
            '*.view',  # Tüm görüntüleme yetkileri
            'bolge_gor', 'sube_gor', 'stok_gor',
            'cari_gor', 'fatura_gor',
            'rapor_gor'
        ]       
    }

    @staticmethod
    def check(user_role, permission_needed):
        """
        Rol ve Yetki Kontrolü
        
        Args:
            user_role (str): Kullanıcı rolü (örn: 'admin', 'bolge_muduru')
            permission_needed (str): İstenen yetki (örn: 'bolge_guncelle', 'fatura.delete')
        
        Returns:
            bool: Yetki var mı?
        
        Wildcard Kuralları:
            - '*' → Tüm yetkiler
            - 'bolge_*' → bolge_olustur, bolge_guncelle, bolge_sil, bolge_gor
            - 'fatura.*' → fatura.create, fatura.view, fatura.delete
            - '*.view' → bolge_gor, stok_gor gibi tüm görüntüleme yetkileri
        """
        if not user_role:
            return False
        
        allowed = PermissionManager.ROLE_DEFINITIONS.get(user_role, [])
        
        # 1. ✅ Tam yetki (*)
        if '*' in allowed:
            return True
        
        # 2. ✅ Tam eşleşme
        if permission_needed in allowed:
            return True
        
        # 3. ✅ Prefix wildcard (bolge_*, stok_*)
        #    Sadece underscore ile ayrılmış wildcard'lar (nokta YOK)
        for perm in allowed:
            if '*' in perm and '.' not in perm:  # ← ÖNEMLİ: Nokta kontrolü
                prefix = perm.replace('*', '')
                if permission_needed.startswith(prefix):
                    return True
        
        # 4. ✅ Grup yetkisi (fatura.*, cari.*)
        #    Nokta ile ayrılmış wildcard'lar
        parts = permission_needed.split('.')
        if len(parts) > 1:
            if f"{parts[0]}.*" in allowed:
                return True
        
        # 5. ✅ Suffix wildcard (*.view, *.gor)
        #    Tüm görüntüleme yetkileri
        if permission_needed.endswith('.view') and '*.view' in allowed:
            return True
        
        if permission_needed.endswith('_gor') and '*_gor' in allowed:
            return True
        
        return False
