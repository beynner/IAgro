# Módulo Entrada (TOP 11)

Recebimento e conferência de notas de compra com pesagem e controle de itens.

---

## Escopo

- Listar notas de compra (TOP 11) recebidas
- Conferir itens linha a linha
- Registrar pesagem (`AD_PESO`) e quantidade conferida (`AD_QTDCONFERIDA`)
- Salvar item parcial e finalizar item
- Geração automática de lote no formato `NUNOTAS{SEQ}D{YYMMDD}` no campo `CODAGREGACAO` da TGFITE

---

## URL e acesso

| Rota | Acesso |
|---|---|
| `/sankhya/compras/portal/` | Grupos `1`, `6`, `8` |

---

## Views principais (`views.py`)

| View | Propósito |
|---|---|
| `view_portal_entradas` | Página HTML do portal |
| `api_listar_itens_nota` | Lista itens de uma nota |
| `item_save` | Salva item (UPDATE de peso/qtd) |
| `item_finalize` | Finaliza item (status conferido) |

---

## Funções de `oracle_conn.py` usadas

- `inserir_cabecalho_nota_banco` (com auto-cura de `AD_NUMPEDIDOORIG`)
- `inserir_item_nota_banco(..., gerar_lote_auto=True)` — gera lote automaticamente
- `atualizar_cabecalho_nota_banco` (com auto-cura)
- `atualizar_item_nota_banco`
- `recalcular_totais_nota_banco`
- `listar_itens_por_nota` — retorno por índice (ver schema.md §9)

---

## Regras específicas

- **Lote auto-gerado** no formato `NUNOTAS{SEQ}D{YYMMDD}` — diferente da Venda, que aceita lote livre ou NULL.
- Auto-cura de `AD_NUMPEDIDOORIG` em `atualizar_cabecalho_nota_banco` e `atualizar_item_nota_banco` é **específica deste módulo** — não reutilizar na Venda nem no Rastreio.
- Conferência atualiza `AD_QTDCONFERIDA` e `AD_PESO` na TGFITE.

---

## Avaria do fornecedor em item NÃO-classificável (Mai/2026 — 2026-05-19, refinado 2026-05-20)

Itens com `GERAPRODUCAO <> 'S'` (in natura direto pra TOP 13, sem passar pela Classificação) agora têm onde registrar descarte do fornecedor — antes não tinha tela e o histórico era perdido (operador só conseguia reduzir QTDNEG no vale Comercial).

### Coluna "Avaria forn." no modal de itens

Tabela "Produtos inseridos" do `cabItemsCard` ganhou coluna entre `Total kg` e ações:

| `GERAPRODUCAO` | Comportamento da célula |
|---|---|
| `S` (classificável) | Mostra `—` cinza. Avaria continua sendo gerenciada na Classificação (campo `AD_QTDAVARIA` via `atualizar_descarte_origem`) |
| `N` ou NULL (não-classificável) | Input numérico amarelado **com auto-save no `blur`/Enter** — sem botão dedicado. Feedback: borda âmbar durante salvamento, verde 1.5s no sucesso, vermelha em falha |

Inputs `<input type="number">` sem spinners (CSS hide). Largura 95px pra exibir números com casa decimal sem cortar.

### Backend — endpoint dedicado (escapa da trava de edição)

A trava de TOP 13/26 (em `api_salvar_item_nota` de [views.py](../../sankhya_integration/views.py)) bloqueia QUALQUER UPDATE em item da TOP 11 quando já existe TOP 13 ou 26 com o lote. Mas avaria pode ser registrada **depois** do vale — operador descobre durante o faturamento. Por isso o caminho foge da trava:

| Endpoint | Função service | Operação |
|---|---|---|
| `GET  /sankhya/compras/api/avarias-fornecedor/?nunota=N` | `consultar_avarias_fornecedor_da_nota(nunota)` | Retorna `{sequencia: AD_QTDAVARIA}` da nota — alimenta a coluna no carregar |
| `POST /sankhya/compras/api/avaria-fornecedor/` | `atualizar_avaria_fornecedor_naoclass(nunota, sequencia, qtd, codusu, nomeusu)` | UPDATE `TGFITE.AD_QTDAVARIA` com filtro `GERAPRODUCAO <> 'S'` |

### Validações no service

- `qtd >= 0`
- `qtd <= QTDNEG` do item
- Filtra `c.CODTIPOPER = 11` (só TOP 11)
- Filtra `GERAPRODUCAO <> 'S'` (defesa em profundidade contra UPDATE em item classificável)
- **Trava B10** (Mai/2026 — 2026-05-20): se vale TOP 13 do pedido tem TGFFIN gerado, REJEITA com mensagem humanizada `"Vale já faturado pra essa entrada (NUFIN=X). Desfature antes de alterar a avaria do fornecedor."` — evita inconsistência com TGFCAB TOP 30 gerada no faturamento
- Invalida cache Rastreio (`invalidar_cache_rastreio()`) pra perna E refletir na próxima leitura
- Audit `AVARIA_FORNECEDOR` em `AD_AUDITORIA_GERAL` (snapshot antes/depois)

### Impacto no saldo

Perna E (`AVARIA_FORNECEDOR`) da view `ANDRE_IAGRO_SALDO_LOTE` reflete o novo valor. **Saldo vendável NÃO muda diretamente pela perna E** — ela é informativa, fora da fórmula de `QTD_DISPONIVEL`.

O desconto efetivo no estoque acontece via Comercial (modal Faturamento):

- **📌 Absorver** → backend gera TGFCAB TOP 30 (avaria interna) ao FATURAR, que desconta via **perna D** da view (`AVARIA_INTERNA`)
- **📉 Descontar** → vale TOP 13 fica com qtd LÍQUIDA (Comercial cobra fornecedor por fora; estoque coerente pela qtd reduzida no próprio vale)

Detalhes em [`comercial.md`](comercial.md) → "Toggle Descontar/Absorver com avaria interna automática".

### Espelhamento (Mai/2026, intocado)

A Classificação continua filtrando `GERAPRODUCAO='S'` em `atualizar_descarte_origem`. Sem conflito — cada módulo gerencia seu próprio universo de produtos.

---

## Frontend

- **Template:** `entrada.html`
- **CSS:** `entrada.css` (também carregado globalmente pelo `base.html` por legado — ver gotchas)
- **JS:** `entrada.js`
- **Container interno:** `.entrada-grid` (flex, aside 320px + rightcol)

---

## Testes

- `test_views_entrada.py` — entrada, health, conversor de tipos
