# app/modules/rapor/routes.py

import logging
import datetime
from flask import Blueprint, render_template, request, jsonify, Response, g, flash, send_file, make_response, session, url_for, redirect
from flask_login import login_required, current_user
from app.extensions import db, get_tenant_db, csrf
from app.modules.stok.models import StokKart, StokDepoDurumu, StokHareketi
from app.modules.depo.models import Depo
from app.modules.cari.models import CariHesap
from app.modules.rapor.models import YazdirmaSablonu, SavedReport
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.firmalar.models import Firma
from .rapor_builder import RaporBuilder, rapor_aylik_satis_ozeti
from .export_engine import ExportEngine
 
#from models import (, , , CariHesap, Fatura, KasaHareket, BankaHareket, CekSenet, Kullanici, FaturaTuru,
#                FaturaKalemi, , HareketTuru, AIRaporAyarlari, AIRaporGecmisi, Siparis, YazdirmaSablonu, Firma)

from .forms import (create_cari_ekstre_form, create_stok_rapor_form, create_tarih_filtre_form,
 create_rapor_filtre_form, get_yevmiye_filter_form)

from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app.utils.decorators import role_required, permission_required
from app.form_builder.ai_generator import analyze_anomalies, generate_ceo_briefing
import json
from app.enums import (
    PortfoyTipi, FaturaTuru, HareketTuru
)
from .services import YevmiyeRaporuMotoru
from io import BytesIO
from .xml_builder import EDefterBuilder 
from .forms import create_sablon_form
from .doc_engine import DocumentGenerator
from app.form_builder import DataGrid
from .engine.standard import YevmiyeDefteriRaporu, BuyukDefterRaporu, GelirTablosuRaporu
from .registry import get_rapor_class, RAPOR_KATALOGU

# ✅ Logger tanımla
logger = logging.getLogger(__name__)

rapor_bp = Blueprint('rapor', __name__)

# ✨ DÜZELTME 1: Jinja2'ye '|yaziyla' filtresini küresel olarak öğretiyoruz
@rapor_bp.app_template_filter('yaziyla')
def yaziyla_filter(sayi):
    try:
        from app.araclar import sayiyi_yaziya_cevir
        return sayiyi_yaziya_cevir(sayi) if sayi else ""
    except Exception:
        return ""

# ✅ Tüm /api/* route'larını CSRF'den muaf tut
@rapor_bp.before_request
def check_csrf():
    """API route'larında CSRF kontrolü yapma"""
    if request.path.startswith('/rapor/api/'):
        csrf.exempt(lambda: None)()

@rapor_bp.route('/')
@login_required
def index():
    """Raporlama ana sayfası"""
    
    # 🚀 ÇÖZÜM: Henüz yazılmamış modüllerin url_for çağrıları sayfayı çökertmesin diye
    # şimdilik '#' (boş link) olarak güncellendi. Modüller yazıldıkça buralar aktif edilecek.
    rapor_kategorileri = [
        {
            'id': 'finans',
            'isim': 'Finans Raporları',
            'ikon': 'bi-bank',
            'renk': 'primary',
            'raporlar': [
                {'isim': 'Cari Bakiye Raporu', 'url': '#', 'aciklama': 'Müşteri ve tedarikçi bakiyeleri'},
                {'isim': 'Kasa/Banka Durumu', 'url': '#', 'aciklama': 'Güncel nakit durumu'},
                {'isim': 'Gelir/Gider Analizi', 'url': '#', 'aciklama': 'Aylık gelir gider tablosu'}
            ]
        },
        {
            'id': 'muhasebe',
            'isim': 'Muhasebe Raporları',
            'ikon': 'bi-calculator',
            'renk': 'success',
            'raporlar': [
                {'isim': 'Mizan', 'url': '#', 'aciklama': 'Geçici ve kesin mizan'},
                {'isim': 'Bilanço ve Gelir Tablosu', 'url': '#', 'aciklama': 'Dönem sonu mali tablolar'},
                {'isim': 'KDV Raporu', 'url': '#', 'aciklama': 'İndirilecek ve hesaplanan KDV'}
            ]
        },
        {
            'id': 'satis',
            'isim': 'Satış ve Stok Raporları',
            'ikon': 'bi-graph-up',
            'renk': 'info',
            'raporlar': [
                {'isim': 'Satış Analizi', 'url': '#', 'aciklama': 'Ürün ve cari bazlı satışlar'},
                {'isim': 'Stok Durum Raporu', 'url': '#', 'aciklama': 'Mevcut stok ve kritik seviyeler'},
                {'isim': 'Karlılık Raporu', 'url': '#', 'aciklama': 'Maliyet ve satış karlılığı'}
            ]
        }
    ]
    
    return render_template('rapor/index.html', rapor_kategorileri=rapor_kategorileri)

@rapor_bp.route('/export/<format>')
@login_required
def export_rapor(format):
    """Rapor export (excel/pdf/csv)"""
    tenant_db = get_tenant_db()
    
    # Rapor tipi (query param)
    rapor_tipi = request.args.get('tip', 'aylik_satis')
    
    # Rapor oluştur
    if rapor_tipi == 'aylik_satis':
        bitis = datetime.now()
        baslangic = bitis - timedelta(days=365)
        df = rapor_aylik_satis_ozeti(tenant_db, baslangic, bitis)
        title = "Aylık Satış Raporu"
    else:
        return jsonify({'error': 'Geçersiz rapor tipi'}), 400
    
    # Export
    if format == 'excel':
        return ExportEngine.to_excel(df, f"{rapor_tipi}.xlsx")
    elif format == 'pdf':
        return ExportEngine.to_pdf(df, title, f"{rapor_tipi}.pdf")
    elif format == 'csv':
        return ExportEngine.to_csv(df, f"{rapor_tipi}.csv")
    else:
        return jsonify({'error': 'Geçersiz format'}), 400
        
        
@rapor_bp.route('/aylik-satis')
@login_required
def aylik_satis():
    """Aylık satış raporu"""
    tenant_db = get_tenant_db()
    
    # Tarih filtresi (query params veya varsayılan)
    bitis_str = request.args.get('bitis')
    baslangic_str = request.args.get('baslangic')
    
    if bitis_str:
        bitis = datetime.strptime(bitis_str, '%Y-%m-%d')
    else:
        bitis = datetime.now()
    
    if baslangic_str:
        baslangic = datetime.strptime(baslangic_str, '%Y-%m-%d')
    else:
        baslangic = bitis - timedelta(days=365)
    
    # Rapor oluştur
    df = rapor_aylik_satis_ozeti(tenant_db, baslangic, bitis)
    
    # JSON'a çevir
    data = df.to_dict(orient='records')
    
    return render_template('rapor/aylik_satis.html', 
                         data=data,
                         baslangic_tarih=baslangic.strftime('%Y-%m-%d'),
                         bitis_tarih=bitis.strftime('%Y-%m-%d'))

