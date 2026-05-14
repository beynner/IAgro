"""
Testes da tela de Auditoria — Lote A (Mai/2026).

Cobertura:
  - Controle de acesso (sem sessão, grupos sem permissão, grupos 1 e 6 OK).
  - API de listagem: passa filtros corretamente, propaga total/tem_mais.
  - API de filtros distintos.
  - View HTML renderiza (200) com sessão válida.
  - Edge cases: filtros vazios, falha do Oracle, etc.
"""
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 1
    session['nomeusu'] = 'AUDIT_TESTE'
    session['nome']    = 'Audit Teste'
    session['grupos']  = grupos or ['1']
    session.save()


# ==========================================================================
# Controle de acesso
# ==========================================================================

class AcessoAuditoriaTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_sem_sessao_redireciona_painel(self):
        response = self.client.get(reverse('view_auditoria_painel'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('home'), response.url)

    def test_grupo_sem_permissao_redireciona_painel(self):
        _login_session(self.client, grupos=['10'])  # Vendas
        response = self.client.get(reverse('view_auditoria_painel'))
        self.assertEqual(response.status_code, 302)

    def test_diretoria_acessa_painel(self):
        _login_session(self.client, grupos=['1'])
        response = self.client.get(reverse('view_auditoria_painel'))
        self.assertEqual(response.status_code, 200)

    def test_suporte_acessa_painel(self):
        _login_session(self.client, grupos=['6'])
        response = self.client.get(reverse('view_auditoria_painel'))
        self.assertEqual(response.status_code, 200)

    def test_api_listar_sem_sessao_retorna_401(self):
        response = self.client.get(reverse('api_auditoria_listar'))
        self.assertEqual(response.status_code, 401)

    def test_api_listar_grupo_errado_retorna_403(self):
        _login_session(self.client, grupos=['8'])  # Entrada
        response = self.client.get(reverse('api_auditoria_listar'))
        self.assertEqual(response.status_code, 403)


# ==========================================================================
# API: listagem com filtros
# ==========================================================================

class ApiListarAuditoriaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    @patch('sankhya_integration.views.consultar_auditoria_paginada')
    def test_sem_filtros_retorna_lista(self, m_consultar):
        m_consultar.return_value = {
            'registros': [
                {'id': 1, 'modulo': 'venda', 'operacao': 'CRIAR_PEDIDO',
                 'tabela_alvo': 'TGFCAB', 'registro_id': '12345',
                 'codusu': 42, 'nomeusu': 'OP', 'dt': '2026-05-13 10:00:00',
                 'snapshot_antes': None,
                 'snapshot_depois': {'NUNOTA': 12345}, 'observacao': None},
            ],
            'total': 1, 'tem_mais': False, 'pagina_size': 50, 'offset_atual': 0,
        }
        response = self.client.get(reverse('api_auditoria_listar'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)
        self.assertEqual(len(data['registros']), 1)
        self.assertEqual(data['registros'][0]['operacao'], 'CRIAR_PEDIDO')

    @patch('sankhya_integration.views.consultar_auditoria_paginada')
    def test_propaga_filtros_para_service(self, m_consultar):
        m_consultar.return_value = {'registros': [], 'total': 0, 'tem_mais': False,
                                     'pagina_size': 50, 'offset_atual': 0}
        self.client.get(reverse('api_auditoria_listar') +
                        '?modulo=venda&operacao=FATURAR_PEDIDO&codusu=42&data_ini=2026-05-01&data_fim=2026-05-13')

        m_consultar.assert_called_once()
        filtros = m_consultar.call_args.args[0]
        self.assertEqual(filtros['modulo'], 'venda')
        self.assertEqual(filtros['operacao'], 'FATURAR_PEDIDO')
        self.assertEqual(filtros['codusu'], 42)
        self.assertEqual(filtros['data_ini'], '2026-05-01')
        self.assertEqual(filtros['data_fim'], '2026-05-13')

    @patch('sankhya_integration.views.consultar_auditoria_paginada')
    def test_paginacao_respeita_offset_limite(self, m_consultar):
        m_consultar.return_value = {'registros': [], 'total': 0, 'tem_mais': False,
                                     'pagina_size': 100, 'offset_atual': 50}
        self.client.get(reverse('api_auditoria_listar') + '?limite=100&offset=50')

        kwargs = m_consultar.call_args.kwargs
        self.assertEqual(kwargs['limite'], 100)
        self.assertEqual(kwargs['offset'], 50)

    @patch('sankhya_integration.views.consultar_auditoria_paginada',
           side_effect=RuntimeError('boom'))
    def test_falha_oracle_retorna_500_humanizada(self, _m):
        response = self.client.get(reverse('api_auditoria_listar'))
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('error', data)
        self.assertNotIn('Traceback', data['error'])

    @patch('sankhya_integration.views.consultar_auditoria_paginada')
    def test_filtros_strings_vazias_viram_none(self, m_consultar):
        m_consultar.return_value = {'registros': [], 'total': 0, 'tem_mais': False,
                                     'pagina_size': 50, 'offset_atual': 0}
        self.client.get(reverse('api_auditoria_listar') +
                        '?modulo=&operacao=  &busca=')
        filtros = m_consultar.call_args.args[0]
        self.assertIsNone(filtros['modulo'])
        self.assertIsNone(filtros['operacao'])
        self.assertIsNone(filtros['busca'])


# ==========================================================================
# API: filtros distintos
# ==========================================================================

class ApiFiltrosAuditoriaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    @patch('sankhya_integration.views.listar_filtros_distintos_auditoria')
    def test_retorna_listas_distintas(self, m_listar):
        m_listar.return_value = {
            'modulos':   ['venda', 'rastreio'],
            'operacoes': ['CRIAR_PEDIDO', 'FATURAR_PEDIDO'],
            'usuarios':  [{'codusu': 42, 'nomeusu': 'OP'}],
        }
        response = self.client.get(reverse('api_auditoria_filtros'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['modulos']), 2)
        self.assertEqual(len(data['usuarios']), 1)

    def test_sem_sessao_retorna_401(self):
        self.client = Client()
        response = self.client.get(reverse('api_auditoria_filtros'))
        self.assertEqual(response.status_code, 401)
