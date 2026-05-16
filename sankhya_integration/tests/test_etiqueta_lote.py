"""Tests do módulo de etiquetas SafeTrace/IAgro (Rastreio — Mai/2026).

Cobertura:
    - calcular_qtd_etiquetas (arredondamento, edge cases)
    - gerar_pdf_etiquetas (smoke + valida bytes não-vazios)
    - api_rastreio_etiqueta_pdf (sem nunota, sem itens, sem peso resolvido,
      precisa de escolha → 409, fluxo feliz com PESO próprio, com TOP 26)
    - api_rastreio_resolver_peso (resposta direta vs precisa_escolha)
    - atribuir_lote_item_pedido grava PESO na TOP 34 (regressão B1)
    - desvincular_lote_item_pedido limpa PESO (regressão B2)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory


# --------------------------------------------------------------------------
# Helper de calculo
# --------------------------------------------------------------------------

class CalcularQtdEtiquetasTest(TestCase):
    """Helper de arredondamento — math.ceil(qtd_kg / peso_caixa)."""

    def setUp(self):
        from sankhya_integration.services.oracle_conn import calcular_qtd_etiquetas
        self.calc = calcular_qtd_etiquetas

    def test_divisao_exata(self):
        self.assertEqual(self.calc(300, 10), 30)
        self.assertEqual(self.calc(1000, 20), 50)

    def test_arredonda_pra_cima(self):
        # 305 / 10 = 30.5 → 31 (a última caixa tem 5 kg)
        self.assertEqual(self.calc(305, 10), 31)
        # 21 / 20 = 1.05 → 2 caixas
        self.assertEqual(self.calc(21, 20), 2)

    def test_zero_peso_retorna_zero(self):
        self.assertEqual(self.calc(300, 0), 0)
        self.assertEqual(self.calc(300, None), 0)

    def test_zero_qtd_retorna_zero(self):
        self.assertEqual(self.calc(0, 10), 0)
        self.assertEqual(self.calc(None, 10), 0)

    def test_negativo_retorna_zero(self):
        self.assertEqual(self.calc(-5, 10), 0)
        self.assertEqual(self.calc(10, -5), 0)


# --------------------------------------------------------------------------
# Renderização do PDF — smoke
# --------------------------------------------------------------------------

class GerarPdfEtiquetasTest(TestCase):
    """Smoke: confirma que o pipeline reportlab+qrcode roda sem exceção e
    devolve bytes não-vazios. Não inspeciona conteúdo binário."""

    def _pedido_fake(self):
        return {
            'nunota': 111777,
            'numnota': 6242,
            'dtneg': None,
            'codemp': 10,
            'empresa': {
                'razao':         'AGROMIL AGROCOMERCIAL',
                'nome_fantasia': 'AGROMIL',
                'cgc':           '21297713000139',
                'latitude':      -15.7195,
                'longitude':     -48.1925,
                'endereco':      'Rodovia BR-070, S/N - GLEBA 76/77 - Brasilia/DF',
                'cep':           '72701991',
            },
        }

    def _item_fake(self, **overrides):
        base = {
            'sequencia':      1,
            'codprod':        100,
            'descrprod':      'ABOBORA ITALIA EXTRA',
            'codvol':         'UN',
            'qtdneg':         300.0,
            'qtdfixada':      1.0,  # mantido pra compat com gerar_pdf_etiquetas
            'codagregacao':   '111777S01D260508',
            'referencia_ean': '1280001250157',
        }
        base.update(overrides)
        return base

    def test_gera_pdf_nao_vazio(self):
        from sankhya_integration.services.etiqueta_lote import gerar_pdf_etiquetas
        pdf = gerar_pdf_etiquetas(self._pedido_fake(), [(self._item_fake(), 3)])
        self.assertGreater(len(pdf), 100)
        self.assertTrue(pdf.startswith(b'%PDF'))  # magic number

    def test_lista_vazia_gera_pdf_vazio(self):
        """0 etiquetas → PDF sem páginas. Caller deve validar antes."""
        from sankhya_integration.services.etiqueta_lote import gerar_pdf_etiquetas
        pdf = gerar_pdf_etiquetas(self._pedido_fake(), [])
        self.assertGreater(len(pdf), 0)

    def test_item_sem_ean_nao_quebra(self):
        from sankhya_integration.services.etiqueta_lote import gerar_pdf_etiquetas
        item = self._item_fake(referencia_ean='')
        pdf = gerar_pdf_etiquetas(self._pedido_fake(), [(item, 1)])
        self.assertGreater(len(pdf), 100)

    def test_empresa_sem_latlong_nao_quebra(self):
        """LAT/LONG NULL — só não aparece a linha."""
        from sankhya_integration.services.etiqueta_lote import gerar_pdf_etiquetas
        pedido = self._pedido_fake()
        pedido['empresa']['latitude']  = None
        pedido['empresa']['longitude'] = None
        pdf = gerar_pdf_etiquetas(pedido, [(self._item_fake(), 1)])
        self.assertGreater(len(pdf), 100)


# --------------------------------------------------------------------------
# View api_rastreio_etiqueta_pdf (Mai/2026 — schema novo com PESO + TOP 26)
# --------------------------------------------------------------------------

class ApiEtiquetaPdfViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request_com_sessao(self, url='/sankhya/rastreio/api/etiqueta-pdf/?nunota=111777'):
        req = self.factory.get(url)
        req.session = {
            'codusu': 1,
            'nomeusu': 'ANDRE',
            'nome': 'Andre',
            'grupos': ['1'],  # Diretoria
        }
        return req

    def _item(self, **overrides):
        """Item no formato novo (Mai/2026) — com peso_resolvido + pesos_top26."""
        base = {
            'sequencia':       1,
            'codprod':         100,
            'descrprod':       'TOMATE',
            'codvol':          'KG',
            'qtdneg':          1000.0,
            'codagregacao':    'L1',
            'referencia_ean':  '',
            'peso_proprio':    0.0,
            'pesos_top26':     [],
            'peso_resolvido':  20.0,
            'origem_peso':     'PROPRIO',
            'precisa_escolha': False,
        }
        base.update(overrides)
        return base

    def _pedido(self):
        return {
            'nunota': 111777, 'numnota': 6242, 'dtneg': None, 'codemp': 10,
            'empresa': {
                'razao': 'AGROMIL', 'nome_fantasia': '', 'cgc': '',
                'latitude': None, 'longitude': None,
                'endereco': '', 'cep': '',
            },
        }

    def test_sem_nunota_retorna_400(self):
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        req = self._request_com_sessao('/sankhya/rastreio/api/etiqueta-pdf/')
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 400)

    def test_nunota_invalido_retorna_400(self):
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        req = self._request_com_sessao('/sankhya/rastreio/api/etiqueta-pdf/?nunota=abc')
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_pedido_sem_itens_retorna_404(self, mock_consulta):
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {'pedido': None, 'itens': []}
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 404)

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_precisa_escolha_retorna_409(self, mock_consulta):
        """Lote com 2+ pesos na TOP 26 sem override → 409 indicando que o
        frontend precisa abrir modal de escolha."""
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {
            'pedido': self._pedido(),
            'itens': [self._item(
                peso_resolvido=0.0,
                pesos_top26=[22.0, 20.0],
                origem_peso=None,
                precisa_escolha=True,
            )],
        }
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 409)
        import json as _json
        body = _json.loads(resp.content.decode())
        self.assertTrue(body.get('precisa_escolha'))
        self.assertEqual(len(body['itens_pendentes']), 1)
        self.assertEqual(body['itens_pendentes'][0]['pesos_top26'], [22.0, 20.0])

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_todos_sem_peso_resolvido_retorna_400(self, mock_consulta):
        """Nenhuma linha tem PESO próprio nem TOP 26 com peso → 400."""
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {
            'pedido': self._pedido(),
            'itens': [self._item(peso_resolvido=0.0, origem_peso=None)],
        }
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 400)
        import json as _json
        body = _json.loads(resp.content.decode())
        self.assertIn('peso', body['error'].lower())

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_fluxo_feliz_peso_proprio_retorna_pdf(self, mock_consulta):
        """Pedido com 1 linha PESO próprio → PDF gerado."""
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {
            'pedido': self._pedido(),
            'itens': [self._item(peso_proprio=20.0, peso_resolvido=20.0,
                                 origem_peso='PROPRIO')],
        }
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_fluxo_top26_unico_retorna_pdf(self, mock_consulta):
        """PESO próprio NULL + TOP 26 tem 1 só peso → resolve auto, PDF ok."""
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {
            'pedido': self._pedido(),
            'itens': [self._item(
                peso_proprio=0.0,
                pesos_top26=[22.0],
                peso_resolvido=22.0,
                origem_peso='TOP26_UNICO',
            )],
        }
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')


# --------------------------------------------------------------------------
# View api_rastreio_resolver_peso (Mai/2026 — novo endpoint)
# --------------------------------------------------------------------------

class ApiResolverPesoViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _req(self, url='/sankhya/rastreio/api/resolver-peso/?nunota=1'):
        req = self.factory.get(url)
        req.session = {'codusu': 1, 'nomeusu': 'X', 'nome': 'X', 'grupos': ['1']}
        return req

    def test_sem_nunota_retorna_400(self):
        from sankhya_integration.views import api_rastreio_resolver_peso
        resp = api_rastreio_resolver_peso(self._req('/sankhya/rastreio/api/resolver-peso/'))
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_sem_itens_retorna_404(self, mock_consulta):
        from sankhya_integration.views import api_rastreio_resolver_peso
        mock_consulta.return_value = {'pedido': None, 'itens': []}
        resp = api_rastreio_resolver_peso(self._req())
        self.assertEqual(resp.status_code, 404)

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_resolucao_direta_sem_escolha(self, mock_consulta):
        """Nenhuma linha precisa de escolha → frontend abre PDF direto."""
        from sankhya_integration.views import api_rastreio_resolver_peso
        mock_consulta.return_value = {
            'pedido': {'nunota': 1},
            'itens': [{
                'sequencia': 1, 'codprod': 100, 'descrprod': 'X',
                'qtdneg': 300, 'codagregacao': 'L1', 'codvol': 'KG',
                'peso_proprio': 16.0, 'pesos_top26': [],
                'peso_resolvido': 16.0, 'origem_peso': 'PROPRIO',
                'precisa_escolha': False,
                'referencia_ean': '',
            }],
        }
        resp = api_rastreio_resolver_peso(self._req())
        self.assertEqual(resp.status_code, 200)
        import json as _json
        body = _json.loads(resp.content.decode())
        self.assertTrue(body['ok'])
        self.assertFalse(body['precisa_escolha'])

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_resolucao_pede_escolha(self, mock_consulta):
        """Pelo menos 1 linha com 2+ pesos TOP 26 → precisa_escolha=True."""
        from sankhya_integration.views import api_rastreio_resolver_peso
        mock_consulta.return_value = {
            'pedido': {'nunota': 1},
            'itens': [{
                'sequencia': 1, 'codprod': 100, 'descrprod': 'TOMATE',
                'qtdneg': 800, 'codagregacao': 'L1', 'codvol': 'KG',
                'peso_proprio': 0.0, 'pesos_top26': [22.0, 20.0],
                'peso_resolvido': 0.0, 'origem_peso': None,
                'precisa_escolha': True,
                'referencia_ean': '',
            }],
        }
        resp = api_rastreio_resolver_peso(self._req())
        self.assertEqual(resp.status_code, 200)
        import json as _json
        body = _json.loads(resp.content.decode())
        self.assertTrue(body['precisa_escolha'])
        self.assertEqual(body['itens'][0]['pesos_top26'], [22.0, 20.0])


# --------------------------------------------------------------------------
# Regressão B1 — atribuir_lote_item_pedido grava PESO (Mai/2026)
# --------------------------------------------------------------------------

class AtribuirGravaPesoTest(TestCase):
    """Confirma que o UPDATE/INSERT grava PESO (não mais QTDFIXADA)."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_peso_passado_grava_no_update(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),    # FOR UPDATE: sem lote, qtd 10, codprod 100
            (34, '0'),            # pedido TOP 34 aberto
            (50.0,),              # saldo do lote suficiente
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(
            nunota=1, sequencia=1, codagregacao='L1',
            peso=15.0,
        )

        self.assertTrue(res['ok'])
        self.assertEqual(res['operacao'], 'UPDATE')

        update_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'PESO' in (call[0][0] if call[0] else '')
            and 'CODAGREGACAO' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(update_calls, "Nenhum UPDATE com PESO encontrado")
        kwargs = update_calls[0][1]
        self.assertEqual(kwargs.get('p'), 15.0)
        # Garantia: SQL não menciona mais QTDFIXADA
        sql = update_calls[0][0][0]
        self.assertNotIn('QTDFIXADA', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_peso_omitido_grava_null(self, _mp, mock_obter):
        """Sem peso no parâmetro → grava NULL (operador deixou vazio).

        Importante: campo agora é OPCIONAL no modal (Mai/2026)."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),
            (34, '0'),
            (50.0,),
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(nunota=1, sequencia=1, codagregacao='L1')

        self.assertTrue(res['ok'])
        update_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'PESO' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(update_calls)
        kwargs = update_calls[0][1]
        self.assertIsNone(kwargs.get('p'))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_peso_zero_ou_negativo_vira_null(self, _mp, mock_obter):
        """Valores inválidos (0, negativo) viram NULL — não passam."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (None, 10.0, 100),
            (34, '0'),
            (50.0,),
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import atribuir_lote_item_pedido
        res = atribuir_lote_item_pedido(
            nunota=1, sequencia=1, codagregacao='L1',
            peso=0,
        )

        self.assertTrue(res['ok'])
        update_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'PESO' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(update_calls)
        kwargs = update_calls[0][1]
        self.assertIsNone(kwargs.get('p'))


# --------------------------------------------------------------------------
# Regressão B2 — desvincular_lote_item_pedido limpa PESO (Mai/2026)
# --------------------------------------------------------------------------

class DesvincularLimpaPesoTest(TestCase):
    """No caminho CLEAR (sem MERGE), o UPDATE deve limpar tanto
    CODAGREGACAO quanto PESO."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_clear_inclui_peso_no_update(self, _mp, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (34, '0', 'L1', 100, 10.0),  # JOIN: top, status, codag, codprod, qtd
            None,                         # nenhuma outra linha pendente
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import desvincular_lote_item_pedido
        res = desvincular_lote_item_pedido(nunota=1, sequencia=1)

        self.assertTrue(res['ok'])
        self.assertEqual(res['operacao'], 'CLEAR')

        clear_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'CODAGREGACAO = NULL' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(clear_calls)
        sql = clear_calls[0][0][0]
        self.assertIn('PESO', sql)
        self.assertIn('NULL', sql)
        # Garantia: limpa PESO, não QTDFIXADA
        self.assertNotIn('QTDFIXADA', sql)


# --------------------------------------------------------------------------
# consultar_pesos_classificacao_lote (Mai/2026 — nova função)
# --------------------------------------------------------------------------

class ConsultarPesosClassificacaoLoteTest(TestCase):
    """SELECT DISTINCT PESO da TOP 26 do mesmo CODAGREGACAO, ordenado DESC."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_retorna_lista_ordenada_desc(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(22.0,), (20.0,)]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import consultar_pesos_classificacao_lote
        pesos = consultar_pesos_classificacao_lote('L1')

        self.assertEqual(pesos, [22.0, 20.0])
        # SQL filtra TOP 26 + STATUSNOTA<>'E' + PESO > 0
        sql_used = cursor.execute.call_args[0][0]
        self.assertIn('CODTIPOPER = 26', sql_used)
        self.assertIn("STATUSNOTA <> 'E'", sql_used)
        self.assertIn('PESO > 0', sql_used)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_vazio_retorna_lista_vazia(self, mock_obter):
        """codagregacao vazio → curto-circuita sem ir ao banco."""
        from sankhya_integration.services.oracle_conn import consultar_pesos_classificacao_lote
        self.assertEqual(consultar_pesos_classificacao_lote(''), [])
        self.assertEqual(consultar_pesos_classificacao_lote(None), [])
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sem_classificacao_retorna_lista_vazia(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import consultar_pesos_classificacao_lote
        self.assertEqual(consultar_pesos_classificacao_lote('L1'), [])
