#!/usr/bin/env python3
"""
Teste simples para validar correção da duplicação múltipla.
"""

import os
import sys
import django

# Configurar Django
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
    django.setup()

from sankhya_integration.services.oracle_conn import (
    get_connection, get_duplicate_status, duplicate_to_classification
)

def test_nunota_91725():
    """Testa a correção com NUNOTA 91725."""
    nunota_11 = 91725
    
    print(f"Testando NUNOTA {nunota_11}")
    print("=" * 50)
    
    # 1. Status inicial
    print("\n1. Status inicial:")
    status = get_duplicate_status(nunota_11)
    print(f"   has_top26: {status.get('has_top26')}")
    print(f"   nunota_26: {status.get('nunota_26')}")
    print(f"   classificable_items: {status.get('classificable_items')}")
    
    # 2. Primeira duplicação
    print("\n2. Primeira duplicação (dry_run=True):")
    result1 = duplicate_to_classification(nunota_11, dry_run=True)
    print(f"   ok: {result1.get('ok')}")
    print(f"   errors: {result1.get('errors')}")
    print(f"   warnings: {result1.get('warnings')}")
    
    if result1.get('ok') and not result1.get('errors'):
        # 3. Executar real
        print("\n3. Executando duplicação real:")
        result2 = duplicate_to_classification(nunota_11, dry_run=False)
        print(f"   ok: {result2.get('ok')}")
        print(f"   nunota_26: {result2.get('nunota_26')}")
        print(f"   items_duplicated: {result2.get('items_duplicated')}")
        print(f"   warnings: {result2.get('warnings')}")
        
        if result2.get('ok'):
            nunota_26_primeira = result2.get('nunota_26')
            
            # 4. Status após primeira duplicação
            print("\n4. Status após primeira duplicação:")
            status2 = get_duplicate_status(nunota_11)
            print(f"   has_top26: {status2.get('has_top26')}")
            print(f"   nunota_26: {status2.get('nunota_26')}")
            
            # 5. Segunda duplicação (deve usar a mesma TOP 26)
            print("\n5. Segunda duplicação (deve usar TOP 26 existente):")
            result3 = duplicate_to_classification(nunota_11, dry_run=False)
            print(f"   ok: {result3.get('ok')}")
            print(f"   nunota_26: {result3.get('nunota_26')}")
            print(f"   items_duplicated: {result3.get('items_duplicated')}")
            print(f"   warnings: {result3.get('warnings')}")
            
            nunota_26_segunda = result3.get('nunota_26')
            
            # 6. Validar resultado
            print("\n6. Resultado:")
            if nunota_26_primeira == nunota_26_segunda:
                print(f"   ✅ SUCESSO! Mesma TOP 26 utilizada: {nunota_26_primeira}")
                print("   A correção está funcionando corretamente!")
                return True
            else:
                print(f"   ❌ FALHA! NUNOTAs diferentes:")
                print(f"      Primeira: {nunota_26_primeira}")
                print(f"      Segunda: {nunota_26_segunda}")
                return False
    
    return False

if __name__ == '__main__':
    test_nunota_91725()