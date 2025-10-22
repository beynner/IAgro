from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from datetime import date as _date
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_http_methods
import logging
import json
import time

try:
    from sankhya_integration.services.oracle_conn import (
        get_connection,
        listar_produtos,
        listar_parceiros,
        listar_notas_compra,
        listar_itens_da_nota,
        obter_cabecalho_nota,
        plan_insert_cabecalho,
        insert_cabecalho,
        insert_cabecalho_fast,
        is_write_enabled,
        buscar_top_operacoes,
        buscar_naturezas,
        buscar_centros_resultado,
        plan_insert_item,
        insert_item,
        insert_item_fast,
        plan_update_item,
        update_item,
        listar_lotes_entradas_classificaveis,
        consultar_lotes_sumario_top11_classificaveis,
    sync_item_to_classification,
        plan_update_cabecalho,
        update_cabecalho,
        delete_itens,
        duplicate_item,
        delete_nota,
        diagnose_nota_delete,
        plan_classificacao,
        execute_classificacao,
        listar_lotes_recentes,
        listar_lotes_portal,
        listar_lotes_classificacao,
        duplicate_to_classification,
        get_duplicate_status,
        is_auto_duplicate_enabled,
        is_auto_duplicate_on_save_enabled,
        should_auto_duplicate_item,
        consultar_lote,
        fetch_tgfite_details,
        listar_itens_portal_basico,
        resumo_classificacao_por_lote,
        
    )
    # Lazy import inside functions for advanced helpers when needed
    ORACLE_AVAILABLE = True
    # Importar serviço gerar_vale_compra_top13 (vale TOP 13) da camada faturamento
    try:
        from .services.faturamento import gerar_vale_compra_top13  # type: ignore
    except Exception:
        # Fallback: tentar obter da oracle_conn (alias pode existir) ou definir stub
        try:
            from sankhya_integration.services.oracle_conn import gerar_vale_compra_top13  # type: ignore
        except Exception:
            def gerar_vale_compra_top13(*_a, **_kw):  # type: ignore
                return {'ok': False, 'error': 'Serviço gerar_vale_compra_top13 indisponível'}
except Exception as exc:  # pragma: no cover - make views importable when Oracle driver is missing
    logger = logging.getLogger(__name__)
    logger.warning('Could not import oracle_conn services (cx_Oracle may be missing): %s', exc)
    ORACLE_AVAILABLE = False
    _import_error_msg = str(exc)

    def _missing(name, _msg=_import_error_msg):
        def _fn(*args, **kwargs):
            raise RuntimeError(f"Service '{name}' is unavailable because oracle driver/import failed: {_msg}")
        return _fn

    get_connection = _missing('get_connection')
    listar_produtos = _missing('listar_produtos')
    listar_parceiros = _missing('listar_parceiros')
    listar_notas_compra = _missing('listar_notas_compra')
    listar_itens_da_nota = _missing('listar_itens_da_nota')
    obter_cabecalho_nota = _missing('obter_cabecalho_nota')
    plan_insert_cabecalho = _missing('plan_insert_cabecalho')
    insert_cabecalho = _missing('insert_cabecalho')
    insert_cabecalho_fast = _missing('insert_cabecalho_fast')
    is_write_enabled = lambda: False
    buscar_top_operacoes = _missing('buscar_top_operacoes')
    buscar_naturezas = _missing('buscar_naturezas')
    buscar_centros_resultado = _missing('buscar_centros_resultado')
    plan_insert_item = _missing('plan_insert_item')
    insert_item = _missing('insert_item')
    insert_item_fast = _missing('insert_item_fast')
    plan_update_item = _missing('plan_update_item')
    update_item = _missing('update_item')
    plan_update_cabecalho = _missing('plan_update_cabecalho')
    update_cabecalho = _missing('update_cabecalho')
    delete_itens = _missing('delete_itens')
    duplicate_item = _missing('duplicate_item')
    delete_nota = _missing('delete_nota')
    diagnose_nota_delete = _missing('diagnose_nota_delete')
    plan_classificacao = _missing('plan_classificacao')
    execute_classificacao = _missing('execute_classificacao')
    listar_lotes_recentes = _missing('listar_lotes_recentes')
    listar_lotes_portal = _missing('listar_lotes_portal')
    listar_lotes_classificacao = _missing('listar_lotes_classificacao')
    listar_lotes_entradas_classificaveis = _missing('listar_lotes_entradas_classificaveis')
    consultar_lotes_sumario_top11_classificaveis = _missing('consultar_lotes_sumario_top11_classificaveis')
    duplicate_to_classification = _missing('duplicate_to_classification')
    get_duplicate_status = _missing('get_duplicate_status')
    is_auto_duplicate_enabled = _missing('is_auto_duplicate_enabled')
    is_auto_duplicate_on_save_enabled = _missing('is_auto_duplicate_on_save_enabled')
    should_auto_duplicate_item = _missing('should_auto_duplicate_item')
    consultar_lote = _missing('consultar_lote')
    sync_item_to_classification = _missing('sync_item_to_classification')
    listar_itens_portal_basico = _missing('listar_itens_portal_basico')
    try:
        from .services.faturamento import gerar_vale_compra_top13  # type: ignore
    except Exception:
        gerar_vale_compra_top13 = _missing('gerar_vale_compra_top13')
logger = logging.getLogger(__name__)


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "sankhya_integration/index.html")


