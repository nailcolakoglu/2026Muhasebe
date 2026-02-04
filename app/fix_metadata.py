# fix_metadata.py (Tek seferlik düzeltme scripti)
# Eğer her dosyayı manuel düzeltmek istemiyorsan:


import os
import re

files = [
    'models/master/user.py',
    'models/master/tenant.py',
    'models/master/license.py',
    'models/master/audit.py'
]

for file_path in files:
    if not os.path.exists(file_path):
        print(f"❌ {file_path} bulunamadı")
        continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # __bind_key__ satırından sonra metadata ekle
    if 'metadata = db.metadata' not in content:
        content = re.sub(
            r"(__bind_key__ = '[^']+'\s*\n)",
            r"\1    \n    # Metadata\n    metadata = db.metadata\n",
            content
        )
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ {file_path} düzeltildi")
    else:
        print(f"⏭️  {file_path} zaten düzeltilmiş")

print("\n✅ Tüm dosyalar düzeltildi!")