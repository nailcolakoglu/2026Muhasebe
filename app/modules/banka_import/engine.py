# app/modules/banka_import/engine.py

import pandas as pd
import hashlib
import re
from datetime import datetime
from app.extensions import db 
from app.modules.cari.models import CariHesap
from .models import BankaImportKurali, BankaImportGecmisi

class BankaImportEngine:
    def __init__(self, firma_id):
        self.firma_id = firma_id
        
        # Kuralları Yükle
        self.kurallar = BankaImportKurali.query.filter_by(firma_id=firma_id).all()
        
        # Carileri Yükle
        # Performans için sadece gerekli alanları çekiyoruz
        cariler_raw = db.session.query(CariHesap.id, CariHesap.unvan, CariHesap.vergi_no).filter_by(firma_id=firma_id, aktif=True).all()
        
        self.cari_listesi = []
        self.vkn_map = {} 
        
        for c in cariler_raw:
            self.cari_listesi.append({
                'id': c.id,
                'unvan': c.unvan,
                'unvan_clean': self._temizle(c.unvan) # Önceden temizlenmiş halini sakla (Hız için)
            })
            if c.vergi_no:
                vkn_clean = str(c.vergi_no).strip()
                if len(vkn_clean) >= 10:
                    self.vkn_map[vkn_clean] = {'id': c.id, 'unvan': c.unvan}

    def _temizle(self, text):
        """
        Metni temizler: Türkçe karakterleri düzeltir, noktalama işaretlerini siler,
        şirket uzantılarını (A.Ş, LTD) kaldırır.
        """
        if not text: return set()
        
        # 1.Türkçe Karakter Düzeltme ve Büyütme
        tr_map = str.maketrans("ğüşıöçĞÜŞİÖÇ", "GUSIOCGUSIOC")
        text = text.translate(tr_map).upper()
        
        # 2.Gereksiz Kelimeler (Stop Words)
        stop_words = [
            'AS', 'AS.', 'A.S.', 'LTD', 'LTD.', 'STI', 'STI.', 'TIC', 'TIC.', 'SAN', 'SAN.', 
            'VE', 'LIMITED', 'SIRKETI', 'TURIZM', 'INSAAT', 'GIDA', 'OTOMOTIV', 'TEKSTIL',
            'IHRACAT', 'ITHALAT', 'ANKARA', 'ISTANBUL', 'IZMIR', 'TR'
        ]
        
        # 3.Kelimelere Böl ve Filtrele
        # Sadece harf ve rakamları al (Noktalama işaretlerini boşluğa çevir)
        text = re.sub(r'[^A-Z0-9\s]', ' ', text)
        words = text.split()
        
        # Anlamsız kelimeleri at ve SET (küme) olarak döndür
        meaningful_words = set([w for w in words if w not in stop_words and len(w) > 2])
        
        return meaningful_words

    def dosya_hash_hesapla(self, file_stream):
        """Dosyanın benzersiz parmak izini çıkarır"""
        file_stream.seek(0)
        content = file_stream.read()
        file_stream.seek(0)
        return hashlib.sha256(content).hexdigest()

    def mukerrer_dosya_kontrol(self, file_hash):
        """Daha önce yüklenmiş mi kontrol eder"""
        return BankaImportGecmisi.query.filter_by(firma_id=self.firma_id, dosya_hash=file_hash).first()

    def excel_oku_ve_isle(self, file_stream, sablon):
        try:
            # 1.Motor Seçimi (.xls ve .xlsx desteği)
            is_xls = file_stream.filename.lower().endswith('.xls')
            engine = 'xlrd' if is_xls else 'openpyxl'
            
            # 2.Pandas ile Excel Oku
            # header=...parametresi 0'dan başlar.Kullanıcı 10 girdiyse Pandas için 9.satırdır.
            header_index = max(0, sablon.baslangic_satiri - 1)
            
            try:
                df = pd.read_excel(file_stream, header=header_index, engine=engine)
            except Exception as read_err:
                raise Exception(f"Excel dosyası okunamadı.'xlrd' veya 'openpyxl' kütüphanesi yüklü mü? Hata: {str(read_err)}")
            
            # 3.Sütun Kontrolü (Kullanıcıya net bilgi vermek için)
            gerekli_sutunlar = [sablon.col_tarih, sablon.col_aciklama]
            if sablon.tutar_yapis_tipi == 'tek':
                gerekli_sutunlar.append(sablon.col_tutar)
            else:
                gerekli_sutunlar.append(sablon.col_borc)
                gerekli_sutunlar.append(sablon.col_alacak)
            
            # Excel'deki sütunları temizle (boşlukları sil)
            df.columns = [str(c).strip() for c in df.columns]
            
            # Eksik sütun var mı kontrol et
            eksik_sutunlar = [col for col in gerekli_sutunlar if col and col not in df.columns]
            if eksik_sutunlar:
                raise Exception(f"Şablonda belirtilen şu sütunlar Excel dosyasında bulunamadı: {', '.join(eksik_sutunlar)}.Excel'deki başlıkların tam adını yazdığınızdan emin olun.")

            islenmis_veri = []
            
            for index, row in df.iterrows():
                # Veri Güvenliği: Tarih sütunu boşsa satırı atla
                if pd.isna(row.get(sablon.col_tarih)): continue

                # Verileri Al
                tarih_raw = row[sablon.col_tarih]
                aciklama = str(row[sablon.col_aciklama]).strip() if pd.notnull(row.get(sablon.col_aciklama)) else ""
                belge_no = str(row[sablon.col_belge_no]) if sablon.col_belge_no and pd.notnull(row.get(sablon.col_belge_no)) else ""
                
                # Tarih Formatlama
                try:
                    tarih_obj = None
                    if isinstance(tarih_raw, str):
                        # Enpara'da saat bilgisi de gelebilir, sadece tarihi al
                        tarih_clean = tarih_raw.split()[0] 
                        tarih_obj = datetime.strptime(tarih_clean, sablon.tarih_formati).date()
                    elif isinstance(tarih_raw, datetime):
                        tarih_obj = tarih_raw.date()
                    elif hasattr(tarih_raw, 'date'): # Timestamp ise
                        tarih_obj = tarih_raw.date()
                        
                    if not tarih_obj: continue
                except Exception as date_err:
                    print(f"Satır {index+1} Tarih Hatası: {tarih_raw} - {str(date_err)}")
                    continue # Tarih hatası varsa satırı atla

                # Tutar Hesaplama
                tutar = 0.0
                yon = 'giris'
                
                if sablon.tutar_yapis_tipi == 'tek':
                    val = row.get(sablon.col_tutar)
                    if pd.notnull(val):
                        # Enpara'da binlik ayracı nokta, ondalık virgül olabilir veya tam tersi.
                        # Pandas genelde float okur ama string gelirse temizle:
                        if isinstance(val, str):
                            val = val.replace('.', '').replace(',', '.')
                        
                        try:
                            ham_tutar = float(val)
                        except:
                            ham_tutar = 0

                        if ham_tutar < 0:
                            yon = 'cikis'
                            tutar = abs(ham_tutar)
                        else:
                            yon = 'giris'
                            tutar = ham_tutar
                else:
                    # Çift Sütun Mantığı (Borç/Alacak Ayrı Sütunlar)
                    borc_val = row.get(sablon.col_borc)
                    alacak_val = row.get(sablon.col_alacak)
                    
                    try:
                        borc = float(str(borc_val).replace('.', '').replace(',', '.')) if pd.notnull(borc_val) else 0
                        alacak = float(str(alacak_val).replace('.', '').replace(',', '.')) if pd.notnull(alacak_val) else 0
                    except:
                        borc, alacak = 0, 0
                    
                    if borc > 0:
                        yon = 'giris'
                        tutar = borc
                    elif alacak > 0:
                        yon = 'cikis'
                        tutar = alacak
                    else:
                        continue # 0 liralık işlem

                # --- YAPAY ZEKA VE EŞLEŞTİRME ---
                net_tutar = tutar 
                eslesme = self.akilli_eslestirme(aciklama, net_tutar)
                
                satir_verisi = {
                    'tarih': tarih_obj.strftime('%Y-%m-%d'),
                    'aciklama': aciklama,
                    'belge_no': belge_no,
                    'tutar': tutar,
                    'yon': yon,
                    'oneri': eslesme
                }
                islenmis_veri.append(satir_verisi)
                
            return islenmis_veri

        except Exception as e:
            # Hata detayını tam olarak döndür
            import traceback
            traceback.print_exc() # Terminale bas
            raise Exception(f"İşlem Hatası: {str(e)}")

    def akilli_eslestirme(self, aciklama, net_tutar):
        """
        Gelişmiş Eşleştirme Algoritması
        """
        # 1.ADIM: MEVCUT KURALLAR (En Hızlısı - Kesin Eşleşme)
        aciklama_upper = str(aciklama).upper()
        for kural in self.kurallar:
            if kural.anahtar_kelime.upper() in aciklama_upper:
                return self._kural_sonuc_olustur(kural, net_tutar)

        # 2.ADIM: VKN/TCKN ARAMA (Kesin Eşleşme)
        potansiyel_vknler = re.findall(r'\b\d{10,11}\b', str(aciklama))
        for vkn in potansiyel_vknler:
            if vkn in self.vkn_map:
                cari_data = self.vkn_map[vkn]
                return self._manuel_sonuc(cari_data, 'vkn_eslesmesi', vkn, net_tutar)

        # 3.ADIM: KELİME BAZLI SKORLAMA (Bulanık Eşleşme)
        # Banka açıklamasını temizle ve kelimelerine ayır
        banka_kelimeleri = self._temizle(aciklama)
        
        en_iyi_skor = 0
        en_iyi_cari = None
        
        for cari in self.cari_listesi:
            cari_kelimeleri = cari['unvan_clean']
            if not cari_kelimeleri: continue
            
            # Kesişim Kümesi (Ortak Kelimeler)
            ortak_kelimeler = cari_kelimeleri.intersection(banka_kelimeleri)
            match_count = len(ortak_kelimeler)
            
            if match_count == 0: continue
            
            # SKORLAMA MANTIĞI:
            # Cari unvanındaki önemli kelimelerin kaçı banka açıklamasında geçiyor?
            basari_orani = match_count / len(cari_kelimeleri)
            
            # EŞİK DEĞERLERİ (Tuning)
            # 1.Eğer cari tek kelimeyse (örn: "KOÇTAŞ") ve bu kelime varsa -> %100 kabul et
            # 2.Eğer cari çok kelimeyse (örn: "AHMET YILMAZ") en az %60'ı tutmalı
            
            if basari_orani > en_iyi_skor:
                en_iyi_skor = basari_orani
                en_iyi_cari = cari

        # Eşik Değer Kontrolü (Yanlış eşleşmeyi önlemek için)
        # %60 ve üzeri benzerlik varsa kabul et (Veya tek kelimelik tam eşleşme)
        if en_iyi_skor >= 0.60 or (en_iyi_skor > 0 and len(en_iyi_cari['unvan_clean']) == 1 and en_iyi_skor == 1.0):
             return self._manuel_sonuc(
                 {'id': en_iyi_cari['id'], 'unvan': en_iyi_cari['unvan']}, 
                 'isim_eslesmesi', 
                 en_iyi_cari['unvan'], # Kural olarak carinin tam adını öner
                 net_tutar
             )

        return {'bulundu': False}

    def _manuel_sonuc(self, cari_data, kaynak, kural_anahtar, net_tutar):
        return {
            'bulundu': True,
            'kaynak': kaynak,
            'hedef_turu': 'cari',
            'target_id': cari_data['id'],
            'display': cari_data['unvan'],
            'kural_anahtar': kural_anahtar,
            'is_pos': False, 'brut_tutar': net_tutar, 'komisyon': 0, 'oran': 0, 'komisyon_hesap_id': None
        }

    def _kural_sonuc_olustur(self, kural, net_tutar):
        """Kural nesnesinden sonuç sözlüğü üretir"""
        sonuc = {
            'bulundu': True,
            'kaynak': 'kural',
            'hedef_turu': kural.hedef_turu,
            'target_id': None,
            'display': '',
            'kural_anahtar': kural.anahtar_kelime,
            'is_pos': False, 'brut_tutar': net_tutar, 'komisyon': 0, 'oran': 0, 'komisyon_hesap_id': None
        }
        if kural.hedef_turu == 'cari' and kural.hedef_cari:
            sonuc['target_id'] = kural.hedef_cari_id
            sonuc['display'] = kural.hedef_cari.unvan
        elif kural.hedef_turu == 'muhasebe' and kural.hedef_muhasebe:
            sonuc['target_id'] = kural.hedef_muhasebe_id
            sonuc['display'] = kural.hedef_muhasebe.ad

        if kural.kural_tipi == 'pos_net' and kural.varsayilan_komisyon_orani > 0:
            try:
                oran = float(kural.varsayilan_komisyon_orani) / 100
                brut = float(net_tutar) / (1 - oran)
                komisyon = brut - float(net_tutar)
                sonuc['is_pos'] = True
                sonuc['brut_tutar'] = round(brut, 2)
                sonuc['komisyon'] = round(komisyon, 2)
                sonuc['oran'] = kural.varsayilan_komisyon_orani
                sonuc['komisyon_hesap_id'] = kural.komisyon_gider_hesap_id
            except: pass
            
        return sonuc