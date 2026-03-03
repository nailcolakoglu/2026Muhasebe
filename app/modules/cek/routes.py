# app/modules/cek/routes.py (Tamamı - Multi-Tenant Uyumlu)

from flask import Blueprint, render_template, request, jsonify, session, current_app, abort
from flask_login import login_required, current_user
import os
import json
from datetime import datetime
from decimal import Decimal
from werkzeug.utils import secure_filename

# Multi-Tenant & Ortak Eklentiler
from app.extensions import get_tenant_db
from app.decorators import tenant_route
from app.form_builder import DataGrid, FieldType
from app.form_builder.kanban import KanbanBoard
from app.form_builder.pivot import PivotEngine

# Modeller ve Servisler
from app.modules.cek.models import CekSenet
from app.modules.cari.models import CariHesap, CariHareket
from app.modules.kasa.models import Kasa
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.modules.banka.models import BankaHesap
from app.modules.firmalar.models import Firma, Donem
from app.modules.cari.services import CariService

# Form ve Enumlar
from .forms import create_cek_form, create_cek_islem_form
from app.enums import CekDurumu, PortfoyTipi, CekIslemTuru, CekKonumu, CariIslemTuru

cek_bp = Blueprint('cek', __name__)

# ==========================================
# YARDIMCI FONKSİYONLAR
# ==========================================

def parse_decimal(value):
    if not value: return Decimal(0)
    if isinstance(value, (int, float)): return Decimal(value)
    clean_val = str(value).replace('.', '').replace(',', '.')
    try: return Decimal(clean_val)
    except: return Decimal(0)

def save_uploaded_file(file_obj, subfolder='cekler'):
    if not file_obj or file_obj.filename == '':
        return None
    filename = secure_filename(f"{int(datetime.now().timestamp())}_{file_obj.filename}")
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', subfolder)
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file_obj.save(file_path)
    return f"uploads/{subfolder}/{filename}"

def cek_to_dict(cekler):
    data_list = []
    for c in cekler:
        item = {
            'id': c.id,
            'cek_durumu': c.cek_durumu,
            'cari_unvan': c.cari.unvan if c.cari else 'Cari Yok',
            'banka_adi': c.banka_adi if c.banka_adi else (getattr(c, 'banka', None).banka_adi if getattr(c, 'banka', None) else '-'),
            'tutar': float(c.tutar),
            'vade_tarihi': c.vade_tarihi.strftime('%d.%m.%Y') if c.vade_tarihi else '-',
            'vade_ayi': c.vade_tarihi.strftime('%Y-%m') if c.vade_tarihi else 'Bilinmiyor',
            'belge_no': c.belge_no
        }
        data_list.append(item)
    return data_list

def update_cari_bakiye(tenant_db, cari_id, tutar, yon, is_reverse=False):
    if not cari_id: return
    cari = tenant_db.query(CariHesap).get(cari_id) 
    if not cari: return
    
    val = float(tutar)
    if is_reverse: val = -val
    
    if yon == 'alinan':
        cari.alacak_bakiye = float(cari.alacak_bakiye or 0) + val
    elif yon == 'verilen':
        cari.borc_bakiye = float(cari.borc_bakiye or 0) - val 
        
    tenant_db.add(cari)


# ==========================================
# ROTALAR (ENDPOINTS)
# ==========================================

@cek_bp.route('/api/siradaki-no')
@login_required
@tenant_route
def api_siradaki_no():
    tenant_db = get_tenant_db()
    yil = datetime.now().year
    son = tenant_db.query(CekSenet).filter_by(firma_id=current_user.firma_id).count()
    return jsonify({'code': f"P-{yil}-{str(son+1).zfill(6)}"})


