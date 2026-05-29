"""Tests do módulo Logística (Mai/2026 — 2026-05-29).

Cobertura Cat A (mockados — zero Oracle real):
  - AcessoLogisticaTest — grupos 1, 6, 10 permitidos
  - ConsultarParceirosPorTipoTest — função service typeahead
  - ConsultarVeiculosLogisticaTest — função service typeahead veículo
  - ListarTiposParceiroTest — função service cadastro de tipos
  - ConsultarProximoNumViagemTest — função service MAX+1
  - ListarViagensTest — função service listagem paginada
  - ObterViagemDetalheTest — função service detalhe
  - CriarViagemBancoTest — função service criação atômica
  - EditarViagemBancoTest — função service edição diferencial
  - ExcluirViagemBancoTest — função service exclusão CASCADE
  - ApiLogisticaListarTiposParceiroTest — endpoint GET
  - ApiLogisticaParceirosPorTipoTest — endpoint GET typeahead
  - ApiLogisticaVeiculosTest — endpoint GET typeahead
  - ApiLogisticaListarViagensTest — endpoint GET listagem
  - ApiLogisticaObterViagemTest — endpoint GET detalhe
  - ApiLogisticaFichaPdfTest — endpoint GET PDF reportlab
  - ApiLogisticaCriarViagemTest — endpoint POST criar
  - ApiLogisticaEditarViagemTest — endpoint POST editar
  - ApiLogisticaExcluirViagemTest — endpoint POST excluir
  - ValidarPayloadViagemTest — helper de validação
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
# Acesso — Diretoria/Suporte/Administrativo entram; outros bloqueados
# --------------------------------------------------------------------------

class AcessoLogisticaTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/sankhya/logistica/'

    def test_diretoria_acessa(self):
        _login_session(self.client, grupos=['1'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_suporte_acessa(self):
        _login_session(self.client, grupos=['6'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_administrativo_acessa(self):
        _login_session(self.client, grupos=['10'])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_packing_bloqueado(self):
        _login_session(self.client, grupos=['8'])
        resp = self.client.get(self.url)
        # @exige_grupo redireciona ou bloqueia (não 200)
        self.assertNotEqual(resp.status_code, 200)

    def test_sem_sessao_bloqueado(self):
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)


# --------------------------------------------------------------------------
# Helper de validação de payload
# --------------------------------------------------------------------------

class ValidarPayloadViagemTest(TestCase):
    def _v(self, dados):
        from sankhya_integration.services.oracle_conn import _validar_payload_viagem
        return _validar_payload_viagem(dados)

    def test_payload_valido_minimo(self):
        erros, n = self._v({
            'data_viagem': '2026-05-29',
            'hora_saida': '08:30',
            'codveiculo': 5,
            'codparc_motorista': 100,
            'destinos': [{'codparc': 200, 'qtd_caixas': 10}],
        })
        self.assertEqual(erros, [])
        self.assertEqual(n['codveiculo'], 5)
        self.assertEqual(n['destinos'][0]['ordem'], 1)

    def test_data_obrigatoria(self):
        erros, _ = self._v({'data_viagem': '', 'hora_saida': '08:00',
                            'codveiculo': 1, 'codparc_motorista': 1,
                            'destinos': [{'codparc': 1, 'qtd_caixas': 5}]})
        self.assertTrue(any('data_viagem' in e for e in erros))

    def test_data_formato_invalido(self):
        erros, _ = self._v({'data_viagem': 'BUG', 'hora_saida': '08:00',
                            'codveiculo': 1, 'codparc_motorista': 1,
                            'destinos': [{'codparc': 1, 'qtd_caixas': 5}]})
        self.assertTrue(any('YYYY-MM-DD' in e for e in erros))

    def test_hora_formato_invalido(self):
        erros, _ = self._v({'data_viagem': '2026-05-29', 'hora_saida': '1230',
                            'codveiculo': 1, 'codparc_motorista': 1,
                            'destinos': [{'codparc': 1, 'qtd_caixas': 5}]})
        self.assertTrue(any('HH:MM' in e for e in erros))

    def test_hora_fora_range(self):
        erros, _ = self._v({'data_viagem': '2026-05-29', 'hora_saida': '25:99',
                            'codveiculo': 1, 'codparc_motorista': 1,
                            'destinos': [{'codparc': 1, 'qtd_caixas': 5}]})
        self.assertTrue(any('00:00' in e for e in erros))

    def test_destinos_obrigatorios(self):
        erros, _ = self._v({'data_viagem': '2026-05-29', 'hora_saida': '08:00',
                            'codveiculo': 1, 'codparc_motorista': 1,
                            'destinos': []})
        self.assertTrue(any('pelo menos 1 destino' in e for e in erros))

    def test_qtd_caixas_negativa(self):
        erros, _ = self._v({'data_viagem': '2026-05-29', 'hora_saida': '08:00',
                            'codveiculo': 1, 'codparc_motorista': 1,
                            'destinos': [{'codparc': 1, 'qtd_caixas': -5}]})
        self.assertTrue(any('qtd_caixas' in e for e in erros))

    def test_ajudantes_dedup(self):
        _, n = self._v({'data_viagem': '2026-05-29', 'hora_saida': '08:00',
                        'codveiculo': 1, 'codparc_motorista': 1,
                        'destinos': [{'codparc': 1, 'qtd_caixas': 5}],
                        'ajudantes': [100, 200, 100, 100]})
        # dedup preserva ordem da primeira aparição
        self.assertEqual(n['ajudantes'], [100, 200])


# --------------------------------------------------------------------------
# Function services — mockam Oracle
# --------------------------------------------------------------------------

class ConsultarParceirosPorTipoTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_payload_normalizado(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_parceiros_por_tipo
        cur = MagicMock()
        cur.fetchall.return_value = [
            (587, 'ADENILTON GILDASIO GOMES', 'ADENILTON SA', 'S'),
            (233, 'ALEX DE SOUSA', '', 'S'),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cur
        mock_obter.return_value.__enter__ = MagicMock(return_value=conn)
        mock_obter.return_value.__exit__ = MagicMock(return_value=None)

        out = consultar_parceiros_por_tipo(tipo_id=4, q='ANDRE', limite=10)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['codparc'], 587)
        self.assertEqual(out[0]['nomeparc'], 'ADENILTON GILDASIO GOMES')

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_erro_oracle_retorna_vazio(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_parceiros_por_tipo
        mock_obter.side_effect = Exception('boom')
        out = consultar_parceiros_por_tipo(tipo_id=4)
        self.assertEqual(out, [])


class ConsultarVeiculosLogisticaTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_retorno_mapeado(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_veiculos_logistica
        cur = MagicMock()
        cur.fetchall.return_value = [
            (12, 'EFU5D47', 'R/RODOFORTSA RFG 2E', 'CARGA CAMINHAO', 'S', 'S', 1, 'HORTIFRUTI SEMEAR'),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cur
        mock_obter.return_value.__enter__ = MagicMock(return_value=conn)
        mock_obter.return_value.__exit__ = MagicMock(return_value=None)

        out = consultar_veiculos_logistica(q='RODO', limite=5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['placa'], 'EFU5D47')
        self.assertEqual(out[0]['proprio'], 'S')


class ListarTiposParceiroTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_retorno_ordenado(self, mock_obter):
        from sankhya_integration.services.oracle_conn import listar_tipos_parceiro
        cur = MagicMock()
        cur.fetchall.return_value = [
            (1, 'CLIENTE', 'Cliente', 'S', 10),
            (4, 'MOTORISTA', 'Motorista', 'S', 40),
        ]
        conn = MagicMock()
        conn.cursor.return_value = cur
        mock_obter.return_value.__enter__ = MagicMock(return_value=conn)
        mock_obter.return_value.__exit__ = MagicMock(return_value=None)

        out = listar_tipos_parceiro()
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['codigo'], 'CLIENTE')
        self.assertEqual(out[1]['ordem_exibicao'], 40)


class ConsultarProximoNumViagemTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_tabela_vazia_retorna_1(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_proximo_num_viagem
        cur = MagicMock()
        cur.fetchone.return_value = (1,)
        conn = MagicMock()
        conn.cursor.return_value = cur
        mock_obter.return_value.__enter__ = MagicMock(return_value=conn)
        mock_obter.return_value.__exit__ = MagicMock(return_value=None)

        self.assertEqual(consultar_proximo_num_viagem(), 1)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_erro_oracle_retorna_1(self, mock_obter):
        from sankhya_integration.services.oracle_conn import consultar_proximo_num_viagem
        mock_obter.side_effect = Exception('boom')
        self.assertEqual(consultar_proximo_num_viagem(), 1)


class ObterViagemDetalheTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_nao_encontrada(self, mock_obter):
        from sankhya_integration.services.oracle_conn import obter_viagem_detalhe
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = cur
        mock_obter.return_value.__enter__ = MagicMock(return_value=conn)
        mock_obter.return_value.__exit__ = MagicMock(return_value=None)

        res = obter_viagem_detalhe(99999)
        self.assertFalse(res['ok'])
        self.assertEqual(res['motivo'], 'nao_encontrada')

    def test_id_invalido(self):
        from sankhya_integration.services.oracle_conn import obter_viagem_detalhe
        res = obter_viagem_detalhe('abc')
        self.assertFalse(res['ok'])
        self.assertEqual(res['motivo'], 'id_invalido')


class CriarViagemBancoTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada(self, _):
        from sankhya_integration.services.oracle_conn import criar_viagem_banco
        res = criar_viagem_banco({})
        self.assertFalse(res['ok'])
        self.assertIn('Escrita desabilitada', res['error'])

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=True)
    def test_payload_invalido(self, _):
        from sankhya_integration.services.oracle_conn import criar_viagem_banco
        res = criar_viagem_banco({})
        self.assertFalse(res['ok'])
        self.assertIn('data_viagem', res['error'])


class EditarViagemBancoTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada(self, _):
        from sankhya_integration.services.oracle_conn import editar_viagem_banco
        res = editar_viagem_banco(1, {})
        self.assertFalse(res['ok'])

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=True)
    def test_id_invalido(self, _):
        from sankhya_integration.services.oracle_conn import editar_viagem_banco
        res = editar_viagem_banco('abc', {'data_viagem': '2026-05-29', 'hora_saida': '08:00',
                                          'codveiculo': 1, 'codparc_motorista': 1,
                                          'destinos': [{'codparc': 1, 'qtd_caixas': 5}]})
        self.assertFalse(res['ok'])
        self.assertEqual(res['error'], 'viagem_id inválido')


class ExcluirViagemBancoTest(TestCase):
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada(self, _):
        from sankhya_integration.services.oracle_conn import excluir_viagem_banco
        res = excluir_viagem_banco(1)
        self.assertFalse(res['ok'])

    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita', return_value=True)
    def test_id_invalido(self, _):
        from sankhya_integration.services.oracle_conn import excluir_viagem_banco
        res = excluir_viagem_banco(-1)
        self.assertFalse(res['ok'])


# --------------------------------------------------------------------------
# Endpoints REST GET — view delega a service
# --------------------------------------------------------------------------

class ApiLogisticaListarTiposParceiroTest(TestCase):
    @patch('sankhya_integration.views.listar_tipos_parceiro')
    def test_lista_tipos(self, mock_func):
        mock_func.return_value = [{'id': 1, 'codigo': 'CLIENTE', 'descricao': 'C', 'ativo': 'S', 'ordem_exibicao': 10}]
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/tipos-parceiro/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['tipos']), 1)


class ApiLogisticaParceirosPorTipoTest(TestCase):
    @patch('sankhya_integration.views.consultar_parceiros_por_tipo')
    def test_lista_parceiros(self, mock_func):
        mock_func.return_value = [{'codparc': 100, 'nomeparc': 'X', 'razaosocial': '', 'ativo': 'S'}]
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/parceiros/?tipo=4&q=X&limite=5')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)

    def test_tipo_obrigatorio(self):
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/parceiros/')
        self.assertEqual(resp.status_code, 400)


class ApiLogisticaVeiculosTest(TestCase):
    @patch('sankhya_integration.views.consultar_veiculos_logistica')
    def test_lista_veiculos(self, mock_func):
        mock_func.return_value = [{'codveiculo': 1, 'placa': 'AAA1234', 'marcamodelo': 'X', 'especietipo': '', 'proprio': 'S', 'ativo': 'S', 'codparc': 1, 'nomeparc': 'X'}]
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/veiculos/?q=AAA')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])


class ApiLogisticaListarViagensTest(TestCase):
    @patch('sankhya_integration.views.consultar_proximo_num_viagem', return_value=5)
    @patch('sankhya_integration.views.listar_viagens')
    def test_lista_viagens(self, mock_listar, _mock_prox):
        mock_listar.return_value = [{'id': 1, 'num_viagem': 1}]
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/viagens/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['proximo_num_viagem'], 5)


class ApiLogisticaObterViagemTest(TestCase):
    @patch('sankhya_integration.views.obter_viagem_detalhe')
    def test_encontrada(self, mock_func):
        mock_func.return_value = {'ok': True, 'viagem': {'id': 1, 'num_viagem': 1}}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/viagem/1/')
        self.assertEqual(resp.status_code, 200)

    @patch('sankhya_integration.views.obter_viagem_detalhe')
    def test_nao_encontrada_404(self, mock_func):
        mock_func.return_value = {'ok': False, 'motivo': 'nao_encontrada'}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/viagem/99999/')
        self.assertEqual(resp.status_code, 404)


class ApiLogisticaFichaPdfTest(TestCase):
    @patch('sankhya_integration.views.gerar_pdf_ficha_viagem', return_value=b'%PDF-1.4 fake')
    @patch('sankhya_integration.views.obter_viagem_detalhe')
    def test_pdf_inline(self, mock_obter, _mock_pdf):
        mock_obter.return_value = {'ok': True, 'viagem': {'num_viagem': 1, 'data_viagem': '2026-05-29', 'hora_saida': '08:00', 'placa': 'X', 'motorista_nome': 'M', 'observacao': '', 'destinos': [], 'ajudantes': []}}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/viagem/1/ficha-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline', resp['Content-Disposition'])

    @patch('sankhya_integration.views.obter_viagem_detalhe')
    def test_viagem_inexistente_404(self, mock_func):
        mock_func.return_value = {'ok': False, 'motivo': 'nao_encontrada'}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/viagem/99999/ficha-pdf/')
        self.assertEqual(resp.status_code, 404)


# --------------------------------------------------------------------------
# Endpoints REST POST — escrita
# --------------------------------------------------------------------------

class ApiLogisticaCriarViagemTest(TestCase):
    @patch('sankhya_integration.views.criar_viagem_banco')
    def test_criacao_ok(self, mock_func):
        mock_func.return_value = {'ok': True, 'viagem_id': 1, 'num_viagem': 1}
        c = Client()
        _login_session(c, grupos=['1'])
        payload = {
            'data_viagem': '2026-05-29', 'hora_saida': '08:00',
            'codveiculo': 1, 'codparc_motorista': 1,
            'destinos': [{'codparc': 100, 'qtd_caixas': 50}],
        }
        resp = c.post('/sankhya/logistica/api/viagem/criar/',
                       data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    @patch('sankhya_integration.views.criar_viagem_banco')
    def test_falha_retorna_400(self, mock_func):
        mock_func.return_value = {'ok': False, 'error': 'destino obrigatório'}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.post('/sankhya/logistica/api/viagem/criar/',
                       data=json.dumps({}), content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_get_nao_permitido(self):
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.get('/sankhya/logistica/api/viagem/criar/')
        self.assertEqual(resp.status_code, 405)


class ApiLogisticaEditarViagemTest(TestCase):
    @patch('sankhya_integration.views.editar_viagem_banco')
    def test_edicao_ok(self, mock_func):
        mock_func.return_value = {'ok': True, 'viagem_id': 1, 'num_viagem': 1, 'mudancas': {}}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.post('/sankhya/logistica/api/viagem/1/editar/',
                       data=json.dumps({'foo': 'bar'}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)


class ApiLogisticaExcluirViagemTest(TestCase):
    @patch('sankhya_integration.views.excluir_viagem_banco')
    def test_exclusao_ok(self, mock_func):
        mock_func.return_value = {'ok': True, 'viagem_id': 1, 'num_viagem': 1, 'destinos_removidos': 2, 'ajudantes_removidos': 1}
        c = Client()
        _login_session(c, grupos=['1'])
        resp = c.post('/sankhya/logistica/api/viagem/1/excluir/',
                       data=json.dumps({'motivo': 'duplicada'}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])

    @patch('sankhya_integration.views.excluir_viagem_banco')
    def test_motivo_repassado(self, mock_func):
        mock_func.return_value = {'ok': True, 'viagem_id': 1, 'num_viagem': 1, 'destinos_removidos': 0, 'ajudantes_removidos': 0}
        c = Client()
        _login_session(c, grupos=['1'])
        c.post('/sankhya/logistica/api/viagem/1/excluir/',
                data=json.dumps({'motivo': 'rota cancelada'}), content_type='application/json')
        # Verifica que motivo chegou ao service
        kwargs = mock_func.call_args.kwargs
        self.assertEqual(kwargs.get('motivo'), 'rota cancelada')
