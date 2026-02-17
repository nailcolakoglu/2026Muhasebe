"""
Context manager performans testi
"""
import time
from app import create_app
from app.context_manager import GlobalContextManager
from flask import g

app = create_app('testing')

def test_old_method():
    """Eski yöntem (her istekte DB sorgusu)."""
    with app.app_context():
        start = time.time()
        
        for _ in range(100):
            # Eski yöntem simülasyonu
            from app.models.master import Module
            modules = Module.query.all()
        
        elapsed = time.time() - start
        print(f"❌ Eski Yöntem: {elapsed:.2f}s (100 istek)")


def test_new_method():
    """Yeni yöntem (cache kullanımı)."""
    with app.app_context():
        start = time.time()
        
        for _ in range(100):
            # Yeni yöntem
            modules = GlobalContextManager.get_active_modules()
        
        elapsed = time.time() - start
        print(f"✅ Yeni Yöntem: {elapsed:.2f}s (100 istek)")


if __name__ == '__main__':
    print("🚀 Performans Testi Başladı\n")
    test_old_method()
    test_new_method()