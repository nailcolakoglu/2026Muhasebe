# app/services/session_service.py

from datetime import datetime, timedelta
from flask import request, session, current_app
from app.extensions import db
from app.models.master import MasterActiveSession, User

class SessionService:
    """
    Oturum Yönetimi ve Lisans Kontrolü
    """
    
    # Oturumun boşta kalma süresi (Dakika)
    # Bu süreden fazla işlem yapmayan otomatik düşer.
    TIMEOUT_MINUTES = 30 

    @staticmethod
    def cleanup_stale_sessions():
        """
        Süresi dolmuş (zombi) oturumları temizler.
        Login işleminden hemen önce çalışmalıdır.
        """
        try:
            expiration_time = datetime.now() - timedelta(minutes=SessionService.TIMEOUT_MINUTES)
            
            # Süresi geçenleri sil
            deleted_count = MasterActiveSession.query.filter(
                MasterActiveSession.last_activity < expiration_time
            ).delete()
            
            if deleted_count > 0:
                db.session.commit()
                # print(f"🧹 Temizlik: {deleted_count} adet zombi oturum silindi.")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Session temizlik hatası: {e}")

    @staticmethod
    def can_login(tenant_id, max_users):
        """
        Kullanıcı içeri girebilir mi? (Limit Kontrolü)
        """
        # 1. Önce ortalığı temizle (Ölü oturumları saymayalım)
        SessionService.cleanup_stale_sessions()

        # 2. Şu anki aktif oturum sayısını çek
        current_active_count = MasterActiveSession.query.filter_by(tenant_id=tenant_id).count()

        # 3. Limit Kontrolü
        # Eğer (Aktif Sayısı) >= (Lisans Hakkı) ise DUR.
        if current_active_count >= max_users:
            return False, f"Lisans limiti dolu! ({current_active_count}/{max_users} Kullanıcı Aktif). Lütfen açık oturumları kapatın."

        return True, "OK"

    @staticmethod
    def register_session(user, tenant_id):
        """
        Giriş başarılı olduğunda oturumu veritabanına kaydeder.
        """
        try:
            ip = request.remote_addr
            agent = request.headers.get('User-Agent')
            
            # Token oluştur (Session Fixation koruması için)
            import uuid
            session_token = str(uuid.uuid4())
            session['_session_token'] = session_token # Flask session'a yaz

            # Eski oturum varsa sil (Aynı tarayıcıdan tekrar giriyorsa)
            # Not: Farklı cihazdan giriyorsa silmiyoruz, yeni kayıt açıyoruz (Concurrent Session)
            # Ancak aynı user_id temizliği istenirse burası açılabilir.
            
            new_session = MasterActiveSession(
                session_token=session_token,
                user_id=user.id,
                tenant_id=tenant_id,
                ip_address=ip,
                user_agent=agent,
                last_activity=datetime.now()
            )
            
            db.session.add(new_session)
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Session kayıt hatası: {e}")
            return False

    @staticmethod
    def heartbeat():
        """
        Kullanıcı her sayfa değiştirdiğinde 'Ben buradayım' der.
        Süreyi uzatır.
        """
        token = session.get('_session_token')
        if not token:
            return False
            
        try:
            # Token ile oturumu bul
            active_session = MasterActiveSession.query.filter_by(session_token=token).first()
            
            if active_session:
                # Süreyi güncelle
                active_session.last_activity = datetime.now()
                # IP değiştiyse güncelle (Mobil veri vs.)
                active_session.ip_address = request.remote_addr
                db.session.commit()
                return True
            else:
                # DB'de yoksa (Admin atmış olabilir veya timeout yemiş)
                return False
        except:
            return False

    @staticmethod
    def logout():
        """
        Çıkış yaparken DB'den sil
        """
        token = session.get('_session_token')
        if token:
            try:
                MasterActiveSession.query.filter_by(session_token=token).delete()
                db.session.commit()
            except Exception as e:
                db.session.rollback()