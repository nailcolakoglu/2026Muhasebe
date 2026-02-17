# test_config.py

from app import create_app

app = create_app()

with app.app_context():
    print("=" * 60)
    print("TENANT DB CONFIG KONTROLÜ")
    print("=" * 60)
    print(f"TENANT_DB_HOST: {app.config['TENANT_DB_HOST']}")
    print(f"TENANT_DB_PORT: {app.config['TENANT_DB_PORT']}")
    print(f"TENANT_DB_USER: {app.config['TENANT_DB_USER']}")
    print(f"TENANT_DB_PASSWORD: {app.config['TENANT_DB_PASSWORD'][:3]}***")
    print(f"TENANT_DB_CHARSET: {app.config['TENANT_DB_CHARSET']}")
    print(f"TENANT_DB_PREFIX: {app.config['TENANT_DB_PREFIX']}")
    print("=" * 60)
    
    # URL Template test
    test_db = "erp_tenant_TEST001"
    url = app.config['TENANT_DB_URL_TEMPLATE'].format(tenant_code=test_db)
    print(f"\nTest URL: {url.replace(app.config['TENANT_DB_PASSWORD'], '***')}")
    print("=" * 60)