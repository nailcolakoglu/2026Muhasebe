# app/modules/rapor/services.py

import logging
from decimal import Decimal
from sqlalchemy import case, cast, Integer, literal
from sqlalchemy.orm import joinedload

from app.extensions import get_tenant_db
from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay, HesapPlani

logger = logging.getLogger(__name__)

class YevmiyeRaporuMotoru:
    """
    Yevmiye Defteri (Journal) dökümünü GİB standartlarına ve sayfa yapılarına 
    uygun şekilde hazırlayan Rapor Motoru (Tenant DB Uyumlu).
    """
    def __init__(self, baslangic_tarihi, bitis_tarihi, satir_limiti=40):
        self.baslangic = baslangic_tarihi
        self.bitis = bitis_tarihi
        self.satir_limiti = satir_limiti
        self.sayfalar = []
        # Genel Toplamlar (Finansal doğruluk için Decimal kullanıyoruz)
        self.genel_toplam_borc = Decimal('0.00')
        self.genel_toplam_alacak = Decimal('0.00')
        self.hesap_adi_cache = {}

    def verileri_hazirla(self, firma_id):
        """
        Fişleri Muhasebe Sıralamasına Göre Çeker:
        1. Tarih (Eskiden Yeniye)
        2. Fiş Türü (Açılış > Tahsil > Tediye > Mahsup > Kapanış)
        3. Fiş No (Artan)
        """
        tenant_db = get_tenant_db()
        
        # --- SIRALAMA MANTIĞI (Tenant DB Uyumlu) ---
        tur_onceligi = case(
            (MuhasebeFisi.fis_turu == 'ACILIS',  cast(literal(1), Integer)),
            (MuhasebeFisi.fis_turu == 'TAHSIL',  cast(literal(2), Integer)),
            (MuhasebeFisi.fis_turu == 'TEDIYE',  cast(literal(3), Integer)),
            (MuhasebeFisi.fis_turu == 'MAHSUP',  cast(literal(4), Integer)),
            (MuhasebeFisi.fis_turu == 'KAPANIS', cast(literal(5), Integer)),
            else_=cast(literal(6), Integer)
        )

        # ✨ PERFORMANS: N+1 Sorgu sorununu çözmek için detayları ve hesapları tek seferde (joinedload) çekiyoruz.
        fisler = tenant_db.query(MuhasebeFisi).options(
            joinedload(MuhasebeFisi.detaylar).joinedload(MuhasebeFisiDetay.hesap)
        ).filter(
            MuhasebeFisi.firma_id == str(firma_id),
            MuhasebeFisi.tarih >= self.baslangic,
            MuhasebeFisi.tarih <= self.bitis,
            MuhasebeFisi.deleted_at.is_(None)
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
            islenmis_satirlar, fis_borc, fis_alacak = self._fisi_isle(fis, str(firma_id), tenant_db)
            
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
                'madde_no': fis.yevmiye_madde_no or yevmiye_madde_no, # Resmi no varsa kullan, yoksa geçici sayaç
                'tarih': fis.tarih,
                'fis_no': fis.fis_no,
                'aciklama': fis.aciklama,
                'satirlar': islenmis_satirlar,
                'fis_toplam_borc': float(fis_borc),
                'fis_toplam_alacak': float(fis_alacak)
            })
            
            # Nakli Yekün Hesaplaması
            self.genel_toplam_borc += fis_borc
            self.genel_toplam_alacak += fis_alacak
            
            yevmiye_madde_no += 1
            current_lines += gerekli_satir

        if current_page_data:
            self._sayfa_kapat(current_page_data, sayfa_no, son_sayfa=True)

        return self.sayfalar

    def _fisi_isle(self, fis, firma_id, tenant_db):
        """
        Fişi hiyerarşik (Kebir/Ana Hesap ve Muavin/Alt Hesap) yapıya dönüştürür.
        """
        # Detayları Kod Sırasına Göre Diz
        detaylar = sorted(fis.detaylar, key=lambda x: x.hesap.kod if x.hesap else "")
        
        borclular = [d for d in detaylar if d.borc > 0]
        alacaklilar = [d for d in detaylar if d.alacak > 0]
        
        final_liste = []
        
        # Fiş Dip Toplamları (Hassasiyet için Decimal)
        t_borc = sum((d.borc or Decimal('0.00')) for d in detaylar)
        t_alacak = sum((d.alacak or Decimal('0.00')) for d in detaylar)

        def hiyerarsi_yap(liste, is_alacak):
            if not liste: return

            kebir_map = {}

            # 1. VERİYİ KEBİR (ANA) HESABA GÖRE GRUPLA (Örn: 120.01 -> 120'ye toplanır)
            for satir in liste:
                if not satir.hesap: continue
                
                tutar = satir.alacak if is_alacak else satir.borc
                parcalar = satir.hesap.kod.split('.')
                kebir_kod = parcalar[0] 
                
                if kebir_kod not in kebir_map:
                    kebir_map[kebir_kod] = {'toplam': Decimal('0.00'), 'tum_satirlar': []}
                
                kebir_map[kebir_kod]['toplam'] += tutar
                kebir_map[kebir_kod]['tum_satirlar'].append(satir)

            # 2. LİSTEYİ OLUŞTUR
            sorted_kebir = sorted(kebir_map.keys())
            
            for k_kod in sorted_kebir:
                k_data = kebir_map[k_kod]
                satirlar = k_data['tum_satirlar']
                hareket_sayisi = len(satirlar)
                
                # Sadece tek satır varsa direkt kebir olarak bas
                if hareket_sayisi == 1:
                    tek_satir = satirlar[0]
                    final_liste.append({
                        'row_type': 'kebir', 
                        'kod': k_kod, 
                        'ad': self._hesap_adi_getir(k_kod, firma_id, tenant_db),
                        'aciklama': tek_satir.aciklama, 
                        'tutar_detay': None,
                        'tutar_ana': float(k_data['toplam']),
                        'is_alacak': is_alacak
                    })
                
                # Çoklu kırılım (Muavin) varsa, üst başlık ve alt kırılımlar şeklinde bas
                else:
                    final_liste.append({
                        'row_type': 'kebir',
                        'kod': k_kod,
                        'ad': self._hesap_adi_getir(k_kod, firma_id, tenant_db),
                        'aciklama': '', 
                        'tutar_detay': None,
                        'tutar_ana': float(k_data['toplam']), 
                        'is_alacak': is_alacak
                    })
                    
                    for m in satirlar:
                        m_tutar = float(m.alacak if is_alacak else m.borc)
                        
                        final_liste.append({
                            'row_type': 'muavin',
                            'kod': m.hesap.kod,      
                            'ad': m.hesap.ad,        
                            'aciklama': m.aciklama,  
                            'tutar_detay': m_tutar,  
                            'tutar_ana': None,       
                            'is_alacak': is_alacak,
                            'has_parent': True
                        })

        hiyerarsi_yap(borclular, False) # Önce Borçlar yazılır
        hiyerarsi_yap(alacaklilar, True) # Sonra Alacaklar yazılır
        
        return final_liste, t_borc, t_alacak

    def _sayfa_kapat(self, data, sayfa_no, son_sayfa=False):
        nakli_yekun = {'borc': float(self.genel_toplam_borc), 'alacak': float(self.genel_toplam_alacak)}
        devreden = {'borc': 0.0, 'alacak': 0.0}
        
        if self.sayfalar: 
            devreden = self.sayfalar[-1]['footer']

        self.sayfalar.append({
            'no': sayfa_no,
            'header': devreden,
            'data': data,
            'footer': nakli_yekun,
            'is_last': son_sayfa
        })

    def _hesap_adi_getir(self, kod, firma_id, tenant_db):
        """Hesap adlarını her seferinde DB'ye sormamak için basit bir cache kullanır."""
        if kod in self.hesap_adi_cache: 
            return self.hesap_adi_cache[kod]
            
        hesap = tenant_db.query(HesapPlani).filter_by(kod=kod, firma_id=firma_id).first()
        ad = hesap.ad if hesap else "TANIMSIZ HESAP"
        self.hesap_adi_cache[kod] = ad
        return ad