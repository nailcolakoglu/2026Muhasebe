# app/modules/cari/listeners.py

from blinker import receiver
from app.signals import banka_hareket_onaylandi, kasa_hareket_onaylandi
from app.enums import CariIslemTuru
from app.modules.cari.services import CariService

@receiver(kasa_hareket_onaylandi)
def on_kasa_hareket(sender, **kwargs):
    hareket = sender 
    if hareket.cari_id:
        # Kasa Tahsilat -> Cari Alacak (Müşteri borcu düşer)
        # Kasa Tediye -> Cari Borç (Müşteri borçlanır veya satıcıya ödeme)
        # İş mantığınıza göre burayı özelleştirin
        pass

@receiver(banka_hareket_onaylandi)
def on_banka_hareket(sender, **kwargs):
    hareket = sender
    
    if hareket.cari_id:
        # Tahsilat ise Cari ALACAK çalışır
        islem_turu = "TAHSILAT" if hareket.islem_turu == "TAHSILAT" else "TEDIYE"
        
        borc = hareket.tutar if islem_turu == "TEDIYE" else 0
        alacak = hareket.tutar if islem_turu == "TAHSILAT" else 0
        
        CariService.hareket_ekle(
            cari_id=hareket.cari_id,
            islem_turu=islem_turu,
            belge_no=hareket.belge_no,
            tarih=hareket.tarih,
            aciklama=f"Banka İşlemi: {hareket.aciklama}",
            borc=borc,
            alacak=alacak,
            kaynak_ref={'tur': 'BANKA', 'id': hareket.id}
        )