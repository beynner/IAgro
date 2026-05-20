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

**Decisão final**: o modal Faturamento mostra a avaria do fornecedor como **decisão por lote** via chip toggle:

- **📌 Absorver (default)**: Agromil banca a perda. Ao **FATURAR**, backend gera automaticamente TGFCAB TOP 30 (Avaria Interna) com `AD_NUMPEDIDOORIG = NUNOTA da TOP 11`. TGFITE TOP 30 desconta o estoque via perna D da view `ANDRE_IAGRO_SALDO_LOTE`.
- **📉 Descontar**: Comercial cobra do fornecedor (sem TOP 30; ajuste fica fora do escopo do IAgro).

Quando há vários itens não-classificáveis com avaria no mesmo pedido, **cada item tem seu próprio toggle**. Backend reconcilia tudo ao faturar (cria N TGFITE dentro de 1 TGFCAB TOP 30).

#### Reconciliação idempotente (cobre refaturamento)

Sequências cobertas sem duplicação ou inconsistência:

| Cenário | Comportamento |
|---|---|
| Faturar com Absorver pela 1ª vez | Cria TGFCAB TOP 30 + TGFITE |
| Desfaturar | TOP 30 permanece (não é mexida) |
| Refaturar mesma decisão | `upsert_avaria_top30_lote` faz DELETE+INSERT idempotente — sem duplicação |
| Faturar Absorver → desfaturar → mudar pra Descontar → refaturar | Reconciliação remove TGFITE TOP 30 do lote; apaga TGFCAB se ficou sem itens |
| Faturar Descontar → desfaturar → mudar pra Absorver → refaturar | Reconciliação cria TGFITE TOP 30 do lote |

#### Trava de faturado

- Frontend: toggle aparece como `🔒 Absorver` ou `🔒 Descontar` (readonly, cursor not-allowed) quando vale tem TGFFIN
- Backend `atualizar_avaria_fornecedor_naoclass` (B10): se vale TOP 13 do pedido tem TGFFIN, rejeita UPDATE em AD_QTDAVARIA com mensagem `"Vale já faturado pra essa entrada (NUFIN=X). Desfature antes de alterar a avaria do fornecedor."`

#### Funções backend (oracle_conn.py)

| Função | Responsabilidade |
|---|---|
| **B6** `upsert_avaria_top30_lote(nunota_origem, codprod, codagregacao, qtd_avaria_unidade, codusu, nomeusu)` | Cria TGFCAB TOP 30 se não existir (herda CODTIPVENDA da TOP 11 origem — exigência do trigger `TRG_INC_TGFCAB`); DELETE+INSERT TGFITE com mesmo lote/produto (idempotente). Reusa `inserir_cabecalho_nota_banco` + `inserir_item_nota_banco` |
| **B7** `remover_avaria_top30_lote(nunota_origem, codprod, codagregacao, codusu, nomeusu)` | DELETE TGFITE; apaga TGFCAB se ficou sem itens. Idempotente — sem erro se já removido |
| **B8** `reconciliar_avaria_top30_no_faturamento(nunota_origem, lotes_absorver, codusu, nomeusu)` | Orquestrador: SELECT itens TOP 11 não-classif. com avaria > 0; pra cada um → upsert ou remove conforme presença em `lotes_absorver` |
| **B9** `gerar_financeiro_banco(... lotes_absorver_avaria=None, codusu=None, nomeusu=None)` | Quando `lotes_absorver_avaria` vier preenchido, chama reconciliação ANTES do INSERT TGFFIN. Backward compat: None ignora |
| **B10** `atualizar_avaria_fornecedor_naoclass` | Trava de vale faturado |
| **B11** `upsert_preco_in_natura_modalFaturamento(... absorver_avaria_no_vale=True)` | Param novo: quando `False` (Descontar), vale TOP 13 recebe qtd LÍQUIDA (`qtd_cx - avaria_unidade`) + vlrTotal recalculado. Default `True` mantém comportamento original |
| **B12** `alternar_modo_avaria_vale_lote(nunota_origem, codprod, codagregacao, absorver, codusu, nomeusu)` | Alterna modo do toggle sem editar preço. Lê VLRUNIT atual do vale e reaplica `upsert_preco_in_natura_modalFaturamento` com a flag. Trava se vale faturado |

#### Visual do toggle

Segmented control sem ícones — só texto. Lado ativo destacado em verde:

```
[ Absorver │ Descontar ]
```

Default = Absorver (Agromil paga). Click em cada lado define explicitamente a decisão (não inverte).

#### Motivos da trava do FATURAR

Quando o botão FATURAR está desabilitado, os motivos aparecem **abaixo do botão** numa lista amarela com ícones ⚠ (além do tooltip):

- *"Vale ainda não foi salvo. Lance o preço de pelo menos um produto pra criar o vale."*
- *"Há produto(s) sem preço definido."*
- *"Há lote(s) classificável(eis) com a classificação ainda não finalizada (finalize a TOP 26 antes)."*

Some quando o vale fatura ou quando todas as travas são resolvidas.

#### Endpoint REST (B12)

`POST /sankhya/comercial/api/avaria-modo-vale/`
Payload: `{nunota_origem, codprod, codagregacao, absorver: true|false}`

Disparado pelo frontend ao clicar em qualquer opção do segmented control quando o vale já existe (preço lançado). Reabre o modal automaticamente após sucesso pra refletir QTDNEG/VLRTOT atualizados.

