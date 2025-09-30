#!/usr/bin/env python3
"""
Corrigir NUNOTA 91730 - Duplicar o item faltante para TOP 26
"""

import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
    django.setup()

from sankhya_integration.services.oracle_conn import get_connection, duplicate_to_classification

def corrigir_91730():
    """Força a duplicação completa da NUNOTA 91730."""
    nunota_11 = 91730
    
    print(f"CORRIGINDO NUNOTA {nunota_11}")
    print("=" * 50)
    
    print("\n1. Executando duplicate_to_classification...")
    
    # Tentar duplicar (deve adicionar o item faltante)
    result = duplicate_to_classification(nunota_11, dry_run=False)
    
    print("Resultado da duplicacao:")
    print(f"   ok: {result.get('ok')}")
    print(f"   nunota_26: {result.get('nunota_26')}")
    print(f"   items_duplicated: {result.get('items_duplicated')}")
    print(f"   errors: {result.get('errors')}")
    print(f"   warnings: {result.get('warnings')}")
    
    if result.get('ok'):
        nunota_26 = result.get('nunota_26')
        items_added = result.get('items_duplicated', 0)
        
        if items_added > 0:
            print(f"\n✅ SUCESSO! {items_added} item(s) adicionado(s) na TOP 26 {nunota_26}")
        else:
            print(f"\nℹ️  Nenhum item novo adicionado na TOP 26 {nunota_26}")
            print("   (Pode ser que todos os itens ja estejam duplicados)")
        
        # Verificar resultado final
        print(f"\n2. Verificando resultado final...")
        
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Contar itens na TOP 26
            cur.execute("""
                SELECT COUNT(*), 
                       COUNT(DISTINCT i.CODAGREGACAO) as controles_unicos
                FROM TGFITE i
                WHERE i.NUNOTA = :n
            """, n=nunota_26)
            
            total_itens, controles_unicos = cur.fetchone()
            
            print(f"   TOP 26 ({nunota_26}) agora tem:")
            print(f"      Total de itens: {total_itens}")
            print(f"      Controles únicos: {controles_unicos}")
            
            # Listar itens
            cur.execute("""
                SELECT i.SEQUENCIA, i.CODPROD, i.CODAGREGACAO, p.DESCRPROD
                FROM TGFITE i
                JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                WHERE i.NUNOTA = :n
                ORDER BY i.SEQUENCIA
            """, n=nunota_26)
            
            itens = cur.fetchall()
            print(f"\n   Itens na TOP 26:")
            for seq, codprod, controle, descr in itens:
                print(f"      SEQ {seq}: {codprod} - {controle}")
                print(f"                {descr[:40]}...")
            
            if controles_unicos >= 2:
                print(f"\n✅ CORRIGIDO! Agora ambos os produtos aparecerao na classificacao!")
            else:
                print(f"\n❌ AINDA FALTA CORRIGIR - so {controles_unicos} controle(s) na TOP 26")
    else:
        print(f"\n❌ ERRO na duplicacao: {result.get('errors')}")

if __name__ == '__main__':
    corrigir_91730()