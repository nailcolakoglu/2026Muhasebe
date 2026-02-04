# araclar.py

import math
from flask_login import current_user
from app.extensions import db
from app.models.base import FirmaOwnedMixin, JSONText, FirmaFilteredQuery
from app.modules.doviz.models import DovizKuru
from datetime import datetime
from sqlalchemy import func
from app.enums import FinansIslemTuru, FaturaTuru
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)

# --- 1.FORMAT VE ÇEVİRİ İŞLEMLERİ (TR FORMAT GÜÇLENDİRİLMİŞ) ---
def para_cevir(deger):
    """
    Türkiye Finans Formatına (%99) Öncelik Veren Çevirici.
    "1.000" -> 1000.00
    "1.000,50" -> 1000.50
    "1000" -> 1000.00
    """
    if deger is None: 
        return Decimal('0.00')
    
    # Zaten sayısal tipteyse direkt çevir
    if isinstance(deger, (int, float, Decimal)):
        return Decimal(str(deger))
    
    val_str = str(deger).strip()
    if not val_str:
        return Decimal('0.00')

    # Sembolleri temizle
    semboller = ['₺', '$', '€', '£', 'TL', 'TRL', 'USD', 'EUR', 'GBP']
    for sembol in semboller:
        val_str = val_str.replace(sembol, '')
    val_str = val_str.strip()

    try:
        # SENARYO A: Virgül varsa, kesinlikle TR formatıdır (Kuruş ayracı virgüldür)
        # Örn: 1.250,50 veya 10,50
        if ',' in val_str:
            # Noktaları (Binlik) sil, Virgülü (Kuruş) noktaya çevir
            temiz_val = val_str.replace('.', '').replace(',', '.')
            return Decimal(temiz_val)
        
        # SENARYO B: Virgül YOK ama Nokta VAR.
        # Örn: "1.000" veya "10.50"
        if '.' in val_str:
            parcalar = val_str.split('.')
            
            # Eğer noktadan sonra tam 3 hane varsa (1.000 gibi), bu büyük ihtimalle binlik ayraçtır.
            # Python/Web dünyasında 1.000 genellikle 1 demektir ama TR muhasebesinde 1000 demektir.
            # Biz ERP olduğumuz için TR mantığını baz alıyoruz.
            if len(parcalar) > 1 and len(parcalar[-1]) == 3:
                # 1.000 -> 1000 (Binlik ayracı kabul et ve sil)
                temiz_val = val_str.replace('.', '')
                return Decimal(temiz_val)
            else:
                # 10.5 veya 10.55 -> Ondalık kabul et
                return Decimal(val_str)
        
        # SENARYO C: Dümdüz Sayı (1000)
        return Decimal(val_str)

    except InvalidOperation:
        return Decimal('0.00')

# --- 2.VERİTABANI YARDIMCILARI ---
def siradaki_kod_uret(model, prefix, hane_sayisi=5):
    """
    Belirtilen model için firmaya özel sıradaki kodu üretir.
    Örn: SIP-00001
    """
    try:
        # Son kaydı bul (Firmaya özel)
        # Modelin 'belge_no' veya 'kod' alanı olduğunu varsayarız.
        # Genelde belge_no kullanılır.
        field = getattr(model, 'belge_no', None)
        if not field:
            field = getattr(model, 'kod', None)
            
        if not field:
            return f"{prefix}{'1'.zfill(hane_sayisi)}"

        son_kayit = model.query.filter_by(firma_id=current_user.firma_id)\
            .filter(field.like(f"{prefix}%"))\
            .order_by(field.desc()).first()
            
        if son_kayit:
            # Mevcut koddan sayıyı ayıkla (SIP-00005 -> 5)
            son_kod = getattr(son_kayit, field.key)
            try:
                # Prefix uzunluğunu atla veya '-' ile split et
                parcalar = son_kod.split('-')
                if len(parcalar) > 1:
                    sayi = int(parcalar[-1])
                    yeni_sayi = sayi + 1
                else:
                    # Prefix'i stringden çıkar
                    temiz = son_kod.replace(prefix, '')
                    yeni_sayi = int(temiz) + 1
            except:
                yeni_sayi = 1
        else:
            yeni_sayi = 1
            
        return f"{prefix}{str(yeni_sayi).zfill(hane_sayisi)}"
        
    except Exception as e:
        return f"{prefix}{'1'.zfill(hane_sayisi)}"

