"""
Verifica se a coluna NUMPEDIDO existe na tabela TGFCAB
"""
from sankhya_integration.services.oracle_conn import get_connection

try:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Verifica se a coluna existe
        cur.execute("""
            SELECT column_name, data_type, data_length, nullable
            FROM user_tab_columns
            WHERE table_name = 'TGFCAB'
            AND column_name LIKE '%PEDIDO%'
            ORDER BY column_name
        """)
        
        print("\n=== Colunas relacionadas a PEDIDO na TGFCAB ===")
        colunas = cur.fetchall()
        
        if colunas:
            for col_name, data_type, data_length, nullable in colunas:
                print(f"Coluna: {col_name}")
                print(f"  Tipo: {data_type}({data_length})")
                print(f"  Nullable: {nullable}")
                print()
        else:
            print("Nenhuma coluna com 'PEDIDO' encontrada!")
        
        # Verifica especificamente NUMPEDIDO
        cur.execute("""
            SELECT COUNT(*) 
            FROM user_tab_columns
            WHERE table_name = 'TGFCAB'
            AND column_name = 'NUMPEDIDO'
        """)
        
        existe = cur.fetchone()[0]
        
        if existe:
            print("✅ Coluna NUMPEDIDO existe na tabela TGFCAB")
        else:
            print("❌ Coluna NUMPEDIDO NÃO existe na tabela TGFCAB")
            print("\nVerificando todas as colunas com NUM...")
            
            cur.execute("""
                SELECT column_name, data_type, nullable
                FROM user_tab_columns
                WHERE table_name = 'TGFCAB'
                AND column_name LIKE 'NUM%'
                ORDER BY column_name
            """)
            
            for col_name, data_type, nullable in cur.fetchall():
                print(f"  {col_name} ({data_type}) - Nullable: {nullable}")
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
