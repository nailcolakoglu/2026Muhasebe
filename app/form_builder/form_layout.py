# form_builder/form_layout.py

from html import escape

class FormLayout:
    """
    Form düzenini yöneten sınıf.
    Hem manuel kodlama (Eski Yöntem) hem de Visual Designer (Yeni Yöntem) ile uyumludur.
    Bootstrap 5 Grid Sistemi, Kartlar, Akordeon ve Sekmeler destekler.
    
    Grid, Card, Tab, Accordion, Offcanvas, Fieldset, Alert ve Floating Window destekler.
    """
    
    def __init__(self):
        self.fields = []      # Eski yöntem için field listesi
        self.html_parts = []  # Yeni yöntem (String builder) için
        self.rows = []

    # ==========================================
    # 1.ESKİ METODLAR (Geri Uyumluluk İçin)
    # ==========================================

    def add_field(self, field):
        """Form field'ı ekle"""
        self.fields.append(field)
        return self
    
    def add_fields(self, *fields):
        """Birden fazla field ekle"""
        for field in fields:
            self.add_field(field)
        return self

    def create_custom_row(self, field_configs, row_class="row"):
        """
        Özel column genişlikleri ile row oluştur.
        Args: field_configs: [(field, "col-md-6"), (field, "col-md-4")]
        """
        html = [f'<div class="{row_class}">']
        for field, column_class in field_configs:
            field.set_column_class(column_class)
            html.append(field.render())
        html.append('</div>')
        return '\n'.join(html)

    def render_all(self):
        """Tüm field'ları sırayla render et (Eski yöntem)"""
        return '\n'.join(field.render() for field in self.fields)

    # ==========================================
    # 2.GÜNCEL METODLAR (Hem Eski Hem Yeni)
    # ==========================================

    def add_html(self, html_content):
        """Doğrudan HTML ekler (Recursive yapı için)"""
        self.html_parts.append(html_content)
        return self

    def create_row(self, *fields, row_class="row g-3"):
        """
        Bir satır oluşturur ve elemanları esnek (flex) sütunlara böler.
        """
        if not fields: return ""
        
        html = [f'<div class="{row_class}">']
        
        for field in fields:
            # HTML String gelirse (Nested yapı)
            if isinstance(field, str):
                if "col-" not in field:
                    # 'col' sınıfı, kalan alanı otomatik doldurmasını sağlar
                    html.append(f'<div class="col-12 col-md">{field}</div>')
                else:
                    html.append(field)
            
            # FormField Nesnesi gelirse
            elif hasattr(field, 'render'):
                # Eğer özel bir genişlik verilmemişse otomatik genişle (col-md)
                if not field.column_class:
                    field.set_column_class("col-12 col-md")
                html.append(field.render())
                
        html.append('</div>')
        return '\n'.join(html)

    def create_card(self, title, content, card_class="shadow-sm mb-4"):
        """Bir kart (panel) oluşturur."""
        # DÜZELTME: escape(title) yerine title kullanıldı (İkonlar için)
        header = f'<div class="card-header fw-bold">{title}</div>' if title else ''
        
        # İçerik bir liste mi (fields) yoksa string mi (html)?
        body_content = ""
        if isinstance(content, (list, tuple)):
            body_content = '\n'.join([
                f.render() if hasattr(f, 'render') else str(f) for f in content
            ])
        else:
            body_content = str(content)

        return f'''
        <div class="card {card_class}">
            {header}
            <div class="card-body">
                {body_content}
            </div>
        </div>
        '''

    # Eski create_card_group metodunu create_card'a yönlendiriyoruz (Alias)
    def create_card_group(self, title, fields, card_class=""):
        return self.create_card(title, fields, card_class)

    def create_tabs(self, tab_id, groups, tab_class="mb-4"):
        nav_html = [f'<ul class="nav nav-tabs" id="{tab_id}" role="tablist">']
        for i, (title, _) in enumerate(groups):
            active = "active" if i == 0 else ""
            selected = "true" if i == 0 else "false"
            
            # --- DÜZELTME: escape() KALDIRILDI ---
            nav_html.append(f'''
                <li class="nav-item" role="presentation">
                    <button class="nav-link {active}" id="{tab_id}-tab-{i}" data-bs-toggle="tab"
                        data-bs-target="#{tab_id}-pane-{i}" type="button" role="tab" aria-selected="{selected}">
                        {title} 
                    </button>
                </li>
            ''')
            # -------------------------------------
            
        nav_html.append('</ul>')
        
        content_html = [f'<div class="tab-content border border-top-0 p-3 bg-white rounded-bottom" id="{tab_id}Content">']
        for i, (_, content) in enumerate(groups):
            active = "show active" if i == 0 else ""
            inner_html = ""
            if isinstance(content, (list, tuple)):
                inner_html = '\n'.join([f.render() if hasattr(f, 'render') else str(f) for f in content])
            else:
                inner_html = str(content)
            content_html.append(f'<div class="tab-pane fade {active}" id="{tab_id}-pane-{i}" role="tabpanel">{inner_html}</div>')
        content_html.append('</div>')
        return f'<div class="{tab_class}">' + '\n'.join(nav_html) + '\n'.join(content_html) + '</div>'
    def create_accordion(self, accordion_id, groups):
        """Akordeon yapı oluşturur."""
        html = [f'<div class="accordion mb-4" id="{accordion_id}">']
        
        for i, (title, content) in enumerate(groups):
            item_id = f"{accordion_id}-item-{i}"
            expanded = "true" if i == 0 else "false"
            collapsed = "" if i == 0 else "collapsed"
            show = "show" if i == 0 else ""
            
            # İçeriği render et
            inner_html = ""
            if isinstance(content, (list, tuple)):
                inner_html = '\n'.join([f.render() if hasattr(f, 'render') else str(f) for f in content])
            else:
                inner_html = str(content)

            # DÜZELTME: escape(title) yerine title kullanıldı
            html.append(f'''
            <div class="accordion-item">
                <h2 class="accordion-header" id="heading-{item_id}">
                    <button class="accordion-button {collapsed}" type="button" data-bs-toggle="collapse"
                        data-bs-target="#collapse-{item_id}" aria-expanded="{expanded}">
                        {title}
                    </button>
                </h2>
                <div id="collapse-{item_id}" class="accordion-collapse collapse {show}"
                    data-bs-parent="#{accordion_id}">
                    <div class="accordion-body">
                        {inner_html}
                    </div>
                </div>
            </div>
            ''')
            
        html.append('</div>')
        return '\n'.join(html) 
            
    def create_offcanvas(self, offcanvas_id, title, content, position='end', btn_text='Paneli Aç', btn_class='btn btn-primary', btn_icon='bi bi-list'):
        """Offcanvas (Yan Panel) Oluşturur."""
        # 1.İçeriği Render Et
        body_content = ""
        if isinstance(content, (list, tuple)):
            body_content = '\n'.join([
                f.render() if hasattr(f, 'render') else str(f) for f in content
            ])
        else:
            body_content = str(content)

        # 2.Tetikleyici Buton
        # DÜZELTME: escape(btn_text) kaldırıldı, HTML ikonlarına izin ver
        trigger_html = f'''
        <button class="{btn_class}" type="button" data-bs-toggle="offcanvas" data-bs-target="#{offcanvas_id}" aria-controls="{offcanvas_id}">
            <i class="{btn_icon} me-1"></i> {btn_text}
        </button>
        '''

        # 3.Offcanvas HTML Yapısı
        # DÜZELTME: title escape kaldırıldı
        offcanvas_html = f'''
        <div class="offcanvas offcanvas-{position}" tabindex="-1" id="{offcanvas_id}" aria-labelledby="{offcanvas_id}Label">
          <div class="offcanvas-header">
            <h5 class="offcanvas-title" id="{offcanvas_id}Label">{title}</h5>
            <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Kapat"></button>
          </div>
          <div class="offcanvas-body">
            {body_content}
          </div>
        </div>
        '''

        return trigger_html + offcanvas_html 
 
    def create_fieldset(self, legend, content, border_color="border-secondary"):
        """Fieldset (Çerçeveli Grup) Oluşturur."""
        # İçeriği Render Et
        body_content = ""
        if isinstance(content, (list, tuple)):
            body_content = '\n'.join([
                f.render() if hasattr(f, 'render') else str(f) for f in content
            ])
        else:
            body_content = str(content)

        # DÜZELTME: escape(legend) kaldırıldı
        return f'''
        <fieldset class="border p-3 rounded mb-4 {border_color} position-relative">
            <legend class="float-none w-auto px-3 fs-6 fw-bold text-primary" 
                    style="font-size: 0.9rem; margin-bottom: 0;">
                {legend}
            </legend>
            <div class="fieldset-body mt-2">
                {body_content}
            </div>
        </fieldset>
        '''

    def create_alert(self, title, message, type="info", icon="bi-info-circle"):
        """Form arasına sabit bilgi/uyarı kutusu ekler."""
        # DÜZELTME: escape(title) ve escape(message) kaldırıldı
        return f'''
        <div class="alert alert-{type} d-flex align-items-center mb-4" role="alert">
            <i class="bi {icon} flex-shrink-0 me-2 fs-4"></i>
            <div>
                {f"<strong>{title}:</strong> " if title else ""}
                {message}
            </div>
        </div>
        '''

    def add_alert(self, title, message, type="info", icon="bi-info-circle"):
        """
        Uyarı kutusu oluşturur ve doğrudan layout akışına (rows listesine) ekler.
        Kullanım: layout.add_alert("Dikkat", "Bu işlem geri alınamaz", "danger")
        """
        # Mevcut create_alert fonksiyonunu kullanarak HTML'i al
        html = self.create_alert(title, message, type, icon)
        
        # Layout satırlarına ekle
        self.rows.append(html)
        return self

    def add_row(self, *fields, responsive=True):
        """
        Girilen field'ları otomatik 'col-12 col-md-X' ile row içine yerleştirir.
        """
        num = len(fields)
        col_class = f"col-12 col-md-{int(12/num)}"
        row_html = '<div class="row g-3">'
        for field in fields:
            row_html += f'<div class="{col_class}">{field.render()}</div>'
        row_html += '</div>'
        self.rows.append(row_html)

    # ==========================================
    # 3.DÜZELTİLMİŞ RENDER METODU
    # ==========================================
    def render(self):
        """
        Tüm içeriği (HTML parçaları + Satırlar) birleştirip döndürür.
        """
        all_content = []
        
        # 1.Önce add_html ile eklenen modern layout parçaları
        if self.html_parts:
            all_content.extend(self.html_parts)
        
        # 2.Sonra add_row/add_fieldset ile eklenen eski tip parçalar
        if self.rows:
            all_content.extend(self.rows)
        
        # 3.Eğer hiçbiri yoksa ama add_field yapıldıysa (sadece field listesi varsa)
        if not all_content and self.fields:
             all_content = [f.render() for f in self.fields]

        return "\n".join(all_content)

    def add_fieldset(self, title, fields: list, help_text: str = None, style_class="mb-4"):
        html = f'<fieldset class="{style_class}">'
        html += f'<legend class="fw-bold mb-1">{title}</legend>'
        
        if help_text:
            from html import escape
            html += f'<small class="d-block mb-2 text-muted">{escape(help_text)}</small>'
            
        # --- DÜZELTME BAŞLANGIÇ ---
        # Gelen veri bir HTML String mi (create_row sonucu) yoksa Nesne mi?
        for field in fields:
            if hasattr(field, 'render'):
                html += field.render() # Nesne ise render et
            else:
                html += str(field)     # String (HTML) ise olduğu gibi ekle
        # --- DÜZELTME BİTİŞ ---
        
        html += '</fieldset>'
        self.rows.append(html) 
        
    def add_card(self, title, content, card_class="shadow-sm mb-4"):
        """Kart oluşturur ve doğrudan layout akışına ekler."""
        html = self.create_card(title, content, card_class)
        self.rows.append(html)
        return self    
        
    def add_card_section(self, title, fields: list, subtitle: str = None, card_class="card shadow-sm mb-3"):
        html = f'<div class="{card_class}">'
        html += f'<div class="card-header fw-bold">{title}</div>' # DÜZELTME: escape kaldırıldı
        if subtitle:
            html += f'<div class="card-subtitle text-muted mb-1">{(subtitle)}</div>'
        html += '<div class="card-body">'
        for field in fields:
            html += field.render()
        html += '</div></div>'
        self.rows.append(html)

    def create_floating_window(self, window_id, title, content, width="400px", height="300px", btn_text="Pencere Aç", btn_class="btn btn-info"):
        """Yüzen Pencere Oluşturur."""
        # İçerik Render
        body_html = ""
        if isinstance(content, (list, tuple)):
            body_html = '\n'.join([f.render() if hasattr(f, 'render') else str(f) for f in content])
        else:
            body_html = str(content)

        # 1.Açma Butonu
        # DÜZELTME: escape(btn_text) kaldırıldı
        trigger_html = f'''
        <button type="button" class="{btn_class}" onclick="toggleWindow('{window_id}')">
            <i class="bi bi-window-stack me-1"></i> {btn_text}
        </button>
        '''

        # 2.Pencere HTML Yapısı
        # DÜZELTME: escape(title) kaldırıldı
        window_html = f'''
        <div id="{window_id}" class="floating-window shadow-lg rounded" 
             style="width: {width}; height: {height}; display: none;">
            
            <div class="window-header bg-primary text-white d-flex justify-content-between align-items-center p-2"
                 onmousedown="dragMouseDown(event, '{window_id}')">
                <span class="fw-bold small"><i class="bi bi-grip-vertical me-1"></i>{title}</span>
                <button type="button" class="btn-close btn-close-white small" onclick="toggleWindow('{window_id}')" style="font-size: 0.7rem;"></button>
            </div>
            
            <div class="window-body p-3 bg-white h-100">
                {body_html}
            </div>
        </div>
        '''
        
        return trigger_html + window_html

    def create_stepper(self, stepper_id, steps, current_step=1):
        """Stepper (Adım Göstergesi)"""
        html = [f'<div class="stepper mb-4" id="{stepper_id}">']
        html.append('<div class="d-flex justify-content-between align-items-center position-relative">')
        
        # Progress line
        html.append('<div class="stepper-line"></div>')
        
        for i, step_text in enumerate(steps, 1):
            active_class = 'active' if i == current_step else ''
            completed_class = 'completed' if i < current_step else ''
            
            html.append(f'''
            <div class="stepper-step {active_class} {completed_class}">
                <div class="stepper-circle">
                    {f'<i class="fas fa-check"></i>' if i < current_step else i}
                </div>
                <div class="stepper-label">{(step_text)}</div>
            </div>
            ''')
        
        html.append('</div></div>')
        return '\n'.join(html)

    def create_timeline(self, timeline_id, events):
        """Timeline (Zaman Çizelgesi)"""
        html = [f'<div class="timeline mb-4" id="{timeline_id}">']
        
        for event in events:
            date = (event.get('date', ''))
            title = (event.get('title', ''))
            description = (event.get('description', ''))
            icon = event.get('icon', 'bi-circle')
            
            html.append(f'''
            <div class="timeline-item">
                <div class="timeline-marker">
                    <i class="bi {icon}"></i>
                </div>
                <div class="timeline-content">
                    <div class="timeline-date text-muted small">{date}</div>
                    <h6 class="timeline-title">{title}</h6>
                    <p class="timeline-description">{description}</p>
                </div>
            </div>
            ''')
        
        html.append('</div>')
        return '\n'.join(html)

    def create_grid(self, items, columns=3, gap='g-3'):
        """Grid Layout"""
        col_class = f"col-12 col-md-{12 // columns}"
        html = [f'<div class="row {gap}">']
        
        for item in items:
            if isinstance(item, str):
                content = item
            elif hasattr(item, 'render'):
                content = item.render()
            else:
                content = str(item)
            html.append(f'<div class="{col_class}">{content}</div>')
        
        html.append('</div>')
        return '\n'.join(html)

    def create_split_panel(self, left_content, right_content, left_width=6, right_width=6):
        """Split Panel"""
        left_html = ""
        if isinstance(left_content, (list, tuple)):
            left_html = '\n'.join([f.render() if hasattr(f, 'render') else str(f) for f in left_content])
        else:
            left_html = str(left_content)
        
        right_html = ""
        if isinstance(right_content, (list, tuple)):
            right_html = '\n'.join([f.render() if hasattr(f, 'render') else str(f) for f in right_content])
        else:
            right_html = str(right_content)
        
        return f'''
        <div class="row g-3 split-panel mb-4">
            <div class="col-md-{left_width}">
                <div class="split-panel-left border-end pe-3">
                    {left_html}
                </div>
            </div>
            <div class="col-md-{right_width}">
                <div class="split-panel-right ps-3">
                    {right_html}
                </div>
            </div>
        </div>
        '''

    def create_carousel(self, carousel_id, slides, controls=True, indicators=True):
        """Carousel (Slider)"""
        html = [f'<div id="{carousel_id}" class="carousel slide mb-4" data-bs-ride="carousel">']
        
        if indicators:
            html.append('<div class="carousel-indicators">')
            for i in range(len(slides)):
                active = 'active' if i == 0 else ''
                html.append(f'<button type="button" data-bs-target="#{carousel_id}" data-bs-slide-to="{i}" class="{active}"></button>')
            html.append('</div>')
        
        html.append('<div class="carousel-inner">')
        for i, slide in enumerate(slides):
            active = 'active' if i == 0 else ''
            image = slide.get('image', '')
            caption = (slide.get('caption', ''))
            description = (slide.get('description', ''))
            
            html.append(f'''
            <div class="carousel-item {active}">
                <img src="{image}" class="d-block w-100" alt="{caption}">
                <div class="carousel-caption d-none d-md-block">
                    <h5>{caption}</h5>
                    <p>{description}</p>
                </div>
            </div>
            ''')
        html.append('</div>')
        
        if controls:
            html.append(f'''
            <button class="carousel-control-prev" type="button" data-bs-target="#{carousel_id}" data-bs-slide="prev">
                <span class="carousel-control-prev-icon"></span>
            </button>
            <button class="carousel-control-next" type="button" data-bs-target="#{carousel_id}" data-bs-slide="next">
                <span class="carousel-control-next-icon"></span>
            </button>
            ''')
        
        html.append('</div>')
        return '\n'.join(html)

    def create_modal(self, modal_id, title, content, btn_text="Aç", btn_class="btn btn-primary", size=""):
        """Modal (Popup Pencere)"""
        body_html = ""
        if isinstance(content, (list, tuple)):
            body_html = '\n'.join([f.render() if hasattr(f, 'render') else str(f) for f in content])
        else:
            body_html = str(content)
        
        # DÜZELTME: escape(btn_text) kaldırıldı
        trigger = f'''
        <button type="button" class="{btn_class}" data-bs-toggle="modal" data-bs-target="#{modal_id}">
            {btn_text}
        </button>
        '''
        
        # DÜZELTME: escape(title) kaldırıldı
        modal = f'''
        <div class="modal fade" id="{modal_id}" tabindex="-1">
            <div class="modal-dialog {size}">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">{title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        {body_html}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Kapat</button>
                    </div>
                </div>
            </div>
        </div>
        '''
        return trigger + modal

    def create_list_group(self, items, clickable=False):
        """List Group"""
        html = ['<div class="list-group mb-4">']
        
        for item in items:
            if isinstance(item, str):
                action_class = 'list-group-item-action' if clickable else ''
                # DÜZELTME: escape kaldırıldı
                html.append(f'<div class="list-group-item {action_class}">{item}</div>')
            elif isinstance(item, dict):
                text = item.get('text', '')
                badge = item.get('badge', '')
                active = 'active' if item.get('active', False) else ''
                action_class = 'list-group-item-action' if clickable else ''
                badge_html = f'<span class="badge bg-primary rounded-pill">{(badge)}</span>' if badge else ''
                
                # HTML tag varsa escape yapma, yoksa yap
                display_text = text if '<' in text else (text)
                
                html.append(f'''
                <div class="list-group-item {action_class} {active} d-flex justify-content-between align-items-center">
                    {display_text}
                    {badge_html}
                </div>
                ''')
        
        html.append('</div>')
        return '\n'.join(html)

    def create_badge_group(self, badges, badge_class="bg-primary"):
        """Badge Group"""
        html = ['<div class="badge-group mb-3">']
        for badge in badges:
            if isinstance(badge, str):
                html.append(f'<span class="badge {badge_class} me-1">{(badge)}</span>')
            elif isinstance(badge, dict):
                text = (badge.get('text', ''))
                css_class = badge.get('class', badge_class)
                html.append(f'<span class="badge {css_class} me-1">{text}</span>')
        html.append('</div>')
        return '\n'.join(html)

    def create_button_group(self, buttons, size=""):
        """Button Group"""
        html = [f'<div class="btn-group {size}" role="group">']
        for btn in buttons:
            text = (btn.get('text', ''))
            css_class = btn.get('class', 'btn-secondary')
            onclick = btn.get('onclick', '')
            onclick_attr = f'onclick="{onclick}"' if onclick else ''
            html.append(f'<button type="button" class="btn {css_class}" {onclick_attr}>{text}</button>')
        html.append('</div>')
        return '\n'.join(html)

    def create_breadcrumb(self, items):
        """Breadcrumb"""
        html = ['<nav aria-label="breadcrumb"><ol class="breadcrumb">']
        for item in items:
            text = (item.get('text', ''))
            href = item.get('href', '#')
            active = item.get('active', False)
            if active:
                html.append(f'<li class="breadcrumb-item active" aria-current="page">{text}</li>')
            else:
                html.append(f'<li class="breadcrumb-item"><a href="{href}">{text}</a></li>')
        html.append('</ol></nav>')
        return '\n'.join(html)

    def create_pagination(self, current_page, total_pages, base_url="/"):
        """Pagination"""
        html = ['<nav><ul class="pagination">']
        
        # Previous
        disabled = 'disabled' if current_page == 1 else ''
        prev_page = current_page - 1 if current_page > 1 else 1
        html.append(f'''
        <li class="page-item {disabled}">
            <a class="page-link" href="{base_url}?page={prev_page}">Önceki</a>
        </li>
        ''')
        
        # Pages
        for i in range(1, total_pages + 1):
            active = 'active' if i == current_page else ''
            html.append(f'''
            <li class="page-item {active}">
                <a class="page-link" href="{base_url}?page={i}">{i}</a>
            </li>
            ''')
        
        # Next
        disabled = 'disabled' if current_page == total_pages else ''
        next_page = current_page + 1 if current_page < total_pages else total_pages
        html.append(f'''
        <li class="page-item {disabled}">
            <a class="page-link" href="{base_url}?page={next_page}">Sonraki</a>
        </li>
        ''')
        
        html.append('</ul></nav>')
        return '\n'.join(html)

    def create_header(self, text, tag="h4", css_class="mb-3 fw-bold text-primary"):
        """Header (Başlık)"""
        # DÜZELTME: escape(text) kaldırıldı
        return f'<{tag} class="{css_class}">{text}</{tag}>'

    def create_html(self, html_content):
        """
        Saf HTML içeriği döndürür.(E-Fatura butonları vb.için)
        """
        return str(html_content)
