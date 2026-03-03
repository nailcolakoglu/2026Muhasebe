# app/modules/siparis/routes.py

from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify, url_for, flash, current_app, redirect, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.extensions import get_tenant_db # 👈 Firebird Bağlantısı Şart
from app.modules.siparis.models import Siparis
from app.modules.doviz.models import DovizKuru
from app.modules.stok.models import StokKart
from app.modules.cari.models import CariHesap
from app.modules.kullanici.models import Kullanici
from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
from app.form_builder import DataGrid
from .forms import create_siparis_form
from .services import SiparisService 
from datetime import datetime
from app.enums import SiparisDurumu
from app.modules.rapor.doc_engine import DocumentGenerator
from app.signals import siparis_faturalandi

siparis_bp = Blueprint('siparis', __name__)

@siparis_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("siparis_grid", Siparis, "Siparişler")
    
    #grid.add_column('belge_no', 'Sipariş No')
    #grid.add_column('tarih', 'Tarih', type='date')
    grid.add_column('cari.unvan', 'Müşteri')
    grid.add_column('plasiyer.ad_soyad', 'Plasiyer')
    
    grid.add_column('durum', 'Durum', type='badge', badge_colors={
        'bekliyor': 'warning', 'onaylandi': 'success', 'iptal': 'danger', 'faturalandi': 'info', 'tamamlandi': 'success'
    })  
    
    grid.add_action('print', 'Yazdır', 'bi bi-printer', 'btn-outline-secondary btn-sm', 'route', 'siparis.yazdir', target='_blank')

    if current_user.rol in ['admin', 'patron', 'satis_muduru']:
        grid.add_action('approve', 'Onayla', 'bi bi-check-lg', 'btn-outline-success btn-sm', 'ajax', 'siparis.onayla')
    
    if current_user.rol in ['admin', 'depo', 'lojistik']:
        grid.add_action('ship', 'Sevk Et', 'bi bi-truck', 'btn-outline-warning btn-sm', 'route', 'siparis.sevk_et')

    if current_user.rol in ['admin', 'muhasebe_muduru', 'finans']:
        grid.add_action('convert', 'Faturala', 'bi bi-receipt', 'btn-outline-success btn-sm', 'ajax', 'siparis.faturala')

    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'siparis.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'siparis.sil')

    #query = tenant_db.query(Siparis).order_by(Siparis.tarih.desc())
    query = tenant_db.query(Siparis).filter_by(firma_id=str(current_user.firma_id))
    
    # Plasiyer sadece kendi siparişlerini listede görsün
    if current_user.rol == 'plasiyer':
        query = query.filter_by(plasiyer_id=str(current_user.id))
        
    
    if not request.args.get('show_all'):
        query = query.filter(Siparis.durum != SiparisDurumu.FATURALANDI.value)

    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'plasiyer_id', 'created_at', 
        'donem_id', 'sube_id', 'updated_at', 'deleted_at'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    grid.hide_column('fiyat_listesi_id').hide_column('odeme_plani_id').hide_column('sevk_adresi').hide_column('onaylayan_id').hide_column('onay_tarihi')
    grid.hide_column('depo_id').hide_column('cari_id').hide_column('doviz_turu').hide_column('doviz_kuru').hide_column('kayip_nedeni')
    grid.hide_column('ara_toplam').hide_column('iskonto_toplam').hide_column('kdv_toplam').hide_column('genel_toplam').hide_column('dovizli_toplam')
    grid.hide_column('tahmini_karlilik').hide_column('oncelik_skoru')

    grid.process_query(query)
    return render_template('siparis/index.html', grid=grid)

@siparis_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_siparis_form()
    if request.method == 'POST':
        try:
            success, msg = SiparisService.save(request.form)
            if success:
                return jsonify({'success': True, 'message': msg, 'redirect': url_for('siparis.index')})
            else:
                return jsonify({'success': False, 'message': msg}), 400
        except Exception as e:
            return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
            
    return render_template('siparis/form.html', form=form)

