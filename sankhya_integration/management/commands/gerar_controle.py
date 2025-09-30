from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import gerar_controle_para_item


class Command(BaseCommand):
    help = 'Gera CODAGREGACAO (lote) para um item (NUNOTA/SEQUENCIA). Usa DTNEG do cabeçalho se data não informada.'

    def add_arguments(self, parser):
        parser.add_argument('nunota', type=int, help='Número único da nota (NUNOTA)')
        parser.add_argument('sequencia', type=int, help='Sequência do item na nota (SEQUENCIA)')
        parser.add_argument('--data', type=str, default=None, help="Data no formato YYYY-MM-DD (opcional)")
        parser.add_argument('--commit', action='store_true', help='Se informado, grava no banco (por padrão é dry-run)')

    def handle(self, *args, **options):
        nunota = options['nunota']
        sequencia = options['sequencia']
        data = options.get('data')
        commit = options.get('commit', False)
        controle = gerar_controle_para_item(nunota, sequencia, data=data, commit=commit)
        if commit:
            self.stdout.write(self.style.SUCCESS(f'CODAGREGACAO gerado e gravado: {controle}'))
        else:
            self.stdout.write(self.style.WARNING(f'DRY-RUN: CODAGREGACAO sugerido: {controle}'))
