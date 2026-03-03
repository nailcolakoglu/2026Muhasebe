# app/modules/mobile/routes.py

# Gerekli Importlar
from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import get_tenant_db # ✨ KESİN KURAL: Multi-tenant DB Session
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.stok.models import StokKart, StokDepoDurumu, StokHareketi
from app.modules.cari.models import CariHesap
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.cek.models import CekSenet
from app.modules.depo.models import Depo
from app.modules.sube.models import Sube
from app.modules.kasa.models import Kasa
from app.modules.firmalar.models import Donem
from app.enums import BankaIslemTuru, FaturaTuru, HareketTuru, CariIslemTuru
import traceback

# ✨ Servis Importları (Arka Plan Otomasyonları İçin)
from app.modules.cari.services import CariService
from app.modules.muhasebe.services import MuhasebeEntegrasyonService

mobile_bp = Blueprint('mobile', __name__)

@mobile_bp.before_request
def check_plasiyer_context():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

@mobile_bp.route('/')
@login_required
def dashboard():
    return render_template('mobile/dashboard.html')

@mobile_bp.route('/sicak-satis', methods=['GET', 'POST'])
@login_required
def sicak_satis():
    tenant_db = get_tenant_db()
    
    # Depo Kontrolü
    depo = tenant_db.query(Depo).filter_by(plasiyer_id=str(current_user.id)).first()
    
    if not depo: 
        if request.method == 'POST':
            return jsonify({'success': False, 'message': 'HATA: Size tanımlı Araç Deposu yok! Yöneticiye bildirin.'})
        return render_template('mobile/error.html', message="Size tanımlı bir Araç Deposu bulunamadı! Lütfen yönetici ile görüşün.")
    
    if request.method == 'POST':
        try:
            print(">>> [POST] Kayıt İşlemi Başlıyor...")
            
            cari_id = request.form.get('cari_id')
            stok_ids = request.form.getlist('stok_id[]')
            miktarlar = request.form.getlist('miktar[]')

            # Dönem ID Belirle
            donem_id = session.get('aktif_donem_id')
            if not donem_id:
                ad = tenant_db.query(Donem).filter_by(firma_id=str(current_user.firma_id), aktif=True).first()
                if ad: donem_id = str(ad.id)
                else:
                    sd = tenant_db.query(Donem).filter_by(firma_id=str(current_user.firma_id)).order_by(Donem.id.desc()).first()
                    if sd: donem_id = str(sd.id)
            
            if not donem_id:
                raise Exception("Aktif Mali Dönem bulunamadı! Lütfen Masaüstünden Dönem oluşturun.")

            # 1. Fatura Başlığı
            fatura = Fatura(
                firma_id=str(current_user.firma_id),
                donem_id=donem_id,
                sube_id=str(depo.sube_id),
                cari_id=str(cari_id),
                depo_id=str(depo.id),
                fatura_turu=FaturaTuru.SATIS.value,
                belge_no=f"MOB-{datetime.now().strftime('%y%m%d%H%M%S')}",
                tarih=date.today(),
                aciklama="Mobil Sıcak Satış",
                durum='ONAYLANDI'
            )
            
            tenant_db.add(fatura)
            tenant_db.flush()
            
            toplam_tutar = Decimal('0.00')
            
            # 2. Kalemler ve Stok Hareketleri
            for i in range(len(stok_ids)):
                if not stok_ids[i] or not miktarlar[i]: continue
                
                stok = tenant_db.query(StokKart).get(str(stok_ids[i]))
                if not stok: continue
                
                miktar = Decimal(str(miktarlar[i]))
                tutar = miktar * Decimal(str(stok.satis_fiyati or 0))
                
                kalem = FaturaKalemi(
                    fatura_id=str(fatura.id),
                    stok_id=str(stok.id),
                    miktar=miktar,
                    birim_fiyat=stok.satis_fiyati,
                    satir_toplami=tutar,
                    net_tutar=tutar, # KDV'siz basitleştirilmiş senaryo (istersen geliştirebilirsin)
                    kdv_orani=Decimal('20.00')
                )
                tenant_db.add(kalem)
                toplam_tutar += tutar
                
                tenant_db.flush() # Kalem ID oluşsun
                
                # Stok Hareketi (Bunu eklediğimiz an `listeners.py` otomatik depodan malı düşecek!)
                sh = StokHareketi(
                    firma_id=str(current_user.firma_id),
                    donem_id=donem_id,
                    sube_id=str(depo.sube_id),
                    stok_id=str(stok.id),
                    hareket_turu=HareketTuru.SATIS.value,
                    miktar=miktar,
                    cikis_depo_id=str(depo.id),
                    tarih=date.today(),
                    kaynak_turu='fatura',
                    kaynak_id=str(fatura.id),
                    kaynak_belge_detay_id=str(kalem.id),
                    aciklama=f"Mobil Satış: {fatura.belge_no}"
                )
                tenant_db.add(sh)

            fatura.genel_toplam = toplam_tutar
            fatura.ara_toplam = toplam_tutar
            
            # 3. Cari Ekstresine İşle (Çok Önemli!)
            CariService.hareket_ekle(
                cari_id=str(cari_id),
                islem_turu=CariIslemTuru.FATURA,
                belge_no=fatura.belge_no,
                tarih=fatura.tarih,
                aciklama="Mobil Sıcak Satış Faturası",
                borc=toplam_tutar,
                alacak=Decimal('0.00'),
                kaynak_ref={'tur': 'fatura', 'id': str(fatura.id)},
                donem_id=donem_id,
                sube_id=str(depo.sube_id),
                tenant_db=tenant_db
            )
            
            tenant_db.commit()
            
            # 4. Muhasebe Yevmiye Fişini Kes
            MuhasebeEntegrasyonService.entegre_et_fatura(str(fatura.id))
            
            return jsonify({'success': True, 'fatura_id': str(fatura.id), 'message': 'Satış başarıyla kaydedildi.'})
            
        except Exception as e:
            tenant_db.rollback()
            print(f">>> ❌ HATA: {str(e)}")
            traceback.print_exc()
            return jsonify({'success': False, 'message': f"Sistem Hatası: {str(e)}"})

    # GET İŞLEMİ
    #cariler = tenant_db.query(CariHesap).filter_by(firma_id=str(current_user.firma_id)).all()
    cariler = []
    arac_stoklari = tenant_db.query(StokKart, StokDepoDurumu.miktar)\
        .join(StokDepoDurumu, StokDepoDurumu.stok_id == StokKart.id)\
        .filter(StokDepoDurumu.depo_id == str(depo.id), StokDepoDurumu.miktar > 0).all()
        
    return render_template('mobile/satis.html', cariler=cariler, stoklar=arac_stoklari, depo_var=True)


