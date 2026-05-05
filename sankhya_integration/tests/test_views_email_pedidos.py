"""
Testes do módulo de Importação de Pedidos por E-mail.

Estrutura por etapa do roadmap:
    E2 → OracleAdapterEmailTest          (funções aditivas em oracle_conn.py)
    E3 → WorkerImapTest                  (management command de coleta IMAP)
    E4 → ParserLLMTest                   (cliente Ollama local)
    E5 → EmailEndpointsTest              (listar/detalhar/descartar/reparser/PDF)
    E7 → ConfirmarPedidoEmailTest        (promoção para TGFCAB via APIs Venda)

Todas as chamadas ao Oracle, IMAP e Ollama são mockadas. Nada toca em rede real.
"""
import json
from datetime import datetime, date
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse


def _login_session(client, grupos=None, codusu=1, nome='Teste'):
    """Injeta sessão autenticada com os grupos informados."""
    session = client.session
    session['codusu'] = codusu
    session['nomeusu'] = nome
    session['nome'] = nome
    session['grupos'] = grupos or ['10']  # grupo Vendas por default
    session.save()


def _mock_conn_ctx(mock_obter, cursor):
    """Encapsula o context manager `with obter_conexao_oracle() as conn` num MagicMock."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    mock_obter.return_value.__enter__.return_value = conn
    mock_obter.return_value.__exit__.return_value = None
    return conn


# ===========================================================================
# E2 — OracleAdapterEmailTest
# Funções em oracle_conn.py para CRUD em AD_PEDIDO_EMAIL_*
# ===========================================================================

class OracleAdapterEmailTest(TestCase):
    """Cobre as funções aditivas adicionadas em oracle_conn.py para o módulo
    de importação por e-mail. Não toca em queries existentes."""

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_inserir_pedido_email_recebido_grava_e_retorna_id(self, mock_obter):
        cursor = MagicMock()
        # 1º execute: SEQ.NEXTVAL retorna 42; 2º execute: o INSERT (sem return)
        cursor.fetchone.side_effect = [(42,)]
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import inserir_pedido_email_recebido
        res = inserir_pedido_email_recebido({
            'MESSAGE_ID': '<abc@host>',
            'REMETENTE': 'cliente@x.com',
            'ASSUNTO': 'Pedido de tomate',
            'RECEBIDO_EM': datetime(2026, 5, 1, 10, 0),
            'PROCESSADO_EM': datetime(2026, 5, 1, 10, 1),
            'PDF_PATH': r'z:\media\foo.pdf',
            'PDF_TEXTO': 'TEXTO EXTRAIDO',
        })

        self.assertTrue(res['ok'])
        self.assertEqual(res['id'], 42)
        # Verifica que a sequence foi consultada antes do INSERT
        self.assertIn('SEQ_AD_PEDIDO_EMAIL_RECEBIDO', cursor.execute.call_args_list[0][0][0])
        # E que o INSERT realmente aconteceu
        self.assertIn('INSERT INTO AD_PEDIDO_EMAIL_RECEBIDO',
                      cursor.execute.call_args_list[1][0][0])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_inserir_pedido_email_status_invalido_recusa(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(99,)]
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import inserir_pedido_email_recebido
        res = inserir_pedido_email_recebido({
            'MESSAGE_ID': '<x>',
            'STATUS': 'XPTO_INVALIDO',
        })
        self.assertFalse(res['ok'])
        self.assertIn('STATUS inválido', res['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_inserir_pedido_email_item_grava_com_recebido_id(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(7,)]
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import inserir_pedido_email_item
        res = inserir_pedido_email_item({
            'RECEBIDO_ID': 42,
            'SEQUENCIA': 1,
            'DESCRICAO_PDF': 'TOMATE BANDEJA 500G',
            'CODPROD_SUGERIDO': 1234,
            'CODPROD_CONFIANCA': 0.92,
            'QTD': 10,
            'CODVOL': 'CX',
            'PRECO_UNIT': 5.50,
        })
        self.assertTrue(res['ok'])
        self.assertEqual(res['id'], 7)
        sql_insert = cursor.execute.call_args_list[1][0][0]
        self.assertIn('AD_PEDIDO_EMAIL_ITEM', sql_insert)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_listar_pendentes_default_filtra_por_pendente_revisao(self, mock_obter):
        cursor = MagicMock()
        cursor.description = [
            ('ID',), ('MESSAGE_ID',), ('REMETENTE',), ('ASSUNTO',),
            ('RECEBIDO_EM',), ('PROCESSADO_EM',),
            ('LLM_CONFIANCA_GERAL',), ('CODPARC_SUGERIDO',),
            ('STATUS',), ('NUNOTA_GERADO',), ('CRIADO_EM',), ('RN',),
        ]
        cursor.fetchall.return_value = [
            (1, '<a>', 'a@x.com', 'P1', None, None, 0.9, 1234, 'PENDENTE_REVISAO', None, None, 1),
            (2, '<b>', 'b@x.com', 'P2', None, None, 0.7, 5678, 'PENDENTE_REVISAO', None, None, 2),
        ]
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import listar_pedidos_email_pendentes
        linhas = listar_pedidos_email_pendentes()
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[0]['status'], 'PENDENTE_REVISAO')
        self.assertNotIn('rn', linhas[0])  # `rn` removido do retorno
        # Confirma que o filtro default entrou no SQL
        sql = cursor.execute.call_args[0][0]
        self.assertIn('STATUS = :status', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_listar_pendentes_aceita_status_lista(self, mock_obter):
        cursor = MagicMock()
        cursor.description = [('ID',), ('STATUS',), ('RN',)]
        cursor.fetchall.return_value = []
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import listar_pedidos_email_pendentes
        listar_pedidos_email_pendentes(filtros={'status': ['PENDENTE_REVISAO', 'ERRO_PARSER']})
        sql = cursor.execute.call_args[0][0]
        self.assertIn('STATUS IN', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_obter_pedido_email_completo_devolve_cab_e_itens(self, mock_obter):
        cursor = MagicMock()
        # Primeiro fetchone: cabeçalho. Depois fetchall: itens.
        cursor.description = [
            ('ID',), ('MESSAGE_ID',), ('REMETENTE',), ('ASSUNTO',),
            ('RECEBIDO_EM',), ('PROCESSADO_EM',),
            ('PDF_PATH',), ('PDF_TEXTO',),
            ('LLM_RESPOSTA',), ('LLM_MODELO',),
            ('LLM_TOKENS_IN',), ('LLM_TOKENS_OUT',), ('LLM_CONFIANCA_GERAL',),
            ('CODPARC_SUGERIDO',), ('CODEMP_SUGERIDO',),
            ('DTNEG_SUGERIDA',), ('CODTIPVENDA_SUGERIDO',),
            ('OBSERVACAO_EXTRAIDA',),
            ('STATUS',), ('MOTIVO_DESCARTE',),
            ('NUNOTA_GERADO',), ('CONFIRMADO_POR',), ('CONFIRMADO_EM',), ('CRIADO_EM',),
        ]
        # Após o execute do cabeçalho, fetchone retorna a linha
        cursor.fetchone.return_value = (
            42, '<msg>', 'cli@x.com', 'Pedido', None, None,
            r'z:\f.pdf', 'TXT', '{}', 'qwen2.5:7b-instruct',
            100, 200, 0.88, 1234, 10, date(2026, 5, 1), 5,
            'observação',
            'PENDENTE_REVISAO', None, None, None, None, None,
        )
        # Para os itens, simulamos description diferente após o segundo execute
        # No nosso código real: o segundo cur.execute redefine .description, mas
        # aqui MagicMock guarda o último. Para teste simples, configuramos para
        # que a segunda lista de itens retorne vazia.
        cursor.fetchall.return_value = []  # nenhum item
        # Mock: o teste cobre que cabeçalho é lido e itens são consultados.
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import obter_pedido_email_completo
        res = obter_pedido_email_completo(42)
        self.assertIsNotNone(res)
        self.assertEqual(res['id'], 42)
        self.assertEqual(res['status'], 'PENDENTE_REVISAO')
        self.assertIn('itens', res)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_obter_pedido_email_completo_inexistente_retorna_none(self, mock_obter):
        cursor = MagicMock()
        cursor.description = [('ID',)]
        cursor.fetchone.return_value = None
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import obter_pedido_email_completo
        self.assertIsNone(obter_pedido_email_completo(999))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_atualizar_status_valido_passa_e_invalido_recusa(self, mock_obter):
        cursor = MagicMock()
        cursor.rowcount = 1
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import atualizar_pedido_email_status
        ok = atualizar_pedido_email_status(42, 'CONFIRMADO')
        self.assertTrue(ok['ok'])
        bad = atualizar_pedido_email_status(42, 'INVENTADO_NAO_EXISTE')
        self.assertFalse(bad['ok'])
        self.assertIn('STATUS inválido', bad['error'])

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_atualizar_pedido_email_item_so_aceita_campos_permitidos(self, mock_obter):
        cursor = MagicMock()
        cursor.rowcount = 1
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import atualizar_pedido_email_item
        # Tudo inválido → nada pra atualizar
        res = atualizar_pedido_email_item(7, {'XYZ_NAO_EXISTE': 1})
        self.assertFalse(res['ok'])
        self.assertIn('Nenhum campo válido', res['error'])
        # Pelo menos um permitido → executa
        res2 = atualizar_pedido_email_item(7, {'CODPROD_FINAL': 1234, 'QTD': 10})
        self.assertTrue(res2['ok'])
        sql = cursor.execute.call_args[0][0]
        self.assertIn('CODPROD_FINAL', sql)
        self.assertIn('QTD', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_vincular_nunota_marca_confirmado_e_grava_codusu(self, mock_obter):
        cursor = MagicMock()
        cursor.rowcount = 1
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import vincular_nunota_pedido_email
        res = vincular_nunota_pedido_email(recebido_id=42, nunota=999, codusu=7)
        self.assertTrue(res['ok'])
        sql = cursor.execute.call_args[0][0]
        self.assertIn("STATUS         = 'CONFIRMADO'", sql)
        self.assertIn('NUNOTA_GERADO', sql)
        self.assertIn('CONFIRMADO_POR', sql)

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_consultar_ultimo_pedido_codparc_devolve_dict(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.return_value = (10, 5, date(2026, 4, 30))
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_ultimo_pedido_codparc
        res = consultar_ultimo_pedido_codparc(1234)
        self.assertEqual(res, {'codemp': 10, 'codtipvenda': 5, 'dtneg': date(2026, 4, 30)})

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_consultar_ultimo_pedido_codparc_inexistente_retorna_none(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_ultimo_pedido_codparc
        self.assertIsNone(consultar_ultimo_pedido_codparc(9999))

    def test_consultar_ultimo_pedido_codparc_zero_ou_none_curto_circuita(self):
        from sankhya_integration.services.oracle_conn import consultar_ultimo_pedido_codparc
        self.assertIsNone(consultar_ultimo_pedido_codparc(None))
        self.assertIsNone(consultar_ultimo_pedido_codparc(0))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_consultar_pedido_email_por_message_id_existente(self, mock_obter):
        cursor = MagicMock()
        cursor.fetchone.return_value = (42, 'PENDENTE_REVISAO')
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import consultar_pedido_email_por_message_id
        res = consultar_pedido_email_por_message_id('<abc@host>')
        self.assertEqual(res['id'], 42)
        self.assertEqual(res['status'], 'PENDENTE_REVISAO')

    def test_consultar_pedido_email_por_message_id_vazio_retorna_none(self):
        from sankhya_integration.services.oracle_conn import consultar_pedido_email_por_message_id
        self.assertIsNone(consultar_pedido_email_por_message_id(''))
        self.assertIsNone(consultar_pedido_email_por_message_id(None))

    @patch('sankhya_integration.services.oracle_conn.obter_conexao_oracle')
    def test_atualizar_parser_resultado_grava_e_muda_status(self, mock_obter):
        cursor = MagicMock()
        cursor.rowcount = 1
        _mock_conn_ctx(mock_obter, cursor)

        from sankhya_integration.services.oracle_conn import atualizar_pedido_email_parser_resultado
        res = atualizar_pedido_email_parser_resultado(42, {
            'LLM_RESPOSTA': '{"foo": "bar"}',
            'LLM_MODELO': 'qwen2.5:7b-instruct',
            'LLM_TOKENS_IN': 1500,
            'LLM_TOKENS_OUT': 300,
            'LLM_CONFIANCA_GERAL': 0.85,
            'CODPARC_SUGERIDO': 1234,
            'CODEMP_SUGERIDO': 10,
            'DTNEG_SUGERIDA': date(2026, 5, 1),
            'CODTIPVENDA_SUGERIDO': 5,
            'OBSERVACAO_EXTRAIDA': 'Entrega urgente',
        })
        self.assertTrue(res['ok'])
        sql = cursor.execute.call_args[0][0]
        self.assertIn("STATUS               = 'PENDENTE_REVISAO'", sql)


# ===========================================================================
# E3 — WorkerImapTest
# Cobre o management command `colher_pedidos_email` com IMAP mockado.
# ===========================================================================

class _FakeAttachment:
    def __init__(self, filename, payload):
        self.filename = filename
        self.payload = payload


class _FakeMsg:
    def __init__(self, uid, from_, subject, message_id, date_, attachments):
        self.uid = uid
        self.from_ = from_
        self.subject = subject
        self.headers = {'message-id': (message_id,)}
        self.date = date_
        self.attachments = attachments


class _FakeMailbox:
    """Stand-in mínimo para imap_tools.MailBox usado nos testes."""
    def __init__(self, msgs):
        self._msgs = msgs
        self.moves: list[tuple[str, str]] = []  # (uid, destino)

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def login(self, *a, **kw): return self

    def fetch(self, *args, **kwargs):
        for m in self._msgs:
            yield m

    def move(self, uids, dest):
        for uid in uids:
            self.moves.append((uid, dest))


class WorkerImapTest(TestCase):
    """Os testes mockam imap_tools.MailBox, pdfplumber e as funções de oracle_conn
    usadas pelo command. Nada de IO real."""

    def _env_minimo(self):
        return {
            'EMAIL_IMAP_HOST': 'imap.titan.email',
            'EMAIL_IMAP_PORT': '993',
            'EMAIL_IMAP_USER': 'pedidos@x.com',
            'EMAIL_IMAP_PASS': 'senha',
            'EMAIL_IMAP_FOLDER_ENTRADA': 'IN',
            'EMAIL_IMAP_FOLDER_PROCESSADOS': 'OK',
            'EMAIL_IMAP_FOLDER_ERROS': 'ERR',
            'PEDIDO_EMAIL_PDF_DIR': '',  # preenchido por tearDown se preciso
        }

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix='iagro_email_test_')
        self.env = self._env_minimo()
        self.env['PEDIDO_EMAIL_PDF_DIR'] = self.tmp

    def tearDown(self):
        import shutil
        try: shutil.rmtree(self.tmp, ignore_errors=True)
        except Exception: pass

    def _rodar_command(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('colher_pedidos_email', stdout=out)
        return out.getvalue()

    @patch('sankhya_integration.management.commands.colher_pedidos_email.Command._extrair_texto_pdf')
    @patch('sankhya_integration.services.oracle_conn.inserir_pedido_email_recebido')
    @patch('sankhya_integration.services.oracle_conn.consultar_pedido_email_por_message_id',
           return_value=None)
    def test_processa_email_com_pdf_e_grava_recebido(
        self, _msgid_check, mock_insert, mock_extrair_texto,
    ):
        mock_extrair_texto.return_value = 'TEXTO EXTRAIDO DO PDF'
        mock_insert.return_value = {'ok': True, 'id': 1}

        msgs = [_FakeMsg(
            uid='100',
            from_='cliente@x.com',
            subject='Pedido tomate',
            message_id='<m1@x>',
            date_=datetime(2026, 5, 1, 9, 0),
            attachments=[_FakeAttachment('pedido.pdf', b'%PDF-1.4 fake')],
        )]
        fake_mailbox = _FakeMailbox(msgs)

        with patch.dict('os.environ', self.env, clear=False), \
             patch('imap_tools.MailBox', return_value=fake_mailbox):
            saida = self._rodar_command()

        self.assertTrue(mock_insert.called)
        argp = mock_insert.call_args[0][0]
        self.assertEqual(argp['MESSAGE_ID'], '<m1@x>')
        self.assertEqual(argp['STATUS'], 'AGUARDANDO_PARSER')
        self.assertEqual(argp['REMETENTE'], 'cliente@x.com')
        self.assertIn('TEXTO EXTRAIDO', argp['PDF_TEXTO'])
        # E-mail movido para Processados
        self.assertIn(('100', 'OK'), fake_mailbox.moves)
        self.assertIn('Concluído', saida)

    @patch('sankhya_integration.services.oracle_conn.inserir_pedido_email_recebido')
    @patch('sankhya_integration.services.oracle_conn.consultar_pedido_email_por_message_id',
           return_value={'id': 99, 'status': 'CONFIRMADO'})  # já existe
    def test_email_duplicado_ignora_sem_inserir(self, _check, mock_insert):
        msgs = [_FakeMsg(
            uid='200', from_='c@x.com', subject='dup',
            message_id='<m1@x>', date_=datetime(2026, 5, 1),
            attachments=[_FakeAttachment('p.pdf', b'%PDF')],
        )]
        fake_mailbox = _FakeMailbox(msgs)
        with patch.dict('os.environ', self.env, clear=False), \
             patch('imap_tools.MailBox', return_value=fake_mailbox):
            self._rodar_command()
        self.assertFalse(mock_insert.called)
        self.assertIn(('200', 'OK'), fake_mailbox.moves)

    @patch('sankhya_integration.services.oracle_conn.inserir_pedido_email_recebido')
    @patch('sankhya_integration.services.oracle_conn.consultar_pedido_email_por_message_id',
           return_value=None)
    def test_email_sem_pdf_vai_para_erros(self, _check, mock_insert):
        msgs = [_FakeMsg(
            uid='300', from_='c@x.com', subject='sem-anexo',
            message_id='<m2@x>', date_=datetime(2026, 5, 1),
            attachments=[_FakeAttachment('texto.txt', b'isso nao e pdf')],
        )]
        fake_mailbox = _FakeMailbox(msgs)
        with patch.dict('os.environ', self.env, clear=False), \
             patch('imap_tools.MailBox', return_value=fake_mailbox):
            self._rodar_command()
        self.assertFalse(mock_insert.called)
        self.assertIn(('300', 'ERR'), fake_mailbox.moves)

    @patch('sankhya_integration.management.commands.colher_pedidos_email.Command._extrair_texto_pdf',
           return_value='')  # texto vazio
    @patch('sankhya_integration.services.oracle_conn.inserir_pedido_email_recebido',
           return_value={'ok': True, 'id': 5})
    @patch('sankhya_integration.services.oracle_conn.consultar_pedido_email_por_message_id',
           return_value=None)
    def test_pdf_sem_texto_grava_erro_pdf(
        self, _check, mock_insert, _ext,
    ):
        msgs = [_FakeMsg(
            uid='400', from_='c@x.com', subject='escaneado',
            message_id='<m3@x>', date_=datetime(2026, 5, 1),
            attachments=[_FakeAttachment('p.pdf', b'%PDF')],
        )]
        fake_mailbox = _FakeMailbox(msgs)
        with patch.dict('os.environ', self.env, clear=False), \
             patch('imap_tools.MailBox', return_value=fake_mailbox):
            self._rodar_command()
        self.assertTrue(mock_insert.called)
        argp = mock_insert.call_args[0][0]
        self.assertEqual(argp['STATUS'], 'ERRO_PDF')
        self.assertIsNone(argp['PDF_TEXTO'])

    def test_config_incompleta_levanta_erro(self):
        from django.core.management.base import CommandError
        env_vazio = self._env_minimo()
        env_vazio['EMAIL_IMAP_HOST'] = ''
        with patch.dict('os.environ', env_vazio, clear=False):
            with self.assertRaises(CommandError) as ctx:
                self._rodar_command()
            self.assertIn('Configuração incompleta', str(ctx.exception))


# ===========================================================================
# E4 — ParserLLMTest
# Cobre o módulo services/llm_local.py com cliente Ollama mockado.
# ===========================================================================

class ParserLLMTest(TestCase):
    """Testa extrair_pedido_de_pdf com Ollama mockado em vários cenários."""

    def test_texto_vazio_retorna_erro(self):
        from sankhya_integration.services.llm_local import extrair_pedido_de_pdf
        res = extrair_pedido_de_pdf('')
        self.assertFalse(res['ok'])
        self.assertIn('vazio', res['error'].lower())

    @patch('sankhya_integration.services.llm_local._cliente_ollama')
    def test_resposta_json_valida_e_normalizada(self, mock_cliente):
        # Resposta válida do Ollama: tem `message.content` com JSON e contadores de tokens
        fake_resposta = MagicMock()
        fake_resposta.message = MagicMock()
        fake_resposta.message.content = json.dumps({
            'cliente': {'nome': 'ASSAI', 'codparc_sugerido': 1234, 'confianca': 0.92},
            'data_negociacao': '2026-05-01',
            'observacao': 'Entrega urgente',
            'itens': [
                {'descricao_pdf': 'TOMATE BANDEJA', 'codprod_sugerido': 100,
                 'codprod_confianca': 0.85, 'qtd': 10, 'codvol': 'cx', 'preco_unit': 5.5},
            ],
            'confianca_geral': 0.88,
        })
        fake_resposta.prompt_eval_count = 1500
        fake_resposta.eval_count = 300
        cliente_mock = MagicMock()
        cliente_mock.chat.return_value = fake_resposta
        mock_cliente.return_value = cliente_mock

        from sankhya_integration.services.llm_local import extrair_pedido_de_pdf
        res = extrair_pedido_de_pdf(
            texto_pdf='ASSAI\nTOMATE BANDEJA 10cx',
            parceiros_contexto=[{'codparc': 1234, 'nome': 'ASSAI', 'cgc': '00.000.000/0001-00'}],
            produtos_contexto=[{'codprod': 100, 'descr': 'TOMATE BANDEJA 500G', 'codvol': 'CX'}],
        )
        self.assertTrue(res['ok'])
        self.assertEqual(res['cliente']['codparc_sugerido'], 1234)
        self.assertEqual(res['cliente']['confianca'], 0.92)
        self.assertEqual(len(res['itens']), 1)
        self.assertEqual(res['itens'][0]['codvol'], 'CX')  # uppercase forçado
        self.assertEqual(res['tokens_in'], 1500)
        self.assertEqual(res['tokens_out'], 300)
        self.assertIn('resposta_crua', res)

    @patch('sankhya_integration.services.llm_local._cliente_ollama')
    def test_resposta_com_fences_markdown_e_extra_recupera_json(self, mock_cliente):
        fake = MagicMock()
        fake.message = MagicMock()
        fake.message.content = (
            "Aqui está o JSON:\n"
            "```json\n"
            '{"cliente": {"nome": "X", "codparc_sugerido": 1, "confianca": 0.5},'
            ' "data_negociacao": null, "observacao": null,'
            ' "itens": [], "confianca_geral": 0.5}\n'
            "```"
        )
        fake.prompt_eval_count = 1
        fake.eval_count = 1
        cli = MagicMock()
        cli.chat.return_value = fake
        mock_cliente.return_value = cli

        from sankhya_integration.services.llm_local import extrair_pedido_de_pdf
        res = extrair_pedido_de_pdf('texto qualquer')
        self.assertTrue(res['ok'])
        self.assertEqual(res['cliente']['nome'], 'X')

    @patch('sankhya_integration.services.llm_local._cliente_ollama')
    def test_resposta_sem_json_retorna_erro(self, mock_cliente):
        fake = MagicMock()
        fake.message = MagicMock()
        fake.message.content = "Desculpe, não consigo extrair."
        cli = MagicMock(); cli.chat.return_value = fake
        mock_cliente.return_value = cli

        from sankhya_integration.services.llm_local import extrair_pedido_de_pdf
        res = extrair_pedido_de_pdf('texto qualquer')
        self.assertFalse(res['ok'])
        self.assertIn('JSON', res['error'])

    @patch('sankhya_integration.services.llm_local._cliente_ollama')
    def test_falha_ollama_retorna_erro_apos_retries(self, mock_cliente):
        cli = MagicMock()
        cli.chat.side_effect = ConnectionError('servidor offline')
        mock_cliente.return_value = cli

        # OLLAMA_MAX_RETRIES=1 para acelerar
        with patch.dict('os.environ', {'OLLAMA_MAX_RETRIES': '1'}, clear=False):
            from sankhya_integration.services.llm_local import extrair_pedido_de_pdf
            res = extrair_pedido_de_pdf('texto qualquer')
        self.assertFalse(res['ok'])
        self.assertIn('falharam', res['error'])

    def test_normalizacao_clipa_confianca_em_0_1(self):
        from sankhya_integration.services.llm_local import _normalizar_resposta
        out = _normalizar_resposta({
            'cliente': {'nome': 'X', 'codparc_sugerido': 1, 'confianca': 5.2},
            'itens': [{'qtd': 'abc', 'codprod_confianca': -1}],
            'confianca_geral': 'invalido',
        })
        self.assertEqual(out['cliente']['confianca'], 1.0)
        self.assertEqual(out['itens'][0]['codprod_confianca'], 0.0)
        self.assertIsNone(out['itens'][0]['qtd'])
        self.assertEqual(out['confianca_geral'], 0.0)


# ===========================================================================
# E4 — Fase 2 do worker (parser LLM dentro do command)
# ===========================================================================

class WorkerParserFase2Test(TestCase):
    """Cobre _rodar_parser_llm dentro do management command."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix='iagro_email_p2_')
        self.env = {
            'EMAIL_IMAP_HOST': 'h', 'EMAIL_IMAP_PORT': '993',
            'EMAIL_IMAP_USER': 'u', 'EMAIL_IMAP_PASS': 'p',
            'EMAIL_IMAP_FOLDER_ENTRADA': 'IN',
            'EMAIL_IMAP_FOLDER_PROCESSADOS': 'OK',
            'EMAIL_IMAP_FOLDER_ERROS': 'ERR',
            'PEDIDO_EMAIL_PDF_DIR': self.tmp,
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _rodar_skip_imap(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('colher_pedidos_email', '--skip-imap', stdout=out)
        return out.getvalue()

    @patch('sankhya_integration.management.commands.colher_pedidos_email.Command._carregar_contexto_produtos',
           return_value=[])
    @patch('sankhya_integration.management.commands.colher_pedidos_email.Command._carregar_contexto_parceiros',
           return_value=[])
    @patch('sankhya_integration.services.oracle_conn.consultar_ultimo_pedido_codparc',
           return_value={'codemp': 10, 'codtipvenda': 5, 'dtneg': None})
    @patch('sankhya_integration.services.oracle_conn.inserir_pedido_email_item',
           return_value={'ok': True, 'id': 1})
    @patch('sankhya_integration.services.oracle_conn.atualizar_pedido_email_parser_resultado',
           return_value={'ok': True})
    @patch('sankhya_integration.services.oracle_conn.listar_pedidos_email_aguardando_parser')
    @patch('sankhya_integration.services.llm_local.extrair_pedido_de_pdf')
    def test_parser_grava_resultado_e_itens_na_tabela_auxiliar(
        self, mock_extrair, mock_listar, mock_upd, mock_ins_item,
        mock_ultimo, _ctx_p, _ctx_pr,
    ):
        mock_listar.return_value = [
            {'id': 42, 'message_id': '<x>', 'remetente': 'c@x.com',
             'pdf_path': 'p.pdf', 'pdf_texto': 'TEXTO'},
        ]
        mock_extrair.return_value = {
            'ok': True,
            'cliente': {'nome': 'ASSAI', 'codparc_sugerido': 1234, 'confianca': 0.9},
            'data_negociacao': '2026-05-01',
            'observacao': None,
            'itens': [
                {'descricao_pdf': 'A', 'codprod_sugerido': 100, 'codprod_confianca': 0.8,
                 'qtd': 5.0, 'codvol': 'KG', 'preco_unit': 1.0},
                {'descricao_pdf': 'B', 'codprod_sugerido': None, 'codprod_confianca': 0.0,
                 'qtd': 2.0, 'codvol': 'UN', 'preco_unit': None},
            ],
            'confianca_geral': 0.85,
            'modelo': 'qwen2.5:7b-instruct',
            'tokens_in': 100, 'tokens_out': 50,
            'resposta_crua': '{}',
        }

        with patch.dict('os.environ', self.env, clear=False):
            saida = self._rodar_skip_imap()

        self.assertTrue(mock_upd.called)
        argp = mock_upd.call_args[0][1]
        self.assertEqual(argp['CODPARC_SUGERIDO'], 1234)
        self.assertEqual(argp['CODEMP_SUGERIDO'], 10)  # veio do consultar_ultimo_pedido_codparc
        self.assertEqual(argp['CODTIPVENDA_SUGERIDO'], 5)
        self.assertEqual(mock_ins_item.call_count, 2)
        self.assertIn('Concluído', saida)

    @patch('sankhya_integration.management.commands.colher_pedidos_email.Command._carregar_contexto_produtos',
           return_value=[])
    @patch('sankhya_integration.management.commands.colher_pedidos_email.Command._carregar_contexto_parceiros',
           return_value=[])
    @patch('sankhya_integration.services.oracle_conn.atualizar_pedido_email_status',
           return_value={'ok': True})
    @patch('sankhya_integration.services.oracle_conn.listar_pedidos_email_aguardando_parser')
    @patch('sankhya_integration.services.llm_local.extrair_pedido_de_pdf',
           return_value={'ok': False, 'error': 'JSON inválido'})
    def test_parser_falho_marca_erro_parser(
        self, _ext, mock_listar, mock_upd_status, _ctx_p, _ctx_pr,
    ):
        mock_listar.return_value = [{
            'id': 42, 'message_id': '<x>', 'remetente': 'c@x.com',
            'pdf_path': '', 'pdf_texto': 'TEXTO',
        }]
        with patch.dict('os.environ', self.env, clear=False):
            self._rodar_skip_imap()
        self.assertTrue(mock_upd_status.called)
        chamada = mock_upd_status.call_args
        self.assertEqual(chamada[0][1], 'ERRO_PARSER')


# ===========================================================================
# E5 — EmailEndpointsTest
# Cobre endpoints HTTP do módulo (listar/detalhar/descartar/PDF/reparser).
# ===========================================================================

class EmailEndpointsTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_view_sem_sessao_redireciona_para_home(self):
        response = self.client.get(reverse('email_importar'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_view_grupo_sem_acesso_redireciona(self):
        _login_session(self.client, grupos=['8'])  # operação, não vendas
        response = self.client.get(reverse('email_importar'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    @patch('sankhya_integration.views.render')
    def test_view_grupo_vendas_renderiza(self, mock_render):
        # Mockamos render para não depender do template existir (criado em E6)
        from django.http import HttpResponse
        mock_render.return_value = HttpResponse('OK')
        _login_session(self.client, grupos=['10'])
        response = self.client.get(reverse('email_importar'))
        self.assertEqual(response.status_code, 200)
        # Confirma que render foi chamado com o template correto
        chamadas = mock_render.call_args_list
        ultimo = chamadas[-1]
        self.assertEqual(ultimo[0][1], 'sankhya_integration/email_importar.html')

    @patch('sankhya_integration.views.listar_pedidos_email_pendentes')
    def test_listar_devolve_rows(self, mock_listar):
        mock_listar.return_value = [
            {'id': 1, 'status': 'PENDENTE_REVISAO', 'remetente': 'a@x.com'},
            {'id': 2, 'status': 'PENDENTE_REVISAO', 'remetente': 'b@x.com'},
        ]
        _login_session(self.client, grupos=['10'])
        r = self.client.get(reverse('api_email_listar'))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertTrue(body['ok'])
        self.assertEqual(len(body['rows']), 2)

    @patch('sankhya_integration.views.listar_pedidos_email_pendentes', return_value=[])
    def test_listar_aceita_status_multiplo(self, mock_listar):
        _login_session(self.client, grupos=['10'])
        self.client.get(reverse('api_email_listar') + '?status=PENDENTE_REVISAO,ERRO_PARSER&dias=5')
        kwargs = mock_listar.call_args[1]
        # filtros é o primeiro arg nomeado
        filtros = kwargs.get('filtros') or mock_listar.call_args[0][0]
        self.assertEqual(filtros['status'], ['PENDENTE_REVISAO', 'ERRO_PARSER'])
        self.assertEqual(filtros['dias'], 5)

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_obter_inexistente_retorna_404(self, mock_obter):
        mock_obter.return_value = None
        _login_session(self.client, grupos=['10'])
        r = self.client.get(reverse('api_email_obter', args=[999]))
        self.assertEqual(r.status_code, 404)
        body = json.loads(r.content)
        self.assertFalse(body['ok'])

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_obter_existente_retorna_pedido_serializado(self, mock_obter):
        mock_obter.return_value = {
            'id': 42, 'status': 'PENDENTE_REVISAO',
            'recebido_em': datetime(2026, 5, 1, 10, 0),
            'criado_em': datetime(2026, 5, 1, 10, 1),
            'dtneg_sugerida': date(2026, 5, 2),
            'itens': [{'id': 1, 'criado_em': datetime(2026, 5, 1, 10, 2)}],
        }
        _login_session(self.client, grupos=['10'])
        r = self.client.get(reverse('api_email_obter', args=[42]))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertTrue(body['ok'])
        # Datas viraram string ISO
        self.assertIsInstance(body['pedido']['recebido_em'], str)
        self.assertIsInstance(body['pedido']['itens'][0]['criado_em'], str)

    @patch('sankhya_integration.views.atualizar_pedido_email_status')
    def test_descartar_grava_motivo(self, mock_upd):
        mock_upd.return_value = {'ok': True, 'rows': 1}
        _login_session(self.client, grupos=['10'])
        r = self.client.post(
            reverse('api_email_descartar', args=[42]),
            data=json.dumps({'motivo': 'PDF não é pedido, é cobrança'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        # Verificou que chamou com STATUS=DESCARTADO e o motivo
        chamada = mock_upd.call_args
        self.assertEqual(chamada[0][0], 42)
        self.assertEqual(chamada[0][1], 'DESCARTADO')
        self.assertIn('cobrança', chamada[1]['motivo_descarte'])

    @patch('sankhya_integration.views.atualizar_pedido_email_status')
    def test_descartar_sem_motivo_usa_default(self, mock_upd):
        mock_upd.return_value = {'ok': True, 'rows': 1}
        _login_session(self.client, grupos=['10'])
        r = self.client.post(reverse('api_email_descartar', args=[42]),
                              data='{}', content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Descartado', mock_upd.call_args[1]['motivo_descarte'])

    @patch('sankhya_integration.views.deletar_pedido_email_item')
    @patch('sankhya_integration.views.atualizar_pedido_email_status')
    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_reparser_remove_itens_e_volta_status(self, mock_obter, mock_upd, mock_del):
        mock_obter.return_value = {
            'id': 42, 'status': 'PENDENTE_REVISAO',
            'itens': [{'id': 100}, {'id': 101}, {'id': 102}],
        }
        mock_upd.return_value = {'ok': True, 'rows': 1}
        mock_del.return_value = {'ok': True}
        _login_session(self.client, grupos=['10'])
        r = self.client.post(reverse('api_email_reparser', args=[42]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_del.call_count, 3)
        # status voltou para AGUARDANDO_PARSER
        self.assertEqual(mock_upd.call_args[0][1], 'AGUARDANDO_PARSER')

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_reparser_em_pedido_confirmado_recusa(self, mock_obter):
        mock_obter.return_value = {
            'id': 42, 'status': 'CONFIRMADO',
            'itens': [],
        }
        _login_session(self.client, grupos=['10'])
        r = self.client.post(reverse('api_email_reparser', args=[42]))
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.content)
        self.assertIn('confirmado', body['error'].lower())

    @patch('sankhya_integration.views.atualizar_pedido_email_item')
    def test_atualizar_item_repassa_payload(self, mock_upd):
        mock_upd.return_value = {'ok': True, 'rows': 1}
        _login_session(self.client, grupos=['10'])
        r = self.client.post(
            reverse('api_email_atualizar_item', args=[7]),
            data=json.dumps({'CODPROD_FINAL': 1234, 'QTD': 10.5}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        chamada = mock_upd.call_args
        self.assertEqual(chamada[0][0], 7)
        self.assertEqual(chamada[0][1]['CODPROD_FINAL'], 1234)

    @patch('sankhya_integration.views.atualizar_pedido_email_item')
    def test_atualizar_item_body_vazio_recusa(self, _):
        _login_session(self.client, grupos=['10'])
        r = self.client.post(
            reverse('api_email_atualizar_item', args=[7]),
            data='{}', content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)

    @patch('sankhya_integration.views.deletar_pedido_email_item')
    def test_remover_item_chama_servico(self, mock_del):
        mock_del.return_value = {'ok': True, 'rows': 1}
        _login_session(self.client, grupos=['10'])
        r = self.client.post(reverse('api_email_remover_item', args=[7]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_del.call_args[0][0], 7)

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_pdf_inexistente_retorna_404(self, mock_obter):
        mock_obter.return_value = None
        _login_session(self.client, grupos=['10'])
        r = self.client.get(reverse('api_email_pdf', args=[999]))
        self.assertEqual(r.status_code, 404)

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_pdf_path_fora_do_diretorio_recusa(self, mock_obter):
        # Tenta servir arquivo de fora do PEDIDO_EMAIL_PDF_DIR (path traversal)
        import tempfile, os as _os
        tmp = tempfile.mkdtemp()
        outside = _os.path.join(tempfile.gettempdir(), 'fora.pdf')
        with open(outside, 'wb') as f: f.write(b'%PDF-1.4 fake')
        mock_obter.return_value = {'id': 42, 'pdf_path': outside}
        _login_session(self.client, grupos=['10'])
        with patch.dict('os.environ', {'PEDIDO_EMAIL_PDF_DIR': tmp}, clear=False):
            r = self.client.get(reverse('api_email_pdf', args=[42]))
        self.assertEqual(r.status_code, 403)

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    def test_pdf_existente_dentro_do_dir_serve_bytes(self, mock_obter):
        import tempfile, os as _os
        tmp = tempfile.mkdtemp()
        sub = _os.path.join(tmp, '2026', '05')
        _os.makedirs(sub, exist_ok=True)
        pdf_path = _os.path.join(sub, 'test.pdf')
        with open(pdf_path, 'wb') as f: f.write(b'%PDF-1.4 conteudo')
        mock_obter.return_value = {'id': 42, 'pdf_path': pdf_path}
        _login_session(self.client, grupos=['10'])
        with patch.dict('os.environ', {'PEDIDO_EMAIL_PDF_DIR': tmp}, clear=False):
            r = self.client.get(reverse('api_email_pdf', args=[42]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn(b'PDF-1.4', r.content)


# ===========================================================================
# E7 — ConfirmarPedidoEmailTest
# Cobre o endpoint que promove o pré-pedido para TGFCAB TOP 34 reusando as
# APIs já testadas da Venda. Sem mexer em nenhuma query existente.
# ===========================================================================

class ConfirmarPedidoEmailTest(TestCase):

    def setUp(self):
        self.client = Client()
        _login_session(self.client, grupos=['10'], codusu=99)

    def _payload_valido(self):
        return {
            'codparc': 1234, 'codemp': 10, 'codtipvenda': 5,
            'dtneg': '01/05/2026', 'observacao': 'Pedido de tomate',
        }

    def _pedido_pronto(self):
        return {
            'id': 42, 'status': 'PENDENTE_REVISAO',
            'itens': [
                {'id': 1, 'codprod_final': 100, 'qtd': 10, 'codvol': 'CX', 'preco_unit': 5.0,
                 'descricao_pdf': 'TOMATE'},
                {'id': 2, 'codprod_final': 200, 'qtd': 5, 'codvol': 'KG', 'preco_unit': 3.0,
                 'descricao_pdf': 'BANANA'},
            ],
        }

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=False)
    def test_escrita_desabilitada_retorna_403(self, _):
        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 403)

    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_payload_incompleto_recusa(self, _):
        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps({'codparc': 1234}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)

    @patch('sankhya_integration.views.obter_pedido_email_completo', return_value=None)
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_pre_pedido_inexistente_retorna_404(self, _, __):
        r = self.client.post(reverse('api_email_confirmar', args=[999]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 404)

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_pre_pedido_ja_confirmado_recusa(self, _, mock_obter):
        mock_obter.return_value = {'id': 42, 'status': 'CONFIRMADO', 'itens': []}
        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.content)
        self.assertIn('confirmado', body['error'].lower())

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_pre_pedido_descartado_recusa(self, _, mock_obter):
        mock_obter.return_value = {'id': 42, 'status': 'DESCARTADO', 'itens': []}
        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_pre_pedido_sem_itens_recusa(self, _, mock_obter):
        mock_obter.return_value = {'id': 42, 'status': 'PENDENTE_REVISAO', 'itens': []}
        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.content)
        self.assertIn('sem itens', body['error'].lower())

    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_item_sem_codprod_final_recusa(self, _, mock_obter):
        mock_obter.return_value = {
            'id': 42, 'status': 'PENDENTE_REVISAO',
            'itens': [
                {'id': 1, 'codprod_final': 100, 'qtd': 10, 'codvol': 'CX', 'preco_unit': 5.0},
                {'id': 2, 'codprod_final': None, 'qtd': 5, 'codvol': 'KG', 'preco_unit': 3.0},
            ],
        }
        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.content)
        self.assertIn('CODPROD', body['error'])

    @patch('sankhya_integration.views.vincular_nunota_pedido_email', return_value={'ok': True})
    @patch('sankhya_integration.views.recalcular_totais_nota_banco', return_value={'ok': True})
    @patch('sankhya_integration.views.inserir_item_nota_banco')
    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco')
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_fluxo_feliz_cria_pedido_e_marca_confirmado(
        self, _, mock_obter, mock_conn, mock_ins_cab, mock_ins_it,
        _mock_recalc, mock_vincular,
    ):
        # Setup do contexto Oracle
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        mock_conn.return_value.__exit__.return_value = None

        mock_obter.return_value = self._pedido_pronto()
        mock_ins_cab.return_value = {'executed': True, 'nunota': 555}
        mock_ins_it.return_value  = {'executed': True, 'sequencia': 1}

        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertTrue(body['ok'])
        self.assertEqual(body['nunota'], 555)
        # Cabeçalho criado com TOP 34
        self.assertEqual(mock_ins_cab.call_args[0][0]['CODTIPOPER'], 34)
        # 2 itens inseridos
        self.assertEqual(mock_ins_it.call_count, 2)
        # vincular foi chamado com NUNOTA + CODUSU da sessão (99)
        self.assertEqual(mock_vincular.call_args[1]['nunota'], 555)
        self.assertEqual(mock_vincular.call_args[1]['codusu'], 99)
        conn.commit.assert_called_once()

    @patch('sankhya_integration.views.vincular_nunota_pedido_email', return_value={'ok': True})
    @patch('sankhya_integration.views.recalcular_totais_nota_banco', return_value={'ok': True})
    @patch('sankhya_integration.views.inserir_item_nota_banco',
           return_value={'executed': False, 'error': 'CODPROD inválido'})
    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco',
           return_value={'executed': True, 'nunota': 555})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_falha_inserindo_item_faz_rollback_e_nao_confirma(
        self, _, mock_obter, mock_conn, _ins_cab, _ins_it, _recalc, mock_vincular,
    ):
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        mock_conn.return_value.__exit__.return_value = None
        mock_obter.return_value = self._pedido_pronto()

        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        # rollback foi chamado, vincular NÃO
        conn.rollback.assert_called()
        self.assertFalse(mock_vincular.called)

    @patch('sankhya_integration.views.inserir_cabecalho_nota_banco',
           return_value={'executed': False, 'error': 'CODNAT inválido'})
    @patch('sankhya_integration.views.obter_conexao_oracle')
    @patch('sankhya_integration.views.obter_pedido_email_completo')
    @patch('sankhya_integration.views.verificar_permissao_escrita', return_value=True)
    def test_falha_inserindo_cabecalho_retorna_400(
        self, _, mock_obter, mock_conn, _ins_cab,
    ):
        conn = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        mock_conn.return_value.__exit__.return_value = None
        mock_obter.return_value = self._pedido_pronto()

        r = self.client.post(reverse('api_email_confirmar', args=[42]),
                             data=json.dumps(self._payload_valido()),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.content)
        self.assertFalse(body['ok'])
        conn.rollback.assert_called()
