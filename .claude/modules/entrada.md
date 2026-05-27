# Módulo Entrada (TOP 11)

Recebimento e conferência de notas de compra com pesagem e controle de itens.

---

## Escopo

- Listar notas de compra (TOP 11) recebidas
- Conferir itens linha a linha
- Registrar pesagem (`AD_PESO`) e quantidade conferida (`AD_QTDCONFERIDA`)
- Salvar item parcial e finalizar item
- Geração automática de lote no formato `NUNOTAS{SEQ}D{YYMMDD}` no campo `CODAGREGACAO` da TGFITE

---

## URL e acesso

| Rota | Acesso |
|---|---|
| `/sankhya/compras/portal/` | Grupos `1`, `6`, `8` |

---

## Views principais (`views.py`)

| View | Propósito |
|---|---|
| `view_portal_entradas` | Página HTML do portal |
| `api_listar_itens_nota` | Lista itens de uma nota |
| `item_save` | Salva item (UPDATE de peso/qtd) |
| `item_finalize` | Finaliza item (status conferido) |

---

## Funções de `oracle_conn.py` usadas

- `inserir_cabecalho_nota_banco` (com auto-cura de `AD_NUMPEDIDOORIG`)
- `inserir_item_nota_banco(..., gerar_lote_auto=True)` — gera lote automaticamente
- `atualizar_cabecalho_nota_banco` (com auto-cura)
- `atualizar_item_nota_banco`
- `recalcular_totais_nota_banco`
- `listar_itens_por_nota` — retorno por índice (ver schema.md §9)

---

## Regras específicas

- **Lote auto-gerado** no formato `NUNOTAS{SEQ}D{YYMMDD}` — diferente da Venda, que aceita lote livre ou NULL.
- Auto-cura de `AD_NUMPEDIDOORIG` em `atualizar_cabecalho_nota_banco` e `atualizar_item_nota_banco` é **específica deste módulo** — não reutilizar na Venda nem no Rastreio.
- Conferência atualiza `AD_QTDCONFERIDA` e `AD_PESO` na TGFITE.

---

## Avaria do fornecedor em item NÃO-classificável (Mai/2026 — 2026-05-19, refinado 2026-05-20)

Itens com `GERAPRODUCAO <> 'S'` (in natura direto pra TOP 13, sem passar pela Classificação) agora têm onde registrar descarte do fornecedor — antes não tinha tela e o histórico era perdido (operador só conseguia reduzir QTDNEG no vale Comercial).

### Coluna "Avaria forn." no modal de itens

Tabela "Produtos inseridos" do `cabItemsCard` ganhou coluna entre `Total kg` e ações:

| `GERAPRODUCAO` | Comportamento da célula |
|---|---|
| `S` (classificável) | Mostra `—` cinza. Avaria continua sendo gerenciada na Classificação (campo `AD_QTDAVARIA` via `atualizar_descarte_origem`) |
| `N` ou NULL (não-classificável) | Input numérico amarelado **com auto-save no `blur`/Enter** — sem botão dedicado. Feedback: borda âmbar durante salvamento, verde 1.5s no sucesso, vermelha em falha |

Inputs `<input type="number">` sem spinners (CSS hide). Largura 95px pra exibir números com casa decimal sem cortar.

### Backend — endpoint dedicado (escapa da trava de edição)

A trava de TOP 13/26 (em `api_salvar_item_nota` de [views.py](../../sankhya_integration/views.py)) bloqueia QUALQUER UPDATE em item da TOP 11 quando já existe TOP 13 ou 26 com o lote. Mas avaria pode ser registrada **depois** do vale — operador descobre durante o faturamento. Por isso o caminho foge da trava:

| Endpoint | Função service | Operação |
|---|---|---|
| `GET  /sankhya/compras/api/avarias-fornecedor/?nunota=N` | `consultar_avarias_fornecedor_da_nota(nunota)` | Retorna `{sequencia: AD_QTDAVARIA}` da nota — alimenta a coluna no carregar |
| `POST /sankhya/compras/api/avaria-fornecedor/` | `atualizar_avaria_fornecedor_naoclass(nunota, sequencia, qtd, codusu, nomeusu)` | UPDATE `TGFITE.AD_QTDAVARIA` com filtro `GERAPRODUCAO <> 'S'` |

### Validações no service

- `qtd >= 0`
- `qtd <= QTDNEG` do item
- Filtra `c.CODTIPOPER = 11` (só TOP 11)
- Filtra `GERAPRODUCAO <> 'S'` (defesa em profundidade contra UPDATE em item classificável)
- **Trava B10** (Mai/2026 — 2026-05-20): se vale TOP 13 do pedido tem TGFFIN gerado, REJEITA com mensagem humanizada `"Vale já faturado pra essa entrada (NUFIN=X). Desfature antes de alterar a avaria do fornecedor."` — evita inconsistência com TGFCAB TOP 30 gerada no faturamento
- Invalida cache Rastreio (`invalidar_cache_rastreio()`) pra perna E refletir na próxima leitura
- Audit `AVARIA_FORNECEDOR` em `AD_AUDITORIA_GERAL` (snapshot antes/depois)

### Impacto no saldo

Perna E (`AVARIA_FORNECEDOR`) da view `ANDRE_IAGRO_SALDO_LOTE` reflete o novo valor. **Saldo vendável NÃO muda diretamente pela perna E** — ela é informativa, fora da fórmula de `QTD_DISPONIVEL`.

O desconto efetivo no estoque acontece via Comercial (modal Faturamento):

- **📌 Absorver** → backend gera TGFCAB TOP 30 (avaria interna) ao FATURAR, que desconta via **perna D** da view (`AVARIA_INTERNA`)
- **📉 Descontar** → vale TOP 13 fica com qtd LÍQUIDA (Comercial cobra fornecedor por fora; estoque coerente pela qtd reduzida no próprio vale)

Detalhes em [`comercial.md`](comercial.md) → "Toggle Descontar/Absorver com avaria interna automática".

### Espelhamento (Mai/2026, intocado)

A Classificação continua filtrando `GERAPRODUCAO='S'` em `atualizar_descarte_origem`. Sem conflito — cada módulo gerencia seu próprio universo de produtos.

---

## 📱 Redesign Mobile app-like (Mai/2026 — 2026-05-27)

Implementação completa pra operador usar no celular. Estratégia: HTML único com 2 containers paralelos (`.entrada-desktop` e `.entrada-mobile`), controlados por media query `body[data-active-module="entrada"]` em ≤900px. Desktop preservado 100% intacto.

### Estrutura mobile

| Componente | Arquivo |
|---|---|
| Template | `entrada.html` — bloco `.entrada-mobile` com 5 `<section class="m-screen">` + 3 `<div class="m-sheet">` |
| CSS | `entrada.css` — bloco "REDESIGN MOBILE-FIRST" com tokens `--m-*`, classes `.m-screen`, `.m-card-nota`, `.m-sheet`, `.m-fab`, etc |
| JS | `entrada_mobile.js` (~1300 linhas) — só ativa em viewport ≤900px |

### Telas mobile

1. **Lista de notas** (tela `lista`) — cards 1 linha (26px altura), avatar + nome + Pedido + data. Search bar client-side. Bottom nav (Notas · Buscar · Filtros · Mais)
2. **Detalhe da nota** (tela `detalhe`) — header com nome do fornecedor + lixeira excluir nota + edit cabeçalho. Lista de itens com cards de status. **Click no card de item abre o sheet "itens-nota" em modo EDIT** (reusa mesma tela de inserir, não tela separada)
3. **Conferir item** (tela `item`) — Qtd conferida + Peso da caixa (m_conf_*) + Avaria + Toggle Classifica. **Desabilitada na navegação atual** (Mai/2026 — 2026-05-27) — preservada no HTML/JS pra reimplementação futura. Click no card de item agora navega pro sheet de edição.

### Bottom sheets

- **Nova nota** (`data-sheet="nova-nota"`) — 7 campos espelhando `#cabModal` desktop (Empresa, Parceiro typeahead, Data, TopOper, Natureza, CentroCusto, Observação). Após salvar, abre sheet de Itens
- **Itens da nota** (`data-sheet="itens-nota"`) — espelha `#cabItemsCard` desktop. Produto (typeahead) + Vol + Qtd + Peso + Total kg (calculado) + Classifica. Lista de itens inseridos com tap pra editar + lixeira (apenas_checar antes do confirm). **Em modo EDIT**: Produto + toggles Classifica ficam `disabled` (paridade desktop entrada.js:1625-1634)
- **Cabeçalho** (`data-sheet="cabec"`) — editar nota existente. Campos preenchidos via `?ajax_header=1`. Parceiro/Empresa/TOP/Natureza/Cencus readonly. Data + Observação editáveis. Acessível também pelo botão de swipe na tela 1 (lápis azul)

