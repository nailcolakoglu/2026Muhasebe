# app/modules/irsaliye/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime
import logging

# Modeller ve Araçlar
from app.extensions import get_tenant_db # ✨ EKLENDİ: Tenant DB bağlantısı
from app.decorators import tenant_route, permission_required # ✨ EKLENDİ: Güvenlik dekoratörleri
from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi
from app.modules.stok.models import StokKart, StokHareketi
from app.modules.cari.models import CariHesap
from app.modules.depo.models import Depo
from app.form_builder import DataGrid
from .forms import create_irsaliye_form
from .services import IrsaliyeService
from app.enums import IrsaliyeDurumu
from app.araclar import siradaki_kod_uret

logger = logging.getLogger(__name__)

# AI Modülü (Yapay Zeka Desteği)
try:
    from app.modules.ai_destek.engine import AIAssistant
except ImportError:
    AIAssistant = None # AI modülü henüz yoksa hata vermesin
    logger.warning("AI Modülü yüklenemedi!")
    
irsaliye_bp = Blueprint('irsaliye', __name__)

# --- LİSTELEME EKRANI ---
@irsaliye_bp.route('/')
@login_required
@tenant_route # ✨ EKLENDİ
def index():
    """İrsaliye Listesi (DataGrid)"""
    tenant_db = get_tenant_db() # ✨ EKLENDİ
    
    grid = DataGrid("irsaliye_list", Irsaliye, "İrsaliyeler")
    
    # Sütunlar
    grid.add_column('tarih', 'Sevk Tarihi', type='date')
    grid.add_column('saat', 'Saat', type='time')
    grid.add_column('belge_no', 'Belge No')
    grid.add_column('cari.unvan', 'Alıcı Firma')
    grid.add_column('plaka_arac', 'Plaka', type='badge', badge_colors={'default': 'warning'})
    grid.add_column('sofor_ad', 'Şoför')
    grid.add_column('durum', 'Durum', type='badge', badge_colors={
        'taslak': 'secondary', 'onaylandi': 'success', 'iptal': 'danger'
    })

    # Aksiyonlar
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'irsaliye.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'irsaliye.sil')

    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'created_at', 'updated_at', 'deleted_at',
        'donem_id', 'sube_id','depo_id'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    # Gizlenecek Sütunlar
    grid.hide_column('id').hide_column('firma_id').hide_column('donem_id').hide_column('depo_id')
    grid.hide_column('cari_id').hide_column('aciklama').hide_column('fatura_id').hide_column('faturalasti_mi')
    grid.hide_column('ettn').hide_column('gib_durum_kodu').hide_column('sofor_soyad').hide_column('sofor_tc')
    grid.hide_column('plaka_dorse').hide_column('tasiyici_firma_vkn').hide_column('tasiyici_firma_unvan')
    grid.hide_column('irsaliye_turu')

    # ✨ DÜZELTİLDİ: Global query yerine tenant_db.query kullanıldı
    query = tenant_db.query(Irsaliye).filter_by(firma_id=current_user.firma_id).order_by(Irsaliye.tarih.desc())
    grid.process_query(query)
    
    return render_template('irsaliye/index.html', grid=grid)

# --- YENİ KAYIT ---
@irsaliye_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@tenant_route # ✨ EKLENDİ
def ekle():
    form = create_irsaliye_form()
    
    if request.method == 'POST':
        try:
            success, msg = IrsaliyeService.kaydet(request.form, user=current_user)
            if success:
                return jsonify({'success': True, 'message': msg, 'redirect': url_for('irsaliye.index')})
            return jsonify({'success': False, 'message': msg}), 400
        except Exception as e:
            logger.error(f"İrsaliye Ekleme Hatası: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
            
    return render_template('irsaliye/form.html', form=form)

# --- DÜZENLEME ---
@irsaliye_bp.route('/duzenle/<string:id>', methods=['GET', 'POST']) # ✨ DÜZELTİLDİ: int yerine string UUID
@login_required
@tenant_route # ✨ EKLENDİ
def duzenle(id):
    tenant_db = get_tenant_db()
    irsaliye = tenant_db.get(Irsaliye, str(id)) # ✨ DÜZELTİLDİ
    
    if not irsaliye or irsaliye.firma_id != current_user.firma_id:
        return "Yetkisiz Erişim", 403
        
    form = create_irsaliye_form(irsaliye)
    
    if request.method == 'POST':
        try:
            success, msg = IrsaliyeService.kaydet(request.form, irsaliye=irsaliye, user=current_user)
            if success:
                return jsonify({'success': True, 'message': msg, 'redirect': url_for('irsaliye.index')})
            return jsonify({'success': False, 'message': msg}), 400
        except Exception as e:
            logger.error(f"İrsaliye Düzenleme Hatası: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
            
    return render_template('irsaliye/form.html', form=form, irsaliye=irsaliye)

# --- SİLME ---
@irsaliye_bp.route('/sil/<string:id>', methods=['POST']) # ✨ DÜZELTİLDİ: int yerine string
@login_required
@tenant_route # ✨ EKLENDİ
def sil(id):
    tenant_db = get_tenant_db()
    irsaliye = tenant_db.get(Irsaliye, str(id))
    
    if not irsaliye:
        return jsonify({'success': False, 'message': 'İrsaliye bulunamadı.'}), 404
    
    # E-İrsaliye kontrolü: Gönderilmiş irsaliye silinemez
    if irsaliye.gib_durum_kodu in [100, 1300]:
        return jsonify({'success': False, 'message': 'GİB\'e gönderilmiş irsaliye silinemez! İptal etmeyi deneyin.'}), 400

    try:
        # ✨ DÜZELTİLDİ: Global silme yerine tenant_db üzerinden silindi
        tenant_db.query(StokHareketi).filter_by(kaynak_turu='irsaliye', kaynak_id=irsaliye.id).delete()
        tenant_db.delete(irsaliye)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'İrsaliye silindi.'})
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"İrsaliye Silme Hatası: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@irsaliye_bp.route('/faturaya-cevir/<string:id>', methods=['POST'])
@login_required
@tenant_route
def faturaya_cevir(id):
    try:
        basari, mesaj, fatura_id = IrsaliyeService.faturaya_donustur(id, current_user)
        if basari:
            # Dönüşüm başarılıysa kullanıcıyı direkt olarak yeni faturanın içine ışınlıyoruz!
            return jsonify({
                'success': True, 
                'message': mesaj, 
                'redirect_url': url_for('fatura.duzenle', id=fatura_id)
            })
        return jsonify({'success': False, 'message': mesaj}), 400
    except Exception as e:
        logger.error(f"Faturaya Çevirme Hatası: {str(e)}")
        return jsonify({'success': False, 'message': "Sunucu hatası oluştu"}), 500

