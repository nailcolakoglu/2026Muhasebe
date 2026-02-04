from enum import Enum
from flask_babel import lazy_gettext as _l

# --- ORTAK ATA SINIF ---
class BaseEnum(str, Enum):
    """
    Tüm string tabanlı Enum'lar için temel sınıf.
    choices() ve __str__() metodlarını otomatik sağlar.
    """
    @classmethod
    def choices(cls):
        # Formlarda (SelectBox) kullanmak için [(value, label)] formatında liste döner
        # Label kısmı Babel ile çevrilebilir (_l)
        return [(e.value, _l(e.value)) for e in cls]

    def __str__(self):
        return str(self.value)

class MuhasebeFisTuru(BaseEnum):
    ACILIS = 'acilis'
    TAHSIL = 'tahsil'
    TEDIYE = 'tediye'
    MAHSUP = 'mahsup'
    KAPANIS = 'kapanis'

class KDVGrubu(BaseEnum):
    # Veritabanında Integer (1, 10, 20) saklamak matematiksel işlemler için daha güvenlidir.
    # Ancak Enum yapısı String tabanlı ise value'yu string yaparız.
    # Senin modelinde Integer kullandığın için burayı Integer Enum yapıyoruz:
    
    SIFIR = '0'
    BIR = '1'
    ON = '10'
    YIRMI = '20'
    
    # Not: Eğer hesaplamalarda direkt sayı kullanacaksak int(e.value) dönüşümü yaparız.

class FaturaTuru(BaseEnum):
    ALIS = 'alis'
    SATIS = 'satis'
    ALIS_IADE = 'alis_iade'
    SATIS_IADE = 'satis_iade'

class StokFisTuru(BaseEnum):
    TRANSFER = 'transfer'
    FIRE = 'fire'
    SARF = 'sarf'
    SAYIM_EKSIK = 'sayim_eksik'
    SAYIM_FAZLA = 'sayim_fazla'
    DEVIR = 'devir'
    URETIM = 'uretim'
    URETIM_CIKIS = 'uretim_cikis'
    SATIS_CIKIS ='satis_cikis'
    ALIS_GIRIS ='alis_giris'

class StokKartTipi(BaseEnum):
    STANDART = 'standart'  # Fiziksel, depoda duran ürün
    HIZMET = 'hizmet'      # Danışmanlık, kargo, işçilik (Stok düşmez)
    PAKET = 'paket'        # İçinde birden fazla ürün olan kampanya kolisi
    MAMUL = 'mamul'
    YARIMAMUL = 'yari_mamul'
    HAMMADDE = 'hammadde'

class HareketTuru(BaseEnum):
    # --- TEMEL ---
    DEVIR = 'devir'               # Dönem başı açılış (Giriş)
    TRANSFER = 'transfer'         # Depolar arası transfer (Giriş/Çıkış)

    # 👇 EKLENECEK SATIRLAR 👇
    SATIS_IRSALIYESI = "Satış İrsaliyesi"
    ALIS_IRSALIYESI = "Alış İrsaliyesi"
    SATIS_IRSALIYESI_IADE = "Satış İrsaliyesi İade"
    ALIS_IRSALIYESI_IADE = "Alış İrsaliyesi İade"

    # --- FATURA KAYNAKLI ---
    ALIS = 'alis'                 # Satın alma faturası (Giriş)
    SATIS = 'satis'               # Satış faturası (Çıkış)
    ALIS_IADE = 'alis_iade'       # Aldığımız malı iade ettik (Çıkış)
    SATIS_IADE = 'satis_iade'     # Müşteri malı iade etti (Giriş)

    # --- FİŞ / İÇ İŞLEMLER ---
    URETIM = 'uretim'             # Üretimden mamul girişi (Giriş)
    URETIM_CIKIS = 'uretim_cikis' # Üretime hammadde çıkışı (Çıkış)
    SARF = 'sarf'                 # İşletme içi tüketim/masraf (Çıkış)
    FIRE = 'fire'                 # Hasar, bozulma, kayıp (Çıkış)
    SAYIM_FAZLA = 'sayim_fazla'   # Sayım sonucu stok artışı (Giriş)
    SAYIM_EKSIK = 'sayim_eksik'   # Sayım sonucu stok azalışı (Çıkış)
    GIRIS = 'giris'               # Genel Giriş (Gerekirse)
    CIKIS = 'cikis'               # Genel Çıkış (Gerekirse)

