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

## Decorator extra

- `@check_vale_lock` — lock para evitar concorrência em edição de vales

---

## Modelo Django relacionado

- **`Simulation`** (SQLite) — simulações comerciais persistidas. Audit via signals (`post_save`/`post_delete`). Registrado no Admin como `SimulationAdmin`.

---

## Testes

- `test_views_comercial.py` — comercial, faturamento, vales
