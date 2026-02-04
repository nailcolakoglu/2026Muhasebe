# app/modules/fatura/routes.py

"""
Fatura Modülü HTTP Route Layer
Enterprise Grade - Thin Controller Pattern
"""

import sys
import os
from typing import Dict, Any, Tuple
from app.services.n8n_client import N8NClient

# Path Fix
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.modules.fatura.models import Fatura
from app.modules.stok.models import StokKart
from app.modules.cari.models import CariHesap
from app.form_builder import DataGrid
from .forms import create_fatura_form
from .services import FaturaService, FiyatHesaplamaService, FaturaDTO
from app.enums import FaturaTuru, FaturaDurumu
from app.utils.decorators import role_required, permission_required
from app.araclar import get_doviz_kuru, siradaki_kod_uret
import logging
from decimal import Decimal
from app.araclar import para_cevir


# Logger
logger = logging.getLogger(__name__)

# Blueprint
fatura_bp = Blueprint('fatura', __name__)


# ========================================
# LİSTELEME EKRANI (READ)
# ========================================
@fatura_bp.route('/')
@login_required
@permission_required('fatura_listele')
def index():
    """
    Fatura Listesi Ekranı
    
    Permissions: fatura_listele
    """
    
    grid = DataGrid("fatura_list", Fatura, _("Faturalar"))
    
    # Kolonlar
    grid.add_column('tarih', _('Tarih'), type='date')
    grid.add_column('belge_no', _('Belge No'))
    grid.add_column('cari.unvan', _('Cari Hesap'))
    grid.add_column('fatura_turu', _('Tür'), type='badge', badge_colors={
        'satis': 'success', 'alis': 'primary',
        'satis_iade': 'warning', 'alis_iade': 'info'
    })
    grid.add_column('genel_toplam', _('Tutar'), type='currency')
    grid.add_column('durum', _('Durum'), type='badge', badge_colors={
        'taslak': 'secondary', 'onaylandi': 'success', 'iptal':  'danger'
    })
    
    # Aksiyonlar
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'fatura.duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'fatura.sil')
    
    # Gizli Kolonlar
    hidden_cols = [
        'id', 'firma_id', 'donem_id', 'sube_id', 'depo_id', 'cari_id',
        'fatura_saati', 'gun_adi', 'sevk_adresi', 'aciklama',
        'ara_toplam', 'kdv_toplam', 'iskonto_toplam', 'doviz_turu',
        'doviz_kuru', 'fiyat_listesi_id', 'ettn', 'efatura_senaryo', 'gib'
    ]
    for col in hidden_cols:
        grid.hide_column(col)
    
    # Query (Eager Loading)
    query = Fatura.query.options(
        joinedload(Fatura.cari)
    ).filter_by(
        firma_id=current_user.firma_id
    ).order_by(Fatura.tarih.desc())
    
    grid.process_query(query)
    
    return render_template('fatura/index.html', grid=grid)


# ========================================
# YENİ KAYIT (CREATE)
# ========================================
@fatura_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@permission_required('fatura_ekle')
def ekle():
    """
    Yeni Fatura Oluşturma
    
    Permissions:  fatura_ekle
    """
    
    if request.method == 'POST':
        try:
            # Servise Delege Et
            basari, mesaj = FaturaService.save(request.form, user=current_user)
            
            if basari:
                logger.info(f"Fatura oluşturuldu: {mesaj} (Kullanıcı: {current_user.username})")
                return jsonify({
                    'success':  True,
                    'message':  mesaj,
                    'redirect':  url_for('fatura.index')
                })
            else:
                logger.warning(f"Fatura oluşturulamadı: {mesaj}")
                return jsonify({'success': False, 'message':  mesaj}), 400
                
        except Exception as e:
            logger.exception(f"Fatura oluşturma hatası: {e}")
            return jsonify({
                'success': False,
                'message': _("Beklenmeyen hata: ") + str(e)
            }), 500
    
    # GET:  Form Render
    form = create_fatura_form()
    return render_template('fatura/form.html', form=form)


