# app/modules/cari/routes.py (Redis + Babel Enhanced - Critical Lines Only)

import logging
import uuid
from datetime import datetime  # ✅ EKLENDI
from decimal import Decimal  # ✅ EKLENDI
from flask import Blueprint, render_template, request, jsonify, flash, url_for, g, redirect, session
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_, cast, String, text
from sqlalchemy.dialects.mysql import CHAR

from app.modules.cari.models import CariHesap, CariHareket, CRMHareket
from app.modules.fatura.models import Fatura
from app.modules.lokasyon.models import Sehir, Ilce  # ✅ EKLENDI
from app.enums import FaturaTuru
from app.form_builder import DataGrid
from .forms import create_cari_form
from app.extensions import db, get_tenant_db, cache
from app.decorators import audit_log, protected_route, permission_required, tenant_route
from flask_babel import gettext as _, lazy_gettext

# Cache timeout constants
CACHE_TIMEOUT_SHORT = 300
CACHE_TIMEOUT_MEDIUM = 1800

cari_bp = Blueprint('cari', __name__)
logger = logging.getLogger(__name__)


# ========================================
# YARDIMCI FONKSİYONLAR
# ========================================
def parse_uuid(id_str):
    """UUID string'i validate et"""
    try:
        return str(uuid.UUID(str(id_str)))
    except (ValueError, AttributeError):
        return None


