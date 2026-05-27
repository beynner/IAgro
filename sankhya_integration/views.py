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
    zerar_fracao_lote_banco,
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
    # Controle de Combustível (Mai/2026 — funções de leitura + escrita)
    consultar_saldo_combustivel,
    consultar_veiculos_disponiveis,
    listar_requisicoes_combustivel,
    obter_requisicao_combustivel,
    consultar_produtos_combustivel,
    consultar_consumo_por_veiculo,
    listar_movimentacoes_combustivel,
    criar_requisicao_combustivel_banco,
    editar_requisicao_combustivel_banco,
    excluir_requisicao_combustivel_banco,
    criar_entrada_combustivel_banco,
    editar_entrada_combustivel_banco,
    excluir_entrada_combustivel_banco,
    obter_entrada_combustivel,
    consultar_prazo_tipvenda,
    consultar_preco_tabela,
    consultar_promocoes_vigentes,
    listar_promocoes_cadastradas,
    listar_tabelas_grupos,
    listar_precos_da_tabela,
    consultar_origem_preco_item,
    criar_promocao_banco,
    editar_promocao_banco,
    excluir_promocao_banco,
    registrar_origem_preco_item,
    consultar_ultimo_preco_combustivel,
    criar_abastecimento_externo_banco,
    # Dashboard executivo (Mai/2026)
    consultar_indicadores_dashboard,
    # Auditoria universal (Mai/2026 — B1)
    registrar_auditoria,
    # Auditoria — Lote A (leitura paginada da tela)
    consultar_auditoria_paginada,
    listar_filtros_distintos_auditoria,
    # Etiquetas SafeTrace/IAgro (Rastreio — Mai/2026)
    consultar_dados_etiqueta_pedido,
    consultar_pesos_classificacao_lote,  # noqa: F401  (uso indireto via consultar_dados_etiqueta_pedido)
    calcular_qtd_etiquetas,
    # Gestão de Usuários (Mai/2026) — leituras Cat A; escritas Cat B pendentes
    listar_usuarios,
    consultar_usuario_detalhe,
    consultar_grupos_disponiveis,
    # Controle de Caixas (Mai/2026) — Cat A (leitura) + Cat B (escritas)
    consultar_saldo_caixas,
    obter_timeline_caixas,
    listar_coletas_caixas,
    listar_produtos_caixa,
    criar_coleta_caixas_banco,
    estornar_coleta_caixas_banco,
    upsert_produto_caixa_banco,
    # [TEMPORÁRIO Mai/2026] backfill PESO — remover quando IAgro virar fluxo único
    popular_pesos_top34_35_37_via_moda_TEMP,
    # Avaria fornecedor não-classificável (Mai/2026 — 2026-05-19)
    atualizar_avaria_fornecedor_naoclass,
    consultar_avarias_fornecedor_da_nota,
    consultar_avarias_fornecedor_de_pedido,
    # Toggle Absorver/Descontar do modal Faturamento (Mai/2026 — 2026-05-20)
    alternar_modo_avaria_vale_lote,
    # Impressão de pedidos (Mai/2026 — 2026-05-21)
    obter_dados_pedido_completo_para_impressao,
    listar_pedidos_para_impressao,
    consultar_pesos_referencia_por_codprods,
)
from .services.etiqueta_lote import gerar_pdf_etiquetas
from .services.pedido_venda_pdf import (
    gerar_pdf_pedidos_individual,
    gerar_pdf_pedidos_consolidado,
)

from django.contrib import messages
from django.core.cache import cache
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
        confirmar_pedido_venda_banco,
        # Mai/2026 — Avaria (TOP 30) + Devolução (TOP 36) + Histórico de Lote
        criar_avaria_top30_banco,
        criar_devolucao_top36_banco,
        consultar_nota_para_devolucao,
        consultar_lotes_origem_de_seq_nota,
        obter_historico_lote,
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
    confirmar_pedido_venda_banco = _ausente('confirmar_pedido_venda_banco')
    criar_avaria_top30_banco = _ausente('criar_avaria_top30_banco')
    criar_devolucao_top36_banco = _ausente('criar_devolucao_top36_banco')
    consultar_nota_para_devolucao = _ausente('consultar_nota_para_devolucao')
    consultar_lotes_origem_de_seq_nota = _ausente('consultar_lotes_origem_de_seq_nota')
    obter_historico_lote = _ausente('obter_historico_lote')

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
    """Home: usuário logado vê o dashboard (estende base.html com sidebar);
    não-logado vê tela de login standalone (sem sidebar)."""
    if request.session.get('codusu'):
        return render(request, "sankhya_integration/home.html")
    return render(request, "sankhya_integration/home_login.html")


def api_dashboard_indicadores(request: HttpRequest) -> JsonResponse:
    """Endpoint do dashboard executivo da home — Mai/2026.

    Retorna JSON com os 6 indicadores de saúde do sistema. Acesso restrito
    a usuários autenticados (qualquer grupo). Cada indicador é tolerante a
    falha individual — se o Oracle quebrar 1 query, o restante volta.
    """
    if not request.session.get('codusu'):
        return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)
    try:
        indicadores = consultar_indicadores_dashboard()
        return JsonResponse({'ok': True, 'indicadores': indicadores})
    except Exception as exc:
        logger.exception("Falha em api_dashboard_indicadores")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(exc)},
            status=500,
        )


# ==============================================================================
# 📋 TELA DE AUDITORIA UNIVERSAL — Mai/2026 (Lote A — leitura)
# Restrito a grupos 1 (Diretoria) e 6 (Suporte). Não usa @exige_grupo pra
# evitar colisão com mapeamento existente — validação direta no corpo.
# ==============================================================================

_GRUPOS_AUDITORIA = ('1', '6')


def _pode_ver_auditoria(request: HttpRequest) -> bool:
    """Diretoria (1) e Suporte (6) têm acesso à tela de Auditoria."""
    grupos = request.session.get('grupos') or []
    return any(str(g) in _GRUPOS_AUDITORIA for g in grupos)


@ensure_csrf_cookie
def view_auditoria_painel(request: HttpRequest) -> HttpResponse:
    """Renderiza a tela de Auditoria (timeline + filtros)."""
    if not request.session.get('codusu'):
        return redirect('home')
    if not _pode_ver_auditoria(request):
        messages.error(request, 'Acesso restrito à Diretoria e ao Suporte.')
        return redirect('home')
    return render(request, "sankhya_integration/auditoria.html")


# ==============================================================================
# 📊 MÓDULO RELATÓRIOS (Mai/2026 — 2026-05-17)
# MVP de 5 relatórios em sub-abas: Top Clientes/Produtos, Lotes Envelhecidos,
# Consumo por Veículo, Fluxo de Caixa, Margem por Venda.
# Acesso: grupos 1 (Diretoria), 6 (Suporte), 9 (Comercial) — mais info no
# decorators.py / GRUPOS_PERMITIDOS['relatorios'].
# ==============================================================================

@ensure_csrf_cookie
@exige_grupo('relatorios')
def view_relatorios_painel(request: HttpRequest) -> HttpResponse:
    """Tela principal de relatórios — operador escolhe a sub-aba e o
    JS faz fetch sob demanda dos dados de cada relatório (lazy load)."""
    return render(request, "sankhya_integration/relatorios.html")


@require_http_methods(["GET"])
@exige_grupo('relatorios')
def api_relatorio_top_clientes_produtos(request: HttpRequest) -> JsonResponse:
    """Top clientes + Top produtos no período (TOP 35/37 STATUSNOTA='L').

    Query params:
        date_de=YYYY-MM-DD  (obrigatório)
        date_ate=YYYY-MM-DD (obrigatório)
        metrica=valor|qtd|pedidos (default 'valor')
        limite=N            (default 15)
    """
    date_de  = (request.GET.get('date_de')  or '').strip()
    date_ate = (request.GET.get('date_ate') or '').strip()
    metrica  = (request.GET.get('metrica')  or 'valor').strip()
    if not date_de or not date_ate:
        return JsonResponse({'ok': False, 'error': 'date_de e date_ate obrigatórios'}, status=400)
    if metrica not in ('valor', 'qtd', 'pedidos'):
        metrica = 'valor'
    try:
        limite = int(request.GET.get('limite') or 15)
        limite = max(1, min(50, limite))
    except (TypeError, ValueError):
        limite = 15

    from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
    dados = consultar_top_clientes_produtos(date_de, date_ate, metrica=metrica, limite=limite)
    return JsonResponse({'ok': True, **dados})


@require_http_methods(["GET"])
@exige_grupo('relatorios')
def api_relatorio_lotes_envelhecidos(request: HttpRequest) -> JsonResponse:
    """Lotes com saldo parado há mais de N dias.

    Query params:
        dias_min=N  (default 30)
        limite=N    (default 200)
    """
    try:
        dias_min = int(request.GET.get('dias_min') or 30)
        dias_min = max(0, min(365, dias_min))
    except (TypeError, ValueError):
        dias_min = 30

    from sankhya_integration.services.oracle_conn import consultar_lotes_envelhecidos
    dados = consultar_lotes_envelhecidos(dias_min=dias_min)
    return JsonResponse({'ok': True, **dados})


@require_http_methods(["GET"])
@exige_grupo('relatorios')
def api_relatorio_consumo_veiculos(request: HttpRequest) -> JsonResponse:
    """Ranking de consumo de combustível por veículo no período.

    Query params:
        date_de=YYYY-MM-DD  (obrigatório)
        date_ate=YYYY-MM-DD (obrigatório)
        tipo=COM|MAQ        (opcional — '' = todos)
    """
    date_de  = (request.GET.get('date_de')  or '').strip()
    date_ate = (request.GET.get('date_ate') or '').strip()
    tipo     = (request.GET.get('tipo')     or '').strip().upper()
    if not date_de or not date_ate:
        return JsonResponse({'ok': False, 'error': 'date_de e date_ate obrigatórios'}, status=400)
    if tipo not in ('', 'COM', 'MAQ'):
        tipo = ''

    from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
    dados = consultar_consumo_ranking_veiculos(date_de, date_ate, tipo=tipo)
    return JsonResponse({'ok': True, **dados})


@require_http_methods(["GET"])
@exige_grupo('relatorios')
def api_relatorio_fluxo_caixa(request: HttpRequest) -> JsonResponse:
    """Fluxo de caixa projetado nos próximos N dias.

    Query params:
        dias=30|60|90  (default 60, clipado entre 7 e 180)
    """
    try:
        dias = int(request.GET.get('dias') or 60)
    except (TypeError, ValueError):
        dias = 60

    from sankhya_integration.services.oracle_conn import consultar_fluxo_caixa
    dados = consultar_fluxo_caixa(dias=dias)
    return JsonResponse({'ok': True, **dados})


# Cache TTL pra margem por venda — query pesada (JOIN cruzado via CODAGREGACAO).
# 5 min é compromisso: operador vê dado quase-realtime, banco não é martelado.
_RELATORIO_MARGEM_CACHE_TTL = 300

@require_http_methods(["GET"])
@exige_grupo('relatorios')
def api_relatorio_margem_venda(request: HttpRequest) -> JsonResponse:
    """Margem (receita − custo) agrupada por cliente OU produto no período.

    Query params:
        date_de=YYYY-MM-DD  (obrigatório)
        date_ate=YYYY-MM-DD (obrigatório)
        agrupar=cliente|produto (default 'cliente')
        nocache=1 (opcional — força refetch ignorando cache)

    Cache: 5 min por chave `(date_de, date_ate, agrupar)` — query pesada
    (JOIN com CTE custos_lote), reuso entre operadores no mesmo período é
    quase certo. Invalidação automática pelo TTL.
    """
    date_de  = (request.GET.get('date_de')  or '').strip()
    date_ate = (request.GET.get('date_ate') or '').strip()
    agrupar  = (request.GET.get('agrupar')  or 'cliente').strip()
    nocache  = request.GET.get('nocache') == '1'
    if not date_de or not date_ate:
        return JsonResponse({'ok': False, 'error': 'date_de e date_ate obrigatórios'}, status=400)
    if agrupar not in ('cliente', 'produto'):
        agrupar = 'cliente'

    cache_key = f'rel:margem:{date_de}:{date_ate}:{agrupar}'
    dados = None if nocache else cache.get(cache_key)
    if dados is None:
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        dados = consultar_margem_por_venda(date_de, date_ate, agrupar=agrupar)
        cache.set(cache_key, dados, _RELATORIO_MARGEM_CACHE_TTL)

    return JsonResponse({'ok': True, **dados})


def api_auditoria_listar(request: HttpRequest) -> JsonResponse:
    """Lista paginada de eventos da AD_AUDITORIA_GERAL com filtros.

    Querystring:
      modulo, operacao, codusu, registro_id, busca,
      data_ini='YYYY-MM-DD', data_fim='YYYY-MM-DD',
      limite=50 (max 500), offset=0
    """
    if not request.session.get('codusu'):
        return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)
    if not _pode_ver_auditoria(request):
        return JsonResponse({'ok': False, 'error': 'Acesso restrito.'}, status=403)

    filtros = {
        'modulo':      (request.GET.get('modulo') or '').strip() or None,
        'operacao':    (request.GET.get('operacao') or '').strip() or None,
        'codusu':      _converter_para_inteiro(request.GET.get('codusu')),
        'registro_id': (request.GET.get('registro_id') or '').strip() or None,
        'busca':       (request.GET.get('busca') or '').strip() or None,
        'data_ini':    (request.GET.get('data_ini') or '').strip() or None,
        'data_fim':    (request.GET.get('data_fim') or '').strip() or None,
    }
    try:
        limite = int(request.GET.get('limite') or 50)
    except Exception:
        limite = 50
    try:
        offset = int(request.GET.get('offset') or 0)
    except Exception:
        offset = 0
    try:
        dados = consultar_auditoria_paginada(filtros, limite=limite, offset=offset)
        return JsonResponse({'ok': True, **dados})
    except Exception as exc:
        logger.exception("Falha em api_auditoria_listar")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(exc)},
            status=500,
        )


def api_auditoria_filtros(request: HttpRequest) -> JsonResponse:
    """Retorna listas distintas pra popular os filtros da tela
    (módulos, operações, usuários)."""
    if not request.session.get('codusu'):
        return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)
    if not _pode_ver_auditoria(request):
        return JsonResponse({'ok': False, 'error': 'Acesso restrito.'}, status=403)
    try:
        return JsonResponse({'ok': True, **listar_filtros_distintos_auditoria()})
    except Exception as exc:
        logger.exception("Falha em api_auditoria_filtros")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)

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
    
    # Mai/2026 (2026-05-27) — Trava de 90 dias por default. Se operador não
    # passar `?days=N`, `?days=all` ou `?start=...&end=...` explícitos, força
    # janela dos últimos 90 dias. Razão: base grande (>4700 notas) tornava
    # lista infinita inútil — agora carrega só recente; pra histórico maior,
    # operador abre filtro e seta datas/days.
    raw_days = request.GET.get("days")
    has_dates = bool(request.GET.get("start")) or bool(request.GET.get("end"))
    if raw_days is None:
        days_val = None if has_dates else 90
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
        # Mai/2026 — campo "Produto" da UI filtra por FABRICANTE (texto LIKE),
        # padrão alinhado com o Comercial. Antes vinha como `codprod` int e
        # era silenciosamente ignorado pelo service.
        "fabricante": (request.GET.get("fabricante") or "").strip() or None,
        # Mai/2026 (2026-05-27) — busca livre do campo `m_search` do mobile
        # (NOMEPARC OR NUNOTA OR NUMNOTA via LIKE). Server-side ágil.
        "q": (request.GET.get("q") or "").strip() or None,
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

    # Mai/2026 — `fabricante` é texto puro (sem código), persiste no template
    # direto via `params.fabricante` — não precisa de prod_display

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

    # Página HTML "compras central" foi removida em refator do início do projeto.
    # Endpoint mantém apenas o ramo AJAX (?ajax_header=1) usado pelo modal de
    # edição de cabeçalho da Entrada. Acessos diretos retornam 410 Gone.
    return JsonResponse({
        "ok": False,
        "error": "Página removida. Use /sankhya/compras/portal/."
    }, status=410)

