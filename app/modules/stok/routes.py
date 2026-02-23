# app/modules/stok/routes.py (MySQL + Redis + Babel + AI)

"""
Stok Modülü HTTP Route Layer
Enterprise Grade - Thin Controller Pattern - Redis Cached - i18n Ready
"""

import os
import re
from decimal import Decimal
from sqlalchemy.orm import joinedload
from flask import (
    Blueprint, render_template, request, jsonify, current_app,
    url_for, redirect, flash, session, abort, send_file
)
from flask_login import login_required, current_user
from flask_babel import gettext as _, lazy_gettext
from werkzeug.utils import secure_filename

from sqlalchemy import func, extract, literal, text, or_
from sqlalchemy.orm import joinedload

from app.extensions import db, cache, get_tenant_db, get_tenant_info
from app.modules.stok.models import (
    StokKart, StokPaketIcerigi, StokDepoDurumu,
    StokMuhasebeGrubu, StokKDVGrubu, StokHareketi
)
from app.modules.kategori.models import StokKategori
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.models import AIRaporGecmisi, AIRaporAyarlari
from app.modules.depo.models import Depo
from app.modules.sube.models import Sube

from app.form_builder import DataGrid, FieldType
from .forms import (
    create_stok_form, get_muhasebe_grup_form,
    get_kdv_grup_form, create_ai_settings_form,
    create_paket_icerik_form
)
from .services import (
    StokKartService, StokHareketService,
    StokAIService, PaketUrunService
)

from datetime import datetime, timedelta
from app.enums import StokKartTipi, FaturaTuru
from app.araclar import para_cevir
from app.decorators import protected_route, tenant_route, audit_log, permission_required

import logging
import json

# Logger
logger = logging.getLogger(__name__)

# Blueprint
stok_bp = Blueprint('stok', __name__)

# Constants
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def get_aktif_firma_id():
    """
    Güvenli Firma ID Çözümleyici (UUID Destekli)
    Artık int() çevrimi yapmıyoruz, doğrudan string/UUID dönüyoruz.
    Aktif firma ID'sini döndürür
    
    Returns:
        str: Firma ID (UUID)
    """
    # Öncelik 1: Session'dan
    if 'firma_id' in session:
        return session['firma_id']
    
    # Öncelik 2: Tenant info'dan
    tenant_info = get_tenant_info()
    if tenant_info and 'firma_id' in tenant_info:
        return tenant_info['firma_id']
    
    # Öncelik 3: Tenant ID = Firma ID (senin mimarinde)
    if 'tenant_id' in session:
        return session['tenant_id']
    
    logger.warning("⚠️ Firma ID bulunamadı!")
    return None


# ========================================
# YARDIMCI FONKSİYONLAR
# ========================================
def allowed_file(filename):
    """Dosya uzantısı kontrolü"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_uuid(id_str):
    """UUID string'i validate et"""
    import uuid
    try:
        return str(uuid.UUID(str(id_str)))
    except (ValueError, AttributeError):
        return None


def get_aktif_firma_id():
    """
    Güvenli Firma ID Çözümleyici (UUID Destekli)
    Artık int() çevrimi yapmıyoruz, doğrudan string/UUID dönüyoruz.
    Aktif firma ID'sini döndürür
    
    Returns:
        str: Firma ID (UUID)
    """
    # Öncelik 1: Session'dan
    if 'firma_id' in session:
        return session['firma_id']
    
    # Öncelik 2: Tenant info'dan
    tenant_info = get_tenant_info()
    if tenant_info and 'firma_id' in tenant_info:
        return tenant_info['firma_id']
    
    # Öncelik 3: Tenant ID = Firma ID (senin mimarinde)
    if 'tenant_id' in session:
        return session['tenant_id']
    
    logger.warning("⚠️ Firma ID bulunamadı!")
    return None