@siparis_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    if not tenant_db: return redirect('/siparis')

    # 👈 DÜZELTME: get_or_404 yerine tenant_db.get kullanıyoruz
    siparis = tenant_db.query(Siparis).get(id)
    if not siparis: abort(404)

    # ✨ 2. YENİ: Başkasının siparişini düzenleme engeli!
    if current_user.rol == 'plasiyer' and str(siparis.plasiyer_id) != str(current_user.id):
        if request.method == 'POST':
            return jsonify({'success': False, 'message': 'Yetki Hatası: Sadece kendi girdiğiniz siparişleri değiştirebilirsiniz!'}), 403
        else:
            flash("Yetki Hatası: Sadece kendi girdiğiniz siparişleri düzenleyebilirsiniz.", "danger")
            return redirect(url_for('siparis.index'))

    kilitli_durumlar = [
        SiparisDurumu.FATURALANDI.value, 
        SiparisDurumu.IPTAL.value, 
        SiparisDurumu.TAMAMLANDI.value
    ]
    
    if siparis.durum in kilitli_durumlar:
        flash(f'Bu sipariş {siparis.durum} durumunda olduğu için düzenlenemez! Sadece görüntülenebilir.', 'warning')
        return redirect(url_for('siparis.index'))
    
    form = create_siparis_form(siparis)
    
    if request.method == 'POST':
        try:
            success, msg = SiparisService.save(request.form, siparis)
            if success:
                return jsonify({'success': True, 'message': msg, 'redirect': url_for('siparis.index')})
            else:
                return jsonify({'success': False, 'message': msg}), 400
        except Exception as e:
            return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
                
    return render_template('siparis/form.html', form=form)

