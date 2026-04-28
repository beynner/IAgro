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
)

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
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
        listar_vendas_paginado
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
    status = {'oracle_import': ORACLE_DISPONIVEL}
    if ORACLE_DISPONIVEL:
        try:
            with obter_conexao_oracle() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM DUAL")
                _ = cur.fetchone()
                status['db_ping'] = True
        except Exception as e:
            status['db_ping'] = False
            status['error'] = str(e)
    else:
        status['error'] = 'Driver Oracle inativo.'
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
        "APP_VERSION": "1.0.0"
    }
    return render(request, "sankhya_integration/entrada.html", contexto)

# Alias de retrocompatibilidade para o frontend JS ou menus do Django
def compras_portal(request: HttpRequest) -> HttpResponse: return view_portal_entradas(request)
def packing_portal(request: HttpRequest) -> HttpResponse: return view_portal_entradas(request)

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
            return redirect(f"/sankhya/packing/central/?nunota={plano['nunota']}")

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
        "APP_VERSION": "1.0.0",
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
        "APP_VERSION": "1.0.0",
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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


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
            plano = inserir_cabecalho_nota_banco(
                payload, simulacao=False, conexao_existente=conn
            )
            if plano.get('executed'):
                conn.commit()
            else:
                conn.rollback()
    except Exception as e:
        logger.exception("Erro ao criar cabeçalho de venda")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    if not plano.get('executed'):
        logger.warning(
            "Falha ao criar cabeçalho de venda. Payload=%s | Resposta service=%s",
            payload, plano,
        )
        return JsonResponse(
            {"ok": False, "error": plano.get('error') or 'Falha ao criar pedido'},
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
            plano = inserir_item_nota_banco(
                payload, simulacao=False, conexao_existente=conn,
                codusu_logado=codusu, gerar_lote_auto=False,
            )
            if not plano.get('executed'):
                conn.rollback()
                return JsonResponse(
                    {"ok": False, "error": plano.get('error') or 'Falha ao salvar item'},
                    status=400,
                )
            recalculo = recalcular_totais_nota_banco(nunota, conexao_existente=conn) or {}
            conn.commit()
    except Exception as e:
        logger.exception("Erro ao salvar item de venda")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    if not row:
        return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)
    if int(row[0]) != 34:
        return JsonResponse(
            {"ok": False, "error": f"Operação permitida apenas para TOP 34 (esta é {int(row[0])})"},
            status=403,
        )

    resposta = excluir_nota_completa_banco(nunota, simulacao=False)
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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    if not plano.get('executed'):
        logger.warning(
            "Falha ao atualizar cabeçalho de venda. Payload=%s | Resposta service=%s",
            payload, plano,
        )
        return JsonResponse(
            {"ok": False, "error": plano.get('error') or 'Falha ao atualizar pedido'},
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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

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


# ==============================================================================
# 💰 MÓDULO DE RASTREABILIDADE
# Interface de consulta e rastreio de lotes, desde a origem até o destino final, incluindo histórico de classificações e vendas.
# ==============================================================================

@exige_grupo('rastreio')
def api_rastreio_view(request):
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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def _parse_codprods(raw: str | None) -> list[int]:
    if not raw: return []
    return [int(x) for x in str(raw).split(',') if x.strip().isdigit()]


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_lotes_disponiveis(request: HttpRequest) -> JsonResponse:
    """Lista lotes com saldo disponível (e in-natura pendente) para a tela de Rastreio."""
    filtros = {
        'q':            request.GET.get('q'),
        'codprod':      request.GET.get('codprod'),
        'codprods':     _parse_codprods(request.GET.get('codprods')),
        'codagregacao': request.GET.get('codagregacao'),
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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


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
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


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
            return JsonResponse(res, status=400)
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_desvincular_lote")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


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
            return JsonResponse(res, status=400)
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_atribuir_lote")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


