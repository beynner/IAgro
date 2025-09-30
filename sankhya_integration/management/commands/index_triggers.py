import os
import re
from django.core.management.base import BaseCommand

# Input folder for .sql files (nested): sankhya_integration/triggers/triggers
TRIG_SQL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'triggers',
    'triggers'
)
# Output folder for index file: top-level triggers
TRIG_OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'triggers'
)

class Command(BaseCommand):
    help = 'Gera um índice agrupando triggers por tabela (TGFCAB, TGFITE, etc.) em triggers/INDEX.md.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--owner', type=str, default='SANKHYA', help='Owner esperado para inferir tabela a partir do arquivo.')

    def handle(self, *args, **opts):
        owner = (opts.get('owner') or 'SANKHYA').upper()
        os.makedirs(TRIG_SQL_DIR, exist_ok=True)
        os.makedirs(TRIG_OUT_DIR, exist_ok=True)
        files = [f for f in os.listdir(TRIG_SQL_DIR) if f.lower().endswith('.sql')]
        groups: dict[str, list[str]] = {}

        # Heurística: nome do arquivo = OWNER.TRIGGER.sql; tabela aparece após último '_', ou no corpo CREATE TRIGGER ... ON owner.table
        for fn in files:
            path = os.path.join(TRIG_SQL_DIR, fn)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read(4000)
            except Exception:
                text = ''
            table = None
            # Try: FROM first occurrence of ' ON owner.' pattern
            m = re.search(rf"\bON\s+{owner}\.([A-Z0-9_]+)", text, re.IGNORECASE)
            if m:
                table = m.group(1).upper()
            else:
                # Fallback: parse trigger name and get trailing token after last underscore
                base = os.path.splitext(fn)[0]
                name = base.split('.', 1)[-1]  # TRIGGER_NAME
                parts = name.split('_')
                if len(parts) >= 2:
                    table = parts[-1].upper()
            if not table:
                table = 'UNKNOWN'
            groups.setdefault(table, []).append(fn)

        # Sort groups/tables and files
        for k in groups:
            groups[k] = sorted(groups[k])
        ordered = sorted(groups.items(), key=lambda kv: kv[0])

        out = ["# Triggers Index\n", "\n", "Agrupadas por tabela (heurística).\n\n"]
        for table, fns in ordered:
            out.append(f"## {table}\n\n")
            for fn in fns:
                out.append(f"- {fn}\n")
            out.append("\n")

        idx_path = os.path.join(TRIG_OUT_DIR, 'INDEX.md')
        with open(idx_path, 'w', encoding='utf-8') as f:
            f.writelines(out)

        self.stdout.write(self.style.SUCCESS(f'INDEX gerado em {idx_path}'))
