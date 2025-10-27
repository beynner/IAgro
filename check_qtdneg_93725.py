#!/usr/bin/env python
"""
Script para verificar QTDNEG dos itens da nota 93725
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
import django
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

nunota = 93725

print(f"\n{'='*80}")
print(f"🔍 VERIFICANDO ITENS DA NOTA {nunota}")
print(f"{'='*80}\n")

sql = """
    SELECT 
        i.SEQUENCIA,
        i.CODPROD,
        pr.DESCRPROD,
        i.CODVOL,
        i.QTDNEG,
        i.PESO,
        i.VLRUNIT,
        i.VLRTOT,
        i.CODAGREGACAO
    FROM TGFITE i
    LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
    WHERE i.NUNOTA = :nunota
    ORDER BY i.SEQUENCIA
"""

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute(sql, nunota=nunota)
    rows = cur.fetchall()
    
    if not rows:
        print(f"❌ Nenhum item encontrado para NUNOTA {nunota}")
    else:
        print(f"✅ Encontrados {len(rows)} itens:\n")
        
        for row in rows:
            seq, codprod, descr, codvol, qtdneg, peso, vlrunit, vlrtot, lote = row
            
            print(f"📦 ITEM SEQUENCIA {seq}")
            print(f"   ├─ Produto: {codprod} - {descr}")
            print(f"   ├─ Lote: {lote}")
            print(f"   ├─ CODVOL: {codvol}")
            print(f"   ├─ QTDNEG (banco): {qtdneg} KG")
            print(f"   ├─ PESO: {peso} kg/unidade")
            print(f"   ├─ VLRUNIT: R$ {vlrunit:.2f}")
            print(f"   └─ VLRTOT: R$ {vlrtot:.2f}")
            
            # Calcular conversão
            if codvol and codvol.upper() != 'KG' and peso and float(peso) > 0:
                qtd_convertida = float(qtdneg) / float(peso)
                print(f"   └─ 🔄 Conversão: {qtdneg} KG ÷ {peso} = {qtd_convertida:.2f} {codvol}")
            
            print()

print(f"{'='*80}\n")
