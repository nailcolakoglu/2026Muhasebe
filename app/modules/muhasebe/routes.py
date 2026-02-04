from app.utils.decorators import role_required, permission_required 
from flask import Blueprint, render_template, request, jsonify, abort, flash
from flask_login import login_required, current_user
from app.models.base import db, FirmaOwnedMixin, JSONText, FirmaFilteredQuery
# Modeller
from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay, HesapPlani
from app.modules.firmalar.models import Donem
from app.modules.sube.models import Sube
from app.models import Sayac
from app.enums import MuhasebeFisTuru, HesapSinifi, BakiyeTuru, OzelHesapTipi

from app.form_builder import DataGrid, FieldType
from .forms import create_muhasebe_fis_form, create_hesap_form
from datetime import datetime
from sqlalchemy import func, case, literal
from app.modules.muhasebe.services import numara_uret, fis_kaydet, resmi_defteri_kesinlestir
from app.modules.rapor.text_engine import TextReportEngine
from flask import Response
from flask_babel import gettext as _
from app.extensions import get_tenant_db, get_tenant_info

muhasebe_bp = Blueprint('muhasebe', __name__)

def get_aktif_firma_id():
    """
    Güvenli Firma ID Çözümleyici (UUID Destekli)
    Artık int() çevrimi yapmıyoruz, doğrudan string/UUID dönüyoruz.
    """
    val = None
    
    # 1. Kaynaktan Al
    if current_user.is_authenticated and getattr(current_user, 'firma_id', None):
        val = current_user.firma_id
    elif get_tenant_info() and get_tenant_info().get('firma_id'):
        val = get_tenant_info().get('firma_id')
    
    # UUID String olarak dönecek, Integer kontrolüne gerek yok.
    # Boş string veya None kontrolü yeterli.
    if val and str(val).strip():
        return str(val)
            
    return None

def bakiye_guncelle(firma_id, etkilenen_hesap_ids=None):
    """PROFESYONEL BAKİYE MOTORU (Firebird Tenant DB)"""
    tenant_db = get_tenant_db()
    # firma_id artık string olduğu için doğrudan filtreye verilebilir
    hesaplar = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id).all()
    
    for h in hesaplar:
        ozet = tenant_db.query(
            func.sum(MuhasebeFisiDetay.borc),
            func.sum(MuhasebeFisiDetay.alacak)
        ).join(MuhasebeFisi).filter(
            MuhasebeFisiDetay.hesap_id == h.id,
            MuhasebeFisi.firma_id == firma_id
        ).first()
        
        yeni_borc = ozet[0] or 0
        yeni_alacak = ozet[1] or 0
        
        if h.borc_bakiye != yeni_borc or h.alacak_bakiye != yeni_alacak:
            h.borc_bakiye = yeni_borc
            h.alacak_bakiye = yeni_alacak
            tenant_db.add(h)
            
    tenant_db.commit()