def sayiyi_yaziya_cevir(sayi):
    """
    Fatura/Çek yazdırma işlemleri için tutarı yazıya çevirir.
    Örn: 1250.50 -> BİN İKİ YÜZ ELLİ TÜRK LİRASI ELLİ KURUŞ
    """
    if not sayi: return ""
    
    try:
        tutar = float(sayi)
        lira = int(tutar)
        kurus = int(round((tutar - lira) * 100))
        
        birler = ["", "Bir", "İki", "Üç", "Dört", "Beş", "Altı", "Yedi", "Sekiz", "Dokuz"]
        onlar = ["", "On", "Yirmi", "Otuz", "Kırk", "Elli", "Altmış", "Yetmiş", "Seksen", "Doksan"]
        binler = ["", "Bin", "Milyon", "Milyar", "Trilyon"]

        def uc_haneli_cevir(sayi):
            if sayi == 0: return ""
            
            yuzler = sayi // 100
            onlar_bas = (sayi % 100) // 10
            birler_bas = sayi % 10
            
            yazi = ""
            
            # Yüzler Basamağı
            if yuzler == 1:
                yazi += "Yüz"
            elif yuzler > 1:
                yazi += birler[yuzler] + " Yüz"
                
            # Onlar ve Birler
            if onlar_bas > 0:
                yazi += " " + onlar[onlar_bas]
            if birler_bas > 0:
                yazi += " " + birler[birler_bas]
                
            return yazi.strip()

        # --- Ana Çevrim Döngüsü ---
        lira_yazi = ""
        str_lira = str(lira)
        
        # Sayıyı 3'lü gruplara bölmek için ters çevir
        gruplar = []
        while len(str_lira) > 0:
            gruplar.append(int(str_lira[-3:]))
            str_lira = str_lira[:-3]
            
        for i, grup in enumerate(gruplar):
            if grup > 0:
                grup_yazi = uc_haneli_cevir(grup)
                
                # "Bir Bin" kuralı (Binler basamağı 1 ise sadece "Bin" denir)
                if i == 1 and grup == 1:
                    grup_yazi = ""
                
                if i < len(binler):
                    lira_yazi = grup_yazi + " " + binler[i] + " " + lira_yazi
        
        sonuc = lira_yazi.strip() + " Türk Lirası"
        
        if kurus > 0:
            kurus_yazi = uc_haneli_cevir(kurus)
            sonuc += " " + kurus_yazi + " Kuruş"
            
        return sonuc.upper()
        
    except Exception:
        return ""

def get_muhasebe_hesaplari():
    """
    FormBuilder Select alanları için muhasebe hesaplarını (ID, AD) formatında döndürür.
    Sadece 'muavin' hesapları getirir.
    """
    if not current_user.is_authenticated:
        return []
        
    try:
        hesaplar = HesapPlani.query.filter_by(
            firma_id=current_user.firma_id,
            hesap_tipi='muavin' # Enum kullanıyorsan .value ekle
        ).order_by(HesapPlani.kod).all()
        
        return [(h.id, f"{h.kod} - {h.ad}") for h in hesaplar]
    except Exception as e:
        print(f"Hesap Planı Hatası: {e}")
        return []    

