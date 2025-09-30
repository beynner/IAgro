#!/usr/bin/env python3
"""
Investigar NUNOTA 91730 - Por que segundo produto nao aparece na classificacao
"""

import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
    django.setup()

from sankhya_integration.services.oracle_conn import get_connection, get_params

def investigar_nunota_91730():
    """Investiga a NUNOTA 91730 e verifica por que o segundo produto nao aparece."""
    nunota_11 = 91730
    params = get_params()
    TOP_ENTRADA = params['TOP_ENTRADA']  # 11
    TOP_CLASS = params['TOP_CLASS']      # 26

    print(f"INVESTIGANDO NUNOTA {nunota_11}")
    print("=" * 60)

    with get_connection() as conn:
        cur = conn.cursor()
        
        # 1. Verificar TOP 11
        print("\n1. TOP 11 (Portal):")
        cur.execute("""
            SELECT c.NUNOTA, c.CODTIPOPER, c.STATUSNOTA, c.DTMOV, c.CODPARC
            FROM TGFCAB c 
            WHERE c.NUNOTA = :n
        """, n=nunota_11)
        
        cab_data = cur.fetchone()
        if not cab_data:
            print("   ERRO: NUNOTA nao encontrada!")
            return
            
        nunota, codtipoper, statusnota, dtmov, codparc = cab_data
        print(f"   NUNOTA: {nunota}")
        print(f"   CODTIPOPER: {codtipoper} ({'OK' if codtipoper == TOP_ENTRADA else 'ERRO'})")
        print(f"   STATUSNOTA: {statusnota}")
        print(f"   DTMOV: {dtmov}")
        print(f"   CODPARC: {codparc}")
        
        # 2. Itens da TOP 11
        print("\n2. Itens da TOP 11:")
        cur.execute("""
            SELECT i.SEQUENCIA, i.CODPROD, i.CODAGREGACAO, 
                   NVL(i.GERAPRODUCAO, 'N') as GERAPRODUCAO,
                   p.DESCRPROD
            FROM TGFITE i
            JOIN TGFPRO p ON p.CODPROD = i.CODPROD
            WHERE i.NUNOTA = :n
            ORDER BY i.SEQUENCIA
        """, n=nunota_11)
        
        itens_top11 = cur.fetchall()
        print(f"   Total de itens: {len(itens_top11)}")
        
        controles = []
        classificaveis = 0
        for seq, codprod, codagregacao, geraprod, descr in itens_top11:
            is_classif = geraprod == 'S'
            if is_classif:
                classificaveis += 1
                
            print(f"   Item SEQ {seq}: {codprod}")
            print(f"      Descricao: {descr[:50]}...")
            print(f"      Controle: {codagregacao}")
            print(f"      Classificavel: {'SIM' if is_classif else 'NAO'} (GERAPRODUCAO={geraprod})")
            print()
            
            if codagregacao and codagregacao not in controles:
                controles.append(codagregacao)
        
        print(f"   RESUMO:")
        print(f"      Itens classificaveis: {classificaveis}")
        print(f"      Controles unicos: {len(controles)}")
        print(f"      Lista de controles: {controles}")
        
        # 3. Verificar TOP 26 existente
        print("\n3. TOP 26 (Classificacao):")
        if not controles:
            print("   ERRO: Sem controles para buscar TOP 26")
            return
            
        controles_str = ','.join([f"'{c}'" for c in controles])
        cur.execute(f"""
            SELECT DISTINCT c.NUNOTA, c.STATUSNOTA, c.DTMOV,
                   COUNT(i.SEQUENCIA) as total_itens
            FROM TGFCAB c
            JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
            WHERE c.CODTIPOPER = :top
            AND i.CODAGREGACAO IN ({controles_str})
            GROUP BY c.NUNOTA, c.STATUSNOTA, c.DTMOV
            ORDER BY c.DTMOV DESC, c.NUNOTA DESC
        """, top=TOP_CLASS)
        
        top26_list = cur.fetchall()
        if not top26_list:
            print("   PROBLEMA: Nenhuma TOP 26 encontrada!")
            print("   Isso significa que a duplicacao automatica nao funcionou.")
            return
            
        print(f"   Encontradas {len(top26_list)} TOP 26(s):")
        for nunota_26, status_26, dtmov_26, total_itens in top26_list:
            print(f"   TOP 26 NUNOTA {nunota_26}:")
            print(f"      Status: {status_26}")
            print(f"      Data: {dtmov_26}")
            print(f"      Total itens: {total_itens}")
            
            # Detalhar itens de cada TOP 26
            cur.execute("""
                SELECT i.SEQUENCIA, i.CODPROD, i.CODAGREGACAO, p.DESCRPROD
                FROM TGFITE i
                JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                WHERE i.NUNOTA = :n
                ORDER BY i.SEQUENCIA
            """, n=nunota_26)
            
            itens_26 = cur.fetchall()
            print(f"      Itens na TOP 26:")
            for seq, codprod, codagregacao, descr in itens_26:
                print(f"         SEQ {seq}: {codprod} - Controle: {codagregacao}")
                print(f"                   Descr: {descr[:40]}...")
            print()
        
        # 4. Comparar controles
        print("4. Analise dos controles:")
        controles_top11 = set(controles)
        
        # Buscar todos os controles nas TOP 26
        controles_top26 = set()
        for nunota_26, _, _, _ in top26_list:
            cur.execute("""
                SELECT DISTINCT i.CODAGREGACAO 
                FROM TGFITE i 
                WHERE i.NUNOTA = :n AND i.CODAGREGACAO IS NOT NULL
            """, n=nunota_26)
            for (ctrl,) in cur.fetchall():
                controles_top26.add(ctrl)
        
        print(f"   Controles na TOP 11: {controles_top11}")
        print(f"   Controles na TOP 26: {controles_top26}")
        
        faltando = controles_top11 - controles_top26
        if faltando:
            print(f"   PROBLEMA: Controles faltando na TOP 26: {faltando}")
            print("   Isso explica por que o segundo produto nao aparece!")
        else:
            print("   OK: Todos os controles estao na TOP 26")

if __name__ == '__main__':
    investigar_nunota_91730()