# app/modules/depo/routes.py

from app.modules.stok.models import StokKart, StokHareketi
from app.modules.depo.models import Depo, DepoLokasyon, StokLokasyonBakiye
from app.enums import HareketTuru
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify, redirect, flash, url_for
from flask_login import login_required, current_user
from app.extensions import get_tenant_db
from app.form_builder import DataGrid
from .forms import create_depo_form

depo_bp = Blueprint('depo', __name__)

@depo_bp.route('/')
@login_required
def index():
    tenant_db = get_tenant_db()
    if not tenant_db:
        flash("Veritabanı bağlantısı yok.", "danger")
        return redirect('/')

    grid = DataGrid("depo_list", Depo, "Depo Listesi")
    
    grid.add_column('kod', 'Kod', sortable=True)
    grid.add_column('ad', 'Ad')
    grid.add_column('sube.ad', 'Şube')
    grid.add_column('plasiyer.ad_soyad', 'Depo Sorumlusu') 
    #grid.add_column('aktif', 'Durum', type='switch')
    
    grid.add_action('edit', 'Düzenle', 'bi bi-pencil', 'btn-outline-primary btn-sm', 'route', 'depo.duzenle')
    grid.add_action('delete', 'Sil', 'bi bi-trash', 'btn-outline-danger btn-sm', 'ajax', 'depo.sil')
    
    # Gizlenecek kolonlar
    hidden_cols = [
        'id', 'firma_id', 'sube_id', 'plasiyer_id',
        'created_at', 'updated_at',
        'deleted_at', 'deleted_by', 
    ]
    
    for col in hidden_cols:
        grid.hide_column(col)


    
    # FirmaFilteredQuery zaten filtreliyor, firma_id=1 yazmaya gerek yok!
    query = tenant_db.query(Depo).order_by(Depo.ad)
    grid.process_query(query)
    
    return render_template('depo/index.html', grid=grid)

@depo_bp.route('/ekle', methods=['GET', 'POST'])
@login_required
def ekle():
    form = create_depo_form()
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            tenant_db = get_tenant_db()
            try:
                data = form.get_data()
                
                # Plasiyer ID '0' veya boş gelirse None yap
                p_id = data.get('plasiyer_id')
                if not p_id or str(p_id) == '0': p_id = None
                
                depo = Depo(
                    firma_id=current_user.firma_id, # Tenant UUID Atandı
                    kod=data['kod'],
                    ad=data['ad'],
                    sube_id=data['sube_id'] if data.get('sube_id') else None,
                    plasiyer_id=p_id,
                    aktif=str(data.get('aktif')).lower() in ['true', '1', 'on']
                )
                
                tenant_db.add(depo)
                
                # ... depo nesnesi atandıktan ve tenant_db.add(depo) yapıldıktan sonra ...
                tenant_db.flush() # UUID'yi garantilemek için veritabanına bir vuruyoruz
                
                # --- WMS LOKASYON İŞLEMLERİ BAŞLANGIÇ ---
                lokasyon_kodlari = request.form.getlist('lokasyon_kod[]')
                lokasyon_adlari = request.form.getlist('lokasyon_ad[]')
                lokasyon_barkodlari = request.form.getlist('lokasyon_barkod[]')
                lokasyon_kapasiteleri = request.form.getlist('lokasyon_kapasite[]')
                
                # Mevcut lokasyonları koduna göre indexle
                mevcut_lokasyonlar = {l.kod: l for l in depo.lokasyonlar} if hasattr(depo, 'lokasyonlar') else {}
                islenen_kodlar = []
                
                for i in range(len(lokasyon_kodlari)):
                    lk_kod = lokasyon_kodlari[i].strip()
                    if not lk_kod: continue
                    
                    lk_ad = lokasyon_adlari[i] if i < len(lokasyon_adlari) else ''
                    lk_barkod = lokasyon_barkodlari[i] if i < len(lokasyon_barkodlari) and lokasyon_barkodlari[i] else None
                    lk_kapasite = lokasyon_kapasiteleri[i] if i < len(lokasyon_kapasiteleri) and lokasyon_kapasiteleri[i] else None
                    
                    if lk_kod in mevcut_lokasyonlar:
                        # Zaten var olan raf, sadece güncelle
                        lok = mevcut_lokasyonlar[lk_kod]
                        lok.ad = lk_ad
                        lok.barkod = lk_barkod
                        lok.tasima_kapasitesi_kg = lk_kapasite
                    else:
                        # Yepyeni bir raf ekleniyor
                        lok = DepoLokasyon(
                            firma_id=current_user.firma_id,
                            depo_id=depo.id,
                            kod=lk_kod,
                            ad=lk_ad,
                            barkod=lk_barkod,
                            tasima_kapasitesi_kg=lk_kapasite
                        )
                        tenant_db.add(lok)
                    
                    islenen_kodlar.append(lk_kod)
                    
                # Ekranda silinmiş olan rafları veritabanından da sil
                for kod, lok in mevcut_lokasyonlar.items():
                    if kod not in islenen_kodlar:
                        tenant_db.delete(lok)
                # --- WMS LOKASYON İŞLEMLERİ BİTİŞ ---

                tenant_db.commit() # Tüm işlemleri onayla
              
                return jsonify({'success': True, 'message': 'Depo eklendi.', 'redirect': url_for('depo.index')})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('base_form.html', form=form)

