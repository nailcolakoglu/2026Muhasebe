# app/modules/bolge/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from flask import session
from app.extensions import get_tenant_db, db # db=MySQL, get_tenant_db=Firebird
from app.modules.kullanici.models import Kullanici
from app.models.master import UserTenantRole # MySQL Rol Tablosu

def create_bolge_form(bolge=None):
    is_edit = bolge is not None
    action_url = f"/bolge/duzenle/{bolge.id}" if is_edit else "/bolge/ekle"
    title = _("Bölge Tanımı")
    
    form = Form(name="bolge_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    # --- YÖNETİCİ LİSTESİ (ÇAPRAZ SORGULAMA) ---
    yonetici_opts = [('', _('Seçiniz...'))]
    
    tenant_db = get_tenant_db()
    if tenant_db:
        try:
            # 1. Adım: MySQL'den 'bolge_muduru' rolüne sahip ID'leri bul
            # (Veya admin/patron da seçilebilir, tercihe bağlı)
            hedef_roller = ['bolge_muduru', 'admin', 'patron']
            
            uygun_user_ids = [
                r.user_id for r in UserTenantRole.query.filter(
                    UserTenantRole.tenant_id == session.get('tenant_id'),
                    UserTenantRole.role.in_(hedef_roller),
                    UserTenantRole.is_active == True
                ).all()
            ]
            
            # 2. Adım: Bu ID'lerin isimlerini Firebird'den çek
            if uygun_user_ids:
                yoneticiler = tenant_db.query(Kullanici).filter(
                    Kullanici.id.in_(uygun_user_ids),
                    Kullanici.aktif == True
                ).all()
                
                yonetici_opts += [(u.id, u.ad_soyad) for u in yoneticiler]
                
        except Exception as e:
            print(f"Yönetici Listesi Hatası: {e}")

    # ALANLAR
    kod = FormField('kod', FieldType.TEXT, _('Bölge Kodu'), required=True, value=bolge.kod if bolge else '')
    ad = FormField('ad', FieldType.TEXT, _('Bölge Adı'), required=True, value=bolge.ad if bolge else '')
    
    # Yönetici Seçimi
    yonetici_id = FormField('yonetici_id', FieldType.SELECT, _('Bölge Müdürü'), 
                            options=yonetici_opts, 
                            value=bolge.yonetici_id if bolge else '')

    aciklama = FormField('aciklama', FieldType.TEXTAREA, _('Açıklama'), value=bolge.aciklama if bolge else '')

    layout.add_row(kod, ad)
    layout.add_row(yonetici_id)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, yonetici_id, aciklama)
    
    return form