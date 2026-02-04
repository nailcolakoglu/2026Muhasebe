from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.cari.models import CariHesap
from app.modules.kasa.models import Kasa
from app.modules.sube.models import Sube
from app.modules.banka.models import BankaHesap
from app.enums import FinansIslemTuru, ParaBirimi

def create_makbuz_form(islem=None):
    is_edit = islem is not None
    action_url = f"/finans/duzenle/{islem.id}" if is_edit else "/finans/ekle"
    
    title = f"Makbuz Düzenle: {islem.belge_no}" if is_edit else _("Yeni Tahsilat/Tediye Makbuzu")
    
    form = Form(name="makbuz_form", title=title, action=action_url, method="POST", submit_text=_("Makbuzu Kaydet"), ajax=True, show_title=False)
    layout = FormLayout()

    # --- Veri Hazırlığı ---
    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
    cari_opts = [(str(c.id), f"{c.kod} - {c.unvan} ({c.doviz_turu})") for c in cariler]
    
    kasalar = Kasa.query.filter_by(firma_id=current_user.firma_id).all()
    kasa_opts = [("", "Seçiniz")] + [(str(k.id), k.ad) for k in kasalar]

    tur_opts = [
        (FinansIslemTuru.TAHSILAT.value, 'Tahsilat (Para Girişi)'),
        (FinansIslemTuru.TEDIYE.value, 'Tediye (Para Çıkışı)')
    ]
    
    doviz_opts = [(p.value, p.value) for p in ParaBirimi]

    # --- 1.GENEL BİLGİLER ---
    islem_turu = FormField('islem_turu', FieldType.SELECT, _('İşlem Türü'), options=tur_opts, required=True, value=islem.islem_turu if islem else 'tahsilat')
    belge_no = FormField('belge_no', FieldType.AUTO_NUMBER, _('Makbuz No'), required=True, value=islem.belge_no if islem else '', endpoint='/finans/api/siradaki-no', icon='bi bi-receipt')
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=islem.tarih if islem else '')
    cari_id = FormField('cari_id', FieldType.SELECT, _('Cari Hesap'), options=cari_opts, required=True, value=islem.cari_id if islem else '', select2_config={'placeholder': 'Cari Seçiniz', 'search': True})
    aciklama = FormField('aciklama', FieldType.TEXT, _('Genel Açıklama'), value=islem.aciklama if islem else '')

    # --- 2.NAKİT KISMI ---
    kasa_id = FormField('kasa_id', FieldType.SELECT, _('Kasa'), options=kasa_opts, select2_config={'placeholder': 'Nakit ise seçiniz'})
    nakit_tutar = FormField('nakit_tutar', FieldType.CURRENCY, _('Nakit Tutar'), value=0, icon='bi bi-cash')
    doviz_cinsi = FormField('doviz_cinsi', FieldType.SELECT, _('Para Birimi'), options=doviz_opts, default_value="TL")

    # --- 3.ÇEK/SENET KISMI (MASTER-DETAIL) ---
    # Bu yapı sayesinde birden fazla çek girilebilir.
    cek_columns = [
        {'name': 'portfoy_no', 'label': 'Portföy No', 'type': islem_turu, 'width': '15%'},
        {'name': 'vade_tarihi', 'label': 'Vade Tarihi', 'type': 'date', 'width': '20%'},
        {'name': 'banka_adi', 'label': 'Banka Adı', 'type': 'text', 'width': '25%'},
        {'name': 'cek_no', 'label': 'Çek Seri No', 'type': 'text', 'width': '20%'},
        {'name': 'tutar', 'label': 'Tutar', 'type': FieldType.CURRENCY, 'width': '20%'}
    ]
    cek_listesi = FormField("cek_listesi", FieldType.MASTER_DETAIL, _("Çek Listesi"), columns=cek_columns)

    # --- 4.DETAY SATIRLARI (KALEMLER) ---
    kalemler = FormField('kalemler', FieldType.MASTER_DETAIL, _('Senet Listesi'), required=True)
    
    kalemler.columns = [
        FormField('portfoy_no', FieldType.AUTO_NUMBER, 'Portföy No', 
                  required=True, endpoint='/finans/api/siradaki-no', icon='bi bi-receipt',
                  html_attributes={'style': 'width: 120px;'}),
        
        # Miktar ve Fiyat alanlarına 'md-calc-...' sınıfları ekliyoruz ki JS otomatik hesaplasın
        FormField('miktar', FieldType.CURRENCY, 'Miktar', required=True,  
                  html_attributes={'class': 'text-end md-calc-qty', 'style': 'width: 80px;'}),
        
        FormField('vade_tarihi', FieldType.DATE, 'Vade Tarihi', required=True, 
                  html_attributes={'class': 'text-end md-calc-price', 'style': 'width: 140px;'}),
        
        FormField('banka_adi', FieldType.TEXT, 'Banka Adı',
                  html_attributes={'class': 'md-calc-tax', 'style': 'width: 250px;'}),
        FormField('senet_no', FieldType.TEXT, 'Senet No',
                  html_attributes={'class': 'md-calc-tax', 'style': 'width: 70px;'}),

        # Bu alan salt okunur olacak, JS hesaplayıp yazacak
        FormField('tutar', FieldType.CURRENCY, 'Tutar',
                  html_attributes={'class': 'text-end fw-bold md-calc-total', 'style': 'width: 100px; background-color: #f8f9fa;'})
    ]

    if is_edit and finans.kalemler:
        row_data = []
        for k in finans.kalemler:
            row_data.append({
                'stok_id': k.stok_id,
                'miktar': float(k.miktar),
                'birim_fiyat': float(k.birim_fiyat),
                'kdv_orani': int(k.kdv_orani),
                'satir_toplami': float(k.satir_toplami)
            })
        kalemler.value = row_data

    layout.add_row(kalemler)
    # --- LAYOUT ---
    layout.add_row(belge_no, tarih, islem_turu)
    layout.add_row(cari_id)
    
    tab_nakit = [
        layout.create_alert("Bilgi", "Nakit tahsilat/ödeme yapacaksanız doldurunuz.", "info"),
        layout.create_row(kasa_id, nakit_tutar, doviz_cinsi)
    ]
    
    tab_cek = [
        layout.create_alert("Bilgi", "Makbuzla birlikte alınan/verilen çekleri listeye ekleyiniz.", "warning"),
        cek_listesi
    ]
    
    tabs = layout.create_tabs("finans_tabs", [
        ('<i class="bi bi-cash-stack me-2"></i>Nakit', tab_nakit),
        ('<i class="bi bi-ticket-detailed me-2"></i>Çek/Senet', tab_cek)
    ])
    
    layout.add_html(tabs)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    
    # Tüm alanları forma tanıt
    form.add_fields(islem_turu, belge_no, tarih, cari_id, aciklama, 
                    kasa_id, nakit_tutar, doviz_cinsi, cek_listesi)
    
    return form

