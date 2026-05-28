# Convenções de Código

## Layout v2 — Sidebar + Content (Mai/2026)

> ✅ **Padrão atual.** Substituiu o layout antigo (`.wrap > .appbar > .main-layout > .ia-footer`).
> Aplicado a TODAS as telas autenticadas. Tela de login (`home_login.html`) é standalone.

### Estrutura

```html
<body class="app-shell" data-active-module="venda">
  <aside class="sidebar" id="appSidebar">       <!-- 200px expand / 56px collapse -->
    <div class="sidebar-header">… (logo + brand + chevron)</div>
    <nav class="sidebar-nav">… (nav-item por módulo)</nav>
    <div class="sidebar-footer">v1.2.0</div>
  </aside>

  <div class="app-content">
    <header class="content-header">             <!-- 56px altura -->
      <h1>TÍTULO DO MÓDULO</h1>
      … (block header_actions: botões específicos)
      <div class="user-badge-inline">… ANDRE</div>
      <a class="btn-logout-inline">Sair</a>
    </header>
    <main class="main-layout">                   <!-- area de conteúdo -->
      … (block content do módulo)
    </main>
    <footer class="ia-footer-inline">NexusGTi · v1.2.0</footer>
  </div>
</body>
```

### Blocos Django novos no `base.html`

| Block | Função |
|---|---|
| `{% block active_module %}<nome>{% endblock %}` | Nome do módulo pra marcar item ativo na sidebar (entrada, classificacao, comercial, venda, rastreio, email, combustivel, auditoria, home) |
| `{% block header_title %}` | Texto do `<h1>` no content-header (mantido do legado) |
| `{% block header_extras %}` | Elementos auxiliares ao lado do título (mantido) |
| `{% block header_actions %}` | Botões à direita (refresh, importar, etc) — novo |
| `{% block content %}` | Área principal — `<main class="main-layout">` (mantido) |
| `{% block extra_css %}` / `{% block extra_js %}` | Mantidos |

### Sidebar: toggle expand/collapse

- `IAgro.setupSidebar()` em `iagro_helpers.js` (chamado 1× no `base.html`)
- Botão chevron `#btnSidebarCollapse` no header da sidebar (só desktop)
- Estado persistido em `localStorage` chave `iagro:sidebar:collapsed:v1`
- Em ≤900px (tablet vertical / mobile), sidebar vira **off-canvas** com botão hambúrguer top-left e backdrop. Esc/click-fora fecham.

### Item ativo na sidebar

JS lê `body[data-active-module]` e adiciona `.active` no `.nav-item[data-mod="X"]` correspondente. Cada template de módulo define seu nome via `{% block active_module %}`.

### Card "Auditoria" condicional

Visível só pra grupos Diretoria (`1`) e Suporte (`6`):

```django
{% if "1" in request.session.grupos or "6" in request.session.grupos %}
<a href="/sankhya/auditoria/" class="nav-item" data-mod="auditoria">…</a>
{% endif %}
```

### Tela de login (não-logado)

`home_login.html` é **standalone** (não estende `base.html`). Layout centralizado com gradiente verde Agromil + card de login + animação shake em erro. CSS em `home.css` (seção `body.login-page`).

---

## 📱 Redesign Mobile app-like (Mai/2026 — 2026-05-26/27)

Estratégia pra módulos terem fluxo mobile próprio (não só responsivo) — PWA-ready. Módulos com redesign até hoje: **Entrada** e **Classificação**.

### Arquitetura — 2 containers paralelos no HTML

```html
<div class="{modulo}-portal">
  <div class="{modulo}-desktop">  <!-- layout original preservado -->
    ...
  </div>
  <div class="{modulo}-mobile">    <!-- novo layout mobile-first -->
    <section class="m-screen m-screen--lista is-active">...</section>
    <section class="m-screen m-screen--detalhe">...</section>
    ...
    <div class="m-sheet" data-sheet="filtros">...</div>
    <nav class="m-bottom-nav">...</nav>
    <button class="m-fab">...</button>
  </div>
</div>
```

CSS controla visibilidade via media query escopada:

```css
.{modulo}-mobile { display: none; }
.{modulo}-desktop { display: flex; ... }

@media (max-width: 900px) {
  body[data-active-module="{modulo}"] .{modulo}-desktop { display: none !important; }
  body[data-active-module="{modulo}"] .{modulo}-mobile { display: block; }
  body[data-active-module="{modulo}"] .content-header,
  body[data-active-module="{modulo}"] .ia-footer-inline { display: none; }
  body[data-active-module="{modulo}"] .main-layout { padding: 0 !important; overflow: hidden !important; }
}
```

### Classes `.m-*` padrão (paleta compartilhada via tokens)

| Classe | Função |
|---|---|
| `.m-screen` | Tela full-screen empilhada (1 visível por vez via `.is-active`). Transição `translateX 0.28s` |
| `.m-screen-header` | Header sticky 48px com back/title/actions |
| `.m-screen-body` | Body scrollável (overflow-y: auto + safe-area padding-bottom) |
| `.m-iconbtn` | Botão de ícone redondo 40px (touch target Apple guideline) |
| `.m-iconbtn--danger` | Variante vermelha (excluir) |
| `.m-card-nota` | Card 1 linha 26px altura — avatar circular 20px + nome + meta + chevron |
| `.m-card-nota-wrap` | Wrapper que esconde os botões de swipe (`.m-card-nota__swipe-edit` + `.m-card-nota__swipe-del`) atrás |
| `.m-card-nota__swipe-edit` | Botão swipe **editar** revelado à esquerda (azul `#2563eb`, 44px, `ph-pencil-simple`) |
| `.m-card-nota__swipe-del` | Botão swipe **excluir** revelado à direita (vermelho `var(--m-danger)`, 44px, `ph-trash`) |
| `.m-card-item` / `.m-card-item-wrap` | Versão pra cards de item da tela 2 — wrapper esconde só `.m-card-item__swipe-del` (44px) |
| `.m-card-item__swipe-del` | Botão swipe **excluir** item (vermelho, 44px) |
| `.m-stat` | Bloco label+valor dentro do card body (Peso, Qtd, etc) |
| `.m-stat--right` | Variante alinhada à direita (usada na Qtd do card-item — Peso à esquerda, Qtd à direita) |
| `.m-fab` | Floating action button 48px verde Agromil (primary, ação positiva: novo) |
| `.m-fab--secondary` | Variante 42px azul `#2563eb` posicionada 12px acima do FAB principal. Ícone `ph-arrows-clockwise` (Atualizar) com classe `.is-loading` aplica spinner via `@keyframes m-spin 0.8s linear infinite` |
| `.m-bottom-nav` | Nav fixo bottom 52px com `.m-bottom-nav__item` (ícone Phosphor + label) |
| `.m-sheet` | Bottom sheet com `.m-sheet__backdrop` + `.m-sheet__content` slide-up |
| `.m-sheet__content--tall` | Variante 92vh (forms longos) |
| `.m-field-input` | Input grande 42px (touch-first). **`font-size: 16px` obrigatório** (iOS faz zoom abaixo) |
| `.m-field-input--lg` | Variante 52px (input destaque) |
| `.m-field-input.is-invalid` | Borda vermelha + fundo `var(--m-danger-soft)` |
| `.m-toggle-row` | Container dos botões Sim/Não (escopo: usar seletor específico, **não `document.querySelector('.m-toggle-row')`** porque há ≥1 no DOM se houver telas múltiplas) |
| `.m-toggle-btn` | Botão de toggle binário — `.is-active` muda pra verde Agromil |
| `.m-toggle-row.is-invalid .m-toggle-btn` | Variante toda vermelha quando classifica obrigatória não selecionada |
| `.m-btn-primary` | Botão principal 46px verde Agromil |
| `.m-btn-secondary` | Botão secundário 48px transparente com borda |
| `.m-empty-state` | Estado vazio centralizado com ícone + texto |
| `.m-user-badge` | Badge do usuário no header das **telas principais** (lista) de cada módulo. **Pílula verde claro** (`#f0f5ec` fundo, `#4a633a` texto uppercase) com `ph-user` + nome — mesma identidade visual do `.user-badge-inline` do desktop (global.css). Some em telas internas |
| `.m-logout-link` | Link "Sair" vermelho ao lado do badge. Pendant do `.btn-logout-inline` do desktop. URL `{% url 'logout' %}` |

### Padronização de ícones Phosphor (regra única — não improvisar)

Mesma família que o desktop (regular + fill), mas com mapeamento fixo por ação no mobile:

