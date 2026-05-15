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


# ==============================================================================
# 🌐 HUMANIZADOR DE ERROS ORACLE
# Traduz códigos ORA-XXXXX e mensagens técnicas em frases compreensíveis
# para o operador. Mantém a mensagem original ao final entre parênteses
# para suporte/debug. Usado em todas as APIs de escrita de Venda e Rastreio.
# ==============================================================================
_MAPA_ORA_HUMANIZADO = (
    # (substring buscada, mensagem amigável)
    # ORA-20101 é o código de RAISE_APPLICATION_ERROR usado por MUITAS triggers
    # Sankhya (não só "Tipo de negociação inativo"). O humanizar_erro_oracle
    # tem case especial pra ORA-20101 (logo abaixo) que extrai a mensagem real
    # do trigger ANTES de cair no fallback genérico. Esta entrada só serve de
    # fallback quando a extração falhar.
    ('ORA-20101',  'Regra do banco rejeitou a operação. Verifique os dados informados.'),
    ('ORA-00001',  'Já existe um registro com esses dados (chave duplicada).'),
    ('ORA-02291',  'Referência inválida — algum código informado não existe no banco.'),
    ('ORA-02292',  'Não é possível remover este registro porque ele tem dependências.'),
    ('ORA-01400',  'Há um campo obrigatório sem valor. Preencha todos os campos marcados.'),
    ('ORA-01438',  'Valor numérico maior do que o permitido para este campo.'),
    ('ORA-01722',  'Número inválido — verifique campos numéricos.'),
    ('ORA-01861',  'Data com formato inválido. Use o seletor de data.'),
    ('ORA-12899',  'Texto digitado é maior do que o permitido para este campo.'),
    ('ORA-00054',  'Outro operador está mexendo neste registro agora. Aguarde alguns segundos e tente novamente. Se o erro persistir após 1 minuto, avise o suporte.'),
    ('ORA-08177',  'Conflito ao salvar — outro usuário alterou os dados ao mesmo tempo. Recarregue e tente novamente.'),
    ('DPY-1001',   'Conexão com o banco caiu durante a operação. Tente novamente.'),
    ('DPY-4011',   'Conexão com o banco caiu durante a operação. Tente novamente.'),
)


def humanizar_erro_oracle(exc_or_msg) -> str:
    """Converte exceção/mensagem do Oracle em texto amigável ao usuário.

    Aceita ``Exception`` ou ``str``. Faz match por substring (case-sensitive)
    nos códigos ORA-* mais comuns. Se não encontrar correspondência, devolve
    a primeira linha da mensagem original (sanitizada para evitar vazar
    stack traces ou paths internos).

    A intenção é mostrar isso ao operador no toast — não substitui o
    ``logger.exception`` que continua registrando o erro completo.
    """
    if exc_or_msg is None:
        return 'Falha desconhecida.'
    msg = str(exc_or_msg)
    if not msg:
        return 'Falha desconhecida.'

    # Case especial: ORA-20101 é genérico (usado por dezenas de triggers Sankhya).
    # Tenta extrair a mensagem real do trigger antes do mapping genérico.
    # Formato típico Oracle: "ORA-20101: <mensagem do trigger>\nORA-06512: at ..."
    if 'ORA-20101' in msg:
        import re
        m = re.search(r'ORA-20101:\s*(.+?)(?:\n|ORA-\d|$)', msg, re.DOTALL)
        if m:
            real = m.group(1).strip().rstrip('.').strip()
            if real and len(real) <= 240:
                return real

    for chave, amigavel in _MAPA_ORA_HUMANIZADO:
        if chave in msg:
            return amigavel
    # Fallback: pega a primeira linha não vazia, limita tamanho.
    primeira = next((l.strip() for l in msg.splitlines() if l.strip()), msg.strip())
    if len(primeira) > 200:
        primeira = primeira[:197] + '...'
    return primeira

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

