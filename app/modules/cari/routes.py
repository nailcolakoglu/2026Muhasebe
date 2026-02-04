# modules/cari/routes.py (DÜZELTİLMİŞ)

from flask import Blueprint, render_template, request, jsonify, flash, url_for, g, redirect
from flask_login import login_required, current_user
from app.modules.cari.models import CariHesap, CariHareket 
from app.modules.fatura.models import Fatura
from app.enums import FaturaTuru
from app.modules.lokasyon.models import Sehir, Ilce
from app.form_builder import DataGrid
from .forms import create_cari_form
from sqlalchemy import func, text
from app.form_builder.ai_generator import analyze_customer_risk
import json
from datetime import datetime
from app.extensions import db, get_tenant_db
from app.decorators import permission_required  # YETKİLİ KULLANICILAR İÇİN

cari_bp = Blueprint('cari', __name__)


# ========================================
# KAYIT FONKSİYONU
# ========================================
def islem_kaydet(form, cari=None):
    """Firebird'e cari kaydet"""
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return False, "Firebird bağlantısı kurulamadı."
    
    data = form.get_data()
    
    if not cari:
        cari = CariHesap()
        cari.firma_id = 1 #current_user.firma_id
        tenant_db.add(cari)
    
    cari.kod = data.get('kod')
    cari.unvan = data.get('unvan')
    cari.vergi_no = data.get('vergi_no') or data.get('tc_no')
    cari.vergi_dairesi = data.get('vergi_dairesi')
    cari.telefon = data.get('telefon')
    cari.eposta = data.get('eposta')
    cari.adres = data.get('adres')
    cari.sehir_id = int(data.get('sehir_id')) if data.get('sehir_id') else None
    cari.ilce_id = int(data.get('ilce_id')) if data.get('ilce_id') else None
    
    if data.get('alis_muhasebe_hesap_id'):
        cari.alis_muhasebe_hesap_id = int(data.get('alis_muhasebe_hesap_id'))
    
    if data.get('satis_muhasebe_hesap_id'):
        cari.satis_muhasebe_hesap_id = int(data.get('satis_muhasebe_hesap_id'))
        
    try:
        tenant_db.commit()
        return True, "Cari kart başarıyla kaydedildi."
    except Exception as e:
        tenant_db.rollback()
        return False, f"Hata: {str(e)}"


# ========================================
# ROTALAR
# ========================================
@cari_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    
    if not tenant_db: 
        flash('Firebird bağlantısı yok.Lütfen firma seçin.', 'danger')
        return redirect(url_for('main.index'))
    
    grid = DataGrid("cari_list", CariHesap, "Cari Hesaplar")
    
    grid.add_column('kod', 'Kod', width='80px')
    grid.add_column('unvan', 'Ünvan')
    grid.add_column('telefon', 'Telefon')
    grid.add_column('borc_bakiye', 'Borç', type='currency')
    grid.add_column('alacak_bakiye', 'Alacak', type='currency')
    
    grid.add_action('detay', 'Ekstre', 'bi bi-file-text', 'btn-info btn-sm', 'route', 'cari.ekstre')
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'cari.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'cari.sil')
    
    query = tenant_db.query(CariHesap).filter_by(firma_id=1)
    grid.process_query(query)
    
    return render_template('cari/index.html', grid=grid)


@cari_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_cari_form()
    if request.method == 'POST': 
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = islem_kaydet(form)
            if basari:
                flash(mesaj, "success")
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('cari.index')})
            else:
                return jsonify({'success': False, 'message': mesaj}), 400
    return render_template('cari/form.html', form=form)


