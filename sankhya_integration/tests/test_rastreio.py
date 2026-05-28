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

    def test_comercial_NAO_acessa_pagina(self):
        # 2026-05-14 — Comercial (CODGRUPO=9) perdeu acesso ao Rastreio. Eles
        # acompanham rastreio pelo módulo Relatórios (não pode alterar lotes).
        _login_session(self.client, grupos=['9'])
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

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
        """Sem query string: backend deve receber Pendente=True, Finalizado=False
        (Mai/2026 — B9 renomeou de Faturado→Finalizado)."""
        self.client.get(self.url)
        filtros = mock_fn.call_args[0][0]
        self.assertTrue(filtros.get('mostrar_pendentes'))
        self.assertFalse(filtros.get('mostrar_finalizados'))

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_toggle_status_apenas_finalizados(self, mock_fn):
        """Operador desliga Pendente e liga Finalizado — backend respeita."""
        self.client.get(self.url, {'mostrar_pendentes': '0', 'mostrar_finalizados': '1'})
        filtros = mock_fn.call_args[0][0]
        self.assertFalse(filtros.get('mostrar_pendentes'))
        self.assertTrue(filtros.get('mostrar_finalizados'))

    @patch('sankhya_integration.views.consultar_pedidos_abertos_para_atribuicao',
           return_value=[])
    def test_alias_retro_mostrar_faturados(self, mock_fn):
        """Retrocompat (Mai/2026 — B9): URL param `mostrar_faturados` ainda
        aceito como alias de `mostrar_finalizados`. Front antigo continua ok."""
        self.client.get(self.url, {'mostrar_pendentes': '0', 'mostrar_faturados': '1'})
        filtros = mock_fn.call_args[0][0]
        self.assertTrue(filtros.get('mostrar_finalizados'),
                        "mostrar_faturados=1 deve mapear pra mostrar_finalizados=True")


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
# Service consultar_saldo_lote_disponivel — filtro cliente_q (Mai/2026 — 2026-05-25)
# ---------------------------------------------------------------------------

