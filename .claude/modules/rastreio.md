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
- `HumanizarErroOracleTest` — ORA-00054 → mensagem operacional, ORA-12899 não vaza coluna (2 testes; assertions atualizadas em Mai/2026 pra novo microcopy)

### Pendências de cobertura

- Testes diretos de `consultar_vinculos_de_lote`, `consultar_fabricantes_disponiveis`, `desvincular_lote_item_pedido`, `consultar_saldo_lote_disponivel`. Replicar padrão do `AtribuirLoteServiceTest`.

---

## UX polish em homologação (Mai/2026)

10 ajustes pequenos pra reduzir fricção no 1º contato com operador real. Tudo em `rastreio.js` / `rastreio.css` exceto items 4 e 5 (`oracle_conn.py`). Em testes em produção.

| # | O que mudou | Onde |
|---|---|---|
| 1 | Skeleton de carga (4 cards cinzas com shimmer animation) substitui "Carregando..." pelado quando `lotesData.length === 0 && lotesCarregando` ou pedidosCarregando | `_renderSkeletonCards(n)` em `rastreio.js` + `.ras-skeleton-card` + `@keyframes ras-skeleton-shimmer` em `rastreio.css` |
| 2 | `.btn--loading` (disable + opacity 0.75 + spinner CSS via `::after`) aplicado em `btnConfirmarTransfer` durante atribuição e em `.btn-desvincular` durante desvinculação. Texto do botão muda pra "Vinculando..." durante a chamada | `confirmarTransferencia()` e `bindDesvincularNoModal()` |
| 3 | Toast de sucesso contextual: `Lote 8117 vinculado: 160 kg → Pedido 4567 · CLIENTE X` (em vez de "Lote atribuído"). Mesma melhoria em desvinculação | `confirmarTransferencia()` |
| 4 | `ORA-00054` reescrita: `"Outro operador está mexendo neste registro agora. Aguarde alguns segundos e tente novamente. Se o erro persistir após 1 minuto, avise o suporte."` | `_MAPA_ORA_HUMANIZADO` em `oracle_conn.py` |
| 5 | Erro de saldo insuficiente em formato BR + sugestão: `Saldo insuficiente no lote 8117. Disponível: 125,50 · Solicitado: 200,00. Reduza a quantidade ou desvincule alguma atribuição existente deste lote (clique no olho do card de lote pra ver quem usa).` | `atribuir_lote_item_pedido` em `oracle_conn.py` |
| 6 | Empty state com botão de ação: `Limpar filtros` (acumula filtros) ou `Mostrar pedidos vinculados` (pra `somentePendentes`). Delegação no container via `_bindEmptyActions(container)` | `renderLotes()` / `renderPedidos()` + `_bindEmptyActions()` |
| 7 | Mensagem distingue: filtros ativos restritivos (`Nenhum lote encontrado com os filtros atuais`) vs sem dados reais (`Sem lotes disponíveis no período`) | mesmo lugar do #6 |
| 8/9 | Tooltips estendidos em badges técnicos: `N/C` ("Sem classificação confirmada — vendável como in natura, vem da TOP 13, não passou pela TOP 26"), `AVARIA INTERNA` ("Avaria interna reservada — não disponível para vincular em pedido"), `FATURADO` ("Pedido já faturado (TOP 35 - Venda com NFe). Não pode mais ser desvinculado."), `ATRIBUÍDO` ("Pedido em aberto (TOP 34) — pode ser desvinculado se necessário") | `renderLotes()` e `abrirModalVinculosDeLote()` |
| 10 | Microcopy: `Confirmar` (do modal de transferência) → `Vincular lote`. Tooltip do `btn-armar` mais explícito ("Selecionar este lote para vincular num pedido") | `rastreio.html` + `rastreio.js` |