def gerar_proxima_sequencia_item(nunota: int, conexao_existente=None) -> int:
    """Consulta a TGFITE e retorna MAX(SEQUENCIA) + 1 para uma nota específica.

    Mai/2026 (2026-05-13): aceita `conexao_existente` opcional. Sem ele, abre
    NOVA conexão (default histórico) — que NÃO vê transação pendente do caller.
    Em fluxos transacionais (ex: edição de entrada B14, onde múltiplos INSERTs
    sucessivos acontecem antes do commit), passar `conexao_existente=conn`
    garante que a SEQUENCIA enxergue os INSERTs anteriores da mesma transação.
    """
    sql = "SELECT NVL(MAX(SEQUENCIA),0) + 1 FROM TGFITE WHERE NUNOTA = :nunota"
    if conexao_existente is not None:
        cur = conexao_existente.cursor()
        cur.execute(sql, nunota=nunota)
        return int(cur.fetchone()[0])
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
        # Mai/2026 (2026-05-13): passa a conexão atual pra `gerar_proxima_sequencia_item`
        # — necessário em fluxos transacionais onde múltiplos INSERTs precedem commit
        # (ex: edição de entrada B14). Sem isso, função abre nova conexão que não
        # enxerga os INSERTs anteriores e gera SEQUENCIAs duplicadas (ORA-00001).
        sequencia = gerar_proxima_sequencia_item(nunota, conexao_existente=conn)
        
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

        # Espelhamento automático (Mai/2026) — produto não-classificável
        # (GERAPRODUCAO ≠ 'S') com PESO > 0 já recebe QTDFIXADA = PESO no
        # INSERT. Evita estado intermediário com QTDFIXADA NULL na TOP 11
        # antes do Fast-Track rodar. Não toca classificáveis ('S'): esses
        # têm QTDFIXADA preenchida depois pela Comercial via botão
        # "Peso CX Classificado" (`atualizar_peso_comercial_entrada`).
        geraprod_normalizado = str(geraproducao or '').strip().upper()
        if (geraprod_normalizado and geraprod_normalizado != 'S'
                and peso and float(peso) > 0
                and 'QTDFIXADA' in colunas_tabela):
            colunas_sql.append('QTDFIXADA')
            valores_sql.append(':QTDFIXADA')
            binds['QTDFIXADA'] = float(peso)

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

    # Mai/2026 — filtro por FABRICANTE (UI: campo "Produto").
    # Replica o padrão do Comercial (consultar_vales_comercial, linha 1232):
    # UPPER(...) LIKE %fab% — pega lotes cujo produto tem fabricante contendo
    # o texto. JOIN extra com TGFPRO (PK indexed) é desprezível em custo.
    # EXISTS preserva GROUP BY + agregação SUM(VLRTOT) do SELECT base.
    if kwargs.get('fabricante'):
        where.append(
            "EXISTS ("
            "  SELECT 1 FROM TGFITE i2 "
            "  JOIN TGFPRO pr2 ON pr2.CODPROD = i2.CODPROD "
            "  WHERE i2.NUNOTA = c.NUNOTA "
            "    AND UPPER(pr2.FABRICANTE) LIKE :fab"
            ")"
        )
        binds['fab'] = f"%{str(kwargs['fabricante']).upper()}%"

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
                                'OBSERVACAO': 'Faturamento automático via IAgro',
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
    """Atualiza o Peso Classificado (QTDFIXADA) do item na TOP 11.

    Side effect (Mai/2026): se já existe vale TOP 13 salvo pro mesmo lote,
    propaga o novo peso pra TGFITE.PESO de todos os itens da TOP 13 do lote.
    Mantém coerência com o INSERT inicial feito em salvar_vale_compra_banco —
    operador pode reajustar o peso a qualquer momento sem precisar abrir
    o vale.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    peso = float(peso_classificado)

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. UPDATE QTDFIXADA na TOP 11 (comportamento existente)
            cur.execute(
                "UPDATE TGFITE SET QTDFIXADA = :peso "
                "WHERE NUNOTA = :nunota AND SEQUENCIA = :seq",
                peso=peso, nunota=int(nunota), seq=int(sequencia),
            )

            # 2. Identifica o lote da linha alterada
            cur.execute(
                "SELECT CODAGREGACAO FROM TGFITE "
                "WHERE NUNOTA = :n AND SEQUENCIA = :s",
                n=int(nunota), s=int(sequencia),
            )
            row = cur.fetchone()
            lote = (row[0] if row else None) or None

            # 3. Propaga pra TGFITE.PESO da TOP 13 do mesmo lote, se já existir vale
            propagado_top13 = 0
            if lote:
                cur.execute(
                    "SELECT MAX(NUNOTA) FROM TGFCAB "
                    "WHERE CODTIPOPER = 13 AND NUMNOTA = :n",
                    n=int(nunota),
                )
                res13 = cur.fetchone()
                nunota_13 = int(res13[0]) if res13 and res13[0] else None

                if nunota_13:
                    cur.execute(
                        "UPDATE TGFITE SET PESO = :peso "
                        "WHERE NUNOTA = :n13 AND CODAGREGACAO = :l",
                        peso=peso, n13=nunota_13, l=lote,
                    )
                    propagado_top13 = cur.rowcount or 0

            conn.commit()
            return {'ok': True, 'executed': True, 'propagado_top13': propagado_top13}
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

            # 0. Pré-requisito: linha da TOP 11 origem do lote precisa ter PESO
            # OU QTDFIXADA preenchido. Se só um dos dois estiver, espelha o
            # vazio com o preenchido (casos comuns: in natura sem Fast-Track
            # tem só PESO; classificável após "Peso CX Classificado" tem só
            # QTDFIXADA). Bloqueia só se ambos NULL/0. O valor consolidado é
            # propagado pra TGFITE.PESO de TODOS os itens da TOP 13 do lote.
            cur.execute(
                """
                SELECT NVL(MAX(PESO), 0), NVL(MAX(QTDFIXADA), 0)
                  FROM TGFITE
                 WHERE NUNOTA = :n
                   AND CODAGREGACAO = :l
                """,
                n=nunota_origem, l=lote,
            )
            row_pesos = cur.fetchone()
            peso_top11 = float(row_pesos[0] or 0) if row_pesos else 0.0
            qtdfix_top11 = float(row_pesos[1] or 0) if row_pesos else 0.0

            if peso_top11 <= 0 and qtdfix_top11 <= 0:
                return {
                    'ok': False,
                    'error': 'Informe o peso classificado da caixa antes de salvar o vale.',
                }

            # Espelhamento bidirecional na TOP 11 — preenche o lado vazio
            # com o valor do lado preenchido. Idempotente: filtro NVL(...,0)=0
            # garante que só atualiza o que está realmente vazio.
            if peso_top11 > 0 and qtdfix_top11 <= 0:
                cur.execute(
                    "UPDATE TGFITE SET QTDFIXADA = :p "
                    "WHERE NUNOTA = :n AND CODAGREGACAO = :l "
                    "AND NVL(QTDFIXADA, 0) = 0",
                    p=peso_top11, n=nunota_origem, l=lote,
                )
                peso_classificado = peso_top11
            elif qtdfix_top11 > 0 and peso_top11 <= 0:
                cur.execute(
                    "UPDATE TGFITE SET PESO = :p "
                    "WHERE NUNOTA = :n AND CODAGREGACAO = :l "
                    "AND NVL(PESO, 0) = 0",
                    p=qtdfix_top11, n=nunota_origem, l=lote,
                )
                peso_classificado = qtdfix_top11
            else:
                # Ambos preenchidos — usa QTDFIXADA (peso classificado tem
                # prioridade sobre o PESO digitado na Entrada)
                peso_classificado = qtdfix_top11

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
                    'OBSERVACAO': f'Faturamento via IAgro',
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

                # PESO propagado da TOP 11.QTDFIXADA (peso classificado do lote)
                # — mesmo valor pra todos os itens da TOP 13 do lote (Extra/Médio
                # vêm da mesma classificação física).
                cur.execute("""
                    INSERT INTO TGFITE (
                        NUNOTA, SEQUENCIA, CODEMP, CODPROD,
                        QTDNEG, VLRUNIT, VLRTOT, CODAGREGACAO,
                        CODVOL, CODLOCALORIG, AD_NUMPEDIDOORIG,
                        PESO
                    )
                    VALUES (
                        :nunota, :seq, :emp, :prod,
                        :qtd, :vlr, :tot, :lote,
                        'KG', 101, :origem,
                        :peso
                    )
                """, {
                    'nunota': nunota_13, 'seq': prox_seq, 'emp': codemp_13,
                    'prod': codprod, 'qtd': qtdneg, 'vlr': vlrunit, 'tot': vlrtot,
                    'lote': lote, 'origem': ad_numpedidoorig,
                    'peso': peso_classificado,
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
                    'OBSERVACAO': 'Faturamento via IAgro',
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

            # 5.1 Propagação Mai/2026 — pra produto não-classificável (in natura),
            # o preço da Comercial é o preço efetivo de compra. Replica pra TGFITE
            # da TOP 11 (PRECOBASE, VLRUNIT, VLRTOT) e recalcula o cabeçalho TOP 11.
            # Operador da Entrada não digita preço — quem trabalha valores é sempre
            # a Comercial, então propagar mantém o card Entrada coerente com o vale.
            # Classificáveis ('S') ficam intactos — preço pode legitimamente diferir.
            geraprod_norm = str(geraprod_origem or '').strip().upper()
            if geraprod_norm and geraprod_norm != 'S':
                cur.execute("""
                    UPDATE TGFITE
                       SET PRECOBASE = :preco,
                           VLRUNIT   = :preco,
                           VLRTOT    = :preco * NVL(QTDNEG, 0)
                     WHERE NUNOTA = :n_orig
                       AND CODPROD = :prod
                """, preco=float(novo_preco), n_orig=int(nunota_origem), prod=int(codprod))

                if cur.rowcount and cur.rowcount > 0:
                    recalcular_totais_nota_banco(nunota_origem, conexao_existente=conn)

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

# ------------------------------------------------------------------
# CODNAT por TOP — usado em criar/atualizar pedido e em faturar
# (ver tabela de referência no CLAUDE.md §2 — módulo Venda).
# Centralizado aqui para uma única fonte da verdade.
# ------------------------------------------------------------------
CODNAT_POR_TOP = {
    30: 20010200,  # Avaria interna (perda no estoque) — DESCRNAT "AVARIA"
    34: 10010100,  # Pedido de Venda
    35: 10010100,  # Venda com NFe
    36: 10020100,  # Devolução de venda — DESCRNAT "DEVOLUCAO DE VENDA"
    37: 10010200,  # Venda sem NFe
}


def faturar_pedido_venda_banco(nunota: int, nova_top: int,
                               codusu_logado: int | None = None) -> dict:
    """Fatura um Pedido TOP 34 transformando-o em TOP 35 (NFe) ou 37 (s/ NFe).

    Operações dentro de UMA transação:
      1) Lock SELECT FOR UPDATE da TGFCAB (NUNOTA).
      2) Validações: pedido existe, é TOP 34 (não-faturado), não está excluído,
         tem ao menos 1 item, e (importante!) **todos os itens têm CODAGREGACAO**.
         Pedido sem lote em algum item NÃO pode ser faturado.
      3) UPDATE TGFCAB SET CODTIPOPER=:nova_top, CODNAT=:nova_codnat,
                         STATUSNOTA='L', DTFATUR=SYSDATE, NUMNOTA=...
         (NUMNOTA é incremental por CODEMP+série; aqui usamos sequence simples
          baseada em NVL(MAX(NUMNOTA),0)+1 dentro da própria CODEMP — aceitável
          até a integração formal de numeração de NFe.)

    Não dispara emissão de NFe via webservice — isso é tarefa do Sankhya
    (TOP 35 marcada para emissão fica visível no painel do ERP).

    Parâmetros:
        nunota: NUNOTA do pedido TOP 34 a faturar.
        nova_top: 35 (com NFe) ou 37 (sem NFe).
        codusu_logado: codusu do usuário (informativo, não-bloqueante).

    Retorno:
        {ok: bool, executed: bool, error?: str, nunota: int, top: int,
         numnota: int|None, codnat: int}
    """
    resultado = {'ok': False, 'executed': False, 'nunota': nunota}

    if not verificar_permissao_escrita():
        resultado['error'] = 'Escrita desabilitada'
        return resultado

    if int(nova_top) not in (35, 37):
        resultado['error'] = f'TOP de faturamento inválido: {nova_top} (esperado 35 ou 37)'
        return resultado

    nova_codnat = CODNAT_POR_TOP.get(int(nova_top))
    if nova_codnat is None:
        resultado['error'] = f'CODNAT não mapeado para TOP {nova_top}'
        return resultado

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            try:
                # 1) Lock pessimista do cabeçalho — evita faturamento duplicado
                cur.execute("""
                    SELECT CODTIPOPER, STATUSNOTA, CODEMP, NVL(VLRNOTA, 0)
                    FROM TGFCAB
                    WHERE NUNOTA = :n
                    FOR UPDATE
                """, n=int(nunota))
                row = cur.fetchone()
                if not row:
                    resultado['error'] = 'Pedido não encontrado'
                    return resultado

                codtipoper, statusnota, codemp, vlrnota = row
                if int(codtipoper) != 34:
                    resultado['error'] = (
                        f'Pedido já foi faturado ou é de outra operação '
                        f'(TOP atual: {codtipoper}).'
                    )
                    return resultado
                if statusnota == 'L':
                    resultado['error'] = 'Pedido já consta como faturado.'
                    return resultado
                if statusnota == 'E':
                    resultado['error'] = 'Pedido foi excluído — não pode ser faturado.'
                    return resultado

                # 2) Valida itens — precisa ter ao menos 1, e nenhum com lote pendente
                cur.execute("""
                    SELECT COUNT(*),
                           SUM(CASE WHEN CODAGREGACAO IS NULL THEN 1 ELSE 0 END)
                    FROM TGFITE WHERE NUNOTA = :n
                """, n=int(nunota))
                total_itens, itens_sem_lote = cur.fetchone()
                if int(total_itens or 0) == 0:
                    resultado['error'] = 'Pedido sem itens — não pode ser faturado.'
                    return resultado
                if int(itens_sem_lote or 0) > 0:
                    resultado['error'] = (
                        f'Pedido tem {int(itens_sem_lote)} item(ns) sem lote vinculado. '
                        f'Vincule todos os lotes no Rastreio antes de faturar.'
                    )
                    return resultado

                # 3) Próximo NUMNOTA dentro do CODEMP — simples e suficiente para
                #    o MVP. Numeração formal de NFe é responsabilidade do Sankhya.
                cur.execute("""
                    SELECT NVL(MAX(NUMNOTA), 0) + 1
                    FROM TGFCAB
                    WHERE CODEMP = :e
                      AND CODTIPOPER IN (35, 37)
                """, e=int(codemp))
                proximo_numnota = int(cur.fetchone()[0])

                # 4) Atualiza o cabeçalho — só colunas conhecidas. Se DTFATUR
                #    não existir nesta versão da TGFCAB, ignora silenciosamente.
                colunas = _obter_colunas_da_tabela(conn, 'TGFCAB')
                set_parts = ["CODTIPOPER = :top", "CODNAT = :nat",
                             "STATUSNOTA = 'L'", "NUMNOTA = :num"]
                binds = {
                    'top': int(nova_top),
                    'nat': int(nova_codnat),
                    'num': proximo_numnota,
                    'n': int(nunota),
                }
                if 'DTFATUR' in colunas:
                    set_parts.append("DTFATUR = SYSDATE")
                if 'DTMOV' in colunas:
                    set_parts.append("DTMOV = SYSDATE")
                if 'CODUSU' in colunas and codusu_logado:
                    set_parts.append("CODUSU = :u")
                    binds['u'] = int(codusu_logado)

                sql = f"UPDATE TGFCAB SET {', '.join(set_parts)} WHERE NUNOTA = :n"
                cur.execute(sql, binds)

                conn.commit()
                resultado.update({
                    'ok': True, 'executed': True,
                    'top': int(nova_top), 'numnota': proximo_numnota,
                    'codnat': int(nova_codnat), 'vlrnota': float(vlrnota or 0),
                })
                return resultado
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as e:
        logger.exception("Erro em faturar_pedido_venda_banco")
        resultado['error'] = str(e)
        return resultado


def listar_vendas_paginado(limite: int = 50, offset: int = 0, **kwargs):
    # TOP 30 (Avaria) e 36 (Devolução) entram na mesma lista — operador filtra via select.
    where = ["c.CODTIPOPER IN (30, 34, 35, 36, 37)", "c.STATUSNOTA <> 'E'"]
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
            c.CODEMP,
            c.OBSERVACAO
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
# Lê da view SANKHYA.ANDRE_IAGRO_SALDO_LOTE (TGFEST não é tocada).
# ==============================================================================

def consultar_saldo_lote_disponivel(filtros: dict | None = None,
                                    limite: int = 50, offset: int = 0) -> list[dict]:
    """Saldo por (CODEMP, CODPROD, CODAGREGACAO) lendo da ANDRE_IAGRO_SALDO_LOTE.

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

    # Filtro combinado lote OU produto (Mai/2026): texto do campo principal
    # bate em CODAGREGACAO OU DESCRPROD via OR. Placeholder do input já é
    # "Buscar lote ou produto…" — agora consistente com isso.
    if filtros.get('q_lote_prod'):
        termo_lp = str(filtros['q_lote_prod']).strip().upper()
        if termo_lp:
            where.append(
                "(UPPER(CODAGREGACAO) LIKE :qlp OR UPPER(DESCRPROD) LIKE :qlp)"
            )
            binds['qlp'] = f"%{termo_lp}%"

    # Filtro exato de FORNECEDOR (Mai/2026 — antes era FABRICANTE de TGFPRO).
    # Agora aponta pra NOMEPARC_ORIGEM (parceiro da TOP 11 do lote), que é
    # o "fornecedor real" exibido nos cards. Parâmetro mantido como
    # `fabricante` por compatibilidade com chamadas existentes.
    if filtros.get('fabricante'):
        where.append("UPPER(NOMEPARC_ORIGEM) = :fab_exato")
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
                WHERE i_cli.CODPROD       = ANDRE_IAGRO_SALDO_LOTE.CODPROD
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
            # Mai/2026: filtro `q` legado agora aponta pra NOMEPARC_ORIGEM
            # (fornecedor real do lote) — antes era FABRICANTE de produto.
            where.append("UPPER(NOMEPARC_ORIGEM) LIKE :q_fornecedor")
            binds['q_fornecedor'] = f"%{termo.upper()}%"

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
        FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
        WHERE {' AND '.join(where)}
    """
    # Ordenação pedida pelo usuário: data DESC (mais recente primeiro)
    # → produto (alfabético) → status → lote como tiebreaker.
    # NULLs em DTNEG_ORIGEM vão pro fim da lista (NULLS LAST).
    sql = f"""
        SELECT * FROM (
            SELECT t.*, ROW_NUMBER() OVER (
                ORDER BY t.DTNEG_ORIGEM DESC NULLS LAST,
                         t.DESCRPROD,
                         t.STATUS_LINHA,
                         t.CODAGREGACAO
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
    """Lista FORNECEDORES DISTINTOS que têm pelo menos um lote vendável agora.

    Mai/2026 — refatorado: consulta DISTINCT em `NOMEPARC_ORIGEM` (parceiro da
    TOP 11 que originou o lote), NÃO mais em `FABRICANTE`. Razão: cadastro
    Sankhya da Agromil tem TGFPRO.FABRICANTE populado com nome do produto
    (LIMÃO, BATATA DOCE...), não com fornecedor de fato. O parceiro real
    do lote (DEBORA, BRUNO, JOSE DO ALHO...) está em NOMEPARC_ORIGEM.

    Nome da função preservado pra não quebrar imports/endpoints existentes;
    o conceito virou "fornecedor do lote".
    """
    where = [
        "NOMEPARC_ORIGEM IS NOT NULL",
        "QTD_DISPONIVEL > 0",
    ]
    binds: dict = {}
    termo = str(termo or '').strip()
    if termo:
        where.append("UPPER(NOMEPARC_ORIGEM) LIKE :q")
        binds['q'] = f"%{termo.upper()}%"

    sql = f"""
        SELECT * FROM (
            SELECT DISTINCT NOMEPARC_ORIGEM
            FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
            WHERE {' AND '.join(where)}
            ORDER BY NOMEPARC_ORIGEM
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
    # Toggle Pendente/Finalizado (Mai/2026, B9): substitui Pendente/Faturado.
    # O critério deixa de ser STATUSNOTA da nota e passa a ser **completude do
    # rastreio** (existem itens com CODAGREGACAO IS NULL?).
    #   - mostrar_pendentes   → pedido com ao menos 1 item sem lote vinculado
    #   - mostrar_finalizados → pedido com TODOS os itens vinculados
    # Em ambos os caminhos lista TOP 34 (em aberto ou STATUSNOTA='L') e notas
    # órfãs TOP 35/37, sem duplicar — quando TOP 34 tem TGFVAR par, a TOP 35/37
    # correspondente NÃO entra como órfã (definição de órfã: sem TGFVAR + sem
    # vínculo manual).
    # Compat: `mostrar_faturados` ainda aceito como alias retro de
    # `mostrar_finalizados`; `incluir_finalizados=True` ainda vale como "ambos".
    mostrar_pendentes  = filtros.get('mostrar_pendentes')
    mostrar_finalizados = filtros.get('mostrar_finalizados')
    if mostrar_finalizados is None:
        # alias retro: mostrar_faturados → mostrar_finalizados
        mostrar_finalizados = filtros.get('mostrar_faturados')
    if mostrar_pendentes is None and mostrar_finalizados is None:
        if bool(filtros.get('incluir_finalizados')):
            mostrar_pendentes  = True
            mostrar_finalizados = True
        else:
            mostrar_pendentes  = True
            mostrar_finalizados = False
    else:
        mostrar_pendentes  = bool(mostrar_pendentes)
        mostrar_finalizados = bool(mostrar_finalizados)

    if not mostrar_pendentes and not mostrar_finalizados:
        # Sem nenhum status selecionado: retorna lista vazia sem ir ao banco.
        return []

    # Nota com vínculo manual deixa de ser órfã — aparece via PEDIDO.
    NOTA_TEM_VINCULO_MANUAL = (
        "EXISTS ("
        "  SELECT 1 FROM AD_VINCULO_PEDIDO_NOTA av"
        "   WHERE av.NUNOTA_NOTA = c.NUNOTA"
        ")"
    )

    # Critério novo (B9, Mai/2026) — completude do rastreio do TGFITE.
    # "Tem item sem lote" = existe pelo menos 1 TGFITE com CODAGREGACAO NULL
    # naquele NUNOTA. Aplica a TOP 34 (todos os status exceto 'E') e a TOP
    # 35/37 órfãs. Sem duplicação: notas TOP 35/37 só entram como ÓRFÃ
    # (sem TGFVAR + sem vínculo manual), nunca ao lado da TOP 34 par.
    TEM_ITEM_SEM_LOTE = (
        "EXISTS ("
        "  SELECT 1 FROM TGFITE i_check"
        "   WHERE i_check.NUNOTA = c.NUNOTA"
        "     AND i_check.CODAGREGACAO IS NULL"
        ")"
    )
    TODOS_ITENS_COM_LOTE = (
        "EXISTS ("
        "  SELECT 1 FROM TGFITE i_any WHERE i_any.NUNOTA = c.NUNOTA"
        ")"
        f" AND NOT {TEM_ITEM_SEM_LOTE}"
    )

    # Predicado de completude por toggle. Se ambos ligados, omite filtro
    # (mostra completos e incompletos juntos).
    if mostrar_pendentes and mostrar_finalizados:
        completude_clause = "1 = 1"
    elif mostrar_pendentes:
        completude_clause = TEM_ITEM_SEM_LOTE
    else:  # só mostrar_finalizados
        completude_clause = f"({TODOS_ITENS_COM_LOTE})"

    condicoes_or = [
        # TOP 34 (em aberto + faturado), aplicando completude
        f"(c.CODTIPOPER = 34 AND c.STATUSNOTA <> 'E' AND {completude_clause})",
        # Notas órfãs TOP 35/37 (sem TGFVAR + sem vínculo manual), aplicando completude
        "(c.CODTIPOPER IN (35, 37) AND c.STATUSNOTA = 'L'"
        " AND NOT EXISTS (SELECT 1 FROM TGFVAR v WHERE v.NUNOTA = c.NUNOTA)"
        f" AND NOT {NOTA_TEM_VINCULO_MANUAL}"
        f" AND {completude_clause})",
    ]

    where = [f"({' OR '.join(condicoes_or)})"]
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

    # Cross filter vindo do typeahead de Fornecedor (Mai/2026 refatorado):
    # mostra apenas pedidos cujos itens tenham produtos presentes em lotes
    # vendáveis cujo NOMEPARC_ORIGEM (parceiro da TOP 11) bate com o
    # selecionado. Antes filtrava por TGFPRO.FABRICANTE (= nome do produto
    # na Agromil), que não casava com a expectativa do operador.
    fabricante = str(filtros.get('fabricante') or '').strip()
    if fabricante:
        where.append("""
            EXISTS (
                SELECT 1
                FROM TGFITE i_fab
                WHERE i_fab.NUNOTA = c.NUNOTA
                  AND EXISTS (
                    SELECT 1 FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE sl
                     WHERE sl.CODPROD = i_fab.CODPROD
                       AND UPPER(sl.NOMEPARC_ORIGEM) = :fabricante
                       AND sl.QTD_DISPONIVEL > 0
                  )
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
    # LEFT JOIN em ANDRE_IAGRO_SALDO_LOTE traz dados de ORIGEM do lote
    # (data, parceiro do fornecedor, NUNOTA da TOP 11) p/ exibir no modal de vínculos.
    # NOTA_NUMNOTA e NOTA_NUNOTA (Mai/2026): quando o pedido tem nota correlata,
    # busca NUMNOTA + NUNOTA via UNIÃO de 2 fontes:
    #   (1) TGFVAR (vínculo nativo Sankhya)
    #   (2) AD_VINCULO_PEDIDO_NOTA (vínculo manual IAgro — Op 1 ou pedido retro Op 2)
    # VINCULO_ORIGEM expõe qual fonte resolveu: 'TGFVAR' | 'MANUAL' | NULL.
    # Frontend usa pra distinguir badge `FATURADO Nota Y` vs `FATURADO Nota Y · MANUAL`.
    SUBQ_NOTAS_DO_PEDIDO = (
        "SELECT v.NUNOTA FROM TGFVAR v WHERE v.NUNOTAORIG = c.NUNOTA"
        "  UNION ALL"
        "  SELECT av.NUNOTA_NOTA FROM AD_VINCULO_PEDIDO_NOTA av WHERE av.NUNOTA_PEDIDO = c.NUNOTA"
    )
    sql = f"""
        SELECT
            cp.NUNOTA, cp.NUMNOTA, cp.CODEMP, cp.CODPARC, cp.NOMEPARC, cp.DTNEG,
            cp.CODTIPOPER, cp.STATUSNOTA,
            cp.NOTA_NUMNOTA, cp.NOTA_NUNOTA, cp.VINCULO_ORIGEM, cp.TIPO_LINHA,
            cp.TEM_CANDIDATO_PEDIDO,
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
                    SELECT c.NUNOTA, c.NUMNOTA, c.CODEMP, c.CODPARC, c.DTNEG, p.NOMEPARC,
                           c.CODTIPOPER, c.STATUSNOTA,
                           (SELECT MAX(c2.NUMNOTA)
                              FROM TGFCAB c2
                             WHERE c2.NUNOTA IN ({SUBQ_NOTAS_DO_PEDIDO})
                               AND c2.CODTIPOPER IN (35, 37)
                               AND c2.STATUSNOTA <> 'E') AS NOTA_NUMNOTA,
                           (SELECT MAX(c2.NUNOTA)
                              FROM TGFCAB c2
                             WHERE c2.NUNOTA IN ({SUBQ_NOTAS_DO_PEDIDO})
                               AND c2.CODTIPOPER IN (35, 37)
                               AND c2.STATUSNOTA <> 'E') AS NOTA_NUNOTA,
                           CASE
                             WHEN EXISTS (
                                 SELECT 1 FROM TGFVAR v
                                   JOIN TGFCAB c2 ON c2.NUNOTA = v.NUNOTA
                                  WHERE v.NUNOTAORIG = c.NUNOTA
                                    AND c2.CODTIPOPER IN (35, 37)
                                    AND c2.STATUSNOTA <> 'E'
                             ) THEN 'TGFVAR'
                             WHEN EXISTS (
                                 SELECT 1 FROM AD_VINCULO_PEDIDO_NOTA av
                                  WHERE av.NUNOTA_PEDIDO = c.NUNOTA
                                    AND av.ORIGEM = 'PEDIDO_RETROATIVO'
                             ) THEN 'RETROATIVO'
                             WHEN EXISTS (
                                 SELECT 1 FROM AD_VINCULO_PEDIDO_NOTA av
                                  WHERE av.NUNOTA_PEDIDO = c.NUNOTA
                             ) THEN 'MANUAL'
                             ELSE NULL
                           END AS VINCULO_ORIGEM,
                           CASE
                             WHEN c.CODTIPOPER = 34 THEN 'PEDIDO'
                             ELSE 'NOTA_ORFA'
                           END AS TIPO_LINHA,
                           -- Pra NOTA_ORFA: sinaliza se há pedido pareável (mesma
                           -- heurística do consultar_candidatos_pedido_para_nota).
                           -- Frontend usa pra decidir qual ação oferecer:
                           --   1 → "Vincular a pedido…"      (Leva A)
                           --   0 → "Criar pedido retroativo" (Leva B)
                           -- Em PEDIDOs sempre 0 (sem efeito visual).
                           -- Heurística rigorosa (Mai/2026, refinada): pedido
                           -- só é candidato a vincular se for "obviamente" o par.
                           -- Critérios firmes: mesmo CODPARC + CODEMP + valor exato
                           -- (tolerância R$ 0,01) + data dentro de [nota-1, nota+1].
                           -- Janela de data antes era frouxa (+7d) — clientes
                           -- recorrentes têm pedidos em quase todo dia, coincidência
                           -- de data sem valor exato não prova nada.
                           CASE WHEN c.CODTIPOPER IN (35, 37) AND EXISTS (
                                  SELECT 1 FROM TGFCAB pc
                                   WHERE pc.CODTIPOPER = 34
                                     AND pc.STATUSNOTA = 'L'
                                     AND pc.CODEMP     = c.CODEMP
                                     AND pc.CODPARC    = c.CODPARC
                                     AND pc.DTNEG BETWEEN c.DTNEG - 1 AND c.DTNEG + 1
                                     AND ABS(NVL(pc.VLRNOTA, 0) - NVL(c.VLRNOTA, 0)) <= 0.01
                                     AND NOT EXISTS (
                                       SELECT 1 FROM TGFVAR v
                                         JOIN TGFCAB c3 ON c3.NUNOTA = v.NUNOTA
                                        WHERE v.NUNOTAORIG = pc.NUNOTA
                                          AND c3.CODTIPOPER IN (35, 37)
                                          AND c3.STATUSNOTA <> 'E'
                                     )
                                     AND NOT EXISTS (
                                       SELECT 1 FROM AD_VINCULO_PEDIDO_NOTA av
                                        WHERE av.NUNOTA_PEDIDO = pc.NUNOTA
                                     )
                                ) THEN 1 ELSE 0 END AS TEM_CANDIDATO_PEDIDO
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
        'nunota', 'numnota', 'codemp', 'codparc', 'nomeparc', 'dtneg',
        'codtipoper', 'statusnota',
        'nota_numnota', 'nota_nunota', 'vinculo_origem', 'tipo_linha',
        'tem_candidato_pedido',
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
    """Desvincula um lote de um item de pedido TOP 34 (em aberto OU faturado).

    Mai/2026: aceita TOP 34 STATUSNOTA='L'. Rastreabilidade vive no pedido,
    mesmo após faturamento — ver docstring de atribuir_lote_item_pedido.

    Comportamento:
        - Se EXISTE outra linha pendente (CODAGREGACAO IS NULL) do mesmo
          (NUNOTA, CODPROD): faz MERGE — soma o QTDNEG desta linha na linha
          pendente mais antiga + recalcula VLRTOT, depois DELETE desta.
          Evita acumular linhas órfãs após ciclos vincular/desvincular.
        - Se NÃO existe outra linha pendente do produto: apenas limpa
          CODAGREGACAO (esta era a única do produto, fica pendente).

    Validações:
        - Item precisa existir e ter CODAGREGACAO atualmente preenchido.
        - Pedido precisa ser TOP 34 e STATUSNOTA != 'E' (excluído).
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

            # Mai/2026: mesma regra de atribuir — TOP 34 (qualquer status) ou
            # TOP 35/37 STATUSNOTA='L' órfã (sem TGFVAR par).
            if statusnota == 'E':
                return {'ok': False, 'error': 'Pedido excluído'}
            top = int(codtipoper)
            if top not in (34, 35, 37):
                return {'ok': False, 'error': f'Operação não suportada (TOP {top})'}
            if top in (35, 37):
                if statusnota != 'L':
                    return {'ok': False, 'error':
                            f'Nota TOP {top} precisa estar liberada (STATUSNOTA=L)'}
                cur.execute(
                    "SELECT COUNT(*) FROM TGFVAR WHERE NUNOTA = :n",
                    n=int(nunota),
                )
                if (cur.fetchone() or [0])[0] > 0:
                    return {'ok': False, 'error':
                            f'Nota TOP {top} tem pedido pareado via TGFVAR. '
                            f'Trabalhe pelo pedido — não desvincule lote direto na nota.'}
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
                # Não há outra linha pendente — só limpa o lote desta.
                # QTDFIXADA também é zerada (Mai/2026): sem lote, não há mais
                # caixa de origem pra peso da etiqueta. Mantém coerência com
                # atribuir_lote_item_pedido que popula os dois juntos.
                cur.execute("""
                    UPDATE TGFITE
                       SET CODAGREGACAO = NULL,
                           QTDFIXADA    = NULL
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
                              qtd: float | None = None,
                              qtdfixada: float | None = None) -> dict:
    """Atribui um lote a um item de pedido TOP 34 (em aberto OU já faturado).

    Mai/2026: aceita TOP 34 STATUSNOTA='L' (pedido já faturado pelo Sankhya).
    A rastreabilidade do IAgro vive no pedido (TGFITE TOP 34) mesmo após
    faturamento — a nota TOP 35/37 não é tocada e fica como referência fiscal.
    Validado: NFe XML pra hortifrúti (NCM 0706) não exige grupo <rastro>, então
    CODAGREGACAO no TGFITE é dado interno e não afeta documento fiscal.

    Comportamento:
        - Se ``qtd`` é None ou igual à QTDNEG do item: UPDATE simples no CODAGREGACAO
          da linha existente.
        - Se ``qtd`` < QTDNEG do item: divide a linha — UPDATE reduzindo a qtd da
          original e INSERT de uma nova linha com a qtd atribuída e o novo lote.

    Validações:
        - Pedido tem que ser TOP 34 e STATUSNOTA != 'E' (excluído).
        - Lote precisa ter saldo suficiente em ANDRE_IAGRO_SALDO_LOTE (VENDAVEL='S').

    UPDATE direto (não usa atualizar_item_nota_banco) para evitar a auto-cura
    de AD_NUMPEDIDOORIG, que é específica da Entrada/Classificação e poderia
    bagunçar a origem do pedido de venda.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1) Lock pessimista da linha do item — evita race condition com
            #    outra atribuição/desvinculação concorrente do mesmo NUNOTA+SEQ.
            #    SELECT ... FOR UPDATE bloqueia a linha até commit/rollback.
            cur.execute("""
                SELECT i.CODAGREGACAO, NVL(i.QTDNEG, 0), i.CODPROD
                FROM TGFITE i
                WHERE i.NUNOTA = :n AND i.SEQUENCIA = :s
                FOR UPDATE
            """, n=int(nunota), s=int(sequencia))
            row_lock = cur.fetchone()
            if not row_lock:
                return {'ok': False, 'error': f'Item NUNOTA={nunota} SEQ={sequencia} não encontrado'}

            # 2) Valida pedido (TOP/STATUSNOTA) — leitura simples, sem lock no cabeçalho
            cur.execute("""
                SELECT c.CODTIPOPER, c.STATUSNOTA
                FROM TGFCAB c
                WHERE c.NUNOTA = :n
            """, n=int(nunota))
            row = cur.fetchone()

            if not row:
                return {'ok': False, 'error': f'Pedido NUNOTA={nunota} não encontrado'}

            codtipoper, statusnota = row
            codagregacao_atual_lock, qtd_item, codprod = row_lock

            # Mai/2026: aceita TOP 34 (qualquer status exceto 'E') ou
            # TOP 35/37 STATUSNOTA='L' órfã (sem TGFVAR par — nota emitida
            # direto no Sankhya sem fluxo de pedido). TOP 35/37 com TGFVAR par
            # é bloqueado: operador deve trabalhar pelo pedido pareado.
            if statusnota == 'E':
                return {'ok': False, 'error': 'Pedido excluído'}
            top = int(codtipoper)
            if top not in (34, 35, 37):
                return {'ok': False, 'error': f'Operação não suportada (TOP {top})'}
            if top in (35, 37):
                if statusnota != 'L':
                    return {'ok': False, 'error':
                            f'Nota TOP {top} precisa estar liberada (STATUSNOTA=L)'}
                cur.execute(
                    "SELECT COUNT(*) FROM TGFVAR WHERE NUNOTA = :n",
                    n=int(nunota),
                )
                if (cur.fetchone() or [0])[0] > 0:
                    return {'ok': False, 'error':
                            f'Nota TOP {top} tem pedido pareado via TGFVAR. '
                            f'Trabalhe pelo pedido — não atribua lote direto na nota.'}

            # Defesa contra double-binding: se o item já tem lote, recusa atribuir
            # de novo (operador deve desvincular antes). Sem isso, dois operadores
            # concorrentes poderiam tentar atribuir lotes diferentes na mesma linha.
            if codagregacao_atual_lock and str(codagregacao_atual_lock) != str(codagregacao):
                return {'ok': False, 'error':
                        f'Item já tem lote {codagregacao_atual_lock} vinculado. '
                        f'Desvincule antes de atribuir outro lote.'}

            qtd_item_f = float(qtd_item)
            qtd_atribuir = float(qtd) if qtd is not None else qtd_item_f

            if qtd_atribuir <= 0:
                return {'ok': False, 'error': 'Qtd a atribuir deve ser > 0'}
            if qtd_atribuir > qtd_item_f + 1e-6:
                return {'ok': False, 'error':
                        f'Qtd a atribuir ({qtd_atribuir}) maior que qtd do item ({qtd_item_f})'}

            # 3) Valida saldo do lote na view (ignora CODEMP — permite vincular
            #    lote de uma empresa em pedido de outra; soma o saldo do lote
            #    em todas as empresas onde ele aparece como vendável).
            #    A view já desconta as TOP 34 abertas, então o saldo aqui já
            #    reflete reservas concorrentes que tenham commitado antes do nosso lock.
            cur.execute("""
                SELECT NVL(SUM(QTD_DISPONIVEL), 0)
                FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
                WHERE CODPROD = :p AND CODAGREGACAO = :l
                  AND VENDAVEL = 'S'
            """, p=int(codprod), l=str(codagregacao))
            res_saldo = cur.fetchone()
            qtd_disp = float(res_saldo[0]) if res_saldo else 0.0

            if qtd_disp + 1e-6 < qtd_atribuir:
                # Mensagem operacional: formato BR + sugestão de ação. O
                # operador raramente sabe qual atribuição pegou o saldo, mas
                # saber o caminho ("desvincular ou reduzir qtd") destrava.
                _fmt_br = lambda v: f'{v:,.2f}'.replace(',', '#').replace('.', ',').replace('#', '.')
                return {'ok': False, 'error':
                        f'Saldo insuficiente no lote {codagregacao}. '
                        f'Disponível: {_fmt_br(qtd_disp)} · Solicitado: {_fmt_br(qtd_atribuir)}. '
                        f'Reduza a quantidade ou desvincule alguma atribuição '
                        f'existente deste lote (clique no olho do card de lote pra ver quem usa).'}

            # 3) Normaliza qtdfixada vindo do frontend (Mai/2026):
            #    operador digita o peso da caixa no modal de atribuição.
            #    Valores inválidos (None / 0 / negativo / não-numérico) viram
            #    None e o UPDATE/INSERT grava NULL. Etiqueta detecta depois.
            qtdfixada_final = None
            if qtdfixada is not None:
                try:
                    qf_val = float(qtdfixada)
                    if qf_val > 0:
                        qtdfixada_final = qf_val
                except (ValueError, TypeError):
                    pass

            # 4) Aplica a atribuição
            if abs(qtd_atribuir - qtd_item_f) < 1e-6:
                # 4a) Atribuição total — UPDATE simples (CODAGREGACAO + QTDFIXADA)
                cur.execute("""
                    UPDATE TGFITE
                       SET CODAGREGACAO = :l,
                           QTDFIXADA    = :qf
                     WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, l=str(codagregacao), qf=qtdfixada_final,
                     n=int(nunota), s=int(sequencia))
                operacao = 'UPDATE'
                nova_seq = None
            else:
                # 4b) Atribuição parcial — divide a linha
                cur.execute(
                    "SELECT NVL(MAX(SEQUENCIA), 0) + 1 FROM TGFITE WHERE NUNOTA = :n",
                    n=int(nunota),
                )
                nova_seq = int(cur.fetchone()[0])

                # Reduz qtd da linha original e recalcula seu VLRTOT.
                # QTDFIXADA da linha original NÃO é tocada — ela continua
                # representando a "linha sem lote" do pedido.
                cur.execute("""
                    UPDATE TGFITE
                       SET QTDNEG = QTDNEG - :q,
                           VLRTOT = NVL(VLRUNIT, 0) * (NVL(QTDNEG, 0) - :q)
                     WHERE NUNOTA = :n AND SEQUENCIA = :s
                """, q=qtd_atribuir, n=int(nunota), s=int(sequencia))

                # Cria nova linha com o lote atribuído (espelha campos da
                # original) e popula QTDFIXADA com o valor digitado pelo
                # operador (ou NULL se não foi informado).
                cur.execute("""
                    INSERT INTO TGFITE (
                        NUNOTA, SEQUENCIA, CODEMP, CODPROD, QTDNEG,
                        VLRUNIT, VLRTOT, CODVOL, CODLOCALORIG, CODAGREGACAO,
                        QTDFIXADA, AD_NUMPEDIDOORIG
                    )
                    SELECT :n_dest, :s_dest, CODEMP, CODPROD, :q,
                           VLRUNIT, NVL(VLRUNIT, 0) * :q, CODVOL, CODLOCALORIG, :l,
                           :qf, AD_NUMPEDIDOORIG
                      FROM TGFITE
                     WHERE NUNOTA = :n_orig AND SEQUENCIA = :s_orig
                """, n_dest=int(nunota), s_dest=nova_seq, q=qtd_atribuir,
                     l=str(codagregacao), qf=qtdfixada_final,
                     n_orig=int(nunota), s_orig=int(sequencia))
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


# ==============================================================================
# 🔗 VÍNCULO MANUAL PEDIDO ↔ NOTA (AD_VINCULO_PEDIDO_NOTA)
# Leva A (Mai/2026): operador vincula manualmente uma nota órfã a um pedido
# pré-existente. Usado quando Sankhya não populou TGFVAR no faturamento.
# DDL versionada em sankhya_integration/sql/AD_VINCULO_PEDIDO_NOTA.sql
# ==============================================================================

def consultar_candidatos_pedido_para_nota(nunota_nota: int, limite: int = 10) -> list[dict]:
    """Sugere pedidos TOP 34 STATUSNOTA='L' órfãos (sem TGFVAR par e sem
    vínculo manual) que poderiam parear com a nota informada.

    Heurística de ranking:
      - Mesmo CODPARC e CODEMP (filtro firme)
      - DTNEG dentro de janela de [nota - 1, nota + 7]
      - Ordena por diferença de valor ascendente (menor delta primeiro)

    Devolve lista de dicts com NUNOTA, NUMNOTA, DTNEG (formatada),
    VLRNOTA, DIFF_VALOR.
    """
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT CODEMP, CODPARC, DTNEG, NVL(VLRNOTA, 0)
              FROM TGFCAB WHERE NUNOTA = :n
        """, n=int(nunota_nota))
        row = cur.fetchone()
        if not row:
            return []
        codemp, codparc, dtneg, vlrnota = row

        # Heurística rigorosa (Mai/2026 refinada): mesmo CODPARC + CODEMP,
        # valor EXATO (∆ ≤ R$ 0,01), data dentro de ±1 dia. Critério rigoroso
        # foi necessário porque clientes recorrentes têm pedidos quase todo
        # dia — coincidência de data não basta como evidência.
        cur.execute("""
            SELECT * FROM (
                SELECT c.NUNOTA, c.NUMNOTA,
                       TO_CHAR(c.DTNEG, 'DD/MM/YYYY') AS DT,
                       NVL(c.VLRNOTA, 0) AS VLR,
                       ABS(NVL(c.VLRNOTA, 0) - :v) AS DIFF_VLR,
                       (SELECT COUNT(*) FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA) AS QTD_ITENS,
                       (SELECT NVL(SUM(i.QTDNEG), 0) FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA) AS QTD_TOTAL,
                       (SELECT pr.DESCRPROD
                          FROM TGFITE i JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
                         WHERE i.NUNOTA = c.NUNOTA AND ROWNUM = 1) AS PRIMEIRO_PRODUTO
                  FROM TGFCAB c
                 WHERE c.CODTIPOPER = 34
                   AND c.STATUSNOTA = 'L'
                   AND c.CODEMP = :emp
                   AND c.CODPARC = :parc
                   AND c.DTNEG BETWEEN :dt - 1 AND :dt + 1
                   AND ABS(NVL(c.VLRNOTA, 0) - :v) <= 0.01
                   AND NOT EXISTS (
                     SELECT 1 FROM TGFVAR v JOIN TGFCAB c2 ON c2.NUNOTA = v.NUNOTA
                      WHERE v.NUNOTAORIG = c.NUNOTA
                        AND c2.CODTIPOPER IN (35, 37)
                        AND c2.STATUSNOTA <> 'E'
                   )
                   AND NOT EXISTS (
                     SELECT 1 FROM AD_VINCULO_PEDIDO_NOTA av
                      WHERE av.NUNOTA_PEDIDO = c.NUNOTA
                   )
                 ORDER BY DIFF_VLR ASC, c.NUNOTA DESC
            ) WHERE ROWNUM <= :lim
        """, v=float(vlrnota), emp=int(codemp), parc=int(codparc), dt=dtneg, lim=int(limite))
        return [
            {
                'nunota':           int(r[0]),
                'numnota':          int(r[1]) if r[1] is not None else None,
                'dtneg':            r[2],
                'vlrnota':          float(r[3]),
                'diff_valor':       float(r[4]),
                'qtd_itens':        int(r[5] or 0),
                'qtd_total':        float(r[6] or 0),
                'primeiro_produto': r[7] or '',
            }
            for r in cur.fetchall()
        ]


def inserir_vinculo_manual_pedido_nota(nunota_pedido: int, nunota_nota: int,
                                       codusu: int, nomeusu: str = '',
                                       observacao: str = '') -> dict:
    """Cria vínculo manual entre pedido (TOP 34) e nota (TOP 35/37).

    Validações:
      - Pedido existe, é TOP 34, STATUSNOTA != 'E', sem TGFVAR par, sem vínculo manual
      - Nota existe, é TOP 35/37, STATUSNOTA != 'E', sem TGFVAR par (qualquer sentido),
        sem vínculo manual

    Retorna {ok, id, error?}.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # Valida pedido
            cur.execute("""
                SELECT CODTIPOPER, STATUSNOTA FROM TGFCAB WHERE NUNOTA = :n
            """, n=int(nunota_pedido))
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Pedido NUNOTA={nunota_pedido} não encontrado'}
            top_ped, status_ped = row
            if int(top_ped) != 34:
                return {'ok': False, 'error': f'NUNOTA={nunota_pedido} não é pedido TOP 34 (é TOP {top_ped})'}
            if status_ped == 'E':
                return {'ok': False, 'error': f'Pedido NUNOTA={nunota_pedido} está excluído'}

            cur.execute("""
                SELECT COUNT(*) FROM TGFVAR v
                  JOIN TGFCAB c2 ON c2.NUNOTA = v.NUNOTA
                 WHERE v.NUNOTAORIG = :n
                   AND c2.CODTIPOPER IN (35, 37)
                   AND c2.STATUSNOTA <> 'E'
            """, n=int(nunota_pedido))
            if (cur.fetchone() or [0])[0] > 0:
                return {'ok': False, 'error':
                        f'Pedido NUNOTA={nunota_pedido} já tem nota pareada via TGFVAR'}

            cur.execute("SELECT COUNT(*) FROM AD_VINCULO_PEDIDO_NOTA WHERE NUNOTA_PEDIDO = :n",
                        n=int(nunota_pedido))
            if (cur.fetchone() or [0])[0] > 0:
                return {'ok': False, 'error':
                        f'Pedido NUNOTA={nunota_pedido} já tem vínculo manual'}

            # Valida nota
            cur.execute("""
                SELECT CODTIPOPER, STATUSNOTA FROM TGFCAB WHERE NUNOTA = :n
            """, n=int(nunota_nota))
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Nota NUNOTA={nunota_nota} não encontrada'}
            top_nota, status_nota = row
            if int(top_nota) not in (35, 37):
                return {'ok': False, 'error':
                        f'NUNOTA={nunota_nota} não é nota TOP 35/37 (é TOP {top_nota})'}
            if status_nota == 'E':
                return {'ok': False, 'error': f'Nota NUNOTA={nunota_nota} está excluída'}

            cur.execute("SELECT COUNT(*) FROM TGFVAR WHERE NUNOTA = :n OR NUNOTAORIG = :n",
                        n=int(nunota_nota))
            if (cur.fetchone() or [0])[0] > 0:
                return {'ok': False, 'error':
                        f'Nota NUNOTA={nunota_nota} já tem vínculo via TGFVAR'}

            cur.execute("SELECT COUNT(*) FROM AD_VINCULO_PEDIDO_NOTA WHERE NUNOTA_NOTA = :n",
                        n=int(nunota_nota))
            if (cur.fetchone() or [0])[0] > 0:
                return {'ok': False, 'error':
                        f'Nota NUNOTA={nunota_nota} já tem vínculo manual'}

            # INSERT
            cur.execute("SELECT SEQ_AD_VINCULO_PEDIDO_NOTA.NEXTVAL FROM DUAL")
            novo_id = int(cur.fetchone()[0])
            cur.execute("""
                INSERT INTO AD_VINCULO_PEDIDO_NOTA
                    (ID, NUNOTA_PEDIDO, NUNOTA_NOTA, ORIGEM, CODUSU, NOMEUSU, OBSERVACAO)
                VALUES (:id, :p, :n, 'VINCULADO', :u, :nu, :obs)
            """, id=novo_id, p=int(nunota_pedido), n=int(nunota_nota),
                 u=int(codusu), nu=(nomeusu or '')[:80], obs=(observacao or '')[:500])

            # Popula AD_NUMPEDIDOORIG na nota (convenção Agromil: venda gerada
            # de pedido aponta pro NUNOTA do pedido). Aplica em TGFCAB e em
            # todos os TGFITE da nota pra ficar consistente — Sankhya nativo
            # passa a enxergar o vínculo via campo customizado.
            cur.execute(
                "UPDATE TGFCAB SET AD_NUMPEDIDOORIG = :p WHERE NUNOTA = :n",
                p=int(nunota_pedido), n=int(nunota_nota),
            )
            cur.execute(
                "UPDATE TGFITE SET AD_NUMPEDIDOORIG = :p WHERE NUNOTA = :n",
                p=int(nunota_pedido), n=int(nunota_nota),
            )

            conn.commit()
            return {'ok': True, 'id': novo_id}
    except Exception as e:
        logger.exception("Erro em inserir_vinculo_manual_pedido_nota")
        return {'ok': False, 'error': str(e)}


def resolver_nota_orfa_automatica(nunota_nota: int, codusu: int,
                                  nomeusu: str = '',
                                  acao: str | None = None) -> dict:
    """Resolve nota órfã (Mai/2026 — fluxo unificado Leva A+B):

    Decide automaticamente entre vincular a pedido existente ou criar pedido
    retroativo, conforme presença de candidato pareável pela heurística rigorosa:
      - Mesmo CODPARC + CODEMP
      - Valor exato (∆ ≤ R$ 0,01)
      - DTNEG dentro de [nota - 1, nota + 1]
      - Sem TGFVAR par, sem vínculo manual

    Parâmetros:
        nunota_nota   — nota órfã alvo
        codusu/nomeusu — usuário operador (audit)
        acao          — opcional, força ação: 'VINCULAR' | 'CRIAR'. Se omitido
                        ('AUTO'), backend decide pela heurística.

    Retorno:
        {ok: True, acao: 'VINCULADO'|'CRIADO_RETROATIVO', nunota_pedido, ...}
        {ok: False, error}
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    # 1) Lê dados da nota e tenta achar candidato exato
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT CODTIPOPER, STATUSNOTA, CODEMP, CODPARC, DTNEG,
                       NVL(VLRNOTA, 0)
                  FROM TGFCAB WHERE NUNOTA = :n
            """, n=int(nunota_nota))
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Nota NUNOTA={nunota_nota} não encontrada'}
            top, status, codemp, codparc, dtneg, vlrnota = row
            if int(top) not in (35, 37):
                return {'ok': False, 'error':
                        f'NUNOTA={nunota_nota} não é nota TOP 35/37 (é TOP {top})'}
            if status == 'E':
                return {'ok': False, 'error': f'Nota NUNOTA={nunota_nota} excluída'}

            # 2) Busca pedido pareável exato. Pega o mais recente (data DESC,
            # NUNOTA DESC pra desempate).
            cur.execute("""
                SELECT * FROM (
                  SELECT NUNOTA FROM TGFCAB pc
                   WHERE pc.CODTIPOPER = 34
                     AND pc.STATUSNOTA = 'L'
                     AND pc.CODEMP = :emp
                     AND pc.CODPARC = :parc
                     AND pc.DTNEG BETWEEN :dt - 1 AND :dt + 1
                     AND ABS(NVL(pc.VLRNOTA, 0) - :v) <= 0.01
                     AND NOT EXISTS (
                       SELECT 1 FROM TGFVAR v JOIN TGFCAB c2 ON c2.NUNOTA = v.NUNOTA
                        WHERE v.NUNOTAORIG = pc.NUNOTA
                          AND c2.CODTIPOPER IN (35, 37)
                          AND c2.STATUSNOTA <> 'E'
                     )
                     AND NOT EXISTS (
                       SELECT 1 FROM AD_VINCULO_PEDIDO_NOTA av
                        WHERE av.NUNOTA_PEDIDO = pc.NUNOTA
                     )
                   ORDER BY pc.DTNEG DESC, pc.NUNOTA DESC
                ) WHERE ROWNUM = 1
            """, emp=int(codemp), parc=int(codparc), dt=dtneg, v=float(vlrnota))
            cand = cur.fetchone()
            nunota_candidato = int(cand[0]) if cand else None
    except Exception as e:
        logger.exception("Erro em resolver_nota_orfa_automatica (busca candidato)")
        return {'ok': False, 'error': str(e)}

    # 3) Decide ação. Operador pode forçar via parâmetro `acao`.
    acao = (acao or 'AUTO').upper()
    if acao == 'AUTO':
        acao_efetiva = 'VINCULAR' if nunota_candidato else 'CRIAR'
    else:
        acao_efetiva = acao

    if acao_efetiva == 'VINCULAR':
        if not nunota_candidato:
            return {'ok': False, 'error':
                    'Sem candidato exato pareável — use ação CRIAR pra gerar pedido retroativo'}
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=nunota_candidato, nunota_nota=int(nunota_nota),
            codusu=int(codusu), nomeusu=nomeusu,
        )
        if not res.get('ok'):
            return res
        return {
            'ok':            True,
            'acao':          'VINCULADO',
            'nunota_pedido': nunota_candidato,
            'vinculo_id':    res.get('id'),
        }

    if acao_efetiva == 'CRIAR':
        res = criar_pedido_retroativo_a_partir_de_nota(
            nunota_nota=int(nunota_nota), codusu=int(codusu), nomeusu=nomeusu,
        )
        if not res.get('ok'):
            return res
        return {
            'ok':            True,
            'acao':          'CRIADO_RETROATIVO',
            'nunota_pedido': res.get('nunota_pedido'),
            'vinculo_id':    res.get('vinculo_id'),
            'qtd_itens':     res.get('qtd_itens'),
        }

    return {'ok': False, 'error': f'Ação inválida: {acao}'}


def criar_pedido_retroativo_a_partir_de_nota(nunota_nota: int, codusu: int,
                                             nomeusu: str = '') -> dict:
    """Leva B (Mai/2026) — cria pedido TOP 34 espelhando os itens da nota
    órfã informada, e grava o vínculo em AD_VINCULO_PEDIDO_NOTA com
    ORIGEM='PEDIDO_RETROATIVO'.

    Caso de uso: nota foi venda direta sem pedido (TOP 35/37 STATUSNOTA='L'
    sem TGFVAR par e sem pedido pareável no banco). Operador clica "Criar
    pedido retroativo" e o IAgro cria a estrutura pra rastreabilidade
    funcionar normalmente daí pra frente.

    Validações:
        - Nota existe e é TOP 35/37 STATUSNOTA != 'E'
        - Nota não tem TGFVAR (nenhum sentido)
        - Nota não tem vínculo manual já criado
        - Nota tem pelo menos 1 item em TGFITE

    O cabeçalho novo recebe:
        - CODEMP, CODPARC, CODTIPVENDA, DTNEG: copiados da nota
        - CODTIPOPER = 34
        - CODNAT     = CODNAT_POR_TOP[34]  (10010100)
        - STATUSNOTA: default Sankhya (vazio = pendente)

    Cada item replica CODPROD, QTDNEG, VLRUNIT, CODVOL, CODLOCALORIG da nota.
    CODAGREGACAO fica NULL — operador vincula lote depois.

    Atomicidade: tudo num único commit. Falha em qualquer passo → rollback total.
    Retorno: {ok, nunota_pedido, vinculo_id, qtd_itens}
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1) Valida nota e lê cabeçalho
            cur.execute("""
                SELECT CODTIPOPER, STATUSNOTA, CODEMP, CODPARC, DTNEG,
                       CODTIPVENDA
                  FROM TGFCAB WHERE NUNOTA = :n
            """, n=int(nunota_nota))
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Nota NUNOTA={nunota_nota} não encontrada'}
            top, status, codemp, codparc, dtneg, codtipvenda = row
            if int(top) not in (35, 37):
                return {'ok': False, 'error':
                        f'NUNOTA={nunota_nota} não é nota TOP 35/37 (é TOP {top})'}
            if status == 'E':
                return {'ok': False, 'error': f'Nota NUNOTA={nunota_nota} está excluída'}

            # 2) Garante que nota é órfã (sem TGFVAR e sem vínculo manual)
            cur.execute("SELECT COUNT(*) FROM TGFVAR WHERE NUNOTA = :n OR NUNOTAORIG = :n",
                        n=int(nunota_nota))
            if (cur.fetchone() or [0])[0] > 0:
                return {'ok': False, 'error':
                        f'Nota NUNOTA={nunota_nota} já tem vínculo via TGFVAR'}
            cur.execute("SELECT COUNT(*) FROM AD_VINCULO_PEDIDO_NOTA WHERE NUNOTA_NOTA = :n",
                        n=int(nunota_nota))
            if (cur.fetchone() or [0])[0] > 0:
                return {'ok': False, 'error':
                        f'Nota NUNOTA={nunota_nota} já tem vínculo manual'}

            # 3) Lê itens da nota
            cur.execute("""
                SELECT SEQUENCIA, CODPROD, NVL(QTDNEG, 0), NVL(VLRUNIT, 0),
                       NVL(CODVOL, 'UN'), NVL(CODLOCALORIG, 101)
                  FROM TGFITE WHERE NUNOTA = :n
                 ORDER BY SEQUENCIA
            """, n=int(nunota_nota))
            itens_nota = cur.fetchall()
            if not itens_nota:
                return {'ok': False, 'error':
                        f'Nota NUNOTA={nunota_nota} não tem itens em TGFITE'}

            # 4) Cria cabeçalho TOP 34 (passa conexão pra ficar tudo no mesmo commit)
            dtneg_str = dtneg.strftime('%d/%m/%Y') if hasattr(dtneg, 'strftime') else str(dtneg)
            dados_cab = {
                'CODEMP':     int(codemp),
                'CODPARC':    int(codparc),
                'CODTIPOPER': 34,
                'CODNAT':     CODNAT_POR_TOP[34],
                'DTNEG':      dtneg_str,
            }
            if codtipvenda:
                dados_cab['CODTIPVENDA'] = int(codtipvenda)
            res_cab = inserir_cabecalho_nota_banco(dados_cab, conexao_existente=conn)
            if not res_cab.get('ok'):
                conn.rollback()
                return {'ok': False, 'error':
                        f'Falha ao criar cabeçalho do pedido: {res_cab.get("error")}'}
            nunota_pedido_novo = int(res_cab['nunota'])

            # 5) Cria itens (sem CODAGREGACAO — operador vincula lote depois)
            for _seq, codprod, qtdneg, vlrunit, codvol, codlocalorig in itens_nota:
                dados_item = {
                    'NUNOTA':       nunota_pedido_novo,
                    'CODPROD':      int(codprod),
                    'QTDNEG':       float(qtdneg),
                    'VLRUNIT':      float(vlrunit),
                    'CODVOL':       codvol,
                    'CODLOCALORIG': int(codlocalorig),
                }
                res_item = inserir_item_nota_banco(
                    dados_item, conexao_existente=conn,
                    codusu_logado=int(codusu) if codusu else None,
                    gerar_lote_auto=False,
                )
                if not res_item.get('ok'):
                    conn.rollback()
                    return {'ok': False, 'error':
                            f'Falha ao copiar item CODPROD={codprod}: {res_item.get("error")}'}

            # 6) Recalcula totais
            recalcular_totais_nota_banco(nunota_pedido_novo, conexao_existente=conn)

            # 7) Cria vínculo na AD_VINCULO_PEDIDO_NOTA
            cur.execute("SELECT SEQ_AD_VINCULO_PEDIDO_NOTA.NEXTVAL FROM DUAL")
            novo_id = int(cur.fetchone()[0])
            cur.execute("""
                INSERT INTO AD_VINCULO_PEDIDO_NOTA
                    (ID, NUNOTA_PEDIDO, NUNOTA_NOTA, ORIGEM, CODUSU, NOMEUSU, OBSERVACAO)
                VALUES (:id, :p, :n, 'PEDIDO_RETROATIVO', :u, :nu, :obs)
            """, id=novo_id, p=nunota_pedido_novo, n=int(nunota_nota),
                 u=int(codusu), nu=(nomeusu or '')[:80],
                 obs=f'Pedido retroativo criado pelo IAgro p/ rastreio da Nota {nunota_nota}'[:500])

            # 8) Popula AD_NUMPEDIDOORIG na nota (TGFCAB + todos os TGFITE) com
            # o NUNOTA do pedido recém-criado. Mesma convenção do fluxo padrão
            # Sankhya (venda aponta pro pedido origem). Pedido novo já recebe
            # AD_NUMPEDIDOORIG = próprio NUNOTA via default do inserir_cabecalho_nota_banco.
            cur.execute(
                "UPDATE TGFCAB SET AD_NUMPEDIDOORIG = :p WHERE NUNOTA = :n",
                p=nunota_pedido_novo, n=int(nunota_nota),
            )
            cur.execute(
                "UPDATE TGFITE SET AD_NUMPEDIDOORIG = :p WHERE NUNOTA = :n",
                p=nunota_pedido_novo, n=int(nunota_nota),
            )

            conn.commit()
            return {
                'ok': True,
                'nunota_pedido': nunota_pedido_novo,
                'vinculo_id':    novo_id,
                'qtd_itens':     len(itens_nota),
            }
    except Exception as e:
        logger.exception("Erro em criar_pedido_retroativo_a_partir_de_nota")
        return {'ok': False, 'error': str(e)}


def remover_vinculo_manual_pedido_nota(*, nunota_pedido: int | None = None,
                                       nunota_nota: int | None = None) -> dict:
    """Desfaz vínculo manual pelo NUNOTA do pedido OU da nota.

    Comportamento conforme `ORIGEM`:
        - 'VINCULADO' (Leva A) → só remove a linha em AD_VINCULO_PEDIDO_NOTA.
          Pedido e nota originais permanecem intactos.
        - 'PEDIDO_RETROATIVO' (Leva B) → remove a linha em AD_VINCULO_PEDIDO_NOTA
          E exclui o pedido (TGFITE + TGFCAB), porque o pedido foi criado
          artificialmente pelo IAgro só pra rastrear a nota.
          Bloqueia se algum item do pedido já tem CODAGREGACAO atribuído —
          operador deve desvincular todos os lotes primeiro.

    Pelo menos um dos dois NUNOTAs deve ser informado.
    Retorna {ok, removidos, origem, pedido_excluido}.
    """
    if not verificar_permissao_escrita():
        return {'ok': False, 'error': 'Escrita desabilitada'}
    if not nunota_pedido and not nunota_nota:
        return {'ok': False, 'error': 'Informe nunota_pedido ou nunota_nota'}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1) Localiza o vínculo (pra saber ORIGEM antes de DELETE)
            if nunota_pedido:
                cur.execute("""
                    SELECT ID, NUNOTA_PEDIDO, NUNOTA_NOTA, ORIGEM
                      FROM AD_VINCULO_PEDIDO_NOTA WHERE NUNOTA_PEDIDO = :n
                """, n=int(nunota_pedido))
            else:
                cur.execute("""
                    SELECT ID, NUNOTA_PEDIDO, NUNOTA_NOTA, ORIGEM
                      FROM AD_VINCULO_PEDIDO_NOTA WHERE NUNOTA_NOTA = :n
                """, n=int(nunota_nota))
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': 'Vínculo não encontrado'}
            id_v, nunota_ped, nunota_n_real, origem = row

            # 2) Se for pedido retroativo, valida que nenhum item tem lote
            pedido_excluido = False
            if origem == 'PEDIDO_RETROATIVO':
                cur.execute(
                    "SELECT COUNT(*) FROM TGFITE WHERE NUNOTA = :n AND CODAGREGACAO IS NOT NULL",
                    n=int(nunota_ped),
                )
                n_atrib = (cur.fetchone() or [0])[0]
                if n_atrib > 0:
                    return {'ok': False, 'error':
                            f'Pedido retroativo {nunota_ped} tem {n_atrib} item(ns) com lote atribuído. '
                            f'Desvincule todos os lotes antes de desfazer.'}
                # Exclui TGFITE + TGFCAB do pedido criado pelo IAgro
                cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n", n=int(nunota_ped))
                cur.execute("DELETE FROM TGFCAB WHERE NUNOTA = :n", n=int(nunota_ped))
                pedido_excluido = True

            # 3) Limpa AD_NUMPEDIDOORIG da nota (TGFCAB + todos os TGFITE).
            # Volta ao estado pré-vínculo: AD_NUMPEDIDOORIG = NULL na venda
            # (convenção: venda sem pedido conhecido fica NULL, igual ao
            # estado original Sankhya direto).
            cur.execute(
                "UPDATE TGFCAB SET AD_NUMPEDIDOORIG = NULL WHERE NUNOTA = :n",
                n=int(nunota_n_real),
            )
            cur.execute(
                "UPDATE TGFITE SET AD_NUMPEDIDOORIG = NULL WHERE NUNOTA = :n",
                n=int(nunota_n_real),
            )

            # 4) Remove a linha do vínculo
            cur.execute("DELETE FROM AD_VINCULO_PEDIDO_NOTA WHERE ID = :id", id=int(id_v))
            removidos = int(cur.rowcount or 0)
            conn.commit()
            return {
                'ok': True,
                'removidos':      removidos,
                'origem':         origem,
                'pedido_excluido': pedido_excluido,
            }
    except Exception as e:
        logger.exception("Erro em remover_vinculo_manual_pedido_nota")
        return {'ok': False, 'error': str(e)}


# ==============================================================================
# 📧 12. IMPORTAÇÃO DE PEDIDOS POR E-MAIL (AD_PEDIDO_EMAIL_*)
# Funções aditivas — não alteram queries existentes. Operam sobre as tabelas
# auxiliares AD_PEDIDO_EMAIL_RECEBIDO e AD_PEDIDO_EMAIL_ITEM.
# DDL versionada em sankhya_integration/sql/AD_PEDIDO_EMAIL.sql
# ==============================================================================

# Estados válidos da coluna STATUS (espelham o CHECK CONSTRAINT da DDL)
EMAIL_STATUS_VALIDOS = (
    'AGUARDANDO_PARSER',
    'PENDENTE_REVISAO',
    'CONFIRMADO',
    'DESCARTADO',
    'ERRO_PARSER',
    'ERRO_PDF',
)


def _proximo_id_sequence(cur, nome_sequence: str) -> int:
    """Retorna o próximo valor de uma SEQUENCE Oracle (compatível 11g+)."""
    cur.execute(f"SELECT {nome_sequence}.NEXTVAL FROM DUAL")
    return int(cur.fetchone()[0])


# Cache em memória (1× por processo Python) das colunas opcionais que podem
# ou não existir conforme migrations já aplicadas. Permite o código
# funcionar em servidores que ainda não rodaram a migration mais recente.
# Reseta no restart do Django — quando operador aplica migration e
# reinicia, passa a detectar a coluna automaticamente.
_SCHEMA_OPCIONAIS_CACHE: dict[str, bool] = {}


def _existe_coluna(cur, tabela: str, coluna: str) -> bool:
    """Verifica (com cache) se uma coluna existe no schema atual.

    Uso típico: features novas que dependem de migration ALTER TABLE
    podem checar antes de incluir a coluna no SELECT/INSERT, evitando
    ORA-00904 quando a migration ainda não foi aplicada em produção.
    """
    chave = f'{tabela.upper()}.{coluna.upper()}'
    if chave in _SCHEMA_OPCIONAIS_CACHE:
        return _SCHEMA_OPCIONAIS_CACHE[chave]
    try:
        cur.execute(
            "SELECT COUNT(*) FROM USER_TAB_COLUMNS "
            "WHERE TABLE_NAME = :t AND COLUMN_NAME = :c",
            {'t': tabela.upper(), 'c': coluna.upper()},
        )
        existe = (cur.fetchone()[0] or 0) > 0
    except Exception:
        existe = False
    _SCHEMA_OPCIONAIS_CACHE[chave] = existe
    return existe


def inserir_pedido_email_recebido(dados: dict, conexao_existente=None) -> dict:
    """Insere um registro de e-mail recebido em AD_PEDIDO_EMAIL_RECEBIDO.

    Campos esperados em `dados`:
      MESSAGE_ID (obrigatório), SUB_ID (default 1 — sequencial quando 1 PDF
      tem N pedidos), REMETENTE, ASSUNTO, RECEBIDO_EM (datetime),
      PROCESSADO_EM (datetime), PDF_PATH, PDF_TEXTO (CLOB), STATUS (default
      'AGUARDANDO_PARSER'), ORIGEM (default 'IMAP' — outras: 'TEXTO_LIVRE',
      'WHATSAPP_API').

    Retorna {'ok': True, 'id': <novo_id>} ou {'ok': False, 'error': msg}.
    Falha com UNIQUE em (MESSAGE_ID, SUB_ID) significa duplicado — caller
    deve ignorar.
    """
    def _operar(conn):
        cur = conn.cursor()
        novo_id = _proximo_id_sequence(cur, 'SEQ_AD_PEDIDO_EMAIL_RECEBIDO')
        status = dados.get('STATUS') or 'AGUARDANDO_PARSER'
        if status not in EMAIL_STATUS_VALIDOS:
            return {'ok': False, 'error': f"STATUS inválido: {status}"}
        origem = dados.get('ORIGEM') or 'IMAP'

        # ORIGEM é opcional até a migration AD_PEDIDO_EMAIL_MIGRATION_ORIGEM
        # ser aplicada no servidor — verificamos dinamicamente.
        # Se a coluna não existe, paste manual (TEXTO_LIVRE) ainda é
        # rejeitado abaixo pra evitar perder o discriminador silenciosamente.
        tem_origem = _existe_coluna(cur, 'AD_PEDIDO_EMAIL_RECEBIDO', 'ORIGEM')
        if not tem_origem and origem != 'IMAP':
            return {'ok': False,
                    'error': "Coluna ORIGEM ainda não existe no Oracle. "
                             "Aplique a migration AD_PEDIDO_EMAIL_MIGRATION_ORIGEM.sql "
                             "antes de usar a importação de texto livre."}

        if tem_origem:
            sql = """
                INSERT INTO AD_PEDIDO_EMAIL_RECEBIDO (
                    ID, MESSAGE_ID, SUB_ID, REMETENTE, ASSUNTO,
                    RECEBIDO_EM, PROCESSADO_EM,
                    PDF_PATH, PDF_TEXTO,
                    STATUS, ORIGEM
                ) VALUES (
                    :id, :message_id, :sub_id, :remetente, :assunto,
                    :recebido_em, :processado_em,
                    :pdf_path, :pdf_texto,
                    :status, :origem
                )
            """
        else:
            sql = """
                INSERT INTO AD_PEDIDO_EMAIL_RECEBIDO (
                    ID, MESSAGE_ID, SUB_ID, REMETENTE, ASSUNTO,
                    RECEBIDO_EM, PROCESSADO_EM,
                    PDF_PATH, PDF_TEXTO,
                    STATUS
                ) VALUES (
                    :id, :message_id, :sub_id, :remetente, :assunto,
                    :recebido_em, :processado_em,
                    :pdf_path, :pdf_texto,
                    :status
                )
            """

        binds = {
            'id': novo_id,
            'message_id': dados['MESSAGE_ID'],
            'sub_id': int(dados.get('SUB_ID') or 1),
            'remetente': dados.get('REMETENTE'),
            'assunto': dados.get('ASSUNTO'),
            'recebido_em': dados.get('RECEBIDO_EM'),
            'processado_em': dados.get('PROCESSADO_EM'),
            'pdf_path': dados.get('PDF_PATH'),
            'pdf_texto': dados.get('PDF_TEXTO'),
            'status': status,
        }
        if tem_origem:
            binds['origem'] = origem

        cur.execute(sql, binds)
        return {'ok': True, 'id': novo_id}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em inserir_pedido_email_recebido")
        return {'ok': False, 'error': str(exc)}


def inserir_pedido_email_item(dados: dict, conexao_existente=None) -> dict:
    """Insere um item extraído em AD_PEDIDO_EMAIL_ITEM.

    Campos esperados em `dados`:
      RECEBIDO_ID (obrigatório), SEQUENCIA, DESCRICAO_PDF,
      CODPROD_SUGERIDO, CODPROD_CONFIANCA, QTD, CODVOL, PRECO_UNIT, OBSERVACAO,
      COD_CLIENTE (opcional — código do produto na visão do cliente, ex: 8117
      em pedidos Consinco; só persiste se a coluna existir no schema).
    """
    def _operar(conn):
        cur = conn.cursor()
        novo_id = _proximo_id_sequence(cur, 'SEQ_AD_PEDIDO_EMAIL_ITEM')
        # COD_CLIENTE é opcional até a migration AD_CLIENTE_PRODUTO_COD ser
        # aplicada (que cria a coluna). Detecção dinâmica preserva backward-compat.
        tem_cod_cliente = _existe_coluna(cur, 'AD_PEDIDO_EMAIL_ITEM', 'COD_CLIENTE')

        if tem_cod_cliente:
            sql = """
                INSERT INTO AD_PEDIDO_EMAIL_ITEM (
                    ID, RECEBIDO_ID, SEQUENCIA, DESCRICAO_PDF,
                    CODPROD_SUGERIDO, CODPROD_CONFIANCA, CODPROD_FINAL,
                    QTD, CODVOL, PRECO_UNIT, OBSERVACAO, COD_CLIENTE
                ) VALUES (
                    :id, :recebido_id, :sequencia, :descricao_pdf,
                    :codprod_sugerido, :codprod_confianca, :codprod_final,
                    :qtd, :codvol, :preco_unit, :observacao, :cod_cliente
                )
            """
        else:
            sql = """
                INSERT INTO AD_PEDIDO_EMAIL_ITEM (
                    ID, RECEBIDO_ID, SEQUENCIA, DESCRICAO_PDF,
                    CODPROD_SUGERIDO, CODPROD_CONFIANCA, CODPROD_FINAL,
                    QTD, CODVOL, PRECO_UNIT, OBSERVACAO
                ) VALUES (
                    :id, :recebido_id, :sequencia, :descricao_pdf,
                    :codprod_sugerido, :codprod_confianca, :codprod_final,
                    :qtd, :codvol, :preco_unit, :observacao
                )
            """
        binds = {
            'id': novo_id,
            'recebido_id': dados['RECEBIDO_ID'],
            'sequencia': dados.get('SEQUENCIA', 1),
            'descricao_pdf': dados.get('DESCRICAO_PDF'),
            'codprod_sugerido': dados.get('CODPROD_SUGERIDO'),
            'codprod_confianca': dados.get('CODPROD_CONFIANCA'),
            'codprod_final': dados.get('CODPROD_FINAL'),
            'qtd': dados.get('QTD'),
            'codvol': dados.get('CODVOL'),
            'preco_unit': dados.get('PRECO_UNIT'),
            'observacao': dados.get('OBSERVACAO'),
        }
        if tem_cod_cliente:
            cod_cliente_raw = dados.get('COD_CLIENTE')
            binds['cod_cliente'] = (
                str(cod_cliente_raw).strip()[:50] if cod_cliente_raw not in (None, '') else None
            )

        cur.execute(sql, binds)
        return {'ok': True, 'id': novo_id}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em inserir_pedido_email_item")
        return {'ok': False, 'error': str(exc)}


def listar_pedidos_email_pendentes(filtros: dict | None = None,
                                    limite: int = 50, offset: int = 0) -> list[dict]:
    """Lista pré-pedidos por status (default PENDENTE_REVISAO) ordenados por RECEBIDO_EM DESC.

    Filtros aceitos: `status` (str ou list), `dias` (int — recebidos nos últimos N dias).
    Retorna lista de dicts com campos resumidos para a fila da tela.
    """
    filtros = filtros or {}
    where = ['1=1']
    binds: dict = {}

    status = filtros.get('status') or 'PENDENTE_REVISAO'
    if isinstance(status, (list, tuple)):
        placeholders = ','.join(f":st{i}" for i in range(len(status)))
        where.append(f"STATUS IN ({placeholders})")
        for i, s in enumerate(status):
            binds[f'st{i}'] = s
    else:
        where.append("STATUS = :status")
        binds['status'] = status

    dias = filtros.get('dias')
    if dias:
        where.append("RECEBIDO_EM >= SYSTIMESTAMP - NUMTODSINTERVAL(:dias, 'DAY')")
        binds['dias'] = int(dias)

    # Ordenação: e-mails mais recentes no topo (RECEBIDO_EM DESC); dentro do
    # mesmo e-mail (SUB_ID 1, 2, 3...), respeita a ordem das páginas do PDF
    # original — antes era ID DESC, que invertia (página 3 vinha antes da 1).
    binds['ini'] = offset + 1
    binds['fim'] = offset + limite

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            # ORIGEM só existe após migration AD_PEDIDO_EMAIL_MIGRATION_ORIGEM.
            # Antes da migration, retorna 'IMAP' literal pra preservar
            # contrato com o frontend.
            tem_origem = _existe_coluna(cur, 'AD_PEDIDO_EMAIL_RECEBIDO', 'ORIGEM')
            col_origem = 'ORIGEM' if tem_origem else "'IMAP' AS ORIGEM"
            sql = f"""
            SELECT * FROM (
                SELECT t.*, ROW_NUMBER() OVER (
                    ORDER BY RECEBIDO_EM DESC NULLS LAST, SUB_ID ASC NULLS LAST, ID ASC
                ) AS rn
                FROM (
                    SELECT
                        ID, MESSAGE_ID, SUB_ID, REMETENTE, ASSUNTO,
                        RECEBIDO_EM, PROCESSADO_EM,
                        LLM_CONFIANCA_GERAL, CODPARC_SUGERIDO,
                        STATUS, NUNOTA_GERADO, CRIADO_EM, {col_origem}
                    FROM AD_PEDIDO_EMAIL_RECEBIDO
                    WHERE {' AND '.join(where)}
                ) t
            ) WHERE rn BETWEEN :ini AND :fim
            """
            cur.execute(sql, binds)
            cols = [d[0].lower() for d in cur.description]
            linhas = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                d.pop('rn', None)
                linhas.append(d)
            return linhas
    except Exception:
        logger.exception("Erro em listar_pedidos_email_pendentes")
        return []


def obter_pedido_email_completo(recebido_id: int) -> dict | None:
    """Retorna o pré-pedido com cabeçalho + itens. None se não existir."""
    # LEFT JOIN com TGFPAR/TSIEMP/TGFTPV trazem nomes canônicos dos IDs
    # sugeridos para o operador conferir visualmente (NOSSO CLIENTE / NOSSA
    # EMPRESA / NOSSO TIPO DE NEGOCIAÇÃO).
    # ORIGEM só existe após a migration AD_PEDIDO_EMAIL_MIGRATION_ORIGEM —
    # tornamos opcional pra rodar antes/depois sem quebrar.
    # LEFT JOIN com TGFPRO traz a descrição canônica do nosso produto
    # (DESCRPROD) ao lado do CODPROD sugerido. Isso permite o operador
    # conferir visualmente: "PIMENTAO VERDE" do PDF está casando com o que
    # da nossa base? — ele vê "PIMENTAO VERDE EXTRA" e confirma.
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            tem_origem = _existe_coluna(cur, 'AD_PEDIDO_EMAIL_RECEBIDO', 'ORIGEM')
            col_origem = 'r.ORIGEM' if tem_origem else "'IMAP' AS ORIGEM"
            tem_cod_cliente = _existe_coluna(cur, 'AD_PEDIDO_EMAIL_ITEM', 'COD_CLIENTE')
            col_cod_cliente = 'i.COD_CLIENTE' if tem_cod_cliente else "NULL AS COD_CLIENTE"
            sql_itens = f"""
                SELECT i.ID, i.RECEBIDO_ID, i.SEQUENCIA, i.DESCRICAO_PDF,
                       i.CODPROD_SUGERIDO, i.CODPROD_CONFIANCA, i.CODPROD_FINAL,
                       i.QTD, i.CODVOL, i.PRECO_UNIT, i.OBSERVACAO, i.CRIADO_EM,
                       {col_cod_cliente},
                       p.DESCRPROD AS CODPROD_SUGERIDO_DESCR,
                       pf.DESCRPROD AS CODPROD_FINAL_DESCR
                FROM AD_PEDIDO_EMAIL_ITEM i
                LEFT JOIN TGFPRO p  ON p.CODPROD  = i.CODPROD_SUGERIDO
                LEFT JOIN TGFPRO pf ON pf.CODPROD = i.CODPROD_FINAL
                WHERE i.RECEBIDO_ID = :id
                ORDER BY i.SEQUENCIA
            """
            sql_cab = f"""
                SELECT r.ID, r.MESSAGE_ID, r.SUB_ID, r.REMETENTE, r.ASSUNTO,
                       r.RECEBIDO_EM, r.PROCESSADO_EM,
                       r.PDF_PATH, r.PDF_TEXTO,
                       r.LLM_RESPOSTA, r.LLM_MODELO,
                       r.LLM_TOKENS_IN, r.LLM_TOKENS_OUT, r.LLM_CONFIANCA_GERAL,
                       r.CODPARC_SUGERIDO, r.CODEMP_SUGERIDO,
                       r.DTNEG_SUGERIDA, r.CODTIPVENDA_SUGERIDO,
                       r.OBSERVACAO_EXTRAIDA,
                       r.STATUS, r.MOTIVO_DESCARTE,
                       r.NUNOTA_GERADO, r.CONFIRMADO_POR, r.CONFIRMADO_EM, r.CRIADO_EM,
                       {col_origem},
                       p.NOMEPARC      AS CODPARC_SUGERIDO_NOME,
                       e.NOMEFANTASIA  AS CODEMP_SUGERIDO_NOME,
                       t.DESCRTIPVENDA AS CODTIPVENDA_SUGERIDO_DESCR
                FROM AD_PEDIDO_EMAIL_RECEBIDO r
                LEFT JOIN TGFPAR p ON p.CODPARC      = r.CODPARC_SUGERIDO
                LEFT JOIN TSIEMP e ON e.CODEMP       = r.CODEMP_SUGERIDO
                LEFT JOIN TGFTPV t ON t.CODTIPVENDA  = r.CODTIPVENDA_SUGERIDO
                WHERE r.ID = :id
            """
            cur.execute(sql_cab, id=recebido_id)
            row = cur.fetchone()
            if not row: return None
            cols_cab = [d[0].lower() for d in cur.description]
            cab = dict(zip(cols_cab, row))
            # CLOBs vêm como objeto LOB — convertemos para string
            for k in ('pdf_texto', 'llm_resposta'):
                v = cab.get(k)
                if v is not None and hasattr(v, 'read'):
                    cab[k] = v.read()
            cur.execute(sql_itens, id=recebido_id)
            cols_it = [d[0].lower() for d in cur.description]
            itens = [dict(zip(cols_it, r)) for r in cur.fetchall()]
            cab['itens'] = itens
            return cab
    except Exception:
        logger.exception("Erro em obter_pedido_email_completo")
        return None


def listar_pedidos_email_aguardando_parser(limite: int = 20) -> list[dict]:
    """Lista IDs+texto+remetente dos registros AGUARDANDO_PARSER (uso do worker LLM)."""
    sql = """
    SELECT * FROM (
        SELECT ID, MESSAGE_ID, REMETENTE, PDF_PATH, PDF_TEXTO
        FROM AD_PEDIDO_EMAIL_RECEBIDO
        WHERE STATUS = 'AGUARDANDO_PARSER'
        ORDER BY RECEBIDO_EM ASC NULLS LAST, ID ASC
    ) WHERE ROWNUM <= :lim
    """
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(sql, lim=int(limite))
            cols = [d[0].lower() for d in cur.description]
            linhas = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                v = d.get('pdf_texto')
                if v is not None and hasattr(v, 'read'):
                    d['pdf_texto'] = v.read()
                linhas.append(d)
            return linhas
    except Exception:
        logger.exception("Erro em listar_pedidos_email_aguardando_parser")
        return []


def atualizar_pedido_email_parser_resultado(recebido_id: int, resultado: dict,
                                              conexao_existente=None) -> dict:
    """Após parser LLM rodar, grava sugestões e troca STATUS para PENDENTE_REVISAO.

    `resultado` deve conter:
      LLM_RESPOSTA (str JSON cru), LLM_MODELO, LLM_TOKENS_IN, LLM_TOKENS_OUT,
      LLM_CONFIANCA_GERAL, CODPARC_SUGERIDO, CODEMP_SUGERIDO,
      DTNEG_SUGERIDA, CODTIPVENDA_SUGERIDO, OBSERVACAO_EXTRAIDA.
    """
    def _operar(conn):
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE AD_PEDIDO_EMAIL_RECEBIDO
               SET LLM_RESPOSTA         = :llm_resposta,
                   LLM_MODELO           = :llm_modelo,
                   LLM_TOKENS_IN        = :tok_in,
                   LLM_TOKENS_OUT       = :tok_out,
                   LLM_CONFIANCA_GERAL  = :conf,
                   CODPARC_SUGERIDO     = :codparc,
                   CODEMP_SUGERIDO      = :codemp,
                   DTNEG_SUGERIDA       = :dtneg,
                   CODTIPVENDA_SUGERIDO = :codtv,
                   OBSERVACAO_EXTRAIDA  = :obs,
                   STATUS               = 'PENDENTE_REVISAO'
             WHERE ID = :id
            """,
            {
                'id': recebido_id,
                'llm_resposta': resultado.get('LLM_RESPOSTA'),
                'llm_modelo': resultado.get('LLM_MODELO'),
                'tok_in': resultado.get('LLM_TOKENS_IN'),
                'tok_out': resultado.get('LLM_TOKENS_OUT'),
                'conf': resultado.get('LLM_CONFIANCA_GERAL'),
                'codparc': resultado.get('CODPARC_SUGERIDO'),
                'codemp': resultado.get('CODEMP_SUGERIDO'),
                'dtneg': resultado.get('DTNEG_SUGERIDA'),
                'codtv': resultado.get('CODTIPVENDA_SUGERIDO'),
                'obs': resultado.get('OBSERVACAO_EXTRAIDA'),
            },
        )
        return {'ok': True, 'rows': cur.rowcount}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em atualizar_pedido_email_parser_resultado")
        return {'ok': False, 'error': str(exc)}


def atualizar_pedido_email_status(recebido_id: int, novo_status: str,
                                    motivo_descarte: str | None = None,
                                    conexao_existente=None) -> dict:
    """Atualiza STATUS de um pré-pedido. Para DESCARTADO, grava motivo."""
    if novo_status not in EMAIL_STATUS_VALIDOS:
        return {'ok': False, 'error': f"STATUS inválido: {novo_status}"}

    def _operar(conn):
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE AD_PEDIDO_EMAIL_RECEBIDO
               SET STATUS = :st,
                   MOTIVO_DESCARTE = COALESCE(:motivo, MOTIVO_DESCARTE)
             WHERE ID = :id
            """,
            {'st': novo_status, 'motivo': motivo_descarte, 'id': recebido_id},
        )
        return {'ok': True, 'rows': cur.rowcount}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em atualizar_pedido_email_status")
        return {'ok': False, 'error': str(exc)}


