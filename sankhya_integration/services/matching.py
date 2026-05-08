"""
sankhya_integration/services/matching.py

Fuzzy matching determinístico de strings extraídas pelo LLM contra a base do
Sankhya. Usado pelo worker `colher_pedidos_email` — o LLM **não vê** lista de
parceiros/produtos no prompt (evita alucinação por contaminação do contexto);
o LLM só extrai texto literal do PDF, e este módulo casa em Python.

Princípio
---------
- LLM extrai `cliente.nome` (string livre do texto) → matching.casar_codparc
- LLM extrai `descricao_pdf` por item → matching.casar_codprod
- Score baixo (< threshold) retorna (None, score, "") — operador escolhe na tela

Estratégia
---------
- Carrega TGFPAR e TGFPRO inteiras na memória do worker (10-50k strings
  típicas, ~1-5 MB) — fit confortável.
- Normaliza ambos os lados: strip de acentos, lowercase, remoção de sufixos
  societários (LTDA, S/A, ME, EIRELI...), remoção de sufixos de embalagem
  (KG, UN, BD, CX...) — porque o operador/PDF nem sempre os reproduz.
- Casa via rapidfuzz.process.extractOne (token_set_ratio).
- Retorna (codparc/codprod, score 0-100, nome_canonico).

Thresholds (calibrar com base nos primeiros e-mails reais)
----------------------------------------------------------
- THRESHOLD_PARCEIRO = 80
- THRESHOLD_PRODUTO  = 75

Cache
-----
- Cache é por processo do worker (módulo-singleton via _cache).
- Cada `python manage.py colher_pedidos_email` recarrega do banco.
- Worker roda a cada 30 min — frescor adequado.
"""
from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


THRESHOLD_PARCEIRO = 70   # token_sort_ratio com curto/longo
THRESHOLD_PRODUTO  = 75   # WRatio é mais permissivo, threshold mais alto compensa


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------

# Sufixos societários comuns no Brasil — removidos pra casamento mais robusto
_SUFIXOS_PARCEIRO = re.compile(
    r'\b(LTDA|S\.?A\.?|ME|EIRELI|EPP|MEI|SIA|CIA|S/A|S/C|FILIAL|MATRIZ)\.?\b',
    re.IGNORECASE,
)

# Sufixos de embalagem em descrições de produto
_SUFIXOS_PRODUTO = re.compile(
    r'\b(KG|G|MG|TON|UN|CX|BD|FD|PCT|BAL|LT|ML|L|DZ|PC|SC|PT|GR)\b',
    re.IGNORECASE,
)

# Tokens repetidos como "C/5UN", "5UN", "5KG", "100G"
_TOKENS_QUANTIDADE = re.compile(
    r'\b\d+\s*(?:KG|G|MG|UN|BD|FD|PCT|LT|ML|L|DZ|PC|UND|C/\d+UN)?\b',
    re.IGNORECASE,
)


def _strip_acentos(s: str) -> str:
    """Remove acentos preservando o restante."""
    if not s:
        return ''
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _normalizar_parceiro(s: str) -> str:
    """Normaliza nome de parceiro para fuzzy matching.

    Tokens duplicados são removidos preservando ordem da primeira ocorrência —
    útil porque a concatenação NOMEPARC+RAZAOSOCIAL frequentemente repete
    palavras (ex: 'SENDAS DISTRIBUIDORA SENDAS DISTRIBUIDORA S/A').

    Exemplos:
      'Sendas Distribuidora S/A LJ347'           -> 'sendas distribuidora lj347'
      'AGROMIL AGROCOMERCIAL LTDA'               -> 'agromil agrocomercial'
      'Açaí Distribuidora & Cia.'                -> 'acai distribuidora'
      'ASSAI ARAGUAINA SENDAS DISTRIBUIDORA S/A' -> 'assai araguaina sendas distribuidora'
    """
    if not s:
        return ''
    s = _strip_acentos(s)
    s = s.lower()
    s = _SUFIXOS_PARCEIRO.sub(' ', s)
    s = re.sub(r'[^\w\s]', ' ', s)  # remove pontuação
    s = re.sub(r'\s+', ' ', s).strip()
    # Dedupe tokens preservando ordem
    visto = set()
    tokens = []
    for tok in s.split():
        if tok not in visto:
            visto.add(tok)
            tokens.append(tok)
    return ' '.join(tokens)


