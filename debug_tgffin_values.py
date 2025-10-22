"""
Script para diagnosticar valores da TGFCAB antes de criar TGFFIN
Útil para identificar problemas com ORA-01722 (invalid number)
"""

import sys
import os

# Adicionar o diretório raiz ao PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection

def debug_tgfcab_values(nunota: int):
    """
    Mostra todos os valores da TGFCAB que serão usados no TGFFIN
    """
    print(f"\n{'='*80}")
    print(f"🔍 DIAGNÓSTICO - NUNOTA {nunota}")
    print(f"{'='*80}\n")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Buscar dados do cabeçalho
            cur.execute("""
                SELECT 
                    NUNOTA,
                    CODEMP, 
                    NUMNOTA, 
                    DTNEG, 
                    CODPARC, 
                    CODTIPOPER,
                    CODNAT, 
                    CODCENCUS, 
                    DTENTSAI, 
                    VLRNOTA, 
                    DTFATUR,
                    STATUSNOTA
                FROM TGFCAB 
                WHERE NUNOTA = :n
            """, n=nunota)
            
            row = cur.fetchone()
            
            if not row:
                print(f"❌ NUNOTA {nunota} não encontrada na TGFCAB")
                return
            
            (NUNOTA, CODEMP, NUMNOTA, DTNEG, CODPARC, CODTIPOPER, 
             CODNAT, CODCENCUS, DTENTSAI, VLRNOTA, DTFATUR, STATUSNOTA) = row
            
            print("📋 VALORES BRUTOS DO BANCO:")
            print(f"  NUNOTA:      {repr(NUNOTA)} (tipo: {type(NUNOTA).__name__})")
            print(f"  CODEMP:      {repr(CODEMP)} (tipo: {type(CODEMP).__name__})")
            print(f"  NUMNOTA:     {repr(NUMNOTA)} (tipo: {type(NUMNOTA).__name__})")
            print(f"  DTNEG:       {repr(DTNEG)} (tipo: {type(DTNEG).__name__})")
            print(f"  CODPARC:     {repr(CODPARC)} (tipo: {type(CODPARC).__name__})")
            print(f"  CODTIPOPER:  {repr(CODTIPOPER)} (tipo: {type(CODTIPOPER).__name__})")
            print(f"  CODNAT:      {repr(CODNAT)} (tipo: {type(CODNAT).__name__})")
            print(f"  CODCENCUS:   {repr(CODCENCUS)} (tipo: {type(CODCENCUS).__name__})")
            print(f"  DTENTSAI:    {repr(DTENTSAI)} (tipo: {type(DTENTSAI).__name__})")
            print(f"  VLRNOTA:     {repr(VLRNOTA)} (tipo: {type(VLRNOTA).__name__})")
            print(f"  DTFATUR:     {repr(DTFATUR)} (tipo: {type(DTFATUR).__name__})")
            print(f"  STATUSNOTA:  {repr(STATUSNOTA)} (tipo: {type(STATUSNOTA).__name__})")
            
            print("\n✅ VALORES APÓS CONVERSÃO:")
            
            # Simular a conversão que a função faz
            try:
                codnat_conv = int(CODNAT) if CODNAT and str(CODNAT).strip() else None
                print(f"  CODNAT:      {repr(CODNAT)} → {repr(codnat_conv)}")
            except Exception as e:
                print(f"  CODNAT:      {repr(CODNAT)} → ❌ ERRO: {e}")
            
            try:
                codcencus_conv = int(CODCENCUS) if CODCENCUS and str(CODCENCUS).strip() else None
                print(f"  CODCENCUS:   {repr(CODCENCUS)} → {repr(codcencus_conv)}")
            except Exception as e:
                print(f"  CODCENCUS:   {repr(CODCENCUS)} → ❌ ERRO: {e}")
            
            try:
                vlrnota_conv = float(VLRNOTA) if VLRNOTA is not None else 0.0
                print(f"  VLRNOTA:     {repr(VLRNOTA)} → {repr(vlrnota_conv)}")
            except Exception as e:
                print(f"  VLRNOTA:     {repr(VLRNOTA)} → ❌ ERRO: {e}")
            
            # Verificar se já existe TGFFIN
            print("\n🔍 VERIFICANDO TGFFIN EXISTENTE:")
            cur.execute("""
                SELECT NUFIN, VLRDESDOB, DTVENC, FINCONFIRMADO, AUTORIZADO
                FROM TGFFIN 
                WHERE NUNOTA = :n
                ORDER BY NUFIN DESC
            """, n=nunota)
            
            rows = cur.fetchall()
            if rows:
                print(f"  ⚠️  Encontrados {len(rows)} registro(s) TGFFIN:")
                for r in rows:
                    print(f"     NUFIN={r[0]}, VLRDESDOB={r[1]}, DTVENC={r[2]}, "
                          f"FINCONFIRMADO={r[3]}, AUTORIZADO={r[4]}")
            else:
                print("  ✅ Nenhum registro TGFFIN encontrado (OK para criar)")
            
            # Verificar STATUSNOTA
            print(f"\n📌 STATUS DA NOTA:")
            print(f"  STATUSNOTA: {repr(STATUSNOTA)}")
            if STATUSNOTA == 'L':
                print("  ✅ Status 'L' (Liberado) - Pronto para criar TGFFIN")
            else:
                print(f"  ⚠️  Status '{STATUSNOTA}' - Esperado 'L' para faturamento")
            
            print(f"\n{'='*80}\n")
            
    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # Alterar para a NUNOTA que está dando erro
    nunota_teste = 93227  # NUNOTA do erro reportado
    
    if len(sys.argv) > 1:
        nunota_teste = int(sys.argv[1])
    
    debug_tgfcab_values(nunota_teste)
