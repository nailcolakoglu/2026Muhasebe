# form_builder/form_style.py

class FormStyle:
    """
    Formun görsel tasarımını yöneten sınıf.
    Bootstrap 5 CSS değişkenlerini (CSS Variables) manipüle eder.
    Tema desteği, renk ayarları ve veritabanından yükleme özelliklerine sahiptir.
    """
    
    def __init__(self, theme="default"):
        # Varsayılan Değerler
        self.primary_color = "#0d6efd"    # Ana Renk
        self.secondary_color = "#6c757d"  # İkincil Renk
        self.bg_color = "#ffffff"         # Arka Plan
        self.text_color = "#212529"       # Yazı Rengi
        self.border_radius = "0.375rem"   # Köşe Yuvarlaklığı
        self.font_family = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
        self.input_bg = "#ffffff"
        self.shadow = "0 0.5rem 1rem rgba(0, 0, 0, 0.15)" # Varsayılan gölge
        self.density = "normal"           # compact, normal, spacious
        
        if theme == "dark":
            self.apply_dark_theme()
        elif theme == "glass":
            self.apply_glass_theme()

    def set_colors(self, primary, secondary, bg_color="#ffffff", text="#212529"):
        self.primary_color = primary
        self.secondary_color = secondary
        self.bg_color = bg_color
        self.text_color = text
        return self

    def set_visuals(self, radius, shadow_level="medium"):
        if isinstance(radius, int):
            self.border_radius = f"{radius}px"
        else:
            self.border_radius = radius
        
        shadows = {
            "none": "none",
            "small": "0 2px 4px rgba(0,0,0,0.1)",
            "medium": "0 4px 8px rgba(0,0,0,0.12)",
            "large": "0 8px 24px rgba(0,0,0,0.15)"
        }
        self.shadow = shadows.get(shadow_level, shadows["medium"])
        return self

    def load_from_dict(self, data):
        if not data: return self
        self.primary_color = data.get('primary_color', self.primary_color)
        self.secondary_color = data.get('secondary_color', self.secondary_color)
        self.bg_color = data.get('bg_color', self.bg_color)
        self.text_color = data.get('text_color', self.text_color)
        
        radius_val = data.get('border_radius')
        if radius_val: self.border_radius = f"{radius_val}px"
            
        shadow_map = { "none": "none", "small": "0 2px 4px rgba(0,0,0,0.1)", "medium": "0 4px 8px rgba(0,0,0,0.12)", "large": "0 8px 24px rgba(0,0,0,0.15)" }
        selected_shadow = data.get('shadow_level', 'medium')
        self.shadow = shadow_map.get(selected_shadow, shadow_map['medium'])
        
        theme_preset = data.get('theme_preset')
        if theme_preset == 'dark': self.apply_dark_theme()
        elif theme_preset == 'glass': self.apply_glass_theme()
            
        if data.get('density'): self.density = data.get('density')
        return self

    def apply_dark_theme(self):
        self.bg_color = "#212529"
        self.text_color = "#f8f9fa"
        self.input_bg = "#2c3034"
        self.secondary_color = "#adb5bd"
        return self

    def apply_glass_theme(self):
        self.bg_color = "rgba(255, 255, 255, 0.25)"
        self.input_bg = "rgba(255, 255, 255, 0.5)"
        self.shadow = "0 8px 32px 0 rgba(31, 38, 135, 0.37)"
        self.text_color = "#000000"
        return self

    def generate_css(self, form_id):
        """
        Forma özel CSS bloğu üretir.
        Hatalar giderildi: Select padding, Input Group border radius ve Select2 uyumluluğu eklendi.
        """
        
        # Yoğunluk (Density) Ayarı
        padding_y = "0.375rem"
        padding_x = "0.75rem"
        font_size = "1rem"
        
        if self.density == "compact":
            padding_y, padding_x = "0.25rem", "0.5rem"
            font_size = "0.875rem"
        elif self.density == "spacious":
            padding_y, padding_x = "0.75rem", "1.25rem"
            font_size = "1.1rem"

        css = f"""
        <style>
            #{form_id} {{
                --bs-primary: {self.primary_color};
                --bs-secondary: {self.secondary_color};
                --bs-body-color: {self.text_color};
                --fb-bg-color: {self.bg_color};
                --fb-input-bg: {self.input_bg};
                --fb-radius: {self.border_radius};
                --fb-shadow: {self.shadow};
                
                font-family: {self.font_family};
                background-color: var(--fb-bg-color);
                color: var(--bs-body-color);
                padding: 20px;
                border-radius: var(--fb-radius);
                box-shadow: var(--fb-shadow);
                transition: all 0.3s ease;
            }}
            
            /* --- STANDART INPUTLAR --- */
            #{form_id} .form-control, 
            #{form_id} .input-group-text {{
                background-color: var(--fb-input-bg);
                border-radius: var(--fb-radius);
                padding: {padding_y} {padding_x};
                font-size: {font_size};
                border-color: {self.secondary_color}40;
            }}

            /* --- SELECT DÜZELTMESİ (HATA BURADAYDI) --- */
            /* Select kutularının sağ tarafında ok işareti için yer bırakmalıyız (2.25rem) */
            #{form_id} .form-select {{
                background-color: var(--fb-input-bg);
                border-radius: var(--fb-radius);
                padding: {padding_y} 2.25rem {padding_y} {padding_x}; /* Sağ padding artırıldı */
                font-size: {font_size};
                border-color: {self.secondary_color}40;
            }}

            /* --- SELECT2 UYUMLULUĞU (YENİ) --- */
            /* Select2 bileşenlerini de temaya uyduruyoruz */
            #{form_id} .select2-container--bootstrap-5 .select2-selection {{
                border-color: {self.secondary_color}40;
                border-radius: var(--fb-radius);
                background-color: var(--fb-input-bg);
                color: var(--bs-body-color);
                padding-top: {padding_y};
                padding-bottom: {padding_y};
                padding-left: {padding_x};
                min-height: calc(1.5em + ({padding_y} * 2) + 2px);
            }}
            
            /* --- INPUT GROUP KENARLIK DÜZELTMESİ (YENİ) --- */
            /* Yan yana inputlarda (Adet, TL vb.) aradaki köşeleri dik yap */
            #{form_id} .input-group > :not(:first-child):not(.dropdown-menu):not(.valid-tooltip):not(.valid-feedback):not(.invalid-tooltip):not(.invalid-feedback) {{
                border-top-left-radius: 0;
                border-bottom-left-radius: 0;
            }}
            #{form_id} .input-group > :not(:last-child):not(.dropdown-menu):not(.valid-tooltip):not(.valid-feedback):not(.invalid-tooltip):not(.invalid-feedback) {{
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
            }}

            /* --- FLOATING LABEL DÜZELTMESİ --- */
            #{form_id} .form-floating > .form-control,
            #{form_id} .form-floating > .form-select {{
                height: calc(3.5rem + 2px);
                padding-top: 1.625rem !important;
                padding-bottom: 0.625rem !important;
                line-height: 1.25;
            }}
            
            #{form_id} .form-floating > label {{
                padding: 1rem 0.75rem;
            }}
            
            /* Floating Label Rengi */
            #{form_id} .form-floating > .form-control:focus ~ label,
            #{form_id} .form-floating > .form-control:not(:placeholder-shown) ~ label {{
                color: {self.primary_color};
                opacity: 0.8;
            }}

            /* --- ODAKLANMA EFEKTLERİ --- */
            #{form_id} .form-control:focus, 
            #{form_id} .form-select:focus,
            #{form_id} .select2-container--bootstrap-5.select2-container--focus .select2-selection {{
                border-color: var(--bs-primary);
                box-shadow: 0 0 0 0.25rem {self.primary_color}40;
            }}

            /* --- KARTLAR --- */
            #{form_id} .card {{
                background-color: var(--fb-input-bg);
                border: 1px solid rgba(0,0,0,0.05);
                border-radius: var(--fb-radius);
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
            
            #{form_id} .card-header {{
                background-color: {self.primary_color}10;
                border-bottom: 1px solid rgba(0,0,0,0.05);
                color: var(--bs-primary);
                font-weight: 600;
                border-top-left-radius: var(--fb-radius);
                border-top-right-radius: var(--fb-radius);
            }}

            /* --- BUTONLAR --- */
            #{form_id} .btn-primary {{
                background-color: var(--bs-primary);
                border-color: var(--bs-primary);
                border-radius: var(--fb-radius);
                padding: {padding_y} {padding_x};
            }}
            
            #{form_id} .btn-primary:hover {{
                filter: brightness(90%);
            }}
            
            /* --- YARDIM METNİ --- */
            #{form_id} .form-text {{
                margin-top: 0.25rem; 
                font-size: 0.85em;
                margin-left: 0.2rem;
                opacity: 0.8;
            }}

            /* --- MODERN CARD RADIO GRUBU (YENİ EKLENDİ) --- */
            #{form_id} .radio-card-group {{
                display: flex;
                gap: 1rem;
                flex-wrap: wrap;
            }}

            #{form_id} .radio-card-group .btn-check + .btn {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 1rem 1.5rem;
                border-width: 2px;
                font-weight: 500;
                border-radius: var(--fb-radius) !important;
                flex: 1; /* Eşit genişlik */
                min-width: 120px; /* Minimum genişlik */
                transition: all 0.2s ease;
            }}
            
            #{form_id} .radio-card-group .btn-check + .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}

            /* Seçili durumdaki ikon rengi */
            #{form_id} .radio-card-group .btn-check:checked + .btn i {{
                color: inherit; /* Butonun metin rengini al */
            }}

            /* Seçili olmayan durumdaki ikon rengi (Daha silik) */
            #{form_id} .radio-card-group .btn-check:not(:checked) + .btn i {{
                color: {self.secondary_color}; 
                opacity: 0.7;
            }}

            /* İkon Boyutu ve Boşluğu */
            #{form_id} .radio-card-group .btn i {{
                margin-bottom: 0.5rem;
                font-size: 1.75rem; 
            }}


            {self._get_glass_css(form_id) if "rgba" in self.bg_color else ""}
        </style>
        """
        return css

    def _get_glass_css(self, form_id):
        return f"""
            #{form_id} {{
                backdrop-filter: blur( 10px );
                -webkit-backdrop-filter: blur( 10px );
                border: 1px solid rgba( 255, 255, 255, 0.18 );
            }}
        """