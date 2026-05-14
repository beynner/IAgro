"""
Testes do módulo Controle de Combustível.

Cobertura:
    - view_portal_combustivel               → render protegido por grupo 'frota'
    - api_listar_estoque_combustivel        → GET, lê ANDRE_IAGRO_SALDO_COMBUSTIVEL
    - api_listar_veiculos                   → GET, lista TGFVEI
    - api_listar_produtos_combustivel       → GET, typeahead CODGRUPOPROD=11
    - api_listar_requisicoes_combustivel    → GET, lista TOP 26 + AD_REQUISICAO_COMBUSTIVEL
    - api_obter_requisicao_combustivel      → GET, detalhe
    - api_criar_requisicao_combustivel      → POST, retorna 501 enquanto B2 não aprovada

Todas as chamadas ao Oracle são mockadas.
"""
import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock

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
# view_portal_combustivel — controle de acesso
# ---------------------------------------------------------------------------

class PortalCombustivelAcessoTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('combustivel_portal')

    def test_sem_sessao_redireciona_para_home(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_grupo_desconhecido_redireciona_para_home(self):
        _login_session(self.client, grupos=['99'])
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_diretoria_acessa(self):
        _login_session(self.client, grupos=['1'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_grupo_frota_acessa(self):
        _login_session(self.client, grupos=['11'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_grupo_administrativo_acessa(self):
        # 2026-05-14 — IAGRO_ADMINISTRATIVO (CODGRUPO=10) ganhou acesso ao
        # Combustível pra fazer lançamento junto com o pessoal da frota.
        _login_session(self.client, grupos=['10'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# api_listar_estoque_combustivel
# ---------------------------------------------------------------------------

class ApiListarEstoqueCombustivelTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_estoque')

    @patch('sankhya_integration.views.consultar_saldo_combustivel')
    def test_retorna_lista_de_combustiveis(self, mock_saldo):
        # Tupla (Mai/2026 — tanques mapeados):
        # (CODPROD, DESCRPROD, CODVOL, QTD_ENTRADA, QTD_SAIDA, QTD_DISPONIVEL,
        #  CAPACIDADE_LT, SALDO_INICIAL_LT, PERCENTUAL_CHEIO)
        mock_saldo.return_value = [
            (392,  'DIESEL S10',  'LT', 5300.0, 500.0, 4800.0, 10000.0, 300.0,  48.0),
            (1373, 'DIESEL S500', 'LT', 4150.0,   0.0, 4150.0,  5000.0, 3150.0, 83.0),
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['items']), 2)
        item_s10 = data['items'][0]
        self.assertEqual(item_s10['descrprod'], 'DIESEL S10')
        self.assertEqual(item_s10['qtd_disponivel'], 4800.0)
        self.assertEqual(item_s10['capacidade_lt'], 10000.0)
        self.assertEqual(item_s10['saldo_inicial'], 300.0)
        self.assertEqual(item_s10['percentual'], 48.0)
        # Item não tem mais codemp
        self.assertNotIn('codemp', item_s10)

    @patch('sankhya_integration.views.consultar_saldo_combustivel')
    def test_filtro_q_passa_pra_service(self, mock_saldo):
        mock_saldo.return_value = []
        self.client.get(self.url, {'q': 'diesel'})
        args, kwargs = mock_saldo.call_args
        filtros = args[0] if args else kwargs.get('filtros')
        self.assertEqual(filtros.get('q'), 'diesel')

    @patch('sankhya_integration.views.consultar_saldo_combustivel')
    def test_excecao_no_oracle_retorna_500(self, mock_saldo):
        mock_saldo.side_effect = RuntimeError('falha simulada')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json()['ok'])


class ConsultarSaldoCombustivelServiceTest(TestCase):
    """Exercita a função real de consultar_saldo_combustivel pra pegar bugs
    de aritmética (Mai/2026: GREATEST da view zerava entrada negativa, somar
    saldo inicial em cima inflava o disponível e ignorava saídas).
    """

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_disponivel_desconta_saida_quando_entrada_view_zero(self, mock_conn):
        """Regressão Mai/2026: tanque com saldo_inicial=300, entrada_view=0,
        saída=100 → disponível deve ser 200 LT (não 300).
        Antes do fix, o GREATEST da view zerava (0 - 100 = -100 → 0) e somar
        saldo_inicial 300 dava 300, ignorando os 100 LT consumidos.
        """
        from sankhya_integration.services.oracle_conn import consultar_saldo_combustivel

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx

        # cursor.execute é chamado 2x: SELECT da view + SELECT do TGFPRO.
        # fetchall na 1ª: rows da view; na 2ª: nomes dos produtos.
        chamadas = [
            # 1ª — SELECT da view ANDRE_IAGRO_SALDO_COMBUSTIVEL
            #     S10 com entrada_view=0, saída=100, disponivel_view=0 (GREATEST)
            [(392, 'DIESEL S10', 'LT', 0.0, 100.0, 0.0)],
            # 2ª — SELECT TGFPRO (CODPROD, DESCRPROD, CODVOL)
            [(392, 'DIESEL S10', 'LT'), (1373, 'DIESEL S500', 'LT')],
        ]
        cursor.fetchall.side_effect = chamadas

        rows = consultar_saldo_combustivel()
        # Procura S10 (CODPROD=392)
        s10 = next(r for r in rows if r[0] == 392)
        # tupla: (CODPROD, DESCRPROD, CODVOL, QTD_ENT_TOTAL, QTD_SAI,
        #         QTD_DISPONIVEL, CAPACIDADE, SALDO_INICIAL, PERCENTUAL)
        self.assertEqual(s10[3], 300.0, "entrada_total = 0 + saldo_inicial 300")
        self.assertEqual(s10[4], 100.0, "saída lida da view")
        self.assertEqual(s10[5], 200.0,
            "DISPONÍVEL DEVE SER 200 (300 - 100), não 300. Bug pré-fix: ignorava saída.")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_tanque_sem_movimentacao_usa_saldo_inicial(self, mock_conn):
        """Tanque sem nenhuma movimentação (nem view, só TGFPRO) → saldo igual
        ao SALDO_INICIAL_TANQUE.
        """
        from sankhya_integration.services.oracle_conn import consultar_saldo_combustivel

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # View não retorna nada (tanque sem TGFITE)
        cursor.fetchall.side_effect = [
            [],  # SELECT da view: vazio
            [(392, 'DIESEL S10', 'LT'), (1373, 'DIESEL S500', 'LT')],  # SELECT TGFPRO
        ]

        rows = consultar_saldo_combustivel()
        s500 = next(r for r in rows if r[0] == 1373)
        # S500 SALDO_INICIAL_TANQUE = 3150
        self.assertEqual(s500[3], 3150.0)
        self.assertEqual(s500[4], 0.0)
        self.assertEqual(s500[5], 3150.0)
        self.assertEqual(s500[1], 'DIESEL S500',
            "Nome deve vir de TGFPRO mesmo sem registro na view")


# ---------------------------------------------------------------------------
# api_listar_veiculos
# ---------------------------------------------------------------------------

class ApiListarVeiculosTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_veiculos')

    @patch('sankhya_integration.views.consultar_veiculos_disponiveis')
    def test_lista_veiculos(self, mock_vei):
        # (CODVEICULO, PLACA, MARCAMODELO, ESPECIETIPO, PROPRIO,
        #  COMBUSTIVEL, CODPARC, NOMEPARC, CODCENCUS, CODFUNC,
        #  CODMOTORISTA, ATIVO)
        mock_vei.return_value = [
            (27, 'JBB5I99', 'MERCEDS 2544', 'CAVALO', 'S', 'D', 26, 'AGROMIL', 1001, None, 0, 'S'),
            (25, 'FWB4A41', 'FIAT STRADA', 'FIAT/STRADA', 'S', 'F', 26, 'AGROMIL', 1001, None, 0, 'S'),
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['placa'], 'JBB5I99')

    @patch('sankhya_integration.views.consultar_veiculos_disponiveis')
    def test_filtro_tipo_externa_frete_passa_pra_service(self, mock_vei):
        mock_vei.return_value = []
        self.client.get(self.url, {'tipo': 'EXTERNA_FRETE'})
        _, kwargs = mock_vei.call_args
        self.assertEqual(kwargs.get('tipo'), 'EXTERNA_FRETE')

    @patch('sankhya_integration.views.consultar_veiculos_disponiveis')
    def test_filtro_q_passa_pra_service(self, mock_vei):
        mock_vei.return_value = []
        self.client.get(self.url, {'q': 'JBB'})
        _, kwargs = mock_vei.call_args
        self.assertEqual(kwargs.get('termo'), 'JBB')


# ---------------------------------------------------------------------------
# api_listar_produtos_combustivel
# ---------------------------------------------------------------------------

class ApiListarProdutosCombustivelTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_produtos')

    @patch('sankhya_integration.views.consultar_produtos_combustivel')
    def test_lista_produtos(self, mock_prod):
        mock_prod.return_value = [
            (5001, 'DIESEL S10', 'L'),
            (5002, 'GASOLINA C', 'L'),
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['codprod'], 5001)
        self.assertEqual(data['results'][0]['codvol'], 'L')


# ---------------------------------------------------------------------------
# api_listar_requisicoes_combustivel
# ---------------------------------------------------------------------------

class ApiListarRequisicoesTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_requisicoes')

    @patch('sankhya_integration.views.listar_requisicoes_combustivel')
    def test_lista_requisicoes(self, mock_lst):
        # tupla Mai/2026 (hodômetro_km + horímetro_h em vez de medidor genérico):
        # (NUNOTA, NUMNOTA, CODEMP, CODPARC, NOMEPARC, DTNEG, STATUSNOTA,
        #  VLRNOTA, QTDVOL, REQ_ID, REQ_TIPO, REQ_CODVEICULO, REQ_PLACA,
        #  REQ_MARCAMODELO, REQ_HODOMETRO_KM, REQ_HORIMETRO_H, REQ_DOC_FRETE_REF,
        #  REQ_OBSERVACAO, REQ_NOMEUSU, REQ_CRIADO_EM,
        #  CODPROD, DESCRPROD, CODVOL, QTDNEG_TOTAL)
        mock_lst.return_value = [
            (123, 456, 1, 26, 'AGROMIL', datetime(2026, 5, 10),
             None, 1500.0, 0.0, 1, 'INTERNA_FROTA', 27, 'JBB5I99',
             'MERCEDS 2544', 50000.0, 4321.5, None, 'Abast. semanal',
             'Teste', datetime(2026, 5, 10, 8, 30),
             5001, 'DIESEL S10', 'L', 200.0),
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['items']), 1)
        item = data['items'][0]
        self.assertEqual(item['nunota'], 123)
        self.assertEqual(item['requisicao']['placa'], 'JBB5I99')
        self.assertEqual(item['requisicao']['hodometro_km'], 50000.0)
        self.assertEqual(item['requisicao']['horimetro_h'], 4321.5)
        self.assertEqual(item['requisicao']['tipo'], 'INTERNA_FROTA')

    @patch('sankhya_integration.views.listar_requisicoes_combustivel')
    def test_filtro_status_aberto_passa_pra_service(self, mock_lst):
        mock_lst.return_value = []
        self.client.get(self.url, {'status': 'aberto'})
        args, kwargs = mock_lst.call_args
        filtros = args[0] if args else kwargs.get('filtros')
        self.assertEqual(filtros.get('status'), 'aberto')

    @patch('sankhya_integration.views.listar_requisicoes_combustivel')
    def test_filtro_tipo_passa_pra_service(self, mock_lst):
        mock_lst.return_value = []
        self.client.get(self.url, {'tipo': 'INTERNA_MAQUINARIO'})
        args, kwargs = mock_lst.call_args
        filtros = args[0] if args else kwargs.get('filtros')
        self.assertEqual(filtros.get('tipo'), 'INTERNA_MAQUINARIO')


# ---------------------------------------------------------------------------
# api_obter_requisicao_combustivel
# ---------------------------------------------------------------------------

class ApiObterRequisicaoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])

    @patch('sankhya_integration.views.obter_requisicao_combustivel')
    def test_retorna_404_se_nao_existe(self, mock_obter):
        mock_obter.return_value = None
        url = reverse('api_combustivel_obter_requisicao', args=[9999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @patch('sankhya_integration.views.obter_requisicao_combustivel')
    def test_retorna_detalhe(self, mock_obter):
        mock_obter.return_value = {
            'cabecalho': {
                'NUNOTA': 123, 'NUMNOTA': 456, 'CODEMP': 1, 'CODPARC': 26,
                'NOMEPARC': 'AGROMIL', 'CODTIPOPER': 26, 'CODNAT': 30070200,
                'CODCENCUS': 1001, 'STATUSNOTA': None, 'DTNEG': date(2026, 5, 10),
                'DTMOV': date(2026, 5, 10), 'VLRNOTA': 1500.0, 'QTDVOL': 200.0,
                'OBSERVACAO': '', 'CODUSU': 1,
            },
            'itens': [
                {'SEQUENCIA': 1, 'CODPROD': 5001, 'DESCRPROD': 'DIESEL S10',
                 'CODVOL': 'L', 'QTDNEG': 200.0, 'VLRUNIT': 7.5, 'VLRTOT': 1500.0,
                 'CODGRUPOPROD': 11},
            ],
            'requisicao': {
                'ID': 1, 'TIPO': 'INTERNA_FROTA', 'CODVEICULO': 27,
                'PLACA': 'JBB5I99', 'MARCAMODELO': 'MERCEDS 2544',
                'ESPECIETIPO': 'CAVALO', 'PROPRIO': 'S', 'COMBUSTIVEL': 'D',
                'VEI_CODCENCUS': 1001,
                'HODOMETRO_KM': 50000.0, 'HORIMETRO_H': 4321.5,
                'DOC_FRETE_REF': '',
                'OBSERVACAO': '', 'CODUSU': 1, 'NOMEUSU': 'Teste',
                'CRIADO_EM': datetime(2026, 5, 10, 8, 30),
            },
        }
        url = reverse('api_combustivel_obter_requisicao', args=[123])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['cabecalho']['NUNOTA'], 123)
        self.assertEqual(len(data['itens']), 1)
        self.assertEqual(data['requisicao']['PLACA'], 'JBB5I99')


# ---------------------------------------------------------------------------
# api_criar_requisicao_combustivel (B2 — TOP 26 saída)
# ---------------------------------------------------------------------------

class ApiCriarRequisicaoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_criar_requisicao')

    @patch('sankhya_integration.views.criar_requisicao_combustivel_banco')
    def test_sucesso_201(self, mock_criar):
        mock_criar.return_value = {'ok': True, 'nunota': 99001, 'requisicao_id': 42}
        payload = {
            'codveiculo': 27, 'codprod': 5001, 'qtd': 200.0,
            'tipo': 'INTERNA_FROTA', 'codcencus': 1001,
        }
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['nunota'], 99001)
        # service deve receber codusu da sessão
        _, kwargs = mock_criar.call_args
        self.assertEqual(kwargs.get('codusu'), 1)

    @patch('sankhya_integration.views.criar_requisicao_combustivel_banco')
    def test_falha_validacao_retorna_400(self, mock_criar):
        mock_criar.return_value = {'ok': False, 'error': 'Saldo insuficiente.'}
        payload = {'codveiculo': 27, 'codprod': 5001, 'qtd': 9999.0,
                   'tipo': 'INTERNA_FROTA', 'codcencus': 1001}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Saldo', response.json()['error'])

    def test_sem_sessao_redireciona(self):
        cli = Client()
        response = cli.post(self.url, data='{}', content_type='application/json')
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# api_criar_entrada_combustivel (B3 — TOP 10 entrada + TGFFIN)
# ---------------------------------------------------------------------------

class ApiCriarEntradaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_criar_entrada')

    @patch('sankhya_integration.views.criar_entrada_combustivel_banco')
    def test_sucesso_201(self, mock_criar):
        mock_criar.return_value = {
            'ok': True, 'nunota': 99100, 'numnota': 555, 'nufin': 438999
        }
        payload = {
            'codemp': 1, 'codparc': 579, 'codprod': 5001,
            'qtd': 5000.0, 'vlrunit': 6.85, 'codcencus': 1001,
            'dtneg': '2026-05-12',
        }
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['nufin'], 438999)

    @patch('sankhya_integration.views.criar_entrada_combustivel_banco')
    def test_falha_validacao_retorna_400(self, mock_criar):
        mock_criar.return_value = {'ok': False, 'error': 'qtd deve ser > 0'}
        payload = {'codemp': 1, 'codparc': 579, 'codprod': 5001,
                   'qtd': 0, 'vlrunit': 6.85, 'codcencus': 1001}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_sem_sessao_redireciona(self):
        cli = Client()
        response = cli.post(self.url, data='{}', content_type='application/json')
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# api_listar_movimentacoes_combustivel (UNION entradas + requisições)
# ---------------------------------------------------------------------------

class ApiListarMovimentacoesTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_movimentacoes')

    @patch('sankhya_integration.views.listar_movimentacoes_combustivel')
    def test_lista_mistura_entradas_e_requisicoes(self, mock_lst):
        # tupla de 24 colunas (Mai/2026 — 1 linha por item via JOIN TGFITE):
        # (TIPO_MOVIMENTO, NUNOTA, NUMNOTA, CODEMP, CODPARC, NOMEPARC,
        #  DTNEG, STATUSNOTA, VLRNOTA, QTDVOL,
        #  REQ_ID, REQ_TIPO, REQ_CODVEICULO, REQ_PLACA, REQ_MARCAMODELO,
        #  REQ_HODOMETRO_KM, REQ_HORIMETRO_H, REQ_DOC_FRETE_REF,
        #  SEQUENCIA, CODPROD, DESCRPROD, CODVOL, QTDNEG_ITEM, VLRTOT_ITEM)
        mock_lst.return_value = [
            # Mesma NUNOTA 99100 com 2 itens (S10 + S500) — agora vira 2 linhas
            ('ENTRADA', 99100, 555, 1, 579, 'MASUT DISTRIBUIDORA',
             datetime(2026, 5, 12), 'L', 34250.0, 6000.0,
             None, None, None, None, None, None, None, None,
             1, 392, 'DIESEL S10', 'LT', 5000.0, 28000.0),
            ('ENTRADA', 99100, 555, 1, 579, 'MASUT DISTRIBUIDORA',
             datetime(2026, 5, 12), 'L', 34250.0, 6000.0,
             None, None, None, None, None, None, None, None,
             2, 1373, 'DIESEL S500', 'LT', 1000.0, 6250.0),
            ('REQUISICAO', 99200, None, 1, 26, 'AGROMIL',
             datetime(2026, 5, 12), None, 1500.0, 200.0,
             7, 'INTERNA_FROTA', 27, 'JBB5I99', 'MERCEDS 2544',
             50000.0, 4321.5, None,
             1, 392, 'DIESEL S10', 'LT', 200.0, 1500.0),
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['items']), 3)  # 2 itens da entrada + 1 da requisição
        # Linha 1: entrada item 1 (S10)
        self.assertEqual(data['items'][0]['tipo_movimento'], 'ENTRADA')
        self.assertEqual(data['items'][0]['nunota'], 99100)
        self.assertEqual(data['items'][0]['descrprod'], 'DIESEL S10')
        self.assertEqual(data['items'][0]['qtdneg_item'], 5000.0)
        self.assertEqual(data['items'][0]['sequencia'], 1)
        self.assertIsNone(data['items'][0]['requisicao'])
        # Linha 2: entrada item 2 (S500) — mesma NUNOTA, qtd diferente
        self.assertEqual(data['items'][1]['nunota'], 99100)
        self.assertEqual(data['items'][1]['descrprod'], 'DIESEL S500')
        self.assertEqual(data['items'][1]['qtdneg_item'], 1000.0)
        self.assertEqual(data['items'][1]['sequencia'], 2)
        # Linha 3: requisição
        self.assertEqual(data['items'][2]['tipo_movimento'], 'REQUISICAO')
        self.assertEqual(data['items'][2]['requisicao']['placa'], 'JBB5I99')
        self.assertEqual(data['items'][2]['requisicao']['hodometro_km'], 50000.0)
        self.assertEqual(data['items'][2]['requisicao']['horimetro_h'], 4321.5)
        self.assertEqual(data['items'][2]['qtdneg_item'], 200.0)

    @patch('sankhya_integration.views.listar_movimentacoes_combustivel')
    def test_filtro_mov_entrada_passa_pra_service(self, mock_lst):
        mock_lst.return_value = []
        self.client.get(self.url, {'mov': 'ENTRADA'})
        args, kwargs = mock_lst.call_args
        filtros = args[0] if args else kwargs.get('filtros')
        self.assertEqual(filtros.get('mov'), 'ENTRADA')