@require_http_methods(["POST"])
def gerar_vale_compra(request: HttpRequest) -> HttpResponse:
    """Cria TOP 13 (vale de compra) a partir de uma nota TOP 11.
    JSON esperado: { "nunota": 123, "items": [ {"sequencia": 1, "preco": 10.5}, ... ] }
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    nunota = payload.get('nunota') or payload.get('nunota_11')
    items = payload.get('items') or []
    if not nunota:
        return JsonResponse({'ok': False, 'error': 'Parâmetro nunota ausente'}, status=400)
    result = gerar_vale_compra_top13(nunota, items)
    return JsonResponse(result, status=200 if result.get('ok') else 400)


def health(request: HttpRequest) -> HttpResponse:
    """Lightweight health check: reports import status and optional DB ping when available."""
    status = {
        'oracle_import': ORACLE_AVAILABLE,
    }
    # If imported, try a quick ping
    if ORACLE_AVAILABLE:
        try:
            with get_connection() as conn:
                try:
                    conn.ping()
                    status['db_ping'] = True
                except Exception:
                    # If ping isn't available, try a trivial query
                    cur = conn.cursor()
                    cur.execute("SELECT 1 FROM DUAL")
                    _ = cur.fetchone()
                    status['db_ping'] = True
        except Exception as e:
            status['db_ping'] = False
            status['error'] = str(e)
    else:
        status['error'] = 'Oracle driver not imported'
    return JsonResponse(status)


def produtos_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q")
    try:
        limit = int(request.GET.get("limit", 50))
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        limit, offset = 50, 0
    rows = listar_produtos(limit=limit, offset=offset, nome=q)

    has_prev = offset > 0
    prev_offset = max(offset - limit, 0)
    has_next = len(rows) == limit
    next_offset = offset + limit
    ctx = {
        "rows": rows,
        "q": q or "",
        "limit": limit,
        "offset": offset,
        "has_prev": has_prev,
        "prev_offset": prev_offset,
        "has_next": has_next,
        "next_offset": next_offset,
    }
    return render(request, "sankhya_integration/produtos_list.html", ctx)


def parceiros_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q")
    try:
        limit = int(request.GET.get("limit", 50))
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        limit, offset = 50, 0
    rows = listar_parceiros(limit=limit, offset=offset, nome=q)
    has_prev = offset > 0
    prev_offset = max(offset - limit, 0)
    has_next = len(rows) == limit
    next_offset = offset + limit
    ctx = {
        "rows": rows,
        "q": q or "",
        "limit": limit,
        "offset": offset,
        "has_prev": has_prev,
        "prev_offset": prev_offset,
        "has_next": has_next,
        "next_offset": next_offset,
    }
    return render(request, "sankhya_integration/parceiros_list.html", ctx)


def entrada_preview(request: HttpRequest) -> HttpResponse:
    # Buscar opções iniciais (somente leitura, limites pequenos)
    produtos = listar_produtos(limit=100, offset=0)
    parceiros = listar_parceiros(limit=100, offset=0)
    ctx = {
        "produtos": produtos,
        "parceiros": parceiros,
    }
    return render(request, "sankhya_integration/entrada_preview.html", ctx)


@ensure_csrf_cookie
def compras_portal(request: HttpRequest) -> HttpResponse:
    def _to_int(value):
        if value in (None, "", "None", "none", "null"):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    raw_controle = request.GET.get("controle")
    controle = (raw_controle or "").strip()
    if controle.lower() in ("", "none", "null"):
        controle = None
    params = {
        "days": _to_int(request.GET.get("days")) or 7,
        "date_start": request.GET.get("start"),
        "date_end": request.GET.get("end"),
        "nronota_ini": request.GET.get("nronota_ini"),
        "nronota_fim": request.GET.get("nronota_fim"),
        "nunota_ini": _to_int(request.GET.get("nunota_ini")),
        "nunota_fim": _to_int(request.GET.get("nunota_fim")),
        "codparc": _to_int(request.GET.get("codparc")),
        "codprod": _to_int(request.GET.get("codprod")),
        "controle": controle,
        "sort": request.GET.get("sort") or "dtneg",
        "dir": (request.GET.get("dir") or "desc").lower(),
    }
    # paginação simples baseada em 'page' (sem expor limit/offset)
    try:
        page = int(request.GET.get("page", 1))
    except Exception:
        page = 1
    if page < 1:
        page = 1
    page_size = 50
    # Keep 'controle' param name in params for compatibility; service expects "controle" to mean CODAGREGACAO
    svc_params = params.copy()
    # Allow selecting TOP(s) via query param: top=13 or tops=11,13
    tops_param = (request.GET.get("tops") or request.GET.get("top") or "").strip()
    tops_list = None
    if tops_param:
        try:
            parts = [p.strip() for p in tops_param.split(',') if p.strip()]
            vals = []
            for pstr in parts:
                try:
                    v = int(pstr)
                    if v > 0:
                        vals.append(v)
                except Exception:
                    continue
            if vals:
                tops_list = vals
        except Exception:
            tops_list = None
    # Portal: Forçar apenas TOP 11 (Pedidos de Compra)
    from sankhya_integration.services.oracle_conn import get_params as get_oracle_params
    p = get_oracle_params()
    svc_params["tops"] = [p['TOP_ENTRADA']]  # Sempre TOP 11 no Portal
    notas = listar_notas_compra(limit=page_size + 1, offset=(page - 1) * page_size, **svc_params)
    has_next = len(notas) > page_size
    if has_next:
        notas = notas[:page_size]
    has_prev = page > 1
    prev_page = page - 1 if has_prev else 1
    next_page = page + 1 if has_next else page

    sel_param = _to_int(request.GET.get("sel"))
    sel_nunota = sel_param if sel_param is not None else (notas[0][0] if notas else None)
    itens = listar_itens_da_nota(sel_nunota) if sel_nunota else []
    # Ajustar quantidade exibida na tabela lateral "Itens da Nota" para a unidade alternativa
    # IMPORTANTE: Sankhya armazena QTDNEG sempre na unidade BASE (KG), mas CODVOL indica a unidade de entrada.
    # Para exibir corretamente, precisamos DIVIDIR pelo fator quando CODVOL != base
    try:
        if itens:
            converted = []
            from sankhya_integration.services.oracle_conn import get_base_unit_and_factor  # lazy import
            for r in itens:
                try:
                    ctrl = r[0] if len(r) > 0 else None
                    seq  = r[1] if len(r) > 1 else None
                    codp = r[2] if len(r) > 2 else None
                    descr= r[3] if len(r) > 3 else None
                    codv = r[4] if len(r) > 4 else None
                    qtdn = r[5] if len(r) > 5 else None
                    peso = r[6] if len(r) > 6 else None
                    vlu  = r[7] if len(r) > 7 else None
                    vlt  = r[8] if len(r) > 8 else None
                    obs  = r[9] if len(r) > 9 else None
                    gp   = r[10] if len(r) > 10 else None
                    disp_qtd = qtdn
                    # Converter de unidade base para alternativa ao EXIBIR
                    try:
                        if codp is not None and codv:
                            base, fator = get_base_unit_and_factor(int(codp), str(codv))
                            if base and str(base).upper() != str(codv).upper() and fator and float(fator) > 0:
                                disp_qtd = float(qtdn or 0) / float(fator)
                    except Exception:
                        pass
                    # rebuild row with converted quantity in the same positions expected by template
                    converted.append((ctrl, seq, codp, descr, codv, disp_qtd, peso, vlu, vlt, obs, gp))
                except Exception:
                    converted.append(r)
            itens = converted
    except Exception:
        # on any failure, keep original itens
        pass

    # Build display strings for partner/product so inputs show "COD — DESCR" after reload
    parc_display = ''
    prod_display = ''
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if params.get('codparc'):
                try:
                    cur.execute("SELECT NOMEPARC FROM TGFPAR WHERE CODPARC = :k", k=int(params['codparc']))
                    r = cur.fetchone()
                    nome = (r[0] if r else '') or ''
                    parc_display = f"{int(params['codparc'])} — {nome}" if nome else f"{int(params['codparc'])}"
                except Exception:
                    parc_display = f"{int(params['codparc'])}"

            if params.get('codprod'):
                try:
                    cur.execute("SELECT DESCRPROD FROM TGFPRO WHERE CODPROD = :k", k=int(params['codprod']))
                    r = cur.fetchone()
                    descr = (r[0] if r else '') or ''
                    prod_display = f"{int(params['codprod'])} — {descr}" if descr else f"{int(params['codprod'])}"
                except Exception:
                    prod_display = f"{int(params['codprod'])}"
    except Exception:
        # ignore lookup errors; fall back to codes only
        pass

    ctx = {
        "notas": notas,
        "itens": itens,
        "sel": sel_nunota,
        "params": params,
        "tops": tops_list,
        "parc_display": parc_display,
        "prod_display": prod_display,
        "page": page,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_page": prev_page,
        "next_page": next_page,
    }
    # Seed initial items JSON for client-side cache (match /sankhya/item/list format)
    try:
        items_out = []
        if sel_nunota and itens:
            for r in itens:
                # Template provides tuples: ctrl, seq, cod, descr, vol, qtd, peso, vlu, vlt, obs, gp
                cont = r[0] if len(r) > 0 else None
                seq = r[1] if len(r) > 1 else None
                codp = r[2] if len(r) > 2 else None
                descrp = r[3] if len(r) > 3 else ''
                codvol = r[4] if len(r) > 4 else ''
                qtdneg = r[5] if len(r) > 5 else None
                peso = r[6] if len(r) > 6 else None
                vlrunit = r[7] if len(r) > 7 else None
                vltot = r[8] if len(r) > 8 else None
                obs = r[9] if len(r) > 9 else ''
                gp = r[10] if len(r) > 10 else None
                total = None
                try:
                    if qtdneg is not None and peso is not None:
                        total = float(qtdneg) * float(peso)
                except Exception:
                    total = None
                items_out.append({
                    'nunota': int(sel_nunota),
                    'sequencia': int(seq) if seq is not None else None,
                    'cod': int(codp) if codp is not None else None,
                    'descr': descrp or '',
                    'lote': cont or '',
                    'codvol': (codvol or ''),
                    'qtd': float(qtdneg or 0) if qtdneg is not None else 0,
                    'peso': float(peso) if peso is not None else None,
                    'total': float(total) if total is not None else None,
                    'vlu': float(vlrunit or 0),
                    'vlt': float(vltot or 0),
                    'obs': obs or '',
                    'classifica': (None if gp is None else (str(gp).upper() != 'N')),
                    'geraproducao': (None if gp is None else str(gp).upper()),
                })
        ctx['initial_items_json'] = json.dumps({'ok': True, 'items': items_out}) if items_out else None
        ctx['initial_items_nunota'] = sel_nunota
    except Exception:
        ctx['initial_items_json'] = None
        ctx['initial_items_nunota'] = None
    return render(request, "sankhya_integration/compras_portal.html", ctx)


@ensure_csrf_cookie
def compras_classificacao(request: HttpRequest) -> HttpResponse:
    # Listar lotes recentes e mostrar agregados + produtos classificados para o lote selecionado
    t0 = time.perf_counter()
    def _to_int(value):
        if value in (None, "", "None", "none", "null"):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    raw_controle = (request.GET.get("controle") or "").strip()
    fabricante_q = (request.GET.get("fabricante") or "").strip()
    nunota_req = request.GET.get("nunota")
    try:
        nunota_req = int(nunota_req) if nunota_req not in (None, "", "None", "none", "null") else None
    except Exception:
        nunota_req = None
    params = {
        "days": _to_int(request.GET.get("days")),
        "date_start": request.GET.get("start"),
        "date_end": request.GET.get("end"),
        "codparc": _to_int(request.GET.get("codparc")),
        "codprod": _to_int(request.GET.get("codprod")),
        "fabricante": (fabricante_q if fabricante_q else None),
        "nunota": nunota_req,
        "controle": (raw_controle if raw_controle else None),
    }
    try:
        page = int(request.GET.get("page", 1))
    except Exception:
        page = 1
    if page < 1:
        page = 1
    page_size = 50

    # Classificação: Mostrar lotes do Portal (TOP 11) que são classificáveis (GERAPRODUCAO='S')
    t_list0 = time.perf_counter()
    db_error = None
    try:
        # If a specific NUNOTA is provided, resolve its controle (CODAGREGACAO)
        if params.get('nunota') and not params.get('controle'):
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT MAX(CODAGREGACAO) FROM TGFITE WHERE NUNOTA=:n", n=int(params['nunota']))
                    r = cur.fetchone()
                    if r and r[0]:
                        params['controle'] = str(r[0])
            except Exception:
                pass
        if params.get('controle'):
            # When filtering by specific controle, bypass list query and fix pagination to a single entry
            lotes_class = [(params['controle'],)]
        else:
            lotes_class = listar_lotes_entradas_classificaveis(
                days=params['days'],
                limit=page_size,
                codparc=params['codparc'],
                codprod=params['codprod'],
                date_start=params['date_start'],
                date_end=params['date_end'],
            )
    except Exception as e:
        # Gracefully handle Oracle connectivity errors so the page can render and surface a message
        lotes_class = []
        db_error = str(e)
    t_list1 = time.perf_counter()
    # Extrair controles para compatibilidade com código existente
    controles = [lote[0] for lote in lotes_class]  # Primeiro campo é o controle

    # Construir lista de lotes com resumo LEVE (apenas TOP 11 classificáveis) para performance
    lotes = []
    exemplo_map = {}
    try:
        t_sum0 = time.perf_counter()
        sum_map = consultar_lotes_sumario_top11_classificaveis(controles)
        t_sum1 = time.perf_counter()
    except Exception:
        sum_map = {}
        t_sum0 = t_sum1 = time.perf_counter()
    # Fill lotes list; ensure partner name is available. If missing from summary, fetch via fallback batch.
    # Identify controls missing partner info
    missing_partner_ctrls = []
    for ctrl in controles:
        info = sum_map.get(ctrl, {})
        if not info.get('parceiro'):
            missing_partner_ctrls.append(ctrl)
    # Batched fallback to resolve partner names when missing
    if missing_partner_ctrls:
        try:
            from sankhya_integration.services.oracle_conn import get_connection, get_params as _get_params
            _p = _get_params(); _top_ent = _p.get('TOP_ENTRADA', 11)
            # Build IN clause
            phs = []
            binds = {'top_ent': _top_ent}
            for idx, c in enumerate(missing_partner_ctrls):
                key = f"c{idx}"
                phs.append(f":{key}")
                binds[key] = c
            in_clause = ",".join(phs) if phs else "''"
            sql = (
                f"""
                SELECT i.CODAGREGACAO AS CTRL,
                       MAX(UPPER(NVL(pr.RAZAOSOCIAL, pr.NOMEPARC))) AS PARCEIRO,
                       MAX(c.CODPARC) AS CODPARC
                  FROM TGFITE i
                  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                  LEFT JOIN TGFPAR pr ON pr.CODPARC = c.CODPARC
                 WHERE i.CODAGREGACAO IN ({in_clause})
                   AND c.CODTIPOPER = :top_ent
                 GROUP BY i.CODAGREGACAO
                """
            )
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, binds)
                for ctrl, parceiro, codparc in cur.fetchall():
                    d = sum_map.setdefault(ctrl, {})
                    d['parceiro'] = parceiro or d.get('parceiro') or ''
                    try:
                        d['codparc'] = int(codparc) if codparc is not None else d.get('codparc')
                    except Exception:
                        d['codparc'] = codparc if codparc is not None else d.get('codparc')
        except Exception:
            pass

    # If any control has no fabricantes list, backfill manufacturers in a single batch for those controls
    missing_fab_ctrls = [c for c in controles if not (sum_map.get(c, {}).get('produtos_entrada') or [])]
    if missing_fab_ctrls:
        try:
            from sankhya_integration.services.oracle_conn import get_connection, get_params as _get_params
            _p = _get_params(); _top_ent = _p.get('TOP_ENTRADA', 11)
            phs = []
            binds = {'top_ent': _top_ent}
            for idx, c in enumerate(missing_fab_ctrls):
                key = f"c{idx}"
                phs.append(f":{key}")
                binds[key] = c
            in_clause = ",".join(phs) if phs else "''"
            sql = (
                f"""
                SELECT i.CODAGREGACAO AS CTRL, i.CODPROD, UPPER(NVL(p.FABRICANTE,'')) AS FABRICANTE
                  FROM TGFITE i
                  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                  LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                 WHERE i.CODAGREGACAO IN ({in_clause})
                   AND c.CODTIPOPER = :top_ent
                """
            )
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, binds)
                for ctrl, cod, fabricante in cur.fetchall():
                    d = sum_map.setdefault(ctrl, {})
                    lst = d.setdefault('produtos_entrada', [])
                    try:
                        cod_i = int(cod) if cod is not None else None
                    except Exception:
                        cod_i = cod
                    lst.append({'cod': cod_i, 'fabricante': fabricante or ''})
        except Exception:
            pass

    for ctrl in controles:
        info = sum_map.get(ctrl, {})
        # Produto: concatenar fabricantes (por produto)
        produtos_list = info.get('produtos_entrada') or []
        # Apply fabricante filter if provided
        if params.get('fabricante'):
            try:
                fab_u = str(params['fabricante']).strip().upper()
                if fab_u:
                    produtos_list = [p for p in produtos_list if (str(p.get('fabricante') or '').strip().upper() == fab_u)]
            except Exception:
                pass
        # If fabricante filter removed all products for this controle, skip lote
        if params.get('fabricante') and not produtos_list:
            continue
        produto_descr = ''
        try:
            if produtos_list:
                # Aggregate by manufacturer; show distinct list with counts when repeated
                mans = {}
                for p in produtos_list:
                    m = (p.get('fabricante') or '').strip()
                    if not m:
                        m = '(SEM FABRICANTE)'
                    mans[m] = mans.get(m, 0) + 1
                # Compose lines like: FABRICANTE (N itens) or just FABRICANTE
                produto_descr = '\n'.join([f"{k}" + (f" ({v})" if v>1 else '') for k, v in mans.items()])
        except Exception:
            produto_descr = ''
        # Compute displayed qCx: 
        # REGRA: Se houver itens classificados (TOP 26), mostrar a SOMA das caixas classificadas.
        # Caso contrário, usar a entrada (TOP 11) calculada.
        try:
            _qcx_classif = float(info.get('qtd_cx_classificado') or 0.0)
        except Exception:
            _qcx_classif = 0.0
        
        # Se já existem produtos classificados, usar essa quantidade
        if _qcx_classif > 0:
            _qcx_disp = _qcx_classif
        else:
            # Fallback: usar quantidade de entrada
            try:
                _qcx_raw = float(info.get('qtd_cx') or 0.0)
            except Exception:
                _qcx_raw = 0.0
            try:
                _qkg_raw = float(info.get('qtd_kg') or 0.0)
            except Exception:
                _qkg_raw = 0.0
            try:
                _peso_raw = float(info.get('peso_inn')) if info.get('peso_inn') is not None else None
            except Exception:
                _peso_raw = None
            if _peso_raw and _peso_raw > 0:
                try:
                    _qcx_disp = _qkg_raw / _peso_raw
                except Exception:
                    _qcx_disp = _qcx_raw
            else:
                _qcx_disp = _qcx_raw

        lotes.append((
            ctrl,
            info.get('parceiro') or '',
            produto_descr,
            float(_qcx_disp or 0.0),
            (float(info.get('peso_inn')) if info.get('peso_inn') is not None else 0.0),
            float(info.get('qtd_kg') or 0.0),
            0.0,  # qtde classificado (adiado/mix down)
            (info.get('pendente_class') or ''),  # reutiliza o slot para PENDENTE (TOP 26)
            None,  # exemplo_nunota (não necessário por enquanto)
            None,  # exemplo_seq
            produtos_list,
            info.get('codparc'),
            info.get('nunota_portal'),  # 🔗 NUNOTA da TOP 11 (Portal/Entrada) para vincular classificação
            info.get('nunota_top26'),   # 🔗 NUNOTA da TOP 26 (Classificação) para exclusão
        ))
        exemplo_map[ctrl] = {'nunota': info.get('exemplo_nunota'), 'sequencia': info.get('exemplo_seq')}

    # Seleção do lote (controle/codagregacao) por query param 'sel' (valor do controle)
    sel_controle = (request.GET.get('sel') or (lotes[0][0] if lotes else None))
    # Pré-carregar dados do lote selecionado (modo leve) para render instantânea no cliente
    produtos_classificados = []
    initial_lote = None
    try:
        if sel_controle:
            from sankhya_integration.services.oracle_conn import consultar_lote_light
            initial_lote = consultar_lote_light(sel_controle)
    except Exception:
        initial_lote = None
    selected_exemplo = exemplo_map.get(sel_controle) if sel_controle else None
    nunota_class_sel = None

    # Paginador simples (baseado no tamanho do lote retornado)
    if params.get('controle'):
        has_prev = False
        has_next = False
        prev_page = 1
        next_page = 1
    else:
        has_prev = page > 1
        has_next = len(lotes_class) == page_size
        prev_page = page - 1 if has_prev else 1
        next_page = page + 1 if has_next else page

    # Perf breakdown (ms)
    t_end = time.perf_counter()
    timings = {
        'list_ms': int((t_list1 - t_list0) * 1000),
        'sum_ms': int((t_sum1 - t_sum0) * 1000),
        'total_ms': int((t_end - t0) * 1000),
        'count_lotes': len(controles),
    }
    try:
        logger.info('[classificacao] perf list=%dms sum=%dms total=%dms lotes=%d', timings['list_ms'], timings['sum_ms'], timings['total_ms'], timings['count_lotes'])
    except Exception:
        pass
    show_perf = str(request.GET.get('perf') or '').lower() in ('1','true','yes','on')

    # Build display string for partner so the input shows "COD — NOME" after reload
    parc_display = ''
    try:
        if params.get('codparc') is not None:
            with get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT NOMEPARC FROM TGFPAR WHERE CODPARC = :k", k=int(params['codparc']))
                    r = cur.fetchone()
                    nome = (r[0] if r else '') or ''
                    parc_display = f"{int(params['codparc'])} — {nome}" if nome else f"{int(params['codparc'])}"
                except Exception:
                    parc_display = f"{int(params['codparc'])}"
    except Exception:
        parc_display = ''

    ctx = {
        'lotes': lotes,
        'produtos_classificados': produtos_classificados,
        'sel': sel_controle,
        'initial_lote_ctrl': sel_controle,
        'initial_lote_json': json.dumps(initial_lote) if initial_lote else None,
        'params': params,
        'parc_display': parc_display,
        'page': page,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': prev_page,
        'next_page': next_page,
        'selected_exemplo': selected_exemplo,
        'nunota_class_sel': nunota_class_sel,
        'timings': timings if show_perf else None,
        'timings_json': json.dumps(timings) if show_perf else None,
        'db_error': db_error,
    }
    return render(request, "sankhya_integration/compras_classificacao.html", ctx)


@ensure_csrf_cookie
def compras_central(request: HttpRequest) -> HttpResponse:
    sel = request.GET.get("nunota")
    try:
        sel_int = int(sel) if sel not in (None, "", "None", "none", "null") else None
    except ValueError:
        sel_int = None
    itens = listar_itens_da_nota(sel_int) if sel_int else []
    # listar_itens_da_nota now returns (CODAGREGACAO, SEQUENCIA, CODPROD, DESCRPROD, CODVOL, QTDNEG, PESO, VLRUNIT, VLRTOT, OBSERVACAO)
    # VLRTOT is at index 8
    vtotal = sum((row[8] or 0) for row in itens) if itens else 0
    cab = obter_cabecalho_nota(sel_int) if sel_int else None
    produtos = listar_produtos(limit=100)
    parceiros = listar_parceiros(limit=100)
    today_iso = _date.today().isoformat()
    default_form = {
        'codemp': '1',
        'nronota': '',
        'dtneg': today_iso,
        'dtmov': today_iso,
        'dtentsai': today_iso,
        'hrmov': '',
        'codparc': '',
        'codtipoper': (request.GET.get('codtipoper') or ''),
        'codtipoper_descr': '',
        'codnat': (request.GET.get('codnat') or '20010100'),
        'codnat_descr': '',
        'codcencus': (request.GET.get('codcencus') or '10100'),
        'codcencus_descr': '',
        'obs': '',
    }
    # Se veio codtipoper pela URL, buscar a descrição para pré-preencher o campo visível
    if default_form['codtipoper']:
        try:
            k = int(str(default_form['codtipoper']).strip())
        except Exception:
            k = None
        if k is not None:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT DESCROPER FROM ("
                    "  SELECT DESCROPER, DHALTER, ROW_NUMBER() OVER (PARTITION BY CODTIPOPER ORDER BY DHALTER DESC) rn"
                    "    FROM TGFTOP WHERE ATIVO='S' AND CODTIPOPER=:k"
                    ") WHERE rn=1",
                    k=k,
                )
                row = cur.fetchone()
                if row:
                    default_form['codtipoper_descr'] = row[0] or ''
    # Pré-carregar descrição da Natureza (default 11) e Centro de Resultado (default 10100)
    try:
        nat_k = int(str(default_form['codnat']).strip()) if default_form['codnat'] else None
    except Exception:
        nat_k = None
    try:
        cencus_k = int(str(default_form['codcencus']).strip()) if default_form['codcencus'] else None
    except Exception:
        cencus_k = None
    with get_connection() as conn:
        cur = conn.cursor()
        if nat_k is not None:
            cur.execute("SELECT DESCRNAT FROM TGFNAT WHERE CODNAT=:k", k=nat_k)
            r = cur.fetchone()
            if r:
                default_form['codnat_descr'] = r[0] or ''
        if cencus_k is not None:
            cur.execute("SELECT DESCRCENCUS FROM TSICUS WHERE CODCENCUS=:k", k=cencus_k)
            r = cur.fetchone()
            if r:
                default_form['codcencus_descr'] = r[0] or ''
    # Buscar descrição do local 101
    local101_descr = ''
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DESCRLOCAL FROM TGFLOC WHERE CODLOCAL = 101")
            r = cur.fetchone()
            if r and r[0]:
                local101_descr = r[0]
    except Exception:
        local101_descr = ''

    # Buscar descrição padrão do volume 'KG'
    vol_default = 'KG'
    vol_default_descr = ''
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DESCRVOL FROM TGFVOL WHERE UPPER(CODVOL) = 'KG'")
            r = cur.fetchone()
            if r and r[0]:
                vol_default_descr = r[0]
    except Exception:
        vol_default_descr = ''

    ctx = {
        "nunota": sel_int,
        "itens": itens,
        "vtotal": vtotal,
        "produtos": produtos,
        "parceiros": parceiros,
        "cab": cab,
        "form": default_form,
        "plan": None,
        "write_enabled": is_write_enabled(),
        "local101_descr": local101_descr,
        "vol_default": vol_default,
        "vol_default_descr": vol_default_descr,
    }
    # If AJAX prefill requested, return lightweight JSON with form/defaults to allow portal modal prefill
    if request.GET.get('ajax_header') in ('1', 'true', 'yes'):
        # prefer values from cab if available, otherwise defaults
        codparc_val = default_form.get('codparc') or (str(cab.get('CODPARC')) if isinstance(cab, dict) and cab.get('CODPARC') is not None else '')
        codparc_descr_val = (cab.get('NOMEPARC') if isinstance(cab, dict) and cab.get('NOMEPARC') else '') or default_form.get('codparc_descr','')
        # prefer codtipoper/codnat/codcencus from cab when available
        codtipoper_val = default_form.get('codtipoper') or (str(cab.get('CODTIPOPER')) if isinstance(cab, dict) and cab.get('CODTIPOPER') is not None else '')
        codtipoper_descr_val = (cab.get('DESCROPER') if isinstance(cab, dict) and cab.get('DESCROPER') else '') or default_form.get('codtipoper_descr','')
        codnat_val = default_form.get('codnat') or (str(cab.get('CODNAT')) if isinstance(cab, dict) and cab.get('CODNAT') is not None else '')
        codnat_descr_val = (cab.get('DESCRNAT') if isinstance(cab, dict) and cab.get('DESCRNAT') else '') or default_form.get('codnat_descr','')
        codcencus_val = default_form.get('codcencus') or (str(cab.get('CODCENCUS')) if isinstance(cab, dict) and cab.get('CODCENCUS') is not None else '')
        codcencus_descr_val = (cab.get('DESCRCENCUS') if isinstance(cab, dict) and cab.get('DESCRCENCUS') else '') or default_form.get('codcencus_descr','')
        out = {
            'form': {
                'nunota': sel_int if sel_int else None,
                'codemp': str(default_form.get('codemp') or ''),
                'nronota': default_form.get('nronota') or '',
                'dtneg': default_form.get('dtneg') or '',
                'dtmov': default_form.get('dtmov') or '',
                'dtentsai': default_form.get('dtentsai') or '',
                'hrmov': default_form.get('hrmov') or '',
                'codparc': codparc_val,
                'codparc_descr': codparc_descr_val,
                'codtipoper': codtipoper_val,
                'codtipoper_descr': codtipoper_descr_val,
                'codnat': codnat_val,
                'codnat_descr': codnat_descr_val,
                'codcencus': codcencus_val,
                'codcencus_descr': codcencus_descr_val,
                'obs': default_form.get('obs') or (cab.get('OBSERVACAO') if isinstance(cab, dict) and cab.get('OBSERVACAO') else ''),
            }
        }
        return JsonResponse(out)

    return render(request, "sankhya_integration/compras_central.html", ctx)


def packing_portal(request: HttpRequest) -> HttpResponse:
    return compras_portal(request)


def packing_central(request: HttpRequest) -> HttpResponse:
    return compras_central(request)


def _iso_to_br(d: str|None) -> str|None:
    if not d:
        return None
    s = str(d).strip()
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def _first(val):
    if isinstance(val, (list, tuple)):
        return val[0] if val else None
    return val


def _to_int_or(val, default=None):
    v = _first(val)
    if v in (None, '', 'None', 'none', 'null'):
        return default
    try:
        return int(v)
    except Exception:
        try:
            return int(str(v))
        except Exception:
            return default


def _to_float_or(val, default=None):
    """Convert value to float, return default if invalid."""
    v = _first(val)
    if v in (None, '', 'None', 'none', 'null'):
        return default
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v))
        except Exception:
            return default


def _map_gp(val):
    """Map various input forms to 'S' or 'N' for GERAPRODUCAO; returns None when unspecified/invalid."""
    if val in (None, '', 'None', 'none', 'null'):
        return None
    try:
        s = str(val).strip().upper()
    except Exception:
        return None
    if s in ('S', 'N'):
        return s
    if s in ('TRUE', '1', 'YES', 'ON'):
        return 'S'
    if s in ('FALSE', '0', 'NO', 'OFF'):
        return 'N'
    return None


def packing_central_validar(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return compras_central(request)
    form = {
    'codemp': _first(request.POST.get('codemp')) or '1',
    'codparc': _first(request.POST.get('codparc')) or '',
    'codtipoper': _first(request.POST.get('codtipoper')) or '',
    'codnat': _first(request.POST.get('codnat')) or '',
    'codcencus': _first(request.POST.get('codcencus')) or '',
    'codvend': _first(request.POST.get('codvend')) or '0',
    'codparctransp': _first(request.POST.get('codparctransp')) or '0',
    'codproj': _first(request.POST.get('codproj')) or '0',
        'dtneg': request.POST.get('dtneg') or '',
        'dtmov': request.POST.get('dtmov') or request.POST.get('dtneg') or '',
        'dtentsai': request.POST.get('dtentsai') or request.POST.get('dtneg') or '',
        'hrmov': request.POST.get('hrmov') or '',
        'nronota': request.POST.get('nronota') or '',
        'obs': request.POST.get('obs') or '',
    }
    # Fallback: if hidden codcencus missing but visible typed numeric, capture it
    if not form['codcencus']:
        vis = _first(request.POST.get('central_cencus'))
        if vis and str(vis).strip().isdigit():
            form['codcencus'] = str(int(str(vis).strip()))
    plan = plan_insert_cabecalho({
        'CODEMP': _to_int_or(form['codemp']),
        'CODPARC': _to_int_or(form['codparc']),
        'CODTIPOPER': _to_int_or(form['codtipoper']),
        'CODNAT': _to_int_or(form['codnat']),
        'CODCENCUS': _to_int_or(form['codcencus']),
        'CODVEND': _to_int_or(form['codvend'], 0),
        'CODPARCTRANSP': _to_int_or(form['codparctransp'], 0),
        'CODPROJ': _to_int_or(form['codproj'], 0),
        'DTNEG': _iso_to_br(form['dtneg']),
        'DTMOV': _iso_to_br(form['dtmov']),
        'DTENTSAI': _iso_to_br(form['dtentsai']),
        'HRMOV': form['hrmov'],
        'NUMNOTA': form['nronota'] or None,
        'OBSERVACAO': form['obs'] or None,
    })
    # Renderiza Central sem nunota, mas com os valores do formulário e o plano de validação
    produtos = listar_produtos(limit=100)
    parceiros = listar_parceiros(limit=100)
    ctx = {
        'nunota': None,
        'itens': [],
        'produtos': produtos,
        'parceiros': parceiros,
        'cab': None,
        'form': form,
        'plan': plan,
        'write_enabled': is_write_enabled(),
    }
    return render(request, "sankhya_integration/compras_central.html", ctx)


def packing_central_salvar(request: HttpRequest) -> HttpResponse:
    # Mantém política: sem sua autorização, não executa no banco.
    if request.method != 'POST':
        return compras_central(request)
    # Support JSON payloads (AJAX) as well as traditional form-encoded POSTs.
    payload_json = {}
    try:
        import json
        ctype = (request.META.get('CONTENT_TYPE') or '')
        if 'application/json' in ctype:
            payload_json = json.loads(request.body.decode('utf-8') or '{}')
        else:
            # If content-type not set but body contains JSON, try to parse defensively
            if request.body:
                try:
                    payload_json = json.loads(request.body.decode('utf-8') or '{}')
                except Exception:
                    payload_json = {}
    except Exception:
        payload_json = {}

    def gv(name, default=''):
        v = _first(request.POST.get(name))
        if v in (None, '', 'None', 'none', 'null'):
            v = payload_json.get(name)
        return v or default

    form = {
        'codemp': gv('codemp', '1'),
        'codparc': gv('codparc', ''),
        'codtipoper': gv('codtipoper', ''),
        'codnat': gv('codnat', ''),
        'codcencus': gv('codcencus', ''),
        'codvend': gv('codvend', '0'),
        'codparctransp': gv('codparctransp', '0'),
        'codproj': gv('codproj', '0'),
        'dtneg': gv('dtneg', ''),
        'dtmov': gv('dtmov') or gv('dtneg') or '',
        'dtentsai': gv('dtentsai') or gv('dtneg') or '',
        'hrmov': gv('hrmov', ''),
        'nronota': gv('nronota', ''),
        'obs': gv('obs', ''),
    }
    if not form['codcencus']:
        vis = _first(request.POST.get('central_cencus'))
        if vis and str(vis).strip().isdigit():
            form['codcencus'] = str(int(str(vis).strip()))
    
    # 🔗 Buscar NUNOTA_ORIGEM do payload para copiar NUMNOTA/NUMPEDIDO do TOP 11
    nunota_origem = gv('nunota_origem', None)
    print(f'🔍 [packing_central_salvar] NUNOTA_ORIGEM recebido do frontend: {nunota_origem}')
    print(f'🔍 [packing_central_salvar] Payload JSON completo: {payload_json}')
    
    payload = {
        'CODEMP': _to_int_or(form['codemp']),
        'CODPARC': _to_int_or(form['codparc']),
        'CODTIPOPER': _to_int_or(form['codtipoper']),
        'CODNAT': _to_int_or(form['codnat']),
        'CODCENCUS': _to_int_or(form['codcencus']),
        'CODVEND': _to_int_or(form['codvend'], 0),
        'CODPARCTRANSP': _to_int_or(form['codparctransp'], 0),
        'CODPROJ': _to_int_or(form['codproj'], 0),
        'DTNEG': _iso_to_br(form['dtneg']),
        'DTMOV': _iso_to_br(form['dtmov']),
        'DTENTSAI': _iso_to_br(form['dtentsai']),
        'HRMOV': form['hrmov'],
        'NUMNOTA': form['nronota'] or None,
        'OBSERVACAO': form['obs'] or None,
        'NUNOTA_ORIGEM': _to_int_or(nunota_origem, None),  # 🔗 Passar para insert_cabecalho_fast
    }
    # Usar versão OTIMIZADA para alta performance (~5x mais rápido)
    plan = insert_cabecalho_fast(payload, dry_run=False)
    # If called via AJAX (X-Requested-With) return JSON payload so clients can handle redirect
    is_xhr = (request.META.get('HTTP_X_REQUESTED_WITH', '') == 'XMLHttpRequest')
    if is_xhr:
        # Return JSON with status 200 on success, 400 on failure
        from django.http import JsonResponse
        status_code = 200 if plan.get('executed') else 400
        return JsonResponse(plan, status=status_code)
    # Non-AJAX default behaviour: redirect to central view when executed
    if plan.get('executed') and plan.get('nunota'):
        return redirect(f"/sankhya/packing/central/?nunota={plan['nunota']}")
    produtos = listar_produtos(limit=100)
    parceiros = listar_parceiros(limit=100)
    ctx = {
        'nunota': None,
        'itens': [],
        'produtos': produtos,
        'parceiros': parceiros,
        'cab': None,
        'form': form,
        'plan': plan,
        'write_enabled': is_write_enabled(),
    }
    return render(request, "sankhya_integration/compras_central.html", ctx)


def parceiros_search(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    try:
        limit = int(request.GET.get("limit", 10))
    except Exception:
        limit = 10
    try:
        from sankhya_integration.services.oracle_conn import buscar_parceiros as _buscar
    except Exception:
        _buscar = None
    if _buscar:
        rows = _buscar(q, limit=limit)
    else:
        # Fallback robusto: consulta direta no Oracle por código (prefixo) ou nome (LIKE)
        try:
            from sankhya_integration.services.oracle_conn import get_connection
            with get_connection() as conn:
                cur = conn.cursor()
                lim = max(1, int(limit))
                if q.isdigit():
                    qprefix = f"{q}%"
                    qpad = str(q).zfill(9) + "%"
                    try:
                        k = int(q)
                    except Exception:
                        k = None
                    cur.execute(
                        "SELECT CODPARC, NOMEPARC FROM ("
                        "  SELECT CODPARC, NOMEPARC FROM ("
                        "    SELECT CODPARC, NOMEPARC, 0 AS PRIO FROM TGFPAR WHERE (:k IS NOT NULL AND CODPARC = :k)"
                        "    UNION ALL "
                        "    SELECT CODPARC, NOMEPARC, 1 AS PRIO FROM TGFPAR "
                        "     WHERE (TO_CHAR(CODPARC) LIKE :qprefix OR LPAD(TO_CHAR(CODPARC), 9, '0') LIKE :qpad) "
                        "       AND (:k IS NULL OR CODPARC <> :k)"
                        "  ) t ORDER BY PRIO, CODPARC"
                        ") WHERE ROWNUM <= :lim",
                        k=k, qprefix=qprefix, qpad=qpad, lim=lim,
                    )
                else:
                    cur.execute(
                        "SELECT CODPARC, NOMEPARC FROM ("
                        "  SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE UPPER(NOMEPARC) LIKE :q ORDER BY NOMEPARC"
                        ") WHERE ROWNUM <= :lim",
                        q=f"%{q.upper()}%", lim=lim,
                    )
                rows = cur.fetchall()
        except Exception:
            # Último recurso: amostragem simples
            if q.isdigit():
                base = listar_parceiros(limit=limit * 50)
                rows = [(c, n) for c, n in base if str(c).startswith(q)][:limit]
            else:
                rows = listar_parceiros(limit=limit, nome=q)
    data = [{"codparc": int(c), "nomeparc": n} for c, n in rows]
    return JsonResponse({"results": data})


def top_search(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limit = int(request.GET.get("limit", 10))
    with get_connection() as conn:
        cur = conn.cursor()
        if q and q.isdigit():
            try:
                k = int(q)
            except Exception:
                k = None
            cur.execute(
                "SELECT CODTIPOPER, DESCROPER, TIPMOV FROM ("
                "  SELECT CODTIPOPER, DESCROPER, TIPMOV, DHALTER,"
                "         ROW_NUMBER() OVER (PARTITION BY CODTIPOPER ORDER BY DHALTER DESC) rn,"
                "         CASE WHEN CODTIPOPER = :k THEN 0 ELSE 1 END prio"
                "    FROM TGFTOP WHERE ATIVO='S'"
                " ) t"
                " WHERE rn=1 AND ( (:k IS NOT NULL AND CODTIPOPER = :k) OR TO_CHAR(CODTIPOPER) LIKE :p )"
                " ORDER BY prio, CODTIPOPER",
                k=k, p=f"{q}%",
            )
            rows = cur.fetchall()
        elif q:
            cur.execute(
                "SELECT CODTIPOPER, DESCROPER, TIPMOV FROM ("
                "  SELECT CODTIPOPER, DESCROPER, TIPMOV, DHALTER,"
                "         ROW_NUMBER() OVER (PARTITION BY CODTIPOPER ORDER BY DHALTER DESC) rn"
                "    FROM TGFTOP WHERE ATIVO='S'"
                " ) t"
                " WHERE rn=1 AND UPPER(DESCROPER) LIKE :q"
                " ORDER BY DESCROPER",
                q=f"%{q.upper()}%",
            )
            rows = cur.fetchall()
        else:
            cur.execute(
                "SELECT CODTIPOPER, DESCROPER, TIPMOV FROM ("
                "  SELECT CODTIPOPER, DESCROPER, TIPMOV, DHALTER,"
                "         ROW_NUMBER() OVER (PARTITION BY CODTIPOPER ORDER BY DHALTER DESC) rn"
                "    FROM TGFTOP WHERE ATIVO='S'"
                " ) t"
                " WHERE rn=1"
                " ORDER BY DHALTER DESC",
            )
            rows = cur.fetchmany(limit)
    data = [{"cod": int(c), "descr": (d or ""), "tipmov": (t or "")} for c, d, t in rows]
    return JsonResponse({"results": data})


def natureza_search(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limit = int(request.GET.get("limit", 10))
    rows = buscar_naturezas(q, limit=limit)
    return JsonResponse({"results": [{"cod": int(c), "descr": d} for c, d in rows]})


def cencus_search(request: HttpRequest) -> JsonResponse:
    q = request.GET.get("q", "").strip()
    limit = int(request.GET.get("limit", 10))
    rows = buscar_centros_resultado(q, limit=limit)
    return JsonResponse({"results": [{"cod": int(c), "descr": d} for c, d in rows]})


def produtos_search(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "")
    lim = int(request.GET.get("limit", 10))
    fabricante_mode = (request.GET.get("fabricante") or "").strip() not in ("", "0", "false", "False")
    cod_inn_raw = (request.GET.get("cod_innatura") or request.GET.get("cod_inn") or "").strip()
    fabricante_flt = None
    token_flt = None
    with get_connection() as conn:
        cur = conn.cursor()
        if fabricante_mode:
            # Auto-complete por FABRICANTE (distinto), ignorando códigos; LIKE no fabricante.
            try:
                cur.execute("ALTER SESSION SET NLS_COMP=LINGUISTIC")
                cur.execute("ALTER SESSION SET NLS_SORT=BINARY_AI")
            except Exception:
                pass
            if q:
                cur.execute(
                    "SELECT fabricante FROM ("
                    "  SELECT DISTINCT UPPER(NVL(FABRICANTE,'')) AS fabricante"
                    "    FROM TGFPRO WHERE UPPER(NVL(FABRICANTE,'')) LIKE :p AND TO_CHAR(CODGRUPOPROD) LIKE '1%'"
                    ") WHERE ROWNUM <= :lim",
                    p=f"%{q.upper()}%", lim=lim,
                )
            else:
                cur.execute(
                    "SELECT fabricante FROM ("
                    "  SELECT DISTINCT UPPER(NVL(FABRICANTE,'')) AS fabricante"
                    "    FROM TGFPRO WHERE TO_CHAR(CODGRUPOPROD) LIKE '1%'"
                    ") WHERE ROWNUM <= :lim",
                    lim=lim,
                )
            rows = [r[0] for r in cur.fetchall() if (r[0] or '').strip()]
            return JsonResponse({"results": [{"fabricante": f} for f in rows]})
        # Ensure accent-insensitive, case-insensitive comparisons for LIKE
        # Using linguistic comparisons makes 'MÉDIO' match 'medio', 'médio', etc.
        try:
            cur.execute("ALTER SESSION SET NLS_COMP=LINGUISTIC")
            cur.execute("ALTER SESSION SET NLS_SORT=BINARY_AI")
        except Exception:
            # If database doesn't allow session changes here, proceed without; queries will still work but be accent-sensitive
            pass
        # Detect context (InNatura) to constrain by FABRICANTE and optional token (e.g., TOMATE SALADA/ITALIANO)
        exclude_in_natura = False
        try:
            if cod_inn_raw and str(cod_inn_raw).isdigit():
                cod_inn = int(cod_inn_raw)
                cur.execute("SELECT UPPER(NVL(FABRICANTE,'')) AS FABRICANTE, UPPER(NVL(DESCRPROD,'')) AS DESCR FROM TGFPRO WHERE CODPROD=:p", p=cod_inn)
                r = cur.fetchone()
                if r:
                    fabricante_flt = (r[0] or '').strip() or None
                    descr_inn = (r[1] or '').strip()
                    exclude_in_natura = True  # we're in modal context; exclude 'IN NATURA' items from results
                    if fabricante_flt == 'TOMATE':
                        # Identify subtype by keywords in In Natura description
                        if 'SALADA' in descr_inn:
                            token_flt = 'SALADA'
                        elif 'ITALIANO' in descr_inn:
                            token_flt = 'ITALIANO'
                        # Extendable: elif 'CEREJA' in descr_inn: token_flt = 'CEREJA'
        except Exception:
            fabricante_flt = None; token_flt = None

        # New rule: when cod_innatura is provided but the In Natura product has no FABRICANTE, return empty list
        try:
            if cod_inn_raw and (not fabricante_flt):
                return JsonResponse({"results": []})
        except Exception:
            pass

        def _append_filters(base_sql: str, add_order: bool = False) -> tuple[str, dict]:
            sql = base_sql
            binds: dict = {}
            if fabricante_flt:
                sql += " AND UPPER(NVL(FABRICANTE,'')) = :fabricante"
                binds['fabricante'] = fabricante_flt
            if token_flt:
                sql += " AND UPPER(DESCRPROD) LIKE :tok"
                binds['tok'] = f"%{token_flt}%"
            # Exclude 'IN NATURA' from listing when in modal classification context
            if exclude_in_natura:
                sql += " AND UPPER(DESCRPROD) NOT LIKE '%IN NATURA%'"
            if add_order:
                sql += " ORDER BY DESCRPROD"
            return sql, binds

        rows = []
        if q.isdigit():
            k = int(q)
            # Exact code priority then prefix; apply same filters to both branches
            base1, b1 = _append_filters("SELECT CODPROD, DESCRPROD FROM TGFPRO WHERE CODPROD = :k AND TO_CHAR(CODGRUPOPROD) LIKE '1%'", False)
            base2, b2 = _append_filters("SELECT CODPROD, DESCRPROD FROM TGFPRO WHERE TO_CHAR(CODPROD) LIKE :p AND CODPROD <> :k AND TO_CHAR(CODGRUPOPROD) LIKE '1%'", False)
            sql = (
                "SELECT CODPROD, DESCRPROD FROM (" +
                base1 + " UNION ALL " + base2 +
                ") WHERE ROWNUM <= :lim"
            )
            binds = {'k': k, 'p': f"{q}%", 'lim': lim}
            binds.update(b1); binds.update(b2)
            cur.execute(sql, binds)
            rows = cur.fetchall()
        else:
            base, b = _append_filters("SELECT CODPROD, DESCRPROD FROM TGFPRO WHERE UPPER(DESCRPROD) LIKE :p AND TO_CHAR(CODGRUPOPROD) LIKE '1%'", True)
            sql = "SELECT CODPROD, DESCRPROD FROM (" + base + ") WHERE ROWNUM <= :lim"
            binds = {'p': f"%{q.upper()}%", 'lim': lim}
            binds.update(b)
            cur.execute(sql, binds)
            rows = cur.fetchall()
    return JsonResponse({"results": [{"cod": int(c), "descr": (d or '')} for c, d in rows]})


def next_lote(request: HttpRequest) -> JsonResponse:
    """Calcula o próximo lote no formato AAMMDD + HEX(incr, 5)
    - 6 dígitos decimais da data (AAMMDD)
    - 5 dígitos HEX do incremento com padding (zfill)
    - Total 11 caracteres, sem produto no código
    - Data base: DTNEG (YYYY-MM-DD)
    - Escopo do incremento: global no dia por CODPROD (todas as notas da data)
    Campo de lote no ERP: CODAGREGACAO
    """
    from datetime import datetime
    codprod_raw = request.GET.get('codprod')
    dtneg_str = (request.GET.get('dtneg') or '').strip()
    try:
        codprod = int(codprod_raw) if codprod_raw is not None else None
    except Exception:
        codprod = None
    if not codprod or not dtneg_str:
        return JsonResponse({"ok": False, "error": "Parâmetros obrigatórios: codprod e dtneg"}, status=400)
    try:
        dt = datetime.strptime(dtneg_str, '%Y-%m-%d').date()
    except Exception:
        return JsonResponse({"ok": False, "error": "dtneg inválida (use YYYY-MM-DD)"}, status=400)
    aammdd = f"{dt.year%100:02d}{dt.month:02d}{dt.day:02d}"
    # Prefixo somente com a data AAMMDD
    prefix = aammdd
    # Buscar lotes existentes pelo prefixo diretamente em TGFITE (independente do DTNEG atual do cabeçalho)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT CODAGREGACAO FROM TGFITE WHERE CODAGREGACAO LIKE :pfx AND CODAGREGACAO IS NOT NULL",
            pfx=f"{prefix}%",
        )
        rows = cur.fetchall()
    max_incr = 0
    preflen = len(prefix)
    for (ctrl,) in rows:
        s = (ctrl or '').strip().upper()
        if not s.startswith(prefix):
            continue
        if len(s) <= preflen:
            continue
        suf = s[preflen:]
        try:
            val = int(suf, 16)
        except Exception:
            continue
        if val > max_incr:
            max_incr = val
    next_incr = max_incr + 1
    incr_hex = format(next_incr, 'X').upper().zfill(5)
    lote = f"{prefix}{incr_hex}"
    if len(lote) > 11:
        return JsonResponse({
            "ok": False,
            "error": "Formato excede 11 caracteres",
            "aammdd": aammdd,
            "incremento": next_incr,
            "incremento_hex": incr_hex,
            "tamanho": len(lote)
        }, status=409)
    return JsonResponse({"ok": True, "lote": lote, "prefix": prefix, "incremento": next_incr, "incremento_hex": incr_hex})


def vendedor_search(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "")
    lim = int(request.GET.get("limit", 10))
    with get_connection() as conn:
        cur = conn.cursor()
        if q.isdigit():
            k = int(q)
            cur.execute(
                "SELECT CODVEND, APELIDO FROM ("
                "  SELECT CODVEND, APELIDO FROM TGFVEN WHERE CODVEND = :k AND ATIVO='S'"
                "  UNION ALL "
                "  SELECT CODVEND, APELIDO FROM TGFVEN WHERE TO_CHAR(CODVEND) LIKE :p AND CODVEND <> :k AND ATIVO='S'"
                ") WHERE ROWNUM <= :lim",
                k=k, p=f"{q}%", lim=lim,
            )
        else:
            cur.execute(
                "SELECT CODVEND, APELIDO FROM ("
                "  SELECT CODVEND, APELIDO FROM TGFVEN WHERE UPPER(APELIDO) LIKE :p AND ATIVO='S' ORDER BY APELIDO"
                ") WHERE ROWNUM <= :lim",
                p=f"%{q.upper()}%", lim=lim,
            )
        rows = cur.fetchall()
    return JsonResponse({"results": [{"cod": int(c), "descr": (d or '')} for c, d in rows]})


def transportadora_search(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "")
    lim = int(request.GET.get("limit", 10))
    with get_connection() as conn:
        cur = conn.cursor()
        if q.isdigit():
            k = int(q)
            cur.execute(
                "SELECT CODPARC, NOMEPARC FROM ("
                "  SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE CODPARC = :k AND ATIVO='S' AND TRANSPORTADORA='S'"
                "  UNION ALL "
                "  SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE TO_CHAR(CODPARC) LIKE :p AND CODPARC <> :k AND ATIVO='S' AND TRANSPORTADORA='S'"
                ") WHERE ROWNUM <= :lim",
                k=k, p=f"{q}%", lim=lim,
            )
        else:
            cur.execute(
                "SELECT CODPARC, NOMEPARC FROM ("
                "  SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE UPPER(NOMEPARC) LIKE :p AND ATIVO='S' AND TRANSPORTADORA='S' ORDER BY NOMEPARC"
                ") WHERE ROWNUM <= :lim",
                p=f"%{q.upper()}%", lim=lim,
            )
        rows = cur.fetchall()
    return JsonResponse({"results": [{"cod": int(c), "descr": (d or '')} for c, d in rows]})


def empresa_search(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "")
    lim = int(request.GET.get("limit", 10))
    with get_connection() as conn:
        cur = conn.cursor()
        if q.isdigit():
            k = int(q)
            cur.execute(
                "SELECT CODEMP, NVL(NM, TO_CHAR(CODEMP)) FROM ("
                "  SELECT CODEMP, NOMEFANTASIA AS NM FROM TSIEMP WHERE CODEMP = :k"
                "  UNION ALL"
                "  SELECT CODEMP, NOMEFANTASIA AS NM FROM TSIEMP WHERE TO_CHAR(CODEMP) LIKE :p AND CODEMP <> :k"
                ") WHERE ROWNUM <= :lim",
                k=k, p=f"{q}%", lim=lim,
            )
        else:
            cur.execute(
                "SELECT CODEMP, NM FROM ("
                "  SELECT CODEMP, NOMEFANTASIA AS NM FROM TSIEMP WHERE UPPER(NOMEFANTASIA) LIKE :p ORDER BY NM"
                ") WHERE ROWNUM <= :lim",
                p=f"%{q.upper()}%", lim=lim,
            )
        rows = cur.fetchall()
    return JsonResponse({"results": [{"cod": int(c), "descr": (d or '')} for c, d in rows]})

def vol_search(request: HttpRequest) -> JsonResponse:
    q = (request.GET.get("q", "").strip() or "").upper()
    lim = int(request.GET.get("limit", 10))
    # Optional: constrain by product code to only base + alternatives configured for that product
    codprod_raw = (request.GET.get('codprod') or '').strip()
    codprod = None
    try:
        if codprod_raw and codprod_raw.isdigit():
            codprod = int(codprod_raw)
    except Exception:
        codprod = None
    with get_connection() as conn:
        cur = conn.cursor()
        if codprod is not None:
            # Restrict to base unit for product plus alternatives from TGFVOA for that product
            if q:
                cur.execute(
                    "SELECT CODVOL, DESCRVOL FROM ("
                    "  SELECT p.CODVOL AS CODVOL, v.DESCRVOL, 0 PRIO FROM TGFPRO p LEFT JOIN TGFVOL v ON UPPER(v.CODVOL)=UPPER(p.CODVOL) WHERE p.CODPROD=:cp AND (UPPER(p.CODVOL)=:k OR UPPER(p.CODVOL) LIKE :p OR UPPER(v.DESCRVOL) LIKE :d)"
                    "  UNION ALL"
                    "  SELECT a.CODVOL, v.DESCRVOL, 1 PRIO FROM TGFVOA a LEFT JOIN TGFVOL v ON UPPER(v.CODVOL)=UPPER(a.CODVOL) WHERE a.CODPROD=:cp AND (UPPER(a.CODVOL)=:k OR UPPER(a.CODVOL) LIKE :p OR UPPER(v.DESCRVOL) LIKE :d)"
                    ") WHERE ROWNUM <= :lim ORDER BY PRIO, CODVOL",
                    cp=codprod, k=q, p=f"{q}%", d=f"%{q}%", lim=lim,
                )
            else:
                cur.execute(
                    "SELECT CODVOL, DESCRVOL FROM ("
                    "  SELECT p.CODVOL AS CODVOL, v.DESCRVOL, 0 PRIO FROM TGFPRO p LEFT JOIN TGFVOL v ON UPPER(v.CODVOL)=UPPER(p.CODVOL) WHERE p.CODPROD=:cp"
                    "  UNION ALL"
                    "  SELECT a.CODVOL, v.DESCRVOL, 1 PRIO FROM TGFVOA a LEFT JOIN TGFVOL v ON UPPER(v.CODVOL)=UPPER(a.CODVOL) WHERE a.CODPROD=:cp"
                    ") WHERE ROWNUM <= :lim ORDER BY PRIO, CODVOL",
                    cp=codprod, lim=lim,
                )
        else:
            if q:
                # Prioriza código exato/prefixo, depois descrição
                cur.execute(
                    "SELECT CODVOL, DESCRVOL FROM ("
                    "  SELECT CODVOL, DESCRVOL, 0 PRIO FROM TGFVOL WHERE UPPER(CODVOL) = :k"
                    "  UNION ALL"
                    "  SELECT CODVOL, DESCRVOL, 1 PRIO FROM TGFVOL WHERE UPPER(CODVOL) LIKE :p"
                    "  UNION ALL"
                    "  SELECT CODVOL, DESCRVOL, 2 PRIO FROM TGFVOL WHERE UPPER(DESCRVOL) LIKE :d"
                    ") WHERE ROWNUM <= :lim ORDER BY PRIO, CODVOL",
                    k=q, p=f"{q}%", d=f"%{q}%", lim=lim,
                )
            else:
                cur.execute(
                    "SELECT CODVOL, DESCRVOL FROM (SELECT CODVOL, DESCRVOL FROM TGFVOL ORDER BY CODVOL) WHERE ROWNUM <= :lim",
                    lim=lim,
                )
        rows = cur.fetchall()
    return JsonResponse({"results": [{"cod": (c or ""), "descr": (d or "")} for c, d in rows]})

def lote_search(request: HttpRequest) -> JsonResponse:
    """Pesquisar lotes (CODAGREGACAO) por prefixo, para typeahead do filtro.
    Query: q (string), limit (default 10)
    Returns: { results: [ { cod: CODAGREGACAO, descr: '' } ] }
    """
    q = (request.GET.get('q') or '').strip()
    try:
        lim = int(request.GET.get('limit', 10))
    except Exception:
        lim = 10
    if not q:
        return JsonResponse({"results": []})
    with get_connection() as conn:
        cur = conn.cursor()
        # Buscar por substring, case-insensitive
        cur.execute(
            "SELECT CODAGREGACAO FROM (\n"
            "  SELECT DISTINCT CODAGREGACAO FROM TGFITE\n"
            "   WHERE CODAGREGACAO IS NOT NULL AND UPPER(CODAGREGACAO) LIKE :p\n"
            "   ORDER BY CODAGREGACAO\n"
            ") WHERE ROWNUM <= :lim",
            p=f"%{q.upper()}%", lim=max(1, lim)
        )
        rows = cur.fetchall()
    data = [{"cod": (c or ""), "descr": ""} for (c,) in rows]
    return JsonResponse({"results": data})


def produto_volume(request: HttpRequest) -> JsonResponse:
    """Retorna o peso padrão de um volume alternativo para um produto."""
    codprod = request.GET.get('codprod', '').strip()
    codvol = request.GET.get('codvol', '').strip()
    
    print(f"[PESO_BACKEND] Requisição recebida: codprod={codprod}, codvol={codvol}")
    
    if not codprod or not codvol:
        return JsonResponse({"ok": False, "error": "codprod e codvol são obrigatórios"}, status=400)
    
    try:
        codprod_int = int(codprod)
    except ValueError:
        print(f"[PESO_BACKEND] Erro: codprod inválido: {codprod}")
        return JsonResponse({"ok": False, "error": "codprod inválido"}, status=400)
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Buscar peso SEMPRE em TGFVOA, independente se é volume base ou alternativo
            query = """
                SELECT QUANTIDADE 
                FROM TGFVOA 
                WHERE CODPROD = :codprod 
                  AND UPPER(CODVOL) = :codvol
                """
            print(f"[PESO_BACKEND] Buscando em TGFVOA: codprod={codprod_int}, codvol={codvol.upper()}")
            cur.execute(query, codprod=codprod_int, codvol=codvol.upper())
            row = cur.fetchone()
            
            if row and row[0] is not None:
                peso = float(row[0])
                print(f"[PESO_BACKEND] Peso encontrado em TGFVOA.QUANTIDADE: {peso}")
                return JsonResponse({"ok": True, "peso": peso})
            else:
                # Se não encontrou em TGFVOA, verificar se é o volume base do produto
                print(f"[PESO_BACKEND] Não encontrado em TGFVOA, verificando se é volume base...")
                cur.execute(
                    "SELECT CODVOL FROM TGFPRO WHERE CODPROD = :cp",
                    cp=codprod_int
                )
                base_row = cur.fetchone()
                print(f"[PESO_BACKEND] Volume base do produto: {base_row}")
                
                if base_row and str(base_row[0]).upper() == codvol.upper():
                    # É o volume base, retornar peso = 1
                    print(f"[PESO_BACKEND] É volume base, retornando peso=1.0")
                    return JsonResponse({"ok": True, "peso": 1.0})
                else:
                    # Não é volume base e não está em TGFVOA
                    print(f"[PESO_BACKEND] Volume {codvol} não é base e não está em TGFVOA")
                    return JsonResponse({"ok": False, "error": f"Volume {codvol} não cadastrado em TGFVOA para este produto"}, status=404)
    except Exception as e:
        print(f"[PESO_BACKEND] Erro: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def produto_codvol(request: HttpRequest) -> JsonResponse:
    """Retorna o CODVOL alternativo de TGFVOA (para exibição) e base de TGFPRO."""
    codprod = request.GET.get('codprod', '').strip()
    
    if not codprod:
        return JsonResponse({"ok": False, "error": "codprod é obrigatório"}, status=400)
    
    try:
        codprod_int = int(codprod)
    except ValueError:
        return JsonResponse({"ok": False, "error": "codprod inválido"}, status=400)
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Buscar unidade alternativa de TGFVOA (para exibição)
            query_voa = """
                SELECT CODVOL 
                FROM TGFVOA 
                WHERE CODPROD = :codprod 
                  AND CODVOL != 'KG'
                ORDER BY CODVOL
            """
            cur.execute(query_voa, codprod=codprod_int)
            row = cur.fetchone()
            
            codvol_display = None
            if row and row[0]:
                codvol_display = str(row[0]).strip()
            
            # Buscar CODVOL base de TGFPRO
            query_pro = """
                SELECT CODVOL 
                FROM TGFPRO 
                WHERE CODPROD = :codprod
            """
            cur.execute(query_pro, codprod=codprod_int)
            row = cur.fetchone()
            
            codvol_base = None
            if row and row[0]:
                codvol_base = str(row[0]).strip()
            
            if codvol_display or codvol_base:
                return JsonResponse({
                    "ok": True, 
                    "codvol": codvol_display or codvol_base,  # Para exibir no campo Vol
                    "codvol_base": codvol_base,  # KG (para salvar)
                    "source": "TGFVOA" if codvol_display else "TGFPRO"
                })
            
            # Não encontrou
            return JsonResponse({"ok": False, "error": "CODVOL não encontrado para este produto"}, status=404)
            
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def header_update(request: HttpRequest) -> JsonResponse:
    """Atualiza campos do cabeçalho TGFCAB via JSON."""
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"JSON inválido: {str(e)}"}, status=400)
    
    nunota = _to_int_or(payload.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "NUNOTA obrigatório"}, status=400)
    
    plan = update_cabecalho({
        'NUNOTA': nunota,
        'NUMNOTA': payload.get('nronota'),
        'DTNEG': payload.get('dtneg'),
        'DTMOV': payload.get('dtmov'),
        'DTENTSAI': payload.get('dtentsai'),
        'HRMOV': payload.get('hrmov'),
    # CODEMP não editável por política atual
        'CODPARC': _to_int_or(payload.get('codparc')),
        'CODTIPOPER': _to_int_or(payload.get('codtipoper')),
    # Natureza e Centro Resultado não editáveis por política atual
        'OBSERVACAO': payload.get('obs'),
        'STATUSNOTA': payload.get('statusnota'),
        # Novo: atualizar total descartado quando informado (aceita decimal)
        'QTDBATIDAS': _to_float_or(payload.get('qtdbatidas')),
    }, dry_run=False)
    
    # Melhorar resposta de erro
    if not plan.get('executed'):
        errors = plan.get('errors', [])
        error_msg = errors[0] if errors else 'Falha ao atualizar cabeçalho'
        return JsonResponse({
            "ok": False,
            "error": error_msg,
            "errors": errors,
            "db_error": plan.get('db_error')
        }, status=400)
    
    return JsonResponse(plan, status=200)


def header_status_toggle(request: HttpRequest) -> JsonResponse:
    """Atualiza PENDENTE e DTALTER do TGFCAB (NÃO atualiza STATUSNOTA).
    Quando marcado como finalizado:
    - PENDENTE = 'N'
    - DTALTER = SYSDATE
    
    Quando desmarcado:
    - PENDENTE = 'S'
    - DTALTER = SYSDATE
    
    POST JSON: { nunota: int, status: 'A'|'L' }
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    nunota = _to_int_or(payload.get('nunota'))
    status = (payload.get('status') or '').strip().upper()
    if not nunota:
        return JsonResponse({"ok": False, "error": "nunota obrigatório"}, status=400)
    if status not in ('A','L'):
        return JsonResponse({"ok": False, "error": "status inválido (use 'A' ou 'L')"}, status=400)
    try:
        # Definir PENDENTE baseado no status (L=finalizado, A=em andamento)
        pendente = 'N' if status == 'L' else 'S'
        
        # Atualizar apenas PENDENTE e DTALTER (NÃO atualiza STATUSNOTA)
        from sankhya_integration.services.oracle_conn import get_connection
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE TGFCAB 
                SET PENDENTE = :pendente,
                    DTALTER = SYSDATE
                WHERE NUNOTA = :nunota
            """, pendente=pendente, nunota=nunota)
            
            rows_updated = cur.rowcount
            conn.commit()
            
            ok = rows_updated > 0
            result = {
                "ok": ok,
                "executed": ok,
                "rows_updated": rows_updated,
                "nunota": nunota,
                "pendente": pendente,
                "message": f"Atualizado: PENDENTE='{pendente}', DTALTER=SYSDATE"
            }
            return JsonResponse(result, status=200 if ok else 400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def header_status_get(request: HttpRequest) -> JsonResponse:
    """GET PENDENTE atual do TGFCAB para um NUNOTA."""
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        nunota = int(request.GET.get('nunota') or '0')
    except Exception:
        return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)
    if not nunota:
        return JsonResponse({"ok": False, "error": "nunota obrigatório"}, status=400)
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT PENDENTE FROM TGFCAB WHERE NUNOTA=:n", n=nunota)
            row = cur.fetchone()
            if not row:
                return JsonResponse({"ok": False, "error": "Cabeçalho não encontrado"}, status=404)
            pendente = (row[0] or '').strip().upper()
            return JsonResponse({"ok": True, "nunota": nunota, "pendente": pendente})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def header_plan(request: HttpRequest) -> JsonResponse:
    """Return a JSON plan (SQL preview) for inserting/updating a header (TGFCAB).
    Accepts JSON POST with similar fields to `packing_central_validar` and returns the plan from `plan_insert_cabecalho`.
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    d = {
        'CODEMP': _to_int_or(payload.get('codemp')),
        'CODPARC': _to_int_or(payload.get('codparc')),
        'CODTIPOPER': _to_int_or(payload.get('codtipoper')),
        'CODNAT': _to_int_or(payload.get('codnat')),
        'CODCENCUS': _to_int_or(payload.get('codcencus')),
        'CODVEND': _to_int_or(payload.get('codvend'), 0),
        'CODPARCTRANSP': _to_int_or(payload.get('codparctransp'), 0),
        'CODPROJ': _to_int_or(payload.get('codproj'), 0),
        'DTNEG': _iso_to_br(payload.get('dtneg')),
        'DTMOV': _iso_to_br(payload.get('dtmov') or payload.get('dtneg')),
        'DTENTSAI': _iso_to_br(payload.get('dtentsai') or payload.get('dtneg')),
        'HRMOV': payload.get('hrmov'),
        'NUMNOTA': payload.get('nronota') or None,
        'OBSERVACAO': payload.get('obs') or None,
    }
    try:
        plan = plan_insert_cabecalho(d)
        plan['write_enabled'] = is_write_enabled()
        status_code = 200 if plan.get('ok') or plan.get('executed') else 400
        return JsonResponse(plan, status=status_code)
    except Exception as e:
        logger.exception('header_plan failed')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def item_plan(request: HttpRequest) -> JsonResponse:
    """Endpoint JSON para validar/planejar um item da nota."""
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    
    print(f"🔍🔍🔍 ITEM_PLAN RECEBEU PAYLOAD: {payload}")
    
    def _map_gp(val):
        if val in (None, '', 'None', 'none', 'null'):
            return None
        s = str(val).strip().upper()
        if s in ('S','N'):
            return s
        if s in ('TRUE','1','YES','ON'):
            return 'S'
        if s in ('FALSE','0','NO','OFF'):
            return 'N'
        return None

    plan = plan_insert_item({
        'NUNOTA': _to_int_or(payload.get('nunota')),
        'CODPROD': _to_int_or(payload.get('codprod')),
        'QTDNEG': payload.get('qtdneg'),
        'VLRUNIT': payload.get('vlrunit'),
        'PESO': payload.get('peso'),
        'CODVOL': payload.get('codvol') or 'UN',
        'CODLOCALORIG': _to_int_or(payload.get('codlocal'), 101),
        'CODAGREGACAO': ((payload.get('codagregacao') or payload.get('controle') or '')).strip() or None,
        'OBSERVACAO': (payload.get('obs') or '').strip() or None,
        # Classificação (GERAPRODUCAO) opcional
        'GERAPRODUCAO': _map_gp(payload.get('geraproducao')),
    })
    status_code = 200 if plan.get('ok') else 400
    return JsonResponse(plan, status=status_code)


