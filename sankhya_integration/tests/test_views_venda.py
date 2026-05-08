"""
Testes do módulo de Venda (Portal TOP 34/35/37).

Todas as chamadas ao Oracle são mockadas. Nenhum código de produção é alterado.
Os testes documentam o comportamento atual do sistema.
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
# view_portal_vendas — controle de acesso e contexto do render
# ---------------------------------------------------------------------------

class PortalVendasAcessoTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_sem_sessao_redireciona_para_home(self):
        """Acesso sem login deve cair no home (exige_grupo)."""
        response = self.client.get(reverse('venda_portal'))
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_operacao_sem_permissao_redireciona_para_home(self):
        """Grupo Operação (8) não tem acesso ao portal de Vendas."""
        _login_session(self.client, grupos=['8'])
        response = self.client.get(reverse('venda_portal'))
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_comercial_sem_permissao_redireciona_para_home(self):
        """Grupo Comercial (9) não tem acesso ao portal de Vendas."""
        _login_session(self.client, grupos=['9'])
        response = self.client.get(reverse('venda_portal'))
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=False)
    def test_grupo_vendas_acessa_portal(self, _mock_perm):
        """Grupo Vendas (10) deve acessar o portal."""
        _login_session(self.client, grupos=['10'])
        response = self.client.get(reverse('venda_portal'))
        self.assertEqual(response.status_code, 200)

    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=False)
    def test_diretoria_acessa_portal(self, _mock_perm):
        """Grupo Diretoria (1) deve acessar o portal."""
        _login_session(self.client, grupos=['1'])
        response = self.client.get(reverse('venda_portal'))
        self.assertEqual(response.status_code, 200)

    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=True)
    def test_contexto_do_render_tem_campos_esperados(self, _mock_perm):
        """Params do GET devem ser refletidos no contexto (e nada extra)."""
        _login_session(self.client, grupos=['10'])
        response = self.client.get(
            reverse('venda_portal'),
            {
                'start': '2026-04-01',
                'end': '2026-04-30',
                'top': '34',
                'codparc': '999',
                'nunota_ini': '  12345  ',
            },
        )
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertIn('params', ctx)
        self.assertEqual(ctx['params']['date_start'], '2026-04-01')
        self.assertEqual(ctx['params']['date_end'], '2026-04-30')
        self.assertEqual(ctx['params']['top'], '34')
        self.assertEqual(ctx['params']['codparc'], 999)
        self.assertEqual(ctx['params']['nunota_ini'], '12345')
        self.assertIn('APP_VERSION', ctx)
        self.assertTrue(ctx['write_enabled'])


# ---------------------------------------------------------------------------
# api_listar_vendas — contrato de filtros e resposta
# ---------------------------------------------------------------------------

class ApiListarVendasTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_listar_vendas')

    @patch('sankhya_integration.views.listar_vendas_paginado', return_value=[])
    def test_sem_filtros_usa_defaults_de_paginacao(self, mock_fn):
        """Sem querystring, limite=50 e offset=0 devem chegar ao serviço."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        _, kwargs = mock_fn.call_args
        self.assertEqual(kwargs['limite'], 50)
        self.assertEqual(kwargs['offset'], 0)

    @patch('sankhya_integration.views.listar_vendas_paginado', return_value=[])
    def test_paginacao_respeitada_no_servico(self, mock_fn):
        """limit/offset da querystring devem ser repassados nomeados."""
        self.client.get(self.url, {'limit': '25', 'offset': '50'})
        _, kwargs = mock_fn.call_args
        self.assertEqual(kwargs['limite'], 25)
        self.assertEqual(kwargs['offset'], 50)

    @patch('sankhya_integration.views.listar_vendas_paginado', return_value=[])
    def test_filtros_encaminhados_ao_servico(self, mock_fn):
        """Todos os filtros do GET devem ser encaminhados ao serviço."""
        self.client.get(self.url, {
            'start': '2026-04-01',
            'end': '2026-04-30',
            'codemp': '10',
            'nunota_ini': '999',
            'numnota': '1234',
            'top': '35',
            'codparc': '77',
            'codprod': 'MORANGO',
            'lote': 'L001',
        })
        _, kwargs = mock_fn.call_args
        self.assertEqual(kwargs['date_start'], '2026-04-01')
        self.assertEqual(kwargs['date_end'], '2026-04-30')
        self.assertEqual(kwargs['codemp'], '10')
        self.assertEqual(kwargs['nunota_ini'], '999')
        self.assertEqual(kwargs['numnota'], '1234')
        self.assertEqual(kwargs['top'], '35')
        self.assertEqual(kwargs['codparc'], '77')
        self.assertEqual(kwargs['codprod'], 'MORANGO')
        self.assertEqual(kwargs['lote'], 'L001')

    @patch('sankhya_integration.views.listar_vendas_paginado')
    def test_tupla_mapeada_para_dict_com_chaves_esperadas(self, mock_fn):
        """Cada tupla do Oracle deve virar dict com as chaves usadas pelo JS."""
        mock_fn.return_value = [
            (12345, 34, date(2026, 4, 15), 'CLIENTE X',
             1500.75, 'OK', 987, 10),
        ]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['vendas']), 1)
        v = data['vendas'][0]
        self.assertEqual(v['nunota'], 12345)
        self.assertEqual(v['top'], 34)
        self.assertEqual(v['data'], '15/04/2026')
        self.assertEqual(v['parceiro'], 'CLIENTE X')
        self.assertAlmostEqual(v['total'], 1500.75)
        self.assertEqual(v['status_lote'], 'OK')
        self.assertEqual(v['numnota'], 987)
        self.assertEqual(v['emp'], 10)

    @patch('sankhya_integration.views.listar_vendas_paginado')
    def test_dtneg_none_vira_string_vazia(self, mock_fn):
        """Data nula no Oracle deve virar string vazia na resposta."""
        mock_fn.return_value = [
            (1, 34, None, 'X', 100.0, 'OK', 0, 10),
        ]
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['vendas'][0]['data'], '')

    @patch('sankhya_integration.views.listar_vendas_paginado')
    def test_total_none_vira_zero(self, mock_fn):
        """VLRNOTA nulo deve virar 0.0 (protege formatação no JS)."""
        mock_fn.return_value = [
            (1, 34, date(2026, 1, 1), 'X', None, 'OK', 0, 10),
        ]
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertAlmostEqual(data['vendas'][0]['total'], 0.0)

    @patch('sankhya_integration.views.listar_vendas_paginado')
    def test_parceiro_none_vira_string_vazia(self, mock_fn):
        """NOMEPARC nulo deve virar string vazia."""
        mock_fn.return_value = [
            (1, 34, date(2026, 1, 1), None, 10.0, 'OK', 0, 10),
        ]
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['vendas'][0]['parceiro'], '')

    @patch('sankhya_integration.views.listar_vendas_paginado',
           side_effect=Exception('boom'))
    def test_excecao_do_servico_retorna_500(self, _mock_fn):
        """Falha no Oracle deve retornar 500 com ok=False e mensagem."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('boom', data['error'])

    def test_metodo_post_nao_permitido(self):
        """Endpoint aceita apenas GET (@require_http_methods)."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