@mobile_bp.route('/tahsilat', methods=['GET', 'POST'])
@login_required
def tahsilat():
    tenant_db = get_tenant_db()
    
    if request.method == 'POST':
        try:
            tutar = Decimal(request.form.get('tutar'))
            tur = request.form.get('tur') 
            cari_id = str(request.form.get('cari_id'))
            vade_tarihi = request.form.get('vade_tarihi')
            
            donem_id = session.get('aktif_donem_id')
            if not donem_id:
                ad = tenant_db.query(Donem).filter_by(firma_id=str(current_user.firma_id), aktif=True).first()
                donem_id = str(ad.id) if ad else None

            if tur == 'NAKIT':
                kasa = tenant_db.query(Kasa).filter_by(firma_id=str(current_user.firma_id)).first()
                if not kasa: raise Exception("Sistemde tanımlı bir Kasa bulunamadı!")

                kh = KasaHareket(
                    firma_id=str(current_user.firma_id),
                    donem_id=donem_id,
                    kasa_id=str(kasa.id),
                    cari_id=cari_id,
                    islem_turu=BankaIslemTuru.TAHSILAT.value,
                    tarih=date.today(),
                    tutar=tutar,
                    plasiyer_id=str(current_user.id),
                    onaylandi=True, 
                    belge_no=f"MTH-{datetime.now().strftime('%H%M%S')}",
                    aciklama="Mobil Tahsilat"
                )
                tenant_db.add(kh)
                tenant_db.flush()
                
                # Cari Ekstreye Ekle
                CariService.hareket_ekle(
                    cari_id=cari_id, islem_turu=CariIslemTuru.TAHSILAT,
                    belge_no=kh.belge_no, tarih=kh.tarih, aciklama="Mobil Nakit Tahsilat",
                    borc=Decimal('0.00'), alacak=tutar,
                    kaynak_ref={'tur': 'kasa', 'id': str(kh.id)},
                    donem_id=donem_id, tenant_db=tenant_db
                )
                
                tenant_db.commit()
                # Muhasebeye İşle
                MuhasebeEntegrasyonService.entegre_et_kasa(str(kh.id))
            
            elif tur in ['CEK', 'SENET']:
                vade_date = datetime.strptime(vade_tarihi, '%Y-%m-%d').date() if vade_tarihi else date.today()
                cek = CekSenet(
                    firma_id=str(current_user.firma_id),
                    cari_id=cari_id,
                    tur=tur,
                    yon='ALINAN',
                    vade_tarihi=vade_date,
                    tarih=date.today(),
                    tutar=tutar,
                    durum='PORTFOY',
                    aciklama="Mobil Evrak Alımı",
                    portfoy_no=f"MP-{datetime.now().strftime('%H%M%S')}"
                )
                tenant_db.add(cek)
                tenant_db.flush()
                
                # Cari Ekstreye Ekle
                CariService.hareket_ekle(
                    cari_id=cari_id, islem_turu=CariIslemTuru.CEK_GIRIS,
                    belge_no=cek.cek_no or cek.portfoy_no, tarih=cek.tarih, aciklama=f"Mobil {tur} Alımı",
                    borc=Decimal('0.00'), alacak=tutar,
                    kaynak_ref={'tur': 'cek', 'id': str(cek.id)},
                    donem_id=donem_id, tenant_db=tenant_db
                )
                
                tenant_db.commit()
                # Muhasebeye İşle
                MuhasebeEntegrasyonService.entegre_et_cek(str(cek.id), 'giris')
            
            return jsonify({'success': True, 'message': 'Tahsilat başarıyla alındı ve deftere işlendi.'})
            
        except Exception as e:
            tenant_db.rollback()
            return jsonify({'success': False, 'message': str(e)})

    #cariler = tenant_db.query(CariHesap).filter_by(firma_id=str(current_user.firma_id)).all()
    cariler =[]
    return render_template('mobile/tahsilat.html', cariler=cariler)

@mobile_bp.route('/arac-stok')
@login_required
def arac_stok():
    tenant_db = get_tenant_db()
    depo = tenant_db.query(Depo).filter_by(plasiyer_id=str(current_user.id)).first()
    if not depo: return render_template('mobile/error.html', message="Araç deposu bulunamadı.")
    
    stoklar = tenant_db.query(StokKart, StokDepoDurumu.miktar).join(StokDepoDurumu).filter(
        StokDepoDurumu.depo_id == str(depo.id), 
        StokDepoDurumu.miktar > 0
    ).all()
    
    return render_template('mobile/arac_stok.html', stoklar=stoklar)

# ✨ UUID UYUMU: <int:fatura_id> -> <string:fatura_id>
@mobile_bp.route('/yazdir/<string:fatura_id>')
@login_required
def yazdir(fatura_id):
    tenant_db = get_tenant_db()
    fatura = tenant_db.query(Fatura).get(str(fatura_id))
    if not fatura: return render_template('mobile/error.html', message="Fatura Bulunamadı"), 404
    
    return render_template('mobile/fis_yazdir.html', fatura=fatura, now_time=datetime.now().strftime('%H:%M'))