@cari_bp.route('/duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    cari = tenant_db.query(CariHesap).get(id)
    
    if not cari:
        flash('Cari bulunamadı', 'danger')
        return redirect(url_for('cari.index'))
    
    form = create_cari_form(cari)
    
    if request.method == 'POST': 
        form.process_request(request.form)
        if form.validate():
            basari, mesaj = islem_kaydet(form, cari)
            if basari:
                flash(mesaj, "success")
                return jsonify({'success': True, 'message': mesaj, 'redirect': url_for('cari.index')})
            else:
                return jsonify({'success': False, 'message': mesaj}), 400
    
    return render_template('cari/form.html', form=form)


@cari_bp.route('/sil/<int:id>', methods=['POST'])
@login_required
@permission_required('cari.delete')
def sil(id):
    tenant_db = get_tenant_db()
    cari = tenant_db.query(CariHesap).get(id)
    
    if not cari:
        return jsonify({'success': False, 'message': 'Cari bulunamadı'}), 404
    
    try:
        tenant_db.delete(cari)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Cari kart silindi.'})
    except Exception as e: 
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@cari_bp.route('/ekstre/<int:id>')
@login_required
def ekstre(id):
    tenant_db = get_tenant_db()
    cari = tenant_db.query(CariHesap).get(id)
    
    if not cari:
        flash('Cari bulunamadı', 'danger')
        return redirect(url_for('cari.index'))
    
    query = tenant_db.query(CariHareket).filter_by(cari_id=id).order_by(CariHareket.tarih.asc())
    ham_hareketler = query.all()
    
    hareketler = []
    toplam_borc = 0
    toplam_alacak = 0
    bakiye = 0
    
    for h in ham_hareketler: 
        borc = float(h.borc or 0)
        alacak = float(h.alacak or 0)
        toplam_borc += borc
        toplam_alacak += alacak
        bakiye += (borc - alacak)
        
        hareketler.append({
            'tarih': h.tarih,
            'belge_no': h.belge_no,
            'islem_turu': h.islem_turu,
            'aciklama': h.aciklama,
            'borc': borc,
            'alacak': alacak,
            'bakiye': bakiye
        })

    return render_template('cari/detay.html', 
                           cari=cari, 
                           hareketler=hareketler, 
                           toplam_borc=toplam_borc, 
                           toplam_alacak=toplam_alacak,
                           genel_bakiye=bakiye)


@cari_bp.route('/api/siradaki-kod')
@login_required
def api_siradaki_kod():
    tenant_db = get_tenant_db()
    son = tenant_db.query(CariHesap).filter_by(firma_id=1).order_by(CariHesap.id.desc()).first()
    
    yeni = "C-0001"
    if son and '-' in son.kod:
        try:
            p, n = son.kod.split('-')
            yeni = f"{p}-{str(int(n)+1).zfill(4)}"
        except:
            pass
    return jsonify({'code': yeni})

@cari_bp.route('/api/get-ilceler', methods=['GET'])
@login_required
def api_get_ilceler():
    """
    Seçilen şehre göre ilçeleri getirir.
    Hem 'parent_id' hem de 'sehir_id' parametrelerini destekler.
    """
    tenant_db = get_tenant_db()
    
    # 1. Parametre Kontrolü (Frontend hangisini gönderirse onu al)
    sehir_id = request.args.get('parent_id') or request.args.get('sehir_id')
    
    if not sehir_id or not tenant_db: 
        return jsonify([])
    
    try:
        # Firebird sorgusu
        ilceler = tenant_db.query(Ilce).filter_by(sehir_id=sehir_id).order_by(Ilce.ad).all()
        return jsonify([{'id': i.id, 'text': i.ad} for i in ilceler])
        
    except Exception as e:
        print(f"İlçe API Hatası: {e}")
        return jsonify([]) # Hata durumunda boş liste dön

@cari_bp.route('/risk-analizi')
@login_required
def risk_analizi():
    return render_template('cari/risk_analizi.html')

@cari_bp.route('/api/risk-hesapla', methods=['POST'])
@login_required
def api_risk_hesapla():
    """Müşteri risk verilerini hazırlar ve AI'ya gönderir (Python ile Hesaplama)"""
    
    # 1.Tüm Carileri Çek  # ✅ DOĞRU:
    # cariler = CariHesap.query_tenant.filter_by(firma_id=current_user.firma_id).all()
    # VEYA daha iyi:  g.tenant_db kullan
    from flask import g
    cariler = g.tenant_db.query(CariHesap).filter_by(firma_id=1).all()
    # 2.Tüm Satış Faturalarını Çek (Gruplama yapmadan ham veri)
    # Bu yöntem Firebird sürücüsünün çökmesini engeller
    faturalar = db.session.query_tenant(
        Fatura.cari_id,
        Fatura.tarih,
        Fatura.genel_toplam
    ).filter(
        Fatura.firma_id == 1,
        Fatura.fatura_turu == FaturaTuru.SATIS.value
    ).all()
    
    # 3.Python ile İstatistik Çıkarma
    fatura_ozetleri = {}
    
    for fatura in faturalar:
        c_id = fatura.cari_id
        tarih = fatura.tarih # Date objesi
        tutar = float(fatura.genel_toplam or 0)
        
        if c_id not in fatura_ozetleri:
            fatura_ozetleri[c_id] = {
                'son_tarih': tarih,
                'islem_sayisi': 0,
                'toplam_ciro': 0.0
            }
        
        # Son tarihi güncelle
        if tarih > fatura_ozetleri[c_id]['son_tarih']:
            fatura_ozetleri[c_id]['son_tarih'] = tarih
            
        fatura_ozetleri[c_id]['islem_sayisi'] += 1
        fatura_ozetleri[c_id]['toplam_ciro'] += tutar

    # 4.AI Veri Setini Oluştur
    analiz_verisi = []
    
    for cari in cariler:
        ozet = fatura_ozetleri.get(cari.id)
        
        if ozet:
            son_tarih_str = ozet['son_tarih'].strftime('%Y-%m-%d')
            islem_sayisi = ozet['islem_sayisi']
            ciro = ozet['toplam_ciro']
        else:
            son_tarih_str = "Yok"
            islem_sayisi = 0
            ciro = 0.0
            
        borc = float(cari.borc_bakiye or 0)
        alacak = float(cari.alacak_bakiye or 0)
        net_bakiye = borc - alacak # Pozitifse bize borçlu
        
        # Filtre: Borcu olanlar VEYA cirosu yüksek olanlar analize girsin
        if net_bakiye > 1000 or ciro > 5000:
            analiz_verisi.append({
                "cari_unvan": cari.unvan,
                "net_borc_bakiye": net_bakiye,
                "son_alisveris_tarihi": son_tarih_str,
                "toplam_islem_adedi": islem_sayisi,
                "toplam_ciro_tl": ciro
            })
            
    if not analiz_verisi:
        return jsonify({'success': False, 'message': 'Analiz edilecek riskli veya aktif cari bulunamadı.'})

    # 5.AI'ya Gönder (En kritik 40 tanesi)
    analiz_verisi.sort(key=lambda x: x['net_borc_bakiye'], reverse=True)
    
    try:
        json_data = json.dumps(analiz_verisi[:40], ensure_ascii=False)
        rapor_html = analyze_customer_risk(json_data)
        
        return jsonify({'success': True, 'report': rapor_html})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f"AI Hatası: {str(e)}"})   

