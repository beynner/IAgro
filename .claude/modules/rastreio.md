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
| `/sankhya/rastreio/api/etiqueta-pdf/?nunota=X[&codprod=Y]` | GET | PDF 100×50mm de etiquetas SafeTrace (Mai/2026) |

**Acesso:** Grupos `1`, `6`, `8`, `10` (decorator `@exige_grupo('rastreio')`). _Comercial (9) perdeu acesso em 2026-05-14 — eles veem rastreio só via relatório._

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

## Materialização do saldo — `AD_SALDO_LOTE_CACHE` (Mai/2026)

A view `ANDRE_IAGRO_SALDO_LOTE` leva 10-22s por hit em produção (5 CTEs com
agregações em TGFITE/TGFCAB/TGFVAR — centenas de milhares de linhas).
Travava o operador na carga do Rastreio.

**Solução**: tabela espelho `SANKHYA.AD_SALDO_LOTE_CACHE` populada via cron
a cada 5 min. Leitura direto da tabela física com índices apropriados:
**~200ms vs 12s** (60x mais rápido).

### Componentes

- **DDL**: [`sankhya_integration/sql/AD_SALDO_LOTE_CACHE.sql`](../../sankhya_integration/sql/AD_SALDO_LOTE_CACHE.sql) — espelho exato das 19 colunas do retorno da view + `ATUALIZADO_EM` (timestamp do último refresh). PK composta `(CODEMP, CODPROD, CODAGREGACAO, STATUS_LINHA)`. 4 índices: `QTD_DISPONIVEL`, `DTNEG_ORIGEM DESC`, `CODPROD`, `VENDAVEL`.
- **Função service**: `refresh_saldo_lote_cache()` em `oracle_conn.py` — TRUNCATE + INSERT-SELECT da view. Logger.info registra contagem + duração. Invalida cache Django em cima ao fim. Retorna `{ok, rows, duracao_s}`.
- **Comando Django**: `python manage.py refresh_saldo_lote` em [`sankhya_integration/management/commands/refresh_saldo_lote.py`](../../sankhya_integration/management/commands/refresh_saldo_lote.py). Saída JSON 1-linha pra parsing fácil. Exit code 0 = sucesso, 1 = falha.
- **Consumo**: `consultar_saldo_lote_disponivel` aponta `FROM SANKHYA.AD_SALDO_LOTE_CACHE` (era `FROM SANKHYA.ANDRE_IAGRO_SALDO_LOTE`). Cache Django (60s TTL + versionamento) continua em cima — combinado, 2ª leitura ≤60s é instantânea.
- **Windows Task Scheduler**: agendamento a cada 5 min no servidor.

### Outros consumidores da view continuam usando a view real

Apenas a função `consultar_saldo_lote_disponivel` foi trocada. As demais
referências (lock pessimista em `atribuir_lote_item_pedido`, validações de
saldo em escritas, relatórios via JOIN com `ANDRE_IAGRO_SALDO_LOTE`)
continuam consultando a view real — integridade transacional preservada.

### Coerência: até 5 min de delay

Operador atribui/desvincula lote → cache Django invalida → próxima leitura
miss no Django, mas SELECT continua na `AD_SALDO_LOTE_CACHE` (snapshot
antigo). O saldo refresh-ado só aparece após o próximo ciclo do cron.

**Por que é seguro**: o lock pessimista em `atribuir_lote_item_pedido`
valida saldo na **view real** antes de gravar. Não dá pra atribuir mais
que tem disponível, mesmo se a tela mostrar saldo antigo. Latência é
exclusivamente visual.

### Setup operacional

**1.** Aplicar a DDL no Oracle (única vez):
```sql
@AD_SALDO_LOTE_CACHE.sql
```

**2.** Rodar refresh manual pra popular a tabela inicial:
```cmd
python manage.py refresh_saldo_lote
```
Esperado: `{"ok": true, "rows": <N>, "duracao_s": ~12}`.

**3.** Agendar no Windows Task Scheduler:
- **Programa**: `D:\TI\NexusGTi\IAgro\IAgro\.venv\Scripts\python.exe`
- **Argumentos**: `manage.py refresh_saldo_lote`
- **Iniciar em**: `D:\TI\NexusGTi\IAgro\IAgro`
- **Disparador**: ao iniciar + repetir a cada 5 min indefinidamente
- **Não rodar se o anterior está em execução**: marcar (evita acúmulo)

### Quando avaliar evolução pra C2 (refresh on-demand pontual)