def api_salvar_novo_cabecalho(request: HttpRequest) -> HttpResponse:
    """Cria um novo cabeçalho (Nota nova) usando dados do Modal Cabeçalho."""
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)

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
        return JsonResponse(plano, status=200 if plano['ok'] else 400)
    except Exception as e:
        logger.exception("Erro ao salvar o cabeçalho novo")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

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
                # Mai/2026 (2026-05-22): usa QTDNEG (negociada) em vez de
                # QTDCONFERIDA pra exibir na UI. B4 fix zera QTDCONFERIDA em
                # TOP 34/35/37 (pré-req do Sankhya pra "atender pedido"), e
                # a UI mostrava 0 erroneamente.
                'qtd': qtdneg,
                'qtd_conferida': qtdconferida,
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

            # Snapshot ANTES (best-effort) — só em UPDATE
            snapshot_antes = None
            if seq:
                try:
                    cur_snap = conn.cursor()
                    cur_snap.execute("""
                        SELECT CODPROD, QTDNEG, PESO, CODVOL, CODVOLPARC, QTDCONFERIDA, OBSERVACAO
                        FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s
                    """, n=nunota, s=seq)
                    rsnap = cur_snap.fetchone()
                    if rsnap:
                        snapshot_antes = {
                            'NUNOTA':       nunota,
                            'SEQUENCIA':    seq,
                            'CODPROD':      int(rsnap[0]) if rsnap[0] is not None else None,
                            'QTDNEG':       float(rsnap[1]) if rsnap[1] is not None else None,
                            'PESO':         float(rsnap[2]) if rsnap[2] is not None else None,
                            'CODVOL':       rsnap[3],
                            'CODVOLPARC':   rsnap[4],
                            'QTDCONFERIDA': float(rsnap[5]) if rsnap[5] is not None else None,
                            'OBSERVACAO':   rsnap[6],
                        }
                except Exception:
                    logger.warning("Falha snapshot ANTES item entrada NUNOTA=%s SEQ=%s", nunota, seq)

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
                    
                    # 🔒 Se estiver na Classificação (26), trava apenas se existe
                    # vale TOP 13 (vendas TOP 35/37 NÃO bloqueiam — Mai/2026).
                    # Operador zera negociação no Comercial pra liberar a edição.
                    elif top_atual == 26:
                        cur.execute("""
                            SELECT COUNT(1) FROM TGFCAB c JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                            WHERE c.CODTIPOPER = 13 AND i.CODAGREGACAO = :l
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

            # Audit — distingue criar vs editar pelo seq
            seq_final = int(seq) if seq else plano.get('sequencia')
            snap_d = {
                'NUNOTA':       nunota,
                'SEQUENCIA':    seq_final,
                'CODPROD':      _converter_para_inteiro(payload.get('CODPROD')),
                'QTDNEG':       float(payload.get('QTDNEG') or 0),
                'PESO':         float(payload.get('PESO') or 0),
                'CODVOL':       payload.get('CODVOL'),
                'CODVOLPARC':   payload.get('CODVOLPARC'),
                'QTDCONFERIDA': float(payload.get('QTDCONFERIDA') or payload.get('QTDNEG') or 0),
                'OBSERVACAO':   payload.get('OBSERVACAO'),
            }
            registrar_auditoria(
                modulo='entrada',
                operacao='EDITAR_ITEM_NOTA' if seq else 'CRIAR_ITEM_NOTA',
                tabela_alvo='TGFITE',
                registro_id=f"{nunota}/{seq_final}",
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_antes=snapshot_antes,
                snapshot_depois=snap_d,
            )
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
                    # Trava na exclusão: apenas vale TOP 13 bloqueia. Vendas
                    # TOP 35/37 NÃO bloqueiam — pra destravar, Comercial zera
                    # negociação (DELETE dos TGFITE TOP 13 do lote). Mai/2026.
                    cur.execute("""
                        SELECT COUNT(1)
                        FROM TGFCAB c
                        JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                        WHERE c.CODTIPOPER = 13
                          AND i.CODAGREGACAO = :l
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

            # Snapshot ANTES (best-effort) — coleta itens que vão sumir
            snapshot_antes = {'NUNOTA': nunota, 'CODTIPOPER': top_atual, 'ITENS': []}
            try:
                placeholders = ','.join(f':s{i}' for i in range(len(seqs_inteiras)))
                binds_snap = {'n': nunota, **{f's{i}': s for i, s in enumerate(seqs_inteiras)}}
                cur.execute(
                    f"""SELECT SEQUENCIA, CODPROD, QTDNEG, PESO, CODVOL, CODAGREGACAO
                        FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA IN ({placeholders})""",
                    binds_snap,
                )
                for r in cur.fetchall():
                    snapshot_antes['ITENS'].append({
                        'SEQUENCIA':    int(r[0]),
                        'CODPROD':      int(r[1]) if r[1] is not None else None,
                        'QTDNEG':       float(r[2]) if r[2] is not None else None,
                        'PESO':         float(r[3]) if r[3] is not None else None,
                        'CODVOL':       r[4],
                        'CODAGREGACAO': r[5],
                    })
            except Exception:
                logger.warning("Falha snapshot ANTES de excluir itens NUNOTA=%s", nunota)

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

        registrar_auditoria(
            modulo='classificacao' if top_atual == 26 else 'entrada',
            operacao='EXCLUIR_ITENS_NOTA',
            tabela_alvo='TGFITE',
            registro_id=nunota,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes=snapshot_antes,
            observacao=f"{len(seqs_inteiras)} item(ns) excluído(s)" + (
                ' — cabeçalho também removido (último item)' if cab_excluido else ''
            ),
        )
        resposta = {'ok': True, 'message': 'Item excluído.', 'cabecalho_excluido': cab_excluido}
        return JsonResponse(resposta)
        
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

def api_alternar_modo_avaria_vale(request: HttpRequest) -> JsonResponse:
    """Alterna modo Absorver/Descontar de um lote do vale TOP 13.

    Recalcula QTDNEG e VLRTOT do TGFITE TOP 13 conforme a decisão atual,
    sem precisar editar preço (lê o VLRUNIT já gravado no vale).

    Payload:
        {nunota_origem, codprod, codagregacao, absorver: true|false}

    Mai/2026 (2026-05-20) — B12 do plano Avaria.
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)

    payload = _get_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota_origem = _converter_para_inteiro(payload.get('nunota_origem'))
    codprod       = _converter_para_inteiro(payload.get('codprod'))
    codagregacao  = (payload.get('codagregacao') or '').strip()
    absorver      = bool(payload.get('absorver'))

    if not (nunota_origem and codprod and codagregacao):
        return JsonResponse(
            {"ok": False, "error": "nunota_origem, codprod e codagregacao são obrigatórios"},
            status=400,
        )

    try:
        res = alternar_modo_avaria_vale_lote(
            nunota_origem=nunota_origem,
            codprod=codprod,
            codagregacao=codagregacao,
            absorver=absorver,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu') or 'desconhecido',
        )
    except Exception as exc:
        logger.exception("Falha em api_alternar_modo_avaria_vale")
        return JsonResponse(
            {"ok": False, "error": humanizar_erro_oracle(exc)},
            status=500,
        )

    return JsonResponse(res, status=200 if res.get('ok') else 400)


def api_avarias_fornecedor_de_pedido(request: HttpRequest) -> JsonResponse:
    """Retorna avarias do fornecedor por LOTE dos itens de um pedido.

    Usado pelo modal Faturamento (Comercial) pra mostrar ⚠ ao lado de itens
    cujo lote teve descarte do fornecedor registrado na TOP 11 origem.

    Resposta:
        {"ok": true, "avarias_por_lote": {codagregacao: {qtd_avaria,
                                                         qtd_entrada,
                                                         fornecedor,
                                                         dtneg_entrada}}}

    Mai/2026 (2026-05-19).
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)

    nunota = _converter_para_inteiro(request.GET.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)

    avarias = consultar_avarias_fornecedor_de_pedido(nunota) or {}
    return JsonResponse({"ok": True, "avarias_por_lote": avarias})


def api_listar_avarias_fornecedor(request: HttpRequest) -> JsonResponse:
    """Retorna o AD_QTDAVARIA atual de cada item de uma nota.

    Usado pelo frontend da Entrada pra preencher a coluna 'Avaria forn.'
    do modal de itens — evita alterar a query existente
    ``listar_itens_por_nota`` (Cat B) com SELECT extra.

    Payload de resposta:
        {"ok": true, "avarias": {sequencia: ad_qtdavaria, ...}}

    Mai/2026 (2026-05-19).
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)

    nunota = _converter_para_inteiro(request.GET.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)

    avarias = consultar_avarias_fornecedor_da_nota(nunota) or {}
    # JSON exige chaves string — converte sequencia (int) pra string
    payload = {str(seq): float(val) for seq, val in avarias.items()}
    return JsonResponse({"ok": True, "avarias": payload})


def api_avaria_fornecedor_naoclass(request: HttpRequest) -> JsonResponse:
    """Registra avaria do fornecedor em item NÃO-classificável da Entrada (TOP 11).

    Endpoint dedicado pra escapar da trava de edição da TOP 11 (que bloqueia
    qualquer UPDATE quando já existe TOP 13/26 com o lote). Avaria do
    fornecedor pode ser registrada depois — operador descobre quando faturando.

    Payload esperado:
        {"nunota": int, "sequencia": int, "qtd_avaria": float}

    Mai/2026 (2026-05-19).
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)

    payload = _get_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota = _converter_para_inteiro(payload.get('nunota'))
    seq    = _converter_para_inteiro(payload.get('sequencia'))
    qtd    = payload.get('qtd_avaria')

    if not nunota or not seq:
        return JsonResponse(
            {"ok": False, "error": "nunota e sequencia são obrigatórios"},
            status=400,
        )

    codusu  = request.session.get('codusu')
    nomeusu = request.session.get('nomeusu') or 'desconhecido'

    try:
        res = atualizar_avaria_fornecedor_naoclass(
            nunota=nunota,
            sequencia=seq,
            qtd_avaria=qtd,
            codusu=codusu,
            nomeusu=nomeusu,
        )
    except Exception as exc:
        logger.exception("Falha em api_avaria_fornecedor_naoclass")
        return JsonResponse(
            {"ok": False, "error": humanizar_erro_oracle(exc)},
            status=500,
        )

    return JsonResponse(res, status=200 if res.get('ok') else 400)


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
            # Snapshot ANTES — captura CODTIPOPER e STATUSNOTA pré-UPDATE
            snapshot_antes = None
            try:
                cur.execute("""
                    SELECT CODTIPOPER, STATUSNOTA, DTFATUR
                    FROM TGFCAB WHERE NUNOTA = :n
                """, n=nunota)
                rsnap = cur.fetchone()
                if rsnap:
                    snapshot_antes = {
                        'NUNOTA':     nunota,
                        'CODTIPOPER': int(rsnap[0]) if rsnap[0] is not None else None,
                        'STATUSNOTA': rsnap[1],
                        'DTFATUR':    rsnap[2].strftime('%Y-%m-%d') if rsnap[2] else None,
                    }
            except Exception:
                logger.warning("Falha snapshot ANTES de finalizar NUNOTA=%s", nunota)

            cur.execute("""
                UPDATE TGFCAB
                SET DTFATUR = SYSDATE, STATUSNOTA = 'L', DTALTER = SYSDATE
                WHERE NUNOTA = :nunota
            """, nunota=nunota)

            linhas_afetadas = cur.rowcount
            conn.commit()

            mod = 'classificacao' if (snapshot_antes and snapshot_antes.get('CODTIPOPER') == 26) else 'entrada'
            registrar_auditoria(
                modulo=mod,
                operacao='FINALIZAR_NOTA',
                tabela_alvo='TGFCAB',
                registro_id=nunota,
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_antes=snapshot_antes,
                snapshot_depois={
                    'NUNOTA':     nunota,
                    'STATUSNOTA': 'L',
                    'DTFATUR':    'SYSDATE',
                },
                observacao='Nota carimbada como finalizada (STATUSNOTA=L)',
            )
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

    # Snapshot ANTES (best-effort) — cabeçalho + lista de itens
    snapshot_antes = None
    try:
        with obter_conexao_oracle() as conn_snap:
            cur = conn_snap.cursor()
            cur.execute("""
                SELECT CODTIPOPER, CODEMP, CODPARC, DTNEG, NUMNOTA
                FROM TGFCAB WHERE NUNOTA = :n
            """, n=nunota)
            r = cur.fetchone()
            if r:
                snapshot_antes = {
                    'NUNOTA':     nunota,
                    'CODTIPOPER': int(r[0]) if r[0] is not None else None,
                    'CODEMP':     int(r[1]) if r[1] is not None else None,
                    'CODPARC':    int(r[2]) if r[2] is not None else None,
                    'DTNEG':      r[3].strftime('%Y-%m-%d') if r[3] else None,
                    'NUMNOTA':    int(r[4]) if r[4] is not None else None,
                    'ITENS':      [],
                }
                cur.execute("""
                    SELECT SEQUENCIA, CODPROD, QTDNEG, PESO, CODVOL, CODAGREGACAO
                    FROM TGFITE WHERE NUNOTA = :n ORDER BY SEQUENCIA
                """, n=nunota)
                for it in cur.fetchall():
                    snapshot_antes['ITENS'].append({
                        'SEQUENCIA':    int(it[0]),
                        'CODPROD':      int(it[1]) if it[1] is not None else None,
                        'QTDNEG':       float(it[2]) if it[2] is not None else None,
                        'PESO':         float(it[3]) if it[3] is not None else None,
                        'CODVOL':       it[4],
                        'CODAGREGACAO': it[5],
                    })
    except Exception:
        logger.warning("Falha snapshot ANTES de excluir nota compra NUNOTA=%s", nunota)

    resposta = excluir_nota_completa_banco(nunota, simulacao=False)
    if resposta.get('ok'):
        mod = 'classificacao' if (snapshot_antes and snapshot_antes.get('CODTIPOPER') == 26) else 'entrada'
        registrar_auditoria(
            modulo=mod,
            operacao='EXCLUIR_NOTA_COMPRA',
            tabela_alvo='TGFCAB',
            registro_id=nunota,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes=snapshot_antes,
            observacao='Nota de compra excluída (cabeçalho + itens)',
        )
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

    if not lote or not ORACLE_DISPONIVEL:
        return JsonResponse({"ok": False, "error": "Lote não informado ou conexão Oracle inativa"}, status=400)

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Recupera o NUNOTA de origem (TOP 11 — compra/fornecedor).
            # Mesmo se o JS enviar, validamos que é TOP 11; senão recalculamos
            # — TGFITE de outras TOPs (13/35/37) também tem GERAPRODUCAO='S'
            # (campo copiado no INSERT), e MAX(NUNOTA) pega o mais recente
            # (geralmente venda), trazendo CLIENTE em vez de FORNECEDOR.
            cur.execute(
                """
                SELECT MAX(c.NUNOTA)
                  FROM TGFITE i
                  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                 WHERE i.CODAGREGACAO = :l
                   AND c.CODTIPOPER = 11
                   AND c.STATUSNOTA <> 'E'
                """,
                l=lote,
            )
            res = cur.fetchone()
            if not res or not res[0]:
                return JsonResponse({"ok": False, "error": "Origem do lote (TOP 11) não encontrada no Sankhya"}, status=404)
            nunota_origem = int(res[0])

            # 2. Busca dados de massa e balanço (Reaproveitando sua regra de negócio homologada)
            dados_massa = obter_detalhes_lote_completo(nunota_origem, lote)

            # 3. Metadados extras para o Cabeçalho do Modal (Fornecedor, Data, Produto).
            # Força CODTIPOPER = 11 — garante que o NOMEPARC mostrado seja o
            # FORNECEDOR de compra (ex: JOSE MARIA), nunca o CLIENTE da venda
            # (ex: ASSAI ASA NORTE) caso o lote já tenha sido vendido.
            cur.execute("""
                SELECT p.NOMEPARC, c.DTNEG, pr.DESCRPROD, c.CODPARC
                FROM TGFCAB c
                JOIN TGFPAR p ON c.CODPARC = p.CODPARC
                JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                JOIN TGFPRO pr ON i.CODPROD = pr.CODPROD
                WHERE c.NUNOTA = :n
                  AND i.CODAGREGACAO = :l
                  AND c.CODTIPOPER = 11
                  AND ROWNUM = 1
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

            # Checagem do módulo Comercial — bloqueia Classificação apenas se
            # existe item do lote em vale TOP 13 (qualquer estado de TGFCAB).
            # Vendas (TOP 35/37) NÃO bloqueiam. Pra destravar, Comercial usa
            # `zerar_negociacao_banco` que DELETE os itens TGFITE do lote
            # — então a contagem zera naturalmente.
            cur.execute("""
                SELECT COUNT(1) FROM TGFCAB c
                JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                WHERE c.CODTIPOPER = 13 AND i.CODAGREGACAO = :l
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

            # 1. Busca o NUNOTA e o descarte atual da TOP 11 (origem real do lote).
            # CODTIPOPER=11 obrigatório — GERAPRODUCAO='S' é copiado pras TGFITE
            # de TOPs filhas (13, 26, etc) no fluxo do lote; sem filtro de TOP,
            # fetchone() pode trazer linha errada e AD_QTDAVARIA atualizado fica
            # no lugar incorreto, mantendo o descarte da TOP 11 intacto. (Mai/2026)
            cur.execute("""
                SELECT c.NUNOTA, NVL(i.AD_QTDAVARIA, 0)
                  FROM TGFITE i
                  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                 WHERE i.CODAGREGACAO = :l
                   AND i.GERAPRODUCAO = 'S'
                   AND c.CODTIPOPER   = 11
                   AND c.STATUSNOTA  <> 'E'
            """, {'l': lote})
            res = cur.fetchone()

            if not res:
                return JsonResponse({"ok": False, "error": f"Lote {lote} não encontrado no Sankhya (TOP 11 origem)"}, status=404)

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

            # Snapshot ANTES — PENDENTE atual + lotes agregados
            snapshot_antes = None
            try:
                cur.execute("SELECT PENDENTE FROM TGFCAB WHERE NUNOTA = :n", n=nunota_class)
                rsnap = cur.fetchone()
                if rsnap:
                    snapshot_antes = {
                        'NUNOTA':   int(nunota_class),
                        'PENDENTE': rsnap[0],
                    }
            except Exception:
                logger.warning("Falha snapshot ANTES de toggle classificação NUNOTA=%s", nunota_class)

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

        registrar_auditoria(
            modulo='classificacao',
            operacao='TOGGLE_PENDENTE',
            tabela_alvo='TGFCAB',
            registro_id=int(nunota_class),
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes=snapshot_antes,
            snapshot_depois={
                'NUNOTA':         int(nunota_class),
                'PENDENTE':       status_pendente,
                'LOTES_AFETADOS': lotes_afetados,
            },
            observacao=(
                f"Classificação marcada como '{'pendente' if status_pendente == 'S' else 'concluída'}' "
                f"({len(lotes_afetados)} lote(s) afetado(s))"
            ),
        )
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

        if resultado.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='SALVAR_VALE',
                tabela_alvo='TGFCAB',
                registro_id=resultado.get('nunota_13') or resultado.get('nunota'),
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_depois={
                    'NUNOTA_13':      resultado.get('nunota_13'),
                    'NUNOTA_ORIGEM':  payload.get('nunota_origem'),
                    'LOTE':           payload.get('lote'),
                    'QTD_EXTRA':      payload.get('qtd_extra'),
                    'QTD_MEDIO':      payload.get('qtd_medio'),
                    'QTD_DESCARTE':   payload.get('qtd_descarte'),
                    'PRECO_EXTRA':    payload.get('preco_extra'),
                    'PRECO_MEDIO':    payload.get('preco_medio'),
                    'CODPARC':        payload.get('codparc'),
                },
                observacao='Vale TOP 13 gerado a partir da Classificação',
            )

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
        if resultado.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='ZERAR_NEGOCIACAO',
                tabela_alvo='TGFCAB',
                registro_id=f"{nunota}/{lote}",
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_antes={
                    'NUNOTA_ORIGEM': nunota,
                    'LOTE':          lote,
                },
                observacao='Negociação zerada — desfaz o faturamento do vale TOP 13',
            )
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

        if res.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='SALVAR_SIMULACAO',
                tabela_alvo='TGFITE',
                registro_id=f"{nunota}/{lote}",
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_depois={
                    'NUNOTA':   nunota,
                    'LOTE':     lote,
                    'SIM_DATA': sim_data,
                },
                observacao='Simulação comercial salva no item',
            )
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
            if resultado.get('ok'):
                registrar_auditoria(
                    modulo='classificacao',
                    operacao='DESMEMBRAR_PEDIDO',
                    tabela_alvo='TGFCAB',
                    registro_id=f"{nunota_origem}/{lote}",
                    codusu=request.session.get('codusu'),
                    nomeusu=request.session.get('nomeusu'),
                    snapshot_antes={
                        'NUNOTA_ORIGEM': int(nunota_origem),
                        'LOTE':          lote,
                    },
                    snapshot_depois={
                        'NUNOTA_ORIGEM':   int(nunota_origem),
                        'LOTE':            lote,
                        'NUNOTA_NOVO':     resultado.get('nunota_novo') or resultado.get('nunota_destino'),
                    },
                    observacao='Lote desmembrado em novo pedido TOP 11',
                )
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
            if resultado.get('ok'):
                registrar_auditoria(
                    modulo='classificacao',
                    operacao='UNIFICAR_PEDIDO',
                    tabela_alvo='TGFCAB',
                    registro_id=f"{nunota_origem}->{nunota_destino}",
                    codusu=request.session.get('codusu'),
                    nomeusu=request.session.get('nomeusu'),
                    snapshot_antes={
                        'NUNOTA_ORIGEM':  int(nunota_origem),
                        'LOTE':           lote,
                        'NUNOTA_DESTINO': int(nunota_destino),
                    },
                    snapshot_depois={
                        'NUNOTA_DESTINO': int(nunota_destino),
                        'LOTE':           lote,
                    },
                    observacao=f"Lote {lote} unificado do pedido {nunota_origem} para {nunota_destino}",
                )
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
# ROTA 1.5 (Mai/2026): Vendas DO LOTE selecionado (não mais "do produto")
# Alimenta lista lateral + sparkline de evolução de preço no card Margem.
# Função sucessora de consultar_lista_ultimas_vendas — filtra por CODAGREGACAO
# em vez de extrair CODPROD do lote e filtrar por produto.
# ==============================================================================
@require_http_methods(["GET"])
def api_vendas_do_lote(request: HttpRequest) -> JsonResponse:
    """Retorna todas as vendas faturadas (TOP 34/35/37 STATUSNOTA='L') que
    consumiram o lote informado, com dedup pedido↔nota."""
    lote = (request.GET.get('lote') or '').strip()
    if not lote:
        return JsonResponse({"ok": False, "error": "Lote não informado"}, status=400)

    from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
    dados = consultar_vendas_do_lote(lote)
    return JsonResponse(dados)


