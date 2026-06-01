# Módulo Comercial (TOP 13)

Faturamento de vales de compra, precificação, negociação e geração de financeiro.

---

## 📱 Redesign Mobile app-like (Mai/2026 — 2026-05-29)

Mesma arquitetura padrão dos outros módulos (Entrada/Classificação/Rastreio/Combustível/Caixas). HTML único com 2 containers paralelos (`.comercial-desktop` + `.comercial-mobile`) escopados por `body[data-active-module="comercial"]` em viewport ≤900px. Desktop preservado 100% intacto. **Backend reusado — zero endpoint novo.**

### Estrutura mobile

| Componente | Arquivo |
|---|---|
| Template | `comercial.html` — bloco `.comercial-mobile` com 2 telas + 3 sheets + bottom nav + FAB |
| CSS | `comercial.css` — bloco "REDESIGN MOBILE-FIRST" no fim, escopado |
| JS | `comercial_mobile.js` (~1.000 linhas IIFE) — só ativa ≤900px ou touch real |

### 2 telas mobile

1. **Lista de vales** (`m-screen[data-screen="lista"]`)
   - Header: `[≡] Comercial [👤 USER] Sair`
   - 4 pílulas de resumo no topo: Vales · Valor · Pendentes · Faturados
   - Campo de busca client-side (debounce 200ms, normaliza acentos)
   - Cards de vale agrupados por NUNOTA com chevron expansível
   - Cor da borda esquerda muda por status: verde Agromil (aberto) · verde sucesso (faturado) · vermelho (sem preço)
   - Sub-cards de item com badge da categoria (classificável verde · não-classif cinza · sem preço vermelho)
   - Bottom nav 4 itens: Vales · Buscar · Filtros · Mais
   - FAB azul Atualizar (sem FAB verde — não cria vale aqui)

2. **Detalhe do vale** (`m-screen[data-screen="detalhe"]`)
   - Header partial `_m_header_interno.html` (`Comercial / Vale` + back + user + Sair)
   - Hero card 4 linhas: Parceiro · Produto · Pedido·Data · Lote
   - Status bar FATURADO (quando aplicável) — gradient verde + lock
   - **4 KPI cards 2×2**: Margem Lote · Qtde Total · Custo Compra · Total Compra
   - Margem usa endpoint `/api/margem-lote/` (cor: verde positivo · vermelho negativo · cinza neutro) + badge "provisória" quando há saldo
   - **2 cards de classificação** (EXTRA verde · MÉDIO âmbar) com bar de progresso + qtd kg/cx + custo kg/cx
   - **Sparkline SVG** "Evolução de preço — vendas deste lote" via endpoint `/api/vendas-lote/`
   - **2 botões grandes em grid**: `Editar preço` (secundário) + `Faturar` (primário verde)
   - Lista amarela de motivos quando FATURAR bloqueado (paridade desktop)

### 3 bottom sheets

- **`filtros`** — Período `<<>>` · typeahead Parceiro + Produto (fabricante) · Nº Vale · 2 chips de status (Sem preço · Faturado)
- **`editar-preco`** — inputs grandes 52px touch-friendly: Preço/cx + Peso CX Classificado. Calcula R$/kg derivado em runtime. Salva via `/api/atualizar-preco/` + `/api/atualizar-peso/` (mesmos endpoints do desktop)
- **`mais`** — 2 atalhos: Atualizar lista + Abrir filtros + info "Simulação, Movimentar Lote e Impressão na versão desktop"

### Endpoints reusados (zero novo)

| Endpoint | Mobile usa pra |
|---|---|
| `GET /sankhya/comercial/lista/?...` | Lista de vales (filtros + paginação) |
| `GET /sankhya/comercial/api/margem-lote/?lote=X` | KPI margem + tooltip |
| `GET /sankhya/comercial/api/vendas-lote/?lote=X` | Sparkline + estatísticas |
| `POST /sankhya/comercial/api/atualizar-preco/` | Salvar preço CX (Sheet editar-preco) |
| `POST /sankhya/comercial/api/atualizar-peso/` | Salvar peso classificado |
| `GET /sankhya/parceiros/search/?q=` | Typeahead filtro Parceiro |
| `GET /sankhya/produtos/search/?q=&fabricante=1` | Typeahead filtro Produto |
| `window.ComercialFinanceiro.abrir(nunota)` | **Reutiliza modal Faturamento desktop** — vira fullscreen via CSS responsivo já existente |

### Limitações conscientes (redireciona pra desktop)

| Feature | Decisão | Razão |
|---|---|---|
| **Simulação de Negócio** | Não exposta mobile | UX complexa (4 inputs reativos + balanço de massa Auto) |
| **Movimentar Lote** (Desmembrar/Unificar) | Não exposto mobile | Operação cirúrgica rara |
| **Modal Impressão** (4 tipos de papel) | Não exposto mobile | Impressora térmica no balcão |
| **Painel Últimas Vendas com toggle Lote/Produto** | Mostra só "deste lote" no sparkline | Toggle vive no desktop |
| **Classificação completa** (gauge + balanço de massa) | Card simplificado (só EXTRA/MÉDIO) | Operador não classifica via Comercial mobile |
| **Breakdown EXTRA/MÉDIO via Classificação** | Mostra dado consolidado quando não-classif; em classificável mostra "—" no share | Backend não retorna breakdown na listagem |

