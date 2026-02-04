from flask import Blueprint, render_template, jsonify, flash, redirect, url_for, request
from flask_login import login_required
from app.extensions import get_tenant_db # GOLDEN RULE: Tenant DB erişimi
from app.modules.doviz.models import DovizKuru
from app.enums import ParaBirimi
from datetime import datetime
import requests
import xml.etree.ElementTree as ET

doviz_bp = Blueprint('doviz', __name__)

def tcmb_kur_cek():
    """
    Merkez Bankasından XML verisini çeker ve Aktif Tenant'ın Firebird veritabanına kaydeder.
    """
    url = "https://www.tcmb.gov.tr/kurlar/today.xml"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return False, "TCMB sunucusuna erişilemedi."
            
        root = ET.fromstring(response.content)
        bugun = datetime.today().date()
        
        # Hangi kurları takip edeceğiz?
        takip_listesi = ['USD', 'EUR', 'GBP']
        kaydedilenler = 0
        
        # GOLDEN RULE: İşlemleri Tenant DB üzerinde başlatıyoruz
        tenant_db = get_tenant_db()
        
        try:
            for currency in root.findall('Currency'):
                kod_str = currency.get('Kod')
                
                if kod_str in takip_listesi:
                    # Enum dönüşümü (String -> Enum)
                    try:
                        enum_kod = ParaBirimi[kod_str]
                    except KeyError:
                        continue # Tanımsız para birimi ise atla

                    # Verileri XML'den ayıkla
                    ad = currency.find('Isim').text
                    forex_buying = float(currency.find('ForexBuying').text or 0)
                    forex_selling = float(currency.find('ForexSelling').text or 0)
                    banknote_buying = float(currency.find('BanknoteBuying').text or 0)
                    banknote_selling = float(currency.find('BanknoteSelling').text or 0)
                    
                    # Veritabanında var mı kontrol et (Bugün için) - TENANT DB SORGUSU
                    mevcut_kur = tenant_db.query(DovizKuru).filter_by(tarih=bugun, kod=enum_kod).first()
                    
                    if mevcut_kur:
                        # Güncelle
                        mevcut_kur.alis = forex_buying
                        mevcut_kur.satis = forex_selling
                        mevcut_kur.efektif_alis = banknote_buying
                        mevcut_kur.efektif_satis = banknote_selling
                    else:
                        # Yeni Ekle
                        yeni_kur = DovizKuru(
                            tarih=bugun,
                            kod=enum_kod,
                            ad=ad,
                            alis=forex_buying,
                            satis=forex_selling,
                            efektif_alis=banknote_buying,
                            efektif_satis=banknote_selling
                        )
                        tenant_db.add(yeni_kur)
                    
                    kaydedilenler += 1
            
            # Tüm işlemler bittikten sonra commit
            tenant_db.commit()
            return True, f"{kaydedilenler} adet kur başarıyla güncellendi."
            
        except Exception as e:
            tenant_db.rollback()
            raise e # Dışarıdaki catch bloğuna fırlat

    except Exception as e:
        return False, f"Hata oluştu: {str(e)}"

# --- ROTALAR ---

@doviz_bp.route('/kur-listesi')
@login_required
def kur_listesi():
    # GOLDEN RULE: Tenant DB kullanımı
    tenant_db = get_tenant_db()
    
    # Bugünü ve son 50 kaydı gösterelim
    kurlar = tenant_db.query(DovizKuru).order_by(DovizKuru.tarih.desc(), DovizKuru.kod).limit(50).all()
    
    return render_template('doviz/list.html', kurlar=kurlar, bugun=datetime.today().date())

@doviz_bp.route('/kurlari-guncelle', methods=['POST'])
@login_required
def kurlari_guncelle():
    basari, mesaj = tcmb_kur_cek()
    if basari:
        flash(mesaj, 'success')
    else:
        flash(mesaj, 'danger')
    return redirect(url_for('doviz.kur_listesi'))

@doviz_bp.route('/api/get-kur/<kod>', methods=['GET'])
@login_required
def api_get_kur(kod):
    """
    Tüm sistemin kullandığı ortak kur getirme servisi.
    Kullanım: /doviz/api/get-kur/USD
    """
    try:
        if not kod:
            return jsonify({'success': False, 'kur': 0.0})
            
        # Enum kontrolü
        try:
            enum_kod = ParaBirimi[kod]
        except KeyError:
             return jsonify({'success': False, 'message': 'Geçersiz Para Birimi', 'kur': 0.0})

        # GOLDEN RULE: Tenant DB üzerinden sorgulama
        tenant_db = get_tenant_db()
        
        # Önce bugünün kuruna bak
        bugun = datetime.today().date()
        kur_obj = tenant_db.query(DovizKuru).filter_by(tarih=bugun, kod=enum_kod).first()
        
        # Eğer bugün yoksa, en son girilen kura bak (Fallback)
        if not kur_obj:
            kur_obj = tenant_db.query(DovizKuru).filter_by(kod=enum_kod).order_by(DovizKuru.tarih.desc()).first()
            
        kur_degeri = float(kur_obj.satis) if kur_obj else 0.0
        
        return jsonify({
            'success': True,
            'kod': kod,
            'kur': kur_degeri,
            'tarih': kur_obj.tarih.strftime('%Y-%m-%d') if kur_obj else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'kur': 0.0})