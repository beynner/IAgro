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

    @patch('sankhya_integration.views.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 100.0, 'qtdvol': 5.0})
    @patch('sankhya_integration.views.atualizar_item_nota_banco',
           return_value={'ok': True, 'executed': True})
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_pedido_confirmado_l_aceita_edicao(self, mock_ctx, _mp, mock_upd, mock_recalc):
        """Mai/2026 (2026-05-20) — STATUSNOTA='L' em TOP 34 NÃO bloqueia edição.
        Paridade com Sankhya nativo (que permite editar pedido confirmado pra
        impressão). NFe real (TOP 35/37) continua bloqueada pela trava de TOP.
        """
        mock_conn = _mock_oracle_conn(mock_ctx)
        cursor = MagicMock()
        # TOP 34 + STATUSNOTA='L' (confirmado pra impressão) — DEVE aceitar
        cursor.fetchone.return_value = (34, 'L')
        mock_conn.cursor.return_value = cursor
        response = self._post({'nunota': 1, 'sequencia': 1, 'qtdneg': 5})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['ok'])

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


# ===========================================================================
# AVARIA (TOP 30) + DEVOLUÇÃO (TOP 36) + HISTÓRICO DE LOTE — Mai/2026
# ===========================================================================

class CriarAvariaEndpointTest(TestCase):
    """Endpoint /sankhya/venda/api/avaria/criar/"""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_criar_avaria')

    def _post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    def test_sem_sessao_redireciona(self):
        client = Client()  # sem login
        response = client.post(self.url, data=json.dumps({}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 302)

    def test_grupo_operacao_redireciona(self):
        client = Client()
        _login_session(client, grupos=['8'])
        response = client.post(self.url, data=json.dumps({'codemp': 10}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 302)

    def test_payload_invalido_400(self):
        response = self._post({'invalido': True})
        # JSON inválido / faltando campos vira 400; o service valida o resto
        self.assertIn(response.status_code, (400, 500))

    @patch('sankhya_integration.views.criar_avaria_top30_banco',
           return_value={'ok': True, 'executed': True, 'nunota': 99999,
                         'codnat': 20010200, 'vlrnota': 250.00})
    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=True)
    def test_sucesso(self, _mp, _mock_svc):
        response = self._post({
            'codemp': 10, 'codparc': 566, 'codagregacao': '12345S01D260507',
            'codprod': 358, 'qtdneg': 50.0, 'codvol': 'KG',
        })
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['nunota'], 99999)
        self.assertEqual(body['codnat'], 20010200)

    @patch('sankhya_integration.views.criar_avaria_top30_banco',
           return_value={'ok': False, 'error': 'Saldo insuficiente no lote X.'})
    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=True)
    def test_saldo_insuficiente_400(self, _mp, _mock_svc):
        response = self._post({
            'codemp': 10, 'codparc': 566, 'codagregacao': 'X',
            'codprod': 1, 'qtdneg': 99999.0,
        })
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.content)
        self.assertFalse(body['ok'])
        self.assertIn('Saldo insuficiente', body['error'])

    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=False)
    def test_escrita_desabilitada_403(self, _mp):
        response = self._post({'codemp': 10, 'codparc': 566})
        self.assertEqual(response.status_code, 403)

    @patch('sankhya_integration.views.criar_avaria_top30_banco',
           side_effect=Exception('ORA-00054 recurso ocupado'))
    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=True)
    def test_excecao_humanizada(self, _mp, _mock_svc):
        response = self._post({
            'codemp': 10, 'codparc': 566, 'codagregacao': 'X',
            'codprod': 1, 'qtdneg': 1.0,
        })
        self.assertEqual(response.status_code, 500)
        body = json.loads(response.content)
        self.assertNotIn('ORA-00054', body['error'])


class ObterNotaParaDevolucaoEndpointTest(TestCase):
    """Endpoint /sankhya/venda/api/devolucao/preparar/?nunota=X"""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_obter_nota_para_devolucao')

    def test_sem_nunota_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.consultar_nota_para_devolucao',
           return_value={'ok': False, 'error': 'Nota não encontrada'})
    def test_nota_inexistente_400(self, _mock):
        response = self.client.get(self.url, {'nunota': 99999})
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.consultar_nota_para_devolucao',
           return_value={
               'ok': True,
               'cabecalho': {'nunota': 111971, 'numnota': 6266,
                             'codemp': 10, 'codparc': 244,
                             'codtipoper': 35, 'statusnota': 'L',
                             'vlrnota': 100.0, 'codtipvenda': 2,
                             'dtneg': '2026-05-09', 'nomeparc': 'CLIENTE X'},
               'itens': [
                   {'sequencia': 1, 'codprod': 21, 'descrprod': 'TOMATE',
                    'codagregacao': '12345S01D260507', 'codvol': 'KG',
                    'qtdneg': 10.0, 'vlrunit': 5.0, 'vlrtot': 50.0,
                    'qtd_ja_devolvida': 2.0, 'qtd_devolvivel': 8.0},
               ],
           })
    def test_sucesso(self, _mock):
        response = self.client.get(self.url, {'nunota': 111971})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['cabecalho']['nunota'], 111971)
        self.assertEqual(len(body['itens']), 1)
        self.assertEqual(body['itens'][0]['qtd_devolvivel'], 8.0)


