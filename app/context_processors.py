# app/context_processors.py

from flask import session, g
from flask_login import current_user
from datetime import datetime
from app.extensions import get_tenant_db

def inject_global_vars():
    """
    Tüm şablonlarda (base.html) kullanılacak global değişkenler.
    Üst menüdeki 'Şube Seçimi' ve 'Dönem Seçimi' buradan beslenir.
    """
    tenant_db = get_tenant_db()
    
    # Varsayılan Boş Listeler (Hata almamak için)
    tum_subeler = []
    tum_donemler = []

    if current_user.is_authenticated and tenant_db:
        try:
            # Modelleri burada import ediyoruz (Circular Import hatasını önlemek için)
            from app.modules.sube.models import Sube
            from app.modules.firmalar.models import Donem
            
            # 1. ŞUBE LİSTESİ
            # Admin/Patron ise hepsini görsün, değilse yetkili olduklarını (ileride eklenebilir)
            tum_subeler = tenant_db.query(Sube).filter_by(aktif=True).order_by(Sube.ad).all()
            
            # 2. DÖNEM LİSTESİ
            tum_donemler = tenant_db.query(Donem).filter_by(aktif=True).order_by(Donem.yil.desc()).all()

        except Exception as e:
            # Hata olsa bile sistemi durdurma, sadece menü boş gelsin
            print(f"⚠️ Context Processor Hatası: {e}")

    # Şablona gidecek sözlük
    return dict(
        # Global Nesneler
        aktif_tenant=g.get('tenant'),
        aktif_firma=g.get('firma'),
        aktif_donem=g.get('donem'),
        aktif_sube=g.get('sube'),
        aktif_bolge=g.get('bolge'),
        
        # Session Bilgileri
        tenant_name=session.get('tenant_name', ''),
        tenant_role=session.get('tenant_role', ''),
        
        # 🟢 EKSİK OLAN LİSTELER (Sorunu Çözen Kısım)
        tum_subeler=tum_subeler,
        tum_donemler=tum_donemler,
        
        # Yardımcılar
        bugun=datetime.now()
    )