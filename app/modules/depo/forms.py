# app/modules/depo/forms.py

from app.form_builder import Form, FormField, FieldType, FormLayout
from flask_babel import gettext as _
from flask_login import current_user
from flask import session
from app.extensions import get_tenant_db
# Modeller
from app.modules.sube.models import Sube
from app.modules.kullanici.models import Kullanici
from app.models.master import UserTenantRole # MySQL Rol Tablosu

def create_depo_form(depo=None):
    is_edit = depo is not None
    action_url = f"/depo/duzenle/{depo.id}" if is_edit else "/depo/ekle"
    title = _("Depo Düzenle") if is_edit else _("Yeni Depo")
    
    form = Form(name="depo_form", title=title, action=action_url, method="POST", submit_text=_("Kaydet"), ajax=True)
    layout = FormLayout()

    tenant_db = get_tenant_db()
    
    sube_opts = []
    plasiyer_opts = [(0, _('--- Yok (Merkez Depo) ---'))]

    if tenant_db:
        # 1. ŞUBELERİ GETİR (Firebird)
        try:
            subeler = tenant_db.query(Sube).filter_by(firma_id=1, aktif=True).all()
            sube_opts = [(s.id, s.ad) for s in subeler]
        except Exception as e:
            print(f"Depo Form Şube Hatası: {e}")

        # 2. PLASİYERLERİ GETİR (MySQL Rol -> Firebird İsim)
        try:
            # A) MySQL'den 'plasiyer' rolüne sahip ID'leri bul
            current_tenant_id = session.get('tenant_id')
            plasiyer_rolleri = UserTenantRole.query.filter(
                UserTenantRole.tenant_id == current_tenant_id,
                UserTenantRole.role == 'plasiyer',
                UserTenantRole.is_active == True
            ).all()
            
            plasiyer_ids = [r.user_id for r in plasiyer_rolleri]
            
            # B) Bu ID'lerin isimlerini Firebird'den çek
            if plasiyer_ids:
                users = tenant_db.query(Kullanici).filter(
                    Kullanici.id.in_(plasiyer_ids),
                    Kullanici.aktif == True
                ).all()
                
                plasiyer_opts += [(u.id, u.ad_soyad) for u in users]
                
        except Exception as e:
            print(f"Depo Form Plasiyer Hatası: {e}")

    # --- ALANLAR ---
    kod = FormField('kod', FieldType.TEXT, _('Depo Kodu'), required=True, value=depo.kod if depo else '', icon='bi bi-barcode')
    ad = FormField('ad', FieldType.TEXT, _('Depo Adı'), required=True, value=depo.ad if depo else '', icon='bi bi-box-seam')
    
    sube_id = FormField('sube_id', FieldType.SELECT, _('Bağlı Olduğu Şube'), 
                        options=sube_opts, required=True, 
                        value=depo.sube_id if depo else '',
                        select2_config={'placeholder': 'Şube Seçiniz'})

    plasiyer_id = FormField('plasiyer_id', FieldType.SELECT, _('Sorumlu Plasiyer (Araç Deposu İse)'), 
                            options=plasiyer_opts, 
                            value=depo.plasiyer_id if depo and depo.plasiyer_id else 0,
                            select2_config={'placeholder': 'Plasiyer Seçiniz'})

    aktif = FormField('aktif', FieldType.SWITCH, _('Aktif mi?'), value=depo.aktif if depo else True)

    # --- LAYOUT ---
    layout.add_row(kod, ad)
    layout.add_row(sube_id, plasiyer_id)
    layout.add_row(aktif)

    form.set_layout_html(layout.render())
    form.add_fields(kod, ad, sube_id, plasiyer_id, aktif)
    
    return form