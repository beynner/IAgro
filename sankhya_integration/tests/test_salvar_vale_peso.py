"""
Testes do service `salvar_vale_compra_banco` — propagação de peso da TOP 11
para a TOP 13 (Mai/2026).

Regra de negócio:
    1. Antes de salvar o vale, validar que a linha in natura (GERAPRODUCAO='S')
       da TOP 11 origem do lote tem `QTDFIXADA > 0`. Esse valor é o "Peso CX
       Classificado" gravado pelo operador da Comercial via botão dedicado.
    2. Se QTDFIXADA estiver NULL/0 → bloqueia salvar com mensagem clara.
    3. Se preenchida → propaga pra `TGFITE.PESO` de TODOS os itens da TOP 13
       gravados naquele lote (Extra, Médio, etc — todos vêm da mesma
       classificação física e dividem o mesmo peso de caixa).

Cobertura mocka apenas `obter_conexao_oracle` e helpers de service (sem
dependência de Oracle real).
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase


def _conn_cursor_mock():
    """Constrói (conn_ctx, conn, cursor) compatível com `with obter_conexao_oracle() as conn`."""
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn_ctx = MagicMock()
    conn_ctx.__enter__.return_value = conn
    conn_ctx.__exit__.return_value = False
    return conn_ctx, conn, cursor


class SalvarValeBloqueioPesoTest(TestCase):
    """Validação bloqueadora B1/B4 — sem peso (nenhum dos 2 campos), não salva."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_quando_peso_e_qtdfixada_zero(self, mock_conn):
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        # SELECT (PESO, QTDFIXADA) → ambos 0
        cursor.fetchone.return_value = (0, 0)

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'NUNOTAS123D260515',
            'itens_faturar': [{'codprod': 10, 'qtdneg': 100, 'vlrunit': 5, 'vlrtot': 500}],
        })

        self.assertFalse(resultado['ok'])
        self.assertIn('peso classificado', resultado['error'].lower())
        # Nenhum INSERT/DELETE/UPDATE de espelhamento — só o SELECT da validação
        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(len(sqls), 1, f"Esperava apenas o SELECT de validação, veio: {sqls}")
        self.assertIn('QTDFIXADA', sqls[0])
        self.assertIn('PESO', sqls[0])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_bloqueia_quando_peso_e_qtdfixada_none(self, mock_conn):
        """SELECT NVL(MAX,0) já cobre NULL → 0, mas testamos fetch retornando None
        explícito também (defesa)."""
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (None, None)

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'L001',
            'itens_faturar': [{'codprod': 10, 'qtdneg': 50, 'vlrunit': 4, 'vlrtot': 200}],
        })

        self.assertFalse(resultado['ok'])
        self.assertIn('peso classificado', resultado['error'].lower())


