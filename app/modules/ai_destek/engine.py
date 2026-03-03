# app/modules/ai_destek/engine.py

import logging
import json
from app.extensions import get_tenant_db
from app.modules.cari.models import CariHesap
# Senin yazdığın güçlü AI motorunu içeri aktarıyoruz
from .ai_generator import get_gemini_response, is_active 

logger = logging.getLogger(__name__)

class AIAssistant:
    """
    SaaS ERP için Gelişmiş Lojistik ve Risk Yapay Zeka Motoru
    """
    
    @staticmethod
    def sevkiyat_analizi(form_data):
        """
        Formdan gelen verileri ve Cari geçmişini harmanlayarak
        Gemini AI üzerinden gerçek zamanlı risk ve rota analizi yapar.
        """
        tenant_db = get_tenant_db()
        
        # 1. Form Verilerini Ayrıştır
        cari_id = form_data.get('cari_id')
        kalemler = form_data.get('kalemler', [])
        
        # 2. Veritabanından Cari Finansal Bilgilerini Çek
        cari_unvan = "Bilinmeyen Müşteri"
        cari_bakiye = 0
        cari_risk_limiti = 50000 # Varsayılan Limit
        
        if cari_id and cari_id not in ['0', '']:
            cari = tenant_db.get(CariHesap, str(cari_id))
            if cari:
                cari_unvan = cari.unvan
                cari_bakiye = float(cari.bakiye or 0)
                cari_risk_limiti = float(cari.risk_limiti or 50000)

        toplam_miktar = sum(float(k.get('miktar', 0)) for k in kalemler)

        # 3. AI İçin Veri Paketi Hazırla
        analiz_paketi = {
            "musteri_bilgisi": {
                "unvan": cari_unvan,
                "mevcut_borc_bakiyesi_TL": cari_bakiye,
                "sirketin_tanimladigi_risk_limiti_TL": cari_risk_limiti
            },
            "sevkiyat_bilgisi": {
                "toplam_urun_miktari": toplam_miktar,
                "farkli_kalem_sayisi": len(kalemler)
            }
        }

        # AI Modülü .env kaynaklı kapalıysa fallback (yedek) mekanizması
        if not is_active:
            logger.warning("AI Modülü kapalı. Kural tabanlı analiz çalıştırılıyor.")
            risk = "Yüksek" if cari_bakiye > cari_risk_limiti else "Düşük"
            return {
                "risk_skoru": risk,
                "oneriler": [
                    "⚠️ Yapay Zeka modülü şu an devre dışı (.env API Key kontrol edin).",
                    f"Müşteri Bakiyesi: {cari_bakiye:,.2f} TL | Limit: {cari_risk_limiti:,.2f} TL",
                    "Lojistik: Standart sevk prosedürünü uygulayın."
                ]
            }

        # 4. GERÇEK GEMINI AI PROMPTU
        system_prompt = """
        Sen üst düzey bir Kurumsal Kaynak Planlama (ERP) Risk Asistanısın.
        Sana bir müşterinin finansal durumu ve yapılmak istenen sevkiyatın detayları verilecek.
        
        GÖREVLERİN:
        1. Müşterinin mevcut borcunu ve risk limitini karşılaştır. Limit aşımı varsa veya yaklaşılmışsa bunu tespit et.
        2. Sevkiyat hacmine bakarak (örneğin 1000 adetten fazlaysa) nakliye aracı (Tır, Kamyon, Kargo) tavsiyesi ver.
        3. Kesinlikle bir risk skoru belirle ("Düşük", "Orta", "Yüksek").
        4. Sevkiyatı yapan personele net, emredici ve profesyonel 3 adet aksiyon önerisi sun.
        
        ÇIKTI FORMATI (SADECE AŞAĞIDAKİ JSON OBJESİ OLACAK, MARKDOWN VEYA TEXT EKLEME):
        {
            "risk_skoru": "Yüksek/Orta/Düşük",
            "oneriler": [
                "1. Finansal öneri...",
                "2. Lojistik öneri...",
                "3. Operasyonel öneri..."
            ]
        }
        """
        
        user_prompt = f"Analiz Edilecek Güncel Veri:\n{json.dumps(analiz_paketi, ensure_ascii=False)}"
        
        try:
            # Senin yazdığın o harika get_gemini_response metodunu çağırıyoruz!
            ai_sonuc = get_gemini_response(system_prompt, user_prompt)
            
            if ai_sonuc and "risk_skoru" in ai_sonuc:
                return ai_sonuc
            else:
                raise Exception("AI beklenmeyen bir format döndürdü.")
                
        except Exception as e:
            logger.error(f"Gemini AI Analiz Hatası: {e}")
            return {
                "risk_skoru": "Hata",
                "oneriler": [f"Yapay zeka analiz yaparken bir hata oluştu: {str(e)}"]
            }