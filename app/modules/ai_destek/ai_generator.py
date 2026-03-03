import json
import os
from dotenv import load_dotenv # 👈 BU SATIRI EKLEYİN
import google.generativeai as genai
from google.api_core import retry
from datetime import datetime

# .env dosyasını hemen burada yükle ki kodlar çalışmadan anahtar hazır olsun
load_dotenv()

# Google Generative AI kütüphanesi kontrolü
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("UYARI: 'google-generativeai' kütüphanesi yüklü değil.'pip install google-generativeai' çalıştırın.")

# 1.API Key Kontrolü
# Google AI Studio'dan aldığınız anahtarı GEMINI_API_KEY olarak kaydedin
api_key = os.environ.get("GEMINI_API_KEY") 
# --- AKILLI MODEL SEÇİCİ ---
def get_best_available_model():
    """
    Sunucuda mevcut olan modelleri tarar ve en uygununu seçer.
    """
    if not api_key: return None

    try:
        genai.configure(api_key=api_key)
        print("📡 AI Modelleri taranıyor...")
        
        # Tüm modelleri listele
        all_models = list(genai.list_models())
        
        # Sadece içerik üretebilenleri (generateContent) filtrele
        available_models = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        
        if not available_models:
            print("⚠️ Hiçbir uygun model bulunamadı!")
            return "models/gemini-pro" # Fallback

        # Tercih Sırası (En yeni ve hızlıdan eskiye)
        preferences = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'models/gemini-1.0-pro',
            'models/gemini-pro'
        ]

        # Tercih listesindekilerden biri var mı?
        for pref in preferences:
            if pref in available_models:
                print(f"✅ Seçilen Model: {pref}")
                return pref
        
        # Listede yoksa ilk bulduğunu seç
        selected = available_models[0]
        print(f"✅ Otomatik Seçilen Model: {selected}")
        return selected

    except Exception as e:
        print(f"❌ Model Seçimi Hatası: {e}")
        return "models/gemini-pro" # Hata olursa varsayılanı dene

# Başlangıçta modeli belirle
ACTIVE_MODEL_NAME = None

try:
    if api_key:
        ACTIVE_MODEL_NAME = get_best_available_model()
        is_active = True
    else:
        print("⚠️ [AI MODÜLÜ] API Key bulunamadı (.env dosyasını kontrol edin).")
except Exception as e:
    print(f"❌ [AI MODÜLÜ] Başlatma Hatası: {e}")
    is_active = False

def get_gemini_response(system_instruction, user_prompt):
    """
    Gemini modelini JSON modunda çalıştırarak yanıt alır.
    """
    if not is_active or not ACTIVE_MODEL_NAME:
        return None

    try:
        # Model Ayarları (JSON zorunluluğu)
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }

        # Modeli Başlat (Sistem talimatı ile)
        # ✨ KRİTİK DÜZELTME: MODEL_NAME yerine ACTIVE_MODEL_NAME kullanıldı
        model = genai.GenerativeModel(
            model_name=ACTIVE_MODEL_NAME, 
            generation_config=generation_config,
            system_instruction=system_instruction
        )

        # İsteği Gönder
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(user_prompt)
        
        # Yanıtı Parse Et
        return json.loads(response.text)

    except Exception as e:
        print(f"Gemini API Hatası: {e}")
        return None
        return None

