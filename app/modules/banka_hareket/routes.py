# app/modules/banka_hareket/routes.py

from flask import Blueprint, render_template, request, jsonify, flash, g
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.form_builder import DataGrid, FieldType
from .forms import create_banka_hareket_form
from .services import BankaHareketService
from app.modules.banka_hareket.models import BankaHareket
from sqlalchemy import func, case

from app.modules.banka.models import BankaHesap
from app.enums import BankaIslemTuru
from app.extensions import db

banka_hareket_bp = Blueprint('banka_hareket', __name__)

@banka_hareket_bp.route('/')
@login_required
def index():
    grid = DataGrid("banka_hareket_list", BankaHareket, "Banka Hareketleri")
    
    grid.add_column('tarih', 'Tarih', type=FieldType.DATE, width='100px')
    grid.add_column('belge_no', 'Dekont No')
    grid.add_column('banka.banka_adi', 'Banka')
    
    # Custom Render ile akıllı açıklama
    def render_aciklama(row):
        if row.cari: return f"{row.cari.unvan}"
        if row.kasa: return f"Kasa: {row.kasa.ad}"
        if row.karsi_banka: return f"Transfer: {row.karsi_banka.banka_adi}"
        return row.aciklama
        
    grid.add_column('aciklama', 'Cari / Açıklama', render_func=render_aciklama)
    
    grid.add_column('islem_turu', 'İşlem', type='badge', 
                    badge_colors={'tahsilat': 'success', 'tediye': 'danger', 'virman_giris': 'primary', 'virman_cikis': 'warning'})
    
    grid.add_column('tutar', 'Tutar', type=FieldType.CURRENCY)
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'banka_hareket.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'banka_hareket.sil')
    
    query = BankaHareket.query.filter_by(firma_id=g.firma.id).order_by(BankaHareket.tarih.desc())
    grid.process_query(query)
    
    return render_template('banka_hareket/index.html', grid=grid)

@banka_hareket_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    b_opts, c_opts, k_opts = BankaHareketService.get_form_options(g.firma.id)
    form = create_banka_hareket_form(banka_opts=b_opts, cari_opts=c_opts, kasa_opts=k_opts)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            data['firma_id'] = g.firma.id
            data['donem_id'] = g.donem.id
            
            success, message = BankaHareketService.islem_kaydet(data, current_user.id)
            if success:
                return jsonify({'success': True, 'message': message, 'redirect': '/banka-hareket'})
            return jsonify({'success': False, 'message': message}), 500
    
    return render_template('banka_hareket/form.html', form=form)

@banka_hareket_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    hareket = BankaHareketService.get_by_id(id)
    if not hareket or hareket.firma_id != g.firma.id:
        return render_template('404.html'), 404

    b_opts, c_opts, k_opts = BankaHareketService.get_form_options(g.firma.id)
    form = create_banka_hareket_form(hareket, b_opts, c_opts, k_opts)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            data['firma_id'] = g.firma.id
            data['donem_id'] = g.donem.id

            success, message = BankaHareketService.islem_kaydet(data, current_user.id, hareket_id=id)
            if success:
                return jsonify({'success': True, 'message': message, 'redirect': '/banka-hareket'})
            return jsonify({'success': False, 'message': message}), 500
                
    return render_template('banka_hareket/form.html', form=form)

@banka_hareket_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    success, message = BankaHareketService.islem_sil(id)
    status = 200 if success else 400
    return jsonify({'success': success, 'message': message}), status           

