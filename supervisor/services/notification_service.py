
# supervisor/services/notification_service.py

import os
from flask_mail import Message, Mail
from datetime import datetime

mail = Mail()

class NotificationService:
    @staticmethod
    def init_app(app):
        app.config['MAIL_SERVER'] = 'smtp.gmail.com'
        app.config['MAIL_PORT'] = 587
        app.config['MAIL_USE_TLS'] = True
        # Buraya kendi bilgilerini gir veya .env dosyasından çek
        app.config['MAIL_USERNAME'] = 'nail19@gmail.com' 
        app.config['MAIL_PASSWORD'] = 'N404736c@19@67' # Google Uygulama Şifresi
        app.config['MAIL_DEFAULT_SENDER'] = ('Supervisor Cloud', app.config['MAIL_USERNAME'])
        mail.init_app(app)

    @staticmethod
    def send_backup_report(to_email, tenant_name, status, details):
        """Yedekleme sonrası durum raporu gönderir"""
        subject = f"🔔 Yedekleme Raporu: {tenant_name} ({status.upper()})"
        
        # HTML İçeriği
        color = "#28a745" if status == 'success' else "#dc3545"
        icon = "✅" if status == 'success' else "❌"
        
        body = f"""
        <html>
            <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td align="center" style="padding: 20px 0;">
                            <table border="0" cellpadding="0" cellspacing="0" width="90%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                                <tr>
                                    <td align="center" style="background-color: {color}; padding: 30px;">
                                        <h1 style="color: #ffffff; margin: 0; font-size: 24px;">{icon} Yedekleme Raporu</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 30px;">
                                        <p style="font-size: 16px; color: #475569; margin-bottom: 20px;">Kaptan, son seferin detayları aşağıdadır:</p>
                                        <table width="100%" style="border-collapse: collapse;">
                                            <tr>
                                                <td style="padding: 10px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;"><strong>Firma:</strong></td>
                                                <td style="padding: 10px 0; color: #1e293b; text-align: right; border-bottom: 1px solid #f1f5f9;">{tenant_name}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;"><strong>Durum:</strong></td>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #f1f5f9; text-align: right;"><span style="color: {color}; font-weight: bold;">{status.upper()}</span></td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; color: #64748b;"><strong>Detay:</strong></td>
                                                <td style="padding: 10px 0; color: #1e293b; text-align: right;">{details}</td>
                                            </tr>
                                        </table>
                                        <div style="margin-top: 30px; text-align: center;">
                                            <a href="http://127.0.0.1:5001/backup/" style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Paneli Görüntüle</a>
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="background-color: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #94a3b8;">
                                        Bu e-posta <strong>Supervisor ERP/SaaS Cloud</strong> tarafından otomatik üretilmiştir.<br>2026 © Tüm Hakları Saklıdır.
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        msg = Message(subject, recipients=[to_email])
        msg.html = body
        
        try:
            mail.send(msg)
            print(f"📧 [Notification] Rapor gönderildi: {to_email}")
        except Exception as e:
            print(f"❌ [Notification] E-posta gönderilemedi: {e}")