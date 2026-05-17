# Módulo Comercial (TOP 13)

Faturamento de vales de compra, precificação, negociação e geração de financeiro.

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

## Testes

- `test_views_comercial.py` — comercial, faturamento, vales
- `test_vendas_lote.py` — `consultar_vendas_do_lote` (SQL+dedup+mapping) + endpoint `api_vendas_do_lote` (validação + delegação) — 10 tests