class IslemDurumu(BaseEnum):
    BEKLIYOR = 'bekliyor'
    ONAYLANDI = 'onaylandi'
    IPTAL = 'iptal'

class FinansIslemTuru(BaseEnum):
    TAHSILAT = 'tahsilat'
    TEDIYE = 'tediye'

class BankaIslemTuru(BaseEnum):
    # Para Girişleri (+)
    TAHSILAT = 'tahsilat'       # Cari veya Bankadan giriş
    VIRMAN_GIRIS = 'virman_giris' # Başka kasadan gelen para

    # 👇 YENİ EKLENEN
    POS_TAHSILAT = 'pos_tahsilat' # Kredi Kartı / POS Cihazı ile Tahsilat

    # Para Çıkışları (-)
    TEDIYE = 'tediye'           # Cari veya Bankaya çıkış
    VIRMAN_CIKIS = 'virman_cikis' # Başka kasaya giden para

class SiparisDurumu(BaseEnum):
    BEKLIYOR = 'bekliyor'
    ONAYLANDI = 'onaylandi'
    FATURALANDI = 'faturalandi'
    TAMAMLANDI = 'tamamlandi'
    KISMI = 'kismi'
    IPTAL = 'iptal'

class EtkilesimTuru(BaseEnum):
    ARAMA = 'arama'
    ZIYARET = 'ziyaret'
    TOPLANTI = 'toplanti'
    EMAIL = 'email'
    SIKAYET = 'sikayet'   

class ParaBirimi(BaseEnum):
    # Format: (Kod, Görünecek İsim) mantığıyla değil, 
    # veritabanında "TL", "USD" gibi kısa kodlar tutmak en sağlıklısıdır.
    # Etiketleri Form tarafında halledeceğiz.
    TL = "TL"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP" # Örnek: Sterlin'i de ekledik
    CHF = "CHF" # Örnek: İsviçre Frangı

class OdemeDurumu(BaseEnum):
    ODENDI = 'odendi'
    KISMEN = 'kismen'
    BEKLIYOR = 'bekliyor'

class CekDurumu(BaseEnum):
    PORTFOYDE = 'portfoyde'
    TEMINATA_VERILDI = 'teminata_verildi'
    TAHSILE_VERILDI = 'tahsile_verildi'
    TEMLIK_EDILDI = 'temlik_edildi'
    PROTESTOLU = 'protestolu'
    KARSILIKSIZ = 'karsiliksiz' # Önemli bir durum
    TAHSIL_EDILDI = 'tahsil_edildi'
    IADE_EDILDI = 'iade_edildi'

class PortfoyTipi(BaseEnum):
    ALINAN = 'alinan'   # Müşteri Çeki
    VERILEN = 'verilen' # Kendi Çekimiz

class RiskSeviyesi(BaseEnum):
    DUSUK = 'dusuk'
    ORTA = 'orta'
    YUKSEK = 'yuksek'
    KRITIK = 'kritik'

class VadeGrubu(BaseEnum):
    GECIKMIS = 'gecikmis'
    ACIL = 'acil' # 0-7 gün
    YAKIN = 'yakin' # 8-30 gün
    ORTA = 'orta' # 31-90 gün
    UZUN = 'uzun' # 90+ gün

class CekIslemTuru(BaseEnum):
    # Alınan Çek İşlemleri
    TAHSIL_KASA = 'tahsil_kasa'     # Elden Tahsilat
    TAHSIL_BANKA = 'tahsil_banka'   # Bankadan Tahsilat
    CIRO = 'ciro'                   # Ciro Etme (Tedarikçiye Verme)
    KARSILIKSIZ = 'karsiliksiz'     # Karşılıksız Çıkması
    IADE_ALINAN = 'iade_alinan'     # Müşteriye İade (Portföyden Çıkış)

    # Verilen Çek İşlemleri
    ODENDI_KASA = 'odendi_kasa'     # Kasadan Ödeme
    ODENDI_BANKA = 'odendi_banka'   # Bankadan Ödeme
    IADE_VERILEN = 'iade_verilen'   # Tedarikçiden Geri Alma

