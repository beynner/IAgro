import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import modal_faturamento_auto_save

# Testar salvamento com novo valor
# Cenário: Digitar R$ 5,00/cx para 112 caixas
# VLRTOT = 5,00 × 112 = 560,00
# PRECOBASE esperado = 5,00

print("Testando salvamento com R$ 5,00/cx...")

result = modal_faturamento_auto_save(
    nunota_pedido=93180,
    sequencia=2,
    codprod=33,
    codagregacao='93180S02D251017',
    vlrtot=560.0,  # 5,00 × 112
    is_classificavel=False
)

print("\nResultado:", result)

if result.get('success'):
    print("\n✅ Salvamento bem-sucedido!")
    
    # Verificar no banco
    from sankhya_integration.services.oracle_conn import get_connection
    
    with get_connection() as conn:
        cur = conn.cursor()
        sql = """
            SELECT PRECOBASE, VLRUNIT, VLRTOT, QTDNEG
            FROM TGFITE
            WHERE NUNOTA = 93180 AND SEQUENCIA = 2
        """
        cur.execute(sql)
        row = cur.fetchone()
        
        if row:
            print(f"\nDados atualizados no banco:")
            print(f"  PRECOBASE: {row[0]}")
            print(f"  VLRUNIT: {row[1]}")
            print(f"  VLRTOT: {row[2]}")
            print(f"  QTDNEG: {row[3]}")
            
            precobase_esperado = 560.0 / 112.0
            print(f"\n  Esperado PRECOBASE: {precobase_esperado} (R$ 5,00/cx)")
            print(f"  Match: {abs(float(row[0]) - precobase_esperado) < 0.01}")
else:
    print(f"\n❌ Erro: {result.get('error')}")
