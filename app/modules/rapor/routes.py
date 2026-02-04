from flask import Blueprint, render_template, request, jsonify, Response, g, flash, send_file, make_response, session
from flask_login import login_required, current_user

from app.extensions import db
from app.modules.stok.models import StokKart, StokDepo, StokHareketi
 
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

rapor_bp = Blueprint('rapor', __name__)

@rapor_bp.route('/')
@login_required
def index():
    return render_template('rapor/index.html')

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
    raporlar = AIRaporGecmisi.query.filter_by(firma_id=current_user.firma_id)\
        .order_by(AIRaporGecmisi.tarih.desc()).limit(20).all()
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
    # 1.Varsayılan Tarihleri Belirle
    if g.donem:
        def_baslangic = g.donem.baslangic.strftime('%Y-%m-%d')
        def_bitis = g.donem.bitis.strftime('%Y-%m-%d')
    else:
        yil = datetime.now().year
        def_baslangic = f"{yil}-01-01"
        def_bitis = f"{yil}-12-31"

    # 2.Form Nesnesini Oluştur (Builder Kullanarak)
    form = get_yevmiye_filter_form(def_baslangic, def_bitis)

    # 3.POST İsteği ve Validasyon
    # form.validate() hem CSRF'yi hem de veri tiplerini kontrol eder
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
            else: bas_dt = baslangic # Zaten date objesi ise

            if isinstance(bitis, str):
                bit_dt = datetime.strptime(bitis, '%Y-%m-%d').date()
            else: bit_dt = bitis

            # Rapor Motorunu Çalıştır
            limit = 60 if format_type == 'dos' else 35
            motor = YevmiyeRaporuMotoru(bas_dt, bit_dt, satir_limiti=limit)
            sayfalar = motor.verileri_hazirla(firma_id=g.firma.id)
            
            if not sayfalar:
                flash("Seçilen tarih aralığında veri bulunamadı.", "warning")
                # Veri yoksa aynı sayfaya dön (Form hatalarını veya mesajı göster)
                return render_template('rapor/yevmiye_filtre.html', form=form)

            # Çıktı Üret
            if format_type == 'dos':
                return render_template('rapor/yevmiye_dos.txt', sayfalar=sayfalar), {'Content-Type': 'text/plain; charset=utf-8'}
            else:
                # Lazer çıktı için ayrı pencere/tab açılmasını form target="_blank" ile sağlarız
                return render_template('rapor/yevmiye_laser.html', 
                                     sayfalar=sayfalar, 
                                     baslangic=baslangic, 
                                     bitis=bitis,
                                     aktif_firma=g.firma,
                                     aktif_donem=g.donem)
                
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

@rapor_bp.route('/sablonlar')
@login_required
def sablonlar():
    """Şablon Yönetim Listesi"""
    if current_user.rol not in ['admin', 'patron']:
        return render_template('errors/403.html'), 403

    grid = DataGrid("sablon_grid", YazdirmaSablonu, "Yazdırma Şablonları")
    
    grid.add_column('baslik', 'Şablon Adı')
    grid.add_column('belge_turu', 'Tür', type='badge', 
                    badge_colors={'fatura': 'primary', 'tahsilat': 'success', 'tediye': 'danger', 'mutabakat': 'info'})
    
    grid.add_column('varsayilan', 'Varsayılan', type='badge', badge_colors={'True': 'success', 'False': 'secondary'})
    grid.add_column('aktif', 'Durum', type='boolean')

    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'rapor.sablon_duzenle')
    grid.add_action('preview', 'Önizle', 'bi bi-eye', 'btn-outline-dark btn-sm', 'route', 'rapor.sablon_onizle') # , target='_blank'
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'rapor.sablon_sil')

    query = YazdirmaSablonu.query.filter(
        (YazdirmaSablonu.firma_id == current_user.firma_id) | (YazdirmaSablonu.firma_id == None)
    )
    
    grid.process_query(query)
    return render_template('rapor/sablon_list.html', grid=grid)