def item_list(request: HttpRequest) -> JsonResponse:
    """Endpoint GET JSON to list items of a given nunota.
    Query param: nunota (int)
    Returns: { ok: true, items: [ { sequencia, cod, descr, qtd, vlu, obs } ] }
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        nunota = int(request.GET.get('nunota'))
    except Exception:
        return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)
    try:
        rows = listar_itens_da_nota(nunota) or []
        out = []
        for r in rows:
            # expected SQL now may include GERAPRODUCAO at index 10
            cont = r[0] if len(r) > 0 else None
            seq = r[1] if len(r) > 1 else None
            codp = r[2] if len(r) > 2 else None
            descrp = r[3] if len(r) > 3 else ''
            codvol = r[4] if len(r) > 4 else ''
            qtdneg = r[5] if len(r) > 5 else None
            peso = r[6] if len(r) > 6 else None
            vlrunit = r[7] if len(r) > 7 else None
            vltot = r[8] if len(r) > 8 else None
            obs = r[9] if len(r) > 9 else ''
            gp = r[10] if len(r) > 10 else None
            total = None
            try:
                if qtdneg is not None and peso is not None:
                    total = float(qtdneg) * float(peso)
            except Exception:
                total = None
            # Ajustar quantidade para exibição quando CODVOL for alternativo (QTD armazenada na base)
            disp_qtd = qtdneg
            try:
                if codp is not None and codvol:
                    # Lazy import to avoid circular import issues during fallback
                    from sankhya_integration.services.oracle_conn import get_base_unit_and_factor
                    base, fator = get_base_unit_and_factor(int(codp), str(codvol))
                    if base and str(base).upper() != str(codvol).upper() and fator and float(fator) > 0:
                        try:
                            disp_qtd = float(qtdneg or 0) / float(fator)
                        except Exception:
                            disp_qtd = qtdneg
            except Exception:
                disp_qtd = qtdneg

            out.append({
                'nunota': int(nunota),
                'sequencia': int(seq) if seq is not None else None,
                'cod': int(codp) if codp is not None else None,
                'descr': descrp or '',
                'lote': cont or '',
                'codvol': (codvol or ''),
                'qtd': float(disp_qtd or 0),
                'peso': float(peso) if peso is not None else None,
                'total': float(total) if total is not None else None,
                'totalkg': float(qtdneg or 0),  # QTDNEG real em KG (sem conversão)
                'vlu': float(vlrunit or 0),
                'vlt': float(vltot or 0),
                'obs': obs or '',
                'classifica': (None if gp is None else (str(gp).upper() != 'N')),
                'geraproducao': (None if gp is None else str(gp).upper()),
            })
        try:
            print(f"🔍🔍 ITEM_LIST - Returning {len(out)} items for nunota={nunota}")
            # print sample item to help debug missing totalkg
            if out:
                import pprint
                pprint.pprint(out[0])
        except Exception:
            pass
        return JsonResponse({"ok": True, "items": out})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def unit_factor_debug(request: HttpRequest) -> JsonResponse:
    """GET /sankhya/unit/debug/?codprod=...&codvol=...
    Retorna base (TGFPRO.CODVOL) e fator (TGFVOA.FATOR) para diagnóstico rápido.
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        codprod = int(request.GET.get('codprod'))
    except Exception:
        return JsonResponse({"ok": False, "error": "codprod inválido"}, status=400)
    codvol = (request.GET.get('codvol') or '').strip().upper() or None
    try:
        from sankhya_integration.services.oracle_conn import get_base_unit_and_factor
        base, fator = get_base_unit_and_factor(codprod, codvol or '')
        return JsonResponse({"ok": True, "codprod": codprod, "codvol": codvol, "base": base, "fator": fator})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def unit_factor_debug_details(request: HttpRequest) -> JsonResponse:
    """GET /sankhya/unit/debug/details/?codprod=...&codvol=...
    Retorna as colunas de TGFVOA e os valores da linha (se existir) para diagnóstico.
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        codprod = int(request.GET.get('codprod'))
    except Exception:
        return JsonResponse({"ok": False, "error": "codprod inválido"}, status=400)
    codvol = (request.GET.get('codvol') or '').strip().upper() or None
    try:
        from sankhya_integration.services.oracle_conn import fetch_tgfvoa_details
        data = fetch_tgfvoa_details(codprod, codvol or '')
        return JsonResponse(data, status=200 if data.get('ok') else 500)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def item_debug_tgfite(request: HttpRequest) -> HttpResponse:
    """GET /sankhya/item/debug/tgfite/?nunota=...&a=codprodA&b=codprodB
    Retorna uma tabela Markdown com as diferenças entre os dois itens da TGFITE.
    """
    if request.method != 'GET':
        return HttpResponse("Use GET", status=405)
    try:
        nunota = int(request.GET.get('nunota'))
        a = int(request.GET.get('a'))
        b = int(request.GET.get('b'))
    except Exception:
        return HttpResponse("Parâmetros inválidos. Use nunota, a, b.", status=400)
    data = fetch_tgfite_details(nunota, [a, b])
    if not data.get('ok'):
        return HttpResponse(f"Erro ao consultar TGFITE: {data.get('error')}", status=500)
    cols = data.get('columns') or []
    rows = data.get('rows') or []
    # map por CODPROD (se houver duplicidade, pega a primeira)
    by_cod = {}
    # detectar índice de CODPROD na lista de colunas
    try:
        idx_cod = cols.index('CODPROD')
    except ValueError:
        idx_cod = None
    for r in rows:
        key = r[idx_cod] if (idx_cod is not None and idx_cod < len(r)) else None
        if key is not None and key not in by_cod:
            by_cod[key] = r
    ra = by_cod.get(a)
    rb = by_cod.get(b)
    if not ra or not rb:
        return HttpResponse("Não encontrei ambos os itens em TGFITE.", status=404)

    # explicações curtas para algumas colunas comuns
    explanations = {
        'NUNOTA': 'Número único do documento (cabeçalho) — FK para TGFCAB.',
        'SEQUENCIA': 'Sequência do item dentro da nota.',
        'CODPROD': 'Código do produto.',
        'CODVOL': 'Unidade de volume do item (pode ser alternativa).',
        'QTDNEG': 'Quantidade negociada (armazenada na unidade base do produto).',
        'PESO': 'Peso informado para o item (quando aplicável).',
        'VLRUNIT': 'Valor unitário.',
        'VLRTOT': 'Valor total (QTDNEG × VLRUNIT).',
        'CODLOCALORIG': 'Local de estoque de origem.',
        'CODAGREGACAO': 'Lote/Controle do item (chave do nosso fluxo).',
        'NUTAB': 'Número da tabela de preço aplicada ao item.',
        'GERAPRODUCAO': 'Indica se o item gera classificação/produção (S/N).',
        'PENDENTE': 'Status de pendência do item.',
        'STATUSNOTA': 'Status do item (herda/espelha do cabeçalho).',
    }

    # coletar apenas colunas onde os valores diferem
    diffs = []
    for i, col in enumerate(cols):
        va = ra[i] if i < len(ra) else None
        vb = rb[i] if i < len(rb) else None
        # normalizar vazios para facilitar comparação visual
        if (va is None or str(va).strip() == '') and (vb is None or str(vb).strip() == ''):
            continue
        if (va is None) != (vb is None) or str(va) != str(vb):
            diffs.append((col, va, vb, explanations.get(col)))

    # construir Markdown
    fmt = (request.GET.get('fmt') or 'md').lower()
    if fmt == 'plain':
        # monospaced, colunas alinhadas por largura máxima
        header = [
            f"Comparação TGFITE — NUNOTA {nunota}: {a} vs {b}",
            ""
        ]
        rows_plain = [(col, '' if va is None else str(va), '' if vb is None else str(vb), '' if not exp else exp) for col, va, vb, exp in diffs]
        # calcular larguras
        col_names = ('Coluna', f'Produto {a}', f'Produto {b}', 'Explicação')
        widths = [len(col_names[0]), len(col_names[1]), len(col_names[2]), len(col_names[3])]
        for c, va, vb, se in rows_plain:
            widths[0] = max(widths[0], len(c))
            widths[1] = max(widths[1], len(va))
            widths[2] = max(widths[2], len(vb))
            widths[3] = max(widths[3], len(se))
        def pad(s, w, align='left'):
            s = s or ''
            if align == 'right':
                return s.rjust(w)
            return s.ljust(w)
        sep = '+-' + '-+-'.join('-' * w for w in widths) + '-+'
        lines = header + [
            sep,
            '| ' + ' | '.join([
                pad(col_names[0], widths[0]), pad(col_names[1], widths[1]), pad(col_names[2], widths[2]), pad(col_names[3], widths[3])
            ]) + ' |',
            sep,
        ]
        for c, va, vb, se in rows_plain:
            lines.append('| ' + ' | '.join([
                pad(c, widths[0]), pad(va, widths[1], 'right'), pad(vb, widths[2], 'right'), pad(se, widths[3])
            ]) + ' |')
        lines.append(sep)
        txt = "\n".join(lines)
        return HttpResponse(txt, content_type="text/plain; charset=utf-8")
    else:
        # Markdown (padrão)
        lines = []
        lines.append(f"Comparação TGFITE — NUNOTA {nunota}: {a} vs {b}")
        lines.append("")
        lines.append("| Coluna | Produto " + str(a) + " | Produto " + str(b) + " | Explicação |")
        lines.append("|---|---:|---:|---|")
        for col, va, vb, exp in diffs:
            sa = ('' if va is None else str(va))
            sb = ('' if vb is None else str(vb))
            se = ('' if not exp else exp)
            # escapar barras verticais
            sa = sa.replace('|','\\|')
            sb = sb.replace('|','\\|')
            se = se.replace('|','\\|')
            lines.append(f"| {col} | {sa} | {sb} | {se} |")
        md = "\n".join(lines)
        return HttpResponse(md, content_type="text/plain; charset=utf-8")


def item_weight_debug(request: HttpRequest) -> JsonResponse:
    """GET /sankhya/item/weight/debug/?nunota=...&seq=...
    Retorna diagnóstico de pesos para o item: campos brutos (TGFITE/TGFPRO/TGFVOA/TGFCAB),
    unidade base+fator e estimativas de peso líquido/bruto.
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        nunota = int(request.GET.get('nunota'))
        seq = int(request.GET.get('seq'))
    except Exception:
        return JsonResponse({"ok": False, "error": "Parâmetros inválidos. Use nunota e seq."}, status=400)
    try:
        from sankhya_integration.services.oracle_conn import weight_diagnostics
        data = weight_diagnostics(nunota, seq)
        return JsonResponse(data, status=200 if data.get('ok') else 500)
    except Exception as e:
        logger.exception('item_weight_debug failed')
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def item_save(request: HttpRequest) -> JsonResponse:
    """Endpoint JSON para gravar um item na TGFITE."""
    from sankhya_integration.services.oracle_conn import get_connection
    
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    
    print(f"🔍🔍🔍 ITEM_SAVE RECEBEU PAYLOAD: {payload}")
    
    # Helper: detect TOP of the destination NUNOTA and the classification TOP value
    def _get_nota_top(nun):
        try:
            from sankhya_integration.services.oracle_conn import get_params as _get_params
            top_class = _get_params().get('TOP_CLASS')
        except Exception:
            top_class = None
        codtop = None
        try:
            n = _to_int_or(payload.get('nunota')) if nun is None else int(nun)
        except Exception:
            n = None
        if n:
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA=:n", n=n)
                    row = cur.fetchone()
                    if row:
                        codtop = row[0]
            except Exception:
                codtop = None
        return codtop, top_class
    # If payload contains 'sequencia', treat as update of existing item
    seq = _to_int_or(payload.get('sequencia'))
    if seq:
        codtop, top_class = _get_nota_top(_to_int_or(payload.get('nunota')))
        # DEBUG: Log do payload recebido
        print(f'\n🔍 ========== UPDATE ITEM DEBUG ==========')
        print(f'🔍 Payload recebido do frontend: {payload}')
        
        # For classification notes (TOP 26), enforce lote immutability: do NOT allow changing CODAGREGACAO on update
        update_dict = {
            'NUNOTA': _to_int_or(payload.get('nunota')),
            'SEQUENCIA': seq,
            'CODPROD': _to_int_or(payload.get('codprod')),
            'QTDNEG': payload.get('qtdneg'),  # Total kg - já vem em KG
            'VLRUNIT': payload.get('vlrunit'),
            'VLRTOT': payload.get('vlrtot'),  # Incluir VLRTOT para itens não classificáveis
            'PRECOBASE': payload.get('preco_inicial'),
            'PESO': payload.get('peso'),
            'CODVOL': payload.get('codvol') or None,  # Manter unidade alternativa (CX)
            'CODLOCALORIG': _to_int_or(payload.get('codlocal'), None),
            'OBSERVACAO': (payload.get('obs') or '').strip() or None,
            # Atualizar GERAPRODUCAO se informado
            'GERAPRODUCAO': _map_gp(payload.get('geraproducao')),
        }
        print(f'🔍 Update dict montado: {update_dict}')
        
        try:
            if not (codtop is not None and top_class is not None and int(codtop) == int(top_class)):
                # Only allow CODAGREGACAO update when not a classification TOP
                val_ctrl = (payload.get('codagregacao') or payload.get('controle') or '').strip()
                update_dict['CODAGREGACAO'] = val_ctrl or None
        except Exception:
            # If we can't determine, be conservative and do not include CODAGREGACAO in update
            pass
        plan = update_item(update_dict, dry_run=False)
        print(f'🔍 Resultado do plan: {plan}')
        
        # Verificar o valor REAL que ficou gravado no banco
        if plan.get('executed'):
            from .services.oracle_conn import get_connection
            check_sql = """
                SELECT QTDNEG, CODVOL, PESO 
                FROM TGFITE 
                WHERE NUNOTA = :NUNOTA AND SEQUENCIA = :SEQUENCIA
            """
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(check_sql, {'NUNOTA': update_dict['NUNOTA'], 'SEQUENCIA': update_dict['SEQUENCIA']})
                row = cur.fetchone()
                if row:
                    print(f'🔍 Valor REAL gravado no banco: QTDNEG={row[0]}, CODVOL={row[1]}, PESO={row[2]}')
                cur.close()
        print(f'🔍 ========================================\n')
        
        if plan.get('executed'):
            # Recalcular VLRNOTA e QTDVOL do cabeçalho após atualizar item
            try:
                nunota_update = update_dict['NUNOTA']
                with get_connection() as conn:
                    cur = conn.cursor()
                    
                    # Somar todos os VLRTOT e QTDNEG dos itens desta nota
                    cur.execute("""
                        SELECT NVL(SUM(VLRTOT), 0), NVL(SUM(QTDNEG), 0)
                        FROM TGFITE 
                        WHERE NUNOTA = :nunota
                    """, nunota=nunota_update)
                    
                    row_sum = cur.fetchone()
                    vlrnota_total = float(row_sum[0]) if row_sum else 0.0
                    qtdvol_total = float(row_sum[1]) if row_sum else 0.0
                    
                    print(f'🔍 [UPDATE] Recalculando para NUNOTA {nunota_update}: VLRNOTA={vlrnota_total}, QTDVOL={qtdvol_total}')
                    
                    # Atualizar VLRNOTA e QTDVOL no cabeçalho
                    cur.execute("""
                        UPDATE TGFCAB 
                        SET VLRNOTA = :vlrnota, QTDVOL = :qtdvol
                        WHERE NUNOTA = :nunota
                    """, vlrnota=vlrnota_total, qtdvol=qtdvol_total, nunota=nunota_update)
                    
                    conn.commit()
                    
                    print(f'🔍 [UPDATE] Atualizado com sucesso: VLRNOTA=R$ {vlrnota_total:.2f}, QTDVOL={qtdvol_total:.2f}')
                    
                    # Adicionar ao response para o frontend saber
                    plan['vlrnota'] = vlrnota_total
                    plan['qtdvol'] = qtdvol_total
                    
            except Exception as e:
                print(f'🔍 [UPDATE] Erro ao recalcular: {e}')
                import traceback
                traceback.print_exc()
            
            # Removido: duplicação/upsync automática de TOP 11→26 no Portal
            return JsonResponse(plan, status=200)
        # Log and return clearer error for clients
        err_msg = plan.get('db_error', {}).get('message') if isinstance(plan.get('db_error'), dict) else None
        if not err_msg:
            err_msg = '; '.join(plan.get('errors', [])) if plan.get('errors') else 'Falha ao atualizar item'
        logger.error('item_update failed payload=%s plan=%s', payload, plan)
        return JsonResponse({'ok': False, 'error': err_msg, 'plan': plan}, status=400)

    # Otherwise, insert as new item
    # Enforce immutable lote for classification TOP: require 'controle' and reuse existing when available
    nun = _to_int_or(payload.get('nunota'))
    codtop, top_class = _get_nota_top(nun)
    
    # Buscar TOP_ENTRADA (11 - Portal/Pedido de Compra)
    try:
        from sankhya_integration.services.oracle_conn import get_params as _gp
        top_entrada = _gp().get('TOP_ENTRADA', 11)
    except Exception:
        top_entrada = 11
    
    # Se codtop é None, a nota ainda não existe. Determinar contexto pelo Referer ou path
    if codtop is None:
        referer = request.META.get('HTTP_REFERER', '')
        path = request.path
        # Se vier de /compras_portal/ ou payload tem indicação, assumir TOP 11
        if '/compras_portal' in referer or '/portal' in referer or payload.get('_source') == 'portal':
            codtop = top_entrada  # TOP 11
            print(f'🔍 Nota nova detectada como Portal (TOP {top_entrada}) via referer/source')
        # Se vier de /compras_classificacao/, assumir TOP 26
        elif '/compras_classificacao' in referer or '/classificacao' in referer or payload.get('_source') == 'classificacao':
            codtop = top_class  # TOP 26
            print(f'🔍 Nota nova detectada como Classificação (TOP {top_class}) via referer/source')
    
    print(f'🔍 INSERT DEBUG: nun={nun}, codtop={codtop}, top_class={top_class}, top_entrada={top_entrada}')
    # Prefer 'codagregacao' from client; keep 'controle' for temporary compatibility
    controle = (payload.get('codagregacao') or payload.get('controle') or '').strip()
    print(f'🔍 Controle recebido do frontend: "{controle}"')
    
    try:
        # Gerar lote automaticamente para TOP 11 (Portal) ou TOP 26 (Classificação)
        if codtop is not None and (int(codtop) == int(top_entrada) or (top_class and int(codtop) == int(top_class))):
            is_portal = (int(codtop) == int(top_entrada))
            is_classif = (top_class and int(codtop) == int(top_class))
            print(f'🔍 É TOP {"Portal (11)" if is_portal else "Classificação (26)" if is_classif else "especial"}')
            
            # Reutilizar controle existente APENAS para Classificação (TOP 26)
            # Para Portal (TOP 11), cada item deve ter seu próprio lote único
            if not controle and nun and is_classif:
                print(f'🔍 TOP Classificação: tentando buscar controle existente...')
                try:
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT MAX(CODAGREGACAO) FROM TGFITE WHERE NUNOTA=:n AND CODAGREGACAO IS NOT NULL", n=nun)
                        row = cur.fetchone()
                        if row and row[0]:
                            controle = str(row[0])
                            print(f'🔍 Encontrou controle existente: {controle}')
                except Exception as e:
                    print(f'🔍 Erro ao buscar controle existente: {e}')
                    controle = controle or ''
            
            # Se ainda não tem controle, será gerado automaticamente após INSERT usando SEQUENCIA real
            # Não gerar aqui para evitar race condition entre busca de MAX(SEQUENCIA) e INSERT
            auto_generate_controle = False
            if not controle and nun:
                auto_generate_controle = True
                controle = None  # Deixar vazio por enquanto
                print(f'🔍 Controle será gerado automaticamente após INSERT com sequência real')
            
            # Apenas TOP 26 (Classificação) é obrigatório ter controle
            if not controle and is_classif:
                return JsonResponse({"ok": False, "errors": ["Controle (lote) obrigatório para itens de Classificação"], "error": "Controle (lote) obrigatório para itens de Classificação"}, status=400)
        else:
            print(f'🔍 NÃO é TOP especial (Portal ou Classificação)')
    except Exception as e:
        print(f'🔍 Exception no bloco de controle: {e}')
        import traceback
        traceback.print_exc()
        pass
    
    print(f'🔍 Controle FINAL que será usado: "{controle}"')

    # Server-side enforcement: if there is already a TOP_CLASS header (TGFCAB) with items for this lote,
    # always reuse its NUNOTA regardless of the provided one — guarantees a single header per lote.
    nun_overridden = None
    try:
        if controle:
            # Resolve TOP_CLASS parameter (fallback to _get_nota_top-derived top_class if needed)
            try:
                from sankhya_integration.services.oracle_conn import get_params as _gp
                top_cls_val = _gp().get('TOP_CLASS')
            except Exception:
                top_cls_val = None
            if top_cls_val is None:
                # fallback to previously detected top_class
                top_cls_val = top_class
            if top_cls_val is not None:
                with get_connection() as _c:
                    cur2 = _c.cursor()
                    cur2.execute(
                        """
                        SELECT i.NUNOTA FROM (
                          SELECT DISTINCT i.NUNOTA
                            FROM TGFITE i
                            JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                           WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
                           ORDER BY i.NUNOTA DESC
                        ) WHERE ROWNUM = 1
                        """,
                        c=controle, top=top_cls_val
                    )
                    row2 = cur2.fetchone()
                    if row2 and row2[0] is not None:
                        try:
                            existing_nun = int(row2[0])
                        except Exception:
                            existing_nun = row2[0]
                        if existing_nun and existing_nun != nun:
                            nun_overridden = existing_nun
                            nun = existing_nun
    except Exception:
        # Non-fatal; continue with provided nun
        pass

    # Usar versão OTIMIZADA para alta performance (~3-5x mais rápido)
    plan = insert_item_fast({
        'NUNOTA': nun,
        'CODPROD': _to_int_or(payload.get('codprod')),
        'QTDNEG': payload.get('qtdneg'),  # Total kg - já vem em KG do frontend
        'VLRUNIT': payload.get('vlrunit'),
        'PESO': payload.get('peso'),
        'CODVOL': payload.get('codvol') or 'UN',  # Manter unidade alternativa (CX)
        'CODLOCALORIG': _to_int_or(payload.get('codlocal'), 101),
        'CODAGREGACAO': (controle or None),
        'OBSERVACAO': (payload.get('obs') or '').strip() or None,
        # Inserir GERAPRODUCAO quando informado; default será do trigger ('S')
        'GERAPRODUCAO': _map_gp(payload.get('geraproducao')),
    }, dry_run=False)
    
    # Se o item foi inserido com sucesso E precisamos gerar controle automaticamente
    if plan.get('executed') and auto_generate_controle and plan.get('sequencia'):
        from datetime import datetime
        hoje = datetime.now().strftime('%y%m%d')
        real_seq = int(plan['sequencia'])
        novo_controle = f"{nun}S{real_seq:02d}D{hoje}"
        print(f'🔍 Atualizando controle com sequência real: {novo_controle} (seq={real_seq})')
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE TGFITE SET CODAGREGACAO = :ctrl WHERE NUNOTA = :n AND SEQUENCIA = :s",
                    ctrl=novo_controle, n=nun, s=real_seq
                )
                conn.commit()
                plan['codagregacao'] = novo_controle
                print(f'🔍 Controle atualizado com sucesso: {novo_controle}')
        except Exception as e:
            print(f'🔍 ERRO ao atualizar controle: {e}')
            # Não falhar a operação por isso
            pass
    
    if nun_overridden:
        try:
            plan.setdefault('warnings', []).append(f"Reutilizado cabeçalho de Classificação existente (NUNOTA {nun_overridden}) para o lote {controle}.")
            plan['nunota'] = nun_overridden
        except Exception:
            pass
    if plan.get('executed'):
        # Recalcular VLRNOTA e QTDVOL do cabeçalho após inserir item
        try:
            nunota_insert = plan.get('nunota') or nun
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Somar todos os VLRTOT e QTDNEG dos itens desta nota
                cur.execute("""
                    SELECT NVL(SUM(VLRTOT), 0), NVL(SUM(QTDNEG), 0)
                    FROM TGFITE 
                    WHERE NUNOTA = :nunota
                """, nunota=nunota_insert)
                
                row_sum = cur.fetchone()
                vlrnota_total = float(row_sum[0]) if row_sum else 0.0
                qtdvol_total = float(row_sum[1]) if row_sum else 0.0
                
                print(f'🔍 [INSERT] Recalculando para NUNOTA {nunota_insert}: VLRNOTA={vlrnota_total}, QTDVOL={qtdvol_total}')
                
                # Atualizar VLRNOTA e QTDVOL no cabeçalho
                cur.execute("""
                    UPDATE TGFCAB 
                    SET VLRNOTA = :vlrnota, QTDVOL = :qtdvol
                    WHERE NUNOTA = :nunota
                """, vlrnota=vlrnota_total, qtdvol=qtdvol_total, nunota=nunota_insert)
                
                conn.commit()
                
                print(f'🔍 [INSERT] Atualizado com sucesso: VLRNOTA=R$ {vlrnota_total:.2f}, QTDVOL={qtdvol_total:.2f}')
                
                # Adicionar ao response para o frontend saber
                plan['vlrnota'] = vlrnota_total
                plan['qtdvol'] = qtdvol_total
                
        except Exception as e:
            print(f'🔍 [INSERT] Erro ao recalcular: {e}')
            import traceback
            traceback.print_exc()
        
        # Removido: duplicação/upsync automática de TOP 11→26 no Portal
        return JsonResponse(plan, status=200)
    err_msg = plan.get('db_error', {}).get('message') if isinstance(plan.get('db_error'), dict) else None
    if not err_msg:
        err_msg = '; '.join(plan.get('errors', [])) if plan.get('errors') else 'Falha ao inserir item'
    logger.error('item_insert failed payload=%s plan=%s', payload, plan)
    return JsonResponse({'ok': False, 'error': err_msg, 'plan': plan}, status=400)