### Decisões pragmáticas vs desktop

| Aspecto | Desktop | Mobile |
|---|---|---|
| Layout | 3 colunas (filtros + zarea + cards) | Stack de telas (lista → detalhe) |
| Lista | Tabela colapsável com 2 view modes (Vale/Parceiro) | Cards verticais agrupados por NUNOTA |
| Filtros | Card lateral com chips de filtros ativos | Bottom sheet + badge no bottom nav |
| Editar preço | Inline na linha de Entrada (click no display) | Bottom sheet dedicado com 2 inputs grandes |
| Modal Faturamento | Modal centralizado | Reusa modal desktop (vira fullscreen via CSS responsivo) |
| Persistência de filtros | localStorage `agromil_comercial_filtros_v3` | Estado em memória (perde no reload) |
| Atualizar lista | Botão `Atualizar` no card | FAB azul `ph-arrows-clockwise` + sheet Mais |

### Cache busting

CSS `?v=17` · JS desktop preservado · JS mobile `?v=2` (Mai/2026 — 2026-05-30 após fix do chain de altura desktop).

### Bug fix pós-deploy — chain de altura quebrado no desktop (Mai/2026 — 2026-05-30 — CSS v17)

Operador relatou no dia seguinte ao deploy do mobile redesign: cards **Classificação + Entrada sumiram** do desktop, e o card Lista (sidebar) cresceu ocupando altura excessiva. Diminuir o zoom revelava os cards escondidos abaixo do viewport.

**Causa**: o `.comercial-portal` (wrapper criado pra abrigar `.comercial-desktop` + `.comercial-mobile` em paralelo) não tinha CSS — virou `display: block; height: auto`. Resultado: chain de altura quebrado entre `.main-layout` (flex container do base.html) e `.comercial-desktop.layout` (grid com `height: 100%`). Sem altura definida no pai, o `height: 100%` resolvia por conteúdo natural, `#distCard` (row 1) ocupava sem limite, e `#classCard` + `#entradaCard` (row 2) iam abaixo do viewport.

A tentativa anterior de contornar com `.comercial-desktop { display: contents }` foi anulada pelo `.layout { display: grid !important }` (vence por `!important`).

**Fix** em [comercial.css](../../sankhya_integration/static/sankhya_integration/comercial.css):

```css
.comercial-portal {
    display: flex;
    flex: 1;
    width: 100%;
    min-height: 0;
    position: relative;   /* contexto pro .comercial-mobile { position: absolute } */
}
```

Restaura chain de altura do `.main-layout` (flex container) pra o `.comercial-desktop.layout` (flex item com grid interno). `position: relative` resolve o contexto pro `.comercial-mobile` no media query ≤900px.

Padrão consolidado em [conventions.md](../conventions.md) → "Arquitetura — 2 containers paralelos no HTML" e gotcha em [gotchas.md](../gotchas.md) → "Wrapper portal sem flex/height quebra chain de altura do desktop". **Toda implementação nova de redesign mobile com 2 containers paralelos PRECISA configurar o `.{modulo}-portal` com `flex: 1; min-height: 0; position: relative`.**

### Bug fix pós-deploy — `data-idx` undefined nos cards de item (Mai/2026 — 2026-05-29 — v2)

Imediatamente após o deploy inicial, operador relatou "só consigo ver a lista". Causa: `carregarLista` não atribuía `_i` aos rows antes de salvar no STATE — o `data-idx="${r._i}"` no template renderizava `undefined`, e o handler do click caía em `STATE.listaRows[NaN] = undefined` silenciosamente.

**Fix** em [comercial_mobile.js](../../sankhya_integration/static/sankhya_integration/comercial_mobile.js):
```js
STATE.listaRows = Array.isArray(data.rows) ? data.rows : [];
STATE.listaRows.forEach(function (r, i) { r._i = i; });   // ← paridade com ComercialLista desktop
```

Padrão consolidado: **toda lista mobile com `data-idx` no template precisa atribuir `_i` (ou índice equivalente) antes de renderizar**. Vide [gotchas.md](../gotchas.md) → "Índice estável `_i` ao usar `data-idx` em cards de lista mobile".

### UX bonus — vale com 1 item abre detalhe direto

Adicionado nessa mesma rodada: vales com **1 item só** abrem o detalhe imediatamente ao tocar no header (sem precisar expandir + tocar no item). Vales com 2+ itens continuam expandindo/colapsando. Reduz cliques desnecessários no fluxo mais comum da operação (1 vale = 1 produto).

```js
lista.querySelectorAll('.m-cm-vale-header').forEach(function (h) {
    h.addEventListener('click', function () {
        var nun = h.getAttribute('data-nun');
        var itens = STATE.listaRows.filter(function (r) { return String(r.nunota) === String(nun); });
        if (itens.length === 1) {
            abrirDetalheVale(itens[0]);   // atalho 1-item
            return;
        }
        // 2+ itens: expande/colapsa
        var isExp = h.getAttribute('data-expanded') === 'true';
        h.setAttribute('data-expanded', isExp ? 'false' : 'true');
    });
});
```