class ApiLotesDeItemNotaEndpointTest(TestCase):
    """Endpoint /sankhya/venda/api/lotes-de-item-nota/?nunota=X&sequencia=Y

    Navegação inversa TGFVAR — usada pelos modais de Devolução (já) e
    Avaria a partir de nota (Fase 3). Fase 1: só leitura.
    """

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_lotes_de_item_nota')

    def test_sem_params_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)

    def test_so_nunota_sem_sequencia_400(self):
        response = self.client.get(self.url, {'nunota': 111971})
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.consultar_lotes_origem_de_seq_nota',
           return_value={'ok': True,
                         'lotes': [
                             {'seq_pedido': 5, 'codagregacao': 'LOTE_A',
                              'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
                              'nunota_pedido': 111900},
                             {'seq_pedido': 6, 'codagregacao': 'LOTE_B',
                              'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
                              'nunota_pedido': 111900},
                         ],
                         'total_atendido': 1000.0})
    def test_sucesso_split_2_lotes(self, _mock):
        response = self.client.get(self.url, {'nunota': 111971, 'sequencia': 1})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(len(body['lotes']), 2)
        self.assertEqual(body['lotes'][0]['codagregacao'], 'LOTE_A')
        self.assertEqual(body['total_atendido'], 1000.0)

    @patch('sankhya_integration.views.consultar_lotes_origem_de_seq_nota',
           return_value={'ok': True, 'lotes': [], 'total_atendido': 0.0})
    def test_sem_tgfvar_par_retorna_vazio(self, _mock):
        """Nota órfã ou erro de fluxo — endpoint responde 200 com lista vazia."""
        response = self.client.get(self.url, {'nunota': 111971, 'sequencia': 1})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['lotes'], [])


class CriarDevolucaoEndpointTest(TestCase):
    """Endpoint /sankhya/venda/api/devolucao/criar/"""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_criar_devolucao')

    def _post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type='application/json')

    @patch('sankhya_integration.views.criar_devolucao_top36_banco',
           return_value={'ok': True, 'executed': True, 'nunota': 111999,
                         'codnat': 10020100, 'vlrnota': 80.0})
    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=True)
    def test_sucesso(self, _mp, _mock_svc):
        response = self._post({
            'nunota_origem': 111971,
            'itens': [{'sequencia_origem': 1, 'qtd_devolver': 8.0}],
            'observacao': 'cliente recusou',
        })
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['nunota'], 111999)
        self.assertEqual(body['codnat'], 10020100)

    @patch('sankhya_integration.views.criar_devolucao_top36_banco',
           return_value={'ok': False, 'error': 'Quantidade excessiva no item SEQ=1 (TOMATE). Já devolvido: 8.000 · Saldo devolvível: 2.000 · Solicitado: 5.000.'})
    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=True)
    def test_qtd_excessiva_400(self, _mp, _mock_svc):
        response = self._post({
            'nunota_origem': 111971,
            'itens': [{'sequencia_origem': 1, 'qtd_devolver': 5.0}],
        })
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.content)
        self.assertIn('Quantidade excessiva', body['error'])

    @patch('sankhya_integration.views.verificar_permissao_escrita',
           return_value=False)
    def test_escrita_desabilitada_403(self, _mp):
        response = self._post({'nunota_origem': 111971,
                               'itens': [{'sequencia_origem': 1, 'qtd_devolver': 1.0}]})
        self.assertEqual(response.status_code, 403)

    def test_payload_invalido_400(self):
        response = self.client.post(self.url, data='não-json',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)


class HistoricoLoteEndpointTest(TestCase):
    """Endpoint /sankhya/venda/api/lote/historico/?lote=X"""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'])
        self.url = reverse('api_historico_lote')

    def test_sem_lote_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)

    @patch('sankhya_integration.views.obter_historico_lote',
           return_value={'ok': True, 'lote': '12345S01D260507', 'timeline': []})
    def test_lote_inexistente_retorna_timeline_vazia(self, _mock):
        response = self.client.get(self.url, {'lote': '12345S01D260507'})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['timeline'], [])

    @patch('sankhya_integration.views.obter_historico_lote',
           return_value={
               'ok': True, 'lote': '12345S01D260507',
               'timeline': [
                   {'nunota': 100, 'numnota': 5000, 'codtipoper': 11,
                    'top_nome': 'Compra (Entrada)', 'statusnota': 'L',
                    'dtneg': '2026-04-01', 'codparc': 100, 'nomeparc': 'FOR.',
                    'codprod': 358, 'descrprod': 'TOMATE', 'qtdneg': 1000.0,
                    'codvol': 'KG', 'vlrunit': 3.0, 'vlrtot': 3000.0,
                    'sequencia': 1, 'ad_qtdavaria': 0,
                    'is_baixa': False, 'is_entrada': True, 'is_devolucao': False},
                   {'nunota': 200, 'numnota': 6000, 'codtipoper': 35,
                    'top_nome': 'Venda com NFe', 'statusnota': 'L',
                    'dtneg': '2026-05-01', 'codparc': 500, 'nomeparc': 'CLI.',
                    'codprod': 358, 'descrprod': 'TOMATE', 'qtdneg': 200.0,
                    'codvol': 'KG', 'vlrunit': 5.0, 'vlrtot': 1000.0,
                    'sequencia': 1, 'ad_qtdavaria': 0,
                    'is_baixa': True, 'is_entrada': False, 'is_devolucao': False},
               ],
           })
    def test_timeline_completa(self, _mock):
        response = self.client.get(self.url, {'lote': '12345S01D260507'})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(len(body['timeline']), 2)
        # Ordem cronológica preservada
        self.assertEqual(body['timeline'][0]['codtipoper'], 11)
        self.assertEqual(body['timeline'][1]['codtipoper'], 35)

    def test_sem_sessao_redireciona(self):
        client = Client()
        response = client.get(self.url, {'lote': 'X'})
        self.assertEqual(response.status_code, 302)


