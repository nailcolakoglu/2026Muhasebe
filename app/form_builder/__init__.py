"""
Form Builder Package
Profesyonel form oluşturma ve yönetim sistemi
Nail Çolakoğlu - Sinem Çolakoğlu - Ceren Çolakoğlu
"""

from .field_types import FieldType
from .form_field import FormField, MasterDetailField
from .form import Form
from .form_layout import FormLayout 
from .form_style import FormStyle
from .multi_step_form import MultiStepForm
from .data_grid import DataGrid  
from .utils import sanitize_html, validate_file_security
from .validation_rules import ValidationRule, Validator
from .kanban import KanbanBoard
from .pivot import PivotEngine
from .workflow import WorkflowEngine
#from .menu_manager import MenuManager

# TEMALARI İÇERİ ALIYORUZ (THEME_MATERIAL EKLENDİ)
from .form_theme import (
    FormTheme, 
    DARK_CARD, 
    BOOTSTRAP5_LIGHT, 
    THEME_MATERIAL, 
    THEME_SUCCESS, 
    THEME_WARNING, 
    THEME_DANGER, 
    THEME_PREMIUM
)

# Utils modülünü paket olarak da erişilebilir yapıyoruz
from .import utils

__all__ = [
    'FieldType', 
    'FormField', 
    'Form', 
    'FormLayout',  
    'FormStyle',     
    'KanbanBoard',
    'MultiStepForm',
    'DataGrid', 
    'FormTheme',
    'utils',
    'ValidationRule',
    'Validator',
    'PivotEngine',
    'WorkflowEngine',
    'sanitize_html',
    'validate_file_security',
    # Temalar dışarıya açıldı
    'DARK_CARD',
    'BOOTSTRAP5_LIGHT',
    'THEME_MATERIAL',
    'THEME_SUCCESS',
    'THEME_WARNING',
    'THEME_DANGER',
    'THEME_PREMIUM'
]

__version__ = '26.58.35'