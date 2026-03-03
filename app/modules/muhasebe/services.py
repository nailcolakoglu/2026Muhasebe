# app/modules/muhasebe/services.py

import logging
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func, case, cast, Integer, literal
from flask_login import current_user
from flask import session # ✨ EKLENDİ: Hayati import eksiği giderildi

from app.araclar import numara_uret
from app.extensions import get_tenant_db # GOLDEN RULE

# Modeller
from app.modules.banka.models import BankaHesap
from app.modules.muhasebe.models import MuhasebeFisi, MuhasebeFisiDetay, HesapPlani
from app.modules.fatura.models import Fatura
from app.modules.firmalar.models import Firma, Donem
from app.modules.sube.models import Sube
from app.modules.cari.models import CariHesap
from app.modules.stok.models import StokKart, StokKDVGrubu, StokMuhasebeGrubu
from app.modules.kategori.models import StokKategori
from app.modules.kullanici.models import Kullanici
from app.modules.kasa.models import Kasa
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.models import Sayac, AIRaporAyarlari
from app.modules.depo.models import Depo
from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
from app.modules.finans.models import FinansIslem
from app.modules.siparis.models import OdemePlani
from app.modules.lokasyon.models import Sehir, Ilce
from app.enums import (
    BankaIslemTuru, FinansIslemTuru, MuhasebeFisTuru, 
    HesapSinifi, BakiyeTuru, OzelHesapTipi
)

logger = logging.getLogger(__name__)

# =============================================================================
# 0. GÜVENLİK VE KİLİT MEKANİZMALARI
# =============================================================================

def tarih_kilidi_kontrol(tarih, donem_id, tenant_db=None):
    """
    Belirtilen tarihe kayıt atılıp atılamayacağını kontrol eder.
    Eğer Resmi Defter (e-Defter) basıldıysa o tarihe hiçbir modülden işlem yapılamaz!
    """
    if tenant_db is None:
        from app.extensions import get_tenant_db
        tenant_db = get_tenant_db()
        
    from app.modules.firmalar.models import Donem
    donem = tenant_db.get(Donem, str(donem_id))
    
    if not donem:
        raise Exception("İlgili dönem bulunamadı!")

    # Gelen tarih string ise date objesine çevir
    if isinstance(tarih, str):
        try:
            islem_tarihi = datetime.strptime(tarih, '%Y-%m-%d').date()
        except ValueError:
            raise Exception("Geçersiz tarih formatı!")
    else:
        if hasattr(tarih, 'date'):
            islem_tarihi = tarih.date()
        else:
            islem_tarihi = tarih

    # 🔥 KİLİT KONTROLÜ
    if donem.son_yevmiye_tarihi:
        if islem_tarihi <= donem.son_yevmiye_tarihi:
            kilit_tarihi_str = donem.son_yevmiye_tarihi.strftime('%d.%m.%Y')
            raise Exception(
                f"⛔ GÜVENLİK UYARISI: {kilit_tarihi_str} tarihine kadar e-Defter (Resmi Defter) onaylanmıştır! "
                f"Bu tarihe veya öncesine ({islem_tarihi.strftime('%d.%m.%Y')}) fiş giremez, silemez veya fatura kesemezsiniz."
            )
    return True

# =============================================================================
# 1. MANUEL İŞLEMLER VE OPTİMİZE BAKİYE MOTORU
# =============================================================================

class MuhasebeHesapService:
    
    @staticmethod
    def hedefli_bakiye_guncelle(firma_id: str, hesap_ids: list):
        """
        ✨ YENİ: Performans canavarı! 
        Bütün hesap planını değil, sadece işlem gören hesapların bakiyesini anında günceller.
        """
        if not hesap_ids: return
        
        tenant_db = get_tenant_db()
        benzersiz_hesaplar = set([h for h in hesap_ids if h])
        
        for h_id in benzersiz_hesaplar:
            ozet = tenant_db.query(
                func.sum(MuhasebeFisiDetay.borc),
                func.sum(MuhasebeFisiDetay.alacak)
            ).join(MuhasebeFisi).filter(
                MuhasebeFisiDetay.hesap_id == str(h_id),
                MuhasebeFisi.firma_id == firma_id
            ).first()
            
            hesap = tenant_db.get(HesapPlani, str(h_id))
            if hesap:
                hesap.borc_bakiye = ozet[0] or Decimal('0.00')
                hesap.alacak_bakiye = ozet[1] or Decimal('0.00')
                
        tenant_db.flush()

