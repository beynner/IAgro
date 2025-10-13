import base64
from PIL import Image
import io

# Abrir logo SEM FUNDO
img = Image.open('images/logoSemFundo.png')
print(f"Tamanho original: {img.size}")

# Redimensionar para 300px de largura (proporcional)
max_width = 300
ratio = max_width / img.width
new_height = int(img.height * ratio)
img_resized = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
print(f"Tamanho redimensionado: {img_resized.size}")

# Converter para base64
buffer = io.BytesIO()
img_resized.save(buffer, format='PNG', optimize=True)
img_bytes = buffer.getvalue()
base64_str = base64.b64encode(img_bytes).decode()

print(f"\nTamanho base64: {len(base64_str)} caracteres")
print(f"\nConstante JavaScript:")
print(f"const LOGO_BASE64_EMBED = 'data:image/png;base64,{base64_str[:100]}...';\n")

# Salvar em arquivo
with open('logoSemFundo_base64_constant.txt', 'w') as f:
    f.write(f"const LOGO_BASE64_EMBED = 'data:image/png;base64,{base64_str}';")

print("✅ Salvo em: logoSemFundo_base64_constant.txt")