# ----------------------------------------------------------------
# 1.FORM OLUŞTURUCU
# ----------------------------------------------------------------
def generate_form_from_text(prompt_text):
    # --- SİMÜLASYON MODU ---
    if not is_active:
        print(f"🤖 Simülasyon: '{prompt_text}' için örnek form.")
        if "araç" in prompt_text.lower():
            return {
                "title": "Araç Bakım Formu (Demo)",
                "action": "/submit-car",
                "method": "POST",
                "fields": [{"name": "plaka", "type": "PLATE", "label": "Plaka", "required": True}]
            }
        return {
            "title": "Demo Form",
            "action": "/submit-demo",
            "method": "POST",
            "fields": [{"name": "ad", "type": "TEXT", "label": "Adınız", "required": True}]
        }

    # --- GEMINI AI MODU ---
    system_prompt = """
    Sen uzman bir sistem mimarısın.Kullanıcının isteğine göre bir Form JSON yapısı oluşturmalısın.
    
    Kullanabileceğin 'type' değerleri (FieldType Enum):
    TEXT, TEXTAREA, NUMBER, DATE, DATETIME, SELECT, CHECKBOX, RADIO, DRAWING, COLOR_PICKER_ADVANCED, CALC, MULTI_FIELD,
    EMAIL, TEL, TCKN, IBAN, FILE, IMAGE, SIGNATURE, RATING, SWITCH, BARCODE, OTP, AUDIO_RECORDER, VIDEO_RECORDER,
    PLATE, AUTO_NUMBER, CURRENCY,GEOLOCATION, SLIDER, IP, CREDIT_CARD, MASTER_DETAIL, MAP_POINT.
    
    Çıktı Şeması (JSON):
    {
        "title": "Form Başlığı",
        "action": "/submit-form",
        "method": "POST",
        "fields": [
            {
                "name": "degisken_adi_snake_case", 
                "type": "TEXT", 
                "label": "Görünecek Etiket", 
                "required": true,
                "placeholder": "İpucu",
                "options": ["A", "B"] (Sadece SELECT/RADIO için)
            }
        ]
    }
    """
    return get_gemini_response(system_prompt, f"İstek: {prompt_text}")

# ----------------------------------------------------------------
# 2.İŞ AKIŞI OLUŞTURUCU
# ----------------------------------------------------------------
def generate_workflow_from_text(prompt_text):
    if not is_active:
        return {"start_step": "onay", "steps": {"onay": {"type": "approval", "role": "manager", "next_step": "END"}}}

    system_prompt = """
    Sen bir BPMN uzmanısın.Metni JSON workflow formatına çevir.
    Adım tipleri: 'condition', 'action', 'approval'.
    
    Çıktı Şeması (JSON):
    {
        "start_step": "step_id",
        "steps": {
            "step_id": { "type": "...", ...}
        }
    }
    """
    return get_gemini_response(system_prompt, f"Süreç: {prompt_text}")

# ----------------------------------------------------------------
# 3.RAPOR KONFIGURASYONU
# ----------------------------------------------------------------
def generate_report_config(prompt_text, available_columns):
    if not is_active:
        return {"title": "Demo Rapor", "chart_type": "bar", "rows": "category", "values": "amount"}

    system_prompt = f"""
    Sen bir Veri Analistisin.Rapor isteğini JSON konfigürasyonuna çevir.
    Mevcut Sütunlar: {available_columns}
    Format: {{"rows": "col_name", "values": "col_name", "aggregator": "sum/count/avg", "chart_type": "bar/line/pie", "title": "..."}}
    """
    return get_gemini_response(system_prompt, f"Analiz İsteği: {prompt_text}")

# ----------------------------------------------------------------
# 4.MODEL DOĞRULAMA (TEYİT FONKSİYONU)
# ----------------------------------------------------------------
def verify_gemini_model():
    """Kullanılan modelin özelliklerini ve erişimi kontrol eder."""
    if not is_active:
        return "Gemini API anahtarı yok veya hatalı."
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        # Basit bir test
        response = model.generate_content("Merhaba, hangi modelsin?")
        return f"✅ Bağlantı Başarılı! Aktif Model: {MODEL_NAME}\nModel Cevabı: {response.text}"
    except Exception as e:
        return f"❌ Model Erişim Hatası: {e}"  

def analyze_stock_trends(sales_data_json):
    """
    Satış verilerini analiz edip stok tavsiyesi verir.
    sales_data_json: Ürün bazlı aylık satış adetleri (JSON String)
    """
    
    # Simülasyon (API Anahtarı Yoksa)
    if not is_active:
        return """
        <h3>🤖 Yapay Zeka Stok Analizi (Demo)</h3>
        <ul>
            <li><strong>Salep:</strong> Kış sezonu (Aralık-Şubat) geldiği için satışlarda %40 artış bekleniyor.<i>Öneri: Stok seviyesini 500 adete çıkarın.</i></li>
            <li><strong>Dondurma:</strong> Mevsim dışı, stok tutmanıza gerek yok.</li>
            <li><strong>Bitki Çayı:</strong> Soğuk algınlığı sezonu, talep artabilir.</li>
        </ul>
        """

    # Gerçek AI Analizi
    import datetime
    current_month = datetime.datetime.now().strftime("%B") # Örn: December
    
    system_prompt = f"""
    Sen uzman bir Tedarik Zinciri ve Stok Planlama Analistisin.
    Sana bir mağazanın geçmiş satış verilerini (Ürün ve Aylık Satış Adetleri) vereceğim.
    
    Şu anki ay: {current_month}
    
    Görevlerin:
    1.Verilerdeki mevsimsel trendleri tespit et (Örn: Kışın artanlar, Yazın düşenler).
    2.Önümüzdeki ay için hangi ürünlerden stok yapılması gerektiğini belirle.
    3.Nedenini kısa ve net bir dille açıkla.
    4.Çıktıyı HTML formatında (Bootstrap uyumlu, şık bir liste veya tablo) ver.
    
    Çıktı Tonu: Profesyonel, yönlendirici ve net.
    """
    
    user_prompt = f"İşte Satış Verileri:\n{sales_data_json}\n\nLütfen stok tavsiyesi raporunu hazırla."
    
    # Gemini'den yanıt al (JSON değil, direkt HTML metin istiyoruz)
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content([system_prompt, user_prompt])
        return response.text
    except Exception as e:
        return f"<div class='alert alert-danger'>Analiz Hatası: {str(e)}</div>"

