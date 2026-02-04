# app/modules/sube/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, flash
from flask_login import login_required, current_user
from app.form_builder import FieldType
from app.extensions import get_tenant_db, get_tenant_info  # 👈 Firebird Bağlantısı
from app.modules.sube.models import Sube
from app.modules.bolge.models import Bolge
from app.form_builder import DataGrid
from .forms import create_sube_form

sube_bp = Blueprint('sube', __name__)

def get_aktif_firma_id():
    """
    Güvenli Firma ID Çözümleyici (UUID Destekli)
    Artık int() çevrimi yapmıyoruz, doğrudan string/UUID dönüyoruz.
    """
    val = None
    
    # 1. Kaynaktan Al
    if current_user.is_authenticated and getattr(current_user, 'firma_id', None):
        val = current_user.firma_id
    elif get_tenant_info() and get_tenant_info().get('firma_id'):
        val = get_tenant_info().get('firma_id')
    
    # UUID String olarak dönecek, Integer kontrolüne gerek yok.
    # Boş string veya None kontrolü yeterli.
    if val and str(val).strip():
        return str(val)
            
    return None


@sube_bp.route('/')
@login_required
def index():
    # 1. Bağlantıyı Al
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
    
    # 2. Firebird Sorgusu (MySQL query yerine)
    # Firma ID = 1 (Tenant DB yapısı)
    query = tenant_db.query(Sube).filter_by(firma_id=1)
    grid.process_query(query)
    
    return render_template('sube/index.html', grid=grid)

@sube_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_sube_form()
    
    if request.method == 'POST':
        form.process_request(request.form)  
        if form.validate():
            try:
                firma_id = get_aktif_firma_id()
                if not firma_id:
                    raise Exception("Firma Kimliği Hatası: Firma ID bulunamadı.")
                tenant_db = get_tenant_db() # 👈 Firebird
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
                if tenant_db: tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('sube/form.html', form=form)

@sube_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/sube')

    sube = tenant_db.query(Sube).get(id)
    if not sube: return redirect('/sube')

    form = create_sube_form(sube)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                sube.kod = data['kod']
                sube.ad = data['ad']
                sube.bolge_id = int(data['bolge_id']) if data.get('bolge_id') else None
                sube.adres = data['adres']
                sube.sehir_id = int(data['sehir_id']) if data.get('sehir_id') else None
                sube.ilce_id = int(data['ilce_id']) if data.get('ilce_id') else None
                sube.telefon = data['telefon']
                sube.aktif = str(data.get('aktif')).lower() in ['true', '1', 'on']
                
                tenant_db.commit()
                return jsonify({'success': True, 'redirect': '/sube'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('sube/form.html', form=form)

@sube_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return jsonify({'success': False, 'message': 'Bağlantı yok'}), 500

    sube = tenant_db.query(Sube).get(id)
    if not sube: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
    
    try:
        # Soft Delete (Mixin varsa)
        sube.aktif = False
        sube.silinmis = True
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Şube silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500