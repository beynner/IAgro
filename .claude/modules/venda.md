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

### Integração com módulo Importação por e-mail (Mai/2026)

- **Botão `btnImportarPedidos`** na toolbar (ícone download/inbox SVG, ao lado da impressora) — IDs da toolbar agora: `btnNewVenda`, `btnDeleteVenda`, `btnPrintVenda`, `btnImportarPedidos`
- Click → `window.open('/sankhya/venda/email-importar/', '_blank')` — abre **aba nova**, NÃO popup nem modal
- Polling no parent: `setInterval(() => { if (aba.closed) { clearInterval(...); carregarVendas(false); } }, 500)` — quando o operador fecha a aba de Importação, a lista de Vendas recarrega automaticamente, refletindo pedidos confirmados em TGFCAB durante a sessão
- **Fallback**: se o navegador bloquear `window.open` (popup blocker), faz `window.location.href = url` — navega na mesma aba sem perder funcionalidade
- O destino também é acessível via card `📥 Importação` no `home.html` (depois do Rastreio). Mesmo URL, diferente entry point — botão na toolbar de Vendas tem o callback de recarga ao fechar; card no home é navegação tradicional na mesma aba
- **Histórico de decisões UX (sessão Mai/2026, 2026-05-08)**: testamos modal full-screen + iframe + click-fora-não-fecha (precisou `@xframe_options_sameorigin` na view e workaround de `style.display='flex'` por causa do `.modal-overlay { display: none }` global do `entrada.css`). Operador preferiu o fluxo de aba nova — modal foi revertido. Card de home foi adicionado pra dar 2 entry points

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

## Rastreabilidade via `AD_NUMPEDIDOORIG` (campo customizado) — Mai/2026

Decisão arquitetural alinhada com Entrada/Classificação/Comercial: **todo pedido criado pela IAgro popula `AD_NUMPEDIDOORIG = NUNOTA próprio`** (auto-referência). Quando o IAgro for a fonte do faturamento (futuro), o UPDATE in-place de `CODTIPOPER 34 → 35/37` preserva naturalmente o valor — pedido e nota terminam com mesma origem.

### Status atual (Mai/2026)

- **Função IAgro popula corretamente**: [`inserir_cabecalho_nota_banco`](../../sankhya_integration/services/oracle_conn.py) tem default `int(dados.get('AD_NUMPEDIDOORIG') or novo_nunota)` (linha ~597). Tanto a página Vendas (`api_criar_cabecalho_venda`) quanto a Importação por e-mail (`api_email_confirmar`) passam pelo mesmo caminho e herdam o default
- **MAS, em produção, 298/298 pedidos TOP 34 dos últimos 30 dias estão com `AD_NUMPEDIDOORIG = NULL`** — confirmado via SQL em 2026-05-09. Razão: praticamente todos os pedidos reais hoje vêm do Sankhya direto (operadores ainda usam o ERP nativo para criar pedidos), e Sankhya não conhece o campo customizado
- **Quando IAgro for adoção real para criação de pedidos**, esses novos passarão a ter o campo populado automaticamente. Pra dados existentes, ficar via TGFVAR (ver schema.md §5.5) ou via job de migração futuro

### Por que vale popular mesmo assim

1. **Prepara o terreno** para quando o IAgro tomar o controle do faturamento
2. **Cobertura natural** de qualquer pedido novo criado pela página Vendas ou Importação por e-mail
3. **Sem custo adicional** — código já existe, só preserva a convenção

### O que NÃO faz parte desta estratégia

- **Não usa AD_NUMPEDIDOORIG para implementar a feature de "vincular lote em nota faturada"**. Essa feature (Fase 2, planejada Mai/2026 mas ainda não implementada) usa **TGFVAR** porque é a única fonte que cobre 100% dos dados existentes (~185k pares pedido↔nota), inclusive os criados via Sankhya
- **Não cria trigger no Sankhya** para copiar AD_NUMPEDIDOORIG na geração de nota faturada via Sankhya — fora do escopo IAgro

