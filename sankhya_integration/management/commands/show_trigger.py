from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import get_trigger_body

class Command(BaseCommand):
    help = 'Exibe o corpo do trigger informado (ALL_TRIGGERS/ALL_SOURCE).'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Nome do trigger (ex.: TRG_INC_TGFCAB)')

    def handle(self, *args, **opts):
        name = opts['name']
        body = get_trigger_body(name)
        if not body:
            self.stdout.write(self.style.ERROR('Trigger não encontrado ou sem acesso.'))
            return
        self.stdout.write(self.style.SUCCESS(f'Conteúdo de {name}:'))
        self.stdout.write(body)