# ========================================
# DÜZENLEME (UPDATE)
# ========================================
@fatura_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('fatura_ekle')
def duzenle(id):
    """
    Mevcut Fatura Düzenleme
    
    Permissions: fatura_duzenle
    Args:
        id:  Fatura ID
    """
    
    # Güvenli Veri Çekme (Eager Loading)
    fatura = FaturaService.get_by_id(id, current_user.firma_id)
    
    if not fatura:
        flash(_("Fatura bulunamadı veya erişim yetkiniz yok."), "error")
        return redirect(url_for('fatura.index'))
    """
    # 🔍 DEBUG:  Fatura kalemlerini görüntüle
    print("\n" + "="*80)
    print(f"DEBUG - Fatura ID: {fatura.id} | Belge No: {fatura.belge_no}")
    print("="*80)
    
    if fatura.kalemler:
        print(f"📋 Toplam Kalem Sayısı: {len(fatura.kalemler)}\n")
        
        for idx, kalem in enumerate(fatura.kalemler, 1):
            print(f"Kalem #{idx}")
            print(f"  - ID: {kalem.id}")
            print(f"  - Stok ID: {kalem.stok_id}")
            print(f"  - Stok Adı: {kalem.stok.ad if kalem.stok else 'N/A'}")
            print(f"  - Stok Kodu: {kalem.stok.kod if kalem.stok else 'N/A'}")
            print(f"  - Miktar: {kalem.miktar}")
            print(f"  - Birim:  {kalem.birim}")
            print(f"  - Birim Fiyat: {kalem.birim_fiyat}")
            print(f"  - İskonto Oranı: {kalem.iskonto_orani}%")
            print(f"  - KDV Oranı: {kalem.kdv_orani}%")
            print(f"  - Net Tutar: {kalem.net_tutar}")
            print(f"  - Satır Toplam: {kalem.satir_toplami}")
            print()
    else:
        print("⚠️  Kalem bulunamadı!")
    
    print("="*80 + "\n")
    """
    if request.method == 'POST': 
        try:
            basari, mesaj = FaturaService.save(request.form, fatura=fatura, user=current_user)
            
            if basari:
                user_name = f"{current_user.ad} {current_user.soyad}" if hasattr(current_user, 'ad') else current_user.email
                logger.info(f"Fatura güncellendi: {fatura.belge_no} (Kullanıcı:  {user_name})")
                return jsonify({
                    'success':  True,
                    'message':  mesaj,
                    'redirect': url_for('fatura.index')
                })
            else:
                return jsonify({'success': False, 'message': mesaj}), 400
                
        except Exception as e:
            logger.exception(f"Fatura güncelleme hatası (ID: {id}): {e}")
            return jsonify({
                'success': False,
                'message': _("Güncelleme başarısız: ") + str(e)
            }), 500
    
    # GET:  Form Render
    form = create_fatura_form(fatura)
    return render_template('fatura/form.html', form=form)



# ========================================
# SİLME (DELETE)
# ========================================
@fatura_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
@permission_required('fatura_sil')
def sil(id: int):
    """
    Fatura Silme
    
    Permissions:  fatura_sil
    Args:
        id: Fatura ID
    """
    
    try:
        basari, mesaj = FaturaService.sil(id, current_user)
        
        if basari: 
            logger.info(f"Fatura silindi: ID {id} (Kullanıcı: {current_user.username})")
            return jsonify({'success': True, 'message':  mesaj})
        else:
            return jsonify({'success': False, 'message': mesaj}), 400
            
    except Exception as e:
        logger.exception(f"Fatura silme hatası (ID: {id}): {e}")
        return jsonify({
            'success': False,
            'message': _("Silme işlemi başarısız: ") + str(e)
        }), 500


# ========================================
# API:  STOK ARAMA (AJAX SELECT2)
# ========================================
@fatura_bp.route('/api/stok-ara')
@login_required
def api_stok_ara():
    """
    Stok kartları için AJAX arama endpoint'i.
    
    Query Params:
        term: Arama kelimesi
        page: Sayfa numarası (default: 1)
        
    Returns:
        JSON:  Select2 formatında sonuçlar
    """
    
    term = request.args.get('term', '').strip()
    page = request.args.get('page', 1, type=int)
    limit = 20
    
    try:
        # Base Query
        query = StokKart.query.filter_by(
            firma_id=current_user.firma_id,
            aktif=True
        )
        
        # Arama Filtresi (Kod veya Ad)
        if term:
            search_pattern = f'%{term}%'
            query = query.filter(
                db.or_(
                    StokKart.kod.ilike(search_pattern),
                    StokKart.ad.ilike(search_pattern)
                )
            )
        
        # Pagination
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        
        # Select2 Format
        results = [
            {'id': s.id, 'text': f"{s.kod} - {s.ad}"}
            for s in pagination.items
        ]
        
        return jsonify({
            'results': results,
            'pagination':  {'more': pagination.has_next}
        })
        
    except Exception as e:
        logger.error(f"Stok arama hatası: {e}")
        return jsonify({'results': [], 'pagination': {'more': False}})


