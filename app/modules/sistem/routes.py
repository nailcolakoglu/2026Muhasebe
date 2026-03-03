# app/modules/sistem/routes.py

from flask import Blueprint, render_template, request, jsonify, session, abort, url_for
from flask_login import login_required, current_user, login_user, logout_user
from app.modules.firmalar.models import SystemMenu
from app.modules.firmalar.models import Firma, Donem
from app.modules.kullanici.models import Kullanici
from app.modules.sube.models import Sube
from app.extensions import db, get_tenant_db  # <-- get_tenant_db EKLENDİ
from app.form_builder import DataGrid
from .forms import create_menu_form

sistem_bp = Blueprint('sistem', __name__)

@sistem_bp.route('/menu')
@login_required
def menu_index():
    tenant_db = get_tenant_db() # <-- TENANT DB
    
    grid = DataGrid("menu_grid", SystemMenu, "Menü Yönetimi")
    grid.add_column('id', 'ID', width='50px')
    grid.add_column('gorunum_baslik', 'Başlık') 
    grid.add_column('gorunum_ust_menu', 'Üst Menü')
    grid.add_column('gorunum_hedef', 'Hedef')
    grid.add_column('yetkili_roller', 'Yetkili Roller')
    grid.add_column('sira', 'Sıra', width='70px')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'sistem.menu_duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'sistem.menu_sil')
    
    # Sıralamayı hiyerarşiye uygun yapalım (Tenant DB Üzerinden)
    # query = tenant_db.query(SystemMenu).filter_by(firma_id=current_user.firma_id).order_by(SystemMenu.parent_id, SystemMenu.sira)
    query = tenant_db.query(SystemMenu).order_by(SystemMenu.parent_id, SystemMenu.sira)
    grid.process_query(query)
    
    return render_template(
        'base_grid.html', 
        grid=grid, 
        endpoint='sistem.menu_index',
        add_url=url_for('sistem.menu_ekle'),  # Butonun gideceği adres
        add_btn_text='Menü Ekle'              # Butonun üzerinde yazacak metin
    )

# --- EKLEME / DÜZENLEME ---
def save_menu(form, menu=None):
    tenant_db = get_tenant_db() # <-- TENANT DB
    data = form.get_data()
    
    if not menu:
        menu = SystemMenu()
        #menu.firma_id = current_user.firma_id # Firma ID zorunlu!
        tenant_db.add(menu)
    
    menu.baslik = data.get('baslik')
    menu.icon = data.get('icon')
    menu.endpoint = data.get('endpoint')
    menu.url = data.get('url')
    menu.yetkili_roller = data.get('yetkili_roller')
    menu.sira = int(data.get('sira') or 0)
    
    # Checkbox Kontrolü
    menu.aktif = True if str(data.get('aktif')).lower() in ['true', '1', 'on'] else False
    
    # Parent ID Kontrolü (UUID Uyumlu)
    p_id = data.get('parent_id')
    if p_id and str(p_id) != '' and str(p_id) != '0':
        menu.parent_id = str(p_id)
    else:
        menu.parent_id = None
        
    tenant_db.commit()
    
    
@sistem_bp.route('/menu/ekle', methods=['GET', 'POST'])
@login_required
def menu_ekle():
    form = create_menu_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            save_menu(form)
            # YENİ MENÜNÜN GÖRÜNMESİ İÇİN CACHE TEMİZLEME
            from app.form_builder.menu_manager import MenuManager
            MenuManager.clear_cache()
            return jsonify({'success': True, 'redirect': '/sistem/menu'})
    return render_template('base_form.html', form=form)
    

