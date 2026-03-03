# app/modules/stok_fisi/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from flask import session
from app.modules.depo.models import Depo
from app.modules.stok.models import StokKart
from app.modules.sube.models import Sube
from app.enums import StokFisTuru
from app.extensions import get_tenant_db
from datetime import datetime

def create_stok_fisi_form(fis=None):
    is_edit = fis is not None
    action_url = f"/stok-fisi/duzenle/{fis.id}" if is_edit else "/stok-fisi/ekle"
    title = _("Stok Fişi İşlemleri")
    
    form = Form(name="stok_fisi_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()
    
    tenant_db = get_tenant_db()

    # ==========================================
    # 1. AKILLI DEPO LİSTESİ (Yetki ve Şube Kapsamlı)
    # ==========================================
    aktif_sube_id = session.get('aktif_sube_id')
    aktif_bolge_id = session.get('aktif_bolge_id')

    depo_query = tenant_db.query(Depo).filter_by(firma_id=str(current_user.firma_id), aktif=True)
    
    # Yetki kontrolü (Data Scoping)
    if current_user.rol not in ['admin', 'patron', 'muhasebe_muduru']:
        if aktif_bolge_id: depo_query = depo_query.join(Sube).filter(Sube.bolge_id == aktif_bolge_id)
        elif aktif_sube_id: depo_query = depo_query.filter_by(sube_id=aktif_sube_id)
    else:
        if aktif_sube_id: depo_query = depo_query.filter_by(sube_id=aktif_sube_id)
        
    depolar = depo_query.order_by(Depo.ad).all()
    depo_opts = [(str(d.id), d.ad) for d in depolar]

    # ==========================================
    # 2. STOK LİSTESİ (100.000 KAYIT OPTİMİZASYONU)
    # ==========================================
    # ❌ ESKİ KOD: Bütün stokları çekip sistemi kilitliyordu!
    # ✅ YENİ KOD: Düzenleme modunda sadece fişteki stoklar yüklenir. Kalanı AJAX ile gelir.
    stok_opts = []
    if is_edit and fis.detaylar:
        stok_id_list = [d.stok_id for d in fis.detaylar if d.stok_id]
        if stok_id_list:
            secili_stoklar = tenant_db.query(StokKart).filter(StokKart.id.in_(stok_id_list)).all()
            stok_opts = [(str(s.id), f"{s.kod} - {s.ad} ({s.birim})") for s in secili_stoklar]

    tur_opts = [
        (StokFisTuru.TRANSFER.value, 'TRANSFER (Depolar Arası Sevk)'),
        (StokFisTuru.FIRE.value, 'FİRE / ZAYİ (Depodan Çıkış)'),
        (StokFisTuru.SARF.value, 'SARF / TÜKETİM (Depodan Çıkış)'),
        (StokFisTuru.SAYIM_EKSIK.value, 'SAYIM EKSİĞİ (Depodan Çıkış)'),
        (StokFisTuru.SAYIM_FAZLA.value, 'SAYIM FAZLASI (Depoya Giriş)'),
        (StokFisTuru.DEVIR.value, 'DEVİR / AÇILIŞ (Depoya Giriş)'),
        (StokFisTuru.URETIM.value, 'ÜRETİMDEN GİRİŞ (Depoya Giriş)')
    ]

    # ==========================================
    # 3. FORM ALANLARI
    # ==========================================
    val_fis_turu = StokFisTuru.TRANSFER.value
    if fis and getattr(fis, 'fis_turu', None):
        val_fis_turu = fis.fis_turu.value if hasattr(fis.fis_turu, 'value') else fis.fis_turu

    fis_turu = FormField('fis_turu', FieldType.SELECT, _('İşlem Türü'), 
                         options=tur_opts, required=True, 
                         value=val_fis_turu)
                         
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Fiş No'), 
                         required=True, value=fis.belge_no if fis else '', 
                         endpoint='/stok-fisi/api/siradaki-no', icon='bi bi-qr-code')

    # TARİH FORMATI DÜZELTİLDİ: Kesinlikle YYYY-MM-DD olarak gitmeli
    bugun_str = datetime.now().strftime('%Y-%m-%d')
    val_tarih = fis.tarih.strftime('%Y-%m-%d') if fis and getattr(fis, 'tarih', None) else bugun_str
    
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=val_tarih)

    cikis_depo_id = FormField('cikis_depo_id', FieldType.SELECT, _('Çıkış Yapılan Depo (Kaynak)'), 
                              options=depo_opts, 
                              value=str(fis.cikis_depo_id) if fis and fis.cikis_depo_id else '',
                              select2_config={'placeholder': 'Depo Seçiniz', 'allowClear': True}) 

    giris_depo_id = FormField('giris_depo_id', FieldType.SELECT, _('Giriş Yapılan Depo (Hedef)'), 
                              options=depo_opts, 
                              value=str(fis.giris_depo_id) if fis and fis.giris_depo_id else '',
                              select2_config={'placeholder': 'Depo Seçiniz', 'allowClear': True})

    aciklama = FormField('aciklama', FieldType.TEXT, _('Açıklama'), value=fis.aciklama if fis else '')

    # ==========================================
    # 4. HAREKET DETAYLARI (AJAX AJAX AJAX)
    # ==========================================
    detaylar = FormField('detaylar', FieldType.MASTER_DETAIL, _('Hareket Görecek Ürünler'), required=True)
    detaylar.columns = [
        # 👇 SİHİRLİ DOKUNUŞ: data-ajax-url Eklendi!
        FormField('stok_id', FieldType.SELECT, 'Stok Adı', options=stok_opts, required=True, 
                  select2_config={'placeholder': 'Aramak için yazın...', 'search': True},
                  html_attributes={'style': 'width: 300px;', 'data-ajax-url': '/fatura/api/stok-ara'}),
                  
        FormField('miktar', FieldType.NUMBER, 'Miktar', default_value=1, html_attributes={'step': '0.01', 'min': '0'}),
        FormField('aciklama', FieldType.TEXT, 'Satır Açıklaması')
    ]

    if is_edit and fis.detaylar:
        row_data = [{'stok_id': str(d.stok_id), 'miktar': float(d.miktar), 'aciklama': d.aciklama} for d in fis.detaylar]
        detaylar.value = row_data

    # --- LAYOUT ---
    layout.add_row(belge_no, tarih, fis_turu)
    layout.add_row(cikis_depo_id, giris_depo_id)
    layout.add_html('<hr>')
    layout.add_row(detaylar)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(belge_no, tarih, fis_turu, cikis_depo_id, giris_depo_id, aciklama, detaylar)
    
    return form