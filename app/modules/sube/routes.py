# app/modules/sube/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, flash, session
from flask_login import login_required, current_user
from app.form_builder import FieldType
from app.extensions import get_tenant_db, get_tenant_info  # 👈 Firebird Bağlantısı
from app.decorators import tenant_route, permission_required
from app.modules.sube.models import Sube
from app.modules.bolge.models import Bolge
from app.form_builder import DataGrid
from .forms import create_sube_form
import logging

logger = logging.getLogger(__name__)

sube_bp = Blueprint('sube', __name__)

def get_aktif_firma_id():
    """
    Güvenli Firma ID Çözümleyici (UUID Destekli)
    Artık int() çevrimi yapmıyoruz, doğrudan string/UUID dönüyoruz.
    Aktif firma ID'sini döndürür
    
    Returns:
        str: Firma ID (UUID)
    """
    # Öncelik 1: Session'dan
    if 'firma_id' in session:
        return session['firma_id']
    
    # Öncelik 2: Tenant info'dan
    tenant_info = get_tenant_info()
    if tenant_info and 'firma_id' in tenant_info:
        return tenant_info['firma_id']
    
    # Öncelik 3: Tenant ID = Firma ID (senin mimarinde)
    if 'tenant_id' in session:
        return session['tenant_id']
    
    logger.warning("⚠️ Firma ID bulunamadı!")
    return None



@sube_bp.route('/')
@login_required
@tenant_route
def index():
    """Şube listesi"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    # Grid Yapısı
    grid = DataGrid("sube_list", Sube, "Şube Listesi")
    
    grid.add_column('kod', 'Şube Kodu', width='100px')
    grid.add_column('ad', 'Şube Adı')
    grid.add_column('bolge.ad', 'Bağlı Olduğu Bölge') 
    grid.add_column('sehir.ad', 'Şehir')
    grid.add_column('aktif', 'Durum', type=FieldType.SWITCH)
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'sube.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'sube.sil')
    
    # Firma ID al
    firma_id = get_aktif_firma_id()
    
    # Query
    query = tenant_db.query(Sube).filter_by(firma_id=firma_id, aktif=True)
    grid.process_query(query)
    
    return render_template('sube/index.html', grid=grid)


@sube_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@tenant_route
@permission_required('sube_olustur')
def ekle():
    form = create_sube_form()
    tenant_db = None  # ✅ BAŞTA TANIMLA!
    
    if request.method == 'POST':
        form.process_request(request.form)  
        if form.validate():
            try:
                firma_id = get_aktif_firma_id()
                if not firma_id:
                    raise Exception("Firma Kimliği Hatası: Firma ID bulunamadı.")
                
                tenant_db = get_tenant_db()  # ✅ Artık üstte tanımlı
                data = form.get_data()
                
                # Bölge ID (Integer)
                b_id = (data['bolge_id']) if data.get('bolge_id') else None
                
                # Şehir ve İlçe (Integer)
                s_id = (data['sehir_id']) if data.get('sehir_id') else None
                i_id = (data['ilce_id']) if data.get('ilce_id') else None

                sube = Sube(
                    firma_id=firma_id,
                    kod=data['kod'],
                    ad=data['ad'],
                    bolge_id=b_id,
                    adres=data['adres'],
                    sehir_id=s_id,
                    ilce_id=i_id,
                    telefon=data['telefon'],
                    aktif=True
                )
                
                tenant_db.add(sube)
                tenant_db.commit()
                return jsonify({'success': True, 'redirect': '/sube'})
            
            except Exception as e:
                # ✅ DÜZELTME: tenant_db kontrolü
                if tenant_db is not None:  # ✅ is not None kullan
                    try:
                        tenant_db.rollback()
                    except Exception as rollback_error:
                        logger.error(f"Rollback hatası: {rollback_error}")
                
                logger.error(f"❌ Şube ekleme hatası: {e}", exc_info=True)
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('sube/form.html', form=form)
    
    
@sube_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
@tenant_route
@permission_required('sube_guncelle')
def duzenle(id):
    """Şube düzenle"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        return redirect('/sube')

    sube = tenant_db.query(Sube).get(id)
    if not sube:
        flash("Şube bulunamadı.", "error")
        return redirect('/sube')

    form = create_sube_form(sube)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                sube.kod = data['kod']
                sube.ad = data['ad']
                sube.bolge_id = data.get('bolge_id') or None
                sube.adres = data.get('adres')
                sube.sehir_id = data.get('sehir_id') or None
                sube.ilce_id = data.get('ilce_id') or None
                sube.telefon = data.get('telefon')
                sube.aktif = str(data.get('aktif', '')).lower() in ['true', '1', 'on']
                
                tenant_db.commit()
                logger.info(f"✅ Şube güncellendi: {sube.kod}")
                return jsonify({'success': True, 'redirect': '/sube'})
            
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"❌ Şube güncelleme hatası: {e}", exc_info=True)
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('sube/form.html', form=form)


# ✅ YENİ (UUID desteği):
@sube_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
@tenant_route
@permission_required('sube_sil')
def sil(id):
    """Şube sil (soft delete)"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Bağlantı yok'}), 500

    sube = tenant_db.query(Sube).get(id)
    if not sube:
        return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
    
    try:
        # Soft Delete
        sube.aktif = False
        if hasattr(sube, 'silinmis'):
            sube.silinmis = True
        
        tenant_db.commit()
        logger.info(f"✅ Şube silindi: {sube.kod}")
        return jsonify({'success': True, 'message': 'Şube silindi.'})
    
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"❌ Şube silme hatası: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
