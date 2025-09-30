#!/usr/bin/env python3
"""
Script simples para testar duplicação da NUNOTA 91715
"""
import requests
import json

print("=== TESTE DUPLICAÇÃO NUNOTA 91715 ===")

# 1. Testar configurações
try:
    print("1. Testando configurações...")
    config_response = requests.get('http://localhost:8000/sankhya/auto/config/', timeout=10)
    if config_response.status_code == 200:
        config = config_response.json()
        print(f"   auto_duplicate_on_save: {config.get('auto_duplicate_on_save')}")
        print(f"   duplicate_method: {config.get('duplicate_method')}")
        print(f"   write_enabled: {config.get('write_enabled')}")
    else:
        print(f"   Erro: Status {config_response.status_code}")
except Exception as e:
    print(f"   Erro ao testar config: {e}")

# 2. Testar status da nota
try:
    print("\n2. Testando status da NUNOTA 91715...")
    status_response = requests.get('http://localhost:8000/sankhya/duplicate/status/?nunota_11=91715', timeout=10)
    if status_response.status_code == 200:
        status = status_response.json()
        print(f"   has_top26: {status.get('has_top26')}")
        print(f"   nunota_26: {status.get('nunota_26')}")
        print(f"   controls: {status.get('controls')}")
        print(f"   classificable_items: {status.get('classificable_items')}")
    else:
        print(f"   Erro: Status {status_response.status_code}")
except Exception as e:
    print(f"   Erro ao testar status: {e}")

# 3. Testar duplicação manual (dry run)
try:
    print("\n3. Testando duplicação manual (dry run)...")
    duplicate_data = {
        'nunota_11': 91715,
        'dry_run': True
    }
    duplicate_response = requests.post(
        'http://localhost:8000/sankhya/duplicate/classification/',
        json=duplicate_data,
        timeout=30
    )
    print(f"   Status: {duplicate_response.status_code}")
    if duplicate_response.status_code in [200, 400]:
        result = duplicate_response.json()
        print(f"   ok: {result.get('ok')}")
        print(f"   errors: {result.get('errors')}")
        print(f"   warnings: {result.get('warnings')}")
        print(f"   items_duplicated: {result.get('items_duplicated')}")
    else:
        print(f"   Response: {duplicate_response.text}")
except Exception as e:
    print(f"   Erro ao testar duplicação: {e}")

print("\n=== FIM DO TESTE ===")