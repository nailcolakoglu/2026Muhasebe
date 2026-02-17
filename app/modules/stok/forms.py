# app/modules/stok/forms.py (MySQL + Redis + Babel Complete)

"""
Stok Modülü Form Tanımları
Enterprise Grade - i18n Ready - Tenant DB Compatible
"""

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _, lazy_gettext
from flask_login import current_user
from flask import url_for, flash, redirect, session

from app.modules.sube.models import Sube
from app.modules.stok.models import (
    StokKart, StokMuhasebeGrubu, StokKDVGrubu, StokPaketIcerigi
)
from app.modules.kategori.models import StokKategori
from app.modules.cari.models import CariHesap
from app.modules.muhasebe.models import HesapPlani
from app.models import AIRaporAyarlari
from markupsafe import Markup

from app.extensions import get_tenant_db, cache
import logging

logger = logging.getLogger(__name__)

# Constants
CACHE_TIMEOUT = 300  # 5 dakika


# ========================================
# ANA STOK FORMU (Redis Cached Options)
# ========================================
def create_stok_form(stok=None):
    """
    Ana stok kartı formu oluştur
    
    Args:
        stok: Düzenleme için mevcut StokKart instance
    
    Returns:
        Form instance
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Firebird bağlantısı yok. Lütfen firma seçin.'), 'danger')
        return redirect(url_for('main.index'))
    
    is_edit = stok is not None
    action_url = url_for('stok.duzenle', id=stok.id) if is_edit else url_for('stok.ekle')
    title = _("Stok Kartı Düzenle") if is_edit else _("Yeni Stok Kartı")
    
    form = Form(
        name="stok_form",
        title=title,
        action=action_url,
        method="POST",
        submit_text=_("Kaydet"),
        ajax=True
    )
    
    form_color = "primary"
    form.extra_context = {'card_color': form_color}
    
    layout = FormLayout()
    
    # ========================================
    # SELECT OPTIONS (CACHED)
    # ========================================
    
    # 1. Kategoriler (Cached)
    cache_key_kategori = f"stok_form_kategoriler:{current_user.firma_id}"
    kategori_opts = cache.get(cache_key_kategori)
    
    if kategori_opts is None:
        kategoriler = tenant_db.query(StokKategori).filter_by(
            firma_id=current_user.firma_id
        ).order_by(StokKategori.ad).all()
        kategori_opts = [(str(k.id), k.ad) for k in kategoriler]
        cache.set(cache_key_kategori, kategori_opts, timeout=CACHE_TIMEOUT)
    
    # 2. Muhasebe Grupları (Cached)
    cache_key_muhasebe = f"stok_form_muhasebe:{current_user.firma_id}"
    muhasebe_opts = cache.get(cache_key_muhasebe)
    
    if muhasebe_opts is None:
        muh_gruplar = tenant_db.query(StokMuhasebeGrubu).filter_by(
            firma_id=current_user.firma_id,
            aktif=True
        ).order_by(StokMuhasebeGrubu.kod).all()
        muhasebe_opts = [(str(g.id), f"{g.kod} - {g.ad}") for g in muh_gruplar]
        cache.set(cache_key_muhasebe, muhasebe_opts, timeout=CACHE_TIMEOUT)
    
    # 3. KDV Grupları (Cached)
    cache_key_kdv = f"stok_form_kdv:{current_user.firma_id}"
    kdv_opts = cache.get(cache_key_kdv)
    
    if kdv_opts is None:
        kdv_gruplar = tenant_db.query(StokKDVGrubu).filter_by(
            firma_id=current_user.firma_id
        ).order_by(StokKDVGrubu.kod).all()
        kdv_opts = [
            (str(k.id), f"{k.ad} ({_('Alış')}:%{k.alis_kdv_orani}, {_('Satış')}:%{k.satis_kdv_orani})")
            for k in kdv_gruplar
        ]
        cache.set(cache_key_kdv, kdv_opts, timeout=CACHE_TIMEOUT)
    
    # 4. Tedarikçiler (Cached - İlk 100)
    cache_key_tedarikci = f"stok_form_tedarikci:{current_user.firma_id}"
    tedarikci_opts = cache.get(cache_key_tedarikci)
    
    if tedarikci_opts is None:
        tedarikciler = tenant_db.query(CariHesap).filter_by(
            firma_id=current_user.firma_id,
            aktif=True
        ).order_by(CariHesap.unvan).limit(100).all()
        tedarikci_opts = [("", _("Seçiniz..."))] + [(str(c.id), c.unvan) for c in tedarikciler]
        cache.set(cache_key_tedarikci, tedarikci_opts, timeout=CACHE_TIMEOUT)
    
    # ========================================
    # ENUM OPTIONS (Statik - i18n)
    # ========================================
    birim_opts = [
        ('ADET', _('Adet')),
        ('KG', _('Kg')),
        ('LT', _('Lt')),
        ('MT', _('Metre')),
        ('M2', _('M²')),
        ('M3', _('M³')),
        ('KUTU', _('Kutu')),
        ('KOLI', _('Koli')),
        ('PALET', _('Palet'))
    ]
    
    doviz_opts = [
        ('TL', 'TL'),
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP')
    ]
    
    tip_opts = [
        ('STANDART', _('Standart Ürün')),
        ('HIZMET', _('Hizmet')),
        ('PAKET', _('Paket')),
        ('MAMUL', _('Mamul')),
        ('YARI_MAMUL', _('Yarı Mamul')),
        ('HAMMADDE', _('Hammadde'))
    ]
    
    mevsim_opts = [
        ('', _('Yok')),
        ('KIS', _('Kış Sezonu')),
        ('YAZ', _('Yaz Sezonu')),
        ('ILKBAHAR', _('İlkbahar')),
        ('SONBAHAR', _('Sonbahar')),
        ('OKUL', _('Okul Sezonu')),
        ('YILBASI', _('Yılbaşı'))
    ]
    
    # ========================================
    # THEME (Form stil)
    # ========================================
    common_theme = {
        'colorfocus': '#e3f2fd',
        'textfocus': '#1565c0',
        'borderfocus': '#2196f3'
    }
    
    # ========================================
    # SEKME 1: TEMEL BİLGİLER
    # ========================================
    kod = FormField(
        'kod',
        FieldType.AUTO_NUMBER,
        _('Stok Kodu'),
        required=True,
        value=stok.kod if stok else '',
        endpoint='/stok/api/siradaki-kod',
        icon='bi bi-qr-code',
        **common_theme
    ).in_row("col-md-4")
    
    barkod = FormField(
        'barkod',
        FieldType.TEXT,
        _('Barkod'),
        value=stok.barkod if stok else '',
        icon='bi bi-upc-scan',
        placeholder="8690000000000",
        **common_theme
    ).in_row("col-md-4")
    
    uretici_kodu = FormField(
        'uretici_kodu',
        FieldType.TEXT,
        _('Üretici Kodu (MPN)'),
        value=stok.uretici_kodu if stok else '',
        placeholder=_("Fabrika Kodu"),
        **common_theme
    ).in_row("col-md-4")
    
    ad = FormField(
        'ad',
        FieldType.TEXT,
        _('Stok Adı'),
        required=True,
        value=stok.ad if stok else '',
        icon='bi bi-box-seam',
        text_transform='uppercase',
        **common_theme
    )
    
    kategori_id = FormField(
        'kategori_id',
        FieldType.SELECT,
        _('Kategori'),
        options=kategori_opts,
        required=True,
        value=str(stok.kategori_id) if stok and stok.kategori_id else '',
        select2_config={
            'placeholder': _('Kategori Seçiniz'),
            'allowClear': True
        },
        **common_theme
    ).in_row("col-md-3")
    
    birim = FormField(
        'birim',
        FieldType.SELECT,
        _('Birim'),
        options=birim_opts,
        required=True,
        value=stok.birim if stok else 'ADET',
        **common_theme
    ).in_row("col-md-3")
    
    tip = FormField(
        'tip',
        FieldType.SELECT,
        _('Stok Tipi'),
        options=tip_opts,
        required=True,
        value=stok.tip if stok else 'STANDART',
        **common_theme
    ).in_row("col-md-3")
    
    aktif = FormField(
        'aktif',
        FieldType.SWITCH,
        _('Aktif'),
        default_value=True,
        value=stok.aktif if stok else True
    ).in_row("col-md-3 mt-4")
    
    marka = FormField(
        'marka',
        FieldType.TEXT,
        _('Marka'),
        value=stok.marka if stok else '',
        **common_theme
    ).in_row("col-md-4")
    
    model = FormField(
        'model',
        FieldType.TEXT,
        _('Model'),
        value=stok.model if stok else '',
        **common_theme
    ).in_row("col-md-4")
    
    mensei = FormField(
        'mensei',
        FieldType.TEXT,
        _('Menşei'),
        value=stok.mensei if stok else 'Türkiye',
        **common_theme
    ).in_row("col-md-4")
    
    # ========================================
    # SEKME 2: FİYAT & FİNANS
    # ========================================
    doviz_turu = FormField(
        'doviz_turu',
        FieldType.SELECT,
        _('Para Birimi'),
        options=doviz_opts,
        value=stok.doviz_turu if stok else 'TL',
        **common_theme
    ).in_row("col-md-4")
    
    alis_fiyati = FormField(
        'alis_fiyati',
        FieldType.CURRENCY,
        _('Alış Fiyatı'),
        value=float(stok.alis_fiyati) if stok else 0,
        currency_symbol='₺',
        **common_theme
    ).in_row("col-md-4")
    
    satis_fiyati = FormField(
        'satis_fiyati',
        FieldType.CURRENCY,
        _('Satış Fiyatı'),
        value=float(stok.satis_fiyati) if stok else 0,
        currency_symbol='₺',
        **common_theme
    ).in_row("col-md-4")
    
    # Kar marjı gösterimi (edit modunda)
    if stok and stok.satis_fiyati > 0:
        kar_marji = float(stok.kar_marji)
        kar_renk = 'success' if kar_marji > 20 else 'warning' if kar_marji > 10 else 'danger'
        
        kar_bilgi = FormField(
            'kar_info',
            FieldType.HTML,
            '',
            value=f'''
            <div class="alert alert-{kar_renk} py-2 small mb-3">
                <i class="bi bi-graph-up-arrow me-2"></i>
                {_("Kar Marjı")}: <strong>%{kar_marji:.2f}</strong>
            </div>
            '''
        )
    else:
        kar_bilgi = None
    
    kdv_kod_id = FormField(
        'kdv_kod_id',
        FieldType.SELECT,
        _('KDV Grubu'),
        options=kdv_opts,
        required=True,
        value=str(stok.kdv_kod_id) if stok and stok.kdv_kod_id else '',
        select2_config={
            'placeholder': _('KDV Seç...'),
            'allowClear': True
        },
        **common_theme
    ).in_row("col-md-6")
    
    muhasebe_kod_id = FormField(
        'muhasebe_kod_id',
        FieldType.SELECT,
        _('Muhasebe Grubu'),
        options=muhasebe_opts,
        value=str(stok.muhasebe_kod_id) if stok and stok.muhasebe_kod_id else '',
        select2_config={
            'placeholder': _('Muhasebe Seç...'),
            'allowClear': True
        },
        **common_theme
    ).in_row("col-md-6")
    
    # ========================================
    # SEKME 3: LOJİSTİK & AI
    # ========================================
    ai_info = FormField(
        'ai_info',
        FieldType.HTML,
        '',
        value=f'''
        <div class="alert alert-info py-2 small mb-3">
            <i class="bi bi-robot me-2"></i>
            {_("AI Analizi: Mevsimsellik ve Tedarikçi verileri stok tahminini %60 iyileştirir.")}
        </div>
        '''
    )
    
    tedarikci_id = FormField(
        'tedarikci_id',
        FieldType.SELECT,
        _('Ana Tedarikçi'),
        options=tedarikci_opts,
        value=str(stok.tedarikci_id) if stok and stok.tedarikci_id else '',
        select2_config={
            'placeholder': _('Tedarikçi Seç...'),
            'allowClear': True,
            'ajax': {
                'url': '/cari/api/get-cariler',
                'dataType': 'json',
                'delay': 250
            }
        },
        **common_theme
    ).in_row("col-md-6")
    
    mevsimsel_grup = FormField(
        'mevsimsel_grup',
        FieldType.SELECT,
        _('Mevsimsellik'),
        options=mevsim_opts,
        value=stok.mevsimsel_grup if stok else '',
        **common_theme
    ).in_row("col-md-6")
    
    tedarik_suresi = FormField(
        'tedarik_suresi_gun',
        FieldType.NUMBER,
        _('Tedarik Süresi (Gün)'),
        value=stok.tedarik_suresi_gun if stok else 3,
        help_text=_("Sipariş verildikten kaç gün sonra gelir?"),
        **common_theme
    ).in_row("col-md-3")
    
    raf_omru = FormField(
        'raf_omru_gun',
        FieldType.NUMBER,
        _('Raf Ömrü (Gün)'),
        value=stok.raf_omru_gun if stok else 0,
        help_text=_("Gıda/İlaç için"),
        **common_theme
    ).in_row("col-md-3")
    
    kritik_seviye = FormField(
        'kritik_seviye',
        FieldType.NUMBER,
        _('Kritik Stok Seviyesi'),
        value=float(stok.kritik_seviye) if stok else 10,
        help_text=_("Stok bu seviyenin altına düşünce uyarı verilir"),
        **common_theme
    ).in_row("col-md-3")
    
    garanti = FormField(
        'garanti_suresi_ay',
        FieldType.NUMBER,
        _('Garanti Süresi (Ay)'),
        value=stok.garanti_suresi_ay if stok else 24,
        **common_theme
    ).in_row("col-md-3")
    
    agirlik = FormField(
        'agirlik_kg',
        FieldType.NUMBER,
        _('Ağırlık (Kg)'),
        value=float(stok.agirlik_kg) if stok else 0,
        step="0.001",
        help_text=_("Kargo maliyeti hesabı için"),
        **common_theme
    ).in_row("col-md-6")
    
    desi = FormField(
        'desi',
        FieldType.NUMBER,
        _('Desi'),
        value=float(stok.desi) if stok else 0,
        step="0.001",
        **common_theme
    ).in_row("col-md-6")
    
    # ========================================
    # SEKME 4: DETAYLAR & NLP
    # ========================================
    resim = FormField(
        'resim',
        FieldType.IMAGE,
        _('Ürün Görseli'),
        value=stok.resim_path if stok else ''
    )
    
    anahtar_kelimeler = FormField(
        'anahtar_kelimeler',
        FieldType.TEXT,
        _('Anahtar Kelimeler (Etiketler)'),
        value=stok.anahtar_kelimeler if stok else '',
        placeholder=_("Örn: yazlık, pamuklu, spor"),
        help_text=_("Virgülle ayırarak yazınız. Arama ve AI için kullanılır."),
        **common_theme
    )
    
    aciklama_detay = FormField(
        'aciklama_detay',
        FieldType.TEXTAREA,
        _('Detaylı Açıklama (Web/AI)'),
        value=stok.aciklama_detay if stok else '',
        html_attributes={'rows': 4},
        help_text=_("SEO ve AI analizi için detaylı açıklama"),
        **common_theme
    )
    
    ozel_kod1 = FormField(
        'ozel_kod1',
        FieldType.TEXT,
        _('Özel Kod 1'),
        value=stok.ozel_kod1 if stok else '',
        **common_theme
    ).in_row("col-md-4")
    
    ozel_kod2 = FormField(
        'ozel_kod2',
        FieldType.TEXT,
        _('Özel Kod 2'),
        value=stok.ozel_kod2 if stok else '',
        **common_theme
    ).in_row("col-md-4")
    
    # ========================================
    # LAYOUT OLUŞTURMA (SEKME YAPISI)
    # ========================================
    tab_genel = [
        layout.create_row(kod, barkod, uretici_kodu),
        ad,
        layout.create_row(kategori_id, birim, tip, aktif),
        layout.create_row(marka, model, mensei)
    ]
    
    tab_finans = [
        kar_bilgi if kar_bilgi else layout.create_html(''),
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
        layout.create_card(_("Medya"), [resim])
    ]
    
    tabs = layout.create_tabs("stok_tabs", [
        (Markup(f'<i class="bi bi-info-circle me-2"></i>{_("Genel")}'), tab_genel),
        (Markup(f'<i class="bi bi-currency-dollar me-2"></i>{_("Finans")}'), tab_finans),
        (Markup(f'<i class="bi bi-truck me-2"></i>{_("Lojistik & AI")}'), tab_lojistik),
        (Markup(f'<i class="bi bi-list-check me-2"></i>{_("Detaylar")}'), tab_detay)
    ])
    
    form.set_layout_html(tabs)
    
    # Tüm alanları forma ekle
    form.add_fields(
        kod, barkod, uretici_kodu, ad, kategori_id, birim, tip, aktif,
        marka, model, mensei,
        doviz_turu, alis_fiyati, satis_fiyati, kdv_kod_id, muhasebe_kod_id,
        ai_info, tedarikci_id, mevsimsel_grup, tedarik_suresi, raf_omru,
        kritik_seviye, garanti, agirlik, desi,
        anahtar_kelimeler, aciklama_detay, ozel_kod1, ozel_kod2, resim
    )
    
    if kar_bilgi:
        form.add_field(kar_bilgi)
    
    return form


# ========================================
# MUHASEBE GRUBU FORMU
# ========================================
def get_muhasebe_grup_form(target_url, edit_mode=False, instance=None):
    """
    Muhasebe grubu formu
    
    Args:
        target_url: Form action URL
        edit_mode: Düzenleme modu mu?
        instance: StokMuhasebeGrubu instance (edit için)
    
    Returns:
        Form instance
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    title = _("Muhasebe Grubu Düzenle") if edit_mode else _("Yeni Muhasebe Grubu")
    form = Form(name="muhasebe_grup_form", title=title, action=target_url, ajax=True)
    
    # Hesap Planı (Cached)
    cache_key = f"muhasebe_hesaplar:{current_user.firma_id}"
    hesap_opts = cache.get(cache_key)
    
    if hesap_opts is None:
        hesaplar = tenant_db.query(HesapPlani).filter_by(
            hesap_tipi='muavin',
            firma_id=current_user.firma_id
        ).order_by(HesapPlani.kod).all()
        hesap_opts = [("", _("Seçiniz..."))] + [
            (str(h.id), f"{h.kod} - {h.ad}") for h in hesaplar
        ]
        cache.set(cache_key, hesap_opts, timeout=CACHE_TIMEOUT)
    
    val = lambda k: getattr(instance, k) if instance else ''
    
    layout = FormLayout()
    
    kod = FormField(
        "kod",
        FieldType.TEXT,
        _("Grup Kodu"),
        required=True,
        value=val('kod')
    ).in_row("col-md-4")
    
    ad = FormField(
        "ad",
        FieldType.TEXT,
        _("Grup Adı"),
        required=True,
        value=val('ad')
    ).in_row("col-md-8")
    
    f_alis = FormField(
        "alis_hesap_id",
        FieldType.SELECT,
        _("Alış Hesabı (153)"),
        options=hesap_opts,
        value=str(val('alis_hesap_id')) if val('alis_hesap_id') else '',
        select2_config={'allowClear': True}
    ).in_row("col-md-6")
    
    f_satis = FormField(
        "satis_hesap_id",
        FieldType.SELECT,
        _("Satış Hesabı (600)"),
        options=hesap_opts,
        value=str(val('satis_hesap_id')) if val('satis_hesap_id') else '',
        select2_config={'allowClear': True}
    ).in_row("col-md-6")
    
    f_alis_iade = FormField(
        "alis_iade_hesap_id",
        FieldType.SELECT,
        _("Alış İade Hesabı"),
        options=hesap_opts,
        value=str(val('alis_iade_hesap_id')) if val('alis_iade_hesap_id') else '',
        select2_config={'allowClear': True}
    ).in_row("col-md-6")
    
    f_satis_iade = FormField(
        "satis_iade_hesap_id",
        FieldType.SELECT,
        _("Satış İade Hesabı (610)"),
        options=hesap_opts,
        value=str(val('satis_iade_hesap_id')) if val('satis_iade_hesap_id') else '',
        select2_config={'allowClear': True}
    ).in_row("col-md-6")
    
    f_smm = FormField(
        "satilan_mal_maliyeti_hesap_id",
        FieldType.SELECT,
        _("Satılan Malın Maliyeti (621)"),
        options=hesap_opts,
        value=str(val('satilan_mal_maliyeti_hesap_id')) if val('satilan_mal_maliyeti_hesap_id') else '',
        select2_config={'allowClear': True}
    ).in_row("col-md-12")
    
    aciklama = FormField(
        "aciklama",
        FieldType.TEXTAREA,
        _("Açıklama"),
        value=val('aciklama')
    )
    
    aktif = FormField(
        "aktif",
        FieldType.SWITCH,
        _("Aktif"),
        default_value=True,
        value=val('aktif')
    )
    
    form.add_fields(kod, ad, f_alis, f_satis, f_alis_iade, f_satis_iade, f_smm, aciklama, aktif)
    
    layout.add_row(kod, ad)
    layout.add_fieldset(_("Ana Hesaplar"), [layout.create_row(f_alis, f_satis)])
    layout.add_fieldset(_("İade Hesapları"), [layout.create_row(f_alis_iade, f_satis_iade)])
    layout.add_fieldset(_("Maliyet Hesabı"), [f_smm])
    layout.add_row(aciklama)
    layout.add_row(aktif)
    
    form.set_layout_html(layout.render())
    return form


