# Schema do Banco

Documentação consolidada das tabelas Oracle (Sankhya), colunas usadas, TOPs, status e view dedicada do WMS. Também inclui modelos SQLite do Django.

---

## 1. Bancos de Dados

| Banco | Uso |
|---|---|
| **Oracle (Sankhya)** | Todas as operações de negócio: notas, itens, financeiro, parceiros, lotes |
| **SQLite (Django)** | Sessões + modelos `Simulation` (simulações comerciais) e `RastreioAudit` (audit log do WMS) |

A conexão Oracle é gerenciada por `obter_conexao_oracle()` (context manager) em `services/oracle_conn.py`. A flag `is_write_enabled()` controla se INSERT/UPDATE/DELETE estão habilitados.

---

## 2. Tabelas Oracle (Sankhya)

### TGFCAB — Cabeçalho de Notas / Pedidos

Núcleo de qualquer documento (compra, venda, transferência, classificação).

| Coluna | Tipo | Descrição |
|---|---|---|
| `NUNOTA` | NUMBER | Número único da nota (PK) |
| `NUMNOTA` | NUMBER | Número sequencial por empresa (gerado no faturamento) |
| `CODEMP` | NUMBER | Código da empresa |
| `CODPARC` | NUMBER | Código do parceiro (cliente ou fornecedor) |
| `CODTIPOPER` | NUMBER | TOP — Tipo de operação (11, 13, 26, 30, 34, 35, 37) |
| `CODNAT` | NUMBER | Código de natureza (ver tabela CODNAT_POR_TOP) |
| `CODTIPVENDA` | NUMBER | Tipo de negociação (FK → TGFTPV) |
| `DHTIPVENDA` | DATE | Timestamp de alteração do tipo de negociação (exigido por trigger) |
| `STATUSNOTA` | CHAR(1) | Status (ver §4) |
| `DTNEG` | DATE | Data da negociação |
| `DTMOV` | DATE | Data do movimento |
| `DTFATUR` | DATE | Data do faturamento (preenchido em TOP 35/37) |
| `VLRNOTA` | NUMBER | Valor total da nota |
| `QTDVOL` | NUMBER | Quantidade total de volumes |
| `OBSERVACAO` | VARCHAR2 | Observação livre |
| `CODUSU` | NUMBER | Usuário que criou |
| `AD_NUMPEDIDOORIG` | NUMBER | Pedido original (auto-cura na Entrada/Classificação — não usar em Venda/Rastreio) |

### TGFITE — Itens de Notas / Pedidos

Cada linha vinculada a um `NUNOTA` da `TGFCAB`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `NUNOTA` | NUMBER | FK → TGFCAB.NUNOTA |
| `SEQUENCIA` | NUMBER | Sequência do item dentro da nota |
| `CODPROD` | NUMBER | Código do produto |
| `CODVOL` | VARCHAR2 | Unidade de volume (KG, UN, etc.) |
| `QTDNEG` | NUMBER | Quantidade negociada |
| `VLRUNIT` | NUMBER | Valor unitário |
| `VLRTOT` | NUMBER | Valor total da linha |
| `CODLOCALORIG` | NUMBER | Local de origem do estoque |
| `CODAGREGACAO` | VARCHAR2 | **Lote** — código do lote (formato `NUNOTAS{SEQ}D{YYMMDD}` na Entrada; livre na Venda; NULL em item de Venda até atribuição pelo Rastreio). É também o vínculo usado pelo WMS para localizar saldo |
| `AD_QTDAVARIA` | NUMBER | Quantidade de avaria (descarte) — usado em Classificação e perna E do WMS |
| `AD_PESO` | NUMBER | Peso registrado na pesagem da Entrada |
| `AD_QTDCONFERIDA` | NUMBER | Quantidade conferida na entrada |
| `RESERVA` | VARCHAR2(1) | Flag de reserva de estoque. **Mai/2026 (2026-05-20)**: IAgro grava `'S'` em TOP 34/35/37 — sem isso o trigger `TRG_UPT_TGFITE` rejeita UPDATE com `ORA-20101: Reserva diferente da definicao na TOP` quando Sankhya recálcula/imprime |
| `ATUALESTOQUE` | NUMBER | Flag de atualização de estoque (`1`=atualiza ao faturar; `-1`=ignora). IAgro grava `1` em TOP 34/35/37 desde Mai/2026 (2026-05-20) — antes era `-1` por default, que aciona o mesmo trigger |
| `USOPROD` | VARCHAR2(1) | Tipo de uso (`V`=Venda, `R`=Revenda, `C`=Consumo). IAgro lê de `TGFPRO.USOPROD` em TOP 34/35/37 desde Mai/2026 (2026-05-20) — antes chutava `'V'` |

### TGFPAR — Parceiros (Clientes/Fornecedores)

| Coluna | Tipo | Descrição |
|---|---|---|
| `CODPARC` | NUMBER | Código do parceiro (PK) |
| `NOMEPARC` | VARCHAR2 | Nome / razão social |
| `RAZAOSOCIAL` | VARCHAR2 | Razão social oficial |
| `CGC_CPF` | VARCHAR2 | CNPJ ou CPF |

### TGFTPV — Tipos de Negociação

| Coluna | Tipo | Descrição |
|---|---|---|
| `CODTIPVENDA` | NUMBER | Código (PK) |
| `DESCRTIPVENDA` | VARCHAR2 | Descrição |
| `ATIVO` | CHAR(1) | `S`/`N` |
| `DHALTER` | DATE | Última alteração (usado em `DHTIPVENDA` da TGFCAB) |

> **Trigger `SANKHYA.TRG_INC_TGFCAB`** exige a tupla `(CODTIPVENDA, DHTIPVENDA)` coerente. Sem isso, Oracle rejeita com `ORA-20101: Verifique se o TIPO DE NEGOCIAÇÃO X está ativo...`.

### TSIEMP — Empresas

| Coluna | Tipo | Descrição |
|---|---|---|
| `CODEMP` | NUMBER | Código da empresa (PK) |
| `RAZAOSOCIAL` | VARCHAR2 | Razão social |
| `NOMEFANTASIA` | VARCHAR2 | Nome fantasia |

### TGFFIN — Financeiro

Gerado pelo módulo Comercial após faturamento de vales.

| Coluna | Tipo | Descrição |
|---|---|---|
| `NUFIN` | NUMBER | Número financeiro (PK) |
| `NUNOTA` | NUMBER | FK → TGFCAB |
| `CODPARC` | NUMBER | Parceiro |
| `VLRDESDOB` | NUMBER | Valor do desdobramento |
| `DTVENC` | DATE | Vencimento |
| `RECDESP` | NUMBER | 1 = receita, -1 = despesa |

### TSIGRU — Grupos de Usuário

| Coluna | Tipo | Descrição |
|---|---|---|
| `CODGRU` | NUMBER | Código do grupo (PK) |
| `DESCRGRU` | VARCHAR2 | Descrição |

Mapeamento aplicado no sistema: ver `architecture.md` → "Mapeamento de grupos Sankhya".

### TGFPRO — Produtos (referenciado nas queries)

| Coluna | Tipo | Descrição |
|---|---|---|
| `CODPROD` | NUMBER | Código do produto (PK) |
| `DESCRPROD` | VARCHAR2 | Descrição |
| `CODVOL` | VARCHAR2 | Volume padrão |
| `FABRICANTE` | VARCHAR2 | Fabricante (usado em typeahead distinct no Rastreio) |

---