# DİKKAT: int:id yerine string:id oldu
@depo_bp.route('/duzenle/<string:id>', methods=['GET', 'POST'])
@login_required
def duzenle(id):
    tenant_db = get_tenant_db()
    depo = tenant_db.get(Depo, str(id))
    if not depo: return redirect(url_for('depo.index'))

    form = create_depo_form(depo)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                p_id = data.get('plasiyer_id')
                if not p_id or str(p_id) == '0': p_id = None
                
                depo.kod = data['kod']
                depo.ad = data['ad']
                depo.sube_id = data['sube_id'] if data.get('sube_id') else None
                depo.plasiyer_id = p_id
                depo.aktif = str(data.get('aktif')).lower() in ['true', '1', 'on']

                tenant_db.flush() # UUID'yi garantilemek için veritabanına bir vuruyoruz
                
                # --- WMS LOKASYON İŞLEMLERİ BAŞLANGIÇ ---
                lokasyon_kodlari = request.form.getlist('lokasyon_kod[]')
                lokasyon_adlari = request.form.getlist('lokasyon_ad[]')
                lokasyon_barkodlari = request.form.getlist('lokasyon_barkod[]')
                lokasyon_kapasiteleri = request.form.getlist('lokasyon_kapasite[]')
                
                # Mevcut lokasyonları koduna göre indexle
                mevcut_lokasyonlar = {l.kod: l for l in depo.lokasyonlar} if hasattr(depo, 'lokasyonlar') else {}
                islenen_kodlar = []
                
                for i in range(len(lokasyon_kodlari)):
                    lk_kod = lokasyon_kodlari[i].strip()
                    if not lk_kod: continue
                    
                    lk_ad = lokasyon_adlari[i] if i < len(lokasyon_adlari) else ''
                    lk_barkod = lokasyon_barkodlari[i] if i < len(lokasyon_barkodlari) and lokasyon_barkodlari[i] else None
                    lk_kapasite = lokasyon_kapasiteleri[i] if i < len(lokasyon_kapasiteleri) and lokasyon_kapasiteleri[i] else None
                    
                    if lk_kod in mevcut_lokasyonlar:
                        # Zaten var olan raf, sadece güncelle
                        lok = mevcut_lokasyonlar[lk_kod]
                        lok.ad = lk_ad
                        lok.barkod = lk_barkod
                        lok.tasima_kapasitesi_kg = lk_kapasite
                    else:
                        # Yepyeni bir raf ekleniyor
                        lok = DepoLokasyon(
                            firma_id=current_user.firma_id,
                            depo_id=depo.id,
                            kod=lk_kod,
                            ad=lk_ad,
                            barkod=lk_barkod,
                            tasima_kapasitesi_kg=lk_kapasite
                        )
                        tenant_db.add(lok)
                    
                    islenen_kodlar.append(lk_kod)
                    
                # Ekranda silinmiş olan rafları veritabanından da sil
                for kod, lok in mevcut_lokasyonlar.items():
                    if kod not in islenen_kodlar:
                        tenant_db.delete(lok)
                # --- WMS LOKASYON İŞLEMLERİ BİTİŞ ---

                tenant_db.commit() # Tüm işlemleri onayla

                return jsonify({'success': True, 'message': 'Depo güncellendi.', 'redirect': url_for('depo.index')})
            except Exception as e:
                tenant_db.rollback()
                return jsonify({'success': False, 'message': str(e)}), 500
                
    return render_template('base_form.html', form=form)

# DİKKAT: int:id yerine string:id oldu
@depo_bp.route('/sil/<string:id>', methods=['POST'])
@login_required
def sil(id):
    tenant_db = get_tenant_db()
    try:
        depo = tenant_db.get(Depo, str(id))
        if not depo: return jsonify({'success': False, 'message': 'Kayıt bulunamadı'}), 404

        tenant_db.delete(depo)
        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Depo silindi.'})
    except Exception as e:
        tenant_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
        
# ==========================================
# WMS - EL TERMİNALİ (MOBİL) ROTALARI
# ==========================================

