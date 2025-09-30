#!/usr/bin/env python3
"""
Teste da correção - Simular adição sequencial de produtos
"""

import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
    django.setup()

from sankhya_integration.services.oracle_conn import (
    get_connection, should_auto_duplicate_item, duplicate_to_classification, 
    get_duplicate_status, is_auto_duplicate_on_save_enabled
)

def simular_adicao_sequencial():
    """Simula adição de produtos sequenciais para testar a lógica corrigida."""
    
    # Usar NUNOTA 91730 que sabemos que tem 2 produtos
    nunota_11 = 91730
    
    print("SIMULANDO ADIÇÃO SEQUENCIAL DE PRODUTOS")
    print("=" * 60)
    
    # Buscar produtos da nota
    with get_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT i.CODPROD, i.CODAGREGACAO, NVL(i.GERAPRODUCAO, 'N') as GERAPROD
            FROM TGFITE i
            WHERE i.NUNOTA = :n
            ORDER BY i.SEQUENCIA
        """, n=nunota_11)
        
        produtos = cur.fetchall()
        
    print(f"NUNOTA {nunota_11} tem {len(produtos)} produtos:")
    for i, (codprod, controle, geraprod) in enumerate(produtos, 1):
        print(f"  {i}. Produto {codprod} - Controle: {controle} - Classificável: {geraprod}")
    
    print(f"\n{'='*60}")
    print("SIMULANDO LÓGICA CORRIGIDA:")
    print("="*60)
    
    # Simular comportamento da view corrigida para cada produto
    for i, (codprod, controle, geraprod) in enumerate(produtos, 1):
        print(f"\n🔄 SIMULANDO ADIÇÃO DO PRODUTO {i}: {codprod}")
        print("-" * 50)
        
        # 1. Verificar se deve duplicar
        enabled = is_auto_duplicate_on_save_enabled()
        print(f"   Auto duplicate enabled: {enabled}")
        
        if enabled:
            check = should_auto_duplicate_item(nunota_11, codprod)
            print(f"   Should duplicate: {check}")
            
            if check.get('should_duplicate'):
                print("   ✅ Produto deve ser duplicado")
                
                # LÓGICA ANTIGA (problematica):
                print("\n   📊 LÓGICA ANTIGA (com problema):")
                status = get_duplicate_status(nunota_11)
                print(f"      get_duplicate_status: {status}")
                
                if not status.get('has_top26'):
                    print("      ✅ Duplicaria (não existe TOP 26)")
                else:
                    print("      ❌ NÃO duplicaria (TOP 26 já existe) <- PROBLEMA!")
                
                # LÓGICA NOVA (corrigida):
                print("\n   🔧 LÓGICA NOVA (corrigida):")
                print("      Sempre chama duplicate_to_classification()")
                
                dup_result = duplicate_to_classification(nunota_11, dry_run=True)
                print(f"      Resultado: {dup_result}")
                
                items_duplicated = dup_result.get('items_duplicated', 0) 
                if dup_result.get('ok'):
                    if items_duplicated > 0:
                        print(f"      ✅ Adicionaria {items_duplicated} item(s) à TOP 26")
                    else:
                        print("      ℹ️  Item já existe na TOP 26")
                else:
                    print(f"      ❌ Erro: {dup_result.get('errors')}")
            else:
                reason = check.get('reason', 'Motivo não informado')
                print(f"   ⏭️  Não deve duplicar: {reason}")
        else:
            print("   ⏭️  Auto duplicate desabilitado")
    
    print(f"\n{'='*60}")
    print("RESULTADO ESPERADO COM A CORREÇÃO:")
    print("="*60)
    print("✅ Produto 1: Cria TOP 26 (ou usa existente)")
    print("✅ Produto 2: Adiciona na mesma TOP 26 (não cria nova)")
    print("✅ Ambos aparecem na página de classificação!")

if __name__ == '__main__':
    simular_adicao_sequencial()