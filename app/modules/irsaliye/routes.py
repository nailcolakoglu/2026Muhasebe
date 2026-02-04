# app/modules/irsaliye/routes.py

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime

# Modeller ve Araçlar
from app.extensions import db
from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi
from app.modules.stok.models import StokKart
from app.modules.cari.models import CariHesap
from app.modules.depo.models import Depo
from app.form_builder import DataGrid
from .forms import create_irsaliye_form
from .services import IrsaliyeService
from app.enums import IrsaliyeDurumu
from app.araclar import siradaki_kod_uret

# AI Modülü (Yapay Zeka Desteği)
try:
    from modules.ai_destek.engine import AIAssistant
except ImportError:
    AIAssistant = None # AI modülü henüz yoksa hata vermesin

irsaliye_bp = Blueprint('irsaliye', __name__)

# --- LİSTELEME EKRANI ---
@irsaliye_bp.route('/')
@login_required
def index():
    """
    İrsaliye Listesi (DataGrid)
    """
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

    # Gizlenecek Sütunlar (Gereksiz kalabalığı önle)
    grid.hide_column('id').hide_column('firma_id').hide_column('donem_id').hide_column('depo_id')
    grid.hide_column('cari_id').hide_column('aciklama').hide_column('fatura_id').hide_column('faturalasti_mi')
    grid.hide_column('ettn').hide_column('gib_durum_kodu').hide_column('sofor_soyad').hide_column('sofor_tc')
    grid.hide_column('plaka_dorse').hide_column('tasiyici_firma_vkn').hide_column('tasiyici_firma_unvan')
    grid.hide_column('irsaliye_turu')

    # Filtreleme: Sadece kendi firması
    query = Irsaliye.query.filter_by(firma_id=current_user.firma_id).order_by(Irsaliye.tarih.desc())
    grid.process_query(query)
    
    return render_template('irsaliye/index.html', grid=grid)

# --- YENİ KAYIT ---
@irsaliye_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_irsaliye_form()
    
    if request.method == 'POST':
        try:
            # Service katmanına gönder
            success, msg = IrsaliyeService.kaydet(request.form, user=current_user)
            if success:
                return jsonify({'success': True, 'message': msg, 'redirect': url_for('irsaliye.index')})
            else:
                return jsonify({'success': False, 'message': msg}), 400
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
            
    return render_template('irsaliye/form.html', form=form)

# --- DÜZENLEME ---
@irsaliye_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    irsaliye = Irsaliye.query.get_or_404(id)
    if irsaliye.firma_id != current_user.firma_id:
        return "Yetkisiz Erişim", 403
        
    form = create_irsaliye_form(irsaliye)
    
    if request.method == 'POST':
        try:
            success, msg = IrsaliyeService.kaydet(request.form, irsaliye=irsaliye, user=current_user)
            if success:
                return jsonify({'success': True, 'message': msg, 'redirect': url_for('irsaliye.index')})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
            
    return render_template('irsaliye/form.html', form=form)

# --- SİLME ---
@irsaliye_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    irsaliye = Irsaliye.query.get_or_404(id)
    
    # E-İrsaliye kontrolü: Gönderilmiş irsaliye silinemez
    if irsaliye.gib_durum_kodu == 100 or irsaliye.gib_durum_kodu == 1300:
        return jsonify({'success': False, 'message': 'GİB\'e gönderilmiş irsaliye silinemez! İptal etmeyi deneyin.'}), 400

    try:
        # Stok hareketlerini temizle
        from models import StokHareketi
        StokHareketi.query.filter_by(kaynak_turu='irsaliye', kaynak_id=irsaliye.id).delete()
        
        db.session.delete(irsaliye)
        db.session.commit()
        return jsonify({'success': True, 'message': 'İrsaliye silindi.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# =================================================================
# 🤖 YENİ: YAPAY ZEKA DESTEK API'Sİ
# =================================================================
@irsaliye_bp.route('/api/ai-analiz', methods=['POST'])
@login_required
def api_ai_analiz():
    """
    Formdaki verileri alıp AI motoruna gönderir ve lojistik tavsiyeler döndürür.
    """
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
        return jsonify({'success': False, 'message': str(e)}), 500

# =================================================================
# YARDIMCI API'LER (Select2 ve Otomasyon)
# =================================================================

@irsaliye_bp.route('/api/stok-ara')
@login_required
def api_stok_ara():
    """Formdaki Stok Seçimi İçin"""
    term = request.args.get('term', '')
    page = request.args.get('page', 1, type=int)
    limit = 20
    
    query = StokKart.query.filter_by(firma_id=current_user.firma_id, aktif=True)
    if term:
        query = query.filter(or_(StokKart.kod.ilike(f'%{term}%'), StokKart.ad.ilike(f'%{term}%')))
        
    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    results = [{'id': s.id, 'text': f"{s.kod} - {s.ad}"} for s in pagination.items]
    
    return jsonify({
        'results': results,
        'pagination': {'more': pagination.has_next}
    })

@irsaliye_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    """Otomatik Belge Numarası"""
    yeni_kod = siradaki_kod_uret(Irsaliye, 'IRS-')
    return jsonify({'code': yeni_kod})