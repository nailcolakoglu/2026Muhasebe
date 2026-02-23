# app/context_processors.py

from flask import session, g
from flask_login import current_user
from datetime import datetime
from app.extensions import get_tenant_db
import logging

logger = logging.getLogger(__name__)


def inject_global_vars():
    """
    Tüm şablonlarda kullanılacak global değişkenler
    
    Üst menüdeki 'Şube Seçimi' ve 'Dönem Seçimi' buradan beslenir.
    """
    tenant_db = get_tenant_db()
    
    # Varsayılan Boş Listeler
    tum_subeler = []
    tum_donemler = []
    aktif_firma = None

    if current_user.is_authenticated and tenant_db:
        try:
            # Modelleri import et
            from app.modules.sube.models import Sube
            from app.modules.firmalar.models import Donem, Firma
            
            # 1. ✅ FİRMA BUL (UUID - ilk kayıt)
            aktif_firma = tenant_db.query(Firma).first()
            
            if aktif_firma:
                # 2. ✅ ŞUBE LİSTESİ (Firmaya bağlı)
                tum_subeler = tenant_db.query(Sube).filter_by(
                    firma_id=aktif_firma.id,  # ✅ Firma UUID'sine göre filtrele
                    aktif=True
                ).order_by(Sube.ad).all()
                
                # 3. ✅ DÖNEM LİSTESİ (Firmaya bağlı, AKTİF OLMAYANLARI DA GÖSTER)
                tum_donemler = tenant_db.query(Donem).filter_by(
                    firma_id=aktif_firma.id  # ✅ Firma UUID'sine göre filtrele
                    # ❌ .filter_by(aktif=True) KALDIRDIK!
                ).order_by(Donem.yil.desc()).all()
                
                logger.debug(
                    f"✅ Context yüklendi: {len(tum_subeler)} şube, "
                    f"{len(tum_donemler)} dönem (firma: {aktif_firma.unvan})"
                )
            else:
                logger.warning("⚠️ Firma bulunamadı (tenant_db var ama Firma tablosu boş)")

        except Exception as e:
            logger.error(f"❌ Context processor hatası: {e}", exc_info=True)

    # Şablona gönder
    return dict(
        # Global Nesneler
        aktif_tenant=g.get('tenant'),
        aktif_firma=aktif_firma,  # ✅ Firma nesnesini de gönder
        aktif_donem=g.get('donem'),
        aktif_sube=g.get('sube'),
        aktif_bolge=g.get('bolge'),
        
        # Session Bilgileri
        tenant_name=session.get('tenant_name', ''),
        tenant_role=session.get('tenant_role', ''),
        
        # Listeler (Dropdown için)
        tum_subeler=tum_subeler,
        tum_donemler=tum_donemler,
        
        # Yardımcılar
        bugun=datetime.now()
    )