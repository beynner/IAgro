import os
from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import get_connection, get_trigger_ddl

# Save .sql files under nested folder: sankhya_integration/triggers/triggers
TRIGGERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'triggers',
    'triggers'
)

class Command(BaseCommand):
    help = 'Exporta triggers para arquivos .sql em triggers/triggers/'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--like', type=str, default='%CAB%', help='Padrão LIKE (ex.: %CAB%)')
        parser.add_argument('--owner', type=str, default='SANKHYA', help='Owner/esquema (ex.: SANKHYA)')
        parser.add_argument('--overwrite', action='store_true', help='Sobrescrever arquivos existentes')

    def handle(self, *args, **opts):
        like = (opts['like'] or '%CAB%').upper()
        owner = (opts['owner'] or 'SANKHYA').upper()
        overwrite = bool(opts.get('overwrite'))

        os.makedirs(TRIGGERS_DIR, exist_ok=True)

        with get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT trigger_name FROM all_triggers WHERE owner=:o AND UPPER(trigger_name) LIKE :p ORDER BY trigger_name",
                    o=owner, p=like
                )
                names = [r[0] for r in cur.fetchall()]
            except Exception:
                names = []
            # Fallback: if empty, and current user equals owner, try USER_TRIGGERS
            if not names:
                try:
                    cur.execute("SELECT USER FROM dual")
                    (current_user,) = cur.fetchone()
                except Exception:
                    current_user = None
                if current_user and current_user.upper() == owner:
                    try:
                        cur.execute(
                            "SELECT trigger_name FROM user_triggers WHERE UPPER(trigger_name) LIKE :p ORDER BY trigger_name",
                            p=like
                        )
                        names = [r[0] for r in cur.fetchall()]
                    except Exception:
                        names = []

        if not names:
            self.stdout.write(self.style.WARNING('Nenhuma trigger encontrada.'))
            return

        saved = 0
        for name in names:
            ddl = get_trigger_ddl(owner, name)
            if not ddl:
                self.stdout.write(self.style.ERROR(f'Falha ao obter DDL de {owner}.{name}'))
                continue
            file_path = os.path.join(TRIGGERS_DIR, f"{owner}.{name}.sql")
            if os.path.exists(file_path) and not overwrite:
                self.stdout.write(f'[skip] {file_path} (já existe)')
                continue
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(ddl)
            saved += 1
            self.stdout.write(self.style.SUCCESS(f'[ok] {file_path}'))

        self.stdout.write(self.style.SUCCESS(f'Triggers salvas: {saved}/{len(names)}'))
