# app/modules/bolge/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, flash, session
from flask_login import login_required
from app.extensions import get_tenant_db, get_tenant_info
from app.decorators import tenant_route, permission_required  # ✅ EKLE
from app.modules.bolge.models import Bolge
from app.modules.sube.models import Sube
from app.form_builder import DataGrid
from .forms import create_bolge_form
import logging

logger = logging.getLogger(__name__)

bolge_bp = Blueprint('bolge', __name__)


def get_aktif_firma_id():
    """Aktif firma ID'sini döndürür (UUID)"""
    if 'firma_id' in session:
        return session['firma_id']
    
    tenant_info = get_tenant_info()
    if tenant_info and 'firma_id' in tenant_info:
        return tenant_info['firma_id']
    
    if 'tenant_id' in session:
        return session['tenant_id']
    
    logger.warning("⚠️ Firma ID bulunamadı!")
    return None


@bolge_bp.route('/')
@login_required
@tenant_route
def index():
    """Bölge listesi"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("bolge_list", Bolge, "Bölge Listesi")
    
    grid.add_column('kod', 'Bölge Kodu', width='100px')
    grid.add_column('ad', 'Bölge Adı')
    grid.add_column('yonetici.ad_soyad', 'Bölge Müdürü') 
    grid.add_column('aciklama', 'Açıklama')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'bolge.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'bolge.sil')
    
    # ✅ Firma ID dinamik
    firma_id = get_aktif_firma_id()
    query = tenant_db.query(Bolge).filter_by(firma_id=firma_id, aktif=True)
    grid.process_query(query)
    
    return render_template('bolge/index.html', grid=grid)


@bolge_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@tenant_route
@permission_required('bolge_olustur')
def ekle():
    """Yeni bölge ekle"""
    form = create_bolge_form()
    tenant_db = None  # ✅ BAŞTA TANIMLA
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                firma_id = get_aktif_firma_id()
                if not firma_id:
                    raise Exception("Firma Kimliği Hatası: Firma ID bulunamadı.")
                
                tenant_db = get_tenant_db()
                data = form.get_data()
                
                # ✅ UUID String olarak al
                y_id = data.get('yonetici_id') or None

                bolge = Bolge(
                    firma_id=firma_id,  # ✅ Dinamik
                    kod=data['kod'],
                    ad=data['ad'],
                    yonetici_id=y_id,
                    aciklama=data.get('aciklama', ''),
                    aktif=True
                )
                
                tenant_db.add(bolge)
                tenant_db.commit()
                
                logger.info(f"✅ Bölge eklendi: {bolge.kod} - {bolge.ad}")
                return jsonify({'success': True, 'redirect': '/bolge'})
            
            except Exception as e:
                if tenant_db is not None:
                    try:
                        tenant_db.rollback()
                    except Exception as rollback_error:
                        logger.error(f"Rollback hatası: {rollback_error}")
                
                logger.error(f"❌ Bölge ekleme hatası: {e}", exc_info=True)
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('bolge/form.html', form=form)


@bolge_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])  # ✅ string:id
@login_required
@tenant_route
@permission_required('bolge_guncelle')
def duzenle(id):
    """Bölge düzenle"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "error")
        return redirect('/bolge')

    bolge = tenant_db.query(Bolge).get(id)
    if not bolge:
        flash("Bölge bulunamadı.", "error")
        return redirect('/bolge')

    form = create_bolge_form(bolge)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                bolge.kod = data['kod']
                bolge.ad = data['ad']
                bolge.yonetici_id = data.get('yonetici_id') or None
                bolge.aciklama = data.get('aciklama', '')
                
                tenant_db.commit()
                logger.info(f"✅ Bölge güncellendi: {bolge.kod}")
                return jsonify({'success': True, 'redirect': '/bolge'})
            
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"❌ Bölge güncelleme hatası: {e}", exc_info=True)
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('bolge/form.html', form=form)


@bolge_bp.route('/sil/<string:id>', methods=['POST'])  # ✅ string:id
@login_required
@tenant_route
@permission_required('bolge_sil')
def sil(id):
    """Bölge sil (soft delete)"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Bağlantı yok'}), 500

    bolge = tenant_db.query(Bolge).get(id)
    if not bolge:
        return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
    
    # Şube kontrolü
    sube_sayisi = tenant_db.query(Sube).filter_by(bolge_id=id).count()
    if sube_sayisi > 0:
        return jsonify({
            'success': False, 
            'message': f'Bu bölgeye bağlı {sube_sayisi} şube var! Önce şubeleri silin.'
        }), 400
    
    try:
        # Soft Delete
        bolge.aktif = False
        if hasattr(bolge, 'silinmis'):
            bolge.silinmis = True
        
        tenant_db.commit()
        logger.info(f"✅ Bölge silindi: {bolge.kod}")
        return jsonify({'success': True, 'message': 'Bölge silindi.'})
    
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"❌ Bölge silme hatası: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500