# DİKKAT: int:id yerine string:id
@sistem_bp.route('/menu/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def menu_duzenle(id):
    tenant_db = get_tenant_db()
    menu = tenant_db.get(SystemMenu, str(id))
    if not menu: abort(404)
        
    form = create_menu_form(menu)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            save_menu(form, menu)
            from app.form_builder.menu_manager import MenuManager
            MenuManager.clear_cache()
            return jsonify({'success': True, 'redirect': '/sistem/menu'})
    return render_template('base_form.html', form=form)
    
    
# DİKKAT: int:id yerine string:id
@sistem_bp.route('/menu/sil/<string:id>', methods=['POST'])
@login_required
def menu_sil(id):
    tenant_db = get_tenant_db()
    menu = tenant_db.get(SystemMenu, str(id))
    if not menu: return jsonify({'success': False}), 404
        
    tenant_db.delete(menu)
    tenant_db.commit()
    
    from app.form_builder.menu_manager import MenuManager
    MenuManager.clear_cache()
    return jsonify({'success': True})
    
    
@sistem_bp.route('/firmalar')
@login_required
def firma_listesi():
    # Sadece Süper Admin görebilir (is_super_admin alanını User modeline eklemelisin)
    if not current_user.kullanici_adi == 'master_admin': # Veya db'de bir flag
        return "Yetkisiz Alan", 403

    # FirmaFilteredQuery kullanmadan tüm firmaları çekmeliyiz
    # Bunun için doğrudan db.session.query kullanabiliriz veya filter'ı devre dışı bırakırız.
    firmalar = Firma.query.all() 
    return render_template('sistem/firmalar.html', firmalar=firmalar)

@sistem_bp.route('/yeni-firma', methods=['POST'])
@login_required
def yeni_firma_olustur():
    # 1.Form Verilerini Al (Hata buradaydı, bu satırlar eksikti)
    unvan = request.form.get('unvan')
    vergi_no = request.form.get('vergi_no')
    email = request.form.get('email')
    sifre = request.form.get('sifre')

    # 2.Basit Doğrulama
    if not unvan or not email or not sifre:
        return jsonify({'success': False, 'message': 'Firma Ünvanı, Email ve Şifre alanları zorunludur!'}), 400

    try:
        # 3.Tenant Manager'ı Çağır
        from tenant_manager import create_new_tenant
        create_new_tenant(unvan, email, sifre, vergi_no)
        
        return jsonify({'success': True, 'message': 'Firma kurulumu başarıyla tamamlandı.'})
        
    except Exception as e:
        # Hata durumunda loglayalım ve ekrana basalım
        print(f"KURULUM HATASI: {str(e)}")
        return jsonify({'success': False, 'message': f"Sistem Hatası: {str(e)}"}), 500

@sistem_bp.route('/giris-yap/<int:firma_id>', methods=['POST'])
@login_required
def firmaya_gecis_yap(firma_id):
    # 1.Güvenlik: Sadece Master Admin yapabilir
    # (Buraya kendi güvenlik kuralını koymalısın, şimdilik basit tutuyorum)
    if not current_user.rol == 'admin': 
        return jsonify({'success': False, 'message': 'Yetkisiz işlem!'}), 403

    try:
        # 2.Hedef firmanın yönetici kullanıcısını bul
        # Genelde ilk oluşturulan veya 'admin' rolündeki kullanıcıdır
        target_user = Kullanici.query.filter_by(
            firma_id=firma_id, 
            rol='admin',
            aktif=True
        ).first()

        if not target_user:
            return jsonify({'success': False, 'message': 'Bu firmada aktif yönetici bulunamadı.'}), 404

        # 3.Mevcut oturumu kapat ve yeni kullanıcı olarak oturum aç (Sihirli Kısım ✨)
        logout_user()
        login_user(target_user)
        
        # Session'daki eski verileri temizle
        session.pop('aktif_donem_id', None)
        session.pop('aktif_sube_id', None)

        return jsonify({'success': True, 'redirect': '/'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
        
        
@sistem_bp.route('/api/set-context', methods=['POST'])
@login_required
def set_context():
    """Üst menüden Şube veya Dönem değiştirildiğinde Session'ı günceller"""
    try:
        # Ajax'tan gelen JSON verisini al (Örn: {type: 'sube', id: 'UUID'})
        data = request.get_json()
        ctx_type = data.get('type')
        ctx_id = data.get('id')

        if ctx_type == 'sube':
            if ctx_id == 'all':
                session.pop('aktif_sube_id', None) # Tüm Şubeler seçildiyse sil
            else:
                session['aktif_sube_id'] = str(ctx_id)
                
        elif ctx_type == 'donem':
            if ctx_id == 'all':
                session.pop('aktif_donem_id', None)
            else:
                session['aktif_donem_id'] = str(ctx_id)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
