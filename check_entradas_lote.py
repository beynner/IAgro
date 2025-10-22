"""
Script para verificar produtos nas entradas do lote 93295S01D251020
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
import django
django.setup()

from sankhya_integration.views import get_connection

def check_entradas():
    controle = '93295S01D251020'
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            print(f"\n=== Itens com CODAGREGACAO = '{controle}' ===\n")
            cur.execute("""
                SELECT 
                    i.NUNOTA,
                    i.SEQUENCIA,
                    i.CODPROD,
                    p.DESCRPROD,
                    i.CODAGREGACAO,
                    c.CODTIPOPER,
                    t.DESCROPER
                FROM TGFITE i
                JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                LEFT JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                LEFT JOIN TGFTOP t ON t.CODTIPOPER = c.CODTIPOPER
                WHERE i.CODAGREGACAO = :c
                ORDER BY c.CODTIPOPER, i.CODPROD
            """, c=controle)
            
            rows = cur.fetchall()
            if rows:
                print(f"{'NUNOTA':<10} {'SEQ':<5} {'CODPROD':<10} {'DESCRPROD':<40} {'TIPOPER':<8} {'DESCROPER':<30}")
                print("-" * 108)
                for row in rows:
                    innatura = ' ← IN NATURA' if row[3] and 'IN NATURA' in str(row[3]).upper() else ''
                    print(f"{row[0]:<10} {row[1]:<5} {row[2]:<10} {row[3][:40]:<40} {row[5]:<8} {row[6][:30] if row[6] else '':<30}{innatura}")
            else:
                print("Nenhum item encontrado com este CODAGREGACAO")
                
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_entradas()
