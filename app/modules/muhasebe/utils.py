# app/modules/muhasebe/utils.py

from app.modules.muhasebe.models import HesapPlani
from app.enums import HesapSinifi, BakiyeTuru, OzelHesapTipi
from flask_login import current_user
from app.extensions import get_tenant_db # GOLDEN RULE

def get_muhasebe_hesaplari():
    """
    Formlarda selectbox için hesap planını getirir.
    Sadece 'muavin' (alt) hesapları seçilebilir yapar.
    Veritabanı: Tenant DB (Firebird)
    """
    # Eğer kullanıcı giriş yapmamışsa boş liste dön
    if not current_user or not current_user.is_authenticated:
        return []

    tenant_db = get_tenant_db()
    
    # Hesap Planı Tenant DB'de
    hesaplar = tenant_db.query(HesapPlani).filter_by(
        firma_id=current_user.firma_id, 
        aktif=True
    ).order_by(HesapPlani.kod).all()
    
    secenekler = []
    for h in hesaplar:
        # Hesap Tipi kontrolü
        is_muavin = getattr(h, 'hesap_tipi', 'muavin') == 'muavin' or str(getattr(h, 'hesap_tipi', 'muavin')) == 'muavin'
        # Enum güvenliği için string çevrimi eklendi
        try:
            if hasattr(h.hesap_tipi, 'value'):
                is_muavin = (h.hesap_tipi.value == 'muavin')
        except: pass
        
        if is_muavin:
            secenekler.append((h.id, f"{h.kod} - {h.ad}"))
            
    return secenekler

def varsayilan_hesap_planini_yukle(tenant_db, firma_id):
    """
    Yeni kurulan bir firma için temel Tekdüzen Hesap Planını (TDHP) otomatik oluşturur.
    """
    standart_hesaplar = [
        # --- ANA HESAPLAR ---
        {'kod': '100', 'ad': 'Kasa', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.BORC, 'ozel': OzelHesapTipi.KASA, 'ust': None},
        {'kod': '102', 'ad': 'Bankalar', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.BORC, 'ozel': OzelHesapTipi.BANKA, 'ust': None},
        {'kod': '120', 'ad': 'Alıcılar', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.HER_IKISI, 'ozel': OzelHesapTipi.STANDART, 'ust': None},
        {'kod': '191', 'ad': 'İndirilecek KDV', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.BORC, 'ozel': OzelHesapTipi.ALIS_KDV, 'ust': None},
        {'kod': '320', 'ad': 'Satıcılar', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.HER_IKISI, 'ozel': OzelHesapTipi.STANDART, 'ust': None},
        {'kod': '391', 'ad': 'Hesaplanan KDV', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.ALACAK, 'ozel': OzelHesapTipi.SATIS_KDV, 'ust': None},
        {'kod': '600', 'ad': 'Yurtiçi Satışlar', 'sinif': HesapSinifi.ANA_HESAP, 'bakiye': BakiyeTuru.ALACAK, 'ozel': OzelHesapTipi.STANDART, 'ust': None},
        
        # --- MUAVİN (ALT) HESAPLAR ---
        {'kod': '100.01', 'ad': 'Merkez TL Kasası', 'sinif': HesapSinifi.MUAVIN_HESAP, 'bakiye': BakiyeTuru.BORC, 'ozel': OzelHesapTipi.KASA, 'ust': '100'},
        {'kod': '191.18', 'ad': '%18 İndirilecek KDV', 'sinif': HesapSinifi.MUAVIN_HESAP, 'bakiye': BakiyeTuru.BORC, 'ozel': OzelHesapTipi.ALIS_KDV, 'ust': '191'},
        {'kod': '191.20', 'ad': '%20 İndirilecek KDV', 'sinif': HesapSinifi.MUAVIN_HESAP, 'bakiye': BakiyeTuru.BORC, 'ozel': OzelHesapTipi.ALIS_KDV, 'ust': '191'},
        {'kod': '391.18', 'ad': '%18 Hesaplanan KDV', 'sinif': HesapSinifi.MUAVIN_HESAP, 'bakiye': BakiyeTuru.ALACAK, 'ozel': OzelHesapTipi.SATIS_KDV, 'ust': '391'},
        {'kod': '391.20', 'ad': '%20 Hesaplanan KDV', 'sinif': HesapSinifi.MUAVIN_HESAP, 'bakiye': BakiyeTuru.ALACAK, 'ozel': OzelHesapTipi.SATIS_KDV, 'ust': '391'},
        {'kod': '600.01', 'ad': 'Ticari Mal Satışları', 'sinif': HesapSinifi.MUAVIN_HESAP, 'bakiye': BakiyeTuru.ALACAK, 'ozel': OzelHesapTipi.STANDART, 'ust': '600'},
    ]

    hesap_objeleri = {}

    for h in standart_hesaplar:
        # Üst hesap ID'sini bul
        ust_id = None
        if h['ust'] and h['ust'] in hesap_objeleri:
            ust_id = hesap_objeleri[h['ust']].id
            
        yeni_hesap = HesapPlani(
            firma_id=firma_id,
            kod=h['kod'],
            ad=h['ad'],
            hesap_tipi=h['sinif'],
            bakiye_turu=h['bakiye'],
            ozel_hesap_tipi=h['ozel'],
            ust_hesap_id=ust_id,
            seviye=2 if ust_id else 1,
            aktif=True
        )
        tenant_db.add(yeni_hesap)
        tenant_db.flush() # ID'yi alabilmek için
        hesap_objeleri[h['kod']] = yeni_hesap

    tenant_db.commit()
    return True