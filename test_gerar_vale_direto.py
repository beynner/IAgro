"""
Testa diretamente a função gerar_vale_compra_top13_impl
"""
import sys
import os

# Forçar recarga dos módulos
if 'sankhya_integration.services.oracle_conn' in sys.modules:
    del sys.modules['sankhya_integration.services.oracle_conn']

from sankhya_integration.services.oracle_conn import gerar_vale_compra_top13_impl, get_connection

# Usar o pedido 92434 que tem itens classificados
nunota_pedido = 92434

# Buscar os itens do pedido
print(f"Buscando itens do pedido {nunota_pedido}...")

try:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT SEQUENCIA, VLRUNIT, QTDNEG
            FROM TGFITE
            WHERE NUNOTA = :n
            ORDER BY SEQUENCIA
        """, n=nunota_pedido)
        
        itens = []
        for seq, vlrunit, qtdneg in cur.fetchall():
            preco = float(vlrunit) if vlrunit else 100.0
            itens.append({'sequencia': seq, 'preco': preco})
            print(f"  Item SEQ={seq}, PRECO={preco}, QTDNEG={qtdneg}")
        
        if not itens:
            print("❌ Nenhum item encontrado!")
            sys.exit(1)
        
        print(f"\nChamando gerar_vale_compra_top13_impl...")
        print(f"  nunota_11: {nunota_pedido}")
        print(f"  itens_precos: {itens}")
        print()
        
        # Chamar a função
        resultado = gerar_vale_compra_top13_impl(nunota_pedido, itens)
        
        print(f"\n=== Resultado ===")
        print(f"OK: {resultado.get('ok')}")
        
        if resultado.get('ok'):
            nunota_vale = resultado.get('nunota_13')
            print(f"Vale criado: NUNOTA={nunota_vale}")
            
            # Verificar se NUMPEDIDO foi gravado
            cur.execute("""
                SELECT NUMPEDIDO
                FROM TGFCAB
                WHERE NUNOTA = :n
            """, n=nunota_vale)
            
            row = cur.fetchone()
            numpedido = row[0] if row else None
            
            if numpedido:
                print(f"✅ NUMPEDIDO gravado: {numpedido}")
            else:
                print(f"❌ NUMPEDIDO está NULL/vazio")
        else:
            print(f"Erro: {resultado.get('error')}")
            if 'details' in resultado:
                print(f"Detalhes: {resultado['details']}")
            
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
