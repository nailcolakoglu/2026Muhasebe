# modules/cek/routes.py (Tamamı)

from flask import Blueprint, render_template, request, jsonify, session, current_app, render_template_string
from flask_login import login_required, current_user
from app.extensions import db
from app.modules.cek.models import CekSenet
from app.modules.cari.models import CariHesap, CariHareket
from app.modules.kasa.models import Kasa
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.modules.banka.models import BankaHesap
from app.form_builder import DataGrid, FieldType
from datetime import datetime
from .forms import create_cek_form, create_cek_islem_form
import os
from werkzeug.utils import secure_filename
from decimal import Decimal
from app.form_builder.kanban import KanbanBoard
from app.form_builder.pivot import PivotEngine
from app.enums import CekDurumu, PortfoyTipi, CekIslemTuru, CekKonumu, CariIslemTuru

def cek_to_dict(cekler):
    """
    Çek nesnelerini güvenli bir şekilde sözlüğe çevirir.
    Hata almamak için if/else kontrolleri eklenmiştir.
    """
    data_list = []
    for c in cekler:
        item = {
            'id': c.id,
            'cek_durumu': c.cek_durumu, # Örn: 'portfoyde'
            'cari_unvan': c.cari.unvan if c.cari else 'Cari Yok',
            'banka_adi': c.banka_adi if c.banka_adi else (c.banka.banka_adi if c.banka else '-'),
            'tutar': float(c.tutar),
            'vade_tarihi': c.vade_tarihi.strftime('%d.%m.%Y') if c.vade_tarihi else '-',
            'belge_no': c.belge_no
        }
        data_list.append(item)

    return data_list

# Helper: Para Birimi
def parse_decimal(value):
    if not value: return Decimal(0)
    if isinstance(value, (int, float)): return Decimal(value)
    clean_val = str(value).replace('.', '').replace(',', '.')
    try: return Decimal(clean_val)
    except: return Decimal(0)

def save_uploaded_file(file_obj, subfolder='cekler'):
    """Dosyayı güvenli bir şekilde kaydeder ve path döner"""
    if not file_obj or file_obj.filename == '':
        return None
    
    filename = secure_filename(f"{int(datetime.now().timestamp())}_{file_obj.filename}")
    # static/uploads/cekler klasörüne kaydet
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', subfolder)
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, filename)
    file_obj.save(file_path)
    
    # DB'ye kaydedilecek path (static/ olmadan, çünkü render ederken ekliyoruz veya tam yol)
    # FormField _render_image metodu '/static/' ekliyor mu kontrol etmiştik.
    # Genelde 'uploads/cekler/dosya.jpg' olarak kaydetmek en iyisidir.
    return f"uploads/{subfolder}/{filename}"

# Helper: Cari Bakiye Güncelle
def update_cari_bakiye(cari_id, tutar, yon, is_reverse=False):
    if not cari_id: return
    cari = CariHesap.query.get(cari_id)
    if not cari: return
    
    val = float(tutar)
    if is_reverse: val = -val
    
    if yon == 'alinan':
        # Müşteriden çek aldık -> Müşteri borcu düştü (Alacaklandı)
        cari.alacak_bakiye = float(cari.alacak_bakiye or 0) + val
    elif yon == 'verilen':
        # Tedarikçiye çek verdik -> Bizim borcumuz düştü (Borçlandırdık/Ödedik)
        cari.borc_bakiye = float(cari.borc_bakiye or 0) - val # Borç azalır
        
    db.session.add(cari)

cek_bp = Blueprint('cek', __name__)

@cek_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    # Benzersiz bir portföy numarası üret
    yil = datetime.now().year
    son = CekSenet.query.filter_by(firma_id=current_user.firma_id).count()
    # Örn: P-2025-000001
    return jsonify({'code': f"P-{yil}-{str(son+1).zfill(6)}"})

