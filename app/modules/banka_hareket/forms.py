# app/modules/banka_hareket/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.enums import BankaIslemTuru
from app.extensions import get_tenant_db # ✨ YENİ: Tenant DB Importu
from app.modules.banka.models import BankaHesap
from app.modules.cari.models import CariHesap
from app.modules.kasa.models import Kasa

def create_banka_hareket_form(hareket=None):
    is_edit = hareket is not None
    # ✨ UUID UYUMU (string id)
    action_url = f"/banka-hareket/duzenle/{hareket.id}" if is_edit else "/banka-hareket/ekle"
    title = _("İşlem Düzenle") if is_edit else _("Yeni Banka İşlemi")

    tenant_db = get_tenant_db() # ✨ VERİLER TENANT DB'DEN ÇEKİLİYOR

    # --- Seçenekleri Veritabanından Çek ---
    bankalar = tenant_db.query(BankaHesap).filter_by(firma_id=str(current_user.firma_id), aktif=True).all()
    b_opts = [(str(b.id), f"{b.banka_adi} - {b.ad}") for b in bankalar]

    cariler = tenant_db.query(CariHesap).filter_by(firma_id=str(current_user.firma_id)).limit(100).all()
    c_opts = [(str(c.id), c.unvan) for c in cariler]

    kasalar = tenant_db.query(Kasa).filter_by(firma_id=str(current_user.firma_id), aktif=True).all()
    k_opts = [(str(k.id), k.ad) for k in kasalar]

    # --- Varsayılanlar ve Mantık ---
    def safe_val(val, default=""):
        return getattr(val, 'value', val) if val else default

    mevcut_yon = 'giris'
    mevcut_taraf = 'cari'
    
    if hareket:
        islem_turu_val = str(safe_val(hareket.islem_turu, '')).lower()
        if 'tediye' in islem_turu_val or 'cikis' in islem_turu_val:
            mevcut_yon = 'cikis'
        
        if hareket.kasa_id: mevcut_taraf = 'kasa'
        elif hareket.karsi_banka_id: mevcut_taraf = 'banka'

    form = Form(name="banka_hareket_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    yon_opts = [
        ('giris', 'PARA GİRİŞİ (Tahsilat/Gelen)', 'bi bi-arrow-down-circle-fill text-success'), 
        ('cikis', 'PARA ÇIKIŞI (Tediye/Giden)', 'bi bi-arrow-up-circle-fill text-danger')
    ]
    
    taraf_opts = [
        ('cari', 'Cari Hesap', 'bi bi-person-badge'),
        ('banka', 'Banka Transfer (Virman)', 'bi bi-bank'),
        ('kasa', 'Kasa (Çek/Yatır)', 'bi bi-safe')
    ]

    # --- ALANLAR ---
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Dekont No'), required=True, 
                         value=hareket.belge_no if hareket else '', 
                         endpoint='/banka-hareket/api/siradaki-no')
                         
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=hareket.tarih if hareket else '')
    
    banka_id = FormField('banka_id', FieldType.SELECT, _('İşlem Gören Banka'), options=b_opts, required=True, value=str(hareket.banka_id) if hareket else '')

    islem_yonu = FormField('islem_yonu', FieldType.RADIO, _('İşlem Yönü'), options=yon_opts, value=mevcut_yon, html_attributes={'class': 'radio-card-group'})
    
    karsi_taraf = FormField('karsi_taraf', FieldType.RADIO, _('Karşı Hesap'), options=taraf_opts, value=mevcut_taraf, html_attributes={'class': 'radio-card-group', 'btn_color': 'secondary'})

    # Dinamik Alanlar
    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=c_opts, 
                        value=str(hareket.cari_id) if hareket and hareket.cari_id else '',
                        select2_config={'placeholder': 'Cari Seçiniz...', 'search': True},
                        conditional={'field': 'karsi_taraf', 'value': 'cari'})
    
    hedef_banka_id = FormField('hedef_banka_id', FieldType.SELECT, _('Karşı Banka'), options=b_opts, 
                               value=str(hareket.karsi_banka_id) if hareket and hareket.karsi_banka_id else '',
                               conditional={'field': 'karsi_taraf', 'value': 'banka'})

    kasa_id = FormField('kasa_id', FieldType.SELECT, _('Kasa'), options=k_opts, 
                        value=str(hareket.kasa_id) if hareket and hareket.kasa_id else '',
                        conditional={'field': 'karsi_taraf', 'value': 'kasa'})

    tutar = FormField('tutar', FieldType.CURRENCY, _('Tutar'), required=True, value=hareket.tutar if hareket else 0)
    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), value=hareket.aciklama if hareket else '')

    # --- Layout ---
    layout.add_row(belge_no, tarih, banka_id)
    layout.add_row(islem_yonu, karsi_taraf)
    layout.add_row(cari_id, hedef_banka_id, kasa_id)
    layout.add_card("Tutar Bilgisi", [tutar, aciklama])

    form.set_layout_html(layout.render())
    form.add_fields(belge_no, tarih, banka_id, islem_yonu, karsi_taraf, cari_id, hedef_banka_id, kasa_id, tutar, aciklama)
    
    return form