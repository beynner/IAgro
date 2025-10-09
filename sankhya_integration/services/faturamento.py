from datetime import datetime, timedelta, date as _date
from typing import List, Dict, Any
from .oracle_conn import (
    get_connection,
    get_params,
    is_write_enabled,
    )

try:
    import oracledb as cx_Oracle
except ImportError:
    try:
        import cx_Oracle  # type: ignore
    except ImportError:
        cx_Oracle = None  # type: ignore

def _next_wednesday(base: _date | None = None) -> _date:
    if base is None:
        base = datetime.now().date()
    wd = base.weekday()  # Monday=0
    days_ahead = (2 - wd) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


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
    # Novo modelo: por padrão 'preco' é considerado PREÇO UNITÁRIO.
    # Se o item trouxer 'preco_total' ou 'vlrtot', esses têm prioridade como valor total.
    # Assim evitamos inflar VLRNOTA quando era enviado apenas o preço unitário.
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
        cur = conn.cursor()
        # Buscar dados do pedido em uma única query, incluindo NUMNOTA
        cur.execute("SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, CODTIPOPER, DHTIPOPER, DTNEG, NUMNOTA FROM TGFCAB WHERE NUNOTA=:n", n=nunota_11)
        row = cur.fetchone()
        if not row:
            out['error'] = 'NUNOTA 11 nao encontrada'
            return out
        CODEMP, CODPARC, CODNAT, CODCENCUS, _ct, _dh, _dt, numnota_orig = row
        CODAGREGACAO = None  # Será reutilizado dos itens origem (cada item tem seu CODAGREGACAO)
        
        # Se NUMNOTA for 0 ou nulo, usamos o próprio NUNOTA como referência
        numnota_pedido = numnota_orig if (numnota_orig and numnota_orig != 0) else nunota_11
        
        params = get_params()
        top_13 = int(params.get('TOP_VALE_COMPRA', 13))
        
        # Buscar TIPMOV da TOP 13
        cur.execute("SELECT TIPMOV, DHALTER FROM (SELECT TIPMOV, DHALTER FROM TGFTOP WHERE CODTIPOPER=:k ORDER BY DHALTER DESC) WHERE ROWNUM=1", k=top_13)
        r = cur.fetchone()
        if not r:
            out['error'] = f'TOP {top_13} não encontrada'
            return out
        tipmov_13 = r[0] if r[0] else 'C'
        dhtipoper_13 = r[1]  # DHALTER da TOP para usar como DHTIPOPER
        
        hoje = datetime.now().strftime('%d/%m/%Y')
        dtfatur = _next_wednesday().strftime('%d/%m/%Y')
        
        # Gerar NUNOTA manualmente (MAX+1)
        cur.execute("SELECT NVL(MAX(NUNOTA),0)+1 FROM TGFCAB")
        nunota_13 = int(cur.fetchone()[0])
        
        # INSERT otimizado direto no TGFCAB
        cur.execute("""
            INSERT INTO TGFCAB (
                NUNOTA, CODEMP, CODEMPNEGOC, CODPARC, CODTIPOPER, DHTIPOPER, TIPMOV,
                CODNAT, CODCENCUS, DTNEG, DTMOV, DTENTSAI,
                NUMNOTA, NUMPEDIDO, PENDENTE, STATUSNOTA, DTALTER
            ) VALUES (
                :NUNOTA, :CODEMP, :CODEMP, :CODPARC, :CODTIPOPER, :DHTIPOPER, :TIPMOV,
                :CODNAT, :CODCENCUS, TO_DATE(:DTNEG,'DD/MM/YYYY'), TO_DATE(:DTMOV,'DD/MM/YYYY'), TO_DATE(:DTENTSAI,'DD/MM/YYYY'),
                :NUMNOTA, :NUMPEDIDO, :PENDENTE, :STATUSNOTA, SYSDATE
            )
        """, {
            'NUNOTA': nunota_13,
            'CODEMP': CODEMP,
            'CODPARC': CODPARC,
            'CODTIPOPER': top_13,
            'DHTIPOPER': dhtipoper_13,
            'TIPMOV': tipmov_13,
            'CODNAT': CODNAT,
            'CODCENCUS': CODCENCUS,
            'DTNEG': hoje,
            'DTMOV': hoje,
            'DTENTSAI': hoje,
            'NUMNOTA': 0,
            'NUMPEDIDO': numnota_pedido,
            'PENDENTE': 'S',
            'STATUSNOTA': 'A'
        })
        
        # Atualizar DTFATUR (tentar direto, falhar silenciosamente se coluna não existir)
        try:
            cur.execute("UPDATE TGFCAB SET DTFATUR=TO_DATE(:d,'DD/MM/YYYY') WHERE NUNOTA=:n", d=dtfatur, n=nunota_13)
        except Exception:
            pass
        # Detectar coluna de lote dinamicamente - tentar cada uma até funcionar
        lote_col = None
        for cand in ['CODAGREGACAO', 'CONTROLE', 'LOTE', 'CODCONTROLE']:
            try:
                cur.execute(f"SELECT {cand} FROM TGFITE WHERE NUNOTA=:n AND ROWNUM=1", n=nunota_11)
                cur.fetchone()
                lote_col = cand
                break
            except Exception:
                continue
        if not lote_col:
            out['error'] = 'Nenhuma coluna de lote (CODAGREGACAO/CONTROLE/LOTE) encontrada em TGFITE'
            return out
        # Montar SELECT dinamicamente
        cur.execute(f"SELECT SEQUENCIA, CODPROD, QTDNEG, CODVOL, {lote_col} FROM TGFITE WHERE NUNOTA=:n", n=nunota_11)
        origem = cur.fetchall()
        if not origem:
            out['error'] = 'Nota 11 sem itens para duplicar'
            return out
        # Validar se algum item não possui coluna de lote preenchida
        itens_sem_lote = [r for r in origem if not r[4]]
        if itens_sem_lote:
            out['error'] = 'Itens sem lote na coluna %s não podem ser duplicados' % lote_col
            out['itens_sem_lote'] = [int(r[0]) for r in itens_sem_lote]
            return out
        total = 0.0
        seq_new = 0
        breakdown = []
        for seq11, codprod, qtdneg, codvol, codag in origem:
            pricing = next((iv for iv in itens_raw if iv['sequencia'] == seq11), None)
            if not pricing:
                conn.rollback()
                out['error'] = 'Preco nao informado para sequencia %s' % seq11
                return out
            try:
                qtd_float = float(qtdneg)
            except Exception:
                qtd_float = 0.0
            preco_total = None
            preco_unit = None
            # Se veio preco_total explícito, usar; senão calcular total = preco_unit * qtd
            if pricing.get('preco_total') is not None:
                preco_total = float(pricing['preco_total'])
                if qtd_float > 0:
                    preco_unit = round(preco_total / qtd_float, 6)
                else:
                    preco_unit = 0.0
                pricing_mode = 'total'
            else:
                preco_unit = float(pricing.get('preco_unit') or 0.0)
                preco_total = round(preco_unit * qtd_float, 2)
                pricing_mode = 'unit'
            total += preco_total
            seq_new += 1
            try:
                cur.execute(
                    f"INSERT INTO TGFITE (NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT, CODVOL, {lote_col}, OBSERVACAO) "
                    f"VALUES (:n,:s,:e,:p,:q,:u,:t,:v,:c,:o)",
                    n=nunota_13, s=seq_new, e=CODEMP, p=codprod, q=qtdneg, u=preco_unit, t=preco_total, v=codvol, c=codag, o='Gerado via app'
                )
            except Exception as ie:
                conn.rollback()
                out['error'] = 'Falha inserir item seq %s: %s' % (seq11, ie)
                return out
            breakdown.append({'sequencia': int(seq11), 'codprod': int(codprod), 'qtd': qtd_float, 'vlrunit': preco_unit, 'vlrtot': preco_total, 'lote': codag, 'lote_column': lote_col, 'pricing_mode': pricing_mode})
        # Recalcular VLRNOTA diretamente do banco para garantir consistência (evita divergência de arredondamento)
        try:
            cur.execute("SELECT NVL(SUM(VLRTOT),0) FROM TGFITE WHERE NUNOTA=:n", n=nunota_13)
            (db_total,) = cur.fetchone()
            if db_total is not None:
                total = float(db_total)
        except Exception:
            pass

        # Atualizar VLRNOTA com o total calculado
        try:
            cur.execute("UPDATE TGFCAB SET VLRNOTA=:v WHERE NUNOTA=:n", v=total, n=nunota_13)
        except Exception:
            pass
            
        conn.commit()
        out.update({'ok': True, 'nunota_11': nunota_11, 'nunota_13': nunota_13, 'dtfatur': dtfatur, 'status': 'A', 'total': total, 'itens': len(origem), 'items_breakdown': breakdown, 'lote_column_used': lote_col})
        return out
    return out
