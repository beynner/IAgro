# Módulo Classificação (TOP 26)

Triagem e classificação de lotes por qualidade com controle de descartes.

---

## Escopo

- Listar lotes pendentes de classificação (provenientes da Entrada/TOP 11 com `GERAPRODUCAO='S'`)
- Classificar quantidades por qualidade
- Registrar descartes em `AD_QTDAVARIA`
- Confirmar classificação criando TOP 26
- Modais de detalhes do lote

---

## URL e acesso

| Rota | Acesso |
|---|---|
| `/sankhya/compras/classificacao/` | Grupos `1`, `6`, `8` |

---

## Views principais (`views.py`)

| View | Propósito |
|---|---|
| `view_classificacao_lote` | Página HTML do portal |
| `api_lotes_classificacao` | Lista lotes pendentes |
| `api_detalhes_lote` | Detalhes de um lote específico |

---

## Regras específicas

- **`AD_QTDAVARIA`** registra descarte que vira a **perna E** (`AVARIA_FORNECEDOR`) na view `ANDRE_IAGRO_SALDO_LOTE` do WMS.
- Lote só fica disponível para vincular em pedido (Rastreio) **após** existir TOP 26 confirmada → vira **perna A** (`CLASSIFICADO`).
- Lotes ainda sem TOP 26 ficam como **perna C** (`AGUARDANDO_CLASSIFICACAO`) — não-vendáveis.
- Auto-cura de `AD_NUMPEDIDOORIG` aplicável (mesmo padrão da Entrada).

---

## Cabeçalho do modal de itens — fornecedor da TOP 11 (Mai/2026 — 2026-05-19)

