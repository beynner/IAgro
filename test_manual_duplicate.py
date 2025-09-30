import subprocess
import json

print("=== TESTE MANUAL DE DUPLICAÇÃO ===")
print("NUNOTA: 91715")
print("Produto: 31")
print("Lote: 250930P536P31S01")
print()

# Testar via curl
cmd = [
    'curl', '-X', 'POST', 
    'http://localhost:8000/sankhya/duplicate/classification/',
    '-H', 'Content-Type: application/json',
    '-d', json.dumps({'nunota_11': 91715, 'dry_run': True})
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    print("Status Code:", result.returncode)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
except Exception as e:
    print("Erro:", e)