# --- 3.İŞ MANTIĞI YARDIMCILARI ---
def hesapla_ve_guncelle_ortalama_odeme(cari_id):
    """
    Bir cariye ait tüm satış faturalarını ve tahsilatları çeker.
    FIFO (İlk Giren İlk Çıkar) mantığıyla ödemeleri faturalarla eşleştirir.
    Ortalama gecikme/ödeme gününü hesaplayıp cari karta yazar.
    
    PERFORMANS İYİLEŞTİRMELERİ:
    - Bulk query (tek sorguda tüm veri)
    - Transaction yönetimi
    - Hata yakalama
    - Logging
    - Edge case kontrolü
    
    Args:
        cari_id (int): Hesaplanacak carinin ID'si
        
    Returns:
        dict: {
            'success': bool,
            'ortalama_gun': int,
            'toplam_fatura':  int,
            'toplam_tahsilat': int,
            'kapanan_tutar': Decimal,
            'kalan_borc': Decimal
        }
    """
    
    try:
        # ========================================
        # 1.VERİ DOĞRULAMA
        # ========================================
        if not cari_id:
            logger.error("Cari ID boş olamaz")
            return {
                'success': False,
                'error': 'Geçersiz cari ID',
                'ortalama_gun': 0
            }
        
        # Cari var mı kontrol et
        cari = db.session.get(CariHesap, cari_id)
        if not cari: 
            logger.error(f"Cari bulunamadı: {cari_id}")
            return {
                'success': False,
                'error': 'Cari hesap bulunamadı',
                'ortalama_gun': 0
            }
        
        # ========================================
        # 2.FATURALARI TEK SORGUDA ÇEK (OPTIMIZED)
        # ========================================
        # NOT: Sadece ödenmemiş veya kısmen ödenmiş faturaları al
        faturalar = Fatura.query.filter(
            and_(
                Fatura.cari_id == cari_id,
                Fatura.fatura_turu == FaturaTuru.SATIS.value,
                Fatura.durum != 'iptal',  # İptal edilenleri dahil etme
                or_(
                    Fatura.odeme_durumu == 'bekliyor',
                    Fatura.odeme_durumu == 'kismen'
                )
            )
        ).order_by(Fatura.vade_tarihi.asc()).all()
        
        # ========================================
        # 3.TAHSİLATLARI TEK SORGUDA ÇEK
        # ========================================
        tahsilatlar = FinansIslem.query.filter(
            and_(
                FinansIslem.cari_id == cari_id,
                FinansIslem.islem_turu == FinansIslemTuru.TAHSILAT.value,
                FinansIslem.durum == 'onaylandi'  # Sadece onaylı tahsilatlar
            )
        ).order_by(FinansIslem.tarih.asc()).all()
        
        # ========================================
        # 4.EDGE CASE KONTROL
        # ========================================
        if not faturalar: 
            logger.info(f"Cari {cari_id} için fatura bulunamadı")
            return {
                'success': True,
                'ortalama_gun': 0,
                'toplam_fatura': 0,
                'toplam_tahsilat': len(tahsilatlar),
                'kapanan_tutar':  Decimal('0.00'),
                'kalan_borc':  Decimal('0.00')
            }
        
        if not tahsilatlar:
            logger.info(f"Cari {cari_id} için tahsilat bulunamadı")
            # Ortalama gecikmeyi hesapla (bugüne göre)
            bugun = datetime.now().date()
            toplam_gecikme = 0
            toplam_tutar = Decimal('0.00')
            
            for fatura in faturalar:
                vade = fatura.vade_tarihi
                if isinstance(vade, datetime):
                    vade = vade.date()
                    
                gun_farki = (bugun - vade).days
                tutar = Decimal(str(fatura.genel_toplam or 0))
                
                toplam_gecikme += (gun_farki * float(tutar))
                toplam_tutar += tutar
            
            ortalama_gun = int(toplam_gecikme / float(toplam_tutar)) if toplam_tutar > 0 else 0
            
            # Veritabanına kaydet
            cari.ortalama_odeme_gunu = ortalama_gun
            if ortalama_gun > 30:
                cari.risk_skoru = min((cari.risk_skoru or 0) + 10, 100)
            
            db.session.commit()
            
            return {
                'success': True,
                'ortalama_gun': ortalama_gun,
                'toplam_fatura':  len(faturalar),
                'toplam_tahsilat':  0,
                'kapanan_tutar':  Decimal('0.00'),
                'kalan_borc': toplam_tutar
            }
        
        # ========================================
        # 5.FIFO ALGORİTMASI (İYİLEŞTİRİLMİŞ)
        # ========================================
        toplam_gecikme_puani = Decimal('0.00')
        toplam_kapanan_tutar = Decimal('0.00')
        
        # Faturaların kalan tutarlarını takip etmek için dictionary kullan
        fatura_bakiyeleri = {}
        for fatura in faturalar: 
            fatura_bakiyeleri[fatura.id] = {
                'kalan':  Decimal(str(fatura.genel_toplam or 0)),
                'vade':  fatura.vade_tarihi,
                'fatura':  fatura
            }
        
        # Her tahsilatı sırayla faturalara dağıt
        for tahsilat in tahsilatlar: 
            kalan_odeme = Decimal(str(tahsilat.genel_toplam or 0))
            
            if kalan_odeme <= 0:
                continue
            
            # Ödeme tarihini standartlaştır
            odeme_tarihi = tahsilat.tarih
            if isinstance(odeme_tarihi, datetime):
                odeme_tarihi = odeme_tarihi.date()
            
            # Faturaları vade tarihine göre sırayla dolaş (FIFO)
            for fatura in faturalar:
                if kalan_odeme <= 0:
                    break
                
                fatura_data = fatura_bakiyeleri[fatura.id]
                
                if fatura_data['kalan'] <= 0:
                    continue
                
                # Eşleşen Tutar (Hangi miktar kadar kapatılacak?)
                eslesen_tutar = min(kalan_odeme, fatura_data['kalan'])
                
                # Vade Tarihini Standartlaştır
                vade = fatura_data['vade']
                if isinstance(vade, datetime):
                    vade = vade.date()
                
                # Gün Farkını Hesapla (Pozitif = Geç, Negatif = Erken)
                gun_farki = (odeme_tarihi - vade).days
                
                # Ağırlıklı Puan (Tutar × Gün)
                # Örn: 1000 TL × 5 gün gecikme = 5000 puan
                puan = eslesen_tutar * Decimal(str(gun_farki))
                toplam_gecikme_puani += puan
                toplam_kapanan_tutar += eslesen_tutar
                
                # Bakiyeleri Güncelle
                kalan_odeme -= eslesen_tutar
                fatura_data['kalan'] -= eslesen_tutar
                
                logger.debug(
                    f"Fatura {fatura.id}:  {eslesen_tutar} TL kapandı, "
                    f"Gecikme: {gun_farki} gün, Puan:  {puan}"
                )
        
        # ========================================
        # 6.ORTALAMA HESAPLAMA
        # ========================================
        ortalama_gun = 0
        if toplam_kapanan_tutar > 0:
            # Ağırlıklı ortalama:  Toplam Puan / Toplam Tutar
            ortalama_gun = int(float(toplam_gecikme_puani) / float(toplam_kapanan_tutar))
        
        # Kalan toplam borç (Kapanmamış fatura tutarları)
        kalan_borc = sum(
            data['kalan'] 
            for data in fatura_bakiyeleri.values()
        )
        
        logger.info(
            f"Cari {cari_id} - Ortalama Ödeme: {ortalama_gun} gün, "
            f"Kapanan:  {toplam_kapanan_tutar} TL, Kalan: {kalan_borc} TL"
        )
        
        # ========================================
        # 7.CARİ KARTI GÜNCELLE (TRANSACTION)
        # ========================================
        try:
            cari.ortalama_odeme_gunu = ortalama_gun
            
            # Risk Skoru Güncelleme (İş Mantığı)
            if ortalama_gun > 60:
                cari.risk_skoru = min((cari.risk_skoru or 0) + 20, 100)
            elif ortalama_gun > 30:
                cari.risk_skoru = min((cari.risk_skoru or 0) + 10, 100)
            elif ortalama_gun < 0:  # Erken ödüyorsa (İyi müşteri)
                cari.risk_skoru = max((cari.risk_skoru or 0) - 5, 0)
            
            # Son güncelleme zamanını kaydet
            cari.son_guncelleme = datetime.now()
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Cari güncelleme hatası: {e}")
            raise
        
        # ========================================
        # 8.SONUÇ DÖNDÜR
        # ========================================
        return {
            'success': True,
            'ortalama_gun': ortalama_gun,
            'toplam_fatura': len(faturalar),
            'toplam_tahsilat': len(tahsilatlar),
            'kapanan_tutar': toplam_kapanan_tutar,
            'kalan_borc': kalan_borc,
            'risk_skoru': cari.risk_skoru
        }
        
    except Exception as e:
        logger.exception(f"Ortalama ödeme hesaplama hatası (Cari:  {cari_id}): {e}")
        db.session.rollback()
        
        return {
            'success':  False,
            'error': str(e),
            'ortalama_gun': 0
        }