class CriarAvariaServiceTest(TestCase):
    """Testa direto a função criar_avaria_top30_banco (sem passar pela view)."""

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_escrita_desabilitada(self, _mp):
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        res = criar_avaria_top30_banco({})
        self.assertFalse(res['ok'])
        self.assertIn('desabilitada', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_payload_faltando_campos(self, _mp):
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        res = criar_avaria_top30_banco({'codemp': 10})  # falta codparc, lote, etc
        self.assertFalse(res['ok'])
        self.assertIn('obrigatórios', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtd_negativa(self, _mp):
        """qtdneg=0 é bloqueada pela validação 'obrigatórios' (0 é falsy);
        qtdneg<0 passa a primeira validação e cai no '> 0' explícito."""
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 566,
            'codagregacao': 'X', 'codprod': 1, 'qtdneg': -1,
        })
        self.assertFalse(res['ok'])
        self.assertIn('maior que zero', res['error'].lower())


class InserirItemNotaBancoQtdConferidaTest(TestCase):
    """B4 (Mai/2026 — 2026-05-22): QTDCONFERIDA=0 default em TOP 34/35/37.

    Sankhya rejeita "atender pedido" com CORE_E04678 quando o item
    TGFITE nasce com QTDCONFERIDA=QTDNEG (entende como já conferido).
    Sankhya nativo grava 0.0. IAgro tava copiando QTDNEG como default.
    Confirmado via UPDATE cirúrgico em 113264 (QTDCONFERIDA: 1.0 → 0.0
    destravou o faturamento sem mudar nenhum outro campo).
    """

    COLUNAS_TGFITE_MIN = {
        'NUNOTA', 'SEQUENCIA', 'CODEMP', 'CODPROD', 'QTDNEG', 'VLRUNIT',
        'VLRTOT', 'AD_NUMPEDIDOORIG', 'CODVOL', 'CODLOCALORIG',
        'QTDCONFERIDA', 'PESO', 'RESERVA', 'ATUALESTOQUE', 'USOPROD',
    }

    def _capturar_insert_tgfite(self, cur_mock):
        for call in cur_mock.execute.call_args_list:
            if 'INSERT INTO TGFITE' in (call.args[0] if call.args else ''):
                return call.args[1]
        return None

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item',
           return_value=1)
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_top_34_qtdconferida_zero(self, _mp, mock_conn, mock_cols, _mseq):
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco
        mock_cols.return_value = self.COLUNAS_TGFITE_MIN
        cur_mock = MagicMock()
        # 1) SELECT cab: CODTIPOPER=34
        # 2) SELECT USOPROD TGFPRO (TOP 34/35/37 lê)
        cur_mock.fetchone.side_effect = [
            (10, None, 244, 113000, 34),
            ('R',),
        ]
        conn = MagicMock(); conn.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn

        res = inserir_item_nota_banco({
            'NUNOTA': 113000, 'CODPROD': 358, 'QTDNEG': 1.0,
            'VLRUNIT': 8.5, 'CODVOL': 'KG',
        }, gerar_lote_auto=False)
        self.assertTrue(res.get('ok'), msg=res.get('error'))

        binds = self._capturar_insert_tgfite(cur_mock)
        self.assertIsNotNone(binds, "INSERT TGFITE não capturado")
        self.assertEqual(binds.get('QTDCONFERIDA'), 0.0,
                         "TOP 34 deve gravar QTDCONFERIDA=0 (não QTDNEG)")
        # Sanity check — QTDNEG ainda é 1.0
        self.assertEqual(binds.get('QTDNEG'), 1.0)

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item',
           return_value=1)
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_top_11_qtdconferida_igual_qtdneg(self, _mp, mock_conn, mock_cols, _mseq):
        """Regressão: Entrada (TOP 11) preserva default antigo QTDCONFERIDA=QTDNEG."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco
        mock_cols.return_value = self.COLUNAS_TGFITE_MIN
        cur_mock = MagicMock()
        cur_mock.fetchone.side_effect = [
            (10, None, 244, 0, 11),
        ]
        conn = MagicMock(); conn.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn

        res = inserir_item_nota_banco({
            'NUNOTA': 100, 'CODPROD': 358, 'QTDNEG': 500.0,
            'VLRUNIT': 3.0, 'CODVOL': 'KG',
        }, gerar_lote_auto=False)
        self.assertTrue(res.get('ok'), msg=res.get('error'))

        binds = self._capturar_insert_tgfite(cur_mock)
        self.assertEqual(binds.get('QTDCONFERIDA'), 500.0,
                         "TOP 11 deve preservar QTDCONFERIDA=QTDNEG default antigo")

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item',
           return_value=1)
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtdconferida_explicita_no_payload_respeitada(self, _mp, mock_conn, mock_cols, _mseq):
        """Caller que passa QTDCONFERIDA explícita NÃO é sobrescrito pelo fix."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco
        mock_cols.return_value = self.COLUNAS_TGFITE_MIN
        cur_mock = MagicMock()
        cur_mock.fetchone.side_effect = [
            (10, None, 244, 0, 34),
            ('R',),
        ]
        conn = MagicMock(); conn.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn

        # TOP 34, mas operador passou QTDCONFERIDA=2.5 explícito
        res = inserir_item_nota_banco({
            'NUNOTA': 113000, 'CODPROD': 358, 'QTDNEG': 5.0,
            'VLRUNIT': 8.5, 'CODVOL': 'KG',
            'QTDCONFERIDA': 2.5,
        }, gerar_lote_auto=False)
        self.assertTrue(res.get('ok'), msg=res.get('error'))

        binds = self._capturar_insert_tgfite(cur_mock)
        self.assertEqual(binds.get('QTDCONFERIDA'), 2.5,
                         "QTDCONFERIDA explícita no payload deve ser respeitada")

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item',
           return_value=1)
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtdconferida_zero_explicito_em_top_11(self, _mp, mock_conn, mock_cols, _mseq):
        """Edge case: caller pode forçar QTDCONFERIDA=0 mesmo em TOP 11
        (default antigo `or qtdneg` ignorava 0 e usava qtdneg — fix corrige)."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco
        mock_cols.return_value = self.COLUNAS_TGFITE_MIN
        cur_mock = MagicMock()
        cur_mock.fetchone.side_effect = [
            (10, None, 244, 0, 11),
        ]
        conn = MagicMock(); conn.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn

        res = inserir_item_nota_banco({
            'NUNOTA': 100, 'CODPROD': 358, 'QTDNEG': 500.0,
            'VLRUNIT': 3.0, 'CODVOL': 'KG',
            'QTDCONFERIDA': 0,
        }, gerar_lote_auto=False)
        self.assertTrue(res.get('ok'), msg=res.get('error'))

        binds = self._capturar_insert_tgfite(cur_mock)
        self.assertEqual(binds.get('QTDCONFERIDA'), 0.0,
                         "QTDCONFERIDA=0 explícito deve ser respeitado (não cair em qtdneg)")


class CriarAvariaSplitLotesServiceTest(TestCase):
    """B2 (Mai/2026) — modo "a partir de nota" no criar_avaria_top30_banco.

    Cenário: produto avariado veio de SPLIT no pedido (2 lotes diferentes).
    Operador escolhe 1 item da nota e divide a qtd avariada entre os lotes
    reais via navegação inversa TGFVAR. Backend cria 1 TGFCAB TOP 30 + N
    TGFITE (1 por lote). Sem TGFVAR (política da avaria preservada).
    """

    LOTES_SPLIT = {
        'ok': True,
        'lotes': [
            {'seq_pedido': 5, 'codagregacao': 'LOTE_A',
             'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
             'nunota_pedido': 111900},
            {'seq_pedido': 6, 'codagregacao': 'LOTE_B',
             'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
             'nunota_pedido': 111900},
        ],
        'total_atendido': 1000.0,
    }

    def _montar_mocks(self, _conn_mock, seq_inicial=10):
        seq_counter = {'v': seq_inicial - 1}

        def _ins_ite(_payload, **_kwargs):
            seq_counter['v'] += 1
            return {'ok': True, 'sequencia': seq_counter['v']}

        return _ins_ite

    def _mock_cursor_saldo(self, conn_obj, saldo=1000.0):
        """Configura o cursor pra responder SELECT de saldo da view."""
        cur_mock = MagicMock()
        cur_mock.fetchone.return_value = (saldo,)
        conn_obj.cursor.return_value = cur_mock
        return cur_mock

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 400.0})
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco',
           return_value={'ok': True, 'nunota': 300000})
    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_split_2_lotes_cria_n_tgfite_e_um_tgfcab(
            self, _mp, mock_conn, _ml, _mcab, mock_ite, _mr):
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco

        conn_obj = MagicMock()
        cur_mock = self._mock_cursor_saldo(conn_obj, saldo=1000.0)
        mock_conn.return_value.__enter__.return_value = conn_obj
        mock_ite.side_effect = self._montar_mocks(conn_obj)

        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 244, 'codprod': 21,
            'codvol': 'KG', 'vlrunit': 5.0,
            'nunota_origem_nota': 111971, 'sequencia_nota': 1,
            'lotes_avaria': [
                {'codagregacao': 'LOTE_A', 'qtd': 50.0},
                {'codagregacao': 'LOTE_B', 'qtd': 30.0},
            ],
        })

        self.assertTrue(res['ok'], msg=res.get('error'))
        self.assertEqual(res['nunota'], 300000)
        # 2 TGFITE criados, 1 TGFCAB
        self.assertEqual(mock_ite.call_count, 2)
        self.assertEqual(_mcab.call_count, 1)
        codagregs = [c.args[0]['CODAGREGACAO'] for c in mock_ite.call_args_list]
        self.assertEqual(set(codagregs), {'LOTE_A', 'LOTE_B'})
        # Sem TGFVAR — confirma política preservada (avaria não tem rastro Sankhya)
        chamadas_tgfvar = [
            call for call in cur_mock.execute.call_args_list
            if 'INSERT INTO TGFVAR' in (call.args[0] if call.args else '')
        ]
        self.assertEqual(len(chamadas_tgfvar), 0)

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_lote_fora_do_tgfvar_bloqueia(self, _mp, mock_conn, _ml):
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        conn_obj = MagicMock()
        self._mock_cursor_saldo(conn_obj)
        mock_conn.return_value.__enter__.return_value = conn_obj

        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 244, 'codprod': 21,
            'codvol': 'KG',
            'nunota_origem_nota': 111971, 'sequencia_nota': 1,
            'lotes_avaria': [{'codagregacao': 'LOTE_FANTASMA', 'qtd': 50.0}],
        })
        self.assertFalse(res['ok'])
        self.assertIn('LOTE_FANTASMA', res['error'])
        self.assertIn('não pertence', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value={'ok': True, 'lotes': [], 'total_atendido': 0.0})
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_sem_tgfvar_origem_bloqueia_modo_nota(self, _mp, _ml):
        """Nota órfã (sem TGFVAR) não pode usar modo "a partir de nota"."""
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 244, 'codprod': 21, 'codvol': 'KG',
            'nunota_origem_nota': 111971, 'sequencia_nota': 1,
            'lotes_avaria': [{'codagregacao': 'X', 'qtd': 10.0}],
        })
        self.assertFalse(res['ok'])
        self.assertIn('não tem lotes rastreáveis', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT)
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_modo_nota_sem_nunota_ou_sequencia_bloqueia(self, _mp, _ml):
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        # sem nunota_origem_nota
        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 244, 'codprod': 21, 'codvol': 'KG',
            'sequencia_nota': 1,
            'lotes_avaria': [{'codagregacao': 'LOTE_A', 'qtd': 50.0}],
        })
        self.assertFalse(res['ok'])
        self.assertIn('nunota_origem_nota', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco',
           return_value={'ok': True, 'nunota': 300000})
    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_saldo_insuficiente_em_um_dos_lotes_bloqueia(
            self, _mp, mock_conn, _ml, _mcab):
        """Se 1 lote não tem saldo, falha tudo (atomicidade)."""
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco
        conn_obj = MagicMock()
        cur_mock = MagicMock()
        # Primeira query retorna saldo OK (100), segunda retorna 0
        cur_mock.fetchone.side_effect = [(100.0,), (0.0,)]
        conn_obj.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_obj

        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 244, 'codprod': 21, 'codvol': 'KG',
            'nunota_origem_nota': 111971, 'sequencia_nota': 1,
            'lotes_avaria': [
                {'codagregacao': 'LOTE_A', 'qtd': 50.0},  # OK
                {'codagregacao': 'LOTE_B', 'qtd': 30.0},  # sem saldo
            ],
        })
        self.assertFalse(res['ok'])
        self.assertIn('sem saldo', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 250.0})
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco',
           return_value={'ok': True, 'nunota': 300000})
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_modo_antigo_continua_funcionando_regressao(
            self, _mp, mock_conn, _mcab, mock_ite, _mr):
        """Backward-compat: payload antigo (codagregacao + qtdneg, sem
        lotes_avaria) cria 1 TGFITE como antes."""
        from sankhya_integration.services.oracle_conn import criar_avaria_top30_banco

        conn_obj = MagicMock()
        self._mock_cursor_saldo(conn_obj, saldo=200.0)
        mock_conn.return_value.__enter__.return_value = conn_obj
        mock_ite.side_effect = self._montar_mocks(conn_obj)

        res = criar_avaria_top30_banco({
            'codemp': 10, 'codparc': 244, 'codprod': 21,
            'codagregacao': 'LOTE_X', 'qtdneg': 50.0,
            'codvol': 'KG', 'vlrunit': 5.0,
        })
        self.assertTrue(res['ok'], msg=res.get('error'))
        self.assertEqual(mock_ite.call_count, 1)
        self.assertEqual(mock_ite.call_args_list[0].args[0]['CODAGREGACAO'], 'LOTE_X')
        self.assertEqual(mock_ite.call_args_list[0].args[0]['QTDNEG'], 50.0)


class CriarDevolucaoServiceTest(TestCase):
    """Testa direto a função criar_devolucao_top36_banco."""

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=False)
    def test_escrita_desabilitada(self, _mp):
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({})
        self.assertFalse(res['ok'])

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_sem_nunota_origem(self, _mp):
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({'itens': [{'sequencia_origem': 1, 'qtd_devolver': 1.0}]})
        self.assertFalse(res['ok'])
        self.assertIn('nunota_origem', res['error'])

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_itens_vazios(self, _mp):
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({'nunota_origem': 111971, 'itens': []})
        self.assertFalse(res['ok'])
        self.assertIn('item', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value={'ok': False, 'error': 'Nota não encontrada'})
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_nota_origem_inexistente(self, _mp, _mock_consulta):
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({
            'nunota_origem': 99999,
            'itens': [{'sequencia_origem': 1, 'qtd_devolver': 1.0}],
        })
        self.assertFalse(res['ok'])
        self.assertIn('não encontrada', res['error'])

    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value={
               'ok': True,
               'cabecalho': {'nunota': 111971, 'numnota': 6266,
                             'codemp': 10, 'codparc': 244,
                             'codtipoper': 35, 'statusnota': 'L',
                             'vlrnota': 100.0, 'codtipvenda': 2,
                             'dtneg': '2026-05-09', 'nomeparc': 'CLI'},
               'itens': [{'sequencia': 1, 'codprod': 21, 'descrprod': 'TOMATE',
                          'codagregacao': 'L1', 'codvol': 'KG',
                          'qtdneg': 10.0, 'vlrunit': 5.0, 'vlrtot': 50.0,
                          'qtd_ja_devolvida': 8.0, 'qtd_devolvivel': 2.0}],
           })
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtd_excessiva_bloqueada(self, _mp, _mock_consulta):
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{'sequencia_origem': 1, 'qtd_devolver': 5.0}],
        })
        self.assertFalse(res['ok'])
        self.assertIn('excessiva', res['error'].lower())
        self.assertIn('2.', res['error'])  # devolvível formatado


class CriarDevolucaoSplitLotesServiceTest(TestCase):
    """B1 (Mai/2026) — formato novo `lotes_devolver` no payload.

    Cobre os cenários onde 1 SEQ da nota TOP 35/37 veio de N SEQs do pedido
    com lotes diferentes (SPLIT). O backend recebe a divisão pronta do
    frontend, valida via navegação inversa TGFVAR e cria N TGFITE TOP 36 +
    N TGFVAR (todas apontando pro SEQ da nota — semântica Sankhya).
    """

    # Helper compartilhado pelos tests de sucesso — mocka todo o pipeline de
    # escrita pra capturar o INSERT TGFVAR.
    NOTA_PADRAO = {
        'ok': True,
        'cabecalho': {'nunota': 111971, 'numnota': 6266,
                      'codemp': 10, 'codparc': 244,
                      'codtipoper': 35, 'statusnota': 'L',
                      'vlrnota': 5000.0, 'codtipvenda': 2,
                      'dtneg': '2026-05-09', 'nomeparc': 'CLIENTE X'},
        # Item consolidado: 1000kg de TOMATE
        'itens': [{'sequencia': 1, 'codprod': 21, 'descrprod': 'TOMATE',
                   'codagregacao': '', 'codvol': 'KG',
                   'qtdneg': 1000.0, 'vlrunit': 5.0, 'vlrtot': 5000.0,
                   'qtd_ja_devolvida': 0.0, 'qtd_devolvivel': 1000.0}],
    }
    LOTES_SPLIT_PADRAO = {
        'ok': True,
        'lotes': [
            {'seq_pedido': 5, 'codagregacao': 'LOTE_A',
             'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
             'nunota_pedido': 111900},
            {'seq_pedido': 6, 'codagregacao': 'LOTE_B',
             'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
             'nunota_pedido': 111900},
        ],
        'total_atendido': 1000.0,
    }

    def _montar_mocks(self, _conn_mock, seq_inicial=10):
        """Devolve side_effect pra inserir_item_nota_banco — incrementa
        SEQUENCIA a cada chamada simulando o INSERT real."""
        seq_counter = {'v': seq_inicial - 1}

        def _ins_ite(_payload, **_kwargs):
            seq_counter['v'] += 1
            return {'ok': True, 'sequencia': seq_counter['v']}

        return _ins_ite

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 1500.0})
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco',
           return_value={'ok': True, 'nunota': 200000})
    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value=NOTA_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_split_2_lotes_cria_n_tgfite_com_codagregacao_certo(
            self, _mp, mock_conn, _mn, _ml, _mc, mock_ite, _mr):
        """Operador divide 300kg entre LOTE_A (150) e LOTE_B (150)."""
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco

        cur_mock = MagicMock()
        conn_obj = MagicMock()
        conn_obj.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_obj

        mock_ite.side_effect = self._montar_mocks(conn_obj)

        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{
                'sequencia_origem': 1,
                'lotes_devolver': [
                    {'codagregacao': 'LOTE_A', 'qtd': 150.0},
                    {'codagregacao': 'LOTE_B', 'qtd': 150.0},
                ],
            }],
        })

        self.assertTrue(res['ok'], msg=res.get('error'))
        self.assertEqual(res['nunota'], 200000)
        # 2 TGFITE criados (1 por lote)
        self.assertEqual(mock_ite.call_count, 2)
        # CODAGREGACAO de cada TGFITE bate com o lote escolhido
        codagregs_inseridos = [
            call.args[0]['CODAGREGACAO']
            for call in mock_ite.call_args_list
        ]
        self.assertEqual(set(codagregs_inseridos), {'LOTE_A', 'LOTE_B'})
        # Qtds batem
        qtds_inseridas = [
            call.args[0]['QTDNEG']
            for call in mock_ite.call_args_list
        ]
        self.assertEqual(sum(qtds_inseridas), 300.0)

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 1500.0})
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco',
           return_value={'ok': True, 'nunota': 200000})
    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value=NOTA_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_tgfvar_sequenciaorig_aponta_pra_seq_da_nota_nao_do_pedido(
            self, _mp, mock_conn, _mn, _ml, _mc, mock_ite, _mr):
        """Semântica TGFVAR: SEQUENCIAORIG = SEQ da nota (não SEQ_pedido).

        Crítico: a trava `consultar_devolucoes_anteriores_de_nota` agrupa
        por SEQUENCIAORIG esperando o SEQ da nota — se aqui apontasse pro
        SEQ do pedido, a trava de devolução excessiva quebraria.
        """
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco

        cur_mock = MagicMock()
        conn_obj = MagicMock()
        conn_obj.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_obj
        mock_ite.side_effect = self._montar_mocks(conn_obj)

        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{
                'sequencia_origem': 1,
                'lotes_devolver': [
                    {'codagregacao': 'LOTE_A', 'qtd': 100.0},
                    {'codagregacao': 'LOTE_B', 'qtd': 200.0},
                ],
            }],
        })
        self.assertTrue(res['ok'], msg=res.get('error'))

        # Inspeciona as chamadas execute (INSERT TGFVAR)
        chamadas_tgfvar = [
            call for call in cur_mock.execute.call_args_list
            if 'INSERT INTO TGFVAR' in (call.args[0] if call.args else '')
        ]
        self.assertEqual(len(chamadas_tgfvar), 2)
        for chamada in chamadas_tgfvar:
            params = chamada.args[1]
            # SEQUENCIAORIG (`so`) = 1 (SEQ da nota), NUNCA 5 ou 6 (SEQs do pedido)
            self.assertEqual(params['so'], 1,
                f'TGFVAR.SEQUENCIAORIG deve ser SEQ da nota (1), recebeu {params["so"]}')
            self.assertEqual(params['no'], 111971,
                'TGFVAR.NUNOTAORIG deve ser NUNOTA da nota TOP 35')

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value=NOTA_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_lote_inexistente_no_pedido_bloqueia(self, _mp, _mn, _ml):
        """Operador informou CODAGREGACAO que não pertence ao pedido origem."""
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{
                'sequencia_origem': 1,
                'lotes_devolver': [
                    {'codagregacao': 'LOTE_FANTASMA', 'qtd': 100.0},
                ],
            }],
        })
        self.assertFalse(res['ok'])
        self.assertIn('LOTE_FANTASMA', res['error'])
        self.assertIn('não pertence', res['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value=NOTA_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_soma_lotes_excede_devolvivel_bloqueia(self, _mp, _mn, _ml):
        """Soma das qtds informadas > saldo devolvível do item (1000kg)."""
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{
                'sequencia_origem': 1,
                'lotes_devolver': [
                    {'codagregacao': 'LOTE_A', 'qtd': 700.0},
                    {'codagregacao': 'LOTE_B', 'qtd': 500.0},  # soma 1200 > 1000
                ],
            }],
        })
        self.assertFalse(res['ok'])
        self.assertIn('excede saldo devolvível', res['error'].lower())
        self.assertIn('1200', res['error'].replace('.', '').replace(',', ''))

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value=LOTES_SPLIT_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value=NOTA_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_codagregacao_vazio_bloqueia(self, _mp, _mn, _ml):
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco
        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{
                'sequencia_origem': 1,
                'lotes_devolver': [
                    {'codagregacao': '', 'qtd': 100.0},
                ],
            }],
        })
        self.assertFalse(res['ok'])
        self.assertIn('CODAGREGACAO', res['error'])

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco',
           return_value={'ok': True, 'vlrnota': 500.0})
    @patch('sankhya_integration.services.oracle_conn.inserir_item_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.inserir_cabecalho_nota_banco',
           return_value={'ok': True, 'nunota': 200000})
    @patch('sankhya_integration.services.oracle_conn.consultar_nota_para_devolucao',
           return_value=NOTA_PADRAO)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_formato_antigo_continua_funcionando_regressao(
            self, _mp, mock_conn, _mn, _mcab, mock_ite, _mr):
        """Backward-compat: payload antigo (`qtd_devolver` simples, sem
        `lotes_devolver`) deve criar 1 TGFITE como antes."""
        from sankhya_integration.services.oracle_conn import criar_devolucao_top36_banco

        cur_mock = MagicMock()
        conn_obj = MagicMock()
        conn_obj.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_obj
        mock_ite.side_effect = self._montar_mocks(conn_obj)

        res = criar_devolucao_top36_banco({
            'nunota_origem': 111971,
            'itens': [{'sequencia_origem': 1, 'qtd_devolver': 100.0}],
        })
        self.assertTrue(res['ok'], msg=res.get('error'))
        self.assertEqual(mock_ite.call_count, 1)
        chamadas_tgfvar = [
            call for call in cur_mock.execute.call_args_list
            if 'INSERT INTO TGFVAR' in (call.args[0] if call.args else '')
        ]
        self.assertEqual(len(chamadas_tgfvar), 1)
        # SEQUENCIAORIG continua igual ao SEQ da nota (compatível com a trava)
        self.assertEqual(chamadas_tgfvar[0].args[1]['so'], 1)


class ConsultarLotesOrigemDeSeqNotaServiceTest(TestCase):
    """Navegação inversa TGFVAR — Fase 1 (leitura pura).

    Cenário central: nota TOP 35 consolidou 2 SEQs do pedido com lotes
    diferentes (SPLIT). A função deve devolver os 2 lotes na ordem do
    SEQUENCIAORIG.
    """

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_split_2_lotes(self, mock_conn):
        from sankhya_integration.services.oracle_conn import (
            consultar_lotes_origem_de_seq_nota,
        )
        cur_mock = MagicMock()
        # (SEQUENCIAORIG, CODAGREGACAO, QTDNEG_PEDIDO, QTDATENDIDA, NUNOTAORIG)
        cur_mock.fetchall.return_value = [
            (5, 'LOTE_A', 500.0, 500.0, 111900),
            (6, 'LOTE_B', 500.0, 500.0, 111900),
        ]
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = consultar_lotes_origem_de_seq_nota(111971, 1)
        self.assertTrue(res['ok'])
        self.assertEqual(len(res['lotes']), 2)
        self.assertEqual(res['lotes'][0]['seq_pedido'], 5)
        self.assertEqual(res['lotes'][0]['codagregacao'], 'LOTE_A')
        self.assertEqual(res['lotes'][0]['qtd_atendida'], 500.0)
        self.assertEqual(res['lotes'][1]['codagregacao'], 'LOTE_B')
        self.assertEqual(res['total_atendido'], 1000.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sem_tgfvar_par_retorna_vazio(self, mock_conn):
        """Nota órfã (sem TGFVAR ligando a pedido) → lista vazia, ok=True."""
        from sankhya_integration.services.oracle_conn import (
            consultar_lotes_origem_de_seq_nota,
        )
        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = []
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = consultar_lotes_origem_de_seq_nota(111971, 1)
        self.assertTrue(res['ok'])
        self.assertEqual(res['lotes'], [])
        self.assertEqual(res['total_atendido'], 0.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_codagregacao_null_no_pedido(self, mock_conn):
        """SEQ do pedido sem CODAGREGACAO (item ainda não vinculado quando
        faturou? cenário raro mas possível) — entra com string vazia."""
        from sankhya_integration.services.oracle_conn import (
            consultar_lotes_origem_de_seq_nota,
        )
        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = [
            (5, None, 500.0, 500.0, 111900),
        ]
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = consultar_lotes_origem_de_seq_nota(111971, 1)
        self.assertTrue(res['ok'])
        self.assertEqual(res['lotes'][0]['codagregacao'], '')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle',
           side_effect=Exception('ORA-12345 boom'))
    def test_falha_oracle_retorna_lista_vazia(self, _mp):
        from sankhya_integration.services.oracle_conn import (
            consultar_lotes_origem_de_seq_nota,
        )
        res = consultar_lotes_origem_de_seq_nota(111971, 1)
        self.assertFalse(res['ok'])
        self.assertEqual(res['lotes'], [])
        self.assertEqual(res['total_atendido'], 0.0)


class ConsultarNotaParaDevolucaoComLotesOrigemTest(TestCase):
    """Confirma que consultar_nota_para_devolucao agora propaga lotes_origem
    no payload de cada item — Fase 1 da navegação inversa TGFVAR."""

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           return_value={'ok': True,
                         'lotes': [
                             {'seq_pedido': 5, 'codagregacao': 'LOTE_A',
                              'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
                              'nunota_pedido': 111900},
                             {'seq_pedido': 6, 'codagregacao': 'LOTE_B',
                              'qtdneg_pedido': 500.0, 'qtd_atendida': 500.0,
                              'nunota_pedido': 111900},
                         ],
                         'total_atendido': 1000.0})
    @patch('sankhya_integration.services.oracle_conn.consultar_devolucoes_anteriores_de_nota',
           return_value={'ok': True, 'por_sequencia': {}})
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_item_recebe_lotes_origem(self, mock_conn, _mdev, _mlotes):
        from sankhya_integration.services.oracle_conn import (
            consultar_nota_para_devolucao,
        )
        cur_mock = MagicMock()
        # 1) Cabeçalho
        # 2) Itens (1 item de TOMATE 1000 kg consolidando 2 lotes do pedido)
        cur_mock.fetchone.return_value = (
            111971, 6266, 10, 244,
            35, 'L', 5000.0, 2,
            '2026-05-09',
            'CLIENTE X',
        )
        cur_mock.fetchall.return_value = [
            # SEQUENCIA, CODPROD, DESCRPROD, CODAGREGACAO, CODVOL,
            # QTDNEG, VLRUNIT, VLRTOT
            (1, 21, 'TOMATE', '', 'KG', 1000.0, 5.0, 5000.0),
        ]
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = consultar_nota_para_devolucao(111971)
        self.assertTrue(res['ok'])
        self.assertEqual(len(res['itens']), 1)
        item = res['itens'][0]
        self.assertIn('lotes_origem', item)
        self.assertEqual(len(item['lotes_origem']), 2)
        self.assertEqual(item['lotes_origem'][0]['codagregacao'], 'LOTE_A')
        self.assertEqual(item['lotes_origem'][1]['codagregacao'], 'LOTE_B')

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_origem_de_seq_nota',
           side_effect=Exception('falha inesperada'))
    @patch('sankhya_integration.services.oracle_conn.consultar_devolucoes_anteriores_de_nota',
           return_value={'ok': True, 'por_sequencia': {}})
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_tolerante_a_falha_em_lotes_origem(self, mock_conn, _mdev, _mlotes):
        """Falha em consultar_lotes_origem_de_seq_nota não derruba a leitura
        principal — item segue com lotes_origem=[] como fallback."""
        from sankhya_integration.services.oracle_conn import (
            consultar_nota_para_devolucao,
        )
        cur_mock = MagicMock()
        cur_mock.fetchone.return_value = (
            111971, 6266, 10, 244, 35, 'L', 5000.0, 2,
            '2026-05-09', 'CLIENTE X',
        )
        cur_mock.fetchall.return_value = [
            (1, 21, 'TOMATE', 'L_X', 'KG', 1000.0, 5.0, 5000.0),
        ]
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = consultar_nota_para_devolucao(111971)
        self.assertTrue(res['ok'])
        # Fallback: lotes_origem fica vazio, mas o item continua acessível
        self.assertEqual(res['itens'][0]['lotes_origem'], [])
        self.assertEqual(res['itens'][0]['codagregacao'], 'L_X')


class HistoricoLoteServiceTest(TestCase):
    """Testa direto a função obter_historico_lote."""

    def test_lote_vazio(self):
        from sankhya_integration.services.oracle_conn import obter_historico_lote
        res = obter_historico_lote('')
        self.assertFalse(res['ok'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_inexistente_retorna_timeline_vazia(self, mock_conn):
        from sankhya_integration.services.oracle_conn import obter_historico_lote
        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = []
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = obter_historico_lote('NAO_EXISTE')
        self.assertTrue(res['ok'])
        self.assertEqual(res['timeline'], [])
        self.assertEqual(res['lote'], 'NAO_EXISTE')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_com_eventos(self, mock_conn):
        from sankhya_integration.services.oracle_conn import obter_historico_lote
        # 2 eventos: TOP 11 (compra) → TOP 35 (venda)
        cur_mock = MagicMock()
        cur_mock.fetchall.return_value = [
            (100, 5000, 11, 'L', '2026-04-01', 100, 'FOR.', 358,
             'TOMATE', 1000.0, 'KG', 3.0, 3000.0, 1, 0.0),
            (200, 6000, 35, 'L', '2026-05-01', 500, 'CLI.', 358,
             'TOMATE', 200.0, 'KG', 5.0, 1000.0, 1, 0.0),
        ]
        conn_mock = MagicMock()
        conn_mock.cursor.return_value = cur_mock
        mock_conn.return_value.__enter__.return_value = conn_mock

        res = obter_historico_lote('12345S01D260507')
        self.assertTrue(res['ok'])
        self.assertEqual(len(res['timeline']), 2)
        self.assertEqual(res['timeline'][0]['top_nome'], 'Compra (Entrada)')
        self.assertTrue(res['timeline'][0]['is_entrada'])
        self.assertEqual(res['timeline'][1]['top_nome'], 'Venda com NFe')
        self.assertTrue(res['timeline'][1]['is_baixa'])


# ---------------------------------------------------------------------------
# Helper compartilhado adicional
# ---------------------------------------------------------------------------
