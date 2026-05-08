"""
Parser LLM local (Ollama) — extrator de pedidos a partir de texto bruto de PDF.

Roda sempre LOCAL (default `http://localhost:11434`). Dados de cliente nunca saem
da máquina — atende a regra de privacidade do projeto.

Modelo padrão: `qwen2.5:14b-instruct` (definido por `OLLAMA_MODELO` no .env).
Subido de 7B para 14B em Mai/2026 — servidor de produção (Xeon E5-2680 v4 +
64GB RAM) comporta sem suor e a acurácia esperada é ~82-90% vs ~75-85% do 7B.
Para experimentar 32B sem trocar default: setar OLLAMA_MODELO=qwen2.5:32b-instruct
no .env temporariamente.

Função principal:
    extrair_pedido_de_pdf(texto_pdf, parceiros_contexto, produtos_contexto) -> dict

Retorna estrutura validada:
    {
        'ok': True/False,
        'cliente': {'nome': ..., 'codparc_sugerido': int, 'confianca': 0.0-1.0},
        'data_negociacao': 'YYYY-MM-DD' | None,
        'observacao': str | None,
        'itens': [
            {
                'descricao_pdf': str,
                'codprod_sugerido': int | None,
                'codprod_confianca': 0.0-1.0,
                'qtd': float,
                'codvol': str,
                'preco_unit': float | None,
            },
            ...
        ],
        'confianca_geral': 0.0-1.0,
        'modelo': 'qwen2.5:7b-instruct',
        'tokens_in': int,
        'tokens_out': int,
        'resposta_crua': str,  # JSON original do LLM (auditoria)
    }

Em caso de erro:
    {'ok': False, 'error': mensagem}
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts — variantes por layout
# ---------------------------------------------------------------------------
# A escolha do prompt afeta apenas a precisão da extração; o JSON de saída
# é o mesmo (cliente_nome, data_negociacao, observacao, itens[]) e o
# matching/aprendizado a jusante são layout-agnósticos. Pra adicionar um
# layout novo, só preencher PROMPTS_POR_LAYOUT abaixo.

_PROMPT_SISTEMA_CONSINCO_RELPED = """Você é um extrator preciso de dados de pedidos de venda agropecuários. Recebe o texto bruto de UM ÚNICO pedido (extraído de PDF) e devolve EXCLUSIVAMENTE um objeto JSON válido. Sem markdown, sem comentário, sem explicação.

═══════════════════════════════════════════════════════
ATENÇÃO — DOIS PONTOS QUE A IA SEMPRE ERRA SEM ESTE AVISO:
═══════════════════════════════════════════════════════

(A) FORNECEDOR ≠ CLIENTE
   - O bloco "FORNECEDOR" no início do PDF é a empresa AGROMIL/HF SEMEAR
     (somos nós que estamos vendendo). NUNCA extraia esse nome como cliente.
   - O CLIENTE está SEMPRE no bloco "DADOS PARA FATURAMENTO" (à direita
     do FORNECEDOR no cabeçalho), ou no rodapé "PALMAS, 30 de Abril de 2026
     SENDAS DISTRIBUIDORA S/A LJ347-FLV1 ... AGROMIL AGROCOMERCIAL LTDA"
     onde o NOSSO nome (AGROMIL) aparece DEPOIS, e o CLIENTE aparece ANTES.
   - Se em dúvida, copie a razão social que aparece em "R. Social" do bloco
     "DADOS PARA FATURAMENTO".

