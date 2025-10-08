"""Testar save dos campos AD_SIM* para nunota 91730 sequencia 1"""
from sankhya_integration.services.oracle_conn import update_item, get_connection

print("=== TESTE: Salvar simulação para 91730/1 ===\n")

# Payload de teste
payload = {
    'NUNOTA': 91730,
    'SEQUENCIA': 1,
    'VLRUNIT': 3.588517,  # manter valor atual
    'VLRTOT': 9000.0,     # manter valor atual
    'AD_SIMQTD1': 100.5,  # extraCx (teste)
    'AD_SIMVLR1': 5500.75,  # extraCustoTotal (teste)
    'AD_SIMQTD2': 50.25,  # medioCx (teste)
    'AD_SIMVLR2': 3499.25,  # medioCustoTotal (teste)
}

print("Payload:")
for k, v in payload.items():
    print(f"  {k}: {v}")

print("\n--- Executando update_item (dry_run=False) ---")
result = update_item(payload, dry_run=False)

print("\nResultado:")
print(f"  ok: {result.get('ok')}")
print(f"  executed: {result.get('executed')}")
if result.get('errors'):
    print(f"  errors: {result.get('errors')}")
if result.get('warnings'):
    print(f"  warnings: {result.get('warnings')}")
if result.get('sql'):
    print(f"\n  SQL: {result.get('sql')}")
    print(f"  Binds: {result.get('binds')}")

# Verificar no Oracle
print("\n--- Verificando no Oracle ---")
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT VLRUNIT, VLRTOT, AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
        FROM TGFITE
        WHERE NUNOTA = 91730 AND SEQUENCIA = 1
    """)
    row = cur.fetchone()
    
    if row:
        print("Valores salvos:")
        print(f"  VLRUNIT:     {row[0]}")
        print(f"  VLRTOT:      {row[1]}")
        print(f"  AD_SIMQTD1:  {row[2]} (extraCx)")
        print(f"  AD_SIMQTD2:  {row[3]} (medioCx)")
        print(f"  AD_SIMVLR1:  {row[4]} (extraCustoTotal)")
        print(f"  AD_SIMVLR2:  {row[5]} (medioCustoTotal)")
        
        # Validar
        if row[2] == 100.5 and row[3] == 50.25 and row[4] == 5500.75 and row[5] == 3499.25:
            print("\n✅ TESTE PASSOU! Todos os valores foram salvos corretamente.")
        else:
            print("\n⚠️  TESTE FALHOU! Valores não correspondem.")
    else:
        print("❌ Item não encontrado após save!")
