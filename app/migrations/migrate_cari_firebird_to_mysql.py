# migrations/migrate_cari_firebird_to_mysql.py

"""
Firebird'den MySQL'e Cari Modülü Migration Script
Her firma için ayrı MySQL database'e taşıma
"""

import logging
import pymysql
import fdb
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.extensions import db
from app.models.master.firma import Firma
from app.modules.cari.models import CariHesap, CariHareket, CRMHareket
from app.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CariMigrationService:
    """Cari modülü migration servisi"""
    
    def __init__(self):
        self.errors = []
        self.success_count = 0
        self.skip_count = 0
    
    def migrate_all_firms(self):
        """Tüm firmaları Firebird'den MySQL'e taşı"""
        
        logger.info("=" * 80)
        logger.info("CARİ MODÜLÜ MİGRATION BAŞLADI")
        logger.info("=" * 80)
        
        # Master DB'den tüm aktif firmaları çek
        firmalar = Firma.query.filter_by(aktif=True).all()
        
        logger.info(f"📊 Toplam {len(firmalar)} firma bulundu")
        
        for idx, firma in enumerate(firmalar, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"[{idx}/{len(firmalar)}] Firma: {firma.unvan}")
            logger.info(f"{'=' * 80}")
            
            try:
                self.migrate_firma(firma)
            except Exception as e:
                logger.error(f"❌ Firma migration hatası: {e}")
                self.errors.append({
                    'firma': firma.unvan,
                    'error': str(e)
                })
        
        # Özet rapor
        self.print_summary()
    
    def migrate_firma(self, firma):
        """Tek bir firmayı taşı"""
        
        # 1. Firebird bağlantısı
        fb_conn = self.connect_firebird(firma)
        if not fb_conn:
            raise Exception("Firebird bağlantısı kurulamadı")
        
        # 2. MySQL tenant DB oluştur (yoksa)
        mysql_db_name = self.create_mysql_tenant_db(firma)
        
        # 3. MySQL tenant bağlantısı
        mysql_session = self.connect_mysql_tenant(mysql_db_name)
        
        # 4. Schema oluştur
        self.create_mysql_schema(mysql_session)
        
        # 5. Verileri taşı
        try:
            # 5a. Cari Hesapları taşı
            cari_count = self.migrate_cari_hesaplar(fb_conn, mysql_session, firma)
            logger.info(f"✅ {cari_count} cari hesap taşındı")
            
            # 5b. Cari Hareketleri taşı
            hareket_count = self.migrate_cari_hareketler(fb_conn, mysql_session, firma)
            logger.info(f"✅ {hareket_count} cari hareket taşındı")
            
            # 5c. CRM Hareketleri taşı (varsa)
            crm_count = self.migrate_crm_hareketler(fb_conn, mysql_session, firma)
            logger.info(f"✅ {crm_count} CRM kaydı taşındı")
            
            # 6. Bakiyeleri doğrula
            self.validate_balances(mysql_session)
            
            # 7. Firma kaydını güncelle
            firma.tenant_db_name = mysql_db_name
            firma.migration_date = datetime.now()
            db.session.commit()
            
            self.success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Veri taşıma hatası: {e}")
            mysql_session.rollback()
            raise
        
        finally:
            fb_conn.close()
            mysql_session.close()
    
    def connect_firebird(self, firma):
        """Firebird bağlantısı kur"""
        try:
            conn = fdb.connect(
                host='localhost',
                database=firma.firebird_db_path,
                user='SYSDBA',
                password=firma.firebird_password,
                charset='UTF8'
            )
            logger.info("✅ Firebird bağlantısı başarılı")
            return conn
        
        except Exception as e:
            logger.error(f"❌ Firebird bağlantı hatası: {e}")
            return None
    
    def create_mysql_tenant_db(self, firma):
        """MySQL tenant database oluştur"""
        
        # DB adı oluştur (güvenli karakterler)
        firma_kod = firma.unvan[:10].upper().replace(' ', '_')
        firma_kod = ''.join(c for c in firma_kod if c.isalnum() or c == '_')
        db_name = f'erp_{firma_kod}_{firma.id[:8]}'
        
        # Root bağlantı
        root_conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_ROOT_USER,
            password=Config.MYSQL_ROOT_PASSWORD,
            charset='utf8mb4'
        )
        
        try:
            with root_conn.cursor() as cursor:
                # Database var mı kontrol et
                cursor.execute(f"SHOW DATABASES LIKE '{db_name}'")
                exists = cursor.fetchone()
                
                if exists:
                    logger.warning(f"⚠️ Database zaten var: {db_name}")
                else:
                    # Yeni database oluştur
                    cursor.execute(f"""
                        CREATE DATABASE {db_name}
                        CHARACTER SET utf8mb4
                        COLLATE utf8mb4_unicode_ci
                    """)
                    
                    # Yetkilendir
                    cursor.execute(f"""
                        GRANT ALL PRIVILEGES ON {db_name}.* 
                        TO '{Config.MYSQL_USER}'@'localhost'
                    """)
                    
                    cursor.execute("FLUSH PRIVILEGES")
                    logger.info(f"✅ MySQL tenant DB oluşturuldu: {db_name}")
            
            root_conn.commit()
            
        finally:
            root_conn.close()
        
        return db_name
    
    def connect_mysql_tenant(self, db_name):
        """MySQL tenant DB'ye bağlan"""
        
        engine = create_engine(
            f"mysql+pymysql://{Config.MYSQL_USER}:{Config.MYSQL_PASSWORD}"
            f"@{Config.MYSQL_HOST}/{db_name}?charset=utf8mb4",
            pool_pre_ping=True
        )
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info(f"✅ MySQL tenant bağlantısı: {db_name}")
        return session
    
    def create_mysql_schema(self, mysql_session):
        """MySQL'de tabloları oluştur"""
        
        # SQLAlchemy metadata'dan tabloları oluştur
        from app.modules.cari.models import CariHesap, CariHareket, CRMHareket
        
        engine = mysql_session.bind
        
        # Tabloları oluştur
        CariHesap.__table__.create(engine, checkfirst=True)
        CariHareket.__table__.create(engine, checkfirst=True)
        CRMHareket.__table__.create(engine, checkfirst=True)
        
        logger.info("✅ MySQL schema oluşturuldu")
    
    def migrate_cari_hesaplar(self, fb_conn, mysql_session, firma):
        """Cari hesapları taşı"""
        
        logger.info("📦 Cari hesaplar taşınıyor...")
        
        fb_cursor = fb_conn.cursor()
        
        # Firebird'den oku
        fb_cursor.execute("""
            SELECT 
                ID, KOD, UNVAN, VERGI_NO, VERGI_DAIRESI, TC_KIMLIK_NO,
                ADRES, SEHIR_ID, ILCE_ID, TELEFON, EPOSTA, WEB_SITE,
                DOVIZ_TURU, BORC_BAKIYE, ALACAK_BAKIYE, BAKIYE,
                RISK_LIMITI, RISK_DURUMU, AKTIF, CARI_TIPI, SEKTOR,
                ILK_SIPARIS_TARIHI, SON_SIPARIS_TARIHI, TOPLAM_SIPARIS_SAYISI,
                TOPLAM_CIRO, ENLEM, BOYLAM, CREATED_AT, UPDATED_AT
            FROM CARI_HESAPLAR
            WHERE FIRMA_ID = ?
        """, (firma.id,))
        
        count = 0
        
        for row in fb_cursor.fetchall():
            try:
                cari = CariHesap()
                
                # ID dönüşümü (Firebird UUID → MySQL CHAR(36))
                cari.id = str(row[0]).strip() if row[0] else None
                cari.firma_id = str(firma.id)
                
                # Temel bilgiler
                cari.kod = row[1]
                cari.unvan = row[2]
                cari.vergi_no = row[3]
                cari.vergi_dairesi = row[4]
                cari.tc_kimlik_no = row[5]
                
                # Adres
                cari.adres = row[6]
                cari.sehir_id = str(row[7]) if row[7] else None
                cari.ilce_id = str(row[8]) if row[8] else None
                cari.telefon = row[9]
                cari.eposta = row[10]
                cari.web_site = row[11]
                
                # Finansal
                cari.doviz_turu = row[12] or 'TL'
                cari.borc_bakiye = Decimal(str(row[13] or 0))
                cari.alacak_bakiye = Decimal(str(row[14] or 0))
                cari.bakiye = Decimal(str(row[15] or 0))
                
                # Risk
                cari.risk_limiti = Decimal(str(row[16] or 0))
                cari.risk_durumu = row[17] or 'NORMAL'
                
                # Diğer
                cari.aktif = bool(row[18])
                cari.cari_tipi = row[19] or 'BIREYSEL'
                cari.sektor = row[20]
                
                # Tarihler
                cari.ilk_siparis_tarihi = row[21]
                cari.son_siparis_tarihi = row[22]
                cari.toplam_siparis_sayisi = row[23] or 0
                cari.toplam_ciro = Decimal(str(row[24] or 0))
                
                # Lokasyon
                cari.enlem = Decimal(str(row[25])) if row[25] else None
                cari.boylam = Decimal(str(row[26])) if row[26] else None
                
                # Timestamp
                cari.created_at = row[27]
                cari.updated_at = row[28]
                
                mysql_session.add(cari)
                count += 1
                
                # Her 100 kayıtta commit (performans)
                if count % 100 == 0:
                    mysql_session.commit()
                    logger.info(f"  ⏳ {count} cari işlendi...")
            
            except Exception as e:
                logger.error(f"❌ Cari taşıma hatası (Kod: {row[1]}): {e}")
                self.errors.append({
                    'type': 'cari_hesap',
                    'kod': row[1],
                    'error': str(e)
                })
        
        mysql_session.commit()
        return count
    
    def migrate_cari_hareketler(self, fb_conn, mysql_session, firma):
        """Cari hareketleri taşı"""
        
        logger.info("📦 Cari hareketler taşınıyor...")
        
        fb_cursor = fb_conn.cursor()
        
        fb_cursor.execute("""
            SELECT 
                ID, CARI_ID, DONEM_ID, SUBE_ID, TARIH, VADE_TARIHI,
                ISLEM_TURU, BELGE_NO, ACIKLAMA,
                BORC, ALACAK, DOVIZ_KODU, KUR, DOVIZLI_TUTAR,
                FATURA_ID, CEK_ID, KASA_HAREKET_ID, BANKA_HAREKET_ID,
                KAYNAK_TURU, KAYNAK_ID, OLUSTURAN_ID, OLUSTURMA_TARIHI
            FROM CARI_HAREKET
            WHERE FIRMA_ID = ?
            ORDER BY TARIH
        """, (firma.id,))
        
        count = 0
        
        for row in fb_cursor.fetchall():
            try:
                hareket = CariHareket()
                
                hareket.id = str(row[0]).strip()
                hareket.firma_id = str(firma.id)
                hareket.cari_id = str(row[1]).strip()
                hareket.donem_id = str(row[2]).strip() if row[2] else None
                hareket.sube_id = str(row[3]).strip() if row[3] else None
                
                hareket.tarih = row[4]
                hareket.vade_tarihi = row[5]
                hareket.islem_turu = row[6]
                hareket.belge_no = row[7]
                hareket.aciklama = row[8]
                
                hareket.borc = Decimal(str(row[9] or 0))
                hareket.alacak = Decimal(str(row[10] or 0))
                hareket.doviz_kodu = row[11] or 'TL'
                hareket.kur = Decimal(str(row[12] or 1))
                hareket.dovizli_tutar = Decimal(str(row[13] or 0))
                
                hareket.fatura_id = str(row[14]) if row[14] else None
                hareket.cek_id = str(row[15]) if row[15] else None
                hareket.kasa_hareket_id = str(row[16]) if row[16] else None
                hareket.banka_hareket_id = str(row[17]) if row[17] else None
                
                hareket.kaynak_turu = row[18]
                hareket.kaynak_id = str(row[19]) if row[19] else None
                hareket.olusturan_id = str(row[20]) if row[20] else None
                hareket.olusturma_tarihi = row[21]
                
                hareket.durum = 'ONAYLANDI'  # Varsayılan
                
                mysql_session.add(hareket)
                count += 1
                
                if count % 500 == 0:
                    mysql_session.commit()
                    logger.info(f"  ⏳ {count} hareket işlendi...")
            
            except Exception as e:
                logger.error(f"❌ Hareket taşıma hatası (Belge: {row[7]}): {e}")
                self.errors.append({
                    'type': 'cari_hareket',
                    'belge_no': row[7],
                    'error': str(e)
                })
        
        mysql_session.commit()
        return count
    
    def migrate_crm_hareketler(self, fb_conn, mysql_session, firma):
        """CRM hareketlerini taşı"""
        
        logger.info("📦 CRM kayıtları taşınıyor...")
        
        fb_cursor = fb_conn.cursor()
        
        # CRM tablosu var mı kontrol et
        try:
            fb_cursor.execute("""
                SELECT 
                    ID, CARI_ID, PLASIYER_ID, TARIH, ISLEM_TURU,
                    KONU, DETAY_NOTU, DUYGU_DURUMU
                FROM CRM_HAREKETLERI
                WHERE FIRMA_ID = ?
            """, (firma.id,))
        except:
            logger.warning("⚠️ CRM_HAREKETLERI tablosu bulunamadı, atlanıyor")
            return 0
        
        count = 0
        
        for row in fb_cursor.fetchall():
            try:
                crm = CRMHareket()
                
                crm.id = str(row[0]).strip()
                crm.firma_id = str(firma.id)
                crm.cari_id = str(row[1]).strip()
                crm.plasiyer_id = str(row[2]) if row[2] else None
                crm.tarih = row[3]
                crm.islem_turu = row[4]
                crm.konu = row[5]
                crm.detay_notu = row[6]
                crm.duygu_durumu = row[7] or 'BELİRSİZ'
                
                mysql_session.add(crm)
                count += 1
                
                if count % 200 == 0:
                    mysql_session.commit()
                    logger.info(f"  ⏳ {count} CRM kaydı işlendi...")
            
            except Exception as e:
                logger.error(f"❌ CRM taşıma hatası: {e}")
        
        mysql_session.commit()
        return count
    
    def validate_balances(self, mysql_session):
        """Bakiyeleri doğrula"""
        
        logger.info("🔍 Bakiye doğrulaması yapılıyor...")
        
        # Her cari için hareket toplamı = bakiye kontrolü
        result = mysql_session.execute(text("""
            SELECT 
                ch.id,
                ch.kod,
                ch.unvan,
                ch.bakiye,
                COALESCE(SUM(h.borc), 0) - COALESCE(SUM(h.alacak), 0) AS hesaplanan_bakiye
            FROM cari_hesaplar ch
            LEFT JOIN cari_hareket h ON h.cari_id = ch.id AND h.durum = 'ONAYLANDI'
            GROUP BY ch.id, ch.kod, ch.unvan, ch.bakiye
            HAVING ABS(ch.bakiye - hesaplanan_bakiye) > 0.01
        """))
        
        hatali = result.fetchall()
        
        if hatali:
            logger.warning(f"⚠️ {len(hatali)} caride bakiye tutarsızlığı!")
            for row in hatali[:5]:  # İlk 5'i göster
                logger.warning(f"  - {row[1]} ({row[2]}): Kayıtlı={row[3]}, Hesaplanan={row[4]}")
        else:
            logger.info("✅ Tüm bakiyeler tutarlı")
    
    def print_summary(self):
        """Migration özet raporu"""
        
        logger.info("\n" + "=" * 80)
        logger.info("MİGRATION ÖZET RAPORU")
        logger.info("=" * 80)
        logger.info(f"✅ Başarılı: {self.success_count} firma")
        logger.info(f"⏭️ Atlanan: {self.skip_count} firma")
        logger.info(f"❌ Hatalı: {len(self.errors)} kayıt")
        
        if self.errors:
            logger.error("\nHATALAR:")
            for idx, err in enumerate(self.errors[:10], 1):
                logger.error(f"{idx}. {err}")
        
        logger.info("=" * 80)


# ========================================
# KULLANIM
# ========================================
if __name__ == '__main__':
    migrator = CariMigrationService()
    migrator.migrate_all_firms()