def _normalizar_produto(s: str) -> str:
    """Normaliza descrição de produto para fuzzy matching.

    Exemplos:
      'TOMATE ITALIANO KG'      -> 'tomate italiano'
      '1042608MILHO VERDE C/5UN BD' -> 'milho verde'
      'Pepino Comum 5kg'        -> 'pepino comum'
    """
    if not s:
        return ''
    s = _strip_acentos(s)
    s = s.lower()
    # Remove código de produto preso ao início (ex: '1042608MILHO VERDE')
    s = re.sub(r'^\d+', '', s)
    s = _TOKENS_QUANTIDADE.sub(' ', s)
    s = _SUFIXOS_PRODUTO.sub(' ', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ---------------------------------------------------------------------------
# Cache de parceiros e produtos (carregado uma vez por execução do worker)
# ---------------------------------------------------------------------------

# _cache é populado pela primeira chamada de carregar_*; subsequente reusa.
# Dict: {'parceiros': [...], 'produtos': [...]}
_cache: dict[str, list[dict]] = {}


def carregar_parceiros(forcar_recarga: bool = False) -> list[dict]:
    """Carrega lista completa de TGFPAR para matching.

    Retorna lista de dicts:
        [{'codparc': int, 'nome': str, 'nome_norm': str, 'cgc': str}, ...]
    """
    if not forcar_recarga and 'parceiros' in _cache:
        return _cache['parceiros']

    from sankhya_integration.services.oracle_conn import obter_conexao_oracle
    parceiros: list[dict] = []
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            # Filtra ATIVO se a coluna existir; senão, traz todos
            try:
                cur.execute(
                    "SELECT CODPARC, NOMEPARC, RAZAOSOCIAL, CGC_CPF "
                    "  FROM TGFPAR "
                    " WHERE NVL(ATIVO, 'S') = 'S'"
                )
            except Exception:
                # ATIVO pode não existir em algumas instalações
                cur.execute(
                    "SELECT CODPARC, NOMEPARC, RAZAOSOCIAL, CGC_CPF "
                    "  FROM TGFPAR"
                )
            for r in cur.fetchall():
                cod, nome, razao, cgc = r[0], (r[1] or ''), (r[2] or ''), (r[3] or '')
                # Mantém duas versões normalizadas:
                #   nome_curto = só NOMEPARC (nome fantasia, mais discriminativo
                #                quando a query é curta tipo "ASSAI ARAGUAINA")
                #   nome_longo = NOMEPARC + RAZAOSOCIAL (cobre quando a query é
                #                o cabeçalho completo do PDF, "SENDAS DISTRIBUIDORA
                #                S/A LJ347 347 ARAGUAINA" — razão social ajuda
                #                desambiguação)
                # Matching tenta ambos e retorna o maior score.
                parceiros.append({
                    'codparc': int(cod),
                    'nome': nome,
                    'razao': razao,
                    'cgc': cgc,
                    'nome_curto': _normalizar_parceiro(nome),
                    'nome_longo': _normalizar_parceiro(f"{nome} {razao}".strip()),
                })
    except Exception:
        logger.exception("Falha carregando TGFPAR para matching")
        parceiros = []

    _cache['parceiros'] = parceiros
    logger.info("matching: %d parceiros carregados em cache", len(parceiros))
    return parceiros


def carregar_produtos(forcar_recarga: bool = False) -> list[dict]:
    """Carrega lista completa de TGFPRO para matching.

    Retorna lista de dicts:
        [{'codprod': int, 'descr': str, 'descr_norm': str, 'codvol': str}, ...]
    """
    if not forcar_recarga and 'produtos' in _cache:
        return _cache['produtos']

    from sankhya_integration.services.oracle_conn import obter_conexao_oracle
    produtos: list[dict] = []
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT CODPROD, DESCRPROD, CODVOL "
                    "  FROM TGFPRO "
                    " WHERE NVL(ATIVO, 'S') = 'S'"
                )
            except Exception:
                cur.execute(
                    "SELECT CODPROD, DESCRPROD, CODVOL "
                    "  FROM TGFPRO"
                )
            for r in cur.fetchall():
                cod, descr, codvol = r[0], (r[1] or ''), (r[2] or '')
                produtos.append({
                    'codprod': int(cod),
                    'descr': descr,
                    'codvol': codvol,
                    'descr_norm': _normalizar_produto(descr),
                })
    except Exception:
        logger.exception("Falha carregando TGFPRO para matching")
        produtos = []

    _cache['produtos'] = produtos
    logger.info("matching: %d produtos carregados em cache", len(produtos))
    return produtos