@cek_bp.route('/')
@login_required
def index():
    grid = DataGrid("cek_list", CekSenet, "Kıymetli Evrak Portföyü")
    
    # Sistem No (Portföy) ve Fiziksel No'yu ayrı gösterelim
    grid.add_column('belge_no', 'Portföy No', width='120px') # Sistem No
    grid.add_column('cek_no', 'Asıl Belge No', width='100px') # Kağıt No
    
    grid.add_column('tur', 'Tür', type='badge', badge_colors={'CEK': 'info', 'SENET': 'warning'})
    grid.add_column('portfoy_tipi', 'Yön', type='badge', badge_colors={'alinan': 'success', 'verilen': 'danger'})
    grid.add_column('cari.unvan', 'Cari Hesap')
    grid.add_column('vade_tarihi', 'Vade', type= FieldType.TARIH )
    grid.add_column('tutar', 'Tutar', type= FieldType.CURRENCY)
    grid.add_column('cek_durumu', 'Durum', type='badge', 
                    badge_colors={'portfoyde': 'primary', 'tahsil_edildi': 'success', 'odendi': 'secondary', 'karsiliksiz': 'dark'})
    
    grid.add_action('islem', 'İşlem', 'bi bi-gear-fill', 'btn-warning btn-sm', 'route', 'cek.islem')
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'cek.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'cek.sil')
    grid.add_action('print', 'Yazdır', 'bi bi-printer', 'btn-outline-secondary btn-sm', 
                    'url', lambda row: f"/cek/yazdir/{row.id}", 
                    html_attributes={'target': '_blank'})
    query = CekSenet.query.filter_by(firma_id=current_user.firma_id).order_by(CekSenet.vade_tarihi.asc())
    grid.process_query(query)
    
    grid.hide_column('id').hide_column('firma_id').hide_column('cari.id').hide_column('finans_islem_id')
    grid.hide_column('tahsil_tarihi').hide_column('kalan_gun').hide_column('vade_grubu').hide_column('doviz_cinsi')
    grid.hide_column('kur').hide_column('iskonto_oranı').hide_column('net_tahsilat_tutarı').hide_column('banka_komisyonu')
    grid.hide_column('tahsilat_olasiligi').hide_column('ciranta_adi').hide_column('risk_seviyesi').hide_column('risk_puani')
    grid.hide_column('resim_on_path').hide_column('resim_arka_path').hide_column('ocr_ham_veri').hide_column('fiziksel_yeri')
    grid.hide_column('iskonto_orani').hide_column('protesto_masrafi').hide_column('ciranta_sayisi').hide_column('ai_onerisi')
    grid.hide_column('seri_no').hide_column('cari_id').hide_column('net_tahsilat_tutari').hide_column('tahsilat_tahmini_tarihi')
    grid.hide_column('gecikme_gunu').hide_column('aciklama').hide_column('olusturma_tarihi').hide_column('duzenleme_tarihi')
    grid.hide_column('sonuc_durumu').hide_column('aciklama').hide_column('olusturma_tarihi').hide_column('iban')
    grid.hide_column('kesideci_tc_vkn').hide_column('cek_no').hide_column('hesap_no').hide_column('kefil')
    
    # --- DASHBOARD HESAPLAMALARI (GÜNCELLENDİ) ---
    tum_kayitlar = query.all()
    
    # 1.Portföydeki Alınan Çekler (Alacaklarımız)
    toplam_alinan_cek = sum(float(c.tutar) for c in tum_kayitlar 
                            if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'alinan' and c.tur == 'CEK')

    # 2.Portföydeki Alınan Senetler (Alacaklarımız)
    toplam_alinan_senet = sum(float(c.tutar) for c in tum_kayitlar 
                              if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'alinan' and c.tur == 'SENET')

    # 3.Verilen Çekler (Borçlarımız - Ödenmemiş)
    toplam_verilen_cek = sum(float(c.tutar) for c in tum_kayitlar 
                             if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'verilen' and c.tur == 'CEK')

    # 4.Verilen Senetler (Borçlarımız - Ödenmemiş)
    toplam_verilen_senet = sum(float(c.tutar) for c in tum_kayitlar 
                               if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'verilen' and c.tur == 'SENET')
    # ...(Önceki 4'lü kart hesaplamaları burada bitiyor) ...
    
    # --- GRAFİK VERİSİ HAZIRLIĞI (YENİ) ---
    import json
    
    # 1.Pasta Grafik: Portföy Dağılımı (Çek vs Senet)
    # Sadece elimizdeki (portfoyde) evraklar
    portfoydeki_evraklar = [c for c in tum_kayitlar if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'alinan']
    
    cek_toplam = sum(float(c.tutar) for c in portfoydeki_evraklar if c.tur == 'CEK')
    senet_toplam = sum(float(c.tutar) for c in portfoydeki_evraklar if c.tur == 'SENET')
    
    pie_data = {
        'labels': ['Çek', 'Senet'],
        'data': [cek_toplam, senet_toplam]
    }

    # 2.Çubuk Grafik: Aylık Tahsilat Planı (Önümüzdeki 6 Ay)
    # Vade tarihine göre gruplama
    from collections import defaultdict
    aylik_toplamlar = defaultdict(float)
    
    for c in portfoydeki_evraklar:
        # Anahtar: "2025-10" formatında Yıl-Ay
        anahtar = c.vade_tarihi.strftime('%Y-%m')
        aylik_toplamlar[anahtar] += float(c.tutar)
    
    # Sözlüğü sırala ve listelere ayır
    sirali_aylar = sorted(aylik_toplamlar.keys())
    bar_labels = [] # ["Ekim 2025", "Kasım 2025"]
    bar_values = [] # [100000, 50000]
    
    # Ay isimleri için basit sözlük
    ay_isimleri = {'01':'Ocak', '02':'Şubat', '03':'Mart', '04':'Nisan', '05':'Mayıs', '06':'Haziran', 
                   '07':'Temmuz', '08':'Ağustos', '09':'Eylül', '10':'Ekim', '11':'Kasım', '12':'Aralık'}

    for ay_kodu in sirali_aylar:
        yil, ay = ay_kodu.split('-')
        bar_labels.append(f"{ay_isimleri.get(ay)} {yil}")
        bar_values.append(aylik_toplamlar[ay_kodu])

    bar_data = {
        'labels': bar_labels,
        'data': bar_values
    }

    return render_template('cek/index.html', grid=grid, 
                           toplam_alinan_cek=toplam_alinan_cek,
                           toplam_alinan_senet=toplam_alinan_senet,
                           toplam_verilen_cek=toplam_verilen_cek,
                           toplam_verilen_senet=toplam_verilen_senet,
                           # Grafikler için JSON string olarak gönderiyoruz
                           pie_chart_data=json.dumps(pie_data),
                           bar_chart_data=json.dumps(bar_data)
                           )

