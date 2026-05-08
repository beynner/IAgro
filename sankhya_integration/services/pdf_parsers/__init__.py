"""
Parsers Python plugáveis (regex + pdfplumber) pra layouts conhecidos de PDF.

ETAPA 0 DO WORKER — antes de chamar o LLM (~3 min em CPU), tenta extrair
diretamente via parser específico do layout. Se conseguir extrair E validar
(soma de itens não-vazia, qtd numérica, etc.), worker usa o resultado direto.
Caso contrário, fallback transparente pro LLM (fluxo atual preservado).

Ganho esperado em layouts conhecidos: ~3600× (50ms vs 3min) sem perda de
acurácia, já que o layout é fixo e previsível.

Como adicionar layout novo:
    1. Implementar parser em <nome>.py com a assinatura
       `parser_<nome>(pdf_path, texto, recebido_id) -> dict | None`
       devolvendo o mesmo shape de `llm_local.extrair_pedido_de_pdf()`
       (com `ok=True`) em caso de sucesso, ou None se extração falhar/validar.
    2. Registrar em `PARSERS_POR_LAYOUT` abaixo.
    3. Garantir que `_HEADERS_POR_LAYOUT` em `colher_pedidos_email.py`
       reconhece o layout (regex de detecção).
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from . import consinco

logger = logging.getLogger(__name__)


# Layout -> função parser. Layouts ausentes daqui caem direto no LLM
# (transparente; sem perda funcional).
PARSERS_POR_LAYOUT: dict[str, Callable[..., Optional[dict]]] = {
    'CONSINCO_RELPED': consinco.parser_consinco,
}


def tentar_parseamento(layout: str | None, *, pdf_path: str | None,
                       texto: str, recebido_id: int) -> dict | None:
    """Tenta extrair via parser Python específico do layout.

    Devolve dict no mesmo formato de `llm_local.extrair_pedido_de_pdf()` em
    caso de sucesso, ou None se:
      - layout não tem parser registrado;
      - parser foi chamado mas devolveu None (extração falhou ou não validou);
      - parser levantou exceção (loga e suprime — worker faz fallback LLM).

    `pdf_path` pode ser None (paste manual / ORIGEM='TEXTO_LIVRE'). Parsers
    que dependem do PDF físico devolvem None nesse caso e caem no LLM.
    """
    if not layout:
        return None
    parser = PARSERS_POR_LAYOUT.get(layout)
    if not parser:
        return None

    try:
        resultado = parser(pdf_path=pdf_path, texto=texto, recebido_id=recebido_id)
    except Exception:
        logger.exception(
            f"Parser Python {layout} levantou exceção para "
            f"recebido_id={recebido_id}; caindo em fallback LLM."
        )
        return None

    if resultado is None:
        return None

    # Validação leve do shape — parser deve devolver `ok=True` e `itens` lista.
    # Inválido = trata como falha silenciosa e cai em LLM.
    if not isinstance(resultado, dict) or not resultado.get('ok'):
        logger.info(
            f"Parser Python {layout} devolveu resultado inválido para "
            f"recebido_id={recebido_id}; caindo em fallback LLM."
        )
        return None

    return resultado
