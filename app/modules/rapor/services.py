from app.extensions import db
from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay, HesapPlani
from app.modules.firmalar.models import Firma
from sqlalchemy import func, case, cast, Integer, literal
from datetime import datetime

class YevmiyeRaporuMotoru:
    def __init__(self, baslangic_tarihi, bitis_tarihi, satir_limiti=40):
        self.baslangic = baslangic_tarihi
        self.bitis = bitis_tarihi
        self.satir_limiti = satir_limiti
        self.sayfalar = []
        # Genel Toplamlar (Float olarak başlatıyoruz)
        self.genel_toplam_borc = 0.0
        self.genel_toplam_alacak = 0.0
        self.hesap_adi_cache = {}

    def verileri_hazirla(self, firma_id):
        """
        Fişleri Muhasebe Sıralamasına Göre Çeker:
        1.Tarih (Eskiden Yeniye)
        2.Fiş Türü (Açılış > Tahsil > Tediye > Mahsup > Kapanış)
        3.Fiş No (Artan)
        """
        
        # --- SIRALAMA MANTIĞI (FIREBIRD UYUMLU) ---
        tur_onceligi = case(
            (MuhasebeFisi.fis_turu == 'acilis',  cast(literal(1), Integer)),
            (MuhasebeFisi.fis_turu == 'tahsil',  cast(literal(2), Integer)),
            (MuhasebeFisi.fis_turu == 'tediye',  cast(literal(3), Integer)),
            (MuhasebeFisi.fis_turu == 'mahsup',  cast(literal(4), Integer)),
            (MuhasebeFisi.fis_turu == 'kapanis', cast(literal(5), Integer)),
            else_=cast(literal(6), Integer)
        )

        fisler = MuhasebeFisi.query.filter(
            MuhasebeFisi.firma_id == firma_id,
            MuhasebeFisi.tarih >= self.baslangic,
            MuhasebeFisi.tarih <= self.bitis
        ).order_by(
            MuhasebeFisi.tarih.asc(),
            tur_onceligi.asc(),
            MuhasebeFisi.fis_no.asc()
        ).all()

        if not fisler:
            return []

        current_page_data = []
        current_lines = 0
        sayfa_no = 1
        yevmiye_madde_no = 1

        for fis in fisler:
            # Fişi işle ve satırları al
            islenmis_satirlar, fis_borc, fis_alacak = self._fisi_isle(fis, firma_id)
            
            # Bu fişin kapladığı satır sayısı
            gerekli_satir = len(islenmis_satirlar) + 3 
            
            if current_lines + gerekli_satir > self.satir_limiti:
                if current_lines > 0:
                    self._sayfa_kapat(current_page_data, sayfa_no, son_sayfa=False)
                    sayfa_no += 1
                    current_page_data = []
                    current_lines = 0

            current_page_data.append({
                'type': 'fis',
                'madde_no': yevmiye_madde_no,
                'tarih': fis.tarih,
                'fis_no': fis.fis_no,
                'aciklama': fis.aciklama,
                'satirlar': islenmis_satirlar,
                'fis_toplam_borc': fis_borc,
                'fis_toplam_alacak': fis_alacak
            })
            
            # HATA ÇÖZÜMÜ BURADA:
            # fis_borc ve fis_alacak artık kesinlikle float geliyor, güvenle toplayabiliriz.
            self.genel_toplam_borc += fis_borc
            self.genel_toplam_alacak += fis_alacak
            
            yevmiye_madde_no += 1
            current_lines += gerekli_satir

        if current_page_data:
            self._sayfa_kapat(current_page_data, sayfa_no, son_sayfa=True)

        return self.sayfalar

    def _fisi_isleSİL(self, fis, firma_id):
        """
        Fişi hiyerarşik yapıya dönüştürür.
        GÜNCELLEME: Tek satırlık hareketlerde detay gizleme özelliği eklendi.
        """
        
        # Detayları Kod Sırasına Göre Diz
        detaylar = sorted(fis.detaylar, key=lambda x: x.hesap.kod)
        
        borclular = [d for d in detaylar if d.borc > 0]
        alacaklilar = [d for d in detaylar if d.alacak > 0]
        
        final_liste = []
        
        # Fiş Dip Toplamları (Decimal -> Float dönüşümü ile)
        t_borc = sum(float(d.borc or 0) for d in detaylar)
        t_alacak = sum(float(d.alacak or 0) for d in detaylar)

    def _fisi_isle(self, fis, firma_id):
        """
        Fişi hiyerarşik yapıya dönüştürür.
        GÜNCELLEME: Grup Başlıkları (Ara Satırlar) tamamen kaldırıldı.
        Sadece Kebir (Ana Başlık) ve Muavin (Detay Satırları) kaldı.
        """
        
        # Detayları Kod Sırasına Göre Diz
        detaylar = sorted(fis.detaylar, key=lambda x: x.hesap.kod)
        
        borclular = [d for d in detaylar if d.borc > 0]
        alacaklilar = [d for d in detaylar if d.alacak > 0]
        
        final_liste = []
        
        # Fiş Dip Toplamları
        t_borc = sum(float(d.borc or 0) for d in detaylar)
        t_alacak = sum(float(d.alacak or 0) for d in detaylar)

        def hiyerarsi_yap(liste, is_alacak):
            if not liste: return

            kebir_map = {}

            # 1.VERİYİ GRUPLA
            for satir in liste:
                tutar = float(satir.alacak if is_alacak else satir.borc)
                parcalar = satir.hesap.kod.split('.')
                kebir_kod = parcalar[0] 
                
                if kebir_kod not in kebir_map:
                    kebir_map[kebir_kod] = {'toplam': 0.0, 'tum_satirlar': []}
                
                # Kebir toplamını artır
                kebir_map[kebir_kod]['toplam'] += tutar
                # Satırı listeye ekle
                kebir_map[kebir_kod]['tum_satirlar'].append(satir)

            # 2.LİSTEYİ OLUŞTUR
            sorted_kebir = sorted(kebir_map.keys())
            
            for k_kod in sorted_kebir:
                k_data = kebir_map[k_kod]
                # Bu kebire ait tüm hareketler (zaten sıralı gelmişti)
                satirlar = k_data['tum_satirlar']
                hareket_sayisi = len(satirlar)
                
                # --- SENARYO A: TEK SATIR VARSA (SADELEŞTİRME) ---
                if hareket_sayisi == 1:
                    tek_satir = satirlar[0]
                    final_liste.append({
                        'row_type': 'kebir', 
                        'kod': k_kod, 
                        'ad': self._hesap_adi_getir(k_kod, firma_id),
                        'aciklama': tek_satir.aciklama, 
                        'tutar_detay': None,
                        'tutar_ana': k_data['toplam'],  # Tutar Ana sütuna
                        'is_alacak': is_alacak
                    })
                
                # --- SENARYO B: ÇOKLU SATIR VARSA (BAŞLIK + DETAYLAR) ---
                else:
                    # 1.KEBİR BAŞLIĞI (Sadece Toplam Tutar)
                    final_liste.append({
                        'row_type': 'kebir',
                        'kod': k_kod,
                        'ad': self._hesap_adi_getir(k_kod, firma_id),
                        'aciklama': '', 
                        'tutar_detay': None,
                        'tutar_ana': k_data['toplam'], # Toplam Tutar Ana Sütuna
                        'is_alacak': is_alacak
                    })
                    
                    # 2.DETAY SATIRLARI (GRUP BAŞLIĞI OLMADAN DİREKT DÖKÜLÜR)
                    # Kırmızı çizgili satırlar artık oluşmayacak.
                    for m in satirlar:
                        m_tutar = float(m.alacak if is_alacak else m.borc)
                        
                        final_liste.append({
                            'row_type': 'muavin',
                            'kod': m.hesap.kod,      # Örn: 320.01
                            'ad': m.hesap.ad,        # Örn: YURT İÇİ SATICILAR
                            'aciklama': m.aciklama,  # Örn: İşlem Detay 10
                            'tutar_detay': m_tutar,  # Tutar DETAY sütununa
                            'tutar_ana': None,       
                            'is_alacak': is_alacak,
                            'has_parent': True
                        })

        hiyerarsi_yap(borclular, False)
        hiyerarsi_yap(alacaklilar, True)
        
        return final_liste, t_borc, t_alacak

    def _sayfa_kapat(self, data, sayfa_no, son_sayfa=False):
        nakli_yekun = {'borc': self.genel_toplam_borc, 'alacak': self.genel_toplam_alacak}
        devreden = {'borc': 0.0, 'alacak': 0.0}
        if self.sayfalar: devreden = self.sayfalar[-1]['footer']

        self.sayfalar.append({
            'no': sayfa_no,
            'header': devreden,
            'data': data,
            'footer': nakli_yekun,
            'is_last': son_sayfa
        })

    def _hesap_adi_getir(self, kod, firma_id):
        if kod in self.hesap_adi_cache: return self.hesap_adi_cache[kod]
        hesap = HesapPlani.query.filter_by(kod=kod, firma_id=firma_id).first()
        ad = hesap.ad if hesap else "TANIMSIZ HESAP"
        self.hesap_adi_cache[kod] = ad
        return ad