# ==============================================================================
# ROTA 1.6 (Mai/2026 — 2026-05-17): Margem do lote (card "Margem Lote")
# Cálculo: (RECEITA_BRUTA − DEVOLUÇÃO − CUSTO) / RECEITA_LIQUIDA × 100.
# Avaria interna não duplica (custo já pago integralmente no vale TOP 13) —
# devolvida no payload como informativa pro tooltip.
# ==============================================================================
@require_http_methods(["GET"])
def api_margem_lote(request: HttpRequest) -> JsonResponse:
    """Devolve a margem realizada/provisória do lote pra preencher card."""
    lote = (request.GET.get('lote') or '').strip()
    if not lote:
        return JsonResponse({"ok": False, "error": "Lote não informado"}, status=400)

    from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
    dados = consultar_margem_do_lote(lote)
    return JsonResponse({"ok": True, **dados})


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

        # Mai/2026 (2026-05-20) — lotes que o operador marcou pra absorver avaria.
        # Backend reconcilia TGFCAB TOP 30 (cria/remove conforme presença). Backward
        # compat: se vier None ou ausente, backend não toca em TOP 30.
        lotes_absorver_avaria = payload.get('lotes_absorver_avaria')
        if lotes_absorver_avaria is not None and not isinstance(lotes_absorver_avaria, list):
            lotes_absorver_avaria = None

        logger.debug("Faturando NUNOTA %s | Líquido: %s | Bruto: %s | LotesAbsorver: %s",
                     nunota_13, vlr_forcar_liquido, vlr_forcar_bruto, lotes_absorver_avaria)

        from sankhya_integration.services.oracle_conn import gerar_financeiro_banco
        res = gerar_financeiro_banco(
            nunota_13, inss, historico, vlrinss,
            vlr_forcar_liquido, vlr_forcar_bruto,
            lotes_absorver_avaria=lotes_absorver_avaria,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
        )

        if res.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='GERAR_FINANCEIRO',
                tabela_alvo='TGFFIN',
                registro_id=nunota_13,
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_depois={
                    'NUNOTA_13':           nunota_13,
                    'NUFIN':               res.get('nufin'),
                    'QTDE_FIN':            res.get('qtde_fin'),
                    'VLR_TOTAL_FIN':       res.get('vlr_total'),
                    'DESCONTAR_INSS':      inss,
                    'VLRINSS':             vlrinss,
                    'VLR_FORCAR_LIQUIDO':  vlr_forcar_liquido,
                    'VLR_FORCAR_BRUTO':    vlr_forcar_bruto,
                    'HISTORICO':           historico,
                },
                observacao='Vale faturado — TGFFIN gerado',
            )
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@require_http_methods(["POST"])
def api_atualizar_preco_modalFaturamento(request):
    try:
        data = json.loads(request.body)
        from sankhya_integration.services.oracle_conn import upsert_preco_in_natura_modalFaturamento

        nunota_origem = int(data['nunota_origem'])
        nunota_13 = int(data.get('nunota_13', 0))
        codprod = int(data['codprod'])
        novo_preco = float(data['preco'])
        res = upsert_preco_in_natura_modalFaturamento(
            nunota_origem=nunota_origem,
            nunota_13=nunota_13,
            codprod=codprod,
            novo_preco=novo_preco,
        )
        if res.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='ATUALIZAR_PRECO_VALE',
                tabela_alvo='TGFITE',
                registro_id=f"{nunota_13}/{codprod}" if nunota_13 else f"{nunota_origem}/{codprod}",
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_depois={
                    'NUNOTA_ORIGEM': nunota_origem,
                    'NUNOTA_13':     nunota_13,
                    'CODPROD':       codprod,
                    'NOVO_PRECO':    novo_preco,
                },
                observacao='Preço in-natura atualizado no modal de faturamento',
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
        if res.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='ATUALIZAR_INSS_VALE',
                tabela_alvo='TGFCAB',
                registro_id=nunota_13,
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_depois={
                    'NUNOTA_13': nunota_13,
                    'VLROUTROS': valor,
                },
                observacao=f'Desconto INSS atualizado para R$ {valor:.2f}',
            )
        return JsonResponse(res)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@require_http_methods(["POST"])
def api_desfaturar_vale(request):
    try:
        payload = json.loads(request.body)
        nunota_13 = int(payload.get('nunota_13'))
        from sankhya_integration.services.oracle_conn import desfaturar_comercial_banco
        res = desfaturar_comercial_banco(nunota_13)
        if res.get('ok'):
            registrar_auditoria(
                modulo='comercial',
                operacao='DESFATURAR_VALE',
                tabela_alvo='TGFFIN',
                registro_id=nunota_13,
                codusu=request.session.get('codusu'),
                nomeusu=request.session.get('nomeusu'),
                snapshot_antes={
                    'NUNOTA_13':   nunota_13,
                    'STATUSNOTA':  'L',
                },
                snapshot_depois={
                    'NUNOTA_13':   nunota_13,
                    'STATUSNOTA':  None,
                    'NUFIN_REMOVIDOS': res.get('nufin_removidos') or res.get('removidos'),
                },
                observacao='Reversão de faturamento — vale volta a estar em aberto',
            )
        return JsonResponse(res)
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
            obs_raw = r[8] if len(r) > 8 else None
            if obs_raw is not None and hasattr(obs_raw, 'read'):
                try:
                    obs_raw = obs_raw.read()
                except Exception:
                    obs_raw = ''
            vendas.append({
                "nunota": r[0],
                "top": r[1],
                "data": r[2].strftime('%d/%m/%Y') if r[2] else "",
                "parceiro": r[3] or "", # NOMEPARC
                "total": float(r[4] or 0),
                "status_lote": r[5],
                "numnota": r[6] or "", # Nº Nota
                "emp": r[7],           # CODEMP
                "observacao": (obs_raw or '').strip() if isinstance(obs_raw, str) else (obs_raw or ''),
                # B5 Mai/2026 — frontend usa pra habilitar botão CONFIRMAR
                "statusnota": r[9] if len(r) > 9 else None,
            })
        return JsonResponse({"ok": True, "vendas": vendas})
    except Exception as e:
        logger.exception("Erro em api_listar_vendas")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_preco_tabela(request: HttpRequest) -> JsonResponse:
    """Resolve preço de venda da tabela de preços do Sankhya
    (Mai/2026 — 2026-05-20).

    Regra: TGFPAR.CODTAB → TGFTAB.NUTAB ativa (MAX DTVIGOR ≤ dtneg) →
    TGFEXC.VLRVENDA. Detalhes em `.claude/tabela_precos_sankhya.md`.

    Query string:
        codparc (obrigatório) — int
        codprod (obrigatório) — int
        dtneg   (opcional)    — DD/MM/AAAA (default SYSDATE)

    Response:
        { ok: True, preco: float|null, nutab: int|null,
          codtab: int, origem: 'TABELA_CLIENTE'|'FALLBACK'|'SEM_PRECO'|'SEM_TABELA' }
    """
    try:
        codparc = _converter_para_inteiro(request.GET.get('codparc'))
        codprod = _converter_para_inteiro(request.GET.get('codprod'))
        if not codparc or not codprod:
            return JsonResponse({'ok': False, 'error': 'codparc e codprod obrigatórios.'}, status=400)

        dtneg_raw = request.GET.get('dtneg')
        dtneg = _data_br_para_iso(dtneg_raw) if dtneg_raw else None

        dados = consultar_preco_tabela(codparc, codprod, dtneg=dtneg)
        return JsonResponse(dados, status=200)
    except Exception as exc:
        logger.exception("Falha em api_preco_tabela")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(exc), 'preco': None},
            status=500,
        )


# ─────────────────────────────────────────────────────────────────────────────
# PROMOÇÕES (Mai/2026 — 2026-05-20)
# Cadastro por (parceiro × produto) + registro de origem do preço.
# ─────────────────────────────────────────────────────────────────────────────

@exige_grupo('venda')
@ensure_csrf_cookie
def view_tabela_precos(request: HttpRequest) -> HttpResponse:
    """Renderiza a tela de Tabela de Preços (visualização leitura — Mai/2026 — 2026-05-21)."""
    return render(request, 'sankhya_integration/tabela_precos.html', {
        'nome_usuario': request.session.get('nomeusu', 'Usuário'),
    })


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_tabela_precos(request: HttpRequest) -> JsonResponse:
    """Lista preços vigentes de um CODTAB (TGFEXC.VLRVENDA + flag de promoção).

    Query string:
        codtab (obrigatório) — int
        q      (opcional)    — busca em DESCRPROD
    """
    try:
        codtab = _converter_para_inteiro(request.GET.get('codtab'))
        if not codtab:
            return JsonResponse({'ok': False, 'error': 'codtab obrigatório.'}, status=400)
        filtros = {'q': request.GET.get('q') or None}
        return JsonResponse(listar_precos_da_tabela(codtab, filtros), status=200)
    except Exception as exc:
        logger.exception("Falha em api_tabela_precos")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc), 'precos': []}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_promocoes_vigentes(request: HttpRequest) -> JsonResponse:
    """Lista promoções vigentes pro par (codparc, codprod)."""
    try:
        codparc = _converter_para_inteiro(request.GET.get('codparc'))
        codprod = _converter_para_inteiro(request.GET.get('codprod'))
        if not codparc or not codprod:
            return JsonResponse({'ok': False, 'error': 'codparc e codprod obrigatórios.'}, status=400)

        dtneg_raw = request.GET.get('dtneg')
        dtneg = _data_br_para_iso(dtneg_raw) if dtneg_raw else None

        dados = consultar_promocoes_vigentes(codparc, codprod, dtneg=dtneg)
        return JsonResponse(dados, status=200)
    except Exception as exc:
        logger.exception("Falha em api_promocoes_vigentes")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc), 'promocoes': []}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_promocoes_listar(request: HttpRequest) -> JsonResponse:
    """Lista promoções pra tela de cadastro (com paginação + filtros)."""
    try:
        filtros = {
            'codtab':  _converter_para_inteiro(request.GET.get('codtab')),
            'codparc': _converter_para_inteiro(request.GET.get('codparc')),
            'codprod': _converter_para_inteiro(request.GET.get('codprod')),
            'ativo':   request.GET.get('ativo') or None,
            'escopo':  request.GET.get('escopo') or None,
            'q':       request.GET.get('q') or None,
            'dt_referencia': request.GET.get('dt_referencia') or None,
        }
        limite = max(1, min(int(request.GET.get('limit', 100)), 500))
        offset = max(0, int(request.GET.get('offset', 0)))
        return JsonResponse(listar_promocoes_cadastradas(filtros, limite, offset), status=200)
    except Exception as exc:
        logger.exception("Falha em api_promocoes_listar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc), 'promocoes': []}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_tabelas_grupos(request: HttpRequest) -> JsonResponse:
    """Lista CODTABs do TGFTAB + contagem de TGFPAR + amostra de nomes (Mai/2026 — 2026-05-21).

    Usado no select da tela de promoção pra escolher grupo (Assaí DF / Palmas /
    Araguaína / Economart / Exal / etc). Grupo é definido pelo `TGFPAR.CODTAB`
    — clientes que compartilham CODTAB formam um grupo automático.
    """
    try:
        incluir_inativas = (request.GET.get('incluir_inativas') or 'false').lower() == 'true'
        return JsonResponse(listar_tabelas_grupos(incluir_inativas), status=200)
    except Exception as exc:
        logger.exception("Falha em api_tabelas_grupos")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc), 'tabelas': []}, status=500)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_origem_preco_item(request: HttpRequest) -> JsonResponse:
    """Lê origem registrada do preço de um item (NUNOTA, SEQUENCIA)."""
    try:
        nunota    = _converter_para_inteiro(request.GET.get('nunota'))
        sequencia = _converter_para_inteiro(request.GET.get('sequencia'))
        if not nunota or not sequencia:
            return JsonResponse({'ok': False, 'error': 'nunota e sequencia obrigatórios.'}, status=400)
        return JsonResponse(consultar_origem_preco_item(nunota, sequencia), status=200)
    except Exception as exc:
        logger.exception("Falha em api_origem_preco_item")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_promocao_criar(request: HttpRequest) -> JsonResponse:
    """Cria uma nova promoção (Cat B)."""
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    if not verificar_permissao_escrita():
        return JsonResponse({'ok': False, 'error': 'Escrita desabilitada'}, status=403)

    res = criar_promocao_banco(
        dados_json,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu') or '',
    )
    return JsonResponse(res, status=200 if res.get('ok') else 400)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_promocao_editar(request: HttpRequest) -> JsonResponse:
    """Edita uma promoção existente (Cat B)."""
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    if not verificar_permissao_escrita():
        return JsonResponse({'ok': False, 'error': 'Escrita desabilitada'}, status=403)

    promocao_id = _converter_para_inteiro(dados_json.get('id'))
    if not promocao_id:
        return JsonResponse({'ok': False, 'error': 'ID obrigatório'}, status=400)

    res = editar_promocao_banco(
        promocao_id, dados_json,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu') or '',
    )
    return JsonResponse(res, status=200 if res.get('ok') else 400)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_promocao_excluir(request: HttpRequest) -> JsonResponse:
    """Exclui uma promoção (Cat B, DELETE físico)."""
    dados_json = _get_json_payload(request)
    if not dados_json:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    if not verificar_permissao_escrita():
        return JsonResponse({'ok': False, 'error': 'Escrita desabilitada'}, status=403)

    promocao_id = _converter_para_inteiro(dados_json.get('id'))
    if not promocao_id:
        return JsonResponse({'ok': False, 'error': 'ID obrigatório'}, status=400)

    res = excluir_promocao_banco(
        promocao_id,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu') or '',
    )
    return JsonResponse(res, status=200 if res.get('ok') else 400)


@exige_grupo('venda')
@ensure_csrf_cookie
def view_promocoes(request: HttpRequest) -> HttpResponse:
    """Renderiza a tela de cadastro de promoções."""
    contexto = {
        'nome_usuario': request.session.get('nomeusu', 'Usuário'),
        'write_enabled': verificar_permissao_escrita(),
    }
    return render(request, 'sankhya_integration/promocoes.html', contexto)