@cek_bp.route('/')
@login_required
@tenant_route
def index():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("cek_list", CekSenet, "Kıymetli Evrak Portföyü")
    
    grid.add_column('belge_no', 'Portföy No', width='120px') 
    grid.add_column('cek_no', 'Asıl Belge No', width='100px') 
    grid.add_column('tur', 'Tür', type='badge', badge_colors={'CEK': 'info', 'SENET': 'warning'})
    grid.add_column('portfoy_tipi', 'Yön', type='badge', badge_colors={'alinan': 'success', 'verilen': 'danger'})
    grid.add_column('cari.unvan', 'Cari Hesap')
    grid.add_column('vade_tarihi', 'Vade', type=FieldType.DATE)
    grid.add_column('tutar', 'Tutar', type=FieldType.CURRENCY)
    grid.add_column('cek_durumu', 'Durum', type='badge', 
                    badge_colors={'portfoyde': 'primary', 'tahsil_edildi': 'success', 'odendi': 'secondary', 'karsiliksiz': 'dark'})
    
    grid.add_action('islem', 'İşlem', 'bi bi-gear-fill', 'btn-warning btn-sm', 'route', 'cek.islem')
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'cek.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'cek.sil')
    grid.add_action('print', 'Yazdır', 'bi bi-printer', 'btn-outline-secondary btn-sm', 
                    'url', lambda row: f"/cek/yazdir/{row.id}", 
                    html_attributes={'target': '_blank'})
        
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sube_id', 'donem_id', 'giris_depo_id', 'cikis_depo_id',
        'ai_guven_skoru', 'ocr_dogruluk_orani', 'sektor_etiketi',
        'created_at', 'updated_at', 'deleted_at', 
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    
    query = tenant_db.query(CekSenet).filter_by(firma_id=current_user.firma_id).order_by(CekSenet.vade_tarihi.asc())
    grid.process_query(query)
    
    # Gizlenecek gereksiz sütunlar
    for hidden_col in ['id', 'firma_id', 'cari.id', 'finans_islem_id', 'tahsil_tarihi', 'kalan_gun', 'vade_grubu', 'doviz_cinsi', 'kur', 'iskonto_oranı', 'net_tahsilat_tutarı', 'banka_komisyonu', 'tahsilat_olasiligi', 'ciranta_adi', 'risk_seviyesi', 'risk_puani', 'resim_on_path', 'resim_arka_path', 'ocr_ham_veri', 'fiziksel_yeri', 'iskonto_orani', 'protesto_masrafi', 'ciranta_sayisi', 'ai_onerisi', 'seri_no', 'cari_id', 'net_tahsilat_tutari', 'tahsilat_tahmini_tarihi', 'gecikme_gunu', 'aciklama', 'olusturma_tarihi', 'duzenleme_tarihi', 'sonuc_durumu', 'iban', 'kesideci_tc_vkn', 'hesap_no', 'kefil']:
        grid.hide_column(hidden_col)
    
    # --- DASHBOARD HESAPLAMALARI ---
    tum_kayitlar = query.all()
    toplam_alinan_cek = sum(float(c.tutar) for c in tum_kayitlar if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'alinan' and c.tur == 'CEK')
    toplam_alinan_senet = sum(float(c.tutar) for c in tum_kayitlar if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'alinan' and c.tur == 'SENET')
    toplam_verilen_cek = sum(float(c.tutar) for c in tum_kayitlar if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'verilen' and c.tur == 'CEK')
    toplam_verilen_senet = sum(float(c.tutar) for c in tum_kayitlar if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'verilen' and c.tur == 'SENET')
    
    # --- GRAFİK VERİSİ ---
    portfoydeki_evraklar = [c for c in tum_kayitlar if c.cek_durumu == 'portfoyde' and c.portfoy_tipi == 'alinan']
    cek_toplam = sum(float(c.tutar) for c in portfoydeki_evraklar if c.tur == 'CEK')
    senet_toplam = sum(float(c.tutar) for c in portfoydeki_evraklar if c.tur == 'SENET')
    pie_data = {'labels': ['Çek', 'Senet'], 'data': [cek_toplam, senet_toplam]}

    from collections import defaultdict
    aylik_toplamlar = defaultdict(float)
    for c in portfoydeki_evraklar:
        if c.vade_tarihi:
            aylik_toplamlar[c.vade_tarihi.strftime('%Y-%m')] += float(c.tutar)
    
    ay_isimleri = {'01':'Ocak', '02':'Şubat', '03':'Mart', '04':'Nisan', '05':'Mayıs', '06':'Haziran', 
                   '07':'Temmuz', '08':'Ağustos', '09':'Eylül', '10':'Ekim', '11':'Kasım', '12':'Aralık'}
    bar_labels, bar_values = [], []
    for ay_kodu in sorted(aylik_toplamlar.keys()):
        yil, ay = ay_kodu.split('-')
        bar_labels.append(f"{ay_isimleri.get(ay)} {yil}")
        bar_values.append(aylik_toplamlar[ay_kodu])
    
    bar_data = {'labels': bar_labels, 'data': bar_values}

    return render_template('cek/index.html', grid=grid, 
                           toplam_alinan_cek=toplam_alinan_cek, toplam_alinan_senet=toplam_alinan_senet,
                           toplam_verilen_cek=toplam_verilen_cek, toplam_verilen_senet=toplam_verilen_senet,
                           pie_chart_data=json.dumps(pie_data), bar_chart_data=json.dumps(bar_data))


