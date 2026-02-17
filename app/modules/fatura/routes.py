# app/modules/fatura/routes.py (MySQL Optimized + Complete)

"""
Fatura Modülü HTTP Route Layer
Enterprise Grade - Thin Controller Pattern - MySQL Optimized
"""

import sys
import os
from typing import Dict, Any, Tuple
from decimal import Decimal

# Path Fix
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_babel import gettext as _
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, and_, or_, text

from app.extensions import db, get_tenant_db, cache
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.stok.models import StokKart
from app.modules.cari.models import CariHesap
from app.form_builder import DataGrid
from .forms import create_fatura_form
from .services import FaturaService, FiyatHesaplamaService, FaturaDTO
from .listeners import fatura_onayla_handler, fatura_iptal_et_handler
from app.enums import FaturaTuru, FaturaDurumu, ParaBirimi
from app.decorators import role_required, permission_required, audit_log
from app.araclar import get_doviz_kuru, siradaki_kod_uret, para_cevir
from flask_babel import gettext as _, lazy_gettext

# Cache timeout
CACHE_TIMEOUT_SHORT = 300

import logging

# Logger
logger = logging.getLogger(__name__)

# Blueprint
fatura_bp = Blueprint('fatura', __name__)


# ========================================
# YARDIMCI FONKSİYONLAR
# ========================================
def parse_uuid(id_str):
    """UUID string'i validate et"""
    import uuid
    try:
        return str(uuid.UUID(str(id_str)))
    except (ValueError, AttributeError):
        return None


# ========================================
# LİSTELEME EKRANI (READ) - MySQL Optimized
# ========================================
@fatura_bp.route('/')
@login_required
@permission_required('fatura_listele')
def index():
    """
    Fatura Listesi Ekranı - MySQL Optimized
    
    Özellikler:
    - Eager loading (N+1 önleme)
    - Index-friendly query
    - Pagination
    
    Permissions: fatura_listele
    """
    """Fatura Listesi Ekranı - i18n Ready"""
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Veritabanı bağlantısı yok. Lütfen firma seçin.', 'danger')
        return redirect(url_for('main.index'))
    
    grid = DataGrid("fatura_list", Fatura, _("Faturalar"))
    
    # Kolonlar
    grid.add_column('tarih', _('Tarih'), type='date', width='100px')
    grid.add_column('belge_no', _('Belge No'), width='120px')
    grid.add_column('cari.unvan', _('Cari Hesap'), sortable=True)
    grid.add_column('fatura_turu', _('Tür'), type='badge', width='100px', badge_colors={
        'SATIS': 'success',
        'ALIS': 'primary',
        'SATIS_IADE': 'warning',
        'ALIS_IADE': 'info'
    })
    grid.add_column('genel_toplam', _('Tutar'), type='currency', width='150px')
    grid.add_column('doviz_turu', _('Döviz'), width='80px')
    grid.add_column('durum', _('Durum'), type='badge', width='100px', badge_colors={
        'TASLAK': 'secondary',
        'ONAYLANDI': 'success',
        'IPTAL': 'danger'
    })
    
    # Aksiyonlar
    grid.add_action('view', _('Görüntüle'), 'bi bi-eye', 'btn-info btn-sm', 'route', 'fatura.goruntule')
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'fatura.duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'fatura.sil')
    
    # ✅ MySQL Optimized Query (Index: idx_fatura_firma_tarih)
    query = tenant_db.query(Fatura).options(
        # Joined load (tek sorgu)
        joinedload(Fatura.cari),
        joinedload(Fatura.depo)
    ).filter(
        Fatura.firma_id == current_user.firma_id,
        Fatura.deleted_at.is_(None)  # Soft delete
    ).order_by(Fatura.tarih.desc())
    
    # Filtreleme (query string'den)
    durum_filtre = request.args.get('durum')
    if durum_filtre:
        query = query.filter(Fatura.durum == durum_filtre)
    
    tur_filtre = request.args.get('tur')
    if tur_filtre:
        query = query.filter(Fatura.fatura_turu == tur_filtre)
    
    grid.process_query(query)
    
    return render_template('fatura/index.html', grid=grid)


