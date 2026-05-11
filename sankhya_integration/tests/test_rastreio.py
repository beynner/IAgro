"""
Testes do módulo de Rastreabilidade (Rastreio / WMS).

Todas as chamadas ao Oracle são mockadas via unittest.mock.patch.
Os testes documentam o contrato dos endpoints novos:
    - api_rastreio_view                   → render protegido por grupo
    - api_rastreio_lotes_disponiveis      → GET, lê SANKHYA.ANDRE_IAGRO_SALDO_LOTE
    - api_rastreio_pedidos_abertos        → GET, lista TOP 34 em aberto
    - api_rastreio_atribuir_lote          → POST, atribui CODAGREGACAO ao item
"""
import json
from datetime import date
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

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_toggle_status_default_pendentes(self, mock_fn):
        """Sem query string: backend deve receber Pendente=True, Faturado=False."""
        self.client.get(self.url)
        filtros = mock_fn.call_args[0][0]
        self.assertTrue(filtros.get('mostrar_pendentes'))
        self.assertFalse(filtros.get('mostrar_faturados'))

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_toggle_status_apenas_faturados(self, mock_fn):
        """Operador desliga Pendente e liga Faturado — backend respeita."""
        self.client.get(self.url, {'mostrar_pendentes': '0', 'mostrar_faturados': '1'})
        filtros = mock_fn.call_args[0][0]
        self.assertFalse(filtros.get('mostrar_pendentes'))
        self.assertTrue(filtros.get('mostrar_faturados'))


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


# ---------------------------------------------------------------------------
# Audit log de Rastreio (Fase 1.6) — RastreioAudit grava em SQLite
# ---------------------------------------------------------------------------