#### Fluxo do operador

```
1. Doca: registra Entrada com AD_QTDAVARIA = 3 mç (não-classificável)
2. Comercial: abre Modal Faturamento
   • Modal mostra qtd bruta (10), ⚠ ícone, chip "📌 Absorver" (default)
3. Comercial: digita preço → vale TOP 13 com QTDNEG=10, VLRTOT=300
4. (opcional) Comercial: alterna chip pra "📉 Descontar" no lote
5. Comercial: clica FATURAR
   • Frontend envia lotes_absorver_avaria = [lotes ainda marcados Absorver]
   • Backend reconcilia: cria/remove TGFCAB TOP 30 conforme presença
   • Backend gera TGFFIN normalmente
6. (se precisa corrigir) Comercial: clica DESFATURAR
   • TGFFIN apagado; TOP 30 permanece
7. Comercial reabre modal, ajusta chip se quiser, refatura
   • Reconciliação idempotente: sincroniza TOP 30 conforme nova decisão
```

#### Não confundir com Opção B descartada

Versão anterior (descartada): mostrava qtd líquida no modal e bloqueava FATURAR forçando refazer o vale. A regra atual reverteu: **vale TOP 13 fica sempre intocado** com qtd bruta — a perda vira TGFCAB TOP 30 separada. Documento de compra reflete o que veio do fornecedor; TOP 30 documenta a perda interna; estoque desconta via perna D.

#### Refator do `abrir` (separação fetch × render)

- `abrir(nunota)` agora faz fetches uma vez e popula `STATE.itensCalculados`
- Função `_renderListasFaturamento()` é pura (sem fetch) — usa STATE pra construir HTML, resumo e estado do botão
- Toggle dispara `_renderListasFaturamento()` + `recalcularLiquido()` — re-render instantâneo sem network

#### Visual do toggle

Cada item com `avariaLote.qtd_avaria > 0` ganha chip clicável na coluna Qtde:

| Estado | Aparência | Significado |
|---|---|---|
| **Off** (default) | `📌 Pagar total` em cinza | Agromil absorve a avaria; linha mostra qtd e total originais; fundo amarelo sutil |
| **On** | `📉 Descontar` em verde | Repassa avaria ao fornecedor; qtd e total originais aparecem riscados + líquidos em verde; fundo amarelo mais saturado |

Estado armazenado em `STATE.descontoAvariaPorLote = {codagregacao: bool}`, reset ao trocar de pedido.

#### Conversão de unidade

Avaria é registrada em kg (sempre). Pra descontar da quantidade da venda (mç, cx, kg, etc), o frontend converte:

```js
const qtdAvariaUnidade = pesoIn > 0 ? (qtdAvariaKg / pesoIn) : qtdAvariaKg;
const qtdLiquidaUnidade = Math.max(0, qtd - qtdAvariaUnidade);
```

Exemplo: CHEIRO VERDE 10mç com peso 1kg/mç + avaria 3kg → 3mç de avaria → 7mç líquido. Toggle "Descontar" mostra `<s>10mç</s> 7mç`.

#### Resumo financeiro

- `STATE.bruto` = soma dos vlrTotal originais (do vale)
- `STATE.brutoLiquido` = bruto − descontos aplicados (apenas dos lotes com toggle "Descontar")
- Quando há desconto: campo `vlrBrutoFechamento` mostra original riscado + líquido em verde
- `recalcularLiquido` parte de `STATE.brutoLiquido` (que cai em `STATE.bruto` quando todos os toggles estão "Pagar total")

#### Trava FATURAR (revisada)

Removida a trava por avaria. Botão FATURAR continua disabled apenas por:
- Preço em branco (`temPendentePreco`)
- Classificação não finalizada na TOP 26 (`temPendenteClassificacao`)

Avaria não bloqueia — é decisão informada do Comercial.

#### Trade-off conhecido

Quando o operador clicar FATURAR com algum toggle "Descontar":
- O TGFFIN será gerado com base em `STATE.bruto` (valor cheio) — **não usa o líquido** atualmente
- O vale TGFITE TOP 13 também não é atualizado

Pra desconto real refletir no financeiro/vale, fica como pendência futura (Cat B): hook em `gerar_financeiro_banco` que aplica o desconto OU UPDATE no TGFITE TOP 13 ao toggle ON.

Por ora, o toggle serve como **visualização decisória** pro operador antes de:
- Refazer o vale manualmente fora do modal, ou
- Renegociar preço com o fornecedor, ou
- Lançar TGFFIN separado de cobrança

### Sem alteração de query existente

A função `consultar_avarias_fornecedor_de_pedido` é **aditiva** (Cat A pura) — evita refator de funções existentes que alimentam `__COM_LIST_ROWS`. Frontend só ganha 1 fetch extra ao abrir o modal (sem impacto perceptível).

---

## Testes

- `test_views_comercial.py` — comercial, faturamento, vales
- `test_vendas_lote.py` — `consultar_vendas_do_lote` (SQL+dedup+mapping) + endpoint `api_vendas_do_lote` (validação + delegação) — 10 tests
- `test_margem_lote.py` — `consultar_margem_do_lote` (positiva, negativa, zero, divisão por zero, devolução, avaria sem duplicar, PROVISORIA/FECHADA, tem_custo=False, falhas Oracle e da view) + endpoint `api_margem_lote` — 13 tests
