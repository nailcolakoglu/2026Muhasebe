# app/modules/siparis/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from flask import session
from datetime import datetime
from app.extensions import get_tenant_db 

from app.modules.cari.models import CariHesap
from app.modules.depo.models import Depo
from app.modules.sube.models import Sube
from app.modules.stok.models import StokKart
from app.modules.fiyat.models import FiyatListesi
from app.modules.siparis.models import Siparis, OdemePlani
from app.enums import ParaBirimi, SiparisDurumu, StokBirimleri
from app.araclar import sayi_formatla

def create_siparis_form(siparis=None):
    is_edit = siparis is not None
    action_url = f"/siparis/duzenle/{siparis.id}" if is_edit else "/siparis/ekle"
    title = _("Sipariş Düzenle") if is_edit else _("Yeni Sipariş")
    
    form = Form(name="siparis_form", title='', action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # ✨ DÜZELTME: UI Tema Ayarları (Formun düzgün görünmesini sağlayan CSS motoru)
    theme = {'colorfocus': '#e3f2fd', 'textfocus': '#1565c0', 'borderfocus': '#2196f3'}
    
    tenant_db = get_tenant_db()
    
    # Varsayılan boş listeler (AJAX İçin)
    cari_opts = []
    depo_opts = []
    stok_opts = []
    liste_opts = [(0, "Varsayılan (Stok Kartı)")]
    odeme_opts = [(0, "Peşin")]

    if tenant_db:
        # ==========================================
        # 1. AKILLI DEPO LİSTESİ (Data Scoping)
        # ==========================================
        aktif_sube_id = session.get('aktif_sube_id')
        aktif_bolge_id = session.get('aktif_bolge_id')

        depo_query = tenant_db.query(Depo).filter_by(firma_id=str(current_user.firma_id), aktif=True)
        
        if current_user.rol not in ['admin', 'patron', 'muhasebe_muduru', 'satis_muduru']:
            if aktif_bolge_id: depo_query = depo_query.join(Sube).filter(Sube.bolge_id == aktif_bolge_id)
            elif aktif_sube_id: depo_query = depo_query.filter_by(sube_id=aktif_sube_id)
        else:
            if aktif_sube_id: depo_query = depo_query.filter_by(sube_id=aktif_sube_id)
            
        depo_opts = [(str(d.id), d.ad) for d in depo_query.order_by(Depo.ad).all()]

        # ==========================================
        # 2. CARİ HESAPLAR (AJAX Lazy Load)
        # ==========================================
        if is_edit and getattr(siparis, 'cari_id', None):
            try:
                secili_cari = tenant_db.query(CariHesap).get(str(siparis.cari_id))
                if secili_cari:
                    cari_opts = [(str(secili_cari.id), f"{secili_cari.unvan} ({secili_cari.kod})")]
            except: pass

        # ==========================================
        # 3. STOKLAR (AJAX Lazy Load)
        # ==========================================
        if is_edit and getattr(siparis, 'detaylar', None):
            stok_id_list = [d.stok_id for d in siparis.detaylar if d.stok_id]
            if stok_id_list:
                secili_stoklar = tenant_db.query(StokKart).filter(StokKart.id.in_(stok_id_list)).all()
                stok_opts = [(str(s.id), f"{s.kod} - {s.ad} ({s.birim or 'Adet'})") for s in secili_stoklar]

        # ==========================================
        # 4. DİĞER KÜÇÜK TABLOLAR
        # ==========================================
        fiyat_listeleri = tenant_db.query(FiyatListesi).filter_by(aktif=True).all()
        liste_opts.extend([(str(fl.id), fl.ad) for fl in fiyat_listeleri])
        
        odeme_planlari = tenant_db.query(OdemePlani).all()
        odeme_opts.extend([(str(op.id), op.ad) for op in odeme_planlari])

    doviz_opts = [(pb.name, pb.value) for pb in ParaBirimi]
    durum_opts = SiparisDurumu.choices()

    # ==========================================
    # 5. DEĞER ATAMALARI & TARİH FORMATLARI
    # ==========================================
    val_doviz = siparis.doviz_turu.name if (siparis and hasattr(siparis.doviz_turu, 'name')) else str(siparis.doviz_turu) if siparis else ParaBirimi.TL.name
    val_fiyat_list = str(siparis.fiyat_listesi_id) if (siparis and siparis.fiyat_listesi_id) else '0'
    val_odeme = str(siparis.odeme_plani_id) if (siparis and siparis.odeme_plani_id) else '0'
    val_durum = siparis.durum.value if (siparis and hasattr(siparis.durum, 'value')) else str(siparis.durum) if siparis else SiparisDurumu.BEKLIYOR.value
    val_depo = str(siparis.depo_id) if siparis else (depo_opts[0][0] if depo_opts else '')
    
    bugun_str = datetime.now().strftime('%Y-%m-%d')
    val_tarih = siparis.tarih.strftime('%Y-%m-%d') if siparis and getattr(siparis, 'tarih', None) else bugun_str
    val_teslim = siparis.teslim_tarihi.strftime('%Y-%m-%d') if siparis and getattr(siparis, 'teslim_tarihi', None) else ''

    # ==========================================
    # 6. FORM ALANLARI (Bootstrap Hizalaması ve THEME Eklendi)
    # ==========================================
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Belge No'), required=True, 
                        value=siparis.belge_no if siparis else '', endpoint='/siparis/api/siradaki-no', icon='bi bi-receipt')
    tarih = FormField('tarih', FieldType.DATE, 'Tarih', required=True, value=val_tarih)
    teslim_tarihi = FormField('teslim_tarihi', FieldType.DATE, 'Teslim Tarihi', value=val_teslim)
    durum = FormField('durum', FieldType.SELECT, 'Durum', options=durum_opts, required=True, value=val_durum)
    
    cari_id = FormField('cari_id', FieldType.SELECT, 'Müşteri', options=cari_opts, required=True, 
                        select2_config={'search': True, 'placeholder': 'Aramak için yazın...'}, 
                        html_attributes={'data-ajax-url': '/cari/api/ara'}, 
                        value=str(siparis.cari_id) if siparis else '')
                        
    depo_id = FormField('depo_id', FieldType.SELECT, 'Çıkış Deposu', options=depo_opts, required=True, value=val_depo)
    
    doviz_turu = FormField('doviz_turu', FieldType.SELECT, 'Döviz', options=doviz_opts, value=val_doviz)
    doviz_kuru = FormField('doviz_kuru', FieldType.CURRENCY, 'Döviz Kuru', value=siparis.doviz_kuru if siparis else 1)
    fiyat_listesi_id = FormField('fiyat_listesi_id', FieldType.SELECT, 'Fiyat Listesi', options=liste_opts, value=val_fiyat_list)
    odeme_plani_id = FormField('odeme_plani_id', FieldType.SELECT, 'Ödeme Planı', options=odeme_opts, value=val_odeme)

    sevk_adresi = FormField('sevk_adresi', FieldType.TEXTAREA, 'Sevk Adresi', value=siparis.sevk_adresi if siparis else '', html_attributes={'rows': 2})
    aciklama = FormField('aciklama', FieldType.TEXTAREA, 'Notlar', value=siparis.aciklama if siparis else '', html_attributes={'rows': 2})

    # ==========================================
    # 7. MASTER-DETAIL (Ürünler)
    # ==========================================
    detaylar = FormField('detaylar', FieldType.MASTER_DETAIL, 'Ürünler')
    detaylar.columns = [
        FormField('id', FieldType.HIDDEN, 'ID', default_value=0, html_attributes={'style': 'width: 0px;'}),
        
        FormField('stok_id', FieldType.SELECT, 'Ürün', 
                  options=stok_opts, 
                  required=True, 
                  html_attributes={
                      'style': 'width: 400px;', 
                      'data-ajax-url': '/siparis/api/stok-ara',
                      'data-placeholder': 'Ürün adı veya kodu arayın...'
                  }),
        FormField('miktar', FieldType.NUMBER, 'Miktar', default_value=1, html_attributes={'step': '0.01', 'style': 'width: 80px;'}),
        FormField('birim', FieldType.SELECT, 'Birim', options=StokBirimleri.choices(), default_value='Adet', html_attributes={'style': 'width: 90px;'}),
        FormField('birim_fiyat', FieldType.CURRENCY, 'Birim Fiyat', default_value=0, html_attributes={'style': 'width: 100px;'}),
        FormField('iskonto_orani', FieldType.NUMBER, 'İsk.%', default_value=0, html_attributes={'max': 100, 'style': 'width: 70px;'}),
        FormField('kdv_orani', FieldType.NUMBER, 'KDV%', default_value=20, html_attributes={'style': 'width: 70px;'}),
        FormField('tutar', FieldType.CURRENCY, 'Satır Toplamı', html_attributes={'readonly': True, 'style': 'width: 120px; font-weight: bold;'})
    ]

    if is_edit and siparis.detaylar:
        row_data = []
        for d in siparis.detaylar:
            row_data.append({
                'id': str(d.id),
                'stok_id': str(d.stok_id),
                'miktar': float(d.miktar), 
                'birim': d.birim.value if hasattr(d.birim, 'value') else d.birim or 'Adet',
                'birim_fiyat': sayi_formatla(d.birim_fiyat), 
                'iskonto_orani': (d.iskonto_orani), 
                'kdv_orani': (d.kdv_orani), 
                'tutar': sayi_formatla(d.satir_toplami)
            })
        detaylar.value = row_data

    # --- LAYOUT OLUŞTURMA (Satırlar birleştirildi) ---
    layout.add_row(belge_no, tarih, teslim_tarihi, durum)
    layout.add_row(cari_id, depo_id)
    layout.add_row(doviz_turu, doviz_kuru, fiyat_listesi_id, odeme_plani_id)
    layout.add_row(sevk_adresi, aciklama)
    layout.add_row(detaylar)

    form.set_layout_html(layout.render())
    form.add_fields(belge_no, tarih, teslim_tarihi, doviz_turu, durum, odeme_plani_id, cari_id, depo_id, fiyat_listesi_id, sevk_adresi, aciklama, detaylar, doviz_kuru)
    
    return form