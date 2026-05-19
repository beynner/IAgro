"""
Management command — refresh do cache de saldo de lotes do Rastreio.

Chama `refresh_saldo_lote_cache()` em `oracle_conn.py`, que faz TRUNCATE +
INSERT-SELECT da view `ANDRE_IAGRO_SALDO_LOTE` pra tabela materializada
`AD_SALDO_LOTE_CACHE`.

Uso (Windows Task Scheduler — a cada 5 min):

    cd "D:\\TI\\NexusGTi\\IAgro\\IAgro"
    .\\.venv\\Scripts\\python.exe manage.py refresh_saldo_lote

Exit codes:
    0   sucesso (linhas inseridas)
    1   falha (erro Oracle, conexão, escrita desabilitada, etc)

Saída padrão: 1 linha JSON com `{ok, rows, duracao_s}` pra parsing fácil
no Task Scheduler / monitoramento externo. Logger.info também grava no
console com mais detalhe.
"""
import json
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Atualiza AD_SALDO_LOTE_CACHE com snapshot de ANDRE_IAGRO_SALDO_LOTE."

    def handle(self, *args, **options):
        # Import tardio pra evitar carga do Oracle no boot do manage.py check
        from sankhya_integration.services.oracle_conn import refresh_saldo_lote_cache

        resultado = refresh_saldo_lote_cache()

        # Saída JSON 1-linha — fácil de parsear em monitoring
        self.stdout.write(json.dumps(resultado, ensure_ascii=False))

        if not resultado.get('ok'):
            sys.exit(1)
