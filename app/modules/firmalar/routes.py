# app/modules/firmalar/routes.py

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import get_tenant_db # 👈 db yerine bunu kullanacağız
from app.modules.firmalar.models import Firma, Donem
from app.form_builder import DataGrid
from .forms import create_firma_form, create_donem_form
from datetime import datetime
from app.context_manager import GlobalContextManager
from .services import FirmaService
import logging

logger = logging.getLogger(__name__)

firmalar_bp = Blueprint('firmalar', __name__)


@firmalar_bp.route('/ekle', methods=['POST'])
def firma_ekle():
    # ... firma ekleme kodu ...
    
    # ✅ Cache'i temizle
    tenant_id = session.get('tenant_id')
    cache.delete(f'tenant_{tenant_id}_firmalar')
    
    flash('Firma eklendi', 'success')
    return redirect(url_for('firma.liste'))
    
@firmalar_bp.route('/')
@login_required
def index():
    return redirect(url_for('firmalar.bilgiler'))

# --- ŞİRKET BİLGİLERİ ---

@firmalar_bp.route('/bilgiler')
@login_required
def bilgiler():
    # 1. Firebird Bağlantısını Al
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect(request.referrer or '/')

    # 2. Firmayı Firebird'den Çek
    # ARTIK UUID KULLANIYORUZ: ID=1 garantisi yok, "İlk Kayıt" mantığına geçiyoruz.
    firma = tenant_db.query(Firma).first()
    
    if not firma:
        # Eğer tablo boşsa hata vermesin, boş form göstersin (İlk kurulum)
        flash("Firma kaydı bulunamadı, lütfen bilgilerinizi girip kaydedin.", "warning")
        firma = Firma() # Boş nesne, ID yok (Model default'u devreye girecek save anında)

    form = create_firma_form(firma)
    # Form action URL'sini dinamik ayarlamak gerekebilir eğer firma yeni ise
    if not firma.id:
        # ID yoksa (None), form action'ı manuel set edelim veya form helper handle etmeli
        # create_firma_form içinde id None ise hata verebilir, kontrol edelim.
        # Basit çözüm: Yeni kayıt için özel rota veya mevcut rotada ID kontrolü.
        pass

    return render_template('firmalar/bilgiler.html', form=form)

@firmalar_bp.route('/guncelle/<string:id>', methods=['POST']) # ID artık string (UUID)
@login_required
def guncelle(id):
    tenant_db = get_tenant_db()
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Veritabanı bağlantısı yok'}), 500

    # ID'ye göre çek (UUID)
    firma = tenant_db.query(Firma).filter_by(id=id).first()
    
    # Eğer ID "None" veya "new" geldiyse ve kayıt yoksa YENİ KAYIT oluştur
    if not firma and (id == 'None' or id == 'new'):
        firma = Firma() # Yeni instance (UUID otomatik oluşur)
        tenant_db.add(firma) # Session'a ekle
    elif not firma:
        return jsonify({'success': False, 'message': 'Firma bulunamadı'}), 404
        
    form = create_firma_form(firma)
    form.process_request(request.form)
    
    if form.validate():
        try:
            data = form.get_data()
            firma.unvan = data['unvan']
            firma.vergi_dairesi = data['vergi_dairesi']
            firma.vergi_no = data['vergi_no']
            firma.adres = data['adres']
            firma.telefon = data['telefon']
            firma.email = data['email']
            
            # Mali Müşavir Bilgileri (Formda varsa)
            if 'sm_unvan' in data: firma.sm_unvan = data['sm_unvan']
            if 'sm_tc_vkn' in data: firma.sm_tc_vkn = data['sm_tc_vkn']
            
            tenant_db.commit() 
            
            return jsonify({'success': True, 'message': 'Şirket bilgileri güncellendi.', 'redirect': '/firmalar/bilgiler'})
        except Exception as e:
            tenant_db.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    return jsonify({'success': False, 'message': 'Form hatası', 'errors': form.get_errors()}), 400

# --- DÖNEM YÖNETİMİ ---

@firmalar_bp.route('/donemler')
@login_required
def donemler():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("donem_list", Donem, "Mali Dönemler")
    
    grid.add_column('ad', 'Dönem Adı')
    grid.add_column('baslangic', 'Başlangıç', type='date')
    grid.add_column('bitis', 'Bitiş', type='date')
    grid.add_column('aktif', 'Durum', type='switch')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'firmalar.donem_duzenle')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'created_at', 
        'donem_id', 'sube_id', 'updated_at', 'deleted_at'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    if tenant_db:
        # Önce aktif firmayı bul (UUID)
        firma = tenant_db.query(Firma).first()
        if firma:
            query = tenant_db.query(Donem).filter_by(firma_id=firma.id).order_by(Donem.id.desc())
            grid.process_query(query)
        else:
            # Firma yoksa boş sorgu döndür (Hata vermemesi için)
            from sqlalchemy import false
            query = tenant_db.query(Donem).filter(false())
            grid.process_query(query)
            flash("Önce Firma Bilgilerini kaydetmelisiniz.", "warning")
    
    return render_template('firmalar/donemler.html', grid=grid)

