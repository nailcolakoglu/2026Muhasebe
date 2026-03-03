# app/modules/crm/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask import url_for
from flask_babel import gettext as _
from flask_login import current_user
from app.enums import CrmAdayDurumu, CrmFirsatAsamasi, CrmAktiviteTipi
from app.extensions import get_tenant_db
from app.modules.kullanici.models import Kullanici

from app.modules.crm.models import AdayMusteri, SatisAsamasi
from app.modules.cari.models import CariHesap

def get_asama_options():
    """Veritabanındaki dinamik aşamaları form için getirir."""
    tenant_db = get_tenant_db()
    # Sadece o firmaya ait aşamaları sırasına göre al
    asamalar = tenant_db.query(SatisAsamasi).filter_by(firma_id=current_user.firma_id).order_by(SatisAsamasi.sira).all()
    return [('', _('Seçiniz...'))] + [(a.id, a.ad) for a in asamalar]

def get_aday_options():
    tenant_db = get_tenant_db()
    adaylar = tenant_db.query(AdayMusteri).filter_by(firma_id=current_user.firma_id).all()
    return [('', 'Aday Seçiniz...')] + [(a.id, a.unvan) for a in adaylar]

def get_cari_options():
    tenant_db = get_tenant_db()
    cariler = tenant_db.query(CariHesap).filter_by(firma_id=current_user.firma_id).all()
    return [('', 'Mevcut Cari Seçiniz...')] + [(c.id, c.unvan) for c in cariler]

