"""Tests do módulo Relatórios (Mai/2026 — 2026-05-17).

MVP de 5 relatórios — cobertura por relatório à medida que cada um entra:
  1. Top clientes + Top produtos
  2. Lotes envelhecidos
  3. Consumo por veículo
  4. Fluxo de caixa
  5. Margem por venda
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
# Acesso à tela (decorator @exige_grupo('relatorios'))
# --------------------------------------------------------------------------

class AcessoRelatoriosTest(TestCase):
    """Apenas grupos 1 (Diretoria), 6 (Suporte), 9 (Comercial) podem entrar."""

    def setUp(self):
        self.client = Client()
        self.url = '/sankhya/relatorios/'

    def test_diretoria_acessa(self):
        _login_session(self.client, grupos=['1'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_suporte_acessa(self):
        _login_session(self.client, grupos=['6'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_comercial_acessa(self):
        _login_session(self.client, grupos=['9'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_administrativo_nao_acessa(self):
        """Grupo 10 (Administrativo) NÃO entra — público-alvo é gerencial."""
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url)
        # @exige_grupo redireciona pra home (302)
        self.assertIn(resp.status_code, (302, 403))

    def test_sem_sessao_nao_acessa(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))


# --------------------------------------------------------------------------
# Service consultar_top_clientes_produtos
# --------------------------------------------------------------------------

class ConsultarTopClientesProdutosTest(TestCase):
    """SQL filtra por TOP 35/37 STATUSNOTA='L' + janela de data; agrupa por
    matriz do cliente (CODPARCMATRIZ) e por CODPROD."""

    def _mock(self, mock_obter, fetchall_side, fetchone_side=None):
        cursor = MagicMock()
        cursor.fetchall.side_effect = fetchall_side
        if fetchone_side is not None:
            cursor.fetchone.side_effect = fetchone_side
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_datas_vazias_retornam_dict_vazio_sem_consultar(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
        out = consultar_top_clientes_produtos('', '')
        self.assertEqual(out['top_clientes'], [])
        self.assertEqual(out['top_produtos'], [])
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_metrica_valor_usa_sum_vlrtot(self, mock_obter):
        cursor = self._mock(
            mock_obter,
            fetchall_side=[[], []],
            fetchone_side=[(0.0,)],
        )
        from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
        consultar_top_clientes_produtos('2026-05-01', '2026-05-17', metrica='valor')
        # 3 queries: top clientes, top produtos, total geral
        self.assertEqual(cursor.execute.call_count, 3)
        # 1ª query (clientes) deve mencionar SUM(NVL(i.VLRTOT, 0))
        sql_cli = cursor.execute.call_args_list[0][0][0]
        self.assertIn('SUM(NVL(i.VLRTOT, 0))', sql_cli)
        self.assertIn("CODTIPOPER IN (35, 37)", sql_cli)
        self.assertIn("STATUSNOTA = 'L'", sql_cli)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_metrica_qtd_usa_sum_qtdneg(self, mock_obter):
        cursor = self._mock(
            mock_obter,
            fetchall_side=[[], []],
            fetchone_side=[(0.0,)],
        )
        from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
        consultar_top_clientes_produtos('2026-05-01', '2026-05-17', metrica='qtd')
        sql_cli = cursor.execute.call_args_list[0][0][0]
        self.assertIn('SUM(NVL(i.QTDNEG, 0))', sql_cli)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_metrica_pedidos_usa_count_distinct_nunota(self, mock_obter):
        cursor = self._mock(
            mock_obter,
            fetchall_side=[[], []],
            fetchone_side=[(0.0,)],
        )
        from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
        consultar_top_clientes_produtos('2026-05-01', '2026-05-17', metrica='pedidos')
        sql_cli = cursor.execute.call_args_list[0][0][0]
        self.assertIn('COUNT(DISTINCT c.NUNOTA)', sql_cli)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_payload_completo_com_dados(self, mock_obter):
        self._mock(
            mock_obter,
            fetchall_side=[
                # Top clientes
                [
                    (588, 'ASSAI', 'ASSAI DISTRIBUIDORA',     45000.0),
                    (601, 'EXTRA', 'COMPANHIA BRASILEIRA',    28000.0),
                ],
                # Top produtos
                [
                    (355, 'TOMATE CARMEN EXTRA',  60000.0),
                    (358, 'BATATA DOCE EXTRA',    13000.0),
                ],
            ],
            fetchone_side=[(73000.0,)],
        )
        from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
        out = consultar_top_clientes_produtos('2026-05-01', '2026-05-17')

        self.assertEqual(len(out['top_clientes']), 2)
        self.assertEqual(out['top_clientes'][0]['codparc'], 588)
        self.assertEqual(out['top_clientes'][0]['nome'],    'ASSAI')
        self.assertEqual(out['top_clientes'][0]['metrica'], 45000.0)
        self.assertEqual(len(out['top_produtos']), 2)
        self.assertEqual(out['top_produtos'][0]['codprod'],   355)
        self.assertEqual(out['top_produtos'][0]['descrprod'], 'TOMATE CARMEN EXTRA')
        self.assertEqual(out['total_geral_clientes'], 73000.0)
        self.assertEqual(out['total_geral_produtos'], 73000.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_dict_vazio_sem_explodir(self, mock_obter):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception('ORA-XXXXX')
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import consultar_top_clientes_produtos
        out = consultar_top_clientes_produtos('2026-05-01', '2026-05-17')
        self.assertEqual(out['top_clientes'], [])
        self.assertEqual(out['top_produtos'], [])


# --------------------------------------------------------------------------
# View api_relatorio_top_clientes_produtos
# --------------------------------------------------------------------------

class ApiTopClientesProdutosViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = '/sankhya/relatorios/api/top-clientes-produtos/'

    def test_sem_datas_retorna_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)

    def test_apenas_date_de_retorna_400(self):
        resp = self.client.get(self.url + '?date_de=2026-05-01')
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.services.oracle_conn.consultar_top_clientes_produtos')
    def test_payload_valido_chama_service(self, mock_fn):
        mock_fn.return_value = {
            'top_clientes': [{'codparc': 1, 'nome': 'X', 'nome_full': 'X', 'metrica': 100.0}],
            'top_produtos': [],
            'total_geral_clientes': 100.0,
            'total_geral_produtos': 100.0,
        }
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17')
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content.decode())
        self.assertTrue(body['ok'])
        self.assertEqual(len(body['top_clientes']), 1)
        mock_fn.assert_called_once_with('2026-05-01', '2026-05-17', metrica='valor', limite=15)

    @patch('sankhya_integration.services.oracle_conn.consultar_top_clientes_produtos')
    def test_metrica_invalida_cai_em_valor(self, mock_fn):
        mock_fn.return_value = {'top_clientes': [], 'top_produtos': [],
                                'total_geral_clientes': 0, 'total_geral_produtos': 0}
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17&metrica=hackz')
        self.assertEqual(resp.status_code, 200)
        # Whitelist no view força 'valor' quando vem coisa estranha
        self.assertEqual(mock_fn.call_args.kwargs['metrica'], 'valor')

    @patch('sankhya_integration.services.oracle_conn.consultar_top_clientes_produtos')
    def test_limite_clipado_entre_1_e_50(self, mock_fn):
        mock_fn.return_value = {'top_clientes': [], 'top_produtos': [],
                                'total_geral_clientes': 0, 'total_geral_produtos': 0}
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17&limite=999')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_fn.call_args.kwargs['limite'], 50)

    def test_sem_sessao_bloqueia(self):
        self.client = Client()  # nova sessão sem login
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17')
        self.assertIn(resp.status_code, (302, 403))


# --------------------------------------------------------------------------
# Service consultar_lotes_envelhecidos
# --------------------------------------------------------------------------

class ConsultarLotesEnvelhecidosTest(TestCase):
    """SQL filtra ANDRE_IAGRO_SALDO_LOTE por QTD_DISPONIVEL > 0 + idade
    (TRUNC(SYSDATE - DTNEG_ORIGEM) >= :dias). Ordem decrescente por dias."""

    def _mock(self, mock_obter, fetchall):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sql_filtra_view_com_qtd_disponivel_e_idade(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_lotes_envelhecidos
        consultar_lotes_envelhecidos(dias_min=45)
        sql = cursor.execute.call_args[0][0]
        self.assertIn('ANDRE_IAGRO_SALDO_LOTE', sql)
        self.assertIn('QTD_DISPONIVEL > 0', sql)
        self.assertIn('DTNEG_ORIGEM', sql)
        # dias_min passa como bind
        self.assertEqual(cursor.execute.call_args[1].get('dias'), 45)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_dias_min_invalido_cai_em_default(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_lotes_envelhecidos
        consultar_lotes_envelhecidos(dias_min='abc')   # type: ignore[arg-type]
        # fallback pra 30 (default seguro)
        self.assertEqual(cursor.execute.call_args[1].get('dias'), 30)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_payload_completo(self, mock_obter):
        from datetime import datetime
        self._mock(mock_obter, [
            (355, 'TOMATE EXTRA', '112220S01D260412', 'JOSE DO ALHO',
             datetime(2026, 4, 12), 500.0, 80.0, 35),
            (358, 'BATATA DOCE',  '112100S01D260301', 'DEBORA',
             datetime(2026, 3,  1), 1000.0, 250.0, 77),
        ])
        from sankhya_integration.services.oracle_conn import consultar_lotes_envelhecidos
        out = consultar_lotes_envelhecidos(dias_min=30)
        self.assertEqual(len(out['lotes']), 2)
        self.assertEqual(out['lotes'][0]['codagregacao'], '112220S01D260412')
        self.assertEqual(out['lotes'][0]['dias_parado'], 35)
        self.assertEqual(out['lotes'][0]['qtd_disponivel'], 80.0)
        self.assertEqual(out['lotes'][0]['fornecedor'], 'JOSE DO ALHO')
        self.assertEqual(out['lotes'][1]['dias_parado'], 77)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_view_retorna_lista_vazia(self, mock_obter):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception('ORA-XXXXX')
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None

        from sankhya_integration.services.oracle_conn import consultar_lotes_envelhecidos
        out = consultar_lotes_envelhecidos(dias_min=30)
        self.assertEqual(out['lotes'], [])


# --------------------------------------------------------------------------
# View api_relatorio_lotes_envelhecidos
# --------------------------------------------------------------------------

class ApiLotesEnvelhecidosViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['9'])
        self.url = '/sankhya/relatorios/api/lotes-envelhecidos/'

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_envelhecidos')
    def test_default_30_dias(self, mock_fn):
        mock_fn.return_value = {'lotes': []}
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with(dias_min=30)

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_envelhecidos')
    def test_dias_min_60(self, mock_fn):
        mock_fn.return_value = {'lotes': []}
        resp = self.client.get(self.url + '?dias_min=60')
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with(dias_min=60)

    @patch('sankhya_integration.services.oracle_conn.consultar_lotes_envelhecidos')
    def test_dias_min_clipado_em_365(self, mock_fn):
        mock_fn.return_value = {'lotes': []}
        resp = self.client.get(self.url + '?dias_min=9999')
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with(dias_min=365)


# --------------------------------------------------------------------------
# Service consultar_consumo_ranking_veiculos
# --------------------------------------------------------------------------

class ConsultarConsumoRankingVeiculosTest(TestCase):
    """Agrega TOP 53 (req combustível) por veículo. Calcula eficiência só
    quando há > 1 leitura de medidor no período (max > min)."""

    def _mock(self, mock_obter, fetchall):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_datas_vazias_retornam_lista_vazia(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        out = consultar_consumo_ranking_veiculos('', '')
        self.assertEqual(out['veiculos'], [])
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sql_filtra_top_53_e_periodo(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('CODTIPOPER = 53', sql)
        self.assertIn("STATUSNOTA <> 'E'", sql)
        self.assertIn('AD_REQUISICAO_COMBUSTIVEL', sql)
        self.assertIn('TGFVEI', sql)
        binds = cursor.execute.call_args[1]
        self.assertEqual(binds.get('de'),  '2026-05-01')
        self.assertEqual(binds.get('ate'), '2026-05-17')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_filtro_tipo_maq_inclui_palavras_chave(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17', tipo='MAQ')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('TRATOR', sql)
        self.assertIn('COLHEIT', sql)
        self.assertIn('LIKE', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_filtro_tipo_com_exclui_maquinario(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17', tipo='COM')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('NOT LIKE', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_eficiencia_kmL_para_frota(self, mock_obter):
        """Caminhonete (PROPRIO='S', sem keywords MAQ) com hodômetro: km/L."""
        self._mock(mock_obter, [
            # codvei, placa,        marca,           especietipo,    proprio,
            # litros, valor, qtd_reqs, hod_max, hod_min, hor_max, hor_min
            (101, 'AAA-1234', 'FIAT STRADA',  'CARGA CAMINHAO', 'S',
             100.0, 600.0, 5, 50000.0, 49000.0, None, None),
        ])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        out = consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17')
        self.assertEqual(len(out['veiculos']), 1)
        v = out['veiculos'][0]
        self.assertEqual(v['tipo'], 'COM')
        # km = 50000 - 49000 = 1000; kmL = 1000/100 = 10,00
        self.assertEqual(v['eficiencia_label'], '10,00 km/L')
        self.assertEqual(v['medidor_total'], 1000.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_eficiencia_Lh_para_maquinario(self, mock_obter):
        """Trator (ESPECIETIPO contém TRATOR) com horímetro: L/h."""
        self._mock(mock_obter, [
            (200, 'TRT-1', 'NEW HOLLAND TM7040', 'TRATOR AGRICOLA', 'S',
             80.0, 480.0, 3, None, None, 1200.0, 1180.0),
        ])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        out = consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17')
        v = out['veiculos'][0]
        self.assertEqual(v['tipo'], 'MAQ')
        # horas = 1200 - 1180 = 20; Lh = 80/20 = 4,00
        self.assertEqual(v['eficiencia_label'], '4,00 L/h')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sem_medidor_eficiencia_traco(self, mock_obter):
        """Apenas 1 leitura ou nenhuma → não dá pra calcular eficiência."""
        self._mock(mock_obter, [
            (300, 'CCC-3333', 'CAMINHAO X', 'CARGA CAMINHAO', 'S',
             50.0, 300.0, 1, 12000.0, 12000.0, None, None),  # mesmo valor
        ])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        out = consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17')
        v = out['veiculos'][0]
        self.assertEqual(v['eficiencia_label'], '—')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_totais_agregados(self, mock_obter):
        self._mock(mock_obter, [
            (101, 'A', 'X', 'CARGA', 'S', 100.0, 600.0, 2, None, None, None, None),
            (200, 'B', 'Y', 'TRATOR', 'S',  80.0, 480.0, 1, None, None, None, None),
        ])
        from sankhya_integration.services.oracle_conn import consultar_consumo_ranking_veiculos
        out = consultar_consumo_ranking_veiculos('2026-05-01', '2026-05-17')
        self.assertEqual(out['total_litros'], 180.0)
        self.assertEqual(out['total_valor'],  1080.0)


# --------------------------------------------------------------------------
# View api_relatorio_consumo_veiculos
# --------------------------------------------------------------------------

class ApiConsumoVeiculosViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['9'])
        self.url = '/sankhya/relatorios/api/consumo-veiculos/'

    def test_sem_datas_retorna_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.services.oracle_conn.consultar_consumo_ranking_veiculos')
    def test_payload_valido(self, mock_fn):
        mock_fn.return_value = {'veiculos': [], 'total_litros': 0, 'total_valor': 0}
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17')
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with('2026-05-01', '2026-05-17', tipo='')

    @patch('sankhya_integration.services.oracle_conn.consultar_consumo_ranking_veiculos')
    def test_filtro_tipo_maq(self, mock_fn):
        mock_fn.return_value = {'veiculos': [], 'total_litros': 0, 'total_valor': 0}
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17&tipo=maq')
        self.assertEqual(resp.status_code, 200)
        # uppercased no view
        self.assertEqual(mock_fn.call_args.kwargs['tipo'], 'MAQ')

    @patch('sankhya_integration.services.oracle_conn.consultar_consumo_ranking_veiculos')
    def test_tipo_invalido_vira_vazio(self, mock_fn):
        mock_fn.return_value = {'veiculos': [], 'total_litros': 0, 'total_valor': 0}
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17&tipo=HACK')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_fn.call_args.kwargs['tipo'], '')


# --------------------------------------------------------------------------
# Service consultar_fluxo_caixa
# --------------------------------------------------------------------------

class ConsultarFluxoCaixaTest(TestCase):
    """Agrupa TGFFIN em aberto por buckets temporais. Buckets passados
    (ATRASADO/HOJE) sempre entram; futuros são clipados pelo horizonte."""

    def _mock(self, mock_obter, fetchall):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sql_filtra_aberto_com_sentinel(self, mock_obter):
        """Aberto = DHBAIXA IS NULL OR <= 01/01/1998 (sentinel Sankhya)."""
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_fluxo_caixa
        consultar_fluxo_caixa(dias=60)
        sql = cursor.execute.call_args[0][0]
        self.assertIn('DHBAIXA IS NULL', sql)
        self.assertIn("01/01/1998", sql)
        self.assertIn('RECDESP', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_horizonte_clipado_entre_7_e_180(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_fluxo_caixa
        consultar_fluxo_caixa(dias=999)
        self.assertEqual(cursor.execute.call_args[1].get('h'), 180)
        consultar_fluxo_caixa(dias=1)
        self.assertEqual(cursor.execute.call_args[1].get('h'), 7)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_horizonte_30_pula_buckets_31_60_e_61_90(self, mock_obter):
        """Horizonte 30 não inclui 31-60d nem 61-90d."""
        self._mock(mock_obter, [
            ('ATRASADO', 2000.0, 500.0),
            ('1-7d',     1000.0, 0.0),
            ('31-60d',   5000.0, 0.0),   # não deve aparecer no horizonte 30
        ])
        from sankhya_integration.services.oracle_conn import consultar_fluxo_caixa
        out = consultar_fluxo_caixa(dias=30)
        labels = [b['label'] for b in out['buckets']]
        self.assertIn('ATRASADO', labels)
        self.assertIn('1-7d',     labels)
        self.assertNotIn('31-60d', labels)
        self.assertNotIn('61-90d', labels)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_saldo_acumulado_progressivo(self, mock_obter):
        self._mock(mock_obter, [
            ('ATRASADO', 1000.0, 0.0),
            ('HOJE',     0.0,    500.0),
            ('1-7d',     2000.0, 0.0),
        ])
        from sankhya_integration.services.oracle_conn import consultar_fluxo_caixa
        out = consultar_fluxo_caixa(dias=30)
        buckets = {b['label']: b for b in out['buckets']}
        self.assertEqual(buckets['ATRASADO']['saldo_acumulado'], 1000.0)
        self.assertEqual(buckets['HOJE']['saldo_acumulado'],     500.0)
        self.assertEqual(buckets['1-7d']['saldo_acumulado'],     2500.0)
        self.assertEqual(out['total_entrada'], 3000.0)
        self.assertEqual(out['total_saida'],   500.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_vazio(self, mock_obter):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception('ORA-XXXXX')
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        from sankhya_integration.services.oracle_conn import consultar_fluxo_caixa
        out = consultar_fluxo_caixa(dias=60)
        self.assertEqual(out['buckets'], [])


# --------------------------------------------------------------------------
# View api_relatorio_fluxo_caixa
# --------------------------------------------------------------------------

class ApiFluxoCaixaViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['9'])
        self.url = '/sankhya/relatorios/api/fluxo-caixa/'

    @patch('sankhya_integration.services.oracle_conn.consultar_fluxo_caixa')
    def test_default_60_dias(self, mock_fn):
        mock_fn.return_value = {'buckets': [], 'total_entrada': 0, 'total_saida': 0}
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with(dias=60)

    @patch('sankhya_integration.services.oracle_conn.consultar_fluxo_caixa')
    def test_horizonte_90(self, mock_fn):
        mock_fn.return_value = {'buckets': [], 'total_entrada': 0, 'total_saida': 0}
        resp = self.client.get(self.url + '?dias=90')
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with(dias=90)


# --------------------------------------------------------------------------
# Service consultar_margem_por_venda
# --------------------------------------------------------------------------

class ConsultarMargemPorVendaTest(TestCase):
    """CTE custos_lote + LEFT JOIN. Custo proporcional só quando há vale
    (TOP 13) E entrada (TOP 11) — senão custo=0 (não computa)."""

    def _mock(self, mock_obter, fetchall):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_datas_vazias_retornam_vazio(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        out = consultar_margem_por_venda('', '')
        self.assertEqual(out['linhas'], [])
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sql_usa_cte_custos_lote(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        consultar_margem_por_venda('2026-05-01', '2026-05-17', agrupar='cliente')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('custos_lote', sql.lower())
        self.assertIn('CODTIPOPER IN (11, 13)', sql)
        # Vendas filtram TOP 35/37 + STATUSNOTA='L'
        self.assertIn('CODTIPOPER IN (35, 37)', sql)
        self.assertIn("STATUSNOTA = 'L'", sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_agrupar_cliente_agrupa_por_matriz(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        consultar_margem_por_venda('2026-05-01', '2026-05-17', agrupar='cliente')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('CODPARCMATRIZ', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_agrupar_produto_agrupa_por_codprod(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        consultar_margem_por_venda('2026-05-01', '2026-05-17', agrupar='produto')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('pr.CODPROD', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_agrupar_invalido_cai_em_cliente(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        consultar_margem_por_venda('2026-05-01', '2026-05-17', agrupar='hackz')
        sql = cursor.execute.call_args[0][0]
        # Cai em cliente — matriz aparece no GROUP BY
        self.assertIn('CODPARCMATRIZ', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_calcula_margem_e_totais(self, mock_obter):
        """Cliente A: receita 10k, custo 7k → lucro 3k, margem 30%."""
        self._mock(mock_obter, [
            (588, 'ASSAI',  10000.0, 7000.0, 1000.0),
            (601, 'EXTRA',   5000.0, 4000.0,  500.0),
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        out = consultar_margem_por_venda('2026-05-01', '2026-05-17')

        self.assertEqual(len(out['linhas']), 2)
        l0 = out['linhas'][0]
        self.assertEqual(l0['receita'], 10000.0)
        self.assertEqual(l0['custo'],   7000.0)
        self.assertEqual(l0['lucro'],   3000.0)
        self.assertAlmostEqual(l0['margem_pct'], 30.0, places=2)
        # Totais
        self.assertEqual(out['total_receita'], 15000.0)
        self.assertEqual(out['total_custo'],   11000.0)
        self.assertEqual(out['total_lucro'],    4000.0)
        self.assertAlmostEqual(out['margem_media'], 4000/15000*100, places=2)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_receita_zero_nao_divide_por_zero(self, mock_obter):
        self._mock(mock_obter, [
            (588, 'ASSAI', 0.0, 0.0, 0.0),
        ])
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        out = consultar_margem_por_venda('2026-05-01', '2026-05-17')
        self.assertEqual(out['linhas'][0]['margem_pct'], 0.0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_vazio(self, mock_obter):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception('ORA-XXXXX')
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        from sankhya_integration.services.oracle_conn import consultar_margem_por_venda
        out = consultar_margem_por_venda('2026-05-01', '2026-05-17')
        self.assertEqual(out['linhas'], [])


# --------------------------------------------------------------------------
# View api_relatorio_margem_venda (com cache)
# --------------------------------------------------------------------------

class ApiMargemVendaViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['9'])
        self.url = '/sankhya/relatorios/api/margem-venda/'
        # Limpa cache entre tests (isolação)
        from django.core.cache import cache
        cache.clear()

    def test_sem_datas_retorna_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.services.oracle_conn.consultar_margem_por_venda')
    def test_payload_valido(self, mock_fn):
        mock_fn.return_value = {
            'linhas': [], 'total_receita': 0, 'total_custo': 0,
            'total_lucro': 0, 'margem_media': 0,
        }
        resp = self.client.get(self.url + '?date_de=2026-05-01&date_ate=2026-05-17')
        self.assertEqual(resp.status_code, 200)
        mock_fn.assert_called_once_with('2026-05-01', '2026-05-17', agrupar='cliente')

    @patch('sankhya_integration.services.oracle_conn.consultar_margem_por_venda')
    def test_cache_evita_segundo_fetch(self, mock_fn):
        """2 requests iguais consecutivos → backend chamado 1× só."""
        mock_fn.return_value = {
            'linhas': [], 'total_receita': 0, 'total_custo': 0,
            'total_lucro': 0, 'margem_media': 0,
        }
        url = self.url + '?date_de=2026-05-01&date_ate=2026-05-17'
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(mock_fn.call_count, 1)

    @patch('sankhya_integration.services.oracle_conn.consultar_margem_por_venda')
    def test_nocache_forca_refetch(self, mock_fn):
        mock_fn.return_value = {
            'linhas': [], 'total_receita': 0, 'total_custo': 0,
            'total_lucro': 0, 'margem_media': 0,
        }
        url = self.url + '?date_de=2026-05-01&date_ate=2026-05-17'
        self.client.get(url)
        self.client.get(url + '&nocache=1')
        self.assertEqual(mock_fn.call_count, 2)

    @patch('sankhya_integration.services.oracle_conn.consultar_margem_por_venda')
    def test_agrupar_diferente_chave_cache_diferente(self, mock_fn):
        """Cliente e produto têm chaves de cache distintas."""
        mock_fn.return_value = {
            'linhas': [], 'total_receita': 0, 'total_custo': 0,
            'total_lucro': 0, 'margem_media': 0,
        }
        base = '?date_de=2026-05-01&date_ate=2026-05-17'
        self.client.get(self.url + base + '&agrupar=cliente')
        self.client.get(self.url + base + '&agrupar=produto')
        # 2 chamadas — chaves de cache distintas
        self.assertEqual(mock_fn.call_count, 2)


# ==========================================================================
# DRILLDOWN — polish v1.1 (Mai/2026 — 2026-05-30)
# ==========================================================================

class ConsultarDrilldownServiceTest(TestCase):
    """Switch interno por tipo. Tudo SELECT puro."""

    def _mock(self, mock_obter, fetchall):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_obter.return_value.__enter__.return_value = conn
        mock_obter.return_value.__exit__.return_value = None
        return cursor

    def test_tipo_invalido_retorna_vazio(self):
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        out = consultar_drilldown_relatorio('inexistente', 123)
        self.assertEqual(out['linhas'], [])
        self.assertEqual(out['tipo'], 'inexistente')

    def test_id_vazio_retorna_vazio(self):
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        out = consultar_drilldown_relatorio('cliente_vendas', '')
        self.assertEqual(out['linhas'], [])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_cliente_vendas_sem_data_retorna_vazio(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        out = consultar_drilldown_relatorio('cliente_vendas', 588)
        self.assertEqual(out['linhas'], [])
        mock_obter.assert_not_called()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_cliente_vendas_filtra_codparc_e_top(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        consultar_drilldown_relatorio('cliente_vendas', 588,
                                       date_de='2026-05-01', date_ate='2026-05-30')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('matriz.CODPARC = :cp', sql)
        self.assertIn('CODTIPOPER IN (35, 37)', sql)
        self.assertIn("STATUSNOTA = 'L'", sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_movs_filtra_codagregacao(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        consultar_drilldown_relatorio('lote_movs', '113821S01D260527')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('i.CODAGREGACAO = :lote', sql)
        self.assertIn("STATUSNOTA <> 'E'", sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_bucket_atrasado_filtra_dtvenc_passado(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        consultar_drilldown_relatorio('fluxo_bucket', 'ATRASADO')
        sql = cursor.execute.call_args[0][0]
        self.assertIn('TRUNC(f.DTVENC) < TRUNC(SYSDATE)', sql)
        # Filtra em aberto via sentinel 01/01/1998
        self.assertIn("'01/01/1998'", sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_fluxo_bucket_invalido_retorna_vazio(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        out = consultar_drilldown_relatorio('fluxo_bucket', 'BUCKET_INVENTADO')
        self.assertEqual(out['linhas'], [])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_margem_detalhe_extras_agrupar_produto(self, mock_obter):
        cursor = self._mock(mock_obter, [])
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        consultar_drilldown_relatorio('margem_detalhe', 351,
                                       date_de='2026-05-01', date_ate='2026-05-30',
                                       extras={'agrupar': 'produto'})
        sql = cursor.execute.call_args[0][0]
        self.assertIn('i.CODPROD = :cod', sql)
        # CTE custos_lote presente (reusa cálculo do relatório principal)
        self.assertIn('custos_lote', sql.lower())

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_falha_oracle_retorna_vazio(self, mock_obter):
        mock_obter.side_effect = Exception('Oracle down')
        from sankhya_integration.services.oracle_conn import consultar_drilldown_relatorio
        out = consultar_drilldown_relatorio('cliente_vendas', 588,
                                             date_de='2026-05-01', date_ate='2026-05-30')
        self.assertEqual(out['linhas'], [])


class ApiDrilldownEndpointTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])
        self.url = '/sankhya/relatorios/api/drilldown/'

    def test_tipo_ausente_retorna_400(self):
        resp = self.client.get(self.url + '?id=1')
        self.assertEqual(resp.status_code, 400)

    def test_tipo_invalido_retorna_400(self):
        resp = self.client.get(self.url + '?tipo=hackz&id=1')
        self.assertEqual(resp.status_code, 400)

    def test_id_ausente_retorna_400(self):
        resp = self.client.get(self.url + '?tipo=cliente_vendas')
        self.assertEqual(resp.status_code, 400)

    def test_id_nao_numerico_em_tipo_numerico_retorna_400(self):
        resp = self.client.get(self.url + '?tipo=cliente_vendas&id=abc')
        self.assertEqual(resp.status_code, 400)

    def test_lote_movs_aceita_id_string(self):
        """lote_movs usa CODAGREGACAO (string), não exige numérico."""
        with patch('sankhya_integration.services.oracle_conn.consultar_drilldown_relatorio') as mock_fn:
            mock_fn.return_value = {
                'tipo': 'lote_movs', 'titulo': '', 'subtitulo': '',
                'colunas': [], 'linhas': [], 'totais': {},
            }
            resp = self.client.get(self.url + '?tipo=lote_movs&id=113821S01D260527')
            self.assertEqual(resp.status_code, 200)
            mock_fn.assert_called_once()
            # ID passa como string pro service
            args, kwargs = mock_fn.call_args
            self.assertEqual(args[1], '113821S01D260527')

    def test_fluxo_bucket_aceita_label_string(self):
        with patch('sankhya_integration.services.oracle_conn.consultar_drilldown_relatorio') as mock_fn:
            mock_fn.return_value = {
                'tipo': 'fluxo_bucket', 'titulo': '', 'subtitulo': '',
                'colunas': [], 'linhas': [], 'totais': {},
            }
            resp = self.client.get(self.url + '?tipo=fluxo_bucket&id=ATRASADO')
            self.assertEqual(resp.status_code, 200)
            args, kwargs = mock_fn.call_args
            self.assertEqual(args[1], 'ATRASADO')

    def test_margem_detalhe_repasse_agrupar(self):
        with patch('sankhya_integration.services.oracle_conn.consultar_drilldown_relatorio') as mock_fn:
            mock_fn.return_value = {
                'tipo': 'margem_detalhe', 'titulo': '', 'subtitulo': '',
                'colunas': [], 'linhas': [], 'totais': {},
            }
            resp = self.client.get(
                self.url + '?tipo=margem_detalhe&id=351&date_de=2026-05-01'
                '&date_ate=2026-05-30&agrupar=produto'
            )
            self.assertEqual(resp.status_code, 200)
            _, kwargs = mock_fn.call_args
            self.assertEqual(kwargs['extras']['agrupar'], 'produto')

    def test_sem_sessao_bloqueia(self):
        c = Client()  # sem login
        resp = c.get(self.url + '?tipo=cliente_vendas&id=1')
        self.assertIn(resp.status_code, (302, 403))