def atualizar_pedido_email_item(item_id: int, dados: dict,
                                  conexao_existente=None) -> dict:
    """Operador editou um item na tela de revisão. Aceita campos parciais."""
    campos_permitidos = {
        'DESCRICAO_PDF', 'CODPROD_FINAL', 'QTD', 'CODVOL', 'PRECO_UNIT', 'OBSERVACAO',
    }
    sets = []
    binds: dict = {'id': item_id}
    for k, v in dados.items():
        ku = k.upper()
        if ku in campos_permitidos:
            sets.append(f"{ku} = :{ku.lower()}")
            binds[ku.lower()] = v
    if not sets:
        return {'ok': False, 'error': 'Nenhum campo válido para atualizar.'}

    def _operar(conn):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE AD_PEDIDO_EMAIL_ITEM SET {', '.join(sets)} WHERE ID = :id",
            binds,
        )
        return {'ok': True, 'rows': cur.rowcount}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em atualizar_pedido_email_item")
        return {'ok': False, 'error': str(exc)}


def deletar_itens_do_pedido_email(recebido_id: int, conexao_existente=None) -> dict:
    """Remove TODOS os itens de um pré-pedido. Usado por 'Restaurar tudo'."""
    def _operar(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM AD_PEDIDO_EMAIL_ITEM WHERE RECEBIDO_ID = :rid",
                    rid=int(recebido_id))
        return {'ok': True, 'rows': cur.rowcount}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em deletar_itens_do_pedido_email")
        return {'ok': False, 'error': str(exc)}


def deletar_pedido_email_item(item_id: int, conexao_existente=None) -> dict:
    """Remove um item da revisão (operador clicou lixeira na tela)."""
    def _operar(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM AD_PEDIDO_EMAIL_ITEM WHERE ID = :id", id=item_id)
        return {'ok': True, 'rows': cur.rowcount}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em deletar_pedido_email_item")
        return {'ok': False, 'error': str(exc)}


def vincular_nunota_pedido_email(recebido_id: int, nunota: int, codusu: int,
                                   conexao_existente=None) -> dict:
    """Após confirmação que cria TGFCAB, marca pré-pedido como CONFIRMADO."""
    def _operar(conn):
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE AD_PEDIDO_EMAIL_RECEBIDO
               SET STATUS         = 'CONFIRMADO',
                   NUNOTA_GERADO  = :nunota,
                   CONFIRMADO_POR = :codusu,
                   CONFIRMADO_EM  = SYSTIMESTAMP
             WHERE ID = :id
            """,
            {'nunota': nunota, 'codusu': codusu, 'id': recebido_id},
        )
        return {'ok': True, 'rows': cur.rowcount}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em vincular_nunota_pedido_email")
        return {'ok': False, 'error': str(exc)}


def consultar_ultimo_pedido_codparc(codparc: int) -> dict | None:
    """Retorna CODEMP/CODTIPVENDA do último pedido (TOP 34/35/37) deste parceiro.

    Usado para pré-popular sugestões na tela de revisão. None se nunca comprou.
    """
    if not codparc:
        return None
    sql = """
    SELECT * FROM (
        SELECT CODEMP, CODTIPVENDA, DTNEG
          FROM TGFCAB
         WHERE CODPARC = :p
           AND CODTIPOPER IN (34, 35, 37)
           AND NVL(STATUSNOTA, 'A') <> 'E'
         ORDER BY DTNEG DESC NULLS LAST, NUNOTA DESC
    ) WHERE ROWNUM = 1
    """
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(sql, p=int(codparc))
            row = cur.fetchone()
            if not row: return None
            return {'codemp': row[0], 'codtipvenda': row[1], 'dtneg': row[2]}
    except Exception:
        logger.exception("Erro em consultar_ultimo_pedido_codparc")
        return None


def consultar_pedido_email_por_message_id(message_id: str) -> dict | None:
    """Retorna o registro pelo MESSAGE_ID (anti-duplicação no worker IMAP)."""
    if not message_id: return None
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT ID, STATUS FROM AD_PEDIDO_EMAIL_RECEBIDO WHERE MESSAGE_ID = :m",
                m=message_id,
            )
            row = cur.fetchone()
            if not row: return None
            return {'id': row[0], 'status': row[1]}
    except Exception:
        logger.exception("Erro em consultar_pedido_email_por_message_id")
        return None


# =============================================================================
# Aprendizado por de-para — AD_PRODUTO_ALIAS / AD_PARCEIRO_ALIAS
# =============================================================================
# Após o operador confirmar um pré-pedido na tela /sankhya/venda/email-importar/,
# salvamos as decisões dele aqui. Próximas execuções do worker LLM vão consultar
# essas tabelas ANTES do fuzzy matching — alias bate, retorna direto.
# Não é Machine Learning. É um dicionário deterministico.
# =============================================================================

def buscar_alias_produto(descricao_normalizada: str,
                          codparc: int | None = None) -> int | None:
    """Retorna CODPROD aprendido para uma descrição (já normalizada).

    Lógica de busca em 2 etapas (mais específico antes):
      1. (descr + codparc) — alias específico desse cliente
      2. (descr + NULL)    — alias global (vale pra todos os clientes)
    Retorna None se não houver match.

    Side effect: incrementa COUNT_USADO + atualiza ULTIMO_USO ao retornar match.
    """
    if not descricao_normalizada:
        return None
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            # Etapa 1: alias específico do cliente
            if codparc:
                cur.execute(
                    "SELECT ID, CODPROD FROM AD_PRODUTO_ALIAS "
                    " WHERE DESCRICAO_NORMALIZADA = :d AND CODPARC = :p",
                    d=descricao_normalizada, p=int(codparc),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE AD_PRODUTO_ALIAS SET COUNT_USADO = COUNT_USADO + 1, "
                        "       ULTIMO_USO = SYSTIMESTAMP WHERE ID = :id",
                        id=row[0],
                    )
                    conn.commit()
                    return int(row[1])
            # Etapa 2: alias global
            cur.execute(
                "SELECT ID, CODPROD FROM AD_PRODUTO_ALIAS "
                " WHERE DESCRICAO_NORMALIZADA = :d AND CODPARC IS NULL",
                d=descricao_normalizada,
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE AD_PRODUTO_ALIAS SET COUNT_USADO = COUNT_USADO + 1, "
                    "       ULTIMO_USO = SYSTIMESTAMP WHERE ID = :id",
                    id=row[0],
                )
                conn.commit()
                return int(row[1])
            return None
    except Exception:
        logger.exception("Erro em buscar_alias_produto")
        return None


def buscar_alias_parceiro(nome_normalizado: str) -> int | None:
    """Retorna CODPARC aprendido para um nome de cliente (já normalizado).

    Side effect: incrementa COUNT_USADO + atualiza ULTIMO_USO ao retornar match.
    """
    if not nome_normalizado:
        return None
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT ID, CODPARC FROM AD_PARCEIRO_ALIAS WHERE NOME_NORMALIZADO = :n",
                n=nome_normalizado,
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "UPDATE AD_PARCEIRO_ALIAS SET COUNT_USADO = COUNT_USADO + 1, "
                "       ULTIMO_USO = SYSTIMESTAMP WHERE ID = :id",
                id=row[0],
            )
            conn.commit()
            return int(row[1])
    except Exception:
        logger.exception("Erro em buscar_alias_parceiro")
        return None


def gravar_alias_produto(descricao_normalizada: str, codprod: int,
                          codparc: int | None = None,
                          confirmado_por: int | None = None,
                          conexao_existente=None) -> dict:
    """Grava ou atualiza um alias produto após confirmação do operador.

    UPSERT: se já existe (descr, codparc), atualiza CODPROD (operador mudou de
    ideia, vale a última escolha). Senão, insere novo.
    """
    if not descricao_normalizada or not codprod:
        return {'ok': False, 'error': 'descricao ou codprod vazio'}

    def _operar(conn):
        cur = conn.cursor()
        # Tenta UPDATE primeiro (mais comum: alias já existe e operador apenas reconfirmou)
        cur.execute(
            "UPDATE AD_PRODUTO_ALIAS "
            "   SET CODPROD = :codprod, ULTIMO_USO = SYSTIMESTAMP, "
            "       CONFIRMADO_POR = COALESCE(:cu, CONFIRMADO_POR) "
            " WHERE DESCRICAO_NORMALIZADA = :d "
            "   AND ((:p IS NULL AND CODPARC IS NULL) OR CODPARC = :p)",
            {'codprod': int(codprod), 'cu': confirmado_por,
             'd': descricao_normalizada,
             'p': int(codparc) if codparc else None},
        )
        if cur.rowcount > 0:
            return {'ok': True, 'acao': 'UPDATE'}

        # Não existe — INSERT
        novo_id = _proximo_id_sequence(cur, 'SEQ_AD_PRODUTO_ALIAS')
        cur.execute(
            "INSERT INTO AD_PRODUTO_ALIAS "
            "  (ID, DESCRICAO_NORMALIZADA, CODPROD, CODPARC, COUNT_USADO, "
            "   ULTIMO_USO, CONFIRMADO_POR) "
            "VALUES (:id, :d, :codprod, :p, 0, SYSTIMESTAMP, :cu)",
            {'id': novo_id, 'd': descricao_normalizada,
             'codprod': int(codprod),
             'p': int(codparc) if codparc else None,
             'cu': confirmado_por},
        )
        return {'ok': True, 'acao': 'INSERT', 'id': novo_id}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em gravar_alias_produto")
        return {'ok': False, 'error': str(exc)}


def gravar_alias_parceiro(nome_normalizado: str, codparc: int,
                           confirmado_por: int | None = None,
                           conexao_existente=None) -> dict:
    """Grava ou atualiza um alias parceiro após confirmação do operador. UPSERT."""
    if not nome_normalizado or not codparc:
        return {'ok': False, 'error': 'nome ou codparc vazio'}

    def _operar(conn):
        cur = conn.cursor()
        cur.execute(
            "UPDATE AD_PARCEIRO_ALIAS "
            "   SET CODPARC = :codparc, ULTIMO_USO = SYSTIMESTAMP, "
            "       CONFIRMADO_POR = COALESCE(:cu, CONFIRMADO_POR) "
            " WHERE NOME_NORMALIZADO = :n",
            {'codparc': int(codparc), 'cu': confirmado_por, 'n': nome_normalizado},
        )
        if cur.rowcount > 0:
            return {'ok': True, 'acao': 'UPDATE'}
        novo_id = _proximo_id_sequence(cur, 'SEQ_AD_PARCEIRO_ALIAS')
        cur.execute(
            "INSERT INTO AD_PARCEIRO_ALIAS "
            "  (ID, NOME_NORMALIZADO, CODPARC, COUNT_USADO, ULTIMO_USO, CONFIRMADO_POR) "
            "VALUES (:id, :n, :codparc, 0, SYSTIMESTAMP, :cu)",
            {'id': novo_id, 'n': nome_normalizado,
             'codparc': int(codparc), 'cu': confirmado_por},
        )
        return {'ok': True, 'acao': 'INSERT', 'id': novo_id}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em gravar_alias_parceiro")
        return {'ok': False, 'error': str(exc)}


# =============================================================================
# Aprendizado por código do cliente (AD_CLIENTE_PRODUTO_COD)
# =============================================================================
# Mais forte que alias por descrição: o "Cod Forn" do PDF Consinco (ex: 8117)
# é estável e único por cliente. Match exato → CODPROD direto, confiança 100.
# Usado como Etapa 0 do matching híbrido (alias por descrição é Etapa 1, fuzzy é Etapa 2).
# Tudo isso é resiliente à migration AD_CLIENTE_PRODUTO_COD.sql ainda não aplicada
# em produção — funções devolvem None ou {'ok': False} silencioso, sem quebrar
# o pipeline.

def buscar_cod_cliente_codprod(codparc: int, cod_cliente: str) -> int | None:
    """Retorna CODPROD aprendido para (CODPARC, COD_CLIENTE), ou None.

    Side effect: incrementa COUNT_USADO + atualiza ULTIMO_USO ao retornar match.
    """
    if not codparc or not cod_cliente:
        return None
    cod_cliente = str(cod_cliente).strip()[:50]
    if not cod_cliente:
        return None
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            # Tabela pode ainda não existir (migration não aplicada) → retorna None.
            if not _existe_coluna(cur, 'AD_CLIENTE_PRODUTO_COD', 'CODPROD'):
                return None
            cur.execute(
                "SELECT ID, CODPROD FROM AD_CLIENTE_PRODUTO_COD "
                " WHERE CODPARC = :p AND COD_CLIENTE = :c",
                {'p': int(codparc), 'c': cod_cliente},
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "UPDATE AD_CLIENTE_PRODUTO_COD "
                "   SET COUNT_USADO = COUNT_USADO + 1, ULTIMO_USO = SYSTIMESTAMP "
                " WHERE ID = :id",
                id=row[0],
            )
            conn.commit()
            return int(row[1])
    except Exception:
        logger.exception("Erro em buscar_cod_cliente_codprod")
        return None


def gravar_cod_cliente_codprod(codparc: int, cod_cliente: str, codprod: int,
                                confirmado_por: int | None = None,
                                conexao_existente=None) -> dict:
    """Grava ou atualiza vinculação (CODPARC, COD_CLIENTE) -> CODPROD após
    confirmação do operador. UPSERT.

    Resiliente: se a tabela não existir ainda (migration não aplicada),
    retorna {'ok': False, 'error': '...'} sem quebrar o fluxo de confirmação
    do pedido (que vai gravar TGFCAB normalmente).
    """
    if not codparc or not cod_cliente or not codprod:
        return {'ok': False, 'error': 'codparc, cod_cliente ou codprod vazio'}
    cod_cliente = str(cod_cliente).strip()[:50]
    if not cod_cliente:
        return {'ok': False, 'error': 'cod_cliente vazio após normalização'}

    def _operar(conn):
        cur = conn.cursor()
        if not _existe_coluna(cur, 'AD_CLIENTE_PRODUTO_COD', 'CODPROD'):
            return {'ok': False, 'error': 'tabela AD_CLIENTE_PRODUTO_COD não existe (migration pendente)'}

        # UPSERT: tenta UPDATE; se 0 rows, INSERT
        cur.execute(
            "UPDATE AD_CLIENTE_PRODUTO_COD "
            "   SET CODPROD = :codprod, ULTIMO_USO = SYSTIMESTAMP, "
            "       CONFIRMADO_POR = COALESCE(:cu, CONFIRMADO_POR) "
            " WHERE CODPARC = :p AND COD_CLIENTE = :c",
            {'codprod': int(codprod), 'cu': confirmado_por,
             'p': int(codparc), 'c': cod_cliente},
        )
        if cur.rowcount > 0:
            return {'ok': True, 'acao': 'UPDATE'}

        novo_id = _proximo_id_sequence(cur, 'SEQ_AD_CLIENTE_PRODUTO_COD')
        cur.execute(
            "INSERT INTO AD_CLIENTE_PRODUTO_COD "
            "  (ID, CODPARC, COD_CLIENTE, CODPROD, COUNT_USADO, "
            "   ULTIMO_USO, CONFIRMADO_POR) "
            "VALUES (:id, :p, :c, :codprod, 0, SYSTIMESTAMP, :cu)",
            {'id': novo_id, 'p': int(codparc), 'c': cod_cliente,
             'codprod': int(codprod), 'cu': confirmado_por},
        )
        return {'ok': True, 'acao': 'INSERT', 'id': novo_id}

    try:
        if conexao_existente is not None:
            return _operar(conexao_existente)
        with obter_conexao_oracle() as conn:
            res = _operar(conn)
            if res.get('ok'): conn.commit()
            return res
    except Exception as exc:
        logger.exception("Erro em gravar_cod_cliente_codprod")
        return {'ok': False, 'error': str(exc)}


# ==============================================================================
# 🔄 5. AVARIA (TOP 30) + DEVOLUÇÃO (TOP 36) + HISTÓRICO DE LOTE — Mai/2026
# ==============================================================================
#
# Premissas (ver .claude/modules/venda.md):
# - Avaria interna: TGFCAB TOP 30 STATUSNOTA='L' direto (sem TGFVAR, sem
#   financeiro reverso). CODAGREGACAO obrigatório no item — rastreabilidade
#   por lote é decisão do IAgro (Sankhya nativo deixa CODAGREGACAO=NULL).
# - Devolução: TGFCAB TOP 36 STATUSNOTA='A' (em aberto) + TGFITE par-a-par
#   preservando CODAGREGACAO da nota origem + INSERT em TGFVAR replicando
#   fielmente o Sankhya nativo. Operador confirma no Sankhya, que dispara
#   financeiro reverso e NFe de devolução.
# - Histórico do lote: lê TGFITE+TGFCAB de um CODAGREGACAO. Timeline ordenada
#   por DTNEG ASC. Permite "pegar um lote e ver o que aconteceu com ele".

# Nome canônico das TOPs para o histórico (mapeado em apenas 1 lugar)
_NOMES_TOP = {
    11: 'Compra (Entrada)',
    13: 'Vale de compra',
    26: 'Classificação',
    30: 'Avaria interna',
    34: 'Pedido de venda',
    35: 'Venda com NFe',
    36: 'Devolução de venda',
    37: 'Venda sem NFe',
}


def consultar_devolucoes_anteriores_de_nota(nunota_origem: int) -> dict:
    """Lê TGFVAR pra somar QTDATENDIDA agrupada por SEQUENCIAORIG.

    Usada na trava de "devolução excessiva" antes de criar TOP 36:
        qtd_a_devolver + ja_devolvido <= qtd_vendida

    Conta devoluções com STATUSNOTA <> 'E' (inclui 'A' em aberto + 'L'
    confirmadas) — devolução em aberto já bloqueia novo lote daquela qtd.

    Retorno: {ok: True, por_sequencia: {seq_orig: qtd_devolvida}}
    """
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT v.SEQUENCIAORIG, NVL(SUM(v.QTDATENDIDA), 0) AS QTD_DEVOLVIDA
                FROM TGFVAR v
                JOIN TGFCAB c ON c.NUNOTA = v.NUNOTA
                WHERE v.NUNOTAORIG = :n
                  AND c.CODTIPOPER = 36
                  AND c.STATUSNOTA <> 'E'
                GROUP BY v.SEQUENCIAORIG
            """, n=int(nunota_origem))
            por_seq = {int(row[0]): float(row[1] or 0) for row in cur.fetchall()}
        return {'ok': True, 'por_sequencia': por_seq}
    except Exception as exc:
        logger.exception("Erro em consultar_devolucoes_anteriores_de_nota")
        return {'ok': False, 'error': str(exc), 'por_sequencia': {}}


