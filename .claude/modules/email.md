# Módulo Importação por E-mail (Pedidos via PDF + LLM local)

Coleta automática de pedidos de venda recebidos por e-mail com PDF anexo OU paste manual de texto livre (WhatsApp). Worker IMAP baixa PDFs, extrai texto via `pdfplumber`, **divide o PDF físico em N arquivos quando traz múltiplos pedidos** (1 sub-arquivo por loja), chama LLM local (Ollama + Qwen 2.5 14B) **apenas para extrair texto literal** — sem injetar listas de IDs. A resolução de CODPARC/CODPROD acontece em Python via matching híbrido em 3 níveis (cod_cliente → alias por descrição → fuzzy). A tela de revisão permite ao operador conferir, corrigir e promover para TGFCAB (TOP 34); cada confirmação alimenta tabelas de aprendizado que progressivamente reduzem trabalho manual.

**Estado atual (Mai/2026 — pós-Fase 1/2/3 + cod_cliente + UX + Etapa 0 regex):**
- DDL aplicada no Oracle (todas as 5 migrations: principal, SUB_ID, alias, ORIGEM, cod_cliente) ✅
- Pastas criadas no Titan: `Pedidos-Entrada`, `Pedidos-Processados`, `Pedidos-Erros` ✅
- Conta IMAP configurada: `comercial@agromilagrocomercial.com.br` (Hostgator/Titan) — exige toggle "Acesso a e-mail de terceiros" ativado no painel ✅
- Modelo padrão `qwen2.5:14b-instruct` rodando em CPU no servidor (Xeon E5-2680 v4 + 64GB RAM) ✅
- Ollama instalado no servidor, `OLLAMA_HOST=http://localhost:11434` ✅
- Pipeline funcional ponta-a-ponta: testado com PDF Consinco/Assaí de 3 lojas → gerou 3 pré-pedidos × 14/13/15 itens, qtd/preço corretos, ~88-95% de matching automático correto ✅
- Performance LLM: ~3 min por pedido (CPU, Qwen 14B). Variabilidade ocasional → timeouts intermitentes em prod (vide gargalo abaixo) ⚠
- Split físico do PDF: cada SUB_ID tem seu próprio arquivo `<MSGID>_sub{N}.pdf` ✅
- Layouts plugáveis: `CONSINCO_RELPED` (com prompt específico Consinco) ou `GENERICO` (fallback neutro) ✅
- Paste manual de texto livre (WhatsApp / e-mail / qualquer): botão `📋 Importar texto` no header da fila ✅
- Vinculação por código do cliente (`AD_CLIENTE_PRODUTO_COD`): após 1ª confirmação, próximos pedidos do mesmo cliente batem CODPROD direto com confiança 100% ✅
- Defesa em camadas contra duplicação: worker faz DELETE defensivo antes de INSERT ✅
- Schema-resilient: `_existe_coluna()` cache 1× por processo permite código rodar antes/depois das migrations ✅
- **Etapa 0 (parser regex Consinco) implementada com fallback LLM transparente** — `services/pdf_parsers/{__init__.py, consinco.py}`. Validações cruzadas: `Total de itens declarado == len(itens)` + `|Σ valor − Total geral PDF| ≤ R$ 0,10`. ~50ms vs ~3min do LLM nos PDFs Consinco. ✅
- **Telemetria visual**: badge `⚡ Regex` / `🧠 LLM` no header do detalhe + linha "PDF (referência)" no `<tfoot>` com chip ✓/⚠ comparando totais calculados vs declarados no PDF. Aparece mesmo em registros parseados via LLM (regex de totais roda no GET). ✅
- ⚠ **Em testes em produção** — Fases A/B/C concluídas. Aguardando 1 semana de uso real antes de novas iterações ou de revisitar a decisão local-vs-cloud (ver seção dedicada).
- Pendente: agendar Task Scheduler (`python manage.py colher_pedidos_email` a cada 30 min).

**Gargalo conhecido (mitigado):** LLM em CPU = ~3 min/pedido. Endereçado pela Etapa 0 regex (Mai/2026) que cobre os ~80% de PDFs Consinco em ~50ms; LLM continua disparando para paste manual e layouts desconhecidos. Outra alavanca futura é trocar Ollama por cloud (Anthropic API) — análise completa registrada em "Decisão pendente registrada: migração LLM local → cloud" abaixo.

---

## Premissa Arquitetural

**Pré-pedidos vivem em tabelas auxiliares Oracle** (`AD_PEDIDO_EMAIL_RECEBIDO` + `AD_PEDIDO_EMAIL_ITEM`) até o momento em que o operador clica "Confirmar". Apenas a confirmação humana grava em TGFCAB/TGFITE — **reusando as APIs já testadas da Venda** (`api_criar_cabecalho_venda` + `api_salvar_item_venda`).

**Multi-pedido por PDF + Split físico:** um e-mail pode trazer N pedidos no mesmo PDF (típico de redes de supermercado: 1 PDF, 1 loja por página). O worker divide as **páginas** do PDF (não só o texto) e cria:
- **N linhas em `AD_PEDIDO_EMAIL_RECEBIDO`** com mesmo `MESSAGE_ID` e `SUB_ID` sequencial (1, 2, 3, ...)
- **N arquivos físicos** `<MSGID>_sub{N}.pdf` (cada um com apenas suas páginas) via `pypdf`
- PDF original preservado em `<MSGID>.pdf` (arquivamento)

Operador na revisão vê só o sub-PDF do pedido específico no iframe — não mais scroll pelo arquivão completo. PDFs com 1 pedido só (caso comum) NÃO criam sub-arquivo: PDF_PATH continua apontando pro original.

**Layouts plugáveis (`detectar_layout`):** worker identifica padrão pelo conteúdo. Hoje suporta:
- `CONSINCO_RELPED`: PDFs Assaí/SENDAS — prompt LLM com avisos específicos (FORNECEDOR≠CLIENTE, ignorar coluna Emb=1, layout das colunas Emb/Qtde/Valor) + few-shot exemplo real Consinco
- `GENERICO`: fallback neutro pra texto livre, novos fornecedores, paste de WhatsApp — extrai cliente/data/itens sem dicas específicas (operador corrige na revisão; alias acelera próximas)

Adicionar layout novo = 1 entrada em `_HEADERS_POR_LAYOUT` (regex) + 1 entrada em `PROMPTS_POR_LAYOUT` (par sistema/usuário do prompt).

**Extração híbrida (LLM + matching determinístico):**
- O LLM **não recebe** lista de parceiros/produtos no prompt — evita alucinação por contaminação de contexto.
- O LLM extrai apenas dados textuais do PDF: `cliente_nome`, `data_negociacao`, `observacao`, e por item `cod_cliente` (Consinco), `descricao_pdf`, `qtd`, `codvol`, `preco_unit`.
- Resolução de `CODPARC` e `CODPROD` acontece em Python via [`services.matching.py`](../../sankhya_integration/services/matching.py) — alias + fuzzy contra TGFPAR/TGFPRO.

**Matching híbrido em 3 níveis (do mais forte ao mais fraco):**
1. **Etapa 0 — Vinculação por código do cliente** (`AD_CLIENTE_PRODUTO_COD`): chave `(CODPARC, COD_CLIENTE)` → CODPROD com confiança 100. Estável (cliente raramente muda código interno) e o método mais forte. Aplicável quando o LLM extraiu `cod_cliente` (típico em PDFs Consinco que têm coluna "Cod Forn").
2. **Etapa 1 — Alias por descrição** (`AD_PRODUTO_ALIAS`): chave `(descricao_normalizada, codparc?)` → CODPROD. `codparc` opcional permite alias scope-specific (Cliente A chama "PIMENTAO VERDE" o EXTRA, Cliente B o MEDIO).
3. **Etapa 2 — Fuzzy contra TGFPRO** (`rapidfuzz.fuzz.WRatio`): score >= 75 vira sugestão; senão operador escolhe na tela.

Mesmo princípio para CODPARC: alias por nome → fuzzy contra TGFPAR. Não há "Etapa 0" pra CODPARC porque clientes não mandam código de si próprios (mas é uma extensão futura possível).

