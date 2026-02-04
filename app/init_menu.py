from app import create_app
from app.extensions import db
from app.modules.firmalar.models import SystemMenu

app = create_app()

def menu_ekle(baslik, icon, endpoint=None, url=None, parent=None, roller=None, sira=0):
    item = SystemMenu(
        baslik=baslik,
        icon=icon,
        endpoint=endpoint,
        url=url,
        parent=parent,
        yetkili_roller=roller,
        sira=sira,
        aktif=True
    )
    db.session.add(item)
    db.session.commit()
    print(f"✅ Eklendi: {baslik}")
    return item

with app.app_context():
    print("🚀 Menü Kurulumu Başlatılıyor...")
    
    # İsteğe bağlı: Önceki menüyü temizle (Çakışma olmasın)
    # db.session.query(MenuItem).delete()
    # db.session.commit()
    
    # 1.PANEL (ANA SAYFA)
    menu_ekle("Panel", "bi bi-speedometer2", endpoint="main.index", sira=1)

    # 2.SATIŞ (Dropdown)
    satis = menu_ekle("Satış", "bi bi-cart3", sira=2)
    # --- Alt Menüler ---
    menu_ekle("Sipariş Listesi", "bi bi-basket", endpoint="siparis.index", parent=satis, sira=1)
    menu_ekle("Yeni Sipariş Al", "bi bi-plus-lg", endpoint="siparis.ekle", parent=satis, sira=2)
    menu_ekle("Satış Faturaları", "bi bi-receipt", endpoint="fatura.index", parent=satis, sira=3)
    menu_ekle("Yeni Fatura Kes", "bi bi-receipt-cutoff", endpoint="fatura.ekle", parent=satis, sira=4)

    # 3.FİNANS (Yetkili: admin, muhasebe)
    finans = menu_ekle("Finans", "bi bi-wallet2", roller="admin,muhasebe", sira=3)
    # --- Alt Menüler ---
    menu_ekle("Virman / Transfer", "bi bi-arrow-left-right", endpoint="finans.virman", parent=finans, sira=1)
    menu_ekle("Gider Fişi", "bi bi-dash-circle", endpoint="finans.gider_ekle", parent=finans, sira=2)
    menu_ekle("Kasa Tanımları", "bi bi-safe", endpoint="kasa.index", parent=finans, sira=3)
    menu_ekle("Kasa Hareketleri", "bi bi-cash-stack", endpoint="kasa_hareket.index", parent=finans, sira=4)
    menu_ekle("Çek / Senet Portföyü", "bi bi-ticket-perforated", endpoint="cek.index", parent=finans, sira=5)
    menu_ekle("Banka Hesapları", "bi bi-credit-card", endpoint="banka.index", parent=finans, sira=6)
    menu_ekle("Banka Hareketleri", "bi bi-credit-card", endpoint="banka_hareket.index", parent=finans, sira=7)
    menu_ekle("CFO Nakit Simülasyonu", "bi bi-currency-exchange", endpoint="finans.nakit_akis_analizi", parent=finans, sira=8)
    menu_ekle("Döviz Kurları", "bi bi-currency-exchange", endpoint="doviz.kur_listesi", parent=finans, sira=9)

    # 4.MUHASEBE (Yetkili: admin, muhasebe)
    muhasebe = menu_ekle("Muhasebe", "bi bi-journal-bookmark-fill", roller="admin,muhasebe", sira=4)
    # --- Alt Menüler ---
    menu_ekle("Muhasebe Fişleri", "bi bi-journal-text", endpoint="muhasebe.index", parent=muhasebe, sira=1)
    menu_ekle("Yeni Mahsup Fişi", "bi bi-plus-circle", endpoint="muhasebe.ekle", parent=muhasebe, sira=2)
    menu_ekle("Hesap Planı (TDHP)", "bi bi-list-nested", endpoint="muhasebe.hesap_plani_index", parent=muhasebe, sira=3)
    menu_ekle("Genel Mizan", "bi bi-calculator", endpoint="muhasebe.mizan", parent=muhasebe, sira=4)
    menu_ekle("Resmi Defterler & e-Defter", "bi bi-file-earmark-lock", endpoint="rapor.resmi_defter_index", parent=muhasebe, sira=5)

    # 5.STOK (Yetkili: admin, muhasebe, depo)
    stok = menu_ekle("Stok", "bi bi-box-seam", roller="admin,muhasebe,depo", sira=5)
    # --- Alt Menüler ---
    menu_ekle("Stok Kartları", "bi bi-boxes", endpoint="stok.index", parent=stok, sira=1)
    menu_ekle("Kategoriler", "bi bi-tags", endpoint="kategori.index", parent=stok, sira=2)
    menu_ekle("Stok Fişleri", "bi bi-arrow-left-right", endpoint="stok_fisi.index", parent=stok, sira=3)
    menu_ekle("Depo Tanımları", "bi bi-building-gear", endpoint="depo.index", parent=stok, sira=4)
    menu_ekle("Fiyat Listeleri", "bi bi-tags-fill", endpoint="fiyat.index", parent=stok, sira=5)
    menu_ekle("AI Stok Analizi", "bi bi-robot", endpoint="stok.yapay_zeka_analiz", parent=stok, sira=6)
    menu_ekle("Ölü Stok Analizi", "bi bi-exclamation-octagon", endpoint="stok.olu_stok_analiz", parent=stok, sira=7)
    menu_ekle("AI Çapraz Satış", "bi bi-cart-plus", endpoint="stok.capraz_satis_analizi", parent=stok, sira=8)

    # 6.CARİ
    cari = menu_ekle("Cari", "bi bi-people", sira=6)
    menu_ekle("Cari Listesi", "bi bi-person-lines-fill", endpoint="cari.index", parent=cari, sira=1)
    menu_ekle("Yeni Cari Kart", "bi bi-person-plus", endpoint="cari.ekle", parent=cari, sira=2)
    menu_ekle("AI Risk Analizi", "bi bi-activity", endpoint="cari.risk_analizi", parent=cari, sira=3)

    # 7.RAPORLAR
    rapor=menu_ekle("Rapor", "bi bi-tags-fill", endpoint="rapor.index", sira=7)

    # 8.TANIMLAR
    tanimlar = menu_ekle("Tanımlar", "bi bi-gear", sira=8)
    menu_ekle("Muhasebe Grupları", "bi bi-journals", endpoint="stok.muhasebe_gruplari", parent=tanimlar, sira=1)
    menu_ekle("KDV Grupları", "bi bi-percent", endpoint="stok.kdv_gruplari", parent=tanimlar, sira=2)
    menu_ekle("Şehirler (İller)", "bi bi-geo-alt", endpoint="lokasyon.sehir_listesi", parent=tanimlar, sira=3)
    menu_ekle("İlçeler", "bi bi-map", endpoint="lokasyon.ilce_listesi", parent=tanimlar, sira=4)

    # 9.SİSTEM (Sadece Admin)
    sistem = menu_ekle("Sistem", "bi bi-gear-fill", roller="admin", sira=9)
    menu_ekle("Firma Bilgileri", "bi bi-building", endpoint="firmalar.index", parent=sistem, sira=1)
    menu_ekle("Dönem Yönetimi", "bi bi-calendar-range", endpoint="firmalar.donemler", parent=sistem, sira=2)
    menu_ekle("Bölge Yönetimi", "bi bi-shop", endpoint="bolge.index", parent=sistem, sira=3)
    menu_ekle("Şube Yönetimi", "bi bi-shop", endpoint="sube.index", parent=sistem, sira=4)    
    menu_ekle("Kullanıcılar", "bi bi-person-badge", endpoint="kullanici.index", parent=sistem, sira=5)
    menu_ekle("Mobil Satış", "bi bi-phone", endpoint="mobile.dashboard", parent=sistem, sira=6)
    menu_ekle("AI Anomali Dedektifi", "bi bi-incognito", endpoint="rapor.anomali_dedektifi", parent=sistem, sira=7)
    
    # 🌟 KENDİSİNİ DE EKLEYELİM (Menü Yönetimi)
    menu_ekle("Menü Yönetimi", "bi bi-list", endpoint="sistem.menu_index", parent=sistem, sira=8)

    print("✅ Tüm menüler başarıyla veritabanına aktarıldı!")