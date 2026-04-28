"""
Testes do módulo Comercial (faturamento, vales, precificação).

Todas as chamadas ao Oracle são mockadas. Os testes documentam o
comportamento atual do sistema — nenhum código de produção é alterado.

Nota sobre imports locais nas views:
  api_gerar_financeiro_banco e api_desfaturar_vale fazem imports dentro do
  corpo da função (ex: `from ...oracle_conn import gerar_financeiro_banco`).
  Por isso o patch deve apontar para o módulo de origem
  ('sankhya_integration.services.oracle_conn.X'), não para views.
"""
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu'] = 1
    session['nomeusu'] = 'Teste'
    session['nome'] = 'Teste'
    session['grupos'] = grupos or ['1']
    session.save()


# ---------------------------------------------------------------------------
# api_gerar_financeiro_banco — endpoint de faturamento
# ---------------------------------------------------------------------------

class GerarFinanceiroBancoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = reverse('api_gerar_financeiro_banco')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    @patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco',
           return_value={'ok': True, 'nunota_financeiro': 42})
    def test_payload_valido_retorna_ok(self, mock_fn):
        """Payload completo e válido deve retornar ok=True."""
        payload = {
            'nunota_13': 999,
            'descontar_inss': False,
            'historico': 'Teste',
            'vlrinss': 0.0,
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('ok'))

    @patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco',
           return_value={'ok': True})
    def test_vlr_forcar_liquido_e_bruto_convertidos_para_float(self, mock_fn):
        """Valores forçados de líquido e bruto devem ser convertidos para float."""
        payload = {
            'nunota_13': 100,
            'descontar_inss': True,
            'historico': '',
            'vlrinss': 50.0,
            'vlr_forcar_liquido': '1200.50',
            'vlr_forcar_bruto': '1500.00',
        }
        self._post(payload)
        args = mock_fn.call_args[0]
        self.assertAlmostEqual(args[4], 1200.50)
        self.assertAlmostEqual(args[5], 1500.00)

    def test_nunota_13_ausente_retorna_500(self):
        """Payload sem nunota_13 deve resultar em 500 (int(None) lança TypeError)."""
        response = self._post({'descontar_inss': False})
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data.get('ok'))

    @patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco',
           side_effect=RuntimeError('Oracle indisponível'))
    def test_excecao_oracle_retorna_500(self, mock_fn):
        """Exceção lançada pela camada Oracle deve retornar 500 com mensagem."""
        payload = {'nunota_13': 1, 'descontar_inss': False, 'historico': '', 'vlrinss': 0}
        response = self._post(payload)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data.get('ok'))
        self.assertIn('error', data)

    def test_metodo_get_nao_permitido(self):
        """Endpoint aceita apenas POST."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


# ---------------------------------------------------------------------------
# api_listar_vales_comercial
# Nota: esta view NÃO tem @exige_grupo — é um endpoint de API sem auth guard.
# ---------------------------------------------------------------------------

class ListarValesComercialTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('api_listar_vales_comercial')

    @patch('sankhya_integration.views.consultar_vales_comercial', return_value=[])
    def test_sem_sessao_retorna_200(self, mock_fn):
        """
        api_listar_vales_comercial não tem @exige_grupo, portanto retorna
        dados mesmo sem sessão autenticada — comportamento atual documentado.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('ok'))

    @patch('sankhya_integration.views.consultar_vales_comercial')
    def test_retorna_linhas_do_oracle(self, mock_fn):
        """Deve retornar as linhas providas pelo Oracle."""
        mock_fn.return_value = [
            {'nunota': 10, 'lote': 'L001', 'total': 500.0}
        ]
        _login_session(self.client, grupos=['9'])
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(len(data.get('rows', [])), 1)

    @patch('sankhya_integration.views.consultar_vales_comercial',
           side_effect=Exception('Falha Oracle'))
    def test_excecao_oracle_retorna_500(self, mock_fn):
        """Falha Oracle deve retornar 500 com ok=False."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data.get('ok'))


# ---------------------------------------------------------------------------
# api_atualizar_preco_comercial
# ---------------------------------------------------------------------------

class AtualizarPrecoComercialTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = reverse('api_atualizar_preco_comercial')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    @patch('sankhya_integration.views.atualizar_preco_inicial_entrada',
           return_value={'ok': True})
    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True})
    def test_payload_valido_retorna_ok(self, mock_recalc, mock_update):
        """Preço válido deve chamar atualizar_preco e recalcular totais."""
        payload = {
            'nunota': 200, 'sequencia': 1, 'preco_inicial': 50.0,
            'qtdconferida': 100.0, 'geraproducao': 'S', 'peso': 2500.0,
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('ok'))
        mock_update.assert_called_once()
        mock_recalc.assert_called_once_with(200)

    @patch('sankhya_integration.views.atualizar_preco_inicial_entrada',
           return_value={'ok': False, 'error': 'preço inválido'})
    def test_oracle_retorna_nok_propaga_400(self, mock_update):
        """Se Oracle retornar ok=False, endpoint deve retornar 400."""
        payload = {
            'nunota': 200, 'sequencia': 1, 'preco_inicial': 0.0,
            'qtdconferida': 0.0, 'geraproducao': 'S', 'peso': 0.0,
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# api_desfaturar_vale
# Usa import local: `from ...oracle_conn import desfaturar_comercial_banco`
# Patch deve ser em oracle_conn, não em views.
# ---------------------------------------------------------------------------

class DesfaturarValeTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = reverse('api_desfaturar_vale')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    @patch('sankhya_integration.services.oracle_conn.desfaturar_comercial_banco',
           return_value={'ok': True})
    def test_desfaturar_com_nunota_valido(self, mock_fn):
        """nunota_13 válido deve chamar desfaturar_comercial_banco e retornar ok."""
        response = self._post({'nunota_13': 55})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('ok'))
        mock_fn.assert_called_once_with(55)

    def test_nunota_ausente_retorna_500(self):
        """Sem nunota_13, int(None) lança TypeError → capturado → 500."""
        response = self._post({})
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data.get('ok'))

    def test_metodo_get_nao_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
