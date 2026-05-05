# Módulo Rastreio / WMS

Atribuição e desvinculação de lotes a pedidos de venda com auditoria, lock pessimista e distinção visual de pedidos faturados.

---

## Premissa Arquitetural

A alocação de lote a pedido é feita gravando `CODAGREGACAO` no `TGFITE` do pedido TOP 34. Saldos são lidos via view dedicada (`SANKHYA.ANDRE_IAGRO_SALDO_LOTE`) que **não toca `TGFEST` nativa do Sankhya** — toda aritmética é derivada de `TGFITE` + `TGFCAB`. Triggers e cleanup do banco continuam responsabilidade do Sankhya.

---

## Escopo

- Listar lotes disponíveis (com filtros e paginação)
- Listar pedidos abertos (TOP 34) com falta por produto
- Vincular lote → item de pedido (atribuição parcial ou total via SPLIT)
- Desvincular lote (remove `CODAGREGACAO`)
- Filtro cruzado bidirecional (lote ↔ pedido)
- Drag & drop de lote em produto-linha
- Modais de vínculos (👁 nas linhas)
- Audit log de cada operação em `RastreioAudit` (SQLite)

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/rastreio/` | GET | Página HTML (`@ensure_csrf_cookie`) |
| `/sankhya/rastreio/api/lotes-disponiveis/` | GET | Lista lotes paginada |
| `/sankhya/rastreio/api/pedidos-abertos/` | GET | Lista pedidos paginada |
| `/sankhya/rastreio/api/atribuir-lote/` | POST | Vincula lote (lock pessimista, audit) |
| `/sankhya/rastreio/api/desvincular-lote/` | POST | Remove vínculo (audit) |
| `/sankhya/rastreio/api/fabricantes/` | GET | Typeahead distinct |
| `/sankhya/rastreio/api/lote-vinculos/` | GET | Pedidos/vendas que usam um lote |

**Acesso:** Grupos `1`, `6`, `8`, `9`, `10` (decorator `@exige_grupo('rastreio')`).

---

## View do banco — `SANKHYA.ANDRE_IAGRO_SALDO_LOTE`

5 pernas, multi-empresa não restritiva. Detalhes completos em `schema.md` §5.

| Perna | STATUS_LINHA | Vendável |
|---|---|:-:|
| A | `CLASSIFICADO` | ✅ |
| B | `NAO_CLASSIFICAVEL` | ✅ |
| C | `AGUARDANDO_CLASSIFICACAO` | ❌ |
| D | `AVARIA_INTERNA` | ❌ |
| E | `AVARIA_FORNECEDOR` | ❌ |

---

## Funções de `oracle_conn.py` usadas

| Função | Operação |
|---|---|
| `consultar_saldo_lote_disponivel(filtros, limite, offset)` | Lê da view |
| `consultar_pedidos_abertos_para_atribuicao(filtros, limite, offset)` | TOP 34 paginado por cabeçalho |
| `atribuir_lote_item_pedido(nunota, sequencia, codagregacao, qtd=None)` | UPDATE total ou SPLIT (UPDATE qtd reduzida + INSERT nova linha) |
| `desvincular_lote_item_pedido(nunota, sequencia)` | `UPDATE TGFITE SET CODAGREGACAO=NULL` |
| `consultar_fabricantes_disponiveis(termo, limite)` | Typeahead `SELECT DISTINCT FABRICANTE` |
| `consultar_vinculos_de_lote(codagregacao)` | Pedidos/vendas que usam o lote |

---

## Lock pessimista — `atribuir_lote_item_pedido`

`SELECT ... FOR UPDATE` da linha do TGFITE **antes** de qualquer escrita.

**Defesa contra double-binding:** se o item já tem `CODAGREGACAO` diferente do solicitado, recusa com mensagem clara: *"Desvincule antes de atribuir outro lote"*.

**Validação de saldo entre empresas:** soma saldo `(CODPROD, CODAGREGACAO)` globalmente, sem filtrar por `CODEMP`. Permite vincular lote da empresa A em pedido da empresa B (decisão explícita do usuário).

**Recalcula `VLRNOTA` / `QTDVOL`** via `recalcular_totais_nota_banco`.

---

## Audit log — `RastreioAudit`

Helper `_registrar_audit_rastreio()` em `views.py` grava cada atribuição/desvinculação bem-sucedida em SQLite. Detalhes do modelo em `schema.md` §8.

**Tolerante a falhas:** se o gravar falhar, a operação no Oracle **não é desfeita** (já foi commitada). Apenas `logger.warning`. Não mudar para `raise`.

---

## Decisões de regra de negócio

1. **Listagem de pedidos ignora `STATUSNOTA = 'L'`** (mostra faturados também) — só filtra `<> 'E'`. **Atribuição** ainda valida e bloqueia faturado.
2. **Multi-empresa não restritiva** — saldo somado entre empresas. Pode vincular lote da empresa A em pedido da empresa B.
3. **In-natura pendente (perna C)** aparece como linha não-vendável (cinza tracejado) — visibilidade ao operador.
4. **Avaria do fornecedor (perna E, `AD_QTDAVARIA` da TOP 11)** aparece como linha não-vendável separada — não some no card "in-natura pendente".
5. **Avaria interna (perna D)** aparece como **badge inline vermelho** `▼ Xkg` no card vendável (Opção A). Linha separada (Opção B) está pronta na view para uso futuro — pendência roadmap.

---

## Frontend — UX

### Cards compactos em 1 linha

- **Lote:** `produto · parceiro · lote · data · qtd`
- **Pedido (produto agregado por `(NUNOTA, CODPROD)`):** `produto · vinculada/total · tag/falta`

### Agrupamento

- Header: `Parceiro | Data | Pedido NUNOTA`
- Toggle PARCEIRO/PRODUTO troca o agrupador grosso

### Ordenação

| Modo | Ordenação |
|---|---|
| POR PARCEIRO | data **ASC** + parceiro ASC (fila cronológica de pedidos a atender) |
| POR PRODUTO | data DESC + parceiro ASC |

**Default colapsado:** todo grupo começa fechado. `pedidosJaVistos` / `gruposProdutoJaVistos` rastreiam o que já foi inicializado para preservar escolha do usuário em refresh/scroll.

### Filtros

- **Toggle TODOS / CLASSIFICÁVEIS / NÃO-CLASSIF** de tipo de lote (radio)
- **Switch TRAVAR FILTRO** (mantém filtro cruzado ao re-clicar)
- **Selects de Período:** lotes (default 30d) e pedidos (default 10d) — janela `desde_dias`
- **Inputs de busca com typeahead** (debounce 300ms, AbortController, ↑↓/Enter/Tab/Esc/clique fora):
  - Lotes: busca por **FABRICANTE** distinct
  - Pedidos: busca por NUNOTA (numérico) ou nome do parceiro

### Filtro cruzado bidirecional

Estado: `produtosFiltrados: Set` + `pedidoIsolado: NUNOTA`.

**Eixos separados (premissa do filtro isolado):**
- `checksLotes: Set<codprod>` — filtra lotes por produto
- `checksPorPedido: Map<NUNOTA, Set<codprod>>` — filtra produtos visíveis dentro de cada pedido

Marcar produto X num pedido **não cascatea** para outros pedidos com o mesmo produto. Decisão explícita do usuário.

**Comportamento:**
- Click no card de lote → filtra pedidos por aquele codprod
- Click em produto-linha do pedido → filtra lotes por aquele codprod, e mostra só esse produto dentro do pedido
- Click no header do pedido → ISOLA esse pedido (`?nunota=X` no fetch) + filtra lotes pelos N codprods dele. Em isolamento, ignora `desde_dias`/`codprods` para não esconder o pedido alvo
- Re-click → toggle limpa (a menos que TRAVAR FILTRO)

**Importante:** filtro é **opt-in via checkbox**, nunca por click direto na linha. Click no card/linha **seleciona** (revela botões 🔗/👁); checkbox tem listener próprio.

### Drag & Drop lote → produto-linha

- Modal sugere `min(disp_lote, qtd_falta_total_do_produto)`
- Trava do `max` no input impede vincular mais que o pedido pediu
- Confirmação distribui qtd entre múltiplas linhas pendentes (split sequencial)
- Recarrega ambos os painéis ao concluir

### Modais de vínculos (👁 nas linhas)

- **Lado lote (👁 do card):** pedidos/vendas (TOP 34/35/37) — `DATA · NUNOTA · PARCEIRO (cliente) · PRODUTO · QTD`
- **Lado pedido (👁 do produto-linha):** lotes vinculados — `DATA · NUNOTA · LOTE · PARCEIRO (fornecedor) · PRODUTO · QTD`
- Click em linha mostra **botão lixeira** com `IAgro.confirmarAcao` → POST desvincular → recarrega
- Linhas TOP 35/37 (faturado): **sem botão** — desvincular bloqueado
- Badge `FATURADO` (cinza) vs `ATRIBUÍDO` (verde) com classes `.vinc-status-faturado` / `.vinc-status-atribuido`

### Botões de ação

Ocultos por padrão. Revelam-se com:
- Hover (opacity 0.55)
- Seleção da linha (cresce de 26→32 com transition cubic-bezier "spring")

Reduz ruído visual em listas longas.

### Bar "Lote armado"

`position: fixed; bottom: 36px` — no rodapé, não no topo. Visível durante scroll, fora do caminho de leitura.

### Persistência

`localStorage` chave `iagro:rastreio:prefs:v1` guarda: `agrupamento`, `tipoLote`, 4 datas, `travado`, `somentePendentes`. Restaurado no boot, salvo a cada change. `Limpar Tudo` reseta e persiste.

### Switch "SÓ PENDENTES"

Esconde produto-linhas já 100% atribuídas e remove pedidos cujos produtos visíveis ficaram completos. Persistido. Empty state contextual: *"Tudo vinculado!"*

### Alerta de lote envelhecido

`DTNEG_ORIGEM > 60 dias` (constante `DIAS_ALERTA_LOTE`) → badge laranja `⚠ Nd` no card + borda esquerda laranja (`.lote-envelhecido`).

### Tooltip nos chips de filtro

`.filtro-chip .chip-valor` com `title` + `cursor: help` + truncamento `text-overflow: ellipsis`. Filtros longos não desaparecem.

---

## Frontend — arquivos

- **Template:** `rastreio.html`
- **CSS:** `rastreio.css`
- **JS:** `rastreio.js`
- **Container interno:** `.rastreio-layout` (grid 2 colunas iguais)

### Tokens locais (`:root` do `rastreio.css`)

| Token | Valor | Origem |
|---|---|---|
| `--ras-primary` | `#5e7e4a` | Verde Agromil (alinhado a `home.css`) |
| `--ras-secondary` | `#825e38` | Marrom |
| `--ras-accent` | `#38292c` | Marrom escuro |