# ---------------------------------------------------------------------------
# Helper compartilhado entre casos de escrita
# ---------------------------------------------------------------------------

def _mock_oracle_conn(mock_ctx_fn):
    """Monta um context manager mockado com conn.commit/rollback rastreáveis."""
    mock_conn = MagicMock()
    mock_ctx_fn.return_value.__enter__.return_value = mock_conn
    mock_ctx_fn.return_value.__exit__.return_value = None
    return mock_conn


# ---------------------------------------------------------------------------
# api_criar_cabecalho_venda — criação de Pedido TOP 34
# ---------------------------------------------------------------------------

class CriarCabecalhoVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_criar_cabecalho_venda')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_sem_sessao_redireciona_para_home(self):
        self.client.session.flush()
        response = self._post({'codparc': 1, 'dtneg': '2026-04-23'})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_comercial_nao_autorizado(self):
        _login_session(self.client, grupos=['9'])
        response = self._post({'codparc': 1, 'dtneg': '2026-04-23'})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_metodo_get_nao_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_payload_vazio_retorna_400(self):
        response = self.client.post(
            self.url, data='', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content)['ok'])

    def test_sem_codparc_retorna_400(self):
        response = self._post({'dtneg': '2026-04-23'})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('CODPARC', data['error'])

    def test_sem_dtneg_retorna_400(self):
        response = self._post({'codparc': 123, 'codtipvenda': 1})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('DTNEG', data['error'])

    def test_sem_codtipvenda_retorna_400(self):
        response = self._post({'codparc': 123, 'dtneg': '2026-04-23'})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('CODTIPVENDA', data['error'])

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada_retorna_403(self, _mock_perm):
        response = self._post({
            'codparc': 1, 'dtneg': '2026-04-23', 'codtipvenda': 1,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(json.loads(response.content)['ok'])

    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_payload_valido_envia_hardcodes_corretos(self, _mock_perm, mock_ctx, mock_fn):
        """CODEMP=10 default, CODTIPOPER=34, CODNAT=1010100, CODCENCUS=10100, CODTIPVENDA repassado."""
        mock_conn = _mock_oracle_conn(mock_ctx)
        mock_fn.return_value = {'ok': True, 'executed': True, 'nunota': 555}
        response = self._post({
            'codparc': 123,
            'dtneg': '2026-04-23',
            'codtipvenda': 7,
            'obs': 'Observação teste',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {'ok': True, 'nunota': 555})
        payload = mock_fn.call_args[0][0]
        self.assertEqual(payload['CODEMP'], 10)
        self.assertEqual(payload['CODPARC'], 123)
        self.assertEqual(payload['CODTIPOPER'], 34)
        self.assertEqual(payload['CODNAT'], 10010100)
        self.assertEqual(payload['CODCENCUS'], 10100)
        self.assertEqual(payload['CODTIPVENDA'], 7)
        self.assertEqual(payload['DTNEG'], '23/04/2026')
        self.assertEqual(payload['OBSERVACAO'], 'Observação teste')
        # Service chamado com a conexão gerenciada pela view e commit disparado
        self.assertIs(mock_fn.call_args.kwargs['conexao_existente'], mock_conn)
        mock_conn.commit.assert_called_once()

    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_codemp_personalizado_respeitado(self, _mock_perm, mock_ctx, mock_fn):
        """Quando informado, codemp do JSON substitui o default 10."""
        _mock_oracle_conn(mock_ctx)
        mock_fn.return_value = {'ok': True, 'executed': True, 'nunota': 1}
        self._post({
            'codparc': 1, 'dtneg': '2026-04-23', 'codtipvenda': 1, 'codemp': 5,
        })
        self.assertEqual(mock_fn.call_args[0][0]['CODEMP'], 5)

    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_service_retorna_executed_false_faz_rollback_e_propaga_400(
        self, _mock_perm, mock_ctx, mock_fn
    ):
        mock_conn = _mock_oracle_conn(mock_ctx)
        mock_fn.return_value = {
            'ok': False, 'executed': False, 'error': 'CODTIPOPER não encontrado',
        }
        response = self._post({
            'codparc': 1, 'dtneg': '2026-04-23', 'codtipvenda': 1,
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('CODTIPOPER', data['error'])
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco',
           side_effect=Exception('ORA-02291 integrity'))
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_excecao_do_servico_retorna_500(self, _mock_perm, mock_ctx, _mock_fn):
        """Erro Oracle deve ser humanizado (não vazar 'ORA-XXXXX' ao usuário)."""
        mock_conn = _mock_oracle_conn(mock_ctx)
        response = self._post({
            'codparc': 1, 'dtneg': '2026-04-23', 'codtipvenda': 1,
        })
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        # Mensagem amigável, sem expor o código ORA ao operador.
        self.assertNotIn('ORA-02291', data['error'])
        self.assertIn('Referência', data['error'])
        # Rollback explícito chamado quando a exceção sobe na view.
        mock_conn.rollback.assert_called()


# ---------------------------------------------------------------------------
# api_salvar_item_venda — inserção de item + recálculo de totais
# ---------------------------------------------------------------------------

class SalvarItemVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_salvar_item_venda')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_sem_sessao_redireciona_para_home(self):
        self.client.session.flush()
        response = self._post({'nunota': 1, 'codprod': 1, 'qtdneg': 1})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_operacao_nao_autorizado(self):
        _login_session(self.client, grupos=['8'])
        response = self._post({'nunota': 1, 'codprod': 1, 'qtdneg': 1})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_metodo_get_nao_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_payload_vazio_retorna_400(self):
        response = self.client.post(
            self.url, data='', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_sem_nunota_retorna_400(self):
        response = self._post({'codprod': 1, 'qtdneg': 1})
        self.assertEqual(response.status_code, 400)

    def test_sem_codprod_retorna_400(self):
        response = self._post({'nunota': 1, 'qtdneg': 1})
        self.assertEqual(response.status_code, 400)

    def test_sem_qtdneg_retorna_400(self):
        response = self._post({'nunota': 1, 'codprod': 1})
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 100.0, 'qtdvol': 5.0, 'cab_deleted': False})
    @patch('sankhya_integration.views.inserir_item_nota_banco',
           return_value={'ok': True, 'executed': True, 'sequencia': 1})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_payload_valido_usa_codvol_default_cx(self, mock_ctx, mock_insert, mock_recalc):
        """Sem codvol no JSON, service deve receber CODVOL='CX' (default)."""
        mock_conn = _mock_oracle_conn(mock_ctx)
        response = self._post({
            'nunota': 100, 'codprod': 200, 'qtdneg': 5, 'vlrunit': 20,
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['sequencia'], 1)
        self.assertAlmostEqual(data['vlrnota'], 100.0)
        self.assertAlmostEqual(data['qtdvol'], 5.0)

        payload = mock_insert.call_args[0][0]
        self.assertEqual(payload['NUNOTA'], 100)
        self.assertEqual(payload['CODPROD'], 200)
        self.assertAlmostEqual(payload['QTDNEG'], 5.0)
        self.assertAlmostEqual(payload['VLRUNIT'], 20.0)
        self.assertEqual(payload['CODVOL'], 'CX')
        self.assertEqual(payload['CODVOLPARC'], 'CX')
        self.assertIsNone(payload['CODAGREGACAO'])

        # Service chamado com a mesma conexão do context manager
        kwargs_insert = mock_insert.call_args.kwargs
        self.assertIs(kwargs_insert['conexao_existente'], mock_conn)
        # Venda NÃO pode auto-gerar lote: gerar_lote_auto deve ser False
        self.assertFalse(kwargs_insert['gerar_lote_auto'])
        kwargs_recalc = mock_recalc.call_args.kwargs
        self.assertIs(kwargs_recalc['conexao_existente'], mock_conn)
        mock_conn.commit.assert_called_once()

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True})
    @patch('sankhya_integration.views.inserir_item_nota_banco',
           return_value={'ok': True, 'executed': True, 'sequencia': 2})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_codvol_customizado_respeitado_e_normalizado(self, mock_ctx, mock_insert, _mock_recalc):
        """codvol='kg' deve virar 'KG' maiúsculo no payload."""
        _mock_oracle_conn(mock_ctx)
        self._post({
            'nunota': 1, 'codprod': 1, 'qtdneg': 1, 'vlrunit': 1, 'codvol': 'kg',
        })
        payload = mock_insert.call_args[0][0]
        self.assertEqual(payload['CODVOL'], 'KG')
        self.assertEqual(payload['CODVOLPARC'], 'KG')

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True})
    @patch('sankhya_integration.views.inserir_item_nota_banco',
           return_value={'ok': True, 'executed': True, 'sequencia': 3})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_codagregacao_opcional_repassado(self, mock_ctx, mock_insert, _mock_recalc):
        """Lote informado deve chegar ao service; vazio vira None."""
        _mock_oracle_conn(mock_ctx)
        self._post({
            'nunota': 1, 'codprod': 1, 'qtdneg': 1, 'vlrunit': 1,
            'codagregacao': 'L999S01D260423',
        })
        self.assertEqual(
            mock_insert.call_args[0][0]['CODAGREGACAO'], 'L999S01D260423'
        )

    @patch('sankhya_integration.views.inserir_item_nota_banco',
           return_value={'ok': False, 'executed': False, 'error': 'Cabeçalho não encontrado'})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_service_executed_false_faz_rollback_e_retorna_400(self, mock_ctx, _mock_insert):
        mock_conn = _mock_oracle_conn(mock_ctx)
        response = self._post({'nunota': 999, 'codprod': 1, 'qtdneg': 1, 'vlrunit': 1})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('Cabeçalho', data['error'])
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch('sankhya_integration.views.inserir_item_nota_banco',
           side_effect=Exception('SQL boom'))
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_excecao_do_servico_retorna_500(self, mock_ctx, _mock_insert):
        _mock_oracle_conn(mock_ctx)
        response = self._post({'nunota': 1, 'codprod': 1, 'qtdneg': 1, 'vlrunit': 1})
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('SQL boom', data['error'])


