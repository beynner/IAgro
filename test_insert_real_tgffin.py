"""
Teste REAL do INSERT TGFFIN com os dados da NUNOTA 93227
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

def test_real_insert(nunota: int):
    print(f"\n{'='*80}")
    print(f"🧪 TESTE REAL INSERT TGFFIN - NUNOTA {nunota}")
    print(f"{'='*80}\n")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Buscar dados
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
            
            # Conversões
            CODNAT = int(CODNAT) if CODNAT and str(CODNAT).strip() else None
            CODCENCUS = int(CODCENCUS) if CODCENCUS and str(CODCENCUS).strip() else None
            VLRNOTA = float(VLRNOTA) if VLRNOTA is not None else 0.0
            
            # 2. Buscar DHTIPOPER
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
            
            # 3. Gerar NUFIN
            try:
                cur.execute("SELECT SQ_TGFFIN_NUFIN.NEXTVAL FROM DUAL")
                NUFIN = cur.fetchone()[0]
            except Exception:
                cur.execute("SELECT NVL(MAX(NUFIN), 0) + 1 FROM TGFFIN")
                NUFIN = cur.fetchone()[0]
            
            # 4. Calcular datas
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
            
            print(f"📋 Dados preparados:")
            print(f"   NUFIN={NUFIN}, CODEMP={CODEMP}, CODPARC={CODPARC}")
            print(f"   CODNAT={CODNAT}, CODCENCUS={CODCENCUS}")
            print(f"   VLRNOTA={VLRNOTA}, DTVENC={dtvenc}")
            
            # 5. TENTAR O INSERT REAL via criar_tgffin (testar função atualizada)
            from sankhya_integration.services.oracle_conn import criar_tgffin

            print(f"\n🔥 EXECUTANDO criar_tgffin({nunota})...\n")
            res = criar_tgffin(nunota)
            print('Resultado criar_tgffin:', res)
            print(f"\n⚠️  Nota: criar_tgffin faz commit isolado em produção; este teste NÃO faz rollback automático")
            
            print(f"\n{'='*80}\n")
            
    except Exception as e:
        print(f"\n❌ ERRO GERAL: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    nunota_teste = 93227
    
    if len(sys.argv) > 1:
        nunota_teste = int(sys.argv[1])
    
    test_real_insert(nunota_teste)
