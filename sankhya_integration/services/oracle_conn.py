import requests
import os
import time
import logging
import importlib
import hashlib
from contextlib import contextmanager
from datetime import datetime, date as _date, timedelta
from typing import Optional, Any

# ==============================================================================
# INICIALIZAÇÃO DO DRIVER ORACLE
# ==============================================================================
try:
    cx_Oracle = importlib.import_module('cx_Oracle')  # type: ignore
except Exception:
    import oracledb as cx_Oracle
    try:
        is_thin = getattr(cx_Oracle, 'is_thin_mode', None)
        if callable(is_thin) and is_thin():
            lib_dir = (
                os.getenv('ORACLE_CLIENT_LIB_DIR')
                or os.getenv('SANKHYA_ORACLE_CLIENT')
                or os.getenv('ORACLE_HOME')
            )
            if lib_dir and os.path.isdir(lib_dir):
                cx_Oracle.init_oracle_client(lib_dir=lib_dir)
            else:
                try: cx_Oracle.init_oracle_client()
                except Exception: pass
    except Exception: pass

logger = logging.getLogger(__name__)

# ==============================================================================
# 🌍 1. INFRAESTRUTURA E UTILITÁRIOS GLOBAIS
# Conexão, permissões e consultas genéricas usadas em todo o sistema
# ==============================================================================

_POOL_CONEXOES = None
_CACHE_COLUNAS: dict[str, set] = {}

PARAMETROS_PADRAO = {
    'TOP_ENTRADA': 11,
    'PROD_IN_NATURA': 863,
}

def obter_configuracoes_sistema():
    """Busca configurações gerais do sistema no settings.py do Django."""
    try:
        from django.conf import settings
        cfg = getattr(settings, 'SANKHYA_CONFIG', {})
        if isinstance(cfg, dict): return cfg
    except Exception: pass
    return {}

def obter_configuracoes_banco():
    """Monta as credenciais de acesso ao banco baseado no ambiente (Local/Remoto)."""
    cfg = obter_configuracoes_sistema().get('DB', {})
    db_mode = os.getenv('DB_MODE', 'local').lower()
    
    perfis_banco = {
        'local': {'host': '', 'port': 1521, 'service': 'XE', 'user': '', 'password': ''},
        'remote': {'host': '', 'port': 1521, 'service': 'XE', 'user': '', 'password': ''}
    }
    perfil = perfis_banco.get(db_mode, perfis_banco['local'])
    
    return {
        'host': os.getenv('SANKHYA_DB_HOST', cfg.get('host', perfil['host'])),
        'port': int(os.getenv('SANKHYA_DB_PORT', cfg.get('port', perfil['port']))),
        'service_name': os.getenv('SANKHYA_DB_SERVICE', cfg.get('service_name', perfil['service'])),
        'sid': os.getenv('SANKHYA_DB_SID', cfg.get('sid')),
        'dsn': os.getenv('SANKHYA_DB_DSN', cfg.get('dsn')),
        'user': os.getenv('SANKHYA_DB_USER', cfg.get('user', perfil['user'])),
        'password': os.getenv('SANKHYA_DB_PASSWORD', cfg.get('password', perfil['password'])),
    }

def obter_parametros_globais():
    """Retorna os parâmetros de negócio (Ex: TOP_ENTRADA = 11)."""
    cfg = obter_configuracoes_sistema().get('PARAMS', {})
    params = PARAMETROS_PADRAO.copy()
    if isinstance(cfg, dict): params.update(cfg)
    return params

def verificar_permissao_escrita() -> bool:
    """Verifica se o sistema tem permissão para salvar/alterar dados no Oracle."""
    try:
        cfg = obter_configuracoes_sistema()
        if isinstance(cfg, dict) and cfg.get('WRITE_ENABLED') is True: return True
    except Exception: pass
    return os.getenv('IAGRO_WRITE_ENABLED', 'false').lower() in ('1', 'true', 'yes', 'on')

def _montar_string_conexao(host: str, port: int, service_name: str | None, sid: str | None, full_dsn: str | None) -> str:
    """Monta a string DSN exigida pelo driver do Oracle."""
    try:
        if full_dsn: return full_dsn
        if sid: return cx_Oracle.makedsn(host, port, sid=sid)
        return cx_Oracle.makedsn(host, port, service_name=service_name)
    except Exception:
        if full_dsn: return full_dsn
        if sid: return f"{host}:{port}/{sid}"
        return f"{host}:{port}/{service_name}"

@contextmanager
def obter_conexao_oracle():
    """Gerenciador de contexto para abrir e fechar a conexão com o Oracle de forma segura."""
    global _POOL_CONEXOES
    db = obter_configuracoes_banco()
    dsn = _montar_string_conexao(db['host'], db['port'], db.get('service_name'), db.get('sid'), db.get('dsn'))
    conn = None
    try:
        if _POOL_CONEXOES is None and hasattr(cx_Oracle, 'create_pool'):
            try:
                _POOL_CONEXOES = cx_Oracle.create_pool(
                    user=db['user'], password=db['password'], dsn=dsn,
                    min=1, max=max(4, int(os.getenv('SANKHYA_DB_POOL_MAX', '4'))), increment=1
                )
            except Exception: _POOL_CONEXOES = None
            
        if _POOL_CONEXOES is not None and hasattr(_POOL_CONEXOES, 'acquire'):
            conn = _POOL_CONEXOES.acquire()
        else:
            conn = cx_Oracle.connect(user=db['user'], password=db['password'], dsn=dsn)
    except Exception:
        conn = cx_Oracle.connect(user=db['user'], password=db['password'], dsn=dsn)
    try:
        yield conn
    finally:
        try: conn.close()
        except Exception: pass

def _obter_colunas_da_tabela(conn, tabela: str) -> set[str]:
    """Lista dinamicamente as colunas de uma tabela (com cache para performance)."""
    try:
        t = str(tabela).upper()
        if t in _CACHE_COLUNAS: return _CACHE_COLUNAS[t]
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM user_tab_cols WHERE table_name=:t", t=t)
        cols = {r[0].upper() for r in cur.fetchall()}
        _CACHE_COLUNAS[t] = cols
        return cols
    except Exception:
        return set()

# --- CONSULTAS GENÉRICAS (TYPEAHEADS) ---

def consultar_parceiros_oracle(termo: str, limite: int = 10):
    """Busca parceiros ativos na TGFPAR (Por código ou nome)."""
    if not termo: return []
    termo = str(termo).strip().upper()
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if termo.isdigit():
            sql = "SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE (CODPARC = :k OR TO_CHAR(CODPARC) LIKE :pfx) AND NVL(ATIVO,'S')='S' AND ROWNUM <= :lim"
            cur.execute(sql, k=int(termo), pfx=f"{termo}%", lim=limite)
        else:
            sql = "SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE UPPER(NOMEPARC) LIKE :q AND NVL(ATIVO,'S')='S' AND ROWNUM <= :lim"
            cur.execute(sql, q=f"%{termo}%", lim=limite)
        return cur.fetchall()

def consultar_produtos_oracle(q: str = "", limit: int = 15, allow_in_natura: bool = False, grupo_inicia_com: str = None):
    """
    Busca produtos de forma inteligente, suportando filtros de in natura, grupo e pesquisa textual/numérica.
    """
    where = ["NVL(ATIVO, 'S') = 'S'"]
    binds = {}
    
    # Filtro: allow_in_natura (SELECIONADO = '0')
    if allow_in_natura:
        where.append("TO_CHAR(SELECIONADO) = '0'")
        
    # Filtro: Grupo Inicia Com
    if grupo_inicia_com:
        where.append("TO_CHAR(CODGRUPOPROD) LIKE :grupo_ini")
        binds['grupo_ini'] = f"{grupo_inicia_com}%"
        
    # Monta a base do SELECT com as 3 colunas exigidas pelo views.py
    sql_base = f"SELECT CODPROD, DESCRPROD, SELECIONADO FROM TGFPRO WHERE {' AND '.join(where)}"
    
    # Lógica de Pesquisa (q)
    if q and q.strip():
        termo = q.strip()
        if termo.isdigit():
            # Busca exata pelo código (aparece primeiro) ou parcial pelo código
            k = int(termo)
            sql = (
                "SELECT CODPROD, DESCRPROD, SELECIONADO FROM ("
                f"{sql_base} AND CODPROD = :k"
                " UNION ALL "
                f"{sql_base} AND TO_CHAR(CODPROD) LIKE :p AND CODPROD <> :k"
                ") WHERE ROWNUM <= :lim"
            )
            binds.update({'k': k, 'p': f"{termo}%", 'lim': limit})
        else:
            # Busca parcial pela descrição
            sql = f"SELECT CODPROD, DESCRPROD, SELECIONADO FROM ({sql_base} AND UPPER(DESCRPROD) LIKE :p ORDER BY DESCRPROD) WHERE ROWNUM <= :lim"
            binds.update({'p': f"%{termo.upper()}%", 'lim': limit})
    else:
        # Se não digitou nada no campo, traz a lista inicial ordenada
        sql = f"SELECT CODPROD, DESCRPROD, SELECIONADO FROM ({sql_base} ORDER BY DESCRPROD) WHERE ROWNUM <= :lim"
        binds.update({'lim': limit})

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        
        # Ignora acentos e maiúsculas/minúsculas no Oracle
        try:
            cur.execute("ALTER SESSION SET NLS_COMP=LINGUISTIC")
            cur.execute("ALTER SESSION SET NLS_SORT=BINARY_AI")
        except Exception:
            pass

        cur.execute(sql, binds)
        return cur.fetchall() # Retorna as 3 colunas para o views.py

def consultar_tipos_operacao_oracle(termo: str, limite: int = 10):
    """Busca tipos de operação (TOP) ativos na TGFTOP."""
    if not termo: return []
    termo = str(termo).strip().upper()
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if termo.isdigit():
            sql = "SELECT DISTINCT CODTIPOPER, DESCROPER FROM TGFTOP WHERE (CODTIPOPER = :k OR TO_CHAR(CODTIPOPER) LIKE :pfx) AND ROWNUM <= :lim"
            cur.execute(sql, k=int(termo), pfx=f"{termo}%", lim=limite)
        else:
            sql = "SELECT DISTINCT CODTIPOPER, DESCROPER FROM TGFTOP WHERE UPPER(DESCROPER) LIKE :q AND ROWNUM <= :lim"
            cur.execute(sql, q=f"%{termo}%", lim=limite)
        return cur.fetchall()

def consultar_naturezas_oracle(termo: str, limite: int = 10):
    """Busca naturezas de receita/despesa na TGFNAT."""
    if not termo: return []
    termo = str(termo).strip().upper()
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if termo.isdigit():
            sql = "SELECT DISTINCT CODNAT, DESCRNAT FROM TGFNAT WHERE (CODNAT = :k OR TO_CHAR(CODNAT) LIKE :pfx) AND ROWNUM <= :lim"
            cur.execute(sql, k=int(termo), pfx=f"{termo}%", lim=limite)
        else:
            sql = "SELECT DISTINCT CODNAT, DESCRNAT FROM TGFNAT WHERE UPPER(DESCRNAT) LIKE :q AND ROWNUM <= :lim"
            cur.execute(sql, q=f"%{termo}%", lim=limite)
        return cur.fetchall()

def consultar_cabecalho_venda_oracle(nunota: int):
    """Devolve os dados do cabeçalho de um pedido de venda para popular o modal de edição.
    Retorna tupla (codemp, nome_emp, codparc, nome_parc, codtipvenda, descr_tpv, dtneg, obs)
    ou None se a nota não existir."""
    sql = """
        SELECT c.CODEMP, e.NOMEFANTASIA, c.CODPARC, p.NOMEPARC,
               c.CODTIPVENDA, t.DESCRTIPVENDA, c.DTNEG, c.OBSERVACAO
        FROM   TGFCAB c
        LEFT JOIN TSIEMP e ON e.CODEMP = c.CODEMP
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        LEFT JOIN TGFTPV t ON t.CODTIPVENDA = c.CODTIPVENDA AND t.DHALTER = c.DHTIPVENDA
        WHERE  c.NUNOTA = :n
    """
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, n=int(nunota))
        return cur.fetchone()

def consultar_empresas_oracle(termo: str, limite: int = 10):
    """Busca empresas ativas na TSIEMP."""
    if not termo: return []
    termo = str(termo).strip().upper()
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if termo.isdigit():
            sql = "SELECT DISTINCT CODEMP, NOMEFANTASIA FROM TSIEMP WHERE (CODEMP = :k OR TO_CHAR(CODEMP) LIKE :pfx) AND ROWNUM <= :lim"
            cur.execute(sql, k=int(termo), pfx=f"{termo}%", lim=limite)
        else:
            sql = "SELECT DISTINCT CODEMP, NOMEFANTASIA FROM TSIEMP WHERE UPPER(NOMEFANTASIA) LIKE :q AND ROWNUM <= :lim"
            cur.execute(sql, q=f"%{termo}%", lim=limite)
        return cur.fetchall()

def consultar_tipos_negociacao_oracle(termo: str, limite: int = 10):
    """Busca tipos de negociação ativos na TGFTPV."""
    if not termo: return []
    termo = str(termo).strip().upper()
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if termo.isdigit():
            sql = "SELECT DISTINCT CODTIPVENDA, DESCRTIPVENDA FROM TGFTPV WHERE (CODTIPVENDA = :k OR TO_CHAR(CODTIPVENDA) LIKE :pfx) AND ROWNUM <= :lim"
            cur.execute(sql, k=int(termo), pfx=f"{termo}%", lim=limite)
        else:
            sql = "SELECT DISTINCT CODTIPVENDA, DESCRTIPVENDA FROM TGFTPV WHERE UPPER(DESCRTIPVENDA) LIKE :q AND ROWNUM <= :lim"
            cur.execute(sql, q=f"%{termo}%", lim=limite)
        return cur.fetchall()

def consultar_centros_resultado_oracle(termo: str, limite: int = 10):
    """Busca centros de resultado na TSICUS."""
    if not termo: return []
    termo = str(termo).strip().upper()
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        if termo.isdigit():
            sql = "SELECT DISTINCT CODCENCUS, DESCRCENCUS FROM TSICUS WHERE (CODCENCUS = :k OR TO_CHAR(CODCENCUS) LIKE :pfx) AND ROWNUM <= :lim"
            cur.execute(sql, k=int(termo), pfx=f"{termo}%", lim=limite)
        else:
            sql = "SELECT DISTINCT CODCENCUS, DESCRCENCUS FROM TSICUS WHERE UPPER(DESCRCENCUS) LIKE :q AND ROWNUM <= :lim"
            cur.execute(sql, q=f"%{termo}%", lim=limite)
        return cur.fetchall()


# ==============================================================================
# 💰 Autenticação de Usuários
# Interface para login e controle de acesso, usando o sistema de usuários do Django.
# ==============================================================================

# Configuração básica para garantir que o log apareça no seu terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def autenticar_usuario_sankhya(usuario, senha) -> dict:
    url_api = "http://hfsemear.ddns.net:8180/mge/service.sbr?serviceName=MobileLoginSP.login"
    
    # Montando o envelope XML que o seu Sankhya exige
    xml_payload = f"""
    <serviceRequest serviceName="MobileLoginSP.login">
        <requestBody>
            <NOMUSU>{usuario}</NOMUSU>
            <INTERNO>{senha}</INTERNO>
            <KEEPCONNECTED>N</KEEPCONNECTED>
        </requestBody>
    </serviceRequest>
    """
    
    headers = {
        'Content-Type': 'text/xml; charset=ISO-8859-1',
        'User-Agent': 'Mozilla/5.0'
    }
    
    try:
        # Enviando como DATA (string XML) em vez de JSON
        api_response = requests.post(url_api, data=xml_payload, headers=headers, timeout=15)
        
        # O seu Sankhya responde em XML, então vamos ler o XML
        from xml.etree import ElementTree as ET
        root = ET.fromstring(api_response.content)
        
        status = root.get('status') # Atributo status="1" ou "0"
        
        if status == "1":
            # Sucesso! Agora vamos buscar os dados no Oracle (Fase 2)
            # Mantenha o seu código de SELECT no Oracle aqui abaixo...
            pass 
        else:
            # Falha: Captura a mensagem de erro dentro da tag <statusMessage>
            msg_node = root.find('statusMessage')
            import base64
            # O Sankhya costuma mandar a mensagem em Base64 dentro do CDATA
            try:
                error_msg = base64.b64decode(msg_node.text).decode('iso-8859-1')
            except:
                error_msg = msg_node.text if msg_node is not None else "Usuário ou senha inválidos."
                
            return {'autenticado': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Erro na comunicação XML: {str(e)}")
        return {'autenticado': False, 'error': 'Servidor ERP indisponível.'}

    # =========================================================================
    # FASE 2: BUSCA NO ORACLE (Grupo Principal + Grupos Adicionais TSIGPU)
    # =========================================================================
    sql_usuario = """
        SELECT U.CODUSU, U.NOMEUSU, U.CODGRUPO
        FROM TSIUSU U
        WHERE UPPER(U.NOMEUSU) = UPPER(:u) 
          AND (U.DTLIMACESSO IS NULL OR TRUNC(U.DTLIMACESSO) >= TRUNC(SYSDATE))
    """
    
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql_usuario, u=usuario)
            row = cur.fetchone()
            
            if row:
                codusu, nome, codgrupo_primario = row
                grupos = set()
                
                # 1. Adiciona o grupo principal do usuário
                if codgrupo_primario is not None:
                    grupos.add(str(codgrupo_primario))
                
                # 2. Busca os grupos extras na TSIGPU (ignorando os com data vencida)
                sql_extras = """
                    SELECT CODGRUPO 
                    FROM TSIGPU 
                    WHERE CODUSU = :cod
                      AND (DATAFIM IS NULL OR TRUNC(DATAFIM) >= TRUNC(SYSDATE))
                """
                cur.execute(sql_extras, cod=codusu)
                
                # Adiciona todos os grupos extras no "set" (que evita duplicidades)
                for g in cur.fetchall():
                    grupos.add(str(g[0]))
                
                return {
                    'autenticado': True,
                    'codusu': codusu,
                    'nome': nome,
                    'grupos': list(grupos) # Retorna a lista completa!
                }
            else:
                return {'autenticado': False, 'error': 'Usuário não encontrado ou bloqueado no banco local.'}
                
        except Exception as e:
            logger.error(f"Erro ao buscar grupos do usuário: {e}")
            return {'autenticado': False, 'error': 'Erro de autorização no banco de dados.'}

def alterar_senha_sankhya(codusu, nova_senha):
    """Atualiza a senha INTERNO na TSIUSU usando a criptografia do ERP."""
    if not verificar_permissao_escrita(): return False
    sql = "UPDATE TSIUSU SET INTERNO = STP_CRYPT(:p) WHERE CODUSU = :cod"
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, p=nova_senha, cod=codusu)
        conn.commit()
        return cur.rowcount > 0