## 3. Tabela CODNAT_POR_TOP

Constante exportada em `oracle_conn.py` — fonte única para CODNAT por TOP de venda.

```python
CODNAT_POR_TOP = {
    30: 20010200,   # Avaria interna (DESCRNAT "AVARIA") — Mai/2026
    34: 10010100,   # Pedido de Venda
    35: 10010100,   # Venda com NFe
    36: 10020100,   # Devolução de venda (DESCRNAT "DEVOLUCAO DE VENDA") — Mai/2026
    37: 10010200,   # Venda sem NFe
}
```

### TOPs do projeto (referência completa)

| TOP | CODNAT | Descrição | Origem | Observações |
|---|---|---|---|---|
| 10 | 30070200 | Entrada de Combustível | Compra de combustível pelo IAgro ou Sankhya (Mai/2026) | Itens com CODAGREGACAO=NULL e CODGRUPOPROD=200400 (COMBUSTÍVEIS). Alimenta saldo da view `ANDRE_IAGRO_SALDO_COMBUSTIVEL` |
| 11 | — | Compra (Entrada) | Recebimento de fornecedor | Gera lote com `CODAGREGACAO = NUNOTAS{SEQ}D{YYMMDD}` |
| 13 | — | Vale de Compra (Comercial) | Faturamento de vales | Gera financeiro em TGFFIN |
| 26 | — | Classificação confirmada | **EXCLUSIVA da Classificação (hortifrúti)** | CODAGREGACAO≠NULL + grupo hortifrúti → discriminador `CLASSIFICADO` no WMS. **Antes de Mai/2026 (2026-05-13) também era usada pelo módulo Combustível — migrado pra TOP 53.** |
| 30 | 20010200 | Avaria interna (perda) | Módulo Venda IAgro (Mai/2026) | STATUSNOTA='L' direto. CODAGREGACAO obrigatório (rastreabilidade). Perna D no WMS |
| 34 | 10010100 | Pedido de Venda (em aberto) | Módulo Venda | TOP base para edição/atribuição de lote |
| 35 | 10010100 | Venda com NFe | Faturamento da Venda | Emissão real de NFe é tarefa do Sankhya |
| 36 | 10020100 | Devolução de venda | Módulo Venda IAgro (Mai/2026) | STATUSNOTA='A' em aberto. TGFVAR populada no INSERT. Operador confirma no Sankhya |
| 37 | 10010200 | Venda sem NFe | Faturamento da Venda | TOP alternativo para venda s/ documento fiscal |
| **53** | 30070200 | **Requisição interna (combustível)** | Módulo Combustível IAgro (Mai/2026 — 2026-05-13) | `TIPMOV='Q'`. CODAGREGACAO=NULL + CODGRUPOPROD=200400 + linha em `AD_REQUISICAO_COMBUSTIVEL`. **Tipos**: INTERNA_FROTA / INTERNA_MAQUINARIO / EXTERNA_FRETE (em aberto, STATUSNOTA=NULL) ou EXTERNA_POSTO (STATUSNOTA='L' direto + TGFFIN despesa contra posto). View `ANDRE_IAGRO_SALDO_COMBUSTIVEL` filtra `NOT EXISTS EXTERNA_POSTO`. |
| 99 | 10010400 | (a confirmar) | — | Não usado no MVP |

---

## 4. STATUSNOTA — Convenções

| Status | Significado | Quem usa |
|---|---|---|
| _(em aberto, vazio ou outro)_ | Pedido criado, não faturado | TGFCAB de TOP 34 |
| `L` | Liberada / confirmada / faturada | TOP 35, 37, 30 (após confirmação) |
| `E` | Excluída | Qualquer TOP marcado como excluído |

### Filtros usados no WMS

- **Entradas (TOP 11/13/26):** `STATUSNOTA <> 'E'` (não excluída)
- **Baixas (TOP 35/37/30):** `STATUSNOTA = 'L'` (liberada/confirmada)
- **Reservas (TOP 34):** `STATUSNOTA NOT IN ('L', 'E')` (em aberto)

### Listagem de pedidos no Rastreio

A listagem **mostra também faturados** (filtra apenas `<> 'E'`). A **atribuição** valida e bloqueia faturado.

---

## 5. View `SANKHYA.ANDRE_IAGRO_SALDO_LOTE`

View dedicada do WMS, **não toca `TGFEST` nativa do Sankhya**. Toda aritmética é derivada de `TGFITE` + `TGFCAB`.

**DDL:** [`sankhya_integration/sql/ANDRE_IAGRO_SALDO_LOTE.sql`](sankhya_integration/sql/ANDRE_IAGRO_SALDO_LOTE.sql)
**Queries de teste:** [`ANDRE_IAGRO_SALDO_LOTE_teste.sql`](sankhya_integration/sql/ANDRE_IAGRO_SALDO_LOTE_teste.sql)

### Estrutura de pernas

| # | STATUS_LINHA | Fonte | Vendável? |
|---|---|---|:-:|
| A | `CLASSIFICADO` | TOP 26 (lotes que têm classificação confirmada) | ✅ |
| B | `NAO_CLASSIFICAVEL` | TOP 13 (lotes que NÃO têm TOP 26) | ✅ |
| C | `AGUARDANDO_CLASSIFICACAO` | TOP 11 com `GERAPRODUCAO='S'` ainda sem TOP 26 (qtd pendente = `QTDNEG − AD_QTDAVARIA − Σ TOP 26`) | ❌ |
| D | `AVARIA_INTERNA` | TOP 30 (perda no estoque) | ❌ |
| E | `AVARIA_FORNECEDOR` | `AD_QTDAVARIA` da TOP 11 (descarte da classificação repassado ao fornecedor) | ❌ |
| F | `DEVOLVIDO` | TOP 36 STATUSNOTA='L' com `CODAGREGACAO` preservado (cliente devolveu — Mai/2026) | ❌ (informativo; SOMA ao saldo das pernas A/B) |

### Fórmula de saldo

```
QTD_DISPONIVEL = ENTRADA
               + Σ TOP 36 confirmadas (devolvido — Mai/2026)
               − BAIXA_VENDA (ver detalhe abaixo)
               − Σ TOP 30 confirmadas
               − Σ TOP 34 abertas (STATUSNOTA NOT IN ('L','E'))
```

**BAIXA_VENDA (Mai/2026 — rastreabilidade no pedido):** UNIÃO deduplicada de duas fontes:
1. **TOP 34 STATUSNOTA='L'** com `CODAGREGACAO` (verdade IAgro — pedido faturado vinculado pela tela)
2. **TOP 35/37 STATUSNOTA='L'** com `CODAGREGACAO`, **somente quando** o item origem via TGFVAR não tem lote no pedido (fallback pra vínculos feitos direto pelo Sankhya nativo, sem duplicar)

### Decisões de agregação

- **Multi-empresa não restritiva:** as CTEs de baixa/reserva agregam por `(CODPROD, CODAGREGACAO)` **globalmente**, sem `CODEMP`. Permite vincular lote da empresa A em pedido da empresa B sem o saldo "ficar órfão" entre empresas.
- **Discriminador A vs B:** existência de TOP 26 confirmada.

### Paginação

Compatível com Oracle 11g via `ROW_NUMBER() OVER ... BETWEEN`. **NÃO usar** `OFFSET ... FETCH NEXT` (Oracle 12c+) — explode com `ORA-00933` no ambiente atual.

### Funções que consomem a view