def analyze_dead_stock(stock_data_json):
    """
    Ölü stokları tespit eder ve likidasyon (nakite çevirme) stratejileri önerir.
    """
    # Simülasyon
    if not is_active:
        return """<div class='alert alert-warning'>AI Modülü kapalı.Simülasyon verisi gösterilemiyor.</div>"""

    import datetime
    bugun = datetime.datetime.now().strftime("%d.%m.%Y")
    
    system_prompt = """
    Sen deneyimli ve disiplinli bir Depo ve Finans Yöneticisisin.
    Şirketin nakit akışını önemsiyorsun ve depoda yatan "Ölü Stoklardan" nefret ediyorsun.
    
    Sana verilen JSON verisinde şunlar var:
    - Ürün Adı
    - Mevcut Stok (Adet)
    - Birim Maliyet (Alış Fiyatı)
    - Son 6 Ay Satış (Adet)
    
    Görevlerin:
    1.**Ölü Stokları Belirle:** Stok miktarı yüksek (>10) ama satışı çok düşük veya sıfır olan ürünleri bul.
    2.**Bağlı Sermayeyi Hesapla:** (Stok * Maliyet) formülüyle bu ürünlerde kaç TL paramızın yattığını vurgula.
    3.**Aksiyon Planı:** Her ölü ürün için onu elden çıkarmaya yönelik *spesifik* bir kampanya önerisi yaz (Örn: "Bundle yap", "%50 indirimle erit", "Hediye olarak ver").
    
    Çıktı Formatı:
    - Yönetici Özeti (Toplam yatan para miktarı ile başla - Kırmızı ve Kalın fontla).
    - HTML Tablosu (Bootstrap classlı şık tablo: Ürün, Stok, Yatan Para, Öneri, Risk Seviyesi).
    - Risk Seviyesi sütununda "Yüksek" için kırmızı badge, "Orta" için sarı badge kullan.
    """
    
    user_prompt = f"Rapor Tarihi: {bugun}\nAnaliz Edilecek Stok Verisi:\n{stock_data_json}"
    
    return get_gemini_response(system_prompt, user_prompt)

def analyze_customer_risk(customer_data_json):
    """
    Müşteri verilerini (RFM + Bakiye) analiz eder ve Risk Raporu oluşturur.
    """
    # Simülasyon
    if not is_active:
        return "<div class='alert alert-warning'>AI Modülü kapalı.</div>"

    system_prompt = """
    Sen uzman bir Finansal Risk Analisti ve CRM Yöneticisisin.
    Sana müşteri listesi, bakiyeleri ve son alışveriş detayları verilecek.
    
    Görevlerin:
    1.**Risk Analizi:** Borcu yüksek (>10.000 TL) ama son 3 aydır alışveriş yapmayanları "YÜKSEK RİSK" olarak işaretle.
    2.**Sadakat Analizi:** Çok sık alışveriş yapan ve cirosu yüksek olanları "VIP MÜŞTERİ" olarak işaretle.
    3.**Aksiyon:** Riskli müşteriler için tahsilat stratejisi, VIP'ler için ödül stratejisi yaz.
    
    Çıktı Formatı:
    Bana doğrudan ve SADECE render edilebilir bir HTML String ver.(JSON verme).
    - İçinde Bootstrap tabloları, renkli badge'ler (bg-danger, bg-success) olsun.
    - Tablo Sütunları: Cari Adı, Borç Bakiye, Son İşlem, Segment (VIP/Riskli/Normal), Aksiyon Önerisi.
    """
    
    user_prompt = f"Analiz Edilecek Müşteri Verisi:\n{customer_data_json}"
    
    try:
        # JSON dönmesini engellemek için response_mime_type kullanmıyoruz
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content([system_prompt, user_prompt])
        return response.text
    except Exception as e:
        return f"<div class='alert alert-danger'>Analiz Hatası: {str(e)}</div>"

