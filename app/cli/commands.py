# cli/commands.py

import sys
import os

# Import fix (çifte garanti)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import click
from flask import current_app
from datetime import datetime

# Artık import çalışacak
from araclar import hesapla_ve_guncelle_ortalama_odeme, toplu_ortalama_odeme_hesapla
from models import db, CariHesap, Firma


@click.group()
def cari_cli():
    """Cari hesap yönetim komutları"""
    pass


@cari_cli.command('hesapla-odemeler')
@click.option('--firma-id', '-f', type=int, help='Sadece belirli bir firmayı işle')
@click.option('--limit', '-l', type=int, help='İşlenecek maksimum cari sayısı')
@click.option('--cari-id', '-c', type=int, help='Sadece tek bir cariyi işle')
@click.option('--verbose', '-v', is_flag=True, help='Detaylı çıktı')
def hesapla_odemeler(firma_id, limit, cari_id, verbose):
    """Cari hesapların ortalama ödeme günlerini hesaplar"""
    
    click.echo("=" * 60)
    click.echo("📊 CARİ ÖDEME ANALİZİ BAŞLATILIYOR...")
    click.echo("=" * 60)
    
    # TEKİL CARİ
    if cari_id: 
        click.echo(f"\n🔍 Cari ID {cari_id} işleniyor...")
        
        cari = db.session.get(CariHesap, cari_id)
        if not cari:
            click.echo(f"❌ Cari bulunamadı: {cari_id}", err=True)
            return
        
        sonuc = hesapla_ve_guncelle_ortalama_odeme(cari_id)
        
        if sonuc['success']:
            click.echo(f"✅ Başarılı!  Ortalama:  {sonuc['ortalama_gun']} gün")
        else:
            click.echo(f"❌ Hata: {sonuc.get('error')}", err=True)
        
        return
    
    # TOPLU İŞLEM
    click.echo("\n🔄 Toplu hesaplama başlatılıyor...")
    
    query = CariHesap.query.filter_by(aktif=True)
    
    if firma_id:
        query = query.filter_by(firma_id=firma_id)
    
    if limit:
        query = query.limit(limit)
    
    cariler = query.all()
    
    if not cariler: 
        click.echo("⚠️ İşlenecek cari bulunamadı!")
        return
    
    basarili = 0
    basarisiz = 0
    
    with click.progressbar(cariler, label='İşleniyor') as bar:
        for cari in bar:
            sonuc = hesapla_ve_guncelle_ortalama_odeme(cari.id)
            if sonuc['success']:
                basarili += 1
            else:
                basarisiz += 1
    
    click.echo(f"\n✅ Başarılı: {basarili}")
    click.echo(f"❌ Başarısız: {basarisiz}")