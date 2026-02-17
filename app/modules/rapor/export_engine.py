# app/modules/raporlar/export_engine.py

from io import BytesIO
from flask import send_file, make_response
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

class ExportEngine:
    """Raporları farklı formatlara export et"""
    
    @staticmethod
    def to_excel(df, filename="rapor.xlsx"):
        """Excel export (çoklu sheet destekli)"""
        
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Ana veri
            df.to_excel(writer, sheet_name='Rapor', index=False)
            
            # Özet sayfa (otomatik)
            summary = pd.DataFrame({
                'Metrik': ['Toplam Kayıt', 'İlk Tarih', 'Son Tarih'],
                'Değer': [
                    len(df),
                    df['tarih'].min() if 'tarih' in df.columns else 'N/A',
                    df['tarih'].max() if 'tarih' in df.columns else 'N/A'
                ]
            })
            summary.to_excel(writer, sheet_name='Özet', index=False)
            
            # Formatting
            workbook = writer.book
            worksheet = writer.sheets['Rapor']
            
            # Başlık stili
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4F81BD',
                'font_color': 'white',
                'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)  # Genişlik
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    @staticmethod
    def to_pdf(df, title="Rapor", filename="rapor.pdf"):
        """PDF export (Türkçe karakter destekli)"""
        
        output = BytesIO()
        
        # PDF oluştur
        doc = SimpleDocTemplate(output, pagesize=landscape(A4))
        elements = []
        
        # Başlık
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph("<br/><br/>", styles['Normal']))
        
        # Tablo verisi hazırla
        data = [df.columns.tolist()] + df.values.tolist()
        
        # Tablo oluştur
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F81BD')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    
    @staticmethod
    def to_csv(df, filename="rapor.csv"):
        """CSV export (Excel uyumlu, Türkçe karakter)"""
        
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig', sep=';')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )