# app/modules/bolge/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from flask import session
from app.extensions import get_tenant_db, db  # ✅ db=MySQL master, get_tenant_db=MySQL tenant
from app.modules.kullanici.models import Kullanici
from app.models.master import UserTenantRole
import logging

logger = logging.getLogger(__name__)


def create_bolge_form(bolge=None):
    """Bölge formu oluşturur"""
    is_edit = bolge is not None
    action_url = f"/bolge/duzenle/{bolge.id}" if is_edit else "/bolge/ekle"
    title = _("Bölge Tanımı")
    
    form = Form(
        name="bolge_form", 
        title=title, 
        action=action_url, 
        method="POST", 
        submit_text=_("Kaydet"), 
        ajax=True
    )
    layout = FormLayout()

    # --- YÖNETİCİ LİSTESİ ---
    yonetici_opts = [('', _('Seçiniz...'))]
    
    tenant_db = get_tenant_db()
    if tenant_db:
        try:
            # 1. MySQL Master'dan rolü olan kullanıcıları bul
            hedef_roller = ['bolge_muduru', 'admin', 'patron']
            
            uygun_user_ids = [
                r.user_id for r in UserTenantRole.query.filter(
                    UserTenantRole.tenant_id == session.get('tenant_id'),
                    UserTenantRole.role.in_(hedef_roller),
                    UserTenantRole.is_active == True
                ).all()
            ]
            
            # 2. Tenant DB'den bu kullanıcıların bilgilerini çek
            if uygun_user_ids:
                yoneticiler = tenant_db.query(Kullanici).filter(
                    Kullanici.id.in_(uygun_user_ids),
                    Kullanici.aktif == True
                ).all()
                
                yonetici_opts += [(str(u.id), u.ad_soyad) for u in yoneticiler]
                
        except Exception as e:
            logger.error(f"Yönetici Listesi Hatası: {e}", exc_info=True)

    # FORM ALANLARI
    kod = FormField(
        'kod', 
        FieldType.TEXT, 
        _('Bölge Kodu'), 
        required=True, 
        value=bolge.kod if bolge else ''
    )
    
    ad = FormField(
        'ad', 
        FieldType.TEXT, 
        _('Bölge Adı'), 
        required=True, 
        value=bolge.ad if bolge else ''
    )
    
    yonetici_id = FormField(
        'yonetici_id', 
        FieldType.SELECT, 
        _('Bölge Müdürü'), 
        options=yonetici_opts, 
        value=str(bolge.yonetici_id) if bolge and bolge.yonetici_id else ''
    )

    aciklama = FormField(
        'aciklama', 
        FieldType.TEXTAREA, 
        _('Açıklama'), 
        value=bolge.aciklama if bolge else ''
    )

    layout.add_row(kod, ad)
    layout.add_row(yonetici_id)
    layout.add_row(aciklama)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, yonetici_id, aciklama)
    
    return form