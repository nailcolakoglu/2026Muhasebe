# Menu Builder

from app import create_app
from app.extensions import get_tenant_db
from flask import session
from app.modules.firmalar.models import MenuItem

app = create_app()

with app.app_context():
    session['tenant_id'] = 'b521c3e4-5af9-4951-91a1-657bed8d8a55'  # Senin tenant ID
    
    tenant_db = get_tenant_db()
    
    if tenant_db: 
        # Toplam menü sayısı
        total = tenant_db.query(MenuItem).count()
        print(f"📋 Toplam Menü:  {total}")
        
        # Aktif menüler
        active = tenant_db.query(MenuItem).filter_by(aktif=True).count()
        print(f"✅ Aktif Menü: {active}")
        
        # Ana menüler (parent_id = NULL)
        main_menus = tenant_db.query(MenuItem).filter_by(parent_id=None, aktif=True).order_by(MenuItem.sira).all()
        print(f"\n🏠 ANA MENÜLER ({len(main_menus)} adet):")
        
        for menu in main_menus[: 10]:  # İlk 10
            alt_sayisi = tenant_db.query(MenuItem).filter_by(parent_id=menu.id, aktif=True).count()
            print(f"  {menu.sira: 2d}.{menu.baslik:30s} ({menu.icon: 25s}) → {menu.url_target:30s} [Alt: {alt_sayisi}]")
        
        # İlk alt menü örneği
        ilk_ana = main_menus[0] if main_menus else None
        if ilk_ana:
            alt_menuler = tenant_db.query(MenuItem).filter_by(parent_id=ilk_ana.id, aktif=True).all()
            if alt_menuler:
                print(f"\n📂 '{ilk_ana.baslik}' ALT MENÜLERİ:")
                for alt in alt_menuler:
                    print(f"     └─ {alt.baslik} → {alt.url_target}")
    else:
        print("❌ Tenant DB bağlantısı yok")

exit()