# ---------------------------------------------------------
# 5.MUHASEBE FİŞ İŞLEMLERİ (KAYIT & KESİNLEŞTİRME)
# ---------------------------------------------------------

def tarih_kilidi_kontrol(tarih, donem_id):
    """
    Belirtilen tarihe kayıt atılıp atılamayacağını kontrol eder.
    Eğer Resmi Defter basıldıysa o tarihe işlem yapılamaz.
    """
    donem = Donem.query.get(donem_id)
    if not donem:
        raise Exception("İlgili dönem bulunamadı!")

    # Gelen tarih string ise date objesine çevir
    if isinstance(tarih, str):
        try:
            islem_tarihi = datetime.strptime(tarih, '%Y-%m-%d').date()
        except ValueError:
            raise Exception("Geçersiz tarih formatı!")
    else:
        islem_tarihi = tarih

    # Kilit Kontrolü
    if donem.son_yevmiye_tarihi:
        if islem_tarihi <= donem.son_yevmiye_tarihi:
            kilit_tarihi_str = donem.son_yevmiye_tarihi.strftime('%d.%m.%Y')
            raise Exception(
                f"⛔ GÜVENLİK UYARISI: {kilit_tarihi_str} tarihine kadar Resmi Defter basılmıştır! "
                f"Bu tarihe veya öncesine ({islem_tarihi.strftime('%d.%m.%Y')}) fiş giremez veya düzenleyemezsiniz."
            )
    return True

