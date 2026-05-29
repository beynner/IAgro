"""Tests do módulo Caixas (Mai/2026 — 2026-05-18).

Cobertura Cat A (Bloco A — leituras + página + endpoints stub de Cat B):
  - AcessoCaixasTest             — quem pode entrar na tela
  - ConsultarSaldoCaixasServiceTest — função service de saldo
  - ObterTimelineCaixasServiceTest  — função service de timeline
  - ListarColetasCaixasServiceTest  — função service de paginação coletas
  - ListarProdutosCaixaServiceTest  — função service de cadastro
  - ApiCaixasSaldoViewTest          — endpoint GET saldo
  - ApiCaixasTimelineViewTest       — endpoint GET timeline
  - ApiCaixasColetasListarViewTest  — endpoint GET coletas
  - ApiCaixasProdutosListarViewTest — endpoint GET produtos
  - StubsCatBCaixasTest             — B1/B2/B3 retornam 501 com pendente_cat_b
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
# AcessoCaixasTest — grupos permitidos: 1, 6, 8, 9, 10, 11
# --------------------------------------------------------------------------

class AcessoCaixasTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/sankhya/caixas/'

    def test_diretoria_acessa(self):
        _login_session(self.client, grupos=['1'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_suporte_acessa(self):
        _login_session(self.client, grupos=['6'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_packing_acessa(self):
        _login_session(self.client, grupos=['8'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_comercial_acessa(self):
        _login_session(self.client, grupos=['9'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_administrativo_acessa(self):
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_frota_acessa(self):
        _login_session(self.client, grupos=['11'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_sem_sessao_nao_acessa(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))


# --------------------------------------------------------------------------
# ConsultarSaldoCaixasServiceTest
# --------------------------------------------------------------------------

class ConsultarSaldoCaixasServiceTest(TestCase):
    """Função service consultar_saldo_caixas."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_saldo_basico(self, _mock_existe, mock_conn):
        """Saldo via Logística (AD_VIAGEM_*) + coletas em AD_COLETA_CAIXAS.

        Mai/2026 — 2026-05-29: TOP 35/37 e TOP 36 NÃO contam mais.
        """
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            # Saídas via Logística (AD_VIAGEM_DESTINO agregadas)
            [
                (123, 'ASSAI CEILANDIA', 100, dt.datetime(2026, 5, 17)),
                (456, 'PAO DE ACUCAR', 60, dt.datetime(2026, 5, 16)),
            ],
            # Coletas
            [
                (123, 'COLETA', 30, dt.datetime(2026, 5, 17)),
                (123, 'QUEBRA', 5, dt.datetime(2026, 5, 16)),
                (456, 'COLETA', 60, dt.datetime(2026, 5, 18)),  # PAO zera todo
            ],
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas()

        # ASSAI: 100 viagens - 30 coleta - 5 quebra = 65
        # PAO:   60 viagens - 60 coleta = 0 (escondido)
        codparcs = [l['codparc'] for l in linhas]
        self.assertIn(123, codparcs)
        self.assertNotIn(456, codparcs)  # saldo 0 escondido por default
        l = next(l for l in linhas if l['codparc'] == 123)
        self.assertEqual(l['caixas_enviadas'], 100)
        self.assertEqual(l['caixas_coletadas'], 30)
        self.assertEqual(l['caixas_quebradas'], 5)
        self.assertEqual(l['saldo'], 65)
        self.assertEqual(l['caixas_devolvidas'], 0)   # legado, sempre 0
        self.assertFalse(l['sem_peso'])                # legado, sempre False

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_incluir_saldo_zerado(self, _mock_existe, mock_conn):
        """Quando apenas_saldo_positivo=False, cliente com saldo 0 ainda aparece."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(456, 'PAO DE ACUCAR', 60, dt.datetime(2026, 5, 16))],   # saídas via Logística
            [(456, 'COLETA', 60, dt.datetime(2026, 5, 18))],           # coletas zeram
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas(filtros={'apenas_saldo_positivo': False})
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]['saldo'], 0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=False)
    def test_schema_resilient_sem_tabela_coleta(self, _mock_existe, mock_conn):
        """Quando AD_COLETA_CAIXAS não existe, retorna só saídas via Logística."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(123, 'ASSAI', 100, dt.datetime(2026, 5, 17))],
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas()
        # _existe_coluna=False bloqueia a 2ª query (coletas); só roda saídas
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertEqual(linhas[0]['saldo'], 100)
        self.assertEqual(linhas[0]['caixas_coletadas'], 0)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle',
           side_effect=Exception('Oracle off'))
    def test_falha_oracle_retorna_lista_vazia(self, _mock):
        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        self.assertEqual(consultar_saldo_caixas(), [])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_ajuste_saldo_soma_no_total(self, _mock_existe, mock_conn):
        """AJUSTE_SALDO entra na fórmula somando (positivo soma, negativo desconta)."""
        cursor = MagicMock()
        # 100 viagens + ajuste +50 (caixas legadas) − coleta 30 = 120
        cursor.fetchall.side_effect = [
            # Saídas Logística
            [(123, 'CLIENTE TESTE', 100, dt.datetime(2026, 5, 17))],
            # Coletas (motivos misturados)
            [
                (123, 'COLETA', 30, dt.datetime(2026, 5, 18)),
                (123, 'AJUSTE_SALDO', 50, dt.datetime(2026, 5, 18)),
            ],
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas()
        self.assertEqual(len(linhas), 1)
        l = linhas[0]
        # 100 viagens - 30 coleta + 50 ajuste = 120
        self.assertEqual(l['caixas_enviadas'], 100)
        self.assertEqual(l['caixas_coletadas'], 30)
        self.assertEqual(l['caixas_ajuste'], 50)
        self.assertEqual(l['saldo'], 120)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_ajuste_saldo_negativo_desconta(self, _mock_existe, mock_conn):
        """AJUSTE_SALDO com qtd negativa desconta do saldo."""
        cursor = MagicMock()
        # 100 viagens + ajuste -10 = 90 saldo
        cursor.fetchall.side_effect = [
            [(123, 'CLIENTE TESTE', 100, dt.datetime(2026, 5, 17))],
            [(123, 'AJUSTE_SALDO', -10, dt.datetime(2026, 5, 18))],
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas()
        l = linhas[0]
        self.assertEqual(l['caixas_ajuste'], -10)
        self.assertEqual(l['saldo'], 90)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_cliente_so_com_ajuste_entra_no_resultado(self, _mock_existe, mock_conn):
        """Cliente sem viagens mas com AJUSTE_SALDO entra (saldo inicial puro)."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [],                                                       # nenhuma viagem
            [(999, 'AJUSTE_SALDO', 80, dt.datetime(2026, 5, 18))],   # só ajuste
            [(999, 'CLIENTE LEGADO')],                                # SELECT NOMEPARC pros órfãos
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas()
        self.assertEqual(len(linhas), 1)
        l = linhas[0]
        self.assertEqual(l['codparc'], 999)
        self.assertEqual(l['nomeparc'], 'CLIENTE LEGADO')
        self.assertEqual(l['caixas_enviadas'], 0)
        self.assertEqual(l['caixas_ajuste'], 80)
        self.assertEqual(l['saldo'], 80)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_sem_peso_sempre_false_legado(self, _mock_existe, mock_conn):
        """Mai/2026 — 2026-05-29: flag sem_peso legada SEMPRE retorna False
        (bloco fantasma removido com migração pra Logística)."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(123, 'ASSAI', 100, dt.datetime(2026, 5, 17))],   # viagens
            [],                                                  # coletas
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas(filtros={'apenas_saldo_positivo': False})
        self.assertEqual(len(linhas), 1)
        self.assertFalse(linhas[0]['sem_peso'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_sem_viagens_e_sem_coletas_retorna_vazio(self, _mock_existe, mock_conn):
        """Sem viagens cadastradas e sem coletas — retorno vazio."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [],   # viagens
            [],   # coletas
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas()
        self.assertEqual(linhas, [])
        # 2 execute: viagens + coletas (sem bloco fantasma)
        self.assertEqual(cursor.execute.call_count, 2)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_filtro_codparc_drill_down(self, _mock_existe, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(123, 'ASSAI', 100, dt.datetime(2026, 5, 17))],   # viagens
            [],                                                  # coletas
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import consultar_saldo_caixas
        linhas = consultar_saldo_caixas(filtros={'codparc': 123})
        # Confirma que o bind codparc=123 foi enviado em todas as queries
        for call in cursor.execute.call_args_list:
            binds = call.args[1] if len(call.args) > 1 else {}
            if 'codparc' in binds:
                self.assertEqual(binds['codparc'], 123)
        self.assertEqual(len(linhas), 1)


# --------------------------------------------------------------------------
# ObterTimelineCaixasServiceTest
# --------------------------------------------------------------------------

class ObterTimelineCaixasServiceTest(TestCase):
    def test_sem_codparc_retorna_vazio(self):
        from sankhya_integration.services.oracle_conn import obter_timeline_caixas
        self.assertEqual(obter_timeline_caixas(0), [])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_eventos_combinados(self, _mock_existe, mock_conn):
        """Timeline mistura VIAGEM (Logística) + COLETA (manual).

        Mai/2026 — 2026-05-29: tipo SAIDA (TOP 35/37) e DEVOLUCAO (TOP 36) removidos.
        """
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            # Viagens (AD_VIAGEM_ENTREGA + AD_VIAGEM_DESTINO)
            # cols: DATA_VIAGEM, ID, NUM_VIAGEM, QTD_CAIXAS, PLACA, MARCAMODELO,
            #       motorista_nome, OBS_VIAGEM, OBS_DESTINO, HORA_SAIDA
            [(
                dt.datetime(2026, 5, 15), 42, 7, 100,
                'OVT0B50', 'VW/10.160 DRC 4X2',
                'WELLINGTON SILVA LEMOS', 'sem obs', None, '06:00',
            )],
            # Coletas — schema novo (11 cols, +CODPARC_MOTORISTA +MOTORISTA_NOME)
            [(7, dt.datetime(2026, 5, 17), 'COLETA', 30, 'motorista trouxe',
              'N', 1, 'TESTE', None, 24, 'WELLINGTON SILVA LEMOS')],
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import obter_timeline_caixas
        eventos = obter_timeline_caixas(codparc=123, dias=30)
        tipos = sorted([e['tipo'] for e in eventos])
        self.assertEqual(tipos, ['COLETA', 'VIAGEM'])

        ev_viagem = next(e for e in eventos if e['tipo'] == 'VIAGEM')
        self.assertEqual(ev_viagem['qtd_caixas'], 100)
        self.assertEqual(ev_viagem['num_viagem'], 7)
        self.assertEqual(ev_viagem['viagem_id'], 42)
        self.assertEqual(ev_viagem['placa'], 'OVT0B50')
        self.assertEqual(ev_viagem['motorista'], 'WELLINGTON SILVA LEMOS')
        self.assertEqual(ev_viagem['hora_saida'], '06:00')
        # Campos legados zerados em VIAGEM
        self.assertIsNone(ev_viagem['nunota'])
        self.assertIsNone(ev_viagem['top'])
        # Descrição = "Placa X · modelo"
        self.assertIn('OVT0B50', ev_viagem['descricao'])
        self.assertIn('VW/10.160', ev_viagem['descricao'])

        ev_coleta = next(e for e in eventos if e['tipo'] == 'COLETA')
        self.assertEqual(ev_coleta['estornado'], False)
        self.assertEqual(ev_coleta['id_coleta'], 7)
        # Motorista (Mai/2026 — 2026-05-29): retornado pra exibir na timeline
        self.assertEqual(ev_coleta['motorista_codparc'], 24)
        self.assertEqual(ev_coleta['motorista_nome'], 'WELLINGTON SILVA LEMOS')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_ordem_intra_dia_viagem_antes_coleta(self, _mock_existe, mock_conn):
        """Mesmo dia: VIAGEM acima de COLETA na timeline DESC (cronologia).

        Operador entrega → coleta depois. Timeline mostra "primeiro entreguei,
        depois recolhi". Mai/2026 — 2026-05-29.
        """
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            # Viagem hoje + viagem ontem (datas diferentes pra ordem primária)
            [
                (dt.datetime(2026, 5, 26), 42, 7, 100,
                 'OVT0B50', 'VW', 'WELLINGTON', None, None, '06:00'),
                (dt.datetime(2026, 5, 25), 41, 6, 50,
                 'PBW', 'MB', 'ALVERI', None, None, '03:00'),
            ],
            # Coleta hoje + coleta ontem (mesmo dia que as viagens) — schema novo (11 cols)
            [
                (7, dt.datetime(2026, 5, 26), 'COLETA', 30, 'obs', 'N', 1, 'OPERADOR', None, None, None),
                (8, dt.datetime(2026, 5, 25), 'COLETA', 20, 'obs', 'N', 1, 'OPERADOR', None, None, None),
            ],
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import obter_timeline_caixas
        eventos = obter_timeline_caixas(codparc=123, dias=30)

        # Ordem esperada (DESC por data, intra-dia: VIAGEM antes COLETA):
        #   1. 26/05 VIAGEM (mais recente, viagem do dia)
        #   2. 26/05 COLETA (mais recente, coleta do dia — depois da viagem)
        #   3. 25/05 VIAGEM (mais antiga, viagem do dia)
        #   4. 25/05 COLETA (mais antiga, coleta do dia — depois da viagem)
        ordem = [(e['data'], e['tipo']) for e in eventos]
        self.assertEqual(ordem, [
            ('2026-05-26', 'VIAGEM'),
            ('2026-05-26', 'COLETA'),
            ('2026-05-25', 'VIAGEM'),
            ('2026-05-25', 'COLETA'),
        ])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle',
           side_effect=Exception('Oracle off'))
    def test_falha_oracle_retorna_vazio(self, _mock):
        from sankhya_integration.services.oracle_conn import obter_timeline_caixas
        self.assertEqual(obter_timeline_caixas(123), [])


# --------------------------------------------------------------------------
# ListarColetasCaixasServiceTest
# --------------------------------------------------------------------------

class ListarColetasCaixasServiceTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_lista_paginada(self, _mock_existe, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (1, 123, 'ASSAI', 30, dt.datetime(2026, 5, 17), 'COLETA', 'ok', 'N', 1, 'TESTE', dt.datetime(2026, 5, 17, 14, 0)),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import listar_coletas_caixas
        coletas = listar_coletas_caixas(filtros={'codparc': 123, 'motivo': 'COLETA'})
        self.assertEqual(len(coletas), 1)
        self.assertEqual(coletas[0]['motivo'], 'COLETA')
        self.assertEqual(coletas[0]['estornado'], False)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=False)
    def test_sem_tabela_retorna_vazio(self, _mock_existe, mock_conn):
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import listar_coletas_caixas
        self.assertEqual(listar_coletas_caixas(), [])


# --------------------------------------------------------------------------
# ListarProdutosCaixaServiceTest
# --------------------------------------------------------------------------

class ListarProdutosCaixaServiceTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=True)
    def test_lista_filtra_por_tipo(self, _mock_existe, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (8117, 'PIMENTAO VERDE', 'KG', 'PLASTICA', 1, 'TESTE',
             dt.datetime(2026, 5, 17, 14, 0), None),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import listar_produtos_caixa
        prods = listar_produtos_caixa(tipo='PLASTICA')
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0]['tipo_caixa'], 'PLASTICA')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=False)
    def test_sem_tabela_retorna_vazio(self, _mock_existe, mock_conn):
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import listar_produtos_caixa
        self.assertEqual(listar_produtos_caixa(), [])


# --------------------------------------------------------------------------
# ApiCaixasSaldoViewTest
# --------------------------------------------------------------------------

class ApiCaixasSaldoViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/sankhya/caixas/api/saldo/'

    @patch('sankhya_integration.views.consultar_saldo_caixas')
    def test_retorno_padrao(self, mock_fn):
        mock_fn.return_value = [
            {'codparc': 123, 'nomeparc': 'ASSAI', 'saldo': 80,
             'caixas_enviadas': 150, 'caixas_devolvidas': 10,
             'caixas_coletadas': 60, 'caixas_perdidas': 0, 'caixas_quebradas': 0,
             'ultima_saida': '2026-05-17', 'ultima_coleta': '2026-05-18'},
        ]
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total_clientes'], 1)
        self.assertEqual(data['total_caixas'], 80)

    def test_codparc_invalido_400(self):
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url + '?codparc=abc')
        self.assertEqual(resp.status_code, 400)

    def test_sem_sessao_redireciona(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))


# --------------------------------------------------------------------------
# ApiCaixasTimelineViewTest
# --------------------------------------------------------------------------

class ApiCaixasTimelineViewTest(TestCase):
    @patch('sankhya_integration.views.obter_timeline_caixas')
    def test_payload_com_dias(self, mock_fn):
        mock_fn.return_value = [{'tipo': 'SAIDA', 'data': '2026-05-17', 'qtd_caixas': 50}]
        _login_session(self.client, grupos=['9'])
        resp = self.client.get('/sankhya/caixas/api/timeline/123/?dias=60')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['dias'], 60)
        mock_fn.assert_called_once_with(codparc=123, dias=60)

    @patch('sankhya_integration.views.obter_timeline_caixas')
    def test_dias_default_90(self, mock_fn):
        mock_fn.return_value = []
        _login_session(self.client, grupos=['1'])
        self.client.get('/sankhya/caixas/api/timeline/123/')
        mock_fn.assert_called_once_with(codparc=123, dias=90)

    @patch('sankhya_integration.views.obter_timeline_caixas')
    def test_dias_clipado_730(self, mock_fn):
        mock_fn.return_value = []
        _login_session(self.client, grupos=['1'])
        self.client.get('/sankhya/caixas/api/timeline/123/?dias=999999')
        mock_fn.assert_called_once_with(codparc=123, dias=730)


# --------------------------------------------------------------------------
# ApiCaixasColetasListarViewTest
# --------------------------------------------------------------------------

class ApiCaixasColetasListarViewTest(TestCase):
    @patch('sankhya_integration.views.listar_coletas_caixas')
    def test_payload(self, mock_fn):
        mock_fn.return_value = [
            {'id': 1, 'codparc': 123, 'nomeparc': 'ASSAI', 'qtd_caixas': 30,
             'data_coleta': '2026-05-17', 'motivo': 'COLETA', 'observacao': '',
             'estornado': False, 'codusu': 1, 'nomeusu': 'TESTE', 'criado_em': '2026-05-17 14:00'},
        ]
        _login_session(self.client, grupos=['1'])
        resp = self.client.get('/sankhya/caixas/api/coletas/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['coletas']), 1)


# --------------------------------------------------------------------------
# ApiCaixasProdutosListarViewTest
# --------------------------------------------------------------------------

class ApiCaixasProdutosListarViewTest(TestCase):
    @patch('sankhya_integration.views.listar_produtos_caixa')
    def test_filtro_tipo(self, mock_fn):
        mock_fn.return_value = []
        _login_session(self.client, grupos=['1'])
        self.client.get('/sankhya/caixas/api/produtos/?tipo=PAPELAO')
        mock_fn.assert_called_once_with(tipo='PAPELAO')

    @patch('sankhya_integration.views.listar_produtos_caixa')
    def test_tipo_invalido_vira_none(self, mock_fn):
        mock_fn.return_value = []
        _login_session(self.client, grupos=['1'])
        self.client.get('/sankhya/caixas/api/produtos/?tipo=XYZ')
        mock_fn.assert_called_once_with(tipo=None)


# --------------------------------------------------------------------------
# CriarColetaServiceTest (B1)
# --------------------------------------------------------------------------

class CriarColetaServiceTest(TestCase):
    def test_validacoes_basicas(self):
        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        # Sem codparc
        r = criar_coleta_caixas_banco({'qtd_caixas': 5, 'data_coleta': '2026-05-18', 'motivo': 'COLETA'}, codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('codparc', r['error'])

        # Qtd zero
        r = criar_coleta_caixas_banco({'codparc': 123, 'qtd_caixas': 0, 'data_coleta': '2026-05-18', 'motivo': 'COLETA'}, codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('qtd_caixas', r['error'])

        # Motivo inválido
        r = criar_coleta_caixas_banco({'codparc': 123, 'qtd_caixas': 5, 'data_coleta': '2026-05-18', 'motivo': 'XYZ'}, codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('motivo', r['error'])

        # Data futura
        r = criar_coleta_caixas_banco({'codparc': 123, 'qtd_caixas': 5, 'data_coleta': '2099-12-31', 'motivo': 'COLETA'}, codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('futura', r['error'])

        # AJUSTE_SALDO com qtd=0 é bloqueado
        r = criar_coleta_caixas_banco({'codparc': 123, 'qtd_caixas': 0, 'data_coleta': '2026-05-18', 'motivo': 'AJUSTE_SALDO'}, codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('AJUSTE_SALDO', r['error'])

    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_ajuste_saldo_positivo(self, mock_conn, _mock_audit):
        """AJUSTE_SALDO com qtd positiva passa (saldo inicial)."""
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)  # cliente existe
        var_obj = MagicMock()
        var_obj.getvalue.return_value = [100]
        cursor.var.return_value = var_obj
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': 80, 'data_coleta': '2026-05-18',
             'motivo': 'AJUSTE_SALDO', 'observacao': 'saldo inicial — cliente já tinha 80 caixas'},
            codusu=1, nomeusu='TESTE',
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['id'], 100)

    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_ajuste_saldo_negativo(self, mock_conn, _mock_audit):
        """AJUSTE_SALDO com qtd negativa passa (caixa sumiu sem motivo registrado)."""
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        var_obj = MagicMock()
        var_obj.getvalue.return_value = [101]
        cursor.var.return_value = var_obj
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': -5, 'data_coleta': '2026-05-18',
             'motivo': 'AJUSTE_SALDO', 'observacao': '5 caixas a menos no balanço físico'},
            codusu=1, nomeusu='TESTE',
        )
        self.assertTrue(r['ok'])

    def test_coleta_normal_nao_aceita_negativo(self):
        """COLETA/QUEBRA/PERDA continuam exigindo qtd > 0."""
        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        for motivo in ('COLETA', 'QUEBRA', 'PERDA'):
            r = criar_coleta_caixas_banco(
                {'codparc': 123, 'qtd_caixas': -5, 'data_coleta': '2026-05-18', 'motivo': motivo},
                codusu=1,
            )
            self.assertFalse(r['ok'], f"motivo={motivo} deveria bloquear qtd<0")
            self.assertIn('> 0', r['error'])

    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=False)
    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_insere_com_sucesso(self, mock_conn, _mock_audit, _mock_existe):
        cursor = MagicMock()
        # Sequência de fetchone:
        #   1. SELECT 1 FROM TGFPAR — cliente existe
        #   2. SELECT motorista — está cadastrado como tipo MOTORISTA
        cursor.fetchone.side_effect = [
            (1,),
            ('WELLINGTON SILVA LEMOS',),
        ]
        var_obj = MagicMock()
        var_obj.getvalue.return_value = [42]
        cursor.var.return_value = var_obj
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': 30, 'data_coleta': '2026-05-18',
             'motivo': 'COLETA', 'observacao': 'motorista trouxe',
             'codparc_motorista': 24},
            codusu=1, nomeusu='TESTE',
        )
        self.assertTrue(r['ok'], r.get('error'))
        self.assertEqual(r['id'], 42)
        conn.commit.assert_called_once()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_codparc_inexistente(self, mock_conn):
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # cliente não existe
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        # Motivo QUEBRA (não exige motorista) — o teste é sobre cliente inexistente
        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 999999, 'qtd_caixas': 5, 'data_coleta': '2026-05-18', 'motivo': 'QUEBRA'},
            codusu=1,
        )
        self.assertFalse(r['ok'])
        self.assertIn('não encontrado', r['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_coleta_sem_motorista_rejeita(self, _mock):
        """COLETA exige motorista — Mai/2026 — 2026-05-29."""
        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': 30, 'data_coleta': '2026-05-18', 'motivo': 'COLETA'},
            codusu=1,
        )
        self.assertFalse(r['ok'])
        self.assertIn('motorista', r['error'].lower())

    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=False)
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_motorista_nao_cadastrado_rejeita(self, mock_conn, _mock_existe):
        """Parceiro existe mas não tem tipo MOTORISTA → erro humanizado."""
        cursor = MagicMock()
        # cliente existe + motorista NÃO está em AD_PARCEIRO_TIPO
        cursor.fetchone.side_effect = [(1,), None]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': 30, 'data_coleta': '2026-05-18',
             'motivo': 'COLETA', 'codparc_motorista': 9999},
            codusu=1,
        )
        self.assertFalse(r['ok'])
        self.assertIn('motorista', r['error'].lower())
        self.assertIn('cadastr', r['error'].lower())

    @patch('sankhya_integration.services.oracle_conn._existe_coluna', return_value=False)
    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_quebra_sem_motorista_aceita(self, mock_conn, _mock_audit, _mock_existe):
        """QUEBRA/PERDA/AJUSTE não exigem motorista."""
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)   # só cliente — não há segundo fetchone de motorista
        var_obj = MagicMock()
        var_obj.getvalue.return_value = [99]
        cursor.var.return_value = var_obj
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': 2, 'data_coleta': '2026-05-18', 'motivo': 'QUEBRA'},
            codusu=1,
        )
        self.assertTrue(r['ok'], r.get('error'))
        self.assertEqual(r['id'], 99)

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=False)
    def test_bloqueia_quando_escrita_desabilitada(self, _mock):
        from sankhya_integration.services.oracle_conn import criar_coleta_caixas_banco
        r = criar_coleta_caixas_banco(
            {'codparc': 123, 'qtd_caixas': 5, 'data_coleta': '2026-05-18', 'motivo': 'COLETA'},
            codusu=1,
        )
        self.assertFalse(r['ok'])
        self.assertIn('Escrita desabilitada', r['error'])


# --------------------------------------------------------------------------
# EstornarColetaServiceTest (B2)
# --------------------------------------------------------------------------

class EstornarColetaServiceTest(TestCase):
    def test_motivo_vazio_bloqueia(self):
        from sankhya_integration.services.oracle_conn import estornar_coleta_caixas_banco
        r = estornar_coleta_caixas_banco(id_coleta=42, motivo_estorno='', codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('motivo', r['error'].lower())

    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_estorna_com_sucesso(self, mock_conn, _mock_audit):
        cursor = MagicMock()
        # SELECT FOR UPDATE retorna linha não estornada
        cursor.fetchone.return_value = (123, 30, dt.datetime(2026, 5, 17), 'COLETA', 'N')
        cursor.rowcount = 1
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import estornar_coleta_caixas_banco
        r = estornar_coleta_caixas_banco(id_coleta=42, motivo_estorno='Errei o cliente', codusu=1, nomeusu='TESTE')
        self.assertTrue(r['ok'])
        conn.commit.assert_called_once()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_id_inexistente(self, mock_conn):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import estornar_coleta_caixas_banco
        r = estornar_coleta_caixas_banco(id_coleta=99999, motivo_estorno='X', codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('não encontrada', r['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_ja_estornada_bloqueia(self, mock_conn):
        cursor = MagicMock()
        cursor.fetchone.return_value = (123, 30, dt.datetime(2026, 5, 17), 'COLETA', 'S')
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import estornar_coleta_caixas_banco
        r = estornar_coleta_caixas_banco(id_coleta=42, motivo_estorno='X', codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('já foi estornada', r['error'])


# --------------------------------------------------------------------------
# UpsertProdutoCaixaServiceTest (B3)
# --------------------------------------------------------------------------

class UpsertProdutoCaixaServiceTest(TestCase):
    def test_tipo_invalido(self):
        from sankhya_integration.services.oracle_conn import upsert_produto_caixa_banco
        r = upsert_produto_caixa_banco(codprod=100, tipo_caixa='XYZ', codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('tipo_caixa', r['error'])

    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_insert_novo_produto(self, mock_conn, _mock_audit):
        cursor = MagicMock()
        # 1ª: SELECT 1 FROM TGFPRO — existe; 2ª: SELECT TIPO_CAIXA — não existe
        cursor.fetchone.side_effect = [(1,), None]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import upsert_produto_caixa_banco
        r = upsert_produto_caixa_banco(codprod=8117, tipo_caixa='PLASTICA', codusu=1, nomeusu='TESTE')
        self.assertTrue(r['ok'])
        self.assertEqual(r['acao'], 'INSERT')
        conn.commit.assert_called_once()

    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_update_produto_existente(self, mock_conn, _mock_audit):
        cursor = MagicMock()
        # produto existe + já tem linha (era PLASTICA)
        cursor.fetchone.side_effect = [(1,), ('PLASTICA',)]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import upsert_produto_caixa_banco
        r = upsert_produto_caixa_banco(codprod=550, tipo_caixa='PAPELAO', codusu=1)
        self.assertTrue(r['ok'])
        self.assertEqual(r['acao'], 'UPDATE')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_codprod_inexistente(self, mock_conn):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import upsert_produto_caixa_banco
        r = upsert_produto_caixa_banco(codprod=999999, tipo_caixa='PLASTICA', codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('não encontrado', r['error'])


# --------------------------------------------------------------------------
# EndpointsCatBCaixasViewTest — endpoints chamam service e propagam
# --------------------------------------------------------------------------

class EndpointsCatBCaixasViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    @patch('sankhya_integration.views.criar_coleta_caixas_banco')
    def test_criar_sucesso(self, mock_fn):
        mock_fn.return_value = {'ok': True, 'id': 42}
        import json as _json
        resp = self.client.post(
            '/sankhya/caixas/api/coleta/criar/',
            data=_json.dumps({'codparc': 123, 'qtd_caixas': 30,
                              'data_coleta': '2026-05-18', 'motivo': 'COLETA'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], 42)
        mock_fn.assert_called_once()

    @patch('sankhya_integration.views.criar_coleta_caixas_banco')
    def test_criar_falha_400(self, mock_fn):
        mock_fn.return_value = {'ok': False, 'error': 'codparc obrigatório'}
        resp = self.client.post('/sankhya/caixas/api/coleta/criar/',
                                data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @patch('sankhya_integration.views.estornar_coleta_caixas_banco')
    def test_estornar_propaga_id(self, mock_fn):
        mock_fn.return_value = {'ok': True}
        import json as _json
        resp = self.client.post(
            '/sankhya/caixas/api/coleta/42/estornar/',
            data=_json.dumps({'motivo_estorno': 'Errei'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        # 1º arg keyword
        _, kw = mock_fn.call_args
        self.assertEqual(kw['id_coleta'], 42)
        self.assertEqual(kw['motivo_estorno'], 'Errei')

    @patch('sankhya_integration.views.upsert_produto_caixa_banco')
    def test_upsert_sucesso(self, mock_fn):
        mock_fn.return_value = {'ok': True, 'acao': 'INSERT'}
        import json as _json
        resp = self.client.post(
            '/sankhya/caixas/api/produto/upsert/',
            data=_json.dumps({'codprod': 8117, 'tipo_caixa': 'PAPELAO'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['acao'], 'INSERT')


# --------------------------------------------------------------------------
# RefreshPesosTempServiceTest (TEMPORÁRIO Mai/2026)
# Backfill TGFITE.PESO via moda TOP 26 — remover quando IAgro virar fluxo único
# --------------------------------------------------------------------------

class RefreshPesosTempServiceTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=False)
    def test_bloqueia_sem_permissao(self, _mock):
        from sankhya_integration.services.oracle_conn import popular_pesos_top34_35_37_via_moda_TEMP
        r = popular_pesos_top34_35_37_via_moda_TEMP(codusu=1)
        self.assertFalse(r['ok'])
        self.assertIn('Escrita desabilitada', r['error'])

    @patch('sankhya_integration.services.oracle_conn.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sucesso_reporta_linhas(self, mock_conn, _mock_audit):
        cursor = MagicMock()
        cursor.rowcount = 184224
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value.__enter__.return_value = conn

        from sankhya_integration.services.oracle_conn import popular_pesos_top34_35_37_via_moda_TEMP
        r = popular_pesos_top34_35_37_via_moda_TEMP(codusu=1, nomeusu='TESTE')
        self.assertTrue(r['ok'])
        self.assertEqual(r['linhas_atualizadas'], 184224)
        conn.commit.assert_called_once()

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle',
           side_effect=Exception('Oracle off'))
    def test_falha_oracle_retorna_erro(self, _mock):
        from sankhya_integration.services.oracle_conn import popular_pesos_top34_35_37_via_moda_TEMP
        r = popular_pesos_top34_35_37_via_moda_TEMP(codusu=1)
        self.assertFalse(r['ok'])


class RefreshPesosEndpointTest(TestCase):
    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['1'])

    @patch('sankhya_integration.views.popular_pesos_top34_35_37_via_moda_TEMP')
    def test_endpoint_sucesso(self, mock_fn):
        mock_fn.return_value = {'ok': True, 'linhas_atualizadas': 184224}
        resp = self.client.post('/sankhya/caixas/api/refresh-pesos/',
                                data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['linhas_atualizadas'], 184224)

    @patch('sankhya_integration.views.popular_pesos_top34_35_37_via_moda_TEMP')
    def test_endpoint_falha_propaga_400(self, mock_fn):
        mock_fn.return_value = {'ok': False, 'error': 'Escrita desabilitada'}
        resp = self.client.post('/sankhya/caixas/api/refresh-pesos/',
                                data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_exige_grupo_caixas(self):
        # operador sem nenhum dos grupos permitidos
        c = Client()
        _login_session(c, grupos=['99'])
        resp = c.post('/sankhya/caixas/api/refresh-pesos/',
                      data='{}', content_type='application/json')
        # redireciona pra home (302) ou bloqueia (403)
        self.assertIn(resp.status_code, (302, 403))
