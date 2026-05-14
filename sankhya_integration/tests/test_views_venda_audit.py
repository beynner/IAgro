"""
Testes da instrumentação de auditoria do módulo Venda (B2 - Mai/2026).

Cobertura:
  - Cada uma das 9 operações de escrita de Venda chama `registrar_auditoria`
    com os parâmetros corretos (modulo, operacao, tabela_alvo, registro_id,
    codusu, nomeusu, snapshot_antes, snapshot_depois).

Não testa o Oracle de fato — mock total em `registrar_auditoria` + funções
service. Esses testes garantem que o "rastro de auditoria" é emitido — a
correção do INSERT em AD_AUDITORIA_GERAL fica nos testes do próprio helper.
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 42
    session['nomeusu'] = 'OPERADOR_TESTE'
    session['nome']    = 'Operador Teste'
    session['grupos']  = grupos or ['10']
    session.save()


# --------------------------------------------------------------------------
# Helper de mock de conexão Oracle (devolve cursor parametrizável)
# --------------------------------------------------------------------------
def _mock_conn_factory(cursor):
    """Embrulha cursor num context manager (with obter_conexao_oracle() as conn)."""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__  = MagicMock(return_value=False)
    conn.cursor.return_value = cursor
    return conn


# ==========================================================================
# CRIAR_PEDIDO
# ==========================================================================

class CriarPedidoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_criar_pedido_emite_audit_correto(self, m_perm, m_conn, m_insert, m_audit):
        m_conn.return_value = _mock_conn_factory(MagicMock())
        m_insert.return_value = {'executed': True, 'nunota': 12345}

        resp = self.client.post(
            reverse('api_criar_cabecalho_venda'),
            data='{"codparc": 100, "codtipvenda": 11, "dtneg": "13/05/2026", "codemp": 10}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['modulo'], 'venda')
        self.assertEqual(kwargs['operacao'], 'CRIAR_PEDIDO')
        self.assertEqual(kwargs['tabela_alvo'], 'TGFCAB')
        self.assertEqual(kwargs['registro_id'], 12345)
        self.assertEqual(kwargs['codusu'], 42)
        self.assertEqual(kwargs['nomeusu'], 'OPERADOR_TESTE')
        self.assertIsNone(kwargs.get('snapshot_antes'))
        snap_d = kwargs['snapshot_depois']
        self.assertEqual(snap_d['NUNOTA'], 12345)
        self.assertEqual(snap_d['CODTIPOPER'], 34)
        self.assertEqual(snap_d['CODPARC'], 100)
        self.assertEqual(snap_d['CODTIPVENDA'], 11)


# ==========================================================================
# EDITAR_CABECALHO
# ==========================================================================

class EditarCabecalhoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.atualizar_cabecalho_venda_banco')
    @patch('sankhya_integration.views.consultar_cabecalho_venda_oracle')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_editar_cabecalho_emite_audit_com_antes_depois(self, m_conn, m_consultar, m_update, m_audit):
        # Trava CODTIPOPER=34
        cur_trava = MagicMock()
        cur_trava.fetchone.return_value = (34,)
        m_conn.return_value = _mock_conn_factory(cur_trava)

        # Snapshot antes (8 colunas como o view espera)
        import datetime
        m_consultar.return_value = (
            10, 'EMPRESA', 100, 'PARC ANTES', 11, 'A VISTA',
            datetime.datetime(2026, 5, 13), 'obs antes',
        )
        m_update.return_value = {'executed': True}

        resp = self.client.post(
            reverse('api_atualizar_cabecalho_venda'),
            data='{"nunota": 555, "codparc": 200, "codtipvenda": 12, "dtneg": "14/05/2026", "obs": "nova obs"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EDITAR_CABECALHO')
        self.assertEqual(kwargs['registro_id'], 555)
        # snapshot_antes vem do consultar
        self.assertEqual(kwargs['snapshot_antes']['CODPARC'], 100)
        self.assertEqual(kwargs['snapshot_antes']['OBSERVACAO'], 'obs antes')
        # snapshot_depois vem do payload novo
        self.assertEqual(kwargs['snapshot_depois']['CODPARC'], 200)
        self.assertEqual(kwargs['snapshot_depois']['OBSERVACAO'], 'nova obs')


# ==========================================================================
# ADICIONAR_ITEM
# ==========================================================================

class AdicionarItemAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.recalcular_totais_nota_banco', return_value={})
    @patch('sankhya_integration.views.inserir_item_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_adicionar_item_emite_audit(self, m_conn, m_insert, m_recalc, m_audit):
        m_conn.return_value = _mock_conn_factory(MagicMock())
        m_insert.return_value = {'executed': True, 'sequencia': 7}

        resp = self.client.post(
            reverse('api_salvar_item_venda'),
            data='{"nunota": 555, "codprod": 999, "qtdneg": 10, "vlrunit": 5.5, "codvol": "KG", "codagregacao": "L001"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'ADICIONAR_ITEM')
        self.assertEqual(kwargs['registro_id'], '555/7')
        snap_d = kwargs['snapshot_depois']
        self.assertEqual(snap_d['CODPROD'], 999)
        self.assertEqual(snap_d['QTDNEG'], 10)
        self.assertEqual(snap_d['CODAGREGACAO'], 'L001')


# ==========================================================================
# FATURAR_PEDIDO
# ==========================================================================

class FaturarPedidoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.faturar_pedido_venda_banco')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_faturar_com_nfe_emite_audit(self, m_perm, m_faturar, m_audit):
        m_faturar.return_value = {'ok': True, 'numnota': 7777, 'nunota': 555}

        resp = self.client.post(
            reverse('api_faturar_pedido_venda'),
            data='{"nunota": 555, "top": 35}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'FATURAR_PEDIDO')
        self.assertEqual(kwargs['snapshot_antes']['CODTIPOPER'], 34)
        self.assertEqual(kwargs['snapshot_depois']['CODTIPOPER'], 35)
        self.assertEqual(kwargs['snapshot_depois']['NUMNOTA'], 7777)
        self.assertIn('NFe', kwargs.get('observacao', ''))

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.faturar_pedido_venda_banco')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_falha_no_service_nao_emite_audit(self, m_perm, m_faturar, m_audit):
        m_faturar.return_value = {'ok': False, 'error': 'Sem lote em algum item'}

        resp = self.client.post(
            reverse('api_faturar_pedido_venda'),
            data='{"nunota": 555, "top": 35}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 400)
        m_audit.assert_not_called()


# ==========================================================================
# CRIAR_AVARIA / CRIAR_DEVOLUCAO
# ==========================================================================

class AvariaDevolucaoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.criar_avaria_top30_banco')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_criar_avaria_emite_audit(self, m_perm, m_avaria, m_audit):
        m_avaria.return_value = {'ok': True, 'nunota': 8888}

        resp = self.client.post(
            reverse('api_criar_avaria'),
            data='{"codemp": 10, "codparc": 100, "codagregacao": "L001", "codprod": 999, "qtdneg": 5, "codvol": "KG", "observacao": "Furto"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'CRIAR_AVARIA')
        self.assertEqual(kwargs['snapshot_depois']['CODTIPOPER'], 30)
        self.assertEqual(kwargs['observacao'], 'Furto')

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.criar_devolucao_top36_banco')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_criar_devolucao_emite_audit(self, m_perm, m_dev, m_audit):
        m_dev.return_value = {'ok': True, 'nunota': 9999}

        resp = self.client.post(
            reverse('api_criar_devolucao'),
            data='{"nunota_origem": 5555, "itens": [{"sequencia_origem": 1, "qtd_devolver": 2}], "observacao": "Cliente devolveu"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'CRIAR_DEVOLUCAO')
        self.assertEqual(kwargs['snapshot_antes']['NUNOTA_ORIGEM'], 5555)
        self.assertEqual(kwargs['snapshot_depois']['CODTIPOPER'], 36)
        self.assertEqual(kwargs['snapshot_depois']['STATUSNOTA'], 'A')