# ==============================================================================
# 📦 MÓDULO EXCLUSIVO: ENTRADA (COMPRAS / TOP 11)
# Regras de negócio, cálculos, geração de lote e persistência de dados
# ==============================================================================

def gerar_proximo_numero_unico_cabecalho(conn) -> int:
    """Consulta a TGFCAB e retorna MAX(NUNOTA) + 1."""
    cur = conn.cursor()
    cur.execute("SELECT NVL(MAX(NUNOTA),0) FROM TGFCAB")
    mx = int(cur.fetchone()[0] or 0)
    return mx + 1

def gerar_proxima_sequencia_item(nunota: int) -> int:
    """Consulta a TGFITE e retorna MAX(SEQUENCIA) + 1 para uma nota específica."""
    sql = "SELECT NVL(MAX(SEQUENCIA),0) + 1 FROM TGFITE WHERE NUNOTA = :nunota"
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, nunota=nunota)
        return int(cur.fetchone()[0])

def gerar_codigo_lote_rastreabilidade(data_negociacao, codparc=None, codprod=None) -> str:
    """
    Gera o código de lote no formato: AAMMDD + 'P' + codparc + 'P' + codprod + 'S' + sequencial_do_dia.
    Exemplo: 260317P76P358S01
    """
    if isinstance(data_negociacao, str): 
        data_negociacao = datetime.strptime(data_negociacao, '%Y-%m-%d').date()
    if not isinstance(data_negociacao, _date): 
        raise ValueError('Data inválida para gerar o lote')
    
    prefixo_data = data_negociacao.strftime('%y%m%d')
    str_parc = str(codparc) if codparc is not None else ''
    str_prod = str(codprod) if codprod is not None else ''
    padrao_busca = f"{prefixo_data}P{str_parc}P{str_prod}S"
    
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute("SELECT CODAGREGACAO FROM TGFITE WHERE CODAGREGACAO LIKE :pfx AND CODAGREGACAO IS NOT NULL", pfx=f"{padrao_busca}%")
        lotes_existentes = cur.fetchall()
        
    maior_sequencia = 0
    tamanho_padrao = len(padrao_busca)
    
    for (lote_encontrado,) in lotes_existentes:
        lote_str = (lote_encontrado or '').strip()
        if not lote_str.startswith(padrao_busca): continue
        
        sufixo_numerico = lote_str[tamanho_padrao:]
        try:
            seq_int = int(sufixo_numerico)
            if seq_int > maior_sequencia: 
                maior_sequencia = seq_int
        except Exception: continue
        
    proxima_sequencia = f"{maior_sequencia + 1:02d}"
    return f"{padrao_busca}{proxima_sequencia}"


# --- MANIPULAÇÃO DO CABEÇALHO (TGFCAB) ---

def inserir_cabecalho_nota_banco(dados: dict, simulacao: bool = False, conexao_existente: Optional[Any] = None) -> dict:
    """
    Insere um novo registro na TGFCAB.
    Bypassa validações complexas para focar em performance.
    """
    resultado = {'ok': False, 'executed': False, 'nunota': None}
    gerencia_conexao = conexao_existente is None
    
    if gerencia_conexao and (simulacao or not verificar_permissao_escrita()):
        resultado['error'] = 'Modo simulação ou escrita desabilitada'
        return resultado
        
    campos_obrigatorios = ['CODEMP', 'CODPARC', 'CODTIPOPER', 'CODNAT', 'DTNEG']
    faltando = [c for c in campos_obrigatorios if not dados.get(c)]
    if faltando:
        resultado['error'] = f'Campos obrigatórios faltando: {", ".join(faltando)}'
        return resultado

    def _executar_insercao(conn):
        cur = conn.cursor()
        
        # Busca detalhes da TOP
        cur.execute("""
            SELECT TIPMOV, DHALTER FROM (
                SELECT TIPMOV, DHALTER FROM TGFTOP WHERE CODTIPOPER=:k ORDER BY DHALTER DESC
            ) WHERE ROWNUM=1
        """, k=dados['CODTIPOPER'])
        
        linha_top = cur.fetchone()
        if not linha_top:
            resultado['error'] = f"CODTIPOPER {dados['CODTIPOPER']} não encontrado na TGFTOP"
            return resultado
            
        tipmov, dhtipoper = linha_top
        novo_nunota = gerar_proximo_numero_unico_cabecalho(conn)
        
        colunas = ['NUNOTA', 'CODEMP', 'CODEMPNEGOC', 'CODPARC', 'CODTIPOPER', 'DHTIPOPER', 'TIPMOV',
                   'CODNAT', 'DTNEG', 'DTMOV', 'DTENTSAI', 'HRMOV', 'NUMNOTA', 'PENDENTE', 'DTALTER',
                   'TIPFRETE', 'CIF_FOB', 'ISSRETIDO', 'APROVADO', 'IRFRETIDO', 'DIGITAL', 'CANCELADO', 
                   'AD_NUMPEDIDOORIG']
               
        valores = [':NUNOTA', ':CODEMP', ':CODEMP', ':CODPARC', ':CODTIPOPER', ':DHTIPOPER', ':TIPMOV',
                   ':CODNAT', 'TO_DATE(:DTNEG,\'DD/MM/YYYY\')', 'TO_DATE(:DTMOV,\'DD/MM/YYYY\')', 
                   'TO_DATE(:DTENTSAI,\'DD/MM/YYYY\')', 'TO_CHAR(SYSDATE, \'HH24MISS\')', ':NUMNOTA', 
                   ':PENDENTE', 'SYSDATE',
                   ':TIPFRETE', ':CIF_FOB', ':ISSRETIDO', ':APROVADO', ':IRFRETIDO', ':DIGITAL', ':CANCELADO', 
                   ':AD_NUMPEDIDOORIG']
        
        binds = {
            'NUNOTA': novo_nunota, 
            'CODEMP': int(dados['CODEMP']), 
            'CODPARC': int(dados['CODPARC']), 
            'CODTIPOPER': int(dados['CODTIPOPER']),
            'DHTIPOPER': dhtipoper, 
            'TIPMOV': tipmov, 
            'CODNAT': int(dados['CODNAT']), 
            'DTNEG': dados['DTNEG'],
            'DTMOV': dados.get('DTMOV') or dados['DTNEG'], 
            'DTENTSAI': dados.get('DTENTSAI') or dados['DTNEG'], 
            'NUMNOTA': dados.get('NUMNOTA') or novo_nunota,
            'PENDENTE': dados.get('PENDENTE', 'S'), 
            'TIPFRETE': 'N', 'CIF_FOB': 'C', 'ISSRETIDO': 'N', 'APROVADO': 'N', 
            'IRFRETIDO': 'S', 'DIGITAL': 'N', 'CANCELADO': 'N',
            'AD_NUMPEDIDOORIG': int(dados.get('AD_NUMPEDIDOORIG') or novo_nunota)
        }
        
        if dados.get('NUMPEDIDO'):
            colunas.append('NUMPEDIDO')
            valores.append(':NUMPEDIDO')
            binds['NUMPEDIDO'] = int(dados['NUMPEDIDO'])

        if dados.get('CODTIPVENDA'):
            cur.execute("""
                SELECT DHALTER FROM (
                    SELECT DHALTER FROM TGFTPV WHERE CODTIPVENDA=:k ORDER BY DHALTER DESC
                ) WHERE ROWNUM=1
            """, k=int(dados['CODTIPVENDA']))
            linha_tpv = cur.fetchone()
            if not linha_tpv:
                resultado['error'] = f"CODTIPVENDA {dados['CODTIPVENDA']} não encontrado na TGFTPV"
                return resultado

            colunas.append('CODTIPVENDA'); valores.append(':CODTIPVENDA')
            binds['CODTIPVENDA'] = int(dados['CODTIPVENDA'])
            colunas.append('DHTIPVENDA'); valores.append(':DHTIPVENDA')
            binds['DHTIPVENDA'] = linha_tpv[0]

        if dados.get('CODCENCUS'):
            colunas.append('CODCENCUS')
            valores.append(':CODCENCUS')
            binds['CODCENCUS'] = int(dados['CODCENCUS'])
            
        if observacao := dados.get('OBSERVACAO') or dados.get('OBS'):
            colunas.append('OBSERVACAO')
            valores.append(':OBSERVACAO')
            binds['OBSERVACAO'] = observacao
        
        sql = f"INSERT INTO TGFCAB ({', '.join(colunas)}) VALUES ({', '.join(valores)})"
        cur.execute(sql, binds)
        
        if gerencia_conexao: conn.commit()
        resultado.update({'ok': True, 'executed': True, 'nunota': novo_nunota, 'sql': sql})
        return resultado

    try:
        if gerencia_conexao:
            with obter_conexao_oracle() as conn_aberta: return _executar_insercao(conn_aberta)
        return _executar_insercao(conexao_existente)
    except Exception as e:
        if gerencia_conexao and 'conn_aberta' in locals(): conn_aberta.rollback()
        resultado['error'] = str(e)
        return resultado

def atualizar_cabecalho_venda_banco(dados: dict, simulacao: bool = False) -> dict:
    """Atualiza o cabeçalho de um Pedido de Venda (TOP 34).

    Função dedicada (não reutiliza atualizar_cabecalho_nota_banco) para:
      1) gravar DHTIPVENDA com a DHALTER mais recente de TGFTPV — o trigger
         TRG_INC_TGFCAB exige esse par CODTIPVENDA/DHTIPVENDA coerente;
      2) evitar a 'auto-cura de origem' (AD_NUMPEDIDOORIG) que só faz sentido
         para Entrada/Classificação.
    """
    resultado = {'ok': False, 'executed': False}
    if simulacao or not verificar_permissao_escrita():
        resultado['error'] = 'Modo simulação ou escrita desabilitada'
        return resultado

    try: nunota = int(dados['NUNOTA'])
    except (KeyError, TypeError, ValueError):
        resultado['error'] = 'NUNOTA obrigatório'
        return resultado

    colunas_set = []
    binds = {'NUNOTA': nunota}

    for campo in ('CODEMP', 'CODPARC'):
        if dados.get(campo) is not None:
            colunas_set.append(f"{campo}=:{campo}")
            binds[campo] = int(dados[campo])

    if dados.get('OBSERVACAO') is not None:
        colunas_set.append('OBSERVACAO=:OBSERVACAO')
        binds['OBSERVACAO'] = dados['OBSERVACAO']

    if dados.get('DTNEG'):
        val_str = str(dados['DTNEG'])
        if len(val_str) == 10 and val_str[2] == '/':
            val_str = f"{val_str[6:10]}-{val_str[3:5]}-{val_str[0:2]}"
        colunas_set.append("DTNEG=TO_DATE(:DTNEG, 'YYYY-MM-DD')")
        binds['DTNEG'] = val_str

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # CODTIPVENDA/DHTIPVENDA: par obrigatório exigido pelo trigger
            if dados.get('CODTIPVENDA') is not None:
                cur.execute("""
                    SELECT DHALTER FROM (
                        SELECT DHALTER FROM TGFTPV WHERE CODTIPVENDA=:k ORDER BY DHALTER DESC
                    ) WHERE ROWNUM=1
                """, k=int(dados['CODTIPVENDA']))
                linha_tpv = cur.fetchone()
                if not linha_tpv:
                    resultado['error'] = f"CODTIPVENDA {dados['CODTIPVENDA']} não encontrado na TGFTPV"
                    return resultado
                colunas_set.append('CODTIPVENDA=:CODTIPVENDA')
                binds['CODTIPVENDA'] = int(dados['CODTIPVENDA'])
                colunas_set.append('DHTIPVENDA=:DHTIPVENDA')
                binds['DHTIPVENDA'] = linha_tpv[0]

            if not colunas_set:
                resultado['error'] = 'Nenhum campo válido para atualizar'
                return resultado

            sql = f"UPDATE TGFCAB SET {', '.join(colunas_set)} WHERE NUNOTA=:NUNOTA"
            cur.execute(sql, binds)
            conn.commit()
            resultado.update({'ok': True, 'executed': True, 'sql': sql})
            return resultado
    except Exception as e:
        resultado['error'] = str(e)
        return resultado