Atual: cron 5min cobre 95% dos casos. Se aparecer demanda de "saldo
imediatamente após atribuir lote", evoluir pra MERGE pontual no fim de
`atribuir_lote_item_pedido` que recalcula só a linha `(CODPROD, CODAGREGACAO)`
afetada e UPDATE em `AD_SALDO_LOTE_CACHE`. Custo +~500ms na escrita, mas
elimina o delay visual. Pra Agromil hoje não vale a complexidade — cron
basta.

### Monitoramento

`AD_SALDO_LOTE_CACHE.ATUALIZADO_EM` mostra quando foi o último refresh.
Se Task Scheduler quebrar, basta query:
```sql
SELECT MAX(ATUALIZADO_EM) FROM SANKHYA.AD_SALDO_LOTE_CACHE;
```
Datas antigas → investigar o agendamento. Frontend pode futuramente exibir
banner "Saldo defasado: última atualização há X min" se a diferença for
maior que 10 min.

---

## Funções de `oracle_conn.py` usadas

| Função | Operação |
|---|---|
| `consultar_saldo_lote_disponivel(filtros, limite, offset)` | Lê da view |
| `consultar_pedidos_abertos_para_atribuicao(filtros, limite, offset)` | TOP 34 paginado por cabeçalho |
| `atribuir_lote_item_pedido(nunota, sequencia, codagregacao, qtd=None, peso=None)` | UPDATE total ou SPLIT. Grava `PESO` (Mai/2026 — 2026-05-16: trocou de QTDFIXADA pra PESO; campo agora **opcional**, fallback via TOP 26 do lote) |
| `desvincular_lote_item_pedido(nunota, sequencia)` | `UPDATE TGFITE SET CODAGREGACAO=NULL, PESO=NULL` (caminho CLEAR) ou MERGE com pendente do mesmo CODPROD |
| `consultar_fabricantes_disponiveis(termo, limite)` | Typeahead `SELECT DISTINCT FABRICANTE` |
| `consultar_vinculos_de_lote(codagregacao)` | Pedidos/vendas que usam o lote |
| `consultar_dados_etiqueta_pedido(nunota, codprod=None, pesos_overrides=None)` | Leitura — JOIN TGFCAB+TGFITE+TGFPAR+TGFPRO+TSIEMP. Inclui só linhas com `CODAGREGACAO != NULL`. **Mai/2026 (2026-05-16):** retorna `peso_resolvido` por linha em cascata — override do operador → `TGFITE.PESO` próprio → DISTINCT `PESO` da TOP 26 do mesmo lote. Se TOP 26 tem 2+ pesos, marca `precisa_escolha=True` |
| `consultar_pesos_classificacao_lote(codagregacao)` | **Nova (Mai/2026 — 2026-05-16).** `SELECT DISTINCT PESO FROM TGFITE i JOIN TGFCAB c WHERE c.CODTIPOPER=26 AND c.STATUSNOTA<>'E' AND i.CODAGREGACAO=:l AND i.PESO>0 ORDER BY PESO DESC`. Cacheada por lote dentro de `consultar_dados_etiqueta_pedido` |
| `calcular_qtd_etiquetas(qtd_kg, peso_caixa_kg)` | `math.ceil(qtd/peso)`. Retorna 0 se algum for ≤ 0 — frontend bloqueia impressão |

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

`localStorage` chave `iagro:rastreio:prefs:v1` guarda: `agrupamento`, `agrupamentoLotes`, 4 datas, `mostrarPendentes`, `loteArmadoCodag`. Restaurado no boot, salvo a cada change. `Limpar Tudo` reseta e persiste.

**Mai/2026 — 2026-05-19:** `mostrarFinalizados` deixou de ser persistido. **Sempre arranca `false`** ao abrir a tela — operador liga manualmente quando precisar de pedidos faturados (cortou ~30% do tempo de query). `tipoLote` também ignora storage e sempre é `'todos'` (filtro Todos/Classific./Não-class. removido da UI).

### Defaults da UI (Mai/2026 — 2026-05-19)

| Filtro | Default | Persiste? |
|---|---|:-:|
| Agrupamento de Pedidos | **Por produto** | ✅ |
| Agrupamento de Lotes | **Por produto** | ✅ |
| Mostrar Pendentes | ligado | ✅ |
| Mostrar Finalizados | **desligado (sempre)** | ❌ (forçado) |
| Tipo de lote | `'todos'` (sem UI) | ❌ |
| Datas Lotes | últimos 7 dias | ✅ |
| Datas Pedidos | últimos 7 dias | ✅ |

### Filtros do painel Lotes — ordem (Mai/2026 — 2026-05-19)

```
[ − ] [ + ]    | Por parceiro | Por produto |    📅 [data ini] → [data fim] ✕
```

Toggle `Todos / Classific. / Não-class.` **removido** (filtro raramente útil — operador sempre via "todos"). Variável JS `tipoLote` mantida como constante `'todos'` pra não quebrar query strings legadas.

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

### Padrão de compactação visual (Mai/2026 — 2026-05-19)

Headers de agrupamento e linhas selecionáveis foram padronizados pra **máxima densidade de informação** sem perder legibilidade. Padrão aplicado nos 3 contextos: lotes, pedidos POR PARCEIRO e pedidos POR PRODUTO.

**Headers de agrupamento** (`.pedido-bloco-header`, `.lote-bloco-header`, `.pedido-bloco-header.tipo-produto`):

| Propriedade | Valor | Por quê |
|---|---|---|
| `padding` | `2px 10px` | altura efetiva ~28px (chevron/avatar 22px + 2+2 padding + 2 borders) |
| `margin` | `0` | sem respiro próprio |
| `border` | `1px solid` + `border-left: 3px` colorida | identidade visual (verde Agromil pra lotes, marrom pra pedidos POR PRODUTO) |
| `border-radius` | `6px` | bordas suaves |
| `font-size` | `12.5px` | leitura confortável |

**Container** (`.list-panel .card-list`):

| Propriedade | Valor |
|---|---|
| `gap` | `2px` |
| `padding` | `8px` |
| `display` | `flex; flex-direction: column` |

**Espaço efetivo entre 2 headers consecutivos**: `2px` (só o `gap` do container — margens zeradas eliminam variação entre os 3 contextos).

**Total por linha**: `~30px` (28 altura header + 2 gap). Cabe ~24 produtos por viewport de 720px.

**Linhas filhas** (`.card-lote.compacto`, `.produto-linha`, `.linha-pedido-compacta`):

| Propriedade | Valor |
|---|---|
| `padding` | `1px 8px` |
| `font-size` | `11px` |
| `border` | `none` + `border-bottom: 1px solid` (último filho sem border-bottom) |
| `border-radius` | `0` |
| Avatar no item | **removido** — só aparece no header do grupo, evita duplicação visual |
| Nome do produto/parceiro | `font-weight: 400` — bold só no header |

**Por que essa abordagem**: usar `padding: 0` ou margens negativas pra colapsar bordas adjacentes é frágil em flex containers (margin-collapse não acontece em flex). A solução robusta é `margin: 0` + `gap` controlando o espaço único.

**Conflito de regras a evitar**: havia 2 declarações de `.list-panel .card-list` em pontos diferentes do CSS (linhas 1007 e 2336) com valores conflitantes. CSS resolve por ordem (último vence). Antes de adicionar nova regra, **sempre verificar duplicatas via Grep**.

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

---

## Vincular lote em pedido faturado — modelo "rastreabilidade no pedido" (Mai/2026)

### Caso de uso real

Operação rotineira da Agromil: NFe sai pelo Sankhya **antes** da classificação física chegar no sistema (operadores anotam classificação em papel, depois transcrevem). Sem suporte a editar lote em pedido faturado, o processo trava por ~3 horas — atrasa a entrega e impede o carregamento em paralelo à classificação (que é como a operação roda hoje, com etiquetas já impressas).

### Decisão arquitetural: rastreabilidade vive no pedido

A "verdade" da rastreabilidade (`CODAGREGACAO` em TGFITE) vive **sempre no pedido (TOP 34)**, mesmo após o Sankhya faturar e gerar a nota TOP 35/37. A nota não é tocada pelo IAgro — fica como referência fiscal. Implicações:

- Sem escrita em TGFVAR (sem disparar as 6 triggers Sankhya em TGFVAR — risco de cascata em TGMTRA / metas / orçamento eliminado)
- Operações suportadas em pedido faturado: atribuir, **split**, troca, desvincular — todas pelo lado do pedido apenas
- NFe XML não muda (`QTDNEG`/`VLRTOT` do pedido permanecem como saíram)
- Operador do Sankhya nativo vê a nota com `CODAGREGACAO` em branco — divergência conhecida, sem impacto fiscal (NCM 0706 hortifrúti não exige grupo `<rastro>`)

### Como a view ANDRE_IAGRO_SALDO_LOTE foi adaptada

Antes baixava só de TOP 35/37 STATUSNOTA='L'. Agora a perna `baixas_venda` é uma UNION com prioridade pro TOP 34:

1. **(Verdade IAgro)** TOP 34 STATUSNOTA='L' com `CODAGREGACAO` populado — pedido vinculado pelo IAgro
2. **(Fallback Sankhya nativo)** TOP 35/37 STATUSNOTA='L' com `CODAGREGACAO` populado, **somente quando** o item origem via TGFVAR não tem lote no pedido — evita contar o mesmo lote 2× quando o operador vinculou pela IAgro

