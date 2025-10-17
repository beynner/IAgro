"""
Script para verificar o VLRTOT no banco de dados
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

# NUNOTA que você está testando
NUNOTA = 93227

print(f"\n{'='*60}")
print(f"Verificando VLRTOT para NUNOTA {NUNOTA}")
print(f"{'='*60}\n")

with get_connection() as conn:
    cur = conn.cursor()
    
    # Query completa igual à usada em listar_itens_portal_basico
    sql = """
        SELECT 
            i.NUNOTA,
            i.SEQUENCIA,
            i.CODPROD,
            pr.DESCRPROD,
            i.QTDNEG,
            i.PRECOBASE,
            i.VLRUNIT,
            i.VLRTOT,
            i.AD_SIMQTD1,
            i.AD_SIMQTD2,
            i.AD_SIMVLR1,
            i.AD_SIMVLR2
        FROM TGFITE i
        LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
        WHERE i.NUNOTA = :nunota
        ORDER BY i.SEQUENCIA
    """
    
    cur.execute(sql, {'nunota': NUNOTA})
    
    rows = cur.fetchall()
    
    if not rows:
        print(f"❌ Nenhum item encontrado para NUNOTA {NUNOTA}")
    else:
        print(f"✅ Encontrados {len(rows)} item(ns):\n")
        
        for row in rows:
            nunota, seq, codprod, descr, qtdneg, precobase, vlrunit, vlrtot, simqtd1, simqtd2, simvlr1, simvlr2 = row
            
            print(f"Item {seq}:")
            print(f"  CODPROD: {codprod}")
            print(f"  PRODUTO: {descr}")
            print(f"  QTDNEG: {qtdneg}")
            print(f"  PRECOBASE: {precobase}")
            print(f"  VLRUNIT: {vlrunit}")
            print(f"  ⭐ VLRTOT: {vlrtot} ⭐")
            print(f"  AD_SIMQTD1: {simqtd1}")
            print(f"  AD_SIMQTD2: {simqtd2}")
            print(f"  AD_SIMVLR1: {simvlr1}")
            print(f"  AD_SIMVLR2: {simvlr2}")
            print()
            
            if vlrtot is None or vlrtot == 0:
                print(f"  ⚠️  VLRTOT está NULL ou ZERO no banco!")
            else:
                print(f"  ✅ VLRTOT = {vlrtot}")
            print()

print(f"{'='*60}\n")
