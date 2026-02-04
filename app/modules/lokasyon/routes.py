# app/modules/lokasyon/routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from app.extensions import get_tenant_db
from app.modules.lokasyon.models import Sehir, Ilce
from app.modules.sube.models import Sube 
from app.form_builder import DataGrid, FieldType
from .forms import get_sehir_form, get_ilce_form

lokasyon_bp = Blueprint('lokasyon', __name__)

# =========================================================
# 1. ŞEHİR (İL) İŞLEMLERİ
# =========================================================

@lokasyon_bp.route('/sehirler')
@login_required
def sehir_listesi():
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("grid_sehirler", Sehir, title="Şehir Listesi")
    
    grid.columns = []
    grid.add_column("kod", "Plaka Kodu", width="100px", sortable=True)
    grid.add_column("ad", "Şehir Adı", sortable=True)
    
    # Rota isimleri DataGrid aksiyonlarıyla eşleşmeli
    grid.add_action("edit", "Düzenle", "bi bi-pencil", "btn-outline-primary btn-sm", action_type="route", route_name="lokasyon.sehir_islem")
    grid.add_action("delete", "Sil", "bi bi-trash", "btn-outline-danger btn-sm", action_type="ajax", route_name="lokasyon.sehir_sil")
    
    query = tenant_db.query(Sehir)
    grid.process_query(query)
    
    return render_template('lokasyon/list.html', grid=grid, create_url=url_for('lokasyon.sehir_ekle'))

@lokasyon_bp.route('/sehir-ekle', methods=['GET', 'POST'], endpoint='sehir_ekle')
@lokasyon_bp.route('/sehir-duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def sehir_islem(id=None):
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/')

    target_url = url_for('lokasyon.sehir_islem', id=id) if id else url_for('lokasyon.sehir_ekle')
    
    kayit = tenant_db.query(Sehir).get(id) if id else None
    
    form = get_sehir_form(target_url, edit_mode=(id is not None), instance=kayit)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                if not kayit:
                    kayit = Sehir()
                    tenant_db.add(kayit)
                
                kayit.kod = form.fields[0].value
                kayit.ad = form.fields[1].value
                
                tenant_db.commit()
                
                return jsonify({
                    'success': True, 
                    'message': 'Şehir başarıyla kaydedildi.', 
                    'redirect': url_for('lokasyon.sehir_listesi')
                })
                
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500

    return render_template('lokasyon/form.html', form=form)

# ⚠️ DÜZELTME: Bu fonksiyon artık en sola dayalı (Girinti hatası giderildi)
@lokasyon_bp.route('/sehirler/sil/<int:id>', methods=['POST'])
@login_required
def sehir_sil(id):
    # print("BURADA") # Artık buraya düşecek
    tenant_db = get_tenant_db()
    try:
        kayit = tenant_db.query(Sehir).get(id)
        if not kayit: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
        
        # 1. Kontrol: İlçeler
        if kayit.ilceler.count() > 0:
            return jsonify({'success': False, 'message': 'Bu şehre bağlı ilçeler var, önce onları silmelisiniz.'}), 400
            
        # 2. Kontrol: Şubeler
        bagli_sube_sayisi = tenant_db.query(Sube).filter_by(sehir_id=id).count()
        if bagli_sube_sayisi > 0:
                return jsonify({
                    'success': False, 
                    'message': f'Bu şehirde kurulu {bagli_sube_sayisi} adet şube bulunmaktadır. İşlem iptal edildi.'
                }), 400

        tenant_db.delete(kayit)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Şehir başarıyla silindi.'})
    except Exception as e:
        tenant_db.rollback()
        print(f"⚠️ Şehir Silme Hatası: {e}") 
        return jsonify({'success': False, 'message': f"Veritabanı Hatası: {str(e)}"}), 500

# =========================================================
# 2. İLÇE İŞLEMLERİ
# =========================================================

@lokasyon_bp.route('/ilceler')
@login_required
def ilce_listesi():
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/')

    grid = DataGrid("grid_ilceler", Ilce, title="İlçe Listesi")
    
    grid.columns = []
    grid.add_column("sehir.ad", "Şehir", width="200px", sortable=True)
    grid.add_column("ad", "İlçe Adı", sortable=True)
    
    grid.add_action("edit", "Düzenle", "bi bi-pencil", "btn-outline-primary btn-sm", action_type="route", route_name="lokasyon.ilce_islem")
    grid.add_action("delete", "Sil", "bi bi-trash", "btn-outline-danger btn-sm", action_type="ajax", route_name="lokasyon.ilce_sil")
    
    query = tenant_db.query(Ilce).join(Sehir).order_by(Sehir.kod, Ilce.ad)
    grid.process_query(query)
    
    return render_template('lokasyon/list.html', grid=grid, create_url=url_for('lokasyon.ilce_ekle'))

@lokasyon_bp.route('/ilce-ekle', methods=['GET', 'POST'], endpoint='ilce_ekle')
@lokasyon_bp.route('/ilce-duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def ilce_islem(id=None):
    
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/')

    target_url = url_for('lokasyon.ilce_islem', id=id) if id else url_for('lokasyon.ilce_ekle')
    
    kayit = tenant_db.query(Ilce).get(id) if id else None
    
    form = get_ilce_form(target_url, edit_mode=(id is not None), instance=kayit)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                if not kayit:
                    kayit = Ilce()
                    tenant_db.add(kayit)
                
                data = form.get_data()
                kayit.sehir_id = (data.get('sehir_id'))
                kayit.ad = data.get('ad')
                
                tenant_db.commit()
                
                return jsonify({
                    'success': True, 
                    'message': 'İlçe başarıyla kaydedildi.', 
                    'redirect': url_for('lokasyon.ilce_listesi')
                })
                
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500

    return render_template('lokasyon/form.html', form=form)

@lokasyon_bp.route('/ilceler/sil/<int:id>', methods=['POST'])
@login_required
def ilce_sil(id):
    tenant_db = get_tenant_db()
    try:
        kayit = tenant_db.query(Ilce).get(id)
        if not kayit: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
        
        # İlçe silinirken Şube kontrolü
        bagli_sube_sayisi = tenant_db.query(Sube).filter_by(ilce_id=id).count()
        if bagli_sube_sayisi > 0:
             return jsonify({
                 'success': False, 
                 'message': f'Bu ilçede kurulu {bagli_sube_sayisi} adet şube bulunmaktadır. İşlem iptal edildi.'
             }), 400

        tenant_db.delete(kayit)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'İlçe silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# =========================================================
# 3. JSON API
# =========================================================
@lokasyon_bp.route('/api/ilceler/<int:sehir_id>')
@login_required
def api_ilceler_getir(sehir_id):
    tenant_db = get_tenant_db()
    if not tenant_db: return jsonify([])

    ilceler = tenant_db.query(Ilce).filter_by(sehir_id=sehir_id).order_by(Ilce.ad).all()
    return jsonify([
        {'id': i.id, 'text': i.ad} for i in ilceler
    ])