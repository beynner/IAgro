"""
Testes unitários do serviço faturamento.py.

faturamento.py importa funções de oracle_conn no topo do módulo; como essas
dependências não estão disponíveis fora do ambiente com Oracle, o módulo
inteiro de oracle_conn é substituído por um MagicMock antes de qualquer
import de faturamento. Nenhum código de produção é alterado.
"""
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Isola o módulo oracle_conn antes do primeiro import de faturamento.
# Sem isso, o import-level de faturamento.py levanta ImportError porque
# funções como `consolidate_vale_to_pedido` podem não existir em oracle_conn.
# ---------------------------------------------------------------------------
_mock_oracle_conn = MagicMock()
sys.modules.setdefault(
    'sankhya_integration.services.oracle_conn', _mock_oracle_conn
)

from django.test import SimpleTestCase  # noqa: E402 — import após mock


# ---------------------------------------------------------------------------
# _to_int_or
# ---------------------------------------------------------------------------

class ToIntOrTest(SimpleTestCase):

    def _fn(self, val, default=None):
        from sankhya_integration.services.faturamento import _to_int_or
        return _to_int_or(val, default)

    def test_inteiro(self):
        self.assertEqual(self._fn(5), 5)

    def test_string_numerica(self):
        self.assertEqual(self._fn('10'), 10)

    def test_none_retorna_default(self):
        self.assertIsNone(self._fn(None))
        self.assertEqual(self._fn(None, default=-1), -1)

    def test_string_vazia_retorna_default(self):
        self.assertIsNone(self._fn(''))

    def test_none_literal_retorna_default(self):
        self.assertIsNone(self._fn('None'))
        self.assertIsNone(self._fn('none'))
        self.assertIsNone(self._fn('null'))

    def test_valor_invalido_retorna_default(self):
        self.assertIsNone(self._fn('xyz'))
        self.assertEqual(self._fn('abc', default=0), 0)

    def test_string_inteira(self):
        self.assertEqual(self._fn('3'), 3)


# ---------------------------------------------------------------------------
# _to_float_or
# ---------------------------------------------------------------------------

class ToFloatOrTest(SimpleTestCase):

    def _fn(self, val, default=None):
        from sankhya_integration.services.faturamento import _to_float_or
        return _to_float_or(val, default)

    def test_float_direto(self):
        self.assertAlmostEqual(self._fn(3.14), 3.14)

    def test_inteiro_vira_float(self):
        self.assertAlmostEqual(self._fn(10), 10.0)

    def test_string_ponto(self):
        self.assertAlmostEqual(self._fn('1.5'), 1.5)

    def test_string_virgula(self):
        self.assertAlmostEqual(self._fn('1,5'), 1.5)

    def test_string_formato_brasileiro_com_milhar(self):
        # '1.234,56' → remove ponto de milhar, troca vírgula → '1234.56'
        self.assertAlmostEqual(self._fn('1.234,56'), 1234.56)

    def test_string_com_cifrao_reais(self):
        self.assertAlmostEqual(self._fn('R$ 99,90'), 99.90)

    def test_none_retorna_default(self):
        self.assertIsNone(self._fn(None))

    def test_string_vazia_retorna_default(self):
        self.assertIsNone(self._fn(''))

    def test_invalido_retorna_default(self):
        self.assertIsNone(self._fn('abc'))
        self.assertEqual(self._fn('abc', default=0.0), 0.0)


# ---------------------------------------------------------------------------
# _next_wednesday
# ---------------------------------------------------------------------------

class NextWednesdayTest(SimpleTestCase):

    def _fn(self, base=None):
        from sankhya_integration.services.faturamento import _next_wednesday
        return _next_wednesday(base)

    def test_resultado_e_sempre_quarta(self):
        """Para qualquer data de base, o resultado deve ser quarta (weekday=2)."""
        base = date(2024, 1, 1)  # segunda-feira
        for _ in range(14):
            result = self._fn(base)
            self.assertEqual(
                result.weekday(), 2,
                f"Esperava quarta para base={base}, obteve {result} (weekday={result.weekday()})"
            )
            base += timedelta(days=1)

    def test_de_uma_segunda_vai_para_proxima_quarta(self):
        segunda = date(2024, 1, 1)
        self.assertEqual(self._fn(segunda), date(2024, 1, 3))

    def test_de_quarta_vai_para_proxima_quarta(self):
        """Quarta → próxima quarta (7 dias à frente, não a mesma)."""
        quarta = date(2024, 1, 3)
        self.assertEqual(self._fn(quarta), date(2024, 1, 10))

    def test_de_quinta_vai_para_proxima_quarta(self):
        quinta = date(2024, 1, 4)
        self.assertEqual(self._fn(quinta), date(2024, 1, 10))

    def test_sem_base_usa_hoje_e_retorna_quarta_futura(self):
        result = self._fn()
        self.assertEqual(result.weekday(), 2)
        self.assertGreater(result, date.today())


