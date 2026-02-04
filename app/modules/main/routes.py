# app/modules/main/routes.py

from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, session, g, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, case, literal
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
    Navbar üzerinden Şube veya Dönem değiştirme işlemi.
    Güvenlik kontrolleri eklendi.
    """
    sube_id = request.form.get('sube_id')
    donem_id = request.form.get('donem_id')
    
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect(request.referrer)

    # 1. ŞUBE DEĞİŞİMİ
    if sube_id is not None:
        if sube_id == "": # "Tüm Şubeler" seçildi
            # Sadece Admin/Patron/Genel Müdür tüm şubeleri görebilir
            if current_user.can('dashboard.konsolide') or current_user.rol in ['admin', 'patron']:
                session.pop('aktif_sube_id', None)
                flash("Tüm şubeler (Konsolide) moduna geçildi.", "info")
            else:
                flash("Tüm şubeleri görme yetkiniz yok.", "warning")
        else:
            # Seçilen şube var mı ve aktif mi?
            sube = tenant_db.query(Sube).filter_by(id=int(sube_id), aktif=True).first()
            if sube:
                # İLERİ SEVİYE TODO: Kullanıcının bu şubeye yetkisi var mı kontrolü buraya eklenebilir.
                session['aktif_sube_id'] = sube.id
                flash(f"Aktif şube değiştirildi: {sube.ad}", "success")
            else:
                flash("Seçilen şube bulunamadı veya pasif.", "warning")

    # 2. DÖNEM DEĞİŞİMİ
    if donem_id:
        donem = tenant_db.query(Donem).filter_by(id=int(donem_id), aktif=True).first()
        if donem:
            session['aktif_donem_id'] = donem.id
            flash(f"Çalışma dönemi değiştirildi: {donem.ad}", "success")
        else:
            flash("Seçilen dönem bulunamadı.", "warning")

    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/')
@login_required
def index():
    """
    ROL VE ŞUBE DUYARLI DASHBOARD
    """
    tenant_db = get_tenant_db()
    if not tenant_db:
        if not session.get('active_db_yolu'):
             flash("Lütfen önce firma seçimi yapınız.", "warning")
        # Boş dashboard döndür
        return render_template('main/index.html', karsilama_mesaji="Hoşgeldiniz",
                               gunluk_satis=0, aylik_satis=0, kasa_toplam=0, banka_toplam=0,
                               toplam_alacak=0, toplam_borc=0, portfoydeki_cekler=0, odenecek_cekler=0,
                               kritik_stoklar=[], son_faturalar=[])

    # 1. TEMEL DEĞİŞKENLER
    bugun = date.today()
    bu_ay_basi = bugun.replace(day=1)
    
    # NOT: 'tum_subeler' ve 'tum_donemler' değişkenlerini buradan kaldırdık.
    # Çünkü Context Processor bunları global olarak zaten sağlıyor.

    # 2. FİLTRELEME MANTIĞI (CONTEXT)
    active_sube_id = session.get('aktif_sube_id')
    
    # SQLAlchemy Filtre Yardımcısı
    def filter_by_sube(query, model_class):
        if active_sube_id and hasattr(model_class, 'sube_id'):
            return query.filter(model_class.sube_id == active_sube_id)
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
            dashboard_data['gunluk_satis'] = safe_scalar(filter_by_sube(q_gunluk, Fatura))

            # Aylık
            q_aylik = tenant_db.query(func.coalesce(func.sum(Fatura.genel_toplam), 0)).filter(
                Fatura.tarih >= bu_ay_basi, Fatura.fatura_turu == 'SATIS', Fatura.iptal_mi == False
            )
            dashboard_data['aylik_satis'] = safe_scalar(filter_by_sube(q_aylik, Fatura))

        # --- B. FİNANS (Kasa/Banka) ---
        if current_user.can('kasa.view'):
            q_kasa = tenant_db.query(KasaHareket)
            q_kasa = filter_by_sube(q_kasa, KasaHareket)
            # SQL tarafında hesaplamak daha performanslıdır
            # Ancak KasaHareket yapınıza göre Python'da toplamak gerekebilir.
            # Şimdilik mevcut mantığı koruyup güvenli hale getiriyoruz.
            try:
                kasalar = q_kasa.all()
                giris = sum(k.tutar for k in kasalar if k.islem_turu in ['tahsilat', 'virman_giris'])
                cikis = sum(k.tutar for k in kasalar if k.islem_turu in ['tediye', 'virman_cikis', 'gider'])
                dashboard_data['kasa_toplam'] = giris - cikis
            except: pass

        if current_user.can('banka.view'):
            try:
                q_banka = tenant_db.query(BankaHareket)
                # q_banka = filter_by_sube(q_banka, BankaHareket) # Bankada şube varsa açılır
                bankalar = q_banka.all()
                giris = sum(b.tutar for b in bankalar if b.islem_turu in ['tahsilat', 'virman_giris', 'gelen_havale'])
                cikis = sum(b.tutar for b in bankalar if b.islem_turu in ['tediye', 'virman_cikis', 'gider', 'giden_havale'])
                dashboard_data['banka_toplam'] = giris - cikis
            except: pass

        # --- C. RİSK (Cari) ---
        if current_user.can('cari.view'):
            dashboard_data['toplam_alacak'] = safe_scalar(tenant_db.query(func.coalesce(func.sum(CariHesap.borc_bakiye), 0)))
            dashboard_data['toplam_borc'] = safe_scalar(tenant_db.query(func.coalesce(func.sum(CariHesap.alacak_bakiye), 0)))

        # --- D. ÇEKLER ---
        if current_user.can('cek.view'):
            try:
                cekler = tenant_db.query(CekSenet).filter(CekSenet.cek_durumu == 'PORTFOYDE').all()
                dashboard_data['portfoydeki_cekler'] = sum(c.tutar for c in cekler if c.portfoy_tipi == 'ALINAN')
                dashboard_data['odenecek_cekler'] = sum(c.tutar for c in cekler if c.portfoy_tipi == 'VERILEN')
            except: pass

        # --- E. KRİTİK STOK ---
        if current_user.can('stok.view'):
            try:
                # Sadece kritik seviyenin altındakileri çeken optimize sorgu
                stoklar = tenant_db.query(StokKart).filter(
                    StokKart.aktif == True,
                    StokKart.kritik_seviye > 0
                    # StokKart.mevcut < StokKart.kritik_seviye # Bu alan hesaplanmış alansa SQL'de çalışmayabilir
                ).limit(50).all()
                
                # Python tarafında filtrele (Mevcut miktar genelde dinamik hesaplanır)
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
            q_fatura = tenant_db.query(Fatura).filter(Fatura.iptal_mi == False)
            q_fatura = filter_by_sube(q_fatura, Fatura)
            dashboard_data['son_faturalar'] = q_fatura.order_by(Fatura.tarih.desc(), Fatura.id.desc()).limit(5).all()
        except: pass

    except Exception as e:
        print(f"⚠️ Dashboard Genel Hata: {e}")
        flash("Dashboard verileri yüklenirken bazı hatalar oluştu.", "warning")

    return render_template('main/index.html',
                           karsilama_mesaji=get_karsilama_mesaji(),
                           **dashboard_data) # Dictionary'i unpack ederek gönderiyoruz

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