def limpar_cache() -> None:
    """Força recarga em chamadas seguintes. Útil para testes."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Funções de casamento
# ---------------------------------------------------------------------------

def casar_codparc(nome_extraido: str,
                   parceiros: list[dict] | None = None,
                   threshold: float = THRESHOLD_PARCEIRO) -> tuple[int | None, float, str]:
    """Casa nome de cliente extraído pelo LLM contra TGFPAR.

    Estratégia em 2 etapas:
      1. Consulta AD_PARCEIRO_ALIAS — se houver alias salvo (operador confirmou
         essa associação anteriormente), retorna direto com score 100.
      2. Cai no fuzzy matching contra TGFPAR (token_sort_ratio + curto/longo).

    Retorna (codparc, score, nome_canonico) ou (None, score_melhor_candidato, '')
    se o melhor candidato fuzzy ficar abaixo do threshold.
    """
    if not nome_extraido:
        return None, 0.0, ''

    nome_norm = _normalizar_parceiro(nome_extraido)
    if not nome_norm:
        return None, 0.0, ''

    # Etapa 1: alias aprendido — match exato em string normalizada
    try:
        from sankhya_integration.services.oracle_conn import buscar_alias_parceiro
        codparc_alias = buscar_alias_parceiro(nome_norm)
        if codparc_alias:
            # Procura o nome canônico no cache de parceiros
            parceiros_cache = parceiros if parceiros is not None else carregar_parceiros()
            for p in parceiros_cache:
                if p['codparc'] == codparc_alias:
                    return codparc_alias, 100.0, p['nome'] or p['razao'] or ''
            return codparc_alias, 100.0, ''  # parceiro existe mas não no cache
    except Exception:
        logger.exception("Falha consultando alias parceiro — caindo no fuzzy")

    parceiros = parceiros if parceiros is not None else carregar_parceiros()
    if not parceiros:
        return None, 0.0, ''

    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        logger.error("rapidfuzz não está instalado — matching desativado")
        return None, 0.0, ''

    # Listas paralelas: process.extractOne retorna o índice na lista que
    # passamos, então alinhamos com `parceiros` por posição.
    candidatos_curto = [p['nome_curto'] for p in parceiros]
    candidatos_longo = [p['nome_longo'] for p in parceiros]

    melhor_curto = process.extractOne(nome_norm, candidatos_curto, scorer=fuzz.token_sort_ratio)
    melhor_longo = process.extractOne(nome_norm, candidatos_longo, scorer=fuzz.token_sort_ratio)

    # Cada melhor_* é (string_match, score, idx_na_lista) ou None
    score_curto = melhor_curto[1] if melhor_curto else 0.0
    score_longo = melhor_longo[1] if melhor_longo else 0.0

    if score_curto >= score_longo:
        score = score_curto
        idx = melhor_curto[2] if melhor_curto else -1
    else:
        score = score_longo
        idx = melhor_longo[2] if melhor_longo else -1

    if idx < 0:
        return None, 0.0, ''

    p = parceiros[idx]
    if score >= threshold:
        return p['codparc'], float(score), p['nome'] or p['razao'] or ''
    return None, float(score), ''


def casar_codprod(descricao_extraida: str,
                   produtos: list[dict] | None = None,
                   threshold: float = THRESHOLD_PRODUTO,
                   codparc: int | None = None,
                   cod_cliente: str | None = None) -> tuple[int | None, float, str]:
    """Casa descrição de produto extraída pelo LLM contra TGFPRO.

    Estratégia em 3 etapas (do mais forte ao mais fraco):
      0. Consulta AD_CLIENTE_PRODUTO_COD por (CODPARC, COD_CLIENTE).
         Match exato → retorna com score 100. Aplicável só em pedidos com
         "Cod Forn" (Consinco/RelPedSuprim).
      1. Consulta AD_PRODUTO_ALIAS — primeiro alias específico do CODPARC,
         depois alias global. Match exato em descricao_normalizada → score 100.
      2. Fuzzy matching (WRatio) contra TGFPRO completo.

    `codparc` opcional permite alias scope-specific: cliente A pode chamar
    "PIMENTAO VERDE" o EXTRA, cliente B o MEDIO — alias por cliente desambigua.
    `cod_cliente` opcional ativa Etapa 0: vinculação histórica por código numérico
    do cliente (mais confiável que descrição).

    Retorna (codprod, score, descr_canonica) ou (None, score, '') se o melhor
    candidato fuzzy ficar abaixo do threshold.
    """
    if not descricao_extraida and not cod_cliente:
        return None, 0.0, ''

    # Etapa 0: vinculação aprendida por (CODPARC, COD_CLIENTE) — mais confiável
    # porque é match de string exata em código numérico, sem fuzziness textual.
    if codparc and cod_cliente:
        try:
            from sankhya_integration.services.oracle_conn import buscar_cod_cliente_codprod
            codprod_cli = buscar_cod_cliente_codprod(int(codparc), str(cod_cliente))
            if codprod_cli:
                produtos_cache = produtos if produtos is not None else carregar_produtos()
                for p in produtos_cache:
                    if p['codprod'] == codprod_cli:
                        return codprod_cli, 100.0, p['descr']
                return codprod_cli, 100.0, ''
        except Exception:
            logger.exception("Falha consultando cod_cliente — caindo no alias/fuzzy")

    descr_norm = _normalizar_produto(descricao_extraida)
    if not descr_norm:
        return None, 0.0, ''

    # Etapa 1: alias aprendido (específico do cliente, depois global)
    try:
        from sankhya_integration.services.oracle_conn import buscar_alias_produto
        codprod_alias = buscar_alias_produto(descr_norm, codparc=codparc)
        if codprod_alias:
            produtos_cache = produtos if produtos is not None else carregar_produtos()
            for p in produtos_cache:
                if p['codprod'] == codprod_alias:
                    return codprod_alias, 100.0, p['descr']
            return codprod_alias, 100.0, ''
    except Exception:
        logger.exception("Falha consultando alias produto — caindo no fuzzy")

    produtos = produtos if produtos is not None else carregar_produtos()
    if not produtos:
        return None, 0.0, ''

    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        logger.error("rapidfuzz não está instalado — matching desativado")
        return None, 0.0, ''

    candidatos = [p['descr_norm'] for p in produtos]
    # WRatio para produtos (combina ratio + token_set + partial_ratio): testes
    # mostraram acerto melhor que token_sort_ratio em produtos curtos (PIMENTAO
    # VERDE, INHAME, REPOLHO VERDE) onde token_sort confundia palavras parecidas.
    melhor = process.extractOne(descr_norm, candidatos, scorer=fuzz.WRatio)
    if not melhor:
        return None, 0.0, ''
    _, score, idx = melhor
    p = produtos[idx]

    if score >= threshold:
        return p['codprod'], float(score), p['descr']
    return None, float(score), ''


# ---------------------------------------------------------------------------
# Aprendizado: gravar alias após confirmação humana
# ---------------------------------------------------------------------------

def aprender_alias_produto(descricao_pdf: str, codprod: int,
                            codparc: int | None = None,
                            confirmado_por: int | None = None) -> dict:
    """Wrapper que normaliza a descrição BRUTA e grava em AD_PRODUTO_ALIAS.

    Use após o operador confirmar um pré-pedido (clique 'Confirmar e criar pedido').
    Próximas chamadas de casar_codprod com a mesma descrição vão retornar este
    CODPROD direto.

    Tolerante a falhas: erros são logados mas não propagados — alias é melhoria
    de UX, não regra de negócio crítica.
    """
    try:
        descr_norm = _normalizar_produto(descricao_pdf)
        if not descr_norm or not codprod:
            return {'ok': False, 'error': 'descricao ou codprod inválido'}
        from sankhya_integration.services.oracle_conn import gravar_alias_produto
        return gravar_alias_produto(
            descricao_normalizada=descr_norm,
            codprod=int(codprod),
            codparc=int(codparc) if codparc else None,
            confirmado_por=int(confirmado_por) if confirmado_por else None,
        )
    except Exception as exc:
        logger.exception("Erro em aprender_alias_produto")
        return {'ok': False, 'error': str(exc)}


def aprender_alias_parceiro(nome_extraido: str, codparc: int,
                              confirmado_por: int | None = None) -> dict:
    """Wrapper que normaliza o nome BRUTO e grava em AD_PARCEIRO_ALIAS."""
    try:
        nome_norm = _normalizar_parceiro(nome_extraido)
        if not nome_norm or not codparc:
            return {'ok': False, 'error': 'nome ou codparc inválido'}
        from sankhya_integration.services.oracle_conn import gravar_alias_parceiro
        return gravar_alias_parceiro(
            nome_normalizado=nome_norm,
            codparc=int(codparc),
            confirmado_por=int(confirmado_por) if confirmado_por else None,
        )
    except Exception as exc:
        logger.exception("Erro em aprender_alias_parceiro")
        return {'ok': False, 'error': str(exc)}


def aprender_cod_cliente(codparc: int, cod_cliente: str, codprod: int,
                          confirmado_por: int | None = None) -> dict:
    """Wrapper: grava vinculação (CODPARC, COD_CLIENTE) -> CODPROD após
    confirmação humana. Próximas chamadas de casar_codprod com mesmo (codparc,
    cod_cliente) retornam direto.

    Tolerante: se a tabela AD_CLIENTE_PRODUTO_COD não existe (migration
    pendente), retorna {'ok': False} silencioso — operação de confirmar pedido
    NÃO é desfeita por causa disso.
    """
    try:
        if not codparc or not cod_cliente or not codprod:
            return {'ok': False, 'error': 'parâmetros incompletos'}
        from sankhya_integration.services.oracle_conn import gravar_cod_cliente_codprod
        return gravar_cod_cliente_codprod(
            codparc=int(codparc),
            cod_cliente=str(cod_cliente).strip(),
            codprod=int(codprod),
            confirmado_por=int(confirmado_por) if confirmado_por else None,
        )
    except Exception as exc:
        logger.exception("Erro em aprender_cod_cliente")
        return {'ok': False, 'error': str(exc)}
