# tests/test_fatura.py (YENİ)
import pytest
from decimal import Decimal

def test_fatura_olusturma(auth_client):
    """Fatura oluşturma testi"""
    response = auth_client.post('/fatura/ekle', json={
        'belge_no': 'TEST-001',
        'tarih': '2025-01-15',
        'cari_id': 1,
        'kalemler': [
            {'aciklama': 'Test', 'miktar': 10, 'birim_fiyat': 100}
        ]
    })
    
    assert response.status_code == 200
    assert response.json['success'] == True

def test_soft_delete(auth_client):
    """Soft delete testi"""
    # Fatura oluştur
    response = auth_client.post('/fatura/ekle', json={...})
    fatura_id = response.json['id']
    
    # Sil
    response = auth_client.delete(f'/fatura/sil/{fatura_id}')
    assert response.status_code == 200
    
    # Silinmiş mi kontrol et (soft delete)
    response = auth_client.get(f'/fatura/{fatura_id}')
    assert response.status_code == 404  # Görünmemeli