| Função em `oracle_conn.py` | Propósito |
|---|---|
| `consultar_saldo_lote_disponivel(filtros, limite, offset)` | Lista lotes paginada — aceita `q`, `codprod`, `codprods` (lista IN), `codagregacao`, `fabricante`, `tipo` (`classificavel\|nao_classificavel\|todos`), `desde_dias` |
| `consultar_pedidos_abertos_para_atribuicao(filtros, limite, offset)` | TOP 34 paginado por cabeçalho, com LEFT JOIN agrupado na TOP 11 trazendo origem do lote |

---

## 5.5 Tabela `TGFVAR` — vínculo nativo Sankhya entre notas geradas

**Descoberta em Mai/2026 (2026-05-09)** durante design da feature "vincular lote em nota faturada". Tabela nativa do Sankhya que registra atendimento de pedido — não está em nenhum lugar do código IAgro, mas é a **única fonte de vínculo confiável** entre TOP 34 (pedido) e TOP 35/37 (nota), porque Sankhya popula automaticamente via trigger interna no faturamento.

### Estrutura

| Coluna | Tipo | Função |
|---|---|---|
| `NUNOTA` | NUMBER | NUNOTA da nota gerada (destino) |
| `SEQUENCIA` | NUMBER | SEQ do item na nota gerada |
| `NUNOTAORIG` | NUMBER | NUNOTA da nota origem (pedido) |
| `SEQUENCIAORIG` | NUMBER | SEQ do item na nota origem |
| `QTDATENDIDA` | FLOAT | Quantidade transferida do pedido pra nota |
| `STATUSNOTA` | VARCHAR2(1) | Status replicado |
| `CUSATEND`, `ORDEMPROD`, `FIXACAO`, etc. | — | Campos auxiliares (não usados pelo IAgro) |

### Uso real (Mai/2026, ~211k linhas no banco da Agromil)

| TOP destino | TOP origem | Qtd linhas | Fluxo |
|---|---|---|---|
| 35 | 34 | 185.221 | NFe ← Pedido de Venda |
| 36 | 35 | 16.623 | Devolução ← NFe |
| 13 | 11 | 9.376 | Vale ← Compra |
| 37 | 34 | 75 | Venda s/NFe ← Pedido |
| 36 | 37 | 6 | Devolução ← Venda s/NFe |

### Características importantes

- **Granularidade por item**: uma linha por par `(SEQUENCIA_destino, SEQUENCIAORIG_origem)`. Permite N:1 e 1:N (1 pedido vira N notas, ou N compras viram 1 vale)
- **SEQUENCIA pode mudar** entre pedido e nota (Sankhya re-ordena, geralmente por CODPROD). Não dá pra usar SEQUENCIA como chave sem passar por TGFVAR
- **Populada via trigger Sankhya** — IAgro nunca escreveu nela. Apenas leitura
- **CUSATEND** parece ser custo atendido; **ORDEMPROD** ordem de produção/separação — fora do escopo IAgro hoje

### Mecânica complementar: `AD_NUMPEDIDOORIG` (campo customizado da Agromil)

Existe em **TGFCAB e TGFITE**. Convenção da Agromil para rastreabilidade da "nota raiz via lote", usada pelos módulos Entrada/Classificação/Comercial (TOP 11/26/13):

- **Auto-referência no INSERT**: `AD_NUMPEDIDOORIG = NUNOTA próprio` (default em [`inserir_cabecalho_nota_banco`](../sankhya_integration/services/oracle_conn.py))
- **Auto-cura no UPDATE**: itens TGFITE buscam o `MIN(AD_NUMPEDIDOORIG)` de outros itens com mesmo `CODAGREGACAO` (lote) e propagam ao cabeçalho/item alvo. Permite TOP 26 herdar origem do TOP 11 do mesmo lote
- **Não cobre venda/NFe (Mai/2026)**: 100% dos pedidos TOP 34 dos últimos 30 dias com `AD_NUMPEDIDOORIG = NULL` (todos vêm do Sankhya direto, não IAgro). Quando IAgro for a fonte de criação, popular naturalmente

### Como o IAgro usa TGFVAR (Mai/2026 — final)

**Apenas leitura, e apenas em 2 lugares específicos:**

1. **`consultar_pedidos_abertos_para_atribuicao`** — subquery escalar pra trazer NUMNOTA + NUNOTA da nota correlata (TOP 35/37 STATUSNOTA<>'E') de cada pedido TOP 34 STATUSNOTA='L'. Frontend usa pra exibir badge `FATURADO Nota Y`.
2. **View `ANDRE_IAGRO_SALDO_LOTE`** — perna `baixas_venda` consulta TGFVAR no `NOT EXISTS` que desempata baixa via TOP 34 (verdade IAgro) vs baixa via TOP 35/37 (fallback Sankhya nativo), evitando duplicação.

**O IAgro nunca escreve em TGFVAR.** A análise das 6 triggers `TRG_*_TGFVAR` (em 2026-05-11) confirmou cascata em TGMTRA (movimentação financeira/meta/orçamento), TGFITE.QTDENTREGUE, TGFCFM (cupons de fidelidade) e bloqueios por TGABDLC — risco grande demais sem ambiente de homologação Sankhya pra testar. A rastreabilidade do IAgro vive no TGFITE do pedido (TOP 34), e a nota não é tocada. Ver [`.claude/gotchas.md`](gotchas.md) → "TGFVAR é populada via trigger Sankhya" pra detalhes.

---

## 6. Funções-chave de `oracle_conn.py`

### Conexão e transação

| Função | Tipo | Descrição |
|---|---|---|
| `obter_conexao_oracle()` | Context manager | Gerencia commit/rollback automaticamente |
| `is_write_enabled()` | Flag | Controla se INSERT/UPDATE/DELETE estão habilitados |
| `humanizar_erro_oracle(exc_or_msg)` | Helper | Traduz `ORA-XXXXX` em mensagem amigável (ver §7) |

### Cabeçalho de notas

| Função | Operação |
|---|---|
| `inserir_cabecalho_nota_banco` | INSERT em TGFCAB. Aceita `CODTIPVENDA` condicionalmente; consulta `DHALTER` mais recente da TGFTPV para gravar `DHTIPVENDA` (exigência do trigger) |
| `atualizar_cabecalho_nota_banco` | UPDATE genérico. **Tem auto-cura de `AD_NUMPEDIDOORIG`** específica da Entrada/Classificação — não reutilizar em Venda/Rastreio |
| `atualizar_cabecalho_venda_banco` | UPDATE dedicado da Venda (sem auto-cura de AD_NUMPEDIDOORIG) |
| `recalcular_totais_nota_banco` | Recalcula `VLRNOTA` e `QTDVOL`. **Se nota fica sem itens, deleta o cabeçalho automaticamente** |

### Itens

| Função | Operação |
|---|---|
| `inserir_item_nota_banco(..., gerar_lote_auto=True)` | INSERT em TGFITE. Default gera lote `NUNOTAS{SEQ}D{YYMMDD}` (Entrada). Venda passa `False` — lote fica `NULL` |
| `atualizar_item_nota_banco` | UPDATE de item. Aceita `CODAGREGACAO` no dict, mas **a atribuição de lote do Rastreio NÃO usa** essa função (evita auto-cura de AD_NUMPEDIDOORIG) |

### Venda

