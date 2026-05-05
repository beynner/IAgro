# Módulo Venda (TOP 34 / 35 / 37)

Criação, edição, exclusão, faturamento e listagem de pedidos de venda.

---

## Escopo

- Criar pedido (TOP 34)
- Editar cabeçalho (TOP 34 não-faturado)
- Adicionar / editar / remover itens
- Excluir pedido completo (TOP 34)
- Faturar pedido: TOP 34 → TOP 35 (com NFe) ou TOP 37 (sem NFe)
- Listagem paginada com filtros
- **Não dispara emissão real de NFe** — Sankhya cuida disso

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/venda/portal/` | GET | Página HTML |
| `/sankhya/venda/api/cabecalho/` | POST | Criar cabeçalho TOP 34 |
| `/sankhya/venda/api/cabecalho/editar/` | POST | Atualizar cabeçalho (só TOP 34 não-faturado) |
| `/sankhya/venda/api/cabecalho/obter/` | GET | Obter cabeçalho com JOINs (TSIEMP, TGFPAR, TGFTPV) |
| `/sankhya/venda/api/item/` | POST | Adicionar item |
| `/sankhya/venda/api/item/editar/` | POST | Editar item (qtd, preço, lote, volume) |
| `/sankhya/venda/api/item/remover/` | POST | Remover item; deleta cabeçalho se foi o último |
| `/sankhya/venda/api/excluir/` | POST | Excluir pedido completo |
| `/sankhya/venda/api/faturar/` | POST | Faturar TOP 34 → 35/37 |
| `/sankhya/empresa/search/` | GET | Typeahead TSIEMP |
| `/sankhya/tipvenda/search/` | GET | Typeahead TGFTPV |
| `/sankhya/natureza/search/` | GET | Typeahead CODNAT |

**Acesso:** Grupos `1`, `6`, `10` (decorator `@exige_grupo('venda')`).

---

## Views principais (`views.py`)

| View | Função |
|---|---|
| `view_portal_vendas` | Página HTML |
| `api_listar_vendas` | Listagem paginada |
| `api_criar_cabecalho_venda` | INSERT TGFCAB |
| `api_atualizar_cabecalho_venda` | UPDATE TGFCAB (trava: só TOP 34) |
| `api_obter_cabecalho_pedido` | SELECT com JOINs |
| `api_salvar_item_venda` | INSERT TGFITE |
| `api_atualizar_item_venda` | UPDATE TGFITE (trava: só TOP 34 não-faturado) |
| `api_remover_item_venda` | DELETE TGFITE + recalculo |
| `api_excluir_pedido_venda` | DELETE pedido completo |
| `api_faturar_pedido_venda` | TOP 34 → 35/37 |

---

## Funções de `oracle_conn.py` usadas

| Função | Diferencial |
|---|---|
| `consultar_empresas_oracle` | Typeahead TSIEMP |
| `consultar_tipos_negociacao_oracle` | Typeahead TGFTPV |
| `consultar_cabecalho_venda_oracle` | SELECT com JOINs |
| `inserir_cabecalho_nota_banco` | Aceita `CODTIPVENDA` + grava `DHTIPVENDA` (exigência do trigger) |
| `atualizar_cabecalho_venda_banco` | **Dedicada** — sem auto-cura de `AD_NUMPEDIDOORIG` |
| `inserir_item_nota_banco(..., gerar_lote_auto=False)` | **Lote NULL** (decisão de negócio: lote nasce na TOP 11; Venda só vincula no Rastreio) |
| `atualizar_item_nota_banco` | UPDATE de item (mas Venda não usa `CODAGREGACAO` aqui — fica para o Rastreio) |
| `recalcular_totais_nota_banco` | Recalcula `VLRNOTA` e `QTDVOL`. **Deleta cabeçalho se ficar sem itens** |
| `faturar_pedido_venda_banco(nunota, nova_top, codusu_logado)` | **Lock pessimista** + validação de itens com lote + geração `NUMNOTA` por empresa + aplicação `CODNAT_POR_TOP` |

---

## Workaround obrigatório `DPY-1001`

`inserir_cabecalho_nota_banco` tem bug que mascara erro real com `DPY-1001`. **Todas as views de escrita da Venda** usam este padrão:

```python
with obter_conexao_oracle() as conn:
    resultado = funcao_do_service(..., conexao_existente=conn)
    conn.commit()
