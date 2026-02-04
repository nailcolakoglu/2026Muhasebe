# modules/cek/services.py

from app.extensions import db
from app.modules.cek.models import CekSenet
from app.modules.cari.models import CariHareket 
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.banka_hareket.models import BankaHareket
from app.enums import CekDurumu, CekIslemTuru, CariIslemTuru, CekKonumu, PortfoyTipi
from datetime import datetime
from app.modules.cek.models import CekSenet

# Diğer servisleri import ediyoruz (Aşağıda tanımlayacağız)
from app.modules.muhasebe.services import MuhasebeEntegrasyonService
from app.modules.cari.services import CariService

class CekService:
    
    @staticmethod
    def yeni_cek_girisi(data, user_id, firma_id):
        """
        Yeni çek kaydı oluşturur, cariyi alacaklandırır ve muhasebe fişini keser.
        """
        try:
            # 1.Çek Kaydı
            yeni_cek = CekSenet(
                firma_id=firma_id,
                portfoy_tipi=data['portfoy_tipi'], # 'alinan'
                tur=data['tur'],
                belge_no=data['belge_no'],
                cek_no=data.get('cek_no'),
                vade_tarihi=data['vade_tarihi'],
                tutar=data['tutar'],
                cari_id=data['cari_id'],
                aciklama=data.get('aciklama'),
                cek_durumu=CekDurumu.PORTFOYDE
            )
            
            # AI Risk Analizi Tetikle
            yeni_cek.risk_analizi_yap()
            
            db.session.add(yeni_cek)
            db.session.flush() # ID oluşsun diye flush yapıyoruz

            # 2.Cari Hesaba İşle (Operasyonel Kayıt)
            # Müşteriden çek aldık -> Müşteri Alacaklanır (Borcu düşer)
            CariService.hareket_ekle(
                cari_id=yeni_cek.cari_id,
                islem_turu=CariIslemTuru.CEK_GIRIS,
                tutar=yeni_cek.tutar,
                yon='alacak', 
                belge_no=yeni_cek.belge_no,
                aciklama=f"Çek Girişi: {yeni_cek.cek_no}",
                kaynak_modul='cek',
                kaynak_id=yeni_cek.id
            )

            # 3.Resmi Muhasebe Fişi (101 Alınan Çekler - 120 Alıcılar)
            MuhasebeEntegrasyonService.cek_giris_fisi(yeni_cek)

            db.session.commit()
            return True, "Çek başarıyla kaydedildi ve muhasebeleştirildi."

        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def cek_durum_degistir(cek_id, islem_turu, hedef_id=None, aciklama=""):
        """
        Tahsilat, Ciro, Karşılıksız gibi durumlarda çalışır.
        """
        cek = CekSenet.query.get(cek_id)
        if not cek: return False, "Kayıt bulunamadı."

        try:
            eski_durum = cek.cek_durumu
            bugun = datetime.now().date()

            # --- TAHSİLAT (KASA) ---
            if islem_turu == CekIslemTuru.TAHSIL_KASA.value:
                # Kasa Hareketi
                kasa_hareket = KasaHareket(
                    firma_id=cek.firma_id,
                    kasa_id=hedef_id,
                    islem_turu='tahsilat',
                    tutar=cek.tutar,
                    belge_no=cek.belge_no,
                    aciklama=f"Çek Tahsilatı: {cek.cek_no}"
                )
                db.session.add(kasa_hareket)
                
                cek.cek_durumu = CekDurumu.TAHSIL_EDILDI
                cek.tahsil_tarihi = bugun
                
                # Muhasebe (100 Kasa - 101 Alınan Çekler)
                MuhasebeEntegrasyonService.cek_tahsil_fisi(cek, 'kasa', hedef_id)

            # --- TAHSİLAT (BANKA) ---
            elif islem_turu == CekIslemTuru.TAHSIL_BANKA.value:
                # Banka Hareketi
                banka_hareket = BankaHareket(
                    firma_id=cek.firma_id,
                    banka_id=hedef_id,
                    islem_turu='tahsilat',
                    tutar=cek.tutar,
                    belge_no=cek.belge_no,
                    aciklama=f"Çek Tahsilatı: {cek.cek_no}"
                )
                db.session.add(banka_hareket)
                
                cek.cek_durumu = CekDurumu.TAHSIL_EDILDI
                cek.tahsil_tarihi = bugun
                
                # Muhasebe (102 Bankalar - 101 Alınan Çekler)
                MuhasebeEntegrasyonService.cek_tahsil_fisi(cek, 'banka', hedef_id)

            # --- CİRO (CARİYE ÇIKIŞ) ---
            elif islem_turu == CekIslemTuru.CIRO.value:
                # Satıcıya verdik -> Satıcı Borçlanır (Bizim borcumuz düşer)
                CariService.hareket_ekle(
                    cari_id=hedef_id,
                    islem_turu=CariIslemTuru.CEK_CIKIS,
                    tutar=cek.tutar,
                    yon='borc', 
                    belge_no=cek.belge_no,
                    aciklama=f"Çek Cirosu: {cek.cek_no}",
                    kaynak_modul='cek',
                    kaynak_id=cek.id
                )
                
                cek.cek_durumu = CekDurumu.TEMLIK_EDILDI
                cek.verilen_cari_id = hedef_id
                
                # Muhasebe (320 Satıcılar - 101 Alınan Çekler)
                MuhasebeEntegrasyonService.cek_ciro_fisi(cek, hedef_id)

            db.session.commit()
            return True, "İşlem başarıyla tamamlandı."

        except Exception as e:
            db.session.rollback()
            return False, f"Hata: {str(e)}"