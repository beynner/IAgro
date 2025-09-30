import os, sys
sys.path.insert(0, r'd:\TI\NexusGTi\Harvest')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
import django
django.setup()
from sankhya_integration.services.oracle_conn import diagnose_nota_delete, delete_nota

nun = 91205
print('Diagnosing nunota =', nun)
print(diagnose_nota_delete(nun))
print('\nDry-run delete:')
print(delete_nota(nun, dry_run=True))