def item_delete(request: HttpRequest) -> JsonResponse:
    """Endpoint JSON para excluir um ou mais itens (TGFITE) da nota.
    Payload: { nunota: number, sequencias: [number] }
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    nunota = _to_int_or(payload.get('nunota'))
    sequencias = payload.get('sequencias') or []
    if not nunota or not isinstance(sequencias, list) or not sequencias:
        return JsonResponse({"ok": False, "error": "Informe nunota e sequencias"}, status=400)
    try:
        seqs = [int(s) for s in sequencias]
    except Exception:
        return JsonResponse({"ok": False, "error": "Sequencias inválidas"}, status=400)
    res = delete_itens(nunota, seqs, dry_run=False)
    
    # Recalcular VLRNOTA e QTDVOL do cabeçalho após excluir itens
    if res.get('ok'):
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Somar todos os VLRTOT e QTDNEG dos itens restantes desta nota
                cur.execute("""
                    SELECT NVL(SUM(VLRTOT), 0), NVL(SUM(QTDNEG), 0), COUNT(*)
                    FROM TGFITE 
                    WHERE NUNOTA = :nunota
                """, nunota=nunota)
                
                row_sum = cur.fetchone()
                vlrnota_total = float(row_sum[0]) if row_sum else 0.0
                qtdvol_total = float(row_sum[1]) if row_sum else 0.0
                itens_restantes = int(row_sum[2]) if row_sum else 0
                
                print(f'🔍 [DELETE] NUNOTA {nunota}: VLRNOTA={vlrnota_total}, QTDVOL={qtdvol_total}, Itens restantes={itens_restantes}')
                
                # Se não há mais itens, excluir o cabeçalho também
                if itens_restantes == 0:
                    print(f'🔍 [DELETE] NUNOTA {nunota} sem itens - excluindo cabeçalho')
                    cur.execute("DELETE FROM TGFCAB WHERE NUNOTA = :nunota", nunota=nunota)
                    conn.commit()
                    res['cab_deleted'] = True
                    res['message'] = 'Último item excluído - cabeçalho também foi removido'
                    print(f'✅ [DELETE] Cabeçalho NUNOTA {nunota} excluído com sucesso')
                else:
                    # Atualizar VLRNOTA e QTDVOL no cabeçalho
                    cur.execute("""
                        UPDATE TGFCAB 
                        SET VLRNOTA = :vlrnota, QTDVOL = :qtdvol
                        WHERE NUNOTA = :nunota
                    """, vlrnota=vlrnota_total, qtdvol=qtdvol_total, nunota=nunota)
                    
                    conn.commit()
                    
                    print(f'✅ [DELETE] Atualizado com sucesso: VLRNOTA=R$ {vlrnota_total:.2f}, QTDVOL={qtdvol_total:.2f}')
                
                # Adicionar ao response para o frontend saber
                res['vlrnota'] = vlrnota_total
                res['qtdvol'] = qtdvol_total
                res['itens_restantes'] = itens_restantes
                
        except Exception as e:
            print(f'❌ [DELETE] Erro ao recalcular: {e}')
            import traceback
            traceback.print_exc()
    
    # HTTP 200 if service completed evaluation; include partial info
    status_code = 200 if res.get('ok') else 400
    return JsonResponse(res, status=status_code)


def item_duplicate(request: HttpRequest) -> JsonResponse:
    """Endpoint JSON para duplicar um item (igual produto/valores, novo CONTROLE e nova SEQUENCIA)."""
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    nunota = _to_int_or(payload.get('nunota'))
    sequencia = _to_int_or(payload.get('sequencia'))
    if not nunota or not sequencia:
        return JsonResponse({"ok": False, "error": "Informe nunota e sequencia"}, status=400)
    res = duplicate_item(nunota, sequencia, dry_run=False)
    return JsonResponse(res, status=200 if res.get('executed') else 400)

def item_get_lote(request: HttpRequest) -> JsonResponse:
    """GET /sankhya/item/get_lote/?nunota=...&seq=... -> { ok, lote }
    Retorna CODAGREGACAO (lote) do item em TGFITE.
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        nunota = int(request.GET.get('nunota'))
        seq = int(request.GET.get('seq'))
    except Exception:
        return JsonResponse({"ok": False, "error": "Parâmetros inválidos (nunota, seq)"}, status=400)
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CODAGREGACAO FROM TGFITE WHERE NUNOTA=:n AND SEQUENCIA=:s", n=nunota, s=seq)
            row = cur.fetchone()
            lote = (row[0] if row else None) or ''
            return JsonResponse({"ok": True, "nunota": nunota, "sequencia": seq, "lote": lote})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def item_finalize(request: HttpRequest) -> JsonResponse:
    """POST /sankhya/item/finalize/ - Finaliza uma nota
    Atualiza DTFATUR, STATUSNOTA='L' e DTALTER em TGFCAB.
    Payload: { nunota: number }
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    
    nunota = _to_int_or(payload.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "Informe nunota válido"}, status=400)
    
    if not is_write_enabled():
        return JsonResponse({"ok": False, "error": "Escrita desabilitada"}, status=403)
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Atualizar o cabeçalho (TGFCAB)
            cur.execute("""
                UPDATE TGFCAB 
                SET DTFATUR = SYSDATE,
                    STATUSNOTA = 'L',
                    DTALTER = SYSDATE
                WHERE NUNOTA = :nunota
            """, nunota=nunota)
            
            rows_updated = cur.rowcount
            conn.commit()
            
            print(f'🔍 [FINALIZE] Cabeçalho finalizado para NUNOTA {nunota}: DTFATUR=SYSDATE, STATUSNOTA=L')
            
            return JsonResponse({
                "ok": True,
                "nunota": nunota,
                "rows_updated": rows_updated,
                "message": f"Nota {nunota} finalizada e liberada"
            })
            
    except Exception as e:
        print(f'🔍 [FINALIZE] Erro: {e}')
        import traceback
        traceback.print_exc()
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def classificacao_resumo(request: HttpRequest) -> JsonResponse:
    """GET /sankhya/classificacao/resumo/?lote=... -> { ok, lote, linhas: [ { produto, cx, kg } ], extra: { qtdbatidas } }
    Usa somente itens TOP 26 (classificados).
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    lote = (request.GET.get('lote') or '').strip()
    if not lote:
        return JsonResponse({"ok": False, "error": "Informe 'lote'"}, status=400)
    try:
        rows = resumo_classificacao_por_lote(lote)
        linhas = []
        for descr, sum_cx, sum_kg, fator_cx in rows:
            linhas.append({
                'produto': (descr or '').strip(),
                'cx': float(sum_cx or 0),
                'kg': float(sum_kg or 0),
                'fator_cx': float(fator_cx or 0),  # kg por caixa (TGFVOA)
            })
        
        # Buscar QTDBATIDAS do cabeçalho TOP 26 (classificação)
        qtdbatidas = None
        try:
            from sankhya_integration.services.oracle_conn import get_connection, get_params
            p = get_params()
            TOP_CLASS = p['TOP_CLASS']
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT c.NUNOTA, c.QTDBATIDAS
                    FROM TGFITE i
                    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                    WHERE i.CODAGREGACAO = :lote AND c.CODTIPOPER = :top
                      AND ROWNUM = 1
                    ORDER BY c.NUNOTA DESC
                """, lote=lote, top=TOP_CLASS)
                row = cur.fetchone()
                if row and row[1] is not None:
                    qtdbatidas = float(row[1])
        except Exception:
            pass
        
        return JsonResponse({
            "ok": True,
            "lote": lote,
            "linhas": linhas,
            "extra": {
                "qtdbatidas": qtdbatidas
            }
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

def nota_delete(request: HttpRequest) -> JsonResponse:
    """Endpoint JSON para excluir uma nota (TGFCAB) e seus itens (TGFITE)."""
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    nunota = _to_int_or(payload.get('nunota'))
    if not nunota:
        return JsonResponse({"ok": False, "error": "Informe nunota"}, status=400)
    res = delete_nota(nunota, dry_run=False)
    status_code = 200 if res.get('ok') else 400
    return JsonResponse(res, status=status_code)

def nota_diagnose(request: HttpRequest) -> JsonResponse:
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        nunota = int(request.GET.get('nunota'))
    except Exception:
        return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)
    out = diagnose_nota_delete(nunota)
    return JsonResponse({"ok": True, **out})

def nota_check_classificacao(request: HttpRequest) -> JsonResponse:
    """Verifica se um item específico de uma nota (TOP 11) possui classificação (TOP 26).
    
    Parâmetros:
    - nunota: NUNOTA da TOP 11 (obrigatório)
    - seq: SEQUENCIA do item (opcional - se não informado, verifica a nota toda)
    
    Se SEQ for informado, verifica se existe classificação para o CODAGREGACAO específico do item.
    Se SEQ não for informado, verifica se existe classificação para qualquer item da nota.
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        nunota = int(request.GET.get('nunota'))
    except Exception:
        return JsonResponse({"ok": False, "error": "nunota inválido"}, status=400)
    
    seq = request.GET.get('seq', None)
    
    try:
        from sankhya_integration.services.oracle_conn import get_connection
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            if seq:
                # Verificação específica para um item (CODAGREGACAO)
                # 1. Buscar CODAGREGACAO do item na TOP 11
                query_item = """
                    SELECT i.CODAGREGACAO
                    FROM TGFITE i
                    WHERE i.NUNOTA = :nunota
                      AND i.SEQUENCIA = :seq
                """
                cursor.execute(query_item, {'nunota': nunota, 'seq': int(seq)})
                result = cursor.fetchone()
                
                if not result or not result[0]:
                    cursor.close()
                    return JsonResponse({
                        "ok": True,
                        "tem_classificacao": False,
                        "total_registros": 0,
                        "observacao": "Item não encontrado ou sem CODAGREGACAO"
                    })
                
                codagregacao = result[0]
                
                # 2. Verificar se existe TOP 26 com item que tem esse CODAGREGACAO
                query_class = """
                    SELECT COUNT(DISTINCT c26.NUNOTA)
                    FROM TGFCAB c26
                    INNER JOIN TGFITE i26 ON i26.NUNOTA = c26.NUNOTA
                    WHERE c26.CODTIPOPER = 26
                      AND (c26.NUMPEDIDO = :nunota OR c26.NUMNOTA = :nunota)
                      AND i26.CODAGREGACAO = :codagregacao
                """
                cursor.execute(query_class, {'nunota': nunota, 'codagregacao': codagregacao})
                count = cursor.fetchone()[0]
            else:
                # Verificação geral da nota inteira
                query = """
                    SELECT COUNT(*) 
                    FROM TGFCAB c26
                    WHERE c26.CODTIPOPER = 26
                      AND (c26.NUMPEDIDO = :nunota OR c26.NUMNOTA = :nunota)
                """
                cursor.execute(query, {'nunota': nunota})
                count = cursor.fetchone()[0]
            
            cursor.close()
        
        return JsonResponse({
            "ok": True,
            "tem_classificacao": count > 0,
            "total_registros": count
        })
    except Exception as e:
        return JsonResponse({
            "ok": False,
            "error": f"Erro ao verificar classificação: {str(e)}"
        }, status=500)

