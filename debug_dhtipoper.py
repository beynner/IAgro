"""
Script para verificar o valor de DHTIPOPER que pode estar causando ORA-01722
"""

import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

def debug_dhtipoper(nunota: int):
    print(f"\n{'='*80}")
    print(f"🔍 VERIFICANDO DHTIPOPER - NUNOTA {nunota}")
    print(f"{'='*80}\n")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Buscar CODTIPOPER da nota
            cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
            row = cur.fetchone()
            
            if not row:
                print(f"❌ NUNOTA {nunota} não encontrada")
                return
            
            codtipoper = row[0]
            print(f"📋 CODTIPOPER da nota: {codtipoper}")
            
            # Buscar DHTIPOPER da TOP
            cur.execute("""
                SELECT DHALTER, CODTIPOPER, DESCROPER 
                FROM TGFTOP 
                WHERE CODTIPOPER = :top 
                ORDER BY DHALTER DESC
            """, top=codtipoper)
            
            rows = cur.fetchall()
            
            if not rows:
                print(f"❌ Nenhum registro encontrado na TGFTOP para CODTIPOPER={codtipoper}")
                return
            
            print(f"\n✅ Encontrados {len(rows)} registro(s) na TGFTOP:")
            for i, r in enumerate(rows, 1):
                dhalter, cod, desc = r
                print(f"\n  [{i}] CODTIPOPER: {cod}")
                print(f"      DESCROPER:  {desc}")
                print(f"      DHALTER:    {repr(dhalter)} (tipo: {type(dhalter).__name__})")
            
            # Pegar o mais recente (que é o que o código usa)
            dhtipoper = rows[0][0]
            print(f"\n🎯 VALOR SELECIONADO (mais recente):")
            print(f"   DHTIPOPER: {repr(dhtipoper)}")
            print(f"   Tipo:      {type(dhtipoper).__name__}")
            
            # Testar se pode ser usado no INSERT
            print(f"\n🧪 TESTE DE INSERÇÃO:")
            try:
                cur.execute("""
                    SELECT :val FROM DUAL
                """, val=dhtipoper)
                result = cur.fetchone()[0]
                print(f"   ✅ Valor aceito pelo Oracle: {repr(result)}")
            except Exception as e:
                print(f"   ❌ ERRO ao testar valor: {e}")
            
            print(f"\n{'='*80}\n")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    nunota_teste = 93227
    
    if len(sys.argv) > 1:
        nunota_teste = int(sys.argv[1])
    
    debug_dhtipoper(nunota_teste)