# ---------------------------------------------------------------------------
# api_excluir_pedido_venda — remoção de cabeçalho órfão
# ---------------------------------------------------------------------------

def _mock_cursor_top(mock_ctx_fn, top_value):
    """Atalho: configura context manager + cursor.fetchone() retornando (top,)."""
    mock_conn = _mock_oracle_conn(mock_ctx_fn)
    cur = MagicMock()
    cur.fetchone.return_value = (top_value,) if top_value is not None else None
    mock_conn.cursor.return_value = cur
    return mock_conn


class ExcluirPedidoVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_excluir_pedido_venda')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_sem_sessao_redireciona_para_home(self):
        self.client.session.flush()
        response = self._post({'nunota': 1})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_comercial_nao_autorizado(self):
        _login_session(self.client, grupos=['9'])
        response = self._post({'nunota': 1})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_metodo_get_nao_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_sem_nunota_retorna_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)
        self.assertIn('NUNOTA', json.loads(response.content)['error'])

    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_inexistente_retorna_404(self, mock_ctx):
        _mock_cursor_top(mock_ctx, None)
        response = self._post({'nunota': 999})
        self.assertEqual(response.status_code, 404)

    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_top_diferente_de_34_bloqueia(self, mock_ctx):
        """Só TOP 34 pode ser excluída por essa rota (trava protege TOP 35/37)."""
        _mock_cursor_top(mock_ctx, 35)
        response = self._post({'nunota': 100})
        self.assertEqual(response.status_code, 403)
        self.assertIn('TOP 34', json.loads(response.content)['error'])

    @patch('sankhya_integration.views.excluir_nota_completa_banco',
           return_value={'ok': True, 'executed': True, 'deleted_itens': 0, 'deleted_cab': 1})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_top_34_exclui_com_sucesso(self, mock_ctx, mock_excluir):
        _mock_cursor_top(mock_ctx, 34)
        response = self._post({'nunota': 100})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        mock_excluir.assert_called_once_with(100, simulacao=False)


