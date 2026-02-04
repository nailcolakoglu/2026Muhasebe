from app.form_builder import Form, FormField, FieldType, FormLayout
from flask import session
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.kullanici.models import Kullanici
from app.modules.sube.models import Sube
from app.modules.kasa.models import Kasa 
# 👇 Utils kullanımı (Muhasebe hesaplarını buradan çekiyoruz)
from app.modules.muhasebe.utils import get_muhasebe_hesaplari
from app.enums import ParaBirimi

def create_kasa_form(kasa=None):
    is_edit = kasa is not None
    action_url = f"/kasa/duzenle/{kasa.id}" if is_edit else "/kasa/ekle"
    
    title = _("Kasa Düzenle") if is_edit else _("Yeni Kasa")
    
    form = Form(
        name="kasa_form",
        title=title,
        action=action_url,
        method="POST",
        submit_text=_("Kaydet"),
        ajax=True
    )
    
    layout = FormLayout()

    # --- VERİ HAZIRLIĞI ---
    
    # 1.Şubeler (Yetkiye göre filtreli)
    sube_query = Sube.query.filter_by(firma_id=current_user.firma_id, aktif=True)
    merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
    
    if current_user.rol not in merkez_rolleri:
        aktif_bolge_id = session.get('aktif_bolge_id')
        aktif_sube_id = session.get('aktif_sube_id')
        if aktif_bolge_id:
            sube_query = sube_query.filter_by(bolge_id=aktif_bolge_id)
        elif aktif_sube_id:
            sube_query = sube_query.filter_by(id=aktif_sube_id)

    subeler = sube_query.all()
    sube_opts = [(s.id, f"{s.kod} - {s.ad}") for s in subeler]
    
    # 2.Personel Listesi (Zimmet İçin) 🛡️
    # Sadece bu firmanın aktif personelleri
    personeller = Kullanici.query.filter_by(firma_id=current_user.firma_id, aktif=True).all()
    # İlk seçenek boş (Genel Kasa) olsun
    personel_opts = [("", "Genel Kasa (Zimmet Yok)")] + [(u.id, u.ad_soyad) for u in personeller]

    # 3.Muhasebe Hesapları
    muhasebe_opts = get_muhasebe_hesaplari()

    # 4.Döviz Türleri
    doviz_etiketleri = {
        'TL': 'Türk Lirası',
        'USD': 'Amerikan Doları',
        'EUR': 'Euro',
        'GBP': 'İngiliz Sterlini',
        'CHF': 'İsviçre Frangı'
    }
    doviz_opts = [(p.value, doviz_etiketleri.get(p.value, p.value)) for p in ParaBirimi]

    # --- ALANLAR ---
    
    kod = FormField(
        'kod', FieldType.AUTO_NUMBER, _('Kasa Kodu'), 
        required=True, 
        value=kasa.kod if kasa else '', 
        endpoint='/kasa/api/siradaki-kod', 
        icon='bi bi-safe'
    )
    
    ad = FormField('ad', FieldType.TEXT, _('Kasa Adı'), required=True, value=kasa.ad if kasa else '', icon='bi bi-wallet2')
    
    sube_id = FormField(
        'sube_id', FieldType.SELECT, _('Bağlı Olduğu Şube'), 
        options=sube_opts, 
        required=True, 
        value=kasa.sube_id if kasa else '',
        select2_config={'placeholder': 'Şube Seçiniz'}
    )
    
    # 👇 YENİ ALAN: Zimmetli Personel
    kullanici_id = FormField(
        'kullanici_id', FieldType.SELECT, _('Kasa Sorumlusu (Zimmet)'), 
        options=personel_opts, 
        required=False, # Zorunlu değil
        value=kasa.kullanici_id if kasa else '',
        select2_config={'placeholder': 'Personel Seçiniz...', 'allowClear': True},
        icon='bi bi-person-badge'
    )
    
    if len(subeler) == 1 and not kasa:
        sube_id.default_value = subeler[0].id

    doviz_turu = FormField('doviz_turu', FieldType.SELECT, _('Döviz Cinsi'), options=doviz_opts, required=True, value=kasa.doviz_turu if kasa else 'TL')
    
    muhasebe_hesap = FormField(
        'muhasebe_hesap_id', FieldType.SELECT, _('Muhasebe Hesabı (100)'), 
        options=muhasebe_opts, 
        value=kasa.muhasebe_hesap_id if kasa else '', 
        select2_config={'placeholder': 'Muhasebe Hesabı Bağla...', 'allowClear': True}
    )

    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'), value=kasa.aciklama if kasa else '', html_attributes={'rows': 2})
    aktif = FormField('aktif', FieldType.CHECKBOX, _('Kasa Aktif'), value='1', checked=(kasa.aktif if kasa else True))

    # --- LAYOUT ---
    tabs = layout.create_tabs("kasa_tabs", [
        ('<i class="bi bi-info-circle me-2"></i>Genel Bilgiler', [
            layout.create_row(kod, ad),
            layout.create_row(sube_id, kullanici_id), # Kullanıcıyı buraya koyduk
            layout.create_row(doviz_turu, aktif)
        ]),
        ('<i class="bi bi-layers me-2"></i>Entegrasyon & Detay', [
            muhasebe_hesap,
            aciklama
        ])
    ])

    form.set_layout_html(tabs)
    form.add_fields(kod, ad, sube_id, kullanici_id, doviz_turu, muhasebe_hesap, aciklama, aktif)
    
    return form