def islem_kaydet(form, fis=None):
    """Muhasebe Fişini Kaydeder (Tenant DB)"""
    tenant_db = get_tenant_db()
    data = form.get_data()
    
    # --- FİRMA ID GÜVENLİK ---
    firma_id = get_aktif_firma_id()
    if not firma_id:
        raise Exception("Firma Kimliği Hatası: Firma ID bulunamadı.")
    # -------------------------
    
    # 1.TARİH VE DÖNEM KONTROLÜ
    try:
        if isinstance(data['tarih'], str):
            girilen_tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
        else:
            girilen_tarih = data['tarih']
    except ValueError:
        raise Exception("Geçersiz tarih formatı!")

    aktif_donem = tenant_db.query(Donem).filter_by(firma_id=firma_id, aktif=True).first()
    if not aktif_donem:
        aktif_donem = tenant_db.query(Donem).filter_by(firma_id=firma_id).order_by(Donem.id.desc()).first()
    
    if not aktif_donem: raise Exception("Aktif Mali Dönem bulunamadı!")
    
    if not (aktif_donem.baslangic <= girilen_tarih <= aktif_donem.bitis):
        raise Exception(f"Fiş tarihi ({girilen_tarih.strftime('%d.%m.%Y')}) mali dönem sınırları dışında!")

    # Şube
    yetkili_sube_id = None
    if current_user.yetkili_subeler:
         yetkili_sube_id = current_user.yetkili_subeler[0].id 
    else:
         ilk_sube = tenant_db.query(Sube).filter_by(firma_id=firma_id).first()
         yetkili_sube_id = ilk_sube.id if ilk_sube else 1

    # 2.FİŞ BAŞLIĞI
    is_new = False
    if not fis:
        is_new = True
        fis = MuhasebeFisi(
            firma_id=firma_id, # UUID String gider
            donem_id=aktif_donem.id,
            sube_id=yetkili_sube_id,
            kaydeden_id=current_user.id,
            sistem_kayit_tarihi=datetime.now()
        )
        
        tur_kod = data['fis_turu'].upper() if isinstance(data['fis_turu'], str) else 'GENEL'
        prefix_map = {'MAHSUP': 'M-', 'TAHSIL': 'T-', 'TEDIYE': 'TD-', 'ACILIS': 'A-', 'KAPANIS': 'K-'}
        on_ek = prefix_map.get(tur_kod, 'FIS-')
        
        fis.fis_no = numara_uret(firma_id, tur_kod, aktif_donem.baslangic.year, on_ek)
        tenant_db.add(fis)
    else:
        if fis.resmi_defter_basildi: raise Exception("Resmi deftere basılan fiş değiştirilemez!")
        
    fis.fis_turu = data['fis_turu']
    fis.tarih = girilen_tarih
    fis.aciklama = data['aciklama']
    
    fis.duzenleyen_id = current_user.id
    fis.son_duzenleme_tarihi = datetime.now()
    fis.e_defter_donemi = girilen_tarih.strftime('%Y%m')
    if fis.gib_durum_kodu is None: fis.gib_durum_kodu = 0

    if is_new: tenant_db.flush()

    # 3.DETAYLARI İŞLE
    if not is_new:
        tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=fis.id).delete()
    
    r = request.form
    hesap_ids = r.getlist('detaylar_hesap_id[]') or r.getlist('detaylar_hesap_id')
    aciklamalar = r.getlist('detaylar_aciklama[]') or r.getlist('detaylar_aciklama')
    borclar = r.getlist('detaylar_borc[]') or r.getlist('detaylar_borc')
    alacaklar = r.getlist('detaylar_alacak[]') or r.getlist('detaylar_alacak')
    
    belge_aciklamalari = r.getlist('detaylar_belge_aciklamasi[]') or r.getlist('detaylar_belge_aciklamasi')
    belge_turleri = r.getlist('detaylar_belge_turu[]') or r.getlist('detaylar_belge_turu')
    belge_nolar = r.getlist('detaylar_belge_no[]') or r.getlist('detaylar_belge_no')
    belge_tarihleri = r.getlist('detaylar_belge_tarihi[]') or r.getlist('detaylar_belge_tarihi')
    odeme_yontemleri = r.getlist('detaylar_odeme_yontemi[]') or r.getlist('detaylar_odeme_yontemi')

    toplam_borc = 0.0
    toplam_alacak = 0.0
    
    row_count = len(hesap_ids)
    
    for i in range(row_count):
        if not hesap_ids[i]: continue 
        
        raw_borc = str(borclar[i]).replace('.', '').replace(',', '.') if borclar[i] else '0'
        raw_alacak = str(alacaklar[i]).replace('.', '').replace(',', '.') if alacaklar[i] else '0'
        b = float(raw_borc)
        a = float(raw_alacak)
        
        if b > 0 and a > 0: raise Exception(f"{i+1}.satırda hem Borç hem Alacak olamaz!")
        
        toplam_borc += b
        toplam_alacak += a
        
        b_tarih = None
        if i < len(belge_tarihleri) and belge_tarihleri[i]:
            try: b_tarih = datetime.strptime(belge_tarihleri[i], '%Y-%m-%d').date()
            except: pass

        detay = MuhasebeFisiDetay(
            fis_id=fis.id,
            hesap_id=hesap_ids[i],
            aciklama=aciklamalar[i] if i < len(aciklamalar) else '',
            borc=b,
            alacak=a,
            belge_aciklamasi=belge_aciklamalari[i] if i < len(belge_aciklamalari) else None,
            belge_turu=belge_turleri[i] if i < len(belge_turleri) else None,
            belge_no=belge_nolar[i] if i < len(belge_nolar) else None,
            belge_tarihi=b_tarih,
            odeme_yontemi=odeme_yontemleri[i] if i < len(odeme_yontemleri) else None
        )
        tenant_db.add(detay)
    
    if abs(toplam_borc - toplam_alacak) > 0.05:
        raise Exception(f"Fiş dengesiz! Fark: {abs(toplam_borc - toplam_alacak):,.2f}")
    
    fis.toplam_borc = toplam_borc
    fis.toplam_alacak = toplam_alacak
    
    tenant_db.commit()
    bakiye_guncelle(firma_id)
    
