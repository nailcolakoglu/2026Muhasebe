from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import SelectField, FileField, StringField, DecimalField, IntegerField
from wtforms.validators import DataRequired
from flask_login import current_user
from app.modules.kasa.models import Kasa
from app.modules.muhasebe.models import HesapPlani
from app.modules.cari.models import CariHesap
from app.modules.banka.models import BankaHesap
# Eğer BankaImportSablon modelini modules/banka_import/models.py içine koyduysanız:
# from modules.banka_import.models import BankaImportSablon 
# Eğer ana models.py içindeyse:
from app.modules.banka_import.models import BankaImportSablon

# ---------------------------------------------------------
# 1.BANKA IMPORT (YÜKLEME) FORMU
# ---------------------------------------------------------
class BankaImportForm(FlaskForm):
    """
    Excel Yükleme ve Parametre Seçim Formu
    """
    banka_id = SelectField('Banka Hesabı', validators=[DataRequired()], coerce=int)
    sablon_id = SelectField('Excel Şablonu', validators=[DataRequired()], coerce=int)
    
    excel_file = FileField('Banka Ekstresi (Excel)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls'], 'Sadece Excel dosyaları yüklenebilir!')
    ])

    def __init__(self, *args, **kwargs):
        super(BankaImportForm, self).__init__(*args, **kwargs)
        self.banka_id.choices = [
            (b.id, f"{b.banka_adi} - {b.ad} ({b.doviz_turu})") 
            for b in BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()
        ]
        
        self.sablon_id.choices = [
            (s.id, f"{s.banka_adi} Şablonu") 
            for s in BankaImportSablon.query.filter_by(firma_id=current_user.firma_id).all()
        ]

# ---------------------------------------------------------
# 2.KURAL TANIMLAMA FORMU
# ---------------------------------------------------------
class BankaImportKuraliForm(FlaskForm):
    """
    Yeni Eşleştirme Kuralı Ekleme Formu
    """
    anahtar_kelime = StringField('Anahtar Kelime', validators=[DataRequired()], render_kw={"placeholder": "Örn: GEDIZ, TURKCELL, POS"})
    
    kural_tipi = SelectField('İşlem Tipi', choices=[
        ('standart', 'Standart İşlem (Havale/EFT)'),
        ('pos_net', 'POS Tahsilat (Bankaya Net Yatan)')
    ], default='standart')
    
    hedef_turu = SelectField('Hedef Türü', choices=[
        ('cari', 'Cari Hesap'),
        ('muhasebe', 'Muhasebe Hesabı')
    ], default='cari')
    
    hedef_cari_id = SelectField('Cari Hesap', coerce=int, validators=[])
    hedef_muhasebe_id = SelectField('Muhasebe Hesabı', coerce=int, validators=[])
    
    varsayilan_komisyon_orani = DecimalField('Komisyon Oranı (%)', default=0, places=2)
    komisyon_gider_hesap_id = SelectField('Komisyon Gider Hesabı (780)', coerce=int, validators=[])

    def __init__(self, *args, **kwargs):
        super(BankaImportKuraliForm, self).__init__(*args, **kwargs)
        
        # Carileri Doldur
        self.hedef_cari_id.choices = [(0, 'Seçiniz...')] + [
            (c.id, c.unvan) for c in CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
        ]
        
        # Muhasebe Hesaplarını Doldur
        muhasebe_listesi = [(0, 'Seçiniz...')] + [
            (h.id, f"{h.kod} - {h.ad}") for h in HesapPlani.query.filter_by(firma_id=current_user.firma_id).all()
        ]
        self.hedef_muhasebe_id.choices = muhasebe_listesi
        
        # ✅ DÜZELTME BURADA:
        # self.hedef_muhasebe_id (Field) DEĞİL, self.hedef_muhasebe_id.choices (Liste) atanmalıydı.
        # Ya da yukarıdaki 'muhasebe_listesi' değişkenini direkt atayabiliriz.
        self.komisyon_gider_hesap_id.choices = muhasebe_listesi    
    
class BankaImportSablonForm(FlaskForm):
    """
    Excel Sütun Eşleştirme Şablonu
    """
    banka_adi = StringField('Şablon Adı', validators=[DataRequired()], render_kw={"placeholder": "Örn: Garanti Bankası Exceli"})
    baslangic_satiri = IntegerField('Başlangıç Satırı', default=2, validators=[DataRequired()])
    
    col_tarih = StringField('Tarih Sütunu', validators=[DataRequired()], render_kw={"placeholder": "Tarih"})
    col_aciklama = StringField('Açıklama Sütunu', validators=[DataRequired()], render_kw={"placeholder": "Açıklama"})
    col_belge_no = StringField('Belge No Sütunu', render_kw={"placeholder": "Dekont No"})
    
    tutar_yapis_tipi = SelectField('Tutar Sütun Yapısı', choices=[
        ('tek', 'Tek Sütun (+/- Birlikte)'),
        ('cift', 'Çift Sütun (Borç ve Alacak Ayrı)')
    ], default='tek')
    
    col_tutar = StringField('Tutar Sütunu', render_kw={"placeholder": "Tutar"})
    col_borc = StringField('Borç (Giriş) Sütunu', render_kw={"placeholder": "Yatan"})
    col_alacak = StringField('Alacak (Çıkış) Sütunu', render_kw={"placeholder": "Çekilen"})
    
    tarih_formati = StringField('Tarih Formatı', default='%d.%m.%Y', render_kw={"placeholder": "%d.%m.%Y"})
