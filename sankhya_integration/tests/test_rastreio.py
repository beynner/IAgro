"""
Testes do módulo de Rastreabilidade (Rastreio / WMS).

Todas as chamadas ao Oracle são mockadas via unittest.mock.patch.
Os testes documentam o contrato dos endpoints novos:
    - api_rastreio_view                   → render protegido por grupo
    - api_rastreio_lotes_disponiveis      → GET, lê SANKHYA.ANDRE_IRIS_SALDO_LOTE
    - api_rastreio_pedidos_abertos        → GET, lista TOP 34 em aberto
    - api_rastreio_atribuir_lote          → POST, atribui CODAGREGACAO ao item
"""
import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    """Injeta sessão autenticada com os grupos informados."""
    session = client.session
    session['codusu'] = 1
    session['nomeusu'] = 'Teste'
    session['nome'] = 'Teste'
    session['grupos'] = grupos or ['1']
    session.save()


# ---------------------------------------------------------------------------
# api_rastreio_view — controle de acesso
# ---------------------------------------------------------------------------

class RastreioPaginaAcessoTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('rastreio')

    def test_sem_sessao_redireciona_para_home(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_desconhecido_redireciona_para_home(self):
        _login_session(self.client, grupos=['99'])
        response = self.client.get(self.url)
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_diretoria_acessa_pagina(self):
        _login_session(self.client, grupos=['1'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_operacao_acessa_pagina(self):
        _login_session(self.client, grupos=['8'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_comercial_acessa_pagina(self):
        _login_session(self.client, grupos=['9'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_vendas_acessa_pagina(self):
        _login_session(self.client, grupos=['10'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# api_rastreio_lotes_disponiveis
# ---------------------------------------------------------------------------

class ApiLotesDisponiveisTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_rastreio_lotes_disponiveis')

    def test_sem_sessao_redireciona(self):
        cli = Client()
        response = cli.get(self.url)
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel',
           return_value=[])
    def test_retorno_vazio(self, _mock):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['lotes'], [])

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel')
    def test_formata_data_e_converte_qtds_para_float(self, mock_fn):
        mock_fn.return_value = [{
            'codemp':              1,
            'codprod':             10,
            'descrprod':           'TOMATE EXTRA',
            'selecionado':         1,
            'codagregacao':        'NUNOTAS100D260424',
            'status_linha':        'CLASSIFICADO',
            'qtd_entrada':         1300,
            'qtd_baixada_venda':   100,
            'qtd_baixada_avaria':  50,
            'qtd_reservada':       200,
            'qtd_disponivel':      950,
            'qtd_pendente':        0,
            'qtd_avaria_interna':  50,
            'vendavel':            'S',
            'nunota_origem':       12345,
            'dtneg_origem':        date(2026, 4, 24),
            'codparc_origem':      999,
            'nomeparc_origem':     'FAZ. ALEGRIA',
        }]
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        l = data['lotes'][0]
        self.assertEqual(l['dtneg_origem'], '24/04/2026')
        self.assertIsInstance(l['qtd_disponivel'], float)
        self.assertAlmostEqual(l['qtd_disponivel'], 950.0)
        self.assertAlmostEqual(l['qtd_avaria_interna'], 50.0)
        self.assertEqual(l['vendavel'], 'S')

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel')
    def test_linha_avaria_fornecedor_eh_nao_vendavel(self, mock_fn):
        """Linha AVARIA_FORNECEDOR (perna E) deve ser não-vendável e ter qtd_entrada > 0."""
        mock_fn.return_value = [{
            'codemp':              1,
            'codprod':             10,
            'descrprod':           'TOMATE ITALIANO IN NATURA',
            'selecionado':         0,
            'codagregacao':        '110439S01D260423',
            'status_linha':        'AVARIA_FORNECEDOR',
            'qtd_entrada':         69,
            'qtd_baixada_venda':   0,
            'qtd_baixada_avaria':  0,
            'qtd_reservada':       0,
            'qtd_disponivel':      0,
            'qtd_pendente':        0,
            'qtd_avaria_interna':  0,
            'vendavel':            'N',
            'nunota_origem':       110439,
            'dtneg_origem':        date(2026, 4, 23),
            'codparc_origem':      999,
            'nomeparc_origem':     'FC TOM 11',
        }]
        response = self.client.get(self.url)
        data = json.loads(response.content)
        l = data['lotes'][0]
        self.assertEqual(l['status_linha'], 'AVARIA_FORNECEDOR')
        self.assertEqual(l['vendavel'], 'N')
        self.assertAlmostEqual(l['qtd_entrada'], 69.0)
        self.assertEqual(l['qtd_disponivel'], 0)

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel',
           return_value=[])
    def test_filtros_encaminhados_ao_servico(self, mock_fn):
        self.client.get(self.url, {
            'q': 'TOMATE',
            'codprod': '10',
            'codagregacao': 'NUNOTAS100',
        })
        args, _ = mock_fn.call_args
        filtros = args[0]
        self.assertEqual(filtros['q'], 'TOMATE')
        self.assertEqual(filtros['codprod'], '10')
        self.assertEqual(filtros['codagregacao'], 'NUNOTAS100')

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel',
           return_value=[])
    def test_data_ini_e_data_fim_encaminhados(self, mock_fn):
        self.client.get(self.url, {
            'data_ini': '2026-04-20',
            'data_fim': '2026-04-27',
        })
        filtros = mock_fn.call_args[0][0]
        self.assertEqual(filtros['data_ini'], '2026-04-20')
        self.assertEqual(filtros['data_fim'], '2026-04-27')

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel',
           side_effect=Exception('erro Oracle simulado'))
    def test_excecao_retorna_500(self, _mock):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('erro Oracle', data['error'])


# ---------------------------------------------------------------------------
# api_rastreio_pedidos_abertos
# ---------------------------------------------------------------------------

class ApiPedidosAbertosTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_rastreio_pedidos_abertos')

    def test_sem_sessao_redireciona(self):
        cli = Client()
        response = cli.get(self.url)
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_retorno_vazio(self, _mock):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['itens'], [])

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao')
    def test_formata_data_e_converte_qtd(self, mock_fn):
        mock_fn.return_value = [{
            'nunota':              987,
            'codemp':              1,
            'codparc':             501,
            'nomeparc':            'ASSAI SIA',
            'dtneg':               date(2026, 4, 25),
            'sequencia':           1,
            'codprod':             10,
            'descrprod':           'TOMATE EXTRA',
            'qtd_pedida':          200,
            'codagregacao_atual':  None,
            'status_item':         'PENDENTE',
        }]
        response = self.client.get(self.url)
        data = json.loads(response.content)
        item = data['itens'][0]
        self.assertEqual(item['dtneg'], '25/04/2026')
        self.assertIsInstance(item['qtd_pedida'], float)
        self.assertAlmostEqual(item['qtd_pedida'], 200.0)
        self.assertEqual(item['status_item'], 'PENDENTE')

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_filtros_encaminhados(self, mock_fn):
        self.client.get(self.url, {
            'q': 'ASSAI',
            'codprod': '10',
            'nunota': '987',
        })
        args, _ = mock_fn.call_args
        filtros = args[0]
        self.assertEqual(filtros['q'], 'ASSAI')
        self.assertEqual(filtros['codprod'], '10')
        self.assertEqual(filtros['nunota'], '987')

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_data_ini_e_data_fim_encaminhados(self, mock_fn):
        self.client.get(self.url, {
            'data_ini': '2026-04-20',
            'data_fim': '2026-04-27',
        })
        filtros = mock_fn.call_args[0][0]
        self.assertEqual(filtros['data_ini'], '2026-04-20')
        self.assertEqual(filtros['data_fim'], '2026-04-27')

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_data_apenas_inicial(self, mock_fn):
        """Só data_ini (sem data_fim) deve ir para o serviço sem reclamar."""
        self.client.get(self.url, {'data_ini': '2026-04-01'})
        filtros = mock_fn.call_args[0][0]
        self.assertEqual(filtros['data_ini'], '2026-04-01')
        self.assertIn(filtros.get('data_fim') or '', ('', None))

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           side_effect=Exception('erro Oracle simulado'))
    def test_excecao_retorna_500(self, _mock):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)


# ---------------------------------------------------------------------------
# api_rastreio_atribuir_lote (POST)
# ---------------------------------------------------------------------------

class ApiAtribuirLoteTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_rastreio_atribuir_lote')

    def test_sem_sessao_redireciona(self):
        cli = Client()
        response = cli.post(self.url, data='{}', content_type='application/json')
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_get_nao_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_body_vazio_retorna_400(self):
        response = self.client.post(self.url, data='', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])

    def test_campos_obrigatorios_ausentes_retorna_400(self):
        # Falta 'codagregacao'
        payload = {'nunota': 100, 'sequencia': 1}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('obrigat', data['error'].lower())

    @patch('sankhya_integration.views.atribuir_lote_item_pedido')
    def test_atribuicao_total_sucesso(self, mock_fn):
        mock_fn.return_value = {
            'ok': True, 'operacao': 'UPDATE',
            'qtd_atribuida': 200.0, 'nova_sequencia': None,
        }
        payload = {
            'nunota': 100, 'sequencia': 1,
            'codagregacao': 'NUNOTAS100D260424',
        }
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['operacao'], 'UPDATE')

        kwargs = mock_fn.call_args.kwargs
        self.assertEqual(kwargs['nunota'], 100)
        self.assertEqual(kwargs['sequencia'], 1)
        self.assertEqual(kwargs['codagregacao'], 'NUNOTAS100D260424')
        self.assertIsNone(kwargs['qtd'])

    @patch('sankhya_integration.views.atribuir_lote_item_pedido')
    def test_atribuicao_parcial_passa_qtd(self, mock_fn):
        mock_fn.return_value = {
            'ok': True, 'operacao': 'SPLIT',
            'qtd_atribuida': 50.0, 'nova_sequencia': 2,
        }
        payload = {
            'nunota': 100, 'sequencia': 1,
            'codagregacao': 'L1', 'qtd': 50,
        }
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        kwargs = mock_fn.call_args.kwargs
        self.assertEqual(kwargs['qtd'], 50.0)

    @patch('sankhya_integration.views.atribuir_lote_item_pedido')
    def test_falha_de_negocio_retorna_400(self, mock_fn):
        mock_fn.return_value = {
            'ok': False,
            'error': 'Saldo insuficiente no lote L1: disponível=10, solicitado=200',
        }
        payload = {
            'nunota': 100, 'sequencia': 1,
            'codagregacao': 'L1', 'qtd': 200,
        }
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('Saldo insuficiente', data['error'])

    @patch('sankhya_integration.views.atribuir_lote_item_pedido',
           side_effect=Exception('erro inesperado'))
    def test_excecao_retorna_500(self, _mock):
        payload = {
            'nunota': 100, 'sequencia': 1, 'codagregacao': 'L1',
        }
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 500)
