"""Tests: margem do lote no Comercial (Mai/2026 — 2026-05-17).

Cobertura da função `consultar_margem_do_lote` + view `api_margem_lote`:

  - cálculo positivo, negativo e zero
  - divisão por zero (sem vendas)
  - devolução desconta receita
  - avaria não duplica (custo já está no vale) mas vem informativa
  - tipo_calculo PROVISORIA vs FECHADA por qtd_disponivel
  - tem_custo=False quando vale ainda não foi lançado
  - falha do banco vira dict vazio (não explode)
"""

from __future__ import annotations

import json
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
# Service consultar_margem_do_lote — fixtures dos 4 SELECTs
# --------------------------------------------------------------------------

class ConsultarMargemDoLoteTest(TestCase):
    """Função consulta 4 selects em sequência:
       1) receita_bruta (vendas com dedup)
       2) devolucoes (TOP 36)
       3) custo + qtd_entrada + avaria_qtd (CASE em 1 query, TOPs 11/13/30)
       4) qtd_disponivel (view ANDRE_IAGRO_SALDO_LOTE)
    """

    def _mock(self, mock_obter, fetchone_side):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetchone_side
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_vazio_retorna_dict_vazio_sem_consultar(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('')
        self.assertEqual(out['receita_bruta'], 0.0)
        self.assertEqual(out['margem_pct'],    0.0)
        self.assertFalse(out['tem_custo'])
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_margem_positiva_lote_fechado(self, mock_obter):
        """Receita 9000, devolução 500, custo 8000 → lucro 500, margem 5,88%.
        Lote fechado (qtd_disponivel = 0)."""
        self._mock(mock_obter, [
            (9000.0,),                  # receita_bruta
            (500.0,),                   # devolucoes
            (8000.0, 1000.0, 100.0),    # custo, qtd_entrada, avaria_qtd
            (0.0,),                     # qtd_disponivel
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')

        self.assertEqual(out['receita_bruta'],   9000.0)
        self.assertEqual(out['devolucoes'],      500.0)
        self.assertEqual(out['receita_liquida'], 8500.0)
        self.assertEqual(out['custo_total'],     8000.0)
        self.assertEqual(out['lucro'],           500.0)
        self.assertAlmostEqual(out['margem_pct'], 500/8500*100, places=2)
        self.assertEqual(out['tipo_calculo'],    'FECHADA')
        self.assertTrue(out['tem_custo'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_margem_negativa_quando_custo_maior_que_receita(self, mock_obter):
        """Receita 5000, devolução 0, custo 8000 → lucro -3000, margem -60%."""
        self._mock(mock_obter, [
            (5000.0,),
            (0.0,),
            (8000.0, 1000.0, 0.0),
            (0.0,),
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertEqual(out['lucro'], -3000.0)
        self.assertAlmostEqual(out['margem_pct'], -60.0, places=2)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_margem_zero_quando_sem_vendas(self, mock_obter):
        """Sem vendas → divisão por zero seria erro; retorna 0% sem explodir."""
        self._mock(mock_obter, [
            (0.0,),                    # receita_bruta
            (0.0,),                    # devolucoes
            (8000.0, 1000.0, 0.0),     # custo+qtd_entrada+avaria
            (1000.0,),                 # tudo no estoque ainda
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertEqual(out['receita_liquida'], 0.0)
        self.assertEqual(out['margem_pct'],      0.0)   # sem dividir por zero
        self.assertEqual(out['lucro'],          -8000.0)
        self.assertEqual(out['tipo_calculo'],   'PROVISORIA')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_devolucao_desconta_receita_liquida(self, mock_obter):
        """Receita 10000, devolução 2000, custo 5000 → líquida 8000, lucro 3000."""
        self._mock(mock_obter, [
            (10000.0,),
            (2000.0,),
            (5000.0, 1000.0, 0.0),
            (0.0,),
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertEqual(out['receita_liquida'], 8000.0)
        self.assertEqual(out['lucro'],           3000.0)
        self.assertAlmostEqual(out['margem_pct'], 3000/8000*100, places=2)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_avaria_nao_duplica_no_calculo_mas_vem_no_payload(self, mock_obter):
        """Avaria 100kg num lote de 1000kg com custo 8000 → custo médio 8/kg.
        Avaria_vlr = 100 × 8 = 800 (informativo no tooltip, NÃO subtrai do lucro)."""
        self._mock(mock_obter, [
            (9000.0,),
            (0.0,),
            (8000.0, 1000.0, 100.0),
            (0.0,),
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        # Avaria devolvida como informativa
        self.assertEqual(out['avaria_qtd'],     100.0)
        self.assertEqual(out['custo_medio_kg'], 8.0)
        self.assertEqual(out['avaria_vlr'],     800.0)
        # Lucro NÃO subtrai avaria_vlr (já está embutida no custo total)
        self.assertEqual(out['lucro'], 9000.0 - 8000.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_provisoria_quando_qtd_disponivel_maior_que_zero(self, mock_obter):
        self._mock(mock_obter, [
            (9000.0,),
            (0.0,),
            (8000.0, 1000.0, 0.0),
            (50.0,),    # ainda tem 50kg em estoque
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertEqual(out['tipo_calculo'],   'PROVISORIA')
        self.assertEqual(out['qtd_disponivel'], 50.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_tem_custo_false_quando_vale_nao_lancado(self, mock_obter):
        """Lote criado pela Entrada mas ainda sem vale (TOP 13) → tem_custo=False,
        frontend mostra '—' em vez de margem enganosa."""
        self._mock(mock_obter, [
            (0.0,),
            (0.0,),
            (0.0, 1000.0, 0.0),   # custo zero
            (1000.0,),
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertFalse(out['tem_custo'])
        self.assertEqual(out['custo_total'], 0.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_dict_vazio(self, mock_obter):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception('ORA-XXXXX boom')
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertEqual(out['receita_bruta'], 0.0)
        self.assertFalse(out['tem_custo'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_view_saldo_falha_segue_calculando_assume_fechado(self, mock_obter):
        """A view ANDRE_IAGRO_SALDO_LOTE pode falhar/ser temporariamente
        inacessível. Backend assume saldo=0 (fechado) e segue retornando
        a margem em vez de explodir.

        Mock: 3 SELECTs primeiros OK, 4º (view) levanta exceção."""
        cursor = MagicMock()
        cursor.execute.side_effect = [
            None,   # query 1 (receita) — OK
            None,   # query 2 (devolução) — OK
            None,   # query 3 (custo/qtd/avaria) — OK
            Exception('view boom'),   # query 4 (view) — falha capturada
        ]
        cursor.fetchone.side_effect = [
            (9000.0,),                  # receita
            (0.0,),                     # devolução
            (8000.0, 1000.0, 0.0),      # custo/qtd_entrada/avaria
            # fetchone da 4ª nunca é chamado (execute já levantou)
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import consultar_margem_do_lote
        out = consultar_margem_do_lote('L1')
        self.assertEqual(out['lucro'],         1000.0)   # cálculo seguiu
        self.assertEqual(out['tipo_calculo'], 'FECHADA') # fallback


# --------------------------------------------------------------------------
# View api_margem_lote
# --------------------------------------------------------------------------

class ApiMargemLoteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = '/sankhya/comercial/api/margem-lote/'

    def test_sem_lote_retorna_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertFalse(body['ok'])
        self.assertIn('lote', body['error'].lower())

    def test_lote_vazio_retorna_400(self):
        resp = self.client.get(self.url + '?lote=')
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.services.oracle_conn.consultar_margem_do_lote')
    def test_lote_valido_delega_ao_service_e_retorna_payload_com_ok(self, mock_fn):
        mock_fn.return_value = {
            'receita_bruta':   9000.0,
            'devolucoes':      500.0,
            'receita_liquida': 8500.0,
            'custo_total':     8000.0,
            'qtd_entrada':     1000.0,
            'qtd_disponivel':  0.0,
            'avaria_qtd':      0.0,
            'avaria_vlr':      0.0,
            'custo_medio_kg':  8.0,
            'lucro':           500.0,
            'margem_pct':      5.88,
            'tipo_calculo':    'FECHADA',
            'tem_custo':       True,
        }
        resp = self.client.get(self.url + '?lote=L1')
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content.decode())
        self.assertTrue(body['ok'])
        self.assertEqual(body['lucro'],     500.0)
        self.assertAlmostEqual(body['margem_pct'], 5.88, places=2)
        self.assertEqual(body['tipo_calculo'], 'FECHADA')
        mock_fn.assert_called_once_with('L1')
