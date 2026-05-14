"""
Testes da instrumentação de auditoria do módulo Combustível (B3 - Mai/2026).

Garante que cada uma das 7 operações de escrita de Combustível chama
`registrar_auditoria` com os parâmetros corretos.
"""
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 99
    session['nomeusu'] = 'FROTA_TESTE'
    session['nome']    = 'Frota Teste'
    session['grupos']  = grupos or ['11']
    session.save()


# ==========================================================================
# CRIAR_REQUISICAO
# ==========================================================================

class CriarRequisicaoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.criar_requisicao_combustivel_banco')
    def test_emite_audit_correto(self, m_service, m_audit):
        m_service.return_value = {'ok': True, 'nunota': 1234}

        resp = self.client.post(
            reverse('api_combustivel_criar_requisicao'),
            data='{"codveiculo": 5, "codprod": 392, "qtd": 50.0, "tipo": "INTERNA_FROTA", "codcencus": 10100, "hodometro_km": 12345}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 201)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['modulo'], 'combustivel')
        self.assertEqual(kwargs['operacao'], 'CRIAR_REQUISICAO')
        self.assertEqual(kwargs['registro_id'], 1234)
        self.assertEqual(kwargs['codusu'], 99)
        snap_d = kwargs['snapshot_depois']
        self.assertEqual(snap_d['TIPO'], 'INTERNA_FROTA')
        self.assertEqual(snap_d['CODVEICULO'], 5)
        self.assertEqual(snap_d['QTD'], 50.0)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.criar_requisicao_combustivel_banco')
    def test_falha_service_nao_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': False, 'error': 'Saldo insuficiente'}
        resp = self.client.post(
            reverse('api_combustivel_criar_requisicao'),
            data='{"codveiculo": 5, "codprod": 392, "qtd": 50, "tipo": "INTERNA_FROTA", "codcencus": 10100, "hodometro_km": 100}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        m_audit.assert_not_called()


# ==========================================================================
# EDITAR_REQUISICAO
# ==========================================================================

class EditarRequisicaoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.editar_requisicao_combustivel_banco')
    @patch('sankhya_integration.views.obter_requisicao_combustivel')
    def test_emite_audit_com_antes_depois(self, m_obter, m_editar, m_audit):
        m_obter.return_value = {'NUNOTA': 1234, 'TIPO': 'INTERNA_FROTA', 'QTD': 50}
        m_editar.return_value = {'ok': True, 'nunota': 1234}

        resp = self.client.post(
            reverse('api_combustivel_editar_requisicao', args=[1234]),
            data='{"qtd": 80}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EDITAR_REQUISICAO')
        self.assertEqual(kwargs['registro_id'], 1234)
        self.assertEqual(kwargs['snapshot_antes']['QTD'], 50)
        self.assertEqual(kwargs['snapshot_depois']['qtd'], 80)


# ==========================================================================
# EXCLUIR_REQUISICAO
# ==========================================================================

class ExcluirRequisicaoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.excluir_requisicao_combustivel_banco')
    @patch('sankhya_integration.views.obter_requisicao_combustivel')
    def test_emite_audit_com_snapshot_antes_e_motivo(self, m_obter, m_excluir, m_audit):
        m_obter.return_value = {'NUNOTA': 1234, 'QTD': 50}
        m_excluir.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_combustivel_excluir_requisicao', args=[1234]),
            data='{"motivo": "Lançamento de teste"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EXCLUIR_REQUISICAO')
        self.assertEqual(kwargs['snapshot_antes']['QTD'], 50)
        self.assertEqual(kwargs['observacao'], 'Lançamento de teste')


# ==========================================================================
# CRIAR_ABASTECIMENTO_EXTERNO
# ==========================================================================

class AbastecimentoExternoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.criar_abastecimento_externo_banco')
    def test_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True, 'nunota': 7777, 'nufin': 99001}

        resp = self.client.post(
            reverse('api_combustivel_criar_externo'),
            data='{"codveiculo": 5, "codparc": 572, "codprod": 392, "qtd": 100, "vlrunit": 6.5, "codcencus": 10100, "hodometro_km": 50000}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 201)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'CRIAR_ABASTECIMENTO_EXTERNO')
        self.assertEqual(kwargs['snapshot_depois']['TIPO'], 'EXTERNA_POSTO')
        self.assertEqual(kwargs['snapshot_depois']['CODPARC'], 572)
        self.assertEqual(kwargs['snapshot_depois']['NUFIN_GERADO'], 99001)


# ==========================================================================
# CRIAR_ENTRADA / EDITAR_ENTRADA / EXCLUIR_ENTRADA
# ==========================================================================

class CriarEntradaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.criar_entrada_combustivel_banco')
    def test_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True, 'nunota': 88888, 'nufin': 99002}

        resp = self.client.post(
            reverse('api_combustivel_criar_entrada'),
            data='{"codemp": 10, "codparc": 100, "numnota": 5555, "dtneg": "2026-05-13", "codcencus": 10100, "itens": [{"codprod": 392, "qtd": 5000, "vlrunit": 6}]}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 201)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'CRIAR_ENTRADA')
        self.assertEqual(kwargs['snapshot_depois']['CODTIPOPER'], 10)
        self.assertEqual(kwargs['snapshot_depois']['NUMNOTA'], 5555)


class EditarEntradaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.editar_entrada_combustivel_banco')
    @patch('sankhya_integration.views.obter_entrada_combustivel')
    def test_emite_audit_com_antes_depois(self, m_obter, m_editar, m_audit):
        m_obter.return_value = {'NUNOTA': 88888, 'NUMNOTA': 5555, 'ITENS': []}
        m_editar.return_value = {'ok': True, 'nunota': 88888}

        resp = self.client.post(
            reverse('api_combustivel_editar_entrada', args=[88888]),
            data='{"observacao": "corrigindo qtd"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EDITAR_ENTRADA')
        self.assertEqual(kwargs['snapshot_antes']['NUMNOTA'], 5555)


class ExcluirEntradaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.excluir_entrada_combustivel_banco')
    @patch('sankhya_integration.views.obter_entrada_combustivel')
    def test_emite_audit_com_motivo(self, m_obter, m_excluir, m_audit):
        m_obter.return_value = {'NUNOTA': 88888, 'NUMNOTA': 5555}
        m_excluir.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_combustivel_excluir_entrada', args=[88888]),
            data='{"motivo": "duplicidade"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EXCLUIR_ENTRADA')
        self.assertEqual(kwargs['observacao'], 'duplicidade')
        self.assertEqual(kwargs['snapshot_antes']['NUMNOTA'], 5555)
