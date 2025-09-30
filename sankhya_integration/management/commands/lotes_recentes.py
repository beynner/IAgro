from django.core.management.base import BaseCommand

from sankhya_integration.services.oracle_conn import listar_lotes_recentes


class Command(BaseCommand):
    help = "Lista CODAGREGACAO (lotes) com movimentação recente (somente leitura)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Dias para trás (padrão: 7). Ignorado se --start/--end usados.")
        parser.add_argument("--limit", type=int, default=50, help="Máximo de lotes (padrão: 50)")
        parser.add_argument("--codparc", type=int, help="Filtrar por CODPARC (parceiro)")
        parser.add_argument("--codprod", type=int, help="Filtrar por CODPROD (produto único)")
        parser.add_argument("--codprods", type=int, nargs="*", help="Filtrar por vários CODPROD (ex: --codprods 358 359 907)")
        parser.add_argument("--start", dest="date_start", help="Data inicial YYYY-MM-DD")
        parser.add_argument("--end", dest="date_end", help="Data final YYYY-MM-DD")

    def handle(self, *args, **options):
        days = options["days"]
        limit = options["limit"]
        codparc = options.get("codparc")
        codprod = options.get("codprod")
        codprods = options.get("codprods")
        date_start = options.get("date_start")
        date_end = options.get("date_end")
        try:
            controles = listar_lotes_recentes(
                days=days,
                limit=limit,
                codparc=codparc,
                codprod=codprod,
                codprods=codprods,
                date_start=date_start,
                date_end=date_end,
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erro ao consultar lotes recentes: {e}"))
            return

        if not controles:
            self.stdout.write(self.style.WARNING("Nenhum lote recente encontrado."))
            return

        self.stdout.write(self.style.SUCCESS(f"Encontrados {len(controles)} lotes recentes (até {limit}):"))
        for c in controles:
            self.stdout.write(str(c))