---

## Avaria (TOP 30) — Mai/2026

Registro de perda interna de estoque, rastreado por lote.

### Fluxo

1. Operador na tela Vendas clica `⚠ Avaria` na toolbar
2. Modal `#avariaModal` abre:
   - Typeahead de lote (busca por CODAGREGACAO ou DESCRPROD via endpoint do Rastreio com `q_lote_prod`)
   - Auto-preenche produto + fornecedor + saldo disponível ao selecionar
   - Operador escolhe cliente, qtd, vol (default KG), NUMNOTA da venda original (campo livre), motivo
3. Frontend valida cliente: lote selecionado, qtd > 0, saldo suficiente (cliente)
4. POST `/sankhya/venda/api/avaria/criar/` → `criar_avaria_top30_banco`
5. Backend: valida saldo na view, cria TGFCAB TOP 30 (CODNAT=20010200, TIPMOV='V' via TGFTOP) + TGFITE com CODAGREGACAO obrigatório + STATUSNOTA='L' direto
6. View `ANDRE_IAGRO_SALDO_LOTE` desconta automaticamente via `baixas_avaria`

### Decisões-chave

- **STATUSNOTA='L' direto** — avaria não tem TGFVAR, não tem financeiro reverso, não tem NFe. Sankhya nativo também só registra a perda
- **CODAGREGACAO obrigatório no item** — diferente do Sankhya nativo (que deixa NULL), IAgro registra o lote pra rastreabilidade ponta-a-ponta. Aparece no Histórico do Lote
- **NUMNOTA livre** — operador anota número da venda original como referência humana, sem vínculo formal de TGFVAR
- **Auto-cura `AD_NUMPEDIDOORIG` por CODAGREGACAO** funciona automaticamente em `inserir_item_nota_banco` — o cabeçalho TOP 30 herda a raiz (TOP 11) do lote sem código adicional

---

## Devolução (TOP 36) — Mai/2026

Cliente devolveu mercadoria de uma TOP 35 (NFe) ou TOP 37 (s/ NFe) faturada.

### Fluxo

1. Operador na tela Vendas clica `📤 Devolução` na toolbar
2. Modal `#devolucaoModal` abre:
   - Input NUNOTA da nota origem + botão `Carregar Itens`
   - GET `/sankhya/venda/api/devolucao/preparar/?nunota=X` → `consultar_nota_para_devolucao`
   - Cabeçalho da nota exibido (cliente, data, total, NUMNOTA)
   - Tabela de itens com colunas: checkbox · produto · lote · qtd vendida · já devolvido · saldo devolvível · qtd a devolver
   - Marca checkbox → pré-preenche qtd a devolver com saldo máximo
3. Frontend valida cliente: pelo menos 1 item marcado, qtd > 0 e ≤ saldo devolvível
4. POST `/sankhya/venda/api/devolucao/criar/` → `criar_devolucao_top36_banco`
5. Backend:
   - Recarrega contexto da nota origem
   - Valida cada item: `qtd_devolver + ja_devolvido <= qtd_vendida` via TGFVAR
   - Cria TGFCAB TOP 36 STATUSNOTA='A' (em aberto) + TGFITE par-a-par preservando CODAGREGACAO
   - **INSERT em TGFVAR** (NUNOTA, SEQUENCIA, NUNOTAORIG=nota_origem, SEQUENCIAORIG, QTDATENDIDA, STATUSNOTA='A')
6. Operador entra no Sankhya, abre a devolução criada, clica `Confirmar` → STATUSNOTA vira 'L' + dispara financeiro reverso + abre NFe devolução
7. Quando STATUSNOTA='L', view `ANDRE_IAGRO_SALDO_LOTE` **soma** a qtd ao saldo do lote correspondente (perna F + soma em A/B)

### Decisões-chave