class CekKonumu(BaseEnum):
    KASADA = 'kasada'                   # Fiziksel olarak kasamızda
    BANKADA_TAHSILDE = 'bankada_tahsilde' # Tahsil için bankaya verildi
    BANKADA_TEMINATTA = 'bankada_teminatta' # Kredi karşılığı teminata verildi
    MUSTERIDE = 'musteride'             # Ciro edildi (Borca karşılık verildi)
    AVUKATTA = 'avukatta'               # Hukuki süreçte
    IADE_EDILDI = 'iade_edildi'         # Sahibine geri verildi

class CariIslemTuru(BaseEnum):
    # --- FATURA İŞLEMLERİ ---
    DEVIR = 'devir'                 # Dönem başı açılış bakiyesi
    SATIS_FATURASI = 'satis_fatura' # Biz sattık (Cari Borçlanır)
    ALIS_FATURASI = 'alis_fatura'   # Biz aldık (Cari Alacaklanır)
    SATIS_IADE = 'satis_iade'       # Müşteri iade etti (Cari Alacaklanır)
    ALIS_IADE = 'alis_iade'         # Biz iade ettik (Cari Borçlanır)

    # --- EKLENEN FİNANSAL İŞLEMLER ---
    TAHSILAT = 'tahsilat'           # Para Girişi (Kasa/Banka) -> Cari Alacaklanır
    TEDIYE = 'tediye'               # Para Çıkışı (Kasa/Banka) -> Cari Borçlanır
    
    BANKA_ISLEM = 'banka_islem'     # Genel Banka Havale/EFT
    KASA_ISLEM = 'kasa_islem'       # Genel Kasa Hareketi
    
    # --- FİNANS İŞLEMLERİ ---
    TAHSILAT_NAKIT = 'tahsilat_nakit' # Kasaya para girdi (Alacaklandır)
    TEDIYE_NAKIT = 'tediye_nakit'     # Kasadan ödeme yaptık (Borçlandır)
    HAVALE_GELEN = 'havale_gelen'     # Bankaya para geldi (Alacaklandır)
    HAVALE_GIDEN = 'havale_giden'     # Bankadan para çıktı (Borçlandır)
    
    # --- ÇEK / SENET ---
    CEK_GIRIS = 'cek_giris'         # Müşteri çek verdi (Alacaklandır)
    CEK_CIKIS = 'cek_cikis'         # Ciro ettik veya kendi çekimiz (Borçlandır)
    SENET_GIRIS = 'senet_giris'
    SENET_CIKIS = 'senet_cikis'
    
    # --- DİĞER ---
    VIRMAN = 'virman'               # Cari'den Cari'ye transfer
    KUR_FARKI = 'kur_farki'         # Döviz değerlemesi

class FaturaDurumu(BaseEnum):
    TASLAK = 'taslak'           # Düzenleniyor, stok/cari etkilenmez
    ONAYLANDI = 'onaylandi'     # Muhasebeleşti, stok/cari işlendi
    IPTAL = 'iptal'             # İptal edildi (Stok/Cari ters kayıt)
    GONDERILDI = 'gonderildi'   # E-Fatura olarak GİB'e gitti

class CekSonucDurumu(BaseEnum):
    NORMAL = 'normal'           # Vadesinde veya öncesinde ödendi
    GECIKMELI = 'gecikmeli'     # Vadesi geçti ama sonunda tahsil edildi
    KARSILIKSIZ = 'karsiliksiz' # Ödenmedi, yasal takip veya şüpheli
    IPTAL = 'iptal'             # Çek iade edildi veya işlem iptal
    BEKLIYOR = 'bekliyor'       # Henüz vadesi gelmedi veya sonuçlanmadı