class ConsultarSaldoLoteClienteQTest(TestCase):
    """Garante que o EXISTS do filtro cliente_q referencia a tabela do FROM
    principal (AD_SALDO_LOTE_CACHE) — antes apontava pra view legada
    ANDRE_IAGRO_SALDO_LOTE pós-refator de 2026-05-19, e quebrava com ORA-00904.
    """

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_cliente_q_correlaciona_com_ad_saldo_lote_cache(self, mock_obter):
        cursor = MagicMock()
        # SELECT principal devolve lista vazia — não interessa o resultado,
        # interessa o SQL que foi enviado pro Oracle.
        cursor.fetchall.return_value = []
        cursor.description = [
            ('CODEMP',), ('CODPROD',), ('DESCRPROD',), ('FABRICANTE',),
            ('SELECIONADO',), ('CODAGREGACAO',), ('STATUS_LINHA',),
            ('QTD_ENTRADA',), ('QTD_BAIXADA_VENDA',), ('QTD_BAIXADA_AVARIA',),
            ('QTD_RESERVADA',), ('QTD_DISPONIVEL',), ('QTD_PENDENTE',),
            ('QTD_AVARIA_INTERNA',), ('VENDAVEL',), ('NUNOTA_ORIGEM',),
            ('DTNEG_ORIGEM',), ('CODPARC_ORIGEM',), ('NOMEPARC_ORIGEM',), ('RN',),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import (
            consultar_saldo_lote_disponivel,
            invalidar_cache_rastreio,
        )
        invalidar_cache_rastreio()
        consultar_saldo_lote_disponivel({'cliente_q': 'ASSAI'}, limite=10, offset=0)

        # SQL emitido tem que apontar pro FROM correto E o EXISTS tem que
        # correlacionar com a MESMA tabela do FROM (sem isso, ORA-00904).
        sqls = [c[0][0] for c in cursor.execute.call_args_list if c[0]]
        sql_principal = next(
            (s for s in sqls if 'AD_SALDO_LOTE_CACHE' in s and 'EXISTS' in s),
            None,
        )
        self.assertIsNotNone(sql_principal,
                             msg='SELECT principal com EXISTS não foi emitido')
        self.assertIn('AD_SALDO_LOTE_CACHE.CODPROD', sql_principal,
                      msg='EXISTS deve correlacionar com AD_SALDO_LOTE_CACHE')
        self.assertNotIn('ANDRE_IAGRO_SALDO_LOTE.CODPROD', sql_principal,
                         msg='nome legado da view não pode aparecer no EXISTS '
                             '(quebraria com ORA-00904)')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_cliente_q_digito_busca_por_NUNOTA_e_NUMNOTA(self, mock_obter):
        """Mai/2026 — 2026-05-25: cliente_q numérico filtra por NUNOTA (interno)
        OU NUMNOTA (fiscal), permitindo operador localizar lotes pelo número
        da nota fiscal além do nº do pedido interno."""
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.description = [
            ('CODEMP',), ('CODPROD',), ('DESCRPROD',), ('FABRICANTE',),
            ('SELECIONADO',), ('CODAGREGACAO',), ('STATUS_LINHA',),
            ('QTD_ENTRADA',), ('QTD_BAIXADA_VENDA',), ('QTD_BAIXADA_AVARIA',),
            ('QTD_RESERVADA',), ('QTD_DISPONIVEL',), ('QTD_PENDENTE',),
            ('QTD_AVARIA_INTERNA',), ('VENDAVEL',), ('NUNOTA_ORIGEM',),
            ('DTNEG_ORIGEM',), ('CODPARC_ORIGEM',), ('NOMEPARC_ORIGEM',), ('RN',),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import (
            consultar_saldo_lote_disponivel,
            invalidar_cache_rastreio,
        )
        invalidar_cache_rastreio()
        consultar_saldo_lote_disponivel(
            {'cliente_q': '113155'}, limite=10, offset=0,
        )

        sqls = [c[0][0] for c in cursor.execute.call_args_list if c[0]]
        sql_principal = next(
            (s for s in sqls if 'AD_SALDO_LOTE_CACHE' in s and 'EXISTS' in s),
            None,
        )
        self.assertIsNotNone(sql_principal,
                             msg='SELECT principal com EXISTS não foi emitido')
        # SQL deve filtrar por NUNOTA OU NUMNOTA
        self.assertIn('c_cli.NUNOTA = :cliente_num', sql_principal)
        self.assertIn('c_cli.NUMNOTA = :cliente_num', sql_principal)
        # Não deve cair no caminho de NOMEPARC quando termo é número.
        # Checamos `p_cli.NOMEPARC` (alias do JOIN TGFPAR no ramo de texto)
        # — o campo NOMEPARC_ORIGEM da lista de colunas projetadas aparece
        # naturalmente no SELECT em ambos os ramos.
        self.assertNotIn('p_cli.NOMEPARC', sql_principal)
        self.assertNotIn('TGFPAR', sql_principal)


# ---------------------------------------------------------------------------
# Service consultar_pedidos_abertos_para_atribuicao — busca por NUNOTA OR NUMNOTA
# ---------------------------------------------------------------------------

class ConsultarPedidosAbertosBuscaTest(TestCase):
    """Garante que termo numérico no campo Pedidos casa por NUNOTA OU NUMNOTA
    (operador pode digitar nº do pedido interno OU nº da nota fiscal)."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_q_digito_busca_NUNOTA_e_NUMNOTA(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        # description com 13 colunas (matches o SELECT real do service)
        cursor.description = [
            ('NUNOTA',), ('CODPARC',), ('NOMEPARC',), ('DTNEG',),
            ('QTDVOL',), ('VLRNOTA',), ('CODTIPOPER',), ('STATUSNOTA',),
            ('NOTA_NUMNOTA',), ('NOTA_NUNOTA',), ('VINCULO_ORIGEM',),
            ('NUMNOTA_PROPRIO',), ('RN',),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import (
            consultar_pedidos_abertos_para_atribuicao,
            invalidar_cache_rastreio,
        )
        invalidar_cache_rastreio()
        consultar_pedidos_abertos_para_atribuicao(
            {'q': '113155'}, limite=10, offset=0,
        )

        sqls = [c[0][0] for c in cursor.execute.call_args_list if c[0]]
        sql_principal = next((s for s in sqls if 'TGFCAB' in s), None)
        self.assertIsNotNone(sql_principal)
        # Mai/2026 — 2026-05-25: WHERE com NUNOTA OR NUMNOTA
        self.assertIn('c.NUNOTA = :q_num', sql_principal)
        self.assertIn('c.NUMNOTA = :q_num', sql_principal)


# ---------------------------------------------------------------------------
# Service q_lotes — campo único do Rastreio (Mai/2026 — 2026-05-25)
# ---------------------------------------------------------------------------

class QLotesUnificadoTest(TestCase):
    """Valida o campo único do Rastreio: termo bate em CODAGREGACAO, DESCRPROD,
    NOMEPARC_ORIGEM (fornecedor) e NUNOTA_ORIGEM (nº pedido de compra). Cross-
    filter espelha pros Pedidos via EXISTS contra AD_SALDO_LOTE_CACHE."""

    def _mock_cursor_lotes(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.description = [
            ('CODEMP',), ('CODPROD',), ('DESCRPROD',), ('FABRICANTE',),
            ('SELECIONADO',), ('CODAGREGACAO',), ('STATUS_LINHA',),
            ('QTD_ENTRADA',), ('QTD_BAIXADA_VENDA',), ('QTD_BAIXADA_AVARIA',),
            ('QTD_RESERVADA',), ('QTD_DISPONIVEL',), ('QTD_PENDENTE',),
            ('QTD_AVARIA_INTERNA',), ('VENDAVEL',), ('NUNOTA_ORIGEM',),
            ('DTNEG_ORIGEM',), ('CODPARC_ORIGEM',), ('NOMEPARC_ORIGEM',), ('RN',),
        ]
        return cursor

    def _mock_cursor_pedidos(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.description = [
            ('NUNOTA',), ('CODPARC',), ('NOMEPARC',), ('DTNEG',),
            ('QTDVOL',), ('VLRNOTA',), ('CODTIPOPER',), ('STATUSNOTA',),
            ('NOTA_NUMNOTA',), ('NOTA_NUNOTA',), ('VINCULO_ORIGEM',),
            ('NUMNOTA_PROPRIO',), ('RN',),
        ]
        return cursor

    def _setup_conn(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_q_lotes_texto_busca_4_campos_no_lotes(self, mock_obter):
        """Termo texto bate nos 3 campos LIKE (CODAGREGACAO/DESCRPROD/
        NOMEPARC_ORIGEM); NUNOTA_ORIGEM só é incluído quando termo é dígito."""
        cursor = self._mock_cursor_lotes()
        self._setup_conn(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import (
            consultar_saldo_lote_disponivel,
            invalidar_cache_rastreio,
        )
        invalidar_cache_rastreio()
        consultar_saldo_lote_disponivel(
            {'q_lotes': 'DEBORA'}, limite=10, offset=0,
        )

        sqls = [c[0][0] for c in cursor.execute.call_args_list if c[0]]
        sql = next((s for s in sqls if 'AD_SALDO_LOTE_CACHE' in s), None)
        self.assertIsNotNone(sql)
        self.assertIn('UPPER(CODAGREGACAO)', sql)
        self.assertIn('UPPER(DESCRPROD)', sql)
        self.assertIn('UPPER(NOMEPARC_ORIGEM)', sql)
        # texto puro não usa o bind numérico — só LIKE
        self.assertNotIn(':q_lotes_num', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_q_lotes_digito_inclui_NUNOTA_ORIGEM(self, mock_obter):
        cursor = self._mock_cursor_lotes()
        self._setup_conn(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import (
            consultar_saldo_lote_disponivel,
            invalidar_cache_rastreio,
        )
        invalidar_cache_rastreio()
        consultar_saldo_lote_disponivel(
            {'q_lotes': '111752'}, limite=10, offset=0,
        )

        sqls = [c[0][0] for c in cursor.execute.call_args_list if c[0]]
        sql = next((s for s in sqls if 'AD_SALDO_LOTE_CACHE' in s), None)
        self.assertIsNotNone(sql)
        # Termo numérico expande pros 4 campos
        self.assertIn('UPPER(CODAGREGACAO)', sql)
        self.assertIn('UPPER(DESCRPROD)', sql)
        self.assertIn('UPPER(NOMEPARC_ORIGEM)', sql)
        self.assertIn('NUNOTA_ORIGEM = :q_lotes_num', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_q_lotes_cross_filter_em_pedidos(self, mock_obter):
        """Pedidos respeita o termo do campo Lotes via pré-resolve em
        AD_SALDO_LOTE_CACHE (DISTINCT CODPROD) + IN literal — mesma janela
        de campos. Otimização: sem subquery aninhada (era 30s, agora ~250ms)."""
        cursor = self._mock_cursor_pedidos()
        # Pré-resolve roda 1 SELECT DISTINCT CODPROD primeiro — devolve lista
        # mockada de CODPRODs pra forçar entrada no caminho IN literal.
        cursor.fetchall.side_effect = [
            [(100,), (200,)],   # pré-resolve devolve 2 CODPRODs
            [],                  # query principal de pedidos
        ]
        self._setup_conn(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import (
            consultar_pedidos_abertos_para_atribuicao,
            invalidar_cache_rastreio,
        )
        invalidar_cache_rastreio()
        consultar_pedidos_abertos_para_atribuicao(
            {'q_lotes': 'DEBORA'}, limite=10, offset=0,
        )

        sqls = [c[0][0] for c in cursor.execute.call_args_list if c[0]]
        # Primeira query: pré-resolve dos CODPRODs no cache
        sql_pre = next(
            (s for s in sqls if 'SELECT DISTINCT CODPROD FROM SANKHYA.AD_SALDO_LOTE_CACHE' in s),
            None,
        )
        self.assertIsNotNone(sql_pre,
                             msg='Pré-resolve deve rodar antes da query principal')
        self.assertIn('UPPER(CODAGREGACAO)', sql_pre)
        self.assertIn('UPPER(DESCRPROD)',    sql_pre)
        self.assertIn('UPPER(NOMEPARC_ORIGEM)', sql_pre)
        # Segunda query: principal com IN literal (sem subquery aninhada no
        # filtro). NOTA: query principal de pedidos JÁ tem LEFT JOIN com
        # AD_SALDO_LOTE_CACHE pra trazer dados de origem do lote (LOTE_NUNOTA,
        # DTNEG_ORIGEM etc) — esse JOIN é pré-existente e não relacionado ao
        # filtro q_lotes. O que validamos aqui é que o EXISTS do filtro usa
        # IN literal (não subquery contra AD_SALDO_LOTE_CACHE).
        sql_main = next((s for s in sqls if 'TGFCAB' in s and 'i_ql.CODPROD' in s), None)
        self.assertIsNotNone(sql_main, msg='Query principal com filtro i_ql não encontrada')
        self.assertIn('i_ql.CODPROD IN (:cp_ql_0, :cp_ql_1)', sql_main)
        # Garante que o EXISTS de q_lotes não virou subquery aninhada
        self.assertNotIn('SELECT sl.CODPROD FROM SANKHYA.AD_SALDO_LOTE_CACHE', sql_main)


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

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.invalidar_cache_rastreio')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_split_insert_inclui_reserva_atualestoque_usoprod(
            self, _mp, mock_obter, _mi, _mr):
        """Mai/2026 — 2026-05-25: SPLIT deve gravar RESERVA='S', ATUALESTOQUE=1,
        USOPROD do TGFPRO na linha NOVA. Sem isso, Sankhya corta o item na
        emissão da NFe (TRG_UPT_TGFITE rejeita silenciosamente — mesma raiz do
        fix em inserir_item_nota_banco)."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),    # FOR UPDATE: sem lote, QTDNEG=10, CODPROD=100
            (34, ' '),            # cabeçalho: TOP 34 em aberto
            (50.0,),              # saldo do lote: suficiente
            (5,),                 # MAX(SEQUENCIA)+1 = 5 (nova seq)
        ]
        self._mock_conn_ctx(mock_obter, cursor)
        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        # qtd=4 < QTDNEG=10 → força caminho SPLIT
        res = atribuir_lote_item_pedido(
            nunota=1, sequencia=1, codagregacao='L1', qtd=4.0,
        )
        self.assertTrue(res['ok'], msg=res.get('error'))
        self.assertEqual(res['operacao'], 'SPLIT')
        # Procura o INSERT no histórico de chamadas. Última escrita do SPLIT.
        sqls_emitidas = [c[0][0] for c in cursor.execute.call_args_list]
        sql_insert = next(
            (s for s in sqls_emitidas if 'INSERT INTO TGFITE' in s.upper()),
            None,
        )
        self.assertIsNotNone(sql_insert, msg='INSERT INTO TGFITE não emitido no SPLIT')
        # Os 3 campos do fix devem aparecer no SQL do INSERT
        self.assertIn('RESERVA', sql_insert)
        self.assertIn('ATUALESTOQUE', sql_insert)
        self.assertIn('USOPROD', sql_insert)
        # E os valores forçados:
        # RESERVA='S', ATUALESTOQUE=1, USOPROD lido de TGFPRO com fallback 'R'
        self.assertIn("'S'", sql_insert)
        self.assertIn('TGFPRO', sql_insert.upper())
        self.assertIn("'R'", sql_insert)


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
        """Mai/2026 (2026-05-13): ORA-20101 agora tem case especial — extrai a
        mensagem real do trigger Sankhya (que pode ser sobre tipo de negociação,
        STATUSNOTA bloqueado, ou outras regras). Quando a mensagem traz texto
        após "ORA-20101:", esse texto é repassado. Sem texto específico, cai
        em fallback genérico mencionando regra do banco."""
        from sankhya_integration.services.oracle_conn import humanizar_erro_oracle
        # Caso real com mensagem do trigger — deve repassar
        real = humanizar_erro_oracle(
            'ORA-20101: Verifique se o TIPO DE NEGOCIAÇÃO 99 está ativo'
        )
        self.assertIn('TIPO DE NEGOCIAÇÃO', real)
        # Caso genérico sem mensagem específica → fallback
        generico = humanizar_erro_oracle('ORA-20101: ...')
        self.assertTrue(generico)  # qualquer string não-vazia

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


def _conn_cursor_mock_rastreio():
    """Constrói (conn_ctx, cursor) compatível com `with obter_conexao_oracle() as conn`."""
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn_ctx = MagicMock()
    conn_ctx.__enter__.return_value = conn
    conn_ctx.__exit__.return_value = False
    return conn_ctx, conn, cursor


class ZerarFracaoLoteServiceTest(TestCase):
    """B1 (Mai/2026 — 2026-05-26, revisado 2026-05-28) — Cria TGFCAB TOP 33
    (Avaria de Ajuste) descontando saldo do lote.

    Mai/2026 — 2026-05-28: trava de 1% removida. Operador decide quanto
    avariar via param `qtd_avaria` (None = saldo todo, valor = parcial).
    Audit em AD_AUDITORIA_GERAL registra cada uso.
    """

    def setUp(self):
        from sankhya_integration.services.oracle_conn import zerar_fracao_lote_banco
        self.fn = zerar_fracao_lote_banco

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_escrita_desabilitada_retorna_erro(self, mock_perm):
        mock_perm.return_value = False
        r = self.fn(codprod=392, codagregacao='LOTE1', codusu=1, nomeusu='Teste')
        self.assertFalse(r['ok'])
        self.assertIn('Escrita desabilitada', r['error'])

    def test_codprod_ou_codagregacao_vazios_recusa(self):
        r1 = self.fn(codprod=0, codagregacao='LOTE1', codusu=1, nomeusu='T')
        self.assertFalse(r1['ok'])
        r2 = self.fn(codprod=392, codagregacao='', codusu=1, nomeusu='T')
        self.assertFalse(r2['ok'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_lote_inexistente_retorna_erro(self, mock_perm, mock_conn):
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.return_value = (None, None, None)  # view sem retorno
        r = self.fn(codprod=999, codagregacao='LOTE_FANTASMA',
                    codusu=1, nomeusu='Teste')
        self.assertFalse(r['ok'])
        self.assertIn('não encontrado', r['error'])

    @patch('sankhya_integration.services.oracle_conn.invalidar_cache_rastreio')
    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_saldo_grande_sem_trava_aceita(
        self, mock_perm, mock_conn, mock_cab, mock_item, mock_rec, mock_audit, mock_invcache,
    ):
        """Mai/2026 — 2026-05-28: saldo de 50 kg num lote de 100 (50%) é
        aceito agora. Operador decide manualmente — sem trava de 1%."""
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.side_effect = [
            (50.0, 100.0, 11111),
            (1, 200, 10100, date(2026, 5, 1), 11, 'KG', 1.0),
            (10.0,),
        ]
        mock_cab.return_value = {'ok': True, 'nunota': 99999}
        mock_item.return_value = {'ok': True, 'nunota': 99999, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        r = self.fn(codprod=392, codagregacao='LOTE_GRANDE',
                    codusu=1, nomeusu='Teste')
        self.assertTrue(r['ok'], f"Inesperado: {r}")
        self.assertEqual(r['qtd_zerada'], 50.0)
        self.assertFalse(r['avaria_parcial'])  # zera tudo por default

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_saldo_ja_zerado_recusa(self, mock_perm, mock_conn):
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.return_value = (0.0, 100.0, 12345)
        r = self.fn(codprod=392, codagregacao='LOTE1', codusu=1, nomeusu='Teste')
        self.assertFalse(r['ok'])
        self.assertIn('já está zerado', r['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_qtd_avaria_negativa_recusa(self, mock_perm, mock_conn):
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.return_value = (10.0, 100.0, 12345)
        r = self.fn(codprod=392, codagregacao='LOTE1', codusu=1, nomeusu='T',
                    qtd_avaria=-5.0)
        self.assertFalse(r['ok'])
        self.assertIn('> 0', r['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_qtd_avaria_acima_do_saldo_recusa(self, mock_perm, mock_conn):
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.return_value = (10.0, 100.0, 12345)
        r = self.fn(codprod=392, codagregacao='LOTE1', codusu=1, nomeusu='T',
                    qtd_avaria=50.0)
        self.assertFalse(r['ok'])
        self.assertIn('excede saldo', r['error'])

    @patch('sankhya_integration.services.oracle_conn.invalidar_cache_rastreio')
    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_fluxo_feliz_cria_top33_com_codagregacao(
        self, mock_perm, mock_conn, mock_cab, mock_item, mock_rec, mock_audit, mock_invcache,
    ):
        """Cenário do operador: lote tem 1 kg de sobra (default = saldo todo).
        TGFCAB TOP 33 criada com CODAGREGACAO preservado."""
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.side_effect = [
            (1.0, 100.0, 11111),                           # view: saldo, entrada, nunota_origem
            (1, 200, 10100, date(2026, 5, 1), 11, 'KG', 1.0),  # TGFCAB TOP 11 origem
            (12.50,),                                      # VLRUNIT do vale TOP 13
        ]
        mock_cab.return_value = {'ok': True, 'nunota': 99999}
        mock_item.return_value = {'ok': True, 'nunota': 99999, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        r = self.fn(codprod=392, codagregacao='LOTE_TOMATE_001',
                    codusu=1, nomeusu='Teste')

        self.assertTrue(r['ok'], f"Inesperado: {r}")
        self.assertEqual(r['nunota_33'], 99999)
        self.assertEqual(r['qtd_zerada'], 1.0)
        self.assertFalse(r['avaria_parcial'])

        # TGFCAB TOP 33 criada
        self.assertTrue(mock_cab.called)
        dados_cab = mock_cab.call_args[0][0]
        self.assertEqual(dados_cab['CODTIPOPER'], 33)
        self.assertEqual(dados_cab['CODNAT'], 20010200)
        self.assertEqual(dados_cab['STATUSNOTA'], 'L')
        self.assertEqual(dados_cab['CODTIPVENDA'], 11)
        self.assertEqual(dados_cab['CODEMP'], 1)
        self.assertEqual(dados_cab['AD_NUMPEDIDOORIG'], 11111)

        # TGFITE com CODAGREGACAO preservado
        self.assertTrue(mock_item.called)
        dados_item = mock_item.call_args[0][0]
        self.assertEqual(dados_item['CODPROD'], 392)
        self.assertEqual(dados_item['CODAGREGACAO'], 'LOTE_TOMATE_001')
        self.assertEqual(dados_item['QTDNEG'], 1.0)
        self.assertEqual(dados_item['VLRUNIT'], 12.50)
        self.assertAlmostEqual(dados_item['VLRTOT'], 12.50, places=2)

        # Audit chamado
        self.assertTrue(mock_audit.called)
        self.assertEqual(mock_audit.call_args.kwargs['operacao'], 'ZERAR_FRACAO_LOTE')

        # Cache invalidado
        self.assertTrue(mock_invcache.called)

    @patch('sankhya_integration.services.oracle_conn.invalidar_cache_rastreio')
    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_qtd_avaria_parcial(
        self, mock_perm, mock_conn, mock_cab, mock_item, mock_rec, mock_audit, mock_invcache,
    ):
        """Lote com 30 kg de saldo, operador avaria apenas 12 kg (parcial).
        Resultado: TOP 33 com 12, avaria_parcial=True, lote continua com 18 kg."""
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.side_effect = [
            (30.0, 500.0, 11111),
            (1, 200, 10100, date(2026, 5, 1), 11, 'KG', 1.0),
            (8.0,),
        ]
        mock_cab.return_value = {'ok': True, 'nunota': 88888}
        mock_item.return_value = {'ok': True, 'nunota': 88888, 'sequencia': 1}
        mock_rec.return_value = {'ok': True}

        r = self.fn(codprod=392, codagregacao='LOTE_PARCIAL',
                    codusu=1, nomeusu='Teste', qtd_avaria=12.0)

        self.assertTrue(r['ok'])
        self.assertEqual(r['qtd_zerada'], 12.0)
        self.assertEqual(r['qtd_disponivel_antes'], 30.0)
        self.assertTrue(r['avaria_parcial'])

        # TGFITE com qtd parcial gravada (não saldo total)
        dados_item = mock_item.call_args[0][0]
        self.assertEqual(dados_item['QTDNEG'], 12.0)
        self.assertAlmostEqual(dados_item['VLRTOT'], 96.0, places=2)  # 12 × 8.0

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    def test_sem_nunota_origem_recusa(self, mock_perm, mock_conn):
        """Lote sem NUNOTA_ORIGEM (raro mas possível) → erro humanizado."""
        mock_perm.return_value = True
        conn_ctx, _, cur = _conn_cursor_mock_rastreio()
        mock_conn.return_value = conn_ctx
        cur.fetchone.return_value = (0.5, 100.0, None)
        r = self.fn(codprod=392, codagregacao='LOTE1', codusu=1, nomeusu='T')
        self.assertFalse(r['ok'])
        self.assertIn('NUNOTA_ORIGEM', r['error'])


class ApiRastreioZerarFracaoEndpointTest(TestCase):
    """B2 — endpoint POST /sankhya/rastreio/api/zerar-fracao/"""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['8'])  # IAGRO_PACKING tem acesso a rastreio

    def test_sem_payload_400(self):
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(url, data='', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_sem_codprod_ou_codagregacao_400(self):
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(url,
                                data=json.dumps({'codprod': 392}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_sem_sessao_redireciona(self):
        client = Client()  # sem _login_session
        url = reverse('api_rastreio_zerar_fracao')
        resp = client.post(url,
                           data=json.dumps({'codprod': 392, 'codagregacao': 'LOTE1'}),
                           content_type='application/json')
        # Sem sessão → exige_grupo redireciona pra /
        self.assertIn(resp.status_code, (302, 403))

    @patch('sankhya_integration.views.zerar_fracao_lote_banco')
    def test_sucesso_delega_pro_service(self, mock_svc):
        mock_svc.return_value = {
            'ok': True, 'nunota_33': 99999,
            'qtd_zerada': 1.0, 'qtd_disponivel_antes': 1.0,
            'avaria_parcial': False,
        }
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(url,
                                data=json.dumps({'codprod': 392, 'codagregacao': 'LOTE1'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['nunota_33'], 99999)
        mock_svc.assert_called_once()
        kwargs = mock_svc.call_args.kwargs
        self.assertEqual(kwargs['codprod'], 392)
        self.assertEqual(kwargs['codagregacao'], 'LOTE1')
        # Sem qtd no payload → qtd_avaria=None pro service (zera tudo)
        self.assertIsNone(kwargs.get('qtd_avaria'))

    @patch('sankhya_integration.views.zerar_fracao_lote_banco')
    def test_qtd_parcial_passada_no_payload_propaga_pro_service(self, mock_svc):
        mock_svc.return_value = {
            'ok': True, 'nunota_33': 88888,
            'qtd_zerada': 12.0, 'qtd_disponivel_antes': 30.0,
            'avaria_parcial': True,
        }
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(
            url,
            data=json.dumps({'codprod': 392, 'codagregacao': 'LOTE1', 'qtd': 12.0}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        kwargs = mock_svc.call_args.kwargs
        self.assertEqual(kwargs['qtd_avaria'], 12.0)

    def test_qtd_invalida_400(self):
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(
            url,
            data=json.dumps({'codprod': 392, 'codagregacao': 'LOTE1', 'qtd': 'abc'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_qtd_negativa_400(self):
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(
            url,
            data=json.dumps({'codprod': 392, 'codagregacao': 'LOTE1', 'qtd': -5}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.views.zerar_fracao_lote_banco')
    def test_service_falha_devolve_400_humanizado(self, mock_svc):
        mock_svc.return_value = {'ok': False, 'error': 'Lote já está zerado'}
        url = reverse('api_rastreio_zerar_fracao')
        resp = self.client.post(url,
                                data=json.dumps({'codprod': 392, 'codagregacao': 'LOTE1'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('já está zerado', resp.json()['error'].lower())
