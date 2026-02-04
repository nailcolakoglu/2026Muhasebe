# supervisor/services/firebird_service.py

"""
Firebird Database Service (Final Sürüm)
Özellikler:
1. UUID/String Tip Zorlama (HesapPlani, Cari vb. dahil)
2. FK Oluşturma Hatasında Devam Etme (MySQL Kaydını Engellemez)
3. Varsayılan Veri Yükleme (Firma ID Eşitleme, Kullanıcı, Dönem)
4. SystemMenu Tablosu Dahil
"""

import fdb
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text, String, Integer, MetaData, Table, Column
from sqlalchemy.orm import Session
from sqlalchemy.types import Enum

# Proje kök dizinini ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.extensions import db
from app.patches import apply_firebird_patches 

class FirebirdService:
    
    def __init__(self):
        apply_firebird_patches()
        
        self.host = 'localhost'
        self.port = 3050
        self.user = 'SYSDBA'
        self.password = 'masterkey'
        self.charset = 'UTF8'
        self.db_base_path = r'D:\Firebird\Data\ERP'
        self._ensure_directories()
    
    def _ensure_directories(self):
        try:
            os.makedirs(self.db_base_path, exist_ok=True)
        except Exception as e:
            print(f"❌ Dizin oluşturma hatası: {e}")
    
    # ----------------------------------------------------------------
    # 1. DATABASE OLUŞTURMA (ANA FONKSİYON)
    # ----------------------------------------------------------------
    def create_database(self, tenant_id, tenant_code, db_name, admin_email, tenant_title):
        """
        Args:
            tenant_id: MySQL'deki Tenant UUID (Eşitleme için)
            tenant_code: Firma Kodu
            db_name: FDB dosya adı
            admin_email: Yönetici maili
            tenant_title: Firma Ünvanı
        """
        print(f"\n{'='*60}")
        print(f"🔥 Profesyonel Firebird Kurulumu...")
        print(f"   Firma Kodu: {tenant_code}")
        print(f"   Firma ID  : {tenant_id} (MySQL Eşitliği İçin)")
        print(f"   DB Dosyası: {db_name}")
        print(f"{'='*60}")
        
        try:
            db_path = os.path.join(self.db_base_path, db_name)
            
            # Temiz Kurulum
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    print(f"♻️  Eski dosya temizlendi.")
                except:
                    return {'success': False, 'message': 'Dosya kilitli, silinemedi.', 'error': 'Locked'}
            
            print(f"🆕 Boş veritabanı oluşturuluyor...")
            self._create_physical_db(db_path)
            
            print(f"📊 Tablolar ve İlişkiler İnşa Ediliyor...")
            self._sync_schema_manual(db_path)
            
            print(f"⚙️  Generators ayarlanıyor...")
            self._create_generators_triggers(db_path)

            # --- HATIRLATMA 1, 3, 4: VARSAYILAN VERİLER ---
            print(f"📝 Varsayılan Veriler (Firma, Dönem, Kullanıcı) Yükleniyor...")
            self._setup_default_data(db_path, tenant_id, tenant_code, tenant_title, admin_email)

            print(f"{'='*60}")
            print(f"✅ KURULUM BAŞARIYLA TAMAMLANDI")
            print(f"{'='*60}\n")
            
            return {'success': True, 'db_path': db_path, 'message': 'Başarılı.', 'error': None}
            
        except Exception as e:
            print(f"❌ KRİTİK HATA: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Hata oluştu', 'error': str(e)}

    # ----------------------------------------------------------------
    # 2. FİZİKSEL DOSYA
    # ----------------------------------------------------------------
    def _create_physical_db(self, db_path):
        try:
            dsn = f"{self.host}/{self.port}:{db_path}"
            con = fdb.create_database(
                f"CREATE DATABASE '{dsn}' USER '{self.user}' PASSWORD '{self.password}' PAGE_SIZE 16384 DEFAULT CHARACTER SET {self.charset}"
            )
            con.close()
        except Exception as e:
            print(f"   ❌ Dosya yaratma hatası: {e}")
            raise

    # ----------------------------------------------------------------
    # 3. ŞEMA SENKRONİZASYONU (MANUEL RECONSTRUCT)
    # ----------------------------------------------------------------
    def _sync_schema_manual(self, db_path):
        self._import_all_models()
        
        connection_string = f"firebird+firebird://{self.user}:{self.password}@{self.host}:{self.port}/{db_path}?charset={self.charset}"
        engine = create_engine(connection_string, echo=False)
        
        excluded_tables = [
            'users', 'tenants', 'licenses', 'user_tenant_roles', 
            'master_active_sessions', 'alembic_version', 'audit_logs', 'backup_configs', 'accounting_periods',
            'supervisors', 'settings', 'notifications', 'system_metrics', 'tenant_extended', 'license_extended'
        ]
        
        # Bu tablolara referans veren FK'lar kesinlikle String(36) olmalı
        uuid_tables = [
            'firmalar', 'donemler', 'subeler', 'kullanicilar', 'depolar', 'bolgeler',
            'hesap_plani', 'cari_hesaplar', 'stok_kartlari', 'menu_items' # Hatırlatma 2: MenuItems eklendi
        ]
        
        firebird_metadata = MetaData()
        deferred_fks = [] 
        
        print(f"   🔨 Tablo tanımları hazırlanıyor...")
        
        for name, original_table in db.metadata.tables.items():
            if name.lower() not in excluded_tables:
                
                new_columns = []
                for original_col in original_table.columns:
                    new_type = original_col.type
                    
                    # 1. Enum -> String
                    if isinstance(new_type, (Enum, db.Enum)) or new_type.__class__.__name__ == 'Enum':
                        new_type = String(50)
                    
                    # 2. UUID Zorlama (PK)
                    if name.lower() in uuid_tables and original_col.name.lower() == 'id':
                        if isinstance(new_type, Integer): new_type = String(36)

                    # 3. UUID Zorlama (FK)
                    is_uuid_target = False
                    if original_col.foreign_keys:
                        for fk in original_col.foreign_keys:
                            if fk.column.table.name.lower() in uuid_tables:
                                is_uuid_target = True
                    
                    # İsimden Yakalama (Garanti olsun diye)
                    if original_col.name.lower() in ['firma_id', 'donem_id', 'sube_id', 'kullanici_id', 
                                                   'depo_id', 'yonetici_id', 'hesap_id', 'cari_id', 'tedarikci_id',
                                                   'alis_hesap_id', 'satis_hesap_id', 'hedef_muhasebe_id', 'parent_id']:
                        is_uuid_target = True

                    if is_uuid_target and isinstance(new_type, Integer):
                        new_type = String(36)

                    new_col = Column(
                        original_col.name, new_type,
                        primary_key=original_col.primary_key,
                        nullable=original_col.nullable,
                        unique=original_col.unique,
                        index=original_col.index
                    )
                    new_columns.append(new_col)
                
                Table(name, firebird_metadata, *new_columns)
                
                for fk in original_table.foreign_key_constraints:
                    deferred_fks.append({
                        'table': name, 'cols': [c.name for c in fk.columns],
                        'ref_table': fk.elements[0].column.table.name,
                        'ref_col': fk.elements[0].column.name, 'name': fk.name
                    })

        print(f"   🧱 Tablolar oluşturuluyor...")
        firebird_metadata.create_all(bind=engine)
        print(f"      ✅ Tablolar oluşturuldu.")

        print(f"   🔗 İlişkiler bağlanıyor ({len(deferred_fks)} adet)...")
        with engine.connect() as conn:
            success = 0
            fail = 0
            for fk in deferred_fks:
                fk_name = fk['name'] or f"FK_{fk['table']}_{fk['cols'][0]}"[:31]
                sql = f"ALTER TABLE {fk['table']} ADD CONSTRAINT {fk_name} FOREIGN KEY ({', '.join(fk['cols'])}) REFERENCES {fk['ref_table']} ({fk['ref_col']})"
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    success += 1
                except Exception as e:
                    conn.rollback()
                    fail += 1
                    print(f"\n   ⚠️  UYARI: İlişki kurulamadı ({fk['table']} -> {fk['ref_table']})")

        print(f"      ✅ {success} ilişki kuruldu. ({fail} atlandı)")

    # ----------------------------------------------------------------
    # 4. GENERATOR / TRIGGER
    # ----------------------------------------------------------------
    def _create_generators_triggers(self, db_path):
        connection_string = f"firebird+firebird://{self.user}:{self.password}@{self.host}:{self.port}/{db_path}?charset={self.charset}"
        engine = create_engine(connection_string)
        
        # UUID Kullanan tablolarda Generator'a gerek yok
        uuid_tables = ['firmalar', 'donemler', 'subeler', 'kullanicilar', 'depolar', 
                        'AI_RAPOR_AYARLARI', 'AI_RAPOR_GECMISI',
                        'BANKA_HAREKETLERI',  'BANKA_HESAPLARI', 'BANKA_IMPORT_GECMISI', 'BANKA_IMPORT_KURALLARI', 'BANKA_IMPORT_SABLONLARI',
                        'CARI_HAREKET', 'CARI_HESAPLAR', 'CEK_SENETLER', 'CRM_HAREKETLERI', 'NTEGRATOR_AYARLARI', 'FATURALAR', 'FATURA_KALEMLERI',
                        'FINANS_ISLEMLERI', 'FIYAT_LISTELERI', 'HEDEFLER', 'ILCELER', 'IRSALIYELER', 'KASALAR', 'KASA_HAREKETLERI', 
                        'MUHASEBE_FISLERI^', 'ODEME_PLANLARI', 'SAYACLAR', 'SEHIRLER', 'SIPARISLER', 'STOK_DEPO_DURUMU',
                       'bolgeler', 'kullanici_sube_yetki', 'hesap_plani']
        
        excluded_tables = ['users', 'tenants'] # vb. Master tablolar

        with engine.connect() as conn:
            for name, table in db.metadata.tables.items():
                if name.lower() not in excluded_tables and name.lower() not in uuid_tables:
                    id_col = table.columns.get('id')
                    if id_col is not None and isinstance(id_col.type, Integer):
                        table_name = name.upper()
                        gen_name = f"GEN_{table_name}_ID"[:31]
                        try:
                            conn.execute(text(f"CREATE GENERATOR {gen_name};"))
                            conn.execute(text(f"SET GENERATOR {gen_name} TO 0;"))
                            conn.execute(text(f"CREATE OR ALTER TRIGGER TR_{table_name[:24]}_BI FOR {table_name} ACTIVE BEFORE INSERT POSITION 0 AS BEGIN IF (NEW.ID IS NULL) THEN NEW.ID = GEN_ID({gen_name}, 1); END"))
                            conn.commit()
                        except: pass

    # ----------------------------------------------------------------
    # 5. VARSAYILAN VERİLER (HATIRLATMALAR BURADA)
    # ----------------------------------------------------------------
    def _setup_default_data(self, db_path, tenant_id, tenant_code, tenant_title, admin_email):
        """
        Hatırlatma 1, 3, 4: Firma, Dönem ve Kullanıcı Ekleme
        """
        from app.modules.firmalar.models import Firma, Donem
        from app.modules.kullanici.models import Kullanici
        
        connection_string = f"firebird+firebird://{self.user}:{self.password}@{self.host}:{self.port}/{db_path}?charset={self.charset}"
        engine = create_engine(connection_string)
        
        with Session(engine) as session:
            # 1. Firma (MySQL ID ile Eşit)
            print(f"      + Firma Ekleniyor: {tenant_id}")
            firma = Firma(
                id=tenant_id, # MySQL'den gelen UUID
                kod=tenant_code,
                unvan=tenant_title,
                aktif=True
            )
            session.add(firma)
            
            # 2. Dönem (2026)
            print(f"      + Dönem Ekleniyor: 2026")
            # Donem ID'si otomatik UUID olacak (Modelde default tanımlı)
            donem = Donem(
                firma_id=tenant_id,
                yil=2026,
                ad="2026 Mali Dönemi",
                baslangic=datetime(2026, 1, 1),
                bitis=datetime(2026, 12, 31),
                aktif=True
            )
            session.add(donem)
            
            # 3. Kullanıcı (Admin)
            # MySQL'de oluşturulan Admin kullanıcısının ID'sini buraya eşitleyebilirsin
            # Şimdilik sabit bir UUID veriyorum veya MySQL'den parametre olarak alabilirsin.
            admin_uuid = "550e8400-e29b-41d4-a716-446655440000" 
            print(f"      + Kullanıcı Ekleniyor: {admin_email}")
            user = Kullanici(
                id=admin_uuid,
                firma_id=tenant_id,
                email=admin_email,
                ad_soyad="Sistem Yöneticisi",
                aktif=True,
                rol='admin'
            )
            session.add(user)
            
            session.commit()
            print(f"      ✅ Varsayılan veriler işlendi.")

    def _import_all_models(self):
        try:
            from app.modules.stok.models import StokKart
            from app.modules.cari.models import CariHesap
            from app.modules.fatura.models import Fatura
            from app.modules.firmalar.models import Firma, SystemMenu # Hatırlatma 2: SystemMenu
            from app.modules.kasa.models import Kasa
            from app.modules.muhasebe.models import MuhasebeFisi, HesapPlani
            from app.modules.cek.models import CekSenet
            from app.modules.banka_hareket.models import BankaHareket
            from app.modules.siparis.models import Siparis
            from app.modules.depo.models import Depo
            from app.modules.kategori.models import StokKategori
            from app.modules.kullanici.models import Kullanici
            from app.modules.sube.models import Sube
            from app.modules.bolge.models import Bolge
            from app.modules.banka_import.models import BankaImportKurali
        except ImportError as e:
            print(f"⚠️ Model import uyarısı: {e}")

    def test_connection(self, db_path):
        try:
            con = fdb.connect(host=self.host, database=db_path, user=self.user, password=self.password, charset=self.charset)
            con.close()
            return True
        except:
            return False