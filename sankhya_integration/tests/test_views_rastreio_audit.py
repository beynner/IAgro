"""
Testes da instrumentação de auditoria do módulo Rastreio (B4 - Mai/2026).

Garante que cada operação de escrita do Rastreio chama `registrar_auditoria`
com os parâmetros corretos. O audit SQLite (`RastreioAudit`) continua sendo
gravado em paralelo — esse comportamento legado é coberto em test_rastreio.py.
"""
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 7
    session['nomeusu'] = 'RASTREIO_TESTE'
    session['nome']    = 'Rastreio Teste'
    session['grupos']  = grupos or ['1']
    session.save()


# ==========================================================================
# ATRIBUIR_LOTE
# ==========================================================================

class AtribuirLoteAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.atribuir_lote_item_pedido')
    def test_atribuir_total_emite_audit_universal(self, m_atr, m_legado, m_audit):
        m_atr.return_value = {
            'ok': True, 'operacao': 'UPDATE',
            'qtd_atribuida': 100, 'nova_sequencia': None,
        }

        resp = self.client.post(
            reverse('api_rastreio_atribuir_lote'),
            data='{"nunota": 5555, "sequencia": 1, "codagregacao": "L001"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_legado.assert_called_once()   # SQLite legado mantido
        m_audit.assert_called_once()    # Oracle universal novo
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['modulo'], 'rastreio')
        self.assertEqual(kwargs['operacao'], 'ATRIBUIR_LOTE')
        self.assertEqual(kwargs['registro_id'], '5555/1')
        self.assertEqual(kwargs['snapshot_depois']['CODAGREGACAO'], 'L001')
        self.assertEqual(kwargs['snapshot_depois']['OPERACAO'], 'UPDATE')

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.atribuir_lote_item_pedido')
    def test_atribuir_split_indica_nova_sequencia_em_observacao(self, m_atr, m_legado, m_audit):
        m_atr.return_value = {
            'ok': True, 'operacao': 'SPLIT',
            'qtd_atribuida': 50, 'nova_sequencia': 7,
        }

        resp = self.client.post(
            reverse('api_rastreio_atribuir_lote'),
            data='{"nunota": 5555, "sequencia": 1, "codagregacao": "L001", "qtd": 50}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['snapshot_depois']['NOVA_SEQUENCIA'], 7)
        self.assertIn('SPLIT', kwargs['observacao'])


# ==========================================================================
# DESVINCULAR_LOTE
# ==========================================================================

class DesvincularLoteAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.desvincular_lote_item_pedido')
    def test_emite_audit_universal(self, m_desv, m_legado, m_audit):
        m_desv.return_value = {'ok': True, 'codagregacao_removido': 'L001', 'operacao': 'UPDATE'}

        resp = self.client.post(
            reverse('api_rastreio_desvincular_lote'),
            data='{"nunota": 5555, "sequencia": 1}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'DESVINCULAR_LOTE')
        self.assertEqual(kwargs['snapshot_antes']['CODAGREGACAO'], 'L001')
        self.assertIsNone(kwargs['snapshot_depois']['CODAGREGACAO'])


# ==========================================================================
# VINCULAR_PEDIDO_NOTA (Leva A)
# ==========================================================================

class VincularPedidoNotaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.inserir_vinculo_manual_pedido_nota')
    def test_emite_audit_origem_vinculado(self, m_insert, m_legado, m_audit):
        m_insert.return_value = {'ok': True, 'id': 42}

        resp = self.client.post(
            reverse('api_rastreio_vinculo_criar'),
            data='{"nunota_pedido": 111975, "nunota_nota": 111976}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'VINCULAR_PEDIDO_NOTA')
        self.assertEqual(kwargs['registro_id'], 42)
        self.assertEqual(kwargs['snapshot_depois']['ORIGEM'], 'VINCULADO')
        self.assertEqual(kwargs['snapshot_depois']['NUNOTA_PEDIDO'], 111975)
        self.assertEqual(kwargs['snapshot_depois']['NUNOTA_NOTA'], 111976)


# ==========================================================================
# CRIAR_PEDIDO_RETROATIVO (Leva B)
# ==========================================================================

class CriarPedidoRetroativoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.criar_pedido_retroativo_a_partir_de_nota')
    def test_emite_audit_origem_pedido_retroativo(self, m_create, m_legado, m_audit):
        m_create.return_value = {
            'ok': True, 'nunota_pedido': 555000, 'vinculo_id': 43, 'qtd_itens': 5,
        }

        resp = self.client.post(
            reverse('api_rastreio_vinculo_criar_pedido_retroativo'),
            data='{"nunota_nota": 111825}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'CRIAR_PEDIDO_RETROATIVO')
        self.assertEqual(kwargs['snapshot_depois']['ORIGEM'], 'PEDIDO_RETROATIVO')
        self.assertEqual(kwargs['snapshot_depois']['NUNOTA_PEDIDO_NOVO'], 555000)
        self.assertEqual(kwargs['snapshot_depois']['QTD_ITENS'], 5)


# ==========================================================================
# RESOLVER_NOTA_ORFA (fluxo unificado)
# ==========================================================================

class ResolverNotaOrfaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.resolver_nota_orfa_automatica')
    def test_emite_audit_com_acao_executada(self, m_resolver, m_legado, m_audit):
        m_resolver.return_value = {
            'ok': True, 'acao': 'VINCULAR',
            'nunota_pedido': 111975, 'vinculo_id': 44, 'qtd_itens': 3,
        }

        resp = self.client.post(
            reverse('api_rastreio_vinculo_resolver'),
            data='{"nunota_nota": 111976, "acao": "AUTO"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'RESOLVER_NOTA_ORFA_VINCULAR')
        self.assertEqual(kwargs['snapshot_antes']['ACAO_SOLICITADA'], 'AUTO')
        self.assertEqual(kwargs['snapshot_depois']['ACAO_EXECUTADA'], 'VINCULAR')


# ==========================================================================
# DESFAZER_VINCULO
# ==========================================================================

class DesfazerVinculoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views._registrar_audit_rastreio')
    @patch('sankhya_integration.views.remover_vinculo_manual_pedido_nota')
    def test_emite_audit_com_snapshot_antes(self, m_rem, m_legado, m_audit):
        m_rem.return_value = {'ok': True, 'removidos': 1}

        resp = self.client.post(
            reverse('api_rastreio_vinculo_remover'),
            data='{"nunota_pedido": 111975, "nunota_nota": 111976}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'DESFAZER_VINCULO')
        self.assertEqual(kwargs['snapshot_antes']['NUNOTA_PEDIDO'], 111975)
        self.assertIn('AD_NUMPEDIDOORIG', kwargs['observacao'])
