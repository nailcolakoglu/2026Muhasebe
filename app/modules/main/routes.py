# app/modules/main/routes.py

from app.modules.ai_destek.ai_generator import generate_ceo_briefing
import json
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import joinedload
from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, session, g, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, case, literal, extract
from app.extensions import get_tenant_db
from app.modules.fatura.models import Fatura
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.modules.cari.models import CariHesap
from app.modules.cek.models import CekSenet
from app.modules.stok.models import StokKart
from app.modules.sube.models import Sube
from app.modules.firmalar.models import Donem
from app.form_builder.ai_generator import generate_form_from_text
from app.form_builder.form import Form
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

def get_karsilama_mesaji():
    """Saate göre dinamik karşılama mesajı"""
    saat = datetime.now().hour
    if 5 <= saat < 12: return "Günaydın"
    elif 12 <= saat < 18: return "İyi Günler"
    elif 18 <= saat < 22: return "İyi Akşamlar"
    else: return "İyi Geceler"

@main_bp.route('/change-context', methods=['POST'])
@login_required
def change_context():
    """
    ✅ UUID DESTEKLİ Context Değiştirme
    
    Navbar üzerinden Şube veya Dönem değiştirme işlemi.
    Güvenlik kontrolleri eklendi.
    """
    sube_id = request.form.get('sube_id')
    donem_id = request.form.get('donem_id')
    
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect(request.referrer or url_for('main.index'))

    # ============================================
    # 1. ŞUBE DEĞİŞİMİ (UUID)
    # ============================================
    if sube_id is not None:
        if sube_id == "":  # "Tüm Şubeler" seçildi
            # Sadece Admin/Patron/Genel Müdür tüm şubeleri görebilir
            if current_user.can('dashboard.konsolide') or current_user.rol in ['admin', 'patron']:
                session.pop('aktif_sube_id', None)
                session.modified = True
                flash("Tüm şubeler (Konsolide) moduna geçildi.", "info")
            else:
                flash("Tüm şubeleri görme yetkiniz yok.", "warning")
        else:
            # ✅ UUID string olarak kullan (int() KALDIRILDI!)
            sube = tenant_db.query(Sube).filter_by(id=sube_id, aktif=True).first()
            
            if sube:
                # İLERİ SEVİYE TODO: Kullanıcının bu şubeye yetkisi var mı kontrolü eklenebilir
                session['aktif_sube_id'] = sube.id
                session.modified = True
                flash(f"Aktif şube değiştirildi: {sube.ad}", "success")
            else:
                flash("Seçilen şube bulunamadı veya pasif.", "warning")

    # ============================================
    # 2. DÖNEM DEĞİŞİMİ (UUID)
    # ============================================
    if donem_id:
        # ✅ UUID string olarak kullan (int() KALDIRILDI!)
        donem = tenant_db.query(Donem).filter_by(id=donem_id).first()  # ✅ aktif=True kaldırıldı
        
        if donem:
            # Dönem kapalı mı kontrol et (opsiyonel)
            if not donem.aktif:
                flash(f"⚠️ Dikkat: Seçilen dönem pasif durumda ({donem.ad})", "warning")
            
            session['aktif_donem_id'] = donem.id
            session.modified = True
            
            logger.info(f"✅ Dönem değiştirildi: {donem.ad} (ID: {donem.id})")
            flash(f"Çalışma dönemi değiştirildi: {donem.ad}", "success")
        else:
            logger.warning(f"⚠️ Dönem bulunamadı: {donem_id}")
            flash("Seçilen dönem bulunamadı.", "warning")

    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/')