def nota_check_negociacao(request: HttpRequest) -> JsonResponse:
    """Verifica se um controle possui negociação comercial.
    
    Pode receber:
    - nunota: NUNOTA da TOP 26 (classificação) - busca TOP 13 (Vale) vinculado
    - controle: CODAGREGACAO - busca diretamente nos itens da TOP 13
    
    Retorna se existe VLRTOT > 0 nos itens da TOP 13 (Vale).
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    
    nunota_param = request.GET.get('nunota', '')
    controle_param = request.GET.get('controle', '')
    
    print(f"🔍 [CHECK_NEGOCIACAO] Recebido - NUNOTA: {nunota_param}, Controle: {controle_param}")
    
    try:
        from sankhya_integration.services.oracle_conn import get_connection
        
        with get_connection() as conn:
            cursor = conn.cursor()
            nunota_vale = None
            numpedido = None
            
            # Variável para armazenar o CODAGREGACAO a ser verificado
            codagregacao = None
            
            # Opção 1: Se recebeu controle, busca TOP 11 e depois TOP 13 via NUMPEDIDO
            if controle_param:
                codagregacao = controle_param
                print(f"📋 [CHECK_NEGOCIACAO] Buscando pela CODAGREGACAO: {codagregacao}")
                
                # Busca TOP 11 pelo controle
                query_top11 = """
                    SELECT c.NUNOTA, c.NUMNOTA
                    FROM TGFITE i
                    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                    WHERE i.CODAGREGACAO = :controle
                      AND c.CODTIPOPER = 11
                      AND ROWNUM = 1
                """
                cursor.execute(query_top11, {'controle': codagregacao})
                row = cursor.fetchone()
                if row:
                    numpedido = row[1]  # NUMNOTA da TOP 11 = NUMPEDIDO da TOP 13
                    print(f"📦 [CHECK_NEGOCIACAO] TOP 11 encontrada - NUMPEDIDO={numpedido}")
            
            # Opção 2: Se não encontrou por controle e recebeu nunota da TOP 26
            if not numpedido and nunota_param:
                try:
                    nunota_top26 = int(nunota_param)
                    print(f"📋 [CHECK_NEGOCIACAO] Buscando pela NUNOTA TOP 26: {nunota_top26}")
                    
                    # Busca o NUMPEDIDO da TOP 26 E o CODAGREGACAO dos itens
                    query_cab = """
                        SELECT c.NUMPEDIDO, i.CODAGREGACAO
                        FROM TGFCAB c
                        LEFT JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                        WHERE c.NUNOTA = :nunota_top26
                          AND c.CODTIPOPER = 26
                          AND ROWNUM = 1
                    """
                    cursor.execute(query_cab, {'nunota_top26': nunota_top26})
                    row = cursor.fetchone()
                    
                    if row:
                        numpedido = row[0]
                        codagregacao = row[1]  # CODAGREGACAO do item da TOP 26
                        print(f"📋 [CHECK_NEGOCIACAO] TOP 26 - NUMPEDIDO={numpedido}, CODAGREGACAO={codagregacao}")
                except Exception as e:
                    print(f"⚠️ [CHECK_NEGOCIACAO] Erro ao processar NUNOTA TOP 26: {e}")
            
            # Se não encontrou o NUMPEDIDO ou CODAGREGACAO, não tem negociação
            if not numpedido or not codagregacao:
                print(f"⚠️ [CHECK_NEGOCIACAO] NUMPEDIDO ou CODAGREGACAO não encontrado")
                cursor.close()
                return JsonResponse({
                    "ok": True,
                    "tem_negociacao": False,
                    "total_registros": 0,
                    "info": "NUMPEDIDO ou CODAGREGACAO não encontrado"
                })
            
            # Busca o NUNOTA da TOP 13 (VALE) pelo NUMPEDIDO
            query_vale = """
                SELECT NUNOTA
                FROM TGFCAB
                WHERE CODTIPOPER = 13
                  AND NUMPEDIDO = :numpedido
                  AND ROWNUM = 1
            """
            cursor.execute(query_vale, {'numpedido': numpedido})
            row_vale = cursor.fetchone()
            
            if not row_vale:
                print(f"⚠️ [CHECK_NEGOCIACAO] TOP 13 (Vale) não encontrado para NUMPEDIDO={numpedido}")
                cursor.close()
                return JsonResponse({
                    "ok": True,
                    "tem_negociacao": False,
                    "total_registros": 0,
                    "info": "Vale (TOP 13) não encontrado"
                })
            
            nunota_vale = row_vale[0]
            print(f"📦 [CHECK_NEGOCIACAO] TOP 13 (Vale) encontrado - NUNOTA={nunota_vale}")
            
            # Verifica se existe VLRTOT > 0 NO ITEM ESPECÍFICO (CODAGREGACAO ou CONTROLE) da TOP 13
            query_vlrtot = """
                SELECT COUNT(*), SUM(VLRTOT)
                FROM TGFITE
                WHERE NUNOTA = :nunota_vale
                  AND (CODAGREGACAO = :codagregacao OR CONTROLE = :codagregacao)
                  AND VLRTOT > 0
            """
            cursor.execute(query_vlrtot, {'nunota_vale': nunota_vale, 'codagregacao': codagregacao})
            row_vlr = cursor.fetchone()
            count = row_vlr[0] if row_vlr else 0
            total_vlrtot = row_vlr[1] if row_vlr and row_vlr[1] else 0
            
            # Query adicional para mostrar o item ESPECÍFICO (debug)
            query_debug = """
                SELECT SEQUENCIA, CODPROD, CODAGREGACAO, CONTROLE, QTDNEG, VLRUNIT, VLRTOT
                FROM TGFITE
                WHERE NUNOTA = :nunota_vale
                  AND (CODAGREGACAO = :codagregacao OR CONTROLE = :codagregacao)
                ORDER BY SEQUENCIA
            """
            cursor.execute(query_debug, {'nunota_vale': nunota_vale, 'codagregacao': codagregacao})
            debug_rows = cursor.fetchall()
            print(f"📊 [CHECK_NEGOCIACAO] Itens na TOP 13 (Vale) (NUNOTA={nunota_vale}, LOTE={codagregacao}):")
            for row in debug_rows:
                seq, cod, codagr, ctrl, qtd, vlu, vlt = row
                print(f"   SEQ={seq} COD={cod} CODAGR={codagr} CTRL={ctrl} QTD={qtd} VLRU={vlu} VLRT={vlt}")
            
            cursor.close()
            
            print(f"💰 [CHECK_NEGOCIACAO] Itens com VLRTOT > 0 no Vale: {count} (Total: R$ {total_vlrtot})")
        
        result = {
            "ok": True,
            "tem_negociacao": count > 0,
            "total_registros": count,
            "nunota_vale": nunota_vale,
            "numpedido": numpedido,
            "codagregacao": codagregacao,
            "total_vlrtot": float(total_vlrtot) if total_vlrtot else 0.0
        }
        print(f"✅ [CHECK_NEGOCIACAO] Resultado: tem_negociacao={count > 0}, count={count}, lote={codagregacao}, total=R$ {total_vlrtot}")
        return JsonResponse(result)
        
    except Exception as e:
        print(f"❌ [CHECK_NEGOCIACAO] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "ok": False,
            "error": f"Erro ao verificar negociação: {str(e)}"
        }, status=500)

def class_plan(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    nunota = _to_int_or(payload.get('nunota_origem'))
    sequencia = _to_int_or(payload.get('sequencia_origem'))
    saidas = payload.get('saidas') or []
    nunota_dest = _to_int_or(payload.get('nunota_dest'))
    plan = plan_classificacao(nunota, sequencia, saidas, nunota_dest)
    # informar ao cliente se a escrita está habilitada neste servidor
    plan['write_enabled'] = is_write_enabled()
    return JsonResponse(plan, status=200 if plan.get('ok') else 400)

def class_execute(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    nunota = _to_int_or(payload.get('nunota_origem'))
    sequencia = _to_int_or(payload.get('sequencia_origem'))
    saidas = payload.get('saidas') or []
    nunota_dest = _to_int_or(payload.get('nunota_dest'))
    # Support optional 'force' in payload to override write flag for testing. Only allowed if env PACKINGHOUSE_ALLOW_FORCE is truthy.
    allow_force = False
    try:
        import os
        allow_force = os.getenv('PACKINGHOUSE_ALLOW_FORCE', 'false').lower() in ('1', 'true', 'yes', 'on')
    except Exception:
        allow_force = False
    force_req = bool(payload.get('force')) and allow_force
    res = execute_classificacao(nunota, sequencia, saidas, nunota_dest, dry_run=False, force=force_req)
    res['force_applied'] = force_req
    res['write_enabled'] = is_write_enabled()
    # Always return 200 so the client can display warnings (including write-disabled simulation)
    # The payload contains 'executed' boolean and 'warnings'/'errors' lists.
    status_code = 200
    if not res.get('executed') and res.get('errors'):
        status_code = 400
    return JsonResponse(res, status=status_code)


def lote_consultar(request: HttpRequest) -> JsonResponse:
    """AJAX helper para consultar um lote (controle) e retornar classificacoes e agregados."""
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    controle = request.GET.get('controle')
    if not controle:
        return JsonResponse({"ok": False, "error": "Parâmetro 'controle' obrigatório"}, status=400)
    try:
        # Service function expects CODAGREGACAO (we accept "controle" query param for compatibility)
        # Use a lightweight path by default to reduce latency; opt-in to full via ?full=1
        from sankhya_integration.services.oracle_conn import consultar_lote_light as _consultar_lote_light, consultar_lote as _consultar_lote_full
        full = (request.GET.get('full') in ('1', 'true', 'yes', 'on'))
        info = _consultar_lote_full(controle) if full else _consultar_lote_light(controle)
        agreg = info.get('agregados') or {}
        classific = info.get('classificacoes') or []
        classificaveis = info.get('classificaveis') or []
        entradas = info.get('entradas') or []
        # Helper to compute display quantity converting from base to alternative unit when needed
        def _disp_qty(_codprod, _codvol, qtdneg):
            """
            IMPORTANTE: Sankhya armazena QTDNEG sempre na unidade BASE (KG).
            Para exibir na unidade alternativa (CX), precisamos DIVIDIR pelo fator.
            """
            try:
                q = float(qtdneg or 0)
            except Exception:
                q = 0.0
            try:
                if _codprod is None or not _codvol:
                    return q
                # Lazy import to avoid cycles
                from sankhya_integration.services.oracle_conn import get_base_unit_and_factor as _get_bf
                base, fator = _get_bf(int(_codprod), str(_codvol))
                if base and str(base).upper() != str(_codvol).upper() and fator and float(fator) > 0:
                    # QTDNEG está na base (KG); para exibir na unidade alternativa (CX), divide pelo fator
                    return round(q / float(fator), 6)
                return q
            except Exception:
                return q

        # Convert rows to simple dicts for JSON (include raw PESO from TGFITE)
        results = []
        for row in classific:
            # row: (NUNOTA, SEQUENCIA, CODPROD, DESCRPROD, CODVOL, QTDNEG, PESO, VLRUNIT, VLRTOT)
            # IMPORTANTE: Agora QTDNEG é sempre em KG (Total kg), não precisa conversão
            qtdneg_kg = float(row[5] or 0)  # Total kg armazenado
            results.append({
                'nunota': int(row[0]) if row[0] is not None else None,
                'sequencia': int(row[1]) if row[1] is not None else None,
                'cod': int(row[2]) if row[2] is not None else None,
                'descr': row[3] or '',
                'codvol': row[4] or '',
                'qtd': _disp_qty(row[2], row[4], row[5]),  # Qtd em caixas (calculado)
                'peso': (float(row[6]) if (len(row) > 6 and row[6] is not None) else None),
                'totalkg': qtdneg_kg,  # Total kg real (QTDNEG sem conversão)
                'vlu': float(row[7] or 0),
                'vlt': float(row[8] or 0),
            })
        # convert entradas to lightweight objects for origin selection
        entradas_out = []
        for e in entradas:
            # expected tuple: (NUNOTA, SEQUENCIA, CODPROD, DESCRPROD, CODVOL, QTDNEG, PESO, VLRUNIT, VLRTOT, NOMEPARC)
            entradas_out.append({
                'nunota': int(e[0]) if e and e[0] is not None else None,
                'sequencia': int(e[1]) if e and e[1] is not None else None,
                'codprod': int(e[2]) if e and e[2] is not None else None,
                'descr': e[3] if e and len(e) > 3 else '',
                'codvol': e[4] if e and len(e) > 4 else '',
                'qtd': _disp_qty(e[2] if len(e) > 2 else None, e[4] if len(e) > 4 else '', e[5] if len(e) > 5 else None),
                'peso': (float(e[6]) if (len(e) > 6 and e[6] is not None) else None),
                'vlu': float(e[7] or 0),
                'vlt': float(e[8] or 0),
                'parceiro': e[9] if e and len(e) > 9 else '',
            })

        # convert classificaveis to lightweight objects (same shape as classificacoes)
        classif_out = []
        for row in classificaveis:
            classif_out.append({
                'nunota': int(row[0]) if row[0] is not None else None,
                'sequencia': int(row[1]) if row[1] is not None else None,
                'cod': int(row[2]) if row[2] is not None else None,
                'descr': row[3] or '',
                'codvol': row[4] or '',
                'qtd': _disp_qty(row[2], row[4], row[5]),
                'peso': (float(row[6]) if (len(row) > 6 and row[6] is not None) else None),
                'vlu': float(row[7] or 0),
                'vlt': float(row[8] or 0),
            })

        # expose product code for In Natura so the UI can default to that origin
        # IMPORTANTE: Usar o prod_in_natura que vem do consultar_lote_light (busca real do banco)
        # NÃO usar o valor hardcoded de get_params() que sempre retorna 863
        _prod_inn = info.get('prod_in_natura') if isinstance(info, dict) else None
        if _prod_inn is None:
            # Fallback para o valor de configuração apenas se não encontrar no banco
            try:
                from sankhya_integration.services.oracle_conn import get_params as _get_params
                _p = _get_params(); _prod_inn = _p.get('PROD_IN_NATURA')
            except Exception:
                _prod_inn = None
        # Include timings if present (esp. from light mode)
        timings = info.get('timings') if isinstance(info, dict) else None
        return JsonResponse({
            "ok": True,
            "agregados": agreg,
            "classificacoes": results,
            "classificaveis": classif_out,
            "entradas": entradas_out,
            "nunota_class": info.get('nunota_class'),
            "pendente_class": info.get('pendente_class'),
            "qtdbatidas": info.get('qtdbatidas'),
            "prod_in_natura": _prod_inn,
            "timings": timings,
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def comercial_sim_save(request: HttpRequest) -> JsonResponse:
    """Salvar uma simulação comercial simples no banco (model Simulation).

    Aceita POST JSON com os campos mínimos (lote, prod, price_cx, q_cx, q_kg, obs_adm, obs_prod, total).
    Se for fornecido 'id' atualiza a simulação existente.
    """
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    from sankhya_integration.models import Simulation
    sim_id = payload.get('id')
    try:
        total = None
        if payload.get('total') is not None:
            try:
                total = float(payload.get('total'))
            except Exception:
                total = None
        if sim_id:
            sim = Simulation.objects.filter(id=sim_id).first()
            if not sim:
                return JsonResponse({'ok': False, 'error': 'Simulação não encontrada'}, status=404)
            sim.lote = payload.get('lote') or sim.lote
            sim.name = payload.get('name') or sim.name
            sim.payload = payload
            sim.total = total
            sim.save()
            return JsonResponse({'ok': True, 'id': sim.id})
        # create new
        sim = Simulation.objects.create(
            name=payload.get('name') or None,
            lote=payload.get('lote') or None,
            payload=payload,
            total=total,
            created_by=(request.user.username if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False) else None),
        )
        return JsonResponse({'ok': True, 'id': sim.id})
    except Exception as e:
        logger.exception('comercial_sim_save failed')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def comercial_sim_list(request: HttpRequest) -> JsonResponse:
    """Listar simulações salvas. Query params: lote (opcional), limit (default 50), offset (default 0)."""
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        from sankhya_integration.models import Simulation
        q_lote = (request.GET.get('lote') or '').strip()
        try:
            limit = int(request.GET.get('limit', 50))
            offset = int(request.GET.get('offset', 0))
        except Exception:
            limit, offset = 50, 0
        qs = Simulation.objects.all()
        if q_lote:
            qs = qs.filter(lote__icontains=q_lote)
        total = qs.count()
        rows = qs[offset:offset+limit]
        out = []
        for s in rows:
            out.append({
                'id': s.id,
                'lote': s.lote,
                'name': s.name,
                'payload': s.payload,
                'total': float(s.total) if s.total is not None else None,
                'created_at': s.created_at.isoformat(),
            })
        return JsonResponse({'ok': True, 'total': total, 'limit': limit, 'offset': offset, 'rows': out})
    except Exception as e:
        logger.exception('comercial_sim_list failed')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def _to_float_or(val, default=None):
    if val in (None, '', 'None', 'none', 'null'):
        return default
    if isinstance(val, (int, float)):
        try:
            return float(val)
        except Exception:
            return default
    try:
        s = str(val).strip()
    except Exception:
        return default
    if not s:
        return default
    s = s.replace('R$', '').replace('r$', '').replace(' ', '')
    if ',' in s and '.' in s:
        # assume thousands separator '.' and decimal ','
        s = s.replace('.', '').replace(',', '.')
    elif s.count(',') == 1 and s.count('.') == 0:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return default


def update_vlrnota_for_nota(nunota: int) -> dict:
    """
    Atualiza o campo VLRNOTA da nota (TGFCAB) com a soma dos VLRTOT de todos os itens
    onde o fabricante está definido.
    
    Args:
        nunota: Número único da nota
        
    Returns:
        dict: {'ok': bool, 'vlrnota': float, 'updated': bool, 'error': str|None}
    """
    result = {
        'ok': False,
        'vlrnota': 0.0,
        'updated': False,
        'error': None
    }
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Calcular soma dos VLRTOT onde fabricante está definido
                sql_sum = """
                    SELECT NVL(SUM(i.VLRTOT), 0)
                    FROM TGFITE i
                    JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                    WHERE i.NUNOTA = :nunota
                      AND TRIM(p.FABRICANTE) IS NOT NULL
                """
                cur.execute(sql_sum, {'nunota': nunota})
                row = cur.fetchone()
                vlrnota_value = float(row[0]) if row and row[0] is not None else 0.0
                
                result['vlrnota'] = vlrnota_value
                
                # Atualizar TGFCAB.VLRNOTA se write habilitado
                if is_write_enabled():
                    sql_update = """
                        UPDATE TGFCAB
                        SET VLRNOTA = :vlrnota
                        WHERE NUNOTA = :nunota
                    """
                    cur.execute(sql_update, {
                        'vlrnota': vlrnota_value,
                        'nunota': nunota
                    })
                    conn.commit()
                    result['updated'] = True
                    logger.info(
                        f'VLRNOTA atualizado: NUNOTA={nunota}, '
                        f'VLRNOTA={vlrnota_value:.2f}'
                    )
                else:
                    logger.warning(
                        f'VLRNOTA não atualizado (write disabled): '
                        f'NUNOTA={nunota}, VLRNOTA={vlrnota_value:.2f}'
                    )
                
                result['ok'] = True
                
    except Exception as e:
        error_msg = f'Erro ao atualizar VLRNOTA: {str(e)}'
        logger.exception(error_msg)
        result['error'] = error_msg
    
    return result


def comercial_dist_save(request: HttpRequest) -> JsonResponse:
    """Persistir custo total e custo por kg da distribuição para o item de entrada (TGFITE)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    nunota = _to_int_or(payload.get('nunota'))
    sequencia = _to_int_or(payload.get('sequencia') or payload.get('seq'))
    if not nunota or not sequencia:
        return JsonResponse({'ok': False, 'error': 'Informe nunota e sequencia válidos'}, status=400)

    total = _to_float_or(payload.get('valor_total', payload.get('custo_total')))
    custo_kg = _to_float_or(payload.get('custo_kg', payload.get('valor_kg')))
    if total is None or custo_kg is None:
        return JsonResponse({'ok': False, 'error': 'Informe valor_total e custo_kg válidos'}, status=400)

    # Extract simulation fields: sim_qtd1→extraCx, sim_vlr1→extraCustoTotal, sim_qtd2→medioCx, sim_vlr2→medioCustoTotal
    sim_qtd1 = _to_float_or(payload.get('sim_qtd1'))
    sim_vlr1 = _to_float_or(payload.get('sim_vlr1'))
    sim_qtd2 = _to_float_or(payload.get('sim_qtd2'))
    sim_vlr2 = _to_float_or(payload.get('sim_vlr2'))

    update_payload = {
        'NUNOTA': nunota,
        'SEQUENCIA': sequencia,
        'VLRUNIT': custo_kg,
        'VLRTOT': total,
        'AD_SIMQTD1': sim_qtd1,
        'AD_SIMVLR1': sim_vlr1,
        'AD_SIMQTD2': sim_qtd2,
        'AD_SIMVLR2': sim_vlr2,
    }

    try:
        plan = update_item(update_payload, dry_run=False)
    except Exception as e:
        logger.exception('comercial_dist_save update_item failed')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

    executed = bool(plan.get('executed'))
    plan_ok = bool(plan.get('ok'))
    plan['plan_ok'] = plan_ok
    plan['inputs'] = {
        'valor_total': total,
        'custo_kg': custo_kg,
        'custo_extra_total': _to_float_or(payload.get('custo_extra_total')),
        'custo_medio_total': _to_float_or(payload.get('custo_medio_total')),
        'custo_extra_kg': _to_float_or(payload.get('custo_extra_kg')),
        'custo_medio_kg': _to_float_or(payload.get('custo_medio_kg')),
    }
    if not executed:
        if 'error' not in plan:
            err_msg = None
            if isinstance(plan.get('db_error'), dict):
                err_msg = plan['db_error'].get('message')
            if not err_msg and plan.get('errors'):
                err_msg = '; '.join(str(e) for e in plan['errors'] if e)
            if err_msg:
                plan['error'] = err_msg
    plan['ok'] = executed
    plan['write_enabled'] = is_write_enabled()
    
    # Atualizar VLRNOTA se o update foi executado com sucesso
    if executed:
        vlrnota_result = update_vlrnota_for_nota(nunota)
        plan['vlrnota_update'] = vlrnota_result
    
    status_code = 200 if executed else 400
    return JsonResponse(plan, status=status_code)


