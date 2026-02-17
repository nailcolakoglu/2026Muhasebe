# app/modules/raporlar/rapor_builder.py

from sqlalchemy import text, func, case, and_, or_
from datetime import datetime, timedelta
import pandas as pd

class RaporBuilder:
    """
    Veritabanı bağımsız dinamik rapor oluşturucu.
    Kullanıcı arayüzden rapor tanımlayabilir.
    """
    
    def __init__(self, tenant_db):
        self.db = tenant_db
        self.filters = []
        self.groupby = []
        self.aggregations = []
        self.order = []
        
    def add_filter(self, column, operator, value):
        """Filtre ekle: ('tarih', '>=', '2024-01-01')"""
        self.filters.append({
            'column': column,
            'operator': operator,
            'value': value
        })
        return self
    
    def add_group(self, column, alias=None):
        """Gruplama ekle"""
        self.groupby.append({
            'column': column,
            'alias': alias or column
        })
        return self
    
    def add_aggregation(self, function, column, alias):
        """Toplama fonksiyonu: ('SUM', 'tutar', 'toplam_tutar')"""
        self.aggregations.append({
            'function': function,  # SUM, AVG, COUNT, MIN, MAX
            'column': column,
            'alias': alias
        })
        return self
    
    def add_order(self, column, direction='ASC'):
        """Sıralama ekle"""
        self.order.append({
            'column': column,
            'direction': direction
        })
        return self
    
    def build_query(self, base_table):
        """SQL sorgusu oluştur (veritabanı bağımsız)"""
        
        # SELECT kısmı
        select_parts = []
        
        # Gruplamalar
        for grp in self.groupby:
            select_parts.append(f"{grp['column']} AS {grp['alias']}")
        
        # Agregasyonlar
        for agg in self.aggregations:
            func_name = agg['function'].upper()
            col = agg['column']
            alias = agg['alias']
            select_parts.append(f"{func_name}({col}) AS {alias}")
        
        select_clause = ", ".join(select_parts) if select_parts else "*"
        
        # WHERE kısmı
        where_parts = []
        params = {}
        
        for idx, flt in enumerate(self.filters):
            col = flt['column']
            op = flt['operator']
            val = flt['value']
            param_name = f"param_{idx}"
            
            # Operatör mapping
            if op == '=':
                where_parts.append(f"{col} = :{param_name}")
            elif op == 'LIKE':
                where_parts.append(f"{col} LIKE :{param_name}")
                val = f"%{val}%"
            elif op in ['>', '<', '>=', '<=', '!=']:
                where_parts.append(f"{col} {op} :{param_name}")
            elif op == 'BETWEEN':
                where_parts.append(f"{col} BETWEEN :{param_name}_start AND :{param_name}_end")
                params[f"{param_name}_start"] = val[0]
                params[f"{param_name}_end"] = val[1]
                continue
            
            params[param_name] = val
        
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        
        # GROUP BY kısmı
        groupby_clause = ""
        if self.groupby:
            groupby_cols = [g['column'] for g in self.groupby]
            groupby_clause = f"GROUP BY {', '.join(groupby_cols)}"
        
        # ORDER BY kısmı
        orderby_clause = ""
        if self.order:
            order_parts = [f"{o['column']} {o['direction']}" for o in self.order]
            orderby_clause = f"ORDER BY {', '.join(order_parts)}"
        
        # Final SQL
        sql = f"""
            SELECT {select_clause}
            FROM {base_table}
            WHERE {where_clause}
            {groupby_clause}
            {orderby_clause}
        """
        
        return text(sql), params
    
    def execute(self, base_table):
        """Raporu çalıştır ve DataFrame döndür"""
        sql, params = self.build_query(base_table)
        
        result = self.db.execute(sql, params).fetchall()
        
        # Pandas DataFrame'e çevir
        if result:
            columns = result[0].keys()
            df = pd.DataFrame(result, columns=columns)
            return df
        
        return pd.DataFrame()


# ===================================
# KULLANIM ÖRNEKLERİ
# ===================================

def rapor_aylik_satis_ozeti(tenant_db, baslangic, bitis):
    """Aylık satış özeti raporu"""
    
    builder = RaporBuilder(tenant_db)
    
    # Filtreleme
    builder.add_filter('fatura_turu', '=', 'SATIS')
    builder.add_filter('tarih', 'BETWEEN', (baslangic, bitis))
    
    # Gruplama (ay bazında)
    builder.add_group("EXTRACT(MONTH FROM tarih)", "ay")
    builder.add_group("EXTRACT(YEAR FROM tarih)", "yil")
    
    # Toplam hesaplama
    builder.add_aggregation('COUNT', 'id', 'fatura_sayisi')
    builder.add_aggregation('SUM', 'genel_toplam', 'toplam_tutar')
    builder.add_aggregation('AVG', 'genel_toplam', 'ortalama_tutar')
    
    # Sıralama
    builder.add_order('yil', 'DESC')
    builder.add_order('ay', 'DESC')
    
    return builder.execute('faturalar')


def rapor_cari_bakiye_analizi(tenant_db, min_bakiye=1000):
    """Cari bakiye analizi"""
    
    builder = RaporBuilder(tenant_db)
    
    # Sadece borclu cariler
    builder.add_filter('borc_bakiye', '>', min_bakiye)
    
    # Gruplama (şehir bazında)
    builder.add_group('sehir_id', 'sehir')
    
    # Toplam borç
    builder.add_aggregation('COUNT', 'id', 'cari_sayisi')
    builder.add_aggregation('SUM', 'borc_bakiye', 'toplam_borc')
    builder.add_aggregation('AVG', 'borc_bakiye', 'ortalama_borc')
    
    # En yüksek borçlular önce
    builder.add_order('toplam_borc', 'DESC')
    
    return builder.execute('cari_hesaplar')