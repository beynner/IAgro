# Módulo Relatórios

Tela gerencial em `/sankhya/relatorios/` com 5 sub-abas (sub-relatórios) em lazy load — 1 fetch por aba ao ativar. Lançado em Mai/2026 (2026-05-17).

---

## 📈 Polish v1.1 — Visualizações + Comparação temporal + Drilldown (Mai/2026 — 2026-05-30)

Sessão de melhoria UX sem novo relatório — transformou o módulo de "lista pra conferir" em "ferramenta de decisão". **3 frentes Cat A** (zero alteração em query existente, zero escrita no banco):

### Frente 1 — Barras horizontais proporcionais

Cada tabela ganhou **barra de fundo** em CSS puro (sem SVG) mostrando o peso relativo da linha em relação ao máximo. Implementação:

```css
.rel-bar-cell::before {
    background: linear-gradient(90deg,
        rgba(94, 126, 74, 0.12) 0%,
        rgba(94, 126, 74, 0.12) var(--bar-pct, 0%),
        transparent var(--bar-pct, 0%));
}
```

Variantes:
- `.rel-bar-cell` — verde Agromil (default — bom)
- `.rel-bar-cell--neg` — vermelho (saídas/despesas)
- `.rel-bar-cell--warn` — âmbar (lotes críticos > 60d)

JS helper `barCell(valor, max, fmt, classExtra)` calcula o `--bar-pct` e formata. Cobertura: Top Clientes, Top Produtos, Lotes Envelhecidos (saldo), Consumo Veículos (litros), Fluxo de Caixa (entrada/saída), Margem por Venda (receita).

### Frente 2 — Comparação com período anterior

Cada relatório com período faz **2 fetches em paralelo**: atual + período espelhado anterior. Chip `+X% / −X% / 0%` aparece nos cards de resumo.

Helper `periodoEspelhadoAnterior(valor)`:
- `7 dias` → 7 dias imediatamente anteriores (-14d até -7d)
- `30 dias` → 30 dias anteriores (-60d até -30d)
- `mes-atual` → mês anterior completo
- `mes-anterior` → mês ante-anterior completo

Chip via `compChipHtml(atual, anterior, {invertirCor})`:
- Verde (`--up`) + ícone seta-cima quando bom (subida em receita; descida em despesa via `invertirCor`)
- Vermelho (`--down`) quando ruim
- Cinza (`--zero`) quando variação ≈ 0
- "Loading" cinza italic quando dado anterior ainda chegando (resiliente — falha silenciosa)

Aplicado em: Top Clientes (Valor total), Consumo Veículos (litros + valor, ambos com `invertirCor`), Margem por Venda (lucro + margem média).

### Frente 3 — Drilldown click → modal compartilhado

Toda linha de tabela é clicável (cursor pointer + hover verde Agromil). Click abre modal genérico `#relDrilldownOverlay` populado dinamicamente.

**6 tipos de drilldown via endpoint único** `GET /sankhya/relatorios/api/drilldown/?tipo=X&id=Y[&date_de=&date_ate=&agrupar=]`:

| Tipo | Origem (relatório) | id_principal | Dados detalhados |
|---|---|---|---|
| `cliente_vendas` | Top Clientes | CODPARC | Vendas do cliente no período (até 100) |
| `produto_vendas` | Top Produtos | CODPROD | Vendas do produto no período (até 100) |
| `lote_movs` | Lotes Envelhecidos | CODAGREGACAO (string) | Timeline completa do lote (até 200 movs) |
| `veiculo_reqs` | Consumo Veículo | CODVEICULO | Requisições no período (até 200) |
| `fluxo_bucket` | Fluxo de Caixa | Label do bucket (`ATRASADO`/`HOJE`/`1-7D`/etc) | TGFFIN em aberto no bucket (até 200) |
| `margem_detalhe` | Margem por Venda | CODPARC ou CODPROD | Vendas que compuseram a margem (com receita/custo/lucro por linha) |

