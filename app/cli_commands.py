# app.py (veya app/cli_commands.py)

import click
from flask import current_app
from sqlalchemy import create_engine, text
from app.extensions import db
import logging

logger = logging.getLogger(__name__)


@app.cli.command('init-tenant-schema')
@click.argument('tenant_db_name')
def init_tenant_schema(tenant_db_name):
    """
    Tenant database'ine tüm tabloları oluşturur
    
    Kullanım:
        flask init-tenant-schema erp_tenant_ABC001
    """
    
    click.echo(f"🔧 Tenant schema oluşturuluyor: {tenant_db_name}")
    
    try:
        # 1. Tenant DB URL'i oluştur
        tenant_db_url = (
            f"mysql+pymysql://{current_app.config['TENANT_DB_USER']}:"
            f"{current_app.config['TENANT_DB_PASSWORD']}"
            f"@{current_app.config['TENANT_DB_HOST']}:"
            f"{current_app.config['TENANT_DB_PORT']}"
            f"/{tenant_db_name}?charset=utf8mb4"
        )
        
        # 2. Tenant engine oluştur
        tenant_engine = create_engine(
            tenant_db_url,
            **current_app.config['SQLALCHEMY_ENGINE_OPTIONS']
        )
        
        # 3. Database bağlantısını test et
        with tenant_engine.connect() as conn:
            result = conn.execute(text("SELECT DATABASE()")).scalar()
            click.echo(f"✅ Bağlantı başarılı: {result}")
        
        # 4. Tüm tenant modellerini import et
        from app.models.tenant import Base  # Tenant modelleri
        
        # ✅ YENİ: Modelleri manuel import (lazy import sorununu çözer)
        from app.modules.banka.models import BankaHesap, BankaHareket
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
        from app.modules.stok.models import StokKart, StokPaketIcerigi, StokMuhasebeGrubu, StokKDVGrubu, StokHareket, StokDepoDurumu
        from app.modules.stok_fisi.models import StokFisi, StokFisiDetay
        from app.modules.sube.models import Sube
        
        click.echo(f"📦 {len(Base.metadata.tables)} tablo bulundu")
        
        # 5. Tabloları oluştur
        Base.metadata.create_all(bind=tenant_engine, checkfirst=True)
        
        click.echo(f"✅ Tenant schema oluşturuldu: {tenant_db_name}")
        click.echo(f"📊 Toplam tablo sayısı: {len(Base.metadata.tables)}")
        
        # 6. Oluşturulan tabloları listele
        with tenant_engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES")).fetchall()
            click.echo(f"\n📋 Oluşturulan tablolar ({len(result)} adet):")
            for row in result:
                click.echo(f"  - {row[0]}")
        
        return True
    
    except Exception as e:
        click.echo(f"❌ Hata: {e}", err=True)
        logger.exception("Tenant schema oluşturma hatası")
        return False