# ========================================
# YENİ KAYIT (CREATE) - MySQL Optimized
# ========================================
@fatura_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@permission_required('fatura_ekle')
@audit_log('fatura', 'ekle')
def ekle():
    """
    Yeni Fatura Oluşturma
    
    Permissions: fatura_ekle
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Veritabanı bağlantısı yok', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Servise delege et
            basari, mesaj = FaturaService.save(
                request.form,
                user=current_user,
                tenant_db=tenant_db
            )
            
            if basari:
                logger.info(
                    f"✅ Fatura oluşturuldu: {mesaj} "
                    f"(Kullanıcı: {current_user.email})"
                )
                
                return jsonify({
                    'success': True,
                    'message': mesaj,
                    'redirect': url_for('fatura.index')
                })
            else:
                logger.warning(f"⚠️ Fatura oluşturulamadı: {mesaj}")
                return jsonify({
                    'success': False,
                    'message': mesaj
                }), 400
        
        except Exception as e:
            logger.exception(f"❌ Fatura oluşturma hatası: {e}")
            return jsonify({
                'success': False,
                'message': _("Beklenmeyen hata: ") + str(e)
            }), 500
    
    # GET: Form Render
    form = create_fatura_form()
    return render_template('fatura/form.html', form=form)


# ========================================
# DÜZENLEME (UPDATE) - MySQL Optimized
# ========================================
@fatura_bp.route('/duzenle/<uuid:id>', methods=['GET', 'POST'])
@login_required
@permission_required('fatura_duzenle')
@audit_log('fatura', 'update')
def duzenle(id):
    """
    Mevcut Fatura Düzenleme - MySQL Optimized
    
    Permissions: fatura_duzenle
    Args:
        id: Fatura ID (UUID)
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Veritabanı bağlantısı yok', 'danger')
        return redirect(url_for('main.index'))
    
    # ✅ MySQL Native UUID Query (CAST gerekmez)
    fatura = FaturaService.get_by_id(
        str(id),
        current_user.firma_id,
        tenant_db
    )
    
    if not fatura:
        flash(_("Fatura bulunamadı veya erişim yetkiniz yok."), "error")
        return redirect(url_for('fatura.index'))
    
    # Onaylı fatura kontrolü
    if fatura.durum == 'ONAYLANDI' and not current_user.has_permission('fatura_onaylandi_duzenle'):
        flash(_("Onaylı fatura düzenlenemez"), "error")
        return redirect(url_for('fatura.index'))
    
    if request.method == 'POST':
        try:
            basari, mesaj = FaturaService.save(
                request.form,
                fatura=fatura,
                user=current_user,
                tenant_db=tenant_db
            )
            
            if basari:
                logger.info(
                    f"✅ Fatura güncellendi: {fatura.belge_no} "
                    f"(Kullanıcı: {current_user.email})"
                )
                
                return jsonify({
                    'success': True,
                    'message': mesaj,
                    'redirect': url_for('fatura.index')
                })
            else:
                return jsonify({
                    'success': False,
                    'message': mesaj
                }), 400
        
        except Exception as e:
            logger.exception(f"❌ Fatura güncelleme hatası (ID: {id}): {e}")
            return jsonify({
                'success': False,
                'message': _("Güncelleme başarısız: ") + str(e)
            }), 500
    
    # GET: Form Render
    form = create_fatura_form(fatura)
    return render_template('fatura/form.html', form=form, title=form.title)


