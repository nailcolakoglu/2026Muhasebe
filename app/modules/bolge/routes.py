# app/modules/bolge/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, flash
from flask_login import login_required
from app.extensions import get_tenant_db 
from app.modules.bolge.models import Bolge
from app.modules.sube.models import Sube
from app.form_builder import DataGrid
from .forms import create_bolge_form

bolge_bp = Blueprint('bolge', __name__)

@bolge_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("bolge_list", Bolge, "Bölge Listesi")
    
    grid.add_column('kod', 'Bölge Kodu', width='100px')
    grid.add_column('ad', 'Bölge Adı')
    # İlişki üzerinden yönetici adı
    grid.add_column('yonetici.ad_soyad', 'Bölge Müdürü') 
    grid.add_column('aciklama', 'Açıklama')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'bolge.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'bolge.sil')
    
    # Firebird Sorgusu
    query = tenant_db.query(Bolge).filter_by(firma_id=1)
    grid.process_query(query)
    
    return render_template('bolge/index.html', grid=grid)

@bolge_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_bolge_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                tenant_db = get_tenant_db()
                data = form.get_data()
                
                # 🚨 DÜZELTME: int() KALDIRILDI. UUID String olarak gelmeli.
                y_id = data['yonetici_id'] if data.get('yonetici_id') else None

                bolge = Bolge(
                    firma_id=1,
                    kod=data['kod'],
                    ad=data['ad'],
                    yonetici_id=y_id,
                    aciklama=data['aciklama'],
                    aktif=True
                )
                
                tenant_db.add(bolge)
                tenant_db.commit()
                # Frontend FormBuilder JSON bekler
                return jsonify({'success': True, 'redirect': '/bolge'})
            except Exception as e:
                if tenant_db: tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('bolge/form.html', form=form)

@bolge_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/bolge')

    bolge = tenant_db.query(Bolge).get(id)
    if not bolge: return redirect('/bolge')

    form = create_bolge_form(bolge)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                bolge.kod = data['kod']
                bolge.ad = data['ad']
                # 🚨 DÜZELTME: int() KALDIRILDI
                bolge.yonetici_id = data['yonetici_id'] if data.get('yonetici_id') else None
                bolge.aciklama = data['aciklama']
                
                tenant_db.commit()
                return jsonify({'success': True, 'redirect': '/bolge'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('bolge/form.html', form=form)

@bolge_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return jsonify({'success': False, 'message': 'Bağlantı yok'}), 500

    bolge = tenant_db.query(Bolge).get(id)
    if not bolge: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
    
    # Şube Kontrolü (Firebird üzerinden)
    bagli_sube_sayisi = tenant_db.query(Sube).filter_by(bolge_id=id).count()
    
    if bagli_sube_sayisi > 0:
        return jsonify({
            'success': False, 
            'message': f'Bu bölgeye bağlı {bagli_sube_sayisi} adet şube bulunmaktadır. Önce şubeleri başka bölgeye aktarın.'
        }), 400
        
    try:
        # Soft Delete
        bolge.aktif = False
        bolge.silinmis = True
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Bölge başarıyla silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500