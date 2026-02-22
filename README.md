# 🚀 2026 Muhasebe ERP Sistemi

Multi-tenant ERP sistemi - MySQL + Flask 3.0

## 📋 Özellikler

- ✅ Multi-tenant mimari (her firma ayrı database)
- ✅ Custom Form Builder
- ✅ DataGrid (filtreleme, sıralama, gruplama)
- ✅ MySQL Master + Tenant DB'ler
- ✅ Flask 3.0 + SQLAlchemy 2.0
- ✅ Babel i18n (TR/EN)
- ✅ CSRF koruması
- ✅ Session yönetimi

## 🔧 Teknolojiler

- **Backend:** Flask 3.0, SQLAlchemy 2.0
- **Database:** MySQL 8.0+
- **Frontend:** Bootstrap 5, jQuery, Select2
- **Cache:** SimpleCache / Redis (opsiyonel)
- **Auth:** Flask-Login

## 📦 Kurulum

```bash
# 1. Virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Gerekli paketler
pip install -r requirements.txt

# 3. .env dosyası oluştur
cp .env.example .env

# 4. Database oluştur
# MySQL'de:
CREATE DATABASE erp_master CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE erp_supervisor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 5. Tabloları oluştur
flask init-db

# 6. Çalıştır
python run.py
