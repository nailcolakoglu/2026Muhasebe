from flask_login import current_user

class FieldPermission:
    """
    Alan Seviyesinde Yetki Kontrolü (Field-Level Security - FLS)
    Bir form elemanını kimin görebileceğini ve kimin düzenleyebileceğini belirler.
    """
    def __init__(self, view_roles=None, edit_roles=None):
        """
        view_roles: Görebilecek roller listesi. None veya ['*'] ise herkes görür.
        edit_roles: Düzenleyebilecek roller listesi. None veya ['*'] ise herkes düzenler.
        """
        self.view_roles = view_roles or ['*']
        self.edit_roles = edit_roles or ['*']

    def _get_current_user_roles(self):
        """Kullanıcının rollerini getirir"""
        if not current_user or not current_user.is_authenticated:
            return []
        print('current_user:', current_user)
        print("KULLANICI VERİLERİ:", current_user.__dict__)
        print("TÜM SAHALAR VE YETENEKLER:", dir(current_user))
        # DOĞRU KULLANIM: Eğer 'roles' özelliği yoksa 'role' dene, o da yoksa varsayılan 'user' olsun.
        roles_data = getattr(current_user, 'roles', getattr(current_user, 'role', 'user'))
        
        if isinstance(roles_data, list):
            return [r.lower() for r in roles_data]
        
        return [r.strip().lower() for r in str(roles_data).split(',')]

    def can_view(self) -> bool:
        """Kullanıcı bu alanı görebilir mi?"""
        if '*' in self.view_roles:
            return True
        
        user_roles = self._get_current_user_roles()
        
        # ✨ SİHİRLİ DOKUNUŞ: 'admin' ve 'patron' her alanı şartsız görebilir!
        if 'admin' in user_roles or 'patron' in user_roles or 'superadmin' in user_roles:
            return True
            
        return bool(set(self.view_roles) & set(user_roles))

    def can_edit(self) -> bool:
        """Kullanıcı bu alanı düzenleyebilir mi?"""
        if '*' in self.edit_roles:
            return True
            
        user_roles = self._get_current_user_roles()
        
        # ✨ SİHİRLİ DOKUNUŞ: 'admin' ve 'patron' her alanı şartsız düzenleyebilir!
        if 'admin' in user_roles or 'patron' in user_roles or 'superadmin' in user_roles:
            return True
            
        return bool(set(self.edit_roles) & set(user_roles))