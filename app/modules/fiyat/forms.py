# app/modules/fiyat/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.stok.models import StokKart
from app.extensions import get_tenant_db

def create_fiyat_listesi_form(liste=None):
    is_edit = liste is not None
    tenant_db = get_tenant_db() 
    
    action_url = f"/fiyat/duzenle/{liste.id}" if is_edit else "/fiyat/ekle"
    title = _("Fiyat Listesi Düzenle") if is_edit else _("Yeni Fiyat Listesi")
    
    form = Form(name="fiyat_listesi_form", title='', action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # ✨ Form Tema Ayarları (Şık görünüm için)
    theme = {'colorfocus': '#e3f2fd', 'textfocus': '#1565c0', 'borderfocus': '#2196f3'}

    # ==========================================
    # 1. STOK LİSTESİ (100.000 KAYIT OPTİMİZASYONU - AJAX)
    # ==========================================
    stok_opts = []
    if is_edit and liste.detaylar:
        stok_id_list = [str(d.stok_id) for d in liste.detaylar if d.stok_id]
        if stok_id_list:
            secili_stoklar = tenant_db.query(StokKart).filter(StokKart.id.in_(stok_id_list)).all()
            stok_opts = [(str(s.id), f"{s.kod} - {s.ad}") for s in secili_stoklar]

    # ==========================================
    # 2. BAŞLIK BİLGİLERİ (in_row ile hizalandı)
    # ==========================================
    kod = FormField('kod', FieldType.AUTO_NUMBER, _('Liste Kodu'), required=True, 
                    value=liste.kod if liste else '', 
                    endpoint='/fiyat/api/siradaki-no', 
                    icon='bi bi-barcode', placeholder=_('Örn: LST-2026-001'), **theme).in_row('col-md-3')
    
    ad = FormField('ad', FieldType.TEXT, _('Liste Adı'), required=True, 
                   value=liste.ad if liste else '', 
                   placeholder=_('Örn: 2026 Kış Kampanyası'), **theme).in_row('col-md-5')
                   
    oncelik = FormField('oncelik', FieldType.NUMBER, _('Öncelik (En yüksek ezer)'), 
                        value=liste.oncelik if liste else 0, **theme).in_row('col-md-2')
                        
    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif'), 
                      value=liste.aktif if liste else True, **theme).in_row('col-md-2 pt-4')

    baslangic = FormField('baslangic_tarihi', FieldType.DATE, _('Başlangıç Tarihi'), 
                          value=liste.baslangic_tarihi.strftime('%Y-%m-%d') if liste and liste.baslangic_tarihi else '', **theme).in_row('col-md-3')
                          
    bitis = FormField('bitis_tarihi', FieldType.DATE, _('Bitiş Tarihi'), 
                      value=liste.bitis_tarihi.strftime('%Y-%m-%d') if liste and liste.bitis_tarihi else '', **theme).in_row('col-md-3')
    
    varsayilan = FormField('varsayilan', FieldType.SWITCH, _('Varsayılan Fiyat Listesi'), 
                           value=liste.varsayilan if liste else False,
                           help_text=_("Faturada/Siparişte liste seçilmezse bu fiyatlar uygulanır."), **theme).in_row('col-md-6 pt-4')

    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama / Notlar'), 
                         value=liste.aciklama if liste else '',
                         html_attributes={'rows': 2}, **theme).in_row('col-md-12')

    # ==========================================
    # 3. DETAYLAR (ÜRÜN FİYATLARI - AJAX ARAMA)
    # ==========================================
    detaylar = FormField('detaylar', FieldType.MASTER_DETAIL, _('Ürün Fiyatları'), required=True,
                         html_attributes={'id': 'fiyat_detaylari'}) 
    
    detaylar.columns = [
        # ✨ SİHİRLİ DOKUNUŞ: data-ajax-url eklendi!
        FormField('stok_id', FieldType.SELECT, _('Ürün'), 
                  options=stok_opts, required=True, 
                  html_attributes={
                      'style': 'width: 400px;', 
                      'class': 'js-stok-select',
                      'data-ajax-url': '/fatura/api/stok-ara',
                      'data-placeholder': 'Ürün Ara...'
                  }),
        
        FormField('fiyat', FieldType.CURRENCY, _('Birim Fiyat'), required=True, default_value=0,
                  html_attributes={'class': 'text-end', 'style': 'width: 120px;'}),
        
        FormField('iskonto_orani', FieldType.NUMBER, _('İskonto %'), default_value=0,
                  html_attributes={'class': 'text-end', 'style': 'width: 80px;', 'min': 0, 'max': 100}),
        
        FormField('min_miktar', FieldType.NUMBER, _('Min.Miktar'), default_value=1,
                  html_attributes={'style': 'width: 100px;', 'title': _('Bu fiyatın geçerli olması için minimum alım')})
    ]

    if is_edit and liste.detaylar:
        row_data = []
        for d in liste.detaylar:
            row_data.append({
                'stok_id': str(d.stok_id),
                'fiyat': float(d.fiyat),
                'iskonto_orani': float(d.iskonto_orani),
                'min_miktar': float(d.min_miktar)
            })
        detaylar.value = row_data

    # --- LAYOUT OLUŞTURMA ---
    layout.add_row(kod, ad, oncelik, aktif)
    layout.add_row(baslangic, bitis, varsayilan)
    layout.add_row(aciklama) 
    
    layout.add_html('<hr class="my-3 text-muted">')
    layout.add_row(detaylar)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, baslangic, bitis, oncelik, varsayilan, aktif, aciklama, detaylar)
    
    return form