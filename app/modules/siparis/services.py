# app/modules/siparis/services.py

from app.extensions import get_tenant_db # 👈 Firebird Bağlantısı
from app.modules.siparis.models import Siparis, SiparisDetay
from app.modules.sube.models import Sube
from app.modules.depo.models import Depo
from app.modules.firmalar.models import Donem
from flask_login import current_user
from datetime import datetime
from app.araclar import para_cevir
from app.signals import siparis_sevk_edildi, siparis_faturalandi
from flask import current_app
from app.enums import SiparisDurumu
from decimal import Decimal

class SiparisService:
    @staticmethod
    def save(form_data, siparis=None):
        tenant_db = get_tenant_db()
        if not tenant_db: return False, "Veritabanı bağlantısı yok"

        try:
            # 1.VALIDASYON
            if not form_data.get('cari_id'):
                return False, "Lütfen bir müşteri (Cari) seçiniz."
            if not form_data.get('belge_no'):
                return False, "Belge numarası boş olamaz."
                
            is_new = False
            if not siparis:
                siparis = Siparis(firma_id=1) # Tenant ID = 1
                siparis.plasiyer_id = current_user.id
                is_new = True
            
            # --- BAŞLIK BİLGİLERİ ---
            if not siparis.sube_id:
                # Kullanıcının yetkili olduğu ilk şube veya sistemdeki ilk şube
                if current_user.yetkili_subeler:
                    siparis.sube_id = current_user.yetkili_subeler[0].id
                else:
                    ilk = tenant_db.query(Sube).filter_by(firma_id=1).first()
                    siparis.sube_id = ilk.id if ilk else 1

            if not siparis.donem_id:
                ilk = tenant_db.query(Donem).filter_by(firma_id=1, aktif=True).first()
                siparis.donem_id = ilk.id if ilk else 1
            
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
            siparis.cari_id = int(form_data.get('cari_id'))
            
            depo_input = form_data.get('depo_id')
            if depo_input:
                siparis.depo_id = int(depo_input)
            else:
                varsayilan_depo = tenant_db.query(Depo).filter_by(firma_id=1).first()
                siparis.depo_id = varsayilan_depo.id if varsayilan_depo else 1

            siparis.durum = form_data.get('durum') or SiparisDurumu.BEKLIYOR.value
            siparis.sevk_adresi = form_data.get('sevk_adresi')
            siparis.aciklama = form_data.get('aciklama')
            siparis.doviz_turu = form_data.get('doviz_turu')
            siparis.doviz_kuru = para_cevir(form_data.get('doviz_kuru') or 1)
            
            f_id = form_data.get('fiyat_listesi_id')
            siparis.fiyat_listesi_id = int(f_id) if f_id and int(f_id) > 0 else None
            
            op_id = form_data.get('odeme_plani_id')
            siparis.odeme_plani_id = int(op_id) if op_id and int(op_id) > 0 else None

            if is_new:
                tenant_db.add(siparis)
            
            tenant_db.flush()

            # --- DETAYLAR ---
            mevcut_detaylar = {d.id: d for d in siparis.detaylar}
            islenen_detay_idleri = []

            ids = form_data.getlist('detaylar_id[]')
            stok_ids = form_data.getlist('detaylar_stok_id[]')
            miktarlar = form_data.getlist('detaylar_miktar[]')
            birimler = form_data.getlist('detaylar_birim[]')
            fiyatlar = form_data.getlist('detaylar_birim_fiyat[]')
            iskontolar = form_data.getlist('detaylar_iskonto_orani[]')
            kdvler = form_data.getlist('detaylar_kdv_orani[]')

            toplam_ara = 0
            toplam_iskonto = 0
            toplam_kdv = 0
            genel_toplam = 0

            for i in range(len(stok_ids)):
                if not stok_ids[i]: continue

                def get_val(lst, idx, default):
                    return lst[idx] if idx < len(lst) else default

                row_id = int(ids[i]) if i < len(ids) and ids[i] and ids[i] != '0' else 0
                miktar = para_cevir(get_val(miktarlar, i, 0))
                fiyat = para_cevir(get_val(fiyatlar, i, 0))
                isk_orani = para_cevir(get_val(iskontolar, i, 0))
                kdv_orani = para_cevir(get_val(kdvler, i, 20))
                birim = get_val(birimler, i, 'Adet')

                brut_tutar = miktar * fiyat
                isk_tutari = brut_tutar * (isk_orani / 100)
                net_tutar = brut_tutar - isk_tutari
                kdv_tutari = net_tutar * (kdv_orani / 100)
                satir_toplami = net_tutar + kdv_tutari

                toplam_ara += net_tutar
                toplam_iskonto += isk_tutari
                toplam_kdv += kdv_tutari
                genel_toplam += satir_toplami

                detay = None
                if row_id > 0 and row_id in mevcut_detaylar:
                    detay = mevcut_detaylar[row_id]
                    islenen_detay_idleri.append(row_id)
                else:
                    detay = SiparisDetay(siparis_id=siparis.id)
                    tenant_db.add(detay)
                
                detay.stok_id = int(stok_ids[i])
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
            siparis.guncelle_karlilik()
            siparis.skor_hesapla()

            tenant_db.commit()
            return True, f"Sipariş {siparis.belge_no} başarıyla kaydedildi."

        except Exception as e:
            tenant_db.rollback()
            print(f"Sipariş Kayıt Hatası: {str(e)}")
            raise e

    @staticmethod
    def sevk_et(siparis, sevk_miktarlar, detay_ids):
        """Sevkiyat Mantığı"""
        tenant_db = get_tenant_db()
        try:
            izinli_durumlar = [SiparisDurumu.ONAYLANDI.value, SiparisDurumu.KISMI.value]
            if siparis.durum not in izinli_durumlar:
                return False, f"Sadece ONAYLI siparişler sevk edilebilir. Şu anki durum: {siparis.durum}"

            sevk_verileri = []
            islem_yapildi = False
            siparis_bitti_mi = True 

            for i, miktar_str in enumerate(sevk_miktarlar):
                sevk_edilen = para_cevir(miktar_str)
                
                detay = tenant_db.query(SiparisDetay).get(detay_ids[i])
                if not detay or detay.siparis_id != siparis.id: continue

                toplam_istenen = detay.miktar
                daha_once_giden = detay.teslim_edilen_miktar
                kalan = toplam_istenen - daha_once_giden
                
                if sevk_edilen <= 0:
                    if kalan > 0.001: siparis_bitti_mi = False
                    continue

                if sevk_edilen > (kalan + Decimal('0.001')): 
                    return False, f"Hata: '{detay.stok.ad}' için fazla çıkış!"

                detay.teslim_edilen_miktar = daha_once_giden + sevk_edilen
                
                sevk_verileri.append({
                    'detay_id': detay.id,
                    'miktar': float(sevk_edilen)
                })
                islem_yapildi = True
                
                if (toplam_istenen - (daha_once_giden + sevk_edilen)) > 0.001:
                    siparis_bitti_mi = False
            
            if not islem_yapildi:
                return False, "Sevk edilecek miktar girilmedi."

            tenant_db.flush()

            if siparis_bitti_mi:
                siparis.durum = SiparisDurumu.TAMAMLANDI.value
                msg = "Sipariş tamamen sevk edildi."
            else:
                siparis.durum = SiparisDurumu.KISMI.value
                msg = "Kısmi sevkiyat yapıldı."

            siparis_sevk_edildi.send(
                current_app._get_current_object(),
                siparis=siparis,
                sevk_verileri=sevk_verileri,
                cikis_depo_id=siparis.depo_id
            )

            tenant_db.commit()
            return True, msg

        except Exception as e:
            tenant_db.rollback()
            raise e