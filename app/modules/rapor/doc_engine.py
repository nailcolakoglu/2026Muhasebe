# app/modules/rapor/doc_engine.py

from flask import render_template_string
from app.extensions import db
from app.modules.rapor.models import YazdirmaSablonu
from app.modules.firmalar.models import Firma
from app.modules.cari.models import CariHesap
from app.modules.siparis.models import Siparis #, Fatura, FaturaKalemi
from jinja2.sandbox import SandboxedEnvironment

class DocumentGenerator:
    def __init__(self, firma_id):
        self.firma_id = firma_id

    def get_sablon(self, belge_turu):
        """
        Önce firmanın kendi özel şablonuna bakar, yoksa genel varsayılan şablonu çeker.
        """
        # 1.Firmanın Varsayılanı
        sablon = YazdirmaSablonu.query.filter_by(
            firma_id=self.firma_id, 
            belge_turu=belge_turu, 
            aktif=True, 
            varsayilan=True
        ).first()
        
        # 2.Sistem Varsayılanı (Firma ID = None)
        if not sablon:
            sablon = YazdirmaSablonu.query.filter_by(
                firma_id=None, 
                belge_turu=belge_turu, 
                varsayilan=True
            ).first()
            
        if not sablon:
            raise Exception(f"{belge_turu} için uygun bir yazdırma şablonu bulunamadı!")
            
        return sablon

    def render_html(self, belge_turu, veri_objesi, ekstra_context=None):
        """
        Veriyi şablona gömer ve HTML üretir.
        :param belge_turu: 'fatura', 'tahsilat' vb.
        :param veri_objesi: Fatura, KasaHareket vb.veritabanı objesi
        :param ekstra_context: Şablona gönderilecek ek değişkenler (tarih, kullanıcı vb.)
        """
        sablon = self.get_sablon(belge_turu)
        firma = Firma.query.get(self.firma_id)
        
        # Context Hazırlığı (Şablon içinde kullanılacak değişkenler)
        context = {
            'belge': veri_objesi,      # Örn: {{ belge.genel_toplam }}
            'firma': firma,            # Örn: {{ firma.unvan }}
            'sablon_css': sablon.css_icerik
        }
        
        if ekstra_context:
            context.update(ekstra_context)
            
        # Jinja2 ile Birleştirme (Magic Happens Here ✨)
        #rendered_html = render_template_string(sablon.html_icerik, **context)
        # Güvenli Render Ortamı
        env = SandboxedEnvironment()
        template = env.from_string(sablon.html_icerik)
        
        rendered_html = template.render(**context)
        return rendered_html