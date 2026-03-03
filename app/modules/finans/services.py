# app/modules/finans/services.py

from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal
from datetime import datetime
import logging

from app.extensions import get_tenant_db # 🔥 SAAS MİMARİSİ İÇİN ŞART
from app.modules.finans.models import FinansIslem
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.modules.cek.models import CekSenet
from app.modules.cari.models import CariHesap
from app.modules.kasa_hareket.services import KasaService # İsim güncellendi
from app.modules.banka_hareket.services import BankaHareketService
from app.modules.cari.services import CariService
from app.modules.muhasebe.services import MuhasebeEntegrasyonService # Muhasebe Motoru
from app.araclar import para_cevir, numara_uret
from app.enums import CariIslemTuru, FinansIslemTuru, BankaIslemTuru
from app.signals import tahsilat_yapildi, tediye_yapildi # Sinyaller

logger = logging.getLogger(__name__)

class FinansService:
    
    @staticmethod
    def create_makbuz(data: Dict[str, Any], user_id: str) -> Tuple[bool, str, Optional[FinansIslem]]:
        """Tahsilat/Tediye Makbuzu oluşturur ve alt kalemleri işler."""
        tenant_db = get_tenant_db()
        try:
            # 1. Ana Kayıt
            makbuz = FinansIslem(
                firma_id=data['firma_id'],
                donem_id=data['donem_id'],
                sube_id=data.get('sube_id'),
                cari_id=data.get('cari_id'),
                islem_turu=data['islem_turu'],
                belge_no=data['belge_no'],
                tarih=data['tarih'],
                aciklama=data.get('aciklama', ''),
                plasiyer_id=str(user_id),
                doviz_cinsi=data.get('doviz_cinsi', 'TL'),
                durum='onaylandi'
            )
            tenant_db.add(makbuz)
            tenant_db.flush()

            # Format Düzeltmeleri
            toplam_nakit = para_cevir(data.get('nakit_tutar'))
            toplam_cek = Decimal('0.00')

            # 2. Nakit İşlemi (Kasa)
            if data.get('kasa_id') and toplam_nakit > 0:
                kasa_har = KasaHareket(
                    firma_id=makbuz.firma_id,
                    donem_id=makbuz.donem_id,
                    kasa_id=str(data['kasa_id']), # UUID Düzeltmesi
                    cari_id=makbuz.cari_id,
                    islem_turu='tahsilat' if makbuz.islem_turu == 'tahsilat' else 'tediye',
                    belge_no=makbuz.belge_no,
                    tarih=makbuz.tarih,
                    tutar=toplam_nakit,
                    aciklama=f"Makbuz: {makbuz.belge_no}",
                    onaylandi=True,
                    finans_islem_id=str(makbuz.id)
                )
                tenant_db.add(kasa_har)
                tenant_db.flush()
                
                # 🔥 Kasa İşlemini Muhasebeleştir (100 Kasa <-> 120/320 Cari)
                MuhasebeEntegrasyonService.entegre_et_kasa(str(kasa_har.id))

            # 3. Çek İşlemleri
            if 'cekler' in data and data['cekler']:
                yon = 'ALINAN' if makbuz.islem_turu == 'tahsilat' else 'VERILEN'
                cek_islem_tipi = 'giris' if makbuz.islem_turu == 'tahsilat' else 'cikis'
                
                for cek_item in data['cekler']:
                    cek_tutar = para_cevir(cek_item.get('tutar'))
                    if cek_tutar > 0:
                        toplam_cek += cek_tutar
                        yeni_cek = CekSenet(
                            firma_id=makbuz.firma_id,
                            cari_id=makbuz.cari_id,
                            finans_islem_id=str(makbuz.id),
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
                        tenant_db.add(yeni_cek)
                        tenant_db.flush()
                        
                        # 🔥 Çek İşlemini Muhasebeleştir (101 Çekler <-> 120/320 Cari)
                        MuhasebeEntegrasyonService.entegre_et_cek(str(yeni_cek.id), cek_islem_tipi)

            # 4. Toplamlar
            makbuz.toplam_nakit = toplam_nakit
            makbuz.toplam_cek = toplam_cek
            makbuz.genel_toplam = toplam_nakit + toplam_cek
            
            # 5. Cari Entegrasyonu (Tek Seferde)
            if makbuz.cari_id and makbuz.genel_toplam > 0:
                islem_turu_enum = CariIslemTuru.TAHSILAT if makbuz.islem_turu == 'tahsilat' else CariIslemTuru.TEDIYE
                borc_tutar = makbuz.genel_toplam if makbuz.islem_turu == 'tediye' else 0
                alacak_tutar = makbuz.genel_toplam if makbuz.islem_turu == 'tahsilat' else 0
                
                CariService.hareket_ekle(
                    cari_id=str(makbuz.cari_id),
                    islem_turu=islem_turu_enum,
                    belge_no=makbuz.belge_no,
                    tarih=makbuz.tarih,
                    borc=borc_tutar,
                    alacak=alacak_tutar,
                    aciklama=f"Makbuz No: {makbuz.belge_no} ({makbuz.aciklama})",
                    kaynak_ref={'tur': 'FINANS', 'id': str(makbuz.id)},
                    tenant_db=tenant_db # Mevcut session'ı kullan
                )

            tenant_db.commit()

            # 6. Sinyalleri Ateşle
            if makbuz.islem_turu == 'tahsilat':
                tahsilat_yapildi.send(makbuz)
            else:
                tediye_yapildi.send(makbuz)

            # 7. Bakiye Güncelle
            if data.get('kasa_id'):
                KasaService.bakiye_guncelle(str(data['kasa_id']))
            
            logger.info(f"✅ Makbuz başarıyla oluşturuldu: {makbuz.belge_no}")
            return True, "Makbuz başarıyla kaydedildi.", makbuz

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Makbuz oluşturma hatası: {str(e)}", exc_info=True)
            return False, f"Hata: {str(e)}", None

    @staticmethod
    def transfer_yap(data: Dict[str, Any]) -> Tuple[bool, str]:
        """Virman (Kasa/Banka Arası İç Transfer)"""
        tenant_db = get_tenant_db()
        try:
            kaynak_tip, kaynak_id = data['kaynak'].split('_')
            hedef_tip, hedef_id = data['hedef'].split('_')
            kaynak_id, hedef_id = str(kaynak_id), str(hedef_id)
            
            # Tutar Güvenliği
            raw_tutar = str(data['tutar'])
            if ',' in raw_tutar: raw_tutar = raw_tutar.replace('.', '').replace(',', '.')
            tutar = Decimal(raw_tutar)

            tarih = data['tarih']
            belge_no = data['belge_no']
            aciklama = data.get('aciklama', '')

            # ÇIKIŞ (Kaynak)
            if kaynak_tip == 'KASA':
                cikis = KasaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    kasa_id=kaynak_id, 
                    islem_turu='VIRMAN_CIKIS', 
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Çıkış -> {hedef_tip} - {aciklama}",
                    onaylandi=True
                )
                if hedef_tip == 'BANKA': cikis.karsi_banka_id = hedef_id
                elif hedef_tip == 'KASA': cikis.karsi_kasa_id = hedef_id
                tenant_db.add(cikis)
                tenant_db.flush()
                MuhasebeEntegrasyonService.entegre_et_kasa(str(cikis.id))
            else: # BANKA
                cikis = BankaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    banka_id=kaynak_id, 
                    islem_turu=BankaIslemTuru.VIRMAN_CIKIS,
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Çıkış -> {hedef_tip} - {aciklama}"
                )
                if hedef_tip == 'BANKA': cikis.karsi_banka_id = hedef_id
                elif hedef_tip == 'KASA': cikis.kasa_id = hedef_id
                tenant_db.add(cikis)
                tenant_db.flush()
                MuhasebeEntegrasyonService.entegre_et_banka(str(cikis.id))

            # GİRİŞ (Hedef)
            if hedef_tip == 'KASA':
                giris = KasaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    kasa_id=hedef_id, 
                    islem_turu='VIRMAN_GIRIS',
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Giriş <- {kaynak_tip} - {aciklama}",
                    onaylandi=True
                )
                if kaynak_tip == 'BANKA': giris.karsi_banka_id = kaynak_id
                elif kaynak_tip == 'KASA': giris.karsi_kasa_id = kaynak_id
                tenant_db.add(giris)
                tenant_db.flush()
                MuhasebeEntegrasyonService.entegre_et_kasa(str(giris.id))
            else: # BANKA
                giris = BankaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    banka_id=hedef_id, 
                    islem_turu=BankaIslemTuru.VIRMAN_GIRIS,
                    tarih=tarih, tutar=tutar, belge_no=belge_no,
                    aciklama=f"Trf.Giriş <- {kaynak_tip} - {aciklama}"
                )
                if kaynak_tip == 'BANKA': giris.karsi_banka_id = kaynak_id
                elif kaynak_tip == 'KASA': giris.kasa_id = kaynak_id
                tenant_db.add(giris)
                tenant_db.flush()
                MuhasebeEntegrasyonService.entegre_et_banka(str(giris.id))

            tenant_db.commit()

            # Bakiye Güncellemeleri
            if kaynak_tip == 'KASA': KasaService.bakiye_guncelle(kaynak_id)
            else: BankaHareketService.bakiye_guncelle(kaynak_id)

            if hedef_tip == 'KASA': KasaService.bakiye_guncelle(hedef_id)
            else: BankaHareketService.bakiye_guncelle(hedef_id)

            return True, "Virman başarıyla gerçekleşti ve muhasebeleştirildi."

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Virman hatası: {str(e)}", exc_info=True)
            return False, f"Hata: {str(e)}"

    @staticmethod
    def gider_kaydet(data: Dict[str, Any]) -> Tuple[bool, str]:
        """Gider / Masraf Kaydı"""
        tenant_db = get_tenant_db()
        try:
            tip, hesap_id = data['hesap'].split('_')
            hesap_id = str(hesap_id)
            
            # Tutar Güvenliği
            raw_tutar = str(data['tutar'])
            if ',' in raw_tutar: raw_tutar = raw_tutar.replace('.', '').replace(',', '.')
            tutar = Decimal(raw_tutar)

            aciklama_tam = f"[GİDER-{data['gider_turu'].upper()}] {data['aciklama']}"
            
            if tip == 'KASA':
                cikis = KasaHareket(
                    firma_id=data['firma_id'], donem_id=data['donem_id'],
                    kasa_id=hesap_id, 
                    islem_turu='tediye', # Gider bir çıkış işlemidir
                    tarih=data['tarih'], 
                    tutar=tutar, 
                    belge_no=data['belge_no'],
                    aciklama=aciklama_tam,
                    onaylandi=True
                )
                tenant_db.add(cikis)
                tenant_db.flush()
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
                tenant_db.add(cikis)
                tenant_db.flush()

            tenant_db.commit()

            # Bakiye Güncelleme (Commit Sonrası)
            if tip == 'KASA': 
                KasaService.bakiye_guncelle(hesap_id)
            else: 
                BankaHareketService.bakiye_guncelle(hesap_id)

            return True, "Gider başarıyla kaydedildi."
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Gider kayıt hatası: {str(e)}", exc_info=True)
            return False, f"Hata: {str(e)}"

    @staticmethod
    def delete_makbuz(makbuz_id: str) -> Tuple[bool, str]:
        tenant_db = get_tenant_db()
        makbuz = tenant_db.get(FinansIslem, str(makbuz_id))
        
        if not makbuz: 
            return False, "Makbuz bulunamadı"
            
        try:
            cari_id = makbuz.cari_id
            
            # Bağlı Kasa, Çek, Banka hareketleri DB seviyesinde "cascade='all, delete-orphan'" 
            # ile silinmiyorsa burada manuel temizlik gerekebilir.
            # Şimdilik ana makbuzu siliyoruz.
            tenant_db.delete(makbuz)
            tenant_db.commit()
            
            if cari_id:
                CariService.bakiye_hesapla_ve_guncelle(cari_id, tenant_db=tenant_db)
                
            return True, "Makbuz başarıyla silindi."
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Makbuz silme hatası: {str(e)}")
            return False, f"Hata: {str(e)}"