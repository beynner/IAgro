# Mapa de Blocos do script.js

Este documento descreve os principais blocos funcionais existentes em `sankhya_integration/static/sankhya_integration/script.js`. Cada seção informa o intervalo de linhas, as responsabilidades centrais e os helpers expostos, facilitando futuras otimizações de maneira segmentada.

## Bootstrap do portal, overlay e lista infinita ([script.js#L1-L400](sankhya_integration/static/sankhya_integration/script.js#L1-L400))
- Inicializa `window.__IA_PAGE__`, o controlador de overlay compartilhado (`IAOverlay`), o `postJSON` com CSRF e os flags contextuais de dashboard/portal.
- `initPortalPage()` conecta a tabela de notas: pré-carrega o painel (`panelLoadItems`), faz prefetch com cache, aplica proteções de exclusão, ativa scroll infinito (`loadNextPage` + `onScroll`) e navegação por teclado (`setActive`, `applySelection`).
- Duplo clique abre os modais (`openCabModalForEdit`, `showItemsModal`) quando disponíveis; caso contrário, cai na página central.
- Ajustes de UX: prefetch em hover, abertura automática de modal para notas recém-criadas e controle do botão de exclusão conforme seleção.

## Automação do formulário de filtros e paginação ([script.js#L497-L743](sankhya_integration/static/sankhya_integration/script.js#L497-L743))
- `applyFilters()` centraliza o envio do formulário, garantindo que inputs com debounce, Enter e botões de recarregar usem o mesmo fluxo.
- Comportamentos por campo: reset completo, cópia dos valores visíveis (typeahead) para os inputs ocultos, sincronização entre datas inicial/final, busca debounced de pedido e aplicação automática do campo `days`.
- `goToPage()` mantém os filtros ao navegar pelos controles de paginação.

## Widgets de typeahead para parceiro/produto ([script.js#L744-L838](sankhya_integration/static/sankhya_integration/script.js#L744-L838))
- Os campos `parcSearch` e `prodSearch` compartilham o mesmo padrão: requisições remotas com debounce, navegação por teclado dentro do dropdown, clique para selecionar e envio automático via `applyFilters()`.
- Ambos tratam busca por código ou descrição e alimentam os inputs ocultos esperados pelo backend.

## Modal rápido de TOP ([script.js#L839-L870](sankhya_integration/static/sankhya_integration/script.js#L839-L870))
- Lista `/sankhya/top/search/` com navegação de teclado (`moveTopSel`), Enter para confirmar (`pickTopSel`) e cliques que abrem diretamente a Central com a TOP escolhida.

## Modal de Cabeçalho + helper attachTA reutilizável ([script.js#L889-L1180](sankhya_integration/static/sankhya_integration/script.js#L889-L1180))
- `_setOverlayVisible`, `showCabModal`, `openCabModalForEdit` e `hideCabModal` orchestram o formulário de cabeçalho: carregam dados do TGFCAB, mantêm overlays exclusivos e tratam Salvar/Cancelar sem recarregar.
- `attachTA()` encapsula o comportamento dropdown/typeahead usado em Parceiro, TOP, Natureza e Centro de Custo dentro do modal.
- Handlers globais de teclado (Enter para salvar, bloqueios quando há dropdown aberto) evitam envios acidentais durante navegação nas sugestões.
- Helpers de feedback (`showToast`, `handleValeLockedError`) exibem mensagens e bloqueios de vale compartilhados pelos modais.

## Acoplamento e ciclo de vida do modal de Itens ([script.js#L1056-L1318](sankhya_integration/static/sankhya_integration/script.js#L1056-L1318))
- `showItemsModal()`/`hideItemsModal()` cuidam de escurecer cabeçalho, foco, renderização cache-first, abort de Fetch e layout (cabeçalho vai para a esquerda, card de itens ocupa a coluna central).
- Utilidades de animação (`getViewportTopOffset`, `animateHeaderToLeft`, `restoreHeaderPosition`) garantem o encaixe com a barra fixa.
- `_setDimmed`, `showRodapeModal` e `hideRodapeModal` reaproveitam o mesmo modelo para o editor de rodapé.

## Helpers de estado da Classificação e formatação ([script.js#L1350-L1491](sankhya_integration/static/sankhya_integration/script.js#L1350-L1491))
- `markInvalidField`, `setItemClassificaState`, `requireItemClassificaState` e `setItemAddBtnMode` tornam explícito o toggle de classificação em todo o UI.
- Funções de parsing/formatação (`parseFlexibleNumber`, `formatBR1`, `formatDateBR`, `normalizeNunota`, `clearItemsList`) mantêm valores no formato local tanto na lista quanto nos modais.

