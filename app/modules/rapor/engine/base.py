import pandas as pd
from io import BytesIO
from abc import ABC, abstractmethod
from datetime import datetime


# --- DEĞİŞİKLİK BAŞLANGICI ---
# WeasyPrint Yüklenemezse Hata Vermesin, Sadece Uyarı Versin
WEASYPRINT_AKTIF = False
# PDF kütüphanesi (Hata verirse program çökmesin diye try-except bloğu)
try:
    #from weasyprint import HTML, CSS
    WEASYPRINT_AKTIF = True
except ImportError:
    WEASYPRINT_AKTIF = False
    print("UYARI: WeasyPrint kütüphanesi yüklü değil.PDF çıktısı alınamaz.")


class BaseReport(ABC):
    """
    Tüm raporların miras alacağı Ana Motor Sınıfı.
    """
    def __init__(self, baslik, filtreler=None):
        self.baslik = baslik
        self.filtreler = filtreler or {}
        self.data = []  
        self.columns = [] 
        self.summary = {} 

    @abstractmethod
    def verileri_getir(self):
        pass

    def to_dataframe(self):
        """Veriyi Pandas DataFrame formatına çevirir"""
        if not self.data:
            return pd.DataFrame(columns=[c['title'] for c in self.columns])
        
        df = pd.DataFrame(self.data)
        col_map = {c['field']: c['title'] for c in self.columns}
        
        # Kolon eşleştirmesi
        mevcut_kolonlar = [c for c in self.data[0].keys() if c in col_map]
        df = df[mevcut_kolonlar]
        
        df.rename(columns=col_map, inplace=True)
        return df

    def export_excel(self):
        """Excel Çıktısı Üretir"""
        output = BytesIO()
        df = self.to_dataframe()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Rapor', index=False)
            
            # Sütun Genişlikleri
            worksheet = writer.sheets['Rapor']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)
                
        output.seek(0)
        return output

    # 👇 YENİ EKLENEN PDF METODU
    def export_pdf(self):
        """Profesyonel PDF Çıktısı Üretir"""
        if not WEASYPRINT_AKTIF:
            raise Exception("PDF Modülü (WeasyPrint) sunucuda yüklü değil!")

        df = self.to_dataframe()
        
        # Basit ve Şık bir HTML Şablonu (Inline CSS ile)
        html_str = f"""
        <html>
        <head>
            <style>
                @page {{ size: A4 landscape; margin: 1cm; }}
                body {{ font-family: sans-serif; font-size: 10pt; color: #333; }}
                h2 {{ text-align: center; margin-bottom: 5px; color: #2c3e50; }}
                .meta {{ text-align: center; font-size: 9pt; color: #777; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 8px; font-weight: bold; text-align: left; }}
                td {{ border: 1px solid #dee2e6; padding: 6px; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .footer {{ position: fixed; bottom: 0; width: 100%; text-align: right; font-size: 8pt; color: #aaa; }}
            </style>
        </head>
        <body>
            <h2>{self.baslik}</h2>
            <div class="meta">
                Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}
            </div>
            
            {df.to_html(index=False, border=0)}
            
            <div class="footer">
                MuhasebeERP Sistemi Tarafından Üretilmiştir.
            </div>
        </body>
        </html>
        """
        
        # HTML'i PDF Byte verisine çevir
        pdf_bytes = HTML(string=html_str).write_pdf()
        
        # BytesIO objesine sarıp döndür
        return BytesIO(pdf_bytes)

    # 👇 İSİM STANDARDI BURADA SAĞLANDI
    def export_html_table(self):
        """Admin paneli önizlemesi için HTML tablosu üretir"""
        df = self.to_dataframe()
        if df.empty:
            return '<div class="alert alert-warning">Görüntülenecek veri bulunamadı.</div>'
            
        return df.to_html(
            classes="table table-striped table-hover table-bordered table-sm",
            index=False,
            border=0,
            justify="left"
        )