### Como a listagem foi adaptada

`consultar_pedidos_abertos_para_atribuicao` traz 2 fontes via OR no WHERE (Mai/2026 — refinado após casos 112017/111975/111976):

- **PEDIDO**: TOP 34 (em aberto OU `STATUSNOTA='L'`). Sempre listado, sem distinguir por TGFVAR par.
- **NOTA_ORFA**: TOP 35/37 STATUSNOTA='L' **sem TGFVAR** em qualquer sentido + **sem vínculo manual** — notas emitidas direto no Sankhya sem fluxo "atender pedido" (caso 111976).

**B9 (Mai/2026, 2026-05-15) — Toggle agora é por completude do rastreio**, não por STATUSNOTA. O critério aplicado a ambos os caminhos:
- `mostrar_pendentes` → pedido com ao menos 1 item TGFITE com `CODAGREGACAO IS NULL` (rastreio incompleto)
- `mostrar_finalizados` → pedido com **TODOS** os itens TGFITE com `CODAGREGACAO IS NOT NULL` (rastreio 100% vinculado)

Param antigo `mostrar_faturados` ainda aceito como **alias retro** de `mostrar_finalizados` (URL legada continua funcionando). Sem duplicação: TOP 35/37 só entra como ÓRFÃ quando não há TGFVAR par nem vínculo manual, nunca ao lado da TOP 34 correspondente.

**Frontend**: label do toggle `Faturado → Finalizado`, variável JS `mostrarFaturados → mostrarFinalizados` (retrocompat lê chave antiga em `iagro:rastreio:prefs:v1` quando nova ainda não gravada). Default: só Pendente ligado.

**Agrupamento dos Lotes (B9)**: novo toggle `grpLotes` (Por Parceiro / Por Produto) ao lado do "Tipo de Lote". `renderLotes` agrupa cards por `NOMEPARC_ORIGEM` ou `DESCRPROD` ordenado alfabeticamente. Header reusa visual `.pedido-bloco-header` (chevron + avatar + nome + qtd total verde + contador de lotes) mas sem impressora/percentual/NUNOTA. Cards com `margin-left: 16px` e regra `.card-lote.compacto:not(.card-lote-avaria-int) > .col-prod { display: none }` esconde nome do produto (já está no header). Set `gruposLotesColapsados` controla expand/collapse; reseta ao trocar tipo de agrupamento.

NUMNOTA e NUNOTA da nota correlata vêm via subquery escalar em TGFVAR (`SELECT MAX(NUMNOTA) FROM TGFCAB c2 JOIN TGFVAR v ON c2.NUNOTA = v.NUNOTA WHERE v.NUNOTAORIG = c.NUNOTA AND c2.CODTIPOPER IN (35,37) AND c2.STATUSNOTA <> 'E'`). Frontend usa pra exibir badge `FATURADO Nota Y` (apenas em PEDIDOs faturados — em NOTA_ORFA a subquery devolve null por definição).

**Distinção visual** (Mai/2026, 5 estados):
- **PEDIDO sem nota par** → header "Pedido X", sem badge
- **PEDIDO com TGFVAR par** (`vinculo_origem='TGFVAR'`) → "Pedido X" + badge amarelo `FATURADO Nota Y`
- **PEDIDO com vínculo manual** (`vinculo_origem='MANUAL'`) → "Pedido X" + badge verde-azulado `FATURADO Nota Y · MANUAL` + botão "Desfazer" (Leva A)
- **PEDIDO retroativo** (`vinculo_origem='RETROATIVO'`) → "Pedido X" + badge roxo `FATURADO Nota Y · RETROATIVO` + botão "Desfazer" (Leva B — pedido foi criado pelo IAgro espelhando a nota)
- **NOTA_ORFA** → header "Nota Y" (NUMNOTA fiscal) + badge vermelho `ÓRFÃ` + **1 botão adaptativo** (ver "Fluxo unificado" abaixo)

### Fluxo unificado de resolução de nota órfã (Mai/2026)

Em vez de mostrar 2 botões (Vincular vs Criar), o operador vê **1 só botão** com label adaptativo segundo a heurística rigorosa:

- **`Vincular ao pedido`** — quando existe pedido pareável exato (mesmo CODPARC + CODEMP + valor exato com ∆ ≤ R$ 0,01 + data ±1 dia + sem TGFVAR + sem vínculo manual)
- **`Criar pedido retroativo`** — quando nenhum pedido bate exatamente

