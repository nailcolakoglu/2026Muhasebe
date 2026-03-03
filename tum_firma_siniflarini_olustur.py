# tüm firma sınıflarını oluşturur.
# tum_firma_siniflarini_olustur.py

# flask --app run.py shell

# mysql şifresini değiştir.

from app.extensions import db
from sqlalchemy import create_engine

# 1. Tenant veritabanınızın tam adresini yazın (Şifrenizi ve veritabanı adını kontrol edin)
# Örn: "mysql+pymysql://kullanici_adi:sifre@localhost/erp_tenant_2025izgrup"
tenant_uri = "mysql+pymysql://root:sifre123@localhost/erp_tenant_2025izgrup"

# 2. Özel bir bağlantı motoru oluşturun
tenant_engine = create_engine(tenant_uri)

# 3. Tablo oluşturma işlemini "bind" parametresi ile SADECE o veritabanına yönlendirin!
db.metadata.create_all(bind=tenant_engine)

print("Harika! Tablolar Tenant DB'ye kuruldu.")
exit()