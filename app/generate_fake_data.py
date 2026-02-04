import uuid
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from app import create_app 
from models.base import db
from models import Firma, Sube, Donem, Depo, CariHesap, Fatura, FaturaKalemi
from modules.stok.models import StokKart  # ✅ DOĞRU IMPORT
from modules.kategori.models import StokKategori  # ✅ DOĞRU IMPORT
from enums import FaturaTuru

app = create_app()

def generate_data():
    with app.app_context():
        print("🚀 Fake Veri Üretimi Başlıyor...")

        try:
            # 1.TEMEL TANIMLARI AL
            firma = Firma.query.first()
            sube = Sube.query.filter_by(firma_id=firma.id).first()
            donem = Donem.query.filter_by(firma_id=firma.id, aktif=True).first()
            depo = Depo.query.filter_by(firma_id=firma.id).first()

            if not all([firma, sube, donem, depo]):
                print("❌ Hata: Sistemde Firma, Şube, Dönem veya Depo tanımlı değil.")
                return

            # 2.KATEGORİLER VE ÜRÜNLER
            kategoriler = {
                "Sıcak İçecekler": ["Salep", "Sıcak Çikolata", "Bitki Çayı", "Türk Kahvesi", "Filtre Kahve"],
                "Soğuk İçecekler":  ["Coca Cola", "Fanta", "Ice Tea", "Limonata", "Ayran", "Su"],
                "Tatlılar": ["Dondurma", "Magnolia", "Cheesecake", "Sufle"],
                "Atıştırmalık": ["Cips", "Kuruyemiş", "Tost", "Sandviç"]
            }

            db_stoklar = []
            
            print("📦 Stok Kartları Oluşturuluyor...")
            for kat_ad, urunler in kategoriler.items():
                kategori = StokKategori.query.filter_by(firma_id=firma.id, ad=kat_ad).first()
                if not kategori:
                    kategori = StokKategori(firma_id=firma.id, ad=kat_ad)
                    db.session.add(kategori)
                    db.session.flush()
                
                for urun_ad in urunler:
                    stok = StokKart.query.filter_by(firma_id=firma.id, ad=urun_ad).first()
                    if not stok: 
                        fiyat = Decimal(str(random.randint(20, 150)))
                        
                        stok = StokKart(
                            firma_id=firma.id,
                            kod=f"STK-{random.randint(1000,9999)}",
                            ad=urun_ad,
                            kategori_id=kategori.id,
                            alis_fiyati=fiyat * Decimal('0.7'),
                            satis_fiyati=fiyat,  # ✅ Artık çalışacak
                            kritik_seviye=10
                        )
                        db.session.add(stok)
                        db.session.flush()
                    db_stoklar.append(stok)
            
            # 3.CARİ HESAPLAR
            print("👥 Cari Hesaplar Oluşturuluyor...")
            cari_isimleri = ["Ahmet Yılmaz", "Mehmet Demir", "Ayşe Kaya", "Yıldız Cafe", "Mavi Market", "Sahil Büfe", "Otel Grand"]
            db_cariler = []
            for isim in cari_isimleri:
                cari = CariHesap.query.filter_by(firma_id=firma.id, unvan=isim).first()
                if not cari:
                    cari = CariHesap(
                        firma_id=firma.id,
                        kod=f"C-{random.randint(100,999)}",
                        unvan=isim
                    )
                    db.session.add(cari)
                    db.session.flush()
                db_cariler.append(cari)

            db.session.commit()

            # 4.FATURALAR
            print("📅 Faturalar Oluşturuluyor...")
            
            baslangic_tarihi = datetime.now() - timedelta(days=365)
            
            for i in range(365):
                islem_tarihi = baslangic_tarihi + timedelta(days=i)
                ay = islem_tarihi.month
                
                gunluk_fatura_sayisi = random.randint(1, 5)
                
                for gun_sirasi in range(gunluk_fatura_sayisi):
                    cari = random.choice(db_cariler)
                    
                    timestamp = int(time.time() * 1000000) + gun_sirasi
                    belge_no = f"FTR-{islem_tarihi.strftime('%Y%m%d')}-{timestamp}"
                    
                    fatura = Fatura(
                        firma_id=firma.id,
                        donem_id=donem.id,
                        sube_id=sube.id,
                        cari_id=cari.id,
                        depo_id=depo.id,
                        fatura_turu=FaturaTuru.SATIS.value,
                        belge_no=belge_no,
                        tarih=islem_tarihi.date(),
                        vade_tarihi=islem_tarihi.date(),
                        aciklama="Test Verisi"
                    )
                    db.session.add(fatura)
                    db.session.flush()
                    
                    ara_toplam = Decimal('0')
                    kdv_toplami = Decimal('0')
                    
                    sepet_urun_sayisi = random.randint(1, 4)
                    
                    for _ in range(sepet_urun_sayisi):
                        stok = random.choice(db_stoklar)
                        miktar = Decimal(str(random.randint(1, 5)))
                        
                        if ay in [12, 1, 2]: 
                            if stok.ad in ["Salep", "Sıcak Çikolata"]:
                                miktar *= Decimal(str(random.randint(3, 6)))
                            elif stok.ad in ["Dondurma", "Limonata"]:
                                if random.random() > 0.2:  continue
                                
                        elif ay in [6, 7, 8]: 
                            if stok.ad in ["Dondurma", "Ice Tea"]:
                                miktar *= Decimal(str(random.randint(4, 8)))
                            elif stok.ad == "Salep":
                                if random.random() > 0.1: continue

                        birim_fiyat = Decimal(str(stok.satis_fiyati))
                        net_tutar = miktar * birim_fiyat
                        kdv_orani = Decimal('20')
                        kdv_tutari = net_tutar * (kdv_orani / Decimal('100'))
                        satir_toplami = net_tutar + kdv_tutari
                        
                        kalem = FaturaKalemi(
                            fatura_id=fatura.id,
                            stok_id=stok.id,
                            miktar=miktar,
                            birim_fiyat=birim_fiyat,
                            kdv_orani=kdv_orani,
                            satir_toplami=satir_toplami
                        )
                        db.session.add(kalem)
                        
                        ara_toplam += net_tutar
                        kdv_toplami += kdv_tutari
                    
                    if ara_toplam == 0:
                        stok = db_stoklar[0]
                        net = Decimal(str(stok.satis_fiyati))
                        kdv = net * Decimal('0.2')
                        
                        kalem = FaturaKalemi(
                            fatura_id=fatura.id,
                            stok_id=stok.id,
                            miktar=Decimal('1'),
                            birim_fiyat=net,
                            kdv_orani=Decimal('20'),
                            satir_toplami=net + kdv
                        )
                        db.session.add(kalem)
                        ara_toplam = net
                        kdv_toplami = kdv

                    fatura.ara_toplam = ara_toplam
                    fatura.kdv_toplam = kdv_toplami
                    fatura.genel_toplam = ara_toplam + kdv_toplami
                
                if (i + 1) % 50 == 0:
                    db.session.commit()
                    print(f"  → {i + 1}/365 gün işlendi...")
                    
            db.session.commit()
            print("✅ Tamamlandı!")
            
        except Exception as e: 
            db.session.rollback()
            print(f"❌ Hata: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    generate_data()