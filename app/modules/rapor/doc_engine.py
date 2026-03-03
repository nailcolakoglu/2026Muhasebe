# app/modules/rapor/doc_engine.py

from flask import render_template_string
from app.extensions import db, get_tenant_db
from app.modules.rapor.models import YazdirmaSablonu
from app.modules.firmalar.models import Firma
from app.modules.cari.models import CariHesap
from app.modules.siparis.models import Siparis
from jinja2.sandbox import SandboxedEnvironment

class DocumentGenerator:
    def __init__(self, firma_id):
        self.firma_id = firma_id

    def get_sablon(self, belge_turu):
        """
        Aktif Tenant veritabanından ilgili belge türüne ait şablonu çeker.
        """
        tenant_db = get_tenant_db()
        
        # 1. Aktif ve Varsayılan olan şablonu bul
        sablon = tenant_db.query(YazdirmaSablonu).filter_by(
            belge_turu=belge_turu, 
            aktif=True, 
            varsayilan=True
        ).first()
        
        # 2. Eğer "Varsayılan" işaretli yoksa, bulduğu ilk aktif şablonu getir
        if not sablon:
            sablon = tenant_db.query(YazdirmaSablonu).filter_by(
                belge_turu=belge_turu, 
                aktif=True
            ).first()
            
        if not sablon:
            raise Exception(f"'{belge_turu}' türü için veritabanınızda uygun bir yazdırma şablonu bulunamadı! Lütfen Rapor/Şablon ayarlarından bir şablon ekleyin.")
            
        return sablon

    def render_html(self, belge_turu, veri_objesi, ekstra_context=None):
        """
        Veriyi şablona gömer ve HTML üretir.
        """
        tenant_db = get_tenant_db()
        sablon = self.get_sablon(belge_turu)
        
        firma = tenant_db.query(Firma).get(self.firma_id)
        
        context = {
            'belge': veri_objesi,      
            'firma': firma,            
            'sablon_css': sablon.css_icerik
        }
        
        if ekstra_context:
            context.update(ekstra_context)
            
        env = SandboxedEnvironment()
        
        # ✨ DÜZELTME 2: Sandbox (Güvenli Alan) motoruna da 'yaziyla' filtresini ekliyoruz
        try:
            from app.araclar import sayiyi_yaziya_cevir
            env.filters['yaziyla'] = sayiyi_yaziya_cevir
        except ImportError:
            pass
        
        template = env.from_string(sablon.html_icerik)
        
        rendered_html = template.render(**context)
        return rendered_html