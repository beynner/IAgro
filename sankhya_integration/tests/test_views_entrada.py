"""
Testes do módulo de Entrada (Portal de Compras / TOP 11).

Todas as chamadas ao Oracle são mockadas. Nenhum código de produção é alterado.
Os testes documentam o comportamento atual do sistema.
"""
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login_session(client, grupos=None):
    """Injeta sessão autenticada com os grupos informados."""
    session = client.session
    session['codusu'] = 1
    session['nomeusu'] = 'Teste'
    session['nome'] = 'Teste'
    session['grupos'] = grupos or ['1']
    session.save()


# ---------------------------------------------------------------------------
# Controle de acesso — view_portal_entradas
# ---------------------------------------------------------------------------

class PortalEntradasAcessoTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_sem_sessao_redireciona_para_home(self):
        """Acesso sem login deve redirecionar para home (exige_grupo)."""
        response = self.client.get(reverse('compras_portal'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_grupo_sem_permissao_redireciona_para_home(self):
        """Usuário com grupo Comercial (9) não tem acesso à Entrada."""
        _login_session(self.client, grupos=['9'])
        response = self.client.get(reverse('compras_portal'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    @patch('sankhya_integration.views.listar_notas_compra_paginado', return_value=[])
    @patch('sankhya_integration.views.listar_itens_por_nota', return_value=[])
    @patch('sankhya_integration.views.ORACLE_DISPONIVEL', True)
    def test_grupo_operacao_acessa_portal(self, mock_itens, mock_notas):
        """Grupo Operação (8) deve acessar o portal de entradas."""
        _login_session(self.client, grupos=['8'])
        response = self.client.get(reverse('compras_portal'))
        self.assertEqual(response.status_code, 200)

    @patch('sankhya_integration.views.listar_notas_compra_paginado', return_value=[])
    @patch('sankhya_integration.views.listar_itens_por_nota', return_value=[])
    @patch('sankhya_integration.views.ORACLE_DISPONIVEL', True)
    def test_diretoria_acessa_portal(self, mock_itens, mock_notas):
        """Grupo Diretoria (1) deve ter acesso irrestrito ao portal."""
        _login_session(self.client, grupos=['1'])
        response = self.client.get(reverse('compras_portal'))
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Endpoint /health/
# ---------------------------------------------------------------------------

class HealthEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()

    @patch('sankhya_integration.views.ORACLE_DISPONIVEL', False)
    def test_health_sem_oracle_retorna_json(self):
        """Health deve retornar JSON mesmo sem Oracle disponível."""
        response = self.client.get(reverse('sankhya_health'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('oracle_import', data)
        self.assertFalse(data['oracle_import'])

    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.ORACLE_DISPONIVEL', True)
    def test_health_com_oracle_ok_retorna_db_ping_true(self, mock_conn_ctx):
        """Health deve retornar db_ping=True quando Oracle responde."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        response = self.client.get(reverse('sankhya_health'))
        data = json.loads(response.content)
        self.assertTrue(data.get('db_ping'))

    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.ORACLE_DISPONIVEL', True)
    def test_health_com_oracle_falho_retorna_db_ping_false(self, mock_conn_ctx):
        """Health deve retornar db_ping=False quando Oracle lança exceção."""
        mock_conn_ctx.return_value.__enter__ = MagicMock(side_effect=Exception("timeout"))
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        response = self.client.get(reverse('sankhya_health'))
        data = json.loads(response.content)
        self.assertFalse(data.get('db_ping'))
        self.assertIn('error', data)


# ---------------------------------------------------------------------------
# API de listagem de itens da nota — item/list/
# ---------------------------------------------------------------------------

class ListarItensNotaTest(TestCase):
    """
    A view api_listar_itens_nota trabalha com tuplas retornadas pelo Oracle
    (não dicts). A ordem das colunas é:
      r[0]=lote, r[1]=seq, r[2]=codprod, r[3]=descr, r[4]=codvol,
      r[5]=qtdneg, r[6]=peso, r[7]=vlu, r[8]=vlt, ..., r[11]=qtdconferida
    """

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    def test_sem_nunota_retorna_400(self):
        """item/list/ sem nunota deve retornar 400 — comportamento atual da view."""
        response = self.client.get(reverse('item_list'))
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data.get('ok'))

    @patch('sankhya_integration.views.listar_itens_por_nota')
    def test_com_nunota_valido_retorna_itens(self, mock_fn):
        """item/list/ com nunota válido deve retornar lista de itens."""
        # Tupla com 12 colunas no formato que a view espera
        mock_fn.return_value = [
            ('LOTE1', 1, 100, 'Tomate Italiano', 'CX', 10.0, 25.0, 5.0, 50.0, None, None, 10.0)
        ]
        response = self.client.get(reverse('item_list'), {'nunota': '999'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data.get('items', [])), 1)  # chave é 'items' (inglês)
        mock_fn.assert_called_once_with(999)

    @patch('sankhya_integration.views.listar_itens_por_nota', return_value=[])
    def test_nunota_sem_itens_retorna_lista_vazia(self, mock_fn):
        """Nota existente sem itens deve retornar lista vazia com status 200."""
        response = self.client.get(reverse('item_list'), {'nunota': '123'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data.get('items'), [])  # chave é 'items' (inglês)


# ---------------------------------------------------------------------------
# Funções utilitárias de conversão
# ---------------------------------------------------------------------------

class ConversorIntTest(TestCase):

    def _fn(self, val, default=None):
        from sankhya_integration.views import _converter_para_inteiro
        return _converter_para_inteiro(val, default)

    def test_inteiro_direto(self):
        self.assertEqual(self._fn(42), 42)

    def test_string_numerica(self):
        self.assertEqual(self._fn('7'), 7)

    def test_none_retorna_default(self):
        self.assertIsNone(self._fn(None))
        self.assertEqual(self._fn(None, default=0), 0)

    def test_string_vazia_retorna_default(self):
        self.assertIsNone(self._fn(''))

    def test_string_none_literal_retorna_default(self):
        self.assertIsNone(self._fn('None'))

    def test_lista_pega_primeiro_item(self):
        self.assertEqual(self._fn([3, 5]), 3)

    def test_valor_invalido_retorna_default(self):
        self.assertIsNone(self._fn('abc'))


class ConversorFloatTest(TestCase):

    def _fn(self, val, default=None):
        from sankhya_integration.views import _converter_para_float
        return _converter_para_float(val, default)

    def test_float_direto(self):
        self.assertAlmostEqual(self._fn(3.14), 3.14)

    def test_string_float(self):
        self.assertAlmostEqual(self._fn('2.5'), 2.5)

    def test_none_retorna_default(self):
        self.assertIsNone(self._fn(None))

    def test_valor_invalido_retorna_default(self):
        self.assertIsNone(self._fn('xyz'))