| Ação | Ícone Phosphor | Cor / contexto |
|---|---|---|
| **Adicionar / Novo** (FAB primário) | `ph-plus` | verde Agromil |
| **Atualizar / Refresh** (FAB secundário) | `ph-arrows-clockwise` **(plural, 2 setas)** | azul `#2563eb` |
| **Editar** (swipe / botão lápis) | `ph-pencil-simple` | azul `#2563eb` |
| **Excluir** (swipe / lixeira) | `ph-trash` | vermelho `var(--m-danger)` |
| **Voltar** (header de tela) | `ph-arrow-left` | herda |
| **Fechar** (sheet / modal) | `ph-x` | herda |
| **Confirmar / OK** | `ph-check-circle` | verde |
| **Atenção / Avaria** | `ph-warning` | âmbar |
| **Lista / Notas** (bottom nav) | `ph-list-checks` | herda |
| **Buscar** (bottom nav) | `ph-magnifying-glass` | herda |
| **Filtros** (bottom nav) | `ph-funnel` | herda |
| **Mais opções** (bottom nav) | `ph-dots-three` | herda |
| **Hambúrguer / sidebar** | `ph-list` | herda |
| **QR / Scan** (em breve) | `ph-qr-code` | herda |
| **Spinner / carregando** | qualquer ícone + classe `.is-loading` (aplica `m-spin` animation) | — |

**Erro recorrente que sai do padrão**: `ph-arrow-clockwise` (singular) NÃO existe ou é diferente — usar `ph-arrows-clockwise` (plural com 2 setas) pra "Atualizar".

### Tokens (via `:root` no escopo `.{modulo}-mobile`)

```css
--m-bg:            #f8fafc;
--m-surface:       #ffffff;
--m-border:        #e5e7eb;
--m-border-soft:   #f1f5f9;
--m-text:          #1f2937;
--m-text-muted:    #6b7280;
--m-primary:       #5e7e4a;    /* verde Agromil */
--m-primary-dark:  #4a6e3e;
--m-primary-soft:  #eaf0e8;
--m-warning:       #d97706;
--m-warning-soft:  #fff7ed;
--m-danger:        #dc2626;
--m-danger-soft:   #fef2f2;
--m-success:       #16a34a;
--m-radius-sm:     7px;
--m-shadow:        0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
--m-header-h:      48px;
--m-bottom-nav-h:  52px;
--m-touch-target:  40px;
```

### JS — arquivo separado `{modulo}_mobile.js`

- Auto-ativação só se `window.matchMedia('(max-width: 900px)').matches`
- Estado interno em closure (não polui `window`)
- Reusa endpoints existentes do desktop (zero novo endpoint)
- Pra cada sheet, padrão `openSheet(name)` / `closeSheet(name)`
- Pra cada tela, padrão `pushScreen(name)` / `popScreen()` com `history.pushState` (back button Android funciona)

### Gestos touch

- **Swipe-to-back** — **OBRIGATÓRIO em TODA tela interna mobile** (qualquer `m-screen` diferente da `lista` raiz: detalhe, item, conferir, etc). `touchstart`/`touchmove`/`touchend` com threshold 35% da largura ou velocidade > 0.5px/ms. Detecta eixo dominante nos primeiros 10px (cancela se vertical pra deixar scroll funcionar). Implementação canônica: função `setupSwipeToBack()` que itera `Object.keys(screens)` ignorando `lista`, registra handlers em cada `m-screen`. Chamar 1× no boot. **Validar no iPhone real** — DevTools mobile do Chrome às vezes mascara bugs de touch. **NÃO aplicar a bottom sheets** — UX testado em Mai/2026 e descartado (gesto horizontal compete com edição de inputs e ficou confuso; bottom sheet fecha por `X` no header ou botão Fechar no footer)
- **Swipe-to-edit + delete** (ou view, armar, etc) nos cards — arrasta esquerda revela botões escondidos atrás:
  - **Cards de NOTA** (Entrada tela 1): 2 botões = **88px** (44 editar azul + 44 excluir vermelho). Threshold pra abrir: **44px** (50% do total)
  - **Cards de ITEM** (Entrada tela 2): 1 botão = **44px** (excluir vermelho). Threshold: **22px**
  - **Cards de LOTE** (Rastreio Mai/2026 — 2026-05-28): 2 botões = **88px** (44 armar verde + 44 olho azul). Threshold: **44px**
  - **Cards de ITEM de PEDIDO** (Rastreio Mai/2026 — 2026-05-28): 2 botões = **96px** (48 vincular verde + 48 olho azul). Threshold: **48px**
  - **Cards de VÍNCULO no sheet** (Rastreio Mai/2026 — 2026-05-28): 1 botão = **56px** (desvincular vermelho). Threshold: **28px**
  - Constantes JS por módulo: `SWIPE_REVEAL_NOTAS = 88` · `SWIPE_REVEAL_LOTES = 88` · `SWIPE_REVEAL_ITEM = 96` · `SWIPE_REVEAL_VINC = 56`. Trigger = ~50% do reveal
  - Botões com largura **44-56px** (touch target mínimo Apple guideline 44px), ícone interno **16-20px**
  - Estado de abertura: `wrap.dataset.swipeOpen = '1'` + `card.style.transform = 'translateX(-N px)'`
  - **Resistência elástica no overswipe** (passar do reveal): `translateX = -REVEAL - over * 0.3`
  - **OBRIGATÓRIO: click no card já em modo swipe-open fecha o swipe** (UX padrão de "cancelar implícito" — operador toca fora do botão pra desistir). Sem isso, swipe aberto fica "preso" e operador precisa swipe de volta. Implementação canônica: no handler de click do card (ou delegação no container), checar `if (wrap.dataset.swipeOpen === '1')` antes de qualquer outra ação — se aberto, limpar `transform`, setar `swipeOpen = '0'` e **retornar**. Padrão presente em `entrada_mobile.js:580`, `classificacao_mobile.js`, `rastreio_mobile.js` (lotes + items + vincs)
  - **1 swipe aberto por vez** — `fecharTodosSwipesX()` é chamada antes de abrir outro, e em `setActiveScreen` + `openSheet`
  - **Pendência registrada (Mai/2026 — 2026-05-28)**: padrão **swipe-to-direita** pra criar avaria nos cards de Lote do Rastreio. Mesma mecânica do swipe-esquerda mas com `dx > 0` revelando botão à esquerda do card. Decisão Cat B pendente entre TOP 30 vs TOP 33

### Reset automático do swipe ao navegar

**Crítico pra UX limpa**: swipes abertos **devem fechar automaticamente** ao mudar de tela ou abrir bottom sheet. Sem isso, operador volta pra lista e vê "lixeira/lápis presos" de uma navegação anterior.

Padrão: função `fecharTodosSwipesNotas()` que itera `[data-swipe-open="1"]` e reseta `transform` + `dataset.swipeOpen`. Hooks de chamada:

```js
function setActiveScreen(name) {
    fecharTodosSwipesNotas();  // ← qualquer pushScreen/popScreen limpa
    /* ... */
}
function openSheet(name) {
    fecharTodosSwipesNotas();  // ← abrir Nova nota / Cabeçalho / Itens limpa
    /* ... */
}
```

### Paridade com desktop — checklist

Antes de implementar mobile de novo módulo, **fazer levantamento exaustivo do desktop** (template + JS + views.py) e documentar regras a replicar. Sem isso, o mobile sai com bugs que o desktop resolveu há meses (paridade ↑ → retrabalho ↓). Padrão usado na Entrada Mobile:

1. **Cabeçalho órfão** — quando criar cabeçalho mas fechar sem add item, deletar automático
2. **Trava `apenas_checar`** antes do confirm em qualquer delete (item + nota)
3. **Editar via tap** no card (abre **mesmo sheet de inserir** em modo EDIT, não tela separada)
4. **Modo EDIT trava campos imutáveis**: Produto + toggles Classifica ficam `disabled = true` com `title` explicativo (paridade desktop entrada.js:1625-1634)
5. **Validação visual** com `.is-invalid` em campos errados (TODOS de uma vez, não 1 por vez)
6. **Vale lock 409 handling** específico (`handleValeLockedError(status, body)`)
7. **Cálculos automáticos**:
   - **QTDNEG sempre = qtd × peso** quando ambos > 0 (mesmo em vol=KG — paridade desktop entrada.js:2269). NÃO usar `vol === 'KG' ? qtd : qtd × peso`
   - Inverso ao editar: `qtdExibida = peso > 0 ? qtdNeg / peso : qtdNeg`
   - Vol != CX e peso vazio → força peso = 1 (paridade desktop checkVolumeClassification)
8. **Detecção de duplicação** (CODPROD+CODVOL) com confirm — em modo EDIT ignora própria linha
9. **Atalhos teclado** (Enter em Qtd/Peso/Produto dispara Adicionar/Salvar)
10. **Flag `cabecalho_excluido`** após delete último item → fecha sheet + reload
11. **Avaria fornecedor inline** (auto-save no blur, só em não-classificáveis)
12. **`Concluir` do sheet NÃO faz reload** quando há tela 2 carregada (`ESTADO_NOTA.nunota`) — só recarrega itens da nota atual. Reload só em cenário "Nova nota" (sem tela 2)

