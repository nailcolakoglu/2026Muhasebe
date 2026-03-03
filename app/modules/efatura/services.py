# app/modules/efatura/services.py

import logging
from .ubl_builder import UBLBuilder
from app.extensions import get_tenant_db
from app.modules.efatura.models import EntegratorAyarlari 
from app.modules.fatura.models import Fatura
from app.modules.firmalar.models import Firma
from .providers.mock_provider import MockProvider

# ✨ EKLENDİ: Enterprise Loglama
logger = logging.getLogger(__name__)

class EntegratorService:
    def __init__(self, firma_id):
        self.tenant_db = get_tenant_db()
        self.firma_id = firma_id
        
        self.ayarlar = self.tenant_db.query(EntegratorAyarlari).filter_by(firma_id=firma_id, aktif=True).first()
        
        if not self.ayarlar:
            logger.warning(f"Firma_id: {firma_id} için Entegratör ayarı bulunamadı, MOCK modunda çalışılıyor.")
            self.provider = MockProvider("test", "test", "http://mock.api")
            return

        if self.ayarlar.provider == 'MOCK':
            self.provider = MockProvider(self.ayarlar.username, self.ayarlar.password, self.ayarlar.api_url)
        elif self.ayarlar.provider == 'UYUMSOFT':
            from .providers.uyumsoft_provider import UyumsoftProvider
            self.provider = UyumsoftProvider(self.ayarlar.username, self.ayarlar.password, self.ayarlar.api_url)
        else:
            raise ValueError(f"Tanımsız entegratör sağlayıcısı: {self.ayarlar.provider}")

    def durum_sorgula(self, fatura_id):
        """
        Faturanın GİB'deki durumunu entegratör üzerinden sorgular ve veritabanını günceller.
        """
        fatura = self.tenant_db.query(Fatura).get(fatura_id)
        if not fatura: 
            return False, "Fatura bulunamadı."
            
        if not fatura.ettn:
            return False, "Bu faturanın ETTN numarası yok. Henüz gönderilmemiş olabilir."

        try:
            # Entegratörden durumu çek (Uyumsoft veya Mock)
            gib_kod, gib_mesaj = self.provider.check_status(fatura.ettn)
            
            if gib_kod is not None:
                # Veritabanını yeni durum ile güncelle
                fatura.gib_durum_kodu = gib_kod
                fatura.gib_durum_aciklama = gib_mesaj
                
                # 1300 Kodu GİB'de "Başarıyla Tamamlandı" anlamına gelir.
                if gib_kod == 1300:
                    # Gerekirse fatura genel durumunu da kilitleyebiliriz (örn: ONAYLANDI)
                    pass 
                elif gib_kod in [1163, 1162, 1143]: 
                    # Hata kodlarından bazıları. Gerekirse faturayı düzeltmeye açabiliriz.
                    pass

                self.tenant_db.commit()
                return True, f"Durum Güncellendi: {gib_kod} - {gib_mesaj}"
            else:
                return False, "Entegratörden durum bilgisi alınamadı."

        except Exception as e:
            self.tenant_db.rollback()
            import logging
            logging.getLogger(__name__).error(f"Fatura Durum Sorgulama Hatası (ID: {fatura_id}): {str(e)}", exc_info=True)
            return False, f"Sistem Hatası: {str(e)}"
            
    def mukellef_kontrol(self, vkn):
        return self.provider.is_euser(vkn)

    def fatura_gonder(self, fatura_id):
        # Senin mevcut veritabanı bağlantı mantığın
        fatura = self.tenant_db.query(Fatura).get(fatura_id)
        
        if not fatura: 
            return False, "Fatura bulunamadı."
            
        if fatura.gib_durum_kodu == 1300:
            return False, "Bu fatura zaten GİB'e başarıyla gönderilmiş!"
        
        try:
            satici_firma = self.tenant_db.query(Firma).get(fatura.firma_id)
            cari_vkn = fatura.cari.vergi_no or fatura.cari.tc_kimlik_no or '11111111111'
            
            # ✨ YENİ: Zaten senin yazdığın mukellef_kontrol'ü kullanarak akıllı yönlendirme yapıyoruz
            is_efatura, pk_alias = self.mukellef_kontrol(cari_vkn)
            
            # --- AKILLI KARAR MEKANİZMASI ---
            if is_efatura:
                fatura.e_fatura_senaryo = "TICARIFATURA"
                if not pk_alias:
                    pk_alias = "urn:mail:defaultpk@gib.gov.tr" 
                fatura.alici_etiket_pk = pk_alias
                belge_turu_mesaj = "E-Fatura"
            else:
                fatura.e_fatura_senaryo = "EARSIVFATURA"
                fatura.alici_etiket_pk = None
                pk_alias = "urn:mail:defaultpk@gib.gov.tr" # Bazı entegratörler E-Arşiv'de de default bir PK ister, burası senin provider'ına göre değişebilir
                belge_turu_mesaj = "E-Arşiv Fatura"
            # --------------------------------

            # Senin çalışan UBL ve Provider kodların (Hiç dokunulmadı)
            builder = UBLBuilder(fatura, satici_firma)
            xml_content = builder.build_xml()
            
            basarili, ref_no = self.provider.send_invoice(
                xml_content, 
                fatura.ettn, 
                cari_vkn, 
                pk_alias
            )
            
            if basarili:
                fatura.gib_durum_kodu = 100
                fatura.gib_durum_aciklama = f"{belge_turu_mesaj} entegratöre iletildi. Ref: {ref_no}"
                self.tenant_db.commit()
                
                # ✨ YENİ: CELERY E-ARŞİV MAİL OTOMASYONU
                mesaj_eki = ""
                if not is_efatura and fatura.cari.eposta:
                    from app.modules.efatura.tasks import send_earsiv_mail_async
                    # 👇 DÜZELTME: İşçiye firma_id bilgisini de gönderiyoruz ki DB'yi bulabilsin
                    send_earsiv_mail_async.delay(str(fatura.id), fatura.cari.eposta, str(self.firma_id))
                    mesaj_eki = " ve müşteriye e-posta gönderimi başlatıldı."
                    
                return True, f"{belge_turu_mesaj} başarıyla kuyruğa alındı. Takip No: {ref_no}{mesaj_eki}"
            else:
                return False, f"Entegratör Hatası: {ref_no}"

        except Exception as e:
            self.tenant_db.rollback()
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Fatura Gönderim Hatası (ID: {fatura_id}): {str(e)}", exc_info=True)
            return False, f"Sistem Hatası: {str(e)}"
            
    def mukellef_sorgula(self, vkn_tckn):
        """
        GİB veya Entegratör API'si üzerinden VKN/TCKN'nin 
        E-Fatura sistemine kayıtlı olup olmadığını sorgular.
        """
        if not vkn_tckn:
            return False
            
        # NOT: Gerçek bir entegratörde (Uyumsoft, Logo vb.) buraya API isteği atılır.
        # Biz şu an Enterprise mimarinin simülasyonunu yapıyoruz:
        # Kural: 11 haneli (TCKN) ise Şahıs/Son Tüketicidir -> E-Arşiv
        # Kural: 10 haneli (VKN) ise Şirkettir -> E-Fatura kabul ediyoruz.
        
        vkn_tckn = str(vkn_tckn).strip()
        if len(vkn_tckn) == 11:
            return False # E-Arşiv kesilecek
        elif len(vkn_tckn) == 10:
            return True  # E-Fatura kesilecek
            
        return False
    
    def gelen_faturalari_getir(self):
        try:
            # Sağlayıcıdan (Mock veya Uyumsoft) gelen faturaları çek
            return self.provider.get_incoming_invoices()
        except AttributeError:
            return [] # Eğer provider'da bu metot yoksa boş liste dön
        except Exception as e:
            logger.error(f"Gelen fatura çekme hatası: {e}")
            return []

    def faturayi_iceri_al(self, ettn, vkn, unvan, belge_no, tarih, tutar):
        """Gelen e-Faturayı ERP'ye Alış Faturası olarak işler ve Cariyi borçlandırır"""
        from app.modules.cari.models import CariHesap
        from app.modules.firmalar.models import Donem
        from app.modules.sube.models import Sube
        from app.modules.depo.models import Depo # ✨ EKLENDİ: Depo Modeli
        from app.modules.fatura.models import Fatura
        from app.modules.cari.services import CariService
        from datetime import datetime
        
        # 1. Mükerrer Kontrolü
        if self.tenant_db.query(Fatura).filter_by(firma_id=self.firma_id, ettn=ettn).first():
            return False, "Bu e-Fatura zaten sistemde mevcut!"

        # 2. Cari Bul veya Otomatik Yarat
        cari = self.tenant_db.query(CariHesap).filter_by(firma_id=self.firma_id, vergi_no=vkn).first()
        if not cari:
            cari = self.tenant_db.query(CariHesap).filter_by(firma_id=self.firma_id, tc_kimlik_no=vkn).first()

        if not cari:
            cari = CariHesap(
                firma_id=self.firma_id,
                kod=f"TED-{vkn}",
                unvan=unvan,
                vergi_no=vkn if len(vkn) == 10 else None,
                tc_kimlik_no=vkn if len(vkn) == 11 else None,
                aktif=True
            )
            self.tenant_db.add(cari)
            self.tenant_db.flush() 

        # ✨ YENİ: Dönem, Şube ve DEPO bulma
        donem = self.tenant_db.query(Donem).filter_by(firma_id=self.firma_id, aktif=True).first()
        sube = self.tenant_db.query(Sube).filter_by(firma_id=self.firma_id, aktif=True).first()
        depo = self.tenant_db.query(Depo).filter_by(firma_id=self.firma_id, aktif=True).first()
        
        # Eğer sistemde hiç depo yoksa mantıklı bir hata mesajı verelim
        if not depo:
            return False, "Sistemde aktif bir depo bulunamadı! Lütfen önce Depo Yönetiminden bir depo tanımlayın."

        # 3. Alış Faturası Oluştur
        yeni_fatura = Fatura(
            firma_id=self.firma_id,
            donem_id=str(donem.id) if donem else None,
            sube_id=str(sube.id) if sube else None,
            depo_id=str(depo.id), # ✨ EKLENDİ: Fatura artık sahipsiz kalmayacak
            cari_id=str(cari.id),
            fatura_turu='ALIS',
            belge_no=belge_no,
            ettn=ettn,
            tarih=datetime.strptime(tarih, '%Y-%m-%d').date(),
            ara_toplam=float(tutar) / 1.20, 
            kdv_toplam=float(tutar) - (float(tutar) / 1.20),
            genel_toplam=float(tutar),
            doviz_turu='TL',
            durum='ONAYLANDI',
            gib_durum_kodu=1300,
            aciklama="E-Fatura Inbox'tan otomatik içeri alındı."
        )
        self.tenant_db.add(yeni_fatura)
        self.tenant_db.flush()

        # 4. Cari Bakiyeyi Otomatik Güncelle (Tedarikçi bizden alacaklı oldu)
        CariService.hareket_ekle(
            cari_id=str(cari.id),
            islem_turu='ALIS_FATURASI',
            belge_no=belge_no,
            tarih=yeni_fatura.tarih,
            aciklama=f"Gelen E-Fatura: {belge_no}",
            borc=0,
            alacak=float(tutar), 
            kaynak_ref={'tur': 'FATURA', 'id': str(yeni_fatura.id)},
            # 👇 DÜZELTME: firma_id, donem_id ve sube_id parametrelerini sildik! 
            # (Çünkü CariService bunları aktif kullanıcıdan kendi otomatik alıyor)
            tenant_db=self.tenant_db
        )
        
        self.tenant_db.commit()
        return True, "Fatura içeri alındı ve Cari Hesaba başarıyla işlendi."        