class DuyguDurumu(BaseEnum):
    POZITIF = 'pozitif'     # Müşteri memnun, satış ihtimali yüksek
    NEGATIF = 'negatif'     # Müşteri şikayetçi veya kızgın
    NOTR = 'notr'           # Standart bilgilendirme, duygu yok
    BELIRSIZ = 'belirsiz'   # AI henüz analiz etmedi

class CariTipi(BaseEnum):
    BIREYSEL = 'bireysel'   # Şahıs (TCKN ile işlem yapan)
    KURUMSAL = 'kurumsal'   # Limited/Anonim Şirket (VKN ile işlem yapan)
    BAYI = 'bayi'           # Bayimiz olan cariler
    DIGER = 'diger'         # Diğer türler

class EFaturaSenaryo(BaseEnum):
    # GİB Standart Kodları (ProfileID)
    TEMELFATURA = 'TEMELFATURA'   # Reddedilemez (Sadece KEP/Noter ile itiraz edilir)
    TICARIFATURA = 'TICARIFATURA' # 8 gün içinde Kabul/Ret yanıtı verilebilir
    KAMU = 'KAMU'                 # Kamu kurumlarına kesilen faturalar
    IHRACAT = 'IHRACAT'           # Gümrük çıkışlı ihracat faturaları
    YOLCUBERABERFATURA = 'YOLCUBERABERFATURA' # Tax-Free (Yolcu beraberinde eşya)
    HAL = 'HAL'                   # Hal Kayıt Sistemi kapsamındaki faturalar
    EARSIVFATURA = 'EARSIVFATURA' # E-Fatura mükellefi olmayanlara kesilen (Bazen senaryo olarak kullanılır)
    TEMELIRSALIYE = "TEMELIRSALIYE" # E-İrsaliye için kritik

class EFaturaTipi(BaseEnum):
    # GİB Standart Kodları (InvoiceTypeCode)
    SATIS = 'SATIS'               # Normal Mal/Hizmet Satışı
    IADE = 'IADE'                 # İade Faturası
    TEVKIFAT = 'TEVKIFAT'         # KDV Tevkifatlı Fatura
    ISTISNA = 'ISTISNA'           # KDV'den İstisna (0 KDV) Fatura (İhracat vb.)
    OZELMATRAH = 'OZELMATRAH'     # Özel Matrah (Konut, Külçe Altın vb.)
    IHRACOVIT = 'IHRACOVIT'       # İhraç Kayıtlı Satış
    SGK = 'SGK'                   # SGK'ya kesilen faturalar (Eczane, Hastane vb.)
    SEVK = 'SEVK'                   # SGK'ya kesilen faturalar (Eczane, Hastane vb.)

class HesapSinifi(BaseEnum):
    ANA_HESAP = 'ana'       # Kebir (100, 120, 600) - İşlem görmez, toplam tutar
    GRUP_HESABI = 'grup'    # Tali (120.01) - İşlem görmez, alt kırılımı vardır
    MUAVIN_HESAP = 'muavin' # Alt Hesap (120.01.001) - Fişler buraya işlenir

class BakiyeTuru(BaseEnum):
    BORC = 'borc'           # Sadece Borç Bakiyesi verebilir (Aktif Karakterli)
    ALACAK = 'alacak'       # Sadece Alacak Bakiyesi verebilir (Pasif Karakterli)
    HER_IKISI = 'her_ikisi' # Cari hesaplar gibi hem borç hem alacak verebilir

class OzelHesapTipi(BaseEnum):
    STANDART = 'standart'   # Normal hesap
    KASA = 'kasa'           # Kasa modülü ile entegre
    BANKA = 'banka'         # Banka modülü ile entegre
    CEK = 'cek'             # Çek/Senet modülü
    ALIS_KDV = 'alis_kdv'   # 191
    SATIS_KDV = 'satis_kdv' # 391
    IADE_KDV = 'iade_kdv'   
    TEVKIFAT = 'tevkifat'   # 360