# ---------------------------------------------------------------------------
# api_obter_cabecalho_pedido — dados para popular modal de edição
# ---------------------------------------------------------------------------

class ObterCabecalhoPedidoTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_obter_cabecalho_pedido')

    def test_sem_sessao_redireciona_para_home(self):
        self.client.session.flush()
        response = self.client.get(self.url, {'nunota': 1})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_comercial_nao_autorizado(self):
        _login_session(self.client, grupos=['9'])
        response = self.client.get(self.url, {'nunota': 1})
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_metodo_post_nao_permitido(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)

    def test_sem_nunota_retorna_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.consultar_cabecalho_venda_oracle',
           return_value=None)
    def test_pedido_inexistente_retorna_404(self, _mock_fn):
        response = self.client.get(self.url, {'nunota': 999})
        self.assertEqual(response.status_code, 404)

    @patch('sankhya_integration.views.consultar_cabecalho_venda_oracle')
    def test_sucesso_retorna_campos_mapeados(self, mock_fn):
        mock_fn.return_value = (
            10, 'HF SEMEAR', 536, 'CLIENTE TESTE',
            2, '30 DIAS', date(2026, 4, 23), 'Nota teste',
        )
        response = self.client.get(self.url, {'nunota': 100})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['codemp'], 10)
        self.assertEqual(data['nome_emp'], 'HF SEMEAR')
        self.assertEqual(data['codparc'], 536)
        self.assertEqual(data['nome_parc'], 'CLIENTE TESTE')
        self.assertEqual(data['codtipvenda'], 2)
        self.assertEqual(data['descr_tipvenda'], '30 DIAS')
        self.assertEqual(data['dtneg'], '2026-04-23')
        self.assertEqual(data['obs'], 'Nota teste')

    @patch('sankhya_integration.views.consultar_cabecalho_venda_oracle',
           side_effect=Exception('Oracle offline'))
    def test_excecao_retorna_500(self, _mock_fn):
        response = self.client.get(self.url, {'nunota': 1})
        self.assertEqual(response.status_code, 500)