@cek_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    yon = request.args.get('yon', 'alinan')
    form = create_cek_form(yon=yon)
    
    if request.method == 'POST':
        form.process_request(request.form, request.files)
        
        if form.validate():
            try:
                data = form.get_data()
                
                # ✅ DÜZELTME 1: Çek Numarasını Güvenli Al (Yoksa None olsun)
                gelen_cek_no = data.get('cek_no')

                # ✅ DÜZELTME 2: Mükerrer Kontrolü (Sadece numara varsa yap)
                if gelen_cek_no:
                    mevcut = CekSenet.query.filter_by(
                        firma_id=current_user.firma_id,
                        cek_no=gelen_cek_no,
                        portfoy_tipi=yon
                    ).first()
                    
                    if mevcut:
                        return jsonify({'success': False, 'message': f"Bu seri numarasıyla ({gelen_cek_no}) bir kayıt zaten var!"}), 400

                # 3.NESNE OLUŞTURMA
                yeni_cek = CekSenet(
                    firma_id=current_user.firma_id,
                    portfoy_tipi=yon,
                    tur=data['tur'],
                    
                    belge_no=data['sys_belge_no'], 
                    cek_no=gelen_cek_no,           # ✅ DÜZELTME 3: Güvenli değişkeni kullan
                    seri_no=data.get('seri_no'),   
                    
                    cari_id=data['cari_id'],
                    vade_tarihi=datetime.strptime(data['vade_tarihi'], '%Y-%m-%d').date(),
                    tutar=parse_decimal(data['tutar']),
                    aciklama=data.get('aciklama'),
                    duzenleme_tarihi=datetime.strptime(data['duzenleme_tarihi'], '%Y-%m-%d').date(),
                    cek_durumu='portfoyde'
                )
                
                # --- A) ALINAN EVRAK DETAYLARI ---
                if yon == 'alinan':
                    # ...(Mevcut kodlar aynı) ...
                    yeni_cek.resim_on_path = save_uploaded_file(request.files['cek_resmi']) if 'cek_resmi' in request.files else None
                    yeni_cek.kesideci_tc_vkn = data.get('kesideci_tc_vkn')
                    yeni_cek.kesideci_unvan = data.get('kesideci_unvan')
                    yeni_cek.banka_adi = data.get('banka_adi')
                    yeni_cek.sube_adi = data.get('sube_adi')
                    yeni_cek.hesap_no = data.get('hesap_no')
                    yeni_cek.iban = data.get('iban')
                    
                    if data['tur'] == 'SENET':
                        yeni_cek.kefil = data.get('kefil')
                        
                    yeni_cek.risk_analizi_yap()

                # --- B) VERİLEN EVRAK DETAYLARI ---
                elif yon == 'verilen':
                    if data['tur'] == 'CEK' and data.get('banka_hesap_id'):
                        bizim_banka = BankaHesap.query.get(data['banka_hesap_id'])
                        if bizim_banka:
                            yeni_cek.banka_adi = bizim_banka.banka_adi
                            yeni_cek.sube_adi = bizim_banka.sube_adi
                            yeni_cek.hesap_no = bizim_banka.hesap_no
                            yeni_cek.iban = bizim_banka.iban
                            
                            # Eğer kullanıcı "Asıl Belge No" girmediyse, Bankadan otomatik çekebiliriz (Opsiyonel)
                            # if not gelen_cek_no: yeni_cek.cek_no = bizim_banka.siradaki_cek_no
                            
                            yeni_cek.kesideci_unvan = current_user.firma.unvan

                db.session.add(yeni_cek)
                update_cari_bakiye(yeni_cek.cari_id, yeni_cek.tutar, yon)
                db.session.commit()
                
                return jsonify({'success': True, 'message': 'Kayıt başarılı.'})
                
            except Exception as e:
                db.session.rollback()
                # Hata detayını görmek için loglayabilirsiniz
                print(f"HATA: {e}") 
                return jsonify({'success': False, 'message': str(e)}), 500
    
    return render_template('cek/form.html', form=form)
