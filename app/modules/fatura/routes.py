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

from app.extensions import db, get_tenant_db, cache, get_tenant_info
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.stok.models import StokKart
from app.modules.cari.models import CariHesap
from app.modules.sube.models import Sube
from app.modules.depo.models import Depo
from app.form_builder import DataGrid
from .forms import create_fatura_form
from .services import FaturaService, FiyatHesaplamaService, FaturaDTO
from .listeners import fatura_onayla_handler, fatura_iptal_et_handler
from app.enums import FaturaTuru, FaturaDurumu, ParaBirimi
from app.decorators import role_required, permission_required, audit_log, tenant_route
from app.araclar import get_doviz_kuru, siradaki_kod_uret, para_cevir
from flask_babel import gettext as _, lazy_gettext

# Cache timeout
CACHE_TIMEOUT_SHORT = 300

import logging

# Logger
logger = logging.getLogger(__name__)

# Blueprint
fatura_bp = Blueprint('fatura', __name__)


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
    """Fatura Listesi Ekranı - i18n Ready - (Optimized)"""
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Veritabanı bağlantısı yok.', 'danger')
        return redirect(url_for('main.index'))
        #return redirect('/')

    
    grid = DataGrid("fatura_list", Fatura, _("Faturalar"))
    
    # Kolonlar
    grid.add_column('tarih', _('Tarih'), type='date', width='100px')
    grid.add_column('belge_no', _('Belge No'), width='120px')
    grid.add_column('cari.unvan', _('Cari Hesap'), sortable=True)
    grid.add_column('sube.ad', _('Şube'), sortable=True)
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
    
    # GİB Durumunu Renkli Badge Olarak Göster
    # Kendi badge mimarine birebir uygun GİB Durum Kolonu
    grid.add_column('gib_durum_metni', _('GİB Durumu'), type='badge', width='120px', badge_colors={
        'ONAYLANDI': 'success',
        'KUYRUKTA': 'warning',
        'ISLENIYOR': 'info',
        'GONDERILMEDI': 'secondary'
    })
    
    # Aksiyonlar
    grid.add_action('view', _('Görüntüle'), 'bi bi-eye', 'btn-info btn-sm', 'route', 'fatura.goruntule')
    grid.add_action('edit', _('Düzenle'), 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'fatura.duzenle')
    grid.add_action('delete', _('Sil'), 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'fatura.sil')
    grid.add_action('goruntule', 'Görüntüle', 'bi bi-eye', 'btn-outline-primary btn-sm', 'url', lambda row: url_for('efatura.goruntule', id=row.id), html_attributes={'target': '_blank'})
    grid.add_action('gonder', 'GİB\'e Gönder', 'bi bi-send-check', 'btn-outline-success btn-sm', 'ajax', 'efatura.gonder')
    grid.add_action('sorgula', 'Durum Sorgula', 'bi bi-arrow-repeat', 'btn-outline-info btn-sm', 'ajax', 'efatura.durum')

    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'created_at', 'updated_at', 'deleted_at',
        'donem_id', 'sube_id','depo_id', 'gun_adi', 'fiyat_listesi_id','ara_toplam',
        'plasiyer_id', 'dovizli_toplam', 'kaydeden_id', 'duzenleyen_id', 'maksimum_iskonto_orani',
        'fatura_saati', 'kaynak_siparis_id', 'musteri_puani', 'e-fatura_tipi', 'gib_durum_aciklama',
        'zarf_uuid', 'xml_path', 'alici_etiket_pk', 'gonderen_etiket_gb',
        'muhasebe_fis_id', 'e_fatura_senaryo', 'gib_gonderim_tarihi', 'gib_yanit_tarihi', 'iade_edilen_fatura_id',
        'iade_edilen_fatura_tarihi', 'dis_belge_no', 'iptal_nedeni', 'satis_kanali',
        'sevk_adresi', 'odeme_durumu', 'iptal_mi', 'iptal_tarihi', 'odeme_sekli_detay', 'odeme_plani_id',
        'internet_satisi_mi', 'web_sitesi_adresi', 'iptal_eden_id', 'e-fatura_tipi', 'tasiyici_unvan',
        'iade_edilen_fatura_no', 'ai_kategori', 'ai_anamoli_skoru', 'gonderim_tarihi_saati', 'ai_metadata',
        'e_fatura_tipi', 'tasiyici_vkn_tckn', 'tasiyici_adres', 'doviz_kuru', 'kdv_toplam', 'iskonto_toplam', 'doviz_turu',
        'ai_tahsilat_tahmini_tarih', 'ai_tahsilat_olasiligi', 'ai_anomali_skoru', 'vade_tarihi'
        
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    # Gizlenecek Sütunlar
    grid.hide_column('id').hide_column('firma_id').hide_column('donem_id').hide_column('depo_id')
    grid.hide_column('cari_id').hide_column('aciklama').hide_column('fatura_id').hide_column('faturalasti_mi')
    grid.hide_column('ettn').hide_column('gib_durum_kodu').hide_column('sofor_soyad').hide_column('sofor_tc')
    grid.hide_column('plaka_dorse').hide_column('tasiyici_firma_vkn').hide_column('tasiyici_firma_unvan')
    grid.hide_column('irsaliye_turu')


    
    # ✅ MySQL Optimized Query (Index: idx_fatura_firma_tarih)
    # query = tenant_db.query(Fatura).options(
    #    # Joined load (tek sorgu)
    #    joinedload(Fatura.cari),
    #    joinedload(Fatura.depo)
    #).filter(
    #    Fatura.firma_id == current_user.firma_id,
    #    Fatura.deleted_at.is_(None)  # Soft delete
    #).order_by(Fatura.tarih.desc())
    
    # ✅ EAGER LOADING (Çoklu İlişki)
    firma_id = get_aktif_firma_id()
    
    # Önce hangi ilişkilerin var olduğunu kontrol et
    eager_loads = [joinedload(Fatura.cari)]  # Cari her zaman var
    
    # Şube ilişkisi varsa ekle
    if hasattr(Fatura, 'sube'):
        eager_loads.append(joinedload(Fatura.sube))
    
    # Depo ilişkisi varsa ekle
    if hasattr(Fatura, 'depo'):
        eager_loads.append(joinedload(Fatura.depo))
    
    try:
        query = tenant_db.query(Fatura).options(
            *eager_loads  # ✅ Dinamik olarak ilişkileri ekle
        ).filter_by(
        firma_id=firma_id, 
        iptal_mi=False
        ).order_by(Fatura.tarih.desc())
    
        logger.debug(
            f"✅ Fatura query oluşturuldu: firma_id={firma_id}, "
            f"eager_loads=['cari', 'sube', 'depo']"
        )
    except InvalidRequestError as e:
        # İlişki hatası varsa fallback
        logger.error(f"❌ Eager loading hatası: {e}")
        
        # Basit query (ilişkiler yüklenmez, N+1 oluşur ama çalışır)
        query = tenant_db.query(Fatura).filter_by(
            firma_id=firma_id,
            iptal_mi=False
        ).order_by(Fatura.tarih.desc())
        
        flash('⚠️ Bazı ilişkiler yüklenemedi, performans düşük olabilir', 'warning')
    
    except Exception as e:
        logger.exception(f"❌ Fatura query hatası: {e}")
        flash('Faturalar yüklenirken hata oluştu', 'danger')
        return redirect(url_for('main.index'))

        
        
    # query = tenant_db.query(Fatura).options(
    #    joinedload(Fatura.cari),   # ✅ Cari ilişkisi
    #    joinedload(Fatura.sube),    # ✅ Şube ilişkisi
    #    joinedload(Fatura.depo)    # ✅ Depo ilişkisi
    # ).filter_by(firma_id=firma_id, iptal_mi=False).order_by(Fatura.tarih.desc())

    
    # Filtreleme (query string'den)  alttakiler son sql de yoktu eksiden kaldı.
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
    form = create_fatura_form(tenant_db=tenant_db)
    return render_template('fatura/form.html', form=form)