class BelgeTuru(BaseEnum):
    """
    e-Defter (GİB) Standart Belge Türleri
    XML oluşturulurken bu değerler (invoice, check...) kullanılır.
    """
    FATURA = 'invoice'
    CEK = 'check'
    MAKBUZ = 'receipt'
    SENET = 'voucher'
    DIGER = 'other'
    # Navlun, Yolcu Bileti vb.gerekirse eklenebilir ama temel set budur.

class OdemeYontemi(BaseEnum):
    """
    e-Defter Ödeme Yöntemleri
    Özellikle Kasa (100) ve Banka (102) fişlerinde zorunludur.
    """
    NAKIT = 'KASA'
    BANKA = 'BANKA' # Havale / EFT
    CEK = 'CEK'
    SENET = 'SENET'
    KREDI_KARTI = 'KREDI_KARTI'
    POSTA = 'POSTA' # PTT vb.

class BankaHesapTuru(BaseEnum):
    VADESIZ = 'vadesiz'       # Normal Mevduat (Kullanılabilir Nakit)
    VADELI = 'vadeli'         # Vadeli Mevduat (Yatırım)
    KREDI = 'kredi'           # Kredi Hesabı (Eksi Bakiye)
    KREDI_KARTI = 'kredi_karti' # Şirket Kredi Kartı
    POS = 'pos'               # POS Cihazı Bağlı Hesap (Bloke)

class TurkiyeBankalari(BaseEnum):
    # Kamu
    ZIRAAT = "T.C.Ziraat Bankası A.Ş."
    HALK = "Türkiye Halk Bankası A.Ş."
    VAKIF = "Türkiye Vakıflar Bankası T.A.O."
    
    # Özel
    IS_BANKASI = "Türkiye İş Bankası A.Ş."
    GARANTI = "Garanti BBVA"
    AKBANK = "Akbank T.A.Ş."
    YAPI_KREDI = "Yapı ve Kredi Bankası A.Ş."
    QNB = "QNB Finansbank A.Ş."
    DENIZ = "Denizbank A.Ş."
    TEB = "Türk Ekonomi Bankası A.Ş."
    SEKER = "Şekerbank T.A.Ş."
    
    # Katılım
    KUVEYT = "Kuveyt Türk Katılım Bankası A.Ş."
    TURKIYE_FINANS = "Türkiye Finans Katılım Bankası A.Ş."
    ALBARAKA = "Albaraka Türk Katılım Bankası A.Ş."
    VAKIF_KATILIM = "Vakıf Katılım Bankası A.Ş."
    ZIRAAT_KATILIM = "Ziraat Katılım Bankası A.Ş."
    
    # Diğer
    ODEA = "Odea Bank A.Ş."
    FIBABANKA = "Fibabanka A.Ş."
    ING = "ING Bank A.Ş."
    HSBC = "HSBC Bank A.Ş."
    DIGER = "Diğer Banka"
    ENPARA = "ENPARA A.Ş."

class StokBirimleri(BaseEnum): 
    ADET = 'Adet'
    KG = 'Kg'
    LT = 'Lt'
    MT = 'Mt'
    KUTU = 'Kutu'
    PAKET = 'Paket'
    SET = 'Set'
    TON = 'Ton'
    M2 = 'm²'
    M3 = 'm³'
    HIZMET = 'Hizmet'         

class IrsaliyeTuru(BaseEnum):
    SEVK = "Sevk İrsaliyesi"
    TASIMA = "Taşıma İrsaliyesi"
    IADE = "İade İrsaliyesi"
    DAHILI_SEVK = "Dahili Sevk (Depolar Arası)"

class IrsaliyeDurumu(BaseEnum):
    TASLAK = "Taslak"
    ONAYLANDI = "Onaylandı"         # Stoktan düştü / stoğa girdi
    GIB_GONDERILDI = "GİB'e Gönderildi" # E-İrsaliye süreci
    GIB_ONAYLANDI = "GİB Onayladı"      # Karşı taraf kabul etti
    GIB_REDDEDILDI = "GİB Reddetti"     # Karşı taraf reddetti
    IPTAL = "İptal"
    FATURALASTI = "Faturalaştı"     # Artık faturaya dönüştü

    def __str__(self):
        return self.value