# app/modules/ai_destek/ocr_service.py
"""
Fatura OCR Servisi - Google Gemini Vision API
Fatura görsellerini okur ve JSON formatında parse eder
"""

import os
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime
from PIL import Image
import io

from .ai_generator import get_gemini_response, ACTIVE_MODEL_NAME
from app.extensions import db
from flask import current_app

logger = logging.getLogger(__name__)

# Gemini Vision için import
try:
    import google.generativeai as genai
    HAS_VISION = True
except ImportError:
    HAS_VISION = False
    logger.warning("google-generativeai paketi yüklü değil. OCR çalışmayacak.")


class FaturaOCRService:
    """
    Fatura OCR İşlemleri (Gemini Vision)
    """
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key and HAS_VISION:
            genai.configure(api_key=self.api_key)
            # Vision için model (gemini-1.5-flash veya gemini-1.5-pro)
            self.vision_model = genai.GenerativeModel(model_name="gemini-1.5-flash")
            self.is_active = True
        else:
            self.is_active = False
            logger.warning("⚠️ Gemini API Key bulunamadı veya kütüphane eksik!")
    
    def fatura_gorselden_oku(self, image_file, fatura_turu: str = 'satis') -> Dict:
        """
        Fatura görselini Gemini Vision ile okur
        
        Args:
            image_file: File object (werkzeug.FileStorage) veya bytes
            fatura_turu: 'satis' veya 'alis'
        
        Returns:
            Dict: Parse edilmiş fatura verisi
        """
        if not self.is_active:
            raise Exception("OCR servisi aktif değil! GEMINI_API_KEY kontrol edin.")
        
        try:
            # Görseli PIL Image'e çevir
            if hasattr(image_file, 'read'):
                image_bytes = image_file.read()
                image_file.seek(0)  # Pointer'ı başa al
            else:
                image_bytes = image_file
            
            image = Image.open(io.BytesIO(image_bytes))
            
            # Gemini'ye gönderilecek prompt
            prompt = self._build_fatura_prompt(fatura_turu)
            
            logger.info(f"📸 Fatura OCR başlatıldı (Model: {self.vision_model._model_name})")
            
            # Gemini Vision API çağrısı
            response = self.vision_model.generate_content([prompt, image])
            
            # JSON parse et
            raw_text = response.text
            
            # Gemini bazen markdown code block içinde JSON döner, temizle
            cleaned_text = self._clean_json_response(raw_text)
            
            parsed_data = json.loads(cleaned_text)
            
            # Başarı logu
            logger.info(f"✅ OCR Başarılı: Belge No: {parsed_data.get('belge_no', 'N/A')}")
            
            return {
                'success': True,
                'data': parsed_data,
                'raw_text': raw_text,
                'confidence': parsed_data.get('confidence', 0.0),
                'model': self.vision_model._model_name
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Parse Hatası: {e}\nRaw Response: {raw_text}")
            return {
                'success': False,
                'error': 'JSON formatı hatalı',
                'raw_text': raw_text
            }
        
        except Exception as e:
            logger.error(f"❌ OCR Hatası: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_fatura_prompt(self, fatura_turu: str) -> str:
        """
        Gemini için fatura okuma promptu oluşturur
        """
        return f"""
Sen bir muhasebe uzmanısın. Bu görseldeki {fatura_turu} FATURASINI detaylı şekilde analiz et ve JSON formatında çıkar.

**ÖNEMLİ KURALLAR:**
1. Tüm parasal değerleri ondalık (Decimal) formatta yaz (örn: 1250.50)
2. Tarihleri YYYY-MM-DD formatında yaz
3. Türkçe karakter sorunlarını düzelt
4. Eğer bir bilgi okunamıyorsa "null" yaz
5. KDV oranlarını yüzde olarak yaz (örn: 20 veya 10)

**ÇIKARILACAK VERİLER:**

{{
  "belge_no": "Fatura numarası",
  "seri": "Fatura serisi (varsa)",
  "sira_no": "Sıra numarası (varsa)",
  "tarih": "YYYY-MM-DD formatında tarih",
  "vade_tarihi": "YYYY-MM-DD formatında vade (yoksa null)",
  "cari_unvan": "Müşteri/Tedarikçi ünvanı",
  "cari_vergi_no": "Vergi numarası (varsa)",
  "cari_adres": "Adres (varsa)",
  "kalemler": [
    {{
      "sira": 1,
      "stok_kodu": "Ürün kodu (varsa)",
      "aciklama": "Ürün açıklaması",
      "miktar": 0.0,
      "birim": "Adet/Kg/M2 vb.",
      "birim_fiyat": 0.0,
      "iskonto_oran": 0.0,
      "kdv_oran": 0.0,
      "tutar": 0.0
    }}
  ],
  "ara_toplam": 0.0,
  "iskonto_toplam": 0.0,
  "kdv_toplam": 0.0,
  "genel_toplam": 0.0,
  "doviz_turu": "TL/USD/EUR",
  "doviz_kuru": 1.0,
  "aciklama": "Fatura notu veya açıklama (varsa)",
  "confidence": 0.95,
  "_notlar": ["Okunamayan veya belirsiz alanlar burada"]
}}

**SADECE JSON DÖNDÜR, BAŞKA AÇIKLAMA YAPMA!**
"""
    
    def _clean_json_response(self, raw_text: str) -> str:
        """
        Gemini'nin markdown code block içinde JSON dönmesi durumunda temizler
        """
        # Markdown code block temizleme
        if raw_text.startswith('```json'):
            raw_text = raw_text.replace('```json', '').replace('```', '').strip()
        elif raw_text.startswith('```'):
            raw_text = raw_text.replace('```', '').strip()
        
        return raw_text
    
    def fatura_onayla_ve_kaydet(self, ocr_data: Dict, firma_id: str, kullanici_id: int) -> Dict:
        """
        OCR sonucunu Fatura modeline çevirir ve kaydeder
        
        Args:
            ocr_data: OCR'dan gelen parse edilmiş data
            firma_id: Firma ID
            kullanici_id: Kullanıcı ID
        
        Returns:
            Dict: Kaydedilen fatura bilgisi
        """
        from app.modules.fatura.models import Fatura, FaturaKalemi
        from app.modules.cari.models import CariHesap
        from decimal import Decimal
        
        try:
            # Cari hesap kontrolü (ünvan ile arama)
            cari_unvan = ocr_data.get('cari_unvan')
            cari = None
            
            if cari_unvan:
                cari = CariHesap.query.filter(
                    CariHesap.firma_id == firma_id,
                    CariHesap.unvan.ilike(f"%{cari_unvan}%")
                ).first()
            
            # Yeni fatura oluştur
            yeni_fatura = Fatura()
            yeni_fatura.firma_id = firma_id
            yeni_fatura.belge_no = ocr_data.get('belge_no', 'OCR-' + datetime.now().strftime('%Y%m%d%H%M'))
            yeni_fatura.tarih = datetime.strptime(ocr_data['tarih'], '%Y-%m-%d').date() if ocr_data.get('tarih') else datetime.now().date()
            
            if ocr_data.get('vade_tarihi'):
                yeni_fatura.vade_tarihi = datetime.strptime(ocr_data['vade_tarihi'], '%Y-%m-%d').date()
            
            yeni_fatura.cari_id = cari.id if cari else None
            yeni_fatura.ara_toplam = Decimal(str(ocr_data.get('ara_toplam', 0)))
            yeni_fatura.kdv_toplam = Decimal(str(ocr_data.get('kdv_toplam', 0)))
            yeni_fatura.iskonto_toplam = Decimal(str(ocr_data.get('iskonto_toplam', 0)))
            yeni_fatura.genel_toplam = Decimal(str(ocr_data.get('genel_toplam', 0)))
            yeni_fatura.aciklama = f"OCR ile oluşturuldu: {ocr_data.get('aciklama', '')}"
            
            # OCR meta bilgisi (opsiyonel, model'de varsa)
            if hasattr(yeni_fatura, 'ocr_raw_text'):
                yeni_fatura.ocr_raw_text = json.dumps(ocr_data, ensure_ascii=False)
                yeni_fatura.ocr_confidence = ocr_data.get('confidence', 0.0)
                yeni_fatura.ocr_processed_at = datetime.now()
            
            db.session.add(yeni_fatura)
            db.session.flush()  # ID'yi al
            
            # Kalemleri ekle
            for kalem_data in ocr_data.get('kalemler', []):
                kalem = FaturaKalemi()
                kalem.fatura_id = yeni_fatura.id
                kalem.aciklama = kalem_data.get('aciklama', '')
                kalem.miktar = Decimal(str(kalem_data.get('miktar', 0)))
                kalem.birim = kalem_data.get('birim', 'Adet')
                kalem.birim_fiyat = Decimal(str(kalem_data.get('birim_fiyat', 0)))
                kalem.kdv_oran = Decimal(str(kalem_data.get('kdv_oran', 20)))
                kalem.tutar = Decimal(str(kalem_data.get('tutar', 0)))
                
                db.session.add(kalem)
            
            db.session.commit()
            
            logger.info(f"✅ OCR Faturası Kaydedildi: {yeni_fatura.belge_no} (ID: {yeni_fatura.id})")
            
            return {
                'success': True,
                'fatura_id': yeni_fatura.id,
                'belge_no': yeni_fatura.belge_no,
                'message': 'Fatura başarıyla kaydedildi'
            }
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Fatura Kaydetme Hatası: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
ocr_service = FaturaOCRService()