# modules/cek/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.cari.models import CariHesap
from app.modules.kasa.models import Kasa
from app.modules.banka.models import BankaHesap
from datetime import datetime 
from app.enums import CekDurumu, PortfoyTipi, ParaBirimi, CekIslemTuru

def create_cek_form(yon='alinan', islem=None, view_only=False):
    """
    yon: 'alinan' (Müşteri Çeki) veya 'verilen' (Kendi Çekimiz)
    """
    is_edit = islem is not None
    action_url = f"/cek/duzenle/{islem.id}" if is_edit else f"/cek/ekle?yon={yon}"
    
    baslik_on_ek = "Girişi" if yon == 'alinan' else "Çıkışı"
    if is_edit: baslik_on_ek = "Düzenleme"
    if view_only: baslik_on_ek = "Detayı" # ✅ Detay başlığı
    
    form = Form(name="cek_form", title=f"Kıymetli Evrak {baslik_on_ek}", action=action_url, method="POST", ajax=True, show_title=False, view_mode=view_only)

    layout = FormLayout()

    # ==========================
    # 1.ALAN TANIMLAMALARI
    # ==========================
    
    # --- Tür ve Numara ---
    tur_opts = [('CEK', 'Çek'), ('SENET', 'Senet')]
    tur = FormField('tur', FieldType.RADIO, _('Evrak Türü'), options=tur_opts, default_value='CEK', required=True)

    sys_no = FormField('sys_belge_no', FieldType.AUTO_NUMBER, _('Portföy No (Sistem)'), 
                       endpoint='/cek/api/siradaki-no', required=True,
                       html_attributes={'readonly': True})

    fiziksel_no = FormField('seri_no', FieldType.TEXT, _('Şirket İçi Seri No'), 
                            required=False, placeholder="İç Takip No")

    # --- Tarih ve Tutar ---
    tarih = FormField('duzenleme_tarihi', FieldType.DATE, _('Düzenleme Tarihi'), required=True, default_value='today')
    vade_tarihi = FormField('vade_tarihi', FieldType.DATE, _('Vade Tarihi'), required=True)
    tutar = FormField('tutar', FieldType.CURRENCY, _('Tutar'), required=True, icon='bi bi-cash-stack')

    # --- Taraflar ---
    cari_label = "Müşteri (Veren)" if yon == 'alinan' else "Tedarikçi (Alan)"
    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
    cari_opts = [(str(c.id), f"{c.unvan}") for c in cariler]
    cari_id = FormField('cari_id', FieldType.SELECT, _(cari_label), options=cari_opts, required=True, select2_config={'search': True})

    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'))

    # --- Koşullu / Yöne Göre Alanlar ---
    fields_to_add = [tur, sys_no, fiziksel_no, tarih, vade_tarihi, tutar, cari_id, aciklama]

    # Değişkenleri önceden None tanımlayalım (Scope hatası olmasın)
    cek_resmi = kesideci_vkn = kesideci_unvan = banka_adi = sube_adi = hesap_no = cek_no = iban = kefil = bizim_banka = None

    if yon == 'alinan':
        cek_resmi = FormField('cek_resmi', FieldType.IMAGE, _('Belge Fotoğrafı'), html_attributes={'data-ocr-target': 'true'})
        kesideci_vkn = FormField('kesideci_tc_vkn', FieldType.TCKN_VKN, _('Keşideci VKN/TC'), html_attributes={'maxlength': '11'})
        kesideci_unvan = FormField('kesideci_unvan', FieldType.TEXT, _('Keşideci Ünvanı'))
        banka_adi = FormField('banka_adi', FieldType.TEXT, _('Banka Adı'), conditional={'field': 'tur', 'value': 'CEK'})
        sube_adi = FormField('sube_adi', FieldType.TEXT, _('Şube Adı'),conditional={'field': 'tur', 'value': 'CEK'})
        hesap_no = FormField('hesap_no', FieldType.TEXT, _('Hesap No'),conditional={'field': 'tur', 'value': 'CEK'})
        cek_no = FormField('cek_no', FieldType.TEXT, _('Matbu Belge No'), required=True) 
        iban = FormField('iban', FieldType.IBAN, _('IBAN'),conditional={'field': 'tur', 'value': 'CEK'})
        kefil = FormField('kefil', FieldType.TEXT, _('Kefil Adı Soyadı'), conditional={'field': 'tur', 'value': 'SENET'})
        
        fields_to_add.extend([cek_resmi, kesideci_vkn, kesideci_unvan, banka_adi, sube_adi, hesap_no, cek_no, iban, kefil])

    else: # Verilen Çek
        bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()
        banka_opts = [("", "Seçiniz")] + [(str(b.id), f"{b.banka_adi} - {b.hesap_no}") for b in bankalar]
        bizim_banka = FormField('banka_hesap_id', FieldType.SELECT, _('Hangi Bankamızdan?'), 
                                options=banka_opts, conditional={'field': 'tur', 'value': 'CEK'})
        fields_to_add.append(bizim_banka)

    # ==========================================
    # 2.VERİ DOLDURMA (BINDING) - BURAYA TAŞINDI!
    # ==========================================
    # Layout oluşturulmadan ÖNCE değerleri atıyoruz.
    if is_edit and islem:
        tur.value = islem.tur
        sys_no.value = islem.belge_no
        fiziksel_no.value = islem.seri_no
        tarih.value = islem.duzenleme_tarihi
        vade_tarihi.value = islem.vade_tarihi
        tutar.value = islem.tutar
        cari_id.value = islem.cari_id
        aciklama.value = islem.aciklama
        
        if yon == 'alinan':
            if islem.resim_on_path: cek_resmi.value = islem.resim_on_path
            kesideci_vkn.value = islem.kesideci_tc_vkn
            kesideci_unvan.value = islem.kesideci_unvan
            banka_adi.value = islem.banka_adi
            sube_adi.value = islem.sube_adi
            hesap_no.value = islem.hesap_no
            cek_no.value = islem.cek_no
            iban.value = islem.iban
            if islem.tur == 'SENET': kefil.value = islem.kefil
        
        elif yon == 'verilen' and islem.tur == 'CEK':
            # Verilen çekte banka hesabını bulma (İsteğe bağlı)
            # Eğer modelde banka_hesap_id tutmuyorsak banka adından eşleştirebiliriz
            if islem.banka_adi:
                for b in bankalar:
                    if b.banka_adi == islem.banka_adi and b.hesap_no == islem.hesap_no:
                        bizim_banka.value = b.id
                        break
    # ==========================================
    # ✅ KRİTİK EKLENTİ: VIEW MODE AYARI (Render'dan ÖNCE)
    # ==========================================
    # Alanların modunu layout çizilmeden önce ayarlamalıyız.
    # Aksi takdirde layout içindeki alanlar input olarak kalır veya hata verir.
    for f in fields_to_add:
        f.view_mode = view_only
    # ==========================================
    # 3.LAYOUT OLUŞTURMA
    # ==========================================
    
    layout.add_row(tur)
    layout.add_row(sys_no, fiziksel_no)
    
    if yon == 'alinan':
        layout.add_row(cek_resmi)
        
    layout.add_row(cari_id)
    
    if yon == 'verilen':
        layout.add_row(bizim_banka)
        
    layout.add_row(tarih, vade_tarihi, tutar)
    
    if yon == 'alinan':
        layout.add_card("Banka / Senet Detayları", [
            layout.create_row(banka_adi, sube_adi),
            layout.create_row(hesap_no, iban),
            # 2.AYRAÇ (Görsel düzgünlük için)
            layout.create_row(FormField('hr1', FieldType.HR, label='')),
            layout.create_row(cek_no),
            layout.create_row(kesideci_vkn, kesideci_unvan),
            layout.create_row(kefil)
        ])

    layout.add_row(aciklama)
    
    # Form Oluştur
    form.set_layout_html(layout.render())
    form.add_fields(*fields_to_add)
    
    return form