**Aprendizado por confirmação humana (não é ML):**
- 3 tabelas guardam decisões: `AD_PRODUTO_ALIAS`, `AD_PARCEIRO_ALIAS`, `AD_CLIENTE_PRODUTO_COD`.
- Match exato em string normalizada / códigos numéricos — sem treinamento, sem inferência. Cache de atalhos, auditável (DELETE de uma linha reverte).
- Aprendizado SÓ acontece no clique de "Confirmar e criar pedido" — confirmação humana = aval de qualidade.
- **Curva esperada:** primeiro pedido de um cliente novo é manual; 2º já vem casado pra parceiro; pelo 3º-5º os itens recorrentes vão automáticos. Após 1 mês, fila típica de Consinco/Assaí passa quase sem revisão manual.

**Múltiplas origens (`ORIGEM`):**
- `IMAP` (default): worker pegou de e-mail. PDF físico salvo, texto extraído, layout detectado.
- `TEXTO_LIVRE`: operador colou texto direto na tela (botão 📋 Importar texto). Sem PDF — frontend mostra `<pre>` em vez de iframe. Worker pula extração (texto já está em `PDF_TEXTO`), só roda LLM com layout `GENERICO`.
- `WHATSAPP_API`: reservado para integração futura via WhatsApp Business API.

**Defesa em camadas contra duplicação de itens:**
1. `api_email_reparser` faz batch DELETE pelo `RECEBIDO_ID` (1 query atômica) antes de mudar STATUS pra AGUARDANDO_PARSER.
2. **Worker LLM** faz DELETE defensivo no início do processamento de cada registro — garantia que mesmo se a camada 1 falhar (race condition, erro silencioso), nenhum INSERT vai por cima de itens existentes.

Sem essas defesas, qualquer descompasso entre Reparser/Restaurar/Worker pode duplicar (já aconteceu — vide gotchas).

Resultado consolidado:
- ERP Sankhya fica limpo: rascunhos não vazam para painéis/cubos do Sankhya.
- Zero alteração em queries existentes de TGFCAB/TGFITE.
- Trigger `TRG_INC_TGFCAB` não é desafiado (INSERT vai pelo caminho normal já validado).
- Privacidade: dados de cliente nunca saem do servidor (LLM roda local).
- LLM continua sendo a **única peça AI** — matching e alias são determinísticos.

---

## Escopo

- Coletar PDFs de pedidos via IMAP (Titan/Hostgator).
- Arquivar PDF original em disco e texto extraído em CLOB Oracle.
- **Dividir** texto em N pedidos quando o PDF tem múltiplos (1 cliente, várias lojas).
- Chamar LLM local **apenas para extração textual literal** (sem inferência de IDs).
- Casar `cliente_nome` → `CODPARC` e `descricao_pdf` → `CODPROD` em Python (alias + fuzzy).
- Tela de revisão: operador edita campos, ajusta itens, confirma ou descarta. Suporta restauração granular (1 item ou todos) sem nova chamada LLM.
- Confirmação chama APIs existentes da Venda → TGFCAB recebe pedido TOP 34 normalmente; alias gravados em `AD_*_ALIAS`.
- Audit: `CONFIRMADO_POR` guarda CODUSU do operador; `NUNOTA_GERADO` faz link reverso para TGFCAB.

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/venda/email-importar/` | GET | Página HTML da fila de revisão |
| `/sankhya/venda/api/email/listar/` | GET | Lista pré-pedidos por status. Ordenação: `RECEBIDO_EM DESC, SUB_ID ASC, ID ASC` (e-mails recentes no topo, pgs do PDF na ordem certa dentro do mesmo e-mail) |
| `/sankhya/venda/api/email/importar-texto/` | POST | Paste manual de texto livre (WhatsApp/e-mail). Cria registro com `PDF_PATH=NULL` + `STATUS=AGUARDANDO_PARSER` + `ORIGEM='TEXTO_LIVRE'`. Validação: texto ≥30 chars |
| `/sankhya/venda/api/email/<id>/` | GET | Detalhes (cabeçalho + itens; LEFT JOIN traz nome canônico TGFPAR/TGFPRO/TSIEMP/TGFTPV; itens trazem DESCRPROD via JOIN com TGFPRO; também extrai `cliente_nome_extraido` do JSON crú do LLM como hint) |
| `/sankhya/venda/api/email/<id>/pdf/` | GET | Serve o PDF autenticado (decorator `@xframe_options_sameorigin`). Se `PDF_PATH=NULL` (paste manual) → 404 amigável; frontend troca iframe por `<pre>` mostrando PDF_TEXTO |
| `/sankhya/venda/api/email/<id>/confirmar/` | POST | Promove para TGFCAB TOP 34. **Após commit**, grava aprendizado em 3 tabelas: alias parceiro, alias produto, e (se houver) `cod_cliente` por item em `AD_CLIENTE_PRODUTO_COD` |
| `/sankhya/venda/api/email/<id>/descartar/` | POST | Marca DESCARTADO + motivo |
| `/sankhya/venda/api/email/<id>/reparser/` | POST | Batch DELETE de itens pelo `RECEBIDO_ID` (atômico) + volta STATUS para AGUARDANDO_PARSER. Worker recria com prompt atual no próximo run |
| `/sankhya/venda/api/email/<id>/restaurar/` | POST | **Restaurar tudo** — recria TODOS os itens a partir do JSON crú do LLM já salvo + matching atual. Não chama LLM, instantâneo |
| `/sankhya/venda/api/email/<id>/item/criar/` | POST | Adiciona item manualmente (caso o LLM tenha esquecido). `SEQUENCIA = MAX+1`, CONFIANCA=1.0 (escolha humana) |
| `/sankhya/venda/api/email/item/<id>/editar/` | POST | Edita item inline na revisão |
| `/sankhya/venda/api/email/item/<id>/remover/` | POST | Remove item do pré-pedido |
| `/sankhya/venda/api/email/item/<id>/restaurar/` | POST | **Restaurar item** — UPDATE volta a 1 item ao valor original do LLM + matching atual. Demais itens preservados |

**Acesso:** Grupos `1`, `6`, `10` (decorator `@exige_grupo('venda')`).

---

## Tabelas auxiliares (DDL versionada)

DDLs em `sankhya_integration/sql/`:
- `AD_PEDIDO_EMAIL.sql` — DDL canônico das 2 tabelas principais (instalações novas)
- `AD_PEDIDO_EMAIL_MIGRATION_SUB_ID.sql` — `ALTER TABLE` adicionando `SUB_ID` em servidor existente
- `AD_PEDIDO_EMAIL_MIGRATION_ORIGEM.sql` — `ALTER TABLE` adicionando `ORIGEM` em servidor existente (Mai/2026)
- `AD_ALIAS_APRENDIZADO.sql` — DDL das 2 tabelas de aprendizado por descrição (`AD_PRODUTO_ALIAS`, `AD_PARCEIRO_ALIAS`)
- `AD_CLIENTE_PRODUTO_COD.sql` — DDL da tabela de vinculação por código do cliente + `ALTER` adicionando `COD_CLIENTE` em `AD_PEDIDO_EMAIL_ITEM` (Mai/2026)

Mesmo padrão da view do WMS (`ANDRE_IAGRO_SALDO_LOTE.sql`). Todas idempotentes via `_existe_coluna()`-pattern: código roda antes ou depois das migrations sem quebrar.

### `AD_PEDIDO_EMAIL_RECEBIDO`

**Uma linha por PEDIDO** dentro de um e-mail. Quando 1 PDF traz N pedidos (ex: rede de supermercado com 1 loja por página), o worker insere N linhas com mesmo `MESSAGE_ID` e `SUB_ID` 1..N. Anti-duplicação por UNIQUE composta `(MESSAGE_ID, SUB_ID)`.

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_PEDIDO_EMAIL_RECEBIDO` |
| `MESSAGE_ID` | VARCHAR2(255) | Header do e-mail (parte 1 da UNIQUE) |
| `SUB_ID` | NUMBER DEFAULT 1 | Sequencial 1,2,3... quando 1 PDF traz N pedidos. PDF de 1 pedido = SUB_ID=1 |
| `REMETENTE` | VARCHAR2(120) | E-mail do remetente |
| `ASSUNTO` | VARCHAR2(255) | Subject |
| `RECEBIDO_EM` | TIMESTAMP | Header Date |
| `PROCESSADO_EM` | TIMESTAMP | Worker timestamp |
| `PDF_PATH` | VARCHAR2(500) | Caminho absoluto no disco. **Multi-pedido:** aponta pro sub-arquivo `<MSGID>_sub{N}.pdf` (1 por SUB_ID). **Pedido único OU paste manual sem PDF:** aponta pro `<MSGID>.pdf` original ou NULL. |
| `PDF_TEXTO` | CLOB | **Texto do bloco específico** desse pedido (não o PDF inteiro). LLM recebe esse texto. |
| `LLM_RESPOSTA` | CLOB | JSON cru do LLM (auditoria + base pra restaurar itens) |
| `LLM_MODELO` | VARCHAR2(50) | Ex: `qwen2.5:14b-instruct` |
| `LLM_TOKENS_IN/OUT` | NUMBER | Telemetria |
| `LLM_CONFIANCA_GERAL` | NUMBER(3,2) | 0.00–1.00 — média ponderada dos scores de matching de parceiro+produtos |
| `CODPARC_SUGERIDO` | NUMBER | Vem do matching (alias > fuzzy contra TGFPAR completa) |
| `CODEMP_SUGERIDO` | NUMBER | Deduzida do último pedido do CODPARC sugerido |
| `CODTIPVENDA_SUGERIDO` | NUMBER | Último tipo do CODPARC sugerido |
| `DTNEG_SUGERIDA` | DATE | Best guess do LLM |
| `OBSERVACAO_EXTRAIDA` | VARCHAR2(2000) | Observação livre do PDF |
| `STATUS` | VARCHAR2(30) | Ver estados abaixo |
| `MOTIVO_DESCARTE` | VARCHAR2(500) | Quando STATUS=DESCARTADO ou ERRO_PARSER |
| `NUNOTA_GERADO` | NUMBER | TGFCAB.NUNOTA após CONFIRMADO |
| `CONFIRMADO_POR` | NUMBER | CODUSU do operador |
| `CONFIRMADO_EM` | TIMESTAMP | — |
| `ORIGEM` | VARCHAR2(20) DEFAULT 'IMAP' | Discriminador da origem: `IMAP` (worker e-mail), `TEXTO_LIVRE` (paste manual), `WHATSAPP_API` (futuro). Adicionada via migration ORIGEM em Mai/2026 |
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
| `SEQUENCIA` | NUMBER | Ordem do item no PDF (1-indexed, alinhada com `LLM_RESPOSTA.itens[i]`) |
| `DESCRICAO_PDF` | VARCHAR2(500) | Texto original do produto (literal do PDF) |
| `COD_CLIENTE` | VARCHAR2(50) | Código que o CLIENTE usa pro produto (ex: 8117 em Consinco). **Chave da Etapa 0 do matching híbrido.** Adicionada via migration `AD_CLIENTE_PRODUTO_COD.sql` em Mai/2026 |
| `CODPROD_SUGERIDO` | NUMBER | Inferido pelo matching híbrido (cod_cliente > alias > fuzzy) |
| `CODPROD_CONFIANCA` | NUMBER(3,2) | 0.00–1.00 — 1.00 se veio de cod_cliente ou alias; score fuzzy senão |
| `CODPROD_FINAL` | NUMBER | Após operador confirmar (NULL = ainda não confirmado) |
| `QTD` | NUMBER(15,3) | — |
| `CODVOL` | VARCHAR2(10) | UN/KG/CX/BD/etc. **Default `KG`** quando LLM não especifica (padrão agro). |
| `PRECO_UNIT` | NUMBER(15,4) | Pode ser NULL |
| `OBSERVACAO` | VARCHAR2(500) | — |
| `CRIADO_EM` | TIMESTAMP | DEFAULT SYSTIMESTAMP |