def create_virman_form():
    """Kasalar ve Bankalar Arası Transfer Formu"""
    form = Form(name="virman_form", title=_("İç Transfer (Virman)"), action="/finans/virman", method="POST", submit_text=_("Transferi Gerçekleştir"), ajax=True, show_title=False)
    layout = FormLayout()

    # --- Veri Hazırlığı ---
    # Kullanıcının yetkili olduğu firmadaki tüm kasalar ve bankalar
    kasalar = Kasa.query.filter_by(firma_id=current_user.firma_id).all()
    bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()

    # Seçenekleri Hazırla (Tip belirteci ekleyerek: 'K-1', 'B-3' gibi)
    kaynak_opts = []
    hedef_opts = []
    
    # Gruplu Seçenek Yapısı (Select2 için optgroup mantığı manuel simüle edilir veya düz liste)
    # Basitlik için düz liste yapıyoruz ama başına etiket koyuyoruz
    
    for k in kasalar:
        etiket = f"KASA: {k.ad} ({k.doviz_turu})"
        val = f"KASA_{k.id}"
        kaynak_opts.append((val, etiket))
        hedef_opts.append((val, etiket))
        
    for b in bankalar:
        # HATA VEREN KISIM BURASIYDI.DÜZELTİLDİ:
        # b.banka_adi (Yeni alan) ve b.ad (Hesap Tanımı) kullanıyoruz
        etiket = f"BANKA: {b.banka_adi} - {b.ad} ({b.doviz_turu})"
        val = f"BANKA_{b.id}"
        kaynak_opts.append((val, etiket))
        hedef_opts.append((val, etiket))

    # --- ALANLAR ---
    tarih = FormField('tarih', FieldType.DATE, _('İşlem Tarihi'), required=True)
    
    kaynak = FormField('kaynak', FieldType.SELECT, _('Kaynak Hesap (Paranın Çıktığı)'), 
                       options=kaynak_opts, required=True, 
                       select2_config={'placeholder': 'Seçiniz...'})
                       
    hedef = FormField('hedef', FieldType.SELECT, _('Hedef Hesap (Paranın Girdiği)'), 
                      options=hedef_opts, required=True, 
                      select2_config={'placeholder': 'Seçiniz...'})
    
    tutar = FormField('tutar', FieldType.CURRENCY, _('Transfer Tutarı'), required=True)
    
    belge_no = FormField('belge_no', FieldType.TEXT, _('Belge No'), required=True, value="VRM-")
    
    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'), value="İç Transfer (Virman)")

    # --- LAYOUT ---
    layout.add_row(tarih, belge_no)
    layout.add_row(kaynak, hedef)
    layout.add_alert("Dikkat", "Kaynak ve Hedef hesapların döviz türleri aynı olmalıdır.Çapraz kur (Arbitraj) işlemi henüz desteklenmemektedir.", "warning")
    layout.add_row(tutar)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(tarih, kaynak, hedef, tutar, belge_no, aciklama)
    
    return form