**1 função service** `consultar_drilldown_relatorio(tipo, id_principal, date_de, date_ate, extras)` com switch interno. Tolerante a falha. Tudo SELECT puro.

**1 view** `api_relatorio_drilldown` valida tipo no enum + id numérico (exceto `lote_movs` e `fluxo_bucket` que aceitam string) + delega ao service.

**Link "Abrir no módulo"** no rodapé do modal aparece em tipos relevantes: `lote_movs` → `/sankhya/rastreio/?lote=X`; `veiculo_reqs` → `/sankhya/combustivel/`. Permite operador continuar a investigação no módulo nativo.

### Frente 4 — Polish visual

- **Ícone Atualizar** corrigido: `ph-arrow-clockwise` (singular, errado) → `ph-arrows-clockwise` (plural, padrão IAgro com 2 setas)
- **Resumo do período no topo** de cada relatório — 3 cards com totais (receita, lucro, margem média / entradas, saídas, saldo / litros total, valor, veículos / etc). Substituiu os `<div style="...">` inline do Fluxo de Caixa por classes (`.rel-resumo-card--entrada/saida/saldo/saldo-neg`)
- **Badge mini de TOP** no drilldown (`.rel-top-mini--35/37/11/13/...`) com cores diferenciadas por tipo de operação
- **Responsivo melhorado**: cards de resumo viram 2 colunas em ≤900px e 1 coluna em ≤520px; modal de drilldown 95vh em mobile

### Componentes principais

| Arquivo | Mudança |
|---|---|
| [oracle_conn.py](../../sankhya_integration/services/oracle_conn.py) | +`DRILLDOWN_TIPOS_VALIDOS` tupla + função aditiva `consultar_drilldown_relatorio` (~340 linhas, 6 switches SELECT puro) |
| [views.py](../../sankhya_integration/views.py) | +view aditiva `api_relatorio_drilldown` com validação + roteamento |
| [urls.py](../../sankhya_integration/urls.py) | +1 path `relatorios/api/drilldown/` |
| [relatorios.html](../../sankhya_integration/templates/sankhya_integration/relatorios.html) | +modal `#relDrilldownOverlay` no fim. Ícones `ph-arrow-clockwise` → `ph-arrows-clockwise` (5×). Cache `?v=2` |
| [relatorios.css](../../sankhya_integration/static/sankhya_integration/relatorios.css) | +200 linhas: `.rel-resumo*`, `.rel-comp-chip*`, `.rel-bar-cell*`, `.rel-row-clickable`, `.rel-drill-*`, `.rel-top-mini--*`, responsivo mobile |
| [relatorios.js](../../sankhya_integration/static/sankhya_integration/relatorios.js) | Refator completo (~1100 linhas). Refatorado de `async/await` arrow functions pra `Promise/var` legível (paridade outros módulos IAgro). 5 renderers ganham bars + comparação. `bindRowsDrilldown` delegado nos rows. Modal `DRILL.*` controlado por `abrirDrilldown/fecharDrilldown` |
| [test_relatorios.py](../../sankhya_integration/tests/test_relatorios.py) | +17 tests: `ConsultarDrilldownServiceTest` (9 — tipos válidos/inválidos, SQL filtra corretamente, falha Oracle) + `ApiDrilldownEndpointTest` (8 — validações HTTP, id string em lote/bucket, repasse de extras, acesso por sessão) |

### Tests

73 tests no total no módulo Relatórios (56 existentes + 17 novos). Todos passando. Zero regressão na suíte de Relatórios.

### Decisões consolidadas

1. **1 endpoint genérico** com switch interno em vez de 6 endpoints separados — reduz superfície de manutenção, padrão consistente.
2. **2 fetches paralelos** pra comparação temporal — endpoints existentes já aceitam `date_de/date_ate`, zero backend novo. Cache da margem amortiza naturalmente.
3. **Drilldown sem cache** — operador clica numa linha específica, espera dado fresco. Volume baixo (1 drilldown por sessão típica).
4. **Barra CSS pura, não SVG** — mais barato, mantém peso, acessível, gradiente nativo cobre 100% dos casos.
5. **`lote_movs` e `fluxo_bucket` aceitam ID string** — backend valida o enum de buckets (`ATRASADO`/`HOJE`/`1-7D`/etc); lote é regex livre.
6. **Comparação tolerante a falha** — se o fetch anterior falha, chip vira "loading cinza" mas relatório atual renderiza normal.
7. **Link "Abrir no módulo X" só em tipos onde faz sentido** — lote → Rastreio; veículo → Combustível. Demais ficam só com drilldown inline.