# ---------------------------------------------------------------------------
# SERVICE REAL — criar_requisicao_combustivel_banco
# Cobertura: chama a função real do oracle_conn mockando só obter_conexao_oracle
# e helpers (inserir_cabecalho_nota_banco, inserir_item_nota_banco, recalcular)
# pra pegar bugs de payload — como o caso CODLOCALORIG=None de Mai/2026, que
# os mocks de view-level não pegavam.
# ---------------------------------------------------------------------------

def _conn_cursor_mock():
    """Constrói (conn_mock, cursor_mock) compatível com o context manager
    `with obter_conexao_oracle() as conn`."""
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn_ctx = MagicMock()
    conn_ctx.__enter__.return_value = conn
    conn_ctx.__exit__.return_value = False
    return conn_ctx, conn, cursor


class CriarRequisicaoServiceTest(TestCase):
    """Exercita a função real (sem mockar o service inteiro)."""

    def _setup_cursor_fluxo_feliz(self, cursor):
        """Configura side_effect do cursor pra simular um fluxo bem-sucedido:
        1) TGFVEI lookup → veiculo encontrado, PROPRIO='S'
        2) TGFPRO lookup → produto encontrado, CODGRUPOPROD=200400, CODVOL='LT'
        3) SALDO_COMBUSTIVEL → 5000 LT disponível
        4) MAX(CODEMP) → 1
        """
        cursor.fetchone.side_effect = [
            (1, 'S'),                         # TGFVEI: (CODPARC, PROPRIO)
            (200400, 'DIESEL S10', 'LT'),     # TGFPRO: (CODGRUPOPROD, DESCRPROD, CODVOL)
            (5000.0,),                        # SALDO_COMBUSTIVEL: QTD_DISPONIVEL
            (1,),                             # MAX(CODEMP)
        ]
        # Mock do RETURNING ID INTO :req_id
        cursor.var.return_value.getvalue.return_value = 42

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_feliz_frota_propria(self, mock_conn, mock_cab, mock_item, mock_rec):
        """Caminho feliz: frota própria com ambos medidores válidos."""
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        self._setup_cursor_fluxo_feliz(cursor)
        mock_cab.return_value = {'ok': True, 'nunota': 12345}
        mock_item.return_value = {'ok': True, 'nunota': 12345, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 500,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'hodometro_km': 142536, 'horimetro_h': 32451,
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(resultado['ok'], f"Resultado inesperado: {resultado}")
        self.assertEqual(resultado['nunota'], 12345)
        self.assertEqual(resultado['requisicao_id'], 42)

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_payload_inserir_item_nao_passa_codlocalorig_none(
        self, mock_conn, mock_cab, mock_item, mock_rec
    ):
        """Regressão (Mai/2026 — 2026-05-12): payload do inserir_item_nota_banco
        NÃO deve conter CODLOCALORIG=None. A função inserir_item_nota_banco faz
        `int(dados.get('CODLOCALORIG', 101))` e quando a chave existe com None,
        .get retorna None (não usa o default) e int(None) explode.
        """
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        self._setup_cursor_fluxo_feliz(cursor)
        mock_cab.return_value = {'ok': True, 'nunota': 12345}
        mock_item.return_value = {'ok': True, 'nunota': 12345, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 500,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'hodometro_km': 142536, 'horimetro_h': 32451,
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(mock_item.called, "inserir_item_nota_banco deveria ter sido chamado")
        args, kwargs = mock_item.call_args
        payload_item = args[0] if args else kwargs.get('dados')
        # CODLOCALORIG não deve existir no payload (ou se existir, não pode ser None)
        if 'CODLOCALORIG' in payload_item:
            self.assertIsNotNone(
                payload_item['CODLOCALORIG'],
                f"CODLOCALORIG=None no payload causa int(None) em inserir_item_nota_banco. "
                f"Payload: {payload_item}",
            )

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_valida_hodometro_obrigatorio_frota_propria(self, mock_conn):
        """Frota própria SEM hodômetro → retorna erro de validação ANTES de tocar no Oracle."""
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 500,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'horimetro_h': 32451,  # hodômetro faltando
        }, codusu=1, nomeusu='Teste')

        self.assertFalse(resultado['ok'])
        self.assertIn('hodômetro', resultado['error'].lower())
        # Validação acontece antes de tentar conectar
        self.assertFalse(mock_conn.called)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_valida_horimetro_obrigatorio_frota_propria(self, mock_conn):
        """Frota própria SEM horímetro → erro de validação."""
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 500,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'hodometro_km': 142536,  # horímetro faltando
        }, codusu=1, nomeusu='Teste')

        self.assertFalse(resultado['ok'])
        self.assertIn('horímetro', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_maquinario_aceita_sem_medidores(self, mock_conn, mock_cab, mock_item, mock_rec):
        """Maquinário fazenda → medidores opcionais. Não deve retornar erro."""
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # TGFVEI: PROPRIO='S' (necessário pra INTERNA_MAQUINARIO)
        cursor.fetchone.side_effect = [
            (1, 'S'), (200400, 'DIESEL S10', 'LT'),
            (5000.0,), (1,),
        ]
        cursor.var.return_value.getvalue.return_value = 42
        mock_cab.return_value = {'ok': True, 'nunota': 12345}
        mock_item.return_value = {'ok': True, 'nunota': 12345, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 500,
            'tipo': 'INTERNA_MAQUINARIO', 'codcencus': 10100,
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(resultado['ok'], f"Resultado inesperado: {resultado}")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_saldo_insuficiente_retorna_erro(self, mock_conn):
        """Saldo menor que solicitado → erro humanizado."""
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (1, 'S'),                         # TGFVEI ok
            (200400, 'DIESEL S10', 'LT'),     # TGFPRO ok
            (0.0,),                           # saldo na view: 0 (sem entrada IAgro)
        ]
        # CODPROD=392 tem SALDO_INICIAL_TANQUE=300; pedindo 500 deve falhar
        # (0 + 300 = 300 < 500)
        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 500,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'hodometro_km': 142536, 'horimetro_h': 32451,
        }, codusu=1, nomeusu='Teste')

        self.assertFalse(resultado['ok'])
        self.assertIn('insuficiente', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_saldo_inicial_tanque_soma_no_disponivel(
        self, mock_conn, mock_cab, mock_item, mock_rec,
    ):
        """Regressão Mai/2026: saldo da view (0) + SALDO_INICIAL_TANQUE (300 LT
        pra S10 CODPROD=392) deve permitir requisição de até 300 LT.

        Antes do fix, a validação só olhava QTD_DISPONIVEL da view e bloqueava
        qualquer requisição em tanque sem entrada IAgro.
        """
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (1, 'S'),                         # TGFVEI
            (200400, 'DIESEL S10', 'LT'),     # TGFPRO (CODPROD=392)
            (0.0,),                           # saldo view = 0 (sem entrada IAgro)
            (1,),                             # MAX(CODEMP) = 1
        ]
        cursor.var.return_value.getvalue.return_value = 99
        mock_cab.return_value = {'ok': True, 'nunota': 55555}
        mock_item.return_value = {'ok': True, 'nunota': 55555, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        # 250 LT solicitado: cabe nos 300 LT de saldo inicial
        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 392, 'qtd': 250,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'hodometro_km': 142536, 'horimetro_h': 32451,
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(resultado['ok'], f"Saldo inicial não foi somado: {resultado}")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_produto_sem_tanque_mapeado_bloqueia(self, mock_conn):
        """Produto fora de CAPACIDADE_TANQUE → bloqueia requisição.
        Ex: Gasolina (391) está no grupo COMBUSTÍVEIS mas sem tanque mapeado.
        """
        from sankhya_integration.services.oracle_conn import criar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (1, 'S'),                         # TGFVEI ok
            (200400, 'GASOLINA', 'LT'),       # TGFPRO ok (CODPROD=391 — sem tanque)
        ]

        resultado = criar_requisicao_combustivel_banco({
            'codveiculo': 5, 'codprod': 391, 'qtd': 100,
            'tipo': 'INTERNA_FROTA', 'codcencus': 10100,
            'hodometro_km': 142536, 'horimetro_h': 32451,
        }, codusu=1, nomeusu='Teste')

        self.assertFalse(resultado['ok'])
        self.assertIn('tanque', resultado['error'].lower())


