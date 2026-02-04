from app.modules.muhasebe.models import HesapPlani
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