Padrão reusável documentado em [conventions.md](../conventions.md) → "UX bonus — cards de grupo com 1 filho navegam direto".

### Validação

- `manage.py check` → 0 issues
- esprima `comercial_mobile.js` → OK (~46.000 chars)
- 0 IDs mobile duplicados (66 IDs únicos com prefixo `m_cm_*`)
- 0 comentários Django multi-line
- Template parseia sem `TemplateSyntaxError`

---

## Escopo

- Faturar vales (TOP 13) com precificação
- Distribuir pesos entre quotas
- Gerar financeiro em TGFFIN
- Imprimir vales
- Persistir simulações comerciais (modelo `Simulation` em SQLite)
- Desfaturar vales (operação reversa)

---

## URL e acesso

| Rota | Acesso |
|---|---|
| `/sankhya/comercial/` | Grupos `1`, `6`, `9` |
| `/sankhya/comercial/lista/` | **Sem decorator de acesso** — ver gotchas |

---

## Views principais (`views.py`)

| View | Propósito |
|---|---|
| `view_comercial_painel` | Página HTML do painel |
| `api_listar_vales_comercial` | Lista vales (⚠ sem `@exige_grupo`) |
| `api_gerar_financeiro_banco` | Gera TGFFIN — **import local** de `gerar_financeiro_banco` |
| `api_salvar_vale_comercial` | Salva alterações de um vale |
| `api_desfaturar_vale` | Reverte faturamento — **import local** de `desfaturar_comercial_banco` |

### Imports locais

`api_gerar_financeiro_banco` e `api_desfaturar_vale` fazem `import` **dentro do corpo da função**, não no topo do arquivo.

**Consequência para testes:** patch deve apontar para o **módulo de origem** (`oracle_conn`), não para `views`. Detalhes em `conventions.md`.

---

## Funções de `oracle_conn.py` usadas

- `gerar_financeiro_banco` — INSERT em TGFFIN
- `desfaturar_comercial_banco` — reversão
- Funções de listagem/precificação de vales

---

## Frontend

- **Template:** `comercial.html`
- **CSS:** `comercial.css`
- **JS principal:** `comercial.js`
- **Sub-módulos JS:**
  - `comercialDistribuicao.js` — distribuição de pesos entre quotas
  - `comercialFinanceiro.js` — geração de financeiro
  - `comercialImpressao.js` — impressão de vales
- **Container interno:** `.layout` (grid 360px + 1fr — nome legado)

### CSS específico

Override `.main-layout { padding: 0 20px }`. Vários componentes próprios: `.zgrid`, `.section-head`, `#filtersCard`, `.lista-view-toggle`, `.dist-mini`, `.dist-class-card .bar-track`, `.modal-content`, `.resumo-card`, `.btn-faturar-final`, `.btn-print-outline`.

---

## Fluxo do peso: `PESO` × `QTDFIXADA` (Mai/2026)

Os dois campos vivem em `TGFITE` e na Agromil carregam **o peso de uma caixa**.
A diferença é semântica e segue padrões distintos por tipo de produto:

