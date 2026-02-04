from .base import BaseReport
from app.extensions import db
from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay, HesapPlani
from sqlalchemy import case, cast, Integer, literal, func, literal_column 

# ---------------------------------------------------------
# 1.YEVMİYE DEFTERİ (Yürüyen Toplamlı)
# ---------------------------------------------------------
class YevmiyeDefteriRaporu(BaseReport):
    def __init__(self, firma_id, donem_id, baslangic, bitis):
        super().__init__("Yevmiye Defteri")
        self.firma_id = firma_id
        self.donem_id = donem_id
        self.baslangic = baslangic
        self.bitis = bitis
        
        self.columns = [
            {'field': 'tarih', 'title': 'Tarih'},
            {'field': 'yevmiye_no', 'title': 'Yev.No'},
            {'field': 'fis_no', 'title': 'Fiş No'},
            {'field': 'hesap_kodu', 'title': 'Hesap Kodu'},
            {'field': 'hesap_adi', 'title': 'Hesap Adı'},
            {'field': 'aciklama', 'title': 'Açıklama'},
            {'field': 'borc', 'title': 'Borç'},
            {'field': 'alacak', 'title': 'Alacak'},
            # 👇 YENİ SÜTUNLAR (Nakli Yekün Mantığı)
            {'field': 'kumulatif_borc', 'title': 'Küm.Borç'},
            {'field': 'kumulatif_alacak', 'title': 'Küm.Alacak'}
        ]

    def verileri_getir(self):
        tur_onceligi = case(
            (MuhasebeFisi.fis_turu == 'acilis',  cast(literal(1), Integer)),
            (MuhasebeFisi.fis_turu == 'tahsil',  cast(literal(2), Integer)),
            (MuhasebeFisi.fis_turu == 'tediye',  cast(literal(3), Integer)),
            (MuhasebeFisi.fis_turu == 'mahsup',  cast(literal(4), Integer)),
            (MuhasebeFisi.fis_turu == 'kapanis', cast(literal(5), Integer)),
            else_=cast(literal(6), Integer)
        )

        sonuclar = db.session.query(
            MuhasebeFisi.tarih,
            MuhasebeFisi.yevmiye_madde_no,
            MuhasebeFisi.fis_no,
            HesapPlani.kod.label('hesap_kodu'),
            HesapPlani.ad.label('hesap_adi'),
            MuhasebeFisiDetay.aciklama,
            MuhasebeFisiDetay.borc,
            MuhasebeFisiDetay.alacak
        )\
        .select_from(MuhasebeFisi)\
        .join(MuhasebeFisiDetay, MuhasebeFisi.id == MuhasebeFisiDetay.fis_id)\
        .join(HesapPlani, MuhasebeFisiDetay.hesap_id == HesapPlani.id)\
        .filter(
            MuhasebeFisi.firma_id == self.firma_id,
            MuhasebeFisi.donem_id == self.donem_id,
            MuhasebeFisi.tarih.between(self.baslangic, self.bitis)
        ).order_by(
            MuhasebeFisi.tarih.asc(),
            tur_onceligi.asc(),
            MuhasebeFisi.fis_no.asc(),
            MuhasebeFisiDetay.id.asc()
        ).all()

        self.data = []
        
        # 👇 HESAPLAMA MANTIĞI BURADA
        toplam_borc = 0.0
        toplam_alacak = 0.0

        for row in sonuclar:
            b = float(row.borc or 0)
            a = float(row.alacak or 0)
            
            toplam_borc += b
            toplam_alacak += a

            self.data.append({
                'tarih': row.tarih.strftime('%d.%m.%Y'),
                'yevmiye_no': row.yevmiye_madde_no or '-',
                'fis_no': row.fis_no,
                'hesap_kodu': row.hesap_kodu,
                'hesap_adi': row.hesap_adi,
                'aciklama': row.aciklama,
                'borc': b,
                'alacak': a,
                'kumulatif_borc': toplam_borc,   # Yürüyen Borç
                'kumulatif_alacak': toplam_alacak # Yürüyen Alacak
            })
            
        return self.data

