# app/form_builder/multi_step_form.py

from .form import Form
from html import escape
from typing import List, Dict, Any, Tuple, Callable

class MultiStepForm(Form):
    """
    Enterprise Çok Adımlı Form (Wizard) Sınıfı.
    - LocalStorage Otomatik Kayıt (Auto-Save)
    - Adım Bazlı Doğrulama Hook'ları (Step Validators)
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
        
        # ✨ YENİ: Adım Bazlı Doğrulama Hook'ları
        self.step_validators: Dict[int, Callable] = {}
        
        # ✨ YENİ: Otomatik Kayıt Ayarları
        self.auto_save = False
        self.storage_key = f"wizard_{self.name}"
        self.auto_save_js = ""
        
        # Form ID ve Class'ı güvenli şekilde ayarla
        if not hasattr(self, 'form_id'):
            self.form_id = None
        
        if not hasattr(self, 'form_class'):
            self.form_class = ''
        
        if not self.form_id:
            self.form_id = kwargs.get('form_id', f"wizard_{name}")
        
        wizard_class = 'form-wizard'
        if self.form_class:
            if wizard_class not in self.form_class:
                self.form_class += f' {wizard_class}'
        else:
            self.form_class = wizard_class

    def set_step_validator(self, step_index: int, validator_func: Callable) -> 'MultiStepForm':
        """
        Belirli bir adım için özel backend doğrulama kuralı ekler.
        validator_func, form_data'yı alıp (is_valid: bool, errors: dict) dönmelidir.
        """
        self.step_validators[step_index] = validator_func
        return self

    def can_proceed_to_next(self, form_data: dict) -> Tuple[bool, dict]:
        """
        Mevcut adımdan sonrakine geçilip geçilemeyeceğini kontrol eder.
        """
        validator = self.step_validators.get(self.current_step)
        if validator:
            is_valid, errors = validator(form_data)
            return is_valid, errors
        return True, {}

    def enable_auto_save(self, storage_key: str = None) -> 'MultiStepForm':
        """
        Kullanıcı formu doldururken verilerin tarayıcıda (LocalStorage) tutulmasını sağlar.
        Sayfa yenilense bile veri kaybolmaz.
        """
        self.auto_save = True
        if storage_key:
            self.storage_key = storage_key
            
        self.auto_save_js = f"""
        <script>
        document.addEventListener("DOMContentLoaded", function() {{
            const storageKey = '{self.storage_key}';
            const $form = $('#{self.form_id}');
            
            if ($form.length === 0) return;

            // 1. Veriyi Geri Yükle (Sayfa açıldığında)
            const savedData = localStorage.getItem(storageKey);
            if (savedData) {{
                try {{
                    const parsed = JSON.parse(savedData);
                    parsed.forEach(item => {{
                        const $input = $form.find(`[name="${{item.name}}"]`);
                        if ($input.length > 0) {{
                            if ($input.is(':radio') || $input.is(':checkbox')) {{
                                $form.find(`[name="${{item.name}}"][value="${{item.value}}"]`).prop('checked', true);
                            }} else {{
                                $input.val(item.value);
                                // Select2 kullanılıyorsa UI'ı tetikle
                                if ($input.hasClass('select2-hidden-accessible')) {{
                                    $input.trigger('change.select2');
                                }}
                            }}
                        }}
                    }});
                }} catch(e) {{ console.error('Wizard Auto-Save Geri Yükleme Hatası:', e); }}
            }}

            // 2. Her Değişiklikte Kaydet (Kullanıcı yazarken)
            $form.on('change input', 'input, select, textarea', function() {{
                const formData = $form.serializeArray();
                localStorage.setItem(storageKey, JSON.stringify(formData));
            }});

            // 3. Form Başarıyla Gönderildiğinde Temizle! (Çok Önemli)
            $form.on('submit', function() {{
                localStorage.removeItem(storageKey);
            }});
        }});
        </script>
        """
        return self

    def get_current_fields(self):
        """Mevcut adımın alanlarını döndür"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step].get('fields', [])
        return []
    
    def render(self) -> str:
        """Form HTML'ini oluştur"""
        html_parts = []
        
        # Form Başlangıcı
        enctype = 'enctype="multipart/form-data"' if self._has_file_upload() else ''
        html_parts.append(
            f'<form id="{self.form_id}" class="{self.form_class}" method="{self.method}" '
            f'action="{self.action}" {enctype}>'
        )
        
        html_parts.append(self._render_csrf_token())
        
        # Adım Göstergesi (Steppers)
        html_parts.append('<div class="wizard-stepper mb-4 d-flex justify-content-between">')
        for i, step in enumerate(self.steps):
            active_class = "active" if i == self.current_step else "completed" if i < self.current_step else ""
            icon = step.get('icon', 'fas fa-circle')
            html_parts.append(f'''
            <div class="step {active_class}" data-step="{i}">
                <div class="step-icon"><i class="{icon}"></i></div>
                <div class="step-label">{step.get("title", f"Adım {i+1}")}</div>
            </div>
            ''')
        html_parts.append('</div>')
        
        # Adım İçerikleri (Sadece aktif adımı gösteririz veya tümünü JS için gizleriz)
        html_parts.append('<div class="wizard-content card shadow-sm mb-3"><div class="card-body">')
        
        for i, step in enumerate(self.steps):
            display = "block" if i == self.current_step else "none"
            html_parts.append(f'<div class="wizard-step-pane" id="step_pane_{i}" style="display: {display};">')
            html_parts.append(f'<h4 class="border-bottom pb-2 mb-4 text-primary">{step.get("title")}</h4>')
            
            # Adımdaki Field'ları render et
            fields = step.get('fields', [])
            for field in fields:
                html_parts.append(field.render())
                
            html_parts.append('</div>')
            
        html_parts.append('</div></div>')
        
        # Butonlar
        html_parts.append('''
        <div class="wizard-buttons d-flex justify-content-between mt-3">
            <button type="button" class="btn btn-secondary btn-wizard-prev d-none">
                <i class="fas fa-arrow-left me-2"></i> Geri
            </button>
            <button type="button" class="btn btn-primary btn-wizard-next">
                İleri <i class="fas fa-arrow-right ms-2"></i>
            </button>
            <button type="submit" class="btn btn-success btn-wizard-submit d-none">
                <i class="fas fa-check me-2"></i> Gönder
            </button>
        </div>
        ''')
        
        html_parts.append('</form>')
        
        # ✨ YENİ: Varsa Otomatik Kayıt JS kodunu HTML'in sonuna ekle
        if self.auto_save:
            html_parts.append(self.auto_save_js)
        
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
            hasattr(field, 'is_file_input') and field.is_file_input() 
            for step in self.steps 
            for field in step.get('fields', [])
        )

    def validate_current_step(self) -> bool:
        """Mevcut adımı doğrula (Tüm alanların validasyonunu çalıştırır)"""
        is_valid = True
        
        for field in self.get_current_fields():
            if hasattr(field, 'validate') and not field.validate():
                is_valid = False
        
        return is_valid
    
    def validate_all_steps(self) -> bool:
        """Tüm adımları baştan sona doğrula (Submit aşamasında çağrılır)"""
        is_valid = True
        for step in self.steps:
            for field in step.get('fields', []):
                if hasattr(field, 'validate') and not field.validate():
                    is_valid = False
        return is_valid