# ---------------------------------------------------------------------------
# SERVICE REAL — editar_requisicao_combustivel_banco (B5) e
#                excluir_requisicao_combustivel_banco (B6)
# ---------------------------------------------------------------------------

class EditarRequisicaoServiceTest(TestCase):
    """B5 — editar requisição em aberto."""

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_feliz_altera_qtd(self, mock_conn, mock_rec):
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx

        # fetchone na ordem: (1) estado atual da req, (2) TGFVEI, (3) TGFPRO,
        # (4) saldo na view
        # Mai/2026 (B11): SELECT do estado atual ganhou 2 colunas extras
        # (REQ_CODPARC, REQ_NUFIN_GERADO) entre AD_REQ DOC/OBS e TGFITE.
        cursor.fetchone.side_effect = [
            ('P', 1, 10100,                                    # TGFCAB (STATUS, CODPARC, CODCENCUS)
             'INTERNA_FROTA', 5, 50000.0, 5000.0,              # AD_REQ (TIPO, VEI, HOD, HOR)
             None, None,                                       # AD_REQ (DOC, OBS)
             None, None,                                       # AD_REQ (CODPARC, NUFIN_GERADO)
             1, 392, 200.0, 0.0, 'LT'),                        # TGFITE (SEQ, CODPROD, QTD, VLU, CODVOL)
            (1, 'S'),                                          # TGFVEI ok
            (200400, 'DIESEL S10', 'LT'),                      # TGFPRO ok
            (4500.0,),                                         # saldo view
        ]
        mock_rec.return_value = {'ok': True}

        # Aumenta a qtd de 200 pra 500 (cabe nos 4500 + 200 antigos = 4700)
        resultado = editar_requisicao_combustivel_banco(
            nunota=112209,
            dados={'qtd': 500},
            codusu=1, nomeusu='Teste',
        )

        self.assertTrue(resultado['ok'], f"Editar falhou: {resultado}")
        self.assertEqual(resultado['nunota'], 112209)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_status_l_confirmada(self, mock_conn):
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (
            'L', 1, 10100,                                     # STATUSNOTA='L'
            'INTERNA_FROTA', 5, 50000.0, 5000.0,
            None, None,
            None, None,                                        # AD_REQ (CODPARC, NUFIN_GERADO)
            1, 392, 200.0, 0.0, 'LT',
        )
        resultado = editar_requisicao_combustivel_banco(
            nunota=112209, dados={'qtd': 500}, codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('sankhya', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_status_e_excluida(self, mock_conn):
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (
            'E', 1, 10100,
            'INTERNA_FROTA', 5, 50000.0, 5000.0,
            None, None,
            None, None,
            1, 392, 200.0, 0.0, 'LT',
        )
        resultado = editar_requisicao_combustivel_banco(
            nunota=112209, dados={'qtd': 500}, codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('exclu', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_requisicao_nao_existe(self, mock_conn):
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = None

        resultado = editar_requisicao_combustivel_banco(
            nunota=999999, dados={'qtd': 500}, codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('encontrada', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_saldo_insuficiente_mesmo_com_qtd_antiga_devolvendo(self, mock_conn, mock_rec):
        """Mesmo devolvendo a qtd antiga, saldo pode ser insuficiente pra qtd nova."""
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            ('P', 1, 10100,
             'INTERNA_FROTA', 5, 50000.0, 5000.0,
             None, None,
             None, None,                                       # AD_REQ (CODPARC, NUFIN_GERADO)
             1, 392, 200.0, 0.0, 'LT'),
            (1, 'S'),                                          # TGFVEI ok
            (200400, 'DIESEL S10', 'LT'),                      # TGFPRO ok
            (50.0,),                                           # saldo view = 50 LT
        ]
        # Antiga: 200 LT; saldo view: 50; saldo_inicial S10: 300
        # disponivel_efetivo = 50 + 300 + 200 = 550. Tenta pedir 10000 → falha.
        resultado = editar_requisicao_combustivel_banco(
            nunota=112209, dados={'qtd': 10000},
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('insuficiente', resultado['error'].lower())


class ExcluirRequisicaoServiceTest(TestCase):
    """B6 — excluir requisição em aberto (DELETE AD_REQ + UPDATE TGFCAB STATUSNOTA='E')."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_feliz_delete_fisico(self, mock_conn):
        """Mai/2026 (2026-05-12): exclusão agora é DELETE físico em TGFITE +
        TGFCAB (UPDATE STATUSNOTA='E' bloqueado pelo trigger Sankhya
        TRG_UPD_TGFCAB).
        """
        from sankhya_integration.services.oracle_conn import excluir_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # Mai/2026 (B12): SELECT agora retorna (STATUSNOTA, TIPO, NUFIN_GERADO)
        # em vez de (STATUSNOTA, HAS_AD_count).
        cursor.fetchone.return_value = ('P', 'INTERNA_FROTA', None)

        resultado = excluir_requisicao_combustivel_banco(
            nunota=112209, motivo='Lançamento de teste',
            codusu=1, nomeusu='ANDRE',
        )

        self.assertTrue(resultado['ok'], f"Excluir falhou: {resultado}")
        self.assertEqual(resultado['nunota'], 112209)
        # 4 execuções: SELECT, DELETE AD_REQ, DELETE TGFITE, DELETE TGFCAB
        self.assertGreaterEqual(cursor.execute.call_count, 4)

        # Regressão: garante que NÃO há mais UPDATE STATUSNOTA='E' (bloqueado)
        sqls_executados = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
        statusnota_e = any("STATUSNOTA" in sql and "'E'" in sql.replace(' ', '')
                           for sql in sqls_executados)
        self.assertFalse(
            statusnota_e,
            "B6 não deve mais usar UPDATE STATUSNOTA='E' — bloqueado pelo trigger Sankhya."
        )
        # Garante que tem DELETE em TGFCAB e TGFITE
        delete_tgfcab = any('DELETE' in sql and 'TGFCAB' in sql for sql in sqls_executados)
        delete_tgfite = any('DELETE' in sql and 'TGFITE' in sql for sql in sqls_executados)
        self.assertTrue(delete_tgfcab, "Deve haver DELETE FROM TGFCAB")
        self.assertTrue(delete_tgfite, "Deve haver DELETE FROM TGFITE")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_motivo_obrigatorio(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_requisicao_combustivel_banco

        # Motivo vazio: nem deve tocar no Oracle
        resultado = excluir_requisicao_combustivel_banco(
            nunota=112209, motivo='', codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('motivo', resultado['error'].lower())
        self.assertFalse(mock_conn.called)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_status_l(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = ('L', 'INTERNA_FROTA', None)

        resultado = excluir_requisicao_combustivel_banco(
            nunota=112209, motivo='qualquer motivo',
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('sankhya', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_requisicao_inexistente(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = None

        resultado = excluir_requisicao_combustivel_banco(
            nunota=999999, motivo='lixo',
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('encontrada', resultado['error'].lower())


# ---------------------------------------------------------------------------
# Views: api_editar_requisicao_combustivel + api_excluir_requisicao_combustivel
# (mockam o service)
# ---------------------------------------------------------------------------

class ApiEditarRequisicaoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_editar_requisicao', args=[112209])

    @patch('sankhya_integration.views.editar_requisicao_combustivel_banco')
    def test_sucesso_200(self, mock_edit):
        mock_edit.return_value = {'ok': True, 'nunota': 112209}
        response = self.client.post(
            self.url, data=json.dumps({'qtd': 500}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

    @patch('sankhya_integration.views.editar_requisicao_combustivel_banco')
    def test_falha_400(self, mock_edit):
        mock_edit.return_value = {'ok': False, 'error': 'Saldo insuficiente.'}
        response = self.client.post(
            self.url, data=json.dumps({'qtd': 999999}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class ApiExcluirRequisicaoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_excluir_requisicao', args=[112209])

    @patch('sankhya_integration.views.excluir_requisicao_combustivel_banco')
    def test_sucesso_200(self, mock_excl):
        mock_excl.return_value = {'ok': True, 'nunota': 112209}
        response = self.client.post(
            self.url, data=json.dumps({'motivo': 'teste'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_motivo_vazio_retorna_400(self):
        # Nem chega no service — view valida antes
        response = self.client.post(
            self.url, data=json.dumps({'motivo': ''}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('motivo', response.json()['error'].lower())


# ---------------------------------------------------------------------------
# SERVICE REAL — consultar_consumo_por_veiculo (Relatório)
# ---------------------------------------------------------------------------

class ConsumoPorVeiculoServiceTest(TestCase):

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_veiculo_inexistente_retorna_none(self, mock_conn):
        from sankhya_integration.services.oracle_conn import consultar_consumo_por_veiculo

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = None

        resultado = consultar_consumo_por_veiculo(999)
        self.assertIsNone(resultado)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_calcula_consumo_kmlt_entre_abastecimentos(self, mock_conn):
        """Frota própria (hodômetro): consumo km/L entre abastecimentos.
        Abastecimento 1: hodômetro 100.000 km, 200 LT
        Abastecimento 2: hodômetro 102.000 km, 250 LT
        → km percorridos = 102000 - 100000 = 2.000 km
        → consumo = 2.000 / 200 = 10 km/L (a qtd do 1º foi consumida pra rodar até o 2º)
        """
        from sankhya_integration.services.oracle_conn import consultar_consumo_por_veiculo

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (
            5, 'NLM6688', 'VOLVO/VM', 'CAVALO', 26, 'AGROMIL', 'S',
        )
        cursor.fetchall.return_value = [
            # NUNOTA, NUMNOTA, DTNEG, STATUSNOTA, VLRNOTA, TIPO, HOD, HOR,
            # DOC, OBS, CODPROD, DESCRPROD, QTDNEG, CODVOL, VLRTOT
            (101, None, date(2026, 5, 1), 'L', 1400.0, 'INTERNA_FROTA',
             100000.0, None, None, None, 392, 'DIESEL S10', 200.0, 'LT', 1400.0),
            (102, None, date(2026, 5, 10), 'L', 1750.0, 'INTERNA_FROTA',
             102000.0, None, None, None, 392, 'DIESEL S10', 250.0, 'LT', 1750.0),
        ]

        r = consultar_consumo_por_veiculo(5, date_start='2026-05-01', date_end='2026-05-31')

        self.assertEqual(r['veiculo']['placa'], 'NLM6688')
        self.assertEqual(len(r['abastecimentos']), 2)
        # 1º abastecimento sem consumo (referência)
        self.assertIsNone(r['abastecimentos'][0]['km_percorridos'])
        self.assertIsNone(r['abastecimentos'][0]['consumo_kmlt'])
        # 2º com consumo calculado
        self.assertEqual(r['abastecimentos'][1]['km_percorridos'], 2000.0)
        self.assertEqual(r['abastecimentos'][1]['consumo_kmlt'], 10.0)
        # Totais
        self.assertEqual(r['totais']['qtd_abastecimentos'], 2)
        self.assertEqual(r['totais']['total_litros'], 450.0)
        self.assertEqual(r['totais']['km_total'], 2000.0)
        self.assertEqual(r['totais']['consumo_medio_kmlt'], 10.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_calcula_consumo_lth_horimetro(self, mock_conn):
        """Maquinário (horímetro): consumo L/h."""
        from sankhya_integration.services.oracle_conn import consultar_consumo_por_veiculo

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (
            10, 'TRT001', 'TRATOR JOHN DEERE', 'TRATOR', 1, 'AGROMIL', 'S',
        )
        cursor.fetchall.return_value = [
            (201, None, date(2026, 5, 1), 'L', 350.0, 'INTERNA_MAQUINARIO',
             None, 1000.0, None, None, 392, 'DIESEL S10', 50.0, 'LT', 350.0),
            (202, None, date(2026, 5, 5), 'L', 700.0, 'INTERNA_MAQUINARIO',
             None, 1010.0, None, None, 392, 'DIESEL S10', 100.0, 'LT', 700.0),
        ]
        r = consultar_consumo_por_veiculo(10, date_start='2026-05-01', date_end='2026-05-31')

        # 1010 - 1000 = 10 h; qtd anterior 50 → 50/10 = 5 L/h
        self.assertEqual(r['abastecimentos'][1]['h_trabalhadas'], 10.0)
        self.assertEqual(r['abastecimentos'][1]['consumo_lth'], 5.0)
        self.assertEqual(r['totais']['h_total'], 10.0)
        self.assertEqual(r['totais']['consumo_medio_lth'], 5.0)
        self.assertIsNone(r['totais']['consumo_medio_kmlt'])


# ---------------------------------------------------------------------------
# View: api_relatorio_consumo_veiculo
# ---------------------------------------------------------------------------

class ApiRelatorioConsumoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_relatorio_consumo')

    @patch('sankhya_integration.views.consultar_consumo_por_veiculo')
    def test_sucesso_200(self, mock_consumo):
        mock_consumo.return_value = {
            'veiculo': {'codveiculo': 5, 'placa': 'NLM6688',
                        'marcamodelo': 'VOLVO', 'especietipo': 'CAVALO',
                        'codparc': 1, 'nomeparc': 'AGROMIL', 'proprio': 'S'},
            'periodo': {'inicio': '2026-05-01', 'fim': '2026-05-31'},
            'abastecimentos': [],
            'totais': {'qtd_abastecimentos': 0, 'total_litros': 0.0,
                       'total_vlr': 0.0, 'km_total': 0.0, 'h_total': 0.0,
                       'consumo_medio_kmlt': None, 'consumo_medio_lth': None,
                       'periodo_dias': 31},
        }
        response = self.client.get(self.url, {'codveiculo': '5'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['veiculo']['placa'], 'NLM6688')

    def test_sem_codveiculo_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('codveiculo', response.json()['error'].lower())

    @patch('sankhya_integration.views.consultar_consumo_por_veiculo')
    def test_veiculo_inexistente_404(self, mock_consumo):
        mock_consumo.return_value = None
        response = self.client.get(self.url, {'codveiculo': '999'})
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# B8 (Mai/2026 — 2026-05-13) — criar_abastecimento_externo_banco
# Abastecimento externo (posto): TGFCAB TOP 26 'L' + TGFITE + AD_REQ
# EXTERNA_POSTO + TGFFIN. NÃO desconta saldo dos tanques internos.
# ---------------------------------------------------------------------------

class CriarAbastecimentoExternoServiceTest(TestCase):
    """B8 — função criar_abastecimento_externo_banco."""

    def _setup_fluxo_feliz(self, cursor):
        """fetchone na ordem:
           (1) TGFVEI veiculo encontrado (PLACA,)
           (2) TGFPAR posto encontrado (NOMEPARC,)
           (3) TGFPRO produto encontrado (CODGRUPOPROD, DESCRPROD, CODVOL)
           (4) MAX(CODEMP) do parceiro
           (5) MAX(NUMNOTA) + 1 → numnota sequencial
           (6) MAX(NUFIN) + 1 → nufin novo
        """
        cursor.fetchone.side_effect = [
            ('NLM6688',),                            # TGFVEI
            ('POSTO ALLIANZ',),                      # TGFPAR
            (200400, 'DIESEL S10', 'LT'),            # TGFPRO
            (1,),                                    # MAX(CODEMP)
            (42,),                                   # MAX(NUMNOTA)+1
            (999000,),                               # MAX(NUFIN)+1
        ]
        cursor.var.return_value.getvalue.return_value = 88

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_feliz_gera_tgffin(self, mock_conn, mock_cab, mock_item, mock_rec):
        from sankhya_integration.services.oracle_conn import criar_abastecimento_externo_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        self._setup_fluxo_feliz(cursor)
        mock_cab.return_value = {'ok': True, 'nunota': 200001}
        mock_item.return_value = {'ok': True, 'nunota': 200001, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        resultado = criar_abastecimento_externo_banco({
            'codveiculo': 5, 'codparc': 1, 'codprod': 392,
            'qtd': 60, 'vlrunit': 6.20, 'codcencus': 10100,
            'hodometro_km': 152000,
            'doc_frete_ref': 'NF 12345',
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(resultado['ok'], f"Resultado inesperado: {resultado}")
        self.assertEqual(resultado['nunota'], 200001)
        self.assertEqual(resultado['nufin'], 999000)
        self.assertEqual(resultado['requisicao_id'], 88)

        # Garante que NÃO houve query de saldo (não desconta tanque) — varre os SQLs
        sqls = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
        consulta_saldo = any('ANDRE_IAGRO_SALDO_COMBUSTIVEL' in sql for sql in sqls)
        self.assertFalse(consulta_saldo,
            "EXTERNA_POSTO não deve consultar saldo do tanque (não desconta).")

        # Garante que houve INSERT em TGFFIN
        insert_fin = any('INSERT' in sql and 'TGFFIN' in sql for sql in sqls)
        self.assertTrue(insert_fin, "EXTERNA_POSTO deve inserir TGFFIN (despesa).")

        # Garante que houve INSERT em AD_REQUISICAO_COMBUSTIVEL com EXTERNA_POSTO
        insert_ad = any('AD_REQUISICAO_COMBUSTIVEL' in sql and 'EXTERNA_POSTO' in sql for sql in sqls)
        self.assertTrue(insert_ad, "AD_REQ deve gravar TIPO='EXTERNA_POSTO'.")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_codparc_obrigatorio(self, mock_conn):
        from sankhya_integration.services.oracle_conn import criar_abastecimento_externo_banco
        resultado = criar_abastecimento_externo_banco({
            'codveiculo': 5, 'codprod': 392,
            'qtd': 60, 'vlrunit': 6.20, 'codcencus': 10100,
            'hodometro_km': 152000,
            # codparc faltando
        }, codusu=1, nomeusu='Teste')
        self.assertFalse(resultado['ok'])
        self.assertIn('codparc', resultado['error'].lower())
        self.assertFalse(mock_conn.called)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_hodometro_obrigatorio(self, mock_conn):
        from sankhya_integration.services.oracle_conn import criar_abastecimento_externo_banco
        resultado = criar_abastecimento_externo_banco({
            'codveiculo': 5, 'codparc': 1, 'codprod': 392,
            'qtd': 60, 'vlrunit': 6.20, 'codcencus': 10100,
            # hodometro faltando — sem ele a curva de consumo fica com lacuna
        }, codusu=1, nomeusu='Teste')
        self.assertFalse(resultado['ok'])
        self.assertIn('hod', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_vlrunit_obrigatorio(self, mock_conn):
        from sankhya_integration.services.oracle_conn import criar_abastecimento_externo_banco
        resultado = criar_abastecimento_externo_banco({
            'codveiculo': 5, 'codparc': 1, 'codprod': 392,
            'qtd': 60, 'codcencus': 10100, 'hodometro_km': 152000,
            # vlrunit faltando — precisa pra gerar TGFFIN
        }, codusu=1, nomeusu='Teste')
        self.assertFalse(resultado['ok'])
        self.assertIn('vlrunit', resultado['error'].lower())


# ---------------------------------------------------------------------------
# B11 adaptado pra EXTERNA_POSTO + B12 adaptado pra deletar TGFFIN
# ---------------------------------------------------------------------------

class EditarRequisicaoExternoTest(TestCase):
    """B11 — adaptação Mai/2026: aceita TIPO='EXTERNA_POSTO'."""

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_externo_permite_editar_mesmo_status_l(self, mock_conn, mock_rec):
        """EXTERNA_POSTO nasce STATUSNOTA='L'. Edição deve passar (TGFFIN não baixado)."""
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # Estado inicial + DHBAIXA NULL + TGFVEI ok + TGFPRO ok + DTNEG/DTVENC do TGFFIN
        cursor.fetchone.side_effect = [
            ('L', 100, 10100,                                  # STATUS='L' + CODPARC=posto + CODCENCUS
             'EXTERNA_POSTO', 5, 152000.0, None,               # AD_REQ TIPO/VEI/HOD/HOR
             'NF 12345', None,                                 # AD_REQ DOC/OBS
             100, 555000,                                      # AD_REQ CODPARC + NUFIN_GERADO
             1, 392, 60.0, 6.20, 'LT'),                        # TGFITE
            (None,),                                           # DHBAIXA = NULL (financeiro em aberto)
            (1, 'S'),                                          # TGFVEI ok
            (200400, 'DIESEL S10', 'LT'),                      # TGFPRO ok
            # Não consulta saldo (externo); próxima fetchone é DTNEG/DTVENC do TGFFIN
            (date(2026, 5, 13), date(2026, 5, 13)),            # à vista
        ]
        mock_rec.return_value = {'ok': True}

        resultado = editar_requisicao_combustivel_banco(
            nunota=200001,
            dados={'qtd': 80, 'vlrunit': 6.30},
            codusu=1, nomeusu='Teste',
        )
        self.assertTrue(resultado['ok'], f"Editar externo falhou: {resultado}")
        # UPDATE em TGFFIN deve ter rolado
        sqls = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
        update_fin = any('UPDATE TGFFIN' in sql for sql in sqls)
        self.assertTrue(update_fin, "Edição de externo deve refletir VLR/HISTORICO no TGFFIN.")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_externo_bloqueia_se_tgffin_baixado(self, mock_conn):
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            ('L', 100, 10100,
             'EXTERNA_POSTO', 5, 152000.0, None,
             'NF 12345', None,
             100, 555000,
             1, 392, 60.0, 6.20, 'LT'),
            (date(2026, 5, 14),),                              # DHBAIXA preenchido — baixado
        ]
        resultado = editar_requisicao_combustivel_banco(
            nunota=200001, dados={'qtd': 80}, codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('baixado', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_troca_interno_externo(self, mock_conn):
        """Não permite alternar entre Interno e Externo na mesma requisição."""
        from sankhya_integration.services.oracle_conn import editar_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            ('P', 1, 10100,
             'INTERNA_FROTA', 5, 50000.0, 5000.0,
             None, None,
             None, None,
             1, 392, 200.0, 0.0, 'LT'),
        ]
        resultado = editar_requisicao_combustivel_banco(
            nunota=112209, dados={'tipo': 'EXTERNA_POSTO', 'codparc': 1},
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('alternar', resultado['error'].lower())


class ExcluirRequisicaoExternoTest(TestCase):
    """B12 — adaptação Mai/2026: EXTERNA_POSTO deleta TGFFIN antes do TGFCAB."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_externo_deleta_tgffin_em_cascata(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # (STATUSNOTA, TIPO, NUFIN_GERADO), depois DHBAIXA
        cursor.fetchone.side_effect = [
            ('L', 'EXTERNA_POSTO', 555000),
            (None,),                                           # DHBAIXA = NULL
        ]
        resultado = excluir_requisicao_combustivel_banco(
            nunota=200001, motivo='estornar lançamento errado',
            codusu=1, nomeusu='ANDRE',
        )
        self.assertTrue(resultado['ok'], f"Excluir externo falhou: {resultado}")
        # 5 execuções esperadas: SELECT, SELECT DHBAIXA, DELETE AD_REQ, DELETE TGFFIN, DELETE TGFITE, DELETE TGFCAB
        sqls = [str(call.args[0]).upper() for call in cursor.execute.call_args_list]
        delete_fin = any('DELETE FROM TGFFIN' in sql for sql in sqls)
        self.assertTrue(delete_fin,
            "EXTERNA_POSTO deve deletar TGFFIN antes do TGFCAB.")

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_externo_bloqueia_se_tgffin_baixado(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_requisicao_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            ('L', 'EXTERNA_POSTO', 555000),
            (date(2026, 5, 14),),                              # baixado
        ]
        resultado = excluir_requisicao_combustivel_banco(
            nunota=200001, motivo='vai falhar',
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('baixado', resultado['error'].lower())


# ---------------------------------------------------------------------------
# View: api_criar_abastecimento_externo
# ---------------------------------------------------------------------------

class ApiCriarAbastecimentoExternoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_criar_externo')

    @patch('sankhya_integration.views.criar_abastecimento_externo_banco')
    def test_sucesso_201(self, mock_ext):
        mock_ext.return_value = {
            'ok': True, 'nunota': 200001, 'numnota': 42,
            'requisicao_id': 88, 'nufin': 999000,
        }
        response = self.client.post(
            self.url,
            data=json.dumps({
                'codveiculo': 5, 'codparc': 1, 'codprod': 392,
                'qtd': 60, 'vlrunit': 6.20, 'codcencus': 10100,
                'hodometro_km': 152000,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['nufin'], 999000)

    @patch('sankhya_integration.views.criar_abastecimento_externo_banco')
    def test_falha_400(self, mock_ext):
        mock_ext.return_value = {'ok': False, 'error': 'codparc obrigatório'}
        response = self.client.post(
            self.url, data=json.dumps({'codveiculo': 5}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_sem_sessao_401(self):
        client = Client()
        response = client.post(
            self.url, data=json.dumps({}),
            content_type='application/json',
        )
        # exige_grupo redireciona, não retorna 401 direto — depende da implementação
        self.assertIn(response.status_code, (302, 401, 403))


# ---------------------------------------------------------------------------
# B13 (Mai/2026 — 2026-05-13) — criar_entrada_combustivel_banco refatorada:
# multi-itens + NUMNOTA do fornecedor + SERIENOTA.
# ---------------------------------------------------------------------------

class CriarEntradaMultiItensServiceTest(TestCase):
    """Exercita criar_entrada com lista de itens (B13)."""

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_2_itens_gera_2_tgfite_1_tgffin_com_soma(
        self, mock_conn, mock_cab, mock_item, mock_rec
    ):
        from sankhya_integration.services.oracle_conn import criar_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # fetchone: 1× TGFPRO p/ cada item (2 itens) + 1× MAX(NUFIN)+1
        cursor.fetchone.side_effect = [
            (200400, 'DIESEL S10', 'LT'),    # item 1
            (200400, 'DIESEL S500', 'LT'),   # item 2
            (438999,),                       # NUFIN
        ]
        mock_cab.return_value = {'ok': True, 'nunota': 99100}
        mock_item.return_value = {'ok': True, 'nunota': 99100, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        resultado = criar_entrada_combustivel_banco({
            'codemp': 1, 'codparc': 579, 'codcencus': 1001,
            'numnota': 12345, 'serienota': '1',
            'itens': [
                {'codprod': 392,  'qtd': 5000, 'vlrunit': 6.26},
                {'codprod': 1373, 'qtd': 500,  'vlrunit': 5.80},
            ],
            'dtneg': '2026-05-13', 'dtvenc': '2026-05-13',
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(resultado['ok'], f"Resultado: {resultado}")
        self.assertEqual(resultado['nunota'], 99100)
        self.assertEqual(resultado['nufin'], 438999)
        self.assertEqual(resultado['qtd_itens'], 2)
        # NUMNOTA agora vem do operador (não MAX+1)
        self.assertEqual(resultado['numnota'], 12345)
        # inserir_item chamado 2 vezes (1 por item)
        self.assertEqual(mock_item.call_count, 2)
        # Valor total esperado: 5000*6.26 + 500*5.80 = 31300 + 2900 = 34200
        self.assertAlmostEqual(resultado['vlrtot'], 34200.0, places=2)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_numnota_obrigatorio(self, mock_conn):
        from sankhya_integration.services.oracle_conn import criar_entrada_combustivel_banco

        resultado = criar_entrada_combustivel_banco({
            'codemp': 1, 'codparc': 579, 'codcencus': 1001,
            'itens': [{'codprod': 392, 'qtd': 100, 'vlrunit': 6.26}],
            # numnota faltando
        }, codusu=1, nomeusu='Teste')

        self.assertFalse(resultado['ok'])
        self.assertIn('numnota', resultado['error'].lower())
        self.assertFalse(mock_conn.called)

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_compat_payload_antigo_codprod_avulso(
        self, mock_conn, mock_cab, mock_item, mock_rec
    ):
        """Payload antigo (codprod/qtd/vlrunit avulsos, sem 'itens') deve continuar
        funcionando — compat retroativa garantida por B13."""
        from sankhya_integration.services.oracle_conn import criar_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (200400, 'DIESEL S10', 'LT'),
            (438999,),
        ]
        mock_cab.return_value = {'ok': True, 'nunota': 99100}
        mock_item.return_value = {'ok': True, 'nunota': 99100, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        resultado = criar_entrada_combustivel_banco({
            'codemp': 1, 'codparc': 579, 'codcencus': 1001,
            'numnota': 12345,
            'codprod': 392, 'qtd': 5000, 'vlrunit': 6.26,  # formato avulso
        }, codusu=1, nomeusu='Teste')

        self.assertTrue(resultado['ok'])
        self.assertEqual(resultado['qtd_itens'], 1)


# ---------------------------------------------------------------------------
# B14 (Mai/2026) — editar_entrada_combustivel_banco
# ---------------------------------------------------------------------------

class EditarEntradaServiceTest(TestCase):

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_feliz_atualiza_cab_itens_fin(self, mock_conn, mock_rec):
        from sankhya_integration.services.oracle_conn import editar_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # fetchone: (1) estado atual + (2) TGFPRO por item
        # fetchall: (1) SEQUENCIAs existentes em TGFITE
        cursor.fetchone.side_effect = [
            ('L', 1, 579, 12345, '1',                          # cab parte 1
             30070200, 1001, 11, date(2026, 5, 13), 'Obs',     # cab parte 2
             438999, date(2026, 5, 13), None, 'Hist antigo',   # fin
             70, 1, 2),                                         # bco/cci/tit
            (200400, 'DIESEL S10', 'LT'),                       # produto novo
        ]
        # SELECT SEQUENCIA FROM TGFITE — devolve 1 seq existente (vai UPDATE)
        cursor.fetchall.return_value = [(1,)]
        mock_rec.return_value = {'ok': True}

        resultado = editar_entrada_combustivel_banco(
            nunota=99100,
            dados={
                'itens': [{'codprod': 392, 'qtd': 6000, 'vlrunit': 6.30}],
                'numnota': 12345,
            },
            codusu=1, nomeusu='Teste',
        )
        self.assertTrue(resultado['ok'], f"Falhou: {resultado}")
        self.assertEqual(resultado['nunota'], 99100)
        # Mai/2026 (2026-05-13): edição usa UPDATE diferencial em vez de DELETE+INSERT.
        # Não deve haver DELETE FROM TGFITE quando lista nova == lista antiga.
        sqls = [str(c.args[0]).upper() for c in cursor.execute.call_args_list]
        self.assertFalse(
            any('DELETE FROM TGFITE' in s for s in sqls),
            "Edit diferencial — UPDATE em vez de DELETE+INSERT quando lista nova == antiga.",
        )
        self.assertTrue(any('UPDATE TGFITE' in s for s in sqls),
                        "Deve haver UPDATE TGFITE.")
        self.assertTrue(any('UPDATE TGFCAB' in s for s in sqls))
        self.assertTrue(any('UPDATE TGFFIN' in s for s in sqls))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_se_tgffin_baixado(self, mock_conn):
        from sankhya_integration.services.oracle_conn import editar_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (
            'L', 1, 579, 12345, '1',
            30070200, 1001, 11, date(2026, 5, 13), 'Obs',
            438999, date(2026, 5, 13), date(2026, 5, 14), 'Hist',
            70, 1, 2,
        )
        resultado = editar_entrada_combustivel_banco(
            nunota=99100, dados={'itens': [{'codprod': 392, 'qtd': 100, 'vlrunit': 6.26}]},
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('baixado', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_entrada_inexistente(self, mock_conn):
        from sankhya_integration.services.oracle_conn import editar_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = None
        resultado = editar_entrada_combustivel_banco(
            nunota=99999, dados={'itens': [{'codprod': 392, 'qtd': 100, 'vlrunit': 6.26}]},
            codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('encontrada', resultado['error'].lower())


# ---------------------------------------------------------------------------
# B15 (Mai/2026) — excluir_entrada_combustivel_banco
# ---------------------------------------------------------------------------

class ExcluirEntradaServiceTest(TestCase):

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_feliz_delete_cascata(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # (STATUSNOTA, NUFIN, DHBAIXA)
        cursor.fetchone.return_value = ('L', 438999, None)

        resultado = excluir_entrada_combustivel_banco(
            nunota=99100, motivo='lançamento errado',
            codusu=1, nomeusu='ANDRE',
        )
        self.assertTrue(resultado['ok'], f"Excluir falhou: {resultado}")
        sqls = [str(c.args[0]).upper() for c in cursor.execute.call_args_list]
        # DELETE TGFFIN, DELETE TGFITE, DELETE TGFCAB
        self.assertTrue(any('DELETE FROM TGFFIN' in s for s in sqls))
        self.assertTrue(any('DELETE FROM TGFITE' in s for s in sqls))
        self.assertTrue(any('DELETE FROM TGFCAB' in s for s in sqls))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_se_tgffin_baixado(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_entrada_combustivel_banco

        conn_ctx, conn, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = ('L', 438999, date(2026, 5, 14))
        resultado = excluir_entrada_combustivel_banco(
            nunota=99100, motivo='vai falhar', codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('baixado', resultado['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_motivo_obrigatorio(self, mock_conn):
        from sankhya_integration.services.oracle_conn import excluir_entrada_combustivel_banco
        resultado = excluir_entrada_combustivel_banco(
            nunota=99100, motivo='', codusu=1, nomeusu='Teste',
        )
        self.assertFalse(resultado['ok'])
        self.assertIn('motivo', resultado['error'].lower())
        self.assertFalse(mock_conn.called)


# ---------------------------------------------------------------------------
# Views Django adicionadas (B14/B15) + consultar_prazo_tipvenda
# ---------------------------------------------------------------------------

class ApiObterEntradaTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_obter_entrada', args=[99100])

    @patch('sankhya_integration.views.obter_entrada_combustivel')
    def test_sucesso_200(self, mock_obt):
        mock_obt.return_value = {
            'cabecalho': {'NUNOTA': 99100, 'NUMNOTA': 12345},
            'itens': [{'CODPROD': 392, 'QTDNEG': 5000.0}],
            'financeiro': {'NUFIN': 438999, 'DTVENC': '2026-05-13'},
        }
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

    @patch('sankhya_integration.views.obter_entrada_combustivel')
    def test_inexistente_404(self, mock_obt):
        mock_obt.return_value = None
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)


class ApiEditarEntradaTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_editar_entrada', args=[99100])

    @patch('sankhya_integration.views.editar_entrada_combustivel_banco')
    def test_sucesso_200(self, mock_edit):
        mock_edit.return_value = {'ok': True, 'nunota': 99100, 'numnota': 12345,
                                  'nufin': 438999, 'qtd_itens': 2}
        response = self.client.post(
            self.url, data=json.dumps({'itens': [{'codprod': 392, 'qtd': 100, 'vlrunit': 6.26}]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    @patch('sankhya_integration.views.editar_entrada_combustivel_banco')
    def test_baixado_400(self, mock_edit):
        mock_edit.return_value = {'ok': False, 'error': 'Financeiro baixado'}
        response = self.client.post(
            self.url, data=json.dumps({'itens': []}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class ApiExcluirEntradaTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_excluir_entrada', args=[99100])

    @patch('sankhya_integration.views.excluir_entrada_combustivel_banco')
    def test_sucesso_200(self, mock_exc):
        mock_exc.return_value = {'ok': True, 'nunota': 99100}
        response = self.client.post(
            self.url, data=json.dumps({'motivo': 'estornar'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_motivo_vazio_400(self):
        response = self.client.post(
            self.url, data=json.dumps({'motivo': ''}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class ApiPrazoTipVendaTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['11'])
        self.url = reverse('api_combustivel_prazo_tipvenda')

    @patch('sankhya_integration.views.consultar_prazo_tipvenda')
    def test_sucesso_200(self, mock_prz):
        mock_prz.return_value = {
            'codtipvenda': 11, 'descrtipvenda': 'A VISTA', 'prazo_dias': 0
        }
        response = self.client.get(self.url, {'codtipvenda': '11'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['prazo_dias'], 0)

    def test_sem_codtipvenda_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.consultar_prazo_tipvenda')
    def test_inexistente_404(self, mock_prz):
        mock_prz.return_value = None
        response = self.client.get(self.url, {'codtipvenda': '999'})
        self.assertEqual(response.status_code, 404)
