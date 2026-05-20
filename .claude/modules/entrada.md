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

## Avaria do fornecedor em item NÃO-classificável (Mai/2026 — 2026-05-19)

Itens com `GERAPRODUCAO <> 'S'` (in natura direto pra TOP 13, sem passar pela Classificação) agora têm onde registrar descarte do fornecedor — antes não tinha tela e o histórico era perdido (operador só conseguia reduzir QTDNEG no vale Comercial).

### Coluna "Avaria forn." no modal de itens

Tabela "Produtos inseridos" do `cabItemsCard` ganhou coluna entre `Total kg` e ações:

| `GERAPRODUCAO` | Comportamento da célula |
|---|---|
| `S` (classificável) | Mostra `—` cinza. Avaria continua sendo gerenciada na Classificação (campo `AD_QTDAVARIA` via `atualizar_descarte_origem`). |
| `N` (não-classificável) | Input numérico amarelado + botão 💾. Operador digita kg de avaria, click salva. |

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
- Invalida cache Rastreio (`invalidar_cache_rastreio()`) pra perna E refletir na próxima leitura
- Audit `AVARIA_FORNECEDOR` em `AD_AUDITORIA_GERAL` (snapshot antes/depois)

### Impacto no saldo

Perna E (`AVARIA_FORNECEDOR`) da view `ANDRE_IAGRO_SALDO_LOTE` reflete o novo valor. **Saldo vendável NÃO muda** — perna E é informativa, fora da fórmula de `QTD_DISPONIVEL`. Modal Faturamento do Comercial usa essa info pra orientar precificação/cobrança (ver [`comercial.md`](comercial.md) → "Avaria do fornecedor no modal Faturamento").

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
