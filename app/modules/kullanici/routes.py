# app/modules/kullanici/routes.py

from app.form_builder import FieldType
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.form_builder import DataGrid
from app.extensions import db, get_tenant_db # db=MySQL, get_tenant_db=Firebird
from .forms import create_kullanici_form
import uuid

# Modeller
from app.modules.kullanici.models import Kullanici # Firebird (Gölge)
from app.models.master import User, UserTenantRole # MySQL (Master)
from app.modules.sube.models import Sube # Firebird Model

kullanici_bp = Blueprint('kullanici', __name__)

# =========================================================
# YARDIMCI FONKSİYON: FIREBIRD SENKRONİZASYONU
# =========================================================
def sync_user_to_firebird(user_id, ad_soyad, email, sube_id=None, aktif=True):
    """
    MySQL'deki kullanıcıyı Firebird'e zorla yazar.
    """
    tenant_db = get_tenant_db()
    if not tenant_db: return False, "Firebird bağlantısı yok"

    try:
        fb_user = tenant_db.query(Kullanici).get(user_id)
        
        if not fb_user:
            fb_user = Kullanici(
                id=str(user_id),
                firma_id=1,
                ad_soyad=ad_soyad,
                email=email,
                sube_id=sube_id,
                aktif=aktif
            )
            tenant_db.add(fb_user)
        else:
            fb_user.ad_soyad = ad_soyad
            fb_user.email = email
            if sube_id is not None:
                fb_user.sube_id = sube_id
            
            # Aktiflik durumunu güncelle
            fb_user.aktif = aktif
            
            if aktif and fb_user.silinmis:
                fb_user.silinmis = False

        tenant_db.commit()
        return True, "Senkronize edildi"
    except Exception as e:
        tenant_db.rollback()
        print(f"⚠️ Firebird Sync Hatası: {e}")
        return False, str(e)

# =========================================================
# ROTALAR
# =========================================================

@kullanici_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("kullanici_list", Kullanici, "Personel Listesi")
    grid.add_column('ad_soyad', 'Ad Soyad')
    grid.add_column('email', 'E-Posta')
    grid.add_column('sube.ad', 'Şube') 
    
    # Listede Aktif/Pasif durumunu görelim
    grid.add_column('aktif', 'Durum', type=FieldType.SWITCH) 

    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kullanici.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kullanici.sil')
    
    query = tenant_db.query(Kullanici).filter_by(firma_id=1)
    grid.process_query(query)
    
    return render_template('kullanici/index.html', grid=grid)


@kullanici_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_kullanici_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db()
            if not tenant_db: return jsonify({'success': False, 'message': 'Bağlantı hatası'}), 500

            try:
                data = form.get_data()
                email = data['email'].lower()
                
                # 1. AKTİFLİK DURUMU (DÜZELTİLDİ)
                # Formdan 'aktif' verisi geliyorsa True, gelmiyorsa False (Checkbox mantığı)
                # 'on', '1', 'true' gibi değerleri kontrol ediyoruz.
                raw_aktif = request.form.get('aktif')
                is_aktif = raw_aktif in ['on', '1', 'true', 'True']
                
                # MySQL İşlemleri
                master_user = User.query.filter_by(email=email).first()
                user_id = str(uuid.uuid4())
                
                if not master_user:
                    # Yeni kullanıcı global olarak da aktif olsun
                    master_user = User(id=user_id, email=email, full_name=data['ad_soyad'], is_active=True)
                    master_user.set_password(data['sifre'])
                    db.session.add(master_user)
                else:
                    user_id = master_user.id
                    master_user.full_name = data['ad_soyad']
                    if data.get('sifre'): master_user.set_password(data['sifre'])
                
                # Rol ve Yetki Durumu
                current_tenant_id = session.get('tenant_id')
                existing_role = UserTenantRole.query.filter_by(user_id=user_id, tenant_id=current_tenant_id).first()
                
                if existing_role: 
                    existing_role.role = data['rol']
                    existing_role.is_active = is_aktif # 👈 Rolü güncelle
                else:
                    new_role = UserTenantRole(
                        user_id=user_id, 
                        tenant_id=current_tenant_id, 
                        role=data['rol'],
                        is_active=is_aktif # 👈 Yeni rol
                    )
                    db.session.add(new_role)
                
                db.session.commit()
                
                # Firebird Eşitleme
                sube_id = int(data['sube_id']) if data['sube_id'] else None
                success, msg = sync_user_to_firebird(user_id, data['ad_soyad'], email, sube_id, is_aktif)
                
                if not success:
                    raise Exception(f"Firebird hatası: {msg}")
                
                return jsonify({'success': True, 'redirect': '/kullanici'})
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
                
    return render_template('kullanici/form.html', form=form)


