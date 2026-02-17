# quick_fix_app.py

import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# initialize_extensions fonksiyonunu kaldır
pattern = r'def initialize_extensions\(app\):.*?(?=\ndef |\Z)'
content = re.sub(pattern, '', content, flags=re.DOTALL)

# initialize_extensions çağrısını kaldır
content = content.replace('initialize_extensions(app)', '# initialize_extensions(app) # REMOVED - duplicate!')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ app.py düzeltildi!")