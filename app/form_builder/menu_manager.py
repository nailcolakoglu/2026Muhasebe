import logging
from flask import session, g, url_for
from app.extensions import cache, get_tenant_db
from app.modules.firmalar.models import SystemMenu
from sqlalchemy import asc

logger = logging.getLogger(__name__)

class MenuManager:
    """
    Menü Yönetimi - Cache Destekli ve Link Hesaplamalı
    """

    @staticmethod
    def get_tree():
        """
        Aktif Tenant için menü ağacını getirir.
        Veriyi Cache'den alır, ancak Linkleri (url_for) anlık hesaplar.
        """
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            return []

        # 1. Kullanıcı Rollerini Belirle
        current_role_str = session.get('tenant_role', 'user')
        user_roles = [r.strip() for r in current_role_str.split(',')]
        
        # Admin ve Patron her şeyi görür
        if getattr(g, 'user', None) and g.user.is_superadmin:
            user_roles.append('admin')

        # 2. CACHE KATMANI
        cache_key = f"menu_raw_{tenant_id}"
        menu_data = cache.get(cache_key)

        if menu_data is None:
            tenant_db = get_tenant_db()
            if not tenant_db:
                return []
            
            try:
                # DB'den çek
                items = tenant_db.query(SystemMenu).filter_by(aktif=True).order_by(asc(SystemMenu.sira)).all()
                
                # SÖZLÜĞE ÇEVİR (Ham Veri)
                menu_data = []
                for item in items:
                    menu_data.append({
                        'id': item.id,
                        'baslik': item.baslik,
                        'icon': item.icon,
                        'endpoint': item.endpoint, 
                        'url': item.url, # Statik URL (Varsa)
                        'parent_id': item.parent_id,
                        'yetkili_roller': item.yetkili_roller,
                        'sira': item.sira
                    })
                
                cache.set(cache_key, menu_data, timeout=3600)
                
            except Exception as e:
                logger.error(f"Menü DB Hatası: {e}")
                return []

        # 3. AĞACI OLUŞTUR (Runtime)
        try:
            return MenuManager._build_tree(menu_data, user_roles)
        except Exception as e:
            logger.error(f"Menü Tree Hatası: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def _build_tree(menu_items, user_roles):
        """
        Düz listeyi ağaca çevirir + URL'leri hesaplar.
        """
        if not menu_items:
            return []

        items_map = {}
        
        for item in menu_items:
            # --- 🔗 URL HESAPLAMA (DÜZELTİLDİ) ---
            final_url = "#"
            endpoint = item.get('endpoint')
            static_url = item.get('url')

            if endpoint:
                try:
                    # Endpoint varsa (örn: 'cek.index') URL üret
                    final_url = url_for(endpoint)
                except Exception:
                    # Endpoint bulunamadıysa (Blueprint yüklenmediyse)
                    final_url = "#"
            elif static_url:
                # Statik URL varsa onu kullan
                final_url = static_url
            # -------------------------------------

            # Yeni node oluştur
            node = {
                'id': item['id'],
                'baslik': item['baslik'],
                'icon': item['icon'],
                'url': final_url, # ✅ DÜZELTME: Şablon 'url' bekliyor, buraya atadık.
                'children': [],
                'parent_id': item['parent_id'],
                'yetkili_roller': item['yetkili_roller']
            }
            items_map[item['id']] = node

        # Parent-Child İlişkisi
        root_items = []
        for item_id, node in items_map.items():
            parent_id = node['parent_id']
            if parent_id and parent_id in items_map:
                items_map[parent_id]['children'].append(node)
            else:
                root_items.append(node)

        # Yetki Filtreleme
        def filter_recursive(nodes):
            filtered = []
            for node in nodes:
                allowed = True
                if node['yetkili_roller']:
                    required = [r.strip() for r in node['yetkili_roller'].split(',')]
                    if not set(required).intersection(set(user_roles)):
                        allowed = False
                
                if allowed:
                    if node['children']:
                        node['children'] = filter_recursive(node['children'])
                    
                    # Linki yoksa ve çocuğu da yoksa gizle
                    if node['url'] == "#" and not node['children']:
                        continue
                        
                    filtered.append(node)
            return filtered

        return filter_recursive(root_items)

    @staticmethod
    def clear_cache():
        tenant_id = session.get('tenant_id')
        if tenant_id:
            cache.delete(f"menu_raw_{tenant_id}")
            
    @staticmethod
    def get_breadcrumb(current_url: str):
        """
        Aktif sayfa için hiyerarşik Breadcrumb (Yol Haritası) oluşturur.
        Query parametrelerini (örneğin ?page=2) yoksayarak akıllı eşleşme yapar.
        """
        menu_tree = MenuManager.get_tree()
        
        # URL'deki GET parametrelerini temizle (Sadece ana path kalsın)
        target_path = current_url.split('?')[0] if current_url else ''

        def _find_path(items, target, current_path=None):
            # ✨ GÜVENLİK: Python 'Mutable Default Argument' hatasını önlemek için None kontrolü
            if current_path is None:
                current_path = []
                
            for item in items:
                # Menüdeki URL'yi de temizle (Güvenlik)
                item_url = item.get('url', '').split('?')[0]
                
                # 1. Hedef Bulunduysa
                if item_url and item_url == target:
                    return current_path + [item]
                
                # 2. Alt Menülerde (Children) Ara
                if item.get('children'):
                    result = _find_path(item['children'], target, current_path + [item])
                    if result:
                        return result
            return None
        
        breadcrumb = _find_path(menu_tree, target_path)
        return breadcrumb or []