# ---------------------------------------------------------------------------
# api_atualizar_cabecalho_venda — edição de Pedido TOP 34
# ---------------------------------------------------------------------------

class AtualizarCabecalhoVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_atualizar_cabecalho_venda')

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def _payload_valido(self, **overrides):
        base = {
            'nunota': 100, 'codparc': 536, 'codtipvenda': 2,
            'dtneg': '2026-04-23', 'codemp': 10, 'obs': '',
        }
        base.update(overrides)
        return base

    def test_sem_sessao_redireciona_para_home(self):
        self.client.session.flush()
        response = self._post(self._payload_valido())
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_grupo_comercial_nao_autorizado(self):
        _login_session(self.client, grupos=['9'])
        response = self._post(self._payload_valido())
        self.assertRedirects(
            response, reverse('home'), fetch_redirect_response=False
        )

    def test_metodo_get_nao_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_sem_nunota_retorna_400(self):
        response = self._post(self._payload_valido(nunota=None))
        self.assertEqual(response.status_code, 400)
        self.assertIn('NUNOTA', json.loads(response.content)['error'])

    def test_sem_codparc_retorna_400(self):
        response = self._post(self._payload_valido(codparc=None))
        self.assertEqual(response.status_code, 400)
        self.assertIn('CODPARC', json.loads(response.content)['error'])

    def test_sem_codtipvenda_retorna_400(self):
        response = self._post(self._payload_valido(codtipvenda=None))
        self.assertEqual(response.status_code, 400)
        self.assertIn('CODTIPVENDA', json.loads(response.content)['error'])

    def test_sem_dtneg_retorna_400(self):
        response = self._post(self._payload_valido(dtneg=None))
        self.assertEqual(response.status_code, 400)
        self.assertIn('DTNEG', json.loads(response.content)['error'])

    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_inexistente_retorna_404(self, mock_ctx):
        _mock_cursor_top(mock_ctx, None)
        response = self._post(self._payload_valido(nunota=999))
        self.assertEqual(response.status_code, 404)

    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_top_diferente_de_34_bloqueia(self, mock_ctx):
        _mock_cursor_top(mock_ctx, 35)
        response = self._post(self._payload_valido())
        self.assertEqual(response.status_code, 403)
        self.assertIn('TOP 34', json.loads(response.content)['error'])

    @patch('sankhya_integration.views.atualizar_cabecalho_venda_banco',
           return_value={'ok': True, 'executed': True})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_sucesso_envia_payload_maiusculo_ao_service(self, mock_ctx, mock_fn):
        _mock_cursor_top(mock_ctx, 34)
        response = self._post(self._payload_valido(obs='Alterado'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['nunota'], 100)
        payload = mock_fn.call_args[0][0]
        self.assertEqual(payload['NUNOTA'], 100)
        self.assertEqual(payload['CODEMP'], 10)
        self.assertEqual(payload['CODPARC'], 536)
        self.assertEqual(payload['CODTIPVENDA'], 2)
        self.assertEqual(payload['DTNEG'], '23/04/2026')
        self.assertEqual(payload['OBSERVACAO'], 'Alterado')

    @patch('sankhya_integration.views.atualizar_cabecalho_venda_banco',
           return_value={'ok': False, 'executed': False, 'error': 'coluna inválida'})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_service_retorna_executed_false_propaga_400(self, mock_ctx, _mock_fn):
        _mock_cursor_top(mock_ctx, 34)
        response = self._post(self._payload_valido())
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['ok'])
        self.assertIn('coluna', data['error'])

    @patch('sankhya_integration.views.atualizar_cabecalho_venda_banco',
           side_effect=Exception('ORA-01234'))
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_excecao_retorna_500(self, mock_ctx, _mock_fn):
        _mock_cursor_top(mock_ctx, 34)
        response = self._post(self._payload_valido())
        self.assertEqual(response.status_code, 500)
        self.assertIn('ORA-01234', json.loads(response.content)['error'])