@login_required
def index():
    """
    ROL, ŞUBE VE DÖNEM DUYARLI AKILLI DASHBOARD
    """
    # ✨ 1. YENİ: Plasiyer Giriş Yönlendirmesi
    if current_user.rol == 'plasiyer':
        return redirect(url_for('mobile.dashboard'))
    tenant_db = get_tenant_db()
    if not tenant_db:
        if not session.get('active_db_yolu'):
             flash("Lütfen önce firma seçimi yapınız.", "warning")
        return render_template('main/index.html', karsilama_mesaji="Hoşgeldiniz",
                               gunluk_satis=0, aylik_satis=0, kasa_toplam=0, banka_toplam=0,
                               toplam_alacak=0, toplam_borc=0, portfoydeki_cekler=0, odenecek_cekler=0,
                               kritik_stoklar=[], son_faturalar=[])

    # 1. TEMEL DEĞİŞKENLER
    bugun = date.today()
    bu_ay_basi = bugun.replace(day=1)

    # 2. KURUMSAL KAPSAM (DATA SCOPING) HAFIZASI
    active_sube_id = session.get('aktif_sube_id')
    active_donem_id = session.get('aktif_donem_id')
    
    # 🧠 Akıllı Filtre Motoru: Hem Şubeyi Hem Dönemi Kontrol Eder
    def filter_by_context(query, model_class):
        if active_sube_id and hasattr(model_class, 'sube_id'):
            query = query.filter(model_class.sube_id == active_sube_id)
        if active_donem_id and hasattr(model_class, 'donem_id'):
            query = query.filter(model_class.donem_id == active_donem_id)
        return query

    # Yardımcı: Hata olsa bile 0 döndüren güvenli sorgu çalıştırıcı
    def safe_scalar(query, default=0):
        try:
            return query.scalar() or default
        except:
            return default

    # Verileri hazırla
    dashboard_data = {
        'gunluk_satis': 0, 'aylik_satis': 0,
        'kasa_toplam': 0, 'banka_toplam': 0,
        'toplam_alacak': 0, 'toplam_borc': 0,
        'portfoydeki_cekler': 0, 'odenecek_cekler': 0,
        'kritik_stoklar': [], 'son_faturalar': []
    }

    try:
        # --- A. SATIŞ ---
        if current_user.can('fatura.view') or current_user.can('dashboard.view'):
            # Günlük
            q_gunluk = tenant_db.query(func.coalesce(func.sum(Fatura.genel_toplam), 0)).filter(
                Fatura.tarih == bugun, Fatura.fatura_turu == 'SATIS', Fatura.iptal_mi == False
            )
            dashboard_data['gunluk_satis'] = safe_scalar(filter_by_context(q_gunluk, Fatura))

            # Aylık
            q_aylik = tenant_db.query(func.coalesce(func.sum(Fatura.genel_toplam), 0)).filter(
                Fatura.tarih >= bu_ay_basi, Fatura.fatura_turu == 'SATIS', Fatura.iptal_mi == False
            )
            dashboard_data['aylik_satis'] = safe_scalar(filter_by_context(q_aylik, Fatura))

        # --- B. FİNANS (Kasa/Banka) ---
        if current_user.can('kasa.view'):
            q_kasa = tenant_db.query(KasaHareket)
            q_kasa = filter_by_context(q_kasa, KasaHareket)
            try:
                kasalar = q_kasa.all()
                giris = sum(k.tutar for k in kasalar if k.islem_turu in ['tahsilat', 'virman_giris'])
                cikis = sum(k.tutar for k in kasalar if k.islem_turu in ['tediye', 'virman_cikis', 'gider'])
                dashboard_data['kasa_toplam'] = giris - cikis
            except: pass

        if current_user.can('banka.view'):
            try:
                q_banka = tenant_db.query(BankaHareket)
                q_banka = filter_by_context(q_banka, BankaHareket)
                bankalar = q_banka.all()
                giris = sum(b.tutar for b in bankalar if b.islem_turu in ['tahsilat', 'virman_giris', 'gelen_havale'])
                cikis = sum(b.tutar for b in bankalar if b.islem_turu in ['tediye', 'virman_cikis', 'gider', 'giden_havale'])
                dashboard_data['banka_toplam'] = giris - cikis
            except: pass

        # --- C. RİSK (Cari) ---
        if current_user.can('cari.view'):
            q_alacak = tenant_db.query(func.coalesce(func.sum(CariHesap.borc_bakiye), 0))
            q_borc = tenant_db.query(func.coalesce(func.sum(CariHesap.alacak_bakiye), 0))
            
            # Carilerde şube filtresi varsa uygular, yoksa otomatik geçer
            dashboard_data['toplam_alacak'] = safe_scalar(filter_by_context(q_alacak, CariHesap))
            dashboard_data['toplam_borc'] = safe_scalar(filter_by_context(q_borc, CariHesap))

        # --- D. ÇEKLER ---
        if current_user.can('cek.view'):
            try:
                q_cekler = tenant_db.query(CekSenet).filter(CekSenet.cek_durumu == 'PORTFOYDE')
                q_cekler = filter_by_context(q_cekler, CekSenet)
                cekler = q_cekler.all()
                dashboard_data['portfoydeki_cekler'] = sum(c.tutar for c in cekler if c.portfoy_tipi == 'ALINAN')
                dashboard_data['odenecek_cekler'] = sum(c.tutar for c in cekler if c.portfoy_tipi == 'VERILEN')
            except: pass

        # --- E. KRİTİK STOK ---
        if current_user.can('stok.view'):
            try:
                # Sadece kritik seviyenin altındakileri çeken optimize sorgu
                q_stok = tenant_db.query(StokKart).filter(
                    StokKart.aktif == True,
                    StokKart.kritik_seviye > 0
                )
                q_stok = filter_by_context(q_stok, StokKart)
                stoklar = q_stok.limit(50).all()
                
                for s in stoklar:
                    # TODO: Stok miktarını depolardan topla
                    mevcut = 0 
                    if mevcut <= s.kritik_seviye:
                        dashboard_data['kritik_stoklar'].append({
                            'ad': s.ad, 
                            'miktar': mevcut, 
                            'sinir': s.kritik_seviye, 
                            'birim': getattr(s, 'birim', 'Adet')
                        })
                dashboard_data['kritik_stoklar'] = dashboard_data['kritik_stoklar'][:5]
            except: pass

        # --- F. SON FATURALAR ---
        try:
            q_fatura = tenant_db.query(Fatura).options(
                joinedload(Fatura.cari),
                joinedload(Fatura.sube)
            ).filter(Fatura.iptal_mi == False)
            
            q_fatura = filter_by_context(q_fatura, Fatura)
            dashboard_data['son_faturalar'] = q_fatura.order_by(
                Fatura.tarih.desc(), 
                Fatura.id.desc()
            ).limit(5).all()
    
        except Exception as e:
            logger.error(f"❌ Dashboard fatura hatası: {e}", exc_info=True)
    

    except Exception as e:
        logger.error(f"⚠️ Dashboard Genel Hata: {e}", exc_info=True)
        flash("Dashboard verileri yüklenirken bazı hatalar oluştu.", "warning")

    return render_template('main/index.html',
                           karsilama_mesaji=get_karsilama_mesaji(),
                           **dashboard_data)


