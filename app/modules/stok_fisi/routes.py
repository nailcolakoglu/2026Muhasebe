# app/modules/stok_fisi/routes.py

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from app.extensions import get_tenant_db
from app.modules.stok_fisi.models import StokFisi, StokFisiDetay
from app.modules.stok.models import StokHareketi, StokKart
from app.modules.firmalar.models import Donem
from app.form_builder import DataGrid
from app.enums import StokFisTuru
from .forms import create_stok_fisi_form
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
stok_fisi_bp = Blueprint('stok_fisi', __name__)

def fis_kaydet(form, fis_id=None):
    """Stok Fişi ve Hareketlerini Güvenli Bir Şekilde Veritabanına Yazar"""
    tenant_db = get_tenant_db()
    data = form.get_data()
    tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
    fis_turu_str = str(data['fis_turu'])

    # ==========================================
    # 1. MANTIKSAL KONTROLLER (VALIDATION)
    # ==========================================
    cikis = data.get('cikis_depo_id')
    giris = data.get('giris_depo_id')
    
    if fis_turu_str == StokFisTuru.TRANSFER.value:
        if not cikis or not giris:
            raise Exception("Transfer işlemi için hem Çıkış hem de Giriş deposu seçilmelidir.")
        if str(cikis) == str(giris):
            raise Exception("Transfer işleminde Kaynak ve Hedef depo aynı olamaz!")
    elif fis_turu_str in [StokFisTuru.FIRE.value, StokFisTuru.SARF.value, StokFisTuru.SAYIM_EKSIK.value] and not cikis:
        raise Exception("Çıkış işlemleri için Çıkış Deposu seçilmelidir.")
    elif fis_turu_str in [StokFisTuru.SAYIM_FAZLA.value, StokFisTuru.DEVIR.value, StokFisTuru.URETIM.value] and not giris:
        raise Exception("Giriş işlemleri için Giriş Deposu seçilmelidir.")

    # ==========================================
    # 2. CONTEXT (SESSION) DEĞERLERİ
    # ==========================================
    donem_id = session.get('aktif_donem_id')
    if not donem_id:
        ad = tenant_db.query(Donem).filter_by(firma_id=str(current_user.firma_id), aktif=True).first()
        # UUID uyumlu hale getirildi (Artık '1' değil None dönüyor)
        donem_id = str(ad.id) if ad else None
        
    sube_id = session.get('aktif_sube_id')
    if not sube_id:
        # ✨ UUID DÜZELTMESİ: Eğer şube seçilmemişse '1' yazma, veritabanından ilk şubeyi bul!
        from app.modules.sube.models import Sube
        ilk_sube = tenant_db.query(Sube).filter_by(firma_id=str(current_user.firma_id), aktif=True).first()
        sube_id = str(ilk_sube.id) if ilk_sube else None
        
    # ==========================================
    # 3. FİŞ ANA KAYDI OLUŞTURMA/GÜNCELLEME
    # ==========================================
    is_new = False
    if fis_id:
        fis = tenant_db.query(StokFisi).get(str(fis_id))
        if not fis: raise Exception("Güncellenecek fiş bulunamadı!")
    else:
        is_new = True
        fis = StokFisi(firma_id=str(current_user.firma_id))
    
    fis.donem_id = str(donem_id)
    fis.sube_id = str(sube_id)
    fis.fis_turu = fis_turu_str  
    fis.belge_no = data['belge_no']
    fis.tarih = tarih
    fis.aciklama = data['aciklama']
    
    # Depo Atamaları (İşlem Türüne Göre Akıllı Atama)
    is_cikis = fis_turu_str in [StokFisTuru.TRANSFER.value, StokFisTuru.FIRE.value, StokFisTuru.SARF.value, StokFisTuru.SAYIM_EKSIK.value]
    is_giris = fis_turu_str in [StokFisTuru.TRANSFER.value, StokFisTuru.SAYIM_FAZLA.value, StokFisTuru.DEVIR.value, StokFisTuru.URETIM.value]

    fis.cikis_depo_id = str(cikis) if is_cikis and cikis else None
    fis.giris_depo_id = str(giris) if is_giris and giris else None

    if is_new:
        tenant_db.add(fis)
        
    tenant_db.flush() # ID'nin oluşması için DB'ye gönder ama henüz commit etme
    
    # --- GÜNCELLEME İSE ESKİ HAREKETLERİ TEMİZLE ---
    if not is_new:
        tenant_db.query(StokHareketi).filter_by(kaynak_turu='stok_fisi', kaynak_id=str(fis.id)).delete()
        tenant_db.query(StokFisiDetay).filter_by(fis_id=str(fis.id)).delete()
        tenant_db.flush()

    # ==========================================
    # 3. DETAYLARI VE HAREKETLERİ İŞLEME
    # ==========================================
    stok_ids = request.form.getlist('detaylar_stok_id[]')
    miktarlar = request.form.getlist('detaylar_miktar[]')
    aciklamalar = request.form.getlist('detaylar_aciklama[]')
    
    if not stok_ids:
        raise Exception("Lütfen en az bir ürün kalemi ekleyin.")
        
    for i in range(len(stok_ids)):
        if not stok_ids[i]: continue
        
        try:
            miktar = float(miktarlar[i] or 0)
        except ValueError:
            miktar = 0
            
        if miktar <= 0: continue
        
        # Detay Satırını Ekle
        detay = StokFisiDetay(
            fis_id=str(fis.id),
            stok_id=str(stok_ids[i]),
            miktar=miktar,
            aciklama=aciklamalar[i] if i < len(aciklamalar) else ''
        )
        tenant_db.add(detay)
        tenant_db.flush() # Detay ID'si oluşsun
        
        # Mükemmel Olay Tabanlı (Event-Driven) Stok Hareketi
        # Listener'ın bu kaydı yakalayıp StokLokasyonBakiye'yi otomatik düzeltecek!
        hareket = StokHareketi(
            firma_id=str(fis.firma_id),
            donem_id=str(fis.donem_id),
            sube_id=str(fis.sube_id),
            stok_id=str(stok_ids[i]),
            cikis_depo_id=fis.cikis_depo_id, 
            giris_depo_id=fis.giris_depo_id, 
            hareket_turu=fis_turu_str,
            tarih=fis.tarih,
            miktar=miktar,
            belge_no=fis.belge_no,
            kaynak_turu='stok_fisi',
            kaynak_id=str(fis.id),
            kaynak_belge_detay_id=str(detay.id),
            aciklama=detay.aciklama or fis.aciklama or f"Stok Fişi: {fis.belge_no}",
            doviz_turu='TL' # Varsayılan
        )
        tenant_db.add(hareket)

    tenant_db.commit()