`api_consultar_lote` ([views.py:1582+](../../sankhya_integration/views.py#L1582)) lê metadados do lote pra preencher o cabeçalho do modal. Antes podia trazer o **cliente da venda** (TOP 35/37) em vez do **fornecedor da compra** (TOP 11) — bug.

**Causa**: queries usavam `MAX(NUNOTA) FROM TGFITE WHERE CODAGREGACAO=:l AND GERAPRODUCAO='S'`. Como `GERAPRODUCAO='S'` é copiado pra TGFITE de outras TOPs ao longo do fluxo, MAX pegava o NUNOTA mais recente — quase sempre venda.

**Fix**: força `CODTIPOPER = 11` + `STATUSNOTA <> 'E'` em ambas queries (recuperação do nunota_origem + metadados):

```sql
SELECT MAX(c.NUNOTA)
  FROM TGFITE i
  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
 WHERE i.CODAGREGACAO = :l
   AND c.CODTIPOPER = 11
   AND c.STATUSNOTA <> 'E'
```

```sql
SELECT p.NOMEPARC, c.DTNEG, pr.DESCRPROD, c.CODPARC
  FROM TGFCAB c JOIN TGFPAR p ON p.CODPARC = c.CODPARC
       JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
       JOIN TGFPRO pr ON i.CODPROD = pr.CODPROD
 WHERE c.NUNOTA = :n AND i.CODAGREGACAO = :l
   AND c.CODTIPOPER = 11
   AND ROWNUM = 1
```

Cabeçalho do modal sempre exibe o **fornecedor de compra** (ex: JOSE MARIA), nunca o cliente da venda (ASSAI ARAGUAINA).

---

## Trava de edição quando lote foi pro Comercial (Mai/2026 — 2026-05-19)

### Regra atual (revisada)

A Classificação só bloqueia edição/exclusão de itens de um lote **se existe TGFITE TOP 13 (Vale de Compra) com aquele CODAGREGACAO**. Vendas TOP 35/37 **não** bloqueiam mais.

```sql
SELECT COUNT(1) FROM TGFCAB c
JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
WHERE c.CODTIPOPER = 13 AND i.CODAGREGACAO = :l
```

Sem filtro de `STATUSNOTA` (mesmo vale excluído ou em qualquer estado conta — só o que importa é a **existência da linha em TGFITE TOP 13**).

**Para destravar**, operador no Comercial usa `zerar_negociacao_banco` (DELETE dos TGFITE TOP 13 do lote, preservando outros produtos do vale). Contagem zera naturalmente e Classificação libera edição.

### Onde a trava está aplicada (3 lugares em [views.py](../../sankhya_integration/views.py))

| Linha aprox | Endpoint | Mensagem |
|---|---|---|
| 1639-1648 | `api_consultar_lote` (abertura do modal de itens) | Frontend recebe `bloqueado_comercial: true` e desabilita botões/inputs do modal |
| 1111-1118 | salvar/editar item (TOP 26) | `"Bloqueado! O Lote {lote} já foi negociado e não pode ser editado."` |
| 1236-1247 | excluir item (TOP 26) | `"Bloqueado! Lote {lote} já foi negociado pelo Comercial."` |

Frontend ([classificacao.js:1059-1085](../../sankhya_integration/static/sankhya_integration/classificacao.js#L1059)) trata `bloqueado_comercial: true` desabilitando todos os botões/inputs do modal de itens + toast `"🔒 Lote possui negociação Comercial. Edições bloqueadas."`.

### Trava de edição da TOP 11 (Entrada) — não tocada

Em `top_atual == 11` (Entrada), a regra continua a antiga: bloqueia se já existe TGFITE TOP **13 ou 26** com o lote (`STATUSNOTA <> 'E'`). Faz sentido — alterar a Entrada depois de já ter sido classificada criaria inconsistência grave.

### Bug fix do descarte (Mai/2026 — 2026-05-19)

`api_update_descarte_lote` ([views.py:1759-1808](../../sankhya_integration/views.py#L1759)) buscava `NUNOTA, AD_QTDAVARIA` filtrando só `CODAGREGACAO + GERAPRODUCAO='S'` — sem TOP. Como `GERAPRODUCAO='S'` é copiado pra TGFITE de outras TOPs (13, 26, 35), `fetchone()` podia pegar a linha errada e atualizar em lugar errado. Operador "não conseguia zerar o descarte" mesmo clicando vários vezes.

Fix: forçar `CODTIPOPER = 11` no SELECT (a origem real do descarte do fornecedor está só na TOP 11):

```sql
SELECT c.NUNOTA, NVL(i.AD_QTDAVARIA, 0)
  FROM TGFITE i
  JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
 WHERE i.CODAGREGACAO = :l
   AND i.GERAPRODUCAO = 'S'
   AND c.CODTIPOPER   = 11
   AND c.STATUSNOTA  <> 'E'
```

---

## 📱 Redesign Mobile app-like (Mai/2026 — 2026-05-26)

Mesma arquitetura da Entrada Mobile: HTML único com 2 containers paralelos (`.classificacao-desktop` + `.classificacao-mobile`), escopados por `body[data-active-module="classificacao"]` em viewport ≤900px. Desktop preservado 100% intacto.

### Estrutura mobile

| Componente | Arquivo |
|---|---|
| Template | `classificacao.html` — bloco `.classificacao-mobile` com 2 telas + 2 bottom sheets |
| CSS | `classificacao.css` — bloco "REDESIGN MOBILE-FIRST — Classificação" |
| JS | `classificacao_mobile.js` (~600 linhas) — só ativa ≤900px |

### 2 telas mobile

1. **Lista de lotes** — cards 1 linha (26px altura) com cor de status:
   - 🟢 Verde — Classificação Finalizada
   - 🟡 Âmbar — Classificando (em andamento)
   - 🔴 Vermelho — A Classificar (pendente)
2. **Detalhe do lote** — hero (Fornecedor / Produto / Pedido + Data) · grid 4 cards de resumo (In natura · Classificado · Descarte · Estoque com kg e %) · toggle "Classificação Finalizada" · lista de produtos classificados read-only · FAB redireciona pro editor desktop

### 2 bottom sheets

- **Filtros** — Status chips (Finalizada/Classificando/A Classificar com ícone colorido) + Data ini/fim com `<<` `>>` + Pedido + Produto (typeahead fabricante) + Parceiro (typeahead CODPARC) + Lote (texto)
- **Descarte** — input numérico grande + toggle "+ Adicionar / − Subtrair" + Confirmar → POST `/sankhya/item/update_descarte_lote/`

### Backend reusado (zero novo endpoint)

| Endpoint | Uso |
|---|---|
| `GET /sankhya/compras/classificacao/api/lotes/` | Lista paginada com filtros e status |
| `GET /sankhya/lote/consultar/?lote=X` | Detalhe completo (entradas + classificações + resumo) |
| `POST /sankhya/item/toggle_status/` | Toggle finalizada |
| `POST /sankhya/item/update_descarte_lote/` | Atualizar descarte |

### Decisão pragmática

**Adicionar nova classificação** e **editar item classificado** continuam redirecionando pro editor desktop com `?open=items&sel=LOTE`. Razão: o modal `modalClassify` tem fluxo complexo (Origem + Planificar + Salvar com SQL preview + múltiplas saídas) — replicar fielmente em mobile é trabalho grande. A visualização mobile já entrega ~80% do valor (operador de doca confere status dos lotes, lança descarte, fecha classificação no celular).

### Features herdadas da Entrada Mobile

- Navegação stack com back button do Android
- **Swipe-to-back (gesto touch da esquerda → direita) na tela `detalhe`** — obrigatório em toda tela diferente da `lista` raiz. Implementado em `setupSwipeToBack()` ([classificacao_mobile.js:764](../../sankhya_integration/static/sankhya_integration/classificacao_mobile.js#L764)) registrando handler em todas as `m-screen` exceto `lista`. Threshold 35% da largura OU velocidade > 0.5px/ms. Detecta eixo dominante nos primeiros 10px (cancela se vertical pra preservar scroll). Padrão alinhado com [`conventions.md`](../conventions.md) → "Gestos touch"
- Bottom nav (Lotes / Buscar / Filtros / Mais)
- Search client-side filtra por produto/parceiro/lote (debounce 250ms)
- Hambúrguer abre sidebar IAgro global
- Toast verde/vermelho via `IAgro.showToast`

### Polish 2026-05-27 — paridade com Entrada Mobile

Aplicado sweep equivalente ao da Entrada (sem swipe-to-edit/delete, sem busca server-side, sem trava 90 dias — decisão pragmática porque o filtro padrão "Classificando + A Classificar" já restringe o universo). Detalhes:

| Item | Implementação |
|---|---|
| **User badge + Sair no header** da tela lista | Pílula verde `#f0f5ec` + texto `#4a633a` uppercase + link Sair vermelho. Some em telas internas |
| **FAB azul Atualizar** (`ph-arrows-clockwise`) | 2 botões: (1) na tela lista — recarrega `carregarLotes()` inteiro; (2) na tela detalhe — re-fetch só do lote atual (`/sankhya/lote/consultar/?lote=X`) sem voltar pra lista. Spinner via `.is-loading` |
| **Badge "filtros ativos"** no bottom nav | Bolinha vermelha + ícone fill quando algum filtro foi tocado. `temFiltroAtivo()` considera: datas, pedido, produto, parceiro, lote, **status chips com combinação diferente do default** (default = AMARELO + VERMELHO ativos) |
| **iOS Safari data picker** | `setupDateReplica()`: listener `input` + `change` no `m_clss_filtroStart`, replica **sempre** em `m_clss_filtroEnd` (sem comparar) — iPhone só dispara `change` quando picker fecha |
| **`ph-dots-three`** (não `ph-dots-three-outline`) | Padronização ícone "Mais" do bottom nav |

**Busca server-side não foi adicionada** — filtro padrão restringe ao universo "Classificando + A Classificar" naturalmente. Operador raramente quer ver lotes finalizados; quando quer, marca o chip Verde nos filtros.

**Sem paginação / sem scroll infinito / sem trava de data** (decisão operador 2026-05-27):
- Mobile envia `limit=10000` no fetch → traz TODOS os lotes do filtro padrão em 1 chamada
- Quando datas vazias, mobile envia `date_start=2000-01-01&date_end=2099-12-31` pra desativar a trava de 60 dias do backend (`oracle_conn.py:1614` — `AND t.DTNEG >= SYSDATE - 60`)
- Filtro padrão de status (AMARELO + VERMELHO = Classificando + A Classificar) já restringe o universo — operador raramente tem >1000 lotes ativos
- Backend `api_listar_lotes_classificacao` ganhou aceitação de `limit` na URL (Cat A — só repassa pro dict de filtros, função service `listar_lotes_para_classificacao` já aceita esse parâmetro). Teto defensivo: 50.000
- Sem `limit` na URL, backend mantém default 50 (desktop preserva paginação com scroll infinito)

### Bottom sheet "Itens — Nota" + edição inline (Mai/2026 — 2026-05-27, big bang)

Substitui o redirect pro editor desktop. **FAB verde +** e **botão lápis no header da tela detalhe** abrem o sheet `data-sheet="itens"` espelhando o `#cabItemsModal` do desktop.

#### Componentes do sheet

| Componente | Detalhe |
|---|---|
| Form de inserção | Produto (typeahead com filtro `fabricante=` lido de `dadosLote.resumo.fabricante`) + Total KG + Total CX + Peso CX + botão "Adicionar item" |
| Auto-cálculo Total CX | `Math.ceil(totalKg / pesoCx)` no `input/blur` do Total KG e Peso CX |
| Lista "Itens classificados" | **Mostra SÓ o item recém-salvo na sessão atual** (feedback visual) — contador continua exibindo total real do lote. Ao abrir o sheet, lista volta vazia ("Nenhum produto adicionado nesta sessão") |
| Descarte | **MOVIDO** pra tela detalhe (abaixo do toggle Finalizada). Não mora mais no sheet |
| Toggle Finalizada | **MOVIDO** pra tela detalhe. Não mora mais no sheet |

#### Fluxo de salvamento (paridade com `saveItem` do desktop)

1. Validações: Produto obrigatório, Total KG > 0, Peso CX > 0
2. Se `nunota_class` é NULL → POST `/sankhya/compras/central/salvar/` cria TGFCAB TOP 26 (codtipoper=26, codnat=20010100, codcencus=10100)
3. POST `/sankhya/item/save/` com `codvol: 'KG'`, `peso`, `qtdneg`, `geraproducao='N'`, `codagregacao=lote`
4. Re-fetch `/sankhya/lote/consultar/?lote=X` → atualiza `ESTADO.dadosLote` + re-renderiza tela detalhe + card do recém-adicionado
5. Form limpo, foco no Produto, modo edição zerado

#### Modo edição (via swipe-to-edit nos cards de Produtos Classificados)

- Swipe esquerda no card revela **2 botões 44px (88px total)**: lápis azul (`#2563eb`) + lixeira vermelha — paridade Entrada Mobile
- Click no lápis: abre o sheet pré-preenchido com `{sequencia, codprod, descrprod, qtd, peso, codvol}` do item. Botão "Adicionar item" vira "Salvar alterações". Backend faz UPDATE quando `sequencia` no payload
- Click na lixeira: `IAgro.confirmarAcao` → POST `/sankhya/item/delete/` (com `apenas_checar` primeiro pra validar trava do Comercial) → confirma definitivo. Se for o último item, TGFCAB TOP 26 é removida (backend retorna `cabecalho_excluido: true`)
- **Click no card em modo swipe-open fecha o swipe** (padrão "cancelar implícito" — vide [`conventions.md`](../conventions.md))
- Reset automático: `fecharTodosSwipesProdutos()` chamada em `setActiveScreen` + `openSheet` pra evitar swipes "presos"

#### Hero card + descarte inline + header limpo (Mai/2026 — 2026-05-27)

Tela detalhe redesenhada:

```
[← back]   [empty title-block]   [🗑 descarte]   [✏ lápis abre sheet]
  HOMOLOGAÇÃO badge (vem do app shell)

┌─────────────────────────────────────┐
│ Hero card (m-clss-hero)             │
│   FORNECEDOR     FELIPE CHACARA     │
│   PRODUTO        CHUCHU IN NATURA   │
│   PEDIDO · DATA  Pedido 113821      │
│   Lote           113821S01D260527   │  ← fonte menor (10.5px)
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 4 cards resumo (2x2, 2 linhas cada) │
│  IN NATURA            CLASSIFICADO  │
│  1.200,0  kg          0,0  kg 0%    │
│  DESCARTE             ESTOQUE       │
│  0,0  kg 0%           1.200,0  kg   │
└─────────────────────────────────────┘

Classificação Finalizada  [toggle]
Descarte (kg):  0,0   [+] [−]   ← inline, abaixo do toggle

PRODUTOS CLASSIFICADOS         N
   [cards com swipe edit+delete]

  [🔄 FAB azul]    [+ FAB verde]
```

- Header sem `<h1>` nem subtitle (info do lote/fornecedor vive no hero)
- Descarte +/- mostra `prompt()` pedindo qtd em kg + `chamarUpdateDescarteBackend('soma'|'subtrai', valor)` → re-fetch lote
- Toggle Finalizada chama `chamarToggleStatusBackend(toggleEl)` com payload `{nunota_class, pendente}` (paridade desktop)

#### Fixes de paridade web (consolidação Mai/2026 — 2026-05-27)

| Bug | Causa | Fix |
|---|---|---|
| Typeahead 404 | URL `/sankhya/produtos/pesquisar-modal/` errada | Corrigido pra `/sankhya/produtos/search/modal/` |
| Typeahead vazio mesmo com produto cadastrado | Mobile passava `fabricante=DESCRPROD` (errado) | Lê de `dadosLote.resumo.fabricante` (= TGFPRO.FABRICANTE, mesmo do desktop `PH_FABRICANTE`) |
| `toggle_status` quebrado | Payload `{nunota, status}` | Backend espera `{nunota_class, pendente}` (paridade `classificacao.js`) |
| `update_descarte_lote` zerando descarte | Payload `{lote, qtd_avaria: total_novo}` | Backend espera `{lote, valor, operacao: 'soma'\|'subtrai'}` (delegado o cálculo do total pro backend) |
| `CODVOLPARC='CX'` em vez de `'KG'` | Mobile mandava `codvol: 'CX'` | Mandar `codvol: 'KG'` (paridade `showItemsModal` desktop que força `item_vol = 'KG'` ao abrir — [classificacao.js:672](../../sankhya_integration/static/sankhya_integration/classificacao.js#L672)) |

#### Validação de paridade Web vs Mobile (Mai/2026 — 2026-05-27)

Comparação TGFITE NUNOTA 113878 (mobile) vs 113879 (web), ambos TGFCAB TOP 26:

**TGFITE — 1 divergência (esperada)**: `CODAGREGACAO` diferente porque cada classificação foi de um lote diferente do mesmo pedido (S01 vs S02). **Zero divergências de bugs.**

**Campos com paridade 100% confirmada**: `CODVOL='KG'`, `CODVOLPARC='KG'`, `RESERVA='N'`, `ATUALESTOQUE=-1`, `USOPROD='V'`, `PESO=20`, `QTDFIXADA=20`, `PENDENTE='N'`, `GERAPRODUCAO='N'`, `AD_NUMPEDIDOORIG`, `FATURAR='S'`, `CODLOCALORIG=101`.

**Campos que dependem de cadastro Sankhya** (não bug): `GTINNFE` e `GTINTRIBNFE` vêm de trigger nativa `TRG_INC_UPD_TGFITE_PRODNFE` que lê `TGFPRO.REFERENCIA` + `TGFPRO.TIPGTINNFE`. Produto sem EAN13 cadastrado → campos NULL em ambos web e mobile.

### Cache atual da Classificação Mobile

CSS `?v=7` · JS `?v=17`

---

## Frontend

- **Template:** `classificacao.html`
- **CSS:** `classificacao.css`
- **JS:** `classificacao.js`
- **Container interno:** `.classificacao-grid` (flex, aside 320px + rightcol)

### CSS específico

- `.appbar { justify-content: space-between; margin-bottom }`
- Override `.main-layout { gap: 12px; padding-bottom: 40px }`
- `.ia-selectable-table`, `.switch .slider`, `.resumo-item`, `#produtosClassificadosWatermark`

---

## Pendências

- **Cobertura de testes dedicada** — hoje sem `test_views_classificacao.py`. Pendência roadmap #4.