def consultar_nota_para_devolucao(nunota_origem: int) -> dict:
    """Lê cabeçalho + itens de uma TOP 35/37 STATUSNOTA='L', incluindo a
    quantidade já devolvida por SEQUENCIA (somatório de TGFVAR).

    Usada pelo modal de devolução pra montar a lista de itens com travas.

    Retorno: {ok: True, cabecalho: {...}, itens: [...]}
        itens[i] = {sequencia, codprod, descrprod, codagregacao, codvol,
                    qtdneg, vlrunit, vlrtot, qtd_ja_devolvida, qtd_devolvivel}
    """
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT c.NUNOTA, c.NUMNOTA, c.CODEMP, c.CODPARC,
                       c.CODTIPOPER, c.STATUSNOTA, c.VLRNOTA, c.CODTIPVENDA,
                       TO_CHAR(c.DTNEG, 'YYYY-MM-DD') AS DTNEG_STR,
                       p.NOMEPARC
                FROM TGFCAB c
                LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
                WHERE c.NUNOTA = :n
            """, n=int(nunota_origem))
            cab_row = cur.fetchone()
            if not cab_row:
                return {'ok': False, 'error': 'Nota não encontrada'}

            codtipoper = int(cab_row[4])
            statusnota = cab_row[5]
            if codtipoper not in (35, 37):
                return {
                    'ok': False,
                    'error': f'Devolução só de notas faturadas (TOP 35/37). '
                             f'NUNOTA {nunota_origem} é TOP {codtipoper}.',
                }
            if statusnota != 'L':
                return {
                    'ok': False,
                    'error': f'Nota precisa estar faturada (STATUSNOTA=L). '
                             f'NUNOTA {nunota_origem} está STATUSNOTA={statusnota}.',
                }

            cabecalho = {
                'nunota': int(cab_row[0]),
                'numnota': int(cab_row[1] or 0),
                'codemp': int(cab_row[2]),
                'codparc': int(cab_row[3]),
                'codtipoper': codtipoper,
                'statusnota': statusnota,
                'vlrnota': float(cab_row[6] or 0),
                'codtipvenda': int(cab_row[7] or 0),
                'dtneg': cab_row[8],
                'nomeparc': cab_row[9] or '',
            }

            # Itens da nota
            cur.execute("""
                SELECT i.SEQUENCIA, i.CODPROD, pr.DESCRPROD, i.CODAGREGACAO,
                       i.CODVOL, NVL(i.QTDNEG, 0), NVL(i.VLRUNIT, 0),
                       NVL(i.VLRTOT, 0)
                FROM TGFITE i
                LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
                WHERE i.NUNOTA = :n
                ORDER BY i.SEQUENCIA
            """, n=int(nunota_origem))
            itens_raw = cur.fetchall()

        # Quanto já foi devolvido por sequência
        ja_dev = consultar_devolucoes_anteriores_de_nota(nunota_origem)
        por_seq = ja_dev.get('por_sequencia', {})

        itens = []
        for r in itens_raw:
            seq = int(r[0])
            qtdneg = float(r[5])
            ja = float(por_seq.get(seq, 0))
            itens.append({
                'sequencia': seq,
                'codprod': int(r[1]),
                'descrprod': r[2] or '',
                'codagregacao': r[3] or '',
                'codvol': r[4] or 'UN',
                'qtdneg': qtdneg,
                'vlrunit': float(r[6]),
                'vlrtot': float(r[7]),
                'qtd_ja_devolvida': ja,
                'qtd_devolvivel': max(qtdneg - ja, 0),
            })

        return {'ok': True, 'cabecalho': cabecalho, 'itens': itens}
    except Exception as exc:
        logger.exception("Erro em consultar_nota_para_devolucao")
        return {'ok': False, 'error': str(exc)}


def criar_avaria_top30_banco(dados: dict, codusu_logado: int | None = None) -> dict:
    """Cria TGFCAB TOP 30 (avaria) + TGFITE com CODAGREGACAO obrigatório.

    STATUSNOTA='L' direto — avaria não tem financeiro, não tem NFe, não tem
    TGFVAR. View ANDRE_IAGRO_SALDO_LOTE perna `baixas_avaria` já desconta
    automaticamente do saldo.

    dados esperado:
        codemp: int
        codparc: int
        codagregacao: str (lote — obrigatório, é a chave da rastreabilidade)
        codprod: int
        qtdneg: float
        codvol: str (default 'KG')
        vlrunit: float (opcional, default 0)
        numnota_ref: str|int (opcional — número da venda original, livre)
        observacao: str (opcional — default 'AVARIA')
        codtipvenda: int (opcional — default 11)
        dtneg: 'DD/MM/YYYY' (opcional — default hoje)

    Retorno: {ok, executed, nunota, codnat, vlrnota}
    """
    resultado = {'ok': False, 'executed': False, 'nunota': None}

    if not verificar_permissao_escrita():
        resultado['error'] = 'Escrita desabilitada'
        return resultado

    # Validações de payload
    obrigatorios = ['codemp', 'codparc', 'codagregacao', 'codprod', 'qtdneg']
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        resultado['error'] = f'Campos obrigatórios faltando: {", ".join(faltando)}'
        return resultado

    try:
        codemp = int(dados['codemp'])
        codparc = int(dados['codparc'])
        codagregacao = str(dados['codagregacao']).strip().upper()
        codprod = int(dados['codprod'])
        qtdneg = float(dados['qtdneg'])
        if qtdneg <= 0:
            resultado['error'] = 'Quantidade deve ser maior que zero'
            return resultado
    except (ValueError, TypeError):
        resultado['error'] = 'Tipos inválidos no payload'
        return resultado

    codvol = str(dados.get('codvol') or 'KG').strip().upper()
    vlrunit = float(dados.get('vlrunit') or 0)
    numnota_ref = dados.get('numnota_ref') or 0
    observacao = (dados.get('observacao') or 'AVARIA').strip()
    codtipvenda = int(dados.get('codtipvenda') or 11)
    dtneg = dados.get('dtneg') or datetime.now().strftime('%d/%m/%Y')

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            try:
                # Valida lote existe e tem saldo
                cur.execute("""
                    SELECT NVL(SUM(QTD_DISPONIVEL), 0)
                    FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
                    WHERE CODAGREGACAO = :l AND CODPROD = :p
                """, l=codagregacao, p=codprod)
                row = cur.fetchone()
                saldo = float(row[0] or 0) if row else 0
                if saldo <= 0:
                    resultado['error'] = (
                        f'Lote {codagregacao} sem saldo disponível para o produto {codprod}.'
                    )
                    return resultado
                if qtdneg > saldo:
                    resultado['error'] = (
                        f'Saldo insuficiente no lote {codagregacao}. '
                        f'Disponível: {saldo:.3f} · Solicitado: {qtdneg:.3f}.'
                    )
                    return resultado

                # 1) Cabeçalho TGFCAB
                cab_payload = {
                    'CODEMP': codemp,
                    'CODPARC': codparc,
                    'CODTIPOPER': 30,
                    'CODNAT': CODNAT_POR_TOP[30],
                    'DTNEG': dtneg,
                    'CODTIPVENDA': codtipvenda,
                    'OBSERVACAO': observacao,
                    'PENDENTE': 'N',
                    'NUMNOTA': int(numnota_ref) if str(numnota_ref).strip().isdigit() else 0,
                }
                ret_cab = inserir_cabecalho_nota_banco(
                    cab_payload, conexao_existente=conn,
                )
                if not ret_cab.get('ok'):
                    resultado['error'] = ret_cab.get('error') or 'Falha ao criar cabeçalho TOP 30'
                    return resultado
                novo_nunota = int(ret_cab['nunota'])

                # 2) Item TGFITE com CODAGREGACAO obrigatório
                ite_payload = {
                    'NUNOTA': novo_nunota,
                    'CODPROD': codprod,
                    'QTDNEG': qtdneg,
                    'VLRUNIT': vlrunit,
                    'CODVOL': codvol,
                    'CODLOCALORIG': 101,
                    'CODAGREGACAO': codagregacao,
                    'OBSERVACAO': observacao,
                }
                ret_ite = inserir_item_nota_banco(
                    ite_payload,
                    conexao_existente=conn,
                    codusu_logado=codusu_logado,
                    gerar_lote_auto=False,
                )
                if not ret_ite.get('ok'):
                    resultado['error'] = ret_ite.get('error') or 'Falha ao criar item TOP 30'
                    return resultado

                # 3) Recalcular totais (define VLRNOTA)
                ret_rec = recalcular_totais_nota_banco(novo_nunota, conexao_existente=conn)
                vlrnota = float(ret_rec.get('vlrnota') or (qtdneg * vlrunit))

                # 4) Confirma direto STATUSNOTA='L' (avaria não tem fluxo de aprovação)
                cur.execute("""
                    UPDATE TGFCAB SET STATUSNOTA = 'L'
                    WHERE NUNOTA = :n
                """, n=novo_nunota)

                conn.commit()
                resultado.update({
                    'ok': True, 'executed': True,
                    'nunota': novo_nunota,
                    'codnat': CODNAT_POR_TOP[30],
                    'vlrnota': vlrnota,
                })
                return resultado
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as exc:
        logger.exception("Erro em criar_avaria_top30_banco")
        resultado['error'] = humanizar_erro_oracle(exc)
        return resultado


def criar_devolucao_top36_banco(dados: dict, codusu_logado: int | None = None) -> dict:
    """Cria TGFCAB TOP 36 (devolução) + TGFITE par-a-par + TGFVAR.

    STATUSNOTA='A' (em aberto). Operador confirma no Sankhya pra disparar
    financeiro reverso + emissão NFe de devolução.

    dados esperado:
        nunota_origem: int (TOP 35/37 STATUSNOTA='L')
        itens: list[{sequencia_origem, qtd_devolver, vlrunit?}]
        observacao: str (opcional — default 'DEVOLUCAO')
        dtneg: 'DD/MM/YYYY' (opcional — default hoje)

    Retorno: {ok, executed, nunota, codnat, vlrnota}
    """
    resultado = {'ok': False, 'executed': False, 'nunota': None}

    if not verificar_permissao_escrita():
        resultado['error'] = 'Escrita desabilitada'
        return resultado

    if not dados.get('nunota_origem'):
        resultado['error'] = 'nunota_origem obrigatório'
        return resultado
    itens_pedidos = dados.get('itens') or []
    if not itens_pedidos:
        resultado['error'] = 'Nenhum item informado para devolução'
        return resultado

    try:
        nunota_origem = int(dados['nunota_origem'])
    except (ValueError, TypeError):
        resultado['error'] = 'nunota_origem inválido'
        return resultado

    observacao = (dados.get('observacao') or 'DEVOLUCAO').strip()
    dtneg = dados.get('dtneg') or datetime.now().strftime('%d/%m/%Y')

    # Carrega contexto da nota origem (cabeçalho + itens + qtd já devolvida)
    info = consultar_nota_para_devolucao(nunota_origem)
    if not info.get('ok'):
        resultado['error'] = info.get('error') or 'Falha ao carregar nota origem'
        return resultado

    cab_origem = info['cabecalho']
    itens_origem_por_seq = {it['sequencia']: it for it in info['itens']}

    # Valida cada item pedido contra o saldo devolvível
    itens_para_inserir = []
    for it_req in itens_pedidos:
        try:
            seq_orig = int(it_req.get('sequencia_origem'))
            qtd_dev = float(it_req.get('qtd_devolver') or 0)
        except (ValueError, TypeError):
            resultado['error'] = f'Item inválido: {it_req}'
            return resultado

        if qtd_dev <= 0:
            continue  # ignora linhas em branco

        if seq_orig not in itens_origem_por_seq:
            resultado['error'] = (
                f'Sequência {seq_orig} não pertence à nota {nunota_origem}'
            )
            return resultado

        it_orig = itens_origem_por_seq[seq_orig]
        devolvivel = it_orig['qtd_devolvivel']
        if qtd_dev > devolvivel + 1e-6:
            resultado['error'] = (
                f'Quantidade excessiva no item SEQ={seq_orig} ({it_orig["descrprod"]}). '
                f'Já devolvido: {it_orig["qtd_ja_devolvida"]:.3f} · '
                f'Saldo devolvível: {devolvivel:.3f} · '
                f'Solicitado: {qtd_dev:.3f}.'
            )
            return resultado

        # Preço: usa o do payload se vier, senão preserva o original
        vlrunit_req = it_req.get('vlrunit')
        vlrunit = float(vlrunit_req) if vlrunit_req is not None else it_orig['vlrunit']

        itens_para_inserir.append({
            'sequencia_origem': seq_orig,
            'codprod': it_orig['codprod'],
            'qtdneg': qtd_dev,
            'vlrunit': vlrunit,
            'codvol': it_orig['codvol'],
            'codagregacao': it_orig['codagregacao'] or None,
        })

    if not itens_para_inserir:
        resultado['error'] = 'Nenhum item com quantidade > 0 para devolver'
        return resultado

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            try:
                # 1) Cabeçalho TGFCAB TOP 36
                cab_payload = {
                    'CODEMP': cab_origem['codemp'],
                    'CODPARC': cab_origem['codparc'],
                    'CODTIPOPER': 36,
                    'CODNAT': CODNAT_POR_TOP[36],
                    'DTNEG': dtneg,
                    'CODTIPVENDA': cab_origem['codtipvenda'] or 2,
                    'OBSERVACAO': observacao,
                    'PENDENTE': 'S',  # em aberto até confirmação
                    'AD_NUMPEDIDOORIG': None,  # Sankhya nativo deixa NULL
                }
                ret_cab = inserir_cabecalho_nota_banco(
                    cab_payload, conexao_existente=conn,
                )
                if not ret_cab.get('ok'):
                    resultado['error'] = ret_cab.get('error') or 'Falha ao criar cabeçalho TOP 36'
                    return resultado
                novo_nunota = int(ret_cab['nunota'])

                # 2) Itens TGFITE + 3) TGFVAR par-a-par
                # Necessário SEQUENCIA do TGFITE recém-criado pra popular TGFVAR
                for item in itens_para_inserir:
                    ite_payload = {
                        'NUNOTA': novo_nunota,
                        'CODPROD': item['codprod'],
                        'QTDNEG': item['qtdneg'],
                        'VLRUNIT': item['vlrunit'],
                        'CODVOL': item['codvol'],
                        'CODLOCALORIG': 101,
                        'CODAGREGACAO': item['codagregacao'],
                        'OBSERVACAO': observacao,
                    }
                    ret_ite = inserir_item_nota_banco(
                        ite_payload,
                        conexao_existente=conn,
                        codusu_logado=codusu_logado,
                        gerar_lote_auto=False,
                    )
                    if not ret_ite.get('ok'):
                        resultado['error'] = ret_ite.get('error') or 'Falha ao inserir item TOP 36'
                        return resultado

                    seq_nova = int(ret_ite['sequencia'])

                    # TGFVAR — replica fielmente Sankhya nativo
                    cur.execute("""
                        INSERT INTO TGFVAR (
                            NUNOTA, SEQUENCIA, NUNOTAORIG, SEQUENCIAORIG,
                            QTDATENDIDA, STATUSNOTA
                        ) VALUES (:n, :s, :no, :so, :q, 'A')
                    """, {
                        'n': novo_nunota,
                        's': seq_nova,
                        'no': nunota_origem,
                        'so': item['sequencia_origem'],
                        'q': item['qtdneg'],
                    })

                # 4) Recalcular totais (VLRNOTA)
                ret_rec = recalcular_totais_nota_banco(novo_nunota, conexao_existente=conn)
                vlrnota = float(ret_rec.get('vlrnota') or 0)

                # STATUSNOTA permanece 'A' (em aberto) — operador confirma no Sankhya

                conn.commit()
                resultado.update({
                    'ok': True, 'executed': True,
                    'nunota': novo_nunota,
                    'codnat': CODNAT_POR_TOP[36],
                    'vlrnota': vlrnota,
                })
                return resultado
            except Exception:
                try: conn.rollback()
                except Exception: pass
                raise
    except Exception as exc:
        logger.exception("Erro em criar_devolucao_top36_banco")
        resultado['error'] = humanizar_erro_oracle(exc)
        return resultado


def obter_historico_lote(codagregacao: str) -> dict:
    """Timeline completa de um lote: compra → classificação → venda → devolução/avaria.

    Lê TGFITE+TGFCAB por CODAGREGACAO. Cada linha vira um nó da timeline.
    Para TOP 35/37 com devolução, agrega os pares TGFVAR mostrando origem.

    Retorno: {ok: True, lote: str, timeline: [...]}
        timeline[i] = {
            nunota, numnota, codtipoper, top_nome, statusnota,
            dtneg, codparc, nomeparc, codprod, descrprod,
            qtdneg, codvol, vlrunit, vlrtot,
            is_baixa (bool — TOP 30/35/37), is_entrada (bool — TOP 11/26/13),
            is_devolucao (bool — TOP 36),
        }
    """
    if not codagregacao:
        return {'ok': False, 'error': 'Lote vazio'}

    lote = str(codagregacao).strip().upper()

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    c.NUNOTA, NVL(c.NUMNOTA, 0), c.CODTIPOPER, c.STATUSNOTA,
                    TO_CHAR(c.DTNEG, 'YYYY-MM-DD'),
                    c.CODPARC, p.NOMEPARC,
                    i.CODPROD, pr.DESCRPROD,
                    NVL(i.QTDNEG, 0), i.CODVOL,
                    NVL(i.VLRUNIT, 0), NVL(i.VLRTOT, 0),
                    i.SEQUENCIA, NVL(i.AD_QTDAVARIA, 0)
                FROM TGFITE i
                JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                LEFT JOIN TGFPAR p  ON p.CODPARC = c.CODPARC
                LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
                WHERE UPPER(i.CODAGREGACAO) = :l
                  AND c.STATUSNOTA <> 'E'
                ORDER BY c.DTNEG ASC, c.NUNOTA ASC, i.SEQUENCIA ASC
            """, l=lote)
            rows = cur.fetchall()

        if not rows:
            return {'ok': True, 'lote': lote, 'timeline': []}

        timeline = []
        for r in rows:
            top = int(r[2])
            timeline.append({
                'nunota': int(r[0]),
                'numnota': int(r[1] or 0),
                'codtipoper': top,
                'top_nome': _NOMES_TOP.get(top, f'TOP {top}'),
                'statusnota': r[3] or '',
                'dtneg': r[4],
                'codparc': int(r[5]) if r[5] else None,
                'nomeparc': r[6] or '',
                'codprod': int(r[7]),
                'descrprod': r[8] or '',
                'qtdneg': float(r[9]),
                'codvol': r[10] or 'UN',
                'vlrunit': float(r[11]),
                'vlrtot': float(r[12]),
                'sequencia': int(r[13]),
                'ad_qtdavaria': float(r[14]),
                'is_baixa': top in (30, 35, 37),
                'is_entrada': top in (11, 26, 13),
                'is_devolucao': top == 36,
            })

        return {'ok': True, 'lote': lote, 'timeline': timeline}
    except Exception as exc:
        logger.exception("Erro em obter_historico_lote")
        return {'ok': False, 'error': str(exc)}


# =============================================================================
# MÓDULO CONTROLE DE COMBUSTÍVEL (TOP 10 entrada Sankhya + TOP 26 requisição IAgro)
# Mai/2026 — Funções aditivas SOMENTE LEITURA.
# A função de escrita criar_requisicao_combustivel_banco vive em bloco separado
# (Categoria B — aguarda aprovação ponto-a-ponto).
# =============================================================================

# Grupo de produto que identifica combustíveis em TGFGRU.CODGRUPOPROD.
# Validado em produção Mai/2026:
#   - CODGRUPOPROD=200400 → DESCRGRUPOPROD='COMBUSTÍVEIS' (pai=200000 'MEF')
#   - Produtos atuais: 392 Diesel S10, 1373 Diesel S500, 391 Gasolina, 550 Óleo de Motor
# Não confundir com TSIGRU.CODGRUPO=11 (IAGRO_FROTA), que é grupo de USUÁRIO.
CODGRUPOPROD_COMBUSTIVEL = 200400

# Capacidade física dos tanques de combustível (litros). Filtra também quais
# produtos do grupo 200400 aparecem no card "Estoque" do portal — produtos sem
# tanque mapeado aqui (Gasolina, Óleo de Motor) não são exibidos.
# Mai/2026: Agromil tem 2 tanques físicos. Pra adicionar Arla32 ou outro,
# cadastre o produto em TGFPRO (CODGRUPOPROD=200400, CODVOL='LT') e adicione
# uma linha aqui com o CODPROD e a capacidade.
CAPACIDADE_TANQUE = {
    392:  10000.0,   # DIESEL S10  — tanque cilíndrico horizontal 10.000 LT
    1373: 5000.0,    # DIESEL S500 — tanque cilíndrico horizontal 5.000 LT
    1374: 1000.0,    # ARLA32      — IBC quadrado 1.000 LT
}

# Saldo pré-existente nos tanques antes do IAgro começar a registrar entradas
# TOP 10. Soma ao QTD_DISPONIVEL da view ANDRE_IAGRO_SALDO_COMBUSTIVEL.
# Mai/2026: Agromil tinha 300 LT de S10 e 3.150 LT de S500 nos tanques quando
# o módulo entrou em produção. Quando esses saldos forem consumidos, esses
# valores podem ser zerados aqui (mas não há urgência — view continua somando
# corretamente entradas/saídas IAgro daqui pra frente).
SALDO_INICIAL_TANQUE = {
    392:  896.0,   # DIESEL S10  — ajuste balanço físico 2026-05-15 (era 300.0; +596 pra bater 3000 L físico)
    1373: 3204.0,  # DIESEL S500 — ajuste balanço físico 2026-05-15 (era 3150.0; +54 pra bater 2490 L físico)
    1374: 300.0,   # ARLA 32     — saldo pré-existente no IBC ao entrar em produção
}

# Formato visual do tanque pra renderização SVG no frontend.
# Mai/2026: Diesel S10 e S500 são cilindros horizontais; Arla 32 é caixa
# quadrada (IBC/contêiner industrial). Pra adicionar um produto novo,
# inclua aqui o CODPROD com 'CILINDRO_HORIZONTAL' ou 'CAIXA_QUADRADA'.
# Default: CILINDRO_HORIZONTAL se ausente.
FORMATO_TANQUE = {
    392:  'CILINDRO_HORIZONTAL',
    1373: 'CILINDRO_HORIZONTAL',
    1374: 'CAIXA_QUADRADA',     # ARLA 32 — IBC industrial
}

# Ordem visual dos tanques no card de Estoque (esquerda → direita).
# Pra reordenar, edite os valores aqui. Tanques sem entrada vão pro fim.
ORDEM_TANQUE = {
    1374: 1,   # ARLA 32      (1ª posição)
    1373: 2,   # DIESEL S500  (2ª posição)
    392:  3,   # DIESEL S10   (3ª posição)
}


def consultar_saldo_combustivel(filtros: dict = None):
    """Lista saldo de combustível dos tanques mapeados em CAPACIDADE_TANQUE.
    Soma SALDO_INICIAL_TANQUE ao saldo da view + retorna capacidade física e
    percentual de preenchimento pra renderizar medidor visual no frontend.

    Mai/2026: combustível é despesa operacional compartilhada — não segrega
    por CODEMP. Produtos do grupo 200400 que NÃO estão em CAPACIDADE_TANQUE
    (ex: Gasolina, Óleo de Motor) não aparecem aqui — fora do escopo de
    controle de tanque.

    Aceita filtros opcionais:
      - q: str — UPPER LIKE em DESCRPROD

    Retorna lista de tuplas:
      (CODPROD, DESCRPROD, CODVOL,
       QTD_ENTRADA, QTD_SAIDA, QTD_DISPONIVEL,
       CAPACIDADE_LT, SALDO_INICIAL_LT, PERCENTUAL_CHEIO,
       FORMATO_TANQUE)
    """
    filtros = filtros or {}
    codprods_mapeados = list(CAPACIDADE_TANQUE.keys())
    if not codprods_mapeados:
        return []

    # Bind list explícito (Oracle não aceita IN :lista direto)
    placeholders = ','.join(f':p{i}' for i in range(len(codprods_mapeados)))
    binds_prod = {f'p{i}': cp for i, cp in enumerate(codprods_mapeados)}

    sql_view = f"""
        SELECT CODPROD, DESCRPROD, CODVOL,
               QTD_ENTRADA, QTD_SAIDA, QTD_DISPONIVEL
        FROM SANKHYA.ANDRE_IAGRO_SALDO_COMBUSTIVEL
        WHERE CODPROD IN ({placeholders})
    """
    binds_view = dict(binds_prod)
    if filtros.get('q'):
        sql_view += " AND UPPER(DESCRPROD) LIKE :q"
        binds_view['q'] = f"%{str(filtros['q']).upper()}%"

    # SELECT auxiliar pra trazer DESCRPROD/CODVOL de tanques sem movimentação
    # (a view não retorna linha pra produtos sem TGFITE). Sem isso, o card
    # aparece como "Produto N" no frontend.
    sql_prod = f"""
        SELECT CODPROD, DESCRPROD, CODVOL
        FROM TGFPRO
        WHERE CODPROD IN ({placeholders})
    """

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_view, binds_view)
        rows_view = {int(r[0]): r for r in cur.fetchall()}
        cur.execute(sql_prod, binds_prod)
        nomes_prod = {int(r[0]): (r[1] or '', r[2] or 'LT') for r in cur.fetchall()}

    # Garante 1 linha por tanque mapeado, mesmo sem registro na view (tanque
    # ainda sem movimentação aparece com saldo = SALDO_INICIAL_TANQUE).
    resultado = []
    for codprod, capacidade in CAPACIDADE_TANQUE.items():
        saldo_inicial = float(SALDO_INICIAL_TANQUE.get(codprod, 0))
        row = rows_view.get(codprod)
        nome_canonico, vol_canonico = nomes_prod.get(codprod, ('', 'LT'))
        if row:
            descrprod = row[1] or nome_canonico
            codvol    = row[2] or vol_canonico or 'LT'
            qtd_entrada_view = float(row[3] or 0)
            qtd_saida = float(row[4] or 0)
        else:
            # Tanque mapeado mas sem TGFITE — usa nome de TGFPRO + saldo inicial
            descrprod = nome_canonico
            codvol = vol_canonico or 'LT'
            qtd_entrada_view = 0.0
            qtd_saida = 0.0

        # IMPORTANTE: a view ANDRE_IAGRO_SALDO_COMBUSTIVEL usa
        # GREATEST(entrada - saida, 0). Quando o tanque só tem saldo inicial
        # (entrada_view=0) e tem saída, GREATEST força a 0 e somar saldo
        # inicial dá um saldo inflado. Recalculo aqui usando a saída literal.
        qtd_entrada_total = qtd_entrada_view + saldo_inicial
        qtd_disponivel = qtd_entrada_total - qtd_saida
        if qtd_disponivel < 0:
            qtd_disponivel = 0.0
        percentual = (qtd_disponivel / capacidade * 100.0) if capacidade > 0 else 0.0
        if percentual > 100:
            percentual = 100.0

        # Filtro de busca por descrição (aplicado em memória pra cobrir tanques
        # sem movimentação que vieram do dicionário, não da view)
        if filtros.get('q'):
            termo = str(filtros['q']).upper()
            if termo not in descrprod.upper():
                continue

        formato = FORMATO_TANQUE.get(codprod, 'CILINDRO_HORIZONTAL')
        resultado.append((
            codprod, descrprod, codvol,
            qtd_entrada_total, qtd_saida, qtd_disponivel,
            capacidade, saldo_inicial, round(percentual, 2),
            formato,
        ))

    # Ordena conforme ORDEM_TANQUE (CODPROD → posição). Tanques sem ordem
    # mapeada vão pro fim e desempatam por descrição.
    resultado.sort(key=lambda r: (ORDEM_TANQUE.get(r[0], 999), r[1]))
    return resultado