# ...(Silme, Düzenleme, İşlem rotaları önceki ile aynı mantıkta devam eder) ...
@cek_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    cek = CekSenet.query.get_or_404(id)
    if cek.cek_durumu != 'portfoyde':
        return jsonify({'success': False, 'message': 'İşlem görmüş kayıt silinemez!'}), 400
    try:
        update_cari_bakiye(cek.cari_id, cek.tutar, cek.portfoy_tipi, is_reverse=True)
        db.session.delete(cek)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Silindi.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- DÜZENLEME ROTASI ---
@cek_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    cek = CekSenet.query.get_or_404(id)
    
    # Güvenlik: Sadece portföydeki (işlem görmemiş) çekler düzenlenebilir
    if cek.cek_durumu != 'portfoyde':
        return render_template('hata.html', mesaj="İşlem görmüş çek/senet düzenlenemez! Önce işlemi iptal ediniz."), 403

    # Formu, çekin yönüne (alinan/verilen) göre oluştur
    form = create_cek_form(yon=cek.portfoy_tipi, islem=cek)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                # 1.Eski bakiyeyi geri al (Ters işlem: Alınansa borçlandır, verilense alacaklandır)
                update_cari_bakiye(cek.cari_id, cek.tutar, cek.portfoy_tipi, is_reverse=True)
                
                data = form.get_data()

                # Resim Güncelleme (Yeni resim varsa)
                if 'cek_resmi' in request.files and request.files['cek_resmi'].filename != '':
                    yeni_yol = save_uploaded_file(request.files['cek_resmi'])
                    if yeni_yol:
                        cek.resim_on_path = yeni_yol 

                # 2.Alanları Güncelle
                cek.tur = data['tur']
                cek.belge_no = data['sys_belge_no'] # Sistem No
                cek.cek_no = data['cek_no']         # Fiziksel No 
                cek.seri_no = data.get('seri_no')
                cek.vade_tarihi = datetime.strptime(data['vade_tarihi'], '%Y-%m-%d').date()
                cek.tutar = parse_decimal(data['tutar'])
                cek.cari_id = data['cari_id']
                cek.aciklama = data['aciklama']
                
                if cek.portfoy_tipi == 'alinan':
                    cek.banka_adi = data.get('banka_adi')
                    cek.sube_adi = data.get('sube_adi')
                    cek.hesap_no = data.get('hesap_no')
                    cek.iban = data.get('iban')
                    cek.kesideci_tc_vkn = data.get('kesideci_tc_vkn')
                    cek.kesideci_unvan = data.get('kesideci_unvan')
                    if cek.tur == 'SENET':
                        cek.kefil = data.get('kefil')
                
                # 3.Yeni bakiyeyi işle
                update_cari_bakiye(cek.cari_id, cek.tutar, cek.portfoy_tipi)
                
                db.session.commit()
                return jsonify({'success': True, 'message': 'Kayıt başarıyla güncellendi.', 'redirect': '/cek'})
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
                
    return render_template('cek/form.html', form=form)

