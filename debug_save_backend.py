"""Debug: Verificar se o backend está processando os campos AD_SIM* corretamente"""
from sankhya_integration.services.oracle_conn import get_connection

# Simular o que o backend recebe
print("=== SIMULAR PAYLOAD DO FRONTEND ===\n")

# Exemplo de payload que o frontend deveria enviar
payload_frontend = {
    'nunota': 91730,
    'sequencia': 1,
    'valor_total': 9000.0,
    'custo_kg': 3.588517,
    'custo_extra_total': 5500.75,
    'custo_medio_total': 3499.25,
    'custo_extra_kg': 2.5,
    'custo_medio_kg': 1.5,
    'sim_qtd1': 200.0,  # NOVO: extraCx
    'sim_vlr1': 5500.75,  # NOVO: extraCustoTotal
    'sim_qtd2': 100.0,  # NOVO: medioCx
    'sim_vlr2': 3499.25,  # NOVO: medioCustoTotal
}

print("Payload que o frontend envia:")
for k, v in payload_frontend.items():
    print(f"  {k}: {v}")

# Simular o que views.py faz
print("\n=== PROCESSAMENTO NO BACKEND (views.py) ===\n")

def _to_float_or(val):
    try:
        return float(val) if val is not None else None
    except Exception:
        return None

nunota = int(payload_frontend.get('nunota'))
sequencia = int(payload_frontend.get('sequencia'))
total = _to_float_or(payload_frontend.get('valor_total'))
custo_kg = _to_float_or(payload_frontend.get('custo_kg'))

# Extrair campos de simulação (como está no views.py)
sim_qtd1 = _to_float_or(payload_frontend.get('sim_qtd1'))
sim_vlr1 = _to_float_or(payload_frontend.get('sim_vlr1'))
sim_qtd2 = _to_float_or(payload_frontend.get('sim_qtd2'))
sim_vlr2 = _to_float_or(payload_frontend.get('sim_vlr2'))

print(f"Extraído do payload:")
print(f"  sim_qtd1: {sim_qtd1} (tipo: {type(sim_qtd1).__name__})")
print(f"  sim_vlr1: {sim_vlr1} (tipo: {type(sim_vlr1).__name__})")
print(f"  sim_qtd2: {sim_qtd2} (tipo: {type(sim_qtd2).__name__})")
print(f"  sim_vlr2: {sim_vlr2} (tipo: {type(sim_vlr2).__name__})")

# Montar update_payload (como está no views.py)
update_payload = {
    'NUNOTA': nunota,
    'SEQUENCIA': sequencia,
    'VLRUNIT': custo_kg,
    'VLRTOT': total,
    'AD_SIMQTD1': sim_qtd1,
    'AD_SIMVLR1': sim_vlr1,
    'AD_SIMQTD2': sim_qtd2,
    'AD_SIMVLR2': sim_vlr2,
}

print("\nupdate_payload montado:")
for k, v in update_payload.items():
    print(f"  {k}: {v}")

# Verificar se algum campo é None
campos_none = [k for k, v in update_payload.items() if v is None and k.startswith('AD_')]
if campos_none:
    print(f"\n⚠️  ATENÇÃO: Campos None: {campos_none}")
    print("   → Esses campos NÃO serão incluídos no UPDATE SQL")
else:
    print("\n✅ Todos os campos AD_SIM* têm valores válidos")

# Testar update_item
print("\n=== TESTAR update_item ===\n")
from sankhya_integration.services.oracle_conn import update_item

result = update_item(update_payload, dry_run=False)

print(f"Resultado:")
print(f"  ok: {result.get('ok')}")
print(f"  executed: {result.get('executed')}")
if result.get('errors'):
    print(f"  errors: {result.get('errors')}")
if result.get('warnings'):
    print(f"  warnings: {result.get('warnings')}")
if result.get('sql'):
    print(f"\n  SQL gerado:\n  {result.get('sql')}")

# Verificar valores salvos
print("\n=== VERIFICAR NO ORACLE ===\n")
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
        FROM TGFITE
        WHERE NUNOTA = :n AND SEQUENCIA = :s
    """, n=nunota, s=sequencia)
    row = cur.fetchone()
    
    if row:
        print(f"Valores no Oracle:")
        print(f"  AD_SIMQTD1: {row[0]} (esperado: 200)")
        print(f"  AD_SIMQTD2: {row[1]} (esperado: 100)")
        print(f"  AD_SIMVLR1: {row[2]} (esperado: 5500.75)")
        print(f"  AD_SIMVLR2: {row[3]} (esperado: 3499.25)")
        
        if row[0] == 200 and row[1] == 100:
            print("\n✅ Valores foram atualizados corretamente!")
        else:
            print("\n⚠️  Valores NÃO foram atualizados. Ainda são os valores do teste anterior.")
