# app/modules/siparis/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from datetime import datetime
from app.extensions import get_tenant_db # 👈 Firebird Bağlantısı
# Modeller
from app.modules.cari.models import CariHesap
from app.modules.depo.models import Depo
from app.modules.stok.models import StokKart
from app.modules.fiyat.models import FiyatListesi
from app.modules.siparis.models import Siparis, OdemePlani
from app.enums import ParaBirimi, SiparisDurumu, StokBirimleri
from app.araclar import sayi_formatla

def create_siparis_form(siparis=None):
    is_edit = siparis is not None
    action_url = f"/siparis/duzenle/{siparis.id}" if is_edit else "/siparis/ekle"
    title = _("Sipariş Düzenle") if is_edit else _("Yeni Sipariş")
    
    form = Form(name="siparis_form", title='', action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    tenant_db = get_tenant_db()
    
    # Varsayılan boş listeler
    cariler = []
    depolar = []
    stok_opts = []
    liste_opts = []
    odeme_opts = []

    if tenant_db:
        # --- 1.SEÇENEKLER (FIREBIRD) ---
        try:
            cariler = [(c.id, c.unvan) for c in tenant_db.query(CariHesap).filter_by(firma_id=1).all()]
            depolar = [(d.id, d.ad) for d in tenant_db.query(Depo).filter_by(firma_id=1).all()]

            # Stoklar (İlk 50 tane)
            stok_query = tenant_db.query(StokKart).filter_by(firma_id=1)
            # Eğer düzenleme modundaysak ve detaylarda stok varsa onları da çek
            mevcut_stok_ids = [d.stok_id for d in siparis.detaylar] if (is_edit and siparis.detaylar) else []
            
            ilk_stoklar = stok_query.limit(50).all()
            
            # Eksik olan (listede olmayan ama siparişte olan) stokları ekle
            yuklenen_ids = [s.id for s in ilk_stoklar]
            eksik_ids = set(mevcut_stok_ids) - set(yuklenen_ids)
            
            if eksik_ids:
                ekstra_stoklar = stok_query.filter(StokKart.id.in_(eksik_ids)).all()
                ilk_stoklar.extend(ekstra_stoklar)
                
            stok_opts = [(s.id, f"{s.kod} - {s.ad} ({s.birim or 'Adet'})") for s in ilk_stoklar]

            # Fiyat Listeleri
            fiyat_listeleri = tenant_db.query(FiyatListesi).filter_by(firma_id=1, aktif=True).all()
            liste_opts = [(fl.id, fl.ad) for fl in fiyat_listeleri]
            liste_opts.insert(0, (0, "Varsayılan (Stok Kartı)"))
            
            # Ödeme Planları
            odeme_planlari = tenant_db.query(OdemePlani).filter_by(firma_id=1).all()
            odeme_opts = [(op.id, op.ad) for op in odeme_planlari]
            odeme_opts.insert(0, (0, "Peşin"))

        except Exception as e:
            print(f"Form Seçenekleri Hatası: {e}")

    doviz_opts = [(pb.name, pb.value) for pb in ParaBirimi]
    durum_opts = SiparisDurumu.choices()

    # --- 2.DEĞER ATAMALARI (VALUES) ---
    val_doviz = siparis.doviz_turu if (siparis and hasattr(siparis, 'doviz_turu')) else ParaBirimi.TL.name
    val_fiyat_list = siparis.fiyat_listesi_id if (siparis and siparis.fiyat_listesi_id) else 0
    val_odeme = siparis.odeme_plani_id if (siparis and siparis.odeme_plani_id) else 0
    val_durum = siparis.durum if siparis else SiparisDurumu.BEKLIYOR.value
    val_depo = siparis.depo_id if siparis else (depolar[0][0] if depolar else '')

    # --- 3.FORM ALANLARI ---
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Belge No'), required=True, value=siparis.belge_no if siparis else '', endpoint='/siparis/api/siradaki-no', icon='bi bi-receipt')
    tarih = FormField('tarih', FieldType.DATE, 'Tarih', required=True, value=siparis.tarih if siparis else datetime.now().strftime('%Y-%m-%d'))
    teslim_tarihi = FormField('teslim_tarihi', FieldType.DATE, 'Teslim Tarihi', value=siparis.teslim_tarihi if siparis else '')
    
    durum = FormField('durum', FieldType.SELECT, 'Durum', options=durum_opts, required=True, value=val_durum)
    cari_id = FormField('cari_id', FieldType.SELECT, 'Müşteri', options=cariler, required=True, select2_config={'search': True, 'placeholder': 'Müşteri Seçiniz...'}, value=siparis.cari_id if siparis else '')
    depo_id = FormField('depo_id', FieldType.SELECT, 'Çıkış Deposu', options=depolar, required=True, value=val_depo)
    
    doviz_turu = FormField('doviz_turu', FieldType.SELECT, 'Döviz', options=doviz_opts, value=val_doviz)
    doviz_kuru = FormField('doviz_kuru', FieldType.CURRENCY, 'Döviz Kuru', value=siparis.doviz_kuru if siparis else 1, html_attributes={'style': 'width: 100px;'})
    
    fiyat_listesi_id = FormField('fiyat_listesi_id', FieldType.SELECT, 'Fiyat Listesi', options=liste_opts, value=val_fiyat_list)
    odeme_plani_id = FormField('odeme_plani_id', FieldType.SELECT, 'Ödeme Planı', options=odeme_opts, value=val_odeme)

    sevk_adresi = FormField('sevk_adresi', FieldType.TEXTAREA, 'Sevk Adresi', value=siparis.sevk_adresi if siparis else '', html_attributes={'rows': 2})
    aciklama = FormField('aciklama', FieldType.TEXTAREA, 'Notlar', value=siparis.aciklama if siparis else '', html_attributes={'rows': 2})

    # --- 4.MASTER-DETAIL ---
    detaylar = FormField('detaylar', FieldType.MASTER_DETAIL, 'Ürünler')
    detaylar.columns = [
        FormField('id', FieldType.HIDDEN, 'ID', default_value=0,html_attributes={'style': 'width: 0px;'}),
        
        FormField('stok_id', FieldType.SELECT, 'Ürün', 
                  options=stok_opts, 
                  required=True, 
                  html_attributes={
                      'style': 'width: 400px;', 
                      'data-ajax-url': '/siparis/api/stok-ara',
                      'data-placeholder': 'Ürün adı veya kodu arayın...'
                  }),
        FormField('miktar', FieldType.NUMBER, 'Miktar', default_value=1, html_attributes={'step': '0.01', 'style': 'width: 80px;'}),
        FormField('birim', FieldType.SELECT, 'Birim', options=StokBirimleri.choices(), default_value='Adet', html_attributes={'style': 'width: 90px;'}),
        FormField('birim_fiyat', FieldType.CURRENCY, 'Birim Fiyat', default_value=0, html_attributes={'style': 'width: 100px;'}),
        FormField('iskonto_orani', FieldType.NUMBER, 'İsk.%', default_value=0, html_attributes={'max': 100, 'style': 'width: 70px;'}),
        FormField('kdv_orani', FieldType.NUMBER, 'KDV%', default_value=20, html_attributes={'style': 'width: 70px;'}),
        FormField('tutar', FieldType.CURRENCY, 'Satır Toplamı', html_attributes={'readonly': True, 'style': 'width: 120px; font-weight: bold;'})
    ]

    if is_edit and siparis.detaylar:
        row_data = []
        for d in siparis.detaylar:
            row_data.append({
                'id': d.id,
                'stok_id': d.stok_id,
                'miktar': float(d.miktar), 
                'birim': d.birim or 'Adet',
                'birim_fiyat': sayi_formatla(d.birim_fiyat), 
                'iskonto_orani': (d.iskonto_orani), 
                'kdv_orani': (d.kdv_orani), 
                'tutar': sayi_formatla(d.satir_toplami)
            })
        detaylar.value = row_data

    layout.add_row(belge_no, tarih, teslim_tarihi, durum)
    layout.add_row(cari_id, depo_id)
    layout.add_row(doviz_turu, doviz_kuru, fiyat_listesi_id, odeme_plani_id)
    layout.add_row(sevk_adresi, aciklama)
    layout.add_row(detaylar)

    form.set_layout_html(layout.render())
    form.add_fields(belge_no, tarih, teslim_tarihi, doviz_turu, durum, odeme_plani_id, cari_id, depo_id, fiyat_listesi_id, sevk_adresi, aciklama, detaylar, doviz_kuru)
    
    return form