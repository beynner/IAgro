import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

# Verificar se PRECOBASE está sendo atualizado
nunota = 93180
sequencia = 2

with get_connection() as conn:
    cur = conn.cursor()
    
    # Buscar item atual
    sql = """
        SELECT CODPROD, QTDNEG, PRECOBASE, VLRUNIT, VLRTOT
        FROM TGFITE
        WHERE NUNOTA = :n AND SEQUENCIA = :s
    """
    cur.execute(sql, n=nunota, s=sequencia)
    row = cur.fetchone()
    
    if row:
        print(f"Item atual:")
        print(f"  CODPROD: {row[0]}")
        print(f"  QTDNEG: {row[1]}")
        print(f"  PRECOBASE: {row[2]}")
        print(f"  VLRUNIT: {row[3]}")
        print(f"  VLRTOT: {row[4]}")
        
        qtdneg = float(row[1])
        vlrtot = float(row[4]) if row[4] else 0
        
        if qtdneg > 0 and vlrtot > 0:
            precobase_esperado = vlrtot / qtdneg
            print(f"\nPRECOBASE esperado (VLRTOT/QTDNEG): {precobase_esperado}")
            print(f"PRECOBASE atual: {row[2]}")
            print(f"Match: {abs(float(row[2] or 0) - precobase_esperado) < 0.01}")
    else:
        print("Item não encontrado")