Vide [`modules/entrada.md`](modules/entrada.md) → "Paridade completa com web" pra tabela com links pros números de linha do desktop.

### Nome do usuário + Sair no header (tela principal de cada módulo)

Pendant do `user-badge-inline` + `btn-logout-inline` do desktop. **Regra**: aparecem **apenas na primeira tela** de cada módulo mobile (lista/dashboard). Somem em telas internas (detalhe, item, etc) — ali o foco visual é o conteúdo da operação. Visual idêntico ao Painel/desktop: pílula verde claro `#f0f5ec` com texto verde escuro `#4a633a` uppercase + link "Sair" vermelho ao lado.

Padrão estrutural no `<header class="m-screen-header">` da tela `data-screen="lista"`:

```html
<header class="m-screen-header">
    <button class="m-iconbtn m-sidebar-toggle">...</button>
    <h1 class="m-screen-title">{Módulo}</h1>
    <div class="m-user-badge" title="{{ request.session.nomeusu|default:'Usuário' }}">
        <i class="ph ph-user" aria-hidden="true"></i>
        <span>{{ request.session.nomeusu|default:'Usuário' }}</span>
    </div>
    <a href="{% url 'logout' %}" class="m-logout-link" title="Encerrar sessão">Sair</a>
</header>
```

Badge truncado em 100px com `text-overflow: ellipsis`. Em telas internas, manter o spacer original ou usar botões de ação.

### Display de quantidade em cards de item

Padrão fixo nos cards de item (tela 2 — detalhe da nota). **Peso à esquerda, Qtd à direita** (`.m-stat--right` no segundo `.m-stat`):

```
PESO/<codvol>                                     QTD
23 kg                              100 cx / 2.300 kg
```

- **Label dinâmica**: `Peso/<codvol.toLowerCase()>` — ex: `Peso/cx`, `Peso/sc`, `Peso/bd`
- **Valor Qtd**:
  - Quando `peso > 0` E `codvol != 'KG'`: `<qtdUnidades> <CODVOL> / <totalKg> KG` (ex: "100 CX / 2.300 KG", "100 SC / 1.000 KG")
  - Quando `peso = 0` OU `codvol = 'KG'`: só `<totalKg> KG`
- **Status icon no header**: só aparece em **OK** (`ph-check-circle` verde). Em pendente, **sem ícone** (não usar `ph-clock`)

### iOS Safari — pegadinhas

- **Zoom em inputs**: type=number/text com `font-size < 16px` faz iOS dar zoom ao focar. Solução: **`font-size: 16px` mínimo** em `.m-field-input` (NÃO usar 14px ou menor mesmo que pareça grande visualmente)
- **type=number rejeita vírgula**: `input.value = '23,5'` em `type=number` fica vazio silenciosamente. Sempre usar `String(num)` com ponto separador. Pra exibir formatado, usar `toLocaleString('pt-BR')` SÓ em campos `type=text` readonly (ex: "Total kg calculado")
- **`dblclick` não dispara em touch**: usar [`IAgro.onDoubleActivate`](../sankhya_integration/static/sankhya_integration/iagro_helpers.js) (vide [`gotchas.md`](gotchas.md))
- **`100vh` cobre footer** (barra inferior dinâmica do Safari): usar `100dvh` com fallback `100vh`
- **`env(safe-area-inset-bottom)` exige `viewport-fit=cover`** no meta tag (já está em base.html)

### IDs do DOM — evitar duplicação entre telas

`document.getElementById(id)` retorna apenas o **primeiro** elemento. Quando o template mobile tem várias telas com mesma classe/id, `getElementById` pega só uma — bug silencioso difícil de detectar.

**Convenção**:
- Cada tela/contexto usa prefixo próprio: `m_item*` (sheet de inserir), `m_conf_*` (tela conferir item), `m_edit*` (sheet cabeçalho), `m_filtro*` (sheet filtros)
- Antes de adicionar campo novo, **conferir IDs duplicados**:

```python
import re
from collections import Counter
with open('templates/.../arquivo.html', encoding='utf-8') as f:
    ids = re.findall(r'id="([^"]+)"', f.read())
dup = [(k,v) for k,v in Counter(ids).items() if v > 1]
print('Duplicados:', dup or '(nenhum)')
```

Validar após cada PR que toque HTML mobile.

### Listeners pra inputs

Em `type=number`, eventos podem ser flaky entre dispositivos. Sempre registrar combo:

```js
['campo1', 'campo2'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', recalc);
    el.addEventListener('change', recalc);
    el.addEventListener('blur', recalc);
    el.addEventListener('keyup', recalc);
});
```

### Versionamento de cache (anti-cache mobile)

Toda mudança em CSS ou JS mobile **deve bumpar** `?v=N` no template — sem isso, browser mobile servirá versão antiga e debug parece "fix não aplicou":

```html
<link rel="stylesheet" href="{% static 'sankhya_integration/entrada.css' %}?v=35">
<script src="{% static 'sankhya_integration/entrada_mobile.js' %}?v=27" defer></script>
```

Sequência atual da Entrada Mobile (Mai/2026 — 2026-05-27): CSS `?v=35` · JS `?v=27`. Bumpar cada PR.

### Restart NSSM obrigatório após mudança no JS/CSS

NSSM cacheia template Django. Restart sempre + hard refresh no celular (Ctrl+Shift+R no DevTools mobile ou limpar cache do site no Safari iOS).

### Lista infinita com scroll listener

Listas mobile que cabem mais que o viewport (Entrada com 50+ notas) usam paginação infinita ancorada na paginação server-side da view desktop.

**Setup**:
1. View renderiza `data-current-page="N"` e `data-has-next="0|1"` no container do desktop (`#notasList`)
2. JS mobile lê esses attrs no boot (`lerEstadoPaginacao()`)
3. Após `hidratarListaNotas()`, cria sentinela visual no fim:

```js
function renderSentinela() {
    var lista = document.getElementById('m_notasList');
    var sent = document.getElementById('m_listaSentinela');
    if (sent) sent.remove();
    if (!pgInfinita.hasNext) return;
    var temBusca = searchInput && searchInput.value.trim();
    if (temBusca && autoPaginarIters >= AUTO_PAGINAR_MAX) return;
    sent = document.createElement('div');
    sent.id = 'm_listaSentinela';
    sent.className = 'm-lista-sentinela';
    sent.innerHTML = '<i class="ph ph-spinner"></i><span>Carregando mais…</span>';
    lista.appendChild(sent);
}
```

4. **Scroll listener no container** (1× no boot) dispara `carregarMaisNotas()` quando operador rola pra baixo + chega perto do fim:

```js
function setupScrollPaginar() {
    var scrollArea = document.getElementById('m_listaScroll');
    var lastScrollTop = 0;
    scrollArea.addEventListener('scroll', function () {
        if (pgInfinita.carregando || !pgInfinita.hasNext) return;
        var st = scrollArea.scrollTop;
        if (st <= lastScrollTop) { lastScrollTop = st; return; }   // só scroll pra baixo
        lastScrollTop = st;
        var threshold = scrollArea.scrollHeight - scrollArea.clientHeight - 200;
        if (st >= threshold) carregarMaisNotas();
    }, { passive: true });
}
```

5. `carregarMaisNotas()` faz `fetch(window.location.pathname + window.location.search + '&page=' + N+1)` — preserva filtros atuais. Parseia HTML retornado: `new DOMParser().parseFromString(html, 'text/html')`, extrai `#notasTable tbody tr.row--click` + atualiza `pgInfinita.hasNext` do novo `#notasList`
6. Appenda cards mobile **antes** da sentinela (que sempre fica no fim)
7. Re-chama `renderSentinela()` — recria/remove conforme `hasNext`

**CSS sentinela**:
```css
.{modulo}-mobile .m-lista-sentinela {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 12px 18px;
    color: var(--m-text-muted);
    font-size: 12px;
    font-weight: 600;
}
.{modulo}-mobile .m-lista-sentinela i {
    font-size: 18px;
    animation: m-spin 0.8s linear infinite;
}
```

### Por que NÃO usar IntersectionObserver

Tentativa inicial usou `IntersectionObserver` com `rootMargin: 200px`. **Cascata infinita** descoberta em 2026-05-27: cada nova sentinela aparecia já dentro do viewport (porque o append não desloca o scrollTop), observer detectava intersect e disparava imediatamente — operador deixava aberto e o server tomava 90+ requests em <60s.

Scroll listener resolve porque:
- Só dispara em **evento real de scroll** (operador roda o dedo)
- Compara com `lastScrollTop` pra ignorar scroll pra cima
- Threshold `scrollHeight - clientHeight - 200` calculado a cada evento (não bate "trigger zone" permanente)

### Badge "filtros ativos" no bottom nav

Quando há filtro aplicado (data, parceiro, produto, etc.) — bolinha vermelha + ícone verde Agromil no item de Filtros do bottom nav. Operador identifica de relance que tem filtro mascarando a lista.

