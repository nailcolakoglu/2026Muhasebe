# app/modules/crm/routes.py


import logging
from sqlalchemy.orm import subqueryload
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from flask_babel import gettext as _

from app.extensions import get_tenant_db
logger = logging.getLogger(__name__)
try:
    from app.decorators import tenant_route, permission_required
except ImportError as e:
    # Bu log sayesinde tam olarak hangi ismin bulunamadığını görebilirsin
    logger.error(f"Kritik Import Hatası: {str(e)}")
    raise e
from app.form_builder import DataGrid, FieldType
from app.modules.crm.models import AdayMusteri, SatisFirsati, CrmAktivite, SatisAsamasi, CrmHareketi
from app.modules.crm.forms import create_aday_form, create_firsat_form, create_aktivite_form, create_crm_hareketi_form
from app.modules.crm.services import CrmService

crm_bp = Blueprint('crm', __name__)

# ==========================================
# 1. ADAY MÜŞTERİ ROTALARI
# ==========================================

@crm_bp.route('/adaylar')
@login_required
@permission_required('crm_goruntule')
@tenant_route
def aday_index():
    """Aday Müşteriler Listesi"""
    tenant_db = get_tenant_db()
    
    grid = DataGrid("adaylar_list", AdayMusteri, _("Aday Müşteriler"), per_page=20)
    grid.add_column('unvan', _('Firma / Ünvan'), sortable=True)
    grid.add_column('yetkili_kisi', _('Yetkili'))
    grid.add_column('telefon', _('Telefon'))
    grid.add_column('durum', _('Durum'), type='badge', 
                    badge_colors={'YENI': 'primary', 'GORUSULUYOR': 'warning', 'NITELIKLI': 'success', 'IPTAL': 'danger'})
    grid.add_column('kaynak', _('Kaynak'))
    
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'crm.aday_duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'crm.aday_sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'temsilci_id', 'uretici_kodu', 'kategori_id',
        'birim', 'tip', 'muhasebe_kod_id', 'kdv_kod_id',
        'donusturulen_cari_id', 
        'anahtar_kelimeler', 'aciklama_detay', 'ozel_kod1', 'ozel_kod2',
        'resim_path', 'aktif', 'created_at', 'updated_at',
        'deleted_at',
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    
    # query_class = FirmaFilteredQuery olduğu için sadece aktif firmanınkiler otomatik gelir
    query = tenant_db.query(AdayMusteri).order_by(AdayMusteri.created_at.desc())
    grid.process_query(query)
    
    return render_template('crm/index.html', grid=grid)


