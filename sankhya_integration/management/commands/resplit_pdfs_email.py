"""
Backfill: re-split físico de PDFs de pré-pedidos legados.

Cenário: registros gravados ANTES do deploy do split físico (Fase 1)
têm múltiplos SUB_IDs apontando pro MESMO arquivo `<MSGID>.pdf` (PDF
inteiro). Este comando rebusca cada PDF original, roda o `split_pedidos()`
+ `split_pdf_fisico()` atual e atualiza `PDF_PATH` por SUB_ID pra apontar
pro arquivo `_sub{N}.pdf` correspondente.

Idempotente: registros já corrigidos (PDF_PATH com sufixo `_sub`) são
ignorados. Pode rodar múltiplas vezes sem efeito colateral.

Status preservados: registros CONFIRMADO/DESCARTADO não são tocados —
apenas pré-pedidos ainda na fila do operador (PENDENTE_REVISAO,
ERRO_PARSER, AGUARDANDO_PARSER).

Uso:
    python manage.py resplit_pdfs_email           # executa
    python manage.py resplit_pdfs_email --dry-run # mostra o que faria
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from sankhya_integration.management.commands.colher_pedidos_email import (
    split_pedidos,
    split_pdf_fisico,
)
from sankhya_integration.services.oracle_conn import obter_conexao_oracle

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ("Re-splita PDFs de pré-pedidos legados (1 PDF compartilhado entre vários SUB_IDs). "
            "Idempotente — registros já corrigidos são ignorados.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Mostra o que seria feito, sem escrever no banco nem em disco.',
        )

    def handle(self, *args, **options):
        dry_run: bool = options['dry_run']

        try:
            from pypdf import PdfReader  # noqa: F401  (só pra validar disponibilidade)
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "pypdf não instalado. Rode `pip install -r requirements.txt`."
            ))
            return

        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "pdfplumber não instalado. Rode `pip install -r requirements.txt`."
            ))
            return

        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1) Detecta grupos legados: mesmos MESSAGE_ID + PDF_PATH com 2+ SUB_IDs.
            #    Filtra status fechados pra não mexer em pedidos já confirmados.
            cur.execute("""
                SELECT MESSAGE_ID, PDF_PATH, COUNT(*) AS N
                FROM AD_PEDIDO_EMAIL_RECEBIDO
                WHERE STATUS NOT IN ('CONFIRMADO', 'DESCARTADO')
                  AND PDF_PATH IS NOT NULL
                GROUP BY MESSAGE_ID, PDF_PATH
                HAVING COUNT(*) > 1
            """)
            grupos = cur.fetchall()

        if not grupos:
            self.stdout.write(self.style.SUCCESS(
                "Nenhum grupo legado encontrado. Nada a fazer."
            ))
            return

        self.stdout.write(self.style.NOTICE(
            f"Encontrados {len(grupos)} grupo(s) legado(s) com PDF compartilhado."
        ))

        corrigidos = 0
        ignorados = 0
        erros = 0

        for message_id, pdf_path, n_subids in grupos:
            resultado = self._processar_grupo(
                message_id=message_id,
                pdf_path=pdf_path,
                n_subids=int(n_subids),
                dry_run=dry_run,
            )
            if resultado == 'CORRIGIDO':
                corrigidos += int(n_subids)
            elif resultado == 'IGNORADO':
                ignorados += 1
            elif resultado == 'ERRO':
                erros += 1

        self.stdout.write(self.style.SUCCESS(
            f"Concluído: {corrigidos} pré-pedido(s) atualizado(s), "
            f"{ignorados} grupo(s) ignorado(s), {erros} erro(s)."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "[DRY-RUN] Nenhuma escrita foi feita. Rode sem --dry-run pra aplicar."
            ))

    # ------------------------------------------------------------------
    # Processamento de 1 grupo
    # ------------------------------------------------------------------
    def _processar_grupo(self, message_id: str, pdf_path: str,
                         n_subids: int, dry_run: bool) -> str:
        """Processa 1 grupo (mesmo MESSAGE_ID + PDF_PATH compartilhado).

        Retorna 'CORRIGIDO' | 'IGNORADO' | 'ERRO'.
        """
        prefixo = f"  [{message_id} ({n_subids} SUB_IDs)]"

        # Idempotência: se PDF_PATH já tem sufixo _sub, foi corrigido antes.
        if '_sub' in (pdf_path or ''):
            self.stdout.write(f"{prefixo} já corrigido (sufixo _sub presente); pulando.")
            return 'IGNORADO'

        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            self.stdout.write(self.style.WARNING(
                f"{prefixo} PDF não encontrado em disco: {pdf_path}; pulando."
            ))
            return 'IGNORADO'

        # 2) Extrai páginas do PDF original
        try:
            paginas = self._extrair_paginas(pdf_file)
        except Exception:
            logger.exception(f"Falha extraindo PDF {pdf_path}")
            self.stdout.write(self.style.ERROR(
                f"{prefixo} falha extraindo PDF; pulando."
            ))
            return 'ERRO'

        if not paginas:
            self.stdout.write(self.style.WARNING(
                f"{prefixo} PDF sem texto extraível; pulando."
            ))
            return 'IGNORADO'

        # 3) Roda o split atual (com heurística de Caso 1+2)
        pedidos_novos = split_pedidos(paginas)
        if len(pedidos_novos) != n_subids:
            self.stdout.write(self.style.WARNING(
                f"{prefixo} novo split detectou {len(pedidos_novos)} pedido(s) vs "
                f"{n_subids} SUB_IDs no banco. Provável heurística divergente. "
                f"Pulando — opere manualmente se precisar."
            ))
            return 'IGNORADO'

        # 4) Carrega IDs reais (ordem por SUB_ID ASC pra zip com pedidos_novos)
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT ID, SUB_ID
                   FROM AD_PEDIDO_EMAIL_RECEBIDO
                   WHERE MESSAGE_ID = :msg AND PDF_PATH = :pdf
                   ORDER BY SUB_ID ASC""",
                {'msg': message_id, 'pdf': pdf_path},
            )
            rows = cur.fetchall()

        if dry_run:
            ranges = [(p['start_page'], p['end_page']) for p in pedidos_novos]
            self.stdout.write(self.style.NOTICE(
                f"{prefixo} [DRY-RUN] criaria {n_subids} arquivo(s) cobrindo páginas {ranges}"
            ))
            return 'CORRIGIDO'  # contagem otimista pra relatório

        # 5) Split físico (cria <base>_sub{N}.pdf no mesmo diretório)
        base_nome = pdf_file.stem  # nome sem .pdf
        try:
            caminhos = split_pdf_fisico(
                str(pdf_file), pedidos_novos,
                pasta_destino=pdf_file.parent, base_nome=base_nome,
            )
        except Exception:
            logger.exception(f"Falha em split_pdf_fisico {pdf_path}")
            self.stdout.write(self.style.ERROR(
                f"{prefixo} falha gerando sub-arquivos; pulando."
            ))
            return 'ERRO'

        if len(caminhos) != n_subids:
            self.stdout.write(self.style.WARNING(
                f"{prefixo} split_pdf_fisico devolveu {len(caminhos)} caminho(s) (esperado {n_subids}); pulando."
            ))
            return 'IGNORADO'

        # 6) UPDATE 1 a 1 (zip por SUB_ID ASC)
        try:
            with obter_conexao_oracle() as conn:
                cur = conn.cursor()
                for (id_, sub_id), caminho in zip(rows, caminhos):
                    cur.execute(
                        "UPDATE AD_PEDIDO_EMAIL_RECEBIDO SET PDF_PATH = :pdf WHERE ID = :id",
                        {'pdf': caminho, 'id': int(id_)},
                    )
                conn.commit()
        except Exception:
            logger.exception(f"Falha no UPDATE PDF_PATH em {message_id}")
            self.stdout.write(self.style.ERROR(
                f"{prefixo} falha no UPDATE; rollback automático."
            ))
            return 'ERRO'

        self.stdout.write(self.style.SUCCESS(
            f"{prefixo} OK: {n_subids} pre-pedido(s) atualizados; arquivos _sub criados."
        ))
        return 'CORRIGIDO'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extrair_paginas(self, pdf_file: Path) -> list[tuple[int, str]]:
        """Extrai texto por página via pdfplumber. Mesmo padrão do worker."""
        import pdfplumber
        paginas: list[tuple[int, str]] = []
        with pdfplumber.open(str(pdf_file)) as pdf:
            for pagina in pdf.pages:
                txt = pagina.extract_text() or ''
                paginas.append((pagina.page_number, txt))
        return paginas