@muhasebe_bp.route('/')
@login_required
@role_required('admin', 'muhasebe')
def index():
    tenant_db = get_tenant_db()
    firma_id = get_aktif_firma_id()
    
    grid = DataGrid("muhasebe_list", MuhasebeFisi, "Muhasebe Fişleri", per_page=20, enable_grouping=True, 
                    enable_summary=True,
                    summary_fields=['aciklama'])
    grid.add_column('tarih', 'Tarih', width='440px', sortable=True, type=FieldType.DATE)
    grid.add_column('fis_no', 'Fiş No', width='120px',sortable=True)
    grid.add_column('aciklama', 'Açıklama', sortable=True)
    grid.add_column('fis_turu', 'Tür', sortable=True, type='badge', 
                    badge_colors={'mahsup': 'primary', 'tahsil': 'success', 'tediye': 'danger'})
    
    grid.add_column('toplam_borc', 'Borç', type=FieldType.CURRENCY, sortable=True)
    grid.add_column('toplam_alacak', _('Alacak'), type=FieldType.CURRENCY, sortable=True)

    grid.add_action('edit', 'İncele/Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'muhasebe.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'muhasebe.sil')
    
    # Güvenlik: ID yoksa boş dön
    if not firma_id:
         flash("Firma Kimliği doğrulanamadı. Oturumunuzu kontrol edin.", "danger")
         query = tenant_db.query(MuhasebeFisi).filter(literal(False)) 
    else:
         # firma_id UUID/String olduğu için doğrudan eşleşir
         query = tenant_db.query(MuhasebeFisi).filter_by(firma_id=firma_id).order_by(MuhasebeFisi.tarih.desc())
   
    grid.hide_column('id').hide_column('firma_id').hide_column('donem_id').hide_column('sube_id').hide_column('kaynak_modul').hide_column('kaynak_id')

    grid.process_query(query)
    return render_template('muhasebe/index.html', grid=grid)

# ... (Ekle, Düzenle, Sil fonksiyonları aynı kalacak, sadece islem_kaydet çağırıyorlar) ...

