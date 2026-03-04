# form_builder/kanban.py

from html import escape
import json

class KanbanBoard:
    """
    Enterprise Kanban Panosu (Swimlane ve Real-Time Socket.IO Destekli).
    Verileri gruplar, 2D (Statü x Kulvar) sürükle-bırak arayüzü oluşturur.
    """
    
    def __init__(self, board_id, data, group_field, title_field, 
                 subtitle_field=None, badge_field=None, 
                 columns=None, update_url=None, 
                 swimlane_field=None, swimlanes=None):
        """
        Args:
            board_id: Panonun benzersiz ID'si
            data: Veri listesi (Dict listesi)
            group_field: Dikey sütun gruplaması (örn: 'status')
            title_field: Kart başlığı (örn: 'company_name')
            columns: Sütun tanımları {'todo': {'label': 'Yapılacak', 'color': 'warning'}}
            update_url: Sürükleme bittiğinde tetiklenecek API adresi
            swimlane_field: Yatay kulvar gruplaması (örn: 'priority' veya 'assignee_id')
            swimlanes: Kulvar tanımları [{'id': 'high', 'label': 'Yüksek Öncelik'}]
        """
        self.board_id = board_id
        self.data = data
        self.group_field = group_field
        self.title_field = title_field
        self.subtitle_field = subtitle_field
        self.badge_field = badge_field
        self.update_url = update_url
        
        # Swimlane (Yatay Kulvar) Ayarları
        self.swimlane_field = swimlane_field
        self.swimlanes = swimlanes
        
        # WebSocket Ayarları
        self.realtime = False
        self.socket_ns = ''
        
        # Varsayılan kolon ayarları
        self.columns = columns or {
            'new': {'label': 'Yeni', 'color': 'secondary'},
            'in_progress': {'label': 'İşlemde', 'color': 'primary'},
            'done': {'label': 'Tamamlandı', 'color': 'success'}
        }

    def enable_realtime(self, socketio_namespace='/kanban'):
        """Socket.IO ile canlı (sayfa yenilemeden) senkronizasyon"""
        self.realtime = True
        self.socket_ns = socketio_namespace
        return self

    def _render_card(self, item):
        item_id = item.get('id', '')
        title = escape(str(item.get(self.title_field, 'İsimsiz')))
        
        subtitle_html = ""
        if self.subtitle_field and item.get(self.subtitle_field):
            subtitle_html = f"<div class='kanban-card-subtitle text-muted small mt-1'>{escape(str(item.get(self.subtitle_field)))}</div>"
            
        badge_html = ""
        if self.badge_field and item.get(self.badge_field):
            badge_html = f"<span class='badge bg-info float-end'>{escape(str(item.get(self.badge_field)))}</span>"
            
        return f"""
        <div class="kanban-card shadow-sm" id="kanban-card-{item_id}" data-id="{item_id}" draggable="true" ondragstart="drag(event)">
            {badge_html}
            <div class="kanban-card-title fw-bold text-dark">{title}</div>
            {subtitle_html}
        </div>
        """

    def _render_board(self, data, swimlane_id=""):
        """Sütunları ve içindeki kartları çizer"""
        html = ['<div class="kanban-board d-flex align-items-start gap-3" style="overflow-x: auto; padding-bottom: 10px;">']
        
        for col_id, col_info in self.columns.items():
            col_label = col_info.get('label', col_id)
            col_color = col_info.get('color', 'secondary')
            
            # Bu kolon ve (varsa) bu kulvara ait verileri filtrele
            col_data = [item for item in data if str(item.get(self.group_field, '')) == str(col_id)]
            
            html.append(f"""
            <div class="kanban-column bg-light rounded border">
                <div class="kanban-header bg-{col_color} text-white p-2 fw-bold d-flex justify-content-between align-items-center rounded-top">
                    <span>{col_label}</span>
                    <span class="badge bg-white text-{col_color} rounded-pill count-badge">{len(col_data)}</span>
                </div>
                <div class="kanban-body p-2" data-status="{col_id}" data-swimlane="{swimlane_id}" ondrop="drop(event)" ondragover="allowDrop(event)">
            """)
            
            for item in col_data:
                html.append(self._render_card(item))
                
            html.append('</div></div>')
            
        html.append('</div>')
        return '\n'.join(html)

    def render(self):
        html = [f'<div class="kanban-wrapper" id="{self.board_id}">']
        
        # ✨ SİHİRLİ DOKUNUŞ: Swimlane (Kulvar) Motoru
        if self.swimlane_field and self.swimlanes:
            for sl in self.swimlanes:
                sl_id = str(sl.get('id', ''))
                sl_label = sl.get('label', 'İsimsiz Kulvar')
                
                # Sadece bu kulvara ait veriyi filtrele
                lane_data = [item for item in self.data if str(item.get(self.swimlane_field, '')) == sl_id]
                
                html.append('<div class="kanban-swimlane mb-4">')
                html.append(f'<h5 class="kanban-swimlane-header text-secondary border-bottom pb-2 mb-3"><i class="bi bi-layers me-2"></i>{sl_label}</h5>')
                html.append(self._render_board(lane_data, swimlane_id=sl_id))
                html.append('</div>')
        else:
            # Standart (Tek Kulvarlı) Kanban
            html.append(self._render_board(self.data))
            
        html.append('</div>')
        return self._get_css() + '\n'.join(html) + self._get_js()

    def _get_css(self):
        return """
        <style>
            .kanban-column { width: 300px; min-width: 300px; flex-shrink: 0; }
            .kanban-body { min-height: 150px; transition: background-color 0.2s; }
            .kanban-body.drag-over { background-color: #e2e3e5 !important; border: 2px dashed #adb5bd; }
            .kanban-card { background: white; padding: 12px; margin-bottom: 10px; border-radius: 6px; border-left: 4px solid #4e73df; cursor: grab; transition: transform 0.1s, box-shadow 0.1s; }
            .kanban-card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .kanban-card:active { cursor: grabbing; transform: scale(0.98); }
        </style>
        """

    def _get_js(self):
        js = f"""
        <script>
            // --- SÜRÜKLE BIRAK (DRAG & DROP) MOTORU ---
            function allowDrop(ev) {{
                ev.preventDefault();
                ev.currentTarget.classList.add('drag-over');
            }}
            
            // Sürükleme efekti temizliği için global event listener
            document.addEventListener('dragleave', function(ev) {{
                if(ev.target.classList && ev.target.classList.contains('kanban-body')) {{
                    ev.target.classList.remove('drag-over');
                }}
            }});

            function drag(ev) {{
                ev.dataTransfer.setData("text", ev.currentTarget.id);
            }}

            function drop(ev) {{
                ev.preventDefault();
                var dropZone = ev.currentTarget;
                dropZone.classList.remove('drag-over');
                
                var data = ev.dataTransfer.getData("text");
                var card = document.getElementById(data);
                
                if (dropZone && card) {{
                    dropZone.appendChild(card);
                    updateKanbanCounts();

                    var newStatus = dropZone.getAttribute('data-status');
                    var newSwimlane = dropZone.getAttribute('data-swimlane');
                    var itemId = card.getAttribute('data-id');

                    // Backend'e Güncelleme Gönder
                    var updateUrl = '{self.update_url}';
                    var tokenValue = document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute('content') : '';
                    
                    if(updateUrl && updateUrl !== 'None') {{
                        fetch(updateUrl, {{
                            method: 'POST',
                            headers: {{ 
                                'Content-Type': 'application/json',
                                'X-CSRFToken': tokenValue
                            }},
                            body: JSON.stringify({{ id: itemId, status: newStatus, swimlane: newSwimlane }})
                        }}).catch(err => console.error('Kanban Fetch Hatası:', err));
                    }}
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
        
        # ✨ SİHİRLİ DOKUNUŞ: Real-Time WebSocket Senkronizasyonu
        if self.realtime:
            js += f"""
            <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
            <script>
                document.addEventListener("DOMContentLoaded", function() {{
                    const socket = io('{self.socket_ns}');
                    
                    socket.on('kanban_update', (payload) => {{
                        // payload formatı: {{ card_id: '123', new_status: 'done', new_swimlane: 'high' }}
                        const card = document.getElementById('kanban-card-' + payload.card_id);
                        if(card) {{
                            // Hedef kolon ve (varsa) kulvarı bul
                            let selector = `.kanban-body[data-status="${{payload.new_status}}"]`;
                            if (payload.new_swimlane) {{
                                selector += `[data-swimlane="${{payload.new_swimlane}}"]`;
                            }}
                            
                            const targetDropZone = document.querySelector(selector);
                            
                            if(targetDropZone) {{
                                targetDropZone.appendChild(card);
                                updateKanbanCounts();
                                
                                // Canlı değişimi belli eden şık bir "flaş" efekti
                                card.style.transition = 'background-color 0.5s';
                                card.style.backgroundColor = '#d4edda'; // Açık yeşil parlama
                                setTimeout(() => card.style.backgroundColor = '', 1000);
                            }}
                        }}
                    }});
                }});
            </script>
            """
        return js