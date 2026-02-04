# tests/fatura_test.py

from app import create_app
from models import YazdirmaSablonu

app = create_app()
# Şimdi import et
#from .import app
from models.base import db
from models import Fatura
from modules.fatura.services import FaturaService

def test_fatura_get_by_id():
    """Fatura kalemlerini test et"""
    
    with app.app_context():
        fatura = FaturaService.get_by_id(1, firma_id=1)
        
        if fatura:
            print(f"✅ Fatura:  {fatura.belge_no}")
            print(f"✅ Kalem Sayısı: {len(fatura.kalemler)}")
            
            for i, kalem in enumerate(fatura.kalemler):
                print(f"\n📦 Kalem {i+1}:")
                print(f"  - ID: {kalem.id}")
                print(f"  - Stok ID: {kalem.stok_id}")
                print(f"  - Stok Adı: {kalem.stok.ad if kalem.stok else '⚠️ YOK'}")
                print(f"  - Miktar: {kalem.miktar}")
                print(f"  - Birim Fiyat: {kalem.birim_fiyat}")
                print(f"  - Satır Toplamı: {kalem.satir_toplami}")
        else:
            print("❌ Fatura bulunamadı!")

if __name__ == '__main__':
    test_fatura_get_by_id()