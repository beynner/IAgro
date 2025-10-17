import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import modal_faturamento_auto_save

# Testar com dados reais
# Cenário: Item com QTDNEG=112 CX, usuário digita R$ 100/cx
# Sistema deve calcular: VLRTOT = 112 × 100 = 11200
# Backend deve recalcular: VLRUNIT = 11200 ÷ 112 = 100

result = modal_faturamento_auto_save(
    nunota_pedido=93180,
    sequencia=2,
    codprod=33,
    codagregacao='93180S02D251017',
    vlrtot=11200.0,  # VLRTOT = QTDNEG × valor_digitado
    is_classificavel=False
)

print("Resultado:", result)
print("\nValidação:")
print(f"  VLRUNIT calculado: {result.get('vlrunit')}")
print(f"  Esperado: 100.0 (11200 ÷ 112)")
print(f"  Correto: {abs(result.get('vlrunit', 0) - 100.0) < 0.01}")