- **STATUSNOTA='A' (em aberto), não 'L'** — Sankhya cuida do financeiro/NFe na confirmação. IAgro não duplica o trabalho do ERP
- **TGFVAR populada no INSERT** — descoberto em investigação Mai/2026: Sankhya nativo popula TGFVAR JÁ no INSERT da TOP 36 (12 de 13 STATUSNOTA='A' têm TGFVAR par). Replicar fielmente é o caminho que o ERP espera
- **AD_NUMPEDIDOORIG=NULL na TOP 36** — Sankhya nativo deixa NULL em 100% das devoluções. Vínculo real vive em TGFVAR. IAgro mantém o mesmo padrão (a função `inserir_cabecalho_nota_banco` substitui NULL por NUNOTA próprio, gerando discrepância cosmética com Sankhya — inocua na operação, documentada como pendência menor)
- **CODAGREGACAO preservado** dos itens da nota origem — diferente do Sankhya nativo, que geralmente perde o vínculo de lote. IAgro pre­serva pra rastreabilidade
- **Trava anti-devolução-excessiva** via `consultar_devolucoes_anteriores_de_nota` que soma TGFVAR.QTDATENDIDA por SEQUENCIAORIG (inclui STATUSNOTA='A' e 'L' — devolução em aberto também bloqueia novo cliente)

### Gotcha refinado

O gotcha "TGFVAR é populada via trigger Sankhya — NÃO escrever direto" foi escrito no contexto do Rastreio Fase 2 (criar vínculo de lote artificial sem criar devolução). Aqui estamos criando uma **devolução real**, exatamente como o Sankhya nativo cria. **Não é trapaça, é replicação fiel**. A cascata em TGMTRA disparada por `TRG_INC_TGFVAR` acontece igual em qualquer cenário — o ERP foi feito pra esse caminho.

---

## Histórico do Lote — Mai/2026

Tela de consulta: "pegue um lote e veja tudo que aconteceu com ele".

### Fluxo

1. Operador clica `🔍 Histórico` na toolbar
2. Modal `#historicoLoteModal` abre com input de CODAGREGACAO
3. GET `/sankhya/venda/api/lote/historico/?lote=X` → `obter_historico_lote`
4. Backend: lê TGFITE+TGFCAB+TGFPAR de um CODAGREGACAO, ordenado por DTNEG ASC
5. Frontend renderiza timeline vertical com nós coloridos por TOP:
   - Verde agro = TOP 11/13/26 (entradas)
   - Verde NFe = TOP 35/37 (vendas)
   - Vermelho = TOP 36 (devolução)
   - Cinza/escuro = TOP 30 (avaria)
6. Cada nó mostra: TOP+nome, NUNOTA, NUMNOTA, parceiro, produto, qtd, valor, status

### Dados consultados

- Inclui só STATUSNOTA <> 'E' (descarta notas excluídas)
- Não consulta TGFVAR — usa apenas CODAGREGACAO em TGFITE pra montar a timeline
- Função pública `obter_historico_lote` é leitura pura, sem efeitos colaterais

---

## Pendências

- **Vínculo lote ↔ item dentro do modal** — hoje fica para o Rastreio. Avaliação: manter assim (recomendação) ou adicionar typeahead com saldo de lote.
- **Emissão real de NFe** — decisão de negócio pendente.
- **Typeahead de Lote** — refino apenas cosmético aplicado. Typeahead real exigiria nova função em `oracle_conn.py` (`SELECT DISTINCT CODAGREGACAO FROM TGFITE WHERE...`); bloqueado pela regra crítica #4 até decisão de negócio. Alternativa atual: input livre com `LIKE` e debounce 500ms.
- **Migração retroativa de `AD_NUMPEDIDOORIG`** (futuro) — script que lê TGFVAR e popula `AD_NUMPEDIDOORIG` em pedidos/notas existentes, uniformizando dados antigos com a convenção que IAgro usa.

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