(B) LAYOUT DA TABELA DE ITENS — Consinco / RelPedSuprim
   Cabeçalho da tabela:
       Cod Forn | SeqProdutos a Receber | Emb. | Qtde | Valor Unitário | Valor Item | Valor IPI | ...
   Cada linha tem essa sequência de COLUNAS NUMÉRICAS:
       <CodForn+Descrição> | <Vol> <Vol> | Emb. (sempre 1) | Qtde | ValorUnit | ValorItem | 0,00 | 0,00 | ...
   Exemplo real:
       8117PIMENTAO VERDE KG KG 1 160,00 12,5000 2.000,00 0,00 0,00 ...
                                  ↑    ↑      ↑        ↑
                                Emb  Qtde   ValorUnit  ValorItem
   - "Emb." é o código de embalagem (geralmente o número 1) — IGNORE.
   - "Qtde" é o número que vem DEPOIS do Emb. — extraia como `qtd`.
   - "Valor Unitário" vem DEPOIS de Qtde — extraia como `preco_unit`.
   - "Valor Item" (qtd × unit) vem DEPOIS — IGNORE, não pedimos.

═══════════════════════════════════════════════════════

REGRAS DE EXTRAÇÃO:
1. EXTRAIA APENAS valores que aparecem LITERALMENTE no texto. NÃO INVENTE.
2. Se um valor não estiver claramente no texto, retorne null.
3. NÃO sugira CODPARC nem CODPROD. Outro sistema resolve.
4. Datas: YYYY-MM-DD. Use "Data da emissão".
5. Números: ponto decimal (1.234,56 BR → 1234.56 saída).
6. Itens: extraia TODOS os produtos da tabela. SEMPRE retorne `itens`, mesmo vazio.
"""

_PROMPT_USUARIO_TMPL_CONSINCO_RELPED = """Texto extraído do PDF (UM pedido):
\"\"\"
{texto_pdf}
\"\"\"

Devolva um JSON com este formato:
{{
  "cliente_nome": "<razão social do CLIENTE em 'DADOS PARA FATURAMENTO' — NÃO o fornecedor>",
  "data_negociacao": "<YYYY-MM-DD ou null>",
  "observacao": "<observação livre se houver, ou null>",
  "itens": [
    {{
      "cod_cliente": "<código numérico que vem ANTES da descrição na coluna 'Cod Forn' (ex: 8117). É o código que o CLIENTE usa pro produto. SEM letras coladas.>",
      "descricao_pdf": "<descrição literal do produto, sem código>",
      "qtd": <número da coluna QTDE — NUNCA da coluna EMB.>,
      "codvol": "<KG/UN/BD/CX/...>",
      "preco_unit": <número da coluna VALOR UNITÁRIO ou null>
    }}
  ]
}}

EXEMPLO REAL (use como referência de layout, NÃO copie valores):

  Texto de entrada (trecho):
    FORNECEDOR 4212917
    R. Social AGROMIL AGROCOMERCIAL LTDA
    DADOS PARA FATURAMENTO
    R. Social SENDAS DISTRIBUIDORA S/A LJ176  176 PALMAS TEOTONIO
    Cod Forn SeqProdutos a Receber Emb. Qtde Valor Unitário Valor Item
    8117PIMENTAO VERDE KG    KG 1 160,00 12,5000  2.000,00  0,00 ...
    1042608MILHO VERDE C/5UN BD 1  80,00  8,0000    640,00  0,00 ...
    Data da emissão 30/04/2026

  JSON correto:
  {{
    "cliente_nome": "SENDAS DISTRIBUIDORA S/A LJ176 176 PALMAS TEOTONIO",
    "data_negociacao": "2026-04-30",
    "observacao": null,
    "itens": [
      {{"cod_cliente": "8117", "descricao_pdf": "PIMENTAO VERDE", "qtd": 160.0, "codvol": "KG", "preco_unit": 12.5}},
      {{"cod_cliente": "1042608", "descricao_pdf": "MILHO VERDE C/5UN", "qtd": 80.0, "codvol": "BD", "preco_unit": 8.0}}
    ]
  }}

  ⚠ ERROS comuns que esse exemplo previne:
   - cliente_nome NÃO é "AGROMIL AGROCOMERCIAL LTDA" (fornecedor).
   - qtd NÃO é 1 (Emb.). É 160 e 80 (Qtde real).
   - preco_unit NÃO é 160 ou 80 (Qtde). É 12.5 e 8.0 (Valor Unitário).
   - cod_cliente é APENAS dígitos do "Cod Forn" (8117, 1042608) — não inclua letras.
   - Se a linha não tem código numérico antes da descrição, use null em cod_cliente.
