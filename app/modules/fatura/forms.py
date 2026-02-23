# app/modules/fatura/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _, lazy_gettext
from flask_login import current_user
from flask import url_for, session
from app.modules.depo.models import Depo
from app.modules.stok.models import StokKart
from app.modules.cari.models import CariHesap
from app.modules.siparis.models import OdemePlani
from app.modules.sube.models import Sube
from app.modules.fiyat.models import FiyatListesi
from app.enums import ParaBirimi, StokBirimleri, FaturaTuru
from app.araclar import para_cevir
from datetime import datetime
from markupsafe import Markup
from app.extensions import get_tenant_db, cache
import logging

# Logger
logger = logging.getLogger(__name__)

# Cache timeout
CACHE_TIMEOUT = 300

def create_fatura_form(fatura=None, tenant_db=None):
    """
    Fatura formu oluştur
    
    Args:
        fatura: Mevcut fatura (düzenleme için)
        tenant_db: Tenant database session (ÖNEMLİ!)
    """
    # ✅ Tenant DB session al
    if tenant_db is None:
        tenant_db = get_tenant_db()
    
    if not tenant_db:
        raise ValueError("Tenant DB bağlantısı yok!")
        
    is_edit = fatura is not None
    
    # Action URL
    if is_edit:
        action_url = url_for('fatura.duzenle', id=fatura.id)
        title = _(f"{fatura.belge_no} - Fatura Düzenle")
    else:
        action_url = url_for('fatura.ekle')
        title = _("Yeni Fatura Oluştur")
        
    form = Form(name="fatura_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    
    form_color = "primary"
    if fatura and 'alis' in str(fatura.fatura_turu):
        form_color = "warning"
    form.extra_context = {'card_color': form_color}
    
    layout = FormLayout()

    # ==========================================
    # 0.VERİ HAZIRLIĞI (OPTIONS)
    # ==========================================

    theme = {'colorfocus': '#e3f2fd', 'textfocus': '#1565c0', 'borderfocus': '#2196f3'}    
    
    try:
        # 1.Depolar (Yetki Kontrollü)
        depo_query = Depo.query.filter_by(firma_id=current_user.firma_id)
        if current_user.rol not in ['admin', 'patron', 'muhasebe_muduru']:
            aktif_bolge = session.get('aktif_bolge_id')
            aktif_sube = session.get('aktif_sube_id')
            if aktif_bolge:  depo_query = depo_query.join(Sube).filter(Sube.bolge_id == aktif_bolge)
            elif aktif_sube: depo_query = depo_query.filter_by(sube_id=aktif_sube)
        
        depo_opts = [(d.id, f"{d.ad}") for d in depo_query.all()]
    except Exception as e:
        logger.error(f"❌ Depo listesi hatası: {e}")
        # form.add_field('cari_id', 'text', 'Cari ID', required=True)

    # ✅ DEPOLAR (TENANT DB İLE!)
    try:
        depolar = tenant_db.query(Depo).filter_by(
            firma_id=firma_id,
            aktif=True
        ).order_by(Depo.ad).all()
        
        depo_choices = [(str(d.id), d.ad) for d in depolar]
        
        form.add_field(
            'depo_id', 'select', 'Depo',
            required=True,
            choices=depo_choices,
            value=str(fatura.depo_id) if fatura else None
        )
    except Exception as e:
        logger.error(f"❌ Depo listesi hatası: {e}")
        form.add_field('depo_id', FieldType.TEXT, _('Depo ID'), required=True)



    
    # 2.Cari
    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id, aktif=True).all()
    cari_opts = [(c.id, f"{c.unvan} ({c.kod})") for c in cariler]
    # Stoklar (Performanslı)
    stok_query = StokKart.query.filter_by(firma_id=current_user.firma_id)
    mevcut_stok_ids = [d.stok_id for d in fatura.kalemler] if (is_edit and fatura.kalemler) else []
    
    if mevcut_stok_ids:
        ilk_stoklar = stok_query.limit(50).all()
        yuklenen_ids = [s.id for s in ilk_stoklar]
        eksik_ids = set(mevcut_stok_ids) - set(yuklenen_ids)
        if eksik_ids:
            ekstra_stoklar = stok_query.filter(StokKart.id.in_(eksik_ids)).all()
            ilk_stoklar.extend(ekstra_stoklar)
        stoklar = ilk_stoklar
    else:
        stoklar = stok_query.limit(50).all()

    #stok_opts = [(s.id, f"{s.kod} - {s.ad} ({s.birim or 'Adet'})") for s in stoklar]
    stok_opts = []  # Boş başlat, AJAX ile dolacak

    # 3.Fiyat Listeleri
    listeler = FiyatListesi.query.filter_by(firma_id=current_user.firma_id, aktif=True).all()
    liste_opts = [(0, _("Varsayılan (Stok Kartı)"))] + [(str(l.id), l.ad) for l in listeler]

    fiyat_listesi = FormField('fiyat_listesi_id', FieldType.SELECT, _('Uygulanacak Fiyat Listesi'), 
                              options=liste_opts, 
                              value=fatura.fiyat_listesi_id if fatura and fatura.fiyat_listesi_id else '0', 
                              html_attributes={'id': 'fiyat_listesi_id'}, **theme).in_row("col-md-4 mb-2")

    # 4.Enumlar
    turu_opts = FaturaTuru.choices()
    doviz_opts = [(pb.name, pb.value) for pb in ParaBirimi]

    # --- Varsayılan Değerler ---
    bugun = datetime.now().strftime('%Y-%m-%d')
    val_tarih = fatura.tarih if fatura else bugun
    val_vade = fatura.vade_tarihi if fatura else bugun
    val_doviz = fatura.doviz_turu if fatura else ParaBirimi.TL.name
    val_kur = fatura.doviz_kuru if fatura else 1.0
    val_odeme = fatura.odeme_plani_id if fatura and fatura.odeme_plani_id else 0

    # Ödeme Planları
    odeme_planlari = OdemePlani.query.filter_by(firma_id=current_user.firma_id).all()
    odeme_opts = [(op.id, op.ad) for op in odeme_planlari]

    # ==========================================
    # 1.SEKME:  GENEL BİLGİLER
    # ==========================================
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Belge No'), required=True, 
                         value=fatura.belge_no if fatura else '', endpoint='/fatura/api/siradaki-no', 
                         icon='bi bi-qr-code', **theme).in_row("col-md-3")
    
    dis_belge_no = FormField('dis_belge_no', FieldType.TEXT, _('Karşı Belge No'), 
                             value=fatura.dis_belge_no if fatura else '', placeholder="Örn:  A-12345", 
                             icon='bi bi-receipt', **theme).in_row("col-md-3")

    tarih = FormField('tarih', FieldType.DATE, _('Fatura Tarihi'), required=True, 
                      value=val_tarih, html_attributes={'id': 'tarih'}, **theme).in_row("col-md-3")
                      
    vade_tarihi = FormField('vade_tarihi', FieldType.DATE, _('Vade Tarihi'), 
                            value=val_vade, **theme).in_row("col-md-3")
    
    fatura_turu = FormField('fatura_turu', FieldType.SELECT, _('Fatura Türü'), options=turu_opts, required=True, 
                            value=fatura.fatura_turu if fatura else FaturaTuru.SATIS.value,
                            html_attributes={'id': 'fatura_turu'}, **theme).in_row("col-md-2")

    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=cari_opts, required=True, 
                        value=fatura.cari_id if fatura else '', 
                        select2_config={'placeholder': 'Cari Seçiniz', 'search':  True},
                        html_attributes={'id': 'cari_select'}, **theme).in_row("col-md-4")

    depo_id = FormField('depo_id', FieldType.SELECT, _('Depo'), options=depo_opts, required=True, 
                        value=fatura.depo_id if fatura else '', **theme).in_row("col-md-4")
    
    odeme_plani_id = FormField('odeme_plani_id', FieldType.SELECT, 'Ödeme Planı', options=odeme_opts, value=val_odeme, **theme).in_row("col-md-2")

    kalemler = FormField('kalemler', FieldType.MASTER_DETAIL, _('Ürünler & Hizmetler'), required=True, 
                         html_attributes={'id': 'kalemler'})
    
    kalemler.columns = [
        FormField('id', FieldType.HIDDEN, 'ID', default_value=0, html_attributes={'style': 'width:  0px;'}),
        
        # ✅ DÜZELTME:  Statik options KALDIRILDI, AJAX ile dolacak
        FormField('stok_id', FieldType.SELECT, 'Ürün / Hizmet', 
                  options=stok_opts,  # ← BOŞTURUN
                  required=True, 
                  select2_config={
                        'placeholder': 'Ürün Seçiniz...',
                        'allowClear': False,
                        'ajax': {
                            'url': '/fatura/api/stok-ara',  # routes.py'deki endpoint
                            'dataType': 'json',
                            'delay': 250
                        }
                    },
                  html_attributes={
                      'style': 'width: 600px ; min-width: 600px; max-width: 600px;', 
                      'data-ajax-url': '/fatura/api/stok-ara',  # ← AJAX URL
                      'data-js': 'stok-select'
                  }),
        
        FormField('miktar', FieldType.NUMBER, 'Miktar', required=True, default_value=1, 
                  html_attributes={'class': 'text-end', 'style': 'width: 100px;', 'data-js': 'miktar-input', 'data-calc': 'qty'}),
        
        FormField('birim', FieldType.SELECT, 'Birim', options=StokBirimleri.choices(), default_value='Adet', 
                  html_attributes={'style': 'width: 120px;', 'data-js': 'birim-select'}),

        FormField('birim_fiyat', FieldType.CURRENCY, 'Birim Fiyat', required=True, default_value=0, 
                  html_attributes={'class': 'text-end', 'style': 'width: 150px;', 'data-js': 'fiyat-input', 'data-calc': 'price'}),
        
        FormField('indirim_orani', FieldType.NUMBER, 'İsk.%', default_value=0, 
                  html_attributes={'class': 'text-end', 'style': 'width: 80px;', 'data-js': 'iskonto-input', 'data-calc': 'discount'}),

        FormField('kdv_orani', FieldType.SELECT, 'KDV', 
                  options=[(0, '%0'), (1, '%1'), (8, '%8'), (10, '%10'), (18, '%18'), (20, '%20')], default_value=20,
                  html_attributes={'style': 'width: 70px;', 'data-js': 'kdv-input', 'data-calc': 'tax'}),

        FormField('satir_toplami', FieldType.CURRENCY, 'Tutar', readonly=True, 
                  html_attributes={'class': 'text-end fw-bold', 'style': 'width: 200px; background-color: #f8f9fa;', 'data-calc': 'total'})
    ]
    
    # ✅ DÜZELTME:  Edit modunda kalem verileri doğru şekilde hazırla
    if is_edit and fatura.kalemler:
        row_data = []
        for k in fatura.kalemler:
            row_data.append({
                'id': k.id,
                'stok_id':  k.stok_id,  # ← Bu değer AJAX ile tekrar çekilecek
                'miktar': float(k.miktar),
                'birim': k.birim or 'Adet',
                'birim_fiyat':  float(k.birim_fiyat),
                'indirim_orani': float(k.iskonto_orani or 0),
                'kdv_orani': int(k.kdv_orani or 0),
                'satir_toplami': float(k.satir_toplami)
            })
        kalemler.value = row_data

    # ==========================================
    # 3.SEKME: FİNANS & TESLİMAT
    # ==========================================
    
    doviz_turu = FormField('doviz_turu', FieldType.SELECT, _('Para Birimi'), options=doviz_opts, value=val_doviz,
                           html_attributes={'id': 'doviz_turu_select'}, **theme).in_row("col-md-4")

    doviz_kuru = FormField('doviz_kuru', FieldType.CURRENCY, _('Kur Değeri'), value=val_kur,
                           html_attributes={'id': 'doviz_kuru_input', 'style': 'font-weight: bold;'}, **theme).in_row("col-md-4")

    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Genel Açıklama'), 
                         value=fatura.aciklama if fatura else '', html_attributes={'rows': 2}, **theme).in_row("col-md-12")
    
    sevk_adresi = FormField('sevk_adresi', FieldType.TEXTAREA, _('Sevk/Teslimat Adresi'), 
                            value=fatura.sevk_adresi if fatura else '', 
                            placeholder=_("Cari adresten farklıysa giriniz..."),
                            html_attributes={'rows': 2, 'id': 'sevk_adresi'}, **theme).in_row("col-md-12")

    # ==========================================
    # LAYOUT OLUŞTURMA
    # ==========================================
    
    tab_genel = [
        layout.create_row(belge_no, dis_belge_no, tarih, vade_tarihi),
        layout.create_row(fatura_turu, cari_id, depo_id, odeme_plani_id)
    ]
    
    tab_kalemler = [
        layout.create_alert("Bilgi", "Döviz türünü seçtiğinizde kur otomatik güncellenecektir.", "info", "bi-info-circle"),
        layout.create_row(fiyat_listesi, doviz_turu, doviz_kuru),
        kalemler
    ]
    
    tab_finans = [
        aciklama,
        sevk_adresi
    ]
    
    if is_edit:
        efatura_html = f'''
        <div class="mt-3 p-3 bg-white border rounded shadow-sm">
            <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-cloud-arrow-up me-2"></i>E-Fatura Entegrasyonu</h6>
            <div class="d-flex gap-2">
                <button type="button" onclick="eFaturaGonder({fatura.id})" class="btn btn-primary">
                    <i class="bi bi-send me-1"></i> GİB'e Gönder
                </button>
                <button type="button" onclick="eFaturaDurum({fatura.id})" class="btn btn-info text-white">
                    <i class="bi bi-arrow-repeat me-1"></i> Durum Sorgula
                </button>
            </div>
        </div>
        '''
        tab_efatura = [layout.create_html(efatura_html)]
    else:
        tab_efatura = []

    tabs_content = [
        (Markup('<i class="bi bi-info-circle me-2"></i>Genel Bilgiler'), tab_genel),
        (Markup('<i class="bi bi-list-check me-2"></i>Finans & Fatura Kalemleri'), tab_kalemler),
        (Markup('<i class="bi bi-wallet2 me-2"></i>Teslimat'), tab_finans)
    ]
    
    if is_edit:
        tabs_content.append((Markup('<i class="bi bi-globe me-2"></i>E-Fatura'), tab_efatura))

    tabs = layout.create_tabs("fatura_tabs", tabs_content)
    form.set_layout_html(tabs)
    
    form.add_fields(
        belge_no, dis_belge_no, tarih, vade_tarihi, fatura_turu, cari_id, depo_id, odeme_plani_id,
        fiyat_listesi, doviz_turu, doviz_kuru, aciklama, sevk_adresi, kalemler
    )
    
    return form