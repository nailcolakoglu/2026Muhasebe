# app/modules/firmalar/services.py (FULL VERSION)

"""
Firma Yönetim Servisi
MySQL Tenant Database Oluşturma
"""

import uuid
import logging
import os
from sqlalchemy import create_engine, text, MetaData, Table, Column
from app.extensions import db
from flask import current_app
from sqlalchemy.orm import Session
from datetime import datetime, date 

logger = logging.getLogger(__name__)


class FirmaService:
    """Firma ve Tenant Database Yönetimi"""
    
    # ========================================
    # 1. ANA FONKSİYON (Entry Point)
    # ========================================
    @staticmethod
    def firma_olustur(kod, unvan, vergi_no, admin_email=None, admin_password=None):
        """
        Yeni firma oluştur ve MySQL tenant DB'sini hazırla
        
        Args:
            kod: Firma kodu (örn: ABC001)
            unvan: Ticari ünvan
            vergi_no: Vergi numarası
            admin_email: Admin email (opsiyonel)
            admin_password: Admin şifre (opsiyonel)
        
        Returns:
            Tuple[bool, str, Tenant]: (Başarı durumu, Mesaj, Tenant objesi)
        """
        from app.models.master import Tenant, User, UserTenantRole
        from werkzeug.security import generate_password_hash
        
        try:
            # 1. Tenant kaydı oluştur (Master DB)
            tenant = Tenant()
            tenant.id = str(uuid.uuid4())
            tenant.kod = kod.upper().strip()
            tenant.unvan = unvan.strip()
            tenant.vergi_no = vergi_no.strip()
            tenant.db_name = f"erp_tenant_{tenant.kod}"
            tenant.is_active = True
            
            db.session.add(tenant)
            db.session.flush()
            
            logger.info(f"📝 Tenant kaydı oluşturuldu: {tenant.kod}")
            
            # ✅ 2. USER OLUŞTUR (Master DB - users tablosu)
            admin_user = None
            password = None
            
            if admin_email:
                # Email zaten var mı kontrol et
                existing_user = db.session.query(User).filter_by(email=admin_email).first()
                
                if existing_user:
                    admin_user = existing_user
                    logger.info(f"👤 Mevcut kullanıcı bulundu: {admin_email}")
                else:
                    # Yeni user oluştur
                    admin_user = User()
                    admin_user.id = str(uuid.uuid4())
                    admin_user.email = admin_email
                    admin_user.full_name = f"{unvan} Yöneticisi"
                    admin_user.is_active = True
                    admin_user.is_superadmin = False
                    
                    # Şifre belirle
                    password = admin_password or f"{kod}123"
                    admin_user.set_password(password)
                    
                    db.session.add(admin_user)
                    db.session.flush()
                    
                    logger.info(f"👤 Yeni kullanıcı oluşturuldu: {admin_email}")
            
            # ✅ 3. USER-TENANT ROL İLİŞKİSİ (Master DB - user_tenant_roles tablosu)
            if admin_user:
                existing_role = db.session.query(UserTenantRole).filter_by(
                    user_id=admin_user.id,
                    tenant_id=tenant.id
                ).first()
                
                if not existing_role:
                    user_role = UserTenantRole()
                    user_role.id = str(uuid.uuid4())
                    user_role.user_id = admin_user.id
                    user_role.tenant_id = tenant.id
                    user_role.role = 'admin'
                    user_role.is_default = True
                    user_role.is_active = True
                    
                    db.session.add(user_role)
                    
                    logger.info(f"🔐 User-Tenant ilişkisi oluşturuldu: {admin_email} -> {tenant.kod} (admin)")
            
            # 4. MySQL'de database oluştur
            FirmaService.create_tenant_database(tenant.db_name)
            
            # 5. Tabloları oluştur
            FirmaService.initialize_tenant_schema(tenant.db_name)
            
            # ✅ 6. TENANT DB'YE DE KULLANICI EKLE (Tenant DB - kullanicilar tablosu)
            if admin_user:
                FirmaService.setup_default_data(
                    db_name=tenant.db_name,
                    tenant_id=tenant.id,
                    tenant_code=tenant.kod,
                    tenant_name=tenant.unvan,
                    admin_user_id=admin_user.id,
                    admin_email=admin_user.email,
                    admin_name=admin_user.full_name
                )
                
            # 7. Başarılı, commit et
            db.session.commit()
            
            logger.info(f"✅ Firma başarıyla oluşturuldu: {tenant.kod} ({tenant.db_name})")
            
            # Şifre bilgisini döndür
            if admin_user and admin_email and password:
                mesaj = f"Firma başarıyla oluşturuldu: {tenant.unvan}\n\n"
                mesaj += f"👤 Admin Email: {admin_email}\n"
                mesaj += f"🔑 Şifre: {password}"
            else:
                mesaj = f"Firma başarıyla oluşturuldu: {tenant.unvan}"
            
            return True, mesaj, tenant
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Firma oluşturma hatası: {e}", exc_info=True)
            return False, f"Hata: {str(e)}", None
  


    # ✅ YENİ FONKSİYON: Tenant DB'ye Kullanıcı Ekle
    @staticmethod
    def create_tenant_user(db_name, user_id, email, full_name, firma_id):
        """
        Tenant DB'ye kullanıcı ekle (ORM ile - Güvenli!)
        
        Args:
            db_name: Tenant DB adı (örn: erp_tenant_ABC001)
            user_id: Master DB'deki user ID (UUID)
            email: Email
            full_name: Ad Soyad
            firma_id: Firma ID (tenant_id)
        """
        try:
            from app.modules.kullanici.models import Kullanici
            
            # Tenant DB URL
            tenant_db_url = (
                f"mysql+pymysql://"
                f"{current_app.config['TENANT_DB_USER']}:"
                f"{current_app.config['TENANT_DB_PASSWORD']}"
                f"@{current_app.config['TENANT_DB_HOST']}:"
                f"{current_app.config['TENANT_DB_PORT']}"
                f"/{db_name}?charset=utf8mb4"
            )
            
            tenant_engine = create_engine(tenant_db_url)
            
            # ✅ ORM ile kullanıcı oluştur
            with Session(tenant_engine) as session:
                # Zaten var mı kontrol et
                existing = session.query(Kullanici).filter_by(id=user_id).first()
                
                if existing:
                    logger.info(f"⚠️ Kullanıcı zaten var: {email}")
                    return
                
                user = Kullanici()
                user.id = user_id  # Master DB ile aynı ID
                user.firma_id = firma_id
                user.email = email
                user.ad_soyad = full_name or f"{email.split('@')[0]} (Admin)"
                user.aktif = True
                
                # ✅ Rol kolonu varsa set et (dinamik)
                if hasattr(user, 'rol'):
                    user.rol = 'admin'
                elif hasattr(user, 'role'):
                    user.role = 'admin'
                elif hasattr(user, 'user_role'):
                    user.user_role = 'admin'
                
                session.add(user)
                session.commit()
            
            logger.info(f"👤 Tenant DB'ye kullanıcı eklendi: {email}")
            
        except Exception as e:
            logger.error(f"❌ Tenant user oluşturma hatası: {e}", exc_info=True)
            # Kritik değil, devam et
    
    
    # ========================================
    # 2. DATABASE OLUŞTURMA (BOŞ DB)
    # ========================================
    @staticmethod
    def create_tenant_database(db_name):
        """
        MySQL'de yeni tenant database oluştur (BOŞ!)
        
        Args:
            db_name: Database adı (örn: erp_tenant_TEST002)
        """
        
        try:
            # Master DB connection'ı kullan
            with db.engine.connect() as conn:
                # Database oluştur
                conn.execute(text(f"""
                    CREATE DATABASE IF NOT EXISTS `{db_name}`
                    CHARACTER SET utf8mb4
                    COLLATE utf8mb4_unicode_ci
                """))
                
                conn.commit()
            
            logger.info(f"✅ Database oluşturuldu: {db_name}")
            
        except Exception as e:
            logger.error(f"❌ Database oluşturma hatası: {e}")
            raise
    
    
    # ========================================
    # 3. TABLO OLUŞTURMA (SCHEMA)
    # ========================================
    @staticmethod
    def initialize_tenant_schema(db_name):
        """
        Tenant DB'sine tabloları ekle
        
        Args:
            db_name: Database adı (örn: erp_tenant_TEST002)
        
        Strateji:
        1. Önce FK'sız tablolar oluştur
        2. Sonra FK'ları ALTER TABLE ile ekle
        """
        
        try:
            # 1. Tenant DB URL oluştur
            tenant_db_url = (
                f"mysql+pymysql://"
                f"{current_app.config['TENANT_DB_USER']}:"
                f"{current_app.config['TENANT_DB_PASSWORD']}"
                f"@{current_app.config['TENANT_DB_HOST']}:"
                f"{current_app.config['TENANT_DB_PORT']}"
                f"/{db_name}?charset=utf8mb4"
            )
            
            logger.info(f"🔗 Bağlantı başlatılıyor...")
            
            # 2. Tenant engine oluştur
            tenant_engine = create_engine(
                tenant_db_url,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # 3. Bağlantıyı test et
            with tenant_engine.connect() as conn:
                result = conn.execute(text("SELECT DATABASE()")).scalar()
                logger.info(f"✅ Bağlantı başarılı: {result}")
            
            # 4. ✅ MODELLERI IMPORT ET
            logger.info("📦 Modeller yükleniyor...")
            
            from app.modules.lokasyon.models import Sehir, Ilce
            from app.modules.kategori.models import StokKategori
            from app.modules.bolge.models import Bolge
            from app.modules.doviz.models import DovizKuru
            from app.modules.firmalar.models import Firma, Donem, SystemMenu
            from app.modules.sube.models import Sube
            from app.modules.depo.models import Depo
            from app.modules.kasa.models import Kasa
            from app.modules.kullanici.models import Kullanici
            from app.modules.cari.models import CariHesap, CariHareket, CRMHareket
            from app.modules.stok.models import (
                StokMuhasebeGrubu, StokKDVGrubu, StokKart, 
                StokPaketIcerigi, StokHareketi, StokDepoDurumu
            )
            from app.modules.banka.models import BankaHesap
            from app.modules.banka_hareket.models import BankaHareket
            from app.modules.banka_import.models import BankaImportSablon, BankaImportKurali, BankaImportGecmisi
            from app.modules.kasa_hareket.models import KasaHareket
            from app.modules.cek.models import CekSenet
            from app.modules.fiyat.models import FiyatListesi, FiyatListesiDetay
            from app.modules.siparis.models import OdemePlani, Siparis, SiparisDetay
            from app.modules.irsaliye.models import Irsaliye, IrsaliyeKalemi
            from app.modules.fatura.models import Fatura, FaturaKalemi
            from app.modules.stok_fisi.models import StokFisi, StokFisiDetay
            from app.modules.muhasebe.models import HesapPlani, MuhasebeFisi, MuhasebeFisiDetay
            from app.modules.finans.models import FinansIslem
            from app.modules.efatura.models import EntegratorAyarlari
            from app.modules.rapor.models import YazdirmaSablonu, SavedReport
            
            logger.info(f"✅ Modeller yüklendi")
            
            # 5. ✅ MASTER TABLOLARI FİLTRELE
            master_tables = {
                'tenants', 'users', 'licenses', 'audit_logs', 
                'user_tenant_roles', 'backup_configs', 'master_active_sessions',
                'accounting_periods', 'workflow_definitions', 'workflow_instances'
            }
            
            # 6. ✅ YENİ METADATA OLUŞTUR (FK'SIZ!)
            no_fk_metadata = MetaData()
            fk_constraints = []
            
            for table_name, original_table in db.metadata.tables.items():
                if table_name in master_tables:
                    continue
                
                columns = []
                for col in original_table.columns:
                    new_col = Column(
                        col.name,
                        col.type,
                        primary_key=col.primary_key,
                        nullable=col.nullable,
                        unique=col.unique,
                        default=col.default,
                        server_default=col.server_default
                    )
                    columns.append(new_col)
                
                Table(table_name, no_fk_metadata, *columns, extend_existing=True)
                
                for fk in original_table.foreign_key_constraints:
                    if fk.referred_table.name in master_tables:
                        continue
                    
                    fk_constraints.append({
                        'table': table_name,
                        'name': fk.name or f"fk_{table_name}_{list(fk.column_keys)[0]}"[:64],
                        'columns': list(fk.column_keys),
                        'ref_table': fk.referred_table.name,
                        'ref_columns': [elem.column.name for elem in fk.elements]
                    })
            
            logger.info(f"📊 Oluşturulacak tablo sayısı: {len(no_fk_metadata.tables)}")
            
            # 7. ✅ TABOOLARI OLUŞTUR (FK'SIZ)
            logger.info("🔧 Tablolar oluşturuluyor...")
            
            no_fk_metadata.create_all(bind=tenant_engine, checkfirst=True)
            
            logger.info(f"✅ {len(no_fk_metadata.tables)} tablo oluşturuldu")
            
            # 8. ✅ FK'LARI EKLE
            logger.info(f"🔗 Foreign key'ler ekleniyor ({len(fk_constraints)} adet)...")
            
            success_count = 0
            fail_count = 0
            
            with tenant_engine.connect() as conn:
                trans = conn.begin()
                
                try:
                    for fk in fk_constraints:
                        try:
                            sql = text(f"""
                                ALTER TABLE {fk['table']} 
                                ADD CONSTRAINT {fk['name']} 
                                FOREIGN KEY ({', '.join(fk['columns'])}) 
                                REFERENCES {fk['ref_table']} ({', '.join(fk['ref_columns'])})
                            """)
                            
                            conn.execute(sql)
                            success_count += 1
                            
                        except Exception:
                            fail_count += 1
                    
                    trans.commit()
                    
                except Exception as e:
                    trans.rollback()
                    raise
            
            logger.info(f"✅ {success_count} FK eklendi, {fail_count} atlandı")
            
            # 9. ✅ SON KONTROL
            with tenant_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db"), 
                    {'db': db_name}
                ).scalar()
                
                logger.info(f"✅ Tenant schema oluşturuldu: {db_name}")
                logger.info(f"📊 Toplam tablo sayısı: {result}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Schema oluşturma hatası: {e}", exc_info=True)
            raise
            
    
    # ✅ YENİ FONKSİYON: Varsayılan Verileri Ekle
    @staticmethod
    def setup_default_data(db_name, tenant_id, tenant_code, tenant_name, admin_user_id, admin_email, admin_name):
        """
        Tenant DB'ye varsayılan verileri ekle
        
        Eklenecekler:
        1. Firma kaydı
        2. 2026 Dönemi
        3. Merkez Şube
        4. Admin Kullanıcı
        5. Menü Yapısı (JSON'dan veya basit)
        """
        try:
            # Tenant DB URL
            tenant_db_url = (
                f"mysql+pymysql://"
                f"{current_app.config['TENANT_DB_USER']}:"
                f"{current_app.config['TENANT_DB_PASSWORD']}"
                f"@{current_app.config['TENANT_DB_HOST']}:"
                f"{current_app.config['TENANT_DB_PORT']}"
                f"/{db_name}?charset=utf8mb4"
            )
            
            tenant_engine = create_engine(tenant_db_url)
            
            with Session(tenant_engine) as session:
                
                # ✅ 1. FIRMA KAYDI
                from app.modules.firmalar.models import Firma
                
                firma = Firma()
                firma.id = tenant_id
                firma.kod = tenant_code
                firma.unvan = tenant_name
                firma.aktif = True
                
                session.add(firma)
                logger.info(f"  ✅ Firma kaydı eklendi: {tenant_code}")
                
                # ✅ 2. 2026 DÖNEMİ
                from app.modules.firmalar.models import Donem
                
                donem = Donem()
                donem.id = str(uuid.uuid4())
                donem.firma_id = tenant_id
                donem.yil = 2026
                donem.ad = "2026 Mali Dönemi"
                donem.baslangic = date(2026, 1, 1)
                donem.bitis = date(2026, 12, 31)
                donem.aktif = True
                
                session.add(donem)
                logger.info(f"  ✅ Dönem eklendi: 2026")
                
                # ✅ 3. MERKEZ ŞUBE
                from app.modules.sube.models import Sube
                
                sube = Sube()
                sube.id = str(uuid.uuid4())
                sube.firma_id = tenant_id
                sube.kod = "MRK"
                sube.ad = "Merkez Şube"
                sube.aktif = True
                
                session.add(sube)
                logger.info(f"  ✅ Şube eklendi: Merkez")
                
                # ✅ 4. ADMIN KULLANICI
                from app.modules.kullanici.models import Kullanici
                
                user = Kullanici()
                user.id = admin_user_id
                user.firma_id = tenant_id
                user.email = admin_email
                user.ad_soyad = admin_name or f"{admin_email.split('@')[0]} (Admin)"
                user.aktif = True
                
                if hasattr(user, 'rol'):
                    user.rol = 'admin'
                elif hasattr(user, 'role'):
                    user.role = 'admin'
                
                session.add(user)
                logger.info(f"  ✅ Kullanıcı eklendi: {admin_email}")
                
                # ✅ 5. MENÜ YAPISI
                from app.modules.firmalar.models import SystemMenu
                import json
                import os
                
                # JSON yollarını sırası ile dene
                json_paths = [
                    os.path.join(current_app.root_path, 'data', 'menu_structure.json'),  # app/data/
                    os.path.join(os.path.dirname(current_app.root_path), 'menu_structure.json'),  # Proje root
                    'D:\\GitHup\\2026Muhasebe\\menu_structure.json',  # Mutlak yol
                ]
                
                json_path = None
                for path in json_paths:
                    if os.path.exists(path):
                        json_path = path
                        break
                
                if json_path:
                    logger.info(f"  📄 Menü JSON'u bulundu: {json_path}")
                    
                    with open(json_path, 'r', encoding='utf-8') as f:
                        menu_structure = json.load(f)
                    
                    def create_menu_recursive(items, parent_id=None):
                        """Menüleri recursive olarak oluştur"""
                        count = 0
                        
                        for item in items:
                            menu = SystemMenu()
                            menu.id = str(uuid.uuid4())
                            menu.firma_id = tenant_id
                            menu.parent_id = parent_id
                            menu.baslik = item.get('title')
                            menu.icon = item.get('icon')
                            menu.endpoint = item.get('endpoint')
                            menu.url = item.get('url', '#')
                            menu.yetkili_roller = item.get('roles')
                            menu.sira = item.get('order', 0)
                            menu.aktif = True
                            
                            session.add(menu)
                            session.flush()
                            count += 1
                            
                            # Alt menüler
                            children = item.get('children', [])
                            if children:
                                child_count = create_menu_recursive(children, parent_id=menu.id)
                                count += child_count
                        
                        return count
                    
                    total_menus = create_menu_recursive(menu_structure)
                    logger.info(f"  ✅ Menü yapısı eklendi: {total_menus} öğe (JSON)")
                
                else:
                    logger.warning(f"  ⚠️ Menü JSON'u bulunamadı! Denenen yollar:")
                    for path in json_paths:
                        logger.warning(f"    - {path}")
                    
                    logger.info(f"  📝 Basit menü yapısı oluşturuluyor...")
                    
                    # Fallback: Basit menü
                    simple_menus = [
                        {'baslik': 'Dashboard', 'icon': 'bi bi-speedometer2', 'url': '/', 'order': 1},
                        {'baslik': 'Satış', 'icon': 'bi bi-cart3', 'url': '#', 'order': 2},
                        {'baslik': 'Stok', 'icon': 'bi bi-box-seam', 'url': '#', 'order': 3},
                        {'baslik': 'Cari', 'icon': 'bi bi-people', 'url': '/cari', 'order': 4},
                        {'baslik': 'Finans', 'icon': 'bi bi-wallet2', 'url': '#', 'order': 5},
                        {'baslik': 'Muhasebe', 'icon': 'bi bi-journal-bookmark-fill', 'url': '#', 'order': 6},
                        {'baslik': 'Raporlar', 'icon': 'bi bi-graph-up', 'url': '/rapor', 'order': 7},
                        {'baslik': 'Sistem', 'icon': 'bi bi-gear-fill', 'url': '#', 'order': 8},
                    ]
                    
                    for item in simple_menus:
                        menu = SystemMenu()
                        menu.id = str(uuid.uuid4())
                        menu.firma_id = tenant_id
                        menu.baslik = item['baslik']
                        menu.icon = item['icon']
                        menu.url = item['url']
                        menu.sira = item['order']
                        menu.aktif = True
                        
                        session.add(menu)
                    
                    logger.info(f"  ✅ Basit menü yapısı eklendi: {len(simple_menus)} öğe")
                
                # ✅ 6. KRİTİK: COMMIT!
                session.commit()
                logger.info(f"✅ Varsayılan veriler kaydedildi: {db_name}")
            
        except Exception as e:
            logger.error(f"❌ Varsayılan veri oluşturma hatası: {e}", exc_info=True)
            # Kritik değil, devam et

