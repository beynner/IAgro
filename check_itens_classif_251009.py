from sankhya_integration.services.oracle_conn import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    
    # Buscar itens classificados do lote 251009P536P27S01
    cur.execute("""
        SELECT i.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, 
               i.QTDNEG, i.CODVOL, pp.CODVOL AS CODVOL_BASE,
               c.CODTIPOPER, c.STATUSNOTA
        FROM TGFITE i
        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
        LEFT JOIN TGFPRO pp ON pp.CODPROD = i.CODPROD
        WHERE i.CODAGREGACAO = '251009P536P27S01'
          AND c.CODTIPOPER = 26
        ORDER BY i.NUNOTA, i.SEQUENCIA
    """)
    
    print("=" * 100)
    print("ITENS CLASSIFICADOS (TOP 26) - Lote 251009P536P27S01")
    print("=" * 100)
    print(f"{'NUNOTA':>8} {'SEQ':>4} {'PROD':>6} {'DESCRIÇÃO':30} {'QTDNEG':>10} {'VOL':>4} {'VOL_BASE':>8} {'TOP':>4} {'ST':>2}")
    print("-" * 100)
    
    total_qtd = 0
    for row in cur.fetchall():
        nunota, seq, codprod, descr, qtdneg, codvol, codvol_base, top, status = row
        print(f"{nunota:>8} {seq:>4} {codprod:>6} {(descr or '')[:30]:30} {qtdneg:>10.2f} {(codvol or ''):>4} {(codvol_base or ''):>8} {top:>4} {(status or ''):>2}")
        if codvol and codvol.upper() == 'CX':
            total_qtd += qtdneg
    
    print("-" * 100)
    print(f"TOTAL DE CAIXAS (CX): {total_qtd:.2f}")
    print("=" * 100)
    
    cur.close()