"""


# Variant GENERICO — neutro, pra layouts ainda não plugados (PDF de outro
# fornecedor, paste de WhatsApp, etc.). Sem dicas específicas — pior precisão,
# mas funciona em qualquer formato. Operador corrige na revisão; aprendizado
# por alias acelera as próximas.
_PROMPT_SISTEMA_GENERICO = """Você é um extrator preciso de dados de pedidos de venda agropecuários. Recebe texto bruto de UM ÚNICO pedido (extraído de PDF, mensagem de WhatsApp ou paste manual) e devolve EXCLUSIVAMENTE um objeto JSON válido. Sem markdown, sem comentário, sem explicação.

REGRAS DE EXTRAÇÃO:
1. EXTRAIA APENAS valores que aparecem LITERALMENTE no texto. NÃO INVENTE.
2. Se um valor não estiver claramente no texto, retorne null.
3. NÃO sugira CODPARC nem CODPROD. Outro sistema resolve.
4. Datas: formato YYYY-MM-DD. Se o texto trouxer "30/04/2026", devolva "2026-04-30".
5. Números: ponto decimal (1.234,56 BR → 1234.56 saída).
6. Itens: extraia TODOS os produtos do pedido. SEMPRE retorne `itens`, mesmo vazio.
7. Cliente vs Fornecedor: o CLIENTE é quem está RECEBENDO o pedido (quem vai
   comprar de nós). O FORNECEDOR somos nós (AGROMIL / HF SEMEAR). Se houver
   ambos no texto, escolha o cliente. Em caso de dúvida, prefira a razão
   social associada a "Cliente", "Faturamento", "Destinatário" ou similar.
"""

_PROMPT_USUARIO_TMPL_GENERICO = """Texto do pedido:
\"\"\"
{texto_pdf}
\"\"\"