@cek_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@tenant_route
def ekle():
    tenant_db = get_tenant_db()
    yon = request.args.get('yon', 'alinan')
    form = create_cek_form(yon=yon)
    
    if request.method == 'POST':
        form.process_request(request.form, request.files)
        if form.validate():
            try:
                data = form.get_data()
                gelen_cek_no = data.get('cek_no')

                if gelen_cek_no:
                    mevcut = tenant_db.query(CekSenet).filter_by(firma_id=current_user.firma_id, cek_no=gelen_cek_no, portfoy_tipi=yon).first()
                    if mevcut:
                        return jsonify({'success': False, 'message': f"Bu seri numarasıyla ({gelen_cek_no}) bir kayıt zaten var!"}), 400

                yeni_cek = CekSenet(
                    firma_id=current_user.firma_id,
                    portfoy_tipi=yon,
                    tur=data['tur'],
                    belge_no=data['sys_belge_no'], 
                    cek_no=gelen_cek_no,           
                    seri_no=data.get('seri_no'),   
                    cari_id=data['cari_id'],
                    vade_tarihi=datetime.strptime(data['vade_tarihi'], '%Y-%m-%d').date(),
                    tutar=parse_decimal(data['tutar']),
                    aciklama=data.get('aciklama'),
                    duzenleme_tarihi=datetime.strptime(data['duzenleme_tarihi'], '%Y-%m-%d').date(),
                    cek_durumu='portfoyde'
                )
                
                if yon == 'alinan':
                    yeni_cek.resim_on_path = save_uploaded_file(request.files['cek_resmi']) if 'cek_resmi' in request.files else None
                    yeni_cek.kesideci_tc_vkn = data.get('kesideci_tc_vkn')
                    yeni_cek.kesideci_unvan = data.get('kesideci_unvan')
                    yeni_cek.banka_adi = data.get('banka_adi')
                    yeni_cek.sube_adi = data.get('sube_adi')
                    yeni_cek.hesap_no = data.get('hesap_no')
                    yeni_cek.iban = data.get('iban')
                    if data['tur'] == 'SENET': yeni_cek.kefil = data.get('kefil')

                elif yon == 'verilen':
                    if data['tur'] == 'CEK' and data.get('banka_hesap_id'):
                        bizim_banka = tenant_db.query(BankaHesap).get(data['banka_hesap_id'])
                        if bizim_banka:
                            yeni_cek.banka_adi = bizim_banka.banka_adi
                            yeni_cek.sube_adi = bizim_banka.sube_adi
                            yeni_cek.hesap_no = bizim_banka.hesap_no
                            yeni_cek.iban = bizim_banka.iban
                            yeni_cek.kesideci_unvan = current_user.firma.unvan

                tenant_db.add(yeni_cek)
                update_cari_bakiye(tenant_db, yeni_cek.cari_id, yeni_cek.tutar, yon)
                tenant_db.commit()
                
                return jsonify({'success': True, 'message': 'Kayıt başarılı.'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('cek/form.html', form=form)


@cek_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
@tenant_route
def sil(id):
    tenant_db = get_tenant_db()
    cek = tenant_db.query(CekSenet).get(id)
    if not cek: abort(404)
        
    if cek.cek_durumu != 'portfoyde':
        return jsonify({'success': False, 'message': 'İşlem görmüş kayıt silinemez!'}), 400
        
    try:
        update_cari_bakiye(tenant_db, cek.cari_id, cek.tutar, cek.portfoy_tipi, is_reverse=True)
        tenant_db.delete(cek)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@cek_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
@tenant_route
def duzenle(id):
    tenant_db = get_tenant_db()
    cek = tenant_db.query(CekSenet).get(id)
    if not cek: abort(404)
    
    if cek.cek_durumu != 'portfoyde':
        return render_template('hata.html', mesaj="İşlem görmüş çek/senet düzenlenemez! Önce işlemi iptal ediniz."), 403

    form = create_cek_form(yon=cek.portfoy_tipi, islem=cek)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                update_cari_bakiye(tenant_db, cek.cari_id, cek.tutar, cek.portfoy_tipi, is_reverse=True)
                data = form.get_data()

                if 'cek_resmi' in request.files and request.files['cek_resmi'].filename != '':
                    yeni_yol = save_uploaded_file(request.files['cek_resmi'])
                    if yeni_yol: cek.resim_on_path = yeni_yol 

                cek.tur = data['tur']
                cek.belge_no = data['sys_belge_no'] 
                cek.cek_no = data['cek_no']         
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
                    if cek.tur == 'SENET': cek.kefil = data.get('kefil')
                
                update_cari_bakiye(tenant_db, cek.cari_id, cek.tutar, cek.portfoy_tipi)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Kayıt başarıyla güncellendi.', 'redirect': '/cek'})
                
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
                
    return render_template('cek/form.html', form=form)


@cek_bp.route('/islem/<string:id>', methods=['GET', 'POST'])
@login_required
@tenant_route
def islem(id):
    tenant_db = get_tenant_db()
    cek = tenant_db.query(CekSenet).get(id)
    if not cek: abort(404)
    
    if cek.cek_durumu != 'portfoyde':
        msg = "Bu evrak zaten işlem görmüş (Tahsil/Ciro edilmiş)."
        if request.method == 'POST': return jsonify({'success': False, 'message': msg}), 400
        return render_template('hata.html', mesaj=msg)
    
    form = create_cek_islem_form(cek)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                islem_turu = data['islem_turu']
                tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
                aciklama = data['aciklama']
                
                donem = tenant_db.query(Donem).filter_by(firma_id=current_user.firma_id, aktif=True).first()
                donem_id = donem.id if donem else None

                # 1.KASADAN TAHSİLAT
                if islem_turu == CekIslemTuru.TAHSIL_KASA.value:
                    kasa_har = KasaHareket(
                        firma_id=cek.firma_id, donem_id=donem_id, kasa_id=data['kasa_id'],
                        islem_turu='tahsilat', belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, tutar=cek.tutar, aciklama=f"Çek Tahsilatı ({cek.cek_no}) - {aciklama}", onaylandi=True
                    )
                    tenant_db.add(kasa_har)
                    cek.cek_durumu = CekDurumu.TAHSIL_EDILDI.value
                    cek.tahsil_tarihi = tarih

                # 2.BANKADAN TAHSİLAT
                elif islem_turu == CekIslemTuru.TAHSIL_BANKA.value:
                    banka_har = BankaHareket(
                        firma_id=cek.firma_id, donem_id=donem_id, banka_id=data['banka_id'],
                        islem_turu='tahsilat', belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, tutar=cek.tutar, aciklama=f"Çek Tahsilatı ({cek.cek_no}) - {aciklama}"
                    )
                    tenant_db.add(banka_har)
                    cek.cek_durumu = CekDurumu.TAHSIL_EDILDI.value
                    cek.tahsil_tarihi = tarih

                # 3.CİRO ETME (Çekirdek Servis Üzerinden)
                elif islem_turu == CekIslemTuru.CIRO.value:
                    satici_id = data['cari_id']
                    CariService.hareket_ekle(
                        cari_id=satici_id,
                        islem_turu=CariIslemTuru.CEK_CIKIS.value,
                        belge_no=cek.portfoy_no or cek.belge_no,
                        tarih=tarih,
                        aciklama=f"Çek Cirosu: {cek.cek_no}",
                        borc=float(cek.tutar), alacak=0,
                        kaynak_ref={'tur': 'CEK_SENET', 'id': str(cek.id)},
                        tenant_db=tenant_db
                    )
                    cek.cek_durumu = CekDurumu.CIRO.value
                    satici = tenant_db.query(CariHesap).get(satici_id)
                    cek.ciranta_adi = satici.unvan if satici else "Bilinmiyor"
                    cek.aciklama += f" | Ciro Edilen: {cek.ciranta_adi}"

                # 4.KARŞILIKSIZ
                elif islem_turu == CekIslemTuru.KARSILIKSIZ.value:
                    update_cari_bakiye(tenant_db, cek.cari_id, cek.tutar, cek.portfoy_tipi, is_reverse=True)
                    cek.cek_durumu = CekDurumu.KARSILIKSIZ.value

                # 5.KENDİ ÇEKİMİZ KASADAN ÖDENDİ
                elif islem_turu == CekIslemTuru.ODENDI_KASA.value:
                    kasa_har = KasaHareket(
                        firma_id=cek.firma_id, donem_id=donem_id, kasa_id=data['kasa_id'],
                        islem_turu='tediye', belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, tutar=cek.tutar, aciklama=f"Çek Ödemesi ({cek.cek_no}) - {aciklama}", onaylandi=True
                    )
                    tenant_db.add(kasa_har)
                    cek.cek_durumu = CekDurumu.ODENDI_KASA.value
                    cek.tahsil_tarihi = tarih
                
                # 6.KENDİ ÇEKİMİZ BANKADAN ÖDENDİ
                elif islem_turu == CekIslemTuru.ODENDI_BANKA.value:
                    banka_har = BankaHareket(
                        firma_id=cek.firma_id, donem_id=donem_id, banka_id=data['banka_id'],
                        islem_turu='tediye', belge_no=cek.cek_no or cek.belge_no, 
                        tarih=tarih, tutar=cek.tutar, aciklama=f"Çek Ödemesi ({cek.cek_no}) - {aciklama}"
                    )
                    tenant_db.add(banka_har)
                    cek.cek_durumu = CekDurumu.ODENDI_BANKA.value
                    cek.tahsil_tarihi = tarih

                tenant_db.commit()
                return jsonify({'success': True, 'message': 'İşlem Başarıyla Gerçekleşti.', 'redirect': '/cek'})
                
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
                
    return render_template('cek/form.html', form=form)


@cek_bp.route('/api/update-status', methods=['POST'])
@login_required
@tenant_route
def api_update_status():
    tenant_db = get_tenant_db()
    try:
        data = request.get_json()
        cek_id = data.get('id')
        yeni_durum = data.get('status')
        hedef_id = data.get('target_id')
        
        if not cek_id or not yeni_durum:
            return jsonify({'success': False, 'message': 'Eksik veri.'}), 400
            
        cek = tenant_db.query(CekSenet).get(cek_id)
        if not cek: return jsonify({'success': False, 'message': 'Kayıt bulunamadı.'}), 404
            
        eski_durum = cek.cek_durumu
        
        if yeni_durum == CekDurumu.TAHSILE_VERILDI.value:
            if not hedef_id: return jsonify({'success': False, 'message': 'Banka seçilmedi!'}), 400
            cek.banka_id = hedef_id
            cek.konum = CekKonumu.BANKADA_TAHSILDE.value
            
        elif yeni_durum == CekDurumu.TEMLIK_EDILDI.value:
            if not hedef_id: return jsonify({'success': False, 'message': 'Cari seçilmedi!'}), 400
            CariService.hareket_ekle(
                cari_id=hedef_id, islem_turu=CariIslemTuru.CEK_CIKIS.value,
                belge_no=cek.portfoy_no or cek.belge_no, tarih=datetime.utcnow().date(),
                aciklama=f"Çek Cirosu: {cek.cek_no}", borc=float(cek.tutar), alacak=0,
                kaynak_ref={'tur': 'CEK_SENET', 'id': str(cek.id)}, tenant_db=tenant_db
            )
            cek.verilen_cari_id = hedef_id
            cek.konum = CekKonumu.MUSTERIDE.value

        elif yeni_durum == CekDurumu.PORTFOYDE.value:
            if eski_durum == CekDurumu.TEMLIK_EDILDI.value and cek.verilen_cari_id:
                CariService.hareket_ekle(
                    cari_id=cek.verilen_cari_id, islem_turu=CariIslemTuru.CEK_GIRIS.value,
                    belge_no=cek.portfoy_no or cek.belge_no, tarih=datetime.utcnow().date(),
                    aciklama=f"İPTAL: Çek Cirosu Geri Alındı - {cek.cek_no}", borc=0, alacak=float(cek.tutar),
                    kaynak_ref={'tur': 'CEK_SENET', 'id': str(cek.id)}, tenant_db=tenant_db
                )
            cek.banka_id = None
            cek.verilen_cari_id = None
            cek.konum = CekKonumu.KASADA.value

        elif yeni_durum == CekDurumu.TAHSIL_EDILDI.value:
            pass 

        cek.cek_durumu = yeni_durum
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'İşlem ve muhasebe kaydı güncellendi.'})

    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@cek_bp.route('/detay/<string:id>')
