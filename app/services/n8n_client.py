import requests
import threading
import json
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class N8NClient:
    """
    ERP sistemi ile n8n Otomasyon sunucusu arasındaki köprü.
    İşlemleri asenkron (arka planda) yaparak ana uygulamayı yavaşlatmaz.
    """

    @staticmethod
    def _send_request_worker(url, method, payload, headers):
        """
        Arka planda çalışacak işçi fonksiyon.
        """
        try:
            if method == 'GET':
                response = requests.get(url, params=payload, headers=headers, timeout=5)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=5)
            
            # Başarılı ise logla (Opsiyonel, çok log kirliliği yapmasın diye kapalı tutulabilir)
            if response.status_code < 300:
                logger.info(f"✅ n8n Tetiklendi: {url} | Status: {response.status_code}")
            else:
                logger.warning(f"⚠️ n8n Hatası: {url} | Status: {response.status_code} | Body: {response.text}")
                
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ n8n Bağlantı Hatası: Sunucuya erişilemiyor ({url})")
        except Exception as e:
            logger.error(f"❌ n8n Beklenmeyen Hata: {str(e)}")

    @classmethod
    def trigger(cls, webhook_path, payload={}, method='POST', sync=False):
        """
        n8n Webhook'unu tetikler.

        Args:
            webhook_path (str): n8n tarafındaki URL sonu (örn: 'fatura-onay')
            payload (dict): Gönderilecek veri
            method (str): 'POST' veya 'GET'
            sync (bool): True ise cevabı bekler (bloklar), False ise arka planda atar.
        """
        # Config'den Base URL'i al
        base_url = current_app.config.get('N8N_WEBHOOK_URL', 'http://localhost:5678/webhook')
        
        # URL birleştirme (slash hatasını önle)
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if webhook_path.startswith('/'):
            webhook_path = webhook_path[1:]
            
        full_url = f"{base_url}/{webhook_path}"
        
        # Güvenlik Header'ı (Opsiyonel: n8n tarafında Basic Auth varsa)
        api_key = current_app.config.get('N8N_API_KEY')
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'MuhMySQL-ERP/1.0'
        }
        if api_key:
            headers['X-N8N-API-KEY'] = api_key

        # Senkron mu Asenkron mu?
        if sync:
            # Cevap bekleyen kritik işlemler için (örn: n8n'den veri alıp ekrana basacaksan)
            try:
                if method == 'GET':
                    return requests.get(full_url, params=payload, headers=headers, timeout=10).json()
                else:
                    return requests.post(full_url, json=payload, headers=headers, timeout=10).json()
            except Exception as e:
                logger.error(f"n8n Sync Hata: {e}")
                return None
        else:
            # Fire-and-Forget (Varsayılan): Bildirimler, Loglama vb.
            thread = threading.Thread(
                target=cls._send_request_worker,
                args=(full_url, method, payload, headers)
            )
            thread.daemon = True # Ana program kapanırsa bu da kapansın
            thread.start()
            return True