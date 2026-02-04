# app/modules/muhasebe/services.py

from decimal import Decimal
from datetime import datetime
from sqlalchemy import func, case, cast, Integer, literal
from flask_login import current_user
from app.araclar import numara_uret

# Modeller
from app.extensions import get_tenant_db # GOLDEN RULE
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
from signals import fatura_olusturuldu, siparis_faturalandi

# =============================================================================
# 1.MANUEL İŞLEMLER
# =============================================================================

def bakiye_guncelle(firma_id):
    """Tüm hesap planını tarar ve bakiyeleri yeniden hesaplar (Tenant DB)."""
    tenant_db = get_tenant_db()
    hesaplar = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id).all()
    for h in hesaplar:
        ozet = tenant_db.query(
            func.sum(MuhasebeFisiDetay.borc),
            func.sum(MuhasebeFisiDetay.alacak)
        ).join(MuhasebeFisi).filter(
            MuhasebeFisiDetay.hesap_id == h.id,
            MuhasebeFisi.firma_id == firma_id
        ).first()
        h.borc_bakiye = ozet[0] or Decimal(0)
        h.alacak_bakiye = ozet[1] or Decimal(0)
        # tenant_db.add(h) demeye gerek yok, session track ediyor.
    tenant_db.flush()

def fis_kaydet(data, kullanici_id, sube_id, donem_id, firma_id, fis_id=None):
    """Manuel Muhasebe Fişi Kaydı (Tenant DB)"""
    tenant_db = get_tenant_db()
    try:
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

        fis.fis_turu = data['fis_turu']
        fis.tarih = girilen_tarih
        fis.aciklama = data.get('aciklama')
        fis.e_defter_donemi = girilen_tarih.strftime('%Y%m')
        tenant_db.flush()

        if fis_id:
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

        toplam_borc = Decimal(0)
        toplam_alacak = Decimal(0)

        for i in range(len(hesap_ids)):
            if not hesap_ids[i]: continue
            b = Decimal(str(borclar[i]).replace('.', '').replace(',', '.') or '0')
            a = Decimal(str(alacaklar[i]).replace('.', '').replace(',', '.') or '0')
            if b == 0 and a == 0: continue

            toplam_borc += b
            toplam_alacak += a
            
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
        tenant_db.commit()
        bakiye_guncelle(firma_id)
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
# 2.OTOMATİK ENTEGRASYON SINIFI (Tenant DB Uyumlu)
# =============================================================================