| Função | Operação |
|---|---|
| `consultar_empresas_oracle` | Typeahead TSIEMP |
| `consultar_tipos_negociacao_oracle` | Typeahead TGFTPV |
| `consultar_cabecalho_venda_oracle` | SELECT cabeçalho + JOINs (TSIEMP, TGFPAR, TGFTPV) |
| `listar_vendas_paginado(filtros, limite, offset)` | Listagem do portal de Venda. WHERE inclui `CODTIPOPER IN (30, 34, 35, 36, 37)` (Mai/2026) |
| `faturar_pedido_venda_banco(nunota, nova_top, codusu_logado)` | Faturamento atômico TOP 34 → 35/37 com `SELECT FOR UPDATE`, validação de itens com lote, geração de `NUMNOTA` por empresa |

### Avaria + Devolução + Histórico de Lote (Mai/2026)

| Função | Operação |
|---|---|
| `criar_avaria_top30_banco(dados, codusu)` | **Manual** (toolbar Venda). TGFCAB TOP 30 STATUSNOTA='L' direto + TGFITE com `CODAGREGACAO` obrigatório. Valida saldo via view. Reusa `inserir_cabecalho_nota_banco` + `inserir_item_nota_banco` |
| `upsert_avaria_top30_lote(nunota_origem, codprod, codagregacao, qtd_avaria_unidade, codusu, nomeusu)` **(Mai/2026 — 2026-05-20)** | **Automática** ao faturar Comercial com toggle Absorver. Herda `CODTIPVENDA` da TOP 11 origem (trigger `TRG_INC_TGFCAB` exige); DELETE+INSERT idempotente; VLRUNIT/VLRTOT da TOP 30 = `qtd_avaria × (VLRUNIT_kg_vale × peso)` documentando custo |
| `remover_avaria_top30_lote(nunota_origem, codprod, codagregacao, codusu, nomeusu)` **(Mai/2026 — 2026-05-20)** | Idempotente. DELETE TGFITE; apaga TGFCAB se ficou sem itens |
| `reconciliar_avaria_top30_no_faturamento(nunota_origem, lotes_absorver, codusu, nomeusu)` **(Mai/2026 — 2026-05-20)** | Orquestrador. Pra cada item TOP 11 não-classif. com avaria > 0: sincroniza vale TOP 13 via B11 (qtd cheia se Absorver, líquida se Descontar) + cria/remove TOP 30 |
| `atualizar_avaria_fornecedor_naoclass(nunota, sequencia, qtd, codusu, nomeusu)` **(Mai/2026)** | UPDATE em `TGFITE.AD_QTDAVARIA` da TOP 11 filtrando `GERAPRODUCAO <> 'S'`. **B10**: trava se vale TOP 13 tem TGFFIN |
| `alternar_modo_avaria_vale_lote(nunota_origem, codprod, codagregacao, absorver, codusu, nomeusu)` **(Mai/2026 — 2026-05-20)** | B12. Endpoint dedicado pro toggle do modal. Lê VLRUNIT atual do vale e reaplica `upsert_preco_in_natura_modalFaturamento` com flag — recalcula QTDNEG/VLRTOT do vale TOP 13 sem precisar editar preço |
| `consultar_avarias_fornecedor_da_nota(nunota)` | Aditiva leitura — `{sequencia: AD_QTDAVARIA}` da nota |
| `consultar_avarias_fornecedor_de_pedido(nunota)` | Aditiva leitura — `{codagregacao: {qtd_avaria, fornecedor, ...}}` pro modal Comercial |
| `criar_devolucao_top36_banco(dados, codusu)` | TGFCAB TOP 36 STATUSNOTA='A' + TGFITE par-a-par preservando CODAGREGACAO + **INSERT em TGFVAR** replicando Sankhya nativo. Operador confirma no Sankhya |
| `consultar_nota_para_devolucao(nunota_origem)` | Lê cabeçalho + itens da TOP 35/37 origem com `qtd_ja_devolvida` somada de TGFVAR. Usada pelo modal de devolução |
| `consultar_devolucoes_anteriores_de_nota(nunota_origem)` | Soma TGFVAR.QTDATENDIDA por SEQUENCIAORIG (TOP 36 STATUSNOTA <> 'E'). Trava anti-devolução-excessiva |
| `obter_historico_lote(codagregacao)` | Timeline completa do lote: TOP 11 → 26 → 13 → 34 → 35/37 → 30/36. Lê TGFITE+TGFCAB+TGFPAR. Ordenada por DTNEG ASC |

### Rastreio (WMS)

| Função | Operação |
|---|---|
| `consultar_saldo_lote_disponivel` | Lista lotes da view |
| `consultar_pedidos_abertos_para_atribuicao` | Lista TOP 34 |
| `atribuir_lote_item_pedido(nunota, sequencia, codagregacao, qtd=None)` | UPDATE simples se total, SPLIT (UPDATE qtd reduzida + INSERT nova linha) se parcial. **Lock pessimista** + defesa contra double-binding. Recalcula totais |
| `desvincular_lote_item_pedido(nunota, sequencia)` | `UPDATE TGFITE SET CODAGREGACAO=NULL`. Bloqueia se pedido faturado/excluído |
| `consultar_fabricantes_disponiveis(termo, limite)` | Typeahead `SELECT DISTINCT FABRICANTE` |
| `consultar_vinculos_de_lote(codagregacao)` | Pedidos/vendas (TOP 34/35/37, sem TOP 13) que usam o lote |

---

## 7. Códigos Oracle mapeados em `humanizar_erro_oracle`

| Código | Mensagem amigável (resumo) |
|---|---|
| `ORA-20101` | Tipo de negociação inativo / verificar TGFTPV |
| `ORA-00001` | Registro duplicado |
| `ORA-02291` | Referência inválida (parceiro/produto/empresa não existe) |
| `ORA-02292` | Não é possível excluir — há registros vinculados |
| `ORA-01400` | Campo obrigatório não preenchido |
| `ORA-01438` | Valor numérico fora do tamanho permitido |
| `ORA-01722` | Número inválido |
| `ORA-01861` | Data inválida |
| `ORA-12899` | Texto maior que o limite (mensagem genérica — não vaza nome de coluna) |
| `ORA-00054` | Recurso ocupado por outro usuário |
| `ORA-08177` | Conflito em transação serializável |
| `DPY-1001` | Conexão Oracle perdida |
| `DPY-4011` | Falha de I/O na conexão |

**Fallback:** primeira linha da mensagem original, sem stack trace.

**Regra:** sempre logar a exceção original com `logger.exception` **antes** de humanizar. Caso contrário, suporte fica sem trilha para diagnóstico.

---

## 7.5 Tabelas auxiliares do módulo Importação por E-mail (prefixo `AD_`)

Schema separado das tabelas Sankhya nativas — não interferem em queries existentes do ERP. Detalhes completos em [`.claude/modules/email.md`](modules/email.md).

| Tabela | Função | Migration |
|---|---|---|
| `AD_PEDIDO_EMAIL_RECEBIDO` | Cabeçalho do pré-pedido (1 linha por SUB_ID) — antes de virar TGFCAB | `AD_PEDIDO_EMAIL.sql` (canônico) + `..._SUB_ID.sql` + `..._ORIGEM.sql` |
| `AD_PEDIDO_EMAIL_ITEM` | Itens do pré-pedido (com COD_CLIENTE pra Consinco) | `AD_PEDIDO_EMAIL.sql` + `AD_CLIENTE_PRODUTO_COD.sql` (adiciona COD_CLIENTE) |
| `AD_PRODUTO_ALIAS` | De-para `(descricao_normalizada, codparc?) → CODPROD` | `AD_ALIAS_APRENDIZADO.sql` |
| `AD_PARCEIRO_ALIAS` | De-para `nome_normalizado → CODPARC` | `AD_ALIAS_APRENDIZADO.sql` |
| `AD_CLIENTE_PRODUTO_COD` | De-para `(CODPARC, COD_CLIENTE) → CODPROD` (matching mais forte) | `AD_CLIENTE_PRODUTO_COD.sql` |

