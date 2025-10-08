import os
import importlib
try:
    # Dynamically import legacy driver if available
    cx_Oracle = importlib.import_module('cx_Oracle')  # type: ignore
except Exception:
    # Fallback to python-oracledb (thin/thick modes). Keep the same name for compatibility.
    import oracledb as cx_Oracle
    # If running with python-oracledb in THIN mode and the target DB is old (DPY-3010), allow auto switch to THICK
    # by initializing the Oracle Instant Client when its directory is provided via env vars.
    try:
        # is_thin_mode is available only in python-oracledb
        is_thin = getattr(cx_Oracle, 'is_thin_mode', None)
        if callable(is_thin) and is_thin():
            lib_dir = (
                os.getenv('ORACLE_CLIENT_LIB_DIR')
                or os.getenv('SANKHYA_ORACLE_CLIENT')
                or os.getenv('ORACLE_HOME')
            )
            if lib_dir and os.path.isdir(lib_dir):
                # Initialize thick mode using Instant Client (explicit path)
                cx_Oracle.init_oracle_client(lib_dir=lib_dir)
            else:
                # Fallback: attempt to initialize using system PATH/registry (works if client is on PATH)
                try:
                    cx_Oracle.init_oracle_client()
                except Exception:
                    pass
    except Exception:
        # If initialization fails, keep thin mode; connection will raise a clear error (e.g., DPY-3010)
        pass

from contextlib import contextmanager

# Optional global connection pool to reduce connect overhead
_POOL = None

def _get_app_config():
    try:
        from django.conf import settings
        cfg = getattr(settings, 'SANKHYA_CONFIG', {})
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return {}


def _get_dsn_cfg():
    cfg = _get_app_config().get('DB', {})
    host = os.getenv('SANKHYA_DB_HOST', cfg.get('host', 'hfsemear.ddns.net'))
    port = int(os.getenv('SANKHYA_DB_PORT', cfg.get('port', 1521)))
    service_name = os.getenv('SANKHYA_DB_SERVICE', cfg.get('service_name', 'XE'))
    sid = os.getenv('SANKHYA_DB_SID', cfg.get('sid'))  # optional override when DB uses SID
    full_dsn = os.getenv('SANKHYA_DB_DSN', cfg.get('dsn'))  # optional: full easy connect/tnsnames alias
    user = os.getenv('SANKHYA_DB_USER', cfg.get('user', 'Sankhya'))
    password = os.getenv('SANKHYA_DB_PASSWORD', cfg.get('password', 'tecsis'))
    return {
        'host': host,
        'port': port,
        'service_name': service_name,
        'sid': sid,
        'dsn': full_dsn,
        'user': user,
        'password': password,
    }


DEFAULT_PARAMS = {
    'TOP_ENTRADA': 11,
    'TOP_CLASS': 26,
    'TOP_VALE_COMPRA': 13,
    'TOP_PED_VENDA': 34,
    'TOP_VENDAS': [35, 37],
    'TOP_AVARIA': 30,
    'PROD_IN_NATURA': 863,
    'PROD_CLASS_LIST': [358, 359, 907],
    'PROD_DESCARTE': 910,
    # Flags de controle para automação
    'AUTO_DUPLICATE_CLASSIFICATION': False,
    'AUTO_DUPLICATE_ON_SAVE': False,    # Duplicar ao salvar item classificável
    'AUTO_CREATE_VALE_COMPRA': False,  # Será implementado na tela Comercial
    'FALLBACK_MANUAL_ENABLED': True,
}


def get_params():
    cfg = _get_app_config().get('PARAMS', {})
    params = DEFAULT_PARAMS.copy()
    if isinstance(cfg, dict):
        params.update(cfg)
    return params


# ===== Lightweight in-memory caches (per-process) to reduce DB roundtrips =====
# Safe because Oracle metadata and product volume mappings change rarely during a Django worker lifetime.
# If needed, call clear_caches() after DDL changes or VOAs maintenance.
_COLS_CACHE: dict[str, set] = {}
_PK_CACHE: dict[str, list] = {}
_FK_CACHE: dict[str, list] = {}
_NN_CACHE: dict[str, list] = {}
_TRG_CACHE: dict[str, list] = {}
_LIKE_COLS_CACHE: dict[tuple[str, str], list] = {}
_BASE_UNIT_CACHE: dict[int, str] = {}
_FACTOR_CACHE: dict[tuple[int, str], float | None] = {}


def clear_caches(kind: str | None = None):
    kinds = {k.strip().lower() for k in ([kind] if kind else [])}
    def m(k):
        return (not kinds) or (k in kinds)
    if m('cols'):
        _COLS_CACHE.clear()
    if m('pk'):
        _PK_CACHE.clear()
    if m('fk'):
        _FK_CACHE.clear()
    if m('nn') or m('notnull'):
        _NN_CACHE.clear()
    if m('trg') or m('triggers'):
        _TRG_CACHE.clear()
    if m('like') or m('likecols'):
        _LIKE_COLS_CACHE.clear()
    if m('unit') or m('base'):
        _BASE_UNIT_CACHE.clear()
    if m('factor') or m('unit'):
        _FACTOR_CACHE.clear()


def _make_dsn(host: str, port: int, service_name: str | None, sid: str | None, full_dsn: str | None) -> str:
    # Use makedsn when available; otherwise use host:port/service_name
    try:
        # If a full DSN (easy connect or tns alias) is given, prefer it as-is
        if full_dsn:
            return full_dsn
        if sid:
            return cx_Oracle.makedsn(host, port, sid=sid)
        return cx_Oracle.makedsn(host, port, service_name=service_name)
    except Exception:
        if full_dsn:
            return full_dsn
        if sid:
            return f"{host}:{port}/{sid}"
        return f"{host}:{port}/{service_name}"


@contextmanager
def get_connection():
    global _POOL
    dsn_cfg = _get_dsn_cfg()
    dsn = _make_dsn(
        dsn_cfg['host'], dsn_cfg['port'], dsn_cfg.get('service_name'), dsn_cfg.get('sid'), dsn_cfg.get('dsn')
    )
    conn = None
    try:
        # Initialize pool on first use when supported by the driver
        if _POOL is None and hasattr(cx_Oracle, 'create_pool'):
            try:
                _POOL = cx_Oracle.create_pool(
                    user=dsn_cfg['user'], password=dsn_cfg['password'], dsn=dsn,
                    min=1, max=max(4, int(os.getenv('SANKHYA_DB_POOL_MAX', '4'))), increment=1
                )
            except Exception:
                _POOL = None
        if _POOL is not None and hasattr(_POOL, 'acquire'):
            conn = _POOL.acquire()
        else:
            conn = cx_Oracle.connect(user=dsn_cfg['user'], password=dsn_cfg['password'], dsn=dsn)
    except Exception:
        # Fallback to direct connection if pooling failed
        conn = cx_Oracle.connect(user=dsn_cfg['user'], password=dsn_cfg['password'], dsn=dsn)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_oracle_connection():
    try:
        with get_connection() as conn:
            conn.ping()
            print('Conexão Oracle bem-sucedida!')
        return True
    except Exception as e:
        print(f'Erro na conexão Oracle: {e}')
        return False


def select_all_tgfpar():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT NOMEPARC FROM TGFPAR')
            rows = cursor.fetchall()
            for row in rows:
                print(row)
            return rows
    except Exception as e:
        print(f'Erro ao consultar tgfpar: {e}')
        return []


def is_write_enabled() -> bool:
    try:
        cfg = _get_app_config()
        if isinstance(cfg, dict) and cfg.get('WRITE_ENABLED') is True:
            return True
    except Exception:
        pass
    return os.getenv('PACKINGHOUSE_WRITE_ENABLED', 'false').lower() in ('1', 'true', 'yes', 'on')


def _fetchall(conn, sql: str, **binds):
    cur = conn.cursor()
    cur.execute(sql, **binds)
    return cur.fetchall()


def get_table_pk(table: str):
    t = str(table).upper()
    if t in _PK_CACHE:
        return _PK_CACHE[t]
    sql = (
        "SELECT cc.column_name FROM user_constraints c "
        "JOIN user_cons_columns cc ON cc.constraint_name = c.constraint_name "
        "WHERE c.table_name = :t AND c.constraint_type = 'P' ORDER BY cc.position"
    )
    with get_connection() as conn:
        rows = _fetchall(conn, sql, t=t)
        _PK_CACHE[t] = [r[0] for r in rows]
        return _PK_CACHE[t]


def get_table_fks(table: str):
    t = str(table).upper()
    if t in _FK_CACHE:
        return _FK_CACHE[t]
    sql = (
        "SELECT a.column_name, pk.table_name r_table, pkc.column_name r_column "
        "FROM user_constraints c "
        "JOIN user_cons_columns a  ON a.constraint_name  = c.constraint_name "
        "JOIN user_constraints pk ON pk.constraint_name = c.r_constraint_name "
        "JOIN user_cons_columns pkc ON pkc.constraint_name = pk.constraint_name AND pkc.position = a.position "
        "WHERE c.table_name = :t AND c.constraint_type = 'R' ORDER BY a.position"
    )
    with get_connection() as conn:
        _FK_CACHE[t] = _fetchall(conn, sql, t=t)
        return _FK_CACHE[t]


def get_not_null_cols(table: str):
    t = str(table).upper()
    if t in _NN_CACHE:
        return _NN_CACHE[t]
    sql = (
        "SELECT column_name, data_type, data_default FROM user_tab_cols "
        "WHERE table_name=:t AND nullable='N'"
    )
    with get_connection() as conn:
        _NN_CACHE[t] = _fetchall(conn, sql, t=t)
        return _NN_CACHE[t]


def get_triggers(table: str):
    t = str(table).upper()
    if t in _TRG_CACHE:
        return _TRG_CACHE[t]
    sql = "SELECT trigger_name, status FROM user_triggers WHERE table_name = :t"
    with get_connection() as conn:
        _TRG_CACHE[t] = _fetchall(conn, sql, t=t)
        return _TRG_CACHE[t]


def find_triggers_using_nextval(table: str, column_keyword: str = 'NUNOTA'):
    sql = (
        "SELECT trigger_name FROM user_triggers "
        "WHERE table_name=:t AND UPPER(trigger_body) LIKE :k1 AND UPPER(trigger_body) LIKE '%NEXTVAL%'"
    )
    with get_connection() as conn:
        try:
            return [r[0] for r in _fetchall(conn, sql, t=table.upper(), k1=f"%{column_keyword.upper()}%")]
        except Exception:
            return []


def list_sequences_like(pattern: str):
    sql = "SELECT sequence_name FROM user_sequences WHERE sequence_name LIKE :p"
    with get_connection() as conn:
        return [r[0] for r in _fetchall(conn, sql, p=pattern.upper())]


def _exists(sql: str, **binds) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, **binds)
        return cur.fetchone() is not None


def validar_cabecalho_minimo(d: dict):
    errs: list[str] = []
    warns: list[str] = []

    # Campos mínimos (considerando exigências do TRG_INC_TGFCAB)
    required = ['CODEMP', 'CODPARC', 'CODTIPOPER', 'CODNAT', 'CODCENCUS', 'DTNEG']
    for k in required:
        if d.get(k) in (None, ''):
            errs.append(f"Campo obrigatório ausente: {k}")

    # Empresas (origem e negociação) em TSIEMP
    try:
        if d.get('CODEMP'):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TSIEMP WHERE CODEMP=:v", v=d['CODEMP'])
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append(f"Empresa (CODEMP={d['CODEMP']}) inexistente em TSIEMP")
        else:
            errs.append("Empresa (CODEMP) obrigatória")
    except Exception:
        warns.append("Não foi possível validar TSIEMP (CODEMP)")

    try:
        if d.get('CODEMPNEGOC'):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TSIEMP WHERE CODEMP=:v", v=d['CODEMPNEGOC'])
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append(f"Empresa de negociação (CODEMPNEGOC={d['CODEMPNEGOC']}) inexistente em TSIEMP")
    except Exception:
        warns.append("Não foi possível validar TSIEMP (CODEMPNEGOC)")

    # Parceiro ativo + papel conforme TIPMOV (fornecedor vs cliente)
    try:
        if d.get('CODPARC') is not None:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT ATIVO, FORNECEDOR, CLIENTE FROM TGFPAR WHERE CODPARC=:v", v=d['CODPARC'])
                row = cur.fetchone()
                if not row:
                    errs.append("Parceiro (CODPARC) inexistente")
                else:
                    ativo, fornecedor, cliente = row
                    if str(ativo).upper() != 'S':
                        errs.append("Parceiro (CODPARC) inativo")
                    tipmov = (d.get('TIPMOV') or '').upper()
                    if tipmov in ('O','C','E') and str(fornecedor).upper() != 'S':
                        errs.append("Parceiro deve ser fornecedor (FORNECEDOR='S') para TIPMOV de entrada ('O','C','E')")
                    if tipmov in ('P','V','D','1','2','3','8','N') and str(cliente).upper() != 'S':
                        errs.append("Parceiro deve ser cliente (CLIENTE='S') para TIPMOV de venda ('P','V','D','1','2','3','8','N')")
        else:
            errs.append("Parceiro (CODPARC) obrigatório")
    except Exception:
        warns.append("Não foi possível validar TGFPAR (ativo/papel)")

    # Transportadora: permitir 0/ausente; validar apenas se > 0
    try:
        codtransp = d.get('CODPARCTRANSP')
        if codtransp not in (None, '', 0):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TGFPAR WHERE CODPARC=:v AND ATIVO='S'", v=codtransp)
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append("Transportadora (CODPARCTRANSP) inativa ou inexistente")
    except Exception:
        warns.append("Não foi possível validar CODPARCTRANSP")

    # Vendedor: permitir 0 (padrão de algumas bases). Validar somente se > 0.
    try:
        codvend = d.get('CODVEND')
        if codvend not in (None, '', 0):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TGFVEN WHERE CODVEND=:v AND ATIVO='S'", v=codvend)
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append("Vendedor (CODVEND) inativo ou inexistente")
    except Exception:
        warns.append("Não foi possível validar TGFVEN")

    # Natureza ativa e analítica
    try:
        if d.get('CODNAT') is not None:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TGFNAT WHERE CODNAT=:v AND ATIVA='S' AND ANALITICA='S'", v=d['CODNAT'])
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append("Natureza (CODNAT) inativa ou não analítica")
    except Exception:
        warns.append("Não foi possível validar TGFNAT")

    # Centro de resultado ativo e analítico
    try:
        if d.get('CODCENCUS'):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TSICUS WHERE CODCENCUS=:v AND ATIVO='S' AND ANALITICO='S'", v=d['CODCENCUS'])
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append("Centro de Resultado (CODCENCUS) inativo ou não analítico")
        else:
            errs.append("Centro de Resultado (CODCENCUS) obrigatório")
    except Exception:
        warns.append("Não foi possível validar TSICUS")

    # Projeto: permitir 0/ausente; validar apenas se > 0 e exigir ativo+analítico
    try:
        codproj = d.get('CODPROJ')
        if codproj not in (None, '', 0):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TCSPRJ WHERE CODPROJ=:v AND ATIVO='S' AND ANALITICO='S'", v=codproj)
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append("Projeto (CODPROJ) inativo, não analítico ou inexistente")
    except Exception:
        warns.append("Não foi possível validar TCSPRJ")

    # TOP ativo e TIPMOV compatível (com DHALTER escolhido)
    try:
        if d.get('CODTIPOPER'):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT ATIVO, TIPMOV FROM TGFTOP WHERE CODTIPOPER=:k AND DHALTER = :d",
                    k=d['CODTIPOPER'], d=d.get('DHTIPOPER')
                )
                row = cur.fetchone()
                if not row:
                    errs.append("TOP (CODTIPOPER/DHTIPOPER) inexistente — DHTIPOPER deve casar com TGFTOP.DHALTER")
                else:
                    ativo, top_tipmov = row
                    if str(ativo).upper() != 'S':
                        errs.append("TOP inativa (TGFTOP.ATIVO<>'S')")
                    if d.get('TIPMOV') and top_tipmov and str(d['TIPMOV']).upper() != str(top_tipmov).upper():
                        errs.append("TIPMOV da nota não corresponde ao TIPMOV da TOP selecionada")
    except Exception:
        warns.append("Não foi possível validar TGFTOP (ATIVO/TIPMOV)")

    # Tipo de negociação (TPV): obrigatório para TIPMOV P/V/D; proibido (0) em T/R
    try:
        tipmov = (d.get('TIPMOV') or '').upper()
        if tipmov in ('P','V','D'):
            if not d.get('CODTIPVENDA'):
                errs.append("Tipo de negociação (CODTIPVENDA) obrigatório para TIPMOV P/V/D")
            else:
                # Se DHTIPVENDA foi preenchido no plano, validar ativo
                if d.get('DHTIPVENDA'):
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT COUNT(1) FROM TGFTPV WHERE CODTIPVENDA=:v AND DHALTER=:d AND ATIVO='S'",
                            v=d['CODTIPVENDA'], d=d['DHTIPVENDA']
                        )
                        (cnt,) = cur.fetchone()
                        if int(cnt) == 0:
                            errs.append("Tipo de negociação (TGFTPV) inativo para o DHALTER selecionado")
        if tipmov in ('T','R'):
            if d.get('CODTIPVENDA') not in (None, '', 0):
                errs.append("Para TIPMOV T/R, CODTIPVENDA deve ser 0")
    except Exception:
        warns.append("Não foi possível validar TGFTPV")

    # Possível duplicidade de NUMNOTA (aviso)
    if d.get('NUMNOTA'):
        try:
            serie = d.get('SERIENOTA') or ''
            if _exists(
                "SELECT 1 FROM TGFCAB WHERE CODEMP=:e AND NUMNOTA=:n AND NVL(SERIENOTA,'')=NVL(:s,'')",
                e=d['CODEMP'], n=d['NUMNOTA'], s=serie
            ):
                warns.append("Já existe documento com CODEMP/NUMNOTA/SERIENOTA — confirme regra de unicidade")
        except Exception:
            warns.append("Não foi possível checar duplicidade de NUMNOTA")

    # Transferência local bloqueada (UTILIZALOCAL='N')
    try:
        if (d.get('TIPMOV') or '').upper() == 'T' and d.get('CODEMP') and d.get('CODEMPNEGOC') and d['CODEMP'] == d['CODEMPNEGOC']:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT LOGICO FROM TSIPAR WHERE CHAVE='UTILIZALOCAL'")
                row = cur.fetchone()
                if row and str(row[0]).upper() == 'N':
                    errs.append("Transferência local bloqueada (TSIPAR UTILIZALOCAL='N') para TIPMOV 'T' com mesma empresa")
    except Exception:
        warns.append("Não foi possível consultar TSIPAR (UTILIZALOCAL)")

    return errs, warns


def _coerce_hour_int(hr) -> int:
    if hr in (None, ''):
        from datetime import datetime
        return int(datetime.now().strftime('%H%M%S'))
    s = str(hr).replace(':','').strip()
    if not s.isdigit():
        raise ValueError('HRMOV inválido')
    return int(s)


def plan_insert_cabecalho(d: dict) -> dict:
    """Monta um plano de INSERT na TGFCAB com binds, após validações básicas.
    Não executa nada; retorna SQL, binds, erros/avisos e detecção de trigger/sequence para NUNOTA.
    """
    # Defaults recomendados
    data = d.copy()
    data.setdefault('TIPMOV', 'E')
    if not data.get('DTMOV'):
        data['DTMOV'] = data.get('DTNEG')
    if not data.get('DTENTSAI'):
        data['DTENTSAI'] = data.get('DTNEG')
    if not data.get('HRMOV'):
        data['HRMOV'] = _coerce_hour_int(d.get('HRMOV'))
    data.setdefault('PENDENTE', 'S')
    data.setdefault('STATUSNOTA', 'A')
    if 'CODEMPNEGOC' not in data and data.get('CODEMP'):
        data['CODEMPNEGOC'] = data['CODEMP']

    # Preencher DHTIPOPER e conciliar TIPMOV com a TOP
    if data.get('CODTIPOPER') and not data.get('DHTIPOPER'):
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT MAX(DHALTER) FROM TGFTOP WHERE CODTIPOPER=:k",
                    k=data['CODTIPOPER']
                )
                (dh,) = cur.fetchone()
                if dh:
                    data['DHTIPOPER'] = dh
                # Tentar obter TIPMOV da TOP mais recente
                cur.execute(
                    "SELECT TIPMOV FROM (SELECT TIPMOV, DHALTER FROM TGFTOP WHERE CODTIPOPER=:k ORDER BY DHALTER DESC) WHERE ROWNUM=1",
                    k=data['CODTIPOPER']
                )
                row = cur.fetchone()
                if row and row[0]:
                    top_tipmov = row[0]
                    if data.get('TIPMOV') and data['TIPMOV'] != top_tipmov:
                        # harmonizar conforme trigger exige igualdade
                        data['TIPMOV'] = top_tipmov
        except Exception:
            pass

    # Se TIPMOV de venda/pedido/devolução, exigir/ajustar TPV (CODTIPVENDA/DHTIPVENDA)
    try:
        tipmov = (data.get('TIPMOV') or '').upper()
        if tipmov in ('P','V','D') and data.get('CODTIPVENDA'):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT MAX(DHALTER) FROM TGFTPV WHERE CODTIPVENDA=:v",
                    v=data['CODTIPVENDA']
                )
                row = cur.fetchone()
                if row and row[0]:
                    data['DHTIPVENDA'] = row[0]
    except Exception:
        pass

    errs, warns = validar_cabecalho_minimo(data)

    # Inspeções de metadados
    pk_cols = get_table_pk('TGFCAB')
    fks = get_table_fks('TGFCAB')
    notnulls = get_not_null_cols('TGFCAB')
    triggers = get_triggers('TGFCAB')
    trig_nextval = find_triggers_using_nextval('TGFCAB', 'NUNOTA')
    seq_guess = list_sequences_like('%NUNOTA%')
    # Extra introspection (cross-schema, if permitted) and identity check
    all_trig = []
    all_seq = []
    identity = None
    try:
        with get_connection() as conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT trigger_name FROM all_triggers "
                    "WHERE table_name=:t AND UPPER(trigger_body) LIKE :k1 AND UPPER(trigger_body) LIKE '%NEXTVAL%'",
                    t='TGFCAB', k1='%NUNOTA%')
                all_trig = [r[0] for r in cur.fetchall()]
            except Exception:
                all_trig = []
            try:
                cur.execute(
                    "SELECT sequence_owner, sequence_name FROM all_sequences WHERE sequence_name LIKE :p",
                    p='%NUNOTA%')
                all_seq = [f"{r[0]}.{r[1]}" for r in cur.fetchall()]
            except Exception:
                all_seq = []
            try:
                cur.execute(
                    "SELECT identity_column FROM user_tab_cols WHERE table_name='TGFCAB' AND column_name='NUNOTA'"
                )
                row = cur.fetchone()
                identity = row[0] if row else None
            except Exception:
                identity = None
    except Exception:
        pass

    uses_trigger_nunota = len(trig_nextval) > 0
    notnull_cols = {c for c, _t, _d in notnulls}
    requires_nunota = ('NUNOTA' in notnull_cols) and (not identity) and (not uses_trigger_nunota)

    # Ajuste: se NUMNOTA é NOT NULL e não informado, preencher com 0 (placeholder)
    if 'NUMNOTA' in notnull_cols and (data.get('NUMNOTA') in (None, '')):
        data['NUMNOTA'] = 0

    # Checar existência da coluna DTALTER para sempre popular com SYSDATE no INSERT
    has_dtalter = False
    try:
        with get_connection() as _c:
            has_dtalter = 'DTALTER' in _get_table_columns(_c, 'TGFCAB')
    except Exception:
        has_dtalter = False

    # Montar SQL minimalista com RETURNING NUNOTA
    cols = [
        'CODEMP','CODEMPNEGOC','CODPARC','CODPARCTRANSP','CODVEND',
        'CODTIPOPER','DHTIPOPER','TIPMOV',
        'CODNAT','CODCENCUS','CODPROJ',
        'CODTIPVENDA','DHTIPVENDA',
        'DTNEG','DTMOV','DTENTSAI','HRMOV',
        'NUMNOTA','OBSERVACAO','PENDENTE','STATUSNOTA'
    ]
    if has_dtalter:
        cols.append('DTALTER')
    if requires_nunota:
        cols = ['NUNOTA'] + cols
    # Remover campos não informados (opcionais)
    for opt in ['CODCENCUS','CODPROJ','CODPARCTRANSP','CODVEND','CODTIPVENDA','DHTIPVENDA','NUMNOTA','OBSERVACAO','DHTIPOPER']:
        val = data.get(opt)
        if val in (None, ''):
            try:
                cols.remove(opt)
            except ValueError:
                pass

    value_exprs = []
    binds = {}
    for c in cols:
        if c == 'DTALTER' and has_dtalter:
            value_exprs.append('SYSDATE')
            continue
        if c in ('DTNEG','DTMOV','DTENTSAI'):
            value_exprs.append(f"TO_DATE(:{c}, 'DD/MM/YYYY')")
            binds[c] = data[c]
        elif c == 'DHTIPOPER':
            value_exprs.append(f":{c}")
            binds[c] = data[c]
        else:
            value_exprs.append(f":{c}")
            binds[c] = data.get(c)

    col_list = ', '.join(cols)
    val_list = ', '.join(value_exprs)
    sql = f"INSERT INTO TGFCAB ({col_list}) VALUES ({val_list}) RETURNING NUNOTA INTO :out_nunota"

    plan = {
        'ok': len(errs)==0,
        'errors': errs,
        'warnings': warns,
        'sql': sql,
        'binds': binds,
        'requires_nunota': requires_nunota,
        'uses_trigger_for_nunota': uses_trigger_nunota,
        'sequence_candidates': seq_guess,
        'all_triggers_using_nextval': all_trig,
        'all_sequences_candidates': all_seq,
        'identity_column_flag': identity,
        'pk': pk_cols,
        'fks': [{'col': c, 'ref_table': rt, 'ref_col': rc} for c, rt, rc in fks],
        'not_nulls': [{'col': c, 'type': t, 'default': dflt} for c, t, dflt in notnulls],
        'triggers': [{'name': n, 'status': s} for n, s in triggers],
        'data': data,
    }
    # Se definimos NUMNOTA automaticamente por ser NOT NULL, registrar aviso
    try:
        if 'NUMNOTA' in notnull_cols and int(d.get('NUMNOTA') or 0) == 0 and int(data.get('NUMNOTA') or 0) == 0:
            plan.setdefault('warnings', []).append('NUMNOTA é NOT NULL nesta base; definido como 0 por padrão. Informe um número de documento se necessário.')
    except Exception:
        pass

    return plan


