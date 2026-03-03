# app/modules/siparis/services.py

import logging
import uuid
from decimal import Decimal
from datetime import datetime
from flask import current_app, session
from flask_login import current_user

from app.extensions import get_tenant_db # 🔥 SAAS MİMARİSİ
from app.modules.siparis.models import Siparis, SiparisDetay
from app.modules.sube.models import Sube
from app.modules.depo.models import Depo
from app.modules.firmalar.models import Donem
from app.araclar import para_cevir
from app.enums import SiparisDurumu

# ✨ SİNYALLER
from app.signals import siparis_sevk_edildi, siparis_olusturuldu

logger = logging.getLogger(__name__)

class SiparisService:
    @staticmethod
    def save(form_data, siparis=None):
        tenant_db = get_tenant_db()
        if not tenant_db: return False, "Veritabanı bağlantısı yok"

        try:
            # 1. VALIDASYON
            if not form_data.get('cari_id'):
                return False, "Lütfen bir müşteri (Cari) seçiniz."
            if not form_data.get('belge_no'):
                return False, "Belge numarası boş olamaz."
                
            is_new = False
            if not siparis:
                siparis = Siparis(firma_id=current_user.firma_id)
                siparis.plasiyer_id = str(current_user.id)
                is_new = True
            
            # --- BAŞLIK BİLGİLERİ ---
            if not siparis.sube_id:
                if hasattr(current_user, 'yetkili_subeler') and current_user.yetkili_subeler:
                    siparis.sube_id = str(current_user.yetkili_subeler[0].id)
                else:
                    ilk = tenant_db.query(Sube).filter_by(aktif=True).first()
                    siparis.sube_id = str(ilk.id) if ilk else None

            if not siparis.donem_id:
                ilk = tenant_db.query(Donem).filter_by(aktif=True).first()
                siparis.donem_id = str(ilk.id) if ilk else None
            
            # Tarih
            if isinstance(form_data.get('tarih'), str):
                siparis.tarih = datetime.strptime(form_data['tarih'], '%Y-%m-%d').date()
            else:
                siparis.tarih = form_data.get('tarih') or datetime.now().date()

            # Teslim Tarihi
            t_tarih = form_data.get('teslim_tarihi')
            if t_tarih:
                if isinstance(t_tarih, str):
                    siparis.teslim_tarihi = datetime.strptime(t_tarih, '%Y-%m-%d').date()
                else:
                    siparis.teslim_tarihi = t_tarih

            siparis.belge_no = form_data.get('belge_no')
            siparis.cari_id = str(form_data.get('cari_id')) # ✨ DÜZELTME: int() yerine str()
            
            depo_input = form_data.get('depo_id')
            if depo_input:
                siparis.depo_id = str(depo_input) # ✨ DÜZELTME: int() yerine str()
            else:
                varsayilan_depo = tenant_db.query(Depo).filter_by(aktif=True).first()
                siparis.depo_id = str(varsayilan_depo.id) if varsayilan_depo else None

            siparis.durum = form_data.get('durum') or SiparisDurumu.BEKLIYOR.value
            siparis.sevk_adresi = form_data.get('sevk_adresi')
            siparis.aciklama = form_data.get('aciklama')
            siparis.doviz_turu = form_data.get('doviz_turu', 'TL')
            siparis.doviz_kuru = para_cevir(form_data.get('doviz_kuru') or 1)
            
            f_id = form_data.get('fiyat_listesi_id')
            siparis.fiyat_listesi_id = str(f_id) if f_id and f_id != '0' else None
            
            op_id = form_data.get('odeme_plani_id')
            siparis.odeme_plani_id = str(op_id) if op_id and op_id != '0' else None

            if is_new:
                tenant_db.add(siparis)
            
            tenant_db.flush()

            # --- DETAYLAR ---
            mevcut_detaylar = {str(d.id): d for d in siparis.detaylar}
            islenen_detay_idleri = []

            ids = form_data.getlist('detaylar_id[]')
            stok_ids = form_data.getlist('detaylar_stok_id[]')
            miktarlar = form_data.getlist('detaylar_miktar[]')
            birimler = form_data.getlist('detaylar_birim[]')
            fiyatlar = form_data.getlist('detaylar_birim_fiyat[]')
            iskontolar = form_data.getlist('detaylar_iskonto_orani[]')
            kdvler = form_data.getlist('detaylar_kdv_orani[]')

            toplam_ara = Decimal('0.00')
            toplam_iskonto = Decimal('0.00')
            toplam_kdv = Decimal('0.00')
            genel_toplam = Decimal('0.00')

            for i in range(len(stok_ids)):
                if not stok_ids[i] or stok_ids[i] == '0': continue

                def get_val(lst, idx, default):
                    return lst[idx] if idx < len(lst) else default

                row_id = str(ids[i]) if i < len(ids) and ids[i] and ids[i] != '0' else None
                miktar = para_cevir(get_val(miktarlar, i, 0))
                fiyat = para_cevir(get_val(fiyatlar, i, 0))
                isk_orani = para_cevir(get_val(iskontolar, i, 0))
                kdv_orani = para_cevir(get_val(kdvler, i, 20))
                birim = get_val(birimler, i, 'Adet')

                brut_tutar = miktar * fiyat
                isk_tutari = brut_tutar * (isk_orani / Decimal('100'))
                net_tutar = brut_tutar - isk_tutari
                kdv_tutari = net_tutar * (kdv_orani / Decimal('100'))
                satir_toplami = net_tutar + kdv_tutari

                toplam_ara += net_tutar
                toplam_iskonto += isk_tutari
                toplam_kdv += kdv_tutari
                genel_toplam += satir_toplami

                detay = None
                if row_id and row_id in mevcut_detaylar:
                    detay = mevcut_detaylar[row_id]
                    islenen_detay_idleri.append(row_id)
                else:
                    detay = SiparisDetay(siparis_id=siparis.id)
                    tenant_db.add(detay)
                
                detay.stok_id = str(stok_ids[i]) # ✨ DÜZELTME: int() yerine str()
                detay.miktar = miktar
                detay.birim = birim
                detay.birim_fiyat = fiyat
                detay.iskonto_orani = isk_orani
                detay.kdv_orani = kdv_orani
                detay.iskonto_tutari = isk_tutari
                detay.kdv_tutari = kdv_tutari
                detay.net_tutar = net_tutar
                detay.satir_toplami = satir_toplami

            # Silinenleri Temizle
            for d_id, d_obj in mevcut_detaylar.items():
                if d_id not in islenen_detay_idleri:
                    tenant_db.delete(d_obj)

            # Başlık Güncelleme
            siparis.ara_toplam = toplam_ara
            siparis.iskonto_toplam = toplam_iskonto
            siparis.kdv_toplam = toplam_kdv
            siparis.genel_toplam = genel_toplam
            
            if siparis.doviz_kuru > 0:
                siparis.dovizli_toplam = genel_toplam / siparis.doviz_kuru

            tenant_db.flush() 
            
            # Eğer modelde bu metotlar tanımlıysa çağır
            if hasattr(siparis, 'guncelle_karlilik'):
                siparis.guncelle_karlilik()
            if hasattr(siparis, 'skor_hesapla'):
                siparis.skor_hesapla()

            tenant_db.commit()
            
            logger.info(f"✅ Sipariş kaydedildi: {siparis.belge_no}")
            
            # ✨ YENİ: Sinyali Ateşle (Sadece yeni siparişte)
            if is_new:
                siparis_olusturuldu.send(siparis)
                
            return True, f"Sipariş {siparis.belge_no} başarıyla kaydedildi."

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Sipariş Kayıt Hatası: {str(e)}", exc_info=True)
            return False, f"Sistem hatası: {str(e)}"

    @staticmethod
    def sevk_et(siparis, sevk_miktarlar, detay_ids):
        """Sevkiyat Mantığı (WMS/Stok Entegrasyonlu)"""
        tenant_db = get_tenant_db()
        try:
            izinli_durumlar = [SiparisDurumu.ONAYLANDI.value, SiparisDurumu.KISMI.value]
            # Enum kontrolü için value'yu garantile
            mevcut_durum = siparis.durum.value if hasattr(siparis.durum, 'value') else siparis.durum
            
            if mevcut_durum not in izinli_durumlar:
                return False, f"Sadece ONAYLI siparişler sevk edilebilir. Şu anki durum: {mevcut_durum}"

            sevk_verileri = []
            islem_yapildi = False
            siparis_bitti_mi = True 

            for i, miktar_str in enumerate(sevk_miktarlar):
                sevk_edilen = para_cevir(miktar_str)
                detay_id = str(detay_ids[i]) # UUID Güvenliği
                
                detay = tenant_db.get(SiparisDetay, detay_id)
                if not detay or detay.siparis_id != siparis.id: continue

                toplam_istenen = Decimal(str(detay.miktar))
                daha_once_giden = Decimal(str(detay.teslim_edilen_miktar or 0))
                kalan = toplam_istenen - daha_once_giden
                
                if sevk_edilen <= 0:
                    if kalan > Decimal('0.001'): siparis_bitti_mi = False
                    continue

                if sevk_edilen > (kalan + Decimal('0.001')): 
                    return False, f"Hata: '{detay.stok.ad}' için fazla çıkış ({sevk_edilen} > {kalan})!"

                detay.teslim_edilen_miktar = daha_once_giden + sevk_edilen
                
                sevk_verileri.append({
                    'detay_id': str(detay.id),
                    'miktar': float(sevk_edilen)
                })
                islem_yapildi = True
                
                if (toplam_istenen - (daha_once_giden + sevk_edilen)) > Decimal('0.001'):
                    siparis_bitti_mi = False
            
            if not islem_yapildi:
                return False, "Sevk edilecek geçerli bir miktar girilmedi."

            tenant_db.flush()

            if siparis_bitti_mi:
                siparis.durum = SiparisDurumu.TAMAMLANDI.value
                msg = "Sipariş tamamen sevk edildi."
            else:
                siparis.durum = SiparisDurumu.KISMI.value
                msg = "Kısmi sevkiyat yapıldı."

            # Stokların düşmesi için sinyal gönderilir
            siparis_sevk_edildi.send(
                current_app._get_current_object(),
                siparis=siparis,
                sevk_verileri=sevk_verileri,
                cikis_depo_id=str(siparis.depo_id)
            )

            tenant_db.commit()
            logger.info(f"🚚 Sipariş Sevk Edildi: {siparis.belge_no}")
            return True, msg

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Sipariş Sevk Hatası: {str(e)}", exc_info=True)
            return False, f"Sevk Hatası: {str(e)}"