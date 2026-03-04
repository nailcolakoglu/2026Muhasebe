# app/modules/cari/forms.py (Minimal Fix - Critical Lines Only)

from app.form_builder import Form, FormField, FieldType, FormLayout
from app.form_builder.form_permissions import FieldPermission
from flask import url_for
from flask_babel import gettext as _, lazy_gettext
from flask_login import current_user
from app.extensions import get_tenant_db, cache # 👈 Firebird Bağlantısı
# Modelleri Firebird sorgusu için import ediyoruz
from app.modules.lokasyon.models import Sehir, Ilce
from app.modules.muhasebe.models import HesapPlani

# Cache timeout
CACHE_TIMEOUT = 300

def create_cari_form(cari=None):
    
    # --- VERİ HAZIRLIĞI (FIREBIRD BAĞLANTISI İLE) ---
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash(_('Firebird bağlantısı yok. Lütfen firma seçin.'), 'danger')
        return redirect(url_for('main.index'))
    
    is_edit = cari is not None
    action_url = url_for('cari.duzenle', id=cari.id) if is_edit else url_for('cari.ekle')
    title = _("Cari Kart Düzenle") if is_edit else _("Yeni Cari Kart")

    
    form = Form(name="cari_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)

    layout = FormLayout()

    # ========================================
    # VERİ HAZIRLIĞI (CACHED)
    # ========================================

    # 1. Şehirler (Cached)
    cache_key_sehir = f"cari_form_sehirler:{current_user.firma_id}"
    sehir_opts = cache.get(cache_key_sehir)
    
    if sehir_opts is None:
        sehirler = tenant_db.query(Sehir).order_by(Sehir.kod).all()
        sehir_opts = [(str(s.id), f"{s.kod} - {s.ad}") for s in sehirler]
        cache.set(cache_key_sehir, sehir_opts, timeout=CACHE_TIMEOUT)
    
    # 2. İlçeler (edit modunda)
    ilce_opts = []
    if cari and cari.sehir_id:
        cache_key_ilce = f"ilceler:{cari.sehir_id}"
        ilce_opts = cache.get(cache_key_ilce)
        
        if ilce_opts is None:
            ilceler = tenant_db.query(Ilce).filter_by(
                sehir_id=cari.sehir_id
            ).order_by(Ilce.ad).all()
            ilce_opts = [(str(i.id), i.ad) for i in ilceler]
            cache.set(cache_key_ilce, ilce_opts, timeout=CACHE_TIMEOUT)
    
    # 3. Muhasebe Hesapları (Cached)
    cache_key_hesap = f"cari_form_hesaplar:{current_user.firma_id}"
    muhasebe_opts = cache.get(cache_key_hesap)
    
    if muhasebe_opts is None:
        hesaplar = tenant_db.query(HesapPlani).filter_by(
            firma_id=current_user.firma_id,
            aktif=True
        ).order_by(HesapPlani.kod).all()
        
        muhasebe_opts = []
        for h in hesaplar:
            is_muavin = (
                getattr(h, 'hesap_tipi', 'muavin') == 'muavin' or
                getattr(h, 'tur', 'ALT') == 'ALT'
            )
            if is_muavin:
                muhasebe_opts.append((str(h.id), f"{h.kod} - {h.ad}"))
        
        cache.set(cache_key_hesap, muhasebe_opts, timeout=CACHE_TIMEOUT)
    
    # --- 1. KİMLİK BİLGİLERİ ---
    kod = FormField('kod', FieldType.AUTO_NUMBER, _('Cari Kodu'), 
        required=True, value=cari.kod if cari else '', 
        endpoint='/cari/api/siradaki-kod', icon='bi bi-person-badge')
    unvan = FormField('unvan', FieldType.TEXT, _('Ticari Ünvan / Ad Soyad'), 
        required=True, 
        value=cari.unvan if cari else '', 
        text_transform='uppercase', 
        icon='bi bi-building', 
        permission=FieldPermission(view_roles=['patron'], 
        edit_roles=['patron']))
    
    # TCKN / VKN (Akıllı Alan)
    vergi_no = FormField('vergi_no', FieldType.TCKN_VKN, _('VKN / TC Kimlik No'), 
                         value=cari.vergi_no if cari else '', 
                         icon='bi bi-card-text',
                         placeholder="10 haneli VKN veya 11 haneli TC giriniz")

    vergi_dairesi = FormField('vergi_dairesi', FieldType.TEXT, _('Vergi Dairesi'), value=cari.vergi_dairesi if cari else '')

    # --- 2. İLETİŞİM ---
    #eposta = FormField('eposta', FieldType.EMAIL, _('E-posta'), value=cari.eposta if cari else '')
    # form.py içinde:
    #eposta = FormField('eposta', FieldType.EMAIL, 'E-Posta', value=cari.eposta if cari else '').set_async_validation('/api/check-email', debounce=600)
    eposta = FormField('eposta', FieldType.EMAIL, _('E-posta'), value=cari.eposta if cari else '')\
        .set_async_validation(
            '/api/check-unique', 
            debounce=600, 
            table='cari_hesaplar', 
            field='eposta', 
            exclude_id=str(cari.id) if cari else None # ✨ BÜYÜ BURADA: "Benim ID'mi görmezden gel!"
        )
        
    telefon = FormField('telefon', FieldType.TEL, _('Telefon'), value=cari.telefon if cari else '')
    
    # Şehir Seçimi
    sehir_id = FormField('sehir_id', FieldType.SELECT, _('Şehir'), 
                         options=sehir_opts, 
                         value=str(cari.sehir_id) if cari and cari.sehir_id else '',
                         select2_config={'placeholder': 'İl Seçiniz', 'search': True})

    # İlçe Seçimi (Senin mükemmel data_source motorunla!)
    ilce_id = FormField('ilce_id', FieldType.SELECT, _('İlçe'), 
                        options=ilce_opts,
                        value=str(cari.ilce_id) if cari and cari.ilce_id else '',
                        data_source={
                            'url': '/cari/api/get-ilceler',
                            'depends_on': 'sehir_id',
                            # ✨ YENİ: Backend'deki rotan url'de hangi parametreyi bekliyorsa onu buraya yazıyorsun
                            'param': 'sehir_id' # Örn: /cari/api/get-ilceler?sehir_id=35 olarak istek atar
                        },
                        select2_config={'placeholder': 'İlçe Seçiniz', 'search': True})

    adres = FormField('adres', FieldType.TEXTAREA, _('Adres Detayı'), value=cari.adres if cari else '', html_attributes={'rows': 2})
    konum = FormField('konum', FieldType.GEOLOCATION, _('Konum'), value=cari.konum if cari else '')
   
    # --- 3. FİNANS ---
    alis_muhasebe = FormField(
        'alis_muhasebe_hesap_id', 
        FieldType.SELECT, 
        _('Alış Muhasebe Kodu (320)'), 
        options=muhasebe_opts, 
        value=cari.alis_muhasebe_hesap_id if cari and hasattr(cari, 'alis_muhasebe_hesap_id') else '',
        help_text="Alış faturalarında kullanılacak hesap."
    )

    satis_muhasebe = FormField(
        'satis_muhasebe_hesap_id', 
        FieldType.SELECT, 
        _('Satış Muhasebe Kodu (120)'), 
        options=muhasebe_opts, 
        value=cari.satis_muhasebe_hesap_id if cari and hasattr(cari, 'satis_muhasebe_hesap_id') else '',
        help_text="Satış faturalarında kullanılacak hesap."
    )

    # --- LAYOUT DÜZENLEMESİ ---
    layout.add_row(kod, unvan)
    layout.add_row(vergi_no, vergi_dairesi)
    layout.add_html('<hr class="my-3 text-muted">')
    layout.add_row(eposta, telefon)
    layout.add_row(adres) 
    layout.add_row(sehir_id, ilce_id, konum)
    layout.add_row(alis_muhasebe, satis_muhasebe)
    
    form.set_layout_html(layout.render())
    
    # Tüm alanları forma ekle
    form.add_fields(kod, unvan, vergi_no, vergi_dairesi, eposta, telefon, sehir_id, ilce_id, konum, adres, alis_muhasebe, satis_muhasebe)
    
    return form