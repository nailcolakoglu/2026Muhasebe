# app/modules/cek/services.py

import logging
from datetime import datetime
from decimal import Decimal

from app.extensions import get_tenant_db
from app.modules.cek.models import CekSenet
from app.modules.cari.models import CariHareket 
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.enums import CekDurumu, CekIslemTuru, CariIslemTuru, CekKonumu, PortfoyTipi

# 🔥 Sinyalleri dahil ediyoruz
from app.signals import cek_tahsil_edildi, cek_ciro_edildi, cek_karsiliksiz_cikti

logger = logging.getLogger(__name__)

class CekService:
    
    @staticmethod
    def yeni_cek_girisi(data, user_id, firma_id):
        """
        Yeni çek kaydı oluşturur, cariyi alacaklandırır ve muhasebe fişini keser.
        (Tenant DB Uyumlu)
        """
        tenant_db = get_tenant_db()
        
        try:
            # 1. Çek Kaydı
            yeni_cek = CekSenet(
                firma_id=firma_id,
                portfoy_tipi=data.get('portfoy_tipi', 'alinan'),
                tur=data.get('tur', 'cek'),
                belge_no=data.get('belge_no'),
                cek_no=data.get('cek_no'),
                vade_tarihi=data.get('vade_tarihi'),
                tutar=Decimal(str(data.get('tutar', 0))),
                cari_id=data.get('cari_id'),
                aciklama=data.get('aciklama'),
                cek_durumu=CekDurumu.PORTFOYDE
            )
            
            # AI Risk Analizi Tetikle (Model içinde tanımlıysa)
            if hasattr(yeni_cek, 'risk_analizi_yap'):
                yeni_cek.risk_analizi_yap()
            
            tenant_db.add(yeni_cek)
            tenant_db.flush() # ID oluşsun diye flush yapıyoruz

            # 2. Cari Hesaba İşle (Operasyonel Kayıt)
            # Müşteriden çek aldık -> Müşteri Alacaklanır (Borcu düşer)
            ch = CariHareket(
                firma_id=firma_id,
                cari_id=yeni_cek.cari_id,
                tarih=datetime.now().date(),
                islem_turu=CariIslemTuru.CEK_GIRIS.name if hasattr(CariIslemTuru, 'name') else 'CEK_GIRIS',
                belge_no=yeni_cek.belge_no,
                aciklama=f"Çek Girişi: {yeni_cek.cek_no}",
                borc=Decimal('0.00'),
                alacak=yeni_cek.tutar,
                kaynak_turu='cek',
                kaynak_id=str(yeni_cek.id)
            )
            tenant_db.add(ch)

            # 3. Resmi Muhasebe Fişi (101 Alınan Çekler - 120 Alıcılar)
            # Circular import önlemek için metot içinde çağırıyoruz
            from app.modules.muhasebe.services import MuhasebeEntegrasyonService
            basari, mesaj = MuhasebeEntegrasyonService.entegre_et_cek(str(yeni_cek.id), 'giris')
            
            if not basari:
                logger.warning(f"⚠️ Çek Giriş Muhasebe Uyarısı: {mesaj}")

            tenant_db.commit()
            return True, "Çek başarıyla kaydedildi ve muhasebeleştirildi."

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Çek Kayıt Hatası: {str(e)}", exc_info=True)
            return False, f"Sistem Hatası: {str(e)}"

    @staticmethod
    def cek_durum_degistir(cek_id, islem_turu, hedef_id=None, aciklama=""):
        """
        Tahsilat, Ciro, Karşılıksız gibi durumlarda çalışır.
        (Tenant DB ve Signal Uyumlu)
        """
        tenant_db = get_tenant_db()
        cek = tenant_db.get(CekSenet, str(cek_id))
        
        if not cek: 
            return False, "Kayıt bulunamadı."

        try:
            bugun = datetime.now().date()
            from app.modules.muhasebe.services import MuhasebeEntegrasyonService

            # Enum nesnesi geldiyse string'e çevir
            islem_val = islem_turu.value if hasattr(islem_turu, 'value') else str(islem_turu)

            # --- TAHSİLAT (KASA) ---
            if islem_val == 'TAHSIL_KASA':
                # Kasa Hareketi
                kh = KasaHareket(
                    firma_id=cek.firma_id,
                    kasa_id=hedef_id,
                    tarih=bugun,
                    islem_turu='tahsilat',
                    tutar=cek.tutar,
                    belge_no=cek.belge_no,
                    aciklama=aciklama or f"Çek Tahsilatı (Kasa): {cek.cek_no}",
                    kaynak_turu='cek',
                    kaynak_id=str(cek.id)
                )
                tenant_db.add(kh)
                
                # Muhasebe servisine "Kasa" olduğunu belirtmek için geçici atama
                cek.cek_durumu = "kasa_tahsil" 
                tenant_db.flush()
                
                # Muhasebe (100 Kasa - 101 Alınan Çekler)
                MuhasebeEntegrasyonService.entegre_et_cek(str(cek.id), 'tahsil', hedef_id)
                
                cek.cek_durumu = CekDurumu.TAHSIL_EDILDI
                cek.tahsil_tarihi = bugun
                
                # Sinyal Ateşle
                cek_tahsil_edildi.send(cek)

            # --- TAHSİLAT (BANKA) ---
            elif islem_val == 'TAHSIL_BANKA':
                # Banka Hareketi
                bh = BankaHareket(
                    firma_id=cek.firma_id,
                    banka_id=hedef_id,
                    tarih=bugun,
                    islem_turu='tahsilat',
                    tutar=cek.tutar,
                    belge_no=cek.belge_no,
                    aciklama=aciklama or f"Çek Tahsilatı (Banka): {cek.cek_no}",
                    kaynak_turu='cek',
                    kaynak_id=str(cek.id)
                )
                tenant_db.add(bh)
                
                cek.cek_durumu = "banka_tahsil"
                tenant_db.flush()
                
                # Muhasebe (102 Bankalar - 101 Alınan Çekler)
                MuhasebeEntegrasyonService.entegre_et_cek(str(cek.id), 'tahsil', hedef_id)

                cek.cek_durumu = CekDurumu.TAHSIL_EDILDI
                cek.tahsil_tarihi = bugun
                
                # Sinyal Ateşle
                cek_tahsil_edildi.send(cek)

            # --- CİRO (CARİYE ÇIKIŞ) ---
            elif islem_val == 'CIRO':
                # Satıcıya verdik -> Satıcı Borçlanır (Bizim borcumuz düşer)
                ch = CariHareket(
                    firma_id=cek.firma_id,
                    cari_id=hedef_id,
                    tarih=bugun,
                    islem_turu=CariIslemTuru.CEK_CIKIS.name if hasattr(CariIslemTuru, 'name') else 'CEK_CIKIS',
                    belge_no=cek.belge_no,
                    aciklama=aciklama or f"Çek Cirosu: {cek.cek_no}",
                    borc=cek.tutar,
                    alacak=Decimal('0.00'),
                    kaynak_turu='cek',
                    kaynak_id=str(cek.id)
                )
                tenant_db.add(ch)
                
                cek.cek_durumu = CekDurumu.TEMLIK_EDILDI
                cek.verilen_cari_id = hedef_id
                
                # Muhasebe (320 Satıcılar - 101 Alınan Çekler)
                MuhasebeEntegrasyonService.entegre_et_cek(str(cek.id), 'ciro', hedef_id)
                
                # Sinyal Ateşle
                cek_ciro_edildi.send(cek)

            # --- KARŞILIKSIZ ÇEK ---
            elif islem_val == 'KARSILIKSIZ':
                cek.cek_durumu = CekDurumu.KARSILIKSIZ
                # Müşteri risk skorunu düşürmek için sinyal ateşle
                cek_karsiliksiz_cikti.send(cek, cari=cek.cari) 

            tenant_db.commit()
            return True, "İşlem başarıyla tamamlandı ve muhasebeleştirildi."

        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ Çek İşlem Hatası: {str(e)}", exc_info=True)
            return False, f"Hata: {str(e)}"