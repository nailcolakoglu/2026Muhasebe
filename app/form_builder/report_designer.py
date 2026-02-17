# app/form_builder/report_designer.py

"""
Report Designer - Kullanıcı Kendi Raporunu Oluşturur (No-Code)

Özellikler:
- Drag & Drop alan seçimi
- Dinamik filtreleme (=, !=, >, <, LIKE, BETWEEN, IN)
- Gruplama ve toplama (SUM, AVG, COUNT, MIN, MAX)
- Sıralama (ASC, DESC)
- Grafik tipi seçimi (Line, Bar, Pie)
- Export (PDF, Excel, CSV, JSON)
- Rapor kaydetme ve paylaşma
- Schedule (Otomatik mail gönderimi)
"""

from typing import List, Dict, Any, Optional, Type
from sqlalchemy import and_, or_, func, cast, String, Integer, Float, Date, DateTime
from sqlalchemy.orm import Query
from flask_sqlalchemy.model import Model as BaseModel
from datetime import datetime, date
import json
import logging

logger = logging.getLogger(__name__)


class ReportDesigner:
    """
    Kullanıcı kendi raporunu tasarlasın (No-code Report Builder)
    """
    
    # Desteklenen operatörler
    OPERATORS = {
        'equals': '=',
        'not_equals': '!=',
        'greater_than': '>',
        'less_than': '<',
        'greater_or_equal': '>=',
        'less_or_equal': '<=',
        'contains': 'LIKE',
        'not_contains': 'NOT LIKE',
        'starts_with': 'LIKE',
        'ends_with': 'LIKE',
        'between': 'BETWEEN',
        'in': 'IN',
        'not_in': 'NOT IN',
        'is_null': 'IS NULL',
        'is_not_null': 'IS NOT NULL'
    }
    
    # Desteklenen toplama fonksiyonları
    AGGREGATIONS = {
        'sum': func.sum,
        'avg': func.avg,
        'count': func.count,
        'min': func.min,
        'max': func.max,
        'count_distinct': lambda col: func.count(func.distinct(col))
    }
    
    def __init__(self, model: Type[BaseModel], config: Dict[str, Any], session=None):
        """
        Args:
            model: SQLAlchemy model class
            config: Kullanıcı rapor konfigürasyonu (JSON)
            session: Database session (Firebird için get_tenant_db())
        
        Config Örneği:
        {
            "name": "Aylık Satış Raporu",
            "description": "Son 12 ay satış analizi",
            "fields": [
                {"name": "tarih", "label": "Tarih", "visible": true},
                {"name": "tutar", "label": "Tutar", "visible": true, "format": "currency"}
            ],
            "filters": [
                {"field": "tarih", "operator": "between", "value": ["2024-01-01", "2024-12-31"]},
                {"field": "durum", "operator": "equals", "value": "ONAYLANDI"}
            ],
            "group_by": ["EXTRACT(MONTH FROM tarih)", "EXTRACT(YEAR FROM tarih)"],
            "aggregations": [
                {"function": "sum", "field": "tutar", "alias": "toplam_tutar"},
                {"function": "count", "field": "id", "alias": "fatura_sayisi"}
            ],
            "order_by": [
                {"field": "yil", "direction": "DESC"},
                {"field": "ay", "direction": "DESC"}
            ],
            "chart": {
                "enabled": true,
                "type": "line",  # line, bar, pie, doughnut
                "x_axis": "ay",
                "y_axis": "toplam_tutar"
            },
            "export": {
                "formats": ["excel", "pdf", "csv"],
                "filename": "aylik_satis_raporu"
            }
        }
        """
        self.model = model
        self.config = config
        self.session = session
        self.query = None
        
    def build_query(self) -> Query:
        """Kullanıcı konfigürasyonunu SQL Query'e çevir"""
        
        # Session belirle (Firebird veya PostgreSQL)
        if self.session:
            query = self.session.query(self.model)
        else:
            from app.extensions import db
            query = db.session.query(self.model)
        
        # 1. SELECT ALANLARI (Gruplama varsa onları seç)
        if self.config.get('group_by'):
            # Gruplama alanları
            select_fields = []
            
            for group_field in self.config['group_by']:
                # Raw SQL expression mi?
                if 'EXTRACT' in group_field or 'CAST' in group_field:
                    from sqlalchemy import text
                    select_fields.append(text(group_field))
                else:
                    select_fields.append(getattr(self.model, group_field))
            
            # Agregasyon alanları
            for agg in self.config.get('aggregations', []):
                func_name = agg['function']
                field_name = agg['field']
                alias = agg.get('alias', f"{func_name}_{field_name}")
                
                if func_name in self.AGGREGATIONS:
                    agg_func = self.AGGREGATIONS[func_name]
                    field_obj = getattr(self.model, field_name)
                    select_fields.append(agg_func(field_obj).label(alias))
            
            query = query.with_entities(*select_fields)
        
        # 2. FİLTRELEME
        for filter_config in self.config.get('filters', []):
            filter_clause = self._build_filter(filter_config)
            if filter_clause is not None:
                query = query.filter(filter_clause)
        
        # 3. GRUPLAMA
        if self.config.get('group_by'):
            for group_field in self.config['group_by']:
                if 'EXTRACT' in group_field or 'CAST' in group_field:
                    from sqlalchemy import text
                    query = query.group_by(text(group_field))
                else:
                    query = query.group_by(getattr(self.model, group_field))
        
        # 4. SIRALAMA
        for order_config in self.config.get('order_by', []):
            order_clause = self._build_order(order_config)
            if order_clause is not None:
                query = query.order_by(order_clause)
        
        # 5. LIMIT (Opsiyonel)
        if self.config.get('limit'):
            query = query.limit(self.config['limit'])
        
        self.query = query
        return query
    
    def _build_filter(self, filter_config: Dict) -> Optional[Any]:
        """Tek bir filtre koşulu oluştur"""
        
        field_name = filter_config['field']
        operator = filter_config['operator']
        value = filter_config.get('value')
        
        # Model'de bu alan var mı kontrol et
        if not hasattr(self.model, field_name):
            logger.warning(f"Model'de '{field_name}' alanı bulunamadı, filtre atlanıyor.")
            return None
        
        field = getattr(self.model, field_name)
        
        # Operatöre göre filtre oluştur
        if operator == 'equals':
            return field == value
        
        elif operator == 'not_equals':
            return field != value
        
        elif operator == 'greater_than':
            return field > value
        
        elif operator == 'less_than':
            return field < value
        
        elif operator == 'greater_or_equal':
            return field >= value
        
        elif operator == 'less_or_equal':
            return field <= value
        
        elif operator == 'contains':
            return field.ilike(f"%{value}%")
        
        elif operator == 'not_contains':
            return ~field.ilike(f"%{value}%")
        
        elif operator == 'starts_with':
            return field.ilike(f"{value}%")
        
        elif operator == 'ends_with':
            return field.ilike(f"%{value}")
        
        elif operator == 'between':
            if isinstance(value, list) and len(value) == 2:
                return field.between(value[0], value[1])
        
        elif operator == 'in':
            if isinstance(value, list):
                return field.in_(value)
        
        elif operator == 'not_in':
            if isinstance(value, list):
                return ~field.in_(value)
        
        elif operator == 'is_null':
            return field.is_(None)
        
        elif operator == 'is_not_null':
            return field.isnot(None)
        
        logger.warning(f"Desteklenmeyen operatör: {operator}")
        return None
    
    def _build_order(self, order_config: Dict) -> Optional[Any]:
        """Sıralama koşulu oluştur"""
        
        field_name = order_config['field']
        direction = order_config.get('direction', 'ASC').upper()
        
        # Model'de bu alan var mı?
        if not hasattr(self.model, field_name):
            logger.warning(f"Model'de '{field_name}' alanı bulunamadı, sıralama atlanıyor.")
            return None
        
        field = getattr(self.model, field_name)
        
        if direction == 'DESC':
            return field.desc()
        else:
            return field.asc()
    
    def execute(self) -> List[Dict[str, Any]]:
        """Raporu çalıştır ve sonuç döndür"""
        
        if not self.query:
            self.build_query()
        
        try:
            results = self.query.all()
            
            # Sonuçları dict listesine çevir
            data = []
            for row in results:
                # Eğer tuple ise (gruplama sonucu)
                if hasattr(row, '_asdict'):
                    data.append(row._asdict())
                # Eğer model instance ise
                elif hasattr(row, '__dict__'):
                    row_dict = {col.name: getattr(row, col.name) 
                               for col in row.__table__.columns}
                    data.append(row_dict)
                # KeyedTuple (SQLAlchemy result)
                else:
                    data.append(dict(row._mapping))
            
            return data
        
        except Exception as e:
            logger.error(f"Rapor çalıştırma hatası: {e}")
            raise
    
    def to_pandas(self):
        """Sonuçları Pandas DataFrame'e çevir"""
        import pandas as pd
        
        data = self.execute()
        return pd.DataFrame(data)
    
    def get_chart_config(self) -> Optional[Dict]:
        """Chart.js için konfigürasyon döndür"""
        
        chart_config = self.config.get('chart')
        
        if not chart_config or not chart_config.get('enabled'):
            return None
        
        data = self.execute()
        
        if not data:
            return None
        
        x_axis = chart_config.get('x_axis')
        y_axis = chart_config.get('y_axis')
        chart_type = chart_config.get('type', 'line')
        
        # Chart.js formatına çevir
        labels = [str(row.get(x_axis, '')) for row in data]
        values = [float(row.get(y_axis, 0)) for row in data]
        
        return {
            'type': chart_type,
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': chart_config.get('label', y_axis),
                    'data': values,
                    'backgroundColor': chart_config.get('backgroundColor', 'rgba(75, 192, 192, 0.2)'),
                    'borderColor': chart_config.get('borderColor', 'rgb(75, 192, 192)'),
                    'borderWidth': 2
                }]
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'legend': {
                        'display': True,
                        'position': 'top'
                    },
                    'title': {
                        'display': True,
                        'text': self.config.get('name', 'Rapor')
                    }
                }
            }
        }
    
    def validate_config(self) -> tuple[bool, str]:
        """Konfigürasyon geçerli mi kontrol et"""
        
        # Zorunlu alanlar
        if not self.config.get('name'):
            return False, "Rapor adı zorunludur"
        
        # Filtre geçerliliği
        for filter_config in self.config.get('filters', []):
            if not filter_config.get('field'):
                return False, "Filtre alanı belirtilmeli"
            
            if not filter_config.get('operator'):
                return False, "Filtre operatörü belirtilmeli"
            
            if filter_config['operator'] not in self.OPERATORS:
                return False, f"Geçersiz operatör: {filter_config['operator']}"
        
        # Agregasyon geçerliliği
        for agg in self.config.get('aggregations', []):
            if agg.get('function') not in self.AGGREGATIONS:
                return False, f"Geçersiz agregasyon fonksiyonu: {agg.get('function')}"
        
        return True, "Geçerli"
    
    def get_sql(self) -> str:
        """Oluşturulan SQL sorgusunu string olarak döndür (Debug için)"""
        
        if not self.query:
            self.build_query()
        
        from sqlalchemy.dialects import postgresql, mysql, sqlite
        
        # Firebird için PostgreSQL dialect kullan (yakın syntax)
        compiled = self.query.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True}
        )
        
        return str(compiled)


