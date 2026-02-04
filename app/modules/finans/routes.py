# app/modules/finans/routes.py

from app.utils.decorators import role_required 
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from app.extensions import db
from app.modules.finans.models import FinansIslem
from app.modules.firmalar.models import Donem
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.modules.cek.models import CekSenet
from app.form_builder import DataGrid
from .forms import create_makbuz_form, create_virman_form, create_gider_form
from datetime import datetime, timedelta
from app.form_builder.ai_generator import analyze_cash_flow
import json
from decimal import Decimal
from .services import FinansService 

finans_bp = Blueprint('finans', __name__)

@finans_bp.route('/')
@login_required
def index():
    grid = DataGrid("finans_list", FinansIslem, "Makbuz Listesi")
    grid.add_column('tarih', 'Tarih', type='date', width='100px')
    grid.add_column('belge_no', 'Makbuz No')
    grid.add_column('cari.unvan', 'Cari Hesap')
    grid.add_column('islem_turu', 'Tür', type='badge', badge_colors={'tahsilat': 'success', 'tediye': 'danger'})
    grid.add_column('genel_toplam', 'Toplam', type='currency')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'finans.sil')
    
    query = FinansIslem.query.filter_by(firma_id=current_user.firma_id).order_by(FinansIslem.tarih.desc())
    grid.process_query(query)
    
    return render_template('finans/index.html', grid=grid)