@banka_hareket_bp.route('/ekstre', methods=['GET'])
@login_required
def ekstre():
    # 1.Filtreleri Al
    banka_id = request.args.get('banka_id', type=int)
    bas_tarih = request.args.get('bas_tarih')
    bit_tarih = request.args.get('bit_tarih')

    # Varsayılan: Bu ayın başı ve bugün
    bugun = datetime.now().date()
    if not bas_tarih: bas_tarih = bugun.replace(day=1).strftime('%Y-%m-%d')
    if not bit_tarih: bit_tarih = bugun.strftime('%Y-%m-%d')

    secilen_banka = None
    hareketler = []
    devir_bakiye = 0
    toplam_giris = 0
    toplam_cikis = 0

    # Banka Seçenekleri (Sadece firmanın bankaları)
    banka_opts = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()

    if banka_id:
        secilen_banka = BankaHesap.query.get(banka_id)
        
        # Giriş Türleri (Tahsilat, Gelen Havale, POS, Virman Giriş)
        giris_turleri = [
            BankaIslemTuru.TAHSILAT, 
            BankaIslemTuru.VIRMAN_GIRIS, 
            BankaIslemTuru.POS_TAHSILAT
        ]
        
        # Çıkış Türleri (Tediye, Giden Havale, Virman Çıkış)
        cikis_turleri = [
            BankaIslemTuru.TEDIYE, 
            BankaIslemTuru.VIRMAN_CIKIS
        ]

        # --- A) DEVİR HESABI (Başlangıç tarihinden önceki bakiye) ---
        devir_sorgu = db.session.query(
            func.sum(case((BankaHareket.islem_turu.in_(giris_turleri), BankaHareket.tutar), else_=0)),
            func.sum(case((BankaHareket.islem_turu.in_(cikis_turleri), BankaHareket.tutar), else_=0))
        ).filter(
            BankaHareket.banka_id == banka_id,
            BankaHareket.tarih < bas_tarih, # Tarihten öncekiler
            # BankaHareket modelinizde 'onaylandi' sütunu varsa ekleyin, yoksa kaldırın:
            # BankaHareket.onaylandi == True 
        ).first()

        devir_giris = devir_sorgu[0] or 0
        devir_cikis = devir_sorgu[1] or 0
        devir_bakiye = devir_giris - devir_cikis

        # --- B) LİSTE SORGUSU (Tarih aralığındaki işlemler) ---
        liste = BankaHareket.query.filter(
            BankaHareket.banka_id == banka_id,
            BankaHareket.tarih >= bas_tarih,
            BankaHareket.tarih <= bit_tarih
            # BankaHareket.onaylandi == True
        ).order_by(BankaHareket.tarih, BankaHareket.id).all()

        # --- C) YÜRÜYEN BAKİYE HESABI ---
        anlik_bakiye = devir_bakiye
        
        # Enum karşılaştırması için string setleri
        str_giris = [str(t) for t in giris_turleri] + [str(t.value) for t in giris_turleri if hasattr(t, 'value')]
        
        for h in liste:
            tur_str = str(h.islem_turu.value) if hasattr(h.islem_turu, 'value') else str(h.islem_turu)
            
            # Giriş mi Çıkış mı?
            is_giris = False
            # Basit kontrol: İçinde 'tahsilat', 'giris' veya 'pos' geçiyorsa giriştir
            if 'tahsilat' in tur_str.lower() or 'giris' in tur_str.lower():
                is_giris = True
            
            if is_giris:
                h.giris = h.tutar
                h.cikis = 0
                anlik_bakiye += h.tutar
                toplam_giris += h.tutar
            else:
                h.giris = 0
                h.cikis = h.tutar
                anlik_bakiye -= h.tutar
                toplam_cikis += h.tutar
            
            h.yuruyen_bakiye = anlik_bakiye
            hareketler.append(h)

    return render_template('banka_hareket/ekstre.html', 
                           banka_opts=banka_opts, 
                           secilen_banka_id=banka_id,
                           secilen_banka=secilen_banka,
                           bas_tarih=bas_tarih, 
                           bit_tarih=bit_tarih,
                           hareketler=hareketler,
                           devir_bakiye=devir_bakiye,
                           toplam_giris=toplam_giris,
                           toplam_cikis=toplam_cikis,
                           son_bakiye=devir_bakiye + toplam_giris - toplam_cikis)