```

Detalhes em `gotchas.md`.

---

## Faturamento — `faturar_pedido_venda_banco`

Operação atômica com `SELECT FOR UPDATE` na TGFCAB. Validações:

1. Pedido existe
2. É TOP 34
3. Não está faturado/excluído
4. Tem itens
5. **Todos os itens com `CODAGREGACAO` preenchido** (validação de lote vinculado)

Atualiza:
- `CODTIPOPER` → 35 ou 37
- `CODNAT` via `CODNAT_POR_TOP[nova_top]`
- `STATUSNOTA` → `'L'`
- `NUMNOTA` → próximo da empresa (`MAX(NUMNOTA) + 1`)
- Opcionalmente `DTFATUR` / `DTMOV` / `CODUSU` se as colunas existirem

**NÃO dispara emissão de NFe.** Decisão consciente: TOP 35 fica visível no painel do Sankhya para emissão lá.

---

## Tabela `CODNAT_POR_TOP`

```python
CODNAT_POR_TOP = {
    34: 10010100,   # Pedido de Venda
    35: 10010100,   # Venda com NFe
    37: 10010200,   # Venda sem NFe
}
```

**Fonte única da verdade.** Não duplicar em outros pontos.

---

## Frontend — fluxo

### Novo pedido

1. Botão `btnNewVenda` na toolbar
2. `cabCard` desliza dock-à-esquerda (padrão visual da Entrada)
3. Campos: Empresa, Cliente, Tipo de Negociação, Data, Observação
4. Natureza (10010100 default) e C. Resultado (10100) são labels carregados do banco
5. Ao salvar: `cabCard` trava, `cabItemsCard` desliza da direita com formulário de item
6. Contador `itensInseridosCount` monitora se pedido tem itens
7. **Fechar sem adicionar itens** dispara **auto-delete do cabeçalho órfão**

### Editar pedido existente

- **Duplo clique numa linha** (apenas TOP 34) abre os dois modais em modo edição
- Botão **"Editar Cabeçalho"** destrava cabCard e fecha modal de itens
- Cancelar restaura valores via fetch
- Botão **"Excluir"** da toolbar fica desabilitado até linha selecionada (click simples)

### Editar/remover item

- Botão lápis por linha → popula form de edição, troca botão "+" por "salvar" verde
- Botão lixeira por linha → modal `IAgro.confirmarAcao({tipo: 'perigo'})`
- Se foi o **último item**, deleta o cabeçalho automaticamente (via `recalcular_totais_nota_banco`)

### UX do cabCard

- `Enter` salva; `Esc` cancela (ignorados em `<textarea>` e dropdown aberto)
- Campos obrigatórios ausentes recebem borda vermelha (`#cabCard .ia-field-invalid`) + toast consolidado
- Inputs fazem `select()` ao receber foco (exceto `hidden`, `disabled`, `<textarea>`)
- `#cabCard.modal-card.small` largura `380px` (apenas no módulo Venda, via `venda.css`)

### UX para não-tech (Fase 2)

- **Resumo do pedido sempre visível** no header do modal: `Cliente · Tipo Negociação · R$ Total · (N itens) · [PENDENTE DE LOTE]`
- **Validação de duplicação preventiva:** ao tentar adicionar produto+lote já presente, modal pergunta "Somar quantidades?" ou "Inserir como novo item?"
- **Empty state amigável** quando lista vazia: ilustração + `[Limpar filtros]` `[+ Novo pedido]`
- **CODNAT como dropdown** (não label readonly) — permite revenda