**Tests adicionados/atualizados em Mai/2026 (2026-05-08):**
- `test_rastreio.py` `HumanizarErroOracleTest.test_excecao_ora_00054_humanizada` — assertions em termos-chave (`operador`, `aguarde`) em vez da frase exata, suportando futuras melhorias de microcopy sem quebrar
- `test_views_venda.py` `FaturarPedidoVendaTest.test_excecao_retorna_500_humanizada` — mesmo padrão

---

## Bloco A — Quick wins UX (Mai/2026, 2026-05-08, pós-feedback)

5 melhorias adicionais de UX implementadas em sequência ao polish anterior. Todo trabalho frontend (`rastreio.js` + `rastreio.css`); zero mudança de backend.

| # | O que mudou | Onde | Por que vale |
|---|---|---|---|
| 1 | **Avaria interna como linha B**: `qtd_avaria_interna > 0` agora gera **card separado** logo abaixo do vendável, em estilo `.nao-vendavel` (cinza tracejado, dashed border) com tag `AVARIA INT.` (`.tag-avaria-int`). Antes era badge inline `▼ Xkg` na col-qtd (Opção A descontinuada — classe `.badge-avaria-interna` mantida no CSS por compat). Helper `_criarCardLoteAvariaInterna(l)` | `renderLotes()` + CSS `.tag-avaria-int`, `.col-qtd-avaria`, `.ras-row-check-box-disabled` | Operador vê de relance "tem X kg deste lote em avaria, fora do saldo". Linha não bagunça o card vendável. |
| 2 | **Saldo total no header de pedidos**: nova métrica `kg a atribuir` (vermelho) na quickstats de pedidos, somando `qtd_falta` agregada de todos pedidos visíveis. Cosmeticamente alinha com `kg disponíveis` (verde) que já existia na quickstats de lotes. | `renderPedidos()` linha quickstats | Operador compara visualmente os 2 totais (oferta vs demanda) sem precisar fazer conta. |
| 3 | **Badge `✨ encaixa`**: card de lote ganha pílula verde quando `qtd_disponivel == falta_total[codprod]` (tolerância 0.001). Borda esquerda verde discreta (`.lote-encaixa-exato`) reforça em listas longas. Pré-cálculo via helper `_calcularFaltaPorCodprod()` que agrega `pedidosData` filtrando linhas sem `codagregacao_atual`. | `renderLotes()` + CSS `.badge-encaixa-exato` / `.lote-encaixa-exato` | Sinal forte de "atribuição segura sem split" — incentiva fechar o ciclo do lote em 1 click. |
| 4 | **Atalhos de teclado globais**: `/` ou `F` foca busca de lote, `R` aciona Atualizar, `C` aciona Limpar, `G` alterna agrupamento parceiro↔produto, `Esc` (já existia) desarma lote / fecha modal. Ignora teclas quando foco está em `INPUT/TEXTAREA/SELECT/contenteditable` ou modal aberto. Sem modificadores (Ctrl/Alt/Meta). | listener `document.keydown` global | Fluxo de operador power-user — quem usa o módulo o dia todo aprende e ganha velocidade. |
| 5 | **Persistência do lote armado**: `loteArmadoCodag` adicionado às prefs em `localStorage` (chave `iagro:rastreio:prefs:v1`). Salvo em `armarLote/desarmarLote`. Restaurado 1× por boot via `_tentarRestaurarLoteArmado()` chamado no `finally` do `carregarLotes`. Se o lote sumiu da listagem (foi vendido / fora do filtro), pref é descartada silenciosamente. | `_salvarPrefs`, `armarLote`, `desarmarLote`, `carregarLotes` | Operador interrompido (almoço, F5 acidental, conexão caiu) retoma exatamente de onde parou. |

**Decisões de design preservadas:**
- Filtros cruzados (`checksLotes`, `checksPorPedido`, `pedidoIsolado`) **NÃO** entram nas prefs — efêmeros por ciclo de uso, decisão consciente de Mai/2026.
- Atalhos `Space`/`Enter` para armar/atribuir lote em foco **não foram implementados** — exigem rastreamento de "card em foco" que adiciona complexidade. Avaliar quando houver pedido explícito do operador.