### Gestos touch

- **Swipe-to-back** — arrastar da esquerda pra direita nas telas internas volta uma tela
- **Swipe-to-edit + delete** nos cards de nota (tela 1) — arrastar pra esquerda revela **2 botões 44px** (88px total):
  - **EDITAR cabeçalho** (azul `#2563eb`, `ph-pencil-simple`) à esquerda — popula `ESTADO_NOTA` + abre sheet `cabec`
  - **EXCLUIR nota** (vermelho, `ph-trash`) à direita — fluxo apenas_checar → confirm → POST
- **Swipe-to-delete** nos cards de item (tela 2) — arrastar pra esquerda revela 1 botão 44px (lixeira)
- **Reset automático**: ao trocar de tela (`setActiveScreen`) ou abrir qualquer sheet (`openSheet`), `fecharTodosSwipesNotas()` zera transforms — evita estado "preso" entre navegações

### FABs

| Tela | FAB principal | FAB secundário (acima) |
|---|---|---|
| 1 — Lista | `m_fabNova` verde 48px (`ph-plus`) → abre Nova nota | `m_fabAtualizar` azul 42px (`ph-arrows-clockwise`) → hard refresh |
| 2 — Detalhe | `m_fabItem` verde 48px (`ph-plus`) → abre sheet Itens | `m_fabAtualizarItens` azul 42px (`ph-arrows-clockwise`) → `carregarItens(nunota, pedido)` sem reload |

Spinner via classe `.is-loading` + `@keyframes m-spin 0.8s linear infinite`. **Ícone correto: `ph-arrows-clockwise` (plural, 2 setas)** — `ph-arrow-clockwise` (singular) é diferente.

### Paridade completa com web

Levantamento exaustivo + 3 lotes implementados ([`CLAUDE.md`](../../CLAUDE.md) → "Redesign Mobile app-like"):