```js
function temFiltroAtivo() {
    var nomes = ['start', 'end', 'nunota_ini', 'codparc', 'fabricante'];
    for (var i = 0; i < nomes.length; i++) {
        var el = getDesktopFormInput(nomes[i]);
        if (el && el.value && String(el.value).trim() !== '') return true;
    }
    return false;
}

function atualizarBadgeFiltros() {
    var navBtn = document.querySelector('.m-bottom-nav__item[data-nav="filtros"]');
    if (!navBtn) return;
    navBtn.classList.toggle('has-filtros-ativos', temFiltroAtivo());
}
```

Chamar `atualizarBadgeFiltros()` no fim de `hidratarListaNotas()`. CSS:

```css
.{modulo}-mobile .m-bottom-nav__item { position: relative; }   /* pra ::after */
.{modulo}-mobile .m-bottom-nav__item.has-filtros-ativos { color: var(--m-primary); }
.{modulo}-mobile .m-bottom-nav__item.has-filtros-ativos i::before { font-family: 'Phosphor-Fill'; }
.{modulo}-mobile .m-bottom-nav__item.has-filtros-ativos::after {
    content: '';
    position: absolute;
    top: 6px; right: 22%;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--m-danger);
    box-shadow: 0 0 0 2px var(--m-surface);
}
```

### Replicar data inicial em data final (sempre, no iPhone)

Padrão "operador olha 1 dia só por default; quem quer range muda dataFim depois". Implementação ingênua faz `if (dataFim.value < dataIni.value) replicar` — **falha no iPhone** quando dataFim já tem valor anterior preenchido (não atualiza).

**Fix**: replicar **sempre**, sem comparação. Também registrar `input` além de `change` (iOS dispara `change` só quando picker fecha):

```js
var replicar = function (e) {
    var v = (e && e.target ? e.target.value : inputIni.value) || '';
    if (v) inputFim.value = v;
};
inputIni.addEventListener('change', replicar);
inputIni.addEventListener('input', replicar);
```

Operador que quiser range manual altera dataFim depois — o handler dela não dispara nada em ini.

### Busca server-side ágil (recomendado) + trava de 90 dias

**Decisão Mai/2026 — 2026-05-27**: busca client-side com auto-paginação foi **descontinuada** após operadores reportarem que resultados apareciam progressivamente (cada página com delay) e bases grandes ficavam parcialmente fora do limite. Solução final é server-side em **1 fetch único** com debounce curto.

**Backend (Cat B — modifica query existente)**:

`listar_notas_compra_paginado` em `oracle_conn.py` ganhou param `q` opcional:

```python
if kwargs.get('q'):
    where.append(
        "(UPPER(p.NOMEPARC) LIKE :q "
        "  OR TO_CHAR(c.NUNOTA) LIKE :q "
        "  OR TO_CHAR(c.NUMNOTA) LIKE :q)"
    )
    binds['q'] = f"%{str(kwargs['q']).strip().upper()}%"
```

Bate em **nome do parceiro OU NUNOTA OR NUMNOTA** — operador digita texto ou número. View `view_portal_entradas` passa adiante via `params['q']`.

**Trava de 90 dias por default**:

```python
raw_days = request.GET.get("days")
has_dates = bool(request.GET.get("start")) or bool(request.GET.get("end"))
if raw_days is None:
    days_val = None if has_dates else 90   # ← default 90 dias
else:
    rd = raw_days.strip().lower()
    days_val = None if rd in ("all", "todos", "*", "") else _converter_para_inteiro(raw_days)
```

Operador que precisa histórico maior **abre o filtro** e seta `days=N` ou `start/end` — override explícito desliga a trava.

**Frontend mobile**:

```js
var buscaFetchToken = 0;

searchInput.addEventListener('input', function () {
    clearTimeout(t);
    var termo = searchInput.value.trim();
    t = setTimeout(function () { buscarServerSide(termo); }, 250);
});

function buscarServerSide(termo) {
    var meuToken = ++buscaFetchToken;
    var params = new URLSearchParams(window.location.search);
    if (termo) params.set('q', termo); else params.delete('q');
    params.set('page', '1');
    var url = window.location.pathname + '?' + params.toString();

    // Spinner instantâneo de "Buscando…"
    // ...

    fetch(url).then(r => r.text()).then(function (html) {
        if (meuToken !== buscaFetchToken) return;   // resposta obsoleta — descarta
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var rows = doc.querySelectorAll('#notasTable tbody tr.row--click');
        substituirCardsNotas(rows);   // REPLACE (não append)
        atualizarBadgeFiltros();
    });
}
```

**Token de race**: quando operador digita rápido (350ms entre tecladas), múltiplos fetches podem disparar em sequência. `buscaFetchToken` incrementa a cada nova chamada — apenas a última response passa pelo `if (meuToken !== buscaFetchToken) return`. Outras são descartadas.

**Vantagens vs client-side**:

| Aspecto | Client-side (descontinuado) | Server-side (atual) |
|---|---|---|
| Tempo até primeiro resultado | ~3s (puxa 20 páginas progressivo) | ~200ms (1 fetch) |
| Cobertura | Limitada a 1000 notas (20 × 50) | Base inteira (com trava 90d) |
| Resultados aparecem | Aos poucos (progressivo) | Todos de uma vez |
| Carga no server | 20 requests | 1 request |
| Carga no cliente | 1000 cards no DOM | Só matches no DOM |

**Quando manter client-side**: nunca pra listas grandes. Pra listas pequenas (sempre <100 itens, sem paginação) client-side ainda funciona — mas adicionar server-side é igualmente simples.

**Placeholder informativo** no `m_search`: sempre comunicar a janela default da busca pra operador não buscar histórico amplo achando que está olhando tudo. Exemplo: `placeholder="Buscar fornecedor ou pedido (últimos 90 dias)"`. Quando default for diferente (ex: outro módulo com 30 dias), refletir no texto.

**Cuidado com sentinela presa**: `renderSentinela` deve checar tanto `hasNext` quanto o limite de auto-paginar — senão quando atinge `AUTO_PAGINAR_MAX` mas o server ainda tem páginas, o spinner fica girando sem nada disparar:

```js
function renderSentinela() {
    var sent = document.getElementById('m_listaSentinela');
    if (sent) sent.remove();
    if (!pgInfinita.hasNext) return;   // fim natural
    var temBusca = searchInput && searchInput.value.trim();
    if (temBusca && autoPaginarIters >= AUTO_PAGINAR_MAX) return;   // limite atingido
    // ...cria sentinela
}
```

### Filtro client-side: esconder o wrapper, não só o card

Quando há busca/filtro client-side (campo `m_search` na lista), o handler que esconde linhas deve esconder o **wrapper** `.m-card-nota-wrap` (ou equivalente), não só o `.m-card-nota`. Senão os botões absolutos do swipe (`__swipe-edit` + `__swipe-del`) ficam pendurados no DOM.

```js
function filtrarCards() {
    var q = normalizar(searchInput.value);
    document.querySelectorAll('#m_notasList .m-card-nota').forEach(function (card) {
        var match = !q || normalizar(card.dataset.parc).indexOf(q) >= 0;
        var wrap = card.closest('.m-card-nota-wrap') || card;
        wrap.style.display = match ? '' : 'none';   // ← wrapper, não só card
    });
}
```

### Bottom sheets — estrutura HTML padrão

Todos os bottom sheets seguem essa estrutura:

```html
<div class="m-sheet" data-sheet="{nome}" aria-hidden="true">
    <div class="m-sheet__backdrop" data-close-sheet></div>
    <div class="m-sheet__content" role="dialog" aria-label="{Título}">
        <div class="m-sheet__handle"></div>
        <header class="m-sheet__header">
            <h2>{Título}</h2>
            <button type="button" class="m-iconbtn" data-close-sheet aria-label="Fechar">
                <i class="ph ph-x" aria-hidden="true"></i>
            </button>
        </header>
        <div class="m-sheet__body">{form/conteúdo}</div>
        <footer class="m-sheet__footer">
            <button class="m-btn-primary" id="m_xyzConcluir">
                <i class="ph ph-check"></i> Concluir
            </button>
        </footer>
    </div>
</div>
```

- **Variante alta** (forms longos): adicionar classe `m-sheet__content--tall` (92vh em vez de auto)
- **Toggle**: `aria-hidden="false"` abre, `"true"` fecha. Helper `openSheet(name)` / `closeSheet(name)`
- **Backdrop click** fecha (via `data-close-sheet`)
- **Botão X no header** fecha (via `data-close-sheet`)
- **Botão Concluir no footer** fecha + opcionalmente recarrega lista

### Bottom nav — 4 itens fixos

Toda tela principal (lista) tem bottom nav. Itens padrão:

