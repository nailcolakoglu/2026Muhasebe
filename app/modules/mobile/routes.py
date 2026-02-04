# Gerekli Importlar
from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.modules.fatura.models import Fatura, FaturaKalemi
from app.modules.stok.models import StokKart, StokDepoDurumu, StokHareketi
from app.modules.cari.models import CariHesap
from app.modules.kasa_hareket.models import KasaHareket
from app.modules.cek.models import CekSenet
from app.modules.depo.models import Depo
from app.modules.sube.models import Sube
from app.modules.kasa.models import Kasa
from app.modules.firmalar.models import Donem
from app.enums import BankaIslemTuru, FaturaTuru, HareketTuru
import traceback

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
    # Depo Kontrolü
    depo = Depo.query.filter_by(plasiyer_id=current_user.id).first()
    
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
                ad = Donem.query.filter_by(firma_id=current_user.firma_id, aktif=True).first()
                if ad: donem_id = ad.id
                else:
                    sd = Donem.query.filter_by(firma_id=current_user.firma_id).order_by(Donem.id.desc()).first()
                    if sd: donem_id = sd.id
            
            if not donem_id:
                raise Exception("Aktif Mali Dönem bulunamadı! Lütfen Masaüstünden Dönem oluşturun.")

            # Fatura Başlığı
            fatura = Fatura(
                firma_id=current_user.firma_id,
                donem_id=donem_id,
                sube_id=depo.sube_id,
                cari_id=cari_id,
                depo_id=depo.id,
                fatura_turu=FaturaTuru.SATIS.value,
                belge_no=f"MOB-{datetime.now().strftime('%y%m%d%H%M%S')}",
                tarih=date.today(),
                aciklama="Mobil Sıcak Satış",
                durum='onayli'
            )
            
            db.session.add(fatura)
            db.session.flush()
            print(f">>> Fatura Başlığı Eklendi.ID: {fatura.id}")
            
            toplam_tutar = Decimal(0)
            
            for i in range(len(stok_ids)):
                if not stok_ids[i] or not miktarlar[i]: continue
                
                stok = StokKart.query.get(stok_ids[i])
                miktar = Decimal(miktarlar[i])
                tutar = miktar * stok.satis_fiyat
                
                # --- DÜZELTME BURADA YAPILDI ---
                # 'tutar=tutar' parametresi silindi, çünkü modelde bu sütun yok.
                # Doğrusu 'satir_toplami=tutar' dır.
                kalem = FaturaKalemi(
                    fatura_id=fatura.id,
                    stok_id=stok.id,
                    miktar=miktar,
                    birim_fiyat=stok.satis_fiyat,
                    # tutar=tutar,  <-- BU SATIR HATALIYDI VE SİLİNDİ
                    satir_toplami=tutar, # Doğru alan bu
                    kdv_orani=stok.kdv_orani or 20
                )
                db.session.add(kalem)
                toplam_tutar += tutar
                
                # Stok Hareketi
                sh = StokHareketi(
                    firma_id=current_user.firma_id,
                    donem_id=donem_id,
                    sube_id=depo.sube_id,
                    stok_id=stok.id,
                    hareket_turu=HareketTuru.SATIS.value,
                    miktar=miktar,
                    cikis_depo_id=depo.id,
                    tarih=date.today(),
                    aciklama=f"Mobil Satış: {fatura.belge_no}"
                )
                db.session.add(sh)
                
                # Depo Bakiyesi Düş
                sd = StokDepoDurumu.query.filter_by(depo_id=depo.id, stok_id=stok.id).first()
                if sd: 
                    sd.miktar -= miktar
                    db.session.add(sd)

            fatura.genel_toplam = toplam_tutar
            fatura.ara_toplam = toplam_tutar
            
            # Cari Güncelle
            cari = CariHesap.query.get(cari_id)
            cari.borc_bakiye = (cari.borc_bakiye or 0) + toplam_tutar
            db.session.add(cari)
            
            db.session.commit()
            print(">>> ✅ COMMIT BAŞARILI!")
            
            return jsonify({'success': True, 'fatura_id': fatura.id, 'message': 'Satış başarıyla kaydedildi.'})
            
        except Exception as e:
            db.session.rollback()
            print(f">>> ❌ HATA: {str(e)}")
            traceback.print_exc()
            return jsonify({'success': False, 'message': f"Sistem Hatası: {str(e)}"})

    # GET İŞLEMİ
    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
    arac_stoklari = db.session.query(StokKart, StokDepoDurumu.miktar)\
        .join(StokDepoDurumu, StokDepoDurumu.stok_id == StokKart.id)\
        .filter(StokDepoDurumu.depo_id == depo.id, StokDepoDurumu.miktar > 0).all()
        
    return render_template('mobile/satis.html', cariler=cariler, stoklar=arac_stoklari, depo_var=True)

# ...(tahsilat ve diğer rotalar aynı kalacak) ...
@mobile_bp.route('/tahsilat', methods=['GET', 'POST'])
@login_required
def tahsilat():
    # Tahsilat kodları buraya gelecek (önceki kodun aynısı)
    if request.method == 'POST':
        try:
            tutar = Decimal(request.form.get('tutar'))
            tur = request.form.get('tur') 
            cari_id = request.form.get('cari_id')
            vade_tarihi = request.form.get('vade_tarihi')
            
            donem_id = session.get('aktif_donem_id')
            if not donem_id:
                ad = Donem.query.filter_by(firma_id=current_user.firma_id, aktif=True).first()
                donem_id = ad.id if ad else None

            if tur == 'NAKIT':
                kasa = Kasa.query.filter_by(firma_id=current_user.firma_id).first()
                kasa_id = kasa.id if kasa else 1 

                kh = KasaHareket(
                    firma_id=current_user.firma_id,
                    donem_id=donem_id,
                    kasa_id=kasa_id,
                    cari_id=cari_id,
                    islem_turu=BankaIslemTuru.TAHSILAT.value,
                    tarih=date.today(),
                    tutar=tutar,
                    plasiyer_id=current_user.id,
                    onaylandi=False, 
                    belge_no=f"MTH-{datetime.now().strftime('%H%M%S')}",
                    aciklama="Mobil Tahsilat"
                )
                db.session.add(kh)
            
            elif tur in ['CEK', 'SENET']:
                vade_date = datetime.strptime(vade_tarihi, '%Y-%m-%d').date() if vade_tarihi else date.today()
                cek = CekSenet(
                    firma_id=current_user.firma_id,
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
                db.session.add(cek)
            
            cari = CariHesap.query.get(cari_id)
            cari.alacak_bakiye = (cari.alacak_bakiye or 0) + tutar
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Tahsilat alındı.'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})

    cariler = CariHesap.query.filter_by(firma_id=current_user.firma_id).all()
    return render_template('mobile/tahsilat.html', cariler=cariler)

@mobile_bp.route('/arac-stok')
@login_required
def arac_stok():
    depo = Depo.query.filter_by(plasiyer_id=current_user.id).first()
    if not depo: return render_template('mobile/error.html', message="Araç deposu bulunamadı.")
    stoklar = db.session.query(StokKart, StokDepoDurumu.miktar).join(StokDepoDurumu).filter(StokDepoDurumu.depo_id == depo.id, StokDepoDurumu.miktar > 0).all()
    return render_template('mobile/arac_stok.html', stoklar=stoklar)

@mobile_bp.route('/yazdir/<int:fatura_id>')
@login_required
def yazdir(fatura_id):
    fatura = Fatura.query.get_or_404(fatura_id)
    return render_template('mobile/fis_yazdir.html', fatura=fatura, now_time=datetime.now().strftime('%H:%M'))