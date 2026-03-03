# app/modules/efatura/forms.py
from app.form_builder import Form, FormField, FieldType, FormLayout

def create_entegrator_ayarlari_form(ayarlar=None):
    form = Form(name="entegrator_form", title="E-Fatura & Entegratör Ayarları", action="/efatura/ayarlar", method="POST", ajax=True)
    layout = FormLayout()
    
    provider_opts = [
        ('MOCK', 'Test Simülasyonu (Gönderim Yapmaz)'),
        ('UYUMSOFT', 'Uyumsoft E-Uyum API'),
        ('LOGO', 'Logo İşbaşı (Yakında)'),
        ('IZIBIZ', 'İzibiz (Yakında)')
    ]
    
    provider = FormField('provider', FieldType.SELECT, 'Entegratör Firması', options=provider_opts, required=True, value=ayarlar.provider if ayarlar else 'MOCK')
    username = FormField('username', FieldType.TEXT, 'API Kullanıcı Adı', required=True, value=ayarlar.username if ayarlar else '')
    password = FormField('password', FieldType.PASSWORD, 'API Şifresi', required=True, value=ayarlar.password if ayarlar else '')
    api_url = FormField('api_url', FieldType.TEXT, 'API Bağlantı URLsi', required=True, value=ayarlar.api_url if ayarlar else 'https://efatura.uyumsoft.com.tr/Services/Integration')
    
    gb = FormField('gb_etiketi', FieldType.TEXT, 'Gönderici Birim (GB) Etiketi', value=ayarlar.gb_etiketi if ayarlar else 'urn:mail:defaultgb@firma.com')
    pk = FormField('pk_etiketi', FieldType.TEXT, 'Posta Kutusu (PK) Etiketi', value=ayarlar.pk_etiketi if ayarlar else 'urn:mail:defaultpk@firma.com')
    aktif = FormField('aktif', FieldType.SWITCH, 'E-Dönüşüm Aktif', value=ayarlar.aktif if ayarlar else True)

    layout.add_row(provider, aktif)
    layout.add_row(username, password)
    layout.add_row(api_url)
    layout.add_html('<hr><small class="text-muted">GİB Etiket Bilgileri (Zorunlu Değilse Varsayılan Bırakın)</small>')
    layout.add_row(gb, pk)
    
    form.set_layout_html(layout.render())
    form.add_fields(provider, username, password, api_url, gb, pk, aktif)
    return form