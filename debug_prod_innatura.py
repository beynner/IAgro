from sankhya_integration.services.oracle_conn import get_connection

controle = '9329S501D251020'

with get_connection() as conn:
    cur = conn.cursor()
    
    # Buscar TODOS os itens de entrada (TOP 11) deste lote
    print(f"\n{'='*80}")
    print(f"INVESTIGANDO CONTROLE: {controle}")
    print(f"{'='*80}\n")
    
    sql = """
        SELECT c.NUNOTA, 
               i.SEQUENCIA, 
               i.CODPROD, 
               p.DESCRPROD,
               NVL(i.GERAPRODUCAO, 'N') AS GERAPRODUCAO,
               c.CODTIPOPER
          FROM TGFITE i
          JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
          LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
         WHERE i.CODAGREGACAO = :c
           AND c.CODTIPOPER = 11
         ORDER BY c.NUNOTA DESC, i.SEQUENCIA
    """
    
    cur.execute(sql, c=controle)
    rows = cur.fetchall()
    
    print(f"Total de itens TOP 11 encontrados: {len(rows)}\n")
    
    for row in rows:
        nunota, seq, codprod, descr, gera, tipoper = row
        print(f"NUNOTA: {nunota} | SEQ: {seq} | CODPROD: {codprod} | GERAPRODUCAO: '{gera}' | DESCR: {descr}")
    
    print(f"\n{'='*80}")
    print("BUSCANDO PRODUTO COM GERAPRODUCAO = 'S'")
    print(f"{'='*80}\n")
    
    sql_gera = """
        SELECT CODPROD FROM (
          SELECT i.CODPROD
            FROM TGFITE i
            JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
           WHERE i.CODAGREGACAO = :c 
             AND c.CODTIPOPER = 11
             AND NVL(i.GERAPRODUCAO, 'N') = 'S'
           ORDER BY c.NUNOTA DESC, i.SEQUENCIA
        ) WHERE ROWNUM = 1
    """
    
    cur.execute(sql_gera, c=controle)
    row_gera = cur.fetchone()
    
    if row_gera:
        print(f"✅ PRODUTO ENCONTRADO COM GERAPRODUCAO='S': {row_gera[0]}")
        
        # Buscar detalhes desse produto
        cur.execute("SELECT CODPROD, DESCRPROD, FABRICANTE FROM TGFPRO WHERE CODPROD = :p", p=row_gera[0])
        prod_info = cur.fetchone()
        if prod_info:
            print(f"   CODPROD: {prod_info[0]}")
            print(f"   DESCRPROD: {prod_info[1]}")
            print(f"   FABRICANTE: {prod_info[2]}")
    else:
        print("❌ NENHUM PRODUTO COM GERAPRODUCAO='S' ENCONTRADO!")
        print("   Isso significa que nenhum item está marcado para classificação.")
    
    print(f"\n{'='*80}\n")