### `AD_PRODUTO_ALIAS` — aprendizado por de-para (produtos)

Cache de decisões humanas: descrição literal do PDF → CODPROD escolhido pelo operador. Consultado **antes** do fuzzy matching no `casar_codprod`. Match exato em `DESCRICAO_NORMALIZADA` (lowercase, sem acentos, sem sufixos KG/UN/etc, sem código numérico do início, dedupe de tokens).

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_PRODUTO_ALIAS` |
| `DESCRICAO_NORMALIZADA` | VARCHAR2(500) | Chave de busca (parte 1 da UNIQUE) |
| `CODPROD` | NUMBER | Mapeamento — qual CODPROD essa descrição representa |
| `CODPARC` | NUMBER NULL | NULL = alias global. Preenchido = scope-specific por cliente (parte 2 da UNIQUE) |
| `COUNT_USADO` | NUMBER DEFAULT 0 | Incrementa a cada uso — analytics |
| `ULTIMO_USO` | TIMESTAMP | Última vez que serviu de match |
| `CONFIRMADO_POR` | NUMBER | CODUSU do operador que gravou (1ª inserção) |
| `CRIADO_EM` | TIMESTAMP | DEFAULT SYSTIMESTAMP |

UNIQUE composta `(DESCRICAO_NORMALIZADA, CODPARC)`. Por que escopo opcional: cliente A pode chamar "PIMENTAO VERDE" o EXTRA, cliente B o MEDIO — alias por cliente desambigua.

### `AD_PARCEIRO_ALIAS` — aprendizado por de-para (clientes)

Análogo ao `AD_PRODUTO_ALIAS`, mas só por nome (não há scope adicional).

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_PARCEIRO_ALIAS` |
| `NOME_NORMALIZADO` | VARCHAR2(500) UNIQUE | Chave (lowercase, sem acentos, sem LTDA/S/A/CIA/etc, dedupe) |
| `CODPARC` | NUMBER | Mapeamento |
| `COUNT_USADO` | NUMBER DEFAULT 0 | — |
| `ULTIMO_USO` | TIMESTAMP | — |
| `CONFIRMADO_POR` | NUMBER | — |
| `CRIADO_EM` | TIMESTAMP | DEFAULT SYSTIMESTAMP |

**Auditável e reversível:** se uma decisão se mostrou errada (operador confirmou descuidadamente), basta `DELETE` da linha — sistema volta a usar fuzzy. Sem caixa preta.

### `AD_CLIENTE_PRODUTO_COD` — vinculação por código do cliente (Mai/2026)

Mais forte que alias por descrição. Em pedidos de redes (Consinco/Assaí/SENDAS), o PDF traz o "Cod Forn" — código que o **cliente** usa pra identificar nosso produto (ex: 8117 = "PIMENTAO VERDE", 8132 = "BERINJELA"). Estável e único por cliente; não muda com o tempo.

