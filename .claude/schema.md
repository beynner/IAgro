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
    34: 10010100,   # Pedido de Venda
    35: 10010100,   # Venda com NFe
    37: 10010200,   # Venda sem NFe
}
```

### TOPs do projeto (referência completa)

| TOP | CODNAT | Descrição | Origem | Observações |
|---|---|---|---|---|
| 11 | — | Compra (Entrada) | Recebimento de fornecedor | Gera lote com `CODAGREGACAO = NUNOTAS{SEQ}D{YYMMDD}` |
| 13 | — | Vale de Compra (Comercial) | Faturamento de vales | Gera financeiro em TGFFIN |
| 26 | — | Classificação confirmada | Triagem de qualidade | Discriminador de lote `CLASSIFICADO` no WMS |
| 30 | — | Avaria interna (perda) | Perda no estoque | Perna D no WMS (não-vendável) |
| 34 | 10010100 | Pedido de Venda (em aberto) | Módulo Venda | TOP base para edição/atribuição de lote |
| 35 | 10010100 | Venda com NFe | Faturamento da Venda | Emissão real de NFe é tarefa do Sankhya |
| 36 | 10020100 | (a confirmar) | — | Não usado no MVP |
| 37 | 10010200 | Venda sem NFe | Faturamento da Venda | TOP alternativo para venda s/ documento fiscal |
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

### Fórmula de saldo

```
QTD_DISPONIVEL = ENTRADA
               − Σ TOP 35/37 confirmadas
               − Σ TOP 30 confirmadas
               − Σ TOP 34 abertas
```

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
| `listar_vendas_paginado(filtros, limite, offset)` | Listagem do portal de Venda |
| `faturar_pedido_venda_banco(nunota, nova_top, codusu_logado)` | Faturamento atômico TOP 34 → 35/37 com `SELECT FOR UPDATE`, validação de itens com lote, geração de `NUMNOTA` por empresa |

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
