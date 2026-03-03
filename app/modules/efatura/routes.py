# app/modules/efatura/routes.py

from sqlalchemy import text
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
import logging
from app.decorators import tenant_route, permission_required
from app.extensions import get_tenant_db # ✨ EKLENDİ
from .models import EntegratorAyarlari # ✨ EKLENDİ
from .forms import create_entegrator_ayarlari_form # ✨ EKLENDİ
from .services import EntegratorService
from app.modules.efatura.tasks import send_efatura_async

logger = logging.getLogger(__name__)
efatura_bp = Blueprint('efatura', __name__, url_prefix='/efatura')

@efatura_bp.route('/gonder/<string:id>', methods=['GET','POST']) # fatura_id yerine id oldu
@login_required
@tenant_route
def gonder(id):
    try:
        # Arka plana id'yi gönderiyoruz
        send_efatura_async.delay(str(id), str(current_user.firma_id))
        return jsonify({'success': True, 'message': 'Fatura arka planda GİB\'e iletilmek üzere kuyruğa alındı!'})
    except Exception as e:
        logger.error(f"E-Fatura Kuyruk Hatası: {str(e)}")
        return jsonify({'success': False, 'message': "Görev kuyruğa alınırken sunucu hatası oluştu."}), 500
        
@efatura_bp.route('/durum/<string:id>', methods=['POST']) # fatura_id yerine id oldu
@login_required
@tenant_route
def durum(id):
    try:
        service = EntegratorService(current_user.firma_id)
        basari, mesaj = service.durum_sorgula(id)
        return jsonify({'success': basari, 'message': mesaj})
    except Exception as e:
        logger.error(f"E-Fatura Durum Sorgulama Hatası: {str(e)}")
        return jsonify({'success': False, 'message': "Durum sorgulanamadı."}), 500

@efatura_bp.route('/ayarlar', methods=['GET', 'POST'])
@login_required
@tenant_route
# @permission_required('ayarlar_yonetimi') # Eğer yetki kontrolün varsa açabilirsin
def ayarlar():
    tenant_db = get_tenant_db()
    
    # Mevcut ayarları veritabanından çek (Varsa form dolu gelecek)
    mevcut_ayar = tenant_db.query(EntegratorAyarlari).filter_by(firma_id=str(current_user.firma_id)).first()
    
    form = create_entegrator_ayarlari_form(mevcut_ayar)
    
    if request.method == 'POST':
        form.process_request(request.form)
        if form.validate():
            try:
                data = form.get_data()
                
                is_new = False
                if not mevcut_ayar:
                    mevcut_ayar = EntegratorAyarlari(firma_id=str(current_user.firma_id))
                    is_new = True
                
                # Verileri modele aktar
                mevcut_ayar.provider = data.get('provider')
                mevcut_ayar.username = data.get('username')
                
                # Şifre alanı boş geçilmemişse güncelle
                if data.get('password') and data.get('password').strip() != '':
                    mevcut_ayar.password = data.get('password')
                    
                mevcut_ayar.api_url = data.get('api_url')
                mevcut_ayar.gb_etiketi = data.get('gb_etiketi')
                mevcut_ayar.pk_etiketi = data.get('pk_etiketi')
                
                # Checkbox / Switch güvenliği
                aktif_val = data.get('aktif')
                mevcut_ayar.aktif = aktif_val in ['True', '1', True, 'true', 'on']
                
                if is_new:
                    tenant_db.add(mevcut_ayar)
                    
                tenant_db.commit()
                return jsonify({'success': True, 'message': 'Entegratör ayarları başarıyla kaydedildi.', 'redirect': '/efatura/ayarlar'})
                
            except Exception as e:
                tenant_db.rollback()
                logger.error(f"E-Fatura Ayar Kayıt Hatası: {str(e)}", exc_info=True)
                return jsonify({'success': False, 'message': f"Kayıt Hatası: {str(e)}"}), 500
        else:
             return jsonify({'success': False, 'message': 'Lütfen formdaki hataları düzeltin.', 'errors': form.get_errors()}), 400
             
    return render_template('efatura/ayarlar.html', form=form)
    