@firmalar_bp.route('/donem/ekle', methods=['GET', 'POST'])
@login_required
def donem_ekle():
    form = create_donem_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                tenant_db = get_tenant_db()
                
                # --- DÜZELTME BURADA ---
                # 1. Önce Firmayı Bul (UUID'sini almak için)
                firma = tenant_db.query(Firma).first()
                if not firma:
                    return jsonify({'success': False, 'message': 'Önce şirket bilgilerini kaydetmelisiniz!'}), 400
                
                data = form.get_data()
                is_aktif = str(data.get('aktif')).lower() in ['true', '1', 'on']
                
                if is_aktif:
                    # Diğer dönemleri pasif yap (Firma ID'ye göre)
                    tenant_db.query(Donem).filter_by(firma_id=firma.id).update({'aktif': False})
                
                baslangic_date = datetime.strptime(data['baslangic'], '%Y-%m-%d').date()
                bitis_date = datetime.strptime(data['bitis'], '%Y-%m-%d').date()

                donem = Donem(
                    firma_id=firma.id, # 👈 ARTIK 1 DEĞİL, GERÇEK UUID
                    yil=baslangic_date.year, 
                    ad=data['ad'],
                    baslangic=baslangic_date,
                    bitis=bitis_date,
                    aktif=is_aktif
                )
                tenant_db.add(donem)
                tenant_db.commit()
                
                if is_aktif:
                    session['aktif_donem_id'] = donem.id
                
                return jsonify({'success': True, 'message': 'Dönem oluşturuldu.', 'redirect': '/firmalar/donemler'})
            except Exception as e:
                if tenant_db: tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('firmalar/form.html', form=form)


@firmalar_bp.route('/donem/duzenle/<string:id>', methods=['GET', 'POST'])  # ✅ string:id
@login_required
def donem_duzenle(id):
    """Dönem düzenle (UUID destekli)"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı koptu", "danger")
        return redirect('/firmalar/donemler')

    # UUID ile çek
    donem = tenant_db.query(Donem).filter_by(id=id).first()  # ✅ .get() yerine .filter_by()
    
    if not donem:
        flash("Dönem bulunamadı", "warning")
        return redirect('/firmalar/donemler')

    form = create_donem_form(donem)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                is_aktif = str(data.get('aktif')).lower() in ['true', '1', 'on']
                
                if is_aktif and not donem.aktif:
                    tenant_db.query(Donem).filter_by(firma_id=donem.firma_id).update({'aktif': False})
                
                donem.ad = data['ad']
                
                yeni_baslangic = datetime.strptime(data['baslangic'], '%Y-%m-%d').date()
                donem.baslangic = yeni_baslangic
                donem.bitis = datetime.strptime(data['bitis'], '%Y-%m-%d').date()
                donem.yil = yeni_baslangic.year 
                donem.aktif = is_aktif
                
                tenant_db.commit()
                
                if is_aktif:
                    session['aktif_donem_id'] = donem.id
                
                return jsonify({'success': True, 'message': 'Dönem güncellendi.', 'redirect': '/firmalar/donemler'})
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"❌ Dönem güncelleme hatası: {e}", exc_info=True)
                return jsonify({'success': False, 'message': str(e)}), 500
    
    return render_template('firmalar/form.html', form=form)               

@firmalar_bp.route('/sec/<uuid:firma_id>')
@login_required
def firma_sec(firma_id):
    """Firma seç ve session'a kaydet"""
    
    firma = Firma.query.get_or_404(firma_id)
    
    # Kullanıcının bu firmaya erişim yetkisi var mı?
    if firma not in current_user.firmalar:
        flash('Bu firmaya erişim yetkiniz yok', 'danger')
        return redirect(url_for('main.index'))
    
    # ✅ Session'a tenant DB adını kaydet
    session['active_firma_id'] = str(firma.id)
    session['active_tenant_db_name'] = firma.tenant_db_name  # ✅ BURASI ÖNEMLİ
    session['tenant_name'] = firma.unvan
    session.modified = True
    
    logger.info(f"✅ Firma seçildi: {firma.unvan} (DB: {firma.tenant_db_name})")
    
    flash(f'Firma seçildi: {firma.unvan}', 'success')
    return redirect(url_for('main.index'))
    
    
@firmalar_bp.route('/test-firma-olustur', methods=['GET', 'POST'])
#@login_required
def test_firma_olustur():
    """Test amaçlı firma oluşturma ekranı"""
    
    if request.method == 'POST':
        try:
            kod = request.form.get('kod', '').strip()
            unvan = request.form.get('unvan', '').strip()
            vergi_no = request.form.get('vergi_no', '').strip()
            admin_email = request.form.get('admin_email', '').strip()  # ✅ YENİ
            admin_password = request.form.get('admin_password', '').strip()  # ✅ YENİ
            
            # Validasyon
            if not kod or not unvan or not vergi_no:
                return jsonify({
                    'success': False,
                    'message': 'Kod, ünvan ve vergi no zorunludur!'
                }), 400
            
            # Email varsa şifre de olmalı
            if admin_email and not admin_password:
                admin_password = f"{kod}123"  # Otomatik şifre
            
            # Firma oluştur
            basari, mesaj, tenant = FirmaService.firma_olustur(
                kod, unvan, vergi_no, admin_email, admin_password
            )
            
            if basari:
                return jsonify({
                    'success': True,
                    'message': mesaj,
                    'tenant': {
                        'id': tenant.id,
                        'kod': tenant.kod,
                        'unvan': tenant.unvan,
                        'db_name': tenant.db_name
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'message': mesaj
                }), 500
        
        except Exception as e:
            logger.exception("Test firma oluşturma hatası")
            return jsonify({
                'success': False,
                'message': f"Beklenmeyen hata: {str(e)}"
            }), 500
    
    return render_template('firmalar/test_firma_olustur.html')

    