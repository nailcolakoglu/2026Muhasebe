from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.sube.models import Sube
from app.modules.kullanici.models import Kullanici
from app.modules.stok.models import StokKart, StokMuhasebeGrubu, StokKDVGrubu, StokPaketIcerigi
from app.modules.kategori.models import StokKategori
from app.modules.cari.models import CariHesap
from app.modules.muhasebe.models import HesapPlani
from app.models import AIRaporAyarlari
from app.modules.muhasebe.utils import get_muhasebe_hesaplari
from markupsafe import Markup
from app.extensions import get_tenant_db # GOLDEN RULE
from flask import flash, redirect, url_for

def create_stok_form(stok=None):

    tenant_db = get_tenant_db()
    
    if not tenant_db: 
        flash('Firebird bağlantısı yok. Lütfen firma seçin.', 'danger')
        return redirect(url_for('main.index'))
    
    is_edit = stok is not None
    action_url = f"/stok/duzenle/{stok.id}" if is_edit else "/stok/ekle"
    title = _("Stok Kartı Düzenle") if is_edit else _("Yeni Stok Kartı")
    
    form = Form(name="stok_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    form_color = "primary" 
    form.extra_context = {'card_color': form_color}
        
    layout = FormLayout()

    # --- SELECT OPTIONS (HEPSİ TENANT DB'DEN) ---
    kategoriler = tenant_db.query(StokKategori).filter_by(firma_id=current_user.firma_id).all()
    kategori_opts = [(k.id, k.ad) for k in kategoriler]
    
    muh_gruplar = tenant_db.query(StokMuhasebeGrubu).filter_by(firma_id=current_user.firma_id, aktif=True).all()
    muhasebe_opts = [(g.id, f"{g.kod} - {g.ad}") for g in muh_gruplar]
    
    kdv_gruplar = tenant_db.query(StokKDVGrubu).filter_by(firma_id=current_user.firma_id).all()
    kdv_opts = [(k.id, f"{k.ad} (Alış:%{k.alis_kdv_orani}, Satış:%{k.satis_kdv_orani})") for k in kdv_gruplar]
    
    tedarikciler = tenant_db.query(CariHesap).filter_by(firma_id=current_user.firma_id).order_by(CariHesap.unvan).all()
    tedarikci_opts = [("", "Seçiniz...")] + [(c.id, c.unvan) for c in tedarikciler]

    birim_opts = [('Adet', 'Adet'), ('Kg', 'Kg'), ('Lt', 'Lt'), ('Mt', 'Metre'), ('Kutu', 'Kutu'), ('Paket', 'Paket'), ('Set', 'Set')]
    doviz_opts = [('TL', 'TL'), ('USD', 'USD'), ('EUR', 'EUR')]
    
    tip_opts = [('standart', 'Standart Ürün'), ('hizmet', 'Hizmet'), ('paket', 'Paket'), ('mamul', 'Mamul'), ('yari_mamul', 'Yarı Mamul'), ('hammadde', 'Hammadde')]
    
    mevsim_opts = [('', 'Yok'), ('kis', 'Kış Sezonu'), ('yaz', 'Yaz Sezonu'), ('ilkbahar', 'İlkbahar'), ('sonbahar', 'Sonbahar'), ('okul', 'Okul Sezonu'), ('yilbasi', 'Yılbaşı')]

    common_theme = {'colorfocus': '#e3f2fd', 'textfocus': '#1565c0', 'borderfocus': '#2196f3'}

    # ==========================================
    # 1.SEKME: TEMEL BİLGİLER
    # ==========================================
    kod = FormField('kod', FieldType.AUTO_NUMBER, _('Stok Kodu'), required=True, value=stok.kod if stok else '', endpoint='/stok/api/siradaki-kod', icon='bi bi-qr-code', **common_theme).in_row("col-md-4")
    barkod = FormField('barkod', FieldType.NUMBER, _('Barkod'), value=stok.barkod if stok else '', icon='bi bi-upc-scan', **common_theme).in_row("col-md-4")
    uretici_kodu = FormField('uretici_kodu', FieldType.TEXT, _('Üretici Kodu (MPN)'), value=stok.uretici_kodu if stok else '', placeholder="Fabrika Kodu", **common_theme).in_row("col-md-4")
    
    ad = FormField('ad', FieldType.TEXT, _('Stok Adı'), required=True, value=stok.ad if stok else '', icon='bi bi-box-seam', text_transform='uppercase', **common_theme)
    
    kategori_id = FormField('kategori_id', FieldType.SELECT, _('Kategori'), options=kategori_opts, required=True, value=stok.kategori_id if stok else '', select2_config={'placeholder': 'Seçiniz', 'allowClear': True}, **common_theme).in_row("col-md-3")
    birim = FormField('birim', FieldType.SELECT, _('Birim'), options=birim_opts, required=True, value=stok.birim if stok else 'Adet', **common_theme).in_row("col-md-3")
    tip = FormField('tip', FieldType.SELECT, _('Stok Tipi'), options=tip_opts, required=True, value=stok.tip if stok else 'standart', **common_theme).in_row("col-md-3")
    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif'), default_value=True, value=stok.aktif if stok else True).in_row("col-md-3 mt-4")

    marka = FormField('marka', FieldType.TEXT, _('Marka'), value=stok.marka if stok else '', **common_theme).in_row("col-md-4")
    model = FormField('model', FieldType.TEXT, _('Model'), value=stok.model if stok else '', **common_theme).in_row("col-md-4")
    mensei = FormField('mensei', FieldType.TEXT, _('Menşei'), value=stok.mensei if stok else 'Türkiye', **common_theme).in_row("col-md-4")

    # ==========================================
    # 2.SEKME: FİYAT & FİNANS
    # ==========================================
    doviz_turu = FormField('doviz_turu', FieldType.SELECT, _('Para Birimi'), options=doviz_opts, value=stok.doviz_turu if stok else 'TL', **common_theme).in_row("col-md-4")
    alis_fiyati = FormField('alis_fiyati', FieldType.CURRENCY, _('Alış Fiyatı'), value=stok.alis_fiyati if stok else 0, currency_symbol='₺', **common_theme).in_row("col-md-4")
    satis_fiyati = FormField('satis_fiyati', FieldType.CURRENCY, _('Satış Fiyatı'), value=stok.satis_fiyati if stok else 0, currency_symbol='₺', **common_theme).in_row("col-md-4")
    
    kdv_kod_id = FormField('kdv_kod_id', FieldType.SELECT, _('KDV Grubu'), options=kdv_opts, required=True, value=stok.kdv_kod_id if stok else '', select2_config={'placeholder': 'Seç...', 'allowClear': True}, **common_theme).in_row("col-md-6")
    muhasebe_kod_id = FormField('muhasebe_kod_id', FieldType.SELECT, _('Muhasebe Grubu'), options=muhasebe_opts, value=stok.muhasebe_kod_id if stok else '', select2_config={'placeholder': 'Seç...', 'allowClear': True}, **common_theme).in_row("col-md-6")

    # ==========================================
    # 3.SEKME: LOJİSTİK & AI & TEDARİK
    # ==========================================
    ai_info = FormField('ai_info', FieldType.HTML, '', value='<div class="alert alert-info py-2 small"><i class="bi bi-robot me-2"></i>AI Analizi: Mevsimsellik ve Tedarikçi verileri stok tahminini %60 iyileştirir.</div>')
    
    tedarikci_id = FormField('tedarikci_id', FieldType.SELECT, _('Ana Tedarikçi'), options=tedarikci_opts, value=stok.tedarikci_id if stok else '', select2_config={'placeholder': 'Tedarikçi Seç...', 'allowClear': True}, **common_theme).in_row("col-md-6")
    mevsimsel_grup = FormField('mevsimsel_grup', FieldType.SELECT, _('Mevsimsellik'), options=mevsim_opts, value=stok.mevsimsel_grup if stok else '', **common_theme).in_row("col-md-6")

    tedarik_suresi = FormField('tedarik_suresi_gun', FieldType.NUMBER, _('Tedarik (Gün)'), value=stok.tedarik_suresi_gun if stok else 3, **common_theme).in_row("col-md-3")
    raf_omru = FormField('raf_omru_gun', FieldType.NUMBER, _('Raf Ömrü (Gün)'), value=stok.raf_omru_gun if stok else 0, **common_theme).in_row("col-md-3")
    kritik_seviye = FormField('kritik_seviye', FieldType.NUMBER, _('Kritik Stok'), value=stok.kritik_seviye if stok else 10, **common_theme).in_row("col-md-3")
    garanti = FormField('garanti_suresi_ay', FieldType.NUMBER, _('Garanti (Ay)'), value=stok.garanti_suresi_ay if stok else 24, **common_theme).in_row("col-md-3")
    
    agirlik = FormField('agirlik_kg', FieldType.NUMBER, _('Ağırlık (Kg)'), value=stok.agirlik_kg if stok else 0, step="0.001", **common_theme).in_row("col-md-6")
    desi = FormField('desi', FieldType.NUMBER, _('Desi'), value=stok.desi if stok else 0, step="0.001", **common_theme).in_row("col-md-6")

    # ==========================================
    # 4.SEKME: DETAYLAR & NLP
    # ==========================================
    resim = FormField('resim', FieldType.IMAGE, _('Ürün Görseli'), value=stok.resim_path if stok else '')
    
    anahtar_kelimeler = FormField('anahtar_kelimeler', FieldType.TEXT, _('Anahtar Kelimeler (Etiketler)'), value=stok.anahtar_kelimeler if stok else '', placeholder="Örn: yazlık, pamuklu, spor", **common_theme)
    aciklama_detay = FormField('aciklama_detay', FieldType.TEXTAREA, _('Detaylı Açıklama (Web/AI)'), value=stok.aciklama_detay if stok else '', html_attributes={'rows': 4}, **common_theme)

    ozel_kod1 = FormField('ozel_kod1', FieldType.TEXT, _('Özel Kod 1'), value=stok.ozel_kod1 if stok else '', **common_theme).in_row("col-md-4")
    ozel_kod2 = FormField('ozel_kod2', FieldType.TEXT, _('Özel Kod 2'), value=stok.ozel_kod2 if stok else '', **common_theme).in_row("col-md-4")

    # --- LAYOUT ---
    tab_genel = [
        layout.create_row(kod, barkod, uretici_kodu),
        ad,
        layout.create_row(kategori_id, birim, tip, aktif),
        layout.create_row(marka, model, mensei)
    ]
    
    tab_finans = [
        layout.create_row(doviz_turu, alis_fiyati, satis_fiyati),
        layout.create_row(kdv_kod_id, muhasebe_kod_id)
    ]
    
    tab_lojistik = [
        ai_info,
        layout.create_row(tedarikci_id, mevsimsel_grup),
        layout.create_row(tedarik_suresi, raf_omru, kritik_seviye, garanti),
        layout.create_row(agirlik, desi)
    ]
    
    tab_detay = [
        anahtar_kelimeler,
        aciklama_detay,
        layout.create_row(ozel_kod1, ozel_kod2),
        layout.create_card("Medya", [resim])
    ]

    tabs = layout.create_tabs("stok_tabs", [
        (Markup('<i class="bi bi-info-circle me-2"></i>Genel'), tab_genel),
        (Markup('<i class="bi bi-currency-dollar me-2"></i>Finans'), tab_finans),
        (Markup('<i class="bi bi-truck me-2"></i>Lojistik & AI'), tab_lojistik),
        (Markup('<i class="bi bi-list-check me-2"></i>Detaylar'), tab_detay)
    ])

    form.set_layout_html(tabs)
    form.add_fields(kod, barkod, uretici_kodu, ad, kategori_id, birim, tip, aktif, marka, model, mensei,
                    doviz_turu, alis_fiyati, satis_fiyati, kdv_kod_id, muhasebe_kod_id,
                    ai_info, tedarikci_id, mevsimsel_grup, tedarik_suresi, raf_omru, kritik_seviye, garanti, agirlik, desi,
                    anahtar_kelimeler, aciklama_detay, ozel_kod1, ozel_kod2, resim)
    return form

# --- MUHASEBE GRUBU FORMU ---
def get_muhasebe_grup_form(target_url, edit_mode=False, instance=None):
    tenant_db = get_tenant_db() # Golden Rule
    
    title = "Muhasebe Grubu Düzenle" if edit_mode else "Yeni Muhasebe Grubu"
    form = Form(name="muhasebe_grup_form", title=title, action=target_url, ajax=True)
    
    # Hesap Planını Firebird'den çek
    hesaplar = tenant_db.query(HesapPlani).filter_by(hesap_tipi='muavin', firma_id=current_user.firma_id).order_by(HesapPlani.kod).all()
    opts = [("", "Seçiniz...")] + [(str(h.id), f"{h.kod} - {h.ad}") for h in hesaplar]
    
    val = lambda k: getattr(instance, k) if instance else ''

    kod = FormField("kod", FieldType.TEXT, "Grup Kodu", required=True, value=val('kod')).in_row("col-md-4")
    ad = FormField("ad", FieldType.TEXT, "Grup Adı", required=True, value=val('ad')).in_row("col-md-8")
    
    f_alis = FormField("alis_hesap_id", FieldType.SELECT, "Alış Hesabı (153)", options=opts, value=val('alis_hesap_id'), select2_config={'allowClear':True}).in_row("col-md-6")
    f_satis = FormField("satis_hesap_id", FieldType.SELECT, "Satış Hesabı (600)", options=opts, value=val('satis_hesap_id'), select2_config={'allowClear':True}).in_row("col-md-6")
    f_alis_iade = FormField("alis_iade_hesap_id", FieldType.SELECT, "Alış İade", options=opts, value=val('alis_iade_hesap_id'), select2_config={'allowClear':True}).in_row("col-md-6")
    f_satis_iade = FormField("satis_iade_hesap_id", FieldType.SELECT, "Satış İade", options=opts, value=val('satis_iade_hesap_id'), select2_config={'allowClear':True}).in_row("col-md-6")
    
    aciklama = FormField("aciklama", FieldType.TEXTAREA, "Açıklama", value=val('aciklama'))
    aktif = FormField("aktif", FieldType.SWITCH, "Aktif", default_value=True, value=val('aktif'))

    form.add_fields(kod, ad, f_alis, f_satis, f_alis_iade, f_satis_iade, aciklama, aktif)
    
    layout = FormLayout()
    layout.add_row(kod, ad)
    layout.add_fieldset("Ana Hesaplar", [layout.create_row(f_alis, f_satis)])
    layout.add_fieldset("İade Hesapları", [layout.create_row(f_alis_iade, f_satis_iade)])
    layout.add_row(aciklama)
    layout.add_row(aktif)
    
    form.set_layout_html(layout.render())
    return form

# --- KDV GRUBU FORMU ---
def get_kdv_grup_form(target_url, edit_mode=False, instance=None):
    tenant_db = get_tenant_db() # Golden Rule
    
    title = "KDV Grubu Düzenle" if edit_mode else "Yeni KDV Grubu"
    form = Form(name="kdv_grup_form", title=title, action=target_url, ajax=True)
    
    hesaplar = tenant_db.query(HesapPlani).filter_by(hesap_tipi='muavin', firma_id=current_user.firma_id).order_by(HesapPlani.kod).all()
    opts = [("", "Seçiniz...")] + [(str(h.id), f"{h.kod} - {h.ad}") for h in hesaplar]
    
    val = lambda k: getattr(instance, k) if instance else ''

    kod = FormField("kod", FieldType.TEXT, "Grup Kodu", required=True, value=val('kod'), placeholder="Örn: KDV_20").in_row("col-md-4")
    ad = FormField("ad", FieldType.TEXT, "Grup Adı", required=True, value=val('ad'), placeholder="Örn: Genel %20").in_row("col-md-8")
    
    alis_oran = FormField("alis_kdv_orani", FieldType.NUMBER, "Alış KDV (%)", required=True, value=val('alis_kdv_orani') or 20).in_row("col-md-6")
    satis_oran = FormField("satis_kdv_orani", FieldType.NUMBER, "Satış KDV (%)", required=True, value=val('satis_kdv_orani') or 20).in_row("col-md-6")

    alis_hesap = FormField(
        "alis_kdv_hesap_id", 
        FieldType.SELECT, 
        "Alış KDV Hesabı (191)", 
        options=opts, 
        value=val('alis_kdv_hesap_id'), 
        select2_config={'allowClear': True, 'placeholder': 'Hesap Seç...'}
    ).in_row("col-md-6")

    satis_hesap = FormField(
        "satis_kdv_hesap_id", 
        FieldType.SELECT, 
        "Satış KDV Hesabı (391)", 
        options=opts, 
        value=val('satis_kdv_hesap_id'), 
        select2_config={'allowClear': True, 'placeholder': 'Hesap Seç...'}
    ).in_row("col-md-6")

    form.add_fields(kod, ad, alis_oran, satis_oran, alis_hesap, satis_hesap)
    
    layout = FormLayout()
    layout.add_row(kod, ad)
    layout.add_row(alis_oran, satis_oran)
    layout.add_html('<hr class="my-3 text-muted"> <h6 class="text-primary"><i class="bi bi-calculator me-2"></i>Muhasebe Entegrasyonu</h6>')
    layout.add_row(alis_hesap, satis_hesap)
    
    form.set_layout_html(layout.render())
    return form

# --- AI AYARLARI FORMU ---
def create_ai_settings_form():
    tenant_db = get_tenant_db() # Golden Rule
    
    action_url = "/stok/ayarlar/ai-guncelle"
    form = Form(name="ai_settings_form", title="AI Parametreleri", action=action_url, method="POST", submit_text=_("Ayarları Kaydet"), ajax=True)
    layout = FormLayout()
    
    if tenant_db:
        ayarlar = tenant_db.query(AIRaporAyarlari).filter_by(firma_id=current_user.firma_id).all()
        
        rows = []
        for ayar in ayarlar:
            field = FormField(
                name=ayar.anahtar, 
                field_type=FieldType.NUMBER, 
                label=ayar.aciklama or ayar.anahtar,
                value=ayar.deger,
                required=True
            ).in_row("col-md-6")
            
            rows.append(field)
            form.add_field(field)
        
        for i in range(0, len(rows), 2):
            row_items = rows[i:i+2]
            layout.add_row(*row_items)
            
    form.set_layout_html(layout.render())
    return form

def create_paket_icerik_form(ana_stok_id):
    tenant_db = get_tenant_db() # Golden Rule
    
    # Not: Model nesnesini tenant_db'den çekiyoruz
    ana_stok = tenant_db.get(StokKart, ana_stok_id)
    
    action_url = f"/stok/paket-icerik/{ana_stok_id}"
    
    form = Form(
        name="paket_form", 
        title=f"{ana_stok.ad} - Paket İçeriği Tanımlama", 
        action=action_url, 
        method="POST", 
        submit_text=_("İçeriği Kaydet"), 
        ajax=True
    )
    layout = FormLayout()

    # Filtreleme Tenant DB üzerinden
    urunler = tenant_db.query(StokKart).filter(
        StokKart.firma_id == current_user.firma_id,
        StokKart.id != ana_stok_id, 
        StokKart.aktif == True
    ).order_by(StokKart.ad).all()
    
    urun_opts = [("", "Ürün Seçiniz...")] + [(u.id, f"{u.ad} ({u.kod})") for u in urunler]

    mevcut_icerik = []
    if ana_stok.paket_icerigi:
        for item in ana_stok.paket_icerigi:
            mevcut_icerik.append({
                'alt_stok_id': item.alt_stok_id,
                'miktar': float(item.miktar)
            })

    detaylar = FormField('bilesenler', FieldType.MASTER_DETAIL, _('Paket Bileşenleri'), required=True,
                         html_attributes={'id': 'detaylar'}, value=mevcut_icerik)
    detaylar.columns = [
        FormField('alt_stok_id', FieldType.SELECT, 'Ürün / Hizmet', 
                  options=urun_opts, required=True, 
                  select2_config={'placeholder': 'Seçiniz'}, 
                  html_attributes={'style': 'width: 250px;', 'data-js': 'stok-select'}), 
        
        FormField('miktar', FieldType.NUMBER, 'Miktar', required=True, default_value=1, 
                  html_attributes={'class': 'text-end', 'style': 'width: 80px;', 'data-js': 'miktar-input', 'data-calc': 'qty'}),
    ]
    
    layout.add_alert("Bilgi", f"<b>{ana_stok.ad}</b> satıldığında, stoktan düşecek ürünleri aşağıda tanımlayınız.", "info", "bi-info-circle")
    layout.add_row(detaylar)
    
    form.set_layout_html(layout.render())
    form.add_fields(detaylar)
    return form