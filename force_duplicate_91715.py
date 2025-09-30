#!/usr/bin/env python3
"""
Testar duplicação manual forçada da NUNOTA 91715
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import (
    duplicate_to_classification, 
    get_duplicate_status,
    should_auto_duplicate_item,
    is_auto_duplicate_on_save_enabled
)

print("=== TESTE DUPLICAÇÃO MANUAL NUNOTA 91715 ===")

nunota_11 = 91715
codprod = 31

try:
    # 1. Verificar configurações
    print("1. Verificar configurações:")
    enabled = is_auto_duplicate_on_save_enabled()
    print(f"   Auto duplicate enabled: {enabled}")
    
    # 2. Verificar se deve duplicar
    print("\n2. Verificar se deve duplicar:")
    check = should_auto_duplicate_item(nunota_11, codprod)
    print(f"   should_duplicate: {check.get('should_duplicate')}")
    print(f"   reason: {check.get('reason')}")
    print(f"   codtipoper: {check.get('codtipoper')}")
    
    # 3. Status atual
    print("\n3. Status atual:")
    status = get_duplicate_status(nunota_11)
    print(f"   has_top26: {status.get('has_top26')}")
    print(f"   controls: {status.get('controls')}")
    print(f"   classificable_items: {status.get('classificable_items')}")
    
    # 4. Testar duplicação (DRY RUN)
    print("\n4. Teste duplicação (dry run):")
    dry_result = duplicate_to_classification(nunota_11, dry_run=True)
    print(f"   ok: {dry_result.get('ok')}")
    print(f"   errors: {dry_result.get('errors')}")
    print(f"   warnings: {dry_result.get('warnings')}")
    print(f"   items_duplicated: {dry_result.get('items_duplicated')}")
    
    # 5. Se dry run funcionou, executar real
    if dry_result.get('ok') and not dry_result.get('errors'):
        print("\n5. Executando duplicação REAL:")
        real_result = duplicate_to_classification(nunota_11, dry_run=False)
        print(f"   ok: {real_result.get('ok')}")
        print(f"   executed: {real_result.get('executed')}")
        print(f"   nunota_26: {real_result.get('nunota_26')}")
        print(f"   items_duplicated: {real_result.get('items_duplicated')}")
        print(f"   errors: {real_result.get('errors')}")
        
        if real_result.get('ok'):
            print(f"\n   ✅ SUCESSO! TOP 26 criada: NUNOTA {real_result.get('nunota_26')}")
        else:
            print(f"\n   ❌ FALHA! Erros: {real_result.get('errors')}")
    else:
        print("\n5. Dry run falhou - não executando duplicação real")
        
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

print("\n=== FIM DO TESTE ===")