def fis_kaydet(data, kullanici_id, sube_id, donem_id, firma_id, fis_id=None):
    """
    Yeni fiş oluşturur veya mevcut fişi günceller.
    Data yapısı: {
        'tarih': '2025-01-20',
        'fis_turu': 'mahsup',
        'aciklama': '...',
        'detaylar': [
            {'hesap_id': 1, 'aciklama': '...', 'borc': 100, 'alacak': 0, 'belge_turu': 'invoice', ...},
            ...
        ]
    }
    """
    try:
        # 1.TARİH KİLİDİ KONTROLÜ (En Başta)
        tarih_kilidi_kontrol(data['tarih'], donem_id)

        # 2.Fişi Bul veya Oluştur
        if fis_id:
            fis = MuhasebeFisi.query.get(fis_id)
            if not fis: return False, "Düzenlenecek fiş bulunamadı."
            
            # Eğer fiş zaten resmi deftere basıldıysa DÜZENLENEMEZ!
            if fis.resmi_defter_basildi:
                return False, "⛔ Bu fiş Resmi Deftere basıldığı için değiştirilemez!"
                
            # Eski detayları temizle (Basit güncelleme mantığı: Sil -> Yeniden Ekle)
            MuhasebeFisiDetay.query.filter_by(fis_id=fis.id).delete()
        else:
            # Yeni Fiş
            # Fiş numarasını sayaçtan al
            yeni_no = numara_uret(firma_id, data['fis_turu'].upper(), on_ek=f"{data['fis_turu'][0].upper()}-")
            
            fis = MuhasebeFisi(
                firma_id=firma_id,
                donem_id=donem_id,
                sube_id=sube_id,
                fis_no=yeni_no,
                kaydeden_id=kullanici_id
            )
            db.session.add(fis)

        # 3.Başlık Bilgilerini Güncelle
        fis.tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date() if isinstance(data['tarih'], str) else data['tarih']
        fis.fis_turu = data['fis_turu']
        fis.aciklama = data.get('aciklama', '')
        fis.duzenleyen_id = kullanici_id
        fis.son_duzenleme_tarihi = datetime.now()

        # 4.Detayları Ekle
        toplam_borc = 0
        toplam_alacak = 0
        
        for satir in data.get('detaylar', []):
            detay = MuhasebeFisiDetay(
                fis=fis,
                hesap_id=satir['hesap_id'],
                aciklama=satir.get('aciklama', fis.aciklama),
                borc=satir.get('borc', 0),
                alacak=satir.get('alacak', 0),
                
                # --- E-DEFTER ALANLARI ---
                belge_turu=satir.get('belge_turu'),      # invoice, check vb.
                belge_no=satir.get('belge_no'),
                belge_tarihi=satir.get('belge_tarihi'), # Date objesi olmalı
                odeme_yontemi=satir.get('odeme_yontemi'), # KASA, BANKA...
                belge_aciklamasi=satir.get('belge_aciklamasi')
            )
            db.session.add(detay)
            toplam_borc += float(satir.get('borc', 0))
            toplam_alacak += float(satir.get('alacak', 0))

        # 5.Bakiye Kontrolü
        if abs(toplam_borc - toplam_alacak) > 0.01:
            db.session.rollback()
            return False, f"Fiş dengesiz! Borç: {toplam_borc}, Alacak: {toplam_alacak}, Fark: {toplam_borc - toplam_alacak}"

        fis.toplam_borc = toplam_borc
        fis.toplam_alacak = toplam_alacak
        
        db.session.commit()
        return True, f"Fiş başarıyla {'güncellendi' if fis_id else 'kaydedildi'}.No: {fis.fis_no}"

    except Exception as e:
        db.session.rollback()
        return False, f"Hata: {str(e)}"