Em ambos os casos: confirmação modal antes (operador nunca confirma sem ler). Backend decide a ação via `resolver_nota_orfa_automatica` na rota `/api/vinculo/resolver/`.

### AD_NUMPEDIDOORIG na nota (Mai/2026)

Convenção Agromil: TGFCAB de **venda** (TOP 35/37) aponta pro NUNOTA do **pedido origem** via `AD_NUMPEDIDOORIG`. No fluxo padrão Sankhya ("atender pedido"), esse campo é populado automaticamente. No fluxo invertido (venda direta sem pedido), fica NULL — daí o ajuste retroativo pelo IAgro:

| Operação | `TGFCAB(nota).AD_NUMPEDIDOORIG` | `TGFITE(nota,*).AD_NUMPEDIDOORIG` |
|---|---|---|
| Estado pré-IAgro (Sankhya direto) | NULL | NULL |
| **Vincular** (Leva A) → Pedido X | X | X (todos os itens) |
| **Criar pedido retroativo** (Leva B) → Pedido X novo | X | X (todos os itens) |
| **Desfazer** vínculo (qualquer origem) | NULL | NULL |

Pedido criado retroativamente (Leva B): recebe `AD_NUMPEDIDOORIG = NUNOTA próprio` via default do `inserir_cabecalho_nota_banco` (auto-referência, ele é a raiz da cadeia).

Atomicidade: o UPDATE de TGFCAB+TGFITE da nota acontece no mesmo commit do INSERT/DELETE em `AD_VINCULO_PEDIDO_NOTA`.

**Heurística rigorosa** — refinamento de Mai/2026. A primeira versão usava janela de data ±1/+7 dias sem filtro de valor, gerando falsos positivos pra clientes recorrentes (Assaí faz pedidos quase todo dia, então coincidência de data dentro de uma semana não prova nada). Caso real do problema:

> Nota 6241 (R$ 510, CODPARC 588): a heurística sugeria pedidos 111735 (R$ 6.300) e 111759 (R$ 8.610) só porque eram do mesmo cliente em datas próximas. Valor 11× a 16× maior — claramente lixo.

Critério firme passou a ser **valor exato + data ±1 dia**. Reduz drasticamente falsos positivos. Se o operador precisar vincular caso especial fora da heurística, ele faz pelo endpoint REST direto (`acao='VINCULAR'` força a tentativa).

### Vínculo manual pedido↔nota (Leva A, Mai/2026)

Quando o Sankhya não popula TGFVAR (caso real 111975/111976: pedido e nota emitidos separadamente no mesmo dia, mesmo cliente, mesmo valor, sem fluxo "atender pedido"), o operador pode pareá-los manualmente no IAgro.

**Tabela auxiliar:** `AD_VINCULO_PEDIDO_NOTA` (DDL em `sankhya_integration/sql/AD_VINCULO_PEDIDO_NOTA.sql`):

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_VINCULO_PEDIDO_NOTA` |
| `NUNOTA_PEDIDO` | NUMBER UNIQUE | TGFCAB TOP 34 |
| `NUNOTA_NOTA` | NUMBER UNIQUE | TGFCAB TOP 35/37 |
| `ORIGEM` | VARCHAR2(20) | `VINCULADO` (Leva A) ou `PEDIDO_RETROATIVO` (Leva B planejada) |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM`, `OBSERVACAO` | — | Audit completo |

**Fluxo operacional:**
1. Nota órfã aparece em Faturado com badge `ÓRFÃ` + botão "Vincular a pedido…"
2. Click no botão abre modal listando candidatos via `consultar_candidatos_pedido_para_nota` (heurística: mesmo CODPARC+CODEMP, DTNEG ±1/+7 dias, valor próximo). Também permite inserir NUNOTA manualmente.
3. Operador confirma → POST `/api/vinculo/criar/` → INSERT em `AD_VINCULO_PEDIDO_NOTA` com `ORIGEM='VINCULADO'`
4. Nota some das órfãs; pedido passa a aparecer em Faturado com `vinculo_origem='MANUAL'` e badge `FATURADO Nota Y · MANUAL`
5. **Reversível:** botão "Desfazer" no badge MANUAL chama `/api/vinculo/remover/` → DELETE da linha

**Funções service** (`oracle_conn.py`):
- `consultar_candidatos_pedido_para_nota(nunota_nota, limite=10)` — lista pedidos órfãos pareáveis
- `inserir_vinculo_manual_pedido_nota(nunota_pedido, nunota_nota, codusu, nomeusu, observacao)` — valida e cria vínculo
- `remover_vinculo_manual_pedido_nota(nunota_pedido OR nunota_nota)` — desfaz