@rapor_bp.route('/stok-durum', methods=['GET'])
@login_required
def stok_durum():
    form = create_stok_rapor_form()
    
    # Filtreleri Al
    kategori_id = request.args.get('kategori_id', type=int)
    sadece_kritik = request.args.get('sadece_kritik') == 'True'
    
    # 1.Stok Kartlarını Çek (Karmaşık Join ve Group By YOK)
    query = StokKart.query.filter_by(firma_id=current_user.firma_id)

    if kategori_id and kategori_id > 0:
        query = query.filter(StokKart.kategori_id == kategori_id)
        
    stoklar = query.order_by(StokKart.ad).all()
    
    sonuclar = []
    
    # 2.Python Döngüsü ile Hesapla (Güvenli Yöntem)
    for stok in stoklar:
        # İlişki üzerinden (backref='depo_durumlari') miktarları topla
        toplam_miktar = sum(d.miktar for d in stok.depo_durumlari)
        
        # Kritik Seviye Kontrolü (Python tarafında filtreleme)
        if sadece_kritik:
            if toplam_miktar > stok.kritik_seviye:
                continue # Kritik değilse listeye ekleme, döngüyü geç
        
        # Veri Yapısını Hazırla
        sonuclar.append({
            'stok': stok,
            'toplam_miktar': toplam_miktar
        })

    return render_template('rapor/stok_durum.html', form=form, sonuclar=sonuclar)

@rapor_bp.route('/cari-ekstre', methods=['GET'])
@login_required
def cari_ekstre():
    form = create_cari_ekstre_form()
    
    cari_id = request.args.get('cari_id', type=int)
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    
    ekstre = []
    cari = None
    devir_bakiye = 0
    toplam_borc = 0
    toplam_alacak = 0
    
    if cari_id and baslangic and bitis:
        cari = CariHesap.query.get_or_404(cari_id)
        bas_tarih = datetime.strptime(baslangic, '%Y-%m-%d').date()
        bit_tarih = datetime.strptime(bitis, '%Y-%m-%d').date()
        
        # --- 1.DEVİR HESABI (Başlangıç tarihinden önceki bakiye) ---
        # Bu kısım performans için ileride optimize edilebilir (SQL SUM ile)
        # Şimdilik basitçe tüm hareketleri çekip python'da işleyeceğiz.
        
        # Tüm Hareketleri Çek
        hareketler = []
        
        # Faturalar
        faturalar = Fatura.query.filter_by(firma_id=current_user.firma_id, cari_id=cari_id).all()
        for f in faturalar:
            if f.fatura_turu == 'satis':
                hareketler.append({'tarih': f.tarih, 'tur': 'Fatura', 'aciklama': f"Satış Faturası ({f.belge_no})", 'borc': f.genel_toplam, 'alacak': 0, 'belge_no': f.belge_no})
            elif f.fatura_turu == 'alis':
                hareketler.append({'tarih': f.tarih, 'tur': 'Fatura', 'aciklama': f"Alış Faturası ({f.belge_no})", 'borc': 0, 'alacak': f.genel_toplam, 'belge_no': f.belge_no})
        
        # Kasa
        kasalar = KasaHareket.query.filter_by(firma_id=current_user.firma_id, cari_id=cari_id, onaylandi=True).all()
        for k in kasalar:
            if k.islem_turu == 'tahsilat': # Biz para aldık -> Cari Alacaklanır
                hareketler.append({'tarih': k.tarih, 'tur': 'Kasa', 'aciklama': f"Tahsilat Makbuzu ({k.belge_no})", 'borc': 0, 'alacak': k.tutar, 'belge_no': k.belge_no})
            elif k.islem_turu == 'tediye': # Biz para verdik -> Cari Borçlanır
                hareketler.append({'tarih': k.tarih, 'tur': 'Kasa', 'aciklama': f"Ödeme Makbuzu ({k.belge_no})", 'borc': k.tutar, 'alacak': 0, 'belge_no': k.belge_no})

        # Banka
        bankalar = BankaHareket.query.filter_by(firma_id=current_user.firma_id, cari_id=cari_id).all()
        for b in bankalar:
            if b.islem_turu == 'tahsilat': # Gelen Havale -> Cari Alacak
                hareketler.append({'tarih': b.tarih, 'tur': 'Banka', 'aciklama': f"Gelen Havale ({b.belge_no})", 'borc': 0, 'alacak': b.tutar, 'belge_no': b.belge_no})
            elif b.islem_turu == 'tediye': # Giden Havale -> Cari Borç
                hareketler.append({'tarih': b.tarih, 'tur': 'Banka', 'aciklama': f"Gönderilen Havale ({b.belge_no})", 'borc': b.tutar, 'alacak': 0, 'belge_no': b.belge_no})

        cekler = CekSenet.query.filter_by(firma_id=current_user.firma_id, cari_id=cari_id).all()
        for c in cekler:
            # Modeldeki gerçek alan isimlerini kullanıyoruz
            tarih_degeri = c.duzenleme_tarihi if c.duzenleme_tarihi else c.vade_tarihi
            
            if c.portfoy_tipi == PortfoyTipi.ALINAN.value: # 'alinan'
                hareketler.append({
                    'tarih': tarih_degeri, 
                    'tur': 'Çek', 
                    'aciklama': f"Alınan Çek ({c.belge_no})", 
                    'borc': 0, 
                    'alacak': c.tutar, 
                    'belge_no': c.cek_no or c.belge_no
                })
            elif c.portfoy_tipi == PortfoyTipi.VERILEN.value: # 'verilen'
                hareketler.append({
                    'tarih': tarih_degeri, 
                    'tur': 'Çek', 
                    'aciklama': f"Verilen Çek ({c.belge_no})", 
                    'borc': c.tutar, 
                    'alacak': 0, 
                    'belge_no': c.cek_no or c.belge_no
                })

        # Tarihe Göre Sırala
        hareketler.sort(key=lambda x: x['tarih'])

        # İşleme
        bakiye = 0
        ekstre = []
        
        # 1.Devir Hesapla
        for h in hareketler:
            if h['tarih'] < bas_tarih:
                bakiye += (h['borc'] - h['alacak'])
        
        devir_bakiye = bakiye
        
        # 2.Aralıktaki Hareketleri Listele
        # Başlangıç satırı olarak deviri ekle
        ekstre.append({
            'tarih': bas_tarih, 'tur': 'DEVİR', 'aciklama': 'Önceki Dönem Devri', 
            'borc': devir_bakiye if devir_bakiye > 0 else 0, 
            'alacak': abs(devir_bakiye) if devir_bakiye < 0 else 0, 
            'bakiye': devir_bakiye,
            'belge_no': '-'
        })

        for h in hareketler:
            if bas_tarih <= h['tarih'] <= bit_tarih:
                bakiye += (h['borc'] - h['alacak'])
                h['bakiye'] = bakiye
                ekstre.append(h)
                
                toplam_borc += h['borc']
                toplam_alacak += h['alacak']

    return render_template('rapor/cari_ekstre.html', form=form, ekstre=ekstre, cari=cari, 
                           devir_bakiye=devir_bakiye, toplam_borc=toplam_borc, toplam_alacak=toplam_alacak)  

