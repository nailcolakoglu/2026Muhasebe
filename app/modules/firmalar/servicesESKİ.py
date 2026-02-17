# app/modules/firmalar/services.py

import pymysql
from config import Config

class FirmaService:
    
    @staticmethod
    def firma_olustur(unvan, vergi_no):
        """Yeni firma oluştur ve MySQL tenant DB'sini hazırla"""
        
        # 1. Master DB'ye firma kaydı
        firma = Firma()
        firma.id = str(uuid.uuid4())
        firma.unvan = unvan
        firma.vergi_no = vergi_no
        
        # 2. Tenant DB adı oluştur (unique)
        firma_kod = unvan[:5].upper().replace(' ', '_')
        firma.tenant_db_name = f'erp_{firma_kod}_{firma.id[:8]}'
        # Örnek: erp_ACME_a1b2c3d4
        
        db.session.add(firma)
        db.session.commit()
        
        # 3. MySQL'de tenant DB oluştur
        FirmaService.create_tenant_database(firma.tenant_db_name)
        
        # 4. Tabloları oluştur (schema migration)
        FirmaService.initialize_tenant_schema(firma.tenant_db_name)
        
        return firma
    
    @staticmethod
    def create_tenant_database(db_name):
        """MySQL'de yeni tenant database oluştur"""
        
        # Root connection (sadece DB oluşturmak için)
        root_conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_ROOT_USER,
            password=Config.MYSQL_ROOT_PASSWORD,
            charset='utf8mb4'
        )
        
        try:
            with root_conn.cursor() as cursor:
                # Database oluştur
                cursor.execute(f"""
                    CREATE DATABASE IF NOT EXISTS {db_name}
                    CHARACTER SET utf8mb4
                    COLLATE utf8mb4_unicode_ci
                """)
                
                # Tenant kullanıcısına yetki ver
                cursor.execute(f"""
                    GRANT ALL PRIVILEGES ON {db_name}.* 
                    TO '{Config.MYSQL_USER}'@'localhost'
                """)
                
                cursor.execute("FLUSH PRIVILEGES")
                
            root_conn.commit()
            logger.info(f"✅ Tenant DB oluşturuldu: {db_name}")
            
        except Exception as e:
            logger.error(f"❌ Tenant DB oluşturma hatası: {e}")
            raise
        
        finally:
            root_conn.close()
    
    @staticmethod
    def initialize_tenant_schema(db_name):
        """Tenant DB'sine tabloları ekle"""
        
        from sqlalchemy import create_engine
        from app.modules.banka.models import BankaHesap
        from app.modules.banka_hareket.models import BankaHareket
        from app.modules.banka_import.models import BankaImportSablon, BankaImportKurali, BankaImportGecmisi
        from app.modules.bolge.models import Bolge
        from app.modules.cari.models import CariHesap, CariHareket, CRMHareket
        from app.modules.cek.models import CekSenet
        from app.modules.depo.models import Depo
        from app.modules.doviz.models import DovizKuru
        from app.modules.efatura.models import EntegratorAyarlari
        from app.modules.fatura.models import Fatura, FaturaKalemi
        from app.modules.finans.models import FinansIslem
        from app.modules.firmalar.models import Firma, Donem, SystemMenu
        from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
        from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi
        from app.modules.kasa.models import Kasa
        from app.modules.kasa_hareket.models import KasaHareket
        from app.modules.kategori.models import StokKategori
        from app.modules.kullanici.models import Kullanici
        from app.modules.lokasyon.models import Sehir, Ilce
        from app.modules.muhasebe.models import HesapPlani, MuhasebeFisi, MuhasebeFisiDetay
        from app.modules.rapor.models import YazdirmaSablonu, SavedReport
        from app.modules.siparis.models import Siparis, SiparisDetay, OdemePlani
        from app.modules.stok.models import StokKart, StokPaketIcerigi, StokMuhasebeGrubu, StokKDVGrubu
        from app.modules.stok_fisi.models import StokFisi
        from app.modules.sube.models import Sube
        
        
        # ... diğer modeller
        
        # Tenant DB'sine bağlan
        tenant_engine = create_engine(
            f"mysql+mysqldb://{Config.MYSQL_USER}:{Config.MYSQL_PASSWORD}"
            f"@{Config.MYSQL_HOST}/{db_name}?charset=utf8mb4"
        )
        
        # Tüm tabloları oluştur
        db.metadata.create_all(
            bind=tenant_engine,
            tables=[ 
                BankaHesap.__table__, 
                BankaHareket.__table__, 
                BankaImportSablon.__table__, BankaImportKurali.__table__, BankaImportGecmisi.__table__,
                Bolge.__table__,
                CariHesap.__table__, CariHareket.__table__, CRMHareket.__table__,
                CekSenet.__table__,
                Depo.__table__, 
                DovizKuru.__table__,
                EntegratorAyarlari.__table__,
                Fatura.__table__, FaturaKalemi.__table__,
                FinansIslem.__table__,
                Firma.__table__, Donem.__table__, SystemMenu.__table__,
                FiyatListesi.__table__, FiyatListesiDetay.__table__,
                Irsaliye.__table__, IrsaliyeKalemi.__table__,
                Kasa.__table__,
                KasaHareket.__table__,
                StokKategori.__table__,
                Kullanici.__table__,
                Sehir.__table__, Ilce.__table__,
                HesapPlani.__table__, MuhasebeFisi.__table__, MuhasebeFisiDetay.__table__,
                YazdirmaSablonu.__table__, SavedReport.__table__,
                Siparis.__table__, SiparisDetay.__table__, OdemePlani.__table__,
                StokKart.__table__, StokPaketIcerigi.__table__, StokMuhasebeGrubu.__table__, StokKDVGrubu.__table__,
                StokFisi.__table__,
                Sube.__table__
            ]
        )
        
        logger.info(f"✅ Tenant schema oluşturuldu: {db_name}")