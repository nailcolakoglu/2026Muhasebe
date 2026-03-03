# app/modules/irsaliye/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask import url_for, session
from flask_login import current_user
from datetime import datetime
from app.extensions import get_tenant_db # ✨ EKLENDİ: Tenant DB bağlantısı

# Modeller
from app.modules.cari.models import CariHesap
from app.modules.depo.models import Depo
from app.modules.stok.models import StokKart
from app.modules.sube.models import Sube
from app.enums import StokBirimleri

def create_irsaliye_form(irsaliye=None):
    tenant_db = get_tenant_db() # ✨ EKLENDİ: Multi-tenant izolasyonu sağlandı
    is_edit = irsaliye is not None
    
    # Action URL belirle
    if is_edit:
        action_url = url_for('irsaliye.duzenle', id=irsaliye.id)
        title = _(f"{irsaliye.belge_no} - İrsaliye Düzenle")
    else:
        action_url = url_for('irsaliye.ekle')
        title = _("Yeni Sevk İrsaliyesi")
        
    form = Form(name="irsaliye_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    
    layout = FormLayout()

    # ==========================================
    # 0.VERİ HAZIRLIĞI (DROPDOWN DOLDURMA)
    # ==========================================
    firma_id = current_user.firma_id

    
    # 1.Cariler (Alıcı Firmalar) - ✨ DÜZELTME: 100.000 kaydı çekmemek için AJAX Select2 yapısı
    # form yüklenirken sadece en son eklenen 20 cariyi (veya düzenleniyorsa mevcut carini) getiririz
    cariler = tenant_db.query(CariHesap).filter_by(firma_id=firma_id, aktif=True).limit(20).all()
    cari_opts = [(c.id, f"{c.unvan}") for c in cariler]
    if not is_edit: cari_opts.insert(0, ('', "Seçiniz..."))

    # 2.Depolar (Yetki Kontrollü) - ✨ DÜZELTİLDİ: tenant_db kullanıldı
    depo_query = tenant_db.query(Depo).filter_by(firma_id=firma_id, aktif=True)
    
    if current_user.rol not in ['admin', 'patron'] and hasattr(current_user, 'yetkili_subeler'):
        yetkili_sube_ids = [s.id for s in current_user.yetkili_subeler]
        if yetkili_sube_ids:
            depo_query = depo_query.filter(Depo.sube_id.in_(yetkili_sube_ids))
    
    depolar = depo_query.all()
    depo_opts = [(d.id, f"{d.ad}") for d in depolar]
    
    varsayilan_depo = irsaliye.depo_id if irsaliye else (depo_opts[0][0] if depo_opts else '')

    # 3.Stoklar (Ürünler) - ✨ DÜZELTİLDİ: tenant_db kullanıldı
    stoklar = tenant_db.query(StokKart).filter_by(firma_id=firma_id, aktif=True).limit(50).all()
    stok_opts = [(s.id, f"{s.kod} - {s.ad}") for s in stoklar]

    # Tarih ve Saat Varsayılanları
    bugun = datetime.now().date()
    simdi = datetime.now().strftime('%H:%M')
    
    val_tarih = irsaliye.tarih if irsaliye else bugun
    val_saat = irsaliye.saat.strftime('%H:%M') if irsaliye and irsaliye.saat else simdi

    # ==========================================
    # 1.SEKME: GENEL BİLGİLER
    # ==========================================
    theme = {'colorfocus': '#fff3cd', 'textfocus': '#856404', 'borderfocus': '#ffeeba'} 

    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Belge No'), required=True, 
                         value=irsaliye.belge_no if irsaliye else '', 
                         endpoint='/irsaliye/api/siradaki-no', icon='bi bi-upc-scan', **theme).in_row("col-md-3")

    tarih = FormField('tarih', FieldType.DATE, _('Sevk Tarihi'), required=True, value=val_tarih, **theme).in_row("col-md-3")
    saat = FormField('saat', FieldType.TIME, _('Sevk Saati'), required=True, value=val_saat, **theme).in_row("col-md-2")

    #cari_id = FormField('cari_id', FieldType.SELECT, _('Alıcı Firma (Cari)'), options=cari_opts, required=True, 
    #                    value=irsaliye.cari_id if irsaliye else '',
    #                    select2_config={'placeholder': 'Cari Seçiniz...', 'search': True},
    #                    html_attributes={'id': 'cari_select'}, **theme).in_row("col-md-4")

    cari_id = FormField('cari_id', FieldType.SELECT, _('Alıcı Firma (Cari)'), options=cari_opts, required=True, 
                        value=irsaliye.cari_id if irsaliye else '',
                        # ✨ DÜZELTME: Select2'ye AJAX URL'sini verdik
                        html_attributes={'id': 'cari_select', 'data-ajax-url': '/irsaliye/api/cari-ara', 'data-js': 'stok-select'}, 
                        **theme).in_row("col-md-4")

    depo_id = FormField('depo_id', FieldType.SELECT, _('Çıkış Deposu'), options=depo_opts, required=True, 
                        value=varsayilan_depo, **theme).in_row("col-md-4")
    
    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), value=irsaliye.aciklama if irsaliye else '', **theme).in_row("col-md-8")

    # ==========================================
    # 2.SEKME: LOJİSTİK & ŞOFÖR (E-İrsaliye)
    # ==========================================
    plaka_arac = FormField('plaka_arac', FieldType.PLATE, 'Araç Plakası', placeholder='34 ABC 123', 
                           value=irsaliye.plaka_arac if irsaliye else '').in_row("col-md-3")
                           
    sofor_tc = FormField('sofor_tc', FieldType.TCKN, 'Şoför TCKN', maxlength=11,
                         value=irsaliye.sofor_tc if irsaliye else '').in_row("col-md-3")
                         
    sofor_ad = FormField('sofor_ad', FieldType.TEXT, 'Şoför Adı', 
                         value=irsaliye.sofor_ad if irsaliye else '').in_row("col-md-3")
                         
    sofor_soyad = FormField('sofor_soyad', FieldType.TEXT, 'Şoför Soyadı', 
                            value=irsaliye.sofor_soyad if irsaliye else '').in_row("col-md-3")

    # ==========================================
    # 3.SEKME: ÜRÜNLER (Master-Detail)
    # ==========================================
    kalemler = FormField('kalemler', FieldType.MASTER_DETAIL, _('Sevk Edilecek Ürünler'), required=True, html_attributes={'id': 'kalemler_table'})
    
    stok_ajax_url = '/irsaliye/api/stok-ara'

    kalemler.columns = [
        FormField('id', FieldType.HIDDEN, 'ID', default_value=0, html_attributes={'style': 'width: 0px;'}),
        
        FormField('stok_id', FieldType.SELECT, 'Ürün / Hizmet', options=stok_opts, required=True, 
                  html_attributes={'style': 'width: 300px;', 'data-ajax-url': stok_ajax_url, 'data-js': 'stok-select'}),
        
        FormField('miktar', FieldType.NUMBER, 'Miktar', required=True, default_value=1, 
                  html_attributes={'class': 'text-end', 'style': 'width: 100px;'}),
        
        FormField('birim', FieldType.SELECT, 'Birim', options=StokBirimleri.choices(), default_value='Adet', 
                  html_attributes={'style': 'width: 100px;'}),

        FormField('aciklama', FieldType.TEXT, 'Satır Açıklaması', 
                  html_attributes={'placeholder': 'Örn: Kırmızı Renk', 'style': 'width: 250px;'})
    ]

    if is_edit and irsaliye.kalemler:
        row_data = []
        for k in irsaliye.kalemler:
            row_data.append({
                'id': k.id,
                'stok_id': k.stok_id,
                'miktar': float(k.miktar),
                'birim': k.birim,
                'aciklama': k.aciklama
            })
        kalemler.value = row_data

    # E-İrsaliye Butonları (Sadece düzenleme modunda görünür)
    if is_edit:
        eirsaliye_html = f'''
        <div class="alert alert-secondary border-0 shadow-sm mt-3">
            <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-truck me-2"></i>E-İrsaliye Entegrasyonu</h6>
            <div class="d-flex gap-2">
                <button type="button" onclick="eIrsaliyeGonder('{str(irsaliye.id)}')" class="btn btn-primary">
                    <i class="bi bi-send me-1"></i> GİB'e Gönder
                </button>
            </div>
        </div>
        '''
        tab_eirsaliye = [layout.create_html(eirsaliye_html)]
    else:
        tab_eirsaliye = []

    # ==========================================
    # LAYOUT YERLEŞİMİ
    # ==========================================
    tabs_content = [
        ("Genel Bilgiler", [
            layout.create_row(belge_no, tarih, saat, cari_id),
            layout.create_row(depo_id, aciklama)
        ]),
        ("Lojistik & Şoför", [
            layout.create_alert("Bilgi", "E-İrsaliye gönderimi için şoför ve plaka bilgileri zorunludur.", "info"),
            layout.create_row(plaka_arac, sofor_tc, sofor_ad, sofor_soyad)
        ]),
        ("Ürünler", [kalemler])
    ]
    
    if is_edit:
        tabs_content.append(("E-İrsaliye", tab_eirsaliye))
        
    tabs = layout.create_tabs("irs_tabs", tabs_content)
    form.set_layout_html(tabs)
    
    form.add_fields(belge_no, tarih, saat, cari_id, depo_id, aciklama, 
                   plaka_arac, sofor_tc, sofor_ad, sofor_soyad, kalemler)
    
    return form