Devolva um JSON com este formato:
{{
  "cliente_nome": "<nome ou razão social do cliente, ou null>",
  "data_negociacao": "<YYYY-MM-DD ou null>",
  "observacao": "<observação livre se houver, ou null>",
  "itens": [
    {{
      "descricao_pdf": "<descrição literal do produto, sem código se possível>",
      "qtd": <número>,
      "codvol": "<KG/UN/CX/BD/etc, use 'UN' se não especificado>",
      "preco_unit": <número ou null>
    }}
  ]
}}
"""


# Mapa layout → (sistema, template_usuario). Adicionar novo layout =
# 1 entrada aqui + 1 entrada no _HEADERS_POR_LAYOUT do worker.
PROMPTS_POR_LAYOUT: dict[str, tuple[str, str]] = {
    'CONSINCO_RELPED': (_PROMPT_SISTEMA_CONSINCO_RELPED, _PROMPT_USUARIO_TMPL_CONSINCO_RELPED),
    'GENERICO':        (_PROMPT_SISTEMA_GENERICO,        _PROMPT_USUARIO_TMPL_GENERICO),
}


def _prompts_para_layout(layout: str | None) -> tuple[str, str]:
    """Retorna (sistema, template_usuario) pro layout. Default GENERICO."""
    return PROMPTS_POR_LAYOUT.get(layout or 'GENERICO', PROMPTS_POR_LAYOUT['GENERICO'])


# ---------------------------------------------------------------------------
# Configuração e cliente
# ---------------------------------------------------------------------------

def _config() -> dict:
    return {
        'host':    os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/'),
        'modelo':  os.getenv('OLLAMA_MODELO', 'qwen2.5:14b-instruct'),
        'timeout': int(os.getenv('OLLAMA_TIMEOUT_SEGUNDOS', '120')),
        'retries': int(os.getenv('OLLAMA_MAX_RETRIES', '3')),
    }


def _cliente_ollama():
    """Retorna o cliente Ollama configurado. Import tardio para não quebrar lint
    se a dep não estiver instalada localmente."""
    try:
        import ollama  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Dependência 'ollama' não instalada. Rode: pip install -r requirements.txt"
        ) from e
    cfg = _config()
    return ollama.Client(host=cfg['host'], timeout=cfg['timeout'])


# ---------------------------------------------------------------------------
# Extração e validação do JSON de resposta
# ---------------------------------------------------------------------------

def _extrair_json_da_resposta(texto: str) -> dict:
    """Tenta parsear JSON da resposta do LLM. Tolerante a markdown ou texto extra."""
    if not texto: raise ValueError("Resposta vazia do LLM.")
    # Remove fences ```json ... ``` se vierem
    texto = re.sub(r'^```(?:json)?\s*|\s*```$', '', texto.strip(), flags=re.IGNORECASE | re.MULTILINE)
    # Tenta direto
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    # Heurística: pega do primeiro { até o último }
    m = re.search(r'\{.*\}', texto, flags=re.DOTALL)
    if not m:
        raise ValueError(f"Sem JSON identificável na resposta: {texto[:200]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido na resposta do LLM: {e}")


def _normalizar_resposta(parsed: dict) -> dict:
    """Garante que campos obrigatórios existem e tipos batem. Não falha — preenche
    com valores neutros.

    O LLM agora retorna apenas dados textuais (cliente_nome, descricao_pdf).
    Os IDs (codparc, codprod) e confiança vêm do matching em Python via
    `services.matching` no worker.
    """
    out: dict = {}
    # Aceita tanto a forma nova ("cliente_nome": "...") quanto a antiga
    # ("cliente": {"nome": "..."}) — robustez contra LLM seguir ou não o template
    cliente_nome = parsed.get('cliente_nome')
    if not cliente_nome:
        cliente_obj = parsed.get('cliente') or {}
        cliente_nome = cliente_obj.get('nome') or cliente_obj.get('cliente_nome') or ''
    out['cliente_nome']    = str(cliente_nome or '')[:200]

    out['data_negociacao'] = parsed.get('data_negociacao') or None
    out['observacao']      = (parsed.get('observacao') or None)
    if out['observacao'] is not None:
        out['observacao'] = str(out['observacao'])[:2000]

    itens_raw = parsed.get('itens') or []
    itens: list[dict] = []
    for it in itens_raw if isinstance(itens_raw, list) else []:
        # cod_cliente: aceita string ou número, normaliza pra string só dígitos
        # (no Consinco vem como int "8117"). Vazio/null vira None.
        cod_raw = it.get('cod_cliente')
        cod_cliente = None
        if cod_raw not in (None, '', 0):
            cod_str = str(cod_raw).strip()
            # Filtra só dígitos pra evitar lixo do LLM ("8117KG" vira "8117")
            so_digitos = re.sub(r'[^0-9]', '', cod_str)
            cod_cliente = so_digitos[:50] if so_digitos else None
        itens.append({
            'cod_cliente':   cod_cliente,
            'descricao_pdf': str(it.get('descricao_pdf') or '')[:500],
            'qtd':           _to_float(it.get('qtd')),
            'codvol':        str(it.get('codvol') or 'KG').upper()[:10],   # default agro = KG
            'preco_unit':    _to_float(it.get('preco_unit')),
        })
    out['itens'] = itens
    return out


def _to_int(v):
    if v is None or v == '': return None
    try: return int(v)
    except (TypeError, ValueError): return None


def _to_float(v):
    if v is None or v == '': return None
    try: return float(v)
    except (TypeError, ValueError): return None


def _to_float_0_1(v):
    f = _to_float(v)
    if f is None: return 0.0
    return max(0.0, min(1.0, f))


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def extrair_pedido_de_pdf(texto_pdf: str, layout: str | None = None) -> dict:
    """Chama o LLM local e devolve o pedido extraído + telemetria.

    Retorno SEMPRE com `ok` (True/False). Em caso de falha, devolve `error`.
    Em caso de sucesso, devolve campos normalizados + `resposta_crua` para audit.

    `layout` controla qual variant do prompt usar — ver `PROMPTS_POR_LAYOUT`.
    Default é `'GENERICO'` (neutro). Para máxima precisão em PDFs Consinco/
    RelPedSuprim, passar `layout='CONSINCO_RELPED'` (avisa o LLM dos pontos
    onde sempre erra: FORNECEDOR≠CLIENTE e layout das colunas Emb/Qtde/Valor).

    O LLM extrai apenas dados textuais (cliente_nome, descricao_pdf, qtd,
    codvol, preco_unit, data_negociacao, observacao). A resolução de
    CODPARC/CODPROD acontece depois em Python via `services.matching`
    (fuzzy determinístico contra TGFPAR/TGFPRO completas), o que evita
    alucinação do LLM por contaminação de contexto.
    """
    if not texto_pdf or not texto_pdf.strip():
        return {'ok': False, 'error': 'texto_pdf vazio.'}

    cfg = _config()
    prompt_sistema, prompt_usuario_tmpl = _prompts_para_layout(layout)
    prompt_user = prompt_usuario_tmpl.format(
        texto_pdf=texto_pdf[:15000],  # trava de tamanho — PDFs muito grandes truncam
    )

    cliente = _cliente_ollama()
    ultima_excecao: Exception | None = None
    for tentativa in range(1, cfg['retries'] + 1):
        try:
            logger.info(
                f"LLM tentativa {tentativa}/{cfg['retries']} "
                f"(modelo={cfg['modelo']}, layout={layout or 'GENERICO'})"
            )
            resposta = cliente.chat(
                model=cfg['modelo'],
                messages=[
                    {'role': 'system', 'content': prompt_sistema},
                    {'role': 'user', 'content': prompt_user},
                ],
                format='json',  # pede JSON estruturado ao Ollama
                options={'temperature': 0.1},  # baixa criatividade — extração determinística
            )
            return _processar_resposta_ollama(resposta, cfg)
        except Exception as exc:
            logger.exception(f"LLM falhou na tentativa {tentativa}")
            ultima_excecao = exc
            continue

    return {'ok': False, 'error': f'Todas as tentativas falharam: {ultima_excecao}'}


def _processar_resposta_ollama(resposta: Any, cfg: dict) -> dict:
    """Converte o objeto retornado pelo cliente Ollama no nosso formato."""
    # Cliente Python do Ollama retorna objeto com `.message.content` (Pydantic)
    # ou dict com `message.content`. Tratamos os dois.
    conteudo = None
    tokens_in = tokens_out = 0
    try:
        if hasattr(resposta, 'message'):
            msg = resposta.message
            conteudo = getattr(msg, 'content', None)
        elif isinstance(resposta, dict):
            conteudo = (resposta.get('message') or {}).get('content')
        if hasattr(resposta, 'prompt_eval_count'):
            tokens_in = int(getattr(resposta, 'prompt_eval_count', 0) or 0)
            tokens_out = int(getattr(resposta, 'eval_count', 0) or 0)
        elif isinstance(resposta, dict):
            tokens_in = int(resposta.get('prompt_eval_count') or 0)
            tokens_out = int(resposta.get('eval_count') or 0)
    except Exception:
        logger.exception("Erro lendo metadados da resposta Ollama")

    if not conteudo:
        return {'ok': False, 'error': 'Resposta do Ollama sem conteúdo.'}

    try:
        parsed = _extrair_json_da_resposta(conteudo)
    except Exception as exc:
        return {
            'ok': False,
            'error': str(exc),
            'resposta_crua': conteudo[:5000],
        }

    norm = _normalizar_resposta(parsed)
    norm.update({
        'ok':            True,
        'modelo':        cfg['modelo'],
        'tokens_in':     tokens_in,
        'tokens_out':    tokens_out,
        'resposta_crua': conteudo,
    })
    return norm
