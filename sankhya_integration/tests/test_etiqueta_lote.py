"""Tests do módulo de etiquetas SafeTrace/IAgro (Rastreio — Mai/2026).

Cobertura:
    - calcular_qtd_etiquetas (arredondamento, edge cases)
    - gerar_pdf_etiquetas (smoke + valida bytes não-vazios)
    - api_rastreio_etiqueta_pdf (sem nunota, sem itens, com itens, sem QTDFIXADA)
    - atribuir_lote_item_pedido grava QTDFIXADA na TOP 34 (regressão B1)
    - desvincular_lote_item_pedido limpa QTDFIXADA (regressão B2)
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
            'qtdfixada':      1.0,
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
        # PDF "vazio" do reportlab ainda tem cabeçalho — bytes > 0 esperado
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
# View api_rastreio_etiqueta_pdf
# --------------------------------------------------------------------------

class ApiEtiquetaPdfViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request_com_sessao(self, url='/sankhya/rastreio/api/etiqueta-pdf/?nunota=111777'):
        """Cria request com sessão simulando usuário do grupo rastreio."""
        req = self.factory.get(url)
        req.session = {
            'codusu': 1,
            'nomeusu': 'ANDRE',
            'nome': 'Andre',
            'grupos': ['1'],  # Diretoria — acesso a tudo
        }
        return req

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
    def test_itens_sem_qtdfixada_retorna_400(self, mock_consulta):
        """Todos itens sem peso da caixa → bloqueio com mensagem clara."""
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {
            'pedido': {'nunota': 111777, 'empresa': {}},
            'itens': [
                {'codprod': 100, 'descrprod': 'X', 'qtdneg': 300,
                 'qtdfixada': 0, 'codagregacao': 'L1', 'codvol': 'KG',
                 'referencia_ean': '', 'sequencia': 1},
            ],
        }
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 400)
        # Espera mensagem útil sobre QTDFIXADA
        import json as _json
        body = _json.loads(resp.content.decode())
        self.assertIn('peso', body['error'].lower())

    @patch('sankhya_integration.views.consultar_dados_etiqueta_pedido')
    def test_fluxo_feliz_retorna_pdf(self, mock_consulta):
        """Pedido com 1 item → PDF gerado, content-type correto."""
        from sankhya_integration.views import api_rastreio_etiqueta_pdf
        mock_consulta.return_value = {
            'pedido': {
                'nunota': 111777, 'numnota': 6242, 'dtneg': None, 'codemp': 10,
                'empresa': {
                    'razao': 'AGROMIL', 'nome_fantasia': '', 'cgc': '',
                    'latitude': None, 'longitude': None,
                    'endereco': '', 'cep': '',
                },
            },
            'itens': [
                {'codprod': 100, 'descrprod': 'TOMATE',
                 'qtdneg': 1000, 'qtdfixada': 20.0,
                 'codagregacao': 'L1', 'codvol': 'KG',
                 'referencia_ean': '', 'sequencia': 1},
            ],
        }
        req = self._request_com_sessao()
        resp = api_rastreio_etiqueta_pdf(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
        # 1000 kg / 20 kg/caixa = 50 etiquetas — content deve ter tamanho
        # consistente com isso (não vou contar páginas via libs externas)
        self.assertGreater(len(resp.content), 1000)


# --------------------------------------------------------------------------
# atribuir_lote_item_pedido grava QTDFIXADA — agora vem do parâmetro
# (operador digita no modal). Mai/2026: não busca mais automático da TOP 11.
# --------------------------------------------------------------------------

class AtribuirGravaQtdfixadaTest(TestCase):
    """Confirma que o UPDATE na TGFITE grava QTDFIXADA com o valor passado
    no parâmetro qtdfixada (operador digita no modal de transferência)."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtdfixada_passado_grava_no_update(self, _mp, mock_obter):
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
            qtdfixada=15.0,
        )

        self.assertTrue(res['ok'])
        self.assertEqual(res['operacao'], 'UPDATE')

        update_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'QTDFIXADA' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(update_calls, "Nenhum UPDATE com QTDFIXADA encontrado")
        kwargs = update_calls[0][1]
        self.assertEqual(kwargs.get('qf'), 15.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtdfixada_omitido_grava_null(self, _mp, mock_obter):
        """Sem qtdfixada no parâmetro → grava NULL (operador deixou vazio)."""
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
            and 'QTDFIXADA' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(update_calls)
        kwargs = update_calls[0][1]
        self.assertIsNone(kwargs.get('qf'))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_qtdfixada_zero_ou_negativo_vira_null(self, _mp, mock_obter):
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
            qtdfixada=0,
        )

        self.assertTrue(res['ok'])
        update_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'QTDFIXADA' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(update_calls)
        kwargs = update_calls[0][1]
        self.assertIsNone(kwargs.get('qf'))


# --------------------------------------------------------------------------
# Regressão B2 — desvincular_lote_item_pedido limpa QTDFIXADA
# --------------------------------------------------------------------------

class DesvincularLimpaQtdfixadaTest(TestCase):
    """No caminho CLEAR (sem MERGE), o UPDATE deve limpar tanto
    CODAGREGACAO quanto QTDFIXADA."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita',
           return_value=True)
    def test_clear_inclui_qtdfixada_no_update(self, _mp, mock_obter):
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

        # O UPDATE com SET CODAGREGACAO=NULL deve incluir também QTDFIXADA=NULL
        clear_calls = [
            call for call in cursor.execute.call_args_list
            if 'UPDATE TGFITE' in (call[0][0] if call[0] else '')
            and 'CODAGREGACAO = NULL' in (call[0][0] if call[0] else '')
        ]
        self.assertTrue(clear_calls)
        sql = clear_calls[0][0][0]
        self.assertIn('QTDFIXADA', sql)
        self.assertIn('NULL', sql)