### Faturamento

- Botão **"Faturar Pedido"** ao lado de "Editar Cabeçalho"
- Modal `#faturarModal` com escolha **TOP 35 (com NFe)** vs **TOP 37 (sem NFe)**
- Validação cliente: bloqueia se há item sem lote (mostra aviso amarelo com `count`)
- Linha de TOP 35/37 fica esmaecida (`.pedido-faturado`)
- Badge `top-badge` mostra `34` / `35-NFe` / `37-S/NFe` com cores diferentes

---

## Frontend — arquivos

- **Templates:** `venda.html` + `venda_modais.html`
- **CSS:** `venda.css`
- **JS:** `venda.js`
- **Container interno:** `.venda-grid` (flex, 3 colunas: filtros 220px + central + itens)

### Layout dos filtros (Abr/2026)

Card lateral `#cardFiltros` (220px) contém, na ordem:

1. `<header>` "Filtros"
2. `<form id="filtersForm">` com todos os campos (Período + setas, TOP, Empresa typeahead, Parceiro typeahead, Produto typeahead, Pedido/NF, Lote)
3. `#filtrosAtivos` → `#filtrosAtivosChips` (chips de filtros ativos, com botão × por chip)
4. `.filters-footer` com botões `Atualizar` (`#btnUpdate`) / `Limpar` (`#btnClear`)

Tentativa anterior de mover os filtros para o header inline do card de Pedidos foi revertida — ver decisão no `roadmap.md`.

### Persistência de filtros

`venda.js` salva todos os campos do form em `localStorage` na chave **`iagro:venda:filtros:v1`** a cada `carregarVendas(false)`. Restaura no boot; se as datas vierem ausentes, cai em `inicializarDatas()` (hoje). `btnClear` apaga o storage além de zerar os campos. Para adicionar um campo novo, atualizar `CAMPOS_FILTRO_PERSISTIDOS` no topo do `venda.js`. **Mudança de formato → bumpar para `v2`** (ver gotchas).

### CSS específico

- `:root` com 7 variáveis aliasadas
- Mantidos como específicos: `--cor-fundo-cabecalho-tabela`, `--cor-texto-primario-escuro`, `--cor-texto-secundario-cinza`, `--cor-borda-dropdown-ativa`
- Override `.main-layout { gap: 12px; padding: 10px 20px }`

---

## Pendências

- **Vínculo lote ↔ item dentro do modal** — hoje fica para o Rastreio. Avaliação: manter assim (recomendação) ou adicionar typeahead com saldo de lote.
- **Emissão real de NFe** — decisão de negócio pendente.
- **Typeahead de Lote** — refino apenas cosmético aplicado. Typeahead real exigiria nova função em `oracle_conn.py` (`SELECT DISTINCT CODAGREGACAO FROM TGFITE WHERE...`); bloqueado pela regra crítica #4 até decisão de negócio. Alternativa atual: input livre com `LIKE` e debounce 500ms.

---

## Testes

`test_views_venda.py` — **90 testes** distribuídos em:

| Classe | Testes |
|---|---|
| `PortalVendasAcessoTest` | 6 |
| `ApiListarVendasTest` | 9 |
| `CriarCabecalhoVendaTest` | 11 |
| `SalvarItemVendaTest` | 12 |
| `ExcluirPedidoVendaTest` | 7 |
| `ObterCabecalhoPedidoTest` | 7 |
| `AtualizarCabecalhoVendaTest` | 12 |
| `AtualizarItemVendaTest` | 8 |
| `RemoverItemVendaTest` | 5 |
| `FaturarPedidoVendaTest` | 8 |
| `FaturarPedidoServiceTest` | 7 |
| `HumanizarErroOracleHelperTest` | 6 |