| Item | Ícone | Ação |
|---|---|---|
| Notas / Lotes / Vendas (depende do módulo) | `ph-list-checks` | Tela atual (`.is-active`) |
| Buscar | `ph-magnifying-glass` | Foca o `m_search` (campo de busca já no topo) |
| Filtros | `ph-funnel` | Abre `m-sheet[data-sheet="filtros"]` |
| Mais | `ph-dots-three` | Reservado pra opções secundárias |

```html
<nav class="m-bottom-nav">
    <button class="m-bottom-nav__item is-active" data-nav="lista">
        <i class="ph ph-list-checks"></i><span>Notas</span>
    </button>
    <button class="m-bottom-nav__item" data-nav="buscar">
        <i class="ph ph-magnifying-glass"></i><span>Buscar</span>
    </button>
    <button class="m-bottom-nav__item" data-nav="filtros">
        <i class="ph ph-funnel"></i><span>Filtros</span>
    </button>
    <button class="m-bottom-nav__item" data-nav="mais">
        <i class="ph ph-dots-three"></i><span>Mais</span>
    </button>
</nav>
```

### Constantes JS reusáveis (copiar entre módulos)

```js
// Swipe
var SWIPE_REVEAL_NOTAS = 88;    // 2 botões (edit + del) 44px cada
var SWIPE_REVEAL_PX    = 44;    // 1 botão (só del) — usado em cards de item
var SWIPE_TRIGGER_PX   = 22;    // 50% do menor reveal

// Helpers comuns
function getCsrf() { /* ... */ }
function parseBR(s) { /* trim + ',' → '.' + parseFloat */ }
function fmtBr(v) { /* toLocaleString pt-BR 2 casas */ }
function escapeHtml(s) { /* &lt;, &gt;, ... */ }
function normalizar(s) { /* lowercase + NFD + remove acentos */ }
function mostrarToast(msg, tipo) { /* usa IAgro.showToast com fallback alert */ }
function handleValeLockedError(status, body) { /* trata 409 vale.locked */ }

// Navegação stack
function pushScreen(name) { /* history.pushState + setActiveScreen */ }
function popScreen() { /* setActiveScreen anterior */ }
function popToRoot() { /* reset pra 'lista' */ }
```

### Checklist passo-a-passo pra novo módulo mobile

Pra começar mobile de um módulo novo (ex: Rastreio, Venda, Combustível), seguir esta sequência. Cada step é cumulativo.

**Step 0 — Levantamento de paridade desktop** (antes de tocar código)

- Listar todas as funções do JS desktop do módulo
- Identificar regras/travas: locks, validações, auto-cura, anti-duplicação, atalhos teclado, modos edit
- Mapear endpoints usados (não criar novos pra mobile — reusar)
- Listar campos do form principal + tabela de itens (se houver)
- Criar tabela `desktop ↔ mobile` em [`modules/{modulo}.md`](modules/) com links pros números de linha

**Step 1 — HTML dual containers**

- Em `{modulo}.html`, dentro do `{% block content %}`:
  - Envolver tudo em `<div class="{modulo}-portal">`
  - Container desktop: `<div class="{modulo}-desktop">...</div>` (conteúdo existente intacto)
  - Container mobile: `<div class="{modulo}-mobile">` com `<section class="m-screen" data-screen="lista">` etc.
- Header da tela `lista` com hambúrguer + título + `.m-user-badge` + `.m-logout-link`
- Headers de telas internas (detalhe/item) sem badge — só botão back

**Step 2 — CSS mobile-first**

- No `{modulo}.css`, adicionar bloco `REDESIGN MOBILE-FIRST` no fim
- `:root` no escopo `.{modulo}-mobile` com tokens `--m-*` (copiar da Entrada)
- Classes `.m-*` reusadas (não duplicar — usar as do entrada.css se já existem)
- Media query escopada por `body[data-active-module="{modulo}"]`

**Step 3 — JS separado**

- Criar `{modulo}_mobile.js` (~600-1300 linhas dependendo da complexidade)
- IIFE com estado em closure
- Auto-ativação: `if (!window.matchMedia('(max-width: 900px)').matches) return;`
- Reusar constantes/helpers acima
- Reusar endpoints do desktop (zero novos)

**Step 4 — Cache busting**

- `<link>` CSS: `?v=N`
- `<script>` JS: `?v=N`
- Bumpar a cada commit que toque CSS/JS

**Step 5 — Validação anti-bugs**

Antes de declarar pronto, rodar:

```bash
# Detectar IDs duplicados
python -c "import re; from collections import Counter; \
ids = re.findall(r'id=\"([^\"]+)\"', open('templates/.../X.html', encoding='utf-8').read()); \
print('Duplicados:', [(k,v) for k,v in Counter(ids).items() if v > 1] or 'OK')"

# Detectar comentários Django multi-line
python -c "import re; txt = open('templates/.../X.html', encoding='utf-8').read(); \
p = re.compile(r'\{#.*?#\}', re.DOTALL); \
print([f'L{txt[:m.start()].count(chr(10))+1}' for m in p.finditer(txt) if chr(10) in m.group()] or 'OK')"

# Django check
python manage.py check
```

**Step 6 — Testes manuais no DevTools mobile**

- Toggle device toolbar (Ctrl+Shift+M) → iPhone 12
- Navegar pelo fluxo principal
- Testar gestos: swipe-to-back, swipe-to-edit/delete
- Testar filtro de busca + verificar que swipes não vazam
- Testar `Concluir` voltando pra tela anterior (não tela inicial)
- Testar input de qtd/peso → verificar Total kg calculado
- Testar modo edit (click no card de item) — Produto + Classifica devem estar disabled
- Conferir badge "👤 USER" + Sair no header da lista

**Step 7 — Restart NSSM + teste em iPhone real**

- `nssm.exe restart IAgro`
- Hard refresh no celular (limpar dados do site no Safari iOS)
- Confirmar: zoom em inputs (não deve fazer), safe-area inferior, swipes 44px, fluxo end-to-end

**Step 8 — Documentação**

- Atualizar `modules/{modulo}.md` com tabela de paridade (links pros números de linha desktop)
- Atualizar `CLAUDE.md` com bullets resumindo entregas
- Se houver gotcha nova, adicionar em `gotchas.md`

---

## Responsivo (Mai/2026 — sweep aplicado em todos os módulos)

Breakpoints padronizados:

| Largura | Comportamento |
|---|---|
| **≥1280px** (desktop largo) | Layout completo: sidebar 200px + grids originais (3/2 colunas) |
| **1025–1279px** (desktop normal) | Igual desktop largo |
| **901–1024px** (tablet horizontal) | Sidebar 200px, grids ficam mais apertados (sidebar interna 280px, gaps menores) |
| **≤900px** (tablet vertical / mobile largo) | Sidebar global vira off-canvas. Grids dos módulos viram **coluna única vertical**. Modais full-width (`95vw`). Tabelas largas com `overflow-x: auto` + `min-width` |
| **≤520px** (mobile pequeno) | Header compacto (label "Atualizar" some), modais **fullscreen** (`100vw × 100vh`, `border-radius: 0`), grids 1 coluna |

### Defesa global pra modais

Em `global.css` (após o layout v2):

```css
.modal-content,
.modal-card,
.cb-modal-card {
  max-width: min(640px, 95vw);
  max-height: 92vh;
  max-height: 92dvh;     /* iOS Safari moderno — desconta barra inferior */
}
@media (max-width: 520px) {
  .modal-content,
  .modal-card,
  .cb-modal-card {
    width: 100vw !important;
    max-width: 100vw !important;
    height: 100vh !important;          /* fallback */
    max-height: 100vh !important;
    height: 100dvh !important;          /* iOS Safari moderno */
    max-height: 100dvh !important;
    border-radius: 0 !important;
  }
}
```

Vale pra TODOS os modais. Módulos que precisam de tamanho específico declaram regra com mais especificidade no próprio CSS.

**Flex-shrink obrigatório no header/footer dos modais flex column** — sem `flex-shrink: 0`, body cresce e empurra footer pra fora da viewport. Aplicado em `.modal-header`, `.modal-footer`, `.cb-modal-header`, `.cb-modal-footer` em `global.css` desde 2026-05-15.

### Safe-area no iPhone Safari (Mai/2026 — 2026-05-15)

Páginas autenticadas usam `body.app-shell .main-layout` com `padding-bottom: calc(90px + env(safe-area-inset-bottom, 0px))` em ≤900px e `100px+env` em ≤520px. Containers internos com `overflow-y: auto` (`.entrada-grid`, `.venda-grid`, etc) replicam esse buffer.

Pré-requisito: `<meta viewport content="...,viewport-fit=cover">` em `base.html` e `home_login.html`. Sem isso `env(safe-area-inset-*)` retorna 0. Detalhes em [`gotchas.md`](gotchas.md) → "Mobile no iPhone Safari".

### Cada módulo tem seu próprio bloco `@media`

