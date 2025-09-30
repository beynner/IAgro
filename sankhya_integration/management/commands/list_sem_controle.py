from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import listar_itens_sem_controle


class Command(BaseCommand):
    help = 'Lista itens de entrada (TOP 11, CODPROD 863) sem CODAGREGACAO (lote) definido'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50, help='Quantidade máxima de itens a listar')

    def handle(self, *args, **options):
        limit = options['limit']
        rows = listar_itens_sem_controle(limit)
        if not rows:
            self.stdout.write(self.style.WARNING('Nenhum item sem CODAGREGACAO encontrado.'))
            return
        self.stdout.write(self.style.SUCCESS(f'Encontrados {len(rows)} itens (até {limit}):'))
        for r in rows:
            nunota, sequencia, codparc, codprod, qtdneg, dtneg = r
            self.stdout.write(f'NUNOTA={nunota} SEQ={sequencia} CODPARC={codparc} CODPROD={codprod} QTD={qtdneg} DTNEG={dtneg}')
