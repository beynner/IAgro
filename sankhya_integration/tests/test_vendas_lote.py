"""Tests: vendas DO LOTE no Comercial (Mai/2026 — 2026-05-16).

Cobertura:
    - consultar_vendas_do_lote: SQL com filtro CODAGREGACAO + dedup TGFVAR
    - api_vendas_do_lote: validação de lote obrigatório + delega ao service
"""

from __future__ import annotations

import json
from datetime import datetime
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
# Service consultar_vendas_do_lote
# --------------------------------------------------------------------------

class ConsultarVendasDoLoteServiceTest(TestCase):
    """SQL filtra por CODAGREGACAO + dedup pedido↔nota + extrai tipo via
    TGFPRO.SELECIONADO + monta preço/kg e preço/cx."""

    def _mock_conn_ctx(self, mock_obter, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return conn

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_vazio_retorna_lista_vazia_sem_consultar(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
        self.assertEqual(consultar_vendas_do_lote(''),   {'ultimasVendas': []})
        self.assertEqual(consultar_vendas_do_lote(None), {'ultimasVendas': []})
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sql_filtra_por_codagregacao_com_dedup_tgfvar(self, mock_obter):
        """SQL deve conter filtro `CODAGREGACAO = :lote`, STATUSNOTA='L',
        TOPs (34,35,37) e cláusula de dedup com TGFVAR."""
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
        consultar_vendas_do_lote('111777S01D260508')

        # Confere que a query foi montada com os filtros corretos
        self.assertEqual(cursor.execute.call_count, 1)
        sql_used = cursor.execute.call_args[0][0]
        binds    = cursor.execute.call_args[1]

        self.assertIn('CODAGREGACAO = :lote',       sql_used)
        self.assertIn("STATUSNOTA = 'L'",           sql_used)
        self.assertIn('CODTIPOPER IN (34, 35, 37)', sql_used)
        # Dedup: TOP 34 sempre OK, TOP 35/37 só sem par TGFVAR
        self.assertIn('TGFVAR',         sql_used)
        self.assertIn('NUNOTAORIG',     sql_used)
        self.assertEqual(binds.get('lote'), '111777S01D260508')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_mapeia_selecionado_para_tipo_humano(self, mock_obter):
        """SELECIONADO '1' → EXTRA, '2' → MÉDIO, '0' → IN NATURA, outros → OUTROS."""
        cursor = MagicMock()
        dt = datetime(2026, 5, 15)
        cursor.fetchall.return_value = [
            (dt, 111, 6242, 35, 'ASSAI', 'ASSAI FULL', '1', 100.0, 250.0, 20.0),  # EXTRA
            (dt, 112, 6243, 35, 'XX',    'XX FULL',    '2', 100.0, 200.0, 20.0),  # MÉDIO
            (dt, 113, 6244, 35, 'YY',    'YY FULL',    '0', 100.0, 150.0, 20.0),  # IN NATURA
            (dt, 114, 6245, 35, 'ZZ',    'ZZ FULL',    '9', 100.0, 180.0, 20.0),  # OUTROS
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
        res = consultar_vendas_do_lote('L1')

        tipos = [v['tipo'] for v in res['ultimasVendas']]
        self.assertEqual(tipos, ['EXTRA', 'MÉDIO', 'IN NATURA', 'OUTROS'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_calcula_preco_kg_e_preco_cx(self, mock_obter):
        """preço/kg = vlrtot / qtd; preço/cx = preço/kg × peso_cx."""
        cursor = MagicMock()
        dt = datetime(2026, 5, 15)
        # 160 kg, R$ 520 total, caixa 20kg → 3,25/kg → 65,00/cx
        cursor.fetchall.return_value = [
            (dt, 111, 6242, 35, 'ASSAI', 'ASSAI FULL', '1', 160.0, 520.0, 20.0),
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
        res = consultar_vendas_do_lote('L1')

        venda = res['ultimasVendas'][0]
        self.assertAlmostEqual(venda['preco_kg'], 3.25, places=4)
        self.assertAlmostEqual(venda['preco_cx'], 65.00, places=4)
        self.assertAlmostEqual(venda['qtd_kg'], 160.0)
        self.assertAlmostEqual(venda['peso_cx'], 20.0)
        self.assertEqual(venda['nunota'], 111)
        self.assertEqual(venda['numnota'], 6242)
        self.assertEqual(venda['top'], 35)
        self.assertEqual(venda['data'], '15/05')
        self.assertEqual(venda['data_iso'], '2026-05-15')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_cliente_truncado_em_24_chars(self, mock_obter):
        """Campo `cliente` (curto) trunca em 24 chars; `cliente_full` mantém completo."""
        cursor = MagicMock()
        dt = datetime(2026, 5, 15)
        nome_longo = 'SENDAS DISTRIBUIDORA S/A LJ176 PALMAS TEOTONIO'
        cursor.fetchall.return_value = [
            (dt, 111, 6242, 35, nome_longo, nome_longo, '1', 100.0, 250.0, 22.0),
        ]
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
        res = consultar_vendas_do_lote('L1')

        venda = res['ultimasVendas'][0]
        self.assertLessEqual(len(venda['cliente']), 24)
        self.assertEqual(venda['cliente_full'], nome_longo)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_lista_vazia_sem_explodir(self, mock_obter):
        """Exceção do banco vira lista vazia (caller não pode quebrar)."""
        cursor = MagicMock()
        cursor.execute.side_effect = Exception('ORA-XXXXX boom')
        self._mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_vendas_do_lote
        res = consultar_vendas_do_lote('L1')
        self.assertEqual(res, {'ultimasVendas': []})


# --------------------------------------------------------------------------
# View api_vendas_do_lote
# --------------------------------------------------------------------------

class ApiVendasDoLoteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = '/sankhya/comercial/api/vendas-lote/'

    def test_sem_lote_retorna_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertFalse(body['ok'])
        self.assertIn('lote', body['error'].lower())

    def test_lote_vazio_retorna_400(self):
        resp = self.client.get(self.url + '?lote=')
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.services.oracle_conn.consultar_vendas_do_lote')
    def test_lote_valido_chama_service_e_retorna_payload(self, mock_fn):
        mock_fn.return_value = {
            'ultimasVendas': [
                {'data': '15/05', 'cliente': 'X', 'tipo': 'EXTRA',
                 'preco_kg': 3.25, 'preco_cx': 65.0},
            ],
        }
        resp = self.client.get(self.url + '?lote=L1')
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content.decode())
        self.assertEqual(len(body['ultimasVendas']), 1)
        self.assertEqual(body['ultimasVendas'][0]['preco_kg'], 3.25)
        mock_fn.assert_called_once_with('L1')

    @patch('sankhya_integration.services.oracle_conn.consultar_vendas_do_lote')
    def test_lote_com_espacos_eh_trimado(self, mock_fn):
        """`lote` trim'ado antes de chamar service (defesa contra espaço acidental)."""
        mock_fn.return_value = {'ultimasVendas': []}
        resp = self.client.get(self.url + '?lote=%20L1%20')
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with('L1')
