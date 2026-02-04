from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.depo.models import Depo
from app.modules.stok.models import StokKart
from app.enums import StokFisTuru

def create_stok_fisi_form(fis=None):
    is_edit = fis is not None
    action_url = f"/stok-fisi/duzenle/{fis.id}" if is_edit else "/stok-fisi/ekle"
    title = _("Stok Fişi İşlemleri")
    
    form = Form(name="stok_fisi_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- Veri Hazırlığı ---
    depolar = Depo.query.filter_by(firma_id=current_user.firma_id).all()
    depo_opts = [(d.id, d.ad) for d in depolar]
    
    stoklar = StokKart.query.filter_by(firma_id=current_user.firma_id).all()
    stok_opts = [(s.id, f"{s.kod} - {s.ad} ({s.birim})") for s in stoklar]

    tur_opts = [
        (StokFisTuru.TRANSFER.value, 'TRANSFER (Depolar Arası Sevk)'),
        (StokFisTuru.FIRE.value, 'FİRE / ZAYİ (Depodan Çıkış)'),
        (StokFisTuru.SARF.value, 'SARF / TÜKETİM (Depodan Çıkış)'),
        (StokFisTuru.SAYIM_EKSIK.value, 'SAYIM EKSİĞİ (Depodan Çıkış)'),
        (StokFisTuru.SAYIM_FAZLA.value, 'SAYIM FAZLASI (Depoya Giriş)'),
        (StokFisTuru.DEVIR.value, 'DEVİR / AÇILIŞ (Depoya Giriş)'),
        (StokFisTuru.URETIM.value, 'ÜRETİMDEN GİRİŞ (Depoya Giriş)')
    ]

    # --- ALANLAR ---
    fis_turu = FormField('fis_turu', FieldType.SELECT, _('İşlem Türü'), 
                         options=tur_opts, required=True, 
                         value=fis.fis_turu if fis else StokFisTuru.TRANSFER.value)

    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Fiş No'), 
                         required=True, value=fis.belge_no if fis else '', 
                         endpoint='/stok-fisi/api/siradaki-no', icon='bi bi-qr-code')

    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=fis.tarih if fis else '')

    # --- DİNAMİK DEPO SEÇİMİ ---
    
    # 1.ÇIKIŞ DEPOSU (conditional parametresini SİLDİK)
    cikis_depo_id = FormField('cikis_depo_id', FieldType.SELECT, _('Çıkış Yapılan Depo (Kaynak)'), 
                              options=depo_opts, 
                              value=fis.cikis_depo_id if fis else '',
                              select2_config={'placeholder': 'Depo Seçiniz'}) 

    # 2.GİRİŞ DEPOSU (conditional parametresini SİLDİK)
    giris_depo_id = FormField('giris_depo_id', FieldType.SELECT, _('Giriş Yapılan Depo (Hedef)'), 
                              options=depo_opts, 
                              value=fis.giris_depo_id if fis else '',
                              select2_config={'placeholder': 'Depo Seçiniz'})

    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), value=fis.aciklama if fis else '')

    # --- DETAYLAR ---
    detaylar = FormField('detaylar', FieldType.MASTER_DETAIL, _('Hareket Görecek Ürünler'), required=True)
    detaylar.columns = [
        FormField('stok_id', FieldType.SELECT, 'Stok Adı', options=stok_opts, required=True, 
                  select2_config={'placeholder': 'Stok Seç', 'search': True},
                  html_attributes={'style': 'width: 300px;'}),
        FormField('miktar', FieldType.NUMBER, 'Miktar', default_value=1, html_attributes={'step': '0.01', 'min': '0'}),
        FormField('aciklama', FieldType.TEXT, 'Satır Açıklaması')
    ]

    if is_edit and fis.detaylar:
        row_data = [{'stok_id': d.stok_id, 'miktar': float(d.miktar), 'aciklama': d.aciklama} for d in fis.detaylar]
        detaylar.value = row_data

    # --- LAYOUT ---
    layout.add_row(belge_no, tarih, fis_turu)
    
    # Depoları dinamik göstereceğiz
    layout.add_row(cikis_depo_id, giris_depo_id)
    
    layout.add_html('<hr>')
    layout.add_row(detaylar)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(belge_no, tarih, fis_turu, cikis_depo_id, giris_depo_id, aciklama, detaylar)
    
    return form