@efatura_bp.route('/db-fix')
@login_required
@tenant_route
def db_fix():
    tenant_db = get_tenant_db()
    try:
        # Sütunu VARCHAR(50) yaparak daralma (truncate) problemini kökünden çözüyoruz.
        tenant_db.execute(text("ALTER TABLE faturalar MODIFY e_fatura_senaryo VARCHAR(50);"))
        tenant_db.execute(text("ALTER TABLE faturalar MODIFY e_fatura_tipi VARCHAR(50);")) # Ne olur ne olmaz bunu da büyütelim
        tenant_db.commit()
        return "<h3>✅ Veritabanı başarıyla güncellendi! Daralma sorunu çözüldü.</h3><p>Sekmeyi kapatabilirsiniz.</p>"
    except Exception as e:
        return f"<h3>❌ Veritabanı Hatası:</h3> <p>{str(e)}</p>"
    
@efatura_bp.route('/gelenler', methods=['GET'])
@login_required
@tenant_route
def gelenler():
    """Gelen faturaları (Inbox) listeler"""
    service = EntegratorService(str(current_user.firma_id))
    faturalar = service.gelen_faturalari_getir()
    return render_template('efatura/gelenler.html', faturalar=faturalar)

@efatura_bp.route('/iceri-al', methods=['POST'])
@login_required
@tenant_route
def iceri_al():
    """Seçilen faturayı ERP'ye kaydeder"""
    ettn = request.form.get('ettn')
    vkn = request.form.get('vkn')
    unvan = request.form.get('unvan')
    belge_no = request.form.get('belge_no')
    tarih = request.form.get('tarih')
    tutar = request.form.get('tutar')
    
    try:
        service = EntegratorService(str(current_user.firma_id))
        basari, mesaj = service.faturayi_iceri_al(ettn, vkn, unvan, belge_no, tarih, tutar)
        return jsonify({'success': basari, 'message': mesaj})
    except Exception as e:
        logger.error(f"Fatura içeri alma hatası: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
       
@efatura_bp.route('/goruntule/<string:id>', methods=['GET'])
@login_required
@tenant_route
def goruntule(id):
    """Faturayı UBL formatında üretip XSLT ile HTML olarak ekrana basar"""
    from app.modules.fatura.models import Fatura
    from app.modules.firmalar.models import Firma
    from app.modules.efatura.ubl_builder import UBLBuilder
    import lxml.etree as ET
    import os
    from flask import current_app, Response
    
    tenant_db = get_tenant_db()
    
    try:
        fatura = tenant_db.query(Fatura).get(id)
        if not fatura:
            return "Fatura bulunamadı.", 404

        satici_firma = tenant_db.query(Firma).get(fatura.firma_id)

        # 1. XML'i Canlı Olarak Üret
        builder = UBLBuilder(fatura, satici_firma)
        xml_bytes = builder.build_xml()

        # 2. XSLT Dosyasının Yolunu Belirle (app/static/xslt/general.xslt)
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        xslt_path = os.path.join(app_dir, 'static', 'xslt', 'general.xslt')
        
        # 3. XSLT Varsa HTML'e Çevir, Yoksa Ham XML Göster
        if os.path.exists(xslt_path):
            xslt_doc = ET.parse(xslt_path)
            transform = ET.XSLT(xslt_doc)
            xml_doc = ET.fromstring(xml_bytes)
            html_result = transform(xml_doc)
            return str(html_result)
        else:
            # Geliştirici dostu: XSLT dosyası henüz klasöre konmamışsa ham XML göster
            return Response(xml_bytes, mimetype='application/xml')
            
    except Exception as e:
        logger.error(f"Fatura Görselleştirme Hatası: {str(e)}", exc_info=True)
        return f"<h3>Görselleştirme Hatası:</h3><p>{str(e)}</p>", 500