def bakiye_guncelle(firma_id):
    """(Geriye Dönük Uyumluluk İçin) Tüm bakiyeleri yeniden hesaplar"""
    tenant_db = get_tenant_db()
    hesaplar = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id).all()
    MuhasebeHesapService.hedefli_bakiye_guncelle(firma_id, [h.id for h in hesaplar])
    tenant_db.commit()

def fis_kaydet(data, kullanici_id, sube_id, donem_id, firma_id, fis_id=None):
    """Manuel Muhasebe Fişi Kaydı (Tenant DB)"""
    tenant_db = get_tenant_db()
    try:
        # ✨ KİLİT KONTROLÜ BURADA ÇALIŞACAK
        tarih_kilidi_kontrol(data.get('tarih') or datetime.now().date(), donem_id, tenant_db)
        
        try:
            if isinstance(data['tarih'], str):
                girilen_tarih = datetime.strptime(data['tarih'], '%Y-%m-%d').date()
            else:
                girilen_tarih = data['tarih']
        except ValueError:
            return False, "Geçersiz tarih formatı!"

        if fis_id:
            fis = tenant_db.get(MuhasebeFisi, fis_id)
            if not fis: return False, "Fiş bulunamadı."
            if fis.resmi_defter_basildi: return False, "Resmi deftere basılan fiş değiştirilemez!"
            fis.duzenleyen_id = kullanici_id
            fis.son_duzenleme_tarihi = datetime.now()
        else:
            fis = MuhasebeFisi(
                firma_id=firma_id, donem_id=donem_id, sube_id=sube_id,
                kaydeden_id=kullanici_id, sistem_kayit_tarihi=datetime.now()
            )
            tur_kod = data['fis_turu'].upper() if isinstance(data['fis_turu'], str) else 'GENEL'
            prefix_map = {'MAHSUP': 'M-', 'TAHSIL': 'T-', 'TEDIYE': 'TD-', 'ACILIS': 'A-', 'KAPANIS': 'K-'}
            on_ek = prefix_map.get(tur_kod, 'FIS-')
            fis.fis_no = numara_uret(firma_id, tur_kod, girilen_tarih.year, on_ek)
            tenant_db.add(fis)

        # Enum Safety
        if hasattr(MuhasebeFisTuru, str(data['fis_turu']).upper()):
            fis.fis_turu = data['fis_turu']
            
        fis.tarih = girilen_tarih
        fis.aciklama = data.get('aciklama')
        fis.e_defter_donemi = girilen_tarih.strftime('%Y%m')
        tenant_db.flush()

        eski_hesap_ids = []
        if fis_id:
            eski_detaylar = tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=fis.id).all()
            eski_hesap_ids = [d.hesap_id for d in eski_detaylar]
            tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=fis.id).delete()

        hesap_ids = data.get('detaylar_hesap_id', [])
        aciklamalar = data.get('detaylar_aciklama', [])
        borclar = data.get('detaylar_borc', [])
        alacaklar = data.get('detaylar_alacak', [])
        
        belge_tarihleri = data.get('detaylar_belge_tarihi', [])
        belge_nolar = data.get('detaylar_belge_no', [])
        belge_turleri = data.get('detaylar_belge_turu', [])
        odeme_yontemleri = data.get('detaylar_odeme_yontemi', [])
        belge_aciklamalari = data.get('detaylar_belge_aciklamasi', [])

        toplam_borc = Decimal('0.00')
        toplam_alacak = Decimal('0.00')
        aktif_hesap_ids = []

        for i in range(len(hesap_ids)):
            if not hesap_ids[i]: continue
            b = Decimal(str(borclar[i]).replace('.', '').replace(',', '.') or '0')
            a = Decimal(str(alacaklar[i]).replace('.', '').replace(',', '.') or '0')
            if b == 0 and a == 0: continue

            toplam_borc += b
            toplam_alacak += a
            aktif_hesap_ids.append(hesap_ids[i])
            
            b_tarih = None
            if i < len(belge_tarihleri) and belge_tarihleri[i]:
                try: b_tarih = datetime.strptime(str(belge_tarihleri[i]), '%Y-%m-%d').date()
                except: pass

            detay = MuhasebeFisiDetay(
                fis_id=fis.id, hesap_id=hesap_ids[i],
                aciklama=aciklamalar[i] if i < len(aciklamalar) else '',
                borc=b, alacak=a,
                belge_tarihi=b_tarih,
                belge_no=belge_nolar[i] if i < len(belge_nolar) else None,
                belge_turu=belge_turleri[i] if i < len(belge_turleri) else None,
                odeme_yontemi=odeme_yontemleri[i] if i < len(odeme_yontemleri) else None,
                belge_aciklamasi=belge_aciklamalari[i] if i < len(belge_aciklamalari) else None
            )
            tenant_db.add(detay)

        if abs(toplam_borc - toplam_alacak) > Decimal('0.05'):
            tenant_db.rollback()
            return False, f"Fiş dengesiz! Borç: {toplam_borc}, Alacak: {toplam_alacak}"

        fis.toplam_borc = toplam_borc
        fis.toplam_alacak = toplam_alacak
        tenant_db.flush()
        
        # ✨ Yalnızca etkilenen hesapların bakiyesini güncelle
        MuhasebeHesapService.hedefli_bakiye_guncelle(firma_id, eski_hesap_ids + aktif_hesap_ids)
        
        tenant_db.commit()
        return True, "Fiş başarıyla kaydedildi."

    except Exception as e:
        tenant_db.rollback()
        return False, f"Sistem Hatası: {str(e)}"