# ========================================
# SİLME (DELETE) - MySQL Optimized
# ========================================
@fatura_bp.route('/sil/<uuid:id>', methods=['POST'])
@login_required
@permission_required('fatura_sil')
@audit_log('fatura', 'delete')
def sil(id):
    """
    Fatura Silme - Soft Delete
    
    Permissions: fatura_sil
    Args:
        id: Fatura ID (UUID)
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': 'Veritabanı bağlantısı yok'
        }), 500
    
    try:
        basari, mesaj = FaturaService.sil(
            str(id),
            current_user,
            tenant_db
        )
        
        if basari:
            logger.info(
                f"✅ Fatura silindi: ID {id} "
                f"(Kullanıcı: {current_user.email})"
            )
            return jsonify({
                'success': True,
                'message': mesaj
            })
        else:
            return jsonify({
                'success': False,
                'message': mesaj
            }), 400
    
    except Exception as e:
        logger.exception(f"❌ Fatura silme hatası (ID: {id}): {e}")
        return jsonify({
            'success': False,
            'message': _("Silme işlemi başarısız: ") + str(e)
        }), 500


# ========================================
# GÖRÜNTÜLEME (VIEW) - MySQL Optimized
# ========================================
@fatura_bp.route('/goruntule/<uuid:id>')
@login_required
@permission_required('fatura_listele')
def goruntule(id):
    """
    Fatura Detay Görüntüleme
    
    Permissions: fatura_listele
    Args:
        id: Fatura ID (UUID)
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Veritabanı bağlantısı yok', 'danger')
        return redirect(url_for('main.index'))
    
    # ✅ Eager loading (tüm ilişkiler)
    fatura = FaturaService.get_by_id(
        str(id),
        current_user.firma_id,
        tenant_db
    )
    
    if not fatura:
        flash(_("Fatura bulunamadı"), "error")
        return redirect(url_for('fatura.index'))
    
    return render_template('fatura/detay.html', fatura=fatura)