@crm_bp.route('/aday/ekle', methods=['GET', 'POST'])
@login_required
@permission_required('crm_ekle')
def aday_ekle():
    form = create_aday_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.aday_kaydet(form.get_data(), current_user.firma_id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.aday_index')})
            return jsonify({'success': False, 'message': mesaj}), 500
            
    return render_template('crm/form.html', form=form)


@crm_bp.route('/aday/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
@permission_required('crm_duzenle')
def aday_duzenle(id):
    tenant_db = get_tenant_db()
    aday = tenant_db.get(AdayMusteri, id)
    
    if not aday:
        return redirect(url_for('crm.aday_index'))
        
    form = create_aday_form(aday)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.aday_kaydet(form.get_data(), current_user.firma_id, aday_id=id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.aday_index')})
            return jsonify({'success': False, 'message': mesaj}), 500
            
    return render_template('crm/form.html', form=form)


@crm_bp.route('/aday/sil/<string:id>', methods=['POST'])
@login_required
@permission_required('crm_sil')
def aday_sil(id):
    tenant_db = get_tenant_db()
    aday = tenant_db.get(AdayMusteri, id)
    if not aday: 
        return jsonify({'success': False, 'message': _('Aday bulunamadı.')}), 404
        
    try:
        tenant_db.delete(aday)
        tenant_db.commit()
        logger.info(f"✅ Aday silindi: {id}")
        return jsonify({'success': True, 'message': _('Aday başarıyla silindi.')})
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"❌ Aday Silme Hatası: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
        
# ==========================================
# 2. SATIŞ FIRSATI ROTALARI
# ==========================================
@crm_bp.route('/firsatlar')
@login_required
@permission_required('crm_goruntule')
def firsat_index():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("firsatlar_list", SatisFirsati, _("Satış Fırsatları"), per_page=20)
    grid.add_column('baslik', _('Fırsat Başlığı'), sortable=True)
    grid.add_column('tahmini_tutar', _('Tutar'), type=FieldType.CURRENCY)
    grid.add_column('olasilik', _('Olasılık (%)'))
    grid.add_column('asama', _('Aşama'), type='badge', 
                    badge_colors={'KESIF': 'secondary', 'TEKLIF_SUNULDU': 'info', 'KAZANILDI': 'success', 'KAYBEDILDI': 'danger'})
    
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'crm.firsat_duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'crm.firsat_sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'temsilci_id', 'uretici_kodu', 'kategori_id',
        'birim', 'tip', 'cari_id', 'aday_id', 'asama_id', 
        'donusturulen_cari_id', 'para_birimi', 'ai_olasilik', 'beklenen_kapanis_tarihi',
        'anahtar_kelimeler', 'aciklama_detay', 'ozel_kod1', 'ozel_kod2',
        'resim_path', 'aktif', 'created_at', 'updated_at',
        'deleted_at',
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    query = tenant_db.query(SatisFirsati).order_by(SatisFirsati.created_at.desc())
    grid.process_query(query)
    
    return render_template('crm/index.html', grid=grid)

@crm_bp.route('/firsat/ekle', methods=['GET', 'POST'])
@login_required
def firsat_ekle():
    form = create_firsat_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.firsat_kaydet(form.get_data(), current_user.firma_id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.firsat_index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('crm/form.html', form=form)

@crm_bp.route('/firsat/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def firsat_duzenle(id):
    tenant_db = get_tenant_db()
    firsat = tenant_db.get(SatisFirsati, id)
    if not firsat: return redirect(url_for('crm.firsat_index'))
    
    form = create_firsat_form(firsat)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.firsat_kaydet(form.get_data(), current_user.firma_id, firsat_id=id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.firsat_index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('crm/form.html', form=form)

@crm_bp.route('/firsat/sil/<string:id>', methods=['POST'])
@login_required
def firsat_sil(id):
    tenant_db = get_tenant_db()
    firsat = tenant_db.get(SatisFirsati, id)
    if not firsat: return jsonify({'success': False, 'message': 'Bulunamadı'}), 404
    try:
        tenant_db.delete(firsat)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Başarıyla silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ==========================================
# 3. AKTİVİTE ROTALARI
# ==========================================
@crm_bp.route('/aktiviteler')
@login_required
@permission_required('crm_goruntule')
def aktivite_index():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("aktiviteler_list", CrmAktivite, _("Görüşmeler & Aktiviteler"), per_page=20)
    grid.add_column('konu', _('Konu'), sortable=True)
    grid.add_column('aktivite_tipi', _('Tip'))
    grid.add_column('tarih', _('Tarih'), type=FieldType.DATE)
    grid.add_column('tamamlandi', _('Durum'), type='boolean')
    
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'crm.aktivite_duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'crm.aktivite_sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'temsilci_id', 'uretici_kodu', 'kategori_id', 'firsat_id',
        'birim', 'tip', 'cari_id', 'aday_id', 'asama_id', 
        'donusturulen_cari_id', 'para_birimi', 'ai_olasilik', 'beklenen_kapanis_tarihi',
        'anahtar_kelimeler', 'aciklama_detay', 'ozel_kod1', 'ozel_kod2',
        'kullanici_id', 'aktif', 'created_at', 'updated_at',
        'deleted_at',
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
  
    query = tenant_db.query(CrmAktivite).order_by(CrmAktivite.tarih.desc())
    grid.process_query(query)
    
    return render_template('crm/index.html', grid=grid)

@crm_bp.route('/aktivite/ekle', methods=['GET', 'POST'])
@login_required
def aktivite_ekle():
    form = create_aktivite_form()
    if request.method == 'POST':
        form.process_request(request.form)
        
        if form.validate():
            data = form.get_data()
            
            # ✨ EKSİK PARÇA: Modal'dan gelen gizli firsat_id'yi veritabanına işlenmesi için yakalıyoruz
            if request.form.get('firsat_id'):
                data['firsat_id'] = request.form.get('firsat_id')
                
            basari, mesaj = CrmService.aktivite_kaydet(data, current_user.firma_id, current_user.id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.aktivite_index')})
            return jsonify({'success': False, 'message': mesaj}), 400
        else:
            # ✨ ÇÖKME ENGELLEYİCİ: Validasyon başarısız olursa HTML yerine JSON döndürüyoruz
            return jsonify({'success': False, 'message': 'Eksik veya hatalı alanlar var.', 'errors': form.errors}), 400
            
    return render_template('crm/form.html', form=form)
@crm_bp.route('/aktivite/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def aktivite_duzenle(id):
    tenant_db = get_tenant_db()
    aktivite = tenant_db.get(CrmAktivite, id)
    if not aktivite: return redirect(url_for('crm.aktivite_index'))
    
    form = create_aktivite_form(aktivite)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.aktivite_kaydet(form.get_data(), current_user.firma_id, current_user.id, aktivite_id=id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.aktivite_index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('crm/form.html', form=form)

@crm_bp.route('/aktivite/sil/<string:id>', methods=['POST'])
@login_required
def aktivite_sil(id):
    tenant_db = get_tenant_db()
    aktivite = tenant_db.get(CrmAktivite, id)
    if not aktivite: return jsonify({'success': False, 'message': 'Bulunamadı'}), 404
    try:
        tenant_db.delete(aktivite)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Başarıyla silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
        
@crm_bp.route('/pipeline')
@login_required
@tenant_route
def pipeline():
    tenant_db = get_tenant_db()
    
    # İlişki artık dynamic olmadığı için subqueryload pürüzsüz çalışacaktır
    asamalar = (tenant_db.query(SatisAsamasi)
                .filter_by(firma_id=current_user.firma_id)
                .options(subqueryload(SatisAsamasi.firsatlar)) 
                .order_by(SatisAsamasi.sira).all())
                
    return render_template('crm/pipeline.html', asamalar=asamalar)

@crm_bp.route('/firsat/tasi/<string:firsat_id>', methods=['POST'])
@login_required
@tenant_route
def firsat_tasi(firsat_id):
    yeni_asama_id = request.json.get('asama_id')
    
    # Tüm ağır işi (loglama + güncelleme) service katmanına devrettik
    basari = CrmService.firsat_asama_degistir(
        firsat_id, 
        yeni_asama_id, 
        current_user.firma_id, 
        current_user.id
    )
    
    if basari:
        return jsonify({'success': True})
    return jsonify({'success': False}), 400    
 
@crm_bp.route('/firsat/hizli-aktivite/<string:firsat_id>')
@login_required
@tenant_route
def hizli_aktivite_form(firsat_id):
    tenant_db = get_tenant_db()
    firsat = tenant_db.get(SatisFirsati, str(firsat_id))
    
    # Sadece boş formu çağırıyoruz, Python tarafında müdahale etmiyoruz
    form = create_aktivite_form()
    
    # Formun kayıt işlemini standart aktivite ekleme rotasına yönlendiriyoruz
    form.action = url_for('crm.aktivite_ekle')
    
    # firsat nesnesini de şablona gönderiyoruz ki içindeki verileri JS ile alabilelim
    return render_template('crm/_hizli_aktivite_modal.html', form=form, firsat=firsat)
    
@crm_bp.route('/hareketler')
@login_required
@tenant_route
def hareket_index():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("hareketler_list", CrmHareketi, _("Müşteri Etkileşimleri (Akıllı Log)"), per_page=20)
    grid.add_column('tarih', _('Tarih'), type=FieldType.DATE, sortable=True)
    grid.add_column('islem_turu', _('İşlem'))
    grid.add_column('konu', _('Konu'))
    
    # Duygu durumunu renkli rozetlerle gösterelim
    grid.add_column('duygu_durumu', _('Duygu Durumu'), type='badge', 
                    badge_colors={'MUTLU': 'success', 'NORMAL': 'info', 'BELIRSIZ': 'secondary', 'MUTSUZ': 'warning', 'SINIRLI': 'danger'})
    
    grid.add_column('memnuniyet_skoru', _('Skor'))
    grid.add_column('aksiyon_gerekli', _('Aksiyon?'), type='boolean')
    
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'crm.hareket_duzenle')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'temsilci_id', 'uretici_kodu', 'kategori_id', 'firsat_id',
        'birim', 'tip', 'cari_id', 'aday_id', 'asama_id', 'ai_metadata', 'plasiyer_id',
        'donusturulen_cari_id', 'para_birimi', 'ai_olasilik', 'beklenen_kapanis_tarihi',
        'anahtar_kelimeler', 'aciklama_detay', 'ozel_kod1', 'ozel_kod2',
        'kullanici_id', 'aktif', 'created_at', 'updated_at',
        'deleted_at',
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
  
    query = tenant_db.query(CrmHareketi).order_by(CrmHareketi.tarih.desc())
    grid.process_query(query)
    
    return render_template('crm/index.html', grid=grid)

@crm_bp.route('/hareket/ekle', methods=['GET', 'POST'])
@login_required
def hareket_ekle():
    form = create_crm_hareketi_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.hareket_kaydet(form.get_data(), current_user.firma_id, current_user.id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.hareket_index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('crm/form.html', form=form)

@crm_bp.route('/hareket/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def hareket_duzenle(id):
    tenant_db = get_tenant_db()
    hareket = tenant_db.get(CrmHareketi, id)
    if not hareket: return redirect(url_for('crm.hareket_index'))
    
    form = create_crm_hareketi_form(hareket)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = CrmService.hareket_kaydet(form.get_data(), current_user.firma_id, current_user.id, hareket_id=id)
            if basari:
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('crm.hareket_index')})
            return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('crm/form.html', form=form)

@crm_bp.route('/firsat/detay/<string:id>')
@login_required
@tenant_route
def firsat_detay(id):
    tenant_db = get_tenant_db()
    firsat = tenant_db.get(SatisFirsati, id)
    if not firsat: return redirect(url_for('crm.firsat_index'))
    
    # Bu fırsatın bağlı olduğu cariye ait tüm "Akıllı Etkileşim" geçmişi (AI verileriyle)
    etkilesimler = []
    if firsat.cari_id:
        etkilesimler = tenant_db.query(CrmHareketi).filter_by(cari_id=firsat.cari_id).order_by(CrmHareketi.tarih.desc()).all()
        
    return render_template('crm/firsat_detay.html', firsat=firsat, etkilesimler=etkilesimler)    