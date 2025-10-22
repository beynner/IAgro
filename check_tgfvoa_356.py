"""
Script para verificar volumes cadastrados em TGFVOA para produto 356
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
import django
django.setup()

from sankhya_integration.views import get_connection

def check_volumes():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Buscar todos os volumes do produto 356 em TGFVOA
            print("\n=== Volumes cadastrados em TGFVOA para produto 356 ===")
            cur.execute("""
                SELECT CODPROD, CODVOL, QUANTIDADE 
                FROM TGFVOA 
                WHERE CODPROD = 356
                ORDER BY CODVOL
            """)
            
            rows = cur.fetchall()
            if rows:
                print(f"\nEncontrados {len(rows)} volume(s):\n")
                print(f"{'CODPROD':<10} {'CODVOL':<10} {'QUANTIDADE (Peso)':<20}")
                print("-" * 40)
                for row in rows:
                    print(f"{row[0]:<10} {row[1]:<10} {row[2]:<20}")
            else:
                print("\nNenhum volume encontrado em TGFVOA para produto 356")
            
            # Buscar volume base do produto
            print("\n=== Volume base do produto em TGFPRO ===")
            cur.execute("""
                SELECT CODPROD, DESCRPROD, CODVOL 
                FROM TGFPRO 
                WHERE CODPROD = 356
            """)
            
            prod_row = cur.fetchone()
            if prod_row:
                print(f"\nProduto: {prod_row[0]} - {prod_row[1]}")
                print(f"Volume base (CODVOL): {prod_row[2]}")
                print(f"\nNota: Volume base sempre tem peso = 1.0")
            else:
                print("\nProduto 356 não encontrado em TGFPRO")
                
    except Exception as e:
        print(f"\nErro ao consultar banco: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_volumes()