No final do CSS de cada módulo (`combustivel.css`, `venda.css`, etc) existe seção comentada **`RESPONSIVO PARA TABLET / MOBILE (Mai/2026 — sweep)`** com os 3 breakpoints. Ao adicionar feature nova com layout, **adicione regra responsiva nessa seção** — não jogue solta no meio do CSS.

### Padrões usados nos sweeps

| Padrão | Onde aplica |
|---|---|
| `flex-direction: column` em ≤900px | Containers que eram flex row (`.entrada-grid`, `.venda-grid`, `.email-grid`) |
| `grid-template-columns: 1fr` em ≤900px | Containers que eram grid horizontal (`.cb-layout`, `.layout` do Comercial, `.rastreio-layout`) |
| `overflow-x: auto` + `min-width: <px>` em ≤900px | Tabelas largas (combustível 9 col, classificação 9 col, etc) |
| `max-height: 50vh` em ≤900px | Sidebars internas dos módulos que viram parte de cima na coluna |
| `width: 95vw` em ≤900px / `100vw` em ≤520px | Modais |
| `.btn span { display: none }` em ≤900px | Esconde label de botões com ícone (mantém só ícone) |
| `opacity: 0.85` (em vez de hover-only) em ≤900px | Botões revelados em touch (Rastreio) |

---

## Ícones — Phosphor Icons (Mai/2026, padrão atual)

> ✅ **Padrão único do projeto.** Substituiu Material Symbols + emojis Unicode + SVGs inline em sweep de Mai/2026 (2026-05-14). Toda iconografia da UI usa **Phosphor** via CDN unpkg, com 2 pesos carregados.

### Setup ([base.html](../sankhya_integration/templates/sankhya_integration/base.html))

```html
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/fill/style.css">
```

### Como usar

Sempre `<i class="ph ph-NOME">` (font-icon, herda `currentColor` e `font-size` do contexto):

```html
<i class="ph ph-magnifying-glass" aria-hidden="true"></i>
<i class="ph ph-trash icon" aria-hidden="true"></i>
<i class="ph ph-warning" style="color: #dc2626;" aria-hidden="true"></i>
```

Catálogo completo em **https://phosphoricons.com/**. Slug do nome (ex: `ph-tree-structure`) é o que entra no `class`.

### Item ativo na sidebar — variante `fill`

[global.css](../sankhya_integration/static/sankhya_integration/global.css):
```css
.nav-item.active .ph::before {
  font-family: 'Phosphor-Fill';
}
```

Cada peso Phosphor é uma fonte separada (`Phosphor`, `Phosphor-Fill`, `Phosphor-Bold`...). Trocar família via CSS = mesma classe `ph-xxx` muda de regular pra preenchido sem trocar HTML.

### Mapeamento atual da sidebar (módulos)

| Módulo | `ph-XXX` |
|---|---|
| Painel | `squares-four` |
| Entrada | `shopping-cart-simple` |
| Classificação | `arrows-split` |
| Comercial | `crosshair` |
| Venda | `currency-circle-dollar` |
| Rastreio | `flow-arrow` |
| Importação | `tray-arrow-down` |
| Combustível | `gas-pump` |
| Auditoria | `magnifying-glass` |

### Regras

1. **Não usar emojis Unicode em UI** (mensagens de toast, badges, botões). Usar `<i class="ph ph-xxx">`. Exceção: comentários `//` em JS (não afetam UI).
2. **SVGs inline customizados são permitidos só quando são desenhos** (tanques de combustível, gauges de medidor) — não pra ícones de UI.
3. **Tamanho controlado por `font-size`**, não `width/height`. Em containers com posicionamento absoluto (ex: lupa de input), substitua `width: Xpx` por `font-size: Xpx` na regra CSS do contêiner.
4. **Cor herda do parent** (`currentColor`) ou via `style="color: #xxx"` inline / classe.
5. **Sempre `aria-hidden="true"`** em ícones decorativos (sem rótulo próprio).

### Não confundir com SVGs decorativos

- `combustivel.js` mantém SVG nos tanques (formato físico + nível de fluido) — não é ícone
- `comercial.html` mantém SVG no gauge de progresso (gráfico semicircular dinâmico) — não é ícone
- Logo Agromil é `<img src="logo.png">` — não migra

### Toast genérico (helper)

[`IAgro.showToast`](../sankhya_integration/static/sankhya_integration/iagro_helpers.js) também usa Phosphor (`check-circle`, `warning-circle`, `info`, `warning`) — ao chamar `mostrarToast(msg, tipo)`, o ícone do toast vem automaticamente.

---

## CSS — Design System

### Tokens globais (`global.css`)

Variáveis CSS centralizadas com **nomes em português**. Nunca usar valores hardcoded em módulos — sempre referenciar tokens.

| Categoria | Tokens (exemplos) |
|---|---|
| Cores principais | `--cor-fundo-painel`, `--cor-borda`, `--cor-acao-primaria`, `--cor-acao-perigo` |
| Appbar/rodapé | `--cor-appbar-fundo`, `--cor-appbar-texto`, `--cor-rodape-fundo`, `--cor-rodape-borda`, `--cor-rodape-texto` |
| Tipografia | `--fonte-principal`, `--peso-titulo`, `--tamanho-titulo` |
| Espaçamento | `--espaco-entre-paineis`, `--altura-appbar` (44px) |
| Borda/sombra | `--raio-borda`, `--sombra-painel` |

### Componentes globais

Definidos em `global.css`, **não duplicar nos módulos**:

- `body`, `.wrap`, `.main-layout` — moldura visual
- `.appbar`, `.appbar h1`, `.home-btn` — cabeçalho
- `.env-badge`, `.env-badge--homologacao`, `.env-badge--producao` — badge de ambiente
- `.user-profile-badge`, `.logout-link` — badge de usuário
- `.ia-footer`, `.ia-footer-versao` — rodapé
- `.panel`, `.modal-overlay`, `.modal-header`, `.modal-body` — containers
- `#toastContainer`, `.toast` — feedback
- `.status-dot` — indicador de status
- 6 `@keyframes` para animações

### Aliases de retrocompatibilidade

Cada módulo redefine `:root` com aliases que apontam para tokens globais. Permitiu migração sem quebrar as classes legadas.

### Regras permanentes

1. **Não redefinir** `body`, `.wrap`, `.appbar`, `.home-btn`, `.env-badge`, `.ia-footer` em CSS de módulo.
2. **Não adicionar `<main>`** dentro de `{% block content %}` — o `<main class="main-layout">` já está em `base.html`.
3. **Layout interno do módulo** vai numa classe própria (`.entrada-grid`, `.rastreio-layout`, etc.) dentro do `{% block content %}`.
4. **Para mudar appbar/rodapé globalmente**, alterar tokens `--cor-appbar-*` / `--cor-rodape-*` em `global.css`.
5. **Header com elementos auxiliares:** usar `{% block header_extras %}{% endblock %}` da `base.html` — irmão do `<h1>`. **NUNCA colocar spans com fontes alternativas dentro do `<h1>`** (quebra `line-height: 44px`).

### Regra do `.main-layout` (canônico em `global.css`)

```css
.main-layout {
  flex: 1;
  min-height: 0;
  padding: 14px 14px 40px 14px;
  display: flex;
  box-sizing: border-box;
  overflow: hidden;
}
```

- 14px nos lados e topo (logo abaixo da appbar)
- 40px no bottom (rodapé é `position: fixed`, ~24px + 14px de respiro)

Mudar valores aqui afeta **todos os módulos** simultaneamente.

---

## JavaScript — Helpers

Tudo exposto sob `window.IAgro` em `iagro_helpers.js`.

| Helper | Assinatura | Descrição |
|---|---|---|
| `IAgro.getCookie(name)` | `(name) => string` | Lê cookie (usado para CSRF token) |
| `IAgro.postJSON(url, data)` | `async (url, data) => response` | Wrapper de `fetch` com content-type JSON e CSRF header |
| `IAgro.showToast(msg, type)` | `(msg, 'success'\|'error'\|'info'\|'warning')` | Toast de feedback |
| `IAgro.debounce(fn, ms)` | `(fn, ms) => debounced` | Debounce simples |
| `IAgro.confirmarAcao(opts)` | `async ({titulo, mensagem, tipo}) => boolean` | Modal custom — substitui `window.confirm`. Tipos: `'perigo'` (vermelho), `'aviso'` (laranja), `'info'` (azul). Suporta Esc/Enter |
| `IAgro.cachedFetch(url, opts)` | `async (url, {ttl: 60_000}) => body` | Cache TTL em memória para typeahead/listas semi-estáticas. Não cacheia respostas de erro |
| `IAgro.onDoubleActivate(el, fn, opts)` | `(el, fn, {delegateSelector?, tapWindowMs?}) => dispose` | Double-click (mouse) + double-tap (touch) cross-device. iOS Safari/Chrome (WKWebView) e DevTools mobile não disparam `dblclick` em touch — daí o fallback manual via click+timer. Sempre usar isso em vez de `addEventListener('dblclick', ...)` |
| `IAOverlay.show()` / `IAOverlay.hide()` | — | Overlay de loading da página |