## Gerenciamento da lista de itens e detecção de duplicados ([script.js#L1491-L1861](sankhya_integration/static/sankhya_integration/script.js#L1491-L1861))
- `addItemRowToList`, `hasDuplicateItemInList` e os formatadores de `qtd/peso/total` montam a grade de itens do modal, eliminando duplicidades por sequência/volume.
- `fetchLotes`, `vshow/vhide`, `checkVolumeClassification` e `recalcItemTotal` alimentam o autocomplete de lote/volume, validam classificação e recalculam totais ao editar quantidade/peso.

## Sugestões inteligentes para lote/volume ([script.js#L1755-L1861](sankhya_integration/static/sankhya_integration/script.js#L1755-L1861))
- Um IIFE cria dropdowns de lote + volume, com suporte a teclado e sincronização imediata com inputs ocultos antes da validação.

## Renderizador de gráficos (canvas) da distribuição ([script.js#L2209-L2544](sankhya_integration/static/sankhya_integration/script.js#L2209-L2544))
- `ensureSize` e `render` desenham gráficos responsivos que resumem métricas de distribuição/classificação na barra lateral do portal.
- Controles de rádio acessíveis (`setActive`, `selectActive`, `moveActive`) mantêm os dropdowns customizados navegáveis por teclado.

## Bloqueio de entrada/vale, totais e sincronização de cabeçalho ([script.js#L2843-L3906](sankhya_integration/static/sankhya_integration/script.js#L2843-L3906))
- `applyEntradaLockState`, `applyValeToEntrada` e `applyItemToEntrada` fazem a ponte entre lista do portal e vales, bloqueando edição quando o backend sinaliza.
- Helpers dessa região mantêm totais, projeções e resumos alinhados sempre que o usuário alterna entre projeção e faturado.

## Parsing de filtros + agrupamentos do dashboard comercial ([script.js#L3084-L3679](sankhya_integration/static/sankhya_integration/script.js#L3084-L3679))
- `parseFilters`, `fmtDate`, `fmtQty` e `resolveListaQuantidade` transformam a querystring em objetos de filtro estruturados.
- `extractHeaderKey`, `captureGroupState`, `applyGroupState` e `renderListaRows` controlam o acordeão agrupado (expandir/recolher todos, pré-seleção via URL, reconstrução de HTML).

## Fluxo Vale → Entrada ([script.js#L3733-L4337](sankhya_integration/static/sankhya_integration/script.js#L3733-L4337))
- `applyValeToEntrada`, `applyItemToEntrada` e `renderClassificacaoCard` definem como linhas do vale preenchem as cartas de entrada/classificação, disparando KPIs e integrações com helpers `window.__DIST_*`.

## Refresh do UI de Vale + modal de observação ([script.js#L7010-L11679](sankhya_integration/static/sankhya_integration/script.js#L7010-L11679))
- `refreshValeUI`, `syncValeObservationButton`, `openValeObservacaoModal` e `closeValeObservacaoModal` mantêm o drawer de observação, incluindo o snapshot em `window.__CURRENT_VALE_OBSERVACAO`.
- `collectValePricesSnapshot`, `AutoSaveQueue`, `sleep` e `ensureCostCoherence` tratam autosave, debounce e reconciliação dos ajustes de preço/custo extra.

## Custos e KPIs (Extra Médio, Resumo Financeiro) ([script.js#L12564-L12931](sankhya_integration/static/sankhya_integration/script.js#L12564-L12931))
- `ensureCostCoherence`, `seedExtraCustoKg`, `syncFromClass`, `updateCostDisplays`, `recalcAllocation`, `updateQtyMiniCard`, `updateKpiMini5`, `updateResumoFinanceiro` e `applyTotalOverride` mantêm todos os cards dependentes sincronizados após mudanças de preço/peso.

## Infraestrutura global de toast e tooltip ([script.js#L13336-L14837](sankhya_integration/static/sankhya_integration/script.js#L13336-L14837))
- A implementação alternativa de `showToast`, além de `buildContent`, `showAt`, `hide` e `recalc`, provê notificações e tooltips leves reutilizadas no portal e no dashboard.

## Rabicho utilitário: querystring + helpers ([script.js#L14803-L15526](sankhya_integration/static/sankhya_integration/script.js#L14803-L15526))
- `getQS` e funções relacionadas encapsulam leitura/escrita da URL para que todos os blocos usem a mesma base ao ajustar filtros ou estados.

### Como usar este mapa
1. Identifique o módulo que deseja revisar (ex.: autosave do vale, filtros do portal) e vá até o intervalo indicado.
2. Dentro dele, procure pelos helpers listados para entender as responsabilidades exatas.
3. Ao refatorar, mantenha os limites de cada bloco para evitar regressões—quase todos expõem hooks (`window.__*`) consumidos em outras áreas.