def create_firsat_form(firsat=None):
    is_edit = firsat is not None
    action_url = f"/crm/firsat/duzenle/{firsat.id}" if is_edit else "/crm/firsat/ekle"
    title = _("Fırsat Düzenle") if is_edit else _("Yeni Satış Fırsatı")
    
    form = Form(name="firsat_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    #asama_opts = [(e.name, e.value) for e in CrmFirsatAsamasi]
    asama_opts = get_asama_options()
    
    baslik = FormField('baslik', FieldType.TEXT, _('Fırsat Başlığı (Örn: 2026 Lisans Yenileme)'), required=True, value=firsat.baslik if firsat else '')
    aday = FormField('aday_id', FieldType.SELECT, _('Aday Müşteri (Varsa)'), options=get_aday_options(), value=firsat.aday_id if firsat else '', select2_config={'search': True})
    cari = FormField('cari_id', FieldType.SELECT, _('Mevcut Cari (Varsa)'), options=get_cari_options(), value=firsat.cari_id if firsat else '', select2_config={'search': True})
    
    tutar = FormField('tahmini_tutar', FieldType.CURRENCY, _('Tahmini Tutar'), value=float(firsat.tahmini_tutar) if firsat and firsat.tahmini_tutar else 0)
    para_birimi = FormField('para_birimi', FieldType.SELECT, _('Döviz'), options=[('TL', 'TL'), ('USD', 'USD'), ('EUR', 'EUR')], value=firsat.para_birimi if firsat else 'TL')
    
    olasilik = FormField('ai_olasilik', FieldType.NUMBER, _('Kazanma Olasılığı (%)'), value=firsat.ai_olasilik if firsat else 10, html_attributes={'min': 0, 'max': 100})
    kapanis = FormField('beklenen_kapanis_tarihi', FieldType.DATE, _('Beklenen Kapanış Tarihi'), value=firsat.beklenen_kapanis_tarihi if firsat else '')
    
    asama = FormField('asama_id', FieldType.SELECT, _('Satış Aşaması'), 
                        options=asama_opts, required=True, value=firsat.asama_id if firsat else '')
    temsilci = FormField('temsilci_id', FieldType.SELECT, _('Sorumlu Temsilci'), options=[('', 'Seçiniz...')] + get_temsilci_options(), value=firsat.temsilci_id if firsat else current_user.id)

    kaybedilme_nedeni = FormField('kaybedilme_nedeni', FieldType.TEXT, _('Kaybedilme Nedeni (Sadece iptalse)'), value=firsat.kaybedilme_nedeni if firsat else '')

    layout.add_row(baslik)
    layout.add_row(aday, cari)
    layout.add_row(tutar, para_birimi, olasilik)
    layout.add_row(asama, kapanis, temsilci)
    layout.add_row(kaybedilme_nedeni)

    form.set_layout_html(layout.render())
    form.add_fields(baslik, aday, cari, tutar, para_birimi, olasilik, kapanis, asama, temsilci, kaybedilme_nedeni)
    
    return form

def create_aktivite_form(aktivite=None):
    is_edit = aktivite is not None
    action_url = f"/crm/aktivite/duzenle/{aktivite.id}" if is_edit else "/crm/aktivite/ekle"
    title = _("Aktivite Düzenle") if is_edit else _("Yeni Aktivite/Görüşme")
    
    form = Form(name="aktivite_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    tip_opts = [(e.name, e.value) for e in CrmAktiviteTipi]

    konu = FormField('konu', FieldType.TEXT, _('Görüşme/Aktivite Konusu'), required=True, value=aktivite.konu if aktivite else '')
    tip = FormField('aktivite_tipi', FieldType.SELECT, _('Aktivite Tipi'), options=tip_opts, required=True, value=aktivite.aktivite_tipi.name if aktivite and hasattr(aktivite.aktivite_tipi, 'name') else 'TELEFON')
    
    # DATETIME-LOCAL type builder destekliyorsa kullanılır, yoksa DATE kullanılır
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=aktivite.tarih.strftime('%Y-%m-%d') if aktivite and aktivite.tarih else '')
    
    aday = FormField('aday_id', FieldType.SELECT, _('İlgili Aday'), options=get_aday_options(), value=aktivite.aday_id if aktivite else '')
    cari = FormField('cari_id', FieldType.SELECT, _('İlgili Cari'), options=get_cari_options(), value=aktivite.cari_id if aktivite else '')
    
    tamamlandi = FormField('tamamlandi', FieldType.CHECKBOX, _('Bu aktivite tamamlandı mı?'), value=aktivite.tamamlandi if aktivite else False)
    notlar = FormField('notlar', FieldType.TEXTAREA, _('Görüşme Notları'), value=aktivite.notlar if aktivite else '', html_attributes={'rows': 4})

    layout.add_row(konu, tip)
    layout.add_row(tarih, tamamlandi)
    layout.add_row(aday, cari)
    layout.add_row(notlar)

    form.set_layout_html(layout.render())
    form.add_fields(konu, tip, tarih, aday, cari, tamamlandi, notlar)
    
    return form
    
def get_temsilci_options():
    """Satış temsilcilerini (kullanıcıları) getirir"""
    tenant_db = get_tenant_db()
    kullanicilar = tenant_db.query(Kullanici).filter_by(firma_id=current_user.firma_id, aktif=True).all()
    return [(k.id, k.ad_soyad) for k in kullanicilar]

def create_aday_form(aday=None):
    is_edit = aday is not None
    action_url = f"/crm/aday/duzenle/{aday.id}" if is_edit else "/crm/aday/ekle"
    title = _("Aday Müşteri Düzenle") if is_edit else _("Yeni Aday Müşteri")
    
    form = Form(name="aday_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    durum_opts = [(e.name, e.value) for e in CrmAdayDurumu]
    temsilci_opts = [('', 'Seçiniz...')] + get_temsilci_options()

    unvan = FormField('unvan', FieldType.TEXT, _('Firma/Kişi Ünvanı'), required=True, value=aday.unvan if aday else '')
    yetkili = FormField('yetkili_kisi', FieldType.TEXT, _('Yetkili Kişi'), value=aday.yetkili_kisi if aday else '')
    telefon = FormField('telefon', FieldType.TEXT, _('Telefon'), value=aday.telefon if aday else '')
    eposta = FormField('eposta', FieldType.EMAIL, _('E-Posta'), value=aday.eposta if aday else '')
    
    sektor = FormField('sektor', FieldType.TEXT, _('Sektör'), value=aday.sektor if aday else '')
    kaynak = FormField('kaynak', FieldType.SELECT, _('Geliş Kaynağı'), options=[('Web', 'Web Sitesi'), ('Referans', 'Referans'), ('Soğuk Arama', 'Soğuk Arama'), ('Fuar', 'Fuar')], value=aday.kaynak if aday else 'Web')
    
    durum = FormField('durum', FieldType.SELECT, _('Aday Durumu'), options=durum_opts, required=True, value=aday.durum.name if aday and hasattr(aday.durum, 'name') else 'YENI')
    temsilci = FormField('temsilci_id', FieldType.SELECT, _('Atanan Temsilci'), options=temsilci_opts, value=aday.temsilci_id if aday else current_user.id)
    
    notlar = FormField('notlar', FieldType.TEXTAREA, _('Notlar/Detaylar'), value=aday.notlar if aday else '')

    layout.add_row(unvan, yetkili)
    layout.add_row(telefon, eposta)
    layout.add_row(sektor, kaynak)
    layout.add_row(durum, temsilci)
    layout.add_row(notlar)

    form.set_layout_html(layout.render())
    form.add_fields(unvan, yetkili, telefon, eposta, sektor, kaynak, durum, temsilci, notlar)
    
    return form
    
from app.modules.crm.models import IslemTuruEnum, DuyguDurumuEnum

def create_crm_hareketi_form(hareket=None):
    is_edit = hareket is not None
    action_url = f"/crm/hareket/duzenle/{hareket.id}" if is_edit else "/crm/hareket/ekle"
    title = _("Etkileşim Düzenle") if is_edit else _("Yeni Müşteri Etkileşimi / Görüşme")
    
    form = Form(name="hareket_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    islem_opts = [(e.name, e.name) for e in IslemTuruEnum]
    duygu_opts = [(e.name, e.name) for e in DuyguDurumuEnum]

    cari = FormField('cari_id', FieldType.SELECT, _('İlgili Cari'), options=get_cari_options(), required=True, value=hareket.cari_id if hareket else '')
    islem = FormField('islem_turu', FieldType.SELECT, _('İşlem Türü'), options=islem_opts, required=True, value=hareket.islem_turu.name if hareket and hasattr(hareket.islem_turu, 'name') else 'ARAMA')
    tarih = FormField('tarih', FieldType.DATE, _('Tarih'), required=True, value=hareket.tarih.strftime('%Y-%m-%d') if hareket and hareket.tarih else '')
    
    konu = FormField('konu', FieldType.TEXT, _('Konu / Başlık'), required=True, value=hareket.konu if hareket else '')
    notlar = FormField('detay_notu', FieldType.TEXTAREA, _('Görüşme Detayları'), value=hareket.detay_notu if hareket else '', html_attributes={'rows': 4})
    
    duygu = FormField('duygu_durumu', FieldType.SELECT, _('Müşteri Duygu Durumu (Manuel/AI)'), options=duygu_opts, value=hareket.duygu_durumu.name if hareket and hasattr(hareket.duygu_durumu, 'name') else 'BELIRSIZ')
    skor = FormField('memnuniyet_skoru', FieldType.NUMBER, _('Memnuniyet Skoru (1-10)'), value=hareket.memnuniyet_skoru if hareket else 5, html_attributes={'min': 1, 'max': 10})
    
    aksiyon = FormField('aksiyon_gerekli', FieldType.CHECKBOX, _('Aksiyon / Geri Dönüş Gerekli mi?'), value=hareket.aksiyon_gerekli if hareket else False)
    aksiyon_tar = FormField('aksiyon_tarihi', FieldType.DATE, _('Aksiyon Tarihi'), value=hareket.aksiyon_tarihi.strftime('%Y-%m-%d') if hareket and hareket.aksiyon_tarihi else '')

    layout.add_row(cari, islem, tarih)
    layout.add_row(konu)
    layout.add_row(notlar)
    layout.add_row(duygu, skor)
    layout.add_row(aksiyon, aksiyon_tar)

    form.set_layout_html(layout.render())
    form.add_fields(cari, islem, tarih, konu, notlar, duygu, skor, aksiyon, aksiyon_tar)
    
    return form