@depo_bp.route('/terminal/mal-kabul')
@login_required
def terminal_mal_kabul():
    """El terminali (Mobil) için optimize edilmiş Mal Kabul ekranı"""
    return render_template('depo/terminal.html')

@depo_bp.route('/api/wms/barkod-coz', methods=['POST'])
@login_required
def wms_barkod_coz():
    """Okutulan barkodun Ürün mü yoksa Raf mı olduğunu anlar"""
    tenant_db = get_tenant_db()
    barkod = request.json.get('barkod', '').strip()
    
    if not barkod:
        return jsonify({'success': False, 'message': 'Barkod boş olamaz!'})

    # 1. İhtimal: Bu barkod bir ÜRÜN (StokKart) mü?
    stok = tenant_db.query(StokKart).filter_by(firma_id=current_user.firma_id, barkod=barkod, aktif=True).first()
    if stok:
        return jsonify({
            'success': True, 
            'tip': 'URUN', 
            'id': str(stok.id), 
            'ad': stok.ad, 
            'kod': stok.kod,
            'birim': stok.birim or 'Adet'
        })

    # 2. İhtimal: Bu barkod bir RAF/LOKASYON mu?
    # Hem rafın kendisine yapıştırılan barkoddan, hem de rafın "A-01" gibi kodundan arayalım
    from sqlalchemy import or_
    lokasyon = tenant_db.query(DepoLokasyon).filter(
        DepoLokasyon.firma_id == current_user.firma_id,
        DepoLokasyon.aktif == True,
        or_(DepoLokasyon.barkod == barkod, DepoLokasyon.kod == barkod)
    ).first()

    if lokasyon:
        return jsonify({
            'success': True, 
            'tip': 'LOKASYON', 
            'id': str(lokasyon.id), 
            'depo_id': str(lokasyon.depo_id), 
            'ad': f"{lokasyon.depo.ad} ➔ {lokasyon.ad} ({lokasyon.kod})"
        })

    return jsonify({'success': False, 'message': 'Barkod sistemde bulunamadı!'}), 404

