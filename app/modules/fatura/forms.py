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
        raise ValueError("Tenant DB bulunamadı!")

    is_edit = fatura is not None
    action_url = f"/fatura/duzenle/{fatura.id}" if is_edit else "/fatura/ekle"
    title = _("Fatura Düzenle") if is_edit else _("Yeni Fatura Oluştur")
    
    form = Form(name="fatura_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # ==========================================
    # 0. VERİ HAZIRLIĞI (OPTIONS & AKILLI FİLTRELER)
    # ==========================================
    theme = {'colorfocus': '#e3f2fd', 'textfocus': '#1565c0', 'borderfocus': '#2196f3'}    
    
    # ✨ AKILLI HAFIZA: Sağ üstten seçilen veya kullanıcının zorunlu olduğu şube/bölgeyi al
    aktif_sube_id = session.get('aktif_sube_id')
    aktif_bolge_id = session.get('aktif_bolge_id')

    # 1. Şube Listesi (Yeni Eklendi)
    try:
        sube_query = tenant_db.query(Sube).filter_by(aktif=True)
        
        # Eğer kullanıcı admin/patron değilse, sadece kendi şubesini/bölgesini görebilsin
        if current_user.rol not in ['admin', 'patron', 'muhasebe_muduru']:
             if aktif_bolge_id: sube_query = sube_query.filter_by(bolge_id=aktif_bolge_id)
             elif aktif_sube_id: sube_query = sube_query.filter_by(id=aktif_sube_id)
             
        sube_opts = [(str(s.id), s.ad) for s in sube_query.order_by(Sube.ad).all()]
    except Exception as e:
        logger.error(f"❌ Şube listesi hatası: {e}")
        sube_opts = []

    # ======================================================
    # 2. Akıllı Depo Listesi (Yetki + Bağımlı Kutu Uyumu)
    # ======================================================
    try:
        depo_opts = []
        auto_depo_id = ''

        # DURUM 1: DÜZENLEME MODU (Mevcut fatura açılıyorsa)
        # Sadece o faturaya ait depoyu listeye koyalım ki seçili gelsin
        if is_edit and getattr(fatura, 'depo_id', None):
            secili_depo = tenant_db.query(Depo).get(fatura.depo_id)
            if secili_depo:
                depo_opts = [(str(secili_depo.id), secili_depo.ad)]
                auto_depo_id = str(secili_depo.id)

        # DURUM 2: YENİ FATURA + ŞUBE KİLİTLİ 
        # Sağ üstten "MENEMEN" seçilmişse, yetki kurgundan geçirerek sadece oranın depolarını yükle
        elif aktif_sube_id:
            depo_query = tenant_db.query(Depo).filter_by(firma_id=current_user.firma_id, aktif=True, sube_id=aktif_sube_id)
            
            # Senin Yetki Kurgun: Normal personelse bölge kontrolü de yap!
            if current_user.rol not in ['admin', 'patron', 'muhasebe_muduru'] and aktif_bolge_id:
                depo_query = depo_query.join(Sube).filter(Sube.bolge_id == aktif_bolge_id)
                
            depos = depo_query.order_by(Depo.ad).all()
            depo_opts = [(str(d.id), d.ad) for d in depos]
            
            if depos:
                auto_depo_id = str(depos[0].id) # O şubenin ilk deposunu otomatik seç

        # DURUM 3: YENİ FATURA + "TÜM ŞUBELER" MODU (Şube boş)
        # Kullanıcı "Tüm Şubeler" modunda yeni fatura kesiyor. 
        # Formda önce Şubeyi seçecek. Bu yüzden Depo listesini BOŞ başlatıyoruz.
        # Javascript (AJAX) Şube seçildiği an API'ye gidip burayı dolduracak!
        else:
            depo_opts = []
            auto_depo_id = ''

    except Exception as e:
        logger.error(f"❌ Depo listesi hatası: {e}")
        depo_opts = []
        auto_depo_id = ''

    # 3. Cari Hesaplar (Performanslı AJAX Lazy Load)
    cari_opts = []
    if is_edit and getattr(fatura, 'cari_id', None):
        try:
            secili_cari = tenant_db.query(CariHesap).get(fatura.cari_id)
            if secili_cari:
                cari_opts = [(str(secili_cari.id), f"{secili_cari.unvan} ({secili_cari.kod})")]
        except Exception as e:
            logger.error(f"❌ Seçili Cari getirme hatası: {e}")

    # 4. Stoklar (AJAX) - Düzenleme modunda mevcut ürünler gelsin
    stok_opts = []
    if is_edit and fatura.kalemler:
        for k in fatura.kalemler:
            if k.stok:
                stok_opts.append((str(k.stok_id), f"{k.stok.kod} - {k.stok.ad}"))

    # 5. Fiyat Listeleri
    try:
        listeler = tenant_db.query(FiyatListesi).filter_by(aktif=True).all()
        liste_opts = [(0, _("Varsayılan (Stok Kartı)"))] + [(str(l.id), l.ad) for l in listeler]
    except Exception:
        liste_opts = [(0, _("Varsayılan (Stok Kartı)"))]

    # 6. Enumlar ve Seçenekler 
    turu_opts = FaturaTuru.choices()
    doviz_opts = [(pb.name, pb.value) for pb in ParaBirimi]

    # ✨ 7. TARİH VE VARSAYILAN DEĞERLER (KESİN ÇÖZÜM)
    bugun_str = datetime.now().strftime('%Y-%m-%d')
    
    # Tarihleri kesinlikle String'e (YYYY-MM-DD) çeviriyoruz!
    val_tarih = fatura.tarih.strftime('%Y-%m-%d') if fatura and getattr(fatura, 'tarih', None) else bugun_str
    val_vade = fatura.vade_tarihi.strftime('%Y-%m-%d') if fatura and getattr(fatura, 'vade_tarihi', None) else bugun_str
    
    # Şube ve Depo varsayılanları
    val_sube = str(fatura.sube_id) if fatura else (aktif_sube_id or '')
    val_depo = str(fatura.depo_id) if fatura else auto_depo_id

    val_doviz = fatura.doviz_turu.name if fatura and hasattr(fatura.doviz_turu, 'name') else str(fatura.doviz_turu) if fatura else ParaBirimi.TL.name
    val_kur = fatura.doviz_kuru if fatura else 1.0
    val_odeme = str(fatura.odeme_plani_id) if fatura and fatura.odeme_plani_id else '0'
    val_liste = str(fatura.fiyat_listesi_id) if fatura and fatura.fiyat_listesi_id else '0'
    val_fatura_turu = str(fatura.fatura_turu.value if hasattr(fatura.fatura_turu, 'value') else fatura.fatura_turu).lower() if fatura else FaturaTuru.SATIS.value
    
    # 8. Ödeme Planları
    try:
        odeme_opts = [(str(op.id), op.ad) for op in tenant_db.query(OdemePlani).all()]
    except Exception:
        odeme_opts = []

    # ==========================================
    # 1.SEKME:  GENEL BİLGİLER
    # ==========================================
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Belge No'), required=True, 
                         value=fatura.belge_no if fatura else '', endpoint='/fatura/api/siradaki-no', 
                         icon='bi bi-qr-code', **theme).in_row("col-md-3")
    
    dis_belge_no = FormField('dis_belge_no', FieldType.TEXT, _('Karşı Belge No'), 
                             value=fatura.dis_belge_no if fatura else '', placeholder="Örn: A-12345", 
                             icon='bi bi-receipt', **theme).in_row("col-md-3")

    tarih = FormField('tarih', FieldType.DATE, _('Fatura Tarihi'), required=True, 
                      value=val_tarih, html_attributes={'id': 'tarih'}, **theme).in_row("col-md-3")
                      
    vade_tarihi = FormField('vade_tarihi', FieldType.DATE, _('Vade Tarihi'), 
                            value=val_vade, **theme).in_row("col-md-3")
    
    fatura_turu = FormField('fatura_turu', FieldType.SELECT, _('Fatura Türü'), options=turu_opts, required=True, 
                            value=val_fatura_turu, html_attributes={'id': 'fatura_turu'}, **theme).in_row("col-md-2")

    # ✨ YENİ EKLENDİ: Şube Seçimi
    sube_id = FormField('sube_id', FieldType.SELECT, _('Şube'), options=sube_opts, required=True, 
                        value=val_sube, 
                        # Sağ üstten şube kilitlendiyse, personelin formda değiştirmesini engelle:
                        html_attributes={'style': 'pointer-events: none; background-color: #e9ecef;'} if aktif_sube_id else {}, 
                        **theme).in_row("col-md-2")

    # Depo alanı daraltıldı
    depo_id = FormField(
        'depo_id', 
        FieldType.SELECT, 
        _('Depo'), 
        options=depo_opts, 
        required=True, 
        value=val_depo, 
        # 👇 SİHİRLİ DOKUNUŞ: Bağımlılık Ayarları
        html_attributes={
            'data-dependent-parent': 'sube_id',       # Hangi kutuyu dinleyecek?
            'data-source-url': '/fatura/api/get-depolar' # Veriyi nereden çekecek?
        },
        **theme
    ).in_row("col-md-2")

    odeme_plani_id = FormField('odeme_plani_id', FieldType.SELECT, 'Ödeme Planı', options=odeme_opts, 
                               value=val_odeme, **theme).in_row("col-md-2")

    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=cari_opts, required=True, 
                        value=str(fatura.cari_id) if fatura else '', 
                        select2_config={'placeholder': 'Aramak için yazın...', 'search':  True},
                        html_attributes={'id': 'cari_select', 'data-ajax-url': '/cari/api/ara'}, **theme).in_row("col-md-4")

    # ==========================================
    # 2.SEKME: FİNANS & FATURA KALEMLERİ
    # ==========================================
    fiyat_listesi = FormField('fiyat_listesi_id', FieldType.SELECT, _('Uygulanacak Fiyat Listesi'), 
                              options=liste_opts, value=val_liste, 
                              html_attributes={'id': 'fiyat_listesi_id'}, **theme).in_row("col-md-4 mb-2")
                              
    doviz_turu = FormField('doviz_turu', FieldType.SELECT, _('Para Birimi'), options=doviz_opts, value=val_doviz,
                           html_attributes={'id': 'doviz_turu_select'}, **theme).in_row("col-md-4")

    doviz_kuru = FormField('doviz_kuru', FieldType.CURRENCY, _('Kur Değeri'), value=val_kur,
                           html_attributes={'id': 'doviz_kuru_input', 'style': 'font-weight: bold;'}, **theme).in_row("col-md-4")


    kalemler = FormField('kalemler', FieldType.MASTER_DETAIL, _('Ürünler & Hizmetler'), required=True, 
                         html_attributes={'id': 'kalemler'})
    
    kalemler.columns = [
        FormField('id', FieldType.HIDDEN, 'ID', default_value=0, html_attributes={'style': 'width:  0px;'}),
        FormField('stok_id', FieldType.SELECT, 'Ürün / Hizmet', options=stok_opts, required=True, 
                  select2_config={'placeholder': 'Ürün Seçiniz...', 'allowClear': False, 'ajax': {'url': '/fatura/api/stok-ara', 'dataType': 'json', 'delay': 250}},
                  html_attributes={'style': 'width: 600px ; min-width: 600px; max-width: 600px;', 'data-ajax-url': '/fatura/api/stok-ara', 'data-js': 'stok-select'}),
        FormField('miktar', FieldType.NUMBER, 'Miktar', required=True, default_value=1, html_attributes={'class': 'text-end', 'style': 'width: 100px;', 'data-js': 'miktar-input', 'data-calc': 'qty'}),
        FormField('birim', FieldType.SELECT, 'Birim', options=StokBirimleri.choices(), default_value='Adet', html_attributes={'style': 'width: 120px;', 'data-js': 'birim-select'}),
        FormField('birim_fiyat', FieldType.CURRENCY, 'Birim Fiyat', required=True, default_value=0, html_attributes={'class': 'text-end', 'style': 'width: 150px;', 'data-js': 'fiyat-input', 'data-calc': 'price'}),
        FormField('indirim_orani', FieldType.NUMBER, 'İsk.%', default_value=0, html_attributes={'class': 'text-end', 'style': 'width: 80px;', 'data-js': 'iskonto-input', 'data-calc': 'discount'}),
        FormField('kdv_orani', FieldType.SELECT, 'KDV', options=[(0, '%0'), (1, '%1'), (8, '%8'), (10, '%10'), (18, '%18'), (20, '%20')], default_value=20, html_attributes={'style': 'width: 70px;', 'data-js': 'kdv-input', 'data-calc': 'tax'}),
        FormField('satir_toplami', FieldType.CURRENCY, 'Tutar', readonly=True, html_attributes={'class': 'text-end fw-bold', 'style': 'width: 200px; background-color: #f8f9fa;', 'data-calc': 'total'})
    ]
    
    if is_edit and fatura.kalemler:
        row_data = []
        for k in fatura.kalemler:
            # ✨ DÜZELTME 3: BİRİM UYUMSUZLUĞU ÇÖZÜMÜ
            b_val = k.birim.value if hasattr(k.birim, 'value') else str(k.birim).capitalize() if k.birim else 'Adet'
            row_data.append({
                'id': k.id,
                'stok_id': str(k.stok_id),
                'miktar': float(k.miktar),
                'birim': b_val,
                'birim_fiyat':  float(k.birim_fiyat),
                'indirim_orani': float(k.iskonto_orani or 0),
                'kdv_orani': int(k.kdv_orani or 0),
                'satir_toplami': float(k.satir_toplami)
            })
        kalemler.value = row_data

    # ==========================================
    # 3.SEKME: TESLİMAT VE DİĞER
    # ==========================================
    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Genel Açıklama'), 
                         value=fatura.aciklama if fatura else '', html_attributes={'rows': 2}, **theme).in_row("col-md-12")
    
    sevk_adresi = FormField('sevk_adresi', FieldType.TEXTAREA, _('Sevk/Teslimat Adresi'), 
                            value=fatura.sevk_adresi if fatura else '', 
                            placeholder=_("Cari adresten farklıysa giriniz..."),
                            html_attributes={'rows': 2, 'id': 'sevk_adresi'}, **theme).in_row("col-md-12")

    # ==========================================
    # LAYOUT OLUŞTURMA
    # ==========================================
    ocr_html = layout.create_html('''
    <div class="alert alert-info py-2 d-flex justify-content-between align-items-center">
        <span><i class="bi bi-robot me-2"></i>AI Destekli Fatura Okuma aktif.</span>
        <button type="button" class="btn btn-info btn-sm text-white" onclick="document.getElementById('ocr_file_input').click()">Yükle</button>
    </div>
    ''')
    tab_genel = [
        ocr_html,
        layout.create_row(belge_no, dis_belge_no, tarih, vade_tarihi),
        layout.create_row(fatura_turu, sube_id, depo_id, odeme_plani_id, cari_id)
    ]
    
    tab_kalemler = [
        layout.create_alert("Bilgi", "Döviz türünü seçtiğinizde kur otomatik güncellenecektir.", "info", "bi-info-circle"),
        layout.create_row(fiyat_listesi, doviz_turu, doviz_kuru)
    ]
    
    # ✨ KÂR ANALİZİ BUTONU: Sadece kayıtlı (düzenlenen) faturalarda görünür
    if is_edit:
        analiz_html = f'''
        <div class="d-flex justify-content-end mb-2">
            <button type="button" onclick="karlilikAnaliziGetir('{fatura.id}')" class="btn btn-outline-success border-2 fw-bold shadow-sm">
                <i class="bi bi-graph-up-arrow me-1"></i> Maliyet ve Kâr Analizi
            </button>
        </div>
        '''
        tab_kalemler.append(layout.create_html(analiz_html))
        
    tab_kalemler.append(kalemler) # Kalemler tablosunu en sona ekliyoruz
    
    tab_finans = [
        aciklama,
        sevk_adresi
    ]
    
    if is_edit:
        efatura_html = f'''
        <div class="mt-3 p-3 bg-white border rounded shadow-sm">
            <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-cloud-arrow-up me-2"></i>E-Fatura Entegrasyonu</h6>
            <div class="d-flex gap-2">
                <button type="button" onclick="eFaturaGonder('{fatura.id}')" class="btn btn-primary">
                    <i class="bi bi-send me-1"></i> GİB'e Gönder
                </button>
                <button type="button" onclick="eFaturaDurum('{fatura.id}')" class="btn btn-info text-white">
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
    
    # Form field'larını kaydet (Post sırasında yakalayabilmek için)
    form.add_fields(
        belge_no, dis_belge_no, tarih, vade_tarihi, fatura_turu, cari_id, sube_id, depo_id, odeme_plani_id,
        fiyat_listesi, doviz_turu, doviz_kuru, kalemler, aciklama, sevk_adresi
    )
    
    return form