# app/modules/cari/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.extensions import get_tenant_db # 👈 Firebird Bağlantısı
# Modelleri Firebird sorgusu için import ediyoruz
from app.modules.lokasyon.models import Sehir, Ilce
from app.modules.muhasebe.models import HesapPlani

def create_cari_form(cari=None):
    is_edit = cari is not None
    action_url = f"/cari/duzenle/{cari.id}" if is_edit else "/cari/ekle"
    title = _("Cari Kart Düzenle") if is_edit else _("Yeni Cari Kart")
    
    form = Form(name="cari_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- VERİ HAZIRLIĞI (FIREBIRD BAĞLANTISI İLE) ---
    tenant_db = get_tenant_db()
    
    sehir_opts = []
    ilce_opts = []
    muhasebe_opts = []
    
    if tenant_db:
        try:
            # 1. Şehirleri Getir
            sehirler = tenant_db.query(Sehir).order_by(Sehir.kod).all()
            sehir_opts = [(s.id, f"{s.kod} - {s.ad}") for s in sehirler]
            
            # 2. İlçeleri Getir (Eğer düzenleme modundaysa ve şehir seçiliyse)
            if cari and cari.sehir_id:
                ilceler = tenant_db.query(Ilce).filter_by(sehir_id=cari.sehir_id).order_by(Ilce.ad).all()
                ilce_opts = [(i.id, i.ad) for i in ilceler]
                
            # 3. Muhasebe Hesaplarını Getir (Sadece Muavin/Alt Hesaplar)
            hesaplar = tenant_db.query(HesapPlani).filter_by(firma_id=1, aktif=True).order_by(HesapPlani.kod).all()
            for h in hesaplar:
                # Hesap tipi kontrolü (model yapısına göre esnek)
                is_muavin = getattr(h, 'hesap_tipi', 'muavin') == 'muavin' or getattr(h, 'tur', 'ALT') == 'ALT'
                if is_muavin:
                    muhasebe_opts.append((h.id, f"{h.kod} - {h.ad}"))
                    
        except Exception as e:
            print(f"Cari Form Veri Hatası: {e}")
            # Hata durumunda boş listelerle devam et, form patlamasın

    # --- 1. KİMLİK BİLGİLERİ ---
    kod = FormField('kod', FieldType.AUTO_NUMBER, _('Cari Kodu'), required=True, value=cari.kod if cari else '', endpoint='/cari/api/siradaki-kod', icon='bi bi-person-badge')
    unvan = FormField('unvan', FieldType.TEXT, _('Ticari Ünvan / Ad Soyad'), required=True, value=cari.unvan if cari else '', text_transform='uppercase', icon='bi bi-building')
    
    # TCKN / VKN (Akıllı Alan)
    vergi_no = FormField('vergi_no', FieldType.TCKN_VKN, _('VKN / TC Kimlik No'), 
                         value=cari.vergi_no if cari else '', 
                         icon='bi bi-card-text',
                         placeholder="10 haneli VKN veya 11 haneli TC giriniz")

    vergi_dairesi = FormField('vergi_dairesi', FieldType.TEXT, _('Vergi Dairesi'), value=cari.vergi_dairesi if cari else '')

    # --- 2. İLETİŞİM ---
    eposta = FormField('eposta', FieldType.EMAIL, _('E-posta'), value=cari.eposta if cari else '')
    telefon = FormField('telefon', FieldType.TEL, _('Telefon'), value=cari.telefon if cari else '')
    
    # Şehir Seçimi
    sehir_id = FormField('sehir_id', FieldType.SELECT, _('Şehir'), 
                         options=sehir_opts, 
                         value=cari.sehir_id if cari else '',
                         select2_config={'placeholder': 'İl Seçiniz', 'search': True})

    # İlçe Seçimi (API Destekli)
    ilce_id = FormField('ilce_id', FieldType.SELECT, _('İlçe'), 
                        options=ilce_opts,
                        value=cari.ilce_id if cari else '',
                        data_source={
                            'url': '/cari/api/get-ilceler',
                            'method': 'GET',
                            'depends_on': 'sehir_id'
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