# ========================================
# TOPLU HESAPLAMA FONKSİYONU (BONUS)
# ========================================
def toplu_ortalama_odeme_hesapla(firma_id=None, limit=None):
    """
    Tüm carilerin ortalama ödeme günlerini toplu hesaplar.
    Gece batch job'ı olarak çalıştırılabilir.
    
    Args:
        firma_id (int, optional): Sadece belirli bir firmayı hesapla
        limit (int, optional): Kaç cari işlensin (test için)
        
    Returns: 
        dict: İstatistikler
    """
    
    try:
        # İşlenecek carileri bul
        query = CariHesap.query
        
        if firma_id: 
            query = query.filter_by(firma_id=firma_id)
        
        # Sadece aktif carileri işle
        query = query.filter_by(aktif=True)
        
        if limit:
            query = query.limit(limit)
        
        cariler = query.all()
        
        basarili = 0
        basarisiz = 0
        toplam_sure = 0
        
        logger.info(f"Toplu hesaplama başladı:  {len(cariler)} cari işlenecek")
        
        for cari in cariler:
            baslangic = datetime.now()
            
            sonuc = hesapla_ve_guncelle_ortalama_odeme(cari.id)
            
            bitis = datetime.now()
            sure = (bitis - baslangic).total_seconds()
            toplam_sure += sure
            
            if sonuc['success']: 
                basarili += 1
            else:
                basarisiz += 1
                logger.warning(
                    f"Cari {cari.id} ({cari.unvan}) işlenemedi: "
                    f"{sonuc.get('error', 'Bilinmeyen hata')}"
                )
        
        ortalama_sure = toplam_sure / len(cariler) if cariler else 0
        
        logger.info(
            f"Toplu hesaplama tamamlandı: "
            f"Başarılı: {basarili}, Başarısız: {basarisiz}, "
            f"Ortalama Süre: {ortalama_sure:.2f}s"
        )
        
        return {
            'success': True,
            'toplam_cari': len(cariler),
            'basarili': basarili,
            'basarisiz': basarisiz,
            'toplam_sure': toplam_sure,
            'ortalama_sure': ortalama_sure
        }
        
    except Exception as e:
        logger.exception(f"Toplu hesaplama hatası: {e}")
        return {
            'success':  False,
            'error': str(e)
        }