def atualizar_cabecalho_nota_banco(dados: dict, simulacao: bool = False) -> dict:
    """Atualiza dados do cabeçalho existente com Auto-Cura de Origem."""
    if simulacao or not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}
        
    try: nunota = int(dados.get('NUNOTA'))
    except Exception: return {'ok': False, 'errors': ['NUNOTA obrigatório']}

    colunas_set = []
    binds = {'NUNOTA': nunota}

    campos_int = ['NUMNOTA', 'CODEMP', 'CODPARC', 'CODTIPOPER', 'CODNAT', 'CODCENCUS']
    for campo in campos_int:
        if dados.get(campo) is not None:
            colunas_set.append(f"{campo}=:{campo}")
            binds[campo] = dados[campo]
            
    if dados.get('OBSERVACAO') is not None:
        colunas_set.append('OBSERVACAO=:OBSERVACAO')
        binds['OBSERVACAO'] = dados['OBSERVACAO']
        
    for campo_data in ('DTNEG','DTMOV','DTENTSAI'):
        if dados.get(campo_data):
            try:
                val_str = str(dados[campo_data])
                if len(val_str) == 10 and val_str[2] == '/':
                    val_str = f"{val_str[6:10]}-{val_str[3:5]}-{val_str[0:2]}" # DD/MM/YYYY para YYYY-MM-DD
                colunas_set.append(f"{campo_data}=TO_DATE(:{campo_data}, 'YYYY-MM-DD')")
                binds[campo_data] = val_str
            except Exception: pass

    if not colunas_set:
        return {'ok': False, 'errors': ['Nenhuma coluna válida para atualizar']}

    sql = f"UPDATE TGFCAB SET {', '.join(colunas_set)} WHERE NUNOTA=:NUNOTA"
    
    with obter_conexao_oracle() as conn:
        try:
            cur = conn.cursor()
            
            # =====================================================================
            # 🔥 AUTO-CURA DO CABEÇALHO: Busca a origem real através dos lotes
            # =====================================================================
            cur.execute("""
                SELECT MIN(AD_NUMPEDIDOORIG) 
                FROM TGFITE 
                WHERE CODAGREGACAO IN (SELECT CODAGREGACAO FROM TGFITE WHERE NUNOTA = :n)
                  AND AD_NUMPEDIDOORIG IS NOT NULL
            """, n=nunota)
            res_orig = cur.fetchone()
            
            origem_real = None
            if res_orig and res_orig[0]:
                origem_real = int(res_orig[0])
            else:
                # Se a nota não tem itens ainda, verifica se ela já tem uma origem gravada. 
                # Se estiver vazia, assume ela mesma (comum para TOP 11 nova).
                cur.execute("SELECT AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
                res_atual = cur.fetchone()
                if not res_atual or not res_atual[0]:
                    origem_real = nunota
            
            if origem_real:
                sql_final = sql.replace(" WHERE NUNOTA=:NUNOTA", ", AD_NUMPEDIDOORIG=:AUTO_ORIG WHERE NUNOTA=:NUNOTA")
                binds['AUTO_ORIG'] = origem_real
            else:
                sql_final = sql
            # =====================================================================
            
            cur.execute(sql_final, binds)
            conn.commit()
            return {'ok': True, 'executed': True, 'sql': sql_final}
        except Exception as e:
            return {'ok': False, 'executed': False, 'db_error': {'message': str(e)}}

def recalcular_totais_nota_banco(nunota: int, conexao_existente=None) -> dict:
    """
    Soma QTDNEG e VLRTOT de todos os itens da TGFITE e atualiza VLRNOTA e QTDVOL no Cabeçalho.
    Se não houver itens restantes, deleta o cabeçalho para não ficar órfão.
    """
    if not nunota: return {'ok': False, 'error': 'NUNOTA inválido'}

    # Separamos a execução SQL pura para poder reaproveitar com ou sem conexão existente
    def _executar(conn):
        cur = conn.cursor()
        cur.execute("SELECT NVL(SUM(VLRTOT), 0), NVL(SUM(QTDNEG), 0), COUNT(*) FROM TGFITE WHERE NUNOTA = :n", n=nunota)
        vlr_total, qtd_total, total_itens = cur.fetchone()

        if int(total_itens) == 0:
            cur.execute("DELETE FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
            return {'ok': True, 'cab_deleted': True}
        else:
            cur.execute("UPDATE TGFCAB SET VLRNOTA = :v, QTDVOL = :q WHERE NUNOTA = :n", v=float(vlr_total), q=float(qtd_total), n=nunota)
            return {'ok': True, 'vlrnota': float(vlr_total), 'qtdvol': float(qtd_total), 'cab_deleted': False}

    try:
        if conexao_existente is None:
            # Uso correto do Context Manager (Evita o erro DPY-1001)
            with obter_conexao_oracle() as conn:
                res = _executar(conn)
                conn.commit()
                return res
        else:
            # Usa a conexão que já veio aberta de outra função (ex: api_atualizar_preco_comercial)
            return _executar(conexao_existente)
    except Exception as e:
        if conexao_existente is None and 'conn' in locals():
            conn.rollback()
        return {'ok': False, 'error': str(e)}

def excluir_nota_completa_banco(nunota: int, simulacao: bool = False) -> dict:
    """Deleta todos os itens na TGFITE e logo após deleta o cabeçalho na TGFCAB."""
    resultado = {'ok': False, 'executed': False, 'deleted_itens': 0, 'deleted_cab': 0, 'errors': []}
    
    if simulacao or not verificar_permissao_escrita():
        resultado['ok'] = True; return resultado

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA=:n", n=int(nunota))
            resultado['deleted_itens'] = int(cur.rowcount or 0)
            
            cur.execute("DELETE FROM TGFCAB WHERE NUNOTA=:n", n=int(nunota))
            resultado['deleted_cab'] = int(cur.rowcount or 0)
            
            conn.commit()
            resultado['ok'] = True
            resultado['executed'] = resultado['deleted_cab'] > 0
            return resultado
    except Exception as e:
        resultado['errors'].append(str(e))
        return resultado


# --- MANIPULAÇÃO DOS ITENS (TGFITE) ---

def inserir_item_nota_banco(dados: dict, simulacao: bool = False, conexao_existente=None, codusu_logado=None, gerar_lote_auto: bool = True) -> dict:
    """Insere um novo produto/item associado a uma nota."""
    resultado = {'ok': False, 'executed': False, 'nunota': None, 'sequencia': None}
    gerencia_conexao = conexao_existente is None
    
    if gerencia_conexao and (simulacao or not verificar_permissao_escrita()):
        resultado['error'] = 'Modo simulação ou escrita desabilitada'
        return resultado
        
    try:
        nunota = int(dados['NUNOTA'])
        codprod = int(dados['CODPROD'])
        qtdneg = float(dados['QTDNEG'])
        vlrunit = float(dados.get('VLRUNIT', 0))
    except (KeyError, ValueError, TypeError):
        resultado['error'] = 'Campos NUNOTA, CODPROD e QTDNEG são obrigatórios'
        return resultado

    def _executar(conn):
        cur = conn.cursor()
        colunas_tabela = _obter_colunas_da_tabela(conn, 'TGFITE')

        cur.execute("SELECT CODEMP, DTNEG, CODPARC, AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA=:n", n=nunota)
        cab = cur.fetchone()
        if not cab:
            resultado['error'] = 'Cabeçalho NUNOTA não encontrado'
            return resultado
            
        codemp, dtneg, codparc, ad_numpedidoorig = cab
        sequencia = gerar_proxima_sequencia_item(nunota)
        
        peso = dados.get('PESO') or 0
        codvol = str(dados.get('CODVOL', 'UN')).strip().upper()
        codlocalorig = int(dados.get('CODLOCALORIG', 101))
        observacao = dados.get('OBSERVACAO') or dados.get('OBS')
        geraproducao = dados.get('GERAPRODUCAO') or dados.get('geraproducao')
        
        codagregacao = dados.get('CODAGREGACAO') or dados.get('LOTE')
        if not codagregacao and gerar_lote_auto:
            try:
                # Formata a data como YYMMDD (ex: 260413)
                aammdd = dtneg.strftime('%y%m%d') if hasattr(dtneg, 'strftime') else datetime.now().strftime('%y%m%d')

                # 🔥 AJUSTE AQUI: :02d garante que o número tenha pelo menos 2 dígitos (1 vira 01)
                seq_formatada = f"{sequencia:02d}"

                # Gera o lote: NUNOTA + S + SEQUENCIA(00) + D + DATA
                codagregacao = f"{nunota}S{seq_formatada}D{aammdd}"
            except Exception:
                pass

        # =====================================================================
        # 🔥 FIX TOP 26: HERANÇA AUTOMÁTICA DA ORIGEM PELO LOTE (CODAGREGACAO)
        # =====================================================================
        if codagregacao:
            # Pergunta pro banco qual foi a nota RAIZ que originou esse Lote
            cur.execute("""
                SELECT MIN(AD_NUMPEDIDOORIG) 
                FROM TGFITE 
                WHERE CODAGREGACAO = :l 
                  AND AD_NUMPEDIDOORIG IS NOT NULL
            """, l=str(codagregacao))
            res_origem = cur.fetchone()
            
            if res_origem and res_origem[0]:
                origem_real = int(res_origem[0])
                
                # Se o cabeçalho atual (ex: TOP 26 vazia) está com a origem errada, corrige ele na hora!
                if ad_numpedidoorig != origem_real:
                    ad_numpedidoorig = origem_real
                    cur.execute("UPDATE TGFCAB SET AD_NUMPEDIDOORIG = :o WHERE NUNOTA = :n", 
                                o=origem_real, n=nunota)
        # =====================================================================

        vlrtot = round(float(qtdneg) * float(vlrunit), 2)
        
        colunas_sql = ['NUNOTA', 'SEQUENCIA', 'CODEMP', 'CODPROD', 'QTDNEG', 'VLRUNIT', 'VLRTOT', 'AD_NUMPEDIDOORIG']
        valores_sql = [':NUNOTA', ':SEQUENCIA', ':CODEMP', ':CODPROD', ':QTDNEG', ':VLRUNIT', ':VLRTOT', ':AD_NUMPEDIDOORIG']
        binds = {'NUNOTA': nunota, 'SEQUENCIA': sequencia, 'CODEMP': codemp, 'CODPROD': codprod, 
                 'QTDNEG': qtdneg, 'VLRUNIT': vlrunit, 'VLRTOT': vlrtot, 'AD_NUMPEDIDOORIG': ad_numpedidoorig}

        if codusu_logado and 'CODUSUULTALTER' in colunas_tabela:
            colunas_sql.append('CODUSUULTALTER')
            valores_sql.append(':codusu_log')
            binds['codusu_log'] = int(codusu_logado)

        qtdconferida = dados.get('QTDCONFERIDA') or qtdneg
        if 'QTDCONFERIDA' in colunas_tabela:
            colunas_sql.append('QTDCONFERIDA'); valores_sql.append(':QTDCONFERIDA'); binds['QTDCONFERIDA'] = float(qtdconferida)
            
        if 'PESO' in colunas_tabela:
            colunas_sql.append('PESO'); valores_sql.append(':PESO'); binds['PESO'] = float(peso)
            
        if 'CODVOL' in colunas_tabela:
            colunas_sql.append('CODVOL'); valores_sql.append(':CODVOL'); binds['CODVOL'] = codvol
        
        codvolparc = dados.get('CODVOLPARC')
        if codvolparc and 'CODVOLPARC' in colunas_tabela:
            colunas_sql.append('CODVOLPARC'); valores_sql.append(':CODVOLPARC'); binds['CODVOLPARC'] = str(codvolparc).strip().upper()
            
        if 'CODLOCALORIG' in colunas_tabela:
            colunas_sql.append('CODLOCALORIG'); valores_sql.append(':CODLOCALORIG'); binds['CODLOCALORIG'] = codlocalorig

        if codagregacao and 'CODAGREGACAO' in colunas_tabela:
            colunas_sql.append('CODAGREGACAO'); valores_sql.append(':CODAGREGACAO'); binds['CODAGREGACAO'] = str(codagregacao)

        if observacao and 'OBSERVACAO' in colunas_tabela:
            colunas_sql.append('OBSERVACAO'); valores_sql.append(':OBSERVACAO'); binds['OBSERVACAO'] = str(observacao)

        if geraproducao and 'GERAPRODUCAO' in colunas_tabela:
            colunas_sql.append('GERAPRODUCAO'); valores_sql.append(':GERAPRODUCAO'); binds['GERAPRODUCAO'] = str(geraproducao).strip().upper()

        sql = f"INSERT INTO TGFITE ({', '.join(colunas_sql)}) VALUES ({', '.join(valores_sql)})"
        cur.execute(sql, binds)
        
        if gerencia_conexao: conn.commit()
        resultado.update({'ok': True, 'executed': True, 'nunota': nunota, 'sequencia': sequencia})
        return resultado

    try:
        if gerencia_conexao:
            with obter_conexao_oracle() as c: return _executar(c)
        return _executar(conexao_existente)
    except Exception as e:
        if gerencia_conexao and 'c' in locals(): c.rollback()
        resultado['error'] = str(e)
        return resultado

def atualizar_item_nota_banco(dados: dict, simulacao: bool = False, conexao_existente=None) -> dict:
    """Atualiza dados de um item existente."""
    if simulacao or not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    binds = {}
    colunas_set = []

    try:
        binds['NUNOTA'] = int(dados.get('NUNOTA'))
        binds['SEQUENCIA'] = int(dados.get('SEQUENCIA'))
    except Exception:
        return {'ok': False, 'errors': ['NUNOTA e SEQUENCIA obrigatórios']}

    if dados.get('CODPROD') is not None:
        colunas_set.append('CODPROD=:CODPROD'); binds['CODPROD'] = int(dados['CODPROD'])
    if dados.get('QTDNEG') is not None:
        colunas_set.append('QTDNEG=:QTDNEG'); binds['QTDNEG'] = float(dados['QTDNEG'])
    if dados.get('PESO') is not None:
        colunas_set.append('PESO=:PESO'); binds['PESO'] = float(dados['PESO'])
    if dados.get('VLRUNIT') is not None:
        colunas_set.append('VLRUNIT=:VLRUNIT'); binds['VLRUNIT'] = float(dados['VLRUNIT'])
    if dados.get('VLRTOT') is not None:
        colunas_set.append('VLRTOT=:VLRTOT'); binds['VLRTOT'] = float(dados['VLRTOT'])
    elif 'QTDNEG' in binds and 'VLRUNIT' in binds:
        colunas_set.append('VLRTOT=:VLRTOT'); binds['VLRTOT'] = round(binds['QTDNEG'] * binds['VLRUNIT'], 2)
        
    if dados.get('QTDCONFERIDA') is not None:
        colunas_set.append('QTDCONFERIDA=:QTDCONFERIDA'); binds['QTDCONFERIDA'] = float(dados['QTDCONFERIDA'])
    if dados.get('CODVOL') is not None:
        colunas_set.append('CODVOL=:CODVOL'); binds['CODVOL'] = str(dados['CODVOL']).strip().upper()
    if dados.get('CODVOLPARC') is not None:
        colunas_set.append('CODVOLPARC=:CODVOLPARC'); binds['CODVOLPARC'] = str(dados['CODVOLPARC']).strip().upper()
    if dados.get('OBSERVACAO') is not None:
        colunas_set.append('OBSERVACAO=:OBSERVACAO'); binds['OBSERVACAO'] = dados['OBSERVACAO']
        
    gp = dados.get('GERAPRODUCAO') or dados.get('geraproducao')
    if gp is not None:
        colunas_set.append('GERAPRODUCAO=:GERAPRODUCAO'); binds['GERAPRODUCAO'] = str(gp).strip().upper()

    if dados.get('AD_NUMPEDIDOORIG') is not None:
        colunas_set.append('AD_NUMPEDIDOORIG=:AD_NUMPEDIDOORIG'); binds['AD_NUMPEDIDOORIG'] = int(dados['AD_NUMPEDIDOORIG'])

    if dados.get('CODAGREGACAO') is not None:
        colunas_set.append('CODAGREGACAO=:CODAGREGACAO'); binds['CODAGREGACAO'] = str(dados['CODAGREGACAO']).strip()

    if not colunas_set:
        return {'ok': False, 'errors': ['Nenhuma coluna informada para atualizar']}

    sql = f"UPDATE TGFITE SET {', '.join(colunas_set)} WHERE NUNOTA=:NUNOTA AND SEQUENCIA=:SEQUENCIA"
    
    gerencia_conexao = conexao_existente is None
    
    def _exec_update(c):
        cur = c.cursor()
        sql_final = sql
        
        # 🔥 AUTO-CURA: Se for editar um item antigo da TOP 26 que está com a origem errada, ele arruma!
        cur.execute("SELECT CODAGREGACAO, AD_NUMPEDIDOORIG FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s", n=binds['NUNOTA'], s=binds['SEQUENCIA'])
        row_atual = cur.fetchone()
        
        if row_atual and row_atual[0]:
            lote_atual = row_atual[0]
            cur.execute("SELECT MIN(AD_NUMPEDIDOORIG) FROM TGFITE WHERE CODAGREGACAO = :l AND AD_NUMPEDIDOORIG IS NOT NULL", l=lote_atual)
            origem_real = cur.fetchone()
            
            if origem_real and origem_real[0]:
                orig_val = int(origem_real[0])
                if orig_val != row_atual[1] and 'AD_NUMPEDIDOORIG' not in binds:
                    sql_final = sql_final.replace(" WHERE ", ", AD_NUMPEDIDOORIG = :AUTO_ORIG WHERE ")
                    binds['AUTO_ORIG'] = orig_val
                    # Conserta o Cabeçalho por tabela
                    cur.execute("UPDATE TGFCAB SET AD_NUMPEDIDOORIG = :o WHERE NUNOTA = :n", o=orig_val, n=binds['NUNOTA'])
        
        cur.execute(sql_final, binds)
        if gerencia_conexao: c.commit()
        return {'ok': True, 'executed': True, 'sql': sql_final}

    try:
        if gerencia_conexao:
            with obter_conexao_oracle() as c: return _exec_update(c)
        return _exec_update(conexao_existente)
    except Exception as e:
        if gerencia_conexao and 'c' in locals(): c.rollback()
        return {'ok': False, 'executed': False, 'db_error': {'message': str(e)}}

def excluir_itens_nota_banco(nunota: int, sequencias: list[int], simulacao: bool = False) -> dict:
    """Exclui múltiplos itens de uma vez e retorna a quantidade de linhas afetadas."""
    resultado = {'ok': False, 'executed': False, 'deleted': 0, 'errors': []}
    if simulacao or not verificar_permissao_escrita():
        resultado['ok'] = True; return resultado

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            count = 0
            # Deletar de trás pra frente evita quebra de integridade caso hajam dependências
            for seq in sorted(sequencias, reverse=True):
                cur.execute("DELETE FROM TGFITE WHERE NUNOTA=:n AND SEQUENCIA=:s", n=int(nunota), s=int(seq))
                count += cur.rowcount or 0
            conn.commit()
            resultado.update({'ok': True, 'executed': True, 'deleted': count})
            return resultado
    except Exception as e:
        resultado['errors'].append(str(e))
        return resultado

# --- LISTAGENS DE TELA ---

def listar_notas_compra_paginado(limite: int = 50, offset: int = 0, **kwargs):
    """Busca o cabeçalho das notas de Entrada com filtros (Data, Parceiro, Nro) e paginação."""
    where = ["c.CODTIPOPER = :top"]
    binds = {"top": obter_parametros_globais()['TOP_ENTRADA']}
    
    if kwargs.get('date_start') and kwargs.get('date_end'):
        where.append("TRUNC(c.DTNEG) BETWEEN TO_DATE(:ds, 'YYYY-MM-DD') AND TO_DATE(:de, 'YYYY-MM-DD')")
        binds['ds'] = kwargs['date_start']; binds['de'] = kwargs['date_end']
    elif kwargs.get('days') is not None:
        where.append("c.DTNEG >= SYSDATE - :days")
        binds['days'] = int(kwargs['days'])
        
    # ==========================================
    # CORREÇÃO: Pesquisa parcial de Pedido/NUNOTA
    # ==========================================
    if kwargs.get('nunota_ini'):
        # Converte a chave primária para texto e busca em qualquer parte
        where.append("TO_CHAR(c.NUNOTA) LIKE '%' || :nunota || '%'")
        # Passa o valor como string pura, sem tentar converter para int
        binds['nunota'] = str(kwargs['nunota_ini']).strip()
        
    if kwargs.get('codparc'):
        where.append("c.CODPARC = :codparc")
        binds['codparc'] = int(kwargs['codparc'])
        
    sql_base = (
        "SELECT c.NUNOTA, c.NUMNOTA, c.DTNEG, c.CODPARC, p.NOMEPARC, NVL(SUM(i.VLRTOT),0) VLRTOTAL "
        "  FROM TGFCAB c "
        "  LEFT JOIN TGFITE i ON i.NUNOTA = c.NUNOTA "
        "  LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC "
        f" WHERE {' AND '.join(where)} "
        " GROUP BY c.NUNOTA, c.NUMNOTA, c.DTNEG, c.CODPARC, p.NOMEPARC"
    )
    
    sql_paginado = (
        "SELECT NUNOTA, NUMNOTA, DTNEG, CODPARC, NOMEPARC, VLRTOTAL FROM ("
        f" SELECT t.*, ROW_NUMBER() OVER (ORDER BY t.DTNEG DESC, t.NUNOTA DESC) rn FROM ({sql_base}) t"
        ") WHERE rn BETWEEN :start_row AND :end_row"
    )
    
    binds['start_row'] = offset + 1
    binds['end_row'] = offset + limite

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_paginado, binds)
        return cur.fetchall()

def listar_itens_por_nota(nunota: int):

    """Busca todos os itens de uma nota específica (Para exibir no grid)."""
    sql = (
        "SELECT i.CODAGREGACAO, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, i.CODVOL, i.QTDNEG, "
        "       i.PESO, i.VLRUNIT, i.VLRTOT, i.OBSERVACAO, i.GERAPRODUCAO, i.QTDCONFERIDA, i.CODVOLPARC,"
        "       i.AD_SIMQTD1, i.AD_SIMVLR1, i.AD_SIMQTD2, i.AD_SIMVLR2, i.AD_SIMQTDDESC "
        "  FROM TGFITE i "
        "  LEFT JOIN TGFPRO p ON p.CODPROD = i.CODPROD "
        " WHERE i.NUNOTA = :nunota ORDER BY i.SEQUENCIA"
    )
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, nunota=nunota)
        return cur.fetchall()
    
# ==============================================================================
# 🧪 3. MÓDULO EXCLUSIVO: CLASSIFICAÇÃO (IAGRO / TOP 26)
# Interface entre Lotes In Natura (TOP 11) e Produtos Acabados (TOP 26)
# ==============================================================================

def listar_lotes_para_classificacao(filtros: dict):
    sql_base = """
        WITH Lotes_Top11 AS (
            SELECT 
                i.CODAGREGACAO, 
                MAX(i.NUNOTA) AS NUNOTA_ORIGEM, 
                MAX(c11.DTNEG) AS DTNEG,
                MAX(c11.CODPARC) AS CODPARC,
                MAX(p.NOMEPARC) AS NOMEPARC, 
                MAX(pr.DESCRPROD) AS DESCRPROD, 
                SUM(i.QTDNEG) AS QTD_IN_NATURA,
                SUM(i.QTDCONFERIDA) AS QTD_CX,      -- 👈 NOVO
                MAX(i.PESO) AS PESO_UNIT            -- 👈 NOVO
            FROM TGFITE i
            INNER JOIN TGFCAB c11 ON i.NUNOTA = c11.NUNOTA
            LEFT JOIN TGFPAR p   ON c11.CODPARC = p.CODPARC
            LEFT JOIN TGFPRO pr  ON i.CODPROD = pr.CODPROD
            WHERE i.CODAGREGACAO IS NOT NULL
              AND c11.CODTIPOPER = 11
              AND i.GERAPRODUCAO = 'S'
            GROUP BY i.CODAGREGACAO
        ),
        Status_Top26 AS (
            SELECT 
                i26.CODAGREGACAO,
                CASE 
                    WHEN COUNT(c26.NUNOTA) > 0 AND MIN(c26.PENDENTE) = 'N' AND MAX(c26.PENDENTE) = 'N' THEN 'VERDE'
                    WHEN COUNT(c26.NUNOTA) > 0 THEN 'AMARELO'
                END AS STATUS_COR
            FROM TGFCAB c26
            INNER JOIN TGFITE i26 ON c26.NUNOTA = i26.NUNOTA
            WHERE c26.CODTIPOPER = 26 
              AND c26.STATUSNOTA <> 'E'
            GROUP BY i26.CODAGREGACAO
        )
        SELECT 
            t11.CODAGREGACAO,
            t11.NUNOTA_ORIGEM,
            t11.DTNEG,
            t11.NOMEPARC,
            t11.DESCRPROD,
            t11.QTD_IN_NATURA,
            NVL(s26.STATUS_COR, 'VERMELHO') AS STATUS_COR,
            t11.CODPARC,
            t11.QTD_CX,     -- Index 8
            t11.PESO_UNIT   -- Index 9
        FROM Lotes_Top11 t11
        LEFT JOIN Status_Top26 s26 ON t11.CODAGREGACAO = s26.CODAGREGACAO
    """

    binds = {}
    sql_filtros = f"SELECT * FROM ({sql_base}) t WHERE 1=1"

    if filtros.get('lote'):
        sql_filtros += " AND UPPER(t.CODAGREGACAO) LIKE :lote"
        binds['lote'] = f"%{str(filtros['lote']).upper()}%"
    if filtros.get('nunota_ini'):
        sql_filtros += " AND TO_CHAR(t.NUNOTA_ORIGEM) LIKE :nunota"
        binds['nunota'] = f"%{filtros['nunota_ini']}%"
    if filtros.get('fabricante'):
        sql_filtros += " AND UPPER(t.DESCRPROD) LIKE :fab"
        binds['fab'] = f"%{str(filtros['fabricante']).upper()}%"
    if filtros.get('codparc'):
        sql_filtros += " AND t.CODPARC = :p_codparc"
        binds['p_codparc'] = filtros['codparc']

    if filtros.get('date_start') and filtros.get('date_end'):
        sql_filtros += " AND TRUNC(t.DTNEG) BETWEEN TO_DATE(:dstart, 'YYYY-MM-DD') AND TO_DATE(:dend, 'YYYY-MM-DD')"
        binds['dstart'] = filtros['date_start']
        binds['dend'] = filtros['date_end']
    else:
        sql_filtros += " AND t.DTNEG >= SYSDATE - 60"

    status_list = [s.upper() for s in filtros.get('status_list', [])]
    
    if 'VERDE' in status_list:
        ordem_sql = "a.DTNEG DESC, a.NUNOTA_ORIGEM DESC"
    else:
        ordem_sql = "a.DTNEG ASC, a.NUNOTA_ORIGEM ASC"

    if status_list:
        placeholders = [f":s{i}" for i in range(len(status_list))]
        sql_filtros += f" AND t.STATUS_COR IN ({', '.join(placeholders)})"
        for i, s in enumerate(status_list):
            binds[f"s{i}"] = s.upper()

    limit = int(filtros.get('limit', 50))
    page = int(filtros.get('page', 1))
    offset = (page - 1) * limit

    sql_paginado = f"""
        SELECT * FROM (
            SELECT a.*, ROW_NUMBER() OVER (ORDER BY {ordem_sql}) AS rn
            FROM ({sql_filtros}) a
        ) WHERE rn BETWEEN :start_row AND :end_row
    """
    binds['start_row'] = offset + 1
    binds['end_row'] = offset + limit

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_paginado, binds)
        return cur.fetchall()

