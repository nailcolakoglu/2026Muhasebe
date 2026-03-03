# app/modules/irsaliye/services.py

import logging
import uuid
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from decimal import Decimal

from flask import session

from app.extensions import get_tenant_db # ✨ KESİN KURAL: Multi-tenant DB Session
from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi
from app.modules.stok.models import StokHareketi
from app.modules.firmalar.models import Donem
from app.modules.sube.models import Sube
from app.enums import HareketTuru, IrsaliyeTuru, IrsaliyeDurumu
from app.araclar import para_cevir

# Sinyalleri Dahil Ediyoruz
from app.signals import stok_hareket_olusturuldu

logger = logging.getLogger(__name__)

class IrsaliyeService:
    
    @staticmethod
    def kaydet(form_data: Dict[str, Any], irsaliye: Optional[Irsaliye] = None, user: Any = None) -> Tuple[bool, str]:
        tenant_db = get_tenant_db() 
        try:
            is_new = False
            if not irsaliye:
                is_new = True
                irsaliye = Irsaliye()
                irsaliye.firma_id = user.firma_id
                
                # Benzersiz ETTN oluştur (E-İrsaliye için şart)
                irsaliye.ettn = str(uuid.uuid4())
                
                if 'aktif_donem_id' in session:
                    irsaliye.donem_id = session['aktif_donem_id']
                else:
                    aktif_donem = tenant_db.query(Donem).filter_by(firma_id=user.firma_id, aktif=True).first()
                    irsaliye.donem_id = str(aktif_donem.id) if aktif_donem else '1'

            # 1. Başlık Bilgileri
            if form_data.get('tarih'):
                irsaliye.tarih = datetime.strptime(form_data.get('tarih'), '%Y-%m-%d').date()
            else:
                irsaliye.tarih = datetime.now().date()
            
            saat_str = form_data.get('saat', datetime.now().strftime('%H:%M'))
            try:
                irsaliye.saat = datetime.strptime(saat_str, '%H:%M').time()
            except ValueError:
                irsaliye.saat = datetime.now().time()
            
            irsaliye.belge_no = form_data.get('belge_no')
            irsaliye.cari_id = str(form_data.get('cari_id')) if form_data.get('cari_id') else None
            irsaliye.depo_id = str(form_data.get('depo_id')) if form_data.get('depo_id') else None
            irsaliye.aciklama = form_data.get('aciklama')
            
            irsaliye.plaka_arac = form_data.get('plaka_arac')
            irsaliye.sofor_ad = form_data.get('sofor_ad')
            irsaliye.sofor_soyad = form_data.get('sofor_soyad')
            irsaliye.sofor_tc = form_data.get('sofor_tc')

            if not irsaliye.irsaliye_turu:
                irsaliye.irsaliye_turu = IrsaliyeTuru.SEVK.value
            if not irsaliye.durum:
                irsaliye.durum = IrsaliyeDurumu.ONAYLANDI.value

            tenant_db.add(irsaliye)
            tenant_db.flush() # İrsaliye UUID'sini alıyoruz

            # Güncelleme modundaysa eski detayları ve stok hareketlerini temizle
            if not is_new:
                tenant_db.query(IrsaliyeKalemi).filter_by(irsaliye_id=irsaliye.id).delete()
                tenant_db.query(StokHareketi).filter_by(kaynak_turu='irsaliye', kaynak_id=irsaliye.id).delete()

            # 2. Kalemler ve Stok Hareketleri
            stok_ids = form_data.getlist('kalemler_stok_id[]')
            miktarlar = form_data.getlist('kalemler_miktar[]')
            birimler = form_data.getlist('kalemler_birim[]')
            aciklamalar = form_data.getlist('kalemler_aciklama[]')

            olusan_hareketler = []

            for i in range(len(stok_ids)):
                if not stok_ids[i] or stok_ids[i] == '0': continue
                
                miktar = para_cevir(miktarlar[i])
                if miktar <= 0: continue

                # Kalemi Oluştur
                kalem = IrsaliyeKalemi(irsaliye_id=irsaliye.id)
                kalem.stok_id = str(stok_ids[i])
                kalem.miktar = miktar
                kalem.birim = birimler[i] if i < len(birimler) else 'Adet'
                kalem.aciklama = aciklamalar[i] if i < len(aciklamalar) else ''
                tenant_db.add(kalem)

                # Kalemin ID (UUID) alabilmesi için flush yapıyoruz
                tenant_db.flush() 

                # Stok Hareketini Oluştur
                sh = StokHareketi()
                sh.firma_id = irsaliye.firma_id
                sh.donem_id = irsaliye.donem_id
                
                # Şube Seçimi Güvenliği
                if hasattr(user, 'yetkili_subeler') and user.yetkili_subeler:
                    sh.sube_id = str(user.yetkili_subeler[0].id)
                elif getattr(user, 'sube_id', None):
                    sh.sube_id = str(user.sube_id)
                else:
                    varsayilan_sube = tenant_db.query(Sube).filter_by(firma_id=irsaliye.firma_id, aktif=True).first()
                    sh.sube_id = str(varsayilan_sube.id) if varsayilan_sube else None
                                    
                sh.kullanici_id = str(user.id) if user else None 
                
                # İrsaliye türüne göre depo girişi mi çıkışı mı? (Varsayılan Çıkış)
                sh.cikis_depo_id = str(irsaliye.depo_id) if irsaliye.depo_id else None
                
                sh.stok_id = str(kalem.stok_id)
                sh.tarih = irsaliye.tarih
                sh.belge_no = irsaliye.belge_no
                sh.kaynak_turu = 'irsaliye'
                sh.kaynak_id = str(irsaliye.id)
                sh.kaynak_belge_detay_id = str(kalem.id) 
                
                sh.hareket_turu = HareketTuru.SATIS_IRSALIYESI.name 
                sh.miktar = kalem.miktar
                sh.aciklama = f"İrsaliye: {irsaliye.aciklama or ''}"
                
                tenant_db.add(sh)
                olusan_hareketler.append(sh)

            tenant_db.commit()

            # ✨ YENİ EKLENDİ: Sinyalleri Ateşle (Örn: Stok kritik seviye analizi için)
            for hareket in olusan_hareketler:
                stok_hareket_olusturuldu.send(hareket)

            return True, f"İrsaliye {irsaliye.belge_no} başarıyla kaydedildi."

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ İrsaliye Kayıt Hatası: {str(e)}", exc_info=True)
            return False, f"Sistem Hatası: {str(e)}"
            
    @staticmethod
    def faturaya_donustur(irsaliye_id: str, user: Any) -> Tuple[bool, str, Optional[str]]:
        """
        İrsaliyeyi alır, yeni bir Taslak Fatura oluşturur ve kalemleri aktarır.
        Not: Fatura TASLAK olarak kaydedilir, onaylanana kadar Muhasebe fişi KESİLMEZ!
        """
        tenant_db = get_tenant_db()
        irsaliye = tenant_db.get(Irsaliye, str(irsaliye_id))
        
        if not irsaliye:
            return False, "İrsaliye bulunamadı", None
            
        if irsaliye.faturalasti_mi:
            return False, "Bu irsaliye zaten faturalandırılmış!", irsaliye.fatura_id
            
        try:
            # Döngüsel içe aktarmayı önlemek için fonksiyon içinde çağırıyoruz
            from app.modules.fatura.models import Fatura, FaturaKalemi
            from app.araclar import siradaki_kod_uret
            
            # 1. Yeni Fatura Başlığını Oluştur
            fatura = Fatura()
            fatura.firma_id = irsaliye.firma_id
            fatura.donem_id = irsaliye.donem_id
            
            # Şube Seçimi
            if hasattr(user, 'yetkili_subeler') and user.yetkili_subeler:
                fatura.sube_id = str(user.yetkili_subeler[0].id)
            elif getattr(user, 'sube_id', None):
                fatura.sube_id = str(user.sube_id)
            else:
                varsayilan_sube = tenant_db.query(Sube).filter_by(firma_id=irsaliye.firma_id, aktif=True).first()
                fatura.sube_id = str(varsayilan_sube.id) if varsayilan_sube else None
                
            fatura.cari_id = str(irsaliye.cari_id) if irsaliye.cari_id else None
            fatura.depo_id = str(irsaliye.depo_id) if irsaliye.depo_id else None
            
            fatura.tarih = datetime.now().date()
            fatura.belge_no = siradaki_kod_uret(Fatura, 'FTR-') or f"FTR-{irsaliye.belge_no}"
            fatura.fatura_turu = 'satis' # Enum uyumlu
            fatura.durum = 'TASLAK'
            fatura.aciklama = f"İrsaliye'den dönüştürüldü. İrsaliye No: {irsaliye.belge_no}"
            fatura.doviz_turu = 'TL'
            fatura.doviz_kuru = Decimal('1.0000')
            
            # Fatura toplamlarını sıfırlıyoruz
            fatura.ara_toplam = Decimal('0.00')
            fatura.kdv_toplam = Decimal('0.00')
            fatura.iskonto_toplam = Decimal('0.00')
            fatura.genel_toplam = Decimal('0.00')
            fatura.dovizli_toplam = Decimal('0.00')
            
            # (Gelecek geliştirme: fatura.kaynak_irsaliye_id = irsaliye.id eklenebilir)
            
            tenant_db.add(fatura)
            tenant_db.flush() # Fatura UUID'sini alıyoruz
            
            # 2. İrsaliye Kalemlerini Fatura Kalemlerine Çevir
            for ik in irsaliye.kalemler:
                fk = FaturaKalemi(fatura_id=fatura.id)
                fk.stok_id = str(ik.stok_id)
                fk.miktar = ik.miktar
                fk.birim = ik.birim
                fk.birim_fiyat = Decimal('0.00') # Fiyatlandırma fatura ekranında yapılacak
                
                # ✨ KRİTİK DÜZELTME: İskonto ve KDV değerleri açıkça Decimal ve tek atama
                fk.iskonto_orani = Decimal('0.00') 
                fk.kdv_orani = Decimal('20.00') # Varsayılan KDV
                
                fk.aciklama = ik.aciklama
                tenant_db.add(fk)
                
            # 3. İrsaliyeyi "Faturalaştı" Olarak İşaretle
            irsaliye.faturalasti_mi = True
            irsaliye.fatura_id = str(fatura.id)
            
            tenant_db.commit()
            
            logger.info(f"✅ İrsaliye ({irsaliye.belge_no}), Faturaya ({fatura.belge_no}) dönüştürüldü.")
            return True, "İrsaliye başarıyla faturaya dönüştürüldü.", str(fatura.id)
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ İrsaliyeden Fatura Dönüştürme Hatası: {e}", exc_info=True)
            return False, f"Sistem Hatası: {str(e)}", None