| Item | Implementação mobile | Equivalente desktop |
|---|---|---|
| Auto-cura cabeçalho órfão | `fecharSheetItens()` checa `ESTADO_ITENS.cabRecemCriado && items.length === 0` → POST `/sankhya/nota/delete/` | `interceptarFechamentoCabecalho()` ([entrada.js:1072](../../sankhya_integration/static/sankhya_integration/entrada.js#L1072)) |
| Trava `apenas_checar` no delete item | 2 POSTs em sequência (checar → confirm → real) | [entrada.js:1699](../../sankhya_integration/static/sankhya_integration/entrada.js#L1699) |
| Trava `apenas_checar` no delete nota | `excluirNotaPorId(nun)` reusável | [entrada.js:399](../../sankhya_integration/static/sankhya_integration/entrada.js#L399) |
| Vol != CX força peso=1 | `aplicarRegraVolume()` no input/change/blur | `checkVolumeClassification` ([entrada.js:2123](../../sankhya_integration/static/sankhya_integration/entrada.js#L2123)) |
| Blur no Vol vazio restaura "CX" | mesma função | [entrada.js:2158](../../sankhya_integration/static/sankhya_integration/entrada.js#L2158) |
| Campos inválidos com borda vermelha | `.is-invalid` class + `limparInvalidItem()` | [entrada.js:2229](../../sankhya_integration/static/sankhya_integration/entrada.js#L2229) |
| Vale lock 409 handling | `handleValeLockedError(status, body)` portado | [entrada.js:1210](../../sankhya_integration/static/sankhya_integration/entrada.js#L1210) |
| Avaria fornecedor inline | só em não-classificáveis. Auto-save no blur via POST `/sankhya/compras/api/avaria-fornecedor/`. Carrega via GET `?nunota=X` após render | [entrada.js:1840](../../sankhya_integration/static/sankhya_integration/entrada.js#L1840) |
| Editar item via tap | `bindItemEdits()` + `abrirEditItem()` popula form com seq + modo edit | duplo-clique ([entrada.js:1876](../../sankhya_integration/static/sankhya_integration/entrada.js#L1876)) |
| Detecção de duplicação | `hasDuplicateItemInList(codprod, codvol)` ignora própria linha em modo edit | [entrada.js:1756](../../sankhya_integration/static/sankhya_integration/entrada.js#L1756) |
| Enter em qtd/peso/produto dispara Add | listener `keydown` Enter em 3 inputs | [entrada.js:2179](../../sankhya_integration/static/sankhya_integration/entrada.js#L2179) |
| Cabeçalho excluído após último item | trata `jdel.cabecalho_excluido` → fecha sheet + reload | [entrada.js:1726](../../sankhya_integration/static/sankhya_integration/entrada.js#L1726) |
| Editar cabeçalho existente | sheet "cabec" com fetch `?ajax_header=1` → POST `/sankhya/header/update/` | [entrada.js:993](../../sankhya_integration/static/sankhya_integration/entrada.js#L993) |

### Bugs descobertos e corrigidos durante implementação (Mai/2026 — 2026-05-27)

Sessão de polish do mobile revelou várias armadilhas que valem registrar pra próximas implementações:

| # | Bug | Causa raiz | Fix |
|---|---|---|---|
| 1 | iPhone fazia zoom em inputs ao focar | `.m-field-input` tinha `font-size: 14px`. iOS Safari faz zoom em qualquer input com `font-size < 16px` | Subir pra **16px** ([entrada.css:1170](../../sankhya_integration/static/sankhya_integration/entrada.css#L1170)) |
| 2 | Total kg (calculado) sempre 100 quando Peso=23 | **2 inputs com `id="m_itemPeso"`** no DOM (tela 3 conferir + sheet itens). `document.getElementById` pegava só o primeiro (tela 3, escondida e vazia) | Renomear tela 3 pra prefixo `m_conf_*` (qtd/peso/avaria/nome/lote/pos). Validação anti-dup: `re.findall(r'id="([^"]+)"', html)` + Counter |
| 3 | Classifica? não ficava vermelho ao submit sem marcar | `document.querySelector('.m-toggle-row')` pegava o **primeiro** no DOM (tela 3, oculto). Sheet de itens não recebia `.is-invalid` | Helper `getToggleRowItens()` que escopa via `.m-toggle-btn[data-classifica-item].closest('.m-toggle-row')` |
| 4 | Edit de item pré-preenche só Produto e Vol; Qtd/Peso ficam vazios | `input[type=number]` rejeita strings com vírgula silenciosamente — `String(23.5).replace('.', ',')` = `"23,5"` → input vazio | Remover `.replace('.', ',')`. Sempre `String(num)` com ponto. Guards `isNaN` |
| 5 | Swipe permanecia aberto ao navegar e voltar | Nenhum hook fechava swipes em mudança de tela. Card ficava com `transform` e `data-swipeOpen='1'` permanente | `fecharTodosSwipesNotas()` chamada em `setActiveScreen` + `openSheet` |
| 6 | Display de Qtd mostrava "100 / 2.300 CX" | Layout antigo: `qtdConferida / qtdNeg + codvol` sem semântica | Novo: `<qtdUnidades> <CODVOL> / <totalKg> KG` quando peso>0 e vol!=KG. Label "PESO/CX" → "Peso/<codvol.toLowerCase()>" dinâmico |
| 7 | Cálculo QTDNEG no mobile divergia do desktop | Mobile fazia `vol === 'KG' ? qtd : qtd × peso`. Desktop sempre `qtd × peso` quando ambos > 0 | Alinhar com desktop: `(qtd > 0 && peso > 0) ? qtd × peso : qtd` em `salvarItem` + `recalcTotalItem` |
| 8 | Status icon "relógio" (ph-clock) poluía cards pendentes | Ícone aparecia em todos os cards | Tirar icon quando pendente. Em OK mantém `ph-check-circle` verde |
| 9 | Concluir do sheet de itens voltava pra tela 1 (entrada) | Sempre fazia `window.location.reload()` ao fechar | Em `fecharSheetItens`: se há `ESTADO_NOTA.nunota`, só `carregarItens(...)` (volta tela 2 com itens atualizados). Reload só em cenário "Nova nota" sem tela 2 |
| 10 | Botões de swipe muito largos (56px) | Operador relatou "atrapalha mais que ajuda" | Reduzir pra **44px** (touch target mínimo Apple). Ícone interno `font-size: 16px` |
| 11 | Display do total kg dentro do card desbalanceado | Qtd à esquerda, Peso à direita | Inverter: **Peso à esquerda, Qtd à direita** via `.m-stat--right` no segundo stat |
| 12 | Ícone do FAB Atualizar errado | Usei `ph-arrow-clockwise` (singular) — não existe / diferente | `ph-arrows-clockwise` (plural, 2 setas curvas) — mesmo da tela 1 |
| 13 | Filtro de busca escondia card mas botões de swipe ficavam pendurados | `card.style.display = 'none'` no `.m-card-nota` — botões absolutos (`__swipe-edit` + `__swipe-del`) vivem no wrapper externo, não no article | Esconder o **wrapper inteiro**: `card.closest('.m-card-nota-wrap').style.display = 'none'` |
| 14 | Comentário Django `{# ... #}` multi-line vazou no header | `{# ... #}` é single-line — quebrar em ≥ 2 linhas vaza no HTML | Remover comentário ou usar `{% comment %}...{% endcomment %}`. Doc fica em `.claude/*.md`, não inline no template |
| 15 | User badge no mobile só com texto sem identidade visual | Estilo padrão sem padding/cor consistente com Painel | Pílula verde claro `#f0f5ec` + texto verde escuro `#4a633a` uppercase (pendant do `.user-badge-inline` desktop) + link "Sair" vermelho |
| 16 | Lista mobile não tinha paginação infinita | `hidratarListaNotas` lia só os rows da página atual server-rendered (`?page=1`, 50 notas), sem hook pra próxima | `IntersectionObserver` em sentinela no fim da lista dispara `carregarMaisNotas()` que faz fetch `?page=N+1` da mesma view, parseia HTML, extrai `tr.row--click` + lê novo `data-has-next` |
| 17 | Botão Filtros não tinha indicador visual quando havia filtro aplicado | Sem feedback visual — operador não sabia que lista estava filtrada | `.has-filtros-ativos` no `.m-bottom-nav__item[data-nav="filtros"]` quando algum input do form desktop tem valor (start/end/nunota_ini/codparc/fabricante). CSS: ícone verde Agromil fill + bolinha vermelha no canto |
| 18 | iPhone — data inicial não replicava em data final | `if (!inputFim.value \|\| inputFim.value < v)` falhava quando dataFim já tinha valor anterior. Padrão da convenção é replicar SEMPRE | Replicar sempre sem comparar. Adicionar `input` listener além de `change` (iOS Safari só dispara `change` quando picker fecha) |
| 19 | Busca "ANDRE" trazia ROSILDO/PERBONI das páginas seguintes | `filtrarCards` só itera cards JÁ carregados. Lista infinita anexava cards novos da página 2/3 sem re-filtrar — entravam todos visíveis | Após `appendCardsNotas`, re-aplicar `filtrarCards()` se há termo de busca + disparar `autoPaginarComBusca` em loop (até 20 páginas = 1000 notas) pra cobrir base inteira durante a busca |
| 20 | Spinner "Carregando mais…" preso após fim da lista | `renderSentinela` recriava sentinela enquanto `pgInfinita.hasNext === true`. Quando auto-paginar com busca batia `AUTO_PAGINAR_MAX`, server ainda tinha próxima → hasNext permanecia true → spinner girava sem nada disparar | `renderSentinela` checa 2 condições: `!hasNext` OR `(temBusca && autoPaginarIters >= AUTO_PAGINAR_MAX)` — remove sentinela em ambos os casos |
| 21 | IntersectionObserver fazia cascata infinita (94 requests em 60s) | Cada nova sentinela aparecia DENTRO do viewport (cards anexados acima não pushavam pra fora). Observer detectava intersect e disparava imediatamente, sem operador rolar | Substituir por scroll listener tradicional em `m_listaScroll` — só dispara em scroll real (`scrollTop` comparado com `lastScrollTop`, ignora scroll pra cima). `autoPaginarComBusca` ganha `setTimeout 250ms` entre iterações + flag `autoPaginarTimer` cancelável quando operador limpa busca |
| 22 | Auto-paginar com busca parava após 1 página | `pgInfinita.carregando = false` setado **depois** de `appendCardsNotas` no `.then`. Quando appendCardsNotas chamava autoPaginarComBusca, guard `if (carregando) return` falhava → cadeia parava | Mover `pgInfinita.carregando = false` pra **antes** de `appendCardsNotas(rows)` no `.then` do fetch — libera a flag pra que o chain funcione |
| 23 | Sem deadline absoluto na auto-paginação com busca | Limite só por iterações (`AUTO_PAGINAR_MAX = 20`) — bases grandes podiam levar muito tempo, operador esperando | Adicionar `AUTO_PAGINAR_TIMEOUT_MS = 3000`. No input handler, seta `autoPaginarDeadline = Date.now() + 3000`. `autoPaginarComBusca` e `renderSentinela` checam `Date.now() > autoPaginarDeadline` e encerram a busca |
| 24 | Busca client-side com auto-paginação era ruim — operador via resultados aparecerem aos poucos página por página | Filtragem `[autoPaginar 20×]` puxava muita carga, ainda mostrava progressivo. Em bases grandes (>4700 notas) ficava muito lento e parte dos matches ficava fora do limite | **Refator Cat B (Mai/2026 — 2026-05-27)**: busca movida pro server. `listar_notas_compra_paginado` ganhou param `q` (LIKE em NOMEPARC OR NUNOTA OR NUMNOTA). `view_portal_entradas` aplica **default `days=90`** quando operador não passa filtro de data explícito — limita universo da base. Mobile faz fetch `?q=...&days=90` em 1 chamada com debounce 250ms, replace dos cards. Removidos: `filtrarCards`, `normalizar`, `autoPaginarComBusca`, `autoPaginarIters`, `autoPaginarTimer`, `autoPaginarDeadline`, `AUTO_PAGINAR_MAX`, `AUTO_PAGINAR_TIMEOUT_MS`. Token `buscaFetchToken` evita race quando operador digita rápido. **Placeholder do campo de busca**: `"Buscar fornecedor ou pedido (últimos 90 dias)"` — operador sabe da janela default sem precisar abrir filtro |

### Regras técnicas críticas (consolidação)

Documentadas em [`conventions.md`](../conventions.md) seção "📱 Redesign Mobile app-like". Resumo:

1. **`font-size: 16px` mínimo** em qualquer input (iOS zoom)
2. **`type=number` + `String(num)` com ponto** — vírgula rejeita silenciosamente
3. **IDs únicos por tela** — convenção de prefixo (m_item*, m_conf_*, m_edit*, m_filtro*). Validar via regex+Counter
4. **Seletores escopados** pra coleções compartilhadas (`.m-toggle-row`, `.m-toggle-btn`) — não usar `document.querySelector` direto
5. **Reset automático de swipes** em `setActiveScreen` + `openSheet`
6. **Listeners completos** em inputs: `input + change + blur + keyup`
7. **QTDNEG = qtd × peso** sempre (paridade desktop entrada.js:2269), nunca dependente de vol
8. **Cache busting** obrigatório (`?v=N` em CSS e JS) — bumpar a cada PR
9. **Restart NSSM** + hard refresh ao testar
10. **Swipe 44px** (touch target Apple) — 88px total quando há 2 botões (edit+del)

### Estados internos do mobile

- `ESTADO_NOTA` — nota selecionada na tela 2 (nunota, parc, pedido, dataNota, items, currentIdx, conferidosSet)
- `ESTADO_ITENS` — sheet de itens aberto (nunota, items, editandoSeq, cabRecemCriado)

### Tela de conferir item (tela 3)

Fluxo de "Salvar e próximo": após `POST /sankhya/item/save/` com QTDCONFERIDA, adiciona seq ao `conferidosSet`, busca próximo pendente via `encontrarProximoPendente(currentIdx)` (procura adiante depois wrap-around). Quando todos conferidos, volta pra tela 2 + toast "Nota completa ✓".

---

## Frontend

- **Template:** `entrada.html`
- **CSS:** `entrada.css` (também carregado globalmente pelo `base.html` por legado — ver gotchas)
- **JS:** `entrada.js`
- **Container interno:** `.entrada-grid` (flex, aside 320px + rightcol)

---

## Testes

- `test_views_entrada.py` — entrada, health, conversor de tipos