def comercial_item_lote(request: HttpRequest) -> JsonResponse:
    """Retorna o LOTE (CONTROLE) de um item do PEDIDO."""
    nunota = _to_int_or(request.GET.get('nunota'))
    sequencia = _to_int_or(request.GET.get('sequencia'))
    
    if not nunota or not sequencia:
        return JsonResponse({'ok': False, 'error': 'Parâmetros inválidos'}, status=400)
    
    sql = """
        SELECT CONTROLE
        FROM TGFITE
        WHERE NUNOTA = :nunota AND SEQUENCIA = :sequencia
    """
    
    try:
        from .services.oracle_conn import get_cursor
        with get_cursor() as cursor:
            cursor.execute(sql, {'nunota': nunota, 'sequencia': sequencia})
            row = cursor.fetchone()
            
            if not row or not row[0]:
                return JsonResponse({'ok': False, 'error': 'LOTE não encontrado'}, status=404)
            
            return JsonResponse({'ok': True, 'lote': row[0]})
    except Exception as e:
        logger.exception('Erro ao buscar LOTE')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def comercial_vale_sync(request: HttpRequest) -> JsonResponse:
    """Sincroniza itens EXTRA/MÉDIO no VALE (TOP 13) a partir da classificação."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception as e:
        logger.exception('Erro ao parsear JSON')
        return JsonResponse({'ok': False, 'error': f'JSON inválido: {str(e)}'}, status=400)
    
    # Extrair dados
    nunota_pedido = _to_int_or(payload.get('nunota_pedido'))
    sequencia_pedido = _to_int_or(payload.get('sequencia_pedido'))
    codprod_in_natura = _to_int_or(payload.get('codprod_in_natura'))
    lote = payload.get('lote')  # String
    
    extra_kg = _to_float_or(payload.get('extra_kg', 0))
    extra_vlrunit_kg = _to_float_or(payload.get('extra_vlrunit_kg', 0))
    
    medio_kg = _to_float_or(payload.get('medio_kg', 0))
    medio_vlrunit_kg = _to_float_or(payload.get('medio_vlrunit_kg', 0))
    
    # Validações
    if not all([nunota_pedido, sequencia_pedido, codprod_in_natura, lote]):
        return JsonResponse({
            'ok': False,
            'error': 'Parâmetros obrigatórios: nunota_pedido, sequencia_pedido, codprod_in_natura, lote'
        }, status=400)
    
    if not (extra_kg > 0 or medio_kg > 0):
        return JsonResponse({
            'ok': False,
            'error': 'Pelo menos um dos produtos (Extra ou Médio) deve ter quantidade > 0'
        }, status=400)
    
    from .services.oracle_conn import (
        get_nunota_vale_from_pedido,
        get_produtos_extra_medio,
        upsert_vale_item
    )
    
    # 1. Buscar NUNOTA do VALE
    try:
        nunota_vale = get_nunota_vale_from_pedido(nunota_pedido)
    except Exception as e:
        logger.exception(f'Erro ao buscar NUNOTA do VALE para pedido {nunota_pedido}')
        return JsonResponse({
            'ok': False,
            'error': f'Erro ao buscar VALE: {str(e)}'
        }, status=500)
    
    if not nunota_vale:
        return JsonResponse({
            'ok': False,
            'error': f'VALE (TOP 13) não encontrado para PEDIDO {nunota_pedido}'
        }, status=404)
    
    # 2. Mapear produtos
    try:
        produtos_map = get_produtos_extra_medio(codprod_in_natura)
    except Exception as e:
        logger.exception(f'Erro ao mapear produtos EXTRA/MÉDIO para CODPROD {codprod_in_natura}')
        return JsonResponse({
            'ok': False,
            'error': f'Erro ao mapear produtos: {str(e)}'
        }, status=500)
    
    if not produtos_map:
        return JsonResponse({
            'ok': False,
            'error': f'Não foi possível mapear produtos EXTRA/MÉDIO para CODPROD {codprod_in_natura}'
        }, status=400)
    
    codprod_extra = produtos_map.get('extra')
    codprod_medio = produtos_map.get('medio')
    
    results = []
    
    # 3. Processar EXTRA
    if extra_kg > 0 and codprod_extra:
        try:
            result_extra = upsert_vale_item(
                nunota_vale=nunota_vale,
                codprod=codprod_extra,
                qtdneg=extra_kg,
                vlrunit=extra_vlrunit_kg,
                lote=lote,
                produto_tipo='EXTRA'
            )
            results.append({'tipo': 'EXTRA', **result_extra})
        except Exception as e:
            logger.exception(f'Erro ao processar item EXTRA (codprod={codprod_extra})')
            results.append({
                'tipo': 'EXTRA',
                'success': False,
                'error': str(e)
            })
    
    # 4. Processar MÉDIO
    if medio_kg > 0 and codprod_medio:
        try:
            result_medio = upsert_vale_item(
                nunota_vale=nunota_vale,
                codprod=codprod_medio,
                qtdneg=medio_kg,
                vlrunit=medio_vlrunit_kg,
                lote=lote,
                produto_tipo='MEDIO'
            )
            results.append({'tipo': 'MEDIO', **result_medio})
        except Exception as e:
            logger.exception(f'Erro ao processar item MÉDIO (codprod={codprod_medio})')
            results.append({
                'tipo': 'MEDIO',
                'success': False,
                'error': str(e)
            })
    
    # 5. Atualizar VLRNOTA
    vlrnota_result = None
    if any(r.get('success') for r in results):
        try:
            vlrnota_result = update_vlrnota_for_nota(nunota_vale)
        except Exception as e:
            logger.exception(f'Erro ao atualizar VLRNOTA do VALE {nunota_vale}')
            vlrnota_result = {'error': str(e)}
    
    return JsonResponse({
        'ok': True,
        'nunota_vale': nunota_vale,
        'items_processed': results,
        'vlrnota_update': vlrnota_result
    })


@csrf_exempt
def comercial_vale_clear(request: HttpRequest) -> JsonResponse:
    """
    Remove produtos Extra/Médio do VALE associado ao PEDIDO.
    Exclusão seletiva: preserva outros produtos que possam existir no VALE.
    """
    from .services.oracle_conn import (
        get_nunota_vale_from_pedido,
        delete_vale_items
    )
    
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    
    # Parâmetros necessários
    nunota_pedido = _to_int_or(payload.get('nunota_pedido'))
    codprod_in_natura = _to_int_or(payload.get('codprod_in_natura'))
    
    if not nunota_pedido:
        return JsonResponse({'ok': False, 'error': 'nunota_pedido é obrigatório'}, status=400)
    
    if not codprod_in_natura:
        return JsonResponse({'ok': False, 'error': 'codprod_in_natura é obrigatório'}, status=400)
    
    logger.info(f'[VALE CLEAR] Requisição recebida - PEDIDO={nunota_pedido}, CODPROD={codprod_in_natura}')
    
    # 1. Buscar NUNOTA do VALE via NUMPEDIDO
    try:
        nunota_vale = get_nunota_vale_from_pedido(nunota_pedido)
    except Exception as e:
        logger.exception(f'Erro ao buscar VALE para PEDIDO {nunota_pedido}')
        return JsonResponse({
            'ok': False,
            'error': f'Erro ao buscar VALE: {str(e)}'
        }, status=500)
    
    if not nunota_vale:
        # Se não encontrou VALE, não é erro - apenas não há nada para limpar
        logger.info(f'[VALE CLEAR] VALE não encontrado para PEDIDO {nunota_pedido} - nada a deletar')
        return JsonResponse({
            'ok': True,
            'message': 'VALE não encontrado - nada a limpar',
            'deleted_count': 0
        })
    
    logger.info(f'[VALE CLEAR] VALE encontrado: NUNOTA={nunota_vale}')
    
    # 2. Deletar produtos Extra/Médio
    try:
        result = delete_vale_items(nunota_vale, codprod_in_natura)
    except Exception as e:
        logger.exception(f'Erro ao deletar itens do VALE {nunota_vale}')
        return JsonResponse({
            'ok': False,
            'error': f'Erro ao deletar itens: {str(e)}'
        }, status=500)
    
    if not result.get('success'):
        return JsonResponse({
            'ok': False,
            'error': result.get('error', 'Erro desconhecido ao deletar itens')
        }, status=500)
    
    logger.info(f'[VALE CLEAR] Sucesso - {result["deleted_count"]} itens deletados')
    
    return JsonResponse({
        'ok': True,
        'nunota_vale': nunota_vale,
        'deleted_count': result['deleted_count'],
        'products_deleted': result['products_deleted'],
        'items': result.get('items', []),
        'vlrnota_recalc': result.get('vlrnota_recalc')
    })


@csrf_exempt
def modal_faturamento_auto_save(request: HttpRequest) -> JsonResponse:
    """
    Auto-salva alterações do modalFaturamento quando usuário edita preço.
    
    Classificável: Cria VALE (cabeçalho) se não existir. Edita PEDIDO (PRECOBASE, VLRUNIT, VLRTOT).
    Não Classificável: Cria/edita VALE completo. Edita PEDIDO (VLRUNIT, VLRTOT).
    """
    from .services.oracle_conn import modal_faturamento_auto_save as auto_save_func
    
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception as e:
        logger.exception('Erro ao parsear JSON')
        return JsonResponse({'ok': False, 'error': f'JSON inválido: {str(e)}'}, status=400)
    
    # Extrair parâmetros
    nunota_pedido = _to_int_or(payload.get('nunota_pedido'))
    sequencia = _to_int_or(payload.get('sequencia'))
    codprod = _to_int_or(payload.get('codprod'))
    codagregacao = payload.get('codagregacao')  # String (lote)
    vlrtot = _to_float_or(payload.get('vlrtot'))
    is_classificavel = bool(payload.get('is_classificavel', False))
    
    # Validações
    if not all([nunota_pedido, sequencia, codprod, codagregacao]):
        return JsonResponse({
            'ok': False,
            'error': 'Parâmetros obrigatórios: nunota_pedido, sequencia, codprod, codagregacao'
        }, status=400)
    
    if vlrtot is None or vlrtot < 0:
        return JsonResponse({
            'ok': False,
            'error': 'vlrtot deve ser >= 0'
        }, status=400)
    
    logger.info(f'[MODAL AUTO-SAVE API] Requisição - NUNOTA={nunota_pedido}, SEQ={sequencia}, '
                f'VLRTOT={vlrtot}, CLASSIFICAVEL={is_classificavel}')
    
    try:
        result = auto_save_func(
            nunota_pedido=nunota_pedido,
            sequencia=sequencia,
            codprod=codprod,
            codagregacao=codagregacao,
            vlrtot=vlrtot,
            is_classificavel=is_classificavel
        )
        
        if not result.get('success'):
            return JsonResponse({
                'ok': False,
                'error': result.get('error', 'Erro desconhecido')
            }, status=500)
        
        logger.info(f'[MODAL AUTO-SAVE API] ✅ Sucesso - NUNOTA_VALE={result["nunota_vale"]}, '
                    f'VLRNOTA_PEDIDO={result["vlrnota_pedido"]}')
        
        return JsonResponse({
            'ok': True,
            'nunota_vale': result['nunota_vale'],
            'vlrnota_pedido': result['vlrnota_pedido'],
            'vlrnota_vale': result.get('vlrnota_vale'),
            'action': result['action'],
            'vlrunit': result['vlrunit']
        })
    
    except Exception as e:
        logger.exception(f'Erro ao processar auto-save modal - NUNOTA={nunota_pedido}, SEQ={sequencia}')
        return JsonResponse({
            'ok': False,
            'error': f'Erro ao salvar: {str(e)}'
        }, status=500)


def comercial_dist_reset(request: HttpRequest) -> JsonResponse:
    """Zerar valores de VLRUNIT e VLRTOT do item selecionado na distribuição."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    nunota = _to_int_or(payload.get('nunota'))
    sequencia = _to_int_or(payload.get('sequencia') or payload.get('seq'))
    if not nunota or not sequencia:
        return JsonResponse({'ok': False, 'error': 'Informe nunota e sequencia válidos'}, status=400)

    update_payload = {
        'NUNOTA': nunota,
        'SEQUENCIA': sequencia,
        'VLRUNIT': 0,
        'VLRTOT': 0,
    }

    try:
        plan = update_item(update_payload, dry_run=False)
    except Exception as e:
        logger.exception('comercial_dist_reset update_item failed')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

    executed = bool(plan.get('executed'))
    plan_ok = bool(plan.get('ok'))
    plan['plan_ok'] = plan_ok
    plan['inputs'] = {
        'nunota': nunota,
        'sequencia': sequencia,
    }
    if not executed:
        if 'error' not in plan:
            err_msg = None
            if isinstance(plan.get('db_error'), dict):
                err_msg = plan['db_error'].get('message')
            if not err_msg and plan.get('errors'):
                err_msg = '; '.join(str(e) for e in plan['errors'] if e)
            if err_msg:
                plan['error'] = err_msg
    plan['ok'] = executed
    plan['write_enabled'] = is_write_enabled()
    
    # Atualizar VLRNOTA se o reset foi executado com sucesso
    if executed:
        vlrnota_result = update_vlrnota_for_nota(nunota)
        plan['vlrnota_update'] = vlrnota_result
    
    status_code = 200 if executed else 400
    return JsonResponse(plan, status=status_code)


