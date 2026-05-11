import logging
import json
from datetime import date as _date, datetime as _datetime
from .services.oracle_conn import (
    autenticar_usuario_sankhya,
    desmembrar_pedido_classificacao,
    unificar_pedido_classificacao,
    consultar_saldo_lote_disponivel,
    consultar_pedidos_abertos_para_atribuicao,
    consultar_fabricantes_disponiveis,
    consultar_vinculos_de_lote,
    atribuir_lote_item_pedido,
    desvincular_lote_item_pedido,
    consultar_candidatos_pedido_para_nota,
    inserir_vinculo_manual_pedido_nota,
    remover_vinculo_manual_pedido_nota,
    criar_pedido_retroativo_a_partir_de_nota,
    resolver_nota_orfa_automatica,
    humanizar_erro_oracle,
    # Importação por e-mail
    listar_pedidos_email_pendentes,
    obter_pedido_email_completo,
    atualizar_pedido_email_status,
    atualizar_pedido_email_item,
    deletar_pedido_email_item,
    vincular_nunota_pedido_email,
)

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .decorators import _get_json_payload, exige_grupo
logger = logging.getLogger(__name__)


# ==============================================================================
# controle de acesso às views (decorators personalizados)
# ==============================================================================

def login_view(request):
    if request.method == 'POST':
        usuario = request.POST.get('usuario')
        senha = request.POST.get('senha')
        
        from sankhya_integration.services.oracle_conn import autenticar_usuario_sankhya
        res = autenticar_usuario_sankhya(usuario, senha)
        
        if res.get('autenticado'):
            request.session['codusu'] = res.get('codusu')
            request.session['nomeusu'] = res.get('nome')
            request.session['grupos'] = res.get('grupos', [])
            request.session['nome'] = res.get('nome')
            return redirect('home') # Logou? Vai pra Home.
        else:
            # Não logou? Cria a mensagem de erro e joga pra Home.
            msg_erro = res.get('error', 'Usuário ou senha inválidos.')
            messages.error(request, msg_erro)
            
    # Se tentarem acessar a URL /login direto pelo navegador, joga pra Home
    return redirect('home') 

def logout_view(request):
    request.session.flush()
    return redirect('home') # Deslogou? Volta pra Home.


# ==============================================================================
# IMPORTAÇÕES SEGURAS (Oracle DB)
# Tratamento para não quebrar a aplicação caso o driver oracle não esteja instalado
# ==============================================================================
try:
    from sankhya_integration.services.oracle_conn import (
        obter_conexao_oracle,
        verificar_permissao_escrita,
        consultar_parceiros_oracle,
        consultar_produtos_oracle,
        consultar_tipos_operacao_oracle,
        consultar_tipos_negociacao_oracle,
        consultar_empresas_oracle,
        consultar_cabecalho_venda_oracle,
        atualizar_cabecalho_venda_banco,
        consultar_naturezas_oracle,
        consultar_centros_resultado_oracle,
        listar_notas_compra_paginado,
        listar_itens_por_nota,
        listar_lotes_para_classificacao,
        inserir_cabecalho_nota_banco,
        atualizar_cabecalho_nota_banco,
        recalcular_totais_nota_banco,
        excluir_nota_completa_banco,
        inserir_item_nota_banco,
        atualizar_item_nota_banco,
        excluir_itens_nota_banco,
        obter_detalhes_lote_completo,
        atualizar_descarte_origem,
        consultar_vales_comercial,
        atualizar_preco_inicial_entrada,
        atualizar_peso_comercial_entrada,
        consultar_lista_ultimas_vendas,
        listar_vendas_paginado,
        faturar_pedido_venda_banco,
    )
    ORACLE_DISPONIVEL = True
except Exception as exc:
    logger.warning('Erro ao importar serviços Oracle: %s', exc)
    ORACLE_DISPONIVEL = False
    
    def _ausente(nome_funcao):
        def _fn(*args, **kwargs):
            raise RuntimeError(f"A função '{nome_funcao}' está inacessível. O Oracle falhou ao carregar.")
        return _fn

    # Mocks para não travar o Django no start
    consultar_parceiros_oracle = _ausente('consultar_parceiros_oracle')
    consultar_produtos_oracle = _ausente('consultar_produtos_oracle')
    consultar_tipos_operacao_oracle = _ausente('consultar_tipos_operacao_oracle')
    consultar_tipos_negociacao_oracle = _ausente('consultar_tipos_negociacao_oracle')
    consultar_empresas_oracle = _ausente('consultar_empresas_oracle')
    consultar_cabecalho_venda_oracle = _ausente('consultar_cabecalho_venda_oracle')
    atualizar_cabecalho_venda_banco = _ausente('atualizar_cabecalho_venda_banco')
    consultar_naturezas_oracle = _ausente('consultar_naturezas_oracle')
    consultar_centros_resultado_oracle = _ausente('consultar_centros_resultado_oracle')
    listar_notas_compra_paginado = _ausente('listar_notas_compra_paginado')
    listar_itens_por_nota = _ausente('listar_itens_por_nota')
    listar_lotes_para_classificacao = _ausente('listar_lotes_para_classificacao')
    inserir_cabecalho_nota_banco = _ausente('inserir_cabecalho_nota_banco')
    atualizar_cabecalho_nota_banco = _ausente('atualizar_cabecalho_nota_banco')
    recalcular_totais_nota_banco = _ausente('recalcular_totais_nota_banco')
    excluir_nota_completa_banco = _ausente('excluir_nota_completa_banco')
    inserir_item_nota_banco = _ausente('inserir_item_nota_banco')
    atualizar_item_nota_banco = _ausente('atualizar_item_nota_banco')
    excluir_itens_nota_banco = _ausente('excluir_itens_nota_banco')
    obter_detalhes_lote_completo = _ausente('obter_detalhes_lote_completo')
    atualizar_descarte_origem = _ausente('atualizar_descarte_origem')
    consultar_vales_comercial = _ausente('consultar_vales_comercial')
    verificar_permissao_escrita = lambda: False
    obter_conexao_oracle = _ausente('obter_conexao_oracle')
    listar_vendas_paginado = _ausente('listar_vendas_paginado')
    faturar_pedido_venda_banco = _ausente('faturar_pedido_venda_banco')

# ==============================================================================
# FUNÇÕES UTILITÁRIAS (Parse e Conversão)
# ==============================================================================


def _data_br_para_iso(d: str|None) -> str|None:
    """Converte string YYYY-MM-DD para formato interno (ou mantém se já estiver certo)."""
    if not d: return None
    s = str(d).strip()
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s

def _primeiro_item(val):
    """Extrai primeiro item de lista (para contornar request.POST.getlist intrusivos)."""
    if isinstance(val, (list, tuple)): return val[0] if val else None
    return val

def _converter_para_inteiro(val, default=None):
    v = _primeiro_item(val)
    if v in (None, '', 'None', 'none', 'null'): return default
    try: return int(v)
    except Exception:
        try: return int(str(v))
        except Exception: return default

def _converter_para_float(val, default=None):
    v = _primeiro_item(val)
    if v in (None, '', 'None', 'none', 'null'): return default
    try: return float(v)
    except Exception:
        try: return float(str(v))
        except Exception: return default


# ==============================================================================
# ROTAS GLOBAIS DE PÁGINA
# ==============================================================================

def home(request: HttpRequest) -> HttpResponse:
    return render(request, "sankhya_integration/home.html")

def health(request: HttpRequest) -> HttpResponse:
    """Healthcheck profundo: ping do Oracle + checagem da view de saldo do Rastreio.

    Use ``/sankhya/health/?deep=1`` para incluir checagens mais lentas (view
    de saldo + contagem da TGFCAB). Sem ``deep``, faz só o ping rápido.
    """
    deep = (request.GET.get('deep') or '').lower() in ('1', 'true', 'yes')
    status = {
        'oracle_import': ORACLE_DISPONIVEL,
        'write_enabled': verificar_permissao_escrita() if ORACLE_DISPONIVEL else False,
    }
    if not ORACLE_DISPONIVEL:
        status['error'] = 'Driver Oracle inativo.'
        # 200 propositalmente — driver inativo é estado de configuração,
        # não falha de runtime; consumidores antigos esperam 200 aqui.
        return JsonResponse(status)

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            # Ping rápido — sempre roda
            cur.execute("SELECT 1 FROM DUAL")
            status['db_ping'] = bool(cur.fetchone())

            if deep:
                # Verifica que a view do Rastreio existe e responde (essencial pro WMS)
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE WHERE ROWNUM <= 1"
                    )
                    cur.fetchone()
                    status['rastreio_view'] = 'ok'
                except Exception as e:
                    status['rastreio_view'] = 'error'
                    status['rastreio_view_error'] = humanizar_erro_oracle(e)

                # Conta pedidos abertos (TOP 34) — sanity check da Venda
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM TGFCAB "
                        "WHERE CODTIPOPER = 34 AND STATUSNOTA <> 'E'"
                    )
                    status['pedidos_abertos'] = int(cur.fetchone()[0] or 0)
                except Exception as e:
                    status['pedidos_abertos_error'] = humanizar_erro_oracle(e)
    except Exception as e:
        status['db_ping'] = False
        status['error'] = humanizar_erro_oracle(e)
        return JsonResponse(status, status=503)

    return JsonResponse(status)

# ==============================================================================
# ROTAS DA API: PESQUISAS RÁPIDAS (TYPEAHEADS)
# Usadas pelos modais para buscar dados enquanto o usuário digita
# ==============================================================================

def api_pesquisar_pedidos(request: HttpRequest) -> JsonResponse:
    """Busca números de NUNOTA únicos da TOP 11 (Pedidos de Origem)."""
    q = request.GET.get("q", "").strip()
    lim = int(request.GET.get("limit", 10))
    if not q or not ORACLE_DISPONIVEL: return JsonResponse({"results": []})

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        # Busca NUNOTAs da TOP 11 que comecem com o que foi digitado
        sql = """
            SELECT DISTINCT NUNOTA 
            FROM TGFCAB 
            WHERE CODTIPOPER = 11 
              AND TO_CHAR(NUNOTA) LIKE :p
            ORDER BY NUNOTA DESC
        """
        sql_limit = f"SELECT NUNOTA FROM ({sql}) WHERE ROWNUM <= :lim"
        cur.execute(sql_limit, {'p': f"{q}%", 'lim': lim})
        linhas = cur.fetchall()

    return JsonResponse({"results": [{"nunota": r[0]} for r in linhas]})