# ---------------------------------------------------------------------------
# api_atualizar_item_venda — Fase 2.1 (editar item individual)
# ---------------------------------------------------------------------------

class AtualizarItemVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_atualizar_item_venda')

    def _post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    def test_sem_sessao_redireciona(self):
        self.client.session.flush()
        response = self._post({'nunota': 1, 'sequencia': 1})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_metodo_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_payload_vazio_400(self):
        response = self.client.post(self.url, data='', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_sem_nunota_ou_sequencia_400(self):
        self.assertEqual(self._post({'sequencia': 1}).status_code, 400)
        self.assertEqual(self._post({'nunota': 1}).status_code, 400)

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada_403(self, _mp):
        response = self._post({'nunota': 1, 'sequencia': 1, 'qtdneg': 5})
        self.assertEqual(response.status_code, 403)

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_nao_encontrado_404(self, mock_ctx, _mp):
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 999, 'sequencia': 1, 'qtdneg': 5})
        self.assertEqual(response.status_code, 404)

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_top_diferente_de_34_403(self, mock_ctx, _mp):
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = (35, 'L')   # TOP 35, faturado
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 1, 'sequencia': 1, 'qtdneg': 5})
        self.assertEqual(response.status_code, 403)
        self.assertIn('TOP 34', json.loads(response.content)['error'])

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_faturado_403(self, mock_ctx, _mp):
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = (34, 'L')   # TOP 34 mas STATUSNOTA L
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 1, 'sequencia': 1, 'qtdneg': 5})
        self.assertEqual(response.status_code, 403)
        self.assertIn('faturado', json.loads(response.content)['error'].lower())

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 200.0, 'qtdvol': 8.0})
    @patch('sankhya_integration.views.atualizar_item_nota_banco',
           return_value={'ok': True, 'executed': True})
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_atualizacao_sucesso_dispara_recalculo_e_commit(
        self, mock_ctx, _mp, mock_upd, mock_recalc
    ):
        # Primeiro cursor (validação) retorna TOP 34 + STATUSNOTA != L;
        # segundo cursor (escrita) é o mesmo conn, sem retorno relevante.
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = (34, '0')
        mock_conn.cursor.return_value = cursor
        response = self._post({
            'nunota': 100, 'sequencia': 2, 'qtdneg': 8, 'vlrunit': 25, 'codvol': 'KG',
        })
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['sequencia'], 2)
        self.assertAlmostEqual(body['vlrnota'], 200.0)
        # Service chamado com payload correto + conexão da view
        payload = mock_upd.call_args[0][0]
        self.assertEqual(payload['NUNOTA'], 100)
        self.assertEqual(payload['SEQUENCIA'], 2)
        self.assertAlmostEqual(payload['QTDNEG'], 8.0)
        self.assertEqual(payload['CODVOL'], 'KG')
        self.assertEqual(payload['CODVOLPARC'], 'KG')   # auto-mirror
        # commit foi chamado uma vez (atomicidade — Fase 1.3)
        mock_conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# api_remover_item_venda — Fase 2.1 (remover item individual)