# ========================================
# ANA LİSTELEME EKRANI - MySQL + Redis Optimized
# ========================================
@stok_bp.route('/')
@tenant_route
def index():
    """Stok listesi (Optimized)"""
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("stok_list", StokKart, "Stok Kartları")
    
    # Kolonlar
    grid.add_column('kod', 'Stok Kodu', width='120px')
    grid.add_column('ad', 'Stok Adı')
    grid.add_column('kategori.ad', 'Kategori')  # ← N+1!
    grid.add_column('birim', 'Birim', width='80px')
    grid.add_column('satis_fiyati', 'Satış Fiyatı', type='currency')
    
    # ✅ EAGER LOADING
    firma_id = get_aktif_firma_id()
    query = tenant_db.query(StokKart).options(
        joinedload(StokKart.kategori)  # ✅ Kategori ilişkisi
    ).filter_by(firma_id=firma_id, aktif=True)

    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'barkod', 'uretici_kodu', 'kategori_id',
        'birim', 'tip', 'muhasebe_kod_id', 'kdv_kod_id',
        'kritik_seviye', 'tedarik_suresi_gun', 'raf_omru_gun',
        'garanti_suresi_ay', 'agirlik_kg', 'desi', 'tedarikci_id',
        'mevsimsel_grup', 'marka', 'model', 'mensei',
        'anahtar_kelimeler', 'aciklama_detay', 'ozel_kod1', 'ozel_kod2',
        'resim_path', 'aktif', 'olusturma_tarihi', 'created_at', 'updated_at',
        'deleted_at', 'deleted_by', 'ai_metadata', 'ai_tahmin_miktar',
        'ai_olu_stok_riski', 'ai_stok_devir_hizi'
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)

    
    grid.process_query(query)
    
    return render_template('stok/index.html', grid=grid)
    

