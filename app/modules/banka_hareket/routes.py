# app/modules/banka_hareket/routes.py

from flask import Blueprint, render_template, request, jsonify, flash, g, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.form_builder import DataGrid, FieldType
from .forms import create_banka_hareket_form
from .services import BankaHareketService
from app.modules.banka_hareket.models import BankaHareket
from sqlalchemy import func, case

from app.modules.banka.models import BankaHesap
from app.modules.firmalar.models import Donem
from app.enums import BankaIslemTuru
from app.extensions import get_tenant_db # ✨ YENİ: Tenant DB Importu

banka_hareket_bp = Blueprint('banka_hareket', __name__)

@banka_hareket_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db() # ✨ TENANT DB SORGUSU
    
    grid = DataGrid("banka_hareket_list", BankaHareket, "Banka Hareketleri")
    
    grid.add_column('tarih', 'Tarih', type='date', width='100px')
    grid.add_column('belge_no', 'Dekont No')
    grid.add_column('banka.banka_adi', 'Banka')
    
    def render_aciklama(row):
        if row.cari: return f"{row.cari.unvan}"
        if row.kasa: return f"Kasa: {row.kasa.ad}"
        if row.karsi_banka: return f"Transfer: {row.karsi_banka.banka_adi}"
        return row.aciklama or '-'
        
    grid.add_column('aciklama', 'Karşı Hesap / Açıklama', render_func=render_aciklama)
    
    grid.add_column('islem_turu', 'İşlem', type='badge', 
                    badge_colors={'TAHSILAT': 'success', 'TEDIYE': 'danger', 'VIRMAN_GIRIS': 'primary', 'VIRMAN_CIKIS': 'warning',
                                  'tahsilat': 'success', 'tediye': 'danger', 'virman_giris': 'primary', 'virman_cikis': 'warning'})
    
    grid.add_column('tutar', 'Tutar', type=FieldType.CURRENCY)
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'banka_hareket.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'banka_hareket.sil')
        
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'cari_id', 'karsi_banka_id', 'donem_id', 'banka_id', 'kasa_id', 'brut_tutar',
        'created_at', 'updated_at', 'muhasebe_fisi_id', 'finans_islem_id', 'komisyon_hesap_id',
        'deleted_at', 'deleted_by', 'aciklama', 'kullanici_id', 'komisyon_tutari', 'komisyon_orani'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    
    query = tenant_db.query(BankaHareket).filter_by(firma_id=str(current_user.firma_id)).order_by(BankaHareket.tarih.desc())
    
    grid.process_query(query)
    
    return render_template('banka_hareket/index.html', grid=grid)

@banka_hareket_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_banka_hareket_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db()
            data = form.get_data()
            data['firma_id'] = str(current_user.firma_id)
            
            # Dönemi Güvenli Bulma
            donem_id = session.get('aktif_donem_id')
            if not donem_id:
                ad = tenant_db.query(Donem).filter_by(firma_id=str(current_user.firma_id), aktif=True).first()
                donem_id = str(ad.id) if ad else '1'
            data['donem_id'] = donem_id
            
            try:
                success, message = BankaHareketService.islem_kaydet(data, str(current_user.id))
                if success:
                    return jsonify({'success': True, 'message': message, 'redirect': '/banka-hareket'})
                return jsonify({'success': False, 'message': message}), 500
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f"Servis Hatası: {str(e)}"}), 500
    
    return render_template('banka_hareket/form.html', form=form)

# ✨ UUID UYUMU: <int:id> -> <string:id>
@banka_hareket_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    hareket = BankaHareketService.get_by_id(str(id))
    if not hareket or str(hareket.firma_id) != str(current_user.firma_id):
        return render_template('errors/404.html'), 404

    form = create_banka_hareket_form(hareket)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            data['firma_id'] = str(hareket.firma_id)
            data['donem_id'] = str(hareket.donem_id)

            try:
                success, message = BankaHareketService.islem_kaydet(data, str(current_user.id), hareket_id=str(id))
                if success:
                    return jsonify({'success': True, 'message': message, 'redirect': '/banka-hareket'})
                return jsonify({'success': False, 'message': message}), 500
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('banka_hareket/form.html', form=form)