Após o operador confirmar 1 pedido, a vinculação `(CODPARC, COD_CLIENTE) → CODPROD` fica gravada e **TODOS os pedidos seguintes do mesmo cliente são casados automaticamente com confiança 100%** — sem fuzzy, sem alias por descrição.

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_CLIENTE_PRODUTO_COD` |
| `CODPARC` | NUMBER | Nosso parceiro (Assaí, etc.) — FK lógica TGFPAR |
| `COD_CLIENTE` | VARCHAR2(50) | Código do produto na visão do cliente (parte 2 da UNIQUE) |
| `CODPROD` | NUMBER | Nosso CODPROD interno — FK lógica TGFPRO |
| `COUNT_USADO` | NUMBER DEFAULT 0 | Incrementa a cada hit — analytics |
| `ULTIMO_USO` | TIMESTAMP | — |
| `CONFIRMADO_POR` | NUMBER | CODUSU do operador (1ª inserção) |
| `CRIADO_EM` | TIMESTAMP | DEFAULT SYSTIMESTAMP |

UNIQUE composta `(CODPARC, COD_CLIENTE)`. Auditável e reversível (DELETE da linha → sistema volta a usar alias/fuzzy).

---

## Fluxo do worker IMAP

Management command: `python manage.py colher_pedidos_email`. Agendado via Windows Task Scheduler a cada **30 minutos** (volume típico: 5 PDFs/dia).

Filtro IMAP: pega só mensagens **UNSEEN**. E-mails já abertos pelo operador no webmail não são reprocessados — pra forçar reprocessamento manual, basta marcar o e-mail como "não lido" no Titan.

```
FASE 1 — Coleta IMAP
1. Conecta IMAP Titan via imap-tools
2. Lista UNSEEN em pasta EMAIL_IMAP_FOLDER_ENTRADA
3. Para cada e-mail:
   a. Verifica MESSAGE_ID em AD_PEDIDO_EMAIL_RECEBIDO (anti-duplicação)
   b. Baixa anexo PDF, salva em PEDIDO_EMAIL_PDF_DIR/AAAA/MM/<MSGID>.pdf
   c. Extrai PÁGINAS do PDF com pdfplumber → list[(page_num, text)]
   d. Sem PDF / sem texto → STATUS=ERRO_PDF, move e-mail para Pedidos-Erros
   e. **detectar_layout()** identifica padrão (CONSINCO_RELPED ou GENERICO)
   f. **split_pedidos(paginas, layout)** divide por página + heurísticas:
      - Caso 1 (continuação sem header): página sem header anexa ao pedido em construção
      - Caso 2 (header repetido em continuação): novo bloco com <2 itens vira continuação
      - GENERICO: 1 pedido único cobrindo todas as páginas
   g. **split_pdf_fisico()** via pypdf cria N arquivos <MSGID>_sub{N}.pdf
      (1 pedido só → mantém <MSGID>.pdf sem sufixo; preserva original sempre)
   h. INSERT N linhas em AD_PEDIDO_EMAIL_RECEBIDO (mesmo MESSAGE_ID, SUB_ID
      1..N, PDF_PATH apontando pro sub-arquivo correto, ORIGEM='IMAP')
   i. Move e-mail para Pedidos-Processados

FASE 2 — Parser LLM + matching
4. Pre-carrega caches do matching: TGFPAR completo + TGFPRO completo (1 vez)
5. Lista registros AGUARDANDO_PARSER
6. Para cada um:
   a. detectar_layout(PDF_TEXTO) — escolhe variant do prompt LLM
   b. **DELETE defensivo** dos itens existentes (deletar_itens_do_pedido_email)
      → cobre cenários de Reparser parcial / race condition / re-parser
   c. Monta prompt do layout (CONSINCO_RELPED com avisos específicos OU GENERICO)
   d. Chama Ollama (timeout 600s, 3 retries; modelo qwen2.5:14b-instruct)
   e. Valida JSON: cliente_nome, data, observacao, itens[]
      Por item: cod_cliente (Consinco), descricao_pdf, qtd, codvol, preco_unit
   f. matching.casar_codparc(cliente_nome) → CODPARC (alias > fuzzy)
   g. Para cada item: matching.casar_codprod(descr, codparc, cod_cliente)
      → Etapa 0: AD_CLIENTE_PRODUTO_COD por (codparc, cod_cliente) → score 100
      → Etapa 1: AD_PRODUTO_ALIAS (scope-specific > global) → score 100
      → Etapa 2: fuzzy WRatio contra TGFPRO → score 75-100
   h. UPDATE cabecalho + INSERT itens (com COD_CLIENTE persistido se schema permite)
   i. STATUS=PENDENTE_REVISAO; falha → STATUS=ERRO_PARSER (reparser manual)

FASE PASTE MANUAL (independente)
- Operador clica botão "📋 Importar texto" na tela
- Cola texto de WhatsApp/e-mail/qualquer (≥30 chars)
- POST /sankhya/venda/api/email/importar-texto/
- Cria registro: PDF_PATH=NULL, PDF_TEXTO=<texto>, ORIGEM='TEXTO_LIVRE',
  STATUS=AGUARDANDO_PARSER, MESSAGE_ID='manual:<uuid>'
- Worker fase 2 pega no próximo run (layout=GENERICO)
```

### Helper: `split_pedidos(paginas, layout)`

Recebe `[(page_num, text), ...]` e devolve `[{sub_id, start_page, end_page, text, layout}, ...]`. Uso por layout:
- **`CONSINCO_RELPED`**: regex `PEDIDO DE COMPRAS PEDIDO PENDENTE DE APROVAÇÃO` em cada página → cada match abre novo pedido. Heurística "Caso 2" desambigua headers repetidos em continuação (bloco com <2 itens vira continuação do anterior).
- **`GENERICO`**: sem regex de header → 1 pedido único cobrindo todas as páginas (fallback seguro pra layouts novos).

### Helper: `split_pdf_fisico(pdf_path, pedidos, pasta_destino, base_nome)`

Via `pypdf`: para cada pedido com `start_page..end_page`, extrai páginas em arquivo separado `<base_nome>_sub{N}.pdf`. Preserva PDF original. Se houver só 1 pedido (caso comum), devolve `[pdf_path]` sem criar sub-arquivo. Fallback se pypdf não instalado: todos os SUB_IDs apontam pro original (não trava o pipeline; operador continua scrollando o PDF inteiro).

### Comando de backfill: `resplit_pdfs_email`

Pra registros legados criados antes da Fase 1 (vários SUB_IDs do mesmo MESSAGE_ID compartilhando o PDF original sem `_sub` no nome): `python manage.py resplit_pdfs_email`. Idempotente. Detecta grupos pela query `GROUP BY MESSAGE_ID, PDF_PATH HAVING COUNT(*) > 1`, re-extrai páginas, roda split_pedidos+split_pdf_fisico atual, faz UPDATE de PDF_PATH por SUB_ID. Conservador: pula grupos onde nº de pedidos detectados ≠ nº de SUB_IDs no banco (evita divergência).

---

## Parser LLM (Ollama local)

Módulo: `sankhya_integration/services/llm_local.py`

Modelo padrão: `qwen2.5:14b-instruct` (~8.5 GB, roda em CPU). Tempo médio por PEDIDO INDIVIDUAL após split: ~3 min em 14B no servidor de produção (Xeon E5-2680 v4 + 64GB RAM).

**Privacidade:** dados nunca saem da máquina. Conexão é só `http://localhost:11434`.

### Mudança chave (B+C, Mai/2026): prompt SEM contexto de IDs

O prompt antigo injetava top 50 parceiros + top 100 produtos como contexto, esperando que o LLM sugerisse IDs reais. Resultado: alucinação severa — em testes, o LLM extraiu CODPARC de um parceiro completamente alheio ("GRUPO PRIMO") porque ele estava no contexto, e inventou quantidades/preços. Trocamos pra:

- **LLM extrai apenas dados textuais literais** (cliente_nome, data, observacao, e por item descricao_pdf/qtd/codvol/preco_unit). Sem CODPARC/CODPROD na resposta.
- O prompt traz **avisos explícitos** sobre 2 erros recorrentes do PDF Consinco:
  - **Fornecedor ≠ Cliente**: bloco "FORNECEDOR" é AGROMIL (nós); cliente está em "DADOS PARA FATURAMENTO".
  - **Layout das colunas**: `Emb.` (sempre 1) → ignorar; `Qtde` → `qtd`; `Valor Unitário` → `preco_unit`. Antes o LLM trocava qtd/preço.
- **Few-shot example** com pedido Consinco real e JSON correto, mostrando inclusive os erros comuns.

Saída esperada do LLM (formato simplificado):

```json
{
  "cliente_nome": "SENDAS DISTRIBUIDORA S/A LJ176 176 PALMAS TEOTONIO",
  "data_negociacao": "2026-04-30",
  "observacao": null,
  "itens": [
    {"descricao_pdf": "PIMENTAO VERDE", "qtd": 160.0, "codvol": "KG", "preco_unit": 12.5},
    {"descricao_pdf": "MILHO VERDE C/5UN", "qtd": 80.0, "codvol": "BD", "preco_unit": 8.0}
  ]
}
```