# ─────────────────────────────────────────────────────────────────────────────


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

    nunota_novo = plano.get('nunota')
    registrar_auditoria(
        modulo='venda',
        operacao='CRIAR_PEDIDO',
        tabela_alvo='TGFCAB',
        registro_id=nunota_novo,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_depois={
            'NUNOTA':     nunota_novo,
            'CODEMP':     payload['CODEMP'],
            'CODPARC':    payload['CODPARC'],
            'CODTIPOPER': 34,
            'CODNAT':     payload['CODNAT'],
            'CODTIPVENDA': payload['CODTIPVENDA'],
            'DTNEG':      payload['DTNEG'],
            'OBSERVACAO': payload.get('OBSERVACAO'),
        },
    )

    return JsonResponse({"ok": True, "nunota": nunota_novo}, status=200)


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

    sequencia_nova = plano.get('sequencia')
    registrar_auditoria(
        modulo='venda',
        operacao='ADICIONAR_ITEM',
        tabela_alvo='TGFITE',
        registro_id=f"{nunota}/{sequencia_nova}",
        codusu=codusu,
        nomeusu=request.session.get('nomeusu'),
        snapshot_depois={
            'NUNOTA':       nunota,
            'SEQUENCIA':    sequencia_nova,
            'CODPROD':      payload['CODPROD'],
            'QTDNEG':       payload['QTDNEG'],
            'VLRUNIT':      payload['VLRUNIT'],
            'CODVOL':       payload['CODVOL'],
            'CODAGREGACAO': payload.get('CODAGREGACAO'),
        },
    )

    # Mai/2026 (2026-05-20) — registra origem do preço (TABELA/PROMOCAO/MANUAL)
    # Backward compat: payload sem `preco_origem` não registra (silencioso).
    preco_origem = (dados_json.get('preco_origem') or '').strip().upper() or None
    if preco_origem:
        try:
            registrar_origem_preco_item(
                nunota=nunota, sequencia=sequencia_nova,
                origem=preco_origem,
                nutab=dados_json.get('nutab'),
                promocao_id=dados_json.get('promocao_id'),
                observacao=dados_json.get('observacao_preco'),
                codusu=codusu,
            )
        except Exception:
            logger.exception('Falha ao registrar origem do preço')

    resposta = {"ok": True, "sequencia": sequencia_nova}
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

    # Snapshot ANTES (cabeçalho + lista de itens). Coleta best-effort.
    snapshot_antes = None
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT CODTIPOPER, CODEMP, CODPARC, CODTIPVENDA, DTNEG, OBSERVACAO,
                       VLRNOTA, QTDVOL
                FROM TGFCAB WHERE NUNOTA = :n
            """, n=nunota)
            row = cur.fetchone()
            if row:
                snapshot_antes = {
                    'NUNOTA':      nunota,
                    'CODTIPOPER':  int(row[0]) if row[0] is not None else None,
                    'CODEMP':      int(row[1]) if row[1] is not None else None,
                    'CODPARC':     int(row[2]) if row[2] is not None else None,
                    'CODTIPVENDA': int(row[3]) if row[3] is not None else None,
                    'DTNEG':       row[4].strftime('%Y-%m-%d') if row[4] else None,
                    'OBSERVACAO':  row[5],
                    'VLRNOTA':     float(row[6]) if row[6] is not None else None,
                    'QTDVOL':      float(row[7]) if row[7] is not None else None,
                    'ITENS':       [],
                }
                cur.execute("""
                    SELECT SEQUENCIA, CODPROD, QTDNEG, VLRUNIT, CODVOL, CODAGREGACAO
                    FROM TGFITE WHERE NUNOTA = :n ORDER BY SEQUENCIA
                """, n=nunota)
                for r in cur.fetchall():
                    snapshot_antes['ITENS'].append({
                        'SEQUENCIA':    int(r[0]) if r[0] is not None else None,
                        'CODPROD':      int(r[1]) if r[1] is not None else None,
                        'QTDNEG':       float(r[2]) if r[2] is not None else None,
                        'VLRUNIT':      float(r[3]) if r[3] is not None else None,
                        'CODVOL':       r[4],
                        'CODAGREGACAO': r[5],
                    })
    except Exception as e:
        logger.exception("Erro ao consultar TOP/snapshot do pedido para exclusão")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not snapshot_antes:
        return JsonResponse({"ok": False, "error": "Pedido não encontrado"}, status=404)
    if snapshot_antes['CODTIPOPER'] != 34:
        return JsonResponse(
            {"ok": False, "error": f"Operação permitida apenas para TOP 34 (esta é {snapshot_antes['CODTIPOPER']})"},
            status=403,
        )

    resposta = excluir_nota_completa_banco(nunota, simulacao=False)
    if not resposta.get('ok') and resposta.get('errors'):
        resposta['error'] = humanizar_erro_oracle('; '.join(resposta['errors']))
    else:
        registrar_auditoria(
            modulo='venda',
            operacao='EXCLUIR_PEDIDO',
            tabela_alvo='TGFCAB',
            registro_id=nunota,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes=snapshot_antes,
        )
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

    # Snapshot ANTES (para auditoria) — captura o estado pré-UPDATE
    snapshot_antes = None
    try:
        linha_antes = consultar_cabecalho_venda_oracle(nunota)
        if linha_antes:
            ce, ne, cp, np_, ctp, dtp, dtn, obs_ = linha_antes
            snapshot_antes = {
                'NUNOTA':      nunota,
                'CODEMP':      int(ce) if ce is not None else None,
                'CODPARC':     int(cp) if cp is not None else None,
                'CODTIPVENDA': int(ctp) if ctp is not None else None,
                'DTNEG':       dtn.strftime('%Y-%m-%d') if dtn else None,
                'OBSERVACAO':  obs_ or None,
            }
    except Exception:
        # Snapshot antes é "best effort" — se falhar, audit segue sem ele
        logger.warning("Falha ao capturar snapshot ANTES de NUNOTA=%s", nunota)

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

    registrar_auditoria(
        modulo='venda',
        operacao='EDITAR_CABECALHO',
        tabela_alvo='TGFCAB',
        registro_id=nunota,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_antes=snapshot_antes,
        snapshot_depois={
            'NUNOTA':      nunota,
            'CODEMP':      payload['CODEMP'],
            'CODPARC':     payload['CODPARC'],
            'CODTIPVENDA': payload['CODTIPVENDA'],
            'DTNEG':       payload['DTNEG'],
            'OBSERVACAO':  payload.get('OBSERVACAO'),
        },
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
    # Mai/2026 (2026-05-20) — STATUSNOTA='L' em TOP 34 NÃO trava edição.
    # Sankhya nativo permite editar pedido confirmado pra impressão
    # (mostra modal "Documento já confirmado, o que deseja fazer?" e segue).
    # IAgro estava mais rígido sem justificativa — paridade restaurada.
    # NFe real (TOP 35/37) continua bloqueada pela trava de TOP acima.
    # STATUSNOTA='E' (excluída) continua bloqueada implicitamente porque
    # `recalcular_totais_nota_banco` não atualiza notas marcadas pra exclusão.

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
    # Mai/2026 (2026-05-20) — espelha QTDCONFERIDA = QTDNEG no UPDATE,
    # mesmo padrão do INSERT (inserir_item_nota_banco linha 1137 default
    # `qtdconferida or qtdneg`). Sem isso, QTDNEG é atualizado mas
    # AD_QTDCONFERIDA fica com valor antigo — `api_listar_itens_nota`
    # retorna `qtd = qtdconferida` (col r[11]) e a tabela do modal mostra
    # qtd antiga + total atualizado, parecendo bug visual.
    if 'QTDNEG' in payload:
        payload['QTDCONFERIDA'] = payload['QTDNEG']

    # Snapshot ANTES do UPDATE (best effort — se falhar, audit segue sem ele)
    snapshot_antes = None
    try:
        with obter_conexao_oracle() as conn_snap:
            cur = conn_snap.cursor()
            cur.execute("""
                SELECT CODPROD, QTDNEG, VLRUNIT, CODVOL, CODAGREGACAO, OBSERVACAO
                FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s
            """, n=nunota, s=sequencia)
            r = cur.fetchone()
            if r:
                snapshot_antes = {
                    'NUNOTA':       nunota,
                    'SEQUENCIA':    sequencia,
                    'CODPROD':      int(r[0]) if r[0] is not None else None,
                    'QTDNEG':       float(r[1]) if r[1] is not None else None,
                    'VLRUNIT':      float(r[2]) if r[2] is not None else None,
                    'CODVOL':       r[3],
                    'CODAGREGACAO': r[4],
                    'OBSERVACAO':   r[5],
                }
    except Exception:
        logger.warning("Falha snapshot ANTES item NUNOTA=%s SEQ=%s", nunota, sequencia)

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

    snapshot_depois = {'NUNOTA': nunota, 'SEQUENCIA': sequencia}
    for k in ('CODPROD','QTDNEG','VLRUNIT','CODVOL','CODAGREGACAO','OBSERVACAO'):
        if k in payload:
            snapshot_depois[k] = payload[k]
    registrar_auditoria(
        modulo='venda',
        operacao='EDITAR_ITEM',
        tabela_alvo='TGFITE',
        registro_id=f"{nunota}/{sequencia}",
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_antes=snapshot_antes,
        snapshot_depois=snapshot_depois,
    )

    # Mai/2026 (2026-05-20) — atualiza origem do preço se enviada
    preco_origem = (dados_json.get('preco_origem') or '').strip().upper() or None
    if preco_origem:
        try:
            registrar_origem_preco_item(
                nunota=nunota, sequencia=sequencia,
                origem=preco_origem,
                nutab=dados_json.get('nutab'),
                promocao_id=dados_json.get('promocao_id'),
                observacao=dados_json.get('observacao_preco'),
                codusu=request.session.get('codusu'),
            )
        except Exception:
            logger.exception('Falha ao registrar origem do preço (edit)')

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
    snapshot_antes = None
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
                # Mai/2026 (2026-05-20) — STATUSNOTA='L' em TOP 34 NÃO trava remoção.
                # Paridade com Sankhya nativo (que permite editar pedido confirmado).
                # NFe real (TOP 35/37) continua bloqueada pela trava de TOP acima.
                # Snapshot do item ANTES do DELETE (rastreabilidade do que sumiu)
                cur.execute("""
                    SELECT CODPROD, QTDNEG, VLRUNIT, CODVOL, CODAGREGACAO, OBSERVACAO
                    FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, n=nunota, s=sequencia)
                rsnap = cur.fetchone()
                if rsnap:
                    snapshot_antes = {
                        'NUNOTA':       nunota,
                        'SEQUENCIA':    sequencia,
                        'CODPROD':      int(rsnap[0]) if rsnap[0] is not None else None,
                        'QTDNEG':       float(rsnap[1]) if rsnap[1] is not None else None,
                        'VLRUNIT':      float(rsnap[2]) if rsnap[2] is not None else None,
                        'CODVOL':       rsnap[3],
                        'CODAGREGACAO': rsnap[4],
                        'OBSERVACAO':   rsnap[5],
                    }
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

    obs_audit = 'Cabeçalho deletado automaticamente (último item removido)' \
        if recalculo.get('cab_deleted') else None
    registrar_auditoria(
        modulo='venda',
        operacao='REMOVER_ITEM',
        tabela_alvo='TGFITE',
        registro_id=f"{nunota}/{sequencia}",
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_antes=snapshot_antes,
        observacao=obs_audit,
    )

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

    registrar_auditoria(
        modulo='venda',
        operacao='FATURAR_PEDIDO',
        tabela_alvo='TGFCAB',
        registro_id=nunota,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_antes={
            'NUNOTA':     nunota,
            'CODTIPOPER': 34,
            'STATUSNOTA': None,
        },
        snapshot_depois={
            'NUNOTA':     nunota,
            'CODTIPOPER': nova_top,
            'NUMNOTA':    res.get('numnota'),
            'STATUSNOTA': 'L',
        },
        observacao='Faturado com NFe' if nova_top == 35 else 'Faturado sem NFe',
    )
    return JsonResponse(res, status=200)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_confirmar_pedido_venda(request: HttpRequest) -> JsonResponse:
    """B5 (Mai/2026 — 2026-05-22): confirma pedido TOP 34 (STATUSNOTA → 'L').

    Equivalente ao botão CONFIRMAR do Sankhya nativo. Passo obrigatório
    antes do faturamento — sem CONFIRMAR, o pedido fica em estado 'P'
    (pré-nota) e o Sankhya bloqueia o atendimento.

    Payload JSON: {nunota: int}

    Validações no service: pedido existe, é TOP 34, STATUSNOTA != 'L'/'E'.
    Sem efeitos colaterais — não cria TGFFIN, não emite NFe, não move
    estoque.
    """
    payload = _get_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nunota = _converter_para_inteiro(payload.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)

    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    try:
        res = confirmar_pedido_venda_banco(
            nunota=nunota,
            codusu_logado=request.session.get('codusu'),
        )
    except Exception as e:
        logger.exception("Erro em api_confirmar_pedido_venda")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao confirmar pedido')
        return JsonResponse(res, status=400)

    registrar_auditoria(
        modulo='venda',
        operacao='CONFIRMAR_PEDIDO',
        tabela_alvo='TGFCAB',
        registro_id=nunota,
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_antes={
            'NUNOTA':     nunota,
            'STATUSNOTA': res.get('statusnota_anterior'),
        },
        snapshot_depois={
            'NUNOTA':     nunota,
            'STATUSNOTA': 'L',
        },
        observacao='Pedido confirmado (equivalente ao CONFIRMAR do Sankhya)',
    )
    return JsonResponse(res, status=200)


# ==============================================================================
# 🔄 AVARIA (TOP 30) + DEVOLUÇÃO (TOP 36) + HISTÓRICO DE LOTE — Mai/2026
# ==============================================================================

@require_http_methods(["POST"])
@exige_grupo('venda')
def api_criar_avaria(request: HttpRequest) -> JsonResponse:
    """Cria TGFCAB TOP 30 (avaria interna) + N TGFITE com lote obrigatório.

    Payload JSON — 2 modos suportados (Mai/2026 — B2):

    Modo AVULSO (lote único, default):
        codemp, codparc, codprod, codvol, qtdneg, codagregacao, vlrunit?
        → 1 TGFITE com o lote informado

    Modo "A PARTIR DE NOTA" (com SPLIT via TGFVAR inverso):
        codemp, codparc, codprod, codvol, vlrunit
        nunota_origem_nota, sequencia_nota
        lotes_avaria: [{codagregacao, qtd}, ...]
        → N TGFITE (1 por lote) validados contra os lotes do pedido origem

    Comuns: numnota_ref?, observacao?, codtipvenda? (default 11),
            dtneg? ('DD/MM/YYYY', default hoje)

    STATUSNOTA='L' direto — avaria não tem TGFVAR nem financeiro.
    Saldo do lote desconta automaticamente via view ANDRE_IAGRO_SALDO_LOTE.
    """
    payload = _get_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    try:
        res = criar_avaria_top30_banco(
            dados=payload,
            codusu_logado=request.session.get('codusu'),
        )
    except Exception as e:
        logger.exception("Erro em api_criar_avaria")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao registrar avaria')
        return JsonResponse(res, status=400)

    registrar_auditoria(
        modulo='venda',
        operacao='CRIAR_AVARIA',
        tabela_alvo='TGFCAB',
        registro_id=res.get('nunota'),
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_depois={
            'NUNOTA':       res.get('nunota'),
            'CODTIPOPER':   30,
            'CODEMP':       payload.get('codemp'),
            'CODPARC':      payload.get('codparc'),
            'CODAGREGACAO': payload.get('codagregacao'),  # modo avulso
            'CODPROD':      payload.get('codprod'),
            'QTDNEG':       payload.get('qtdneg'),        # modo avulso
            'CODVOL':       payload.get('codvol'),
            'VLRUNIT':      payload.get('vlrunit'),
            'NUMNOTA_REF':  payload.get('numnota_ref'),
            # Modo "a partir de nota" (Mai/2026 — B2)
            'NUNOTA_ORIGEM_NOTA': payload.get('nunota_origem_nota'),
            'SEQUENCIA_NOTA':     payload.get('sequencia_nota'),
            'LOTES_AVARIA':       payload.get('lotes_avaria'),
        },
        observacao=payload.get('observacao') or 'Avaria interna',
    )
    return JsonResponse(res, status=200)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_obter_nota_para_devolucao(request: HttpRequest) -> JsonResponse:
    """Carrega dados da nota origem (TOP 35/37 STATUSNOTA='L') para o modal
    de devolução montar a lista de itens com trava de qtd devolvível.

    Querystring: ?nunota=X
    """
    nunota = _converter_para_inteiro(request.GET.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "nunota obrigatório"}, status=400)

    try:
        res = consultar_nota_para_devolucao(nunota)
    except Exception as e:
        logger.exception("Erro em api_obter_nota_para_devolucao")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao carregar nota')
        return JsonResponse(res, status=400)
    return JsonResponse(res, status=200)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_lotes_de_item_nota(request: HttpRequest) -> JsonResponse:
    """Navegação inversa TGFVAR: nota TOP 35/37 → pedido TOP 34 → lotes.

    Querystring: ?nunota=X&sequencia=Y

    Resposta:
        {ok: True, lotes: [{seq_pedido, codagregacao, qtdneg_pedido,
                             qtd_atendida, nunota_pedido}], total_atendido}
        Lista vazia = sem TGFVAR par (nota órfã ou erro de fluxo).
    """
    nunota = _converter_para_inteiro(request.GET.get('nunota'))
    sequencia = _converter_para_inteiro(request.GET.get('sequencia'))
    if not nunota or not sequencia:
        return JsonResponse(
            {"ok": False, "error": "nunota e sequencia obrigatórios"},
            status=400,
        )

    try:
        res = consultar_lotes_origem_de_seq_nota(nunota, sequencia)
    except Exception as e:
        logger.exception("Erro em api_lotes_de_item_nota")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao consultar lotes origem')
        return JsonResponse(res, status=400)
    return JsonResponse(res, status=200)


