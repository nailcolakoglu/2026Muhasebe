# app/modules/banka_hareket/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from app.enums import BankaIslemTuru

def create_banka_hareket_form(hareket=None, banka_opts=None, cari_opts=None, kasa_opts=None):
    """
    Banka Hareket Formu.
    Opsiyonlar parametre olarak gelir (Dependency Injection).
    """
    is_edit = hareket is not None
    action_url = f"/banka-hareket/duzenle/{hareket.id}" if is_edit else "/banka-hareket/ekle"
    title = _("İşlem Düzenle") if is_edit else _("Yeni Banka İşlemi")

    # --- Varsayılanlar ve Mantık ---
    defaults = {
        'belge_no': hareket.belge_no if hareket else '',
        'tarih': hareket.tarih if hareket else '',
        'banka_id': hareket.banka_id if hareket else '',
        'tutar': hareket.tutar if hareket else 0,
        'aciklama': hareket.aciklama if hareket else '',
        'cari_id': hareket.cari_id if hareket else '',
        'hedef_banka_id': hareket.karsi_banka_id if hareket else '',
        'kasa_id': hareket.kasa_id if hareket else ''
    }

    # Yön ve Taraf Analizi
    mevcut_yon = 'giris'
    mevcut_taraf = 'cari'
    
    if hareket:
        if hareket.islem_turu in [BankaIslemTuru.TEDIYE, BankaIslemTuru.VIRMAN_CIKIS]:
            mevcut_yon = 'cikis'
        
        if hareket.kasa_id: mevcut_taraf = 'kasa'
        elif hareket.karsi_banka_id: mevcut_taraf = 'banka'

    form = Form(name="banka_hareket_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- Seçenekler (Defaults to Empty List) ---
    b_opts = banka_opts or []
    c_opts = cari_opts or []
    k_opts = kasa_opts or []

    yon_opts = [
        ('giris', 'PARA GİRİŞİ (Tahsilat)', 'bi bi-arrow-down-circle-fill text-success'), 
        ('cikis', 'PARA ÇIKIŞI (Tediye)', 'bi bi-arrow-up-circle-fill text-danger')
    ]
    
    taraf_opts = [
        ('cari', 'Cari Hesap', 'bi bi-person-badge'),
        ('banka', 'Banka Transfer (Virman)', 'bi bi-bank'),
        ('kasa', 'Kasa (Çek/Yatır)', 'bi bi-safe')
    ]

    # --- ALANLAR ---
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Dekont No'), required=True, value=defaults['belge_no'], endpoint='/banka-hareket/api/siradaki-no')
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=defaults['tarih'])
    
    banka_id = FormField('banka_id', FieldType.SELECT, _('İşlem Gören Banka'), options=b_opts, required=True, value=defaults['banka_id'])

    islem_yonu = FormField('islem_yonu', FieldType.RADIO, _('İşlem Yönü'), options=yon_opts, value=mevcut_yon, html_attributes={'class': 'radio-card-group'})
    
    karsi_taraf = FormField('karsi_taraf', FieldType.RADIO, _('Karşı Hesap'), options=taraf_opts, value=mevcut_taraf, html_attributes={'class': 'radio-card-group', 'btn_color': 'secondary'})

    # Dinamik Alanlar
    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=c_opts, value=defaults['cari_id'],
                        select2_config={'placeholder': 'Cari Seçiniz...', 'search': True},
                        conditional={'field': 'karsi_taraf', 'value': 'cari'})
    
    hedef_banka_id = FormField('hedef_banka_id', FieldType.SELECT, _('Karşı Banka'), options=b_opts, value=defaults['hedef_banka_id'],
                               conditional={'field': 'karsi_taraf', 'value': 'banka'})

    kasa_id = FormField('kasa_id', FieldType.SELECT, _('Kasa'), options=k_opts, value=defaults['kasa_id'],
                        conditional={'field': 'karsi_taraf', 'value': 'kasa'})

    tutar = FormField('tutar', FieldType.CURRENCY, _('Tutar'), required=True, value=defaults['tutar'])
    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), value=defaults['aciklama'])

    # --- Layout ---
    layout.add_row(belge_no, tarih, banka_id)
    layout.add_row(islem_yonu, karsi_taraf)
    layout.add_row(cari_id, hedef_banka_id, kasa_id)
    layout.add_card("Tutar Bilgisi", [tutar, aciklama])

    form.set_layout_html(layout.render())
    form.add_fields(belge_no, tarih, banka_id, islem_yonu, karsi_taraf, cari_id, hedef_banka_id, kasa_id, tutar, aciklama)
    
    return form