# ========================================
# API: SIRADAKİ BELGE NUMARASI
# ========================================
@fatura_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    """
    Fatura için sıradaki belge numarasını üretir.
    
    Returns:
        JSON: {'code': 'FAT-00001'}
    """
    
    try:
        yeni_kod = siradaki_kod_uret(Fatura, 'FAT-', hane_sayisi=5)
        return jsonify({'code': yeni_kod})
        
    except Exception as e:
        logger.error(f"Belge no üretme hatası: {e}")
        return jsonify({'code': 'FAT-00001'})  # Fallback


# ========================================
# API: FİYAT HESAPLAMA (ÇAPRAZ KUR + MİN MİKTAR)
# ========================================
@fatura_bp.route('/api/get-fiyat', methods=['POST'])
@login_required
def api_get_fiyat():
    """
    Stok fiyatını hesaplar (Çapraz Kur + Fiyat Listesi + Min Miktar Baremli).
    
    Request JSON:
        {
            'stok_id': int,
            'fatura_turu': str,
            'doviz_turu': str,
            'doviz_kuru': float,
            'liste_id': int (optional),
            'toplam_miktar': float (optional) <- YENİ:  Baremli fiyatlandırma için
        }
        
    Returns:
        JSON:  {
            'success': bool,
            'fiyat':  Decimal,
            'iskonto_orani': Decimal,
            'kdv_orani': int,
            'birim': str,
            'debug': dict
        }
    """
    
    try:
        data = request.get_json()
        stok_id = data.get('stok_id')
        liste_id = data.get('liste_id', 0)
        fatura_turu = data.get('fatura_turu', 'satis')
        fatura_para_birimi = data.get('doviz_turu')

        # ✅ DÜZELTME:  Kuru Decimal Olarak Al
        # ------------------------------------
        try:
            fatura_kur_raw = data.get('doviz_kuru', 1)
            # para_cevir zaten Decimal döndürür, ama direkt float gelmişse dönüştür
            if isinstance(fatura_kur_raw, (int, float)):
                fatura_kur = Decimal(str(fatura_kur_raw))
            else:
                # String geldiyse (1.250,50 formatında olabilir)
                fatura_kur = para_cevir(fatura_kur_raw)
        except Exception as e:
            logger.error(f"Kur dönüşüm hatası:  {e}")
            fatura_kur = Decimal('1.0')
        
        # Güvenlik Kontrolü
        if fatura_kur <= 0:
            fatura_kur = Decimal('1.0')

        if not stok_id:
            return jsonify({'success': False, 'message': 'Stok ID eksik'}), 400
        
        # Servisi Çağır (Artık Decimal gidiyor)
        result = FiyatHesaplamaService.hesapla(
            stok_id=int(stok_id),
            fatura_turu=fatura_turu,
            fatura_para_birimi=fatura_para_birimi,
            fatura_kuru=fatura_kur,  # <-- Artık Decimal
            liste_id=int(liste_id) if liste_id else None,
            firma_id=current_user.firma_id
        )
        
        # JSON için Float'a Çevir (Serialization)
        return jsonify({
            'success':  True,
            'fiyat': float(result['fiyat']),
            'iskonto_orani': float(result['iskonto_orani']),
            'kdv_orani': result['kdv_orani'],
            'birim':  result['birim'],
            'debug': result.get('debug')
        })
        
    except Exception as e:
        logger.error(f"Fiyat Getirme Hatası: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500




# ========================================
# API: DÖVİZ KURU GETİRME
# ========================================
@fatura_bp.route('/api/get-kur/<doviz_kodu>')
@login_required
def api_get_kur(doviz_kodu:  str):
    """
    Belirtilen döviz kodunun sistemdeki güncel kurunu getirir.
    
    Args:
        doviz_kodu: USD, EUR, GBP vs.
        
    Returns:
        JSON: {'kur': 42.50}
    """
    
    try:
        if not doviz_kodu or doviz_kodu.upper() == 'TL':
            return jsonify({'kur': 1.0})
        
        kur = get_doviz_kuru(doviz_kodu.upper())
        
        if kur == 0:
            logger.warning(f"Kur bulunamadı: {doviz_kodu}")
            return jsonify({'kur': 1.0, 'warning': _('Kur bulunamadı, 1.0 olarak ayarlandı')})
        
        return jsonify({'kur': kur})
        
    except Exception as e: 
        logger.error(f"Kur getirme hatası ({doviz_kodu}): {e}")
        return jsonify({'kur': 1.0, 'error': str(e)})


# ========================================
# API: CARİ DETAY GETİRME (BALANCE & INFO)
# ========================================
@fatura_bp.route('/api/get-cari-detay/<int:cari_id>')
@login_required
def api_get_cari_detay(cari_id: int):
    """
    Cari hesap detaylarını getirir (Bakiye, Risk Skoru, vs.).
    
    Args:
        cari_id: Cari Hesap ID
        
    Returns:
        JSON: {
            'success': bool,
            'bakiye': Decimal,
            'risk_skoru': int,
            'risk_durumu': str,
            'limit_durumu': str
        }
    """
    
    try:
        cari = db.session.execute(
            db.select(CariHesap)
            .where(CariHesap.id == cari_id)
            .where(CariHesap.firma_id == current_user.firma_id)
        ).scalar_one_or_none()
        
        if not cari: 
            return jsonify({'success': False, 'message': _('Cari bulunamadı')}), 404
        
        # Bakiye Hesaplama (Eğer yoksa cari_hareket tablosundan hesaplanabilir)
        bakiye = float(getattr(cari, 'bakiye', 0) or 0)
        risk_skoru = getattr(cari, 'risk_skoru', 0) or 0
        
        # Risk Durumu
        if risk_skoru > 70:
            risk_durumu = 'yuksek'
            risk_mesaj = _('Yüksek Riskli Müşteri')
        elif risk_skoru > 40:
            risk_durumu = 'orta'
            risk_mesaj = _('Orta Riskli Müşteri')
        else:
            risk_durumu = 'dusuk'
            risk_mesaj = _('Düşük Riskli Müşteri')
        
        # Limit Kontrolü
        limit = float(getattr(cari, 'risk_limiti', 0) or 0)
        if limit > 0 and bakiye > limit:
            limit_durumu = 'asim'
            limit_mesaj = _('Limit Aşıldı!')
        else:
            limit_durumu = 'normal'
            limit_mesaj = _('Limit Dahilinde')
        
        return jsonify({
            'success': True,
            'bakiye': bakiye,
            'risk_skoru': risk_skoru,
            'risk_durumu': risk_durumu,
            'risk_mesaj': risk_mesaj,
            'limit_durumu': limit_durumu,
            'limit_mesaj': limit_mesaj,
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Cari detay getirme hatası (ID: {cari_id}): {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========================================
# API: E-FATURA GÖNDER
# ========================================
@fatura_bp.route('/api/efatura-gonder/<int:id>', methods=['POST'])
@login_required
@permission_required('efatura_gonder')
def api_efatura_gonder(id: int):
    """
    Faturayı GİB'e e-fatura olarak gönderir.
    
    Permissions: efatura_gonder
    Args:
        id: Fatura ID
        
    Returns:
        JSON:  {'success': bool, 'message': str}
    """
    
    try:
        # Lazy Import (Circular Import'u Önler)
        from modules.efatura.services import EntegratorService
        
        service = EntegratorService(current_user.firma_id)
        basari, mesaj = service.fatura_gonder(id)
        
        if basari: 
            logger.info(f"E-Fatura gönderildi:  Fatura ID {id} (Kullanıcı: {current_user.username})")
            return jsonify({'success': True, 'message':  mesaj})
        else:
            logger.warning(f"E-Fatura gönderilemedi: {mesaj}")
            return jsonify({'success': False, 'message':  mesaj}), 400
            
    except ImportError:
        logger.error("E-Fatura modülü yüklenemedi")
        return jsonify({
            'success': False,
            'message': _("E-Fatura modülü bulunamadı")
        }), 500
        
    except Exception as e: 
        logger.exception(f"E-Fatura gönderme hatası (Fatura:  {id}): {e}")
        return jsonify({
            'success': False,
            'message': _("E-Fatura gönderilemedi: ") + str(e)
        }), 500


# ========================================
# API: E-FATURA DURUM SORGULA
# ========================================
@fatura_bp.route('/api/efatura-durum/<int:id>', methods=['GET'])
@login_required
def api_efatura_durum(id: int):
    """
    E-Fatura durumunu GİB'den sorgular.
    
    Args:
        id: Fatura ID
        
    Returns: 
        JSON: {
            'success': bool,
            'durum_kodu': int,
            'durum_aciklama': str,
            'ettn':  str
        }
    """
    
    try:
        from modules.efatura.services import EntegratorService
        
        service = EntegratorService(current_user.firma_id)
        sonuc = service.fatura_durum_sorgula(id)
        
        return jsonify(sonuc)
        
    except ImportError:
        return jsonify({
            'success':  False,
            'message': _("E-Fatura modülü bulunamadı")
        }), 500
        
    except Exception as e:
        logger.exception(f"E-Fatura durum sorgulama hatası (Fatura: {id}): {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500