# modules/fiyat/routes.py

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _
from app.extensions import db
from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
from app.form_builder import DataGrid, FieldType
from .forms import create_fiyat_listesi_form
from datetime import datetime

# Blueprint Tanımı
fiyat_bp = Blueprint('fiyat', __name__)

# --- YARDIMCI KAYIT FONKSİYONU ---
def liste_kaydet(form, liste=None):
    data = form.get_data()
    
    if not liste:
        liste = FiyatListesi(firma_id=current_user.firma_id)
        db.session.add(liste)
    
    # Başlık Bilgileri
    liste.kod = data.get('kod')
    liste.ad = data.get('ad')
    liste.aciklama = data.get('aciklama') # ✅ EKLENDİ
    
    # Sayısal Değerler
    try:
        liste.oncelik = int(data.get('oncelik') or 0)
    except: liste.oncelik = 0
    
    # Boolean Değerler (Aktif ve Varsayılan)
    def parse_bool(val):
        if isinstance(val, str):
            return val.lower() in ['true', '1', 'on', 'yes']
        return bool(val)

    liste.aktif = parse_bool(data.get('aktif'))
    liste.varsayilan = parse_bool(data.get('varsayilan')) # ✅ EKLENDİ

    # Tarih İşlemleri
    if data.get('baslangic_tarihi'):
        try: liste.baslangic_tarihi = datetime.strptime(data['baslangic_tarihi'], '%Y-%m-%d').date()
        except: liste.baslangic_tarihi = None
    else: liste.baslangic_tarihi = None
        
    if data.get('bitis_tarihi'):
        try: liste.bitis_tarihi = datetime.strptime(data['bitis_tarihi'], '%Y-%m-%d').date()
        except: liste.bitis_tarihi = None
    else: liste.bitis_tarihi = None
        
    db.session.flush() 
    
    # ✅ ÖNEMLİ: Eğer bu liste "Varsayılan" seçildiyse, diğerlerinin varsayılan özelliğini kaldır
    if liste.varsayilan:
        FiyatListesi.query.filter(
            FiyatListesi.firma_id == current_user.firma_id,
            FiyatListesi.id != liste.id
        ).update({'varsayilan': False})

    # Detayları Temizle ve Yeniden Ekle
    if liste.id:
        FiyatListesiDetay.query.filter_by(fiyat_listesi_id=liste.id).delete()
    
    # ...(Detay kayıt döngüsü AYNEN kalacak) ...
    # Formdan gelen listeleri al
    stok_ids = request.form.getlist('detaylar_stok_id[]') # 'fiyat_detaylari_' prefixi ile gelebilir, kontrol edin
    # Eğer forms.py'de master-detail name='detaylar' ise inputlar 'detaylar_stok_id[]' olur.
    # ...
    
    # NOT: Eğer forms.py'de name='detaylar' ise request.form'da 'detaylar_stok_id[]' arayın.
    # Aşağıdaki döngüyü mevcut kodunuzdaki gibi koruyun.
    
    stok_ids = request.form.getlist('detaylar_stok_id[]')
    fiyatlar = request.form.getlist('detaylar_fiyat[]')
    iskontolar = request.form.getlist('detaylar_iskonto_orani[]')
    min_miktarlar = request.form.getlist('detaylar_min_miktar[]')

    for i in range(len(stok_ids)):
        if not stok_ids[i]: continue
        
        # Fiyat parse
        ham_fiyat = fiyatlar[i]
        fiyat = 0.0
        if ham_fiyat:
            try: fiyat = float(str(ham_fiyat).replace('.', '').replace(',', '.'))
            except: pass
            
        # Diğerleri
        try: iskonto = float(str(iskontolar[i] or 0).replace(',', '.'))
        except: iskonto = 0
        
        try: miktar = float(str(min_miktarlar[i] or 1).replace(',', '.'))
        except: miktar = 1

        detay = FiyatListesiDetay(
            fiyat_listesi_id=liste.id,
            stok_id=stok_ids[i],
            fiyat=fiyat,
            iskonto_orani=iskonto,
            min_miktar=miktar
        )
        db.session.add(detay)
        
    db.session.commit()


# --- ROTALAR ---
@fiyat_bp.route('/')
@login_required
def index():
    grid = DataGrid("fiyat_liste_grid", FiyatListesi, _("Fiyat Listeleri"))
    
    grid.add_column('kod', _('Liste Kodu'), width='120px')
    grid.add_column('ad', _('Liste Adı'))
    grid.add_column('baslangic_tarihi', _('Başlangıç'), type=FieldType.DATE)
    grid.add_column('bitis_tarihi', _('Bitiş'), type=FieldType.DATE)
    grid.add_column('oncelik', _('Öncelik'), type=FieldType.NUMBER)
    grid.add_column('aktif', _('Durum'), type=FieldType.SWITCH)
    
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'fiyat.duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'fiyat.sil')
    
    query = FiyatListesi.query.filter_by(firma_id=current_user.firma_id).order_by(FiyatListesi.oncelik.desc())
    grid.process_query(query)
    
    return render_template('fiyat/index.html', grid=grid)

@fiyat_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_fiyat_listesi_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                liste_kaydet(form)
                return jsonify({'success': True, 'message': _('Fiyat listesi başarıyla kaydedildi.'), 'redirect': '/fiyat'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f"Kayıt Hatası: {str(e)}"}), 500
        else:
             return jsonify({'success': False, 'message': _('Lütfen hataları düzeltin.'), 'errors': form.get_errors()}), 400
    
    return render_template('fiyat/form.html', form=form)

@fiyat_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    liste = FiyatListesi.query.get_or_404(id)
    form = create_fiyat_listesi_form(liste)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                liste_kaydet(form, liste)
                return jsonify({'success': True, 'message': _('Kayıt güncellendi.'), 'redirect': '/fiyat'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f"Güncelleme Hatası: {str(e)}"}), 500
                
    return render_template('fiyat/form.html', form=form)

@fiyat_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    liste = FiyatListesi.query.get_or_404(id)
    try:
        db.session.delete(liste)
        db.session.commit()
        return jsonify({'success': True, 'message': _('Kayıt silindi.')})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500   

@fiyat_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    """
    Otomatik Fiyat Listesi Kodu Üretici
    Format: LST-YYYY-SIRA (Örn: LST-2025-001)
    """
    yil = datetime.now().year
    # Bu yıl içindeki toplam liste sayısını bul
    # (Daha güvenli olması için LIKE ile filtreleme yapılabilir)
    sayi = FiyatListesi.query.filter(
        FiyatListesi.firma_id == current_user.firma_id,
        FiyatListesi.kod.like(f"LST-{yil}-%")
    ).count()
    
    yeni_kod = f"LST-{yil}-{str(sayi + 1).zfill(3)}"
    
    return jsonify({'code': yeni_kod})

