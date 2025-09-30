from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import calcular_agregados_lote, consultar_lote
from pprint import pformat


class Command(BaseCommand):
    help = 'Mostra status de um lote (somente leitura): agregados e listas (entradas, classificacoes, descarte, vendas, reservas)'

    def add_arguments(self, parser):
        parser.add_argument('controle', type=str, help='Código do lote (CONTROLE)')

    def handle(self, *args, **options):
        controle = options['controle']
        ag = calcular_agregados_lote(controle)
        self.stdout.write(self.style.SUCCESS('Agregados:'))
        self.stdout.write(pformat(ag))

        det = consultar_lote(controle)
        self.stdout.write(self.style.SUCCESS('\nDetalhes:'))
        for key in ['entradas', 'classificacoes', 'descarte', 'vendas', 'reservas']:
            self.stdout.write(self.style.NOTICE(f'\n== {key.upper()} =='))
            self.stdout.write(pformat(det.get(key, [])))