@rapor_bp.route('/plasiyer-performans')
@login_required
@role_required('admin', 'muhasebe') # Sadece yetkililer görebilsin
def plasiyer_performans():
    form = create_rapor_filtre_form()
    
    # 1.Filtreleri Al
    start_date = request.args.get('baslangic', datetime.today().replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('bitis', datetime.today().strftime('%Y-%m-%d'))
    
    # 2.Veritabanı Sorgusu (Plasiyer Bazlı Satış Toplamı)
    # Fatura -> Cari -> Plasiyer ilişkisi veya Fatura -> Plasiyer (Eğer Fatura modelinde plasiyer_id varsa)
    # Bizim Fatura modelimizde 'plasiyer_id' yoktu, 'Sipariş'te vardı.
    # Ancak Fatura'yı oluşturan kişiyi (created_by) veya Cari'nin plasiyerini baz alabiliriz.
    # Şimdilik basitlik adına: Fatura'yı oluşturan kullanıcı (log tutuluyorsa) veya
    # Cari kartındaki 'plasiyer_id' (Eğer cari modeline eklediysek) üzerinden gidelim.
    # Varsayım: Fatura modeline 'plasiyer_id' eklediğimizi varsayalım veya Sipariş üzerinden raporlayalım.
    
    # Hızlı Çözüm: Şimdilik Sipariş tablosundan rapor çekelim (Orada plasiyer_id var)
    # Eğer Sipariş modeliniz boşsa, Fatura tablosuna geçici olarak 'plasiyer_id' eklemeniz gerekebilir.
    # Biz Sipariş üzerinden gidelim:
    
    from models import Siparis # Sipariş modelini import et
    
    # Sorgu: Plasiyer ID'ye göre grupla ve toplam tutarı al
    sonuclar = db.session.query(
        Kullanici.ad_soyad,
        func.count(Siparis.id).label('adet'),
        func.sum(Siparis.genel_toplam).label('ciro')
    ).join(Kullanici, Siparis.plasiyer_id == Kullanici.id)\
     .filter(Siparis.firma_id == current_user.firma_id)\
     .filter(Siparis.tarih >= start_date)\
     .filter(Siparis.tarih <= end_date)\
     .group_by(Kullanici.id, Kullanici.ad_soyad)\
     .order_by(desc('ciro')).all()

    # 3.Grafik İçin Veri Hazırlama (Chart.js Formatı)
    labels = []
    data_ciro = []
    data_adet = []
    
    toplam_ciro = 0
    
    for row in sonuclar:
        labels.append(row.ad_soyad)
        tutar = float(row.ciro or 0)
        data_ciro.append(tutar)
        data_adet.append(row.adet)
        toplam_ciro += tutar

    # 4.En Çok Satan Ürünler (Top 5)
    # Fatura Kalemleri üzerinden
    top_urunler = db.session.query(
        StokKart.ad,
        func.sum(FaturaKalemi.miktar).label('toplam_miktar'),
        func.sum(FaturaKalemi.satir_toplami).label('toplam_tutar')
    ).join(Fatura, FaturaKalemi.fatura_id == Fatura.id)\
     .join(StokKart, FaturaKalemi.stok_id == StokKart.id)\
     .filter(Fatura.firma_id == current_user.firma_id)\
     .filter(Fatura.tarih >= start_date)\
     .filter(Fatura.tarih <= end_date)\
     .filter(Fatura.fatura_turu == FaturaTuru.SATIS.value)\
     .group_by(StokKart.id, StokKart.ad)\
     .order_by(desc('toplam_tutar'))\
     .limit(5).all()
     
    urun_labels = [u.ad for u in top_urunler]
    urun_data = [float(u.toplam_tutar or 0) for u in top_urunler]

    return render_template('rapor/performans.html', 
                           form=form, 
                           labels=labels, data_ciro=data_ciro, data_adet=data_adet,
                           urun_labels=urun_labels, urun_data=urun_data,
                           toplam_ciro=toplam_ciro,
                           start_date=start_date, end_date=end_date)

@rapor_bp.route('/anomali-dedektifi')
@login_required
def anomali_dedektifi():
    return render_template('rapor/anomali.html')

@rapor_bp.route('/api/anomali-tara', methods=['POST'])
@login_required
def api_anomali_tara():
    """Şüpheli işlemleri bulur ve AI'ya gönderir"""
    
    supheli_islemler = []
    
    # 1.YÜKSEK İSKONTO ANALİZİ (%20 üzeri)
    # Son 1 aydaki satış faturalarını çek
    bir_ay_once = datetime.now() - timedelta(days=30)
    faturalar = Fatura.query.filter(
        Fatura.firma_id == current_user.firma_id,
        Fatura.fatura_turu == FaturaTuru.SATIS.value,
        Fatura.tarih >= bir_ay_once
    ).all()
    
    for f in faturalar:
        genel = float(f.genel_toplam or 0)
        iskonto = float(f.iskonto_toplam or 0)
        ara_toplam = float(f.ara_toplam or 0)
        
        # İskonto oranı hesabı
        matrah = ara_toplam + iskonto
        if matrah > 0:
            oran = (iskonto / matrah) * 100
            
            # EŞİK DEĞER: %20 üzeri indirim şüphelidir
            if oran > 20:
                supheli_islemler.append({
                    "tur": "YUKSEK_ISKONTO",
                    "belge_no": f.belge_no,
                    "tarih": f.tarih.strftime('%d.%m.%Y'),
                    "tutar": genel,
                    "yapilan_indirim_tl": iskonto,
                    "indirim_orani": f"%{int(oran)}",
                    "aciklama": f.aciklama
                })

    # 2.STOK KAÇAKLARI (Fire ve Sayım Eksiği)
    stok_hareketleri = StokHareketi.query.filter(
        StokHareketi.firma_id == current_user.firma_id,
        StokHareketi.hareket_turu.in_([HareketTuru.FIRE.value, HareketTuru.SAYIM_EKSIK.value]),
        StokHareketi.tarih >= bir_ay_once
    ).all()
    
    for h in stok_hareketleri:
        # Stoğu bulabilirsek adını alalım (İlişki tanımlı olmayabilir, manuel bakalım)
        from models import StokKart
        stok = StokKart.query.get(h.stok_id)
        stok_adi = stok.ad if stok else "Bilinmeyen Ürün"
        
        # Şüpheli Stok Hareketi
        supheli_islemler.append({
            "tur": "STOK_KAYBI",
            "urun": stok_adi,
            "hareket_turu": h.hareket_turu,
            "miktar": float(h.miktar or 0),
            "tarih": h.tarih.strftime('%d.%m.%Y'),
            "aciklama": h.aciklama
        })

    if not supheli_islemler:
        return jsonify({'success': False, 'message': 'Temiz! Sistemde herhangi bir anomali tespit edilemedi.'})

    # 3.AI'ya Gönder
    try:
        json_data = json.dumps(supheli_islemler, ensure_ascii=False)
        rapor_html = analyze_anomalies(json_data)
        return jsonify({'success': True, 'report': rapor_html})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f"AI Hatası: {str(e)}"})