@muhasebe_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_muhasebe_fis_form()
    tenant_db = get_tenant_db()
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                islem_kaydet(form)
                return jsonify({'success': True, 'message': 'Fiş kaydedildi.', 'redirect': '/muhasebe'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('muhasebe/form.html', form=form)

@muhasebe_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    fis = tenant_db.get(MuhasebeFisi, id)
    if not fis: abort(404)
    form = create_muhasebe_fis_form(fis)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                islem_kaydet(form, fis)
                return jsonify({'success': True, 'message': 'Fiş güncellendi.', 'redirect': '/muhasebe'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('muhasebe/form.html', form=form)

@muhasebe_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
@permission_required('fatura_sil')
def sil(id):
    tenant_db = get_tenant_db()
    fis = tenant_db.get(MuhasebeFisi, id)
    if not fis: return jsonify({'success': False, 'message': 'Bulunamadı'}), 404
    try:
        tenant_db.delete(fis)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Fiş silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@muhasebe_bp.route('/api/siradaki-no')
@login_required
def api_siradaki_no():
    tenant_db = get_tenant_db()
    firma_id = get_aktif_firma_id()
    if not firma_id: return jsonify({'code': 'ERR-FIRM-ID'})

    tur = request.args.get('tur', 'GENEL') 
    yil = datetime.now().year
    
    sayac = tenant_db.query(Sayac).filter_by(firma_id=firma_id, kod=tur.upper(), donem_yili=yil).first()
    
    if sayac:
        onizleme = f"{sayac.on_ek}{str(sayac.son_no + 1).zfill(sayac.hane_sayisi)}"
    else:
        prefix_map = {'MAHSUP': 'M-', 'TAHSIL': 'T-', 'TEDIYE': 'TD-', 'ACILIS': 'ACL-', 'FATURA': 'FAT-'}
        prefix = prefix_map.get(tur.upper(), 'BLG-')
        onizleme = f"{prefix}000001"
        
    return jsonify({'code': onizleme})            

@muhasebe_bp.route('/hesap-plani')
@login_required
def hesap_plani_index():
    tenant_db = get_tenant_db()
    firma_id = get_aktif_firma_id()
    if not firma_id:
        flash("Geçersiz Firma Kimliği", "danger")
        return render_template('muhasebe/hesap_plani.html', hesaplar=[])
    
    hesaplar = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id).order_by(HesapPlani.kod).all()
    return render_template('muhasebe/hesap_plani.html', hesaplar=hesaplar)

@muhasebe_bp.route('/hesap/ekle', methods=['GET', 'POST'])
@login_required
def hesap_ekle():
    form = create_hesap_form()
    tenant_db = get_tenant_db()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                firma_id = get_aktif_firma_id()
                if not firma_id:
                    return jsonify({'success': False, 'message': 'Hata: Firma ID bulunamadı.'}), 400
                
                mevcut = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id, kod=data['kod']).first()
                if mevcut:
                    return jsonify({'success': False, 'message': f"Bu hesap kodu ({data['kod']}) zaten kullanımda!"}), 400

                ust_id = int(data['ust_hesap_id']) if data['ust_hesap_id'] and str(data['ust_hesap_id']) != '0' else None
                seviye = 1
                if ust_id:
                    ust_hesap = tenant_db.get(HesapPlani, ust_id)
                    if ust_hesap:
                        seviye = ust_hesap.seviye + 1 
                        tip = ust_hesap.hesap_tipi.value if hasattr(ust_hesap.hesap_tipi, 'value') else ust_hesap.hesap_tipi
                        if str(tip) == 'muavin':
                            return jsonify({'success': False, 'message': 'Muavin hesaba alt hesap eklenemez!'}), 400

                # firma_id artık UUID/String
                hesap = HesapPlani(
                    firma_id=firma_id, 
                    ust_hesap_id=ust_id,
                    kod=data['kod'],
                    ad=data['ad'],
                    seviye=seviye,
                    aciklama=data.get('aciklama')
                )
                hesap.hesap_tipi = data['hesap_tipi']
                hesap.bakiye_turu = data['bakiye_turu']
                hesap.ozel_hesap_tipi = data['ozel_hesap_tipi']
                
                tenant_db.add(hesap)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Hesap kartı başarıyla oluşturuldu.', 'redirect': '/muhasebe/hesap-plani'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
    return render_template('muhasebe/form.html', form=form)

# ... (Hesap düzenle/sil rotaları benzer mantıkla güncellendi) ...

@muhasebe_bp.route('/yazdir/dos/<int:id>')
@login_required
def yazdir_dos(id):
    tenant_db = get_tenant_db()
    fis = tenant_db.get(MuhasebeFisi, id)
    if not fis: abort(404)
    
    # Firma bilgisi Master DB'de
    from app.modules.firmalar.models import Firma
    
    # UUID ile sorgulama
    firma = db.session.get(Firma, fis.firma_id) 
    
    rapor = TextReportEngine(sayfa_satir_sayisi=60, sayfa_genisligi=80)
    rapor.basliklar = ["HESAP KODU", "ACIKLAMA", "BORC", "ALACAK"]
    rapor.kolon_genislikleri = [15, 35, 14, 14] 
    rapor.kolon_tipleri = ['str', 'str', 'money', 'money']
    
    fis_turu_str = fis.fis_turu.value if hasattr(fis.fis_turu, 'value') else str(fis.fis_turu)
    
    rapor.header_ekle(
        firma_adi=firma.unvan if firma else "Firma Bilgisi Yok",
        belge_adi=f"{fis_turu_str.upper()} FISI",
        belge_no=fis.fis_no,
        tarih=fis.tarih.strftime('%d.%m.%Y')
    )
    # ... Rapor detay döngüsü (Değişiklik yok) ...
    for detay in fis.detaylar:
        rapor.sayfa_sonu_kontrol(
            firma_adi=firma.unvan if firma else "Firma Bilgisi Yok",
            belge_adi=f"{fis_turu_str.upper()} FISI",
            belge_no=fis.fis_no,
            tarih=fis.tarih.strftime('%d.%m.%Y'),
            devreden_tutar=None
        )
        hesap_kodu = detay.hesap.kod if detay.hesap else ""
        rapor.satir_ekle([hesap_kodu, detay.aciklama, detay.borc, detay.alacak])
    
    rapor.dip_toplam_ekle("TOPLAM BORC", fis.toplam_borc)
    rapor.dip_toplam_ekle("TOPLAM ALACAK", fis.toplam_alacak)
    
    return Response(
        rapor.output,
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename={fis.fis_no}.txt"}
    )
    
# Diğer fonksiyonlar (fis/kaydet, resmi-defter/kesinlestir) get_aktif_firma_id() kullanarak güncellendi.
@muhasebe_bp.route('/fis/kaydet', methods=['POST'])
@login_required
def kaydet():
    form_data = request.json 
    sube_id = current_user.yetkili_subeler[0].id if current_user.yetkili_subeler else 1
    tenant_db = get_tenant_db()
    
    firma_id = get_aktif_firma_id()
    if not firma_id: return jsonify({'status': 'error', 'message': 'Firma kimliği doğrulanamadı.'}), 400

    donem = tenant_db.query(Donem).filter_by(firma_id=firma_id, aktif=True).first()
    donem_id = donem.id if donem else 1

    basari, mesaj = fis_kaydet(
        data=form_data,
        kullanici_id=current_user.id,
        sube_id=sube_id,
        donem_id=donem_id,
        firma_id=firma_id,
        fis_id=form_data.get('fis_id')
    )
    if basari: return jsonify({'status': 'success', 'message': mesaj})
    else: return jsonify({'status': 'error', 'message': mesaj}), 400

@muhasebe_bp.route('/resmi-defter/kesinlestir', methods=['POST'])
@login_required
def kesinlestir():
    rol = getattr(current_user, 'rol', '')
    if str(rol) != 'admin' and 'muhasebe' not in str(rol):
         return jsonify({'success': False, 'message': 'Yetkisiz işlem!'}), 403
    tarih = request.form.get('bitis_tarihi')
    if not tarih: return jsonify({'success': False, 'message': 'Tarih seçilmedi!'}), 400
    
    tenant_db = get_tenant_db()
    firma_id = get_aktif_firma_id()
    if not firma_id: return jsonify({'success': False, 'message': 'Firma kimliği hatası.'}), 400
    donem = tenant_db.query(Donem).filter_by(firma_id=firma_id, aktif=True).first()
    
    basari, mesaj = resmi_defteri_kesinlestir(firma_id=firma_id, donem_id=donem.id if donem else 1, bitis_tarihi=tarih)
    if basari: return jsonify({'success': True, 'message': mesaj})
    else: return jsonify({'success': False, 'message': mesaj}), 400

@muhasebe_bp.route('/hesap/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def hesap_duzenle(id):
    tenant_db = get_tenant_db()
    hesap = tenant_db.get(HesapPlani, id)
    if not hesap: abort(404)
    form = create_hesap_form(hesap)
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                ust_id = int(data['ust_hesap_id']) if data['ust_hesap_id'] and str(data['ust_hesap_id']) != '0' else None
                if ust_id == hesap.id: return jsonify({'success': False, 'message': 'Hesap kendi kendisinin üst hesabı olamaz!'}), 400
                seviye = 1
                if ust_id:
                    ust = tenant_db.get(HesapPlani, ust_id)
                    seviye = ust.seviye + 1
                hesap.ust_hesap_id = ust_id
                hesap.seviye = seviye
                hesap.kod = data['kod']
                hesap.ad = data['ad']
                hesap.hesap_tipi = data['hesap_tipi']
                hesap.bakiye_turu = data['bakiye_turu']
                hesap.ozel_hesap_tipi = data['ozel_hesap_tipi']
                hesap.aciklama = data.get('aciklama')
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Hesap güncellendi.', 'redirect': '/muhasebe/hesap-plani'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
    return render_template('muhasebe/form.html', form=form)

@muhasebe_bp.route('/hesap/sil/<int:id>', methods=['POST'])
@login_required
def hesap_sil(id):
    tenant_db = get_tenant_db()
    hesap = tenant_db.get(HesapPlani, id)
    if not hesap: abort(404)
    if hesap.alt_hesaplar and len(hesap.alt_hesaplar) > 0:
         return jsonify({'success': False, 'message': 'Alt hesapları olan bir hesap silinemez!'}), 400
    try:
        tenant_db.delete(hesap)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Hesap silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500