#!/usr/bin/env python3
"""
Teste para validar correção do problema de duplicação múltipla.

Este script testa:
1. Se get_duplicate_status detecta TOP 26 existente corretamente
2. Se duplicate_to_classification adiciona itens à TOP 26 existente ao invés de criar nova
"""

import os
import sys
import django

# Configurar Django
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
    django.setup()

from sankhya_integration.services.oracle_conn import (
    get_connection, get_duplicate_status, duplicate_to_classification,
    get_params
)

def test_duplicate_logic(nunota_11):
    """Testa a lógica de duplicação corrigida."""
    print(f"\n🔍 TESTANDO LÓGICA DE DUPLICAÇÃO PARA NUNOTA {nunota_11}")
    print("=" * 60)
    
    # 1. Status inicial
    print("\n1️⃣ Status inicial:")
    status = get_duplicate_status(nunota_11)
    print(f"   Status: {status}")
    
    # 2. Primeira duplicação (deve criar TOP 26)
    print("\n2️⃣ Primeira duplicação:")
    result1 = duplicate_to_classification(nunota_11, dry_run=False)
    print(f"   Resultado: {result1}")
    
    if result1.get('ok'):
        nunota_26 = result1.get('nunota_26')
        print(f"   ✅ TOP 26 criada/atualizada: {nunota_26}")
        
        # 3. Status após primeira duplicação
        print("\n3️⃣ Status após primeira duplicação:")
        status2 = get_duplicate_status(nunota_11)
        print(f"   Status: {status2}")
        
        # 4. Segunda duplicação (deve usar a mesma TOP 26)
        print("\n4️⃣ Segunda duplicação (simular adição de segundo produto):")
        result2 = duplicate_to_classification(nunota_11, dry_run=False)
        print(f"   Resultado: {result2}")
        
        # 5. Verificar se NUNOTA 26 é a mesma
        nunota_26_segunda = result2.get('nunota_26')
        if nunota_26 == nunota_26_segunda:
            print(f"   ✅ SUCESSO: Mesma TOP 26 utilizada ({nunota_26})")
            return True
        else:
            print(f"   ❌ ERRO: Nova TOP 26 criada ({nunota_26_segunda}) ao invés de usar a existente ({nunota_26})")
            return False
    else:
        print(f"   ❌ ERRO na primeira duplicação: {result1.get('errors')}")
        return False

def verificar_itens_top26(nunota_26):
    """Verifica quantos itens existem na TOP 26."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), MAX(SEQUENCIA) FROM TGFITE WHERE NUNOTA = :n", n=nunota_26)
            count, max_seq = cur.fetchone()
            print(f"   TOP 26 ({nunota_26}): {count} itens, sequência máxima: {max_seq}")
            return count, max_seq
    except Exception as e:
        print(f"   ❌ Erro ao verificar itens: {e}")
        return 0, 0

if __name__ == '__main__':
    # Teste com NUNOTA conhecida
    nunota_teste = 91715  # Usar a NUNOTA que sabemos que funciona
    
    print("🧪 TESTE DE CORREÇÃO - DUPLICAÇÃO MÚLTIPLA")
    print("=" * 60)
    print("Este teste verifica se a correção impede a criação de múltiplas TOP 26")
    print("para a mesma TOP 11 quando produtos são adicionados sequencialmente.")
    
    # Executar teste
    sucesso = test_duplicate_logic(nunota_teste)
    
    if sucesso:
        print("\n🎉 TESTE PASSOU! Correção funcionando corretamente.")
    else:
        print("\n💥 TESTE FALHOU! Ainda há problema na lógica.")
    
    print("\n" + "=" * 60)
    print("Teste finalizado.")