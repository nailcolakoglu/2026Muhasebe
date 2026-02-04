from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.enums import BankaHesapTuru, ParaBirimi, TurkiyeBankalari
from app.modules.sube.models import Sube
from app.modules.banka.models import BankaHesap
from app.modules.muhasebe.utils import get_muhasebe_hesaplari
from wtforms import StringField, DecimalField
from app.modules.cari.models import CariHesap
from app.modules.muhasebe.models import HesapPlani

def create_banka_form(banka=None):
    is_edit = banka is not None
    action_url = f"/banka/duzenle/{banka.id}" if is_edit else "/banka/ekle"
    title = _("Banka Hesabı Düzenle") if is_edit else _("Yeni Banka Hesabı")
    
    form = Form(name="banka_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True, show_title=False)
    layout = FormLayout()

    # --- VERİ HAZIRLIĞI ---
    # 1.Şubeler
    subeler = Sube.query.filter_by(firma_id=current_user.firma_id, aktif=True).all()
    sube_opts = [(s.id, f"{s.kod} - {s.ad}") for s in subeler]
   
    # bankalar
    banka_listesi = sorted([(b.value, b.value) for b in TurkiyeBankalari], key=lambda x: x[1])

    # 2.Döviz Listesi (YENİ - ENUM'DAN OTOMATİK)
    # List Comprehension ile Enum'ı döngüye sokuyoruz.
    # Format: (Veritabanına Gidecek Değer, Ekranda Görünecek Değer)
    # p.name = TL, USD (Kod)
    # p.value = TL, USD (Değer) -> İstersen Enum değerlerini "Türk Lirası" yapıp burayı özelleştirebilirsin.
    doviz_opts = [(p.name, p.value) for p in ParaBirimi]

    # 2.Hesap Türleri (Enum'dan)
    tur_opts = [
        (BankaHesapTuru.VADESIZ.value, 'Vadesiz Mevduat'),
        (BankaHesapTuru.VADELI.value, 'Vadeli Mevduat'),
        (BankaHesapTuru.KREDI.value, 'Kredi Hesabı'),
        (BankaHesapTuru.KREDI_KARTI.value, 'Kredi Kartı'),
        (BankaHesapTuru.POS.value, 'POS Hesabı')
    ]

    # 3.Muhasebe Hesapları (Varsa)
    # muhasebe_list = HesapPlani.query.filter(...).all()
    # muhasebe_opts = [(m.id, f"{m.kod} - {m.ad}") for m in muhasebe_list]
    muhasebe_opts = get_muhasebe_hesaplari() # Şimdilik boş, senin yapına göre doldurursun

    # --- ALANLAR ---

    # 1.SEKME: GENEL BİLGİLER
    kod = FormField('kod', FieldType.AUTO_NUMBER, _('Banka Kodu'), required=True, value=banka.kod if banka else '', endpoint='/banka/api/siradaki-no', icon='bi bi-qr-code')
    banka_adi = FormField(
        'banka_adi', 
        FieldType.SELECT, 
        _('Banka Adı'), 
        required=True, 
        options=banka_listesi, # Hazırladığımız liste
        value=banka.banka_adi if banka else '', 
        select2_config={'placeholder': 'Bankayı Seçiniz...', 'search': True} # Arama özelliği çok önemli!
    )    
    ad = FormField('ad', FieldType.TEXT, _('Hesap Tanımı'), required=True, value=banka.ad if banka else '', placeholder="Örn: Merkez TL Hesabı")
    # 1.Hesap Türü Değerini Güvenli Al
    mevcut_hesap_turu = 'vadesiz' # Varsayılan
    if banka and banka.hesap_turu:
        # Eğer Enum nesnesiyse .value ile değerini al, değilse (string ise) direkt al
        if hasattr(banka.hesap_turu, 'value'):
            mevcut_hesap_turu = banka.hesap_turu.value
        else:
            mevcut_hesap_turu = str(banka.hesap_turu)

    hesap_turu = FormField('hesap_turu', FieldType.SELECT, _('Hesap Türü'), 
                           options=tur_opts, required=True, 
                           value=mevcut_hesap_turu) # Değişkeni buraya veriyoruz
    
    sube_id = FormField('sube_id', FieldType.SELECT, _('Bağlı Şube'), options=sube_opts, required=True, value=banka.sube_id if banka else '', select2_config={'placeholder': 'Şube Seçiniz'})

    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif'), value=banka.aktif if banka else True)


    # 2.SEKME: HESAP DETAYLARI
    sube_adi = FormField('sube_adi', FieldType.TEXT, _('Banka Şubesi'), value=banka.sube_adi if banka else '', placeholder="Örn: Kadıköy Şb.")
    hesap_no = FormField('hesap_no', FieldType.TEXT, _('Hesap No'), value=banka.hesap_no if banka else '')
    iban = FormField('iban', FieldType.IBAN, _('IBAN'), value=banka.iban if banka else '')
    
    # Döviz Enumu models.py'den gelebilir veya manuel
    # 2.Döviz Türü Değerini Güvenli Al

    mevcut_doviz = 'TL' # Varsayılan
    if banka and banka.doviz_turu:
        # Enum ise ismini (name) veya değerini al
        if hasattr(banka.doviz_turu, 'name'): 
            mevcut_doviz = banka.doviz_turu.name 
        elif hasattr(banka.doviz_turu, 'value'):
             mevcut_doviz = banka.doviz_turu.value
        else:
            mevcut_doviz = str(banka.doviz_turu)

    doviz_turu = FormField('doviz_turu', FieldType.SELECT, _('Döviz'), 
                           options=doviz_opts, required=True, 
                           value=mevcut_doviz)

    # 3.SEKME: FİNANS & ENTEGRASYON
    kredi_limiti = FormField('kredi_limiti', FieldType.CURRENCY, _('Kredi / Kart Limiti'), value=banka.kredi_limiti if banka else 0)
    hesap_kesim_gunu = FormField('hesap_kesim_gunu', FieldType.NUMBER, _('Hesap Kesim Günü'), value=banka.hesap_kesim_gunu if banka else '', html_attributes={'max': 31, 'min': 1}, placeholder="1-31 arası")
    
    muhasebe_hesap = FormField('muhasebe_hesap_id', FieldType.SELECT, _('Muhasebe Kodu'), options=muhasebe_opts, value=banka.muhasebe_hesap_id if banka else '', select2_config={'placeholder': 'Hesap Seç', 'allowClear': True})
    
    # İletişim
    temsilci_adi = FormField('temsilci_adi', FieldType.TEXT, _('Müşteri Temsilcisi'), value=banka.temsilci_adi if banka else '')
    temsilci_tel = FormField('temsilci_tel', FieldType.TEL, _('Temsilci Tel'), value=banka.temsilci_tel if banka else '')


    # --- LAYOUT (SEKMELİ YAPI) ---
    tabs = layout.create_tabs("banka_tabs", [
        # SEKME 1: Temel Bilgiler
        ('<i class="bi bi-bank me-2"></i>Genel Bilgiler', [
            layout.create_row(kod, aktif), # Kod ve Aktif yan yana
            layout.create_row(banka_adi, ad),
            layout.create_row(hesap_turu, sube_id)
        ]),
        
        # SEKME 2: Banka Detayları
        ('<i class="bi bi-card-list me-2"></i>Hesap Detayları', [
            layout.create_row(sube_adi, doviz_turu),
            layout.create_row(hesap_no, iban),
            layout.create_row(temsilci_adi, temsilci_tel)
        ]),

        # SEKME 3: Finansal & Özel
        ('<i class="bi bi-sliders me-2"></i>Finans & Ayarlar', [
            layout.create_row(kredi_limiti, hesap_kesim_gunu),
            muhasebe_hesap
        ])
    ])

    form.set_layout_html(tabs)
    
    # Tüm alanları ekle
    form.add_fields(kod, banka_adi, ad, hesap_turu, sube_id, aktif, 
                    sube_adi, hesap_no, iban, doviz_turu, temsilci_adi, temsilci_tel,
                    kredi_limiti, hesap_kesim_gunu, muhasebe_hesap)
    
    return form   