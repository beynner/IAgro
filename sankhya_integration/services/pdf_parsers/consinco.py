"""
Parser Python pra PDFs Consinco / RelPedSuprim (Assaí, SENDAS, etc.).

ETAPA 0 do worker: extrai cliente_nome, data_negociacao e itens diretamente
via regex sobre o texto já extraído pelo pdfplumber, sem chamar LLM.

Performance esperada: ~50ms vs ~3min do LLM (~3600× speedup).

ESTRATÉGIA:
  - Cliente: bloco "DADOS PARA FATURAMENTO" -> primeiro "R. Social <NOME>"
  - Data: "Data da emissão DD/MM/YYYY"
  - Itens: linha com âncora "<VOL> <VOL> <EMB=1> <QTDE> <VLR_UNIT> <VLR_ITEM>"
    onde o prefixo (cod_cliente colado com descrição) vira `cod_cliente +
    descricao_pdf` separados por regex.

VALIDAÇÕES (qualquer falha -> None -> fallback LLM):
  1. Cliente identificado
  2. >=1 item válido (qtd > 0, preco_unit numérico)
  3. `Total de itens: N` declarado == len(itens) extraídos (se houver)
  4. |Σ(valor_item) - total_geral_pdf| <= R$ 0,02 (se houver)

Conservador por design: prefere LLM lento mas correto a regex rápida e errada.

A UI (Fase C) lê `totais_pdf` de `resposta_crua` pra mostrar conferência
visual no rodapé do pedido.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

# Cliente — depois de "DADOS PARA FATURAMENTO", primeiro "R. Social <NOME>"
# até quebra de linha. Limite de 200 chars pra evitar capturar bloco inteiro
# se o terminador falhar.
_RE_CLIENTE = re.compile(
    r'DADOS\s+PARA\s+FATURAMENTO'
    r'.{0,500}?'
    r'R\.\s*Social\s+([^\n]{3,200})',
    re.IGNORECASE | re.DOTALL,
)

# Data: "Data da emissão DD/MM/YYYY" (variantes: "Data Emissão", com/sem "da")
_RE_DATA = re.compile(
    r'Data\s+(?:da\s+)?Emiss[aã]o\s+(\d{2})/(\d{2})/(\d{4})',
    re.IGNORECASE,
)

# Início do bloco de itens — header "Cod Forn ... Valor Item"
_RE_BLOCO_INI = re.compile(
    r'Cod\s*Forn[\s\S]{0,200}?Valor\s*Item[^\n]*\n',
    re.IGNORECASE,
)
# Fim do bloco — "Total geral" / "Total de itens" / "Data da emissão"
_RE_BLOCO_FIM = re.compile(
    r'(?:Total\s+(?:geral|do\s+pedido)|Total\s+de\s+itens?|Data\s+(?:da\s+)?Emiss[aã]o)',
    re.IGNORECASE,
)

# Linha de item — âncora: VOL repetido + EMB(=1) + 3 colunas numéricas BR
# Padrão: "...<prefix> KG KG 1 160,00 12,5000 2.000,00 0,00 ..."
# Tolerâncias:
#   - prefix lazy (.+?)
#   - VOL pode ter 1-4 letras maiúsculas (KG, UN, BD, CX, FD, PCT, etc)
#   - EMB pode ter 1+ dígitos (geralmente 1)
#   - QTDE/VLR_UNIT/VLR_ITEM em formato BR (1.234,56 ou 12,50)
#   - Pode ter colunas numéricas extras depois (IPI, ICMS, etc)
_RE_ITEM = re.compile(
    r'^\s*'
    r'(?P<prefix>\S.+?)'
    r'\s+(?P<vol>[A-Z]{1,4})\s+(?P=vol)'   # VOL repetido (âncora)
    r'\s+(?P<emb>\d+)'                      # EMB
    r'\s+(?P<qtde>[\d.]*\d,\d+)'            # QTDE BR (com vírgula obrigatória)
    r'\s+(?P<vlr_unit>[\d.]*\d,\d+)'        # VLR UNIT
    r'\s+(?P<vlr_item>[\d.]*\d,\d+)'        # VLR ITEM
    r'(?:\s+[\d.]*\d,\d+)*'                 # outras colunas (IPI, ICMS, etc)
    r'\s*$',
    re.MULTILINE,
)

# Cod cliente — dígitos colados no início do prefix ("8117PIMENTAO" -> 8117)
_RE_COD_CLIENTE = re.compile(r'^\s*(\d{3,8})\s*([^\d].*)$')

# Totais declarados pra validação cruzada
_RE_TOTAL_GERAL = re.compile(
    r'Total\s+(?:geral|do\s+pedido)\s*[:\s]+'
    r'(?:R\$\s*)?'
    r'([\d.]*\d,\d{2})',
    re.IGNORECASE,
)
_RE_TOTAL_ITENS = re.compile(
    r'Total\s+de\s+itens?\s*[:\s]+(\d+)',
    re.IGNORECASE,
)

# Tolerância de soma — arredondamento na 4ª casa de preço unit pode causar
# diferença de centavos em pedidos grandes. R$ 0,10 é folga conservadora.
_TOLERANCIA_SOMA = 0.10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extrair_totais_pdf(texto: str | None) -> dict:
    """Extrai totais declarados no PDF (`total_geral`, `total_itens`).

    Não falha — devolve dict (possivelmente vazio) com as chaves que
    conseguir bater. Usa as mesmas regex do parser regex, mas isolado
    pra reuso em LLM-parsed records também: a UI de conferência cruzada
    funciona em qualquer registro cujo PDF tenha esses campos no texto,
    independente de quem parseou os itens (LLM ou regex).
    """
    out: dict = {}
    if not texto:
        return out
    m_ti = _RE_TOTAL_ITENS.search(texto)
    if m_ti:
        try:
            out['total_itens'] = int(m_ti.group(1))
        except (ValueError, TypeError):
            pass
    m_tg = _RE_TOTAL_GERAL.search(texto)
    if m_tg:
        v = _br_to_float(m_tg.group(1))
        if v is not None:
            out['total_geral'] = v
    return out


def _br_to_float(s: str | None) -> Optional[float]:
    """Converte número BR ('1.234,56' / '12,50') -> 1234.56 / 12.5. None se inválido."""
    if not s:
        return None
    try:
        return float(str(s).strip().replace('.', '').replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def _normalizar_cliente(s: str) -> str:
    """Strip + colapsa espaços + remove sufixos comuns no fim ('CNPJ', 'IE', etc)."""
    s = re.sub(r'\s+', ' ', (s or '').strip())
    # Corta no primeiro CNPJ/IE/CGC se ficou colado por extração
    s = re.split(r'\b(?:CNPJ|CGC|IE|I\.?E\.?)\b', s, maxsplit=1)[0]
    return s.strip().rstrip(',;:.-')[:200]


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def parser_consinco(*, pdf_path: str | None, texto: str,
                    recebido_id: int) -> Optional[dict]:
    """Tenta extrair pedido Consinco/RelPedSuprim via regex.

    Args:
        pdf_path: Caminho do PDF (não usado nesta versão — parsing puro de texto).
        texto: PDF_TEXTO da AD_PEDIDO_EMAIL_RECEBIDO.
        recebido_id: ID do registro (logging).

    Returns:
        dict no shape de `llm_local.extrair_pedido_de_pdf()` em sucesso,
        ou None se extração/validação falhar (worker faz fallback LLM).

    Nota sobre `pdf_path`: faz parte do contrato compartilhado dos parsers
    (ver __init__.py). Hoje a extração é só de texto (já extraído pelo worker
    via pdfplumber). Em v2, se a regex de texto falhar, abrir o PDF físico
    e tentar `pdfplumber.extract_tables()` como segunda tentativa antes do
    LLM. Por ora, o caminho aparece no log de sucesso pra debug.
    """
    if not texto or not texto.strip():
        logger.debug(f"parser_consinco #{recebido_id}: texto vazio -> None")
        return None

    # 1. Cliente
    m_cli = _RE_CLIENTE.search(texto)
    if not m_cli:
        logger.info(f"parser_consinco #{recebido_id}: bloco DADOS PARA FATURAMENTO nao encontrado -> LLM")
        return None
    cliente_nome = _normalizar_cliente(m_cli.group(1))
    if len(cliente_nome) < 3:
        logger.info(f"parser_consinco #{recebido_id}: cliente extraido vazio -> LLM")
        return None

    # 2. Data
    data_negociacao: Optional[str] = None
    m_dt = _RE_DATA.search(texto)
    if m_dt:
        d, mes, y = m_dt.groups()
        data_negociacao = f"{y}-{mes}-{d}"

    # 3. Bloco de itens (entre header "Cod Forn..." e "Total..." ou "Data...")
    m_ini = _RE_BLOCO_INI.search(texto)
    if not m_ini:
        logger.info(f"parser_consinco #{recebido_id}: cabecalho 'Cod Forn' nao encontrado -> LLM")
        return None
    bloco = texto[m_ini.end():]
    m_fim = _RE_BLOCO_FIM.search(bloco)
    if m_fim:
        bloco = bloco[:m_fim.start()]

    # 4. Itens — itera matches da regex de linha
    itens: list[dict] = []
    soma_calculada = 0.0
    for m in _RE_ITEM.finditer(bloco):
        prefix = m.group('prefix').strip()
        vol = m.group('vol').strip()
        qtde = _br_to_float(m.group('qtde'))
        vlr_unit = _br_to_float(m.group('vlr_unit'))
        vlr_item = _br_to_float(m.group('vlr_item'))

        if qtde is None or qtde <= 0 or vlr_unit is None:
            continue  # falsa positiva ou linha não-item

        # Separa cod_cliente dos dígitos iniciais (se houver)
        m_cc = _RE_COD_CLIENTE.match(prefix)
        if m_cc:
            cod_cliente = m_cc.group(1)
            descricao = m_cc.group(2).strip()
        else:
            cod_cliente = None
            descricao = prefix

        # Remove eventual prefixo de "Sequência" (alguns layouts trazem '1' colado)
        descricao = re.sub(r'^\s*\d+\s+', '', descricao).strip()
        if not descricao:
            continue

        itens.append({
            'cod_cliente':   cod_cliente,
            'descricao_pdf': descricao[:500],
            'qtd':           qtde,
            'codvol':        vol.upper()[:10],
            'preco_unit':    vlr_unit,
        })
        if vlr_item is not None:
            soma_calculada += vlr_item
        else:
            soma_calculada += qtde * vlr_unit

    if not itens:
        logger.info(f"parser_consinco #{recebido_id}: nenhum item extraido -> LLM")
        return None

    # 5. Validação cruzada — totais declarados vs extraídos
    total_itens_pdf = None
    m_ti = _RE_TOTAL_ITENS.search(texto)
    if m_ti:
        try:
            total_itens_pdf = int(m_ti.group(1))
        except (ValueError, TypeError):
            total_itens_pdf = None

    total_geral_pdf = None
    m_tg = _RE_TOTAL_GERAL.search(texto)
    if m_tg:
        total_geral_pdf = _br_to_float(m_tg.group(1))

    if total_itens_pdf is not None and total_itens_pdf != len(itens):
        logger.info(
            f"parser_consinco #{recebido_id}: divergencia itens "
            f"PDF={total_itens_pdf} vs extraidos={len(itens)} -> LLM"
        )
        return None

    if total_geral_pdf is not None:
        diff = abs(soma_calculada - total_geral_pdf)
        if diff > _TOLERANCIA_SOMA:
            logger.info(
                f"parser_consinco #{recebido_id}: divergencia soma "
                f"PDF={total_geral_pdf:.2f} vs calculado={soma_calculada:.2f} "
                f"(diff={diff:.2f} > {_TOLERANCIA_SOMA:.2f}) -> LLM"
            )
            return None

    # 6. Monta payload no shape do LLM (compatível com Restaurar tudo / item)
    payload = {
        'cliente_nome':     cliente_nome,
        'data_negociacao':  data_negociacao,
        'observacao':       None,
        'itens':            itens,
        # Metadados de telemetria/conferência (UI Fase C lê daqui)
        'totais_pdf': {
            'total_geral':   total_geral_pdf,
            'total_itens':   total_itens_pdf,
            'soma_calc':     round(soma_calculada, 2),
        },
        '_origem': 'regex_consinco_v1',
    }

    logger.info(
        f"parser_consinco #{recebido_id}: OK cliente={cliente_nome[:40]!r} "
        f"itens={len(itens)} total={soma_calculada:.2f} pdf={pdf_path or '-'} (sem LLM)"
    )

    return {
        'ok':               True,
        'cliente_nome':     cliente_nome,
        'data_negociacao':  data_negociacao,
        'observacao':       None,
        'itens':            itens,
        'modelo':           'regex_consinco_v1',
        'tokens_in':        0,
        'tokens_out':       0,
        'resposta_crua':    json.dumps(payload, ensure_ascii=False),
    }