def analyze_cash_flow(cash_data_json):
    """
    Nakit akışını simüle eder ve likidite krizi uyarıları verir.
    """
    if not is_active:
        return "<div class='alert alert-warning'>AI Modülü kapalı.</div>"

    system_prompt = """
    Sen Şirketin CFO'su (Finans Direktörü) ve Kriz Yönetimi Uzmanısın.
    Sana şirketin şu anki nakit varlığı ve önümüzdeki 4 haftanın tahsilat/ödeme planı verilecek.
    
    Görevlerin:
    1.**Simülasyon:** Her haftanın sonunda kasanın artıda mı ekside mi olacağını yorumla.
    2.**Kriz Uyarısı:** Eğer herhangi bir hafta bakiye EKSİYE düşüyorsa "KIRMIZI ALARM" ver.
    3.**Kurtarma Planı:** - Nakit açığını kapatmak için hangi "Alınan Çeklerin" erken bozdurulabileceğini (faktoring vb.) öner.
       - Hangi ödemelerin (Verilen Çekler) ertelenebileceğini veya taksitlendirilebileceğini belirt.
    
    Çıktı Formatı:
    - HTML olarak ver.
    - Haftalık durum için bir tablo oluştur (Hafta, Giriş, Çıkış, Tahmini Bakiye, Durum).
    - Durum sütununda "Güvenli" (Yeşil) veya "Riskli" (Kırmızı) badge kullan.
    - En alta "CFO Tavsiyesi" başlıklı bir paragraf ekle.
    """
    
    user_prompt = f"Finansal Veriler:\n{cash_data_json}"
    
    return get_gemini_response(system_prompt, user_prompt)

def analyze_cross_sell(baskets_json):
    """
    Alışveriş sepetlerini analiz eder ve ürün eşleşmeleri (Bundle) önerir.
    """
    if not is_active:
        return "<div class='alert alert-warning'>AI Modülü kapalı.</div>"

    system_prompt = """
    Sen bir Veri Madencisi ve Pazarlama Stratejistisin.
    Sana son dönemdeki faturaların içeriği (hangi faturada hangi ürünler beraber satılmış) verilecek.
    
    Görevlerin:
    1.**Gizli İlişkileri Bul:** Hangi iki veya üç ürün sürekli beraber satılıyor? (Örn: Kahve & Şeker)
    2.**Satış Reçetesi Yaz:** Plasiyerlerin sahada kullanması için "Bunu soran müşteriye, şunu öner" şeklinde kısa replikler hazırla.
    3.**Kampanya Kurgula:** Beraber satılan ürünler için bir "İkili Fırsat Paketi" ismi ve sloganı uydur.
    
    Çıktı Formatı:
    - HTML Kartlar şeklinde (Bootstrap Card) sun.
    - Her ilişki için: "X Alanlar Y de Alıyor" başlığı, Oran tahmini ve Plasiyer Repliği olsun.
    """
    
    user_prompt = f"İşlenmiş Fatura Sepetleri:\n{baskets_json}"
    
    return get_gemini_response(system_prompt, user_prompt)