**Hierarquia de matching de produto (forte → fraco):**
1. `AD_CLIENTE_PRODUTO_COD` por `(codparc, cod_cliente)` — Etapa 0, score 100
2. `AD_PRODUTO_ALIAS` por descrição normalizada — Etapa 1, score 100
3. Fuzzy (`rapidfuzz.WRatio`) contra TGFPRO completo — Etapa 2, score 75-100

**Schema-resilience:** `oracle_conn.py` tem helper `_existe_coluna(cur, tabela, coluna)` com cache 1× por processo — código roda antes/depois das migrations sem ORA-00904. Reseta no restart do Django/worker.

---

## 7.6 Tabela auxiliar do Rastreio — `AD_VINCULO_PEDIDO_NOTA` (Mai/2026)

Registra vínculos manuais pedido↔nota feitos pelo IAgro quando o Sankhya não populou TGFVAR. Detalhes completos em [`.claude/modules/rastreio.md`](modules/rastreio.md) → "Fluxo unificado de resolução de nota órfã".

**Migration:** `sankhya_integration/sql/AD_VINCULO_PEDIDO_NOTA.sql`

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_VINCULO_PEDIDO_NOTA` |
| `NUNOTA_PEDIDO` | NUMBER UNIQUE | TGFCAB TOP 34 |
| `NUNOTA_NOTA` | NUMBER UNIQUE | TGFCAB TOP 35/37 |
| `ORIGEM` | VARCHAR2(20) CHECK | `VINCULADO` (Leva A) ou `PEDIDO_RETROATIVO` (Leva B) |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM`, `OBSERVACAO` | — | Audit completo |

**Funções service** (`oracle_conn.py`):
- `consultar_candidatos_pedido_para_nota(nunota_nota, limite)` — sugere pedidos pareáveis via heurística rigorosa (mesmo CODPARC + valor exato + data ±1 dia)
- `inserir_vinculo_manual_pedido_nota(nunota_pedido, nunota_nota, codusu, nomeusu)` — Leva A: cria vínculo de pedido pré-existente
- `criar_pedido_retroativo_a_partir_de_nota(nunota_nota, codusu, nomeusu)` — Leva B: cria TGFCAB+TGFITE TOP 34 espelhando a nota
- `resolver_nota_orfa_automatica(nunota_nota, codusu, nomeusu, acao='AUTO')` — fluxo unificado: backend decide entre VINCULAR/CRIAR conforme heurística
- `remover_vinculo_manual_pedido_nota(nunota_pedido, nunota_nota)` — desfaz vínculo (em Leva B também exclui o pedido criado, se nenhum lote foi atribuído)

**Side effects no AD_NUMPEDIDOORIG:** todas as funções de criação/remoção atualizam `TGFCAB.AD_NUMPEDIDOORIG` + `TGFITE.AD_NUMPEDIDOORIG` (todos os itens) da nota:
- Ao vincular/criar: aponta pro `NUNOTA_PEDIDO`
- Ao desfazer: volta pra NULL

**Por que tabela auxiliar e não TGFVAR:** TGFVAR é populada por trigger interna Sankhya (TRG_INC_TGFVAR), com cascata em TGMTRA (movimentação financeira/meta-orçamento) e TGFITE.QTDENTREGUE. INSERT manual é risco grande sem ambiente de homologação — ver gotchas.md "TGFVAR é populada via trigger Sankhya". A tabela auxiliar IAgro vive paralela e é lida em UNION com TGFVAR na consulta principal.

---

## 7.7 Módulo Controle de Combustível — TGFVEI, view + tabela auxiliar (Mai/2026)

Pacote de schema do módulo Combustível. Detalhes completos em [`.claude/modules/combustivel.md`](modules/combustivel.md).

### Cadastro nativo Sankhya — `TGFVEI`

Tabela de veículos do Sankhya — reusada sem alteração. Campos relevantes pro IAgro:

| Coluna | Tipo | Função |
|---|---|---|
| `CODVEICULO` | NUMBER PK | Identificador único |
| `PLACA` | VARCHAR2(10) | Placa visível |
| `MARCAMODELO` | VARCHAR2(30) | Descrição humana ("FIAT STRADA", "MERCEDS 2544") |
| `ESPECIETIPO` | VARCHAR2(22) | Categoria ("CAVALO", "CARGA CAMINHAO") |
| `PROPRIO` | VARCHAR2(1) | **`S` = frota própria + maquinário; `N` = veículo de terceiro** |
| `COMBUSTIVEL` | VARCHAR2(1) | Combustível típico (D=diesel, G=gasolina, F=flex) |
| `CODPARC` | NUMBER NOT NULL | Parceiro proprietário (empresa Agromil em próprios, freteiro em terceiros) |
| `CODCENCUS` | NUMBER NULL | Centro de resultado default do veículo |
| `ATIVO` | VARCHAR2(1) NOT NULL | S/N |

Em produção (Mai/2026): 32 veículos cadastrados, todos `PROPRIO='S'`. Terceiros serão cadastrados conforme aparecem.

### Tabela `TGFGRU` (grupos de produto)

| Coluna | Tipo | Função |
|---|---|---|
| `CODGRUPOPROD` | NUMBER PK | Identificador do grupo |
| `DESCRGRUPOPROD` | VARCHAR2(30) | Nome do grupo |
| `CODGRUPAI` | NUMBER | Hierarquia |

Grupo de combustível: **`CODGRUPOPROD = 200400` (`DESCRGRUPOPROD = 'COMBUSTÍVEIS'`)** — pai `200000 (MEF)`. Validado Mai/2026 em produção: 4 produtos (Diesel S10 392, Diesel S500 1373, Gasolina 391, Óleo de Motor 550), CODVOL='LT'.

⚠ **Não confundir** com `TSIGRU.CODGRUPO=11` (IAGRO_FROTA), que é o grupo de **usuário** referenciado em `decorators.py`.

### View dedicada `ANDRE_IAGRO_SALDO_COMBUSTIVEL`

DDL em [`sankhya_integration/sql/ANDRE_IAGRO_SALDO_COMBUSTIVEL.sql`](../sankhya_integration/sql/ANDRE_IAGRO_SALDO_COMBUSTIVEL.sql).

**Fórmula** (Mai/2026 — estoque único, sem segregação por CODEMP):
```
QTD_DISPONIVEL = GREATEST( Σ TOP 10 entradas (STATUSNOTA <> 'E')
                          − Σ TOP 26 saídas    (STATUSNOTA <> 'E'),  0 )
WHERE pr.CODGRUPOPROD = 200400
agrupado por CODPROD
```

**Razão**: combustível é despesa operacional compartilhada entre as empresas do grupo (Agromil/Semear/etc) — não faz sentido segregar estoque por CODEMP. A CODEMP da TGFCAB TOP 26 da requisição é apenas metadata escritural (herdada da última entrada do produto).

**Segregação total versus Classificação**: a Classificação também grava TOP 26, mas seus itens têm `CODAGREGACAO IS NOT NULL` + produtos do grupo hortifrúti. Combustível grava `CODAGREGACAO IS NULL` + `CODGRUPOPROD=200400`. View `ANDRE_IAGRO_SALDO_LOTE` exige `IS NOT NULL` → zero interferência.

