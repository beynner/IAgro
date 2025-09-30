#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import (
    get_duplicate_status, 
    should_auto_duplicate_item, 
    is_auto_duplicate_on_save_enabled,
    get_connection
)

print('=== INVESTIGAÇÃO NUNOTA 91715 ===')
print('Produto: 31')
print('Lote: 250930P536P31S01')
print()

# 1. Verificar configurações
print('1. CONFIGURAÇÕES:')
print('   Auto duplicate habilitado:', is_auto_duplicate_on_save_enabled())
print()

# 2. Verificar status do lote
print('2. STATUS DO LOTE:')
try:
    status = get_duplicate_status(91715)
    print('   Status:', status)
except Exception as e:
    print('   Erro:', e)
print()

# 3. Verificar se deveria duplicar
print('3. VERIFICAÇÃO DE DUPLICAÇÃO:')
try:
    check = should_auto_duplicate_item(91715, 31)
    print('   Deveria duplicar:', check)
except Exception as e:
    print('   Erro:', e)
print()

# 4. Verificar dados no banco
print('4. DADOS NO BANCO:')
try:
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Verificar TGFCAB
        cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=91715)
        cab = cur.fetchone()
        print('   TGFCAB - CODTIPOPER:', cab[0] if cab else 'NÃO ENCONTRADO')
        
        # Verificar TGFITE
        cur.execute("""
            SELECT CODPROD, CODAGREGACAO, NVL(GERAPRODUCAO, 'N') as GP 
            FROM TGFITE WHERE NUNOTA = :n
        """, n=91715)
        itens = cur.fetchall()
        print('   TGFITE - Itens:')
        for item in itens:
            print(f'     CODPROD: {item[0]}, LOTE: {item[1]}, GERAPRODUCAO: {item[2]}')
        
        # Verificar produto 31
        cur.execute("SELECT NVL(GERAPRODUCAO, 'N') FROM TGFPRO WHERE CODPROD = 31")
        prod = cur.fetchone()
        print('   TGFPRO - Produto 31 GERAPRODUCAO:', prod[0] if prod else 'NÃO ENCONTRADO')
        
        # Verificar se já existe TOP 26 para o lote
        cur.execute("""
            SELECT COUNT(*) FROM TGFITE i
            JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
            WHERE i.CODAGREGACAO = '250930P536P31S01' AND c.CODTIPOPER = 26
        """)
        existe = cur.fetchone()
        print('   TOP 26 já existe para este lote:', 'SIM' if existe[0] > 0 else 'NÃO')
        
except Exception as e:
    print('   Erro ao consultar banco:', e)