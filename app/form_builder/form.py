# form_builder/form.py
from typing import List, Dict, Any, Optional, Set
from flask import session, request
from .field_types import FieldType
from .form_field import FormField
from .form_style import FormStyle
from .utils import validate_file_security
import uuid
import secrets
from flask_wtf.csrf import generate_csrf, validate_csrf

class Form:
    def __init__(
        self, 
        name: str, 
        title: str = "", 
        action: str = "", 
        method: str = "POST",
        show_title: bool = True,
        submit_text: str = "Gönder",
        submit_class: str = "btn btn-primary",
        reset_text: str = "Sıfırla",
        reset_class: str = "btn btn-secondary", 
        form_class: str = "needs-validation", 
        form_id: str = None, 
        ajax: bool = False,
        ajax_reset: bool = True,
        ajax_callback: str = None,
        ajax_redirect: bool = False,
        view_mode=False,
        style: Optional[FormStyle] = None,
        **kwargs
    ):
        self.name = name
        self.title = title
        self.action = action
        self.method = method  
        self.view_mode = view_mode
        self.show_title = show_title
        
        # ✅ Form ID (Wizard için gerekli)
        self.form_id = form_id or f"form_{name}"
        
        # AJAX Ayarları
        self.ajax = ajax
        self.ajax_reset = ajax_reset
        self.ajax_callback = ajax_callback
        self.ajax_redirect = ajax_redirect
        self.extra_context = kwargs.get('extra_context', {})

        self.fields: List[FormField] = []
        self.errors: Dict[str, str] = {}
        self.csrf_token_field = None

        self.style = style if style else FormStyle()

        # Buton Özelleştirmeleri
        self.submit_text = submit_text
        self.reset_text = reset_text
        self.submit_class = submit_class
        self.reset_class = reset_class
        self.form_class = form_class

        self.data = {}
        self.layout_html = ""
        self._get_csrf_token()    

    def set_layout_html(self, html_content):
        self.layout_html = html_content
        return self
    
    def _get_csrf_token_sil(self):
        """
        CSRF token'ı oluşturur veya mevcut olanı döndürür.
        Request context yoksa (terminal test gibi) None döner.
        """
        try:
            if 'csrf_token' not in session:
                session['csrf_token'] = secrets.token_hex(16)
            return session['csrf_token']
        except RuntimeError:
            # Request context dışında (örn: terminal test, script)
            return None

    # --- ESKİ _get_csrf_token METODUNU SİLİN VE BUNU YAPIŞTIRIN ---
    def _get_csrf_token(self):
        """
        Flask-WTF kütüphanesini kullanarak standart ve güvenli token üretir.
        """
        try:
            # Flask-WTF'in kendi fonksiyonunu kullanıyoruz
            return generate_csrf()
        except RuntimeError:
            # Request context dışında (test ortamı vb.)
            return None

    # --- ESKİ validate_csrf METODUNU SİLİN VE BUNU YAPIŞTIRIN ---

    def validate_csrf(self):
        """
        CSRF token'ı Flask-WTF kütüphanesi ile doğrular.
        """
        if self.method.upper() == 'POST':
            try:
                # Formdan gelen token'ı al
                token = request.form.get('csrf_token')
                
                # Flask-WTF'in doğrulama fonksiyonunu kullan
                # Bu fonksiyon token geçerli değilse ValidationError fırlatır
                validate_csrf(token)
                return True
                
            except Exception as e:
                # Token geçersizse veya süresi dolmuşsa
                self.errors['csrf'] = "Güvenlik (CSRF) hatası: Oturum süreniz dolmuş olabilir."
                return False
                
        return True

    def validate_csrfSil(self):
        """CSRF token'ı doğrular."""
        if self.method.upper() == 'POST':
            try:
                token = request.form.get('csrf_token')
                session_token = session.get('csrf_token')
                
                if not token or not session_token or token != session_token:
                    self.errors['csrf'] = "Oturum süreniz dolmuş veya geçersiz istek."
                    return False
                    
            except RuntimeError:
                # Request context dışında (test ortamı)
                return True
                
        return True

    def add_field(self, field):
        """Tek bir alan ekler"""
        self.fields.append(field)
        return field
    
    def add_fields(self, *fields):
        """Birden fazla alanı aynı anda forma ekler."""
        for field in fields:  
            field.view_mode = self.view_mode
            self.add_field(field)
        return self
    
    # ✅ YENİ EKLEME: process_request metodu
    def process_request(self, form_data, files=None):
        """
        Flask request.form ve request.files verilerini işler
        
        Args:
            form_data: request.form (ImmutableMultiDict)
            files: request.files (opsiyonel)
        """
        # Field'lara veri yükle
        self.load_data(form_data)
        
        # File upload varsa işle
        if files:
            for field in self.fields:
                if field.is_file_input():
                    file_obj = files.get(field.name)
                    if file_obj and file_obj.filename:
                        # Dosya güvenlik kontrolü
                        is_safe, result = validate_file_security(
                            file_obj, 
                            allowed_types=self._get_allowed_type(field),
                            max_size_mb=field.max_file_size
                        )
                        
                        if is_safe:
                            field.set_value(result)  # Güvenli dosya adı
                        else:
                            self.errors[field.name] = result  # Hata mesajı
        
        return self
    
    def load_data(self, data):
        """
        Form verilerini (request.form) alanlara yükler.
        Artık her alan kendi verisini process_incoming_data ile işler.
        """
        for field in self.fields:
            field.process_incoming_data(data)

    def get_all_assets(self) -> Dict[str, Set[str]]:
        """
        Formdaki tüm alanları tarar ve gereken benzersiz CSS/JS dosyalarını döndürür.
        """
        assets = {'css': set(), 'js': set()}
        for field in self.fields:
            req = field.get_required_assets()
            if req:
                assets['css'].update(req['css'])
                assets['js'].update(req['js'])
        return assets

    def validate(self, data=None, files=None):
        """
        Form validasyonu (Master-Detail Düzeltilmiş - Dict/Object Destekli)
        """
        self.errors = {}
        
        # 1.Veri Kaynağını Belirle
        if data is None:
            data = request.form if request else {}

        # 2.CSRF Kontrolü
        if not self.validate_csrf():
            return False

        # 3.Verileri field nesnelerine yükle
        self.load_data(data)

        valid = True
        
        for field in self.fields:
            # --- A) DOSYA KONTROLLERİ ---
            if field.is_file_input():
                current_files = files if files is not None else (request.files if request else {})
                file_obj = current_files.get(field.name) if field.field_type != FieldType.FILES else None
                
                if field.required and (not file_obj or not file_obj.filename):
                    if not field.value: 
                        self.errors[field.name] = "Dosya seçimi zorunludur."
                        valid = False
                    continue
                
                if file_obj and file_obj.filename:
                    is_safe, msg = validate_file_security(
                        file_obj, 
                        allowed_types=self._get_allowed_type(field), 
                        max_size_mb=field.max_file_size
                    )
                    if not is_safe:
                        self.errors[field.name] = msg
                        valid = False
                    else:
                        field.set_value(msg)

            # --- B) MASTER-DETAIL KONTROLLERİ (GÜNCELLENDİ) ---
            elif field.field_type == FieldType.MASTER_DETAIL:
                row_count = 0
                
                if field.columns:
                    # 1.Satır Sayısını Bul
                    first_col = field.columns[0]
                    # Dict mi Obje mi kontrolü
                    first_col_name = first_col.get('name') if isinstance(first_col, dict) else first_col.name
                    
                    # Olası input ismi: "detaylar_stok_id[]"
                    input_name = f"{field.name}_{first_col_name}[]"
                    
                    if hasattr(data, 'getlist'):
                        row_list = data.getlist(input_name)
                        # Eğer boşsa prefixsiz isme bak
                        if not row_list: 
                            row_list = data.getlist(f"{first_col_name}[]")
                        
                        row_count = len(row_list)
                
                # Hiç satır yoksa ve zorunluysa hata ver
                if field.required and row_count == 0:
                    self.errors[field.name] = "En az bir satır eklemelisiniz."
                    valid = False
                    continue

                # 2.Sütun Değerlerini Kontrol Et
                for col in field.columns:
                    # --- KRİTİK DÜZELTME BURASI ---
                    # Kolon özelliklerini güvenli şekilde al
                    if isinstance(col, dict):
                        c_name = col.get('name')
                        c_label = col.get('label', c_name)
                        c_required = col.get('required', False)
                    else:
                        c_name = col.name
                        c_label = getattr(col, 'label', c_name)
                        c_required = getattr(col, 'required', False)
                    # ------------------------------

                    # Olası anahtar isimleri
                    keys_to_try = [
                        f"{field.name}_{c_name}[]",
                        f"{field.name}_{c_name}",
                        f"{c_name}[]",
                        c_name
                    ]
                    
                    col_values = []
                    if hasattr(data, 'getlist'):
                        for key in keys_to_try:
                            vals = data.getlist(key)
                            if vals:
                                col_values = vals
                                break 
                    
                    # Her satırı gez
                    for i in range(row_count):
                        val = col_values[i] if i < len(col_values) else ""
                        
                        # Zorunluluk Kontrolü
                        if c_required and not str(val).strip():
                            self.errors[f"{field.name}_{i}_{c_name}"] = f"{i+1}.satırda {c_label} zorunludur."
                            valid = False

            # --- C) STANDART ALAN KONTROLLERİ ---
            else:
                if field.field_type not in [FieldType.HTML, FieldType.SCRIPT]:
                    if not field.validate():
                        self.errors[field.name] = field.error
                        valid = False
        
        return valid

    def _get_allowed_type(self, field):
        """Dosya tipi kontrolü için izin verilen türler"""
        if field.field_type == FieldType.IMAGE: 
            return 'image'
        if field.field_type == FieldType.VIDEO_RECORDER: 
            return 'video'
        if field.field_type == FieldType.AUDIO_RECORDER: 
            return 'audio'
        return ['image', 'document']

    def get_data(self) -> Dict[str, Any]:
        """Form verilerini dict olarak döndür"""
        return {field.name: field.value for field in self.fields}
    
    # ✅ YENİ EKLEME: get_errors metodu
    def get_errors(self) -> Dict[str, str]:
        """
        Validasyon hatalarını döndür
        AJAX response'lar için kullanılır
        """
        return self.errors.copy()
        
    def render(self) -> str:
        """Formu HTML olarak render eder."""
        
        # 1.Formda Dosya Yükleme Alanı Var mı Kontrol Et
        has_file_upload = False
        for field in self.fields:
            if field.field_type in [FieldType.FILE, FieldType.FILES, FieldType.IMAGE, FieldType.AUDIO_RECORDER, FieldType.VIDEO_RECORDER]:
                has_file_upload = True
                break
        
        # Varsa enctype ekle
        enctype_attr = ' enctype="multipart/form-data"' if has_file_upload else ''
        
        # CSRF Token
        csrf_token = self._get_csrf_token()
        csrf_html = ""
        if csrf_token:
            csrf_html = f'<input type="hidden" name="csrf_token" value="{csrf_token}">'
        
        validation_attrs = ' data-form-handler="true" data-realtime="true"'
        
        ajax_attrs = ''
        if self.ajax:
            ajax_attrs = ' data-ajax="true"'
            if not self.ajax_reset:
                ajax_attrs += ' data-reset="false"'
            if self.ajax_callback:
                ajax_attrs += f' data-callback="{self.ajax_callback}"'
            if self.ajax_redirect:
                ajax_attrs += ' data-redirect="true"'
        
        if getattr(self, 'server_validation', False):
            validation_attrs += ' data-server-validation="true"'
        
        form_id_attr = f' id="{self.form_id}"' if self.form_id else f' id="{self.name}"'
        
        # 👇 GÜNCELLENEN SATIR (enctype_attr eklendi)
        html_parts = [
            f'<form name="{self.name}" method="{self.method}" action="{self.action}" '
            f'class="{self.form_class}"{form_id_attr} novalidate{validation_attrs}{ajax_attrs}{enctype_attr}>'
        ]
        
        if csrf_html:
            html_parts.append(csrf_html)
        
        if self.show_title and self.title:
            html_parts.append(f'<h3 class="mb-4">{self.title}</h3>')
        
        if self.layout_html:
            html_parts.append(self.layout_html)
        else:
            for field in self.fields:
                html_parts.append(field.render())

        # ✅ BUTON GRUBU (GÜNCELLENDİ)
        # Eğer submit_text (Kaydet yazısı) None veya Boş ise butonu hiç basma!
        # Bu sayede 'Salt Okunur' modda buton gizlenir.
        if self.submit_text:
            html_parts.append('<div class="mt-4 d-flex gap-2 justify-content-end">')
            
            html_parts.append(f'<button type="submit" class="{self.submit_class}">{self.submit_text}</button>')
            
            if self.reset_text:
                html_parts.append(f'<button type="reset" class="{self.reset_class}">{self.reset_text}</button>')
            
            html_parts.append('</div>')
        
        html_parts.append('</form>')
        
        return '\n'.join(html_parts)

    def render_i18n_js(self):
        """
        Aktif dildeki çevirileri JSON formatında JS değişkenine atar.
        Bu sayede form-builder.js dosyası çevirileri buradan okur.
        """
        import json
        from flask_babel import gettext as _

        # JS tarafında ihtiyaç duyulan tüm metinleri buraya ekleyin
        translations = {
            'required': _('Bu alan zorunludur.'),
            'upload_button': _('Dosya Seç'),
            'remove': _('Kaldır'),
            'error_title': _('Hata'),
            'success_title': _('İşlem Başarılı'),
            'max_size_error': _('Dosya boyutu çok büyük.'),
            'network_error': _('Bir ağ hatası oluştu.'),
            'processing': _('İşleniyor...')
        }
        
        # Güvenli bir şekilde HTML içine script olarak basıyoruz
        return f'<script>window.FormBuilderI18n = {json.dumps(translations, ensure_ascii=False)};</script>'

    def render_assets_html(self):
        """
        Form için gerekli tüm CSS ve JS taglerini oluşturur.
        Bunu template'de {{ form.render_assets_html()|safe }} olarak kullanabilirsiniz.
        """
        assets = self.get_all_assets()
        html_parts = []

        # Dosya isimlerini CDN URL'leri ile eşleştiren harita
        CDN_MAP = {
            # --- CSS ---
            'bootstrap-icons.min.css':'href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
            'leaflet.css': 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
            'quill.snow.css': 'https://cdn.quilljs.com/1.3.6/quill.snow.css',
            'nouislider.min.css': 'https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.7.1/nouislider.min.css',
            'select2.min.css': 'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css',
            'select2-bootstrap-5-theme.min.css': 'https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.min.css',            
            'classic.min.css': 'https://cdn.jsdelivr.net/npm/@simonwep/pickr/dist/themes/classic.min.css', 
            
            # --- JS ---
            'leaflet.js': 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'quill.min.js': 'https://cdn.quilljs.com/1.3.6/quill.min.js',
            'nouislider.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.7.1/nouislider.min.js',
            'select2.min.js': 'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js',
            'select2.tr.js': 'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/i18n/tr.js',
            'html5-qrcode.min.js': 'https://unpkg.com/html5-qrcode',
            'signature_pad.umd.js': 'https://cdn.jsdelivr.net/npm/signature_pad@4.1.7/dist/signature_pad.umd.min.js',
            'pickr.min.js': 'https://cdn.jsdelivr.net/npm/@simonwep/pickr/dist/pickr.min.js',
        }
        
        # CSS Dosyaları
        for css in sorted(assets['css']):
            # Eğer dosya CDN haritasında varsa oradan al, yoksa yerele bak
            url = CDN_MAP.get(css, f'/static/vendor/css/{css}')
            html_parts.append(f'<link rel="stylesheet" href="{url}">')
            
        # JS Dosyaları
        for js in sorted(assets['js']):
            url = CDN_MAP.get(js, f'/static/vendor/js/{js}')
            html_parts.append(f'<script src="{url}"></script>')

            # 👇 EĞER SELECT2 YÜKLENDİYSE, TR DİL DOSYASINI DA YÜKLE
            if js == 'select2.min.js':
                tr_url = CDN_MAP['select2.tr.js']
                html_parts.append(f'<script src="{tr_url}"></script>')

        
        # 1.Çeviri Scripti
        html_parts.append(self.render_i18n_js())
 
        # 2.Ana Form Builder Scripti (Bu dosya yereldir ve sizde mevcut)
        html_parts.append('<script src="/static/js/form-builder-validation.js"></script>')
        
        # 3.form-builder-validation.js (Validasyon scripti de yereldir)
        # Eğer bu dosyayı static altına koyduysanız buraya ekleyin, 
        # yoksa HTML şablonunda elle eklenmiş olabilir.
        #html_parts.append('<script src="/static/js/form-builder-validation.js"></script>')
            
        return '\n'.join(html_parts)

    def get_changed_fields(self, original_data: dict) -> dict:
        """Değişen alanları tespit et"""
        changed = {}
        for field in self.fields:
            if field.field_type in [FieldType.MASTER_DETAIL, FieldType.FILE, FieldType.IMAGE, FieldType.HTML, FieldType.SCRIPT]:
                continue
                
            if field.name in original_data:
                new_val = str(field.value) if field.value is not None else ""
                old_val = str(original_data[field.name]) if original_data[field.name] is not None else ""
                
                if new_val != old_val:
                    changed[field.name] = {'old': old_val, 'new': new_val}
        return changed

    @staticmethod
    def from_json(json_schema):
        """
        JSON verisinden Form nesnesi oluşturur.
        Örnek JSON:
        {
            "name": "contact_form",
            "title": "İletişim Formu",
            "fields": [
                {"name": "ad", "type": "text", "label": "Adınız", "required": true},
                {"name": "yas", "type": "number", "label": "Yaşınız"}
            ]
        }
        """
        # Formu başlat
        form = Form(
            name=json_schema.get('name', 'dynamic_form'),
            title=json_schema.get('title', ''),
            action=json_schema.get('action', ''),
            method=json_schema.get('method', 'POST')
        )
        
        # Alanları (Fields) döngüyle ekle
        for field_data in json_schema.get('fields', []):
            # FieldType enum'ını string'den bul
            # Örn: "text" -> FieldType.TEXT
            try:
                f_type_str = field_data.get('type', 'text').upper()
                f_type = FieldType[f_type_str] 
            except KeyError:
                f_type = FieldType.TEXT # Hata olursa varsayılan text
            
            # FormField nesnesini oluştur
            field = FormField(
                name=field_data.get('name'),
                field_type=f_type,
                label=field_data.get('label'),
                required=field_data.get('required', False),
                placeholder=field_data.get('placeholder', ''),
                help_text=field_data.get('help_text', ''),
                # Diğer özellikler buraya eklenebilir...
            )
            
            # Seçenekler (Select/Radio için)
            if 'options' in field_data:
                field.options = field_data['options']
                
            form.add_field(field)
            
        return form
    
    @property
    def fields_dict(self):
        return {f.name: f for f in self.fields}
    
    
    
    