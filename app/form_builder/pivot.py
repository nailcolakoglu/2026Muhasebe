# form_builder/pivot.py

import json
from collections import defaultdict

class PivotEngine:
    """
    Enterprise Data Analysis & Pivot Motoru.
    1D (Tek Boyutlu) ve 2D (Satır x Sütun Çapraz) matrisleme destekler.
    Drill-Down (Tıklayarak detaya inme) özelliğine sahiptir.
    """
    
    def __init__(self, data, rows, values, columns=None, aggregator='sum', title="Analiz Raporu", chart_type="bar"):
        """
        Args:
            data: Veri listesi (List of Dicts)
            rows: Satırda gruplanacak alan (örn: 'bolge')
            values: Hesaplanacak sayısal alan (örn: 'tutar')
            columns: Sütunda gruplanacak alan (opsiyonel, örn: 'ay')
            aggregator: 'sum', 'count', 'avg'
            chart_type: 'bar', 'line', 'pie', 'doughnut'
        """
        self.data = data
        self.rows = rows
        self.columns = columns
        self.values = values
        self.aggregator = aggregator
        self.title = title
        self.chart_type = chart_type
        self.chart_id = f"chart_{id(self)}"
        
        # Drill-Down Ayarları
        self.drill_endpoint = None
        self.drill_param = "filter"

    def enable_drill_down(self, endpoint, param_name="filter"):
        """Grafik elemanına tıklandığında detaya inme (Drill-Down) linkini aktif eder."""
        self.drill_endpoint = endpoint
        self.drill_param = param_name
        return self

    def _aggregate(self, vals):
        if not vals: return 0.0
        if self.aggregator == 'sum': return sum(vals)
        if self.aggregator == 'avg': return sum(vals) / len(vals)
        if self.aggregator == 'count': return len(vals)
        return sum(vals)

    def _process_data(self):
        """Veriyi 1D veya 2D olarak işler ve gruplar"""
        if not self.columns:
            # --- 1D STANDART PIVOT ---
            grouped = defaultdict(list)
            for item in self.data:
                key = str(item.get(self.rows) or 'Diğer')
                try: val = float(item.get(self.values, 0))
                except (ValueError, TypeError): val = 0.0
                grouped[key].append(val)
                
            result = {k: self._aggregate(v) for k, v in grouped.items()}
            # Büyükten küçüğe sırala
            return dict(sorted(result.items(), key=lambda x: x[1], reverse=True)), None
            
        else:
            # --- 2D MATRIX (CROSS-TAB) PIVOT ---
            matrix = defaultdict(lambda: defaultdict(list))
            col_keys = set()
            
            for item in self.data:
                row_key = str(item.get(self.rows) or 'Diğer')
                col_key = str(item.get(self.columns) or 'Diğer')
                try: val = float(item.get(self.values, 0))
                except (ValueError, TypeError): val = 0.0
                
                matrix[row_key][col_key].append(val)
                col_keys.add(col_key)
                
            result = {}
            for r_key, cols in matrix.items():
                result[r_key] = {c_key: self._aggregate(vals) for c_key, vals in cols.items()}
                
            return result, sorted(list(col_keys))

    def _get_colors(self):
        return ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796', '#5a5c69', '#f8f9fc']

    def render(self):
        """Chart.js ve HTML Tablo Çıktısını Üretir"""
        processed_data, col_keys = self._process_data()
        labels = list(processed_data.keys())
        colors = self._get_colors()
        
        chart_data = {"labels": labels, "datasets": []}
        table_html = ""

        if not self.columns:
            # 1 Boyutlu Veri (Grafik ve Tablo)
            data_values = list(processed_data.values())
            chart_data["datasets"].append({
                "label": f"{self.values.title()} ({self.aggregator})",
                "data": data_values,
                "backgroundColor": colors[:len(labels)] if self.chart_type in ['pie', 'doughnut'] else colors[0],
                "borderWidth": 1
            })
            
            table_html = f"<table class='table table-sm table-striped'><thead><tr><th>{self.rows.title()}</th><th class='text-end'>{self.values.title()}</th></tr></thead><tbody>"
            for k, v in processed_data.items():
                table_html += f"<tr><td>{k}</td><td class='text-end'>{v:,.2f}</td></tr>"
            table_html += "</tbody></table>"
            
        else:
            # 2 Boyutlu Veri (Çoklu Dataset ve Çapraz Tablo)
            for i, c_key in enumerate(col_keys):
                dataset_data = [processed_data[r].get(c_key, 0) for r in labels]
                chart_data["datasets"].append({
                    "label": c_key,
                    "data": dataset_data,
                    "backgroundColor": colors[i % len(colors)],
                    "borderWidth": 1
                })
                
            table_html = f"<table class='table table-sm table-striped table-bordered'><thead><tr><th>{self.rows.title()} \\ {self.columns.title()}</th>"
            for c in col_keys: table_html += f"<th class='text-end'>{c}</th>"
            table_html += "<th class='text-end bg-light'>Genel Toplam</th></tr></thead><tbody>"
            
            for r in labels:
                table_html += f"<tr><td><strong>{r}</strong></td>"
                row_total = 0
                for c in col_keys:
                    val = processed_data[r].get(c, 0)
                    row_total += val
                    table_html += f"<td class='text-end'>{val:,.2f}</td>"
                table_html += f"<td class='text-end bg-light'><strong>{row_total:,.2f}</strong></td></tr>"
            table_html += "</tbody></table>"

        # Şablon Üretimi
        html = f"""
        <div class="card shadow-sm mb-4" id="pivot_{self.chart_id}">
            <div class="card-header bg-white d-flex justify-content-between align-items-center">
                <h6 class="m-0 font-weight-bold text-primary"><i class="bi bi-bar-chart-fill me-2"></i>{self.title}</h6>
                <button class="btn btn-sm btn-outline-secondary" onclick="printDiv('pivot_{self.chart_id}')"><i class="bi bi-printer"></i></button>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-lg-7">
                        <div style="height: 300px; position: relative;">
                            <canvas id="{self.chart_id}"></canvas>
                        </div>
                    </div>
                    <div class="col-lg-5">
                        <div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
                            {table_html}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                var ctx = document.getElementById("{self.chart_id}").getContext('2d');
                var myChart = new Chart(ctx, {{
                    type: '{self.chart_type}',
                    data: {json.dumps(chart_data)},
                    options: {{
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: {str(self.chart_type == 'pie' or self.chart_type == 'doughnut').lower()}, position: 'bottom' }}
                        }},
                        scales: {{
                            y: {{ beginAtZero: true, display: {str(self.chart_type != 'pie' and self.chart_type != 'doughnut').lower()} }}
                        }},
                        
                        // ✨ SİHİRLİ DOKUNUŞ: Drill-Down (Detaya İnme) Motoru
                        { f'''
                        onHover: (event, chartElement) => {{
                            event.native.target.style.cursor = chartElement[0] ? 'pointer' : 'default';
                        }},
                        onClick: (event, elements) => {{
                            if (elements.length > 0) {{
                                const elementIndex = elements[0].index;
                                const label = myChart.data.labels[elementIndex];
                                let targetUrl = '{self.drill_endpoint}?{self.drill_param}=' + encodeURIComponent(label);
                                
                                // Eğer 2 boyutlu grafikse, tıklanan sütun bilgisini de gönder!
                                {'if (myChart.data.datasets.length > 1) { const datasetIndex = elements[0].datasetIndex; const colLabel = myChart.data.datasets[datasetIndex].label; targetUrl += "&col_filter=" + encodeURIComponent(colLabel); }' if self.columns else ''}
                                
                                window.location.href = targetUrl;
                            }}
                        }}
                        ''' if self.drill_endpoint else '' }
                    }}
                }});
            }});
        </script>
        """
        return html