### Tabela auxiliar `AD_REQUISICAO_COMBUSTIVEL` (aplicada Mai/2026, ampliada 2026-05-13)

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_REQUISICAO_COMBUSTIVEL` |
| `NUNOTA` | NUMBER UNIQUE NOT NULL | FK lógica TGFCAB TOP **53** (era TOP 26 até 2026-05-13) |
| `TIPO` | VARCHAR2(20) CHECK | `INTERNA_FROTA` \| `INTERNA_MAQUINARIO` \| `EXTERNA_FRETE` \| **`EXTERNA_POSTO`** (B7 Mai/2026) |
| `CATEGORIA` | VARCHAR2(20) DEFAULT 'COMBUSTIVEL' NOT NULL CHECK | `COMBUSTIVEL` \| `MANUTENCAO` (preparado pro módulo futuro de manutenção da frota) |
| `CODVEICULO` | NUMBER NOT NULL | FK lógica TGFVEI |
| `CODPARC` | NUMBER NULL | **Obrigatório se TIPO='EXTERNA_POSTO'** — CODPARC do posto/fornecedor (Allianz, Semear, Agromil) |
| `NUFIN_GERADO` | NUMBER NULL | Audit do NUFIN criado (só em EXTERNA_POSTO) |
| `HODOMETRO_KM` | NUMBER(15,2) | km do veículo (obrigatório em INTERNA_FROTA + EXTERNA_POSTO; opcional em INTERNA_MAQUINARIO; NULL em EXTERNA_FRETE) |
| `HORIMETRO_H` | NUMBER(15,2) | h da bomba (mesma regra de obrigatoriedade) |
| `DOC_FRETE_REF` | VARCHAR2(50) | NF/boleto. Obrigatório se TIPO=EXTERNA_FRETE; opcional em EXTERNA_POSTO |
| `OBSERVACAO` | VARCHAR2(500) | Texto livre |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM` | — | Audit |

**Constraints** (Oracle 11g — nomes ≤30 chars):
- `CK_AD_REQ_COMBUST_TIPO` — `TIPO IN ('INTERNA_FROTA','INTERNA_MAQUINARIO','EXTERNA_FRETE','EXTERNA_POSTO')`
- `CK_AD_REQ_COMBUST_EXTPOSTO` — `TIPO <> 'EXTERNA_POSTO' OR CODPARC IS NOT NULL`
- `CK_AD_REQ_COMBUST_CATEG` — `CATEGORIA IN ('COMBUSTIVEL','MANUTENCAO')`

**Histórico de migrations**:
- B1 (Mai/2026 inicial): DDL original com `MEDIDOR_ATUAL` + `MEDIDOR_TIPO`.
- **B4 (Mai/2026)**: ALTER trocou pra 2 colunas dedicadas (`HODOMETRO_KM` + `HORIMETRO_H`) — frota própria precisa AMBOS simultaneamente.
- **B7 (Mai/2026, 2026-05-13)** [[`AD_REQUISICAO_COMBUSTIVEL_MIGRATION_EXTERNO.sql`](../sankhya_integration/sql/AD_REQUISICAO_COMBUSTIVEL_MIGRATION_EXTERNO.sql)]: ADD `CATEGORIA`+`CODPARC`+`NUFIN_GERADO`, CHECK ampliado pra `EXTERNA_POSTO`. Suporta abastecimento externo (posto) sem desconto do tanque interno.

### Constantes Python de configuração (em `oracle_conn.py`)

```python
CODGRUPOPROD_COMBUSTIVEL = 200400   # TGFGRU.CODGRUPOPROD do grupo COMBUSTÍVEIS

# Capacidade física dos tanques. Filtra também quais produtos do grupo 200400
# aparecem no card "Estoque" do frontend.
CAPACIDADE_TANQUE = {
    392:  10000.0,   # DIESEL S10
    1373: 5000.0,    # DIESEL S500
    1374: 1000.0,    # ARLA 32
}

# Saldo pré-existente nos tanques antes do IAgro registrar TOP 10.
# Somado em Python ao saldo da view (NÃO usar QTD_DISPONIVEL da view direto —
# GREATEST(0) corrompe quando entrada_view=0 + saída>0; ver gotchas.md).
SALDO_INICIAL_TANQUE = {
    392:  896.0,   # DIESEL S10  — ajustado 2026-05-15 após balanço físico (era 300.0)
    1373: 3204.0,  # DIESEL S500 — ajustado 2026-05-15 após balanço físico (era 3150.0)
    1374: 300.0,   # ARLA 32
}

# Formato visual do tanque (renderização SVG no frontend)
FORMATO_TANQUE = {
    392:  'CILINDRO_HORIZONTAL',
    1373: 'CILINDRO_HORIZONTAL',
    1374: 'CAIXA_QUADRADA',     # ARLA 32 — IBC industrial
}

# Ordem visual dos tanques no card de Estoque (esquerda → direita)
ORDEM_TANQUE = {
    1374: 1,   # ARLA 32      (1ª)
    1373: 2,   # DIESEL S500  (2ª)
    392:  3,   # DIESEL S10   (3ª)
}
```

### Funções service (`oracle_conn.py`)

| Função | Operação | Cat |
|---|---|:-:|
| `consultar_saldo_combustivel(filtros)` | SELECT view + TGFPRO; calcula disponível em Python (não usa GREATEST da view) | A |
| `consultar_veiculos_disponiveis(termo, tipo, ativo, limite)` | SELECT TGFVEI + TGFPAR | A |
| `consultar_produtos_combustivel(termo, limite)` | SELECT TGFPRO CODGRUPOPROD=200400 | A |
| `consultar_consumo_por_veiculo(codveiculo, date_start, date_end)` | Relatório: SELECT abastecimentos do veículo no período + calcula km/L e L/h entre consecutivos | A |
| `listar_movimentacoes_combustivel(filtros, limite, offset)` | UNION (TOP 10 c/ CODGRUPOPROD=200400) ∪ (TOP 26 c/ AD_REQ); **JOIN com TGFITE — 1 linha por item** | A |
| `listar_requisicoes_combustivel(filtros, limite, offset)` | SELECT só saídas TOP 26 (legado) | A |
| `obter_requisicao_combustivel(nunota)` | SELECT detalhe (cab + itens + req) | A |
| `criar_requisicao_combustivel_banco(dados, codusu, nomeusu)` | INSERT TGFCAB TOP 26 + TGFITE + AD_REQUISICAO_COMBUSTIVEL (STATUSNOTA=NULL em aberto) | **B2** (aplicada) |
| `editar_requisicao_combustivel_banco(nunota, dados, codusu, nomeusu)` | UPDATE atômico TGFCAB + TGFITE + AD_REQ; re-valida saldo "devolvendo" qtd antiga | **B5** (aplicada) |
| `excluir_requisicao_combustivel_banco(nunota, motivo, codusu, nomeusu)` | **DELETE físico** AD_REQ + TGFITE + TGFCAB (UPDATE STATUSNOTA='E' bloqueado pelo trigger Sankhya) | **B6** (aplicada) |
| `criar_entrada_combustivel_banco(dados, codusu, nomeusu)` | INSERT TGFCAB TOP 10 + TGFITE + TGFFIN; UPDATE STATUSNOTA='L'. Padrão à vista (DHBAIXA=DTNEG). Defaults TGFFIN modelo NUFIN=438989: CODBCO=70, CODCTABCOINT=1, CODTIPTIT=2, CODTIPOPER=1, ORIGEM='F' | **B3** (aplicada) |

