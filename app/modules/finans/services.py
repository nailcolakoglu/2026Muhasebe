# app/modules/finans/services.py

from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.modules.finans.models import FinansIslem
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.modules.cek.models import CekSenet
from app.modules.cari.models import CariHesap
from app.modules.firmalar.models import Firma, Donem
from app.modules.kasa_hareket.services import KasaHareketService
from app.modules.banka_hareket.services import BankaHareketService
from app.modules.cari.services import CariService
from app.araclar import para_cevir, numara_uret
from app.enums import CariIslemTuru, FinansIslemTuru, BankaIslemTuru

class FinansService:
    
    @staticmethod
    def create_makbuz(data: Dict[str, Any], user_id: int) -> FinansIslem:
        """Tahsilat/Tediye Makbuzu oluşturur."""
        try:
            # 1.Ana Kayıt
            makbuz = FinansIslem(
                firma_id=data['firma_id'],
                donem_id=data['donem_id'],
                sube_id=data.get('sube_id'),
                cari_id=data.get('cari_id'),
                islem_turu=data['islem_turu'],
                belge_no=data['belge_no'],
                tarih=data['tarih'],
                aciklama=data.get('aciklama', ''),
                plasiyer_id=user_id,
                doviz_cinsi=data.get('doviz_cinsi', 'TL'),
                durum='onaylandi'
            )
            db.session.add(makbuz)
            db.session.flush()

            # Format Düzeltmeleri
            toplam_nakit = para_cevir(data.get('nakit_tutar'))
            toplam_cek = Decimal('0.00')

            # 2.Nakit İşlemi
            if data.get('kasa_id') and toplam_nakit > 0:
                kasa_har = KasaHareket(
                    firma_id=makbuz.firma_id,
                    donem_id=makbuz.donem_id,
                    kasa_id=int(data['kasa_id']),
                    cari_id=makbuz.cari_id,
                    islem_turu='tahsilat' if makbuz.islem_turu == 'tahsilat' else 'tediye',
                    belge_no=makbuz.belge_no,
                    tarih=makbuz.tarih,
                    tutar=toplam_nakit,
                    aciklama=f"Makbuz: {makbuz.belge_no}",
                    onaylandi=True,
                    finans_islem_id=makbuz.id
                )
                db.session.add(kasa_har)

            # 3.Çek İşlemleri
            if 'cekler' in data and data['cekler']:
                yon = 'ALINAN' if makbuz.islem_turu == 'tahsilat' else 'VERILEN'
                for cek_item in data['cekler']:
                    cek_tutar = para_cevir(cek_item.get('tutar'))
                    if cek_tutar > 0:
                        toplam_cek += cek_tutar
                        yeni_cek = CekSenet(
                            firma_id=makbuz.firma_id,
                            cari_id=makbuz.cari_id,
                            finans_islem_id=makbuz.id,
                            tur='CEK',
                            yon=yon,
                            portfoy_no=cek_item.get('portfoy_no'),
                            cek_no=cek_item.get('cek_no'),
                            tarih=makbuz.tarih,
                            vade_tarihi=cek_item.get('vade_tarihi') or makbuz.tarih,
                            banka_adi=cek_item.get('banka_adi'),
                            tutar=cek_tutar,
                            durum='PORTFOY'
                        )
                        db.session.add(yeni_cek)

            # 4.Toplamlar
            makbuz.toplam_nakit = toplam_nakit
            makbuz.toplam_cek = toplam_cek
            makbuz.genel_toplam = toplam_nakit + toplam_cek
            
            # 5.Cari Entegrasyonu
            if makbuz.cari_id and makbuz.genel_toplam > 0:
                islem_turu_enum = CariIslemTuru.TAHSILAT if makbuz.islem_turu == 'tahsilat' else CariIslemTuru.TEDIYE
                borc_tutar = makbuz.genel_toplam if makbuz.islem_turu == 'tediye' else 0
                alacak_tutar = makbuz.genel_toplam if makbuz.islem_turu == 'tahsilat' else 0
                
                CariService.hareket_ekle(
                    cari_id=makbuz.cari_id,
                    islem_turu=islem_turu_enum,
                    evrak_no=makbuz.belge_no,
                    tarih=makbuz.tarih,
                    borc=borc_tutar,
                    alacak=alacak_tutar,
                    aciklama=f"Makbuz No: {makbuz.belge_no} ({makbuz.aciklama})",
                    kaynak_ref={'tur': 'FINANS', 'id': makbuz.id}
                )

            db.session.commit()

            # 6.Bakiye Güncelle
            if data.get('kasa_id'):
                KasaHareketService.bakiye_guncelle(int(data['kasa_id']))
            
            return makbuz

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def transfer_yap(data: Dict[str, Any]) -> bool:
        """Virman (İç Transfer)"""
        try:
            kaynak_tip, kaynak_id = data['kaynak'].split('_')
            hedef_tip, hedef_id = data['hedef'].split('_')
            kaynak_id, hedef_id = int(kaynak_id), int(hedef_id)
            
            # Tutar Güvenliği
            raw_tutar = str(data['tutar'])
            if ',' in raw_tutar: raw_tutar = raw_tutar.replace('.', '').replace(',', '.')
            tutar = Decimal(raw_tutar)

            tarih = data['tarih']
            belge_no = data['belge_no']
            aciklama = data.get('aciklama', '')

            # ÇIKIŞ
            if kaynak_tip == 'KASA':
                cikis = KasaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    kasa_id=kaynak_id, 
                    islem_turu=BankaIslemTuru.VIRMAN_CIKIS, 
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Çıkış -> {hedef_tip} #{hedef_id} - {aciklama}",
                    onaylandi=True
                )
                db.session.add(cikis)
            else: # BANKA
                cikis = BankaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    banka_id=kaynak_id, 
                    islem_turu=BankaIslemTuru.VIRMAN_CIKIS,
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Çıkış -> {hedef_tip} #{hedef_id} - {aciklama}"
                )
                db.session.add(cikis)

            # GİRİŞ
            if hedef_tip == 'KASA':
                giris = KasaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    kasa_id=hedef_id, 
                    islem_turu=BankaIslemTuru.VIRMAN_GIRIS,
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Giriş <- {kaynak_tip} #{kaynak_id} - {aciklama}",
                    onaylandi=True
                )
                db.session.add(giris)
            else: # BANKA
                giris = BankaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    banka_id=hedef_id, 
                    islem_turu=BankaIslemTuru.VIRMAN_GIRIS,
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Giriş <- {kaynak_tip} #{kaynak_id} - {aciklama}"
                )
                db.session.add(giris)

            db.session.commit()

            # Bakiye Güncellemeleri
            if kaynak_tip == 'KASA': KasaHareketService.bakiye_guncelle(kaynak_id)
            else: BankaHareketService.bakiye_guncelle(kaynak_id)

            if hedef_tip == 'KASA': KasaHareketService.bakiye_guncelle(hedef_id)
            else: BankaHareketService.bakiye_guncelle(hedef_id)

            return True

        except Exception as e:
            db.session.rollback()
            raise e

    # 👇 YENİ EKLENEN METOD (Gider Ekleme) 👇
    @staticmethod
    def gider_kaydet(data: Dict[str, Any]) -> bool:
        """Gider / Masraf Kaydı"""
        try:
            tip, hesap_id = data['hesap'].split('_')
            hesap_id = int(hesap_id)
            
            # Tutar Güvenliği
            raw_tutar = str(data['tutar'])
            if ',' in raw_tutar: raw_tutar = raw_tutar.replace('.', '').replace(',', '.')
            tutar = Decimal(raw_tutar)

            aciklama_tam = f"[GİDER-{data['gider_turu'].upper()}] {data['aciklama']}"
            
            if tip == 'KASA':
                cikis = KasaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    kasa_id=hesap_id, 
                    islem_turu=BankaIslemTuru.TEDIYE, # Gider bir çıkış işlemidir
                    tarih=data['tarih'], 
                    tutar=tutar, 
                    belge_no=data['belge_no'],
                    aciklama=aciklama_tam,
                    onaylandi=True
                )
                db.session.add(cikis)
                # Commit'i aşağıda yapıyoruz, burada flush gerekebilir
                db.session.flush()
                # Kasa bakiyesini en son güncelleyeceğiz
            else: # BANKA
                cikis = BankaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    banka_id=hesap_id, 
                    islem_turu=BankaIslemTuru.TEDIYE,
                    tarih=data['tarih'], 
                    tutar=tutar, 
                    belge_no=data['belge_no'],
                    aciklama=aciklama_tam
                )
                db.session.add(cikis)
                db.session.flush()

            db.session.commit()

            # Bakiye Güncelleme (Commit Sonrası)
            if tip == 'KASA': 
                KasaHareketService.bakiye_guncelle(hesap_id)
            else: 
                BankaHareketService.bakiye_guncelle(hesap_id)

            return True
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_makbuz(makbuz_id: int) -> bool:
        makbuz = FinansIslem.query.get(makbuz_id)
        if not makbuz: raise ValueError("Makbuz bulunamadı")
        try:
            db.session.delete(makbuz)
            db.session.commit()
            if makbuz.cari_id:
                CariService.bakiye_hesapla_ve_guncelle(makbuz.cari_id)
            return True
        except Exception as e:
            db.session.rollback()
            raise e