# app/modules/banka_import/routes.py

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db 
from app.modules.banka_hareket.models import BankaHareket
from app.modules.banka.models import BankaHesap
from app.modules.banka_import.models import BankaImportSablon, BankaImportGecmisi, BankaImportKurali
from .engine import BankaImportEngine
from app.enums import BankaIslemTuru
from .forms import BankaImportKuraliForm, BankaImportForm, BankaImportSablonForm

# 👇 DÜZELTME 1: Yeni Servis Sınıflarını Import Ediyoruz
from app.modules.banka_hareket.services import BankaService
from app.modules.muhasebe.services import MuhasebeEntegrasyonService

banka_import_bp = Blueprint('banka_import', __name__)

@banka_import_bp.route('/yukle', methods=['GET', 'POST'])
@login_required
def yukle():
    form = BankaImportForm()

    if request.method == 'POST':
        # API isteği olduğu için form.validate_on_submit() yerine manuel kontrol
        if 'file' not in request.files:
            return jsonify({'error': 'Dosya seçilmedi'}), 400
            
        file = request.files['file']
        banka_id = request.form.get('banka_id')
        sablon_id = request.form.get('sablon_id')
        
        # Motoru Başlat
        engine = BankaImportEngine(current_user.firma_id)
        
        # 1.Mükerrer Kontrolü (Dosya Bazlı)
        file_hash = engine.dosya_hash_hesapla(file)
        gecmis = engine.mukerrer_dosya_kontrol(file_hash)
        if gecmis:
            return jsonify({'error': f"Bu dosya daha önce {gecmis.yukleme_tarihi.strftime('%d.%m.%Y')} tarihinde yüklenmiş!"}), 400
            
        # 2.Excel'i İşle
        sablon = BankaImportSablon.query.get(sablon_id)
        if not sablon:
             return jsonify({'error': 'Şablon bulunamadı.'}), 400

        try:
            veriler = engine.excel_oku_ve_isle(file, sablon)
            return jsonify({
                'success': True, 
                'data': veriler, 
                'file_hash': file_hash,
                'count': len(veriler)
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # GET İsteği (Sayfa Açılışı)
    bankalar = BankaHesap.query.filter_by(firma_id=current_user.firma_id).all()
    sablonlar = BankaImportSablon.query.filter_by(firma_id=current_user.firma_id).all()
    
    return render_template('banka_import/yukle.html', form=form, bankalar=bankalar, sablonlar=sablonlar)

@banka_import_bp.route('/kaydet', methods=['POST'])
@login_required
def kaydet():
    data = request.json
    satirlar = data.get('satirlar', [])
    banka_id = data.get('banka_id')
    file_hash = data.get('file_hash')
    
    if not satirlar: return jsonify({'error': 'Veri yok'}), 400
    
    kaydedilen = 0
    yeni_kural_sayisi = 0
    
    for row in satirlar:
        # 1.Mükerrer Kontrolü (Satır Bazlı)
        criteria = {
            'banka_id': banka_id,
            'tarih': row['tarih'],
            'tutar': row['tutar']
        }
        if row.get('belge_no'):
            criteria['belge_no'] = row['belge_no']
        else:
            criteria['aciklama'] = row['aciklama']

        exists = BankaHareket.query.filter_by(**criteria).first()
        if exists: continue 
        
        # 2.İşlemi Kaydet (Banka Hareket)
        islem_turu = BankaIslemTuru.TAHSILAT.value if row['yon'] == 'giris' else BankaIslemTuru.TEDIYE.value
        
        hareket = BankaHareket(
            firma_id=current_user.firma_id,
            donem_id=current_user.firma.donemler[-1].id,
            banka_id=banka_id,
            tarih=row['tarih'],
            belge_no=row.get('belge_no'),
            aciklama=row['aciklama'],
            tutar=row['tutar'],
            islem_turu=islem_turu,
            
            # POS Bilgileri
            brut_tutar=row.get('brut_tutar', 0),
            komisyon_tutari=row.get('komisyon_tutari', 0),
            komisyon_orani=row.get('komisyon_orani', 0),
            komisyon_hesap_id=row.get('komisyon_hesap_id')
        )
        
        # Hedef Atama
        if row.get('target_type') == 'cari':
            hareket.cari_id = row['target_id']
        elif row.get('target_type') == 'muhasebe':
            # Muhasebe kodunu serviste yöneteceğiz
            pass 

        db.session.add(hareket)
        db.session.flush() # ID al
        
        # 👇 DÜZELTME 2: Yeni Servis Metotlarını Kullanıyoruz
        if hareket.cari_id:
            # BankaService içindeki entegrasyon metodunu çağırıyoruz
            # Not: Bu metot 'private' (_) olsa da import işlemi için burada kullanabiliriz 
            # veya BankaService.islem_kaydet metodunu kullanabilirdik ama burada toplu işlem var.
            BankaService._entegre_cari(hareket)
        
        # Muhasebe Entegrasyonu
        MuhasebeEntegrasyonService.entegre_et_banka(hareket.id)
        
        # --- OTOMATİK KURAL OLUŞTURMA ---
        save_rule = row.get('save_rule', False)
        match_key = row.get('match_key')
        
        if save_rule and match_key:
            kural_var = BankaImportKurali.query.filter_by(
                firma_id=current_user.firma_id, 
                anahtar_kelime=match_key
            ).first()
            
            if not kural_var:
                yeni_kural = BankaImportKurali(
                    firma_id=current_user.firma_id,
                    anahtar_kelime=match_key,
                    kural_tipi='standart',
                    hedef_turu=row['target_type'],
                    hedef_cari_id=row['target_id'] if row['target_type'] == 'cari' else None,
                    hedef_muhasebe_id=row['target_id'] if row['target_type'] == 'muhasebe' else None,
                    aciklama_sablonu="Otomatik Öğrenildi (Excel Import)"
                )
                db.session.add(yeni_kural)
                yeni_kural_sayisi += 1

        kaydedilen += 1

    # 👇 DÜZELTME 3: Bakiye Güncelleme Servisi
    BankaService.bakiye_guncelle(banka_id)
    
    gecmis = BankaImportGecmisi(
        firma_id=current_user.firma_id,
        banka_id=banka_id,
        dosya_hash=file_hash,
        satir_sayisi=kaydedilen,
        kullanici_id=current_user.id
    )
    db.session.add(gecmis)
    db.session.commit()
    
    msg = f'{kaydedilen} adet işlem aktarıldı.'
    if yeni_kural_sayisi > 0:
        msg += f' Ayrıca {yeni_kural_sayisi} adet yeni kural otomatik öğrenildi.'
        
    return jsonify({'success': True, 'message': msg})

# --- DİĞER ROTALAR (Sablonlar, Kurallar vb.) ---
# Bu kısımlarda değişiklik yapılmasına gerek yoktur, olduğu gibi kalabilir.
# Ancak import hatası almamak için `BankaImportSablonForm` vb.formların
# yukarıda import edildiğinden emin olun.

@banka_import_bp.route('/sablonlar', methods=['GET', 'POST'])
@login_required
def sablonlar():
    form = BankaImportSablonForm()
    
    if form.validate_on_submit():
        try:
            sablon = BankaImportSablon(
                firma_id=current_user.firma_id,
                banka_adi=form.banka_adi.data,
                baslangic_satiri=form.baslangic_satiri.data,
                col_tarih=form.col_tarih.data,
                col_aciklama=form.col_aciklama.data,
                col_belge_no=form.col_belge_no.data,
                tutar_yapis_tipi=form.tutar_yapis_tipi.data,
                col_tutar=form.col_tutar.data,
                col_borc=form.col_borc.data,
                col_alacak=form.col_alacak.data,
                tarih_formati=form.tarih_formati.data
            )
            db.session.add(sablon)
            db.session.commit()
            flash("Şablon başarıyla kaydedildi.", "success")
            return redirect(url_for('banka_import.sablonlar'))
        except Exception as e:
            db.session.rollback()
            flash(f"Hata: {str(e)}", "danger")

    sablonlar_listesi = BankaImportSablon.query.filter_by(firma_id=current_user.firma_id).all()
    return render_template('banka_import/sablonlar.html', form=form, sablonlar=sablonlar_listesi)

@banka_import_bp.route('/sablon-sil/<int:id>', methods=['POST'])
@login_required
def sablon_sil(id):
    sablon = BankaImportSablon.query.get_or_404(id)
    if sablon.firma_id != current_user.firma_id:
        return jsonify({'success': False, 'message': 'Yetkisiz'}), 403
    db.session.delete(sablon)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Şablon silindi'})

@banka_import_bp.route('/kurallar', methods=['GET', 'POST'])
@login_required
def kurallar():
    form = BankaImportKuraliForm()
    if form.validate_on_submit():
        try:
            kural = BankaImportKurali(
                firma_id=current_user.firma_id,
                anahtar_kelime=form.anahtar_kelime.data,
                kural_tipi=form.kural_tipi.data,
                hedef_turu=form.hedef_turu.data,
                hedef_cari_id=form.hedef_cari_id.data if form.hedef_turu.data == 'cari' else None,
                hedef_muhasebe_id=form.hedef_muhasebe_id.data if form.hedef_turu.data == 'muhasebe' else None,
                varsayilan_komisyon_orani=form.varsayilan_komisyon_orani.data,
                komisyon_gider_hesap_id=form.komisyon_gider_hesap_id.data
            )
            db.session.add(kural)
            db.session.commit()
            flash("Kural eklendi.", "success")
            return redirect(url_for('banka_import.kurallar'))
        except Exception as e:
            db.session.rollback()
            flash(f"Hata: {str(e)}", "danger")

    kurallar_listesi = BankaImportKurali.query.filter_by(firma_id=current_user.firma_id).all()
    return render_template('banka_import/kurallar.html', form=form, kurallar=kurallar_listesi)

@banka_import_bp.route('/kural-sil/<int:id>', methods=['POST'])
@login_required
def kural_sil(id):
    kural = BankaImportKurali.query.get_or_404(id)
    if kural.firma_id != current_user.firma_id:
        return jsonify({'success': False}), 403
    db.session.delete(kural)
    db.session.commit()
    return jsonify({'success': True})