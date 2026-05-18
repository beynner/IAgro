"""IAgroTestRunner — patcha `verificar_permissao_escrita` globalmente em tests.

Mai/2026 (2026-05-18) — resposta ao incidente dos 803 fakes em produção.

Arquitetura de defesa em 2 camadas:

  1. **Bloqueio FÍSICO** em ``obter_conexao_oracle`` (oracle_conn.py):
     quando ``'test' in sys.argv``, lança RuntimeError em vez de conectar
     Oracle real. Tests bem-mockados (com ``@patch('...obter_conexao_oracle')``)
     não chegam aqui — o mock intercepta antes. Tests mal-mockados batem
     no erro e ficam VISÍVEIS — sem poluir o banco real.

  2. **Liberação LÓGICA** em ``verificar_permissao_escrita`` (este runner):
     patcheia retornando True pra que as ~80 guards das funções de escrita
     deixem o código fluir até o nível dos mocks. Sem isso, todas as
     funções retornariam ``{'ok': False, 'error': 'Escrita desabilitada'}``
     antes de chegar nos mocks, quebrando 65 tests existentes.

Resultado: zero escritas no Oracle real durante tests + zero regressão de
suíte existente. Bypass consciente via ``IAGRO_TEST_REAL_DB=true`` libera
conexão real (pra testes de integração intencionais).

Configurar em ``settings.py``:
    TEST_RUNNER = 'sankhya_integration.tests.test_runner.IAgroTestRunner'
"""
from unittest.mock import patch

from django.test.runner import DiscoverRunner


class IAgroTestRunner(DiscoverRunner):
    """DiscoverRunner que patcha ``verificar_permissao_escrita`` globalmente."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._patcher_permissao = patch(
            'sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
            return_value=True,
        )
        self._patcher_permissao.start()

    def teardown_test_environment(self, **kwargs):
        try:
            self._patcher_permissao.stop()
        except Exception:
            pass
        super().teardown_test_environment(**kwargs)
