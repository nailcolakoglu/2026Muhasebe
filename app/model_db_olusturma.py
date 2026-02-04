from app import create_app
from extensions import db

app = create_app()

with app.app_context():
    #db.drop_all()                # DİKKAT TABLOLARI SİLMEMEK İÇİN HATIRLATMA KOYDUM.
    db.create_all()
    print("✅ Master DB yeniden oluşturuldu")
    
    # Tabloları kontrol et
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"✅ Tablolar: {tables} chr(13)")

exit()