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