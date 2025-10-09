from sankhya_integration.services.oracle_conn import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT COLUMN_NAME 
        FROM ALL_TAB_COLUMNS 
        WHERE TABLE_NAME = 'TGFVOA' 
        AND OWNER = 'SANKHYA'
        ORDER BY COLUMN_ID
    """)
    
    print("Colunas da tabela TGFVOA:")
    print("=" * 50)
    for row in cur.fetchall():
        print(f"  • {row[0]}")
    
    cur.close()
