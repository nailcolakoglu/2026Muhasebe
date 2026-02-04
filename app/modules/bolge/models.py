# modules/bolge/models.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (Numeric, func, ForeignKey, cast, case, Text, UniqueConstraint, event, Index,  
                    select, Integer, Enum as PgEnum)
from app.extensions import db
from app.models.base import FirmaFilteredQuery, TimestampMixin, SoftDeleteMixin
# UUID oluşturucu fonksiyon
import uuid # 👈 EKLENDİ

def generate_uuid():
    return str(uuid.uuid4())

class Bolge(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'bolgeler'
    query_class = FirmaFilteredQuery 

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firma_id = db.Column(db.String(36), db.ForeignKey('firmalar.id'), nullable=False)
    
    kod = db.Column(db.String(20), nullable=False)
    ad = db.Column(db.String(100), nullable=False)
    
    # 🚨 DÜZELTME: Yönetici ID artık String(36) UUID formatındadır.
    yonetici_id = db.Column(db.String(36), db.ForeignKey('kullanicilar.id'), nullable=True)
    
    aciklama = db.Column(db.String(255))
    aktif = db.Column(db.Boolean, default=True)

    # İLİŞKİLER
    firma = db.relationship('Firma', backref='bolgeler')
    
    # Yönetici İlişkisi
    yonetici = db.relationship('Kullanici', foreign_keys=[yonetici_id])
    
    # Şubeler
    subeler = db.relationship('Sube', backref='bolge', lazy='dynamic')

    def __repr__(self):
        return f"<Bolge {self.ad}>"



# =============================================================================
# 4.BAŞLANGIÇ VERİLERİ (INIT DATA)
# =============================================================================
def init_default_data():
    """
    Sistemin İlk Kurulum Verilerini Yükler
    """
    from app.enums import HesapSinifi, BakiyeTuru, OzelHesapTipi 
    from app.modules.sehir.models import Sehir
    from app.modules.firma.models import Firma, Donem
    
    
    print("🚀 Varsayılan veriler kontrol ediliyor...")
    
    try:
        # 0.Şehirleri Yükle
        if not Sehir.query.first():
            print("⏳ Şehirler yükleniyor...")
            iller = {
                '01': 'ADANA', '02': 'ADIYAMAN', '03': 'AFYONKARAHİSAR', '04': 'AĞRI', '05': 'AMASYA',
                '06': 'ANKARA', '07': 'ANTALYA', '08': 'ARTVİN', '09': 'AYDIN', '10': 'BALIKESİR',
                '11': 'BİLECİK', '12': 'BİNGÖL', '13': 'BİTLİS', '14': 'BOLU', '15': 'BURDUR',
                '16': 'BURSA', '17': 'ÇANAKKALE', '18': 'ÇANKIRI', '19': 'ÇORUM', '20': 'DENİZLİ',
                '21': 'DİYARBAKIR', '22': 'EDİRNE', '23': 'ELAZIĞ', '24': 'ERZİNCAN', '25': 'ERZURUM',
                '26': 'ESKİŞEHİR', '27': 'GAZİANTEP', '28': 'GİRESUN', '29': 'GÜMÜŞHANE', '30': 'HAKKARİ',
                '31': 'HATAY', '32': 'ISPARTA', '33': 'MERSİN', '34': 'İSTANBUL', '35': 'İZMİR',
                '36': 'KARS', '37': 'KASTAMONU', '38': 'KAYSERİ', '39': 'KIRKLARELİ', '40': 'KIRŞEHİR',
                '41': 'KOCAELİ', '42': 'KONYA', '43': 'KÜTAHYA', '44': 'MALATYA', '45': 'MANİSA',
                '46': 'KAHRAMANMARAŞ', '47': 'MARDİN', '48': 'MUĞLA', '49': 'MUŞ', '50': 'NEVŞEHİR',
                '51': 'NİĞDE', '52': 'ORDU', '53': 'RİZE', '54': 'SAKARYA', '55': 'SAMSUN',
                '56': 'SİİRT', '57': 'SİNOP', '58': 'SİVAS', '59': 'TEKİRDAĞ', '60': 'TOKAT',
                '61': 'TRABZON', '62': 'TUNCELİ', '63': 'ŞANLIURFA', '64': 'UŞAK', '65': 'VAN',
                '66': 'YOZGAT', '67': 'ZONGULDAK', '68': 'AKSARAY', '69': 'BAYBURT', '70': 'KARAMAN',
                '71': 'KIRIKKALE', '72': 'BATMAN', '73': 'ŞIRNAK', '74': 'BARTIN', '75': 'ARDAHAN',
                '76': 'IĞDIR', '77': 'YALOVA', '78': 'KARABÜK', '79': 'KİLİS', '80': 'OSMANİYE', '81': 'DÜZCE'
            }
            
            for kod, ad in iller.items():
                yeni_il = Sehir(kod=kod, ad=ad)
                db.session.add(yeni_il)
                
                # Örnek İlçeler
                if kod == '34': 
                    for ilce_ad in ['KADIKÖY', 'BEŞİKTAŞ', 'ŞİŞLİ', 'ÜMRANİYE', 'FATİH']:
                        db.session.add(Ilce(sehir=yeni_il, ad=ilce_ad))
                elif kod == '35': 
                    for ilce_ad in ['KONAK', 'KARŞIYAKA', 'BORNOVA', 'BUCA', 'MENEMEN']:
                        db.session.add(Ilce(sehir=yeni_il, ad=ilce_ad))
                elif kod == '06': 
                    for ilce_ad in ['ÇANKAYA', 'KEÇİÖREN', 'YENİMAHALLE']:
                        db.session.add(Ilce(sehir=yeni_il, ad=ilce_ad))
                        
            db.session.commit()
            print("   + 81 İl ve Örnek İlçeler yüklendi.")

        # 1.Firma Tanımla
        if not Firma.query.first():
            firma = Firma(kod="Frm-01", unvan="Merkez Firma A.Ş.", vergi_no="1111111111", adres="Merkez")
            db.session.add(firma)
            db.session.commit()
            
            izmir = Sehir.query.filter_by(kod='35').first()
            sube = Sube(firma_id=firma.id, kod="MRK", ad="Merkez Şube", sehir_id=izmir.id if izmir else None)
            db.session.add(sube)
            db.session.commit()
        
        firma = Firma.query.first() 
        sube = Sube.query.first()

        # 2.Mali Dönem
        if not Donem.query.first():
            donem = Donem(firma_id=firma.id, ad=f"{datetime.now().year} Yılı", 
                          baslangic=datetime(datetime.now().year, 1, 1), 
                          bitis=datetime(datetime.now().year, 12, 31),
                          aktif=True)
            db.session.add(donem)
            db.session.commit()

        # 3.PROFESYONEL HESAP PLANI (TDHP)
        if not HesapPlani.query.first():
            print("   ⏳ Hesap Planı oluşturuluyor...")
            ana_hesaplar = [
                ("100", "KASA HESABI", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.STANDART),
                ("102", "BANKALAR", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.STANDART),
                ("120", "ALICILAR", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.STANDART),
                ("153", "TİCARİ MALLAR", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.STANDART),
                ("191", "İNDİRİLECEK KDV", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.ALIS_KDV),
                ("320", "SATICILAR", HesapSinifi.ANA_HESAP, BakiyeTuru.ALACAK, OzelHesapTipi.STANDART),
                ("391", "HESAPLANAN KDV", HesapSinifi.ANA_HESAP, BakiyeTuru.ALACAK, OzelHesapTipi.SATIS_KDV),
                ("600", "YURT İÇİ SATIŞLAR", HesapSinifi.ANA_HESAP, BakiyeTuru.ALACAK, OzelHesapTipi.STANDART),
                ("610", "SATIŞTAN İADELER", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.STANDART),
                ("621", "SATILAN MALIN MALİYETİ", HesapSinifi.ANA_HESAP, BakiyeTuru.BORC, OzelHesapTipi.STANDART)
            ]
            created_parents = {}
            for kod, ad, tip, bakiye, ozel in ana_hesaplar:
                hesap = HesapPlani(firma_id=firma.id, kod=kod, ad=ad, hesap_tipi=tip, bakiye_turu=bakiye, ozel_hesap_tipi=ozel, seviye=1)
                db.session.add(hesap)
                created_parents[kod] = hesap 
            db.session.flush() 

            muavinler = [
                ("100.01", "MERKEZ TL KASA", "100", OzelHesapTipi.KASA),
                ("120.35", "İZMİR MÜŞTERİLER HESABI", "120", OzelHesapTipi.STANDART),   
                ("120.35.001", "NAİL ÇOLAKOĞLU", "120.35", OzelHesapTipi.STANDART),   
                ("153.01", "GIDA ÜRÜNLERİ STOK", "153", OzelHesapTipi.STANDART), 
                ("191.01", "İNDİRİLECEK KDV %1", "191", OzelHesapTipi.ALIS_KDV),
                ("191.10", "İNDİRİLECEK KDV %10", "191", OzelHesapTipi.ALIS_KDV),
                ("191.20", "İNDİRİLECEK KDV %20", "191", OzelHesapTipi.ALIS_KDV),
                ("320.35", "İZMİR SATICILAR HESABI", "320", OzelHesapTipi.STANDART),
                ("320.35.001", "NAİL ÇOLAKOĞLU", "320.35", OzelHesapTipi.STANDART),
                ("391.01", "HESAPLANAN KDV %1", "391", OzelHesapTipi.SATIS_KDV),
                ("391.10", "HESAPLANAN KDV %10", "391", OzelHesapTipi.SATIS_KDV),
                ("391.20", "HESAPLANAN KDV %20", "391", OzelHesapTipi.SATIS_KDV),
                ("600.01", "GIDA SATIŞLARI", "600", OzelHesapTipi.STANDART),
                ("610.01", "GIDA İADELERİ", "610", OzelHesapTipi.STANDART)
            ]
            
            for kod, ad, ust_kod, ozel in muavinler:
                ust = created_parents.get(ust_kod)
                if ust:
                    alt_hesap = HesapPlani(firma_id=firma.id, kod=kod, ad=ad, hesap_tipi=HesapSinifi.MUAVIN_HESAP, bakiye_turu=ust.bakiye_turu, ozel_hesap_tipi=ozel, ust_hesap_id=ust.id, seviye=2)
                    db.session.add(alt_hesap)
            db.session.commit()

        # 4.Admin Kullanıcısı
        if not Kullanici.query.filter_by(kullanici_adi="admin").first():
            admin = Kullanici(kullanici_adi="admin", ad_soyad="Sistem Yöneticisi", rol="admin", firma_id=firma.id)
            admin.set_sifre("admin123")
            admin.yetkili_subeler.append(sube)
            db.session.add(admin)
            db.session.commit()

        # 5.SAYAÇLAR (Belge Numaralama)
        if not Sayac.query.first():
            print("   ⏳ Belge sayaçları tanımlanıyor...")
            sayaclar = [('FATURA', 'FAT-'), ('MAHSUP', 'M-'), ('TAHSIL', 'T-'), ('TEDIYE', 'TD-'), ('ACILIS', 'ACL-')]
            yil = datetime.now().year
            for kod, on_ek in sayaclar:
                db.session.add(Sayac(firma_id=firma.id, donem_yili=yil, kod=kod, on_ek=on_ek, son_no=0))
            db.session.commit()

        # 6.Temel Modüller
        if not Kasa.query.first():
            muh_kasa = HesapPlani.query.filter_by(kod="100.01").first()
            kasa = Kasa(firma_id=firma.id, sube_id=sube.id, kod="01", ad="Merkez Kasa", muhasebe_hesap_id=muh_kasa.id if muh_kasa else None)
            db.session.add(kasa)

        if not Depo.query.first():
            db.session.add(Depo(firma_id=firma.id, sube_id=sube.id, kod="Dp-001", ad="Merkez Depo"))

        if not StokKategori.query.first():
            db.session.add(StokKategori(firma_id=firma.id, ad="GIDA"))

        if not StokMuhasebeGrubu.query.first():
            # Hesapları Bul
            h153 = HesapPlani.query.filter_by(kod="153.01").first()
            h600 = HesapPlani.query.filter_by(kod="600.01").first()
            h610 = HesapPlani.query.filter_by(kod="610.01").first()
            
            stok_grp = StokMuhasebeGrubu(
                firma_id=firma.id,
                kod="GIDA_GRP",
                ad="Gıda Grubu Entegrasyonu",
                alis_hesap_id=h153.id if h153 else None,
                satis_hesap_id=h600.id if h600 else None,
                alis_iade_hesap_id=h153.id if h153 else None, # İadede stoktan düşer (Alacak)
                satis_iade_hesap_id=h610.id if h610 else None
            )
            db.session.add(stok_grp)
            db.session.commit()

        if not StokKDVGrubu.query.first():
            # KDV Hesaplarını Bul
            h191_10 = HesapPlani.query.filter_by(kod="191.10").first()
            h391_10 = HesapPlani.query.filter_by(kod="391.10").first()
            
            kdv_grp = StokKDVGrubu(
                firma_id=firma.id,
                kod="KDV_10",
                ad="Gıda KDV (%10)",
                alis_kdv_orani=10,
                satis_kdv_orani=10,
                alis_kdv_hesap_id=h191_10.id if h191_10 else None,
                satis_kdv_hesap_id=h391_10.id if h391_10 else None
            )
            db.session.add(kdv_grp)
            db.session.commit()

        # 7.Cari ve Stok (Güncellenmiş)
        if not CariHesap.query.first():
            h_alici = HesapPlani.query.filter_by(kod="120.35.001").first()
            h_satici = HesapPlani.query.filter_by(kod="320.35.001").first()
            
            cari = CariHesap(
                firma_id=firma.id, 
                kod="CR-001", 
                unvan="Nail Çolakoğlu", 
                alis_muhasebe_hesap_id=h_satici.id if h_satici else None, 
                satis_muhasebe_hesap_id=h_alici.id if h_alici else None
            )
            db.session.add(cari)
            db.session.commit()

        if not StokKart.query.first():
            # Oluşturduğumuz grupları stoğa bağla
            grp_muh = StokMuhasebeGrubu.query.first()
            grp_kdv = StokKDVGrubu.query.first()
            gida_kat = StokKategori.query.first()

            stok = StokKart(
                firma_id=firma.id, 
                kod="STK-001", 
                ad="Tam Buğday Ekmeği",
                alis_fiyati=15.00,
                satis_fiyati=25.00,
                kategori_id=gida_kat.id if gida_kat else 1,
                muhasebe_kod_id=grp_muh.id if grp_muh else None,
                kdv_kod_id=grp_kdv.id if grp_kdv else None
            )
            db.session.add(stok)
            db.session.commit()
        print(" + Örnek Stok (Gruplarıyla) eklendi.")
    
        if not OdemePlani.query.first():

            odeme = OdemePlani(
                firma_id=firma.id, 
                ad="PEŞİN", 
                gun_vadesi=0,
                aktif=True
            )
            db.session.add(odeme)
            db.session.commit()
        print(" + Örnek Ödeme Planı eklendi.")

        #db.session.flush()
        if not FiyatListesi.query.first():
            fiyat= FiyatListesi(
                    firma_id=firma.id,
                    kod='FYT-00', 
                    ad='YILBAŞI FİYAT LİSTESİ',
                    baslangic_tarihi= '2025-12-01',
                    bitis_tarihi= '2025-12-31',
                    aktif = True,
                    varsayilan = True, 
                    oncelik = 0,
                    aciklama = 'Yilbaşında Geçerli olacak Fiyat Tarifemiz.'
                )
            db.session.add(fiyat)
            db.session.commit()

            fiyatDetay1= FiyatListesiDetay(
                    fiyat_listesi_id=fiyat.id,
                    stok_id=stok.id, 
                    fiyat=100,
                    doviz='TL',
                    iskonto_orani=5,
                    min_miktar=5
                )  
            db.session.add(fiyatDetay1) 
            fiyatDetay2= FiyatListesiDetay(
                    fiyat_listesi_id=fiyat.id,
                    stok_id=stok.id, 
                    fiyat=100,
                    doviz='USD',
                    iskonto_orani=7,
                    min_miktar=7
                
                ) 
            db.session.add(fiyatDetay2)
 
        if not CariHesap.query.first():
            h_alici = HesapPlani.query.filter_by(firma_id=firma.id, kod="120.01").first()
            h_satici = HesapPlani.query.filter_by(firma_id=firma.id, kod="320.01").first()
            db.session.add(CariHesap(firma_id=firma.id, kod="CR-2025-0001", unvan="Nail Çolakoğlu", alis_muhasebe_hesap_id=h_satici.id if h_satici else None, satis_muhasebe_hesap_id=h_alici.id if h_alici else None))

        if not StokKart.query.first():
            stok = StokKart(firma_id=firma.id, kod="STK-2025-0001", ad="Ekmek")
            db.session.add(stok)
            print("   + Stok eklendi.")

        if not AIRaporAyarlari.query.first():
            varsayilanlar = [
                ('max_iskonto_orani', '20', 'Şüpheli İskonto Oranı (%)'),
                ('riskli_borc_limiti', '10000', 'Riskli Müşteri Borç Limiti (TL)'),
                ('olu_stok_ay_siniri', '6', 'Ölü Stok İçin Hareketsizlik Süresi (Ay)'),
                ('kritik_nakit_haftasi', '4', 'Nakit Akışı Tahmin Süresi (Hafta)')
            ]
            for k, v, desc in varsayilanlar:
                ayar = AIRaporAyarlari.query.filter_by(firma_id=firma.id, anahtar=k).first()
                if not ayar:
                    db.session.add(AIRaporAyarlari(firma_id=firma.id, anahtar=k, deger=v, aciklama=desc))
            print("✅ AI Ayarları yüklendi.")

        db.session.commit()
        print("✅ TÜM VERİLER YÜKLENDİ.")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Veri yükleme hatası: {e}")

