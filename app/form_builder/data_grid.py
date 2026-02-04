# data_grid.py

from typing import List, Dict, Any, Type, Optional, Union, Callable
from flask import url_for, request
from flask_sqlalchemy.model import Model as BaseModel
from sqlalchemy import or_, desc, asc, cast, String, select
from datetime import datetime, date, timedelta
from html import escape
from .field_types import FieldType

class DataGrid:
    """
    DataGrid Ultimate Version
    - Modern UI (CSS Class ve Badge Desteği)
    - Akıllı Hizalama (Sayısal alanlar otomatik sağa yaslanır)
    - Tam Kolon Yönetimi (Gizleme, Sıralama, Yeniden Adlandırma)
    - Güvenli SQL Sorguları
    - Custom Render Function Desteği (render_func)
    - DİKKAT DataGrid paginate Kullanıyor Ama SQLAlchemy 2.0'da Yok
    - SQLAlchemy 2.0 uygun 
    - from sqlalchemy import select   eklendi.

    """

    def __init__(self, name: str, model: Type[BaseModel], title: str = "Veri Listesi", 
                 per_page: int = 10,
                 enable_grouping: bool = False, enable_summary: bool = False,
                 summary_fields: Optional[List[str]] = None, target=None):
        self.name = name
        self.model = model
        self.title = title
        self.columns: List[Dict[str, Any]] = []
        self.data: List[Any] = []
        self.pagination = {'page': 1, 'total_pages': 1, 'total_items': 0}
        self.per_page = per_page
        self.enable_grouping = enable_grouping
        self.enable_summary = enable_summary
        self.summary_fields = summary_fields or []
        self.actions: List[Any] = []
        self.export_action: Optional[Dict] = None
        
        self.current_sort_field: Optional[str] = None
        self.current_sort_direction: str = 'asc' 
        
        # Başlangıçta tüm model alanlarını oluştur
        self._auto_generate_columns()
        self.target=target
    # =================================================================
    # 1.KOLON YÖNETİMİ (EKSİK OLAN METODLAR EKLENDİ)
    # =================================================================

    def add_column(self, name: str, title: str = None, width: str = None, 
                   type: FieldType = FieldType.TEXT, sortable: bool = False, 
                   badge_colors: dict = None, css_class: str = "" , 
                   render_func: Callable[[Any], str] = None ):
        """
        Grid'e manuel sütun ekler veya mevcut olanı günceller.
        render_func: Satır verisini (row object) alıp string döndüren özel fonksiyon.
        """
        # Var olanı güncelle
        for col in self.columns:
            if col['name'] == name:
                if title: col['label'] = title
                if width: col['width'] = width
                col['type'] = type
                col['sortable'] = sortable
                if badge_colors: col['badge_colors'] = badge_colors
                if css_class: col['css_class'] = css_class
                if render_func: col['render_func'] = render_func
                return self

        # Yeni ekle
        self.columns.append({
            'name': name,
            'label': title or name.replace('_', ' ').capitalize(),
            'type': type,
            'sortable': sortable,
            'visible': True,
            'width': width,
            'badge_colors': badge_colors or {},
            'css_class': css_class, 
            'render_func': render_func
        })
        return self

    def reorder_column(self, name: str, new_index: int):
        """Sütunu listeden alır ve new_index sırasına taşır."""
        current_index = next((i for i, c in enumerate(self.columns) if c['name'] == name), None)
        if current_index is not None:
            col = self.columns.pop(current_index)
            self.columns.insert(new_index, col)
        return self

    def set_column_order(self, ordered_names: list):
        """Sütunları verilen isim listesine göre dizer."""
        col_map = {c['name']: c for c in self.columns}
        new_columns = []
        # 1.Listede belirtilenleri sırayla ekle
        for name in ordered_names:
            if name in col_map:
                new_columns.append(col_map[name])
                del col_map[name]
        # 2.Kalanları sona ekle
        new_columns.extend(col_map.values())
        self.columns = new_columns
        return self

    def set_column_label(self, name: str, label: str):
        """Sütun başlığını değiştirir."""
        for col in self.columns:
            if col['name'] == name:
                col['label'] = label; break
        return self
    
    def hide_column(self, name: str):
        """Sütunu gizler."""
        for col in self.columns:
            if col['name'] == name:
                col['visible'] = False; break
        return self
        
    def add_action(self, name: str, label: str, icon: str, class_name: str, 
                   action_type: str = 'route', route_name: Optional[Union[str, Any]] = None, 
                   html_attributes: dict = None, target=None):
        """Aksiyon butonu ekler (Düzenle, Sil vb.)."""
        self.actions.append({
            'name': name, 'label': label, 'icon': icon, 'class': class_name,
            'action_type': action_type, 'route_name': route_name or name,
            'html_attributes': html_attributes or {}, 'target': target
        })
        return self

    def add_export_action(self, label_page="Bu Sayfayı İndir", label_all="Tümünü İndir", 
                          format="csv", icon_page="bi bi-file-earmark-excel", 
                          icon_all="bi bi-download", class_page="btn-outline-success", 
                          class_all="btn-success"):
        """Export butonlarını yapılandırır."""
        self.export_action = {
            "label_page": label_page, "label_all": label_all, "format": format,
            "icon_page": icon_page, "icon_all": icon_all,
            "class_page": class_page, "class_all": class_all
        }
        return self

    # =================================================================
    # 2.SORGULAMA MANTIĞI (Process Query)
    # =================================================================

    def process_query(self, query, default_sort:  tuple = None):
        """Request argümanlarını alır ve sorguyu işler."""
        
        # A.KOLON FİLTRELEME
        for col in self.columns:
            field_name = col['name']
            
            # Modelde bu alan var mı?
            if not hasattr(self.model, field_name):
                continue
                
            column_attr = getattr(self.model, field_name)
            
            # --- Tarih Aralığı ve Tam Eşleşme Filtreleme ---
            if col['type'] in [FieldType.DATE, FieldType.DATETIME]:
                start_val = request.args.get(f"{field_name}_start")
                end_val = request.args.get(f"{field_name}_end")
                exact_val = request.args.get(field_name)
                
                # Format belirleme
                fmt = '%Y-%m-%d' if col['type'] == FieldType.DATE else '%Y-%m-%dT%H:%M:%S'
                
                # 1.Aralık Araması (Start)
                if start_val: 
                    try:
                        dt = datetime.strptime(start_val, fmt)
                        if col['type'] == FieldType.DATE:  dt = dt.date()
                        query = query.filter(column_attr >= dt)
                    except ValueError:  pass
                
                # 2.Aralık Araması (End)
                if end_val: 
                    try:
                        dt = datetime.strptime(end_val, fmt)
                        if col['type'] == FieldType.DATE: dt = dt.date()
                        query = query.filter(column_attr <= dt)
                    except ValueError: pass

                # 3.Tekil (Tam) Eşleşme
                if exact_val:
                    try:
                        dt_val = datetime.strptime(exact_val, '%Y-%m-%d') 
                        if col['type'] == FieldType.DATE: 
                            dt_val = dt_val.date()
                            query = query.filter(column_attr == dt_val)
                        else:
                            from datetime import timedelta
                            next_day = dt_val + timedelta(days=1)
                            query = query.filter(column_attr >= dt_val, column_attr < next_day)
                    except ValueError: pass
            # --- Standart Filtreleme ---
            else: 
                filter_value = request.args.get(field_name)
                if filter_value:
                    if col['type'] == FieldType.TEXT:
                        query = query.filter(column_attr.ilike(f"%{filter_value}%"))
                    elif col['type'] in [FieldType.NUMBER, FieldType.CURRENCY, FieldType.TCKN, FieldType.VKN]:
                        query = query.filter(cast(column_attr, String(50)).ilike(f"%{filter_value}%"))
                    elif col['type'] == FieldType.SWITCH:
                        bool_val = filter_value.lower() in ['true', '1', 'yes', 'on']
                        query = query.filter(column_attr == bool_val)
                    else:
                        query = query.filter(column_attr == filter_value)

        # B.GLOBAL ARAMA ('q' parametresi)
        global_search = request.args.get('q') 
        if global_search: 
            search_filters = []
            for col in self.columns:
                if not col['visible'] or not hasattr(self.model, col['name']): continue
                column_attr = getattr(self.model, col['name'])
                
                if col['type'] == FieldType.TEXT:
                    search_filters.append(column_attr.ilike(f"%{global_search}%"))
                elif col['type'] in [FieldType.NUMBER, FieldType.CURRENCY, FieldType.TCKN]: 
                    search_filters.append(cast(column_attr, String).ilike(f"%{global_search}%"))
            
            if search_filters:
                query = query.filter(or_(*search_filters))

        # C.SIRALAMA
        sort_col = request.args.get('sort')
        sort_dir = request.args.get('direction', 'asc')
        
        if not sort_col and default_sort:
            sort_col, sort_dir = default_sort

        if sort_col and hasattr(self.model, sort_col):
            column_attr = getattr(self.model, sort_col)
            try:
                query = query.order_by(desc(column_attr) if sort_dir == 'desc' else asc(column_attr))
                self.current_sort_field = sort_col
                self.current_sort_direction = sort_dir
            except:  pass
        
        # D.SAYFALAMA (✅ SQLAlchemy 2.0 Uyumlu)
        try:  
            page = int(request.args.get('page', 1))
        except: 
            page = 1
        
        # ✅ MANUEL PAGINATION (query.paginate() yerine)
        from sqlalchemy import func
        
        # Toplam kayıt sayısı
        total = query.count()
        
        # Sayfa hesaplama
        total_pages = (total + self.per_page - 1) // self.per_page if self.per_page > 0 else 1
        
        # Sayfa sınır kontrolü
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
        
        # Offset hesaplama
        offset = (page - 1) * self.per_page
        
        # Veriyi çek
        items = query.limit(self.per_page).offset(offset).all()
        
        # Pagination objesi oluştur
        pagination_info = {
            'page': page,
            'per_page':  self.per_page,
            'total_pages': total_pages,
            'total_items': total
        }
        
        self.load_data(items, pagination_info)
        
        return self



    def load_data(self, query_result: List[Any], pagination_info: Optional[Dict[str, int]] = None):
        self.data = query_result
        self.pagination = pagination_info or {'page': 1, 'per_page': 10, 'total_pages': 1, 'total_items': len(query_result)}
        return self

    def _auto_generate_columns(self):
        """Modelden sütunları otomatik çeker."""
        for col in self.model.__table__.columns:
            col_name = col.key
            if col_name.startswith('_') or 'password' in col_name.lower(): continue

            self.columns.append({
                'name': col_name,
                'label': ' '.join(word.capitalize() for word in col_name.split('_')),
                'type': self._map_db_type_to_grid_type(col.type),
                'sortable': True,
                'visible': True,
                'css_class': '', 
                'badge_colors': {}, 
                'render_func': None
            })

    def _map_db_type_to_grid_type(self, db_type):
        db_type_str = str(db_type).upper()
        if any(x in db_type_str for x in ['VARCHAR', 'TEXT', 'STRING']): return FieldType.TEXT
        if any(x in db_type_str for x in ['INT', 'FLOAT', 'DECIMAL', 'NUMERIC']): return FieldType.NUMBER
        if 'BOOLEAN' in db_type_str: return FieldType.SWITCH
        if 'DATETIME' in db_type_str: return FieldType.DATETIME
        if 'DATE' in db_type_str: return FieldType.DATE
        return FieldType.TEXT

    def _get_type_str(self, raw_type: Any) -> str:
        """Enum veya String olan type bilgisini güvenli şekilde stringe çevirir."""
        if hasattr(raw_type, 'value'):
            return raw_type.value # Enum ise (FieldType.TEXT -> 'text')
        return str(raw_type)      # String ise ('badge' -> 'badge')

    # =================================================================
    # 3.RENDER METODLARI
    # =================================================================

    def _render_header(self, base_url_name: str) -> str:
        html = ['<thead><tr>']
        
        for col in self.columns:
            if not col['visible']: continue
            
            field_name = col['name']
            width_style = f' style="width: {col.get("width")}"' if col.get("width") else ''
            
            # Tip belirleme (Güvenli metod)
            type_str = self._get_type_str(col["type"])
            
            # --- CSS & OTOMATİK HİZALAMA ---
            header_class = col.get('css_class', '')
            # Sayısal ve Para alanlarını otomatik sağa yasla (kullanıcı aksini belirtmediyse)
            if type_str in ['currency', 'number'] and 'text-' not in header_class:
                header_class += ' text-end'
            
            class_attr = f' class="dx-grid-header {header_class}"'
            # -------------------------------

            # Sıralama Linki
            label = col["label"]
            if col.get('sortable', True) and hasattr(self.model, field_name):
                sort_icon = '<i class="fas fa-sort text-muted fa-sm ms-1"></i>'
                new_dir = 'asc'
                if self.current_sort_field == field_name:
                    if self.current_sort_direction == 'asc':
                        new_dir = 'desc'; sort_icon = '<i class="fas fa-sort-up fa-sm ms-1"></i>'
                    else:
                        sort_icon = '<i class="fas fa-sort-down fa-sm ms-1"></i>'
                
                args = request.args.to_dict()
                args.update({'sort': field_name, 'direction': new_dir, 'page': 1})
                label = f'<a href="{url_for(base_url_name, **args)}" class="text-decoration-none text-dark">{col["label"]} {sort_icon}</a>'
            
            html.append(f'<th scope="col"{class_attr} data-field="{field_name}"{width_style}>{label}</th>')
        
        if self.actions:
            html.append('<th scope="col" class="text-center dx-grid-actions" style="width: 120px;">İşlemler</th>')
        
        # Filtre Satırı
        html.append('</tr><tr class="dx-filter-row">')
        for col in self.columns:
            if not col['visible']: continue
            if not col.get('sortable', True):
                 html.append('<th></th>')
            else:
                val = (request.args.get(col['name'], ''))
                # --- YENİ: Eğer Tarih ise 'date' input kullan ---
                input_type = "text"
                if col['type'] == FieldType.DATE:
                    input_type = "date"
                
                html.append(f'<th class="p-1"><input type="{input_type}" class="form-control form-control-sm dx-column-filter" data-field="{col["name"]}" value="{val}" placeholder="..."></th>')
                # ------------------------------------------------
            
        if self.actions: html.append('<th></th>')
        html.append('</tr></thead>')
        return ''.join(html)

    def _render_row(self, item: Any, base_url_name: str) -> str:
        html = ['<tr>']
        for col in self.columns:
            if not col['visible']: continue

            # --- CUSTOM RENDER FUNC DESTEĞİ ---
            if col.get('render_func'):
                try:
                    val = col['render_func'](item)
                except Exception as e:
                    val = f"<span class='text-danger'>Error: {str(e)}</span>"
            else:
                raw_val = self._get_nested_value(item, col['name'])
                type_str = self._get_type_str(col["type"])

            # --- CSS & OTOMATİK HİZALAMA (Gövde) ---
            cell_class = col.get('css_class', '')
            if type_str in ['currency', 'number'] and 'text-' not in cell_class:
                cell_class += ' text-end'
            if type_str == 'currency':
                cell_class += ' font-monospace' # Para birimi için monospaced font
            
            class_attr = f' class="{cell_class.strip()}"' if cell_class.strip() else ''
            # ---------------------------------------

            # Değer Formatlama
            if type_str == 'badge':
                # Badge Enum veya String değeri
                val_str = str(raw_val.value) if hasattr(raw_val, 'value') else str(raw_val)
                colors = col.get('badge_colors', {})
                color = colors.get(val_str, 'secondary') 
                display_text = val_str.replace('_', ' ').title()
                val = f'<span class="badge bg-{color} bg-opacity-10 text-{color}">{display_text}</span>'
            else:
                val = self._format_value(raw_val, col['type'])
            
            html.append(f'<td{class_attr} data-field="{col["name"]}">{val}</td>')
            
        # Aksiyonlar
        if self.actions:
            html.append('<td class="text-center text-nowrap">')
            for action in self.actions:
                attrs = []
                if action.get('html_attributes'):
                    for k, v in action['html_attributes'].items():
                        attrs.append(f'{k}="{escape(str(v))}"')
                attrs_str = ' ' + ' '.join(attrs) if attrs else ''

                if action['action_type'] == 'route':
                    try:
                        endpoint = action['route_name']
                        if '.' not in endpoint and '.' in base_url_name:
                            prefix = base_url_name.split('.')[0]
                            endpoint = f"{prefix}.{endpoint}"
                        act_url = url_for(endpoint, id=item.id)
                    except: act_url = '#'
                    html.append(f'<a href="{act_url}" class="btn btn-sm {action["class"]} me-1" title="{action["label"]}"{attrs_str}><i class="{action["icon"]}"></i></a>')
                
                elif action['action_type'] == 'url':
                    try:
                        act_url = action['route_name'](item)
                    except: act_url = '#'
                    html.append(f'<a href="{act_url}" class="btn btn-sm {action["class"]} me-1" title="{action["label"]}"{attrs_str}><i class="{action["icon"]}"></i></a>')

                else: # AJAX Button
                    html.append(f'<button class="btn btn-sm {action["class"]} me-1" data-id="{item.id}" data-action="{action["name"]}"{attrs_str}><i class="{action["icon"]}"></i></button>')
            html.append('</td>')
        html.append('</tr>')
        return ''.join(html)

    def _get_nested_value(self, obj, field_path):
        """'cari.unvan' gibi noktalı alanları bulur."""
        try:
            for attr in field_path.split('.'):
                if obj is None: return ""
                obj = getattr(obj, attr)
            return obj
        except AttributeError: return ""

    def _format_value(self, value: Any, field_type: FieldType) -> str:
        if value is None: return ''
        if hasattr(value, 'value'): # Enum desteği
            return str(value.value).replace('_', ' ').title()
            
        if field_type == FieldType.CURRENCY:
            return f"{float(value):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

        elif field_type == FieldType.DATETIME and isinstance(value, (datetime, date)):
            return value.strftime('%d.%m.%Y %H:%M')

        # --- DÜZELTİLEN KISIM BURASI ---
        elif field_type == FieldType.DATE:
             # Hem 'datetime' hem 'date' objelerini yakalamak için genel 'date' kontrolü
             if isinstance(value, (datetime, date)):
                 # İstediğiniz format: 18-12-2025 (%d-%m-%Y)
                 return value.strftime('%d-%m-%Y')
        # -------------------------------



        elif field_type == FieldType.SWITCH:
            return '<span class="badge bg-success">Aktif</span>' if value else '<span class="badge bg-secondary">Pasif</span>'
        return str(value)

    def _render_pagination(self, base_url_name: str) -> str:
        info = self.pagination
        current, total = info['page'], info['total_pages']
        if total <= 1: return ''

        def get_url(p):
            args = request.args.to_dict(); args['page'] = p
            return url_for(base_url_name, **args)

        html = ['<nav><ul class="pagination pagination-sm justify-content-center mb-0">']
        disabled = 'disabled' if current <= 1 else ''
        html.append(f'<li class="page-item {disabled}"><a class="page-link" href="{get_url(current-1) if current > 1 else "#"}">&laquo;</a></li>')

        start = max(1, current - 2)
        end = min(total, current + 2)
        
        if start > 1:
             html.append(f'<li class="page-item"><a class="page-link" href="{get_url(1)}">1</a></li>')
             if start > 2: html.append('<li class="page-item disabled"><span class="page-link">...</span></li>')

        for p in range(start, end + 1):
            active = 'active' if p == current else ''
            html.append(f'<li class="page-item {active}"><a class="page-link" href="{get_url(p)}">{p}</a></li>')

        if end < total:
            if end < total - 1: html.append('<li class="page-item disabled"><span class="page-link">...</span></li>')
            html.append(f'<li class="page-item"><a class="page-link" href="{get_url(total)}">{total}</a></li>')

        disabled = 'disabled' if current >= total else ''
        html.append(f'<li class="page-item {disabled}"><a class="page-link" href="{get_url(current+1) if current < total else "#"}">&raquo;</a></li>')
        html.append('</ul></nav>')
        return ''.join(html)

    def render(self, base_url_name: str) -> str:
        """Grid'i Render Eder."""
        group_cls = " dx-grouping-enabled" if self.enable_grouping else ""
        html = [f'<div class="card dx-grid-card shadow-sm mb-4{group_cls}" id="dx-grid-card-{self.name}">']
        
        if self.title:
            html.append(f'<div class="card-header bg-light d-flex justify-content-between align-items-center"><h5 class="mb-0">{self.title}</h5>')
            # Export Butonları
            if self.export_action:
                export_url_page = url_for(f"{base_url_name}_export", scope='page')
                export_url_all = url_for(f"{base_url_name}_export", scope='all')
                html.append('<div>') 
                html.append(f'<a href="{export_url_page}" class="btn btn-sm {self.export_action["class_page"]} me-1" target="_blank"><i class="{self.export_action["icon_page"]}"></i> {self.export_action["label_page"]}</a>')
                html.append(f'<a href="{export_url_all}" class="btn btn-sm {self.export_action["class_all"]}" target="_blank"><i class="{self.export_action["icon_all"]}"></i> {self.export_action["label_all"]}</a>')
                html.append('</div>')
            html.append('</div>')
        
        if self.enable_grouping:
            html.append(f'<div class="card-body py-2 bg-light border-bottom"><div id="dx-group-area-{self.name}" class="dx-group-area border rounded p-2 text-center text-muted small">Sütun başlığını buraya sürükleyin</div></div>')
        
        html.append('<div class="card-body">')
        q_val = request.args.get("q", "")
        html.append(f'<div class="row mb-3"><div class="col-md-6"><input type="text" class="form-control form-control-sm dx-grid-filter" data-target="{self.name}" placeholder="Hızlı Ara (Enter)..." value="{q_val}"></div><div class="col-md-6 text-end">{self._render_pagination(base_url_name)}</div></div>')
        
        html.append(f'<div class="table-responsive"><table class="table table-hover table-striped table-sm dx-grid" id="dx-grid-{self.name}">')
        html.append(self._render_header(base_url_name))
        html.append('<tbody>')
        
        if self.data:
            for item in self.data: html.append(self._render_row(item, base_url_name))
        else:
            cols = len([c for c in self.columns if c['visible']]) + (1 if self.actions else 0)
            html.append(f'<tr><td colspan="{cols}" class="text-center py-4 text-muted">Kayıt bulunamadı.</td></tr>')
            
        html.append('</tbody></table></div>')
        html.append(f'<div class="small text-muted mt-2">Toplam {self.pagination["total_items"]} kayıt, Sayfa {self.pagination["page"]}/{self.pagination["total_pages"]}</div>')
        html.append('</div></div>')
        
        return ''.join(html)