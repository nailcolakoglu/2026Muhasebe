from app import create_app
from models import db
from modules.bolge.models import init_default_data

app = create_app()

def veritabanini_kur():
    with app.app_context():
        print("⏳ Veritabanı tabloları oluşturuluyor...")
        try:
            # 1.Tabloları Oluştur
            db.create_all()
            print("✅ Tablolar başarıyla oluşturuldu.")
            
            # 2.Varsayılan Verileri Yükle (Admin, Firma vb.)
            print("⏳ Varsayılan veriler yükleniyor...")
            init_default_data()
            print("✅ Veri yükleme tamamlandı.")
            
        except Exception as e:
            print(f"❌ HATA: {e}")

if __name__ == "__main__":
    veritabanini_kur()