# app/modules/sube/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask import session
from app.extensions import get_tenant_db, get_tenant_info
from app.modules.bolge.models import Bolge
from app.modules.lokasyon.models import Sehir, Ilce
import logging

logger = logging.getLogger(__name__)


def get_aktif_firma_id():
    """Aktif firma ID'sini döndürür"""
    if 'firma_id' in session:
        return session['firma_id']
    
    tenant_info = get_tenant_info()
    if tenant_info and 'firma_id' in tenant_info:
        return tenant_info['firma_id']
    
    if 'tenant_id' in session:
        return session['tenant_id']
    
    return None
    
    
def create_sube_form(sube=None):
    """Şube formu oluşturur"""
    is_edit = sube is not None
    action_url = f"/sube/duzenle/{sube.id}" if is_edit else "/sube/ekle"
    title = _("Şube Düzenle") if is_edit else _("Yeni Şube Ekle")
    
    form = Form(name="sube_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # Veritabanı Bağlantısı
    tenant_db = get_tenant_db()
    
    
    # Tenant DB bağlantısı
    tenant_db = get_tenant_db()
    
    # Firma ID
    firma_id = get_aktif_firma_id()
    
    # ===========================================
    # 1. BÖLGE LİSTESİ
    # ===========================================
    bolge_opts = [('', _('Seçiniz...'))]
    
    if tenant_db and firma_id:
        try:
            # ✅ Tüm bölgeleri göster (aktif=True filtresi YOK)
            bolgeler = tenant_db.query(Bolge).filter_by(
                firma_id=firma_id
                # aktif=True  ← BUNU KALDIRDIK!
            ).order_by(Bolge.ad).all()
            
            if bolgeler:
                # ✅ Sadece aktif olanları göstermek istersen:
                # bolge_opts += [(str(b.id), b.ad) for b in bolgeler if b.aktif]
                
                # ✅ Tümünü göstermek istersen:
                bolge_opts += [(str(b.id), f"{b.ad} {'✓' if b.aktif else '(Pasif)'}") for b in bolgeler]
                
                logger.info(f"✅ {len(bolgeler)} bölge yüklendi (Firma: {firma_id})")
            else:
                logger.warning(f"⚠️ Firma {firma_id} için bölge bulunamadı")
        
        except Exception as e:
            logger.error(f"❌ Bölge listesi hatası: {e}", exc_info=True)
    else:
        logger.warning("⚠️ Tenant DB veya Firma ID bulunamadı")

    # 2. ŞEHİR LİSTESİ (FIREBIRD) 👈 DÜZELTİLDİ
    sehir_opts = []
    if tenant_db:
        try:
            # MySQL (Sehir.query) yerine Firebird (tenant_db.query)
            sehirler = tenant_db.query(Sehir).order_by(Sehir.ad).all()
            sehir_opts = [(s.id, s.ad) for s in sehirler]
        except:
            sehir_opts = []

    # 3. İLÇE LİSTESİ (FIREBIRD) 👈 DÜZELTİLDİ
    ilce_opts = []
    selected_sehir_id = sube.sehir_id if sube else (sehir_opts[0][0] if sehir_opts else None)
    
    if tenant_db and selected_sehir_id:
        try:
            ilceler = tenant_db.query(Ilce).filter_by(sehir_id=selected_sehir_id).order_by(Ilce.ad).all()
            ilce_opts = [(i.id, i.ad) for i in ilceler]
        except:
            ilce_opts = []

    # ALANLAR
    kod = FormField('kod', FieldType.TEXT, _('Şube Kodu'), required=True, value=sube.kod if sube else '')
    ad = FormField('ad', FieldType.TEXT, _('Şube Adı'), required=True, value=sube.ad if sube else '')
    
    bolge = FormField(
        'bolge_id', 
        FieldType.SELECT, 
        _('Bağlı Olduğu Bölge'), 
        options=bolge_opts, 
        required=False,
        value=str(sube.bolge_id) if sube and sube.bolge_id else '',
        help_text=_('Önce Bölge Tanımları menüsünden bölge eklemelisiniz') if len(bolge_opts) == 1 else None
    )
    
    sehir = FormField('sehir_id', FieldType.SELECT, _('Şehir'), options=sehir_opts, required=True, value=sube.sehir_id if sube else '')
    
    # İlçe API Kaynağı
    # Not: API tarafında da sorguların Firebird'e atıldığından emin olunmalıdır.
    ilce = FormField('ilce_id', FieldType.SELECT, _('İlçe'), 
                        options=ilce_opts,
                        value=sube.ilce_id if sube else '',
                        data_source={
                            'url': '/cari/api/get-ilceler', 
                            'method': 'GET',
                            'depends_on': 'sehir_id'
                        },
                        select2_config={'placeholder': 'İlçe Seçiniz', 'search': True})

    adres = FormField('adres', FieldType.TEXTAREA, _('Adres'), value=sube.adres if sube else '')
    telefon = FormField('telefon', FieldType.TEL, _('Telefon'), value=sube.telefon if sube else '')
    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif'), value=sube.aktif if sube else '')
    
    layout.add_row(kod, ad)
    layout.add_row(bolge, sehir)
    layout.add_row(ilce, telefon)
    layout.add_row(adres, aktif)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, bolge, sehir, ilce, adres, telefon)
    
    return form