def analyze_anomalies(audit_data_json):
    """
    Şüpheli işlemleri (Yüksek iskonto, stok kaybı vb.) analiz eder.
    """
    if not is_active:
        return "<div class='alert alert-warning'>AI Modülü kapalı.</div>"

    system_prompt = """
    Sen Şüpheci bir İç Denetçi ve Dedektifsin.
    Sana şirketin işlem kayıtlarındaki potansiyel anomaliler (yüksek iskontolar, stok kayıpları) verilecek.
    
    Görevlerin:
    1.Sorgula: Neden bir faturada %20'den fazla indirim yapılmış? Bu bir hata mı, suiistimal mi?
    2.İncele: Depodan "Fire" veya "Sayım Eksiği" olarak çıkan malların miktarını ve değerini kontrol et.
    3.Raporla: Her şüpheli durumu ciddiyet derecesine göre (Düşük/Orta/Kritik) sınıflandır.
    
    ÇIKTI FORMATI KRİTİKTİR: SADECE GEÇERLİ BİR JSON OBJESİ DÖNDÜR.
    Tüm HTML içeriğini, 'rapor_html' anahtarının içine bir string olarak yerleştir.
    
    Örnek Format:
    {
      "durum": "Anomali Tespit Edildi",
      "kritik_vaka_sayisi": 2,
      "rapor_html": "<div class='alert alert-danger'>...DETAYLI HTML RAPORU BURAYA GELECEK...</div>"
    }
    """
    
    user_prompt = f"Denetim Verileri:\n{audit_data_json}"
    
    return get_gemini_response(system_prompt, user_prompt)

def analyze_check_image1(image_path):
    """
    Çek görselini AI'ya gönderir ve OCR verilerini JSON olarak döner.
    Otomatik Retry (Tekrar Deneme) mekanizması eklenmiştir.
    """
    if not is_active:
        return {"error": "AI Modülü aktif değil."}

    try:
        import PIL.Image
        img = PIL.Image.open(image_path)
        
        system_prompt = """
        Sen uzman bir bankacılık asistanısın.Sana verilen ÇEK görselini analiz et.
        Görselden aşağıdaki bilgileri okuyup SADECE geçerli bir JSON objesi döndür.
        Yorum veya markdown ekleme.
        
        İstenen JSON Formatı:
        {
            "cek_no": "...",
            "vade_tarihi": "YYYY-MM-DD",
            "tutar": 12345.50,
            "banka_adi": "...",
            "sube_adi": "...",
            "hesap_no": "...",
            "kesideci_vkn": "...",
            "kesideci_tckn": "...",
            "kesideci_unvan": "...",
            "iban": "TR..."
        }
        
        Okuyamadığın alanlar için null değeri ver.Tarih formatı YYYY-MM-DD olmalı.
        Tutar sadece sayı ve nokta (kuruş için) içermeli.
        """
        
        # ✅ STRATEJİ DEĞİŞİKLİĞİ:
        # Listenizdeki en kararlı ve kotası yüksek model budur.
        # "gemini-2.0" serisi deneysel olduğu için 429 hatası veriyor.
        model_name = "models/gemini-flash-latest" 
        
        print(f"📡 AI İsteği Gönderiliyor: {model_name}...") 
        
        model = genai.GenerativeModel(model_name)
        
        # Retry mantığı: Hata alırsa (429) 1 kere daha dener
        try:
            response = model.generate_content([system_prompt, img])
        except Exception as e:
            if "429" in str(e):
                print("⚠️ Kota aşıldı, 5 saniye bekleniyor...")
                time.sleep(5)
                # İkinci deneme (Daha hafif bir modelle veya aynısıyla)
                print("🔄 Tekrar deneniyor...")
                response = model.generate_content([system_prompt, img])
            else:
                raise e # Diğer hataları fırlat

        # Temizlik
        text = response.text.replace('```json', '').replace('```', '').strip()
        print(f"✅ AI Yanıtı: {text}") 
        
        return json.loads(text)
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Çek OCR Hatası: {error_msg}")
        
        # Kullanıcıya dostane hata mesajı
        if "429" in error_msg:
            return {"error": "Servis şu an çok yoğun (Kota Aşımı).Lütfen 30 saniye sonra tekrar deneyin."}
        
        return {"error": error_msg}

