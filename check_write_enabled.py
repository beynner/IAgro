"""Verificar se WRITE_ENABLED está ativo"""
from sankhya_integration.services.oracle_conn import is_write_enabled, _get_app_config

print("=== VERIFICAR WRITE_ENABLED ===\n")

# Verificar app config
cfg = _get_app_config()
print(f"App Config: {cfg}")
print(f"  WRITE_ENABLED no config: {cfg.get('WRITE_ENABLED')}")

# Verificar is_write_enabled()
write_enabled = is_write_enabled()
print(f"\nis_write_enabled(): {write_enabled}")

if write_enabled:
    print("\n✅ Modo de escrita HABILITADO")
else:
    print("\n❌ Modo de escrita DESABILITADO")
    print("\nPara habilitar, defina:")
    print("  - SANKHYA_CONFIG['WRITE_ENABLED'] = True em settings.py (JÁ ESTÁ)")
    print("  - OU variável de ambiente: PACKINGHOUSE_WRITE_ENABLED=true")
