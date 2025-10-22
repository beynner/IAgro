from sankhya_integration.services.oracle_conn import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    
    # Buscar itens TOP 11 do lote 93295S01D251020
    cur.execute("""
        SELECT i.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.GERAPRODUCAO, c.CODTIPOPER
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
        WHERE i.CODAGREGACAO = '93295S01D251020'
          AND c.CODTIPOPER = 11
        ORDER BY i.NUNOTA, i.SEQUENCIA
    """)
    
    rows = cur.fetchall()
    print('\n=== ITENS TOP 11 (ENTRADA) DO LOTE 93295S01D251020 ===')
    for r in rows:
        print(f'NUNOTA: {r[0]}, SEQ: {r[1]}, CODPROD: {r[2]}, DESCR: {r[3]}, GERAPRODUCAO: {r[4]}, CODTIPOPER: {r[5]}')
    print(f'\nTotal: {len(rows)} itens')
    
    # Buscar itens TOP 26 do lote
    print('\n\n=== ITENS TOP 26 (CLASSIFICAÇÃO) DO LOTE 93295S01D251020 ===')
    cur.execute("""
        SELECT i.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, c.CODTIPOPER
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
        WHERE i.CODAGREGACAO = '93295S01D251020'
          AND c.CODTIPOPER = 26
        ORDER BY i.NUNOTA, i.SEQUENCIA
    """)
    
    rows = cur.fetchall()
    for r in rows:
        print(f'NUNOTA: {r[0]}, SEQ: {r[1]}, CODPROD: {r[2]}, DESCR: {r[3]}, CODTIPOPER: {r[4]}')
    print(f'\nTotal: {len(rows)} itens classificados')
