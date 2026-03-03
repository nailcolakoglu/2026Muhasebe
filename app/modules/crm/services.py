# app/modeles/crm/services.py

import logging
from app.extensions import get_tenant_db
from app.modules.crm.models import AdayMusteri, SatisFirsati, CrmAktivite
from datetime import datetime
from flask_babel import gettext as _

logger = logging.getLogger(__name__)

class CrmService:
    
    @staticmethod
    def _hesapla_ai_olasilik(firsat):
        """
        Fırsat verilerine göre kazanma olasılığını ve analizini hesaplar.
        """
        skor = 20 # Baz puan
        analiz_notlari = []
        
        try:
            # Tutar Analizi
            tutar = float(firsat.tahmini_tutar or 0)
            if 0 < tutar <= 25000:
                skor += 40
                analiz_notlari.append(_("Düşük tutarlı fırsat: Kapanış ihtimali yüksek."))
            elif tutar > 100000:
                skor -= 10
                analiz_notlari.append(_("Yüksek tutarlı proje: Uzun onay süreci gerekebilir."))
            else:
                skor += 20

            # Müşteri İlişkisi Skoru
            if firsat.cari_id:
                skor += 30
                analiz_notlari.append(_("Mevcut müşteri: Güvenli ve tanıdık portföy."))
            elif firsat.aday_id:
                skor += 10
                analiz_notlari.append(_("Yeni aday müşteri: İlk ikna süreci devam ediyor."))

            # Tarih Analizi
            if firsat.beklenen_kapanis_tarihi:
                from datetime import date
                today = date.today()
                # Eğer tarih objesi değilse parse et (güvenlik için)
                if isinstance(firsat.beklenen_kapanis_tarihi, str):
                    kapanis_tarihi = datetime.strptime(firsat.beklenen_kapanis_tarihi, '%Y-%m-%d').date()
                else:
                    kapanis_tarihi = firsat.beklenen_kapanis_tarihi
                
                gun_farki = (kapanis_tarihi - today).days
                if 0 <= gun_farki <= 15:
                    skor += 15
                    analiz_notlari.append(_("Kapanış tarihi yakın: Sıcak takipte."))
                elif gun_farki < 0:
                    skor -= 30
                    analiz_notlari.append(_("⚠️ Beklenen kapanış tarihi geçmiş!"))

        except Exception as e:
            logger.error(f"AI Hesaplama Hatası: {str(e)}")
            analiz_notlari.append(f"Hesaplama hatası: {str(e)}")

        final_skor = max(5, min(95, skor))
        return final_skor, {"analiz": analiz_notlari}

    @staticmethod
    def _save_logic(model_instance, data):
        """MySQL UUID ve Null uyumluluğunu sağlayan ortak mantık."""
        for key, value in data.items():
            if hasattr(model_instance, key) and key not in ['id', 'firma_id']:
                # Boş string gelirse MySQL FK hatası vermesin diye None yapıyoruz
                val = value if (value != '' and value is not None) else None
                setattr(model_instance, key, val)
        return model_instance

    @classmethod
    def firsat_kaydet(cls, data, firma_id, firsat_id=None):
        tenant_db = get_tenant_db()
        try:
            # 1. Kaydı bul veya oluştur
            firsat = tenant_db.get(SatisFirsati, str(firsat_id)) if firsat_id else SatisFirsati(firma_id=firma_id)
            if not firsat: return False, "Kayıt bulunamadı."
            
            # 2. Form verilerini nesneye işle
            firsat = cls._save_logic(firsat, data)
            
            # 3. AI HESAPLA (Burada artık veriler nesneye işlendiği için sonuç doğru çıkar)
            # ÖNEMLİ: Bu fonksiyon nesne üzerindeki cari_id ve aday_id'ye bakarak isim sorununu da çözer
            olasilik, analiz = cls._hesapla_ai_olasilik(firsat)
            firsat.ai_olasilik = olasilik
            firsat.ai_analiz = analiz

            if not firsat_id: tenant_db.add(firsat)
            tenant_db.commit()
            return True, firsat.id
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"Fırsat Kayıt Hatası: {str(e)}")
            return False, str(e)

    @staticmethod
    def aday_kaydet(data, firma_id, aday_id=None):
        """Aday Müşteri Ekleme/Güncelleme İş Mantığı"""
        tenant_db = get_tenant_db()
        
        try:
            if aday_id:
                aday = tenant_db.get(AdayMusteri, str(aday_id))
                if not aday:
                    return False, "Aday bulunamadı."
            else:
                aday = AdayMusteri(firma_id=firma_id)
                tenant_db.add(aday)

            # Boş stringleri None'a çevir (MySQL UUID uyumu için kritik)
            for key, value in data.items():
                if hasattr(aday, key) and key != 'id':
                    if isinstance(value, str) and value.strip() == '':
                        value = None
                    setattr(aday, key, value)

            tenant_db.commit()
            action = "Güncellendi" if aday_id else "Eklendi"
            logger.info(f"✅ Aday Müşteri {action}: {aday.unvan}")
            return True, f"Aday başarıyla {action.lower()}."
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Aday Kayıt Hatası: {str(e)}")
            return False, f"Sistem hatası: {str(e)}"

    @staticmethod
    def aktivite_kaydet(data, firma_id, kullanici_id, aktivite_id=None):
        tenant_db = get_tenant_db()
        try:
            if aktivite_id:
                aktivite = tenant_db.get(CrmAktivite, str(aktivite_id))
                if not aktivite: return False, "Aktivite bulunamadı."
            else:
                aktivite = CrmAktivite(firma_id=firma_id, kullanici_id=kullanici_id)
                tenant_db.add(aktivite)

            for key, value in data.items():
                if hasattr(aktivite, key) and key not in ['id', 'kullanici_id', 'firma_id']:
                    if isinstance(value, str) and value.strip() == '':
                        value = None
                    
                    # Checkbox (boolean) kontrolü
                    if key == 'tamamlandi':
                        value = str(value).lower() in ['true', 'on', '1']
                        
                    setattr(aktivite, key, value)

            # Tarih formatlaması
            if isinstance(aktivite.tarih, str):
                aktivite.tarih = datetime.strptime(aktivite.tarih, '%Y-%m-%d')

            tenant_db.commit()
            return True, "Aktivite başarıyla kaydedildi."
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Aktivite Kayıt Hatası: {str(e)}")
            return False, f"Sistem hatası: {str(e)}"
            
    @staticmethod
    def firsat_asama_degistir(firsat_id, yeni_asama_id, firma_id, kullanici_id):
        """Pipeline sürükle-bırak işlemi sırasında loglama yaparak aşamayı günceller."""
        tenant_db = get_tenant_db()
        try:
            from app.modules.crm.models import SatisAsamasi, CrmFirsatLogu # İçeride import güvenlik amaçlı
            
            firsat = tenant_db.get(SatisFirsati, str(firsat_id))
            if not firsat or firsat.firma_id != firma_id: 
                return False
                
            eski_asama_id = firsat.asama_id
            if eski_asama_id == yeni_asama_id: 
                return True # Aşama değişmediyse loglama yapma
                
            # Aşama isimlerini bulalım (Log açıklaması şık dursun diye)
            eski_asama = tenant_db.get(SatisAsamasi, eski_asama_id) if eski_asama_id else None
            yeni_asama = tenant_db.get(SatisAsamasi, yeni_asama_id) if yeni_asama_id else None
            
            eski_ad = eski_asama.ad if eski_asama else "Belirsiz"
            yeni_ad = yeni_asama.ad if yeni_asama else "Belirsiz"
            
            # 1. Fırsatın aşamasını güncelle
            firsat.asama_id = yeni_asama_id
            
            # 2. Hareketi Logla
            log = CrmFirsatLogu(
                firma_id=firma_id,
                firsat_id=firsat.id,
                kullanici_id=kullanici_id,
                islem_turu="ASAMA_DEGISIMI",
                eski_deger=str(eski_asama_id),
                yeni_deger=str(yeni_asama_id),
                aciklama=f"Aşama değiştirildi: {eski_ad} ➔ {yeni_ad}"
            )
            
            tenant_db.add(log)
            tenant_db.commit()
            return True
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"Aşama Değişim Hatası: {str(e)}")
            return False

    @staticmethod
    def _simulate_ai_sentiment(metin):
        """
        Gelecekteki NLP / Yapay Zeka entegrasyonu için ayrılmış soket.
        Şimdilik basit bir anahtar kelime analizi yapıyor.
        """
        if not metin: return None, None
        metin = metin.lower()
        if any(kelime in metin for kelime in ['kızgın', 'iptal', 'şikayet', 'kötü', 'mahkeme']):
            return 'SINIRLI', 2
        elif any(kelime in metin for kelime in ['harika', 'teşekkür', 'memnun', 'süper', 'onay']):
            return 'MUTLU', 9
        return 'NORMAL', 5

    @classmethod
    def hareket_kaydet(cls, data, firma_id, kullanici_id, hareket_id=None):
        tenant_db = get_tenant_db()
        from app.modules.crm.models import CrmHareketi # İçeride import
        
        try:
            if hareket_id:
                hareket = tenant_db.get(CrmHareketi, str(hareket_id))
                if not hareket: return False, "Kayıt bulunamadı."
            else:
                hareket = CrmHareketi(firma_id=firma_id, plasiyer_id=kullanici_id)
                tenant_db.add(hareket)

            # Checkbox ve null kontrolleri
            for key, value in data.items():
                if hasattr(hareket, key) and key not in ['id', 'firma_id', 'plasiyer_id']:
                    if isinstance(value, str) and value.strip() == '':
                        value = None
                    if key in ['aksiyon_gerekli', 'aksiyon_tamamlandi']:
                        value = str(value).lower() in ['true', 'on', '1']
                    setattr(hareket, key, value)

            # Tarih formatlamaları
            if isinstance(hareket.tarih, str) and hareket.tarih:
                from datetime import datetime
                hareket.tarih = datetime.strptime(hareket.tarih, '%Y-%m-%d')
            if isinstance(hareket.aksiyon_tarihi, str) and hareket.aksiyon_tarihi:
                hareket.aksiyon_tarihi = datetime.strptime(hareket.aksiyon_tarihi, '%Y-%m-%d')

            # ✨ AI Duygu Analizi Entegrasyonu
            # Formdan gelen değerin obje mi yoksa düz metin mi (string) olduğunu güvenlice yakalıyoruz
            guncel_duygu = hareket.duygu_durumu.name if hasattr(hareket.duygu_durumu, 'name') else str(hareket.duygu_durumu)

            # Eğer kullanıcı duygu durumunu manuel seçmediyse veya notu değiştirdiyse AI analiz yapsın
            if hareket.detay_notu and (not hareket.duygu_durumu or guncel_duygu == 'BELIRSIZ' or guncel_duygu == 'None'):
                duygu, skor = cls._simulate_ai_sentiment(hareket.detay_notu)
                if duygu:
                    hareket.duygu_durumu = duygu
                    hareket.memnuniyet_skoru = skor
                    hareket.ai_metadata = {"analiz_tipi": "otomatik_anahtar_kelime", "guven_skoru": 0.85}

            tenant_db.commit()
            return True, "Etkileşim başarıyla kaydedildi."
            
        except Exception as e:
            tenant_db.rollback()
            import logging
            logging.getLogger(__name__).error(f"Hareket Kayıt Hatası: {str(e)}")
            return False, f"Sistem hatası: {str(e)}"


