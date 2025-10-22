"""
Teste direto com Oracle - INSERT mínimo TGFFIN
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

from sankhya_integration.services.oracle_conn import get_connection

def test_minimal_insert():
    print(f"\n{'='*80}")
    print(f"🧪 TESTE INSERT MÍNIMO - Testando valores literais")
    print(f"{'='*80}\n")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Gerar NUFIN
            try:
                cur.execute("SELECT SQ_TGFFIN_NUFIN.NEXTVAL FROM DUAL")
                nufin = cur.fetchone()[0]
            except:
                cur.execute("SELECT NVL(MAX(NUFIN), 0) + 1 FROM TGFFIN")
                nufin = cur.fetchone()[0]
            
            print(f"NUFIN gerado: {nufin}\n")
            
            # Testar INSERT com apenas valores literais problemáticos
            print("Testando INSERT com 68 colunas e 68 valores...\n")
            
            try:
                cur.execute("""
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
                        :nf, 1, 93227, SYSDATE, 1, SYSDATE,
                        SYSDATE, SYSDATE, 536, 11, SYSDATE,
                        33, 2, 20010100, 10100, 0,
                        0, 0, 13, 0, 0,
                        0, 0, 0, 'N', 0,
                        0, 0, 1, 0, 1,
                        0, 0, TO_DATE('01/01/1998', 'DD/MM/YYYY'), 0, 'N',
                        'E', 'A', 93227, 93227, 'N',
                        SYSDATE, 0, 'S', 'S', 0,
                        SYSDATE, 0, 0, 0, 0,
                        1, 0, 0, 0, 0,
                        0, 0, 0, 0, 0,
                        0, SYSDATE, 'S', 0, 'S',
                        0, 0
                    )
                """, nf=nufin)
                
                print("✅ INSERT executado com sucesso!")
                print(f"   NUFIN: {nufin}")
                
                conn.rollback()
                print("\n⚠️  ROLLBACK executado (teste)")
                
            except Exception as e:
                print(f"❌ ERRO NO INSERT: {e}\n")
                
                # Agora vamos testar cada grupo de valores
                print("🔍 Testando valores individuais...\n")
                
                tests = [
                    ("DTVENC com SYSDATE", "SELECT SYSDATE FROM DUAL"),
                    ("DESDOBRAMENTO = 1", "SELECT 1 FROM DUAL"),
                    ("TIPMULTA = 1", "SELECT 1 FROM DUAL"),
                    ("TIPJURO = 1", "SELECT 1 FROM DUAL"),
                    ("ISSRETIDO = 'N'", "SELECT 'N' FROM DUAL"),
                    ("AUTORIZADO = 'N'", "SELECT 'N' FROM DUAL"),
                    ("RECDESP = 'E'", "SELECT 'E' FROM DUAL"),
                    ("PROVISAO = 'A'", "SELECT 'A' FROM DUAL"),
                    ("RATEADO = 'N'", "SELECT 'N' FROM DUAL"),
                    ("IRFRETIDO = 'S'", "SELECT 'S' FROM DUAL"),
                    ("INSSRETIDO = 'S'", "SELECT 'S' FROM DUAL"),
                    ("FINCONFIRMADO = 'S'", "SELECT 'S' FROM DUAL"),
                    ("RECEBIDO = 'S'", "SELECT 'S' FROM DUAL"),
                    ("CODBCO = 33", "SELECT 33 FROM DUAL"),
                    ("CODCTABCOINT = 2", "SELECT 2 FROM DUAL"),
                    ("CODTIPTIT = 13", "SELECT 13 FROM DUAL"),
                    ("CODNAT = 20010100", "SELECT 20010100 FROM DUAL"),
                    ("CODCENCUS = 10100", "SELECT 10100 FROM DUAL"),
                    ("DATA 01/01/1998", "SELECT TO_DATE('01/01/1998', 'DD/MM/YYYY') FROM DUAL"),
                ]
                
                for desc, sql in tests:
                    try:
                        cur.execute(sql)
                        val = cur.fetchone()[0]
                        print(f"   ✅ {desc:30} = {repr(val)}")
                    except Exception as e2:
                        print(f"   ❌ {desc:30} ERRO: {e2}")
                
                import traceback
                traceback.print_exc()
            
            print(f"\n{'='*80}\n")
            
    except Exception as e:
        print(f"\n❌ ERRO GERAL: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_minimal_insert()
