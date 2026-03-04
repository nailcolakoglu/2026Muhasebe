# form_builder/workflow.py
import logging
import requests
from datetime import datetime, timedelta
from simpleeval import simple_eval

class WorkflowEngine:
    """
    Basit ama güçlü bir State Machine (Durum Makinesi).
    Verilen 'context' (form verisi) üzerinde kuralları çalıştırır ve bir sonraki adıma geçer.
    """
    
    def __init__(self, definition):
        """
        definition: İş akışının JSON haritası
        """
        self.steps = definition.get('steps', {})
        self.start_step = definition.get('start_step', 'start')

    def run(self, current_step_id, context_data):
        """
        Mevcut adımdan başlar, bir duraklama noktasına (WAIT, DELAY) veya bitişe (END) kadar ilerler.
        """
        step_id = current_step_id or self.start_step
        history = []

        while step_id and step_id != 'END':
            step = self.steps.get(step_id)
            if not step:
                break

            history.append(f"Running: {step_id}")

            # ==========================================
            # 🚀 1. DEV: ZAMANLANMIŞ GECİKME (DELAY) MOTORU
            # ==========================================
            if step.get('type') == 'delay':
                delay_seconds = step.get('duration', 0)
                resume_time = datetime.now() + timedelta(seconds=delay_seconds)
                
                logging.info(f"⏳ WORKFLOW DURAKLATILDI: {delay_seconds} saniye bekleniyor...")
                
                # Motoru burada durdurur ve durumu dışarıya (Örn: Veritabanına / Celery'e) teslim ederiz
                return {
                    'status': 'DELAYED',
                    'resume_at': resume_time.isoformat(),
                    'resume_step': step.get('next'), # Süre dolunca burdan uyanacak
                    'context': context_data,
                    'history': history
                }

            # 2. Action (Eylem) Var mı? (Örn: E-posta at, Statü güncelle, Webhook)
            if 'action' in step:
                self._execute_action(step['action'], context_data)

            # 3. Transition (Geçiş) Mantığı
            next_step = None
            if 'transitions' in step:
                for transition in step['transitions']:
                    condition = transition.get('condition', 'True')
                    if self._evaluate(condition, context_data):
                        next_step = transition.get('next')
                        break

            # Eğer koşullara uymazsa veya geçiş yoksa default 'next' kullan
            if not next_step:
                next_step = step.get('next')

            step_id = next_step

        return {
            'status': 'COMPLETED',
            'final_step': step_id,
            'context': context_data,
            'history': history
        }

    def _evaluate(self, condition_str, data):
        try:
            # Python'un tehlikeli fonksiyonlarına erişimi kapatır
            return simple_eval(condition_str, names=data)
        except Exception as e:
            logging.error(f"❌ Kural Hatası: {e}")
            return False

    def _execute_action(self, action_config, data):
        """
        Tanımlı eylemleri gerçekleştirir.
        """
        action_type = action_config.get('type')
        
        if action_type == 'update_status':
            # Veri içindeki statüyü güncelle
            data['status'] = action_config.get('value')
            logging.info(f"⚡ ACTION: Statü '{action_config.get('value')}' olarak güncellendi.")
            
        elif action_type == 'send_email':
            to = action_config.get('to')
            subject = action_config.get('subject')
            logging.info(f"📧 EMAIL: {to} adresine '{subject}' konulu mail atıldı.")
            
        # ==========================================
        # 🚀 2. DEV: GERÇEK WEBHOOK (HTTP/API) MOTORU
        # ==========================================
        elif action_type == 'webhook':
            url = action_config.get('url')
            method = action_config.get('method', 'POST').upper()
            headers = action_config.get('headers', {})
            
            # Webhook'a sadece belirli bir veriyi göndermek isteyebilirsin, yoksa tüm datayı (context) yollar
            payload = action_config.get('payload', data) 
            
            try:
                if method == 'POST':
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                elif method == 'GET':
                    response = requests.get(url, params=payload, headers=headers, timeout=10)
                elif method == 'PUT':
                    response = requests.put(url, json=payload, headers=headers, timeout=10)
                else:
                    response = requests.request(method, url, json=payload, headers=headers, timeout=10)
                    
                # Eğer HTTP 400 veya 500 dönerse sistemi çökertmek yerine Exception fırlattırıyoruz
                response.raise_for_status() 
                logging.info(f"📡 WEBHOOK BAŞARILI: {url} (Status: {response.status_code})")
                
                # API'den gelen yanıtı dataya ekle (Bir sonraki adımda değerlendirebilmek için)
                try:
                    data['webhook_response'] = response.json()
                except:
                    data['webhook_response'] = response.text
                    
                data['webhook_status'] = 'SUCCESS'
                
            except requests.exceptions.RequestException as e:
                logging.error(f"❌ WEBHOOK HATASI ({url}): {e}")
                data['webhook_status'] = 'FAILED'
                data['webhook_error'] = str(e)    

        # Buraya webhook, SMS vb.eklenebilir.
        elif action_type == 'trigger_n8n':
            from app.services.n8n_client import N8NClient
            webhook = action_config.get('webhook')
            payload = action_config.get('payload', {})
            
            # Context verisini payload ile birleştir
            full_payload = {**data, **payload} 
            
            N8NClient.trigger(webhook, full_payload)
            print(f"🔗 WORKFLOW: n8n '{webhook}' tetiklendi.")
            
        