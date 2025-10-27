"""
Testar endpoint de itens do vale
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PackingHouse.settings')
django.setup()

from sankhya_integration.services.oracle_conn import get_connection, get_params

def test_itens_vale():
    nunota_vale = 93838
    
    with get_connection() as conn:
        cur = conn.cursor()
        params = get_params()
        top_13 = int(params.get('TOP_VALE_COMPRA', 13))
        
        print(f"Buscando itens do vale {nunota_vale} (TOP {top_13})")
        
        # Query simplificada
        sql = """
            SELECT 
                c.CODPARC,
                parc.NOMEPARC,
                prod.DESCRPROD,
                i.CODPROD,
                i.QTDNEG,
                i.SEQUENCIA,
                c.NUNOTA,
                i.CODVOL,
                i.VLRUNIT,
                voa.QUANTIDADE as FATOR_CONVERSAO,
                i.VLRTOT,
                i.CODAGREGACAO,
                c.CODTIPOPER,
                c.NUMPEDIDO
            FROM TGFCAB c
            JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
            JOIN TGFPRO prod ON prod.CODPROD = i.CODPROD
            LEFT JOIN TGFPAR parc ON parc.CODPARC = c.CODPARC
            LEFT JOIN TGFVOA voa ON voa.CODPROD = i.CODPROD 
                AND voa.CODVOL = i.CODVOL 
                AND voa.ATIVO = 'S'
            WHERE c.NUNOTA = :nunota
                AND c.CODTIPOPER = :top_13
            ORDER BY i.SEQUENCIA
        """
        
        try:
            cur.execute(sql, {'nunota': nunota_vale, 'top_13': top_13})
            rows = cur.fetchall()
            
            print(f"\n✅ Query executada com sucesso!")
            print(f"Linhas retornadas: {len(rows)}")
            
            for idx, row in enumerate(rows):
                print(f"\nLinha {idx + 1}:")
                print(f"  CODPARC: {row[0]}")
                print(f"  NOMEPARC: {row[1]}")
                print(f"  DESCRPROD: {row[2]}")
                print(f"  CODPROD: {row[3]}")
                print(f"  QTDNEG: {row[4]}")
                print(f"  SEQUENCIA: {row[5]}")
                print(f"  NUNOTA: {row[6]}")
                print(f"  CODVOL: {row[7]}")
                print(f"  VLRUNIT: {row[8]}")
                print(f"  FATOR_CONVERSAO: {row[9]}")
                print(f"  VLRTOT: {row[10]}")
                print(f"  CODAGREGACAO: {row[11]}")
                print(f"  CODTIPOPER: {row[12]}")
                print(f"  NUMPEDIDO: {row[13]}")
                
        except Exception as e:
            print(f"\n❌ Erro ao executar query:")
            print(f"Tipo: {type(e).__name__}")
            print(f"Mensagem: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    test_itens_vale()
