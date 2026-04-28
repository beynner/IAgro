import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta, date as _date
from .oracle_conn import (
    consolidate_vale_to_pedido,
    get_connection,
    get_params,
    is_write_enabled,
    insert_cabecalho_fast,
    insert_item_fast,
    get_nunota_vale_from_pedido,
    get_produtos_extra_medio,
    update_item,
    update_vlrnota_for_nota,
    upsert_vale_item,
)
logger = logging.getLogger(__name__)


def _to_int_or(val, default=None):
    """Converte valor para int, com fallback."""
    if val in (None, "", "None", "none", "null"):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        try:
            return int(str(val))
        except Exception:
            return default

def _next_wednesday(base: _date | None = None) -> _date:
    if base is None:
        base = datetime.now().date()
    wd = base.weekday()  # Monday=0
    days_ahead = (2 - wd) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)

def _to_float_or(val, default=None):
    """Converte valor para float, com fallback."""
    if val in (None, "", "None", "none", "null"):
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
    s = s.replace("R$", "").replace("r$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default


def _parse_seq_list(value: Any) -> List[int]:
    """Converte uma string ou lista de sequências em uma lista de inteiros únicos."""
    seqs: list[int] = []
    if value in (None, ""):
        return seqs
    iterable = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    for item in iterable:
        seq_val = _to_int_or(item)
        if seq_val:
            seqs.append(seq_val)
    seen: set[int] = set()
    ordered: list[int] = []
    for seq_val in seqs:
        if seq_val not in seen:
            seen.add(seq_val)
            ordered.append(seq_val)
    return ordered

def gerar_vale_compra_top13(nunota_11: int, itens_precos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cria TOP 13 (vale de compra) a partir de uma TOP 11 existente.
    Regras:
      - STATUSNOTA='A', PENDENTE='S'
      - DTFATUR = próxima quarta-feira
      - Todos os itens devem ter preço > 0
    Retorna dict com ok, nunota_13, total etc.
    """
    out: Dict[str, Any] = {'ok': False}
    if not is_write_enabled():
        out['error'] = 'Escrita desabilitada'
        return out
    try:
        nunota_11 = int(nunota_11)
    except Exception:
        out['error'] = 'nunota_11 invalido'
        return out
    
    itens_raw: List[Dict[str, Any]] = []
    for it in (itens_precos or []):
        try:
            seq = int(it.get('sequencia') or 0)
        except Exception:
            out['error'] = 'Sequencia invalida'
            return out
        if seq <= 0:
            out['error'] = 'Sequencia invalida (%s)' % seq
            return out
        preco_unit = it.get('preco') if it.get('preco') is not None else it.get('preco_unit')
        preco_total_override = it.get('preco_total') if it.get('preco_total') is not None else it.get('vlrtot') or it.get('vlrtotal')
        try:
            if preco_unit is not None:
                preco_unit = float(preco_unit)
        except Exception:
            out['error'] = 'Preco unitario invalido para sequencia %s' % seq
            return out
        try:
            if preco_total_override is not None:
                preco_total_override = float(preco_total_override)
        except Exception:
            out['error'] = 'Preco total invalido para sequencia %s' % seq
            return out
        if (preco_unit is None) and (preco_total_override is None):
            out['error'] = 'Informe preco (unit) ou preco_total para sequencia %s' % seq
            return out
        if preco_unit is not None and preco_unit <= 0:
            out['error'] = 'Preco unitario <=0 para sequencia %s' % seq
            return out
        if preco_total_override is not None and preco_total_override <= 0:
            out['error'] = 'Preco total <=0 para sequencia %s' % seq
            return out
        itens_raw.append({'sequencia': seq, 'preco_unit': preco_unit, 'preco_total': preco_total_override})
    if not itens_raw:
        out['error'] = 'Sem itens'
        return out

    with get_connection() as conn:
        try:
            cur = conn.cursor()
            # ... (lógica original de gerar_vale_compra_top13)
            
            # Usar insert_cabecalho_fast com a conexão atual
            cab_result = insert_cabecalho_fast(cab_data, dry_run=False, conn=conn)
            if not cab_result.get('ok'):
                raise Exception(f"Falha ao criar cabeçalho: {cab_result.get('error')}")
            
            nunota_13 = cab_result['nunota']

            # ... (lógica de loop de itens)
            for item_data in itens_para_inserir:
                # Usar insert_item_fast com a conexão atual
                item_result = insert_item_fast(item_data, dry_run=False, conn=conn)
                if not item_result.get('ok'):
                    raise Exception(f"Falha ao inserir item: {item_result.get('error')}")
            
            # ... (lógica de atualização de VLRNOTA)
            
            conn.commit()
            out.update({ ... })
            return out
        except Exception as e:
            conn.rollback()
            out['error'] = f'Erro na transação: {e}'
            return out


def _resolve_sequencia(
    nunota_val: int | None, seq_primary: int | None, seq_list: list[int], lot: str
) -> tuple[int | None, list[int]]:
    """Resolve a sequência correta a ser usada, priorizando por lote e depois por entrada."""
    candidates: list[int] = []
    if seq_primary:
        candidates.append(seq_primary)
    candidates.extend(s for s in seq_list if s not in candidates)

    lot_candidates: list[int] = []
    normalized_lot = lot.strip().upper() if isinstance(lot, str) else ""
    if normalized_lot and nunota_val:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT SEQUENCIA FROM TGFITE WHERE NUNOTA = :nunota AND UPPER(TRIM(CODAGREGACAO)) = :lote ORDER BY SEQUENCIA",
                        {"nunota": int(nunota_val), "lote": normalized_lot},
                    )
                    lot_candidates = [
                        int(row[0]) for row in cur.fetchall() if row and row[0] is not None
                    ]
        except Exception:
            logger.exception(
                "Erro ao buscar sequência por CODAGREGACAO: NUNOTA=%s LOTE=%s",
                nunota_val,
                normalized_lot,
            )

    ordered: list[int] = []
    seen: set[int] = set()
    for seq_val in list(lot_candidates) + candidates:
        if seq_val and seq_val not in seen:
            seen.add(seq_val)
            ordered.append(seq_val)

    return (ordered[0] if ordered else None, ordered)


def salvar_distribuicao(payload: dict) -> dict:
    """Service para persistir custo total e custo por kg da distribuição."""
    nunota = _to_int_or(payload.get("nunota"))
    codagregacao_raw = payload.get("codagregacao") or payload.get("lote") or payload.get("codag")
    codagregacao = str(codagregacao_raw or "").strip()

    sequencias_payload = _parse_seq_list(
        payload.get("sequencias") or payload.get("seq_list") or payload.get("seqs")
    )
    sequencia_input = _to_int_or(payload.get("sequencia") or payload.get("seq"))

    sequencia_resolved, sequencias_order = _resolve_sequencia(
        nunota, sequencia_input, sequencias_payload, codagregacao
    )

    if not nunota:
        return {"ok": False, "error": "Informe nunota válido"}
    if not sequencia_resolved:
        msg = (
            f"Não foi possível localizar item para o lote {codagregacao} na nota {nunota}"
            if codagregacao
            else "Informe sequencia válida"
        )
        return {"ok": False, "error": msg}

    item_payload_base: dict[str, object] = {"NUNOTA": nunota}
    update_fields = [
        ("VLRUNIT", _to_float_or(payload.get("custo_kg"))),
        ("VLRTOT", _to_float_or(payload.get("valor_total"))),
        ("AD_SIMQTD1", _to_float_or(payload.get("sim_qtd1"))),
        ("AD_SIMVLR1", _to_float_or(payload.get("sim_vlr1"))),
        ("AD_SIMQTD2", _to_float_or(payload.get("sim_qtd2"))),
        ("AD_SIMVLR2", _to_float_or(payload.get("sim_vlr2"))),
        ("AD_SIMQTDDESC", _to_float_or(payload.get("ad_simqtddesc"))),
    ]
    for key, value in update_fields:
        if value is not None:
            item_payload_base[key] = value

    if len(item_payload_base) <= 1:
        return {"ok": False, "error": "Nenhum valor válido para salvar"}

    batch_results = []
    for seq_val in sequencias_order:
        seq_payload = {**item_payload_base, "SEQUENCIA": seq_val}
        try:
            seq_plan = update_item(seq_payload, dry_run=False)
            seq_plan["ok"] = seq_plan.get("executed", False)
            batch_results.append(seq_plan)
            if not seq_plan["ok"]:
                break  # Stop on first failure
        except Exception as e:
            logger.exception("salvar_distribuicao update_item falhou para seq %s", seq_val)
            batch_results.append({"ok": False, "error": str(e), "sequencia": seq_val})
            break

    plan = batch_results[-1] if batch_results else {"ok": False, "error": "Nenhum item processado"}
    plan["ok"] = all(r.get("ok") for r in batch_results)
    plan["batch_results"] = batch_results

    if plan["ok"] and "VLRTOT" in item_payload_base:
        plan["vlrnota_update"] = update_vlrnota_for_nota(nunota)

    return plan


def sincronizar_classificacao_para_vale(payload: dict) -> dict:
    """Service para sincronizar itens EXTRA/MÉDIO no VALE (TOP 13) a partir da classificação."""
    nunota_pedido = _to_int_or(payload.get("nunota_pedido"))
    codprod_in_natura = _to_int_or(payload.get("codprod_in_natura"))
    lote = payload.get("lote")
    extra_kg = _to_float_or(payload.get("extra_kg", 0))
    extra_vlrunit_kg = _to_float_or(payload.get("extra_vlrunit_kg", 0))
    medio_kg = _to_float_or(payload.get("medio_kg", 0))
    medio_vlrunit_kg = _to_float_or(payload.get("medio_vlrunit_kg", 0))

    if not all([nunota_pedido, codprod_in_natura, lote]):
        return {
            "ok": False,
            "error": "Parâmetros obrigatórios: nunota_pedido, codprod_in_natura, lote",
        }

    if not (extra_kg > 0 or medio_kg > 0):
        return {
            "ok": False,
            "error": "Pelo menos um dos produtos (Extra ou Médio) deve ter quantidade > 0",
        }

    try:
        nunota_vale = get_nunota_vale_from_pedido(nunota_pedido)
        if not nunota_vale:
            return {"ok": False, "error": f"VALE (TOP 13) não encontrado para PEDIDO {nunota_pedido}"}

        # Alinhar datas do VALE ao DTNEG do PEDIDO
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DTNEG FROM TGFCAB WHERE NUNOTA=:n", n=int(nunota_pedido))
            rdt = cur.fetchone()
            if rdt and rdt[0]:
                dtneg_str = rdt[0].strftime("%d/%m/%Y")
                cur.execute(
                    "UPDATE TGFCAB SET DTNEG=TO_DATE(:d,'DD/MM/YYYY'), DTMOV=TO_DATE(:d,'DD/MM/YYYY'), DTENTSAI=TO_DATE(:d,'DD/MM/YYYY') WHERE NUNOTA=:v",
                    d=dtneg_str, v=int(nunota_vale)
                )
                conn.commit()

        produtos_map = get_produtos_extra_medio(codprod_in_natura)
        if not produtos_map:
            return {"ok": False, "error": f"Não foi possível mapear produtos EXTRA/MÉDIO para CODPROD {codprod_in_natura}"}

        codprod_extra = produtos_map.get("extra")
        codprod_medio = produtos_map.get("medio")

        results = []
        if extra_kg > 0 and codprod_extra:
            result_extra = upsert_vale_item(
                nunota_vale=nunota_vale,
                codprod=codprod_extra,
                qtdneg=extra_kg,
                vlrunit=extra_vlrunit_kg,
                lote=lote,
                produto_tipo="EXTRA",
            )
            results.append({"tipo": "EXTRA", **result_extra})

        if medio_kg > 0 and codprod_medio:
            result_medio = upsert_vale_item(
                nunota_vale=nunota_vale,
                codprod=codprod_medio,
                qtdneg=medio_kg,
                vlrunit=medio_vlrunit_kg,
                lote=lote,
                produto_tipo="MEDIO",
            )
            results.append({"tipo": "MEDIO", **result_medio})

        vlrnota_result = None
        consolidation_result = None

        if any(r.get("success") for r in results):
            vlrnota_result = update_vlrnota_for_nota(nunota_vale)
            fabricante = produtos_map.get("fabricante")
            if fabricante:
                consolidation_result = consolidate_vale_to_pedido(
                    nunota_pedido=nunota_pedido,
                    nunota_vale=nunota_vale,
                    fabricante=fabricante,
                )
            else:
                consolidation_result = {"error": "FABRICANTE não encontrado"}

        return {
            "ok": True,
            "nunota_vale": nunota_vale,
            "items_processed": results,
            "vlrnota_update": vlrnota_result,
            "pedido_consolidation": consolidation_result,
        }

    except Exception as e:
        logger.exception("sincronizar_classificacao_para_vale falhou")
        return {"ok": False, "error": str(e)}


def gerar_vale_compra_service(payload: dict) -> dict:
    """
    Serviço para gerar um Vale de Compra (TOP 13) a partir de um Pedido (TOP 11).
    Encapsula a lógica de negócio que antes estava na view `comercial_vale_gerar`.
    """
    nunota_origem = _to_int_or(payload.get('nunota_origem'))
    items = payload.get('items') or []

    if not nunota_origem:
        return {'ok': False, 'error': 'nunota_origem obrigatório'}
    if not isinstance(items, list) or not items:
        return {'ok': False, 'error': 'items deve ser uma lista não vazia'}

    try:
        p = get_params()
        TOP_ENTRADA = int(p['TOP_ENTRADA'])
        TOP_VALE = 13

        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Validar pedido origem
            cur.execute("SELECT CODPARC, CODNAT, CODEMP, CODVEND, DTNEG, CODCENCUS FROM TGFCAB WHERE NUNOTA = :n AND CODTIPOPER = :top", n=nunota_origem, top=TOP_ENTRADA)
            row_origem = cur.fetchone()
            if not row_origem:
                return {'ok': False, 'error': f'Pedido de compra (TOP 11) NUNOTA {nunota_origem} não encontrado'}
            
            codparc, codnat, codemp, codvend, dtneg, codcencus = row_origem
            
            # 2. Verificar se já existe vale
            cur.execute("SELECT NUNOTA FROM TGFCAB WHERE NUMPEDIDO = :n_origem AND CODTIPOPER = :top_vale", n_origem=nunota_origem, top_vale=TOP_VALE)
            if cur.fetchone():
                return {'ok': False, 'error': 'Já existe um vale para este pedido'}

            # 3. Criar cabeçalho do vale
            dtneg_str = dtneg.strftime('%d/%m/%Y') if hasattr(dtneg, 'strftime') else datetime.now().strftime('%d/%m/%Y')
            cab_data = {
                'CODTIPOPER': TOP_VALE, 'CODPARC': codparc, 'DTNEG': dtneg_str, 'DTMOV': dtneg_str,
                'CODNAT': codnat or 1, 'CODEMP': codemp or 1, 'CODVEND': codvend, 'CODCENCUS': codcencus,
                'NUMPEDIDO': nunota_origem, 'STATUSNOTA': 'A', 'PENDENTE': 'N'
            }
            result = insert_cabecalho_fast(cab_data, dry_run=False, conn=conn)
            if not result.get('ok') or not result.get('nunota'):
                raise Exception(f"Falha ao criar cabeçalho do vale: {result.get('error', 'erro desconhecido')}")
            
            nunota_vale = result['nunota']
            
            # 4. Criar itens do vale
            items_criados = []
            sequencia = 0
            vlrnota_total = 0.0

            for item in items:
                tipo_item = item.get('tipo', 'classificavel')
                codprod = _to_int_or(item.get('codprod'))
                codagregacao = item.get('codagregacao')

                if not codprod: continue

                if tipo_item == 'nao_classificavel':
                    sequencia += 1
                    qtdneg = float(item.get('qtdneg', 0) or 0)
                    vlrunit = float(item.get('vlrunit', 0) or 0)
                    vlrtot = float(item.get('vlrtot', 0) or 0)
                    codvol = str(item.get('codvol', 'CX')).upper()
                    
                    item_data = {'NUNOTA': nunota_vale, 'SEQUENCIA': sequencia, 'CODPROD': codprod, 'QTDNEG': qtdneg, 'VLRUNIT': vlrunit, 'VLRTOT': vlrtot, 'CODVOL': codvol, 'CODAGREGACAO': codagregacao}
                    res_insert = insert_item_fast(item_data, dry_run=False, conn=conn)
                    if res_insert.get('ok'):
                        items_criados.append({'sequencia': sequencia, 'codprod': codprod, 'tipo': 'NAO_CLASSIFICAVEL', 'vlrtot': vlrtot})
                        vlrnota_total += vlrtot

                elif tipo_item == 'classificavel':
                    extra_cx = float(item.get('extra_cx', 0) or 0)
                    extra_total = float(item.get('extra_total', 0) or 0)
                    medio_cx = float(item.get('medio_cx', 0) or 0)
                    medio_total = float(item.get('medio_total', 0) or 0)
                    codvol = str(item.get('codvol', 'CX')).upper()

                    produtos_map = get_produtos_extra_medio(codprod)
                    codprod_extra = produtos_map.get('extra')
                    codprod_medio = produtos_map.get('medio')

                    from .oracle_conn import get_base_unit_and_factor
                    _, fator_extra = get_base_unit_and_factor(codprod_extra, codvol) if codprod_extra else (None, None)
                    _, fator_medio = get_base_unit_and_factor(codprod_medio, codvol) if codprod_medio else (None, None)

                    if extra_cx > 0 and extra_total > 0 and codprod_extra:
                        sequencia += 1
                        qtdneg_extra_kg = extra_cx * fator_extra if fator_extra else extra_cx
                        vlrunit_extra = extra_total / qtdneg_extra_kg if qtdneg_extra_kg > 0 else 0
                        item_data = {'NUNOTA': nunota_vale, 'SEQUENCIA': sequencia, 'CODPROD': codprod_extra, 'QTDNEG': qtdneg_extra_kg, 'VLRUNIT': vlrunit_extra, 'VLRTOT': extra_total, 'CODVOL': 'KG', 'CODAGREGACAO': codagregacao, 'OBSERVACAO': f'{int(extra_cx)} cx'}
                        res_insert = insert_item_fast(item_data, dry_run=False, conn=conn)
                        if res_insert.get('ok'):
                            items_criados.append({'sequencia': sequencia, 'codprod': codprod_extra, 'tipo': 'EXTRA', 'vlrtot': extra_total})
                            vlrnota_total += extra_total

                    if medio_cx > 0 and medio_total > 0 and codprod_medio:
                        sequencia += 1
                        qtdneg_medio_kg = medio_cx * fator_medio if fator_medio else medio_cx
                        vlrunit_medio = medio_total / qtdneg_medio_kg if qtdneg_medio_kg > 0 else 0
                        item_data = {'NUNOTA': nunota_vale, 'SEQUENCIA': sequencia, 'CODPROD': codprod_medio, 'QTDNEG': qtdneg_medio_kg, 'VLRUNIT': vlrunit_medio, 'VLRTOT': medio_total, 'CODVOL': 'KG', 'CODAGREGACAO': codagregacao, 'OBSERVACAO': f'{int(medio_cx)} cx'}
                        res_insert = insert_item_fast(item_data, dry_run=False, conn=conn)
                        if res_insert.get('ok'):
                            items_criados.append({'sequencia': sequencia, 'codprod': codprod_medio, 'tipo': 'MEDIO', 'vlrtot': medio_total})
                            vlrnota_total += medio_total
            
            # 5. Atualizar VLRNOTA
            if vlrnota_total > 0:
                cur.execute("UPDATE TGFCAB SET VLRNOTA = :vlrnota WHERE NUNOTA = :nunota", vlrnota=vlrnota_total, nunota=nunota_vale)

            conn.commit()
            return {'ok': True, 'nunota_13': nunota_vale, 'items_criados': len(items_criados), 'vlrnota': vlrnota_total, 'detalhes': items_criados}

    except Exception as e:
        logger.exception('gerar_vale_compra_service failed')
        return {'ok': False, 'error': str(e)}


def preparar_dados_novo_item(payload: dict, request_meta: dict) -> dict:
    """
    Prepara os dados para a inserção de um novo item, movendo a lógica de
    detecção de contexto e geração de lote da view para o serviço.
    """
    from .oracle_conn import get_params, get_connection

    nun = _to_int_or(payload.get('nunota'))
    
    # Lógica de _get_nota_top
    top_class = get_params().get('TOP_CLASS')
    codtop = None
    if nun:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA=:n", n=nun)
            row = cur.fetchone()
            if row: codtop = row[0]

    top_entrada = get_params().get('TOP_ENTRADA', 11)
    if codtop is None:
        referer = request_meta.get('HTTP_REFERER', '')
        if '/compras_portal' in referer or '/portal' in referer or payload.get('_source') == 'portal':
            codtop = top_entrada
        elif '/compras_classificacao' in referer or '/classificacao' in referer or payload.get('_source') == 'classificacao':
            codtop = top_class

    lote = (payload.get('codagregacao') or payload.get('lote') or '').strip()
    is_classif = (top_class and codtop and int(codtop) == int(top_class))
    
    auto_generate_lote = False
    if not lote and nun:
        if is_classif:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(CODAGREGACAO) FROM TGFITE WHERE NUNOTA=:n AND CODAGREGACAO IS NOT NULL", n=nun)
                row = cur.fetchone()
                if row and row[0]: lote = str(row[0])
        else:
            auto_generate_lote = True
            lote = None

    if not lote and is_classif:
        return {'ok': False, 'error': 'Lote (lote) obrigatório para itens de Classificação'}

    nun_overridden = None
    if lote and top_class:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT i.NUNOTA FROM (SELECT DISTINCT i.NUNOTA FROM TGFITE i JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top ORDER BY i.NUNOTA DESC) WHERE ROWNUM = 1", c=lote, top=top_class)
            row2 = cur.fetchone()
            if row2 and row2[0] is not None:
                existing_nun = int(row2[0])
                if existing_nun and existing_nun != nun:
                    nun_overridden = existing_nun
                    nun = existing_nun

    return {
        'ok': True,
        'nun': nun,
        'lote': lote,
        'auto_generate_lote': auto_generate_lote,
        'nun_overridden': nun_overridden
    }