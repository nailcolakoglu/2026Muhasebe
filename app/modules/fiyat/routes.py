# app/modules/fiyat/routes.py

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app.extensions import get_tenant_db # ✨ YENİ: Tenant DB Importu
from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
from app.form_builder import DataGrid, FieldType
from .forms import create_fiyat_listesi_form
from datetime import datetime

fiyat_bp = Blueprint('fiyat', __name__)

# --- YARDIMCI KAYIT FONKSİYONU ---
def liste_kaydet(form, liste=None):
    tenant_db = get_tenant_db() # ✨ YENİ
    data = form.get_data()
    
    is_new = False
    if not liste:
        liste = FiyatListesi(firma_id=str(current_user.firma_id))
        tenant_db.add(liste)
        is_new = True
    
    # Başlık Bilgileri
    liste.kod = data.get('kod')
    liste.ad = data.get('ad')
    liste.aciklama = data.get('aciklama')
    
    # Sayısal Değerler
    try: liste.oncelik = int(data.get('oncelik') or 0)
    except: liste.oncelik = 0
    
    def parse_bool(val):
        if isinstance(val, str):
            return val.lower() in ['true', '1', 'on', 'yes']
        return bool(val)

    liste.aktif = parse_bool(data.get('aktif'))
    liste.varsayilan = parse_bool(data.get('varsayilan'))

    if data.get('baslangic_tarihi'):
        try: liste.baslangic_tarihi = datetime.strptime(data['baslangic_tarihi'], '%Y-%m-%d').date()
        except: liste.baslangic_tarihi = None
    else: liste.baslangic_tarihi = None
        
    if data.get('bitis_tarihi'):
        try: liste.bitis_tarihi = datetime.strptime(data['bitis_tarihi'], '%Y-%m-%d').date()
        except: liste.bitis_tarihi = None
    else: liste.bitis_tarihi = None
        
    tenant_db.flush() # UUID alabilmek için
    
    # Diğer listelerin varsayılan özelliğini kaldır
    if liste.varsayilan:
        tenant_db.query(FiyatListesi).filter(
            FiyatListesi.firma_id == str(current_user.firma_id),
            FiyatListesi.id != str(liste.id)
        ).update({'varsayilan': False})

    # Detayları Temizle
    if not is_new:
        tenant_db.query(FiyatListesiDetay).filter_by(fiyat_listesi_id=str(liste.id)).delete()
    
    stok_ids = request.form.getlist('detaylar_stok_id[]')
    fiyatlar = request.form.getlist('detaylar_fiyat[]')
    iskontolar = request.form.getlist('detaylar_iskonto_orani[]')
    min_miktarlar = request.form.getlist('detaylar_min_miktar[]')

    for i in range(len(stok_ids)):
        if not stok_ids[i]: continue
        
        fiyat = 0.0
        if i < len(fiyatlar) and fiyatlar[i]:
            try: fiyat = float(str(fiyatlar[i]).replace('.', '').replace(',', '.'))
            except: pass
            
        try: iskonto = float(str(iskontolar[i] or 0).replace(',', '.'))
        except: iskonto = 0
        
        try: miktar = float(str(min_miktarlar[i] or 1).replace(',', '.'))
        except: miktar = 1

        detay = FiyatListesiDetay(
            fiyat_listesi_id=str(liste.id),
            stok_id=str(stok_ids[i]),
            fiyat=fiyat,
            iskonto_orani=iskonto,
            min_miktar=miktar
        )
        tenant_db.add(detay)
        
    tenant_db.commit()


# --- ROTALAR ---
@fiyat_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    grid = DataGrid("fiyat_liste_grid", FiyatListesi, _("Fiyat Listeleri"))
    
    grid.add_column('kod', _('Liste Kodu'), width='120px')
    grid.add_column('ad', _('Liste Adı'))
    grid.add_column('baslangic_tarihi', _('Başlangıç'), type=FieldType.DATE)
    grid.add_column('bitis_tarihi', _('Bitiş'), type=FieldType.DATE)
    grid.add_column('oncelik', _('Öncelik'), type=FieldType.NUMBER)
    grid.add_column('aktif', _('Durum'), type=FieldType.SWITCH)
    
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'fiyat.duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'fiyat.sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id',
        'created_at', 'updated_at', 
        'deleted_at', 'deleted_by', 
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    
    query = tenant_db.query(FiyatListesi).filter_by(firma_id=str(current_user.firma_id)).order_by(FiyatListesi.oncelik.desc())
    grid.process_query(query)
    
    return render_template('fiyat/index.html', grid=grid)

@fiyat_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_fiyat_listesi_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db()
            try:
                liste_kaydet(form)
                return jsonify({'success': True, 'message': _('Fiyat listesi başarıyla kaydedildi.'), 'redirect': '/fiyat'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f"Kayıt Hatası: {str(e)}"}), 500
        else:
             return jsonify({'success': False, 'message': _('Lütfen hataları düzeltin.'), 'errors': form.get_errors()}), 400
    
    return render_template('fiyat/form.html', form=form)

# ✨ UUID UYUMU: <int:id> -> <string:id>
@fiyat_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    liste = tenant_db.query(FiyatListesi).get(str(id))
    if not liste: return jsonify({'success': False, 'message': 'Liste bulunamadı'}), 404
    
    form = create_fiyat_listesi_form(liste)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                liste_kaydet(form, liste)
                return jsonify({'success': True, 'message': _('Kayıt güncellendi.'), 'redirect': '/fiyat'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f"Güncelleme Hatası: {str(e)}"}), 500
                
    return render_template('fiyat/form.html', form=form)

# ✨ UUID UYUMU: <int:id> -> <string:id>
@fiyat_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    liste = tenant_db.query(FiyatListesi).get(str(id))
    if not liste: return jsonify({'success': False, 'message': 'Liste bulunamadı'}), 404
    
    try:
        # Önce detayları temizle (Cascade yoksa hata vermesin)
        tenant_db.query(FiyatListesiDetay).filter_by(fiyat_listesi_id=str(id)).delete()
        tenant_db.delete(liste)
        tenant_db.commit()
        return jsonify({'success': True, 'message': _('Kayıt silindi.')})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500   

@fiyat_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    yil = datetime.now().year
    
    sayi = tenant_db.query(FiyatListesi).filter(
        FiyatListesi.firma_id == str(current_user.firma_id),
        FiyatListesi.kod.like(f"LST-{yil}-%")
    ).count()
    
    yeni_kod = f"LST-{yil}-{str(sayi + 1).zfill(3)}"
    return jsonify({'code': yeni_kod})