class RastreioAuditLogTest(TestCase):
    """Cada atribuição/desvinculação bem-sucedida gera uma linha em RastreioAudit."""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])

    @patch('sankhya_integration.views.atribuir_lote_item_pedido',
           return_value={'ok': True, 'operacao': 'UPDATE',
                         'qtd_atribuida': 5.0, 'nova_sequencia': None})
    def test_atribuir_bem_sucedido_grava_audit(self, _mock):
        from sankhya_integration.models import RastreioAudit
        n0 = RastreioAudit.objects.filter(acao='ATRIBUIR').count()
        url = reverse('api_rastreio_atribuir_lote')
        response = self.client.post(
            url,
            data=json.dumps({'nunota': 100, 'sequencia': 1, 'codagregacao': 'L1', 'qtd': 5}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        registros = RastreioAudit.objects.filter(acao='ATRIBUIR')
        self.assertEqual(registros.count(), n0 + 1)
        ultimo = registros.order_by('-created_at').first()
        self.assertEqual(ultimo.nunota, 100)
        self.assertEqual(ultimo.sequencia, 1)
        self.assertEqual(ultimo.codagregacao, 'L1')
        self.assertEqual(ultimo.codusu, 1)

    @patch('sankhya_integration.views.atribuir_lote_item_pedido',
           return_value={'ok': False, 'error': 'Saldo insuficiente'})
    def test_atribuir_falha_NAO_grava_audit(self, _mock):
        """Audit só registra operações que efetivamente modificaram o banco."""
        from sankhya_integration.models import RastreioAudit
        n0 = RastreioAudit.objects.filter(acao='ATRIBUIR').count()
        url = reverse('api_rastreio_atribuir_lote')
        response = self.client.post(
            url,
            data=json.dumps({'nunota': 100, 'sequencia': 1, 'codagregacao': 'L1'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(RastreioAudit.objects.filter(acao='ATRIBUIR').count(), n0)

    @patch('sankhya_integration.views.desvincular_lote_item_pedido',
           return_value={'ok': True, 'operacao': 'CLEAR',
                         'codagregacao_removido': 'L9'})
    def test_desvincular_bem_sucedido_grava_audit(self, _mock):
        from sankhya_integration.models import RastreioAudit
        n0 = RastreioAudit.objects.filter(acao='DESVINCULAR').count()
        url = reverse('api_rastreio_desvincular_lote')
        response = self.client.post(
            url,
            data=json.dumps({'nunota': 200, 'sequencia': 7}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        registros = RastreioAudit.objects.filter(acao='DESVINCULAR')
        self.assertEqual(registros.count(), n0 + 1)
        ultimo = registros.order_by('-created_at').first()
        self.assertEqual(ultimo.nunota, 200)
        self.assertEqual(ultimo.sequencia, 7)
        self.assertEqual(ultimo.codagregacao, 'L9')


# ---------------------------------------------------------------------------
# Erros Oracle humanizados (Fase 1.1) — não vazam ORA-XXXXX para o usuário
# ---------------------------------------------------------------------------

class HumanizarErroOracleTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])

    @patch('sankhya_integration.views.atribuir_lote_item_pedido',
           side_effect=Exception('ORA-00054 resource busy'))
    def test_excecao_ora_00054_humanizada(self, _mock):
        url = reverse('api_rastreio_atribuir_lote')
        response = self.client.post(
            url,
            data=json.dumps({'nunota': 1, 'sequencia': 1, 'codagregacao': 'L1'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.content)
        self.assertNotIn('ORA-00054', body['error'])
        # Mensagem operacional refinada (Mai/2026): aponta colega operador
        # e sugere ação de espera. Validamos pelos termos-chave que devem
        # estar presentes — não pela frase exata, pra suportar futuras
        # melhorias de microcopy sem quebrar teste.
        self.assertIn('operador', body['error'].lower())
        self.assertIn('aguarde', body['error'].lower())

    @patch('sankhya_integration.views.consultar_saldo_lote_disponivel',
           side_effect=Exception('ORA-12899 value too large'))
    def test_excecao_em_lotes_disponiveis_humanizada(self, _mock):
        response = self.client.get(reverse('api_rastreio_lotes_disponiveis'))
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.content)
        self.assertNotIn('ORA-12899', body['error'])


# ---------------------------------------------------------------------------
# Service atribuir_lote_item_pedido — Fase 1.2 (lock pessimista FOR UPDATE)
# ---------------------------------------------------------------------------

class AtribuirLoteServiceTest(TestCase):
    """Cobre o service direto (sem passar por view): valida que o SELECT FOR
    UPDATE foi emitido antes da escrita e que os erros de validação acontecem
    na ordem certa (lock → existência → top → status → saldo)."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        """Helper: encapsula o context manager do Oracle com um cursor mockado."""
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_escrita_desabilitada_retorna_erro(self, _mp):
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='L1')
        self.assertFalse(res['ok'])
        self.assertIn('desabilitada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_emite_select_for_update_no_item(self, _mp, mock_obter):
        """O primeiro execute do service deve usar SELECT ... FOR UPDATE."""
        cursor = MagicMock()
        # 1ª chamada (FOR UPDATE no item) retorna None → item não encontrado
        cursor.fetchone.side_effect = [None]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=99, sequencia=1, codagregacao='L1')
        self.assertFalse(res['ok'])
        self.assertIn('não encontrado', res['error'])
        # Verifica que o primeiro SQL contém "FOR UPDATE"
        primeira_sql = cursor.execute.call_args_list[0][0][0]
        self.assertIn('FOR UPDATE', primeira_sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_item_ja_tem_lote_diferente_recusa(self, _mp, mock_obter):
        """Defesa contra double-binding — Fase 1.2."""
        cursor = MagicMock()
        # 1ª: lock retorna (CODAGREGACAO_ATUAL, QTDNEG, CODPROD)
        # 2ª: cabeçalho retorna (CODTIPOPER, STATUSNOTA)
        cursor.fetchone.side_effect = [
            ('LOTE_EXISTENTE', 10.0, 100),
            (34, '0'),
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='LOTE_NOVO')
        self.assertFalse(res['ok'])
        self.assertIn('Desvincule antes', res['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_pedido_faturado_aceita(self, _mp, mock_obter):
        """Mai/2026: TOP 34 STATUSNOTA='L' (pedido já faturado) é aceito.
        Rastreabilidade vive no pedido mesmo após faturamento. O guard agora
        só bloqueia STATUSNOTA='E' (excluído)."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),    # item sem lote ainda
            (34, 'L'),            # pedido faturado — aceito agora
            (50.0,),              # saldo do lote: suficiente
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='L1')
        self.assertTrue(res['ok'])
        self.assertEqual(res['operacao'], 'UPDATE')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_pedido_excluido_recusa(self, _mp, mock_obter):
        """STATUSNOTA='E' (pedido excluído) continua bloqueado."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),
            (34, 'E'),
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='L1')
        self.assertFalse(res['ok'])
        self.assertIn('excluído', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_nota_orfa_top35_aceita(self, _mp, mock_obter):
        """TOP 35 STATUSNOTA='L' SEM TGFVAR par (nota órfã) é aceita.
        Operador vincula lote direto no TGFITE da nota (caso 111976)."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),    # FOR UPDATE: sem lote, qtd 10, codprod 100
            (35, 'L'),            # TOP 35 STATUSNOTA='L'
            (0,),                 # COUNT(*) TGFVAR — zero = órfã
            (50.0,),              # saldo do lote
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=111976, sequencia=1, codagregacao='L1')
        self.assertTrue(res['ok'])
        self.assertEqual(res['operacao'], 'UPDATE')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_top35_com_tgfvar_par_recusa(self, _mp, mock_obter):
        """TOP 35 com TGFVAR par bloqueia — operador deve trabalhar pelo pedido."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),
            (35, 'L'),
            (15,),    # COUNT(*) TGFVAR > 0 — tem pedido pareado
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=111983, sequencia=1, codagregacao='L1')
        self.assertFalse(res['ok'])
        self.assertIn('tgfvar', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_top35_sem_status_L_recusa(self, _mp, mock_obter):
        """TOP 35 com STATUSNOTA != 'L' (rascunho/cancelada) bloqueia."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),
            (35, ' '),    # STATUSNOTA em branco — não está liberada
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='L1')
        self.assertFalse(res['ok'])
        self.assertIn('liberada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_top_nao_suportada_recusa(self, _mp, mock_obter):
        """TOP fora de 34/35/37 (ex: 30 avaria) é rejeitada."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),
            (30, 'L'),    # TOP 30
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='L1')
        self.assertFalse(res['ok'])
        self.assertIn('não suportada', res['error'].lower())


# ---------------------------------------------------------------------------
# Service vínculo manual pedido↔nota — Leva A (Mai/2026)
# ---------------------------------------------------------------------------

class VinculoManualPedidoNotaServiceTest(TestCase):
    """Cobertura das 3 funções de vínculo manual (AD_VINCULO_PEDIDO_NOTA).
    Mocks isolam totalmente Oracle — testa apenas a lógica de fluxo."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_inserir_escrita_desabilitada(self, _mp):
        from sankhya_integration.services.oracle_conn import inserir_vinculo_manual_pedido_nota
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=1, nunota_nota=2, codusu=999,
        )
        self.assertFalse(res['ok'])
        self.assertIn('desabilitada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_inserir_pedido_top_errada(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (35, 'L'),    # pedido informado é na verdade TOP 35
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import inserir_vinculo_manual_pedido_nota
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=111976, nunota_nota=111975, codusu=1,
        )
        self.assertFalse(res['ok'])
        self.assertIn('top 34', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_inserir_pedido_ja_tem_tgfvar(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, 'L'),    # pedido válido
            (1,),         # COUNT TGFVAR > 0 — já tem nota pareada
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import inserir_vinculo_manual_pedido_nota
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=111829, nunota_nota=111983, codusu=1,
        )
        self.assertFalse(res['ok'])
        self.assertIn('tgfvar', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_inserir_nota_top_errada(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, 'L'),    # pedido OK
            (0,),         # sem TGFVAR
            (0,),         # sem vínculo manual
            (34, 'L'),    # nota informada é na verdade TOP 34
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import inserir_vinculo_manual_pedido_nota
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=111975, nunota_nota=111974, codusu=1,
        )
        self.assertFalse(res['ok'])
        self.assertIn('top 35/37', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_inserir_sucesso(self, _mp, mock_obter):
        """Fluxo feliz: pedido TOP 34 STATUS=L sem TGFVAR sem vínculo +
        nota TOP 35 STATUS=L sem TGFVAR sem vínculo → INSERT OK, id=42."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, 'L'),    # pedido OK
            (0,),         # sem TGFVAR par pra pedido
            (0,),         # sem vínculo manual pra pedido
            (35, 'L'),    # nota OK
            (0,),         # sem TGFVAR pra nota
            (0,),         # sem vínculo manual pra nota
            (42,),        # NEXTVAL da sequence
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import inserir_vinculo_manual_pedido_nota
        res = inserir_vinculo_manual_pedido_nota(
            nunota_pedido=111975, nunota_nota=111976, codusu=7, nomeusu='OP1',
        )
        self.assertTrue(res['ok'])
        self.assertEqual(res['id'], 42)

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_remover_sem_parametros_recusa(self, _mp):
        from sankhya_integration.services.oracle_conn import remover_vinculo_manual_pedido_nota
        res = remover_vinculo_manual_pedido_nota()
        self.assertFalse(res['ok'])
        self.assertIn('informe', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_remover_vinculo_inexistente(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [None]   # SELECT do vínculo: não achou
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import remover_vinculo_manual_pedido_nota
        res = remover_vinculo_manual_pedido_nota(nunota_pedido=999)
        self.assertFalse(res['ok'])
        self.assertIn('não encontrado', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_remover_sucesso_vinculado(self, _mp, mock_obter):
        """ORIGEM='VINCULADO' (Leva A) — só remove a linha, pedido fica intacto."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (1, 111975, 111976, 'VINCULADO'),   # SELECT do vínculo
        ]
        cursor.rowcount = 1
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import remover_vinculo_manual_pedido_nota
        res = remover_vinculo_manual_pedido_nota(nunota_nota=111976)
        self.assertTrue(res['ok'])
        self.assertEqual(res['origem'], 'VINCULADO')
        self.assertFalse(res['pedido_excluido'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_remover_sucesso_retroativo(self, _mp, mock_obter):
        """ORIGEM='PEDIDO_RETROATIVO' (Leva B) — exclui pedido + linha."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (2, 222001, 111825, 'PEDIDO_RETROATIVO'),   # SELECT do vínculo
            (0,),                                        # COUNT itens com CODAGREGACAO
        ]
        cursor.rowcount = 1
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import remover_vinculo_manual_pedido_nota
        res = remover_vinculo_manual_pedido_nota(nunota_nota=111825)
        self.assertTrue(res['ok'])
        self.assertEqual(res['origem'], 'PEDIDO_RETROATIVO')
        self.assertTrue(res['pedido_excluido'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_remover_retroativo_bloqueia_com_lote_atribuido(self, _mp, mock_obter):
        """Pedido retroativo com lote atribuído não pode ser desfeito."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (3, 222002, 111900, 'PEDIDO_RETROATIVO'),   # SELECT do vínculo
            (1,),                                        # 1 item com CODAGREGACAO
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import remover_vinculo_manual_pedido_nota
        res = remover_vinculo_manual_pedido_nota(nunota_nota=111900)
        self.assertFalse(res['ok'])
        self.assertIn('desvincule todos os lotes', res['error'].lower())

    # ----- Leva B — criar_pedido_retroativo_a_partir_de_nota -----

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_criar_retroativo_escrita_desabilitada(self, _mp):
        from sankhya_integration.services.oracle_conn import criar_pedido_retroativo_a_partir_de_nota
        res = criar_pedido_retroativo_a_partir_de_nota(nunota_nota=1, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('desabilitada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_criar_retroativo_nota_inexistente(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [None]   # nota não encontrada
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import criar_pedido_retroativo_a_partir_de_nota
        res = criar_pedido_retroativo_a_partir_de_nota(nunota_nota=999, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('não encontrada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_criar_retroativo_top_errada(self, _mp, mock_obter):
        cursor = MagicMock()
        # Cabeçalho informado é TOP 34, não TOP 35/37
        from datetime import date as _d
        cursor.fetchone.side_effect = [
            (34, 'L', 10, 244, _d(2026, 5, 9), None),
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import criar_pedido_retroativo_a_partir_de_nota
        res = criar_pedido_retroativo_a_partir_de_nota(nunota_nota=111975, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('top 35/37', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_criar_retroativo_nota_com_tgfvar_recusa(self, _mp, mock_obter):
        from datetime import date as _d
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (35, 'L', 10, 244, _d(2026, 5, 9), None),
            (1,),    # TGFVAR > 0 — tem vínculo
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import criar_pedido_retroativo_a_partir_de_nota
        res = criar_pedido_retroativo_a_partir_de_nota(nunota_nota=111976, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('tgfvar', res['error'].lower())

    # ----- Resolver unificado (Mai/2026) -----

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_resolver_escrita_desabilitada(self, _mp):
        from sankhya_integration.services.oracle_conn import resolver_nota_orfa_automatica
        res = resolver_nota_orfa_automatica(nunota_nota=1, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('desabilitada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_resolver_nota_inexistente(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [None]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import resolver_nota_orfa_automatica
        res = resolver_nota_orfa_automatica(nunota_nota=999, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('não encontrada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_resolver_acao_invalida(self, _mp, mock_obter):
        from datetime import date as _d
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (35, 'L', 10, 244, _d(2026, 5, 9), 4200.0),  # nota OK
            None,                                          # sem candidato exato
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import resolver_nota_orfa_automatica
        res = resolver_nota_orfa_automatica(
            nunota_nota=111976, codusu=1, acao='XXX',
        )
        self.assertFalse(res['ok'])
        self.assertIn('ação inválida', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_resolver_forca_vincular_sem_candidato_recusa(self, _mp, mock_obter):
        """acao='VINCULAR' sem candidato exato é recusado (sugere CRIAR)."""
        from datetime import date as _d
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (35, 'L', 10, 244, _d(2026, 5, 9), 510.0),
            None,   # sem candidato
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import resolver_nota_orfa_automatica
        res = resolver_nota_orfa_automatica(
            nunota_nota=111825, codusu=1, acao='VINCULAR',
        )
        self.assertFalse(res['ok'])
        self.assertIn('sem candidato', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_criar_retroativo_nota_sem_itens(self, _mp, mock_obter):
        from datetime import date as _d
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (35, 'L', 10, 244, _d(2026, 5, 9), None),
            (0,),    # sem TGFVAR
            (0,),    # sem vínculo manual
        ]
        cursor.fetchall.return_value = []  # SELECT itens — vazio
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import criar_pedido_retroativo_a_partir_de_nota
        res = criar_pedido_retroativo_a_partir_de_nota(nunota_nota=111825, codusu=1)
        self.assertFalse(res['ok'])
        self.assertIn('não tem itens', res['error'].lower())


# ---------------------------------------------------------------------------
# Service faturar_pedido_venda_banco — Fase 4 (Faturar pedido)
# ---------------------------------------------------------------------------

class FaturarPedidoServiceTest(TestCase):

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_escrita_desabilitada(self, _mp):
        from sankhya_integration.services.oracle_conn import faturar_pedido_venda_banco
        res = faturar_pedido_venda_banco(nunota=1, nova_top=35)
        self.assertFalse(res['ok'])

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_top_invalida_recusa(self, _mp):
        from sankhya_integration.services.oracle_conn import faturar_pedido_venda_banco
        res = faturar_pedido_venda_banco(nunota=1, nova_top=99)
        self.assertFalse(res['ok'])
        self.assertIn('inválido', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_pedido_top_diferente_de_34_recusa(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.return_value = (35, 'L', 10, 1500.0)   # já faturado
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import faturar_pedido_venda_banco
        res = faturar_pedido_venda_banco(nunota=1, nova_top=35)
        self.assertFalse(res['ok'])
        self.assertIn('outra operação', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_pedido_sem_itens_recusa(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, '0', 10, 0.0),    # FOR UPDATE — TOP 34, status livre
            (0, None),             # contagem de itens = 0
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import faturar_pedido_venda_banco
        res = faturar_pedido_venda_banco(nunota=1, nova_top=35)
        self.assertFalse(res['ok'])
        self.assertIn('sem itens', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_pedido_com_item_sem_lote_recusa(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, '0', 10, 1500.0),
            (5, 2),    # 5 itens, 2 sem lote
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import faturar_pedido_venda_banco
        res = faturar_pedido_venda_banco(nunota=1, nova_top=35)
        self.assertFalse(res['ok'])
        self.assertIn('sem lote', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela',
           return_value={'CODTIPOPER', 'CODNAT', 'STATUSNOTA', 'NUMNOTA', 'DTFATUR'})
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_faturamento_completo_top_35_aplica_codnat_correto(
        self, _mp, mock_obter, _mock_cols
    ):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, '0', 10, 1500.0),   # FOR UPDATE: TOP=34, livre, codemp=10, vlrnota=1500
            (5, 0),                  # 5 itens, todos com lote
            (42,),                   # próximo NUMNOTA
        ]
        conn = self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import faturar_pedido_venda_banco
        res = faturar_pedido_venda_banco(nunota=100, nova_top=35, codusu_logado=99)
        self.assertTrue(res['ok'])
        self.assertEqual(res['top'], 35)
        self.assertEqual(res['numnota'], 42)
        self.assertEqual(res['codnat'], 10010100)
        self.assertEqual(res['vlrnota'], 1500.0)
        # Commit chamado dentro do try interno (atomicidade)
        conn.commit.assert_called_once()

    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela',
           return_value={'CODTIPOPER', 'CODNAT', 'STATUSNOTA', 'NUMNOTA'})
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_faturamento_top_37_usa_codnat_diferente(
        self, _mp, mock_obter, _mock_cols
    ):
        from sankhya_integration.services.oracle_conn import (
            faturar_pedido_venda_banco, CODNAT_POR_TOP,
        )
        # CODNAT da TOP 37 = 10010200 (Venda sem NFe)
        self.assertEqual(CODNAT_POR_TOP[37], 10010200)
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, '0', 10, 1500.0),
            (3, 0),
            (10,),
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        res = faturar_pedido_venda_banco(nunota=100, nova_top=37)
        self.assertTrue(res['ok'])
        self.assertEqual(res['codnat'], 10010200)


# ---------------------------------------------------------------------------
# Helper humanizar_erro_oracle — Fase 1.1 (mapeamento ORA → mensagem amigável)
# ---------------------------------------------------------------------------

class HumanizarErroOracleHelperTest(TestCase):

    def test_ora_20101_mapeado(self):
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        self.assertIn('Tipo de negociação', humanizar_erro_oracle('ORA-20101: ...'))

    def test_ora_00001_mapeado(self):
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        self.assertIn('chave duplicada', humanizar_erro_oracle('ORA-00001 unique constraint').lower())

    def test_dpy_1001_mapeado(self):
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        self.assertIn('Conexão', humanizar_erro_oracle('DPY-1001: not connected'))

    def test_mensagem_desconhecida_devolve_primeira_linha(self):
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        msg = 'Erro qualquer\nLinha 2 do stack'
        self.assertEqual(humanizar_erro_oracle(msg), 'Erro qualquer')

    def test_string_vazia_devolve_padrao(self):
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        self.assertEqual(humanizar_erro_oracle(''), 'Falha desconhecida.')

    def test_excecao_aceita_diretamente(self):
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        try:
            raise RuntimeError('ORA-02292 child record found')
        except Exception as e:
            humanizada = humanizar_erro_oracle(e)
        self.assertIn('dependências', humanizada)
