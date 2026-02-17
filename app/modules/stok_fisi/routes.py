from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.modules.stok_fisi.models import StokFisi, StokFisiDetay
from app.modules.stok.models import StokHareketi, StokDepoDurumu
from app.modules.depo.models import Depo
from app.form_builder import DataGrid
from app.enums import StokFisTuru
from .forms import create_stok_fisi_form
from datetime import datetime

stok_fisi_bp = Blueprint('stok_fisi', __name__)

# --- STOK GÜNCELLEME YARDIMCISI ---
def stok_guncelle(firma_id, depo_id, stok_id, miktar_degisimi):
    """
    StokDepo tablosundaki anlık miktarı günceller.
    miktar_degisimi: Pozitif ise artırır, Negatif ise azaltır.
    """
    if not depo_id: return

    kayit = StokDepoDurumu.query.filter_by(depo_id=depo_id, stok_id=stok_id).first()
    
    if not kayit:
        # Kayıt yoksa oluştur
        kayit = StokDepoDurumu(firma_id=firma_id, depo_id=depo_id, stok_id=stok_id, miktar=0)
        db.session.add(kayit)
    
    kayit.miktar = float(kayit.miktar) + float(miktar_degisimi)
    db.session.add(kayit)

def fis_hareketlerini_isle(fis, is_delete=False):
    """
    Fiş detaylarına göre Stok Hareketlerini oluşturur ve StokDepo'yu günceller.
    is_delete=True ise yapılan işlemleri geri alır (ters kayıt).
    """
    # Önce bu fişe ait eski hareketleri temizle (Silme veya Güncelleme durumunda)
    # Ancak StokHareketi tablosunda 'kaynak_belge_id' gibi bir alanımız yoksa manuel temizlemeliyiz.
    # Bu örnekte StokHareketi tablosu tarihçe içindir, doğrudan silinmesi önerilmez ama
    # güncelleme anında bakiyeyi düzeltmek için ters işlem yapacağız.
    
    pass # Bu fonksiyonun içi aşağıda detaylı yazıldı

def fis_kaydet(form, fis=None):
    data = form.get_data()
    tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
    # String gelen veriyi Enum objesine çeviriyoruz
    fis_turu_enum = StokFisTuru(data['fis_turu'])

    # --- TRANSFER KONTROLÜ ---
    if fis_turu_enum == StokFisTuru.TRANSFER:
        cikis = data.get('cikis_depo_id')
        giris = data.get('giris_depo_id')
        
        if not cikis or not giris:
            raise Exception("Transfer işlemi için hem Çıkış hem de Giriş deposu seçilmelidir.")
            
        if str(cikis) == str(giris):
            raise Exception("Transfer işleminde Kaynak ve Hedef depo aynı olamaz!")

    # --- ÖNCE GEREKLİ ID'LERİ HAZIRLA (Autoflush Hatasını Önlemek İçin) ---
    # Aktif dönem ve şubeyi güvenli şekilde alalım
    aktif_donem = current_user.firma.donemler[-1] if current_user.firma.donemler else None
    if not aktif_donem:
        raise Exception("Firmaya ait aktif bir dönem bulunamadı!")
        
    aktif_sube = current_user.yetkili_subeler[0] if current_user.yetkili_subeler else None
    if not aktif_sube:
        raise Exception("Yetkili olduğunuz bir şube bulunamadı!")

    is_new = False
    if not fis:
        is_new = True
        # Nesneyi oluşturuyoruz ama henüz session.add yapmıyoruz!
        fis = StokFisi(firma_id=current_user.firma_id)
    
    # --- DEĞERLERİ ATA ---
    fis.donem_id = aktif_donem.id
    fis.sube_id = aktif_sube.id
    fis.fis_turu = fis_turu_enum  # Enum olarak atıyoruz
    fis.belge_no = data['belge_no']
    fis.tarih = tarih
    fis.aciklama = data['aciklama']
    
    # Depo Atamaları
    if fis_turu_enum in [StokFisTuru.TRANSFER, StokFisTuru.FIRE, StokFisTuru.SARF, StokFisTuru.SAYIM_EKSIK]:
        fis.cikis_depo_id = data.get('cikis_depo_id') or None
    else:
        fis.cikis_depo_id = None
        
    if fis_turu_enum in [StokFisTuru.TRANSFER, StokFisTuru.SAYIM_FAZLA, StokFisTuru.DEVIR, StokFisTuru.URETIM]:
        fis.giris_depo_id = data.get('giris_depo_id') or None
    else:
        fis.giris_depo_id = None

    # --- ŞİMDİ SESSION'A EKLE (Tüm veriler dolu) ---
    if is_new:
        db.session.add(fis)
        
    db.session.flush() # Artık ID oluştu ve hata almaz
    
    # --- ESKİ DETAYLARI TEMİZLE (Güncelleme ise) ---
    if not is_new:
        old_detaylar = StokFisiDetay.query.filter_by(fis_id=fis.id).all()
        for old in old_detaylar:
            # Bakiyeleri ters işlemle düzelt
            if fis.cikis_depo_id:
                stok_guncelle(fis.firma_id, fis.cikis_depo_id, old.stok_id, +float(old.miktar))
            if fis.giris_depo_id:
                stok_guncelle(fis.firma_id, fis.giris_depo_id, old.stok_id, -float(old.miktar))
            
            # Eski hareketleri sil
            StokHareketi.query.filter_by(
                firma_id=fis.firma_id, 
                stok_id=old.stok_id,
                aciklama=f"Fiş Detay: {fis.belge_no}" # Burayı ID bazlı yapmak daha güvenlidir ilerde
            ).delete()
            
        StokFisiDetay.query.filter_by(fis_id=fis.id).delete()

    # --- YENİ DETAYLARI İŞLE ---
    stok_ids = request.form.getlist('detaylar_stok_id[]')
    miktarlar = request.form.getlist('detaylar_miktar[]')
    aciklamalar = request.form.getlist('detaylar_aciklama[]')
    
    for i in range(len(stok_ids)):
        if not stok_ids[i]: continue
        
        miktar = float(miktarlar[i] or 0)
        if miktar <= 0: continue
        
        # Detay Ekle
        detay = StokFisiDetay(
            fis_id=fis.id,
            stok_id=stok_ids[i],
            miktar=miktar,
            aciklama=aciklamalar[i]
        )
        db.session.add(detay)
        
        # --- STOK HAREKETLERİ (Burada Transfer için ÇİFT KAYIT oluşturuyoruz) ---
        # Böylece "Stok Hareket Geçmişi"nde hem giren depoda hem çıkan depoda görebilirsin.
        
        # 1.ÇIKIŞ HAREKETİ (Varsa)
        if fis.cikis_depo_id:
            h_cikis = StokHareketi(
                firma_id=fis.firma_id,
                donem_id=fis.donem_id,
                sube_id=fis.sube_id,
                stok_id=stok_ids[i],
                cikis_depo_id=fis.cikis_depo_id, # Hangi depodan
                hareket_turu=fis_turu_enum,
                #yon=-1, # Eksi Yön
                tarih=fis.tarih,
                miktar=miktar,
                belge_no=fis.belge_no,
                kaynak_turu='stok_fisi',
                kaynak_id=fis.id,
                aciklama=f"Çıkış: {fis.aciklama}" if fis.aciklama else f"Fiş: {fis.belge_no}",
                doviz_turu='TL'
            )
            db.session.add(h_cikis)
            stok_guncelle(fis.firma_id, fis.cikis_depo_id, stok_ids[i], -miktar)

        # 2.GİRİŞ HAREKETİ (Varsa)
        if fis.giris_depo_id:
            h_giris = StokHareketi(
                firma_id=fis.firma_id,
                donem_id=fis.donem_id,
                sube_id=fis.sube_id,
                stok_id=stok_ids[i],
                giris_depo_id=fis.giris_depo_id, # Hangi depoya
                hareket_turu=fis_turu_enum,
                #yon=1, # Artı Yön
                tarih=fis.tarih,
                miktar=miktar,
                belge_no=fis.belge_no,
                kaynak_turu='stok_fisi',
                kaynak_id=fis.id,
                aciklama=f"Giriş: {fis.aciklama}" if fis.aciklama else f"Fiş: {fis.belge_no}",
                doviz_turu='TL'
            )
            db.session.add(h_giris)
            stok_guncelle(fis.firma_id, fis.giris_depo_id, stok_ids[i], +miktar)

    db.session.commit()