class SalvarValePropagaPesoTest(TestCase):
    """B2 — Peso classificado propaga pra todos os itens da TOP 13 do lote."""

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_peso_propaga_para_todos_itens(self, mock_conn, mock_rec):
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (20.0, 20.0),  # SELECT (PESO, QTDFIXADA) da TOP 11 → 20 kg/caixa (ambos)
            (8888,),       # SELECT MAX(NUNOTA) FROM TGFCAB CODTIPOPER=13 → vale já existe
            (10,),         # SELECT CODEMP FROM TGFCAB do vale
            (5000,),       # SELECT AD_NUMPEDIDOORIG
            (1,),          # MAX(SEQUENCIA)+1 do 1º item
            (2,),          # MAX(SEQUENCIA)+1 do 2º item
        ]
        mock_rec.return_value = {'ok': True}

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'NUNOTAS123D260515',
            'itens_faturar': [
                {'codprod': 100, 'qtdneg': 60, 'vlrunit': 8, 'vlrtot': 480},   # Tomate Extra
                {'codprod': 101, 'qtdneg': 40, 'vlrunit': 5, 'vlrtot': 200},   # Tomate Médio
            ],
        })

        self.assertTrue(resultado['ok'], f"Esperava sucesso, veio: {resultado}")
        self.assertEqual(resultado['nunota_13'], 8888)

        # Coleta os INSERTs e seus binds
        inserts = [
            c for c in cursor.execute.call_args_list
            if 'INSERT INTO TGFITE' in c.args[0]
        ]
        self.assertEqual(len(inserts), 2, f"Esperava 2 INSERTs, veio: {len(inserts)}")

        # Confirma que PESO está na coluna do INSERT
        for ins in inserts:
            sql = ins.args[0]
            self.assertIn('PESO', sql)

        # Confirma que cada INSERT recebeu peso=20.0
        for ins in inserts:
            binds = ins.args[1] if len(ins.args) > 1 else ins.kwargs
            self.assertEqual(
                binds['peso'], 20.0,
                f"Cada item da TOP 13 deve receber peso classificado da TOP 11 (20.0); veio: {binds}",
            )

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_peso_propaga_em_item_unico(self, mock_conn, mock_rec):
        """Caso comum hortifrúti: 1 lote → 1 produto derivado (ex: só Tomate Extra)."""
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (15.5, 15.5),  # (PESO, QTDFIXADA) = 15,5 kg/caixa
            (7777,),       # NUNOTA do vale existente
            (10,),         # CODEMP
            (5000,),       # AD_NUMPEDIDOORIG
            (1,),          # MAX(SEQUENCIA)+1
        ]
        mock_rec.return_value = {'ok': True}

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'L001',
            'itens_faturar': [{'codprod': 100, 'qtdneg': 100, 'vlrunit': 10, 'vlrtot': 1000}],
        })

        self.assertTrue(resultado['ok'])
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        self.assertEqual(len(inserts), 1)
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertEqual(binds['peso'], 15.5)


# ==========================================================================
# B4 — Espelhamento bidirecional PESO ↔ QTDFIXADA na TOP 11
# ==========================================================================