@login_required
@tenant_route
def detay(id):
    tenant_db = get_tenant_db()
    cek = tenant_db.query(CekSenet).get(id)
    if not cek: abort(404)
    
    form = create_cek_form(yon=cek.portfoy_tipi, islem=cek, view_only=True)
    form.submit_text = None 
    
    timeline = []
    timeline.append({
        'tarih': cek.olusturma_tarihi or datetime.now(),
        'baslik': 'Sisteme Kayıt',
        'detay': f"{cek.belge_no} referansıyla portföye alındı.",
        'icon': 'bi-plus-lg',
        'renk': 'success'
    })
    
    aranacak_no = cek.cek_no if cek.cek_no else cek.belge_no
    
    kasa_hareketleri = tenant_db.query(KasaHareket).filter_by(firma_id=current_user.firma_id, belge_no=aranacak_no).all()
    for k in kasa_hareketleri:
        timeline.append({'tarih': k.olusturma_tarihi or datetime.now(), 'baslik': 'Kasa İşlemi', 'detay': k.aciklama, 'icon': 'bi-wallet2', 'renk': 'primary'})
        
    banka_hareketleri = tenant_db.query(BankaHareket).filter_by(firma_id=current_user.firma_id, belge_no=aranacak_no).all()
    for b in banka_hareketleri:
        timeline.append({'tarih': b.olusturma_tarihi or datetime.now(), 'baslik': 'Banka İşlemi', 'detay': b.aciklama, 'icon': 'bi-bank', 'renk': 'info'})

    timeline.sort(key=lambda x: x['tarih'], reverse=True)
    return render_template('cek/form.html', form=form, timeline=timeline)


