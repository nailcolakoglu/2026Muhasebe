# data_grid.py

import logging
from typing import List, Dict, Any, Type, Optional, Union, Callable
from flask import url_for, request
from flask_sqlalchemy.model import Model as BaseModel
from sqlalchemy import or_, desc, asc, cast, String, select
from datetime import datetime, date, timedelta
from html import escape
from .field_types import FieldType

logger = logging.getLogger(__name__)

class DataGrid:
    """DataGrid Ultimate Version.

    Özellikler:
        - Modern UI (CSS Class ve Badge Desteği)
        - Akıllı Hizalama (Sayısal alanlar otomatik sağa yaslanır)
        - Tam Kolon Yönetimi (Gizleme, Sıralama, Yeniden Adlandırma)
        - Güvenli SQL Sorguları
        - Custom Render Function Desteği (render_func)
        - SQLAlchemy 2.0 uyumlu (paginate yerine manuel pagination)
        - Excel export desteği (pandas + openpyxl)
    """

    def __init__(
        self,
        name: str,
        model: Type[BaseModel],
        title: str = "Veri Listesi",
        per_page: int = 10,
        enable_grouping: bool = False,
        enable_summary: bool = False,
        summary_fields: Optional[List[str]] = None,
        target: Optional[Any] = None,
    ) -> None:
        """DataGrid örneği oluşturur.

        Args:
            name: Grid'in benzersiz adı (HTML id olarak kullanılır).
            model: SQLAlchemy model sınıfı.
            title: Başlık metni.
            per_page: Sayfa başına kayıt sayısı.
            enable_grouping: Sürükle-bırak gruplama etkin mi?
            enable_summary: Özet satırı etkin mi?
            summary_fields: Özet hesaplanacak alan adları listesi.
            target: Özel hedef parametresi.
        """
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

    def add_column(
        self,
        name: str,
        title: Optional[str] = None,
        width: Optional[str] = None,
        type: FieldType = FieldType.TEXT,
        sortable: bool = False,
        badge_colors: Optional[Dict[str, str]] = None,
        css_class: str = "",
        render_func: Optional[Callable[[Any], str]] = None,
    ) -> 'DataGrid':
        """Grid'e manuel sütun ekler veya mevcut olanı günceller.

        Args:
            name: Sütun adı (model alan adıyla eşleşmeli).
            title: Görünen başlık (opsiyonel; verilmezse name kullanılır).
            width: Genişlik değeri (örn: ``'150px'``).
            type: Sütun tipi (:class:`FieldType` enum).
            sortable: Sıralanabilir mi?
            badge_colors: Badge renkleri (örn: ``{'active': 'success'}``).
            css_class: Ek CSS sınıfları.
            render_func: Özel render fonksiyonu ``(row) -> str``.

        Returns:
            DataGrid: Zincir çağrı için ``self``.

        Example:
            >>> grid.add_column(
            ...     'status',
            ...     'Durum',
            ...     type=FieldType.BADGE,
            ...     badge_colors={'active': 'success', 'passive': 'danger'}
            ... )
        """
        logger.debug("add_column: %s.%s", self.name, name)
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

    def reorder_column(self, name: str, new_index: int) -> 'DataGrid':
        """Sütunu belirtilen indekse taşır.

        Args:
            name: Taşınacak sütunun adı.
            new_index: Hedef indeks.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
        current_index = next((i for i, c in enumerate(self.columns) if c['name'] == name), None)
        if current_index is not None:
            col = self.columns.pop(current_index)
            self.columns.insert(new_index, col)
        return self

    def set_column_order(self, ordered_names: List[str]) -> 'DataGrid':
        """Sütunları verilen isim listesine göre sıralar.

        Args:
            ordered_names: Sütun adlarının istenen sırası. Listede yer
                almayan sütunlar mevcut sıralarında sona eklenir.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
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

    def set_column_label(self, name: str, label: str) -> 'DataGrid':
        """Sütun başlığını değiştirir.

        Args:
            name: Sütun adı.
            label: Yeni başlık metni.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
        for col in self.columns:
            if col['name'] == name:
                col['label'] = label; break
        return self
    
    def hide_column(self, name: str) -> 'DataGrid':
        """Sütunu gizler.

        Args:
            name: Gizlenecek sütun adı.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
        for col in self.columns:
            if col['name'] == name:
                col['visible'] = False; break
        return self
        
    def add_action(
        self,
        name: str,
        label: str,
        icon: str,
        class_name: str,
        action_type: str = 'route',
        route_name: Optional[Union[str, Any]] = None,
        html_attributes: Optional[Dict[str, Any]] = None,
        target: Optional[Any] = None,
    ) -> 'DataGrid':
        """Aksiyon butonu ekler (Düzenle, Sil vb.).

        Args:
            name: Aksiyon adı (``'edit'``, ``'delete'`` vb.).
            label: Buton başlığı / tooltip metni.
            icon: Bootstrap/FontAwesome ikon sınıfı.
            class_name: Buton Bootstrap sınıfları.
            action_type: ``'route'``, ``'url'`` veya ``'ajax'``.
            route_name: Flask endpoint adı veya URL üretici callable.
            html_attributes: Ek HTML özellikleri (dict).
            target: Özel hedef parametresi.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
        logger.debug("add_action: %s -> %s", self.name, name)
        self.actions.append({
            'name': name, 'label': label, 'icon': icon, 'class': class_name,
            'action_type': action_type, 'route_name': route_name or name,
            'html_attributes': html_attributes or {}, 'target': target
        })
        return self

    def add_export_action(
        self,
        label_page: str = "Bu Sayfayı İndir",
        label_all: str = "Tümünü İndir",
        format: str = "csv",
        icon_page: str = "bi bi-file-earmark-excel",
        icon_all: str = "bi bi-download",
        class_page: str = "btn-outline-success",
        class_all: str = "btn-success",
    ) -> 'DataGrid':
        """Export butonlarını yapılandırır.

        Args:
            label_page: Sayfa export butonu etiketi.
            label_all: Tümünü export butonu etiketi.
            format: Export formatı (``'csv'`` veya ``'excel'``).
            icon_page: Sayfa export ikon sınıfı.
            icon_all: Tümünü export ikon sınıfı.
            class_page: Sayfa export buton CSS sınıfları.
            class_all: Tümünü export buton CSS sınıfları.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
        self.export_action = {
            "label_page": label_page, "label_all": label_all, "format": format,
            "icon_page": icon_page, "icon_all": icon_all,
            "class_page": class_page, "class_all": class_all
        }
        return self

    # =================================================================
    # 2.SORGULAMA MANTIĞI (Process Query)
    # =================================================================

    def process_query(self, query: Any, default_sort: Optional[tuple] = None) -> 'DataGrid':
        """Request argümanlarını okuyarak sorguyu filtreler, sıralar ve sayfalandırır.

        Otomatik olarak şube ve dönem filtresi uygular (session'da varsa).
        Sütun filtreleri, global arama (``?q=``), sıralama ve sayfalandırma
        işlemleri de bu metod tarafından yönetilir.

        Args:
            query: SQLAlchemy sorgu nesnesi.
            default_sort: Varsayılan sıralama ``(alan_adı, 'asc'|'desc')`` demeti.

        Returns:
            DataGrid: Zincir çağrı için ``self`` (veri yüklenmiş).

        Raises:
            Exception: Sorgu işleme sırasında beklenmedik hata oluşursa.
        """
        try:
            logger.debug("DataGrid query işleniyor: %s", self.name)

            # ✨ 1. KURUMSAL KAPSAM (DATA SCOPING) - OTOMATİK ŞUBE/DÖNEM FİLTRESİ ✨
            from flask import session

            # A) Şube Filtresi
            aktif_sube_id = session.get('aktif_sube_id')
            if aktif_sube_id and hasattr(self.model, 'sube_id'):
                column_attr = getattr(self.model, 'sube_id')
                query = query.filter(column_attr == aktif_sube_id)

            # B) Dönem Filtresi
            aktif_donem_id = session.get('aktif_donem_id')
            if aktif_donem_id and hasattr(self.model, 'donem_id'):
                column_attr = getattr(self.model, 'donem_id')
                query = query.filter(column_attr == aktif_donem_id)

            # A.KOLON FİLTRELEME
            for col in self.columns:
                field_name = col['name']

                if not hasattr(self.model, field_name):
                    continue

                column_attr = getattr(self.model, field_name)

                # SQL Sütunu değilse (@property vb.) filtrelemeyi atla
                if not hasattr(column_attr, 'ilike'):
                    continue

                # --- Tarih Aralığı ve Tam Eşleşme Filtreleme ---
                if col['type'] in [FieldType.DATE, FieldType.DATETIME]:
                    start_val = request.args.get(f"{field_name}_start")
                    end_val = request.args.get(f"{field_name}_end")
                    exact_val = request.args.get(field_name)

                    def _parse_date_flexible(date_str: str) -> Optional[datetime]:
                        """Birden fazla format denerek tarih ayrıştırır."""
                        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y', '%Y-%m-%dT%H:%M:%S'):
                            try:
                                return datetime.strptime(date_str, fmt)
                            except ValueError:
                                continue
                        logger.debug("Tarih ayrıştırılamadı: %s", date_str)
                        return None

                    if start_val:
                        dt = _parse_date_flexible(start_val)
                        if dt:
                            if col['type'] == FieldType.DATE:
                                dt = dt.date()
                            query = query.filter(column_attr >= dt)

                    if end_val:
                        dt = _parse_date_flexible(end_val)
                        if dt:
                            if col['type'] == FieldType.DATE:
                                dt = dt.date()
                                # End date'i bir gün sonraya al (son gün dahil olsun)
                                query = query.filter(column_attr < dt + timedelta(days=1))
                            else:
                                query = query.filter(column_attr < dt + timedelta(days=1))

                    if exact_val:
                        dt = _parse_date_flexible(exact_val)
                        if dt:
                            if col['type'] == FieldType.DATE:
                                query = query.filter(column_attr == dt.date())
                            else:
                                next_day = dt + timedelta(days=1)
                                query = query.filter(column_attr >= dt, column_attr < next_day)

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
                    if not col['visible'] or not hasattr(self.model, col['name']):
                        continue
                    column_attr = getattr(self.model, col['name'])
                    if not hasattr(column_attr, 'ilike'):
                        continue
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
                except Exception:
                    pass

            # D.SAYFALAMA (✅ SQLAlchemy 2.0 Uyumlu)
            try:
                page = int(request.args.get('page', 1))
            except (ValueError, TypeError):
                page = 1

            total = query.count()
            total_pages = (total + self.per_page - 1) // self.per_page if self.per_page > 0 else 1

            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages

            offset = (page - 1) * self.per_page
            items = query.limit(self.per_page).offset(offset).all()

            pagination_info = {
                'page': page,
                'per_page': self.per_page,
                'total_pages': total_pages,
                'total_items': total,
            }

            self.load_data(items, pagination_info)
            logger.info("DataGrid loaded: %s - %d items (page %d/%d)", self.name, len(items), page, total_pages)
            return self

        except Exception as e:
            logger.error("process_query hatası (%s): %s", self.name, e, exc_info=True)
            raise


    def load_data(
        self,
        query_result: List[Any],
        pagination_info: Optional[Dict[str, int]] = None,
    ) -> 'DataGrid':
        """Veriyi ve sayfalandırma bilgisini yükler.

        Args:
            query_result: Model nesneleri listesi.
            pagination_info: Sayfalandırma bilgisi dict'i.

        Returns:
            DataGrid: Zincir çağrı için ``self``.
        """
        self.data = query_result
        self.pagination = pagination_info or {
            'page': 1, 'per_page': 10, 'total_pages': 1, 'total_items': len(query_result)
        }
        logger.debug("load_data: %s - %d items", self.name, len(self.data))
        return self

    def _auto_generate_columns(self) -> None:
        """Modelden sütunları otomatik olarak çeker ve columns listesini doldurur."""
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

    def _map_db_type_to_grid_type(self, db_type: Any) -> FieldType:
        """Veritabanı sütun tipini FieldType enum değerine dönüştürür.

        Args:
            db_type: SQLAlchemy kolon tip nesnesi.

        Returns:
            FieldType: Eşleşen grid sütun tipi.
        """
        db_type_str = str(db_type).upper()
        if any(x in db_type_str for x in ['VARCHAR', 'TEXT', 'STRING']): return FieldType.TEXT
        if any(x in db_type_str for x in ['INT', 'FLOAT', 'DECIMAL', 'NUMERIC']): return FieldType.NUMBER
        if 'BOOLEAN' in db_type_str: return FieldType.SWITCH
        if 'DATETIME' in db_type_str: return FieldType.DATETIME
        if 'DATE' in db_type_str: return FieldType.DATE
        return FieldType.TEXT

    def _get_type_str(self, raw_type: Any) -> str:
        """Enum veya string olan tip bilgisini güvenli biçimde string'e çevirir.

        Args:
            raw_type: FieldType enum değeri veya ham string.

        Returns:
            str: Tip adı string olarak (örn: ``'text'``, ``'currency'``).
        """
        if hasattr(raw_type, 'value'):
            return raw_type.value # Enum ise (FieldType.TEXT -> 'text')
        return str(raw_type)      # String ise ('badge' -> 'badge')

    # =================================================================
    # 3.RENDER METODLARI
    # =================================================================

    def _render_header(self, base_url_name: str) -> str:
        """Tablo başlığı HTML'ini oluşturur (başlıklar + filtre satırı).

        Args:
            base_url_name: Sıralama linkleri için Flask endpoint adı.

        Returns:
            str: ``<thead>`` HTML bloğu.
        """
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
        """Tek bir veri satırı HTML'ini oluşturur.

        Args:
            item: Model nesnesi (tablo satırı).
            base_url_name: Aksiyon URL'leri için Flask endpoint adı.

        Returns:
            str: ``<tr>`` HTML bloğu.
        """
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
                cell_class += ' font-monospace'
            
            class_attr = f' class="{cell_class.strip()}"' if cell_class.strip() else ''

            # Değer Formatlama
            if type_str == 'badge':
                val_str = str(raw_val.value) if hasattr(raw_val, 'value') else str(raw_val)
                colors = col.get('badge_colors', {})
                color = colors.get(val_str, 'secondary') 
                display_text = val_str.replace('_', ' ').title()
                val = f'<span class="badge bg-{color} bg-opacity-10 text-{color}">{display_text}</span>'
            else:
                val = self._format_value(raw_val, col['type'])
            
            html.append(f'<td{class_attr} data-field="{col["name"]}">{val}</td>')
            
        # ========================================
        # ✅ DÜZELTİLMİŞ: Aksiyonlar (UUID Desteği)
        # ========================================
        if self.actions:
            html.append('<td class="text-center text-nowrap">')
            
            # ✅ item.id'yi string'e çevir (UUID ise string olacak)
            item_id = str(item.id) if hasattr(item, 'id') else None
            
            for action in self.actions:
                attrs = []
                if action.get('html_attributes'):
                    for k, v in action['html_attributes'].items():
                        attrs.append(f'{k}="{escape(str(v))}"')
                attrs_str = ' ' + ' '.join(attrs) if attrs else ''

                if action['action_type'] == 'route':
                    try:
                        endpoint = action['route_name']
                        
                        # Blueprint prefix ekle (gerekiyorsa)
                        if '.' not in endpoint and '.' in base_url_name:
                            prefix = base_url_name.split('.')[0]
                            endpoint = f"{prefix}.{endpoint}"
                        
                        # ✅ UUID'yi string olarak gönder
                        if item_id:
                            act_url = url_for(endpoint, id=item_id)
                        else:
                            act_url = '#'
                            
                    except Exception as e:
                        logger.warning("DataGrid URL oluşturma hatası: %s, endpoint: %s, id: %s", e, endpoint, item_id)
                        act_url = '#'
                        
                    html.append(f'<a href="{act_url}" class="btn btn-sm {action["class"]} me-1" title="{action["label"]}"{attrs_str}><i class="{action["icon"]}"></i></a>')
                
                elif action['action_type'] == 'url':
                    try:
                        act_url = action['route_name'](item)
                    except Exception:
                        act_url = '#'
                    html.append(f'<a href="{act_url}" class="btn btn-sm {action["class"]} me-1" title="{action["label"]}"{attrs_str}><i class="{action["icon"]}"></i></a>')

                else:  # AJAX Button
                    # ✅ AJAX için de string ID 
                    try:
                        endpoint = action['route_name']
                        if '.' not in endpoint and '.' in base_url_name:
                            prefix = base_url_name.split('.')[0]
                            endpoint = f"{prefix}.{endpoint}"
                        act_url = url_for(endpoint, id=item_id) if item_id else '#'
                    except Exception as e:
                        logger.warning("Custom AJAX URL hatası: %s", e)
                        act_url = '#'
                        
                    # 👇 YENİ: datagrid-ajax-btn class'ı ve data-url özelliği eklendi!
                    html.append(f'<button class="btn btn-sm {action["class"]} me-1 datagrid-ajax-btn" data-url="{act_url}" data-id="{item_id}" data-action="{action["name"]}"{attrs_str} title="{action["label"]}"><i class="{action["icon"]}"></i></button>')                    

            html.append('</td>')
        html.append('</tr>')
        return ''.join(html)
        
    def _get_nested_value(self, obj: Any, field_path: str) -> Any:
        """Noktalı alan yolunu takip ederek değer döndürür.

        Args:
            obj: Başlangıç nesnesi.
            field_path: Alan yolu (örn: ``'cari.unvan'``).

        Returns:
            Any: Bulunan değer; hata durumunda boş string.
        """
        try:
            for attr in field_path.split('.'):
                if obj is None: return ""
                obj = getattr(obj, attr)
            return obj
        except AttributeError: return ""

    def _format_value(self, value: Any, field_type: FieldType) -> str:
        """Değeri sütun tipine göre görüntülenebilir HTML string'e dönüştürür.

        Args:
            value: Ham değer.
            field_type: Sütun tipi.

        Returns:
            str: Formatlanmış HTML string.
        """
        if value is None:
            return ''
        if hasattr(value, 'value'):  # Enum desteği
            return str(value.value).replace('_', ' ').title()

        if field_type == FieldType.CURRENCY:
            return f"{float(value):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

        elif field_type == FieldType.DATETIME and isinstance(value, (datetime, date)):
            return value.strftime('%d.%m.%Y %H:%M')

        elif field_type == FieldType.DATE:
            if isinstance(value, (datetime, date)):
                return value.strftime('%d-%m-%Y')

        elif field_type == FieldType.SWITCH:
            return '<span class="badge bg-success">Aktif</span>' if value else '<span class="badge bg-secondary">Pasif</span>'
        return str(value)

    def _render_pagination(self, base_url_name: str) -> str:
        """Sayfalandırma kontrol HTML'ini oluşturur.

        Args:
            base_url_name: Sayfa linkleri için Flask endpoint adı.

        Returns:
            str: Bootstrap pagination HTML bloğu; tek sayfalıysa boş string.
        """
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
        """Grid'i HTML olarak render eder.

        Args:
            base_url_name: Sıralama, filtreleme ve sayfalandırma linkleri için
                Flask endpoint adı.

        Returns:
            str: Tam grid HTML bloğu. Hata durumunda hata mesajı içeren
                basit bir ``div`` döner.
        """
        try:
            logger.debug("render başlıyor: %s -> %s", self.name, base_url_name)
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
                for item in self.data:
                    html.append(self._render_row(item, base_url_name))
            else:
                cols = len([c for c in self.columns if c['visible']]) + (1 if self.actions else 0)
                html.append(f'<tr><td colspan="{cols}" class="text-center py-4 text-muted">Kayıt bulunamadı.</td></tr>')

            html.append('</tbody></table></div>')
            html.append(f'<div class="small text-muted mt-2">Toplam {self.pagination["total_items"]} kayıt, Sayfa {self.pagination["page"]}/{self.pagination["total_pages"]}</div>')
            html.append('</div></div>')

            result = ''.join(html)
            logger.debug("render tamamlandı: %s", self.name)
            return result

        except Exception as e:
            logger.error("render hatası (%s): %s", self.name, e, exc_info=True)
            return '<div class="alert alert-danger">Grid render hatası</div>'

    # =================================================================
    # 4. EXPORT METODLARI
    # =================================================================

    def export_to_excel(self, filename: str = 'export.xlsx') -> bytes:
        """Grid verisini Excel formatında dışa aktarır.

        Mevcut ``self.data`` koleksiyonunu kullanır; bu nedenle bu metodu
        çağırmadan önce ``process_query`` veya ``load_data`` ile veri
        yüklenmiş olmalıdır.

        Args:
            filename: Dosya adı (yalnızca loglama amaçlıdır; dönen bytes
                üzerinde etkisi yoktur).

        Returns:
            bytes: ``.xlsx`` formatında Excel dosyasının binary içeriği.

        Raises:
            Exception: Export sırasında beklenmedik hata oluşursa.

        Example:
            >>> from io import BytesIO
            >>> from flask import send_file
            >>> data = grid.export_to_excel('faturalar.xlsx')
            >>> return send_file(BytesIO(data), download_name='faturalar.xlsx',
            ...                  mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        """
        import pandas as pd
        from io import BytesIO

        try:
            logger.debug("Excel export başlıyor: %s (%s)", self.name, filename)

            records = []
            for item in self.data:
                row: Dict[str, Any] = {}
                for col in self.columns:
                    if not col.get('visible', True):
                        continue
                    val = self._get_nested_value(item, col['name'])
                    row[col['label']] = self._format_excel_value(val, col['type'])
                records.append(row)

            df = pd.DataFrame(records)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Data')

                # Sütun genişliklerini otomatik ayarla
                from openpyxl.utils import get_column_letter
                worksheet = writer.sheets['Data']
                for col_idx, col_name in enumerate(df.columns):
                    col_letter = get_column_letter(col_idx + 1)
                    max_len = max(
                        df[col_name].astype(str).map(len).max() if not df.empty else 0,
                        len(str(col_name)),
                    ) + 2
                    worksheet.column_dimensions[col_letter].width = min(max_len, 50)

            output.seek(0)
            result = output.read()
            logger.info("Excel export tamamlandı: %s - %d satır", filename, len(records))
            return result

        except Exception as e:
            logger.error("Excel export hatası (%s): %s", self.name, e, exc_info=True)
            raise

    def _format_excel_value(self, value: Any, field_type: FieldType) -> Any:
        """Excel hücresi için değeri düz (HTML içermeyen) biçime dönüştürür.

        Args:
            value: Ham değer.
            field_type: Sütun tipi.

        Returns:
            Any: Excel'e uygun native Python değeri.
        """
        if value is None:
            return ''
        if hasattr(value, 'value'):  # Enum
            return str(value.value).replace('_', ' ').title()
        if field_type == FieldType.CURRENCY:
            try:
                return float(value)
            except (ValueError, TypeError):
                return str(value)
        if field_type == FieldType.SWITCH:
            return 'Aktif' if value else 'Pasif'
        if isinstance(value, (datetime, date)):
            return value
        return str(value)