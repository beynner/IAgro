from django.core.management.base import BaseCommand
from sankhya_integration.services.oracle_conn import plan_insert_cabecalho


class Command(BaseCommand):
    help = 'Planeja o INSERT do cabeçalho (TGFCAB) sem gravar — exibe SQL, binds e checagens.'

    def add_arguments(self, parser):
        parser.add_argument('--codemp', type=int, required=True)
        parser.add_argument('--codparc', type=int, required=True)
        parser.add_argument('--codtipoper', type=int, required=True)
        parser.add_argument('--codnat', type=int, required=True)
        parser.add_argument('--codcencus', type=int)
        parser.add_argument('--dtneg', type=str, required=True, help='Formato DD/MM/YYYY')
        parser.add_argument('--dtmov', type=str)
        parser.add_argument('--dtentsai', type=str)
        parser.add_argument('--hrmov', type=str)
        parser.add_argument('--nronota', type=str)
        parser.add_argument('--obs', type=str)

    def handle(self, *args, **opts):
        d = {
            'CODEMP': opts['codemp'],
            'CODPARC': opts['codparc'],
            'CODTIPOPER': opts['codtipoper'],
            'CODNAT': opts['codnat'],
            'CODCENCUS': opts.get('codcencus'),
            'DTNEG': opts['dtneg'],
            'DTMOV': opts.get('dtmov'),
            'DTENTSAI': opts.get('dtentsai'),
            'HRMOV': opts.get('hrmov'),
            'NUMNOTA': opts.get('nronota'),
            'OBSERVACAO': opts.get('obs'),
        }
        plan = plan_insert_cabecalho(d)
        self.stdout.write(self.style.SUCCESS('Plano de INSERT (dry-run):'))
        self.stdout.write(f"OK: {plan['ok']}")
        if plan['errors']:
            self.stdout.write(self.style.ERROR('Erros:'))
            for e in plan['errors']:
                self.stdout.write(f" - {e}")
        if plan['warnings']:
            self.stdout.write(self.style.WARNING('Avisos:'))
            for w in plan['warnings']:
                self.stdout.write(f" - {w}")
        self.stdout.write('SQL:')
        self.stdout.write(plan['sql'])
        self.stdout.write('Binds:')
        for k, v in plan['binds'].items():
            self.stdout.write(f"  :{k} = {v}")
        self.stdout.write('PK: ' + str(plan['pk']))
        self.stdout.write('FKs: ' + str(plan['fks']))
        self.stdout.write('NOT NULLs: ' + str(plan['not_nulls']))
        self.stdout.write('Triggers: ' + str(plan['triggers']))
        self.stdout.write('Trigger usa NEXTVAL para NUNOTA?: ' + str(plan['uses_trigger_for_nunota']))
        self.stdout.write('Sequences candidatas: ' + str(plan['sequence_candidates']))
        # Extra introspection if available
        if 'all_triggers_using_nextval' in plan:
            self.stdout.write('ALL_TRIGGERS com NEXTVAL/NUNOTA: ' + str(plan['all_triggers_using_nextval']))
        if 'all_sequences_candidates' in plan:
            self.stdout.write('ALL_SEQUENCES candidatas: ' + str(plan['all_sequences_candidates']))
        if 'identity_column_flag' in plan:
            self.stdout.write('NUNOTA é IDENTITY?: ' + str(plan['identity_column_flag']))