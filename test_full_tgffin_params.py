"""
Teste completo simulando exatamente o que criar_tgffin faz
"""

import sys
import os
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection, get_params

def test_insert_tgffin(nunota: int):
    print(f"\n{'='*80}")
    print(f"🧪 TESTE COMPLETO INSERT TGFFIN - NUNOTA {nunota}")
    print(f"{'='*80}\n")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Buscar dados (EXATAMENTE como no código)
            print("1️⃣ Buscando dados da TGFCAB...")
            cur.execute("""
                SELECT 
                    CODEMP, NUMNOTA, DTNEG, CODPARC, CODTIPOPER, 
                    CODNAT, CODCENCUS, DTENTSAI, VLRNOTA, DTFATUR
                FROM TGFCAB 
                WHERE NUNOTA = :n
            """, n=nunota)
            
            row = cur.fetchone()
            if not row:
                print(f"❌ NUNOTA não encontrada")
                return
            
            (CODEMP, NUMNOTA, DTNEG, CODPARC, CODTIPOPER, 
             CODNAT, CODCENCUS, DTENTSAI, VLRNOTA, DTFATUR) = row
            
            # Conversões (EXATAMENTE como no código corrigido)
            CODNAT = int(CODNAT) if CODNAT and str(CODNAT).strip() else None
            CODCENCUS = int(CODCENCUS) if CODCENCUS and str(CODCENCUS).strip() else None
            VLRNOTA = float(VLRNOTA) if VLRNOTA is not None else 0.0
            
            print(f"   ✅ CODEMP={CODEMP}, NUMNOTA={NUMNOTA}, CODPARC={CODPARC}")
            print(f"   ✅ CODNAT={CODNAT}, CODCENCUS={CODCENCUS}, VLRNOTA={VLRNOTA}")
            
            # 2. Buscar DHTIPOPER
            print("\n2️⃣ Buscando DHTIPOPER...")
            cur.execute("""
                SELECT DHALTER 
                FROM (
                    SELECT DHALTER 
                    FROM TGFTOP 
                    WHERE CODTIPOPER = :top 
                    ORDER BY DHALTER DESC
                ) 
                WHERE ROWNUM = 1
            """, top=CODTIPOPER)
            
            dhtipoper_row = cur.fetchone()
            DHTIPOPER = dhtipoper_row[0] if dhtipoper_row else None
            print(f"   ✅ DHTIPOPER={repr(DHTIPOPER)}")
            
            # 3. Gerar NUFIN
            print("\n3️⃣ Gerando NUFIN...")
            try:
                cur.execute("SELECT SQ_TGFFIN_NUFIN.NEXTVAL FROM DUAL")
                NUFIN = cur.fetchone()[0]
                print(f"   ✅ NUFIN (sequence): {NUFIN}")
            except Exception as e:
                print(f"   ⚠️  Sequence falhou: {e}")
                cur.execute("SELECT NVL(MAX(NUFIN), 0) + 1 FROM TGFFIN")
                NUFIN = cur.fetchone()[0]
                print(f"   ✅ NUFIN (MAX+1): {NUFIN}")
            
            # 4. Calcular datas
            print("\n4️⃣ Calculando datas...")
            if DTFATUR:
                base_date = DTFATUR if isinstance(DTFATUR, datetime) else datetime.now()
            else:
                base_date = DTNEG if isinstance(DTNEG, datetime) else datetime.now()
            
            params = get_params()
            CODBCO = int(params.get('FINANCEIRO_BANCO_PADRAO', 33))
            CODCTABCOINT = int(params.get('FINANCEIRO_CONTA_BANCARIA', 2))
            CODTIPTIT = int(params.get('FINANCEIRO_TIPO_TITULO', 13))
            DIAS_VENC = int(params.get('FINANCEIRO_DIAS_VENCIMENTO', 30))
            
            dtvenc = base_date + timedelta(days=DIAS_VENC)
            
            print(f"   ✅ Base: {base_date.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"   ✅ Vencimento: {dtvenc.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"   ✅ CODBCO={CODBCO}, CODCTABCOINT={CODCTABCOINT}, CODTIPTIT={CODTIPTIT}")
            
            # 5. Montar dicionário de parâmetros
            print("\n5️⃣ Montando parâmetros do INSERT...")
            params_dict = {
                'NUFIN': int(NUFIN),
                'CODEMP': int(CODEMP),
                'NUMNOTA': int(NUMNOTA) if NUMNOTA else None,
                'DTNEG': base_date,
                'DTVENC': dtvenc,
                'CODPARC': int(CODPARC),
                'CODTIPOPER': int(CODTIPOPER),
                'DHTIPOPER': DHTIPOPER,
                'CODBCO': int(CODBCO),
                'CODCTABCOINT': int(CODCTABCOINT),
                'CODNAT': CODNAT,
                'CODCENCUS': CODCENCUS,
                'CODTIPTIT': int(CODTIPTIT),
                'VLRDESDOB': float(VLRNOTA),
                'NUNOTA': int(nunota),
                'DTENTSAI': DTENTSAI,
                'DTPRAZO': dtvenc
            }
            
            print("   📋 Parâmetros:")
            for k, v in params_dict.items():
                tipo = type(v).__name__
                print(f"      {k:15} = {repr(v):30} ({tipo})")
            
            # 6. Validar cada parâmetro
            print("\n6️⃣ Validando tipos dos parâmetros...")
            erros = []
            for k, v in params_dict.items():
                if v is None:
                    print(f"   ⚠️  {k}: None (NULL no Oracle)")
                elif isinstance(v, (int, float)):
                    print(f"   ✅ {k}: {type(v).__name__} OK")
                elif isinstance(v, datetime):
                    print(f"   ✅ {k}: datetime OK")
                else:
                    erros.append(f"{k} tem tipo inválido: {type(v).__name__}")
                    print(f"   ❌ {k}: {type(v).__name__} - INVÁLIDO!")
            
            if erros:
                print(f"\n❌ ERROS ENCONTRADOS:")
                for e in erros:
                    print(f"   - {e}")
                return
            
            print("\n✅ Todos os parâmetros são válidos!")
            
            print(f"\n{'='*80}\n")
            
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    nunota_teste = 93227
    
    if len(sys.argv) > 1:
        nunota_teste = int(sys.argv[1])
    
    test_insert_tgffin(nunota_teste)