def insert_cabecalho(d: dict, dry_run: bool = True) -> dict:
    """Executa (ou simula) o INSERT do cabeçalho TGFCAB. Respeita feature-flag de escrita.
    Retorna dict com plano e, se executado, o NUNOTA gerado.
    """
    plan = plan_insert_cabecalho(d)
    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            plan.setdefault('warnings', []).append('Escrita desabilitada por política — execução em modo simulado')
        return plan

    if not plan['ok']:
        return plan

    with get_connection() as conn:
        try:
            cur = conn.cursor()
            out_n = cur.var(cx_Oracle.NUMBER)
            binds = plan['binds'].copy()
            # Preencher NUNOTA se necessário e ainda não definido
            if plan.get('requires_nunota'):
                try:
                    if not binds.get('NUNOTA'):
                        binds['NUNOTA'] = _obter_proximo_nunota(conn)
                        plan['nunota_assigned_before'] = binds['NUNOTA']
                except Exception as gen_err:
                    plan.setdefault('warnings', []).append(f'Falha ao gerar NUNOTA automaticamente: {gen_err}')
            binds['out_nunota'] = out_n
            cur.execute(plan['sql'], binds)
            raw = out_n.getvalue()
            if isinstance(raw, list):
                raw = raw[0] if raw else None
            nunota_val = int(raw) if raw is not None else None
            conn.commit()
            plan['nunota'] = nunota_val
            plan['executed'] = True
            return plan
        except cx_Oracle.DatabaseError as e:
            # Tratamento de violação de PK_TGFCAB: tentar regenerar NUNOTA e reexecutar uma vez
            try:
                err, = e.args
                code = getattr(err, 'code', None)
                msg = getattr(err, 'message', str(e))
            except Exception:
                code = None
                msg = str(e)
            if plan.get('requires_nunota') and code in (1, '1') and ('PK_TGFCAB' in (msg or '')):
                try:
                    cur = conn.cursor()
                    out_n = cur.var(cx_Oracle.NUMBER)
                    binds = plan['binds'].copy()
                    binds['NUNOTA'] = _obter_proximo_nunota(conn)
                    plan['nunota_retry_assigned'] = binds['NUNOTA']
                    binds['out_nunota'] = out_n
                    cur.execute(plan['sql'], binds)
                    raw2 = out_n.getvalue()
                    if isinstance(raw2, list):
                        raw2 = raw2[0] if raw2 else None
                    nunota_val = int(raw2) if raw2 is not None else None
                    conn.commit()
                    plan['nunota'] = nunota_val
                    plan['executed'] = True
                    plan.setdefault('warnings', []).append('NUNOTA colidiu com PK; gerado novo NUNOTA e reexecutado com sucesso.')
                    return plan
                except Exception as e2:
                    try:
                        err2, = getattr(e2, 'args', [None])
                        plan['db_error'] = {
                            'code': getattr(err2, 'code', None),
                            'message': getattr(err2, 'message', str(e2)),
                        }
                    except Exception:
                        plan['db_error'] = {'message': str(e2)}
                    plan['executed'] = False
                    return plan
            # Sem possibilidade de retry, reportar erro
            plan['db_error'] = {'code': code, 'message': msg}
            plan['executed'] = False
            return plan

def _obter_proximo_nunota(conn) -> int:
    """Gera próximo NUNOTA evitando colisão com PK.
    Estratégia: usar USER_SEQUENCES/ALL_SEQUENCES candidatas e avançar NEXTVAL até superar MAX(NUNOTA);
    fallback para MAX(NUNOTA)+1 se nenhuma sequence apropriada.
    """
    cur = conn.cursor()
    # MAX atual
    cur.execute("SELECT NVL(MAX(NUNOTA),0) FROM TGFCAB")
    (mx,) = cur.fetchone()
    mx = int(mx or 0)

    # Tentar sequences do usuário primeiro
    seqs: list[tuple[str, str]] = []
    try:
        cur.execute("SELECT sequence_name FROM user_sequences WHERE sequence_name LIKE :p OR sequence_name LIKE :p2 ORDER BY sequence_name", p='%NUNOTA%', p2='%TGFCAB%')
        seqs = [(None, r[0]) for r in cur.fetchall()]
    except Exception:
        seqs = []
    if not seqs:
        try:
            cur.execute("SELECT sequence_owner, sequence_name FROM all_sequences WHERE sequence_name LIKE :p OR sequence_name LIKE :p2 ORDER BY sequence_owner, sequence_name",
                        p='%NUNOTA%', p2='%TGFCAB%')
            seqs = [(r[0], r[1]) for r in cur.fetchall()]
        except Exception:
            seqs = []

    def _nextval(owner: str|None, name: str) -> int:
        if owner:
            cur.execute(f"SELECT {owner}.{name}.NEXTVAL FROM DUAL")
        else:
            cur.execute(f"SELECT {name}.NEXTVAL FROM DUAL")
        (v,) = cur.fetchone()
        return int(v)

    for owner, name in seqs:
        try:
            val = _nextval(owner, name)
            # Avança até ficar acima do MAX atual (com limite de iterações)
            steps = 0
            while val <= mx and steps < 100:
                val = _nextval(owner, name)
                steps += 1
            if val > mx:
                return val
        except Exception:
            continue

    # Fallback seguro: MAX+1
    return mx + 1


def plan_update_cabecalho(d: dict) -> dict:
    """Planeja UPDATE no cabeçalho TGFCAB. Revalida campos-chave e monta SQL com binds.
    Campos aceitos para atualização: NUMNOTA, DTNEG, DTMOV, DTENTSAI, HRMOV, CODPARC, CODTIPOPER, DHTIPOPER, CODNAT, CODCENCUS, OBSERVACAO, STATUSNOTA.
    Requer: NUNOTA.
    """
    data = d.copy()
    errs: list[str] = []
    warns: list[str] = []

    try:
        nunota = int(data.get('NUNOTA'))
    except Exception:
        nunota = None
    if not nunota:
        errs.append('NUNOTA obrigatório para atualização')

    # Carregar cabeçalho atual para defaults/validação
    current = None
    if nunota:
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT CODEMP, CODPARC, CODTIPOPER, CODNAT, CODCENCUS, DTNEG, DTMOV, DTENTSAI, HRMOV, NUMNOTA FROM TGFCAB WHERE NUNOTA=:n", n=nunota)
                row = cur.fetchone()
                if row:
                    current = {
                        'CODEMP': row[0], 'CODPARC': row[1], 'CODTIPOPER': row[2], 'CODNAT': row[3], 'CODCENCUS': row[4],
                        'DTNEG': row[5], 'DTMOV': row[6], 'DTENTSAI': row[7], 'HRMOV': row[8], 'NUMNOTA': row[9],
                    }
                else:
                    errs.append('Cabeçalho (NUNOTA) não encontrado')
        except Exception:
            warns.append('Falha ao carregar cabeçalho atual para validação')

    # Preparar payload completo para validação
    if current:
        payload = current.copy()
        # Coerções de entrada (datas no formato dd/mm/yyyy se vierem como yyyy-mm-dd)
        def _to_br(val):
            if val in (None, '', 'None', 'null'):
                return None
            s = str(val)
            if len(s) == 10 and s[4] == '-' and s[7] == '-':
                return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
            return s
        # Aplicar overrides vindos no dicionário
        if data.get('NUMNOTA') is not None:
            payload['NUMNOTA'] = data.get('NUMNOTA')
        if data.get('DTNEG'):
            payload['DTNEG'] = _to_br(data.get('DTNEG'))
        if data.get('DTMOV'):
            payload['DTMOV'] = _to_br(data.get('DTMOV'))
        if data.get('DTENTSAI'):
            payload['DTENTSAI'] = _to_br(data.get('DTENTSAI'))
        if data.get('HRMOV'):
            payload['HRMOV'] = data.get('HRMOV')
        if data.get('CODPARC') is not None:
            payload['CODPARC'] = data.get('CODPARC')
        if data.get('CODTIPOPER') is not None:
            payload['CODTIPOPER'] = data.get('CODTIPOPER')
        if data.get('CODNAT') is not None:
            payload['CODNAT'] = data.get('CODNAT')
        if data.get('CODCENCUS') is not None:
            payload['CODCENCUS'] = data.get('CODCENCUS')
        if data.get('OBSERVACAO') is not None:
            payload['OBSERVACAO'] = data.get('OBSERVACAO')

        # Ajustar TIPMOV/DHTIPOPER conforme TOP
        try:
            if payload.get('CODTIPOPER'):
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT MAX(DHALTER) FROM TGFTOP WHERE CODTIPOPER=:k", k=payload['CODTIPOPER'])
                    (dhmax,) = cur.fetchone()
                    if dhmax:
                        data['DHTIPOPER'] = dhmax
                        payload['DHTIPOPER'] = dhmax
                    cur.execute(
                        "SELECT TIPMOV FROM (SELECT TIPMOV, DHALTER FROM TGFTOP WHERE CODTIPOPER=:k ORDER BY DHALTER DESC) WHERE ROWNUM=1",
                        k=payload['CODTIPOPER']
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        payload['TIPMOV'] = row[0]
        except Exception:
            pass

        # Validar conjunto
        v_errs, v_warns = validar_cabecalho_minimo(payload)
        errs.extend(v_errs)
        warns.extend(v_warns)

    # Construir SQL de UPDATE apenas com campos informados
    sets = []
    binds = {'NUNOTA': nunota}
    if data.get('NUMNOTA') is not None:
        sets.append('NUMNOTA=:NUMNOTA')
        binds['NUMNOTA'] = data.get('NUMNOTA')
    if data.get('CODEMP') is not None:
        sets.append('CODEMP=:CODEMP')
        binds['CODEMP'] = data.get('CODEMP')
    for col in ('DTNEG','DTMOV','DTENTSAI'):
        if data.get(col):
            sets.append(f"{col}=TO_DATE(:{col}, 'YYYY-MM-DD')")
            binds[col] = data.get(col)
    if data.get('HRMOV'):
        sets.append('HRMOV=:HRMOV')
        binds['HRMOV'] = data.get('HRMOV')
    if data.get('CODPARC') is not None:
        sets.append('CODPARC=:CODPARC')
        binds['CODPARC'] = data.get('CODPARC')
    if data.get('CODTIPOPER') is not None:
        sets.append('CODTIPOPER=:CODTIPOPER')
        binds['CODTIPOPER'] = data.get('CODTIPOPER')
        if data.get('DHTIPOPER') is not None:
            sets.append('DHTIPOPER=:DHTIPOPER')
            binds['DHTIPOPER'] = data.get('DHTIPOPER')
    if data.get('CODNAT') is not None:
        sets.append('CODNAT=:CODNAT')
        binds['CODNAT'] = data.get('CODNAT')
    if data.get('CODCENCUS') is not None:
        sets.append('CODCENCUS=:CODCENCUS')
        binds['CODCENCUS'] = data.get('CODCENCUS')
    if data.get('OBSERVACAO') is not None:
        sets.append('OBSERVACAO=:OBSERVACAO')
        binds['OBSERVACAO'] = data.get('OBSERVACAO')

    # STATUSNOTA ('A' Atendimento, 'L' Liberado)
    if data.get('STATUSNOTA') is not None:
        try:
            sn = str(data.get('STATUSNOTA') or '').strip().upper()
        except Exception:
            sn = ''
        if sn not in ('A', 'L'):
            errs.append("STATUSNOTA inválido (use 'A' ou 'L')")
        else:
            sets.append('STATUSNOTA=:STATUSNOTA')
            binds['STATUSNOTA'] = sn
    # PENDENTE ('S' ou 'N')
    if data.get('PENDENTE') is not None:
        try:
            pd = str(data.get('PENDENTE') or '').strip().upper()
        except Exception:
            pd = ''
        if pd not in ('S','N'):
            errs.append("PENDENTE inválido (use 'S' ou 'N')")
        else:
            sets.append('PENDENTE=:PENDENTE')
            binds['PENDENTE'] = pd

    if not sets and len(errs) == 0:
        warns.append('Nenhuma alteração informada')
    # Se houver alterações, e a coluna DTALTER existir, acrescente DTALTER=SYSDATE
    if sets:
        try:
            with get_connection() as _c:
                if 'DTALTER' in _get_table_columns(_c, 'TGFCAB'):
                    sets.append('DTALTER=SYSDATE')
        except Exception:
            pass

    sql = f"UPDATE TGFCAB SET {', '.join(sets)} WHERE NUNOTA=:NUNOTA" if sets else None
    return {
        'ok': len(errs) == 0 and bool(sets),
        'errors': errs,
        'warnings': warns,
        'sql': sql,
        'binds': binds,
        'data': data,
    }


def update_cabecalho(d: dict, dry_run: bool = True) -> dict:
    plan = plan_update_cabecalho(d)
    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            plan.setdefault('warnings', []).append('Escrita desabilitada por política — execução em modo simulado')
        return plan
    if not plan['ok']:
        return plan
    with get_connection() as conn:
        try:
            cur = conn.cursor()
            cur.execute(plan['sql'], plan['binds'])
            conn.commit()
            plan['executed'] = True
            return plan
        except cx_Oracle.DatabaseError as e:
            try:
                err, = e.args
                code = getattr(err, 'code', None)
                msg = getattr(err, 'message', str(e))
            except Exception:
                code = None
                msg = str(e)
            plan['db_error'] = {'code': code, 'message': msg}
            plan['executed'] = False
            return plan

def get_trigger_body(trigger_name: str) -> str | None:
    """Obtém corpo do trigger (se possível) com ALL_TRIGGERS; fallback para ALL_SOURCE concatenando linhas."""
    t = trigger_name.upper()
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT trigger_body FROM all_triggers WHERE trigger_name=:n", n=t)
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        try:
            cur.execute(
                "SELECT text FROM all_source WHERE name=:n AND type='TRIGGER' ORDER BY line",
                n=t
            )
            parts = [r[0] for r in cur.fetchall()]
            return ''.join(parts) if parts else None
        except Exception:
            return None

def get_trigger_ddl(owner: str | None, trigger_name: str) -> str | None:
    name = (trigger_name or '').upper()
    with get_connection() as conn:
        cur = conn.cursor()
        # Try ALL_TRIGGERS columns (no full DDL, but includes header/body)
        try:
            if owner:
                cur.execute(
                    "SELECT description, trigger_body FROM all_triggers WHERE owner=:o AND trigger_name=:n",
                    o=owner.upper(), n=name
                )
            else:
                cur.execute(
                    "SELECT description, trigger_body FROM all_triggers WHERE trigger_name=:n",
                    n=name
                )
            row = cur.fetchone()
            if row:
                descr, body = row
                ddl = f"-- {owner+'.' if owner else ''}{name}\nCREATE OR REPLACE TRIGGER {owner+'.' if owner else ''}{name}\n{descr}\n{body}\n/\n"
                return ddl
        except Exception:
            pass
        # Fallback: stitch from ALL_SOURCE
        try:
            if owner:
                cur.execute(
                    "SELECT text FROM all_source WHERE owner=:o AND name=:n AND type='TRIGGER' ORDER BY line",
                    o=owner.upper(), n=name
                )
            else:
                cur.execute(
                    "SELECT text FROM all_source WHERE name=:n AND type='TRIGGER' ORDER BY line",
                    n=name
                )
            parts = [r[0] for r in cur.fetchall()]
            return ''.join(parts) + "\n/\n" if parts else None
        except Exception:
            return None


def proximo_sequencial_controle(data) -> str:
    """Retorna próximo sequencial HEX (5 dígitos) para o prefixo AAMMDD do lote (CODAGREGACAO).
    Busca TGFITE por prefixo de CODAGREGACAO, independente do DTNEG do cabeçalho.
    """
    from datetime import datetime, date as _date
    if isinstance(data, str):
        data = datetime.strptime(data, '%Y-%m-%d').date()
    if not isinstance(data, _date):
        raise ValueError('data inválida para gerar controle')
    prefix = data.strftime('%y%m%d')
    # Buscar todos controles com esse prefixo e extrair sufixo como HEX
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT CODAGREGACAO FROM TGFITE WHERE CODAGREGACAO LIKE :pfx AND CODAGREGACAO IS NOT NULL", pfx=f"{prefix}%")
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
    nxt = max_incr + 1
    if nxt > int('FFFFF', 16):
        raise ValueError('Limite diário de FFFFF (HEX) excedido')
    return format(nxt, 'X').upper().zfill(5)


def gerar_lote(data, codparc=None, codprod=None):
    """Gera lote no padrão AAMMDD + 'P' + codparc + 'P' + codprod + 'S' + sequencia(2dig).
    Sequencia é incremental por data+codparc+codprod e sem padding à esquerda.
    Ex: 250924P536P358S01 or 250924P6P25S14
    """
    from datetime import datetime, date as _date
    if isinstance(data, str):
        data = datetime.strptime(data, '%Y-%m-%d').date()
    if not isinstance(data, _date):
        raise ValueError('data inválida para gerar lote')
    prefix = data.strftime('%y%m%d')
    # Build key prefix for searching existing CODAGREGACAO values
    # Pattern: AAMMDDP<codparc>P<codprod>S
    cp = str(codparc) if codparc is not None else ''
    cpp = str(codprod) if codprod is not None else ''
    key_prefix = f"{prefix}P{cp}P{cpp}S"
    # Find existing ones and extract trailing sequence number
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT CODAGREGACAO FROM TGFITE WHERE CODAGREGACAO LIKE :pfx AND CODAGREGACAO IS NOT NULL", pfx=f"{key_prefix}%")
        rows = cur.fetchall()
    max_seq = 0
    preflen = len(key_prefix)
    for (val,) in rows:
        s = (val or '').strip()
        if not s.startswith(key_prefix):
            continue
        suf = s[preflen:]
        # try to parse numeric suffix
        try:
            seqv = int(suf)
        except Exception:
            continue
        if seqv > max_seq:
            max_seq = seqv
    next_seq = max_seq + 1
    return f"{prefix}P{cp}P{cpp}S{next_seq:02d}"


def obter_proxima_sequencia(nunota: int) -> int:
    """Retorna próxima SEQUENCIA para um NUNOTA em TGFITE (max + 1). Se nenhum item, retorna 1."""
    sql = "SELECT NVL(MAX(SEQUENCIA),0) + 1 FROM TGFITE WHERE NUNOTA = :nunota"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, nunota=nunota)
        (prox,) = cur.fetchone()
        return int(prox)


def montar_item_compra(nunota: int, codparc: int, codprod: int, quantidade: float, vlrunit: float, data, sufixo: str|None=None):
    """Monta estrutura de item bruto (entrada) com lote (CODAGREGACAO) gerado.
    Não insere no banco, apenas retorna dict pronto para bind.
    """
    from datetime import date as _date, datetime
    if not isinstance(data, _date):
        data = datetime.strptime(str(data), '%Y-%m-%d').date()
    codag = gerar_lote(data, codparc, codprod)
    sequencia = obter_proxima_sequencia(nunota)
    vlrtot = round(quantidade * vlrunit, 2)
    return {
        'NUNOTA': nunota,
        'SEQUENCIA': sequencia,
        'CODPROD': codprod,
        'QTDNEG': quantidade,
        'VLRUNIT': vlrunit,
        'VLRTOT': vlrtot,
        'CODPARC': codparc,
        'CODAGREGACAO': codag,
        'CODVOL': 'UN',
        'OBSERVACAO': f'Entrada automatizada lote {codag}'
    }


def build_insert_item_sql():
    """Retorna SQL parametrizado para inserir item em TGFITE (campos mínimos)."""
    return (
        "INSERT INTO TGFITE (NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, PESO, VLRUNIT, VLRTOT, CODVOL, CODLOCALORIG, CODAGREGACAO, OBSERVACAO, GERAPRODUCAO) "
        "VALUES (:NUNOTA, :SEQUENCIA, :CODEMP, :CODPROD, :QTDNEG, :PESO, :VLRUNIT, :VLRTOT, :CODVOL, :CODLOCALORIG, :CODAGREGACAO, :OBSERVACAO, :GERAPRODUCAO)"
    )