@main_bp.route('/api/nakit-akis-grafik')
@login_required
def api_nakit_akis_grafik():
    """Son 6 ayın Gelir/Gider Nakit Akışı verilerini grafiğe gönderir (Şube ve Dönem Duyarlı)"""
    tenant_db = get_tenant_db()
    if not tenant_db: 
        return jsonify({'success': False})
        
    aylar = []
    gelirler = []
    giderler = []
    
    bugun = date.today()
    
    # ✨ AKILLI HAFIZA
    active_sube_id = session.get('aktif_sube_id')
    active_donem_id = session.get('aktif_donem_id')
    
    try:
        # Son 6 ayı geriye doğru hesapla
        for i in range(5, -1, -1):
            hedef_tarih = bugun - relativedelta(months=i)
            aylar.append(hedef_tarih.strftime('%b %Y')) # Örn: "Oct 2025"
            
            # SATIŞ TOPLAMI (Gelir)
            q_gelir = tenant_db.query(func.coalesce(func.sum(Fatura.genel_toplam), 0)).filter(
                Fatura.fatura_turu == 'SATIS',
                Fatura.iptal_mi == False,
                extract('year', Fatura.tarih) == hedef_tarih.year,
                extract('month', Fatura.tarih) == hedef_tarih.month
            )
            
            # ALIŞ/GİDER TOPLAMI (Gider)
            q_gider = tenant_db.query(func.coalesce(func.sum(Fatura.genel_toplam), 0)).filter(
                Fatura.fatura_turu == 'ALIS',
                Fatura.iptal_mi == False,
                extract('year', Fatura.tarih) == hedef_tarih.year,
                extract('month', Fatura.tarih) == hedef_tarih.month
            )
            
            # ✨ ŞUBE VE DÖNEM KISITLAMASI EKLENİYOR
            if active_sube_id:
                q_gelir = q_gelir.filter(Fatura.sube_id == active_sube_id)
                q_gider = q_gider.filter(Fatura.sube_id == active_sube_id)
                
            if active_donem_id:
                q_gelir = q_gelir.filter(Fatura.donem_id == active_donem_id)
                q_gider = q_gider.filter(Fatura.donem_id == active_donem_id)
            
            gelirler.append(float(q_gelir.scalar() or 0))
            giderler.append(float(q_gider.scalar() or 0))
            
        return jsonify({
            'success': True,
            'kategoriler': aylar,
            'gelirler': gelirler,
            'giderler': giderler
        })
        
    except Exception as e:
        logger.error(f"Grafik veri hatası: {e}")
        return jsonify({'success': False, 'message': 'Veri çekilemedi.'})

@main_bp.route('/ai/create-form', methods=['POST'])
def ai_create_form():
    """AI ile form oluştur"""
    data = request.json
    user_prompt = data.get('prompt')
    if not user_prompt: return jsonify({"error": "Prompt boş olamaz"}), 400
    
    try:
        form_schema = generate_form_from_text(user_prompt)
        if not form_schema: return jsonify({"error": "AI yanıt veremedi"}), 500
        form_obj = Form.from_json(form_schema)
        return form_obj.render()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main_bp.route('/ai-sihirbaz', methods=['GET'])
@login_required
def ai_sihirbaz():
    return render_template('main/ai_sihirbaz.html')
            
@main_bp.route('/api/ceo-brifing-olustur', methods=['POST'])
@login_required
def api_ceo_brifing_olustur():
    """
    Önyüzden gelen finansal özet verilerini AI'ya gönderip HTML brifing alır.
    """
    try:
        # Frontend'den gelen JSON verisini yakala
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Veri alınamadı.'})

        # Veriyi AI jeneratörüne gönder (ensure_ascii=False ile Türkçe karakterleri koru)
        ai_rapor_html = generate_ceo_briefing(json.dumps(data, ensure_ascii=False))

        return jsonify({'success': True, 'report': ai_rapor_html})
        
    except Exception as e:
        import logging
        logging.error(f"CEO Brifing Hatası: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'AI Hatası: {str(e)}'})