@depo_bp.route('/api/wms/islem-kaydet', methods=['POST'])
@login_required
def wms_islem_kaydet():
    """Terminalden gelen mal kabul işlemini veritabanına yazar"""
    tenant_db = get_tenant_db()
    data = request.json
    
    try:
        stok_id = data.get('stok_id')
        lokasyon_id = data.get('lokasyon_id')
        depo_id = data.get('depo_id')
        miktar = Decimal(str(data.get('miktar', 0)))
        
        if miktar <= 0:
            return jsonify({'success': False, 'message': 'Miktar 0 olamaz!'})

        # 1. StokLokasyonBakiye Tablosunu Güncelle
        bakiye = tenant_db.query(StokLokasyonBakiye).filter_by(
            stok_id=stok_id, lokasyon_id=lokasyon_id, depo_id=depo_id
        ).first()

        if not bakiye:
            bakiye = StokLokasyonBakiye(
                firma_id=current_user.firma_id,
                stok_id=stok_id,
                depo_id=depo_id,
                lokasyon_id=lokasyon_id,
                miktar=0
            )
            tenant_db.add(bakiye)
            
        bakiye.miktar += miktar
        
        # ✨ YENİ EKLENEN: Raf kodunu güvenli bir şekilde doğrudan veritabanından çekiyoruz
        lokasyon_obj = tenant_db.get(DepoLokasyon, str(lokasyon_id))
        raf_kodu = lokasyon_obj.kod if lokasyon_obj else "Bilinmeyen Raf"

        # ✨ YENİ EKLENEN: Şube ID'yi bul (Deponun bağlı olduğu şube)
        from app.modules.depo.models import Depo
        depo_obj = tenant_db.get(Depo, str(depo_id))
        aktif_sube_id = depo_obj.sube_id if depo_obj else None

        # ✨ YENİ EKLENEN: Dönem ID'yi bul (Session'dan veya veritabanından)
        from flask import session
        from app.modules.firmalar.models import Donem
        aktif_donem_id = session.get('donem_id') or session.get('aktif_donem_id')
        if not aktif_donem_id:
            donem = tenant_db.query(Donem).filter_by(firma_id=current_user.firma_id).first()
            aktif_donem_id = donem.id if donem else None
            
        # 2. Stok Hareketi Oluştur (Tarihçesi olsun diye)
        sh = StokHareketi(
            firma_id=current_user.firma_id,
            donem_id=aktif_donem_id, 
            sube_id=aktif_sube_id,
            stok_id=stok_id,
            giris_depo_id=depo_id,
            kullanici_id=current_user.id,
            tarih=datetime.now().date(),
            hareket_turu=HareketTuru.SAYIM_FAZLASI.name,
            miktar=miktar,
            aciklama=f"WMS Terminal Mal Kabul (Raf: {raf_kodu})", # ✨ DÜZELTİLDİ
            kaynak_turu="WMS"
        )
        tenant_db.add(sh)
        
        tenant_db.commit()
        return jsonify({'success': True, 'message': f'Başarılı: {miktar} adet ürün rafa yerleştirildi.'})

    except Exception as e:
        tenant_db.rollback()
        import logging
        logging.error(f"WMS Kayıt Hatası: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Sistem Hatası: {str(e)}'}), 500
        
# ==========================================
# WMS - DEPOLAR/RAFLAR ARASI TRANSFER
# ==========================================

@depo_bp.route('/terminal/transfer')
@login_required
def terminal_transfer():
    """El terminali (Mobil) için optimize edilmiş Transfer ekranı"""
    return render_template('depo/terminal_transfer.html')

@depo_bp.route('/api/wms/transfer-kaydet', methods=['POST'])
@login_required
def wms_transfer_kaydet():
    """Terminalden gelen transfer işlemini veritabanına yazar"""
    tenant_db = get_tenant_db()
    data = request.json
    
    try:
        stok_id = data.get('stok_id')
        cikis_lok_id = data.get('cikis_lokasyon_id')
        varis_lok_id = data.get('varis_lokasyon_id')
        miktar = Decimal(str(data.get('miktar', 0)))
        
        if miktar <= 0:
            return jsonify({'success': False, 'message': 'Miktar 0 olamaz!'})
        if cikis_lok_id == varis_lok_id:
            return jsonify({'success': False, 'message': 'Çıkış ve Varış rafı aynı olamaz!'})

        # 1. ÇIKIŞ RAFINDA YETERLİ MAL VAR MI KONTROLÜ
        cikis_bakiye = tenant_db.query(StokLokasyonBakiye).filter_by(
            stok_id=stok_id, lokasyon_id=cikis_lok_id
        ).first()

        if not cikis_bakiye or cikis_bakiye.miktar < miktar:
            mevcut = cikis_bakiye.miktar if cikis_bakiye else 0
            return jsonify({'success': False, 'message': f'Hata: Çıkış rafında yeterli stok yok! (Mevcut: {mevcut})'})

        # 2. VARIŞ RAFINI BUL VEYA OLUŞTUR
        varis_lokasyon_obj = tenant_db.get(DepoLokasyon, str(varis_lok_id))
        varis_bakiye = tenant_db.query(StokLokasyonBakiye).filter_by(
            stok_id=stok_id, lokasyon_id=varis_lok_id
        ).first()

        if not varis_bakiye:
            varis_bakiye = StokLokasyonBakiye(
                firma_id=current_user.firma_id,
                stok_id=stok_id,
                depo_id=varis_lokasyon_obj.depo_id,
                lokasyon_id=varis_lok_id,
                miktar=0
            )
            tenant_db.add(varis_bakiye)

        # 3. BAKİYELERİ GÜNCELLE (Birisinden düş, diğerine ekle)
        cikis_bakiye.miktar -= miktar
        varis_bakiye.miktar += miktar

        # 4. STOK HAREKETİ (LOG) OLUŞTUR
        from flask import session
        from app.modules.firmalar.models import Donem
        aktif_donem_id = session.get('donem_id') or session.get('aktif_donem_id')
        if not aktif_donem_id:
            donem = tenant_db.query(Donem).filter_by(firma_id=current_user.firma_id).first()
            aktif_donem_id = donem.id if donem else None

        sh = StokHareketi(
            firma_id=current_user.firma_id,
            donem_id=aktif_donem_id,
            sube_id=cikis_bakiye.depo.sube_id if cikis_bakiye.depo else None,
            stok_id=stok_id,
            cikis_depo_id=cikis_bakiye.depo_id,
            giris_depo_id=varis_bakiye.depo_id,
            kullanici_id=current_user.id,
            tarih=datetime.now().date(),
            hareket_turu=HareketTuru.DEPO_TRANSFER.name if hasattr(HareketTuru, 'DEPO_TRANSFER') else "DEPO_TRANSFER", 
            miktar=miktar,
            aciklama=f"WMS Transfer: [{cikis_bakiye.lokasyon.kod}] ➔ [{varis_lokasyon_obj.kod}]",
            kaynak_turu="WMS"
        )
        tenant_db.add(sh)

        tenant_db.commit()
        return jsonify({'success': True, 'message': 'Transfer işlemi başarıyla tamamlandı.'})

    except Exception as e:
        tenant_db.rollback()
        import logging
        logging.error(f"WMS Transfer Hatası: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Sistem Hatası: {str(e)}'}), 500

