"""
Teste da função criar_tgffin
Valida a criação de registro financeiro (TGFFIN) para um TOP 13 existente.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sankhya_integration.services.oracle_conn import criar_tgffin, get_connection

def test_criar_tgffin():
    """
    Testa a criação de TGFFIN para um TOP 13 específico.
    """
    print("="*80)
    print("TESTE: criar_tgffin")
    print("="*80)
    
    # NUNOTA de teste (TOP 13 existente - ajustar conforme necessário)
    nunota_teste = 92638  # Usar NUNOTA do rastreamento ou outro TOP 13 válido
    
    print(f"\n1. Verificando se NUNOTA {nunota_teste} existe...")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Verificar se o TOP 13 existe
            cur.execute("""
                SELECT 
                    NUNOTA, NUMNOTA, CODPARC, CODTIPOPER, 
                    STATUSNOTA, VLRNOTA, DTFATUR
                FROM TGFCAB
                WHERE NUNOTA = :n
            """, n=nunota_teste)
            
            row = cur.fetchone()
            
            if not row:
                print(f"❌ NUNOTA {nunota_teste} não encontrada!")
                print("\n💡 Ajuste a variável 'nunota_teste' para um TOP 13 válido")
                return
                
            nunota, numnota, codparc, codtipoper, statusnota, vlrnota, dtfatur = row
            
            print(f"✅ TOP encontrado:")
            print(f"   - NUNOTA: {nunota}")
            print(f"   - NUMNOTA: {numnota}")
            print(f"   - CODPARC: {codparc}")
            print(f"   - CODTIPOPER: {codtipoper}")
            print(f"   - STATUSNOTA: {statusnota}")
            print(f"   - VLRNOTA: {vlrnota}")
            print(f"   - DTFATUR: {dtfatur}")
            
            # Verificar se já existe TGFFIN para este NUNOTA
            cur.execute("""
                SELECT COUNT(*) 
                FROM TGFFIN 
                WHERE NUNOTA = :n
            """, n=nunota_teste)
            
            count = cur.fetchone()[0]
            
            if count > 0:
                print(f"\n⚠️  Já existem {count} registro(s) em TGFFIN para este NUNOTA")
                
                # Mostrar detalhes
                cur.execute("""
                    SELECT NUFIN, VLRDESDOB, DTVENC, FINCONFIRMADO, AUTORIZADO
                    FROM TGFFIN
                    WHERE NUNOTA = :n
                """, n=nunota_teste)
                
                for nufin, vlrdesdob, dtvenc, finconf, autor in cur.fetchall():
                    print(f"   - NUFIN: {nufin}, VLRDESDOB: {vlrdesdob}, DTVENC: {dtvenc}, "
                          f"FINCONFIRMADO: {finconf}, AUTORIZADO: {autor}")
                
                resp = input("\n❓ Deseja criar outro registro TGFFIN (pode gerar duplicação)? (s/N): ")
                if resp.lower() != 's':
                    print("❌ Teste cancelado pelo usuário")
                    return
    
    except Exception as e:
        print(f"❌ Erro ao verificar NUNOTA: {e}")
        return
    
    print(f"\n2. Testando criar_tgffin({nunota_teste})...")
    
    try:
        result = criar_tgffin(nunota_teste)
        
        print("\n📊 Resultado:")
        print(f"   - ok: {result.get('ok')}")
        print(f"   - nufin: {result.get('nufin')}")
        print(f"   - vlrdesdob: {result.get('vlrdesdob')}")
        print(f"   - dtvenc: {result.get('dtvenc')}")
        
        if result.get('error'):
            print(f"   - error: {result.get('error')}")
        
        if result.get('ok'):
            print("\n✅ TGFFIN criado com sucesso!")
            
            # Verificar no banco
            print("\n3. Verificando registro criado no banco...")
            
            with get_connection() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT 
                        NUFIN, CODEMP, NUMNOTA, CODPARC, CODTIPOPER,
                        VLRDESDOB, DTVENC, DTPRAZO, FINCONFIRMADO, AUTORIZADO,
                        CODBCO, CODCTABCOINT, CODTIPTIT, RECDESP, PROVISAO
                    FROM TGFFIN
                    WHERE NUFIN = :n
                """, n=result.get('nufin'))
                
                row = cur.fetchone()
                
                if row:
                    print("✅ Registro encontrado na TGFFIN:")
                    (nufin, codemp, numnota, codparc, codtipoper, vlrdesdob, 
                     dtvenc, dtprazo, finconf, autor, codbco, codctabco, 
                     codtiptit, recdesp, provisao) = row
                    
                    print(f"   - NUFIN: {nufin}")
                    print(f"   - CODEMP: {codemp}")
                    print(f"   - NUMNOTA: {numnota}")
                    print(f"   - CODPARC: {codparc}")
                    print(f"   - CODTIPOPER: {codtipoper}")
                    print(f"   - VLRDESDOB: {vlrdesdob}")
                    print(f"   - DTVENC: {dtvenc}")
                    print(f"   - DTPRAZO: {dtprazo}")
                    print(f"   - FINCONFIRMADO: {finconf}")
                    print(f"   - AUTORIZADO: {autor}")
                    print(f"   - CODBCO: {codbco}")
                    print(f"   - CODCTABCOINT: {codctabco}")
                    print(f"   - CODTIPTIT: {codtiptit}")
                    print(f"   - RECDESP: {recdesp}")
                    print(f"   - PROVISAO: {provisao}")
                    
                    # Validações
                    print("\n4. Validações:")
                    
                    validacoes = []
                    validacoes.append(("CODBCO = 33", codbco == 33))
                    validacoes.append(("CODCTABCOINT = 2", codctabco == 2))
                    validacoes.append(("CODTIPTIT = 13", codtiptit == 13))
                    validacoes.append(("FINCONFIRMADO = 'S'", finconf == 'S'))
                    validacoes.append(("AUTORIZADO = 'N'", autor == 'N'))
                    validacoes.append(("RECDESP = 'E'", recdesp == 'E'))
                    validacoes.append(("PROVISAO = 'A'", provisao == 'A'))
                    
                    for desc, passou in validacoes:
                        status = "✅" if passou else "❌"
                        print(f"   {status} {desc}")
                    
                    if all(v[1] for v in validacoes):
                        print("\n🎉 Todas as validações passaram!")
                    else:
                        print("\n⚠️  Algumas validações falharam")
                else:
                    print("❌ Registro NÃO encontrado na TGFFIN (erro inesperado)")
        else:
            print(f"\n❌ Erro ao criar TGFFIN: {result.get('error')}")
    
    except Exception as e:
        print(f"\n❌ Exceção ao executar criar_tgffin: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("FIM DO TESTE")
    print("="*80)


if __name__ == '__main__':
    test_criar_tgffin()