# --- İŞLEM ROTASI (Tahsilat, Ciro, Ödeme) ---
@cek_bp.route('/islem/<int:id>', methods=['GET', 'POST'])
@login_required
def islem(id):
    cek = CekSenet.query.get_or_404(id)
    
    # Zaten işlem gördüyse hata ver (Sadece GET isteğinde, POST'ta JSON dön)
    if cek.cek_durumu != 'portfoyde':
        msg = "Bu evrak zaten işlem görmüş (Tahsil/Ciro edilmiş)."
        if request.method == 'POST':
            return jsonify({'success': False, 'message': msg}), 400
        return render_template('hata.html', mesaj=msg)
    
    # İşlem Formunu Oluştur
    form = create_cek_islem_form(cek)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                islem_turu = data['islem_turu']
                tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
                aciklama = data['aciklama']
                
                # Aktif Dönemi Bul
                donem = Donem.query.filter_by(firma_id=current_user.firma_id, aktif=True).first()
                donem_id = donem.id if donem else None

                # === İŞLEM MANTIĞI ===
                
                # 1.KASADAN TAHSİLAT (Alınan Çek -> Kasa)
                if islem_turu == CekIslemTuru.TAHSIL_KASA.value:
                    kasa_har = KasaHareket(
                        firma_id=cek.firma_id, 
                        donem_id=donem_id,
                        kasa_id=data['kasa_id'],
                        islem_turu='tahsilat',
                        belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, 
                        tutar=cek.tutar,
                        aciklama=f"Çek Tahsilatı ({cek.cek_no}) - {aciklama}", 
                        onaylandi=True
                    )
                    db.session.add(kasa_har)
                    cek.cek_durumu = CekDurumu.TAHSIL_EDILDI.value
                    cek.tahsil_tarihi = tarih

                # 2.BANKADAN TAHSİLAT (Alınan Çek -> Banka)
                elif islem_turu == CekIslemTuru.TAHSIL_BANKA.value:
                    banka_har = BankaHareket(
                        firma_id=cek.firma_id, 
                        donem_id=donem_id,
                        banka_id=data['banka_id'],
                        islem_turu='tahsilat',
                        belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, 
                        tutar=cek.tutar,
                        aciklama=f"Çek Tahsilatı ({cek.cek_no}) - {aciklama}"
                    )
                    db.session.add(banka_har)
                    cek.cek_durumu = CekDurumu.TAHSIL_EDILDI.value
                    cek.tahsil_tarihi = tarih

                # 3.CİRO (Alınan Çek -> Başka Cari'ye Ödeme)
                elif islem_turu == CekIslemTuru.CIRO.value:
                    satici_id = data['cari_id']
                    satici = CariHesap.query.get(satici_id)
                    
                    # Satıcıya ödeme yaptık -> Satıcının borcu azaldı (Borç Bakiye Düşer)
                    # Not: Cari Hesap mantığında 'borç_bakiye' bizim ona olan borcumuzdur.
                    if satici:
                        satici.borc_bakiye = float(satici.borc_bakiye or 0) - float(cek.tutar)
                        db.session.add(satici)
                        
                        cek.cek_durumu = CekDurumu.CIRO.value
                        cek.ciranta_adi = satici.unvan
                        cek.aciklama += f" | Ciro Edilen: {satici.unvan}"

                # 4.KARŞILIKSIZ (Geri İade / Sorunlu)
                elif islem_turu == CekIslemTuru.KARSILIKSIZ.value:
                    # Müşteri bakiyesini eski haline getir (Borçlandır)
                    update_cari_bakiye(cek.cari_id, cek.tutar, cek.portfoy_tipi, is_reverse=True)
                    cek.cek_durumu = CekDurumu.KARSILIKSIZ.value

                # 5.KENDİ ÇEKİMİZİ ÖDEDİK (Verilen Çek -> Kasadan Çıkış)
                elif islem_turu == CekIslemTuru.ODENDI_KASA.value:
                    kasa_har = KasaHareket(
                        firma_id=cek.firma_id, 
                        donem_id=donem_id,
                        kasa_id=data['kasa_id'],
                        islem_turu='tediye', # Para çıkışı
                        belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, 
                        tutar=cek.tutar,
                        aciklama=f"Çek Ödemesi ({cek.cek_no}) - {aciklama}", 
                        onaylandi=True
                    )
                    db.session.add(kasa_har)
                    cek.cek_durumu = CekDurumu.ODENDI_KASA.value
                    cek.tahsil_tarihi = tarih
                
                # 6.KENDİ ÇEKİMİZ BANKADAN ÖDENDİ
                elif islem_turu == CekIslemTuru.ODENDI_BANKA.value:
                    banka_har = BankaHareket(
                        firma_id=cek.firma_id, 
                        donem_id=donem_id,
                        banka_id=data['banka_id'],
                        islem_turu='tediye', # Para çıkışı
                        belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, 
                        tutar=cek.tutar,
                        aciklama=f"Çek Ödemesi ({cek.cek_no}) - {aciklama}"
                    )
                    db.session.add(banka_har)
                    cek.cek_durumu = CekDurumu.ODENDI_BANKA.value
                    cek.tahsil_tarihi = tarih

                db.session.commit()
                return jsonify({'success': True, 'message': 'İşlem Başarıyla Gerçekleşti.', 'redirect': '/cek'})
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
                
    return render_template('cek/form.html', form=form)

