# app/modules/firmalar/routes.py

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import get_tenant_db # 👈 db yerine bunu kullanacağız
from app.modules.firmalar.models import Firma, Donem
from app.form_builder import DataGrid
from .forms import create_firma_form, create_donem_form
from datetime import datetime

firmalar_bp = Blueprint('firmalar', __name__)

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

@firmalar_bp.route('/donem/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def donem_duzenle(id):
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı koptu", "danger")
        return redirect('/firmalar/donemler')

    donem = tenant_db.query(Donem).get(id)
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
                    # Firma ID'yi mevcut dönem nesnesinden alıyoruz
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
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('firmalar/form.html', form=form)