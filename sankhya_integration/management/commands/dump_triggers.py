from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import get_connection, get_trigger_body

class Command(BaseCommand):
    help = "Lista e (opcionalmente) imprime o corpo de triggers cujo nome casa com o padrão."

    def add_arguments(self, parser):
        parser.add_argument('--like', type=str, default='%CAB%', help="Padrão LIKE (case-insensitive), ex.: %CAB%")
        parser.add_argument('--owner', type=str, default=None, help="Owner/esquema (ex.: SANKHYA). Se omitido, busca em ALL_TRIGGERS.")
        parser.add_argument('--no-body', action='store_true', help="Apenas listar nomes, não imprimir corpo.")

    def handle(self, *args, **opts):
        like = (opts['like'] or '%CAB%').upper()
        owner = opts.get('owner')
        only_list = bool(opts.get('no_body'))

        with get_connection() as conn:
            cur = conn.cursor()
            if owner:
                cur.execute(
                    "SELECT trigger_name FROM all_triggers WHERE owner=:o AND UPPER(trigger_name) LIKE :p ORDER BY trigger_name",
                    o=owner.upper(), p=like,
                )
            else:
                cur.execute(
                    "SELECT owner, trigger_name FROM all_triggers WHERE UPPER(trigger_name) LIKE :p ORDER BY owner, trigger_name",
                    p=like,
                )
            rows = cur.fetchall()

        if not rows:
            self.stdout.write(self.style.WARNING('Nenhuma trigger encontrada para o padrão informado.'))
            return

        if owner:
            names = [r[0] for r in rows]
        else:
            names = [f"{r[0]}.{r[1]}" for r in rows]

        self.stdout.write(self.style.SUCCESS(f"Encontradas {len(names)} triggers:"))
        for n in names:
            self.stdout.write(f" - {n}")

        if only_list:
            return

        self.stdout.write("\n================= CORPOS =================\n")
        for n in names:
            name_only = n.split('.')[-1]
            body = get_trigger_body(name_only)
            if not body:
                self.stdout.write(self.style.ERROR(f"[SEM ACESSO/VAZIO] {n}"))
                continue
            self.stdout.write(self.style.SUCCESS(f"-- BEGIN {n} --"))
            self.stdout.write(body)
            self.stdout.write(self.style.SUCCESS(f"-- END {n} --\n"))
