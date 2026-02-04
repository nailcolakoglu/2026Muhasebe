# app/modules/kasa_hareket/routes.py

from sqlalchemy import func, case
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, g
from flask_login import login_required, current_user
from app.form_builder import DataGrid, FieldType
from .forms import create_kasa_hareket_form
from .services import KasaService 
from app.extensions import db
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.kasa.models import Kasa
from app.araclar import siradaki_kod_uret, para_cevir
from app.enums import BankaIslemTuru

kasa_hareket_bp = Blueprint('kasa_hareket', __name__)

def parse_date_safe(date_str):
    if not date_str: return datetime.now().date()
    formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%Y.%m.%d']
    for fmt in formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except ValueError: continue
    return datetime.now().date()

@kasa_hareket_bp.route('/')
@login_required
def index():
    grid = DataGrid("kasa_hareket_list", KasaHareket, "Kasa Hareketleri")
    
    grid.add_column('tarih', 'Tarih', type='date', width='100px')
    grid.add_column('belge_no', 'Makbuz No')
    grid.add_column('cari.unvan', 'Cari / Açıklama', render_func=lambda r: r.cari.unvan if r.cari else (r.aciklama or '-'))
    grid.add_column('kasa.ad', 'Kasa')
    grid.add_column('tutar', 'Tutar', type=FieldType.CURRENCY)
    grid.add_column('onaylandi', 'Durum', type='badge', badge_colors={'True': 'success', 'False': 'warning'})
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kasa_hareket.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kasa_hareket.sil')
    
    query = KasaHareket.query.filter_by(firma_id=current_user.firma_id).order_by(KasaHareket.tarih.desc())
    grid.process_query(query)
    
    return render_template('kasa_hareket/index.html', grid=grid)

@kasa_hareket_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_kasa_hareket_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        
        # TEXT yaptığımız için artık burası %99 True döner.
        if form.validate():
            try:
                data = form.get_data()
                data['firma_id'] = current_user.firma_id
                
                donem_id = 1
                if hasattr(current_user, 'firma') and current_user.firma.donemler:
                     donem_id = current_user.firma.donemler[-1].id
                data['donem_id'] = donem_id
                
                if 'tarih' in data:
                    data['tarih'] = parse_date_safe(data['tarih'])
                
                # Servisi Çağır (para_cevir servis içinde çalışacak)
                success, msg = KasaService.islem_kaydet(data, current_user.id)
                
                if success:
                    return jsonify({'success': True, 'message': msg, 'redirect': '/kasa-hareket'})
                else:
                    return jsonify({'success': False, 'message': msg}), 500
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f"Sistem Hatası: {str(e)}"}), 500
        else:
            # Hata varsa detayını konsola bas
            print("❌ KASA FORM HATASI:", form.get_errors())
            return jsonify({'success': False, 'message': 'Form alanlarını kontrol ediniz.', 'errors': form.get_errors()}), 400

    return render_template('kasa_hareket/form.html', form=form)

@kasa_hareket_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    hareket = KasaService.get_by_id(id)
    if not hareket or hareket.firma_id != current_user.firma_id:
        return render_template('errors/404.html'), 404

    form = create_kasa_hareket_form(hareket)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                data['firma_id'] = hareket.firma_id
                data['donem_id'] = hareket.donem_id
                
                # --- TARİH FORMATI DÜZELTME ---
                if 'tarih' in data:
                    data['tarih'] = parse_date_safe(data['tarih'])
                
                success, msg = KasaService.islem_kaydet(data, current_user.id, hareket_id=id)
                if success:
                    return jsonify({'success': True, 'message': msg, 'redirect': '/kasa-hareket'})
                return jsonify({'success': False, 'message': msg}), 500
            except Exception as e:
                print(f"Hata Detayı: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500
            
    return render_template('kasa_hareket/form.html', form=form)

@kasa_hareket_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    success, msg = KasaService.islem_sil(id)
    if success:
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'message': msg}), 400

@kasa_hareket_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    code = siradaki_kod_uret(KasaHareket, 'MAK-', hane_sayisi=5)
    return jsonify({'code': code})    

@kasa_hareket_bp.route('/ekstre', methods=['GET'])
@login_required
def ekstre():
    # 1.Filtreleri Al
    kasa_id = request.args.get('kasa_id', type=int)
    bas_tarih = request.args.get('bas_tarih')
    bit_tarih = request.args.get('bit_tarih')

    # Varsayılan: Bu ayın başı ve bugün
    bugun = datetime.now().date()
    if not bas_tarih: bas_tarih = bugun.replace(day=1).strftime('%Y-%m-%d')
    if not bit_tarih: bit_tarih = bugun.strftime('%Y-%m-%d')

    secilen_kasa = None
    hareketler = []
    devir_bakiye = 0
    toplam_giris = 0
    toplam_cikis = 0

    kasa_opts = Kasa.query.filter_by(firma_id=current_user.firma_id).all()

    if kasa_id:
        secilen_kasa = Kasa.query.get(kasa_id)
        
        # --- A) DEVİR HESABI (Başlangıç tarihinden önceki bakiye) ---
        devir_sorgu = db.session.query(
            func.sum(case((KasaHareket.islem_turu.in_([BankaIslemTuru.TAHSILAT, BankaIslemTuru.VIRMAN_GIRIS]), KasaHareket.tutar), else_=0)),
            func.sum(case((KasaHareket.islem_turu.in_([BankaIslemTuru.TEDIYE, BankaIslemTuru.VIRMAN_CIKIS]), KasaHareket.tutar), else_=0))
        ).filter(
            KasaHareket.kasa_id == kasa_id,
            KasaHareket.tarih < bas_tarih, # Seçilen tarihten öncekiler
            KasaHareket.onaylandi == True
        ).first()

        devir_giris = devir_sorgu[0] or 0
        devir_cikis = devir_sorgu[1] or 0
        devir_bakiye = devir_giris - devir_cikis

        # --- B) LİSTE SORGUSU (Tarih aralığındaki işlemler) ---
        liste = KasaHareket.query.filter(
            KasaHareket.kasa_id == kasa_id,
            KasaHareket.tarih >= bas_tarih,
            KasaHareket.tarih <= bit_tarih,
            KasaHareket.onaylandi == True
        ).order_by(KasaHareket.tarih, KasaHareket.id).all()

        # --- C) YÜRÜYEN BAKİYE HESABI ---
        anlik_bakiye = devir_bakiye
        for h in liste:
            if str(h.islem_turu) in ['BankaIslemTuru.TAHSILAT', 'BankaIslemTuru.VIRMAN_GIRIS', 'tahsilat', 'virman_giris']:
                h.giris = h.tutar
                h.cikis = 0
                anlik_bakiye += h.tutar
                toplam_giris += h.tutar
            else:
                h.giris = 0
                h.cikis = h.tutar
                anlik_bakiye -= h.tutar
                toplam_cikis += h.tutar
            
            h.yuruyen_bakiye = anlik_bakiye # Objeye geçici özellik ekliyoruz
            hareketler.append(h)

    return render_template('kasa_hareket/ekstre.html', 
                           kasa_opts=kasa_opts, 
                           secilen_kasa_id=kasa_id,
                           secilen_kasa=secilen_kasa,
                           bas_tarih=bas_tarih, 
                           bit_tarih=bit_tarih,
                           hareketler=hareketler,
                           devir_bakiye=devir_bakiye,
                           toplam_giris=toplam_giris,
                           toplam_cikis=toplam_cikis,
                           son_bakiye=devir_bakiye + toplam_giris - toplam_cikis)