**NÃO usar gradientes saturados (azul→roxo)** — quebram consistência visual.

### CSS específico

- 130 blocos: cards compactos, tags/badges/estados não-vendáveis, structure, typeahead dropdown, modal de vínculos, lixeira aparecendo ao selecionar linha
- Override `.main-layout { padding: 0; gap: 0 }` (rastreio gerencia padding via `.rastreio-layout`)
- `:has()` CSS para estilização dependente de checkbox

---

## Pontos de atenção do JS

Detalhes em `gotchas.md`. Resumo:

- `renderPedidos()` é função central — validar 4 caminhos (parceiro/produto × com/sem filtro) ao mexer
- `pedidosColapsados` + `pedidosJaVistos` — duplicidade intencional, não consolidar
- `checksLotes` + `checksPorPedido` — eixos separados, não consolidar
- `limparTudo()` — toda nova feature de filtro/estado precisa adicionar reset aqui
- `renderFiltrosAtivos()` popula apenas `#filtrosAtivosChips`, não o container externo
- IDs `btnLimparTudo` / `btnAtualizar` — preservados; listeners dependem deles

---

## Testes

`test_rastreio.py` — **53 testes** mockados:

- Endpoints (lotes, pedidos, atribuir, desvincular, fabricantes, vinculos)
- `AtribuirLoteServiceTest` — lock, double-binding, faturamento (4 testes)
- `RastreioAuditLogTest` — atribuir grava, falha não grava, desvincular grava (3 testes)
- `HumanizarErroOracleTest` — ORA-00054 → "outro usuário", ORA-12899 não vaza coluna (2 testes)

### Pendências de cobertura

- Testes diretos de `consultar_vinculos_de_lote`, `consultar_fabricantes_disponiveis`, `desvincular_lote_item_pedido`, `consultar_saldo_lote_disponivel`. Replicar padrão do `AtribuirLoteServiceTest`.