**Endpoints:**
- `GET  /sankhya/rastreio/api/vinculo/candidatos/?nunota_nota=X`
- `POST /sankhya/rastreio/api/vinculo/criar/`
- `POST /sankhya/rastreio/api/vinculo/remover/`

**Audit:** `RastreioAudit.acao = 'VINCULAR_MANUAL'` ou `'DESVINCULAR_MANUAL'`, `detalhe` JSON com `{nunota_pedido, nunota_nota, vinculo_id, origem}`.

**Por que tabela auxiliar e não TGFVAR:** TGFVAR é populada por trigger interna do Sankhya (TRG_INC_TGFVAR), com cascata em TGMTRA (movimentação financeira/meta-orçamento) e TGFITE.QTDENTREGUE. INSERT manual é arriscado — ver gotchas. A tabela auxiliar IAgro vive paralela, é lida em UNION com TGFVAR na consulta principal.

### Pedido retroativo a partir de nota órfã (Leva B, Mai/2026)

Para o caso da nota órfã que **não tem pedido pareável** no banco (caso real 111825 — venda direta sem pedido, NUMNOTA 6242). O IAgro cria um pedido TOP 34 espelhando os itens da nota e grava o vínculo automaticamente.

**Função service:** `criar_pedido_retroativo_a_partir_de_nota(nunota_nota, codusu, nomeusu)` em [oracle_conn.py](../../sankhya_integration/services/oracle_conn.py).

**Fluxo:**
1. Operador clica "Criar pedido retroativo" no card da nota órfã.
2. Modal de confirmação.
3. POST `/sankhya/rastreio/api/vinculo/criar-pedido-retroativo/`
4. Backend (atômico — tudo num único commit):
   - Lê TGFCAB+TGFITE da nota
   - Cria TGFCAB TOP 34 via `inserir_cabecalho_nota_banco` (CODEMP, CODPARC, CODTIPVENDA, DTNEG copiados; CODNAT=10010100)
   - Cria 1 TGFITE por item via `inserir_item_nota_banco(gerar_lote_auto=False)` (CODPROD, QTDNEG, VLRUNIT, CODVOL copiados; CODAGREGACAO=NULL)
   - `recalcular_totais_nota_banco`
   - INSERT em `AD_VINCULO_PEDIDO_NOTA` com `ORIGEM='PEDIDO_RETROATIVO'`
5. Nota some das órfãs; pedido novo aparece em Faturado com badge `FATURADO Nota Y · RETROATIVO` (roxo).
6. Operador vincula lote normalmente no pedido novo.

**Desfazer (reversão completa):** botão "Desfazer" no badge RETROATIVO chama `remover_vinculo_manual_pedido_nota`. Quando `ORIGEM='PEDIDO_RETROATIVO'`:
- Valida que nenhum item do pedido tem CODAGREGACAO atribuído. Se tiver, bloqueia com erro `"desvincule todos os lotes antes de desfazer"`.
- DELETE em TGFITE → DELETE em TGFCAB → DELETE em AD_VINCULO_PEDIDO_NOTA, tudo no mesmo commit.
- A nota volta a aparecer como ÓRFÃ.

**Endpoint:** `POST /sankhya/rastreio/api/vinculo/criar-pedido-retroativo/`

**Audit:** `RastreioAudit.acao = 'CRIAR_PEDIDO_RETROATIVO'`, `detalhe` JSON com `{nunota_pedido_novo, nunota_nota, vinculo_id, qtd_itens, origem='PEDIDO_RETROATIVO'}`.

### Mudanças no backend

| Função | Mudança |
|---|---|
| `atribuir_lote_item_pedido(nunota, sequencia, codagregacao, qtd)` | Aceita: (a) TOP 34 com STATUSNOTA != 'E'; (b) TOP 35/37 STATUSNOTA='L' **sem TGFVAR par** (nota órfã). TOP 35/37 com TGFVAR par é bloqueado (operador deve trabalhar pelo pedido). SPLIT funciona normal — qtd parcial cria nova SEQ na TGFITE. Sem escrita em TGFVAR |
| `desvincular_lote_item_pedido(nunota, sequencia)` | Mesma matriz de aceitação. MERGE com outra linha pendente do mesmo CODPROD continua valendo |
| `consultar_pedidos_abertos_para_atribuicao` | Lista TOP 34 (pedidos) + TOP 35/37 órfãs. Filtros `mostrar_pendentes` / `mostrar_faturados` controlam quais entram. Adiciona `nota_numnota`, `nota_nunota` (via subquery TGFVAR) e `tipo_linha` (PEDIDO ou NOTA_ORFA) |

### Mudanças no frontend

