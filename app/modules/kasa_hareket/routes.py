# app/modules/kasa_hareket/routes.py

from sqlalchemy import func, case
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, g, session
from flask_login import login_required, current_user
from app.form_builder import DataGrid, FieldType
from .forms import create_kasa_hareket_form
from .services import KasaService 
from app.extensions import db, get_tenant_db # ✨ YENİ: Tenant DB
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.kasa.models import Kasa
from app.modules.firmalar.models import Donem # ✨ YENİ: Dönem modeli
from app.araclar import para_cevir
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
    tenant_db = get_tenant_db()
    
    grid = DataGrid("kasa_hareket_list", KasaHareket, "Kasa Hareketleri")
    
    grid.add_column('tarih', 'Tarih', type='date', width='100px')
    grid.add_column('belge_no', 'Makbuz No')
    grid.add_column('cari.unvan', 'Cari / Açıklama', render_func=lambda r: r.cari.unvan if r.cari else (r.aciklama or '-'))
    grid.add_column('kasa.ad', 'Kasa')
    grid.add_column('plasiyer.ad', 'Sorumlu')
    grid.add_column('tutar', 'Tutar', type=FieldType.CURRENCY)
    grid.add_column('onaylandi', 'Durum', type='badge', badge_colors={'True': 'success', 'False': 'warning'})
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kasa_hareket.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kasa_hareket.sil')
            
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'cari_id', 'karsi_banka_id', 'donem_id', 'banka_id', 'kasa_id', 'brut_tutar',
        'created_at', 'updated_at', 'muhasebe_fisi_id', 'finans_islem_id', 'komisyon_hesap_id',
        'deleted_at', 'deleted_by', 'aciklama', 'kullanici_id', 'komisyon_tutari', 'komisyon_orani',
        'karsi_kasa_id', 'plasiyer_id'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)


    
    query = tenant_db.query(KasaHareket).filter_by(firma_id=str(current_user.firma_id)).order_by(KasaHareket.tarih.desc())
    grid.process_query(query)
    
    return render_template('kasa_hareket/index.html', grid=grid)


@kasa_hareket_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_kasa_hareket_form()
    tenant_db = get_tenant_db() # ✨ VERİTABANI BAĞLANTISI
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                data['firma_id'] = str(current_user.firma_id)
                
                # ✨ GÜVENLİ DÖNEM BULMA (Artık '1' atamıyoruz, gerçek dönemi buluyoruz)
                donem_id = session.get('aktif_donem_id')
                if not donem_id:
                    aktif_donem = tenant_db.query(Donem).filter_by(firma_id=str(current_user.firma_id), aktif=True).first()
                    if aktif_donem:
                        donem_id = str(aktif_donem.id)
                    else:
                        raise Exception("Aktif bir mali dönem bulunamadı. Lütfen Sistem Yönetiminden bir dönem açın.")
                        
                data['donem_id'] = donem_id
                
                if 'tarih' in data:
                    data['tarih'] = parse_date_safe(data['tarih'])
                
                success, msg = KasaService.islem_kaydet(data, str(current_user.id))
                
                if success:
                    return jsonify({'success': True, 'message': msg, 'redirect': '/kasa-hareket'})
                else:
                    return jsonify({'success': False, 'message': msg}), 500
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f"Sistem Hatası: {str(e)}"}), 500
        else:
            return jsonify({'success': False, 'message': 'Form alanlarını kontrol ediniz.', 'errors': form.get_errors()}), 400

    return render_template('kasa_hareket/form.html', form=form)


@kasa_hareket_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    hareket = KasaService.get_by_id(id)
    if not hareket or str(hareket.firma_id) != str(current_user.firma_id):
        return render_template('errors/404.html'), 404

    form = create_kasa_hareket_form(hareket)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                data['firma_id'] = str(hareket.firma_id)
                data['donem_id'] = str(hareket.donem_id)
                
                if 'tarih' in data:
                    data['tarih'] = parse_date_safe(data['tarih'])
                
                success, msg = KasaService.islem_kaydet(data, str(current_user.id), hareket_id=str(id))
                if success:
                    return jsonify({'success': True, 'message': msg, 'redirect': '/kasa-hareket'})
                return jsonify({'success': False, 'message': msg}), 500
            except Exception as e:
                print(f"Hata Detayı: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500
            
    return render_template('kasa_hareket/form.html', form=form)


@kasa_hareket_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    success, msg = KasaService.islem_sil(str(id))
    if success:
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'message': msg}), 400


