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
- Swipe-to-back (gesto touch direita) na tela 2
- Bottom nav (Lotes / Buscar / Filtros / Mais)
- Search client-side filtra por produto/parceiro/lote
- Hambúrguer abre sidebar IAgro global
- Toast verde/vermelho via `IAgro.showToast`

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