def plan_insert_item(d: dict) -> dict:
    """Planeja o INSERT em TGFITE com validações mínimas e binds calculados.
    Campos esperados: NUNOTA, CODPROD, QTDNEG, VLRUNIT, CODAGREGACAO(opcional), CODVOL(opcional), OBSERVACAO(opcional).
    """
    data = d.copy()
    errs: list[str] = []
    warns: list[str] = []

    # Coerções/Defaults
    try:
        data['NUNOTA'] = int(data.get('NUNOTA'))
    except Exception:
        errs.append('NUNOTA inválido ou ausente')
    try:
        data['CODPROD'] = int(data.get('CODPROD'))
    except Exception:
        errs.append('CODPROD inválido ou ausente')
    try:
        data['QTDNEG'] = float(data.get('QTDNEG'))
    except Exception:
        errs.append('QTDNEG inválida ou ausente')
    try:
        vu = float(data.get('VLRUNIT'))
        if vu < 0:
            warns.append('VLRUNIT negativo — verifique política')
        data['VLRUNIT'] = vu
    except Exception:
        errs.append('VLRUNIT inválido ou ausente')
    data['CODVOL'] = (data.get('CODVOL') or 'UN')
    # CODLOCALORIG: padrão 101 conforme solicitação
    try:
        data['CODLOCALORIG'] = int(data.get('CODLOCALORIG') or data.get('CODLOCAL') or 101)
    except Exception:
        data['CODLOCALORIG'] = 101
    # data['CONTROLE'] removed; use CODAGREGACAO instead
    data['CODAGREGACAO'] = (data.get('CODAGREGACAO') or None)
    obs = data.get('OBSERVACAO')
    data['OBSERVACAO'] = obs if (obs not in (None, '')) else None

    # GERAPRODUCAO (classificação): aceitar 'S'/'N' (case-insensitive); default None para deixar trigger definir 'S'
    try:
        gp = d.get('GERAPRODUCAO') if 'GERAPRODUCAO' in d else d.get('geraproducao')
    except Exception:
        gp = None
    if gp is not None:
        s = str(gp).strip().upper()
        if s in ('S','N'):
            data['GERAPRODUCAO'] = s
        else:
            data['GERAPRODUCAO'] = None
    else:
        data['GERAPRODUCAO'] = None

    # Regras simples
    if 'QTDNEG' in data and (isinstance(data['QTDNEG'], (int, float)) and data['QTDNEG'] <= 0):
        errs.append('QTDNEG deve ser > 0')

    # Verificar existência de NUNOTA e obter dados do cabeçalho (DTNEG, CODPARC, CODEMP, CODTIPOPER/DHTIPOPER)
    dtneg_date = None
    codparc = None
    codemp = None
    cab_codtop = None
    cab_dhtop = None
    if not errs:
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT DTNEG, CODPARC, CODEMP, CODTIPOPER, DHTIPOPER FROM TGFCAB WHERE NUNOTA=:n", n=data['NUNOTA'])
                row = cur.fetchone()
                if not row:
                    errs.append('NUNOTA inexistente em TGFCAB')
                else:
                    dtneg_date, codparc, codemp, cab_codtop, cab_dhtop = row[0], row[1], row[2], row[3], row[4]
                    # Validar que TOP/DHALTER existem
                    if cab_codtop is None or cab_dhtop is None:
                        errs.append('Cabeçalho sem DHTIPOPER vinculado à TOP — não atende trigger')
                    else:
                        try:
                            cur.execute("SELECT 1 FROM TGFTOP WHERE CODTIPOPER=:k AND DHALTER=:d", k=cab_codtop, d=cab_dhtop)
                            if cur.fetchone() is None:
                                errs.append('TOP/DHALTER inválidos para a nota (TGFTOP)')
                        except Exception:
                            pass
                    # Validar empresa em TGFEMP (trigger usa TGFEMP)
                    if codemp is not None:
                        try:
                            cur.execute("SELECT 1 FROM TGFEMP WHERE CODEMP=:e", e=codemp)
                            if cur.fetchone() is None:
                                errs.append(f'Empresa (CODEMP={codemp}) não encontrada em TGFEMP — trigger pode falhar')
                        except Exception:
                            pass
        except Exception:
            warns.append('Falha ao validar NUNOTA em TGFCAB')
    try:
        data['CODVOL'] = str(data['CODVOL']).strip().upper()
    except Exception:
        pass
    # Validar CODVOL em TGFVOL
    if not errs and data.get('CODVOL'):
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM TGFVOL WHERE UPPER(CODVOL)=:v", v=str(data['CODVOL']).upper())
                if cur.fetchone() is None:
                    errs.append(f"Unidade (CODVOL='{data['CODVOL']}') inexistente em TGFVOL")
        except Exception:
            warns.append('Falha ao validar TGFVOL (CODVOL)')

    # Verificar existência do produto
    if not errs:
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1) FROM TGFPRO WHERE CODPROD=:p", p=data['CODPROD'])
                (cnt,) = cur.fetchone()
                if int(cnt) == 0:
                    errs.append('Produto (CODPROD) inexistente')
        except Exception:
            warns.append('Falha ao validar TGFPRO')

    # Conversão de quantidade para unidade base (se necessário)
    # Regra: ERP armazena QTDNEG na unidade base do produto (TGFPRO.CODVOL).
    # Se usuário informou QTDNEG em unidade alternativa (CODVOL != base) e existir fator (TGFVOA),
    # normalizamos QTDNEG *= fator. Mantemos CODVOL informado para referência/validação.
    try:
        if not errs and data.get('CODPROD') is not None and data.get('CODVOL'):
            base, fator = get_base_unit_and_factor(int(data['CODPROD']), str(data['CODVOL']))
            # Enforce: if unit differs from base and no factor mapping exists in TGFVOA, reject as invalid alternative unit
            if base and str(base).upper() != str(data['CODVOL']).upper() and (fator is None or float(fator) <= 0):
                errs.append(f"Unidade (CODVOL='{data['CODVOL']}') não é alternativa válida para o produto {data['CODPROD']}")
            # If alternative and factor exists, normalize to base
            if base and str(base).upper() != str(data['CODVOL']).upper() and fator and float(fator) > 0:
                try:
                    q_alt = float(data['QTDNEG'])
                    q_base = round(q_alt * float(fator), 6)
                    data['QTDNEG'] = q_base
                    warns.append(f"QTDNEG normalizada para a unidade base {base} (×{fator}).")
                except Exception:
                    pass
    except Exception:
        # Não bloquear em caso de falha de conversão; prosseguir sem normalização
        pass

    # Calcular SEQUENCIA e valores
    sequencia = None
    if not errs and data.get('NUNOTA') is not None:
        try:
            sequencia = obter_proxima_sequencia(int(data['NUNOTA']))
        except Exception:
            warns.append('Não foi possível calcular SEQUENCIA; usando 1')
            sequencia = 1
    data['SEQUENCIA'] = sequencia
    try:
        data['VLRTOT'] = round(float(data['QTDNEG']) * float(data['VLRUNIT']), 2)
    except Exception:
        data['VLRTOT'] = None

    # Política de CODAGREGACAO:
    # - Para notas de Classificação (TOP_CLASS), exigir CODAGREGACAO fornecido pelo cliente (lote imutável)
    # - Para outras TOPs, manter comportamento de sugerir automaticamente quando possível
    try:
        top_class = get_params().get('TOP_CLASS')
    except Exception:
        top_class = None
    is_class_note = False
    try:
        if cab_codtop is not None and top_class is not None and int(cab_codtop) == int(top_class):
            is_class_note = True
    except Exception:
        is_class_note = False

    if is_class_note:
        if not data.get('CODAGREGACAO'):
            errs.append('CODAGREGACAO (lote) é obrigatório para itens de Classificação (TOP 26)')
        # Política de preços: TOP 26 não trabalha com preço
        try:
            data['VLRUNIT'] = 0.0
            data['VLRTOT'] = 0.0
        except Exception:
            pass
    else:
        # Gerar CODAGREGACAO se não informado but dtneg available (não-classificação)
        if not data.get('CODAGREGACAO') and dtneg_date is not None:
            try:
                data['CODAGREGACAO'] = gerar_lote(dtneg_date, codparc, data.get('CODPROD'))
                warns.append(f"CODAGREGACAO não informado; sugerido automaticamente: {data['CODAGREGACAO']}")
            except Exception:
                pass

    # Montar SQL/binds mínimos — incluir DTALTER=SYSDATE se a coluna existir em TGFITE
    has_dtalter_tgfite = False
    try:
        with get_connection() as _c:
            has_dtalter_tgfite = 'DTALTER' in _get_table_columns(_c, 'TGFITE')
    except Exception:
        has_dtalter_tgfite = False

    cols = [
        'NUNOTA','SEQUENCIA','CODEMP','CODPROD','QTDNEG','PESO','VLRUNIT','VLRTOT','CODVOL','CODLOCALORIG','CODAGREGACAO','OBSERVACAO','GERAPRODUCAO'
    ]
    if has_dtalter_tgfite:
        cols.append('DTALTER')
    val_exprs = []
    for c in cols:
        if c == 'DTALTER':
            val_exprs.append('SYSDATE')
        else:
            val_exprs.append(f":{c}")
    sql = f"INSERT INTO TGFITE ({', '.join(cols)}) VALUES ({', '.join(val_exprs)})"
    binds = {
        'NUNOTA': data.get('NUNOTA'),
        'SEQUENCIA': data.get('SEQUENCIA'),
        'CODEMP': codemp,
        'CODPROD': data.get('CODPROD'),
        'QTDNEG': data.get('QTDNEG'),
        'PESO': data.get('PESO'),
        'VLRUNIT': 0.0 if is_class_note else data.get('VLRUNIT'),
        'VLRTOT': 0.0 if is_class_note else data.get('VLRTOT'),
        'CODVOL': data.get('CODVOL'),
        'CODLOCALORIG': data.get('CODLOCALORIG'),
        'CODAGREGACAO': data.get('CODAGREGACAO'),
        'OBSERVACAO': data.get('OBSERVACAO'),
        'GERAPRODUCAO': data.get('GERAPRODUCAO'),
    }

    return {
        'ok': len(errs) == 0,
        'errors': errs,
        'warnings': warns,
        'sql': sql,
        'binds': binds,
        'data': data,
    }

# ===== Standardization helpers (must be defined before insert/update item usage) =====
def _get_table_columns(conn, table: str) -> set[str]:
    try:
        t = str(table).upper()
        cached = _COLS_CACHE.get(t)
        if cached is not None:
            return cached
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM user_tab_cols WHERE table_name=:t",
            t=t
        )
        cols = {r[0].upper() for r in cur.fetchall()}
        _COLS_CACHE[t] = cols
        return cols
    except Exception:
        return set()


def standardize_item_fields(nunota: int, sequencia: int, conn=None) -> dict:
    """Standardize post-write columns on TGFITE.
    Applies the following defaults when the respective columns exist:
      - NUTAB=77
      - ALIQICMS=0, ALIQIPI=0, CODTRIB=0, M3=0, SOLCOMPRA='N', TERCEIROS='N',
        ALTURA=0, LARGURA=0, ESPESSURA=0, PRECOBASE=0, VLRACRESCDESC=0,
        VLRRETENCAO=0, CSTIPI=-1, QTDWMS=0, BASESTUFDEST=0, VLRICMSUFDEST=0,
        BASESTANT=0, STATUSLOSTE='N', QTDVOL=1, VLRSTEXTRANOTA=0, VLRUNITMOE=0,
        VLRDESCMOE=0, VLRTOTMOE=0, ALIQSTEXTRANOTA=0, BASESTEXTRANOTA=0,
        VLRREPREDSEMDESC=0, CODSIT08EFD='N', INDREPDES=1
    Always updates DTALTER=SYSDATE if the column exists.
    """
    res = {'ok': False, 'updated': 0, 'sql': None}
    if nunota in (None, '') or sequencia in (None, ''):
        res['error'] = 'Parâmetros inválidos'
        return res
    owns_conn = False
    if conn is None:
        conn = get_connection().__enter__()
        owns_conn = True
    try:
        cur = conn.cursor()
        cols = _get_table_columns(conn, 'TGFITE')
        # Build SETs with requested defaults when columns exist
        wanted_defaults = {
            'NUTAB': 77,
            'ALIQICMS': 0,
            'ALIQIPI': 0,
            'CODTRIB': 0,
            'M3': 0,
            'SOLCOMPRA': 'N',
            'TERCEIROS': 'N',
            'ALTURA': 0,
            'LARGURA': 0,
            'ESPESSURA': 0,
            'VLRACRESCDESC': 0,
            'VLRRETENCAO': 0,
            'CSTIPI': -1,
            'QTDWMS': 0,
            'BASESTUFDEST': 0,
            'VLRICMSUFDEST': 0,
            'BASESTANT': 0,
            'STATUSLOSTE': 'N',
            'STATUSLOTE': 'N',
            'QTDVOL': 1,
            'VLRSTEXTRANOTA': 0,
            'VLRUNITMOE': 0,
            'VLRDESCMOE': 0,
            'VLRTOTMOE': 0,
            'ALIQSTEXTRANOTA': 0,
            'BASESTEXTRANOTA': 0,
            'VLRREPREDSEMDESC': 0,
            'CODSIT08EFD': 'N',
            'INDREPDES': 1,
            'ATUALESTTERC': 'N',
            'CUSTO': 0,
        }
        apply_items = [(k, v) for k, v in wanted_defaults.items() if k in cols]
        # Special handling: do NOT overwrite PRECOBASE if it's already set. Only default to 0 when NULL.
        try:
            if 'PRECOBASE' in cols:
                cur.execute("SELECT PRECOBASE FROM TGFITE WHERE NUNOTA=:N AND SEQUENCIA=:S", N=int(nunota), S=int(sequencia))
                row_pb = cur.fetchone()
                current_pb = row_pb[0] if row_pb else None
                if current_pb in (None, ''):
                    apply_items.append(('PRECOBASE', 0))
                # else: keep existing PRECOBASE (user-edited) — do not add to defaults
        except Exception:
            # On any error reading current value, be conservative and do not touch PRECOBASE
            pass
        set_parts = []
        binds = {}
        if apply_items:
            set_parts.extend([f"{k} = :{k}" for k, _ in apply_items])
            binds.update({k: v for k, v in apply_items})
        if 'DTALTER' in cols:
            set_parts.append('DTALTER = SYSDATE')
        if not set_parts:
            res['ok'] = True
            return res
        sql = f"UPDATE TGFITE SET {', '.join(set_parts)} WHERE NUNOTA=:N AND SEQUENCIA=:S"
        binds['N'] = int(nunota)
        binds['S'] = int(sequencia)
        cur.execute(sql, binds)
        res['updated'] = int(cur.rowcount or 0)
        conn.commit()
        res['sql'] = sql
        res['binds'] = binds
        res['ok'] = True
        return res
    finally:
        if owns_conn:
            try:
                conn.close()
            except Exception:
                pass




def insert_item(d: dict, dry_run: bool = True) -> dict:
    """Executa (ou simula) o INSERT do item em TGFITE.
    Retorna dict com plano, e se executado, confirma a sequência gravada.
    """
    plan = plan_insert_item(d)
    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            plan.setdefault('warnings', []).append('Escrita desabilitada por política — execução em modo simulado')
        return plan

    if not plan['ok']:
        return plan

    with get_connection() as conn:
        try:
            cur = conn.cursor()
            cur.execute(plan['sql'], plan['binds'])
            conn.commit()
            plan['executed'] = True
            plan['nunota'] = plan['binds'].get('NUNOTA')
            plan['sequencia'] = plan['binds'].get('SEQUENCIA')
            # Apply standardization for SIM columns after insert
            try:
                std = standardize_item_fields(plan['nunota'], plan['sequencia'], conn=conn)
                plan['standardize'] = std
            except Exception as _e:
                plan.setdefault('warnings', []).append(f'Falha ao padronizar colunas SIM: {_e}')
            return plan
        except cx_Oracle.DatabaseError as e:
            try:
                err, = e.args
                code = getattr(err, 'code', None)
                msg = getattr(err, 'message', str(e))
            except Exception:
                code = None
                msg = str(e)
            plan['db_error'] = {'code': code, 'message': msg}
            plan['executed'] = False
            return plan


def plan_update_item(d: dict) -> dict:
    """Planeja UPDATE em TGFITE para um item existente identificado por NUNOTA+SEQUENCIA.
    Campos aceitos para atualização: CODPROD, QTDNEG, VLRUNIT, CODVOL, CODLOCALORIG, CONTROLE, OBSERVACAO, AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2.
    Requer: NUNOTA e SEQUENCIA.
    """
    data = d.copy()
    errs: list[str] = []
    warns: list[str] = []

    try:
        data['NUNOTA'] = int(data.get('NUNOTA'))
    except Exception:
        errs.append('NUNOTA inválido ou ausente')
    try:
        data['SEQUENCIA'] = int(data.get('SEQUENCIA'))
    except Exception:
        errs.append('SEQUENCIA inválida ou ausente')

    if errs:
        return {'ok': False, 'errors': errs, 'warnings': warns, 'data': data}

    # Verificar existência do item
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM TGFITE WHERE NUNOTA=:n AND SEQUENCIA=:s", n=data['NUNOTA'], s=data['SEQUENCIA'])
            if cur.fetchone() is None:
                errs.append('Item (NUNOTA/SEQUENCIA) não encontrado')
    except Exception:
        warns.append('Falha ao validar existência do item')

    # Coerções/opcionais
    if data.get('CODPROD') is not None:
        try:
            data['CODPROD'] = int(data.get('CODPROD'))
        except Exception:
            errs.append('CODPROD inválido')
    if data.get('QTDNEG') is not None:
        try:
            data['QTDNEG'] = float(data.get('QTDNEG'))
            if data['QTDNEG'] <= 0:
                errs.append('QTDNEG deve ser > 0')
        except Exception:
            errs.append('QTDNEG inválida')
    if data.get('VLRUNIT') is not None:
        try:
            data['VLRUNIT'] = float(data.get('VLRUNIT'))
        except Exception:
            errs.append('VLRUNIT inválido')
    # Permitir atualizar PRECOBASE (Preço Inicial unitário na tela Comercial)
    if data.get('PRECOBASE') is not None:
        def _parse_decimal(val):
            try:
                # aceita numérico direto
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).strip()
                if s == '':
                    return None
                # remove símbolos monetários e espaços
                import re
                s = re.sub(r"[^0-9,\.-]", "", s)
                # remove separadores de milhar (.) quando há vírgula como decimal
                if ',' in s and '.' in s:
                    s = s.replace('.', '')
                # vírgula para decimal
                s = s.replace(',', '.')
                return float(s)
            except Exception:
                return None
        pb = _parse_decimal(data.get('PRECOBASE'))
        if pb is None:
            # valor inválido: não incluir PRECOBASE na atualização (em vez de gravar 0)
            data.pop('PRECOBASE', None)
            warns.append('PRECOBASE ignorado (formato inválido)')
        else:
            data['PRECOBASE'] = pb
    if data.get('CODVOL') is not None:
        try:
            data['CODVOL'] = str(data.get('CODVOL')).strip().upper()
        except Exception:
            pass

    # Converter QTDNEG para base se CODVOL mudar/for diferente da base (seguir mesma regra do insert)
    try:
        if data.get('CODPROD') is not None and data.get('CODVOL') is not None and data.get('QTDNEG') is not None:
            base, fator = get_base_unit_and_factor(int(data['CODPROD']), str(data['CODVOL']))
            # Enforce valid alternative unit mapping
            if base and str(base).upper() != str(data['CODVOL']).upper() and (fator is None or float(fator) <= 0):
                errs.append(f"Unidade (CODVOL='{data['CODVOL']}') não é alternativa válida para o produto {data['CODPROD']}")
            if base and str(base).upper() != str(data['CODVOL']).upper() and fator and float(fator) > 0:
                try:
                    q_alt = float(data['QTDNEG'])
                    data['QTDNEG'] = round(q_alt * float(fator), 6)
                    warns.append(f"QTDNEG normalizada para a unidade base {base} (×{fator}) no update.")
                except Exception:
                    pass
    except Exception:
        pass

    # Se VLRUNIT e QTDNEG presentes, recalcular VLRTOT
    if data.get('QTDNEG') is not None and data.get('VLRUNIT') is not None:
        try:
            data['VLRTOT'] = round(float(data['QTDNEG']) * float(data['VLRUNIT']), 2)
        except Exception:
            data['VLRTOT'] = None

    # Se a nota for TOP_CLASS, forçar preço 0 (política: TOP 26 não trabalha com preço)
    try:
        with get_connection() as _c3:
            cur3 = _c3.cursor()
            cur3.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA=:n", n=data['NUNOTA'])
            row3 = cur3.fetchone()
            codtop3 = row3[0] if row3 else None
            top_class3 = get_params().get('TOP_CLASS')
            if codtop3 is not None and top_class3 is not None and int(codtop3) == int(top_class3):
                data['VLRUNIT'] = 0.0
                data['VLRTOT'] = 0.0
    except Exception:
        pass

    # Montar SETs/binds
    sets = []
    binds = {'NUNOTA': data['NUNOTA'], 'SEQUENCIA': data['SEQUENCIA']}
    if data.get('CODPROD') is not None:
        sets.append('CODPROD=:CODPROD'); binds['CODPROD'] = data['CODPROD']
    if data.get('QTDNEG') is not None:
        sets.append('QTDNEG=:QTDNEG'); binds['QTDNEG'] = data['QTDNEG']
    if data.get('PESO') is not None:
        sets.append('PESO=:PESO'); binds['PESO'] = data['PESO']
    if data.get('VLRUNIT') is not None:
        sets.append('VLRUNIT=:VLRUNIT'); binds['VLRUNIT'] = data['VLRUNIT']
    if data.get('VLRTOT') is not None:
        sets.append('VLRTOT=:VLRTOT'); binds['VLRTOT'] = data['VLRTOT']
    if data.get('PRECOBASE') is not None:
        sets.append('PRECOBASE=:PRECOBASE'); binds['PRECOBASE'] = data['PRECOBASE']
    if data.get('CODVOL') is not None:
        sets.append('CODVOL=:CODVOL'); binds['CODVOL'] = data['CODVOL']
    if data.get('CODLOCALORIG') is not None:
        sets.append('CODLOCALORIG=:CODLOCALORIG'); binds['CODLOCALORIG'] = data['CODLOCALORIG']
    if data.get('CODAGREGACAO') is not None:
        # Enforce: if destination header is TOP_CLASS, do not allow changing CODAGREGACAO (immutable lote)
        try:
            with get_connection() as _c2:
                cur2 = _c2.cursor()
                cur2.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA=:n", n=data['NUNOTA'])
                row2 = cur2.fetchone()
                codtop = row2[0] if row2 else None
                top_class = get_params().get('TOP_CLASS')
                if codtop is not None and top_class is not None and int(codtop) == int(top_class):
                    # skip adding CODAGREGACAO to SETs for classification note
                    pass
                else:
                    sets.append('CODAGREGACAO=:CODAGREGACAO'); binds['CODAGREGACAO'] = data['CODAGREGACAO']
        except Exception:
            # On failure to determine, default to allowing update
            sets.append('CODAGREGACAO=:CODAGREGACAO'); binds['CODAGREGACAO'] = data['CODAGREGACAO']
    if data.get('OBSERVACAO') is not None:
        sets.append('OBSERVACAO=:OBSERVACAO'); binds['OBSERVACAO'] = data['OBSERVACAO']
    # Permitir alterar GERAPRODUCAO quando informado
    if d.get('GERAPRODUCAO') is not None or d.get('geraproducao') is not None:
        val = d.get('GERAPRODUCAO') if d.get('GERAPRODUCAO') is not None else d.get('geraproducao')
        sval = str(val).strip().upper() if val is not None else None
        if sval in ('S','N'):
            sets.append('GERAPRODUCAO=:GERAPRODUCAO'); binds['GERAPRODUCAO'] = sval
        else:
            # valor inválido é ignorado, sem erro
            pass
    
    # Permitir salvar campos de simulação Extra/Médio (AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2)
    if data.get('AD_SIMQTD1') is not None:
        try:
            sets.append('AD_SIMQTD1=:AD_SIMQTD1'); binds['AD_SIMQTD1'] = float(data['AD_SIMQTD1'])
        except Exception:
            pass
    if data.get('AD_SIMQTD2') is not None:
        try:
            sets.append('AD_SIMQTD2=:AD_SIMQTD2'); binds['AD_SIMQTD2'] = float(data['AD_SIMQTD2'])
        except Exception:
            pass
    if data.get('AD_SIMVLR1') is not None:
        try:
            sets.append('AD_SIMVLR1=:AD_SIMVLR1'); binds['AD_SIMVLR1'] = float(data['AD_SIMVLR1'])
        except Exception:
            pass
    if data.get('AD_SIMVLR2') is not None:
        try:
            sets.append('AD_SIMVLR2=:AD_SIMVLR2'); binds['AD_SIMVLR2'] = float(data['AD_SIMVLR2'])
        except Exception:
            pass

    if not sets:
        warns.append('Nenhuma coluna para atualizar')

    if sets:
        try:
            with get_connection() as _c:
                if 'DTALTER' in _get_table_columns(_c, 'TGFITE'):
                    sets.append('DTALTER=SYSDATE')
        except Exception:
            pass
    sql = f"UPDATE TGFITE SET {', '.join(sets)} WHERE NUNOTA=:NUNOTA AND SEQUENCIA=:SEQUENCIA" if sets else None

    return {'ok': len(errs) == 0 and bool(sets), 'errors': errs, 'warnings': warns, 'sql': sql, 'binds': binds, 'data': data}


def update_item(d: dict, dry_run: bool = True) -> dict:
    """Executa (ou simula) um UPDATE em TGFITE para o item identificado por NUNOTA/SEQUENCIA."""
    plan = plan_update_item(d)
    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            plan.setdefault('warnings', []).append('Escrita desabilitada por política — execução em modo simulado')
        return plan
    if not plan.get('ok'):
        return plan
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(plan['sql'], plan['binds'])
            conn.commit()
            plan['executed'] = True
            # Apply standardization after update as well
            try:
                std = standardize_item_fields(plan['binds']['NUNOTA'], plan['binds']['SEQUENCIA'], conn=conn)
                plan['standardize'] = std
            except Exception as _e:
                plan.setdefault('warnings', []).append(f'Falha ao padronizar colunas SIM: {_e}')
            return plan
    except cx_Oracle.DatabaseError as e:
        try:
            err, = e.args
            plan['db_error'] = {'code': getattr(err, 'code', None), 'message': getattr(err, 'message', str(e))}
        except Exception:
            plan['db_error'] = {'message': str(e)}
        plan['executed'] = False
        return plan