---

## Escopo (MVP)

5 relatórios em sub-abas, todos como **leitura pura** (Cat A) com tolerância a falha do Oracle (retornam dict vazio + `logger.exception`).

| # | Aba | Função service | Endpoint |
|---|---|---|---|
| 1 | Top Clientes + Top Produtos | `consultar_top_clientes_produtos` | `/api/top-clientes-produtos/` |
| 2 | Lotes Envelhecidos | `consultar_lotes_envelhecidos` | `/api/lotes-envelhecidos/` |
| 3 | Consumo por Veículo | `consultar_consumo_ranking_veiculos` | `/api/consumo-veiculos/` |
| 4 | Fluxo de Caixa | `consultar_fluxo_caixa` | `/api/fluxo-caixa/` |
| 5 | Margem por Venda (cliente × produto) | `consultar_margem_por_venda` | `/api/margem-venda/` |

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/relatorios/` | GET | Página HTML (`@ensure_csrf_cookie`) |
| `/sankhya/relatorios/api/top-clientes-produtos/` | GET | Top clientes + top produtos no período |
| `/sankhya/relatorios/api/lotes-envelhecidos/` | GET | Lotes com saldo parado há > N dias |
| `/sankhya/relatorios/api/consumo-veiculos/` | GET | Ranking de consumo de combustível |
| `/sankhya/relatorios/api/fluxo-caixa/` | GET | Fluxo de caixa projetado nos próximos N dias |
| `/sankhya/relatorios/api/margem-venda/` | GET | Margem por cliente/produto (com cache 5min) |

**Acesso:** Grupos `1` (Diretoria), `6` (Suporte), `9` (Comercial). Decorator `@exige_grupo('relatorios')` — mapeamento já em `decorators.py` (chave `relatorios`). Administrativo (10) NÃO tem acesso por decisão de produto (público-alvo é gerencial).

Sidebar: novo item com permissão `{% if "1" in grupos or "6" in grupos or "9" in grupos %}` antes do item Auditoria. Ícone Phosphor `ph-chart-bar`.

---

## Detalhe por relatório

### 1. Top Clientes + Top Produtos

**Fonte:** TGFCAB+TGFITE filtrando `CODTIPOPER IN (35, 37)` + `STATUSNOTA='L'` + período (`DTNEG BETWEEN :de AND :ate`).

**Agrupamento:**
- Clientes: por `TGFPAR.CODPARC` da matriz (`p.CODPARCMATRIZ` ou `p.CODPARC`)
- Produtos: por `TGFPRO.CODPROD`

**Métricas (3 modos):**
- `valor` (default): `SUM(VLRTOT)` — R$ vendido
- `qtd`: `SUM(QTDNEG)` — kg vendido
- `pedidos`: `COUNT(DISTINCT c.NUNOTA)` — nº de pedidos distintos

**Limite:** top 15 (default), max 50.

**Payload:**
```json
{
  "top_clientes": [{"codparc", "nome", "nome_full", "metrica"}, ...],
  "top_produtos": [{"codprod", "descrprod", "metrica"}, ...],
  "total_geral_clientes": float,
  "total_geral_produtos": float
}
```

### 2. Lotes Envelhecidos

**Fonte:** view `SANKHYA.ANDRE_IAGRO_SALDO_LOTE` (já dedup baixa pedido↔nota).

**Filtros:**
- `VENDAVEL = 'S'`
- `QTD_DISPONIVEL > 0` (lote ainda tem coisa pra vender)
- `TRUNC(SYSDATE - DTNEG_ORIGEM) >= :dias_min`

**Param `dias_min`:** default 30, clipado 0-365.

**Ordem:** `dias_parado DESC` (mais parado primeiro).

**Payload:**
```json
{
  "lotes": [
    {"codprod", "descrprod", "codagregacao", "fornecedor",
     "dtneg_origem", "qtd_entrada", "qtd_disponivel", "dias_parado"},
    ...
  ]
}
```

**Bandeiras (frontend):** `>30d` amarelo "ATENÇÃO" · `>60d` laranja "ALERTA" · `>90d` vermelho "CRÍTICO" · senão azul "OK".

### 3. Consumo por Veículo

**Fonte:** TGFCAB TOP 53 STATUSNOTA<>'E' + AD_REQUISICAO_COMBUSTIVEL + TGFITE + TGFVEI no período.

**Métricas agregadas por `CODVEICULO`:**
- `litros_total = SUM(QTDNEG)`
- `valor_total = SUM(VLRTOT)`
- `qtd_reqs = COUNT(DISTINCT NUNOTA)`
- `hod_max / hod_min / hor_max / hor_min` (de AD_REQ)

**Eficiência (calculada em Python):**
- COM (frota): se `hod_max > hod_min` e `litros > 0` → `km/L = (hod_max - hod_min) / litros`
- MAQ (maquinário): se `hor_max > hor_min` e `litros > 0` → `L/h = litros / (hor_max - hor_min)`
- Senão: `'—'`

**Tipo COM vs MAQ (via keywords em ESPECIETIPO):**
- MAQ_KEYWORDS = TRATOR · COLHEIT · MAQUINA · PULVERIZ · EMPILHA · RETROESCAV · CARREGA
- Qualquer veículo com `ESPECIETIPO` contendo alguma dessas → MAQ; senão COM
- Param `tipo=MAQ` adiciona `AND (UPPER(ESPECIETIPO) LIKE '%TRATOR%' OR ...)` no WHERE
- Param `tipo=COM` adiciona `AND (UPPER(ESPECIETIPO) NOT LIKE '%TRATOR%' AND ...)`

**Payload:**
```json
{
  "veiculos": [
    {"codveiculo", "placa", "marcamodelo", "especietipo", "proprio",
     "tipo": "COM" | "MAQ",
     "litros_total", "valor_total", "qtd_reqs",
     "medidor_total", "eficiencia_label": "X,XX km/L" | "X,XX L/h" | "—"},
    ...
  ],
  "total_litros": float, "total_valor": float
}
```

### 4. Fluxo de Caixa Projetado

**Fonte:** TGFFIN em aberto + `DTVENC` dentro do horizonte (default 60d).

**"Em aberto":** `DHBAIXA IS NULL OR DHBAIXA <= TO_DATE('01/01/1998', 'DD/MM/YYYY')` — Sankhya usa sentinel 01/01/1998 pra "não baixado ainda" (convenção também usada em `criar_entrada_combustivel_banco`).

**Sinal:** `RECDESP > 0` → entrada (receber); `RECDESP < 0` → saída (pagar).

**Buckets (via CASE):**
```
ATRASADO  → DTVENC < hoje
HOJE      → DTVENC = hoje
1-7d      → 1-7 dias à frente
8-15d     → 8-15
16-30d    → 16-30
31-60d    → 31-60   (só aparece se horizonte >= 60)
61-90d    → 61-90   (só aparece se horizonte >= 90)
```

**Saldo acumulado:** progressivo bucket-a-bucket (`saldo[i] = saldo[i-1] + entrada[i] - saida[i]`).

**Param `dias`:** default 60, clipado 7-180.

**Payload:**
```json
{
  "buckets": [
    {"label", "ordem", "entrada", "saida", "saldo_acumulado"}, ...
  ],
  "total_entrada": float, "total_saida": float
}
```

### 5. Margem por Venda (cliente × produto)

**Mais complexo dos 5** — JOIN cruzado via CODAGREGACAO + cache.

**CTE `custos_lote`:** agrega por lote o custo total do vale (TOP 13) e a qtd entrada (TOP 11):
```sql
WITH custos_lote AS (
    SELECT
        ite.CODAGREGACAO,
        SUM(CASE WHEN cab.CODTIPOPER = 13 THEN VLRTOT END) AS custo_total_vale,
        SUM(CASE WHEN cab.CODTIPOPER = 11 THEN QTDNEG END) AS qtd_entrada_total
      FROM TGFCAB cab JOIN TGFITE ite ON ite.NUNOTA = cab.NUNOTA
     WHERE cab.STATUSNOTA <> 'E' AND cab.CODTIPOPER IN (11, 13)
       AND ite.CODAGREGACAO IS NOT NULL
     GROUP BY ite.CODAGREGACAO
)
```

**Query principal:** vendas TOP 35/37 'L' LEFT JOIN custos_lote por CODAGREGACAO.

**Custo proporcional:**
```sql
qtd_vendida × (custo_total_vale / qtd_entrada_total)
```

Linhas sem vale/entrada caem com `custo_kg=NULL` → custo=0 (conservador). Margem nesse caso será 100% (suspeito → frontend mostra com bandeira amarela/vermelha).

**Agrupamento:** `cliente` (CODPARCMATRIZ) ou `produto` (CODPROD).

**Cache:**
- Engine: `django.core.cache` (in-memory padrão Django dev; em prod precisa de Redis se quiser persistente)
- Chave: `rel:margem:{date_de}:{date_ate}:{agrupar}`
- TTL: 300s (5 min)
- Invalidação: TTL OR `?nocache=1` no query param

**Bandeiras (frontend):**
- `≥ 15%` → verde "BOM"
- `≥ 5%` → amarelo "OK"
- `≥ 0%` → laranja "BAIXA"
- `< 0%` → vermelho "PREJU"

**Payload:**
```json
{
  "linhas": [
    {"codigo", "nome", "receita", "custo", "lucro", "margem_pct", "qtd_vendida"},
    ...
  ],
  "total_receita": float, "total_custo": float,
  "total_lucro": float, "margem_media": float
}
```

---

## Frontend — arquivos

| Arquivo | Função |
|---|---|
| `templates/sankhya_integration/relatorios.html` | 5 sub-abas via segmented control + 5 `<article class="rel-pane">` (1 ativo por vez) |
| `static/sankhya_integration/relatorios.css` | Tabs, painéis, filtros, tabela genérica `.rel-tabela`, bandeiras `.rel-bandeira--*` |
| `static/sankhya_integration/relatorios.js` | IIFE com 5 RENDERERS (1 por aba), lazy load (`carregado` flag), helpers `fmtBRL/fmtPct/escapeHtml`, switch de tabs, fetch padronizado com estado loading/erro/vazio |

**Lazy load**: cada renderer guarda flag `carregado` interna. `carregar(force)` retorna early se já carregado e `force` é false. Ativar uma aba a 1ª vez dispara fetch; depois fica em cache até `force=true` (refresh button, change de filtro).

**Switch de período**: chips com `data-periodo` (7/30/90/mes-atual/mes-anterior). Helper `periodoToDatas(valor)` converte pra `{date_de, date_ate}` em formato `YYYY-MM-DD`.

**Estados visuais padronizados**:
- `.rel-loading` aplica overlay branco semi-transparente
- `.rel-empty` (cinza) e `.rel-error` (vermelho) com ícone Phosphor
- `.rel-btn-refresh.is-loading` anima ícone com spin

**Responsivo**:
- ≤900px: tabs com `overflow-x: auto` (scroll horizontal); botão refresh sem `margin-left: auto`
- ≤520px: tabs só ícone (`span` escondido)

---

## Tests

`test_relatorios.py` — **56 testes** distribuídos em:

| Classe | Cobertura | Nº |
|---|---|---|
| `AcessoRelatoriosTest` | Diretoria/Suporte/Comercial entram; Administrativo + sem sessão bloqueados | 5 |
| `ConsultarTopClientesProdutosTest` | Datas vazias, SQL filtros corretos (TOP 35/37 'L'), 3 métricas, payload completo, fallback Oracle | 6 |
| `ApiTopClientesProdutosViewTest` | 400 sem datas, métrica inválida cai em 'valor', limite clipado, sem sessão bloqueia | 6 |
| `ConsultarLotesEnvelhecidosTest` | SQL filtra view, dias_min inválido → default, payload completo, falha view | 4 |
| `ApiLotesEnvelhecidosViewTest` | Default 30d, dias_min custom, clip em 365 | 3 |
| `ConsultarConsumoRankingVeiculosTest` | Datas vazias, SQL filtra TOP 53, filtro tipo MAQ inclui keywords, COM exclui, eficiência km/L vs L/h, sem medidor → '—', totais | 8 |
| `ApiConsumoVeiculosViewTest` | 400 sem datas, payload, filtro tipo, tipo inválido vira vazio | 4 |
| `ConsultarFluxoCaixaTest` | SQL com sentinel 01/01/1998, horizonte clipado 7-180, pula buckets fora do horizonte, saldo acumulado, falha Oracle | 5 |
| `ApiFluxoCaixaViewTest` | Default 60d, horizonte 90 | 2 |
| `ConsultarMargemPorVendaTest` | Datas vazias, CTE custos_lote no SQL, agrupar cliente/produto/inválido, cálculo margem, receita=0 sem div/zero, falha Oracle | 8 |
| `ApiMargemVendaViewTest` | 400 sem datas, payload valido, **cache hit evita 2º fetch**, `?nocache=1` força refetch, agrupamentos diferentes têm chaves distintas | 5 |

`setUp` do `ApiMargemVendaViewTest` chama `cache.clear()` pra isolar testes.

---

## Backlog restante (20 relatórios)

Os outros 20 relatórios mapeados na sessão de planejamento (em `roadmap.md` → "Módulo Relatórios — Backlog planejado") estão **fora do MVP intencionalmente**. Aguardando feedback operacional pra priorizar:

- **Financeiro:** contas a pagar vencendo, inadimplência
- **Vendas:** curva ABC, pedidos não faturados envelhecidos, avarias e devoluções
- **Compras/Estoque:** giro de lote por fornecedor, aproveitamento por lote, compras por fornecedor, rendimento da classificação
- **Rastreio/WMS:** lotes sem vínculo a pedido, pedidos faturados sem lote, notas órfãs
- **Combustível:** custo por veículo/período, abast. externo vs interno, frequência
- **Auditoria/Produtividade:** lançamentos por operador, operações estornadas, pedidos email confirmados vs descartados

---

## Export Excel/PDF — fora do MVP

Decisão consciente: começar só com tela web. Operador decide quais relatórios realmente precisa exportar depois de usar. Stack já tem `reportlab` (PDF) e seria simples adicionar `openpyxl` se aparecer demanda.

---

## Decisões consolidadas

1. **Lazy load por aba** (vs carregar tudo no boot) — economia de query desnecessária; operador raramente abre as 5 abas na mesma sessão.
2. **Cache só na margem** — outras queries são leves, não vale o overhead. Margem tem CTE pesada (3 tabelas grandes).
3. **Função antiga `consultar_lista_ultimas_vendas` preservada** — retrocompat. Função nova `consultar_vendas_do_lote` (Comercial) é da mesma família mas com dedup TGFVAR.
4. **Dedup pedido↔nota só onde faz sentido** — Top Clientes/Produtos usa TOP 35/37 direto (vendas faturadas Sankhya); Margem só TOP 35/37 'L' também (não TOP 34, porque pedido sem nota não tem receita realizada).
5. **Tolerância a falha do Oracle** em todas as 5 funções service — retornam dict vazio (com estrutura completa) + `logger.exception`. Frontend trata como "sem dados".
6. **Frontend sem framework** — JS puro, IIFE, padrão do projeto. Reuso de Phosphor Icons + paleta verde Agromil.
