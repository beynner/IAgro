"""
Testa a geração de vale e verifica se NUMPEDIDO está sendo gravado
"""
from sankhya_integration.services.oracle_conn import get_connection

# NUNOTA do vale que foi criado
nunota_vale = 92448

try:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Busca informações do vale
        cur.execute("""
            SELECT NUNOTA, CODTIPOPER, NUMNOTA, NUMPEDIDO, CODPARC
            FROM TGFCAB 
            WHERE NUNOTA = :n
        """, n=nunota_vale)
        
        row = cur.fetchone()
        
        if row:
            nunota, codtipoper, numnota, numpedido, codparc = row
            print(f"\n=== Vale NUNOTA {nunota} ===")
            print(f"CODTIPOPER: {codtipoper}")
            print(f"NUMNOTA: {numnota}")
            print(f"NUMPEDIDO: {numpedido if numpedido else 'NULL/VAZIO ❌'}")
            print(f"CODPARC: {codparc}")
            
            if numpedido:
                print(f"\n✅ NUMPEDIDO foi gravado: {numpedido}")
                
                # Tenta encontrar o pedido original
                cur.execute("""
                    SELECT NUNOTA, CODTIPOPER
                    FROM TGFCAB
                    WHERE NUMNOTA = :n OR NUNOTA = :n
                """, n=numpedido)
                
                pedido_row = cur.fetchone()
                if pedido_row:
                    print(f"   Pedido original encontrado: NUNOTA={pedido_row[0]}, TOP={pedido_row[1]}")
            else:
                print(f"\n❌ NUMPEDIDO está vazio!")
                print("\nInvestigando o problema...")
                
                # Verifica se a coluna existe e está acessível
                cur.execute("""
                    SELECT column_name, data_type, nullable
                    FROM user_tab_columns
                    WHERE table_name = 'TGFCAB'
                    AND column_name = 'NUMPEDIDO'
                """)
                
                col_info = cur.fetchone()
                if col_info:
                    print(f"   Coluna NUMPEDIDO existe: {col_info[0]} ({col_info[1]}) - Nullable: {col_info[2]}")
                else:
                    print("   ⚠️  Coluna NUMPEDIDO não encontrada!")
        else:
            print(f"Vale NUNOTA {nunota_vale} não encontrado!")
            
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