# ✨ UUID UYUMU: <int:id> -> <string:id>
@banka_hareket_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    success, message = BankaHareketService.islem_sil(str(id))
    status = 200 if success else 400
    return jsonify({'success': success, 'message': message}), status           

@banka_hareket_bp.route('/ekstre', methods=['GET'])
@login_required
def ekstre():
    tenant_db = get_tenant_db() # ✨ YENİ
    
    # ✨ UUID İÇİN type=str YAPILDI
    banka_id = request.args.get('banka_id', type=str)
    bas_tarih = request.args.get('bas_tarih')
    bit_tarih = request.args.get('bit_tarih')

    bugun = datetime.now().date()
    if not bas_tarih: bas_tarih = bugun.replace(day=1).strftime('%Y-%m-%d')
    if not bit_tarih: bit_tarih = bugun.strftime('%Y-%m-%d')

    secilen_banka = None
    hareketler = []
    devir_bakiye = 0
    toplam_giris = 0
    toplam_cikis = 0

    # ✨ TENANT DB SORGUSU
    banka_opts = tenant_db.query(BankaHesap).filter_by(firma_id=str(current_user.firma_id)).all()

    if banka_id:
        secilen_banka = tenant_db.query(BankaHesap).get(banka_id)
        
        giris_turleri = [BankaIslemTuru.TAHSILAT.value, BankaIslemTuru.VIRMAN_GIRIS.value, BankaIslemTuru.POS_TAHSILAT.value, 'TAHSILAT', 'VIRMAN_GIRIS']
        cikis_turleri = [BankaIslemTuru.TEDIYE.value, BankaIslemTuru.VIRMAN_CIKIS.value, 'TEDIYE', 'VIRMAN_CIKIS']

        # --- A) DEVİR HESABI ---
        devir_sorgu = tenant_db.query(
            func.sum(case((BankaHareket.islem_turu.in_(giris_turleri), BankaHareket.tutar), else_=0)),
            func.sum(case((BankaHareket.islem_turu.in_(cikis_turleri), BankaHareket.tutar), else_=0))
        ).filter(
            BankaHareket.banka_id == banka_id,
            BankaHareket.tarih < bas_tarih, 
        ).first()

        devir_giris = devir_sorgu[0] or 0
        devir_cikis = devir_sorgu[1] or 0
        devir_bakiye = devir_giris - devir_cikis

        # --- B) LİSTE SORGUSU ---
        liste = tenant_db.query(BankaHareket).filter(
            BankaHareket.banka_id == banka_id,
            BankaHareket.tarih >= bas_tarih,
            BankaHareket.tarih <= bit_tarih
        ).order_by(BankaHareket.tarih, BankaHareket.id).all()

        # --- C) YÜRÜYEN BAKİYE HESABI ---
        anlik_bakiye = devir_bakiye
        
        for h in liste:
            tur_str = str(h.islem_turu.value) if hasattr(h.islem_turu, 'value') else str(h.islem_turu)
            
            is_giris = False
            if 'tahsilat' in tur_str.lower() or 'giris' in tur_str.lower() or 'pos' in tur_str.lower():
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


# ✨ KUSURSUZ VE ÇÖKMEYEN NUMARA ÜRETİCİ
@banka_hareket_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    try:
        from app.models import Sayac
        sayac = tenant_db.query(Sayac).filter_by(
            firma_id=str(current_user.firma_id),
            kod='BANKA',
            donem_yili=datetime.now().year
        ).first()
        
        son_no = sayac.son_no if sayac else 0
        siradaki = son_no + 1
        return jsonify({'code': f"BHK-{str(siradaki).zfill(6)}"})
        
    except Exception as e:
        try:
            son_hareket = tenant_db.query(BankaHareket).filter_by(
                firma_id=str(current_user.firma_id)
            ).order_by(BankaHareket.id.desc()).first()
            
            if son_hareket and son_hareket.belge_no and '-' in son_hareket.belge_no:
                parcalar = son_hareket.belge_no.rsplit('-', 1)
                if len(parcalar) == 2 and parcalar[1].isdigit():
                    yeni_num = str(int(parcalar[1]) + 1).zfill(len(parcalar[1]))
                    return jsonify({'code': f"{parcalar[0]}-{yeni_num}"})
        except: pass
            
        return jsonify({'code': 'BHK-000001'})