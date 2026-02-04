from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from app.extensions import db 
from app.modules.kasa.models import Kasa
from app.modules.sube.models import Sube
from app.modules.kullanici.models import Kullanici
from app.form_builder import DataGrid, FieldType
from .forms import create_kasa_form
# 👇 Hata yakalamak için gerekli kütüphane
from sqlalchemy.exc import IntegrityError

kasa_bp = Blueprint('kasa', __name__)

@kasa_bp.route('/')
@login_required
def index():
    """Kasa Listesi"""
    grid = DataGrid("kasa_list", Kasa, "Kasa Tanımları")
    
    grid.set_column_label('kod', 'Kasa Kodu')
    grid.set_column_label('ad', 'Kasa Adı')
    grid.set_column_label('doviz_turu', 'Döviz')
    grid.set_column_label('aktif', 'Durum')
    grid.add_column('sube.ad', 'Şube', sortable='True')
    
    # 👇 YENİ KOLON: Sorumlu Personel (İlişki üzerinden)
    # Modelde sorumlu = db.relationship(...) olduğu için sorumlu.ad_soyad diyebiliriz.
    grid.add_column('sorumlu.ad_soyad', 'Sorumlu (Zimmet)', width='150px')

    grid.add_action('islem','İşlem Yap','bi bi-arrow-left-right','btn-outline-success btn-sm', 'route', 'kasa_hareket.hizli_ekle')
    grid.add_action('edit', 'Düzelt', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'kasa.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'kasa.sil')

    grid.hide_column('id').hide_column('firma_id').hide_column('muhasebe_hesap_id').hide_column('sube_id').hide_column('kullanici_id')

    # --- GÜVENLİK FİLTRESİ ---
    query = Kasa.query.filter_by(firma_id=current_user.firma_id)

    merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
    
    if current_user.rol not in merkez_rolleri:
        aktif_bolge_id = session.get('aktif_bolge_id')
        aktif_sube_id = session.get('aktif_sube_id')
        
        if aktif_bolge_id:
            query = query.join(Sube).filter(Sube.bolge_id == aktif_bolge_id)
        elif aktif_sube_id:
            query = query.filter(Kasa.sube_id == aktif_sube_id)

    grid.process_query(query)
    
    
    return render_template('kasa/index.html', grid=grid)

@kasa_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_kasa_form()
    
    if request.method == 'POST':
        if form.validate(request.form):
            try:
                # Veri Hazırlığı
                m_id = request.form.get('muhasebe_hesap_id')
                m_id = int(m_id) if m_id and m_id.strip() else None

                # 👇 Zimmet Verisini Al
                k_id = request.form.get('kullanici_id')
                k_id = int(k_id) if k_id and k_id.strip() else None

                yeni_kasa = Kasa(
                    firma_id=current_user.firma_id,
                    sube_id=request.form.get('sube_id'),
                    kullanici_id=k_id, # Yeni Alan
                    kod=request.form.get('kod'),
                    ad=request.form.get('ad'),
                    doviz_turu=request.form.get('doviz_turu'),
                    aciklama=request.form.get('aciklama'),
                    muhasebe_hesap_id=m_id,
                    aktif=True if request.form.get('aktif') else False
                )
                
                db.session.add(yeni_kasa)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Kasa tanımlandı.', 'redirect': '/kasa'})
            
            except IntegrityError as e:
                db.session.rollback()
                if "UNIQUE" in str(e).upper() or "UQ_" in str(e).upper():
                     return jsonify({'success': False, 'message': f"Bu Kasa Kodu ({request.form.get('kod')}) zaten kullanılıyor."}), 400
                else:
                     return jsonify({'success': False, 'message': f"Veritabanı Hatası: {str(e)}"}), 500

            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kasa/form.html', form=form, title="Yeni Kasa")

@kasa_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    kasa = Kasa.query.get_or_404(id)
    if kasa.firma_id != current_user.firma_id: return "Yetkisiz", 403

    form = create_kasa_form(kasa)
    
    if request.method == 'POST':
        if form.validate(request.form):
            try:
                m_id = request.form.get('muhasebe_hesap_id')
                k_id = request.form.get('kullanici_id')

                kasa.sube_id = request.form.get('sube_id')
                # 👇 Zimmet Verisini Güncelle
                kasa.kullanici_id = int(k_id) if k_id and k_id.strip() else None
                
                kasa.kod = request.form.get('kod')
                kasa.ad = request.form.get('ad')
                kasa.doviz_turu = request.form.get('doviz_turu')
                kasa.aciklama = request.form.get('aciklama')
                kasa.muhasebe_hesap_id = int(m_id) if m_id and m_id.strip() else None
                kasa.aktif = True if request.form.get('aktif') else False
                
                db.session.commit()
                return jsonify({'success': True, 'message': 'Kasa güncellendi.', 'redirect': '/kasa'})
            
            except IntegrityError as e:
                db.session.rollback()
                if "UNIQUE" in str(e).upper() or "UQ_" in str(e).upper():
                     return jsonify({'success': False, 'message': f"Bu Kasa Kodu ({request.form.get('kod')}) başka bir kasada kullanılıyor."}), 400
                else:
                     return jsonify({'success': False, 'message': f"Veritabanı Hatası: {str(e)}"}), 500

            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('kasa/form.html', form=form, title="Kasa Düzenle")

@kasa_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    try:
        kasa = Kasa.query.get_or_404(id)
        if kasa.firma_id != current_user.firma_id: 
            return jsonify({'success': False, 'message': 'Yetkisiz işlem.'}), 403

        if kasa.hareketler and len(kasa.hareketler) > 0:
            return jsonify({'success': False, 'message': 'Hareket gören kasa silinemez, pasife alınız.'}), 400
        
        db.session.delete(kasa)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Kasa silindi.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- OTO NUMARA API ---
@kasa_bp.route('/api/siradaki-kod')
@login_required
def api_siradaki_kod():
    """
    Sıradaki Kasa Kodunu Üretir.
    Varsayılan Başlangıç: KS-001
    """
    son_kasa = Kasa.query.filter_by(firma_id=current_user.firma_id)\
        .order_by(Kasa.id.desc()).first()
    
    # Varsayılan başlangıç
    yeni_kod = "KS-001"
    
    if son_kasa and son_kasa.kod:
        try:
            mevcut_kod = son_kasa.kod
            
            # Senaryo 1: KS-001 gibi Tireli Format
            if '-' in mevcut_kod:
                parcalar = mevcut_kod.rsplit('-', 1)
                prefix = parcalar[0]
                numara = parcalar[1]
                
                if numara.isdigit():
                    # Mevcut numaranın uzunluğunu koru (001 -> 3 hane)
                    yeni_num = str(int(numara) + 1).zfill(len(numara))
                    yeni_kod = f"{prefix}-{yeni_num}"

            # Senaryo 2: 100.01 gibi Noktalı Format (Muhasebe Kodu)
            elif '.' in mevcut_kod:
                parcalar = mevcut_kod.rsplit('.', 1)
                prefix = parcalar[0]
                numara = parcalar[1]
                
                if numara.isdigit():
                    yeni_num = str(int(numara) + 1).zfill(len(numara))
                    yeni_kod = f"{prefix}.{yeni_num}"

            # Senaryo 3: 001 gibi Sadece Sayı
            elif mevcut_kod.isdigit():
                yeni_kod = str(int(mevcut_kod) + 1).zfill(len(mevcut_kod))
                
        except Exception as e:
            print(f"Kod üretim hatası: {e}")
            # Hata olursa varsayılan (KS-001) döner
            pass
            
    return jsonify({'code': yeni_kod})