# form_builder/workflow.py
import logging
from simpleeval import simple_eval # pip install simpleeval

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
        Mevcut adımdan başlar, bir duraklama noktasına (WAIT) veya bitişe (END) kadar ilerler.
        """
        step_id = current_step_id or self.start_step
        history = []

        while step_id and step_id != 'END':
            step = self.steps.get(step_id)
            if not step:
                break

            history.append(f"Running: {step_id}")
            
            # 1.Action (Eylem) Var mı? (Örn: E-posta at, Statü güncelle)
            if 'action' in step:
                self._execute_action(step['action'], context_data)

            # 2.Transition (Geçiş) Mantığı
            next_step = None
            
            # Eğer tip 'condition' (Karar) ise
            if step.get('type') == 'condition':
                if self._evaluate(step['condition'], context_data):
                    next_step = step.get('true_step')
                else:
                    next_step = step.get('false_step')
            
            # Eğer tip 'task' (Görev) ise ve onay bekleniyorsa dur
            elif step.get('type') == 'approval':
                return {
                    'status': 'WAITING', 
                    'current_step': step_id, 
                    'context': context_data,
                    'history': history
                }
            
            # Düz geçiş
            else:
                next_step = step.get('next_step')

            # Döngü için adımı güncelle
            step_id = next_step or 'END'

        return {
            'status': 'COMPLETED', 
            'current_step': 'END', 
            'context': context_data,
            'history': history
        }

    def _evaluate(self, condition_str, data):
        try:
            # Python'un tehlikeli fonksiyonlarına erişimi kapatır
            return simple_eval(condition_str, names=data)
        except Exception as e:
            logging.error(f"Kural Hatası: {e}")
            return False

    def _execute_action(self, action_config, data):
        """
        Tanımlı eylemleri gerçekleştirir.
        """
        action_type = action_config.get('type')
        
        if action_type == 'update_status':
            # Veri içindeki statüyü güncelle
            data['status'] = action_config.get('value')
            print(f"⚡ ACTION: Statü '{action_config.get('value')}' olarak güncellendi.")
            
        elif action_type == 'send_email':
            to = action_config.get('to')
            subject = action_config.get('subject')
            print(f"📧 EMAIL: {to} adresine '{subject}' konulu mail atıldı.")
        # Buraya webhook, SMS vb.eklenebilir.
        elif action_type == 'trigger_n8n':
            from app.services.n8n_client import N8NClient
            webhook = action_config.get('webhook')
            payload = action_config.get('payload', {})
            
            # Context verisini payload ile birleştir
            full_payload = {**data, **payload} 
            
            N8NClient.trigger(webhook, full_payload)
            print(f"🔗 WORKFLOW: n8n '{webhook}' tetiklendi.")
            
        