def consultar_veiculos_disponiveis(termo: str = None, somente_ativos: bool = True,
                                   tipo: str = None, limite: int = 50):
    """Lista veículos da TGFVEI com JOIN em TGFPAR pra trazer NOMEPARC.
    Filtros:
      - termo: busca em PLACA, MARCAMODELO, ESPECIETIPO (UPPER LIKE)
      - somente_ativos: filtra ATIVO='S'
      - tipo: 'INTERNA_FROTA' | 'INTERNA_MAQUINARIO' | 'EXTERNA_FRETE'
              (mapeado para TGFVEI.PROPRIO — INTERNA_* exige PROPRIO='S';
               EXTERNA_FRETE exige PROPRIO='N')
    Retorna: (CODVEICULO, PLACA, MARCAMODELO, ESPECIETIPO, PROPRIO,
              COMBUSTIVEL, CODPARC, NOMEPARC, CODCENCUS, CODFUNC,
              CODMOTORISTA, ATIVO).
    """
    sql = """
        SELECT v.CODVEICULO, v.PLACA, v.MARCAMODELO, v.ESPECIETIPO,
               v.PROPRIO, v.COMBUSTIVEL, v.CODPARC, p.NOMEPARC,
               v.CODCENCUS, v.CODFUNC, v.CODMOTORISTA, v.ATIVO
        FROM TGFVEI v
        LEFT JOIN TGFPAR p ON p.CODPARC = v.CODPARC
        WHERE 1 = 1
    """
    binds = {}
    if somente_ativos:
        sql += " AND v.ATIVO = 'S'"
    if tipo == 'EXTERNA_FRETE':
        sql += " AND v.PROPRIO = 'N'"
    elif tipo in ('INTERNA_FROTA', 'INTERNA_MAQUINARIO'):
        sql += " AND v.PROPRIO = 'S'"
    if termo:
        sql += (" AND (UPPER(v.PLACA) LIKE :q"
                "      OR UPPER(NVL(v.MARCAMODELO, '')) LIKE :q"
                "      OR UPPER(NVL(v.ESPECIETIPO, '')) LIKE :q)")
        binds['q'] = f"%{str(termo).upper()}%"
    sql += " ORDER BY v.PLACA"
    sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :lim"
    binds['lim'] = max(1, int(limite))

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        return cur.fetchall()


def listar_requisicoes_combustivel(filtros: dict = None, limite: int = 50, offset: int = 0):
    """Lista requisições de combustível (TOP 26 com linha em
    AD_REQUISICAO_COMBUSTIVEL). Filtros:
      - codemp: int
      - codveiculo: int
      - tipo: str ('INTERNA_FROTA' | 'INTERNA_MAQUINARIO' | 'EXTERNA_FRETE')
      - codparc: int
      - status: 'aberto' (STATUSNOTA NULL ou diferente de L) | 'confirmado' (L) | None (todos)
      - date_start / date_end: 'YYYY-MM-DD'

    Retorna lista de tuplas:
      (NUNOTA, NUMNOTA, CODEMP, CODPARC, NOMEPARC, DTNEG, STATUSNOTA,
       VLRNOTA, QTDVOL, AD_ID, AD_TIPO, AD_CODVEICULO, AD_PLACA,
       AD_MARCAMODELO, AD_HODOMETRO_KM, AD_HORIMETRO_H,
       AD_DOC_FRETE_REF, AD_OBSERVACAO, AD_NOMEUSU, AD_CRIADO_EM,
       CODPROD, DESCRPROD, CODVOL, QTDNEG_TOTAL)
    Paginação compatível com Oracle 11g (ROW_NUMBER + BETWEEN).
    """
    filtros = filtros or {}
    where = ["c.CODTIPOPER = 53", "EXISTS (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL r WHERE r.NUNOTA = c.NUNOTA)"]
    binds = {}

    if filtros.get('codemp'):
        where.append("c.CODEMP = :codemp")
        binds['codemp'] = int(filtros['codemp'])
    if filtros.get('codveiculo'):
        where.append("EXISTS (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL r2 WHERE r2.NUNOTA = c.NUNOTA AND r2.CODVEICULO = :codvei)")
        binds['codvei'] = int(filtros['codveiculo'])
    if filtros.get('tipo'):
        where.append("EXISTS (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL r3 WHERE r3.NUNOTA = c.NUNOTA AND r3.TIPO = :tipo)")
        binds['tipo'] = str(filtros['tipo']).upper()
    if filtros.get('codparc'):
        where.append("c.CODPARC = :codparc")
        binds['codparc'] = int(filtros['codparc'])
    if filtros.get('status') == 'aberto':
        where.append("(c.STATUSNOTA IS NULL OR c.STATUSNOTA NOT IN ('L', 'E'))")
    elif filtros.get('status') == 'confirmado':
        where.append("c.STATUSNOTA = 'L'")
    else:
        where.append("c.STATUSNOTA <> 'E'")
    if filtros.get('date_start') and filtros.get('date_end'):
        where.append("TRUNC(c.DTNEG) BETWEEN TO_DATE(:dstart, 'YYYY-MM-DD') AND TO_DATE(:dend, 'YYYY-MM-DD')")
        binds['dstart'] = filtros['date_start']
        binds['dend'] = filtros['date_end']

    sql_base = f"""
        SELECT
          c.NUNOTA, c.NUMNOTA, c.CODEMP, c.CODPARC,
          p.NOMEPARC, c.DTNEG, c.STATUSNOTA, c.VLRNOTA, c.QTDVOL,
          r.ID, r.TIPO, r.CODVEICULO, v.PLACA, v.MARCAMODELO,
          r.HODOMETRO_KM, r.HORIMETRO_H, r.DOC_FRETE_REF, r.OBSERVACAO,
          r.NOMEUSU, r.CRIADO_EM,
          (SELECT MIN(i.CODPROD)
             FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA)            AS CODPROD,
          (SELECT MIN(pr.DESCRPROD)
             FROM TGFITE i JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
             WHERE i.NUNOTA = c.NUNOTA)                          AS DESCRPROD,
          (SELECT MIN(i.CODVOL)
             FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA)            AS CODVOL,
          (SELECT NVL(SUM(i.QTDNEG), 0)
             FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA)            AS QTDNEG_TOTAL
        FROM TGFCAB c
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        LEFT JOIN AD_REQUISICAO_COMBUSTIVEL r ON r.NUNOTA = c.NUNOTA
        LEFT JOIN TGFVEI v ON v.CODVEICULO = r.CODVEICULO
        WHERE {' AND '.join(where)}
    """
    sql_paginado = f"""
        SELECT * FROM (
          SELECT t.*, ROW_NUMBER() OVER (ORDER BY t.DTNEG DESC, t.NUNOTA DESC) AS RN
          FROM ({sql_base}) t
        ) WHERE RN BETWEEN :ini AND :fim
    """
    inicio = int(offset) + 1
    fim = int(offset) + int(limite)
    binds['ini'] = inicio
    binds['fim'] = fim

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_paginado, binds)
        return cur.fetchall()


def obter_requisicao_combustivel(nunota: int):
    """Carrega uma requisição específica + itens. Retorna dict com:
       {cabecalho: {...}, itens: [{...}, ...], requisicao: {...}}
       ou None se não existir requisição IAgro.
    """
    nunota = int(nunota)
    sql_cab = """
        SELECT c.NUNOTA, c.NUMNOTA, c.CODEMP, c.CODPARC, p.NOMEPARC,
               c.CODTIPOPER, c.CODNAT, c.CODCENCUS, c.STATUSNOTA,
               c.DTNEG, c.DTMOV, c.VLRNOTA, c.QTDVOL, c.OBSERVACAO, c.CODUSU,
               r.ID, r.TIPO, r.CODVEICULO, v.PLACA, v.MARCAMODELO, v.ESPECIETIPO,
               v.PROPRIO, v.COMBUSTIVEL, v.CODCENCUS AS VEI_CODCENCUS,
               r.HODOMETRO_KM, r.HORIMETRO_H, r.DOC_FRETE_REF,
               r.OBSERVACAO, r.CODUSU, r.NOMEUSU, r.CRIADO_EM,
               r.CODPARC AS REQ_CODPARC, r.CATEGORIA, r.NUFIN_GERADO
        FROM TGFCAB c
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        LEFT JOIN AD_REQUISICAO_COMBUSTIVEL r ON r.NUNOTA = c.NUNOTA
        LEFT JOIN TGFVEI v ON v.CODVEICULO = r.CODVEICULO
        WHERE c.NUNOTA = :nun
    """
    sql_itens = """
        SELECT i.SEQUENCIA, i.CODPROD, pr.DESCRPROD, i.CODVOL,
               i.QTDNEG, i.VLRUNIT, i.VLRTOT, pr.CODGRUPOPROD
        FROM TGFITE i
        LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
        WHERE i.NUNOTA = :nun
        ORDER BY i.SEQUENCIA
    """
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_cab, nun=nunota)
        row = cur.fetchone()
        if not row:
            return None
        cab = {
            'NUNOTA': int(row[0]),
            'NUMNOTA': int(row[1]) if row[1] is not None else None,
            'CODEMP': int(row[2]) if row[2] is not None else None,
            'CODPARC': int(row[3]) if row[3] is not None else None,
            'NOMEPARC': row[4] or '',
            'CODTIPOPER': int(row[5]) if row[5] is not None else None,
            'CODNAT': int(row[6]) if row[6] is not None else None,
            'CODCENCUS': int(row[7]) if row[7] is not None else None,
            'STATUSNOTA': row[8],
            'DTNEG': row[9],
            'DTMOV': row[10],
            'VLRNOTA': float(row[11]) if row[11] is not None else 0.0,
            'QTDVOL': float(row[12]) if row[12] is not None else 0.0,
            'OBSERVACAO': row[13] or '',
            'CODUSU': int(row[14]) if row[14] is not None else None,
        }
        req = None
        if row[15] is not None:
            req = {
                'ID': int(row[15]),
                'TIPO': row[16],
                'CODVEICULO': int(row[17]) if row[17] is not None else None,
                'PLACA': row[18] or '',
                'MARCAMODELO': row[19] or '',
                'ESPECIETIPO': row[20] or '',
                'PROPRIO': row[21],
                'COMBUSTIVEL': row[22],
                'VEI_CODCENCUS': int(row[23]) if row[23] is not None else None,
                'HODOMETRO_KM': float(row[24]) if row[24] is not None else None,
                'HORIMETRO_H':  float(row[25]) if row[25] is not None else None,
                'DOC_FRETE_REF': row[26] or '',
                'OBSERVACAO': row[27] or '',
                'CODUSU': int(row[28]) if row[28] is not None else None,
                'NOMEUSU': row[29] or '',
                'CRIADO_EM': row[30],
                'CODPARC': int(row[31]) if row[31] is not None else None,
                'CATEGORIA': row[32] or 'COMBUSTIVEL',
                'NUFIN_GERADO': int(row[33]) if row[33] is not None else None,
            }
        cur.execute(sql_itens, nun=nunota)
        itens = []
        for r in cur.fetchall():
            itens.append({
                'SEQUENCIA': int(r[0]),
                'CODPROD': int(r[1]),
                'DESCRPROD': r[2] or '',
                'CODVOL': r[3] or '',
                'QTDNEG': float(r[4]) if r[4] is not None else 0.0,
                'VLRUNIT': float(r[5]) if r[5] is not None else 0.0,
                'VLRTOT': float(r[6]) if r[6] is not None else 0.0,
                'CODGRUPOPROD': int(r[7]) if r[7] is not None else None,
            })
        return {'cabecalho': cab, 'itens': itens, 'requisicao': req}


def consultar_consumo_por_veiculo(codveiculo: int, date_start: str = None, date_end: str = None):
    """Relatório de consumo por veículo (Mai/2026).

    Lista todas as requisições (TOP 26 com STATUSNOTA <> 'E') do veículo no
    período, com hodômetro/horímetro de cada uma, ordenadas por data. Calcula
    o consumo entre abastecimentos consecutivos:
      - km/L  → (hodometro_atual - hodometro_anterior) / qtd_anterior
      - L/h   → qtd_anterior / (horimetro_atual - horimetro_anterior)

    A qtd do abastecimento ANTERIOR é o combustível consumido pra rodar até
    o ATUAL — daí a métrica vem amarrada ao "anterior".

    Args:
      codveiculo: int — TGFVEI.CODVEICULO
      date_start: 'YYYY-MM-DD' ou None (default: últimos 30 dias)
      date_end:   'YYYY-MM-DD' ou None (default: hoje)

    Retorna:
      {
        'veiculo': {'codveiculo', 'placa', 'marcamodelo', 'especietipo',
                    'codparc', 'nomeparc', 'proprio'},
        'periodo': {'inicio': 'YYYY-MM-DD', 'fim': 'YYYY-MM-DD'},
        'abastecimentos': [
            {'nunota', 'numnota', 'dtneg', 'statusnota', 'tipo',
             'codprod', 'descrprod', 'qtd', 'codvol', 'vlrtot',
             'hodometro_km', 'horimetro_h',
             'km_percorridos', 'h_trabalhadas',
             'consumo_kmlt', 'consumo_lth',
             'doc_frete_ref', 'observacao'}, ...
        ],
        'totais': {
            'qtd_abastecimentos', 'total_litros', 'total_vlr',
            'km_total', 'h_total',
            'consumo_medio_kmlt', 'consumo_medio_lth',
            'periodo_dias',
        }
      }
    """
    codveiculo = int(codveiculo)

    # Períodos default
    from datetime import date as _date_class, timedelta as _td
    hoje = _date_class.today()
    if not date_end:
        date_end = hoje.strftime('%Y-%m-%d')
    if not date_start:
        date_start = (hoje - _td(days=30)).strftime('%Y-%m-%d')

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()

        # 1) Dados do veículo
        cur.execute("""
            SELECT v.CODVEICULO, v.PLACA, v.MARCAMODELO, v.ESPECIETIPO,
                   v.CODPARC, p.NOMEPARC, v.PROPRIO
            FROM TGFVEI v
            LEFT JOIN TGFPAR p ON p.CODPARC = v.CODPARC
            WHERE v.CODVEICULO = :cv
        """, cv=codveiculo)
        row_vei = cur.fetchone()
        if not row_vei:
            return None
        veiculo = {
            'codveiculo': int(row_vei[0]),
            'placa': row_vei[1] or '',
            'marcamodelo': row_vei[2] or '',
            'especietipo': row_vei[3] or '',
            'codparc': int(row_vei[4]) if row_vei[4] is not None else None,
            'nomeparc': row_vei[5] or '',
            'proprio': row_vei[6] or '',
        }

        # 2) Abastecimentos no período (TOP 26 + AD_REQ filtrados por veículo).
        # JOIN com TGFITE pra trazer cada item (1 linha por item — uma req
        # normalmente tem 1 item, mas suporta multi-item).
        cur.execute("""
            SELECT c.NUNOTA, c.NUMNOTA, c.DTNEG, c.STATUSNOTA, c.VLRNOTA,
                   r.TIPO, r.HODOMETRO_KM, r.HORIMETRO_H,
                   r.DOC_FRETE_REF, r.OBSERVACAO,
                   i.CODPROD, pr.DESCRPROD, i.QTDNEG, i.CODVOL, i.VLRTOT
            FROM TGFCAB c
            JOIN AD_REQUISICAO_COMBUSTIVEL r ON r.NUNOTA = c.NUNOTA
            JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
            JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
            WHERE c.CODTIPOPER = 53
              AND c.STATUSNOTA <> 'E'
              AND r.CODVEICULO = :cv
              AND TRUNC(c.DTNEG) BETWEEN TO_DATE(:ds, 'YYYY-MM-DD')
                                     AND TO_DATE(:de, 'YYYY-MM-DD')
            ORDER BY c.DTNEG ASC, c.NUNOTA ASC, i.SEQUENCIA ASC
        """, cv=codveiculo, ds=date_start, de=date_end)

        rows = cur.fetchall()

    # Monta abastecimentos + calcula consumo entre consecutivos
    abastecimentos = []
    hod_anterior = None
    hor_anterior = None
    qtd_anterior = None

    total_litros = 0.0
    total_vlr = 0.0
    km_total = 0.0
    h_total = 0.0
    soma_kmlt = 0.0
    n_kmlt = 0
    soma_lth = 0.0
    n_lth = 0

    for r in rows:
        nunota   = int(r[0])
        numnota  = int(r[1]) if r[1] is not None else None
        dtneg    = r[2]
        status   = r[3]
        vlrnota  = float(r[4] or 0)
        tipo_req = r[5]
        hod      = float(r[6]) if r[6] is not None else None
        hor      = float(r[7]) if r[7] is not None else None
        doc      = r[8] or ''
        obs      = r[9] or ''
        codprod  = int(r[10]) if r[10] is not None else None
        descrp   = r[11] or ''
        qtd      = float(r[12] or 0)
        codvol   = r[13] or 'LT'
        vlrtot   = float(r[14] or 0)

        km_perc = None
        h_trab = None
        consumo_kmlt = None
        consumo_lth = None

        # Consumo entre o ATUAL e o ANTERIOR. A qtd ANTERIOR foi consumida
        # pra rodar até aqui.
        if qtd_anterior and qtd_anterior > 0:
            if hod is not None and hod_anterior is not None and hod > hod_anterior:
                km_perc = hod - hod_anterior
                consumo_kmlt = km_perc / qtd_anterior
                km_total += km_perc
                soma_kmlt += consumo_kmlt
                n_kmlt += 1
            if hor is not None and hor_anterior is not None and hor > hor_anterior:
                h_trab = hor - hor_anterior
                if h_trab > 0:
                    consumo_lth = qtd_anterior / h_trab
                    h_total += h_trab
                    soma_lth += consumo_lth
                    n_lth += 1

        abastecimentos.append({
            'nunota': nunota,
            'numnota': numnota,
            'dtneg': dtneg.strftime('%Y-%m-%d') if dtneg else None,
            'statusnota': status,
            'tipo': tipo_req,
            'codprod': codprod,
            'descrprod': descrp,
            'qtd': qtd,
            'codvol': codvol,
            'vlrtot': vlrtot,
            'vlrnota': vlrnota,
            'hodometro_km': hod,
            'horimetro_h': hor,
            'km_percorridos': km_perc,
            'h_trabalhadas': h_trab,
            'consumo_kmlt': consumo_kmlt,
            'consumo_lth': consumo_lth,
            'doc_frete_ref': doc,
            'observacao': obs,
        })

        total_litros += qtd
        total_vlr += vlrtot
        # Atualiza referência pro próximo
        if hod is not None: hod_anterior = hod
        if hor is not None: hor_anterior = hor
        qtd_anterior = qtd

    from datetime import datetime as _dt
    try:
        dias = (_dt.strptime(date_end, '%Y-%m-%d')
              - _dt.strptime(date_start, '%Y-%m-%d')).days + 1
    except Exception:
        dias = None

    totais = {
        'qtd_abastecimentos': len(abastecimentos),
        'total_litros': round(total_litros, 2),
        'total_vlr': round(total_vlr, 2),
        'km_total': round(km_total, 2),
        'h_total': round(h_total, 2),
        'consumo_medio_kmlt': round(soma_kmlt / n_kmlt, 2) if n_kmlt else None,
        'consumo_medio_lth':  round(soma_lth  / n_lth,  2) if n_lth  else None,
        'periodo_dias': dias,
    }

    return {
        'veiculo': veiculo,
        'periodo': {'inicio': date_start, 'fim': date_end},
        'abastecimentos': abastecimentos,
        'totais': totais,
    }


def consultar_produtos_combustivel(termo: str = None, limite: int = 30):
    """Typeahead de produtos de combustível (filtra CODGRUPOPROD=11).
    Retorna: (CODPROD, DESCRPROD, CODVOL).
    """
    sql = """
        SELECT CODPROD, DESCRPROD, CODVOL
        FROM TGFPRO
        WHERE CODGRUPOPROD = :grupo
          AND ATIVO = 'S'
    """
    binds = {'grupo': CODGRUPOPROD_COMBUSTIVEL}
    if termo:
        sql += " AND (UPPER(DESCRPROD) LIKE :q OR TO_CHAR(CODPROD) LIKE :q)"
        binds['q'] = f"%{str(termo).upper()}%"
    sql += " ORDER BY DESCRPROD"
    sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :lim"
    binds['lim'] = max(1, int(limite))
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds)
        return cur.fetchall()


def listar_movimentacoes_combustivel(filtros: dict = None, limite: int = 100, offset: int = 0):
    """Lista unificada de movimentações: entradas (TOP 10 CODNAT=30070200) +
    saídas (TOP 26 com AD_REQUISICAO_COMBUSTIVEL). 1 linha por item da TGFITE
    — se uma NUNOTA tem 2 produtos, vira 2 linhas (corrige bug Mai/2026 onde
    notas multi-item apareciam com nome do primeiro produto + soma de todos).

    Filtros:
      codemp, codveiculo, tipo (INTERNA_FROTA|INTERNA_MAQUINARIO|EXTERNA_FRETE),
      codparc, status (aberto|confirmado),
      date_start / date_end ('YYYY-MM-DD'),
      mov ('ENTRADA' | 'REQUISICAO' | None) — filtra movimento específico.

    Retorna tuplas de 24 colunas:
      (TIPO_MOVIMENTO, NUNOTA, NUMNOTA, CODEMP, CODPARC, NOMEPARC,
       DTNEG, STATUSNOTA, VLRNOTA, QTDVOL,
       REQ_ID, REQ_TIPO, REQ_CODVEICULO, REQ_PLACA, REQ_MARCAMODELO,
       REQ_HODOMETRO_KM, REQ_HORIMETRO_H, REQ_DOC_FRETE_REF,
       SEQUENCIA, CODPROD, DESCRPROD, CODVOL, QTDNEG_ITEM, VLRTOT_ITEM)

    Paginação compatível Oracle 11g.
    """
    filtros = filtros or {}
    binds = {}

    # WHERE comum (data, codemp, status)
    where_comum = ["c.CODTIPOPER IN (10, 53)"]
    if filtros.get('codemp'):
        where_comum.append("c.CODEMP = :codemp")
        binds['codemp'] = int(filtros['codemp'])
    if filtros.get('codparc'):
        where_comum.append("c.CODPARC = :codparc")
        binds['codparc'] = int(filtros['codparc'])
    if filtros.get('status') == 'aberto':
        where_comum.append("(c.STATUSNOTA IS NULL OR c.STATUSNOTA NOT IN ('L', 'E'))")
    elif filtros.get('status') == 'confirmado':
        where_comum.append("c.STATUSNOTA = 'L'")
    else:
        where_comum.append("c.STATUSNOTA <> 'E'")
    if filtros.get('date_start') and filtros.get('date_end'):
        where_comum.append(
            "TRUNC(c.DTNEG) BETWEEN TO_DATE(:dstart, 'YYYY-MM-DD') AND TO_DATE(:dend, 'YYYY-MM-DD')")
        binds['dstart'] = filtros['date_start']
        binds['dend'] = filtros['date_end']

    # Discriminador: TOP 10 (entrada com CODGRUPOPROD=11) | TOP 26 (requisição com AD_REQ)
    where_entrada = list(where_comum) + [
        "c.CODTIPOPER = 10",
        ("EXISTS (SELECT 1 FROM TGFITE i JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD "
         "WHERE i.NUNOTA = c.NUNOTA AND pr.CODGRUPOPROD = :grupo_e)"),
    ]
    where_requisicao = list(where_comum) + [
        "c.CODTIPOPER = 53",
        "EXISTS (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL r WHERE r.NUNOTA = c.NUNOTA)",
    ]
    binds['grupo_e'] = CODGRUPOPROD_COMBUSTIVEL

    # Filtros específicos de requisição
    if filtros.get('codveiculo'):
        where_requisicao.append(
            "EXISTS (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL r2 "
            "WHERE r2.NUNOTA = c.NUNOTA AND r2.CODVEICULO = :codvei)")
        binds['codvei'] = int(filtros['codveiculo'])
    if filtros.get('tipo'):
        where_requisicao.append(
            "EXISTS (SELECT 1 FROM AD_REQUISICAO_COMBUSTIVEL r3 "
            "WHERE r3.NUNOTA = c.NUNOTA AND r3.TIPO = :tipo)")
        binds['tipo'] = str(filtros['tipo']).upper()

    mov = (filtros.get('mov') or '').upper().strip()

    # Mai/2026 (2026-05-12): JOIN com TGFITE em vez de subquery MIN/SUM.
    # Cada item vira 1 linha — se a NUNOTA tem 2 produtos, a listagem mostra 2
    # linhas com a mesma NUNOTA (corrige bug onde DIESEL S10 aparecia com qtd
    # somada de S10 + S500). Filtro CODGRUPOPROD=:grupo_i garante que linhas
    # de outros grupos da mesma nota não aparecem.
    base_select_entrada = f"""
        SELECT
          'ENTRADA'                              AS TIPO_MOVIMENTO,
          c.NUNOTA, c.NUMNOTA, c.CODEMP, c.CODPARC,
          p.NOMEPARC, c.DTNEG, c.STATUSNOTA, c.VLRNOTA, c.QTDVOL,
          NULL                                   AS REQ_ID,
          NULL                                   AS REQ_TIPO,
          NULL                                   AS REQ_CODVEICULO,
          NULL                                   AS REQ_PLACA,
          NULL                                   AS REQ_MARCAMODELO,
          NULL                                   AS REQ_HODOMETRO_KM,
          NULL                                   AS REQ_HORIMETRO_H,
          NULL                                   AS REQ_DOC_FRETE_REF,
          i.SEQUENCIA                            AS SEQUENCIA,
          i.CODPROD, pr.DESCRPROD, i.CODVOL, i.QTDNEG, i.VLRTOT
        FROM TGFCAB c
        JOIN TGFITE i  ON i.NUNOTA = c.NUNOTA
        JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD AND pr.CODGRUPOPROD = :grupo_i
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        WHERE {' AND '.join(where_entrada)}
    """
    base_select_requisicao = f"""
        SELECT
          'REQUISICAO'                           AS TIPO_MOVIMENTO,
          c.NUNOTA, c.NUMNOTA, c.CODEMP, c.CODPARC,
          p.NOMEPARC, c.DTNEG, c.STATUSNOTA, c.VLRNOTA, c.QTDVOL,
          r.ID                                   AS REQ_ID,
          r.TIPO                                 AS REQ_TIPO,
          r.CODVEICULO                           AS REQ_CODVEICULO,
          v.PLACA                                AS REQ_PLACA,
          v.MARCAMODELO                          AS REQ_MARCAMODELO,
          r.HODOMETRO_KM                         AS REQ_HODOMETRO_KM,
          r.HORIMETRO_H                          AS REQ_HORIMETRO_H,
          r.DOC_FRETE_REF                        AS REQ_DOC_FRETE_REF,
          i.SEQUENCIA                            AS SEQUENCIA,
          i.CODPROD, pr.DESCRPROD, i.CODVOL, i.QTDNEG, i.VLRTOT
        FROM TGFCAB c
        JOIN TGFITE i  ON i.NUNOTA = c.NUNOTA
        JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD AND pr.CODGRUPOPROD = :grupo_i
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        LEFT JOIN AD_REQUISICAO_COMBUSTIVEL r ON r.NUNOTA = c.NUNOTA
        LEFT JOIN TGFVEI v ON v.CODVEICULO = r.CODVEICULO
        WHERE {' AND '.join(where_requisicao)}
    """
    binds['grupo_i'] = CODGRUPOPROD_COMBUSTIVEL

    if mov == 'ENTRADA':
        sql_union = base_select_entrada
    elif mov == 'REQUISICAO':
        sql_union = base_select_requisicao
    else:
        sql_union = f"{base_select_entrada}\nUNION ALL\n{base_select_requisicao}"

    sql_paginado = f"""
        SELECT * FROM (
          SELECT t.*, ROW_NUMBER() OVER (
                        ORDER BY t.DTNEG DESC, t.NUNOTA DESC, t.SEQUENCIA ASC
                      ) AS RN
          FROM ({sql_union}) t
        ) WHERE RN BETWEEN :ini AND :fim
    """
    binds['ini'] = int(offset) + 1
    binds['fim'] = int(offset) + int(limite)

    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_paginado, binds)
        return cur.fetchall()


# =============================================================================
# MÓDULO CONTROLE DE COMBUSTÍVEL — Funções de ESCRITA (Categoria B aprovada Mai/2026)
# B2: criar_requisicao_combustivel_banco — TOP 26 STATUSNOTA NULL + AD_REQUISICAO_COMBUSTIVEL
# B3: criar_entrada_combustivel_banco    — TOP 10 STATUSNOTA='L' + TGFITE + TGFFIN
# =============================================================================


def _parse_data_iagro(s, default=None):
    """Parser tolerante: aceita date, datetime, 'YYYY-MM-DD' ou 'DD/MM/YYYY'.
    Retorna `date` (sem hora). Se inválido, devolve `default` (ou date.today())."""
    if s is None or s == '':
        return default if default is not None else _date.today()
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, _date):
        return s
    s = str(s).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return default if default is not None else _date.today()


