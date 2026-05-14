"""
Testes da instrumentação de auditoria de Entrada/Classificação (B6 - Mai/2026).

Cobertura:
  - api_salvar_item_nota (criar vs editar)
  - api_excluir_itens_nota
  - api_finalizar_nota_compra
  - api_excluir_nota_compra
  - api_finaliza_classificacao_toggle
  - api_salvar_simulacao
  - api_desmembrar_pedido_classificacao
  - api_unificar_pedido_classificacao
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None):
    session = client.session
    session['codusu']  = 21
    session['nomeusu'] = 'ENTRADA_TESTE'
    session['nome']    = 'Entrada Teste'
    session['grupos']  = grupos or ['8']
    session.save()


def _conn_factory(cursor):
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__  = MagicMock(return_value=False)
    conn.cursor.return_value = cursor
    return conn


# ==========================================================================
# CRIAR_ITEM_NOTA / EDITAR_ITEM_NOTA
# ==========================================================================

class SalvarItemNotaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.recalcular_totais_nota_banco', return_value={})
    @patch('sankhya_integration.views.inserir_item_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_insercao_emite_criar_item_nota(self, m_conn, m_insert, m_recalc, m_audit):
        m_conn.return_value = _conn_factory(MagicMock())
        m_insert.return_value = {'executed': True, 'ok': True, 'sequencia': 7}

        resp = self.client.post(
            reverse('item_save'),
            data='{"NUNOTA": 555, "CODPROD": 999, "QTDNEG": 10, "CODVOL": "KG"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['modulo'], 'entrada')
        self.assertEqual(kwargs['operacao'], 'CRIAR_ITEM_NOTA')
        self.assertEqual(kwargs['registro_id'], '555/7')


# ==========================================================================
# EXCLUIR_ITENS_NOTA
# ==========================================================================

class ExcluirItensNotaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_excluir_emite_audit(self, m_conn, m_audit):
        cur = MagicMock()
        # 1ª: top_atual = 11 (Entrada)
        # 2ª: SELECT CODAGREGACAO do item — sem lote (None)
        # 3ª: snapshot SELECT — devolve 1 item
        # 4ª: DELETE
        # 5ª: SELECT COUNT(*) sobras = 1 (não deleta cabeçalho)
        cur.fetchone.side_effect = [
            (11,),         # CODTIPOPER
            (None,),       # CODAGREGACAO (sem lote)
            (1,),          # COUNT itens sobrando
        ]
        cur.fetchall.return_value = [
            (1, 999, 10, 5, 'KG', None),  # snapshot do item
        ]
        m_conn.return_value = _conn_factory(cur)

        resp = self.client.post(
            reverse('item_delete'),
            data='{"nunota": 555, "sequencias": [1]}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EXCLUIR_ITENS_NOTA')
        self.assertEqual(kwargs['modulo'], 'entrada')
        self.assertIn('1 item', kwargs['observacao'])


# ==========================================================================
# FINALIZAR_NOTA
# ==========================================================================

class FinalizarNotaAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_finalizar_emite_audit_entrada(self, m_conn, m_perm, m_audit):
        cur = MagicMock()
        # SELECT snapshot ANTES (CODTIPOPER=11), UPDATE
        cur.fetchone.return_value = (11, None, None)
        cur.rowcount = 1
        m_conn.return_value = _conn_factory(cur)

        resp = self.client.post(
            reverse('item_finalize'),
            data='{"nunota": 555}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'FINALIZAR_NOTA')
        self.assertEqual(kwargs['modulo'], 'entrada')
        self.assertEqual(kwargs['snapshot_depois']['STATUSNOTA'], 'L')


# ==========================================================================
# EXCLUIR_NOTA_COMPRA
# ==========================================================================

class ExcluirNotaCompraAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.excluir_nota_completa_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_excluir_emite_audit(self, m_conn, m_excluir, m_audit):
        cur = MagicMock()
        # 1ª chamada (trava classificação) → conta = 0
        # 2ª (snapshot — CODTIPOPER etc) → tupla cabeçalho
        cur.fetchone.side_effect = [
            (0,),
            (11, 10, 100, MagicMock(strftime=lambda f: '2026-05-13'), 5555),
        ]
        cur.fetchall.return_value = []
        m_conn.return_value = _conn_factory(cur)
        m_excluir.return_value = {'ok': True}

        resp = self.client.post(
            reverse('nota_delete'),
            data='{"nunota": 555}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'EXCLUIR_NOTA_COMPRA')
        self.assertEqual(kwargs['snapshot_antes']['CODTIPOPER'], 11)


# ==========================================================================
# TOGGLE_PENDENTE (Classificação)
# ==========================================================================

class TogglePendenteAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    def test_toggle_emite_audit(self, m_conn, m_audit):
        cur = MagicMock()
        # SELECT PENDENTE antes (devolve 'S')
        cur.fetchone.return_value = ('S',)
        # SELECT DISTINCT CODAGREGACAO (lotes afetados)
        cur.fetchall.return_value = [('L001',), ('L002',)]
        m_conn.return_value = _conn_factory(cur)

        resp = self.client.post(
            reverse('api_finaliza_classificacao_toggle'),
            data='{"nunota_class": 8888, "pendente": "N"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'TOGGLE_PENDENTE')
        self.assertEqual(kwargs['modulo'], 'classificacao')
        self.assertEqual(kwargs['snapshot_antes']['PENDENTE'], 'S')
        self.assertEqual(kwargs['snapshot_depois']['PENDENTE'], 'N')
        self.assertEqual(len(kwargs['snapshot_depois']['LOTES_AFETADOS']), 2)


# ==========================================================================
# DESMEMBRAR / UNIFICAR / SIMULACAO
# ==========================================================================

class DesmembrarUnificarAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.views.desmembrar_pedido_classificacao')
    def test_desmembrar_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True, 'nunota_novo': 9999}

        resp = self.client.post(
            reverse('api_desmembrar_pedido_classificacao'),
            data='{"nunota_origem": 5000, "lote": "L001"}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'DESMEMBRAR_PEDIDO')
        self.assertEqual(kwargs['modulo'], 'classificacao')

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.unificar_pedido_classificacao')
    def test_unificar_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_unificar_pedido_classificacao'),
            data='{"nunota_origem": 5000, "lote": "L001", "nunota_destino": 7000}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'UNIFICAR_PEDIDO')
        self.assertEqual(kwargs['modulo'], 'classificacao')
        self.assertEqual(kwargs['snapshot_antes']['NUNOTA_DESTINO'], 7000)


class SalvarSimulacaoAuditTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client)

    @patch('sankhya_integration.views.registrar_auditoria')
    @patch('sankhya_integration.services.oracle_conn.atualizar_simulacao_item_banco')
    def test_emite_audit(self, m_service, m_audit):
        m_service.return_value = {'ok': True}

        resp = self.client.post(
            reverse('api_salvar_simulacao'),
            data='{"nunota": 5000, "lote": "L001", "sim_data": {"preco_cx": 50.0}}',
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 200)
        m_audit.assert_called_once()
        kwargs = m_audit.call_args.kwargs
        self.assertEqual(kwargs['operacao'], 'SALVAR_SIMULACAO')
        self.assertEqual(kwargs['registro_id'], '5000/L001')
        self.assertEqual(kwargs['snapshot_depois']['SIM_DATA']['preco_cx'], 50.0)
