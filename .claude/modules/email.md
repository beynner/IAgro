# Módulo Importação por E-mail (Pedidos via PDF + LLM local)

Coleta automática de pedidos de venda recebidos por e-mail com PDF anexo. Worker IMAP baixa PDFs, extrai texto via `pdfplumber`, parser LLM local (Ollama + Qwen 2.5 14B) extrai dados estruturados e tela de revisão permite ao operador confirmar e promover para TGFCAB (TOP 34).

**Estado atual (Mai/2026):**
- DDL aplicada no Oracle (Sankhya) ✅
- Pastas criadas no Titan: `Pedidos-Entrada`, `Pedidos-Processados`, `Pedidos-Erros` ✅
- Conta IMAP configurada: `comercial@agromilagrocomercial.com.br`
- Modelo padrão **subido de 7B para 14B** após confirmar capacidade do servidor de produção (Xeon E5-2680 v4 + 64GB RAM) ✅
- Ollama 0.23.0 instalado no servidor (`C:\Users\ANDRE\AppData\Local\Programs\Ollama\`) ✅
- `qwen2.5:14b-instruct` baixado e testado (resposta "pronto" validada) ✅
- Cenário A confirmado: Django + Ollama no mesmo servidor → `OLLAMA_HOST=http://localhost:11434` ✅
- Pendente do operador: criar venv no servidor + `pip install -r requirements.txt`, preencher `EMAIL_IMAP_PASS` no `.env`, agendar Task Scheduler.

---

## Premissa Arquitetural

**Pré-pedidos vivem em tabelas auxiliares Oracle (`AD_PEDIDO_EMAIL_RECEBIDO` + `AD_PEDIDO_EMAIL_ITEM`)** até o momento em que o operador clica "Confirmar". Apenas a confirmação humana grava em TGFCAB/TGFITE — **reusando as APIs já testadas da Venda** (`api_criar_cabecalho_venda` + `api_salvar_item_venda`).

Resultado:
- ERP Sankhya fica limpo: rascunhos não vazam para painéis/cubos do Sankhya.
- Zero alteração em queries existentes de TGFCAB/TGFITE.
- Trigger `TRG_INC_TGFCAB` não é desafiado (INSERT vai pelo caminho normal já validado).
- Privacidade: dados de cliente nunca saem para serviços externos (LLM roda local).

---

## Escopo

- Coletar PDFs de pedidos via IMAP (Titan/Hostinger).
- Arquivar PDF original em disco e texto extraído em CLOB Oracle.
- Extrair via LLM local: cliente sugerido (CODPARC), data, tipo de negociação, itens (descrição, qtd, preço, CODPROD sugerido).
- Tela de revisão: operador edita campos, ajusta itens, confirma ou descarta.
- Confirmação chama APIs existentes da Venda → TGFCAB recebe pedido TOP 34 normalmente.
- Audit: `CONFIRMADO_POR` guarda CODUSU do operador; `NUNOTA_GERADO` faz link reverso para TGFCAB.

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/venda/email-importar/` | GET | Página HTML da fila de revisão |
| `/sankhya/venda/api/email/listar/` | GET | Lista pré-pedidos por status |
| `/sankhya/venda/api/email/<id>/` | GET | Detalhes (cabeçalho + itens + sugestões) |
| `/sankhya/venda/api/email/<id>/pdf/` | GET | Serve o PDF autenticado |
| `/sankhya/venda/api/email/<id>/confirmar/` | POST | Promove para TGFCAB TOP 34 |
| `/sankhya/venda/api/email/<id>/descartar/` | POST | Marca DESCARTADO + motivo |
| `/sankhya/venda/api/email/<id>/reparser/` | POST | Re-roda LLM (debug) |

**Acesso:** Grupos `1`, `6`, `10` (decorator `@exige_grupo('venda')`).

**Endpoints adicionais (E5+E7) — não estavam no esboço inicial:**

| Rota | Método | Função |
|---|---|---|
| `/sankhya/venda/api/email/<id>/confirmar/` | POST | Promove para TGFCAB TOP 34 |
| `/sankhya/venda/api/email/item/<id>/editar/` | POST | Edita item inline na revisão |
| `/sankhya/venda/api/email/item/<id>/remover/` | POST | Remove item do pré-pedido |

---

## Tabelas auxiliares (DDL versionada)

DDL em `sankhya_integration/sql/AD_PEDIDO_EMAIL.sql`. Mesmo padrão da view do WMS (`ANDRE_IAGRO_SALDO_LOTE.sql`).

### `AD_PEDIDO_EMAIL_RECEBIDO`

Um registro por e-mail processado. Anti-duplicação por `MESSAGE_ID` UNIQUE.

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_PEDIDO_EMAIL_RECEBIDO` |
| `MESSAGE_ID` | VARCHAR2(255) UNIQUE | Header do e-mail |
| `REMETENTE` | VARCHAR2(120) | E-mail do remetente |
| `ASSUNTO` | VARCHAR2(255) | Subject |
| `RECEBIDO_EM` | TIMESTAMP | Header Date |
| `PROCESSADO_EM` | TIMESTAMP | Worker timestamp |
| `PDF_PATH` | VARCHAR2(500) | Caminho absoluto no disco |
| `PDF_TEXTO` | CLOB | Texto extraído via pdfplumber |
| `LLM_RESPOSTA` | CLOB | JSON cru do LLM (auditoria) |
| `LLM_MODELO` | VARCHAR2(50) | Ex: `qwen2.5:14b-instruct` |
| `LLM_TOKENS_IN/OUT` | NUMBER | Telemetria |
| `LLM_CONFIANCA_GERAL` | NUMBER(3,2) | 0.00–1.00 |
| `CODPARC_SUGERIDO` | NUMBER | Best guess |
| `CODEMP_SUGERIDO` | NUMBER | Deduzida do último pedido do CODPARC |
| `CODTIPVENDA_SUGERIDO` | NUMBER | Último tipo do CODPARC |
| `DTNEG_SUGERIDA` | DATE | Best guess |
| `OBSERVACAO_EXTRAIDA` | VARCHAR2(2000) | Observação livre do PDF |
| `STATUS` | VARCHAR2(30) | Ver estados abaixo |
| `MOTIVO_DESCARTE` | VARCHAR2(500) | Quando STATUS=DESCARTADO |
| `NUNOTA_GERADO` | NUMBER | TGFCAB.NUNOTA após CONFIRMADO |
| `CONFIRMADO_POR` | NUMBER | CODUSU do operador |
| `CONFIRMADO_EM` | TIMESTAMP | — |
| `CRIADO_EM` | TIMESTAMP | DEFAULT SYSTIMESTAMP |

### Estados (coluna STATUS)

| Status | Significado |
|---|---|
| `AGUARDANDO_PARSER` | E-mail recebido, PDF salvo, ainda não passou pelo LLM |
| `PENDENTE_REVISAO` | Parser concluído; aguarda operador na fila |
| `CONFIRMADO` | Operador confirmou; `NUNOTA_GERADO` populado |
| `DESCARTADO` | Operador rejeitou (ver `MOTIVO_DESCARTE`) |
| `ERRO_PARSER` | LLM falhou (timeout, JSON inválido) — passível de reparser |
| `ERRO_PDF` | PDF corrompido / sem texto / escaneado sem OCR |

### `AD_PEDIDO_EMAIL_ITEM`

Um registro por linha extraída do PDF. Operador pode editar/remover/adicionar.

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_PEDIDO_EMAIL_ITEM` |
| `RECEBIDO_ID` | NUMBER FK | → `AD_PEDIDO_EMAIL_RECEBIDO.ID` (ON DELETE CASCADE) |
| `SEQUENCIA` | NUMBER | Ordem do item no PDF |
| `DESCRICAO_PDF` | VARCHAR2(500) | Texto original |
| `CODPROD_SUGERIDO` | NUMBER | Inferido pelo LLM |
| `CODPROD_CONFIANCA` | NUMBER(3,2) | 0.00–1.00 |
| `CODPROD_FINAL` | NUMBER | Após operador confirmar |
| `QTD` | NUMBER(15,3) | — |
| `CODVOL` | VARCHAR2(10) | UN/KG/CX |
| `PRECO_UNIT` | NUMBER(15,4) | Pode ser NULL |
| `OBSERVACAO` | VARCHAR2(500) | — |
| `CRIADO_EM` | TIMESTAMP | DEFAULT SYSTIMESTAMP |

---

## Fluxo do worker IMAP

Management command: `python manage.py colher_pedidos_email`. Agendado via Windows Task Scheduler a cada **30 minutos** (volume típico: 5 PDFs/dia).

```
1. Conecta IMAP Titan via imap-tools
2. Lista UNSEEN em pasta EMAIL_IMAP_FOLDER_ENTRADA
3. Para cada e-mail:
   a. Verifica MESSAGE_ID em AD_PEDIDO_EMAIL_RECEBIDO (anti-duplicação)
   b. Baixa anexo PDF, salva em PEDIDO_EMAIL_PDF_DIR/AAAA/MM/<MSGID>.pdf
   c. Extrai texto com pdfplumber → string
   d. Sem PDF / sem texto → STATUS=ERRO_PDF, move e-mail para Pedidos/Erros
   e. INSERT AD_PEDIDO_EMAIL_RECEBIDO com STATUS=AGUARDANDO_PARSER
   f. Marca e-mail como lido / move para Pedidos/Processados
4. Segunda fase: lista registros AGUARDANDO_PARSER e chama parser LLM
5. Para cada um:
   a. Monta prompt com texto + lista enxuta de parceiros/produtos
   b. Chama Ollama (timeout 120s, 3 retries)
   c. Valida JSON do retorno
   d. INSERT em AD_PEDIDO_EMAIL_ITEM (uma linha por item)
   e. UPDATE STATUS=PENDENTE_REVISAO
   f. Falha → STATUS=ERRO_PARSER (passível de reparser manual via endpoint)
```

---

## Parser LLM (Ollama local)

Módulo: `sankhya_integration/services/llm_local.py`

Modelo padrão: `qwen2.5:14b-instruct` (~8.5 GB, roda em CPU). Tempo médio por PDF: 40-80s no servidor de produção (Xeon E5-2680 v4 + 64GB RAM).

> **Histórico:** Mai/2026 subimos de 7B → 14B após confirmar que o servidor comporta com folga. Acurácia esperada subiu de ~75-85% para ~82-90%, com custo de tempo irrelevante no volume típico (5 PDFs/dia × 80s ≈ 7 min/dia).

**Experimentação com 32B** sem trocar o default: rodar `ollama pull qwen2.5:32b-instruct` no servidor e setar `OLLAMA_MODELO=qwen2.5:32b-instruct` no `.env` temporariamente (também subir `OLLAMA_TIMEOUT_SEGUNDOS=300`). Voltar para 14B após o teste. Ganho esperado de acurácia é ~3-5%, custo de tempo é ~3x.

Prompt fixo em português pede JSON estruturado:

```json
{
  "cliente": {"nome": "...", "codparc_sugerido": 123, "confianca": 0.92},
  "data_negociacao": "YYYY-MM-DD",
  "observacao": "...",
  "itens": [
    {
      "descricao_pdf": "...",
      "codprod_sugerido": 456,
      "codprod_confianca": 0.85,
      "qtd": 10.5,
      "codvol": "KG",
      "preco_unit": 5.50
    }
  ],
  "confianca_geral": 0.88
}
```

Contexto enriquecido no prompt (top 50 parceiros mais ativos, produtos do remetente histórico ou top 100 globais) — força LLM a sugerir IDs reais em vez de inventar.

**Privacidade:** dados nunca saem da máquina. Conexão é só `http://localhost:11434`.

---

## Tela de revisão (frontend)

Layout 2 colunas:
- **Coluna esquerda:** lista da fila (`PENDENTE_REVISAO`) ordenada por `RECEBIDO_EM`. Indicadores visuais: confiança geral (◐XX%), nº de itens, alerta de campos ausentes.
- **Coluna direita:** detalhe do pré-pedido selecionado.
  - PDF original embutido em `<iframe>`.
  - Form de cabeçalho com sugestões editáveis (typeaheads de parceiro/empresa/tipo já existentes).
  - Tabela de itens com edição inline (typeahead de produto reusado de `cab_prod_*`).
  - Botões `Descartar` / `Confirmar e criar pedido`.

Convenções visuais:
- ◐XX% = confiança geral (vermelho < 50%, laranja 50-80%, verde > 80%)
- Badge laranja `Sugerido — confirme` em campos com confiança baixa
- ⚠ inline em itens sem CODPROD mapeado

---

## Confirmação — promoção para TGFCAB

Endpoint `POST /sankhya/venda/api/email/<id>/confirmar/`:

1. Validações: pré-pedido existe, STATUS=PENDENTE_REVISAO, todos os itens têm CODPROD_FINAL, CODPARC válido.
2. Atomicidade: dentro de `with obter_conexao_oracle() as conn`.
3. Chama `inserir_cabecalho_nota_banco(..., CODTIPOPER=34, conexao_existente=conn)` — workaround DPY-1001 padrão.
4. Para cada item: `inserir_item_nota_banco(...)` com NUNOTA gerado.
5. `recalcular_totais_nota_banco`.
6. UPDATE em AD_PEDIDO_EMAIL_RECEBIDO: `STATUS='CONFIRMADO'`, `NUNOTA_GERADO=<NUNOTA>`, `CONFIRMADO_POR=<codusu da sessão>`, `CONFIRMADO_EM=SYSTIMESTAMP`.
7. `conn.commit()`.

**100% das funções existentes da Venda permanecem intocadas.**

---

## Configuração `.env`

```dotenv
# IMAP Titan (conta Agromil)
EMAIL_IMAP_HOST=imap.titan.email
EMAIL_IMAP_PORT=993
EMAIL_IMAP_USER=comercial@agromilagrocomercial.com.br
EMAIL_IMAP_PASS=<senha de app gerada no painel Hostinger>
# Pastas com hífen (não barra) — Titan trata como nome literal
EMAIL_IMAP_FOLDER_ENTRADA=Pedidos-Entrada
EMAIL_IMAP_FOLDER_PROCESSADOS=Pedidos-Processados
EMAIL_IMAP_FOLDER_ERROS=Pedidos-Erros

# LLM (Mai/2026: padrão 14B; ver bloco em llm_local.py)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODELO=qwen2.5:14b-instruct
OLLAMA_TIMEOUT_SEGUNDOS=120
OLLAMA_MAX_RETRIES=3
# Para experimentar 32B sem trocar default:
#   OLLAMA_MODELO=qwen2.5:32b-instruct + OLLAMA_TIMEOUT_SEGUNDOS=300

# Storage
PEDIDO_EMAIL_PDF_DIR=z:\TI\NexusGTi\IAgro\IAgro\media\pedidos_email
```

---

## Decisões de regra de negócio

1. **Pré-pedido fica em tabela auxiliar Oracle, não em SQLite nem em TGFCAB com TOP novo.** Razão: backup unificado, joinable com TGFCAB via NUNOTA_GERADO, mas sem poluir queries existentes.
2. **TGFCAB recebe INSERT só após confirmação humana.** Razão: rascunhos de parser não viram ruído em painéis Sankhya de outros operadores.
3. **CODUSU em TGFCAB = quem clicou Confirmar**, não o "usuário do worker". Audit fica natural.
4. **CODEMP é deduzida do último pedido do CODPARC**, não fixada em 10. Operador pode trocar.
5. **CODTIPVENDA = último do CODPARC**, com badge laranja "Confirme — sugerido pelo histórico" até operador validar.
6. **Atrasados na fila ficam esperando indefinidamente** — sem job de alerta SMTP. Operador tem hábito de olhar a tela.
7. **Aprendizado de mapeamentos (`AD_EMAIL_PARCEIRO_MAP`, `AD_PRODUTO_ALIAS`) fica para v2.** MVP entra sem isso; LLM começa do zero a cada PDF (com contexto de parceiros/produtos no prompt).
8. **PDF original mora em disco, não em BLOB.** Caminho absoluto em `PDF_PATH`. Disco backupeado pelo backup geral do servidor.
9. **OCR não está incluído.** Se PDF for escaneado e pdfplumber não conseguir extrair texto, registro vai para `ERRO_PDF` e operador trata manualmente. OCR (Tesseract) pode ser adicionado em v2 se aparecer demanda.

---

## Frontend — arquivos

- **Template:** `email_importar.html`
- **CSS:** `email_importar.css`
- **JS:** `email_importar.js`
- **Helpers reusados:** `IAgro.postJSON`, `IAgro.confirmarAcao`, typeaheads existentes (`attachTA` de `venda.js`)

---

## Setup operacional (executar uma vez)

1. **Aplicar DDL no Oracle:** executar `sankhya_integration/sql/AD_PEDIDO_EMAIL.sql` no Sankhya. **✅ Concluído Mai/2026.**
2. **Criar pastas IMAP no Titan webmail:** `Pedidos-Entrada`, `Pedidos-Processados`, `Pedidos-Erros` (hífens, não barras). **✅ Concluído Mai/2026.**
3. **Instalar Ollama no servidor de produção** (Xeon E5-2680 v4 + 64GB RAM): `https://ollama.com/download/windows` → executar instalador. **✅ Concluído Mai/2026 (versão 0.23.0).**
4. **Baixar modelo padrão:** `ollama pull qwen2.5:14b-instruct` (~8.5 GB, uma vez). **✅ Concluído Mai/2026.**
4b. **Baixar modelo experimental opcional:** `ollama pull qwen2.5:32b-instruct` (~20 GB) — para testes A/B futuros sem trocar default. *(opcional, ainda não baixado)*
5. **Instalar dependências Python:** `pip install -r requirements.txt`.
6. **Preencher `.env`** com credenciais IMAP do Titan (senha de app, não a do e-mail). *(pendente)*
7. **Agendar worker no Windows Task Scheduler:** comando `python manage.py colher_pedidos_email` a cada 30 min. *(pendente)*

**Filtro automático no Titan:** ainda não criado. Operador move e-mails manualmente da Caixa de Entrada para `Pedidos-Entrada`. Decisão tática — começar simples, calibrar regra depois de algumas semanas de uso real.

---

## Pendências (v2)

- **OCR (Tesseract)** para PDFs escaneados.
- **Tabelas de aprendizado** (`AD_EMAIL_PARCEIRO_MAP` por domínio, `AD_PRODUTO_ALIAS` por descrição).
- **Métricas de acurácia do LLM** (% de campos confirmados sem alteração).
- **Re-treino/fine-tuning** de prompt baseado em feedback acumulado.
- **Alerta passivo de fila atrasada** (contador no header da tela).

---

## Testes

Adicionados em `test_views_email_pedidos.py` (cobertura ~40 testes):

| Classe | Cobertura |
|---|---|
| `OracleAdapterEmailTest` | Funções aditivas em `oracle_conn.py` |
| `WorkerImapTest` | Coleta IMAP com mock |
| `ParserLLMTest` | Cliente Ollama com mock |
| `EmailEndpointsTest` | Listar/detalhar/serve PDF/descartar/reparser |
| `ConfirmarPedidoEmailTest` | Promoção para TGFCAB via APIs existentes |