def optimize_sales_route1(start_location, customers_list):
    """
    Plasiyer rotasını optimize eder.
    
    :param start_location: "41.0082, 28.9784" (Ofis veya Plasiyerin anlık konumu)
    :param customers_list: Liste içinde Sözlük formatında müşteri verisi:
                           [{"id": 1, "unvan": "ABC Market", "konum": "41.0122, 28.9800", "bakiye": 5000}]
    :return: Optimize edilmiş rota sırası ve Google Maps linki (JSON)
    """
    
    if not is_active:
        return {"error": "AI Modülü aktif değil."}

    # Tarih ve saat bilgisi trafik tahmini için bağlam sağlar
    import datetime
    simdi = datetime.datetime.now().strftime("%A %H:%M")
    
    system_prompt = """
    Sen uzman bir Lojistik Planlama ve Rota Optimizasyon Yapay Zekasısın.
    Görevin: Bir satış temsilcisi (plasiyer) için verilen müşteri listesini EN KISA MESAFE ve EN AZ YAKIT tüketimi sağlayacak şekilde sıralamak.
    
    Kullanacağın Algoritma Mantığı:
    1.Başlangıç noktasından en yakın müşteriye git.
    2.Oradan bir sonraki en yakın müşteriye git (Nearest Neighbor Heuristic).
    3.Trafik akışını genel olarak (İstanbul/Türkiye şartlarına göre) dikkate alarak mantıklı bir güzergah çiz.
    
    GİRDİ FORMATI:
    - Başlangıç Konumu (Lat, Lng)
    - Müşteri Listesi (Unvan, Konum, Bakiye vb.)
    
    ÇIKTI FORMATI (SADECE SAF JSON):
    {
        "rota_siralamasi": [
            {"sira": 1, "unvan": "...", "mesafe_tahmini": "X km", "neden": "Başlangıca en yakın nokta"}
        ],
        "toplam_tahmini_mesafe": "XX km",
        "tasarruf_notu": "Bu rota ile yaklaşık %X yakıt tasarrufu sağlanır.",
        "google_maps_link": "https://www.google.com/maps/dir/..."
    }
    
    ÖNEMLİ: "google_maps_link" alanında, başlangıç noktasından başlayıp optimize ettiğin sıraya göre tüm koordinatları '/' ile birleştirerek çalışan bir navigasyon linki oluştur.
    Format: https://www.google.com/maps/dir/BASLANGIC_KOORD/MUSTERI_1_KOORD/MUSTERI_2_KOORD/...
    """
    
    # Kullanıcı verisini hazırla
    user_prompt = f"""
    Zaman: {simdi}
    Başlangıç Noktası: {start_location}
    
    Ziyaret Edilecek Müşteriler:
    {json.dumps(customers_list, ensure_ascii=False)}
    
    Lütfen bu listeyi en verimli rota olacak şekilde yeniden sırala.
    """
    
    print(f"📡 AI Rota Optimizasyonu İsteniyor ({len(customers_list)} durak)...")
    
    try:
        # JSON modunda yanıt al
        generation_config = {
            "temperature": 0.2, # Daha deterministik ve mantıklı olması için düşük sıcaklık
            "response_mime_type": "application/json"
        }
        
        model = genai.GenerativeModel(MODEL_NAME, generation_config=generation_config, system_instruction=system_prompt)
        response = model.generate_content(user_prompt)
        
        return json.loads(response.text)
        
    except Exception as e:
        return {"error": f"Rota oluşturulurken hata: {str(e)}"}

# ----------------------------------------------------------------
# 1.ROTA OPTİMİZASYONU (Metin)
# ----------------------------------------------------------------
def optimize_sales_route(start_location, customers_list):
    if not is_active or not ACTIVE_MODEL_NAME:
        return {"error": "AI Modülü aktif değil.API Key veya Model bulunamadı."}

    simdi = datetime.now().strftime("%A %H:%M")

    system_prompt = """
    Sen uzman bir Lojistik Planlama Yapay Zekasısın.
    Görevin: Verilen müşteri listesini EN KISA MESAFE ve EN AZ YAKIT tüketimi sağlayacak şekilde sıralamak.
    
    ÇIKTI FORMATI (SAF JSON):
    {
        "rota_siralamasi": [
            {
                "sira": 1, 
                "unvan": "Müşteri Adı", 
                "mesafe_tahmini": "X km", 
                "neden": "Başlangıca en yakın nokta"
            }
        ],
        "toplam_tahmini_mesafe": "XX km",
        "tasarruf_notu": "Bu rota ile yaklaşık %X yakıt tasarrufu sağlanır.",
        "google_maps_link": "URL"
    }
    
    GOOGLE MAPS LINK FORMATI:
    https://www.google.com/maps/dir/{BAŞLANGIÇ}/{KONUM_1}/{KONUM_2}/.../{KONUM_N}/{BAŞLANGIÇ}
    Konumlar "lat,lng" formatında olmalı.
    """
    
    user_prompt = f"""
    Zaman: {simdi}
    Başlangıç Noktası: {start_location}
    
    Ziyaret Edilecek Müşteriler:
    {json.dumps(customers_list, ensure_ascii=False)}
    
    Bu listeyi en verimli rota olacak şekilde sırala ve JSON döndür.
    """
    
    try:
        # Config (Sıcaklık 0.2 daha tutarlı sonuç verir)
        generation_config = {"temperature": 0.2}
        
        # Dinamik seçilen modeli kullan
        model = genai.GenerativeModel(ACTIVE_MODEL_NAME, generation_config=generation_config)
        
        response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
        
    except Exception as e:
        print(f"AI Rota Hatası: {e}")
        return {"error": f"Rota oluşturulamadı.({str(e)})"}

