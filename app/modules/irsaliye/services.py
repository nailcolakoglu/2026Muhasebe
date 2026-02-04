from app.extensions import db
from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi
from app.modules.stok.models import StokHareketi
from app.modules.firmalar.models import Donem
from app.enums import HareketTuru, IrsaliyeTuru, IrsaliyeDurumu
from datetime import datetime
from flask import session
from app.araclar import para_cevir

class IrsaliyeService:
    @staticmethod
    def kaydet(form_data, irsaliye=None, user=None):
        try:
            is_new = False
            if not irsaliye:
                irsaliye = Irsaliye()
                is_new = True
                # 1.Kritik Alanların Doldurulması
                irsaliye.firma_id = user.firma_id
                
                # Dönem Kontrolü
                if 'aktif_donem_id' in session:
                    irsaliye.donem_id = session['aktif_donem_id']
                else:
                    aktif_donem = Donem.query.filter_by(firma_id=user.firma_id, aktif=True).first()
                    irsaliye.donem_id = aktif_donem.id if aktif_donem else 1

            # 2.Başlık Verileri
            if form_data.get('tarih'):
                irsaliye.tarih = datetime.strptime(form_data.get('tarih'), '%Y-%m-%d').date()
            else:
                irsaliye.tarih = datetime.now().date()
            
            # Saat verisi (HTML time input 'HH:MM' döner)
            saat_str = form_data.get('saat', datetime.now().strftime('%H:%M'))
            try:
                irsaliye.saat = datetime.strptime(saat_str, '%H:%M').time()
            except:
                irsaliye.saat = datetime.now().time()
            
            irsaliye.belge_no = form_data.get('belge_no')
            irsaliye.cari_id = int(form_data.get('cari_id'))
            irsaliye.depo_id = int(form_data.get('depo_id'))
            irsaliye.aciklama = form_data.get('aciklama')
            
            # Lojistik Bilgileri
            irsaliye.plaka_arac = form_data.get('plaka_arac')
            irsaliye.sofor_ad = form_data.get('sofor_ad')
            irsaliye.sofor_soyad = form_data.get('sofor_soyad')
            irsaliye.sofor_tc = form_data.get('sofor_tc')

            # Varsayılanlar
            if not irsaliye.irsaliye_turu:
                irsaliye.irsaliye_turu = IrsaliyeTuru.SEVK.value
            
            if not irsaliye.durum:
                irsaliye.durum = IrsaliyeDurumu.ONAYLANDI.value # Doğrudan onaylı kaydediyoruz

            db.session.add(irsaliye)
            db.session.flush() # ID oluşsun

            # 3.Kalemler ve Stok Hareketi
            # Önce eski kalemleri temizle (Düzenleme modu için)
            IrsaliyeKalemi.query.filter_by(irsaliye_id=irsaliye.id).delete()
            
            # Stok hareketlerini de temizle ki çift kayıt olmasın
            StokHareketi.query.filter_by(kaynak_turu='irsaliye', kaynak_id=irsaliye.id).delete()

            # Formdan gelen listeleri işle
            stok_ids = form_data.getlist('kalemler_stok_id[]')
            miktarlar = form_data.getlist('kalemler_miktar[]')
            birimler = form_data.getlist('kalemler_birim[]')
            aciklamalar = form_data.getlist('kalemler_aciklama[]')

            for i in range(len(stok_ids)):
                if not stok_ids[i]: continue
                
                miktar = para_cevir(miktarlar[i])
                if miktar <= 0: continue

                kalem = IrsaliyeKalemi(irsaliye_id=irsaliye.id)
                kalem.stok_id = int(stok_ids[i])
                kalem.miktar = miktar
                kalem.birim = birimler[i] if i < len(birimler) else 'Adet'
                kalem.aciklama = aciklamalar[i] if i < len(aciklamalar) else ''
                
                db.session.add(kalem)

                # 4.STOK DÜŞÜŞÜ (Stok Hareketi Oluştur)
                # İrsaliye stoktan düşer (Satış İrsaliyesi ise)
                sh = StokHareketi()
                sh.firma_id = irsaliye.firma_id
                sh.donem_id = irsaliye.donem_id
                sh.sube_id = user.yetkili_subeler[0].id if user.yetkili_subeler else 1
                
                sh.cikis_depo_id = irsaliye.depo_id # Çıkış yapan depo
                sh.giris_depo_id = None
                
                sh.stok_id = kalem.stok_id
                sh.tarih = irsaliye.tarih
                sh.belge_no = irsaliye.belge_no
                
                sh.kaynak_turu = 'irsaliye'
                sh.kaynak_id = irsaliye.id
                sh.kaynak_belge_detay_id = kalem.id
                
                sh.hareket_turu = HareketTuru.SATIS_IRSALIYESI.value
                sh.miktar = kalem.miktar
                sh.aciklama = f"İrsaliye: {irsaliye.aciklama or ''}"
                
                db.session.add(sh)

            db.session.commit()
            return True, f"İrsaliye {irsaliye.belge_no} başarıyla kaydedildi."

        except Exception as e:
            db.session.rollback()
            raise e