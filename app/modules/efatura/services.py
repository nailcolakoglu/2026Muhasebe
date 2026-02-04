# app/modules/efatura/services.py

from .ubl_builder import UBLBuilder
from app.extensions import db
from app.modules.efatura.models import EntegratorAyarlari 
from app.modules.fatura.models import Fatura
from app.modules.firmalar.models import Firma
from .providers.mock_provider import MockProvider

class EntegratorService:
    def __init__(self, firma_id):
        # Ayarları veritabanından çek (Model henüz yoksa mock kullanırız)
        self.ayarlar = EntegratorAyarlari.query.filter_by(firma_id=firma_id, aktif=True).first()
        
        # --- MOCK FALLBACK (Ayarlar tablosu boşsa test için) ---
        if not self.ayarlar:
            print("⚠️ UYARI: Entegratör ayarı bulunamadı, MOCK modunda çalışılıyor.")
            self.provider = MockProvider("test", "test", "http://mock.api")
            return
        # -------------------------------------------------------

        # Factory Pattern: Sağlayıcı Seçimi
        if self.ayarlar.provider == 'MOCK':
            self.provider = MockProvider(self.ayarlar.username, self.ayarlar.password, self.ayarlar.api_url)
        elif self.ayarlar.provider == 'UYUMSOFT':
            # self.provider = UyumsoftProvider(...) # İleride eklenecek
            raise NotImplementedError("Uyumsoft entegrasyonu henüz aktif değil.")
        else:
            raise Exception("Tanımsız entegratör sağlayıcısı!")

    def mukellef_kontrol(self, vkn):
        """Alıcının E-Fatura mükellefi olup olmadığını kontrol eder"""
        return self.provider.is_euser(vkn)

    def fatura_gonder(self, fatura_id):
        fatura = Fatura.query.get(fatura_id)
        if not fatura: return False, "Fatura bulunamadı."
        
        try:
            satici_firma = Firma.query.get(fatura.firma_id)
            
            # 1.Mükellef Kontrolü
            is_efatura, pk_alias = self.mukellef_kontrol(fatura.cari.vergi_no)
            
            # Senaryo Kontrolü (Örn: E-Arşiv seçilmişse E-Fatura'ya zorlama vb.)
            # Şimdilik basit tutuyoruz.
            if not pk_alias:
                pk_alias = "defaultpk" # Alias yoksa varsayılan (Mock için)

            # 2.XML Oluştur (LXML ile)
            builder = UBLBuilder(fatura, satici_firma)
            xml_content = builder.build_xml()
            
            # 3.Sağlayıcıya Gönder
            basarili, ref_no = self.provider.send_invoice(
                xml_content, 
                fatura.ettn, 
                fatura.cari.vergi_no, 
                pk_alias
            )
            
            if basarili:
                # Veritabanını Güncelle
                fatura.gib_durum_kodu = 100
                fatura.gib_durum_aciklama = f"Entegratöre iletildi.Ref: {ref_no}"
                # İleride XML dosyasını diske kaydetmek iyi olur
                db.session.commit()
                return True, f"Fatura başarıyla gönderildi.Takip No: {ref_no}"
            else:
                return False, f"Entegratör Hatası: {ref_no}"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Sistem Hatası: {str(e)}"