def resmi_defteri_kesinlestir(firma_id, donem_id, bitis_tarihi):
    """
    Belirtilen tarihe kadar olan fişlere Resmi Yevmiye Numarası verir ve kilitler.
    Bu işlem geri alınamaz! (Admin/Mali Müşavir yetkisi gerektirir)
    """
    try:
        donem = Donem.query.get(donem_id)
        if not donem: return False, "Dönem bulunamadı."

        # Tarih string ise çevir
        if isinstance(bitis_tarihi, str):
            bitis_tarihi = datetime.strptime(bitis_tarihi, '%Y-%m-%d').date()

        # 1.Daha önce kesinleştirilmiş tarihten öncesine işlem yapılamaz
        if donem.son_yevmiye_tarihi and bitis_tarihi <= donem.son_yevmiye_tarihi:
            return False, f"Hata: {donem.son_yevmiye_tarihi} tarihine kadar zaten kesinleştirilmiş."

        # 2.Kesinleştirilecek Fişleri Çek (Sıralama Çok Önemli!)
        # Kriter: Tarih ARTAN, Fiş Türü (Açılış>Tahsil>Tediye>Mahsup>Kapanış), Fiş No ARTAN
        
        # Sıralama mantığı için case yapısını import ettiğinizden emin olun (sqlalchemy.case)
        from sqlalchemy import case, cast, Integer, literal
        from app.modules.muhasebe.models import MuhasebeFisi # Import kontrolü
        
        tur_onceligi = case(
            (MuhasebeFisi.fis_turu == 'acilis',  cast(literal(1), Integer)),
            (MuhasebeFisi.fis_turu == 'tahsil',  cast(literal(2), Integer)),
            (MuhasebeFisi.fis_turu == 'tediye',  cast(literal(3), Integer)),
            (MuhasebeFisi.fis_turu == 'mahsup',  cast(literal(4), Integer)),
            (MuhasebeFisi.fis_turu == 'kapanis', cast(literal(5), Integer)),
            else_=cast(literal(6), Integer)
        )

        fisler = MuhasebeFisi.query.filter(
            MuhasebeFisi.firma_id == firma_id,
            MuhasebeFisi.donem_id == donem_id,
            MuhasebeFisi.tarih <= bitis_tarihi,
            MuhasebeFisi.resmi_defter_basildi == False # Henüz basılmamış olanlar
        ).order_by(
            MuhasebeFisi.tarih.asc(),
            tur_onceligi.asc(),
            MuhasebeFisi.fis_no.asc()
        ).all()

        if not fisler:
            return False, "Belirtilen tarihe kadar kesinleştirilecek yeni fiş bulunamadı."

        # 3.Numaralandırma Başlasın
        sayac = donem.son_madde_no or 0
        basarili_adet = 0

        for fis in fisler:
            sayac += 1
            fis.yevmiye_madde_no = sayac
            fis.resmi_defter_basildi = True # KİLİTLE
            basarili_adet += 1
        
        # 4.Dönemi Güncelle
        donem.son_yevmiye_tarihi = bitis_tarihi
        donem.son_madde_no = sayac
        
        db.session.commit()
        
        return True, f"{basarili_adet} adet fiş kesinleştirildi.Son Yevmiye Madde No: {sayac}"

    except Exception as e:
        db.session.rollback()
        return False, f"Kesinleştirme Hatası: {str(e)}"

