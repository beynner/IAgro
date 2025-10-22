"""
Contar colunas do INSERT TGFFIN
"""

sql_insert = """
INSERT INTO TGFFIN (
    NUFIN, CODEMP, NUMNOTA, DTNEG, DESDOBRAMENTO, DHMOV, 
    DTVENCINIC, DTVENC, CODPARC, CODTIPOPER, DHTIPOPER, 
    CODBCO, CODCTABCOINT, CODNAT, CODCENCUS, CODPROJ, 
    CODVEND, CODMOEDA, CODTIPTIT, VLRDESDOB, VLRVENDOR, 
    VLRIRF, VLRISS, DESPCART, ISSRETIDO, VLRDESC, 
    VLRMULTA, VLRINSS, TIPMULTA, VLRJURO, TIPJURO, 
    BASEICMS, ALIQICMS, DHTIPOPERBAIXA, VLRBAIXA, AUTORIZADO, 
    RECDESP, PROVISAO, ORIGEM, NUNOTA, RATEADO, 
    DTENTSAI, VLRPROV, IRFRETIDO, INSSRETIDO, CARTAODESC, 
    DTALTER, NUMCONTRATO, ORDEMCARGA, CODVEICULO, CODUSU, 
    SEQUENCIA, VLRDESCEMBUT, VLRJUROEMBUT, VLRMULTAEMBUT, VLRMOEDA, 
    VLRMOEDABAIXA, VLRMULTANEGOC, VLRJURONEGOC, VLRMULTALIB, VLRJUROLIB, 
    VLRALIBERAR, DTPRAZO, FINCONFIRMADO, VLRGNREDOIS, RECEBIDO, 
    VLRDESDOBCALC, NUMOCORRENCIAS
) VALUES (
    :NUFIN, :CODEMP, :NUMNOTA, :DTNEG, 1, SYSDATE,
    :DTVENC, :DTVENC, :CODPARC, :CODTIPOPER, :DHTIPOPER,
    :CODBCO, :CODCTABCOINT, :CODNAT, :CODCENCUS, 0,
    0, 0, :CODTIPTIT, :VLRDESDOB, 0,
    0, 0, 0, 'N', 0,
    0, 0, 1, 0, 1,
    0, 0, TO_DATE('01/01/1998', 'DD/MM/YYYY'), 0, 'N',
    'E', 'A', :NUNOTA, :NUNOTA, 'N',
    :DTENTSAI, 0, 'S', 'S', 0,
    SYSDATE, 0, 0, 0, 0,
    1, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, :DTPRAZO, 'S', 0, 'S',
    0, 0
)
"""

# Extrair colunas
import re

# Pegar parte do INSERT INTO (...)
columns_part = re.search(r'INSERT INTO TGFFIN \((.*?)\) VALUES', sql_insert, re.DOTALL)
if columns_part:
    columns_text = columns_part.group(1)
    columns = [c.strip() for c in columns_text.split(',')]
    print(f"📋 Total de colunas: {len(columns)}\n")
    for i, col in enumerate(columns, 1):
        print(f"{i:2}. {col}")

# Pegar parte do VALUES (...)
values_part = re.search(r'VALUES \((.*?)\)', sql_insert, re.DOTALL)
if values_part:
    values_text = values_part.group(1)
    # Separar por vírgulas, mas cuidado com funções TO_DATE que têm vírgulas
    values = []
    depth = 0
    current = ""
    for char in values_text:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            values.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        values.append(current.strip())
    
    print(f"\n📊 Total de valores: {len(values)}\n")
    for i, val in enumerate(values, 1):
        print(f"{i:2}. {val[:60]}")
    
    print(f"\n{'='*80}")
    if len(columns) == len(values):
        print(f"✅ Quantidade de colunas ({len(columns)}) == valores ({len(values)})")
    else:
        print(f"❌ ERRO: colunas ({len(columns)}) != valores ({len(values)})")
        print(f"   Diferença: {abs(len(columns) - len(values))}")