# ========================================
# KDV GRUBU FORMU
# ========================================
def get_kdv_grup_form(target_url, edit_mode=False, instance=None):
    """
    KDV grubu formu
    
    Args:
        target_url: Form action URL
        edit_mode: Düzenleme modu mu?
        instance: StokKDVGrubu instance (edit için)
    
    Returns:
        Form instance
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    title = _("KDV Grubu Düzenle") if edit_mode else _("Yeni KDV Grubu")
    form = Form(name="kdv_grup_form", title=title, action=target_url, ajax=True)
    
    # Hesap Planı (Cached - Muhasebe form ile aynı)
    cache_key = f"muhasebe_hesaplar:{current_user.firma_id}"
    hesap_opts = cache.get(cache_key)
    
    if hesap_opts is None:
        hesaplar = tenant_db.query(HesapPlani).filter_by(
            hesap_tipi='muavin',
            firma_id=current_user.firma_id
        ).order_by(HesapPlani.kod).all()
        hesap_opts = [("", _("Seçiniz..."))] + [
            (str(h.id), f"{h.kod} - {h.ad}") for h in hesaplar
        ]
        cache.set(cache_key, hesap_opts, timeout=CACHE_TIMEOUT)
    
    val = lambda k: getattr(instance, k) if instance else ''
    
    layout = FormLayout()
    
    kod = FormField(
        "kod",
        FieldType.TEXT,
        _("Grup Kodu"),
        required=True,
        value=val('kod'),
        placeholder=_("Örn: KDV_20")
    ).in_row("col-md-4")
    
    ad = FormField(
        "ad",
        FieldType.TEXT,
        _("Grup Adı"),
        required=True,
        value=val('ad'),
        placeholder=_("Örn: Genel %20")
    ).in_row("col-md-8")
    
    alis_oran = FormField(
        "alis_kdv_orani",
        FieldType.NUMBER,
        _("Alış KDV (%)"),
        required=True,
        value=val('alis_kdv_orani') or 20
    ).in_row("col-md-6")
    
    satis_oran = FormField(
        "satis_kdv_orani",
        FieldType.NUMBER,
        _("Satış KDV (%)"),
        required=True,
        value=val('satis_kdv_orani') or 20
    ).in_row("col-md-6")
    
    alis_hesap = FormField(
        "alis_kdv_hesap_id",
        FieldType.SELECT,
        _("Alış KDV Hesabı (191)"),
        options=hesap_opts,
        value=str(val('alis_kdv_hesap_id')) if val('alis_kdv_hesap_id') else '',
        select2_config={'allowClear': True, 'placeholder': _('Hesap Seç...')}
    ).in_row("col-md-6")
    
    satis_hesap = FormField(
        "satis_kdv_hesap_id",
        FieldType.SELECT,
        _("Satış KDV Hesabı (391)"),
        options=hesap_opts,
        value=str(val('satis_kdv_hesap_id')) if val('satis_kdv_hesap_id') else '',
        select2_config={'allowClear': True, 'placeholder': _('Hesap Seç...')}
    ).in_row("col-md-6")
    
    form.add_fields(kod, ad, alis_oran, satis_oran, alis_hesap, satis_hesap)
    
    layout.add_row(kod, ad)
    layout.add_row(alis_oran, satis_oran)
    layout.add_html(f'<hr class="my-3 text-muted">')
    layout.add_html(f'<h6 class="text-primary"><i class="bi bi-calculator me-2"></i>{_("Muhasebe Entegrasyonu")}</h6>')
    layout.add_row(alis_hesap, satis_hesap)
    
    form.set_layout_html(layout.render())
    return form


# ========================================
# AI AYARLARI FORMU
# ========================================
def create_ai_settings_form():
    """
    AI parametreleri formu
    
    Returns:
        Form instance
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    action_url = url_for('stok.ai_ayarlar_guncelle')
    form = Form(
        name="ai_settings_form",
        title=_("AI Parametreleri"),
        action=action_url,
        method="POST",
        submit_text=_("Ayarları Kaydet"),
        ajax=True
    )
    
    layout = FormLayout()
    
    # AI ayarlarını çek
    ayarlar = tenant_db.query(AIRaporAyarlari).filter_by(
        firma_id=current_user.firma_id
    ).all()
    
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