def create_cek_islem_form(cek):
    """
    Çek durumunu değiştirmek için (Tahsilat, Ciro, Ödeme vb.) işlem formu.
    """
    # Başlık: Çek No ve Tutar bilgisiyle
    # Eğer fiziksel no (cek_no) varsa onu, yoksa sistem nosunu göster
    belge_no_goster = cek.cek_no if cek.cek_no else cek.belge_no
    tutar_str = f"{float(cek.tutar):,.2f} TL"
    
    title = f"{'Senet' if cek.tur == 'SENET' else 'Çek'} İşlemi | No: {belge_no_goster} | {tutar_str}"
    
    form = Form(name="cek_islem_form", title=title, action=f"/cek/islem/{cek.id}", method="POST", submit_text=_("İşlemi Onayla"), ajax=True)
    layout = FormLayout()

    # --- Veri Hazırlığı ---
    kasalar = Kasa.query.filter_by(firma_id=current_user.firma_id).all()
    kasa_opts = [(str(k.id), k.ad) for k in kasalar]
    
    bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()
    banka_opts = [(str(b.id), f"{b.banka_adi} - {b.ad}") for b in bankalar]
    
    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
    cari_opts = [(str(c.id), c.unvan) for c in cariler]

    # --- İŞLEM SEÇENEKLERİ (Yöne Göre) ---
    if cek.portfoy_tipi == PortfoyTipi.ALINAN.value:
        islem_turleri = [
            (CekIslemTuru.TAHSIL_KASA.value, 'Elden Tahsilat (Kasaya Giriş)'),
            (CekIslemTuru.TAHSIL_BANKA.value, 'Bankadan Tahsilat (Hesaba Giriş)'),
            (CekIslemTuru.CIRO.value, 'Ciro Et (Satıcıya Ver)'),
            (CekIslemTuru.KARSILIKSIZ.value, 'Karşılıksız İşaretle')
        ]
    else: # VERILEN (Bizim Çek)
        islem_turleri = [
            (CekIslemTuru.ODENDI_KASA.value, 'Kasadan Ödendi (Nakit Çıkış)'),
            (CekIslemTuru.ODENDI_BANKA.value, 'Bankadan Ödendi (Hesaptan Çıkış)')
        ]

    # --- ALANLAR ---
    islem_turu = FormField('islem_turu', FieldType.SELECT, _('Yapılacak İşlem'), 
                           options=islem_turleri, required=True, 
                           select2_config={'placeholder': 'İşlem Seçiniz'})

    tarih = FormField('tarih', FieldType.DATE, _('İşlem Tarihi'), required=True, default_value='today')

    # --- KOŞULLU ALANLAR ---
    
    # 1.Kasa Seçimi (Eğer işlem KASA ise görünür)
    kasa_id = FormField('kasa_id', FieldType.SELECT, _('Kasa Seçimi'), 
                        options=kasa_opts,
                        select2_config={'placeholder': 'Kasa Seçiniz'},
                        conditional={'field': 'islem_turu', 'value': [CekIslemTuru.TAHSIL_KASA.value, CekIslemTuru.ODENDI_KASA.value]})

    # 2.Banka Seçimi (Eğer işlem BANKA ise görünür)
    banka_id = FormField('banka_id', FieldType.SELECT, _('Banka Seçimi'), 
                         options=banka_opts,
                         select2_config={'placeholder': 'Banka Seçiniz'},
                         conditional={'field': 'islem_turu', 'value': [CekIslemTuru.TAHSIL_BANKA.value, CekIslemTuru.ODENDI_BANKA.value]})

    # 3.Cari Seçimi (Sadece CIRO ise görünür)
    cari_id = FormField('cari_id', FieldType.SELECT, _('Verilecek Cari (Satıcı)'), 
                        options=cari_opts,
                        select2_config={'placeholder': 'Cari Seçiniz', 'search': True},
                        conditional={'field': 'islem_turu', 'value': CekIslemTuru.CIRO.value})

    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'), placeholder="İşlem detayı...", html_attributes={'rows': 2})

    # Layout Yerleşimi
    layout.add_alert("Bilgi", f"Bu çekin vadesi: <b>{cek.vade_tarihi.strftime('%d.%m.%Y')}</b>", "info", "bi-calendar-event")
    
    layout.add_row(islem_turu)
    layout.add_row(tarih)
    
    # Koşullu alanlar alt alta gelsin
    layout.add_row(kasa_id)
    layout.add_row(banka_id)
    layout.add_row(cari_id)
    
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(islem_turu, tarih, kasa_id, banka_id, cari_id, aciklama)
    
    return form
