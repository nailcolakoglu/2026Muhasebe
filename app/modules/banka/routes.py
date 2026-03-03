# app/modules/banka/routes.py

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.enums import BankaHesapTuru, ParaBirimi, TurkiyeBankalari, CariIslemTuru
from app.extensions import get_tenant_db # ✨ YENİ: Tenant DB Importu
from app.modules.cari.models import CariHareket, CariHesap
from app.modules.banka.models import BankaHesap
from app.form_builder import DataGrid, FieldType
from .forms import create_banka_form
from app.araclar import siradaki_kod_uret

banka_bp = Blueprint('banka', __name__)

# Yardımcı Fonksiyon: Sayı Çevirici
def parse_currency(value):
    if not value: return 0
    if isinstance(value, (int, float)): return value
    return float(str(value).replace('.', '').replace(',', '.'))

@banka_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db() # ✨ Tenant DB'den sorguluyoruz
    
    grid = DataGrid("banka_list", BankaHesap, "Banka Hesapları")
    
    grid.add_column('kod', 'Kod', width='100px')
    grid.add_column('banka_adi', 'Banka')
    grid.add_column('ad', 'Hesap Tanımı')
    grid.add_column('sube_adi', 'Şube')
    grid.add_column('iban', 'IBAN')
    grid.add_column('doviz_turu', 'Döviz', width='80px')
    grid.add_column('aktif', 'Durum')
 
    grid.add_action('ekstre','Ekstre','bi bi-file-earmark-spreadsheet','btn-outline-secondary btn-sm', 'route', 'banka_hareket.ekstre')
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'banka.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'banka.sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sube_id', 'donem_id', 
        'muhasebe_hesap_id', 
        'created_at', 'updated_at', 'deleted_at', 
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    
    query = tenant_db.query(BankaHesap).filter_by(firma_id=str(current_user.firma_id))
    grid.process_query(query)
    
    return render_template('banka/index.html', grid=grid)

@banka_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_banka_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db() # ✨ YENİ
            try:
                data = form.get_data()
                banka = BankaHesap(
                    firma_id=str(current_user.firma_id),
                    kod=data['kod'],
                    banka_adi=data['banka_adi'],
                    ad=data['ad'],
                    sube_id=str(data.get('sube_id')) if data.get('sube_id') else None,
                    
                    hesap_turu=BankaHesapTuru(data['hesap_turu']),
                    doviz_turu=ParaBirimi(data['doviz_turu']) if data.get('doviz_turu') else ParaBirimi.TL,
                    
                    sube_adi=data['sube_adi'],
                    hesap_no=data['hesap_no'],
                    iban=data['iban'],
                    
                    kredi_limiti=parse_currency(data.get('kredi_limiti')),
                    hesap_kesim_gunu=int(data['hesap_kesim_gunu']) if data.get('hesap_kesim_gunu') else None,
                    
                    muhasebe_hesap_id=str(data.get('muhasebe_hesap_id')) if data.get('muhasebe_hesap_id') else None,
                    temsilci_adi=data['temsilci_adi'],
                    temsilci_tel=data['temsilci_tel'],
                    
                    aktif=data['aktif'] in ['True', '1', True, 'true', 'on']
                )
                tenant_db.add(banka)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Banka hesabı başarıyla eklendi.', 'redirect': '/banka'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('banka/form.html', form=form)

# ✨ UUID UYUMU: <int:id> -> <string:id>
@banka_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    banka = tenant_db.query(BankaHesap).get(str(id))
    if not banka: return "Banka bulunamadı", 404
    
    form = create_banka_form(banka)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                banka.kod = data['kod']
                banka.banka_adi = data['banka_adi']
                banka.ad = data['ad']
                banka.sube_id = str(data.get('sube_id')) if data.get('sube_id') else None
                
                banka.hesap_turu = BankaHesapTuru(data['hesap_turu'])
                banka.doviz_turu = ParaBirimi(data['doviz_turu'])
                
                banka.sube_adi = data['sube_adi']
                banka.hesap_no = data['hesap_no']
                banka.iban = data['iban']
                
                banka.kredi_limiti = parse_currency(data.get('kredi_limiti'))
                banka.hesap_kesim_gunu = int(data['hesap_kesim_gunu']) if data.get('hesap_kesim_gunu') else None
                
                banka.muhasebe_hesap_id = str(data.get('muhasebe_hesap_id')) if data.get('muhasebe_hesap_id') else None
                banka.temsilci_adi = data['temsilci_adi']
                banka.temsilci_tel = data['temsilci_tel']
                
                banka.aktif = data['aktif'] in ['True', '1', True, 'true', 'on']
                
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Banka hesabı güncellendi.', 'redirect': '/banka'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('banka/form.html', form=form)

# ✨ UUID UYUMU: <int:id> -> <string:id>
@banka_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    banka = tenant_db.query(BankaHesap).get(str(id))
    if not banka: return jsonify({'success': False, 'message': 'Banka bulunamadı'}), 404
    
    try:
        tenant_db.delete(banka)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@banka_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    yeni_kod = siradaki_kod_uret(BankaHesap, 'BNK-', hane_sayisi=3, tenant_db=tenant_db)
    return jsonify({'code': yeni_kod})