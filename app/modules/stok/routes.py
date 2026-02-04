# app/modules/stok/routes.py

import os
import re
from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify, current_app, url_for, redirect, flash, session, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

# Modeller
from app.modules.stok.models import StokKart, StokPaketIcerigi, StokDepoDurumu, StokMuhasebeGrubu, StokKDVGrubu, StokHareketi
from app.modules.kategori.models import StokKategori
from app.modules.stok_fisi.models import StokFisi
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.models import AIRaporGecmisi, AIRaporAyarlari
from app.modules.depo.models import Depo
from app.modules.sube.models import Sube

# Formlar ve Araçlar
from app.form_builder import DataGrid, FieldType
from .forms import create_stok_form, get_muhasebe_grup_form, get_kdv_grup_form, create_ai_settings_form, create_paket_icerik_form
from sqlalchemy import func, extract, literal
from app.form_builder.ai_generator import analyze_stock_trends, analyze_cross_sell, analyze_dead_stock
import json
from datetime import datetime, timedelta
from app.enums import StokKartTipi, FaturaTuru
from flask_babel import gettext as _
from app.araclar import para_cevir
from app.extensions import get_tenant_db # db importuna gerek kalmadı (sadece tip için durabilir)

stok_bp = Blueprint('stok', __name__)

# GEÇİCİ SONRA SİLİNECEK (BAKIM SCRIPTI)
@stok_bp.route('/yonetim/bakiyeleri-duzelt')
@login_required
def bakiyeleri_duzelt():
    """
    Acil Durum Butonu: Tüm Stok Hareketlerini tarar ve Depo Mevcutlarını sıfırdan hesaplar.
    Veritabanı: Tenant DB (Firebird)
    """
    tenant_db = get_tenant_db()
    
    try:
        # 1. Mevcut Hatalı Depo Durumlarını SIFIRLA (Temiz Sayfa)
        # Sadece o firmaya ait kayıtları sil
        tenant_db.query(StokDepoDurumu).filter_by(firma_id=current_user.firma_id).delete()
        tenant_db.flush()
        
        # 2. Tüm Hareketleri Çek
        hareketler = tenant_db.query(StokHareketi).filter_by(firma_id=current_user.firma_id).all()
        
        # 3. Hafızada Hesapla
        # Yapı: {(depo_id, stok_id): miktar}
        depo_stok_map = {} 
        
        for h in hareketler:
            try:
                miktar = float(h.miktar or 0)
                
                # A) GİRİŞ DEPOSU VARSA (Stok Artar)
                if h.giris_depo_id:
                    key = (h.giris_depo_id, h.stok_id)
                    depo_stok_map[key] = depo_stok_map.get(key, 0) + miktar
                    
                # B) ÇIKIŞ DEPOSU VARSA (Stok Azalır)
                if h.cikis_depo_id:
                    key = (h.cikis_depo_id, h.stok_id)
                    depo_stok_map[key] = depo_stok_map.get(key, 0) - miktar
            except:
                continue # Hatalı kaydı atla
        
        # 4. Veritabanına Temiz Veriyi Yaz
        sayac = 0
        for (depo_id, stok_id), miktar in depo_stok_map.items():
            if miktar != 0: # 0 olanları yazmaya gerek yok
                yeni_kayit = StokDepoDurumu(
                    firma_id=current_user.firma_id,
                    depo_id=depo_id,
                    stok_id=stok_id,
                    miktar=miktar
                )
                tenant_db.add(yeni_kayit)
                sayac += 1
        
        tenant_db.commit()
        
        return jsonify({
            'success': True, 
            'message': f"TAMAMLANDI! {len(hareketler)} hareket tarandı. {sayac} adet stok bakiyesi güncellendi."
        })
        
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': f"Hata oluştu: {str(e)}"})