@cek_bp.route('/api/cek-ocr', methods=['POST'])
@login_required
def api_cek_ocr():
    # ...(OCR kodu önceki gibi kalacak, sadece dönüşte 'cek_no' verisi 'fiziksel_no' inputuna gidecek)
    # JS tarafında data.cek_no -> input[name="cek_no"] eşleşmesi zaten doğru.
    if 'file' not in request.files: return jsonify({'success': False, 'message': 'Dosya yok'})
    file = request.files['file']
    if file.filename == '': return jsonify({'success': False, 'message': 'Seçim yok'})
    
    try:
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp_checks')
        os.makedirs(path, exist_ok=True)
        full_path = os.path.join(path, filename)
        file.save(full_path)
        
        from form_builder.ai_generator import analyze_check_image
        ocr_data = analyze_check_image(full_path)
        
        if ocr_data and "error" not in ocr_data:
            return jsonify({'success': True, 'data': ocr_data})
        else:
            return jsonify({'success': False, 'message': ocr_data.get("error", "Hata")})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})   

@cek_bp.route('/detay/<int:id>')
@login_required
def detay(id):
    cek = CekSenet.query.get_or_404(id)
    
    # 1.Formu Hazırla (İzleme Modu)
    form = create_cek_form(yon=cek.portfoy_tipi, islem=cek, view_only=True)
    form.submit_text = None 
    
    # 2.TARİHÇE OLUŞTURMA (Timeline Data)
    timeline = []
    
    # A) İlk Kayıt (Oluşturma)
    timeline.append({
        'tarih': cek.olusturma_tarihi,
        'baslik': 'Sisteme Kayıt',
        'detay': f"{cek.belge_no} referansıyla portföye alındı.",
        'icon': 'bi-plus-lg',
        'renk': 'success'
    })
    
    # B) Kasa Hareketlerini Bul
    # Çek No veya Belge No üzerinden eşleşen hareketleri çek
    aranacak_no = cek.cek_no if cek.cek_no else cek.belge_no
    
    kasa_hareketleri = KasaHareket.query.filter_by(
        firma_id=current_user.firma_id, 
        belge_no=aranacak_no
    ).all()
    
    for k in kasa_hareketleri:
        timeline.append({
            'tarih': k.olusturma_tarihi or datetime.now(), # Hareket saati yoksa şu anı al
            'baslik': 'Kasa İşlemi',
            'detay': k.aciklama,
            'icon': 'bi-wallet2',
            'renk': 'primary'
        })
        
    # C) Banka Hareketlerini Bul
    banka_hareketleri = BankaHareket.query.filter_by(
        firma_id=current_user.firma_id, 
        belge_no=aranacak_no
    ).all()
    
    for b in banka_hareketleri:
        timeline.append({
            'tarih': b.olusturma_tarihi or datetime.now(),
            'baslik': 'Banka İşlemi',
            'detay': b.aciklama,
            'icon': 'bi-bank',
            'renk': 'info'
        })

    # 3.Kronolojik Sıralama (Yeniden Eskiye)
    timeline.sort(key=lambda x: x['tarih'], reverse=True)
    
    return render_template('cek/form.html', form=form, timeline=timeline)