def resmi_defteri_kesinlestir(firma_id, donem_id, bitis_tarihi):
    """Resmi Defter Numaralandırma (Tenant DB)"""
    tenant_db = get_tenant_db()
    try:
        tarih_siniri = datetime.strptime(bitis_tarihi, '%Y-%m-%d').date()
        fisler = tenant_db.query(MuhasebeFisi).filter(
            MuhasebeFisi.firma_id == firma_id, MuhasebeFisi.donem_id == donem_id,
            MuhasebeFisi.tarih <= tarih_siniri, MuhasebeFisi.resmi_defter_basildi == False
        ).order_by(MuhasebeFisi.tarih, MuhasebeFisi.id).all()
        
        if not fisler: return False, "Bu tarihe kadar kesinleştirilecek fiş bulunamadı."

        son_yevmiye = tenant_db.query(func.max(MuhasebeFisi.yevmiye_madde_no)).filter_by(
            firma_id=firma_id, donem_id=donem_id
        ).scalar() or 0
        yevmiye_sayac = son_yevmiye + 1
        
        for fis in fisler:
            fis.yevmiye_madde_no = yevmiye_sayac
            fis.resmi_defter_basildi = True
            yevmiye_sayac += 1
            
        tenant_db.commit()
        return True, f"{len(fisler)} adet fiş kesinleştirildi.Son Yevmiye No: {yevmiye_sayac - 1}"
    except Exception as e:
        tenant_db.rollback()
        return False, f"Hata: {str(e)}"


# =============================================================================
# 2.OTOMATİK ENTEGRASYON SINIFI (Tenant DB Uyumlu + Gelişmiş Loglama)
# =============================================================================

