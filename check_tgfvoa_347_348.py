from sankhya_integration.services.oracle_conn import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    
    # Verificar TGFVOA para produtos classificados
    cur.execute("""
        SELECT v.CODPROD, v.CODVOL, v.QUANTIDADE, v.DIVIDEMULTIPLICA,
               p.DESCRPROD, p.CODVOL AS CODVOL_BASE
        FROM TGFVOA v
        JOIN TGFPRO p ON p.CODPROD = v.CODPROD
        WHERE v.CODPROD IN (347, 348)
        ORDER BY v.CODPROD, v.CODVOL
    """)
    
    print("=" * 100)
    print("TGFVOA - Relações de Volume para Produtos Classificados")
    print("=" * 100)
    print(f"{'PROD':>6} {'DESCRIÇÃO':30} {'VOL':>4} {'QTD':>10} {'D/M':>3} {'BASE':>8}")
    print("-" * 100)
    
    for row in cur.fetchall():
        codprod, codvol, qtd, div_mult, descr, codvol_base = row
        print(f"{codprod:>6} {(descr or '')[:30]:30} {(codvol or ''):>4} {(qtd or 0):>10.4f} {(div_mult or ''):>3} {(codvol_base or ''):>8}")
    
    print("=" * 100)
    
    cur.close()