# ---------------------------------------------------------------------------

class RemoverItemVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_remover_item_venda')

    def _post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    def test_sem_sessao_redireciona(self):
        self.client.session.flush()
        response = self._post({'nunota': 1, 'sequencia': 1})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_metodo_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_sem_nunota_ou_sequencia_400(self):
        self.assertEqual(self._post({'sequencia': 1}).status_code, 400)

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_top_diferente_403(self, mock_ctx, _mp):
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = (35, 'L')
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 1, 'sequencia': 1})
        self.assertEqual(response.status_code, 403)
        # Rollback não chamado pois a trava bloqueou antes do DELETE,
        # mas commit também não — a transação ficou intacta.
        mock_conn.commit.assert_not_called()

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 50.0, 'qtdvol': 2.0,
                         'cab_deleted': False})
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_remocao_sucesso(self, mock_ctx, _mp, mock_recalc):
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        # 1ª chamada: validação TOP/STATUS; 2ª: DELETE com rowcount=1
        cursor.fetchone.return_value = (34, '0')
        cursor.rowcount = 1
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 100, 'sequencia': 3})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['sequencia'], 3)
        self.assertFalse(body['cab_deleted'])
        mock_conn.commit.assert_called_once()

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True, 'cab_deleted': True})
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_ultimo_item_remove_cabecalho(self, mock_ctx, _mp, mock_recalc):
        """Quando recalcular_totais informa cab_deleted=True, view propaga essa
        flag — JS usa isso para fechar o modal e atualizar a lista."""
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = (34, '0')
        cursor.rowcount = 1
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 100, 'sequencia': 1})
        body = json.loads(response.content)
        self.assertTrue(body['cab_deleted'])

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_item_inexistente_404(self, mock_ctx, _mp):
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        cursor.fetchone.return_value = (34, '0')
        cursor.rowcount = 0
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 100, 'sequencia': 999})
        self.assertEqual(response.status_code, 404)
        mock_conn.rollback.assert_called()


