#!/usr/bin/env python3
"""
Investigar especificamente os itens da NUNOTA 91715
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

print("=== ANÁLISE DETALHADA NUNOTA 91715 ===")

try:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # 1. Verificar TOP
        cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = 91715")
        result = cur.fetchone()
        print(f"TOP da nota: {result[0] if result else 'NÃO ENCONTRADA'}")
        
        # 2. Verificar TODOS os itens
        cur.execute("""
            SELECT SEQUENCIA, CODPROD, CODAGREGACAO, 
                   NVL(GERAPRODUCAO, 'N') as GP,
                   QTDNEG, VLRUNIT
            FROM TGFITE 
            WHERE NUNOTA = 91715 
            ORDER BY SEQUENCIA
        """)
        
        itens = cur.fetchall()
        print(f"\nItens encontrados: {len(itens)}")
        
        classificaveis = 0
        for item in itens:
            seq, cod, lote, gp, qtd, vlr = item
            status = "✅ CLASSIFICA" if gp == 'S' else "❌ NÃO CLASSIFICA"
            print(f"  SEQ: {seq}, PROD: {cod}, LOTE: {lote}, GP: '{gp}', QTD: {qtd} - {status}")
            if gp == 'S':
                classificaveis += 1
        
        print(f"\nTotal classificáveis: {classificaveis}")
        
        # 3. Se existe produto 31, verificar especificamente
        cur.execute("""
            SELECT SEQUENCIA, CODAGREGACAO, NVL(GERAPRODUCAO, 'N') as GP
            FROM TGFITE 
            WHERE NUNOTA = 91715 AND CODPROD = 31
        """)
        
        prod31 = cur.fetchall()
        if prod31:
            print(f"\nProduto 31 encontrado:")
            for item in prod31:
                seq, lote, gp = item
                print(f"  SEQ: {seq}, LOTE: {lote}, GERAPRODUCAO: '{gp}'")
        else:
            print(f"\nProduto 31 NÃO encontrado na NUNOTA 91715")

except Exception as e:
    print(f"Erro: {e}")

print("\n=== CONCLUSÃO ===")
print("Se classificaveis = 0, então nenhum item tem GERAPRODUCAO='S'")
print("Para duplicar automaticamente, precisa ter GERAPRODUCAO='S' no item")
print("Verifique se o item foi salvo com GERAPRODUCAO='S' via Portal")