@finans_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_makbuz_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                # Dönem/Şube
                donem_id = session.get('aktif_donem_id') or current_user.firma.donemler[-1].id
                sube_id = session.get('aktif_sube_id') or current_user.yetkili_subeler[0].id
                
                data['donem_id'] = donem_id
                data['sube_id'] = sube_id
                data['tarih'] = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
                
                # Çek listesini topla
                cek_tutarlar = request.form.getlist('cek_listesi_tutar[]')
                # ...(Diğer çek alanları servis içinde işlenmeli veya burada hazırlanmalı)
                # Basitlik için ham datayı servise yolluyoruz, servis create_makbuz içinde işliyor.
                # Ancak form_builder master-detail yapısı veriyi 'data' dict içine koymuş olabilir.
                # Eğer koymadıysa request.form'dan alıp data'ya ekleyelim:
                if cek_tutarlar:
                    cekler = []
                    cek_nolar = request.form.getlist('cek_listesi_cek_no[]')
                    cek_bankalar = request.form.getlist('cek_listesi_banka_adi[]')
                    cek_vadeler = request.form.getlist('cek_listesi_vade_tarihi[]')
                    
                    for i in range(len(cek_tutarlar)):
                        cekler.append({
                            'tutar': cek_tutarlar[i],
                            'cek_no': cek_nolar[i] if i < len(cek_nolar) else '',
                            'banka_adi': cek_bankalar[i] if i < len(cek_bankalar) else '',
                            'vade_tarihi': cek_vadeler[i] if i < len(cek_vadeler) else None
                        })
                    data['cekler'] = cekler

                FinansService.create_makbuz(data, current_user.id)
                return jsonify({'success': True, 'message': 'Makbuz kaydedildi.', 'redirect': '/finans'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500

    return render_template('finans/form.html', form=form)

@finans_bp.route('/virman', methods=['GET', 'POST'])
@login_required 
@role_required('admin', 'muhasebe')
def virman():
    form = create_virman_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                data['firma_id'] = current_user.firma_id
                
                donem_id = session.get('aktif_donem_id')
                if not donem_id:
                     d = Donem.query.filter_by(firma_id=current_user.firma_id, aktif=True).first()
                     donem_id = d.id if d else None
                data['donem_id'] = donem_id
                
                data['tarih'] = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
                
                FinansService.transfer_yap(data)
                return jsonify({'success': True, 'message': 'Transfer başarılı.', 'redirect': '/finans'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('finans/virman.html', form=form)

@finans_bp.route('/gider-ekle', methods=['GET', 'POST'])
@login_required
def gider_ekle():
    form = create_gider_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                data['firma_id'] = current_user.firma_id
                
                donem_id = session.get('aktif_donem_id')
                if not donem_id:
                     d = Donem.query.filter_by(firma_id=current_user.firma_id, aktif=True).first()
                     donem_id = d.id if d else None
                data['donem_id'] = donem_id
                
                data['tarih'] = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
                
                # Servis Çağrısı
                FinansService.gider_kaydet(data)
                
                return jsonify({'success': True, 'message': 'Gider fişi kaydedildi.', 'redirect': '/finans'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500

    return render_template('finans/gider.html', form=form)

@finans_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    try:
        FinansService.delete_makbuz(id)
        return jsonify({'success': True, 'message': 'Silindi.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@finans_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    son = FinansIslem.query.filter_by(firma_id=current_user.firma_id).count()
    return jsonify({'code': f"MKB-{str(son+1).zfill(5)}"})

@finans_bp.route('/nakit-akis-analizi')
@login_required
def nakit_akis_analizi():
    return render_template('finans/nakit_akis.html')

@finans_bp.route('/api/nakit-simulasyon', methods=['POST'])
@login_required
def api_nakit_simulasyon():
    """Nakit akış verilerini hazırlar ve AI'ya gönderir"""
    try:
        # 1.MEVCUT LİKİDİTE (Kasa + Banka)
        kasa_h = KasaHareket.query.filter_by(firma_id=current_user.firma_id, onaylandi=True).all()
        # Not: BankaIslemTuru enum değerlerini string olarak kullanmak gerekebilir
        kasa_giris = sum(h.tutar for h in kasa_h if str(h.islem_turu) in ['tahsilat', 'virman_giris'])
        kasa_cikis = sum(h.tutar for h in kasa_h if str(h.islem_turu) in ['tediye', 'virman_cikis'])
        toplam_kasa = kasa_giris - kasa_cikis

        banka_h = BankaHareket.query.filter_by(firma_id=current_user.firma_id).all()
        b_giris = sum(h.tutar for h in banka_h if str(h.islem_turu) in ['tahsilat', 'virman_giris'])
        b_cikis = sum(h.tutar for h in banka_h if str(h.islem_turu) in ['tediye', 'virman_cikis'])
        toplam_banka = b_giris - b_cikis
        
        mevcut_para = float(toplam_kasa + toplam_banka)

        # 2.GELECEK PLANLAMASI (Çek/Senet - Önümüzdeki 4 Hafta)
        bugun = datetime.today().date()
        bitis = bugun + timedelta(weeks=4)
        
        cekler = CekSenet.query.filter(
            CekSenet.firma_id == current_user.firma_id,
            CekSenet.durum == 'PORTFOY', 
            CekSenet.vade_tarihi >= bugun,
            CekSenet.vade_tarihi <= bitis
        ).order_by(CekSenet.vade_tarihi).all()
        
        # Haftalık Gruplama
        haftalar = {}
        for i in range(4):
            haftalar[i+1] = {'giris': 0, 'cikis': 0, 'cekler': []}
            
        for cek in cekler:
            gun_farki = (cek.vade_tarihi - bugun).days
            hafta_no = (gun_farki // 7) + 1
            
            if 1 <= hafta_no <= 4:
                tutar = float(cek.tutar)
                if cek.yon == 'ALINAN': 
                    haftalar[hafta_no]['giris'] += tutar
                    tur = "Tahsilat"
                else: 
                    haftalar[hafta_no]['cikis'] += tutar
                    tur = "Ödeme"
                    
                haftalar[hafta_no]['cekler'].append(f"{cek.vade_tarihi.strftime('%d.%m')} - {tur} - {tutar} TL")

        # 3.AI Veri Seti
        ai_data = {
            "baslangic_bakiyesi_tl": mevcut_para,
            "analiz_tarihi": bugun.strftime('%d.%m.%Y'),
            "haftalik_projeksiyon": haftalar
        }
        
        json_data = json.dumps(ai_data, ensure_ascii=False)
        rapor_html = analyze_cash_flow(json_data)
        return jsonify({'success': True, 'report': rapor_html})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f"Hata: {str(e)}"})