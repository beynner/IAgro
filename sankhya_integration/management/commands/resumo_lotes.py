from django.core.management.base import BaseCommand

from sankhya_integration.services.oracle_conn import listar_lotes_recentes, calcular_agregados_lote


class Command(BaseCommand):
    help = "Resumo de lotes recentes com agregados (somente leitura)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Dias para trás (padrão: 7). Ignorado se --start/--end usados.")
        parser.add_argument("--limit", type=int, default=20, help="Máximo de lotes (padrão: 20)")
        parser.add_argument("--csv", action="store_true", help="Saída em CSV")
        parser.add_argument("--codparc", type=int, help="Filtrar por CODPARC (parceiro)")
        parser.add_argument("--codprod", type=int, help="Filtrar por CODPROD (produto único)")
        parser.add_argument("--codprods", type=int, nargs="*", help="Filtrar por vários CODPROD (ex: --codprods 358 359 907)")
        parser.add_argument("--start", dest="date_start", help="Data inicial YYYY-MM-DD")
        parser.add_argument("--end", dest="date_end", help="Data final YYYY-MM-DD")

    def handle(self, *args, **options):
        days = options["days"]
        limit = options["limit"]
        as_csv = options["csv"]
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
            self.stderr.write(self.style.ERROR(f"Erro ao listar lotes: {e}"))
            return

        if not controles:
            self.stdout.write(self.style.WARNING("Nenhum lote recente encontrado."))
            return

        headers = [
            "controle",
            "prevista",
            "classificada",
            "descartada",
            "vendida",
            "reservada",
            "disponivel",
            "divergencia",
            "estado",
        ]
        if as_csv:
            self.stdout.write(";".join(headers))
        else:
            self.stdout.write(self.style.SUCCESS(f"Resumo de {len(controles)} lotes:"))

        for c in controles:
            try:
                agg = calcular_agregados_lote(c)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Falha ao calcular agregados do lote {c}: {e}"))
                continue

            row = [
                agg.get("controle"),
                f"{agg.get('qtd_prevista', 0):.2f}",
                f"{agg.get('qtd_classificada', 0):.2f}",
                f"{agg.get('qtd_descartada', 0):.2f}",
                f"{agg.get('qtd_vendida', 0):.2f}",
                f"{agg.get('qtd_reservada', 0):.2f}",
                f"{agg.get('qtd_disponivel', 0):.2f}",
                f"{agg.get('divergencia', 0):.2f}",
                agg.get("estado"),
            ]

            if as_csv:
                self.stdout.write(";".join(map(str, row)))
            else:
                self.stdout.write(
                    f"Lote {row[0]} | Prev: {row[1]} | Class: {row[2]} | Desc: {row[3]} | Vend: {row[4]} | Res: {row[5]} | Disp: {row[6]} | Div: {row[7]} | {row[8]}"
                )