# modules/cek/routes.py dosyasının en altına ekleyin:

@cek_bp.route('/yazdir/<int:id>')
@login_required
def yazdir(id):
    cek = CekSenet.query.get_or_404(id)
    
    # Başlık Belirleme (Tahsilat Makbuzu / Tediye Makbuzu)
    if cek.portfoy_tipi == 'alinan':
        baslik = "TAHSİLAT MAKBUZU (ÇEK/SENET GİRİŞ BORDROSU)"
        taraf_lbl = "Teslim Eden (Müşteri)"
        biz_lbl = "Teslim Alan"
    else:
        baslik = "TEDİYE MAKBUZU (ÇEK/SENET ÇIKIŞ BORDROSU)"
        taraf_lbl = "Teslim Alan (Tedarikçi)"
        biz_lbl = "Teslim Eden"

    return render_template('cek/print.html', 
                           cek=cek, 
                           firma=current_user.firma,
                           baslik=baslik,
                           taraf_lbl=taraf_lbl,
                           biz_lbl=biz_lbl,
                           tarih=datetime.now())

@cek_bp.route('/analiz')
@login_required
def analiz():
    # Tüm çekleri getir
    cekler = CekSenet.query.filter_by(firma_id=current_user.firma_id).all()
    data = cek_to_dict(cekler)
    
    # 1.Banka Bazlı Rapor
    pivot_banka = PivotEngine(
        data=data,
        rows="banka_adi",
        values="tutar",
        aggregator="sum",
        title="Banka Bazlı Risk Dağılımı",
        chart_type="doughnut"
    )
    
    # 2.Vade Bazlı Nakit Akışı
    pivot_vade = PivotEngine(
        data=data,
        rows="vade_ayi",
        values="tutar",
        aggregator="sum",
        title="Aylık Tahsilat/Ödeme Planı",
        chart_type="bar"
    )
    
    # İki raporu alt alta birleştir
    html_content = pivot_banka.render() + "<br>" + pivot_vade.render()
    
    return render_template('cek/rapor.html', title="Finansal Analiz Raporları", content=html_content)