# ========================================
# KULLANIM ÖRNEKLERİ
# ========================================
"""
# Tekil kullanım: 
sonuc = hesapla_ve_guncelle_ortalama_odeme(cari_id=123)
if sonuc['success']:
    print(f"Ortalama ödeme günü: {sonuc['ortalama_gun']}")
    print(f"Kalan borç: {sonuc['kalan_borc']} TL")

# Toplu kullanım (Flask CLI komutu olarak):
@app.cli.command()
def hesapla_odemeler():
    with app.app_context():
        sonuc = toplu_ortalama_odeme_hesapla(limit=100)
        print(f"İşlenen:  {sonuc['toplam_cari']}, Süre: {sonuc['toplam_sure']:.2f}s")

# Cron Job (Her gece 02:00):
# 0 2 * * * cd /app && flask hesapla_odemeler
"""


# ---------------------------------------------------------
# 4.NUMARA ÜRETME MOTORU (ATOMİK & GÜVENLİ)
# ---------------------------------------------------------
def numara_uret(firma_id, kod, yil=None, on_ek='DOC-', hane=6):
    """
    ATOMİK NUMARA ÜRETİCİSİ (Thread-Safe)
    """
    if not yil:
        yil = datetime.now().year

    try:
        # Sayacı Bul ve KİLİTLE
        sayac = Sayac.query.filter_by(
            firma_id=firma_id, 
            kod=kod, 
            donem_yili=yil
        ).with_for_update().first()

        # Sayaç Yoksa Oluştur
        if not sayac:
            sayac = Sayac(
                firma_id=firma_id,
                donem_yili=yil,
                kod=kod,
                on_ek=on_ek,
                son_no=0
            )
            if hasattr(sayac, 'hane_sayisi'):
                sayac.hane_sayisi = hane
            db.session.add(sayac)
            db.session.flush()
        
        sayac.son_no += 1
        yeni_no = sayac.son_no
        
        hane_len = getattr(sayac, 'hane_sayisi', hane)
        formatli_no = f"{sayac.on_ek}{str(yeni_no).zfill(hane_len)}"
        return formatli_no

    except Exception as e:
        raise e

def get_doviz_kuru(doviz_kodu):
    """
    Verilen döviz kodunun sistemdeki en güncel kurunu getirir.
    Kullanım:
      kur = get_doviz_kuru('USD') -> 32.50
      kur = get_doviz_kuru('TL')  -> 1.0
    """
    if not doviz_kodu or doviz_kodu == 'TL':
        return 1.0
    
    try:
        # En son tarihli kuru bul
        kur_kaydi = DovizKuru.query.filter_by(kod=doviz_kodu)\
            .order_by(DovizKuru.tarih.desc())\
            .first()
        
        if kur_kaydi:
            # Satış kurunu baz alıyoruz (Yoksa efektif satış)
            val = kur_kaydi.satis if kur_kaydi.satis > 0 else kur_kaydi.efektif_satis
            return float(val)
        
        return 0.0 # Kur bulunamadı
        
    except Exception as e:
        print(f"Kur getirme hatası: {e}")
        return 0.0

def sayi_formatla(deger, basamak=2):
    """
    Sayısal değerleri TR formatında stringe çevirir.
    Örn: 1250.5 -> "1.250,50"
    None gelirse "0,00" döner.
    """
    if deger is None:
        return "0," + "0"*basamak
        
    try:
        val = float(deger)
        # Python f-string ile binlik ayraç (,) ve ondalık (.) yapıyoruz
        # Sonra bunları TR formatına (nokta ve virgül yer değiştir) çeviriyoruz
        format_str = f"{{:,.{basamak}f}}"
        formatted = format_str.format(val)
        return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "0," + "0"*basamak


