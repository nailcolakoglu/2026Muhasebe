# app/modules/depo/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, flash, url_for
from flask_login import login_required, current_user
from app.extensions import get_tenant_db
from app.modules.depo.models import Depo
from app.form_builder import DataGrid
from .forms import create_depo_form

depo_bp = Blueprint('depo', __name__)

@depo_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("depo_list", Depo, "Depo Listesi")
    
    grid.add_column('kod', 'Kod')
    grid.add_column('ad', 'Ad')
    grid.add_column('sube.ad', 'Şube')
    grid.add_column('plasiyer.ad_soyad', 'Sorumlu Plasiyer') 
    grid.add_column('aktif', 'Durum', type='switch')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'depo.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'depo.sil')
    
    # 👈 Firebird Sorgusu
    query = tenant_db.query(Depo).filter_by(firma_id=1)
    grid.process_query(query)
    
    return render_template('depo/index.html', grid=grid)

@depo_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_depo_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db()
            if not tenant_db: return jsonify({'success': False, 'message': 'Bağlantı hatası'}), 500

            try:
                data = form.get_data()
                
                # Plasiyer ID '0' veya boş gelirse None yap
                p_id = data.get('plasiyer_id')
                if not p_id or str(p_id) == '0': p_id = None
                
                depo = Depo(
                    firma_id=1, # Tenant ID Sabit
                    kod=data['kod'],
                    ad=data['ad'],
                    sube_id=data['sube_id'],
                    plasiyer_id=p_id,
                    aktif=str(data.get('aktif')).lower() in ['true', '1', 'on']
                )
                
                tenant_db.add(depo)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Depo eklendi.', 'redirect': '/depo'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('depo/form.html', form=form)

@depo_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/depo')

    depo = tenant_db.query(Depo).get(id)
    if not depo: return redirect('/depo')

    form = create_depo_form(depo)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                p_id = data.get('plasiyer_id')
                if not p_id or str(p_id) == '0': p_id = None
                
                depo.kod = data['kod']
                depo.ad = data['ad']
                depo.sube_id = data['sube_id']
                depo.plasiyer_id = p_id
                depo.aktif = str(data.get('aktif')).lower() in ['true', '1', 'on']
                
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Depo güncellendi.', 'redirect': '/depo'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('depo/form.html', form=form)

@depo_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    try:
        depo = tenant_db.query(Depo).get(id)
        if not depo: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
        
        # Stok kontrolü eklenebilir
        # if depo.stoklar.count() > 0: ...

        tenant_db.delete(depo)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Depo silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500