@stok_fisi_bp.route('/')
@login_required
def index():
    grid = DataGrid("stok_fisi_list", StokFisi, "Depo Hareketleri")
    
    grid.add_column('tarih', 'Tarih', type='date', width='100px')
    grid.add_column('belge_no', 'Fiş No')
    
    grid.add_column('fis_turu', 'İşlem Türü', type='badge', 
                    badge_colors={
                        'transfer': 'info', 'fire': 'danger', 'sarf': 'warning',
                        'sayim_eksik': 'danger', 'sayim_fazla': 'success',
                        'devir': 'primary', 'uretim': 'secondary'
                    })
                    
    grid.add_column('cikis_depo.ad', 'Çıkış Deposu')
    grid.add_column('giris_depo.ad', 'Giriş Deposu')
    grid.add_column('aciklama', 'Açıklama')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'stok_fisi.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'stok_fisi.sil')
    
    query = StokFisi.query.filter_by(firma_id=current_user.firma_id).order_by(StokFisi.tarih.desc())
    grid.process_query(query)
    
    return render_template('stok_fisi/index.html', grid=grid)

@stok_fisi_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_stok_fisi_form()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                fis_kaydet(form)
                return jsonify({'success': True, 'message': 'Fiş kaydedildi.', 'redirect': '/stok-fisi'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('stok_fisi/form.html', form=form)

@stok_fisi_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    fis = StokFisi.query.get_or_404(id)
    form = create_stok_fisi_form(fis)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                fis_kaydet(form, fis)
                return jsonify({'success': True, 'message': 'Fiş güncellendi.', 'redirect': '/stok-fisi'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('stok_fisi/form.html', form=form)

@stok_fisi_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    fis = StokFisi.query.get_or_404(id)
    try:
        # Silmeden önce bakiyeleri geri al (Ters İşlem)
        for detay in fis.detaylar:
            if fis.cikis_depo_id:
                stok_guncelle(fis.firma_id, fis.cikis_depo_id, detay.stok_id, +float(detay.miktar))
            if fis.giris_depo_id:
                stok_guncelle(fis.firma_id, fis.giris_depo_id, detay.stok_id, -float(detay.miktar))
        
        # Hareketleri de temizle
        StokHareketi.query.filter(
            StokHareketi.aciklama.like(f"%{fis.belge_no}%"), 
            StokHareketi.tarih == fis.tarih
        ).delete(synchronize_session=False)

        db.session.delete(fis)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Fiş silindi ve stoklar geri alındı.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@stok_fisi_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    son = StokFisi.query.filter_by(firma_id=current_user.firma_id).count()
    return jsonify({'code': f"FIS-{str(son+1).zfill(5)}"})