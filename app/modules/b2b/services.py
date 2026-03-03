# app/modules/b2b/services.py

import logging
from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.extensions import db
from app.models.master import Tenant
from app.modules.b2b.models import B2BKullanici, B2BAyar

logger = logging.getLogger(__name__)

class B2BAuthService:
    """B2B Portalı Kimlik Doğrulama Servisi"""
    
    @staticmethod
    def login(firma_kodu, email, sifre):
        """
        Bayi Girişini Uçtan Uca Doğrular:
        1. Master DB'den Firmayı (Tenant) bulur.
        2. Tenant DB'ye dinamik bağlanıp Email/Şifre kontrolü yapar.
        3. Portalın aktif olup olmadığına bakar.
        """
        # 1. Master DB Kontrolü (Firma var mı?)
        tenant = db.session.query(Tenant).filter_by(kod=firma_kodu.upper(), is_active=True).first()
        if not tenant:
            return False, "Firma kodu hatalı veya firma pasif durumda.", None
            
        # 2. Dinamik Olarak Hedef Firmanın Veritabanına Bağlan
        tenant_db_url = (
            f"mysql+pymysql://"
            f"{current_app.config['TENANT_DB_USER']}:"
            f"{current_app.config['TENANT_DB_PASSWORD']}"
            f"@{current_app.config['TENANT_DB_HOST']}:"
            f"{current_app.config['TENANT_DB_PORT']}"
            f"/{tenant.db_name}?charset=utf8mb4"
        )
        
        try:
            engine = create_engine(tenant_db_url)
            with Session(engine) as tenant_session:
                
                # A. Portal Aktiflik Kontrolü
                ayar = tenant_session.query(B2BAyar).first()
                if not ayar or not ayar.aktif_mi:
                    return False, "Bu firmanın B2B Portalı şu an geçici olarak kapalıdır.", None
                
                # B. Kullanıcı Doğrulama
                user = tenant_session.query(B2BKullanici).filter_by(email=email).first()
                
                if not user:
                    return False, "E-posta veya şifre hatalı.", None
                    
                if not user.aktif:
                    return False, "Hesabınız askıya alınmış. Lütfen firma ile iletişime geçin.", None
                    
                if not user.sifre_kontrol(sifre):
                    return False, "E-posta veya şifre hatalı.", None
                
                # Kullanıcının son giriş tarihini güncelle (Opsiyonel ama profesyonel)
                from datetime import datetime
                user.son_giris_tarihi = datetime.utcnow()
                tenant_session.commit()
                
                # Güvenli dict kopyası oluştur (Session kapandığında data kaybolmasın diye)
                user_data = {
                    'b2b_user_id': user.id,
                    'tenant_id': tenant.id,
                    'cari_id': user.cari_id,
                    'ad_soyad': user.ad_soyad
                }
                
                logger.info(f"✅ B2B Başarılı Giriş: {email} -> Firma: {firma_kodu}")
                return True, "Giriş başarılı.", user_data
                
        except Exception as e:
            logger.error(f"❌ B2B Login DB Hatası: {str(e)}")
            return False, "Sistem veritabanı bağlantı hatası.", None
            

class B2BYonetimService:
    """ERP personelinin B2B hesaplarını yönettiği servis"""
    
    @staticmethod
    def kullanici_kaydet(data, firma_id, user_id=None):
        tenant_db = get_tenant_db()
        try:
            if user_id:
                user = tenant_db.get(B2BKullanici, str(user_id))
                if not user: return False, "Hesap bulunamadı."
                
                # Başkasının mailini almasını engelle
                mevcut = tenant_db.query(B2BKullanici).filter_by(email=data.get('email')).first()
                if mevcut and str(mevcut.id) != str(user_id):
                    return False, "Bu e-posta adresi başka bir bayide kullanılıyor."
            else:
                # Yeni kayıt email kontrolü
                if tenant_db.query(B2BKullanici).filter_by(email=data.get('email')).first():
                    return False, "Bu e-posta adresi zaten kullanımda."
                
                user = B2BKullanici(firma_id=firma_id)
                tenant_db.add(user)

            # Verileri Doldur
            user.cari_id = data.get('cari_id')
            user.ad_soyad = data.get('ad_soyad')
            user.email = data.get('email')
            user.telefon = data.get('telefon')
            
            # Şifre girilmişse Hash'le ve kaydet
            if data.get('sifre'):
                user.sifre_belirle(data.get('sifre'))
                
            # Yetkiler (Checkbox'lar string olarak gelebilir)
            user.aktif = str(data.get('aktif')).lower() in ['true', 'on', '1']
            user.yetki_siparis_ver = str(data.get('yetki_siparis_ver')).lower() in ['true', 'on', '1']
            user.yetki_ekstre_gor = str(data.get('yetki_ekstre_gor')).lower() in ['true', 'on', '1']

            tenant_db.commit()
            return True, "B2B Müşteri hesabı başarıyla kaydedildi."
            
        except Exception as e:
            tenant_db.rollback()
            logger.error(f"❌ B2B Yönetim Kayıt Hatası: {str(e)}")
            return False, f"Sistem hatası: {str(e)}"