def calcular_agregados_lote(controle: str) -> dict:
    """Calcula agregados principais do lote pesquisando TGFCAB/TGFITE usando TOPs reais."""
    p = get_params()
    TOP_ENTRADA = p['TOP_ENTRADA']
    TOP_CLASS = p.get('TOP_CLASS', 26)
    TOP_CLASS = p.get('TOP_CLASS', 26)
    # Also need TOP_CLASS (e.g., 26) for classification status lookup below
    TOP_CLASS = p.get('TOP_CLASS', 26)
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_CLASS = p['TOP_CLASS']
    TOP_PED_VENDA = p['TOP_PED_VENDA']
    TOP_VENDAS = p['TOP_VENDAS']
    TOP_AVARIA = p['TOP_AVARIA']
    PROD_IN_NATURA = p['PROD_IN_NATURA']
    PROD_CLASS_LIST = p['PROD_CLASS_LIST']
    PROD_DESCARTE = p['PROD_DESCARTE']

    class_list_sql = ','.join(str(x) for x in PROD_CLASS_LIST)
    vendas_list_sql = ','.join(str(x) for x in TOP_VENDAS)

    agregados = {
        'lote': controle,
        'qtd_prevista': 0.0,
        'qtd_classificada': 0.0,
        'qtd_descartada': 0.0,
        'qtd_vendida': 0.0,
        'qtd_reservada': 0.0,
        'qtd_disponivel': 0.0,
        'divergencia': 0.0,
        'estado': 'Desconhecido'
    }
    with get_connection() as conn:
        cur = conn.cursor()
        # Prevista (entrada in natura)
        cur.execute(
            """
            SELECT NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO = :c
               AND c.CODTIPOPER = :top
               AND i.CODPROD = :prod
            """,
            c=controle, top=TOP_ENTRADA, prod=PROD_IN_NATURA
        )
        (agregados['qtd_prevista'],) = cur.fetchone()

        # Classificada
        cur.execute(
            f"""
            SELECT NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO = :c
               AND c.CODTIPOPER = :top
               AND i.CODPROD IN ({class_list_sql})
            """,
            c=controle, top=TOP_CLASS
        )
        (agregados['qtd_classificada'],) = cur.fetchone()

        # Descarte (910) em classificação e avaria
        cur.execute(
            """
            SELECT NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO = :c
               AND i.CODPROD = :prod
               AND c.CODTIPOPER IN (:tc, :ta)
            """,
            c=controle, prod=PROD_DESCARTE, tc=TOP_CLASS, ta=TOP_AVARIA
        )
        (agregados['qtd_descartada'],) = cur.fetchone()

        # Vendida (TOPs vendas)
        cur.execute(
            f"""
            SELECT NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO = :c
               AND c.CODTIPOPER IN ({vendas_list_sql})
            """,
            c=controle
        )
        (agregados['qtd_vendida'],) = cur.fetchone()

        # Reservada (pedido de venda TOP)
        cur.execute(
            """
            SELECT NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO = :c
               AND c.CODTIPOPER = :top
            """,
            c=controle, top=TOP_PED_VENDA
        )
        (agregados['qtd_reservada'],) = cur.fetchone()

    agregados['qtd_disponivel'] = max(0.0, float(agregados['qtd_classificada']) - float(agregados['qtd_vendida']) - float(agregados['qtd_reservada']))
    agregados['divergencia'] = float(agregados['qtd_classificada']) + float(agregados['qtd_descartada']) - float(agregados['qtd_prevista'])

    if agregados['qtd_prevista'] > 0 and agregados['qtd_classificada'] == 0 and agregados['qtd_descartada'] == 0:
        agregados['estado'] = 'Pedido Compra'
    elif agregados['qtd_classificada'] > 0 and agregados['qtd_disponivel'] > 0:
        agregados['estado'] = 'Classificando'
    elif agregados['qtd_disponivel'] == 0 and agregados['qtd_classificada'] > 0:
        agregados['estado'] = 'Encerrado'
    else:
        agregados['estado'] = 'Entregue' if agregados['qtd_reservada'] == 0 else 'Parcialmente Entregue'

    return agregados

def resumo_classificacao_por_lote(lote: str) -> list[tuple]:
    """Agrega itens classificados (TOP 26) por produto para um lote (CODAGREGACAO).
    Retorna lista de tuplas: (DESCRPROD, SUM_CX, SUM_KG)
    Regras:
      - Considera somente cabeçalhos com CODTIPOPER = TOP_CLASS
      - Interpretação de unidades:
          QTDNEG é armazenado na unidade base do produto; para exposição:
            • somatório em CX: somar QTDNEG quando CODVOL='CX'
            • somatório em KG: somar QTDNEG quando CODVOL='KG'
        Se necessário, podemos normalizar por fator TGFVOA numa versão futura.
    """
    p = get_params()
    top_class = p['TOP_CLASS']
    sql = (
        """
        SELECT p.DESCRPROD,
               SUM(CASE WHEN UPPER(NVL(i.CODVOL,''))='CX' THEN NVL(i.QTDNEG,0) ELSE 0 END) AS SUM_CX,
               SUM(CASE WHEN UPPER(NVL(i.CODVOL,''))='KG' THEN NVL(i.QTDNEG,0) ELSE 0 END) AS SUM_KG
          FROM TGFITE i
          JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
          LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
         WHERE i.CODAGREGACAO = :lote AND c.CODTIPOPER = :top
         GROUP BY p.DESCRPROD
         ORDER BY p.DESCRPROD
        """
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, lote=lote, top=top_class)
        return cur.fetchall()