# ========================================
# YENİ KAYIT (CREATE) - Redis Cache Invalidation
# ========================================
@stok_bp.route('/ekle', methods=['GET', 'POST'])
@protected_route
@permission_required('stok.create')  # Yetki ayrı decorator
@audit_log('stok', 'create')
@login_required
def ekle():
    """
    Yeni Stok Kartı Oluştur
    
    Permissions: stok.create
    """
    form = create_stok_form()
    
    if request.method == 'POST':
        form.process_request(request.form, request.files)
        
        if form.validate():
            tenant_db = get_tenant_db()
            
            try:
                # Resim yükleme
                resim_yolu = None
                if 'resim' in request.files:
                    file = request.files['resim']
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(
                            f"{current_user.firma_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                        )
                        upload_folder = os.path.join(
                            current_app.config.get('UPLOAD_FOLDER', 'uploads'),
                            'stok'
                        )
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        file_path = os.path.join(upload_folder, filename)
                        file.save(file_path)
                        resim_yolu = f"uploads/stok/{filename}"
                
                # Form verilerini al
                data = form.get_data()
                data['resim_path'] = resim_yolu
                
                # Servise delege et
                basari, mesaj = StokKartService.save(data, tenant_db=tenant_db)
                
                if basari:
                    logger.info(
                        f"✅ Stok oluşturuldu: {data.get('kod')} "
                        f"(Kullanıcı: {current_user.email})"
                    )
                    
                    return jsonify({
                        'success': True,
                        'message': mesaj,
                        'redirect': url_for('stok.index')
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': mesaj
                    }), 400
            
            except Exception as e:
                logger.exception(f"❌ Stok oluşturma hatası: {e}")
                return jsonify({
                    'success': False,
                    'message': _("Beklenmeyen hata: %(error)s", error=str(e))
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': _('Validasyon hatası'),
                'errors': form.get_errors()
            }), 400
    
    return render_template('stok/form.html', form=form, title=_("Yeni Stok Kartı"))


# ========================================
# DÜZENLEME (UPDATE) - Redis Cache Invalidation
# ========================================
@stok_bp.route('/duzenle/<uuid:id>', methods=['GET', 'POST'])
@protected_route
@audit_log('stok', 'update')
@login_required
def duzenle(id):
    """
    Stok Kartı Düzenle
    
    Permissions: stok.update
    Args:
        id: Stok ID (UUID)
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    # Stok kartını getir (servisten - cached)
    stok = StokKartService.get_by_id(str(id), current_user.firma_id, tenant_db)
    
    if not stok:
        flash(_('Stok bulunamadı'), 'danger')
        return redirect(url_for('stok.index'))
    
    form = create_stok_form(stok)
    
    if request.method == 'POST':
        form.process_request(request.form, request.files)
        
        if form.validate():
            try:
                # Resim güncelleme
                if 'resim' in request.files:
                    file = request.files['resim']
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(
                            f"{current_user.firma_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                        )
                        upload_folder = os.path.join(
                            current_app.config.get('UPLOAD_FOLDER', 'uploads'),
                            'stok'
                        )
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        file_path = os.path.join(upload_folder, filename)
                        file.save(file_path)
                        
                        # Eski resmi sil (opsiyonel)
                        if stok.resim_path:
                            try:
                                old_file = os.path.join(
                                    current_app.root_path,
                                    'static',
                                    stok.resim_path
                                )
                                if os.path.exists(old_file):
                                    os.remove(old_file)
                            except:
                                pass
                        
                        stok.resim_path = f"uploads/stok/{filename}"
                
                # Form verilerini al
                data = form.get_data()
                
                # Servise delege et
                basari, mesaj = StokKartService.save(data, stok=stok, tenant_db=tenant_db)
                
                if basari:
                    logger.info(
                        f"✅ Stok güncellendi: {stok.kod} "
                        f"(Kullanıcı: {current_user.email})"
                    )
                    
                    return jsonify({
                        'success': True,
                        'message': mesaj,
                        'redirect': url_for('stok.index')
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': mesaj
                    }), 400
            
            except Exception as e:
                logger.exception(f"❌ Stok güncelleme hatası: {e}")
                return jsonify({
                    'success': False,
                    'message': _("Güncelleme başarısız: %(error)s", error=str(e))
                }), 500
    
    return render_template('stok/form.html', form=form, title=_("Stok Kartı Düzenle"))


# ========================================
# SİLME (DELETE) - Redis Cache Invalidation
# ========================================
@stok_bp.route('/sil/<uuid:id>', methods=['POST'])
@protected_route
@audit_log('stok', 'delete')
@login_required
def sil(id):
    """
    Stok Kartı Sil (Soft Delete)
    
    Permissions: stok.delete
    Args:
        id: Stok ID (UUID)
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': _('Veritabanı bağlantısı yok')
        }), 500
    
    try:
        # Servise delege et
        basari, mesaj = StokKartService.sil(str(id), current_user.firma_id, tenant_db)
        
        if basari:
            logger.info(
                f"✅ Stok silindi: ID {id} "
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
        logger.exception(f"❌ Stok silme hatası (ID: {id}): {e}")
        return jsonify({
            'success': False,
            'message': _("Silme işlemi başarısız: %(error)s", error=str(e))
        }), 500


# ========================================
# DETAY EKRANI - Redis Cached
# ========================================
@stok_bp.route('/detay/<uuid:id>')
@protected_route
@login_required
def detay(id):
    """
    Stok Detay ve Hareketler
    
    Permissions: stok.view
    Args:
        id: Stok ID (UUID)
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    # Stok kartını getir (servisten - cached)
    stok = StokKartService.get_by_id(str(id), current_user.firma_id, tenant_db)
    
    if not stok:
        abort(404)
    
    # GÜVENLİK FİLTRESİ (Yetki kontrolü)
    merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
    aktif_bolge_id = session.get('aktif_bolge_id')
    aktif_sube_id = session.get('aktif_sube_id')
    
    izinli_sube_ids = []
    
    if current_user.rol not in merkez_rolleri:
        if aktif_bolge_id:
            subeler = tenant_db.query(Sube).filter_by(bolge_id=aktif_bolge_id).all()
            izinli_sube_ids = [s.id for s in subeler]
        elif aktif_sube_id:
            izinli_sube_ids = [aktif_sube_id]
    
    # ✅ MySQL Optimized Query (Index: idx_hareket_stok_tarih)
    hareket_query = tenant_db.query(StokHareketi).options(
        joinedload(StokHareketi.giris_depo),
        joinedload(StokHareketi.cikis_depo),
        joinedload(StokHareketi.kullanici)
    ).filter(
        StokHareketi.stok_id == str(id),
        StokHareketi.firma_id == current_user.firma_id
    )
    
    # Yetki filtreleme
    if current_user.rol not in merkez_rolleri:
        if izinli_sube_ids:
            hareket_query = hareket_query.filter(
                StokHareketi.sube_id.in_(izinli_sube_ids)
            )
        else:
            hareket_query = hareket_query.filter(literal(False))
    
    hareketler = hareket_query.order_by(
        StokHareketi.tarih.desc(),
        StokHareketi.created_at.desc()
    ).limit(100).all()
    
    # Depo durumları
    depo_query = tenant_db.query(
        Depo.ad,
        StokDepoDurumu.miktar
    ).join(
        StokDepoDurumu,
        Depo.id == StokDepoDurumu.depo_id
    ).filter(
        StokDepoDurumu.stok_id == str(id),
        StokDepoDurumu.miktar != 0
    )
    
    # Yetki filtreleme
    if current_user.rol not in merkez_rolleri:
        if izinli_sube_ids:
            depo_query = depo_query.filter(Depo.sube_id.in_(izinli_sube_ids))
        else:
            depo_query = depo_query.filter(literal(False))
    
    depo_durumlari = depo_query.all()
    
    # AI tahmin (cached)
    ai_tahmin = StokAIService.talep_tahmini(str(id), current_user.firma_id, tenant_db)
    
    return render_template(
        'stok/detay.html',
        stok=stok,
        hareketler=hareketler,
        depo_durumlari=depo_durumlari,
        ai_tahmin=ai_tahmin
    )


# ========================================
# API: OTOMATİK NUMARA - Redis Cached
# ========================================
@stok_bp.route('/api/siradaki-kod')
@login_required
@cache.cached(timeout=60, key_prefix='stok_siradaki_kod')
def api_siradaki_kod():
    """
    Sıradaki stok kodunu üret (Cached - 60 saniye)
    
    Returns:
        JSON: {'code': 'STK-0001'}
    """
    tenant_db = get_tenant_db()
    
    try:
        # ✅ MySQL Optimized: MAX() kullan
        son_kod = tenant_db.query(
            func.max(StokKart.kod)
        ).filter(
            StokKart.firma_id == current_user.firma_id
        ).scalar()
        
        yeni_kod = "STK-0001"
        
        if son_kod:
            try:
                if '-' in son_kod:
                    prefix, numara = son_kod.rsplit('-', 1)
                    yeni_num = str(int(numara) + 1).zfill(len(numara))
                    yeni_kod = f"{prefix}-{yeni_num}"
                elif '.' in son_kod:
                    prefix, numara = son_kod.rsplit('.', 1)
                    yeni_num = str(int(numara) + 1).zfill(len(numara))
                    yeni_kod = f"{prefix}.{yeni_num}"
                else:
                    yeni_kod = str(int(son_kod) + 1)
            except:
                pass
        
        return jsonify({'code': yeni_kod})
    
    except Exception as e:
        logger.error(f"❌ Kod üretme hatası: {e}")
        return jsonify({'code': 'STK-0001'})


# ========================================
# API: STOK ARAMA (AJAX SELECT2) - Redis Cached
# ========================================
@stok_bp.route('/api/stok-ara')
@login_required
def api_stok_ara():
    """
    Stok arama (AJAX Select2 için)
    
    Query Params:
        term: Arama kelimesi
        page: Sayfa numarası
    
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
        # Cache key
        cache_key = f"stok_ara:{current_user.firma_id}:{term}:{page}"
        
        # Cache'ten kontrol et
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        # ✅ MySQL Full-Text Search (Index: idx_stok_fulltext)
        if term and len(term) >= 2:
            # Full-text search query
            query = tenant_db.execute(text("""
                SELECT id, kod, ad, birim
                FROM stok_kartlari
                WHERE firma_id = :firma_id
                AND aktif = 1
                AND deleted_at IS NULL
                AND MATCH(ad, anahtar_kelimeler) AGAINST(:term IN NATURAL LANGUAGE MODE)
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
            
            has_more = len(results) == limit
        
        else:
            # Terim yoksa veya kısa ise, ilk 20 kaydı getir
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
            
            has_more = len(results) == limit
        
        result_data = {
            'results': results,
            'pagination': {'more': has_more}
        }
        
        # Cache'e kaydet (5 dakika)
        cache.set(cache_key, result_data, timeout=300)
        
        return jsonify(result_data)
    
    except Exception as e:
        logger.error(f"❌ Stok arama hatası: {e}")
        return jsonify({
            'results': [],
            'pagination': {'more': False}
        })


# ========================================
# BELGE GİT (Hareket kaynak belgesine git)
# ========================================
@stok_bp.route('/belge-git/<uuid:hareket_id>')
@login_required
def belge_git(hareket_id):
    """
    Stok hareketinin kaynak belgesine git
    
    Args:
        hareket_id: StokHareketi ID
    """
    tenant_db = get_tenant_db()
    
    hareket = tenant_db.query(StokHareketi).get(str(hareket_id))
    
    if not hareket:
        abort(404)
    
    # Kaynak türüne göre yönlendir
    if hareket.kaynak_turu == 'fatura' and hareket.kaynak_id:
        return redirect(url_for('fatura.duzenle', id=hareket.kaynak_id))
    
    elif hareket.kaynak_turu == 'stok_fisi' and hareket.kaynak_id:
        return redirect(url_for('stok_fisi.duzenle', id=hareket.kaynak_id))
    
    elif hareket.kaynak_turu == 'siparis' and hareket.kaynak_id:
        return redirect(url_for('siparis.detay', id=hareket.kaynak_id))
    
    # Belge numarasından çıkarım yap
    if hareket.belge_no:
        match = re.search(r'(FIS-\d{4}-\d+|MOB-[\w-]+|FAT-[\w-]+)', hareket.belge_no)
        if match:
            belge_no = match.group(0)
            
            if belge_no.startswith('FAT'):
                fatura = tenant_db.query(Fatura).filter_by(belge_no=belge_no).first()
                if fatura:
                    return redirect(url_for('fatura.duzenle', id=fatura.id))
    
    flash(_("İlgili kaynak belge bulunamadı"), "warning")
    return redirect(request.referrer or url_for('stok.detay', id=hareket.stok_id))


# ========================================
# YAPAY ZEKA ANALİZ EKRANI
# ========================================
@stok_bp.route('/yapay-zeka-analiz')
@protected_route
@login_required
def yapay_zeka_analiz():
    """AI Analiz Dashboard"""
    return render_template('stok/ai_analiz.html')


# ========================================
# API: ÖLÜ STOK ANALİZİ - Redis Cached
# ========================================
@stok_bp.route('/api/olu-stok-hesapla', methods=['POST'])
@protected_route
@login_required
def api_olu_stok_hesapla():
    """
    Ölü stok analizi (AI + Cached)
    
    Returns:
        JSON: {
            'success': bool,
            'report': str (HTML),
            'kesin_toplam': float
        }
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': _('Veritabanı bağlantısı yok')
        }), 500
    
    try:
        # Servisten cached analizi al
        analiz = StokAIService.olu_stok_analizi(current_user.firma_id, tenant_db)
        
        if analiz['urun_sayisi'] == 0:
            return jsonify({
                'success': False,
                'message': _('Harika! Deponuzda ölü stok tespit edilemedi.')
            })
        
        # AI'ya gönder (detaylı rapor için)
        try:
            from app.form_builder.ai_generator import analyze_dead_stock
            
            json_data = json.dumps(analiz['urunler'][:50], ensure_ascii=False)
            rapor_html = analyze_dead_stock(json_data)
            
            # Raporu kaydet
            yeni_rapor = AIRaporGecmisi(
                firma_id=current_user.firma_id,
                rapor_turu='OLU_STOK',
                baslik=f"{datetime.now().strftime('%d.%m.%Y')} - {_('Ölü Stok Analizi')}",
                html_icerik=str(rapor_html),
                ham_veri_json=json_data
            )
            tenant_db.add(yeni_rapor)
            tenant_db.commit()
            
            return jsonify({
                'success': True,
                'report': rapor_html,
                'kesin_toplam': analiz['toplam_deger']
            })
        
        except Exception as ai_error:
            logger.error(f"❌ AI rapor oluşturma hatası: {ai_error}")
            
            # AI başarısız olursa manuel rapor
            rapor_html = f"""
            <div class="alert alert-warning">
                <h5>{_('Ölü Stok Analiz Özeti')}</h5>
                <p>{_('Toplam %(count)d ürün tespit edildi.', count=analiz['urun_sayisi'])}</p>
                <p>{_('Bağlı sermaye: %(tutar)s TL', tutar=f"{analiz['toplam_deger']:,.2f}")}</p>
            </div>
            """
            
            return jsonify({
                'success': True,
                'report': rapor_html,
                'kesin_toplam': analiz['toplam_deger']
            })
    
    except Exception as e:
        logger.error(f"❌ Ölü stok analizi hatası: {e}")
        return jsonify({
            'success': False,
            'message': _("Analiz başarısız: %(error)s", error=str(e))
        }), 500


# ========================================
# PAKET ÜRÜN İÇERİK EKRANI
# ========================================
@stok_bp.route('/paket-icerik/<uuid:id>', methods=['GET', 'POST'])
@protected_route
@login_required
def paket_icerik(id):
    """
    Paket ürün içeriği tanımlama
    
    Permissions: stok.update
    Args:
        id: Paket stok ID
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    stok = StokKartService.get_by_id(str(id), current_user.firma_id, tenant_db)
    
    if not stok:
        abort(404)
    
    # Tip kontrolü
    if request.method == 'GET' and stok.tip not in ['PAKET', 'MAMUL', 'SET']:
        flash(
            _(
                "Bu ürünün tipi '%(tip)s'. Paket içeriği sadece Paket/Set ürünler için tanımlanabilir.",
                tip=stok.tip
            ),
            "warning"
        )
    
    form = create_paket_icerik_form(str(id))
    
    if request.method == 'POST':
        form.process_request(request.form)
        
        if form.validate():
            try:
                # İçerik listesini hazırla
                alt_stok_ids = request.form.getlist('bilesenler_alt_stok_id[]')
                miktarlar = request.form.getlist('bilesenler_miktar[]')
                
                icerik_listesi = []
                for i in range(len(alt_stok_ids)):
                    alt_id = alt_stok_ids[i]
                    miktar = miktarlar[i]
                    
                    if alt_id and miktar:
                        icerik_listesi.append({
                            'alt_stok_id': alt_id,
                            'miktar': para_cevir(miktar)
                        })
                
                # Servise delege et
                basari, mesaj = PaketUrunService.icerik_kaydet(
                    str(id),
                    icerik_listesi,
                    tenant_db
                )
                
                if basari:
                    logger.info(
                        f"✅ Paket içeriği güncellendi: {stok.kod} "
                        f"({len(icerik_listesi)} bileşen)"
                    )
                    
                    return jsonify({
                        'success': True,
                        'message': mesaj,
                        'redirect': url_for('stok.detay', id=id)
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': mesaj
                    }), 400
            
            except Exception as e:
                logger.exception(f"❌ Paket içerik kaydetme hatası: {e}")
                return jsonify({
                    'success': False,
                    'message': _("Kaydetme başarısız: %(error)s", error=str(e))
                }), 500
    
    return render_template('stok/paket.html', form=form, stok=stok)


# ========================================
# MUHASEBE GRUBU YÖNETİMİ
# ========================================
@stok_bp.route('/tanimlar/muhasebe-gruplari')
@protected_route
@login_required
def muhasebe_gruplari():
    """Muhasebe Grupları Listesi"""
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    grid = DataGrid("grid_muh_grup", StokMuhasebeGrubu, title=_("Stok Muhasebe Grupları"))
    grid.columns = []
    grid.add_column("kod", _("Grup Kodu"), width="150px")
    grid.add_column("ad", _("Grup Adı"))
    grid.add_column("aciklama", _("Açıklama"))
    grid.add_column("aktif", _("Durum"), type=FieldType.SWITCH)
    
    grid.add_action("edit", _("Düzenle"), "fas fa-edit", "btn-primary", action_type="route", route_name="stok.muhasebe_grup_islem")
    
    query = tenant_db.query(StokMuhasebeGrubu).filter_by(
        firma_id=current_user.firma_id,
        deleted_at=None
    )
    grid.process_query(query)
    
    return render_template(
        'stok/tanimlar/list.html',
        grid=grid,
        create_url=url_for('stok.muhasebe_grup_islem_yeni')
    )


# ========================================
# KDV GRUBU YÖNETİMİ
# ========================================
@stok_bp.route('/tanimlar/kdv-gruplari')
@protected_route
@login_required
def kdv_gruplari():
    """KDV Grupları Listesi"""
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash(_('Veritabanı bağlantısı yok'), 'danger')
        return redirect(url_for('main.index'))
    
    grid = DataGrid("grid_kdv", StokKDVGrubu, title=_("KDV Grupları"))
    grid.columns = []
    grid.add_column("kod", _("Kod"), width="150px")
    grid.add_column("ad", _("Ad"))
    grid.add_column("alis_kdv_orani", _("Alış (%)"), type=FieldType.NUMBER)
    grid.add_column("satis_kdv_orani", _("Satış (%)"), type=FieldType.NUMBER)
    
    grid.add_action("edit", _("Düzenle"), "fas fa-edit", "btn-primary", action_type="route", route_name="stok.kdv_grup_islem")
    
    query = tenant_db.query(StokKDVGrubu).filter_by(
        firma_id=current_user.firma_id,
        deleted_at=None
    )
    grid.process_query(query)
    
    return render_template(
        'stok/tanimlar/list.html',
        grid=grid,
        create_url=url_for('stok.kdv_grup_islem_yeni')
    )


# ========================================
# STOK BAKİYE DÜZELTME (Acil Durum Butonu)
# ========================================
@stok_bp.route('/yonetim/bakiyeleri-duzelt')
@protected_route
@login_required
def bakiyeleri_duzelt():
    """
    Acil Durum: Stok bakiyelerini sıfırdan hesapla
    
    Permissions: admin
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({
            'success': False,
            'message': _('Veritabanı bağlantısı yok')
        }), 500
    
    try:
        # Mevcut kayıtları temizle
        tenant_db.query(StokDepoDurumu).filter_by(
            firma_id=current_user.firma_id
        ).delete()
        tenant_db.flush()
        
        # Tüm hareketleri topla
        hareketler = tenant_db.query(StokHareketi).filter_by(
            firma_id=current_user.firma_id
        ).all()
        
        # Hafızada hesapla
        depo_stok_map = {}
        
        for h in hareketler:
            try:
                miktar = float(h.miktar or 0)
                
                # Giriş depo
                if h.giris_depo_id:
                    key = (h.giris_depo_id, h.stok_id)
                    depo_stok_map[key] = depo_stok_map.get(key, 0) + miktar
                
                # Çıkış depo
                if h.cikis_depo_id:
                    key = (h.cikis_depo_id, h.stok_id)
                    depo_stok_map[key] = depo_stok_map.get(key, 0) - miktar
            except:
                continue
        
        # Database'e yaz
        sayac = 0
        for (depo_id, stok_id), miktar in depo_stok_map.items():
            if miktar != 0:
                yeni_kayit = StokDepoDurumu(
                    firma_id=current_user.firma_id,
                    depo_id=depo_id,
                    stok_id=stok_id,
                    miktar=Decimal(str(miktar)),
                    son_hareket_tarihi=date.today()
                )
                tenant_db.add(yeni_kayit)
                sayac += 1
        
        tenant_db.commit()
        
        # Cache'leri temizle
        cache.clear()
        
        logger.info(
            f"✅ Stok bakiyeleri düzeltildi: "
            f"{len(hareketler)} hareket tarandı, {sayac} kayıt güncellendi"
        )
        
        return jsonify({
            'success': True,
            'message': _(
                "TAMAMLANDI! %(hareket)d hareket tarandı, %(kayit)d bakiye güncellendi.",
                hareket=len(hareketler),
                kayit=sayac
            )
        })
    
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"❌ Bakiye düzeltme hatası: {e}")
        return jsonify({
            'success': False,
            'message': _("Hata oluştu: %(error)s", error=str(e))
        }), 500