### Regras

- **`window.confirm` está banido** em ações destrutivas — usar `IAgro.confirmarAcao` com tipo `perigo`.
- **CSRF token** sempre enviado via header `X-CSRFToken` (helper `postJSON` já cuida).
- **Modal `IAgro.confirmarAcao`** retorna Promise: `if (await IAgro.confirmarAcao({...}))`.
- **Compatibilidade legada:** os módulos `compras_portal` (entrada) e `compras_classificacao` usam wrappers que preferem as funções centrais (`window.getCookie`, `window.postJSON`) com fallback local.

---

## UX padrão (DEFAULT OBRIGATÓRIO — Mai/2026)

> **🟢 Agora é padrão pra TODOS os módulos.** Aplicado em retrofit Mai/2026 nos
> 7 módulos com filtros/typeaheads (Entrada, Classificação, Comercial, Venda,
> Rastreio, Email importação, modais da Venda). Helpers centrais em
> [`iagro_helpers.js`](../sankhya_integration/static/sankhya_integration/iagro_helpers.js)
> garantem comportamento idêntico em toda a aplicação.

### Helpers centrais — referência canônica

| Helper | Para que serve |
|---|---|
| `IAgro.attachTypeahead(opts)` | Typeahead com ↑/↓/Enter/Tab/Esc, debounce, dropdown |
| `IAgro.installAutoSelect()` | Delegação global de select-on-focus (chamado 1× no `base.html`) |
| `IAgro.wireFilterAuto(ids, cb, opts)` | Bind padronizado de filtros de listagem (debounce 500ms default) |

### Typeaheads

Use **sempre** `IAgro.attachTypeahead`. Sem retypar handlers de teclado nem dropdown.

```js
IAgro.attachTypeahead({
    inputId:    'meu_campo',
    hiddenId:   'meu_campo_hidden',     // opcional — pra campos só visuais
    dropdownId: 'meu_campo_dropdown',
    url:        '/sankhya/parceiros/search/',
    limit:        15,                    // default 15
    debounceMs:  300,                    // default 300ms (typeahead)
    minChars:    1,                      // default 1
    extraQuery: 'grupo_inicia_com=1',   // opcional
    positionFixed: true,                 // true: dropdown dentro de <td>
    pickItems:  (data) => data.results,  // default: tenta .results/.items/.lotes
    pickCod:    (it) => it.codparc,      // default: cod/codparc/codemp/codtipvenda
    pickDescr:  (it) => it.nomeparc,     // default: descr/nomeparc/nomefantasia
    renderItem: (it) => `${it.codparc} — ${it.nomeparc}`,
    pickExtra:  (it) => ({ selecionado: it.selecionado }), // injeta data-* customizados
    onSelect:   (cod, descr, item) => carregarLista(),
    onClear:    () => carregarLista(),
});
```

Garantias do helper:

| Tecla | Comportamento |
|---|---|
| `↓` / `↑` | Move `.dd-item.active`; wrap em ambas pontas; `scrollIntoView` |
| `Enter` | Confirma item ativo + `preventDefault` (não submete form) |
| `Tab` | Confirma item ativo + NÃO chama `preventDefault` (segue pro próximo campo) |
| `Esc` | Fecha sem selecionar |
| Click | Confirma |
| Blur | Fecha após 200ms (tolerância pra click) |

Estrutura mínima do HTML:
```html
<input type="text" id="meu_campo" autocomplete="off">
<input type="hidden" id="meu_campo_hidden">
<div id="meu_campo_dropdown" class="dropdown-abs"></div>
```

### Select-all on first focus — GLOBAL

`IAgro.installAutoSelect()` é chamado uma vez no [`base.html`](../sankhya_integration/templates/sankhya_integration/base.html), valendo pra **toda** a aplicação. Cobre:

- `<input type="text|number|search|tel|email|url|password">`
- `<textarea>`

Ignora `readonly`, `disabled`, e campos com atributo `data-no-select`.

**Opt-out por campo:**
```html
<input type="text" id="campo_que_nao_quer_select" data-no-select>
```

NÃO duplicar listeners locais de `focus → this.select()`. O global cobre.

### Filtros de listagem — `wireFilterAuto`

```js
IAgro.wireFilterAuto(
    ['filtroTop', 'filtroPedido', 'filtroNF', 'filtroLote'],
    () => carregarLista(),
    { debounceMs: 500 }   // opcional; default 500ms pra filtros
);
```

Comportamento por tipo de campo:

| Tipo | Evento | Debounce |
|---|---|---|
| `<input type="text\|number\|search">` | `input` + `change` | 500ms |
| `<select>`, `<input type="date\|time\|month\|week>` | `change` imediato | 0ms |

NÃO adicionar listeners manuais paralelos pros mesmos campos.

### Debounce — padrão consolidado

| Cenário | Debounce | Justificativa |
|---|---|---|
| Typeahead (busca por dropdown) | **300ms** (helper default) | Suficiente pra leitura humana; corta picos de keystroke |
| Filtro de listagem grande | **500ms** (helper default) | Query pesada — pede mais espera |
| Select / date / time | **0ms** | Mudança discreta — efeito imediato esperado |

Helpers cuidam disso automaticamente. Quem precisa de outro tempo passa o `debounceMs` no opts.

### Defaults sensíveis ao domínio

Campos com valor sugerido devem refletir o cenário **mais comum** do agronegócio (poupa o operador):

| Campo | Default |
|---|---|
| Volume / unidade de medida | `KG` (não `UN`) — maioria dos itens vendidos é em quilo |
| Empresa (CODEMP) quando não houver matching | `10` |
| CODNAT | `10010100` (Pedido de Venda) |
| Data | hoje (`YYYY-MM-DD` atual) |

### Formato visual de campos pré-populados (typeahead)

Inputs visíveis de typeahead devem mostrar `cod — NOME` (não só `cod`), padrão consistente com o conteúdo dos itens do dropdown. Isso evita o operador ver `456` sem saber qual parceiro é. Backend deve devolver o nome canônico via JOIN.

**Exceção: campos de filtro por FABRICANTE** mostram só o nome (sem código) — fabricante não tem código numérico, ver seção abaixo.

### Período data inicial → data final + navegação dia-a-dia `<<` `>>`

Padrão consolidado para qualquer tela com filtro de período por data:

```
[<<]  [Data Inicial]  a  [Data Final]  [>>]
```

**Regras**:
- Operador digita `Data Inicial` → JS **replica automaticamente em `Data Final`** (cobre 90% dos casos onde o operador olha um dia só). Operador pode mudar a `Data Final` depois.
- Botão `<<` recua 1 dia: ambos os campos vão pra `data_inicial - 1` (mantém o range em 1 dia).
- Botão `>>` avança 1 dia: ambos vão pra `data_inicial + 1`.
- Ao alterar qualquer um dos campos ou clicar nos botões, dispara `change` → recarrega listagem/dados automaticamente.

**Implementação** (vide `entrada.js` e `combustivel.js`):

```js
// 1. Replica data_inicial → data_final no onChange da primeira
detIni.addEventListener('change', () => {
    const v = detIni.value;
    if (!v) return;
    if (!detFim.value || detFim.value < v) {
        detFim.value = v;
    }
    aplicarFiltros();
});

// 2. Botões << / >>
const shiftDate = (delta) => {
    let d = detIni.value ? new Date(detIni.value + 'T12:00:00') : new Date();
    if (isNaN(d.getTime())) d = new Date();
    d.setDate(d.getDate() + delta);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const iso = `${y}-${m}-${dd}`;
    detIni.value = iso;
    detFim.value = iso;
    aplicarFiltros();
};
btnPrev.addEventListener('click', () => shiftDate(-1));
btnNext.addEventListener('click', () => shiftDate(1));
```

**HTML mínimo**:

```html
<button id="btnPrevDay" class="btn-mini-nav" title="Dia anterior">&lt;&lt;</button>
<input type="date" id="detDataIni" />
<span class="sep">a</span>
<input type="date" id="detDataFim" />
<button id="btnNextDay" class="btn-mini-nav" title="Dia seguinte">&gt;&gt;</button>
```

**Onde já aparece**: Entrada (filtros laterais), Combustível (detalhe do veículo).

**Não usar `<select>Últimos N dias</select>`** em telas novas — operador prefere data específica + setas. O select fica reservado para relatórios agregados (Dashboard, Relatórios) onde "período" é semântica de bucket.

---

## Campo "Produto" — dois padrões de filtragem (Mai/2026)

> ⚠ **Antes de criar ou alterar QUALQUER campo de busca rotulado "Produto", PERGUNTAR ao usuário qual padrão usar.** Mesmo nome de campo, comportamentos diferentes — escolher errado causa filtro silenciosamente errado (operador acha que filtrou e não filtrou).