# ---------------------------------------------------------------------------
# _parse_seq_list
# ---------------------------------------------------------------------------

class ParseSeqListTest(SimpleTestCase):

    def _fn(self, value):
        from sankhya_integration.services.faturamento import _parse_seq_list
        return _parse_seq_list(value)

    def test_none_retorna_vazio(self):
        self.assertEqual(self._fn(None), [])

    def test_string_vazia_retorna_vazio(self):
        self.assertEqual(self._fn(''), [])

    def test_string_unico_valor(self):
        self.assertEqual(self._fn('3'), [3])

    def test_string_multiplos_valores(self):
        self.assertEqual(self._fn('1,2,3'), [1, 2, 3])

    def test_lista_de_inteiros(self):
        self.assertEqual(self._fn([4, 5, 6]), [4, 5, 6])

    def test_deduplicacao_preserva_ordem(self):
        self.assertEqual(self._fn('2,1,2,3'), [2, 1, 3])

    def test_valores_invalidos_ignorados(self):
        self.assertEqual(self._fn('1,abc,2'), [1, 2])


# ---------------------------------------------------------------------------
# gerar_vale_compra_top13 — validações de entrada (sem I/O Oracle)
# ---------------------------------------------------------------------------

class GerarValeCompraTop13ValidacaoTest(SimpleTestCase):

    def _fn(self, nunota_11, itens_precos):
        from sankhya_integration.services.faturamento import gerar_vale_compra_top13
        return gerar_vale_compra_top13(nunota_11, itens_precos)

    def test_escrita_desabilitada_retorna_erro(self):
        """Quando escrita está desabilitada, retorna ok=False sem tocar no banco."""
        _mock_oracle_conn.is_write_enabled.return_value = False
        result = self._fn(100, [{'sequencia': 1, 'preco': 10.0}])
        self.assertFalse(result.get('ok'))
        self.assertIn('error', result)

    def test_nunota_invalido_retorna_erro(self):
        """nunota_11 não conversível para int deve retornar ok=False."""
        _mock_oracle_conn.is_write_enabled.return_value = True
        result = self._fn('invalido', [])
        self.assertFalse(result.get('ok'))
        self.assertIn('error', result)

    def test_sem_itens_retorna_erro(self):
        """Lista de itens vazia deve retornar ok=False com 'Sem itens'."""
        _mock_oracle_conn.is_write_enabled.return_value = True
        result = self._fn(100, [])
        self.assertFalse(result.get('ok'))
        self.assertEqual(result.get('error'), 'Sem itens')

    def test_sequencia_zero_retorna_erro(self):
        """Item com sequência 0 deve retornar ok=False."""
        _mock_oracle_conn.is_write_enabled.return_value = True
        result = self._fn(100, [{'sequencia': 0, 'preco': 10.0}])
        self.assertFalse(result.get('ok'))
        self.assertIn('Sequencia invalida', result.get('error', ''))

    def test_preco_zero_retorna_erro(self):
        """Item com preço unitário <= 0 deve ser rejeitado."""
        _mock_oracle_conn.is_write_enabled.return_value = True
        result = self._fn(100, [{'sequencia': 1, 'preco': 0.0}])
        self.assertFalse(result.get('ok'))
        self.assertIn('error', result)

    def test_sem_preco_unitario_nem_total_retorna_erro(self):
        """Item sem preco e sem preco_total deve ser rejeitado."""
        _mock_oracle_conn.is_write_enabled.return_value = True
        result = self._fn(100, [{'sequencia': 1}])
        self.assertFalse(result.get('ok'))
        self.assertIn('error', result)