# ---------------------------------------------------------
# 2.BÜYÜK DEFTER (KEBİR)
# ---------------------------------------------------------
class BuyukDefterRaporu(BaseReport):
    def __init__(self, firma_id, donem_id, baslangic, bitis):
        super().__init__("Büyük Defter (Kebir)")
        self.firma_id = firma_id
        self.donem_id = donem_id
        self.baslangic = baslangic
        self.bitis = bitis
        
        self.columns = [
            {'field': 'kebir_kodu', 'title': 'Kebir Kodu'},
            {'field': 'kebir_adi', 'title': 'Hesap Adı'},
            {'field': 'toplam_borc', 'title': 'Toplam Borç'},
            {'field': 'toplam_alacak', 'title': 'Toplam Alacak'},
            {'field': 'bakiye', 'title': 'Hesap Bakiyesi'},
            # 👇 YENİ SÜTUN: Genel gidişatı gösterir
            {'field': 'yuruyen_bakiye', 'title': 'Küm.Bakiye'} 
        ]

    def verileri_getir(self):
        # Firebird uyumlu Literal kullanımı
        kebir_kodu = func.substring(HesapPlani.kod, literal_column("1"), literal_column("3"))
        
        sonuclar = db.session.query(
            kebir_kodu.label('kebir_kodu'),
            func.min(HesapPlani.ad).label('kebir_adi'), 
            func.sum(MuhasebeFisiDetay.borc).label('t_borc'),
            func.sum(MuhasebeFisiDetay.alacak).label('t_alacak')
        )\
        .select_from(HesapPlani)\
        .join(MuhasebeFisiDetay, HesapPlani.id == MuhasebeFisiDetay.hesap_id)\
        .join(MuhasebeFisi, MuhasebeFisiDetay.fis_id == MuhasebeFisi.id)\
        .filter(
            MuhasebeFisi.firma_id == self.firma_id,
            MuhasebeFisi.donem_id == self.donem_id,
            MuhasebeFisi.tarih.between(self.baslangic, self.bitis)
        ).group_by(kebir_kodu).order_by(kebir_kodu).all()

        self.data = []
        
        # 👇 HESAPLAMA MANTIĞI
        yuruyen_genel_bakiye = 0.0

        for row in sonuclar:
            borc = float(row.t_borc or 0)
            alacak = float(row.t_alacak or 0)
            hesap_bakiyesi = borc - alacak
            
            yuruyen_genel_bakiye += hesap_bakiyesi

            self.data.append({
                'kebir_kodu': row.kebir_kodu,
                'kebir_adi': row.kebir_adi,
                'toplam_borc': borc,
                'toplam_alacak': alacak,
                'bakiye': hesap_bakiyesi,
                'yuruyen_bakiye': yuruyen_genel_bakiye # Listenin sonuna kadar toplar
            })
        return self.data

# ---------------------------------------------------------
# 3.GELİR TABLOSU
# ---------------------------------------------------------
class GelirTablosuRaporu(BaseReport):
    def __init__(self, firma_id, donem_id, baslangic, bitis):
        super().__init__("Gelir Tablosu")
        self.firma_id = firma_id
        self.donem_id = donem_id
        self.baslangic = baslangic
        self.bitis = bitis
        
        self.columns = [
            {'field': 'grup', 'title': 'Grup'},
            {'field': 'hesap_kodu', 'title': 'Hesap Kodu'},
            {'field': 'hesap_adi', 'title': 'Hesap Adı'},
            {'field': 'tutar', 'title': 'Tutar'}
        ]

    def verileri_getir(self):
        sonuclar = db.session.query(
            HesapPlani.kod,
            HesapPlani.ad,
            func.sum(MuhasebeFisiDetay.alacak - MuhasebeFisiDetay.borc).label('net_tutar')
        )\
        .select_from(HesapPlani)\
        .join(MuhasebeFisiDetay, HesapPlani.id == MuhasebeFisiDetay.hesap_id)\
        .join(MuhasebeFisi, MuhasebeFisiDetay.fis_id == MuhasebeFisi.id)\
        .filter(
            MuhasebeFisi.firma_id == self.firma_id,
            MuhasebeFisi.donem_id == self.donem_id,
            MuhasebeFisi.tarih.between(self.baslangic, self.bitis),
            HesapPlani.kod.like('6%') # 6 ile başlayan hesaplar
        ).group_by(HesapPlani.kod, HesapPlani.ad).order_by(HesapPlani.kod).all()

        self.data = []
        for row in sonuclar:
            tutar = float(row.net_tutar or 0)
            
            grup_adi = "BRÜT SATIŞLAR"
            if row.kod.startswith('63'): grup_adi = "FAALİYET GİDERLERİ (-)"
            elif row.kod.startswith('60'): grup_adi = "BRÜT SATIŞLAR"
            
            self.data.append({
                'grup': grup_adi,
                'hesap_kodu': row.kod,
                'hesap_adi': row.ad,
                'tutar': tutar
            })
        return self.data