@cek_bp.route('/kanban')
@login_required
def kanban():
    # Sadece Firma ID'sine göre filtrele, tüm durumları getir ki hatayı görelim
    cekler = CekSenet.query.filter_by(firma_id=current_user.firma_id).all()
    
    # Veriyi hazırla
    kanban_data = cek_to_dict(cekler)
    
    bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()
    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()

    return render_template('cek/kanban.html', 
                           kanban_data=kanban_data,
                           bankalar=bankalar,
                           cariler=cariler)


# 2.API UPDATE STATUS (ENUM İLE REFAKTÖR EDİLMİŞ HALİ)
@cek_bp.route('/api/update-status', methods=['POST'])
@login_required
def api_update_status():
    try:
        data = request.get_json()
        cek_id = data.get('id')
        yeni_durum = data.get('status')
        hedef_id = data.get('target_id')
        
        if not cek_id or not yeni_durum:
            return jsonify({'success': False, 'message': 'Eksik veri.'}), 400
            
        cek = CekSenet.query.get(cek_id)
        if not cek:
            return jsonify({'success': False, 'message': 'Kayıt bulunamadı.'}), 404
            
        eski_durum = cek.cek_durumu
        
        # --- DURUM GEÇİŞ KONTROLLERİ ---
        
        # 1.TAHSİLE VERME (Portföy -> Banka)
        if yeni_durum == CekDurumu.TAHSILE_VERILDI.value:
            if not hedef_id:
                return jsonify({'success': False, 'message': 'Banka seçilmedi!'}), 400
            
            cek.banka_id = hedef_id
            cek.konum = CekKonumu.BANKADA_TAHSILDE.value
            
        # 2.CİRO ETME (Portföy -> Cari)
        elif yeni_durum == CekDurumu.TEMLIK_EDILDI.value:
            if not hedef_id:
                return jsonify({'success': False, 'message': 'Cari seçilmedi!'}), 400
            
            # Cari Hareket (Satıcıya Borçlanma / Ödeme)
            CariHareket.kayit_olustur(
                cari_id=hedef_id,
                islem_turu=CariIslemTuru.CEK_CIKIS.value,
                tutar=cek.tutar,
                yon='borc', # Satıcıya ödeme yaptık, o bize borçlandı (bakiyesi düştü)
                belge_no=cek.portfoy_no,
                aciklama=f"Çek Cirosu: {cek.cek_no}",
                kaynak_belge=('cek', cek.id)
            )
            
            cek.verilen_cari_id = hedef_id
            cek.konum = CekKonumu.MUSTERIDE.value

        # 3.PORTFÖYE GERİ ALMA (İPTAL / DÜZELTME)
        elif yeni_durum == CekDurumu.PORTFOYDE.value:
            
            # A) Eğer CİRO'dan geri geliyorsa -> TERS KAYIT AT (İPTAL ET)
            if eski_durum == CekDurumu.TEMLIK_EDILDI.value and cek.verilen_cari_id:
                
                # Önceki işlemin TERSİNİ yapıyoruz (Yön: 'alacak')
                # Böylece +1000 ve -1000 birbirini götürüp 0 olacak.
                CariHareket.kayit_olustur(
                    cari_id=cek.verilen_cari_id,
                    islem_turu=CariIslemTuru.CEK_GIRIS.value, # İade girişi gibi düşünelim
                    tutar=cek.tutar,
                    yon='alacak', # <--- TERS İŞLEM (Borcu siliyoruz/Alacaklandırıyoruz)
                    belge_no=cek.portfoy_no,
                    aciklama=f"İPTAL: Çek Cirosu Geri Alındı - {cek.cek_no}",
                    kaynak_belge=('cek', cek.id)
                )
                
            # B) Alanları Temizle
            cek.banka_id = None
            cek.verilen_cari_id = None
            cek.konum = CekKonumu.KASADA.value

        # 4.TAHSİL EDİLDİ (Banka veya Kasaya Para Girdi)
        elif yeni_durum == CekDurumu.TAHSIL_EDILDI.value:
            # Burası için ayrı bir pop-up gerekebilir (Kasa mı Banka mı?)
            # Şimdilik basitçe durumu güncelliyoruz.
            pass

        # Durumu güncelle
        cek.cek_durumu = yeni_durum
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'İşlem ve muhasebe kaydı güncellendi.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

    