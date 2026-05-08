"""
Worker IMAP — Coletor de pedidos por e-mail (Fase 1 IMAP + Fase 2 LLM).

Conecta ao IMAP do Titan/Hostinger, lista mensagens UNSEEN na pasta de entrada,
baixa anexos PDF, extrai texto via pdfplumber, **divide o texto em N pedidos**
quando o PDF traz vários (ex: rede de supermercado com 1 PDF por loja), e
cria N registros em AD_PEDIDO_EMAIL_RECEBIDO (mesmo MESSAGE_ID, SUB_ID 1..N)
com status `AGUARDANDO_PARSER`.

Fase 2: chama o LLM (Ollama qwen2.5:14b-instruct) para cada registro
individualmente, depois usa fuzzy matching (services.matching) contra
TGFPAR/TGFPRO para resolver CODPARC e CODPROD em Python — o LLM nunca
recebe contexto de IDs, evita alucinação.

Uso:
    python manage.py colher_pedidos_email
    python manage.py colher_pedidos_email --max 10  # limita a 10 e-mails

Idempotência:
    Anti-duplicação por (MESSAGE_ID, SUB_ID) UNIQUE em AD_PEDIDO_EMAIL_RECEBIDO.
    Se o worker for reiniciado e tentar reprocessar o mesmo e-mail, o INSERT
    falha silenciosamente (caller captura e ignora).

Pastas no Titan (configuráveis em .env, criar com hífen no webmail):
    EMAIL_IMAP_FOLDER_ENTRADA       (default: Pedidos-Entrada)
    EMAIL_IMAP_FOLDER_PROCESSADOS   (default: Pedidos-Processados)
    EMAIL_IMAP_FOLDER_ERROS         (default: Pedidos-Erros)

Configuração no .env:
    EMAIL_IMAP_HOST, EMAIL_IMAP_PORT (993),
    EMAIL_IMAP_USER, EMAIL_IMAP_PASS,
    PEDIDO_EMAIL_PDF_DIR (caminho base de armazenamento de PDFs),
    OLLAMA_HOST, OLLAMA_MODELO, OLLAMA_TIMEOUT_SEGUNDOS, OLLAMA_MAX_RETRIES.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


# Mapa de layouts conhecidos -> regex que identifica início de cada pedido
# dentro do texto. Para layouts ainda não plugados, o sistema cai em
# 'GENERICO' (sem split — 1 pedido cobrindo o PDF inteiro). Adicionar
# layout novo = 1 entrada aqui (regex de header) + 1 prompt variant em
# `llm_local.py` (PROMPTS_POR_LAYOUT).
_HEADERS_POR_LAYOUT: dict[str, re.Pattern] = {
    'CONSINCO_RELPED': re.compile(
        r'PEDIDO\s+DE\s+COMPRAS\s+PEDIDO\s+PENDENTE\s+DE\s+APROVA[CÇ][AÃ]O',
        re.IGNORECASE,
    ),
    # Adicione novos layouts aqui. Ex:
    # 'COBASI_FLEX': re.compile(r'COBASI[\s\S]+?Pedido\s+nº', re.IGNORECASE),
}

# Backward-compat alias — usado em testes antigos
_REGEX_INICIO_PEDIDO = _HEADERS_POR_LAYOUT['CONSINCO_RELPED']


def detectar_layout(texto: str) -> str:
    """Identifica o layout do PDF pelo conteúdo extraído.

    Procura por marcadores de cada layout conhecido no _HEADERS_POR_LAYOUT.
    Cai em 'GENERICO' se nenhum match — comportamento seguro pra layouts
    novos: o pedido vai pra fila com fallback de 1 pedido único + prompt
    LLM neutro, e o operador corrige na revisão. Após repetidas confirmações
    do mesmo cliente, o aprendizado por alias acelera a curva.
    """
    if not texto:
        return 'GENERICO'
    for nome_layout, regex in _HEADERS_POR_LAYOUT.items():
        if regex.search(texto):
            return nome_layout
    return 'GENERICO'

# Heurística pra contar itens aproximados num bloco — usada pra detectar
# "header repetido em página de continuação" (Caso 2). Match em código
# numérico de 4-6 dígitos seguido de letra (padrão típico do Consinco
# "8117 PIMENTAO..."). Outros layouts podem precisar regex diferente,
# mas como o uso é só pra desambiguar continuação vs novo pedido,
# falsos negativos só causam pedidos extras (o operador percebe).
_REGEX_ITEM_APROX = re.compile(r'\b\d{4,6}\b\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]', re.IGNORECASE)


def _contar_itens_aproximado(texto: str) -> int:
    """Estima nº de itens num bloco de texto pra heurística de continuação."""
    return len(_REGEX_ITEM_APROX.findall(texto or ''))


def split_pedidos(paginas: list[tuple[int, str]],
                  layout: str | None = None) -> list[dict]:
    """Divide páginas do PDF em N pedidos.

    Recebe lista `[(page_number, page_text), ...]` (1-indexed). Devolve
    lista de dicts:
        [{'sub_id', 'start_page', 'end_page', 'text', 'layout'}, ...]

    Quando `layout=None`, detecta automaticamente via `detectar_layout()`.

    Heurísticas (cobrem 2 casos comuns de PDF multi-pedido em layouts
    com header reconhecido):
      - Caso 1: pedido transborda pra próxima página SEM repetir o header.
        -> A página seguinte sem header é anexada ao pedido em construção.
      - Caso 2: o layout repete o header em toda página de continuação
        (ex: alguns Consinco). Detecção: bloco "novo" com <2 itens
        aproximados é tratado como continuação do anterior.

    Para layout 'GENERICO' (sem regex de header), devolve 1 pedido único
    cobrindo todas as páginas — fallback seguro pra PDFs/textos novos.
    """
    if not paginas:
        return []

    if layout is None:
        texto_amostra = '\n'.join(t for _, t in paginas[:3]) or ''
        layout = detectar_layout(texto_amostra)

    regex_header = _HEADERS_POR_LAYOUT.get(layout)
    if not regex_header:
        # Layout sem split (genérico): tudo num só pedido, range = pgs todas
        texto_completo = '\n'.join(t for _, t in paginas).strip()
        return [{
            'sub_id':     1,
            'start_page': paginas[0][0],
            'end_page':   paginas[-1][0],
            'text':       texto_completo,
            'layout':     layout,
        }]

    pedidos: list[dict] = []
    current: dict | None = None

    for page_num, page_text in paginas:
        page_text = page_text or ''
        has_header = bool(regex_header.search(page_text))

        if has_header:
            if current is None:
                current = {'start_page': page_num, 'end_page': page_num, 'text': page_text}
            elif _contar_itens_aproximado(page_text) < 2:
                # Caso 2: novo header detectado mas poucos itens =
                # continuação do anterior com cabeçalho repetido.
                current['end_page'] = page_num
                current['text'] = (current['text'] + '\n' + page_text).strip()
            else:
                # Pedido novo legítimo
                pedidos.append(current)
                current = {'start_page': page_num, 'end_page': page_num, 'text': page_text}
        else:
            # Sem header — continuação (Caso 1) ou primeira página de
            # PDF sem cabeçalho conhecido (fallback).
            if current is None:
                current = {'start_page': page_num, 'end_page': page_num, 'text': page_text}
            else:
                current['end_page'] = page_num
                current['text'] = (current['text'] + '\n' + page_text).strip()

    if current:
        pedidos.append(current)

    # Atribui sub_id 1-indexed e layout em cada pedido
    for idx, p in enumerate(pedidos, start=1):
        p['sub_id'] = idx
        p['text']   = (p['text'] or '').strip()
        p['layout'] = layout

    return pedidos


def split_pdf_fisico(pdf_path: str, pedidos: list[dict],
                     pasta_destino: Path, base_nome: str) -> list[str]:
    """Para cada pedido, extrai páginas [start_page..end_page] do PDF
    original e grava como `<base_nome>_sub{N}.pdf` em `pasta_destino`.

    Comportamento:
      - 1 pedido só -> retorna [pdf_path] sem criar arquivo extra.
      - N pedidos -> cria N arquivos com sufixo `_sub{N}` e retorna
        a lista de caminhos absolutos (na ordem dos pedidos).
      - Sem pypdf instalado -> fallback: todos apontam pro PDF original
        (operador continua scrollando, mas não trava o pipeline).

    O PDF original é preservado em disco — útil pra arquivamento e pra
    futuro endpoint "ver PDF completo".
    """
    if not pedidos:
        return []
    if len(pedidos) == 1:
        return [pdf_path]

    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except ImportError:
        logger.warning("pypdf não instalado — split físico desabilitado; "
                       "todos os pré-pedidos apontarão pro PDF completo.")
        return [pdf_path] * len(pedidos)

    try:
        reader = PdfReader(pdf_path)
    except Exception:
        logger.exception(f"Falha lendo PDF {pdf_path} para split físico")
        return [pdf_path] * len(pedidos)

    caminhos: list[str] = []
    total_paginas = len(reader.pages)
    for p in pedidos:
        writer = PdfWriter()
        # page_number é 1-indexed; pypdf é 0-indexed
        ini = max(0, int(p['start_page']) - 1)
        fim = min(total_paginas, int(p['end_page']))
        for idx_pag in range(ini, fim):
            writer.add_page(reader.pages[idx_pag])
        out_path = pasta_destino / f"{base_nome}_sub{p['sub_id']}.pdf"
        try:
            with open(out_path, 'wb') as fh:
                writer.write(fh)
            caminhos.append(str(out_path))
        except Exception:
            logger.exception(f"Falha gravando {out_path}; fallback pro PDF original")
            caminhos.append(pdf_path)

    return caminhos


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
                    self.stdout.write(f"  -> {len(msgs)} e-mail(is) não lido(s) na fila.")

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
            self.stdout.write("  -> --skip-imap: pulando fase de coleta IMAP.")

        # ============================================================
        # FASE 2 — Parser LLM (a menos que --skip-llm seja passado)
        # ============================================================
        parseados, erros_parser = 0, 0
        if not skip_llm:
            parseados, erros_parser = self._rodar_parser_llm(dry_run=dry_run, max_proc=max_emails)
        else:
            self.stdout.write("  -> --skip-llm: pulando fase de parser LLM.")

        self.stdout.write(self.style.SUCCESS(
            f"  -> Concluído: {processados} coletados, {ignorados} duplicados, "
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
        """Itera sobre registros AGUARDANDO_PARSER, roda LLM em cada um e
        casa CODPARC/CODPROD via fuzzy matching em Python.

        Cada registro AGUARDANDO_PARSER já é UM pedido (split foi feito na
        fase IMAP). O LLM extrai dados textuais; o matching resolve IDs.

        Retorna (parseados_ok, erros_parser).
        """
        from sankhya_integration.services.oracle_conn import (
            listar_pedidos_email_aguardando_parser,
            atualizar_pedido_email_parser_resultado,
            atualizar_pedido_email_status,
            inserir_pedido_email_item,
            deletar_itens_do_pedido_email,
            consultar_ultimo_pedido_codparc,
        )
        from sankhya_integration.services.llm_local import extrair_pedido_de_pdf
        from sankhya_integration.services import matching, pdf_parsers

        registros = listar_pedidos_email_aguardando_parser(limite=max_proc)
        if not registros:
            self.stdout.write("  -> Nenhum registro AGUARDANDO_PARSER.")
            return 0, 0

        ok_count, err_count = 0, 0
        self.stdout.write(f"  -> {len(registros)} registro(s) para parser LLM.")

        # Pré-carrega caches do matching uma vez por execução do worker
        parceiros = matching.carregar_parceiros()
        produtos = matching.carregar_produtos()

        for reg in registros:
            recebido_id = reg['id']
            texto = reg.get('pdf_texto') or ''
            # Detecta layout no momento do parser (não é persistido).
            # Layouts conhecidos usam prompt específico com avisos de
            # erros recorrentes; desconhecidos caem em GENERICO (neutro).
            layout = detectar_layout(texto)

            # Etapa 0 — parser Python específico do layout (regex + pdfplumber).
            # Se conseguir extrair + validar, pulamos o LLM (~50ms vs ~3min).
            # Layouts ausentes do registry, parsers que devolvem None ou erros
            # de exceção caem em fallback transparente pro LLM logo abaixo.
            # Telemetria: campo `modelo` no resultado distingue origem
            # ('regex_consinco_v1' vs 'qwen2.5:14b-instruct').
            resultado = pdf_parsers.tentar_parseamento(
                layout=layout,
                pdf_path=reg.get('pdf_path'),
                texto=texto,
                recebido_id=recebido_id,
            )
            if resultado is not None:
                self.stdout.write(
                    f"  -> Recebido #{recebido_id} via parser regex "
                    f"(layout={layout}, sem LLM)"
                )
            else:
                # Etapa 1 — fallback LLM (fluxo original)
                try:
                    resultado = extrair_pedido_de_pdf(texto, layout=layout)
                except Exception as exc:
                    logger.exception(f"LLM falhou para recebido_id={recebido_id} layout={layout}")
                    if not dry_run:
                        atualizar_pedido_email_status(recebido_id, 'ERRO_PARSER',
                                                       motivo_descarte=f'LLM falhou: {exc}')
                    err_count += 1
                    continue

            # Validação de sucesso — vale tanto pra parser regex quanto pra LLM
            if not resultado.get('ok'):
                if not dry_run:
                    atualizar_pedido_email_status(
                        recebido_id, 'ERRO_PARSER',
                        motivo_descarte=resultado.get('error', 'parser falhou'),
                    )
                err_count += 1
                continue

            # Matching CODPARC pelo nome extraído
            cliente_nome = resultado.get('cliente_nome') or ''
            codparc_sug, score_parc, _ = matching.casar_codparc(cliente_nome, parceiros)

            # Itens: extrai dados e roda matching de produto.
            # Passa cod_cliente (extraído pelo LLM em pedidos Consinco) +
            # codparc_sug pro matching — Etapa 0 acerta direto se já tem
            # vinculação histórica em AD_CLIENTE_PRODUTO_COD.
            itens_resolvidos: list[dict] = []
            scores_prod: list[float] = []
            for idx, it in enumerate(resultado.get('itens') or [], start=1):
                descr = it.get('descricao_pdf') or ''
                cod_cliente = it.get('cod_cliente')
                codprod_sug, score_prod, _ = matching.casar_codprod(
                    descr, produtos,
                    codparc=codparc_sug,
                    cod_cliente=cod_cliente,
                )
                itens_resolvidos.append({
                    'sequencia':         idx,
                    'descricao_pdf':     descr,
                    'cod_cliente':       cod_cliente,
                    'codprod_sugerido':  codprod_sug,
                    'codprod_confianca': round(score_prod / 100.0, 2),
                    'qtd':               it.get('qtd'),
                    'codvol':            it.get('codvol'),
                    'preco_unit':        it.get('preco_unit'),
                })
                if codprod_sug:
                    scores_prod.append(score_prod)

            # Confiança geral = média(score_parc + scores_prod normalizados)
            todos_scores = ([score_parc] if codparc_sug else []) + scores_prod
            conf_geral = round(sum(todos_scores) / 100.0 / len(todos_scores), 2) if todos_scores else 0.0

            if dry_run:
                self.stdout.write(
                    f"  OK: [DRY-RUN] #{recebido_id}: cliente={cliente_nome!r} "
                    f"-> CODPARC={codparc_sug} ({score_parc:.0f}); "
                    f"{len(itens_resolvidos)} itens; conf={conf_geral:.2f}"
                )
                ok_count += 1
                continue

            # Resolve sugestões CODEMP/CODTIPVENDA pelo último pedido deste CODPARC
            codemp_sug, codtv_sug = None, None
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
                'LLM_CONFIANCA_GERAL':  conf_geral,
                'CODPARC_SUGERIDO':     codparc_sug,
                'CODEMP_SUGERIDO':      codemp_sug,
                'DTNEG_SUGERIDA':       self._parse_data(resultado.get('data_negociacao')),
                'CODTIPVENDA_SUGERIDO': codtv_sug,
                'OBSERVACAO_EXTRAIDA':  resultado.get('observacao'),
            })

            # DEFESA CONTRA DUPLICAÇÃO: deleta qualquer item residual do
            # mesmo recebido_id antes de inserir os novos. Cobre cenários:
            #   - Reparser parcial (alguns DELETEs falharam)
            #   - Worker rodando em paralelo com operação manual
            #   - Re-parser de registro que já tinha itens de uma execução anterior
            # Já era pra estar limpo (api_email_reparser deleta), mas defesa
            # em camadas evita reincidência. Idempotente: 0 itens = 0 deletes.
            res_del = deletar_itens_do_pedido_email(recebido_id)
            if res_del.get('rows'):
                logger.info(
                    f"Removidos {res_del.get('rows')} itens orfaos do recebido_id={recebido_id} antes do reparser"
                )

            # Persiste itens. COD_CLIENTE só é gravado se a coluna existir
            # (resilient ao schema; a função inserir_pedido_email_item ignora
            # se a migration AD_CLIENTE_PRODUTO_COD ainda não rodou).
            for it in itens_resolvidos:
                inserir_pedido_email_item({
                    'RECEBIDO_ID':       recebido_id,
                    'SEQUENCIA':         it['sequencia'],
                    'DESCRICAO_PDF':     it['descricao_pdf'],
                    'COD_CLIENTE':       it.get('cod_cliente'),
                    'CODPROD_SUGERIDO':  it['codprod_sugerido'],
                    'CODPROD_CONFIANCA': it['codprod_confianca'],
                    'QTD':               it['qtd'],
                    'CODVOL':            it['codvol'],
                    'PRECO_UNIT':        it['preco_unit'],
                })
            ok_count += 1
            self.stdout.write(
                f"  OK: Recebido #{recebido_id} parseado: cliente={cliente_nome[:40]!r} "
                f"-> CODPARC={codparc_sug}, {len(itens_resolvidos)} itens, conf={conf_geral:.2f}."
            )

        return ok_count, err_count

    def _parse_data(self, s):
        """Parser tolerante de YYYY-MM-DD ou DD/MM/YYYY -> date."""
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
        """Processa um e-mail. PDF pode conter N pedidos — cria N linhas com
        SUB_ID sequencial, mesmo MESSAGE_ID, mesmo PDF_PATH.

        Retorna:
          'PROCESSADO' -> PDF salvo + N INSERTs (um por bloco detectado)
          'DUPLICADO'  -> MESSAGE_ID já existe na tabela (anti-duplicação)
          'SEM_PDF'    -> e-mail não tem anexo PDF ou PDF ilegível
        """
        # Imports tardios
        from sankhya_integration.services.oracle_conn import (
            consultar_pedido_email_por_message_id, inserir_pedido_email_recebido,
        )

        message_id = (msg.headers.get('message-id', ('',))[0]
                      if hasattr(msg, 'headers') else None) or msg.uid
        message_id = message_id.strip() if isinstance(message_id, str) else message_id

        # Anti-duplicação: a função consulta a UNIQUE composta (MESSAGE_ID, SUB_ID)
        # e retorna qualquer registro com esse MESSAGE_ID — basta um existir
        # para considerarmos o e-mail inteiro como já processado.
        if message_id and consultar_pedido_email_por_message_id(message_id):
            self.stdout.write(f"  -> Duplicado (MESSAGE_ID={message_id}); ignorando.")
            return 'DUPLICADO'

        # Procura primeiro anexo PDF
        pdf_attachment = next(
            (a for a in msg.attachments if (a.filename or '').lower().endswith('.pdf')),
            None,
        )
        if not pdf_attachment:
            self.stdout.write(f"  [!] E-mail UID {msg.uid} sem PDF anexo; movendo para Erros.")
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

        # Extrai texto por página (necessário pra detecção de range em
        # multi-pedido + split físico do PDF via pypdf)
        try:
            paginas = self._extrair_paginas_pdf(
                str(pdf_path) if not dry_run else None,
                payload=pdf_attachment.payload,
            )
        except Exception:
            logger.exception(f"Falha ao extrair texto do PDF UID {msg.uid}")
            paginas = []

        if not paginas or not any(t.strip() for _, t in paginas):
            self.stdout.write(f"  [!] PDF UID {msg.uid} sem texto extraível; STATUS=ERRO_PDF.")
            if dry_run: return 'SEM_PDF'
            inserir_pedido_email_recebido({
                'MESSAGE_ID': message_id, 'SUB_ID': 1,
                'REMETENTE': msg.from_,
                'ASSUNTO': msg.subject,
                'RECEBIDO_EM': recebido_em,
                'PROCESSADO_EM': datetime.now(),
                'PDF_PATH': str(pdf_path),
                'PDF_TEXTO': None,
                'STATUS': 'ERRO_PDF',
            })
            return 'PROCESSADO'  # registro criado, embora com erro

        # Divide as páginas em N pedidos. Cada pedido conhece seu range
        # de páginas (start..end) — usado tanto pelo LLM (texto isolado)
        # quanto pelo split físico do PDF (arquivo isolado).
        pedidos = split_pedidos(paginas)
        if not pedidos:
            # Fallback paranoico: tudo num só pedido
            pedidos = [{
                'sub_id': 1, 'start_page': paginas[0][0],
                'end_page': paginas[-1][0],
                'text': '\n'.join(t for _, t in paginas).strip(),
            }]

        if dry_run:
            self.stdout.write(
                f"  OK: [DRY-RUN] Inseriria {len(pedidos)} pré-pedido(s) para {message_id} "
                f"(ranges: {[(p['start_page'], p['end_page']) for p in pedidos]})"
            )
            return 'PROCESSADO'

        # Split físico do PDF: cada SUB_ID ganha seu próprio arquivo cobrindo
        # apenas suas páginas. Se 1 pedido só, devolve [pdf_path] sem
        # criar arquivo extra. PDF original é preservado em disco.
        caminhos_sub = split_pdf_fisico(
            str(pdf_path), pedidos,
            pasta_destino=pasta, base_nome=nome_arquivo,
        )

        # Persiste UMA linha por pedido. Cada uma aponta pro PDF específico
        # (sub-arquivo se múltiplos pedidos) e tem o texto isolado do seu
        # range de páginas — prompt LLM menor, mais rápido e mais preciso.
        ids_criados: list[int] = []
        for pedido, caminho in zip(pedidos, caminhos_sub):
            res = inserir_pedido_email_recebido({
                'MESSAGE_ID': message_id, 'SUB_ID': pedido['sub_id'],
                'REMETENTE': msg.from_,
                'ASSUNTO': msg.subject,
                'RECEBIDO_EM': recebido_em,
                'PROCESSADO_EM': datetime.now(),
                'PDF_PATH': caminho,
                'PDF_TEXTO': pedido['text'],
                'STATUS': 'AGUARDANDO_PARSER',
            })
            if not res.get('ok'):
                err = (res.get('error') or '').lower()
                # ORA-00001 = corrida com outro worker -> tratar como duplicado
                if 'ora-00001' in err or 'unique constraint' in err:
                    if pedido['sub_id'] == 1:
                        self.stdout.write(f"  -> Race-condition: outro worker já gravou {message_id}.")
                        return 'DUPLICADO'
                    # Se duplicou no meio, ignora os demais (pacial mas não trava)
                    logger.warning(f"Duplicidade em SUB_ID={pedido['sub_id']} de {message_id}; parando split.")
                    break
                raise RuntimeError(f"Falha gravando recebido SUB_ID={pedido['sub_id']}: {res.get('error')}")
            ids_criados.append(res['id'])

        plural = 's' if len(ids_criados) > 1 else ''
        self.stdout.write(
            f"  OK: {len(ids_criados)} pré-pedido{plural} criado{plural} (IDs={ids_criados}, {message_id})."
        )
        return 'PROCESSADO'

    def _extrair_paginas_pdf(self, path: str | None, payload: bytes) -> list[tuple[int, str]]:
        """Extrai texto por página do PDF via pdfplumber. Aceita path ou bytes (dry-run).

        Retorna [(page_number, text), ...] com page_number 1-indexed.
        Páginas sem texto extraível ainda aparecem (text='') pra preservar
        a numeração — o split_pedidos() lida com isso anexando como continuação.
        """
        try:
            import pdfplumber  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Dependência 'pdfplumber' não instalada. Rode: pip install -r requirements.txt"
            )

        paginas: list[tuple[int, str]] = []
        if path:
            with pdfplumber.open(path) as pdf:
                for pagina in pdf.pages:
                    txt = pagina.extract_text() or ''
                    paginas.append((pagina.page_number, txt))
        else:
            from io import BytesIO
            with pdfplumber.open(BytesIO(payload)) as pdf:
                for pagina in pdf.pages:
                    txt = pagina.extract_text() or ''
                    paginas.append((pagina.page_number, txt))

        return paginas

    def _nome_arquivo_seguro(self, base: str) -> str:
        """Sanitiza um identificador para usar como nome de arquivo."""
        import re
        s = (base or 'sem-id').strip().strip('<>')
        s = re.sub(r'[^A-Za-z0-9._-]+', '_', s)
        return s[:120] or 'sem-id'