### Padrão A — Filtro por FABRICANTE (texto LIKE)

Operador digita um nome → busca em fabricantes únicos → filtra lotes/notas onde **algum produto tem aquele fabricante**.

Exemplo: digitar "CENOURA" pega notas com produtos `CENOURA IN NATURA`, `CENOURA EXTRA`, `CENOURA MOLHO`, etc — todos cujo `pr.FABRICANTE` contém "CENOURA".

**Quando usar:** filtros laterais de listagem (Entrada, Comercial) onde operador quer ver tudo de uma categoria de produto.

**Frontend:**
```js
// URL com flag fabricante=1 → endpoint retorna FABRICANTEs únicos
const url = `/sankhya/produtos/search/?q=${encodeURIComponent(q)}&limit=15&fabricante=1`;
// Render: SÓ o nome (sem código numérico)
dropdown.innerHTML = items.map(it => {
    const nome = (it.fabricante || it.descr || '').trim();
    return `<div class="dd-item" data-descr="${nome}">${nome}</div>`;
}).join('');
// Hidden e visível recebem o MESMO texto (sem código)
hidden.value = el.dataset.descr;  // ex: "CENOURA"
input.value  = el.dataset.descr;  // ex: "CENOURA"
```

**Template:**
```html
<input type="hidden" name="fabricante" id="fabricanteHidden" value="{{ params.fabricante|default:'' }}" />
<input type="text" id="prodSearch" value="{{ params.fabricante|default:'' }}" />
```

**Views (`views.py`):**
```python
"fabricante": (request.GET.get("fabricante") or "").strip() or None
```

**Backend (`oracle_conn.py`):**
```python
if kwargs.get('fabricante'):
    where.append(
        "EXISTS ("
        "  SELECT 1 FROM TGFITE i2 "
        "  JOIN TGFPRO pr2 ON pr2.CODPROD = i2.CODPROD "
        "  WHERE i2.NUNOTA = c.NUNOTA "
        "    AND UPPER(pr2.FABRICANTE) LIKE :fab"
        ")"
    )
    binds['fab'] = f"%{str(kwargs['fabricante']).upper()}%"
```

**Exemplos no projeto:**
- [entrada.js:755-815](../sankhya_integration/static/sankhya_integration/entrada.js) — filtro lateral da Entrada
- [comercial.js:612](../sankhya_integration/static/sankhya_integration/comercial.js) — filtro lateral do Comercial
- [oracle_conn.py:1119](../sankhya_integration/services/oracle_conn.py) — `listar_notas_compra_paginado`
- [oracle_conn.py:1232](../sankhya_integration/services/oracle_conn.py) — `consultar_vales_comercial`

### Padrão B — Filtro por PRODUTO específico (CODPROD numérico)

Operador digita → busca em produtos individuais → filtra por **CODPROD exato selecionado**.

Exemplo: digitar "CENOURA" mostra `30 — CENOURA IN NATURA`, `45 — CENOURA EXTRA`, etc. Operador escolhe CODPROD=30 → filtra **só** esse produto específico.

**Quando usar:** modais de criação/edição de itens (Venda, Entrada item, Classificação item) onde a operação precisa do produto **específico** pra inserir TGFITE.

**Frontend:**
```js
// URL SEM fabricante=1 → endpoint retorna PRODUTOS individuais
const url = `/sankhya/produtos/search/?q=${encodeURIComponent(q)}&limit=15`;
// Render: cod — descrição
dropdown.innerHTML = items.map(it =>
    `<div class="dd-item" data-cod="${it.cod}" data-descr="${it.descr}">${it.cod} — ${it.descr}</div>`
).join('');
// Hidden recebe CODPROD (int); visível mostra "cod — descr"
hidden.value = el.dataset.cod;                       // ex: "30"
input.value  = `${el.dataset.cod} — ${el.dataset.descr}`;  // ex: "30 — CENOURA IN NATURA"
```

**Template:**
```html
<input type="hidden" name="codprod" id="prodHidden" value="{{ params.codprod|default:'' }}" />
<input type="text" id="prodSearch" />
```

**Views (`views.py`):**
```python
"codprod": _converter_para_inteiro(request.GET.get("codprod"))
```

**Backend (`oracle_conn.py`):**
```python
if kwargs.get('codprod'):
    where.append(
        "EXISTS (SELECT 1 FROM TGFITE i2 "
        "WHERE i2.NUNOTA = c.NUNOTA AND i2.CODPROD = :codprod)"
    )
    binds['codprod'] = int(kwargs['codprod'])
```

**Exemplos no projeto:**
- [venda.js:170](../sankhya_integration/static/sankhya_integration/venda.js) — filtro lateral de Venda
- [venda.js:857](../sankhya_integration/static/sankhya_integration/venda.js) — modal de item da Venda (`item_prod_vis`)
- [classificacao.js:1097](../sankhya_integration/static/sankhya_integration/classificacao.js) — modal de item da Classificação
- [oracle_conn.py:2713](../sankhya_integration/services/oracle_conn.py) — `listar_vendas_paginado`

### Como escolher

| Cenário | Padrão |
|---|---|
| Filtro de listagem (lateral) onde operador quer "tudo de uma categoria" | **A — Fabricante** |
| Filtro de listagem por item específico (rastreio, lote individual) | **B — CODPROD** |
| Modal de criar/editar TGFITE (item de nota) | **B — CODPROD** (precisa do número pra gravar) |
| Sugestão de pesquisa rápida em dashboard/relatório | Caso a caso — pergunta |

### Endpoint compartilhado

`/sankhya/produtos/search/` aceita ambos os modos:

- Sem flag → retorna `{cod, descr, selecionado}` (CODPROD individual) — Padrão B
- Com `?fabricante=1` → retorna `{fabricante}` (DISTINCT em FABRICANTE) — Padrão A

Ambos os fluxos passam pelo mesmo endpoint Django ([api_pesquisar_produtos_entrada](../sankhya_integration/views.py)), que internamente roteia.

---

## Padrão de Resposta de API

Todas as APIs JSON retornam:

```json
{ "ok": true, "dados": "..." }      // sucesso
{ "ok": false, "error": "..." }     // falha (HTTP 400 ou 500)
```

**Erro sempre humanizado** via `humanizar_erro_oracle()`. Stack trace vai apenas para `logger.exception` — nunca para o cliente.

---

## Atomicidade Transacional (views de escrita)

Padrão obrigatório em todas as views que fazem INSERT/UPDATE/DELETE:

```python
@exige_grupo('venda')
def api_xxx(request):
    try:
        with obter_conexao_oracle() as conn:
            try:
                resultado = funcao_do_service(..., conexao_existente=conn)
                conn.commit()
                return JsonResponse({'ok': True, ...})
            except Exception as exc:
                conn.rollback()
                raise
    except Exception as exc:
        logger.exception("Falha em api_xxx")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)
```

**Razões:**
- `conexao_existente=conn` evita o bug `DPY-1001` em `inserir_cabecalho_nota_banco`
- `rollback` explícito antes de re-raise garante consistência
- `humanizar_erro_oracle` na resposta esconde detalhes técnicos
- `logger.exception` preserva stack trace para suporte

---

## Decorators

| Decorator | Aplicação |
|---|---|
| `@exige_grupo('modulo')` | Valida que `request.session['grupos']` contém grupo permitido para o módulo |
| `@check_vale_lock` | Lock para evitar concorrência em edição de vales (Comercial) |
| `@ensure_csrf_cookie` | Garante que cookie CSRF chegue no primeiro response da página (necessário em portais SPA-like) |

---

## Imports locais (dentro do corpo da função)

Algumas views fazem imports **dentro do corpo**, não no topo:

- `api_gerar_financeiro_banco` → importa `gerar_financeiro_banco`
- `api_desfaturar_vale` → importa `desfaturar_comercial_banco`

**Consequência para testes:** o patch deve apontar para o **módulo de origem**, não para `views`:

```python
# CORRETO:
@patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco', ...)

# ERRADO (não funciona com import local):
@patch('sankhya_integration.views.gerar_financeiro_banco', ...)
```

---

## Logging

`settings.py` tem bloco `LOGGING` estruturado. Todos os `print()` e `traceback.print_exc()` foram substituídos por:

- `logger.debug(...)` — fluxo normal detalhado
- `logger.info(...)` — eventos importantes
- `logger.warning(...)` — algo inesperado mas não crítico (ex: audit falhou mas operação ok)
- `logger.exception(...)` — capturar exceção com stack trace (uso obrigatório antes de humanizar erro)

---

## Migrations

- **Append-only** — nunca editar migration existente.
- **Nunca remover** — para reverter, criar nova migration que desfaça.
- **`0001_initial.py`** cria `Simulation` + `RastreioAudit` juntos.
- Ambiente de produção precisa rodar `python manage.py migrate` ao deploy.
