"""
Worker IMAP — Coletor de pedidos por e-mail (Fase 1: sem LLM).

Conecta ao IMAP do Titan/Hostinger, lista mensagens UNSEEN na pasta de entrada,
baixa anexos PDF, extrai texto via pdfplumber e cria registros em
AD_PEDIDO_EMAIL_RECEBIDO com status `AGUARDANDO_PARSER`.

A fase 2 (chamada do LLM Ollama) é adicionada na E4 — esta versão deixa os
registros prontos para serem processados depois.

Uso:
    python manage.py colher_pedidos_email
    python manage.py colher_pedidos_email --max 10  # limita a 10 e-mails

Idempotência:
    Anti-duplicação por MESSAGE_ID UNIQUE em AD_PEDIDO_EMAIL_RECEBIDO. Se o
    worker for reiniciado e tentar reprocessar o mesmo e-mail, o INSERT falha
    silenciosamente (caller captura e ignora) e o e-mail é movido novamente
    para a pasta `Processados`.

Pastas no Titan (configuráveis em .env, criar com hífen no webmail):
    EMAIL_IMAP_FOLDER_ENTRADA       (default: Pedidos-Entrada)
    EMAIL_IMAP_FOLDER_PROCESSADOS   (default: Pedidos-Processados)
    EMAIL_IMAP_FOLDER_ERROS         (default: Pedidos-Erros)

Configuração no .env:
    EMAIL_IMAP_HOST, EMAIL_IMAP_PORT (993),
    EMAIL_IMAP_USER, EMAIL_IMAP_PASS,
    PEDIDO_EMAIL_PDF_DIR (caminho base de armazenamento de PDFs).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Coleta pedidos por e-mail (IMAP), arquiva PDFs e cria pré-pedidos."

    def add_arguments(self, parser):
        parser.add_argument(
            '--max', type=int, default=50,
            help='Máximo de e-mails a processar nesta rodada (default 50)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simula a coleta sem gravar nada (debug).',
        )
        parser.add_argument(
            '--skip-imap', action='store_true',
            help='Não conecta IMAP — processa só os AGUARDANDO_PARSER existentes.',
        )
        parser.add_argument(
            '--skip-llm', action='store_true',
            help='Coleta IMAP mas não roda o parser LLM (registros ficam AGUARDANDO_PARSER).',
        )

    def handle(self, *args, **options):
        max_emails: int = options['max']
        dry_run: bool = options['dry_run']
        skip_imap: bool = options['skip_imap']
        skip_llm: bool = options['skip_llm']

        cfg = self._carregar_config()
        self._validar_config(cfg, exigir_imap=not skip_imap)

        processados, ignorados, erros = 0, 0, 0

        # ============================================================
        # FASE 1 — Coleta IMAP (a menos que --skip-imap seja passado)
        # ============================================================
        if not skip_imap:
            try:
                from imap_tools import MailBox, AND  # type: ignore
            except ImportError:
                raise CommandError(
                    "Dependência 'imap-tools' não instalada. Rode: pip install -r requirements.txt"
                )

            self.stdout.write(self.style.NOTICE(
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Conectando IMAP {cfg['host']}:{cfg['port']} "
                f"como {cfg['user']}..."
            ))

            try:
                with MailBox(cfg['host'], port=cfg['port']).login(
                    cfg['user'], cfg['password'], initial_folder=cfg['folder_entrada']
                ) as mailbox:
                    msgs = list(mailbox.fetch(AND(seen=False), limit=max_emails, mark_seen=False))
                    self.stdout.write(f"  → {len(msgs)} e-mail(is) não lido(s) na fila.")

                    for msg in msgs:
                        try:
                            resultado = self._processar_mensagem(msg, cfg, dry_run=dry_run)
                            if resultado == 'PROCESSADO':
                                processados += 1
                                if not dry_run:
                                    mailbox.move([msg.uid], cfg['folder_processados'])
                            elif resultado == 'DUPLICADO':
                                ignorados += 1
                                if not dry_run:
                                    mailbox.move([msg.uid], cfg['folder_processados'])
                            elif resultado == 'SEM_PDF':
                                erros += 1
                                if not dry_run:
                                    mailbox.move([msg.uid], cfg['folder_erros'])
                        except Exception:
                            logger.exception(f"Falha processando UID {msg.uid}")
                            erros += 1
                            if not dry_run:
                                try: mailbox.move([msg.uid], cfg['folder_erros'])
                                except Exception: pass
            except Exception as exc:
                logger.exception("Falha na conexão IMAP")
                raise CommandError(f"Erro IMAP: {exc}")
        else:
            self.stdout.write("  ↪ --skip-imap: pulando fase de coleta IMAP.")

        # ============================================================
        # FASE 2 — Parser LLM (a menos que --skip-llm seja passado)
        # ============================================================
        parseados, erros_parser = 0, 0
        if not skip_llm:
            parseados, erros_parser = self._rodar_parser_llm(dry_run=dry_run, max_proc=max_emails)
        else:
            self.stdout.write("  ↪ --skip-llm: pulando fase de parser LLM.")

        self.stdout.write(self.style.SUCCESS(
            f"  → Concluído: {processados} coletados, {ignorados} duplicados, "
            f"{erros} erros IMAP, {parseados} parseados, {erros_parser} erros parser."
        ))

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _carregar_config(self) -> dict:
        """Lê todas as variáveis de ambiente necessárias num único dict."""
        return {
            'host':               os.getenv('EMAIL_IMAP_HOST', '').strip(),
            'port':               int(os.getenv('EMAIL_IMAP_PORT', '993')),
            'user':               os.getenv('EMAIL_IMAP_USER', '').strip(),
            'password':           os.getenv('EMAIL_IMAP_PASS', ''),
            'folder_entrada':     os.getenv('EMAIL_IMAP_FOLDER_ENTRADA', 'Pedidos-Entrada'),
            'folder_processados': os.getenv('EMAIL_IMAP_FOLDER_PROCESSADOS', 'Pedidos-Processados'),
            'folder_erros':       os.getenv('EMAIL_IMAP_FOLDER_ERROS', 'Pedidos-Erros'),
            'pdf_dir':            os.getenv('PEDIDO_EMAIL_PDF_DIR', '').strip(),
        }

    def _validar_config(self, cfg: dict, exigir_imap: bool = True) -> None:
        # `pdf_dir` sempre exigido. Variáveis IMAP só se a fase 1 for rodar.
        chaves = ['pdf_dir']
        if exigir_imap:
            chaves = ['host', 'user', 'password'] + chaves
        faltando = [k for k in chaves if not cfg[k]]
        if faltando:
            nomes_env = {
                'host': 'EMAIL_IMAP_HOST',
                'user': 'EMAIL_IMAP_USER',
                'password': 'EMAIL_IMAP_PASS',
                'pdf_dir': 'PEDIDO_EMAIL_PDF_DIR',
            }
            raise CommandError(
                f"Configuração incompleta no .env: {', '.join(nomes_env[k] for k in faltando)}"
            )
        Path(cfg['pdf_dir']).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Fase 2: parser LLM (Ollama local)
    # ------------------------------------------------------------------
    def _rodar_parser_llm(self, dry_run: bool = False, max_proc: int = 50) -> tuple[int, int]:
        """Itera sobre registros AGUARDANDO_PARSER e roda o LLM em cada um.

        Retorna (parseados_ok, erros_parser).
        """
        from sankhya_integration.services.oracle_conn import (
            listar_pedidos_email_aguardando_parser,
            atualizar_pedido_email_parser_resultado,
            atualizar_pedido_email_status,
            inserir_pedido_email_item,
            consultar_ultimo_pedido_codparc,
        )
        from sankhya_integration.services.llm_local import extrair_pedido_de_pdf

        registros = listar_pedidos_email_aguardando_parser(limite=max_proc)
        if not registros:
            self.stdout.write("  ↪ Nenhum registro AGUARDANDO_PARSER.")
            return 0, 0

        ok_count, err_count = 0, 0
        self.stdout.write(f"  → {len(registros)} registro(s) para parser LLM.")

        # Contexto reutilizado entre registros (caches simples)
        parceiros_ctx = self._carregar_contexto_parceiros()
        produtos_ctx_global = self._carregar_contexto_produtos()

        for reg in registros:
            recebido_id = reg['id']
            texto = reg.get('pdf_texto') or ''
            try:
                resultado = extrair_pedido_de_pdf(
                    texto_pdf=texto,
                    parceiros_contexto=parceiros_ctx,
                    produtos_contexto=produtos_ctx_global,
                )
            except Exception as exc:
                logger.exception(f"LLM falhou para recebido_id={recebido_id}")
                if not dry_run:
                    atualizar_pedido_email_status(recebido_id, 'ERRO_PARSER',
                                                   motivo_descarte=f'LLM falhou: {exc}')
                err_count += 1
                continue

            if not resultado.get('ok'):
                if not dry_run:
                    atualizar_pedido_email_status(
                        recebido_id, 'ERRO_PARSER',
                        motivo_descarte=resultado.get('error', 'parser falhou'),
                    )
                err_count += 1
                continue

            if dry_run:
                self.stdout.write(f"  ✓ [DRY-RUN] Parsearia recebido #{recebido_id}: "
                                  f"{len(resultado.get('itens', []))} itens.")
                ok_count += 1
                continue

            # Resolve sugestões CODEMP/CODTIPVENDA pelo último pedido do CODPARC
            codparc_sug = (resultado.get('cliente') or {}).get('codparc_sugerido')
            codemp_sug = None
            codtv_sug = None
            if codparc_sug:
                ultimo = consultar_ultimo_pedido_codparc(codparc_sug)
                if ultimo:
                    codemp_sug = ultimo.get('codemp')
                    codtv_sug = ultimo.get('codtipvenda')

            # Persiste resultado no cabeçalho
            atualizar_pedido_email_parser_resultado(recebido_id, {
                'LLM_RESPOSTA':         resultado.get('resposta_crua'),
                'LLM_MODELO':           resultado.get('modelo'),
                'LLM_TOKENS_IN':        resultado.get('tokens_in'),
                'LLM_TOKENS_OUT':       resultado.get('tokens_out'),
                'LLM_CONFIANCA_GERAL':  resultado.get('confianca_geral'),
                'CODPARC_SUGERIDO':     codparc_sug,
                'CODEMP_SUGERIDO':      codemp_sug,
                'DTNEG_SUGERIDA':       self._parse_data(resultado.get('data_negociacao')),
                'CODTIPVENDA_SUGERIDO': codtv_sug,
                'OBSERVACAO_EXTRAIDA':  resultado.get('observacao'),
            })

            # Persiste itens
            for idx, it in enumerate(resultado.get('itens', []), start=1):
                inserir_pedido_email_item({
                    'RECEBIDO_ID':       recebido_id,
                    'SEQUENCIA':         idx,
                    'DESCRICAO_PDF':     it.get('descricao_pdf'),
                    'CODPROD_SUGERIDO':  it.get('codprod_sugerido'),
                    'CODPROD_CONFIANCA': it.get('codprod_confianca'),
                    'QTD':               it.get('qtd'),
                    'CODVOL':            it.get('codvol'),
                    'PRECO_UNIT':        it.get('preco_unit'),
                })
            ok_count += 1
            self.stdout.write(f"  ✓ Recebido #{recebido_id} parseado: "
                              f"{len(resultado.get('itens', []))} itens, conf={resultado.get('confianca_geral'):.2f}.")

        return ok_count, err_count

    def _carregar_contexto_parceiros(self) -> list[dict]:
        """Top 50 parceiros mais ativos para o prompt do LLM."""
        try:
            from sankhya_integration.services.oracle_conn import obter_conexao_oracle
            with obter_conexao_oracle() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM (
                        SELECT p.CODPARC, p.NOMEPARC, p.CGC_CPF,
                               COUNT(c.NUNOTA) AS qtd
                          FROM TGFPAR p
                          LEFT JOIN TGFCAB c ON c.CODPARC = p.CODPARC
                                            AND c.CODTIPOPER IN (34, 35, 37)
                                            AND NVL(c.STATUSNOTA, 'A') <> 'E'
                                            AND c.DTNEG >= ADD_MONTHS(SYSDATE, -12)
                         GROUP BY p.CODPARC, p.NOMEPARC, p.CGC_CPF
                         ORDER BY qtd DESC NULLS LAST
                    ) WHERE ROWNUM <= 50
                """)
                rows = cur.fetchall()
                return [{'codparc': r[0], 'nome': r[1], 'cgc': r[2]} for r in rows]
        except Exception:
            logger.exception("Falha carregando contexto de parceiros")
            return []

    def _carregar_contexto_produtos(self) -> list[dict]:
        """Top 100 produtos para o prompt do LLM."""
        try:
            from sankhya_integration.services.oracle_conn import obter_conexao_oracle
            with obter_conexao_oracle() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM (
                        SELECT p.CODPROD, p.DESCRPROD, p.CODVOLPADRAO
                          FROM TGFPRO p
                         WHERE NVL(p.ATIVO, 'S') = 'S'
                         ORDER BY p.CODPROD ASC
                    ) WHERE ROWNUM <= 100
                """)
                rows = cur.fetchall()
                return [{'codprod': r[0], 'descr': r[1], 'codvol': r[2]} for r in rows]
        except Exception:
            logger.exception("Falha carregando contexto de produtos")
            return []

    def _parse_data(self, s):
        """Parser tolerante de YYYY-MM-DD ou DD/MM/YYYY → date."""
        if not s: return None
        from datetime import date as _date
        try:
            if isinstance(s, _date): return s
            s = str(s).strip()
            if len(s) >= 10 and s[4] == '-':
                y, m, d = s[:10].split('-')
                return _date(int(y), int(m), int(d))
            if len(s) >= 10 and s[2] == '/':
                d, m, y = s[:10].split('/')
                return _date(int(y), int(m), int(d))
        except Exception:
            return None
        return None

    def _processar_mensagem(self, msg, cfg: dict, dry_run: bool = False) -> str:
        """Processa um e-mail.

        Retorna:
          'PROCESSADO' → PDF salvo + INSERT em AD_PEDIDO_EMAIL_RECEBIDO
          'DUPLICADO'  → MESSAGE_ID já existe na tabela (anti-duplicação)
          'SEM_PDF'    → e-mail não tem anexo PDF ou PDF ilegível
        """
        # Imports tardios
        from sankhya_integration.services.oracle_conn import (
            consultar_pedido_email_por_message_id, inserir_pedido_email_recebido,
        )

        message_id = (msg.headers.get('message-id', ('',))[0]
                      if hasattr(msg, 'headers') else None) or msg.uid
        message_id = message_id.strip() if isinstance(message_id, str) else message_id

        # Anti-duplicação
        if message_id and consultar_pedido_email_por_message_id(message_id):
            self.stdout.write(f"  ↪ Duplicado (MESSAGE_ID={message_id}); ignorando.")
            return 'DUPLICADO'

        # Procura primeiro anexo PDF
        pdf_attachment = next(
            (a for a in msg.attachments if (a.filename or '').lower().endswith('.pdf')),
            None,
        )
        if not pdf_attachment:
            self.stdout.write(f"  ⚠ E-mail UID {msg.uid} sem PDF anexo; movendo para Erros.")
            return 'SEM_PDF'

        # Salva o PDF em disco
        recebido_em = msg.date or datetime.now()
        ano = f"{recebido_em.year:04d}"
        mes = f"{recebido_em.month:02d}"
        pasta = Path(cfg['pdf_dir']) / ano / mes
        pasta.mkdir(parents=True, exist_ok=True)
        nome_arquivo = self._nome_arquivo_seguro(message_id or msg.uid)
        pdf_path = pasta / f"{nome_arquivo}.pdf"

        if not dry_run:
            with open(pdf_path, 'wb') as fh:
                fh.write(pdf_attachment.payload)

        # Extrai texto
        try:
            pdf_texto = self._extrair_texto_pdf(str(pdf_path) if not dry_run else None,
                                                payload=pdf_attachment.payload)
        except Exception:
            logger.exception(f"Falha ao extrair texto do PDF UID {msg.uid}")
            pdf_texto = None

        if not pdf_texto:
            self.stdout.write(f"  ⚠ PDF UID {msg.uid} sem texto extraível; STATUS=ERRO_PDF.")
            if dry_run: return 'SEM_PDF'
            inserir_pedido_email_recebido({
                'MESSAGE_ID': message_id,
                'REMETENTE': msg.from_,
                'ASSUNTO': msg.subject,
                'RECEBIDO_EM': recebido_em,
                'PROCESSADO_EM': datetime.now(),
                'PDF_PATH': str(pdf_path),
                'PDF_TEXTO': None,
                'STATUS': 'ERRO_PDF',
            })
            return 'PROCESSADO'  # registro criado, embora com erro

        # Persiste o registro
        if dry_run:
            self.stdout.write(f"  ✓ [DRY-RUN] Inseriria recebido para {message_id}")
            return 'PROCESSADO'

        res = inserir_pedido_email_recebido({
            'MESSAGE_ID': message_id,
            'REMETENTE': msg.from_,
            'ASSUNTO': msg.subject,
            'RECEBIDO_EM': recebido_em,
            'PROCESSADO_EM': datetime.now(),
            'PDF_PATH': str(pdf_path),
            'PDF_TEXTO': pdf_texto,
            'STATUS': 'AGUARDANDO_PARSER',
        })
        if not res.get('ok'):
            err = (res.get('error') or '').lower()
            # ORA-00001 (UNIQUE violation) = corrida com outro worker → tratar como duplicado
            if 'ora-00001' in err or 'unique constraint' in err:
                self.stdout.write(f"  ↪ Race-condition: outro worker já gravou {message_id}.")
                return 'DUPLICADO'
            raise RuntimeError(f"Falha gravando recebido: {res.get('error')}")

        self.stdout.write(f"  ✓ Pré-pedido #{res['id']} criado ({message_id}).")
        return 'PROCESSADO'

    def _extrair_texto_pdf(self, path: str | None, payload: bytes) -> str:
        """Extrai texto do PDF via pdfplumber. Aceita path ou bytes (dry-run)."""
        try:
            import pdfplumber  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Dependência 'pdfplumber' não instalada. Rode: pip install -r requirements.txt"
            )

        partes: list[str] = []
        if path:
            with pdfplumber.open(path) as pdf:
                for pagina in pdf.pages:
                    txt = pagina.extract_text() or ''
                    if txt.strip(): partes.append(txt)
        else:
            from io import BytesIO
            with pdfplumber.open(BytesIO(payload)) as pdf:
                for pagina in pdf.pages:
                    txt = pagina.extract_text() or ''
                    if txt.strip(): partes.append(txt)

        return '\n'.join(partes).strip()

    def _nome_arquivo_seguro(self, base: str) -> str:
        """Sanitiza um identificador para usar como nome de arquivo."""
        import re
        s = (base or 'sem-id').strip().strip('<>')
        s = re.sub(r'[^A-Za-z0-9._-]+', '_', s)
        return s[:120] or 'sem-id'