@stok_bp.route('/')
@login_required
def index():  
    tenant_db = get_tenant_db()
    
    # DataGrid Konfigürasyonu
    grid = DataGrid("stok_list", StokKart, "Stok Kartları")
    
    grid.set_column_label('kod', 'Stok Kodu')
    grid.set_column_label('ad', 'Stok Adı')
    grid.set_column_label('kategori.ad', 'Kategori')
    grid.set_column_label('satis_fiyat', 'Satış Fiyatı')
    
    grid.add_column('kod', sortable=True, width='150px')
    grid.add_column('ad', sortable=True, width='300px')
    grid.add_column('kategori.ad', sortable=True, width='200px') 
    grid.add_column('satis_fiyati', sortable=True, width='100px', type=FieldType.CURRENCY)
    grid.add_column('alis_fiyati', sortable=True, width='100px', type=FieldType.CURRENCY)

    grid.add_action('detay', 'Hareketler', 'bi bi-clock-history', 'btn-info btn-sm', 'route', 'stok.detay')
    grid.add_action('edit', 'Düzelt', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'stok.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'stok.sil')
    
    # Golden Rule: Query Tenant DB üzerinden
    query = tenant_db.query(StokKart).filter_by(firma_id=current_user.firma_id)
    
    grid.set_column_order(['kategori.ad', 'kod', 'ad', 'satis_fiyati', 'alis_fiyati'])
    
    # Gizlenecek Sütunlar
    hidden_cols = [
        'olusturma_tarihi', 'resim_path', 'anahtar_kelimeler', 'kategori_id',
        'mevsimsel_grup', 'aciklama_detay', 'mensei', 'model', 'garanti_suresi_ay',
        'marka', 'tedarikci_id', 'muhasebe_kod_id', 'id', 'firma_id', 'uretici_kodu',
        'kdv_kod_id', 'raf_omru_gun', 'kritik_seviye', 'tedarik_suresi_gun', 'desi',
        'agirlik_kg', 'stok_fisi_hareketleri', 'depo_hareketleri', 'fatura_kalemleri',
        'siparis_detaylari', 'sepet_detaylari', 'paket_icerigi', 'paket_ana_urun'
    ]
    for col in hidden_cols:
        grid.hide_column(col)
        
    grid.process_query(query)
    return render_template('stok/index.html', grid=grid)

@stok_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_stok_form()
    
    if request.method == 'POST':
        form.process_request(request.form, request.files)
        
        if form.validate():
            tenant_db = get_tenant_db()
            try:
                # Resim Kaydetme
                resim_yolu = None
                if 'resim' in request.files:
                    file = request.files['resim']
                    if file and file.filename:
                        filename = secure_filename(f"{current_user.firma_id}_{file.filename}")
                        os.makedirs(current_app.config.get('UPLOAD_FOLDER'), exist_ok=True)
                        file.save(os.path.join(current_app.config.get('UPLOAD_FOLDER'), filename))
                        resim_yolu = f"uploads/stok/{filename}"

                data = form.get_data()
                is_aktif = str(data.get('aktif')).lower() in ['true', '1', 'on', 'yes']

                stok = StokKart(
                    firma_id=current_user.firma_id,
                    kod=data.get('kod'),
                    ad=data.get('ad'),
                    barkod=data.get('barkod'),
                    uretici_kodu=data.get('uretici_kodu'),
                    kategori_id=data.get('kategori_id'),
                    
                    birim=data.get('birim'),
                    tip=data.get('tip'),
                    aktif=is_aktif,
                    
                    marka=data.get('marka'),
                    model=data.get('model'),
                    mensei=data.get('mensei'),
                    
                    doviz_turu=data.get('doviz_turu'),
                    alis_fiyati=para_cevir(data.get('alis_fiyati')),
                    satis_fiyati=para_cevir(data.get('satis_fiyati')),
                    kdv_kod_id=data.get('kdv_kod_id') or None,
                    muhasebe_kod_id=data.get('muhasebe_kod_id') or None,
                    
                    tedarikci_id=data.get('tedarikci_id') or None,
                    mevsimsel_grup=data.get('mevsimsel_grup'),
                    
                    kritik_seviye=para_cevir(data.get('kritik_seviye')),
                    tedarik_suresi_gun=int(data.get('tedarik_suresi_gun') or 3),
                    raf_omru_gun=int(data.get('raf_omru_gun') or 0),
                    garanti_suresi_ay=int(data.get('garanti_suresi_ay') or 24),
                    agirlik_kg=para_cevir(data.get('agirlik_kg')),
                    desi=para_cevir(data.get('desi')),
                    
                    anahtar_kelimeler=data.get('anahtar_kelimeler'),
                    aciklama_detay=data.get('aciklama_detay'),
                    ozel_kod1=data.get('ozel_kod1'),
                    ozel_kod2=data.get('ozel_kod2'),
                    
                    resim_path=resim_yolu
                )
                
                tenant_db.add(stok)
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Stok kartı kaydedildi.', 'redirect': '/stok'})
            
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500
        else:
             return jsonify({'success': False, 'message': 'Validasyon hatası', 'errors': form.get_errors()}), 400

    return render_template('stok/form.html', form=form, title="Yeni Stok Kartı")

@stok_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    
    # Manual get_or_404
    stok = tenant_db.get(StokKart, id)
    if not stok or stok.firma_id != current_user.firma_id:
        abort(404)

    form = create_stok_form(stok)
    
    if request.method == 'POST':
        form.process_request(request.form, request.files)
        if form.validate():
            try:
                data = form.get_data()
                
                # Resim Güncelleme
                if 'resim' in request.files:
                    file = request.files['resim']
                    if file and file.filename:
                        filename = secure_filename(f"{current_user.firma_id}_{file.filename}")
                        os.makedirs(current_app.config.get('UPLOAD_FOLDER'), exist_ok=True)
                        file.save(os.path.join(current_app.config.get('UPLOAD_FOLDER'), filename))
                        stok.resim_path = f"uploads/stok/{filename}"

                # Tüm Alanları Güncelle
                stok.kod = data.get('kod')
                stok.ad = data.get('ad')
                stok.barkod = data.get('barkod')
                stok.uretici_kodu = data.get('uretici_kodu')
                stok.kategori_id = data.get('kategori_id')
                stok.birim = data.get('birim')
                stok.tip = data.get('tip')
                
                stok.marka = data.get('marka')
                stok.model = data.get('model')
                stok.mensei = data.get('mensei')
                stok.aktif = str(data.get('aktif')).lower() in ['true', '1', 'on', 'yes']
                
                stok.doviz_turu = data.get('doviz_turu')
                stok.alis_fiyati = para_cevir(data.get('alis_fiyati'))
                stok.satis_fiyati = para_cevir(data.get('satis_fiyati'))
                stok.kdv_kod_id = data.get('kdv_kod_id') or None
                stok.muhasebe_kod_id = data.get('muhasebe_kod_id') or None
                
                stok.tedarikci_id = data.get('tedarikci_id') or None
                stok.mevsimsel_grup = data.get('mevsimsel_grup')
                
                stok.kritik_seviye = para_cevir(data.get('kritik_seviye'))
                stok.tedarik_suresi_gun = int(data.get('tedarik_suresi_gun') or 3)
                stok.raf_omru_gun = int(data.get('raf_omru_gun') or 0)
                stok.garanti_suresi_ay = int(data.get('garanti_suresi_ay') or 24)
                stok.agirlik_kg = para_cevir(data.get('agirlik_kg'))
                stok.desi = para_cevir(data.get('desi'))
                
                stok.anahtar_kelimeler = data.get('anahtar_kelimeler')
                stok.aciklama_detay = data.get('aciklama_detay')
                stok.ozel_kod1 = data.get('ozel_kod1')
                stok.ozel_kod2 = data.get('ozel_kod2')
                
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Güncellendi.', 'redirect': '/stok'})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('stok/form.html', form=form, title="Stok Kartı Düzenle")

@stok_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    stok = tenant_db.get(StokKart, id)
    
    if not stok or stok.firma_id != current_user.firma_id: 
        return jsonify({'success': False, 'message': 'Yetkisiz veya bulunamadı'}), 403

    try:
        tenant_db.delete(stok)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Stok kartı silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@stok_bp.route('/detay/<int:id>')
@login_required
def detay(id):
    tenant_db = get_tenant_db()
    
    stok = tenant_db.get(StokKart, id)
    if not stok or stok.firma_id != current_user.firma_id: 
        abort(403)
        
    # --- GÜVENLİK FİLTRESİ ---
    merkez_rolleri = ['admin', 'patron', 'finans_muduru', 'muhasebe_muduru']
    
    aktif_bolge_id = session.get('aktif_bolge_id')
    aktif_sube_id = session.get('aktif_sube_id')
    
    izinli_sube_ids = []

    if current_user.rol not in merkez_rolleri:
        if aktif_bolge_id:
            # Sube tablosu da Tenant DB'de
            subeler = tenant_db.query(Sube).filter_by(bolge_id=aktif_bolge_id).all()
            izinli_sube_ids = [s.id for s in subeler]
            
        elif aktif_sube_id:
            izinli_sube_ids = [int(aktif_sube_id)]
            
    # 1. HAREKETLER (Tenant DB)
    hareket_query = tenant_db.query(StokHareketi).filter_by(stok_id=id, firma_id=current_user.firma_id)

    if current_user.rol not in merkez_rolleri:
        if izinli_sube_ids:
            hareket_query = hareket_query.filter(StokHareketi.sube_id.in_(izinli_sube_ids))
        else:
            hareket_query = hareket_query.filter(literal(False))

    hareketler = hareket_query.order_by(StokHareketi.tarih.desc(), StokHareketi.id.desc()).all()

    # 2. DEPO DURUMLARI (Tenant DB)
    depo_query = tenant_db.query(
        Depo.ad, 
        StokDepoDurumu.miktar
    ).join(StokDepoDurumu, Depo.id == StokDepoDurumu.depo_id)\
     .filter(StokDepoDurumu.stok_id == id)\
     .filter(StokDepoDurumu.miktar != 0)

    if current_user.rol not in merkez_rolleri:
        if izinli_sube_ids:
            depo_query = depo_query.filter(Depo.sube_id.in_(izinli_sube_ids))
        else:
            depo_query = depo_query.filter(literal(False))

    depo_durumlari = depo_query.all()

    return render_template(
        'stok/detay.html', 
        stok=stok, 
        hareketler=hareketler, 
        depo_durumlari=depo_durumlari
    )

# --- OTO NUMARA API ---
@stok_bp.route('/api/siradaki-kod')
@login_required
def api_siradaki_kod():
    tenant_db = get_tenant_db()
    son_stok = tenant_db.query(StokKart).filter_by(firma_id=current_user.firma_id).order_by(StokKart.id.desc()).first()
    yeni_kod = "STK-0001"
    
    if son_stok and son_stok.kod:
        try:
            if '-' in son_stok.kod:
                prefix, numara = son_stok.kod.rsplit('-', 1)
                yeni_num = str(int(numara) + 1).zfill(len(numara))
                yeni_kod = f"{prefix}-{yeni_num}"
            elif '.' in son_stok.kod:
                prefix, numara = son_stok.kod.rsplit('.', 1)
                yeni_num = str(int(numara) + 1).zfill(len(numara))
                yeni_kod = f"{prefix}.{yeni_num}"
            else:
                yeni_kod = str(int(son_stok.kod) + 1)
        except: pass
            
    return jsonify({'code': yeni_kod})    

@stok_bp.route('/belge-git/<int:hareket_id>')
@login_required
def belge_git(hareket_id):
    tenant_db = get_tenant_db()
    hareket = tenant_db.get(StokHareketi, hareket_id)
    if not hareket: abort(404)
    
    match = re.search(r'(FIS-\d{4}-\d+|MOB-[\w-]+)', hareket.aciklama or "")
    belge_no = match.group(0) if match else None
    
    if belge_no:
        if belge_no.startswith('FIS'):
            fis = tenant_db.query(StokFisi).filter_by(belge_no=belge_no).first()
            if fis: return redirect(url_for('stok_fisi.duzenle', id=fis.id))
        elif belge_no.startswith('MOB'):
            fatura = tenant_db.query(Fatura).filter_by(belge_no=belge_no).first()
            if fatura: return redirect(url_for('mobile.yazdir', fatura_id=fatura.id))

    flash("İlgili kaynak belge bulunamadı.", "danger")
    return redirect(request.referrer)   

# --- AI ANALİZ ROTALARI (TENANT DB) ---

@stok_bp.route('/yapay-zeka-analiz')
@login_required
def yapay_zeka_analiz():
    return render_template('stok/ai_analiz.html')

@stok_bp.route('/api/ai-tahmin', methods=['POST'])
@login_required
def api_ai_tahmin():
    tenant_db = get_tenant_db()
    
    satislar = tenant_db.query(
        StokKart.ad, Fatura.tarih, FaturaKalemi.miktar
    ).join(Fatura, FaturaKalemi.fatura_id == Fatura.id)\
     .join(StokKart, FaturaKalemi.stok_id == StokKart.id)\
     .filter(Fatura.fatura_turu == FaturaTuru.SATIS.value)\
     .all()
     
    veri_seti = {}
    for satir in satislar:
        urun_adi = satir.ad
        ay = satir.tarih.month 
        miktar = float(satir.miktar or 0)
        if urun_adi not in veri_seti: veri_seti[urun_adi] = {}
        if ay not in veri_seti[urun_adi]: veri_seti[urun_adi][ay] = 0.0
        veri_seti[urun_adi][ay] += miktar

    if not veri_seti:
        return jsonify({'success': False, 'message': 'Analiz için yeterli satış verisi bulunamadı.'})

    try:
        json_data = json.dumps(veri_seti, ensure_ascii=False)
        analiz_raporu = analyze_stock_trends(json_data)
        return jsonify({'success': True, 'report': analiz_raporu})
    except Exception as e:
        return jsonify({'success': False, 'message': f"AI Analiz Hatası: {str(e)}"})

@stok_bp.route('/olu-stok-analiz')
@login_required
def olu_stok_analiz():
    return render_template('stok/olu_stok.html')

@stok_bp.route('/api/olu-stok-hesapla', methods=['POST'])
@login_required
def api_olu_stok_hesapla():
    tenant_db = get_tenant_db()
    
    alti_ay_once = datetime.now() - timedelta(days=180)
    urunler = tenant_db.query(StokKart).filter_by(firma_id=current_user.firma_id).all()
    
    depo_durumlari = {}
    depo_kayitlari = tenant_db.query(StokDepoDurumu).filter_by(firma_id=current_user.firma_id).all()
    for k in depo_kayitlari:
        depo_durumlari[k.stok_id] = depo_durumlari.get(k.stok_id, 0) + float(k.miktar)
        
    satis_miktarlari = {}
    satislar = tenant_db.query(FaturaKalemi.stok_id, FaturaKalemi.miktar)\
        .join(Fatura)\
        .filter(Fatura.firma_id == current_user.firma_id)\
        .filter(Fatura.fatura_turu == FaturaTuru.SATIS.value)\
        .filter(Fatura.tarih >= alti_ay_once)\
        .all()
        
    for s in satislar:
        satis_miktarlari[s.stok_id] = satis_miktarlari.get(s.stok_id, 0) + float(s.miktar)

    analiz_verisi = []
    python_tarafi_toplam_tutar = 0.0 
    
    for urun in urunler:
        stok_adedi = depo_durumlari.get(urun.id, 0)
        satis_adedi = satis_miktarlari.get(urun.id, 0)
        maliyet = float(urun.alis_fiyati or 0)
        
        is_dead_candidate = stok_adedi > 0 and (satis_adedi == 0 or stok_adedi > (satis_adedi * 3))
        
        if is_dead_candidate:
            tutar = stok_adedi * maliyet
            python_tarafi_toplam_tutar += tutar 
            
            analiz_verisi.append({
                "urun_adi": urun.ad,
                "mevcut_stok": stok_adedi,
                "birim_maliyet": maliyet,
                "bagli_sermaye": tutar, 
                "son_6_ay_satis": satis_adedi
            })
    
    if not analiz_verisi:
        return jsonify({'success': False, 'message': 'Harika! Deponuzda ölü stok tespit edilemedi.'})

    try:
        json_data = json.dumps(analiz_verisi[:50], ensure_ascii=False)
        analiz_sonucu = analyze_dead_stock(json_data)
        
        if analiz_sonucu:
            yeni_rapor = AIRaporGecmisi(
                firma_id=current_user.firma_id,
                rapor_turu='OLU_STOK',
                baslik=f"{datetime.now().strftime('%d.%m.%Y')} - Ölü Stok Analizi",
                html_icerik=str(analiz_sonucu),
                ham_veri_json=json_data
            )
            tenant_db.add(yeni_rapor)
            tenant_db.commit()
        
        return jsonify({
            'success': True, 
            'report': analiz_sonucu,
            'kesin_toplam': python_tarafi_toplam_tutar
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f"AI Hatası: {str(e)}"})

@stok_bp.route('/capraz-satis-analizi')
@login_required
def capraz_satis_analizi():
    return render_template('stok/capraz_satis.html')

@stok_bp.route('/api/capraz-satis-hesapla', methods=['POST'])
@login_required
def api_capraz_satis_hesapla():
    tenant_db = get_tenant_db()
    
    son_faturalar = tenant_db.query(Fatura.id).filter(
        Fatura.firma_id == current_user.firma_id,
        Fatura.fatura_turu == FaturaTuru.SATIS.value
    ).order_by(Fatura.tarih.desc()).limit(200).all()
    
    fatura_ids = [f.id for f in son_faturalar]
    
    if not fatura_ids:
        return jsonify({'success': False, 'message': 'Analiz için yeterli satış faturası bulunamadı.'})

    kalemler = tenant_db.query(FaturaKalemi.fatura_id, StokKart.ad)\
        .join(StokKart, FaturaKalemi.stok_id == StokKart.id)\
        .filter(FaturaKalemi.fatura_id.in_(fatura_ids))\
        .all()
        
    sepetler = {}
    for fatura_id, urun_adi in kalemler:
        if fatura_id not in sepetler: sepetler[fatura_id] = []
        sepetler[fatura_id].append(urun_adi)
        
    analiz_verisi = [urunler for urunler in sepetler.values() if len(urunler) > 1]
    
    if len(analiz_verisi) < 3:
        return jsonify({'success': False, 'message': 'Çapraz satış analizi için en az 3 adet çoklu ürün içeren fatura gerekiyor.'})

    try:
        json_data = json.dumps(analiz_verisi, ensure_ascii=False)
        rapor_html = analyze_cross_sell(json_data)
        return jsonify({'success': True, 'report': rapor_html})
    except Exception as e:
        return jsonify({'success': False, 'message': f"AI Hatası: {str(e)}"})

# =========================================================================
# TANIMLAMA ROTALARI (HEPSİ TENANT DB)
# =========================================================================

@stok_bp.route('/tanimlar/muhasebe-gruplari')
@login_required
def muhasebe_gruplari():
    tenant_db = get_tenant_db()
    
    grid = DataGrid("grid_muh_grup", StokMuhasebeGrubu, title="Stok Muhasebe Grupları")
    grid.columns = [] 
    grid.add_column("kod", "Grup Kodu", width="150px")
    grid.add_column("ad", "Grup Adı")
    grid.add_column("aciklama", "Açıklama")
    grid.add_column("aktif", "Durum", type=FieldType.SWITCH)
    
    grid.add_action("edit", "Düzenle", "fas fa-edit", "btn-primary", action_type="route", route_name="stok.muhasebe_grup_islem")
    
    query = tenant_db.query(StokMuhasebeGrubu).filter_by(firma_id=current_user.firma_id)
    grid.process_query(query)
    
    return render_template('stok/tanimlar/list.html', grid=grid, create_url=url_for('stok.muhasebe_grup_islem_yeni'))

@stok_bp.route('/tanimlar/muhasebe-grup-ekle', methods=['GET', 'POST'], endpoint='muhasebe_grup_islem_yeni')
@stok_bp.route('/tanimlar/muhasebe-grup-duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def muhasebe_grup_islem(id=None):
    tenant_db = get_tenant_db()
    target_url = url_for('stok.muhasebe_grup_islem', id=id) if id else url_for('stok.muhasebe_grup_islem_yeni')
    
    grup = None
    if id: 
        grup = tenant_db.get(StokMuhasebeGrubu, id)
        if not grup: abort(404)
        
    form = get_muhasebe_grup_form(target_url, edit_mode=(id is not None), instance=grup)
    
    if request.method == 'GET' and grup:
        for field in form.fields:
            if hasattr(grup, field.name):
                val = getattr(grup, field.name)
                if val is not None: field.value = val

    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                yeni_kod = data.get('kod')

                # MÜKERRER KOD KONTROLÜ (Tenant DB)
                mevcut = tenant_db.query(StokMuhasebeGrubu).filter_by(firma_id=current_user.firma_id, kod=yeni_kod).first()
                
                if mevcut and (not grup or mevcut.id != grup.id):
                    return jsonify({'success': False, 'message': f"Hata: '{yeni_kod}' kodu zaten kullanılıyor!"}), 400

                if not grup:
                    grup = StokMuhasebeGrubu(firma_id=current_user.firma_id)
                    tenant_db.add(grup)
                
                grup.kod = yeni_kod
                grup.ad = data.get('ad')
                grup.aciklama = data.get('aciklama')
                grup.alis_hesap_id = data.get('alis_hesap_id') or None
                grup.satis_hesap_id = data.get('satis_hesap_id') or None
                grup.alis_iade_hesap_id = data.get('alis_iade_hesap_id') or None
                grup.satis_iade_hesap_id = data.get('satis_iade_hesap_id') or None
                
                raw_aktif = data.get('aktif')
                grup.aktif = str(raw_aktif).lower() in ['true', '1', 'on', 'yes']
                
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'İşlem başarıyla tamamlandı.', 'redirect': url_for('stok.muhasebe_gruplari')})
            
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f"Hata: {str(e)}"}), 500
            
    return render_template('stok/tanimlar/form.html', form=form)

