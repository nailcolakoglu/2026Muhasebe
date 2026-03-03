# app/modules/firmalar/services.py (FULL VERSION - Event Driven & SaaS Optimized)

"""
Firma Yönetim Servisi
MySQL Tenant Database Oluşturma ve Otomatik Konfigürasyon
"""

import uuid
import logging
import os
from sqlalchemy import create_engine, text, MetaData, Table, Column
from app.extensions import db
from flask import current_app
from sqlalchemy.orm import Session
from datetime import datetime, date 

# ✨ SİNYALLER EKLENDİ
from app.signals import yeni_tenant_kuruldu

logger = logging.getLogger(__name__)

class FirmaService:
    """Firma ve Tenant Database Yönetimi"""
    
    # ========================================
    # 1. ANA FONKSİYON (Entry Point)
    # ========================================
    @staticmethod
    def firma_olustur(kod, unvan, vergi_no, admin_email=None, admin_password=None):
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
            
            # 2. USER OLUŞTUR (Master DB - users tablosu)
            admin_user = None
            password = None
            
            if admin_email:
                existing_user = db.session.query(User).filter_by(email=admin_email).first()
                
                if existing_user:
                    admin_user = existing_user
                    logger.info(f"👤 Mevcut kullanıcı bulundu: {admin_email}")
                else:
                    admin_user = User()
                    admin_user.id = str(uuid.uuid4())
                    admin_user.email = admin_email
                    admin_user.full_name = f"{unvan} Yöneticisi"
                    admin_user.is_active = True
                    admin_user.is_superadmin = False
                    
                    password = admin_password or f"{kod}123"
                    admin_user.set_password(password)
                    
                    db.session.add(admin_user)
                    db.session.flush()
                    
                    logger.info(f"👤 Yeni kullanıcı oluşturuldu: {admin_email}")
            
            # 3. USER-TENANT ROL İLİŞKİSİ
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
            
            # 6. TENANT DB'YE VARSAYILANLARI EKLE
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
            
            # ✨ 8. SİNYALİ ATEŞLE
            yeni_tenant_kuruldu.send(tenant)
            
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

    @staticmethod
    def create_tenant_database(db_name):
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"""
                    CREATE DATABASE IF NOT EXISTS `{db_name}`
                    CHARACTER SET utf8mb4
                    COLLATE utf8mb4_unicode_ci
                """))
                conn.commit()
        except Exception as e:
            logger.error(f"❌ Database oluşturma hatası: {e}")
            raise
    
    @staticmethod
    def initialize_tenant_schema(db_name):
        try:
            tenant_db_url = (
                f"mysql+pymysql://"
                f"{current_app.config['TENANT_DB_USER']}:"
                f"{current_app.config['TENANT_DB_PASSWORD']}"
                f"@{current_app.config['TENANT_DB_HOST']}:"
                f"{current_app.config['TENANT_DB_PORT']}"
                f"/{db_name}?charset=utf8mb4"
            )
            
            tenant_engine = create_engine(tenant_db_url, pool_pre_ping=True, pool_recycle=3600)
            logger.info("📦 Modeller yükleniyor...")
            
            from app.modules.lokasyon.models import Sehir, Ilce
            from app.modules.kategori.models import StokKategori
            from app.modules.bolge.models import Bolge
            from app.modules.doviz.models import DovizKuru
            from app.modules.firmalar.models import Firma, Donem, SystemMenu
            from app.modules.sube.models import Sube
            from app.modules.depo.models import Depo, DepoLokasyon, StokLokasyonBakiye
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
            
            master_tables = {
                'tenants', 'users', 'licenses', 'audit_logs', 
                'user_tenant_roles', 'backup_configs', 'master_active_sessions',
                'accounting_periods', 'workflow_definitions', 'workflow_instances'
            }
            
            no_fk_metadata = MetaData()
            fk_constraints = []
            
            for table_name, original_table in db.metadata.tables.items():
                if table_name in master_tables: continue
                
                columns = []
                for col in original_table.columns:
                    new_col = Column(
                        col.name, col.type, primary_key=col.primary_key,
                        nullable=col.nullable, unique=col.unique,
                        default=col.default, server_default=col.server_default
                    )
                    columns.append(new_col)
                
                Table(table_name, no_fk_metadata, *columns, extend_existing=True)
                
                for fk in original_table.foreign_key_constraints:
                    if fk.referred_table.name in master_tables: continue
                    fk_constraints.append({
                        'table': table_name,
                        'name': fk.name or f"fk_{table_name}_{list(fk.column_keys)[0]}"[:64],
                        'columns': list(fk.column_keys),
                        'ref_table': fk.referred_table.name,
                        'ref_columns': [elem.column.name for elem in fk.elements]
                    })
            
            no_fk_metadata.create_all(bind=tenant_engine, checkfirst=True)
            
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
                        except Exception:
                            pass
                    trans.commit()
                except Exception:
                    trans.rollback()
                    raise
            return True
            
        except Exception as e:
            logger.error(f"❌ Schema oluşturma hatası: {e}", exc_info=True)
            raise
            
    @staticmethod
    def setup_default_data(db_name, tenant_id, tenant_code, tenant_name, admin_user_id, admin_email, admin_name):
        try:
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
                
                # 1. FIRMA KAYDI
                from app.modules.firmalar.models import Firma
                firma = Firma(id=tenant_id, kod=tenant_code, unvan=tenant_name, aktif=True)
                session.add(firma)
                
                # 2. 2026 DÖNEMİ
                from app.modules.firmalar.models import Donem
                donem = Donem(
                    id=str(uuid.uuid4()), firma_id=tenant_id, yil=2026, 
                    ad="2026 Mali Dönemi", baslangic=date(2026, 1, 1), bitis=date(2026, 12, 31), aktif=True
                )
                session.add(donem)
                
                # 3. MERKEZ ŞUBE
                from app.modules.sube.models import Sube
                sube = Sube(id=str(uuid.uuid4()), firma_id=tenant_id, kod="MRK", ad="Merkez Şube", aktif=True)
                session.add(sube)
                
                # 4. ADMIN KULLANICI
                from app.modules.kullanici.models import Kullanici
                user = Kullanici(
                    id=admin_user_id, firma_id=tenant_id, email=admin_email, 
                    ad_soyad=admin_name or f"{admin_email.split('@')[0]} (Admin)", aktif=True
                )
                if hasattr(user, 'rol'): user.rol = 'admin'
                elif hasattr(user, 'role'): user.role = 'admin'
                session.add(user)
                
                # ✨ 5. MENÜ YAPISI (HATA TOLERANSLI - TRYCATCH İÇİNDE)
                try:
                    from app.modules.firmalar.models import SystemMenu
                    import json
                    
                    json_paths = [
                        os.path.join(current_app.root_path, 'data', 'menu_structure.json'),
                        os.path.join(os.path.dirname(current_app.root_path), 'menu_structure.json'),
                        'D:\\GitHup\\2026Muhasebe\\app\\data\\menu_structure.json',
                    ]
                    json_path = next((path for path in json_paths if os.path.exists(path)), None)
                    
                    if json_path:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            menu_structure = json.load(f)
                        
                        def create_menu_recursive(items, parent_id=None):
                            for item in items:
                                # ✨ DÜZELTME 1: firma_id parametresini çıkardık
                                menu = SystemMenu(
                                    id=str(uuid.uuid4()), 
                                    parent_id=parent_id,
                                    baslik=item.get('title'), 
                                    icon=item.get('icon'), 
                                    url=item.get('url', '#'), 
                                    sira=item.get('order', 0), 
                                    aktif=True
                                )
                                # Opsiyonel kolonlar (Modelde varsa ekle)
                                if hasattr(menu, 'endpoint'): menu.endpoint = item.get('endpoint')
                                if hasattr(menu, 'yetkili_roller'): menu.yetkili_roller = item.get('roles')
                                
                                session.add(menu)
                                session.flush()
                                if item.get('children', []):
                                    create_menu_recursive(item.get('children', []), parent_id=menu.id)
                        create_menu_recursive(menu_structure)
                    else:
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
                            # ✨ DÜZELTME 2: firma_id çıkarıldı
                            session.add(SystemMenu(
                                id=str(uuid.uuid4()), baslik=item['baslik'],
                                icon=item['icon'], url=item['url'], sira=item['order'], aktif=True
                            ))
                except Exception as ex:
                    logger.error(f"  ⚠️ Menü yüklenirken hata oldu (Kuruluma devam ediliyor): {ex}")
                
                # 6. HESAP PLANI (TDHP) YÜKLEMESİ
                try:
                    from app.modules.muhasebe.utils import varsayilan_hesap_planini_yukle
                    varsayilan_hesap_planini_yukle(session, tenant_id)
                    session.flush() 
                    logger.info(f"  ✅ Standart Hesap Planı (TDHP) eklendi.")
                    
                    # 7. VARSAYILAN MERKEZ KASANIN KURULUMU
                    from app.modules.muhasebe.models import HesapPlani
                    from app.modules.kasa.models import Kasa
                    
                    kasa_hesap = session.query(HesapPlani).filter_by(firma_id=tenant_id, kod='100.01').first()
                    
                    merkez_kasa = Kasa(
                        id=str(uuid.uuid4()),
                        firma_id=tenant_id,
                        sube_id=sube.id,
                        kod="KAS-MRK",
                        ad="Merkez Kasa",
                        muhasebe_hesap_id=kasa_hesap.id if kasa_hesap else None,
                        aktif=True
                    )
                    session.add(merkez_kasa)
                    logger.info(f"  ✅ Varsayılan Merkez Kasa oluşturuldu ve muhasebeye bağlandı.")
                    
                except Exception as ex:
                    logger.error(f"  ❌ TDHP veya Kasa Yükleme hatası: {ex}")
                
                # 8. KRİTİK: COMMIT!
                session.commit()
                logger.info(f"✅ Varsayılan veriler başarıyla kaydedildi: {db_name}")
            
        except Exception as e:
            logger.error(f"❌ Varsayılan veri oluşturma hatası: {e}", exc_info=True)