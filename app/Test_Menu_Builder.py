# Test_Menu_Builder.py (SESSION MOCK)

from app import create_app
from extensions import db
from flask import session
from app.modules.firmalar.models import MenuItem
from flask_login import login_user
from models.master import User, Tenant

app = create_app()

with app.app_context():
    with app.test_request_context():
        print("\n🔍 Tenant ID bulunuyor...\n")
        
        # Master DB'den tenant bul
        tenant = Tenant.query.filter_by(kod='MUHASEBE').first()
        
        if not tenant:
            print("❌ Tenant bulunamadı!  Lütfen önce /setup'ı çalıştırın")
            exit()
        
        print(f"✅ Tenant: {tenant.unvan} (ID: {tenant.id})\n")
        
        # Session'a ekle
        session['tenant_id'] = tenant.id
        session['tenant_role'] = 'admin'
        
        # Mock user
        user = User.query.first()
        if user:
            login_user(user)
            print(f"✅ Kullanıcı: {user.email}\n")
        
        # Firebird bağlantısı
        from extensions import get_tenant_db
        
        tenant_db = get_tenant_db()
        
        if not tenant_db:
            print("❌ Tenant DB bağlantısı başarısız")
            print(f"   DB Name: {tenant.db_name}")
            print(f"   DB Path: {tenant.db_name}")
            exit()
        
        print(f"✅ Firebird bağlantısı başarılı\n")
        
        # Menü sorguları
        total = tenant_db.query(MenuItem).count()
        print(f"📋 Toplam Menü: {total}")
        
        active = tenant_db.query(MenuItem).filter_by(aktif=True).count()
        print(f"✅ Aktif Menü: {active}")
        
        # Ana menüler
        main_menus = tenant_db.query(MenuItem).filter_by(
            parent_id=None, 
            aktif=True
        ).order_by(MenuItem.sira).all()
        
        print(f"\n🏠 ANA MENÜLER ({len(main_menus)} adet):\n")
        
        for menu in main_menus[:10]: 
            alt_sayisi = tenant_db.query(MenuItem).filter_by(
                parent_id=menu.id, 
                aktif=True
            ).count()
            
            icon_str = menu.icon or ""
            url_str = menu.url or menu.endpoint or "#"
            
            print(f"  {menu.sira:2d}.{menu.baslik:30s} {icon_str:25s} → {url_str:30s} [Alt: {alt_sayisi}]")
        
        # MenuManager testi
        print("\n" + "="*60)
        print("🧪 MENU MANAGER TESTİ")
        print("="*60 + "\n")
        
        from form_builder.menu_manager import MenuManager
        
        menu_tree = MenuManager.get_tree()
        print(f"✅ MenuManager.get_tree() sonucu: {len(menu_tree)} ana menü\n")
        
        for item in menu_tree[: 5]:
            print(f"📌 {item['baslik']}")
            print(f"   Icon: {item['icon']}")
            print(f"   URL:  {item['url']}")
            print(f"   Alt:  {len(item['children'])} adet")
            
            if item['children']:
                for child in item['children'][:3]:
                    print(f"      └─ {child['baslik']} → {child['url']}")
            print()

print("\n✅ Test tamamlandı")