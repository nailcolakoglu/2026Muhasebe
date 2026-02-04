# app/modules/rapor/registry.py

# Rapor sınıflarını buraya import ediyoruz
from .engine.standard import YevmiyeDefteriRaporu, BuyukDefterRaporu, GelirTablosuRaporu

# Rapor Kataloğu (Fabrika Ayarları)
# Yeni bir rapor yazdığında sadece buraya eklemen yeterli olacak.
RAPOR_KATALOGU = {
    'yevmiye': {
        'sinif': YevmiyeDefteriRaporu,
        'ad': 'Yevmiye Defteri',
        'yetki': 'muhasebe', # İleride yetki kontrolü için kullanılabilir
        'ikon': 'bi-book'
    },
    'kebir': {
        'sinif': BuyukDefterRaporu,
        'ad': 'Büyük Defter (Kebir)',
        'yetki': 'muhasebe',
        'ikon': 'bi-journal-bookmark'
    },
    'gelir_tablosu': {
        'sinif': GelirTablosuRaporu,
        'ad': 'Gelir Tablosu',
        'yetki': 'yonetici',
        'ikon': 'bi-graph-up-arrow'
    }
}

def get_rapor_class(rapor_turu):
    """Verilen türe göre rapor sınıfını döndürür."""
    kayit = RAPOR_KATALOGU.get(rapor_turu)
    if kayit:
        return kayit['sinif']
    return None