# ========================================
# PAKET İÇERİK FORMU
# ========================================
def create_paket_icerik_form(ana_stok_id):
    """
    Paket ürün içeriği formu
    
    Args:
        ana_stok_id: Ana stok (paket) ID
    
    Returns:
        Form instance
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    # Ana stoğu getir
    ana_stok = tenant_db.query(StokKart).get(ana_stok_id)
    
    if not ana_stok:
        flash(_('Stok bulunamadı'), 'danger')
        return redirect(url_for('stok.index'))
    
    action_url = url_for('stok.paket_icerik', id=ana_stok_id)
    
    form = Form(
        name="paket_form",
        title=f"{ana_stok.ad} - {_('Paket İçeriği Tanımlama')}",
        action=action_url,
        method="POST",
        submit_text=_("İçeriği Kaydet"),
        ajax=True
    )
    
    layout = FormLayout()
    
    # Ürünler (Ana stok hariç)
    urunler = tenant_db.query(StokKart).filter(
        StokKart.firma_id == current_user.firma_id,
        StokKart.id != ana_stok_id,
        StokKart.aktif == True,
        StokKart.deleted_at.is_(None)
    ).order_by(StokKart.ad).limit(200).all()
    
    urun_opts = [("", _("Ürün Seçiniz..."))] + [
        (str(u.id), f"{u.ad} ({u.kod})") for u in urunler
    ]
    
    # Mevcut içerik
    mevcut_icerik = []
    if ana_stok.paket_icerigi:
        for item in ana_stok.paket_icerigi:
            mevcut_icerik.append({
                'alt_stok_id': str(item.alt_stok_id),
                'miktar': float(item.miktar)
            })
    
    # Master-Detail Field
    detaylar = FormField(
        'bilesenler',
        FieldType.MASTER_DETAIL,
        _('Paket Bileşenleri'),
        required=True,
        html_attributes={'id': 'detaylar'},
        value=mevcut_icerik
    )
    
    detaylar.columns = [
        FormField(
            'alt_stok_id',
            FieldType.SELECT,
            _('Ürün / Hizmet'),
            options=urun_opts,
            required=True,
            select2_config={'placeholder': _('Seçiniz')},
            html_attributes={
                'style': 'width: 400px;',
                'data-js': 'stok-select'
            }
        ),
        
        FormField(
            'miktar',
            FieldType.NUMBER,
            _('Miktar'),
            required=True,
            default_value=1,
            html_attributes={
                'class': 'text-end',
                'style': 'width: 120px;',
                'data-js': 'miktar-input',
                'data-calc': 'qty'
            }
        ),
    ]
    
    layout.add_alert(
        _("Bilgi"),
        f"<b>{ana_stok.ad}</b> {_('satıldığında, stoktan düşecek ürünleri aşağıda tanımlayınız.')}",
        "info",
        "bi-info-circle"
    )
    layout.add_row(detaylar)
    
    form.set_layout_html(layout.render())
    form.add_fields(detaylar)
    
    return form