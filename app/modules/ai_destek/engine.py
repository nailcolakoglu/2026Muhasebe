# app/modules/ai_destek/engine.py
import re

class AIAssistant:
    """
    Basit AI motoru.İleride OpenAI veya HuggingFace eklenebilir.
    """
    
    @staticmethod
    def sevkiyat_analizi(irsaliye_verisi):
        """
        İrsaliye verisine bakarak lojistik önerilerde bulunur.
        """
        oneriler = []
        
        # 1.Ağırlık/Hacim Kontrolü (Simülasyon)
        toplam_miktar = sum([k['miktar'] for k in irsaliye_verisi['kalemler']])
        
        if toplam_miktar > 5000:
            oneriler.append("⚠️ Yüksek tonaj! Tır veya Kamyon planlaması yapın.")
        elif toplam_miktar < 100:
            oneriler.append("💡 Düşük miktar.Kargo veya Parsiyel gönderim daha uygun olabilir.")

        # 2.Şehir Bazlı Rota Tahmini (Basit Regex)
        adres = irsaliye_verisi.get('adres', '').lower()
        if 'istanbul' in adres and 'ankara' in adres:
            oneriler.append("🚚 Rota: İstanbul -> Ankara (Ort.450km / 5-6 Saat)")
            
        return {
            'risk_skoru': 'Yüksek' if toplam_miktar > 10000 else 'Düşük',
            'oneriler': oneriler
        }

    @staticmethod
    def irsaliye_ocr_simulasyonu(dosya_icerigi):
        """
        Gelen bir irsaliye fotoğrafından metin okuma simülasyonu.
        Gerçekte Tesseract OCR veya Google Vision API kullanılır.
        """
        return {
            "tahmin_edilen_belge_no": "IRS-2025-999",
            "tahmin_edilen_tarih": "2025-01-01",
            "okunan_satirlar": [
                {"stok_kodu": "STK-001", "miktar": 10},
                {"stok_kodu": "STK-002", "miktar": 5}
            ]
        }