from sankhya_integration.services.oracle_conn import get_connection

with get_connection() as conn:
    cur = conn.cursor()

    # Buscar dados do item
    cur.execute("""
        SELECT NUNOTA, SEQUENCIA, CODPROD, QTDNEG, VLRUNIT, VLRTOT, 
               CODVOL, CODLOCALORIG, CONTROLE, CODAGREGACAO
        FROM TGFITE 
        WHERE NUNOTA = 92434 AND SEQUENCIA = 1
    """)

    cols = [d[0] for d in cur.description]
    row = cur.fetchone()

    if row:
        print("=" * 60)
        print("CONFERÊNCIA ITEM - NUNOTA 92434 SEQ 1")
        print("=" * 60)
        for i in range(len(cols)):
            print(f"{cols[i]:20s}: {row[i]}")
        
        # Buscar dados do cabeçalho
        print("\n" + "=" * 60)
        print("DADOS DO CABEÇALHO")
        print("=" * 60)
        
        cur.execute("""
            SELECT NUNOTA, DTNEG, DTFATUR, STATUSNOTA, PENDENTE, TIPMOV,
                   CODTIPOPER, CODPARC, VLRNOTA, CODTIPVENDA
            FROM TGFCAB
            WHERE NUNOTA = 92434
        """)
        
        cols_cab = [d[0] for d in cur.description]
        row_cab = cur.fetchone()
        
        if row_cab:
            for i in range(len(cols_cab)):
                print(f"{cols_cab[i]:20s}: {row_cab[i]}")
        
        # Verificar se há mais itens nesta nota
        cur.execute("SELECT COUNT(*) FROM TGFITE WHERE NUNOTA = 92434")
        total_itens = cur.fetchone()[0]
        
        print("\n" + "=" * 60)
        print(f"TOTAL DE ITENS NA NOTA: {total_itens}")
        print("=" * 60)
        
        # Se houver mais itens, listar resumo
        if total_itens > 1:
            cur.execute("""
                SELECT SEQUENCIA, CODPROD, QTDNEG, VLRTOT
                FROM TGFITE
                WHERE NUNOTA = 92434
                ORDER BY SEQUENCIA
            """)
            print("\nRESUMO DE TODOS OS ITENS:")
            print(f"{'SEQ':>5} {'PRODUTO':>10} {'QTDE':>12} {'VALOR TOTAL':>15}")
            print("-" * 50)
            for item in cur.fetchall():
                print(f"{item[0]:>5} {item[1]:>10} {item[2]:>12.2f} {item[3]:>15.2f}")
        
    else:
        print("Item não encontrado: NUNOTA 92434 SEQ 1")

    cur.close()
