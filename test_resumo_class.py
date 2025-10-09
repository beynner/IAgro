#!/usr/bin/env python
"""
Testa resumo_classificacao_por_lote com normalização via TGFVOA
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import resumo_classificacao_por_lote

lote = '251009P536P27S01'

print("=" * 80)
print(f"TESTE: resumo_classificacao_por_lote('{lote}')")
print("=" * 80)

try:
    rows = resumo_classificacao_por_lote(lote)
    
    print(f"\n📦 Total de produtos classificados: {len(rows)}\n")
    
    total_cx = 0.0
    total_kg = 0.0
    
    for descr, sum_cx, sum_kg, fator_cx in rows:
        print(f"🏷️  Produto: {descr}")
        print(f"   └─ CX: {sum_cx:.2f} caixas")
        print(f"   └─ KG: {sum_kg:.2f} kg")
        print(f"   └─ Fator: {fator_cx:.2f} kg/cx (TGFVOA)")
        print(f"   └─ Verificação: {sum_kg:.2f} ÷ {fator_cx:.2f} = {sum_kg/fator_cx if fator_cx > 0 else 0:.2f} cx")
        print()
        
        total_cx += float(sum_cx or 0)
        total_kg += float(sum_kg or 0)
    
    print("=" * 80)
    print(f"📊 TOTAIS:")
    print(f"   ✅ Total CX (normalizado): {total_cx:.2f} caixas")
    print(f"   ✅ Total KG: {total_kg:.2f} kg")
    print("=" * 80)
    
    print("\n💡 VERIFICAÇÃO:")
    print(f"   Esperado: 100 caixas (1600 KG ÷ 20 + 400 KG ÷ 20 = 80 + 20)")
    print(f"   Obtido: {total_cx:.2f} caixas")
    print(f"   Status: {'✅ CORRETO' if abs(total_cx - 100) < 0.1 else '❌ INCORRETO'}")
    print()

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
