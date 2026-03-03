# app/modules/kasa/routes.py

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from app.extensions import get_tenant_db # ✨ YENİ: Tenant DB Importu
from app.modules.kasa.models import Kasa
from app.modules.sube.models import Sube
from app.modules.kullanici.models import Kullanici
from app.form_builder import DataGrid, FieldType
from .forms import create_kasa_form
from sqlalchemy.exc import IntegrityError

kasa_bp = Blueprint('kasa', __name__)

@kasa_bp.route('/')
@login_required
def index():
    """Kasa Listesi"""
    tenant_db = get_tenant_db() # ✨ YENİ: Tenant DB Bağlantısı
    
    grid = DataGrid("kasa_list", Kasa, "Kasa Tanımları")
    
    grid.set_column_label('kod', 'Kasa Kodu')
    grid.set_column_label('ad', 'Kasa Adı')
    grid.set_column_label('doviz_turu', 'Döviz')
    grid.set_column_label('aktif', 'Durum')
    grid.add_column('sube.ad', 'Şube', sortable='True')
    
    # Sorumlu Personel (İlişki üzerinden)
    grid.add_column('sorumlu.ad_soyad', 'Sorumlu (Zimmet)', width='150px')

    grid.add_action('islem','İşlem Yap','bi bi-arrow-left-right','btn-outline-success btn-sm', 'route', 'kasa_hareket.hizli_ekle')
    grid.add_action('edit', 'Düzelt', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kasa.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kasa.sil')

    # --- GÜVENLİK FİLTRESİ ---
    query = tenant_db.query(Kasa).filter_by(firma_id=current_user.firma_id)

    merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
    
    if current_user.rol not in merkez_rolleri:
        aktif_bolge_id = session.get('aktif_bolge_id')
        aktif_sube_id = session.get('aktif_sube_id')
        
        if aktif_bolge_id:
            query = query.join(Sube).filter(Sube.bolge_id == str(aktif_bolge_id))
        elif aktif_sube_id:
            query = query.filter(Kasa.sube_id == str(aktif_sube_id))

    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sube_id', 'plasiyer_id',
        'created_at', 'updated_at', 'muhasebe_hesap_id',
        'deleted_at', 'deleted_by', 'aciklama', 'kullanici_id'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    grid.process_query(query)
    
    return render_template('kasa/index.html', grid=grid)

@kasa_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_kasa_form()
    tenant_db = get_tenant_db()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                # Veri Hazırlığı (✨ UUID Güvenliği: int() yerine str() kullanıyoruz)
                m_id = request.form.get('muhasebe_hesap_id')
                m_id = str(m_id) if m_id and m_id.strip() else None

                # Zimmet Verisini Al
                k_id = request.form.get('kullanici_id')
                k_id = str(k_id) if k_id and k_id.strip() else None

                yeni_kasa = Kasa(
                    firma_id=current_user.firma_id,
                    sube_id=str(request.form.get('sube_id')) if request.form.get('sube_id') else None,
                    kullanici_id=k_id, 
                    kod=request.form.get('kod'),
                    ad=request.form.get('ad'),
                    doviz_turu=request.form.get('doviz_turu'),
                    aciklama=request.form.get('aciklama'),
                    muhasebe_hesap_id=m_id,
                    aktif=True if request.form.get('aktif') else False
                )
                
                tenant_db.add(yeni_kasa)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Kasa tanımlandı.', 'redirect': '/kasa'})
            
            except IntegrityError as e:
                tenant_db.rollback()
                if "UNIQUE" in str(e).upper() or "UQ_" in str(e).upper():
                     return jsonify({'success': False, 'message': f"Bu Kasa Kodu ({request.form.get('kod')}) zaten kullanılıyor."}), 400
                else:
                     return jsonify({'success': False, 'message': f"Veritabanı Hatası: {str(e)}"}), 500

            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kasa/form.html', form=form, title="Yeni Kasa")

# ✨ UUID UYUMU: <int:id> yerine <string:id>
@kasa_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    kasa = tenant_db.query(Kasa).get(str(id))
    
    if not kasa: return "Kasa bulunamadı", 404
    if str(kasa.firma_id) != str(current_user.firma_id): return "Yetkisiz", 403

    form = create_kasa_form(kasa)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                m_id = request.form.get('muhasebe_hesap_id')
                k_id = request.form.get('kullanici_id')

                kasa.sube_id = str(request.form.get('sube_id')) if request.form.get('sube_id') else None
                # Zimmet Verisini Güncelle
                kasa.kullanici_id = str(k_id) if k_id and k_id.strip() else None
                
                kasa.kod = request.form.get('kod')
                kasa.ad = request.form.get('ad')
                kasa.doviz_turu = request.form.get('doviz_turu')
                kasa.aciklama = request.form.get('aciklama')
                kasa.muhasebe_hesap_id = str(m_id) if m_id and m_id.strip() else None
                kasa.aktif = True if request.form.get('aktif') else False
                
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Kasa güncellendi.', 'redirect': '/kasa'})
            
            except IntegrityError as e:
                tenant_db.rollback()
                if "UNIQUE" in str(e).upper() or "UQ_" in str(e).upper():
                     return jsonify({'success': False, 'message': f"Bu Kasa Kodu ({request.form.get('kod')}) başka bir kasada kullanılıyor."}), 400
                else:
                     return jsonify({'success': False, 'message': f"Veritabanı Hatası: {str(e)}"}), 500

            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kasa/form.html', form=form, title="Kasa Düzenle")

# ✨ UUID UYUMU: <int:id> yerine <string:id>
@kasa_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    try:
        kasa = tenant_db.query(Kasa).get(str(id))
        if not kasa: 
            return jsonify({'success': False, 'message': 'Kasa bulunamadı.'}), 404
            
        if str(kasa.firma_id) != str(current_user.firma_id): 
            return jsonify({'success': False, 'message': 'Yetkisiz işlem.'}), 403

        if kasa.hareketler and len(kasa.hareketler) > 0:
            return jsonify({'success': False, 'message': 'Hareket gören kasa silinemez, pasife alınız.'}), 400
        
        tenant_db.delete(kasa)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Kasa silindi.'})

    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- OTO NUMARA API ---
@kasa_bp.route('/api/siradaki-kod')
@login_required
def api_siradaki_kod():
    """
    Sıradaki Kasa Kodunu Üretir.
    Varsayılan Başlangıç: KS-001
    """
    tenant_db = get_tenant_db()
    son_kasa = tenant_db.query(Kasa).filter_by(firma_id=current_user.firma_id)\
        .order_by(Kasa.created_at.desc()).first()
    
    # Varsayılan başlangıç
    yeni_kod = "KS-001"
    
    if son_kasa and son_kasa.kod:
        try:
            mevcut_kod = son_kasa.kod
            
            if '-' in mevcut_kod:
                parcalar = mevcut_kod.rsplit('-', 1)
                prefix = parcalar[0]
                numara = parcalar[1]
                
                if numara.isdigit():
                    yeni_num = str(int(numara) + 1).zfill(len(numara))
                    yeni_kod = f"{prefix}-{yeni_num}"

            elif '.' in mevcut_kod:
                parcalar = mevcut_kod.rsplit('.', 1)
                prefix = parcalar[0]
                numara = parcalar[1]
                
                if numara.isdigit():
                    yeni_num = str(int(numara) + 1).zfill(len(numara))
                    yeni_kod = f"{prefix}.{yeni_num}"

            elif mevcut_kod.isdigit():
                yeni_kod = str(int(mevcut_kod) + 1).zfill(len(mevcut_kod))
                
        except Exception as e:
            print(f"Kod üretim hatası: {e}")
            pass
            
    return jsonify({'code': yeni_kod})