| Produto | `TGFITE.PESO` TOP 11 | `TGFITE.QTDFIXADA` TOP 11 |
|---|---|---|
| **Classificável** (passa por TOP 26) | Digitado pela Entrada no modal de item | NULL no INSERT → preenchido pela Comercial via botão "Peso CX Classificado" (`atualizar_peso_comercial_entrada`) |
| **Não-classificável** (in natura direto pra TOP 13) | Digitado pela Entrada | **Espelhado automaticamente do PESO** pelo Fast-Track em `atualizar_preco_inicial_entrada` ([oracle_conn.py:1677-1680](../../sankhya_integration/services/oracle_conn.py#L1677-L1680)) |

**Por que espelhar em in natura:** produto não-classificável não tem etapa intermediária que justifique peso diferente. Sem o espelhamento, o operador da Comercial teria que redigitar o mesmo valor no botão "Peso CX Classificado" — e o bloqueio do salvar vale (ver abaixo) impediria de continuar.

### Salvar vale (TOP 13) — propagação automática (B1-B5, Mai/2026)

`salvar_vale_compra_banco` ([oracle_conn.py:1904](../../sankhya_integration/services/oracle_conn.py#L1904)):

1. **B4** — Bloqueia se PESO **e** QTDFIXADA da TOP 11 (linha de origem do lote, qualquer GERAPRODUCAO) forem ambos NULL/0 → mensagem `"Informe o peso classificado da caixa antes de salvar o vale."`.
2. **B4 (espelhamento bidirecional)** — Se só um dos dois está preenchido (caso de in natura sem Fast-Track ou classificável onde Comercial não digitou), **UPDATE espelha** o lado vazio com o valor do preenchido (`NVL(...,0)=0` garante idempotência). Quando ambos estão preenchidos, QTDFIXADA tem prioridade (peso classificado vence sobre peso digitado na Entrada).
3. **B2** — Propaga o valor consolidado pra `TGFITE.PESO` de **todos os itens da TOP 13** gravados no lote (Extra/Médio/etc — todos compartilham o mesmo peso de caixa).

**B5 — Espelhamento no INSERT da TOP 11**: `inserir_item_nota_banco` ([oracle_conn.py:998+](../../sankhya_integration/services/oracle_conn.py#L998)) agora grava `QTDFIXADA = PESO` direto no INSERT quando `GERAPRODUCAO ≠ 'S'` e PESO > 0. Evita estado intermediário com QTDFIXADA NULL — não precisa esperar Fast-Track rodar.

### Alteração tardia do peso classificado (B3)

`atualizar_peso_comercial_entrada` ([oracle_conn.py:1760](../../sankhya_integration/services/oracle_conn.py#L1760)) é o botão "Peso CX Classificado" da Comercial. Além do `UPDATE QTDFIXADA` na TOP 11, **propaga automaticamente pra `TGFITE.PESO` da TOP 13** se já houver vale salvo daquele lote. Operador não precisa abrir/re-salvar o vale.

Retorno ganhou `propagado_top13: int` com nº de linhas atualizadas (informativo).

### Preço in natura modal Faturamento → TOP 11 (B6)

`upsert_preco_in_natura_modalFaturamento` ([oracle_conn.py:2472](../../sankhya_integration/services/oracle_conn.py#L2472)) — quando operador digita preço no modal de faturamento de um item **não-classificável** (`GERAPRODUCAO ≠ 'S'`), o backend faz UPDATE em **TGFITE da TOP 11** propagando `PRECOBASE = VLRUNIT = preço` + `VLRTOT = preço × QTDNEG`, e em seguida chama `recalcular_totais_nota_banco(nunota_origem)`. Razão: pra in natura, preço do vale **é** preço da entrada (única etapa). Classificáveis (`'S'`) ficam intactos — preço pode legitimamente diferir.

### Refresh global após salvar preço

Tanto `comercial.js` (card Entrada) quanto `comercialFinanceiro.js` (modalFaturamento) chamam `window.ComercialFiltros.atualizar()` imediato após sucesso (Mai/2026, 2026-05-15 — era `setTimeout 500ms` no card). Garante que lista lateral reflita o novo preço/Fast-Track sem operador precisar dar F5.

---

## Decorator extra

- `@check_vale_lock` — lock para evitar concorrência em edição de vales

---

## Modelo Django relacionado

- **`Simulation`** (SQLite) — simulações comerciais persistidas. Audit via signals (`post_save`/`post_delete`). Registrado no Admin como `SimulationAdmin`.

---

## Últimas vendas DO LOTE + sparkline de preço (Mai/2026 — 2026-05-16)

A lista lateral "ÚLTIMAS VENDAS" passou a filtrar por **lote selecionado** (`CODAGREGACAO`) em vez de "produtos que existem nesse lote". Função antiga `consultar_lista_ultimas_vendas` ficou preservada por retrocompat — a substituta é `consultar_vendas_do_lote(codagregacao)`.

### Endpoint e fluxo

- `GET /sankhya/comercial/api/vendas-lote/?lote=X` → [`api_vendas_do_lote`](../../sankhya_integration/views.py) → [`consultar_vendas_do_lote`](../../sankhya_integration/services/oracle_conn.py)
- Frontend [comercialDistribuicao.js](../../sankhya_integration/static/sankhya_integration/comercialDistribuicao.js) faz **1 fetch único** que alimenta a lista lateral E o sparkline (sem dobrar query Oracle).

### Dedup pedido↔nota

Mesma regra da view `ANDRE_IAGRO_SALDO_LOTE` na perna `baixas_venda`:
- Prefere TOP 34 STATUSNOTA='L' com lote vinculado (verdade IAgro — atribuição pelo Rastreio)
- Aceita TOP 35/37 STATUSNOTA='L' **somente quando** não há par TGFVAR (operador faturou direto no Sankhya sem pedido pareado)

Evita mostrar pedido + nota como duplicata.

### Sparkline SVG inline

Card `#cardSparkVendas` (full width, no fim do `#distGrid` antes dos botões de ação). Renderizado por `window.ComercialDistribuicao.renderSparkline(pontos)`:

- Eixo Y: preço/kg auto-escalado com margem visual 10%
- Eixo X: cronológico (esquerda = mais antigo, direita = mais recente)
- Verde Agromil (`#5e7e4a`) — mesma paleta do Rastreio
- Linha tracejada horizontal mostrando **média**
- Pontos hover-ativos com tooltip (cliente + data + tipo + preço)
- Estatísticas no header do card: média, min, max, nº de vendas
- Estado vazio: `display: none` no card (não aparece se lote ainda não tem vendas)

Sem dependência externa (Chart.js/D3) — consistente com tanques combustível e gauge do comercial que também usam SVG inline.

### Decisões

- **Filtra por lote, mostra TODAS as vendas** (sem `LIMIT`). Lote típico esvazia em ~7 dias, então naturalmente fica entre 5-15 vendas
- **Sparkline mostra preço/kg, não margem real %**. Razão: preço/kg vem pronto da query; margem real exige cruzar com custo entrada (TOP 13 do mesmo lote) — fica pra etapa 2
- **JS limpa sparkline no `limpar()`** junto com o resto do estado — sem isso, troca de lote mostraria fantasma do anterior

---

## Margem do lote — card preenchido (Mai/2026 — 2026-05-17)

Card `#distMini1` "Margem Lote" agora calculado em runtime via novo endpoint.

### Fórmula

```
RECEITA_BRUTA = Σ VLRTOT vendas (TOP 34 'L' + TOP 35/37 'L' sem par TGFVAR — mesmo dedup)
DEVOLUÇÕES    = Σ VLRTOT TOP 36 STATUSNOTA='L' do lote
CUSTO         = Σ VLRTOT TGFITE TOP 13 STATUSNOTA<>'E' do lote

RECEITA_LIQ = RECEITA_BRUTA − DEVOLUÇÕES
LUCRO       = RECEITA_LIQ − CUSTO
MARGEM%     = LUCRO / RECEITA_LIQ × 100   (se RECEITA_LIQ > 0)
```

**Avaria interna (TOP 30) NÃO desconta no cálculo** — o vale (TOP 13) paga o lote inteiro independente de perdas, então a avaria naturalmente piora a margem via custo total sem receita correspondente. O backend devolve `avaria_qtd` + `avaria_vlr` (qtd × custo_médio/kg) **informativamente** pro tooltip mostrar a perda destacada — operador entende de onde veio o lucro menor sem dupla contagem.

### Estados visuais

| Estado | Quando | Aparência |
|---|---|---|
| **Sem dados** (—) | Nenhum lote selecionado OU `tem_custo=False` (vale ainda não lançado) | Cinza, valor "—" |
| **Positiva** | `MARGEM% > 0,05` | Verde (#16a34a), prefixo "+" |
| **Negativa** | `MARGEM% < -0,05` | Vermelho (#dc2626), prefixo "−" |
| **Neutra** | `≈ 0%` | Cinza (#64748b) |
| **Provisória** | `qtd_disponivel > 0` na view de saldo | Badge âmbar `⚠ provisória` no canto |
| **Fechada** | Lote esvaziou | Sem badge — número é definitivo |

### Tooltip detalhado (`title` HTML nativo)

```
Receita bruta:   R$ 9.000,00
(−) Devolução:   R$ 500,00
Receita líq.:    R$ 8.500,00
(−) Custo vale:  R$ 8.000,00
= Lucro:         R$ 500,00  (+5,9%)

Avaria: 100,0 kg × R$ 8,00/kg = R$ 800,00
   (custo perdido — já está no vale, não duplica)

Status: Provisória — lote ainda em estoque
```

### Endpoint e fluxo

- `GET /sankhya/comercial/api/margem-lote/?lote=X` → [`api_margem_lote`](../../sankhya_integration/views.py) → [`consultar_margem_do_lote`](../../sankhya_integration/services/oracle_conn.py)
- Chamado em **paralelo** com `carregarVendasNoModoAtual()` via `Promise.allSettled` no `preencher()` — não bloqueia uma chamada na outra
- Tolerância a falha da view `ANDRE_IAGRO_SALDO_LOTE`: assume `qtd_disponivel=0` (fechado) e segue retornando margem

### Limpeza

`limpar()` reseta: `data-margem-cor='neutro'`, `data-tipo-calculo=''`, valor "—", lucro "R$ 0,00", esconde badge. Cobre troca de lote.

---

## Travas do botão FATURAR (Mai/2026 — 2026-05-19)

Botão **FATURAR** do modal de faturamento ([comercialFinanceiro.js](../../sankhya_integration/static/sankhya_integration/comercialFinanceiro.js)) tem 2 travas dinâmicas pra evitar gerar TGFFIN inválido:

### Trava 1 — Preço (existente, mantida)

Em cada item iterado:
- **Classificáveis** (`item.geraproducao === 'S'`): bloqueia se `vlrTotal <= 0` (sem preço no vale TOP 13)
- **Não-classificáveis**: bloqueia se `vlrUnit <= 0 || vlrTotal <= 0`

### Trava 2 — Classificação finalizada (Mai/2026, nova)

**Apenas em produtos classificáveis** (`geraproducao = 'S'`):
- Bloqueia se `item.pendente !== 'N'` — ou seja, classificação ainda **pendente** (PENDENTE='S') ou inexistente (NULL, sem TGFCAB TOP 26)

Pra produtos NÃO-classificáveis, só preço importa (não há classificação envolvida).

### Tooltip discrimina os 2 motivos

```
"Existem produtos sem preço definido."
"Há classificáveis com classificação ainda não finalizada (finalize a TOP 26 antes)."
```

Se ambos faltam, mostra os 2 em linhas separadas.

### Defesa em profundidade — backend

Mesma trava replicada em `gerar_financeiro_banco` ([oracle_conn.py:3385-3415](../../sankhya_integration/services/oracle_conn.py#L3385)) **antes do INSERT do TGFFIN**:

```sql
SELECT COUNT(DISTINCT i13.CODAGREGACAO)
  FROM TGFITE i13
  JOIN TGFITE i11 ON i11.CODAGREGACAO = i13.CODAGREGACAO
  JOIN TGFCAB c11 ON c11.NUNOTA = i11.NUNOTA AND c11.CODTIPOPER = 11
 WHERE i13.NUNOTA = :n
   AND i13.CODAGREGACAO IS NOT NULL
   AND NVL(i11.GERAPRODUCAO, 'N') = 'S'
   AND NOT EXISTS (
       SELECT 1 FROM TGFCAB c26
       JOIN TGFITE i26 ON i26.NUNOTA = c26.NUNOTA
       WHERE c26.CODTIPOPER = 26 AND c26.STATUSNOTA <> 'E'
         AND c26.PENDENTE = 'N'
         AND i26.CODAGREGACAO = i13.CODAGREGACAO
   )
```

Operador burlando JS via console/API recebe `{ok: False, error: "Há N lote(s) classificável(eis) com classificação ainda não finalizada (TOP 26). Finalize a classificação antes de faturar."}`.

### Botão começa desabilitado (Mai/2026 — 2026-05-19)

Antes: ao abrir o modal, FATURAR aparecia clicável (`disabled=false` default do HTML) e só era desabilitado após o loop de validação. Causava "flash" visual enganoso.

Agora: o HTML do botão tem `disabled` + `title="Verificando travas..."` por default ([comercial.html:370](../../sankhya_integration/templates/sankhya_integration/comercial.html#L370)). Logo após `modal.style.display = 'flex'`, o JS reforça `disabled = true; cursor = 'wait'` ([comercialFinanceiro.js:33-40](../../sankhya_integration/static/sankhya_integration/comercialFinanceiro.js#L33)). Só após o loop de validação completo é que decide entre habilitar FATURAR, mostrar DESFATURAR (modo já-faturado), ou manter desabilitado com tooltip explicativo.

### Simulação de Negócio — ratio_medio default (Mai/2026 — 2026-05-19)

Bug: ao clicar **Aplicar** preenchendo só Extra (Qtd CX + Valor/CX) e deixando Médio em branco, `ratio_medio` virava `0` (vMd / vEx = 0 / X = 0). Aí em `preencher()` o cálculo distribuía 100% do total pro Extra e Médio ficava `R$ 0,00` em todos os campos — mesmo tendo kg físico de Médio.

Fix em [comercialDistribuicao.js:256-260](../../sankhya_integration/static/sankhya_integration/comercialDistribuicao.js#L256):

```js
// Antes
if (vEx > 0) dadosDaLinha.ratio_medio = vMd / vEx;
else dadosDaLinha.ratio_medio = 0.5;

// Depois
if (vEx > 0 && vMd > 0) dadosDaLinha.ratio_medio = vMd / vEx;
else dadosDaLinha.ratio_medio = 0.5;
```

Quando operador não preenche Médio, o sistema assume **default histórico 0.5** (Médio vale metade do Extra) — mesma constante usada como fallback no `?? 0.5` da linha 538 do `preencher()`.

---

## Avaria do fornecedor no modal Faturamento (Mai/2026 — 2026-05-19)

Modal Faturamento (`#modalFaturamento`) mostra ⚠ ao lado do nome do produto quando o lote teve avaria do fornecedor registrada na TOP 11 origem (campo `AD_QTDAVARIA` em produtos não-classificáveis — ver [`entrada.md`](entrada.md) → "Avaria do fornecedor em item NÃO-classificável").

### Backend — função aditiva pura de leitura

| Componente | Função |
|---|---|
| `consultar_avarias_fornecedor_de_pedido(nunota_pedido)` em [oracle_conn.py](../../sankhya_integration/services/oracle_conn.py) | Cruza CODAGREGACAO dos itens do pedido com TGFITE TOP 11 origem; retorna dict `{codagregacao: {qtd_avaria, qtd_entrada, fornecedor, dtneg_entrada}}` |
| `GET /sankhya/comercial/api/avarias-fornecedor-pedido/?nunota=N` | Endpoint REST consumido por `comercialFinanceiro.js` |

Função filtra `AD_QTDAVARIA > 0` e `STATUSNOTA <> 'E'` — só lotes com avaria real entram no payload. Pedidos sem lote vinculado retornam `{}` (modal renderiza normal, sem ícone).

### Frontend — fluxo do modal

1. `abrir(nunota)` faz fetch da avaria após carregar itens (não bloqueia render — `try/catch` tolerante)
2. `STATE.avariasPorLote` guarda `{codagregacao: {...}}`
3. Cada linha de produto em `htmlClass` e `htmlDireto` verifica se `STATE.avariasPorLote[lote]` existe
4. Se sim, injeta botão `<button class="cf-avaria-badge">` com ícone `⚠` Phosphor + `title=` (tooltip nativo)
5. Click no botão chama `window.ComercialFinanceiro.abrirAvariaDetalhe(lote)` → cria mini-modal `#avariaForncDetalheModal` em runtime (cache 1× por sessão)

### Mini-modal de detalhes

Renderizado com gradiente âmbar no header e tabela com:
- Lote (monospace)
- Fornecedor da entrada
- Data da entrada
- Qtd entrada / Qtd avaria / Qtd líquida (subtração)
- Nota explicativa: *"Esta perda foi registrada na Entrada (TOP 11) como descarte do fornecedor. Não desconta automaticamente do vale — orienta precificação e cobrança."*

Click fora do mini-modal ou no × fecha. Cor âmbar `#d97706` consistente com o ícone na linha.

### Toggle Descontar/Absorver com avaria interna automática (Mai/2026 — 2026-05-20)

**Decisão por lote** via segmented control sem ícones (só texto):

```
[ Absorver │ Descontar ]
```

- **Descontar (default quando há `AD_QTDAVARIA > 0` na TOP 11)**: Comercial cobra do fornecedor. Vale TOP 13 fica com qtd **LÍQUIDA** (`qtd_cx − avaria_unidade × peso`) + vlrTotal recalculado. **Sem TOP 30**. Estoque coerente naturalmente.
- **Absorver**: Agromil banca a perda. Vale TOP 13 fica com qtd **CHEIA** + vlrTotal cheio. Ao FATURAR, backend gera automaticamente TGFCAB TOP 30 (Avaria Interna) com `AD_NUMPEDIDOORIG = NUNOTA da TOP 11`. TGFITE TOP 30 desconta estoque via perna D da view `ANDRE_IAGRO_SALDO_LOTE` e carrega `VLRUNIT/VLRTOT` documentando o custo da perda.

Quando há vários itens não-classificáveis com avaria no mesmo pedido, **cada item tem seu próprio toggle**. Backend reconcilia tudo ao faturar (cria 1 TGFCAB TOP 30 por pedido com N itens TGFITE — 1 por lote/produto absorvido).

#### Reconciliação idempotente (cobre refaturamento)

Ao FATURAR, `reconciliar_avaria_top30_no_faturamento` sincroniza tanto vale TOP 13 (via B11) quanto TGFCAB TOP 30 (B6/B7) com a decisão final do toggle:

| Cenário | Comportamento |
|---|---|
| Faturar com Absorver pela 1ª vez | Reconciliação: vale fica com qtd cheia + cria TGFCAB TOP 30 |
| Faturar com Descontar pela 1ª vez | Vale com qtd líquida + sem TOP 30 |
| Desfaturar | TOP 30 permanece (não é mexida) |
| Refaturar mesma decisão | DELETE+INSERT idempotente — sem duplicação |
| Faturar Absorver → desfaturar → mudar Descontar → refaturar | Vale vira líquido + TOP 30 removida |
| Faturar Descontar → desfaturar → mudar Absorver → refaturar | Vale vira cheio + TOP 30 criada |

#### Trava de faturado

- Frontend: ambas opções do segmented control aparecem com `disabled` + ícone 🔒 quando vale tem TGFFIN
- Backend `atualizar_avaria_fornecedor_naoclass` (B10): se vale TOP 13 tem TGFFIN, rejeita UPDATE em AD_QTDAVARIA com mensagem `"Vale já faturado pra essa entrada (NUFIN=X). Desfature antes de alterar a avaria do fornecedor."`
- Backend `alternar_modo_avaria_vale_lote` (B12): mesma trava — operador não pode alternar se vale faturado

#### Funções backend (oracle_conn.py)

| # | Função | Responsabilidade |
|---|---|---|
| **B6** | `upsert_avaria_top30_lote(nunota_origem, codprod, codagregacao, qtd_avaria_unidade, codusu, nomeusu)` | Cria TGFCAB TOP 30 se não existir herdando `CODTIPVENDA` da TOP 11 origem (exigência do trigger `TRG_INC_TGFCAB`); DELETE+INSERT TGFITE com mesmo lote/produto (idempotente). Lê VLRUNIT do vale TOP 13 pra preencher VLRUNIT/VLRTOT da TOP 30 — documenta custo da perda |
| **B7** | `remover_avaria_top30_lote` | DELETE TGFITE; apaga TGFCAB se ficou sem itens. Idempotente — sem erro se já removido |
| **B8** | `reconciliar_avaria_top30_no_faturamento(nunota_origem, lotes_absorver, codusu, nomeusu)` | Orquestrador: SELECT itens TOP 11 não-classif. com avaria > 0; pra cada um **sincroniza vale TOP 13** (chama B11 com flag conforme decisão) + upsert/remove TOP 30 |
| **B9** | `gerar_financeiro_banco(... lotes_absorver_avaria=None, codusu=None, nomeusu=None)` | Quando `lotes_absorver_avaria` vier preenchido, chama B8 ANTES do INSERT TGFFIN. Backward compat: None ignora |
| **B10** | `atualizar_avaria_fornecedor_naoclass` | Trava de vale faturado (impede UPDATE em AD_QTDAVARIA quando vale tem TGFFIN) |
| **B11** | `upsert_preco_in_natura_modalFaturamento(... absorver_avaria_no_vale=True)` | Param novo: quando `False` (Descontar), vale TOP 13 recebe qtd LÍQUIDA + vlrTotal recalculado. Default `True` mantém comportamento original (backward compat com outros consumers) |
| **B12** | `alternar_modo_avaria_vale_lote(nunota_origem, codprod, codagregacao, absorver, codusu, nomeusu)` | Endpoint dedicado pra alternar toggle sem editar preço. Lê VLRUNIT atual do vale e reaplica B11 com a flag. Trava se vale faturado |

#### TGFITE TOP 11 (Entrada) NUNCA modificada

Preserva o documento original do recebimento do fornecedor (10 mç recebidos com 3 mç avariados). Toda variação vai pro vale TOP 13 ou pro TGFCAB/TGFITE TOP 30. Auditoria contábil intacta.

#### Motivos da trava do FATURAR (abaixo do botão)

Quando FATURAR está desabilitado, os motivos aparecem **explicitamente** numa lista amarela com ⚠ Phosphor abaixo do botão (além do tooltip nativo):

- *"Vale ainda não foi salvo. Lance o preço de pelo menos um produto pra criar o vale."*
- *"Há produto(s) sem preço definido."*
- *"Há lote(s) classificável(eis) com a classificação ainda não finalizada (finalize a TOP 26 antes)."*

A lista some quando o vale fatura ou quando todas as travas são resolvidas. Avaria **não bloqueia mais** — é decisão informada do Comercial via toggle.

#### Endpoints REST

| Endpoint | Função service | Payload |
|---|---|---|
| `POST /sankhya/comercial/api/efetivar-faturamento/` | `gerar_financeiro_banco` (com `lotes_absorver_avaria`) | `{nunota_13, vlr_forcar_bruto, vlr_forcar_liquido, lotes_absorver_avaria: [...]}` |
| `POST /sankhya/comercial/api/avaria-modo-vale/` (Mai/2026 — 2026-05-20) | `alternar_modo_avaria_vale_lote` (B12) | `{nunota_origem, codprod, codagregacao, absorver: bool}` |
| `GET /sankhya/comercial/api/avarias-fornecedor-pedido/?nunota=X` | `consultar_avarias_fornecedor_de_pedido` | Retorna `{lote: {qtd_avaria, fornecedor, ...}}` |

#### Fluxo do operador

```
1. Doca: registra Entrada com AD_QTDAVARIA = 3 mç (não-classificável)
2. Comercial: abre Modal Faturamento
   • Modal mostra qtd bruta (10), ⚠ ícone no nome, chip "Descontar" (default)
3. Comercial: digita preço → vale TOP 13 criado com qtd 10 (default absorver=True
   ainda no banco até reconciliação ajustar)
4. (opcional) Comercial: clica "Absorver" no chip
   → B12 dispara, reaplica B11 com flag=True → vale fica com qtd cheia
   → Modal reabre refletindo o novo estado
5. Comercial: clica FATURAR
   • Frontend envia lotes_absorver_avaria = [lotes onde operador clicou Absorver]
   • B9 → B8 reconcilia: sincroniza vale TOP 13 + TGFCAB TOP 30 conforme decisão
   • B9 INSERT TGFFIN normalmente
6. (se precisa corrigir) Comercial: clica DESFATURAR
   • TGFFIN apagado; TOP 30 permanece (não é mexida)
7. Comercial reabre modal, ajusta chip se quiser, refatura
   • B8 sincroniza idempotentemente: vale e TOP 30 batem com nova decisão
```

#### Refator do `abrir` (separação fetch × render + performance)

- `abrir(nunota)` faz fetches uma vez e popula `STATE.itensCalculados`
- Função pura `_renderListasFaturamento()` (sem fetch) usa STATE pra construir HTML, resumo e estado do botão
- Toggle dispara `setAbsorverAvaria()` → atualiza STATE + B12 backend → reabre modal pra refletir vale atualizado
- **Performance (Mai/2026 — 2026-05-20):**
  - Fetches em paralelo: avarias + cabeçalho do vale via `Promise.all`
  - Loop de itens (detalhes-vale + balanço de classificáveis) também `Promise.all` com `map`
  - Cache local `cacheVale` evita re-fetch quando 2 itens compartilham o mesmo lote
  - Ao faturar/desfaturar: helper `_aplicarEstadoFaturado(faturou)` atualiza botão+carimbo **imediatamente** após API responder. Refresh do modal vira fire-and-forget (não bloqueia feedback visual)
  - Tempo típico de abertura: ~1s (antes era ~4s sequencial)

#### Conversão de unidade (kg ↔ unidade do produto)

Avaria é registrada em kg na `AD_QTDAVARIA` da TOP 11. Pra descontar da quantidade da venda (mç, cx, kg, etc), conversão via PESO do TGFITE TOP 11:

```python
qtd_avaria_unidade = qtd_avaria_kg / peso  if peso > 0  else qtd_avaria_kg
qtd_liquida       = qtd_cx − qtd_avaria_unidade
```

Exemplo: CHEIRO VERDE 10mç com peso 1kg/mç + avaria 3kg → 3mç de avaria → 7mç líquido.

### Sem alteração de query existente

As funções aditivas `consultar_avarias_fornecedor_da_nota`, `consultar_avarias_fornecedor_de_pedido` e `consultar_lotes_com_top30_de_pedido` são Cat A pura (SELECT só). Não tocam queries pesadas existentes.

A modificação de `gerar_financeiro_banco` (B9) e `upsert_preco_in_natura_modalFaturamento` (B11) são Cat B porque alteram queries de escrita existentes — mas com backward compat por default arguments (`lotes_absorver_avaria=None`, `absorver_avaria_no_vale=True`).

---

## Testes

- `test_views_comercial.py` — comercial, faturamento, vales
- `test_vendas_lote.py` — `consultar_vendas_do_lote` (SQL+dedup+mapping) + endpoint `api_vendas_do_lote` (validação + delegação) — 10 tests
- `test_margem_lote.py` — `consultar_margem_do_lote` (positiva, negativa, zero, divisão por zero, devolução, avaria sem duplicar, PROVISORIA/FECHADA, tem_custo=False, falhas Oracle e da view) + endpoint `api_margem_lote` — 13 tests
