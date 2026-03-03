# app/modules/kullanici/routes.py

from app.form_builder import FieldType
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.form_builder import DataGrid
from app.extensions import db, get_tenant_db # db=Master MySQL, get_tenant_db=Tenant MySQL
from .forms import create_kullanici_form
import uuid
from datetime import datetime

# Modeller
from app.modules.kullanici.models import Kullanici # Tenant
from app.models.master import User, UserTenantRole # Master
from app.modules.sube.models import Sube # Tenant

kullanici_bp = Blueprint('kullanici', __name__)

# =========================================================
# YARDIMCI FONKSİYON: TENANT SENKRONİZASYONU
# =========================================================
def sync_user_to_tenant(user_id, firma_id, ad_soyad, email, sube_id=None, aktif=True):
    """
    Master DB'deki kullanıcıyı firmanın kendi veritabanına (Tenant DB) yazar.
    """
    tenant_db = get_tenant_db()
    if not tenant_db: return False, "Tenant veritabanı bağlantısı yok"

    try:
        t_user = tenant_db.query(Kullanici).get(str(user_id))
        
        if not t_user:
            t_user = Kullanici(
                id=str(user_id),
                firma_id=str(firma_id), # ✨ DÜZELTME 2: Hardcoded 1 yerine UUID firma_id
                ad_soyad=ad_soyad,
                email=email,
                sube_id=str(sube_id) if sube_id else None,
                aktif=aktif
            )
            tenant_db.add(t_user)
        else:
            t_user.ad_soyad = ad_soyad
            t_user.email = email
            t_user.firma_id = str(firma_id)
            if sube_id is not None:
                t_user.sube_id = str(sube_id)
            
            t_user.aktif = aktif
            
            # ✨ DÜZELTME 3: silinmis sütunu yerine deleted_at kontrolü
            if aktif and getattr(t_user, 'deleted_at', None) is not None:
                t_user.deleted_at = None

        tenant_db.commit()
        return True, "Senkronize edildi"
    except Exception as e:
        tenant_db.rollback()
        print(f"⚠️ Tenant Sync Hatası: {e}")
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
    
    grid.add_column('aktif', 'Durum', type=FieldType.SWITCH) 

    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kullanici.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kullanici.sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sube_id', 
        'aktif', 'olusturma_tarihi', 'created_at', 'updated_at',
        'deleted_at', 'deleted_by',        
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    
    # ✨ Sadece silinmemişleri ve o firmaya ait olanları getir
    query = tenant_db.query(Kullanici).filter(
        Kullanici.firma_id == str(current_user.firma_id),
        Kullanici.deleted_at.is_(None)
    )
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
                
                raw_aktif = request.form.get('aktif')
                is_aktif = raw_aktif in ['on', '1', 'true', 'True']
                
                master_user = User.query.filter_by(email=email).first()
                user_id = str(uuid.uuid4())
                
                if not master_user:
                    master_user = User(id=user_id, email=email, full_name=data['ad_soyad'], is_active=True)
                    master_user.set_password(data['sifre'])
                    db.session.add(master_user)
                else:
                    user_id = str(master_user.id)
                    master_user.full_name = data['ad_soyad']
                    if data.get('sifre'): master_user.set_password(data['sifre'])
                
                current_tenant_id = str(current_user.firma_id)
                existing_role = UserTenantRole.query.filter_by(user_id=user_id, tenant_id=current_tenant_id).first()
                
                if existing_role: 
                    existing_role.role = data['rol']
                    existing_role.is_active = is_aktif 
                else:
                    new_role = UserTenantRole(
                        user_id=user_id, 
                        tenant_id=current_tenant_id, 
                        role=data['rol'],
                        is_active=is_aktif 
                    )
                    db.session.add(new_role)
                
                db.session.commit()
                
                # ✨ DÜZELTME 4: int() çevirimi silindi, str() zorlaması getirildi
                sube_id = str(data['sube_id']) if data.get('sube_id') else None
                success, msg = sync_user_to_tenant(user_id, current_tenant_id, data['ad_soyad'], email, sube_id, is_aktif)
                
                if not success:
                    raise Exception(f"Tenant DB Senkronizasyon hatası: {msg}")
                
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
    t_user = tenant_db.query(Kullanici).get(str(id))
    master_user = User.query.get(str(id))
    
    if not master_user:
         flash("Kullanıcı Master DB'de bulunamadı", "danger")
         return redirect('/kullanici')

    current_tenant_id = str(current_user.firma_id)
    mysql_role = UserTenantRole.query.filter_by(user_id=str(id), tenant_id=current_tenant_id).first()
    
    form_obj = t_user if t_user else master_user
    if not t_user:
        form_obj.ad_soyad = master_user.full_name
    
    if mysql_role:
        setattr(form_obj, 'rol_kodu', mysql_role.role)
        setattr(form_obj, 'aktif', mysql_role.is_active)

    form = create_kullanici_form(form_obj)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                raw_aktif = request.form.get('aktif')
                is_aktif = raw_aktif in ['on', '1', 'true', 'True']
                
                master_user.full_name = data['ad_soyad']
                master_user.email = data['email']
                if data.get('sifre'): master_user.set_password(data['sifre'])
                
                if mysql_role: 
                    mysql_role.role = data['rol']
                    mysql_role.is_active = is_aktif 
                else:
                    new_role = UserTenantRole(
                        user_id=str(id), 
                        tenant_id=current_tenant_id, 
                        role=data['rol'],
                        is_active=is_aktif
                    )
                    db.session.add(new_role)

                db.session.commit()
                
                # ✨ UUID Koruması
                sube_id = str(data['sube_id']) if data.get('sube_id') else None
                success, msg = sync_user_to_tenant(id, current_tenant_id, data['ad_soyad'], data['email'], sube_id, is_aktif)
                
                if not success:
                    raise Exception(f"Tenant Güncelleme Hatası: {msg}")
                
                return jsonify({'success': True, 'redirect': '/kullanici'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kullanici/form.html', form=form)

@kullanici_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    if str(id) == str(current_user.id):
        return jsonify({'success': False, 'message': 'Kendinizi silemezsiniz!'}), 400
        
    try:
        current_tenant_id = str(current_user.firma_id)
        UserTenantRole.query.filter_by(user_id=str(id), tenant_id=current_tenant_id).delete()
        db.session.commit()
        
        # Sadece bu firmadaki yetkisini kapat ve Tenant tarafında soft delete yap
        sync_user_to_tenant(id, current_tenant_id, "Silinmiş Kullanıcı", "silindi@silindi.com", None, False)
        
        tenant_db = get_tenant_db()
        t_user = tenant_db.query(Kullanici).get(str(id))
        if t_user:
            t_user.deleted_at = datetime.now() # ✨ silinmis yerine deleted_at kullanıldı
            t_user.aktif = False
            tenant_db.commit()

        return jsonify({'success': True, 'message': 'Kullanıcı yetkisi kaldırıldı.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@kullanici_bp.route('/sync-all')
@login_required
def sync_all():
    tenant_db = get_tenant_db()
    current_tenant_id = str(current_user.firma_id)
    
    roller = UserTenantRole.query.filter_by(tenant_id=current_tenant_id).all()
    count = 0
    errors = []
    
    for rol in roller:
        user = User.query.get(str(rol.user_id))
        if user:
            success, msg = sync_user_to_tenant(
                user.id,
                current_tenant_id, # ✨ DÜZELTME: Firma ID dinamik olarak gönderildi
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
        flash(f"{count} kullanıcı başarıyla Tenant DB ile eşitlendi.", "success")
        
    return redirect(url_for('kullanici.index'))