@cek_bp.route('/yazdir/<string:id>')
@login_required
@tenant_route
def yazdir(id):
    tenant_db = get_tenant_db()
    
    # 1. Çeki Bul
    cek = tenant_db.query(CekSenet).get(id)
    if not cek: 
        flash("Yazdırılacak çek bulunamadı.", "danger")
        return redirect(url_for('cek.index'))

    # ✨ DÜZELTME: Firma bilgisini Tenant DB'den çek (current_user.firma yerine)
    aktif_firma = tenant_db.query(Firma).filter_by(id=str(current_user.firma_id)).first()
    
    # Eğer firma bulunamazsa en azından boş bir nesne veya isim gönderelim ki şablon çökmesin
    if not aktif_firma:
        aktif_firma = tenant_db.query(Firma).first() # Fallback
    
    if cek.portfoy_tipi == 'alinan':
        baslik = "TAHSİLAT MAKBUZU (ÇEK/SENET GİRİŞ BORDROSU)"
        taraf_lbl = "Teslim Eden (Müşteri)"
        biz_lbl = "Teslim Alan"
    else:
        baslik = "TEDİYE MAKBUZU (ÇEK/SENET ÇIKIŞ BORDROSU)"
        taraf_lbl = "Teslim Alan (Tedarikçi)"
        biz_lbl = "Teslim Eden"

    return render_template('cek/print.html', cek=cek, firma=aktif_firma,
                           baslik=baslik, taraf_lbl=taraf_lbl, biz_lbl=biz_lbl, tarih=datetime.now())


