# modules/rapor/text_engine.py

from flask_babel import gettext as _  

class TextReportEngine:
    def __init__(self, sayfa_satir_sayisi=60, sayfa_genisligi=80):
        """
        DOS / Nokta Vuruşlu Yazıcı Motoru
        :param sayfa_satir_sayisi: Bir sayfaya sığan maksimum satır (Genelde 11 inç için 60-66)
        :param sayfa_genisligi: Karakter genişliği (80 veya 136 kolon)
        """
        self.MAX_SATIR = sayfa_satir_sayisi
        self.GENISLIK = sayfa_genisligi
        self.output = ""
        self.sayfa_no = 1
        self.satir_sayaci = 0
        
        # Format Ayarları
        self.basliklar = []
        self.kolon_genislikleri = [] # Örn: [30, 10, 15, 20]
        self.kolon_tipleri = []      # Örn: ['str', 'int', 'money', 'money']

    def header_ekle(self, firma_adi, belge_adi, belge_no, tarih):
        """Sayfa Başlığı Oluşturur"""
        self.output += f"{firma_adi:<{self.GENISLIK}}\n"
        self.output += "-" * self.GENISLIK + "\n"
        
        # Sağ ve Sol hizalı başlık
        sol = f"{_('Tarih')}: {tarih}"
        sag = f"{_('Belge')}: {belge_no} / {_('Sayfa')}: {self.sayfa_no}"
        bosluk = self.GENISLIK - len(sol) - len(sag)
        
        self.output += f"{sol}{' ' * bosluk}{sag}\n"
        self.output += f"{belge_adi:^{self.GENISLIK}}\n"
        self.output += "-" * self.GENISLIK + "\n"
        
        # Kolon Başlıkları
        header_str = ""
        for i, baslik in enumerate(self.basliklar):
            w = self.kolon_genislikleri[i]
            # Sayısal alanlar sağa, metinler sola dayalı
            align = ">" if self.kolon_tipleri[i] in ['money', 'int', 'float'] else "<"
            header_str += f"{baslik:{align}{w}} "
            
        self.output += header_str + "\n"
        self.output += "-" * self.GENISLIK + "\n"
        
        # Başlık yaklaşık 6 satır yer kapladı
        self.satir_sayaci = 6

    def sayfa_sonu_kontrol(self, firma_adi, belge_adi, belge_no, tarih, devreden_tutar=None):
        """Sayfa bittiyse Nakli Yekün atıp yeni sayfaya geçer"""
        
        # Alt bilgi için son 4 satırı rezerve et
        if self.satir_sayaci >= (self.MAX_SATIR - 4):
            
            # 1.Nakli Yekün Yaz (Eğer tutar varsa)
            if devreden_tutar is not None:
                txt = f"{_('NAKLI YEKUN')}: {devreden_tutar:,.2f}"
                self.output += "-" * self.GENISLIK + "\n"
                self.output += f"{txt:>{self.GENISLIK}}\n"
            
            # 2.Sayfa Atlat (Form Feed)
            self.output += "\f" 
            self.sayfa_no += 1
            self.satir_sayaci = 0
            
            # 3.Yeni Sayfa Başlığı
            self.header_ekle(firma_adi, belge_adi, belge_no, tarih)
            
            # 4.Devreden Yaz
            if devreden_tutar is not None:
                txt = f"{_('DEVREDEN')}: {devreden_tutar:,.2f}"
                self.output += f"{txt:>{self.GENISLIK}}\n"
                self.output += "-" * self.GENISLIK + "\n"
                self.satir_sayaci += 2

    def satir_ekle(self, veriler):
        """Veri satırını formatlayıp ekler"""
        row_str = ""
        for i, veri in enumerate(veriler):
            w = self.kolon_genislikleri[i]
            tip = self.kolon_tipleri[i]
            
            val_str = ""
            if tip == 'money':
                val_str = f"{float(veri or 0):,.2f}"
                row_str += f"{val_str:>{w}} "
            elif tip == 'int':
                row_str += f"{str(veri):>{w}} "
            else:
                # Metin çok uzunsa kes
                val_str = str(veri)[:w]
                row_str += f"{val_str:<{w}} "
                
        self.output += row_str + "\n"
        self.satir_sayaci += 1

    def dip_toplam_ekle(self, etiket, tutar):
        """En alta genel toplamı basar"""
        # Sayfanın en altına itmek isterseniz boş satır ekleyebilirsiniz
        kalan_satir = self.MAX_SATIR - self.satir_sayaci - 3
        if kalan_satir > 0:
            self.output += "\n" * kalan_satir
            
        self.output += "=" * self.GENISLIK + "\n"
        txt = f"{etiket}: {tutar:,.2f}"
        self.output += f"{txt:>{self.GENISLIK}}\n"