#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

print('=== VERIFICAÇÃO RÁPIDA NUNOTA 91715 ===')

try:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # 1. Verificar TOP
        cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = 91715")
        top = cur.fetchone()
        print(f'TOP da nota: {top[0] if top else "NÃO ENCONTRADA"}')
        
        # 2. Verificar itens e GERAPRODUCAO
        cur.execute("""
            SELECT CODPROD, CODAGREGACAO, NVL(GERAPRODUCAO, 'N') as GP
            FROM TGFITE WHERE NUNOTA = 91715 ORDER BY SEQUENCIA
        """)
        itens = cur.fetchall()
        print(f'Itens na nota ({len(itens)}):')
        for item in itens:
            prod, lote, gp = item
            status = '✅ CLASSIFICA' if gp == 'S' else '❌ Não classifica'
            print(f'  CODPROD: {prod}, LOTE: {lote}, GERAPRODUCAO: {gp} - {status}')
        
        # 3. Verificar se já existe TOP 26 para o lote
        if itens:
            lote = itens[0][1]  # Primeiro lote
            cur.execute("""
                SELECT COUNT(*) FROM TGFITE i
                JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                WHERE i.CODAGREGACAO = :lote AND c.CODTIPOPER = 26
            """, lote=lote)
            existe_top26 = cur.fetchone()[0]
            print(f'TOP 26 já existe para lote {lote}: {"SIM" if existe_top26 > 0 else "NÃO"}')
            
except Exception as e:
    print(f'Erro: {e}')

print('=== FIM VERIFICAÇÃO ===')