# ========================================
# FATURA ONAYLA
# ========================================
@fatura_bp.route('/onayla/<uuid:id>', methods=['POST'])
@login_required
@permission_required('fatura_onayla')
@audit_log('fatura', 'onayla')
def onayla(id):
    """
    Faturayı onayla ve entegrasyonları çalıştır
    
    Permissions: fatura_onayla
    Args:
        id: Fatura ID (UUID)
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': 'Veritabanı bağlantısı yok'
        }), 500
    
    try:
        fatura = tenant_db.query(Fatura).filter_by(
            id=str(id),
            firma_id=current_user.firma_id
        ).first()
        
        if not fatura:
            return jsonify({
                'success': False,
                'message': 'Fatura bulunamadı'
            }), 404
        
        if fatura.durum == 'ONAYLANDI':
            return jsonify({
                'success': False,
                'message': 'Fatura zaten onaylı'
            }), 400
        
        # Listener fonksiyonunu çağır
        basari, mesaj = fatura_onayla_handler(fatura)
        
        if basari:
            logger.info(
                f"✅ Fatura onaylandı: {fatura.belge_no} "
                f"(Kullanıcı: {current_user.email})"
            )
            
            return jsonify({
                'success': True,
                'message': mesaj
            })
        else:
            return jsonify({
                'success': False,
                'message': mesaj
            }), 400
    
    except Exception as e:
        logger.exception(f"❌ Fatura onaylama hatası: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========================================
# FATURA İPTAL ET
# ========================================
@fatura_bp.route('/iptal-et/<uuid:id>', methods=['POST'])
@login_required
@permission_required('fatura_iptal')
@audit_log('fatura', 'iptal')
def iptal_et(id):
    """
    Faturayı iptal et
    
    Permissions: fatura_iptal
    Args:
        id: Fatura ID (UUID)
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': 'Veritabanı bağlantısı yok'
        }), 500
    
    try:
        data = request.get_json()
        iptal_nedeni = data.get('iptal_nedeni', 'Belirtilmedi')
        
        fatura = tenant_db.query(Fatura).filter_by(
            id=str(id),
            firma_id=current_user.firma_id
        ).first()
        
        if not fatura:
            return jsonify({
                'success': False,
                'message': 'Fatura bulunamadı'
            }), 404
        
        if fatura.iptal_mi:
            return jsonify({
                'success': False,
                'message': 'Fatura zaten iptal edilmiş'
            }), 400
        
        # Listener fonksiyonunu çağır
        basari, mesaj = fatura_iptal_et_handler(fatura, iptal_nedeni)
        
        if basari:
            logger.warning(
                f"⚠️ Fatura iptal edildi: {fatura.belge_no} - {iptal_nedeni} "
                f"(Kullanıcı: {current_user.email})"
            )
            
            return jsonify({
                'success': True,
                'message': mesaj
            })
        else:
            return jsonify({
                'success': False,
                'message': mesaj
            }), 400
    
    except Exception as e:
        logger.exception(f"❌ Fatura iptal hatası: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========================================
# API: STOK ARAMA (AJAX SELECT2) - MySQL Optimized
# ========================================
@fatura_bp.route('/api/stok-ara')
@login_required
def api_stok_ara():
    """
    Stok kartları için AJAX arama endpoint'i
    
    Query Params:
        term: Arama kelimesi
        page: Sayfa numarası (default: 1)
    
    Returns:
        JSON: Select2 formatında sonuçlar
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'results': [],
            'pagination': {'more': False}
        })
    
    term = request.args.get('term', '').strip()
    page = request.args.get('page', 1, type=int)
    limit = 20
    
    try:
        # ✅ MySQL Full-Text Search (Index: idx_stok_fulltext)
        # Eğer full-text index varsa
        if term and len(term) >= 2:
            # Full-text search
            query = tenant_db.execute(text("""
                SELECT id, kod, ad, birim
                FROM stok_kartlari
                WHERE firma_id = :firma_id
                AND aktif = 1
                AND deleted_at IS NULL
                AND MATCH(kod, ad) AGAINST(:term IN NATURAL LANGUAGE MODE)
                LIMIT :limit OFFSET :offset
            """), {
                'firma_id': current_user.firma_id,
                'term': term,
                'limit': limit,
                'offset': (page - 1) * limit
            })
            
            results = []
            for row in query:
                results.append({
                    'id': str(row[0]),
                    'text': f"{row[1]} - {row[2]} ({row[3] or 'Adet'})"
                })
            
            # Sayfa kontrolü
            has_more = len(results) == limit
            
            return jsonify({
                'results': results,
                'pagination': {'more': has_more}
            })
        
        else:
            # Term yoksa veya kısa ise, ilk 20 kaydı getir
            query = tenant_db.query(StokKart).filter(
                StokKart.firma_id == current_user.firma_id,
                StokKart.aktif == True,
                StokKart.deleted_at.is_(None)
            ).order_by(StokKart.kod).limit(limit).offset((page - 1) * limit)
            
            results = [
                {
                    'id': str(s.id),
                    'text': f"{s.kod} - {s.ad} ({s.birim or 'Adet'})"
                }
                for s in query.all()
            ]
            
            return jsonify({
                'results': results,
                'pagination': {'more': len(results) == limit}
            })
    
    except Exception as e:
        logger.error(f"❌ Stok arama hatası: {e}")
        return jsonify({
            'results': [],
            'pagination': {'more': False}
        })


# ========================================
# API: SIRADAKİ BELGE NUMARASI - MySQL Optimized
# ========================================
@fatura_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    """
    Fatura için sıradaki belge numarasını üretir
    
    Returns:
        JSON: {'code': 'FAT-00001'}
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({'code': 'FAT-00001'})
    
    try:
        # ✅ MySQL Optimized: MAX() kullan (index sayesinde hızlı)
        son_belge = tenant_db.query(
            func.max(Fatura.belge_no)
        ).filter(
            Fatura.firma_id == current_user.firma_id
        ).scalar()
        
        if son_belge and '-' in son_belge:
            try:
                prefix, num = son_belge.split('-')
                yeni_kod = f"{prefix}-{str(int(num) + 1).zfill(5)}"
            except:
                yeni_kod = 'FAT-00001'
        else:
            yeni_kod = 'FAT-00001'
        
        return jsonify({'code': yeni_kod})
    
    except Exception as e:
        logger.error(f"❌ Belge no üretme hatası: {e}")
        return jsonify({'code': 'FAT-00001'})


# ========================================
# API: FİYAT HESAPLAMA - MySQL + AI Optimized
# ========================================
@fatura_bp.route('/api/get-fiyat', methods=['POST'])
@login_required
def api_get_fiyat():
    """
    Stok fiyatını hesaplar (Çapraz Kur + Fiyat Listesi + AI Analiz)
    
    Request JSON:
        {
            'stok_id': str (UUID),
            'fatura_turu': str,
            'doviz_turu': str,
            'doviz_kuru': float,
            'liste_id': str (UUID, optional),
            'miktar': float (optional)
        }
    
    Returns:
        JSON: {
            'success': bool,
            'fiyat': Decimal,
            'iskonto_orani': Decimal,
            'kdv_orani': int,
            'birim': str,
            'ai_metadata': dict,
            'debug': dict
        }
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': 'Veritabanı bağlantısı yok'
        }), 500
    
    try:
        data = request.get_json()
        
        stok_id = data.get('stok_id')
        liste_id = data.get('liste_id')
        fatura_turu = data.get('fatura_turu', 'SATIS')
        fatura_para_birimi = data.get('doviz_turu', 'TL')
        miktar = data.get('miktar')
        
        # ✅ Kur dönüşümü (Decimal)
        try:
            fatura_kur_raw = data.get('doviz_kuru', 1)
            if isinstance(fatura_kur_raw, (int, float)):
                fatura_kur = Decimal(str(fatura_kur_raw))
            else:
                fatura_kur = para_cevir(fatura_kur_raw)
        except Exception as e:
            logger.error(f"❌ Kur dönüşüm hatası: {e}")
            fatura_kur = Decimal('1.0')
        
        if fatura_kur <= 0:
            fatura_kur = Decimal('1.0')
        
        if not stok_id:
            return jsonify({
                'success': False,
                'message': 'Stok ID eksik'
            }), 400
        
        # Miktar Decimal'e çevir
        if miktar:
            try:
                miktar = Decimal(str(miktar))
            except:
                miktar = None
        
        # Servisi çağır
        result = FiyatHesaplamaService.hesapla(
            stok_id=stok_id,
            fatura_turu=fatura_turu,
            fatura_para_birimi=fatura_para_birimi,
            fatura_kuru=fatura_kur,
            liste_id=liste_id,
            miktar=miktar,
            firma_id=current_user.firma_id,
            tenant_db=tenant_db
        )
        
        # JSON için Float'a çevir
        return jsonify({
            'success': True,
            'fiyat': float(result['fiyat']),
            'iskonto_orani': float(result['iskonto_orani']),
            'kdv_orani': result['kdv_orani'],
            'birim': result['birim'],
            'ai_metadata': result.get('ai_metadata'),
            'debug': result.get('debug')
        })
    
    except Exception as e:
        logger.error(f"❌ Fiyat hesaplama hatası: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========================================
# API: DÖVİZ KURU GETİRME - MySQL Optimized
# ========================================
@fatura_bp.route('/api/get-kur/<doviz_kodu>')
@login_required
def api_get_kur(doviz_kodu: str):
    """
    Belirtilen döviz kodunun güncel kurunu getirir
    
    Args:
        doviz_kodu: TL, USD, EUR, GBP
    
    Returns:
        JSON: {'kur': 42.50}
    """
    
    try:
        if not doviz_kodu or doviz_kodu.upper() == 'TL':
            return jsonify({'kur': 1.0})
        
        # Önce cache'ten kontrol et (Redis)
        from app.extensions import cache
        
        cache_key = f"doviz_kuru:{doviz_kodu.upper()}"
        kur = cache.get(cache_key)
        
        if kur is None:
            # Cache'te yoksa API'den çek
            kur = get_doviz_kuru(doviz_kodu.upper())
            
            if kur and kur > 0:
                # 1 saatlik cache
                cache.set(cache_key, kur, timeout=3600)
            else:
                kur = 1.0
        
        return jsonify({'kur': float(kur)})
    
    except Exception as e:
        logger.error(f"❌ Kur getirme hatası ({doviz_kodu}): {e}")
        return jsonify({
            'kur': 1.0,
            'error': str(e)
        })


# ========================================
# API: CARİ DETAY - MySQL Optimized
# ========================================
@fatura_bp.route('/api/get-cari-detay/<uuid:cari_id>')
@login_required
def api_get_cari_detay(cari_id):
    """
    Cari hesap detaylarını getirir
    
    Args:
        cari_id: Cari Hesap ID (UUID)
    
    Returns:
        JSON: {
            'success': bool,
            'bakiye': Decimal,
            'risk_skoru': int,
            'risk_durumu': str,
            'limit_durumu': str,
            'ai_oneriler': list
        }
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': 'Veritabanı bağlantısı yok'
        }), 500
    
    try:
        # ✅ MySQL Native UUID query
        cari = tenant_db.query(CariHesap).filter_by(
            id=str(cari_id),
            firma_id=current_user.firma_id
        ).first()
        
        if not cari:
            return jsonify({
                'success': False,
                'message': _('Cari bulunamadı')
            }), 404
        
        # Bakiye
        bakiye = float(getattr(cari, 'bakiye', 0) or 0)
        risk_skoru = getattr(cari, 'risk_skoru', 0) or 0
        
        # Risk durumu
        if risk_skoru > 70:
            risk_durumu = 'yuksek'
            risk_mesaj = _('Yüksek Riskli Müşteri')
            risk_renk = 'danger'
        elif risk_skoru > 40:
            risk_durumu = 'orta'
            risk_mesaj = _('Orta Riskli Müşteri')
            risk_renk = 'warning'
        else:
            risk_durumu = 'dusuk'
            risk_mesaj = _('Düşük Riskli Müşteri')
            risk_renk = 'success'
        
        # Limit kontrolü
        limit = float(getattr(cari, 'risk_limiti', 0) or 0)
        if limit > 0 and bakiye > limit:
            limit_durumu = 'asim'
            limit_mesaj = _('⚠️ Limit Aşıldı!')
            limit_renk = 'danger'
        else:
            limit_durumu = 'normal'
            limit_mesaj = _('✅ Limit Dahilinde')
            limit_renk = 'success'
        
        # AI Önerileri
        ai_oneriler = []
        
        if bakiye > limit:
            ai_oneriler.append({
                'tip': 'UYARI',
                'mesaj': f'Limit {limit:.2f} TL aşıldı. Tahsilat yapılmalı.',
                'ikon': 'bi-exclamation-triangle'
            })
        
        if risk_skoru > 60:
            ai_oneriler.append({
                'tip': 'DİKKAT',
                'mesaj': 'Risk skoru yüksek. Teminat talep edilebilir.',
                'ikon': 'bi-shield-exclamation'
            })
        
        # Churn riski
        if hasattr(cari, 'churn_riski') and cari.churn_riski > 60:
            ai_oneriler.append({
                'tip': 'FİRSAT',
                'mesaj': 'Müşteri kaybetme riski var. İskonto teklif edilebilir.',
                'ikon': 'bi-gift'
            })
        
        return jsonify({
            'success': True,
            'bakiye': bakiye,
            'risk_skoru': risk_skoru,
            'risk_durumu': risk_durumu,
            'risk_mesaj': risk_mesaj,
            'risk_renk': risk_renk,
            'limit_durumu': limit_durumu,
            'limit_mesaj': limit_mesaj,
            'limit_renk': limit_renk,
            'limit': limit,
            'ai_oneriler': ai_oneriler
        })
    
    except Exception as e:
        logger.error(f"❌ Cari detay hatası (ID: {cari_id}): {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========================================
# API: E-FATURA GÖNDER
# ========================================
@fatura_bp.route('/api/efatura-gonder/<uuid:id>', methods=['POST'])
@login_required
@permission_required('efatura_gonder')
def api_efatura_gonder(id):
    """
    Faturayı GİB'e e-fatura olarak gönderir
    
    Permissions: efatura_gonder
    Args:
        id: Fatura ID (UUID)
    
    Returns:
        JSON: {'success': bool, 'message': str}
    """
    
    try:
        # Lazy Import
        from app.modules.efatura.services import EntegratorService
        
        service = EntegratorService(current_user.firma_id)
        basari, mesaj = service.fatura_gonder(str(id))
        
        if basari:
            logger.info(
                f"✅ E-Fatura gönderildi: ID {id} "
                f"(Kullanıcı: {current_user.email})"
            )
            return jsonify({
                'success': True,
                'message': mesaj
            })
        else:
            logger.warning(f"⚠️ E-Fatura gönderilemedi: {mesaj}")
            return jsonify({
                'success': False,
                'message': mesaj
            }), 400
    
    except ImportError:
        logger.error("❌ E-Fatura modülü yüklenemedi")
        return jsonify({
            'success': False,
            'message': _("E-Fatura modülü bulunamadı")
        }), 500
    
    except Exception as e:
        logger.exception(f"❌ E-Fatura gönderme hatası (ID: {id}): {e}")
        return jsonify({
            'success': False,
            'message': _("E-Fatura gönderilemedi: ") + str(e)
        }), 500


# ========================================
# API: E-FATURA DURUM SORGULA
# ========================================
@fatura_bp.route('/api/efatura-durum/<uuid:id>', methods=['GET'])
@login_required
def api_efatura_durum(id):
    """
    E-Fatura durumunu GİB'den sorgular
    
    Args:
        id: Fatura ID (UUID)
    
    Returns:
        JSON: {
            'success': bool,
            'durum_kodu': int,
            'durum_aciklama': str,
            'ettn': str
        }
    """
    
    try:
        from app.modules.efatura.services import EntegratorService
        
        service = EntegratorService(current_user.firma_id)
        sonuc = service.fatura_durum_sorgula(str(id))
        
        return jsonify(sonuc)
    
    except ImportError:
        return jsonify({
            'success': False,
            'message': _("E-Fatura modülü bulunamadı")
        }), 500
    
    except Exception as e:
        logger.exception(f"❌ E-Fatura durum sorgulama hatası (ID: {id}): {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ========================================
# RAPORLAMA API'LERİ
# ========================================

@fatura_bp.route('/api/ozet-istatistikler', methods=['GET'])
@login_required
def api_ozet_istatistikler():
    """
    Fatura özet istatistikleri (Dashboard için)
    
    Returns:
        JSON: {
            'bugun': {...},
            'bu_ay': {...},
            'gecen_ay': {...}
        }
    """
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({})
    
    try:
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        bugun = date.today()
        bu_ay_baslangic = bugun.replace(day=1)
        gecen_ay_baslangic = bu_ay_baslangic - relativedelta(months=1)
        gecen_ay_bitis = bu_ay_baslangic - relativedelta(days=1)
        
        # ✅ MySQL Aggregate Query (tek sorgu)
        stats = tenant_db.execute(text("""
            SELECT 
                COUNT(CASE WHEN tarih = :bugun THEN 1 END) as bugun_adet,
                COALESCE(SUM(CASE WHEN tarih = :bugun THEN genel_toplam END), 0) as bugun_tutar,
                
                COUNT(CASE WHEN tarih >= :bu_ay_baslangic THEN 1 END) as bu_ay_adet,
                COALESCE(SUM(CASE WHEN tarih >= :bu_ay_baslangic THEN genel_toplam END), 0) as bu_ay_tutar,
                
                COUNT(CASE WHEN tarih BETWEEN :gecen_ay_baslangic AND :gecen_ay_bitis THEN 1 END) as gecen_ay_adet,
                COALESCE(SUM(CASE WHEN tarih BETWEEN :gecen_ay_baslangic AND :gecen_ay_bitis THEN genel_toplam END), 0) as gecen_ay_tutar
            FROM faturalar
            WHERE firma_id = :firma_id
            AND durum = 'ONAYLANDI'
            AND deleted_at IS NULL
        """), {
            'firma_id': current_user.firma_id,
            'bugun': bugun,
            'bu_ay_baslangic': bu_ay_baslangic,
            'gecen_ay_baslangic': gecen_ay_baslangic,
            'gecen_ay_bitis': gecen_ay_bitis
        }).fetchone()
        
        return jsonify({
            'bugun': {
                'adet': stats[0],
                'tutar': float(stats[1])
            },
            'bu_ay': {
                'adet': stats[2],
                'tutar': float(stats[3])
            },
            'gecen_ay': {
                'adet': stats[4],
                'tutar': float(stats[5])
            }
        })
    
    except Exception as e:
        logger.error(f"❌ İstatistik hatası: {e}")
        return jsonify({})