def obter_balanco_massa_lote(nunota: int, lote: str):
    """
    Calcula o resumo usando NUNOTA (ID da nota) e CODAGREGACAO (Texto do lote).
    Não utiliza o campo AD_NUNOTA_ORIGEM.
    """
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Busca dados da Entrada (TOP 11) - Usa o NUNOTA da nota de origem
            sql_entrada = """
                SELECT NVL(SUM(QTDNEG), 0), NVL(SUM(AD_QTDAVARIA), 0)
                FROM TGFITE 
                WHERE NUNOTA = :n AND CODAGREGACAO = :l AND GERAPRODUCAO = 'S'
            """
            cur.execute(sql_entrada, n=nunota, l=lote)
            row_in = cur.fetchone()
            in_natura, descarte = (float(row_in[0] or 0), float(row_in[1] or 0))

            # 2. Busca o que já foi classificado (TOP 26) - Usa o texto do Lote como ponte
            sql_classificado = """
                SELECT SUM(NVL(i.QTDNEG, 0))
                FROM TGFITE i
                JOIN TGFCAB c ON i.NUNOTA = c.NUNOTA
                WHERE i.CODAGREGACAO = :l AND c.CODTIPOPER = 26 AND c.STATUSNOTA <> 'E'
            """
            cur.execute(sql_classificado, l=lote)
            row_cl = cur.fetchone()
            classificado = float(row_cl[0] or 0)

            estoque = in_natura - (classificado + descarte)
            rendimento = round((classificado / in_natura * 100), 2) if in_natura > 0 else 0
            
            return {
                "in_natura": in_natura,
                "classificado": classificado,
                "descarte": descarte,
                "estoque": estoque,
                "rendimento": rendimento
            }
    except Exception as e:
        logger.error("Erro Oracle no Resumo: %s", e)
        return {"in_natura": 0, "classificado": 0, "descarte": 0, "estoque": 0, "rendimento": 0}    

def atualizar_descarte_origem(nunota_origem: int, codagregacao: str, qtd_descarte: float):
    """
    Grava a quantidade de descarte no campo AD_QTDAVARIA do item original (TOP 11).
    """
    if not verificar_permissao_escrita():
        return False
        
    sql = """
        UPDATE TGFITE 
        SET AD_QTDAVARIA = :qtd 
        WHERE NUNOTA = :nunota AND CODAGREGACAO = :lote AND GERAPRODUCAO = 'S'
    """
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, qtd=qtd_descarte, nunota=nunota_origem, lote=codagregacao)
        conn.commit()
        return cur.rowcount > 0

def excluir_item_classificacao_com_cascata(nunota_26: int, sequencia: int):
    """
    Regra 4: Exclui o item da TOP 26. Se for o último, deleta o cabeçalho automaticamente.
    """
    if not verificar_permissao_escrita():
        return {"ok": False, "error": "Escrita desabilitada"}

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        try:
            # 1. Deleta o item
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s", n=nunota_26, s=sequencia)
            
            # 2. Verifica se ainda existem itens para este cabeçalho
            cur.execute("SELECT COUNT(*) FROM TGFITE WHERE NUNOTA = :n", n=nunota_26)
            restantes = cur.fetchone()[0]
            
            cabecalho_excluido = False
            if restantes == 0:
                cur.execute("DELETE FROM TGFCAB WHERE NUNOTA = :n", n=nunota_26)
                cabecalho_excluido = True
            
            conn.commit()
            return {"ok": True, "cabecalho_excluido": cabecalho_excluido}
        except Exception as e:
            conn.rollback()
            return {"ok": False, "error": str(e)}
        
def obter_detalhes_lote_completo(nunota_origem: int, lote: str):
    resultado = {
        "resumo": {"in_natura": 0, "cx_in_natura": 0, "classificado": 0, "descarte": 0, "estoque": 0, "rendimento": 0, "fabricante": ""},
        "itens": []
    }
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        # ⭐ ALTERAÇÃO: SELECT agora busca o FABRICANTE (Índice 3)
        cur.execute("""
            SELECT 
                NVL(SUM(i.QTDCONFERIDA), 0), NVL(MAX(i.PESO), 0), NVL(SUM(i.AD_QTDAVARIA), 0),
                MAX(p.FABRICANTE) AS FABRICANTE
            FROM TGFITE i
            INNER JOIN TGFPRO p ON i.CODPROD = p.CODPROD
            WHERE i.NUNOTA = :n AND i.CODAGREGACAO = :l AND i.GERAPRODUCAO = 'S'
        """, {'n': nunota_origem, 'l': lote})
        
        row_in = cur.fetchone()
        fabricante = str(row_in[3] or "").strip()
        
        if row_in:
            cx_in_natura = float(row_in[0] or 0)
            peso_unit = float(row_in[1] or 0)
            descarte = float(row_in[2] or 0)
            # Pegamos o fabricante e limpamos espaços extras
            fabricante = str(row_in[3] or "").strip()
            in_natura = cx_in_natura * peso_unit
        else:
            cx_in_natura, peso_unit, descarte, fabricante, in_natura = 0, 0, 0, "", 0

        # 2. Busca o que já foi classificado (TOP 26)
        cur.execute("""
            SELECT SUM(NVL(i.QTDNEG, 0))
            FROM TGFITE i
            JOIN TGFCAB c ON i.NUNOTA = c.NUNOTA
            WHERE i.CODAGREGACAO = :l AND c.CODTIPOPER = 26 AND c.STATUSNOTA <> 'E'
        """, {'l': lote})
        row_cl = cur.fetchone()
        classificado = float(row_cl[0] or 0)

        # 3. Cálculos de balanço de massa
        estoque = in_natura - (classificado + descarte)
        rendimento = round((classificado / in_natura * 100), 2) if in_natura > 0 else 0
        
        # ----------------------------------------------------------------------
        # ⭐ MONTAGEM DO DICIONÁRIO: Agora com a chave 'fabricante'
        # ----------------------------------------------------------------------
        resultado["resumo"] = {
            "in_natura": in_natura, 
            "cx_in_natura": cx_in_natura,
            "classificado": classificado, 
            "descarte": descarte, 
            "estoque": estoque, 
            "rendimento": rendimento,
            "fabricante": fabricante  # 👈 O dado viaja por aqui até o JS
        }

        # 4. Busca a lista de itens já classificados para a tabela inferior
        cur.execute("""
            SELECT i.CODAGREGACAO, i.SEQUENCIA, i.CODPROD, p.DESCRPROD, NVL(i.QTDNEG, 0), NVL(i.PESO, 0), p.SELECIONADO, p.CARACTERISTICAS
            FROM TGFITE i
            JOIN TGFCAB c ON i.NUNOTA = c.NUNOTA
            JOIN TGFPRO p ON i.CODPROD = p.CODPROD
            WHERE c.CODTIPOPER = 26 
              AND c.STATUSNOTA <> 'E'
              AND i.CODAGREGACAO = :lote
            ORDER BY i.SEQUENCIA
        """, {'lote': lote})
        
        for r in cur.fetchall():
            total_kg = float(r[4])
            peso_item = float(r[5])
            resultado["itens"].append({
                "lote": str(r[0] or ""), "seq": int(r[1] or 0), "codprod": int(r[2] or 0),
                "produto": str(r[3] or ""), "total_kg": total_kg, "peso": peso_item,
                "total_cx": (total_kg / peso_item) if peso_item > 0 else 0,
                "selecionado": int(r[6] if r[6] is not None else 0),
                "caracteristicas": str(r[7] or "").upper() # 👈 NOVO: Pegando a característica
            })
            
    return resultado


# ==============================================================================
# 💰 4. MÓDULO EXCLUSIVO: COMERCIAL (VENDAS E FATURAMENTO)
# ==============================================================================

def consultar_vales_comercial(filtros: dict):
    """Busca os vales (Entradas TOP 11) com seus itens filtrados para a tela Comercial."""
    binds = {'top': obter_parametros_globais()['TOP_ENTRADA']}
    
    # 1. Filtros de CABEÇALHO (Para achar a Nota)
    where_cab = ["c.CODTIPOPER = :top", "c.STATUSNOTA <> 'E'"]
    
    if filtros.get('start') and filtros.get('end'):
        where_cab.append("TRUNC(c.DTNEG) BETWEEN TO_DATE(:ds, 'YYYY-MM-DD') AND TO_DATE(:de, 'YYYY-MM-DD')")
        binds['ds'] = filtros['start']
        binds['de'] = filtros['end']
    elif filtros.get('days') is not None:
        where_cab.append("c.DTNEG >= SYSDATE - :days")
        binds['days'] = int(filtros['days'])
        
    if filtros.get('codparc'):
        where_cab.append("c.CODPARC = :codparc")
        binds['codparc'] = int(filtros['codparc'])
        
    if filtros.get('nunota'):
        # 🚀 BUSCA UNIVERSAL: Pesquisa pelo número do Pedido (TOP 11) OU pelo Vale (TOP 13)
        where_cab.append("(c.NUNOTA = :nunota OR v13.NUNOTA_13 = :nunota)")
        binds['nunota'] = int(filtros['nunota'])
        
    faturado = filtros.get('faturado')
    if faturado == 'S':
        where_cab.append("v13.NUFIN IS NOT NULL")
    elif faturado == 'N':
        where_cab.append("v13.NUFIN IS NULL")
        
    # 2. Filtros de ITEM (Define o que realmente atende à busca da tela)
    where_item = []
    
    if filtros.get('fabricante'):
        where_item.append("UPPER(pr.FABRICANTE) LIKE :fab")
        binds['fab'] = f"%{str(filtros['fabricante']).upper()}%"
        
    sem_preco = filtros.get('sem_preco')
    if sem_preco == '1':
        where_item.append("NVL(i.PRECOBASE, 0) <= 0")
    elif sem_preco == '0':
        where_item.append("NVL(i.PRECOBASE, 0) > 0")
        
    classif = filtros.get('classificacao')
    if classif == 'S':
        where_item.append("NVL(i.GERAPRODUCAO, 'S') = 'S'")
    elif classif == 'N':
        where_item.append("NVL(i.GERAPRODUCAO, 'S') = 'N'")

    limit = int(filtros.get('limit', 150))
    offset = int(filtros.get('offset', 0))

    if filtros.get('faturado') in ('S', 'T'):
        ordem_sql = "DTNEG DESC, NUNOTA DESC, SEQUENCIA ASC"
    else:
        ordem_sql = "DTNEG ASC, NUNOTA ASC, SEQUENCIA ASC"

    # Junta as regras
    where_total = where_cab + where_item
    where_sql = " AND ".join(where_total) if where_total else "1=1"
    flag_sql = " AND ".join(where_item) if where_item else "1=1"

    # 🚀 OTIMIZAÇÃO + FLAG: Traz a nota completa, mas marca quem passou no filtro!
    sql_base = f"""
        WITH Vales13 AS (
            SELECT c13.NUMNOTA, 
                   MAX(c13.NUNOTA) AS NUNOTA_13, 
                   MAX(c13.VLRNOTA) AS VLRTOT_VALE, 
                   MAX(f.NUFIN) AS NUFIN,
                   SUM(CASE WHEN f.DHBAIXA IS NOT NULL THEN 1 ELSE 0 END) AS QTD_BAIXADOS
            FROM TGFCAB c13
            LEFT JOIN TGFFIN f ON f.NUNOTA = c13.NUNOTA
            WHERE c13.CODTIPOPER = 13
            GROUP BY c13.NUMNOTA
        ),
        Classificacoes26 AS (
            SELECT i26.CODAGREGACAO, MIN(c26.PENDENTE) AS PENDENTE
            FROM TGFCAB c26
            JOIN TGFITE i26 ON c26.NUNOTA = i26.NUNOTA
            WHERE c26.CODTIPOPER = 26 AND c26.STATUSNOTA <> 'E'
            GROUP BY i26.CODAGREGACAO
        ),
        NotasFiltradas AS (
            SELECT DISTINCT c.NUNOTA
            FROM TGFCAB c
            INNER JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
            LEFT JOIN TGFPRO pr ON i.CODPROD = pr.CODPROD
            LEFT JOIN Vales13 v13 ON v13.NUMNOTA = c.NUNOTA
            LEFT JOIN Classificacoes26 c26 ON c26.CODAGREGACAO = i.CODAGREGACAO
            WHERE {where_sql}
        )
        SELECT 
            c.NUNOTA, p.NOMEPARC AS PARCEIRO, c.DTNEG,
            i.SEQUENCIA, i.CODPROD, pr.DESCRPROD AS PRODUTO, pr.FABRICANTE,
            i.QTDNEG, i.QTDCONFERIDA, 
            NVL(i.CODVOLPARC, i.CODVOL) AS CODVOL, 
            i.PESO, i.VLRUNIT, i.VLRTOT,
            i.QTDFIXADA, i.PRECOBASE,
            v13.NUNOTA_13,
            v13.VLRTOT_VALE,
            v13.NUFIN,
            NVL(v13.QTD_BAIXADOS, 0) AS QTD_BAIXADOS,
            i.CODAGREGACAO,
            c26.PENDENTE,
            NVL(i.GERAPRODUCAO, 'S') AS GERAPRODUCAO,
            
            i.AD_SIMQTD1, 
            i.AD_SIMVLR1, 
            i.AD_SIMQTD2, 
            i.AD_SIMVLR2, 
            i.AD_SIMQTDDESC,
            NVL(i.AD_SIMAUTO, 'S') AS AD_SIMAUTO,
            
            CASE WHEN {flag_sql} THEN 1 ELSE 0 END AS ATENDE_FILTRO

        FROM TGFCAB c
        INNER JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPAR p ON c.CODPARC = p.CODPARC
        LEFT JOIN TGFPRO pr ON i.CODPROD = pr.CODPROD
        LEFT JOIN Vales13 v13 ON v13.NUMNOTA = c.NUNOTA
        LEFT JOIN Classificacoes26 c26 ON c26.CODAGREGACAO = i.CODAGREGACAO
        WHERE c.NUNOTA IN (SELECT NUNOTA FROM NotasFiltradas)
    """

    sql_paginado = f"""
        SELECT * FROM (
            SELECT a.*, ROW_NUMBER() OVER (ORDER BY {ordem_sql}) rn
            FROM ({sql_base}) a
        ) WHERE rn BETWEEN :offset_start AND :offset_end
    """
    
    binds['offset_start'] = offset + 1
    binds['offset_end'] = offset + limit

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(sql_paginado, binds)
            
            cols = [col[0].lower() for col in cur.description]
            resultados = []
            
            for row in cur.fetchall():
                row_dict = dict(zip(cols, row))
                if row_dict.get('dtneg'):
                    row_dict['dtneg'] = row_dict['dtneg'].strftime('%Y-%m-%d')
                resultados.append(row_dict)
                
            return resultados
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro buscar vales comercial: {e}")
        return []

