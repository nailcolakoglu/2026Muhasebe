# app/modules/stok/listeners.py

from datetime import datetime
from flask_login import current_user
from app.extensions import get_tenant_db
from app.modules.stok.models import StokHareketi
from app.modules.siparis.models import SiparisDetay
from app.enums import HareketTuru
from signals import siparis_sevk_edildi

def stok_hareketi_olustur(sender, **kwargs):
    """
    Sipariş sevk edildiğinde tetiklenir.
    NOT: Bu sinyalin çağrıldığı yer de Tenant DB context'inde olmalıdır.
    """
    tenant_db = get_tenant_db()
    
    siparis = kwargs.get('siparis')
    sevk_verileri = kwargs.get('sevk_verileri') # [{'detay_id': 1, 'miktar': 5}, ...]
    cikis_depo_id = kwargs.get('cikis_depo_id')
    
    print(f"📡 SİNYAL ALINDI: Stok Modülü (Tenant DB), Sipariş {siparis.belge_no} için çalışıyor...")

    for veri in sevk_verileri:
        detay_id = int(veri['detay_id'])
        miktar = float(veri['miktar'])
        
        if miktar <= 0: continue
        
        # Detay bilgisini çek (Tenant DB'den)
        detay = tenant_db.get(SiparisDetay, detay_id)
        
        # STOK HAREKETİNİ KAYDET
        hareket = StokHareketi(
            firma_id=siparis.firma_id,
            donem_id=siparis.donem_id,
            sube_id=siparis.sube_id,
            kullanici_id=current_user.id,
            
            stok_id=detay.stok_id,
            cikis_depo_id=cikis_depo_id,
            
            tarih=datetime.now().date(),
            belge_no=f"IRS-{siparis.belge_no}-{datetime.now().strftime('%H%M%S')}",
            hareket_turu=HareketTuru.SATIS, 
            
            miktar=miktar,
            birim_fiyat=detay.birim_fiyat,
            
            # Finansal & İzlenebilirlik
            doviz_turu=siparis.doviz_turu,
            doviz_kuru=siparis.doviz_kuru,
            kaynak_turu='siparis',
            kaynak_id=siparis.id,
            kaynak_belge_detay_id=detay.id, 
            aciklama=f"Sipariş Sevkiyatı: {siparis.belge_no}"
        )
        tenant_db.add(hareket)
        
        # Not: Commit, işlemi başlatan ana fonksiyon tarafından yapılacak (Transaction bütünlüğü)

# Dinleyiciyi Bağla
siparis_sevk_edildi.connect(stok_hareketi_olustur)