def consultar_lote(controle: str) -> dict:
    """Retorna detalhes do lote: itens agrupados por tipo e agregados."""
    p = get_params()
    TOP_ENTRADA = p['TOP_ENTRADA']
    TOP_CLASS = p['TOP_CLASS']
    TOP_PED_VENDA = p['TOP_PED_VENDA']
    TOP_VENDAS = p['TOP_VENDAS']
    TOP_AVARIA = p['TOP_AVARIA']
    PROD_CLASS_LIST = p['PROD_CLASS_LIST']

    class_list_sql = ','.join(str(x) for x in PROD_CLASS_LIST)
    vendas_list_sql = ','.join(str(x) for x in TOP_VENDAS)

    resultado = {
        'agregados': calcular_agregados_lote(controle),
        'entradas': [],
        'classificaveis': [],
        'classificacoes': [],
        'descarte': [],
        'vendas': [],
        'reservas': [],
        'nunota_class': None,
        'statusnota_class': None,
    }
    # Perf counters
    import time
    t0 = time.perf_counter()
    t_ag0 = time.perf_counter()
    # calcular_agregados_lote já executado acima
    t_ag1 = time.perf_counter()
    with get_connection() as conn:
        cur = conn.cursor()

        # Entradas
        t_e0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT, pr.NOMEPARC
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
              LEFT JOIN TGFPAR pr ON pr.CODPARC = c.CODPARC
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top=TOP_ENTRADA
        )
        resultado['entradas'] = cur.fetchall()
        t_e1 = time.perf_counter()

        # Itens classificáveis (entrada TOP_ENTRADA com GERAPRODUCAO = 'S' apenas)
        t_cv0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                         WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top_ent
                             AND NVL(i.GERAPRODUCAO, 'N') = 'S'
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top_ent=TOP_ENTRADA
        )
        resultado['classificaveis'] = cur.fetchall()
        t_cv1 = time.perf_counter()

        # Classificações — mostrar todos os itens classificados (TOP_CLASS)
        t_cl0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top=TOP_CLASS
        )
        resultado['classificacoes'] = cur.fetchall()
        t_cl1 = time.perf_counter()

        # Descarte
        t_ds0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.QTDNEG
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO = :c AND i.CODPROD = 910 AND c.CODTIPOPER IN (:tc, :ta)
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, tc=TOP_CLASS, ta=TOP_AVARIA
        )
        resultado['descarte'] = cur.fetchall()
        t_ds1 = time.perf_counter()

        # Vendas
        t_v0 = time.perf_counter()
        cur.execute(
            f"""
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.QTDNEG, i.VLRUNIT, i.VLRTOT, c.CODTIPOPER
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER IN ({vendas_list_sql})
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle
        )
        resultado['vendas'] = cur.fetchall()
        t_v1 = time.perf_counter()

        # Reservas
        t_r0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.QTDNEG
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top=TOP_PED_VENDA
        )
        resultado['reservas'] = cur.fetchall()
        t_r1 = time.perf_counter()

        # Nota TOP_CLASS existente para este controle (se houver)
        try:
            t_nc0 = time.perf_counter()
            cur.execute(
                """
                SELECT i.NUNOTA FROM (
                  SELECT DISTINCT i.NUNOTA
                    FROM TGFITE i
                    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                   WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
                   ORDER BY i.NUNOTA DESC
                ) WHERE ROWNUM = 1
                """,
                c=controle, top=TOP_CLASS
            )
            row_nc = cur.fetchone()
            if row_nc and row_nc[0] is not None:
                try:
                    resultado['nunota_class'] = int(row_nc[0])
                except Exception:
                    resultado['nunota_class'] = row_nc[0]
                # Fetch STATUSNOTA for this header
                try:
                    cur.execute("SELECT STATUSNOTA FROM TGFCAB WHERE NUNOTA=:n", n=resultado['nunota_class'])
                    row_st = cur.fetchone()
                    if row_st and row_st[0] is not None:
                        try:
                            resultado['statusnota_class'] = str(row_st[0]).strip()
                        except Exception:
                            resultado['statusnota_class'] = row_st[0]
                except Exception:
                    resultado['statusnota_class'] = None
            t_nc1 = time.perf_counter()
        except Exception:
            resultado['nunota_class'] = None
            t_nc1 = time.perf_counter()
    t1 = time.perf_counter()
    try:
        resultado['timings'] = {
            'total_ms': int((t1 - t0) * 1000),
            'agregados_ms': int((t_ag1 - t_ag0) * 1000),
            'entradas_ms': int((t_e1 - t_e0) * 1000),
            'classificaveis_ms': int((t_cv1 - t_cv0) * 1000),
            'classificacoes_ms': int((t_cl1 - t_cl0) * 1000),
            'descarte_ms': int((t_ds1 - t_ds0) * 1000),
            'vendas_ms': int((t_v1 - t_v0) * 1000),
            'reservas_ms': int((t_r1 - t_r0) * 1000),
            'nunota_class_ms': int((t_nc1 - t_nc0) * 1000),
        }
    except Exception:
        pass
    return resultado


def consultar_lote_light(controle: str) -> dict:
    """Versão leve de consultar_lote usada no clique da UI.
    Busca somente:
      - entradas (TOP_ENTRADA)
      - itens classificáveis (subset de entradas com GERAPRODUCAO='S')
      - classificações (TOP_CLASS)
      - nunota_class (mais recente)
    Ignora agregados, vendas, reservas e descarte para reduzir latência.
    Retorna também um bloco de timings em milissegundos.
    """
    p = get_params()
    TOP_ENTRADA = p['TOP_ENTRADA']
    TOP_CLASS = p['TOP_CLASS']

    resultado = {
        'entradas': [],
        'classificaveis': [],
        'classificacoes': [],
        'nunota_class': None,
        'statusnota_class': None,
    }
    import time
    t0 = time.perf_counter()
    with get_connection() as conn:
        cur = conn.cursor()

        # Entradas (TOP_ENTRADA)
        t_e0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT, pr.NOMEPARC
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
              LEFT JOIN TGFPAR pr ON pr.CODPARC = c.CODPARC
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top=TOP_ENTRADA
        )
        resultado['entradas'] = cur.fetchall()
        t_e1 = time.perf_counter()

        # Classificáveis (subset das entradas com GERAPRODUCAO='S')
        t_cv0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top_ent
               AND NVL(i.GERAPRODUCAO, 'N') = 'S'
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top_ent=TOP_ENTRADA
        )
        resultado['classificaveis'] = cur.fetchall()
        t_cv1 = time.perf_counter()

        # Classificações (TOP_CLASS)
        t_cl0 = time.perf_counter()
        cur.execute(
            """
            SELECT c.NUNOTA, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
             ORDER BY c.NUNOTA, i.SEQUENCIA
            """,
            c=controle, top=TOP_CLASS
        )
        resultado['classificacoes'] = cur.fetchall()
        t_cl1 = time.perf_counter()

        # Status TOP_CLASS agregado por controle (preferir 'L' se qualquer nota TOP 26 do controle estiver liberada)
        t_nc0 = time.perf_counter()
        try:
            cur.execute(
                """
                SELECT MAX(CASE WHEN c.STATUSNOTA='L' THEN 1 ELSE 0 END) AS has_l,
                       MAX(c.NUNOTA) AS nunota_any,
                       MAX(c.STATUSNOTA) AS status_any
                  FROM TGFITE i
                  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                 WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
                """,
                c=controle, top=TOP_CLASS
            )
            row_nc = cur.fetchone()
            if row_nc:
                has_l, nun_any, status_any = row_nc
                try:
                    resultado['nunota_class'] = int(nun_any) if nun_any is not None else None
                except Exception:
                    resultado['nunota_class'] = nun_any
                try:
                    hl = int(has_l or 0)
                except Exception:
                    hl = 0
                if hl > 0:
                    resultado['statusnota_class'] = 'L'
                else:
                    try:
                        resultado['statusnota_class'] = (status_any or '').strip()
                    except Exception:
                        resultado['statusnota_class'] = status_any
        except Exception:
            pass
        t_nc1 = time.perf_counter()

    t1 = time.perf_counter()
    try:
        resultado['timings'] = {
            'total_ms': int((t1 - t0) * 1000),
            'entradas_ms': int((t_e1 - t_e0) * 1000),
            'classificaveis_ms': int((t_cv1 - t_cv0) * 1000),
            'classificacoes_ms': int((t_cl1 - t_cl0) * 1000),
            'nunota_class_ms': int((t_nc1 - t_nc0) * 1000),
            'mode': 'light',
        }
    except Exception:
        pass
    return resultado


def consultar_lotes_sumario(controles: list[str]) -> dict[str, dict]:
    """Batched summary for multiple controles to speed up the classificação page.
    Returns a dict mapping controle -> {
      parceiro, produto_descr, qtd_pedido, qtd_classificada, qtd_disponivel,
      exemplo_nunota, exemplo_seq, nunota_class
    }
    Note: produtos_entrada list is intentionally omitted for performance; the UI
    falls back to produto_descr when list is empty.
    """
    if not controles:
        return {}
    # Ensure unique and reasonable length
    keys = [str(c) for c in controles if c]
    if not keys:
        return {}
    # Build placeholders for IN clause
    placeholders = []
    binds = {}
    for idx, c in enumerate(keys):
        ph = f"c{idx}"
        placeholders.append(f":{ph}")
        binds[ph] = c
    in_clause = ",".join(placeholders)

    p = get_params()
    TOP_ENTRADA = p['TOP_ENTRADA']
    TOP_CLASS = p['TOP_CLASS']
    TOP_PED_VENDA = p['TOP_PED_VENDA']
    TOP_VENDAS = p['TOP_VENDAS']
    PROD_IN_NATURA = p['PROD_IN_NATURA']
    PROD_CLASS_LIST = p['PROD_CLASS_LIST']

    vendas_list_sql = ",".join(str(x) for x in TOP_VENDAS)
    class_list_sql = ",".join(str(x) for x in PROD_CLASS_LIST)

    out: dict[str, dict] = {c: {
        'parceiro': '', 'produto_descr': '',
        'codparc': None,
        'qtd_pedido': 0.0, 'qtd_classificada': 0.0, 'qtd_disponivel': 0.0,
        'exemplo_nunota': None, 'exemplo_seq': None, 'nunota_class': None,
        'produtos_entrada': [],
    } for c in keys}

    import time
    t0 = time.perf_counter()
    with get_connection() as conn:
        cur = conn.cursor()
        # 1) Entradas: parceiro, qtd_pedido (In Natura), exemplo nunota/seq
        t_ent0 = time.perf_counter()
        sql_ent = f"""
                        SELECT i.CODAGREGACAO AS CTRL,
                                     MAX(pr.NOMEPARC) AS PARCEIRO,
                                     MAX(c.CODPARC) AS CODPARC,
                                     -- Qtde de caixas calculada dividindo a quantidade base pelo fator da unidade alternativa (quando CX)
                                     SUM(CASE 
                                                 WHEN c.CODTIPOPER = :top_ent 
                                                    AND UPPER(NVL(i.CODVOL,'')) = 'CX' 
                                                    AND (
                                                             CASE 
                                                                 WHEN voa.FATOR IS NOT NULL AND voa.FATOR > 0 THEN voa.FATOR
                                                                 WHEN voa.QUANTIDADE IS NOT NULL AND UPPER(NVL(voa.DIVIDEMULTIPLICA,'M')) = 'M' THEN voa.QUANTIDADE
                                                                 WHEN voa.QUANTIDADE IS NOT NULL AND UPPER(NVL(voa.DIVIDEMULTIPLICA,'M')) = 'D' AND voa.QUANTIDADE <> 0 THEN (1/voa.QUANTIDADE)
                                                                 ELSE NULL
                                                             END
                                                            ) > 0
                                                    THEN i.QTDNEG / (
                                                             CASE 
                                                                 WHEN voa.FATOR IS NOT NULL AND voa.FATOR > 0 THEN voa.FATOR
                                                                 WHEN voa.QUANTIDADE IS NOT NULL AND UPPER(NVL(voa.DIVIDEMULTIPLICA,'M')) = 'M' THEN voa.QUANTIDADE
                                                                 WHEN voa.QUANTIDADE IS NOT NULL AND UPPER(NVL(voa.DIVIDEMULTIPLICA,'M')) = 'D' AND voa.QUANTIDADE <> 0 THEN (1/voa.QUANTIDADE)
                                                                 ELSE NULL
                                                             END
                                                    )
                                                 ELSE 0 
                                             END) AS QTD_CX,
                                     -- Qtde em KG: somar somente produtos cuja unidade base é KG
                                     SUM(CASE WHEN c.CODTIPOPER = :top_ent AND UPPER(NVL(pp.CODVOL,'')) = 'KG' THEN i.QTDNEG ELSE 0 END) AS QTD_KG,
                                     MIN(c.NUNOTA) KEEP (DENSE_RANK FIRST ORDER BY c.NUNOTA) AS EX_NUNOTA,
                                     MIN(i.SEQUENCIA) KEEP (DENSE_RANK FIRST ORDER BY i.SEQUENCIA) AS EX_SEQ
                            FROM TGFITE i
                            JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                            LEFT JOIN TGFPAR pr ON pr.CODPARC = c.CODPARC
                            LEFT JOIN TGFPRO pp ON pp.CODPROD = i.CODPROD
                            LEFT JOIN TGFVOA voa ON voa.CODPROD = i.CODPROD AND UPPER(voa.CODVOL) = UPPER(NVL(i.CODVOL,''))
                         WHERE i.CODAGREGACAO IN ({in_clause})
                         GROUP BY i.CODAGREGACAO
        """
        cur.execute(sql_ent, {**binds, 'top_ent': TOP_ENTRADA})
        rows_ent = cur.fetchall()
        t_ent1 = time.perf_counter()
        for ctrl, parceiro, codparc, qtd_cx, qtd_kg, ex_n, ex_s in rows_ent:
            d = out.get(ctrl)
            if d is not None:
                d['parceiro'] = parceiro or ''
                try:
                    d['codparc'] = int(codparc) if codparc is not None else None
                except Exception:
                    d['codparc'] = codparc
                # New fields
                try:
                    d['qtd_cx'] = float(qtd_cx or 0)
                except Exception:
                    d['qtd_cx'] = 0.0
                try:
                    d['qtd_kg'] = float(qtd_kg or 0)
                except Exception:
                    d['qtd_kg'] = 0.0
                # Back-compat for existing UI: keep qtd_pedido as qtd_cx
                d['qtd_pedido'] = d['qtd_cx']
                d['exemplo_nunota'] = ex_n
                d['exemplo_seq'] = ex_s

        # 2) Classificada: sum for class products in TOP_CLASS
        t_cls0 = time.perf_counter()
        sql_cls = (
            f"""
            SELECT i.CODAGREGACAO AS CTRL, NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO IN ({in_clause})
               AND c.CODTIPOPER = :top_class
               AND i.CODPROD IN ({class_list_sql})
             GROUP BY i.CODAGREGACAO
            """
        )
        cur.execute(sql_cls, {**binds, 'top_class': TOP_CLASS})
        rows_cls = cur.fetchall()
        t_cls1 = time.perf_counter()
        for ctrl, qtd_class in rows_cls:
            d = out.get(ctrl)
            if d is not None:
                try:
                    d['qtd_classificada'] = float(qtd_class or 0)
                except Exception:
                    d['qtd_classificada'] = 0.0

        # 3) Vendas (TOPs vendas)
        t_vnd0 = time.perf_counter()
        sql_vnd = (
            f"""
            SELECT i.CODAGREGACAO AS CTRL, NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO IN ({in_clause})
               AND c.CODTIPOPER IN ({vendas_list_sql})
             GROUP BY i.CODAGREGACAO
            """
        )
        cur.execute(sql_vnd, binds)
        rows_vnd = cur.fetchall()
        vendidas = {ctrl: float(q or 0) for ctrl, q in rows_vnd}
        t_vnd1 = time.perf_counter()

        # 4) Reservas (pedido de venda TOP)
        t_rsv0 = time.perf_counter()
        sql_rsv = (
            f"""
            SELECT i.CODAGREGACAO AS CTRL, NVL(SUM(i.QTDNEG), 0)
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO IN ({in_clause})
               AND c.CODTIPOPER = :top_ped
             GROUP BY i.CODAGREGACAO
            """
        )
        cur.execute(sql_rsv, {**binds, 'top_ped': TOP_PED_VENDA})
        rows_rsv = cur.fetchall()
        reservadas = {ctrl: float(q or 0) for ctrl, q in rows_rsv}
        t_rsv1 = time.perf_counter()

        # 5) NUNOTA TOP_CLASS existente (mais recente)
        t_nc0 = time.perf_counter()
        sql_ncls = (
            f"""
            SELECT ctrl, MAX(nun) AS nunota_class FROM (
              SELECT i.CODAGREGACAO AS ctrl, i.NUNOTA AS nun
                FROM TGFITE i
                JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
               WHERE i.CODAGREGACAO IN ({in_clause})
                 AND c.CODTIPOPER = :top_class
            ) GROUP BY ctrl
            """
        )
        cur.execute(sql_ncls, {**binds, 'top_class': TOP_CLASS})
        rows_nc = cur.fetchall()
        t_nc1 = time.perf_counter()
        for ctrl, nun in rows_nc:
            d = out.get(ctrl)
            if d is not None:
                d['nunota_class'] = nun

        # 6) Produtos de entrada por controle (TOP_ENTRADA)
        t_pe0 = time.perf_counter()
        sql_pe = (
            f"""
            SELECT i.CODAGREGACAO AS CTRL, i.CODPROD, p.DESCRPROD
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO IN ({in_clause}) AND c.CODTIPOPER = :top_ent
             GROUP BY i.CODAGREGACAO, i.CODPROD, p.DESCRPROD
            """
        )
        cur.execute(sql_pe, {**binds, 'top_ent': TOP_ENTRADA})
        rows_pe = cur.fetchall()
        t_pe1 = time.perf_counter()
        for ctrl, cod, descr in rows_pe:
            d = out.get(ctrl)
            if d is not None:
                lst = d.setdefault('produtos_entrada', [])
                try:
                    cod_i = int(cod) if cod is not None else None
                except Exception:
                    cod_i = cod
                lst.append({'cod': cod_i, 'descr': descr or ''})

        # Set produto_descr from first product when available
        for d in out.values():
            if d['produtos_entrada']:
                first = d['produtos_entrada'][0]
                d['produto_descr'] = (first.get('descr') or '').strip()

        # Compute disponibilidade
        for ctrl, d in out.items():
            q_class = float(d.get('qtd_classificada') or 0)
            q_vend = float(vendidas.get(ctrl) or 0)
            q_resv = float(reservadas.get(ctrl) or 0)
            disp = q_class - q_vend - q_resv
            d['qtd_disponivel'] = disp if disp > 0 else 0.0

    t1 = time.perf_counter()
    try:
        import logging
        logging.getLogger(__name__).info(
            '[sumario] ent=%dms cls=%dms vnd=%dms rsv=%dms nuncls=%dms prod=%dms total=%dms controles=%d',
            int((t_ent1 - t_ent0) * 1000), int((t_cls1 - t_cls0) * 1000), int((t_vnd1 - t_vnd0) * 1000),
            int((t_rsv1 - t_rsv0) * 1000), int((t_nc1 - t_nc0) * 1000), int((t_pe1 - t_pe0) * 1000),
            int((t1 - t0) * 1000), len(keys)
        )
    except Exception:
        pass
        return out


def listar_lotes_recentes(
    days: int = 7,
    limit: int = 50,
    codparc: int | None = None,
    codprod: int | None = None,
    codprods: list[int] | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
):
    """Lista CONTROLEs distintos com movimentação recente.
    - Periodicidade por `days` (padrão) ou por período explícito (`date_start`/`date_end`, formato YYYY-MM-DD).
    - Filtros opcionais por parceiro (`codparc`) e por produto único (`codprod`) ou vários (`codprods`).
    """
    from datetime import datetime, date as _date

    def _to_date(val: str | _date | None):
        if val in (None, '', 'None', 'none', 'null'):
            return None
        if isinstance(val, _date):
            return val
        if isinstance(val, datetime):
            return val.date()
        try:
            return datetime.strptime(str(val), "%Y-%m-%d").date()
        except Exception:
            return None

    dtini = _to_date(date_start)
    dtfim = _to_date(date_end)

    where = [
        "i.CODAGREGACAO IS NOT NULL",
        "LENGTH(i.CODAGREGACAO) >= 8",
    ]
    binds: dict[str, object] = {}

    if dtini and dtfim:
        where.append("TRUNC(c.DTNEG) BETWEEN :dtini AND :dtfim")
        binds["dtini"] = dtini
        binds["dtfim"] = dtfim
    elif dtini:
        where.append("TRUNC(c.DTNEG) >= :dtini")
        binds["dtini"] = dtini
    elif dtfim:
        where.append("TRUNC(c.DTNEG) <= :dtfim")
        binds["dtfim"] = dtfim
    else:
        where.append("c.DTNEG >= SYSDATE - :days")
        binds["days"] = days

    if codparc is not None:
        where.append("c.CODPARC = :codparc")
        binds["codparc"] = codparc

    # Produtos: único ou lista
    in_clause = None
    if codprods:
        plist = [int(x) for x in codprods]
        if plist:
            in_clause = ",".join(str(x) for x in plist)
    if in_clause:
        where.append(f"i.CODPROD IN ({in_clause})")
    elif codprod is not None:
        where.append("i.CODPROD = :codprod")
        binds["codprod"] = codprod

    sql = (
        "SELECT DISTINCT i.CODAGREGACAO "
        "FROM TGFITE i JOIN TGFCAB c ON c.NUNOTA=i.NUNOTA "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY i.CODAGREGACAO DESC"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        rows = cur.fetchmany(limit)
        return [r[0] for r in rows]


def listar_lotes_entradas_classificaveis(
        days: int = 7,
        limit: int = 50,
        codparc: int | None = None,
        codprod: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
    ):
        """Lista CONTROLEs (lotes) a partir de itens de ENTRADA (TOP 11) que são classificáveis (GERAPRODUCAO='S').
        - Filtro por período (DTNEG) com days ou date_start/date_end
        - Filtros opcionais por CODPARC e CODPROD
        - Retorna até `limit` controles distintos (ordenados por DTNEG desc e controle desc)
        """
        from datetime import datetime, date as _date, timedelta

        def _to_date(val: str | _date | None):
            if val in (None, '', 'None', 'none', 'null'):
                return None
            if isinstance(val, _date):
                return val
            if isinstance(val, datetime):
                return val.date()
            try:
                return datetime.strptime(str(val), "%Y-%m-%d").date()
            except Exception:
                return None

        params = get_params()
        TOP_ENTRADA = params['TOP_ENTRADA']  # 11

        dtini = _to_date(date_start)
        dtfim = _to_date(date_end)
        if dtini is None and dtfim is None:
            dtini = (_date.today() - timedelta(days=days))
            dtfim = _date.today()

        where = [
            "c.CODTIPOPER = :top_entrada",
            "i.CODAGREGACAO IS NOT NULL",
            "NVL(i.GERAPRODUCAO,'N') = 'S'",
        ]
        binds: dict[str, object] = {"top_entrada": TOP_ENTRADA}

        if dtini:
            where.append("c.DTNEG >= :dtini")
            binds["dtini"] = dtini
        if dtfim:
            where.append("c.DTNEG <= :dtfim")
            binds["dtfim"] = dtfim
        if codparc is not None:
            where.append("c.CODPARC = :codparc")
            binds["codparc"] = codparc
        if codprod is not None:
            where.append("i.CODPROD = :codprod")
            binds["codprod"] = codprod

        inner = (
            "SELECT DISTINCT i.CODAGREGACAO AS controle, c.DTNEG "
            "FROM TGFITE i JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY c.DTNEG DESC, i.CODAGREGACAO DESC"
        )
        sql = f"SELECT controle FROM ({inner}) WHERE ROWNUM <= :lim"
        binds['lim'] = int(limit or 50)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, binds)
            rows = cur.fetchall()
            # return as list of tuples to mirror other list_* functions usage
            return [(r[0],) if not isinstance(r, (list, tuple)) else r for r in rows]


def consultar_lotes_sumario_top11_classificaveis(controles: list[str]) -> dict[str, dict]:
    """Resumo leve para múltiplos controles baseado SOMENTE em entradas TOP 11
    classificáveis (GERAPRODUCAO='S') para uso na página de Classificação.
    Retorna por controle: parceiro/codparc, qtd_cx, qtd_kg e lista de produtos classificáveis.
    """
    if not controles:
        return {}
    keys = [str(c) for c in controles if c]
    if not keys:
        return {}

    # Build IN clause
    placeholders = []
    binds: dict[str, object] = {}
    for idx, c in enumerate(keys):
        ph = f"c{idx}"
        placeholders.append(f":{ph}")
        binds[ph] = c
    in_clause = ",".join(placeholders)

    p = get_params()
    TOP_ENTRADA = p['TOP_ENTRADA']
    TOP_CLASS = p.get('TOP_CLASS', 26)

    out: dict[str, dict] = {c: {
        'parceiro': '',
        'codparc': None,
        'qtd_cx': 0.0,
        'qtd_kg': 0.0,
        'peso_inn': None,
        'nunota_class': None,
        'statusnota_class': None,
        'produtos_entrada': [],  # classifiable products only
    } for c in keys}
    with get_connection() as conn:
        cur = conn.cursor()
        # Partner + quantities by volume
        # Qtde cx: normaliza QTDNEG da unidade do item para CX usando fatores do TGFVOA.
        # Regra:
        # - Se o item já estiver em CX, usa QTDNEG direto.
        # - Caso contrário, converte a QTDNEG para a unidade base (via TGFVOA do CODVOL do item) e depois divide pelo fator da CX.
        sql_q = f"""
                SELECT i.CODAGREGACAO AS CTRL,
                         MAX(UPPER(NVL(pr.RAZAOSOCIAL, pr.NOMEPARC))) AS PARCEIRO,
                         MAX(c.CODPARC) AS CODPARC,
                         SUM(
                                 CASE WHEN UPPER(NVL(i.CODVOL,''))='CX' THEN i.QTDNEG
                                            ELSE
                                                CASE
                                                    -- Fator base por CX (kg/caixa, un/caixa, etc)
                                                    WHEN (
                                                             CASE
                                                                 WHEN vcx.FATOR IS NOT NULL AND vcx.FATOR > 0 THEN vcx.FATOR
                                                                 WHEN vcx.QUANTIDADE IS NOT NULL AND UPPER(NVL(vcx.DIVIDEMULTIPLICA,'M'))='M' THEN vcx.QUANTIDADE
                                                                 WHEN vcx.QUANTIDADE IS NOT NULL AND UPPER(NVL(vcx.DIVIDEMULTIPLICA,'M'))='D' AND vcx.QUANTIDADE<>0 THEN (1/vcx.QUANTIDADE)
                                                                 ELSE NULL
                                                             END
                                                    ) > 0
                                                    THEN (
                                                      -- Quantidade em unidade base do produto
                                                      (
                                                        CASE
                                                          WHEN UPPER(NVL(pp.CODVOL,'')) = UPPER(NVL(i.CODVOL,'')) THEN i.QTDNEG
                                                          ELSE
                                                            CASE
                                                              WHEN (
                                                                       CASE
                                                                         WHEN vio.FATOR IS NOT NULL AND vio.FATOR > 0 THEN vio.FATOR
                                                                         WHEN vio.QUANTIDADE IS NOT NULL AND UPPER(NVL(vio.DIVIDEMULTIPLICA,'M'))='M' THEN vio.QUANTIDADE
                                                                         WHEN vio.QUANTIDADE IS NOT NULL AND UPPER(NVL(vio.DIVIDEMULTIPLICA,'M'))='D' AND vio.QUANTIDADE<>0 THEN (1/vio.QUANTIDADE)
                                                                         ELSE NULL
                                                                       END
                                                              ) > 0 THEN i.QTDNEG * (
                                                                       CASE
                                                                         WHEN vio.FATOR IS NOT NULL AND vio.FATOR > 0 THEN vio.FATOR
                                                                         WHEN vio.QUANTIDADE IS NOT NULL AND UPPER(NVL(vio.DIVIDEMULTIPLICA,'M'))='M' THEN vio.QUANTIDADE
                                                                         WHEN vio.QUANTIDADE IS NOT NULL AND UPPER(NVL(vio.DIVIDEMULTIPLICA,'M'))='D' AND vio.QUANTIDADE<>0 THEN (1/vio.QUANTIDADE)
                                                                         ELSE NULL
                                                                       END
                                                              )
                                                              ELSE NULL
                                                            END
                                                        END
                                                      ) / (
                                                         CASE
                                                           WHEN vcx.FATOR IS NOT NULL AND vcx.FATOR > 0 THEN vcx.FATOR
                                                           WHEN vcx.QUANTIDADE IS NOT NULL AND UPPER(NVL(vcx.DIVIDEMULTIPLICA,'M'))='M' THEN vcx.QUANTIDADE
                                                           WHEN vcx.QUANTIDADE IS NOT NULL AND UPPER(NVL(vcx.DIVIDEMULTIPLICA,'M'))='D' AND vcx.QUANTIDADE<>0 THEN (1/vcx.QUANTIDADE)
                                                           ELSE NULL
                                                         END
                                                      )
                                                    )
                                                    ELSE 0
                                                END
                                 END
                         ) AS QTD_CX,
                         -- Qtde em KG (somar quando base for KG)
                         SUM(CASE WHEN UPPER(NVL(pp.CODVOL,''))='KG' THEN i.QTDNEG ELSE 0 END) AS QTD_KG
                    FROM TGFITE i
                    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                    LEFT JOIN TGFPAR pr ON pr.CODPARC = c.CODPARC
                    LEFT JOIN TGFPRO pp ON pp.CODPROD = i.CODPROD
                    LEFT JOIN TGFVOA vcx ON vcx.CODPROD = i.CODPROD AND UPPER(vcx.CODVOL)='CX'
                    LEFT JOIN TGFVOA vio ON vio.CODPROD = i.CODPROD AND UPPER(vio.CODVOL) = UPPER(NVL(i.CODVOL,''))
                 WHERE i.CODAGREGACAO IN ({in_clause})
                     AND c.CODTIPOPER = :top_ent
                 GROUP BY i.CODAGREGACAO
        """
        cur.execute(sql_q, {**binds, 'top_ent': TOP_ENTRADA})
        for ctrl, parceiro, codparc, qcx, qkg in cur.fetchall():
            d = out.get(ctrl)
            if not d:
                continue
            d['parceiro'] = parceiro or ''
            try:
                d['codparc'] = int(codparc) if codparc is not None else None
            except Exception:
                d['codparc'] = codparc
            try:
                d['qtd_cx'] = float(qcx or 0)
            except Exception:
                d['qtd_cx'] = 0.0
            try:
                d['qtd_kg'] = float(qkg or 0)
            except Exception:
                d['qtd_kg'] = 0.0

        # Classifiable product list — return manufacturer (FABRICANTE)
        sql_p = (
            f"""
            SELECT i.CODAGREGACAO AS CTRL, i.CODPROD, MAX(UPPER(NVL(p.FABRICANTE,''))) AS FABRICANTE
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
              LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
             WHERE i.CODAGREGACAO IN ({in_clause})
               AND c.CODTIPOPER = :top_ent
             GROUP BY i.CODAGREGACAO, i.CODPROD
            """
        )
        cur.execute(sql_p, {**binds, 'top_ent': TOP_ENTRADA})
        for ctrl, cod, fabricante in cur.fetchall():
            d = out.get(ctrl)
            if not d:
                continue
            lst = d.setdefault('produtos_entrada', [])
            try:
                cod_i = int(cod) if cod is not None else None
            except Exception:
                cod_i = cod
            lst.append({'cod': cod_i, 'fabricante': fabricante or ''})

        # PESO do item de entrada (qualquer produto) para cada controle: usa qualquer PESO não nulo
        sql_pw = (
            f"""
            SELECT i.CODAGREGACAO AS CTRL, MAX(i.PESO) AS PESO
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO IN ({in_clause})
               AND c.CODTIPOPER = :top_ent
               AND i.PESO IS NOT NULL
             GROUP BY i.CODAGREGACAO
            """
        )
        cur.execute(sql_pw, {**binds, 'top_ent': TOP_ENTRADA})
        for ctrl, peso in cur.fetchall():
            d = out.get(ctrl)
            if not d:
                continue
            try:
                d['peso_inn'] = float(peso) if peso is not None else None
            except Exception:
                d['peso_inn'] = peso

        # TOP 26 (Classificação) status per controle:
        # Prefer 'L' if ANY classification note for that control is liberated; otherwise use any status available.
        sql_nc = (
            f"""
            SELECT i.CODAGREGACAO AS ctrl,
                   MAX(CASE WHEN c.STATUSNOTA = 'L' THEN 1 ELSE 0 END) AS has_l,
                   MAX(c.NUNOTA) AS nunota_any,
                   MAX(c.STATUSNOTA) AS status_any
              FROM TGFITE i
              JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
             WHERE i.CODAGREGACAO IN ({in_clause})
               AND c.CODTIPOPER = :top_class
             GROUP BY i.CODAGREGACAO
            """
        )
        cur.execute(sql_nc, {**binds, 'top_class': TOP_CLASS})
        for ctrl, has_l, nun_any, status_any in cur.fetchall():
            d = out.get(ctrl)
            if not d:
                continue
            d['nunota_class'] = nun_any
            try:
                hl = int(has_l or 0)
            except Exception:
                hl = 0
            if hl > 0:
                d['statusnota_class'] = 'L'
            else:
                try:
                    d['statusnota_class'] = (status_any or '').strip()
                except Exception:
                    d['statusnota_class'] = status_any

    return out


def listar_itens_sem_controle(limit: int = 50):
    """Lista itens de entrada (TOP 11, CODPROD 863) sem CODAGREGACAO definido."""
    TOP_ENTRADA = 11
    CODPROD_IN_NATURA = 863
    sql = (
        "SELECT c.NUNOTA, i.SEQUENCIA, c.CODPARC, i.CODPROD, i.QTDNEG, c.DTNEG "
        "FROM TGFITE i JOIN TGFCAB c ON c.NUNOTA=i.NUNOTA "
        "WHERE c.CODTIPOPER = :top AND i.CODPROD = :codprod "
    "AND (i.CODAGREGACAO IS NULL OR LENGTH(i.CODAGREGACAO)=0) "
        "ORDER BY c.DTNEG DESC"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, top=TOP_ENTRADA, codprod=CODPROD_IN_NATURA)
        rows = cur.fetchmany(limit)
    return rows


def gerar_controle_para_item(nunota: int, sequencia: int, data: str | None = None, commit: bool = False) -> str:
    """Gera e (opcionalmente) grava CONTROLE para um item específico de entrada.
    - Se data não informada, usa DTNEG do cabeçalho (TGFCAB).
    - commit=False: apenas mostra SQL/params (dry-run). commit=True: executa e faz commit.
    Retorna o CONTROLE gerado.
    """
    from datetime import datetime
    if data is None:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DTNEG FROM TGFCAB WHERE NUNOTA=:n", n=nunota)
            row = cur.fetchone()
            if not row:
                raise ValueError('NUNOTA não encontrado')
            dtneg = row[0]
            if isinstance(dtneg, datetime):
                data = dtneg.strftime('%Y-%m-%d')
            else:
                data = str(dtneg)[:10]
    controle = gerar_lote(data)
    # Se a coluna DTALTER existir, atualize também DTALTER=SYSDATE
    try:
        with get_connection() as _c:
            has_dtalter = 'DTALTER' in _get_table_columns(_c, 'TGFITE')
    except Exception:
        has_dtalter = False
    sql = "UPDATE TGFITE SET CODAGREGACAO=:c" + (", DTALTER=SYSDATE" if has_dtalter else "") + " WHERE NUNOTA=:n AND SEQUENCIA=:s"
    params = {'c': controle, 'n': nunota, 's': sequencia}
    if not commit:
        print('DRY-RUN SQL ->', sql)
        print('DRY-RUN BINDS ->', params)
        return controle
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, **params)
        conn.commit()
    return controle


def listar_lotes_portal(
    days: int = 7,
    limit: int = 50,
    codparc: int | None = None,
    codprod: int | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
):
    """Lista lotes/controles para Portal (apenas TOP 11 - Pedidos de Compra)."""
    from datetime import datetime, date as _date, timedelta
    
    def _to_date(val: str | _date | None):
        if val in (None, '', 'None', 'none', 'null'):
            return None
        if isinstance(val, _date):
            return val
        if isinstance(val, datetime):
            return val.date()
        try:
            return datetime.strptime(str(val), "%Y-%m-%d").date()
        except Exception:
            return None

    params = get_params()
    TOP_ENTRADA = params['TOP_ENTRADA']  # 11

    dtini = _to_date(date_start)
    dtfim = _to_date(date_end)
    
    if dtini is None and dtfim is None:
        dtini = (_date.today() - timedelta(days=days))
        dtfim = _date.today()

    where = ["c.CODTIPOPER = :top_entrada"]
    binds = {"top_entrada": TOP_ENTRADA}
    
    if dtini:
        where.append("c.DTNEG >= :dtini")
        binds["dtini"] = dtini
    if dtfim:
        where.append("c.DTNEG <= :dtfim")
        binds["dtfim"] = dtfim
    if codparc:
        where.append("c.CODPARC = :codparc")
        binds["codparc"] = codparc
    if codprod:
        where.append("i.CODPROD = :codprod")
        binds["codprod"] = codprod

    sql = (
        "SELECT DISTINCT i.CODAGREGACAO AS controle, "
        "       c.CODPARC, p.RAZAOSOCIAL, c.DTNEG, "
        "       COUNT(DISTINCT i.NUNOTA) AS notas, "
        "       COUNT(*) AS itens, "
        "       NVL(SUM(i.QTDNEG), 0) AS qtd_total "
        "FROM TGFITE i "
        "JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA "
        "LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC "
        f"WHERE {' AND '.join(where)} "
        "  AND i.CODAGREGACAO IS NOT NULL "
        "GROUP BY i.CODAGREGACAO, c.CODPARC, p.RAZAOSOCIAL, c.DTNEG "
        "ORDER BY c.DTNEG DESC, i.CODAGREGACAO DESC"
    )
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        return cur.fetchmany(limit)


def listar_lotes_classificacao(
    days: int = 7,
    limit: int = 50,
    codparc: int | None = None,
    codprod: int | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
):
    """Lista lotes/controles para Classificação (apenas TOP 26 - Classificação)."""
    from datetime import datetime, date as _date, timedelta
    
    def _to_date(val: str | _date | None):
        if val in (None, '', 'None', 'none', 'null'):
            return None
        if isinstance(val, _date):
            return val
        if isinstance(val, datetime):
            return val.date()
        try:
            return datetime.strptime(str(val), "%Y-%m-%d").date()
        except Exception:
            return None

    params = get_params()
    TOP_CLASS = params['TOP_CLASS']  # 26

    dtini = _to_date(date_start)
    dtfim = _to_date(date_end)
    
    if dtini is None and dtfim is None:
        dtini = (_date.today() - timedelta(days=days))
        dtfim = _date.today()

    where = ["c.CODTIPOPER = :top_class"]
    binds = {"top_class": TOP_CLASS}
    
    if dtini:
        where.append("c.DTNEG >= :dtini")
        binds["dtini"] = dtini
    if dtfim:
        where.append("c.DTNEG <= :dtfim")
        binds["dtfim"] = dtfim
    if codparc:
        where.append("c.CODPARC = :codparc")
        binds["codparc"] = codparc
    if codprod:
        where.append("i.CODPROD = :codprod")
        binds["codprod"] = codprod

    # Apply server-side row limiting with ROWNUM to avoid materializing the full grouped set
    inner = (
        "SELECT DISTINCT i.CODAGREGACAO AS controle, "
        "       c.NUNOTA, c.CODPARC, p.RAZAOSOCIAL, c.DTNEG, c.STATUSNOTA, "
        "       COUNT(*) AS itens, "
        "       NVL(SUM(i.QTDNEG), 0) AS qtd_classificada, "
        "       MAX(c.OBSERVACAO) AS obs "
        "FROM TGFITE i "
        "JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA "
        "LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC "
        f"WHERE {' AND '.join(where)} "
        "  AND i.CODAGREGACAO IS NOT NULL "
        "GROUP BY i.CODAGREGACAO, c.NUNOTA, c.CODPARC, p.RAZAOSOCIAL, c.DTNEG, c.STATUSNOTA "
        "ORDER BY c.DTNEG DESC, i.CODAGREGACAO DESC"
    )
    sql = f"SELECT * FROM ({inner}) WHERE ROWNUM <= :lim"
    binds['lim'] = int(limit or 50)

    import time
    t0 = time.perf_counter()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        rows = cur.fetchall()
        t1 = time.perf_counter()
        try:
            import logging
            logging.getLogger(__name__).info('[lotes_class] rows=%d ms=%d', len(rows), int((t1 - t0) * 1000))
        except Exception:
            pass
        return rows


def listar_produtos(limit: int = 50, offset: int = 0, nome: str | None = None):
    """Lista produtos (TGFPRO) de forma simples. Read-only."""
    where = ["1=1"]
    binds: dict[str, object] = {}
    if nome:
        where.append("UPPER(DESCRPROD) LIKE :nome")
        binds["nome"] = f"%{nome.upper()}%"
    sql = (
        "SELECT CODPROD, DESCRPROD "
        "FROM TGFPRO "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY CODPROD "
    )
    with get_connection() as conn:
        cur = conn.cursor()
        # Oracle: paginação simples via fetchmany após salto manual quando necessário
        cur.execute(sql, binds)
        # Pular offset manualmente
        if offset:
            for _ in range(offset):
                if cur.fetchone() is None:
                    return []
        rows = cur.fetchmany(limit)
        return rows


def listar_parceiros(limit: int = 50, offset: int = 0, nome: str | None = None):
    """Lista parceiros (TGFPAR) de forma simples. Read-only."""
    where = ["1=1"]
    binds: dict[str, object] = {}
    if nome:
        where.append("UPPER(NOMEPARC) LIKE :nome")
        binds["nome"] = f"%{nome.upper()}%"
    sql = (
        "SELECT CODPARC, NOMEPARC "
        "FROM TGFPAR "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY CODPARC "
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        if offset:
            for _ in range(offset):
                if cur.fetchone() is None:
                    return []
        rows = cur.fetchmany(limit)
        return rows


def listar_itens_portal_basico(
    days: int = 60,
    date_start: str | None = None,
    date_end: str | None = None,
    codparc: int | None = None,
    codprod: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Lista itens de TOP 11 (Portal) com colunas básicas para o painel Comercial.
    Retorna tuplas: (NOMEPARC, PRODNAME, QTDNEG, DTNEG, CODVOL, CODPROD, NUNOTA, SEQUENCIA, GP, PESO, PRECOBASE, VLRUNIT, VLRTOT, AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2)
    Suporta filtros por data, parceiro e produto, com paginação segura via ROW_NUMBER.
    """
    from datetime import datetime, date as _date

    def _to_date(val):
        if val in (None, '', 'None', 'none', 'null'):
            return None
        if isinstance(val, _date):
            return val
        if isinstance(val, datetime):
            return val.date()
        try:
            return datetime.strptime(str(val), "%Y-%m-%d").date()
        except Exception:
            return None

    p = get_params()
    TOP_ENTRADA = int(p['TOP_ENTRADA'])

    dtini = _to_date(date_start)
    dtfim = _to_date(date_end)

    where = ["c.CODTIPOPER = :top"]
    binds: dict[str, object] = {"top": TOP_ENTRADA}

    if dtini and dtfim:
        where.append("TRUNC(c.DTNEG) BETWEEN :dtini AND :dtfim")
        binds["dtini"], binds["dtfim"] = dtini, dtfim
    elif dtini:
        where.append("TRUNC(c.DTNEG) >= :dtini")
        binds["dtini"] = dtini
    elif dtfim:
        where.append("TRUNC(c.DTNEG) <= :dtfim")
        binds["dtfim"] = dtfim
    else:
        where.append("c.DTNEG >= SYSDATE - :days")
        binds["days"] = int(days or 60)

    if codparc is not None:
        where.append("c.CODPARC = :codparc")
        binds["codparc"] = int(codparc)
    if codprod is not None:
        where.append("i.CODPROD = :codprod")
        binds["codprod"] = int(codprod)

    inner = (
        "SELECT p.NOMEPARC, NVL(pr.FABRICANTE, pr.DESCRPROD) AS PRODNAME, i.QTDNEG, c.DTNEG, i.CODVOL, i.CODPROD, c.NUNOTA, i.SEQUENCIA, NVL(i.GERAPRODUCAO, 'S') AS GP, i.PESO AS PESO, i.PRECOBASE AS PRECOBASE, i.VLRUNIT AS VLRUNIT, i.VLRTOT AS VLRTOT, i.AD_SIMQTD1, i.AD_SIMQTD2, i.AD_SIMVLR1, i.AD_SIMVLR2 "
        "  FROM TGFITE i "
        "  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA "
        "  LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC "
        "  LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD "
        f" WHERE {' AND '.join(where)} "
        "  ORDER BY c.DTNEG DESC, c.NUNOTA DESC, i.SEQUENCIA ASC"
    )
    sql = (
        "SELECT NOMEPARC, PRODNAME, QTDNEG, DTNEG, CODVOL, CODPROD, NUNOTA, SEQUENCIA, GP, PESO, PRECOBASE, VLRUNIT, VLRTOT, AD_SIMQTD1, AD_SIMQTD2, AD_SIMVLR1, AD_SIMVLR2 FROM ("
        "  SELECT t.*, ROW_NUMBER() OVER (ORDER BY t.DTNEG DESC, t.NUNOTA DESC, t.SEQUENCIA ASC) rn FROM (" + inner + ") t"
        ") WHERE rn BETWEEN :start_row AND :end_row ORDER BY rn"
    )
    binds["start_row"] = int(offset) + 1
    binds["end_row"] = int(offset) + int(limit)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        return cur.fetchall()

def buscar_parceiros(q: str, limit: int = 10):
    """Busca parceiros por código (numérico) ou nome (LIKE), retornando tuplas (CODPARC, NOMEPARC).
    - Caso `q` seja numérico, filtra por `CODPARC LIKE 'q%'`.
    - Caso contrário, filtra por `NOMEPARC LIKE '%q%'` (case-insensitive).
    """
    if not q:
        return []
    import re
    q = str(q).strip()
    m = re.match(r"^(\d+)", q)
    by_code = bool(m)
    code_prefix = m.group(1) if m else None
    with get_connection() as conn:
        cur = conn.cursor()
        lim = max(1, int(limit))
        if by_code and code_prefix:
            # Definitivo: exato primeiro (prio=0), depois prefixos (prio=1)
            qprefix = f"{code_prefix}%"
            qpad = code_prefix.zfill(9) + "%"
            try:
                k = int(code_prefix)
            except Exception:
                k = None
            sql = (
                "SELECT CODPARC, NOMEPARC FROM ("
                "  SELECT CODPARC, NOMEPARC FROM ("
                "    SELECT CODPARC, NOMEPARC, 0 AS PRIO FROM TGFPAR WHERE (:k IS NOT NULL AND CODPARC = :k)"
                "    UNION ALL "
                "    SELECT CODPARC, NOMEPARC, 1 AS PRIO FROM TGFPAR "
                "     WHERE (TO_CHAR(CODPARC) LIKE :qprefix OR LPAD(TO_CHAR(CODPARC), 9, '0') LIKE :qpad) "
                "       AND (:k IS NULL OR CODPARC <> :k)"
                "  ) t ORDER BY PRIO, CODPARC"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, k=k, qprefix=qprefix, qpad=qpad, lim=lim)
        else:
            sql = (
                "SELECT CODPARC, NOMEPARC FROM ("
                "  SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE UPPER(NOMEPARC) LIKE :q ORDER BY NOMEPARC"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, q=f"%{q.upper()}%", lim=lim)
        return cur.fetchall()


def listar_notas_compra(
    days: int = 7,
    date_start: str | None = None,
    date_end: str | None = None,
    nronota_ini: str | None = None,
    nronota_fim: str | None = None,
    nunota_ini: int | None = None,
    nunota_fim: int | None = None,
    codparc: int | None = None,
    codprod: int | None = None,
    controle: str | None = None,
    tops: list[int] | None = None,
    sort: str | None = None,
    dir: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Lista notas (TGFCAB) com total de itens, com paginação via ROW_NUMBER.
    - Usa NUMNOTA (número do documento) e NUNOTA (número único).
    - Filtros opcionais adicionais: produto (i.CODPROD) e lote/controle (i.CODAGREGACAO).
    """
    from datetime import datetime, date as _date

    def _to_date(val):
        if val in (None, '', 'None', 'none', 'null'):
            return None
        if isinstance(val, _date):
            return val
        if isinstance(val, datetime):
            return val.date()
        try:
            return datetime.strptime(str(val), "%Y-%m-%d").date()
        except Exception:
            return None

    def _clean_doc(v):
        if v in (None, '', 'None', 'none', 'null'):
            return None
        s = str(v).strip()
        return s if s.isdigit() else None

    nronota_ini = _clean_doc(nronota_ini)
    nronota_fim = _clean_doc(nronota_fim)

    dtini = _to_date(date_start)
    dtfim = _to_date(date_end)

    p = get_params()
    default_top = [p['TOP_ENTRADA']]
    tops_list = [int(t) for t in (tops or default_top)]
    tops_sql = ",".join(str(t) for t in tops_list)

    where = ["1=1", f"c.CODTIPOPER IN ({tops_sql})"]
    binds: dict[str, object] = {}

    if dtini and dtfim:
        where.append("TRUNC(c.DTNEG) BETWEEN :dtini AND :dtfim")
        binds["dtini"] = dtini
        binds["dtfim"] = dtfim
    elif dtini:
        where.append("TRUNC(c.DTNEG) >= :dtini")
        binds["dtini"] = dtini
    elif dtfim:
        where.append("TRUNC(c.DTNEG) <= :dtfim")
        binds["dtfim"] = dtfim
    else:
        where.append("c.DTNEG >= SYSDATE - :days")
        binds["days"] = days

    if nronota_ini and nronota_fim:
        where.append("c.NUMNOTA BETWEEN :num_ini AND :num_fim")
        binds["num_ini"] = nronota_ini
        binds["num_fim"] = nronota_fim
    elif nronota_ini:
        where.append("c.NUMNOTA >= :num_ini")
        binds["num_ini"] = nronota_ini
    elif nronota_fim:
        where.append("c.NUMNOTA <= :num_fim")
        binds["num_fim"] = nronota_fim

    if nunota_ini and nunota_fim:
        where.append("c.NUNOTA BETWEEN :nunota_ini AND :nunota_fim")
        binds["nunota_ini"] = nunota_ini
        binds["nunota_fim"] = nunota_fim
    elif nunota_ini:
        where.append("c.NUNOTA >= :nunota_ini")
        binds["nunota_ini"] = nunota_ini
    elif nunota_fim:
        where.append("c.NUNOTA <= :nunota_fim")
        binds["nunota_fim"] = nunota_fim

    if codparc is not None:
        where.append("c.CODPARC = :codparc")
        binds["codparc"] = codparc

    # Filtros opcionais por item
    if codprod is not None:
        where.append("i.CODPROD = :codprod")
        binds["codprod"] = codprod
    if controle:
        where.append("i.CODAGREGACAO = :controle")
        binds["controle"] = controle

    inner_sql = (
        "SELECT c.NUNOTA, c.NUMNOTA, c.DTNEG, c.CODPARC, p.NOMEPARC, NVL(SUM(i.VLRTOT),0) VLRTOTAL "
        "  FROM TGFCAB c "
        "  LEFT JOIN TGFITE i ON i.NUNOTA = c.NUNOTA "
        "  LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC "
        f" WHERE {' AND '.join(where)} "
        " GROUP BY c.NUNOTA, c.NUMNOTA, c.DTNEG, c.CODPARC, p.NOMEPARC"
    )

    # Ordenação segura via whitelist
    sort_key = (sort or 'dtneg').lower()
    dir_key = (dir or 'desc').lower()
    dir_sql = 'DESC' if dir_key not in ('asc', 'desc') else dir_key.upper()
    sort_map = {
        'nunota': 't.NUNOTA',
        'nronota': 't.NUMNOTA',
        'dtneg': 't.DTNEG',
        'parceiro': 't.NOMEPARC',
        'valor': 't.VLRTOTAL',
    }
    sort_col = sort_map.get(sort_key, 't.DTNEG')
    order_expr = f"{sort_col} {dir_sql}, t.NUNOTA DESC"

    sql = (
        "SELECT NUNOTA, NUMNOTA, DTNEG, CODPARC, NOMEPARC, VLRTOTAL FROM ("
        f" SELECT t.*, ROW_NUMBER() OVER (ORDER BY {order_expr}) rn FROM (" + inner_sql + ") t"
        ") WHERE rn BETWEEN :start_row AND :end_row ORDER BY rn"
    )

    binds["start_row"] = int(offset) + 1
    binds["end_row"] = int(offset) + int(limit)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        rows = cur.fetchall()
        return rows


def listar_itens_da_nota(nunota: int):
    """Retorna itens de uma nota (somente leitura) nos campos essenciais para rodapé/edição."""
    sql = (
        "SELECT i.CODAGREGACAO, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, i.PESO, i.VLRUNIT, i.VLRTOT, i.OBSERVACAO, i.GERAPRODUCAO "
        "  FROM TGFITE i "
        "  LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD "
        " WHERE i.NUNOTA = :nunota "
        " ORDER BY i.SEQUENCIA"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, nunota=nunota)
        return cur.fetchall()


def get_base_unit_and_factor(codprod: int, codvol: str) -> tuple[str | None, float | None]:
    """Obtem a unidade base do produto (TGFPRO.CODVOL) e o fator de conversão para a unidade informada (TGFVOA).

    Convenção: fator representa quantas unidades base existem em UMA unidade alternativa.
    Ex.: produto base = KG e alterna = CX(22KG) -> fator = 22 (1 CX = 22 KG).

    Retorna: (codvol_base, fator) — se não houver mapeamento, fator=None.
    """
    if codprod in (None, "", 0) or not codvol:
        return None, None
    try:
        codvol_u = str(codvol).strip().upper()
    except Exception:
        codvol_u = None
    base = None
    fator = None
    # Fast path: cached base for product and factor for (product, unit)
    try:
        if codprod and isinstance(codprod, int):
            if codprod in _BASE_UNIT_CACHE:
                base = _BASE_UNIT_CACHE[codprod]
        key = (int(codprod or 0), codvol_u or '')
        if key in _FACTOR_CACHE:
            return (base or _BASE_UNIT_CACHE.get(key[0]) or None, _FACTOR_CACHE[key])
    except Exception:
        pass
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Base unit from TGFPRO
            try:
                cur.execute("SELECT CODVOL FROM TGFPRO WHERE CODPROD=:p", p=int(codprod))
                row = cur.fetchone()
                if row and row[0]:
                    base = str(row[0]).strip().upper()
                    _BASE_UNIT_CACHE[int(codprod)] = base
            except Exception:
                base = None
            # If requested unit equals base, factor is 1.0 (no conversion needed)
            if base and codvol_u and base == codvol_u:
                return base, 1.0
            # Alternative volume factor from TGFVOA (Volumes Alternativos)
            # Try legacy/common column FATOR first; fallback to QUANTIDADE+DIVIDEMULTIPLICA.
            try:
                cur.execute(
                    "SELECT FATOR FROM TGFVOA WHERE CODPROD=:p AND UPPER(CODVOL)=:v",
                    p=int(codprod), v=codvol_u or ""
                )
                row2 = cur.fetchone()
                if row2 and row2[0] is not None:
                    try:
                        fator_val = float(row2[0])
                        if fator_val > 0:
                            fator = fator_val
                    except Exception:
                        fator = None
            except Exception:
                fator = None
            # Fallback: QUANTIDADE (numeric) + DIVIDEMULTIPLICA ('M' multiplica, 'D' divide)
            if fator is None:
                try:
                    cur.execute(
                        "SELECT QUANTIDADE, DIVIDEMULTIPLICA FROM TGFVOA WHERE CODPROD=:p AND UPPER(CODVOL)=:v",
                        p=int(codprod), v=codvol_u or ""
                    )
                    row3 = cur.fetchone()
                    if row3 and row3[0] is not None:
                        try:
                            qtd = float(row3[0])
                        except Exception:
                            qtd = None
                        dv = (str(row3[1]).strip().upper() if row3[1] is not None else 'M')
                        if qtd and qtd > 0:
                            if dv == 'M':
                                # 1 alt = qtd base => base = alt * qtd
                                fator = qtd
                            elif dv == 'D':
                                # base = alt / qtd => 1 alt = 1/qtd base
                                try:
                                    fator = 1.0 / qtd if qtd != 0 else None
                                except Exception:
                                    fator = None
                except Exception:
                    pass
        # Cache factor result (including None to avoid re-querying)
        try:
            _FACTOR_CACHE[(int(codprod or 0), codvol_u or '')] = fator
        except Exception:
            pass
    except Exception:
        # On any connection error, return safe fallbacks
        return base, fator
    return base, fator


def fetch_tgfvoa_details(codprod: int, codvol: str) -> dict:
    """Diagnóstico: retorna lista de colunas de TGFVOA e os valores da linha para (CODPROD, CODVOL).
    Útil para identificar qual coluna armazena o fator de conversão nesta base.
    """
    out = {
        'ok': False,
        'codprod': codprod,
        'codvol': codvol,
        'columns': [],
        'row': [],
        'error': None,
    }
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Get column names ordered by column_id
            try:
                cur.execute("""
                    SELECT column_name FROM user_tab_cols
                    WHERE table_name='TGFVOA' ORDER BY column_id
                """)
                cols = [r[0] for r in cur.fetchall()]
                out['columns'] = cols
            except Exception:
                out['columns'] = []
            # Fetch a row for the given key
            try:
                cur.execute(
                    "SELECT * FROM TGFVOA WHERE CODPROD=:p AND UPPER(CODVOL)=:v",
                    p=int(codprod), v=str(codvol or '').upper()
                )
                row = cur.fetchone()
                if row:
                    out['row'] = list(row)
                    out['ok'] = True
                else:
                    out['ok'] = True
            except Exception as e:
                out['error'] = str(e)
    except Exception as e:
        out['error'] = str(e)
    return out


def fetch_tgfite_details(nunota: int, codprods: list[int]) -> dict:
    """Retorna diagnóstico de TGFITE para uma nota: lista de colunas e linhas para os CODPRODs informados.
    Saída: { ok, columns:[...], rows:[...], order:['CODPROD','SEQUENCIA',...], error }
    """
    res = { 'ok': False, 'columns': [], 'rows': [], 'error': None }
    if not nunota or not codprods:
        res['error'] = 'Parâmetros inválidos'
        return res
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Descobrir colunas em ordem física
            cur.execute(
                "SELECT column_name FROM user_tab_cols WHERE table_name='TGFITE' ORDER BY column_id"
            )
            cols = [r[0] for r in cur.fetchall()]
            res['columns'] = cols
            # Montar SELECT explícito com todas as colunas, para garantir a ordem
            col_list = ', '.join(cols)
            # IN dinâmico com binds
            binds = { 'n': int(nunota) }
            in_placeholders = []
            for idx, cp in enumerate(codprods):
                key = f'p{idx}'
                in_placeholders.append(f':{key}')
                binds[key] = int(cp)
            in_sql = ', '.join(in_placeholders) if in_placeholders else 'NULL'
            sql = (
                f"SELECT {col_list} FROM TGFITE WHERE NUNOTA=:n AND CODPROD IN ({in_sql}) "
                "ORDER BY CODPROD, SEQUENCIA"
            )
            cur.execute(sql, binds)
            res['rows'] = [tuple(r) for r in cur.fetchall()]
            res['ok'] = True
            return res
    except Exception as e:
        res['error'] = str(e)
        return res


def buscar_top_operacoes(q: str, limit: int = 10):
    if not q:
        return []
    lim = max(1, int(limit))
    q = str(q).strip()
    by_code = q.isdigit()
    with get_connection() as conn:
        cur = conn.cursor()
        if by_code:
            k = int(q)
            qprefix = f"{q}%"
            sql = (
                "SELECT CODTIPOPER, DESCROPER FROM ("
                "  SELECT CODTIPOPER, DESCROPER FROM ("
                "    SELECT DISTINCT CODTIPOPER, UPPER(DESCROPER) DESCROPER, 0 PRIO FROM TGFTOP WHERE CODTIPOPER = :k"
                "    UNION ALL "
                "    SELECT DISTINCT CODTIPOPER, UPPER(DESCROPER) DESCROPER, 1 PRIO FROM TGFTOP WHERE TO_CHAR(CODTIPOPER) LIKE :qprefix AND CODTIPOPER <> :k"
                "  ) t ORDER BY PRIO, CODTIPOPER"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, k=k, qprefix=qprefix, lim=lim)
        else:
            sql = (
                "SELECT CODTIPOPER, DESCROPER FROM ("
                "  SELECT CODTIPOPER, DESCROPER FROM ("
                "    SELECT DISTINCT CODTIPOPER, UPPER(DESCROPER) DESCROPER FROM TGFTOP WHERE UPPER(DESCROPER) LIKE :q"
                "  ) ORDER BY DESCROPER"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, q=f"%{q.upper()}%", lim=lim)
        return cur.fetchall()


def buscar_naturezas(q: str, limit: int = 10):
    if not q:
        return []
    lim = max(1, int(limit))
    q = str(q).strip()
    by_code = q.isdigit()
    with get_connection() as conn:
        cur = conn.cursor()
        if by_code:
            k = int(q)
            qprefix = f"{q}%"
            sql = (
                "SELECT CODNAT, DESCRNAT FROM ("
                "  SELECT CODNAT, DESCRNAT FROM ("
                "    SELECT DISTINCT CODNAT, UPPER(DESCRNAT) DESCRNAT, 0 PRIO FROM TGFNAT WHERE CODNAT = :k"
                "    UNION ALL "
                "    SELECT DISTINCT CODNAT, UPPER(DESCRNAT) DESCRNAT, 1 PRIO FROM TGFNAT WHERE TO_CHAR(CODNAT) LIKE :qprefix AND CODNAT <> :k"
                "  ) t ORDER BY PRIO, CODNAT"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, k=k, qprefix=qprefix, lim=lim)
        else:
            sql = (
                "SELECT CODNAT, DESCRNAT FROM ("
                "  SELECT CODNAT, DESCRNAT FROM ("
                "    SELECT DISTINCT CODNAT, UPPER(DESCRNAT) DESCRNAT FROM TGFNAT WHERE UPPER(DESCRNAT) LIKE :q"
                "  ) ORDER BY DESCRNAT"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, q=f"%{q.upper()}%", lim=lim)
        return cur.fetchall()


def buscar_centros_resultado(q: str, limit: int = 10):
    if not q:
        return []
    lim = max(1, int(limit))
    q = str(q).strip()
    by_code = q.isdigit()
    with get_connection() as conn:
        cur = conn.cursor()
        if by_code:
            k = int(q)
            qprefix = f"{q}%"
            sql = (
                "SELECT CODCENCUS, DESCRCENCUS FROM ("
                "  SELECT CODCENCUS, DESCRCENCUS FROM ("
                "    SELECT DISTINCT CODCENCUS, UPPER(DESCRCENCUS) DESCRCENCUS, 0 PRIO FROM TSICUS WHERE CODCENCUS = :k"
                "    UNION ALL "
                "    SELECT DISTINCT CODCENCUS, UPPER(DESCRCENCUS) DESCRCENCUS, 1 PRIO FROM TSICUS WHERE TO_CHAR(CODCENCUS) LIKE :qprefix AND CODCENCUS <> :k"
                "  ) t ORDER BY PRIO, CODCENCUS"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, k=k, qprefix=qprefix, lim=lim)
        else:
            sql = (
                "SELECT CODCENCUS, DESCRCENCUS FROM ("
                "  SELECT CODCENCUS, DESCRCENCUS FROM ("
                "    SELECT DISTINCT CODCENCUS, UPPER(DESCRCENCUS) DESCRCENCUS FROM TSICUS WHERE UPPER(DESCRCENCUS) LIKE :q"
                "  ) ORDER BY DESCRCENCUS"
                ") WHERE ROWNUM <= :lim"
            )
            cur.execute(sql, q=f"%{q.upper()}%", lim=lim)
        return cur.fetchall()


def obter_cabecalho_nota(nunota: int) -> dict | None:
    """Retorna campos básicos do cabeçalho da nota (somente leitura).
    Campos: CODEMP, NOMEFANTASIA_EMP, NUMNOTA, DTNEG, CODPARC, NOMEPARC, CODTIPOPER, DESCROPER, CODNAT, DESCRNAT, CODCENCUS, DESCRCENCUS, OBSERVACAO.
    """
    sql = (
        "SELECT c.CODEMP, emp.NOMEFANTASIA, c.NUMNOTA, c.DTNEG, c.CODPARC, p.NOMEPARC, "
        "       c.CODTIPOPER, top.DESCROPER, c.CODNAT, nat.DESCRNAT, c.CODCENCUS, cus.DESCRCENCUS, c.OBSERVACAO "
        "  FROM TGFCAB c "
        "  LEFT JOIN TSIEMP emp ON emp.CODEMP = c.CODEMP "
        "  LEFT JOIN TGFPAR p   ON p.CODPARC   = c.CODPARC "
        "  LEFT JOIN TGFTOP top ON top.CODTIPOPER = c.CODTIPOPER "
        "  LEFT JOIN TGFNAT nat ON nat.CODNAT  = c.CODNAT "
        "  LEFT JOIN TSICUS cus ON cus.CODCENCUS = c.CODCENCUS "
        " WHERE c.NUNOTA = :nunota"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, nunota=nunota)
        row = cur.fetchone()
        if not row:
            return None
        return {
            'CODEMP': row[0],
            'NOMEFANTASIA_EMP': row[1],
            'NUMNOTA': row[2],
            'DTNEG': row[3],
            'CODPARC': row[4],
            'NOMEPARC': row[5],
            'CODTIPOPER': row[6],
            'DESCROPER': row[7],
            'CODNAT': row[8],
            'DESCRNAT': row[9],
            'CODCENCUS': row[10],
            'DESCRCENCUS': row[11],
            'OBSERVACAO': row[12],
        }


def delete_itens(nunota: int, sequencias: list[int], dry_run: bool = True) -> dict:
    """Apaga itens pelo par (NUNOTA, SEQUENCIA). Respeita triggers de exclusão (AFTER DELETE em TGFITE).
    Retorna resumo com contagem e mensagens de erro, se houver.
    """
    res = {
        'ok': False,
        'executed': False,
        'nunota': nunota,
        'sequencias': sequencias,
        'deleted': 0,
        'errors': [],
        'warnings': [],
    }
    if not isinstance(sequencias, list) or not sequencias:
        res['errors'].append('Nenhuma sequência informada')
        return res
    try:
        nun = int(nunota)
        seqs = [int(s) for s in sequencias]
    except Exception:
        res['errors'].append('Parâmetros inválidos')
        return res
    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            res['warnings'].append('Escrita desabilitada por política — execução em modo simulado')
        res['ok'] = True
        return res
    with get_connection() as conn:
        try:
            cur = conn.cursor()
            count = 0
            results: list[dict] = []
            # Deleta em ordem decrescente de SEQUENCIA para reduzir dependências
            for s in sorted(seqs, reverse=True):
                try:
                    cur.execute("DELETE FROM TGFITE WHERE NUNOTA=:n AND SEQUENCIA=:s", n=nun, s=s)
                    affected = cur.rowcount or 0
                    count += affected
                    # Commit por item para garantir persistência mesmo com falhas posteriores
                    conn.commit()
                    results.append({'sequencia': s, 'deleted': affected, 'ok': affected > 0})
                except cx_Oracle.DatabaseError as e:
                    try:
                        err, = e.args
                        msg = getattr(err, 'message', str(e))
                        res['errors'].append(msg)
                        results.append({'sequencia': s, 'deleted': 0, 'ok': False, 'error': msg})
                    except Exception:
                        m = str(e)
                        res['errors'].append(m)
                        results.append({'sequencia': s, 'deleted': 0, 'ok': False, 'error': m})
                except Exception as e:
                    m = str(e)
                    res['errors'].append(m)
                    results.append({'sequencia': s, 'deleted': 0, 'ok': False, 'error': m})
            res['deleted'] = count
            res['results'] = results
            # Considera executado se houve ao menos uma exclusão
            res['executed'] = (count > 0)
            res['partial'] = (count > 0 and len(res['errors']) > 0)
            res['ok'] = True
            return res
        except cx_Oracle.DatabaseError as e:
            try:
                err, = e.args
                res['errors'].append(getattr(err, 'message', str(e)))
            except Exception:
                res['errors'].append(str(e))
            res['executed'] = False
            return res


def duplicate_item(nunota: int, sequencia: int, dry_run: bool = True) -> dict:
    """Duplica um item da nota: copia campos essenciais e insere novo item com CODAGREGACAO novo.
    - Copia CODPROD, CODVOL, QTDNEG, VLRUNIT, CODLOCALORIG, OBSERVACAO.
    - Gera CODAGREGACAO pelo DTNEG do cabeçalho (garantindo unicidade) e SEQUENCIA nova.
    """
    res = {
        'ok': False,
        'executed': False,
        'nunota': nunota,
        'sequencia_origem': sequencia,
        'sequencia_nova': None,
        'errors': [],
        'warnings': [],
    }
    try:
        nun = int(nunota)
        seq = int(sequencia)
    except Exception:
        res['errors'].append('Parâmetros inválidos')
        return res
    with get_connection() as conn:
        cur = conn.cursor()
        # Carregar item origem e dados do cabeçalho
        cur.execute(
            "SELECT i.CODPROD, i.CODVOL, i.QTDNEG, i.VLRUNIT, i.CODLOCALORIG, i.OBSERVACAO, c.DTNEG, c.CODEMP "
            "  FROM TGFITE i JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA "
            " WHERE i.NUNOTA = :n AND i.SEQUENCIA = :s",
            n=nun, s=seq
        )
        row = cur.fetchone()
        if not row:
            res['errors'].append('Item não encontrado')
            return res
        codprod, codvol, qtdneg, vlrunit, codlocal, obs, dtneg, codemp = row
    # Gerar novo codagregacao via gerar_lote(dtneg)
    try:
        new_ctrl = gerar_lote(dtneg)
    except Exception as e:
        res['errors'].append(f'Falha ao gerar CODAGREGACAO: {e}')
        return res
    # Calcular nova sequência
    try:
        new_seq = obter_proxima_sequencia(nun)
    except Exception:
        new_seq = 1
        res['warnings'].append('Não foi possível calcular SEQUENCIA; usando 1')
    vlrtot = None
    try:
        vlrtot = round(float(qtdneg) * float(vlrunit), 2)
    except Exception:
        pass
    insert_sql = build_insert_item_sql()
    binds = {
        'NUNOTA': nun,
        'SEQUENCIA': new_seq,
        'CODEMP': codemp,
        'CODPROD': int(codprod),
        'QTDNEG': float(qtdneg),
        'VLRUNIT': float(vlrunit),
        'VLRTOT': vlrtot,
        'CODVOL': (codvol or 'UN'),
        'CODLOCALORIG': int(codlocal or 101),
        'CODAGREGACAO': new_ctrl,
        'OBSERVACAO': obs,
    }
    res['plan'] = {'sql': insert_sql, 'binds': binds}
    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            res['warnings'].append('Escrita desabilitada por política — execução em modo simulado')
        res['ok'] = True
        res['sequencia_nova'] = new_seq
        return res
    try:
        with get_connection() as conn2:
            cur2 = conn2.cursor()
            cur2.execute(insert_sql, binds)
            conn2.commit()
        res['ok'] = True
        res['executed'] = True
        res['sequencia_nova'] = new_seq
        res['controle_novo'] = new_ctrl
        return res
    except cx_Oracle.DatabaseError as e:
        try:
            err, = e.args
            res['errors'].append(getattr(err, 'message', str(e)))
        except Exception:
            res['errors'].append(str(e))
        res['executed'] = False
        return res



def diagnose_nota_delete(nunota: int) -> dict:
    """Diagnostica possíveis bloqueios para exclusão de uma nota.
    - Conta itens em TGFITE
    - Identifica e conta referências por FK a TGFCAB (por NUNOTA)
    - Identifica FKs que referenciam TGFITE e estima contagens por NUNOTA
    """
    out = {
        'nunota': nunota,
        'itens_count': 0,
        'fk_refs_to_cab': [],  # [{table, column, count}]
        'fk_refs_to_ite_by_nunota': [],  # approx counts per table
    }
    try:
        nun = int(nunota)
    except Exception:
        out['error'] = 'NUNOTA inválido'
        return out
    with get_connection() as conn:
        cur = conn.cursor()
        # Itens da nota
        try:
            cur.execute("SELECT COUNT(1) FROM TGFITE WHERE NUNOTA=:n", n=nun)
            (c_itens,) = cur.fetchone()
            out['itens_count'] = int(c_itens or 0)
        except Exception:
            out['itens_count'] = None
        # FKs -> TGFCAB (por NUNOTA)
        try:
            cur.execute(
                """
                SELECT a.table_name, acc.column_name
                  FROM user_constraints c
                  JOIN user_constraints a ON a.r_constraint_name = c.constraint_name AND a.constraint_type='R'
                  JOIN user_cons_columns acc ON acc.constraint_name = a.constraint_name
                 WHERE c.table_name = 'TGFCAB' AND c.constraint_type = 'P'
                """
            )
            rows = cur.fetchall()
            seen = set()
            for tbl, col in rows:
                key = (str(tbl).upper(), str(col).upper())
                if key in seen:  # evitar duplicados quando PK tem múltiplas colunas (não é o caso usual aqui)
                    continue
                seen.add(key)
                if str(col).upper() != 'NUNOTA':
                    continue
                try:
                    cur.execute(f"SELECT COUNT(1) FROM {tbl} WHERE {col}=:n", n=nun)
                    (cnt,) = cur.fetchone()
                    out['fk_refs_to_cab'].append({'table': str(tbl), 'column': str(col), 'count': int(cnt or 0)})
                except Exception:
                    out['fk_refs_to_cab'].append({'table': str(tbl), 'column': str(col), 'count': None})
        except Exception:
            pass
        # FKs -> TGFITE (aproximação por NUNOTA)
        try:
            # Descobrir PK de TGFITE (normalmente NUNOTA+SEQUENCIA)
            cur.execute("SELECT constraint_name FROM user_constraints WHERE table_name='TGFITE' AND constraint_type='P'")
            row_pk = cur.fetchone()
            if row_pk and row_pk[0]:
                pk_name = row_pk[0]
                cur.execute(
                    """
                    SELECT a.table_name, acc.column_name
                      FROM user_constraints a
                      JOIN user_cons_columns acc ON acc.constraint_name = a.constraint_name
                     WHERE a.constraint_type='R' AND a.r_constraint_name = :pk
                    """,
                    pk=pk_name
                )
                rows2 = cur.fetchall()
                grouped = {}
                for tbl, col in rows2:
                    tblu = str(tbl).upper(); colu = str(col).upper()
                    if tblu not in grouped:
                        grouped[tblu] = set()
                    grouped[tblu].add(colu)
                for tblu, cols in grouped.items():
                    if 'NUNOTA' in cols:
                        try:
                            cur.execute(f"SELECT COUNT(1) FROM {tblu} WHERE NUNOTA=:n", n=nun)
                            (cnt2,) = cur.fetchone()
                            out['fk_refs_to_ite_by_nunota'].append({'table': tblu, 'column': 'NUNOTA', 'count': int(cnt2 or 0)})
                        except Exception:
                            out['fk_refs_to_ite_by_nunota'].append({'table': tblu, 'column': 'NUNOTA', 'count': None})
        except Exception:
            pass
    return out

def _carregar_item_origem(nunota: int, sequencia: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
                """
                SELECT i.CODPROD, p.DESCRPROD, i.QTDNEG, i.CODVOL, i.CODAGREGACAO,
                       c.CODEMP, c.CODPARC, c.DTNEG, c.DTMOV, c.DTENTSAI,
                       c.CODTIPOPER, c.DHTIPOPER, c.CODNAT, c.CODCENCUS
                  FROM TGFITE i
                  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                  LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD
                 WHERE i.NUNOTA=:n AND i.SEQUENCIA=:s
                """,
                n=nunota, s=sequencia
            )
        return cur.fetchone()

def plan_classificacao(nunota_origem: int, sequencia_origem: int, saidas: list[dict], nunota_dest: int|None = None) -> dict:
    """Valida e planeja a classificação/beneficiamento a partir de um item de origem.
    Returns: { ok, errors[], warnings[], origem:{...}, totals:{origem, saidas, saldo}, plano:{cabecalho?, itens[]} }
    """
    res = { 'ok': False, 'errors': [], 'warnings': [], 'origem': None, 'totals': {}, 'plano': {} }
    try:
        n = int(nunota_origem); s = int(sequencia_origem)
    except Exception:
        res['errors'].append('Parâmetros de origem inválidos')
        return res
    row = _carregar_item_origem(n, s)
    if not row:
        res['errors'].append('Item de origem não encontrado')
        return res
    (codprod_o, descr_o, qtd_o, codvol_o, codag_o,
     codemp_o, codparc_o, dtneg_o, dtmov_o, dtentsai_o,
     codtop_o, dhtop_o, codnat_o, codcencus_o) = row
    if not codag_o:
        res['warnings'].append('Item de origem sem CODAGREGACAO — prosseguindo mesmo assim')
    # Validar saídas
    out_total = 0.0
    itens_plan = []
    if not isinstance(saidas, list) or not saidas:
        res['errors'].append('Informe ao menos uma saída')
        return res
    with get_connection() as conn:
        cur = conn.cursor()
        for idx, it in enumerate(saidas, start=1):
            try:
                cp = int(it.get('codprod'))
            except Exception:
                res['errors'].append(f'Linha {idx}: CODPROD inválido')
                continue
            try:
                qtd = float(it.get('qtd'))
            except Exception:
                res['errors'].append(f'Linha {idx}: quantidade inválida')
                continue
            if qtd <= 0:
                res['errors'].append(f'Linha {idx}: quantidade deve ser > 0')
                continue
            cv = (it.get('codvol') or codvol_o or 'KG')
            # Validar produto
            try:
                cur.execute("SELECT 1 FROM TGFPRO WHERE CODPROD=:p", p=cp)
                if cur.fetchone() is None:
                    res['errors'].append(f'Linha {idx}: produto {cp} inexistente')
            except Exception:
                pass
            # Validar unidade
            try:
                cur.execute("SELECT 1 FROM TGFVOL WHERE UPPER(CODVOL)=:v", v=str(cv).upper())
                if cur.fetchone() is None:
                    res['errors'].append(f'Linha {idx}: unidade {cv} inexistente')
            except Exception:
                pass
            out_total += qtd
            itens_plan.append({
                'CODPROD': cp,
                'QTDNEG': qtd,
                'CODVOL': str(cv).upper(),
                'CODLOCALORIG': 101,
                'CODAGREGACAO': codag_o,
                'VLRUNIT': 0.0,
                'OBSERVACAO': (it.get('obs') or None),
            })
    try:
        origem_val = float(qtd_o)
    except Exception:
        origem_val = None
    # Allow outputs to exceed origin: convert previous hard error into a warning
    if origem_val is not None and out_total > origem_val + 1e-9:
        excesso = out_total - origem_val
        res['warnings'].append(f'Saídas excedem a quantidade de origem (excesso: {excesso})')
    saldo = None
    if origem_val is not None:
        saldo = round(origem_val - out_total, 9)
        if saldo > 0:
            res['warnings'].append(f'Perda/Saldo não classificado: {saldo}')
    # Se não informado nunota_dest, tentar detectar nota 26 existente por item do mesmo controle
    if nunota_dest is None:
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT i.NUNOTA FROM TGFITE i
                      JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                     WHERE i.CODAGREGACAO = :ctrl AND c.CODTIPOPER = :top
                       AND ROWNUM = 1
                    """,
                    ctrl=codag_o, top=get_params()['TOP_CLASS']
                )
                row_exist = cur.fetchone()
                if row_exist and row_exist[0]:
                    nunota_dest = int(row_exist[0])
        except Exception:
            pass

    # Preparar plano de cabeçalho (se for criar nova nota)
    cab_plan = None
    if nunota_dest is None:
        def _fmt_date(d):
            try:
                return d.strftime('%d/%m/%Y')
            except Exception:
                s = str(d)[:10]
                return f"{s[8:10]}/{s[5:7]}/{s[0:4]}" if len(s) == 10 else None
        cab_plan = {
            'CODEMP': int(codemp_o),
            'CODPARC': int(codparc_o),
            'CODTIPOPER': int(get_params()['TOP_CLASS']),
            'CODNAT': int(codnat_o) if codnat_o is not None else None,
            'CODCENCUS': int(codcencus_o) if codcencus_o is not None else None,
            'DTNEG': _fmt_date(dtneg_o),
            'DTMOV': _fmt_date(dtmov_o) or _fmt_date(dtneg_o),
            'DTENTSAI': _fmt_date(dtentsai_o) or _fmt_date(dtneg_o),
            'HRMOV': None,
            'NUMNOTA': None,
            'OBSERVACAO': None,
        }
    res['origem'] = {
        'NUNOTA': n, 'SEQUENCIA': s, 'CODPROD': int(codprod_o), 'DESCRPROD': descr_o,
        'QTDNEG': float(qtd_o), 'CODVOL': codvol_o, 'CODAGREGACAO': codag_o,
        'CODEMP': int(codemp_o), 'CODPARC': int(codparc_o)
    }
    res['totals'] = { 'origem': origem_val, 'saidas': out_total, 'saldo': saldo }
    res['plano'] = { 'cabecalho': cab_plan, 'itens': itens_plan, 'nunota_dest': nunota_dest }
    # Enriquecer o plano com SQL/binds para exibição (não executa)
    try:
        # Cabeçalho
        if res['plano'].get('cabecalho'):
            try:
                cab_plan_preview = plan_insert_cabecalho(res['plano']['cabecalho'])
                res['plano']['cabecalho_sql'] = cab_plan_preview.get('sql')
                res['plano']['cabecalho_binds'] = cab_plan_preview.get('binds')
            except Exception:
                res['plano']['cabecalho_sql'] = None
                res['plano']['cabecalho_binds'] = {}
        # Itens
        it_sql = build_insert_item_sql()
        enriched_items = []
        for it in itens_plan:
            binds = {
                'NUNOTA': '<<NUNOTA>>',
                'SEQUENCIA': '<<SEQUENCIA>>',
                'CODEMP': int(codemp_o) if 'codemp_o' in locals() else None,
                'CODPROD': it.get('CODPROD'),
                'QTDNEG': it.get('QTDNEG'),
                'VLRUNIT': it.get('VLRUNIT'),
                'VLRTOT': round((it.get('QTDNEG') or 0) * (it.get('VLRUNIT') or 0), 2),
                'CODVOL': it.get('CODVOL'),
                'CODLOCALORIG': it.get('CODLOCALORIG'),
                'CODAGREGACAO': it.get('CODAGREGACAO'),
                'OBSERVACAO': it.get('OBSERVACAO'),
            }
            itm = it.copy()
            itm['sql'] = it_sql
            itm['binds'] = binds
            enriched_items.append(itm)
        res['plano']['itens'] = enriched_items
    except Exception:
        # If enrichment fails, ignore and return base plan
        pass
    res['ok'] = len(res['errors']) == 0
    return res


def _list_columns_like(table: str, like_pattern: str) -> list[str]:
    """Returns column names for `table` whose name matches LIKE pattern (case-insensitive), ordered by column_id."""
    try:
        t = str(table).upper(); p = str(like_pattern).upper()
        key = (t, p)
        cached = _LIKE_COLS_CACHE.get(key)
        if cached is not None:
            return cached
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT column_name FROM user_tab_cols
                 WHERE table_name=:t AND UPPER(column_name) LIKE :p
                 ORDER BY column_id
                """,
                t=t, p=p
            )
            cols = [r[0] for r in cur.fetchall()]
            _LIKE_COLS_CACHE[key] = cols
            return cols
    except Exception:
        return []


def _fetch_row_dynamic(table: str, columns: list[str], where_sql: str, binds: dict) -> dict:
    """Safely fetch a single row with selected columns; returns {col:value} for found row or {}."""
    if not columns:
        return {}
    cols_sql = ', '.join(columns)
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT {cols_sql} FROM {table} WHERE {where_sql}", binds)
            row = cur.fetchone()
            if not row:
                return {}
            return {c: row[i] for i, c in enumerate(columns)}
    except Exception:
        return {}


def weight_diagnostics(nunota: int, sequencia: int) -> dict:
    """Diagnostics for item weight logic: collects raw DB fields and computed estimates.

    - Reads TGFITE(NUNOTA, SEQUENCIA): CODPROD, CODVOL, QTDNEG, PESO (if exists)
    - Reads TGFPRO(CODPROD): CODVOL base and any columns like 'PESO%'
    - Reads TGFVOA(CODPROD, CODVOL): any columns like 'PESO%'
    - Reads TGFCAB(NUNOTA): any columns like 'PESO%'
    - Computes base unit + factor; estimates net/gross weights from product-level fields when present.
    """
    out = {
        'ok': False,
        'nunota': nunota,
        'sequencia': sequencia,
        'ite': {},
        'pro': {},
        'voa': {},
        'cab': {},
        'base_unit': None,
        'factor': None,
        'computed': {
            'qtd_base': None,
            'net_per_base': None,
            'gross_per_base': None,
            'net_estimated_total': None,
            'gross_estimated_total': None,
        },
        'notes': [],
        'error': None,
    }
    try:
        nun = int(nunota); seq = int(sequencia)
    except Exception:
        out['error'] = 'Parâmetros inválidos'
        return out

    # 1) TGFITE essentials
    ite_cols = ['CODPROD', 'CODVOL', 'QTDNEG']
    # PESO exists in this base; still guard just in case
    if 'PESO' in _list_columns_like('TGFITE', 'PESO') or True:
        if 'PESO' not in ite_cols:
            ite_cols.append('PESO')
    out['ite'] = _fetch_row_dynamic('TGFITE', ite_cols, 'NUNOTA=:n AND SEQUENCIA=:s', {'n': nun, 's': seq})
    if not out['ite']:
        out['error'] = 'Item não encontrado'
        return out

    codprod = int(out['ite'].get('CODPROD') or 0)
    codvol = str(out['ite'].get('CODVOL') or '')
    qtdneg = float(out['ite'].get('QTDNEG') or 0)

    # 2) Product weights
    pro_cols_all = ['CODVOL'] + _list_columns_like('TGFPRO', 'PESO%')
    out['pro'] = _fetch_row_dynamic('TGFPRO', pro_cols_all, 'CODPROD=:p', {'p': codprod})

    # 3) Alternative volume (VOA) weights for the item's CODVOL, if any
    voa_cols = _list_columns_like('TGFVOA', 'PESO%')
    if voa_cols:
        out['voa'] = _fetch_row_dynamic('TGFVOA', voa_cols + ['CODVOL'], 'CODPROD=:p AND UPPER(CODVOL)=:v', {'p': codprod, 'v': codvol.upper()})
    else:
        out['voa'] = {}

    # 4) Header weights (document level)
    cab_cols = _list_columns_like('TGFCAB', 'PESO%')
    out['cab'] = _fetch_row_dynamic('TGFCAB', cab_cols, 'NUNOTA=:n', {'n': nun}) if cab_cols else {}

    # 5) Conversion and estimates
    base, fator = get_base_unit_and_factor(codprod, codvol)
    out['base_unit'] = base
    out['factor'] = fator
    qtd_base = None
    try:
        if base and fator and base != (codvol or '').upper():
            qtd_base = float(qtdneg) * float(fator)
        else:
            qtd_base = float(qtdneg)
    except Exception:
        qtd_base = None
    out['computed']['qtd_base'] = qtd_base

    # Heuristic: search product columns for net/gross per BASE unit
    def _pick(colnames: list[str], key: str) -> str|None:
        keyu = key.upper()
        for c in colnames:
            cu = c.upper()
            if cu == keyu:
                return c
        # try common variants
        variants = [
            keyu,
            keyu.replace('PESO', 'PESOLIQ') if 'BRUTO' not in keyu else keyu,
        ]
        for v in variants:
            for c in colnames:
                if c.upper() == v:
                    return c
        return None

    pro_keys = list(out['pro'].keys()) if out['pro'] else []
    col_net = None
    col_gross = None
    # Common names in many Sankhya bases
    for cand in ['PESOLIQ', 'PESOLIQUIDO', 'PESOLIQPROD', 'PESOLIQU']:
        if cand in pro_keys:
            col_net = cand; break
    for cand in ['PESOBRUTO', 'PESOBRU', 'PESOBRUT']:
        if cand in pro_keys:
            col_gross = cand; break

    net_per_base = None
    gross_per_base = None
    try:
        if col_net and out['pro'].get(col_net) is not None:
            net_per_base = float(out['pro'][col_net])
    except Exception:
        net_per_base = None
    try:
        if col_gross and out['pro'].get(col_gross) is not None:
            gross_per_base = float(out['pro'][col_gross])
    except Exception:
        gross_per_base = None

    out['computed']['net_per_base'] = net_per_base
    out['computed']['gross_per_base'] = gross_per_base
    try:
        if qtd_base is not None and net_per_base is not None:
            out['computed']['net_estimated_total'] = round(qtd_base * net_per_base, 6)
        if qtd_base is not None and gross_per_base is not None:
            out['computed']['gross_estimated_total'] = round(qtd_base * gross_per_base, 6)
    except Exception:
        pass

    # Notes to help interpretation
    if 'PESO' in ite_cols:
        out['notes'].append('TGFITE.PESO é um campo livre por item (peso medido/informado).')
    if pro_keys:
        out['notes'].append('Pesos por unidade podem estar em TGFPRO (ex.: PESOLIQ, PESOBRUTO).')
    if cab_cols:
        out['notes'].append('Pesos do documento podem estar consolidados no TGFCAB (ex.: PESOLIQ, PESOBRUTO).')

    out['ok'] = True
    return out

def execute_classificacao(nunota_origem: int, sequencia_origem: int, saidas: list[dict], nunota_dest: int|None = None, dry_run: bool = True, force: bool = False) -> dict:
    """Executa a classificação: cria/usa nota de classificação e insere os itens de saída."""
    plan = plan_classificacao(nunota_origem, sequencia_origem, saidas, nunota_dest)
    res = { 'ok': False, 'executed': False, 'errors': [], 'warnings': [], 'nunota_dest': nunota_dest, 'itens_inseridos': 0 }
    if not plan.get('ok'):
        res['errors'] = plan.get('errors', [])
        res['warnings'] = plan.get('warnings', [])
        return res
    # Respeitar flag de escrita, a menos que 'force' seja solicitado
    write_ok = is_write_enabled() or force
    if dry_run or not write_ok:
        if not write_ok and not dry_run:
            res['warnings'].append('Escrita desabilitada por política — execução em modo simulado')
        # informar se o force foi usado
        res['force_used'] = bool(force)
        res['ok'] = True
        return res
    # 1) Criar cabeçalho se necessário
    #    Se o plano já detectou uma nota 26 existente por item/controle, reutilize.
    nun_dest = nunota_dest or plan.get('plano', {}).get('nunota_dest')
    if nun_dest is None:
        cab = plan.get('plano', {}).get('cabecalho') or {}
        cab_plan = insert_cabecalho(cab, dry_run=False)
        if not cab_plan.get('executed'):
            res['errors'].append(cab_plan.get('db_error', {}).get('message') or 'Falha ao criar cabeçalho de classificação')
            return res
        nun_dest = cab_plan.get('nunota')
        res['nunota_dest'] = nun_dest
    # 2) Inserir itens de saída
    count = 0
    for item in plan.get('plano', {}).get('itens', []):
        d = {
            'NUNOTA': nun_dest,
            'CODPROD': item['CODPROD'],
            'QTDNEG': item['QTDNEG'],
            'VLRUNIT': item['VLRUNIT'],
            'CODVOL': item['CODVOL'],
            'CODLOCALORIG': item['CODLOCALORIG'],
            # Reutilizar a CODAGREGACAO da origem (não gerar novo lote)
            'CODAGREGACAO': item.get('CODAGREGACAO') or item.get('CODAGREGACAO'),
            'OBSERVACAO': item.get('OBSERVACAO'),
        }
        ins = insert_item(d, dry_run=False)
        if not ins.get('executed'):
            res['errors'].append(ins.get('db_error', {}).get('message') or f"Falha ao inserir item {item['CODPROD']}")
        else:
            count += 1
    res['itens_inseridos'] = count
    res['ok'] = (count == len(plan.get('plano', {}).get('itens', [])))
    res['executed'] = res['ok']
    return res

def delete_nota(nunota: int, dry_run: bool = True) -> dict:
    """Exclui a nota (TGFCAB) e seus itens (TGFITE).
    Estratégia:
    - Carrega sequências dos itens e tenta excluir em ordem decrescente (reutiliza delete_itens).
    - Valida que não restaram itens; então exclui o cabeçalho TGFCAB.
    - Commit em cada etapa; retorna resultado detalhado/parcelado.
    """
    res = {
        'ok': False,
        'executed': False,
        'nunota': nunota,
        'deleted_itens': 0,
        'deleted_cab': 0,
        'errors': [],
        'warnings': [],
        'results_itens': [],
    }
    try:
        nun = int(nunota)
    except Exception:
        res['errors'].append('NUNOTA inválido')
        return res

    # Carregar sequências atuais (somente leitura)
    seqs = []
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT SEQUENCIA FROM TGFITE WHERE NUNOTA=:n ORDER BY SEQUENCIA DESC", n=nun)
        seqs = [int(r[0]) for r in cur.fetchall()]

    if dry_run or not is_write_enabled():
        if not is_write_enabled() and not dry_run:
            res['warnings'].append('Escrita desabilitada por política — execução em modo simulado')
        res['ok'] = True
        res['results_itens'] = [{'sequencia': s, 'would_delete': True} for s in seqs]
        return res

    # 1) Excluir itens (se existirem)
    if seqs:
        itens_res = delete_itens(nun, seqs, dry_run=False)
        res['results_itens'] = itens_res.get('results', [])
        res['deleted_itens'] = int(itens_res.get('deleted') or 0)
        if itens_res.get('errors'):
            res['errors'].extend(itens_res['errors'])

    # 2) Verificar se ainda há itens
    remaining = 0
    with get_connection() as conn2:
        cur2 = conn2.cursor()
        cur2.execute("SELECT COUNT(1) FROM TGFITE WHERE NUNOTA=:n", n=nun)
        (remaining,) = cur2.fetchone()
        remaining = int(remaining or 0)

    if remaining > 0:
        res['warnings'].append(f'Ainda restam {remaining} item(ns) — cabeçalho não será excluído')
        res['ok'] = (res['deleted_itens'] > 0 and len(res['errors']) == 0)
        res['executed'] = False
        return res

    # 3) Excluir cabeçalho
    try:
        with get_connection() as conn3:
            cur3 = conn3.cursor()
            cur3.execute("DELETE FROM TGFCAB WHERE NUNOTA=:n", n=nun)
            res['deleted_cab'] = int(cur3.rowcount or 0)
            conn3.commit()
        res['ok'] = True
        res['executed'] = (res['deleted_cab'] > 0)
        if res['deleted_cab'] == 0:
            res['warnings'].append('Nenhum cabeçalho excluído (NUNOTA não encontrado)')
        return res
    except cx_Oracle.DatabaseError as e:
        try:
            err, = e.args
            res['errors'].append(getattr(err, 'message', str(e)))
        except Exception:
            res['errors'].append(str(e))
        res['executed'] = False
        return res

if __name__ == '__main__':
    test_oracle_connection()
    print('\nConsultando tabela tgfpar:')
    select_all_tgfpar()

    # Exemplo de geração de lote
    from datetime import date
    lote = gerar_lote(date.today(), 76, 358)
    print(f'Exemplo de lote gerado: {lote}')


def duplicate_to_classification(nunota_11: int, dry_run: bool = True) -> dict:
    """Duplica nota TOP 11 para TOP 26 com produtos classificáveis.
    
    Fallback manual para quando o trigger automático não funcionar.
    
    Args:
        nunota_11: NUNOTA da nota TOP 11 (origem)
        dry_run: Se True, apenas simula (não executa)
    
    Returns:
        dict: {ok, nunota_26, errors, warnings, executed}
    """
    res = {
        'ok': False, 
        'nunota_26': None, 
        'errors': [], 
        'warnings': [],
        'executed': False,
        'items_duplicated': 0
    }
    
    try:
        nunota_11 = int(nunota_11)
    except (ValueError, TypeError):
        res['errors'].append('NUNOTA inválido')
        return res

    params = get_params()
    TOP_ENTRADA = params['TOP_ENTRADA']  # 11
    TOP_CLASS = params['TOP_CLASS']      # 26
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Verificar se TOP 11 existe
            cur.execute("""
                SELECT COUNT(*) FROM TGFCAB 
                WHERE NUNOTA = :n AND CODTIPOPER = :top
            """, n=nunota_11, top=TOP_ENTRADA)
            
            if cur.fetchone()[0] == 0:
                res['errors'].append(f'NUNOTA {nunota_11} TOP 11 não encontrada')
                return res
            
            # 2. Obter controle(s) da nota origem
            cur.execute("""
                SELECT DISTINCT i.CODAGREGACAO 
                FROM TGFITE i 
                WHERE i.NUNOTA = :n
                AND i.CODAGREGACAO IS NOT NULL
            """, n=nunota_11)
            
            controles = [row[0] for row in cur.fetchall()]
            if not controles:
                res['errors'].append('Nenhum controle encontrado nos itens da nota')
                return res
            
            # 3. Verificar se já existe TOP 26 para algum controle (buscar mais recente)
            nunota_26_existente = None
            if controles:
                controles_str = ','.join([f"'{c}'" for c in controles])
                cur.execute(f"""
                    SELECT i.NUNOTA FROM TGFITE i
                    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                    WHERE i.CODAGREGACAO IN ({controles_str}) 
                    AND c.CODTIPOPER = :top
                    ORDER BY c.DTMOV DESC, i.NUNOTA DESC
                """, top=TOP_CLASS)
                
                row = cur.fetchone()
                if row:
                    nunota_26_existente = int(row[0])
                    res['warnings'].append(f'TOP 26 já existe: NUNOTA {nunota_26_existente}')
            
            # 4. Contar itens classificáveis
            cur.execute("""
                SELECT COUNT(*) FROM TGFITE
                WHERE NUNOTA = :n AND NVL(GERAPRODUCAO, 'N') = 'S'
            """, n=nunota_11)
            
            items_classificaveis = cur.fetchone()[0]
            if items_classificaveis == 0:
                res['warnings'].append('Nenhum item classificável encontrado')
                res['ok'] = True
                return res
            
            if dry_run:
                res['ok'] = True
                res['warnings'].append(f'Modo simulação - {items_classificaveis} itens seriam duplicados')
                return res
            
            if not is_write_enabled():
                res['warnings'].append('Escrita desabilitada - execução simulada')
                res['ok'] = True
                return res
            
            # 5. Usar TOP 26 existente ou criar nova
            if nunota_26_existente:
                # Usar TOP 26 existente
                nunota_26 = nunota_26_existente
                res['nunota_26'] = nunota_26
                res['warnings'].append(f'Usando TOP 26 existente: {nunota_26}')
            else:
                # Criar nova TOP 26
                # Primeiro, obter dados da nota original
                cur.execute("""
                    SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, DTMOV, DTENTSAI,
                           CODVEND, CODPARCTRANSP, CODPROJ, NUMNOTA, OBSERVACAO
                    FROM TGFCAB WHERE NUNOTA = :n
                """, n=nunota_11)
                orig_data = cur.fetchone()
                
                if not orig_data:
                    res['errors'].append('Cabeçalho da nota original não encontrado')
                    return res
                
                # Criar dados para TOP 26
                cab_data = {
                    'CODEMP': orig_data[0],
                    'CODPARC': orig_data[1], 
                    'CODTIPOPER': TOP_CLASS,  # 26
                    'CODNAT': orig_data[2],
                    'CODCENCUS': orig_data[3],
                    'DTNEG': orig_data[4].strftime('%d/%m/%Y') if orig_data[4] else None,
                    'DTMOV': orig_data[5].strftime('%d/%m/%Y') if orig_data[5] else None,
                    'DTENTSAI': orig_data[6].strftime('%d/%m/%Y') if orig_data[6] else None,
                    'CODVEND': orig_data[7] if orig_data[7] else 0,
                    'CODPARCTRANSP': orig_data[8] if orig_data[8] else 0,
                    'CODPROJ': orig_data[9] if orig_data[9] else 0,
                    'NUMNOTA': orig_data[10] if orig_data[10] else None,
                    'OBSERVACAO': f'Auto-duplicado de TOP 11 NUNOTA {nunota_11}'
                }
                
                # Usar insert_cabecalho para criar TOP 26
                cab_result = insert_cabecalho(cab_data, dry_run=False)
                if not cab_result.get('executed'):
                    res['errors'].append('Falha ao criar cabeçalho TOP 26')
                    res['errors'].extend(cab_result.get('errors', []))
                    return res
                    
                nunota_26 = cab_result.get('nunota')
                res['nunota_26'] = int(nunota_26)
                res['warnings'].append(f'Nova TOP 26 criada: {nunota_26}')

            
            # 6. Duplicar apenas itens que ainda não existem na TOP 26
            # Verificar próxima sequência disponível
            cur.execute("""
                SELECT NVL(MAX(SEQUENCIA), 0) + 1 FROM TGFITE WHERE NUNOTA = :n
            """, n=nunota_26)
            next_seq = cur.fetchone()[0]
            
            # Inserir apenas itens que não estão duplicados ainda
            cur.execute("""
                INSERT INTO TGFITE (
                    NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT,
                    CODVOL, CODLOCALORIG, CODAGREGACAO, GERAPRODUCAO, STATUSNOTA,
                    OBSERVACAO
                )
                SELECT 
                    :nunota_26, 
                    :next_seq + ROW_NUMBER() OVER (ORDER BY i11.SEQUENCIA) - 1,
                    i11.CODEMP, i11.CODPROD, i11.QTDNEG, i11.VLRUNIT, i11.VLRTOT,
                    i11.CODVOL, i11.CODLOCALORIG, i11.CODAGREGACAO, i11.GERAPRODUCAO, 'A',
                    'Auto-duplicado de TOP 11'
                FROM TGFITE i11
                WHERE i11.NUNOTA = :nunota_11 
                AND NVL(i11.GERAPRODUCAO, 'N') = 'S'
                AND NOT EXISTS (
                    SELECT 1 FROM TGFITE i26
                    WHERE i26.NUNOTA = :nunota_26
                    AND i26.CODPROD = i11.CODPROD
                    AND i26.CODAGREGACAO = i11.CODAGREGACAO
                )
            """, {
                'nunota_26': nunota_26, 
                'nunota_11': nunota_11,
                'next_seq': next_seq
            })
            
            items_inserted = cur.rowcount
            res['items_duplicated'] = items_inserted
            
            conn.commit()
            res['executed'] = True
            res['ok'] = True
            
            if nunota_26_existente:
                res['warnings'].append(f'Adicionados {items_inserted} itens à TOP 26 existente: NUNOTA {nunota_26}')
            else:
                res['warnings'].append(f'TOP 26 criada: NUNOTA {nunota_26} com {items_inserted} itens')
            
    except Exception as e:
        res['errors'].append(f'Erro ao duplicar: {str(e)}')
        
    return res


def is_auto_duplicate_enabled() -> bool:
    """Verifica se a duplicação automática está habilitada."""
    try:
        params = get_params()
        return bool(params.get('AUTO_DUPLICATE_CLASSIFICATION', True))
    except Exception:
        return False


def is_auto_duplicate_on_save_enabled() -> bool:
    """Verifica se deve duplicar automaticamente ao salvar item."""
    try:
        # Verificar configurações Django
        from django.conf import settings
        config = getattr(settings, 'SANKHYA_CONFIG', {})
        auto_flows = config.get('AUTO_FLOWS', {})
        
        # Se não tem configuração, assume True (habilitado por padrão)
        duplicate_on_save = auto_flows.get('DUPLICATE_ON_SAVE', True)
        duplicate_method = auto_flows.get('DUPLICATE_METHOD', 'python')
        
        # Verificar parâmetros também
        params = get_params()
        auto_duplicate_on_save = params.get('AUTO_DUPLICATE_ON_SAVE', True)
        
        result = (
            duplicate_on_save and 
            duplicate_method == 'python' and
            auto_duplicate_on_save
        )
        
        return result
    except Exception:
        # Em caso de erro, retorna True para não bloquear
        return True


def should_auto_duplicate_item(nunota: int, codprod: int) -> dict:
    """Verifica se um item deve ser duplicado automaticamente.
    
    Returns:
        dict: {should_duplicate: bool, reason: str, codtipoper: int|None}
    """
    result = {'should_duplicate': False, 'reason': '', 'codtipoper': None}
    
    if not is_auto_duplicate_on_save_enabled():
        result['reason'] = 'Duplicação automática desabilitada'
        return result
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Verificar se é TOP 11
            cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
            row = cur.fetchone()
            if not row:
                result['reason'] = 'Nota não encontrada'
                return result
                
            codtipoper = row[0]
            result['codtipoper'] = codtipoper
            
            params = get_params()
            if codtipoper != params['TOP_ENTRADA']:  # 11
                result['reason'] = f'Nota não é TOP {params["TOP_ENTRADA"]} (é TOP {codtipoper})'
                return result
            
            # Verificar se item é classificável (GERAPRODUCAO na TGFITE)
            cur.execute("""
                SELECT NVL(GERAPRODUCAO, 'N') FROM TGFITE 
                WHERE NUNOTA = :n AND CODPROD = :p
            """, n=nunota, p=codprod)
            row = cur.fetchone()
            if not row or row[0] != 'S':
                result['reason'] = 'Item não é classificável (GERAPRODUCAO != S na TGFITE)'
                return result
            
            result['should_duplicate'] = True
            result['reason'] = 'Item classificável em nota TOP 11'
            return result
            
    except Exception as e:
        result['reason'] = f'Erro ao verificar: {str(e)}'
        return result


def get_duplicate_status(nunota_11: int) -> dict:
    """Verifica status de duplicação para uma nota TOP 11.
    
    Returns:
        dict: {
            has_top26: bool,
            nunota_26: int|None, 
            controls: list[str],
            classificable_items: int
        }
    """
    try:
        nunota_11 = int(nunota_11)
    except (ValueError, TypeError):
        return {'error': 'NUNOTA inválido'}

    params = get_params()
    TOP_CLASS = params['TOP_CLASS']
    
    result = {
        'has_top26': False,
        'nunota_26': None,
        'controls': [],
        'classificable_items': 0
    }
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Controles da nota
            cur.execute("""
                SELECT DISTINCT i.CODAGREGACAO 
                FROM TGFITE i 
                WHERE i.NUNOTA = :n
                AND i.CODAGREGACAO IS NOT NULL
            """, n=nunota_11)
            result['controls'] = [row[0] for row in cur.fetchall()]
            
            # Items classificáveis
            cur.execute("""
                SELECT COUNT(*) FROM TGFITE
                WHERE NUNOTA = :n AND NVL(GERAPRODUCAO, 'N') = 'S'
            """, n=nunota_11)
            result['classificable_items'] = cur.fetchone()[0]
            
            # Verificar se existe TOP 26 para qualquer controle (buscar mais recente)
            if result['controls']:
                # Buscar TOP 26 mais recente para qualquer controle da nota
                controles_str = ','.join([f"'{c}'" for c in result['controls']])
                cur.execute(f"""
                    SELECT i.NUNOTA FROM TGFITE i
                    JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                    WHERE i.CODAGREGACAO IN ({controles_str}) 
                    AND c.CODTIPOPER = :top
                    ORDER BY c.DTMOV DESC, i.NUNOTA DESC
                """, top=TOP_CLASS)
                
                row = cur.fetchone()
                if row:
                    result['has_top26'] = True
                    result['nunota_26'] = int(row[0])
                    
    except Exception:
        pass
        
    return result


def sync_item_to_classification(nunota_11: int, codprod: int, dry_run: bool = False) -> dict:
    """Sincroniza alterações do item (TOP 11) para o item correspondente na TOP 26 com UPSERT.

    Passos:
    - Localiza o item origem em TOP 11 (por NUNOTA, CODPROD) e lê campos: CODAGREGACAO (controle),
      QTDNEG, VLRUNIT, VLRTOT, CODVOL, PESO, CODLOCALORIG, GERAPRODUCAO.
    - Busca a TOP 26 mais recente para este controle.
      - Se existir: tenta UPDATE do item (match por CODPROD+CODAGREGACAO).
      - Se o UPDATE afetar 0 linhas e GERAPRODUCAO='S': faz INSERT (upsert) do item.
    - Se não existir TOP 26 para o controle e GERAPRODUCAO='S': cria cabeçalho TOP 26 baseado na TOP 11
      (via insert_cabecalho) e insere o item.

    Observações:
    - O INSERT considera apenas colunas existentes em TGFITE (detecção dinâmica) e define DTALTER=SYSDATE quando disponível.
    - Itens não classificáveis (GERAPRODUCAO!='S') não são inseridos na TOP 26.

    Returns:
        dict: { ok, updated: int, inserted: int, nunota_26: int|None, created_header: bool, warnings: list, errors: list }
    """
    out = {
        'ok': False, 'updated': 0, 'inserted': 0,
        'nunota_26': None, 'created_header': False,
        'warnings': [], 'errors': []
    }
    try:
        nun = int(nunota_11)
        prod = int(codprod)
    except Exception:
        out['errors'].append('Parâmetros inválidos (nunota_11, codprod)')
        return out

    params = get_params()
    TOP_CLASS = params['TOP_CLASS']

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1) Obter dados do item na TOP 11
            cur.execute(
                """
                SELECT /*+ FIRST_ROWS(1) */
                       CODAGREGACAO,
                       QTDNEG,
                       VLRUNIT,
                       VLRTOT,
                       CODVOL,
                       NVL(PESO, 0) AS PESO,
                       CODLOCALORIG,
                       NVL(GERAPRODUCAO,'N') AS GP
                  FROM (
                        SELECT CODAGREGACAO, QTDNEG, VLRUNIT, VLRTOT, CODVOL, PESO, CODLOCALORIG, GERAPRODUCAO
                          FROM TGFITE
                         WHERE NUNOTA = :n AND CODPROD = :p
                         ORDER BY SEQUENCIA
                       )
                 WHERE ROWNUM = 1
                """,
                n=nun, p=prod
            )
            row = cur.fetchone()
            if not row:
                out['warnings'].append('Item não encontrado em TOP 11')
                out['ok'] = True
                return out

            ctrl, qtd, vlu, vlt, codvol, peso, codlocal, gp = row
            if not ctrl:
                out['warnings'].append('Item sem controle (CODAGREGACAO) — nada a sincronizar')
                out['ok'] = True
                return out

            # 2) Localizar NUNOTA da TOP 26 mais recente para o mesmo controle
            cur.execute(
                """
                SELECT /*+ FIRST_ROWS(1) */ x.NUNOTA FROM (
                    SELECT i.NUNOTA
                      FROM TGFITE i
                      JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                     WHERE i.CODAGREGACAO = :c AND c.CODTIPOPER = :top
                     ORDER BY c.DTMOV DESC, i.NUNOTA DESC
                ) x WHERE ROWNUM = 1
                """,
                c=ctrl, top=TOP_CLASS
            )
            r26 = cur.fetchone()
            nun26 = int(r26[0]) if r26 and r26[0] is not None else None

            # Se não há TOP 26 para o controle e o item é classificável, criaremos o cabeçalho
            if nun26 is None and str(gp).strip().upper() == 'S':
                # Carregar dados do cabeçalho TOP 11 para basear a criação
                cur.execute(
                    """
                    SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, DTMOV, DTENTSAI,
                           CODVEND, CODPARCTRANSP, CODPROJ, NUMNOTA, OBSERVACAO
                      FROM TGFCAB WHERE NUNOTA = :n
                    """,
                    n=nun
                )
                cab11 = cur.fetchone()
                if not cab11:
                    out['errors'].append('Cabeçalho TOP 11 não encontrado para criar TOP 26')
                    return out
                cab_data = {
                    'CODEMP': cab11[0],
                    'CODPARC': cab11[1],
                    'CODTIPOPER': TOP_CLASS,
                    'CODNAT': cab11[2],
                    'CODCENCUS': cab11[3],
                    'DTNEG': cab11[4].strftime('%d/%m/%Y') if cab11[4] else None,
                    'DTMOV': cab11[5].strftime('%d/%m/%Y') if cab11[5] else None,
                    'DTENTSAI': cab11[6].strftime('%d/%m/%Y') if cab11[6] else None,
                    'CODVEND': cab11[7] if cab11[7] else 0,
                    'CODPARCTRANSP': cab11[8] if cab11[8] else 0,
                    'CODPROJ': cab11[9] if cab11[9] else 0,
                    'NUMNOTA': cab11[10] if cab11[10] else None,
                    'OBSERVACAO': f'Sync (auto) de TOP 11 NUNOTA {nun}'
                }
                if dry_run or not is_write_enabled():
                    out['warnings'].append('Criaria cabeçalho TOP 26 (dry_run ou write desabilitado)')
                else:
                    cab_res = insert_cabecalho(cab_data, dry_run=False)
                    if not cab_res.get('executed'):
                        out['errors'].append('Falha ao criar cabeçalho TOP 26 (upsert)')
                        out['errors'].extend(cab_res.get('errors', []))
                        return out
                    nun26 = int(cab_res.get('nunota'))
                    out['created_header'] = True
                out['nunota_26'] = nun26

            # Se ainda não há TOP 26 e gp != 'S', nada a inserir
            if nun26 is None and str(gp).strip().upper() != 'S':
                out['warnings'].append('TOP 26 inexistente e item não classificável — sem upsert')
                out['ok'] = True
                return out

            # Se chegamos aqui e for dry_run/write disabled, apenas reportar
            if dry_run or not is_write_enabled():
                out['warnings'].append('Execução em modo simulado (dry_run ou write desabilitado)')
                out['ok'] = True
                return out

            # 3) Tentar UPDATE no item correspondente da TOP 26
            cols = _get_table_columns(conn, 'TGFITE')
            set_parts = [
                'QTDNEG=:Q', 'VLRUNIT=:VU', 'VLRTOT=:VT', 'CODVOL=:CV', 'PESO=:PS', 'CODLOCALORIG=:LOC', 'GERAPRODUCAO=:GP'
            ]
            if 'DTALTER' in cols:
                set_parts.append('DTALTER=SYSDATE')

            sql_upd = f"UPDATE TGFITE SET {', '.join(set_parts)} WHERE NUNOTA=:N26 AND CODPROD=:P AND CODAGREGACAO=:CTRL"
            binds_upd = {
                'Q': float(qtd or 0),
                'VU': float(vlu or 0),
                'VT': float(vlt or 0),
                'CV': (codvol or None),
                'PS': float(peso or 0),
                'LOC': int(codlocal or 0) if codlocal is not None else 0,
                'GP': (str(gp).strip().upper() if gp is not None else None),
                'N26': nun26,
                'P': prod,
                'CTRL': ctrl,
            }
            cur.execute(sql_upd, binds_upd)
            out['updated'] = int(cur.rowcount or 0)

            # 4) Se nenhum item foi atualizado e for classificável, realizar INSERT (UPSERT)
            if out['updated'] == 0 and str(gp).strip().upper() == 'S':
                # Obter CODEMP do cabeçalho destino e próxima SEQUENCIA
                cur.execute("SELECT CODEMP FROM TGFCAB WHERE NUNOTA=:n", n=nun26)
                row_emp = cur.fetchone()
                dest_emp = int(row_emp[0]) if row_emp and row_emp[0] is not None else None
                cur.execute("SELECT NVL(MAX(SEQUENCIA),0) + 1 FROM TGFITE WHERE NUNOTA=:n", n=nun26)
                (next_seq,) = cur.fetchone()
                try:
                    next_seq = int(next_seq or 1)
                except Exception:
                    next_seq = 1

                # Montar INSERT dinâmico com colunas existentes
                tcols = _get_table_columns(conn, 'TGFITE')
                base_cols = [
                    'NUNOTA','SEQUENCIA','CODEMP','CODPROD','QTDNEG','PESO','VLRUNIT','VLRTOT','CODVOL','CODLOCALORIG','CODAGREGACAO','OBSERVACAO','GERAPRODUCAO'
                ]
                cols_present = [c for c in base_cols if c in tcols]
                col_list = cols_present[:]
                values_parts = []
                binds_ins = {}
                for c in cols_present:
                    if c == 'NUNOTA':
                        values_parts.append(':NUNOTA'); binds_ins['NUNOTA'] = nun26
                    elif c == 'SEQUENCIA':
                        values_parts.append(':SEQUENCIA'); binds_ins['SEQUENCIA'] = next_seq
                    elif c == 'CODEMP':
                        values_parts.append(':CODEMP'); binds_ins['CODEMP'] = dest_emp
                    elif c == 'CODPROD':
                        values_parts.append(':CODPROD'); binds_ins['CODPROD'] = prod
                    elif c == 'QTDNEG':
                        values_parts.append(':QTDNEG'); binds_ins['QTDNEG'] = float(qtd or 0)
                    elif c == 'PESO':
                        values_parts.append(':PESO'); binds_ins['PESO'] = float(peso or 0)
                    elif c == 'VLRUNIT':
                        values_parts.append(':VLRUNIT'); binds_ins['VLRUNIT'] = float(vlu or 0)
                    elif c == 'VLRTOT':
                        values_parts.append(':VLRTOT'); binds_ins['VLRTOT'] = float(vlt or 0)
                    elif c == 'CODVOL':
                        values_parts.append(':CODVOL'); binds_ins['CODVOL'] = (codvol or None)
                    elif c == 'CODLOCALORIG':
                        values_parts.append(':CODLOCALORIG'); binds_ins['CODLOCALORIG'] = int(codlocal or 0) if codlocal is not None else 0
                    elif c == 'CODAGREGACAO':
                        values_parts.append(':CODAGREGACAO'); binds_ins['CODAGREGACAO'] = ctrl
                    elif c == 'OBSERVACAO':
                        values_parts.append(':OBS'); binds_ins['OBS'] = 'Upsert automático (sync portal)'
                    elif c == 'GERAPRODUCAO':
                        values_parts.append(':GP'); binds_ins['GP'] = (str(gp).strip().upper() if gp is not None else None)
                # DTALTER
                add_dtalter = 'DTALTER' in tcols
                if add_dtalter:
                    col_list.append('DTALTER')
                    values_parts.append('SYSDATE')

                sql_ins = f"INSERT INTO TGFITE ({', '.join(col_list)}) VALUES ({', '.join(values_parts)})"
                cur.execute(sql_ins, binds_ins)
                out['inserted'] = int(cur.rowcount or 0)

                # Padronizações pós-gravação
                try:
                    std = standardize_item_fields(nun26, next_seq, conn=conn)
                    out['standardize'] = std
                except Exception:
                    pass

            # Commit final e retorno
            conn.commit()
            out['nunota_26'] = nun26
            out['ok'] = True
            if out['updated'] == 0 and out['inserted'] == 0:
                out['warnings'].append('Nenhum item correspondente atualizado ou inserido na TOP 26')
            return out

    except cx_Oracle.DatabaseError as e:
        try:
            err, = e.args
            out['errors'].append(getattr(err, 'message', str(e)))
        except Exception:
            out['errors'].append(str(e))
        out['ok'] = False
        return out