@siparis_bp.route('/sevk-et/<string:id>', methods=['GET', 'POST'])
@login_required
def sevk_et(id):
    tenant_db = get_tenant_db()
    
    try:
        siparis = tenant_db.query(Siparis).get(str(id))
        if not siparis: 
            return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
            
        # ✨ 3. YENİ: Başkasının siparişini silme engeli!
        if current_user.rol == 'plasiyer' and str(siparis.plasiyer_id) != str(current_user.id):
            return jsonify({'success': False, 'message': 'Yetki Hatası: Sadece kendi girdiğiniz siparişleri silebilirsiniz!'}), 403
    except:
        pass
    yasakli_durumlar = [SiparisDurumu.BEKLIYOR.value, SiparisDurumu.TAMAMLANDI.value, SiparisDurumu.FATURALANDI.value]
    sevkiyat_var_mi = any(d.teslim_edilen_miktar > 0 for d in siparis.detaylar)
    
    if siparis.durum in yasakli_durumlar:
        msg = "Hata: Sadece ONAYLANDI veya KISMİ durumundaki siparişler sevk edilebilir."
        if request.method == 'GET':
            flash(msg, 'danger')
            return redirect(url_for('siparis.index'))
        return jsonify({'success': False, 'message': msg})

    if request.method == 'GET':
        return render_template('siparis/sevkiyat_form.html', siparis=siparis)

    try:
        miktarlar = request.form.getlist('sevk_miktar[]')
        detay_ids = request.form.getlist('detay_id[]')
        
        success, msg = SiparisService.sevk_et(siparis, miktarlar, detay_ids)
        if success:
            return jsonify({'success': True, 'message': msg, 'redirect': url_for('siparis.index')})
        else:
            return jsonify({'success': False, 'message': msg}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@siparis_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    siparis = tenant_db.query(Siparis).get(id)
    if not siparis: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
    
    kilitli_durumlar = [SiparisDurumu.KISMI.value, SiparisDurumu.TAMAMLANDI.value, SiparisDurumu.FATURALANDI.value]
    if siparis.durum in kilitli_durumlar:
        return jsonify({'success': False, 'message': 'İşlem görmüş siparişler silinemez!'}), 400

    sevkiyat_var_mi = any(d.teslim_edilen_miktar > 0 for d in siparis.detaylar)
    if sevkiyat_var_mi:
         return jsonify({'success': False, 'message': 'Hareket gören siparişler silinemez!'}), 400

    try:
        tenant_db.delete(siparis)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Sipariş kalıcı olarak silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@siparis_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    if not tenant_db: return jsonify({'code': ''})
    
    count = tenant_db.query(Siparis).count()
    return jsonify({'code': f"SIP-{datetime.now().year}-{str(count+1).zfill(4)}"})

@siparis_bp.route('/onayla/<string:id>', methods=['POST'])
@login_required
def onayla(id):
    tenant_db = get_tenant_db()
    siparis = tenant_db.query(Siparis).get(id)
    if not siparis: return jsonify({'success': False, 'message': 'Kayıt yok'}), 404
    
    # DÜZELTME: Her iki tarafı da .lower() ile küçülterek harf uyuşmazlığını eziyoruz
    if siparis.durum.lower() != SiparisDurumu.BEKLIYOR.value.lower():
        return jsonify({'success': False, 'message': f'Sadece BEKLIYOR durumundakiler onaylanabilir.'}), 400

    try:
        siparis.durum = SiparisDurumu.ONAYLANDI.value
        siparis.onay_tarihi = datetime.now()
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Sipariş başarıyla onaylandı.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@siparis_bp.route('/faturala/<string:id>', methods=['POST'])
@login_required
def faturala(id):
    tenant_db = get_tenant_db()
    siparis = tenant_db.query(Siparis).get(id)
    
    if siparis.durum != SiparisDurumu.TAMAMLANDI.value:
        return jsonify({'success': False, 'message': 'Sadece TAMAMLANMIŞ siparişler faturalanabilir!'}), 400
        
    try:
        sonuc_kutusu = {} 
        siparis_faturalandi.send(
            current_app._get_current_object(),
            siparis=siparis,
            olusan_fatura_id=sonuc_kutusu
        )
        
        siparis.durum = SiparisDurumu.FATURALANDI.value
        tenant_db.commit()
        
        yeni_fatura_id = sonuc_kutusu.get('olusan_fatura_id')
        if yeni_fatura_id:
             return jsonify({
                'success': True, 
                'message': 'Sipariş faturaya dönüştürüldü.', 
                'redirect': url_for('fatura.duzenle', id=yeni_fatura_id)
            })
        
        return jsonify({'success': True, 'message': 'Sipariş faturalandı işaretlendi.'})
        
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500

@siparis_bp.route('/api/get-urun-detay')
@login_required
def api_get_urun_detay():
    tenant_db = get_tenant_db()
    if not tenant_db: return jsonify({})

    stok_id = request.args.get('stok_id')
    cari_id = request.args.get('cari_id')
    fiyat_listesi_id = request.args.get('fiyat_listesi_id', type=int)
    kur_degeri = float(request.args.get('kur', 1))
    
    if not stok_id: return jsonify({})

    cari = tenant_db.query(CariHesap).get(cari_id)
    stok = tenant_db.query(StokKart).get(stok_id)
    if not stok: return jsonify({})
    
    kdv_orani = 20.0
    if stok.kdv_grubu and stok.kdv_grubu.satis_kdv_orani is not None:
        kdv_orani = float(stok.kdv_grubu.satis_kdv_orani)

    ham_fiyat = float(stok.satis_fiyati or 0)
    nihai_fiyat = ham_fiyat
    iskonto_orani=0
    
    if fiyat_listesi_id and fiyat_listesi_id > 0:
        bugun = datetime.now().date()
        liste = tenant_db.query(FiyatListesi).filter_by(id=fiyat_listesi_id, aktif=True).first()
        
        if liste:
            baslangic_ok = not liste.baslangic_tarihi or liste.baslangic_tarihi <= bugun
            bitis_ok = not liste.bitis_tarihi or liste.bitis_tarihi >= bugun
            
            if baslangic_ok and bitis_ok:
                detay = tenant_db.query(FiyatListesiDetay).filter_by(
                    fiyat_listesi_id=liste.id, 
                    stok_id=stok.id
                ).first()
                if detay:
                    ham_fiyat = float(detay.fiyat or 0)
                    iskonto_orani = detay.iskonto_orani

    if kur_degeri > 0:
        nihai_fiyat = ham_fiyat / kur_degeri

    return jsonify({
        'cari_bakiye': float(cari.bakiye) if cari else 0,
        'stok_id': stok.id,
        'stok_adi': stok.ad,
        'stok_kodu': stok.kod,
        'birim': stok.birim or 'Adet',
        'fiyat': round(nihai_fiyat, 2), 
        'iskonto_orani': iskonto_orani,
        'kdv_orani': kdv_orani,
        'stok_bakiye': 0
    })

@siparis_bp.route('/api/get-cari-detay/<string:id>')
@login_required
def api_get_cari_detay(id):
    tenant_db = get_tenant_db()
    cari = tenant_db.query(CariHesap).get(id)
    if not cari: return jsonify({})
    
    return jsonify({
        'odeme_plani_id': cari.odeme_plani_id or 0,
        'risk_durumu': cari.risk_durumu,
        'bakiye': float(cari.bakiye)
    })

@siparis_bp.route('/iptal-et/<string:id>', methods=['POST'])
@login_required
def iptal_et(id):
    tenant_db = get_tenant_db()
    siparis = tenant_db.query(Siparis).get(id)
    neden = request.form.get('neden')
    
    siparis.durum = 'IPTAL'
    siparis.kayip_nedeni = neden
    tenant_db.commit()
    return jsonify({'success': True, 'message': 'Sipariş iptal edildi.'})

@siparis_bp.route('/api/get-kur/<doviz_kodu>')
@login_required
def api_get_kur(doviz_kodu):
    tenant_db = get_tenant_db()
    if doviz_kodu == 'TL': return jsonify({'kur': 1.0})
    
    kur = tenant_db.query(DovizKuru).filter_by(kod=doviz_kodu).order_by(DovizKuru.tarih.desc()).first()
    
    if kur:
        deger = float(kur.satis) if kur.satis > 0 else float(kur.efektif_satis)
        return jsonify({'kur': deger})
    else:
        return jsonify({'kur': 0.0, 'message': 'Kur bulunamadı'}), 404

@siparis_bp.route('/api/stok-ara')
@login_required
def api_stok_ara():
    tenant_db = get_tenant_db()
    search = request.args.get('term', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = tenant_db.query(StokKart).filter_by(aktif=True)
    
    if search:
        query = query.filter(
            or_(StokKart.kod.ilike(f'%{search}%'), StokKart.ad.ilike(f'%{search}%'))
        )
       
    # Pagination Firebird'de limit/offset ile
    total = query.count()
    stoklar = query.limit(per_page).offset((page - 1) * per_page).all()
    
    results = []
    for s in stoklar:
        results.append({
            'id': s.id,
            'text': f"{s.kod} - {s.ad} ({s.birim or 'Adet'})",
            'fiyat': float(s.satis_fiyati or 0),
            'kdv': float(s.kdv_grubu.satis_kdv_orani if s.kdv_grubu else 20)
        })
        
    return jsonify({
        'results': results,
        'pagination': {'more': (page * per_page) < total}
    })

@siparis_bp.route('/yazdir/<string:id>')
@login_required
def yazdir(id):
    tenant_db = get_tenant_db()
    siparis = tenant_db.query(Siparis).get(id)
    if not siparis: return redirect(url_for('siparis.index'))
    
    try:
        # DÜZELTME: Firma ID 1 yerine dinamik current_user.firma_id kullanıyoruz
        doc_gen = DocumentGenerator(current_user.firma_id) 
        html_content = doc_gen.render_html('siparis', siparis)
        return html_content
    except Exception as e:
        flash(f"Yazdırma hatası: {str(e)}", "danger")
        return redirect(url_for('siparis.index'))