class MuhasebeEntegrasyonService:

    @staticmethod
    def register_handlers():
        """
        Sinyal handler'ları. Çift kayıt (Double-Entry) riskine karşı
        doğrudan DB işlemi yapmazlar, sadece Audit/Log amaçlı dinlerler.
        Ana modüller entegre_et_XXX metotlarını senkron çağırır.
        """
        from app.signals import fatura_olusturuldu, siparis_faturalandi
        logger.info("📡 Muhasebe Sinyalleri (Audit Mode) dinlemeye başlandı...")
        
        @fatura_olusturuldu.connect_via(None)
        def on_fatura_olusturuldu(sender, **extra):
            logger.info(f"🔔 SİNYAL: {sender.belge_no} nolu fatura muhasebe motoruna ulaştı.")
            
        @siparis_faturalandi.connect_via(None)
        def on_siparis_faturalandi(sender, fatura, **extra):
            logger.info(f"🔔 SİNYAL: Sipariş faturalandı. Fatura ID: {fatura.id}")

    @staticmethod
    def _hesap_bul(firma_id, ozel_kod=None, cari_id=None, banka_id=None, kasa_id=None):
        tenant_db = get_tenant_db()
        if cari_id:
            cari = tenant_db.get(CariHesap, str(cari_id))
            return str(cari.satis_muhasebe_hesap_id) if cari and cari.satis_muhasebe_hesap_id else (str(cari.alis_muhasebe_hesap_id) if cari else None)
        if banka_id:
            bnk = tenant_db.get(BankaHesap, str(banka_id)) 
            return str(bnk.muhasebe_hesap_id) if bnk and bnk.muhasebe_hesap_id else None
        if kasa_id:
            ksa = tenant_db.get(Kasa, str(kasa_id))
            return str(ksa.muhasebe_hesap_id) if ksa and ksa.muhasebe_hesap_id else None
        if ozel_kod:
            hesap = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id, kod=ozel_kod).first()
            return str(hesap.id) if hesap else None
        return None

    @staticmethod
    def _fis_kaydet_generic(firma_id, donem_id, sube_id, tarih, aciklama, tur, satirlar, kaynak_modul, kaynak_id, belge_no_override=None):
        tenant_db = get_tenant_db()
        
        # ✨ OTOMATİK ENTEGRASYON KİLİDİ
        tarih_kilidi_kontrol(tarih, donem_id, tenant_db)
        
        prefix = "M-"
        if tur == MuhasebeFisTuru.TAHSIL: prefix = "T-"
        elif tur == MuhasebeFisTuru.TEDIYE: prefix = "TD-"
        
        if belge_no_override: fis_no = f"ENT-{belge_no_override}"
        else: fis_no = f"{prefix}{int(datetime.now().timestamp())}"

        fis = MuhasebeFisi(
            firma_id=firma_id, donem_id=donem_id, sube_id=sube_id,
            fis_turu=tur, fis_no=fis_no, tarih=tarih, aciklama=aciklama,
            kaynak_modul=kaynak_modul, kaynak_id=kaynak_id,
            e_defter_donemi=tarih.strftime('%Y%m'),
            kaydeden_id=current_user.id if current_user and hasattr(current_user, 'id') else None
        )
        tenant_db.add(fis)
        tenant_db.flush()

        toplam_borc = Decimal('0.00')
        toplam_alacak = Decimal('0.00')
        kullanilan_hesap_ids = []

        for s in satirlar:
            if not s.get('hesap_id'): continue
            borc = Decimal(str(s.get('borc', 0)))
            alacak = Decimal(str(s.get('alacak', 0)))
            if borc == 0 and alacak == 0: continue

            detay = MuhasebeFisiDetay(
                fis_id=fis.id, hesap_id=s['hesap_id'],
                aciklama=s.get('aciklama', aciklama),
                borc=borc, alacak=alacak,
                belge_turu=s.get('belge_turu')
            )
            tenant_db.add(detay)
            toplam_borc += borc
            toplam_alacak += alacak
            kullanilan_hesap_ids.append(s['hesap_id'])

        fis.toplam_borc = toplam_borc
        fis.toplam_alacak = toplam_alacak
        tenant_db.flush()
        
        # ✨ Otomatik fişlerde de hesap bakiyelerini güncelliyoruz
        MuhasebeHesapService.hedefli_bakiye_guncelle(firma_id, kullanilan_hesap_ids)
        
        return fis

    # --- MODÜL ENTEGRASYONLARI ---

    @staticmethod
    def entegre_et_fatura(fatura_id):
        tenant_db = get_tenant_db()
        fatura = tenant_db.get(Fatura, str(fatura_id))
        if not fatura: 
            return False, "Fatura bulunamadı."
        
        # Eski fişi sil
        if fatura.muhasebe_fis_id:
            old = tenant_db.get(MuhasebeFisi, str(fatura.muhasebe_fis_id))
            if old: 
                if old.resmi_defter_basildi: 
                    return False, "Resmi defter basılmış!"
                
                fatura.muhasebe_fis_id = None
                tenant_db.flush()
                
                eski_hesap_ids = [d.hesap_id for d in tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).all()]
                tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).delete()
                tenant_db.delete(old)
                tenant_db.flush()
                MuhasebeHesapService.hedefli_bakiye_guncelle(fatura.firma_id, eski_hesap_ids)

        satirlar = []
        
        # ✨ TİP GÜVENLİ (Safe) ENUM KONTROLÜ
        fatura_turu_str = str(fatura.fatura_turu.value).lower() if hasattr(fatura.fatura_turu, 'value') else str(fatura.fatura_turu).lower()
        is_satis = 'satis' in fatura_turu_str and 'iade' not in fatura_turu_str
        
        # 1.CARİ HESAP
        cari_hesap_id = MuhasebeEntegrasyonService._hesap_bul(fatura.firma_id, cari_id=fatura.cari_id)
        if not cari_hesap_id:
            return False, "Cari muhasebe hesabı eksik."

        if is_satis:
            satirlar.append({'hesap_id': cari_hesap_id, 'borc': fatura.genel_toplam, 'alacak': 0, 'aciklama': f"Fatura: {fatura.belge_no}"})
        else: # Alış
            satirlar.append({'hesap_id': cari_hesap_id, 'borc': 0, 'alacak': fatura.genel_toplam, 'aciklama': f"Fatura: {fatura.belge_no}"})

        # 2.STOK VE KDV
        hesap_toplamlari = {}
        
        for kalem in fatura.kalemler:
            stok = tenant_db.get(StokKart, str(kalem.stok_id))
            if not stok or not stok.muhasebe_grubu: 
                return False, f"Stok muhasebe grubu eksik: {stok.ad if stok else 'Bilinmiyor'}"
            
            tutar_kdv = kalem.kdv_tutari or Decimal('0.00')  
            matrah = kalem.satir_toplami - tutar_kdv
            
            # A) Mal Bedeli Hesabı
            hesap_id = stok.muhasebe_grubu.satis_hesap_id if is_satis else stok.muhasebe_grubu.alis_hesap_id
            if not hesap_id:
                return False, "Satış/Alış ana hesabı tanımlı değil."
            
            hesap_toplamlari[hesap_id] = hesap_toplamlari.get(hesap_id, Decimal('0.00')) + matrah

            # B) KDV Hesabı
            if stok.kdv_grubu:
                kdv_hesap_id = stok.kdv_grubu.satis_kdv_hesap_id if is_satis else stok.kdv_grubu.alis_kdv_hesap_id
                
                if not kdv_hesap_id and tutar_kdv > 0:
                    return False, "KDV ana hesabı tanımlı değil."
                    
                if kdv_hesap_id: 
                    hesap_toplamlari[kdv_hesap_id] = hesap_toplamlari.get(kdv_hesap_id, Decimal('0.00')) + tutar_kdv

        for h_id, tutar in hesap_toplamlari.items():
            if tutar == 0: continue
            
            if is_satis:
                satirlar.append({'hesap_id': str(h_id), 'borc': 0, 'alacak': tutar, 'aciklama': f'Mal Satışı / {fatura.belge_no}'})
            else:
                satirlar.append({'hesap_id': str(h_id), 'borc': tutar, 'alacak': 0, 'aciklama': f'Mal Alışı / {fatura.belge_no}'})

        fis = MuhasebeEntegrasyonService._fis_kaydet_generic(
            fatura.firma_id, fatura.donem_id, fatura.sube_id, fatura.tarih,
            f"Fatura: {fatura.belge_no}", MuhasebeFisTuru.MAHSUP, satirlar, 'fatura', str(fatura.id),
            belge_no_override=f"FAT-{fatura.belge_no}"
        )
        fatura.muhasebe_fis_id = str(fis.id)
        tenant_db.commit()
        
        return True, "Fatura muhasebeleştirildi."

    @staticmethod
    def entegre_et_kasa(hareket_id):
        tenant_db = get_tenant_db()
        hareket = tenant_db.get(KasaHareket, str(hareket_id))
        if not hareket: return False, "Hareket bulunamadı"
        
        if hareket.muhasebe_fisi_id:
            old = tenant_db.get(MuhasebeFisi, str(hareket.muhasebe_fisi_id))
            if old: 
                if old.resmi_defter_basildi: 
                    return False, "Resmi defter basılmış!"
                hareket.muhasebe_fisi_id = None
                tenant_db.flush()
                eski_hesap_ids = [d.hesap_id for d in tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).all()]
                tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=str(old.id)).delete()
                tenant_db.delete(old)
                tenant_db.flush()
                MuhasebeHesapService.hedefli_bakiye_guncelle(hareket.firma_id, eski_hesap_ids)

        ana_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, kasa_id=hareket.kasa_id)
        if not ana_hesap: return False, "Kasa muhasebe hesabı tanımlı değil."

        # Enum Safety
        tur_val = str(hareket.islem_turu.value).lower() if hasattr(hareket.islem_turu, 'value') else str(hareket.islem_turu).lower()
        is_giris = 'tahsilat' in tur_val or 'giris' in tur_val

        karsi_hesap = None
        if hareket.cari_id:
            karsi_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, cari_id=hareket.cari_id)
        elif getattr(hareket, 'banka_id', None): 
            karsi_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, banka_id=hareket.banka_id)
        elif getattr(hareket, 'karsi_kasa_id', None): 
            karsi_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, kasa_id=hareket.karsi_kasa_id)
        else:
            return False, "Karşı hesap (Cari/Banka/Kasa) belirlenemedi."
        
        if not karsi_hesap: return False, "Karşı muhasebe hesabı tanımlı değil."
        
        satirlar = [
            {'hesap_id': str(ana_hesap), 'borc': hareket.tutar if is_giris else 0, 'alacak': hareket.tutar if not is_giris else 0, 'aciklama': f"Kasa: {hareket.aciklama}"},
            {'hesap_id': str(karsi_hesap), 'borc': hareket.tutar if not is_giris else 0, 'alacak': hareket.tutar if is_giris else 0, 'aciklama': f"Karşı Hesap: {hareket.aciklama}"}
        ]

        donem_id = getattr(hareket, 'donem_id', None) or session.get('aktif_donem_id') or '1'
        sube_id = getattr(hareket.kasa, 'sube_id', None) or session.get('aktif_sube_id') or '1'

        fis = MuhasebeEntegrasyonService._fis_kaydet_generic(
            hareket.firma_id, donem_id, sube_id, hareket.tarih,
            f"Kasa İşlemi: {hareket.belge_no}", MuhasebeFisTuru.TAHSIL if is_giris else MuhasebeFisTuru.TEDIYE,
            satirlar, 'kasa', str(hareket.id), belge_no_override=f"KAS-{str(hareket.id)[:8]}"
        )
        hareket.muhasebe_fisi_id = str(fis.id)
        tenant_db.commit()
        return True, "Kasa işlemi muhasebeleştirildi."

    @staticmethod
    def entegre_et_banka(hareket_id):
        tenant_db = get_tenant_db()
        hareket = tenant_db.get(BankaHareket, str(hareket_id))
        if not hareket: return False, "Banka Hareketi bulunamadı"
        
        if hareket.muhasebe_fisi_id:
            old = tenant_db.get(MuhasebeFisi, str(hareket.muhasebe_fisi_id))
            if old: 
                if old.resmi_defter_basildi: 
                    return False, "Resmi defter basılmış!"
                hareket.muhasebe_fisi_id = None
                tenant_db.flush()
                eski_hesap_ids = [d.hesap_id for d in tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).all()]
                tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=str(old.id)).delete()
                tenant_db.delete(old)
                tenant_db.flush()
                MuhasebeHesapService.hedefli_bakiye_guncelle(hareket.firma_id, eski_hesap_ids)

        ana_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, banka_id=hareket.banka_id)
        if not ana_hesap: return False, "Banka muhase hesabı tanımlı değil."

        # Enum Safety
        tur_val = str(hareket.islem_turu.value).lower() if hasattr(hareket.islem_turu, 'value') else str(hareket.islem_turu).lower()
        is_giris = 'tahsilat' in tur_val or 'giris' in tur_val

        karsi_hesap = None
        if hareket.cari_id:
            karsi_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, cari_id=hareket.cari_id)
        elif getattr(hareket, 'kasa_id', None): 
            karsi_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, kasa_id=hareket.kasa_id)
        elif getattr(hareket, 'karsi_banka_id', None): 
            karsi_hesap = MuhasebeEntegrasyonService._hesap_bul(hareket.firma_id, banka_id=hareket.karsi_banka_id)
        else:
            return False, "Karşı hesap (Cari/Kasa/Banka) belirlenemedi."
            
        if not karsi_hesap: return False, "Karşı muhasebe hesabı tanımlı değil."

        alacak_tutar = getattr(hareket, 'brut_tutar', hareket.tutar) if (getattr(hareket, 'brut_tutar', 0) and getattr(hareket, 'brut_tutar', 0) > 0) else hareket.tutar

        satirlar = [
            {'hesap_id': str(ana_hesap), 'borc': hareket.tutar if is_giris else 0, 'alacak': hareket.tutar if not is_giris else 0, 'aciklama': f"Banka: {hareket.aciklama}"},
            {'hesap_id': str(karsi_hesap), 'borc': alacak_tutar if not is_giris else 0, 'alacak': alacak_tutar if is_giris else 0, 'aciklama': f"İşlem: {hareket.aciklama}"}
        ]
        
        komisyon_tutari = getattr(hareket, 'komisyon_tutari', 0)
        komisyon_hesap_id = getattr(hareket, 'komisyon_hesap_id', None)
        
        if is_giris and komisyon_tutari > 0 and komisyon_hesap_id:
            satirlar.append({'hesap_id': str(komisyon_hesap_id), 'borc': komisyon_tutari, 'alacak': 0, 'aciklama': 'Komisyon'})

        donem_id = getattr(hareket, 'donem_id', None) or session.get('aktif_donem_id') or '1'
        sube_id = getattr(hareket.banka, 'sube_id', None) or session.get('aktif_sube_id') or '1'

        fis = MuhasebeEntegrasyonService._fis_kaydet_generic(
            hareket.firma_id, donem_id, sube_id, hareket.tarih,
            f"Banka İşlemi: {hareket.belge_no}", MuhasebeFisTuru.MAHSUP, satirlar, 'banka', str(hareket.id), belge_no_override=f"BNK-{str(hareket.id)[:8]}"
        )
        hareket.muhasebe_fisi_id = str(fis.id)
        tenant_db.commit()
        return True, "Banka işlemi muhasebeleştirildi."

    @staticmethod
    def entegre_et_cek(cek_id, islem_tipi, hedef_id=None):
        tenant_db = get_tenant_db()
        from app.modules.cek.models import CekSenet 
        cek = tenant_db.get(CekSenet, str(cek_id))
        if not cek: return False, "Çek bulunamadı."

        h_portfoy = MuhasebeEntegrasyonService._hesap_bul(cek.firma_id, ozel_kod='101.01')
        if not h_portfoy: return False, "101.01 Çek Portföy hesabı bulunamadı."
        
        h_cari = MuhasebeEntegrasyonService._hesap_bul(cek.firma_id, cari_id=cek.cari_id)
        if not h_cari: return False, "Cari muhasebe hesabı tanımlı değil."

        satirlar = []
        aciklama = f"Çek: {cek.cek_no}"

        if islem_tipi == 'giris':
            satirlar.append({'hesap_id': h_portfoy, 'borc': cek.tutar, 'alacak': 0, 'aciklama': aciklama})
            satirlar.append({'hesap_id': h_cari, 'borc': 0, 'alacak': cek.tutar, 'aciklama': aciklama})
        elif islem_tipi == 'ciro':
            h_satici = MuhasebeEntegrasyonService._hesap_bul(cek.firma_id, cari_id=hedef_id)
            if not h_satici: return False, "Hedef cari muhasebe hesabı tanımlı değil."
            
            satirlar.append({'hesap_id': h_satici, 'borc': cek.tutar, 'alacak': 0, 'aciklama': f"Ciro: {aciklama}"})
            satirlar.append({'hesap_id': h_portfoy, 'borc': 0, 'alacak': cek.tutar, 'aciklama': f"Ciro: {aciklama}"})
        elif islem_tipi == 'tahsil':
            kasa_banka_kod = '100.01' if 'kasa' in str(cek.cek_durumu).lower() else '102.01'
            h_kasa_banka = MuhasebeEntegrasyonService._hesap_bul(cek.firma_id, ozel_kod=kasa_banka_kod)
            if not h_kasa_banka: return False, f"{kasa_banka_kod} hesabı bulunamadı."
            
            satirlar.append({'hesap_id': h_kasa_banka, 'borc': cek.tutar, 'alacak': 0, 'aciklama': f"Tahsil: {aciklama}"})
            satirlar.append({'hesap_id': h_portfoy, 'borc': 0, 'alacak': cek.tutar, 'aciklama': f"Tahsil: {aciklama}"})

        donem_id = getattr(cek, 'donem_id', None) or session.get('aktif_donem_id') or '1'
        sube_id = getattr(cek, 'sube_id', None) or session.get('aktif_sube_id') or '1'

        MuhasebeEntegrasyonService._fis_kaydet_generic(
            cek.firma_id, donem_id, sube_id, datetime.now().date(),
            aciklama, MuhasebeFisTuru.MAHSUP, satirlar, 'cek', str(cek.id), belge_no_override=f"CEK-{str(cek.id)[:8]}"
        )
        tenant_db.commit()
        return True, "Çek işlemi muhasebeleştirildi."