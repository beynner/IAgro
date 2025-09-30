#!/usr/bin/env python3
"""
Comando Django para gerenciar o trigger de duplicação automática TOP 11 → 26.

Uso:
    python manage.py manage_duplicate_trigger --install
    python manage.py manage_duplicate_trigger --uninstall  
    python manage.py manage_duplicate_trigger --status
    python manage.py manage_duplicate_trigger --test
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Gerencia o trigger de duplicação automática TOP 11 → 26'

    def add_arguments(self, parser):
        parser.add_argument(
            '--install',
            action='store_true',
            help='Instalar o trigger no banco',
        )
        parser.add_argument(
            '--uninstall',
            action='store_true',
            help='Remover o trigger do banco',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Verificar status do trigger',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Testar se automação funciona',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forçar operação mesmo se escrita estiver desabilitada',
        )

    def handle(self, *args, **options):
        # Verificar se Oracle está disponível
        try:
            from sankhya_integration.services.oracle_conn import (
                get_connection, is_write_enabled, get_params
            )
        except ImportError as e:
            raise CommandError(f'Oracle não disponível: {e}')

        # Verificar permissões de escrita
        if not is_write_enabled() and not options['force']:
            raise CommandError(
                'Escrita desabilitada. Use --force para forçar ou habilite WRITE_ENABLED.'
            )

        if options['install']:
            self._install_trigger()
        elif options['uninstall']:
            self._uninstall_trigger()
        elif options['status']:
            self._check_status()
        elif options['test']:
            self._test_automation()
        else:
            self.stdout.write(self.style.ERROR('Especifique --install, --uninstall, --status ou --test'))

    def _install_trigger(self):
        """Instalar o trigger no banco."""
        from sankhya_integration.services.oracle_conn import get_connection
        
        # Caminho do arquivo SQL
        trigger_file = os.path.join(
            settings.BASE_DIR,
            'sankhya_integration',
            'triggers',
            'triggers',
            'SANKHYA.TRG_AUTO_DUPLICATE_CLASS.sql'
        )
        
        if not os.path.exists(trigger_file):
            raise CommandError(f'Arquivo do trigger não encontrado: {trigger_file}')
        
        # Ler conteúdo do arquivo
        with open(trigger_file, 'r', encoding='utf-8') as f:
            trigger_sql = f.read()
        
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Executar o SQL do trigger
                cur.execute(trigger_sql)
                conn.commit()
                
                # Verificar se foi criado
                cur.execute("""
                    SELECT trigger_name, status FROM user_triggers 
                    WHERE trigger_name = 'TRG_AUTO_DUPLICATE_CLASS'
                """)
                result = cur.fetchone()
                
                if result:
                    name, status = result
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Trigger {name} instalado com sucesso! Status: {status}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('Trigger instalado mas não encontrado na verificação')
                    )
                    
        except Exception as e:
            raise CommandError(f'Erro ao instalar trigger: {e}')

    def _uninstall_trigger(self):
        """Remover o trigger do banco."""
        from sankhya_integration.services.oracle_conn import get_connection
        
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Verificar se existe
                cur.execute("""
                    SELECT COUNT(*) FROM user_triggers 
                    WHERE trigger_name = 'TRG_AUTO_DUPLICATE_CLASS'
                """)
                
                if cur.fetchone()[0] == 0:
                    self.stdout.write(
                        self.style.WARNING('Trigger não encontrado para remoção')
                    )
                    return
                
                # Remover o trigger
                cur.execute('DROP TRIGGER SANKHYA.TRG_AUTO_DUPLICATE_CLASS')
                conn.commit()
                
                self.stdout.write(
                    self.style.SUCCESS('Trigger removido com sucesso!')
                )
                
        except Exception as e:
            raise CommandError(f'Erro ao remover trigger: {e}')

    def _check_status(self):
        """Verificar status do trigger."""
        from sankhya_integration.services.oracle_conn import (
            get_connection, get_params, is_auto_duplicate_enabled
        )
        
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Status do trigger
                cur.execute("""
                    SELECT trigger_name, status, table_name, triggering_event 
                    FROM user_triggers 
                    WHERE trigger_name = 'TRG_AUTO_DUPLICATE_CLASS'
                """)
                
                result = cur.fetchone()
                if result:
                    name, status, table, event = result
                    self.stdout.write(f'Trigger: {name}')
                    self.stdout.write(f'Status: {status}')
                    self.stdout.write(f'Tabela: {table}')
                    self.stdout.write(f'Evento: {event}')
                    
                    if status == 'ENABLED':
                        self.stdout.write(self.style.SUCCESS('✓ Trigger ativo'))
                    else:
                        self.stdout.write(self.style.WARNING('⚠ Trigger inativo'))
                else:
                    self.stdout.write(self.style.ERROR('✗ Trigger não encontrado'))
                
                # Configurações da aplicação
                params = get_params()
                auto_enabled = is_auto_duplicate_enabled()
                
                self.stdout.write(f'\nConfigurações:')
                self.stdout.write(f'TOP_ENTRADA: {params.get("TOP_ENTRADA")}')
                self.stdout.write(f'TOP_CLASS: {params.get("TOP_CLASS")}')
                self.stdout.write(f'Auto Duplicate: {auto_enabled}')
                
        except Exception as e:
            raise CommandError(f'Erro ao verificar status: {e}')

    def _test_automation(self):
        """Testar se a automação funciona."""
        from sankhya_integration.services.oracle_conn import (
            get_connection, get_duplicate_status, duplicate_to_classification
        )
        
        self.stdout.write('Testando automação de duplicação...')
        
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                
                # Buscar uma nota TOP 11 recente com itens classificáveis
                cur.execute("""
                    SELECT DISTINCT c.NUNOTA, COUNT(*) as itens
                    FROM TGFCAB c
                    JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
                    WHERE c.CODTIPOPER = 11
                    AND NVL(i.GERAPRODUCAO, 'N') = 'S'
                    AND c.DTNEG >= SYSDATE - 30
                    GROUP BY c.NUNOTA
                    ORDER BY c.NUNOTA DESC
                """)
                
                result = cur.fetchone()
                if not result:
                    self.stdout.write(
                        self.style.WARNING('Nenhuma nota TOP 11 com itens classificáveis encontrada')
                    )
                    return
                
                nunota_11, itens_count = result
                self.stdout.write(f'Testando com NUNOTA {nunota_11} ({itens_count} itens)')
                
                # Verificar status atual
                status = get_duplicate_status(nunota_11)
                self.stdout.write(f'Status atual: {status}')
                
                if status.get('has_top26'):
                    self.stdout.write(
                        self.style.WARNING(
                            f'TOP 26 já existe (NUNOTA {status["nunota_26"]})'
                        )
                    )
                else:
                    self.stdout.write('TOP 26 não existe - trigger deveria ter criado')
                    
                    # Testar duplicação manual
                    self.stdout.write('Testando duplicação manual...')
                    result = duplicate_to_classification(nunota_11, dry_run=True)
                    
                    if result.get('ok'):
                        self.stdout.write(
                            self.style.SUCCESS('✓ Duplicação manual funcionaria')
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'✗ Duplicação manual falharia: {result.get("errors")}')
                        )
                        
        except Exception as e:
            raise CommandError(f'Erro no teste: {e}')