@stok_bp.route('/tanimlar/kdv-gruplari')
@login_required
def kdv_gruplari():
    tenant_db = get_tenant_db()
    grid = DataGrid("grid_kdv", StokKDVGrubu, title="KDV Grupları")
    grid.columns = []
    grid.add_column("kod", "Kod", width="150px")
    grid.add_column("ad", "Ad")
    grid.add_column("alis_kdv_orani", "Alış (%)", type=FieldType.NUMBER)
    grid.add_column("satis_kdv_orani", "Satış (%)", type=FieldType.NUMBER)
    
    grid.add_action("edit", "Düzenle", "fas fa-edit", "btn-primary", action_type="route", route_name="stok.kdv_grup_islem")
    
    query = tenant_db.query(StokKDVGrubu).filter_by(firma_id=current_user.firma_id)
    grid.process_query(query)
    
    return render_template('stok/tanimlar/list.html', grid=grid, create_url=url_for('stok.kdv_grup_islem_yeni'))

@stok_bp.route('/tanimlar/kdv-grup-ekle', methods=['GET', 'POST'], endpoint='kdv_grup_islem_yeni')
@stok_bp.route('/tanimlar/kdv-grup-duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def kdv_grup_islem(id=None):
    tenant_db = get_tenant_db()
    target_url = url_for('stok.kdv_grup_islem', id=id) if id else url_for('stok.kdv_grup_islem_yeni')
    
    grup = None
    if id: 
        grup = tenant_db.get(StokKDVGrubu, id)
        if not grup: abort(404)

    form = get_kdv_grup_form(target_url, edit_mode=(id is not None), instance=grup)
    
    if request.method == 'GET' and grup:
        for field in form.fields:
            if hasattr(grup, field.name): 
                field.value = getattr(grup, field.name)

    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            yeni_kod = data.get('kod')

            mevcut_kayit = tenant_db.query(StokKDVGrubu).filter_by(firma_id=current_user.firma_id, kod=yeni_kod).first()
            hata_var = False
            if not grup and mevcut_kayit: hata_var = True
            elif grup and mevcut_kayit and mevcut_kayit.id != grup.id: hata_var = True
            
            if hata_var:
                flash(f"Hata: '{yeni_kod}' kodu zaten kullanımda!", "danger")
                return render_template('stok/tanimlar/form.html', form=form)

            if not grup:
                grup = StokKDVGrubu(firma_id=current_user.firma_id)
                tenant_db.add(grup)
            
            grup.kod = yeni_kod
            grup.ad = data.get('ad')
            grup.alis_kdv_orani = data.get('alis_kdv_orani')
            grup.satis_kdv_orani = data.get('satis_kdv_orani')
            grup.alis_kdv_hesap_id = data.get('alis_kdv_hesap_id') or None
            grup.satis_kdv_hesap_id = data.get('satis_kdv_hesap_id') or None
            
            try:
                tenant_db.commit()
                flash('KDV Grubu kaydedildi.', 'success')
                return redirect(url_for('stok.kdv_gruplari'))
            except Exception as e:
                tenant_db.rollback()
                flash(f'Hata: {str(e)}', 'danger')

    return render_template('stok/tanimlar/form.html', form=form)

@stok_bp.route('/ayarlar/ai')
@login_required
def ai_ayarlar():
    form = create_ai_settings_form()
    return render_template('stok/form.html', form=form, title="Yapay Zeka Ayarları")

@stok_bp.route('/ayarlar/ai-guncelle', methods=['POST'])
@login_required
def ai_ayarlar_guncelle():
    tenant_db = get_tenant_db()
    form = create_ai_settings_form()
    form.process_request(request.form)
    
    if form.validate():
        try:
            data = form.get_data()
            for key, val in data.items():
                ayar = tenant_db.query(AIRaporAyarlari).filter_by(firma_id=current_user.firma_id, anahtar=key).first()
                if ayar: ayar.deger = str(val)
            
            tenant_db.commit()
            return jsonify({'success': True, 'message': 'AI parametreleri güncellendi.', 'redirect': '/stok/ayarlar/ai'})
        except Exception as e:
            tenant_db.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
            
    return jsonify({'success': False, 'message': 'Hata', 'errors': form.get_errors()}), 400

@stok_bp.route('/paket-icerik/<int:id>', methods=['GET', 'POST'])
@login_required
def paket_icerik(id):
    tenant_db = get_tenant_db()
    stok = tenant_db.get(StokKart, id)
    if not stok: abort(404)
    
    if request.method == 'GET' and stok.tip not in ['paket', 'mamul', 'set']:
        flash(f"Bu ürünün tipi '{stok.tip}'. Paket içeriği sadece Paket/Set ürünler için tanımlanabilir.", "warning")
    
    form = create_paket_icerik_form(id)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                # 1. Eski İçeriği Temizle (Tenant DB)
                tenant_db.query(StokPaketIcerigi).filter_by(paket_stok_id=id).delete()
                
                # 2. Formdan Gelen Veriler
                alt_stok_ids = request.form.getlist('bilesenler_alt_stok_id[]')
                miktarlar = request.form.getlist('bilesenler_miktar[]')
                
                # 3. Yeni Satırları Ekle
                for i in range(len(alt_stok_ids)):
                    alt_id = alt_stok_ids[i]
                    miktar = miktarlar[i]
                    
                    if alt_id and miktar:
                        yeni_bilesen = StokPaketIcerigi(
                            paket_stok_id=stok.id,
                            alt_stok_id=int(alt_id),
                            miktar=para_cevir(miktar)
                        )
                        tenant_db.add(yeni_bilesen)
                
                if stok.tip == 'standart':
                    stok.tip = 'paket'
                
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Paket içeriği güncellendi.', 'redirect': f'/stok/detay/{id}'})
            
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500
                
    return render_template('stok/paket.html', form=form, stok=stok)