Configuração:
- `OLLAMA_MODELO=qwen2.5:14b-instruct`
- `OLLAMA_TIMEOUT_SEGUNDOS=600` (10 min — folga para prompt grande do few-shot + retries)
- `OLLAMA_MAX_RETRIES=3`
- `format='json'` no chamado pra Ollama força JSON válido na resposta
- `temperature=0.1` — extração quase determinística

**Experimentação com 32B** sem trocar default: `ollama pull qwen2.5:32b-instruct` + `OLLAMA_MODELO=qwen2.5:32b-instruct` + `OLLAMA_TIMEOUT_SEGUNDOS=900` no `.env` temporariamente. Voltar para 14B após o teste. Ganho de acurácia ~3-5%, custo de tempo ~3x.

---

## Matching híbrido — `services/matching.py`

Resolve `CODPARC` e `CODPROD` em Python, **fora do LLM**. Estratégia em 2 etapas:

**Etapa 1 — alias (de-para):**
- `casar_codparc("SENDAS DISTRIBUIDORA S/A LJ176-FLV1")` consulta `AD_PARCEIRO_ALIAS` por `nome_normalizado`. Se encontrar, retorna direto com score 100.
- `casar_codprod("PIMENTAO VERDE", codparc=566)` consulta `AD_PRODUTO_ALIAS`: primeiro `(descricao_normalizada, codparc=566)`, depois `(descricao_normalizada, codparc IS NULL)` (alias global). Score 100 se achar.

**Etapa 2 — fuzzy contra TGFPAR/TGFPRO completos:**
- Cache em memória: 1 carga por execução do worker (~1700 strings × 2 versões).
- **Parceiros**: dois campos normalizados — `nome_curto` (NOMEPARC só) e `nome_longo` (NOMEPARC + RAZAOSOCIAL). Cada candidato é avaliado contra os dois e o maior score ganha. Scorer: `rapidfuzz.fuzz.token_sort_ratio` — penaliza tokens extras dos dois lados (importante porque várias filiais compartilham razão social como "SENDAS DISTRIBUIDORA S/A").
- **Produtos**: campo único `descr_norm`. Scorer: `rapidfuzz.fuzz.WRatio` (combina ratio + token_set + partial_ratio) — discrimina melhor produtos curtos como "PIMENTAO VERDE" vs "PIMENTAO VERMELHO".
- **Thresholds**: 70 pra parceiros, 75 pra produtos. Abaixo retorna `(None, score, '')` — operador escolhe na tela.

**Normalização**:
- Parceiros: strip de acentos, lowercase, remoção de sufixos `LTDA|S\.?A\.?|ME|EIRELI|EPP|MEI|SIA|CIA|S/A|S/C|FILIAL|MATRIZ`, dedupe de tokens.
- Produtos: strip de acentos, lowercase, remoção de código numérico colado (`8117PIMENTAO` → `pimentao`), remoção de sufixos `KG|G|MG|TON|UN|CX|BD|FD|PCT|...`.

**API pública do módulo:**

| Função | Retorno | Uso |
|---|---|---|
| `casar_codparc(nome, parceiros=None)` | `(codparc, score, nome_canonico)` ou `(None, score, '')` | Worker chama com nome extraído pelo LLM |
| `casar_codprod(descr, produtos=None, codparc=None)` | `(codprod, score, descr_canonica)` ou `(None, score, '')` | Worker chama por item; `codparc` opcional para alias scope-specific |
| `aprender_alias_parceiro(nome, codparc, confirmado_por)` | `{'ok': True, 'acao': 'INSERT'\|'UPDATE'}` | View `api_email_confirmar` chama após sucesso do INSERT em TGFCAB |
| `aprender_alias_produto(descricao, codprod, codparc, confirmado_por)` | idem | Idem, por item |
| `carregar_parceiros()` / `carregar_produtos()` | `list[dict]` | Pré-load no worker |
| `limpar_cache()` | — | Útil em testes pra forçar recarga |

---

## Tela de revisão (frontend)

Layout 2 colunas (proporções ajustadas em Mai/2026, 2026-05-08):
- **Coluna esquerda — Fila (`#emailFilaPanel`, 260px)**: lista de pré-pedidos `PENDENTE_REVISAO` ordenada por `RECEBIDO_EM DESC, SUB_ID ASC`. Indicadores: confiança geral (◐XX%), contador de pendentes, ações de import manual. _Largura era 320px antes da sessão de UX 2026-05-08 — encolhida pra dar mais espaço aos itens._
- **Coluna direita — Detalhe (`#emailDetalhePanel`, flex: 1)**, internamente split via grid `1fr 1.35fr` (PDF à esquerda, items à direita):
  - **Lado PDF**: iframe embutido (endpoint `api_email_pdf` tem `@xframe_options_sameorigin`). Em registros `ORIGEM='TEXTO_LIVRE'` (paste manual), troca por `<pre>` com `PDF_TEXTO`.
  - **Lado items**: badges no header (`⚡ Regex` / `🧠 LLM` distinguindo origem) + form de cabeçalho com typeaheads (parceiro/empresa/tipo). Hint "Nosso cliente: NOMEPARC" abaixo do typeahead de parceiro mostra o nome canônico da TGFPAR (vem do LEFT JOIN no `obter_pedido_email_completo`).

### Tabela de itens — 6 colunas (reorganizada Mai/2026, 2026-05-08)

| Coluna | Largura | Conteúdo |
|---|---|---|
| `Texto do PDF` | 26% | `cod_cliente - descricao` combinado, ex: `1042608 - MILHO VERDE C/5UN`. Cai pra só descrição se PDF não trouxe `cod_cliente`. **Read-only**, do LLM/regex |
| `CODPROD` | 32% | Typeahead (busca por código OU nome), endpoint `/sankhya/produtos/search/` reusado da Venda + filtro `grupo_inicia_com=1` (mesma regra da Venda — só hortifrúti vendável, sem mudas/insumos/embalagens). Mostra `cod — descrição` da TGFPRO. Navegação ↓/↑/Tab/Enter/Esc. Pill da origem do match no canto inferior direito (ver abaixo) |
| `Qtd` | 110px | Célula unificada com 2 inputs em `.qtdvol-wrap` (inline-flex, gap 4px): qtd 50px + vol 34px (vol em font-size 11px, cor mais clara — visualmente vira sufixo). Ex: `160 KG` |
| `Preço` | 75px (`col-w-preco`) | Preço unitário, edição livre |
| `Total` | 90px (`col-w-num`) | **NOVA** (Mai/2026, 2026-05-08): `qtd × preço_unit` formatado em BR (`R$ 640,00`). Recalcula reativo em `atualizarTotais()` que já roda em onChange de qtd/preço. Mostra `—` quando falta qtd ou preço |
| Ações | 60px | `↺` restaurar este item + `🗑` remover |

Linhas sem CODPROD ficam destacadas em amarelo (`.alerta`). Padding global das células: `5px 6px` (compacto).

### Pill da origem do match (CODPROD)

Indicador visual de **onde** veio a sugestão de CODPROD. Posicionado no **canto inferior direito** da célula CODPROD (`bottom: 1px; right: 4px`), `pointer-events: none` pra não bloquear clicks no input do typeahead.

| Pill | Cor | Quando aparece | Significado |
|---|---|---|---|
| `✓` | verde forte | `CODPROD_FINAL` preenchido na DB | **Você** editou/confirmou esse item nesta revisão (digitou no typeahead, salvou). É um carimbo de toque humano nesta sessão |
| `alias` | verde claro | `confiança = 1.00` (Etapa 0 ou 1 do matching) | O **worker** aplicou uma vinculação aprendida em pedido anterior. Sem toque humano nesta sessão. **Pode estar errado** se a vinculação prévia estava errada — operador edita e a confirmação **sobrescreve** o alias (UPSERT em `aprender_alias_produto` / `gravar_cod_cliente_codprod`) |
| `~ XX%` | amarelo | confiança 0.75–0.99 (Etapa 2 fuzzy WRatio) | Match por similaridade. **Confira sempre** |
| `~ XX%` | vermelho | confiança 0.01–0.74 (raro, defensivo) | Match fraco. Threshold 75 do matching corta antes na prática |
| _(sem pill)_ | — | sem CODPROD sugerido | Linha amarela "alerta", operador escolhe manualmente |