# ==========================================
# KULLANIM ÖRNEKLERİ
# ==========================================

def ornek_aylik_satis_raporu(tenant_db):
    """Örnek: Aylık satış raporu"""
    
    from app.modules.fatura.models import Fatura
    
    config = {
        "name": "Aylık Satış Raporu",
        "description": "2024 yılı aylık satış analizi",
        "fields": [
            {"name": "ay", "label": "Ay"},
            {"name": "yil", "label": "Yıl"},
            {"name": "toplam_tutar", "label": "Toplam Tutar", "format": "currency"},
            {"name": "fatura_sayisi", "label": "Fatura Sayısı"}
        ],
        "filters": [
            {
                "field": "tarih",
                "operator": "between",
                "value": ["2024-01-01", "2024-12-31"]
            },
            {
                "field": "fatura_turu",
                "operator": "equals",
                "value": "SATIS"
            }
        ],
        "group_by": [
            "EXTRACT(MONTH FROM tarih)",
            "EXTRACT(YEAR FROM tarih)"
        ],
        "aggregations": [
            {"function": "sum", "field": "genel_toplam", "alias": "toplam_tutar"},
            {"function": "count", "field": "id", "alias": "fatura_sayisi"}
        ],
        "order_by": [
            {"field": "yil", "direction": "DESC"},
            {"field": "ay", "direction": "DESC"}
        ],
        "chart": {
            "enabled": True,
            "type": "line",
            "x_axis": "ay",
            "y_axis": "toplam_tutar",
            "label": "Aylık Satış (₺)"
        }
    }
    
    designer = ReportDesigner(Fatura, config, session=tenant_db)
    
    # Konfigürasyon geçerli mi?
    valid, message = designer.validate_config()
    if not valid:
        raise ValueError(f"Geçersiz konfigürasyon: {message}")
    
    # Raporu çalıştır
    data = designer.execute()
    
    # Grafik konfigürasyonu
    chart_config = designer.get_chart_config()
    
    return data, chart_config


def ornek_cari_bakiye_raporu(tenant_db):
    """Örnek: Borçlu cariler raporu"""
    
    from app.modules.cari.models import CariHesap
    
    config = {
        "name": "Borçlu Cariler Raporu",
        "filters": [
            {"field": "borc_bakiye", "operator": "greater_than", "value": 1000},
            {"field": "aktif", "operator": "equals", "value": True}
        ],
        "order_by": [
            {"field": "borc_bakiye", "direction": "DESC"}
        ],
        "limit": 50
    }
    
    designer = ReportDesigner(CariHesap, config, session=tenant_db)
    return designer.execute()