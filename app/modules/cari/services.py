# app/modules/cari/services.py

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy import func
from flask import current_app, session
from flask_login import current_user

# Modelleri import et
from app.extensions import db
from app.modules.cari.models import CariHesap, CariHareket
from app.modules.firmalar.models import Donem
from app.enums import CariIslemTuru

class CariService:
    
    @staticmethod
    def get_by_id(cari_id: int) -> Optional[CariHesap]:
        return CariHesap.query.get(cari_id)

    @staticmethod
    def bakiye_hesapla_ve_guncelle(cari_id: int):
        """
        Cari hesabın tüm hareketlerini tarar ve bakiyeyi günceller.
        """
        if not cari_id: return

        # Toplam Borç
        toplam_borc = db.session.query(func.coalesce(func.sum(CariHareket.borc), 0)).filter(
            CariHareket.cari_id == cari_id
        ).scalar()

        # Toplam Alacak
        toplam_alacak = db.session.query(func.coalesce(func.sum(CariHareket.alacak), 0)).filter(
            CariHareket.cari_id == cari_id
        ).scalar()

        cari = CariHesap.query.get(cari_id)
        if cari:
            cari.bakiye = Decimal(str(toplam_borc)) - Decimal(str(toplam_alacak))
            # Commit caller'a ait

    @staticmethod
    def hareket_ekle(cari_id: int, 
                     islem_turu: CariIslemTuru, 
                     belge_no: str, 
                     tarih: Any, 
                     aciklama: str, 
                     kaynak_ref: Dict[str, Any],
                     borc: Decimal = 0, 
                     alacak: Decimal = 0,
                     vade_tarihi=None,
                     donem_id=None,  # Opsiyonel parametre eklendi
                     sube_id=None):  # Opsiyonel parametre eklendi
        """
        Cari hareketi ekler.Otomatik Dönem ve Şube tamamlama özelliğine sahiptir.
        """
        try:
            # Tarih formatı kontrolü
            if isinstance(tarih, str):
                try:
                    tarih = datetime.strptime(tarih, '%Y-%m-%d').date()
                except:
                    tarih = datetime.now().date()

            # Yeni Hareket Nesnesi
            hareket = CariHareket()
            hareket.cari_id = cari_id
            
            # 1.FİRMA VE KULLANICI BİLGİSİ
            if current_user and current_user.is_authenticated:
                hareket.firma_id = current_user.firma_id
                hareket.olusturan_id = current_user.id
            else:
                hareket.firma_id = current_app.config.get('FIRMA_ID', 1)

            # 2.DÖNEM ID (KRİTİK DÜZELTME)
            if donem_id:
                hareket.donem_id = donem_id
            elif session.get('aktif_donem_id'):
                hareket.donem_id = session.get('aktif_donem_id')
            else:
                # Session'da yoksa veritabanından son aktif dönemi bul
                son_donem = Donem.query.filter_by(firma_id=hareket.firma_id, aktif=True).order_by(Donem.id.desc()).first()
                if son_donem:
                    hareket.donem_id = son_donem.id
                else:
                    # Hiç dönem yoksa varsayılan 1 (Hata almamak için)
                    hareket.donem_id = 1

            # 3.ŞUBE ID
            if sube_id:
                hareket.sube_id = sube_id
            elif session.get('aktif_sube_id'):
                hareket.sube_id = session.get('aktif_sube_id')
            elif hasattr(current_user, 'sube_id') and current_user.sube_id:
                hareket.sube_id = current_user.sube_id

            # Diğer Alanlar
            hareket.islem_turu = islem_turu
            hareket.belge_no = belge_no
            hareket.tarih = tarih
            hareket.vade_tarihi = vade_tarihi or tarih
            hareket.aciklama = aciklama
            
            hareket.borc = Decimal(str(borc))
            hareket.alacak = Decimal(str(alacak))
            
            # Kaynak Referansı
            if kaynak_ref:
                hareket.kaynak_turu = kaynak_ref.get('tur')
                hareket.kaynak_id = kaynak_ref.get('id')

            db.session.add(hareket)
            db.session.flush()

            # Bakiyeyi güncelle
            CariService.bakiye_hesapla_ve_guncelle(cari_id)
            
            return True, "Cari hareket eklendi."

        except Exception as e:
            # Hata detayını görebilmek için konsola yazdırıyoruz
            print(f"❌ Cari Hareket Ekleme Hatası: {e}")
            raise e