def comercial_vale_save(request: HttpRequest) -> JsonResponse:
    """Salvar preços para itens não classificáveis de um Vale e, opcionalmente, faturar.

    POST JSON:
    {
      "nunota": int,                  # Vale (TOP 11)
      "items": [
        { "sequencia": int, "preco": number },   # atualiza VLRUNIT e VLRTOT = preco * qtd
        ...
      ],
      "faturar": bool (optional)     # se true, tenta alterar STATUSNOTA para 'L'
    }
    Retorna { ok, updated, errors?, header? }.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    nunota = _to_int_or(payload.get('nunota'))
    items = payload.get('items') or []
    faturar = bool(payload.get('faturar'))
    if not nunota:
        return JsonResponse({'ok': False, 'error': 'nunota obrigatório'}, status=400)
    if not isinstance(items, list):
        return JsonResponse({'ok': False, 'error': 'items deve ser uma lista'}, status=400)

    updated = []
    errors = []
    try:
        # Buscar QTDNEG por item para calcular VLRTOT corretamente
        qtd_map = {}
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT SEQUENCIA, QTDNEG FROM TGFITE WHERE NUNOTA=:n", n=nunota)
            for seq, qtd in cur.fetchall():
                try:
                    qtd_map[int(seq)] = float(qtd or 0)
                except Exception:
                    continue
    except Exception:
        # Falha em pré-carregar quantidades não impede updates (VLRTOT cairá como preco*qtd com qtd=0)
        qtd_map = {}

    for it in items:
        try:
            seq = _to_int_or(it.get('sequencia'))
            preco = _to_float_or(it.get('preco'), None)
            preco_inicial = _to_float_or(it.get('preco_inicial'), None)
            if not seq:
                errors.append(f"Item inválido (sequencia ausente): {it}")
                continue
            # Monta update flexível: permite atualizar apenas PRECOBASE, apenas preço (VLRUNIT/VLRTOT) ou ambos
            upd = {
                'NUNOTA': nunota,
                'SEQUENCIA': seq,
            }
            if preco is not None:
                qtd = float(qtd_map.get(seq, 0))
                vlrtot = float(preco) * (qtd if qtd > 0 else 0)
                upd['VLRUNIT'] = float(preco)
                upd['VLRTOT'] = vlrtot
            if preco_inicial is not None:
                upd['PRECOBASE'] = float(preco_inicial)
            # Se nenhum campo foi informado, reporta erro
            if len(upd.keys()) <= 2:
                # Nenhuma alteração para este item — ignorar silenciosamente para não interromper faturamento
                continue
            plan = update_item(upd, dry_run=False)
            if not plan.get('executed'):
                msg = None
                if isinstance(plan.get('db_error'), dict):
                    msg = plan['db_error'].get('message')
                if not msg and plan.get('errors'):
                    msg = '; '.join([str(e) for e in plan['errors'] if e])
                errors.append(msg or f'Falha ao atualizar item seq {seq}')
            else:
                updated.append(seq)
        except Exception as e:
            errors.append(str(e))

    header = None
    nufin_result = None
    
    if faturar:
        try:
            # 1. Resolver NUNOTA do VALE (TOP 13) se o recebido for do PEDIDO (TOP 11)
            nunota_para_faturar = nunota
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT CODTIPOPER, NUMNOTA FROM TGFCAB WHERE NUNOTA=:n", n=int(nunota))
                    cab = cur.fetchone()
                    if cab:
                        codtop, numnota_cab = cab[0], cab[1]
                        if int(codtop) != 13:
                            # Tentar localizar VALE (TOP 13) vinculado a este pedido via NUMPEDIDO
                            numnota_pedido = numnota_cab if (numnota_cab and int(numnota_cab) != 0) else int(nunota)
                            cur.execute("""
                                SELECT NUNOTA FROM TGFCAB 
                                WHERE CODTIPOPER=13 AND NUMPEDIDO=:np
                            """, np=int(numnota_pedido))
                            v = cur.fetchone()
                            if v and v[0]:
                                nunota_para_faturar = int(v[0])
                            else:
                                errors.append('Não foi encontrado um VALE (TOP 13) vinculado a este pedido para faturar')
                                nunota_para_faturar = None
                    else:
                        errors.append('Cabeçalho não encontrado para a NUNOTA informada')
                        nunota_para_faturar = None
            except Exception as _e_resolve:
                errors.append(f'Falha ao resolver VALE para faturamento: {_e_resolve}')
                nunota_para_faturar = None

            # Se não foi possível resolver o VALE, não prosseguir faturamento
            if not nunota_para_faturar:
                header = {'executed': False, 'status': None}
            else:
                # 2. Alterar STATUSNOTA para 'L' (Liberado) no VALE
                plan_h = update_cabecalho({'NUNOTA': nunota_para_faturar, 'STATUSNOTA': 'L'}, dry_run=False)
            header = {'executed': bool(plan_h.get('executed')), 'status': 'L'}
            
            if nunota_para_faturar and not plan_h.get('executed'):
                msg = None
                if isinstance(plan_h.get('db_error'), dict):
                    msg = plan_h['db_error'].get('message')
                if not msg and plan_h.get('errors'):
                    msg = '; '.join([str(e) for e in plan_h['errors'] if e])
                errors.append(msg or 'Falha ao faturar (alterar STATUSNOTA)')
            else:
                # 2. CRIAR TGFFIN (Financeiro)
                # Importar função de criação do financeiro
                from .services.oracle_conn import criar_tgffin
                
                try:
                    if nunota_para_faturar:
                        nufin_result = criar_tgffin(nunota_para_faturar)
                    
                    if not nufin_result.get('ok'):
                        # Erro ao criar TGFFIN - reportar mas manter TGFCAB
                        erro_fin = nufin_result.get('error', 'Erro desconhecido ao criar financeiro')
                        errors.append(f'TGFFIN: {erro_fin}')
                        
                        # Log detalhado
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f'[FATURAR] Erro ao criar TGFFIN para NUNOTA {nunota}: {erro_fin}')
                    else:
                        # Sucesso ao criar TGFFIN
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f'[FATURAR] ✅ TGFFIN criado com sucesso: NUFIN={nufin_result.get("nufin")}, '
                                  f'VLRDESDOB={nufin_result.get("vlrdesdob")}, '
                                  f'DTVENC={nufin_result.get("dtvenc")}')
                        
                except Exception as e_fin:
                    # Exception ao tentar criar TGFFIN - reportar mas manter TGFCAB
                    erro_msg = f'Exceção ao criar TGFFIN: {str(e_fin)}'
                    errors.append(erro_msg)
                    
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f'[FATURAR] Exceção ao criar TGFFIN para NUNOTA {nunota}: {e_fin}', exc_info=True)
                    
        except Exception as e:
            errors.append(str(e))

    ok = len(errors) == 0
    
    # Montar resposta com informações do financeiro
    response_data = {
        'ok': ok, 
        'updated': updated, 
        'errors': errors or None, 
        'header': header
    }
    
    # Adicionar informações do TGFFIN se foi criado
    if nufin_result:
        response_data['financeiro'] = {
            'criado': nufin_result.get('ok', False),
            'nufin': nufin_result.get('nufin'),
            'vlrdesdob': nufin_result.get('vlrdesdob'),
            'dtvenc': nufin_result.get('dtvenc'),
            'error': nufin_result.get('error')
        }
    
    return JsonResponse(response_data, status=200 if ok else 400)


def comercial_vale_gerar(request: HttpRequest) -> JsonResponse:
    """
    Gera um Vale de Compra (TOP 13) a partir de um Pedido de Compra (TOP 11).
    
    POST JSON:
    {
      "nunota_origem": int,           # NUNOTA do pedido (TOP 11)
      "items": [
        # ITEM CLASSIFICÁVEL (gera EXTRA + MEDIO):
        {
          "tipo": "classificavel",
          "codprod": int,              # Código do produto IN NATURA
          "sequencia_origem": int,     # Sequência do item no pedido
          "extra_cx": float,           # Quantidade EXTRA em caixas
          "extra_total": float,        # Valor total EXTRA
          "medio_cx": float,           # Quantidade MÉDIO em caixas
          "medio_total": float,        # Valor total MÉDIO
          "codvol": str,               # Unidade (ex: 'CX')
          "codagregacao": str          # Lote
        },
        # ITEM NÃO CLASSIFICÁVEL (duplica produto original):
        {
          "tipo": "nao_classificavel",
          "codprod": int,              # Código do produto (mesmo do pedido)
          "sequencia_origem": int,     # Sequência do item no pedido
          "qtdneg": float,             # Quantidade (mesma do pedido)
          "vlrunit": float,            # Valor unitário (mesmo do pedido)
          "vlrtot": float,             # Valor total (mesmo do pedido)
          "codvol": str,               # Unidade (mesma do pedido)
          "codagregacao": str          # Lote (mesmo do pedido)
        },
        ...
      ]
    }
    
    Retorna:
    {
      "ok": bool,
      "nunota_13": int,               # NUNOTA do vale criado
      "items_criados": int,           # Quantidade de linhas TGFITE criadas
      "detalhes": [...]               # Lista de itens criados
    }
    """
    print('='*80)
    print('[GERAR VALE] ========== ENDPOINT CHAMADO ==========')
    print(f'[GERAR VALE] Method: {request.method}')
    print(f'[GERAR VALE] Path: {request.path}')
    print('='*80)
    
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'JSON inválido: {str(e)}'}, status=400)
    
    nunota_origem = _to_int_or(payload.get('nunota_origem'))
    items = payload.get('items') or []
    
    if not nunota_origem:
        return JsonResponse({'ok': False, 'error': 'nunota_origem obrigatório'}, status=400)
    if not isinstance(items, list) or len(items) == 0:
        return JsonResponse({'ok': False, 'error': 'items deve ser uma lista não vazia'}, status=400)
    
    try:
        from sankhya_integration.services.oracle_conn import (
            get_connection, get_params, insert_cabecalho_fast, insert_item_fast,
            get_produtos_extra_medio
        )
        
        p = get_params()
        TOP_ENTRADA = int(p['TOP_ENTRADA'])  # TOP 11
        TOP_VALE = 13  # TOP 13
        
        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Validar pedido origem
            cur.execute("""
                SELECT CODPARC, CODNAT, CODEMP, CODVEND, DTNEG, CODCENCUS
                FROM TGFCAB
                WHERE NUNOTA = :nunota AND CODTIPOPER = :top
            """, nunota=nunota_origem, top=TOP_ENTRADA)
            
            row_origem = cur.fetchone()
            if not row_origem:
                return JsonResponse({
                    'ok': False,
                    'error': f'Pedido de compra (TOP 11) NUNOTA {nunota_origem} não encontrado'
                }, status=404)
            
            codparc, codnat, codemp, codvend, dtneg, codcencus = row_origem
            
            # 2. Verificar se já existe vale para este pedido
            # IMPORTANTE: Usar MERGE ou INSERT com verificação para evitar race condition
            cur.execute("""
                SELECT NUNOTA
                FROM TGFCAB
                WHERE NUMPEDIDO = :nunota_origem AND CODTIPOPER = :top_vale
            """, nunota_origem=nunota_origem, top_vale=TOP_VALE)
            
            vale_existente = cur.fetchone()
            if vale_existente:
                print(f'[GERAR VALE] ⚠️ Vale já existe! NUNOTA={vale_existente[0]} para pedido {nunota_origem}')
                conn.rollback()  # Garantir rollback
                return JsonResponse({
                    'ok': False,
                    'vale_existente': int(vale_existente[0]),
                    'error': f'Já existe um vale (NUNOTA {vale_existente[0]}) para este pedido'
                }, status=400)
            
            # 3. Criar cabeçalho do vale (TOP 13)
            from datetime import datetime
            
            dtneg_str = dtneg.strftime('%d/%m/%Y') if hasattr(dtneg, 'strftime') else datetime.now().strftime('%d/%m/%Y')
            
            cab_data = {
                'CODTIPOPER': TOP_VALE,
                'CODPARC': codparc,
                'DTNEG': dtneg_str,
                'DTMOV': dtneg_str,
                'CODNAT': codnat or 1,
                'CODEMP': codemp or 1,
                'CODVEND': codvend,
                'CODCENCUS': codcencus,  # Centro de custo do pedido origem
                'NUMPEDIDO': nunota_origem,  # Vincula ao pedido de origem
                'STATUSNOTA': 'A',  # Aberto
                'PENDENTE': 'N'
            }
            
            print(f'[GERAR VALE] Criando cabeçalho com NUMPEDIDO={nunota_origem}')
            
            result = insert_cabecalho_fast(cab_data, dry_run=False)
            
            print(f'[GERAR VALE] Resultado insert_cabecalho_fast: {result}')
            
            if not result.get('ok') or not result.get('nunota'):
                return JsonResponse({
                    'ok': False,
                    'error': f'Falha ao criar cabeçalho do vale: {result.get("error", "erro desconhecido")}'
                }, status=500)
            
            nunota_vale = result['nunota']
            
            print(f'[GERAR VALE] Vale criado: NUNOTA={nunota_vale}, NUMPEDIDO={nunota_origem}')
            
            # 4. Criar itens do vale (TGFITE)
            items_criados = []
            sequencia = 0
            
            print(f'[GERAR VALE] Processando {len(items)} items para NUNOTA {nunota_vale}')
            
            for item in items:
                tipo_item = item.get('tipo', 'classificavel')  # Default: classificável
                codprod = _to_int_or(item.get('codprod'))
                sequencia_origem = _to_int_or(item.get('sequencia_origem'))
                codagregacao = item.get('codagregacao')  # Lote do item origem
                
                if not codprod:
                    print(f'[GERAR VALE] Item sem codprod, pulando: {item}')
                    continue
                
                # ============================================================
                # TIPO 1: ITEM NÃO CLASSIFICÁVEL - Duplica produto original
                # ============================================================
                if tipo_item == 'nao_classificavel':
                    sequencia += 1
                    
                    qtdneg = float(item.get('qtdneg', 0) or 0)
                    vlrunit = float(item.get('vlrunit', 0) or 0)
                    vlrtot = float(item.get('vlrtot', 0) or 0)
                    codvol = str(item.get('codvol', 'CX')).upper()
                    
                    print(f'[GERAR VALE] Item NÃO CLASSIFICÁVEL: codprod={codprod}, qtd={qtdneg}, vlrunit={vlrunit}, vlrtot={vlrtot}, lote={codagregacao}')
                    
                    item_data = {
                        'NUNOTA': nunota_vale,
                        'SEQUENCIA': sequencia,
                        'CODPROD': codprod,           # Mesmo código do pedido
                        'QTDNEG': qtdneg,             # Mesma quantidade
                        'VLRUNIT': vlrunit,           # Mesmo valor unitário
                        'VLRTOT': vlrtot,             # Mesmo valor total
                        'CODVOL': codvol,             # Mesma unidade
                        'CODAGREGACAO': codagregacao  # Mesmo lote
                    }
                    
                    result = insert_item_fast(item_data, dry_run=False)
                    
                    print(f'[GERAR VALE] Resultado insert NÃO CLASSIFICÁVEL: {result}')
                    
                    if result.get('ok'):
                        items_criados.append({
                            'sequencia': sequencia,
                            'codprod': codprod,
                            'tipo': 'NAO_CLASSIFICAVEL',
                            'qtdneg': qtdneg,
                            'vlrunit': vlrunit,
                            'vlrtot': vlrtot
                        })
                    else:
                        print(f'[GERAR VALE] *** FALHA ao criar item NÃO CLASSIFICÁVEL: {result.get("error")}')
                    
                    continue  # Próximo item
                
                # ============================================================
                # TIPO 2: ITEM CLASSIFICÁVEL - Gera EXTRA + MEDIO
                # ============================================================
                extra_cx = float(item.get('extra_cx', 0) or 0)
                extra_total = float(item.get('extra_total', 0) or 0)
                medio_cx = float(item.get('medio_cx', 0) or 0)
                medio_total = float(item.get('medio_total', 0) or 0)
                codvol = str(item.get('codvol', 'CX')).upper()
                
                print(f'[GERAR VALE] Item CLASSIFICÁVEL: codprod={codprod}, extra_cx={extra_cx}, medio_cx={medio_cx}, lote={codagregacao}')
                
                # Buscar códigos EXTRA e MÉDIO para este produto IN NATURA
                produtos_map = get_produtos_extra_medio(codprod)
                codprod_extra = produtos_map.get('extra')
                codprod_medio = produtos_map.get('medio')
                fabricante = produtos_map.get('fabricante')
                
                print(f'[GERAR VALE] Mapeamento produtos: IN NATURA={codprod} ({fabricante}) → EXTRA={codprod_extra}, MEDIO={codprod_medio}')
                
                # Obter fator de conversão CX -> KG para calcular VLRUNIT correto
                from sankhya_integration.services.oracle_conn import get_base_unit_and_factor
                base_unit_extra, fator_extra = get_base_unit_and_factor(codprod_extra, codvol) if codprod_extra else (None, None)
                base_unit_medio, fator_medio = get_base_unit_and_factor(codprod_medio, codvol) if codprod_medio else (None, None)
                
                print(f'[GERAR VALE] Fator conversão EXTRA: {fator_extra} (base: {base_unit_extra})')
                print(f'[GERAR VALE] Fator conversão MÉDIO: {fator_medio} (base: {base_unit_medio})')
                
                # Criar linha EXTRA (se houver quantidade)
                if extra_cx > 0 and extra_total > 0 and codprod_extra:
                    sequencia += 1
                    
                    # Calcular QTDNEG em KG (unidade base)
                    qtdneg_extra_kg = extra_cx * fator_extra if fator_extra else extra_cx
                    
                    # Calcular VLRUNIT por KG (não por caixa!)
                    vlrunit_extra = extra_total / qtdneg_extra_kg if qtdneg_extra_kg > 0 else 0
                    
                    print(f'[GERAR VALE] Criando item EXTRA: seq={sequencia}, codprod={codprod_extra}, qtd_cx={extra_cx}, qtd_kg={qtdneg_extra_kg}, vlrunit={vlrunit_extra}, total={extra_total}')
                    
                    item_data = {
                        'NUNOTA': nunota_vale,
                        'SEQUENCIA': sequencia,
                        'CODPROD': codprod_extra,
                        'QTDNEG': qtdneg_extra_kg,  # Em KG!
                        'VLRUNIT': vlrunit_extra,    # Por KG!
                        'VLRTOT': extra_total,
                        'CODVOL': 'KG',  # Unidade base
                        'CODAGREGACAO': codagregacao,  # Lote do item origem
                        'OBSERVACAO': f'{int(extra_cx)} cx'  # Quantidade de caixas
                    }
                    
                    result = insert_item_fast(item_data, dry_run=False)
                    
                    print(f'[GERAR VALE] Resultado insert EXTRA: {result}')
                    
                    if result.get('ok'):
                        items_criados.append({
                            'sequencia': sequencia,
                            'codprod': codprod_extra,
                            'tipo': 'EXTRA',
                            'qtdneg': extra_cx,
                            'vlrunit': vlrunit_extra,
                            'vlrtot': extra_total
                        })
                    else:
                        print(f'[GERAR VALE] *** FALHA ao criar item EXTRA: {result.get("error")}')
                else:
                    print(f'[GERAR VALE] Pulando EXTRA: cx={extra_cx}, total={extra_total}, codprod={codprod_extra}')
                
                # Criar linha MÉDIO (se houver quantidade)
                if medio_cx > 0 and medio_total > 0 and codprod_medio:
                    sequencia += 1
                    
                    # Calcular QTDNEG em KG (unidade base)
                    qtdneg_medio_kg = medio_cx * fator_medio if fator_medio else medio_cx
                    
                    # Calcular VLRUNIT por KG (não por caixa!)
                    vlrunit_medio = medio_total / qtdneg_medio_kg if qtdneg_medio_kg > 0 else 0
                    
                    print(f'[GERAR VALE] Criando item MÉDIO: seq={sequencia}, codprod={codprod_medio}, qtd_cx={medio_cx}, qtd_kg={qtdneg_medio_kg}, vlrunit={vlrunit_medio}, total={medio_total}')
                    
                    item_data = {
                        'NUNOTA': nunota_vale,
                        'SEQUENCIA': sequencia,
                        'CODPROD': codprod_medio,
                        'QTDNEG': qtdneg_medio_kg,  # Em KG!
                        'VLRUNIT': vlrunit_medio,    # Por KG!
                        'VLRTOT': medio_total,
                        'CODVOL': 'KG',  # Unidade base
                        'CODAGREGACAO': codagregacao,  # Lote do item origem
                        'OBSERVACAO': f'{int(medio_cx)} cx'  # Quantidade de caixas
                    }
                    
                    result = insert_item_fast(item_data, dry_run=False)
                    
                    print(f'[GERAR VALE] Resultado insert MÉDIO: {result}')
                    
                    if result.get('ok'):
                        items_criados.append({
                            'sequencia': sequencia,
                            'codprod': codprod_medio,
                            'tipo': 'MEDIO',
                            'qtdneg': medio_cx,
                            'vlrunit': vlrunit_medio,
                            'vlrtot': medio_total
                        })
                    else:
                        print(f'[GERAR VALE] *** FALHA ao criar item MÉDIO: {result.get("error")}')
                else:
                    print(f'[GERAR VALE] Pulando MÉDIO: cx={medio_cx}, total={medio_total}, codprod={codprod_medio}')
            
            # 5. Atualizar VLRNOTA no cabeçalho (soma dos VLRTOT dos itens)
            print(f'[GERAR VALE] Calculando VLRNOTA total de {len(items_criados)} itens...')
            
            vlrnota_total = 0.0
            for item in items_criados:
                vlrtot_item = float(item.get('vlrtot', 0) or 0)
                vlrnota_total += vlrtot_item
                print(f'[GERAR VALE] Item seq={item.get("sequencia")}, tipo={item.get("tipo")}, vlrtot={vlrtot_item}')
            
            print(f'[GERAR VALE] VLRNOTA calculado: {vlrnota_total}')
            
            if vlrnota_total > 0:
                try:
                    cur.execute("""
                        UPDATE TGFCAB 
                        SET VLRNOTA = :vlrnota 
                        WHERE NUNOTA = :nunota
                    """, vlrnota=vlrnota_total, nunota=nunota_vale)
                    
                    conn.commit()  # Commit aqui para garantir que VLRNOTA seja salvo
                    
                    print(f'[GERAR VALE] VLRNOTA atualizado no cabeçalho: R$ {vlrnota_total:.2f} para NUNOTA {nunota_vale}')
                    
                    # Verificar se foi gravado
                    cur.execute("SELECT VLRNOTA FROM TGFCAB WHERE NUNOTA = :n", n=nunota_vale)
                    row_check = cur.fetchone()
                    if row_check:
                        print(f'[GERAR VALE] Verificação: VLRNOTA no banco = {row_check[0]}')
                    
                except Exception as e:
                    print(f'[GERAR VALE] ⚠️ ERRO ao atualizar VLRNOTA: {e}')
                    import traceback
                    traceback.print_exc()
            else:
                print(f'[GERAR VALE] ⚠️ VLRNOTA é zero, não atualizando cabeçalho')
            
            return JsonResponse({
                'ok': True,
                'nunota_13': nunota_vale,
                'items_criados': len(items_criados),
                'vlrnota': vlrnota_total,
                'detalhes': items_criados
            })
    
    except Exception as e:
        logger.exception('comercial_vale_gerar failed')
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@ensure_csrf_cookie
def comercial_dashboard(request: HttpRequest) -> HttpResponse:
    """Render a página do Painel Comercial (template localizado em templates/sankhya_integration/comercial_dashboard.html)."""
    return render(request, "sankhya_integration/comercial_dashboard.html", {})


def comercial_lista(request: HttpRequest) -> JsonResponse:
    """Endpoint JSON para a 'Lista' do painel Comercial.
    Retorna linhas com Parceiro, Produto (fabricante), Qtdneg e Data da TOP 11.
    Query params aceitos: days, start, end, codparc, codprod, limit, offset
    """
    if request.method != 'GET':
        return JsonResponse({"ok": False, "error": "Use GET"}, status=405)
    try:
        def _to_int(v, default=None):
            try:
                return int(v)
            except Exception:
                return default
        days = _to_int(request.GET.get('days'), 60)
        date_start = request.GET.get('start') or None
        date_end = request.GET.get('end') or None
        codparc = _to_int(request.GET.get('codparc'))
        codprod = _to_int(request.GET.get('codprod'))
        fabricante = (request.GET.get('fabricante') or '').strip()
        limit = _to_int(request.GET.get('limit'), 50)
        offset = _to_int(request.GET.get('offset'), 0)

        rows = listar_itens_portal_basico(
            days=days,
            date_start=date_start,
            date_end=date_end,
            codparc=codparc,
            codprod=codprod,
            limit=limit,
            offset=offset,
        )
        
        # Buscar vales (TOP 13) associados aos pedidos (TOP 11)
        nunota_to_vale = {}
        vale_to_nufin = {}  # 🔥 Mapear NUNOTA do vale → NUFIN
        if rows:
            from sankhya_integration.services.oracle_conn import get_connection, get_params
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    params = get_params()
                    top_13 = int(params.get('TOP_VALE_COMPRA', 13))
                    
                    # Coletar todos os NUNOTAs únicos dos pedidos
                    nunotas_pedidos = list(set([r[6] for r in rows if r[6]]))
                    
                    if nunotas_pedidos:
                        # Buscar TOP 13 vinculadas via NUMPEDIDO
                        placeholders = ','.join([':n' + str(i) for i in range(len(nunotas_pedidos))])
                        sql = f"""
                            SELECT NUMPEDIDO, NUNOTA 
                            FROM TGFCAB 
                            WHERE CODTIPOPER = :top 
                              AND NUMPEDIDO IN ({placeholders})
                        """
                        bind_vars = {'top': top_13}
                        for i, nunota in enumerate(nunotas_pedidos):
                            bind_vars[f'n{i}'] = nunota
                        
                        cur.execute(sql, bind_vars)
                        for numpedido, nunota_vale in cur.fetchall():
                            if numpedido and nunota_vale:
                                nunota_to_vale[int(numpedido)] = int(nunota_vale)
                        
                        # 🔥 Buscar NUFIN dos vales (se já foram faturados)
                        vale_to_nufin = {}
                        if nunota_to_vale:
                            nunotas_vales = list(set(nunota_to_vale.values()))
                            placeholders_v = ','.join([':v' + str(i) for i in range(len(nunotas_vales))])
                            sql_nufin = f"""
                                SELECT NUNOTA, NUFIN 
                                FROM TGFFIN 
                                WHERE NUNOTA IN ({placeholders_v})
                                ORDER BY NUNOTA, NUFIN DESC
                            """
                            bind_vars_v = {}
                            for i, nunota_vale in enumerate(nunotas_vales):
                                bind_vars_v[f'v{i}'] = nunota_vale
                            
                            cur.execute(sql_nufin, bind_vars_v)
                            for nunota_v, nufin_v in cur.fetchall():
                                if nunota_v and nufin_v:
                                    # Pegar apenas o primeiro NUFIN (mais recente)
                                    if nunota_v not in vale_to_nufin:
                                        vale_to_nufin[int(nunota_v)] = int(nufin_v)
            except Exception as e:
                logger.warning(f'Erro ao buscar vales associados: {e}')
                vale_to_nufin = {}
        
        # Filtrar por FABRICANTE em memória, se solicitado (para evitar alterar a SQL base)
        if fabricante:
            f = fabricante.upper()
            def _ok(r):
                try:
                    prodname = (r[1] or '')
                    return f in str(prodname).upper()
                except Exception:
                    return False
            rows = [r for r in rows if _ok(r)]
        out = []
        for r in rows:
            # (NOMEPARC, PRODNAME, QTDNEG, DTNEG, CODVOL, CODPROD, NUNOTA, SEQUENCIA, GP, PESO, PRECOBASE, VLRUNIT, VLRTOT, AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2, CODAGREGACAO, CODTIPOPER, NUMPEDIDO)
            parc = r[0] if len(r) > 0 else ''
            prod = r[1] if len(r) > 1 else ''
            qtd = r[2] if len(r) > 2 else 0
            dt = r[3] if len(r) > 3 else None
            codvol = (r[4] if len(r) > 4 else None) or None
            codprod_val = (r[5] if len(r) > 5 else None)
            nunota_val = (r[6] if len(r) > 6 else None)
            sequencia_val = (r[7] if len(r) > 7 else None)
            gp_val = (r[8] if len(r) > 8 else None)
            peso_val = (r[9] if len(r) > 9 else None)
            precobase_val = (r[10] if len(r) > 10 else None)
            vlrunit_val = (r[11] if len(r) > 11 else None)
            vlrtot_val = (r[12] if len(r) > 12 else None)
            ad_simqtd1_val = (r[13] if len(r) > 13 else None)
            ad_simqtd2_val = (r[14] if len(r) > 14 else None)
            ad_simvlr1_val = (r[15] if len(r) > 15 else None)
            ad_simvlr2_val = (r[16] if len(r) > 16 else None)
            codagregacao_val = (r[17] if len(r) > 17 else None)
            codtipoper_val = (r[18] if len(r) > 18 else None)
            numpedido_val = (r[19] if len(r) > 19 else None)
            try:
                # compact date for UI: send DD/MM
                if hasattr(dt, 'strftime'):
                    dt_iso = dt.strftime('%d/%m')
                else:
                    s = str(dt)[:10]
                    dt_iso = (s[8:10] + '/' + s[5:7]) if len(s) >= 10 else None
            except Exception:
                dt_iso = None
            # Normalize QTDNEG to the displayed unit (alternative) if needed
            disp_qtd = qtd
            fator_conversao = 1.0  # fator para converter de unidade base para codvol
            try:
                if codprod_val is not None and codvol:
                    from sankhya_integration.services.oracle_conn import get_base_unit_and_factor  # lazy import
                    base, fator = get_base_unit_and_factor(int(codprod_val), str(codvol))
                    if base and str(base).upper() != str(codvol).upper() and fator and float(fator) > 0:
                        disp_qtd = float(qtd or 0) / float(fator)
                        fator_conversao = float(fator)  # salvar para conversão de preço
            except Exception:
                disp_qtd = qtd
            
            # Buscar vale associado a este pedido
            nunota_13_val = nunota_to_vale.get(int(nunota_val)) if nunota_val else None
            # Buscar NUFIN se vale já foi faturado
            nufin_val = vale_to_nufin.get(nunota_13_val) if nunota_13_val else None
            
            out.append({
                'parceiro': parc or '',
                'produto': prod or '',
                'codprod': int(codprod_val) if codprod_val is not None else None,
                'qtdneg': float(disp_qtd or 0),
                'dtneg': dt_iso,
                'nunota': int(nunota_val) if nunota_val is not None else None,
                'nunota_13': nunota_13_val,  # NUNOTA da TOP 13 (vale) se existir
                'nufin': nufin_val,  # 🔥 NUFIN do financeiro se já foi faturado
                'sequencia': int(sequencia_val) if sequencia_val is not None else None,
                'classificavel': (None if gp_val is None else (str(gp_val).upper() != 'N')),
                'codvol': (str(codvol).upper() if codvol is not None else None),
                'peso': (float(peso_val) if peso_val is not None else None),
                # Preço Inicial: usar PRECOBASE; se estiver vazio/zero, usar VLRUNIT como fallback para exibir
                'preco_inicial': (
                    float(precobase_val) if precobase_val not in (None, '') and float(precobase_val or 0) != 0 else (
                        float(vlrunit_val) if vlrunit_val not in (None, '') and float(vlrunit_val or 0) != 0 else None
                    )
                ),
                'vlrunit': (float(vlrunit_val) if vlrunit_val not in (None, '') else None),  # valor unitário em unidade base (KG)
                'fator_conversao': fator_conversao,  # TGFVOA.QUANTIDADE: quantos KG em 1 CX
                'vlrtot': (
                    float(vlrtot_val) if vlrtot_val not in (None, '') and float(vlrtot_val or 0) != 0 else 0.0
                ),
                # Simulation fields: AD_SIMQTD1→extraCx, AD_SIMVLR1→extraCustoTotal, AD_SIMQTD2→medioCx, AD_SIMVLR2→medioCustoTotal
                'ad_simqtd1': (float(ad_simqtd1_val) if ad_simqtd1_val not in (None, '') else None),
                'ad_simqtd2': (float(ad_simqtd2_val) if ad_simqtd2_val not in (None, '') else None),
                'ad_simvlr1': (float(ad_simvlr1_val) if ad_simvlr1_val not in (None, '') else None),
                'ad_simvlr2': (float(ad_simvlr2_val) if ad_simvlr2_val not in (None, '') else None),
                'codagregacao': (str(codagregacao_val) if codagregacao_val not in (None, '') else None),
                'codtipoper': (int(codtipoper_val) if codtipoper_val is not None else None),
                'numpedido': (int(numpedido_val) if numpedido_val is not None else None),
            })
        return JsonResponse({ 'ok': True, 'rows': out, 'limit': limit, 'offset': offset })
    except Exception as e:
        logger.exception('comercial_lista failed')
        return JsonResponse({ 'ok': False, 'error': str(e) }, status=500)


def comercial_vale_verificar_ou_criar_cabecalho(request: HttpRequest) -> JsonResponse:
    """
    Verifica se existe TOP 13 vinculada à TOP 11.
    Se não existir: cria cabeçalho (sem itens).
    Se existir: atualiza PRECOBASE do item (se existir).
    
    POST JSON:
    {
        "nunota_11": int,      # NUNOTA da TOP 11 (pedido de compra)
        "codprod": int,        # Código do produto editado
        "novo_preco": float    # Novo PRECOBASE a gravar
    }
    
    Retorna:
    {
        "ok": True,
        "nunota_13": 123456,
        "criou_cabecalho": True/False,
        "atualizou_item": True/False,
        "item_nao_existe": True/False
    }
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Use POST'}, status=405)
    
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'JSON inválido: {str(e)}'}, status=400)
    
    nunota_11 = payload.get('nunota_11')
    codprod = payload.get('codprod')
    novo_preco = payload.get('novo_preco')
    
    if not nunota_11:
        return JsonResponse({'ok': False, 'error': 'nunota_11 obrigatório'}, status=400)
    if not codprod:
        return JsonResponse({'ok': False, 'error': 'codprod obrigatório'}, status=400)
    if not novo_preco:
        return JsonResponse({'ok': False, 'error': 'novo_preco obrigatório'}, status=400)
    
    try:
        from sankhya_integration.services.faturamento import verificar_ou_criar_cabecalho_vale
        resultado = verificar_ou_criar_cabecalho_vale(
            nunota_11=nunota_11,
            codprod=codprod,
            novo_preco=novo_preco
        )
        
        logger.info(f'[VALE API] Resultado: {resultado}')
        
        status_code = 200 if resultado.get('ok') else 400
        return JsonResponse(resultado, status=status_code)
    except Exception as e:
        logger.exception('comercial_vale_verificar_ou_criar_cabecalho failed')
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

