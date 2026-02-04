# form_builder/pivot.py

import json
from collections import defaultdict

class PivotEngine:
    """
    Veri Analiz ve Raporlama Motoru.
    Veriyi alır, gruplar (Pivot) ve hem Tablo hem Grafik üretir.
    """
    
    def __init__(self, data, rows, values, aggregator='sum', title="Analiz Raporu", chart_type="bar"):
        """
        Args:
            data: Veri listesi (List of Dicts)
            rows: Satırda gruplanacak alan (örn: 'category')
            values: Hesaplanacak sayısal alan (örn: 'amount')
            aggregator: 'sum', 'count', 'avg'
            chart_type: 'bar', 'line', 'pie', 'doughnut'
        """
        self.data = data
        self.rows = rows
        self.values = values
        self.aggregator = aggregator
        self.title = title
        self.chart_type = chart_type
        self.chart_id = f"chart_{id(self)}"

    def _process_data(self):
        """Veriyi işler ve gruplar"""
        grouped = defaultdict(list)
        
        # 1.Gruplama
        for item in self.data:
            key = item.get(self.rows, 'Diğer')
            val = float(item.get(self.values, 0))
            grouped[key].append(val)
            
        # 2.Hesaplama (Aggregation)
        results = {}
        for key, vals in grouped.items():
            if self.aggregator == 'sum':
                results[key] = sum(vals)
            elif self.aggregator == 'count':
                results[key] = len(vals)
            elif self.aggregator == 'avg':
                results[key] = sum(vals) / len(vals) if vals else 0
                
        # 3.Sıralama (Değere göre azalan)
        return dict(sorted(results.items(), key=lambda item: item[1], reverse=True))

    def render(self):
        processed_data = self._process_data()
        labels = list(processed_data.keys())
        values = list(processed_data.values())
        
        # Grafik Renkleri (Otomatik Üretim)
        colors = [
            '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', 
            '#858796', '#5a5c69', '#f8f9fa', '#e83e8c', '#6f42c1'
        ]
        
        # Formatlanmış JSON (JS için)
        chart_data = {
            'labels': labels,
            'datasets': [{
                'label': self.values.title(),
                'data': values,
                'backgroundColor': colors[:len(labels)],
                'borderColor': '#ffffff',
                'borderWidth': 1
            }]
        }

        # HTML Çıktısı (Kart İçinde Grafik + Tablo Yan Yana)
        html = f"""
        <div class="card shadow mb-4">
            <div class="card-header py-3 d-flex flex-row align-items-center justify-content-between">
                <h6 class="m-0 font-weight-bold text-primary">{self.title}</h6>
                <div class="dropdown no-arrow">
                    <button class="btn btn-sm btn-outline-secondary" onclick="printDiv('{self.chart_id}_wrapper')">
                        <i class="fas fa-print"></i> Yazdır
                    </button>
                </div>
            </div>
            <div class="card-body" id="{self.chart_id}_wrapper">
                <div class="row">
                    <div class="col-md-8">
                        <div class="chart-area" style="height: 300px;">
                            <canvas id="{self.chart_id}"></canvas>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <h6 class="text-muted mb-3">Özet Veriler</h6>
                        <div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
                            <table class="table table-bordered table-sm table-hover">
                                <thead class="table-light">
                                    <tr>
                                        <th>{self.rows.title()}</th>
                                        <th class="text-end">{self.aggregator.upper()}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {''.join(f'<tr><td>{k}</td><td class="text-end fw-bold">{v:,.2f}</td></tr>' for k, v in processed_data.items())}
                                </tbody>
                                <tfoot class="table-light fw-bold">
                                    <tr>
                                        <td>TOPLAM</td>
                                        <td class="text-end">{sum(values):,.2f}</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                var ctx = document.getElementById("{self.chart_id}").getContext('2d');
                new Chart(ctx, {{
                    type: '{self.chart_type}',
                    data: {json.dumps(chart_data)},
                    options: {{
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: {str(self.chart_type == 'pie' or self.chart_type == 'doughnut').lower()}, position: 'bottom' }}
                        }},
                        scales: {{
                            y: {{ beginAtZero: true, display: {str(self.chart_type != 'pie' and self.chart_type != 'doughnut').lower()} }}
                        }}
                    }}
                }});
            }});
            
            function printDiv(divName) {{
                var printContents = document.getElementById(divName).innerHTML;
                var originalContents = document.body.innerHTML;
                document.body.innerHTML = printContents;
                window.print();
                document.body.innerHTML = originalContents;
                window.location.reload(); // JS eventlerini geri yüklemek için
            }}
        </script>
        """
        return html