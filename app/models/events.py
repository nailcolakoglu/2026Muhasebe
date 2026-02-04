# models/events.py (YENİ DOSYA)

"""
SQLAlchemy Event Listeners
"""

from sqlalchemy import event
from app.models.base import db

def setup_event_listeners():
    """Tüm event listener'ları kaydet"""
    
    # Lazy import (circular dependency önleme)
    from models import (
        Fatura, CariHesap, StokHareketi, 
        StokDepoDurumu, FaturaKalemi, FinansIslem
    )
    from araclar import hesapla_ve_guncelle_ortalama_odeme
    
    # 1.Cari istatistik güncelleme
    @event.listens_for(Fatura, 'after_insert')
    def fatura_sonrasi_cari_guncelle(mapper, connection, target):
        if target.fatura_turu != 'satis':
            return
        
        from datetime import datetime
        islem_tarihi = datetime.combine(target.tarih, datetime.min.time()) \
            if isinstance(target.tarih, type(datetime.now().date())) else target.tarih
        islem_tutari = target.genel_toplam or 0
        
        cari_table = CariHesap.__table__
        
        connection.execute(
            cari_table.update()
            .where(cari_table.c.id == target.cari_id)
            .where(
                (cari_table.c.ilk_siparis_tarihi.is_(None)) | 
                (cari_table.c.ilk_siparis_tarihi > islem_tarihi)
            )
            .values(ilk_siparis_tarihi=islem_tarihi)
        )
        
        connection.execute(
            cari_table.update()
            .where(cari_table.c.id == target.cari_id)
            .where(
                (cari_table.c.son_siparis_tarihi.is_(None)) | 
                (cari_table.c.son_siparis_tarihi < islem_tarihi)
            )
            .values(son_siparis_tarihi=islem_tarihi)
        )
        
        connection.execute(
            cari_table.update()
            .where(cari_table.c.id == target.cari_id)
            .values(
                toplam_siparis_sayisi=cari_table.c.toplam_siparis_sayisi + 1,
                toplam_ciro=cari_table.c.toplam_ciro + islem_tutari
            )
        )
    
    # 2.Tahsilat sonrası ortalama ödeme güncelleme
    @event.listens_for(FinansIslem, 'after_insert')
    def tahsilat_sonrasi(mapper, connection, target):
        if target.islem_turu == 'tahsilat':
            try:
                hesapla_ve_guncelle_ortalama_odeme(target.cari_id)
            except: 
                pass
    
    # 3.Fatura gün adı güncelleme
    @event.listens_for(Fatura, 'before_insert')
    @event.listens_for(Fatura, 'before_update')
    def fatura_gun_adi_guncelle(mapper, connection, target):
        if target.tarih: 
            gunler = {
                0: 'Pazartesi', 1: 'Salı', 2: 'Çarşamba',
                3: 'Perşembe', 4: 'Cuma', 5: 'Cumartesi', 6: 'Pazar'
            }
            target.gun_adi = gunler.get(target.tarih.weekday())
    
    # 4.Fatura kalemi sıra no
    @event.listens_for(FaturaKalemi, 'before_insert')
    def otomatik_sira_no(mapper, connection, target):
        if not target.fatura_id or (target.sira_no and target.sira_no > 1):
            return
        
        from sqlalchemy import select, func
        tablo = target.__table__
        
        sorgu = select(func.max(tablo.c.sira_no)).where(
            tablo.c.fatura_id == target.fatura_id
        )
        
        mevcut_max = connection.execute(sorgu).scalar()
        target.sira_no = (mevcut_max + 1) if mevcut_max else 1
    
    # 5.Stok bakiye güncelleme
    @event.listens_for(StokHareketi, 'after_insert')
    def stok_bakiye_guncelle(mapper, connection, target):
        stok_depo_table = StokDepoDurumu.__table__
        
        if target.giris_depo_id:
            result = connection.execute(
                stok_depo_table.update()
                .where(stok_depo_table.c.firma_id == target.firma_id)
                .where(stok_depo_table.c.depo_id == target.giris_depo_id)
                .where(stok_depo_table.c.stok_id == target.stok_id)
                .values(miktar=stok_depo_table.c.miktar + target.miktar)
            )
            if result.rowcount == 0:
                connection.execute(
                    stok_depo_table.insert().values(
                        firma_id=target.firma_id,
                        depo_id=target.giris_depo_id,
                        stok_id=target.stok_id,
                        miktar=target.miktar
                    )
                )
        
        if target.cikis_depo_id: 
            result = connection.execute(
                stok_depo_table.update()
                .where(stok_depo_table.c.firma_id == target.firma_id)
                .where(stok_depo_table.c.depo_id == target.cikis_depo_id)
                .where(stok_depo_table.c.stok_id == target.stok_id)
                .values(miktar=stok_depo_table.c.miktar - target.miktar)
            )
            if result.rowcount == 0:
                connection.execute(
                    stok_depo_table.insert().values(
                        firma_id=target.firma_id,
                        depo_id=target.cikis_depo_id,
                        stok_id=target.stok_id,
                        miktar=-target.miktar
                    )
                )
    
    # 6.Stok hareketi silme
    @event.listens_for(StokHareketi, 'before_delete')
    def stok_hareketi_silme(mapper, connection, target):
        stok_table = StokDepoDurumu.__table__
        miktar = float(target.miktar or 0)
        
        if target.cikis_depo_id: 
            connection.execute(
                stok_table.update()
                .where(stok_table.c.depo_id == target.cikis_depo_id)
                .where(stok_table.c.stok_id == target.stok_id)
                .values(miktar=stok_table.c.miktar + miktar)
            )
        
        if target.giris_depo_id:
            connection.execute(
                stok_table.update()
                .where(stok_table.c.depo_id == target.giris_depo_id)
                .where(stok_table.c.stok_id == target.stok_id)
                .values(miktar=stok_table.c.miktar - miktar)
            )
    
    print("✅ Event listeners kayıt edildi")