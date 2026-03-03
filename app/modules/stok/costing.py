# app/modules/stok/costing.py

import logging
from decimal import Decimal
from app.extensions import get_tenant_db
from app.modules.stok.models import StokHareketi
from app.enums import HareketTuru

logger = logging.getLogger(__name__)

class MaliyetMotoru:
    @staticmethod
    def ortalama_maliyet_hesapla(stok_id, tarih, firma_id):
        """
        Belirtilen tarihe kadar olan Alış ve Devir hareketlerini tarayarak
        'Hareketli Ağırlıklı Ortalama' (Moving Average) maliyetini hesaplar.
        """
        tenant_db = get_tenant_db()
        
        try:
            # Sadece maliyeti oluşturan giriş hareketlerini (Alış Faturası ve Devir) buluyoruz
            giriş_hareketleri = tenant_db.query(StokHareketi).filter(
                StokHareketi.firma_id == str(firma_id),
                StokHareketi.stok_id == str(stok_id),
                StokHareketi.tarih <= tarih,
                StokHareketi.hareket_turu.in_(['ALIS_FATURASI', 'DEVIR_GIRISI'])
            ).all()

            toplam_miktar = Decimal('0.0')
            toplam_maliyet_tutari = Decimal('0.0')

            for hareket in giriş_hareketleri:
                miktar = Decimal(str(hareket.miktar or 0))
                birim_fiyat = Decimal(str(hareket.birim_fiyat or 0))
                
                if miktar > 0 and birim_fiyat > 0:
                    toplam_miktar += miktar
                    toplam_maliyet_tutari += (miktar * birim_fiyat)

            # Sıfıra bölünme hatasını engelliyoruz
            if toplam_miktar > 0:
                ortalama_maliyet = toplam_maliyet_tutari / toplam_miktar
                return round(ortalama_maliyet, 4)
                
            return Decimal('0.0')
            
        except Exception as e:
            logger.error(f"Maliyet Hesaplama Hatası (Stok ID: {stok_id}): {e}")
            return Decimal('0.0')