@cek_bp.route('/analiz')
@login_required
@tenant_route
def analiz():
    tenant_db = get_tenant_db()
    cekler = tenant_db.query(CekSenet).filter_by(firma_id=current_user.firma_id).all()
    data = cek_to_dict(cekler)
    
    pivot_banka = PivotEngine(data=data, rows="banka_adi", values="tutar", aggregator="sum", title="Banka Bazlı Risk Dağılımı", chart_type="doughnut")
    pivot_vade = PivotEngine(data=data, rows="vade_ayi", values="tutar", aggregator="sum", title="Aylık Tahsilat/Ödeme Planı", chart_type="bar")
    html_content = pivot_banka.render() + "<br>" + pivot_vade.render()
    
    return render_template('cek/rapor.html', title="Finansal Analiz Raporları", content=html_content)


@cek_bp.route('/kanban')
@login_required
@tenant_route
def kanban():
    tenant_db = get_tenant_db()
    cekler = tenant_db.query(CekSenet).filter_by(firma_id=current_user.firma_id).all()
    kanban_data = cek_to_dict(cekler)
    
    bankalar = tenant_db.query(BankaHesap).filter_by(firma_id=current_user.firma_id).all()
    cariler = tenant_db.query(CariHesap).filter_by(firma_id=current_user.firma_id).all()

    return render_template('cek/kanban.html', kanban_data=kanban_data, bankalar=bankalar, cariler=cariler)


@cek_bp.route('/api/cek-ocr', methods=['POST'])
@login_required
@tenant_route
def api_cek_ocr():
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