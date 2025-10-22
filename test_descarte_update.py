#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste rápido para verificar atualização de QTDBATIDAS
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import plan_update_cabecalho, update_cabecalho

def test_float_conversion():
    """Testa conversão de float"""
    print("\n=== Teste 1: Conversão de Float ===")
    
    # Teste com float direto
    data1 = {
        'NUNOTA': 92500,
        'QTDBATIDAS': 5.5
    }
    print(f"Input: {data1}")
    result1 = plan_update_cabecalho(data1)
    print(f"Result: ok={result1['ok']}, errors={result1['errors']}")
    print(f"SQL: {result1.get('sql')}")
    print(f"Binds: {result1.get('binds')}")
    
    # Teste com string
    print("\n=== Teste 2: String numérica ===")
    data2 = {
        'NUNOTA': 92500,
        'QTDBATIDAS': '12.3'
    }
    print(f"Input: {data2}")
    result2 = plan_update_cabecalho(data2)
    print(f"Result: ok={result2['ok']}, errors={result2['errors']}")
    print(f"SQL: {result2.get('sql')}")
    
    # Teste com zero
    print("\n=== Teste 3: Zero ===")
    data3 = {
        'NUNOTA': 92500,
        'QTDBATIDAS': 0
    }
    print(f"Input: {data3}")
    result3 = plan_update_cabecalho(data3)
    print(f"Result: ok={result3['ok']}, errors={result3['errors']}")
    print(f"SQL: {result3.get('sql')}")
    
    # Teste com None (não deve adicionar ao SET)
    print("\n=== Teste 4: None (não deve atualizar) ===")
    data4 = {
        'NUNOTA': 92500,
        'QTDBATIDAS': None
    }
    print(f"Input: {data4}")
    result4 = plan_update_cabecalho(data4)
    print(f"Result: ok={result4['ok']}, errors={result4['errors']}, warnings={result4['warnings']}")
    print(f"SQL: {result4.get('sql')}")

if __name__ == '__main__':
    print("Testando atualização de QTDBATIDAS...")
    test_float_conversion()
    print("\n✅ Testes concluídos!")