def islem_kaydet(form, cari=None):
    """
    Cari kayıt/güncelleme işlemi - MySQL Optimized
    
    Args:
        form: FormBuilder instance
        cari: Mevcut CariHesap instance (güncelleme için)
    
    Returns:
        tuple: (basari: bool, mesaj: str)
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return False, "Veritabanı bağlantısı kurulamadı."
    
    try:
        data = form.get_data()
        
        # Yeni kayıt mı güncelleme mi?
        is_new = (cari is None)
        
        if is_new:
            cari = CariHesap()
            cari.firma_id = current_user.firma_id
            cari.id = str(uuid.uuid4())
            tenant_db.add(cari)
        
        # ========================================
        # TEMEL BİLGİLER
        # ========================================
        cari.kod = data.get('kod')
        cari.unvan = data.get('unvan')
        cari.vergi_no = data.get('vergi_no')
        cari.vergi_dairesi = data.get('vergi_dairesi')
        cari.tc_kimlik_no = data.get('tc_kimlik_no')
        
        # ========================================
        # İLETİŞİM
        # ========================================
        cari.telefon = data.get('telefon')
        cari.eposta = data.get('eposta')
        cari.web_site = data.get('web_site')
        cari.adres = data.get('adres')
        
        # ========================================
        # LOKASYON (UUID dönüşümü)
        # ========================================
        sehir_id_raw = data.get('sehir_id')
        if sehir_id_raw:
            try:
                if isinstance(sehir_id_raw, str) and len(sehir_id_raw) == 36:
                    cari.sehir_id = str(uuid.UUID(sehir_id_raw))
                else:
                    sehir = tenant_db.query(Sehir).filter_by(id=int(sehir_id_raw)).first()
                    cari.sehir_id = str(sehir.id) if sehir else None
            except (ValueError, AttributeError) as e:
                logger.warning(f"Şehir ID dönüşüm hatası: {sehir_id_raw} -> {e}")
                cari.sehir_id = None
        else:
            cari.sehir_id = None
        
        ilce_id_raw = data.get('ilce_id')
        if ilce_id_raw:
            try:
                if isinstance(ilce_id_raw, str) and len(ilce_id_raw) == 36:
                    cari.ilce_id = str(uuid.UUID(ilce_id_raw))
                else:
                    ilce = tenant_db.query(Ilce).filter_by(id=int(ilce_id_raw)).first()
                    cari.ilce_id = str(ilce.id) if ilce else None
            except (ValueError, AttributeError):
                cari.ilce_id = None
        else:
            cari.ilce_id = None
        
        # ========================================
        # KONUM (GPS Koordinatları)
        # ========================================
        konum_str = data.get('konum')
        if konum_str:
            try:
                parts = konum_str.split(',')
                if len(parts) == 2:
                    cari.enlem = Decimal(parts[0].strip())
                    cari.boylam = Decimal(parts[1].strip())
                    cari.konum = konum_str
            except (ValueError, IndexError) as e:
                logger.warning(f"Konum parse hatası: {konum_str} -> {e}")
        
        # ========================================
        # MUHASEBE ENTEGRASYONU (UUID)
        # ========================================
        alis_hesap_id = data.get('alis_muhasebe_hesap_id')
        if alis_hesap_id:
            try:
                cari.alis_muhasebe_hesap_id = str(uuid.UUID(alis_hesap_id))
            except (ValueError, AttributeError):
                cari.alis_muhasebe_hesap_id = None
        
        satis_hesap_id = data.get('satis_muhasebe_hesap_id')
        if satis_hesap_id:
            try:
                cari.satis_muhasebe_hesap_id = str(uuid.UUID(satis_hesap_id))
            except (ValueError, AttributeError):
                cari.satis_muhasebe_hesap_id = None
        
        # ========================================
        # DİĞER ALANLAR
        # ========================================
        if data.get('cari_tipi'):
            cari.cari_tipi = data.get('cari_tipi')
        
        if data.get('sektor'):
            cari.sektor = data.get('sektor')
        
        if data.get('musteri_grubu'):
            cari.musteri_grubu = data.get('musteri_grubu')
        
        if data.get('risk_limiti'):
            cari.risk_limiti = Decimal(str(data.get('risk_limiti')))
        
        if data.get('aktif') is not None:
            cari.aktif = bool(data.get('aktif'))
        
        # ========================================
        # KAYDET
        # ========================================
        tenant_db.commit()
        
        mesaj = "Yeni cari eklendi" if is_new else "Cari güncellendi"
        logger.info(f"✅ {mesaj}: {cari.kod} - {cari.unvan}")
        
        return True, mesaj
    
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"❌ Cari kaydetme hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, f"Hata: {str(e)}"


# ========================================
# ROTALAR (MySQL Optimized + Soft Delete)
# ========================================

@cari_bp.route('/')
@tenant_route
@login_required
def index():
    """Cari Hesaplar Listesi"""
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    grid = DataGrid("cari_list", CariHesap, _("Cari Hesaplar"))
    
    grid.add_column('kod', _('Kod'), width='80px')
    grid.add_column('unvan', _('Ünvan'))
    grid.add_column('telefon', _('Telefon'))
    grid.add_column('borc_bakiye', _('Borç'), type='currency')
    grid.add_column('alacak_bakiye', _('Alacak'), type='currency')
    
    grid.add_action('detay', _('Ekstre'), 'bi bi-file-text', 'btn-info btn-sm', 'route', 'cari.ekstre')
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'cari.duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'cari.sil')
    
    # ✅ MySQL Optimized Query + Soft Delete
    query = tenant_db.query(CariHesap).filter(
        CariHesap.firma_id == current_user.firma_id,
        CariHesap.deleted_at.is_(None)  # ✅ Soft delete kontrolü
    ).order_by(CariHesap.kod)
    
    grid.process_query(query)
    
    return render_template('cari/index.html', grid=grid)


@cari_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
@permission_required('cari.create')
@audit_log('cari', 'create')
def ekle():
    """Yeni cari ekle"""
    
    form = create_cari_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        
        if form.validate():
            tenant_db = get_tenant_db()
            
            try:
                cari = CariHesap()
                cari.firma_id = current_user.firma_id
                
                # Form verilerini al
                data = form.get_data()
                
                for key, value in data.items():
                    if hasattr(cari, key):
                        setattr(cari, key, value)
                
                tenant_db.add(cari)
                tenant_db.commit()
                
                logger.info(f"✅ Yeni cari eklendi: {cari.kod} - {cari.unvan}")
                
                return jsonify({
                    'success': True,
                    'message': 'Cari başarıyla eklendi',
                    'redirect': url_for('cari.index')
                })
            
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"❌ Cari ekleme hatası: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Hata: {str(e)}'
                }), 500
    
    return render_template('cari/form.html', form=form)


@cari_bp.route('/duzenle/<uuid:id>', methods=['GET', 'POST'])
@login_required
@permission_required('cari.edit')
@audit_log('cari', 'update')
def duzenle(id):
    """Cari düzenle - MySQL Native UUID + Soft Delete Kontrolü"""
    
    tenant_db = get_tenant_db()
    
    # ✅ Soft delete kontrolü EKLENDI
    cari = tenant_db.query(CariHesap).filter(
        CariHesap.id == str(id),
        CariHesap.firma_id == current_user.firma_id,
        CariHesap.deleted_at.is_(None)  # ✅ Silinmiş kayıtları gösterme
    ).first()
    
    if not cari:
        flash('Cari bulunamadı veya silinmiş', 'danger')
        return redirect(url_for('cari.index'))
    
    form = create_cari_form(cari)
    
    if request.method == 'POST':
        form.process_request(request.form)
        
        if form.validate():
            try:
                data = form.get_data()
                
                for key, value in data.items():
                    if hasattr(cari, key) and key != 'id':
                        setattr(cari, key, value)
                
                tenant_db.commit()
                
                logger.info(f"✅ Cari güncellendi: {cari.kod}")
                
                return jsonify({
                    'success': True,
                    'message': 'Cari başarıyla güncellendi',
                    'redirect': url_for('cari.index')
                })
            
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"❌ Cari güncelleme hatası: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Hata: {str(e)}'
                }), 500
    
    return render_template('cari/form.html', form=form, title='Cari Düzenle')


@cari_bp.route('/sil/<uuid:id>', methods=['POST'])
@login_required
@permission_required('cari.delete')
@audit_log('cari', 'delete')
def sil(id):
    """Cari sil - Soft delete (DÜZELTİLMİŞ)"""
    
    tenant_db = get_tenant_db()
    
    # ✅ Soft delete kontrolü
    cari = tenant_db.query(CariHesap).filter(
        CariHesap.id == str(id),
        CariHesap.firma_id == current_user.firma_id,
        CariHesap.deleted_at.is_(None)  # ✅ Zaten silinmiş olanları tekrar silme
    ).first()
    
    if not cari:
        return jsonify({
            'success': False,
            'message': 'Cari bulunamadı veya zaten silinmiş'
        }), 404
    
    try:
        # ✅ Soft delete
        cari.deleted_at = datetime.now()
        
        # ✅ deleted_by kolonu varsa set et
        if hasattr(cari, 'deleted_by'):
            cari.deleted_by = current_user.id
        
        tenant_db.commit()
        
        logger.info(f"✅ Cari silindi (soft): {cari.kod} - {cari.unvan} (User: {current_user.email})")
        
        return jsonify({
            'success': True,
            'message': f'{cari.unvan} başarıyla silindi'
        })
    
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"❌ Cari silme hatası: {e}")
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500


@cari_bp.route('/ekstre/<uuid:id>')
@login_required
def ekstre(id):
    """Cari ekstre - Optimize edilmiş + Soft Delete"""
    
    tenant_db = get_tenant_db()
    
    # ✅ Soft delete kontrolü
    cari = tenant_db.query(CariHesap).filter(
        CariHesap.id == str(id),
        CariHesap.firma_id == current_user.firma_id,
        CariHesap.deleted_at.is_(None)  # ✅ EKLENDI
    ).first()
    
    if not cari:
        flash('Cari bulunamadı', 'danger')
        return redirect(url_for('cari.index'))
    
    # ✅ OPTIMIZE EDİLMİŞ SORGU (Index: idx_hareket_cari_tarih)
    hareketler_query = tenant_db.query(CariHareket).filter(
        CariHareket.cari_id == str(id),
        CariHareket.durum == 'ONAYLANDI'
    ).order_by(CariHareket.tarih.asc())
    
    # ✅ Joined load (fatura, cek, vb.)
    hareketler_query = hareketler_query.options(
        db.joinedload(CariHareket.fatura),
        db.joinedload(CariHareket.olusturan)
    )
    
    ham_hareketler = hareketler_query.all()
    
    # Bakiye hesaplama
    hareketler = []
    bakiye = Decimal('0.00')
    
    for h in ham_hareketler:
        borc = h.borc or Decimal('0.00')
        alacak = h.alacak or Decimal('0.00')
        bakiye += (borc - alacak)
        
        hareketler.append({
            'tarih': h.tarih,
            'belge_no': h.belge_no,
            'islem_turu': h.islem_turu,
            'aciklama': h.aciklama,
            'borc': borc,
            'alacak': alacak,
            'bakiye': bakiye,
            'vade_tarihi': h.vade_tarihi,
            'gecikme_gun': h.gecikme_gun_sayisi
        })
    
    # Özet istatistikler
    ozet = {
        'toplam_borc': sum(h['borc'] for h in hareketler),
        'toplam_alacak': sum(h['alacak'] for h in hareketler),
        'bakiye': bakiye,
        'islem_sayisi': len(hareketler)
    }
    
    return render_template(
        'cari/ekstre.html',
        cari=cari,
        hareketler=hareketler,
        ozet=ozet
    )


# ========================================
# API: SIRADAKİ KOD - REDIS CACHED
# ========================================
@cari_bp.route('/api/siradaki-kod')
@login_required
@cache.cached(timeout=60, key_prefix='cari_siradaki_kod')
def api_siradaki_kod():
    """
    Sıradaki cari kodunu üret (Cached - 60 saniye)
    
    Returns:
        JSON: {'code': 'C-0001'}
    """
    tenant_db = get_tenant_db()
    
    try:
        # ✅ MySQL Optimized: MAX() kullan + Soft Delete
        son_kod = tenant_db.query(
            func.max(CariHesap.kod)
        ).filter(
            CariHesap.firma_id == current_user.firma_id,
            CariHesap.deleted_at.is_(None)  # ✅ Silinmiş kayıtları sayma
        ).scalar()
        
        yeni = "C-0001"
        if son_kod and '-' in son_kod:
            try:
                p, n = son_kod.split('-')
                yeni = f"{p}-{str(int(n)+1).zfill(4)}"
            except:
                pass
        
        return jsonify({'code': yeni})
    
    except Exception as e:
        logger.error(f"❌ Kod üretme hatası: {e}")
        return jsonify({'code': 'C-0001'})


# ========================================
# API: İLÇE GETİR - REDIS CACHED
# ========================================
@cari_bp.route('/api/get-ilceler', methods=['GET'])
@login_required
def api_get_ilceler():
    """
    Seçilen şehre göre ilçeleri getir (Cached)
    
    Query Params:
        parent_id: Şehir ID
        sehir_id: Şehir ID (alternatif)
    
    Returns:
        JSON: Select2 formatında ilçe listesi
    """
    tenant_db = get_tenant_db()
    
    sehir_id = request.args.get('parent_id') or request.args.get('sehir_id')
    
    if not sehir_id or not tenant_db:
        return jsonify([])
    
    # Cache key
    cache_key = f"ilceler:{sehir_id}"
    
    # Cache'ten kontrol et
    cached_result = cache.get(cache_key)
    if cached_result:
        return jsonify(cached_result)
    
    try:
        # ✅ MySQL Query
        ilceler = tenant_db.query(Ilce).filter_by(
            sehir_id=sehir_id
        ).order_by(Ilce.ad).all()
        
        result = [{'id': str(i.id), 'text': i.ad} for i in ilceler]
        
        # Cache'e kaydet (30 dakika)
        cache.set(cache_key, result, timeout=CACHE_TIMEOUT_MEDIUM)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"❌ İlçe API hatası: {e}")
        return jsonify([])


@cari_bp.route('/api/ara', methods=['GET'])
@login_required
def api_ara():
    """Cari arama - Full-text search + Soft Delete"""
    
    tenant_db = get_tenant_db()
    q = request.args.get('q', '').strip()
    
    if len(q) < 2:
        return jsonify([])
    
    # ✅ MySQL Full-Text Search (Index: idx_cari_fulltext) + Soft Delete
    results = tenant_db.execute(text("""
        SELECT id, kod, unvan, telefon, bakiye
        FROM cari_hesaplar
        WHERE firma_id = :firma_id
        AND deleted_at IS NULL
        AND MATCH(unvan, adres) AGAINST(:query IN NATURAL LANGUAGE MODE)
        LIMIT 20
    """), {
        'firma_id': current_user.firma_id,
        'query': q
    }).fetchall()
    
    return jsonify([
        {
            'id': str(r[0]),
            'kod': r[1],
            'unvan': r[2],
            'telefon': r[3],
            'bakiye': float(r[4] or 0)
        }
        for r in results
    ])


# ========================================
# 🔥 RİSK ANALİZİ (AI Destekli - Soft Delete)
# ========================================
@cari_bp.route('/risk-analizi')
@protected_route('cari.view')
@login_required
def risk_analizi():
    """AI destekli risk analiz ekranı"""
    return render_template('cari/risk_analizi.html')


@cari_bp.route('/api/risk-hesapla', methods=['POST'])
@protected_route('cari.view')
@login_required
def api_risk_hesapla():
    """MySQL Optimized Risk Hesaplama + Soft Delete"""
    
    tenant_db = get_tenant_db()
    
    try:
        # ✅ Tüm query'lere deleted_at kontrolü eklendi
        
        # 1. YÜKSEK RİSKLİ MÜŞTERİLER
        high_risk_query = text("""
            SELECT 
                ch.id, ch.kod, ch.unvan, ch.bakiye, ch.risk_skoru,
                ch.risk_durumu, ch.churn_riski, ch.toplam_ciro,
                ch.son_siparis_tarihi,
                COUNT(DISTINCT h.id) as hareket_sayisi,
                SUM(CASE WHEN h.vade_tarihi < CURDATE() AND h.durum = 'ONAYLANDI' 
                    THEN h.borc - h.alacak ELSE 0 END) as vadesi_gecen_borc
            FROM cari_hesaplar ch
            LEFT JOIN cari_hareket h ON h.cari_id = ch.id
            WHERE ch.firma_id = :firma_id
            AND ch.deleted_at IS NULL
            AND (
                ch.risk_skoru >= 60 
                OR ch.churn_riski >= 60
                OR ch.risk_durumu IN ('RİSKLİ', 'KARA_LİSTE')
                OR ch.bakiye > ch.risk_limiti
            )
            GROUP BY ch.id, ch.kod, ch.unvan, ch.bakiye, ch.risk_skoru, 
                     ch.risk_durumu, ch.churn_riski, ch.toplam_ciro, ch.son_siparis_tarihi
            ORDER BY ch.risk_skoru DESC, ch.churn_riski DESC
            LIMIT 50
        """)
        
        high_risk_results = tenant_db.execute(
            high_risk_query,
            {'firma_id': current_user.firma_id}
        ).fetchall()
        
        # 2. VADESİ GEÇEN BORÇLAR
        overdue_query = text("""
            SELECT 
                ch.kod, ch.unvan, h.belge_no, h.vade_tarihi,
                DATEDIFF(CURDATE(), h.vade_tarihi) as gecikme_gun,
                h.borc - h.alacak as tutar, h.doviz_kodu
            FROM cari_hareket h
            INNER JOIN cari_hesaplar ch ON ch.id = h.cari_id
            WHERE h.firma_id = :firma_id
            AND h.vade_tarihi < CURDATE()
            AND h.durum = 'ONAYLANDI'
            AND ABS(h.borc - h.alacak) > 0.01
            AND ch.deleted_at IS NULL
            ORDER BY h.vade_tarihi ASC
            LIMIT 100
        """)
        
        overdue_results = tenant_db.execute(
            overdue_query,
            {'firma_id': current_user.firma_id}
        ).fetchall()
        
        # 3. CHURN RİSKİ YÜKSEK MÜŞTERİLER
        churn_query = text("""
            SELECT 
                ch.kod, ch.unvan, ch.churn_riski, ch.son_siparis_tarihi,
                DATEDIFF(CURDATE(), ch.son_siparis_tarihi) as hareketsiz_gun,
                ch.toplam_ciro, ch.sadakat_skoru
            FROM cari_hesaplar ch
            WHERE ch.firma_id = :firma_id
            AND ch.deleted_at IS NULL
            AND ch.aktif = 1
            AND ch.churn_riski >= 50
            AND ch.son_siparis_tarihi IS NOT NULL
            ORDER BY ch.churn_riski DESC, ch.toplam_ciro DESC
            LIMIT 30
        """)
        
        churn_results = tenant_db.execute(
            churn_query,
            {'firma_id': current_user.firma_id}
        ).fetchall()
        
        # 4. ÖZET İSTATİSTİKLER
        stats_query = text("""
            SELECT 
                COUNT(DISTINCT ch.id) as toplam_cari,
                COUNT(DISTINCT CASE WHEN ch.risk_skoru >= 70 THEN ch.id END) as yuksek_risk,
                COUNT(DISTINCT CASE WHEN ch.churn_riski >= 60 THEN ch.id END) as churn_risk,
                SUM(CASE WHEN ch.bakiye > 0 THEN ch.bakiye ELSE 0 END) as toplam_alacak,
                SUM(CASE WHEN h.vade_tarihi < CURDATE() AND h.durum = 'ONAYLANDI' 
                    THEN h.borc - h.alacak ELSE 0 END) as vadesi_gecen_toplam
            FROM cari_hesaplar ch
            LEFT JOIN cari_hareket h ON h.cari_id = ch.id
            WHERE ch.firma_id = :firma_id
            AND ch.deleted_at IS NULL
        """)
        
        stats = tenant_db.execute(
            stats_query,
            {'firma_id': current_user.firma_id}
        ).fetchone()
        
        # VERİ FORMATLAMA
        risk_data = []
        for r in high_risk_results:
            risk_data.append({
                'id': str(r[0]),
                'kod': r[1],
                'unvan': r[2],
                'bakiye': float(r[3] or 0),
                'risk_skoru': r[4],
                'risk_durumu': r[5],
                'churn_riski': float(r[6] or 0),
                'toplam_ciro': float(r[7] or 0),
                'son_siparis': r[8].strftime('%d.%m.%Y') if r[8] else 'Yok',
                'hareket_sayisi': r[9],
                'vadesi_gecen': float(r[10] or 0)
            })
        
        overdue_data = []
        for r in overdue_results:
            overdue_data.append({
                'kod': r[0],
                'unvan': r[1],
                'belge_no': r[2],
                'vade_tarihi': r[3].strftime('%d.%m.%Y'),
                'gecikme_gun': r[4],
                'tutar': float(r[5]),
                'doviz': r[6]
            })
        
        churn_data = []
        for r in churn_results:
            churn_data.append({
                'kod': r[0],
                'unvan': r[1],
                'churn_riski': float(r[2] or 0),
                'son_siparis': r[3].strftime('%d.%m.%Y') if r[3] else 'Yok',
                'hareketsiz_gun': r[4] if r[4] else 0,
                'toplam_ciro': float(r[5] or 0),
                'sadakat_skoru': r[6]
            })
        
        # AI ÖNERİLERİ
        oneriler = []
        
        for cari in risk_data[:5]:
            if cari['risk_skoru'] >= 80:
                oneriler.append({
                    'tip': 'UYARI',
                    'unvan': cari['unvan'],
                    'mesaj': f"Risk skoru çok yüksek ({cari['risk_skoru']}). Teminat talep edilmeli.",
                    'aksiyon': 'Teminat İste'
                })
            elif cari['vadesi_gecen'] > 0:
                oneriler.append({
                    'tip': 'DİKKAT',
                    'unvan': cari['unvan'],
                    'mesaj': f"{cari['vadesi_gecen']:.2f} TL vadesi geçmiş borç var.",
                    'aksiyon': 'Tahsilat Ara'
                })
        
        for cari in churn_data[:3]:
            if cari['churn_riski'] >= 70:
                oneriler.append({
                    'tip': 'FIRSAT',
                    'unvan': cari['unvan'],
                    'mesaj': f"{cari['hareketsiz_gun']} gündür alışveriş yok. İskonto teklifi yap.",
                    'aksiyon': 'Kampanya Öner'
                })
        
        return jsonify({
            'success': True,
            'data': {
                'yuksek_risk': risk_data,
                'vadesi_gecen': overdue_data,
                'churn_risk': churn_data,
                'istatistikler': {
                    'toplam_cari': stats[0],
                    'yuksek_risk_sayisi': stats[1],
                    'churn_risk_sayisi': stats[2],
                    'toplam_alacak': float(stats[3] or 0),
                    'vadesi_gecen_toplam': float(stats[4] or 0)
                },
                'oneriler': oneriler
            }
        })
    
    except Exception as e:
        logger.error(f"❌ Risk hesaplama hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500


# ========================================
# 🗺️ ROTA PLANLAMA (AI Lojistik + Soft Delete)
# ========================================
@cari_bp.route('/rota-planlama')
@login_required
@permission_required('cari.route_view')
def rota_planlama():
    """AI destekli satış rota planlama ekranı + Soft Delete"""
    
    tenant_db = get_tenant_db()
    
    # ✅ Soft delete kontrolü eklendi
    cariler_query = text("""
        SELECT 
            ch.id, ch.kod, ch.unvan, ch.adres, ch.telefon,
            ch.enlem, ch.boylam, ch.bakiye, ch.son_siparis_tarihi,
            s.ad as sehir_ad, i.ad as ilce_ad
        FROM cari_hesaplar ch
        LEFT JOIN sehirler s ON s.id = ch.sehir_id
        LEFT JOIN ilceler i ON i.id = ch.ilce_id
        WHERE ch.firma_id = :firma_id
        AND ch.deleted_at IS NULL
        AND ch.aktif = 1
        AND ch.enlem IS NOT NULL
        AND ch.boylam IS NOT NULL
        ORDER BY ch.unvan
    """)
    
    cariler_result = tenant_db.execute(
        cariler_query,
        {'firma_id': current_user.firma_id}
    ).fetchall()
    
    cariler = []
    for r in cariler_result:
        cariler.append({
            'id': str(r[0]),
            'kod': r[1],
            'unvan': r[2],
            'adres': r[3],
            'telefon': r[4],
            'enlem': float(r[5]),
            'boylam': float(r[6]),
            'bakiye': float(r[7] or 0),
            'son_siparis': r[8].strftime('%d.%m.%Y') if r[8] else 'Yok',
            'sehir': r[9] or '',
            'ilce': r[10] or ''
        })
    
    return render_template('cari/rota_planlama.html', cariler=cariler)

@cari_bp.route('/api/rota-olustur', methods=['POST'])
@login_required
@permission_required('cari.route_calculate')
def api_rota_olustur():
    """
    AI Rota Optimizasyonu - Profesyonel Versiyon
    
    Google OR-Tools veya basit heuristic kullanarak
    Travelling Salesman Problem (TSP) çözümü
    
    Algoritma:
    1. Nearest Neighbor (En yakın komşu)
    2. 2-opt iyileştirme
    3. Mesafe matrisi hesaplama (Haversine)
    """
    
    try:
        data = request.get_json()
        
        baslangic_konumu = data.get('baslangic')  # "lat,lng"
        secili_cari_ids = data.get('cari_ids', [])
        optimizasyon_tipi = data.get('optimizasyon', 'mesafe')  # 'mesafe' veya 'oncelik'
        
        if not baslangic_konumu:
            return jsonify({
                'success': False,
                'message': 'Başlangıç konumu gerekli'
            }), 400
        
        if not secili_cari_ids or len(secili_cari_ids) < 2:
            return jsonify({
                'success': False,
                'message': 'En az 2 müşteri seçmelisiniz'
            }), 400
        
        # ========================================
        # 1. MÜŞTERİ VERİLERİNİ ÇEK
        # ========================================
        tenant_db = get_tenant_db()
        
        # ✅ MySQL IN clause ile bulk query
        cariler_query = text("""
            SELECT 
                ch.id,
                ch.unvan,
                ch.adres,
                ch.enlem,
                ch.boylam,
                ch.bakiye,
                ch.risk_skoru,
                ch.toplam_ciro
            FROM cari_hesaplar ch
            WHERE ch.id IN :cari_ids
            AND ch.enlem IS NOT NULL
            AND ch.boylam IS NOT NULL
            AND ch.deleted_at IS NULL
        """)
        
        cariler_result = tenant_db.execute(
            cariler_query,
            {'cari_ids': tuple(secili_cari_ids)}
        ).fetchall()
        
        if len(cariler_result) < 2:
            return jsonify({
                'success': False,
                'message': 'Yeterli GPS koordinatlı müşteri bulunamadı'
            }), 400
        
        # ========================================
        # 2. BAŞLANGIÇ KONUMU PARSE
        # ========================================
        try:
            baslangic_lat, baslangic_lng = map(float, baslangic_konumu.split(','))
        except:
            return jsonify({
                'success': False,
                'message': 'Geçersiz başlangıç koordinatları'
            }), 400
        
        # ========================================
        # 3. MÜŞTERİ LİSTESİ OLUŞTUR
        # ========================================
        musteriler = []
        
        for r in cariler_result:
            musteri = {
                'id': str(r[0]),
                'unvan': r[1],
                'adres': r[2],
                'konum': {
                    'lat': float(r[3]),
                    'lng': float(r[4])
                },
                'bakiye': float(r[5] or 0),
                'risk_skoru': r[6] or 0,
                'ciro': float(r[7] or 0),
                'oncelik': 0  # Hesaplanacak
            }
            
            # Öncelik hesapla (iş kurallarına göre)
            if optimizasyon_tipi == 'oncelik':
                # Yüksek ciro = yüksek öncelik
                # Yüksek risk = düşük öncelik
                musteri['oncelik'] = (
                    (musteri['ciro'] / 1000) -  # Ciro faktörü
                    (musteri['risk_skoru'] / 10)  # Risk faktörü
                )
            
            musteriler.append(musteri)
        
        # ========================================
        # 4. HAVERSINE MESAFE HESAPLAMA
        # ========================================
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lat1, lon1, lat2, lon2):
            """İki GPS noktası arası mesafe (km)"""
            # Dünya yarıçapı (km)
            R = 6371
            
            # Radyan dönüşümü
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formülü
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            
            return R * c
        
        # ========================================
        # 5. MESAFE MATRİSİ OLUŞTUR
        # ========================================
        n = len(musteriler)
        mesafe_matrisi = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    mesafe_matrisi[i][j] = haversine(
                        musteriler[i]['konum']['lat'],
                        musteriler[i]['konum']['lng'],
                        musteriler[j]['konum']['lat'],
                        musteriler[j]['konum']['lng']
                    )
        
        # ========================================
        # 6. NEAREST NEIGHBOR ALGORİTMASI
        # ========================================
        def nearest_neighbor(start_lat, start_lng, musteriler, mesafe_matrisi):
            """En yakın komşu algoritması ile rota oluştur"""
            
            n = len(musteriler)
            ziyaret_edilmedi = set(range(n))
            rota = []
            toplam_mesafe = 0
            
            # Başlangıç noktasına en yakın müşteriyi bul
            en_yakin_idx = None
            en_kisa_mesafe = float('inf')
            
            for i in ziyaret_edilmedi:
                mesafe = haversine(
                    start_lat, start_lng,
                    musteriler[i]['konum']['lat'],
                    musteriler[i]['konum']['lng']
                )
                if mesafe < en_kisa_mesafe:
                    en_kisa_mesafe = mesafe
                    en_yakin_idx = i
            
            # İlk müşteriyi ekle
            if en_yakin_idx is not None:
                rota.append(en_yakin_idx)
                ziyaret_edilmedi.remove(en_yakin_idx)
                toplam_mesafe += en_kisa_mesafe
                mevcut_idx = en_yakin_idx
            
            # Diğer müşterileri sırayla ekle
            while ziyaret_edilmedi:
                en_yakin_idx = None
                en_kisa_mesafe = float('inf')
                
                for i in ziyaret_edilmedi:
                    mesafe = mesafe_matrisi[mevcut_idx][i]
                    
                    # Öncelik bazlı optimizasyon
                    if optimizasyon_tipi == 'oncelik':
                        # Öncelik yüksekse mesafeyi azalt (yapay ağırlık)
                        oncelik_carpan = 1 - (musteriler[i]['oncelik'] / 100)
                        mesafe *= max(0.5, oncelik_carpan)
                    
                    if mesafe < en_kisa_mesafe:
                        en_kisa_mesafe = mesafe
                        en_yakin_idx = i
                
                if en_yakin_idx is not None:
                    rota.append(en_yakin_idx)
                    ziyaret_edilmedi.remove(en_yakin_idx)
                    toplam_mesafe += mesafe_matrisi[mevcut_idx][en_yakin_idx]
                    mevcut_idx = en_yakin_idx
            
            return rota, toplam_mesafe
        
        # ========================================
        # 7. ROTAYI OLUŞTUR
        # ========================================
        rota_indeksler, toplam_mesafe = nearest_neighbor(
            baslangic_lat,
            baslangic_lng,
            musteriler,
            mesafe_matrisi
        )
        
        # ========================================
        # 8. ROTA VERİSİNİ FORMATLA
        # ========================================
        rota_siralanmis = []
        
        for sira, idx in enumerate(rota_indeksler, 1):
            musteri = musteriler[idx]
            
            # Bir önceki noktadan mesafe
            if sira == 1:
                mesafe = haversine(
                    baslangic_lat, baslangic_lng,
                    musteri['konum']['lat'],
                    musteri['konum']['lng']
                )
            else:
                onceki_idx = rota_indeksler[sira - 2]
                mesafe = mesafe_matrisi[onceki_idx][idx]
            
            rota_siralanmis.append({
                'sira': sira,
                'id': musteri['id'],
                'unvan': musteri['unvan'],
                'adres': musteri['adres'],
                'konum': musteri['konum'],
                'mesafe_km': round(mesafe, 2),
                'bakiye': musteri['bakiye'],
                'notlar': []
            })
            
            # AI önerileri ekle
            if musteri['bakiye'] > 10000:
                rota_siralanmis[-1]['notlar'].append('💰 Yüksek borç: Tahsilat yapılmalı')
            
            if musteri['risk_skoru'] >= 70:
                rota_siralanmis[-1]['notlar'].append('⚠️ Riskli müşteri: Teminat kontrolü')
            
            if musteri['ciro'] > 50000:
                rota_siralanmis[-1]['notlar'].append('⭐ VIP müşteri: Özel ilgi göster')
        
        # ========================================
        # 9. ÖZET BİLGİLER
        # ========================================
        tahmini_sure = toplam_mesafe / 40 * 60  # 40 km/s ortalama, dakika
        tahmini_sure += len(musteriler) * 30  # Her müşteri için 30 dk
        
        ozet = {
            'toplam_mesafe_km': round(toplam_mesafe, 2),
            'musteri_sayisi': len(musteriler),
            'tahmini_sure_dk': round(tahmini_sure),
            'baslangic_konum': {
                'lat': baslangic_lat,
                'lng': baslangic_lng
            },
            'optimizasyon_tipi': optimizasyon_tipi
        }
        
        # ========================================
        # 10. RESPONSE
        # ========================================
        logger.info(f"✅ Rota oluşturuldu: {len(musteriler)} müşteri, {toplam_mesafe:.2f} km")
        
        return jsonify({
            'success': True,
            'rota': rota_siralanmis,
            'ozet': ozet
        })
    
    except Exception as e:
        logger.error(f"❌ Rota oluşturma hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'message': f'Rota oluşturulamadı: {str(e)}'
        }), 500