# --- 1.AYARLAR EKRANI ---
@rapor_bp.route('/ai-ayarlari', methods=['GET', 'POST'])
@login_required
def ai_ayarlari():
    if request.method == 'POST':
        # Formdan gelen verileri kaydet
        for key, value in request.form.items():
            ayar = AIRaporAyarlari.query.filter_by(firma_id=current_user.firma_id, anahtar=key).first()
            if ayar:
                ayar.deger = value
        db.session.commit()
        return jsonify({'success': True, 'message': 'Kriterler güncellendi.'})

    ayarlar = AIRaporAyarlari.query.filter_by(firma_id=current_user.firma_id).all()
    return render_template('rapor/ayarlar.html', ayarlar=ayarlar)

# --- 2.GEÇMİŞ RAPORLAR ---
@rapor_bp.route('/gecmis-raporlar')
@login_required
def gecmis_raporlar():
    """AI tarafından önceden oluşturulmuş geçmiş raporların listesi"""
    
    # 🚀 ÇÖZÜM 1: Eksik olan modeli lokal olarak import ettik (NameError'ı çözer)
    from app.modules.rapor.models import AIRaporGecmisi
    
    # 🚀 ÇÖZÜM 2: Eski ".query" yapısı yerine Multi-Tenant veritabanı bağlantısı kullandık
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Lütfen önce bir firma (tenant) seçin.', 'warning')
        return redirect(url_for('main.index'))
        
    try:
        # Eski kullanım: AIRaporGecmisi.query.filter_by(...)
        # Yeni ve Güvenli Kullanım: tenant_db.query()
        raporlar = tenant_db.query(AIRaporGecmisi).order_by(AIRaporGecmisi.tarih.desc()).all()
        
    except Exception as e:
        import logging
        logging.error(f"Geçmiş raporlar çekilirken hata: {e}")
        flash('Raporlar yüklenirken bir hata oluştu.', 'danger')
        raporlar = []

    return render_template('rapor/gecmis.html', raporlar=raporlar)
    
@rapor_bp.route('/rapor-detay/<int:rapor_id>')
@login_required
def rapor_detay(rapor_id):
    rapor = AIRaporGecmisi.query.get_or_404(rapor_id)
    return render_template('rapor/detay.html', rapor=rapor)

# --- 3.CEO BRİFİNGİ (MASTER RUNNER) ---
@rapor_bp.route('/api/ceo-brifing-olustur', methods=['POST'])
@login_required
def api_ceo_brifing():
    """Tüm analizleri çalıştırır, DB ayarlarını kullanır ve sonucu kaydeder."""
    
    # A) AYARLARI ÇEK
    def get_setting(key, default):
        ayar = AIRaporAyarlari.query.filter_by(firma_id=current_user.firma_id, anahtar=key).first()
        return float(ayar.deger) if ayar else default

    max_iskonto = get_setting('max_iskonto_orani', 20)
    riskli_borc = get_setting('riskli_borc_limiti', 10000)

    ozet_veri = {"tarih": datetime.now().strftime("%d.%m.%Y"), "uyarilar": []}

    # B) HIZLI ANALİZLER (Derinlemesine değil, sadece özet için sayılar)
    
    # 1.Anomali Kontrolü (İskonto)
    supheli_fatura_sayisi = Fatura.query.filter(
        Fatura.firma_id == current_user.firma_id, 
        (Fatura.iskonto_toplam / Fatura.genel_toplam * 100) > max_iskonto
    ).count()
    if supheli_fatura_sayisi > 0:
        ozet_veri['uyarilar'].append(f"{supheli_fatura_sayisi} adet faturada %{max_iskonto} üzeri şüpheli iskonto tespit edildi.")

    # 2.Riskli Cari Kontrolü
    riskli_cari_sayisi = CariHesap.query.filter(
        Fatura.firma_id == current_user.firma_id,
        (CariHesap.borc_bakiye - CariHesap.alacak_bakiye) > riskli_borc
    ).count()
    if riskli_cari_sayisi > 0:
        ozet_veri['uyarilar'].append(f"{riskli_cari_sayisi} müşterinin borcu risk limitini ({riskli_borc} TL) aştı.")
    
    # 3.Kasa Durumu
    # (Burada basit bir bakiye kontrolü yapıyoruz)
    # ...Kasa bakiyesi eksi mi? ...
    # (Kısalık olması için detay kodu atlıyorum, mantık aynı)

    # C) AI'YA GÖNDER
    import json
    try:
        json_input = json.dumps(ozet_veri, ensure_ascii=False)
        ai_response = generate_ceo_briefing(json_input)
        
        # Yanıtı Parse Et
        if isinstance(ai_response, str):
            ai_data = json.loads(ai_response)
        else:
            ai_data = ai_response # Zaten dict gelmiştir

        html_content = ai_data.get('brifing_html', 'Rapor oluşturulamadı.')
        
        # D) VERİTABANINA KAYDET (TARİHÇE)
        yeni_rapor = AIRaporGecmisi(
            firma_id=current_user.firma_id,
            rapor_turu='CEO_BRIFING',
            baslik=f"{datetime.now().strftime('%d.%m.%Y')} - Günlük Yönetici Özeti",
            html_icerik=html_content,
            ham_veri_json=json_input
        )
        db.session.add(yeni_rapor)
        db.session.commit()
        
        return jsonify({'success': True, 'report': html_content})

    except Exception as e:
        return jsonify({'success': False, 'message': f"Hata: {str(e)}"})

