#!/usr/bin/env python3
"""
Comando Django para investigar por que uma nota não duplicou automaticamente.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Investiga por que uma NUNOTA não duplicou automaticamente'

    def add_arguments(self, parser):
        parser.add_argument('nunota', type=int, help='NUNOTA a investigar')
        parser.add_argument('--codprod', type=int, help='CODPROD específico a verificar')
        parser.add_argument('--test-manual', action='store_true', help='Testar duplicação manual')

    def handle(self, *args, **options):
        nunota = options['nunota']
        codprod = options.get('codprod')
        
        try:
            from sankhya_integration.services.oracle_conn import (
                get_connection, get_duplicate_status, should_auto_duplicate_item, 
                is_auto_duplicate_on_save_enabled, duplicate_to_classification,
                get_params
            )
        except ImportError as e:
            raise CommandError(f'Oracle não disponível: {e}')

        self.stdout.write(f'\n=== INVESTIGAÇÃO NUNOTA {nunota} ===')
        
        # 1. Configurações
        self.stdout.write('\n1. CONFIGURAÇÕES:')
        auto_enabled = is_auto_duplicate_on_save_enabled()
        self.stdout.write(f'   Auto duplicate on save: {auto_enabled}')
        
        try:
            config = getattr(settings, 'SANKHYA_CONFIG', {})
            auto_flows = config.get('AUTO_FLOWS', {})
            self.stdout.write(f'   DUPLICATE_ON_SAVE: {auto_flows.get("DUPLICATE_ON_SAVE", "NÃO CONFIGURADO")}')
            self.stdout.write(f'   DUPLICATE_METHOD: {auto_flows.get("DUPLICATE_METHOD", "NÃO CONFIGURADO")}')
        except Exception:
            self.stdout.write('   Erro ao ler configurações Django')

        # 2. Dados no banco
        self.stdout.write('\n2. DADOS NO BANCO:')
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Verificar TGFCAB
                cur.execute("SELECT CODTIPOPER FROM TGFCAB WHERE NUNOTA = :n", n=nunota)
                cab = cur.fetchone()
                if cab:
                    codtipoper = cab[0]
                    self.stdout.write(f'   TGFCAB - CODTIPOPER: {codtipoper}')
                    
                    params = get_params()
                    if codtipoper == params['TOP_ENTRADA']:
                        self.stdout.write('   ✅ É TOP 11 (Entrada)')
                    else:
                        self.stdout.write(f'   ❌ NÃO é TOP 11 (é TOP {codtipoper})')
                else:
                    self.stdout.write('   ❌ NUNOTA não encontrada')
                    return
                
                # Verificar TGFITE
                cur.execute("""
                    SELECT CODPROD, CODAGREGACAO, NVL(GERAPRODUCAO, 'N') as GP 
                    FROM TGFITE WHERE NUNOTA = :n ORDER BY SEQUENCIA
                """, n=nunota)
                itens = cur.fetchall()
                
                self.stdout.write(f'   TGFITE - {len(itens)} itens:')
                classificaveis = 0
                lotes = set()
                
                for item in itens:
                    prod, lote, gp = item
                    lotes.add(lote)
                    if gp == 'S':
                        classificaveis += 1
                        self.stdout.write(f'     ✅ CODPROD: {prod}, LOTE: {lote}, GERAPRODUCAO: {gp}')
                    else:
                        self.stdout.write(f'     ❌ CODPROD: {prod}, LOTE: {lote}, GERAPRODUCAO: {gp}')
                
                self.stdout.write(f'   Itens classificáveis: {classificaveis}')
                self.stdout.write(f'   Lotes encontrados: {list(lotes)}')
                
                # Verificar se já existe TOP 26 para os lotes
                for lote in lotes:
                    cur.execute("""
                        SELECT COUNT(*) FROM TGFITE i
                        JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                        WHERE i.CODAGREGACAO = :lote AND c.CODTIPOPER = 26
                    """, lote=lote)
                    existe = cur.fetchone()[0]
                    if existe > 0:
                        self.stdout.write(f'   ⚠️  TOP 26 JÁ EXISTE para lote {lote}')
                    else:
                        self.stdout.write(f'   ✅ TOP 26 NÃO EXISTE para lote {lote}')
                        
        except Exception as e:
            self.stdout.write(f'   ❌ Erro ao consultar banco: {e}')

        # 3. Status de duplicação
        self.stdout.write('\n3. STATUS DE DUPLICAÇÃO:')
        try:
            status = get_duplicate_status(nunota)
            self.stdout.write(f'   has_top26: {status.get("has_top26")}')
            self.stdout.write(f'   nunota_26: {status.get("nunota_26")}')
            self.stdout.write(f'   controls: {status.get("controls")}')
            self.stdout.write(f'   classificable_items: {status.get("classificable_items")}')
        except Exception as e:
            self.stdout.write(f'   ❌ Erro: {e}')

        # 4. Verificação específica do produto
        if codprod:
            self.stdout.write(f'\n4. VERIFICAÇÃO PRODUTO {codprod}:')
            try:
                check = should_auto_duplicate_item(nunota, codprod)
                self.stdout.write(f'   should_duplicate: {check.get("should_duplicate")}')
                self.stdout.write(f'   reason: {check.get("reason")}')
                self.stdout.write(f'   codtipoper: {check.get("codtipoper")}')
            except Exception as e:
                self.stdout.write(f'   ❌ Erro: {e}')

        # 5. Teste manual (se solicitado)
        if options['test_manual']:
            self.stdout.write('\n5. TESTE DE DUPLICAÇÃO MANUAL:')
            try:
                result = duplicate_to_classification(nunota, dry_run=True)
                self.stdout.write(f'   ok: {result.get("ok")}')
                self.stdout.write(f'   errors: {result.get("errors")}')
                self.stdout.write(f'   warnings: {result.get("warnings")}')
                self.stdout.write(f'   items_duplicated: {result.get("items_duplicated")}')
                
                if result.get('ok'):
                    self.stdout.write(self.style.SUCCESS('   ✅ Duplicação manual FUNCIONARIA'))
                else:
                    self.stdout.write(self.style.ERROR('   ❌ Duplicação manual FALHARIA'))
            except Exception as e:
                self.stdout.write(f'   ❌ Erro no teste: {e}')

        self.stdout.write('\n=== FIM DA INVESTIGAÇÃO ===\n')