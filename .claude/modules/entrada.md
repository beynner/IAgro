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

## Frontend

- **Template:** `entrada.html`
- **CSS:** `entrada.css` (também carregado globalmente pelo `base.html` por legado — ver gotchas)
- **JS:** `entrada.js`
- **Container interno:** `.entrada-grid` (flex, aside 320px + rightcol)

---

## Testes

- `test_views_entrada.py` — entrada, health, conversor de tipos