@require_http_methods(["POST"])
@exige_grupo('venda')
def api_criar_devolucao(request: HttpRequest) -> JsonResponse:
    """Cria TGFCAB TOP 36 STATUSNOTA='A' + TGFITE par-a-par + TGFVAR.

    Payload JSON:
        nunota_origem: int (TOP 35/37 STATUSNOTA='L')
        itens: [{sequencia_origem, qtd_devolver, vlrunit?}]
        observacao (opcional), dtneg (opcional)

    Após criação, operador confirma a devolução no Sankhya (muda STATUSNOTA
    pra 'L', dispara financeiro reverso e abre NFe de devolução).
    """
    payload = _get_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    if not verificar_permissao_escrita():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)

    try:
        res = criar_devolucao_top36_banco(
            dados=payload,
            codusu_logado=request.session.get('codusu'),
        )
    except Exception as e:
        logger.exception("Erro em api_criar_devolucao")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao criar devolução')
        return JsonResponse(res, status=400)

    registrar_auditoria(
        modulo='venda',
        operacao='CRIAR_DEVOLUCAO',
        tabela_alvo='TGFCAB',
        registro_id=res.get('nunota'),
        codusu=request.session.get('codusu'),
        nomeusu=request.session.get('nomeusu'),
        snapshot_antes={
            'NUNOTA_ORIGEM': payload.get('nunota_origem'),
        },
        snapshot_depois={
            'NUNOTA':        res.get('nunota'),
            'CODTIPOPER':    36,
            'STATUSNOTA':    'A',
            'NUNOTA_ORIGEM': payload.get('nunota_origem'),
            'ITENS':         payload.get('itens', []),
            'DTNEG':         payload.get('dtneg'),
        },
        observacao=payload.get('observacao') or 'Devolução criada (aguarda confirmação no Sankhya)',
    )
    return JsonResponse(res, status=200)


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_historico_lote(request: HttpRequest) -> JsonResponse:
    """Timeline completa de um lote — compra → classificação → venda → devolução/avaria.

    Querystring: ?lote=CODAGREGACAO
    """
    lote = (request.GET.get('lote') or '').strip()
    if not lote:
        return JsonResponse({"ok": False, "error": "lote obrigatório"}, status=400)

    try:
        res = obter_historico_lote(lote)
    except Exception as e:
        logger.exception("Erro em api_historico_lote")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)

    if not res.get('ok'):
        res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao consultar histórico do lote')
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
        # Campo único do Rastreio (Mai/2026 — 2026-05-25): lote/produto/
        # fornecedor/NUNOTA origem num único termo.
        'q_lotes':      request.GET.get('q_lotes'),
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
        # Campo único do Rastreio (Mai/2026 — 2026-05-25): cross-filter
        # vindo de Lotes — pedido aparece se algum item dele tiver CODPROD
        # em comum com lotes que casam com o termo.
        'q_lotes':    request.GET.get('q_lotes'),
        # Toggle Pendente/Finalizado (Mai/2026 — B9): substitui Pendente/Faturado.
        # Critério passa a ser completude do rastreio (existem itens sem lote?).
        # `mostrar_faturados` ainda aceito como alias retro de `mostrar_finalizados`.
        # Default backend: pendentes=True, finalizados=False (traz pendentes
        # por default — pedido explícito do operador).
        'mostrar_pendentes':   _parse_bool_flag(request.GET.get('mostrar_pendentes'), default=True),
        'mostrar_finalizados': _parse_bool_flag(
            request.GET.get('mostrar_finalizados',
                            request.GET.get('mostrar_faturados')),
            default=False,
        ),
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
        # Audit log SQLite (legado — mantém Django Admin funcionando)
        _registrar_audit_rastreio(
            request, acao='DESVINCULAR',
            nunota=nunota, sequencia=sequencia,
            codagregacao=res.get('codagregacao_removido'),
            qtd=None,
            extra={'operacao': res.get('operacao')},
        )
        # Audit Oracle universal (B4 — Mai/2026)
        registrar_auditoria(
            modulo='rastreio',
            operacao='DESVINCULAR_LOTE',
            tabela_alvo='TGFITE',
            registro_id=f"{nunota}/{sequencia}",
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes={
                'NUNOTA':       nunota,
                'SEQUENCIA':    sequencia,
                'CODAGREGACAO': res.get('codagregacao_removido'),
            },
            snapshot_depois={
                'NUNOTA':       nunota,
                'SEQUENCIA':    sequencia,
                'CODAGREGACAO': None,
            },
            observacao=f"Operação: {res.get('operacao') or 'UPDATE'}",
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_desvincular_lote")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_zerar_fracao(request: HttpRequest) -> JsonResponse:
    """Mai/2026 (2026-05-26) — Zera fração residual de um lote criando
    TGFCAB TOP 33 (Avaria de Ajuste) automática.

    Caso de uso: pedido pediu 19 kg, operação enviou 20 kg (caixa cheia)
    e o lote ficou com 1 kg fantasma. Operador chama esse endpoint pelo
    botão "Zerar fração" do card de lote.

    Trava (defesa em profundidade): só zera quando saldo <= 1% da qtd que
    entrou no lote (TOP 11 origem). Avarias maiores devem usar fluxo TOP 30.

    Body JSON: {codprod, codagregacao}
    """
    dados = _get_json_payload(request)
    if not dados:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    codprod      = _converter_para_inteiro(dados.get('codprod'))
    codagregacao = (dados.get('codagregacao') or '').strip()

    if not codprod or not codagregacao:
        return JsonResponse(
            {"ok": False, "error": "codprod e codagregacao são obrigatórios"},
            status=400,
        )

    try:
        res = zerar_fracao_lote_banco(
            codprod=codprod,
            codagregacao=codagregacao,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu') or '',
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao zerar fração')
            return JsonResponse(res, status=400)
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_zerar_fracao")
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
    qtd          = _converter_para_float(dados.get('qtd'))         # opcional
    # Mai/2026: peso da caixa pra etiqueta — agora OPCIONAL. Se NULL, etiqueta
    # resolve em runtime via TGFITE.PESO desta linha (NULL) → DISTINCT PESO da
    # TOP 26 do mesmo lote (modal de escolha se houver 2+ embalagens).
    # Aceita alias retro `qtdfixada` (JS antigo) durante transição.
    peso         = _converter_para_float(dados.get('peso') if dados.get('peso') is not None else dados.get('qtdfixada'))

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
            peso=peso,
        )
        if not res.get('ok'):
            res['error'] = humanizar_erro_oracle(res.get('error') or 'Falha ao atribuir lote')
            return JsonResponse(res, status=400)
        # Audit log SQLite (legado)
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
        # Audit Oracle universal (B4 — Mai/2026)
        op_realizada = (res.get('operacao') or 'UPDATE').upper()
        registrar_auditoria(
            modulo='rastreio',
            operacao='ATRIBUIR_LOTE',
            tabela_alvo='TGFITE',
            registro_id=f"{nunota}/{sequencia}",
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes={
                'NUNOTA':       nunota,
                'SEQUENCIA':    sequencia,
                'CODAGREGACAO': None,
            },
            snapshot_depois={
                'NUNOTA':         nunota,
                'SEQUENCIA':      sequencia,
                'CODAGREGACAO':   codagregacao,
                'QTD_ATRIBUIDA':  res.get('qtd_atribuida') or qtd,
                'OPERACAO':       op_realizada,
                'NOVA_SEQUENCIA': res.get('nova_sequencia'),
            },
            observacao=f"SPLIT (nova SEQ={res.get('nova_sequencia')})" if op_realizada == 'SPLIT' else 'UPDATE total',
        )
        return JsonResponse(res)
    except Exception as e:
        logger.exception("Erro em api_rastreio_atribuir_lote")
        return JsonResponse({"ok": False, "error": humanizar_erro_oracle(e)}, status=500)


# ==============================================================================
# 🏷  ETIQUETAS SAFE TRACE / IAGRO (Mai/2026)
# Gera PDF 100×50mm landscape com 1 etiqueta por caixa. Operador clica
# 🖨 no header do pedido (todos os itens) ou na linha de cada produto.
# Nº de etiquetas = QTDNEG (kg) / PESO (kg por caixa), arredondado pra cima.
#
# Resolução do peso (em cascata):
#  1. Override do operador via ?pesos=seq:val,seq:val (modal de escolha)
#  2. TGFITE.PESO da própria linha (preenchido no vínculo, opcional)
#  3. PESO da TOP 26 do mesmo lote (1 só → automático; 2+ → modal escolha)
# ==============================================================================

def _parse_pesos_overrides(raw: str) -> dict[int, float]:
    """Parseia query param ?pesos=10:22,11:20 em {10: 22.0, 11: 20.0}.

    Ignora segmentos inválidos sem explodir — modal sempre envia clean,
    mas defesa em profundidade.
    """
    out: dict[int, float] = {}
    if not raw:
        return out
    for parte in raw.split(','):
        if ':' not in parte:
            continue
        seq_raw, val_raw = parte.split(':', 1)
        try:
            seq = int(seq_raw.strip())
            val = float(val_raw.strip())
            if seq > 0 and val > 0:
                out[seq] = val
        except (ValueError, TypeError):
            continue
    return out


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_resolver_peso(request: HttpRequest) -> JsonResponse:
    """Devolve quais linhas do pedido precisam de escolha de peso e os
    pesos disponíveis na TOP 26 do lote. Frontend chama ANTES de abrir o PDF.

    Query params:
        ?nunota=X (obrigatório): NUNOTA do pedido (TOP 34/35/37)
        ?codprod=Y (opcional):  limita à produto-linha

    Resposta:
      {
        'ok': True,
        'pedido_nunota': X,
        'precisa_escolha': True/False,  # alguma linha tem 2+ pesos na TOP 26?
        'itens': [
          {'sequencia', 'codprod', 'descrprod', 'qtdneg', 'codagregacao',
           'peso_proprio', 'pesos_top26', 'peso_resolvido', 'precisa_escolha'},
          ...
        ]
      }

    Se ``precisa_escolha=False`` em todos, frontend abre o PDF direto.
    Se algum True, frontend abre modal com radios pra cada SEQ ambígua.
    """
    try:
        nunota = int(request.GET.get('nunota') or 0)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'NUNOTA inválido'}, status=400)
    if nunota <= 0:
        return JsonResponse({'ok': False, 'error': 'NUNOTA obrigatório'}, status=400)

    codprod = None
    codprod_raw = request.GET.get('codprod')
    if codprod_raw:
        try:
            codprod = int(codprod_raw)
        except (TypeError, ValueError):
            codprod = None

    try:
        dados = consultar_dados_etiqueta_pedido(nunota, codprod=codprod)
    except Exception as e:
        logger.exception("Erro em api_rastreio_resolver_peso")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(e)}, status=500,
        )

    pedido = dados.get('pedido')
    itens  = dados.get('itens') or []
    if not pedido or not itens:
        return JsonResponse({
            'ok': False,
            'error': ('Nenhum item com lote vinculado neste pedido. '
                      'Vincule lotes antes de imprimir etiquetas.'),
        }, status=404)

    return JsonResponse({
        'ok': True,
        'pedido_nunota':   pedido.get('nunota'),
        'precisa_escolha': any(it.get('precisa_escolha') for it in itens),
        'itens': [
            {
                'sequencia':       it.get('sequencia'),
                'codprod':         it.get('codprod'),
                'descrprod':       it.get('descrprod'),
                'qtdneg':          it.get('qtdneg'),
                'codagregacao':    it.get('codagregacao'),
                'peso_proprio':    it.get('peso_proprio'),
                'pesos_top26':     it.get('pesos_top26'),
                'peso_resolvido':  it.get('peso_resolvido'),
                'origem_peso':     it.get('origem_peso'),
                'precisa_escolha': it.get('precisa_escolha'),
            }
            for it in itens
        ],
    })


@require_http_methods(["GET"])
@exige_grupo('rastreio')
def api_rastreio_etiqueta_pdf(request: HttpRequest):
    """Gera PDF de etiquetas de rastreabilidade de um pedido.

    Query params:
        ?nunota=X (obrigatório): NUNOTA do pedido (TOP 34/35/37)
        ?codprod=Y (opcional):  limita etiquetas a este CODPROD
        ?pesos=seq:val,...     : overrides do modal de escolha (opcional)

    Cada linha TGFITE com lote vinculado gera N páginas (N=qtd/peso). Linhas
    sem peso definido (sem PESO próprio e sem TOP 26 com peso > 0) são puladas
    silenciosamente. Se NENHUMA linha gerar etiqueta, retorna 400.

    Se alguma linha tem 2+ pesos disponíveis na TOP 26 e NÃO veio override,
    retorna 409 indicando que o frontend precisa abrir o modal de escolha.
    """
    try:
        nunota = int(request.GET.get('nunota') or 0)
    except (TypeError, ValueError):
        return JsonResponse(
            {'ok': False, 'error': 'NUNOTA inválido'}, status=400,
        )
    if nunota <= 0:
        return JsonResponse(
            {'ok': False, 'error': 'NUNOTA obrigatório'}, status=400,
        )

    codprod = None
    codprod_raw = request.GET.get('codprod')
    if codprod_raw:
        try:
            codprod = int(codprod_raw)
        except (TypeError, ValueError):
            codprod = None

    overrides = _parse_pesos_overrides(request.GET.get('pesos', ''))

    try:
        dados = consultar_dados_etiqueta_pedido(
            nunota, codprod=codprod, pesos_overrides=overrides,
        )
    except Exception as e:
        logger.exception("Erro em api_rastreio_etiqueta_pdf")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(e)}, status=500,
        )

    pedido = dados.get('pedido')
    itens  = dados.get('itens') or []
    if not pedido or not itens:
        return JsonResponse({
            'ok': False,
            'error': ('Nenhum item com lote vinculado encontrado neste pedido. '
                      'Vincule lotes antes de imprimir etiquetas.'),
        }, status=404)

    # Se alguma linha precisa de escolha sem override → frontend abre modal.
    pendentes = [it for it in itens if it.get('precisa_escolha')]
    if pendentes:
        return JsonResponse({
            'ok': False,
            'precisa_escolha': True,
            'itens_pendentes': [
                {
                    'sequencia':    it.get('sequencia'),
                    'codprod':      it.get('codprod'),
                    'descrprod':    it.get('descrprod'),
                    'qtdneg':       it.get('qtdneg'),
                    'codagregacao': it.get('codagregacao'),
                    'pesos_top26':  it.get('pesos_top26'),
                }
                for it in pendentes
            ],
            'error': ('Esse lote foi classificado em pesos diferentes. '
                      'Escolha qual peso usar antes de imprimir.'),
        }, status=409)

    # Calcula nº de cópias por linha; pula linhas sem peso resolvido
    itens_com_copias: list[tuple[dict, int]] = []
    for it in itens:
        # Adapta dict pro gerar_pdf_etiquetas (que espera 'qtdfixada')
        it_adapt = dict(it)
        it_adapt['qtdfixada'] = it.get('peso_resolvido') or 0
        n = calcular_qtd_etiquetas(it.get('qtdneg', 0), it.get('peso_resolvido', 0))
        if n > 0:
            itens_com_copias.append((it_adapt, n))

    if not itens_com_copias:
        return JsonResponse({
            'ok': False,
            'error': ('Nenhuma linha tem peso da caixa definido — sem ele '
                      'não dá pra calcular quantas etiquetas imprimir. '
                      'Verifique se o lote foi classificado (TOP 26 com peso) '
                      'ou informe o peso manualmente no vínculo.'),
        }, status=400)

    pdf_bytes = gerar_pdf_etiquetas(pedido, itens_com_copias)

    fname = f'etiquetas-pedido-{pedido.get("nunota")}'
    if codprod:
        fname += f'-prod-{codprod}'
    fname += '.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response