class MuhasebeEntegrasyonService:

    @staticmethod
    def register_handlers():
        """Signal handler'larını kaydeder"""
        
        @fatura_olusturuldu.connect_via(None)
        def on_fatura_olusturuldu(sender, fatura, user, **extra):
            try:
                # Fatura ve User zaten Tenant Context'inde
                MuhasebeEntegrasyonService.entegre_et_fatura(fatura.id)
            except Exception as e:
                # Loglama buraya
                print(f"Muhasebe kaydı hatası: {e}")
        
        @siparis_faturalandi.connect_via(None)
        def on_siparis_faturalandi(sender, siparis, olusan_fatura_id, **extra):
            try:
                MuhasebeEntegrasyonService.entegre_et_fatura(olusan_fatura_id)
            except Exception as e: 
                print(f"Sipariş->Fatura muhasebe kaydı hatası:  {e}")

    @staticmethod
    def _hesap_bul(firma_id, ozel_kod=None, cari_id=None, banka_id=None, kasa_id=None):
        tenant_db = get_tenant_db()
        if cari_id:
            cari = tenant_db.get(CariHesap, cari_id)
            return cari.satis_muhasebe_hesap_id or cari.alis_muhasebe_hesap_id if cari else None
        if banka_id:
            bnk = tenant_db.get(BankaHesap, banka_id) # Model importu eksikse eklenmeli
            return bnk.muhasebe_hesap_id if bnk else None
        if kasa_id:
            ksa = tenant_db.get(Kasa, kasa_id)
            return ksa.muhasebe_hesap_id if ksa else None
        if ozel_kod:
            hesap = tenant_db.query(HesapPlani).filter_by(firma_id=firma_id, kod=ozel_kod).first()
            return hesap.id if hesap else None
        return None

    @staticmethod
    def _fis_kaydet_generic(firma_id, donem_id, sube_id, tarih, aciklama, tur, satirlar, kaynak_modul, kaynak_id, belge_no_override=None):
        tenant_db = get_tenant_db()
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
            kaydeden_id=current_user.id if current_user else None
        )
        tenant_db.add(fis)
        tenant_db.flush()

        toplam_borc = Decimal(0)
        toplam_alacak = Decimal(0)

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

        fis.toplam_borc = toplam_borc
        fis.toplam_alacak = toplam_alacak
        # Commit çağıran metoda bırakılabilir veya burada yapılabilir.
        # Genelde transaction bütünlüğü için çağıran yer yapar ama bu atomik bir işlem.
        tenant_db.commit() 
        return fis

    # --- MODÜL ENTEGRASYONLARI ---

    @staticmethod
    def entegre_et_fatura(fatura_id):
        tenant_db = get_tenant_db()
        fatura = tenant_db.get(Fatura, fatura_id)
        if not fatura: return False
        
        # Eski fişi sil
        if fatura.muhasebe_fis_id:
            old = tenant_db.get(MuhasebeFisi, fatura.muhasebe_fis_id)
            if old: 
                if old.resmi_defter_basildi: return False, "Resmi defter basılmış!"
                
                fatura.muhasebe_fis_id = None
                tenant_db.flush()

                tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).delete()
                tenant_db.delete(old)

        satirlar = []
        
        # 1.CARİ HESAP
        cari_hesap_id = None
        # İlişki lazy loading ise tenant_db session içinde erişilebilir
        if fatura.fatura_turu == 'satis':
            cari_hesap_id = fatura.cari.satis_muhasebe_hesap_id or fatura.cari.alis_muhasebe_hesap_id
            satirlar.append({'hesap_id': cari_hesap_id, 'borc': fatura.genel_toplam, 'alacak': 0, 'aciklama': f"Fatura: {fatura.belge_no}"})
        else: # Alış
            cari_hesap_id = fatura.cari.alis_muhasebe_hesap_id or fatura.cari.satis_muhasebe_hesap_id
            satirlar.append({'hesap_id': cari_hesap_id, 'borc': 0, 'alacak': fatura.genel_toplam, 'aciklama': f"Fatura: {fatura.belge_no}"})

        # 2.STOK VE KDV
        hesap_toplamlari = {}
        
        for kalem in fatura.kalemler:
            stok = tenant_db.get(StokKart, kalem.stok_id)
            if not stok or not stok.muhasebe_grubu: continue 
            
            tutar_kdv = kalem.kdv_tutari or 0  
            matrah = kalem.satir_toplami - tutar_kdv
            
            # A) Mal Bedeli Hesabı
            hesap_id = stok.muhasebe_grubu.satis_hesap_id if fatura.fatura_turu == 'satis' else stok.muhasebe_grubu.alis_hesap_id
            if hesap_id: 
                hesap_toplamlari[hesap_id] = hesap_toplamlari.get(hesap_id, 0) + matrah

            # B) KDV Hesabı
            if stok.kdv_grubu:
                kdv_hesap_id = stok.kdv_grubu.satis_kdv_hesap_id if fatura.fatura_turu == 'satis' else stok.kdv_grubu.alis_kdv_hesap_id
                
                if kdv_hesap_id: 
                    hesap_toplamlari[kdv_hesap_id] = hesap_toplamlari.get(kdv_hesap_id, 0) + tutar_kdv

        for h_id, tutar in hesap_toplamlari.items():
            if tutar == 0: continue
            
            if fatura.fatura_turu == 'satis':
                satirlar.append({'hesap_id': h_id, 'borc': 0, 'alacak': tutar, 'aciklama': f'Mal Satışı / {fatura.belge_no}'})
            else:
                satirlar.append({'hesap_id': h_id, 'borc': tutar, 'alacak': 0, 'aciklama': f'Mal Alışı / {fatura.belge_no}'})

        fis = MuhasebeEntegrasyonService._fis_kaydet_generic(
            fatura.firma_id, fatura.donem_id, fatura.sube_id, fatura.tarih,
            f"Fatura: {fatura.belge_no}", MuhasebeFisTuru.MAHSUP, satirlar, 'fatura', fatura.id,
            belge_no_override=f"FAT-{fatura.belge_no}"
        )
        fatura.muhasebe_fis_id = fis.id
        tenant_db.commit()
        
        return True, "Fatura muhasebeleştirildi."

    @staticmethod
    def entegre_et_kasa(hareket_id):
        tenant_db = get_tenant_db()
        hareket = tenant_db.get(KasaHareket, hareket_id)
        if not hareket: return False, "Hareket yok"
        
        if hareket.muhasebe_fisi_id:
            old = tenant_db.get(MuhasebeFisi, hareket.muhasebe_fisi_id)
            if old: 
                hareket.muhasebe_fisi_id = None
                tenant_db.flush()
                tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).delete()
                tenant_db.delete(old)

        ana_hesap = hareket.kasa.muhasebe_hesap_id
        if not ana_hesap: return False, "Hesaplar eksik"

        tur_val = str(hareket.islem_turu.value) if hasattr(hareket.islem_turu, 'value') else str(hareket.islem_turu)
        tahsilat_val = str(BankaIslemTuru.TAHSILAT.value)
        virman_giris_val = str(BankaIslemTuru.VIRMAN_GIRIS.value)

        karsi_hesap = None
        if hareket.cari:
            if tur_val == tahsilat_val:
                karsi_hesap = hareket.cari.satis_muhasebe_hesap_id or hareket.cari.alis_muhasebe_hesap_id
            else:
                karsi_hesap = hareket.cari.alis_muhasebe_hesap_id or hareket.cari.satis_muhasebe_hesap_id
        elif hareket.banka: 
            karsi_hesap = hareket.banka.muhasebe_hesap_id
        elif hareket.karsi_kasa: 
            karsi_hesap = hareket.karsi_kasa.muhasebe_hesap_id
        
        if not karsi_hesap: return False, "Karşı hesap eksik"

        is_giris = tur_val in [tahsilat_val, virman_giris_val]
        
        satirlar = [
            {'hesap_id': ana_hesap, 'borc': hareket.tutar if is_giris else 0, 'alacak': hareket.tutar if not is_giris else 0, 'aciklama': f"Kasa: {hareket.aciklama}"},
            {'hesap_id': karsi_hesap, 'borc': hareket.tutar if not is_giris else 0, 'alacak': hareket.tutar if is_giris else 0, 'aciklama': f"Karşı Hesap: {hareket.aciklama}"}
        ]

        fis = MuhasebeEntegrasyonService._fis_kaydet_generic(
            hareket.firma_id, hareket.donem_id, hareket.kasa.sube_id, hareket.tarih,
            f"Kasa İşlemi: {hareket.belge_no}", MuhasebeFisTuru.TAHSIL if is_giris else MuhasebeFisTuru.TEDIYE,
            satirlar, 'kasa', hareket.id, belge_no_override=f"KASA-{hareket.id}"
        )
        hareket.muhasebe_fisi_id = fis.id
        tenant_db.commit()
        return True, "Kasa muhasebeleştirildi."

    @staticmethod
    def entegre_et_banka(hareket_id):
        tenant_db = get_tenant_db()
        hareket = tenant_db.get(BankaHareket, hareket_id)
        if not hareket: return False, "Hareket yok"
        
        if hareket.muhasebe_fisi_id:
            old = tenant_db.get(MuhasebeFisi, hareket.muhasebe_fisi_id)
            if old: 
                hareket.muhasebe_fisi_id = None
                tenant_db.flush()
                tenant_db.query(MuhasebeFisiDetay).filter_by(fis_id=old.id).delete()
                tenant_db.delete(old)

        if not hareket.banka.muhasebe_hesap_id: return False, "Banka hesabı yok"

        tur_val = str(hareket.islem_turu.value) if hasattr(hareket.islem_turu, 'value') else str(hareket.islem_turu)
        tahsilat_val = str(BankaIslemTuru.TAHSILAT.value)
        virman_giris_val = str(BankaIslemTuru.VIRMAN_GIRIS.value)

        karsi_hesap = None
        if hareket.cari:
            if tur_val == tahsilat_val: # Giriş
                karsi_hesap = hareket.cari.satis_muhasebe_hesap_id or hareket.cari.alis_muhasebe_hesap_id
            else: # Çıkış
                karsi_hesap = hareket.cari.alis_muhasebe_hesap_id or hareket.cari.satis_muhasebe_hesap_id
        elif hareket.kasa: karsi_hesap = hareket.kasa.muhasebe_hesap_id
        elif hareket.karsi_banka: karsi_hesap = hareket.karsi_banka.muhasebe_hesap_id
        
        if not karsi_hesap: return False, "Karşı hesap yok"

        is_giris = tur_val in [tahsilat_val, virman_giris_val]
        alacak_tutar = hareket.brut_tutar if (hareket.brut_tutar and hareket.brut_tutar > 0) else hareket.tutar

        satirlar = [
            {'hesap_id': hareket.banka.muhasebe_hesap_id, 'borc': hareket.tutar if is_giris else 0, 'alacak': hareket.tutar if not is_giris else 0, 'aciklama': f"Banka: {hareket.aciklama}"},
            {'hesap_id': karsi_hesap, 'borc': alacak_tutar if not is_giris else 0, 'alacak': alacak_tutar if is_giris else 0, 'aciklama': f"İşlem: {hareket.aciklama}"}
        ]
        
        if is_giris and hareket.komisyon_tutari > 0 and hareket.komisyon_hesap_id:
            satirlar.append({'hesap_id': hareket.komisyon_hesap_id, 'borc': hareket.komisyon_tutari, 'alacak': 0, 'aciklama': 'Komisyon'})

        fis = MuhasebeEntegrasyonService._fis_kaydet_generic(
            hareket.firma_id, hareket.donem_id, hareket.banka.sube_id, hareket.tarih,
            f"Banka: {hareket.belge_no}", MuhasebeFisTuru.MAHSUP, satirlar, 'banka', hareket.id, belge_no_override=f"BNK-{hareket.id}"
        )
        hareket.muhasebe_fisi_id = fis.id
        tenant_db.commit()
        return True, "Banka muhasebeleştirildi."

    @staticmethod
    def entegre_et_cek(cek_id, islem_tipi, hedef_id=None):
        tenant_db = get_tenant_db()
        from modules.cek.models import CekSenet
        cek = tenant_db.get(CekSenet, cek_id)
        if not cek: return False

        h_portfoy = MuhasebeEntegrasyonService._hesap_bul(cek.firma_id, ozel_kod='101.01')
        
        h_cari = None
        if cek.portfoy_tipi == 'alinan': 
            h_cari = cek.cari.satis_muhasebe_hesap_id or cek.cari.alis_muhasebe_hesap_id
        else: 
            h_cari = cek.cari.alis_muhasebe_hesap_id or cek.cari.satis_muhasebe_hesap_id

        satirlar = []
        aciklama = f"Çek: {cek.cek_no}"

        if islem_tipi == 'giris':
            satirlar.append({'hesap_id': h_portfoy, 'borc': cek.tutar, 'alacak': 0, 'aciklama': aciklama})
            satirlar.append({'hesap_id': h_cari, 'borc': 0, 'alacak': cek.tutar, 'aciklama': aciklama})
        elif islem_tipi == 'ciro':
            hedef_cari = tenant_db.get(CariHesap, hedef_id)
            h_satici = hedef_cari.alis_muhasebe_hesap_id or hedef_cari.satis_muhasebe_hesap_id
            satirlar.append({'hesap_id': h_satici, 'borc': cek.tutar, 'alacak': 0, 'aciklama': f"Ciro: {aciklama}"})
            satirlar.append({'hesap_id': h_portfoy, 'borc': 0, 'alacak': cek.tutar, 'aciklama': f"Ciro: {aciklama}"})
        elif islem_tipi == 'tahsil':
            h_kasa_banka = MuhasebeEntegrasyonService._hesap_bul(cek.firma_id, ozel_kod='100.01' if 'kasa' in str(cek.cek_durumu) else '102.01')
            satirlar.append({'hesap_id': h_kasa_banka, 'borc': cek.tutar, 'alacak': 0, 'aciklama': f"Tahsil: {aciklama}"})
            satirlar.append({'hesap_id': h_portfoy, 'borc': 0, 'alacak': cek.tutar, 'aciklama': f"Tahsil: {aciklama}"})

        MuhasebeEntegrasyonService._fis_kaydet_generic(
            cek.firma_id, 1, 1, datetime.now().date(),
            aciklama, MuhasebeFisTuru.MAHSUP, satirlar, 'cek', cek.id
        )
        return True, "Çek muhasebeleştirildi."