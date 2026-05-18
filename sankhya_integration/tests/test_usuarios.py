"""Tests do módulo Usuários + Hub de Configurações (Mai/2026).

Cobre Cat A (leituras + página + endpoints stub de Cat B):
  - AcessoUsuariosTest
  - AcessoConfiguracoesHubTest
  - ListarUsuariosServiceTest
  - ConsultarUsuarioDetalheServiceTest
  - ConsultarGruposDisponiveisServiceTest
  - ApiUsuariosListarViewTest
  - ApiUsuariosDetalheViewTest
  - ApiUsuariosGruposViewTest
  - StubsCatBTest  (B1-B6 retornam 501 com pendente_cat_b=true)
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from django.test import TestCase, Client


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 1
    session['nomeusu'] = 'Teste'
    session['nome']    = 'Teste'
    session['grupos']  = grupos or ['1']
    session.save()


# --------------------------------------------------------------------------
# AcessoUsuariosTest
# --------------------------------------------------------------------------

class AcessoUsuariosTest(TestCase):
    """Apenas grupos 1 (Diretoria) e 6 (Suporte) podem entrar."""

    def setUp(self):
        self.client = Client()
        self.url = '/sankhya/usuarios/'

    def test_diretoria_acessa(self):
        _login_session(self.client, grupos=['1'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_suporte_acessa(self):
        _login_session(self.client, grupos=['6'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_comercial_nao_acessa(self):
        _login_session(self.client, grupos=['9'])
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))

    def test_administrativo_nao_acessa(self):
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))

    def test_sem_sessao_nao_acessa(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))


# --------------------------------------------------------------------------
# AcessoConfiguracoesHubTest — Hub de configurações no header (engrenagem)
# --------------------------------------------------------------------------

class AcessoConfiguracoesHubTest(TestCase):
    """Hub /sankhya/configuracoes/ — só Diretoria (1) e Suporte (6) entram.
    Conteúdo: card "Usuários" (por enquanto único)."""

    def setUp(self):
        self.client = Client()
        self.url = '/sankhya/configuracoes/'

    def test_diretoria_acessa(self):
        _login_session(self.client, grupos=['1'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        # Card Usuários renderizado
        self.assertContains(resp, '/sankhya/usuarios/')
        self.assertContains(resp, 'Usuários')

    def test_hub_inclui_card_auditoria(self):
        """Auditoria foi movida da sidebar pro hub de Configurações."""
        _login_session(self.client, grupos=['1'])
        resp = self.client.get(self.url)
        self.assertContains(resp, '/sankhya/auditoria/')
        self.assertContains(resp, 'Auditoria')

    def test_suporte_acessa(self):
        _login_session(self.client, grupos=['6'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_administrativo_nao_acessa(self):
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))

    def test_comercial_nao_acessa(self):
        _login_session(self.client, grupos=['9'])
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))

    def test_sem_sessao_nao_acessa(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))


# --------------------------------------------------------------------------
# Service listar_usuarios
# --------------------------------------------------------------------------

class ListarUsuariosServiceTest(TestCase):
    """Cobertura SQL + tratamento de filtros."""

    def _mock_cursor(self, mock_obter, fetchall, fetchone=None):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall
        if fetchone is not None:
            cursor.fetchone.return_value = fetchone
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lista_basica_sem_filtros(self, mock_obter):
        """Sem filtros, retorna ativos paginados; default apenas_ativos=True."""
        from sankhya_integration.services.oracle_conn import listar_usuarios
        cursor = self._mock_cursor(
            mock_obter,
            fetchall=[
                (10, 'ANDRE', 'ANDRE SILVA', 'a@a.com', '12345678901', 1, 'DIRETORIA',
                 dt.datetime(2099, 1, 1), 'S', 2),
                (20, 'BIA',   'BIA',        '',        '',           8, 'IAGRO_PACKING',
                 None, 'S', 0),
            ],
            fetchone=(2,),
        )
        result = listar_usuarios()
        self.assertEqual(result['total'], 2)
        self.assertEqual(len(result['usuarios']), 2)
        u1 = result['usuarios'][0]
        self.assertEqual(u1['codusu'], 10)
        self.assertEqual(u1['nomeusu'], 'ANDRE')
        self.assertTrue(u1['ativo'])
        self.assertEqual(u1['grupos_extras'], 2)
        # Filtro de ativos aplicado por padrão
        sql_executado = cursor.execute.call_args_list[0][0][0]
        self.assertIn('DTLIMACESSO IS NULL', sql_executado)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_filtro_busca_aplica_upper_like(self, mock_obter):
        from sankhya_integration.services.oracle_conn import listar_usuarios
        cursor = self._mock_cursor(mock_obter, fetchall=[], fetchone=(0,))
        listar_usuarios(filtros={'busca': 'andre'})
        binds = cursor.execute.call_args_list[0][0][1]
        self.assertIn('busca', binds)
        self.assertEqual(binds['busca'], '%ANDRE%')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_filtro_codgrupo_int(self, mock_obter):
        from sankhya_integration.services.oracle_conn import listar_usuarios
        cursor = self._mock_cursor(mock_obter, fetchall=[], fetchone=(0,))
        listar_usuarios(filtros={'codgrupo': '8'})
        binds = cursor.execute.call_args_list[0][0][1]
        self.assertEqual(binds.get('codgrupo'), 8)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_filtro_apenas_inativos_inverte_where(self, mock_obter):
        from sankhya_integration.services.oracle_conn import listar_usuarios
        cursor = self._mock_cursor(mock_obter, fetchall=[], fetchone=(0,))
        listar_usuarios(filtros={'apenas_inativos': True, 'apenas_ativos': False})
        sql = cursor.execute.call_args_list[0][0][0]
        self.assertIn('DTLIMACESSO IS NOT NULL', sql)
        self.assertIn('< TRUNC(SYSDATE)', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_paginacao(self, mock_obter):
        from sankhya_integration.services.oracle_conn import listar_usuarios
        cursor = self._mock_cursor(mock_obter, fetchall=[], fetchone=(0,))
        listar_usuarios(limite=25, offset=50)
        # Segundo execute é o de paginação
        binds_pag = cursor.execute.call_args_list[1][0][1]
        self.assertEqual(binds_pag['ini'], 51)
        self.assertEqual(binds_pag['fim'], 75)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_vazio(self, mock_obter):
        from sankhya_integration.services.oracle_conn import listar_usuarios
        mock_obter.side_effect = Exception('boom')
        result = listar_usuarios()
        self.assertEqual(result, {'usuarios': [], 'total': 0, 'limite': 50, 'offset': 0})


# --------------------------------------------------------------------------
# Service consultar_usuario_detalhe
# --------------------------------------------------------------------------

class ConsultarUsuarioDetalheServiceTest(TestCase):

    def _mock(self, mock_obter, cab, extras):
        cursor = MagicMock()
        cursor.fetchone.return_value = cab
        cursor.fetchall.return_value = extras
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_usuario_existente(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_usuario_detalhe
        self._mock(mock_obter,
            cab=(10, 'ANDRE', 'ANDRE SILVA', 'a@a.com', '12345',
                 1, 'DIRETORIA',
                 None, dt.datetime(2026, 5, 16, 9, 30), dt.datetime(2026, 1, 1),
                 'S', 'S'),
            extras=[
                (100, 6, 'SUPORTE', dt.datetime(2025, 1, 1)),
                (101, 8, 'IAGRO_PACKING', dt.datetime(2025, 2, 1)),
            ],
        )
        result = consultar_usuario_detalhe(10)
        self.assertEqual(result['codusu'], 10)
        self.assertEqual(result['nomeusu'], 'ANDRE')
        self.assertTrue(result['tem_senha'])
        self.assertTrue(result['ativo'])
        # 2 extras vieram do banco; nenhum é o principal (CODGRUPO=1), então
        # ambos passam pro frontend
        self.assertEqual(len(result['grupos_extras']), 2)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_principal_filtrado_dos_extras(self, mock_obter):
        """Se TSIGPU tem entrada com o mesmo CODGRUPO do principal, deve ser
        omitida pra não duplicar na UI."""
        from sankhya_integration.services.oracle_conn import consultar_usuario_detalhe
        self._mock(mock_obter,
            cab=(10, 'X', 'X', '', '', 8, 'IAGRO_PACKING',
                 None, None, None, 'S', 'S'),
            extras=[
                (200, 8, 'IAGRO_PACKING', dt.datetime(2024, 1, 1)),  # mesmo do principal
                (201, 6, 'SUPORTE',       dt.datetime(2025, 1, 1)),
            ],
        )
        result = consultar_usuario_detalhe(10)
        self.assertEqual(len(result['grupos_extras']), 1)
        self.assertEqual(result['grupos_extras'][0]['codgrupo'], 6)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_usuario_inexistente_retorna_none(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_usuario_detalhe
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        result = consultar_usuario_detalhe(999)
        self.assertIsNone(result)

    def test_codusu_invalido_retorna_none(self):
        from sankhya_integration.services.oracle_conn import consultar_usuario_detalhe
        self.assertIsNone(consultar_usuario_detalhe('abc'))
        self.assertIsNone(consultar_usuario_detalhe(None))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sem_senha_quando_interno_null(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_usuario_detalhe
        self._mock(mock_obter,
            cab=(10, 'X', 'X', '', '', 8, '?', None, None, None, 'N', 'S'),
            extras=[],
        )
        result = consultar_usuario_detalhe(10)
        self.assertFalse(result['tem_senha'])


# --------------------------------------------------------------------------
# Service consultar_grupos_disponiveis
# --------------------------------------------------------------------------

class ConsultarGruposDisponiveisServiceTest(TestCase):

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lista_grupos_ativos(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_grupos_disponiveis
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (1, 'DIRETORIA', ''),
            (6, 'SUPORTE',   ''),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        result = consultar_grupos_disponiveis()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['codgrupo'], 1)
        self.assertEqual(result[0]['nomegrupo'], 'DIRETORIA')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fallback_sem_coluna_descricao(self, mock_obter):
        """Se TSIGRU não tiver coluna DESCRICAO em alguma instalação, faz
        fallback pra SELECT sem DESCRICAO."""
        from sankhya_integration.services.oracle_conn import consultar_grupos_disponiveis

        chamadas = []

        def execute_lado_efeito(sql, *args, **kw):
            chamadas.append(sql)
            if 'DESCRICAO' in sql.upper() and len(chamadas) == 1:
                raise Exception('ORA-00904: invalid identifier')

        cursor = MagicMock()
        cursor.execute.side_effect = execute_lado_efeito
        cursor.fetchall.return_value = [(1, 'DIRETORIA'), (6, 'SUPORTE')]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn

        result = consultar_grupos_disponiveis()
        # Fallback executou
        self.assertGreaterEqual(len(chamadas), 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['descricao'], '')


# --------------------------------------------------------------------------
# Endpoints REST de leitura
# --------------------------------------------------------------------------

class ApiUsuariosListarViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['6'])

    @patch('sankhya_integration.views.listar_usuarios')
    def test_listagem_simples(self, mock_listar):
        mock_listar.return_value = {
            'usuarios': [{'codusu': 1, 'nomeusu': 'X'}],
            'total': 1, 'limite': 50, 'offset': 0,
        }
        resp = self.client.get('/sankhya/usuarios/api/listar/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)

    @patch('sankhya_integration.views.listar_usuarios')
    def test_limite_clipado_max_200(self, mock_listar):
        mock_listar.return_value = {'usuarios': [], 'total': 0, 'limite': 200, 'offset': 0}
        self.client.get('/sankhya/usuarios/api/listar/?limite=9999')
        kwargs = mock_listar.call_args.kwargs
        self.assertEqual(kwargs['limite'], 200)

    @patch('sankhya_integration.views.listar_usuarios')
    def test_filtros_chegam_no_service(self, mock_listar):
        mock_listar.return_value = {'usuarios': [], 'total': 0, 'limite': 50, 'offset': 0}
        self.client.get('/sankhya/usuarios/api/listar/?busca=andre&codgrupo=1&apenas_ativos=false&apenas_inativos=true')
        filtros = mock_listar.call_args.kwargs['filtros']
        self.assertEqual(filtros['busca'], 'andre')
        self.assertEqual(filtros['codgrupo'], '1')
        self.assertFalse(filtros['apenas_ativos'])
        self.assertTrue(filtros['apenas_inativos'])

    def test_sem_sessao_redireciona(self):
        client = Client()
        resp = client.get('/sankhya/usuarios/api/listar/')
        self.assertIn(resp.status_code, (302, 401, 403))


class ApiUsuariosDetalheViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    @patch('sankhya_integration.views.consultar_usuario_detalhe')
    def test_usuario_existe(self, mock_det):
        mock_det.return_value = {
            'codusu': 10, 'nomeusu': 'ANDRE', 'nomeusucplt': '',
            'email': '', 'cpf': '', 'codgrupo_principal': 1,
            'nomegrupo_principal': 'DIRETORIA',
            'dtlimacesso': '', 'dtultacesso': '', 'dtultimasenha': '',
            'tem_senha': True, 'ativo': True, 'grupos_extras': [],
        }
        resp = self.client.get('/sankhya/usuarios/api/10/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['usuario']['codusu'], 10)

    @patch('sankhya_integration.views.consultar_usuario_detalhe')
    def test_usuario_nao_existe(self, mock_det):
        mock_det.return_value = None
        resp = self.client.get('/sankhya/usuarios/api/999/')
        self.assertEqual(resp.status_code, 404)


class ApiUsuariosGruposViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    @patch('sankhya_integration.views.consultar_grupos_disponiveis')
    def test_lista_grupos(self, mock_gr):
        mock_gr.return_value = [
            {'codgrupo': 1, 'nomegrupo': 'DIRETORIA', 'descricao': ''},
            {'codgrupo': 6, 'nomegrupo': 'SUPORTE',   'descricao': ''},
        ]
        resp = self.client.get('/sankhya/usuarios/api/grupos/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['grupos']), 2)


# --------------------------------------------------------------------------
# Stubs Cat B — TODOS retornam 501 com pendente_cat_b=true
# --------------------------------------------------------------------------

class StubsCatBTest(TestCase):
    """Stubs de B1-B6 devem retornar 501 enquanto Cat B não for aprovado."""

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    def _post(self, url):
        return self.client.post(url, data='{}', content_type='application/json')

    def test_b1_criar_retorna_501(self):
        resp = self._post('/sankhya/usuarios/api/criar/')
        self.assertEqual(resp.status_code, 501)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertTrue(data['pendente_cat_b'])

    def test_b2_editar_retorna_501(self):
        resp = self._post('/sankhya/usuarios/api/10/editar/')
        self.assertEqual(resp.status_code, 501)
        self.assertTrue(resp.json()['pendente_cat_b'])

    def test_b3_inativar_retorna_501(self):
        resp = self._post('/sankhya/usuarios/api/10/inativar/')
        self.assertEqual(resp.status_code, 501)
        self.assertTrue(resp.json()['pendente_cat_b'])

    def test_b4_reativar_retorna_501(self):
        resp = self._post('/sankhya/usuarios/api/10/reativar/')
        self.assertEqual(resp.status_code, 501)
        self.assertTrue(resp.json()['pendente_cat_b'])

    def test_b5_add_grupo_retorna_501(self):
        resp = self._post('/sankhya/usuarios/api/10/grupo/adicionar/')
        self.assertEqual(resp.status_code, 501)
        self.assertTrue(resp.json()['pendente_cat_b'])

    def test_b6_remover_grupo_retorna_501(self):
        resp = self._post('/sankhya/usuarios/api/10/grupo/remover/')
        self.assertEqual(resp.status_code, 501)
        self.assertTrue(resp.json()['pendente_cat_b'])

    def test_stubs_respeitam_decorator_de_grupo(self):
        """Grupo 10 não consegue chamar nem o stub."""
        client = Client()
        _login_session(client, grupos=['10'])
        resp = client.post('/sankhya/usuarios/api/criar/', data='{}',
                           content_type='application/json')
        self.assertIn(resp.status_code, (302, 403))