@require_http_methods(["POST"])
@exige_grupo('rastreio')
def api_rastreio_refresh_saldo(request: HttpRequest) -> JsonResponse:
    """Força refresh manual do AD_SALDO_LOTE_CACHE — disparado pelo botão
    Atualizar do Rastreio quando o operador precisa de dado fresco antes
    do próximo ciclo do Windows Task Scheduler (5min).

    Síncrono: bloqueia ~12s aguardando o INSERT-SELECT da view. Frontend
    deve mostrar feedback visual (spinner/banner) durante a chamada.

    Retorna o JSON do `refresh_saldo_lote_cache()`:
        {ok: bool, rows: int, duracao_s: float, error?: str}
    """
    try:
        from sankhya_integration.services.oracle_conn import refresh_saldo_lote_cache
        resultado = refresh_saldo_lote_cache()
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu')
        if resultado.get('ok'):
            logger.info(
                "[api_rastreio_refresh_saldo] manual OK rows=%d duracao=%.2fs (user=%s/%s)",
                resultado.get('rows', 0), resultado.get('duracao_s', 0), codusu, nomeusu,
            )
            return JsonResponse(resultado)
        else:
            logger.warning(
                "[api_rastreio_refresh_saldo] manual FALHOU (user=%s/%s): %s",
                codusu, nomeusu, resultado.get('error'),
            )
            return JsonResponse(resultado, status=500)
    except Exception as exc:
        logger.exception("Falha em api_rastreio_refresh_saldo")
        return JsonResponse(
            {"ok": False, "error": "Não foi possível atualizar o saldo. Tente novamente."},
            status=500,
        )


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
        registrar_auditoria(
            modulo='rastreio',
            operacao='VINCULAR_PEDIDO_NOTA',
            tabela_alvo='AD_VINCULO_PEDIDO_NOTA',
            registro_id=res.get('id'),
            codusu=int(codusu),
            nomeusu=nomeusu,
            snapshot_depois={
                'NUNOTA_PEDIDO': nunota_pedido,
                'NUNOTA_NOTA':   nunota_nota,
                'ORIGEM':        'VINCULADO',
                'VINCULO_ID':    res.get('id'),
            },
            observacao=observacao or 'Leva A — vínculo manual de pedido pré-existente',
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
        registrar_auditoria(
            modulo='rastreio',
            operacao='CRIAR_PEDIDO_RETROATIVO',
            tabela_alvo='AD_VINCULO_PEDIDO_NOTA',
            registro_id=res.get('vinculo_id'),
            codusu=int(codusu),
            nomeusu=nomeusu,
            snapshot_antes={'NUNOTA_NOTA': nunota_nota},
            snapshot_depois={
                'NUNOTA_PEDIDO_NOVO': res.get('nunota_pedido'),
                'NUNOTA_NOTA':        nunota_nota,
                'ORIGEM':             'PEDIDO_RETROATIVO',
                'VINCULO_ID':         res.get('vinculo_id'),
                'QTD_ITENS':          res.get('qtd_itens'),
            },
            observacao='Leva B — IAgro criou pedido TOP 34 retroativo a partir da nota órfã',
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
        # Audit unificado (SQLite legado)
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
        # Audit Oracle universal
        registrar_auditoria(
            modulo='rastreio',
            operacao=f'RESOLVER_NOTA_ORFA_{acao_executada}',
            tabela_alvo='AD_VINCULO_PEDIDO_NOTA',
            registro_id=res.get('vinculo_id'),
            codusu=int(codusu),
            nomeusu=nomeusu,
            snapshot_antes={'NUNOTA_NOTA': nunota_nota, 'ACAO_SOLICITADA': acao},
            snapshot_depois={
                'NUNOTA_PEDIDO':  res.get('nunota_pedido'),
                'NUNOTA_NOTA':    nunota_nota,
                'VINCULO_ID':     res.get('vinculo_id'),
                'QTD_ITENS':      res.get('qtd_itens'),
                'ACAO_EXECUTADA': acao_executada,
            },
            observacao=f"Fluxo unificado: backend decidiu '{acao_executada}' (solicitado '{acao}')",
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
        registrar_auditoria(
            modulo='rastreio',
            operacao='DESFAZER_VINCULO',
            tabela_alvo='AD_VINCULO_PEDIDO_NOTA',
            registro_id=nunota_nota or nunota_pedido,
            codusu=request.session.get('codusu'),
            nomeusu=request.session.get('nomeusu'),
            snapshot_antes={
                'NUNOTA_PEDIDO': nunota_pedido,
                'NUNOTA_NOTA':   nunota_nota,
            },
            observacao=f"DELETE em AD_VINCULO_PEDIDO_NOTA (removidos={res.get('removidos')}); AD_NUMPEDIDOORIG da nota volta a NULL",
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


# =============================================================================
# MÓDULO CONTROLE DE COMBUSTÍVEL (Mai/2026)
# TOP 10 entrada (Sankhya) + TOP 26 requisição (IAgro com STATUSNOTA NULL)
# Grupo de produto: TGFGRU.CODGRUPOPROD = 11 (IAGRO_FROTA)
# Grupo de usuário: TSIGRU.CODGRUPO = 11 (IAGRO_FROTA)
# =============================================================================

@exige_grupo('combustivel')
@ensure_csrf_cookie
def view_portal_combustivel(request: HttpRequest) -> HttpResponse:
    """Renderiza o portal do módulo Controle de Combustível."""
    return render(request, 'sankhya_integration/combustivel.html')


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_listar_estoque_combustivel(request: HttpRequest) -> JsonResponse:
    """Lista saldo dos tanques de combustível mapeados em CAPACIDADE_TANQUE.
    Retorna saldo (soma de SALDO_INICIAL_TANQUE + view), capacidade física e
    % de preenchimento pra renderizar medidor visual.
    Filtro opcional: q (busca em DESCRPROD).
    """
    try:
        filtros = {
            'q': (request.GET.get('q') or '').strip() or None,
        }
        rows = consultar_saldo_combustivel(filtros)
        itens = [{
            'codprod':        int(r[0]) if r[0] is not None else None,
            'descrprod':      r[1] or '',
            'codvol':         r[2] or '',
            'qtd_entrada':    float(r[3]) if r[3] is not None else 0.0,
            'qtd_saida':      float(r[4]) if r[4] is not None else 0.0,
            'qtd_disponivel': float(r[5]) if r[5] is not None else 0.0,
            'capacidade_lt':  float(r[6]) if r[6] is not None else 0.0,
            'saldo_inicial':  float(r[7]) if r[7] is not None else 0.0,
            'percentual':     float(r[8]) if r[8] is not None else 0.0,
            'formato':        r[9] if len(r) > 9 else 'CILINDRO_HORIZONTAL',
        } for r in rows]
        return JsonResponse({'ok': True, 'items': itens})
    except Exception as exc:
        logger.exception("Falha em api_listar_estoque_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_listar_veiculos(request: HttpRequest) -> JsonResponse:
    """Typeahead de veículos da TGFVEI. Filtros opcionais: q (texto),
    tipo (INTERNA_FROTA | INTERNA_MAQUINARIO | EXTERNA_FRETE), limit.
    """
    try:
        termo = (request.GET.get('q') or '').strip() or None
        tipo = (request.GET.get('tipo') or '').strip().upper() or None
        try: limite = int(request.GET.get('limit') or 30)
        except (TypeError, ValueError): limite = 30
        rows = consultar_veiculos_disponiveis(termo=termo, tipo=tipo, limite=limite)
        itens = [{
            'codveiculo': int(r[0]),
            'placa': r[1] or '',
            'marcamodelo': r[2] or '',
            'especietipo': r[3] or '',
            'proprio': r[4] or '',
            'combustivel': r[5] or '',
            'codparc': int(r[6]) if r[6] is not None else None,
            'nomeparc': r[7] or '',
            'codcencus': int(r[8]) if r[8] is not None else None,
            'codfunc': int(r[9]) if r[9] is not None else None,
            'codmotorista': int(r[10]) if r[10] is not None else None,
            'ativo': r[11] or '',
        } for r in rows]
        return JsonResponse({'ok': True, 'results': itens})
    except Exception as exc:
        logger.exception("Falha em api_listar_veiculos")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_listar_produtos_combustivel(request: HttpRequest) -> JsonResponse:
    """Typeahead de produtos de combustível (CODGRUPOPROD=11). Filtros: q, limit."""
    try:
        termo = (request.GET.get('q') or '').strip() or None
        try: limite = int(request.GET.get('limit') or 30)
        except (TypeError, ValueError): limite = 30
        rows = consultar_produtos_combustivel(termo=termo, limite=limite)
        itens = [{
            'codprod': int(r[0]),
            'descrprod': r[1] or '',
            'codvol': r[2] or '',
        } for r in rows]
        return JsonResponse({'ok': True, 'results': itens})
    except Exception as exc:
        logger.exception("Falha em api_listar_produtos_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_listar_movimentacoes_combustivel(request: HttpRequest) -> JsonResponse:
    """Listagem unificada: entradas (TOP 10 CODGRUPOPROD=11) + requisições
    (TOP 26 com AD_REQUISICAO_COMBUSTIVEL). Filtros: codemp, codveiculo, tipo,
    codparc, status (aberto|confirmado), date_start, date_end,
    mov (ENTRADA|REQUISICAO). Paginação: page (1-based), limit.
    """
    try:
        try: page = max(1, int(request.GET.get('page') or 1))
        except (TypeError, ValueError): page = 1
        try: limite = int(request.GET.get('limit') or 100)
        except (TypeError, ValueError): limite = 100
        offset = (page - 1) * limite

        filtros = {
            'codemp':     _converter_para_inteiro(request.GET.get('codemp')),
            'codveiculo': _converter_para_inteiro(request.GET.get('codveiculo')),
            'tipo':       (request.GET.get('tipo') or '').strip().upper() or None,
            'codparc':    _converter_para_inteiro(request.GET.get('codparc')),
            'status':     (request.GET.get('status') or '').strip().lower() or None,
            'mov':        (request.GET.get('mov') or '').strip().upper() or None,
            'date_start': request.GET.get('date_start'),
            'date_end':   request.GET.get('date_end'),
        }
        rows = listar_movimentacoes_combustivel(filtros, limite=limite, offset=offset)
        itens = [{
            'tipo_movimento': r[0],
            'nunota':         int(r[1]),
            'numnota':        int(r[2]) if r[2] is not None else None,
            'codemp':         int(r[3]) if r[3] is not None else None,
            'codparc':        int(r[4]) if r[4] is not None else None,
            'nomeparc':       r[5] or '',
            'dtneg':          r[6].strftime('%Y-%m-%d') if r[6] else None,
            'statusnota':     r[7],
            'vlrnota':        float(r[8]) if r[8] is not None else 0.0,
            'qtdvol':         float(r[9]) if r[9] is not None else 0.0,
            'requisicao': {
                'id':            int(r[10]) if r[10] is not None else None,
                'tipo':          r[11],
                'codveiculo':    int(r[12]) if r[12] is not None else None,
                'placa':         r[13] or '',
                'marcamodelo':   r[14] or '',
                'hodometro_km':  float(r[15]) if r[15] is not None else None,
                'horimetro_h':   float(r[16]) if r[16] is not None else None,
                'doc_frete_ref': r[17] or '',
            } if r[0] == 'REQUISICAO' else None,
            'sequencia':      int(r[18]) if r[18] is not None else None,
            'codprod':        int(r[19]) if r[19] is not None else None,
            'descrprod':      r[20] or '',
            'codvol':         r[21] or '',
            'qtdneg_item':    float(r[22]) if r[22] is not None else 0.0,
            'vlrtot_item':    float(r[23]) if r[23] is not None else 0.0,
        } for r in rows]
        return JsonResponse({'ok': True, 'items': itens, 'page': page, 'limit': limite})
    except Exception as exc:
        logger.exception("Falha em api_listar_movimentacoes_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_listar_requisicoes_combustivel(request: HttpRequest) -> JsonResponse:
    """Lista requisições de combustível (TOP 26 com linha em AD_REQUISICAO_COMBUSTIVEL).
    Filtros: codemp, codveiculo, tipo, codparc, status (aberto|confirmado),
    date_start, date_end. Paginação: page (1-based), limit.
    """
    try:
        try: page = max(1, int(request.GET.get('page') or 1))
        except (TypeError, ValueError): page = 1
        try: limite = int(request.GET.get('limit') or 50)
        except (TypeError, ValueError): limite = 50
        offset = (page - 1) * limite

        filtros = {
            'codemp': _converter_para_inteiro(request.GET.get('codemp')),
            'codveiculo': _converter_para_inteiro(request.GET.get('codveiculo')),
            'tipo': (request.GET.get('tipo') or '').strip().upper() or None,
            'codparc': _converter_para_inteiro(request.GET.get('codparc')),
            'status': (request.GET.get('status') or '').strip().lower() or None,
            'date_start': request.GET.get('date_start'),
            'date_end': request.GET.get('date_end'),
        }
        rows = listar_requisicoes_combustivel(filtros, limite=limite, offset=offset)
        itens = [{
            'nunota': int(r[0]),
            'numnota': int(r[1]) if r[1] is not None else None,
            'codemp': int(r[2]) if r[2] is not None else None,
            'codparc': int(r[3]) if r[3] is not None else None,
            'nomeparc': r[4] or '',
            'dtneg': r[5].strftime('%Y-%m-%d') if r[5] else None,
            'statusnota': r[6],
            'vlrnota': float(r[7]) if r[7] is not None else 0.0,
            'qtdvol': float(r[8]) if r[8] is not None else 0.0,
            'requisicao': {
                'id': int(r[9]) if r[9] is not None else None,
                'tipo': r[10],
                'codveiculo': int(r[11]) if r[11] is not None else None,
                'placa': r[12] or '',
                'marcamodelo': r[13] or '',
                'hodometro_km': float(r[14]) if r[14] is not None else None,
                'horimetro_h':  float(r[15]) if r[15] is not None else None,
                'doc_frete_ref': r[16] or '',
                'observacao': r[17] or '',
                'nomeusu': r[18] or '',
                'criado_em': r[19].strftime('%Y-%m-%d %H:%M:%S') if r[19] else None,
            },
            'codprod': int(r[20]) if r[20] is not None else None,
            'descrprod': r[21] or '',
            'codvol': r[22] or '',
            'qtdneg_total': float(r[23]) if r[23] is not None else 0.0,
        } for r in rows]
        return JsonResponse({'ok': True, 'items': itens, 'page': page, 'limit': limite})
    except Exception as exc:
        logger.exception("Falha em api_listar_requisicoes_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_obter_requisicao_combustivel(request: HttpRequest, nunota: int) -> JsonResponse:
    """Detalhe de uma requisição (cabeçalho + itens + metadata IAgro)."""
    try:
        dados = obter_requisicao_combustivel(nunota)
        if not dados:
            return JsonResponse({'ok': False, 'error': 'Requisição não encontrada.'}, status=404)

        def _fmt(d):
            if d is None: return None
            try: return d.strftime('%Y-%m-%d %H:%M:%S') if hasattr(d, 'strftime') else str(d)
            except Exception: return str(d)

        cab = dict(dados['cabecalho'])
        cab['DTNEG'] = _fmt(cab.get('DTNEG'))
        cab['DTMOV'] = _fmt(cab.get('DTMOV'))
        req = dados.get('requisicao')
        if req:
            req = dict(req)
            req['CRIADO_EM'] = _fmt(req.get('CRIADO_EM'))
        return JsonResponse({
            'ok': True,
            'cabecalho': cab,
            'itens': dados.get('itens') or [],
            'requisicao': req,
        })
    except Exception as exc:
        logger.exception("Falha em api_obter_requisicao_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_criar_requisicao_combustivel(request: HttpRequest) -> JsonResponse:
    """Cria nova requisição TOP 26 + linha em AD_REQUISICAO_COMBUSTIVEL.

    Payload:
      {
        codveiculo: int,
        codprod: int,
        qtd: float (litros),
        vlrunit: float (opcional),
        tipo: 'INTERNA_FROTA' | 'INTERNA_MAQUINARIO' | 'EXTERNA_FRETE',
        hodometro_km: float (obrigatório em INTERNA_FROTA),
        horimetro_h:  float (obrigatório em INTERNA_FROTA),
        codcencus: int,
        doc_frete_ref: str (obrigatório se tipo=EXTERNA_FRETE),
        observacao: str (opcional)
      }
    """
    try:
        payload = _get_json_payload(request) or {}
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)

        resultado = criar_requisicao_combustivel_banco(
            dados=payload, codusu=int(codusu), nomeusu=str(nomeusu)
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='CRIAR_REQUISICAO',
            tabela_alvo='AD_REQUISICAO_COMBUSTIVEL',
            registro_id=resultado.get('nunota'),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_depois={
                'NUNOTA':       resultado.get('nunota'),
                'TIPO':         payload.get('tipo'),
                'CODVEICULO':   payload.get('codveiculo'),
                'CODPROD':      payload.get('codprod'),
                'QTD':          payload.get('qtd'),
                'VLRUNIT':      payload.get('vlrunit'),
                'HODOMETRO_KM': payload.get('hodometro_km'),
                'HORIMETRO_H':  payload.get('horimetro_h'),
                'CODCENCUS':    payload.get('codcencus'),
                'DOC_FRETE_REF': payload.get('doc_frete_ref'),
            },
            observacao=payload.get('observacao'),
        )
        return JsonResponse(resultado, status=201)
    except Exception as exc:
        logger.exception("Falha em api_criar_requisicao_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_criar_abastecimento_externo(request: HttpRequest) -> JsonResponse:
    """B8 (Mai/2026) — Cria abastecimento externo (posto): TGFCAB TOP 26 STATUSNOTA='L'
    + TGFITE + AD_REQUISICAO_COMBUSTIVEL (TIPO='EXTERNA_POSTO') + TGFFIN (despesa
    contra o posto). Não desconta do saldo dos tanques internos.

    Payload:
      {
        codveiculo: int,
        codparc: int (posto: Allianz, 1=Semear, 572=Agromil),
        codprod: int (CODGRUPOPROD=200400),
        qtd: float (litros, > 0),
        vlrunit: float (> 0),
        codcencus: int,
        hodometro_km: float (obrigatório),
        horimetro_h:  float (opcional),
        doc_frete_ref: str (opcional — nº da nota fiscal/boleto),
        observacao: str (opcional),
        dtneg:  'YYYY-MM-DD' (opcional, default hoje),
        dtvenc: 'YYYY-MM-DD' (opcional, default = dtneg = à vista),
        historico: str (opcional — TGFFIN.HISTORICO)
      }
    """
    try:
        payload = _get_json_payload(request) or {}
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)

        resultado = criar_abastecimento_externo_banco(
            dados=payload, codusu=int(codusu), nomeusu=str(nomeusu)
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='CRIAR_ABASTECIMENTO_EXTERNO',
            tabela_alvo='AD_REQUISICAO_COMBUSTIVEL',
            registro_id=resultado.get('nunota'),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_depois={
                'NUNOTA':         resultado.get('nunota'),
                'TIPO':           'EXTERNA_POSTO',
                'CODVEICULO':     payload.get('codveiculo'),
                'CODPARC':        payload.get('codparc'),
                'CODPROD':        payload.get('codprod'),
                'QTD':            payload.get('qtd'),
                'VLRUNIT':        payload.get('vlrunit'),
                'ITENS':          payload.get('itens'),
                'HODOMETRO_KM':   payload.get('hodometro_km'),
                'HORIMETRO_H':    payload.get('horimetro_h'),
                'CODCENCUS':      payload.get('codcencus'),
                'DOC_FRETE_REF':  payload.get('doc_frete_ref'),
                'DTNEG':          payload.get('dtneg'),
                'DTVENC':         payload.get('dtvenc'),
                'NUFIN_GERADO':   resultado.get('nufin'),
            },
            observacao=payload.get('observacao') or 'Abastecimento em posto externo (não desconta tanque interno)',
        )
        return JsonResponse(resultado, status=201)
    except Exception as exc:
        logger.exception("Falha em api_criar_abastecimento_externo")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_editar_requisicao_combustivel(request: HttpRequest, nunota: int) -> JsonResponse:
    """Edita uma requisição em aberto (STATUSNOTA != 'L' e != 'E').

    Payload mesmo da criação (todos opcionais — campos ausentes preservam):
      codveiculo, codprod, qtd, vlrunit, tipo, codcencus,
      hodometro_km, horimetro_h, doc_frete_ref, observacao
    """
    try:
        payload = _get_json_payload(request) or {}
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)

        # Snapshot ANTES (best-effort) — captura estado pré-UPDATE
        snapshot_antes = None
        try:
            snapshot_antes = obter_requisicao_combustivel(int(nunota))
        except Exception:
            logger.warning("Falha ao capturar snapshot ANTES de requisição NUNOTA=%s", nunota)

        resultado = editar_requisicao_combustivel_banco(
            nunota=int(nunota), dados=payload,
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='EDITAR_REQUISICAO',
            tabela_alvo='AD_REQUISICAO_COMBUSTIVEL',
            registro_id=int(nunota),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_antes=snapshot_antes,
            snapshot_depois={'NUNOTA': int(nunota), **payload},
        )
        return JsonResponse(resultado, status=200)
    except Exception as exc:
        logger.exception("Falha em api_editar_requisicao_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_excluir_requisicao_combustivel(request: HttpRequest, nunota: int) -> JsonResponse:
    """Exclui logicamente uma requisição em aberto.

    Payload: {motivo: str obrigatório}
    Trava: bloqueia se STATUSNOTA='L' (já confirmada no Sankhya).
    """
    try:
        payload = _get_json_payload(request) or {}
        motivo = (payload.get('motivo') or '').strip()
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)
        if not motivo:
            return JsonResponse({'ok': False, 'error': 'Motivo da exclusão é obrigatório.'},
                                status=400)

        # Snapshot ANTES do DELETE — captura estado completo da requisição
        snapshot_antes = None
        try:
            snapshot_antes = obter_requisicao_combustivel(int(nunota))
        except Exception:
            logger.warning("Falha ao capturar snapshot ANTES de DELETE requisicao NUNOTA=%s", nunota)

        resultado = excluir_requisicao_combustivel_banco(
            nunota=int(nunota), motivo=motivo,
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='EXCLUIR_REQUISICAO',
            tabela_alvo='AD_REQUISICAO_COMBUSTIVEL',
            registro_id=int(nunota),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_antes=snapshot_antes,
            observacao=motivo,
        )
        return JsonResponse(resultado, status=200)
    except Exception as exc:
        logger.exception("Falha em api_excluir_requisicao_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_relatorio_consumo_veiculo(request: HttpRequest) -> JsonResponse:
    """Relatório de consumo por veículo.

    Querystring:
      codveiculo: int (obrigatório)
      date_start: 'YYYY-MM-DD' (opcional — default: -30 dias)
      date_end:   'YYYY-MM-DD' (opcional — default: hoje)

    Retorna JSON com {veiculo, periodo, abastecimentos, totais}.
    """
    try:
        codveiculo = _converter_para_inteiro(request.GET.get('codveiculo'))
        if not codveiculo:
            return JsonResponse({'ok': False, 'error': 'codveiculo obrigatório.'},
                                status=400)
        date_start = (request.GET.get('date_start') or '').strip() or None
        date_end   = (request.GET.get('date_end')   or '').strip() or None

        dados = consultar_consumo_por_veiculo(codveiculo, date_start=date_start,
                                              date_end=date_end)
        if not dados:
            return JsonResponse({'ok': False, 'error': 'Veículo não encontrado.'},
                                status=404)
        return JsonResponse({'ok': True, **dados})
    except Exception as exc:
        logger.exception("Falha em api_relatorio_consumo_veiculo")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)},
                            status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_criar_entrada_combustivel(request: HttpRequest) -> JsonResponse:
    """Cria entrada de combustível (compra) TOP 10 + TGFITE + TGFFIN.

    Payload:
      {
        codemp: int,
        codparc: int (fornecedor),
        codprod: int,
        qtd: float (litros, > 0),
        vlrunit: float (> 0),
        codcencus: int,
        dtneg: str 'YYYY-MM-DD' (opcional — default hoje),
        dtvenc: str 'YYYY-MM-DD' (opcional — default = dtneg = à vista),
        codbco: int (opcional — default 70),
        codctabcoint: int (opcional — default 1),
        codtiptit: int (opcional — default 2),
        historico: str (opcional),
        observacao: str (opcional)
      }
    """
    try:
        payload = _get_json_payload(request) or {}
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)

        resultado = criar_entrada_combustivel_banco(
            dados=payload, codusu=int(codusu), nomeusu=str(nomeusu)
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='CRIAR_ENTRADA',
            tabela_alvo='TGFCAB',
            registro_id=resultado.get('nunota'),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_depois={
                'NUNOTA':       resultado.get('nunota'),
                'CODTIPOPER':   10,
                'CODEMP':       payload.get('codemp'),
                'CODPARC':      payload.get('codparc'),
                'NUMNOTA':      payload.get('numnota'),
                'SERIENOTA':    payload.get('serienota'),
                'DTNEG':        payload.get('dtneg'),
                'DTVENC':       payload.get('dtvenc'),
                'CODCENCUS':    payload.get('codcencus'),
                'CODNAT':       payload.get('codnat'),
                'CODTIPVENDA':  payload.get('codtipvenda'),
                'ITENS':        payload.get('itens') or [{
                    'CODPROD':  payload.get('codprod'),
                    'QTD':      payload.get('qtd'),
                    'VLRUNIT':  payload.get('vlrunit'),
                }],
                'NUFIN_GERADO': resultado.get('nufin'),
            },
            observacao=payload.get('observacao') or payload.get('historico'),
        )
        return JsonResponse(resultado, status=201)
    except Exception as exc:
        logger.exception("Falha em api_criar_entrada_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_obter_entrada_combustivel(request: HttpRequest, nunota: int) -> JsonResponse:
    """B14 (Mai/2026) — Retorna cabeçalho + itens + financeiro de uma entrada
    de combustível (TOP 10). Usado pelo modal em modo edição."""
    try:
        dados = obter_entrada_combustivel(int(nunota))
        if not dados:
            return JsonResponse({'ok': False, 'error': 'Entrada não encontrada.'}, status=404)
        return JsonResponse({'ok': True, **dados})
    except Exception as exc:
        logger.exception("Falha em api_obter_entrada_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_editar_entrada_combustivel(request: HttpRequest, nunota: int) -> JsonResponse:
    """B14 (Mai/2026) — Edita entrada de combustível (TOP 10) com multi-itens.

    Payload mesmo formato do criar (com `itens` lista) — campos ausentes
    preservam valor atual. Bloqueia se TGFFIN baixado.
    """
    try:
        payload = _get_json_payload(request) or {}
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)

        # Snapshot ANTES — captura cabeçalho + itens + financeiro pré-UPDATE
        snapshot_antes = None
        try:
            snapshot_antes = obter_entrada_combustivel(int(nunota))
        except Exception:
            logger.warning("Falha snapshot ANTES de entrada NUNOTA=%s", nunota)

        resultado = editar_entrada_combustivel_banco(
            nunota=int(nunota), dados=payload,
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='EDITAR_ENTRADA',
            tabela_alvo='TGFCAB',
            registro_id=int(nunota),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_antes=snapshot_antes,
            snapshot_depois={'NUNOTA': int(nunota), **payload},
        )
        return JsonResponse(resultado, status=200)
    except Exception as exc:
        logger.exception("Falha em api_editar_entrada_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["POST"])
@exige_grupo('combustivel')
def api_excluir_entrada_combustivel(request: HttpRequest, nunota: int) -> JsonResponse:
    """B15 (Mai/2026) — Exclui FISICAMENTE uma entrada (DELETE em cascata
    TGFFIN → TGFITE → TGFCAB). Payload: {motivo: str obrigatório}.
    Bloqueia se TGFFIN baixado."""
    try:
        payload = _get_json_payload(request) or {}
        motivo = (payload.get('motivo') or '').strip()
        codusu = request.session.get('codusu')
        nomeusu = request.session.get('nomeusu') or ''
        if not motivo:
            return JsonResponse({'ok': False, 'error': 'Motivo é obrigatório.'}, status=400)
        if not codusu:
            return JsonResponse({'ok': False, 'error': 'Sessão expirada.'}, status=401)
        # Snapshot ANTES do DELETE cascata — captura tudo antes de sumir
        snapshot_antes = None
        try:
            snapshot_antes = obter_entrada_combustivel(int(nunota))
        except Exception:
            logger.warning("Falha snapshot ANTES de excluir entrada NUNOTA=%s", nunota)

        resultado = excluir_entrada_combustivel_banco(
            nunota=int(nunota), motivo=motivo,
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
        if not resultado.get('ok'):
            return JsonResponse(resultado, status=400)

        registrar_auditoria(
            modulo='combustivel',
            operacao='EXCLUIR_ENTRADA',
            tabela_alvo='TGFCAB',
            registro_id=int(nunota),
            codusu=int(codusu),
            nomeusu=str(nomeusu),
            snapshot_antes=snapshot_antes,
            observacao=motivo,
        )
        return JsonResponse(resultado, status=200)
    except Exception as exc:
        logger.exception("Falha em api_excluir_entrada_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_foto_veiculo(request: HttpRequest, placa: str) -> HttpResponse:
    """Mai/2026 — Serve a foto de um veículo.

    Resolução de arquivo:
      - Procura `static/sankhya_integration/img/veiculos/<PLACA>.{jpg,jpeg,png,webp}`
      - Case-insensitive (placa normalizada pra UPPER, alfanum apenas)
      - Fallback: `_placeholder.svg`

    Query param `?size=thumb` (Mai/2026 - 2026-05-13):
      - Pillow redimensiona pra 240x180 com filtro LANCZOS, cacheia em
        `_cache/<PLACA>.jpg`. Invalida automaticamente se o original mudar
        (mtime check). SVG não é redimensionado (servido direto).
      - Sem o param: serve original (full resolution) — usado em detalhe + lightbox.

    Cache do browser: 1 dia (Cache-Control: max-age=86400).
    """
    import os
    import mimetypes
    from django.http import FileResponse, HttpResponseNotFound
    from django.conf import settings

    placa_norm = ''.join(c for c in str(placa).upper() if c.isalnum())
    if not placa_norm:
        return HttpResponseNotFound()

    base_dir = os.path.join(
        settings.BASE_DIR, 'sankhya_integration', 'static',
        'sankhya_integration', 'img', 'veiculos',
    )

    # Localiza o arquivo original
    original_path = None
    extensoes = ['.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP']
    for ext in extensoes:
        caminho = os.path.join(base_dir, placa_norm + ext)
        if os.path.isfile(caminho):
            original_path = caminho
            break

    if not original_path:
        placeholder = os.path.join(base_dir, '_placeholder.svg')
        if os.path.isfile(placeholder):
            r = FileResponse(open(placeholder, 'rb'), content_type='image/svg+xml')
            r['Cache-Control'] = 'public, max-age=86400'
            return r
        return HttpResponseNotFound()

    quer_thumb = (request.GET.get('size') or '').lower() == 'thumb'

    if quer_thumb:
        # Tenta servir do cache ou gera com Pillow
        cache_dir = os.path.join(base_dir, '_cache')
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, placa_norm + '.jpg')

        # Cache invalida se original foi modificado depois do cache
        precisa_gerar = (
            not os.path.isfile(cache_path)
            or os.path.getmtime(cache_path) < os.path.getmtime(original_path)
        )
        if precisa_gerar:
            try:
                from PIL import Image
                with Image.open(original_path) as img:
                    # Converte pra RGB pra salvar em JPG (PNG com transparência viraria preto)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        fundo = Image.new('RGB', img.size, (241, 245, 249))  # #f1f5f9
                        fundo.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                        img = fundo
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.thumbnail((480, 360), Image.Resampling.LANCZOS)  # 2x da thumb visível (60×44 @ DPR 2)
                    img.save(cache_path, format='JPEG', quality=85, optimize=True)
            except Exception:
                logger.exception("Falha gerando thumb veículo placa=%s", placa_norm)
                # Cai pro original em caso de erro
                ctype, _ = mimetypes.guess_type(original_path)
                r = FileResponse(open(original_path, 'rb'),
                                 content_type=ctype or 'application/octet-stream')
                r['Cache-Control'] = 'public, max-age=86400'
                return r

        r = FileResponse(open(cache_path, 'rb'), content_type='image/jpeg')
        r['Cache-Control'] = 'public, max-age=86400'
        return r

    # Original full resolution
    ctype, _ = mimetypes.guess_type(original_path)
    r = FileResponse(open(original_path, 'rb'),
                     content_type=ctype or 'application/octet-stream')
    r['Cache-Control'] = 'public, max-age=86400'
    return r


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_ultimo_preco_combustivel(request: HttpRequest) -> JsonResponse:
    """Mai/2026 — Retorna VLRUNIT do último abastecimento (TOP 10) de um
    combustível. Usado pelo modal de Requisição: ao escolher o produto, o
    campo "Valor unit." é preenchido automaticamente.

    Query: ?codprod=N
    Retorna: {ok, codprod, vlrunit, dtneg, nunota} ou 404 se sem entradas.
    """
    try:
        codprod = request.GET.get('codprod')
        if not codprod:
            return JsonResponse({'ok': False, 'error': 'codprod obrigatório.'}, status=400)
        dados = consultar_ultimo_preco_combustivel(int(codprod))
        if not dados:
            return JsonResponse({'ok': False,
                                 'error': 'Nenhum abastecimento encontrado pra este combustível.'},
                                status=404)
        return JsonResponse({'ok': True, **dados})
    except Exception as exc:
        logger.exception("Falha em api_ultimo_preco_combustivel")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('combustivel')
def api_prazo_tipvenda(request: HttpRequest) -> JsonResponse:
    """Mai/2026 — Retorna prazo padrão de TGFTPV pra auto-cálculo de DTVENC."""
    try:
        codtipvenda = request.GET.get('codtipvenda')
        if not codtipvenda:
            return JsonResponse({'ok': False, 'error': 'codtipvenda obrigatório.'}, status=400)
        dados = consultar_prazo_tipvenda(int(codtipvenda))
        if not dados:
            return JsonResponse({'ok': False, 'error': 'Tipo de negociação não encontrado.'}, status=404)
        return JsonResponse({'ok': True, **dados})
    except Exception as exc:
        logger.exception("Falha em api_prazo_tipvenda")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


# ==============================================================================
# ⚙️ HUB DE CONFIGURAÇÕES (Mai/2026)
# Acessado pela engrenagem no header. Concentra opções administrativas
# (Usuários hoje, mais módulos no futuro). Sidebar fica só com operacional.
# Acesso: grupos 1 (Diretoria) + 6 (Suporte).
# ==============================================================================

@ensure_csrf_cookie
@exige_grupo('configuracoes')
def view_configuracoes_painel(request: HttpRequest) -> HttpResponse:
    """Hub de configurações — cards de subseções (Usuários, etc)."""
    return render(request, "sankhya_integration/configuracoes.html")


# ==============================================================================
# 👥 MÓDULO USUÁRIOS (Mai/2026)
# Tela de gestão de acesso: lista TSIUSU, detalhe com grupos TSIGPU, catálogo
# de grupos TSIGRU. Acesso restrito a grupos 1 (Diretoria) e 6 (Suporte).
#
# Cat A entregue: leituras (listar, detalhe, grupos) + página + frontend.
# Cat B pendente (B1-B6): inserir/atualizar/inativar/reativar/add+rem grupo —
# endpoints abaixo retornam 501 Not Implemented até serem aprovados.
# ==============================================================================

@ensure_csrf_cookie
@exige_grupo('usuarios')
def view_usuarios_painel(request: HttpRequest) -> HttpResponse:
    """Tela principal de gestão de usuários (Layout v2 com sidebar + 2 colunas)."""
    return render(request, "sankhya_integration/usuarios.html")


@require_http_methods(["GET"])
@exige_grupo('usuarios')
def api_usuarios_listar(request: HttpRequest) -> JsonResponse:
    """Lista paginada de usuários com filtros opcionais.

    Querystring:
      busca, codgrupo, limite (max 200, default 50), offset,
      apenas_ativos (default true), apenas_inativos (default false)
    """
    filtros = {
        'busca':           (request.GET.get('busca') or '').strip() or None,
        'codgrupo':        (request.GET.get('codgrupo') or '').strip() or None,
        'apenas_ativos':   (request.GET.get('apenas_ativos', 'true').lower() not in ('false', '0', 'no', 'n')),
        'apenas_inativos': (request.GET.get('apenas_inativos', 'false').lower() in ('true', '1', 'yes', 's')),
    }
    try:
        limite = int(request.GET.get('limite') or 50)
        limite = max(1, min(200, limite))
    except (TypeError, ValueError):
        limite = 50
    try:
        offset = max(0, int(request.GET.get('offset') or 0))
    except (TypeError, ValueError):
        offset = 0

    try:
        dados = listar_usuarios(filtros=filtros, limite=limite, offset=offset)
        return JsonResponse({'ok': True, **dados})
    except Exception as exc:
        logger.exception("Falha em api_usuarios_listar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('usuarios')
def api_usuarios_detalhe(request: HttpRequest, codusu: int) -> JsonResponse:
    """Detalhe completo de um usuário (cabeçalho + grupos extras ativos)."""
    try:
        dados = consultar_usuario_detalhe(int(codusu))
        if not dados:
            return JsonResponse({'ok': False, 'error': 'Usuário não encontrado.'}, status=404)
        return JsonResponse({'ok': True, 'usuario': dados})
    except Exception as exc:
        logger.exception("Falha em api_usuarios_detalhe codusu=%s", codusu)
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('usuarios')
def api_usuarios_grupos(request: HttpRequest) -> JsonResponse:
    """Catálogo de grupos TSIGRU ativos pra dropdowns da UI."""
    try:
        grupos = consultar_grupos_disponiveis()
        return JsonResponse({'ok': True, 'grupos': grupos})
    except Exception as exc:
        logger.exception("Falha em api_usuarios_grupos")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


# ------------------------------------------------------------------
# Stubs Cat B (B1-B6) — retornam 501 até serem aprovados ponto-a-ponto
# Frontend já chama esses endpoints, mas com tratamento de erro amigável.
# ------------------------------------------------------------------

def _stub_cat_b_pendente(operacao: str) -> JsonResponse:
    return JsonResponse({
        'ok': False,
        'pendente_cat_b': True,
        'error': (
            f'Operação "{operacao}" aguardando aprovação ponto-a-ponto do bloco '
            f'Cat B correspondente. Backend de leitura já entregue.'
        ),
    }, status=501)


@require_http_methods(["POST"])
@exige_grupo('usuarios')
def api_usuarios_criar(request: HttpRequest) -> JsonResponse:
    return _stub_cat_b_pendente('Criar usuário (B1)')


@require_http_methods(["POST"])
@exige_grupo('usuarios')
def api_usuarios_atualizar(request: HttpRequest, codusu: int) -> JsonResponse:
    return _stub_cat_b_pendente('Atualizar dados (B2)')


@require_http_methods(["POST"])
@exige_grupo('usuarios')
def api_usuarios_inativar(request: HttpRequest, codusu: int) -> JsonResponse:
    return _stub_cat_b_pendente('Inativar usuário (B3)')


@require_http_methods(["POST"])
@exige_grupo('usuarios')
def api_usuarios_reativar(request: HttpRequest, codusu: int) -> JsonResponse:
    return _stub_cat_b_pendente('Reativar usuário (B4)')


@require_http_methods(["POST"])
@exige_grupo('usuarios')
def api_usuarios_adicionar_grupo(request: HttpRequest, codusu: int) -> JsonResponse:
    return _stub_cat_b_pendente('Adicionar grupo (B5)')


@require_http_methods(["POST"])
@exige_grupo('usuarios')
def api_usuarios_remover_grupo(request: HttpRequest, codusu: int) -> JsonResponse:
    return _stub_cat_b_pendente('Remover grupo (B6)')


# ==============================================================================
# 📦 MÓDULO CAIXAS (Mai/2026, 2026-05-18)
# Controle de vasilhame retornável (caixa plástica). Saídas calculadas em
# runtime via CEIL(QTDNEG/PESO) de TGFITE TOP 35/37 'L' (mesma fórmula da
# etiqueta SafeTrace). Devoluções TOP 36 'L' descontam. Coletas/quebras/
# perdas são manuais em AD_COLETA_CAIXAS. Produtos PAPELAO (cadastrados em
# AD_PRODUTO_CAIXA) não contam saldo.
#
# Cat A entregue: saldo por cliente + timeline + lista de coletas + lista
# de produtos cadastrados + página HTML.
# Cat B pendente (B1-B3): criar coleta / estornar coleta / upsert tipo de
# caixa por produto — endpoints abaixo retornam 501 até aprovação.
# ==============================================================================

@ensure_csrf_cookie
@exige_grupo('caixas')
def view_caixas_painel(request: HttpRequest) -> HttpResponse:
    """Tela principal de controle de caixas (Layout v2)."""
    return render(request, "sankhya_integration/caixas.html")


@require_http_methods(["GET"])
@exige_grupo('caixas')
def api_caixas_saldo(request: HttpRequest) -> JsonResponse:
    """Lista saldo de caixas plásticas em campo por cliente.

    Querystring:
      q                       — UPPER LIKE em NOMEPARC
      apenas_saldo_positivo   — default true
      codparc                 — filtra um cliente específico (drill-down)
    """
    apenas_pos_raw = (request.GET.get('apenas_saldo_positivo', 'true') or '').lower()
    filtros = {
        'q':                     (request.GET.get('q') or '').strip() or None,
        'apenas_saldo_positivo': apenas_pos_raw not in ('false', '0', 'no', 'n'),
    }
    codparc = request.GET.get('codparc')
    if codparc:
        try:
            filtros['codparc'] = int(codparc)
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'codparc inválido.'}, status=400)
    try:
        linhas = consultar_saldo_caixas(filtros=filtros)
        total_caixas = sum(l['saldo'] for l in linhas if l['saldo'] > 0)
        return JsonResponse({
            'ok': True,
            'linhas': linhas,
            'total_clientes': len(linhas),
            'total_caixas': total_caixas,
        })
    except Exception as exc:
        logger.exception("Falha em api_caixas_saldo")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('caixas')
def api_caixas_timeline(request: HttpRequest, codparc: int) -> JsonResponse:
    """Timeline cronológica de eventos de caixa pra 1 cliente."""
    try:
        dias_raw = request.GET.get('dias') or '90'
        dias = max(1, min(730, int(dias_raw)))
    except (TypeError, ValueError):
        dias = 90
    try:
        eventos = obter_timeline_caixas(codparc=int(codparc), dias=dias)
        return JsonResponse({'ok': True, 'eventos': eventos, 'dias': dias})
    except Exception as exc:
        logger.exception("Falha em api_caixas_timeline codparc=%s", codparc)
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('caixas')
def api_caixas_coletas_listar(request: HttpRequest) -> JsonResponse:
    """Lista paginada de coletas manuais."""
    filtros = {
        'codparc':           request.GET.get('codparc') or None,
        'motivo':            (request.GET.get('motivo') or '').strip().upper() or None,
        'date_de':           (request.GET.get('date_de') or '').strip() or None,
        'date_ate':          (request.GET.get('date_ate') or '').strip() or None,
        'incluir_estornadas': (request.GET.get('incluir_estornadas', 'false') or '').lower() in ('1', 'true', 'yes', 's'),
    }
    if filtros['codparc']:
        try:
            filtros['codparc'] = int(filtros['codparc'])
        except (TypeError, ValueError):
            filtros['codparc'] = None
    try:
        limite = max(1, min(500, int(request.GET.get('limite') or 100)))
    except (TypeError, ValueError):
        limite = 100
    try:
        offset = max(0, int(request.GET.get('offset') or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        coletas = listar_coletas_caixas(filtros=filtros, limite=limite, offset=offset)
        return JsonResponse({'ok': True, 'coletas': coletas, 'limite': limite, 'offset': offset})
    except Exception as exc:
        logger.exception("Falha em api_caixas_coletas_listar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


@require_http_methods(["GET"])
@exige_grupo('caixas')
def api_caixas_produtos_listar(request: HttpRequest) -> JsonResponse:
    """Lista produtos cadastrados em AD_PRODUTO_CAIXA. Suporta filtro `tipo`."""
    tipo = (request.GET.get('tipo') or '').strip().upper() or None
    if tipo and tipo not in ('PLASTICA', 'PAPELAO'):
        tipo = None
    try:
        produtos = listar_produtos_caixa(tipo=tipo)
        return JsonResponse({'ok': True, 'produtos': produtos})
    except Exception as exc:
        logger.exception("Falha em api_caixas_produtos_listar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)


# ------------------------------------------------------------------
# Stubs Cat B (B1-B3) — retornam 501 até serem aprovados ponto-a-ponto
# ------------------------------------------------------------------

@require_http_methods(["POST"])
@exige_grupo('caixas')
def api_caixas_coleta_criar(request: HttpRequest) -> JsonResponse:
    """B1 — lança coleta/quebra/perda manual."""
    payload = _get_json_payload(request)
    codusu  = request.session.get('codusu') or 0
    nomeusu = request.session.get('nomeusu') or ''
    try:
        result = criar_coleta_caixas_banco(payload, codusu=int(codusu), nomeusu=str(nomeusu))
    except Exception as exc:
        logger.exception("Falha em api_caixas_coleta_criar")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)
    if not result.get('ok'):
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@require_http_methods(["POST"])
@exige_grupo('caixas')
def api_caixas_coleta_estornar(request: HttpRequest, id_coleta: int) -> JsonResponse:
    """B2 — soft-delete de coleta (ESTORNADO='S')."""
    payload = _get_json_payload(request)
    motivo  = (payload.get('motivo_estorno') or payload.get('motivo') or '').strip()
    codusu  = request.session.get('codusu') or 0
    nomeusu = request.session.get('nomeusu') or ''
    try:
        result = estornar_coleta_caixas_banco(
            id_coleta=int(id_coleta), motivo_estorno=motivo,
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
    except Exception as exc:
        logger.exception("Falha em api_caixas_coleta_estornar id=%s", id_coleta)
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)
    if not result.get('ok'):
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@require_http_methods(["POST"])
@exige_grupo('caixas')
def api_caixas_produto_upsert(request: HttpRequest) -> JsonResponse:
    """B3 — cadastra/atualiza tipo de caixa por produto."""
    payload    = _get_json_payload(request)
    codprod    = payload.get('codprod')
    tipo_caixa = payload.get('tipo_caixa') or payload.get('tipo')
    codusu     = request.session.get('codusu') or 0
    nomeusu    = request.session.get('nomeusu') or ''
    try:
        result = upsert_produto_caixa_banco(
            codprod=int(codprod or 0), tipo_caixa=str(tipo_caixa or ''),
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
    except Exception as exc:
        logger.exception("Falha em api_caixas_produto_upsert")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)
    if not result.get('ok'):
        return JsonResponse(result, status=400)
    return JsonResponse(result)


# =============================================================================
# !!! TEMPORÁRIO Mai/2026 — REMOVER QUANDO IAGRO VIRAR FLUXO ÚNICO !!!
#
# Endpoint chamado pelo botão "Atualizar" da tela /sankhya/caixas/ pra fazer
# backfill de TGFITE.PESO via moda da TOP 26 (vendas faturadas direto no
# Sankhya chegam com PESO=0).
#
# Quando todas as vendas passarem pelo IAgro, peso vem populado pelo Rastreio
# e essa rota deixa de ter razão. Pra remover (ver detalhes na função service):
#   1. Apagar este endpoint + import
#   2. Apagar a rota em urls.py (caixas/api/refresh-pesos/)
#   3. Reverter o bloco TEMPORÁRIO em caixas.js (handler do botão Atualizar)
# =============================================================================
@require_http_methods(["POST"])
@exige_grupo('caixas')
def api_caixas_refresh_pesos(request: HttpRequest) -> JsonResponse:
    """[TEMPORÁRIO Mai/2026] Backfill TGFITE.PESO via moda da TOP 26.

    Idempotente: linhas com PESO > 0 ficam intactas.
    Primeira chamada em base grande pode demorar alguns minutos (MERGE em
    centenas de milhares de linhas + triggers Sankhya). Próximas chamadas
    cobrem apenas vendas novas → rápido.
    """
    codusu  = request.session.get('codusu') or 0
    nomeusu = request.session.get('nomeusu') or ''
    try:
        result = popular_pesos_top34_35_37_via_moda_TEMP(
            codusu=int(codusu), nomeusu=str(nomeusu),
        )
    except Exception as exc:
        logger.exception("Falha em api_caixas_refresh_pesos")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)
    if not result.get('ok'):
        return JsonResponse(result, status=400)
    return JsonResponse(result)


# ============================================================================
# IMPRESSÃO DE PEDIDOS DE VENDA (Mai/2026 — 2026-05-21)
# 3 endpoints: preview JSON + PDF individual + PDF consolidado.
# Tudo Cat A (leitura pura + geração de PDF — zero escrita).
# ============================================================================

# Atalhos de agrupamento — CODTAB no TGFPAR identifica famílias de cliente
_GRUPOS_IMPRESSAO_CODTAB = {
    'ASSAI_DF':                 [5],            # 7 lojas Assaí DF
    'ASSAI_PALMAS_ARAGUAINA':   [17, 18],       # Araguaína + Palmas (2 lojas)
    'ASSAI_TODOS':              [5, 17, 18],    # todos os Assaís
}


def _build_filtros_impressao(request: HttpRequest) -> dict:
    """Constrói o dict de filtros pra ``listar_pedidos_para_impressao`` a partir
    do GET (modo + codtabs + datas + nunotas explícitos)."""
    filtros: dict = {}

    # codtabs explícitos (ex: ?codtabs=4,5,6) — vence sobre `modo`
    codtabs_raw = (request.GET.get('codtabs') or '').strip()
    if codtabs_raw:
        try:
            filtros['codtabs'] = [int(t) for t in codtabs_raw.split(',') if t.strip()]
        except ValueError:
            pass

    # Modo nomeado legado (compat com chips antigos) — só se ainda não tiver codtabs
    if 'codtabs' not in filtros:
        modo = (request.GET.get('modo') or '').strip().upper()
        if modo in _GRUPOS_IMPRESSAO_CODTAB:
            filtros['codtabs'] = _GRUPOS_IMPRESSAO_CODTAB[modo]

    # Datas — aceita ou data única (dtneg) ou intervalo (dtneg_de/dtneg_ate)
    dtneg = (request.GET.get('dtneg') or '').strip()
    if dtneg:
        # Aceita YYYY-MM-DD do input HTML e converte pra DD/MM/YYYY do Oracle
        if len(dtneg) == 10 and dtneg[4] == '-':
            y, m, d = dtneg.split('-')
            filtros['dtneg'] = f"{d}/{m}/{y}"
        else:
            filtros['dtneg'] = dtneg
    else:
        de  = (request.GET.get('dtneg_de')  or '').strip()
        ate = (request.GET.get('dtneg_ate') or '').strip()
        def _to_br(s):
            if not s:
                return None
            if len(s) == 10 and s[4] == '-':
                y, m, d = s.split('-')
                return f"{d}/{m}/{y}"
            return s
        de_br  = _to_br(de)
        ate_br = _to_br(ate)
        if de_br and ate_br:
            filtros['dtneg_de']  = de_br
            filtros['dtneg_ate'] = ate_br

    codparc = (request.GET.get('codparc') or '').strip()
    if codparc:
        try:
            filtros['codparc'] = int(codparc)
        except ValueError:
            pass

    nunotas_raw = (request.GET.get('nunotas') or '').strip()
    if nunotas_raw:
        try:
            filtros['nunotas'] = [int(n) for n in nunotas_raw.split(',') if n.strip()]
        except ValueError:
            pass

    return filtros


@require_http_methods(["GET"])
@exige_grupo('venda')
def api_imprimir_preview(request: HttpRequest) -> JsonResponse:
    """Lista pedidos TOP 34 ativos pra preview da tela de impressão.

    Aceita os mesmos filtros do ``_build_filtros_impressao``. Frontend usa
    pra montar painel esquerdo (lista) + chips dinâmicos (só grupos com
    pedidos no dia aparecem).
    """
    filtros = _build_filtros_impressao(request)
    pedidos = listar_pedidos_para_impressao(filtros)
    # CODTABs únicos detectados — alimenta os chips de agrupamento dinâmico
    codtabs_distintos = sorted({
        p['codtab'] for p in pedidos if p.get('codtab') is not None
    })
    return JsonResponse({
        'ok': True,
        'pedidos': pedidos,
        'codtabs_distintos': codtabs_distintos,
        'filtros_aplicados': filtros,
    })


def _carregar_dados_para_pdf(nunotas: list[int]) -> list[dict]:
    """Carrega dados completos pra cada NUNOTA. Pula NUNOTAs inexistentes."""
    out = []
    for n in nunotas:
        try:
            d = obter_dados_pedido_completo_para_impressao(int(n))
        except Exception:
            logger.exception("Falha em obter_dados_pedido_completo_para_impressao(%s)", n)
            continue
        if d and d.get('pedido'):
            out.append(d)
    return out


def _coletar_pesos_fallback_pdf(dados: list[dict]) -> dict[int, float]:
    """Resolve pesos fallback (TOP 26 → TOP 11) só pros CODPRODs onde a venda
    não tem PESO populado. Reusado pelos endpoints de PDF individual e
    consolidado pra preencher a coluna CX nos relatórios."""
    codprods = list({
        it['codprod']
        for d in dados
        for it in (d.get('itens') or [])
        if not it.get('qtd_caixas')
    })
    if not codprods:
        return {}
    try:
        return consultar_pesos_referencia_por_codprods(codprods)
    except Exception:
        logger.exception("Falha em consultar_pesos_referencia_por_codprods (pdf)")
        return {}


def _parse_nunotas_payload(request: HttpRequest) -> list[int] | None:
    """Lê lista de NUNOTAs do corpo da request (JSON ``{nunotas: [...]}``) OU
    do query string ``?nunotas=N1,N2,...`` como fallback. Retorna None se
    formato inválido."""
    # 1ª tentativa: JSON body (POST)
    if request.method == 'POST':
        try:
            body = json.loads(request.body or b'{}')
            lista = body.get('nunotas') or []
            return [int(n) for n in lista if n]
        except (ValueError, TypeError, json.JSONDecodeError):
            return None
    # Fallback: query string
    raw = (request.GET.get('nunotas') or '').strip()
    if not raw:
        return []
    try:
        return [int(n) for n in raw.split(',') if n.strip()]
    except ValueError:
        return None


@require_http_methods(["GET", "POST"])
@exige_grupo('venda')
def api_imprimir_consolidacao(request: HttpRequest) -> JsonResponse:
    """Retorna agregação por CODPROD de uma lista de NUNOTAs.

    Aceita POST (JSON body ``{nunotas: [...]}``) — recomendado pra listas
    grandes — ou GET (``?nunotas=N1,N2``) como fallback.
    """
    nunotas = _parse_nunotas_payload(request)
    if nunotas is None:
        return JsonResponse(
            {'ok': False, 'error': 'Lista de pedidos inválida.'}, status=400,
        )
    if not nunotas:
        return JsonResponse({'ok': True, 'produtos': [], 'total_pedidos': 0,
                              'total_qtd': 0, 'total_caixas': 0})

    dados = _carregar_dados_para_pdf(nunotas)
    if not dados:
        return JsonResponse({'ok': True, 'produtos': [], 'total_pedidos': 0,
                              'total_qtd': 0, 'total_caixas': 0})

    por_prod: dict[int, dict] = {}
    for d in dados:
        for it in (d.get('itens') or []):
            cp = it['codprod']
            slot = por_prod.setdefault(cp, {
                'codprod':    cp,
                'descrprod':  it['descrprod'],
                'codvol':     it['codvol'],
                'qtd_total':  0.0,
                'qtd_caixas': 0,
                'n_pedidos':  0,
                '_nunotas':   set(),
            })
            slot['qtd_total']  += float(it['qtdneg'] or 0)
            slot['qtd_caixas'] += int(it['qtd_caixas'] or 0)
            slot['_nunotas'].add(d['pedido']['nunota'])

    # Pra produtos sem caixas calculadas (TGFITE.PESO=0), resolve via cascata
    # TOP 26 → TOP 11 numa única query. Recalcula qtd_caixas = CEIL(qtd_total / peso).
    codprods_sem_cx = [cp for cp, slot in por_prod.items() if slot['qtd_caixas'] == 0]
    pesos_ref = {}
    if codprods_sem_cx:
        try:
            pesos_ref = consultar_pesos_referencia_por_codprods(codprods_sem_cx)
        except Exception:
            logger.exception("Falha em consultar_pesos_referencia_por_codprods")

    produtos = []
    total_qtd = 0.0
    total_cx  = 0
    for slot in sorted(por_prod.values(), key=lambda r: r['codprod']):
        slot['n_pedidos'] = len(slot['_nunotas'])
        del slot['_nunotas']
        # Fallback de caixas
        if slot['qtd_caixas'] == 0:
            peso_ref = pesos_ref.get(slot['codprod'])
            if peso_ref and peso_ref > 0:
                slot['qtd_caixas'] = int(-(-float(slot['qtd_total']) // float(peso_ref)))
        total_qtd += slot['qtd_total']
        total_cx  += slot['qtd_caixas']
        produtos.append(slot)

    return JsonResponse({
        'ok': True,
        'produtos':       produtos,
        'total_pedidos':  len(dados),
        'total_qtd':      total_qtd,
        'total_caixas':   total_cx,
    })


@require_http_methods(["GET", "POST"])
@exige_grupo('venda')
def api_imprimir_pdf_individual(request: HttpRequest):
    """Gera PDF com 1 página por pedido (layout Sankhya).

    Aceita POST (JSON body ``{nunotas: [...]}``) — recomendado pra listas
    grandes — ou GET (``?nunotas=N1,N2``) como fallback.
    """
    nunotas = _parse_nunotas_payload(request)
    if nunotas is None:
        return JsonResponse(
            {'ok': False, 'error': 'Lista de pedidos inválida.'}, status=400,
        )
    if not nunotas:
        return JsonResponse(
            {'ok': False, 'error': 'Selecione pelo menos 1 pedido pra imprimir.'},
            status=400,
        )

    dados = _carregar_dados_para_pdf(nunotas)
    if not dados:
        return JsonResponse(
            {'ok': False, 'error': 'Nenhum pedido encontrado.'}, status=404,
        )

    pesos_fallback = _coletar_pesos_fallback_pdf(dados)

    try:
        pdf_bytes = gerar_pdf_pedidos_individual(dados, pesos_fallback=pesos_fallback)
    except Exception as exc:
        logger.exception("Falha em gerar_pdf_pedidos_individual")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500,
        )

    sufx = f'-{nunotas[0]}' if len(nunotas) == 1 else f'-lote-{len(nunotas)}'
    fname = f'pedidos{sufx}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response


@require_http_methods(["GET", "POST"])
@exige_grupo('venda')
def api_imprimir_pdf_consolidado(request: HttpRequest):
    """Gera PDF consolidado de N pedidos agrupado por CODPROD.

    Aceita POST (JSON body ``{nunotas: [...], titulo: ..., subtitulo: ...}``)
    — recomendado — ou GET (``?nunotas=...&titulo=...&subtitulo=...``).
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body or b'{}')
        except (ValueError, json.JSONDecodeError):
            body = {}
        titulo    = (body.get('titulo')    or '').strip() or 'CONSOLIDAÇÃO DE PEDIDOS'
        subtitulo = (body.get('subtitulo') or '').strip()
    else:
        titulo    = (request.GET.get('titulo')    or '').strip() or 'CONSOLIDAÇÃO DE PEDIDOS'
        subtitulo = (request.GET.get('subtitulo') or '').strip()

    nunotas = _parse_nunotas_payload(request)
    if nunotas is None:
        return JsonResponse(
            {'ok': False, 'error': 'Lista de pedidos inválida.'}, status=400,
        )
    if not nunotas:
        return JsonResponse(
            {'ok': False, 'error': 'Selecione pelo menos 1 pedido pra consolidar.'},
            status=400,
        )

    dados = _carregar_dados_para_pdf(nunotas)
    if not dados:
        return JsonResponse(
            {'ok': False, 'error': 'Nenhum pedido encontrado.'}, status=404,
        )

    pesos_fallback = _coletar_pesos_fallback_pdf(dados)

    try:
        pdf_bytes = gerar_pdf_pedidos_consolidado(
            dados, titulo=titulo, subtitulo=subtitulo,
            pesos_fallback=pesos_fallback,
        )
    except Exception as exc:
        logger.exception("Falha em gerar_pdf_pedidos_consolidado")
        return JsonResponse(
            {'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500,
        )

    fname = f'consolidado-{len(nunotas)}-pedidos.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response
