import time
import uuid
from faker import Faker
from run import app
from flask import session
from app.extensions import get_tenant_db

# Kendi modellerinin yollarını doğrula (stok modeli ismi StokKarti veya Stok olabilir)
from app.modules.cari.models import CariHesap
from app.modules.stok.models import StokKart

fake = Faker('tr_TR') # Türkçe veriler üretecek

def run_stress_test(firma_id, hedef_adet=100000, batch_size=5000):
    print(f"🚀 STRES TESTİ BAŞLIYOR: {hedef_adet} Cari ve {hedef_adet} Stok üretilecek...")
    baslangic_zamani = time.time()

    with app.test_request_context('/'):
        # Celery'de yaptığımız gibi sanal bir oturum (session) açıp Tenant DB'yi kandırıyoruz
        session['tenant_id'] = str(firma_id)
        session['aktif_firma_id'] = str(firma_id)
        
        tenant_db = get_tenant_db()
        
        # ---------------------------------------------------------
        # 1. CARİ HESAP ÜRETİMİ (100.000 Adet)
        # ---------------------------------------------------------
        
        print("👥 Cariler üretiliyor, lütfen bekleyin...")
        cari_liste = []
        for i in range(1, hedef_adet + 1):
            cari_liste.append({
                'id': str(uuid.uuid4()),
                'firma_id': str(firma_id),
                'kod': f"CR-TEST-{i}",
                'unvan': fake.company(),
                'vergi_no': str(fake.random_number(digits=10, fix_len=True)),
                'vergi_dairesi': fake.city() + " V.D.",
                'eposta': fake.company_email(),
                'telefon': fake.phone_number()[:15],
                'il': fake.city(),
                'aktif': True
            })
            
            # Belleği şişirmemek için paketler (batch) halinde veritabanına basıyoruz
            if i % batch_size == 0:
                tenant_db.bulk_insert_mappings(CariHesap, cari_liste)
                tenant_db.commit()
                cari_liste.clear()
                print(f"   -> {i} Cari eklendi...")
        
        # Kalan son partiyi ekle
        if cari_liste:
            tenant_db.bulk_insert_mappings(CariHesap, cari_liste)
            tenant_db.commit()
        
        # ---------------------------------------------------------
        # 2. STOK KARTI ÜRETİMİ (100.000 Adet)
        # ---------------------------------------------------------
        print("\n📦 Stoklar üretiliyor, lütfen bekleyin...")
        stok_liste = []
        for i in range(1, hedef_adet + 1):
            stok_liste.append({
                'id': str(uuid.uuid4()),
                'firma_id': str(firma_id),
                'kod': f"STK-TEST-{i}",  # ✨ DÜZELTME: 'stok_kodu' yerine 'kod'
                'ad': f"{fake.word().capitalize()} {fake.word().capitalize()} Modeli"[:100], # ✨ DÜZELTME: 'stok_adi' yerine 'ad'
                'birim': fake.random_element(elements=('ADET','KG','LT','MT','M2','M3','KUTU','KOLI','PALET')),
                'alis_fiyati': round(fake.pyfloat(positive=True, min_value=10, max_value=500), 2),
                'satis_fiyati': round(fake.pyfloat(positive=True, min_value=550, max_value=2000), 2),
                'aktif': True
                # Not: KDV Oranı modelde yoksa veya adı farklıysa (örn: kdv_alis) hata vermemesi için şimdilik kaldırdım.
                # Eğer modelinde zorunlu olan başka alanlar varsa (tip vb.) onları da buraya ekleyebilirsin.
            })
            
            if i % batch_size == 0:
                tenant_db.bulk_insert_mappings(StokKart, stok_liste)
                tenant_db.commit()
                stok_liste.clear()
                print(f"   -> {i} Stok eklendi...")

        if stok_liste:
            tenant_db.bulk_insert_mappings(StokKarti, stok_liste)
            tenant_db.commit()

        if stok_liste:
            tenant_db.bulk_insert_mappings(StokKart, stok_liste)
            tenant_db.commit()

        bitis_zamani = time.time()
        gecen_sure = bitis_zamani - baslangic_zamani
        print(f"\n✅ MÜKEMMEL! Toplam {hedef_adet * 2} kayıt {gecen_sure:.2f} saniyede başarıyla oluşturuldu!")

if __name__ == '__main__':
    # DİKKAT: Buraya kendi sistemindeki aktif Firma ID'ni (UUID) yapıştır.
    # Örnek: '3851b622-74d4-423d-947a-998ec7f27ef3'
    TEST_FIRMA_ID = "3851b622-74d4-423d-947a-998ec7f27ef3" 
    
    # İstersen önce 5000 ile test et, sonra 100000'e çıkar
    run_stress_test(TEST_FIRMA_ID, hedef_adet=100000)