**Histórico do design**: a pill ficava `top: -6px` saindo pra cima da célula e atrapalhava leitura. Em Mai/2026 (2026-05-08) testamos bolinha colorida (●) inline, mas operador preferiu voltar pro pill com texto — apenas reposicionado pra dentro da célula. Mantém legibilidade do texto (`alias` / `~90%`) que é mais imediato que cor isolada.

### Rodapé com totais

`<tfoot>` reorganizado pras 6 colunas (Mai/2026, 2026-05-08):
- **Linha "Calculado"**: Σ qtd (sem casa decimal) e Σ valor calculado de `qtd × preço`. Recalcula a cada onChange.
- **Linha "PDF (referência)"** — só visível quando há totais extraídos: número de itens + `Total geral` declarado no PDF. Chip ✓/⚠ indica se calculado bate (tolerância R$ 0,10).

⚠ **Importante sobre os totais**: a linha "PDF (referência)" mostra o que foi **extraído literal** do texto do PDF via regex (`Total geral: R$ X.XXX,XX` e `Total de itens: N`), não calculado. Quando aparece `—`, é porque a regex não achou o padrão no texto (típico do Consinco que traz "Total geral" mas não "Total de itens"). **A linha existe pra confrontar literal vs calculado** — se também calculássemos, perderia a função de auditoria.

Campo `Observação` fica abaixo da tabela. Rodapé de ações: `Descartar` | `Restaurar tudo` | `Reparser` | `Confirmar e criar pedido`.

### Restauração de itens

Operador tem 3 opções pra desfazer edições:

| Botão | O que faz | Tempo | Quando usar |
|---|---|---|---|
| `↺` por linha | UPDATE da linha pra valores originais (do `LLM_RESPOSTA`) + matching atual. Outros itens preservados. | Instantâneo | Editou 1 item por engano |
| `Restaurar tudo` | DELETE itens + INSERT recriando do `LLM_RESPOSTA` + matching. **Não chama LLM** | ~1s | Quer voltar tudo ao zero sem esperar LLM |
| `Reparser` | DELETE itens + STATUS=AGUARDANDO_PARSER. Worker vai reprocessar (chama Ollama de novo). | ~3 min ou até 30 min (Task Scheduler) | Prompt foi melhorado e quer re-extrair |

A diferença chave: `Restaurar tudo` reusa o JSON crú já salvo em `LLM_RESPOSTA`, enquanto `Reparser` força nova chamada Ollama. Pra desfazer edições normais, **sempre prefira "Restaurar tudo"** — é instantâneo e idempotente.

Convenções visuais:
- ◐XX% = confiança geral (vermelho < 50%, laranja 50-80%, verde > 80%)
- Badge laranja `Sugerido — confirme` em campos com confiança baixa
- ⚠ inline em itens sem CODPROD mapeado

---

## Confirmação — promoção para TGFCAB + aprendizado

Endpoint `POST /sankhya/venda/api/email/<id>/confirmar/`:

1. Validações: pré-pedido existe, STATUS=PENDENTE_REVISAO, todos os itens têm CODPROD_FINAL, CODPARC válido.
2. Atomicidade: dentro de `with obter_conexao_oracle() as conn`.
3. Chama `inserir_cabecalho_nota_banco(..., CODTIPOPER=34, conexao_existente=conn)` — workaround DPY-1001 padrão.
4. Para cada item: `inserir_item_nota_banco(...)` com NUNOTA gerado.
5. `recalcular_totais_nota_banco`.
6. UPDATE em AD_PEDIDO_EMAIL_RECEBIDO: `STATUS='CONFIRMADO'`, `NUNOTA_GERADO=<NUNOTA>`, `CONFIRMADO_POR=<codusu da sessão>`, `CONFIRMADO_EM=SYSTIMESTAMP`.
7. `conn.commit()`.
8. **APRENDIZADO (pós-commit, tolerante a falhas)** — após o commit do TGFCAB, gravamos as decisões do operador em `AD_*_ALIAS`:
   - `aprender_alias_parceiro(cliente_nome_extraido_do_LLM, codparc, codusu)` — chave: nome literal do LLM, valor: CODPARC escolhido.
   - Para cada item: `aprender_alias_produto(descricao_pdf, codprod_final, codparc, codusu)` — alias scope-specific por cliente.
   - **Falha aqui NÃO desfaz a confirmação** — só perde a oportunidade de aprender. Audit é telemetria, regra de negócio já foi efetivada.

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
OLLAMA_TIMEOUT_SEGUNDOS=600   # subido de 120 → 600 pós B+C — prompt grande do few-shot demanda folga
OLLAMA_MAX_RETRIES=3
# Para experimentar 32B sem trocar default:
#   OLLAMA_MODELO=qwen2.5:32b-instruct + OLLAMA_TIMEOUT_SEGUNDOS=900