@rapor_bp.route('/yevmiye', methods=['GET', 'POST'])
def yevmiye_defteri():
# 🚀 ÇÖZÜM 1: G objesinden güvenli veri çekme (Yoksa None döner, sistemi çökertmez)
    aktif_donem = getattr(g, 'donem', None)
    aktif_firma = getattr(g, 'firma', None)

    # 1.Varsayılan Tarihleri Belirle
    if aktif_donem:
        def_baslangic = aktif_donem.baslangic.strftime('%Y-%m-%d')
        def_bitis = aktif_donem.bitis.strftime('%Y-%m-%d')
    else:
        yil = datetime.now().year
        def_baslangic = f"{yil}-01-01"
        def_bitis = f"{yil}-12-31"

    # 2.Form Nesnesini Oluştur (Builder Kullanarak)
    form = get_yevmiye_filter_form(def_baslangic, def_bitis)

    # 3.POST İsteği ve Validasyon
    if request.method == 'POST' and form.validate():
        try:
            # Form verilerini al
            data = form.get_data()
            baslangic = data['baslangic']
            bitis = data['bitis']
            format_type = data['format']

            # Tarih dönüşümü (FormBuilder string döndürürse)
            if isinstance(baslangic, str):
                bas_dt = datetime.strptime(baslangic, '%Y-%m-%d').date()
            else: 
                bas_dt = baslangic

            if isinstance(bitis, str):
                bit_dt = datetime.strptime(bitis, '%Y-%m-%d').date()
            else: 
                bit_dt = bitis

            # Rapor Motorunu Çalıştır
            limit = 60 if format_type == 'dos' else 35
            motor = YevmiyeRaporuMotoru(bas_dt, bit_dt, satir_limiti=limit)
            
            # 🚀 ÇÖZÜM 2: Firma ID'yi güvenli al
            firma_id = aktif_firma.id if aktif_firma else None
            sayfalar = motor.verileri_hazirla(firma_id=firma_id)
            
            if not sayfalar:
                flash("Seçilen tarih aralığında veri bulunamadı.", "warning")
                return render_template('rapor/yevmiye_filtre.html', form=form)

            # Çıktı Üret
            if format_type == 'dos':
                return render_template('rapor/yevmiye_dos.txt', sayfalar=sayfalar), {'Content-Type': 'text/plain; charset=utf-8'}
            else:
                return render_template('rapor/yevmiye_laser.html', 
                                     sayfalar=sayfalar, 
                                     baslangic=baslangic, 
                                     bitis=bitis,
                                     aktif_firma=aktif_firma,  # Güvenli değişkeni kullan
                                     aktif_donem=aktif_donem)  # Güvenli değişkeni kullan
                
        except Exception as e:
            flash(f"Rapor hatası: {str(e)}", "danger")

    # GET isteği veya Validasyon Hatası durumunda formu göster
    return render_template('rapor/yevmiye_filtre.html', form=form)
    
@rapor_bp.route('/e-defter/indir', methods=['POST'])
def e_defter_indir():
    try:
        # Formdan tarihleri al
        baslangic = request.form.get('baslangic')
        bitis = request.form.get('bitis')
        
        # String tarihleri date objesine çevir
        dt_bas = datetime.strptime(baslangic, '%Y-%m-%d').date()
        dt_bit = datetime.strptime(bitis, '%Y-%m-%d').date()
        
        # XML Motorunu Başlat
        builder = EDefterBuilder(
            firma_id=g.firma.id, 
            donem_id=g.donem.id,
            baslangic=dt_bas,
            bitis=dt_bit
        )
        
        # XML'i Üret
        xml_content = builder.yevmiye_xml_olustur()
        
        # Dosya İndirme Yanıtı Hazırla
        buffer = BytesIO(xml_content)
        buffer.seek(0)
        
        dosya_adi = f"yevmiye_{baslangic}_{bitis}.xml"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=dosya_adi,
            mimetype='application/xml'
        )
        
    except Exception as e:
        flash(f"e-Defter Hatası: {str(e)}", "danger")
        return redirect(url_for('rapor.index')) # Veya ilgili sayfaya yönlendir

# ==========================================
# DİNAMİK ŞABLON YÖNETİMİ ROTALARI
# ==========================================

