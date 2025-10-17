"""
Script para verificar o VLRTOT no VALE (TOP 13) vinculado ao PEDIDO
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

# NUNOTA do PEDIDO (TOP 11)
NUNOTA_PEDIDO = 93227

print(f"\n{'='*60}")
print(f"Verificando VALE vinculado ao PEDIDO {NUNOTA_PEDIDO}")
print(f"{'='*60}\n")

with get_connection() as conn:
    cur = conn.cursor()
    
    # 1. Buscar VALE (TOP 13) vinculado ao PEDIDO via NUMPEDIDO
    sql_vale = """
        SELECT NUNOTA, NUMPEDIDO, CODTIPOPER
        FROM TGFCAB
        WHERE CODTIPOPER = 13
          AND NUMPEDIDO = :nunota_pedido
    """
    
    cur.execute(sql_vale, {'nunota_pedido': NUNOTA_PEDIDO})
    vale_row = cur.fetchone()
    
    if not vale_row:
        print(f"❌ Nenhum VALE (TOP 13) encontrado vinculado ao PEDIDO {NUNOTA_PEDIDO}")
        print(f"   (NUMPEDIDO = {NUNOTA_PEDIDO})")
    else:
        nunota_vale, numpedido, codtipoper = vale_row
        print(f"✅ VALE encontrado:")
        print(f"   NUNOTA do VALE: {nunota_vale}")
        print(f"   NUMPEDIDO (ref): {numpedido}")
        print(f"   CODTIPOPER: {codtipoper}\n")
        
        # 2. Buscar itens do VALE
        sql_items = """
            SELECT 
                i.NUNOTA,
                i.SEQUENCIA,
                i.CODPROD,
                pr.DESCRPROD,
                i.QTDNEG,
                i.PRECOBASE,
                i.VLRUNIT,
                i.VLRTOT
            FROM TGFITE i
            LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
            WHERE i.NUNOTA = :nunota_vale
            ORDER BY i.SEQUENCIA
        """
        
        cur.execute(sql_items, {'nunota_vale': nunota_vale})
        items = cur.fetchall()
        
        if not items:
            print(f"⚠️  VALE {nunota_vale} não tem itens")
        else:
            print(f"✅ VALE tem {len(items)} item(ns):\n")
            
            for item in items:
                nunota, seq, codprod, descr, qtdneg, precobase, vlrunit, vlrtot = item
                
                print(f"Item {seq}:")
                print(f"  CODPROD: {codprod}")
                print(f"  PRODUTO: {descr}")
                print(f"  QTDNEG: {qtdneg}")
                print(f"  PRECOBASE: {precobase}")
                print(f"  VLRUNIT: {vlrunit}")
                print(f"  ⭐ VLRTOT: {vlrtot} ⭐")
                print()
                
                if vlrtot and vlrtot > 0:
                    print(f"  ✅ VLRTOT do VALE = {vlrtot}")
                else:
                    print(f"  ⚠️  VLRTOT está NULL ou ZERO no VALE")
                print()

print(f"{'='*60}\n")