# Storage
PEDIDO_EMAIL_PDF_DIR=z:\TI\NexusGTi\IAgro\IAgro\media\pedidos_email
```

---

## Decisões de regra de negócio

1. **Pré-pedido fica em tabela auxiliar Oracle, não em SQLite nem em TGFCAB com TOP novo.** Razão: backup unificado, joinable com TGFCAB via NUNOTA_GERADO, mas sem poluir queries existentes.
2. **TGFCAB recebe INSERT só após confirmação humana.** Razão: rascunhos de parser não viram ruído em painéis Sankhya de outros operadores.
3. **CODUSU em TGFCAB = quem clicou Confirmar**, não o "usuário do worker". Audit fica natural.
4. **CODEMP é deduzida do último pedido do CODPARC**; sem matching → cai no default 10. Operador pode trocar.
5. **CODTIPVENDA = último do CODPARC**, com badge laranja "Confirme — sugerido pelo histórico" até operador validar.
6. **Atrasados na fila ficam esperando indefinidamente** — sem job de alerta SMTP. Operador tem hábito de olhar a tela.
7. **Multi-pedido por PDF**: 1 e-mail = N linhas em RECEBIDO (mesmo MESSAGE_ID, SUB_ID 1..N), cada uma confirmada e auditada independente. UNIQUE composta `(MESSAGE_ID, SUB_ID)`. Decisão: replicar metadata (REMETENTE) entre as N linhas em troca de auditoria limpa por pedido. **PDF_PATH é específico por SUB_ID** (sub-arquivo via pypdf) — a partir da Fase 1 (Mai/2026).
8. **Split físico do PDF (Fase 1)**: cada SUB_ID tem seu arquivo. Operador vê só as páginas relevantes no iframe. PDF original preservado em `<MSGID>.pdf`. PDFs com 1 pedido só **NÃO criam** sub-arquivo (sem sufixo).
9. **LLM extrai SÓ texto literal**, sem injeção de IDs candidatos. Resolução de CODPARC/CODPROD em Python via `services.matching` (cod_cliente > alias > fuzzy). Razão: contexto top-N causava alucinação severa do LLM (escolhia nomes/IDs do contexto em vez de extrair do texto).
10. **Matching híbrido com 2 scorers fuzzy diferentes**: `token_sort_ratio` para parceiros (várias filiais compartilham razão social) e `WRatio` para produtos (descrições curtas como "PIMENTAO VERDE" vs "PIMENTAO VERMELHO" exigem discriminação fina).
11. **Hierarquia de matching de produto em 3 níveis (Mai/2026)**: Etapa 0 (`AD_CLIENTE_PRODUTO_COD` por cod_cliente) > Etapa 1 (`AD_PRODUTO_ALIAS` por descrição normalizada) > Etapa 2 (fuzzy WRatio). Etapa 0 só ativa quando o LLM extraiu cod_cliente (típico Consinco). É a mais forte e estável: bate exato em código numérico, não sofre com variações textuais.
12. **Aprendizado por confirmação é dicionário, NÃO ML**. 3 tabelas de cache de atalhos auditável (DELETE da linha reverte). Sem treinamento, sem inferência.
13. **Aprendizado scope-specific por cliente** em produtos (`CODPARC` opcional na PK composta de `AD_PRODUTO_ALIAS`). Cliente A pode chamar "PIMENTAO VERDE" o EXTRA, B o MEDIO. Parceiros não tem escopo (só por nome).
14. **Alias é gravado SOMENTE no clique de "Confirmar e criar pedido"** — confirmação humana = aval de qualidade. Edições parciais sem confirmar não viram aprendizado. Falha em gravar alias é tolerada (logger.warning) — TGFCAB já foi commitado, regra de negócio efetivada.
15. **PDF original mora em disco, não em BLOB.** Caminho absoluto em `PDF_PATH`. Disco backupeado pelo backup geral do servidor.
16. **OCR não está incluído.** Se PDF for escaneado e pdfplumber não conseguir extrair texto, registro vai para `ERRO_PDF` e operador trata manualmente. OCR (Tesseract) pode ser adicionado em v2 se aparecer demanda.
17. **`Restaurar tudo` reusa o JSON crú do LLM**, não chama Ollama. Diferente de `Reparser` que invalida e espera worker. Razão: 99% dos casos de "desfazer edição" não precisam de novo LLM call (~3 min); só precisam recriar a partir do estado conhecido.
18. **Layouts plugáveis (Fase 2)**: `_HEADERS_POR_LAYOUT` (worker) + `PROMPTS_POR_LAYOUT` (LLM). Layout desconhecido cai em `GENERICO` (split sem regex, prompt neutro) — sistema funciona mesmo com fornecedor novo, operador corrige na revisão e alias acelera próximas.
19. **Paste manual de texto livre (Fase 3)**: botão `📋 Importar texto` cria registro com `PDF_PATH=NULL` + `ORIGEM='TEXTO_LIVRE'`. Frontend troca iframe por `<pre>` mostrando o texto colado. Worker pula extração de PDF (texto já está em PDF_TEXTO) e roda LLM com layout=GENERICO.
20. **`ORIGEM` é discriminador, não filtro**: `IMAP` (default), `TEXTO_LIVRE`, `WHATSAPP_API` (futuro). Tudo entra na mesma fila e usa o mesmo fluxo de revisão.
21. **Defesa anti-duplicação em camadas**: (a) `api_email_reparser` faz batch DELETE pelo `RECEBIDO_ID` (atômico, não loop); (b) **worker faz DELETE defensivo** antes de cada INSERT mesmo. Razão: já tivemos duplicação real quando a camada 1 falhou silenciosamente. Defesa em camadas custa pouco e elimina o cenário.
22. **Hostgator/Titan exige toggle "Acesso a e-mail de terceiros"**. Sem ativar, IMAP retorna `[AUTHENTICATIONFAILED] Auth not allowed for mailbox` mesmo com senha correta. Não há app password no Titan — usa-se senha normal do e-mail.
23. **Schema-resilient via `_existe_coluna()`**: helper em `oracle_conn.py` cacheia 1× por processo Python qual coluna existe. Permite código rodar antes/depois de migrations sem quebrar (ORA-00904 evitado). Reseta no restart do Django/worker.
24. **Console Windows é cp1252** — strings em `self.stdout.write()` de management commands devem ser ASCII (sem `→ ↪ ✓ ⚠`). Comentários e docstrings podem ter Unicode (não passam pelo encode).
25. **Filtro `grupo_inicia_com=1` no typeahead de produto** (Mai/2026): mesma regra usada na Venda — só produtos com `CODGRUPOPROD LIKE '1%'` (hortifrúti vendável). Aplicado nos 2 typeaheads de produto da tela (linha por linha + modal "Adicionar item manual"). Razão: o pré-pedido vai virar TGFCAB TOP 34 reusando as APIs da Venda — manter o mesmo conjunto de produtos disponíveis evita inconsistência (operador pode escolher mudas/insumos no email-importar e a venda rejeitar depois).
26. **Dropdown do typeahead de produto vai pro `<body>` com `position: fixed`** (Mai/2026): dentro de `<td>` em tabela com `border-collapse: collapse`, `position: absolute` ancorado em `position: relative` da td é instável (Chrome ignora em alguns cenários, dropdown some). Solução: `appendChild` ao body antes do show + coordenadas via `getBoundingClientRect()` do input. Vide `.claude/gotchas.md` ("Dropdown de typeahead dentro de <td>"). Mesma técnica deve ser usada em qualquer typeahead novo dentro de tabela.

---

## Frontend — arquivos

- **Template:** `email_importar.html`
- **CSS:** `email_importar.css`
- **JS:** `email_importar.js`
- **Helpers reusados:** `IAgro.postJSON`, `IAgro.confirmarAcao`, typeaheads existentes (`attachTA` de `venda.js`)

---

## Setup operacional (executar uma vez)

1. **Aplicar DDLs no Oracle:**
   - `sankhya_integration/sql/AD_PEDIDO_EMAIL.sql` (tabelas principais) **✅ Concluído Mai/2026**
   - `sankhya_integration/sql/AD_PEDIDO_EMAIL_MIGRATION_SUB_ID.sql` (migration SUB_ID em servidor existente) **✅ Concluído Mai/2026**
   - `sankhya_integration/sql/AD_ALIAS_APRENDIZADO.sql` (tabelas de alias) **✅ Concluído Mai/2026**
   - `sankhya_integration/sql/AD_PEDIDO_EMAIL_MIGRATION_ORIGEM.sql` (coluna ORIGEM pra paste manual — Fase 3) **✅ Concluído Mai/2026**
   - `sankhya_integration/sql/AD_CLIENTE_PRODUTO_COD.sql` (vinculação por código do cliente — Mai/2026) **✅ Concluído Mai/2026**
2. **Criar pastas IMAP no Titan webmail:** `Pedidos-Entrada`, `Pedidos-Processados`, `Pedidos-Erros` (hífens). **✅ Concluído Mai/2026.**
3. **Ativar "Acesso a e-mail de terceiros" no painel Titan/Hostgator** — sem isso o IMAP rejeita login. **✅ Concluído Mai/2026.**
4. **Instalar Ollama no servidor** (Xeon E5-2680 v4 + 64GB RAM): `https://ollama.com/download/windows`. **✅ Concluído Mai/2026.**
5. **Baixar modelo padrão:** `ollama pull qwen2.5:14b-instruct` (~8.5 GB). **✅ Concluído Mai/2026.**
6. **Criar venv no servidor + `pip install -r requirements.txt`** (inclui `rapidfuzz`, `imap-tools`, `pdfplumber`, `ollama`, **`pypdf`** pra split físico). **✅ Concluído Mai/2026.**
7. **Preencher `.env`** com credenciais IMAP (senha NORMAL do e-mail no Titan, não app password). **✅ Concluído Mai/2026.**
8. **Smoke tests** (Oracle + Ollama + IMAP) — todos OK. **✅ Concluído Mai/2026.**
9. **Backfill de PDFs antigos** (legado pré-Fase 1, vários SUB_IDs compartilhando o mesmo PDF): `python manage.py resplit_pdfs_email`. Idempotente. **✅ Concluído Mai/2026.**
10. **Agendar worker no Windows Task Scheduler:** `python manage.py colher_pedidos_email` a cada 30 min. *(pendente)*

**Filtro automático no Titan:** ainda não criado. Operador move e-mails manualmente da Caixa de Entrada para `Pedidos-Entrada`. Decisão tática — começar simples, calibrar regra depois de algumas semanas de uso real.

---

## Pendências (v2)

### ✅ Etapa 0 regex parser — implementado em testes (Mai/2026)

Implementado em 3 fases (sessão Mai/2026, 2026-05-07):