# ---------------------------------------------------------------------------
# api_faturar_pedido_venda — Fase 4.1+4.2 (Faturar Pedido)
# ---------------------------------------------------------------------------

class FaturarPedidoVendaTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_faturar_pedido_venda')

    def _post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    def test_sem_sessao_redireciona(self):
        self.client.session.flush()
        response = self._post({'nunota': 1, 'top': 35})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_grupo_operacao_nao_autorizado(self):
        _login_session(self.client, grupos=['8'])
        response = self._post({'nunota': 1, 'top': 35})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_metodo_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_sem_nunota_400(self):
        response = self._post({'top': 35})
        self.assertEqual(response.status_code, 400)

    def test_top_invalido_400(self):
        """TOP de faturamento só pode ser 35 ou 37."""
        response = self._post({'nunota': 1, 'top': 99})
        self.assertEqual(response.status_code, 400)
        self.assertIn('inválido', json.loads(response.content)['error'].lower())

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada_403(self, _mp):
        response = self._post({'nunota': 1, 'top': 35})
        self.assertEqual(response.status_code, 403)

    @patch('sankhya_integration.views.faturar_pedido_venda_banco',
           return_value={'ok': True, 'executed': True, 'top': 35,
                         'numnota': 42, 'codnat': 10010100, 'vlrnota': 1500.0})
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_faturar_top_35_sucesso(self, _mp, mock_fat):
        response = self._post({'nunota': 100, 'top': 35})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['top'], 35)
        self.assertEqual(body['numnota'], 42)
        # Service chamado com nova_top correto
        kwargs = mock_fat.call_args.kwargs
        self.assertEqual(kwargs['nunota'], 100)
        self.assertEqual(kwargs['nova_top'], 35)

    @patch('sankhya_integration.views.faturar_pedido_venda_banco',
           return_value={'ok': False, 'error': 'Pedido sem itens — não pode ser faturado.'})
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_faturar_pedido_sem_itens_400(self, _mp, _mock_fat):
        response = self._post({'nunota': 100, 'top': 37})
        self.assertEqual(response.status_code, 400)
        self.assertIn('sem itens', json.loads(response.content)['error'])

    @patch('sankhya_integration.views.faturar_pedido_venda_banco',
           side_effect=Exception('ORA-00054 lock timeout'))
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_excecao_retorna_500_humanizada(self, _mp, _mock_fat):
        """Erro de lock concorrente deve virar mensagem amigável (sem ORA)."""
        response = self._post({'nunota': 100, 'top': 35})
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.content)
        self.assertNotIn('ORA-00054', body['error'])
        # Mensagem operacional refinada (Mai/2026): aponta colega operador
        # e sugere ação de espera. Validamos pelos termos-chave em vez da
        # frase exata pra suportar futuras melhorias de microcopy.
        self.assertIn('operador', body['error'].lower())
        self.assertIn('aguarde', body['error'].lower())


# ---------------------------------------------------------------------------
# Helper compartilhado adicional
# ---------------------------------------------------------------------------
