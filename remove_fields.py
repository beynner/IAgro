import re

file_path = 'sankhya_integration/templates/sankhya_integration/comercial_dashboard.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove bloco rates
pattern_rates = r'<div class="metric metric--double" data-block="rates">[\s\S]*?</div>\s*</div>'
content = re.sub(pattern_rates, '', content)

# Remove bloco total  
pattern_total = r'<div class="metric metric--currency" data-block="total">[\s\S]*?</div>\s*</div>'
content = re.sub(pattern_total, '', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ CAMPOS REMOVIDOS!')