# ========================================
# DÜZENLEME (UPDATE) - MySQL Optimized
# ========================================
@fatura_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
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
    
    # 1. Faturayı getir (Servis aracılığıyla veya doğrudan sorguyla)
    fatura = tenant_db.query(Fatura).filter(
        Fatura.id == str(id),
        Fatura.firma_id == current_user.firma_id,
        Fatura.deleted_at.is_(None)
    ).first()
    
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
@fatura_bp.route('/sil/<string:id>', methods=['POST'])
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
@fatura_bp.route('/goruntule/<string:id>', methods=['GET'])
@login_required
def goruntule(id):
    tenant_db = get_tenant_db()
    
    # 1. Faturayı çekiyoruz
    fatura = tenant_db.query(Fatura).filter(
        Fatura.id == str(id),
        Fatura.firma_id == current_user.firma_id,
        Fatura.deleted_at.is_(None)
    ).first()
    
    if not fatura:
        flash("Fatura bulunamadı!", "danger")
        return redirect(url_for('fatura.index'))
        
    # ✨ DÜZELTME 1: Satıcı Firma bilgisini ana veritabanından çekiyoruz
    from app.modules.firmalar.models import Firma
    firma = tenant_db.query(Firma).filter(Firma.id == str(current_user.firma_id)).first()
        
    # ==========================================
    # 2. SAYFALAMA VE NAKLİ YEKÜN HESAPLAMASI
    # ==========================================
    sayfalar = []
    
    if hasattr(fatura.kalemler, 'all'):
        kalemler = fatura.kalemler.all()
    else:
        kalemler = fatura.kalemler or []
        
    sayfa_basina_satir = 18 
    
    toplam_sayfa = (len(kalemler) // sayfa_basina_satir) + (1 if len(kalemler) % sayfa_basina_satir > 0 else 0)
    if toplam_sayfa == 0: toplam_sayfa = 1
    
    yuruyen_toplam = 0.0
    
    for i in range(toplam_sayfa):
        baslangic = i * sayfa_basina_satir
        bitis = baslangic + sayfa_basina_satir
        sayfa_kalemleri = kalemler[baslangic:bitis]
        
        devreden = yuruyen_toplam
        
        sayfa_tutar = sum(float(k.satir_toplami or 0) for k in sayfa_kalemleri)
        yuruyen_toplam += sayfa_tutar
        
        sayfalar.append({
            'sayfa_no': i + 1,
            'kalemler': sayfa_kalemleri,
            'devreden': devreden,
            'nakli_yekun': yuruyen_toplam,
            'son_sayfa_mi': (i + 1 == toplam_sayfa)
        })
        
    # ✨ DÜZELTME 2: firma değişkenini de sayfaya render_template ile gönderiyoruz
    #return render_template('fatura/print.html', fatura=fatura, sayfalar=sayfalar, firma=firma)
    
    # ==========================================
    # 3. DİNAMİK ŞABLON MOTORU (DocumentGenerator)
    # ==========================================
    from app.modules.rapor.doc_engine import DocumentGenerator
    
    try:
        doc_gen = DocumentGenerator(current_user.firma_id)
        
        # doc_engine.py içindeki render_html'e sayfalar verisini 'ekstra_context' ile yolluyoruz
        html_cikti = doc_gen.render_html(
            belge_turu='fatura', 
            veri_objesi=fatura, 
            ekstra_context={'sayfalar': sayfalar} 
        )
        
        return html_cikti
        
    except Exception as e:
        # Eğer veritabanında "fatura" türünde bir şablon bulunamazsa veya hata olursa
        # Sistem çökmesin, standart sabit şablona (print.html) fallback (geri dönüş) yapsın
        logger.warning(f"Dinamik şablon hatası/eksikliği: {e}")
        return render_template('fatura/print.html', fatura=fatura, sayfalar=sayfalar, firma=firma)

# ========================================
# FATURA ONAYLA
# ========================================
@fatura_bp.route('/onayla/<string:id>', methods=['POST'])
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
        fatura = tenant_db.query(Fatura).filter(Fatura.id == str(id)).first()
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
@fatura_bp.route('/iptal-et/<string:id>', methods=['POST'])
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
@fatura_bp.route('/api/stok-ara', methods=['GET'])
@login_required
def api_stok_ara():
    """
    Stok kartları için AJAX arama endpoint'i (Yüksek Performanslı JOIN + LIKE Sorgusu)
    """
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({'results': [], 'pagination': {'more': False}})
    
    term = request.args.get('term') or request.args.get('q', '')
    term = term.strip()
    page = request.args.get('page', 1, type=int)
    limit = 20
    
    try:
        # 🚀 DÜZELTME: LEFT JOIN eklendi. Tablolara 's' ve 'k' takma adları (alias) verildi.
        # COALESCE kullanarak, eğer KDV grubu seçilmemişse boş dönmek yerine 0 dönmesini sağladık.
        sql_query = """
            SELECT 
                s.id, 
                s.kod, 
                s.ad, 
                s.birim, 
                s.satis_fiyati, 
                COALESCE(k.satis_kdv_orani, 0) as kdv_orani
            FROM stok_kartlari s
            LEFT JOIN stok_kdv_gruplari k ON s.kdv_kod_id = k.id
            WHERE s.firma_id = :firma_id
            AND s.aktif = 1
            AND s.deleted_at IS NULL
        """
        
        params = {
            'firma_id': current_user.firma_id,
            'limit': limit,
            'offset': (page - 1) * limit
        }
        
        # Eğer arama yapılıyorsa
        if term:
            sql_query += " AND (s.kod LIKE :term OR s.ad LIKE :term)"
            params['term'] = f"%{term}%"
            
        # Sıralama ve Sayfalama (Pagination)
        sql_query += " ORDER BY s.ad ASC LIMIT :limit OFFSET :offset"
        
        # Sorguyu Çalıştır
        rows = tenant_db.execute(text(sql_query), params).fetchall()
        
        results = []
        for row in rows:
            results.append({
                'id': str(row[0]),
                'text': f"{row[1]} - {row[2]} ({row[3] or 'Adet'})",
                'kod': row[1],
                'ad': row[2],
                'birim': row[3] or 'Adet',
                'fiyat': float(row[4] or 0),
                'kdv': float(row[5] or 0) # ✅ Artık stok_kdv_gruplari tablosundan geliyor!
            })
            
        has_more = len(results) == limit
        
        return jsonify({
            'results': results,
            'pagination': {'more': has_more}
        })
        
    except Exception as e:
        logger.error(f"❌ Stok arama hatası: {e}")
        return jsonify({'results': [], 'pagination': {'more': False}})

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
        
@fatura_bp.route('/api/get-cari-by-vkn/<string:vkn>')
@login_required
def api_get_cari_by_vkn(vkn):
    tenant_db = get_tenant_db()
    cari = tenant_db.query(CariHesap).filter(
        (CariHesap.vergi_no == vkn) | (CariHesap.tc_kimlik_no == vkn),
        CariHesap.firma_id == current_user.firma_id
    ).first()
    
    if cari:
        return jsonify({'id': str(cari.id), 'text': f"{cari.unvan} ({cari.kod})"})
        
@fatura_bp.route('/api/karlilik-analizi/<string:fatura_id>', methods=['GET'])
@login_required
@tenant_route
def api_karlilik_analizi(fatura_id):
    """
    Faturadaki satılan ürünlerin maliyetini bulup, satış fiyatıyla kıyaslayarak
    net kâr tutarını ve kâr marjını döndürür.
    """
    print("KARLILIK ANALİZİ")
    tenant_db = get_tenant_db()
    fatura = tenant_db.get(Fatura, str(fatura_id))
    
    if not fatura or fatura.firma_id != current_user.firma_id:
        return jsonify({'success': False, 'message': 'Fatura bulunamadı.'}), 404

    try:
        # Costing motorunu içe aktarıyoruz
        from app.modules.stok.costing import MaliyetMotoru
        from decimal import Decimal

        toplam_satis_geliri = Decimal('0.0')
        toplam_maliyet = Decimal('0.0')
        kalem_detaylari = []

        for kalem in fatura.kalemler:
            miktar = Decimal(str(kalem.miktar or 0))
            satis_fiyati = Decimal(str(kalem.birim_fiyat or 0))
            iskonto_orani = Decimal(str(kalem.iskonto_orani or 0))
            
            # İskontolu gerçek net satış fiyatını buluyoruz (KDV hariç)
            net_satis_fiyati = satis_fiyati * (1 - (iskonto_orani / 100))
            kalem_satis_geliri = miktar * net_satis_fiyati
            
            # Motorumuzdan bu ürünün ortalama maliyetini çekiyoruz
            birim_maliyet = MaliyetMotoru.ortalama_maliyet_hesapla(kalem.stok_id, fatura.tarih, fatura.firma_id)
            kalem_toplam_maliyet = miktar * birim_maliyet

            toplam_satis_geliri += kalem_satis_geliri
            toplam_maliyet += kalem_toplam_maliyet
            
            kalem_detaylari.append({
                'urun': kalem.stok.ad,
                'miktar': float(miktar),
                'net_satis_tutari': float(kalem_satis_geliri),
                'maliyet_tutari': float(kalem_toplam_maliyet),
                'kar': float(kalem_satis_geliri - kalem_toplam_maliyet)
            })

        net_kar = toplam_satis_geliri - toplam_maliyet
        kar_marji = (net_kar / toplam_satis_geliri * 100) if toplam_satis_geliri > 0 else 0

        return jsonify({
            'success': True,
            'toplam_gelir': float(toplam_satis_geliri),
            'toplam_maliyet': float(toplam_maliyet),
            'net_kar': float(net_kar),
            'kar_marji': round(float(kar_marji), 2),
            'detaylar': kalem_detaylari
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Hesaplama hatası: {str(e)}'}), 500
    return jsonify({'id': None})
    
@fatura_bp.route('/api/get-depolar', methods=['GET'])
@login_required
def api_get_depolar():
    """Şube ID'ye göre depoları getirir (Cascading Select için)"""
    sube_id = request.args.get('sube_id')
    if not sube_id:
        return jsonify([])

    tenant_db = get_tenant_db()
    depos = tenant_db.query(Depo).filter_by(sube_id=sube_id, aktif=True).order_by(Depo.ad).all()
    
    # Select2 ve JS dosyanın beklediği format: [{'id': '...', 'text': '...'}]
    result = [{'id': str(d.id), 'text': d.ad} for d in depos]
    return jsonify(result)