def atualizar_preco_inicial_entrada(nunota: int, sequencia: int, preco_inicial: float, qtd_conferida: float, geraproducao: str = 'S', peso_in_natura: float = 0) -> dict:
    """
    Atualiza a TOP 11. Se o produto NÃO for classificável (In Natura), 
    copia o peso classificado e faz um Upsert automático na TOP 13.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    vlrtot = round(preco_inicial * qtd_conferida, 2)
    geraproducao = str(geraproducao).strip().upper()

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Update Padrão da TOP 11
            sql_top11 = """
                UPDATE TGFITE 
                SET PRECOBASE = :preco,
                    VLRUNIT = :preco,
                    QTDNEG = :qtd,
                    VLRTOT = :tot
            """
            binds_top11 = {
                'preco': float(preco_inicial),
                'qtd': float(qtd_conferida),
                'tot': float(vlrtot),
                'nunota': int(nunota),
                'seq': int(sequencia)
            }

            # 🚀 Se for In Natura (Fast-Track), espelha o peso classificado
            if geraproducao != 'S' and peso_in_natura > 0:
                sql_top11 += ", QTDFIXADA = :peso "
                binds_top11['peso'] = float(peso_in_natura)

            sql_top11 += " WHERE NUNOTA = :nunota AND SEQUENCIA = :seq"
            cur.execute(sql_top11, binds_top11)

            # 2. Lógica do Fast-Track (Auto-Faturamento na TOP 13)
            nunota_13 = None
            peso_copiado = None
            
            if geraproducao != 'S' and peso_in_natura > 0:
                peso_copiado = peso_in_natura
                
                # Busca os dados do item da TOP 11
                cur.execute("SELECT CODPROD, CODAGREGACAO, CODEMP FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA = :s", n=nunota, s=sequencia)
                row_ite = cur.fetchone()
                
                if row_ite:
                    codprod, codagregacao, codemp_ite = row_ite

                    # Procura se o Vale TOP 13 já existe
                    cur.execute("SELECT MAX(NUNOTA) FROM TGFCAB WHERE CODTIPOPER = 13 AND NUMNOTA = :n", n=nunota)
                    res_13 = cur.fetchone()
                    nunota_13 = int(res_13[0]) if res_13 and res_13[0] else None

                    if not nunota_13:
                        # Cria o Cabeçalho TOP 13
                        cur.execute("SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
                        cab_origem = cur.fetchone()
                        if cab_origem:
                            dados_novo_cab = {
                                #'CODEMP': cab_origem[0], # seleciona a empresa do pedido de compra
                                'CODEMP': 10,
                                'CODPARC': cab_origem[1],
                                'CODNAT': cab_origem[2] or 20010100, 'CODCENCUS': cab_origem[3] or 10100,
                                'DTNEG': cab_origem[4].strftime('%d/%m/%Y') if cab_origem[4] else _date.today().strftime('%d/%m/%Y'),
                                'CODTIPOPER': 13, 'NUMNOTA': nunota,
                                'OBSERVACAO': 'Faturamento automático via SIG (Sistema Integrado de Gestão)',
                                'AD_NUMPEDIDOORIG': cab_origem[5] or nunota
                            }
                            res_cab = inserir_cabecalho_nota_banco(dados_novo_cab, simulacao=False, conexao_existente=conn)
                            if res_cab.get('ok'): nunota_13 = res_cab['nunota']

                    if nunota_13:
                        # Regra: TOP 13 salva em KG e Rateia o Valor
                        kg_total = qtd_conferida * peso_in_natura
                        vlr_kg = vlrtot / kg_total if kg_total > 0 else 0

                        # Verifica se o item já existe na TOP 13
                        cur.execute("SELECT SEQUENCIA FROM TGFITE WHERE NUNOTA = :n AND CODPROD = :p AND CODAGREGACAO = :l", 
                                    n=nunota_13, p=codprod, l=codagregacao)
                        ite_13 = cur.fetchone()

                        if ite_13:
                            # UPDATE (Ajuste de Custo/Quantidade)
                            cur.execute("""
                                UPDATE TGFITE 
                                SET QTDNEG = :q, VLRUNIT = :v, VLRTOT = :t
                                WHERE NUNOTA = :n AND SEQUENCIA = :s
                            """, q=kg_total, v=vlr_kg, t=vlrtot, n=nunota_13, s=ite_13[0])
                        else:
                            # INSERT (Novo Produto no Vale)
                            cur.execute("SELECT NVL(MAX(SEQUENCIA), 0) + 1 FROM TGFITE WHERE NUNOTA = :n", n=nunota_13)
                            prox_seq = int(cur.fetchone()[0])
                            cur.execute("""
                                INSERT INTO TGFITE (NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG, VLRUNIT, VLRTOT, CODAGREGACAO, CODVOL, CODLOCALORIG, AD_NUMPEDIDOORIG)
                                VALUES (:n, :s, :e, :p, :q, :v, :t, :l, 'KG', 101, :origem)
                            """, n=nunota_13, s=prox_seq, e=codemp_ite, p=codprod, q=kg_total, v=vlr_kg, t=vlrtot, l=codagregacao, origem=cab_origem[5] or nunota)
                        
                        # Recalcula a TOP 13 logo após inserir/atualizar
                        recalcular_totais_nota_banco(nunota_13, conexao_existente=conn)

            conn.commit()
            return {
                'ok': True, 'executed': True, 'vlrtot': vlrtot, 
                'nunota_13': nunota_13, 'peso_copiado': peso_copiado
            }
            
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    
def atualizar_peso_comercial_entrada(nunota: int, sequencia: int, peso_classificado: float) -> dict:
    """Atualiza o Peso Classificado (QTDFIXADA) do item na TOP 11."""
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    sql = """
        UPDATE TGFITE 
        SET QTDFIXADA = :peso
        WHERE NUNOTA = :nunota AND SEQUENCIA = :seq
    """
    binds = {
        'peso': float(peso_classificado),
        'nunota': int(nunota),
        'seq': int(sequencia)
    }
    
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(sql, binds)
            conn.commit()
            return {'ok': True, 'executed': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def consultar_lista_ultimas_vendas(lote: str):
    """Retorna a lista de vendas definindo a etiqueta pela regra do SELECIONADO."""
    res_final = {"ultimasVendas": []}
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT DISTINCT CODPROD FROM TGFITE WHERE CODAGREGACAO = :lote", lote=lote)
            produtos_lote = [str(r[0]) for r in cur.fetchall()]
            if not produtos_lote: return res_final
            codprods_in = ','.join(produtos_lote)

            sql_ultimas = f"""
                SELECT * FROM (
                    SELECT 
                        v.DTNEG, 
                        NVL(TO_CHAR(matriz.OBSERVACOES), matriz.NOMEPARC) AS NOME_EXIBICAO, 
                        p.SELECIONADO, 
                        v.VLR_KG_BANCO,
                        NVL(p.PESOBRUTO, 22) AS PESO_CX
                    FROM (
                        SELECT DTNEG, CODPARCMATRIZ, CODPROD, VLR_KG_BANCO
                        FROM (
                            SELECT 
                                c.DTNEG, parc.CODPARCMATRIZ, i.CODPROD, 
                                (i.VLRTOT / NULLIF(i.QTDNEG, 0)) AS VLR_KG_BANCO,
                                ROW_NUMBER() OVER (PARTITION BY parc.CODPARCMATRIZ ORDER BY c.DTNEG DESC, c.NUNOTA DESC) as rn
                            FROM TGFCAB c
                            JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                            JOIN TGFPAR parc ON c.CODPARC = parc.CODPARC
                            WHERE c.DTNEG >= SYSDATE - 15
                              AND c.CODTIPOPER IN (35, 37) AND c.STATUSNOTA = 'L'
                              AND i.CODPROD IN ({codprods_in})
                        ) WHERE rn = 1 ORDER BY DTNEG DESC
                    ) v
                    JOIN TGFPRO p ON v.CODPROD = p.CODPROD
                    JOIN TGFPAR matriz ON v.CODPARCMATRIZ = matriz.CODPARC
                ) WHERE ROWNUM <= 15
            """
            cur.execute(sql_ultimas)
            for row in cur.fetchall():
                dtneg, nome_exibicao, selecionado, vlr_kg_banco, peso_cx = row
                
                # 🚀 REGRA DO SELECIONADO PARA A ETIQUETA DA LISTA
                sel = str(selecionado).strip()
                if sel == '1': tipo = "EXTRA"
                elif sel == '2': tipo = "MÉDIO"
                elif sel == '0': tipo = "IN NATURA"
                else: tipo = "OUTROS"
                
                v_kg = float(vlr_kg_banco or 0)
                p_cx = float(peso_cx or 22)
                v_cx = v_kg * p_cx 
                
                res_final["ultimasVendas"].append({
                    "data": dtneg.strftime('%d/%m') if dtneg else "",
                    "cliente": str(nome_exibicao)[:18].strip(),
                    "tipo": tipo,
                    "preco_cx": v_cx,
                    "preco_kg": v_kg
                })
    except Exception as e:
        logger.error("Erro SQL Vendas: %s", e)
    return res_final

def consultar_calculo_ticket_medio(lote: str):
    """Calcula o Ticket Médio e envia a 'Bandeira' de tipo de fluxo."""
    # 🚀 ADICIONAMOS A BANDEIRA 'tipo_fluxo' AQUI
    res_final = {"tipo_fluxo": "CLASSIFICADO", "ticketGeral": 0, "ticketExtra": 0, "ticketMedio": 0}
    
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT DISTINCT CODPROD FROM TGFITE WHERE CODAGREGACAO = :lote", lote=lote)
            produtos_lote = [str(r[0]) for r in cur.fetchall()]
            if not produtos_lote: return res_final
            codprods_in = ','.join(produtos_lote)

            cur.execute("""
                SELECT TRUNC(DTNEG) FROM TGFCAB
                WHERE NUNOTA = (SELECT MAX(NUNOTA) FROM TGFITE WHERE CODAGREGACAO = :lote)
            """, lote=lote)
            row_dt = cur.fetchone()
            dt_compra = row_dt[0] if row_dt and row_dt[0] else None
            
            if dt_compra:
                dt_str = dt_compra.strftime('%Y-%m-%d')
                sql_media = f"""
                    SELECT p.SELECIONADO, v.MEDIA
                    FROM (
                        SELECT /*+ LEADING(c) USE_NL(i) */
                               i.CODPROD, NVL(SUM(i.VLRTOT) / NULLIF(SUM(i.QTDNEG), 0), 0) AS MEDIA
                        FROM TGFCAB c
                        JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
                        WHERE c.DTNEG >= TO_DATE('{dt_str}', 'YYYY-MM-DD')
                          AND c.DTNEG < TO_DATE('{dt_str}', 'YYYY-MM-DD') + 6
                          AND c.CODTIPOPER IN (35, 37) AND c.STATUSNOTA = 'L'
                          AND i.CODPROD IN ({codprods_in})
                        GROUP BY i.CODPROD
                    ) v
                    JOIN TGFPRO p ON v.CODPROD = p.CODPROD
                """
                cur.execute(sql_media)
                for selecionado, media in cur.fetchall():
                    sel = str(selecionado).strip()
                    if sel == '1': 
                        res_final["ticketExtra"] = float(media)
                    elif sel == '2': 
                        res_final["ticketMedio"] = float(media)
                    elif sel == '0': 
                        # 🚀 SE ENCONTROU PRODUTO 0, MARCA A BANDEIRA COMO IN NATURA
                        res_final["ticketGeral"] = float(media)
                        res_final["tipo_fluxo"] = "IN_NATURA"
                        
    except Exception as e:
        logger.error("Erro Ticket Background: %s", e)
    return res_final

def salvar_vale_compra_banco(payload: dict) -> dict:
    """
    Cria ou atualiza uma TOP 13 vinculada a uma TOP 11.
    Aplica substituição destrutiva apenas nos itens do Lote (CODAGREGACAO) especificado.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada no sistema'}

    nunota_origem = payload.get('nunota_origem')
    lote = payload.get('lote')
    itens = payload.get('itens_faturar', [])

    if not nunota_origem or not lote or not itens:
        return {'ok': False, 'error': 'Dados incompletos: NUNOTA, Lote e Itens são obrigatórios.'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Verifica se já existe a TOP 13 (Amarrada pelo NUMNOTA)
            cur.execute("SELECT MAX(NUNOTA) FROM TGFCAB WHERE CODTIPOPER = 13 AND NUMNOTA = :n", n=nunota_origem)
            res_13 = cur.fetchone()
            nunota_13 = int(res_13[0]) if res_13 and res_13[0] else None

            # 2. Se não existe, cria o Cabeçalho (Herdando dados da TOP 11)
            if not nunota_13:
                cur.execute("SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA = :n", n=nunota_origem)
                cab_origem = cur.fetchone()
                if not cab_origem:
                    return {'ok': False, 'error': 'Cabeçalho da nota de origem não encontrado.'}
                
                dados_novo_cab = {
                    'CODEMP': cab_origem[0],
                    'CODPARC': cab_origem[1],
                    'CODNAT': cab_origem[2] or 20010100, # Fallback de segurança
                    'CODCENCUS': cab_origem[3] or 10100,
                    'DTNEG': cab_origem[4].strftime('%d/%m/%Y') if cab_origem[4] else _date.today().strftime('%d/%m/%Y'),
                    'CODTIPOPER': 13,
                    'NUMNOTA': nunota_origem,
                    'OBSERVACAO': f'Faturamento gerado via Painel SIG(Sistema Integrado de Gestão)',
                    'AD_NUMPEDIDOORIG': cab_origem[5] or nunota_origem
                }
                res_cab = inserir_cabecalho_nota_banco(dados_novo_cab, simulacao=False, conexao_existente=conn)
                if not res_cab.get('ok'):
                    raise Exception(f"Erro ao criar Vale 13: {res_cab.get('error')}")
                nunota_13 = res_cab['nunota']

            # 3. EXCLUSÃO CIRÚRGICA: Limpa apenas os itens deste Lote na TOP 13
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n AND CODAGREGACAO = :l", n=nunota_13, l=lote)

            # 4. INSERÇÃO DOS NOVOS ITENS (Extra / Médio)
            cur.execute("SELECT CODEMP FROM TGFCAB WHERE NUNOTA = :n", n=nunota_13)
            codemp_13 = cur.fetchone()[0]
            
            # Pega a origem para herdar nos itens
            cur.execute("SELECT AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA = :n", n=nunota_13)
            res_origem = cur.fetchone()
            ad_numpedidoorig = res_origem[0] if res_origem else nunota_origem

            for item in itens:
                codprod = item.get('codprod')
                qtdneg = float(item.get('qtdneg', 0))
                vlrunit = float(item.get('vlrunit', 0))
                vlrtot = float(item.get('vlrtot', 0))

                if not codprod or qtdneg <= 0:
                    continue # Ignora cestas vazias

                # Pega a próxima sequência livre na unha para evitar bloqueios de transação
                cur.execute("SELECT NVL(MAX(SEQUENCIA), 0) + 1 FROM TGFITE WHERE NUNOTA = :n", n=nunota_13)
                prox_seq = int(cur.fetchone()[0])

                cur.execute("""
                    INSERT INTO TGFITE (
                        NUNOTA, SEQUENCIA, CODEMP, CODPROD, 
                        QTDNEG, VLRUNIT, VLRTOT, CODAGREGACAO, 
                        CODVOL, CODLOCALORIG, AD_NUMPEDIDOORIG
                    )
                    VALUES (
                        :nunota, :seq, :emp, :prod, 
                        :qtd, :vlr, :tot, :lote, 
                        'KG', 101, :origem
                    )
                """, {
                    'nunota': nunota_13, 'seq': prox_seq, 'emp': codemp_13, 
                    'prod': codprod, 'qtd': qtdneg, 'vlr': vlrunit, 'tot': vlrtot, 
                    'lote': lote, 'origem': ad_numpedidoorig
                })

            # Comita os itens para que a função de recálculo consiga enxergá-los
            conn.commit()

            # 5. Fechamento: Roda a procedure do banco para fechar o valor do cabeçalho
            res_recalc = recalcular_totais_nota_banco(nunota_13)
            if not res_recalc.get('ok'):
                raise Exception(f"Erro ao fechar o valor da nota: {res_recalc.get('error')}")

            return {'ok': True, 'nunota_13': nunota_13}

    except Exception as e:
        return {'ok': False, 'error': str(e)}

def zerar_negociacao_banco(nunota_origem: int, lote: str) -> dict:
    """
    Remove os itens de um lote específico do Vale de Compra (TOP 13).
    Se o Vale ficar sem nenhum item, exclui o cabeçalho e financeiro.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada no sistema'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Encontra o NUNOTA da TOP 13
            cur.execute("SELECT MAX(NUNOTA) FROM TGFCAB WHERE CODTIPOPER = 13 AND NUMNOTA = :n", n=nunota_origem)
            res = cur.fetchone()
            if not res or not res[0]:
                return {'ok': True, 'acao': 'nada_a_fazer', 'msg': 'Não há Vale gerado para zerar.'}
            
            nunota_13 = int(res[0])

            # 2. Exclusão Cirúrgica: Deleta apenas os itens deste Lote
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n AND CODAGREGACAO = :l", n=nunota_13, l=lote)
            conn.commit()

            # 3. Checagem de Segurança: Sobrou algum item de outro produtor/lote nesta nota?
            cur.execute("SELECT COUNT(*) FROM TGFITE WHERE NUNOTA = :n", n=nunota_13)
            qtd_restante = int(cur.fetchone()[0])

            if qtd_restante > 0:
                # Cenário A: Sobrou coisa na nota. Apenas recalcula o Valor Total do Cabeçalho.
                recalcular_totais_nota_banco(nunota_13)
                return {'ok': True, 'acao': 'itens_deletados'}
            else:
                # Cenário B: A nota ficou vazia. Exclui ela inteira (TGFCAB, TGFFIN) usando a função que você já tem.
                res_exclusao = excluir_nota_completa_banco(nunota_13)
                if not res_exclusao.get('ok'):
                    raise Exception(res_exclusao.get('error'))
                return {'ok': True, 'acao': 'nota_excluida'}

    except Exception as e:
        return {'ok': False, 'error': str(e)}

def desmembrar_pedido_classificacao(nunota_origem: int, lote_desmembrar: str) -> dict:
    """
    Clona o Pedido de Compra (TOP 11) original e transfere o lote selecionado para ele.
    Transfere também TODO o histórico de classificação (TOP 26) amarrado a este lote, 
    sejam classificações pendentes ou já finalizadas, garantindo a integridade do Balanço de Massa.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada no sistema'}

    try:
        from datetime import date as _date
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Verifica se o pedido de origem tem mais de 1 lote. Se tiver só 1, não há o que desmembrar.
            cur.execute("SELECT COUNT(DISTINCT CODAGREGACAO) FROM TGFITE WHERE NUNOTA = :n", n=nunota_origem)
            qtd_lotes = int(cur.fetchone()[0] or 0)
            if qtd_lotes <= 1:
                return {'ok': False, 'error': 'O pedido possui apenas este lote. Não é possível desmembrar.'}

            # 2. Busca os dados do cabeçalho original (TOP 11) para clonar
            cur.execute("""
                SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, CODTIPOPER, OBSERVACAO 
                FROM TGFCAB WHERE NUNOTA = :n
            """, n=nunota_origem)
            cab_origem = cur.fetchone()
            
            if not cab_origem:
                return {'ok': False, 'error': 'Cabeçalho original não encontrado.'}

            obs_antiga = str(cab_origem[6] or '')
            nova_obs = f"{obs_antiga} | Desmembrado do Pedido {nunota_origem}".strip()
            
            # Prepara os dados do novo pedido clonado
            dados_novo_cab = {
                'CODEMP': cab_origem[0],
                'CODPARC': cab_origem[1],
                'CODNAT': cab_origem[2], 
                'CODCENCUS': cab_origem[3],
                'DTNEG': cab_origem[4].strftime('%d/%m/%Y') if cab_origem[4] else _date.today().strftime('%d/%m/%Y'),
                'CODTIPOPER': cab_origem[5], # TOP 11
                'OBSERVACAO': nova_obs[:60]
            }
            
            # Insere o novo cabeçalho usando a função existente
            res_novo_cab = inserir_cabecalho_nota_banco(dados_novo_cab, simulacao=False, conexao_existente=conn)
            if not res_novo_cab.get('ok'):
                raise Exception(f"Erro ao criar novo Pedido: {res_novo_cab.get('error')}")
                
            nunota_novo = res_novo_cab['nunota']

            # Corta o cordão umbilical: O novo pedido é a origem dele mesmo
            cur.execute("UPDATE TGFCAB SET AD_NUMPEDIDOORIG = :n WHERE NUNOTA = :n", n=nunota_novo)

            # 3. TRANSFERÊNCIA FÍSICA (In Natura): CLONAR E APAGAR
            # Lê as colunas dinamicamente para fazer uma cópia idêntica (Bypass na Trigger do Sankhya)
            colunas_ite = list(_obter_colunas_da_tabela(conn, 'TGFITE'))
            if not colunas_ite:
                raise Exception("Não foi possível ler a estrutura da tabela de itens.")
                
            colunas_str = ", ".join(colunas_ite)
            select_cols = []
            
            # Substitui apenas o dono da nota, o resto copia igual
            for c in colunas_ite:
                if c == 'NUNOTA': select_cols.append(':novo_n')
                elif c == 'AD_NUMPEDIDOORIG': select_cols.append(':novo_n')
                else: select_cols.append(c)
                
            select_str = ", ".join(select_cols)
            
            # 3.1 Insere a cópia exata no pedido novo
            sql_clone = f"INSERT INTO TGFITE ({colunas_str}) SELECT {select_str} FROM TGFITE WHERE NUNOTA = :velho_n AND CODAGREGACAO = :lote"
            cur.execute(sql_clone, novo_n=nunota_novo, velho_n=nunota_origem, lote=lote_desmembrar)
            
            linhas_movidas = cur.rowcount
            if linhas_movidas == 0:
                raise Exception("Nenhum item físico (In Natura) encontrado para mover.")
                
            # 3.2 Apaga os itens do pedido velho
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :velho_n AND CODAGREGACAO = :lote", velho_n=nunota_origem, lote=lote_desmembrar)

            # 4. TRANSFERÊNCIA DE CLASSIFICAÇÃO (TOP 26): Atualiza a origem de TODAS as TOP 26 deste lote
            # Atualiza os ITENS classificados para apontarem para o novo pedido
            cur.execute("""
                UPDATE TGFITE 
                SET AD_NUMPEDIDOORIG = :novo_n 
                WHERE CODAGREGACAO = :lote 
                  AND NUNOTA IN (SELECT NUNOTA FROM TGFCAB WHERE CODTIPOPER = 26)
            """, novo_n=nunota_novo, lote=lote_desmembrar)
            
            # Atualiza os CABEÇALHOS das classificações para apontarem para o novo pedido
            cur.execute("""
                UPDATE TGFCAB 
                SET AD_NUMPEDIDOORIG = :novo_n 
                WHERE NUNOTA IN (
                    SELECT NUNOTA FROM TGFITE WHERE CODAGREGACAO = :lote
                ) AND CODTIPOPER = 26
            """, novo_n=nunota_novo, lote=lote_desmembrar)

            # 5. LIMPEZA DE VALE: Se esse lote já estava salvo em um Vale 13 na nota original, arranca de lá
            cur.execute("SELECT MAX(NUNOTA) FROM TGFCAB WHERE CODTIPOPER = 13 AND NUMNOTA = :n", n=nunota_origem)
            res_13 = cur.fetchone()
            if res_13 and res_13[0]:
                nunota_13_velho = int(res_13[0])
                cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n AND CODAGREGACAO = :l", n=nunota_13_velho, l=lote_desmembrar)
                recalcular_totais_nota_banco(nunota_13_velho, conexao_existente=conn)

            # 6. Atualiza os valores totais (VLRNOTA, QTDVOL) dos dois pedidos principais
            recalcular_totais_nota_banco(nunota_origem, conexao_existente=conn)
            recalcular_totais_nota_banco(nunota_novo, conexao_existente=conn)

            conn.commit()
            return {'ok': True, 'novo_pedido': nunota_novo, 'linhas_movidas': linhas_movidas}

    except Exception as e:
        return {'ok': False, 'error': str(e)}
    
def unificar_pedido_classificacao(nunota_origem: int, lote_unificar: str, nunota_destino: int) -> dict:
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada no sistema'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Verifica se o pedido de destino realmente existe
            cur.execute("SELECT NUNOTA FROM TGFCAB WHERE NUNOTA = :n AND CODTIPOPER = 11", n=nunota_destino)
            if not cur.fetchone():
                return {'ok': False, 'error': 'Pedido de destino não encontrado no banco de dados.'}

            # 2. TRANSFERÊNCIA FÍSICA (In Natura): Clonar para o destino e Apagar da Origem
            colunas_ite = list(_obter_colunas_da_tabela(conn, 'TGFITE'))
            colunas_str = ", ".join(colunas_ite)
            
            select_cols = []
            for c in colunas_ite:
                if c == 'NUNOTA' or c == 'AD_NUMPEDIDOORIG': select_cols.append(':novo_n')
                else: select_cols.append(c)
                
            select_str = ", ".join(select_cols)
            
            # Insere no destino
            sql_clone = f"INSERT INTO TGFITE ({colunas_str}) SELECT {select_str} FROM TGFITE WHERE NUNOTA = :velho_n AND CODAGREGACAO = :lote"
            cur.execute(sql_clone, novo_n=nunota_destino, velho_n=nunota_origem, lote=lote_unificar)
            linhas_movidas = cur.rowcount
            if linhas_movidas == 0:
                raise Exception("Item físico não encontrado na nota de origem.")
                
            # Apaga da origem
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :velho_n AND CODAGREGACAO = :lote", velho_n=nunota_origem, lote=lote_unificar)

            # 3. TRANSFERÊNCIA DE CLASSIFICAÇÃO (TOP 26): Atualiza a origem de TODAS as TOP 26
            cur.execute("""
                UPDATE TGFITE SET AD_NUMPEDIDOORIG = :novo_n 
                WHERE CODAGREGACAO = :lote AND NUNOTA IN (SELECT NUNOTA FROM TGFCAB WHERE CODTIPOPER = 26)
            """, novo_n=nunota_destino, lote=lote_unificar)
            
            cur.execute("""
                UPDATE TGFCAB SET AD_NUMPEDIDOORIG = :novo_n 
                WHERE NUNOTA IN (SELECT NUNOTA FROM TGFITE WHERE CODAGREGACAO = :lote) AND CODTIPOPER = 26
            """, novo_n=nunota_destino, lote=lote_unificar)

            # 4. LIMPEZA DE VALE ORIGEM (Segurança extra)
            cur.execute("SELECT MAX(NUNOTA) FROM TGFCAB WHERE CODTIPOPER = 13 AND NUMNOTA = :n", n=nunota_origem)
            res_13 = cur.fetchone()
            if res_13 and res_13[0]:
                cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n AND CODAGREGACAO = :l", n=int(res_13[0]), l=lote_unificar)
                recalcular_totais_nota_banco(int(res_13[0]), conexao_existente=conn)

            # 5. Atualiza totais dos dois pedidos
            recalcular_totais_nota_banco(nunota_origem, conexao_existente=conn)
            recalcular_totais_nota_banco(nunota_destino, conexao_existente=conn)

            conn.commit()
            return {'ok': True, 'linhas_movidas': linhas_movidas}

    except Exception as e:
        return {'ok': False, 'error': str(e)}

def consultar_detalhes_vale_banco(nunota_13: int, lote: str) -> dict:
    """Busca os itens reais faturados na TOP 13 para espelhar no painel."""
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT i.CODPROD, NVL(i.QTDNEG,0), NVL(i.VLRUNIT,0), NVL(i.VLRTOT,0), 
                       p.CARACTERISTICAS, p.SELECIONADO
                FROM TGFITE i
                JOIN TGFPRO p ON i.CODPROD = p.CODPROD
                WHERE i.NUNOTA = :n AND i.CODAGREGACAO = :l
            """, n=nunota_13, l=lote)
            
            itens = []
            for r in cur.fetchall():
                itens.append({
                    "codprod": int(r[0]),
                    "qtdneg": float(r[1]),
                    "vlrunit": float(r[2]),
                    "vlrtot": float(r[3]),
                    "caracteristicas": str(r[4] or "").upper(),
                    "selecionado": int(r[5] or 0)
                })
            return {'ok': True, 'itens': itens}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def atualizar_simulacao_item_banco(nunota: int, lote: str, sim_data: dict) -> dict:
    """Atualiza os campos de simulação de negócio na TGFITE da TOP 11."""
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 🚀 FIX: SQL totalmente limpo! Sem emojis ou comentários internos para não bugar o parser do Oracle.
            cur.execute("""
                UPDATE TGFITE 
                SET AD_SIMQTD1 = :q1, 
                    AD_SIMVLR1 = :v1, 
                    AD_SIMQTD2 = :q2, 
                    AD_SIMVLR2 = :v2, 
                    AD_SIMQTDDESC = :v_desc,
                    AD_SIMAUTO = :auto
                WHERE NUNOTA = :nunota AND CODAGREGACAO = :lote
            """, 
            q1=sim_data.get('q1'), 
            v1=sim_data.get('v1'),
            q2=sim_data.get('q2'), 
            v2=sim_data.get('v2'),
            v_desc=sim_data.get('desc'),
            auto=sim_data.get('auto', 'S'),
            nunota=nunota, 
            lote=lote)
            
            conn.commit()
            return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def gerar_financeiro_banco(nunota_13: int, descontar_inss: bool = False, historico: str = '', vlrinss: float = 0, vlr_forcar_liquido: float = None, vlr_forcar_bruto: float = None) -> dict:
    """Gera o financeiro (TGFFIN) e marca a nota como confirmada usando os valores exatos da interface."""
    if not verificar_permissao_escrita(): return {'ok': False, 'error': 'Escrita desabilitada'}

    from decimal import Decimal, ROUND_HALF_UP

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Trava de segurança
            cur.execute("SELECT MAX(NUFIN) FROM TGFFIN WHERE NUNOTA = :n", n=nunota_13)
            if cur.fetchone()[0]:
                return {'ok': False, 'error': 'Esta nota já possui um título financeiro gerado.'}

            # 2. Busca dados do Cabeçalho
            cur.execute("""
                SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, VLRNOTA, NUMNOTA, DHTIPOPER
                FROM TGFCAB WHERE NUNOTA = :n
            """, n=nunota_13)
            cab = cur.fetchone()
            if not cab: return {'ok': False, 'error': 'Nota não encontrada no banco de dados.'}
            
            codemp, codparc, codnat, codcencus, dtneg, vlrnota, numnota, dhtipoper = cab
            dt_venc = calcular_vencimento_agromil(dtneg)

            # 3. Gera ID provisório
            cur.execute("SELECT NVL(MAX(NUFIN), 0) + 1 FROM TGFFIN")
            nufin_temp = cur.fetchone()[0]

            # 🚀 BLINDAGEM SUPREMA: Confia cegamente nos valores enviados pela tela
            vlr_bruto_final = vlr_forcar_bruto if vlr_forcar_bruto else vlrnota
            vlr_liquido_final = vlr_forcar_liquido if vlr_forcar_liquido else vlr_bruto_final
            
            vlr_bruto = float(Decimal(str(vlr_bruto_final)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            vlr_liquido = float(Decimal(str(vlr_liquido_final)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

            sql_fin = """
                INSERT INTO TGFFIN (
                    NUFIN, NUNOTA, NUMNOTA, CODEMP, CODPARC, CODNAT, CODCENCUS, 
                    ORIGEM, CODTIPOPER, DHTIPOPER, CODBCO, CODCTABCOINT, CODTIPTIT, 
                    CODMOEDA, CODPROJ, CODVEND, CODVEICULO, DTNEG, DHMOV, DTALTER, 
                    DTENTSAI, DTVENCINIC, DTVENC, DTPRAZO, VLRDESDOB, VLRBAIXA,
                    DESDOBRAMENTO, SEQUENCIA, RECDESP, PROVISAO, FINCONFIRMADO, 
                    AUTORIZADO, ISSRETIDO, IRFRETIDO, RATEADO, RECEBIDO,
                    TIPMULTA, TIPJURO, DHTIPOPERBAIXA, HISTORICO
                ) VALUES (
                    :nufin, :nunota, :numnota, :emp, :parc, :nat, :cus,
                    'E', 13, :dhtip, 336, 17, 9,
                    0, 0, 0, 0, :dtneg, SYSDATE, SYSDATE,
                    :dtneg, :dtvenc, :dtvenc, :dtvenc, :vlr_insert, 0,
                    '1', 1, -1, 'N', 'S',
                    'N', 'N', 'N', 'N', 0,
                    1, 1, TO_DATE('01/01/1998','DD/MM/YYYY'), :hist
                )
            """

            # 4. Faz a Inserção Inicial
            cur.execute(sql_fin, {
                'nufin': nufin_temp, 'nunota': nunota_13, 'numnota': numnota, 'emp': codemp,
                'parc': codparc, 'nat': codnat, 'cus': codcencus, 'dhtip': dhtipoper,
                'dtneg': dtneg, 'dtvenc': dt_venc, 
                'vlr_insert': vlr_bruto,  
                'hist': historico[:255]
            })

            # 5. Confirma a Nota (Aqui as triggers do Sankhya despertam)
            cur.execute("UPDATE TGFCAB SET STATUSNOTA='L', DTFATUR=SYSDATE WHERE NUNOTA=:n", n=nunota_13)
            
            # 🚀 6. A MARRETA DEFINITIVA NO ALVO CERTO
            # Ignoramos o NUFIN e vamos caçar o título pelo NUNOTA da nota
            cur.execute("UPDATE TGFFIN SET VLRDESDOB = :vlr_final WHERE NUNOTA = :n", vlr_final=vlr_liquido, n=nunota_13)
            cur.execute("UPDATE TGFCAB SET VLRNOTA = :vlr_cab WHERE NUNOTA = :n", vlr_cab=vlr_bruto, n=nunota_13)

            conn.commit()

            cur.execute("SELECT MAX(NUFIN) FROM TGFFIN WHERE NUNOTA = :n", n=nunota_13)
            nufin_real = cur.fetchone()[0]

            return {'ok': True, 'nufin': nufin_real}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def upsert_preco_in_natura_modalFaturamento(nunota_origem: int, nunota_13: int, codprod: int, novo_preco: float) -> dict:
    if not verificar_permissao_escrita(): return {'ok': False}
    
    try:
        from datetime import date as _date
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. 🚀 VERIFICA/CRIA O VALE (TOP 13)
            # Independentemente do que o frontend mandar, consultamos a realidade do banco
            cur.execute("SELECT MAX(NUNOTA) FROM TGFCAB WHERE CODTIPOPER = 13 AND NUMNOTA = :n", n=nunota_origem)
            res_13 = cur.fetchone()
            nunota_13_real = int(res_13[0]) if res_13 and res_13[0] else None

            if not nunota_13_real:
                # O Vale não existe. Vamos criar o Cabeçalho agora!
                cur.execute("SELECT CODEMP, CODPARC, CODNAT, CODCENCUS, DTNEG, AD_NUMPEDIDOORIG FROM TGFCAB WHERE NUNOTA = :n", n=nunota_origem)
                cab_origem = cur.fetchone()
                if not cab_origem:
                    return {'ok': False, 'error': 'Cabeçalho da nota de origem não encontrado.'}

                dados_novo_cab = {
                    #'CODEMP': cab_origem[0], # seleciona a empresa do pedido de compra
                    'CODEMP': 10, 
                    'CODPARC': cab_origem[1],
                    'CODNAT': cab_origem[2] or 20010100, 'CODCENCUS': cab_origem[3] or 10100,
                    'DTNEG': cab_origem[4].strftime('%d/%m/%Y') if cab_origem[4] else _date.today().strftime('%d/%m/%Y'),
                    'CODTIPOPER': 13, 'NUMNOTA': nunota_origem,
                    'OBSERVACAO': 'Faturamento automático via SIG (Sistema Integrado de Gestão)',
                    'AD_NUMPEDIDOORIG': cab_origem[5] or nunota_origem
                }
                res_cab = inserir_cabecalho_nota_banco(dados_novo_cab, simulacao=False, conexao_existente=conn)
                if not res_cab.get('ok'):
                    return {'ok': False, 'error': f"Erro ao criar Vale 13: {res_cab.get('error')}"}
                nunota_13_real = res_cab['nunota']

            # 2. Busca os dados físicos do item na origem (TOP 11)
            cur.execute("""
                SELECT NVL(QTDCONFERIDA, QTDNEG), CODVOL, PESO, CODAGREGACAO, GERAPRODUCAO
                FROM TGFITE 
                WHERE NUNOTA = :origem AND CODPROD = :prod AND ROWNUM = 1
            """, origem=nunota_origem, prod=codprod)
            item_origem = cur.fetchone()
            
            if not item_origem:
                return {'ok': False, 'error': 'Produto físico não encontrado na nota de origem.'}
                
            qtd_cx, vol_origem, peso_origem, lote_origem, geraprod_origem = item_origem
            if qtd_cx <= 0:
                return {'ok': False, 'error': 'A quantidade deste produto está zerada.'}
                
            # 🚀 MATEMÁTICA CIRÚRGICA PARA O SANKHYA:
            # 1. Descobre o peso total (Ex: 8 cx * 17 kg = 136 kg)
            peso_real = float(peso_origem) if float(peso_origem) > 0 else 1.0
            qtd_kg = float(qtd_cx * peso_real)
            
            # 2. Descobre o Valor Total (Ex: 8 cx * 80,00 = 640,00)
            vlr_tot = round(qtd_cx * novo_preco, 2)
            
            # 3. Calcula um Valor Unitário infinito para o Sankhya bater a conta exata!
            # Ex: 640 / 136 = 4.7058823...
            vlr_unit_kg = round(vlr_tot / qtd_kg, 7) if qtd_kg > 0 else 0

            # 3. 🚀 TENTA ATUALIZAR O ITEM (Agora mandando QTDNEG em KG e CODVOL em KG)
            cur.execute("""
                UPDATE TGFITE 
                SET QTDNEG = :qtdkg, VLRUNIT = :vlrkg, VLRTOT = :tot, CODVOL = 'KG', CODEMP = 10 
                WHERE NUNOTA = :nota13 AND CODPROD = :prod
            """, qtdkg=qtd_kg, vlrkg=vlr_unit_kg, tot=vlr_tot, nota13=nunota_13_real, prod=codprod)
            
            # 4. 🚀 SE NÃO ATUALIZOU, FAZ O INSERT MANDANDO KG
            if cur.rowcount == 0:
                dados_insercao = {
                    'NUNOTA': nunota_13_real,
                    'CODEMP': 10,

                    'CODPROD': codprod,
                    'QTDNEG': qtd_kg,
                    'VLRUNIT': vlr_unit_kg, # O seu inserir_item_nota_banco vai arredondar o total certinho!
                    'PESO': peso_origem,
                    'CODVOL': 'KG',         # Força KG na tela do Sankhya
                    'QTDCONFERIDA': qtd_cx,
                    'CODAGREGACAO': lote_origem,
                    'GERAPRODUCAO': geraprod_origem
                }
                
                resultado_insert = inserir_item_nota_banco(dados_insercao, simulacao=False, conexao_existente=conn)
                
                if not resultado_insert.get('ok'):
                    conn.rollback()
                    return {'ok': False, 'error': f"Falha ao inserir item no Sankhya: {resultado_insert.get('error')}"}

            # 5. INDISPENSÁVEL: Recalcula o cabeçalho (TGFCAB) para bater com os novos valores
            recalcular_totais_nota_banco(nunota_13_real, conexao_existente=conn)

            # Tudo deu certo! Salva as alterações no banco.
            conn.commit()

            # --- BLOCO DE INTEGRIDADE DO INSS ---
            cur.execute("SELECT NVL(VLROUTROS, 0) FROM TGFCAB WHERE NUNOTA = :n", n=nunota_13_real)
            vlr_outros_atual = cur.fetchone()[0]

            if vlr_outros_atual > 0:
                cur.execute("""
                    SELECT ROUND(SUM(NVL(VLRTOT, 0)) * 0.0163, 2) 
                    FROM TGFITE 
                    WHERE NUNOTA = :n
                """, n=nunota_13_real)
                novo_inss = cur.fetchone()[0] or 0
                
                cur.execute("UPDATE TGFCAB SET VLROUTROS = :vlr WHERE NUNOTA = :n", vlr=novo_inss, n=nunota_13_real)
                conn.commit()
                recalcular_totais_nota_banco(nunota_13_real, conexao_existente=conn)
            # --- FIM DO BLOCO ---

            return {'ok': True, 'nunota_13': nunota_13_real, 'vlrtot': vlr_tot}
            
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def atualizar_desconto_inss_vale(nunota_13: int, valor_desconto: float) -> dict:
    """
    Salva o valor do INSS no campo VLROUTROS da TGFCAB (TOP 13) 
    e recalcula os totais da nota.
    """
    if not verificar_permissao_escrita(): return {'ok': False}
    
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # 1. Atualiza o valor do desconto (INSS) no campo VLROUTROS
            cur.execute("""
                UPDATE TGFCAB 
                SET VLROUTROS = :vlr 
                WHERE NUNOTA = :nota
            """, vlr=valor_desconto, nota=nunota_13)
            
            # 2. Recalcula os totais da nota para que o VLRNOTA reflita a mudança
            # (Utilizando a função que já existe no seu oracle_conn.py)
            recalcular_totais_nota_banco(nunota_13, conexao_existente=conn)
            
            conn.commit()
            return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def buscar_vlroutros_vale(nunota_13: int) -> float:
    """Retorna o valor atual de VLROUTROS do cabeçalho da nota."""
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("SELECT NVL(VLROUTROS, 0) FROM TGFCAB WHERE NUNOTA = :n", n=nunota_13)
            row = cur.fetchone()
            return float(row[0]) if row else 0.0
    except:
        return 0.0

def calcular_vencimento_agromil(dt_neg):
    """
    Regra Agromil: Pagamento toda quinta-feira. 
    Corte na sexta: Compra até sexta vence na próxima quinta.
    Compra sábado/domingo vence na quinta da semana subsequente.
    """
    # 0=Seg, 1=Ter, 2=Qua, 3=Qui, 4=Sex, 5=Sab, 6=Dom
    dia_semana = dt_neg.weekday()
    
    if dia_semana <= 4:
        dias_ate_quinta = (3 - dia_semana) + 7
    else:
        dias_ate_quinta = (3 - dia_semana) + 14
        
    return dt_neg + timedelta(days=dias_ate_quinta)

def desfaturar_comercial_banco(nunota_13: int) -> dict:
    """Deleta o financeiro (TGFFIN) sem alterar o status da nota (TGFCAB), evitando a trigger."""
    if not verificar_permissao_escrita(): return {'ok': False}
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            
            # Verifica existência e travas do financeiro
            cur.execute("SELECT NUFIN, DHBAIXA, NURENEG FROM TGFFIN WHERE NUNOTA = :n", n=nunota_13)
            fin = cur.fetchone()
            
            if fin:
                nufin, dhbaixa, nureneg = fin
                if dhbaixa: return {'ok': False, 'error': 'Bloqueado: Este título já possui baixa/pagamento no Sankhya.'}
                if nureneg: return {'ok': False, 'error': 'Bloqueado: Este título foi renegociado no Sankhya.'}
                
                # Deleta apenas o financeiro
                cur.execute("DELETE FROM TGFFIN WHERE NUFIN = :f", f=nufin)

            # 🚀 REMOVIDO: O UPDATE da TGFCAB que tentava mudar o STATUSNOTA para 'A'
            # Como a edição de preços foi liberada e o botão lê a TGFFIN, a nota pode ficar como 'L'.
            
            conn.commit()
            return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# ==============================================================================
# 💰 4. MÓDULO EXCLUSIVO: VENDAS
# ==============================================================================

def listar_vendas_paginado(limite: int = 50, offset: int = 0, **kwargs):
    where = ["c.CODTIPOPER IN (34, 35, 37)", "c.STATUSNOTA <> 'E'"]
    binds = {}
    
    # 1. Datas
    if kwargs.get('date_start') and kwargs.get('date_end'):
        where.append("TRUNC(c.DTNEG) BETWEEN TO_DATE(:ds, 'YYYY-MM-DD') AND TO_DATE(:de, 'YYYY-MM-DD')")
        binds['ds'] = kwargs['date_start']
        binds['de'] = kwargs['date_end']

    # 2. Empresa
    if kwargs.get('codemp'):
        where.append("c.CODEMP = :codemp")
        binds['codemp'] = int(kwargs['codemp'])

    # 3. Pedido / Vale (NUNOTA)
    if kwargs.get('nunota_ini'):
        where.append("c.NUNOTA = :nunota")
        binds['nunota'] = int(kwargs['nunota_ini'])

    # 4. Nota Fiscal (NUMNOTA)
    if kwargs.get('numnota'):
        where.append("c.NUMNOTA = :numnota")
        binds['numnota'] = int(kwargs['numnota'])

    # 5. Operação (TOP)
    if kwargs.get('top') and kwargs.get('top') != 'T':
        where.append("c.CODTIPOPER = :top_v")
        binds['top_v'] = int(kwargs['top'])

    # 6. Parceiro (Cliente)
    if kwargs.get('codparc'):
        where.append("c.CODPARC = :codparc")
        binds['codparc'] = int(kwargs['codparc'])

    # 7. Produto (Busca inteligente: Se digitar número busca CODPROD, se digitar texto busca DESCRPROD)
    if kwargs.get('codprod'):
        prod_val = str(kwargs['codprod']).strip()
        if prod_val.isdigit():
            where.append("EXISTS (SELECT 1 FROM TGFITE i2 WHERE i2.NUNOTA = c.NUNOTA AND i2.CODPROD = :cp)")
            binds['cp'] = int(prod_val)
        else:
            where.append("""
                EXISTS (SELECT 1 FROM TGFITE i2 
                        JOIN TGFPRO pr ON pr.CODPROD = i2.CODPROD 
                        WHERE i2.NUNOTA = c.NUNOTA AND UPPER(pr.DESCRPROD) LIKE :dp)
            """)
            binds['dp'] = f"%{prod_val.upper()}%"

    # 8. Lote
    if kwargs.get('lote'):
        where.append("EXISTS (SELECT 1 FROM TGFITE i3 WHERE i3.NUNOTA = c.NUNOTA AND UPPER(i3.CODAGREGACAO) LIKE :lt)")
        binds['lt'] = f"%{str(kwargs['lote']).upper()}%"

    # Restante da SQL permanece o mesmo...
    sql_base = f"""
        SELECT 
            c.NUNOTA, c.CODTIPOPER, c.DTNEG, p.NOMEPARC, c.VLRNOTA,
            CASE 
                WHEN EXISTS (SELECT 1 FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA AND i.CODAGREGACAO IS NULL) 
                THEN 'PENDENTE' ELSE 'OK'
            END AS STATUS_LOTE,
            c.NUMNOTA,
            c.CODEMP
        FROM TGFCAB c
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        WHERE {' AND '.join(where)}
    """
    # ... código da paginação ...

    sql_paginado = f"""
        SELECT * FROM (
            SELECT t.*, ROW_NUMBER() OVER (ORDER BY t.DTNEG DESC, t.NUNOTA DESC) rn FROM ({sql_base}) t
        ) WHERE rn BETWEEN :start_row AND :end_row
    """
    binds['start_row'] = offset + 1
    binds['end_row'] = offset + limite

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_paginado, binds)
        return cur.fetchall()


# ==============================================================================
# 📦 RASTREABILIDADE — saldo por lote e atribuição em pedido de venda
# Lê da view SANKHYA.ANDRE_IRIS_SALDO_LOTE (TGFEST não é tocada).
# ==============================================================================

def consultar_saldo_lote_disponivel(filtros: dict | None = None,
                                    limite: int = 50, offset: int = 0) -> list[dict]:
    """Saldo por (CODEMP, CODPROD, CODAGREGACAO) lendo da ANDRE_IRIS_SALDO_LOTE.

    Retorna SOMENTE linhas vendáveis com saldo > 0
    (status CLASSIFICADO e NAO_CLASSIFICAVEL).
    Pernas não-vendáveis (AGUARDANDO_CLASSIFICACAO, AVARIA_FORNECEDOR,
    AVARIA_INTERNA) ficam ocultas — a UI só lista o que pode ser vinculado.

    Filtros opcionais:
        q             busca textual: número exato → CODPROD; texto → FABRICANTE (LIKE)
        codprod       código de produto exato
        codagregacao  lote (LIKE %valor%, case-insensitive)
        tipo          'classificavel' | 'nao_classificavel' (default: todos)

    Paginação: limite (default 50) e offset (default 0).
    """
    filtros = filtros or {}
    where = ["QTD_DISPONIVEL > 0"]
    binds: dict = {}

    if filtros.get('codprod'):
        where.append("CODPROD = :codprod")
        binds['codprod'] = int(filtros['codprod'])

    # Filtro IN — usado pelo filtro cruzado da UI quando o usuário clica no
    # header de um pedido (1..N produtos) ou no card de um lote (1 produto).
    codprods_in = filtros.get('codprods')
    if codprods_in:
        try:
            codprods_in = [int(x) for x in codprods_in if str(x).strip()]
        except (TypeError, ValueError):
            codprods_in = []
        if codprods_in:
            ks = []
            for i, cp in enumerate(codprods_in):
                k = f'cp_in_{i}'
                ks.append(':' + k)
                binds[k] = int(cp)
            where.append(f"CODPROD IN ({', '.join(ks)})")

    if filtros.get('codagregacao'):
        where.append("UPPER(CODAGREGACAO) LIKE :lote")
        binds['lote'] = f"%{str(filtros['codagregacao']).upper()}%"

    # Filtro exato de FABRICANTE — usado quando o usuário seleciona no typeahead
    if filtros.get('fabricante'):
        where.append("UPPER(FABRICANTE) = :fab_exato")
        binds['fab_exato'] = str(filtros['fabricante']).upper()

    # Cross filter: mostra apenas lotes cujo CODPROD aparece em pedidos
    # (TOP 34/35/37) de um cliente cujo nome casa com o termo digitado.
    cliente_q = str(filtros.get('cliente_q') or '').strip()
    if cliente_q:
        where.append("""
            EXISTS (
                SELECT 1
                FROM TGFITE i_cli
                JOIN TGFCAB c_cli       ON c_cli.NUNOTA = i_cli.NUNOTA
                LEFT JOIN TGFPAR p_cli  ON p_cli.CODPARC = c_cli.CODPARC
                WHERE i_cli.CODPROD       = ANDRE_IRIS_SALDO_LOTE.CODPROD
                  AND c_cli.CODTIPOPER   IN (34, 35, 37)
                  AND c_cli.STATUSNOTA  <> 'E'
                  AND UPPER(p_cli.NOMEPARC) LIKE :cliente_q
            )
        """)
        binds['cliente_q'] = f"%{cliente_q.upper()}%"

    termo = str(filtros.get('q') or '').strip()
    if termo:
        if termo.isdigit():
            where.append("CODPROD = :q_codprod")
            binds['q_codprod'] = int(termo)
        else:
            where.append("UPPER(FABRICANTE) LIKE :q_fab")
            binds['q_fab'] = f"%{termo.upper()}%"

    tipo = str(filtros.get('tipo') or '').strip().lower()
    if tipo == 'classificavel':
        where.append("STATUS_LINHA = 'CLASSIFICADO'")
    elif tipo in ('nao_classificavel', 'naoclassificavel'):
        where.append("STATUS_LINHA = 'NAO_CLASSIFICAVEL'")

    # Filtro de janela temporal: prioriza data_ini/data_fim (range explícito).
    # Fallback: desde_dias (legado, retrocompatibilidade dos testes).
    data_ini = (filtros.get('data_ini') or '').strip() or None
    data_fim = (filtros.get('data_fim') or '').strip() or None
    if data_ini or data_fim:
        if data_ini:
            where.append("DTNEG_ORIGEM >= TO_DATE(:data_ini, 'YYYY-MM-DD')")
            binds['data_ini'] = data_ini
        if data_fim:
            where.append("DTNEG_ORIGEM < TO_DATE(:data_fim, 'YYYY-MM-DD') + 1")
            binds['data_fim'] = data_fim
    else:
        desde_dias = filtros.get('desde_dias')
        try:
            desde_dias = int(desde_dias) if desde_dias not in (None, '') else 0
        except (TypeError, ValueError):
            desde_dias = 0
        if desde_dias > 0:
            where.append("DTNEG_ORIGEM >= (TRUNC(SYSDATE) - :desde_dias)")
            binds['desde_dias'] = desde_dias

    # Paginação compatível com Oracle 11g (ROW_NUMBER + BETWEEN). Mesmo padrão
    # já usado em listar_vendas_paginado.
    sql_base = f"""
        SELECT
            CODEMP, CODPROD, DESCRPROD, FABRICANTE, SELECIONADO,
            CODAGREGACAO, STATUS_LINHA,
            QTD_ENTRADA, QTD_BAIXADA_VENDA, QTD_BAIXADA_AVARIA,
            QTD_RESERVADA, QTD_DISPONIVEL, QTD_PENDENTE, QTD_AVARIA_INTERNA,
            VENDAVEL,
            NUNOTA_ORIGEM, DTNEG_ORIGEM, CODPARC_ORIGEM, NOMEPARC_ORIGEM
        FROM SANKHYA.ANDRE_IRIS_SALDO_LOTE
        WHERE {' AND '.join(where)}
    """
    sql = f"""
        SELECT * FROM (
            SELECT t.*, ROW_NUMBER() OVER (
                ORDER BY t.DESCRPROD, t.STATUS_LINHA, t.CODAGREGACAO
            ) AS RN
            FROM ({sql_base}) t
        ) WHERE RN BETWEEN :start_row AND :end_row
    """
    binds['start_row'] = int(offset) + 1
    binds['end_row']   = int(offset) + int(limite)

    cols = [
        'codemp', 'codprod', 'descrprod', 'fabricante', 'selecionado',
        'codagregacao', 'status_linha',
        'qtd_entrada', 'qtd_baixada_venda', 'qtd_baixada_avaria',
        'qtd_reservada', 'qtd_disponivel', 'qtd_pendente', 'qtd_avaria_interna',
        'vendavel',
        'nunota_origem', 'dtneg_origem', 'codparc_origem', 'nomeparc_origem',
    ]

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        rows = cur.fetchall()

    return [dict(zip(cols, row)) for row in rows]


def consultar_vinculos_de_lote(codagregacao: str) -> list[dict]:
    """Lista pedidos/vendas que tenham este CODAGREGACAO em TGFITE.

    Considera apenas TOPs 34 (pedido), 35 (venda c/ NFe) e 37 (venda s/ NFe).
    Não inclui TOP 13 (vale do fornecedor — CODPARC é o fornecedor, não cliente).
    Ignora STATUSNOTA='E'.
    """
    sql = """
        SELECT
            c.NUNOTA, c.CODEMP, c.CODTIPOPER, c.STATUSNOTA, c.DTNEG, c.CODPARC,
            p.NOMEPARC,
            i.SEQUENCIA, i.CODPROD, pr.DESCRPROD,
            NVL(i.QTDNEG, 0) AS QTDNEG
        FROM TGFITE i
        JOIN TGFCAB c       ON c.NUNOTA = i.NUNOTA
        LEFT JOIN TGFPAR p  ON p.CODPARC = c.CODPARC
        LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
        WHERE i.CODAGREGACAO = :l
          AND c.CODTIPOPER IN (34, 35, 37)
          AND c.STATUSNOTA <> 'E'
        ORDER BY c.DTNEG DESC, c.NUNOTA DESC, i.SEQUENCIA
    """
    cols = [
        'nunota', 'codemp', 'codtipoper', 'statusnota', 'dtneg', 'codparc',
        'nomeparc', 'sequencia', 'codprod', 'descrprod', 'qtdneg',
    ]
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, l=str(codagregacao))
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def consultar_fabricantes_disponiveis(termo: str = '', limite: int = 10) -> list[str]:
    """Lista FABRICANTEs DISTINTOS que têm pelo menos um lote vendável agora.

    Consulta SANKHYA.ANDRE_IRIS_SALDO_LOTE filtrando por QTD_DISPONIVEL > 0
    — versão original, comprovadamente funcional. O cache cliente-side
    carrega tudo no boot (1 fetch só), então o custo da view é pago uma vez
    por sessão e os filtros por keystroke ficam locais.
    """
    where = [
        "FABRICANTE IS NOT NULL",
        "QTD_DISPONIVEL > 0",
    ]
    binds: dict = {}
    termo = str(termo or '').strip()
    if termo:
        where.append("UPPER(FABRICANTE) LIKE :q")
        binds['q'] = f"%{termo.upper()}%"

    sql = f"""
        SELECT * FROM (
            SELECT DISTINCT FABRICANTE
            FROM SANKHYA.ANDRE_IRIS_SALDO_LOTE
            WHERE {' AND '.join(where)}
            ORDER BY FABRICANTE
        )
        WHERE ROWNUM <= :lim
    """
    binds['lim'] = int(limite)

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        return [str(r[0]) for r in cur.fetchall()]


def consultar_pedidos_abertos_para_atribuicao(filtros: dict | None = None,
                                              limite: int = 50, offset: int = 0) -> list[dict]:
    """Lista itens de pedidos TOP 34 em aberto (STATUSNOTA NOT IN 'L','E').

    Cada linha do retorno é um item (TGFITE) com qtd pedida e o lote já
    atribuído (CODAGREGACAO_ATUAL — None se ainda não atribuído).

    Filtros opcionais:
        q        busca textual (NUNOTA numérico ou NOMEPARC parcial)
        codprod  filtra itens de um produto específico
        nunota   filtra um pedido específico

    Paginação: limite (default 50) e offset (default 0). A paginação é por
    CABEÇALHO (NUNOTA): trazemos os N pedidos mais recentes e TODOS os itens
    deles. Isso evita "cortar" um pedido ao meio em scroll infinito.
    """
    filtros = filtros or {}
    # STATUSNOTA: ignora 'L' (faturado) na listagem para o operador ver tudo;
    # mantém o filtro de 'E' (excluídos), que sempre são lixo.
    # A validação de "não pode atribuir a faturado" continua ativa em
    # atribuir_lote_item_pedido, abaixo.
    where = ["c.CODTIPOPER = 34", "c.STATUSNOTA <> 'E'"]
    binds: dict = {}

    if filtros.get('nunota'):
        where.append("c.NUNOTA = :nunota")
        binds['nunota'] = int(filtros['nunota'])

    if filtros.get('codprod'):
        where.append(
            "EXISTS (SELECT 1 FROM TGFITE i2 WHERE i2.NUNOTA = c.NUNOTA AND i2.CODPROD = :codprod)"
        )
        binds['codprod'] = int(filtros['codprod'])

    # Filtro EXISTS IN — pedidos que tenham AO MENOS UM item em qualquer dos
    # codprods solicitados. Usado pelo filtro cruzado a partir dos lotes.
    codprods_in = filtros.get('codprods')
    if codprods_in:
        try:
            codprods_in = [int(x) for x in codprods_in if str(x).strip()]
        except (TypeError, ValueError):
            codprods_in = []
        if codprods_in:
            ks = []
            for i, cp in enumerate(codprods_in):
                k = f'cp_in_{i}'
                ks.append(':' + k)
                binds[k] = int(cp)
            where.append(
                "EXISTS (SELECT 1 FROM TGFITE i2 WHERE i2.NUNOTA = c.NUNOTA "
                f"AND i2.CODPROD IN ({', '.join(ks)}))"
            )

    termo = str(filtros.get('q') or '').strip()
    if termo:
        if termo.isdigit():
            where.append("c.NUNOTA = :q_nunota")
            binds['q_nunota'] = int(termo)
        else:
            where.append("UPPER(p.NOMEPARC) LIKE :q_parc")
            binds['q_parc'] = f"%{termo.upper()}%"

    # Cross filter vindo do typeahead de Lotes (FABRICANTE selecionado):
    # mostra apenas pedidos que têm pelo menos um item de produto cujo
    # FABRICANTE bate com o selecionado. Usa TGFPRO direto (mais rápido
    # que joinar com a view de saldo).
    fabricante = str(filtros.get('fabricante') or '').strip()
    if fabricante:
        where.append("""
            EXISTS (
                SELECT 1
                FROM TGFITE i_fab
                JOIN TGFPRO pr_fab ON pr_fab.CODPROD = i_fab.CODPROD
                WHERE i_fab.NUNOTA = c.NUNOTA
                  AND UPPER(pr_fab.FABRICANTE) = :fabricante
            )
        """)
        binds['fabricante'] = fabricante.upper()

    # Filtro de janela temporal: prioriza data_ini/data_fim (range explícito).
    # Fallback: desde_dias (legado, retrocompatibilidade dos testes).
    data_ini = (filtros.get('data_ini') or '').strip() or None
    data_fim = (filtros.get('data_fim') or '').strip() or None
    if data_ini or data_fim:
        if data_ini:
            where.append("c.DTNEG >= TO_DATE(:data_ini, 'YYYY-MM-DD')")
            binds['data_ini'] = data_ini
        if data_fim:
            where.append("c.DTNEG < TO_DATE(:data_fim, 'YYYY-MM-DD') + 1")
            binds['data_fim'] = data_fim
    else:
        desde_dias = filtros.get('desde_dias')
        try:
            desde_dias = int(desde_dias) if desde_dias not in (None, '') else 0
        except (TypeError, ValueError):
            desde_dias = 0
        if desde_dias > 0:
            where.append("c.DTNEG >= (TRUNC(SYSDATE) - :desde_dias)")
            binds['desde_dias'] = desde_dias

    # Filtro a nível de ITEM (não só de cabeçalho). Quando o cross filter de
    # FABRICANTE está ativo, queremos que cada pedido apareça SÓ com os itens
    # daquele fabricante — não com todos os outros produtos do pedido.
    # O EXISTS no inner WHERE seleciona quais NUNOTAs aparecem; este filtro
    # de item peneira as linhas da TGFITE retornadas para esse cabeçalho.
    item_where_parts = []
    if fabricante:
        item_where_parts.append("UPPER(pr.FABRICANTE) = :fabricante")
    # Mesma lógica para codprods do filtro cruzado: quando o usuário clica
    # num lote (ou em produto-linha), só os itens daquele(s) codprod(s) devem
    # aparecer dentro de cada pedido. Sem isso, o cabeçalho mostraria todos
    # os outros produtos junto.
    codprods_in = filtros.get('codprods')
    if codprods_in:
        try:
            cps = [int(x) for x in codprods_in if str(x).strip()]
        except (TypeError, ValueError):
            cps = []
        if cps:
            ks_item = []
            for i, cp in enumerate(cps):
                k = f'cp_item_{i}'
                ks_item.append(':' + k)
                binds[k] = int(cp)
            item_where_parts.append(f"i.CODPROD IN ({', '.join(ks_item)})")
    item_filter_sql = ('WHERE ' + ' AND '.join(item_where_parts)) if item_where_parts else ''

    # Paginação por cabeçalho compatível com Oracle 11g (ROW_NUMBER + BETWEEN).
    # Pega os N NUNOTAs mais recentes e depois traz TODOS os itens deles
    # (ou só os filtrados, quando há filtro de item ativo).
    # LEFT JOIN em ANDRE_IRIS_SALDO_LOTE traz dados de ORIGEM do lote
    # (data, parceiro do fornecedor, NUNOTA da TOP 11) p/ exibir no modal de vínculos.
    sql = f"""
        SELECT
            cp.NUNOTA, cp.CODEMP, cp.CODPARC, cp.NOMEPARC, cp.DTNEG,
            i.SEQUENCIA, i.CODPROD, pr.DESCRPROD,
            NVL(i.QTDNEG, 0)   AS QTD_PEDIDA,
            i.CODAGREGACAO     AS CODAGREGACAO_ATUAL,
            CASE WHEN i.CODAGREGACAO IS NULL THEN 'PENDENTE' ELSE 'ATRIBUIDO' END AS STATUS_ITEM,
            sl.NUNOTA_ORIGEM   AS LOTE_NUNOTA,
            sl.DTNEG_ORIGEM    AS LOTE_DTNEG,
            sl.CODPARC_ORIGEM  AS LOTE_CODPARC,
            sl.NOMEPARC_ORIGEM AS LOTE_NOMEPARC
        FROM (
            SELECT * FROM (
                SELECT t.*, ROW_NUMBER() OVER (
                    ORDER BY t.DTNEG DESC, t.NUNOTA DESC
                ) AS RN
                FROM (
                    SELECT c.NUNOTA, c.CODEMP, c.CODPARC, c.DTNEG, p.NOMEPARC
                    FROM TGFCAB c
                    LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
                    WHERE {' AND '.join(where)}
                ) t
            ) WHERE RN BETWEEN :start_row AND :end_row
        ) cp
        JOIN TGFITE i ON i.NUNOTA = cp.NUNOTA
        LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
        LEFT JOIN (
            SELECT i11.CODAGREGACAO,
                   MIN(c11.NUNOTA)   AS NUNOTA_ORIGEM,
                   MIN(c11.DTNEG)    AS DTNEG_ORIGEM,
                   MIN(c11.CODPARC)  AS CODPARC_ORIGEM,
                   MIN(p11.NOMEPARC) AS NOMEPARC_ORIGEM
            FROM TGFITE i11
            JOIN TGFCAB c11      ON c11.NUNOTA = i11.NUNOTA
            LEFT JOIN TGFPAR p11 ON p11.CODPARC = c11.CODPARC
            WHERE c11.CODTIPOPER = 11
              AND c11.STATUSNOTA <> 'E'
              AND i11.CODAGREGACAO IS NOT NULL
            GROUP BY i11.CODAGREGACAO
        ) sl ON sl.CODAGREGACAO = i.CODAGREGACAO
        {item_filter_sql}
        ORDER BY cp.DTNEG DESC, cp.NUNOTA DESC, i.SEQUENCIA
    """
    binds['start_row'] = int(offset) + 1
    binds['end_row']   = int(offset) + int(limite)

    cols = [
        'nunota', 'codemp', 'codparc', 'nomeparc', 'dtneg',
        'sequencia', 'codprod', 'descrprod',
        'qtd_pedida', 'codagregacao_atual', 'status_item',
        'lote_nunota', 'lote_dtneg', 'lote_codparc', 'lote_nomeparc',
    ]

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        rows = cur.fetchall()

    return [dict(zip(cols, row)) for row in rows]


def desvincular_lote_item_pedido(nunota: int, sequencia: int) -> dict:
    """Desvincula um lote de um item de pedido TOP 34.

    Comportamento:
        - Se EXISTE outra linha pendente (CODAGREGACAO IS NULL) do mesmo
          (NUNOTA, CODPROD): faz MERGE — soma o QTDNEG desta linha na linha
          pendente mais antiga + recalcula VLRTOT, depois DELETE desta.
          Evita acumular linhas órfãs após ciclos vincular/desvincular.
        - Se NÃO existe outra linha pendente do produto: apenas limpa
          CODAGREGACAO (esta era a única do produto, fica pendente).

    Validações:
        - Item precisa existir e ter CODAGREGACAO atualmente preenchido.
        - Pedido precisa ser TOP 34 e não estar faturado/excluído.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT c.CODTIPOPER, c.STATUSNOTA,
                       i.CODAGREGACAO, i.CODPROD, NVL(i.QTDNEG, 0)
                FROM TGFCAB c
                JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                WHERE c.NUNOTA = :n AND i.SEQUENCIA = :s
            """, n=int(nunota), s=int(sequencia))
            row = cur.fetchone()

            if not row:
                return {'ok': False, 'error': f'Item NUNOTA={nunota} SEQ={sequencia} não encontrado'}

            codtipoper, statusnota, codagregacao_atual, codprod, qtdneg = row

            if int(codtipoper) != 34:
                return {'ok': False, 'error': f'Operação não é TOP 34 (encontrada: TOP {codtipoper})'}
            if statusnota == 'L':
                return {'ok': False, 'error': 'Pedido já foi faturado — não é mais editável'}
            if statusnota == 'E':
                return {'ok': False, 'error': 'Pedido excluído'}
            if not codagregacao_atual:
                return {'ok': False, 'error': 'Item não tem lote vinculado'}

            qtd_atual = float(qtdneg)

            # Procura outra linha pendente do mesmo (NUNOTA, CODPROD).
            # ROWNUM=1 + subquery ordenada por SEQUENCIA garante a mais antiga.
            cur.execute("""
                SELECT SEQUENCIA FROM (
                    SELECT SEQUENCIA FROM TGFITE
                    WHERE NUNOTA = :n
                      AND CODPROD = :p
                      AND CODAGREGACAO IS NULL
                      AND SEQUENCIA <> :s
                    ORDER BY SEQUENCIA
                )
                WHERE ROWNUM = 1
            """, n=int(nunota), p=int(codprod), s=int(sequencia))
            outra = cur.fetchone()

            if outra and qtd_atual > 0:
                # MERGE: soma qtd na pendente, recalcula seu VLRTOT, deleta esta.
                # No mesmo UPDATE, QTDNEG e VLRTOT usam o valor antigo de QTDNEG
                # (Oracle avalia toda a expressão antes de aplicar). Então
                # VLRTOT fica = VLRUNIT * (QTDNEG_antigo + :q).
                outra_seq = int(outra[0])
                cur.execute("""
                    UPDATE TGFITE
                       SET QTDNEG = NVL(QTDNEG, 0) + :q,
                           VLRTOT = NVL(VLRUNIT, 0) * (NVL(QTDNEG, 0) + :q)
                     WHERE NUNOTA = :n AND SEQUENCIA = :o
                """, q=qtd_atual, n=int(nunota), o=outra_seq)
                cur.execute("""
                    DELETE FROM TGFITE
                    WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, n=int(nunota), s=int(sequencia))
                operacao = 'MERGE'
            else:
                # Não há outra linha pendente — só limpa o lote desta
                cur.execute("""
                    UPDATE TGFITE SET CODAGREGACAO = NULL
                    WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, n=int(nunota), s=int(sequencia))
                operacao = 'CLEAR'

            # Recalcula totais do cabeçalho (VLRNOTA / QTDVOL)
            recalcular_totais_nota_banco(int(nunota), conexao_existente=conn)

            conn.commit()
            return {
                'ok': True,
                'operacao': operacao,
                'codagregacao_removido': str(codagregacao_atual),
            }
    except Exception as e:
        logger.exception("Erro em desvincular_lote_item_pedido")
        return {'ok': False, 'error': str(e)}


def atribuir_lote_item_pedido(nunota: int, sequencia: int, codagregacao: str,
                              qtd: float | None = None) -> dict:
    """Atribui um lote a um item de pedido TOP 34.

    Comportamento:
        - Se ``qtd`` é None ou igual à QTDNEG do item: UPDATE simples no CODAGREGACAO
          da linha existente.
        - Se ``qtd`` < QTDNEG do item: divide a linha — UPDATE reduzindo a qtd da
          original e INSERT de uma nova linha com a qtd atribuída e o novo lote.

    Validações:
        - Pedido tem que ser TOP 34 e não estar faturado/excluído.
        - Lote precisa ter saldo suficiente em ANDRE_IRIS_SALDO_LOTE (VENDAVEL='S').

    UPDATE direto (não usa atualizar_item_nota_banco) para evitar a auto-cura
    de AD_NUMPEDIDOORIG, que é específica da Entrada/Classificação e poderia
    bagunçar a origem do pedido de venda.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1) Valida o pedido e o item
            cur.execute("""
                SELECT c.CODTIPOPER, c.STATUSNOTA, i.CODPROD, NVL(i.QTDNEG, 0), i.CODEMP
                FROM TGFCAB c
                JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                WHERE c.NUNOTA = :n AND i.SEQUENCIA = :s
            """, n=int(nunota), s=int(sequencia))
            row = cur.fetchone()

            if not row:
                return {'ok': False, 'error': f'Item NUNOTA={nunota} SEQ={sequencia} não encontrado'}

            codtipoper, statusnota, codprod, qtd_item, codemp = row

            if int(codtipoper) != 34:
                return {'ok': False, 'error': f'Operação não é TOP 34 (encontrada: TOP {codtipoper})'}
            if statusnota == 'L':
                return {'ok': False, 'error': 'Pedido já foi faturado — não é mais editável'}
            if statusnota == 'E':
                return {'ok': False, 'error': 'Pedido excluído'}

            qtd_item_f = float(qtd_item)
            qtd_atribuir = float(qtd) if qtd is not None else qtd_item_f

            if qtd_atribuir <= 0:
                return {'ok': False, 'error': 'Qtd a atribuir deve ser > 0'}
            if qtd_atribuir > qtd_item_f + 1e-6:
                return {'ok': False, 'error':
                        f'Qtd a atribuir ({qtd_atribuir}) maior que qtd do item ({qtd_item_f})'}

            # 2) Valida saldo do lote na view (ignora CODEMP — permite vincular
            #    lote de uma empresa em pedido de outra; soma o saldo do lote
            #    em todas as empresas onde ele aparece como vendável).
            cur.execute("""
                SELECT NVL(SUM(QTD_DISPONIVEL), 0)
                FROM SANKHYA.ANDRE_IRIS_SALDO_LOTE
                WHERE CODPROD = :p AND CODAGREGACAO = :l
                  AND VENDAVEL = 'S'
            """, p=int(codprod), l=str(codagregacao))
            res_saldo = cur.fetchone()
            qtd_disp = float(res_saldo[0]) if res_saldo else 0.0

            if qtd_disp + 1e-6 < qtd_atribuir:
                return {'ok': False, 'error':
                        f'Saldo insuficiente no lote {codagregacao}: '
                        f'disponível={qtd_disp}, solicitado={qtd_atribuir}'}

            # 3) Aplica a atribuição
            if abs(qtd_atribuir - qtd_item_f) < 1e-6:
                # 3a) Atribuição total — UPDATE simples
                cur.execute("""
                    UPDATE TGFITE SET CODAGREGACAO = :l
                    WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, l=str(codagregacao), n=int(nunota), s=int(sequencia))
                operacao = 'UPDATE'
                nova_seq = None
            else:
                # 3b) Atribuição parcial — divide a linha
                cur.execute(
                    "SELECT NVL(MAX(SEQUENCIA), 0) + 1 FROM TGFITE WHERE NUNOTA = :n",
                    n=int(nunota),
                )
                nova_seq = int(cur.fetchone()[0])

                # Reduz qtd da linha original e recalcula seu VLRTOT
                cur.execute("""
                    UPDATE TGFITE
                       SET QTDNEG = QTDNEG - :q,
                           VLRTOT = NVL(VLRUNIT, 0) * (NVL(QTDNEG, 0) - :q)
                     WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, q=qtd_atribuir, n=int(nunota), s=int(sequencia))

                # Cria nova linha com o lote atribuído (espelha campos da original)
                cur.execute("""
                    INSERT INTO TGFITE (
                        NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG,
                        VLRUNIT, VLRTOT, CODVOL, CODLOCALORIG, CODAGREGACAO,
                        AD_NUMPEDIDOORIG
                    )
                    SELECT :n_dest, :s_dest, CODEMP, CODPROD, :q,
                           VLRUNIT, NVL(VLRUNIT, 0) * :q, CODVOL, CODLOCALORIG, :l,
                           AD_NUMPEDIDOORIG
                      FROM TGFITE
                     WHERE NUNOTA = :n_orig AND SEQUENCIA = :s_orig
                """, n_dest=int(nunota), s_dest=nova_seq, q=qtd_atribuir,
                     l=str(codagregacao), n_orig=int(nunota), s_orig=int(sequencia))
                operacao = 'SPLIT'

            # 4) Recalcula totais do cabeçalho
            recalcular_totais_nota_banco(int(nunota), conexao_existente=conn)

            conn.commit()
            return {
                'ok': True,
                'operacao': operacao,
                'qtd_atribuida': qtd_atribuir,
                'nova_sequencia': nova_seq,
            }
    except Exception as e:
        logger.exception("Erro em atribuir_lote_item_pedido")
        return {'ok': False, 'error': str(e)}
