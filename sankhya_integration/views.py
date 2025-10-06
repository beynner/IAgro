from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from datetime import date as _date
from django.views.decorators.csrf import ensure_csrf_cookie
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
        is_write_enabled,
        buscar_top_operacoes,
        buscar_naturezas,
        buscar_centros_resultado,
        plan_insert_item,
        insert_item,
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
    is_write_enabled = lambda: False
    buscar_top_operacoes = _missing('buscar_top_operacoes')
    buscar_naturezas = _missing('buscar_naturezas')
    buscar_centros_resultado = _missing('buscar_centros_resultado')
    plan_insert_item = _missing('plan_insert_item')
    insert_item = _missing('insert_item')
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
logger = logging.getLogger(__name__)


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "sankhya_integration/index.html")


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
    # mesma regra usada no endpoint /sankhya/item/list
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

    params = {
        "days": _to_int(request.GET.get("days")) or 7,
        "date_start": request.GET.get("start"),
        "date_end": request.GET.get("end"),
        "codparc": _to_int(request.GET.get("codparc")),
        "codprod": _to_int(request.GET.get("codprod")),
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
        # Produto: concatenar fabricantes (por produto) — solicitou usar TGFPRO.FABRICANTE
        produtos_list = info.get('produtos_entrada') or []
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
        # Compute displayed qCx: use backend value unless it's zero or clearly the same as qKg; then derive from qKg/peso
        try:
            _qcx_raw = float(info.get('qtd_cx') or 0.0)
        except Exception:
            _qcx_raw = 0.0
        try:
            _qkg_raw = float(info.get('qtd_kg') or 0.0)
        except Exception:
            _qkg_raw = 0.0
        _peso_raw = None
        try:
            _peso_raw = float(info.get('peso_inn')) if info.get('peso_inn') is not None else None
        except Exception:
            _peso_raw = None
        _qcx_disp = _qcx_raw
        try:
            if (_qcx_raw <= 0.0 or abs(_qcx_raw - _qkg_raw) < 1e-6) and (_peso_raw is not None) and (_peso_raw > 0):
                _qcx_disp = _qkg_raw / _peso_raw
        except Exception:
            _qcx_disp = _qcx_raw

        lotes.append((
            ctrl,
            info.get('parceiro') or '',
            produto_descr,
            float(_qcx_disp or 0.0),
            (float(info.get('peso_inn')) if info.get('peso_inn') is not None else 0.0),
            float(info.get('qtd_kg') or 0.0),
            0.0,  # qtde classificado (adiado/mix down)
            (info.get('statusnota_class') or ''),  # reutiliza o slot para STATUSNOTA (TOP 26)
            None,  # exemplo_nunota (não necessário por enquanto)
            None,  # exemplo_seq
            produtos_list,
            info.get('codparc'),
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

    ctx = {
        'lotes': lotes,
        'produtos_classificados': produtos_classificados,
        'sel': sel_controle,
        'initial_lote_ctrl': sel_controle,
        'initial_lote_json': json.dumps(initial_lote) if initial_lote else None,
        'params': params,
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
    }
    plan = insert_cabecalho(payload, dry_run=False)
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
    cod_inn_raw = (request.GET.get("cod_innatura") or request.GET.get("cod_inn") or "").strip()
    fabricante_flt = None
    token_flt = None
    with get_connection() as conn:
        cur = conn.cursor()
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

def header_update(request: HttpRequest) -> JsonResponse:
    """Atualiza campos do cabeçalho TGFCAB via JSON."""
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    plan = update_cabecalho({
        'NUNOTA': _to_int_or(payload.get('nunota')),
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
    }, dry_run=False)
    return JsonResponse(plan, status=200 if plan.get('executed') else 400)


def header_status_toggle(request: HttpRequest) -> JsonResponse:
    """Define STATUSNOTA do TGFCAB ('A' Atendimento, 'L' Liberado).
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
        plan = update_cabecalho({'NUNOTA': nunota, 'STATUSNOTA': status}, dry_run=False)
        ok = bool(plan.get('executed')) or bool(plan.get('ok'))
        return JsonResponse({"ok": ok, **plan}, status=200 if ok else 400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def header_status_get(request: HttpRequest) -> JsonResponse:
    """GET STATUSNOTA atual do TGFCAB para um NUNOTA."""
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
            cur.execute("SELECT STATUSNOTA FROM TGFCAB WHERE NUNOTA=:n", n=nunota)
            row = cur.fetchone()
            if not row:
                return JsonResponse({"ok": False, "error": "Cabeçalho não encontrado"}, status=404)
            status = (row[0] or '').strip().upper()
            return JsonResponse({"ok": True, "nunota": nunota, "statusnota": status})
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
                'vlu': float(vlrunit or 0),
                'vlt': float(vltot or 0),
                'obs': obs or '',
                'classifica': (None if gp is None else (str(gp).upper() != 'N')),
                'geraproducao': (None if gp is None else str(gp).upper()),
            })
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
    if request.method != 'POST':
        return JsonResponse({"ok": False, "error": "Use POST"}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
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
        # For classification notes (TOP 26), enforce lote immutability: do NOT allow changing CODAGREGACAO on update
        update_dict = {
            'NUNOTA': _to_int_or(payload.get('nunota')),
            'SEQUENCIA': seq,
            'CODPROD': _to_int_or(payload.get('codprod')),
            'QTDNEG': payload.get('qtdneg'),
            'VLRUNIT': payload.get('vlrunit'),
            'PRECOBASE': payload.get('preco_inicial'),
            'PESO': payload.get('peso'),
            'CODVOL': payload.get('codvol') or None,
            'CODLOCALORIG': _to_int_or(payload.get('codlocal'), None),
            'OBSERVACAO': (payload.get('obs') or '').strip() or None,
            # Atualizar GERAPRODUCAO se informado
            'GERAPRODUCAO': _map_gp(payload.get('geraproducao')),
        }
        try:
            if not (codtop is not None and top_class is not None and int(codtop) == int(top_class)):
                # Only allow CODAGREGACAO update when not a classification TOP
                val_ctrl = (payload.get('codagregacao') or payload.get('controle') or '').strip()
                update_dict['CODAGREGACAO'] = val_ctrl or None
        except Exception:
            # If we can't determine, be conservative and do not include CODAGREGACAO in update
            pass
        plan = update_item(update_dict, dry_run=False)
        if plan.get('executed'):
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
    # Prefer 'codagregacao' from client; keep 'controle' for temporary compatibility
    controle = (payload.get('codagregacao') or payload.get('controle') or '').strip()
    try:
        if codtop is not None and top_class is not None and int(codtop) == int(top_class):
            # If no controle provided, attempt to reuse existing from items in this note
            if not controle and nun:
                try:
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT MAX(CODAGREGACAO) FROM TGFITE WHERE NUNOTA=:n AND CODAGREGACAO IS NOT NULL", n=nun)
                        row = cur.fetchone()
                        if row and row[0]:
                            controle = str(row[0])
                except Exception:
                    controle = controle or ''
            if not controle:
                return JsonResponse({"ok": False, "errors": ["Controle (lote) obrigatório para itens de Classificação"], "error": "Controle (lote) obrigatório para itens de Classificação"}, status=400)
    except Exception:
        pass

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

    plan = insert_item({
        'NUNOTA': nun,
        'CODPROD': _to_int_or(payload.get('codprod')),
        'QTDNEG': payload.get('qtdneg'),
        'VLRUNIT': payload.get('vlrunit'),
        'PESO': payload.get('peso'),
        'CODVOL': payload.get('codvol') or 'UN',
        'CODLOCALORIG': _to_int_or(payload.get('codlocal'), 101),
        'CODAGREGACAO': (controle or None),
        'OBSERVACAO': (payload.get('obs') or '').strip() or None,
        # Inserir GERAPRODUCAO quando informado; default será do trigger ('S')
        'GERAPRODUCAO': _map_gp(payload.get('geraproducao')),
    }, dry_run=False)
    if nun_overridden:
        try:
            plan.setdefault('warnings', []).append(f"Reutilizado cabeçalho de Classificação existente (NUNOTA {nun_overridden}) para o lote {controle}.")
            plan['nunota'] = nun_overridden
        except Exception:
            pass
    if plan.get('executed'):
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

def classificacao_resumo(request: HttpRequest) -> JsonResponse:
    """GET /sankhya/classificacao/resumo/?lote=... -> { ok, lote, linhas: [ { produto, cx, kg } ] }
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
        for descr, sum_cx, sum_kg in rows:
            linhas.append({
                'produto': (descr or '').strip(),
                'cx': float(sum_cx or 0),
                'kg': float(sum_kg or 0),
            })
        return JsonResponse({"ok": True, "lote": lote, "linhas": linhas})
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
                    # QTDNEG está na base; para exibir na unidade alternativa informada (ex.: CX), divide pelo fator
                    return round(q / float(fator), 6)
                return q
            except Exception:
                return q

        # Convert rows to simple dicts for JSON (include raw PESO from TGFITE)
        results = []
        for row in classific:
            # row: (NUNOTA, SEQUENCIA, CODPROD, DESCRPROD, CODVOL, QTDNEG, PESO, VLRUNIT, VLRTOT)
            results.append({
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
            "statusnota_class": info.get('statusnota_class'),
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
        out = []
        for r in rows:
            # (NOMEPARC, PRODNAME, QTDNEG, DTNEG, CODVOL, CODPROD, NUNOTA, SEQUENCIA, GP, PESO, PRECOBASE, VLRUNIT)
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
            try:
                if codprod_val is not None and codvol:
                    from sankhya_integration.services.oracle_conn import get_base_unit_and_factor  # lazy import
                    base, fator = get_base_unit_and_factor(int(codprod_val), str(codvol))
                    if base and str(base).upper() != str(codvol).upper() and fator and float(fator) > 0:
                        disp_qtd = float(qtd or 0) / float(fator)
            except Exception:
                disp_qtd = qtd
            out.append({
                'parceiro': parc or '',
                'produto': prod or '',
                'qtdneg': float(disp_qtd or 0),
                'dtneg': dt_iso,
                'nunota': int(nunota_val) if nunota_val is not None else None,
                'sequencia': int(sequencia_val) if sequencia_val is not None else None,
                'classificavel': (None if gp_val is None else (str(gp_val).upper() != 'N')),
                'codvol': (str(codvol).upper() if codvol is not None else None),
                'peso': (float(peso_val) if peso_val is not None else None),
                # Preço Inicial: usar PRECOBASE; se estiver vazio/zero, usar VLRUNIT como fallback para exibir
                'preco_inicial': (
                    float(precobase_val) if precobase_val not in (None, '') and float(precobase_val or 0) != 0 else (
                        float(vlrunit_val) if vlrunit_val not in (None, '') and float(vlrunit_val or 0) != 0 else None
                    )
                )
            })
        return JsonResponse({ 'ok': True, 'rows': out, 'limit': limit, 'offset': offset })
    except Exception as e:
        logger.exception('comercial_lista failed')
        return JsonResponse({ 'ok': False, 'error': str(e) }, status=500)