# =================================================================
# YARDIMCI API'LER (Select2 ve Otomasyon)
# =================================================================

@irsaliye_bp.route('/api/stok-ara')
@login_required
@tenant_route
def api_stok_ara():
    tenant_db = get_tenant_db()
    term = request.args.get('term', '')
    page = request.args.get('page', 1, type=int)
    limit = 20
    offset = (page - 1) * limit
    
    try:
        query = tenant_db.query(StokKart).filter_by(firma_id=current_user.firma_id, aktif=True)
        
        if term:
            query = query.filter(or_(StokKart.kod.ilike(f'%{term}%'), StokKart.ad.ilike(f'%{term}%')))
            
        # .paginate() yerine saf ve hatasız SQLAlchemy limit/offset kullanıyoruz
        items = query.limit(limit).offset(offset).all()
        total_count = query.count()
        
        results = [{'id': str(s.id), 'text': f"{s.kod} - {s.ad}"} for s in items]
        
        return jsonify({
            'results': results,
            'pagination': {'more': (offset + limit) < total_count}
        })
    except Exception as e:
        logger.error(f"İrsaliye Stok Arama AJAX Hatası: {str(e)}")
        # Hata durumunda boş liste dön ki UI tarafı (Select2) kırmızı hata vermesin
        return jsonify({'results': [], 'pagination': {'more': False}})

@irsaliye_bp.route('/api/siradaki-no')
@login_required
@tenant_route
def api_siradaki_no():
    # Burada araclar içindeki siradaki_kod_uret fonksiyonunun da tenant_db kullandığından emin olmalısın.
    yeni_kod = siradaki_kod_uret(Irsaliye, 'IRS-')
    return jsonify({'code': yeni_kod})
    
# =================================================================
# 🤖 YENİ: YAPAY ZEKA DESTEK API'Sİ
# =================================================================
@irsaliye_bp.route('/api/ai-analiz', methods=['POST'])
@login_required
@tenant_route # ✨ EKLENDİ: Multi-tenant izolasyonu (DB erişimi için şart)
def api_ai_analiz():
    if not AIAssistant:
        return jsonify({'success': False, 'message': 'AI Modülü yüklü değil.'}), 501

    try:
        data = request.get_json()
        # AI Motorunu Çalıştır
        analiz_sonucu = AIAssistant.sevkiyat_analizi(data)
        
        return jsonify({
            'success': True,
            'analiz': analiz_sonucu
        })
    except Exception as e:
        logger.error(f"AI Analiz Hatası: {str(e)}")
        return jsonify({'success': False, 'message': "Analiz sırasında bir hata oluştu."}), 500

@irsaliye_bp.route('/api/cari-ara')
@login_required
@tenant_route
def api_cari_ara():
    tenant_db = get_tenant_db()
    term = request.args.get('term', '')
    page = request.args.get('page', 1, type=int)
    limit = 20
    offset = (page - 1) * limit
    
    try:
        query = tenant_db.query(CariHesap).filter_by(firma_id=current_user.firma_id, aktif=True)
        if term:
            query = query.filter(or_(CariHesap.kod.ilike(f'%{term}%'), CariHesap.unvan.ilike(f'%{term}%')))
            
        items = query.limit(limit).offset(offset).all()
        total_count = query.count()
        
        results = [{'id': str(c.id), 'text': f"{c.kod or ''} {c.unvan}".strip()} for c in items]
        return jsonify({'results': results, 'pagination': {'more': (offset + limit) < total_count}})
    except Exception as e:
        return jsonify({'results': [], 'pagination': {'more': False}})
        
@irsaliye_bp.route('/yazdir/<string:id>')
@login_required
@tenant_route
def yazdir(id):
    tenant_db = get_tenant_db()
    irsaliye = tenant_db.get(Irsaliye, str(id))
    
    if not irsaliye or irsaliye.firma_id != current_user.firma_id:
        return "Yetkisiz Erişim", 403

    # Burada şık bir yazdırma şablonu (HTML) döndürüyoruz
    return render_template('irsaliye/yazdir.html', irsaliye=irsaliye)