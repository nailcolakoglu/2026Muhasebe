from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from app.modules.firmalar.models import SystemMenu

def create_menu_form(menu=None):
    is_edit = menu is not None
    action = f"/sistem/menu/duzenle/{menu.id}" if is_edit else "/sistem/menu/ekle"
    
    form = Form(name="menu_form", title="Menü Öğesi", action=action, method="POST", ajax=True)
    layout = FormLayout()
    
    # Parent Seçenekleri (Kendisi hariç)
    parents = SystemMenu.query.order_by(SystemMenu.baslik).all()
    parent_opts = [(0, '--- Ana Menü ---')] + [(p.id, f"{p.baslik}") for p in parents if not is_edit or p.id != menu.id]
    
    baslik = FormField('baslik', FieldType.TEXT, 'Başlık', required=True, value=menu.baslik if menu else '', icon='bi bi-type')
    icon = FormField('icon', FieldType.TEXT, 'İkon Class', value=menu.icon if menu else 'bi bi-circle', placeholder='bi bi-house')
    
    parent_id = FormField('parent_id', FieldType.SELECT, 'Üst Menü', options=parent_opts, value=menu.parent_id if menu else 0)
    
    endpoint = FormField('endpoint', FieldType.TEXT, 'Flask Rota', value=menu.endpoint if menu else '', placeholder='modul.index')
    url = FormField('url', FieldType.TEXT, 'Statik URL', value=menu.url if menu else '', placeholder='/tarafim')
    
    yetkili_roller = FormField('yetkili_roller', FieldType.TEXT, 'Roller (Virgülle)', value=menu.yetkili_roller if menu else '', placeholder='admin,muhasebe')
    sira = FormField('sira', FieldType.NUMBER, 'Sıralama', value=menu.sira if menu else 0)
    aktif = FormField('aktif', FieldType.CHECKBOX, 'Aktif mi?', value=menu.aktif if menu else True)

    layout.add_row(baslik, icon)
    layout.add_row(parent_id, sira)
    layout.add_row(endpoint, url)
    layout.add_row(yetkili_roller, aktif)
    
    form.set_layout_html(layout.render())
    form.add_fields(baslik, icon, parent_id, endpoint, url, yetkili_roller, sira, aktif)
    return form