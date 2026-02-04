from .form import Form
from html import escape
from typing import List, Dict, Any

class MultiStepForm(Form):
    """
    Çok adımlı form sınıfı
    Backend rendering + Frontend JavaScript entegrasyonu
    """
    
    def __init__(self, name: str, steps: List[Dict[str, Any]], **kwargs):
        """
        Args:
            name: Form adı
            steps: Adım listesi
        """
        title = kwargs.get('title', name)
        super().__init__(name, title, **kwargs)
        
        self.steps: List[Dict[str, Any]] = steps
        self.current_step: int = 0
        self.progress: int = 0
        
        # ✅ Form ID ve Class'ı güvenli şekilde ayarla
        # Önce base class'dan gelen değerleri kontrol et
        if not hasattr(self, 'form_id'):
            self.form_id = None
        
        if not hasattr(self, 'form_class'):
            self.form_class = ''
        
        # Şimdi wizard-specific değerleri ata
        if not self.form_id:
            self.form_id = kwargs.get('form_id', f"wizard_{name}")
        
        # Wizard class'ını ekle (varolan class'ları koruyarak)
        wizard_class = 'form-wizard'
        if self.form_class:
            if wizard_class not in self.form_class:
                self.form_class += f' {wizard_class}'
        else:
            self.form_class = wizard_class
        
        # Tüm adımlardaki field'ları ana forma kaydet
        for step in steps:
            for field in step.get('fields', []):
                self.add_field(field)
        
        self.update_progress()

    def update_progress(self):
        """Progress yüzdesini hesapla"""
        if len(self.steps) > 0:
            self.progress = round((self.current_step + 1) / len(self.steps) * 100)
        else:
            self.progress = 0
    
    def get_step_count(self) -> int:
        """Toplam adım sayısı"""
        return len(self.steps)
    
    def get_current_step_data(self) -> Dict[str, Any]:
        """Mevcut adımın tüm bilgilerini döndür"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return {}
    
    def get_current_fields(self):
        """Mevcut adımın field'ları"""
        return self.get_current_step_data().get('fields', [])

    def get_current_title(self) -> str:
        """Mevcut adımın başlığı"""
        return self.get_current_step_data().get('title', f"Adım {self.current_step + 1}")
    
    def get_current_description(self) -> str:
        """Mevcut adımın açıklaması"""
        return self.get_current_step_data().get('description', '')

    def is_last_step(self) -> bool:
        """Son adımda mıyız?"""
        return self.current_step == len(self.steps) - 1

    def is_first_step(self) -> bool:
        """İlk adımda mıyız? """
        return self.current_step == 0
    
    def next_step(self) -> bool:
        """Sonraki adıma geç"""
        if not self.is_last_step():
            self.current_step += 1
            self.update_progress()
            return True
        return False
    
    def prev_step(self) -> bool:
        """Önceki adıma geç"""
        if not self.is_first_step():
            self.current_step -= 1
            self.update_progress()
            return True
        return False
    
    def go_to_step(self, step_number: int) -> bool:
        """Belirli bir adıma git"""
        if 0 <= step_number < len(self.steps):
            self.current_step = step_number
            self.update_progress()
            return True
        return False

    def render(self) -> str:
        """Wizard form'unu HTML olarak render et"""
        html_parts = []
        
        # Form başlangıcı
        method = getattr(self, 'method', 'POST').upper()
        action = getattr(self, 'action', '')
        action_attr = f' action="{escape(action)}"' if action else ''
        enctype = ' enctype="multipart/form-data"' if self._has_file_upload() else ''
        form_id_attr = f' id="{self.form_id}"' if self.form_id else ''
        form_class_attr = f' class="{self.form_class}"' if self.form_class else ''
        data_steps = f' data-wizard-steps="{self.get_step_count()}"'
        
        html_parts.append(
            f'<form method="{method}"{action_attr}{enctype}{form_id_attr}{form_class_attr}{data_steps}>'
        )
        
        # CSRF Token
        html_parts.append(self._render_csrf_token())
        
        # ✅ Modern Step Indicators (Boş container - JavaScript dolduracak)
        html_parts.append('''
        <div class="wizard-progress mb-4">
            <div class="wizard-steps-indicator">
                <!-- JavaScript buraya step indicators ekleyecek -->
            </div>
        </div>
        ''')
        
        # Her adımı render et
        for step_index, step in enumerate(self.steps):
            step_num = step_index + 1
            title = step.get('title', f'Adım {step_num}')
            description = step.get('description', '')
            fields = step.get('fields', [])
            
            display_style = '' if step_num == 1 else ' style="display: none;"'
            
            html_parts.append(f'<div class="wizard-step" data-step="{step_num}"{display_style}>')
            html_parts.append(f'<h4 class="wizard-step-title">{escape(title)}</h4>')
            
            if description:
                html_parts.append(f'<p class="text-muted">{escape(description)}</p>')
            
            for field in fields:
                html_parts.append(field.render())
            
            html_parts.append('</div>')
        
        # ✅ Navigation Buttons (Modern)
        html_parts.append('''
        <div class="wizard-navigation">
            <button type="button" class="btn btn-wizard-prev" style="display: none;">
                <i class="fas fa-arrow-left me-2"></i> Geri
            </button>
            <button type="button" class="btn btn-wizard-next">
                İleri <i class="fas fa-arrow-right ms-2"></i>
            </button>
            <button type="submit" class="btn btn-wizard-submit d-none">
                <i class="fas fa-check me-2"></i> Gönder
            </button>
        </div>
        ''')
        
        html_parts.append('</form>')
        
        return '\n'.join(html_parts)
    
    def _render_csrf_token(self) -> str:
        """CSRF token render et"""
        from flask import session
        
        if 'csrf_token' in session:
            return f'<input type="hidden" name="csrf_token" value="{session["csrf_token"]}">'
        return ''
    
    def _has_file_upload(self) -> bool:
        """Form'da file upload var mı?"""
        return any(
            field.is_file_input() 
            for step in self.steps 
            for field in step.get('fields', [])
        )

    def validate_current_step(self) -> bool:
        """Mevcut adımı doğrula"""
        is_valid = True
        
        for field in self.get_current_fields():
            if not field.validate():
                is_valid = False
        
        return is_valid
    
    def validate_all_steps(self) -> bool:
        """Tüm adımları doğrula"""
        all_valid = True
        
        for step in self.steps:
            for field in step.get('fields', []):
                if not field.validate():
                    all_valid = False
        
        return all_valid