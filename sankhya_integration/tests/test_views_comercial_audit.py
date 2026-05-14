"""
Testes da instrumentação de auditoria do módulo Comercial (B5 - Mai/2026).

Garante que cada operação de escrita do Comercial chama `registrar_auditoria`
com os parâmetros corretos.

Atenção: as views do Comercial fazem `import local` (dentro do corpo) dos
helpers `salvar_vale_compra_banco`, `gerar_financeiro_banco`, etc. Por isso
patchamos o **módulo de origem** (`sankhya_integration.services.oracle_conn`),
não a view.
"""
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 13
    session['nomeusu'] = 'COMERCIAL_TESTE'
    session['nome']    = 'Comercial Teste'
    session['grupos']  = grupos or ['1']
    session.save()


# ==========================================================================
# SALVAR_VALE
# ==========================================================================

class SalvarValeAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.salvar_vale_compra_banco')
    def test_emite_audit_em_sucesso(self, m_service, m_audit):
        m_service.return_value = {'ok': True, 'nunota_13': 9999}

        resp = self.client.post(
            reverse('api_salvar_vale_comercial'),
            data='{"nunota_origem": 5000, "lote": "L001", "codparc": 200, "qtd_extra": 100, "preco_extra": 5.5}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['modulo'], 'comercial')
        self.assertEqual(kwargs['operacao'], 'SALVAR_VALE')
        self.assertEqual(kwargs['registro_id'], 9999)
        snap_d = kwargs['snapshot_depois']
        self.assertEqual(snap_d['NUNOTA_13'], 9999)
        self.assertEqual(snap_d['NUNOTA_ORIGEM'], 5000)
        self.assertEqual(snap_d['LOTE'], 'L001')

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.salvar_vale_compra_banco')
    def test_falha_nao_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': False, 'error': 'Saldo insuficiente'}

        resp = self.client.post(
            reverse('api_salvar_vale_comercial'),
            data='{"nunota_origem": 5000, "lote": "L001"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        m_audit.assert_not_called()


# ==========================================================================
# ZERAR_NEGOCIACAO
# ==========================================================================

class ZerarNegociacaoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.zerar_negociacao_banco')
    def test_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_zerar_negociacao'),
            data='{"nunota_origem": 5000, "lote": "L001"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'ZERAR_NEGOCIACAO')
        self.assertEqual(kwargs['registro_id'], '5000/L001')
        self.assertEqual(kwargs['snapshot_antes']['LOTE'], 'L001')


# ==========================================================================
# GERAR_FINANCEIRO
# ==========================================================================

class GerarFinanceiroAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco')
    def test_emite_audit(self, m_service, m_audit):
        m_service.return_value = {
            'ok': True, 'nufin': 12345, 'qtde_fin': 2, 'vlr_total': 5000.0,
        }

        resp = self.client.post(
            reverse('api_gerar_financeiro_banco'),
            data='{"nunota_13": 9999, "descontar_inss": false, "historico": "Compra produtor X"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'GERAR_FINANCEIRO')
        self.assertEqual(kwargs['registro_id'], 9999)
        self.assertEqual(kwargs['snapshot_depois']['NUFIN'], 12345)
        self.assertEqual(kwargs['snapshot_depois']['VLR_TOTAL_FIN'], 5000.0)


# ==========================================================================
# DESFATURAR_VALE
# ==========================================================================

class DesfaturarValeAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.desfaturar_comercial_banco')
    def test_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True, 'removidos': 3}

        resp = self.client.post(
            reverse('api_desfaturar_vale'),
            data='{"nunota_13": 9999}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'DESFATURAR_VALE')
        self.assertEqual(kwargs['snapshot_antes']['STATUSNOTA'], 'L')
        self.assertIsNone(kwargs['snapshot_depois']['STATUSNOTA'])


# ==========================================================================
# ATUALIZAR_PRECO_VALE / ATUALIZAR_INSS_VALE
# ==========================================================================

class AtualizarPrecoIssAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.upsert_preco_in_natura_modalFaturamento')
    def test_atualizar_preco_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_atualizar_preco_modalFaturamento'),
            data='{"nunota_origem": 5000, "nunota_13": 9999, "codprod": 863, "preco": 6.5}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'ATUALIZAR_PRECO_VALE')
        self.assertEqual(kwargs['registro_id'], '9999/863')
        self.assertEqual(kwargs['snapshot_depois']['NOVO_PRECO'], 6.5)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.atualizar_desconto_inss_vale')
    def test_atualizar_inss_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_atualizar_desconto_inss_vale'),
            data='{"nunota_13": 9999, "valor": 50.25}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'ATUALIZAR_INSS_VALE')
        self.assertEqual(kwargs['snapshot_depois']['VLROUTROS'], 50.25)
        self.assertIn('50.25', kwargs['observacao'])
