from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from app.modules.kategori.models import StokKategori
from app.extensions import get_tenant_db # Tenant DB erişimi eklendi

def create_kategori_form(kategori=None):
    is_edit = kategori is not None
    action_url = f"/kategori/duzenle/{kategori.id}" if is_edit else "/kategori/ekle"
    title = _("Kategori Düzenle") if is_edit else _("Yeni Stok Kategorisi")
    
    form = Form(name="kategori_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- Veri Hazırlığı (Üst Kategori Seçimi İçin) ---
    # ALTIN KURAL: Form doldururken de tenant_db kullanıyoruz.
    tenant_db = get_tenant_db()
    
    query = tenant_db.query(StokKategori).filter_by(firma_id=current_user.firma_id)
    
    # Düzenleme modundaysak, kategorinin kendisini "Üst Kategori" listesinden çıkaralım
    if is_edit:
        query = query.filter(StokKategori.id != kategori.id)
        
    kategoriler = query.order_by(StokKategori.ad).all()
    
    # (0, 'Ana Kategori') seçeneğini başa ekleyelim
    kategori_opts = [(0, '--- Ana Kategori (Yok) ---')] + [(k.id, k.ad) for k in kategoriler]

    # --- ALANLAR ---
    ad = FormField('ad', FieldType.TEXT, _('Kategori Adı'), required=True, value=kategori.ad if kategori else '', icon='bi bi-tag')
    
    ust_kategori_id = FormField('ust_kategori_id', FieldType.SELECT, _('Üst Kategori'), 
                                options=kategori_opts, 
                                value=kategori.ust_kategori_id if kategori and kategori.ust_kategori_id else 0,
                                select2_config={'placeholder': 'Seçiniz'})

    # --- LAYOUT ---
    layout.add_row(ad)
    layout.add_row(ust_kategori_id)
    
    # Bilgi Notu (kategori.alt_kategoriler ilişkisi Model'de tanımlıysa çalışır,
    # ancak ilişki lazy='dynamic' ise tenant session hatası verebilir. 
    # Basit bir list ilişki ise sorun olmaz. Garanti olması için manuel sayım yapılabilir ama şimdilik model yapını bozmamak için dokunmuyorum.)
    if is_edit and hasattr(kategori, 'alt_kategoriler') and kategori.alt_kategoriler:
        # Not: Eğer modelde backref lazy='dynamic' değilse len() çalışır.
        # Firebird session'ı açık olduğu sürece ilişki yüklenebilir.
        try:
            count = len(kategori.alt_kategoriler)
            if count > 0:
                layout.add_alert("Bilgi", f"Bu kategoriye bağlı <b>{count}</b> adet alt kategori bulunmaktadır.", "info")
        except:
            pass # İlişki yüklenemezse hatayı yut

    form.set_layout_html(layout.render())
    form.add_fields(ad, ust_kategori_id)
    
    return form