# app/modules/b2b/routes.py

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, g
from sqlalchemy import func
from datetime import datetime
import uuid

from app.extensions import get_tenant_db
from app.utils.decorators import b2b_login_required
from app.modules.b2b.services import B2BAuthService

# Yeni Mimari Model ve Servis Importları
from app.modules.stok.models import StokKart
from app.modules.siparis.models import Siparis, SiparisDetay
from app.modules.cari.models import CariHareket, CariHesap
from app.modules.cari.services import CariService
from app.enums import CariIslemTuru, SiparisDurumu

b2b_bp = Blueprint('b2b', __name__)

@b2b_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Bayi Portalı Giriş Ekranı"""
    if 'b2b_user_id' in session and 'tenant_id' in session:
        return redirect(url_for('b2b.dashboard'))
        
    if request.method == 'POST':
        firma_kodu = request.form.get('firma_kodu', '').strip()
        email = request.form.get('email', '').strip()
        sifre = request.form.get('sifre', '')
        
        if not firma_kodu or not email or not sifre:
            return jsonify({'success': False, 'message': 'Lütfen tüm alanları doldurun.'}), 400
            
        basari, mesaj, user_data = B2BAuthService.login(firma_kodu, email, sifre)
        
        if basari:
            session.clear() 
            session['tenant_id'] = user_data['tenant_id'] 
            session['b2b_user_id'] = user_data['b2b_user_id']
            session['b2b_cari_id'] = user_data['cari_id']
            session['b2b_name'] = user_data['ad_soyad']
            
            return jsonify({'success': True, 'redirect': url_for('b2b.dashboard')})
            
        return jsonify({'success': False, 'message': mesaj}), 401
        
    return render_template('b2b/login.html')

@b2b_bp.route('/logout')
def logout():
    """Bayi Portalı Çıkış"""
    session.clear()
    return redirect(url_for('b2b.login'))

@b2b_bp.route('/')
@b2b_bp.route('/dashboard')
@b2b_login_required
def dashboard():
    """Bayi Portalı Ana Ekranı ve Dinamik Özetler"""
    tenant_db = get_tenant_db()
    cari_id = g.b2b_user.cari_id
    
    # ✨ DÜZELTME: CariHesap önbelleği yerine, hareketlerden (Ledger) KESİN hesaplama yapıyoruz
    bakiye_sorgu = tenant_db.query(
        func.sum(CariHareket.borc).label('toplam_borc'),
        func.sum(CariHareket.alacak).label('toplam_alacak')
    ).filter(CariHareket.cari_id == str(cari_id)).first()
    
    toplam_borc = float(bakiye_sorgu.toplam_borc or 0)
    toplam_alacak = float(bakiye_sorgu.toplam_alacak or 0)
    guncel_bakiye = toplam_borc - toplam_alacak
    
    bekleyen_siparis_sayisi = tenant_db.query(Siparis).filter(
        Siparis.cari_id == str(cari_id),
        Siparis.durum.in_([SiparisDurumu.BEKLIYOR.value, SiparisDurumu.ONAYLANDI.value, SiparisDurumu.KISMI.value, 'Yeni', 'Bekliyor']) 
    ).count()

    return render_template(
        'b2b/dashboard.html', 
        user=g.b2b_user,
        guncel_bakiye=guncel_bakiye,
        bekleyen_siparis_sayisi=bekleyen_siparis_sayisi
    )
    
# ==========================================
# B2B E-TİCARET (KATALOG VE SEPET) ROTALARI
# ==========================================

@b2b_bp.route('/katalog')
@b2b_login_required
def katalog():
    tenant_db = get_tenant_db()
    
    # Arama ve Sayfalama Parametreleri
    search = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12 # Her sayfada 12 ürün (3x4 grid için idealdir)
    
    from app.modules.stok.models import StokKart, StokDepoDurumu
    from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
    from sqlalchemy import func, or_
    
    # 1. SADECE STOKTA OLANLARI GETİR (SUM > 0)
    query = tenant_db.query(
        StokKart, 
        func.sum(StokDepoDurumu.miktar).label('toplam_stok')
    ).outerjoin(StokDepoDurumu, StokKart.id == StokDepoDurumu.stok_id)\
     .filter(StokKart.aktif == True)\
     .group_by(StokKart.id)\
     .having(func.sum(StokDepoDurumu.miktar) > 0)
     
    # 2. ARAMA FİLTRESİ
    if search:
        query = query.filter(or_(
            StokKart.ad.ilike(f'%{search}%'),
            StokKart.kod.ilike(f'%{search}%')
        ))
        
    # Sayfalama (Pagination) Hesaplamaları
    total_items = query.count()
    toplam_sayfa = (total_items + per_page - 1) // per_page
    
    stok_sonuclari = query.order_by(StokKart.ad).limit(per_page).offset((page - 1) * per_page).all()
    
    # 3. ÖZEL B2B FİYATLARINI EKRANA YANSITMA
    aktif_fiyat_listesi = tenant_db.query(FiyatListesi).filter_by(aktif=True, varsayilan=True).order_by(FiyatListesi.oncelik.desc()).first()
    fiyat_map = {}
    if aktif_fiyat_listesi:
        detaylar = tenant_db.query(FiyatListesiDetay).filter_by(fiyat_listesi_id=str(aktif_fiyat_listesi.id)).all()
        fiyat_map = {str(d.stok_id): d for d in detaylar}
        
    katalog_verisi = []
    for stok, toplam_miktar in stok_sonuclari:
        birim_fiyat = float(stok.satis_fiyati or 0)
        
        # Ürüne özel iskontolu fiyatı bul
        if str(stok.id) in fiyat_map:
            detay = fiyat_map[str(stok.id)]
            if detay.fiyat and float(detay.fiyat) > 0:
                birim_fiyat = float(detay.fiyat)
            elif detay.iskonto_orani and float(detay.iskonto_orani) > 0:
                birim_fiyat = birim_fiyat - (birim_fiyat * (float(detay.iskonto_orani) / 100))
                
        katalog_verisi.append({
            'id': stok.id,
            'kod': stok.kod,
            'ad': stok.ad,
            'birim': getattr(stok, 'birim', 'Adet'),
            'fiyat': birim_fiyat,
            'resim_path': getattr(stok, 'resim_path', None),
            'stok_miktari': float(toplam_miktar or 0)
        })

    return render_template(
        'b2b/katalog.html', 
        urunler=katalog_verisi, 
        search=search, 
        page=page, 
        toplam_sayfa=toplam_sayfa
    )

@b2b_bp.route('/api/sepete-ekle', methods=['POST'])
@b2b_login_required
def sepete_ekle():
    stok_id = str(request.form.get('stok_id'))
    try:
        miktar = float(request.form.get('miktar', 1))
    except ValueError:
        miktar = 1.0
        
    if miktar <= 0:
        return jsonify({'success': False, 'message': 'Lütfen geçerli bir miktar girin.'}), 400

    tenant_db = get_tenant_db()
    stok = tenant_db.get(StokKart, stok_id)
    
    if not stok:
        return jsonify({'success': False, 'message': 'Ürün bulunamadı.'}), 404
        
    sepet = session.get('b2b_sepet', {})
    
    # Sepette bu üründen zaten varsa, yeni eklenmek istenenle topla (Stok kontrolü için)
    mevcut_sepet_miktari = sepet.get(stok_id, {}).get('miktar', 0.0)
    istenen_toplam_miktar = mevcut_sepet_miktari + miktar
    
    # ==========================================
    # 🚀 1. DEV: CANLI STOK KONTROL MOTORU
    # ==========================================
    from app.modules.stok.models import StokDepoDurumu
    from sqlalchemy import func
    
    # Firmanın tüm depolarındaki toplam stoku bul
    toplam_stok_sorgu = tenant_db.query(func.sum(StokDepoDurumu.miktar)).filter(
        StokDepoDurumu.stok_id == stok_id,
        StokDepoDurumu.miktar > 0
    ).scalar()
    
    toplam_stok = float(toplam_stok_sorgu or 0.0)
    
    if istenen_toplam_miktar > toplam_stok:
        return jsonify({
            'success': False, 
            'message': f'Yetersiz stok! Depomuzda şu an maksimum {toplam_stok:,.0f} {getattr(stok, "birim", "Adet")} bulunuyor.'
        }), 400

    # ==========================================
    # 🚀 2. DEV: DİNAMİK B2B FİYAT VE İSKONTO MOTORU
    # ==========================================
    birim_fiyat = float(getattr(stok, 'satis_fiyati', 0.0) or 0.0)
    
    from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
    
    # Sisteme tanımlı "Varsayılan" veya "B2B" öncelikli fiyat listesini bul
    aktif_fiyat_listesi = tenant_db.query(FiyatListesi).filter_by(aktif=True, varsayilan=True).order_by(FiyatListesi.oncelik.desc()).first()
    
    if aktif_fiyat_listesi:
        # Ürünün bu listedeki özel fiyatını/iskontosunu bul
        ozel_fiyat_detay = tenant_db.query(FiyatListesiDetay).filter_by(
            fiyat_listesi_id=str(aktif_fiyat_listesi.id), 
            stok_id=stok_id
        ).first()
        
        if ozel_fiyat_detay:
            # Bayi, toptan satış (min_miktar) baremini aştı mı?
            min_alim_sarti = float(ozel_fiyat_detay.min_miktar or 0.0)
            if istenen_toplam_miktar >= min_alim_sarti:
                # 1. Seçenek: Listede net fiyat (Örn: 50 TL) verilmişse onu kullan
                if ozel_fiyat_detay.fiyat and float(ozel_fiyat_detay.fiyat) > 0:
                    birim_fiyat = float(ozel_fiyat_detay.fiyat)
                # 2. Seçenek: Listede İskonto (Örn: %10) verilmişse ana fiyattan düş
                elif ozel_fiyat_detay.iskonto_orani and float(ozel_fiyat_detay.iskonto_orani) > 0:
                    iskonto_yuzde = float(ozel_fiyat_detay.iskonto_orani)
                    birim_fiyat = birim_fiyat - (birim_fiyat * (iskonto_yuzde / 100))

    # ==========================================
    # 3. NİHAİ SEPETE EKLEME İŞLEMİ
    # ==========================================
    if stok_id in sepet:
        sepet[stok_id]['miktar'] += miktar
        # Toptan alım baremi aşıldığı için fiyat düşmüş olabilir, fiyatı güncelle!
        sepet[stok_id]['fiyat'] = birim_fiyat 
    else:
        sepet[stok_id] = {
            'kod': stok.kod,
            'ad': stok.ad,
            'miktar': miktar,
            'fiyat': birim_fiyat,
            'birim': getattr(stok, 'birim', 'Adet')
        }
        
    session['b2b_sepet'] = sepet
    session.modified = True 
    
    return jsonify({
        'success': True, 
        'message': f"{stok.ad} sepete eklendi. (Fiyat: {birim_fiyat:,.2f} TL)",
        'sepet_sayisi': len(sepet)
    })

@b2b_bp.route('/sepet')
@b2b_login_required
def sepet():
    sepet = session.get('b2b_sepet', {})
    genel_toplam = sum(item['miktar'] * item['fiyat'] for item in sepet.values())
    return render_template('b2b/sepet.html', sepet=sepet, genel_toplam=genel_toplam)

@b2b_bp.route('/api/sepeti-temizle', methods=['POST'])
@b2b_login_required
def sepeti_temizle():
    session.pop('b2b_sepet', None)
    return jsonify({'success': True, 'redirect': url_for('b2b.katalog')})

@b2b_bp.route('/siparis-tamamla', methods=['POST'])
@b2b_login_required
def siparis_tamamla():
    sepet = session.get('b2b_sepet', {})
    if not sepet: return redirect(url_for('b2b.katalog'))
        
    tenant_db = get_tenant_db()
    
    from app.modules.depo.models import Depo
    from app.modules.sube.models import Sube
    from app.modules.firmalar.models import Donem
    from app.modules.b2b.models import B2BAyar # ✨ B2B Ayarları eklendi
    
    varsayilan_depo = tenant_db.query(Depo).first()
    varsayilan_sube = tenant_db.query(Sube).filter_by(aktif=True).first()
    varsayilan_donem = tenant_db.query(Donem).filter_by(aktif=True).first()
    
    if not varsayilan_depo:
        return "Sipariş oluşturulamadı: ERP sisteminizde tanımlı hiçbir depo bulunmuyor!", 400
        
    # ==========================================
    # 🚀 OTOMATİK SİPARİŞ ONAY MOTORU
    # ==========================================
    b2b_ayar = tenant_db.query(B2BAyar).filter_by(firma_id=str(session['tenant_id'])).first()
    
    # getattr ile güvenli çekim yapıyoruz, modelde sütun yoksa bile kod çökmez, False sayar.
    oto_onay_aktif_mi = getattr(b2b_ayar, 'oto_siparis_onayi', False) if b2b_ayar else False
    
    # Ayar açıksa ONAYLANDI, kapalıysa BEKLIYOR statüsü ata
    siparis_durumu = SiparisDurumu.ONAYLANDI.value if oto_onay_aktif_mi else SiparisDurumu.BEKLIYOR.value
    durum_metni = "Otomatik Onaylandı" if oto_onay_aktif_mi else "Muhasebe Onayı Bekliyor"

    try:
        toplam = sum(item['miktar'] * item['fiyat'] for item in sepet.values())
        oto_belge_no = f"B2B-{datetime.now().strftime('%Y%m%d%H%M')}"
        
        yeni_siparis = Siparis(
            firma_id=str(session['tenant_id']),
            donem_id=str(varsayilan_donem.id) if varsayilan_donem else None, 
            sube_id=str(varsayilan_sube.id) if varsayilan_sube else None,    
            cari_id=str(session['b2b_cari_id']),
            depo_id=str(varsayilan_depo.id),
            belge_no=oto_belge_no,
            tarih=datetime.utcnow().date(),
            durum=siparis_durumu, # ✨ DİNAMİK DURUM BURADAN GİDİYOR
            aciklama=f"B2B Portal: {g.b2b_user.ad_soyad} tarafından oluşturuldu. ({durum_metni})",
            ara_toplam=toplam,
            genel_toplam=toplam,
            doviz_turu='TL'
        )
        tenant_db.add(yeni_siparis)
        tenant_db.flush() 
        
        for stok_id, detay in sepet.items():
            satir_tutar = detay['miktar'] * detay['fiyat']
            siparis_kalemi = SiparisDetay(
                siparis_id=str(yeni_siparis.id),
                stok_id=str(stok_id),
                miktar=detay['miktar'],
                birim=detay.get('birim', 'Adet'),
                birim_fiyat=detay['fiyat'],
                net_tutar=satir_tutar,
                satir_toplami=satir_tutar
            )
            tenant_db.add(siparis_kalemi)
            
        tenant_db.commit()
        session.pop('b2b_sepet', None)
        
        # Sipariş tamamlanınca bayi dashboard'una yönlendir (Dilersen buraya flash mesaj da koyabilirsin)
        return redirect(url_for('b2b.dashboard'))
        
    except Exception as e:
        tenant_db.rollback()
        import logging
        logging.getLogger(__name__).error(f"❌ B2B Sipariş Hatası: {str(e)}")
        return f"Sipariş oluşturulurken bir hata meydana geldi: {str(e)}", 500
        
# ==========================================
# B2B ONLINE TAHSİLAT (KREDİ KARTI) ROTALARI
# ==========================================

@b2b_bp.route('/odeme')
@b2b_login_required
def odeme_ekrani():
    tenant_db = get_tenant_db()
    cari_id = session.get('b2b_cari_id')
    
    # ✨ DÜZELTME: Ödeme ekranında da KESİN hesaplamayı kullanıyoruz
    bakiye_sorgu = tenant_db.query(
        func.sum(CariHareket.borc).label('toplam_borc'),
        func.sum(CariHareket.alacak).label('toplam_alacak')
    ).filter(CariHareket.cari_id == str(cari_id)).first()
    
    toplam_borc = float(bakiye_sorgu.toplam_borc or 0)
    toplam_alacak = float(bakiye_sorgu.toplam_alacak or 0)
    guncel_bakiye = toplam_borc - toplam_alacak
    
    return render_template('b2b/odeme.html', user=g.b2b_user, guncel_bakiye=guncel_bakiye)

@b2b_bp.route('/api/odeme-yap', methods=['POST'])
@b2b_login_required
def odeme_yap():
    odenecek_tutar = float(request.form.get('tutar', 0))
    kart_uzerindeki_isim = request.form.get('kart_isim', '')
    
    if odenecek_tutar <= 0:
        return jsonify({'success': False, 'message': 'Geçerli bir tutar giriniz.'}), 400
        
    tenant_db = get_tenant_db()
    
    try:
        from app.modules.firmalar.models import Donem
        from app.modules.sube.models import Sube
        from app.modules.cari.models import CariHareket, CariHesap
        import uuid
        
        varsayilan_donem = tenant_db.query(Donem).filter_by(aktif=True).first()
        varsayilan_sube = tenant_db.query(Sube).filter_by(aktif=True).first()
        belge_no = f"POS-{datetime.now().strftime('%y%m%d%H%M')}"
        
        # 1. Hareketi B2B Oturum Bilgileriyle (Personelden Bağımsız) Doğrudan Kaydet
        yeni_hareket = CariHareket(
            id=str(uuid.uuid4()),
            firma_id=str(session['tenant_id']),
            donem_id=str(varsayilan_donem.id) if varsayilan_donem else None,
            sube_id=str(varsayilan_sube.id) if varsayilan_sube else None,
            cari_id=str(session['b2b_cari_id']),
            islem_turu='TAHSILAT', # Direkt string atıyoruz ki enum hatası olmasın
            belge_no=belge_no,
            tarih=datetime.utcnow().date(),
            aciklama=f"B2B Online Kredi Kartı Tahsilatı ({kart_uzerindeki_isim})",
            borc=0,
            alacak=odenecek_tutar,
            kaynak_turu='B2B_POS',
            kaynak_id=belge_no,
            durum='ONAYLANDI'
        )
        tenant_db.add(yeni_hareket)
        
        # 2. Cari Bakiyesini Anında Güncelle
        cari = tenant_db.get(CariHesap, str(session['b2b_cari_id']))
        if cari:
            mevcut_alacak = float(cari.alacak_bakiye or 0)
            cari.alacak_bakiye = mevcut_alacak + odenecek_tutar
            
        tenant_db.commit()
        
        return jsonify({'success': True, 'message': f'{odenecek_tutar} TL tahsilat başarıyla gerçekleşti ve cari hesabınıza işlendi.'})
            
    except Exception as e:
        tenant_db.rollback()
        import logging
        logging.getLogger(__name__).error(f"❌ B2B Ödeme Hatası: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Ödeme kaydedilirken sistem hatası oluştu.'}), 500
        
@b2b_bp.route('/ekstre')
@b2b_login_required
def ekstre():
    tenant_db = get_tenant_db()
    cari_id = session.get('b2b_cari_id')
    
    # ✨ DÜZELTME: deleted_at filtresi kaldırıldı ve sıralama id'ye göre garantiye alındı
    hareketler = tenant_db.query(CariHareket).filter(
        CariHareket.cari_id == str(cari_id)
    ).order_by(
        CariHareket.tarih.asc(), 
        CariHareket.id.asc() 
    ).all()
    
    guncel_bakiye = 0
    ekstre_verisi = []
    
    for h in hareketler:
        borc = float(h.borc or 0)
        alacak = float(h.alacak or 0)
        guncel_bakiye += (borc - alacak)
        
        # ✨ Enum String Koruması
        islem_turu_str = h.islem_turu.value if hasattr(h.islem_turu, 'value') else str(h.islem_turu)
        
        ekstre_verisi.append({
            'tarih': h.tarih.strftime('%d.%m.%Y') if h.tarih else '-',
            'islem_turu': islem_turu_str,
            'belge_no': h.belge_no or '-', 
            'aciklama': h.aciklama or '-',
            'borc': borc,
            'alacak': alacak,
            'bakiye': guncel_bakiye
        })
        
    ekstre_verisi.reverse()
    return render_template('b2b/ekstre.html', hareketler=ekstre_verisi, guncel_bakiye=guncel_bakiye)
    
@b2b_bp.route('/siparislerim')
@b2b_login_required
def siparislerim():
    tenant_db = get_tenant_db()
    cari_id = session.get('b2b_cari_id')
    
    siparisler = tenant_db.query(Siparis).filter_by(cari_id=str(cari_id)).order_by(
        Siparis.tarih.desc(), 
        Siparis.created_at.desc()
    ).all()
    
    return render_template('b2b/siparislerim.html', siparisler=siparisler)