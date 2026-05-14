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
}
@media (max-width: 520px) {
  .modal-content,
  .modal-card,
  .cb-modal-card {
    width: 100vw !important;
    max-width: 100vw !important;
    height: 100vh !important;
    max-height: 100vh !important;
    border-radius: 0 !important;
  }
}
```

Vale pra TODOS os modais. Módulos que precisam de tamanho específico declaram regra com mais especificidade no próprio CSS.

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
