import os, sys
sys.path.insert(0, r'd:\TI\NexusGTi\Harvest')
# Allow writes for this run
os.environ['PACKINGHOUSE_WRITE_ENABLED'] = 'true'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
import django
django.setup()
from sankhya_integration.services.oracle_conn import is_write_enabled, delete_nota

nun = 91205
print('is_write_enabled before call =', is_write_enabled())
res = delete_nota(nun, dry_run=False)
print('delete_nota result:')
import json
print(json.dumps(res, indent=2, default=str))