# ✨ KUSURSUZ VE ÇÖKMEYEN NUMARA ÜRETİCİ
@kasa_hareket_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    try:
        from app.models import Sayac
        sayac = tenant_db.query(Sayac).filter_by(
            firma_id=str(current_user.firma_id),
            kod='KASA',
            donem_yili=datetime.now().year
        ).first()
        
        son_no = sayac.son_no if sayac else 0
        siradaki = son_no + 1
        return jsonify({'code': f"MAK-{str(siradaki).zfill(6)}"})
        
    except Exception as e:
        # Eğer sayaç tablosunda hata olursa sistemin çökmemesi için Kasa Hareketi tablosundaki son işleme bakar
        try:
            son_hareket = tenant_db.query(KasaHareket).filter_by(
                firma_id=str(current_user.firma_id)
            ).order_by(KasaHareket.id.desc()).first()
            
            if son_hareket and son_hareket.belge_no and '-' in son_hareket.belge_no:
                parcalar = son_hareket.belge_no.rsplit('-', 1)
                if len(parcalar) == 2 and parcalar[1].isdigit():
                    yeni_num = str(int(parcalar[1]) + 1).zfill(len(parcalar[1]))
                    return jsonify({'code': f"{parcalar[0]}-{yeni_num}"})
        except:
            pass
            
        return jsonify({'code': 'MAK-000001'})


@kasa_hareket_bp.route('/ekstre', methods=['GET'])
@login_required
def ekstre():
    tenant_db = get_tenant_db() 
    
    kasa_id = request.args.get('kasa_id', type=str) 
    bas_tarih = request.args.get('bas_tarih')
    bit_tarih = request.args.get('bit_tarih')

    bugun = datetime.now().date()
    if not bas_tarih: bas_tarih = bugun.replace(day=1).strftime('%Y-%m-%d')
    if not bit_tarih: bit_tarih = bugun.strftime('%Y-%m-%d')

    secilen_kasa = None
    hareketler = []
    devir_bakiye = 0
    toplam_giris = 0
    toplam_cikis = 0

    kasa_opts = tenant_db.query(Kasa).filter_by(firma_id=str(current_user.firma_id)).all()

    if kasa_id:
        secilen_kasa = tenant_db.query(Kasa).get(kasa_id)
        
        giris_turleri = [BankaIslemTuru.TAHSILAT.value, BankaIslemTuru.VIRMAN_GIRIS.value, 'tahsilat', 'virman_giris', 'GIRIS']
        cikis_turleri = [BankaIslemTuru.TEDIYE.value, BankaIslemTuru.VIRMAN_CIKIS.value, 'tediye', 'virman_cikis', 'CIKIS']
        
        devir_sorgu = tenant_db.query(
            func.sum(case((KasaHareket.islem_turu.in_(giris_turleri), KasaHareket.tutar), else_=0)),
            func.sum(case((KasaHareket.islem_turu.in_(cikis_turleri), KasaHareket.tutar), else_=0))
        ).filter(
            KasaHareket.kasa_id == kasa_id,
            KasaHareket.tarih < bas_tarih, 
            KasaHareket.onaylandi == True
        ).first()

        devir_giris = devir_sorgu[0] or 0
        devir_cikis = devir_sorgu[1] or 0
        devir_bakiye = devir_giris - devir_cikis

        liste = tenant_db.query(KasaHareket).filter(
            KasaHareket.kasa_id == kasa_id,
            KasaHareket.tarih >= bas_tarih,
            KasaHareket.tarih <= bit_tarih,
            KasaHareket.onaylandi == True
        ).order_by(KasaHareket.tarih, KasaHareket.id).all()

        anlik_bakiye = devir_bakiye
        for h in liste:
            tur_str = str(h.islem_turu)
            if tur_str in giris_turleri or 'tahsilat' in tur_str.lower() or 'giris' in tur_str.lower():
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