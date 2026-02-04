# modules/fiyat/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from flask import url_for
from app.modules.stok.models import StokKart

def create_fiyat_listesi_form(liste=None):
    is_edit = liste is not None
    
    # Dinamik URL
    if is_edit:
        action_url = url_for('fiyat.duzenle', id=liste.id)
    else:
        action_url = url_for('fiyat.ekle')
    
    title = _("Fiyat Listesi Düzenle") if is_edit else _("Yeni Fiyat Listesi")
    
    form = Form(name="fiyat_listesi_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- Veri Hazırlığı ---
    stoklar = StokKart.query.filter_by(firma_id=current_user.firma_id, aktif=True).all()
    stok_opts = [(s.id, f"{s.kod} - {s.ad}") for s in stoklar]

    # --- 1.BAŞLIK BİLGİLERİ ---
    # Kod Alanı (Auto Number API'sine bağlı)
    kod = FormField('kod', FieldType.AUTO_NUMBER, _('Liste Kodu'), required=True, 
                    value=liste.kod if liste else '', 
                    endpoint='/fiyat-listesi/api/siradaki-no', # Veya /fiyat/api/...rotanıza göre
                    icon='bi bi-barcode', placeholder=_('Örn: LST-2025-001'))
    
    ad = FormField('ad', FieldType.TEXT, _('Liste Adı'), required=True, 
                   value=liste.ad if liste else '', 
                   placeholder=_('Örn: 2025 Kış Kampanyası'))
    
    baslangic = FormField('baslangic_tarihi', FieldType.DATE, _('Başlangıç Tarihi'), 
                          value=liste.baslangic_tarihi if liste else '')
                          
    bitis = FormField('bitis_tarihi', FieldType.DATE, _('Bitiş Tarihi'), 
                      value=liste.bitis_tarihi if liste else '')
    
    oncelik = FormField('oncelik', FieldType.NUMBER, _('Öncelik'), 
                        value=liste.oncelik if liste else 0, 
                        help_text=_("Çakışma durumunda yüksek öncelikli liste geçerlidir."))
    
    # ✅ YENİ: Varsayılan Seçeneği
    varsayilan = FormField('varsayilan', FieldType.SWITCH, _('Varsayılan Liste'), 
                           value=liste.varsayilan if liste else False,
                           help_text=_("Faturada liste seçilmezse bu fiyatlar uygulanır."))

    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif'), 
                      value=liste.aktif if liste else True)

    # ✅ YENİ: Açıklama Alanı
    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'), 
                         value=liste.aciklama if liste else '',
                         html_attributes={'rows': 2})

    # --- 2.DETAYLAR (ÜRÜN FİYATLARI) ---
    detaylar = FormField('detaylar', FieldType.MASTER_DETAIL, _('Ürün Fiyatları'), required=True,
                         html_attributes={'id': 'fiyat_detaylari'}) # ID Sabitledik
    
    detaylar.columns = [
        FormField('stok_id', FieldType.SELECT, _('Ürün'), 
                  options=stok_opts, required=True, 
                  select2_config={'placeholder': _('Ürün Seçiniz'), 'search': True},
                  html_attributes={'style': 'width: 300px;', 'class': 'js-stok-select'}),
        
        FormField('fiyat', FieldType.CURRENCY, _('Birim Fiyat'), required=True, default_value=0,
                  html_attributes={'class': 'text-end', 'style': 'width: 120px;'}),
        
        FormField('iskonto_orani', FieldType.NUMBER, _('İskonto %'), default_value=0,
                  html_attributes={'class': 'text-end', 'style': 'width: 80px;', 'min': 0, 'max': 100}),
        
        FormField('min_miktar', FieldType.NUMBER, _('Min.Miktar'), default_value=1,
                  html_attributes={'style': 'width: 100px;', 'title': _('Bu fiyatın geçerli olması için gereken en az alım adedi')})
    ]

    # Düzenleme modunda detayları doldur
    if is_edit and liste.detaylar:
        row_data = []
        for d in liste.detaylar:
            row_data.append({
                'stok_id': d.stok_id,
                'fiyat': float(d.fiyat),
                'iskonto_orani': float(d.iskonto_orani),
                'min_miktar': float(d.min_miktar)
            })
        detaylar.value = row_data

    # --- LAYOUT ---
    layout.add_row(kod, ad)
    layout.add_row(baslangic, bitis)
    layout.add_row(oncelik, varsayilan, aktif) # Varsayılan buraya eklendi
    layout.add_row(aciklama) # Açıklama buraya eklendi
    
    layout.add_html('<hr class="my-3 text-muted">')
    layout.add_row(detaylar)

    form.set_layout_html(layout.render())
    
    # Validasyon listesine yenileri ekle
    form.add_fields(kod, ad, baslangic, bitis, oncelik, varsayilan, aktif, aciklama, detaylar)
    
    return form