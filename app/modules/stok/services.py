# app/modules/stok/services.py

from app.extensions import get_tenant_db
from app.modules.fatura.models import Fatura
from app.modules.stok.models import StokFisi, StokHareketi, StokKart
from app.enums import StokFisTuru, FaturaTuru, StokKartTipi
from flask_login import current_user

def stok_hareketi_olustur(fatura_id):
    """
    Fatura kesinleştiğinde arka planda Stok Fişini ve Hareketlerini oluşturur.
    Tüm işlemler Tenant DB (Firebird) üzerinde döner.
    """
    tenant_db = get_tenant_db()
    
    fatura = tenant_db.get(Fatura, fatura_id)
    if not fatura: return False, "Fatura bulunamadı"

    # 1. Daha önce stok fişi oluşmuş mu? (Mükerrer kaydı önle)
    if fatura.stok_fis_id:
        eski_fis = tenant_db.get(StokFisi, fatura.stok_fis_id)
        if eski_fis:
            # İlişkili hareketleri sil
            tenant_db.query(StokHareketi).filter_by(stok_fis_id=eski_fis.id).delete()
            tenant_db.delete(eski_fis)
            tenant_db.flush()

    # 2. Fiş Türünü Belirle
    if fatura.fatura_turu == FaturaTuru.SATIS:
        fis_turu = StokFisTuru.SATIS_CIKIS 
        giris_cikis_carpan = -1 # Depodan düşecek
    elif fatura.fatura_turu == FaturaTuru.ALIS:
        fis_turu = StokFisTuru.ALIS_GIRIS
        giris_cikis_carpan = 1 # Depoya girecek
    else:
        return True, "Hizmet faturası, stok işlemi yok"

    # 3. Stok Fişi Başlığı
    stok_fisi = StokFisi(
        firma_id=fatura.firma_id,
        sube_id=fatura.sube_id,
        fis_turu=fis_turu,
        tarih=fatura.tarih,
        aciklama=f"{fatura.belge_no} nolu fatura hareketi",
        kaynak_belge_turu='fatura',
        kaynak_belge_id=fatura.id
    )
    tenant_db.add(stok_fisi)
    tenant_db.flush() # ID almak için flush
    
    # 4. Satırları (Hareketleri) Aktar
    for kalem in fatura.kalemler:
        # Hizmet stoklarını atla
        stok_kart = tenant_db.get(StokKart, kalem.stok_id)
        
        if stok_kart and hasattr(stok_kart, 'tip') and stok_kart.tip == 'hizmet':
            continue

        hareket = StokHareketi(
            firma_id=fatura.firma_id,
            stok_id=kalem.stok_id, # Modelde 'stok_id' ise 'stok_kart_id' değil
            depo_id=fatura.depo_id or 1,
            miktar=kalem.miktar,
            birim_fiyat=kalem.birim_fiyat,
            giris_cikis=giris_cikis_carpan, 
            tarih=fatura.tarih,
            stok_fis_id=stok_fisi.id # Elle ilişkilendirme garanti olur
        )
        tenant_db.add(hareket)
    
    tenant_db.commit()
    
    # 5. Bağlantıyı Kur
    fatura.stok_fis_id = stok_fisi.id
    tenant_db.commit()
    
    return True, "Stok fişi oluşturuldu"