- Cards de pedido faturado: badge laranja `FATURADO Nota Y` (Y = NUMNOTA da nota correlata via TGFVAR) + borda esquerda âmbar
- Tooltip explica: "Pedido já faturado pelo Sankhya. A rastreabilidade continua editável no pedido — a nota TOP 35/37 não é alterada"
- Endpoint único `/atribuir-lote/` e `/desvincular-lote/` (endpoints `/atribuir-finalizado/` e `/desvincular-finalizado/` foram aposentados)
- Modal de vínculos de lote: TOP 34 sempre desvinculável (independente de STATUSNOTA). TOP 35/37 (vinculação Sankhya direta, raríssimo) aparece como `NOTA SANKHYA` cinza não-desvinculável

### Audit em `RastreioAudit`

- Operação registrada normalmente (`ATRIBUIR` ou `DESVINCULAR`). Sem campo de propagação — não há propagação a registrar.
- O detalhe inclui `operacao` (`UPDATE` ou `SPLIT`) e `nova_sequencia` quando split — útil pra rastrear retroativamente quem mexeu e o que.

### Histórico — Fase 2 com TGFVAR (aposentada em 2026-05-11)

Houve uma primeira implementação que escrevia em TGFITE dos dois lados (pedido + nota) propagando via `_localizar_par_via_tgfvar()`. Funcionava pra atribuir/desvincular total, mas **não suportava SPLIT** porque exigiria INSERT em TGFVAR (tabela populada por trigger Sankhya — análise das 6 triggers `TRG_*_TGFVAR` mostrou cascata em TGMTRA, metas e orçamento). Foi aposentada no mesmo mês quando ficou claro que (a) o caso de uso real exige SPLIT e (b) o XML da NFe não exige `<rastro>` — então não precisa propagar pra nota de forma alguma. Funções `atribuir_lote_pedido_finalizado`, `desvincular_lote_pedido_finalizado` e helper `_localizar_par_via_tgfvar` foram removidos.

---

## Etiquetas SafeTrace/IAgro (Mai/2026)

Impressão de etiquetas de rastreabilidade 100×50mm landscape pra impressora térmica **Zebra ZD220**. 1 etiqueta = 1 caixa do pedido. Operador imprime no momento da expedição (todos os pedidos com lote vinculado).

### Layout da etiqueta

```
+---------------------------------------------+
| NOME DO PRODUTO (bold 11pt)        | IAgro  |
| Fornecedor: ...                    | rastreio
| CNPJ/CPF: 21.297.713/0001-39       | [QR]   |
| LAT: ...    LONG: ...              |        |
| Endereco: ... | CEP: ...           |        |
| Codigo do Fornecedor: ...          |        |
| Peso Liquido: 16 KG                |        |
| Data de Producao/Consolidacao: ... |        |
| Lote: 112327S01D260512             |        |
| Origem: BRASIL                     |        |
|                                             |
|        [EAN13 barcode — TGFPRO.REFERENCIA]  |
| ◀◀  PRODUTO COM ORIGEM RASTREADA  ▶▶        |
+---------------------------------------------+
```

- **Esquerda**: bloco texto com dados do produto + empresa emissora (`TSIEMP`) + lote
- **Sup. direita**: texto "IAgro / rastreio" + QR code apontando pra `URL_RASTREIO_PUBLICA` no `.env` (placeholder até definir URL pública real)
- **Meio direita**: código de barras EAN13 do produto (de `TGFPRO.REFERENCIA`). Se vazio/inválido, etiqueta sai sem barcode
- **Rodapé**: faixa preta com texto branco entre setas

### Fluxo de impressão

1. Operador no Rastreio vê os pedidos com lote vinculado
2. Botão 🖨 (verde Agromil, `.btn-etiqueta`) aparece no **header do pedido** (todos os itens) **e em cada produto-linha** (subset) — só quando `qtd_atribuida > 0`
3. Click → `_abrirPdfEtiquetas(nunota, codprod?)` → frontend faz `GET /api/resolver-peso/` primeiro
   - Sem ambiguidade: abre PDF direto em aba nova
   - Lote com 2+ pesos na TOP 26 (ex: tomate em caixas de 22kg e 20kg): abre **modal de escolha** com radios por SEQ
   - Operador escolhe → PDF abre com `?pesos=seq:val,seq:val`
4. `Ctrl+P` → Zebra ZD220 (na primeira vez; depois fica salva)

Cálculo do nº de etiquetas: `math.ceil(qtd_total_kg / peso_caixa_kg)`. Ex: 300 kg ÷ caixa de 10 kg = 30 etiquetas; 305 kg ÷ 10 = 31 (a última caixa fracionária também rotula).

