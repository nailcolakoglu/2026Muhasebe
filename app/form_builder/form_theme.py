# form_builder/form_theme.py

class FormTheme:
    def __init__(self, name, field_class="", panel_class="", label_class="", help_class=""):
        self.name = name
        self.field_class = field_class or "form-control"
        self.panel_class = panel_class or "card card-body"
        self.label_class = label_class or "form-label"
        self.help_class = help_class or "form-text text-muted"

# Örnek Sınıf Bazlı Temalar
BOOTSTRAP5_LIGHT = FormTheme(
    "bootstrap5-light",
    field_class="form-control",
    panel_class="card card-body bg-white shadow-sm",
    label_class="form-label fw-bold text-dark",
    help_class="form-text text-muted"
)

DARK_CARD = FormTheme(
    "dark-card",
    field_class="form-control bg-dark text-white border-dark",
    panel_class="card card-body bg-dark text-white",
    label_class="form-label fw-bold text-light",
    help_class="form-text text-light"
)

# --- YENİ EKLENEN SÖZLÜK TEMALAR (RENK PALETLERİ) ---
THEME_MATERIAL = {
    'colorfocus': '#e3f2fd', 
    'colorblur': '#ffffff', 
    'textfocus': '#1565c0', 
    'textblur': '#212121', 
    'borderfocus': '#2196f3', 
    'borderblur': '#e0e0e0'
}

THEME_SUCCESS = {
    'colorfocus': '#e8f5e9', 
    'colorblur': '#ffffff', 
    'textfocus': '#2e7d32', 
    'textblur': '#000000', 
    'borderfocus': '#4caf50', 
    'borderblur': '#bdbdbd'
}

THEME_WARNING = {
    'colorfocus': '#fff3e0', 
    'colorblur': '#ffffff', 
    'textfocus': '#e65100', 
    'textblur': '#424242', 
    'borderfocus': '#ff9800', 
    'borderblur': '#9e9e9e'
}

THEME_DANGER = {
    'colorfocus': '#ffebee', 
    'colorblur': '#ffffff', 
    'textfocus': '#c62828', 
    'textblur': '#000000', 
    'borderfocus': '#f44336', 
    'borderblur': '#757575'
}

THEME_PREMIUM = {
    'colorfocus': '#fff8e1', 
    'colorblur': '#ffffff', 
    'textfocus': '#f57f17', 
    'textblur': '#3e2723', 
    'borderfocus': '#ffc107', 
    'borderblur': '#bcaaa4'
}