# --- ROTA PLANLAMA EKRANI ---
@cari_bp.route('/rota-planlama')
@login_required
def rota_planlama():
    """
    Plasiyerin müşterilerini seçip rota oluşturacağı ekran.
    """
    # Sadece konumu olan carileri getir
    cariler = CariHesap.query_tenant.filter(
        CariHesap.firma_id == 1,
        CariHesap.aktif == True,
        CariHesap.konum.isnot(None),
        CariHesap.konum != ''
    ).order_by(CariHesap.unvan).all()
    
    return render_template('cari/rota.html', cariler=cariler)

# --- AI ROTA API ---
@cari_bp.route('/api/rota-olustur', methods=['POST'])
@login_required
def api_rota_olustur():
    """
    Seçilen carileri ve başlangıç konumunu alıp AI'ya optimize ettirir.
    """
    if not optimize_sales_route:
        return jsonify({'success': False, 'message': 'AI Modülü aktif değil.'}), 501

    try:
        data = request.get_json()
        baslangic_konumu = data.get('baslangic') # "lat,lng"
        secili_ids = data.get('cari_ids', [])
        
        if not baslangic_konumu:
            return jsonify({'success': False, 'message': 'Başlangıç konumu alınamadı.'})
            
        if not secili_ids:
            return jsonify({'success': False, 'message': 'Lütfen en az bir müşteri seçiniz.'})

        # Carileri Veritabanından Çek
        cariler = CariHesap.query_tenant.filter(CariHesap.id.in_(secili_ids)).all()
        
        # AI İçin Veriyi Hazırla
        musteri_listesi = []
        for c in cariler:
            musteri_listesi.append({
                "id": c.id,
                "unvan": c.unvan,
                "konum": c.konum, # FieldType.GEOLOCATION'dan gelen "41.123,29.123" verisi
                "bakiye": float(c.bakiye),
                "adres": c.adres or "Adres girilmemiş"
            })
            
        # Yapay Zeka Motorunu Çalıştır
        sonuc = optimize_sales_route(baslangic_konumu, musteri_listesi)
        
        if "error" in sonuc:
            return jsonify({'success': False, 'message': sonuc["error"]})
            
        return jsonify({'success': True, 'rota': sonuc})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500         

@cari_bp.route('/api1/rota-olustur', methods=['POST'])
@login_required
def api_rota_olustur1():
    """
    Seçili carileri veya plasiyerin müşterilerini alıp AI'ya gönderir.
    """
    try:
        data = request.get_json()
        baslangic_konumu = "38.4192, 27.1287" #data.get('baslangic') # Örn: Tarayıcıdan gelen geolocation
        secili_cari_ids = data.get('cari_ids', [])
        
        if not baslangic_konumu:
            # Konum yoksa Merkez Depo/Ofis konumu varsayalım
            baslangic_konumu = "38.4192, 27.1287" # Örn: İzmir Merkez
            
        # Veritabanından Carileri Çek (Koordinatı olanlar)
        cariler = CariHesap.query_tenant.filter(
            CariHesap.id.in_(secili_cari_ids),
            CariHesap.konum.isnot(None),
            CariHesap.konum != ''
        ).all()
        
        if not cariler:
            return jsonify({'success': False, 'message': 'Seçili carilerde konum bilgisi bulunamadı.'})
            
        # AI İçin Listeyi Hazırla
        musteri_listesi = []
        for c in cariler:
            musteri_listesi.append({
                "id": c.id,
                "unvan": c.unvan,
                "konum": c.konum, # "lat,lng" formatında string olmalı
                "bakiye": float(c.bakiye),
                "risk_durumu": "Yüksek" if c.bakiye > 100000 else "Normal" # AI buna göre öncelik verebilir
            })
            
        # Yapay Zeka Motorunu Çağır
        sonuc = optimize_sales_route(baslangic_konumu, musteri_listesi)
        
        if "error" in sonuc:
            return jsonify({'success': False, 'message': sonuc["error"]})
            
        return jsonify({'success': True, 'rota': sonuc})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