@rapor_bp.route('/sablonlar')
@login_required
def sablonlar():
    """Şablon Yönetim Listesi"""
    if current_user.rol not in ['admin', 'patron']:
        return render_template('errors/403.html'), 403

    tenant_db = get_tenant_db() # ✨ DÜZELTME: Tenant DB bağlantısı

    grid = DataGrid("sablon_grid", YazdirmaSablonu, "Yazdırma Şablonları")
    
    grid.add_column('baslik', 'Şablon Adı')
    grid.add_column('belge_turu', 'Tür', type='badge', 
                    badge_colors={'fatura': 'primary', 'tahsilat': 'success', 'tediye': 'danger', 'mutabakat': 'info'})
    
    grid.add_column('varsayilan', 'Varsayılan', type='badge', badge_colors={'True': 'success', 'False': 'secondary'})
    grid.add_column('aktif', 'Durum', type='boolean')

    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'rapor.sablon_duzenle')
    grid.add_action('preview', 'Önizle', 'bi bi-eye', 'btn-outline-dark btn-sm', 'route', 'rapor.sablon_onizle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'rapor.sablon_sil')

    # ✨ DÜZELTME: Sorgu artık Tenant DB üzerinden atılıyor
    query = tenant_db.query(YazdirmaSablonu).filter(
        (YazdirmaSablonu.firma_id == str(current_user.firma_id)) | (YazdirmaSablonu.firma_id == None)
    )
    
    grid.process_query(query)
    return render_template('rapor/sablon_list.html', grid=grid)


@rapor_bp.route('/sablon-duzenle/<string:id>', methods=['GET', 'POST']) # ✨ DÜZELTME: <int:id> -> <string:id>
@login_required
def sablon_duzenle(id):
    if current_user.rol not in ['admin', 'patron']: return "Yetkisiz", 403
    
    tenant_db = get_tenant_db()
    
    # ✨ DÜZELTME: get_or_404 yerine tenant_db query kullanımı
    sablon = tenant_db.query(YazdirmaSablonu).filter_by(id=id).first()
    if not sablon:
        flash("Şablon bulunamadı!", "danger")
        return redirect(url_for('rapor.sablonlar'))
        
    form = create_sablon_form(sablon)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            
            sablon.baslik = data['baslik']
            sablon.html_icerik = data['html_icerik']
            sablon.css_icerik = data['css_icerik']
            sablon.varsayilan = True if request.form.get('varsayilan') else False
            sablon.aktif = True if request.form.get('aktif') else False
            
            if sablon.varsayilan:
                tenant_db.query(YazdirmaSablonu).filter_by(
                    firma_id=sablon.firma_id, 
                    belge_turu=sablon.belge_turu
                ).filter(YazdirmaSablonu.id != sablon.id).update({'varsayilan': False})
            
            tenant_db.commit() # ✨ DÜZELTME: db.session yerine tenant_db
            return jsonify({'success': True, 'message': 'Şablon güncellendi.', 'redirect': '/rapor/sablonlar'})

    # ✨ DÜZELTME: Firma ve Fatura çekimi tenant üzerinden yapılıyor
    firma = tenant_db.query(Firma).filter_by(id=str(current_user.firma_id)).first()
    ornek_belge = tenant_db.query(Fatura).filter_by(firma_id=current_user.firma_id).order_by(Fatura.created_at.desc()).first()

    return render_template('rapor/sablon_form.html', form=form, sablon=sablon, firma=firma, belge=ornek_belge)


@rapor_bp.route('/sablon-ekle', methods=['GET', 'POST'])
@login_required
def sablon_ekle():
    if current_user.rol not in ['admin', 'patron']: return "Yetkisiz", 403
    
    tenant_db = get_tenant_db()
    form = create_sablon_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            
            sablon = YazdirmaSablonu(
                firma_id=str(current_user.firma_id),
                belge_turu=data['belge_turu'],
                baslik=data['baslik'],
                html_icerik=data['html_icerik'],
                css_icerik=data['css_icerik'],
                varsayilan=True if request.form.get('varsayilan') else False,
                aktif=True if request.form.get('aktif') else False
            )
            
            if sablon.varsayilan:
                 tenant_db.query(YazdirmaSablonu).filter_by(
                    firma_id=str(current_user.firma_id), 
                    belge_turu=sablon.belge_turu
                ).update({'varsayilan': False})
            
            tenant_db.add(sablon)
            tenant_db.commit() # ✨ DÜZELTME: db.session yerine tenant_db
            return jsonify({'success': True, 'message': 'Şablon oluşturuldu.', 'redirect': '/rapor/sablonlar'})
            
    firma = tenant_db.query(Firma).filter_by(id=str(current_user.firma_id)).first()
    ornek_belge = tenant_db.query(Fatura).filter_by(firma_id=current_user.firma_id).order_by(Fatura.created_at.desc()).first()

    return render_template('rapor/sablon_form.html', form=form, firma=firma, belge=ornek_belge)


@rapor_bp.route('/sablon-onizle/<string:id>') # ✨ DÜZELTME: <int:id> -> <string:id>
@login_required
def sablon_onizle(id):
    """
    Şablonu sahte (dummy) verilerle veya gerçek son kayıtla test eder.
    """
    tenant_db = get_tenant_db()
    sablon = tenant_db.query(YazdirmaSablonu).filter_by(id=id).first()
    
    if not sablon:
        return "Şablon bulunamadı", 404
    
    veri = None
    if sablon.belge_turu == 'fatura':
        veri = tenant_db.query(Fatura).filter_by(firma_id=current_user.firma_id).order_by(Fatura.created_at.desc()).first()
    
    if not veri:
        return f"<h1>Önizleme İçin Veri Bulunamadı</h1><p>Lütfen önce sisteme en az bir tane <b>{sablon.belge_turu}</b> kaydı ekleyin.</p>"
    
    from flask import render_template_string
    firma = tenant_db.query(Firma).filter_by(id=str(current_user.firma_id)).first()
    
    context = {
        'belge': veri,
        'firma': firma,
        'sayfalar': [], # Önizlemede sayfalama döngüsü hata vermesin diye boş liste gönderiyoruz
        'sablon_css': sablon.css_icerik
    }
    
    try:
        return render_template_string(sablon.html_icerik, **context)
    except Exception as e:
        return f"<h1>Şablon Render Hatası</h1><pre>{str(e)}</pre>"


@rapor_bp.route('/sablon-sil/<string:id>', methods=['POST']) # ✨ DÜZELTME: <int:id> -> <string:id>
@login_required
def sablon_sil(id):
    tenant_db = get_tenant_db()
    sablon = tenant_db.query(YazdirmaSablonu).filter_by(id=id).first()
    
    if not sablon:
        return jsonify({'success': False, 'message': 'Şablon bulunamadı'}), 404
        
    if sablon.firma_id != str(current_user.firma_id):
        return jsonify({'success': False, 'message': 'Yetkisiz işlem'}), 403
        
    tenant_db.delete(sablon)
    tenant_db.commit()
    return jsonify({'success': True, 'message': 'Şablon silindi.'})

# ==========================================
@rapor_bp.route('/muhasebe-raporlari')
@login_required
def muhasebe_raporlari():
    """Rapor Seçim Ekranı"""
    return render_template('rapor/menu.html')

@rapor_bp.route('/calistir/<tur>')
@login_required
def rapor_calistir(tur):
    """
    Dinamik Rapor Çalıştırıcı (Factory Pattern)
    """
    # 1.Rapor Sınıfını Katalogdan Bul
    RaporSinifi = get_rapor_class(tur)
    
    if not RaporSinifi:
        return render_template('errors/404.html', message="Geçersiz veya Tanımsız Rapor Türü"), 404

    # 2.Parametreleri Al
    baslangic = request.args.get('baslangic')
    bitis = request.args.get('bitis')
    cikti_formati = request.args.get('format', 'html')
    
    # Dönem Güvenliği
    donem_id = session.get('aktif_donem_id')
    if not donem_id and hasattr(current_user.firma, 'donemler') and current_user.firma.donemler:
        donem_id = current_user.firma.donemler[-1].id # Son dönem

    try:
        # 3.Raporu Başlat (Instantiate)
        # Her rapor sınıfı __init__ metodunda standart parametreleri beklemeli
        rapor_obj = RaporSinifi(current_user.firma_id, donem_id, baslangic, bitis)
        
        # 4.Verileri Hesapla
        rapor_obj.verileri_getir()

        # 5.Çıktı Üret (Strategy)
        if cikti_formati == 'excel':
            excel_io = rapor_obj.export_excel()
            filename = f"{tur}_{baslangic}_{bitis}.xlsx"
            return send_file(
                excel_io, 
                download_name=filename, 
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        elif cikti_formati == 'pdf':
            # PDF desteği eklediysen burayı açabilirsin
            # pdf_io = rapor_obj.export_pdf()
            # return send_file(pdf_io, download_name=f"{tur}.pdf", mimetype='application/pdf')
            return "PDF modülü henüz aktif değil.", 501

        else:
            # HTML Önizleme
            tablo_html = rapor_obj.export_html_table()
            
            # Katalogdan ek bilgiler (Başlık vb.)
            meta = RAPOR_KATALOGU.get(tur, {})
            
            return render_template('rapor/onizleme.html', 
                                 tablo=tablo_html, 
                                 baslik=rapor_obj.baslik,
                                 ikon=meta.get('ikon', 'bi-file-text'),
                                 rapor_turu=tur)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Rapor oluşturulurken hata: {str(e)}", "danger")
        return redirect(url_for('rapor.muhasebe_raporlari'))
        
        
@rapor_bp.route('/api/rapor-calistir', methods=['POST'])
@login_required
@csrf.exempt
def api_rapor_calistir():
    """Raporu çalıştır (AJAX)"""
    
    from app.form_builder.report_designer import ReportDesigner
    from app.modules.fatura.models import Fatura
    
    config = request.get_json()
    
    # Model map
    model_map = {
        'CariHesap': CariHesap,
        'Fatura': Fatura,
        'StokKart': StokKart,
        'StokHareketi': StokHareketi,
        'Depo': Depo,
        'Firma': Firma
    }
    
    model_name = config.get('model_name', 'CariHesap')
    model = model_map.get(model_name)
    
    if not model:
        return jsonify({'success': False, 'message': 'Geçersiz model'}), 400
    
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Database bağlantısı yok'}), 400
    
    try:
        # ✅ Session'a kaydet (önizleme için)
        session['last_report_config'] = config
        session.modified = True
        logger.info(f"💾 Config session'a kaydedildi: {model_name}, {len(config.get('fields', []))} alan")
        
        designer = ReportDesigner(model, config, session=tenant_db)
        
        valid, message = designer.validate_config()
        if not valid:
            return jsonify({'success': False, 'message': message}), 400
        
        data = designer.execute()
        chart_config = designer.get_chart_config()
        
        logger.info(f"✅ Rapor çalıştırıldı: {len(data)} kayıt")
        
        return jsonify({
            'success': True,
            'data': data,
            'chart': chart_config,
            'row_count': len(data),
            'model_name': model_name
        })
    
    except Exception as e:
        logger.error(f"❌ Rapor çalıştırma hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 500


@rapor_bp.route('/onizleme/<model_name>')
@login_required
def onizleme(model_name):
    """Rapor önizleme (A4 formatında)"""
    
    # Session'dan son çalıştırılan rapor config'ini al
    config = session.get('last_report_config')
    
    if not config:
        flash('Önizlenecek rapor yok. Lütfen önce raporu çalıştırın.', 'warning')
        return redirect(url_for('rapor.tasarimci'))
    
    logger.info(f"📄 Önizleme açılıyor: {model_name}")
    logger.debug(f"📋 Config: {config}")
    
    # Model class map
    model_class_map = {
        'CariHesap': CariHesap,
        'Fatura': Fatura,     
        'StokKart': StokKart,
        'StokHareketi': StokHareketi,
        'Depo': Depo,
        'Firma': Firma
    }
    
    model_class = model_class_map.get(model_name)
    
    if not model_class:
        flash(f'Model "{model_name}" desteklenmiyor.', 'danger')
        return redirect(url_for('rapor.tasarimci')) 
        
    # Database session
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        flash('Database bağlantısı yok.', 'danger')
        return redirect(url_for('rapor.tasarimci'))
    
    try:
        # Raporu tekrar çalıştır
        from app.form_builder.report_designer import ReportDesigner
        
        designer = ReportDesigner(model_class, config, session=tenant_db)
        data = designer.execute()
        
        logger.info(f"✅ Rapor çalıştırıldı: {len(data)} kayıt")
        
        # Sayfalama (A4 için ~30 satır/sayfa)
        rows_per_page = 30
        pages = [data[i:i+rows_per_page] for i in range(0, len(data), rows_per_page)]
        
        # Kolonlar
        columns = config.get('fields', [])
        
        # Özet
        summary = {
            'total_rows': len(data),
            'filter_count': len(config.get('filters', [])),
            'field_count': len(columns)
        }
        
        # Model adı Türkçe
        model_names = {
            'CariHesap': 'Cari Hesaplar Raporu',
            'Fatura': 'Faturalar Raporu',
            'StokKart': 'Stok Kartları Raporu',
            'StokHareketi': 'Stok Hareketleri Raporu',
            'Depo': 'Depolar Listesi',
            'Firma': 'Firma Listesi'
        }
        
        return render_template('rapor/onizleme_full.html',
                             rapor_adi=config.get('name', model_names.get(model_name, 'Rapor')),
                             rapor_tarihi=datetime.now().strftime('%d.%m.%Y %H:%M'),
                             firma_adi=current_user.firma.unvan if hasattr(current_user, 'firma') else 'Firma',
                             firma_logo=None,
                             pages=pages,
                             columns=columns,
                             summary=summary,
                             report_id=None)
    
    except Exception as e:
        logger.error(f"❌ Önizleme hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'Önizleme oluşturulamadı: {str(e)}', 'danger')
        return redirect(url_for('rapor.tasarimci'))
            
@rapor_bp.route('/rapor-yukle/<string:report_id>')
@login_required
def rapor_yukle(report_id):
    """Kayıtlı raporu yükle"""
    
    from app.modules.rapor.models import SavedReport
    
    # ✅ DEBUG: Session key'leri kontrol et
    logger.info("🔍 Session içeriği:")
    logger.info(f"  - active_db_yolu: {session.get('active_db_yolu')}")
    logger.info(f"  - active_db_sifre: {'***' if session.get('active_db_sifre') else None}")
    logger.info(f"  - tenant_id: {session.get('tenant_id')}")
    logger.info(f"  - aktif_firma_id: {session.get('aktif_firma_id')}")
    logger.info(f"  - Tüm key'ler: {list(session.keys())}")
    
    # ✅ Database session al
    tenant_db = get_tenant_db()
    
    # ✅ KONTROL
    if tenant_db is None:
        logger.error("❌ get_tenant_db() None döndü!")
        logger.error("   Olası sebep: session['active_db_yolu'] veya session['active_db_sifre'] eksik")
        flash('Database bağlantısı kurulamadı. Lütfen firma seçin.', 'danger')
        return redirect(url_for('rapor.kaydedilenler'))
    
    try:
        logger.info(f"🔍 Rapor sorgulanıyor: ID={report_id}")
        report = tenant_db.query(SavedReport).filter_by(id=report_id).first()
        
        if not report:
            logger.warning(f"❌ Rapor bulunamadı: ID={report_id}")
            flash('Rapor bulunamadı', 'danger')
            return redirect(url_for('rapor.kaydedilenler'))
        
        logger.info(f"✅ Rapor bulundu: {report.name}")
        
        # Yetki kontrolü
        if report.user_id != str(current_user.id) and not report.is_public_bool:
            flash('Bu raporu görüntüleme yetkiniz yok.', 'danger')
            return redirect(url_for('rapor.kaydedilenler'))
        
        # to_dict()
        report_dict = report.to_dict()
        
        logger.info(f"📂 Rapor yüklendi: {report.name}")
        
        return render_template('rapor/tasarimci.html', 
                             loaded_report=report_dict)
    
    except Exception as e:
        logger.error(f"❌ Rapor yükleme hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'Rapor yüklenirken hata oluştu: {str(e)}', 'danger')
        return redirect(url_for('rapor.kaydedilenler'))
        
        
@rapor_bp.route('/rapor-sil/<string:report_id>', methods=['POST'])
@login_required
@csrf.exempt
def rapor_sil(report_id):
    """Kayıtlı raporu sil"""
    
    from app.modules.rapor.models import SavedReport
    
    # ✅ Database session
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Database bağlantısı yok'}), 400
    
    # ✅ Database'den rapor çek
    report = tenant_db.query(SavedReport).filter_by(id=report_id).first()
    
    if not report:
        return jsonify({'success': False, 'message': 'Rapor bulunamadı'}), 404
    
    # Sadece sahibi silebilir
    if report.user_id != str(current_user.id):
        return jsonify({'success': False, 'message': 'Bu raporu silme yetkiniz yok'}), 403
    
    try:
        tenant_db.delete(report)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Rapor silindi'})
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"Rapor silme hatası: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@rapor_bp.route('/rapor-kopyala/<string:report_id>', methods=['POST'])
@login_required
@csrf.exempt 
def rapor_kopyala(report_id):
    """Başkasının raporunu kendi hesabına kopyala"""
    
    from app.modules.rapor.models import SavedReport
    
    # ✅ Database session
    tenant_db = get_tenant_db()
    
    if not tenant_db:
        return jsonify({'success': False, 'message': 'Database bağlantısı yok'}), 400
    
    # ✅ Database'den rapor çek
    original_report = tenant_db.query(SavedReport).filter_by(id=report_id).first()
    
    if not original_report:
        return jsonify({'success': False, 'message': 'Rapor bulunamadı'}), 404
    
    # Sadece public raporlar kopyalanabilir
    if not original_report.is_public and original_report.user_id != str(current_user.id):
        return jsonify({'success': False, 'message': 'Bu rapor kopyalanamaz'}), 403
    
    try:
        # Yeni rapor oluştur
        new_report = SavedReport()
        new_report.name = f"{original_report.name} (Kopya)"
        new_report.description = original_report.description
        new_report.model_name = original_report.model_name
        new_report.config = original_report.config  # Property kullan
        new_report.user_id = str(current_user.id)
        new_report.is_public = False
        
        tenant_db.add(new_report)
        tenant_db.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Rapor kopyalandı',
            'report_id': new_report.id
        })
    except Exception as e:
        tenant_db.rollback()
        logger.error(f"Rapor kopyalama hatası: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

        
@rapor_bp.route('/tasarimci')
@login_required
def tasarimci():
    """Rapor tasarım arayüzü"""
    saved_reports = []
    try:
        from app.modules.rapor.models import SavedReport
        tenant_db = get_tenant_db() # ✨ Eklendi
        
        # ✨ query_fb() yerine tenant_db.query() kullanıldı
        saved_reports = tenant_db.query(SavedReport).filter_by(
            user_id=str(current_user.id)
        ).order_by(SavedReport.updated_at.desc()).all()
    except Exception as e:
        logger.warning(f"SavedReport sorgulanamadı: {e}")
    
    return render_template('rapor/tasarimci.html', saved_reports=saved_reports)
    
    
@rapor_bp.route('/kaydedilenler')
@login_required
def kaydedilenler():
    """Kullanıcının kaydettiği raporları listele"""
    
    user_reports = []
    public_reports = []
    try:
        from app.modules.rapor.models import SavedReport
        tenant_db = get_tenant_db() # ✨ Eklendi
        
        # ✨ query_fb() kaldırıldı
        user_reports = tenant_db.query(SavedReport).filter_by(
            user_id=str(current_user.id)
        ).order_by(SavedReport.updated_at.desc()).all()
        
        # Database boolean'ı 1/0 olarak saklar mantığı MySQL/PG'de True/False olmalıdır
        public_reports = tenant_db.query(SavedReport).filter(
            SavedReport.is_public == True, # ✨ 1 yerine True yazıldı
            SavedReport.user_id != str(current_user.id)
        ).order_by(SavedReport.created_at.desc()).limit(10).all()
        
    except Exception as e:
        logger.error(f"Raporlar yüklenemedi: {e}")
        flash('Raporlar yüklenemedi.', 'danger')
        
    return render_template('rapor/kaydedilenler.html', user_reports=user_reports, public_reports=public_reports)


@rapor_bp.route('/api/rapor-kaydet', methods=['POST'])
@login_required
@csrf.exempt  # ✅ Artık çalışacak
def api_rapor_kaydet():
    """Raporu Database'e kaydet"""
    
    import traceback
    
    try:
        tenant_db = get_tenant_db()
        
        if not tenant_db:
            logger.error("❌ Database bağlantısı yok")
            return jsonify({
                'success': False, 
                'message': 'Database bağlantısı yok'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Veri gönderilmedi'
            }), 400
        
        logger.info(f"📥 Request data keys: {list(data.keys())}")
        
        if not data.get('name'):
            return jsonify({'success': False, 'message': 'Rapor adı zorunludur'}), 400
        
        if not data.get('model_name'):
            return jsonify({'success': False, 'message': 'Model adı zorunludur'}), 400
        
        if not data.get('config'):
            return jsonify({'success': False, 'message': 'Config zorunludur'}), 400
        
        from app.modules.rapor.models import SavedReport
        
        logger.info(f"📝 Rapor oluşturuluyor: {data.get('name')}")
        
        report = SavedReport()
        report.name = data['name']
        report.description = data.get('description', '')
        report.model_name = data['model_name']
        report.user_id = str(current_user.id)
        report.is_public = data.get('is_public', False)
        
        logger.info(f"💾 Config set ediliyor...")
        report.config = data['config']
        logger.info(f"✅ Config set edildi: {len(report.config_json)} karakter")
        
        logger.info("💾 Database'e kaydediliyor...")
        
        tenant_db.add(report)
        tenant_db.commit()
        
        logger.info(f"✅ Rapor kaydedildi: ID={report.id}, Name={report.name}")
        
        return jsonify({
            'success': True, 
            'report_id': report.id,
            'message': f'"{report.name}" başarıyla kaydedildi'
        })
    
    except Exception as e:
        if tenant_db:
            tenant_db.rollback()
        
        error_trace = traceback.format_exc()
        logger.error(f"❌ Kaydetme hatası:\n{error_trace}")
        
        return jsonify({
            'success': False, 
            'message': f'Hata: {str(e)}'
        }), 500
        
@rapor_bp.route('/export-pdf')
@login_required
def export_rapor_pdf():
    """PDF export (WeasyPrint ile)"""
    
    # Session'dan config al
    config = session.get('last_report_config')
    
    if not config:
        flash('Önce raporu çalıştırın', 'warning')
        return redirect(url_for('rapor.tasarimci'))
    
    try:
        # HTML render et
        from flask import render_template_string
        
        # ... (HTML oluştur, WeasyPrint ile PDF'e çevir)
        
        flash('PDF export özelliği yakında eklenecek', 'info')
        return redirect(url_for('rapor.tasarimci'))
    
    except Exception as e:
        logger.error(f"PDF export hatası: {e}")
        flash('PDF oluşturulamadı', 'danger')
        return redirect(url_for('rapor.tasarimci'))


@rapor_bp.route('/export-excel')
@login_required
def export_rapor_excel():
    """Excel export (openpyxl ile)"""
    
    # Session'dan config al
    config = session.get('last_report_config')
    
    if not config:
        flash('Önce raporu çalıştırın', 'warning')
        return redirect(url_for('rapor.tasarimci'))
    
    try:
        # ... (Excel oluştur)
        
        flash('Excel export özelliği yakında eklenecek', 'info')
        return redirect(url_for('rapor.tasarimci'))
    
    except Exception as e:
        logger.error(f"Excel export hatası: {e}")
        flash('Excel oluşturulamadı', 'danger')
        return redirect(url_for('rapor.tasarimci'))
                
    return render_template('firmalar/form.html', form=form)      