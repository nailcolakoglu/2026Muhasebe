# app/modules/kasa_hareket/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.kasa.models import Kasa
from app.modules.cari.models import CariHesap
from app.modules.sube.models import Sube
from app.modules.banka.models import BankaHesap
from app.enums import BankaIslemTuru

def create_kasa_hareket_form(hareket=None):
    is_edit = hareket is not None
    action_url = f"/kasa-hareket/duzenle/{hareket.id}" if is_edit else "/kasa-hareket/ekle"
    title = _("İşlem Düzenle") if is_edit else _("Yeni Kasa İşlemi")
    
    form = Form(name="kasa_hareket_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- OPTIONS ---
    kasalar = Kasa.query.filter_by(firma_id=current_user.firma_id, aktif=True).all()
    kasa_opts = [(k.id, f"{k.ad} ({getattr(k.doviz_turu, 'name', str(k.doviz_turu))})") for k in kasalar]

    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).limit(100).all()
    cari_opts = [(c.id, f"{c.unvan}") for c in cariler]

    bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()
    banka_opts = [(b.id, f"{b.banka_adi} - {b.ad}") for b in bankalar]

    # --- VARSAYILAN DEĞERLER (GÜVENLİ) ---
    def safe_val(val, default=""):
        # Eğer val bir Enum ise .value döndür, string ise kendisini döndür
        return getattr(val, 'value', val) if val else default

    # Varsayılan Yön ve Taraf Belirleme
    mevcut_yon = 'giris'
    mevcut_taraf = 'cari'
    islem_turu_val = BankaIslemTuru.TAHSILAT.value

    if hareket:
        # Enum değerini güvenli al
        islem_turu_val = safe_val(hareket.islem_turu, BankaIslemTuru.TAHSILAT.value)
        
        cikis_turleri = [
            BankaIslemTuru.TEDIYE.value, 
            BankaIslemTuru.VIRMAN_CIKIS.value
        ]
        
        if islem_turu_val in cikis_turleri:
            mevcut_yon = 'cikis'
        
        if hareket.karsi_kasa_id: mevcut_taraf = 'kasa'
        elif hareket.banka_id: mevcut_taraf = 'banka'

    # --- ALANLAR ---
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Makbuz No'), required=True, value=hareket.belge_no if hareket else '', endpoint='/kasa-hareket/api/siradaki-no')
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=hareket.tarih if hareket else '')
    
    kasa_id = FormField('kasa_id', FieldType.SELECT, _('İşlem Gören Kasa'), options=kasa_opts, required=True, value=hareket.kasa_id if hareket else '')

    # Yön Seçimi
    islem_yonu = FormField('islem_yonu', FieldType.RADIO, _('İşlem Yönü'), 
                           options=[('giris', 'Tahsilat / Giriş'), ('cikis', 'Tediye / Çıkış')], 
                           value=mevcut_yon, html_attributes={'class': 'radio-card-group'})
    
    # Karşı Taraf Seçimi
    karsi_hesap_turu = FormField('karsi_hesap_turu', FieldType.RADIO, _('Karşı Hesap Türü'),
                                 options=[('cari', 'Cari Hesap'), ('banka', 'Banka'), ('kasa', 'Kasa (Virman)')],
                                 value=mevcut_taraf, html_attributes={'class': 'radio-card-group btn_color:info'})

    # Dinamik Alanlar
    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=cari_opts, value=hareket.cari_id if hareket else '',
                        conditional={'field': 'karsi_hesap_turu', 'value': 'cari'},
                        select2_config={'placeholder': 'Cari Seçiniz...', 'search': True})
    
    banka_id = FormField('banka_id', FieldType.SELECT, _('Banka Hesabı'), options=banka_opts, value=hareket.banka_id if hareket else '',
                         conditional={'field': 'karsi_hesap_turu', 'value': 'banka'})
    
    karsi_kasa_id = FormField('karsi_kasa_id', FieldType.SELECT, _('Hedef Kasa'), options=kasa_opts, value=hareket.karsi_kasa_id if hareket else '',
                              conditional={'field': 'karsi_hesap_turu', 'value': 'kasa'})

    tutar = FormField('tutar', FieldType.CURRENCY, _('Tutar'), required=True, value=hareket.tutar if hareket else 0)
    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), value=hareket.aciklama if hareket else '')

    # Layout
    layout.add_row(belge_no, tarih, kasa_id)
    layout.add_row(islem_yonu, karsi_hesap_turu)
    layout.add_row(cari_id, banka_id, karsi_kasa_id)
    layout.add_card("Tutar & Detay", [tutar, aciklama])

    form.set_layout_html(layout.render())
    form.add_fields(tarih, kasa_id, islem_yonu, karsi_hesap_turu, cari_id, banka_id, karsi_kasa_id, tutar, aciklama, belge_no)
    return form