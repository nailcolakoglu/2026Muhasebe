from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
# db importunu kaldırdık veya sadece tip tanımları için tutabiliriz ama session için kullanmayacağız.
from app.extensions import get_tenant_db 
from app.modules.stok.models import StokKart
from app.modules.kategori.models import StokKategori
from app.form_builder import DataGrid
from .forms import create_kategori_form

kategori_bp = Blueprint('kategori', __name__)

@kategori_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db() # Tenant bağlantısı
    
    # Grid yapısı
    grid = DataGrid("kategori_list", StokKategori, "Stok Kategorileri")
    grid.add_column('ad', 'Kategori Adı')
    grid.add_column('ust_kategori.ad', 'Üst Kategori') # İlişkisel alan
    
    grid.hide_column('id').hide_column('firma_id').hide_column('ust_kategori_id')

    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kategori.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kategori.sil')
    
    # SORGULARDA GOLDEN RULE: tenant_db.query()
    # Not: DataGrid'in process_query metodu SQLAlchemy Query objesi bekler.
    query = tenant_db.query(StokKategori).filter_by(firma_id=current_user.firma_id).order_by(StokKategori.ust_kategori_id, StokKategori.ad)
    
    grid.process_query(query)
    
    return render_template('kategori/index.html', grid=grid)

@kategori_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    # Form fonksiyonu artık tenant_db'ye ihtiyaç duyabilir (Selectbox için), 
    # ancak form içinde get_tenant_db çağırdığımız için parametre gerekmez.
    form = create_kategori_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db() # İşlem için session aç
            try:
                data = form.get_data()
                
                ust_id = data.get('ust_kategori_id')
                if not ust_id or str(ust_id) == '0': 
                    ust_id = None
                
                kategori = StokKategori(
                    firma_id=current_user.firma_id,
                    ad=data['ad'],
                    ust_kategori_id=ust_id
                )
                
                tenant_db.add(kategori)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Kategori eklendi.', 'redirect': '/kategori'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
        else:
             return jsonify({'success': False, 'message': 'Validasyon hatası', 'errors': form.get_errors()}), 400
             
    return render_template('kategori/form.html', form=form)

@kategori_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    # get_or_404 tenant session'da doğrudan yoktur, elle kontrol ederiz veya extension kullanırız.
    # Güvenli yol:
    kategori = tenant_db.get(StokKategori, id)
    if not kategori:
        abort(404)
        
    form = create_kategori_form(kategori)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                ust_id = data.get('ust_kategori_id')
                if not ust_id or str(ust_id) == '0': 
                    ust_id = None
                
                # Döngüsel Kontrol
                if ust_id and int(ust_id) == kategori.id:
                    return jsonify({'success': False, 'message': 'Kategori kendi kendisinin alt kategorisi olamaz.'}), 400
                
                kategori.ad = data['ad']
                kategori.ust_kategori_id = ust_id
                
                tenant_db.commit() # tenant_db session'ı commit ediyoruz
                return jsonify({'success': True, 'message': 'Kategori güncellendi.', 'redirect': '/kategori'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kategori/form.html', form=form)

@kategori_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    kategori = tenant_db.get(StokKategori, id)
    if not kategori:
        return jsonify({'success': False, 'message': 'Kategori bulunamadı.'}), 404

    try:
        # 1.Kontrol: Altında ürün var mı? (StokKart sorgusu da tenant_db üzerinden olmalı)
        urun_sayisi = tenant_db.query(StokKart).filter_by(kategori_id=id).count()
        if urun_sayisi > 0:
            return jsonify({'success': False, 'message': f'Bu kategoriye bağlı {urun_sayisi} adet ürün var. Önce onları taşıyın veya silin.'}), 400
            
        # 2.Kontrol: Alt kategorisi var mı? (StokKategori sorgusu da tenant_db üzerinden)
        alt_kat_sayisi = tenant_db.query(StokKategori).filter_by(ust_kategori_id=id).count()
        if alt_kat_sayisi > 0:
            return jsonify({'success': False, 'message': f'Bu kategoriye bağlı {alt_kat_sayisi} adet alt kategori var. Silinemez.'}), 400

        tenant_db.delete(kategori)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Kategori silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500