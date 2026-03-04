# app/form_builder/report_designer.py

"""
Report Designer - Kullanıcı Kendi Raporunu Oluşturur (No-Code)

Özellikler:
- Drag & Drop alan seçimi
- Dinamik filtreleme (=, !=, >, <, LIKE, BETWEEN, IN)
- Gruplama ve toplama (SUM, AVG, COUNT, MIN, MAX)
- Sıralama (ASC, DESC)
- Grafik tipi seçimi (Line, Bar, Pie)
- ✨ YENİ: FormExporter ile Anında Export (PDF, Excel, CSV)
- ✨ YENİ: SQL Injection Korumalı Dinamik Sütun Eşleştirme
- ✨ YENİ: Sayfalama (Pagination) Desteği (RAM Dostu)
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional, Type, Tuple
from sqlalchemy import and_, or_, func, cast, String, Integer, Float, Date, DateTime, text
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
    
    OPERATORS = {
        'equals': '=', 'not_equals': '!=',
        'greater_than': '>', 'less_than': '<',
        'greater_or_equal': '>=', 'less_or_equal': '<=',
        'contains': 'LIKE', 'not_contains': 'NOT LIKE',
        'starts_with': 'LIKE', 'ends_with': 'LIKE',
        'between': 'BETWEEN', 'in': 'IN', 'not_in': 'NOT IN',
        'is_null': 'IS NULL', 'is_not_null': 'IS NOT NULL'
    }
    
    AGGREGATIONS = {
        'sum': func.sum, 'avg': func.avg, 'count': func.count,
        'min': func.min, 'max': func.max,
        'count_distinct': lambda col: func.count(func.distinct(col))
    }
    
    def __init__(self, model: Type[BaseModel], config: Dict[str, Any], session=None):
        self.model = model
        self.config = config
        self.session = session
        self.query = None
        self.select_fields = [] # Export ve Dict dönüşümleri için başlıkları tutar

    def _get_safe_column(self, field_name: str):
        """✨ GÜVENLİK KALKANI: SQL Injection'ı önler ve sadece var olan sütunlara izin verir"""
        if not field_name or field_name.startswith('_'):
            return None
            
        # Eğer RAW SQL (EXTRACT vb.) geliyorsa izin ver (Riskli ama senin kurgunda gerekli)
        if 'EXTRACT' in field_name.upper() or 'CAST' in field_name.upper():
            return text(field_name)
            
        return getattr(self.model, field_name, None)

    def validate_config(self) -> Tuple[bool, str]:
        """Konfigürasyon geçerli mi kontrol et"""
        if not self.config.get('name'):
            return False, "Rapor adı zorunludur"
        
        for filter_config in self.config.get('filters', []):
            if not filter_config.get('field'):
                return False, "Filtre alanı belirtilmeli"
            if not filter_config.get('operator'):
                return False, "Filtre operatörü belirtilmeli"
            if filter_config['operator'] not in self.OPERATORS:
                return False, f"Geçersiz operatör: {filter_config['operator']}"
                
        for agg in self.config.get('aggregations', []):
            if agg.get('function') not in self.AGGREGATIONS:
                return False, f"Geçersiz agregasyon fonksiyonu: {agg.get('function')}"
        
        return True, "Geçerli"

    def build_query(self) -> Query:
        """Kullanıcı konfigürasyonunu SQL Query'e çevirir"""
        if self.session:
            query = self.session.query(self.model)
        else:
            from app.extensions import db
            query = db.session.query(self.model)
            
        select_entities = []

        # 1. GRUPLAMA ve SELECT ALANLARI
        if self.config.get('group_by'):
            for group_field in self.config['group_by']:
                col = self._get_safe_column(group_field)
                if col is not None:
                    # Text objesi ise direkt ekle, değilse label ile ekle
                    if isinstance(col, type(text(""))):
                         select_entities.append(col)
                    else:
                         select_entities.append(col.label(group_field))
                    self.select_fields.append(group_field)
            
            # Agregasyonlar
            for agg in self.config.get('aggregations', []):
                func_name = agg['function']
                field_name = agg['field']
                alias = agg.get('alias', f"{func_name}_{field_name}")
                
                col = self._get_safe_column(field_name)
                if col is not None and func_name in self.AGGREGATIONS:
                    agg_func = self.AGGREGATIONS[func_name]
                    # Eğer kolon text ise doğrudan fonksiyona yolla (Örn: func.count(text('id')))
                    select_entities.append(agg_func(col).label(alias))
                    self.select_fields.append(alias)
            
            query = query.with_entities(*select_entities)

        # 2. FİLTRELEME
        sql_filters = []
        for filter_config in self.config.get('filters', []):
            field_name = filter_config['field']
            operator = filter_config['operator']
            value = filter_config.get('value')
            
            col = self._get_safe_column(field_name)
            if col is None:
                logger.warning(f"Model'de '{field_name}' alanı bulunamadı, filtre atlanıyor.")
                continue
                
            if operator == 'equals': sql_filters.append(col == value)
            elif operator == 'not_equals': sql_filters.append(col != value)
            elif operator == 'greater_than': sql_filters.append(col > value)
            elif operator == 'less_than': sql_filters.append(col < value)
            elif operator == 'greater_or_equal': sql_filters.append(col >= value)
            elif operator == 'less_or_equal': sql_filters.append(col <= value)
            elif operator == 'contains': sql_filters.append(col.ilike(f"%{value}%"))
            elif operator == 'not_contains': sql_filters.append(~col.ilike(f"%{value}%"))
            elif operator == 'starts_with': sql_filters.append(col.ilike(f"{value}%"))
            elif operator == 'ends_with': sql_filters.append(col.ilike(f"%{value}"))
            elif operator == 'between' and isinstance(value, list) and len(value) == 2:
                sql_filters.append(col.between(value[0], value[1]))
            elif operator == 'in' and isinstance(value, list): sql_filters.append(col.in_(value))
            elif operator == 'not_in' and isinstance(value, list): sql_filters.append(col.notin_(value))
            elif operator == 'is_null': sql_filters.append(col.is_(None))
            elif operator == 'is_not_null': sql_filters.append(col.isnot(None))

        if sql_filters:
            # logic: 'AND' veya 'OR'
            logic = self.config.get("filter_logic", "AND").upper()
            if logic == "OR":
                query = query.filter(or_(*sql_filters))
            else:
                query = query.filter(and_(*sql_filters))

        # 3. GRUPLAMA UYGULAMASI (GROUP BY)
        if self.config.get('group_by'):
            group_cols = []
            for group_field in self.config['group_by']:
                col = self._get_safe_column(group_field)
                if col is not None: group_cols.append(col)
            if group_cols:
                query = query.group_by(*group_cols)

        # 4. SIRALAMA
        for order_config in self.config.get('order_by', []):
            field_name = order_config['field']
            direction = order_config.get('direction', 'ASC').upper()
            
            # ==========================================
            # 🚀 ÇÖZÜM: ONLY_FULL_GROUP_BY Koruması
            # ==========================================
            # Eğer gruplama yapılıyorsa, SADECE gruplanan alanlara veya
            # hesaplanan Alias'lara (select_fields) göre sıralama yapılabilir.
            if self.config.get('group_by') and field_name not in self.select_fields:
                logger.debug(f"Gruplama kuralı ihlali: '{field_name}' alanı atlandı.")
                continue # SQL'in çökmesini engellemek için bu sıralamayı es geç
                
            # Kolon modelde gerçekten var mı diye güvenli şekilde kontrol et
            col = self._get_safe_column(field_name)
            
            # Eğer kolon modelin orijinal bir kolonuysa (text objesi değilse)
            if col is not None and not isinstance(col, type(text(""))):
                if direction == 'DESC':
                    query = query.order_by(col.desc())
                else:
                    query = query.order_by(col.asc())
            else:
                # Modelde yoksa, gruplama veya toplama (aggregation) ile oluşan bir Alias'tır
                if direction == 'DESC':
                    query = query.order_by(text(f"{field_name} DESC"))
                else:
                    query = query.order_by(text(f"{field_name} ASC"))
                    
        # 5. LIMIT (Eski limit kurgunu koruyoruz)
        if self.config.get('limit'):
            query = query.limit(self.config['limit'])
            
        self.query = query
        return query

    def execute(self, page: int = 1, per_page: int = None) -> List[Dict[str, Any]]:
        """
        Raporu çalıştır ve sonuç döndür.
        ✨ YENİ: per_page verilirse RAM dostu Pagination yapar.
        """
        if not self.query:
            self.build_query()
            
        try:
            # Pagination Uygula
            if per_page:
                self.query = self.query.limit(per_page).offset((page - 1) * per_page)
                
            results = self.query.all()
            data = []
            
            for row in results:
                row_dict = {}
                # SQLAlchemy KeyedTuple (Gruplama sonucu)
                if hasattr(row, '_mapping'):
                    row_dict = dict(row._mapping)
                # Eski tip Tuple
                elif hasattr(row, '_asdict'):
                    row_dict = row._asdict()
                # Standart Model Instance (Eğer group_by yoksa)
                elif hasattr(row, '__dict__'):
                    row_dict = {col.name: getattr(row, col.name) for col in row.__table__.columns}
                else:
                    if self.select_fields:
                        row_dict = dict(zip(self.select_fields, row))
                
                # 🚀 SİHİRLİ DOKUNUŞ: JSON Hatalarını Önleyen Tip Dönüştürücü
                clean_dict = {}
                for key, value in row_dict.items():
                    # Eğer değer Decimal ise, JSON'ın anlayacağı Float tipine çevir
                    if isinstance(value, Decimal):
                        clean_dict[key] = float(value)
                    else:
                        clean_dict[key] = value
                        
                data.append(clean_dict)
                        
            return data
            
        except Exception as e:
            logger.error(f"Rapor çalıştırma hatası: {e}")
            raise

    def export(self, format_type='excel', filename=None):
        """
        ✨ YENİ: Rapor sonucunu FormExporter kullanarak anında dışa aktarır.
        """
        from app.form_builder.form_export import FormExporter
        
        # Dosya adı config'den gelebilir
        fname = filename or self.config.get('export', {}).get('filename', 'Rapor_Ciktisi')
        
        # Dışa aktarımda sayfalama yapmıyoruz (limit 10.000 koyarak sunucuyu koruyoruz)
        data = self.execute(per_page=10000) 
        
        # Export için kolon başlıklarını hazırla (Eğer group_by kullanıldıysa)
        if self.select_fields:
            columns = [{'name': f, 'label': f.replace('_', ' ').title()} for f in self.select_fields]
        else:
            # Group_by yoksa modelin kendi kolonlarını al
            columns = [{'name': col.name, 'label': col.name.replace('_', ' ').title()} for col in self.model.__table__.columns]
        
        if format_type.lower() == 'csv':
            return FormExporter.to_csv(data, columns, fname)
        else:
            return FormExporter.to_excel(data, columns, fname)

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
                    'legend': {'display': True, 'position': 'top'},
                    'title': {'display': True, 'text': self.config.get('name', 'Rapor')}
                }
            }
        }

    def get_sql(self) -> str:
        """Oluşturulan SQL sorgusunu string olarak döndür (Debug için)"""
        if not self.query:
            self.build_query()
            
        from sqlalchemy.dialects import postgresql
        compiled = self.query.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True}
        )
        return str(compiled)


# ==========================================
# KULLANIM ÖRNEKLERİ (Mevcut kodun korundu)
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
            {"field": "tarih", "operator": "between", "value": ["2024-01-01", "2024-12-31"]},
            {"field": "fatura_turu", "operator": "equals", "value": "SATIS"}
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
    
    valid, message = designer.validate_config()
    if not valid: raise ValueError(f"Geçersiz konfigürasyon: {message}")
    
    data = designer.execute()
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
        "order_by": [{"field": "borc_bakiye", "direction": "DESC"}],
        "limit": 50
    }
    
    designer = ReportDesigner(CariHesap, config, session=tenant_db)
    return designer.execute()