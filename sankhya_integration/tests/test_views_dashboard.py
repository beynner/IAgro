"""
Testes do Dashboard Executivo da home (Mai/2026).

Cobertura:
  - api_dashboard_indicadores: exige sessão, retorna shape correto,
    propaga indicadores do service, humaniza falha.
  - consultar_indicadores_dashboard (service): tolerância a falha por
    indicador, threshold de tanque crítico, threshold de lote envelhecido.

Todas as chamadas ao Oracle são mockadas. Sem dependência de banco real.
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    """Injeta sessão autenticada."""
    session = client.session
    session['codusu'] = 1
    session['nomeusu'] = 'Operador'
    session['nome'] = 'Operador Teste'
    session['grupos'] = grupos or ['1']
    session.save()


# ---------------------------------------------------------------------------
# Endpoint /api/dashboard/
# ---------------------------------------------------------------------------

class DashboardEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_sem_sessao_retorna_401(self):
        """Endpoint exige usuário autenticado (qualquer grupo)."""
        response = self.client.get(reverse('api_dashboard_indicadores'))
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('error', data)

    @patch('sankhya_integration.views.consultar_indicadores_dashboard')
    def test_com_sessao_retorna_indicadores(self, mock_dashboard):
        """Com sessão válida, retorna shape esperado."""
        mock_dashboard.return_value = {
            'sem_lote':           {'count': 3, 'label': 'Pedidos sem lote atribuído'},
            'aguardando_classif': {'count': 12, 'label': 'Lotes aguardando classificação'},
            'vales_abertos':      {'count': 5, 'label': 'Vales em aberto'},
            'tanques_criticos':   {'count': 1, 'label': 'Tanques críticos', 'detalhes': [
                {'codprod': 392, 'descricao': 'DIESEL S10', 'qtd_disponivel': 1500, 'capacidade': 10000, 'percentual': 15.0}
            ]},
            'prontos_faturar':    {'count': 8, 'label': 'Pedidos prontos pra faturar'},
            'lotes_envelhecidos': {'count': 2, 'label': 'Lotes com mais de 60 dias'},
        }
        _login_session(self.client)
        response = self.client.get(reverse('api_dashboard_indicadores'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertIn('indicadores', data)
        ind = data['indicadores']
        self.assertEqual(ind['sem_lote']['count'], 3)
        self.assertEqual(ind['aguardando_classif']['count'], 12)
        self.assertEqual(ind['vales_abertos']['count'], 5)
        self.assertEqual(ind['tanques_criticos']['count'], 1)
        self.assertEqual(len(ind['tanques_criticos']['detalhes']), 1)
        self.assertEqual(ind['prontos_faturar']['count'], 8)
        self.assertEqual(ind['lotes_envelhecidos']['count'], 2)

    @patch('sankhya_integration.views.consultar_indicadores_dashboard')
    def test_falha_geral_retorna_500_humanizada(self, mock_dashboard):
        """Exceção no service vira 500 com mensagem humanizada."""
        mock_dashboard.side_effect = RuntimeError('boom')
        _login_session(self.client)
        response = self.client.get(reverse('api_dashboard_indicadores'))
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('error', data)
        # Não deve vazar 'RuntimeError' nem o traceback
        self.assertNotIn('Traceback', data['error'])

    @patch('sankhya_integration.views.consultar_indicadores_dashboard')
    def test_qualquer_grupo_autenticado_passa(self, mock_dashboard):
        """Acesso liberado pra qualquer grupo autenticado (não restringe por módulo)."""
        mock_dashboard.return_value = {}
        for grupo in ['1', '6', '8', '9', '10', '11']:
            with self.subTest(grupo=grupo):
                self.client = Client()
                _login_session(self.client, grupos=[grupo])
                response = self.client.get(reverse('api_dashboard_indicadores'))
                self.assertEqual(response.status_code, 200, f"Grupo {grupo} bloqueado indevidamente")


# ---------------------------------------------------------------------------
# Service consultar_indicadores_dashboard — tolerância e thresholds
# ---------------------------------------------------------------------------

class DashboardServiceTest(TestCase):
    """Testes diretos do service de leitura. Mockamos a conexão Oracle e
    consultar_saldo_combustivel (usado pra calcular tanques críticos)."""

    def _mock_cursor(self, valores_por_query):
        """Devolve um MagicMock que se comporta como cursor Oracle, com
        execute() consumindo a próxima entrada da lista valores_por_query
        e fetchone() devolvendo a tupla correspondente."""
        cursor = MagicMock()
        # Cada execute consome 1 retorno em ordem
        cursor._idx = 0
        cursor._valores = list(valores_por_query)

        def _execute(*args, **kwargs):
            return cursor

        def _fetchone():
            if cursor._idx >= len(cursor._valores):
                return (0,)
            v = cursor._valores[cursor._idx]
            cursor._idx += 1
            return v

        cursor.execute.side_effect = _execute
        cursor.fetchone.side_effect = _fetchone
        return cursor

    def _mock_conn(self, cursor):
        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor
        return conn

    @patch('sankhya_integration.services.oracle_conn.consultar_saldo_combustivel')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_consolida_todos_indicadores(self, mock_conn_factory, mock_saldo):
        """Todas as 5 SELECTs do Oracle + chamada de tanque devolvem valores."""
        from sankhya_integration.services.oracle_conn import consultar_indicadores_dashboard

        # Ordem das queries: sem_lote, aguardando_classif, vales_abertos,
        # prontos_faturar, lotes_envelhecidos
        cursor = self._mock_cursor([(7,), (15,), (4,), (9,), (3,)])
        mock_conn_factory.return_value = self._mock_conn(cursor)
        # 2 tanques: 1 crítico (10%), 1 ok (50%)
        # Tupla: (CODPROD, DESCRPROD, CODVOL, qtd_entrada, qtd_saida,
        #         qtd_disponivel, capacidade_lt, saldo_inicial, percentual, formato)
        mock_saldo.return_value = [
            (392, 'DIESEL S10', 'LT', 10000, 9000, 1000, 10000, 0, 10.0, 'CILINDRO'),
            (1373, 'DIESEL S500', 'LT', 5000, 2500, 2500, 5000, 0, 50.0, 'CILINDRO'),
        ]

        res = consultar_indicadores_dashboard()

        self.assertEqual(res['sem_lote']['count'], 7)
        self.assertEqual(res['aguardando_classif']['count'], 15)
        self.assertEqual(res['vales_abertos']['count'], 4)
        self.assertEqual(res['prontos_faturar']['count'], 9)
        self.assertEqual(res['lotes_envelhecidos']['count'], 3)
        # Tanques críticos: apenas o S10 (10%) entra
        self.assertEqual(res['tanques_criticos']['count'], 1)
        self.assertEqual(res['tanques_criticos']['detalhes'][0]['codprod'], 392)

    @patch('sankhya_integration.services.oracle_conn.consultar_saldo_combustivel')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_em_um_indicador_nao_derruba_outros(self, mock_conn_factory, mock_saldo):
        """Se 1 SELECT falhar, os outros devolvem normalmente; o que falhou
        ganha {'count': None, 'erro': ...}."""
        from sankhya_integration.services.oracle_conn import consultar_indicadores_dashboard

        cursor = MagicMock()
        cursor.fetchone.return_value = (5,)
        # execute lança erro só no 3º call (vales_abertos)
        chamadas = {'count': 0}
        def _execute(*args, **kwargs):
            chamadas['count'] += 1
            if chamadas['count'] == 3:
                raise RuntimeError('falha localizada')
            return cursor
        cursor.execute.side_effect = _execute
        mock_conn_factory.return_value = self._mock_conn(cursor)
        mock_saldo.return_value = []

        res = consultar_indicadores_dashboard()

        # Os indicadores antes e depois da falha devolvem normalmente
        self.assertEqual(res['sem_lote']['count'], 5)
        self.assertEqual(res['aguardando_classif']['count'], 5)
        # O da falha vem como None + chave erro
        self.assertIsNone(res['vales_abertos']['count'])
        self.assertIn('erro', res['vales_abertos'])
        # Tanques (que não passa por conn Oracle) também vem ok (lista vazia)
        self.assertEqual(res['tanques_criticos']['count'], 0)

    @patch('sankhya_integration.services.oracle_conn.consultar_saldo_combustivel')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_tanque_no_threshold_exato_nao_e_critico(self, mock_conn_factory, mock_saldo):
        """Tanque com 20% exato não é crítico (threshold é < 20%)."""
        from sankhya_integration.services.oracle_conn import consultar_indicadores_dashboard

        cursor = self._mock_cursor([(0,), (0,), (0,), (0,), (0,)])
        mock_conn_factory.return_value = self._mock_conn(cursor)
        mock_saldo.return_value = [
            (392, 'DIESEL S10', 'LT', 2000, 0, 2000, 10000, 0, 20.0, 'CILINDRO'),
            (1373, 'DIESEL S500', 'LT', 500, 0, 500, 5000, 0, 10.0, 'CILINDRO'),
        ]

        res = consultar_indicadores_dashboard()
        # Só o S500 (10%) entra; S10 (20%) fica fora
        self.assertEqual(res['tanques_criticos']['count'], 1)
        self.assertEqual(res['tanques_criticos']['detalhes'][0]['codprod'], 1373)

    @patch('sankhya_integration.services.oracle_conn.consultar_saldo_combustivel')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_em_saldo_combustivel_nao_derruba_indicadores(self, mock_conn_factory, mock_saldo):
        """Exceção na consulta de tanques deixa tanques_criticos com erro,
        mas os 5 indicadores SQL devolvem normalmente."""
        from sankhya_integration.services.oracle_conn import consultar_indicadores_dashboard

        cursor = self._mock_cursor([(1,), (2,), (3,), (4,), (5,)])
        mock_conn_factory.return_value = self._mock_conn(cursor)
        mock_saldo.side_effect = RuntimeError('Oracle fora')

        res = consultar_indicadores_dashboard()
        self.assertEqual(res['sem_lote']['count'], 1)
        self.assertEqual(res['aguardando_classif']['count'], 2)
        self.assertIsNone(res['tanques_criticos']['count'])
        self.assertIn('erro', res['tanques_criticos'])
        self.assertEqual(res['tanques_criticos']['detalhes'], [])