### Resolução do peso da caixa (Mai/2026 — 2026-05-16, refatorado)

**Coerência com Entrada/Comercial:** Rastreio passa a usar `TGFITE.PESO` em vez de `QTDFIXADA` na TOP 34/35/37/30/36. `PESO` é o campo canônico do peso/caixa em todas as etapas (Entrada TOP 11, Classificação TOP 26, Vale TOP 13, agora Rastreio também). `QTDFIXADA` na TOP 34/35 era populada com zeros default pelo Sankhya nativo — IAgro para de poluir esse campo.

**Origem do peso por linha TGFITE** (em cascata, frontend e backend acordados):

| Prioridade | Origem | Quando |
|---|---|---|
| 1 | Override do modal de escolha | TOP 26 tem 2+ pesos, operador escolheu por SEQ |
| 2 | `TGFITE.PESO` próprio da linha | Operador digitou no modal de vínculo |
| 3 | `SELECT DISTINCT PESO` da TOP 26 do mesmo lote (1 único) | Fallback automático |
| 4 | TOP 26 com 2+ pesos sem override | Modal de escolha (não gera PDF até resolver) |
| 5 | Nada | Erro humanizado pedindo override manual |

**Campo no modal de vínculo agora é OPCIONAL** (era obrigatório até 2026-05-15). Frontend mostra "opcional — usa o da classificação". `TGFITE.PESO` recebe `NULL` quando operador deixa em branco.

**Split por peso = N vínculos (mesma mecânica do SPLIT por qtd):**

```
Pedido 4567 pede 800kg de tomate; lote tem 22kg e 20kg na TOP 26.

Operador vincula 500kg do lote no peso 22:
 → SPLIT (qtd 500 < qtdneg 800)
 → UPDATE SEQ 5: QTDNEG=300, PESO=NULL (linha pendente)
 → INSERT SEQ 25: QTDNEG=500, PESO=22, lote vinculado

Operador vincula 300kg restantes no peso 20:
 → UPDATE total (300 == 300)
 → UPDATE SEQ 5: PESO=20, lote vinculado

Resultado: 23 etiquetas de 22kg + 14 de 20kg.
```

Pedidos vinculados antes (com `QTDFIXADA` populada) **continuam funcionando se a TOP 26 do lote tem peso** — sistema cai automaticamente no fallback. Sem TOP 26 com peso, operador re-vincula informando manualmente. Sem backfill SQL necessário.

### Endpoints

| Endpoint | Função |
|---|---|
| `GET /api/etiqueta-pdf/?nunota=X[&codprod=Y][&pesos=seq:val,...]` | Gera PDF. Retorna 409 + `itens_pendentes` se alguma linha precisa de escolha sem override |
| `GET /api/resolver-peso/?nunota=X[&codprod=Y]` | **Novo (2026-05-16).** Frontend chama antes do PDF pra decidir entre abrir direto ou mostrar modal. Retorna `precisa_escolha` + lista por linha com `pesos_top26` |

### Arquivos

| Arquivo | Função |
|---|---|
| `services/etiqueta_lote.py` | `gerar_pdf_etiquetas(pedido, itens_com_copias) -> bytes`. Reportlab + qrcode + Ean13BarcodeWidget |
| `services/oracle_conn.py` | `consultar_dados_etiqueta_pedido` (leitura) + `calcular_qtd_etiquetas` (helper) + alterações em `atribuir_lote_item_pedido`/`desvincular_lote_item_pedido` |
| `views.py` | `api_rastreio_etiqueta_pdf` — retorna `HttpResponse(content_type='application/pdf')` inline |
| `urls.py` | rota `/sankhya/rastreio/api/etiqueta-pdf/` |
| `rastreio.html` | modal de transferência ganhou campo `inputQtdFixadaTransfer` (obrigatório) |
| `rastreio.js` | helpers `_renderEtiquetaBtn`, listeners do botão 🖨 e validação do peso |
| `rastreio.css` | `.btn-etiqueta` (verde Agromil, sempre visível) + `.input-group-pesoCx` (estilo do campo) |
| `tests/test_etiqueta_lote.py` | 17 tests: helper, render, view, regressão B1/B2 |

### Configuração

```dotenv
# .env
URL_RASTREIO_PUBLICA=http://localhost:8000/rastreio-publico/{lote}
```

`{lote}` é substituído pelo `CODAGREGACAO` em runtime. Quando a URL pública existir (Agromil definir hostname), trocar o `.env` + restart NSSM — nenhuma mudança de código.

### Dependência

```text
qrcode>=7.4.2
```

`reportlab` já é dependência do projeto.
