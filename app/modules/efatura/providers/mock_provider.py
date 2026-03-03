from .base import BaseProvider
import time
import random

class MockProvider(BaseProvider):
    """
    Gerçek gönderim yapmadan sistemi test etmek için sahte sağlayıcı.
    """
    def connect(self):
        print("🔌 Mock API'ye sanal bağlantı kuruldu.")
        return True

    def send_invoice(self, ubl_xml, ettn, alici_vkn, alici_alias):
        print(f"🚀 MOCK GÖNDERİM:")
        print(f"   - ETTN: {ettn}")
        print(f"   - Alıcı: {alici_vkn} ({alici_alias})")
        print(f"   - XML Boyutu: {len(ubl_xml)} bytes")
        
        # Sanki internete gidiyormuş gibi bekle
        time.sleep(1.5)
        
        # Rastgele bir GİB takip numarası üret
        ref_no = f"GIB-{random.randint(100000, 999999)}"
        return True, ref_no

    def check_status(self, ettn):
        # Rastgele durum döndür
        durumlar = [
            (100, "Kuyruğa Alındı"),
            (120, "GİB'e Gönderildi"),
            (1300, "BAŞARIYLA TAMAMLANDI")
        ]
        return random.choice(durumlar)
        
    def is_euser(self, vkn):
        # Simülasyon: VKN '1' ile başlıyorsa E-Fatura mükellefi say
        vkn_str = str(vkn)
        if vkn_str.startswith("1"):
            return True, "urn:mail:defaultpk@gib.gov.tr"
        return False, None
        
    def get_incoming_invoices(self):
        """Inbox'a (Gelen Kutusuna) düşmüş sanal faturalar üretir"""
        import uuid, random
        from datetime import datetime, timedelta
        
        print("📥 MOCK API: Gelen faturalar sorgulanıyor...")
        time.sleep(1) # API Gecikmesi simülasyonu
        
        invoices = []
        for i in range(random.randint(2, 5)):
            invoices.append({
                'ettn': str(uuid.uuid4()),
                'fatura_no': f"TED2026{str(random.randint(100000000, 999999999))}",
                'gonderici_vkn': f"111111111{i}1",
                'gonderici_unvan': f"Örnek Tedarikçi ve San. Tic. A.Ş. - Şube {i}",
                'tarih': (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                'tutar': round(random.uniform(5000, 50000), 2),
                'para_birimi': 'TRY'
            })
        return invoices