- **Fase A — infra plugável**: `services/pdf_parsers/__init__.py` (registry `PARSERS_POR_LAYOUT` + dispatcher `tentar_parseamento()`) + `services/pdf_parsers/consinco.py`. Worker tenta o parser específico do layout antes do LLM; falha (None / exceção / shape inválido) cai em fallback transparente.
- **Fase B — parser Consinco real**: regex sobre `pdf_texto` extraído pelo pdfplumber. Extrai `cliente_nome` (bloco `DADOS PARA FATURAMENTO`), `data_negociacao`, `itens` (âncora regex `<VOL> <VOL> <EMB=1> <QTDE> <VLR_UNIT> <VLR_ITEM>`). Validações cruzadas: `Total de itens declarado == len(itens)` + `|Σ valor − Total geral PDF| ≤ R$ 0,10`. Qualquer divergência → None → fallback LLM. Conservador por design: prefere LLM lento e correto a regex rápida e errada.
- **Fase C — telemetria visual**: badge `⚡ Regex` / `🧠 LLM` no header do detalhe + 2ª linha no `<tfoot>` mostrando totais declarados no PDF (`<N> itens` + `R$ <total>`) com chip `✓ Bate com PDF` / `⚠ Diverge` (tooltip com diff). Telemetria persistida via `LLM_MODELO='regex_consinco_v1'` na DB.

**Cobertura ampla**: `extrair_totais_pdf()` em `services/pdf_parsers/consinco.py` é reutilizado em `api_email_obter` no GET — a linha de conferência aparece **mesmo em registros parseados via LLM** se o `pdf_texto` tinha "Total geral" / "Total de itens".

**Compatibilidade preservada**: `LLM_RESPOSTA` segue shape idêntico ao do LLM (`cliente_nome`, `data_negociacao`, `observacao`, `itens` com `cod_cliente`/`descricao_pdf`/`qtd`/`codvol`/`preco_unit`). `Restaurar tudo` e `Restaurar item` funcionam nos dois caminhos sem mudança.

**Status**: aguardando 1 semana de uso real em produção pra:
1. Validar acurácia em PDFs Consinco variados (~88% no MVP de Mai/2026)
2. Medir % de fallback LLM (alvo: <20% — confirma que regex pega a maioria)
3. Medir tempo médio da fila (alvo: 5-10s vs ~3min do regime LLM-only)

### Outras pendências

- **OCR (Tesseract)** para PDFs escaneados (atualmente caem em `ERRO_PDF`).
- **Detecção de mais layouts** — hoje só conhece o cabeçalho Consinco/RelPedSuprim. Outros provedores (Cobasi, Pão de Açúcar próprio, etc.) podem usar templates diferentes. Ampliar `_HEADERS_POR_LAYOUT` + `PROMPTS_POR_LAYOUT` quando aparecerem.
- **Métricas de acurácia do matching** — dashboard com `COUNT_USADO` por alias, % de itens que passaram sem edição manual, evolução semanal.
- **Mapeamento por domínio do remetente** (`AD_EMAIL_DOMAIN_MAP`) — `klistian.lima@assai.com.br` → família ASSAI/SENDAS, mesmo se o nome no PDF for ambíguo.
- **Reparser imediato** (sem esperar Task Scheduler) — endpoint que dispara LLM em foreground com `--max 1`. Tela mostra "processando…" ~3 min mas elimina espera de 30 min do Task Scheduler. Especialmente importante pra paste manual de WhatsApp.
- **`keep_alive=-1` no cliente Ollama** — modelo nunca descarrega da RAM, elimina latência de 1ª chamada do dia (~1-2 min de carga). Adicionar em `llm_local.py`.
- **Trocar pra `qwen2.5:7b-instruct`** se acurácia testada for aceitável — 3× mais rápido (~1 min vs ~3 min).
- **Alerta passivo de fila atrasada** (contador no header da tela).
- **Re-treino/fine-tuning** de prompt baseado em feedback acumulado.
- **Integração WhatsApp Business API** (longo prazo, depois de validar paste manual em uso real).

---

## Decisão pendente registrada: migração LLM local → cloud (Anthropic API)

Discussão técnica registrada em sessão Mai/2026 — **decisão pendente** aguardando:

1. Aval do compliance/jurídico sobre LGPD (Anthropic não é processadora cadastrada na ANPD, dados de cliente saem da máquina)
2. Resultado de 1 semana de produção da Etapa 0 regex — pode reduzir ~80% das chamadas LLM e mudar o cálculo de custo/benefício

### Esclarecimento do "Plano Max"

O plano Max da Anthropic cobre Claude.ai (chat) + Claude Code com cotas elevadas. **Não cobre uso server-side via API** (Django → `api.anthropic.com`). Para integração de backend, é cobrança separada por token. Validar conta antes de assumir custo zero.

### Custo estimado (volume real ~5 PDFs/dia, ~5k tokens in + 1k out por pedido)

| Modelo | Custo/pedido | Custo/mês |
|---|---|---|
| Haiku 4.5 | ~US$ 0,01 | ~US$ 1,50 |
| Sonnet 4.6 | ~US$ 0,03 | ~US$ 4,50 |
| Opus 4.7 | ~US$ 0,15 | ~US$ 22,50 |

Custo desprezível na operação atual.

### Prós

- **Latência 30-60×**: 5-15s vs ~3min/pedido. Paste manual de WhatsApp deixa de ser doloroso.
- **Acurácia 95-98% vs 82-90% (Qwen 14B local)**: menos correções, alias aprende mais rápido.
- **Sem CPU travado**: servidor livre durante parser para outras tarefas.
- **Multimodal**: pode mandar PDF direto sem `pdfplumber`. Robustez contra layouts difíceis.
- **Sem manutenção de modelo**: sem `ollama pull`, sem 8.5 GB em disco, sem patches de segurança do Ollama.
- **Lida com layouts novos sem fine-tuning**: novo cliente Cobasi/Pão de Açúcar funciona sem ajuste de prompt.

### Contras

- **🔴 LGPD/privacidade (alta)**: cada PDF envia CNPJ, razão social, preços, dados de cliente, talvez vendedor para servidor da Anthropic (US). Anthropic não é processadora cadastrada perante ANPD. Exige aval explícito do compliance.
- **Dependência de internet (média)**: queda do link da Agromil → fila trava. Ollama local segue rodando offline.
- **Auditoria (média)**: logs de requests ficam na Anthropic; ideal seria trilha local também.
- **Vendor lock-in (baixa)**: API estável, mas mudanças de preço/deprecation acontecem.
- **Latência variável (baixa)**: 95% dos requests <10s, mas pode picar a 30s em dias ruins.

### Impacto arquitetural se a migração for aprovada

| Componente | Mudança |
|---|---|
| `services/llm_local.py` | Reescrever com cliente `anthropic` em vez de `ollama`. Prompts (Consinco/GENERICO) permanecem — formato JSON é igual |
| `requirements.txt` | + `anthropic` (substitui ou convive com `ollama`) |
| `.env` | + `ANTHROPIC_API_KEY`, `ANTHROPIC_MODELO` (haiku/sonnet/opus) |
| Worker | Sem mudança estrutural — só troca a chamada |
| **Etapa 0 regex Consinco** | **Continua valendo e ganha peso** — evita expor ~80% do volume Consinco para fora da máquina |
| Tela de revisão | Badge `🧠 LLM` pode virar `☁️ Claude Sonnet` para distinguir cloud de local |

### Caminhos possíveis (sem ordem de preferência)

1. **All-in cloud**: substitui Ollama por Anthropic. Simples e rápido, mas atravessa a decisão de privacidade.
2. **Híbrido por origem**: Consinco/IMAP fica regex+Ollama (privacidade preservada); paste manual vai para cloud (velocidade onde mais dói). Mais código mas respeita decisão original.
3. **Manter Ollama, downsize 14B → 7B**: ~1min/pedido, sem gasto, sem expor dados. Acurácia ~75-85% (3-5 p.p. abaixo do 14B).
4. **GPU local**: RTX 4070 ~R$ 5k → Qwen 14B em ~10s. Capex alto, elimina o trade-off privacidade-vs-velocidade.

### Recomendação registrada

A combinação **Etapa 0 regex (já implementada) + paste manual em cloud** (caminho 2 híbrido) provavelmente atende sem expor dados estruturados de redes de supermercado. **A Etapa 0 sozinha pode tornar essa decisão desnecessária** — esperar 1 semana de produção antes de decidir. Se a fila atrasada for o motivo principal de revisitar, a Etapa 0 deve resolver na maioria dos casos.

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