@kullanici_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/')

    # Verileri çek
    fb_user = tenant_db.query(Kullanici).get(id)
    master_user = User.query.get(id)
    if not master_user:
         flash("Kullanıcı sistemde bulunamadı", "danger")
         return redirect('/kullanici')

    current_tenant_id = session.get('tenant_id')
    mysql_role = UserTenantRole.query.filter_by(user_id=id, tenant_id=current_tenant_id).first()
    
    # Form Hazırlığı
    form_obj = fb_user if fb_user else master_user
    if not fb_user:
        form_obj.ad_soyad = master_user.full_name
    
    # Form verilerini MySQL'den (Master Data) besle
    if mysql_role:
        setattr(form_obj, 'rol_kodu', mysql_role.role)
        # Aktiflik bilgisini MySQL'deki rol durumundan alıyoruz
        # Bu sayede form açıldığında veritabanındaki gerçek durumu görürsünüz.
        setattr(form_obj, 'aktif', mysql_role.is_active)

    form = create_kullanici_form(form_obj)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                # 1. AKTİFLİK DURUMU (DÜZELTİLDİ)
                # Direkt request.form'dan okuyoruz.
                raw_aktif = request.form.get('aktif')
                is_aktif = raw_aktif in ['on', '1', 'true', 'True']
                
                # 2. MySQL Güncelleme
                master_user.full_name = data['ad_soyad']
                master_user.email = data['email']
                if data.get('sifre'): master_user.set_password(data['sifre'])
                
                if mysql_role: 
                    mysql_role.role = data['rol']
                    mysql_role.is_active = is_aktif # 👈 Yetkiyi Aç/Kapa
                else:
                    new_role = UserTenantRole(
                        user_id=id, 
                        tenant_id=current_tenant_id, 
                        role=data['rol'],
                        is_active=is_aktif
                    )
                    db.session.add(new_role)

                db.session.commit()
                
                # 3. Firebird Güncelleme
                sube_id = int(data['sube_id']) if data['sube_id'] else None
                success, msg = sync_user_to_firebird(id, data['ad_soyad'], data['email'], sube_id, is_aktif)
                
                if not success:
                    raise Exception(f"Firebird Güncelleme Hatası: {msg}")
                
                return jsonify({'success': True, 'redirect': '/kullanici'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kullanici/form.html', form=form)

@kullanici_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    if id == current_user.id:
        return jsonify({'success': False, 'message': 'Kendinizi silemezsiniz!'}), 400
        
    try:
        current_tenant_id = session.get('tenant_id')
        UserTenantRole.query.filter_by(user_id=id, tenant_id=current_tenant_id).delete()
        db.session.commit()
        
        # Firebird tarafında silindi işaretle
        sync_user_to_firebird(id, "Silinmiş Kullanıcı", "silindi@silindi.com", None, False)
        
        tenant_db = get_tenant_db()
        fb_user = tenant_db.query(Kullanici).get(id)
        if fb_user:
            fb_user.silinmis = True
            tenant_db.commit()

        return jsonify({'success': True, 'message': 'Kullanıcı yetkisi kaldırıldı.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@kullanici_bp.route('/sync-all')
@login_required
def sync_all():
    tenant_db = get_tenant_db()
    current_tenant_id = session.get('tenant_id')
    
    roller = UserTenantRole.query.filter_by(tenant_id=current_tenant_id).all()
    count = 0
    errors = []
    
    for rol in roller:
        user = User.query.get(rol.user_id)
        if user:
            success, msg = sync_user_to_firebird(
                user.id, 
                user.full_name, 
                user.email, 
                sube_id=None,
                aktif=rol.is_active 
            )
            if success:
                count += 1
            else:
                errors.append(f"{user.email}: {msg}")
    
    if errors:
        flash(f"{count} kullanıcı senkronize edildi. Hatalar: {', '.join(errors)}", "warning")
    else:
        flash(f"{count} kullanıcı başarıyla Firebird ile eşitlendi.", "success")
        
    return redirect(url_for('kullanici.index'))