"""Verificar dados do item nunota 91730 sequencia 1"""
from sankhya_integration.services.oracle_conn import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    
    # Verificar item TGFITE
    cur.execute("""
        SELECT NUNOTA, SEQUENCIA, CODPROD, QTDNEG, CODVOL, PESO, PRECOBASE,
               VLRUNIT, VLRTOT, 
               AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2
        FROM TGFITE 
        WHERE NUNOTA = 91730 AND SEQUENCIA = 1
    """)
    
    row = cur.fetchone()
    
    if row:
        print("=== ITEM TGFITE 91730/1 ===")
        print(f"NUNOTA:      {row[0]}")
        print(f"SEQUENCIA:   {row[1]}")
        print(f"CODPROD:     {row[2]}")
        print(f"QTDNEG:      {row[3]}")
        print(f"CODVOL:      {row[4]}")
        print(f"PESO:        {row[5]}")
        print(f"PRECOBASE:   {row[6]}")
        print(f"\n--- Campos Gerais ---")
        print(f"VLRUNIT:     {row[7]}")
        print(f"VLRTOT:      {row[8]}")
        print(f"\n--- Campos Simulação ---")
        print(f"AD_SIMQTD1:  {row[9]} (extraCx)")
        print(f"AD_SIMQTD2:  {row[10]} (medioCx)")
        print(f"AD_SIMVLR1:  {row[11]} (extraCustoTotal)")
        print(f"AD_SIMVLR2:  {row[12]} (medioCustoTotal)")
        
        # Verificar se colunas existem e tem valores
        if row[9] is None and row[10] is None and row[11] is None and row[12] is None:
            print("\n⚠️  TODAS as colunas AD_SIM* estão NULL")
        else:
            print("\n✅ Pelo menos uma coluna AD_SIM* tem valor")
            
    else:
        print("❌ Item não encontrado: NUNOTA=91730, SEQUENCIA=1")
    
    # Verificar se as colunas existem na tabela
    print("\n=== VERIFICAR SE COLUNAS EXISTEM ===")
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, NULLABLE
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = 'TGFITE'
        AND COLUMN_NAME IN ('AD_SIMQTD1', 'AD_SIMQTD2', 'AD_SIMVLR1', 'AD_SIMVLR2')
        ORDER BY COLUMN_NAME
    """)
    
    cols = cur.fetchall()
    if cols:
        print("Colunas encontradas:")
        for col in cols:
            print(f"  - {col[0]}: {col[1]} (NULL: {col[2]})")
    else:
        print("❌ COLUNAS AD_SIM* NÃO EXISTEM NA TABELA TGFITE!")