@stok_fisi_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("stok_fisi_list", StokFisi, "Depo Hareketleri")
    
    grid.add_column('tarih', 'Tarih', type='date', width='100px')
    grid.add_column('belge_no', 'Fiş No', width='150px')
    
    grid.add_column('fis_turu', 'İşlem Türü', type='badge', 
                    badge_colors={
                        'TRANSFER': 'info', 'FIRE': 'danger', 'SARF': 'warning',
                        'SAYIM_EKSIK': 'danger', 'SAYIM_FAZLA': 'success',
                        'DEVIR': 'primary', 'URETIM': 'secondary'
                    })
                    
    grid.add_column('cikis_depo.ad', 'Çıkış Deposu')
    grid.add_column('giris_depo.ad', 'Giriş Deposu')
    grid.add_column('aciklama', 'Açıklama')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'stok_fisi.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'stok_fisi.sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sube_id', 'donem_id', 'giris_depo_id', 'cikis_depo_id',
        'created_at', 'updated_at', 'deleted_at', 
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)
    
    # ✨ DATA SCOPING DEVREDE: DataGrid arka planda şubeye göre filtrelemeyi kendi yapacak!
    query = tenant_db.query(StokFisi).filter_by(firma_id=str(current_user.firma_id)).order_by(StokFisi.tarih.desc())
    grid.process_query(query)
    
    return render_template('stok_fisi/index.html', grid=grid)

@stok_fisi_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_stok_fisi_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db()
            try:
                fis_kaydet(form)
                return jsonify({'success': True, 'message': 'Fiş başarıyla kaydedildi.', 'redirect': '/stok-fisi/'})
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"Fiş Kayıt Hatası: {str(e)}")
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('stok_fisi/form.html', form=form)

@stok_fisi_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    fis = tenant_db.query(StokFisi).get(str(id))
    if not fis: 
        return "Fiş bulunamadı", 404
    
    form = create_stok_fisi_form(fis)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                fis_kaydet(form, fis_id=str(id))
                return jsonify({'success': True, 'message': 'Fiş başarıyla güncellendi.', 'redirect': '/stok-fisi/'})
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"Fiş Güncelleme Hatası: {str(e)}")
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('stok_fisi/form.html', form=form)

@stok_fisi_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    try:
        fis = tenant_db.query(StokFisi).get(str(id))
        if not fis: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404
        
        # Sildiğimiz an, stok_hareket tablosundaki after_delete (listener) tetiklenip stokları eski haline döndürecektir.
        tenant_db.query(StokHareketi).filter_by(kaynak_turu='stok_fisi', kaynak_id=str(fis.id)).delete()
        tenant_db.query(StokFisiDetay).filter_by(fis_id=str(fis.id)).delete()
        tenant_db.delete(fis)
        
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Fiş silindi ve stoklar otomatik geri alındı.'})
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"Fiş Silme Hatası: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@stok_fisi_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    try:
        from app.models import Sayac
        sayac = tenant_db.query(Sayac).filter_by(
            firma_id=str(current_user.firma_id),
            kod='STOK_FISI',
            donem_yili=datetime.now().year
        ).first()
        
        son_no = sayac.son_no if sayac else 0
        siradaki = son_no + 1
        return jsonify({'code': f"SF-{str(siradaki).zfill(6)}"})
        
    except Exception:
        try:
            son_islem = tenant_db.query(StokFisi).filter_by(
                firma_id=str(current_user.firma_id)
            ).order_by(StokFisi.tarih.desc(), StokFisi.id.desc()).first()
            
            if son_islem and son_islem.belge_no and '-' in son_islem.belge_no:
                parcalar = son_islem.belge_no.rsplit('-', 1)
                if len(parcalar) == 2 and parcalar[1].isdigit():
                    yeni_num = str(int(parcalar[1]) + 1).zfill(len(parcalar[1]))
                    return jsonify({'code': f"{parcalar[0]}-{yeni_num}"})
        except: pass
            
        return jsonify({'code': 'SF-000001'})