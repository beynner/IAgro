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
# Prompts
# ---------------------------------------------------------------------------

PROMPT_SISTEMA = """Você é um extrator de dados de pedidos de venda no agronegócio. Recebe o texto bruto de um PDF de pedido e devolve EXCLUSIVAMENTE um objeto JSON válido (nada antes, nada depois — sem markdown, sem comentário, sem explicação).

Regras:
- Use o contexto de parceiros e produtos fornecido para sugerir IDs reais (CODPARC, CODPROD).
- Se não tiver certeza, retorne null no ID e a confiança próxima de 0.
- Datas no formato YYYY-MM-DD.
- Quantidades como número (ex: 10.5 — ponto, não vírgula).
- Sempre devolva o array `itens`, mesmo que vazio.
- Confiança é float entre 0.0 e 1.0.
"""

PROMPT_USUARIO_TMPL = """Texto extraído do PDF:
\"\"\"{texto_pdf}\"\"\"

Lista enxuta de parceiros conhecidos (use para sugerir CODPARC):
{parceiros}

Lista enxuta de produtos conhecidos (use para sugerir CODPROD por item):
{produtos}

Devolva um JSON com este formato exato:
{{
  "cliente": {{"nome": "...", "codparc_sugerido": 0, "confianca": 0.0}},
  "data_negociacao": "YYYY-MM-DD",
  "observacao": "...",
  "itens": [
    {{"descricao_pdf": "...", "codprod_sugerido": 0, "codprod_confianca": 0.0,
      "qtd": 0.0, "codvol": "UN", "preco_unit": 0.0}}
  ],
  "confianca_geral": 0.0
}}
"""


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
# Helpers de prompt
# ---------------------------------------------------------------------------

def _formatar_lista_parceiros(parceiros: list[dict]) -> str:
    """Formata top N parceiros como linhas curtas para o prompt."""
    if not parceiros: return '(nenhum no contexto)'
    linhas = []
    for p in parceiros[:50]:
        cod = p.get('codparc') or p.get('CODPARC')
        nome = p.get('nome') or p.get('NOMEPARC') or ''
        cgc = p.get('cgc') or p.get('CGC_CPF') or ''
        linhas.append(f"  CODPARC={cod} — {nome} (CGC: {cgc})")
    return '\n'.join(linhas)


def _formatar_lista_produtos(produtos: list[dict]) -> str:
    if not produtos: return '(nenhum no contexto)'
    linhas = []
    for p in produtos[:100]:
        cod = p.get('codprod') or p.get('CODPROD')
        descr = p.get('descr') or p.get('DESCRPROD') or ''
        vol = p.get('codvol') or p.get('CODVOL') or ''
        linhas.append(f"  CODPROD={cod} — {descr} ({vol})")
    return '\n'.join(linhas)


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
    com valores neutros e baixa a confiança quando algo está estranho."""
    out: dict = {}
    cliente = parsed.get('cliente') or {}
    out['cliente'] = {
        'nome':              str(cliente.get('nome') or '')[:120],
        'codparc_sugerido':  _to_int(cliente.get('codparc_sugerido')),
        'confianca':         _to_float_0_1(cliente.get('confianca')),
    }
    out['data_negociacao'] = parsed.get('data_negociacao') or None
    out['observacao']      = (parsed.get('observacao') or None)
    if out['observacao'] is not None:
        out['observacao'] = str(out['observacao'])[:2000]

    itens_raw = parsed.get('itens') or []
    itens: list[dict] = []
    for it in itens_raw if isinstance(itens_raw, list) else []:
        itens.append({
            'descricao_pdf':     str(it.get('descricao_pdf') or '')[:500],
            'codprod_sugerido':  _to_int(it.get('codprod_sugerido')),
            'codprod_confianca': _to_float_0_1(it.get('codprod_confianca')),
            'qtd':               _to_float(it.get('qtd')),
            'codvol':            str(it.get('codvol') or 'UN').upper()[:10],
            'preco_unit':        _to_float(it.get('preco_unit')),
        })
    out['itens']            = itens
    out['confianca_geral']  = _to_float_0_1(parsed.get('confianca_geral'))
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

def extrair_pedido_de_pdf(texto_pdf: str,
                           parceiros_contexto: list[dict] | None = None,
                           produtos_contexto: list[dict] | None = None) -> dict:
    """Chama o LLM local e devolve o pedido extraído + telemetria.

    Retorno SEMPRE com `ok` (True/False). Em caso de falha, devolve `error`.
    Em caso de sucesso, devolve campos normalizados + `resposta_crua` para audit.
    """
    if not texto_pdf or not texto_pdf.strip():
        return {'ok': False, 'error': 'texto_pdf vazio.'}

    cfg = _config()
    parceiros = _formatar_lista_parceiros(parceiros_contexto or [])
    produtos = _formatar_lista_produtos(produtos_contexto or [])

    prompt_user = PROMPT_USUARIO_TMPL.format(
        texto_pdf=texto_pdf[:15000],  # trava de tamanho — PDFs muito grandes truncam
        parceiros=parceiros,
        produtos=produtos,
    )

    cliente = _cliente_ollama()
    ultima_excecao: Exception | None = None
    for tentativa in range(1, cfg['retries'] + 1):
        try:
            logger.info(f"LLM tentativa {tentativa}/{cfg['retries']} (modelo={cfg['modelo']})")
            resposta = cliente.chat(
                model=cfg['modelo'],
                messages=[
                    {'role': 'system', 'content': PROMPT_SISTEMA},
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
