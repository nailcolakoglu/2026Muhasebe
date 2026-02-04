# form_builder/form_field.py

from typing import Any, Optional, Dict, List, Union
from html import escape
from datetime import datetime
import re
import copy 
from markupsafe import Markup

from flask_babel import gettext as _ # Standart gettext
from .field_types import FieldType
from .validation_rules import Validator, ValidationRule
from .form_theme import BOOTSTRAP5_LIGHT, DARK_CARD


class FormField:
    def __init__(
        self, 
        name: str, 
        field_type: FieldType, 
        label: str, 
        conditional: dict = None, 
        show_if: dict = None, 
        theme=None, endpoint=None, **kwargs: Any) -> None:

        self.name = self._validate_name(name)
        self.field_type = field_type
        self.label = label
        self.theme = theme 
        self.view_mode = False
        # --- Standart Özellikler ---
        self.required = kwargs.get('required', False)
        self.placeholder = kwargs.get('placeholder', '')
        self.help_text = kwargs.get('help_text', '')
        self.default_value = kwargs.get('default_value') or kwargs.get('value', '')
        self.css_class = kwargs.get('css_class', '')
        self.disabled = kwargs.get('disabled', False)
        self.readonly = kwargs.get('readonly', False)
        
        # --- UX Özellikleri (Floating Label & Addons) ---
        self.floating_label = kwargs.get('floating_label', False)
        self.prepend_html = kwargs.get('prepend')
        self.append_html = kwargs.get('append')
        
        if self.floating_label and not self.placeholder:
            self.placeholder = self.label

        # --- Özel Konfigürasyonlar ---
        self.min_val = kwargs.get('min_val')
        self.max_val = kwargs.get('max_val')
        self.min_length = kwargs.get('min_length') or kwargs.get('minLength')
        self.max_length = kwargs.get('max_length')or kwargs.get('maxLength')
        self.pattern = kwargs.get('pattern')
        self.options = kwargs.get('options', [])
        self.inline = kwargs.get('inline', False)
        self.select2_config = kwargs.get('select2_config', {})
        self.data_source = kwargs.get('data_source', None)
        self.accept = kwargs.get('accept', '*/*')
        self.max_file_size = kwargs.get('max_file_size', 5)
        self.max_total_size = kwargs.get('max_total_size')
        self.preview = kwargs.get('preview', True)
        self.currency_symbol = kwargs.get('currency_symbol', '₺')
        self.max_rating = kwargs.get('max_rating', 5)
        self.step = kwargs.get('step', 1)
        self.map_default = kwargs.get('map_default', [39.925, 32.836])
        self.map_zoom = kwargs.get('map_zoom', 10)
        self.icon = kwargs.get('icon')
        self.strength_meter = kwargs.get('strength_meter', False)
        self.policy = kwargs.get('policy', {})
        
        # --- Layout ve Stil ---
        self.html_attributes = kwargs.get('html_attributes', {})
        self.container_class = kwargs.get('container_class', 'mb-3')
        self.column_class = kwargs.get('column_class', '')
        self.wrapper_div = kwargs.get('wrapper_div', True)
        self.custom_container = kwargs.get('custom_container', '')
        
        # JS Odaklanma Efektleri
        self.colorfocus = kwargs.get('colorfocus')
        self.colorblur = kwargs.get('colorblur')
        self.textfocus = kwargs.get('textfocus')
        self.textblur = kwargs.get('textblur')
        self.borderfocus = kwargs.get('borderfocus')
        self.borderblur = kwargs.get('borderblur')
        self.text_transform = kwargs.get('text_transform')
        self.input_mode = kwargs.get('input_mode')
        
        # Master-Detail ve Koşullu Alanlar
        self.columns = kwargs.get('columns', [])

        # --- KOŞULLU GÖSTERİM ---
        if show_if and not conditional:
            self.conditional = show_if
        else:
            self.conditional = conditional
        
        # ✅ Conditional field ise d-none ve conditional-field ekle
        if self.conditional:
            if 'd-none' not in self.container_class:
                self.container_class += ' d-none'
            if 'conditional-field' not in self.container_class:
                self.container_class += ' conditional-field'

        # Runtime Değerleri
        self.value = self.default_value
        self.error = ""
        self.is_valid = True
        
        self.validation_rules = []
        self._setup_validation_rules()

        self.endpoint = endpoint        
        # Eğer endpoint varsa, bunu html attribute olarak sakla (JS için)
        if self.endpoint:
            if self.html_attributes is None: self.html_attributes = {}
            self.html_attributes['data-auto-fetch'] = self.endpoint

    def _validate_name(self, name):
        if not name or not isinstance(name, str): raise ValueError("Field name zorunludur.")
        if not re.match(r'^[a-zA-Z0-9_-]+$', name): raise ValueError("Field name geçersiz karakter içeriyor.")
        return name.lower()
    
    def _setup_validation_rules(self):
        if self.field_type == FieldType.EMAIL: self.validation_rules.append(ValidationRule.EMAIL)
        if self.field_type == FieldType.TEL: self.validation_rules.append(ValidationRule.PHONE)
        if self.field_type == FieldType.TCKN: self.validation_rules.append(ValidationRule.TCKN)
        if self.field_type == FieldType.VKN: self.validation_rules.append(ValidationRule.VKN)
        if self.field_type == FieldType.IBAN: self.validation_rules.append(ValidationRule.IBAN)
        if self.field_type == FieldType.PLATE: self.validation_rules.append(ValidationRule.PLATE)
        if self.field_type == FieldType.OTP: self.validation_rules.append(ValidationRule.OTP)
        if self.field_type in [FieldType.DATE, FieldType.TARIH]: self.validation_rules.append(ValidationRule.DATE)
        if self.field_type == FieldType.TCKN_VKN: self.validation_rules.append(ValidationRule.TCKN_VKN)
        
        if self.min_length or self.max_length: self.validation_rules.append(ValidationRule.LENGTH)
        if self.min_val or self.max_val: self.validation_rules.append(ValidationRule.NUMBER_RANGE)
        if self.pattern: self.validation_rules.append(ValidationRule.PATTERN)

    def set_show_if(self, field, value):
        """Kolay koşul tanımı"""
        self.conditional = {'field': field, 'value': value}
        return self

    def get_required_assets(self) -> Dict[str, List[str]]:
        assets = {'css': [], 'js': []}
        if self.field_type == FieldType.RICHTEXT:
            assets['css'].append('quill.snow.css')
            assets['js'].append('quill.min.js')
        elif self.field_type in [FieldType.SELECT, FieldType.TAGS]:
            assets['css'].append('select2.min.css')
            assets['css'].append('select2-bootstrap-5-theme.min.css')
            assets['js'].append('select2.min.js') 
        elif self.field_type == FieldType.COLOR_PICKER_ADVANCED:
            assets['css'].append('classic.min.css') # Pickr Teması
            assets['js'].append('pickr.min.js')     # Pickr JS Kütüphanesi
        elif self.field_type == FieldType.SIGNATURE:
            assets['js'].append('signature_pad.umd.js')
        elif self.field_type == FieldType.MAP_POINT:
            assets['css'].append('leaflet.css')
            assets['js'].append('leaflet.js')
        elif self.field_type in [FieldType.SLIDER, FieldType.RANGE_DUAL]:
            assets['css'].append('nouislider.min.css')
            assets['js'].append('nouislider.min.js')
        elif self.field_type == FieldType.BARCODE:
            assets['js'].append('html5-qrcode.min.js')
        elif self.field_type in [FieldType.CREDIT_CARD, FieldType.TEL, FieldType.PLATE, FieldType.IP]:
            # Eğer yerel dosyanız yoksa CDN kullanabilirsiniz veya dosyayı indirip static klasörüne atabilirsiniz
            assets['js'].append('https://unpkg.com/imask')
        return assets

    def process_incoming_data(self, form_data):
        if self.field_type in [FieldType.HTML, FieldType.SCRIPT, FieldType.HEADER, FieldType.HR]:
            return
        if self.is_file_input():
            return

        if self.field_type == FieldType.DATE_RANGE:
            self.value = {
                'start': form_data.get(f"{self.name}_start", ""),
                'end': form_data.get(f"{self.name}_end", "")
            }
        elif self.field_type == FieldType.MAP_POINT:
            lat = form_data.get(f"{self.name}_lat")
            lng = form_data.get(f"{self.name}_lng")
            if lat and lng:
                self.value = f"{lat},{lng}"
            elif self.name in form_data:
                self.value = form_data.get(self.name)
        elif self.field_type == FieldType.RANGE_DUAL:
            self.value = {
                'min': form_data.get(f"{self.name}_min", ""),
                'max': form_data.get(f"{self.name}_max", "")
            }
        elif self.field_type == FieldType.MASTER_DETAIL:
            # Master-Detail verileri genellikle list olarak gelir, 
            # ancak burada ana value işlemesi yapılmaz, routes tarafında getlist ile alınır.
            pass
        else:
            # Standart Alanlar
            lookup_name = f"{self.name}[]" if self.is_multiple_select() else self.name
            if lookup_name in form_data:
                if self.is_multiple_select() and hasattr(form_data, 'getlist'):
                    self.value = form_data.getlist(lookup_name)
                else:
                    self.value = form_data.get(lookup_name)
            elif self.name in form_data:
                self.value = form_data.get(self.name)


        # ✅ OTOMATİK DÖNÜŞÜMLER (YENİ EKLENEN KISIM)
        
        # 1.Para Birimi (1.250,50 -> 1250.50)
        if self.field_type == FieldType.CURRENCY:
            self.value = self._parse_currency(self.value)
            
        # 2.Sayısal Alanlar (Boşsa 0 yap)
        if self.field_type == FieldType.NUMBER and self.value == "":
            self.value = 0

    def _parse_currency(self, value):
        """
        Gelen string para değerini veritabanı dostu float'a çevirir.
        TR Formatı: 1.250,50 -> 1250.50
        """
        if value is None or value == "":
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
            
        if isinstance(value, str):
            # Sadece sayı, nokta, virgül ve eksi işaretine izin ver
            # (Güvenlik önlemi)
            clean_val = value.strip()
            
            # TR Formatı Kontrolü (Nokta varsa ve virgül varsa veya virgül sondaysa)
            if ',' in clean_val:
                # Binlik ayracı olan noktaları sil (1.250,00 -> 1250,00)
                clean_val = clean_val.replace('.', '')
                # Ondalık ayracı olan virgülü noktaya çevir (1250,00 -> 1250.00)
                clean_val = clean_val.replace(',', '.')
            else:
                # Virgül yoksa, sadece nokta varsa ve birden fazla nokta yoksa (1250.50)
                # Dokunma.Ama eğer (1.250) gibiyse ve kuruş yoksa dikkatli olmak lazım.
                # Standart olarak TR sisteminde nokta binliktir.
                # Ancak Python float("1.250") = 1.25 olarak anlar.
                # Bu yüzden nokta sayısı 1'den fazlaysa veya format belliyse silinmeli.
                pass 

            try:
                return float(clean_val)
            except ValueError:
                return 0.0
                
        return 0.0

    # --- BUILDER METODLARI ---
    def set_column_class(self, class_name: str) -> 'FormField':
        self.column_class = class_name
        return self
    
    def set_container_class(self, class_name: str) -> 'FormField':
        self.container_class = class_name
        return self

    def set_wrapper_div(self, enabled: bool = True) -> 'FormField':
        self.wrapper_div = enabled
        return self

    def set_custom_container(self, html_template: str) -> 'FormField':
        self.custom_container = html_template
        return self

    def in_row(self, column_classes: str) -> 'FormField':
        self.column_class = column_classes
        return self

    def in_card(self, title: str = "", card_class: str = "") -> 'FormField':
        header = f'<div class="card-header">{(title)}</div>' if title else ''
        self.custom_container = f'<div class="card {card_class}">{header}<div class="card-body">{{field_content}}</div></div>'
        return self
    
    def add_css_class(self, class_name: str) -> 'FormField':
        if self.css_class: self.css_class += f" {class_name}"
        else: self.css_class = class_name
        return self

    def add_html_attribute(self, key, value):
        self.html_attributes[key] = value
        return self
    
    def set_conditional(self, depends_on: str, condition: any = None):
        self.conditional = {'field': depends_on, 'value': condition}
        return self

    def set_value(self, value: Any) -> 'FormField':
        if self.field_type == FieldType.SELECT and self.select2_config.get('multiple'):
            if isinstance(value, list): self.value = value
            elif value: self.value = [str(value)]
            else: self.value = []
        else:
            self.value = value if value is not None else ""
        return self

    def is_multiple_select(self):
        return (self.field_type == FieldType.SELECT and self.select2_config.get('multiple', False))

    def is_file_input(self):
        return self.field_type in [FieldType.FILE, FieldType.IMAGE, FieldType.FILES, FieldType.AUDIO_RECORDER, FieldType.VIDEO_RECORDER]

    def _get_attrs_string(self):
        return self.get_html_attributes_string()

    def get_html_attributes_string(self):
        attrs = []
        if self.required: attrs.append('required')
        if self.disabled: attrs.append('disabled')
        if self.readonly: attrs.append('readonly')
        if self.placeholder: attrs.append(f'placeholder="{(str(self.placeholder))}"')
        if self.min_val is not None: attrs.append(f'min="{self.min_val}"')
        if self.max_val is not None: attrs.append(f'max="{self.max_val}"')
        if self.step is not None: attrs.append(f'step="{self.step}"')
        if self.min_length is not None: attrs.append(f'minlength="{self.min_length}"')
        if self.max_length is not None: attrs.append(f'maxlength="{self.max_length}"')
        if self.pattern: attrs.append(f'pattern="{(self.pattern)}"')
        
        if self.data_source:
            if self.data_source.get('url'): attrs.append(f'data-source-url="{self.data_source["url"]}"')
            if self.data_source.get('method'): attrs.append(f'data-source-method="{self.data_source["method"]}"')
            if self.data_source.get('depends_on'): attrs.append(f'data-dependent-parent="{self.data_source["depends_on"]}"')

        if self.colorfocus: attrs.append(f'data-colorfocus="{escape(self.colorfocus)}"')
        if self.colorblur: attrs.append(f'data-colorblur="{escape(self.colorblur)}"')
        if self.textfocus: attrs.append(f'data-textfocus="{escape(self.textfocus)}"')
        if self.textblur: attrs.append(f'data-textblur="{escape(self.textblur)}"')
        if self.borderfocus: attrs.append(f'data-borderfocus="{escape(self.borderfocus)}"')
        if self.borderblur: attrs.append(f'data-borderblur="{escape(self.borderblur)}"')
        if self.text_transform: attrs.append(f'data-text-transform="{escape(self.text_transform)}"')
        if self.input_mode: attrs.append(f'inputmode="{escape(self.input_mode)}"')

        # =====================================================
        # ✅ YENİ: Validasyon için data attribute'ları
        # =====================================================
        
        # Field tipini JS'e bildir (client-side validasyon için)
        field_type_map = {
            FieldType.EMAIL: 'email',
            FieldType.TEL: 'tel',
            FieldType.TCKN: 'tckn',
            FieldType.VKN: 'vkn',
            FieldType.IBAN: 'iban',
            FieldType.PLATE: 'plate',
            FieldType.URL: 'url',
            FieldType.CURRENCY: 'currency',
            FieldType.CREDIT_CARD: 'credit_card',
            FieldType.DATE: 'date',
            FieldType.TARIH: 'tarih',
            FieldType.DATETIME: 'datetime',
            FieldType.TIME: 'time',
            FieldType.OTP: 'otp',
            FieldType.IP: 'ip',
            FieldType.NUMBER: 'number',
            FieldType.PASSWORD: 'password',
            FieldType.TCKN_VKN: 'tckn_vkn',
        }
        
        if self.field_type in field_type_map:
            attrs.append(f'data-type="{field_type_map[self.field_type]}"')
        
        # Validasyon kurallarını JSON olarak ekle
        validation_rules = self._get_validation_rules_json()
        if validation_rules:
            attrs.append(f"data-rules='{validation_rules}'")
        
        # =====================================================
        # Mevcut html_attributes döngüsü (en sonda kalmalı)
        # =====================================================
        for key, value in self.html_attributes.items():
            # DÜZELTME: Eğer anahtar 'class' ise atla (Çünkü get_css_classes içinde ekledik)
            if key == 'class': continue 
            
            attrs.append(f'{key}="{escape(str(value))}"')
        
        return ' ' + ' '.join(attrs) if attrs else ''

    def _get_validation_rules_json(self):
        """
        Validasyon kurallarını JSON formatında döndürür.
        Bu kurallar client-side JS tarafından okunur.
        """
        import json
        
        rules = []
        
        # Zorunluluk
        if self.required:
            rules.append('required')
        
        # Uzunluk kuralları
        if self.min_length:
            rules.append({
                'name': 'minLength', 
                'params': {'min': self.min_length}
            })
        
        if self.max_length:
            rules.append({
                'name': 'maxLength', 
                'params': {'max': self.max_length}
            })
        
        # Sayısal aralık kuralları
        if self.min_val is not None:
            rules.append({
                'name': 'min', 
                'params': {'min': self.min_val}
            })
        
        if self.max_val is not None:
            rules.append({
                'name': 'max', 
                'params': {'max': self.max_val}
            })
        
        # Pattern (Regex) kuralı
        if self.pattern:
            rules.append({
                'name': 'pattern', 
                'params': {'pattern': self.pattern}
            })
        
        # Dosya kuralları
        if self.field_type in [FieldType.FILE, FieldType.FILES, FieldType.IMAGE]:
            if self.max_file_size:
                rules.append({
                    'name': 'fileSize', 
                    'params': {'maxSize': self.max_file_size}
                })
            if self.accept and self.accept != '*/*':
                rules.append({
                    'name': 'fileType', 
                    'params': {'accept': self.accept}
                })
        
        # Kural yoksa None döndür
        if not rules:
            return None
        
        # JSON formatında döndür (escape için tek tırnak kullanıyoruz HTML'de)
        # eski return json.dumps(rules, ensure_ascii=False)
        # Öneri (HTML entity encode):
        import json
        json_str = json.dumps(rules, ensure_ascii=False)
        return escape(json_str) # Jinja2 veya html.escape kullanarak attribute'u kırmasını önleyin.

    def get_css_classes(self):
        base_classes = {
            # --- Temel Metin Girişleri ---
            FieldType.TEXT: "form-control",
            FieldType.PASSWORD: "form-control",
            FieldType.EMAIL: "form-control email-input",
            FieldType.NUMBER: "form-control",
            FieldType.URL: "form-control",
            FieldType.SEARCH: "form-control",
            FieldType.HIDDEN: "d-none", # Gizli alanlar için

            # --- Seçim Elemanları ---
            FieldType.SELECT: "form-select select2-field dx-form-control",
            FieldType.CHECKBOX: "form-check-input",
            FieldType.RADIO: "form-check-input",
            FieldType.SWITCH: "form-check-input switch-input",
            FieldType.TAGS: "form-control tags-input",
            FieldType.AUTOCOMPLETE: "form-control autocomplete-field",

            # --- Metin Editörleri ---
            FieldType.TEXTAREA: "form-control dx-form-control",
            FieldType.RICHTEXT: "form-control quill-editor", # Quill.js için
            FieldType.MARKDOWN: "form-control markdown-editor",
            FieldType.CODE_EDITOR: "form-control font-monospace code-editor",
            FieldType.JSON_EDITOR: "form-control json-editor font-monospace",

            # --- Tarih ve Zaman ---
            FieldType.DATE: "form-control date-input",
            FieldType.DATETIME: "form-control datetime-input",
            FieldType.TIME: "form-control time-input",
            FieldType.MONTH: "form-control month-input",
            FieldType.WEEK: "form-control week-input",
            FieldType.TARIH: "form-control tarih-input", # TR Format
            FieldType.DATE_RANGE: "form-control date-range-input",

            # --- Özel Maskeli Alanlar ---
            FieldType.TEL: "form-control phone-mask-tr",
            FieldType.IP: "form-control ip-mask",
            FieldType.TCKN: "form-control tckn-input",
            FieldType.IBAN: "form-control iban-input",
            FieldType.VKN: "form-control vkn-input",
            FieldType.CREDIT_CARD: "form-control credit-card-mask",
            FieldType.PLATE: "form-control plate-input",
            FieldType.CURRENCY: "form-control fiyat-input text-end fw-bold",
            FieldType.MASK: "form-control custom-mask", # Genel maske desteği

            # --- Medya ve Dosya ---
            FieldType.FILE: "form-control",
            FieldType.FILES: "form-control", # Çoklu dosya
            FieldType.IMAGE: "form-control image-input",
            FieldType.AUDIO_RECORDER: "d-none", # Genelde butonla yönetilir, input gizli olur
            FieldType.VIDEO_RECORDER: "d-none",

            # --- Görsel Araçlar ---
            FieldType.COLOR: "form-control form-control-color",
            FieldType.COLOR_PICKER_ADVANCED: "form-control advanced-color-picker",
            FieldType.RANGE: "form-range",
            FieldType.SLIDER: "dx-slider", # NoUiSlider vb.için
            FieldType.SIGNATURE: "d-none", # Canvas kullanılır, input gizli olur
            FieldType.DRAWING: "d-none",   # Canvas kullanılır, input gizli olur

            # --- Diğerleri ---
            FieldType.BUTTON: "btn btn-secondary", # Standart buton sınıfı
            FieldType.CALC: "form-control calc-input",
            FieldType.OTP: "form-control otp-input text-center",
            FieldType.RATING: "d-none", # Yıldızlar görünür, input gizli
            FieldType.BARCODE: "form-control barcode-input",
            FieldType.MAP_POINT: "form-control map-coords",
            FieldType.GEOLOCATION: "form-control geolocation-input",
            FieldType.AUTO_NUMBER: "form-control bg-light fw-bold", # Otomatik numara, readonly gibi görünsün
        }
        cls = base_classes.get(self.field_type, "form-control dx-form-control")
        if self.css_class: cls += f" {self.css_class}"
        
        # EKLENEN KISIM: html_attributes içinde class varsa onu da ana sınıfa dahil et
        if self.html_attributes and self.html_attributes.get('class'):
            cls += f" {self.html_attributes['class']}"

        if self.error: cls += " is-invalid"
        return cls

    def _get_field_icon(self):
        icons = {
            FieldType.TEXT: 'font', FieldType.EMAIL: 'envelope', FieldType.TEL: 'phone',
            FieldType.NUMBER: 'hashtag', FieldType.PASSWORD: 'lock', FieldType.HIDDEN: 'eye-slash',
            FieldType.DATE: 'calendar-alt', FieldType.TARIH: 'calendar-days', FieldType.DATETIME: 'calendar-plus',
            FieldType.TIME: 'clock', FieldType.MONTH: 'calendar', FieldType.WEEK: 'calendar-week',
            FieldType.DATE_RANGE: 'calendar-range', FieldType.SELECT: 'list', FieldType.TEXTAREA: 'align-left',
            FieldType.RICHTEXT: 'paragraph', FieldType.CHECKBOX: 'check-square', FieldType.RADIO: 'dot-circle',
            FieldType.MARKDOWN: 'file-code', FieldType.JSON_EDITOR: 'code', FieldType.URL: 'link',
            FieldType.COLOR: 'palette', FieldType.RANGE: 'sliders-h', FieldType.RANGE_DUAL: 'exchange-alt',
            FieldType.FILE: 'file-upload', FieldType.FILES: 'copy', FieldType.SEARCH: 'search',
            FieldType.SLIDER: 'sliders-h', FieldType.AUTOCOMPLETE: 'magic', FieldType.CURRENCY: 'lira-sign',
            FieldType.RATING: 'star', FieldType.SWITCH: 'toggle-on', FieldType.IMAGE: 'image',
            FieldType.TAGS: 'tags', FieldType.SIGNATURE: 'file-signature', FieldType.BUTTON: 'hand-pointer',
            FieldType.CALC: 'calculator', FieldType.MASTER_DETAIL: 'table', FieldType.AUDIO_RECORDER: 'microphone',
            FieldType.VIDEO_RECORDER: 'video', FieldType.DRAWING: 'pencil-ruler', FieldType.GEOLOCATION: 'map-marker-alt',
            FieldType.TCKN: 'id-card', FieldType.IBAN: 'money-check', FieldType.VKN: 'building',
            FieldType.OTP: 'shield-alt', FieldType.PLATE: 'car', FieldType.MAP_POINT: 'map-marked-alt',
            FieldType.BARCODE: 'qrcode', FieldType.CREDIT_CARD: 'credit-card', FieldType.IP: 'network-wired',
            FieldType.HTML: 'code', FieldType.SCRIPT: 'file-code', FieldType.MODAL: 'window-restore', FieldType.HR: 'dash-lg', FieldType.HEADER: 'type-h1'
        }
        icon_name = icons.get(self.field_type, 'edit')
        return f'<i class="fas fa-{icon_name} me-2"></i>'

    # --- ANA RENDER METODU ---
    
    def render(self):
        # --- Koşullu alan attribute ---
        if self.conditional:
            self.html_attributes['data-conditional-field'] = self.conditional.get('field')
            self.html_attributes['data-conditional-value'] = self.conditional.get("value")

        # --- Tema Class ekleme ---
        theme = self.theme or BOOTSTRAP5_LIGHT
        # theme.panel_class, theme.label_class vs.default atama
        self.container_class = self.container_class if self.container_class not in [None, '', 'mb-3'] else theme.panel_class
        self.label_class = self.label_class if hasattr(self, 'label_class') and self.label_class else theme.label_class
        self.field_class = self.field_class if hasattr(self, 'field_class') and self.field_class else theme.field_class
        self.help_class = self.help_class if hasattr(self, 'help_class') and self.help_class else theme.help_class
    

        # Custom container varsa...
        if self.custom_container:
            return self.custom_container.format(field_content=self._render_field_content())

        html_parts = []
        no_wrapper_types = [FieldType.HIDDEN, FieldType.SCRIPT, FieldType.HTML, FieldType.HR, FieldType.HEADER]
        should_wrap = self.wrapper_div and self.field_type not in no_wrapper_types
        if should_wrap:
            classes = [self.container_class]
            if self.column_class: classes.append(self.column_class)
            html_parts.append(f'<div class="{" ".join(classes)}" id="container_{self.name}">')

        html_parts.append(self._render_field_content())

        if should_wrap:
            html_parts.append('</div>')

        return '\n'.join(html_parts)

    def _render_field_content(self): 
        if self.view_mode:
            return self._render_read_only()
        parts = []
        no_label_types = [
            FieldType.CHECKBOX, FieldType.SWITCH, FieldType.BUTTON, 
            FieldType.HTML, FieldType.HIDDEN, FieldType.SCRIPT,
            FieldType.MODAL, FieldType.HR, FieldType.HEADER, FieldType.MASTER_DETAIL
        ]
        
        # Eğer Floating Label ise dışarıya etiket basma (Çift olmasın)
        if self.field_type not in no_label_types and not self.floating_label:
            parts.append(self._render_label())
            
        renderers = {
            # Metin Alanları
            FieldType.TEXTAREA: self._render_textarea,
            FieldType.SELECT: self._render_select,
            FieldType.CHECKBOX: self._render_checkbox,
            FieldType.RADIO: self._render_radio,
            FieldType.SWITCH: self._render_switch,
            FieldType.RICHTEXT: self._render_richtext,
            FieldType.SIGNATURE: self._render_signature,
            FieldType.JSON_EDITOR: self._render_json,
            FieldType.MARKDOWN: self._render_markdown,
            FieldType.CODE_EDITOR: self._render_code_editor,
            
            # Tarih ve Zaman
            FieldType.DATE: self._render_date,
            FieldType.DATETIME: self._render_datetime,
            FieldType.TIME: self._render_time,
            FieldType.MONTH: self._render_month,
            FieldType.WEEK: self._render_week,
            FieldType.TARIH: self._render_tarih,
            FieldType.DATE_RANGE: self._render_date_range,
            FieldType.DATE_TIME_RANGE: self._render_datetime_range,

            # Diğerleri
            FieldType.IMAGE: self._render_image,
            FieldType.FILES: self._render_files,
            FieldType.RANGE: self._render_range,
            FieldType.RANGE_DUAL: self._render_range_dual,
            FieldType.GEOLOCATION: self._render_geolocation,
            FieldType.MAP_POINT: self._render_map_point,
            FieldType.BARCODE: self._render_barcode,
            FieldType.BUTTON: self._render_button,
            FieldType.CALC: self._render_calc,
            FieldType.OTP: self._render_otp,
            FieldType.TAGS: self._render_tags,
            FieldType.RATING: self._render_rating,
            FieldType.CURRENCY: self._render_currency,
            FieldType.SEARCH: self._render_search,
            FieldType.AUDIO_RECORDER: self._render_media_recorder,
            FieldType.VIDEO_RECORDER: self._render_media_recorder,
            FieldType.DRAWING: self._render_drawing,
            FieldType.SLIDER: self._render_slider,
            FieldType.AUTOCOMPLETE: self._render_autocomplete,
            FieldType.COLOR: self._render_color, 
            FieldType.COLOR_PICKER_ADVANCED: self._render_color_advanced,
            FieldType.CAPTCHA: self._render_captcha,
            FieldType.MASK: self._render_mask,
            FieldType.MULTI_FIELD: self._render_multi_field,
            FieldType.MASTER_DETAIL: self._render_master_detail,
            FieldType.PASSWORD: lambda: self._render_password_with_meter() if self.strength_meter else self._render_input(),
            FieldType.HTML: self._render_html,
            FieldType.SCRIPT: self._render_script,
            FieldType.MODAL: self._render_modal,
            FieldType.HR: self._render_hr,       # YENİ
            FieldType.HEADER: self._render_header, # YENİ
            FieldType.AUTO_NUMBER: self._render_auto_number
        }

        renderer = renderers.get(self.field_type, self._render_input)
        parts.append(renderer())
            
        if self.field_type in [FieldType.SCRIPT, FieldType.HTML, FieldType.HIDDEN, FieldType.MODAL, FieldType.HR, FieldType.HEADER ]:
            return '\n'.join(parts)

        # Help text (Yardım Metni)
        if self.help_text and self.field_type not in [FieldType.CHECKBOX, FieldType.SWITCH, FieldType.CODE_EDITOR, FieldType.BUTTON]:
            parts.append(f'<div class="form-text">{(self.help_text)}</div>')
        
        if self.error:
            parts.append(f'<div class="invalid-feedback d-block">{(self.error)}</div>')
            
        return '\n'.join(parts)

    def _render_read_only(self):
        """Salt okunur modda alanı render eder (Bootstrap Plain Text)"""
        
        # 1.GÖRÜNTÜLENECEK DEĞERİ HAZIRLA
        display_val = self.value
        
        # A) Seçim Kutusu (Select) ise ID yerine Etiketi (Label) bul
        if self.field_type == FieldType.SELECT and self.options:
            for opt_val, opt_label in self.options:
                if str(opt_val) == str(self.value):
                    display_val = opt_label
                    break
        
        # B) Tarih ise formatla
        elif self.field_type in [FieldType.DATE, FieldType.TARIH] and self.value:
            try:
                # Eğer value string ise ve YYYY-MM-DD formatındaysa çevir
                if isinstance(self.value, str) and '-' in self.value:
                    from datetime import datetime
                    d = datetime.strptime(self.value, '%Y-%m-%d')
                    display_val = d.strftime('%d.%m.%Y')
                # Zaten date objesi ise
                elif hasattr(self.value, 'strftime'):
                    display_val = self.value.strftime('%d.%m.%Y')
            except:
                pass

        # C) Para Birimi ise
        elif self.field_type == FieldType.CURRENCY and self.value:
            try:
                val = float(self.value)
                display_val = f"{val:,.2f} ₺"
            except:
                pass
        
        # D) Resim ise (Özel Durum)
        elif self.field_type == FieldType.IMAGE:
            if self.value:
                src = self.value
                if not src.startswith('/static/') and not src.startswith('http'):
                    src = f"/static/{src}"
                return f'<div class="mb-2"><img src="{src}" class="img-thumbnail" style="max-height: 200px;"></div>'
            else:
                return '<div class="text-muted fst-italic">Görsel Yok</div>'

        # E) Boşsa
        if display_val is None or display_val == "":
            display_val = "-"

        # 2.HTML ÇIKTISI (Bootstrap Stilinde)
        # form-control-plaintext: Input gibi hizalar ama border/bg yoktur.
        return f'''
        <div class="form-control-plaintext border-bottom pb-1">
            <span class="fw-bold text-dark">{display_val}</span>
        </div>
        '''


    def validate(self, value: Optional[Any] = None) -> bool:
        """
        Sunucu tarafı validasyon
        Returns: bool (True=geçerli, False=hatalı)
        Hata mesajı self.error içinde saklanır
        """
        # Değer verilmişse güncelle
        if value is not None:
            self.set_value(value)
        
        # ✅ Başlangıç durumunu temizle
        self.error = ""
        self.is_valid = True
        
        # ✅ DATE_RANGE özel kontrolü (genel kontrollerden ÖNCE)
        if self.field_type == FieldType.DATE_RANGE:
            return self._validate_date_range(self.value)

        # HR, HEADER, HTML gibi tipler validasyon gerektirmez
        if self.field_type in [FieldType.HR, FieldType.HEADER, FieldType.HTML, FieldType.SCRIPT, FieldType.MODAL]:
            return True

        # ✅ Genel validasyon kontrolü
        is_valid, error_message = Validator.check(self, self.value)
        
        if not is_valid:
            self.error = error_message
            self.is_valid = False
            return False
        
        return True

    def _validate_date_range(self, value):
        start = None
        end = None
        if isinstance(value, dict):
            start = value.get('start')
            end = value.get('end')
        if self.required and (not start or not end):
            self.error = Validator.MESSAGES['required']
            self.is_valid = False
            return False
        if start and end:
            try:
                sdt = datetime.strptime(start, '%Y-%m-%d').date()
                edt = datetime.strptime(end, '%Y-%m-%d').date()
                if sdt > edt:
                    self.error = 'Başlangıç tarihi bitişten büyük olamaz'
                    self.is_valid = False
                    return False
            except:
                self.error = Validator.MESSAGES['invalid_date']
                self.is_valid = False
                return False
        return True 

    # --- ALT RENDERLAR ---

    def _render_label(self):
        required_span = '<span class="text-danger">*</span>' if self.required else ''
        icon_html = f'<i class="{self.icon} me-2"></i>' if self.icon else self._get_field_icon()
        default_val = escape(str(self.default_value)) if self.default_value else ""
        
        menu_html = f'''
        <div class="field-popup-wrapper ms-auto d-inline-block position-relative">
            <button type="button" class="btn btn-sm btn-link text-muted text-decoration-none p-0 field-menu-trigger" 
                    data-bs-toggle="dropdown" aria-expanded="false" tabindex="-1">
                <i class="fas fa-ellipsis-v"></i>
            </button>
            <ul class="dropdown-menu dropdown-menu-end field-popup-menu shadow">
                <li><button class="dropdown-item small" type="button" data-field-action="copy" data-target="{self.name}"><i class="fas fa-copy text-primary me-2"></i> Kopyala</button></li>
                <li><button class="dropdown-item small" type="button" data-field-action="paste" data-target="{self.name}"><i class="fas fa-paste text-info me-2"></i> Yapıştır</button></li>
                <li><hr class="dropdown-divider"></li>
                <li><button class="dropdown-item small" type="button" data-field-action="clear" data-target="{self.name}"><i class="fas fa-eraser text-danger me-2"></i> Temizle</button></li>
                <li><button class="dropdown-item small" type="button" data-field-action="reset" data-target="{self.name}" data-default="{default_val}"><i class="fas fa-undo text-secondary me-2"></i> Varsayılana Dön</button></li>
            </ul>
        </div>
        '''
        return f'<div class="d-flex justify-content-between align-items-center mb-1"><label for="{self.name}" class="form-label dx-form-label mb-0 text-truncate" style="max-width: 90%;">{icon_html}{escape(self.label)} {required_span}</label>{menu_html}</div>'

    def _render_html(self):
        if not self.value: return ""
        return Markup(str(self.value))

    def _render_script(self):
        attrs = self.get_html_attributes_string()
        if self.html_attributes.get('src'):
            return Markup(f'<script {attrs}></script>')
        val = str(self.value) if self.value else ""
        if not val: return ""
        return Markup(f'<script {attrs}>\n{val}\n</script>')

    def _render_button(self):
        return f'<button type="button" name="{self.name}" id="{self.name}" class="btn {self.css_class or "btn-secondary"}" {self._get_attrs_string()}>{escape(self.label)}</button>'

    def _render_input(self):
        """Standard input alanları için Tam Uyumlu Render (Floating + Addons + Asterisk)"""
        
        type_map = {
            FieldType.TEXT: 'text', FieldType.EMAIL: 'email', FieldType.PASSWORD: 'password',
            FieldType.NUMBER: 'number', FieldType.TEL: 'tel', FieldType.URL: 'url',
            FieldType.SEARCH: 'search', FieldType.FILE: 'file', FieldType.HIDDEN: 'hidden',
            FieldType.DATE: 'date', FieldType.DATETIME: 'datetime-local', FieldType.TIME: 'time',
            FieldType.MONTH: 'month', FieldType.WEEK: 'week', FieldType.COLOR: 'color',
            FieldType.TCKN: 'text', FieldType.IBAN: 'text', FieldType.VKN: 'text',
            FieldType.PLATE: 'text', FieldType.CURRENCY: 'text', FieldType.IP: 'text',
            FieldType.CREDIT_CARD: 'text', FieldType.TARIH: 'text'
        }
        input_type = type_map.get(self.field_type, 'text')
        
        # Değer ve Stil Hazırlığı
        val = self.value
        if self.field_type == FieldType.COLOR and not val: val = '#000000'
        safe_val = escape(str(val)) if val is not None else ""
        style_attr = f' style="text-transform: {self.text_transform};"' if self.text_transform else ""
        css_classes = self.get_css_classes()
        
        # İkon ve Zorunluluk İşareti Hazırlığı
        icon_class = self.icon if self.icon else (self._get_field_icon() if hasattr(self, '_get_field_icon') else "")
        if icon_class and "<i" not in icon_class:
            icon_html = f'<i class="{icon_class} me-2"></i>'
        else:
            icon_html = icon_class
        req_mark = ' <span class="text-danger">*</span>' if self.required else ''

        # 1.Saf Input HTML'i
        input_html = (
            f'<input type="{input_type}" name="{self.name}" id="{self.name}" '
            f'class="{css_classes}" value="{safe_val}" placeholder="{self.placeholder}"'
            f'{self.get_html_attributes_string()}{style_attr}>'
        )

        # 2.İçerik Hazırlığı (Floating Label Var mı?)
        # Eğer Floating Label varsa, input'u label ile sarıyoruz.
        content_html = input_html
        is_floating = self.floating_label and self.field_type not in [FieldType.FILE, FieldType.COLOR, FieldType.HIDDEN]

        if is_floating:
            label_content = f'{icon_html} {escape(self.label)}{req_mark}'
            # Hata mesajını buraya değil, en dış katmana koyacağız
            content_html = f'''
            <div class="form-floating">
                {input_html}
                <label for="{self.name}">{label_content}</label>
            </div>
            '''

        # 3.Grup Hazırlığı (Prepend / Append Var mı?)
        # Floating olsun ya da olmasın, eğer ek varsa Input Group oluşturulur.
        if self.prepend_html or self.append_html:
            group_parts = ['<div class="input-group">'] # mb-3 kaldırıldı, dışarıdan yönetilir
            
            # Sol Ek (Prepend)
            if self.prepend_html:
                addon = self.prepend_html
                if "<button" not in addon and "<i" in addon:
                    group_parts.append(f'<span class="input-group-text">{addon}</span>')
                elif "<button" in addon:
                    group_parts.append(addon)
                else:
                    group_parts.append(f'<span class="input-group-text">{addon}</span>')
            
            # Orta Kısım (Floating Label Yapısı veya Saf Input)
            group_parts.append(content_html)
            
            # Sağ Ek (Append) - Butonunuz burada devreye girecek
            if self.append_html:
                addon = self.append_html
                if "<button" not in addon and "<i" in addon:
                    group_parts.append(f'<span class="input-group-text">{addon}</span>')
                elif "<button" in addon:
                    group_parts.append(addon)
                else:
                    group_parts.append(f'<span class="input-group-text">{addon}</span>')
            
            # Validasyon Hatası (Grup içinde)
            if getattr(self, 'error', None):
                group_parts.append(f'<div class="invalid-feedback d-block ms-2">{self.error}</div>')
                
            group_parts.append('</div>')
            return ''.join(group_parts)

        # 4.Eğer Grup Yoksa ama Floating Varsa (Hata mesajını ekle ve döndür)
        if is_floating:
            # Tek başına durduğu için mb-3 ekliyoruz
            final_html = content_html.replace('class="form-floating"', 'class="form-floating mb-3"')
            if self.error:
                final_html += f'<div class="invalid-feedback d-block">{self.error}</div>'
            return final_html

        # 5.Hiçbiri Yoksa (Standart)
        return input_html

    def _render_date(self):
        if not self.prepend_html and not self.floating_label:
            self.prepend_html = '<i class="bi bi-calendar"></i>'
        if self.value and hasattr(self.value, 'strftime'):
             self.value = self.value.strftime('%Y-%m-%d')
        elif self.value:
             self.value = str(self.value)[:10]
        return self._render_input()

    def _render_time(self):
        if not self.prepend_html and not self.floating_label:
            self.prepend_html = '<i class="bi bi-clock"></i>'
        if self.value and hasattr(self.value, 'strftime'):
            fmt = '%H:%M:%S' if 'step' in self.html_attributes else '%H:%M'
            self.value = self.value.strftime(fmt)
        return self._render_input()

    def _render_datetime(self):
        if not self.prepend_html and not self.floating_label:
            self.prepend_html = '<i class="bi bi-calendar-plus"></i>'
        if self.value and hasattr(self.value, 'strftime'):
            self.value = self.value.strftime('%Y-%m-%dT%H:%M')
        elif self.value:
            self.value = str(self.value)[:16]
        return self._render_input()

    def _render_month(self):
        if not self.prepend_html and not self.floating_label:
            self.prepend_html = '<i class="bi bi-calendar-month"></i>'
        if self.value and hasattr(self.value, 'strftime'):
            self.value = self.value.strftime('%Y-%m')
        elif self.value:
            self.value = str(self.value)[:7]
        return self._render_input()

    def _render_week(self):
        if not self.prepend_html and not self.floating_label:
            self.prepend_html = '<i class="bi bi-calendar-week"></i>'
        return self._render_input()

    def _render_tarih(self):
        return self._render_input()

    def _render_search(self):
        if not self.prepend_html and not self.floating_label:
            self.prepend_html = '<i class="bi bi-search"></i>'
        if self.html_attributes.get('data-target'): 
            self.html_attributes['data-search-target'] = self.html_attributes.pop('data-target')
        if self.html_attributes.get("show_button") and not self.append_html:
            self.append_html = f'<button class="btn btn-primary" type="button" onclick="document.getElementById(\'{self.name}\').form.submit()">Ara</button>'
        return self._render_input()

    def _render_select(self):
        css_classes = self.get_css_classes()
        html_attrs = self.get_html_attributes_string()
        is_multiple = self.is_multiple_select()
        name_attr = f"{self.name}[]" if is_multiple else self.name
        if is_multiple: html_attrs += ' multiple'
        if self.select2_config:
            if self.select2_config.get('placeholder'):
                ph_text = escape(self.select2_config["placeholder"])
                html_attrs += f' data-placeholder="{ph_text}"'
            if self.select2_config.get('tags'): html_attrs += ' data-tags="true"'
            if self.select2_config.get('allowClear'): html_attrs += ' data-allow-clear="true"'
        
        parts = []
        parts.append(f'<select name="{name_attr}" id="{self.name}" class="{css_classes}" {html_attrs}>')
        if not is_multiple: parts.append('<option value=""></option>') 
        if self.options:
            current_vals = []
            if self.value:
                if isinstance(self.value, list): current_vals = [str(v) for v in self.value]
                else: current_vals = [str(self.value)]
            for option in self.options:
                if isinstance(option, (list, tuple)) and len(option) >= 2:
                    val, label = str(option[0]), str(option[1])
                else:
                    val, label = str(option), str(option)
                is_selected = ' selected' if val in current_vals else ''
                parts.append(f'<option value="{escape(val)}"{is_selected}>{escape(label)}</option>')
        parts.append('</select>')
        return '\n'.join(parts)

    def _render_textarea(self):
        val = escape(str(self.value)) if self.value else ""
        return (f'<textarea name="{self.name}" id="{self.name}" class="{self.get_css_classes()}" {self.get_html_attributes_string()}>{val}</textarea>')

    def _render_checkbox(self):
        css_classes = self.get_css_classes()
        if 'form-check-input' not in css_classes: css_classes = (css_classes + ' form-check-input').strip()
        html_attrs = self.get_html_attributes_string()
        is_checked = str(self.value).lower() in ['true', '1', 'on'] if self.value else False
        checked_attr = ' checked' if is_checked else ''
        label_html = f'<label class="form-check-label" for="{self.name}">{escape(self.label)}</label>'
        help_html = f'<div class="form-text text-muted small">{escape(self.help_text)}</div>' if self.help_text else ''
        return f'<div class="form-check"><input type="checkbox" name="{self.name}" id="{self.name}" class="{css_classes}" {checked_attr} {html_attrs}>{label_html}{help_html}</div>'

    def _render_radio(self):
        """
        Radio butonlarını render eder.
        Destekler:
        1.Standart görünüm (Alt alta veya Yan yana)
        2.Modern Kart Görünümü (class='radio-card-group' varsa)
        3.İkonlu Seçenekler (options=[(val, label, icon), ...])
        """
        # 1.Stil ve Yapı Ayarları
        custom_classes = self.html_attributes.get('class', '')
        is_card_style = 'radio-card-group' in custom_classes
        is_inline = self.inline or 'form-check-inline' in custom_classes
        
        # HTML özniteliklerini al (class hariç, çünkü yukarıda işledik)
        attrs = self.get_html_attributes_string()
        
        html_parts = []
        
        # Eğer Kart Stili ise, stillerin çalışması için kapsayıcı div ekle
        if is_card_style:
            html_parts.append(f'<div class="{custom_classes}">')

        if self.options:
            for i, option in enumerate(self.options):
                # Seçenek Ayrıştırma: (Değer, Etiket) veya (Değer, Etiket, İkon)
                if isinstance(option, (list, tuple)):
                    val = str(option[0])
                    label = str(option[1])
                    # 3.eleman varsa ikon sınıfı olarak al
                    icon_class = option[2] if len(option) > 2 else None
                else:
                    val = str(option)
                    label = str(option)
                    icon_class = None

                opt_id = f"{self.name}_{i}"
                is_checked = str(self.value) == val if self.value is not None else False
                checked_attr = ' checked' if is_checked else ''
                
                # --- A) MODERN KART GÖRÜNÜMÜ (Bootstrap Button Group) ---
                if is_card_style:
                    # Renk Teması (Varsayılan: primary)
                    btn_color = self.html_attributes.get('btn_color', 'primary')
                    label_class = f"btn btn-outline-{btn_color}"
                    
                    # İkon varsa ekle (Kart içinde blok olarak durması için d-block)
                    icon_html = f'<i class="{icon_class} fs-3"></i>' if icon_class else ''
                    
                    # btn-check sınıfı input'u gizler, label'ı buton gibi gösterir
                    html_parts.append(f'''
                        <input type="radio" class="btn-check" name="{self.name}" id="{opt_id}" value="{escape(val)}" {checked_attr} {attrs} autocomplete="off">
                        <label class="{label_class}" for="{opt_id}">{icon_html}<span>{escape(label)}</span></label>
                    ''')

                # --- B) STANDART GÖRÜNÜM (Klasik Radio) ---
                else:
                    wrapper_class = "form-check form-check-inline" if is_inline else "form-check"
                    input_class = "form-check-input"
                    
                    # Standart görünümde de ikon varsa başa koyalım
                    icon_html = f'<i class="{icon_class} me-1"></i>' if icon_class else ''
                    
                    html_parts.append(f'''
                        <div class="{wrapper_class}">
                            <input class="{input_class}" type="radio" name="{self.name}" id="{opt_id}" value="{escape(val)}" {checked_attr} {attrs}>
                            <label class="form-check-label" for="{opt_id}">{icon_html}{escape(label)}</label>
                        </div>
                    ''')

        # Kart stili kapsayıcısını kapat
        if is_card_style:
            html_parts.append('</div>')

        return ''.join(html_parts)

    def _render_switch(self):
        css_classes = self.get_css_classes()
        if 'switch-input' not in css_classes: css_classes += ' switch-input'
        html_attrs = self.get_html_attributes_string()
        checked = ' checked' if self.value else ''
        parts = []
        parts.append('<div class="form-check form-switch">')
        parts.append(f'<input type="checkbox" name="{self.name}" id="{self.name}" value="true" class="{css_classes}" role="switch"{checked}{html_attrs}>')
        parts.append(f'<label class="form-check-label" for="{self.name}">{escape(self.label)}</label>')
        if self.help_text: parts.append(f'<div class="form-text">{escape(self.help_text)}</div>')
        parts.append('</div>')
        return '\n'.join(parts)

    def _render_richtext(self):
        editor_id = f"{self.name}_editor"
        placeholder = self.placeholder or "Metninizi buraya yazın..."
        css_classes = self.get_css_classes()
        if 'quill-editor' not in css_classes: css_classes += ' quill-editor'
        content = str(self.value) if self.value else ""
        safe_value = escape(content)
        parts = []
        parts.append(f'<div id="{editor_id}" class="{css_classes}" style="height: 200px;" data-target="{self.name}" data-placeholder="{placeholder}">{content}</div>')
        parts.append(f'<input type="hidden" name="{self.name}" id="{self.name}" value="{safe_value}" {self.get_html_attributes_string()}>')
        #if self.help_text: parts.append(f'<div class="form-text text-muted small mt-1">{self.help_text}</div>')
        return '\n'.join(parts)

    def _render_signature(self):
        editor_id = f"{self.name}_canvas"
        help_text = self.help_text or "Lütfen alana imzanızı çiziniz."
        val = escape(str(self.value)) if self.value else ""
        html_parts = []
        html_parts.append(f'<div class="dx-signature-pad signature-wrapper border rounded p-3 bg-light" data-input="{self.name}" data-bg="#ffffff" data-pen="#000000" data-height="180">')
        html_parts.append('<div class="d-flex justify-content-between align-items-center mb-2">')
        html_parts.append(f'<div class="small text-muted fw-bold"><i class="fas fa-pen-nib me-1"></i> {help_text}</div>')
        html_parts.append('<div class="btn-group btn-group-sm"><button type="button" class="btn btn-outline-secondary" data-action="sig-undo" title="Son çizgiyi geri al"><i class="fas fa-undo me-1"></i> Geri Al</button><button type="button" class="btn btn-outline-danger" data-action="sig-clear" title="İmzayı tamamen sil"><i class="fas fa-trash me-1"></i> Temizle</button></div></div>')
        html_parts.append(f'<div class="drawing-area border bg-white rounded overflow-hidden shadow-sm" style="position: relative;"><canvas id="{editor_id}" style="width: 100%; display: block; touch-action: none;"></canvas></div>')
        html_parts.append(f'<input type="hidden" name="{self.name}" id="{self.name}" value="{val}" {self._get_attrs_string()}></div>')
        return '\n'.join(html_parts)

    def _render_json(self):
        import json
        val = self.value
        if val is not None and not isinstance(val, str):
            try: val = json.dumps(val, indent=4, ensure_ascii=False)
            except: val = str(val)
        display_val = val if val else "{}"
        css_classes = self.get_css_classes()
        if 'font-monospace' not in css_classes: css_classes += ' font-monospace'
        html_attrs = self.get_html_attributes_string()
        html_parts = []
        html_parts.append(f'<div class="json-editor-wrapper"><textarea name="{self.name}" id="{self.name}" class="{css_classes}" rows="8" spellcheck="false" data-editor="json" {html_attrs}>{escape(str(display_val))}</textarea><div class="form-text text-muted d-flex justify-content-between align-items-center mt-1"><span class="small"><i class="fas fa-code me-1"></i> JSON formatında giriniz.</span><button type="button" class="btn btn-sm btn-link text-decoration-none p-0" data-action="format-json" data-target="{self.name}" title="Kodu Güzelleştir"><i class="fas fa-magic me-1"></i> Formatla</button></div></div>')
        return '\n'.join(html_parts)

    def _render_image(self):
        """
        Resim alanı: Mevcut resmi gösterir ve yeni yükleme inputu sağlar.
        """
        # Sizin yapınızdaki helper fonksiyonları kullanıyoruz
        css_classes = self.get_css_classes() if hasattr(self, 'get_css_classes') else "form-control"
        html_attrs = self.get_html_attributes_string() if hasattr(self, 'get_html_attributes_string') else ""
        
        # 1.Resim Yolu Ayarlama
        # Veritabanında "uploads/stok/..." şeklinde kayıtlıdır.
        # Tarayıcıda görünmesi için başına "/static/" eklemeliyiz.
        src = ""
        has_value = False
        display_style = "none"
        
        if self.value:
            has_value = True
            src = str(self.value)
            # Eğer zaten http veya /static ile başlamıyorsa ekle
            if not src.startswith('/static/') and not src.startswith('http'):
                src = f"/static/{src}"
            display_style = "block"
            
        html_parts = []
        
        # 2.MEVCUT RESMİ GÖSTER (Varsa)
        if has_value:
            html_parts.append(f'''
            <div class="d-flex align-items-center mb-2 p-2 border rounded bg-light">
                <div class="me-3 bg-white p-1 border rounded shadow-sm" style="width: 80px; height: 80px; display: flex; align-items: center; justify-content: center;">
                    <img src="{src}" alt="Mevcut Resim" class="img-fluid" style="max-height: 100%; max-width: 100%;">
                </div>
                <div>
                    <span class="badge bg-success mb-1"><i class="fas fa-check-circle"></i> Yüklü</span>
                    <div class="small text-muted" style="font-size: 0.75rem;">Değiştirmek için aşağıdan yeni dosya seçiniz.</div>
                </div>
            </div>
            ''')

        # 3.DOSYA INPUT (Sizin yapınıza uygun class ve attribute'lar ile)
        # data-preview attribute'u JS tarafında yakalamak için eklendi
        html_parts.append(f'<input type="file" name="{self.name}" id="{self.name}" class="{css_classes}" accept="image/*" {html_attrs} data-preview="{self.name}_preview">')
        
        # 4.YENİ SEÇİLEN RESİM İÇİN CANLI ÖNİZLEME (JS Script)
        # Kullanıcı yeni bir dosya seçtiğinde anında gösterir
        script = f'''
        <div id="{self.name}_new_preview_container" class="mt-2" style="display:none;">
            <div class="small fw-bold text-primary mb-1">Yeni Seçilen:</div>
            <img id="{self.name}_new_preview" class="img-thumbnail shadow-sm" style="max-height: 150px;">
        </div>
        <script>
            document.getElementById("{self.name}").addEventListener("change", function(e) {{
                var container = document.getElementById("{self.name}_new_preview_container");
                var img = document.getElementById("{self.name}_new_preview");
                if (this.files && this.files[0]) {{
                    var reader = new FileReader();
                    reader.onload = function(e) {{
                        img.src = e.target.result;
                        container.style.display = "block";
                    }};
                    reader.readAsDataURL(this.files[0]);
                }} else {{
                    container.style.display = "none";
                }}
            }});
        </script>
        '''
        html_parts.append(script)
        
        return '\n'.join(html_parts)

    def _render_files(self):
        input_id = self.name
        accept = self.accept or '*/*'
        max_size_mb = self.max_file_size or 10
        help_text = self.help_text or _("Maksimum {max_size_mb} MB")
        total_attr = f' data-total-max-size="{self.max_total_size}"' if getattr(self, 'max_total_size', None) else ''
        strict_attr = ' data-total-strict="true"' if self.html_attributes.get('strict_total') else ''
        batch_attr = ' data-batch-reject="true"' if self.html_attributes.get('batch_reject') else ''
        parts = []
        parts.append(f'<div class="file-upload-wrapper" id="wrapper_{input_id}"><div class="file-dropzone border border-2 border-dashed rounded p-4 text-center bg-light position-relative" data-input="{input_id}" data-max-size="{max_size_mb}"{total_attr}{strict_attr}{batch_attr}><div class="dz-message needsclick"><i class="bi bi-cloud-arrow-up text-primary display-4 mb-3"></i><h6 class="mb-2">Dosyaları buraya sürükleyin</h6><span class="text-muted small">veya</span><br><button type="button" class="btn btn-sm btn-outline-primary mt-2" data-action="pick-files"><i class="bi bi-folder2-open me-1"></i> Dosya Seç</button><div class="small text-muted mt-3">{escape(help_text)}</div></div></div><ul class="list-group list-group-flush mt-3 file-list" id="{input_id}_list"></ul><div class="file-actions mt-3 d-none d-flex justify-content-end gap-2" id="{input_id}_actions"><button type="button" class="btn btn-outline-secondary btn-sm" data-action="clear-all"><i class="bi bi-trash"></i> Tümünü Temizle</button><button type="button" class="btn btn-success btn-sm" data-action="upload-now"><i class="bi bi-upload"></i> SEÇİLENLERİ YÜKLE</button></div><input type="file" name="{self.name}[]" id="{input_id}" class="{self.get_css_classes()} d-none" multiple accept="{accept}"><template class="file-item-template"><li class="list-group-item d-flex justify-content-between align-items-center py-2 animate__animated animate__fadeIn"><div class="d-flex align-items-center overflow-hidden"><div class="file-icon me-3"><i class="bi bi-file-earmark-text fs-4 text-secondary"></i></div><div class="file-info text-start" style="min-width: 0;"><h6 class="mb-0 text-truncate file-name fw-bold" style="font-size: 0.9rem; max-width: 250px;"></h6><small class="text-muted file-size" style="font-size: 0.75rem;"></small></div></div><button type="button" class="btn btn-sm btn-outline-danger btn-remove-file ms-2" title="Listeden Kaldır"><i class="bi bi-x-lg"></i> Kaldır</button></li></template></div>')
        return ''.join(parts)

    def _render_date_range(self):
        start_id = f"{self.name}_start"
        end_id = f"{self.name}_end"
        placeholder_start = self.html_attributes.get('placeholder_start', _('Başlangıç Tarihi'))
        placeholder_end = self.html_attributes.get('placeholder_end', _('Bitiş Tarihi'))
        start_val = self.value.get('start', '') if isinstance(self.value, dict) else ''
        end_val = self.value.get('end', '') if isinstance(self.value, dict) else ''
        presets_attr = f' data-presets="{self.html_attributes.get("presets")}"' if self.html_attributes.get('presets') else ''
        parts = []
        parts.append(f'<div class="date-range" data-range-name="{self.name}"{presets_attr}><div class="d-flex align-items-center mb-2 date-range-presets"><div class="me-2 small text-muted"><i class="fas fa-bolt me-1"></i> Hızlı Seçim:</div><div class="btn-group btn-group-sm" role="group"><button type="button" class="btn btn-outline-secondary" data-preset="yesterday">Dün</button><button type="button" class="btn btn-outline-secondary" data-preset="today">Bugün</button><button type="button" class="btn btn-outline-secondary" data-preset="last7">Son 7 Gün</button><button type="button" class="btn btn-outline-secondary" data-preset="thisMonth">Bu Ay</button><button type="button" class="btn btn-outline-secondary" data-preset="lastMonth">Önceki Ay</button></div></div><div class="row g-2"><div class="col-md-6"><label class="form-label small text-muted d-block d-md-none">{placeholder_start}</label><input type="date" class="form-control dx-form-control" id="{start_id}" name="{start_id}" value="{escape(str(start_val))}" placeholder="{placeholder_start}" aria-label="{placeholder_start}"></div><div class="col-md-6"><label class="form-label small text-muted d-block d-md-none">{placeholder_end}</label><input type="date" class="form-control dx-form-control" id="{end_id}" name="{end_id}" value="{escape(str(end_val))}" placeholder="{placeholder_end}" aria-label="{placeholder_end}"></div></div><div class="invalid-feedback d-block d-none" id="{self.name}_range_error">Başlangıç tarihi, bitiş tarihinden büyük olamaz.</div></div>')
        return '\n'.join(parts)

    def _render_range_dual(self):
        vmin = self.value.get('min') if isinstance(self.value, dict) else None
        vmax = self.value.get('max') if isinstance(self.value, dict) else None
        limit_min = self.min_val if self.min_val is not None else 0
        limit_max = self.max_val if self.max_val is not None else 100
        if vmin is None: vmin = limit_min
        if vmax is None: vmax = limit_max
        step = self.step if self.step is not None else 1
        symbol = self.currency_symbol if hasattr(self, 'currency_symbol') else ''
        slider_id = f"range_{self.name}"
        html = []
        html.append(f'<div class="d-flex justify-content-between align-items-center mb-2"><span class="badge bg-primary" id="{self.name}_min_badge">{symbol}{vmin}</span><div class="text-muted small"><i class="fas fa-arrows-alt-h"></i></div><span class="badge bg-primary" id="{self.name}_max_badge">{symbol}{vmax}</span></div>')
        html.append(f'<div id="{slider_id}" class="dx-range-dual" data-name="{self.name}" data-min="{limit_min}" data-max="{limit_max}" data-step="{step}" data-symbol="{symbol}" data-start-min="{vmin}" data-start-max="{vmax}"></div>')
        html.append(f'<input type="hidden" name="{self.name}_min" id="{self.name}_min" value="{escape(str(vmin))}"><input type="hidden" name="{self.name}_max" id="{self.name}_max" value="{escape(str(vmax))}">')
        return '\n'.join(html)

    def _render_map_point(self):
        lat, lng = None, None
        if self.value and isinstance(self.value, str) and ',' in self.value:
            try: lat, lng = map(float, map(str.strip, self.value.split(',')))
            except: pass
        if lat is None:
            try: lat, lng = float(self.map_default[0]), float(self.map_default[1])
            except: lat, lng = 39.925, 32.836
        map_id = f"map_{self.name}"
        display_coords = f"{lat:.6f}, {lng:.6f}"
        html_parts = []
        html_parts.append(f'<div class="d-flex justify-content-between align-items-center mb-2"><div class="small text-muted"><i class="fas fa-location-dot me-1 text-danger"></i> <span id="{self.name}_coord" class="fw-bold text-dark">{display_coords}</span></div><small class="text-muted fst-italic" style="font-size: 0.75rem;"><i class="fas fa-hand-pointer me-1"></i>İşaretçiyi sürükleyin</small></div>')
        html_parts.append(f'<div class="map-wrapper border rounded shadow-sm bg-light position-relative overflow-hidden" style="height: 320px; z-index: 0;"><div id="{map_id}" class="dx-map-point w-100 h-100" data-name="{self.name}" data-lat="{lat}" data-lng="{lng}" data-zoom="{self.map_zoom}"></div></div>')
        html_parts.append(f'<input type="hidden" name="{self.name}_lat" id="{self.name}_lat" value="{escape(str(lat))}"><input type="hidden" name="{self.name}_lng" id="{self.name}_lng" value="{escape(str(lng))}" onchange="document.getElementById(\'{self.name}_coord\').innerText = parseFloat(document.getElementById(\'{self.name}_lat\').value).toFixed(6) + \', \' + parseFloat(this.value).toFixed(6)">')
        return '\n'.join(html_parts)

    def _render_range(self):
        css_classes = self.get_css_classes()
        if 'form-range' not in css_classes: css_classes += ' form-range'
        html_attrs = self.get_html_attributes_string()
        current_value = self.value if self.value is not None else (self.min_val or 0)
        return f'<div class="d-flex align-items-center gap-2"><input type="range" name="{self.name}" id="{self.name}" class="{css_classes} flex-grow-1" value="{escape(str(current_value))}" {html_attrs} oninput="document.getElementById(\'{self.name}_value\').textContent = this.value"><span class="badge bg-primary" style="min-width: 40px;" id="{self.name}_value">{current_value}</span></div>'

    def _render_barcode(self):
        reader_id = f"barcode_reader_{self.name}"
        result_id = f"barcode_result_{self.name}"
        file_input_id = f"barcode_file_{self.name}"
        val = str(self.value) if self.value else ""
        val_escaped = escape(val)
        html = []
        html.append(f'<input type="hidden" name="{self.name}" id="{self.name}" value="{val_escaped}"><div class="dx-barcode-container border rounded p-3 bg-light" data-input="{self.name}"><ul class="nav nav-tabs mb-3" role="tablist"><li class="nav-item" role="presentation"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#camera-{self.name}" type="button"><i class="fas fa-camera me-1"></i> Kamera</button></li><li class="nav-item" role="presentation"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#file-{self.name}" type="button"><i class="fas fa-file-image me-1"></i> Dosyadan</button></li></ul><div class="tab-content"><div class="tab-pane fade show active" id="camera-{self.name}"><div id="{reader_id}" class="bg-dark rounded" style="width: 100%; min-height: 250px;"></div><div class="mt-2 d-grid gap-2"><button type="button" class="btn btn-primary" data-action="start-scan" data-reader="{reader_id}" data-input="{self.name}"><i class="fas fa-power-off me-1"></i> Kamerayı Başlat</button><button type="button" class="btn btn-danger" data-action="stop-scan" data-reader="{reader_id}" data-input="{self.name}" style="display: none;"><i class="fas fa-stop-circle me-1"></i> Durdur</button></div></div><div class="tab-pane fade" id="file-{self.name}"><label class="form-label small text-muted">Barkod içeren bir resim seçin:</label><input type="file" id="{file_input_id}" class="form-control" accept="image/*" data-input="{self.name}"></div></div>')
        alert_class = "alert-success" if val else "alert-info"
        content = f'<i class="fas fa-check-circle me-2"></i><strong>Kayıtlı Kod:</strong> <code class="fs-6">{val_escaped}</code>' if val else '<i class="fas fa-info-circle me-2"></i>Henüz kod okunmadı.'
        html.append(f'<div id="{result_id}" class="alert {alert_class} mt-3 mb-2 d-flex align-items-center justify-content-between"><div>{content}</div><button type="button" class="btn btn-sm btn-outline-secondary" data-action="clear-barcode" data-input="{self.name}" title="Temizle"><i class="fas fa-trash"></i></button></div></div>')
        return '\n'.join(html)

    def _render_calc(self):
        # 1.Değer Hazırlığı
        val = escape(str(self.value or ""))
        css_classes = self.get_css_classes()
        
        # 2.Çok Satırlı HTML (Okunaklı ve Düzenlenebilir)
        return f'''
        <div class="calc-container position-relative" data-field="{self.name}">
            
            <div class="input-group">
                <input type="text" name="{self.name}" id="{self.name}" class="{css_classes}" value="{val}" readonly>
                <button type="button" class="btn btn-secondary calc-opener" data-calc-id="calc_popup_{self.name}">
                    <i class="bi bi-calculator"></i>
                </button>
            </div>

            <div class="calc-popup shadow-lg rounded p-2" id="calc_popup_{self.name}" 
                 style="display:none; position:absolute; top:100%; right:0; z-index:1050; background:white; border:1px solid #dee2e6; width: 240px;">
                
                <input type="text" class="form-control calc-display mb-2 text-end fw-bold" readonly value="0">
                
                <div class="calc-buttons d-grid gap-1" style="grid-template-columns: repeat(4, 1fr);">
                    <button type="button" class="btn btn-light btn-sm" data-key="C">C</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="/">/</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="*">*</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-key="back"><i class="bi bi-backspace"></i></button>
                    
                    <button type="button" class="btn btn-light btn-sm" data-key="7">7</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="8">8</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="9">9</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="-">-</button>
                    
                    <button type="button" class="btn btn-light btn-sm" data-key="4">4</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="5">5</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="6">6</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="+">+</button>
                    
                    <button type="button" class="btn btn-light btn-sm" data-key="1">1</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="2">2</button>
                    <button type="button" class="btn btn-light btn-sm" data-key="3">3</button>
                    
                    <button type="button" class="btn btn-success btn-sm" style="grid-row: span 2;" data-key="=">=</button>
                    
                    <button type="button" class="btn btn-light btn-sm" data-key="0" style="grid-column: span 2;">0</button>
                    <button type="button" class="btn btn-light btn-sm" data-key=".">.</button>
                </div>
                
                <div class="mt-2">
                    <button type="button" class="btn btn-primary btn-sm w-100 calc-apply">Onayla</button>
                </div>
            </div>
        </div>
        '''
    def _render_otp(self):
        length = int(self.html_attributes.get('data-length', 6))
        html_parts = []
        html_parts.append(f'<div class="mb-3"><label class="form-label fw-bold">{self.label}</label><div class="dx-otp d-flex gap-2 justify-content-center" data-target="{self.name}" data-length="{length}">')
        for i in range(length):
            html_parts.append('<input type="text" class="form-control dx-otp-input text-center fs-4 fw-bold" maxlength="1" inputmode="numeric" autocomplete="one-time-code" style="width: 50px; height: 60px;">')
        html_parts.append(f'</div><input type="hidden" name="{self.name}" id="{self.name}" required>')
        if self.help_text: html_parts.append(f'<div class="form-text text-center mt-2">{self.help_text}</div>')
        html_parts.append('</div>')
        return ''.join(html_parts)

    def _render_tags(self):
        attrs = self._get_attrs_string()
        css_classes = self.get_css_classes()
        if 'select2-field' not in css_classes: css_classes += ' select2-field'
        html = [f'<select name="{self.name}[]" id="{self.name}" class="{css_classes}" multiple data-tags="true" {attrs}>']
        vals = []
        if self.value:
            if isinstance(self.value, list): vals = self.value
            elif isinstance(self.value, str): vals = [tag.strip() for tag in self.value.split(',') if tag.strip()]
        for v in vals:
            safe_v = escape(str(v))
            html.append(f'<option value="{safe_v}" selected>{safe_v}</option>')
        html.append('</select>')
        return ''.join(html)

    def _render_rating(self):
        val = int(self.value) if self.value else 0
        html = [f'<div class="rating-container" data-field="{self.name}">']
        for i in range(1, self.max_rating + 1):
            icon_cls = 'fas fa-star text-warning' if i <= val else 'far fa-star text-warning'
            html.append(f'<i class="{icon_cls} rating-star fs-4 me-1" data-rating="{i}" style="cursor: pointer;"></i>')
        html.append(f'<input type="hidden" name="{self.name}" id="{self.name}" value="{val}"></div>')
        return ''.join(html)

    def _render_currency(self):
        """Para birimi için değeri formatlar ve _render_input'a devreder."""
        decimals = self.html_attributes.get('data-decimal-places', 2)
        if self.value:
            try:
                if ',' not in str(self.value):
                    f_val = float(str(self.value))
                    self.value = f"{f_val:,.{decimals}f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except: pass
        self.html_attributes['data-currency'] = 'true'
        self.html_attributes['data-decimal-places'] = decimals
        if not self.prepend_html and not self.append_html:
             symbol = self.currency_symbol or '₺'
             self.append_html = symbol
        return self._render_input()

    def _render_media_recorder(self):
        is_video = (self.field_type == FieldType.VIDEO_RECORDER)
        type_name = 'video' if is_video else 'audio'
        icon = 'camera-video' if is_video else 'mic'
        btn_text = 'Video Kaydet' if is_video else 'Ses Kaydet'
        live_preview_html = ''
        if is_video:
            live_preview_html = f'<div class="ratio ratio-4x3 bg-dark rounded mb-2 overflow-hidden"><video id="live_{self.name}" class="w-100 h-100 object-fit-cover" style="display:none;" autoplay muted playsinline></video><div class="d-flex align-items-center justify-content-center h-100 text-white-50" id="placeholder_{self.name}"><i class="bi bi-camera-video fs-1"></i></div></div>'
        return f'<div class="media-recorder-wrapper border rounded p-3 bg-light" id="wrapper_{self.name}">{live_preview_html}<div class="d-flex gap-2 align-items-center"><button type="button" class="btn btn-outline-primary" data-action="start" data-type="{type_name}" data-target="{self.name}"><i class="bi bi-{icon}"></i> {btn_text}</button><button type="button" class="btn btn-danger d-none" data-action="stop" data-target="{self.name}"><i class="bi bi-stop-circle-fill"></i> Durdur</button><small class="text-muted ms-2 status-text">Hazır</small></div><div id="playback_{self.name}" class="mt-3"></div><input type="hidden" name="{self.name}" id="{self.name}" value=""></div>'

    def _render_drawing(self):
        canvas_id = f"drawing_{self.name}"
        val = escape(str(self.value)) if self.value else ""
        custom_width = self.html_attributes.get('width')
        custom_height = self.html_attributes.get('height', '250')
        width_attr = f' width="{custom_width}"' if custom_width else ''
        height_attr = f' height="{custom_height}"'
        display_mode = "d-inline-block" if custom_width else "d-block"
        html = []
        html.append('<div class="drawing-field mb-3"><small class="text-muted d-block mb-1"><i class="fas fa-pencil-alt"></i> Çizim alanı</small>')
        html.append(f'<div class="drawing-wrapper position-relative {display_mode} border rounded bg-white shadow-sm" style="overflow: hidden;"><button type="button" class="btn btn-sm btn-danger position-absolute top-0 end-0 m-2" data-action="clear-drawing" data-target="{canvas_id}" style="z-index: 10; opacity: 0.9; padding: 2px 8px; font-size: 12px;"><i class="fas fa-trash me-1"></i>Temizle</button><canvas id="{canvas_id}"{width_attr}{height_attr}></canvas></div>')
        html.append(f'<input type="hidden" name="{self.name}" id="{self.name}" value="{val}"></div>')
        return '\n'.join(html)

    def _render_slider(self):
        min_val = self.html_attributes.get('min', 0)
        max_val = self.html_attributes.get('max', 100)
        step = self.html_attributes.get('step', 1)
        start_val = self.value if self.value is not None else min_val
        slider_attrs = f' data-min="{min_val}" data-max="{max_val}" data-step="{step}" data-start="{start_val}"'
        if self.html_attributes.get('tooltips'): slider_attrs += ' data-tooltips="true"'
        if self.html_attributes.get('pips'): slider_attrs += ' data-pips="true"'
        return f'<div class="mb-4 slider-wrapper"><label class="form-label fw-bold d-block mb-3">{self.label}</label><div id="slider_{self.name}" class="dx-slider mb-2" {slider_attrs}></div><input type="hidden" name="{self.name}" id="{self.name}" value="{start_val}"><div class="d-flex justify-content-between text-muted small mt-2"><span>{min_val}</span><span id="display_{self.name}" class="fw-bold text-primary">{start_val}</span><span>{max_val}</span></div>{f"<div class=\'form-text mt-1\'>{self.help_text}</div>" if self.help_text else ""}</div>'

    def _render_autocomplete(self):
        css_classes = self.get_css_classes()
        if 'autocomplete-field' not in css_classes: css_classes += ' autocomplete-field'
        html_attrs = self.get_html_attributes_string()
        val = escape(str(self.value)) if self.value else ""
        return f'<div class="autocomplete-wrapper position-relative"><input type="text" name="{self.name}" id="{self.name}" class="{css_classes}" value="{val}" data-autocomplete="true" {html_attrs}></div>'

    def _render_markdown(self):
        css_classes = self.get_css_classes()
        if 'markdown-editor' not in css_classes: css_classes += ' markdown-editor'
        return f'<div class="markdown-wrapper"><textarea name="{self.name}" id="{self.name}" class="{css_classes}" rows="10" {self._get_attrs_string()}>{escape(str(self.value or ""))}</textarea></div>'

    def _render_code_editor(self):
        css_classes = self.get_css_classes()
        if 'code-editor' not in css_classes: css_classes += ' code-editor'
        if 'font-monospace' not in css_classes: css_classes += ' font-monospace'
        html_attrs = self.get_html_attributes_string()
        val = escape(str(self.value)) if self.value else ""
        language = self.html_attributes.get('data-language', 'javascript')
        is_runnable = self.html_attributes.get('data-runnable') == 'true'
        parts = []
        parts.append(f'<div class="code-editor-wrapper mb-3 border rounded shadow-sm overflow-hidden bg-white">')
        parts.append(f'<div class="bg-light px-3 py-2 border-bottom fw-bold text-dark small d-flex justify-content-between align-items-center"><span><i class="fas fa-code me-2 text-primary"></i>{self.label or "Kod Editörü"}</span>')
        if is_runnable: parts.append(f'<button type="button" class="btn btn-sm btn-success btn-run-code" data-target="{self.name}"><i class="bi bi-play-fill"></i> Çalıştır</button>')
        parts.append('</div>')
        parts.append(f'<textarea name="{self.name}" id="{self.name}" class="{css_classes}" rows="10" spellcheck="false" {html_attrs}>{val}</textarea>')
        parts.append(f'<div class="bg-light px-3 py-1 border-top d-flex justify-content-between align-items-center small text-muted" style="min-height: 30px;">')
        parts.append(f'<span class="text-truncate me-2">{self.help_text or ""}</span>')
        parts.append(f'<span class="badge bg-secondary text-white font-monospace text-uppercase" title="Dil">{language}</span></div>')
        if is_runnable: parts.append(f'<div id="output_{self.name}" class="code-output bg-dark text-white p-3 font-monospace small d-none" style="max-height: 150px; overflow-y: auto; border-top: 1px solid #444;"><div class="text-muted mb-1 text-uppercase" style="font-size: 10px;">Terminal Çıktısı:</div><pre class="m-0 text-success output-content"></pre></div>')
        parts.append('</div>')
        return ''.join(parts)

    def _render_color_advanced(self):
        return f'<div class="input-group color-picker-advanced"><span class="input-group-text color-preview" style="background-color:{self.value or "#ffffff"}"></span><input type="text" name="{self.name}" id="{self.name}" class="{self.get_css_classes()} advanced-color-picker" value="{escape(str(self.value or ""))}" {self._get_attrs_string()}></div>'

    def _render_datetime_range(self):
        start_val = self.value.get('start', '') if isinstance(self.value, dict) else ''
        end_val = self.value.get('end', '') if isinstance(self.value, dict) else ''
        return f'<div class="datetime-range-wrapper row g-2"><div class="col-md-6"><label class="small text-muted">Başlangıç</label><input type="datetime-local" name="{self.name}_start" class="form-control" value="{start_val}"></div><div class="col-md-6"><label class="small text-muted">Bitiş</label><input type="datetime-local" name="{self.name}_end" class="form-control" value="{end_val}"></div></div>'
    
    def _render_mask(self):
        css_classes = self.get_css_classes()
        if 'mask-field' not in css_classes: css_classes += ' mask-field'
        html_attrs = self.get_html_attributes_string()
        val = escape(str(self.value)) if self.value else ""
        return f'<input type="text" name="{self.name}" id="{self.name}" class="{css_classes}" value="{val}" {html_attrs}>'

    def _render_color(self):
        css_classes = self.get_css_classes()
        if 'form-control-color' not in css_classes: css_classes = (css_classes + ' form-control form-control-color').strip()
        html_attrs = self.get_html_attributes_string()
        val = escape(str(self.value)) if self.value else ""
        return f'<input type="color" name="{self.name}" id="{self.name}" class="{css_classes}" value="{val}" {html_attrs}>'
    
    def _render_multi_field(self):
        if not hasattr(self, 'columns') or not self.columns:
            self.columns = [{'name': 'value', 'type': 'text', 'placeholder': self.placeholder}]
        wrapper_id = f"wrapper_{self.name}"
        header_html = ['<div class="row g-2 mb-1 fw-bold text-muted small">']
        for col in self.columns:
            width_class = col.get('width', 'col') 
            header_html.append(f'<div class="{width_class}">{col.get("label", "")}</div>')
        header_html.append('<div class="col-auto" style="width: 40px;"></div></div>')
        values = self.value if isinstance(self.value, list) else []
        if not values: values = [{}] 
        rows_html = []
        for row_data in values: rows_html.append(self._generate_multi_column_row(row_data))
        return f'<div class="multi-field-wrapper" id="{wrapper_id}">{"".join(header_html)}<div class="multi-field-list">{"".join(rows_html)}</div><button type="button" class="btn btn-sm btn-outline-primary mt-2 btn-add-row"><i class="fas fa-plus"></i> Yeni Satır Ekle</button><template class="row-template">{self._generate_multi_column_row({})}</template></div>'

    def _generate_multi_column_row(self, row_data):
        cols_html = []
        for col in self.columns:
            input_name = f"{self.name}_{col['name']}[]"
            val = ''
            if isinstance(row_data, dict): val = row_data.get(col['name'], '')
            elif isinstance(row_data, str) and col['name'] == 'value': val = row_data
            width_class = col.get('width', 'col')
            col_type = col.get('type', 'text')
            placeholder = col.get('placeholder', '')
            custom_class = col.get('css_class', '') 
            field_html = ''
            if col_type == 'select':
                options_html = []
                options_html.append(f'<option value="">{placeholder or "Seçiniz"}</option>')
                for opt_val, opt_label in col.get('options', []):
                    selected = 'selected' if str(opt_val) == str(val) else ''
                    options_html.append(f'<option value="{opt_val}" {selected}>{opt_label}</option>')
                field_html = f'<select name="{input_name}" class="form-select form-select-sm {custom_class}">{"".join(options_html)}</select>'
            elif col_type == 'checkbox':
                is_checked = 'checked' if val in ['1', 'true', 'True', True, 1] else ''
                field_html = f'<div class="form-check d-flex justify-content-center pt-1"><input type="hidden" name="{input_name}" value="{val}"><input type="checkbox" class="form-check-input {custom_class}" {is_checked} onchange="this.previousElementSibling.value = this.checked ? \'1\' : \'0\'"></div>'
            else:
                field_html = f'<input type="{col_type}" name="{input_name}" class="form-control form-control-sm {custom_class}" value="{escape(str(val))}" placeholder="{placeholder}">'
            cols_html.append(f'<div class="{width_class}">{field_html}</div>')
        cols_html.append('<div class="col-auto" style="width: 40px;"><button type="button" class="btn btn-sm btn-outline-danger w-100 btn-remove-row" tabindex="-1"><i class="fas fa-trash"></i></button></div>')
        return f'<div class="row g-2 mb-2 multi-field-row align-items-center">{"".join(cols_html)}</div>'

    def _render_captcha(self):
        site_key = self.html_attributes.get('data-sitekey')
        provider = self.html_attributes.get('data-captcha', 'recaptcha')
        if site_key:
            return f'<div class="dx-captcha-wrapper mb-3 d-flex justify-content-center"><div class="dx-captcha" data-sitekey="{site_key}" data-captcha="{provider}" id="captcha_{self.name}"></div><input type="hidden" name="{self.name}" id="input_{self.name}" required></div>'
        else:
            return f'<div class="captcha-wrapper p-3 bg-light border rounded text-center mb-3"><div class="mb-2 text-muted small"><i class="fas fa-robot"></i> Güvenlik Kontrolü (Demo)</div><div class="form-check d-inline-block"><input class="form-check-input" type="checkbox" name="{self.name}_check" id="{self.name}" required><label class="form-check-label" for="{self.name}">Ben robot değilim</label></div></div>'

    def _render_geolocation(self):
        val = self.value if self.value else ""
        val_escaped = escape(str(val))
        css_classes = self.get_css_classes()
        html_attrs = self.get_html_attributes_string()
        html_parts = []
        html_parts.append('<div class="geolocation-field"><div class="input-group">')
        html_parts.append(f'<button type="button" class="btn btn-outline-primary" data-action="get-location" data-input="{self.name}" title="Mevcut konumumu al"><i class="fas fa-location-crosshairs me-1"></i> Konum Al</button>')
        html_parts.append(f'<input type="text" name="{self.name}" id="{self.name}" class="{css_classes}" value="{val_escaped}" placeholder="Enlem, Boylam" {html_attrs}>')
        html_parts.append('</div>')
        #if self.help_text: html_parts.append(f'<div class="form-text text-muted">{escape(self.help_text)}</div>')
        html_parts.append('</div>')
        return '\n'.join(html_parts)

    def _render_master_detail(self):
        # --- 1.KOLON NORMALİZASYONU (HATA DÜZELTME) ---
        # Gelen kolonlar sözlük (dict) ise bunları geçici FormField nesnelerine çeviriyoruz.
        # Böylece .html_attributes veya .render() çağrıldığında hata almayız.
        # --- 1.KOLON NORMALİZASYONU (GÜÇLENDİRİLMİŞ) ---
        # --- 1.KOLON NORMALİZASYONU (String -> Enum Dönüşümü) ---
        # ============================================================
        # 1.KOLON NORMALİZASYONU (HER İKİ YÖNTEMİ DE DESTEKLEME)
        # ============================================================
        # Master-Detail Tablo Render Metodu (Tam Kapsamlı)
        # Tüm FieldType'ları destekler.
        # ============================================================
        # 1.KOLON NORMALİZASYONU
        # (Sözlük veya FormField nesnesi olarak gelen kolonları standartlaştırır)
        # ============================================================
        # Master-Detail Tablo Render Metodu (GÜNCELLENMİŞ - Satır İçi Ekle Butonlu)
        # ============================================================
        # 1.KOLON NORMALİZASYONU
        # ============================================================
        """
        Master-Detail Tablo Render Metodu (HATA DÜZELTİLDİ + TEMİZ GÖRÜNÜM)
        - Etiket (Label) sorunu giderildi (NoneType hatası çözüldü).
        - Tablo içi gereksiz boşluklar atıldı.
        """
        import copy # Eğer dosya başında yoksa buraya ekleyelim

        # ============================================================
        # 1.KOLON NORMALİZASYONU
        # ============================================================
        normalized_columns = []
        for col in self.columns:
            if isinstance(col, FormField):
                normalized_columns.append(col)
            elif isinstance(col, dict):
                raw_type = col.get('type', 'text')
                f_type = FieldType.TEXT
                if isinstance(raw_type, FieldType): f_type = raw_type
                
                field_obj = FormField(
                    name=col.get('name', 'unknown'),
                    field_type=f_type,
                    label=col.get('label', ''), 
                    placeholder=col.get('placeholder', ''),
                    required=col.get('required', False),
                    options=col.get('options', []),
                    default_value=col.get('default_value')
                )
                if col.get('html_attributes'): field_obj.html_attributes.update(col.get('html_attributes'))
                if col.get('width'): field_obj.html_attributes['width'] = col.get('width')
                if col.get('css_class'): field_obj.css_class = col.get('css_class')
                normalized_columns.append(field_obj)

        # 2.HTML ÇIKTISI
        table_id = f"tbl_{self.name}"
        html = []
        html.append(f'<div class="master-detail-container mb-3" data-name="{self.name}">')
        
        # --- DÜZELTME BURADA YAPILDI ---
        # Başlık SOLDA, Buton SAĞDA olacak şekilde hizaladık.
        html.append('<div class="d-flex justify-content-between align-items-center mb-2 pb-1 border-bottom">')
        
        # SOL: Başlık (Label)
        req_span = '<span class="text-danger">*</span>' if self.required else ''
        html.append(f'<h6 class="fw-bold mb-0 text-primary"><i class="bi bi-table me-2"></i>{escape(self.label)}{req_span}</h6>')
        
        # SAĞ: Ekle Butonu
        html.append(f'<button type="button" class="btn btn-sm btn-success btn-add-row" onclick="mdAddRow(\'{self.name}\')"><i class="bi bi-plus-lg"></i> Yeni Satır</button>')
        html.append('</div>')
        # -------------------------------
        
        html.append(f'<div class="table-responsive"><table class="table table-bordered table-hover align-middle shadow-sm" id="{table_id}">')
        
        # THEAD
        html.append('<thead class="table-light"><tr>')
        for col in normalized_columns:
            width_attr = col.html_attributes.get("width")
            style = col.html_attributes.get('style', '')
            if width_attr and 'width' not in style: style += f'; width: {width_attr}'
            style_attr = f' style="{style}"' if style else ''
            
            req_mark = ' <span class="text-danger">*</span>' if col.required else ''
            html.append(f'<th{style_attr} class="small text-muted text-uppercase fw-bold" style="font-size: 0.75rem;">{escape(col.label)}{req_mark}</th>')
        
        html.append('<th style="width: 100px;" class="text-center small text-muted text-uppercase fw-bold">İşlem</th></tr></thead>')        
               
        # Renderer Helper (Etiketleri temizle)
        def get_rendered_field(temp_col):
            temp_col.label = "" 
            temp_col.help_text = "" 
            temp_col.wrapper_div = False 
            temp_col.floating_label = False
            temp_col._render_label = lambda: "" 
            if temp_col.field_type == FieldType.CHECKBOX:
                return temp_col._render_checkbox().replace('form-check', 'd-flex justify-content-center')
            return temp_col.render()

        # TBODY
        html.append('<tbody>')
        if self.value and isinstance(self.value, list):
            for row_data in self.value:
                html.append('<tr>')
                for col in normalized_columns:
                    temp_col = copy.copy(col)
                    temp_col.name = f"{self.name}_{col.name}[]"
                    if 'id' in temp_col.html_attributes: del temp_col.html_attributes['id']
                    val = row_data.get(col.name, '')
                    temp_col.value = val
                    html.append(f'<td>{get_rendered_field(temp_col)}</td>')
                
                html.append(f'''
                    <td class="text-center text-nowrap">
                        <button type="button" class="btn btn-sm btn-success me-1 btn-add-inline" onclick="mdAddRow('{self.name}')" tabindex="0"><i class="bi bi-plus-lg"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="mdRemoveRow(this)" tabindex="-1"><i class="bi bi-trash"></i></button>
                    </td>
                ''')
                html.append('</tr>')
        html.append('</tbody>')
        
        # TFOOT
        has_total = any('total' in c.name or 'md-calc-total' in (c.css_class or '') for c in normalized_columns)
        if has_total:
            html.append('<tfoot><tr>')
            html.append(f'<td colspan="{len(normalized_columns)}" class="text-end fw-bold text-primary fs-5" id="md_grand_total">0,00 ₺</td>')
            html.append('<td></td></tr></tfoot>')
            
        html.append('</table></div>')
        
        # TEMPLATE
        html.append(f'<template id="tpl_{self.name}"><tr>')
        for col in normalized_columns:
            temp_col = copy.copy(col)
            temp_col.html_attributes = col.html_attributes.copy()
            temp_col.name = f"{self.name}_{col.name}[]"
            temp_col.value = temp_col.default_value if hasattr(temp_col, 'default_value') else ""
            if 'id' in temp_col.html_attributes: del temp_col.html_attributes['id']
            html.append(f'<td>{get_rendered_field(temp_col)}</td>')
            
        html.append(f'''
            <td class="text-center text-nowrap">
                <button type="button" class="btn btn-sm btn-success me-1 btn-add-inline" onclick="mdAddRow('{self.name}')" tabindex="-1"><i class="bi bi-plus-lg"></i></button>
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="mdRemoveRow(this)" tabindex="-1"><i class="bi bi-trash"></i></button>
            </td>
        ''')
        html.append('</tr></template></div>')
        
        return '\n'.join(html)    
               
        # --- RENDERER HARİTASI (TÜM TİPLER) ---
        # Bu fonksiyon, hem veri satırları hem de template için kullanılacak
        def get_rendered_field(temp_col):
            # Checkbox için özel durum: Tablo içinde etikete gerek yok
            checkbox_renderer = lambda: (setattr(temp_col, 'label', ''), temp_col._render_checkbox())[1]
            
            render_map = {
                # Metin Alanları
                FieldType.TEXTAREA: temp_col._render_textarea,
                FieldType.SELECT: temp_col._render_select,
                FieldType.CHECKBOX: checkbox_renderer,
                FieldType.RADIO: temp_col._render_radio,
                FieldType.SWITCH: temp_col._render_switch,
                FieldType.RICHTEXT: temp_col._render_richtext,
                FieldType.SIGNATURE: temp_col._render_signature,
                FieldType.JSON_EDITOR: temp_col._render_json,
                FieldType.MARKDOWN: temp_col._render_markdown,
                FieldType.CODE_EDITOR: temp_col._render_code_editor,
                
                # Tarih ve Zaman
                FieldType.DATE: temp_col._render_date,
                FieldType.DATETIME: temp_col._render_datetime,
                FieldType.TIME: temp_col._render_time,
                FieldType.MONTH: temp_col._render_month,
                FieldType.WEEK: temp_col._render_week,
                FieldType.TARIH: temp_col._render_tarih,
                FieldType.DATE_RANGE: temp_col._render_date_range,
                FieldType.DATE_TIME_RANGE: temp_col._render_datetime_range,

                # Diğerleri
                FieldType.IMAGE: temp_col._render_image,
                FieldType.FILES: temp_col._render_files,
                FieldType.RANGE: temp_col._render_range,
                FieldType.RANGE_DUAL: temp_col._render_range_dual,
                FieldType.GEOLOCATION: temp_col._render_geolocation,
                FieldType.MAP_POINT: temp_col._render_map_point,
                FieldType.BARCODE: temp_col._render_barcode,
                FieldType.BUTTON: temp_col._render_button,
                FieldType.CALC: temp_col._render_calc,
                FieldType.OTP: temp_col._render_otp,
                FieldType.TAGS: temp_col._render_tags,
                FieldType.RATING: temp_col._render_rating,
                FieldType.CURRENCY: temp_col._render_currency,
                FieldType.SEARCH: temp_col._render_search,
                FieldType.AUDIO_RECORDER: temp_col._render_media_recorder,
                FieldType.VIDEO_RECORDER: temp_col._render_media_recorder,
                FieldType.DRAWING: temp_col._render_drawing,
                FieldType.SLIDER: temp_col._render_slider,
                FieldType.AUTOCOMPLETE: temp_col._render_autocomplete,
                FieldType.COLOR: temp_col._render_color, 
                FieldType.COLOR_PICKER_ADVANCED: temp_col._render_color_advanced,
                FieldType.CAPTCHA: temp_col._render_captcha,
                FieldType.MASK: temp_col._render_mask,
                FieldType.MULTI_FIELD: temp_col._render_multi_field,
                FieldType.PASSWORD: lambda: temp_col._render_password_with_meter() if temp_col.strength_meter else temp_col._render_input(),
                FieldType.HTML: temp_col._render_html,
                FieldType.SCRIPT: temp_col._render_script,
                FieldType.MODAL: temp_col._render_modal,
                FieldType.HR: temp_col._render_hr,
                FieldType.HEADER: temp_col._render_header,
                FieldType.AUTO_NUMBER: temp_col._render_auto_number
            }
            # Haritada varsa özel fonksiyonu, yoksa standart input'u çağır
            return render_map.get(temp_col.field_type, temp_col._render_input)()

        # TBODY (Mevcut Veriler - Edit Modu)
        html.append('<tbody>')
        
        if self.value and isinstance(self.value, list):
            for row_data in self.value:
                html.append('<tr>')
                for col in normalized_columns:
                    # Nesnenin kopyasını al (Her satır için ayrı instance)
                    temp_col = copy.copy(col)
                    
                    # Name güncelle: kalemler_stok_id[]
                    temp_col.name = f"{self.name}_{col.name}[]"
                    
                    # ID sil (Çakışma olmasın, ancak JS gerektirenler için ID önemli olabilir)
                    # Not: AutoNumber, Map vb.benzersiz ID'ye ihtiyaç duyar.
                    # Burada basitçe siliyoruz, eğer sorun çıkarsa her satıra unique ID vermek gerekir.
                    if 'id' in temp_col.html_attributes: del temp_col.html_attributes['id']
                    
                    # Değeri satır verisinden al
                    val = row_data.get(col.name, '')
                    temp_col.value = val
                    
                    # Render
                    inp = get_rendered_field(temp_col)
                    html.append(f'<td>{inp}</td>')
                
                html.append('<td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="mdRemoveRow(this)"><i class="bi bi-trash"></i></button></td>')
                html.append('</tr>')
        
        html.append('</tbody>')
        
        # TFOOT (Alt Toplam Satırı)
        # Sütunlarda 'total' veya 'md-calc-total' geçen varsa dip toplam ekle
        has_total = False
        for c in normalized_columns:
            if 'total' in c.name or 'md-calc-total' in (c.css_class or ''):
                has_total = True
                break
                
        if has_total:
            html.append('<tfoot><tr>')
            col_count = len(normalized_columns)
            html.append(f'<td colspan="{col_count}" class="text-end fw-bold text-primary fs-5" id="md_grand_total">0,00 ₺</td>')
            html.append('<td></td></tr></tfoot>')
            
        html.append('</table></div>')
        
        # ============================================================
        # 3.TEMPLATE (YENİ SATIR ŞABLONU)
        # ============================================================
        html.append(f'<template id="tpl_{self.name}"><tr>')
        
        for col in normalized_columns:
            temp_col = copy.copy(col)
            temp_col.html_attributes = col.html_attributes.copy()
            
            temp_col.name = f"{self.name}_{col.name}[]"
            temp_col.value = temp_col.default_value if hasattr(temp_col, 'default_value') else ""
            
            if 'id' in temp_col.html_attributes: del temp_col.html_attributes['id']
            
            # Template Render
            inp = get_rendered_field(temp_col)
            html.append(f'<td>{inp}</td>')
            
        html.append('<td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="mdRemoveRow(this)"><i class="bi bi-trash"></i></button></td>')
        html.append('</tr></template></div>')
        
        return '\n'.join(html)

    def _render_modal(self):
        modal_id = f"modal_{self.name}"
        btn_text = self.html_attributes.get('btn_text', self.label or 'Aç')
        btn_class = self.html_attributes.get('btn_class', 'btn btn-primary')
        btn_icon = self.html_attributes.get('btn_icon', 'bi bi-window')
        size_class = self.html_attributes.get('size', '') 
        btn_html = (f'<button type="button" class="{btn_class}" data-bs-toggle="modal" data-bs-target="#{modal_id}"><i class="{btn_icon} me-1"></i> {escape(btn_text)}</button>')
        modal_body = Markup(str(self.value)) if self.value else ""
        modal_html = f'<div class="modal fade" id="{modal_id}" tabindex="-1" aria-labelledby="{modal_id}Label" aria-hidden="true"><div class="modal-dialog {size_class}"><div class="modal-content"><div class="modal-header"><h5 class="modal-title" id="{modal_id}Label">{escape(self.label)}</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Kapat"></button></div><div class="modal-body">{modal_body}</div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Kapat</button>{self.html_attributes.get("footer_html", "")}</div></div></div></div>'
        return btn_html + modal_html

    def _render_password_with_meter(self):
        css_classes = self.get_css_classes()
        html_attrs = self.get_html_attributes_string()
        policy = self.policy or {}
        min_len = int(policy.get('min', 0) or 0)
        min_upper = int(policy.get('upper', 0) or 0)
        min_digit = int(policy.get('digit', 0) or 0)
        min_special = int(policy.get('special', 0) or 0)
        attrs = f' data-strength="true" data-min="{min_len}" data-upper="{min_upper}" data-digit="{min_digit}" data-special="{min_special}"'
        html = []
        html.append('<div class="password-wrapper"><div class="input-group">')
        html.append(f'<input type="password" name="{self.name}" id="{self.name}" class="{css_classes} password-strength" {attrs}{html_attrs}>')
        html.append(f'<button class="btn btn-outline-secondary" type="button" data-toggle-password="{self.name}" title="Şifreyi Göster/Gizle"><i class="fas fa-eye"></i></button></div>')
        html.append(f'<div class="progress mt-1" id="{self.name}_strength_bar" style="height: 5px;"><div class="progress-bar bg-danger" role="progressbar" style="width: 0%; transition: width 0.3s;"></div></div>')
        if any([min_len, min_upper, min_digit, min_special]):
            html.append(f'<ul class="list-unstyled small mt-2 mb-0 text-muted" id="{self.name}_policy">')
            if min_len: html.append(f'<li data-rule="min" class="pending"><i class="far fa-circle me-1"></i> En az {min_len} karakter</li>')
            if min_upper: html.append(f'<li data-rule="upper" class="pending"><i class="far fa-circle me-1"></i> En az {min_upper} büyük harf</li>')
            if min_digit: html.append(f'<li data-rule="digit" class="pending"><i class="far fa-circle me-1"></i> En az {min_digit} rakam</li>')
            if min_special: html.append(f'<li data-rule="special" class="pending"><i class="far fa-circle me-1"></i> En az {min_special} özel karakter</li>')
            html.append('</ul>')
        html.append('</div>')
        return '\n'.join(html)

    def _render_hr(self):
        """Ayırıcı çizgi render eder."""
        # Kullanıcı özel sınıf verdiyse onu, yoksa varsayılan stili kullanır.
        custom_class = self.css_class if self.css_class else "my-4 border-secondary opacity-50"
        return f'<hr class="{custom_class}" {self.get_html_attributes_string()}>'

    def _render_header(self):
        """Ara başlık (H1-H6) render eder."""
        # Tag tipi html_attributes içinde 'tag' anahtarıyla belirtilebilir (h1, h2...h6)
        # Varsayılan: h4
        tag = self.html_attributes.get('tag', 'h4')
        
        # Varsayılan stil sınıfları (Eğer css_class verilmediyse)
        default_class = "mb-3 mt-4 fw-bold text-primary"
        css_class = self.css_class if self.css_class else default_class
        
        text = escape(self.label) # Başlık metni label olarak girilir
        
        return f'<{tag} class="{css_class}" {self.get_html_attributes_string()}>{text}</{tag}>'

    def _render_auto_number(self):
        """
        Otomatik Numara Alanı (Güncellenmiş)
        """
        is_edit_mode = self.value is not None and str(self.value) != ""
        
        attrs_list = [f'{k}="{v}"' for k, v in self.html_attributes.items()]
        if is_edit_mode:
            attrs_list = [a for a in attrs_list if 'data-auto-fetch' not in a]
            
        attrs_str = " ".join(attrs_list)
        css_classes = self.get_css_classes()
        
        # ID varsa kullan, yoksa isimden türet (Template içinde ID olmayabilir)
        el_id = self.html_attributes.get('id', self.name)
        
        common_attrs = f'name="{self.name}" id="{el_id}" class="{css_classes}" data-type="auto_number" {attrs_str}'
        
        if self.required: common_attrs += ' required'
        
        icon_class = self.icon if self.icon else "bi bi-upc-scan"
        
        spinner_html = ""
        if not is_edit_mode:
            # Spinner ID'si de dinamik olmalı ama master-detail'de JS ile hallediyoruz
            spinner_html = f'''
            <span class="input-group-text bg-white text-primary" style="display:none;" data-spinner-for="{el_id}">
                <div class="spinner-border spinner-border-sm" role="status"></div>
            </span>
            '''

        # NOT: toggleLockGeneric fonksiyonunu JS dosyasında tanımladık.
        # Burada sadece onclick olayını o fonksiyona yönlendiriyoruz.
        # Master-Detail klonlama sırasında JS kodu ID'yi ve bu onclick'i güncelleyecek.
        # Normal render için statik ID kullanıyoruz.
        
        lock_icon_id = f"{el_id}_lock_icon"
        
        html = f'''
        <div class="input-group">
            <span class="input-group-text bg-light"><i class="{icon_class}"></i></span>
            
            <input type="text" {common_attrs} value="{self.value or ''}" readonly 
                   style="background-color: #e9ecef; cursor: not-allowed; font-family: monospace; font-weight: bold; letter-spacing: 1px;">
            
            {spinner_html}
            
            <button class="btn btn-warning" type="button" onclick="toggleLockGeneric('{el_id}')" title="Kilidi Aç">
                <i class="bi bi-lock-fill" id="{lock_icon_id}"></i>
            </button>
        </div>
        '''
        
        # Scripti sadece bu alan Master-Detail DIŞINDAYSA eklememiz yeterli olurdu
        # ama toggleLockGeneric global olduğu için artık inline script'e ihtiyacımız yok!
        # Tek ihtiyacımız JS dosyasında toggleLockGeneric'in tanımlı olması.
        
        return html

    def to_dict(self):
        """
        Bu metot, formu Mobil Uygulama (iOS/Android) için 
        JSON formatına hazırlar.HTML üretmez, SAF VERİ verir.
        """
        return {
            "id": self.name,
            "type": self.field_type.value,  # örn: "text", "select"
            "label": self.label,
            "placeholder": self.placeholder,
            "defaultValue": self.default_value,
            
            # Mobil uygulamanın da Web ile aynı validasyonu yapması için:
            "validation": {
                "required": self.required,
                "min": self.min_val,
                "max": self.max_val,
                "minLength": self.min_length,
                "pattern": self.pattern
            },
            
            # Görünüm ayarları (Mobilde de benzer dursun diye)
            "ui": {
                "icon": self.icon,
                "hidden": self.field_type == FieldType.HIDDEN,
                "readOnly": self.readonly
            },
            
            # Selectbox seçenekleri
            "options": [{"id": k, "label": v} for k, v in self.options] if self.options else []
        }





class MasterDetailField(FormField):
    def __init__(self, name, columns, label=None, **kwargs):
        super().__init__(name, field_type='masterdetail', label=label, **kwargs)
        self.columns = columns  # Kolon tanımları (liste: field_name, label, field_type vs.)

    def render(self):
        # Tablo, ekleme butonu ve şablon generasyonu
        html = f'<table id="tbl_{self.name}" class="table table-bordered">'
        html += '<thead><tr>'
        for col in self.columns:
            html += f'<th>{col["label"]}</th>'
        html += '<th>İşlem</th></tr></thead>'
        html += '<tbody></tbody></table>'
        html += f'<template id="tpl_{self.name}"><tr>'
        for col in self.columns:
            html += f'<td><input type="{col.get("type", "text")}" name="{self.name}_{col["name"]}[]" class="form-control"></td>'
        html += '<td><button type="button" onclick="mdRemoveRow(this)" class="btn btn-danger btn-sm">Sil</button></td></tr></template>'
        html += f'<button type="button" class="btn btn-success btn-sm" onclick="mdAddRow(\'{self.name}\')">Satır Ekle</button>'
        return html