def create_gider_form():
    """Gider/Masraf İşleme Formu"""
    form = Form(name="gider_form", title=_("Gider Fişi (Masraf)"), action="/finans/gider-ekle", method="POST", submit_text=_("Gideri Kaydet"), ajax=True, show_title=False)
    layout = FormLayout()

    # --- Veri Hazırlığı ---
    kasalar = Kasa.query.filter_by(firma_id=current_user.firma_id).all()
    bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()

    hesap_opts = []
    
    for k in kasalar:
        etiket = f"KASA: {k.ad} ({k.doviz_turu})"
        val = f"KASA_{k.id}"
        hesap_opts.append((val, etiket))
        
    for b in bankalar:
        etiket = f"BANKA: {b.banka_adi} - {b.ad} ({b.doviz_turu})"
        val = f"BANKA_{b.id}"
        hesap_opts.append((val, etiket))

    gider_turleri = [
        ('genel', 'Genel Giderler'),
        ('kira', 'Kira Ödemesi'),
        ('enerji', 'Elektrik/Su/Doğalgaz'),
        ('personel', 'Personel/Maaş/Avans'),
        ('akaryakit', 'Araç/Akaryakıt'),
        ('yemek', 'Yemek/Temsil'),
        ('kirtasiye', 'Ofis/Kırtasiye'),
        ('vergi', 'Vergi/SGK Ödemesi')
    ]

    # --- ALANLAR ---
    tarih = FormField('tarih', FieldType.DATE, _('İşlem Tarihi'), required=True)
    
    hesap = FormField('hesap', FieldType.SELECT, _('Ödeme Yapılan Hesap'), 
                       options=hesap_opts, required=True, 
                       select2_config={'placeholder': 'Kasa veya Banka Seçiniz...'})
                       
    gider_turu = FormField('gider_turu', FieldType.SELECT, _('Gider Türü'), 
                      options=gider_turleri, required=True)
    
    tutar = FormField('tutar', FieldType.CURRENCY, _('Tutar'), required=True)
    
    belge_no = FormField('belge_no', FieldType.TEXT, _('Fiş/Fatura No'), required=True, value="")
    
    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'), value="")

    # --- LAYOUT ---
    layout.add_row(tarih, belge_no)
    layout.add_row(hesap, gider_turu)
    layout.add_row(tutar)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(tarih, hesap, gider_turu, tutar, belge_no, aciklama)
    
    return form