class SalvarValeEspelhamentoTest(TestCase):
    """B4 — se um dos campos (PESO ou QTDFIXADA) está vazio na TOP 11, espelha
    o preenchido sobre o vazio antes de propagar pra TOP 13."""

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_espelha_qtdfixada_quando_so_peso_preenchido(self, mock_conn, mock_rec):
        """Caso comum in natura sem Fast-Track: TGFITE.PESO=20 mas QTDFIXADA NULL.
        Deve fazer UPDATE QTDFIXADA = 20 na TOP 11 + INSERT TOP 13 com peso=20."""
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (20.0, 0.0),   # PESO=20, QTDFIXADA=NULL/0
            (8888,),       # NUNOTA vale existente
            (10,),         # CODEMP
            (5000,),       # AD_NUMPEDIDOORIG
            (1,),          # MAX(SEQUENCIA)+1
        ]
        mock_rec.return_value = {'ok': True}

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'L001',
            'itens_faturar': [{'codprod': 100, 'qtdneg': 100, 'vlrunit': 10, 'vlrtot': 1000}],
        })

        self.assertTrue(resultado['ok'], f"Veio: {resultado}")

        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        # Deve ter UPDATE de espelhamento QTDFIXADA=20 na TOP 11
        espelhamentos = [c for c in cursor.execute.call_args_list
                         if 'UPDATE TGFITE SET QTDFIXADA' in c.args[0]
                         and 'NVL(QTDFIXADA, 0) = 0' in c.args[0]]
        self.assertEqual(len(espelhamentos), 1, f"Esperava 1 UPDATE de espelhamento; sqls: {sqls}")
        binds_esp = espelhamentos[0].kwargs
        self.assertEqual(binds_esp['p'], 20.0)

        # INSERT da TOP 13 deve usar peso=20
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        self.assertEqual(len(inserts), 1)
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertEqual(binds['peso'], 20.0)

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_espelha_peso_quando_so_qtdfixada_preenchido(self, mock_conn, mock_rec):
        """Cenário inverso: QTDFIXADA preenchida (Comercial digitou) mas PESO
        ficou 0/NULL na entrada. Espelha PESO = QTDFIXADA."""
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (0.0, 18.0),   # PESO=0, QTDFIXADA=18
            (9999,),       # NUNOTA vale
            (10,),         # CODEMP
            (5000,),       # AD_NUMPEDIDOORIG
            (1,),          # MAX(SEQ)+1
        ]
        mock_rec.return_value = {'ok': True}

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'L001',
            'itens_faturar': [{'codprod': 100, 'qtdneg': 50, 'vlrunit': 6, 'vlrtot': 300}],
        })

        self.assertTrue(resultado['ok'])

        # UPDATE espelhamento PESO = 18 na TOP 11
        espelhamentos = [c for c in cursor.execute.call_args_list
                         if 'UPDATE TGFITE SET PESO' in c.args[0]
                         and 'NVL(PESO, 0) = 0' in c.args[0]]
        self.assertEqual(len(espelhamentos), 1)
        self.assertEqual(espelhamentos[0].kwargs['p'], 18.0)

        # INSERT TOP 13 com peso=18
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertEqual(binds['peso'], 18.0)

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_usa_qtdfixada_quando_ambos_preenchidos_sem_espelhar(self, mock_conn, mock_rec):
        """Quando os dois campos têm valor (caso classificável após Comercial
        digitar peso): usa QTDFIXADA (prioridade do peso classificado) e NÃO
        faz UPDATE de espelhamento."""
        from sankhya_integration.services.oracle_conn import salvar_vale_compra_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            (16.0, 20.0),  # PESO=16 (digitado entrada), QTDFIXADA=20 (Comercial corrigiu)
            (8888,),       # NUNOTA vale
            (10,),
            (5000,),
            (1,),
        ]
        mock_rec.return_value = {'ok': True}

        resultado = salvar_vale_compra_banco({
            'nunota_origem': 5000,
            'lote': 'L001',
            'itens_faturar': [{'codprod': 100, 'qtdneg': 60, 'vlrunit': 5, 'vlrtot': 300}],
        })

        self.assertTrue(resultado['ok'])

        # NENHUM UPDATE de espelhamento — semântica original mantida
        espelhamentos = [c for c in cursor.execute.call_args_list
                         if 'NVL(QTDFIXADA, 0) = 0' in c.args[0]
                         or 'NVL(PESO, 0) = 0' in c.args[0]]
        self.assertEqual(len(espelhamentos), 0, "Não deve espelhar quando ambos preenchidos")

        # INSERT TOP 13 usa QTDFIXADA (20), não o PESO (16)
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertEqual(binds['peso'], 20.0, "QTDFIXADA tem prioridade quando ambos preenchidos")


# ==========================================================================
# B5 — inserir_item_nota_banco espelha PESO → QTDFIXADA quando GERAPRODUCAO≠'S'
# ==========================================================================


