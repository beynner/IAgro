"""
Consultar estrutura da tabela TGFFIN no Oracle
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

def get_tgffin_structure():
    print(f"\n{'='*80}")
    print(f"📋 ESTRUTURA DA TABELA TGFFIN")
    print(f"{'='*80}\n")
    
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Consultar estrutura da tabela
            cur.execute("""
                SELECT 
                    COLUMN_NAME, 
                    DATA_TYPE, 
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE
                FROM USER_TAB_COLUMNS 
                WHERE TABLE_NAME = 'TGFFIN'
                ORDER BY COLUMN_ID
            """)
            
            rows = cur.fetchall()
            
            print(f"Total de colunas: {len(rows)}\n")
            print(f"{'Nº':<4} {'COLUNA':<30} {'TIPO':<15} {'TAMANHO':<10} {'NULL':<6}")
            print(f"{'-'*4} {'-'*30} {'-'*15} {'-'*10} {'-'*6}")
            
            # Colunas que estamos usando no INSERT
            our_columns = [
                'NUFIN', 'CODEMP', 'NUMNOTA', 'DTNEG', 'DESDOBRAMENTO', 'DHMOV',
                'DTVENCINIC', 'DTVENC', 'CODPARC', 'CODTIPOPER', 'DHTIPOPER',
                'CODBCO', 'CODCTABCOINT', 'CODNAT', 'CODCENCUS', 'CODPROJ',
                'CODVEND', 'CODMOEDA', 'CODTIPTIT', 'VLRDESDOB', 'VLRVENDOR',
                'VLRIRF', 'VLRISS', 'DESPCART', 'ISSRETIDO', 'VLRDESC',
                'VLRMULTA', 'VLRINSS', 'TIPMULTA', 'VLRJURO', 'TIPJURO',
                'BASEICMS', 'ALIQICMS', 'DHTIPOPERBAIXA', 'VLRBAIXA', 'AUTORIZADO',
                'RECDESP', 'PROVISAO', 'ORIGEM', 'NUNOTA', 'RATEADO',
                'DTENTSAI', 'VLRPROV', 'IRFRETIDO', 'INSSRETIDO', 'CARTAODESC',
                'DTALTER', 'NUMCONTRATO', 'ORDEMCARGA', 'CODVEICULO', 'CODUSU',
                'SEQUENCIA', 'VLRDESCEMBUT', 'VLRJUROEMBUT', 'VLRMULTAEMBUT', 'VLRMOEDA',
                'VLRMOEDABAIXA', 'VLRMULTANEGOC', 'VLRJURONEGOC', 'VLRMULTALIB', 'VLRJUROLIB',
                'VLRALIBERAR', 'DTPRAZO', 'FINCONFIRMADO', 'VLRGNREDOIS', 'RECEBIDO',
                'VLRDESDOBCALC', 'NUMOCORRENCIAS'
            ]
            
            for i, row in enumerate(rows, 1):
                col_name, data_type, data_len, data_prec, data_scale, nullable = row
                
                # Formatar tipo
                if data_type == 'NUMBER':
                    if data_prec and data_scale:
                        tipo = f"{data_type}({data_prec},{data_scale})"
                    elif data_prec:
                        tipo = f"{data_type}({data_prec})"
                    else:
                        tipo = data_type
                elif data_type in ['VARCHAR2', 'CHAR']:
                    tipo = f"{data_type}({data_len})"
                else:
                    tipo = data_type
                
                null_str = 'YES' if nullable == 'Y' else 'NO'
                
                # Marcar se está no nosso INSERT
                marker = '✅' if col_name in our_columns else ''
                
                print(f"{i:<4} {col_name:<30} {tipo:<15} {data_len:<10} {null_str:<6} {marker}")
            
            print(f"\n{'='*80}")
            print(f"✅ = Coluna usada no INSERT")
            print(f"{'='*80}\n")
            
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    get_tgffin_structure()