def api_pesquisar_lotes(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    if not q or not ORACLE_DISPONIVEL: 
        return JsonResponse({"results": []})

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        sql = """
            SELECT DISTINCT CODAGREGACAO 
            FROM TGFITE 
            WHERE CODAGREGACAO IS NOT NULL 
              AND UPPER(CODAGREGACAO) LIKE :p
            ORDER BY CODAGREGACAO
        """
        sql_limit = f"SELECT CODAGREGACAO FROM ({sql}) WHERE ROWNUM <= 10"
        cur.execute(sql_limit, {'p': f"%{q.upper()}%"})
        
        # 👉 AQUI ESTÁ A CHAVE: Mudamos para 'label'
        resultados = [{"label": str(r[0])} for r in cur.fetchall()]

    return JsonResponse({"results": resultados})

def api_pesquisar_parceiros(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    try: limite = int(request.GET.get("limit", 10))
    except Exception: limite = 10
    
    linhas = consultar_parceiros_oracle(q, limite=limite) if ORACLE_DISPONIVEL else []
    dados = [{"codparc": int(c), "nomeparc": n} for c, n in linhas]
    return JsonResponse({"results": dados})

def api_pesquisar_tipos_operacao(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limite = int(request.GET.get("limit", 10))
    linhas = consultar_tipos_operacao_oracle(q, limite=limite) if ORACLE_DISPONIVEL else []
    dados = [{"cod": int(c), "descr": (d or "")} for c, d in linhas]
    return JsonResponse({"results": dados})

def api_pesquisar_naturezas(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limite = int(request.GET.get("limit", 10))
    linhas = consultar_naturezas_oracle(q, limite=limite) if ORACLE_DISPONIVEL else []
    return JsonResponse({"results": [{"cod": int(c), "descr": d} for c, d in linhas]})

def api_pesquisar_tipos_negociacao(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limite = int(request.GET.get("limit", 10))
    linhas = consultar_tipos_negociacao_oracle(q, limite=limite) if ORACLE_DISPONIVEL else []
    return JsonResponse({"results": [{"cod": int(c), "descr": d} for c, d in linhas]})

def api_pesquisar_empresas(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limite = int(request.GET.get("limit", 10))
    linhas = consultar_empresas_oracle(q, limite=limite) if ORACLE_DISPONIVEL else []
    return JsonResponse({"results": [{"cod": int(c), "descr": d or ""} for c, d in linhas]})

def api_pesquisar_centros_resultado(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limite = int(request.GET.get("limit", 10))
    linhas = consultar_centros_resultado_oracle(q, limite=limite) if ORACLE_DISPONIVEL else []
    return JsonResponse({"results": [{"cod": int(c), "descr": d} for c, d in linhas]})

def api_pesquisar_lotes(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get('q') or '').strip()
    try: lim = int(request.GET.get('limit', 10))
    except Exception: lim = 10
    
    if not q or not ORACLE_DISPONIVEL:
        return JsonResponse({"results": []})
        
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT CODAGREGACAO FROM ("
            "  SELECT DISTINCT CODAGREGACAO FROM TGFITE"
            "   WHERE CODAGREGACAO IS NOT NULL AND UPPER(CODAGREGACAO) LIKE :p"
            "   ORDER BY CODAGREGACAO"
            ") WHERE ROWNUM <= :lim",
            p=f"%{q.upper()}%", lim=max(1, lim)
        )
        linhas = cur.fetchall()
    return JsonResponse({"results": [{"cod": (c or ""), "descr": ""} for (c,) in linhas]})

def api_pesquisar_volumes(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "").upper()
    lim = int(request.GET.get("limit", 10))
    
    if not ORACLE_DISPONIVEL: return JsonResponse({"results": []})
        
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if q:
            cur.execute(
                "SELECT CODVOL, DESCRVOL FROM ("
                "  SELECT CODVOL, DESCRVOL, 0 PRIO FROM TGFVOL WHERE UPPER(CODVOL) = :k"
                "  UNION ALL"
                "  SELECT CODVOL, DESCRVOL, 1 PRIO FROM TGFVOL WHERE UPPER(CODVOL) LIKE :p"
                "  UNION ALL"
                "  SELECT CODVOL, DESCRVOL, 2 PRIO FROM TGFVOL WHERE UPPER(DESCRVOL) LIKE :d"
                ") WHERE ROWNUM <= :lim ORDER BY PRIO, CODVOL",
                k=q, p=f"{q}%", d=f"{q}%", lim=lim,
            )
        else:
            cur.execute("SELECT CODVOL, DESCRVOL FROM (SELECT CODVOL, DESCRVOL FROM TGFVOL ORDER BY CODVOL) WHERE ROWNUM <= :lim", lim=lim)
        linhas = cur.fetchall()
    return JsonResponse({"results": [{"cod": (c or ""), "descr": (d or "")} for c, d in linhas]})

@require_http_methods(["GET"])
def api_pesquisar_produtos_entrada(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "")
    lim = int(request.GET.get("limit", 15))
    
    # 🚀 REDIRECIONA PARA A BUSCA DE FABRICANTE SE O JS PEDIR
    if request.GET.get("fabricante") == "1":
        return api_pesquisar_produtos_fabricante(request)
    
    if not ORACLE_DISPONIVEL: 
        return JsonResponse({"results": []})

    # Extrai as flags da URL
    is_in_natura = str(request.GET.get("allow_in_natura") or "").lower() in ("1", "true", "yes", "on")
    grupo_inicia_com = request.GET.get("grupo_inicia_com")

    try:
        # Chama a nova função modularizada do oracle_conn.py
        linhas = consultar_produtos_oracle(
            q=q, 
            limit=lim, 
            allow_in_natura=is_in_natura, 
            grupo_inicia_com=grupo_inicia_com
        )
        
        # Formata o resultado exatamente como o seu JS antigo espera
        resultados = [
            {
                "cod": int(c), 
                "descr": (d or ''), 
                "selecionado": (int(s) if s is not None else 0)
            } 
            for c, d, s in linhas
        ]
        
        return JsonResponse({"results": resultados})
        
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def api_pesquisar_produtos_fabricante(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "")
    lim = int(request.GET.get("limit", 15))
    if not ORACLE_DISPONIVEL: return JsonResponse({"results": []})
        
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        
        # SQL para trazer nomes de FABRICANTES únicos que não sejam vazios
        sql = """
            SELECT DISTINCT FABRICANTE 
            FROM TGFPRO 
            WHERE NVL(ATIVO, 'S') = 'S' 
              AND REGEXP_LIKE(FABRICANTE, '[[:alnum:]]')
              AND UPPER(FABRICANTE) LIKE :p
            ORDER BY FABRICANTE
        """
        
        # Filtramos apenas se houver termo de busca, senão o Oracle pode demorar
        binds = {'p': f"%{q.upper()}%"}
        
        # Aplicamos o limite na consulta final
        sql_limit = f"SELECT FABRICANTE FROM ({sql}) WHERE ROWNUM <= :lim"
        binds['lim'] = lim

        cur.execute(sql_limit, binds)
        linhas = cur.fetchall()
        
    # Retornamos apenas o nome do fabricante
    return JsonResponse({"results": [{"fabricante": f[0]} for f in linhas]})

# ==============================================================================
# ROTAS DO MÓDULO DE COMPRAS / ENTRADA (TOP 11)
# ==============================================================================

@exige_grupo('entrada')
@ensure_csrf_cookie
def view_portal_entradas(request: HttpRequest) -> HttpResponse:
    """Renderiza a página principal com a grid de Notas/Pedidos (Painel Lateral + Lista)."""
    raw_lote = request.GET.get("lote")
    lote = (raw_lote or "").strip()
    if lote.lower() in ("", "none", "null"): lote = None
    
    raw_days = request.GET.get("days")
    if raw_days is None: days_val = None
    else:
        rd = (raw_days or "").strip().lower()
        if rd in ("all", "todos", "*", "tudo", ""): days_val = None
        else: days_val = _converter_para_inteiro(raw_days)

    parametros = {
        "days": days_val,
        "date_start": request.GET.get("start"),
        "date_end": request.GET.get("end"),
        # GARANTA QUE ESTA LINHA ESTEJA ASSIM (Sem conversão para inteiro):
        "nunota_ini": request.GET.get("nunota_ini", "").strip(), 
        "codparc": _converter_para_inteiro(request.GET.get("codparc")),
        "codprod": _converter_para_inteiro(request.GET.get("codprod")),
    }
    
    try: pagina = int(request.GET.get("page", 1))
    except Exception: pagina = 1
    if pagina < 1: pagina = 1
    tamanho_pagina = 50

    notas = listar_notas_compra_paginado(limite=tamanho_pagina + 1, offset=(pagina - 1) * tamanho_pagina, **parametros)
    tem_proxima = len(notas) > tamanho_pagina
    if tem_proxima: notas = notas[:tamanho_pagina]
    
    tem_anterior = pagina > 1

    nunota_selecionado = _converter_para_inteiro(request.GET.get("sel"))
    if nunota_selecionado is None:
        nunota_selecionado = notas[0][0] if notas else None
        
    itens_da_nota = listar_itens_por_nota(nunota_selecionado) if nunota_selecionado else []

    # Nome amigável do parceiro na barra de pesquisa após F5
    parceiro_display = ''
    try:
        if parametros.get('codparc') and ORACLE_DISPONIVEL:
            with obter_conexao_oracle() as conn:
                cur = conn.cursor()
                cur.execute("SELECT NOMEPARC FROM TGFPAR WHERE CODPARC = :k", k=int(parametros['codparc']))
                r = cur.fetchone()
                nome = (r[0] if r else '') or ''
                parceiro_display = f"{int(parametros['codparc'])} — {nome}" if nome else f"{int(parametros['codparc'])}"
    except Exception: pass

    contexto = {
        "nome_usuario": request.session.get('nomeusu', 'Usuário'),
        "notas": notas,
        "itens": itens_da_nota,
        "sel": nunota_selecionado,
        "params": parametros,
        "parc_display": parceiro_display,
        "page": pagina,
        "has_prev": tem_anterior,
        "has_next": tem_proxima,
    }
    return render(request, "sankhya_integration/entrada.html", contexto)

# Alias de retrocompatibilidade para o frontend JS ou menus do Django
def compras_portal(request: HttpRequest) -> HttpResponse: return view_portal_entradas(request)

@ensure_csrf_cookie
def view_central_compras(request: HttpRequest) -> HttpResponse:
    """Renderiza a tela de visualização de nota e retorna os dados via JSON para preencher o Modal no Portal."""
    nunota_req = request.GET.get("nunota")
    try: nunota_val = int(nunota_req) if nunota_req not in (None, "", "None", "none", "null") else None
    except ValueError: nunota_val = None
    
    itens = listar_itens_por_nota(nunota_val) if nunota_val else []
    valor_total = sum((row[8] or 0) for row in itens) if itens else 0
    
    hoje_iso = _date.today().isoformat()
    form_padrao = {
        'codemp': '10',
        'nronota': '',
        'dtneg': hoje_iso,
        'dtmov': hoje_iso,
        'dtentsai': hoje_iso,
        'hrmov': '',
        'codparc': '',
        'codtipoper': (request.GET.get('codtipoper') or ''),
        'codnat': (request.GET.get('codnat') or '20010100'),
        'codcencus': (request.GET.get('codcencus') or '10100'),
        'obs': '',
    }

    # Helper para requisições AJAX do frontend (pré-preenchimento do modal Cabeçalho para Edição)
    if request.GET.get('ajax_header') in ('1', 'true', 'yes'):
        resposta_form = {
            'nunota': nunota_val,
            'codemp': str(form_padrao.get('codemp')),
            'dtneg': form_padrao.get('dtneg'),
            'codparc': '',
            'nomparc': '',
            'codtipoper': form_padrao.get('codtipoper'),
            'codtipoper_descr': '',
            'codnat': form_padrao.get('codnat'),
            'codnat_descr': '',
            'codcencus': form_padrao.get('codcencus'),
            'codcencus_descr': '',
            'obs': '',
        }
        
        # 🔥 A MÁGICA AQUI: Se tem NUNOTA, vai no Oracle buscar os dados REAIS!
        if nunota_val and ORACLE_DISPONIVEL:
            try:
                with obter_conexao_oracle() as conn:
                    cur = conn.cursor()
                    sql = """
                        SELECT 
                            c.CODEMP, c.CODPARC, p.NOMEPARC, 
                            c.CODTIPOPER, t.DESCROPER, 
                            c.CODNAT, n.DESCRNAT,
                            c.CODCENCUS, cr.DESCRCENCUS,
                            c.DTNEG, c.OBSERVACAO
                        FROM TGFCAB c
                        LEFT JOIN TGFPAR p ON c.CODPARC = p.CODPARC
                        LEFT JOIN TGFTOP t ON c.CODTIPOPER = t.CODTIPOPER AND t.DHALTER = c.DHTIPOPER
                        LEFT JOIN TGFNAT n ON c.CODNAT = n.CODNAT
                        LEFT JOIN TSICUS cr ON c.CODCENCUS = cr.CODCENCUS
                        WHERE c.NUNOTA = :n AND ROWNUM = 1
                    """
                    cur.execute(sql, n=nunota_val)
                    row = cur.fetchone()
                    
                    if row:
                        resposta_form.update({
                            'codemp': str(row[0] or '10'),
                            'codparc': str(row[1] or ''),
                            'nomparc': str(row[2] or ''),
                            'codtipoper': str(row[3] or ''),
                            'codtipoper_descr': str(row[4] or ''),
                            'codnat': str(row[5] or ''),
                            'codnat_descr': str(row[6] or ''),
                            'codcencus': str(row[7] or ''),
                            'codcencus_descr': str(row[8] or ''),
                            'dtneg': row[9].strftime('%Y-%m-%d') if row[9] else form_padrao.get('dtneg'),
                            'obs': str(row[10] or ''),
                        })
            except Exception as e:
                logger.error("Erro SQL cabeçalho ajax: %s", e)

        return JsonResponse({'form': resposta_form})

    contexto = {
        "nunota": nunota_val,
        "itens": itens,
        "vtotal": valor_total,
        "form": form_padrao,
        "write_enabled": verificar_permissao_escrita(),
    }
    return render(request, "sankhya_integration/compras_central.html", contexto)

def api_salvar_novo_cabecalho(request: HttpRequest) -> HttpResponse:
    """Cria um novo cabeçalho (Nota nova) usando dados do Modal Cabeçalho."""
    if request.method != 'POST': return view_central_compras(request)

    dados_json = _get_json_payload(request)
    def_get = lambda nome, def_val='': (dados_json.get(nome) or request.POST.get(nome) or def_val)

    payload_banco = {
        'CODEMP': _converter_para_inteiro(def_get('codemp', '10')),
        'CODPARC': _converter_para_inteiro(def_get('codparc')),
        'CODTIPOPER': _converter_para_inteiro(def_get('codtipoper')),
        'CODNAT': _converter_para_inteiro(def_get('codnat')),
        'CODCENCUS': _converter_para_inteiro(def_get('codcencus')),
        'DTNEG': _data_br_para_iso(def_get('dtneg')),
        'DTMOV': _data_br_para_iso(def_get('dtmov') or def_get('dtneg')),
        'DTENTSAI': _data_br_para_iso(def_get('dtentsai') or def_get('dtneg')),
        'HRMOV': def_get('hrmov'),
        'NUMNOTA': def_get('numnota') or def_get('nronota') or None,
        'OBSERVACAO': def_get('obs') or None,
    }
    
    try:
        plano = inserir_cabecalho_nota_banco(payload_banco, simulacao=False)
        plano['ok'] = plano.get('executed', False)

        # Se foi uma chamada via Javascript Modal
        if dados_json or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse(plano, status=200 if plano['ok'] else 400)

        # Se for um POST clássico de formulário (Legado)
        if plano.get('executed') and plano.get('nunota'):
            return redirect(f"/sankhya/compras/central/?nunota={plano['nunota']}")

    except Exception as e:
        logger.exception("Erro ao salvar o cabeçalho novo")
        if dados_json or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)

    # Fallback caso falhe
    return render(request, "sankhya_integration/compras_central.html", {'write_enabled': verificar_permissao_escrita()})

def api_atualizar_cabecalho_existente(request: HttpRequest) -> JsonResponse:
    """Atualiza as informações de uma nota que já existe (Botão Editar Cabeçalho)."""
    if request.method != 'POST': return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    
    dados_json = _get_json_payload(request)
    if not dados_json: return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)
        
    nunota = _converter_para_inteiro(dados_json.get('nunota'))
    if not nunota: return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)

    plano = atualizar_cabecalho_nota_banco({
        'NUNOTA': nunota,
        'NUMNOTA': dados_json.get('nronota'),
        'DTNEG': dados_json.get('dtneg'),
        'DTMOV': dados_json.get('dtmov'),
        'DTENTSAI': dados_json.get('dtentsai'),
        'HRMOV': dados_json.get('hrmov'),
        'CODPARC': _converter_para_inteiro(dados_json.get('codparc')),
        'CODTIPOPER': _converter_para_inteiro(dados_json.get('codtipoper')),
        'OBSERVACAO': dados_json.get('obs'),
        # 🔥 REMOVIDO o envio forçado do AD_NUMPEDIDOORIG. O oracle_conn fará a auto-cura.
    }, simulacao=False)
    
    if not plano.get('executed'):
        erros = plano.get('errors', [])
        return JsonResponse({"ok": False, "error": erros[0] if erros else 'Falha ao atualizar cabeçalho'}, status=400)
    
    # Quando altera o cabeçalho, tem que recalcular para manter as dependências (Ex: VLRNOTA)
    recalculo = recalcular_totais_nota_banco(nunota)
    if recalculo.get('ok'): plano.update(recalculo)

    return JsonResponse(plano, status=200)

def api_listar_itens_nota(request: HttpRequest) -> JsonResponse:
    """Busca e retorna todos os produtos/itens pendurados em um NUNOTA (Para popular a tabela do Modal Itens)."""
    if request.method != 'GET': return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    
    try: nunota = int(request.GET.get('nunota'))
    except Exception: return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)

    try:
        linhas = listar_itens_por_nota(nunota) or []
        retorno = []
        for r in linhas:
            seq = r[1] if len(r) > 1 else None
            qtdneg = float(r[5] or 0) if len(r) > 5 else 0.0
            qtdconferida = float(r[11]) if len(r) > 11 and r[11] is not None else qtdneg
            
            retorno.append({
                'nunota': nunota,
                'sequencia': int(seq) if seq is not None else None,
                'cod': int(r[2]) if len(r) > 2 and r[2] is not None else None,
                'descr': r[3] if len(r) > 3 else '',
                'lote': r[0] if len(r) > 0 else '',
                'codvol': r[4] if len(r) > 4 else '',
                'qtd': qtdconferida,
                'peso': float(r[6]) if len(r) > 6 and r[6] is not None else None,
                'vlu': float(r[7] or 0) if len(r) > 7 else 0.0,
                'vlt': float(r[8] or 0) if len(r) > 8 else 0.0,
                'total': qtdneg, 
                'obs': r[9] if len(r) > 9 else '',
                'classifica': (str(r[10]).upper() != 'N') if len(r) > 10 and r[10] is not None else None,
                'geraproducao': str(r[10]).upper() if len(r) > 10 and r[10] is not None else None,
                'codvolparc': r[12] if len(r) > 12 and r[12] is not None else '',
            })
        return JsonResponse({"ok": True, "items": retorno})
    except Exception as e:
        logger.exception(f"Erro ao listar itens da nota {nunota}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def api_salvar_item_nota(request: HttpRequest) -> JsonResponse:
    """Insere ou Atualiza um item na nota aplicando a regra de conversão e travas de segurança."""
    if request.method != 'POST': return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    dados_raw = _get_json_payload(request)
    if not dados_raw: return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    # Força tudo para maiúsculo para evitar erros de digitação
    payload = {k.upper(): v for k, v in dados_raw.items()}
    
    # Interceptação de Volume
    vol_digitado = str(payload.get('CODVOL') or payload.get('VOL') or 'KG').strip().upper()
    payload['CODVOLPARC'] = vol_digitado
    
    if vol_digitado in ('CX', 'SC'):
        payload['CODVOL'] = 'KG'
    else:
        payload['CODVOL'] = vol_digitado
    
    with obter_conexao_oracle() as conn: 
        try:
            nunota = _converter_para_inteiro(payload.get('NUNOTA'))
            seq = _converter_para_inteiro(payload.get('SEQUENCIA'))
            
            if not nunota or not payload.get('CODPROD'):
                return JsonResponse({"ok": False, "error": "NUNOTA e CODPROD são obrigatórios"}, status=400)

            if seq:
                # =========================================================================
                # 🔥 TRAVA DE SEGURANÇA PARA EDIÇÃO
                # =========================================================================
                cur = conn.cursor()
                
                # Descobre em qual tela o usuário está (Doca=11, Classificação=26)
                cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
                top_atual_row = cur.fetchone()
                if not top_atual_row:
                    return JsonResponse({"ok": False, "error": "Cabeçalho não encontrado."}, status=404)
                
                top_atual = int(top_atual_row[0])

                # Pega o Lote do item que ele quer editar
                cur.execute("SELECT CODAGREGACAO FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s", n=nunota, s=seq)
                row_lote = cur.fetchone()
                
                if row_lote and row_lote[0]:
                    lote = row_lote[0]
                    
                    # 🔒 Se estiver na Entrada (11), trava se já foi pra Classificação(26) ou Faturamento(13)
                    if top_atual == 11:
                        cur.execute("""
                            SELECT COUNT(1) FROM TGFCAB c JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                            WHERE c.CODTIPOPER IN (13, 26) AND i.CODAGREGACAO = :l AND NVL(c.STATUSNOTA, 'A') <> 'E'
                        """, l=lote)
                        if cur.fetchone()[0] > 0:
                            return JsonResponse({"ok": False, "error": f"Bloqueado! O Lote {lote} já avançou no fluxo e não pode ser editado."}, status=403)
                    
                    # 🔒 Se estiver na Classificação (26), trava se já foi pro Comercial(13, 35, 37)
                    elif top_atual == 26:
                        cur.execute("""
                            SELECT COUNT(1) FROM TGFCAB c JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                            WHERE c.CODTIPOPER IN (13, 35, 37) AND i.CODAGREGACAO = :l AND NVL(c.STATUSNOTA, 'A') <> 'E'
                        """, l=lote)
                        if cur.fetchone()[0] > 0:
                            return JsonResponse({"ok": False, "error": f"Bloqueado! O Lote {lote} já foi negociado e não pode ser editado."}, status=403)
                # =========================================================================
                
                # Resgata a origem real para não perder a rastreabilidade
                cur.execute("SELECT AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
                res_origem = cur.fetchone()
                origem_val = res_origem[0] if res_origem and res_origem[0] else nunota

                qtd_conferida = payload.get('QTDCONFERIDA')
                if qtd_conferida is None: qtd_conferida = payload.get('QTDNEG')

                sql = """
                    UPDATE TGFITE 
                    SET QTDNEG = :qtdneg, 
                        PESO = :peso, 
                        CODVOL = :codvol,
                        CODVOLPARC = :codvolparc,
                        QTDCONFERIDA = :qtdconferida,
                        OBSERVACAO = :obs,
                        AD_NUMPEDIDOORIG = :origem
                    WHERE NUNOTA = :nunota AND SEQUENCIA = :sequencia
                """
                
                cur.execute(sql, {
                    'qtdneg': float(payload.get('QTDNEG', 0)), 
                    'peso': float(payload.get('PESO', 0)), 
                    'codvol': payload['CODVOL'],               
                    'codvolparc': payload['CODVOLPARC'],       
                    'qtdconferida': float(qtd_conferida),
                    'obs': payload.get('OBSERVACAO'),
                    'origem': origem_val,
                    'nunota': int(nunota),
                    'sequencia': int(seq)
                })
                plano = {'executed': True, 'ok': True}
            else:
                # INSERÇÃO NOVA
                plano = inserir_item_nota_banco(payload, simulacao=False, conexao_existente=conn)

            # Recalcula totais da nota após inserir/editar
            recalculo = recalcular_totais_nota_banco(nunota, conexao_existente=conn)
            conn.commit() 
            plano.update(recalculo)
            return JsonResponse(plano, status=200)

        except Exception as e:
            conn.rollback() 
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)

def api_excluir_itens_nota(request: HttpRequest) -> JsonResponse:
    """Exclui itens individualmente com travas de segurança baseadas na TOP (11 ou 26)."""
    if request.method != 'POST': return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    
    payload = _get_json_payload(request)
    nunota = _converter_para_inteiro(payload.get('nunota'))
    sequencias = payload.get('sequencias') or []
    
    # 🔥 NOVA FLAG: Verifica se o JS quer apenas testar a trava
    apenas_checar = payload.get('apenas_checar', False) 
    
    if not nunota or not sequencias:
        return JsonResponse({"ok": False, "error": "Dados insuficientes"}, status=400)
    
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
            top_atual_row = cur.fetchone()
            if not top_atual_row:
                return JsonResponse({"ok": False, "error": "Cabeçalho não encontrado no banco."}, status=404)
            
            top_atual = int(top_atual_row[0])

            # --- VERIFICAÇÃO DE VÍNCULOS ---
            for seq in sequencias:
                cur.execute("SELECT CODAGREGACAO FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s", n=nunota, s=seq)
                row = cur.fetchone()
                if not row or not row[0]: continue
                lote = row[0]

                if top_atual == 11:
                    cur.execute("""
                        SELECT COUNT(1) 
                        FROM TGFCAB c 
                        JOIN TGFITE i ON c.NUNOTA = i.NUNOTA 
                        WHERE c.CODTIPOPER IN (13, 26) 
                          AND i.CODAGREGACAO = :l 
                          AND NVL(c.STATUSNOTA, 'A') <> 'E'
                    """, l=lote)
                    
                    if cur.fetchone()[0] > 0:
                        return JsonResponse({"ok": False, "error": f"Bloqueado! Verifique CLASSIFICAÇÃO ou COMERCIAL. Lote {lote} "}, status=403)

                elif top_atual == 26:
                    cur.execute("""
                        SELECT COUNT(1) 
                        FROM TGFCAB c 
                        JOIN TGFITE i ON c.NUNOTA = i.NUNOTA 
                        WHERE c.CODTIPOPER IN (13, 35, 37) 
                          AND i.CODAGREGACAO = :l 
                          AND NVL(c.STATUSNOTA, 'A') <> 'E'
                    """, l=lote)
                    
                    if cur.fetchone()[0] > 0:
                        return JsonResponse({"ok": False, "error": f"Bloqueado! Lote {lote} já foi negociado pelo Comercial."}, status=403)

            # ==========================================================
            # 🔥 SE FOI SÓ UMA CHECAGEM DO JS, PARA AQUI E DÁ SINAL VERDE!
            # ==========================================================
            if apenas_checar:
                return JsonResponse({"ok": True, "message": "Pode excluir"})

            # --- EXECUTA A EXCLUSÃO REAL ---
            seqs_inteiras = [int(s) for s in sequencias]
            binds = {'nunota': nunota}
            chaves_bind = []
            for i, s in enumerate(seqs_inteiras):
                chave = f'seq{i}'; chaves_bind.append(f':{chave}'); binds[chave] = s
            
            sql_excluir = f"DELETE FROM TGFITE WHERE NUNOTA = :nunota AND SEQUENCIA IN ({', '.join(chaves_bind)})"
            cur.execute(sql_excluir, binds)
            
            cur.execute("SELECT COUNT(*) FROM TGFITE WHERE NUNOTA = :n", n=nunota)
            cab_excluido = False
            if cur.fetchone()[0] == 0:
                cur.execute("DELETE FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
                cab_excluido = True

            conn.commit()
            
        resposta = {'ok': True, 'message': 'Item excluído.', 'cabecalho_excluido': cab_excluido}
        return JsonResponse(resposta)
        
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

def api_finalizar_nota_compra(request: HttpRequest) -> JsonResponse:
    """Carimba a nota como 'Finalizada' (Muda STATUSNOTA para 'L' e preenche a DTFATUR)."""
    if request.method != 'POST': return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    payload = _get_json_payload(request)
    
    nunota = _converter_para_inteiro(payload.get('nunota'))
    if not nunota: return JsonResponse({"ok": False, "error": "Informe o NUNOTA para finalizar"}, status=400)
    
    if not verificar_permissao_escrita(): return JsonResponse({"ok": False, "error": "Escrita desabilitada no sistema"}, status=403)
    
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE TGFCAB 
                SET DTFATUR = SYSDATE, STATUSNOTA = 'L', DTALTER = SYSDATE
                WHERE NUNOTA = :nunota
            """, nunota=nunota)
            
            linhas_afetadas = cur.rowcount
            conn.commit()
            
            return JsonResponse({"ok": True, "nunota": nunota, "rows_updated": linhas_afetadas, "message": "Nota finalizada com sucesso."})
            
    except Exception as e:
        logger.exception('Erro ao finalizar a nota de compra')
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def api_excluir_nota_compra(request: HttpRequest) -> JsonResponse:
    """Exclui o cabeçalho e itens, ou apenas verifica as travas de segurança."""
    if request.method != 'POST': return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    
    payload = _get_json_payload(request)
    nunota = _converter_para_inteiro(payload.get('nunota'))
    # NOVA FLAG: Verifica se o JS quer apenas validar
    apenas_checar = payload.get('apenas_checar', False) 
    
    if not nunota: return JsonResponse({"ok": False, "error": "Informe o NUNOTA"}, status=400)
    
    # =========================================================================
    # TRAVA DE SEGURANÇA
    # =========================================================================
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(1) FROM TGFCAB WHERE CODTIPOPER = 26 AND NUMNOTA = :nunota", nunota=nunota)
            tem_classificacao = cur.fetchone()[0]
            
            if tem_classificacao > 0:
                return JsonResponse({"ok": False, "error": "Não é possível excluir esta nota de entrada, já possui itens classificados."}, status=403)
                
    except Exception as e:
        logger.exception("Erro ao checar trava de classificação")
        return JsonResponse({"ok": False, "error": f"Erro de segurança: {e}"}, status=500)
        
    # Se o frontend mandou 'apenas_checar', nós paramos aqui com sinal verde!
    if apenas_checar:
        return JsonResponse({"ok": True, "message": "Pode excluir"})

    # =========================================================================
    # Passou pela trava e NÃO é só checagem: Executa a exclusão real
    # =========================================================================
    resposta = excluir_nota_completa_banco(nunota, simulacao=False)
    return JsonResponse(resposta, status=200 if resposta.get('ok') else 400)


# ==============================================================================
# MÓDULO CLASSIFICAÇÃO (TOP 26)
# Funções exclusivas da tela de Classificação de Lotes.
# ==============================================================================

@exige_grupo('classificacao')
@ensure_csrf_cookie
def view_classificacao_lotes(request: HttpRequest) -> HttpResponse:
    """Renderiza a interface principal de Classificação de Lotes (TOP 26)."""
    
    # 1. Verifica se existe algum status na URL
    tem_filtro_status = any(k in request.GET for k in ['status_verde', 'status_amarelo', 'status_vermelho'])

    if tem_filtro_status:
        # Se tem na URL, obedece a URL (ex: após um F5)
        status_verde = request.GET.get('status_verde') == 'true'
        status_amarelo = request.GET.get('status_amarelo') == 'true'
        status_vermelho = request.GET.get('status_vermelho') == 'true'
    else:
        # 🎯 PADRÃO DA PÁGINA (Se a URL estiver limpa)
        status_verde = False
        status_amarelo = True
        status_vermelho = True

    # 2. Empacota tudo para mandar para o HTML
    parametros = {
        "status_verde": status_verde,
        "status_amarelo": status_amarelo,
        "status_vermelho": status_vermelho,
        # Manteremos os outros filtros (lote, pedido, etc) originais por enquanto
        "lote": request.GET.get("lote", "").strip(),
        "nunota_origem": _converter_para_inteiro(request.GET.get("origem")),
    }

    contexto = {
        "params": parametros,
        "write_enabled": verificar_permissao_escrita(),
    }

    return render(request, "sankhya_integration/classificacao.html", contexto)

@require_http_methods(["GET"])
def api_listar_lotes_classificacao(request: HttpRequest) -> JsonResponse:
    try:
        page_num = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page_num = 1

    filtros = {
        "lote": request.GET.get("lote"),
        "nunota_ini": request.GET.get("nunota_ini"),
        "page": page_num,
        "codparc": request.GET.get("codparc"),
        "fabricante": request.GET.get("fabricante"),
        "date_start": request.GET.get("date_start"),
        "date_end": request.GET.get("date_end"),
        "status_list": request.GET.getlist('status')
    }
    
    if not filtros["status_list"]:
        filtros["status_list"] = ['AMARELO', 'VERMELHO']

    try:
        linhas = listar_lotes_para_classificacao(filtros)
        lotes = []
        for r in linhas:
            lotes.append({
                "lote": str(r[0] or ""),
                "nunota_origem": r[1],
                "data": r[2].strftime('%d/%m/%Y') if r[2] else "",
                "parceiro": str(r[3] or ""),
                "produto": str(r[4] or ""),
                "qtd_in_natura": float(r[5] or 0),
                "status": str(r[6] or "VERMELHO").upper(),
                "qtd_cx": float(r[8] or 0),     # 👈 NOVO
                "peso_unit": float(r[9] or 0)   # 👈 NOVO
            })
        return JsonResponse({"ok": True, "lotes": lotes})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["GET"])
def api_detalhes_lote_classificacao(request):
    """API enxuta. Deixa todo o trabalho pesado para o oracle_conn."""
    lote = request.GET.get('lote')
    nunota_raw = request.GET.get('nunota_origem')

    if not lote:
        return JsonResponse({"ok": False, "error": "Parâmetro Lote inválido"}, status=400)

    try:
        # ⭐ A BLINDAGEM ESTÁ AQUI:
        # Tenta converter o que o JS mandou para número. 
        try:
            nunota_origem = int(nunota_raw)
        except (ValueError, TypeError):
            # Se o JS mandou "true", "undefined" ou vazio, o Python busca no Oracle
            with obter_conexao_oracle() as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(NUNOTA) FROM TGFITE WHERE CODAGREGACAO = :l AND GERAPRODUCAO = 'S'", {'l': lote})
                res = cur.fetchone()
                if not res or not res[0]:
                    return JsonResponse({"ok": False, "error": "Origem do lote não encontrada"}, status=404)
                nunota_origem = int(res[0])
        
        # 🚨 AQUI NÃO TEM MAIS NENHUM IMPORT!
        # Chama a função pesada que já calcula tudo com o NUNOTA correto
        dados = obter_detalhes_lote_completo(nunota_origem, lote)

        return JsonResponse({
            "ok": True, 
            "resumo": dados["resumo"], 
            "itens": dados["itens"]
        })

    except Exception as e:
        logger.exception("Erro grave na busca de detalhes do lote")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["GET"])
def api_consultar_lote(request: HttpRequest) -> JsonResponse:
    """
    Endpoint para o Clique Duplo (Modais).
    Busca dados detalhados da origem (TOP 11) e da classificação (TOP 26).
    """
    lote = request.GET.get('lote')
    nunota_origem_req = request.GET.get('nunota_origem')

    if not lote or not ORACLE_DISPONIVEL:
        return JsonResponse({"ok": False, "error": "Lote não informado ou conexão Oracle inativa"}, status=400)

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Recupera o NUNOTA de origem caso o JS não tenha enviado no clique duplo
            if not nunota_origem_req or nunota_origem_req in ("undefined", "null"):
                cur.execute("SELECT MAX(NUNOTA) FROM TGFITE WHERE CODAGREGACAO = :l AND GERAPRODUCAO = 'S'", l=lote)
                res = cur.fetchone()
                if not res or not res[0]:
                    return JsonResponse({"ok": False, "error": "Origem do lote não encontrada no Sankhya"}, status=404)
                nunota_origem = int(res[0])
            else:
                nunota_origem = int(nunota_origem_req)

            # 2. Busca dados de massa e balanço (Reaproveitando sua regra de negócio homologada)
            dados_massa = obter_detalhes_lote_completo(nunota_origem, lote)

            # 3. Busca metadados extras para o Cabeçalho do Modal (Parceiro, Data, Produto)
            cur.execute("""
                SELECT p.NOMEPARC, c.DTNEG, pr.DESCRPROD, c.CODPARC
                FROM TGFCAB c
                JOIN TGFPAR p ON c.CODPARC = p.CODPARC
                JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                JOIN TGFPRO pr ON i.CODPROD = pr.CODPROD
                WHERE c.NUNOTA = :n AND i.CODAGREGACAO = :l AND ROWNUM = 1
            """, n=nunota_origem, l=lote)
            row_extra = cur.fetchone()
            
            nome_parc = row_extra[0] if row_extra else "—"
            dt_neg = row_extra[1].strftime('%Y-%m-%d') if row_extra and row_extra[1] else ""
            descr_prod = row_extra[2] if row_extra else "—"
            cod_parc = row_extra[3] if row_extra else ""

            # 4. Busca nota TOP 26 vinculada (se houver) para carregar o histórico de classificação
            cur.execute("""
                SELECT c.NUNOTA, c.PENDENTE
                FROM TGFCAB c
                JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                WHERE i.CODAGREGACAO = :l AND c.CODTIPOPER = 26 AND c.STATUSNOTA <> 'E'
                AND ROWNUM = 1
            """, l=lote)
            row_26 = cur.fetchone()
            nunota_26 = row_26[0] if row_26 else None
            status_pendente = row_26[1] if row_26 else 'S'

            # 👇 NOVO: CHECAGEM DO MÓDULO COMERCIAL 👇
            cur.execute("""
                SELECT COUNT(1) FROM TGFCAB c 
                JOIN TGFITE i ON c.NUNOTA = i.NUNOTA 
                WHERE c.CODTIPOPER IN (13, 35, 37) AND i.CODAGREGACAO = :l AND c.STATUSNOTA <> 'E'
            """, l=lote)
            bloqueado_comercial = cur.fetchone()[0] > 0

            # Resposta estruturada para os métodos do seu classificacao.js
            return JsonResponse({
                "ok": True,
                "bloqueado_comercial": bloqueado_comercial, # 👈 MANDANDO PARA O JS
                "resumo": dados_massa.get("resumo", {}),
                "nunota_class": nunota_26,
                "pendente_class": status_pendente, 
                "agregados": {
                    "lote": lote,
                    "descarte": dados_massa["resumo"]["descarte"]
                },
                "entradas": [{
                    "nunota": nunota_origem,
                    "parceiro": nome_parc,
                    "descr": descr_prod,
                    "dtneg": dt_neg,
                    "qtd": dados_massa["resumo"]["in_natura"],
                    "qtdconferida": dados_massa["resumo"]["cx_in_natura"],
                    "codparc": cod_parc
                }],
                "classificacoes": [
                    {
                        "sequencia": it["seq"],
                        "nunota": nunota_26,
                        "cod": it["codprod"],
                        "codprod": it["codprod"], # 👈 NOVO: Mantém o nome original pro JS
                        "descr": it["produto"],
                        "qtd": it["total_kg"],
                        "peso": it["peso"],
                        "total": it["total_kg"],
                        "selecionado": it["selecionado"],
                        "caracteristicas": it.get("caracteristicas", "") # 👈 NOVO: Passando a tag pro JS
                    } for it in dados_massa["itens"]
                ]
            })
    except Exception as e:
        logger.exception(f"Erro ao consultar lote {lote}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["GET"])
def api_pesquisar_produtos_modal(request: HttpRequest) -> JsonResponse:
    """Pesquisa produtos filtrando obrigatoriamente pelo fabricante do In Natura."""
    query = request.GET.get("q", "").strip().upper()
    fabricante_filtro = request.GET.get("fabricante", "").strip()
    lim = int(request.GET.get("limit", 15))

    if not query:
        return JsonResponse({"results": []})

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()

        # SQL que busca produto por nome/código e TRAVA no fabricante
        sql = """
            SELECT CODPROD, DESCRPROD, FABRICANTE
            FROM TGFPRO
            WHERE (
                TRANSLATE(UPPER(DESCRPROD), 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ', 'AAAAAEEEEIIIIOOOOOUUUUC') 
                LIKE TRANSLATE(:p, 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ', 'AAAAAEEEEIIIIOOOOOUUUUC') 
                OR TO_CHAR(CODPROD) LIKE :p
            )
              AND NVL(ATIVO, 'S') = 'S'
              AND NVL(SELECIONADO, 0) > 0
        """
        binds = {'p': f"%{query}%"}

        if fabricante_filtro:
            sql += " AND UPPER(TRIM(FABRICANTE)) LIKE UPPER(TRIM(:fab))"
            binds['fab'] = f"%{fabricante_filtro}%"

        sql += " ORDER BY DESCRPROD"
        
        # Limite de linhas para performance
        sql_limit = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :lim"
        binds['lim'] = lim

        cur.execute(sql_limit, binds)
        linhas = cur.fetchall()

    # Retorno formatado para o Autocomplete do JS
    results = [
        {"cod": f[0], "descr": f[1], "fabricante": f[2]} 
        for f in linhas
    ]
    
    return JsonResponse({"results": results})

@require_http_methods(["POST"])
def api_update_descarte_lote(request):
    try:
        dados = json.loads(request.body)
        lote = dados.get('lote')
        operacao = dados.get('operacao')
        # Limpa o valor vindo do JS (aceita 1.5 ou "1,5")
        valor_bruto = str(dados.get('valor', '0')).replace(',', '.')
        valor_input = float(valor_bruto)

        if not lote:
            return JsonResponse({"ok": False, "error": "Lote não enviado"}, status=400)

        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Busca o NUNOTA e o descarte atual direto no Oracle
            cur.execute("""
                SELECT NUNOTA, NVL(AD_QTDAVARIA, 0) 
                FROM TGFITE 
                WHERE CODAGREGACAO = :l AND GERAPRODUCAO = 'S'
            """, {'l': lote})
            res = cur.fetchone()
            
            if not res:
                return JsonResponse({"ok": False, "error": f"Lote {lote} não encontrado no Sankhya"}, status=404)
            
            nunota_origem = res[0]
            descarte_atual = float(res[1])

            # 2. Calcula o novo valor
            if operacao in ('soma', '+'):
                novo_total = descarte_atual + valor_input
            elif operacao in ('subtrai', '-'):
                novo_total = max(0, descarte_atual - valor_input)
            else:
                novo_total = valor_input # Substituição se não vier operação

            # 3. Salva usando a sua função do oracle_conn.py
            # Passamos o nunota_origem que acabamos de descobrir
            atualizar_descarte_origem(nunota_origem, lote, novo_total)

        # 4. Retorno EXATO que o seu JS espera
        return JsonResponse({
            "ok": True, 
            "novo_total_lote": float(novo_total)
        })

    except Exception as e:
        logger.exception("Erro em api_update_descarte_lote")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["POST"])
def api_finaliza_classificacao_toggle(request):
    try:
        dados = json.loads(request.body)
        
        # O JS envia nunota_origem, nunota_class e pendente ('N' ou 'S')
        nunota_class = dados.get('nunota_class')
        status_pendente = dados.get('pendente') 

        if not nunota_class or not status_pendente:
            return JsonResponse({"ok": False, "error": "NUNOTA da TOP 26 ou Status ausentes."}, status=400)

        # Conecta no Oracle e faz o UPDATE direto na nota
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 🔍 DEBUG: lista lotes que esta TGFCAB agrupa (para o front mostrar no console)
            cur.execute("""
                SELECT DISTINCT i.CODAGREGACAO
                FROM TGFITE i
                WHERE i.NUNOTA = :n
                  AND i.CODAGREGACAO IS NOT NULL
                ORDER BY i.CODAGREGACAO
            """, {'n': nunota_class})
            lotes_afetados = [r[0] for r in cur.fetchall()]

            cur.execute("""
                UPDATE TGFCAB
                SET PENDENTE = :status
                WHERE NUNOTA = :nota
            """, {'status': status_pendente, 'nota': nunota_class})

            # Confirma a gravação no banco
            conn.commit()

        return JsonResponse({
            "ok": True,
            "debug": {
                "nunota_class": nunota_class,
                "pendente": status_pendente,
                "qtd_lotes_no_cab": len(lotes_afetados),
                "lotes_afetados": lotes_afetados,
            },
        })

    except Exception as e:
        logger.exception("Erro em api_finaliza_classificacao_toggle")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ==============================================================================
# 💰 MÓDULO COMERCIAL (VENDAS E FATURAMENTO)
# Interface de negociação e consumo de estoque classificado
# ==============================================================================

@exige_grupo('comercial')
@ensure_csrf_cookie
def view_comercial_painel(request: HttpRequest) -> HttpResponse:
    """Renderiza a interface principal do Painel Comercial."""
    
    contexto = {
        "write_enabled": verificar_permissao_escrita(),
    }
    
    return render(request, "sankhya_integration/comercial.html", contexto)

@require_http_methods(["GET"])
def api_listar_vales_comercial(request: HttpRequest) -> JsonResponse:
    """API para o Frontend listar os vales e itens na barra lateral do Módulo Comercial."""
    
    filtros = {
        "start": request.GET.get('start'),
        "end": request.GET.get('end'),
        "days": request.GET.get('days'),
        "codparc": request.GET.get('codparc'),
        "nunota": request.GET.get('nunota'),
        "fabricante": request.GET.get('fabricante'),
        "faturado": request.GET.get('faturado'),          # 'S', 'N', 'T'
        "sem_preco": request.GET.get('sem_preco'),        # '1', '0'
        "classificacao": request.GET.get('classificacao'),# 'S', 'N'
        "limit": request.GET.get('limit', 150),
        "offset": request.GET.get('offset', 0)
    }
    
    try:
        linhas = consultar_vales_comercial(filtros)
        return JsonResponse({"ok": True, "rows": linhas})
    except Exception as e:
        logger.exception("Erro na API listar_vales_comercial")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["POST"])
def api_atualizar_preco_comercial(request: HttpRequest) -> JsonResponse:
    """Recebe o Preço Inicial digitado no Card Entrada e salva no banco.
       Se o produto for In Natura, faz o Auto-Faturamento (Fast-Track)."""
    try:
        dados = json.loads(request.body)
        nunota = int(dados.get('nunota'))
        sequencia = int(dados.get('sequencia'))
        preco_inicial = float(dados.get('preco_inicial', 0))
        qtd_conferida = float(dados.get('qtdconferida', 0))
        
        # 🚀 FAST-TRACK: Captura a flag e o peso In Natura
        geraproducao = str(dados.get('geraproducao', 'S')).strip().upper()
        peso_in_natura = float(dados.get('peso', 0))
        
        plano = atualizar_preco_inicial_entrada(
            nunota, sequencia, preco_inicial, qtd_conferida, 
            geraproducao, peso_in_natura
        )
        
        if plano.get('ok'):
            # Recalcula a TOP 11
            recalculo = recalcular_totais_nota_banco(nunota)
            if recalculo.get('ok'):
                plano.update(recalculo)
            return JsonResponse(plano, status=200)
        else:
            return JsonResponse(plano, status=400)
            
    except Exception as e:
        logger.exception("Erro em api_atualizar_preco_comercial")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["POST"])
def api_atualizar_peso_comercial(request: HttpRequest) -> JsonResponse:
    """Recebe o Peso Classificado digitado no Card Entrada e salva no banco."""
    try:
        dados = json.loads(request.body)
        nunota = int(dados.get('nunota'))
        sequencia = int(dados.get('sequencia'))
        peso_classificado = float(dados.get('peso_classificado', 0))
        
        plano = atualizar_peso_comercial_entrada(nunota, sequencia, peso_classificado)
        
        if plano.get('ok'):
            return JsonResponse(plano, status=200)
        else:
            return JsonResponse(plano, status=400)
            
    except Exception as e:
        logger.exception("Erro em api_atualizar_peso_comercial")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["POST"])
def api_salvar_vale_comercial(request: HttpRequest) -> JsonResponse:
    """Recebe o payload da tela de Distribuição e orquestra a criação do Vale 13."""
    try:
        payload = json.loads(request.body)
        
        # Importa a função nova que você acabou de colar no oracle_conn.py
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco
        
        resultado = salvar_vale_compra_banco(payload)
        status_code = 200 if resultado.get('ok') else 400
        
        return JsonResponse(resultado, status=status_code)
        
    except Exception as e:
        logger.exception("Erro em api_salvar_vale_comercial")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["POST"])
def api_zerar_negociacao(request: HttpRequest) -> JsonResponse:
    """Endpoint para desfazer o faturamento de um lote na Distribuição."""
    try:
        payload = json.loads(request.body)
        nunota = payload.get('nunota_origem')
        lote = payload.get('lote')

        if not nunota or not lote:
            return JsonResponse({"ok": False, "error": "NUNOTA e Lote são obrigatórios."}, status=400)

        from sankhya_integration.services.oracle_conn import zerar_negociacao_banco
        resultado = zerar_negociacao_banco(nunota, lote)
        
        status_code = 200 if resultado.get('ok') else 400
        return JsonResponse(resultado, status=status_code)
        
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@require_http_methods(["GET"])
def api_detalhes_vale_comercial(request: HttpRequest) -> JsonResponse:
    """Endpoint para retornar os KGs e Custos faturados na TOP 13, incluindo o INSS."""
    nunota = request.GET.get('nunota_13')
    lote = request.GET.get('lote')
    if not nunota or not lote:
        return JsonResponse({"ok": False, "error": "Faltam parâmetros"})
    
    from sankhya_integration.services.oracle_conn import consultar_detalhes_vale_banco, obter_conexao_oracle
    
    # 1. Busca os detalhes dos itens já existentes
    dados = consultar_detalhes_vale_banco(int(nunota), lote)
    
    # 2. Busca o valor de VLROUTROS (INSS) e se existe Financeiro
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("SELECT NVL(VLROUTROS, 0) FROM TGFCAB WHERE NUNOTA = :n", n=int(nunota))
            row = cur.fetchone()
            dados['vlroutros'] = float(row[0]) if row else 0.0
            
            # NOVO: Descobre se já tem financeiro gerado
            cur.execute("SELECT MAX(NUFIN) FROM TGFFIN WHERE NUNOTA = :n", n=int(nunota))
            nufin_row = cur.fetchone()
            dados['nufin'] = nufin_row[0] if nufin_row and nufin_row[0] else 0
    except Exception as e:
        logger.warning(f"Erro ao buscar dados adicionais para nota {nunota}: {e}")
        dados['vlroutros'] = 0.0
        dados['nufin'] = 0

    return JsonResponse(dados)

@require_http_methods(["POST"])
def api_salvar_simulacao(request: HttpRequest) -> JsonResponse:
    """Endpoint para salvar ou limpar a simulação no banco."""
    try:
        payload = _get_json_payload(request)
        nunota = payload.get('nunota')
        lote = payload.get('lote')
        sim_data = payload.get('sim_data', {})
        
        if not nunota or not lote:
            return JsonResponse({"ok": False, "error": "Parâmetros de nota ou lote inválidos"})
        
        from sankhya_integration.services.oracle_conn import atualizar_simulacao_item_banco
        res = atualizar_simulacao_item_banco(nunota, lote, sim_data)
        
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})

def api_desmembrar_pedido_classificacao(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            nunota_origem = dados.get('nunota_origem')
            lote = dados.get('lote')
            
            if not nunota_origem or not lote:
                return JsonResponse({'ok': False, 'error': 'Pedido original ou Lote não informados.'})
                
            # Chama a super função que criamos no oracle_conn
            resultado = desmembrar_pedido_classificacao(int(nunota_origem), lote)
            return JsonResponse(resultado)
            
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)})
            
    return JsonResponse({'ok': False, 'error': 'Método inválido.'})

def api_listar_pedidos_unificacao(request):
    """ Solução Definitiva: Busca pedidos TOP 11 do parceiro filtrando via Lote -> Vale -> Financeiro """
    nunota_atual = request.GET.get('nunota_atual')
    
    if not nunota_atual:
        return JsonResponse({'ok': False, 'error': 'Nota atual não informada.'})
        
    try:
        from sankhya_integration.services.oracle_conn import obter_conexao_oracle
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Pega apenas o parceiro da nota atual
            cur.execute("SELECT CODPARC FROM TGFCAB WHERE NUNOTA = :1", [nunota_atual])
            row_origem = cur.fetchone()
            if not row_origem:
                return JsonResponse({'ok': False, 'error': 'Pedido atual não encontrado no banco.'})
                
            codparc = row_origem[0]

            # 2. A MÁGICA DE ALTA PERFORMANCE E PRECISÃO:
            # Trava na TOP 11 e usa o Lote para descobrir se a nota já foi faturada no Comercial.
            cur.execute("""
                SELECT NUNOTA, DATA_NEG, VLR 
                FROM (
                    SELECT 
                        c.NUNOTA, 
                        TO_CHAR(c.DTNEG, 'DD/MM/YYYY') as DATA_NEG, 
                        (SELECT NVL(SUM(VLRTOT), 0) FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA) as VLR
                    FROM TGFCAB c
                    WHERE c.CODTIPOPER = 11 
                      AND c.CODPARC = :parc 
                      AND c.NUNOTA <> :atual
                      AND NVL(c.STATUSNOTA, 'A') <> 'E'
                      /* 🛑 A TRAVA DEFINITIVA: Exclui se QUALQUER lote deste pedido estiver em um Vale com Financeiro */
                      AND NOT EXISTS (
                          SELECT 1 
                          FROM TGFITE i_orig
                          JOIN TGFITE i_vale ON i_orig.CODAGREGACAO = i_vale.CODAGREGACAO
                          JOIN TGFCAB c_vale ON i_vale.NUNOTA = c_vale.NUNOTA
                          JOIN TGFFIN fin ON c_vale.NUNOTA = fin.NUNOTA
                          WHERE i_orig.NUNOTA = c.NUNOTA
                            AND i_orig.CODAGREGACAO IS NOT NULL
                            AND c_vale.CODTIPOPER IN (13, 35, 37)
                      )
                    ORDER BY c.DTNEG DESC
                )
                WHERE ROWNUM <= 20
            """, parc=codparc, atual=nunota_atual)
            
            pedidos = []
            for row in cur.fetchall():
                pedidos.append({
                    'nunota': row[0],
                    'data': row[1],
                    'vlrnota': float(row[2])
                })
            return JsonResponse({'ok': True, 'pedidos': pedidos})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f"Erro SQL: {str(e)}"})

def api_unificar_pedido_classificacao(request):
    """ Processa a unificação de um lote para um pedido existente """
    if request.method == 'POST':
        import json
        try:
            dados = json.loads(request.body)
            nunota_origem = dados.get('nunota_origem')
            lote = dados.get('lote')
            nunota_destino = dados.get('nunota_destino')
            
            if not all([nunota_origem, lote, nunota_destino]):
                return JsonResponse({'ok': False, 'error': 'Faltam parâmetros para unificar.'})

            # 🚀 FIX: Caminho de importação corrigido aqui também!
            from sankhya_integration.services.oracle_conn import unificar_pedido_classificacao
            
            resultado = unificar_pedido_classificacao(int(nunota_origem), lote, int(nunota_destino))
            return JsonResponse(resultado)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)})
    return JsonResponse({'ok': False, 'error': 'Método inválido.'})


# ==============================================================================
# ROTA 1: A Lista de Últimas Vendas (Rápida - 0.3s)
# ==============================================================================
@require_http_methods(["GET"])
def api_lista_ultimas_vendas(request: HttpRequest) -> JsonResponse:
    """Endpoint para retornar a lista de últimas vendas (agrupada por matriz)."""
    lote = request.GET.get('lote')
    if not lote:
        return JsonResponse({"ok": False, "error": "Lote não informado"}, status=400)
    
    # CORREÇÃO: Importando o nome correto que você alterou!
    from sankhya_integration.services.oracle_conn import consultar_lista_ultimas_vendas
    dados = consultar_lista_ultimas_vendas(lote)
    
    return JsonResponse(dados)


# ==============================================================================
# ROTA 2: O Ticket Médio em Background (Para não travar a tela)
# ==============================================================================
@require_http_methods(["GET"])
def api_ticket_calculo(request: HttpRequest) -> JsonResponse:
    """Endpoint exclusivo para calcular o Ticket Médio real das vendas do lote."""
    lote = request.GET.get('lote')
    if not lote:
        return JsonResponse({"ok": False, "error": "Lote não informado"}, status=400)

    # Importa a nova função otimizada que criamos no oracle_conn.py
    from sankhya_integration.services.oracle_conn import consultar_calculo_ticket_medio
    dados = consultar_calculo_ticket_medio(lote)
    
    return JsonResponse(dados)


# ==============================================================================
# Faturamento do vale
# ==============================================================================
@require_http_methods(["POST"])
def api_gerar_financeiro_banco(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body)
        nunota_13 = int(payload.get('nunota_13'))
        inss = bool(payload.get('descontar_inss', False))
        
        historico = payload.get('historico', '')
        vlrinss = float(payload.get('vlrinss', 0.0))
        
        # 🚀 Captura os valores exatos da tela
        vlr_forcar_liquido = payload.get('vlr_forcar_liquido')
        vlr_forcar_bruto = payload.get('vlr_forcar_bruto')
        if vlr_forcar_liquido is not None: vlr_forcar_liquido = float(vlr_forcar_liquido)
        if vlr_forcar_bruto is not None: vlr_forcar_bruto = float(vlr_forcar_bruto)
        
        logger.debug("Faturando NUNOTA %s | Líquido: %s | Bruto: %s", nunota_13, vlr_forcar_liquido, vlr_forcar_bruto)
        
        from sankhya_integration.services.oracle_conn import gerar_financeiro_banco
        res = gerar_financeiro_banco(nunota_13, inss, historico, vlrinss, vlr_forcar_liquido, vlr_forcar_bruto)
        
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@require_http_methods(["POST"])
def api_atualizar_preco_modalFaturamento(request):
    try:
        data = json.loads(request.body)
        from sankhya_integration.services.oracle_conn import upsert_preco_in_natura_modalFaturamento
        
        res = upsert_preco_in_natura_modalFaturamento(
            nunota_origem=int(data['nunota_origem']),
            nunota_13=int(data.get('nunota_13', 0)), # 🚀 Adicionamos isso
            codprod=int(data['codprod']),
            novo_preco=float(data['preco'])
        )
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@require_http_methods(["POST"])
def api_atualizar_desconto_inss_vale(request):
    try:
        data = json.loads(request.body)
        nunota_13 = int(data.get('nunota_13', 0))
        valor = float(data.get('valor', 0))
        
        from sankhya_integration.services.oracle_conn import atualizar_desconto_inss_vale
        res = atualizar_desconto_inss_vale(nunota_13, valor)
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@require_http_methods(["POST"])
def api_desfaturar_vale(request):
    try:
        payload = json.loads(request.body)
        nunota_13 = int(payload.get('nunota_13'))
        from sankhya_integration.services.oracle_conn import desfaturar_comercial_banco
        return JsonResponse(desfaturar_comercial_banco(nunota_13))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

# ==============================================================================
# 💰 MÓDULO VENDA (PEDIDOS E VALES)
# Interface de negociação e consumo de estoque classificado atraves de vendas
# ==============================================================================
@exige_grupo('venda')
@ensure_csrf_cookie
def view_portal_vendas(request: HttpRequest) -> HttpResponse:
    """Renderiza a página principal do Módulo de Vendas (TOP 34/35/37)."""
    
    # Reuso de lógica de filtros que você já utiliza na entrada
    parametros = {
        "date_start": request.GET.get("start"),
        "date_end": request.GET.get("end"),
        "nunota_ini": request.GET.get("nunota_ini", "").strip(),
        "codparc": _converter_para_inteiro(request.GET.get("codparc")),
        "top": request.GET.get("top", "T"), # T para Todas
    }

    contexto = {
        "nome_usuario": request.session.get('nomeusu', 'Usuário'),
        "params": parametros,
        "write_enabled": verificar_permissao_escrita(),
    }

    return render(request, "sankhya_integration/venda.html", contexto)

@require_http_methods(["GET"])
def api_listar_vendas(request: HttpRequest) -> JsonResponse:
    filtros = {
        "date_start": request.GET.get('start'),
        "date_end": request.GET.get('end'),
        "codemp": request.GET.get('codemp'),
        "nunota_ini": request.GET.get('nunota_ini'),
        "numnota": request.GET.get('numnota'),
        "top": request.GET.get('top'),
        "codparc": request.GET.get('codparc'),
        "codprod": request.GET.get('codprod'),
        "lote": request.GET.get('lote'),
        "limite": int(request.GET.get('limit', 50)),
        "offset": int(request.GET.get('offset', 0))
    }
    
    try:
        linhas = listar_vendas_paginado(**filtros)
        vendas = []
        for r in linhas:
            vendas.append({
                "nunota": r[0],
                "top": r[1],
                "data": r[2].strftime('%d/%m/%Y') if r[2] else "",
                "parceiro": r[3] or "", # NOMEPARC
                "total": float(r[4] or 0),
                "status_lote": r[5],
                "numnota": r[6] or "", # Nº Nota
                "emp": r[7]            # CODEMP
            })
        return JsonResponse({"ok": True, "vendas": vendas})
    except Exception as e:
        logger.exception("Erro em api_listar_vendas")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_criar_cabecalho_venda(request: HttpRequest) -> JsonResponse:
    """Cria um Pedido de Venda (TOP 34) na TGFCAB."""
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    codparc = _converter_para_inteiro(dados_json.get('codparc'))
    if not codparc:
        return JsonResponse({"ok": False, "error": "CODPARC obrigatório"}, status=400)

    dtneg_raw = dados_json.get('dtneg')
    if not dtneg_raw:
        return JsonResponse({"ok": False, "error": "DTNEG obrigatória"}, status=400)

    codtipvenda = _converter_para_inteiro(dados_json.get('codtipvenda'))
    if not codtipvenda:
        return JsonResponse({"ok": False, "error": "CODTIPVENDA obrigatório"}, status=400)

    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    payload = {
        'CODEMP':      _converter_para_inteiro(dados_json.get('codemp'), default=10),
        'CODPARC':     codparc,
        'CODTIPOPER':  34,
        'CODNAT':      10010100,
        'CODCENCUS':   10100,
        'CODTIPVENDA': codtipvenda,
        'DTNEG':       _data_br_para_iso(dtneg_raw),
        'OBSERVACAO':  dados_json.get('obs') or None,
    }

    try:
        with obter_conexao_oracle() as conn:
            try:
                plano = inserir_cabecalho_nota_banco(
                    payload, simulacao=False, conexao_existente=conn
                )
                if plano.get('executed'):
                    conn.commit()
                else:
                    conn.rollback()
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as e:
        logger.exception("Erro ao criar cabeçalho de venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not plano.get('executed'):
        logger.warning(
            "Falha ao criar cabeçalho de venda. Payload=%s | Resposta service=%s",
            payload, plano,
        )
        return JsonResponse(
            {"ok": False, "error": humanizar_erro_oracle(plano.get('error') or 'Falha ao criar pedido')},
            status=400,
        )

    return JsonResponse({"ok": True, "nunota": plano.get('nunota')}, status=200)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_salvar_item_venda(request: HttpRequest) -> JsonResponse:
    """Insere um item (TGFITE) em um Pedido de Venda e recalcula totais da nota."""
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota  = _converter_para_inteiro(dados_json.get('nunota'))
    codprod = _converter_para_inteiro(dados_json.get('codprod'))
    qtdneg  = _converter_para_float(dados_json.get('qtdneg'))
    if not nunota or not codprod or qtdneg is None:
        return JsonResponse(
            {"ok": False, "error": "NUNOTA, CODPROD e QTDNEG são obrigatórios"},
            status=400,
        )

    codvol = str(dados_json.get('codvol') or 'CX').strip().upper()
    payload = {
        'NUNOTA':        nunota,
        'CODPROD':       codprod,
        'QTDNEG':        qtdneg,
        'VLRUNIT':       _converter_para_float(dados_json.get('vlrunit'), default=0.0),
        'CODVOL':        codvol,
        'CODVOLPARC':    codvol,
        'CODAGREGACAO':  dados_json.get('codagregacao') or None,
    }

    codusu = request.session.get('codusu')
    recalculo = {}
    try:
        with obter_conexao_oracle() as conn:
            try:
                plano = inserir_item_nota_banco(
                    payload, simulacao=False, conexao_existente=conn,
                    codusu_logado=codusu, gerar_lote_auto=False,
                )
                if not plano.get('executed'):
                    conn.rollback()
                    return JsonResponse(
                        {"ok": False, "error": humanizar_erro_oracle(plano.get('error') or 'Falha ao salvar item')},
                        status=400,
                    )
                recalculo = recalcular_totais_nota_banco(nunota, conexao_existente=conn) or {}
                conn.commit()
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as e:
        logger.exception("Erro ao salvar item de venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    resposta = {"ok": True, "sequencia": plano.get('sequencia')}
    if 'vlrnota' in recalculo: resposta['vlrnota'] = recalculo['vlrnota']
    if 'qtdvol'  in recalculo: resposta['qtdvol']  = recalculo['qtdvol']
    return JsonResponse(resposta, status=200)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_excluir_pedido_venda(request: HttpRequest) -> JsonResponse:
    """Exclui Pedido de Venda (TOP 34). Usado para remover cabeçalho órfão
    criado sem itens. Bloqueia se a nota não for TOP 34 (evita deletar NFe)."""
    dados_json = _get_json_payload(request)
    nunota = _converter_para_inteiro(dados_json.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
            row = cur.fetchone()
    except Exception as e:
        logger.exception("Erro ao consultar TOP do pedido para exclusão")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not row:
        return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)
    if int(row[0]) != 34:
        return JsonResponse(
            {"ok": False, "error": f"Operação permitida apenas para TOP 34 (esta é {int(row[0])})"},
            status=403,
        )

    resposta = excluir_nota_completa_banco(nunota, simulacao=False)
    if not resposta.get('ok') and resposta.get('errors'):
        resposta['error'] = humanizar_erro_oracle('; '.join(resposta['errors']))
    return JsonResponse(resposta, status=200 if resposta.get('ok') else 400)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_atualizar_cabecalho_venda(request: HttpRequest) -> JsonResponse:
    """Atualiza o cabeçalho de um Pedido de Venda existente (TOP 34)."""
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota = _converter_para_inteiro(dados_json.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)

    codparc = _converter_para_inteiro(dados_json.get('codparc'))
    if not codparc:
        return JsonResponse({"ok": False, "error": "CODPARC obrigatório"}, status=400)

    codtipvenda = _converter_para_inteiro(dados_json.get('codtipvenda'))
    if not codtipvenda:
        return JsonResponse({"ok": False, "error": "CODTIPVENDA obrigatório"}, status=400)

    dtneg_raw = dados_json.get('dtneg')
    if not dtneg_raw:
        return JsonResponse({"ok": False, "error": "DTNEG obrigatória"}, status=400)

    # Trava: só Pedido (TOP 34) pode ser editado por esta rota
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
            row = cur.fetchone()
    except Exception as e:
        logger.exception("Erro ao consultar TOP para edição")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not row:
        return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)
    if int(row[0]) != 34:
        return JsonResponse(
            {"ok": False, "error": f"Edição permitida apenas para TOP 34 (esta é {int(row[0])})"},
            status=403,
        )

    payload = {
        'NUNOTA':      nunota,
        'CODEMP':      _converter_para_inteiro(dados_json.get('codemp'), default=10),
        'CODPARC':     codparc,
        'CODTIPVENDA': codtipvenda,
        'DTNEG':       _data_br_para_iso(dtneg_raw),
        'OBSERVACAO':  dados_json.get('obs') or None,
    }

    try:
        plano = atualizar_cabecalho_venda_banco(payload, simulacao=False)
    except Exception as e:
        logger.exception("Erro ao atualizar cabeçalho de venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not plano.get('executed'):
        logger.warning(
            "Falha ao atualizar cabeçalho de venda. Payload=%s | Resposta service=%s",
            payload, plano,
        )
        return JsonResponse(
            {"ok": False, "error": humanizar_erro_oracle(plano.get('error') or 'Falha ao atualizar pedido')},
            status=400,
        )

    return JsonResponse({"ok": True, "nunota": nunota}, status=200)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_obter_cabecalho_pedido(request: HttpRequest) -> JsonResponse:
    """Devolve os dados do cabeçalho de um pedido para o modal de edição."""
    nunota = _converter_para_inteiro(request.GET.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)

    try:
        linha = consultar_cabecalho_venda_oracle(nunota)
    except Exception as e:
        logger.exception("Erro ao consultar cabeçalho do pedido")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not linha:
        return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)

    codemp, nome_emp, codparc, nome_parc, codtpv, descr_tpv, dtneg, obs = linha
    return JsonResponse({
        "ok":             True,
        "codemp":         int(codemp) if codemp is not None else None,
        "nome_emp":       nome_emp or "",
        "codparc":        int(codparc) if codparc is not None else None,
        "nome_parc":      nome_parc or "",
        "codtipvenda":    int(codtpv) if codtpv is not None else None,
        "descr_tipvenda": descr_tpv or "",
        "dtneg":          dtneg.strftime('%Y-%m-%d') if dtneg else "",
        "obs":            obs or "",
    })


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_atualizar_item_venda(request: HttpRequest) -> JsonResponse:
    """Atualiza um item de pedido TOP 34 (qtd, preço, lote, volume).

    Reutiliza ``atualizar_item_nota_banco``. Trava: pedido tem que ser TOP 34
    e não estar faturado (STATUSNOTA != 'L'). Recalcula totais ao final na
    mesma transação.
    """
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota    = _converter_para_inteiro(dados_json.get('nunota'))
    sequencia = _converter_para_inteiro(dados_json.get('sequencia'))
    if not nunota or not sequencia:
        return JsonResponse(
            {"ok": False, "error": "NUNOTA e SEQUENCIA são obrigatórios"},
            status=400,
        )

    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    # Trava — só pedido TOP 34 não-faturado
    try:
        with obter_conexao_oracle() as conn_check:
            cur = conn_check.cursor()
            cur.execute("""
                SELECT CODTIPOPER, STATUSNOTA FROM TGFCAB WHERE NUNOTA = :n
            """, n=nunota)
            row = cur.fetchone()
    except Exception as e:
        logger.exception("Erro ao validar TOP/STATUSNOTA do pedido para edição de item")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not row:
        return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)
    if int(row[0]) != 34:
        return JsonResponse(
            {"ok": False, "error": f"Edição permitida apenas para TOP 34 (esta é {int(row[0])})"},
            status=403,
        )
    if row[1] == 'L':
        return JsonResponse(
            {"ok": False, "error": "Pedido já foi faturado — não é mais editável"},
            status=403,
        )

    # Monta payload aceitando só os campos editáveis pela tela
    payload = {'NUNOTA': nunota, 'SEQUENCIA': sequencia}
    for chave_in, chave_out, conv in (
        ('codprod',     'CODPROD',     _converter_para_inteiro),
        ('qtdneg',      'QTDNEG',      _converter_para_float),
        ('vlrunit',     'VLRUNIT',     _converter_para_float),
    ):
        v = conv(dados_json.get(chave_in))
        if v is not None:
            payload[chave_out] = v
    for chave_in, chave_out in (
        ('codvol',       'CODVOL'),
        ('codvolparc',   'CODVOLPARC'),
        ('codagregacao', 'CODAGREGACAO'),
        ('observacao',   'OBSERVACAO'),
    ):
        v = dados_json.get(chave_in)
        if v not in (None, ''):
            payload[chave_out] = v
    # CODVOLPARC sempre acompanha CODVOL quando informado
    if 'CODVOL' in payload and 'CODVOLPARC' not in payload:
        payload['CODVOLPARC'] = payload['CODVOL']

    try:
        with obter_conexao_oracle() as conn:
            try:
                plano = atualizar_item_nota_banco(
                    payload, simulacao=False, conexao_existente=conn,
                )
                if not plano.get('executed'):
                    conn.rollback()
                    return JsonResponse(
                        {"ok": False, "error": humanizar_erro_oracle(
                            (plano.get('errors') and '; '.join(plano['errors']))
                            or (plano.get('db_error') or {}).get('message')
                            or 'Falha ao atualizar item'
                        )},
                        status=400,
                    )
                recalculo = recalcular_totais_nota_banco(nunota, conexao_existente=conn) or {}
                conn.commit()
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as e:
        logger.exception("Erro ao atualizar item de venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    resposta = {"ok": True, "sequencia": sequencia}
    if 'vlrnota' in recalculo: resposta['vlrnota'] = recalculo['vlrnota']
    if 'qtdvol'  in recalculo: resposta['qtdvol']  = recalculo['qtdvol']
    return JsonResponse(resposta, status=200)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_remover_item_venda(request: HttpRequest) -> JsonResponse:
    """Remove um item de pedido TOP 34 e recalcula totais.

    Se for o último item do pedido, ``recalcular_totais_nota_banco`` deleta
    o cabeçalho automaticamente — comportamento já existente do helper.
    """
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota    = _converter_para_inteiro(dados_json.get('nunota'))
    sequencia = _converter_para_inteiro(dados_json.get('sequencia'))
    if not nunota or not sequencia:
        return JsonResponse(
            {"ok": False, "error": "NUNOTA e SEQUENCIA são obrigatórios"},
            status=400,
        )
    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    # Trava — só pedido TOP 34 não-faturado
    try:
        with obter_conexao_oracle() as conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT CODTIPOPER, STATUSNOTA FROM TGFCAB WHERE NUNOTA = :n FOR UPDATE
                """, n=nunota)
                row = cur.fetchone()
                if not row:
                    return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)
                if int(row[0]) != 34:
                    return JsonResponse(
                        {"ok": False, "error": f"Remoção permitida apenas para TOP 34 (esta é {int(row[0])})"},
                        status=403,
                    )
                if row[1] == 'L':
                    return JsonResponse(
                        {"ok": False, "error": "Pedido já foi faturado — não é mais editável"},
                        status=403,
                    )
                cur.execute("""
                    DELETE FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, n=nunota, s=sequencia)
                deletados = int(cur.rowcount or 0)
                if deletados == 0:
                    conn.rollback()
                    return JsonResponse(
                        {"ok": False, "error": f"Item SEQ={sequencia} não encontrado"},
                        status=404,
                    )
                recalculo = recalcular_totais_nota_banco(nunota, conexao_existente=conn) or {}
                conn.commit()
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as e:
        logger.exception("Erro ao remover item de venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    resposta = {"ok": True, "sequencia": sequencia,
                "cab_deleted": bool(recalculo.get('cab_deleted'))}
    if 'vlrnota' in recalculo: resposta['vlrnota'] = recalculo['vlrnota']
    if 'qtdvol'  in recalculo: resposta['qtdvol']  = recalculo['qtdvol']
    return JsonResponse(resposta, status=200)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_faturar_pedido_venda(request: HttpRequest) -> JsonResponse:
    """Fatura um pedido TOP 34 transformando-o em TOP 35 (NFe) ou TOP 37 (s/ NFe).

    Validações no service: pedido existe, é TOP 34, não-faturado, tem itens,
    todos os itens têm lote vinculado.
    """
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota   = _converter_para_inteiro(dados_json.get('nunota'))
    nova_top = _converter_para_inteiro(dados_json.get('top'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)
    if nova_top not in (35, 37):
        return JsonResponse(
            {"ok": False, "error": "TOP de faturamento inválido (use 35 para NFe ou 37 para sem NFe)"},
            status=400,
        )
    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    try:
        res = faturar_pedido_venda_banco(
            nunota=nunota, nova_top=nova_top,
            codusu_logado=request.session.get('codusu'),
        )
    except Exception as e:
        logger.exception("Erro em api_faturar_pedido_venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao faturar pedido')
        return JsonResponse(res, status=400)
    return JsonResponse(res, status=200)


# ==============================================================================
# 💰 MÓDULO DE RASTREABILIDADE
# Interface de consulta e rastreio de lotes, desde a origem até o destino final, incluindo histórico de classificações e vendas.
# ==============================================================================

@exige_grupo('rastreio')
@ensure_csrf_cookie
def api_rastreio_view(request):
    """Renderiza a página do Rastreio. ``ensure_csrf_cookie`` garante que o
    cookie csrftoken já vai no primeiro response — sem ele, o primeiro POST
    da página (atribuir/desvincular lote) falharia com 403 do middleware CSRF."""
    return render(request, 'sankhya_integration/rastreio.html')


def _paginacao_do_request(request: HttpRequest, default_limit: int = 50) -> tuple[int, int]:
    """Extrai limit/offset da querystring com defaults seguros."""
    try:
        lim = int(request.GET.get('limit') or default_limit)
    except (TypeError, ValueError):
        lim = default_limit
    try:
        off = int(request.GET.get('offset') or 0)
    except (TypeError, ValueError):
        off = 0
    lim = max(1, min(lim, 200))   # clamp 1..200
    off = max(0, off)
    return lim, off


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_lote_vinculos(request: HttpRequest) -> JsonResponse:
    """Lista todos os pedidos/vendas que estão consumindo um determinado lote."""
    codagregacao = (request.GET.get('codagregacao') or '').strip()
    if not codagregacao:
        return JsonResponse({"ok": False, "error": "codagregacao obrigatório"}, status=400)
    try:
        rows = consultar_vinculos_de_lote(codagregacao)
        for r in rows:
            if r.get('dtneg') and hasattr(r['dtneg'], 'strftime'):
                r['dtneg'] = r['dtneg'].strftime('%d/%m/%Y')
            if r.get('qtdneg') is not None:
                r['qtdneg'] = float(r['qtdneg'])
        return JsonResponse({"ok": True, "vinculos": rows})
    except Exception as e:
        logger.exception("Erro em api_rastreio_lote_vinculos")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_fabricantes(request: HttpRequest) -> JsonResponse:
    """Typeahead — lista FABRICANTEs distintos que têm lote elegível.

    Aceita ?q=texto&limit=N (default 10).
    """
    termo = request.GET.get('q') or ''
    try:
        limite = int(request.GET.get('limit') or 10)
    except (TypeError, ValueError):
        limite = 10
    limite = max(1, min(limite, 50))
    try:
        nomes = consultar_fabricantes_disponiveis(termo=termo, limite=limite)
        return JsonResponse({"ok": True, "fabricantes": nomes})
    except Exception as e:
        logger.exception("Erro em api_rastreio_fabricantes")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


def _parse_codprods(raw: str | None) -> list[int]:
    if not raw: return []
    return [int(x) for x in str(raw).split(',') if x.strip().isdigit()]


def _parse_bool_flag(raw, *, default: bool = False) -> bool:
    """Parse de query string com default explícito quando ausente.

    None ou '' devolve o default; caso contrário interpreta '1/true/on/yes' como True.
    """
    if raw is None or raw == '':
        return default
    return str(raw).strip().lower() in ('1', 'true', 'on', 'yes')


def _registrar_audit_rastreio(request, *, acao, nunota, sequencia,
                              codagregacao=None, qtd=None, extra=None):
    """Grava uma linha em RastreioAudit. Falhas no audit não derrubam a operação.

    Captura usuário da sessão (codusu/nomeusu). Se algo falhar (DB local
    indisponível, etc), só loga warning — a vinculação/desvinculação no
    Oracle já foi feita e não pode ser desfeita por causa de um audit.
    """
    try:
        from .models import RastreioAudit
        RastreioAudit.objects.create(
            acao=acao,
            nunota=int(nunota),
            sequencia=int(sequencia),
            codagregacao=str(codagregacao) if codagregacao else None,
            qtd=qtd,
            codusu=request.session.get('codusu'),
            nomeusu=(request.session.get('nomeusu')
                     or request.session.get('nome') or '')[:80],
            detalhe=extra or {},
        )
    except Exception:
        logger.warning("Falha ao gravar RastreioAudit (acao=%s nunota=%s seq=%s)",
                       acao, nunota, sequencia, exc_info=True)


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_lotes_disponiveis(request: HttpRequest) -> JsonResponse:
    """Lista lotes com saldo disponível (e in-natura pendente) para a tela de Rastreio."""
    filtros = {
        'q':            request.GET.get('q'),
        'codprod':      request.GET.get('codprod'),
        'codprods':     _parse_codprods(request.GET.get('codprods')),
        'codagregacao': request.GET.get('codagregacao'),
        # Busca combinada do input principal: lote OU produto (Mai/2026)
        'q_lote_prod':  request.GET.get('q_lote_prod'),
        'fabricante':   request.GET.get('fabricante'),
        'tipo':         request.GET.get('tipo'),
        'desde_dias':   request.GET.get('desde_dias'),
        'data_ini':     request.GET.get('data_ini'),
        'data_fim':     request.GET.get('data_fim'),
        'cliente_q':    request.GET.get('cliente_q'),
    }
    limite, offset = _paginacao_do_request(request)
    try:
        lotes = consultar_saldo_lote_disponivel(filtros, limite=limite, offset=offset)
        for l in lotes:
            if l.get('dtneg_origem') and hasattr(l['dtneg_origem'], 'strftime'):
                l['dtneg_origem'] = l['dtneg_origem'].strftime('%d/%m/%Y')
            for k in ('qtd_entrada', 'qtd_baixada_venda', 'qtd_baixada_avaria',
                      'qtd_reservada', 'qtd_disponivel', 'qtd_pendente',
                      'qtd_avaria_interna'):
                if l.get(k) is not None:
                    l[k] = float(l[k])
        return JsonResponse({
            "ok": True, "lotes": lotes,
            "limit": limite, "offset": offset, "tem_mais": len(lotes) >= limite,
        })
    except Exception as e:
        logger.exception("Erro em api_rastreio_lotes_disponiveis")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_pedidos_abertos(request: HttpRequest) -> JsonResponse:
    """Lista itens de pedidos TOP 34 em aberto, com lote já atribuído ou pendente.

    Paginação por cabeçalho: 'limit' pedidos por página; cada pedido vem com
    todos os seus itens. 'tem_mais' indica se há mais pedidos a buscar.
    """
    filtros = {
        'q':          request.GET.get('q'),
        'codprod':    request.GET.get('codprod'),
        'codprods':   _parse_codprods(request.GET.get('codprods')),
        'nunota':     request.GET.get('nunota'),
        'desde_dias': request.GET.get('desde_dias'),
        'data_ini':   request.GET.get('data_ini'),
        'data_fim':   request.GET.get('data_fim'),
        'fabricante': request.GET.get('fabricante'),
        # Toggle Pendente/Faturado (Mai/2026 — substitui incluir_finalizados):
        # cada flag controla um conjunto de TOPs. Pendente = TOP 34, Faturado
        # = TOP 35/37. Default no backend: pendentes=True, faturados=False.
        'mostrar_pendentes': _parse_bool_flag(request.GET.get('mostrar_pendentes'), default=True),
        'mostrar_faturados': _parse_bool_flag(request.GET.get('mostrar_faturados'), default=False),
    }
    limite, offset = _paginacao_do_request(request)
    try:
        itens = consultar_pedidos_abertos_para_atribuicao(filtros, limite=limite, offset=offset)
        for it in itens:
            if it.get('dtneg') and hasattr(it['dtneg'], 'strftime'):
                it['dtneg'] = it['dtneg'].strftime('%d/%m/%Y')
            if it.get('lote_dtneg') and hasattr(it['lote_dtneg'], 'strftime'):
                it['lote_dtneg'] = it['lote_dtneg'].strftime('%d/%m/%Y')
            if it.get('qtd_pedida') is not None:
                it['qtd_pedida'] = float(it['qtd_pedida'])
        # tem_mais: número de NUNOTAs distintos atinge o limit
        nunotas_distintos = len({it['nunota'] for it in itens})
        return JsonResponse({
            "ok": True, "itens": itens,
            "limit": limite, "offset": offset,
            "tem_mais": nunotas_distintos >= limite,
        })
    except Exception as e:
        logger.exception("Erro em api_rastreio_pedidos_abertos")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_desvincular_lote(request: HttpRequest) -> JsonResponse:
    """Remove o vínculo de lote (CODAGREGACAO) de um item de pedido TOP 34."""
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota    = _converter_para_inteiro(dados.get('nunota'))
    sequencia = _converter_para_inteiro(dados.get('sequencia'))

    if not nunota or not sequencia:
        return JsonResponse(
            {"ok": False, "error": "nunota e sequencia são obrigatórios"},
            status=400,
        )

    try:
        res = desvincular_lote_item_pedido(nunota=nunota, sequencia=sequencia)
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao desvincular lote')
            return JsonResponse(res, status=400)
        # Audit log: usuário/quando/o quê
        _registrar_audit_rastreio(
            request, acao='DESVINCULAR',
            nunota=nunota, sequencia=sequencia,
            codagregacao=res.get('codagregacao_removido'),
            qtd=None,
            extra={'operacao': res.get('operacao')},
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_desvincular_lote")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_atribuir_lote(request: HttpRequest) -> JsonResponse:
    """Atribui um lote (CODAGREGACAO) a um item de pedido TOP 34.

    Aceita atribuição total (qtd omitido ou igual à QTDNEG do item) ou parcial
    (qtd menor — divide a linha do TGFITE).
    """
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota       = _converter_para_inteiro(dados.get('nunota'))
    sequencia    = _converter_para_inteiro(dados.get('sequencia'))
    codagregacao = (dados.get('codagregacao') or '').strip()
    qtd          = _converter_para_float(dados.get('qtd'))  # opcional

    if not nunota or not sequencia or not codagregacao:
        return JsonResponse(
            {"ok": False, "error": "nunota, sequencia e codagregacao são obrigatórios"},
            status=400,
        )

    try:
        res = atribuir_lote_item_pedido(
            nunota=nunota,
            sequencia=sequencia,
            codagregacao=codagregacao,
            qtd=qtd,
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao atribuir lote')
            return JsonResponse(res, status=400)
        # Audit log — registra qual lote foi atribuído a qual item por quem
        _registrar_audit_rastreio(
            request, acao='ATRIBUIR',
            nunota=nunota, sequencia=sequencia,
            codagregacao=codagregacao,
            qtd=res.get('qtd_atribuida') or qtd,
            extra={
                'operacao':       res.get('operacao'),
                'nova_sequencia': res.get('nova_sequencia'),
            },
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_atribuir_lote")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


# ==============================================================================
# 🔗 VÍNCULO MANUAL PEDIDO ↔ NOTA (Leva A, Mai/2026)
# Quando Sankhya não populou TGFVAR e há pedido+nota pareáveis no banco,
# operador vincula manualmente pelo IAgro. Reversível (DELETE da linha).
# ==============================================================================

@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_vinculo_candidatos(request: HttpRequest) -> JsonResponse:
    """Sugere pedidos órfãos pareáveis com a nota informada (mesmo CODPARC +
    DTNEG ±N + valor próximo). Não persiste nada — só busca."""
    nunota_nota = _converter_para_inteiro(request.GET.get('nunota_nota'))
    if not nunota_nota:
        return JsonResponse(
            {"ok": False, "error": "nunota_nota é obrigatório"}, status=400,
        )
    try:
        candidatos = consultar_candidatos_pedido_para_nota(nunota_nota, limite=10)
        return JsonResponse({"ok": True, "candidatos": candidatos})
    except Exception as e:
        logger.exception("Erro em api_rastreio_vinculo_candidatos")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_vinculo_criar(request: HttpRequest) -> JsonResponse:
    """Cria vínculo manual entre pedido (TOP 34) e nota (TOP 35/37)."""
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota_pedido = _converter_para_inteiro(dados.get('nunota_pedido'))
    nunota_nota   = _converter_para_inteiro(dados.get('nunota_nota'))
    observacao    = (dados.get('observacao') or '').strip()

    if not nunota_pedido or not nunota_nota:
        return JsonResponse(
            {"ok": False, "error": "nunota_pedido e nunota_nota são obrigatórios"},
            status=400,
        )

    try:
        codusu  = request.session.get('codusu') or 0
        nomeusu = (request.session.get('nomeusu')
                   or request.session.get('nome') or '')[:80]
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=nunota_pedido, nunota_nota=nunota_nota,
            codusu=int(codusu), nomeusu=nomeusu, observacao=observacao,
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao vincular')
            return JsonResponse(res, status=400)
        _registrar_audit_rastreio(
            request, acao='VINCULAR_MANUAL',
            nunota=nunota_nota, sequencia=0,
            codagregacao=None, qtd=None,
            extra={
                'nunota_pedido': nunota_pedido,
                'nunota_nota':   nunota_nota,
                'vinculo_id':    res.get('id'),
                'origem':        'VINCULADO',
            },
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_vinculo_criar")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_vinculo_criar_pedido_retroativo(request: HttpRequest) -> JsonResponse:
    """Leva B (Mai/2026) — cria pedido TOP 34 retroativo a partir de nota órfã
    e grava vínculo com ORIGEM='PEDIDO_RETROATIVO'. Usado quando a nota foi
    venda direta sem pedido (caso 111825)."""
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota_nota = _converter_para_inteiro(dados.get('nunota_nota'))
    if not nunota_nota:
        return JsonResponse(
            {"ok": False, "error": "nunota_nota é obrigatório"}, status=400,
        )

    try:
        codusu  = request.session.get('codusu') or 0
        nomeusu = (request.session.get('nomeusu')
                   or request.session.get('nome') or '')[:80]
        res = criar_pedido_retroativo_a_partir_de_nota(
            nunota_nota=nunota_nota, codusu=int(codusu), nomeusu=nomeusu,
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao criar pedido retroativo')
            return JsonResponse(res, status=400)
        _registrar_audit_rastreio(
            request, acao='CRIAR_PEDIDO_RETROATIVO',
            nunota=nunota_nota, sequencia=0,
            codagregacao=None, qtd=None,
            extra={
                'nunota_pedido_novo': res.get('nunota_pedido'),
                'nunota_nota':        nunota_nota,
                'vinculo_id':         res.get('vinculo_id'),
                'qtd_itens':          res.get('qtd_itens'),
                'origem':             'PEDIDO_RETROATIVO',
            },
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_vinculo_criar_pedido_retroativo")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_vinculo_resolver(request: HttpRequest) -> JsonResponse:
    """Fluxo unificado de resolução de nota órfã (Mai/2026 — Levas A+B):

    O backend busca pedido pareável pela heurística rigorosa e executa a
    ação correspondente:
      - Se há candidato exato: vincula (Leva A)
      - Se não há: cria pedido retroativo (Leva B)

    Operador pode forçar via `acao = 'VINCULAR'|'CRIAR'`. Sem parâmetro,
    backend decide (`AUTO`).
    """
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota_nota = _converter_para_inteiro(dados.get('nunota_nota'))
    acao        = (dados.get('acao') or 'AUTO').upper()

    if not nunota_nota:
        return JsonResponse(
            {"ok": False, "error": "nunota_nota é obrigatório"}, status=400,
        )
    if acao not in ('AUTO', 'VINCULAR', 'CRIAR'):
        return JsonResponse(
            {"ok": False, "error": "acao deve ser AUTO, VINCULAR ou CRIAR"},
            status=400,
        )

    try:
        codusu  = request.session.get('codusu') or 0
        nomeusu = (request.session.get('nomeusu')
                   or request.session.get('nome') or '')[:80]
        res = resolver_nota_orfa_automatica(
            nunota_nota=nunota_nota, codusu=int(codusu), nomeusu=nomeusu,
            acao=acao,
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao resolver nota órfã')
            return JsonResponse(res, status=400)
        # Audit unificado
        acao_executada = res.get('acao')
        _registrar_audit_rastreio(
            request,
            acao=f'RESOLVER_NOTA_ORFA_{acao_executada}',
            nunota=nunota_nota, sequencia=0,
            codagregacao=None, qtd=None,
            extra={
                'nunota_pedido':   res.get('nunota_pedido'),
                'nunota_nota':     nunota_nota,
                'vinculo_id':      res.get('vinculo_id'),
                'qtd_itens':       res.get('qtd_itens'),
                'acao_executada':  acao_executada,
                'acao_solicitada': acao,
            },
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_vinculo_resolver")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_vinculo_remover(request: HttpRequest) -> JsonResponse:
    """Desfaz vínculo manual pelo NUNOTA do pedido OU da nota."""
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota_pedido = _converter_para_inteiro(dados.get('nunota_pedido'))
    nunota_nota   = _converter_para_inteiro(dados.get('nunota_nota'))

    if not nunota_pedido and not nunota_nota:
        return JsonResponse(
            {"ok": False, "error": "Informe nunota_pedido ou nunota_nota"},
            status=400,
        )

    try:
        res = remover_vinculo_manual_pedido_nota(
            nunota_pedido=nunota_pedido, nunota_nota=nunota_nota,
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao desfazer vínculo')
            return JsonResponse(res, status=400)
        _registrar_audit_rastreio(
            request, acao='DESVINCULAR_MANUAL',
            nunota=nunota_nota or nunota_pedido, sequencia=0,
            codagregacao=None, qtd=None,
            extra={
                'nunota_pedido': nunota_pedido,
                'nunota_nota':   nunota_nota,
                'removidos':     res.get('removidos'),
            },
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_vinculo_remover")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


# ==============================================================================
# 📧 IMPORTAÇÃO DE PEDIDOS POR E-MAIL
# Endpoints para a fila de revisão (E5). Confirmação fica em E7.
# ==============================================================================

@exige_grupo('venda')
@ensure_csrf_cookie
def view_email_importar(request: HttpRequest) -> HttpResponse:
    """Renderiza a página de revisão de pré-pedidos vindos de e-mail.

    `ensure_csrf_cookie` é necessário porque a tela faz POSTs (descartar,
    reparser, confirmar) sem prévia de form HTML.
    """
    return render(request, 'sankhya_integration/email_importar.html')


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_email_listar(request: HttpRequest) -> JsonResponse:
    """Lista pré-pedidos por status (default PENDENTE_REVISAO).

    Querystring: ?status=PENDENTE_REVISAO|... &dias=N &limit=&offset=
    """
    try:
        status_param = request.GET.get('status') or 'PENDENTE_REVISAO'
        # aceita múltiplos: ?status=PENDENTE_REVISAO,ERRO_PARSER
        if ',' in status_param:
            status: str | list = [s.strip() for s in status_param.split(',') if s.strip()]
        else:
            status = status_param

        dias = request.GET.get('dias')
        try: dias_n = int(dias) if dias else None
        except (TypeError, ValueError): dias_n = None

        lim, off = _paginacao_do_request(request, default_limit=50)

        rows = listar_pedidos_email_pendentes(
            filtros={'status': status, 'dias': dias_n},
            limite=lim, offset=off,
        )
        return JsonResponse({'ok': True, 'rows': rows, 'limit': lim, 'offset': off})
    except Exception as exc:
        logger.exception("Erro em api_email_listar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


_ORIGENS_PASTE_VALIDAS = {'TEXTO_LIVRE', 'WHATSAPP_API'}


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_importar_texto(request: HttpRequest) -> JsonResponse:
    """Operador colou um pedido em texto livre (WhatsApp / e-mail / etc.).

    Cria registro em AD_PEDIDO_EMAIL_RECEBIDO com STATUS=AGUARDANDO_PARSER e
    PDF_PATH=NULL. O worker, ao rodar a fase de parser LLM, lê PDF_TEXTO
    direto e processa igual aos pedidos vindos de IMAP.

    Body JSON: {"texto": "<...>", "origem": "TEXTO_LIVRE"|"WHATSAPP_API"}
    """
    import uuid
    from datetime import datetime
    from sankhya_integration.services.oracle_conn import inserir_pedido_email_recebido

    try:
        payload = _get_json_payload(request) or {}
        texto = (payload.get('texto') or '').strip()
        origem = (payload.get('origem') or 'TEXTO_LIVRE').upper()
        codusu = request.session.get('codusu')

        if not texto:
            return JsonResponse({'ok': False, 'error': 'Texto vazio.'}, status=400)
        if len(texto) < 30:
            return JsonResponse(
                {'ok': False, 'error': 'Texto muito curto (mín. 30 caracteres).'},
                status=400,
            )
        if origem not in _ORIGENS_PASTE_VALIDAS:
            return JsonResponse(
                {'ok': False, 'error': f"Origem inválida: {origem}"},
                status=400,
            )

        agora = datetime.now()
        message_id = f'manual:{uuid.uuid4().hex}'
        remetente = f'Operador {codusu or "?"}'
        assunto_label = {
            'TEXTO_LIVRE':  'Texto livre',
            'WHATSAPP_API': 'WhatsApp',
        }.get(origem, origem)

        res = inserir_pedido_email_recebido({
            'MESSAGE_ID':    message_id,
            'SUB_ID':        1,
            'REMETENTE':     remetente,
            'ASSUNTO':       assunto_label,
            'RECEBIDO_EM':   agora,
            'PROCESSADO_EM': agora,
            'PDF_PATH':      None,           # paste manual não tem arquivo
            'PDF_TEXTO':     texto,
            'STATUS':        'AGUARDANDO_PARSER',
            'ORIGEM':        origem,
        })
        if not res.get('ok'):
            return JsonResponse(
                {'ok': False, 'error': humanizar_erro_oracle(res.get('error') or 'falha')},
                status=400,
            )
        return JsonResponse({
            'ok': True,
            'id': res.get('id'),
            'mensagem': 'Texto importado. O parser LLM vai processar na próxima rodada do worker.',
        })
    except Exception as exc:
        logger.exception("Erro em api_email_importar_texto")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_email_obter(request: HttpRequest, recebido_id: int) -> JsonResponse:
    """Detalhes de um pré-pedido (cabeçalho + itens + sugestões)."""
    try:
        rec = obter_pedido_email_completo(int(recebido_id))
        if not rec:
            return JsonResponse({'ok': False, 'error': 'Pré-pedido não encontrado.'}, status=404)
        # Serializa datas/timestamps de forma amigável para JSON
        for k in ('recebido_em', 'processado_em', 'confirmado_em', 'criado_em', 'dtneg_sugerida'):
            v = rec.get(k)
            if hasattr(v, 'isoformat'): rec[k] = v.isoformat()
        for it in rec.get('itens', []):
            v = it.get('criado_em')
            if hasattr(v, 'isoformat'): it['criado_em'] = v.isoformat()
        # Extrai do JSON crú do LLM o nome literal do cliente que veio no PDF.
        # Útil como hint visual ao operador: o matching pode ter casado num
        # CODPARC genérico ("SENDAS DISTRIBUIDORA"), mas o PDF dizia
        # "SENDAS DISTRIBUIDORA S/A LJ176 PALMAS" — ver isso ajuda a refinar.
        try:
            llm_raw = rec.get('llm_resposta')
            if llm_raw:
                rec['cliente_nome_extraido'] = (json.loads(llm_raw).get('cliente_nome') or '').strip() or None
        except Exception:
            rec['cliente_nome_extraido'] = None

        # Totais declarados no PDF — pra UI de conferência cruzada
        # (Σ calculado dos itens vs total declarado pelo PDF). Vale pra
        # registros parseados via LLM E via regex_consinco_v1: quando o
        # parser regex já gravou totais em llm_resposta.totais_pdf, prefere
        # esses; senão extrai do pdf_texto via mesma regex (Consinco/RelPed).
        # Records de outros layouts ou paste manual ficam com totais_pdf=None
        # e a UI esconde a linha de conferência.
        try:
            from sankhya_integration.services.pdf_parsers.consinco import extrair_totais_pdf
            totais = extrair_totais_pdf(rec.get('pdf_texto') or '')
            try:
                llm_data = json.loads(rec.get('llm_resposta') or '{}')
                tot_llm = (llm_data or {}).get('totais_pdf') or {}
                for k, v in tot_llm.items():
                    if v is not None:
                        totais[k] = v
            except Exception:
                pass
            rec['totais_pdf'] = totais if totais else None
        except Exception:
            logger.exception("Erro extraindo totais_pdf")
            rec['totais_pdf'] = None

        return JsonResponse({'ok': True, 'pedido': rec})
    except Exception as exc:
        logger.exception("Erro em api_email_obter")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
@xframe_options_sameorigin
def api_email_pdf(request: HttpRequest, recebido_id: int) -> HttpResponse:
    """Serve o PDF original arquivado, autenticado por sessão.

    O PDF_PATH guardado é absoluto. Validamos que existe e está dentro do
    PEDIDO_EMAIL_PDF_DIR antes de servir (defesa contra path traversal).
    """
    import os
    from pathlib import Path

    try:
        rec = obter_pedido_email_completo(int(recebido_id))
        if not rec:
            return HttpResponse('Pré-pedido não encontrado', status=404)
        pdf_path = rec.get('pdf_path') or ''
        if not pdf_path:
            return HttpResponse('PDF não disponível', status=404)

        base_dir = os.getenv('PEDIDO_EMAIL_PDF_DIR', '').strip()
        try:
            base_resolved = Path(base_dir).resolve()
            file_resolved = Path(pdf_path).resolve()
            file_resolved.relative_to(base_resolved)  # raises se não for filho
        except (ValueError, OSError):
            logger.warning(f"Tentativa de acessar PDF fora de PEDIDO_EMAIL_PDF_DIR: {pdf_path}")
            return HttpResponse('Acesso negado', status=403)

        if not file_resolved.exists():
            return HttpResponse('PDF não encontrado no disco', status=404)

        with open(file_resolved, 'rb') as fh:
            data = fh.read()
        resp = HttpResponse(data, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="{file_resolved.name}"'
        return resp
    except Exception:
        logger.exception("Erro em api_email_pdf")
        return HttpResponse('Erro ao servir PDF', status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_descartar(request: HttpRequest, recebido_id: int) -> JsonResponse:
    """Marca pré-pedido como DESCARTADO. Aceita motivo opcional no body."""
    try:
        payload = _get_json_payload(request) or {}
        motivo = (payload.get('motivo') or '').strip()[:500] or 'Descartado pelo operador'
        res = atualizar_pedido_email_status(int(recebido_id), 'DESCARTADO',
                                              motivo_descarte=motivo)
        if not res.get('ok'):
            return JsonResponse({'ok': False, 'error': res.get('error')}, status=400)
        return JsonResponse({'ok': True, 'rows': res.get('rows', 0)})
    except Exception as exc:
        logger.exception("Erro em api_email_descartar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_reparser(request: HttpRequest, recebido_id: int) -> JsonResponse:
    """Força re-execução do parser LLM em um pré-pedido específico.

    Útil quando o operador melhorou o prompt ou quando o registro está em
    ERRO_PARSER. Apenas troca o STATUS de volta para AGUARDANDO_PARSER e remove
    os itens existentes; o worker pega na próxima rodada.
    """
    from sankhya_integration.services.oracle_conn import deletar_itens_do_pedido_email
    try:
        rec = obter_pedido_email_completo(int(recebido_id))
        if not rec:
            return JsonResponse({'ok': False, 'error': 'Pré-pedido não encontrado.'}, status=404)
        if rec.get('status') == 'CONFIRMADO':
            return JsonResponse({'ok': False, 'error': 'Pedido já confirmado — não pode ser reparseado.'}, status=400)

        # Remove itens existentes em batch (1 DELETE pelo RECEBIDO_ID).
        # Trocamos o loop antigo `for it in rec.itens: deletar_pedido_email_item(it.id)`
        # porque o loop é falível: se obter_pedido_email_completo retornar
        # `itens=[]` por algum motivo (erro silencioso na query, etc.), nenhum
        # DELETE acontece e o worker insere por cima → DUPLICAÇÃO. Batch
        # DELETE pelo RECEBIDO_ID é atômico e não depende da lista carregada.
        res_del = deletar_itens_do_pedido_email(int(recebido_id))
        if not res_del.get('ok'):
            return JsonResponse(
                {'ok': False,
                 'error': f"Falha removendo itens existentes: {res_del.get('error')}"},
                status=500,
            )

        res = atualizar_pedido_email_status(int(recebido_id), 'AGUARDANDO_PARSER',
                                              motivo_descarte=None)
        if not res.get('ok'):
            return JsonResponse({'ok': False, 'error': res.get('error')}, status=400)
        return JsonResponse({
            'ok': True,
            'itens_removidos': res_del.get('rows', 0),
            'mensagem': 'Reparser agendado para próxima rodada do worker.',
        })
    except Exception as exc:
        logger.exception("Erro em api_email_reparser")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_atualizar_item(request: HttpRequest, item_id: int) -> JsonResponse:
    """Operador editou um item na tela de revisão.

    Body JSON aceita: CODPROD_FINAL, QTD, CODVOL, PRECO_UNIT, OBSERVACAO,
    DESCRICAO_PDF.
    """
    try:
        payload = _get_json_payload(request) or {}
        if not payload:
            return JsonResponse({'ok': False, 'error': 'Body vazio.'}, status=400)
        res = atualizar_pedido_email_item(int(item_id), payload)
        if not res.get('ok'):
            return JsonResponse({'ok': False, 'error': res.get('error')}, status=400)
        return JsonResponse({'ok': True, 'rows': res.get('rows', 0)})
    except Exception as exc:
        logger.exception("Erro em api_email_atualizar_item")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_remover_item(request: HttpRequest, item_id: int) -> JsonResponse:
    """Operador clicou lixeira em um item da tela de revisão."""
    try:
        res = deletar_pedido_email_item(int(item_id))
        if not res.get('ok'):
            return JsonResponse({'ok': False, 'error': res.get('error')}, status=400)
        return JsonResponse({'ok': True, 'rows': res.get('rows', 0)})
    except Exception as exc:
        logger.exception("Erro em api_email_remover_item")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_criar_item(request: HttpRequest, recebido_id: int) -> JsonResponse:
    """Operador adicionou item manualmente na tela de revisão.

    Útil quando o LLM esqueceu uma linha do PDF ou o operador precisa
    incluir item que não veio. SEQUENCIA = MAX+1 do pré-pedido.
    Como o operador escolheu o CODPROD na hora, já gravamos como FINAL
    com CONFIANCA=1.00 (decisão humana).
    """
    from sankhya_integration.services.oracle_conn import inserir_pedido_email_item

    try:
        payload = _get_json_payload(request) or {}
        codprod    = _converter_para_inteiro(payload.get('codprod'))
        qtd        = payload.get('qtd')
        codvol     = (payload.get('codvol') or '').strip().upper() or None
        preco_unit = payload.get('preco_unit')

        if not codprod:
            return JsonResponse({'ok': False, 'error': 'CODPROD obrigatório.'}, status=400)
        try:
            qtd_f = float(qtd) if qtd not in (None, '') else 0
        except (TypeError, ValueError):
            qtd_f = 0
        if qtd_f <= 0:
            return JsonResponse({'ok': False, 'error': 'QTD obrigatória e positiva.'}, status=400)

        rec = obter_pedido_email_completo(int(recebido_id))
        if not rec:
            return JsonResponse({'ok': False, 'error': 'Pré-pedido não encontrado.'}, status=404)
        if rec.get('status') in ('CONFIRMADO', 'DESCARTADO'):
            return JsonResponse(
                {'ok': False, 'error': f"Pré-pedido {rec['status'].lower()} — não é possível adicionar itens."},
                status=400,
            )

        seq_atual = max(
            (int(it.get('sequencia') or 0) for it in (rec.get('itens') or [])),
            default=0,
        )
        nova_seq = seq_atual + 1

        res = inserir_pedido_email_item({
            'RECEBIDO_ID':       int(recebido_id),
            'SEQUENCIA':         nova_seq,
            'DESCRICAO_PDF':     '[manual]',
            'CODPROD_SUGERIDO':  codprod,
            'CODPROD_CONFIANCA': 1.0,
            'CODPROD_FINAL':     codprod,
            'QTD':               qtd_f,
            'CODVOL':            codvol,
            'PRECO_UNIT':        preco_unit,
        })
        if not res.get('ok'):
            return JsonResponse({'ok': False, 'error': res.get('error')}, status=400)
        return JsonResponse({'ok': True, 'item_id': res.get('id'), 'sequencia': nova_seq})
    except Exception as exc:
        logger.exception("Erro em api_email_criar_item")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


# ----------------------------------------------------------------------------
# Restauração de itens (sem rodar LLM de novo)
# ----------------------------------------------------------------------------
# O LLM_RESPOSTA crú está sempre salvo em AD_PEDIDO_EMAIL_RECEBIDO. Esses
# endpoints leem o JSON e refazem os itens via matching atual — sem nova
# chamada Ollama, instantâneo. Útil quando operador edita errado e quer
# desfazer SEM esperar 3 min de novo LLM call.

def _restaurar_itens_originais(rec: dict, codparc_sug: int | None) -> tuple[int, int]:
    """Apaga itens atuais e re-cria a partir do LLM_RESPOSTA + matching atual.

    Retorna (qtd_inseridos, qtd_apagados). Não chama LLM — usa o JSON crú
    já salvo em rec['llm_resposta'].
    """
    import json as _json
    from sankhya_integration.services import matching as _matching
    from sankhya_integration.services.oracle_conn import (
        deletar_itens_do_pedido_email, inserir_pedido_email_item,
    )

    recebido_id = int(rec['id'])
    raw = rec.get('llm_resposta') or '{}'
    try:
        llm = _json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        llm = {}
    itens_originais = llm.get('itens') or []

    res_del = deletar_itens_do_pedido_email(recebido_id)
    apagados = res_del.get('rows', 0) if res_del.get('ok') else 0

    inseridos = 0
    for idx, it in enumerate(itens_originais, start=1):
        descr = (it.get('descricao_pdf') or '').strip()
        if not descr:
            continue
        cod_cliente = it.get('cod_cliente')  # pode estar no JSON crú do LLM (Consinco)
        codprod, score, _descr_canon = _matching.casar_codprod(
            descr, codparc=codparc_sug, cod_cliente=cod_cliente,
        )
        inserir_pedido_email_item({
            'RECEBIDO_ID':       recebido_id,
            'SEQUENCIA':         idx,
            'DESCRICAO_PDF':     descr,
            'COD_CLIENTE':       cod_cliente,
            'CODPROD_SUGERIDO':  codprod,
            'CODPROD_CONFIANCA': round(score / 100.0, 2) if score else 0,
            'CODPROD_FINAL':     None,   # null = "operador ainda não confirmou" — vai
                                          # render usando codprod_sugerido
            'QTD':               it.get('qtd'),
            'CODVOL':            (it.get('codvol') or 'KG').upper(),
            'PRECO_UNIT':        it.get('preco_unit'),
        })
        inseridos += 1
    return inseridos, apagados


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_restaurar_todos(request: HttpRequest, recebido_id: int) -> JsonResponse:
    """Restaura TODOS os itens ao estado original do LLM_RESPOSTA + matching atual.

    NÃO chama LLM (instantâneo). Apaga itens atuais e recria a partir do JSON
    crú salvo. Útil pra desfazer edições sem esperar nova rodada do worker.
    """
    try:
        rec = obter_pedido_email_completo(int(recebido_id))
        if not rec:
            return JsonResponse({'ok': False, 'error': 'Pré-pedido não encontrado.'}, status=404)
        if rec.get('status') == 'CONFIRMADO':
            return JsonResponse({'ok': False, 'error': 'Pré-pedido já confirmado.'}, status=400)

        inseridos, apagados = _restaurar_itens_originais(rec, rec.get('codparc_sugerido'))
        return JsonResponse({
            'ok': True,
            'inseridos': inseridos,
            'apagados': apagados,
            'mensagem': f'{inseridos} itens restaurados ao original.',
        })
    except Exception as exc:
        logger.exception("Erro em api_email_restaurar_todos")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_restaurar_item(request: HttpRequest, item_id: int) -> JsonResponse:
    """Restaura UM item ao valor original do LLM_RESPOSTA + matching atual.

    Identifica o item original pela SEQUENCIA do item atual (1-indexed na
    lista do JSON). Faz UPDATE — preserva o ID do item.
    """
    try:
        import json as _json
        from sankhya_integration.services import matching as _matching

        # Carrega item + cabecalho (precisamos da SEQUENCIA + LLM_RESPOSTA)
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT i.SEQUENCIA, i.RECEBIDO_ID, r.LLM_RESPOSTA, r.CODPARC_SUGERIDO, r.STATUS "
                "  FROM AD_PEDIDO_EMAIL_ITEM i "
                "  JOIN AD_PEDIDO_EMAIL_RECEBIDO r ON r.ID = i.RECEBIDO_ID "
                " WHERE i.ID = :id",
                id=int(item_id),
            )
            row = cur.fetchone()
            if not row:
                return JsonResponse({'ok': False, 'error': 'Item não encontrado.'}, status=404)
            sequencia, recebido_id, llm_raw, codparc_sug, status = row
            if hasattr(llm_raw, 'read'):
                llm_raw = llm_raw.read()
            if status == 'CONFIRMADO':
                return JsonResponse({'ok': False, 'error': 'Pré-pedido já confirmado.'}, status=400)

            try:
                llm = _json.loads(llm_raw or '{}')
            except Exception:
                llm = {}
            itens_orig = llm.get('itens') or []
            idx = int(sequencia) - 1
            if idx < 0 or idx >= len(itens_orig):
                return JsonResponse({
                    'ok': False,
                    'error': 'Item original não encontrado no LLM_RESPOSTA — use Restaurar tudo.',
                }, status=400)

            it_orig = itens_orig[idx]
            descr = (it_orig.get('descricao_pdf') or '').strip()
            cod_cliente = it_orig.get('cod_cliente')
            codprod, score, _ = _matching.casar_codprod(
                descr, codparc=codparc_sug, cod_cliente=cod_cliente,
            )

            # COD_CLIENTE só é atualizado se a coluna existir (migration aplicada)
            from sankhya_integration.services.oracle_conn import _existe_coluna
            tem_cod_cliente = _existe_coluna(cur, 'AD_PEDIDO_EMAIL_ITEM', 'COD_CLIENTE')
            sql = (
                "UPDATE AD_PEDIDO_EMAIL_ITEM "
                "   SET DESCRICAO_PDF = :d, "
                "       CODPROD_SUGERIDO = :sug, "
                "       CODPROD_CONFIANCA = :conf, "
                "       CODPROD_FINAL = NULL, "
                "       QTD = :q, CODVOL = :v, PRECO_UNIT = :p "
                + (", COD_CLIENTE = :cc " if tem_cod_cliente else "")
                + " WHERE ID = :id"
            )
            binds = {
                'id': int(item_id),
                'd': descr,
                'sug': codprod,
                'conf': round(score / 100.0, 2) if score else 0,
                'q': it_orig.get('qtd'),
                'v': (it_orig.get('codvol') or 'UN').upper(),
                'p': it_orig.get('preco_unit'),
            }
            if tem_cod_cliente:
                binds['cc'] = (str(cod_cliente).strip()[:50] if cod_cliente else None)

            cur.execute(sql, binds)
            conn.commit()
            return JsonResponse({'ok': True, 'mensagem': 'Item restaurado ao original.'})
    except Exception as exc:
        logger.exception("Erro em api_email_restaurar_item")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_email_confirmar(request: HttpRequest, recebido_id: int) -> JsonResponse:
    """Promove pré-pedido vindo de e-mail para TGFCAB TOP 34.

    Reusa as mesmas funções que `api_criar_cabecalho_venda` e
    `api_salvar_item_venda` usam — comportamento idêntico ao fluxo manual.

    Validações antes de tocar TGFCAB:
        - Pré-pedido existe e está em PENDENTE_REVISAO ou ERRO_PARSER.
        - JSON tem CODPARC, CODEMP, CODTIPVENDA, DTNEG.
        - Todos os itens têm CODPROD_FINAL (operador confirmou na tela).
    Em caso de qualquer falha durante o INSERT, faz rollback. AD_PEDIDO_EMAIL_*
    só é atualizada para CONFIRMADO se TUDO deu certo.
    """
    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    payload = _get_json_payload(request) or {}
    codparc = _converter_para_inteiro(payload.get('codparc'))
    codemp = _converter_para_inteiro(payload.get('codemp'))
    codtipvenda = _converter_para_inteiro(payload.get('codtipvenda'))
    dtneg_raw = payload.get('dtneg')
    observacao = (payload.get('observacao') or '').strip() or None
    codusu = request.session.get('codusu')

    if not codparc:     return JsonResponse({"ok": False, "error": "CODPARC obrigatório"}, status=400)
    if not codemp:      return JsonResponse({"ok": False, "error": "CODEMP obrigatório"}, status=400)
    if not codtipvenda: return JsonResponse({"ok": False, "error": "CODTIPVENDA obrigatório"}, status=400)
    if not dtneg_raw:   return JsonResponse({"ok": False, "error": "DTNEG obrigatória"}, status=400)
    if not codusu:      return JsonResponse({"ok": False, "error": "Sessão sem CODUSU"}, status=403)

    # Carrega o pré-pedido + itens
    rec = obter_pedido_email_completo(int(recebido_id))
    if not rec:
        return JsonResponse({"ok": False, "error": "Pré-pedido não encontrado"}, status=404)
    if rec.get('status') == 'CONFIRMADO':
        return JsonResponse({"ok": False, "error": "Pré-pedido já confirmado"}, status=400)
    if rec.get('status') == 'DESCARTADO':
        return JsonResponse({"ok": False, "error": "Pré-pedido descartado"}, status=400)

    itens_pre = rec.get('itens') or []
    if not itens_pre:
        return JsonResponse({"ok": False, "error": "Pré-pedido sem itens"}, status=400)

    sem_codprod = [i for i in itens_pre if not i.get('codprod_final')]
    if sem_codprod:
        return JsonResponse(
            {"ok": False, "error": f"{len(sem_codprod)} item(ns) sem CODPROD definido"},
            status=400,
        )

    # Cabeçalho — mesmos defaults da api_criar_cabecalho_venda
    cabecalho_payload = {
        'CODEMP':      codemp,
        'CODPARC':     codparc,
        'CODTIPOPER':  34,
        'CODNAT':      10010100,
        'CODCENCUS':   10100,
        'CODTIPVENDA': codtipvenda,
        'DTNEG':       _data_br_para_iso(dtneg_raw),
        'OBSERVACAO':  observacao,
    }

    try:
        with obter_conexao_oracle() as conn:
            try:
                # 1) INSERT TGFCAB (TOP 34)
                plano_cab = inserir_cabecalho_nota_banco(
                    cabecalho_payload, simulacao=False, conexao_existente=conn,
                )
                if not plano_cab.get('executed'):
                    conn.rollback()
                    return JsonResponse(
                        {"ok": False,
                         "error": humanizar_erro_oracle(plano_cab.get('error') or 'Falha ao criar pedido')},
                        status=400,
                    )
                nunota = plano_cab['nunota']

                # 2) INSERT TGFITE para cada item (gerar_lote_auto=False — venda não gera lote)
                for it in itens_pre:
                    item_payload = {
                        'NUNOTA':       nunota,
                        'CODPROD':      int(it['codprod_final']),
                        'QTDNEG':       float(it.get('qtd') or 0),
                        'VLRUNIT':      float(it.get('preco_unit') or 0),
                        'CODVOL':       (it.get('codvol') or 'CX').upper(),
                        'CODVOLPARC':   (it.get('codvol') or 'CX').upper(),
                        'CODAGREGACAO': None,  # vínculo de lote fica para o Rastreio
                    }
                    plano_it = inserir_item_nota_banco(
                        item_payload, simulacao=False, conexao_existente=conn,
                        codusu_logado=codusu, gerar_lote_auto=False,
                    )
                    if not plano_it.get('executed'):
                        conn.rollback()
                        return JsonResponse(
                            {"ok": False,
                             "error": humanizar_erro_oracle(
                                 plano_it.get('error') or f"Falha ao salvar item: {it.get('descricao_pdf')}"),
                             "item_falhou": it.get('descricao_pdf')},
                            status=400,
                        )

                # 3) Recalcula totais
                recalcular_totais_nota_banco(nunota, conexao_existente=conn)

                # 4) Marca pré-pedido como CONFIRMADO + grava NUNOTA + CODUSU
                vincular_nunota_pedido_email(
                    recebido_id=int(recebido_id), nunota=int(nunota), codusu=int(codusu),
                    conexao_existente=conn,
                )

                conn.commit()
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as e:
        logger.exception("Erro em api_email_confirmar")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    # 5) APRENDIZADO (pós-commit, tolerante a falhas)
    # Após confirmação humana, gravamos as decisões dele em AD_*_ALIAS
    # pra próximos pré-pedidos com a mesma descrição/cliente irem direto.
    # Falha aqui NÃO desfaz a confirmação — só perde a oportunidade de aprender.
    try:
        from sankhya_integration.services.matching import (
            aprender_alias_parceiro, aprender_alias_produto, aprender_cod_cliente,
        )
        # Alias de parceiro: usa o nome extraído pelo LLM como chave.
        # Se o LLM_RESPOSTA tem cliente_nome, usamos. Senão pula.
        try:
            import json
            llm_resp_raw = rec.get('llm_resposta') or '{}'
            llm_resp = json.loads(llm_resp_raw) if isinstance(llm_resp_raw, str) else llm_resp_raw
            cliente_nome_extraido = (llm_resp.get('cliente_nome')
                                       or (llm_resp.get('cliente') or {}).get('nome'))
            if cliente_nome_extraido:
                aprender_alias_parceiro(
                    nome_extraido=cliente_nome_extraido,
                    codparc=int(codparc),
                    confirmado_por=int(codusu),
                )
        except Exception:
            logger.warning("Falha aprendendo alias parceiro — segue sem aprender", exc_info=True)

        # Aprendizado por item:
        #   1) Alias por descrição (chave = descricao_pdf, valor = codprod_final)
        #   2) Vinculação por código do cliente quando presente
        #      (chave = (codparc, cod_cliente), valor = codprod_final)
        # A 2ª é mais forte: bate exato em código numérico, sem fuzzy.
        for it in itens_pre:
            descr = it.get('descricao_pdf')
            codprod_final = it.get('codprod_final')
            cod_cliente = it.get('cod_cliente')
            if descr and codprod_final:
                aprender_alias_produto(
                    descricao_pdf=descr,
                    codprod=int(codprod_final),
                    codparc=int(codparc),  # alias scope-specific por cliente
                    confirmado_por=int(codusu),
                )
            if cod_cliente and codprod_final:
                aprender_cod_cliente(
                    codparc=int(codparc),
                    cod_cliente=cod_cliente,
                    codprod=int(codprod_final),
                    confirmado_por=int(codusu),
                )
    except Exception:
        logger.warning("Falha geral no aprendizado de alias — pré-pedido confirmado normalmente", exc_info=True)

    return JsonResponse({"ok": True, "nunota": nunota}, status=200)


