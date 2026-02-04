# form_builder/kanban.py

from html import escape
import json

class KanbanBoard:
    """
    Python Code-First Kanban Panosu.
    Verileri gruplar, sürükle-bırak arayüzü oluşturur ve statü değişimlerini yönetir.
    """
    
    def __init__(self, board_id, data, group_field, title_field, 
                 subtitle_field=None, badge_field=None, 
                 columns=None, update_url=None):
        """
        Args:
            board_id: Panonun benzersiz ID'si
            data: Veri listesi (Dict listesi)
            group_field: Gruplama yapılacak alan (örn: 'status')
            title_field: Kart başlığı (örn: 'company_name')
            columns: Sütun tanımları ve renkleri {'todo': {'label': 'Yapılacak', 'color': 'warning'}}
            update_url: Sürükleme bittiğinde tetiklenecek API adresi
        """
        self.board_id = board_id
        self.data = data
        self.group_field = group_field
        self.title_field = title_field
        self.subtitle_field = subtitle_field
        self.badge_field = badge_field
        self.update_url = update_url
        
        # Varsayılan kolon ayarları
        self.columns = columns or {
            'new': {'label': 'Yeni', 'color': 'primary'},
            'progress': {'label': 'İşlemde', 'color': 'warning'},
            'done': {'label': 'Tamamlandı', 'color': 'success'}
        }

    def _group_data(self):
        """Verileri group_field'a göre ayırır"""
        grouped = {key: [] for key in self.columns.keys()}
        
        for item in self.data:
            key = item.get(self.group_field)
            if key in grouped:
                grouped[key].append(item)
            else:
                # Tanımsız statüleri ilk kolona at veya yoksay
                pass 
        return grouped

    def render(self):
        grouped_data = self._group_data()
        
        # CSS (Kart Efektleri)
        css = """
        <style>
            .kanban-board { display: flex; gap: 20px; overflow-x: auto; padding-bottom: 20px; }
            .kanban-column { 
                flex: 1; min-width: 300px; max-width: 350px; 
                background: #f8f9fa; border-radius: 12px; 
                display: flex; flex-direction: column; max-height: 80vh;
                border-top: 4px solid transparent;
            }
            .kanban-header { padding: 15px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
            .kanban-body { 
                padding: 10px; flex-grow: 1; overflow-y: auto; min-height: 150px;
                transition: background-color 0.3s;
            }
            .kanban-card {
                background: white; padding: 15px; margin-bottom: 10px;
                border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                cursor: grab; transition: all 0.2s; border-left: 3px solid transparent;
            }
            .kanban-card:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            .kanban-card:active { cursor: grabbing; }
            .kanban-card.dragging { opacity: 0.5; transform: scale(0.95); }
            .kanban-body.drag-over { background-color: rgba(0,0,0,0.05); border-radius: 8px; }
            
            /* Renk Temaları */
            .border-top-primary { border-top-color: #0d6efd; }
            .border-top-warning { border-top-color: #ffc107; }
            .border-top-success { border-top-color: #198754; }
            .border-top-danger { border-top-color: #dc3545; }
            .border-top-info { border-top-color: #0dcaf0; }
        </style>
        """

        html = [f'<div class="kanban-board" id="{self.board_id}">']
        
        for col_key, col_config in self.columns.items():
            items = grouped_data.get(col_key, [])
            count = len(items)
            color = col_config.get('color', 'secondary')
            label = col_config.get('label', col_key.title())
            
            html.append(f'''
            <div class="kanban-column border-top-{color}">
                <div class="kanban-header text-{color}">
                    <span>{label}</span>
                    <span class="badge bg-{color} rounded-pill count-badge">{count}</span>
                </div>
                <div class="kanban-body" data-status="{col_key}" ondrop="kanbanDrop(event)" ondragover="kanbanAllowDrop(event)" ondragleave="kanbanLeave(event)">
            ''')
            
            for item in items:
                item_id = item.get('id') or item.get('tckn') or item.get('company_name') # Unique ID bul
                title = escape(str(item.get(self.title_field, '')))
                subtitle = escape(str(item.get(self.subtitle_field, ''))) if self.subtitle_field else ''
                
                badge_html = ''
                if self.badge_field and item.get(self.badge_field):
                    badge_val = item.get(self.badge_field)
                    badge_html = f'<span class="badge bg-light text-dark border float-end">{badge_val}</span>'

                html.append(f'''
                <div class="kanban-card" id="card_{item_id}" draggable="true" ondragstart="kanbanDrag(event)" data-id="{item_id}">
                    <div class="fw-bold mb-1">{title}</div>
                    <div class="small text-muted">{subtitle}</div>
                    <div class="mt-2 clearfix">
                        {badge_html}
                        <button class="btn btn-sm btn-link text-decoration-none p-0" onclick="alert('Detay ID: {item_id}')">Detay</button>
                    </div>
                </div>
                ''')
                
            html.append('</div></div>') # Kapanış: body, column
            
        html.append('</div>') # Kapanış: board
        
        # JS (Sürükle Bırak Mantığı)
        # form_builder/kanban.py dosyasının en altındaki js değişkeni:

        # JS (Sürükle Bırak Mantığı)
        js = f"""
        <script>
            function kanbanAllowDrop(ev) {{ ev.preventDefault(); ev.currentTarget.classList.add('drag-over'); }}
            function kanbanLeave(ev) {{ ev.currentTarget.classList.remove('drag-over'); }}
            
            function kanbanDrag(ev) {{
                ev.dataTransfer.setData("text", ev.target.id);
                ev.target.classList.add('dragging');
            }}
            
            function kanbanDrop(ev) {{
                ev.preventDefault();
                var cardId = ev.dataTransfer.getData("text");
                var card = document.getElementById(cardId);
                var targetColumn = ev.currentTarget;
                
                targetColumn.classList.remove('drag-over');
                card.classList.remove('dragging');
                
                // Kartı yeni kolona taşı
                targetColumn.appendChild(card);
                
                // Sayaçları Güncelle
                updateKanbanCounts();
                
                // Backend'e Bildir
                var newStatus = targetColumn.getAttribute('data-status');
                var itemId = card.getAttribute('data-id');
                var updateUrl = '{self.update_url}';
                
                // ✅ GÜNCELLEME: CSRF Token'ı Meta Etiketinden Al
                var csrfToken = document.querySelector('meta[name="csrf-token"]');
                var tokenValue = csrfToken ? csrfToken.getAttribute('content') : '';
                
                if(updateUrl && updateUrl !== 'None') {{
                    fetch(updateUrl, {{
                        method: 'POST',
                        headers: {{ 
                            'Content-Type': 'application/json',
                            'X-CSRFToken': tokenValue // ✅ HEADER'A EKLE
                        }},
                        body: JSON.stringify({{ id: itemId, status: newStatus }})
                    }}).then(res => res.json())
                      .then(data => {{
                          if(data.success) {{
                              // Başarılı
                              console.log('Durum güncellendi');
                          }} else {{
                              alert('Güncelleme hatası: ' + (data.message || 'Bilinmeyen hata'));
                          }}
                      }})
                      .catch(err => {{
                          console.error('Fetch Hatası:', err);
                      }});
                }}
            }}
            
            function updateKanbanCounts() {{
                document.querySelectorAll('.kanban-column').forEach(col => {{
                    var count = col.querySelector('.kanban-body').children.length;
                    col.querySelector('.count-badge').innerText = count;
                }});
            }}
        </script>
        """
        
        return css + '\n'.join(html) + js