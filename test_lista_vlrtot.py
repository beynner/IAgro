"""
Testar listar_itens_portal_basico com a query atualizada
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import listar_itens_portal_basico

print(f"\n{'='*60}")
print(f"Testando listar_itens_portal_basico")
print(f"{'='*60}\n")

rows = listar_itens_portal_basico(days=30, limit=10)

print(f"✅ Retornou {len(rows)} itens\n")

for r in rows:
    nunota = r[6] if len(r) > 6 else None
    if nunota == 93227:
        print(f"🎯 Item NUNOTA 93227 encontrado:")
        print(f"   Parceiro: {r[0]}")
        print(f"   Produto: {r[1]}")
        print(f"   QTDNEG: {r[2]}")
        print(f"   PRECOBASE: {r[10] if len(r) > 10 else 'N/A'}")
        print(f"   VLRUNIT: {r[11] if len(r) > 11 else 'N/A'}")
        print(f"   ⭐ VLRTOT: {r[12] if len(r) > 12 else 'N/A'} ⭐")
        print()
        
        vlrtot = r[12] if len(r) > 12 else 0
        if vlrtot and vlrtot > 0:
            print(f"   ✅ VLRTOT = {vlrtot} (esperado: ~15.000)")
        else:
            print(f"   ❌ VLRTOT está zerado (deveria ser ~15.000)")
        break

print(f"\n{'='*60}\n")