---

## 7.8 Módulo Controle de Caixas — `AD_COLETA_CAIXAS` + `AD_PRODUTO_CAIXA` (Mai/2026 — 2026-05-18)

Controle de vasilhame retornável (caixa plástica) circulando entre Agromil e clientes. Saídas derivadas em runtime (sem persistência); coletas/quebras/perdas manuais; tipo de caixa por produto (default PLASTICA, exceções cadastradas).

### Tabela `AD_COLETA_CAIXAS`

DDL em [`sankhya_integration/sql/AD_COLETA_CAIXAS.sql`](../sankhya_integration/sql/AD_COLETA_CAIXAS.sql).

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_COLETA_CAIXAS` |
| `CODPARC` | NUMBER NOT NULL | FK lógica TGFPAR — cliente que devolveu/perdeu/quebrou |
| `QTD_CAIXAS` | NUMBER NOT NULL | Qtd inteira positiva (CHECK > 0) |
| `DATA_COLETA` | DATE NOT NULL | Data do evento |
| `MOTIVO` | VARCHAR2(20) NOT NULL CHECK | `COLETA` / `QUEBRA` / `PERDA` / `AJUSTE_SALDO` |
| `OBSERVACAO` | VARCHAR2(500) | Texto livre opcional (recomendado em AJUSTE_SALDO) |
| `ESTORNADO` | CHAR(1) DEFAULT 'N' | Soft-delete pra preservar audit |
| `ESTORNADO_EM`, `ESTORNADO_POR`, `MOTIVO_ESTORNO` | — | Audit do estorno |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM` | — | Audit da criação |

Índices: `IDX_AD_COLETA_CODPARC(CODPARC, ESTORNADO)` + `IDX_AD_COLETA_DATA(DATA_COLETA DESC)`.

### Tabela `AD_PRODUTO_CAIXA`

DDL em [`sankhya_integration/sql/AD_PRODUTO_CAIXA.sql`](../sankhya_integration/sql/AD_PRODUTO_CAIXA.sql).

| Coluna | Tipo | Função |
|---|---|---|
| `CODPROD` | NUMBER PK | FK lógica TGFPRO |
| `TIPO_CAIXA` | VARCHAR2(20) CHECK | `PLASTICA` (retornável) / `PAPELAO` (descartável) |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM`, `ATUALIZADO_EM`, `ATUALIZADO_POR` | — | Audit |

**Default**: produto SEM linha = `PLASTICA`. Operador cadastra só as exceções de papelão (mudas, embalagens pequenas).

### Fórmula de saldo (calculada em runtime, não persistida)

```
saldo_cliente = Σ caixas_enviadas (TOP 35/37 'L')
              − Σ caixas_devolvidas (TOP 36 'L')
              − Σ AD_COLETA_CAIXAS (motivo IN COLETA/QUEBRA/PERDA, ESTORNADO='N')
              + Σ AD_COLETA_CAIXAS (motivo = AJUSTE_SALDO, ESTORNADO='N')   ← com sinal natural (pos soma, neg desconta)
```

Onde `caixas` por TGFITE = `CEIL(QTDNEG / TGFITE.PESO)` quando `PESO > 0`. Descoberto Mai/2026 (2026-05-18) que `CODVOL='CX'` na Agromil NÃO significa "QTDNEG é nº de caixas" — QTDNEG está sempre em kg, mesmo em vendas marcadas CX. Vendas sem PESO populado (legadas, faturadas direto no Sankhya sem passar pelo Rastreio) ficam **fora do cálculo automático**; operador usa `AJUSTE_SALDO` pra clientes importantes (Assaí/Sendas) cujo saldo precisa ser controlado. Conforme IAgro vira fluxo único, novas vendas trazem PESO real (gravado no modal de vínculo do Rastreio) e saldo passa a funcionar naturalmente. Filtro de plástica: `NOT EXISTS (SELECT 1 FROM AD_PRODUTO_CAIXA WHERE CODPROD=i.CODPROD AND TIPO_CAIXA='PAPELAO')`.

### Funções service (`oracle_conn.py`)

| Função | Operação | Cat |
|---|---|:-:|
| `consultar_saldo_caixas(filtros)` | Saldo agregado por CODPARC. Filtros: `q`, `apenas_saldo_positivo`, `codparc`. Schema-resilient via `_existe_coluna` | A |
| `obter_timeline_caixas(codparc, dias)` | Timeline cronológica DESC (saídas + devoluções + coletas) | A |
| `listar_coletas_caixas(filtros, limite, offset)` | Paginação ROW_NUMBER de AD_COLETA_CAIXAS + JOIN TGFPAR | A |
| `listar_produtos_caixa(tipo?)` | Lista AD_PRODUTO_CAIXA + JOIN TGFPRO | A |
| `criar_coleta_caixas_banco` | INSERT em AD_COLETA_CAIXAS + audit | **B1** (pendente) |
| `estornar_coleta_caixas_banco` | UPDATE ESTORNADO='S' + motivo (não DELETE) | **B2** (pendente) |
| `upsert_produto_caixa_banco` | INSERT/UPDATE em AD_PRODUTO_CAIXA | **B3** (pendente) |

---

## 7.9 Tabela de Preços + Promoções — TGFNTA, TGFTAB, TGFEXC + AD_PROMOCAO + AD_ITEM_PRECO_ORIGEM (Mai/2026 — 2026-05-20/21)

Cadastro completo de **resolução de preço por cliente** + **promoções por (Tabela × Produto)** com flexibilidade de escopo.

### Tabelas Sankhya nativas envolvidas (LEITURA APENAS)

| Tabela | Função |
|---|---|
| `TGFNTA` | Mestre nominal — `CODTAB` (PK), `NOMETAB`, `OBS`, `ATIVO` (descoberta Mai/2026 — 2026-05-21) |
| `TGFTAB` | Versionamento — `NUTAB` (PK), `CODTAB`, `DTVIGOR`, `PERCENTUAL` |
| `TGFEXC` | Preço operacional — `NUTAB`, `CODPROD`, `VLRVENDA`, `TIPO='V'` |
| `TGFPAR.CODTAB` | Liga cliente ao grupo |

**Cascata de resolução:**
```
TGFPAR.CODTAB → TGFNTA.NOMETAB (label) + TGFTAB[MAX(DTVIGOR<=hoje)].NUTAB → TGFEXC[NUTAB,CODPROD].VLRVENDA
```

Detalhes completos em `.claude/tabela_precos_sankhya.md`.

### `AD_PROMOCAO` (auxiliar IAgro — escopo flexível Mai/2026)

DDL em [`AD_PROMOCAO.sql`](../sankhya_integration/sql/AD_PROMOCAO.sql).

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_PROMOCAO` |
| `CODPROD` | NUMBER NOT NULL | FK lógica TGFPRO |
| `CODTAB` | NUMBER NULL | Quando preenchido, afeta TODOS os TGFPAR com esse CODTAB |
| `CODPARC` | NUMBER NULL | Quando preenchido, afeta só 1 cliente |
| `VLRPROMO` | NUMBER(15,4) NOT NULL CHECK > 0 | Preço promocional |
| `DT_INICIO`, `DT_FIM` | DATE NOT NULL CHECK fim >= inicio | Vigência |
| `ATIVO` | CHAR(1) DEFAULT 'S' CHECK in (S,N) | Liga/desliga sem perder histórico |
| `OBSERVACAO`, `CODUSU`, `NOMEUSU`, `CRIADO_EM` | — | Audit |
| `CONSTRAINT CK_AD_PROMO_ESCOPO` | CHECK XOR | Exatamente 1 entre CODTAB/CODPARC |