def criar_requisicao_combustivel_banco(dados: dict, codusu: int, nomeusu: str = '') -> dict:
    """B2 — Cria requisição de combustível (TOP 26 STATUSNOTA NULL em aberto)
    + linha em AD_REQUISICAO_COMBUSTIVEL com metadata IAgro.

    Atômico via with obter_conexao_oracle(). Valida saldo na view
    ANDRE_IAGRO_SALDO_COMBUSTIVEL antes de gravar. Trava cruzada TIPO ↔
    TGFVEI.PROPRIO. CODAGREGACAO=NULL no TGFITE (segregação total da
    Classificação).

    Payload (`dados`):
      codveiculo:    int (obrigatório)
      codprod:       int (obrigatório — CODGRUPOPROD deve ser 200400)
      qtd:           float (litros, > 0)
      tipo:          'INTERNA_FROTA' | 'INTERNA_MAQUINARIO' | 'EXTERNA_FRETE'
      codcencus:     int (obrigatório)
      vlrunit:       float (opcional)
      hodometro_km:  float — obrigatório se tipo=INTERNA_FROTA;
                            opcional se tipo=INTERNA_MAQUINARIO;
                            ignorado em EXTERNA_FRETE
      horimetro_h:   float — idem hodometro_km
      doc_frete_ref: str (obrigatório se tipo=EXTERNA_FRETE)
      observacao:    str (opcional)

    Retorno:
      {'ok': True,  'nunota': int, 'requisicao_id': int}
      {'ok': False, 'error': str}
    """
    # 1. Validações
    erros = []
    codveiculo = int(dados.get('codveiculo') or 0)
    codprod    = int(dados.get('codprod') or 0)
    qtd        = float(dados.get('qtd') or 0)
    tipo       = (dados.get('tipo') or '').upper().strip()
    codcencus  = int(dados.get('codcencus') or 0)

    if not codveiculo: erros.append('codveiculo obrigatório')
    if not codprod:    erros.append('codprod obrigatório')
    if qtd <= 0:       erros.append('qtd deve ser > 0')
    if tipo not in ('INTERNA_FROTA', 'INTERNA_MAQUINARIO', 'EXTERNA_FRETE'):
        erros.append('tipo inválido')
    if not codcencus:  erros.append('codcencus obrigatório')

    doc_frete = (dados.get('doc_frete_ref') or '').strip()
    if tipo == 'EXTERNA_FRETE' and not doc_frete:
        erros.append('doc_frete_ref obrigatório para EXTERNA_FRETE')

    # CODNAT parametrizável (Mai/2026); default mantém 30070200 (combustível).
    codnat = int(dados.get('codnat') or 30070200)
    # CODTIPVENDA parametrizável (Mai/2026); default 11 (compra de combustível).
    codtipvenda = int(dados.get('codtipvenda') or 11)

    def _parse_medidor(raw):
        if raw in (None, '', 0, 0.0):
            return None
        try:
            v = float(raw)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return False  # marca erro de parse

    hodometro_km = _parse_medidor(dados.get('hodometro_km'))
    horimetro_h  = _parse_medidor(dados.get('horimetro_h'))
    if hodometro_km is False: erros.append('hodometro_km inválido')
    if horimetro_h  is False: erros.append('horimetro_h inválido')

    # Hodômetro/horímetro são opcionais em TODOS os tipos (Mai/2026) — operador
    # preenche quando tem informação confiável. Freteiro continua zerando porque
    # veículo terceiro não tem como rastrear km/h da nossa parte.
    if tipo == 'EXTERNA_FRETE':
        hodometro_km = None
        horimetro_h  = None

    if erros:
        return {'ok': False, 'error': ' · '.join(erros)}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 2. Veículo + trava PROPRIO ↔ TIPO
            cur.execute("""
                SELECT v.CODPARC, v.PROPRIO
                FROM TGFVEI v
                WHERE v.CODVEICULO = :cv AND v.ATIVO = 'S'
            """, cv=codveiculo)
            row_vei = cur.fetchone()
            if not row_vei:
                return {'ok': False, 'error': f'Veículo {codveiculo} não encontrado ou inativo.'}
            codparc_vei, proprio_vei = row_vei

            if tipo == 'EXTERNA_FRETE' and proprio_vei != 'N':
                return {'ok': False, 'error':
                    'Tipo EXTERNA_FRETE exige veículo de terceiro (TGFVEI.PROPRIO=N).'}
            if tipo in ('INTERNA_FROTA', 'INTERNA_MAQUINARIO') and proprio_vei != 'S':
                return {'ok': False, 'error':
                    'Tipo interno exige veículo próprio (TGFVEI.PROPRIO=S).'}

            # 3. Produto deve ser combustível (CODGRUPOPROD=11)
            cur.execute("""
                SELECT CODGRUPOPROD, DESCRPROD, CODVOL
                FROM TGFPRO WHERE CODPROD = :cp AND ATIVO = 'S'
            """, cp=codprod)
            row_prod = cur.fetchone()
            if not row_prod:
                return {'ok': False, 'error': f'Produto {codprod} não encontrado ou inativo.'}
            codgrupo, descrprod, codvol = row_prod
            if codgrupo != CODGRUPOPROD_COMBUSTIVEL:
                return {'ok': False, 'error':
                    f'Produto {codprod} ({descrprod}) não é combustível (grupo {codgrupo}).'}

            # 4. Validação de saldo (estoque único, sem segregação por CODEMP).
            # Soma SALDO_INICIAL_TANQUE ao saldo da view (saldo pré-existente
            # nos tanques antes do IAgro). Tanques sem mapping em
            # CAPACIDADE_TANQUE também são bloqueados — combustível só pode
            # sair de tanques sob controle do IAgro.
            if codprod not in CAPACIDADE_TANQUE:
                return {'ok': False, 'error':
                    f'Produto {codprod} ({descrprod}) não tem tanque mapeado no IAgro.'}
            cur.execute("""
                SELECT QTD_DISPONIVEL FROM SANKHYA.ANDRE_IAGRO_SALDO_COMBUSTIVEL
                WHERE CODPROD = :cp
            """, cp=codprod)
            row_saldo = cur.fetchone()
            disponivel_view = float(row_saldo[0]) if row_saldo and row_saldo[0] is not None else 0.0
            disponivel = disponivel_view + float(SALDO_INICIAL_TANQUE.get(codprod, 0))
            if qtd > disponivel:
                return {'ok': False, 'error':
                    f'Saldo insuficiente. Disponível: {disponivel:.2f} {codvol or "L"} · '
                    f'Solicitado: {qtd:.2f}. Lance entrada TOP 10 ou reduza a quantidade.'}

            # CODEMP da TGFCAB TOP 26 — apenas metadata escritural. Reusa a CODEMP
            # da entrada mais recente do produto (consistência) ou cai em default 1.
            cur.execute("""
                SELECT MAX(c.CODEMP)
                FROM TGFCAB c
                JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                WHERE c.CODTIPOPER = 10
                  AND c.STATUSNOTA <> 'E'
                  AND i.CODPROD = :cp
            """, cp=codprod)
            row_emp = cur.fetchone()
            codemp = int(row_emp[0]) if row_emp and row_emp[0] else 1

            # 6. INSERT TGFCAB TOP 53 - REQUISIÇÃO INTERNA (STATUSNOTA em aberto).
            # dtneg vem do operador (Mai/2026) — formato 'YYYY-MM-DD' (HTML5
            # input type=date). Default hoje quando não passado.
            hoje = _date.today()
            dtneg_payload = (dados.get('dtneg') or '').strip()
            if dtneg_payload:
                try:
                    _d = _date.fromisoformat(dtneg_payload)
                    dtneg_str = _d.strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    dtneg_str = hoje.strftime('%d/%m/%Y')
            else:
                dtneg_str = hoje.strftime('%d/%m/%Y')

            cab_resp = inserir_cabecalho_nota_banco({
                'CODEMP':       codemp,
                'CODPARC':      codparc_vei,
                'CODTIPOPER':   53,
                'CODNAT':       codnat,
                'CODCENCUS':    codcencus,
                'CODTIPVENDA':  codtipvenda,
                'DTNEG':        dtneg_str,
                'DTMOV':        dtneg_str,
                'OBSERVACAO':   (dados.get('observacao') or '')[:200] or None,
            }, conexao_existente=conn)
            if not cab_resp.get('ok'):
                return {'ok': False, 'error':
                    f'Falha ao criar cabeçalho TOP 26: {cab_resp.get("error", "desconhecido")}'}
            nunota = int(cab_resp['nunota'])

            # 7. INSERT TGFITE — CODAGREGACAO=NULL (segregação)
            vlrunit = float(dados.get('vlrunit') or 0)
            item_resp = inserir_item_nota_banco({
                'NUNOTA':       nunota,
                'CODPROD':      codprod,
                'QTDNEG':       qtd,
                'VLRUNIT':      vlrunit,
                'CODVOL':       codvol or 'L',
                'CODAGREGACAO': None,
            }, gerar_lote_auto=False, conexao_existente=conn)
            if not item_resp.get('ok'):
                return {'ok': False, 'error':
                    f'Falha ao criar item: {item_resp.get("error", "desconhecido")}'}

            recalcular_totais_nota_banco(nunota, conexao_existente=conn)

            # 8. INSERT AD_REQUISICAO_COMBUSTIVEL (B4 Mai/2026: hodometro + horimetro
            # separados; obrigatórios em frota própria, opcionais em maquinário, NULL
            # em freteiro)
            req_id_var = cur.var(int)
            cur.execute("""
                INSERT INTO AD_REQUISICAO_COMBUSTIVEL (
                    ID, NUNOTA, TIPO, CODVEICULO,
                    HODOMETRO_KM, HORIMETRO_H,
                    DOC_FRETE_REF, OBSERVACAO,
                    CODUSU, NOMEUSU
                ) VALUES (
                    SEQ_AD_REQUISICAO_COMBUSTIVEL.NEXTVAL, :nun, :tipo, :cv,
                    :hod_km, :hor_h,
                    :doc_frete, :obs,
                    :codusu, :nomeusu
                )
                RETURNING ID INTO :req_id
            """, {
                'nun': nunota, 'tipo': tipo, 'cv': codveiculo,
                'hod_km': hodometro_km,
                'hor_h':  horimetro_h,
                'doc_frete': doc_frete or None,
                'obs': (dados.get('observacao') or '')[:500] or None,
                'codusu': int(codusu), 'nomeusu': (nomeusu or '')[:60] or None,
                'req_id': req_id_var,
            })
            req_id = req_id_var.getvalue()
            if isinstance(req_id, list):
                req_id = req_id[0]

            conn.commit()
            logger.info("Requisição combustível criada: NUNOTA=%s req_id=%s veículo=%s qtd=%s",
                        nunota, req_id, codveiculo, qtd)
            return {'ok': True, 'nunota': nunota, 'requisicao_id': int(req_id)}

    except Exception as exc:
        logger.exception("Falha em criar_requisicao_combustivel_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


def editar_requisicao_combustivel_banco(nunota: int, dados: dict, codusu: int, nomeusu: str = '') -> dict:
    """B5 — Edita requisição existente em aberto (STATUSNOTA != 'L' e != 'E').
    Atualiza atomicamente:
      - AD_REQUISICAO_COMBUSTIVEL (metadata: tipo, veículo, medidores, doc, obs)
      - TGFCAB (CODPARC do novo veículo, CODCENCUS, OBSERVACAO)
      - TGFITE (CODPROD, QTDNEG, VLRUNIT, VLRTOT, CODVOL)
      - Recalcula totais via recalcular_totais_nota_banco

    Saldo é re-validado considerando a qtd antiga como "devolvida" antes de
    descontar a nova: saldo_efetivo = saldo_view + qtd_antiga; valida que
    saldo_efetivo >= qtd_nova.

    Payload mesmo do criar (todos opcionais — campos ausentes preservam valor
    atual). Campos suportados: tipo, codveiculo, codprod, qtd, vlrunit,
    hodometro_km, horimetro_h, codcencus, doc_frete_ref, observacao.

    Retorno:
      {'ok': True,  'nunota': int}
      {'ok': False, 'error': str}
    """
    nunota = int(nunota)
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Carrega estado atual da requisição (inclui CODPARC e NUFIN_GERADO
            # pra suportar EXTERNA_POSTO Mai/2026 + DHBAIXA do TGFFIN pra trava de
            # edição de externos já baixados)
            cur.execute("""
                SELECT c.STATUSNOTA, c.CODPARC, c.CODCENCUS,
                       r.TIPO, r.CODVEICULO, r.HODOMETRO_KM, r.HORIMETRO_H,
                       r.DOC_FRETE_REF, r.OBSERVACAO,
                       r.CODPARC, r.NUFIN_GERADO,
                       i.SEQUENCIA, i.CODPROD, i.QTDNEG, i.VLRUNIT, i.CODVOL
                FROM TGFCAB c
                JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                JOIN AD_REQUISICAO_COMBUSTIVEL r ON r.NUNOTA = c.NUNOTA
                WHERE c.NUNOTA = :n AND c.CODTIPOPER = 53
            """, n=nunota)
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Requisição {nunota} não encontrada.'}
            (statusnota, cab_codparc, cab_codcencus,
             req_tipo, req_codveiculo, req_hod, req_hor,
             req_doc, req_obs,
             req_codparc_atual, req_nufin_gerado,
             ite_seq, ite_codprod, ite_qtd, ite_vlu, ite_codvol) = row

            eh_externo_atual = (req_tipo == 'EXTERNA_POSTO')

            # Tipos internos: STATUSNOTA='L' bloqueia (Sankhya confirma).
            # EXTERNA_POSTO: nasce com STATUSNOTA='L' direto — não bloqueia por status,
            # mas bloqueia se TGFFIN já estiver baixado.
            if statusnota == 'L' and not eh_externo_atual:
                return {'ok': False, 'error':
                    'Requisição já confirmada no Sankhya — não pode ser editada pela IAgro. Estorne no ERP.'}
            if statusnota == 'E':
                return {'ok': False, 'error': 'Requisição já está excluída.'}
            if eh_externo_atual and req_nufin_gerado:
                cur.execute(
                    "SELECT DHBAIXA FROM TGFFIN WHERE NUFIN = :nf",
                    nf=int(req_nufin_gerado),
                )
                row_fin = cur.fetchone()
                if row_fin and row_fin[0] is not None:
                    return {'ok': False, 'error':
                        'Financeiro do abastecimento externo já está baixado — '
                        'estorne a baixa no Sankhya antes de editar.'}

            # 2. Resolve valores novos (preserva atual se ausente)
            tipo         = (dados.get('tipo') or req_tipo or '').upper().strip()
            codveiculo   = int(dados.get('codveiculo') or req_codveiculo)
            codprod      = int(dados.get('codprod') or ite_codprod)
            qtd_nova     = float(dados.get('qtd') if dados.get('qtd') is not None else ite_qtd)
            vlrunit      = float(dados.get('vlrunit') if dados.get('vlrunit') is not None
                                 else (ite_vlu or 0))
            codcencus    = int(dados.get('codcencus') or cab_codcencus)
            doc_frete    = (dados.get('doc_frete_ref') if 'doc_frete_ref' in dados else req_doc)
            observacao   = (dados.get('observacao') if 'observacao' in dados else req_obs)
            qtd_antiga   = float(ite_qtd or 0)
            # CODPARC do parceiro/posto (só usado em EXTERNA_POSTO)
            codparc_novo = int(dados.get('codparc') or req_codparc_atual or 0)

            eh_externo_novo = (tipo == 'EXTERNA_POSTO')

            erros = []
            if tipo not in ('INTERNA_FROTA', 'INTERNA_MAQUINARIO', 'EXTERNA_FRETE', 'EXTERNA_POSTO'):
                erros.append('tipo inválido')
            if qtd_nova <= 0:
                erros.append('qtd deve ser > 0')
            if not codcencus:
                erros.append('codcencus obrigatório')
            # Trava de mudança entre interno↔externo (semântica + financeiro
            # diferente): permitir só se for o mesmo "lado".
            if eh_externo_atual != eh_externo_novo:
                erros.append(
                    'Não é permitido alternar entre Interno e Externo na mesma '
                    'requisição. Exclua e crie um novo lançamento.'
                )
            # EXTERNA_POSTO exige CODPARC e vlrunit
            if eh_externo_novo:
                if not codparc_novo:
                    erros.append('codparc (posto) obrigatório para EXTERNA_POSTO')
                if vlrunit <= 0:
                    erros.append('vlrunit obrigatório para EXTERNA_POSTO')

            doc_frete_str = (doc_frete or '').strip() if doc_frete else ''
            if tipo == 'EXTERNA_FRETE' and not doc_frete_str:
                erros.append('doc_frete_ref obrigatório para EXTERNA_FRETE')

            # Mai/2026 (B8): NUMNOTA do operador (EXTERNA_POSTO). Texto recusa.
            numnota_raw = (dados.get('numnota') or '').strip() if dados.get('numnota') else ''
            numnota_operador = None
            if numnota_raw:
                try:
                    numnota_operador = int(numnota_raw)
                    if numnota_operador <= 0:
                        erros.append('numnota deve ser maior que zero')
                        numnota_operador = None
                except (ValueError, TypeError):
                    erros.append('Nº da nota fiscal deve ser apenas números '
                                 '(digite 12345, não NF 12345).')

            # Parse medidores
            def _parse_med(raw):
                if raw in (None, '', 0, 0.0): return None
                try:
                    v = float(raw)
                    return v if v > 0 else None
                except (TypeError, ValueError):
                    return False
            hod_raw = dados.get('hodometro_km') if 'hodometro_km' in dados else req_hod
            hor_raw = dados.get('horimetro_h')  if 'horimetro_h'  in dados else req_hor
            hod_km  = _parse_med(hod_raw)
            hor_h   = _parse_med(hor_raw)
            if hod_km is False: erros.append('hodometro_km inválido')
            if hor_h  is False: erros.append('horimetro_h inválido')

            # Mai/2026: hodômetro/horímetro opcionais em todos os tipos.
            # Freteiro continua zerando porque não rastreamos veículo terceiro.
            if tipo == 'EXTERNA_FRETE':
                hod_km = None
                hor_h  = None

            if erros:
                return {'ok': False, 'error': ' · '.join(erros)}

            # 3. Veículo + trava PROPRIO ↔ TIPO (só para internos+EXTERNA_FRETE).
            # EXTERNA_POSTO aceita qualquer veículo ativo (própria ou terceiro).
            cur.execute("""
                SELECT v.CODPARC, v.PROPRIO
                FROM TGFVEI v WHERE v.CODVEICULO = :cv AND v.ATIVO = 'S'
            """, cv=codveiculo)
            row_vei = cur.fetchone()
            if not row_vei:
                return {'ok': False, 'error': f'Veículo {codveiculo} não encontrado ou inativo.'}
            codparc_vei_novo, proprio_vei = row_vei
            if tipo == 'EXTERNA_FRETE' and proprio_vei != 'N':
                return {'ok': False, 'error':
                    'Tipo EXTERNA_FRETE exige veículo de terceiro (PROPRIO=N).'}
            if tipo in ('INTERNA_FROTA', 'INTERNA_MAQUINARIO') and proprio_vei != 'S':
                return {'ok': False, 'error':
                    'Tipo interno exige veículo próprio (PROPRIO=S).'}

            # 4. Produto deve ser combustível
            cur.execute("""
                SELECT CODGRUPOPROD, DESCRPROD, CODVOL
                FROM TGFPRO WHERE CODPROD = :cp AND ATIVO = 'S'
            """, cp=codprod)
            row_prod = cur.fetchone()
            if not row_prod:
                return {'ok': False, 'error': f'Produto {codprod} não encontrado ou inativo.'}
            codgrupo, descrprod, codvol = row_prod
            if codgrupo != CODGRUPOPROD_COMBUSTIVEL:
                return {'ok': False, 'error':
                    f'Produto {codprod} ({descrprod}) não é combustível.'}
            # Tanque mapeado: só relevante pra internos (que descontam saldo)
            if not eh_externo_novo and codprod not in CAPACIDADE_TANQUE:
                return {'ok': False, 'error':
                    f'Produto {codprod} ({descrprod}) não tem tanque mapeado no IAgro.'}

            # 5. Re-valida saldo SÓ pra internos. EXTERNA_POSTO não toca tanque.
            if not eh_externo_novo:
                cur.execute("""
                    SELECT QTD_DISPONIVEL FROM SANKHYA.ANDRE_IAGRO_SALDO_COMBUSTIVEL
                    WHERE CODPROD = :cp
                """, cp=codprod)
                r = cur.fetchone()
                disponivel_view = float(r[0]) if r and r[0] is not None else 0.0
                disponivel = disponivel_view + float(SALDO_INICIAL_TANQUE.get(codprod, 0))
                if codprod == int(ite_codprod):
                    # Mesmo produto — qtd antiga "devolve" pro saldo antes de checar
                    disponivel += qtd_antiga
                if qtd_nova > disponivel:
                    return {'ok': False, 'error':
                        f'Saldo insuficiente. Disponível: {disponivel:.2f} {codvol or "LT"} · '
                        f'Solicitado: {qtd_nova:.2f}.'}

            # 6. UPDATE AD_REQUISICAO_COMBUSTIVEL (CODPARC só preenchido pra EXTERNA_POSTO)
            cur.execute("""
                UPDATE AD_REQUISICAO_COMBUSTIVEL
                   SET TIPO = :tipo,
                       CODVEICULO = :cv,
                       CODPARC = :codparc,
                       HODOMETRO_KM = :hod,
                       HORIMETRO_H = :hor,
                       DOC_FRETE_REF = :doc,
                       OBSERVACAO = :obs
                 WHERE NUNOTA = :n
            """, {
                'n': nunota, 'tipo': tipo, 'cv': codveiculo,
                'codparc': codparc_novo if eh_externo_novo else None,
                'hod': hod_km, 'hor': hor_h,
                'doc': doc_frete_str or None,
                'obs': (observacao or '')[:500] or None,
            })

            # 7. UPDATE TGFCAB — CODPARC do cabeçalho:
            #    - interno: CODPARC do veículo (mantém comportamento original)
            #    - EXTERNA_POSTO: CODPARC do posto (informado)
            # dtneg opcional (Mai/2026): se passado, atualiza DTNEG/DTMOV junto.
            from datetime import date as _date_edit
            codparc_cab = codparc_novo if eh_externo_novo else codparc_vei_novo
            dtneg_payload = (dados.get('dtneg') or '').strip()
            dtneg_obj = None
            if dtneg_payload:
                try:
                    dtneg_obj = _date_edit.fromisoformat(dtneg_payload)
                except (ValueError, TypeError):
                    dtneg_obj = None

            if dtneg_obj:
                cur.execute("""
                    UPDATE TGFCAB
                       SET CODPARC = :parc, CODCENCUS = :cus, OBSERVACAO = :obs,
                           DTNEG   = :dtn, DTMOV    = :dtn
                     WHERE NUNOTA = :n AND CODTIPOPER = 53
                """, {
                    'n': nunota,
                    'parc': codparc_cab,
                    'cus': codcencus,
                    'obs': (observacao or '')[:200] or None,
                    'dtn': dtneg_obj,
                })
            else:
                cur.execute("""
                    UPDATE TGFCAB
                       SET CODPARC = :parc, CODCENCUS = :cus, OBSERVACAO = :obs
                     WHERE NUNOTA = :n AND CODTIPOPER = 53
                """, {
                    'n': nunota,
                    'parc': codparc_cab,
                    'cus': codcencus,
                    'obs': (observacao or '')[:200] or None,
                })

            # 8. UPDATE TGFITE — caminho duplo (Mai/2026 — 2026-05-13):
            #    - Single item (interno OU externo legado): UPDATE direto na SEQUENCIA carregada
            #    - Multi-itens externo (dados['itens']): UPDATE diferencial igual editar entrada
            itens_payload = dados.get('itens') if eh_externo_novo else None
            eh_multi = bool(itens_payload and isinstance(itens_payload, list))

            if eh_multi:
                # Valida cada item e captura DESCRPROD/CODVOL
                erros_itens = []
                itens_norm = []
                for idx_it, it in enumerate(itens_payload, start=1):
                    cp = int(it.get('codprod') or 0)
                    qt = float(it.get('qtd') or 0)
                    vu = float(it.get('vlrunit') or 0)
                    if not cp:  erros_itens.append(f'Item {idx_it}: codprod obrigatório')
                    if qt <= 0: erros_itens.append(f'Item {idx_it}: qtd > 0')
                    if vu <= 0: erros_itens.append(f'Item {idx_it}: vlrunit > 0')
                    itens_norm.append({'codprod': cp, 'qtd': qt, 'vlrunit': vu})
                if erros_itens:
                    return {'ok': False, 'error': ' · '.join(erros_itens)}

                descricoes_multi = {}
                for it in itens_norm:
                    cur.execute("""
                        SELECT CODGRUPOPROD, DESCRPROD, CODVOL
                        FROM TGFPRO WHERE CODPROD = :cp AND ATIVO = 'S'
                    """, cp=it['codprod'])
                    rp = cur.fetchone()
                    if not rp:
                        return {'ok': False, 'error': f"Produto {it['codprod']} não encontrado."}
                    if rp[0] != CODGRUPOPROD_COMBUSTIVEL:
                        return {'ok': False,
                                'error': f"Produto {it['codprod']} ({rp[1]}) não é combustível."}
                    descricoes_multi[it['codprod']] = (rp[1], rp[2] or 'LT')

                # SELECT seqs existentes pra fazer UPDATE diferencial
                cur.execute(
                    "SELECT SEQUENCIA FROM TGFITE WHERE NUNOTA = :n ORDER BY SEQUENCIA",
                    n=nunota,
                )
                seqs_existentes = [int(r[0]) for r in cur.fetchall()]

                vlrtot = 0.0
                for idx_it, it in enumerate(itens_norm):
                    cp = it['codprod']
                    _, codvol_i = descricoes_multi[cp]
                    vlt_it = round(it['qtd'] * it['vlrunit'], 4)
                    vlrtot += vlt_it

                    if idx_it < len(seqs_existentes):
                        # UPDATE no slot existente — reusa SEQUENCIA (evita PK violation)
                        cur.execute("""
                            UPDATE TGFITE
                               SET CODPROD = :cp, CODVOL = :cv,
                                   QTDNEG = :qt, VLRUNIT = :vlu, VLRTOT = :vlt,
                                   QTDCONFERIDA = :qt,
                                   CODAGREGACAO = NULL
                             WHERE NUNOTA = :n AND SEQUENCIA = :s
                        """, {
                            'n': nunota, 's': seqs_existentes[idx_it],
                            'cp': cp, 'cv': codvol_i,
                            'qt': it['qtd'], 'vlu': it['vlrunit'], 'vlt': vlt_it,
                        })
                    else:
                        # Item novo — reusa helper que preenche todas as colunas
                        # necessárias pros triggers Sankhya
                        item_resp = inserir_item_nota_banco({
                            'NUNOTA':       nunota,
                            'CODPROD':      cp,
                            'QTDNEG':       it['qtd'],
                            'VLRUNIT':      it['vlrunit'],
                            'CODVOL':       codvol_i,
                            'CODAGREGACAO': None,
                        }, gerar_lote_auto=False, conexao_existente=conn)
                        if not item_resp.get('ok'):
                            return {'ok': False,
                                    'error': f"Falha ao adicionar item CODPROD={cp}: {item_resp.get('error')}"}

                # DELETE seqs em excesso (lista nova menor que antiga)
                if len(itens_norm) < len(seqs_existentes):
                    seqs_remover = seqs_existentes[len(itens_norm):]
                    placeholders = ','.join(str(int(s)) for s in seqs_remover)
                    cur.execute(
                        f"DELETE FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA IN ({placeholders})",
                        n=nunota,
                    )

                vlrtot = round(vlrtot, 4)
            else:
                # Caminho antigo (single item — usado em internos e externo legado)
                vlrtot = round(qtd_nova * vlrunit, 4)
                cur.execute("""
                    UPDATE TGFITE
                       SET CODPROD = :cp, QTDNEG = :qtd, VLRUNIT = :vlu,
                           VLRTOT = :vlt, CODVOL = :cv
                     WHERE NUNOTA = :n AND SEQUENCIA = :seq
                """, {
                    'n': nunota, 'seq': int(ite_seq),
                    'cp': codprod, 'qtd': qtd_nova, 'vlu': vlrunit,
                    'vlt': vlrtot, 'cv': codvol or 'LT',
                })

            # 9. Recalcula totais do cabeçalho
            recalcular_totais_nota_banco(nunota, conexao_existente=conn)

            # 10. EXTERNA_POSTO: refletir mudanças no TGFFIN (CODPARC, VLRDESDOB,
            #     VLRBAIXA, HISTORICO, CODCENCUS) — sempre que NUFIN_GERADO existir
            #     e ainda não estiver baixado (DHBAIXA NULL já validado no início).
            #     Mai/2026 (B8): se operador alterou o NUMNOTA, propaga pra TGFCAB
            #     e TGFFIN do externo.
            if eh_externo_novo and req_nufin_gerado:
                # Propaga NUMNOTA do operador (B8) — se omitido no payload,
                # preserva o atual de TGFCAB.
                if numnota_operador:
                    cur.execute("""
                        UPDATE TGFCAB SET NUMNOTA = :nn
                         WHERE NUNOTA = :n AND CODTIPOPER = 53
                    """, nn=numnota_operador, n=nunota)
                    cur.execute("""
                        UPDATE TGFFIN SET NUMNOTA = :nn
                         WHERE NUFIN = :nf
                    """, nn=numnota_operador, nf=int(req_nufin_gerado))

                # TGFFIN sempre em aberto (DHBAIXA=NULL, VLRBAIXA=0, CODTIPOPERBAIXA=0).
                # Trigger TRG_UPT_TGFFIN bloqueia "A TOP da Baixa deve ser informada"
                # se VLRBAIXA > 0 sem CODTIPOPERBAIXA preenchida. Como IAgro não
                # cuida de TGFMBC (baixa real), nunca preenchemos VLRBAIXA aqui.
                # Operador baixa pelo Sankhya quando paga.
                cur.execute("""
                    UPDATE TGFFIN
                       SET CODPARC = :p,
                           CODCENCUS = :cus,
                           VLRDESDOB = :vlr,
                           VLRBAIXA  = 0,
                           HISTORICO = :hist,
                           DHMOV     = SYSDATE,
                           DTALTER   = SYSDATE
                     WHERE NUFIN = :nf
                """, {
                    'p': codparc_novo,
                    'cus': codcencus,
                    'vlr': vlrtot,
                    'hist': f'{descrprod}'[:255],
                    'nf': int(req_nufin_gerado),
                })

            conn.commit()
            logger.info("Requisição combustível NUNOTA=%s editada (codusu=%s)",
                        nunota, codusu)
            return {'ok': True, 'nunota': nunota}

    except Exception as exc:
        logger.exception("Falha em editar_requisicao_combustivel_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


def excluir_requisicao_combustivel_banco(nunota: int, motivo: str, codusu: int, nomeusu: str = '') -> dict:
    """B6 — Exclui FISICAMENTE uma requisição em aberto.

    Mai/2026 (2026-05-12): inicialmente B6 fazia UPDATE STATUSNOTA='E', mas o
    trigger TRG_UPD_TGFCAB do Sankhya (linha 979) bloqueia explicitamente:
      "A única atualização permitida para o Status da Nota é a passagem deste
       para L."
    Portanto a exclusão precisa ser DELETE físico — caminho que o Sankhya
    espera (e que dispara as triggers TRG_DLT_TGFCAB_* de auditoria do ERP).

    Operação atômica:
      1. Audit pré-DELETE em IAgroDjango logs (motivo + usuário)
      2. DELETE da AD_REQUISICAO_COMBUSTIVEL (metadata IAgro)
      3. DELETE de TGFITE WHERE NUNOTA (todos os itens)
      4. DELETE de TGFCAB WHERE NUNOTA AND CODTIPOPER=53

    Saldo volta automaticamente porque a NUNOTA some das contas da view.

    Trava: bloqueia se STATUSNOTA='L' (Sankhya já confirmou — estorno deve ser
    feito no ERP pra reverter financeiro/contábil corretamente).
    """
    nunota = int(nunota)
    motivo = (motivo or '').strip()
    if not motivo:
        return {'ok': False, 'error': 'Motivo da exclusão é obrigatório.'}
    if len(motivo) > 300:
        motivo = motivo[:300]

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Verifica estado da TGFCAB TOP 53 + metadata IAgro (TIPO/NUFIN)
            cur.execute("""
                SELECT c.STATUSNOTA, r.TIPO, r.NUFIN_GERADO
                FROM TGFCAB c
                LEFT JOIN AD_REQUISICAO_COMBUSTIVEL r ON r.NUNOTA = c.NUNOTA
                WHERE c.NUNOTA = :n AND c.CODTIPOPER = 53
            """, n=nunota)
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Requisição {nunota} não encontrada.'}
            statusnota, req_tipo, req_nufin_gerado = row[0], row[1], row[2]

            if req_tipo is None:
                return {'ok': False, 'error':
                    'Metadata IAgro não encontrada — requisição inconsistente.'}

            eh_externo = (req_tipo == 'EXTERNA_POSTO')

            # Tipos internos: STATUSNOTA='L' bloqueia (Sankhya confirma).
            # EXTERNA_POSTO: nasce com STATUSNOTA='L' direto — exclusão livre
            # exceto se TGFFIN já estiver baixado.
            if statusnota == 'L' and not eh_externo:
                return {'ok': False, 'error':
                    'Requisição já confirmada no Sankhya — estorno deve ser feito no ERP.'}
            if eh_externo and req_nufin_gerado:
                cur.execute(
                    "SELECT DHBAIXA FROM TGFFIN WHERE NUFIN = :nf",
                    nf=int(req_nufin_gerado),
                )
                row_fin = cur.fetchone()
                if row_fin and row_fin[0] is not None:
                    return {'ok': False, 'error':
                        'Financeiro do abastecimento externo já está baixado — '
                        'estorne a baixa no Sankhya antes de excluir.'}

            # 2. Audit em log Django (motivo+usuário). Faço ANTES dos DELETEs
            # pra ter rastro mesmo se algo falhar adiante.
            usu_label = (nomeusu or str(codusu))[:30]
            logger.info(
                "EXCLUSAO requisição combustível NUNOTA=%s tipo=%s nufin=%s por codusu=%s (%s) — motivo: %s",
                nunota, req_tipo, req_nufin_gerado, codusu, usu_label, motivo,
            )

            # 3. DELETE metadata IAgro (AD_REQ)
            cur.execute(
                "DELETE FROM AD_REQUISICAO_COMBUSTIVEL WHERE NUNOTA = :n",
                n=nunota,
            )

            # 4. EXTERNA_POSTO: DELETE do TGFFIN gerado (despesa contra o posto).
            # Deve vir ANTES do DELETE de TGFCAB porque TGFFIN.NUNOTA aponta pra cá.
            if eh_externo and req_nufin_gerado:
                cur.execute(
                    "DELETE FROM TGFFIN WHERE NUFIN = :nf",
                    nf=int(req_nufin_gerado),
                )

            # 5. DELETE itens (TGFITE) — necessário antes da TGFCAB (FK Sankhya)
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n", n=nunota)

            # 6. DELETE cabeçalho (TGFCAB TOP 53) — dispara TRG_DLT_TGFCAB_*
            # do Sankhya (auditoria/limpeza nativa); saldo da view some.
            cur.execute(
                "DELETE FROM TGFCAB WHERE NUNOTA = :n AND CODTIPOPER = 53",
                n=nunota,
            )

            conn.commit()
            logger.info(
                "Requisição combustível NUNOTA=%s DELETE físico concluído (tipo=%s)",
                nunota, req_tipo,
            )
            return {'ok': True, 'nunota': nunota}

    except Exception as exc:
        logger.exception("Falha em excluir_requisicao_combustivel_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


def criar_entrada_combustivel_banco(dados: dict, codusu: int, nomeusu: str = '') -> dict:
    """B3 (Mai/2026 — refatorada em B13) — Cria entrada de combustível (compra TOP 10).

    Fluxo:
      - TGFCAB TOP 10 STATUSNOTA='L', NUMNOTA da NF do FORNECEDOR (operador
        informa), SERIENOTA opcional. CODNAT/CODTIPVENDA parametrizáveis com
        defaults 30070200 (COMBUSTÍVEL) e 11 (A VISTA).
      - N x TGFITE (multi-itens), CODAGREGACAO=NULL (segregação total).
      - 1 TGFFIN com VLRDESDOB = soma dos itens (modelo NUFIN=438989: ORIGEM='F',
        CODTIPOPER=1, CODBCO=70, CODCTABCOINT=1, CODTIPTIT=2). À vista (DTVENC=DTNEG)
        baixa automática.

    Atômico via `with obter_conexao_oracle()`.

    Payload (`dados`):
      codemp:       int (obrigatório)
      codparc:      int (fornecedor, obrigatório)
      numnota:      int (NF do fornecedor — obrigatório)
      serienota:    str (opcional, máx 3 chars)
      itens:        list[{codprod, qtd, vlrunit}]  (>= 1 item)
                    -- compat retroativa: se itens ausente, monta de codprod/qtd/vlrunit
      codcencus:    int (obrigatório)
      dtneg:        str 'YYYY-MM-DD' (opcional — default hoje)
      dtvenc:       str 'YYYY-MM-DD' (opcional — default = dtneg = à vista)
      codnat:       int (opcional — default 30070200)
      codtipvenda:  int (opcional — default 11 A VISTA)
      codbco:       int (opcional — default 70)
      codctabcoint: int (opcional — default 1)
      codtiptit:    int (opcional — default 2)
      historico:    str (opcional — default = "Compra combust. NF {NUMNOTA}")
      observacao:   str (opcional — vai para TGFCAB.OBSERVACAO)

    Retorno:
      {'ok': True, 'nunota': int, 'numnota': int, 'nufin': int, 'qtd_itens': int}
      {'ok': False, 'error': str}
    """
    # 1. Itens — aceita lista nova OU campos avulsos (compat retroativa)
    itens_payload = dados.get('itens')
    if not itens_payload:
        # Compat: monta lista a partir de codprod/qtd/vlrunit avulsos
        codp_legacy = dados.get('codprod')
        if codp_legacy:
            itens_payload = [{
                'codprod': codp_legacy,
                'qtd': dados.get('qtd'),
                'vlrunit': dados.get('vlrunit'),
            }]
    if not itens_payload or not isinstance(itens_payload, list):
        return {'ok': False, 'error': 'Informe ao menos 1 item.'}

    erros = []
    codemp    = int(dados.get('codemp') or 0)
    codparc   = int(dados.get('codparc') or 0)
    codcencus = int(dados.get('codcencus') or 0)
    numnota_forn = dados.get('numnota')
    serienota = (dados.get('serienota') or '').strip()[:3] or None
    if not codemp:    erros.append('codemp obrigatório')
    if not codparc:   erros.append('codparc obrigatório')
    if not codcencus: erros.append('codcencus obrigatório')
    if not numnota_forn:
        erros.append('numnota (nº da NF do fornecedor) obrigatório')
    else:
        try: numnota_forn = int(numnota_forn)
        except (TypeError, ValueError):
            erros.append('numnota inválido (precisa ser numérico)')

    # Valida cada item
    itens_norm = []
    for idx, it in enumerate(itens_payload, start=1):
        cp  = int(it.get('codprod') or 0)
        qt  = float(it.get('qtd') or 0)
        vlu = float(it.get('vlrunit') or 0)
        if not cp:  erros.append(f'Item {idx}: codprod obrigatório')
        if qt <= 0: erros.append(f'Item {idx}: qtd deve ser > 0')
        if vlu <= 0: erros.append(f'Item {idx}: vlrunit deve ser > 0')
        itens_norm.append({'codprod': cp, 'qtd': qt, 'vlrunit': vlu})

    if erros:
        return {'ok': False, 'error': ' · '.join(erros)}

    # Defaults TGFFIN modelo NUFIN=438989
    codbco       = int(dados.get('codbco')       or 70)
    codctabcoint = int(dados.get('codctabcoint') or 1)
    codtiptit    = int(dados.get('codtiptit')    or 2)
    codnat       = int(dados.get('codnat') or 30070200)
    codtipvenda  = int(dados.get('codtipvenda') or 11)

    dtneg  = _parse_data_iagro(dados.get('dtneg'),  _date.today())
    dtvenc = _parse_data_iagro(dados.get('dtvenc'), dtneg)
    if dtvenc < dtneg:
        return {'ok': False, 'error': 'dtvenc não pode ser anterior a dtneg.'}
    # TGFFIN nasce sempre em aberto (DHBAIXA=NULL) — operador baixa no Sankhya
    # ver bloco do INSERT TGFFIN abaixo pra justificativa do trigger.

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 2. Validar cada produto (combustível) e capturar DESCRPROD/CODVOL
            descricoes = {}  # codprod -> (descrprod, codvol)
            for it in itens_norm:
                cur.execute("""
                    SELECT CODGRUPOPROD, DESCRPROD, CODVOL
                    FROM TGFPRO WHERE CODPROD = :cp AND ATIVO = 'S'
                """, cp=it['codprod'])
                row_p = cur.fetchone()
                if not row_p:
                    return {'ok': False,
                            'error': f"Produto {it['codprod']} não encontrado ou inativo."}
                codgrupo, descrprod, codvol = row_p
                if codgrupo != CODGRUPOPROD_COMBUSTIVEL:
                    return {'ok': False, 'error':
                        f"Produto {it['codprod']} ({descrprod}) não é combustível."}
                descricoes[it['codprod']] = (descrprod, codvol or 'LT')

            # 3. INSERT TGFCAB TOP 10 — NUMNOTA já vem do operador (NF do fornecedor)
            cab_resp = inserir_cabecalho_nota_banco({
                'CODEMP':       codemp,
                'CODPARC':      codparc,
                'CODTIPOPER':   10,
                'CODNAT':       codnat,
                'CODCENCUS':    codcencus,
                'CODTIPVENDA':  codtipvenda,
                'NUMNOTA':      numnota_forn,
                'DTNEG':        dtneg.strftime('%d/%m/%Y'),
                'DTMOV':        dtneg.strftime('%d/%m/%Y'),
                'OBSERVACAO':   (dados.get('observacao') or '')[:200] or None,
            }, conexao_existente=conn)
            if not cab_resp.get('ok'):
                return {'ok': False, 'error':
                    f'Falha ao criar cabeçalho TOP 10: {cab_resp.get("error", "desconhecido")}'}
            nunota = int(cab_resp['nunota'])

            # 3.5 SERIENOTA — UPDATE pós-INSERT (inserir_cabecalho não suporta no payload)
            if serienota:
                cur.execute("UPDATE TGFCAB SET SERIENOTA = :s WHERE NUNOTA = :n",
                            s=serienota, n=nunota)

            # 4. INSERT N x TGFITE (CODAGREGACAO=NULL — segregação)
            vlrtot_total = 0.0
            for it in itens_norm:
                cp = it['codprod']
                descrprod, codvol = descricoes[cp]
                vlrtot_item = round(it['qtd'] * it['vlrunit'], 4)
                vlrtot_total += vlrtot_item
                item_resp = inserir_item_nota_banco({
                    'NUNOTA':       nunota,
                    'CODPROD':      cp,
                    'QTDNEG':       it['qtd'],
                    'VLRUNIT':      it['vlrunit'],
                    'CODVOL':       codvol,
                    'CODAGREGACAO': None,
                }, gerar_lote_auto=False, conexao_existente=conn)
                if not item_resp.get('ok'):
                    return {'ok': False, 'error':
                        f"Falha ao criar item CODPROD={cp}: {item_resp.get('error', 'desconhecido')}"}

            recalcular_totais_nota_banco(nunota, conexao_existente=conn)
            vlrtot_total = round(vlrtot_total, 4)
            numnota = numnota_forn

            # 6. NUFIN provisório (mesma estratégia do gerar_financeiro_banco)
            cur.execute("SELECT NVL(MAX(NUFIN), 0) + 1 FROM TGFFIN")
            nufin = int(cur.fetchone()[0])
            historico = (dados.get('historico') or f'Compra combust. NF {numnota_forn}')[:255]
            # Renomeia pra compatibilidade do bloco abaixo
            vlrtot = vlrtot_total
            # `descrprod` é usado pelo template de histórico em fluxos antigos —
            # mantém uma versão composta com todos os produtos como referência.
            descrprod = ', '.join(d[0] for d in descricoes.values())[:255]

            # 7. INSERT TGFFIN (modelo NUFIN=438989: ORIGEM='F', CODTIPOPER=1)
            sql_fin = """
                INSERT INTO TGFFIN (
                    NUFIN, NUNOTA, NUMNOTA, CODEMP, CODPARC, CODNAT, CODCENCUS,
                    CODTIPOPER, DHTIPOPER, CODBCO, CODCTABCOINT, CODTIPTIT,
                    CODMOEDA, CODPROJ, CODVEND, CODVEICULO,
                    DTNEG, DHMOV, DTALTER, DTENTSAI,
                    DTVENCINIC, DTVENC, DTPRAZO,
                    VLRDESDOB, VLRBAIXA,
                    DESDOBRAMENTO, SEQUENCIA,
                    RECDESP, PROVISAO, AUTORIZADO,
                    ISSRETIDO, IRFRETIDO, INSSRETIDO, RATEADO,
                    ORIGEM, TIPMARCCHEQ,
                    TIPMULTA, TIPJURO,
                    CODTIPOPERBAIXA, DHTIPOPERBAIXA,
                    HISTORICO, VLRPROV, NUMCONTRATO, ORDEMCARGA, CODUSU,
                    DHBAIXA, CODEMPBAIXA, CODUSUBAIXA
                ) VALUES (
                    :nufin, :nunota, :numnota, :emp, :parc, :nat, :cus,
                    1, TO_DATE('01/01/2004','DD/MM/YYYY'), :bco, :ccbi, :tit,
                    0, 0, 0, 0,
                    :dtneg, SYSDATE, SYSDATE, :dtneg,
                    :dtneg, :dtvenc, :dtvenc,
                    :vlr, :vlrbaixa,
                    '1', 1,
                    -1, 'N', 'N',
                    'N', 'S', 'N', 'N',
                    'E', 'I',
                    1, 1,
                    0, TO_DATE('01/01/1998','DD/MM/YYYY'),
                    :hist, 0, 0, 0, :usr,
                    :dhbaixa, :empbaixa, :usubaixa
                )
            """
            # TGFFIN nasce SEMPRE em aberto (DHBAIXA=NULL, VLRBAIXA=0) — mesmo
            # quando à vista. Mai/2026 (2026-05-13): o trigger Sankhya
            # TRG_UPT_TGFFIN_NUBCO bloqueia "baixa sem ligação com TGFMBC".
            # Pra marcar baixado é preciso criar registro paralelo em TGFMBC
            # (que IAgro não cuida). Operador baixa pelo Sankhya quando paga.
            cur.execute(sql_fin, {
                'nufin': nufin, 'nunota': nunota, 'numnota': numnota,
                'emp': codemp, 'parc': codparc, 'nat': codnat, 'cus': codcencus,
                'bco': codbco, 'ccbi': codctabcoint, 'tit': codtiptit,
                'dtneg': dtneg, 'dtvenc': dtvenc,
                'vlr': vlrtot, 'vlrbaixa': 0,
                'hist': historico, 'usr': int(codusu),
                'dhbaixa': None,
                'empbaixa': None,
                'usubaixa': None,
            })

            # 8. Confirma a nota (STATUSNOTA='L') — triggers Sankhya disparam aqui;
            # com NUFIN já existente, não duplica financeiro
            cur.execute("""
                UPDATE TGFCAB SET STATUSNOTA = 'L', DTFATUR = :dt
                WHERE NUNOTA = :n
            """, dt=dtneg, n=nunota)

            conn.commit()
            logger.info(
                "Entrada combustível: NUNOTA=%s NUFIN=%s NUMNOTA=%s itens=%s vlrtot=%s",
                nunota, nufin, numnota, len(itens_norm), vlrtot,
            )
            return {
                'ok': True, 'nunota': nunota, 'numnota': numnota, 'nufin': nufin,
                'qtd_itens': len(itens_norm), 'vlrtot': float(vlrtot),
            }

    except Exception as exc:
        logger.exception("Falha em criar_entrada_combustivel_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


def criar_abastecimento_externo_banco(dados: dict, codusu: int, nomeusu: str = '') -> dict:
    """B8 — Cria abastecimento externo (posto): TGFCAB TOP 26 STATUSNOTA='L'
    + TGFITE (CODAGREGACAO=NULL) + AD_REQUISICAO_COMBUSTIVEL (TIPO='EXTERNA_POSTO')
    + TGFFIN (despesa contra o posto).

    Fluxo Mai/2026: caminhão sai com tanque cheio → abastece no meio da viagem em
    posto externo → não desconta dos tanques internos, mas precisa registrar
    o consumo (km/L) e gerar financeiro contra o posto. A view
    ANDRE_IAGRO_SALDO_COMBUSTIVEL ignora notas com TIPO='EXTERNA_POSTO' na perna
    de saída (via NOT EXISTS), preservando saldo interno.

    Diferenças vs criar_requisicao_combustivel_banco (interno):
      - SEM validação de saldo (não desconta tanque)
      - SEM trava PROPRIO ↔ TIPO (motorista pode usar veículo próprio mesmo
        abastecendo fora; veículos de freteiros também podem usar)
      - CODPARC do cabeçalho = posto informado (NÃO TGFVEI.CODPARC)
      - STATUSNOTA='L' direto (lançamento avulso já confirmado)
      - Gera TGFFIN (modelo NUFIN=438989 da Agromil)
      - Hodômetro/horímetro continuam OBRIGATÓRIOS (não pode ter lacuna de consumo)

    Payload (`dados`):
      codveiculo:    int (obrigatório)
      codparc:       int (obrigatório — posto: Allianz, 1=Semear, 572=Agromil)
      codprod:       int (obrigatório — CODGRUPOPROD=200400)
      qtd:           float (litros, > 0)
      vlrunit:       float (> 0)
      codcencus:     int (obrigatório)
      hodometro_km:  float (obrigatório)
      horimetro_h:   float (opcional)
      doc_frete_ref: str (opcional — número da nota/boleto do posto)
      observacao:    str (opcional)
      dtneg:         str 'YYYY-MM-DD' (opcional, default hoje)
      dtvenc:        str 'YYYY-MM-DD' (opcional, default = dtneg = à vista)
      codbco/codctabcoint/codtiptit: opcionais (defaults do modelo)
      historico:     str (opcional — TGFFIN.HISTORICO; default DESCRPROD)

    Retorno:
      {'ok': True,  'nunota': int, 'requisicao_id': int, 'nufin': int}
      {'ok': False, 'error': str}
    """
    # 1. Validações
    erros = []
    codveiculo = int(dados.get('codveiculo') or 0)
    codparc    = int(dados.get('codparc') or 0)
    codcencus  = int(dados.get('codcencus') or 0)

    # Multi-itens (Mai/2026 — 2026-05-13). Compat retroativa: aceita
    # `itens=[{codprod, qtd, vlrunit}, ...]` ou `codprod/qtd/vlrunit` avulsos
    # (monta lista de 1 item).
    itens_payload = dados.get('itens')
    if not itens_payload:
        codp_legacy = dados.get('codprod')
        if codp_legacy:
            itens_payload = [{
                'codprod': codp_legacy,
                'qtd': dados.get('qtd'),
                'vlrunit': dados.get('vlrunit'),
            }]
    if not itens_payload or not isinstance(itens_payload, list):
        return {'ok': False, 'error': 'Informe ao menos 1 item.'}

    itens_norm = []
    for idx, it in enumerate(itens_payload, start=1):
        cp = int(it.get('codprod') or 0)
        qt = float(it.get('qtd') or 0)
        vu = float(it.get('vlrunit') or 0)
        if not cp:  erros.append(f'Item {idx}: codprod obrigatório')
        if qt <= 0: erros.append(f'Item {idx}: qtd > 0')
        if vu <= 0: erros.append(f'Item {idx}: vlrunit > 0')
        itens_norm.append({'codprod': cp, 'qtd': qt, 'vlrunit': vu})

    if not codveiculo: erros.append('codveiculo obrigatório')
    if not codparc:    erros.append('codparc (posto) obrigatório')
    if not codcencus:  erros.append('codcencus obrigatório')

    def _parse_medidor(raw):
        if raw in (None, '', 0, 0.0):
            return None
        try:
            v = float(raw)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return False

    hodometro_km = _parse_medidor(dados.get('hodometro_km'))
    horimetro_h  = _parse_medidor(dados.get('horimetro_h'))
    if hodometro_km is False: erros.append('hodometro_km inválido')
    if horimetro_h  is False: erros.append('horimetro_h inválido')
    # Mai/2026: hodômetro opcional no abastecimento externo (era obrigatório).

    # Mai/2026 (B8): NUMNOTA do posto vem do operador. Validação numérica
    # estrita — se digitar texto como "NF 12345", recusa pra evitar gravar
    # lixo em TGFCAB.NUMNOTA/TGFFIN.NUMNOTA (campo NUMBER no Sankhya).
    numnota_raw = (dados.get('numnota') or '').strip() if dados.get('numnota') else ''
    numnota_operador = None
    if numnota_raw:
        try:
            numnota_operador = int(numnota_raw)
            if numnota_operador <= 0:
                erros.append('numnota deve ser maior que zero')
                numnota_operador = None
        except (ValueError, TypeError):
            erros.append('Nº da nota fiscal deve ser apenas números '
                         '(digite 12345, não NF 12345).')

    if erros:
        return {'ok': False, 'error': ' · '.join(erros)}

    # Defaults TGFFIN
    codbco       = int(dados.get('codbco')       or 70)
    codctabcoint = int(dados.get('codctabcoint') or 1)
    codtiptit    = int(dados.get('codtiptit')    or 2)
    codnat       = int(dados.get('codnat') or 30070200)
    codtipvenda  = int(dados.get('codtipvenda') or 11)
    dtneg  = _parse_data_iagro(dados.get('dtneg'),  _date.today())
    dtvenc = _parse_data_iagro(dados.get('dtvenc'), dtneg)
    if dtvenc < dtneg:
        return {'ok': False, 'error': 'dtvenc não pode ser anterior a dtneg.'}
    # TGFFIN nasce sempre em aberto (DHBAIXA=NULL). Trigger Sankhya
    # TRG_UPT_TGFFIN_NUBCO exige TGFMBC paralela pra baixa — operador baixa
    # pelo Sankhya quando paga.

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 2. Veículo existe (sem trava PROPRIO — externo aceita qualquer)
            cur.execute("""
                SELECT v.PLACA FROM TGFVEI v
                WHERE v.CODVEICULO = :cv AND v.ATIVO = 'S'
            """, cv=codveiculo)
            if not cur.fetchone():
                return {'ok': False, 'error': f'Veículo {codveiculo} não encontrado ou inativo.'}

            # 3. Parceiro (posto) existe e ativo
            cur.execute("""
                SELECT NOMEPARC FROM TGFPAR
                WHERE CODPARC = :cp AND ATIVO = 'S'
            """, cp=codparc)
            row_parc = cur.fetchone()
            if not row_parc:
                return {'ok': False, 'error': f'Parceiro {codparc} (posto) não encontrado ou inativo.'}
            nome_posto = row_parc[0]

            # 4. Validar todos os itens são combustíveis
            descricoes = {}  # codprod -> (descrprod, codvol)
            for it in itens_norm:
                cur.execute("""
                    SELECT CODGRUPOPROD, DESCRPROD, CODVOL
                    FROM TGFPRO WHERE CODPROD = :cp AND ATIVO = 'S'
                """, cp=it['codprod'])
                row_p = cur.fetchone()
                if not row_p:
                    return {'ok': False,
                            'error': f"Produto {it['codprod']} não encontrado ou inativo."}
                codgrupo, descrprod_i, codvol_i = row_p
                if codgrupo != CODGRUPOPROD_COMBUSTIVEL:
                    return {'ok': False, 'error':
                        f"Produto {it['codprod']} ({descrprod_i}) não é combustível."}
                descricoes[it['codprod']] = (descrprod_i, codvol_i or 'LT')

            # CODEMP da TGFCAB — reusa a CODEMP mais recente do CODPARC do posto
            # (mesma estratégia da Entrada interna) ou cai em default 1.
            cur.execute("""
                SELECT MAX(CODEMP) FROM TGFCAB
                WHERE CODPARC = :p AND STATUSNOTA <> 'E'
            """, p=codparc)
            row_emp = cur.fetchone()
            codemp = int(row_emp[0]) if row_emp and row_emp[0] else 1

            # 5. INSERT TGFCAB TOP 53 - REQUISIÇÃO INTERNA (PENDENTE='S' inicialmente)
            cab_resp = inserir_cabecalho_nota_banco({
                'CODEMP':       codemp,
                'CODPARC':      codparc,                  # POSTO (não veículo)
                'CODTIPOPER':   53,
                'CODNAT':       codnat,
                'CODCENCUS':    codcencus,
                'CODTIPVENDA':  codtipvenda,
                'DTNEG':        dtneg.strftime('%d/%m/%Y'),
                'DTMOV':        dtneg.strftime('%d/%m/%Y'),
                'OBSERVACAO':   (dados.get('observacao') or f'Abast. externo - {nome_posto}')[:200] or None,
            }, conexao_existente=conn)
            if not cab_resp.get('ok'):
                return {'ok': False, 'error':
                    f'Falha ao criar cabeçalho TOP 53: {cab_resp.get("error", "desconhecido")}'}
            nunota = int(cab_resp['nunota'])

            # 6. INSERT N x TGFITE (CODAGREGACAO=NULL — segregação)
            vlrtot = 0.0
            for it in itens_norm:
                cp = it['codprod']
                descrprod_i, codvol_i = descricoes[cp]
                vlt_item = round(it['qtd'] * it['vlrunit'], 4)
                vlrtot += vlt_item
                item_resp = inserir_item_nota_banco({
                    'NUNOTA':       nunota,
                    'CODPROD':      cp,
                    'QTDNEG':       it['qtd'],
                    'VLRUNIT':      it['vlrunit'],
                    'CODVOL':       codvol_i,
                    'CODAGREGACAO': None,
                }, gerar_lote_auto=False, conexao_existente=conn)
                if not item_resp.get('ok'):
                    return {'ok': False, 'error':
                        f"Falha ao criar item CODPROD={cp}: {item_resp.get('error')}"}
            vlrtot = round(vlrtot, 4)

            recalcular_totais_nota_banco(nunota, conexao_existente=conn)

            # 7. NUMNOTA — Mai/2026 (B8): prioriza o número digitado pelo
            # operador. Sankhya aceita números repetidos em TOP de requisição,
            # então não há trava de colisão. Fallback (operador não digitou):
            # gera sequencial MAX+1 por empresa (comportamento legado).
            if numnota_operador:
                numnota = numnota_operador
            else:
                cur.execute("""
                    SELECT NVL(MAX(NUMNOTA), 0) + 1 FROM TGFCAB
                    WHERE CODEMP = :e AND CODTIPOPER = 53
                """, e=codemp)
                numnota = int(cur.fetchone()[0])
            cur.execute("UPDATE TGFCAB SET NUMNOTA = :nn WHERE NUNOTA = :n",
                        nn=numnota, n=nunota)

            # 8. NUFIN — gera despesa (RECDESP=-1) contra o posto.
            # Histórico: composto pelos produtos do abastecimento + nome do posto.
            cur.execute("SELECT NVL(MAX(NUFIN), 0) + 1 FROM TGFFIN")
            nufin = int(cur.fetchone()[0])
            hist_produtos = ', '.join(d[0] for d in descricoes.values())[:200]
            historico = (dados.get('historico') or f'{hist_produtos} - {nome_posto}')[:255]

            sql_fin = """
                INSERT INTO TGFFIN (
                    NUFIN, NUNOTA, NUMNOTA, CODEMP, CODPARC, CODNAT, CODCENCUS,
                    CODTIPOPER, DHTIPOPER, CODBCO, CODCTABCOINT, CODTIPTIT,
                    CODMOEDA, CODPROJ, CODVEND, CODVEICULO,
                    DTNEG, DHMOV, DTALTER, DTENTSAI,
                    DTVENCINIC, DTVENC, DTPRAZO,
                    VLRDESDOB, VLRBAIXA,
                    DESDOBRAMENTO, SEQUENCIA,
                    RECDESP, PROVISAO, AUTORIZADO,
                    ISSRETIDO, IRFRETIDO, INSSRETIDO, RATEADO,
                    ORIGEM, TIPMARCCHEQ,
                    TIPMULTA, TIPJURO,
                    CODTIPOPERBAIXA, DHTIPOPERBAIXA,
                    HISTORICO, VLRPROV, NUMCONTRATO, ORDEMCARGA, CODUSU,
                    DHBAIXA, CODEMPBAIXA, CODUSUBAIXA
                ) VALUES (
                    :nufin, :nunota, :numnota, :emp, :parc, :nat, :cus,
                    1, TO_DATE('01/01/2004','DD/MM/YYYY'), :bco, :ccbi, :tit,
                    0, 0, 0, :cv,
                    :dtneg, SYSDATE, SYSDATE, :dtneg,
                    :dtneg, :dtvenc, :dtvenc,
                    :vlr, :vlrbaixa,
                    '1', 1,
                    -1, 'N', 'N',
                    'N', 'S', 'N', 'N',
                    'E', 'I',
                    1, 1,
                    0, TO_DATE('01/01/1998','DD/MM/YYYY'),
                    :hist, 0, 0, 0, :usr,
                    :dhbaixa, :empbaixa, :usubaixa
                )
            """
            # TGFFIN sempre em aberto (DHBAIXA=NULL) — operador baixa no Sankhya.
            cur.execute(sql_fin, {
                'nufin': nufin, 'nunota': nunota, 'numnota': numnota,
                'emp': codemp, 'parc': codparc, 'nat': codnat, 'cus': codcencus,
                'bco': codbco, 'ccbi': codctabcoint, 'tit': codtiptit,
                'cv': codveiculo,
                'dtneg': dtneg, 'dtvenc': dtvenc,
                'vlr': vlrtot, 'vlrbaixa': 0,
                'hist': historico, 'usr': int(codusu),
                'dhbaixa': None,
                'empbaixa': None,
                'usubaixa': None,
            })

            # 9. INSERT AD_REQUISICAO_COMBUSTIVEL (TIPO=EXTERNA_POSTO + audit do NUFIN)
            req_id_var = cur.var(int)
            cur.execute("""
                INSERT INTO AD_REQUISICAO_COMBUSTIVEL (
                    ID, NUNOTA, TIPO, CATEGORIA, CODVEICULO, CODPARC,
                    HODOMETRO_KM, HORIMETRO_H,
                    DOC_FRETE_REF, OBSERVACAO,
                    NUFIN_GERADO, CODUSU, NOMEUSU
                ) VALUES (
                    SEQ_AD_REQUISICAO_COMBUSTIVEL.NEXTVAL, :nun, 'EXTERNA_POSTO',
                    'COMBUSTIVEL', :cv, :cp,
                    :hod_km, :hor_h,
                    :doc, :obs,
                    :nufin, :codusu, :nomeusu
                )
                RETURNING ID INTO :req_id
            """, {
                'nun': nunota, 'cv': codveiculo, 'cp': codparc,
                'hod_km': hodometro_km, 'hor_h': horimetro_h,
                'doc': (dados.get('doc_frete_ref') or '')[:50] or None,
                'obs': (dados.get('observacao') or '')[:500] or None,
                'nufin': nufin,
                'codusu': int(codusu), 'nomeusu': (nomeusu or '')[:60] or None,
                'req_id': req_id_var,
            })
            req_id = req_id_var.getvalue()
            if isinstance(req_id, list):
                req_id = req_id[0]

            # 10. Confirma TGFCAB (STATUSNOTA='L') — lançamento avulso já confirmado.
            cur.execute("""
                UPDATE TGFCAB SET STATUSNOTA = 'L', DTFATUR = :dt
                WHERE NUNOTA = :n
            """, dt=dtneg, n=nunota)

            conn.commit()
            logger.info(
                "Abast. externo: NUNOTA=%s NUFIN=%s posto=%s veículo=%s itens=%s vlrtot=%s",
                nunota, nufin, codparc, codveiculo, len(itens_norm), vlrtot,
            )
            return {
                'ok': True, 'nunota': nunota, 'numnota': numnota,
                'requisicao_id': int(req_id), 'nufin': nufin,
                'qtd_itens': len(itens_norm), 'vlrtot': float(vlrtot),
            }

    except Exception as exc:
        logger.exception("Falha em criar_abastecimento_externo_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


def obter_entrada_combustivel(nunota: int):
    """Carrega cabeçalho + itens + financeiro de uma entrada (TOP 10 combustível).

    Retorna dict {cabecalho, itens, financeiro} ou None se não existir.
    """
    nunota = int(nunota)
    sql_cab = """
        SELECT c.NUNOTA, c.NUMNOTA, c.SERIENOTA, c.CODEMP, c.CODPARC, p.NOMEPARC,
               c.CODTIPOPER, c.CODNAT, c.CODCENCUS, c.CODTIPVENDA, c.STATUSNOTA,
               c.DTNEG, c.DTMOV, c.VLRNOTA, c.QTDVOL, c.OBSERVACAO, c.CODUSU
        FROM TGFCAB c
        LEFT JOIN TGFPAR p ON p.CODPARC = c.CODPARC
        WHERE c.NUNOTA = :n AND c.CODTIPOPER = 10
    """
    sql_itens = """
        SELECT i.SEQUENCIA, i.CODPROD, pr.DESCRPROD, i.CODVOL,
               i.QTDNEG, i.VLRUNIT, i.VLRTOT, pr.CODGRUPOPROD
        FROM TGFITE i
        LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
        WHERE i.NUNOTA = :n
        ORDER BY i.SEQUENCIA
    """
    sql_fin = """
        SELECT NUFIN, DTVENC, DHBAIXA, VLRDESDOB, VLRBAIXA, HISTORICO,
               CODBCO, CODCTABCOINT, CODTIPTIT
        FROM TGFFIN WHERE NUNOTA = :n
    """
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql_cab, n=nunota)
        row = cur.fetchone()
        if not row:
            return None
        cab = {
            'NUNOTA': int(row[0]),
            'NUMNOTA': int(row[1]) if row[1] is not None else None,
            'SERIENOTA': row[2] or '',
            'CODEMP': int(row[3]) if row[3] is not None else None,
            'CODPARC': int(row[4]) if row[4] is not None else None,
            'NOMEPARC': row[5] or '',
            'CODTIPOPER': int(row[6]) if row[6] is not None else None,
            'CODNAT': int(row[7]) if row[7] is not None else None,
            'CODCENCUS': int(row[8]) if row[8] is not None else None,
            'CODTIPVENDA': int(row[9]) if row[9] is not None else None,
            'STATUSNOTA': row[10],
            'DTNEG': row[11].strftime('%Y-%m-%d') if row[11] else None,
            'DTMOV': row[12].strftime('%Y-%m-%d') if row[12] else None,
            'VLRNOTA': float(row[13]) if row[13] is not None else 0.0,
            'QTDVOL': float(row[14]) if row[14] is not None else 0.0,
            'OBSERVACAO': row[15] or '',
            'CODUSU': int(row[16]) if row[16] is not None else None,
        }
        cur.execute(sql_itens, n=nunota)
        itens = [{
            'SEQUENCIA': int(r[0]),
            'CODPROD': int(r[1]),
            'DESCRPROD': r[2] or '',
            'CODVOL': r[3] or '',
            'QTDNEG': float(r[4]) if r[4] is not None else 0.0,
            'VLRUNIT': float(r[5]) if r[5] is not None else 0.0,
            'VLRTOT': float(r[6]) if r[6] is not None else 0.0,
            'CODGRUPOPROD': int(r[7]) if r[7] is not None else None,
        } for r in cur.fetchall()]
        cur.execute(sql_fin, n=nunota)
        fr = cur.fetchone()
        financeiro = None
        if fr:
            financeiro = {
                'NUFIN': int(fr[0]),
                'DTVENC': fr[1].strftime('%Y-%m-%d') if fr[1] else None,
                'DHBAIXA': fr[2].strftime('%Y-%m-%d') if fr[2] else None,
                'VLRDESDOB': float(fr[3]) if fr[3] is not None else 0.0,
                'VLRBAIXA': float(fr[4]) if fr[4] is not None else 0.0,
                'HISTORICO': fr[5] or '',
                'CODBCO': int(fr[6]) if fr[6] is not None else None,
                'CODCTABCOINT': int(fr[7]) if fr[7] is not None else None,
                'CODTIPTIT': int(fr[8]) if fr[8] is not None else None,
            }
        return {'cabecalho': cab, 'itens': itens, 'financeiro': financeiro}


def consultar_ultimo_preco_combustivel(codprod: int):
    """Mai/2026 (2026-05-13) — Retorna o VLRUNIT do último abastecimento de
    estoque (TOP 10 não-excluído) de um combustível.

    Usado pelo módulo Combustível: ao escolher o produto numa requisição
    interna, o campo "Valor unitário" é preenchido automaticamente com esse
    valor (read-only — operador não digita). Pra abastecimento externo, o
    preço vem do posto (operador edita).

    Retorna:
      {'codprod': int, 'vlrunit': float, 'dtneg': 'YYYY-MM-DD', 'nunota': int}
      None se não houver entrada de estoque com VLRUNIT > 0.
    """
    codprod = int(codprod)
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT VLRUNIT, DTNEG, NUNOTA FROM (
                SELECT i.VLRUNIT, c.DTNEG, c.NUNOTA
                FROM TGFITE i
                JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                WHERE c.CODTIPOPER = 10
                  AND c.STATUSNOTA <> 'E'
                  AND i.CODPROD = :cp
                  AND NVL(i.VLRUNIT, 0) > 0
                ORDER BY c.DTNEG DESC, c.NUNOTA DESC
            )
            WHERE ROWNUM = 1
        """, cp=codprod)
        row = cur.fetchone()
        if not row:
            return None
        return {
            'codprod': codprod,
            'vlrunit': float(row[0]) if row[0] is not None else 0.0,
            'dtneg': row[1].strftime('%Y-%m-%d') if row[1] else None,
            'nunota': int(row[2]) if row[2] is not None else None,
        }


def consultar_prazo_tipvenda(codtipvenda: int):
    """Retorna o prazo padrão (em dias) de um TGFTPV pra cálculo automático
    de DTVENC = DTNEG + prazo.

    Fonte do prazo (Mai/2026, 2026-05-13) — Agromil tem ~95% dos TGFTPV com
    BASEPRAZO=0 mas o prazo real está no NOME (ex: "A PRAZO - 30 DIAS"). Por
    isso uso 2 camadas:
      1. BASEPRAZO da TGFTPV (oficial)
      2. Fallback: regex no DESCRTIPVENDA buscando "\\d+ DIAS"
      3. Sem nada → 0 (à vista; operador edita DTVENC manualmente)

    Se houver múltiplas linhas pro mesmo CODTIPVENDA (Sankhya versiona por
    DHALTER), pega a MAIS RECENTE.
    """
    import re
    codtipvenda = int(codtipvenda)
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT CODTIPVENDA, DESCRTIPVENDA, NVL(BASEPRAZO, 0)
            FROM (
                SELECT CODTIPVENDA, DESCRTIPVENDA, BASEPRAZO, DHALTER
                FROM TGFTPV WHERE CODTIPVENDA = :c AND ATIVO = 'S'
                ORDER BY DHALTER DESC
            )
            WHERE ROWNUM = 1
        """, c=codtipvenda)
        row = cur.fetchone()
        if not row:
            return None
        descr = row[1] or ''
        prazo = int(row[2] or 0)
        # Fallback: extrai dias da descrição (formato "X DIAS")
        if prazo == 0 and descr:
            m = re.search(r'(\d+)\s*DIAS?', descr.upper())
            if m:
                prazo = int(m.group(1))
        return {
            'codtipvenda': int(row[0]),
            'descrtipvenda': descr,
            'prazo_dias': prazo,
        }


def editar_entrada_combustivel_banco(nunota: int, dados: dict, codusu: int, nomeusu: str = '') -> dict:
    """B14 (Mai/2026) — Edita entrada de combustível (TOP 10) em modo CRUD do IAgro.

    Trava: bloqueia se TGFFIN já está baixado (DHBAIXA NOT NULL) — operador
    deve estornar a baixa no Sankhya antes.

    Estratégia transacional atômica:
      1. Valida estado atual
      2. UPDATE TGFCAB (cab metadata: CODEMP, CODPARC, NUMNOTA, SERIENOTA,
         DTNEG, CODNAT, CODCENCUS, CODTIPVENDA, OBSERVACAO)
      3. DELETE TGFITE WHERE NUNOTA  → INSERT N novos itens
         (simples e robusto vs UPDATE item-a-item com match de SEQUENCIA)
      4. recalcular_totais_nota_banco
      5. UPDATE TGFFIN (VLRDESDOB, VLRBAIXA, DTVENC, HISTORICO, CODPARC,
         CODEMP, CODNAT, CODCENCUS, DTNEG)

    Payload (`dados`) — mesmo formato do criar (com `itens` lista).
    Todos os campos do payload são opcionais — campos ausentes preservam o
    valor atual.

    Retorno:
      {'ok': True, 'nunota': int, 'numnota': int, 'nufin': int, 'qtd_itens': int}
      {'ok': False, 'error': str}
    """
    nunota = int(nunota)
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Carrega estado atual (cab + fin)
            cur.execute("""
                SELECT c.STATUSNOTA, c.CODEMP, c.CODPARC, c.NUMNOTA, c.SERIENOTA,
                       c.CODNAT, c.CODCENCUS, c.CODTIPVENDA, c.DTNEG, c.OBSERVACAO,
                       f.NUFIN, f.DTVENC, f.DHBAIXA, f.HISTORICO,
                       f.CODBCO, f.CODCTABCOINT, f.CODTIPTIT
                FROM TGFCAB c
                LEFT JOIN TGFFIN f ON f.NUNOTA = c.NUNOTA
                WHERE c.NUNOTA = :n AND c.CODTIPOPER = 10
            """, n=nunota)
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Entrada {nunota} não encontrada.'}
            (statusnota, cab_emp, cab_parc, cab_numnota, cab_serie,
             cab_nat, cab_cencus, cab_tipv, cab_dtneg, cab_obs,
             fin_nufin, fin_dtvenc, fin_dhbaixa, fin_hist,
             fin_bco, fin_ccbi, fin_tit) = row

            if statusnota == 'E':
                return {'ok': False, 'error': 'Entrada já está excluída.'}
            if fin_dhbaixa is not None:
                return {'ok': False, 'error':
                    'Financeiro desta entrada já está baixado. '
                    'Estorne a baixa no Sankhya antes de editar.'}
            if not fin_nufin:
                return {'ok': False, 'error':
                    'Esta entrada não tem TGFFIN associado — inconsistente.'}

            # 2. Resolve novos valores (preserva atual se ausente)
            codemp     = int(dados.get('codemp')     or cab_emp)
            codparc    = int(dados.get('codparc')    or cab_parc)
            numnota_n  = int(dados.get('numnota')    or cab_numnota)
            serienota_n = (dados.get('serienota') if 'serienota' in dados
                           else (cab_serie or ''))
            serienota_n = (serienota_n or '').strip()[:3] or None
            codnat     = int(dados.get('codnat')     or cab_nat)
            codcencus  = int(dados.get('codcencus')  or cab_cencus)
            codtipvenda = int(dados.get('codtipvenda') or cab_tipv or 11)
            dtneg_n  = _parse_data_iagro(dados.get('dtneg'),  cab_dtneg)
            dtvenc_n = _parse_data_iagro(dados.get('dtvenc'), fin_dtvenc)
            observacao = (dados.get('observacao') if 'observacao' in dados else cab_obs)

            if dtvenc_n < dtneg_n:
                return {'ok': False, 'error': 'dtvenc não pode ser anterior a dtneg.'}
            # TGFFIN não tem baixa automática — operador baixa pelo Sankhya.
            # Edição preserva o estado de baixa atual (DHBAIXA permanece como está).

            # 3. Itens — exige lista (ou monta de campos avulsos por compat)
            itens_payload = dados.get('itens')
            if not itens_payload:
                codp_legacy = dados.get('codprod')
                if codp_legacy:
                    itens_payload = [{
                        'codprod': codp_legacy,
                        'qtd': dados.get('qtd'),
                        'vlrunit': dados.get('vlrunit'),
                    }]
            if not itens_payload or not isinstance(itens_payload, list):
                return {'ok': False, 'error': 'Informe ao menos 1 item.'}

            erros_itens = []
            itens_norm = []
            for idx, it in enumerate(itens_payload, start=1):
                cp = int(it.get('codprod') or 0)
                qt = float(it.get('qtd') or 0)
                vu = float(it.get('vlrunit') or 0)
                if not cp:  erros_itens.append(f'Item {idx}: codprod obrigatório')
                if qt <= 0: erros_itens.append(f'Item {idx}: qtd > 0')
                if vu <= 0: erros_itens.append(f'Item {idx}: vlrunit > 0')
                itens_norm.append({'codprod': cp, 'qtd': qt, 'vlrunit': vu})
            if erros_itens:
                return {'ok': False, 'error': ' · '.join(erros_itens)}

            # Valida cada produto é combustível
            descricoes = {}
            for it in itens_norm:
                cur.execute("""
                    SELECT CODGRUPOPROD, DESCRPROD, CODVOL
                    FROM TGFPRO WHERE CODPROD = :cp AND ATIVO = 'S'
                """, cp=it['codprod'])
                rp = cur.fetchone()
                if not rp:
                    return {'ok': False, 'error': f"Produto {it['codprod']} não encontrado."}
                if rp[0] != CODGRUPOPROD_COMBUSTIVEL:
                    return {'ok': False, 'error':
                        f"Produto {it['codprod']} ({rp[1]}) não é combustível."}
                descricoes[it['codprod']] = (rp[1], rp[2] or 'LT')

            # 4. UPDATE TGFCAB
            cur.execute("""
                UPDATE TGFCAB
                   SET CODEMP = :emp, CODPARC = :parc,
                       NUMNOTA = :nn, SERIENOTA = :sn,
                       CODNAT = :nat, CODCENCUS = :cus, CODTIPVENDA = :tipv,
                       DTNEG = :dt, DTMOV = :dt,
                       OBSERVACAO = :obs
                 WHERE NUNOTA = :n AND CODTIPOPER = 10
            """, {
                'n': nunota,
                'emp': codemp, 'parc': codparc,
                'nn': numnota_n, 'sn': serienota_n,
                'nat': codnat, 'cus': codcencus, 'tipv': codtipvenda,
                'dt': dtneg_n,
                'obs': (observacao or '')[:200] or None,
            })

            # 5. UPDATE diferencial dos itens (Mai/2026, 2026-05-13).
            # Reusa SEQUENCIAs existentes via UPDATE (evita disparar
            # TRG_INC_UPD_TGFITE_PRODNFE) e usa `inserir_item_nota_banco` para
            # adicionais — que agora aceita conn existente em
            # `gerar_proxima_sequencia_item`, então as SEQUENCIAs sucessivas
            # batem dentro da mesma transação sem PK violation.
            cur.execute("""
                SELECT SEQUENCIA FROM TGFITE WHERE NUNOTA = :n ORDER BY SEQUENCIA
            """, n=nunota)
            seqs_existentes = [int(r[0]) for r in cur.fetchall()]

            vlrtot_total = 0.0
            for idx, it in enumerate(itens_norm):
                cp = it['codprod']
                _, codvol = descricoes[cp]
                vlt_item = round(it['qtd'] * it['vlrunit'], 4)
                vlrtot_total += vlt_item

                if idx < len(seqs_existentes):
                    # Item já existe nesta posição → UPDATE
                    seq_alvo = seqs_existentes[idx]
                    cur.execute("""
                        UPDATE TGFITE
                           SET CODPROD = :cp, CODVOL = :cv,
                               QTDNEG = :qt, VLRUNIT = :vlu, VLRTOT = :vlt,
                               QTDCONFERIDA = :qt,
                               CODAGREGACAO = NULL
                         WHERE NUNOTA = :n AND SEQUENCIA = :s
                    """, {
                        'n': nunota, 's': seq_alvo,
                        'cp': cp, 'cv': codvol,
                        'qt': it['qtd'], 'vlu': it['vlrunit'], 'vlt': vlt_item,
                    })
                else:
                    # Item novo → reusa helper que cuida de todas as colunas
                    # exigidas pelos triggers Sankhya (TRG_INC_UPD_TGFITE_PRODNFE).
                    item_resp = inserir_item_nota_banco({
                        'NUNOTA':       nunota,
                        'CODPROD':      cp,
                        'QTDNEG':       it['qtd'],
                        'VLRUNIT':      it['vlrunit'],
                        'CODVOL':       codvol,
                        'CODAGREGACAO': None,
                    }, gerar_lote_auto=False, conexao_existente=conn)
                    if not item_resp.get('ok'):
                        return {'ok': False, 'error':
                            f"Falha ao adicionar item CODPROD={cp}: {item_resp.get('error')}"}

            # 5.5 Itens em excesso (lista nova menor que a antiga) → DELETE
            if len(itens_norm) < len(seqs_existentes):
                seqs_remover = seqs_existentes[len(itens_norm):]
                placeholders = ','.join(str(int(s)) for s in seqs_remover)
                cur.execute(
                    f"DELETE FROM TGFITE WHERE NUNOTA = :n AND SEQUENCIA IN ({placeholders})",
                    n=nunota,
                )

            recalcular_totais_nota_banco(nunota, conexao_existente=conn)
            vlrtot_total = round(vlrtot_total, 4)

            # 6. UPDATE TGFFIN — não mexe nos campos de baixa (DHBAIXA/VLRBAIXA/
            # CODEMPBAIXA/CODUSUBAIXA). O bloqueio inicial (linha 1) já garante
            # que só editamos TGFFIN ainda em aberto, mas mesmo assim preserva
            # o estado por consistência: campos de baixa = NULL.
            historico_n = (dados.get('historico')
                           or fin_hist
                           or f'Compra combust. NF {numnota_n}')[:255]
            cur.execute("""
                UPDATE TGFFIN
                   SET CODEMP = :emp, CODPARC = :parc, CODNAT = :nat, CODCENCUS = :cus,
                       NUMNOTA = :nn,
                       DTNEG = :dtneg, DTVENC = :dtvenc, DTVENCINIC = :dtvenc, DTPRAZO = :dtvenc,
                       VLRDESDOB = :vlr, VLRBAIXA = 0,
                       HISTORICO = :hist,
                       DHBAIXA = NULL, CODEMPBAIXA = NULL, CODUSUBAIXA = NULL,
                       DHMOV = SYSDATE, DTALTER = SYSDATE
                 WHERE NUFIN = :nf
            """, {
                'nf': int(fin_nufin),
                'emp': codemp, 'parc': codparc, 'nat': codnat, 'cus': codcencus,
                'nn': numnota_n,
                'dtneg': dtneg_n, 'dtvenc': dtvenc_n,
                'vlr': vlrtot_total,
                'hist': historico_n,
            })

            conn.commit()
            logger.info(
                "Entrada combustível NUNOTA=%s editada (numnota=%s itens=%s vlrtot=%s)",
                nunota, numnota_n, len(itens_norm), vlrtot_total,
            )
            return {
                'ok': True, 'nunota': nunota, 'numnota': numnota_n,
                'nufin': int(fin_nufin), 'qtd_itens': len(itens_norm),
                'vlrtot': float(vlrtot_total),
            }

    except Exception as exc:
        logger.exception("Falha em editar_entrada_combustivel_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


def excluir_entrada_combustivel_banco(nunota: int, motivo: str, codusu: int, nomeusu: str = '') -> dict:
    """B15 (Mai/2026) — Exclui FISICAMENTE uma entrada de combustível (TOP 10).

    DELETE em cascata: TGFFIN → TGFITE → TGFCAB.
    Bloqueia se TGFFIN já estiver baixado (DHBAIXA NOT NULL) — operador deve
    estornar a baixa no Sankhya antes pra reverter financeiro corretamente.

    Mesma estratégia da B6/B12: trigger Sankhya TRG_UPD_TGFCAB bloqueia
    UPDATE STATUSNOTA='E', então é DELETE físico.
    """
    nunota = int(nunota)
    motivo = (motivo or '').strip()
    if not motivo:
        return {'ok': False, 'error': 'Motivo da exclusão é obrigatório.'}
    if len(motivo) > 300:
        motivo = motivo[:300]

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # 1. Verifica estado + NUFIN + DHBAIXA
            cur.execute("""
                SELECT c.STATUSNOTA, f.NUFIN, f.DHBAIXA
                FROM TGFCAB c
                LEFT JOIN TGFFIN f ON f.NUNOTA = c.NUNOTA
                WHERE c.NUNOTA = :n AND c.CODTIPOPER = 10
            """, n=nunota)
            row = cur.fetchone()
            if not row:
                return {'ok': False, 'error': f'Entrada {nunota} não encontrada.'}
            statusnota, nufin, dhbaixa = row[0], row[1], row[2]

            if dhbaixa is not None:
                return {'ok': False, 'error':
                    'Financeiro desta entrada já está baixado. '
                    'Estorne a baixa no Sankhya antes de excluir.'}

            # 2. Audit em log (motivo+usuário) ANTES dos DELETEs
            usu_label = (nomeusu or str(codusu))[:30]
            logger.info(
                "EXCLUSAO entrada combustível NUNOTA=%s nufin=%s por codusu=%s (%s) — motivo: %s",
                nunota, nufin, codusu, usu_label, motivo,
            )

            # 3. DELETE em cascata: TGFFIN → TGFITE → TGFCAB
            if nufin:
                cur.execute("DELETE FROM TGFFIN WHERE NUFIN = :nf", nf=int(nufin))
            cur.execute("DELETE FROM TGFITE WHERE NUNOTA = :n", n=nunota)
            cur.execute(
                "DELETE FROM TGFCAB WHERE NUNOTA = :n AND CODTIPOPER = 10",
                n=nunota,
            )

            conn.commit()
            logger.info(
                "Entrada combustível NUNOTA=%s DELETE físico concluído (statusnota=%s)",
                nunota, statusnota,
            )
            return {'ok': True, 'nunota': nunota}

    except Exception as exc:
        logger.exception("Falha em excluir_entrada_combustivel_banco")
        return {'ok': False, 'error': humanizar_erro_oracle(exc)}


# ==============================================================================
# 📊 DASHBOARD EXECUTIVO — INDICADORES DE SAÚDE DO SISTEMA
# Função aditiva (SELECT puro). Categoria A — Mai/2026.
# Consolidada em 1 conexão pra minimizar round-trips. Cada indicador é uma
# subquery independente; falha de um não derruba os outros (try/except por bloco).
# ==============================================================================

# Threshold pra "tanque crítico" — saldo abaixo desse % vira alerta vermelho
TANQUE_CRITICO_PCT = 20.0

# Threshold pra "lote envelhecido" — alinhado com a constante DIAS_ALERTA_LOTE
# do frontend do Rastreio (rastreio.js).
DIAS_LOTE_ENVELHECIDO = 60


def consultar_indicadores_dashboard():
    """Consolida os 6 indicadores do dashboard home em chamadas paralelas.

    Retorna dict no formato:
      {
        'sem_lote':              {'count': int, 'label': str},
        'aguardando_classif':    {'count': int, 'label': str},
        'vales_abertos':         {'count': int, 'label': str},
        'tanques_criticos':      {'count': int, 'label': str, 'detalhes': [...]},
        'prontos_faturar':       {'count': int, 'label': str},
        'lotes_envelhecidos':    {'count': int, 'label': str},
      }

    Indicadores escolhidos (Mai/2026):
      #1 Pedidos sem lote atribuído (TOP 34, STATUSNOTA <> 'L'/'E', item CODAGREGACAO IS NULL)
      #2 Lotes aguardando classificação (perna C da view ANDRE_IAGRO_SALDO_LOTE)
      #4 Vales em aberto (TOP 13, STATUSNOTA NOT IN ('L', 'E'))
      #5 Tanques com saldo crítico (< TANQUE_CRITICO_PCT % da capacidade)
      #7 Pedidos prontos pra faturar (TOP 34, todos itens com CODAGREGACAO)
      #8 Lotes envelhecidos (DTNEG_ORIGEM < SYSDATE - DIAS_LOTE_ENVELHECIDO e disponíveis)
    """
    indicadores = {}

    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()

            # #1 Pedidos sem lote atribuído
            try:
                cur.execute("""
                    SELECT COUNT(DISTINCT c.NUNOTA)
                    FROM TGFCAB c
                    JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                    WHERE c.CODTIPOPER = 34
                      AND (c.STATUSNOTA IS NULL OR c.STATUSNOTA NOT IN ('L', 'E'))
                      AND i.CODAGREGACAO IS NULL
                """)
                indicadores['sem_lote'] = {
                    'count': int(cur.fetchone()[0] or 0),
                    'label': 'Pedidos sem lote atribuído',
                }
            except Exception as exc:
                logger.exception("Falha indicador sem_lote")
                indicadores['sem_lote'] = {'count': None, 'label': 'Pedidos sem lote atribuído', 'erro': str(exc)[:120]}

            # #2 Lotes aguardando classificação (perna C)
            try:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
                    WHERE STATUS_LINHA = 'AGUARDANDO_CLASSIFICACAO'
                      AND QTD_DISPONIVEL > 0
                """)
                indicadores['aguardando_classif'] = {
                    'count': int(cur.fetchone()[0] or 0),
                    'label': 'Lotes aguardando classificação',
                }
            except Exception as exc:
                logger.exception("Falha indicador aguardando_classif")
                indicadores['aguardando_classif'] = {'count': None, 'label': 'Lotes aguardando classificação', 'erro': str(exc)[:120]}

            # #4 Vales em aberto (TOP 13)
            try:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM TGFCAB
                    WHERE CODTIPOPER = 13
                      AND (STATUSNOTA IS NULL OR STATUSNOTA NOT IN ('L', 'E'))
                """)
                indicadores['vales_abertos'] = {
                    'count': int(cur.fetchone()[0] or 0),
                    'label': 'Vales em aberto',
                }
            except Exception as exc:
                logger.exception("Falha indicador vales_abertos")
                indicadores['vales_abertos'] = {'count': None, 'label': 'Vales em aberto', 'erro': str(exc)[:120]}

            # #7 Pedidos prontos pra faturar (TOP 34 com TODOS itens com CODAGREGACAO)
            try:
                cur.execute("""
                    SELECT COUNT(*) FROM (
                      SELECT c.NUNOTA
                      FROM TGFCAB c
                      WHERE c.CODTIPOPER = 34
                        AND (c.STATUSNOTA IS NULL OR c.STATUSNOTA NOT IN ('L', 'E'))
                        AND EXISTS (SELECT 1 FROM TGFITE i WHERE i.NUNOTA = c.NUNOTA)
                        AND NOT EXISTS (
                          SELECT 1 FROM TGFITE i
                          WHERE i.NUNOTA = c.NUNOTA AND i.CODAGREGACAO IS NULL
                        )
                    )
                """)
                indicadores['prontos_faturar'] = {
                    'count': int(cur.fetchone()[0] or 0),
                    'label': 'Pedidos prontos pra faturar',
                }
            except Exception as exc:
                logger.exception("Falha indicador prontos_faturar")
                indicadores['prontos_faturar'] = {'count': None, 'label': 'Pedidos prontos pra faturar', 'erro': str(exc)[:120]}

            # #8 Lotes envelhecidos (> N dias, ainda disponíveis e vendáveis)
            try:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE
                    WHERE STATUS_LINHA IN ('CLASSIFICADO', 'NAO_CLASSIFICAVEL')
                      AND QTD_DISPONIVEL > 0
                      AND DTNEG_ORIGEM < TRUNC(SYSDATE) - :dias
                """, dias=DIAS_LOTE_ENVELHECIDO)
                indicadores['lotes_envelhecidos'] = {
                    'count': int(cur.fetchone()[0] or 0),
                    'label': f'Lotes com mais de {DIAS_LOTE_ENVELHECIDO} dias',
                }
            except Exception as exc:
                logger.exception("Falha indicador lotes_envelhecidos")
                indicadores['lotes_envelhecidos'] = {'count': None, 'label': f'Lotes com mais de {DIAS_LOTE_ENVELHECIDO} dias', 'erro': str(exc)[:120]}

    except Exception as exc:
        logger.exception("Falha geral no dashboard (conexão Oracle)")
        # Se a conexão caiu, devolve todos os indicadores como erro de infra
        msg = humanizar_erro_oracle(exc)
        for k in ['sem_lote', 'aguardando_classif', 'vales_abertos', 'prontos_faturar', 'lotes_envelhecidos']:
            if k not in indicadores:
                indicadores[k] = {'count': None, 'label': '', 'erro': msg}

    # #5 Tanques com saldo crítico — usa função existente consultar_saldo_combustivel
    # (que já trata SALDO_INICIAL_TANQUE e GREATEST 0 corretamente)
    try:
        saldos = consultar_saldo_combustivel()
        criticos = []
        for r in saldos:
            # tupla retornada: (CODPROD, DESCRPROD, CODVOL, qtd_entrada, qtd_saida,
            #                   qtd_disponivel, capacidade_lt, saldo_inicial, percentual, formato)
            codprod  = int(r[0])
            descr    = r[1]
            disp     = float(r[5] or 0)
            capac    = float(r[6] or 0)
            pct      = float(r[8] or 0)
            if capac > 0 and pct < TANQUE_CRITICO_PCT:
                criticos.append({
                    'codprod': codprod,
                    'descricao': descr,
                    'qtd_disponivel': disp,
                    'capacidade': capac,
                    'percentual': round(pct, 1),
                })
        indicadores['tanques_criticos'] = {
            'count': len(criticos),
            'label': f'Tanques com saldo abaixo de {int(TANQUE_CRITICO_PCT)}%',
            'detalhes': criticos,
        }
    except Exception as exc:
        logger.exception("Falha indicador tanques_criticos")
        indicadores['tanques_criticos'] = {'count': None, 'label': 'Tanques com saldo crítico', 'erro': str(exc)[:120], 'detalhes': []}

    return indicadores


# ==============================================================================
# 📋 AUDITORIA UNIVERSAL — AD_AUDITORIA_GERAL (Mai/2026)
# Helper Categoria B (INSERT em tabela nova). Tolerante a falha.
# Sempre chamado DEPOIS do commit da operação principal — se este INSERT
# falhar, a operação não é desfeita (mesmo padrão do _registrar_audit_rastreio).
# ==============================================================================

# Módulos permitidos (alinhado com CK_AD_AUDIT_MODULO da DDL)
MODULOS_AUDIT = (
    'venda', 'combustivel', 'rastreio', 'comercial',
    'entrada', 'classificacao', 'email',
)


def registrar_auditoria(
    modulo: str,
    operacao: str,
    *,
    tabela_alvo: Optional[str] = None,
    registro_id: Optional[Any] = None,
    codusu: Optional[int] = None,
    nomeusu: Optional[str] = None,
    snapshot_antes: Optional[dict] = None,
    snapshot_depois: Optional[dict] = None,
    observacao: Optional[str] = None,
) -> None:
    """Grava 1 evento na AD_AUDITORIA_GERAL.

    Tolerante a falha — se INSERT falhar, registra warning e NÃO levanta
    exceção. A operação principal JÁ foi commitada quando este helper é
    chamado, então perder a auditoria é menos pior que reverter a operação.
    Mesmo padrão do _registrar_audit_rastreio existente.

    Parâmetros:
      modulo: um de MODULOS_AUDIT (venda/combustivel/rastreio/...).
      operacao: nome da operação (ex: 'CRIAR_PEDIDO', 'EDITAR_REQUISICAO').
      tabela_alvo: tabela Oracle principal afetada (ex: 'TGFCAB').
      registro_id: NUNOTA/ID/etc — convertido pra string.
      codusu, nomeusu: do request.session.
      snapshot_antes: dict com estado anterior (None em CRIAR).
      snapshot_depois: dict com estado posterior (None em EXCLUIR).
      observacao: texto livre opcional (motivo, contexto).

    Não retorna nada — efeitos colaterais via logger.warning em caso de falha.
    """
    try:
        import json
        snap_a = json.dumps(snapshot_antes, ensure_ascii=False, default=str) if snapshot_antes else None
        snap_d = json.dumps(snapshot_depois, ensure_ascii=False, default=str) if snapshot_depois else None
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO SANKHYA.AD_AUDITORIA_GERAL (
                    ID, MODULO, OPERACAO, TABELA_ALVO, REGISTRO_ID,
                    CODUSU, NOMEUSU, SNAPSHOT_ANTES, SNAPSHOT_DEPOIS, OBSERVACAO
                ) VALUES (
                    SANKHYA.SEQ_AD_AUDITORIA_GERAL.NEXTVAL,
                    :modulo, :operacao, :tabela_alvo, :registro_id,
                    :codusu, :nomeusu, :snap_a, :snap_d, :observacao
                )
                """,
                modulo=modulo,
                operacao=operacao,
                tabela_alvo=tabela_alvo,
                registro_id=str(registro_id) if registro_id is not None else None,
                codusu=codusu,
                nomeusu=nomeusu,
                snap_a=snap_a,
                snap_d=snap_d,
                observacao=observacao,
            )
            conn.commit()
    except Exception as exc:
        logger.warning(
            "Falha ao gravar AD_AUDITORIA_GERAL (modulo=%s, operacao=%s, registro_id=%s): %s",
            modulo, operacao, registro_id, exc,
        )


# ==============================================================================
# 📋 CONSULTA DE AUDITORIA (Lote A — leitura paginada com filtros)
# ==============================================================================

def _ler_clob(v):
    """Materializa um LOB Oracle em string. Tolerante a None."""
    if v is None:
        return None
    if hasattr(v, 'read'):
        try:
            return v.read()
        except Exception:
            return str(v)
    return v


def consultar_auditoria_paginada(filtros: dict = None, limite: int = 50, offset: int = 0):
    """Lista eventos de AD_AUDITORIA_GERAL com filtros + paginação Oracle 11g.

    Filtros aceitos (todos opcionais):
      - modulo:       str | None
      - operacao:     str | None
      - codusu:       int | None
      - registro_id:  str | None       (busca exata em REGISTRO_ID)
      - busca:        str | None       (LIKE em snapshot_antes/depois/observacao)
      - data_ini:     'YYYY-MM-DD'
      - data_fim:     'YYYY-MM-DD'

    Retorna dict:
      {
        'registros': [
          {id, modulo, operacao, tabela_alvo, registro_id, codusu, nomeusu,
           dt (ISO), snapshot_antes (dict|None), snapshot_depois (dict|None),
           observacao},
          ...
        ],
        'total':         int,   # COUNT(*) com mesmos filtros
        'tem_mais':      bool,  # se há mais páginas
        'pagina_size':   int,
        'offset_atual':  int,
      }
    """
    import json
    filtros = filtros or {}
    limite = max(1, min(int(limite or 50), 500))
    offset = max(0, int(offset or 0))

    where = ['1=1']
    binds = {}

    if filtros.get('modulo'):
        where.append('MODULO = :modulo')
        binds['modulo'] = str(filtros['modulo']).strip()
    if filtros.get('operacao'):
        where.append('OPERACAO = :operacao')
        binds['operacao'] = str(filtros['operacao']).strip()
    if filtros.get('codusu'):
        where.append('CODUSU = :codusu')
        binds['codusu'] = int(filtros['codusu'])
    if filtros.get('registro_id'):
        where.append('REGISTRO_ID = :reg_id')
        binds['reg_id'] = str(filtros['registro_id']).strip()
    if filtros.get('data_ini'):
        where.append("DT >= TO_DATE(:dt_ini, 'YYYY-MM-DD')")
        binds['dt_ini'] = str(filtros['data_ini']).strip()
    if filtros.get('data_fim'):
        where.append("DT < TO_DATE(:dt_fim, 'YYYY-MM-DD') + 1")
        binds['dt_fim'] = str(filtros['data_fim']).strip()
    if filtros.get('busca'):
        where.append(
            "(UPPER(NOMEUSU) LIKE :busca "
            "OR UPPER(OBSERVACAO) LIKE :busca "
            "OR DBMS_LOB.INSTR(UPPER(SNAPSHOT_ANTES), :busca_raw) > 0 "
            "OR DBMS_LOB.INSTR(UPPER(SNAPSHOT_DEPOIS), :busca_raw) > 0)"
        )
        b = str(filtros['busca']).strip().upper()
        binds['busca']     = f"%{b}%"
        binds['busca_raw'] = b

    where_sql = ' AND '.join(where)

    sql_count = f"SELECT COUNT(*) FROM SANKHYA.AD_AUDITORIA_GERAL WHERE {where_sql}"

    # Paginação Oracle 11g compatível (ROW_NUMBER) — ver gotchas
    sql_pag = f"""
        SELECT ID, MODULO, OPERACAO, TABELA_ALVO, REGISTRO_ID,
               CODUSU, NOMEUSU, DT, SNAPSHOT_ANTES, SNAPSHOT_DEPOIS, OBSERVACAO
        FROM (
            SELECT t.*, ROW_NUMBER() OVER (ORDER BY DT DESC, ID DESC) AS rn
            FROM SANKHYA.AD_AUDITORIA_GERAL t
            WHERE {where_sql}
        )
        WHERE rn BETWEEN :inicio AND :fim
        ORDER BY DT DESC, ID DESC
    """
    binds_pag = dict(binds)
    binds_pag['inicio'] = offset + 1
    binds_pag['fim']    = offset + limite

    total = 0
    registros = []
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute(sql_count, binds)
            total = int(cur.fetchone()[0] or 0)

            cur.execute(sql_pag, binds_pag)
            for r in cur.fetchall():
                snap_a_raw = _ler_clob(r[8])
                snap_d_raw = _ler_clob(r[9])
                snap_a = None
                snap_d = None
                try:
                    snap_a = json.loads(snap_a_raw) if snap_a_raw else None
                except Exception:
                    snap_a = {'_raw': snap_a_raw[:500]} if snap_a_raw else None
                try:
                    snap_d = json.loads(snap_d_raw) if snap_d_raw else None
                except Exception:
                    snap_d = {'_raw': snap_d_raw[:500]} if snap_d_raw else None

                registros.append({
                    'id':              int(r[0]),
                    'modulo':          r[1],
                    'operacao':        r[2],
                    'tabela_alvo':     r[3],
                    'registro_id':     r[4],
                    'codusu':          int(r[5]) if r[5] is not None else None,
                    'nomeusu':         r[6],
                    'dt':              r[7].strftime('%Y-%m-%d %H:%M:%S') if r[7] else None,
                    'snapshot_antes':  snap_a,
                    'snapshot_depois': snap_d,
                    'observacao':      r[10],
                })
    except Exception as exc:
        logger.exception("Falha em consultar_auditoria_paginada")
        raise

    return {
        'registros':    registros,
        'total':        total,
        'tem_mais':     (offset + len(registros)) < total,
        'pagina_size':  limite,
        'offset_atual': offset,
    }


def listar_filtros_distintos_auditoria():
    """Pré-carrega valores distintos pra popular os filtros da tela:
      - modulos (lista de strings)
      - operacoes (lista de strings)
      - usuarios (lista de {codusu, nomeusu})

    Limita pra evitar selects gigantes (auditoria nova, vai crescer).
    Retorna dict pronto para JsonResponse.
    """
    out = {'modulos': [], 'operacoes': [], 'usuarios': []}
    try:
        with obter_conexao_oracle() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT MODULO FROM SANKHYA.AD_AUDITORIA_GERAL ORDER BY MODULO")
            out['modulos'] = [r[0] for r in cur.fetchall() if r[0]]

            cur.execute("SELECT DISTINCT OPERACAO FROM SANKHYA.AD_AUDITORIA_GERAL ORDER BY OPERACAO")
            out['operacoes'] = [r[0] for r in cur.fetchall() if r[0]]

            cur.execute("""
                SELECT CODUSU, MAX(NOMEUSU) as NOMEUSU
                FROM SANKHYA.AD_AUDITORIA_GERAL
                WHERE CODUSU IS NOT NULL
                GROUP BY CODUSU
                ORDER BY MAX(NOMEUSU)
            """)
            out['usuarios'] = [
                {'codusu': int(r[0]), 'nomeusu': r[1] or f"Usuário {r[0]}"}
                for r in cur.fetchall()
            ]
    except Exception as exc:
        logger.warning("Falha em listar_filtros_distintos_auditoria: %s", exc)
    return out


# ==============================================================================
# 🏷  ETIQUETAS SAFE TRACE / IAGRO (Mai/2026)
# Leitura pura dos dados pra renderizar etiquetas 100×50mm de rastreabilidade.
# Estrutura: 1 etiqueta por CAIXA do pedido. Operador clica "Imprimir" no
# header do pedido (todos os itens) ou na linha de cada produto (subset).
# Peso da caixa vem de TGFITE.QTDFIXADA, populada por atribuir_lote_item_pedido
# a partir da TOP 11 origem do lote.
# ==============================================================================

def consultar_dados_etiqueta_pedido(nunota: int, codprod: int | None = None) -> dict:
    """Retorna dados pra renderizar etiquetas de rastreabilidade de um pedido.

    Filtros:
        - ``nunota`` obrigatório (TGFCAB do pedido — pode ser TOP 34/35/37).
        - ``codprod`` opcional: limita aos itens daquele CODPROD específico
          (botão "imprimir etiquetas deste produto" na produto-linha).

    Inclui apenas itens com ``CODAGREGACAO`` ≠ NULL — sem lote, sem
    rastreabilidade, sem etiqueta. Itens sem ``QTDFIXADA`` (peso da caixa)
    vão no retorno mas o frontend detecta e mostra aviso ao operador.

    Retorna:
        {
          'pedido': {
            'nunota', 'numnota', 'dtneg', 'codemp',
            'empresa': {'razao', 'nome_fantasia', 'cgc',
                        'latitude', 'longitude', 'endereco', 'cep'},
          },
          'itens': [
            {'sequencia', 'codprod', 'descrprod', 'codvol',
             'qtdneg', 'qtdfixada', 'codagregacao', 'referencia_ean'},
            ...
          ]
        }
        ou {'pedido': None, 'itens': []} se nada bater no filtro.
    """
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()

        # TSIEMP varia entre instalações Sankhya — algumas colunas de endereço
        # podem não existir. Detectamos via _existe_coluna (cacheado 1× por
        # processo) e montamos o SELECT incluindo só o que existe; o resto
        # vira NULL explícito pra preservar a ordem dos índices.
        col_endereco = None
        for cand in ('ENDERECO', 'NOMEEND', 'LOGRADOURO'):
            if _existe_coluna(cur, 'TSIEMP', cand):
                col_endereco = cand
                break
        tem_cep = _existe_coluna(cur, 'TSIEMP', 'CEP')

        sel_endereco = f"e.{col_endereco}" if col_endereco else "NULL"
        sel_cep      = "e.CEP"             if tem_cep      else "NULL"

        sql = f"""
            SELECT
                c.NUNOTA, c.NUMNOTA, c.DTNEG, c.CODEMP,
                e.RAZAOSOCIAL, e.NOMEFANTASIA, e.CGC,
                e.LATITUDE, e.LONGITUDE,
                {sel_endereco}, {sel_cep},
                i.SEQUENCIA, i.CODPROD,
                pr.DESCRPROD, i.CODVOL,
                NVL(i.QTDNEG, 0), NVL(i.QTDFIXADA, 0),
                i.CODAGREGACAO, pr.REFERENCIA
              FROM TGFCAB c
              LEFT JOIN TSIEMP e  ON e.CODEMP = c.CODEMP
              JOIN TGFITE i       ON i.NUNOTA = c.NUNOTA
              LEFT JOIN TGFPRO pr ON pr.CODPROD = i.CODPROD
             WHERE c.NUNOTA = :n
               AND i.CODAGREGACAO IS NOT NULL
        """
        params: dict = {'n': int(nunota)}
        if codprod is not None:
            sql += " AND i.CODPROD = :p"
            params['p'] = int(codprod)
        sql += " ORDER BY i.SEQUENCIA"
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        return {'pedido': None, 'itens': []}

    r0 = rows[0]
    pedido = {
        'nunota':  int(r0[0]) if r0[0] is not None else None,
        'numnota': int(r0[1]) if r0[1] is not None else None,
        'dtneg':   r0[2],
        'codemp':  int(r0[3]) if r0[3] is not None else None,
        'empresa': {
            'razao':         r0[4] or '',
            'nome_fantasia': r0[5] or '',
            'cgc':           r0[6] or '',
            'latitude':      float(r0[7])  if r0[7]  is not None else None,
            'longitude':     float(r0[8])  if r0[8]  is not None else None,
            'endereco':      r0[9]  or '',
            'cep':           r0[10] or '',
        },
    }
    itens = [{
        'sequencia':      int(r[11]) if r[11] is not None else None,
        'codprod':        int(r[12]) if r[12] is not None else None,
        'descrprod':      r[13] or '',
        'codvol':         r[14] or 'KG',
        'qtdneg':         float(r[15] or 0),
        'qtdfixada':      float(r[16] or 0),
        'codagregacao':   str(r[17]) if r[17] is not None else None,
        'referencia_ean': r[18] or '',
    } for r in rows]

    return {'pedido': pedido, 'itens': itens}


def calcular_qtd_etiquetas(qtd_total_kg: float, peso_caixa_kg: float) -> int:
    """Calcula quantas etiquetas imprimir pra um item.

    Arredonda pra cima — caixa fracionária também recebe etiqueta porque
    fisicamente é uma caixa diferenciada que sai do galpão.

    Exemplos:
        300 kg ÷ caixa 10 kg = 30 etiquetas
        1000 kg ÷ caixa 20 kg = 50 etiquetas
        305 kg ÷ caixa 10 kg = 31 etiquetas (a última caixa tem 5 kg)

    Retorna 0 se algum dos valores for ≤ 0 ou inválido — frontend trata
    como "peso da caixa não definido" e bloqueia impressão com aviso.
    """
    import math
    qtd  = float(qtd_total_kg or 0)
    peso = float(peso_caixa_kg or 0)
    if peso <= 0 or qtd <= 0:
        return 0
    return math.ceil(qtd / peso)