class InserirItemEspelhamentoQtdFixadaTest(TestCase):
    """B5 — produto não-classificável recebe QTDFIXADA = PESO já no INSERT
    inicial da TOP 11, evitando estado intermediário NULL."""

    def _mock_obter_colunas(self):
        return {
            'NUNOTA', 'SEQUENCIA', 'CODEMP', 'CODPROD', 'QTDNEG', 'VLRUNIT',
            'VLRTOT', 'AD_NUMPEDIDOORIG', 'QTDCONFERIDA', 'PESO', 'CODVOL',
            'CODVOLPARC', 'CODLOCALORIG', 'CODAGREGACAO', 'OBSERVACAO',
            'GERAPRODUCAO', 'QTDFIXADA',
        }

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item')
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_geraproducao_N_com_peso_grava_qtdfixada(self, mock_conn, mock_perm, mock_cols, mock_seq):
        """GERAPRODUCAO='N' + PESO=20 → INSERT inclui QTDFIXADA=20."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        mock_perm.return_value = True
        mock_cols.return_value = self._mock_obter_colunas()
        mock_seq.return_value = 1
        # SELECT CODEMP, DTNEG, CODPARC, AD_NUMPEDIDOORIG
        cursor.fetchone.return_value = (10, None, 200, 5000)

        resultado = inserir_item_nota_banco({
            'NUNOTA': 5000, 'CODPROD': 100, 'QTDNEG': 50,
            'VLRUNIT': 5, 'PESO': 20, 'CODVOL': 'CX',
            'GERAPRODUCAO': 'N',
        })

        self.assertTrue(resultado['ok'], f"Veio: {resultado}")

        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        self.assertEqual(len(inserts), 1)
        sql = inserts[0].args[0]
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertIn('QTDFIXADA', sql)
        self.assertEqual(binds.get('QTDFIXADA'), 20.0)

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item')
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_geraproducao_S_nao_grava_qtdfixada(self, mock_conn, mock_perm, mock_cols, mock_seq):
        """GERAPRODUCAO='S' (classificável) + PESO=20 → QTDFIXADA NÃO entra no
        INSERT; fica NULL até Comercial digitar Peso CX Classificado."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        mock_perm.return_value = True
        mock_cols.return_value = self._mock_obter_colunas()
        mock_seq.return_value = 1
        cursor.fetchone.return_value = (10, None, 200, 5000)

        resultado = inserir_item_nota_banco({
            'NUNOTA': 5000, 'CODPROD': 100, 'QTDNEG': 50,
            'VLRUNIT': 5, 'PESO': 20, 'CODVOL': 'CX',
            'GERAPRODUCAO': 'S',
        })

        self.assertTrue(resultado['ok'])
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        self.assertEqual(len(inserts), 1)
        sql = inserts[0].args[0]
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        # Coluna QTDFIXADA não pode estar no INSERT
        self.assertNotIn('QTDFIXADA', sql)
        self.assertNotIn('QTDFIXADA', binds)

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item')
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_sem_geraproducao_nao_grava_qtdfixada(self, mock_conn, mock_perm, mock_cols, mock_seq):
        """Quando GERAPRODUCAO não vem (Venda, Combustível, etc.) → não espelha."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        mock_perm.return_value = True
        mock_cols.return_value = self._mock_obter_colunas()
        mock_seq.return_value = 1
        cursor.fetchone.return_value = (10, None, 200, 5000)

        resultado = inserir_item_nota_banco({
            'NUNOTA': 5000, 'CODPROD': 100, 'QTDNEG': 50,
            'VLRUNIT': 5, 'PESO': 20, 'CODVOL': 'KG',
            # Sem GERAPRODUCAO
        })

        self.assertTrue(resultado['ok'])
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        sql = inserts[0].args[0]
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertNotIn('QTDFIXADA', sql)
        self.assertNotIn('QTDFIXADA', binds)

    @patch('sankhya_integration.services.oracle_conn.gerar_proxima_sequencia_item')
    @patch('sankhya_integration.services.oracle_conn._obter_colunas_da_tabela')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_geraproducao_N_com_peso_zero_nao_grava_qtdfixada(self, mock_conn, mock_perm, mock_cols, mock_seq):
        """GERAPRODUCAO='N' mas PESO=0 → não espelha (não tem o que espelhar)."""
        from sankhya_integration.services.oracle_conn import inserir_item_nota_banco

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        mock_perm.return_value = True
        mock_cols.return_value = self._mock_obter_colunas()
        mock_seq.return_value = 1
        cursor.fetchone.return_value = (10, None, 200, 5000)

        resultado = inserir_item_nota_banco({
            'NUNOTA': 5000, 'CODPROD': 100, 'QTDNEG': 50,
            'VLRUNIT': 5, 'PESO': 0, 'CODVOL': 'KG',
            'GERAPRODUCAO': 'N',
        })

        self.assertTrue(resultado['ok'])
        inserts = [c for c in cursor.execute.call_args_list if 'INSERT INTO TGFITE' in c.args[0]]
        sql = inserts[0].args[0]
        binds = inserts[0].args[1] if len(inserts[0].args) > 1 else inserts[0].kwargs
        self.assertNotIn('QTDFIXADA', sql)
        self.assertNotIn('QTDFIXADA', binds)


# ==========================================================================
# B6 — upsert_preco_in_natura_modalFaturamento propaga preço pra TOP 11
# ==========================================================================


class UpsertPrecoModalFaturamentoTest(TestCase):
    """B6 — preço definido no modalFaturamento (Comercial) deve replicar pra
    TGFITE da TOP 11 quando o produto for não-classificável (in natura)."""

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_geraproducao_N_propaga_preco_para_top11(self, mock_conn, mock_perm, mock_rec):
        """GERAPRODUCAO='N' → UPDATE PRECOBASE/VLRUNIT/VLRTOT na TOP 11 ocorre + recalcula cabeçalho TOP 11."""
        from sankhya_integration.services.oracle_conn import upsert_preco_in_natura_modalFaturamento

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        mock_perm.return_value = True
        mock_rec.return_value = {'ok': True}

        # SELECTs em ordem:
        # 1) MAX(NUNOTA) TOP 13 → 8888 (vale existe)
        # 2) (QTDCONFERIDA, CODVOL, PESO, CODAGREGACAO, GERAPRODUCAO) da TOP 11 → 8 cx, KG, 17, L001, 'N'
        # 3) VLROUTROS do TOP 13 (bloco INSS) → 0
        cursor.fetchone.side_effect = [
            (8888,),
            (8, 'CX', 17.0, 'L001', 'N'),
            (0,),
        ]
        cursor.rowcount = 1  # UPDATE da TOP 13 e da TOP 11 ambos afetam 1 linha

        res = upsert_preco_in_natura_modalFaturamento(
            nunota_origem=5000, nunota_13=0, codprod=100, novo_preco=80.0,
        )

        self.assertTrue(res.get('ok'), f"Veio: {res}")

        # UPDATE na TOP 11 com PRECOBASE/VLRUNIT/VLRTOT deve existir
        ups_top11 = [c for c in cursor.execute.call_args_list
                     if 'PRECOBASE' in c.args[0] and 'VLRUNIT' in c.args[0] and 'NUNOTA = :n_orig' in c.args[0]]
        self.assertEqual(len(ups_top11), 1, "Esperava 1 UPDATE de propagação na TOP 11")
        binds = ups_top11[0].kwargs
        self.assertEqual(binds['preco'], 80.0)
        self.assertEqual(binds['n_orig'], 5000)
        self.assertEqual(binds['prod'], 100)

        # recalcular_totais_nota_banco deve ter sido chamado pra TOP 11 também
        chamadas_recalc = [args for args, kwargs in
                           [(c.args, c.kwargs) for c in mock_rec.call_args_list]]
        nunotas_recalculadas = [a[0] for a in chamadas_recalc if a]
        self.assertIn(5000, nunotas_recalculadas, "recalcular deve ser chamado com NUNOTA origem (TOP 11)")

    @patch('sankhya_integration.services.oracle_conn.recalcular_totais_nota_banco')
    @patch('sankhya_integration.services.oracle_conn.verificar_permissao_escrita')
    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_geraproducao_S_nao_propaga_preco_para_top11(self, mock_conn, mock_perm, mock_rec):
        """GERAPRODUCAO='S' (classificável) → preço só fica na TOP 13, TOP 11 intacta."""
        from sankhya_integration.services.oracle_conn import upsert_preco_in_natura_modalFaturamento

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        mock_perm.return_value = True
        mock_rec.return_value = {'ok': True}

        cursor.fetchone.side_effect = [
            (8888,),                              # NUNOTA TOP 13
            (10, 'CX', 17.0, 'L001', 'S'),        # TOP 11: GERAPRODUCAO='S'
            (0,),                                  # VLROUTROS
        ]
        cursor.rowcount = 1

        res = upsert_preco_in_natura_modalFaturamento(
            nunota_origem=5000, nunota_13=0, codprod=100, novo_preco=80.0,
        )

        self.assertTrue(res.get('ok'))

        # NENHUM UPDATE com NUNOTA = :n_orig na TOP 11 deve ter rodado
        ups_top11 = [c for c in cursor.execute.call_args_list
                     if 'NUNOTA = :n_orig' in c.args[0]]
        self.assertEqual(len(ups_top11), 0,
                         "Classificável não deve propagar preço pra TOP 11")

        # recalcular não deve ter sido chamado com NUNOTA origem
        nunotas_recalc = [c.args[0] for c in mock_rec.call_args_list if c.args]
        self.assertNotIn(5000, nunotas_recalc,
                         "recalcular não deve ser chamado pra TOP 11 quando GERAPRODUCAO='S'")


# ==========================================================================
# B3 — atualizar_peso_comercial_entrada propaga PESO pra TOP 13 quando existe
# ==========================================================================


class AtualizarPesoComercialPropagacaoTest(TestCase):
    """Quando operador altera 'Peso CX Classificado' na TOP 11, deve propagar
    pro PESO de todos os itens da TOP 13 do mesmo lote (se vale existir)."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_atualiza_top11_e_propaga_top13_quando_vale_existe(self, mock_conn):
        from sankhya_integration.services.oracle_conn import atualizar_peso_comercial_entrada

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            ('NUNOTAS123D260515',),   # SELECT CODAGREGACAO da TOP 11 linha alterada
            (8888,),                  # SELECT MAX(NUNOTA) TOP 13 → vale existe
        ]
        # UPDATE da TOP 13 afetou 2 linhas (Extra + Médio)
        cursor.rowcount = 2

        resultado = atualizar_peso_comercial_entrada(nunota=5000, sequencia=1, peso_classificado=20.0)

        self.assertTrue(resultado['ok'])
        self.assertEqual(resultado['propagado_top13'], 2)

        # Deve ter rodado: UPDATE TOP 11 + SELECT lote + SELECT vale + UPDATE TOP 13
        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(len(sqls), 4, f"Sequência esperada de 4 execs, veio: {sqls}")
        self.assertIn('UPDATE TGFITE SET QTDFIXADA', sqls[0])
        self.assertIn('SELECT CODAGREGACAO', sqls[1])
        self.assertIn('CODTIPOPER = 13', sqls[2])
        self.assertIn('UPDATE TGFITE SET PESO', sqls[3])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_atualiza_apenas_top11_quando_vale_nao_existe(self, mock_conn):
        from sankhya_integration.services.oracle_conn import atualizar_peso_comercial_entrada

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.side_effect = [
            ('L001',),    # CODAGREGACAO da TOP 11
            (None,),      # MAX(NUNOTA) TOP 13 → não existe vale
        ]

        resultado = atualizar_peso_comercial_entrada(nunota=5000, sequencia=1, peso_classificado=20.0)

        self.assertTrue(resultado['ok'])
        self.assertEqual(resultado['propagado_top13'], 0)

        # UPDATE da TOP 13 NÃO deve ter sido executado
        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(len(sqls), 3, f"Sem vale: só 3 execs (UPDATE 11 + 2 SELECTs); veio: {sqls}")
        self.assertFalse(
            any('UPDATE TGFITE SET PESO' in s for s in sqls),
            "Não deveria ter UPDATE em TGFITE.PESO sem TOP 13 existente",
        )

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_lote_null_na_top11_pula_propagacao(self, mock_conn):
        """Defesa: se CODAGREGACAO da linha for NULL (caso degenerado), não tenta
        buscar/propagar — segue só com o UPDATE da TOP 11."""
        from sankhya_integration.services.oracle_conn import atualizar_peso_comercial_entrada

        conn_ctx, _, cursor = _conn_cursor_mock()
        mock_conn.return_value = conn_ctx
        cursor.fetchone.return_value = (None,)   # CODAGREGACAO NULL

        resultado = atualizar_peso_comercial_entrada(nunota=5000, sequencia=1, peso_classificado=20.0)

        self.assertTrue(resultado['ok'])
        self.assertEqual(resultado['propagado_top13'], 0)

        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        # UPDATE TOP 11 + SELECT CODAGREGACAO (e nada mais — pulou os 2 últimos)
        self.assertEqual(len(sqls), 2)
        self.assertFalse(any('CODTIPOPER = 13' in s for s in sqls))
