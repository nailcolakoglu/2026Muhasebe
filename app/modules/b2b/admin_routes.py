# app/modules/b2b/admin_routes.py

from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import login_required, current_user
from app.extensions import get_tenant_db
from app.form_builder import DataGrid, FieldType
from app.modules.b2b.models import B2BKullanici
from app.modules.b2b.admin_forms import create_b2b_kullanici_form
from app.modules.b2b.services import B2BYonetimService

# Dikkat: Blueprint adı ve url_prefix B2B portaldan farklıdır!
b2b_admin_bp = Blueprint('b2b_admin', __name__)

@b2b_admin_bp.route('/kullanicilar')
@login_required # flask_login kullanıyoruz (Çünkü bu ekrana ERP personeli girecek)
def index():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("b2b_users_grid", B2BKullanici, "B2B Müşteri / Bayi Hesapları", per_page=20)
    
    grid.add_column('ad_soyad', 'Yetkili Kişi', sortable=True)
    grid.add_column('gorunum_cari', 'Bağlı Olduğu Cari') # Modelde yazdığımız property
    grid.add_column('email', 'Giriş E-Postası')
    #grid.add_column('aktif', 'Portal Durumu', type='boolean')
    grid.add_column('son_giris_tarihi', 'Son Giriş', type=FieldType.DATE)
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'b2b_admin.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'b2b_admin.sil')
        
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sifre_hash', 'cari_id',
        'created_at', 'updated_at', 'muhasebe_hesap_id', 'yetki_ekstre_gor', 'yetki_kredi_karti_odeme',
        'deleted_at', 'deleted_by', 'telefon', 'yetki_siparis_ver'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    query = tenant_db.query(B2BKullanici).order_by(B2BKullanici.created_at.desc())
    grid.process_query(query)
    
    return render_template(
        'base_grid.html', 
        grid=grid,
        endpoint='b2b_admin.index',
        add_url=url_for('b2b_admin.ekle'),
        add_btn_text='Yeni B2B Hesabı'
    )

@b2b_admin_bp.route('/kullanici/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_b2b_kullanici_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = B2BYonetimService.kullanici_kaydet(form.get_data(), current_user.firma_id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('b2b_admin.index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('base_form.html', form=form)

@b2b_admin_bp.route('/kullanici/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    kullanici = tenant_db.get(B2BKullanici, id)
    if not kullanici: return jsonify({'success': False}), 404
    
    form = create_b2b_kullanici_form(kullanici)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = B2BYonetimService.kullanici_kaydet(form.get_data(), current_user.firma_id, user_id=id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('b2b_admin.index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('base_form.html', form=form)

@b2b_admin_bp.route('/kullanici/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    kullanici = tenant_db.get(B2BKullanici, id)
    if not kullanici: return jsonify({'success': False}), 404
    
    try:
        tenant_db.delete(kullanici)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Hesap başarıyla silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500