# ----------------------------------------------------------------
# 2.ÇEK ANALİZİ (Resim)
# ----------------------------------------------------------------
def analyze_check_image(image_path):
    if not is_active or not ACTIVE_MODEL_NAME:
        return {"error": "AI Modülü aktif değil."}

    try:
        import PIL.Image
        img = PIL.Image.open(image_path)
        
        # Not: Seçilen model sadece metin destekliyorsa (gemini-pro gibi),
        # resim gönderince hata verebilir.Bu yüzden resim için özel kontrol ekliyoruz.
        # Eğer aktif model 'vision' veya 'flash' veya '1.5' içermiyorsa uyarı verilebilir.
        # Ancak gemini-1.5 serisi (otomatik seçilirse) her ikisini de yapar.
        
        system_prompt = """
        Sen bir bankacılık asistanısın.Bu ÇEK görselini analiz et ve JSON ver.
        Format:
        {
            "cek_no": "...", "vade_tarihi": "YYYY-MM-DD", "tutar": 12345.50,
            "banka_adi": "...", "kesideci_vkn": "...", "kesideci_unvan": "..."
        }
        """
        
        model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
        response = model.generate_content([system_prompt, img])
        
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
        
    except Exception as e:
        print(f"Çek OCR Hatası: {e}")
        return {"error": f"Çek okunamadı: {str(e)}"}

# ----------------------------------------------------------------
# 3.YÖNETİCİ ÖZETLERİ (Metin)
# ----------------------------------------------------------------
def generate_ceo_briefing(summary_data_json):
    """
    Tüm modüllerden gelen verileri özetleyerek CEO için şık bir HTML brifing hazırlar.
    """
    if not is_active or not ACTIVE_MODEL_NAME:
        return "<div class='alert alert-warning shadow-sm'><i class='bi bi-exclamation-triangle me-2'></i>AI Modülü kapalı veya API Key eksik.</div>"

    system_prompt = """
    Sen bir Holding CEO'sunun Başdanışmanı ve Finansal Analistisin.
    Sana şirketin güncel finansal durumunu (Alacak/Borç, Kasa) ve riskli stok sayısını vereceğim.

    GÖREVLERİN:
    1. CEO'ya hitaben profesyonel ve enerjik bir giriş yap (Örn: "Günaydın Patron" veya "Değerli Yöneticim").
    2. Alacak/Borç dengesini analiz et. Eğer alacaklar yüksekse nakit akışını öv, borç fazlaysa tahsilat uyarısı yap.
    3. Kritik stok sayılarına dikkat çek ve "WMS üzerinden mal kabul" veya "Satınalma" talimatı ver.
    4. Bu verileri düz metin olarak DEĞİL; Bootstrap 5 class'larını kullanarak şık kutular (card), ikonlar (bi bi-...) ve renkli badge'ler (bg-success, bg-danger) ile harika bir tasarımla sun.
    5. En alta "Günün Stratejik Hamlesi:" adında altın değerinde tek cümlelik bir tavsiye yaz (Koyu renkli ve belirgin olsun).

    ÇIKTI KURALLARI:
    SADECE VE SADECE render edilebilir HTML kodu döndür. Markdown blokları (```html) veya ekstra metin KULLANMA.
    """
    
    try:
        model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
        response = model.generate_content([system_prompt, f"Bugünün ERP Verileri:\n{summary_data_json}"])
        
        # ✨ İŞTE HAYAT KURTARAN TIRAŞLAMA SATIRI:
        # Gelen yanıttaki o gereksiz ```html ve ``` işaretlerini siliyoruz
        html_cikti = response.text.replace('```html', '').replace('```', '').strip()
        
        return html_cikti
        
    except Exception as e:
        return f"<div class='alert alert-danger shadow-sm'>Yapay Zeka Analiz Hatası: {str(e)}</div>"