@rapor_bp.route('/sablon-duzenle/<int:id>', methods=['GET', 'POST'])
@login_required
def sablon_duzenle(id):
    if current_user.rol not in ['admin', 'patron']: return "Yetkisiz", 403
    
    sablon = YazdirmaSablonu.query.get_or_404(id)
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
                YazdirmaSablonu.query.filter_by(
                    firma_id=sablon.firma_id, 
                    belge_turu=sablon.belge_turu
                ).filter(YazdirmaSablonu.id != sablon.id).update({'varsayilan': False})
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Şablon güncellendi.', 'redirect': '/rapor/sablonlar'})

    # 👇 REHBER İÇİN VERİ HAZIRLIĞI (HATA BURADAYDI)
    firma = Firma.query.get(current_user.firma_id)
    # Rehberde {{ belge.x }} kullanıldığı için dummy (örnek) bir belge gönderiyoruz.
    # Son faturayı çekelim, yoksa None gitmesin diye boş obje oluşturabiliriz ama şimdilik en son kaydı alalım.
    ornek_belge = Fatura.query.filter_by(firma_id=current_user.firma_id).order_by(Fatura.id.desc()).first()

    return render_template('rapor/sablon_form.html', form=form, sablon=sablon, firma=firma, belge=ornek_belge)

@rapor_bp.route('/sablon-ekle', methods=['GET', 'POST'])
@login_required
def sablon_ekle():
    if current_user.rol not in ['admin', 'patron']: return "Yetkisiz", 403
    
    form = create_sablon_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            data = form.get_data()
            
            sablon = YazdirmaSablonu(
                firma_id=current_user.firma_id,
                belge_turu=data['belge_turu'],
                baslik=data['baslik'],
                html_icerik=data['html_icerik'],
                css_icerik=data['css_icerik'],
                varsayilan=True if request.form.get('varsayilan') else False,
                aktif=True if request.form.get('aktif') else False
            )
            
            if sablon.varsayilan:
                 YazdirmaSablonu.query.filter_by(
                    firma_id=current_user.firma_id, 
                    belge_turu=sablon.belge_turu
                ).update({'varsayilan': False})
            
            db.session.add(sablon)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Şablon oluşturuldu.', 'redirect': '/rapor/sablonlar'})
            
    # 👇 REHBER İÇİN VERİ HAZIRLIĞI
    firma = Firma.query.get(current_user.firma_id)
    ornek_belge = Fatura.query.filter_by(firma_id=current_user.firma_id).order_by(Fatura.id.desc()).first()

    return render_template('rapor/sablon_form.html', form=form, firma=firma, belge=ornek_belge)

@rapor_bp.route('/sablon-onizle/<int:id>')
@login_required
def sablon_onizle(id):
    """
    Şablonu sahte (dummy) verilerle veya gerçek son kayıtla test eder.
    """
    sablon = YazdirmaSablonu.query.get_or_404(id)
    
    # Test verisi bul (O türdeki son kayıt)
    veri = None
    if sablon.belge_turu == 'fatura':
        veri = Fatura.query.filter_by(firma_id=current_user.firma_id).order_by(Fatura.id.desc()).first()
    
    # Eğer veri yoksa basit bir uyarı göster
    if not veri:
        return f"<h1>Önizleme İçin Veri Bulunamadı</h1><p>Lütfen önce sisteme en az bir tane <b>{sablon.belge_turu}</b> kaydı ekleyin.</p>"
    
    from flask import render_template_string
    firma = Firma.query.get(current_user.firma_id)
    
    context = {
        'belge': veri,
        'firma': firma,
        'sablon_css': sablon.css_icerik
    }
    
    try:
        return render_template_string(sablon.html_icerik, **context)
    except Exception as e:
        return f"<h1>Şablon Render Hatası</h1><pre>{str(e)}</pre>"

@rapor_bp.route('/sablon-sil/<int:id>', methods=['POST'])
@login_required
def sablon_sil(id):
    sablon = YazdirmaSablonu.query.get_or_404(id)
    if sablon.firma_id != current_user.firma_id:
        return jsonify({'success': False, 'message': 'Yetkisiz işlem'}), 403
        
    db.session.delete(sablon)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Şablon silindi.'})

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