Índices: `IDX_AD_PROMO_VIGENTE (CODPARC, CODPROD, ATIVO, DT_INICIO, DT_FIM)` + `IDX_AD_PROMO_CODTAB (CODTAB, CODPROD, ATIVO, DT_INICIO, DT_FIM)`.

### `AD_ITEM_PRECO_ORIGEM` (audit por item)

DDL em [`AD_ITEM_PRECO_ORIGEM.sql`](../sankhya_integration/sql/AD_ITEM_PRECO_ORIGEM.sql).

| Coluna | Tipo | Função |
|---|---|---|
| `NUNOTA`, `SEQUENCIA` | NUMBER NOT NULL (PK composto) | TGFITE do item |
| `ORIGEM` | VARCHAR2(20) NOT NULL CHECK in (TABELA, PROMOCAO, MANUAL) | De onde veio o VLRUNIT |
| `NUTAB` | NUMBER NULL | Quando ORIGEM='TABELA' |
| `PROMOCAO_ID` | NUMBER NULL | FK lógica AD_PROMOCAO quando ORIGEM='PROMOCAO' |
| `OBSERVACAO` | VARCHAR2(500) NULL | **Obrigatória quando ORIGEM='MANUAL'** (validado no service) |
| `CODUSU`, `REGISTRADO_EM` | — | Audit |

### Funções service (em `oracle_conn.py`)

| Função | Cat | Operação |
|---|---|---|
| `consultar_preco_tabela(codparc, codprod, dtneg=None)` | A | Resolve preço via TGFPAR.CODTAB → TGFTAB → TGFEXC. Já validado contra Oracle (smoke Mai/2026) |
| `consultar_promocoes_vigentes(codparc, codprod, dtneg=None)` | A | Promoções vigentes (CODPARC direto OR CODTAB do parceiro) |
| `listar_tabelas_grupos(incluir_inativas=False)` | A | TODAS as TGFNTA + nome + nutab vigente + clientes (LEFT JOIN, ordena por nome) |
| `listar_precos_da_tabela(codtab, filtros)` | A | TGFEXC[NUTAB ativa do CODTAB] + flag de promoção vigente |
| `listar_promocoes_cadastradas(filtros, limite, offset)` | A | CRUD list (paginado) com escopo TABELA/PARCEIRO + qtd_clientes_grupo |
| `consultar_origem_preco_item(nunota, sequencia)` | A | Lê AD_ITEM_PRECO_ORIGEM |
| `criar_promocao_banco(dados, codusu, nomeusu)` | **B** | INSERT — aceita CODTAB OU CODPARC (XOR) |
| `editar_promocao_banco(promocao_id, dados, codusu, nomeusu)` | **B** | UPDATE — pode trocar escopo (CODTAB ↔ CODPARC) |
| `excluir_promocao_banco(promocao_id, codusu, nomeusu)` | **B** | DELETE físico |
| `registrar_origem_preco_item(...)` | **B** | UPSERT (MERGE) em AD_ITEM_PRECO_ORIGEM. Valida MANUAL → observação obrigatória |

### Endpoints REST

- `GET  /sankhya/venda/promocoes/` — tela CRUD
- `GET  /sankhya/venda/tabela-precos/` — tela LEITURA
- `GET  /sankhya/venda/api/preco-tabela/?codparc=X&codprod=Y`
- `GET  /sankhya/venda/api/promocoes/vigentes/?codparc=X&codprod=Y`
- `GET  /sankhya/venda/api/promocoes/listar/?codtab=X&codparc=Y&ativo=S&escopo=TABELA|PARCEIRO`
- `GET  /sankhya/venda/api/tabelas-grupos/?incluir_inativas=true`
- `GET  /sankhya/venda/api/tabela-precos/?codtab=X`
- `GET  /sankhya/venda/api/origem-preco-item/?nunota=X&sequencia=Y`
- `POST /sankhya/venda/api/promocao/criar/`
- `POST /sankhya/venda/api/promocao/editar/`
- `POST /sankhya/venda/api/promocao/excluir/`

Acesso: `@exige_grupo('venda')` (grupos 1, 6, 10).

---

## 8. Modelos SQLite (Django)

### `Simulation`

Simulações comerciais persistidas localmente.

- Registrado em `admin.py` (`SimulationAdmin`)
- Audit via signals (`post_save` / `post_delete` em `signals.py`)

### `RastreioAudit`

Audit log dedicado do WMS — registra cada atribuição/desvinculação bem-sucedida.

| Campo | Tipo | Descrição |
|---|---|---|
| `acao` | string | `ATRIBUIR` ou `DESVINCULAR` |
| `nunota` | int | NUNOTA do pedido afetado |
| `sequencia` | int | Sequência do item |
| `codagregacao` | int | Lote vinculado/desvinculado |
| `qtd` | decimal | Quantidade |
| `codusu` | int | Usuário que executou |
| `nomeusu` | string | Nome de usuário |
| `detalhe` | JSON | `{operacao, nova_sequencia}` para SPLIT |
| `created_at` | datetime | Timestamp |

- Registrado em `RastreioAuditAdmin` com filtros e search.
- Migration: `0001_initial.py` (junto com `Simulation`).
- Helper `_registrar_audit_rastreio()` em `views.py` é **tolerante a falhas**: se o gravar falhar, a operação no Oracle **não é desfeita** (apenas warning no log) — porque a operação já foi commitada.

---

## 9. Particularidades importantes

### Retorno de tuplas (não dicts)

Funções de `oracle_conn.py` retornam **listas de tuplas** (formato nativo do cursor Oracle). Views acessam por índice (`r[0]`, `r[1]`, etc.).

**Exemplo — `listar_itens_por_nota`:**

```
r[0]=lote, r[1]=seq, r[2]=codprod, r[3]=descr, r[4]=codvol,
r[5]=qtdneg, r[6]=peso, r[7]=vlu, r[8]=vlt, ..., r[11]=qtdconferida
```

**Ao adicionar novas colunas a qualquer query, os índices das colunas seguintes mudam — verificar todos os usos.**

### Geração de NUMNOTA

`faturar_pedido_venda_banco` usa `MAX(NUMNOTA) + 1` por empresa. Suficiente para o MVP porque o lock pessimista no cabeçalho protege a janela de concorrência. Sequência Oracle nativa seria mais robusta, mas exige criação no Sankhya — avaliar se emissão automática de NFe for ativada.

### `AD_NUMPEDIDOORIG` — auto-cura

`atualizar_cabecalho_nota_banco` tem auto-cura específica de Entrada/Classificação. **Venda e Rastreio NÃO usam** essa função para evitar efeitos colaterais.

### Bug crítico de `oracle_conn.py` — DPY-1001

`inserir_cabecalho_nota_banco` tem um `except` que tenta `rollback()` numa conexão já fechada pelo context manager, substituindo a exceção Oracle original com `DPY-1001: not connected to database`.

**Workaround aplicado em todas as views de escrita da Venda:** view gerencia a conn com `with obter_conexao_oracle() as conn:` e passa `conexao_existente=conn` para o service. Isso evita o caminho bugado e dá acesso explícito a `commit()`/`rollback()` da view.
