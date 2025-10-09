"""
Deleta o vale 92448 para poder testar novamente
"""
from sankhya_integration.services.oracle_conn import get_connection

nunota_vale = 92448

try:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Deletar itens primeiro
        cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n", n=nunota_vale)
        itens_deleted = cur.rowcount
        print(f"Deletados {itens_deleted} itens")
        
        # Deletar cabeçalho
        cur.execute("DELETE FROM TGFCAB WHERE NUNOTA = :n", n=nunota_vale)
        cab_deleted = cur.rowcount
        print(f"Deletado {cab_deleted} cabeçalho")
        
        conn.commit()
        print(f"\n✅ Vale {nunota_vale} deletado com sucesso!")
        
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
