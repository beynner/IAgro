# Módulo Controle de Combustível (TOP 10 entrada / TOP 53 requisição interna)

Controle integral de estoque de combustível: compra (TOP 10 + TGFFIN em aberto), requisição interna (TOP 53 — frota/maquinário/freteiro) e abastecimento externo (TOP 53 + TGFFIN contra posto, **não desconta tanque**). Visual de tanques SVG, lista de veículos com lightbox de foto, listagem unificada de movimentações com Total km/Média de consumo, CRUD completo (criar/editar/excluir) de entrada e requisição, relatório de consumo por veículo.

**Status (Mai/2026, 2026-05-13)**: ✅ ponta-a-ponta funcional em produção. Falta apenas atribuir usuários ao grupo TSIGRU=11 (IAGRO_FROTA) e cadastrar veículos faltantes em TGFVEI.

---

## 📱 Combustível Mobile — redesign app-like + UI v2 unificada (Mai/2026 — 2026-05-27/28)

Implementação completa do **fluxo mobile** + **refator da UI desktop** numa única arquitetura coerente. Aplicado **a desktop e mobile simultaneamente**.

### Mobile app-like (Mai/2026 — 2026-05-27)

Mesma arquitetura dos outros módulos (Entrada/Classificação/Rastreio). HTML único com 2 containers paralelos (`.combustivel-desktop` + `.combustivel-mobile`), escopados por `body[data-active-module="combustivel"]` em viewport ≤900px. Desktop preservado 100% intacto.

**Componentes mobile**:
- **3 telas** (`m-screen`): `lista` (com 3 contextos: Estoque / Movs / Veículos) · `detalheVeiculo` (foto + 7 cards Diesel/ARLA + lista filtrada) · `fotoLightbox` (sheet fullscreen)
- **Bottom nav 5 itens**: Estoque · Movs · Veículos · Filtros · Mais — toggle de contexto **vive apenas no bottom nav** (sem toggle de topo redundante)
- **Bottom sheets**: `nova-req` (único pra todos os tipos) · `filtros` · `excluir` · `mais`
- **Tanques SVG** reutilizam funções desktop (`renderTanqueCilindricoSVG` / `renderTanqueQuadradoSVG`) — empilhados verticalmente em mobile
- **Lista de veículos** 1 coluna com foto thumb 60×44 + swipe-to-back nas telas internas
- **Cards de movimentação** 3 linhas (parc · prod+qtd · vlr+consumo) com swipe-to-edit + swipe-to-delete
- **Cálculo Total km + Média Diesel/ARLA client-side** reusado (`_calcularConsumoMov`)

**Persistência**: localStorage `iagro:combustivel:prefs:v1` guarda só `veiculosFiltro` (Frota/Maquinário — herdado do desktop).

### UI v2 — Modal único com 3 pills (Mai/2026 — 2026-05-28)

**Antes** havia 2 botões na toolbar (`Entrada` verde claro + `Requisição` verde Agromil), cada um abrindo modal separado:
- `modalNovaEntrada` (form de compra)
- `modalNovaReq` com 2 pills (Interno / Posto Externo)

**Agora**: 1 botão único **`+`** abre **modal único** com **3 pills**:

| Pill | Cor | Valor backend | Bloco visível |
|---|---|---|---|
| **Entrada** | azul info `#2563eb` | `ENTRADA` (frontend só) | `reqEntradaWrap` — form de compra (Empresa, Fornecedor, NF, Série, Tipo Negociação, DTVENC auto, multi-itens, Histórico, Observação) |
| **Interno** (default) | verde Agromil `#5e7e4a` | `INTERNA_FROTA` | `reqRequisicaoWrap` — form single (Veículo + Combustível + Qtd + Vlr Unit + Hodômetro/Horímetro + Data) |
| **Posto Externo** | âmbar `#c4862e` | `EXTERNA_POSTO` | `reqRequisicaoWrap` com multi-itens + Posto + NUMNOTA + Datas + DTVENC auto |

**Mudanças desktop**:
- `btnNovaEntrada` removido da toolbar
- `btnNovaRequisicao` virou `+` simples (ícone `ph-plus`)
- `modalNovaEntrada` removido (form migrou pra dentro de `modalNovaReq`)
- `cb-pill--entrada` adicionada (CSS azul info + hint azul `#eff6ff`)
- `rotuloTipo()` retorna `'Interna'` em vez de `'Veículo'` (badge verde nos cards de movimentação)

**Mudanças mobile**:
- FAB secundário `m_cb_fabEntrada` removido — sobra só FAB principal `+` (verde)
- Sheet `nova-entrada` removido (form migrou pra dentro de `nova-req`)
- Sheet "Mais" agora tem só 2 atalhos: **Atualizar todos** + **Novo lançamento**
- Toggle de contexto (Estoque/Movs/Veículos) **removido do topo** — vive só no bottom nav
- Badge `m-cb-mov-badge--frota` mostra `'Interna'` (era `'Veículo'`)

**Toggle Maquinário removido** (desktop + mobile, 2026-05-28):
- Pill `INTERNA_MAQUINARIO` removida do form (Interno cobre tudo)
- Filtro `Maquinário` removido do select de tipo da listagem
- Backend continua aceitando `INTERNA_MAQUINARIO` por compat — requisições antigas continuam visíveis com badge "Máquina" (raro, legado)

### Validação por tipo

`validarReq()` e `enviarRequisicao()` (desktop) / `validarReq()` e `enviarRequisicao()` (mobile) **roteam por tipo**:
- `ENTRADA` → delega pra `validarEntrada()` + `enviarEntrada()` (endpoint `URL_ENT_CRIAR` ou `/entrada/<n>/editar/`)
- `INTERNA_FROTA` → fluxo single (endpoint `URL_REQ_CRIAR` ou `/requisicao/<n>/editar/`)
- `EXTERNA_POSTO` → fluxo multi-itens (endpoint `URL_EXT_CRIAR` ou `/requisicao/<n>/editar/`)

**Em modo edição** (entrada ou requisição), as **outras pills ficam disabled + opacity 0.45**. Operador não troca entrada por requisição (estados diferentes no banco).

### Sem botão "Excluir entrada" (2026-05-28)

O botão `Excluir entrada` foi **removido do rodapé** do modal/sheet único (estava só em edição de entrada). Razão: poluição visual + caminho redundante. Exclusão continua disponível via **swipe-to-delete** (lixeira vermelha 🗑) nos cards de movimentação — mesmo fluxo do sheet de exclusão com motivo obrigatório.

### Mensagem unificada

Modal/sheet único usa **uma única área de mensagem**:
- Desktop: `#reqMensagem` (substituiu `#entMensagem`)
- Mobile: `#m_cb_reqMsg` (substituiu `#m_cb_entMsg`)

Botão Salvar também é único: `#btnConfirmarReq` (desktop) / `#m_cb_reqSalvar` (mobile). Label muda conforme tipo + estado de edição.

---

## 💰 TGFFIN automático pra veículos de terceiro (Mai/2026 — 2026-05-26)

Veículos cadastrados em `TGFVEI` com `PROPRIO='N'` (freteiros, cooperados, maquinário alugado) abastecem do nosso tanque interno mas o financeiro ficava sem rastro. Agora o IAgro gera TGFFIN automático contra o parceiro do veículo a cada requisição.

### Detecção automática (operador não escolhe)

| TGFVEI.PROPRIO | TGFITE.PESO/qtd | Comportamento |
|---|---|---|
| `S` (próprio) | normal | **Sem TGFFIN** — comportamento atual preservado |
| `N` (terceiro) | normal | **Gera TGFFIN** auto + AD_REQ.NUFIN_GERADO populado |

Tipos da UI desde 2026-05-28 (revisão pós-Combustível Mobile):
- **Entrada** (compra de combustível, TOP 10)
- **Interno** (`INTERNA_FROTA` no banco — cobre frota própria + maquinário, simplificado em 2026-05-28)
- **Posto Externo** (`EXTERNA_POSTO`)

Backend ainda aceita `INTERNA_MAQUINARIO` e `EXTERNA_FRETE` por compatibilidade (requisições antigas continuam aparecendo na listagem com badge "Máquina"; novas vão tudo como `INTERNA_FROTA`).

### TGFFIN modelo

Quando `PROPRIO='N'`:

| Campo | Valor |
|---|---|
| `CODNAT` | `10040800` (Receita de Abastecimento — DESCRNAT no Sankhya da Agromil) |
| `CODCENCUS` | `10100` (Comercialização — fixo) |
| `CODPARC` | `TGFVEI.CODPARC` (parceiro/freteiro do veículo) |
| `CODVEICULO` | passa o veículo pra rastreio |
| `RECDESP` | `+1` (receita a receber do freteiro) |
| `VLRDESDOB` | `qtd × vlrunit` (preço do TOP 10 mais recente como base) |
| `DTVENC` | `proxima_data_fechamento_decendial(DTNEG)` (ver abaixo) |
| `ORIGEM` | `E` (entrada de nota — exigido pelo trigger TRG_INC_TGFFIN quando NUNOTA preenchido) |
| `STATUSNOTA` | em aberto (`DHBAIXA=NULL, VLRBAIXA=0, CODTIPOPERBAIXA=0`) — operador da finança baixa no Sankhya quando descontar do pagamento |
| `HISTORICO` | `"Abastecimento Diesel S10 / 50 LT (R$6,26) - JFO5H79"` (combustível + qtd + preço + placa) |

### Ciclo decendial pra DTVENC

Helper `proxima_data_fechamento_decendial(dtneg)` em `oracle_conn.py`:

```
dia 1..10  → DTVENC = dia 10 do mês corrente
dia 11..20 → DTVENC = dia 20 do mês corrente
dia 21..fim → DTVENC = último dia do mês (28/29/30/31)
```

Alinha com o ciclo de acerto Agromil↔freteiros (3 fechamentos por mês). Financeiro só precisa ajustar caso a caso quando vier vencimento atípico.

### Trava NURENEG

`TGFFIN.NURENEG IS NOT NULL` ⇒ financeiro foi tocado por operação de renegociação do Sankhya ⇒ IAgro **não mexe mais** (UPDATE/DELETE). Defesa universal aplicada em B2 (editar) e B3 (excluir). Smoke confirmou semântica: 58% dos TGFFIN da Agromil têm NURENEG (positivo ou negativo — ambos indicam "tocado por renegociação"). Helper `consultar_tgffin_renegociado(nufin)` em `oracle_conn.py`.

### Cenários de edição (B2 — idempotência completa)

`editar_requisicao_combustivel_banco` decide automaticamente conforme estado anterior × estado novo:

| Caso | NUFIN_GERADO anterior | PROPRIO veículo atual | NURENEG | Ação |
|---|:-:|:-:|:-:|---|
| **A** | NULL | `N` | — | **CRIA TGFFIN** retroativo (típico: requisições antigas pré-B1) |
| **B** | preenchido | `N` | NULL | **UPDATE TGFFIN** proporcional (valor + DTVENC) |
| **C** | preenchido | `N` | NOT NULL | **BLOQUEIA** ("Financeiro NUFIN=X já foi renegociado…") |
| **D** | preenchido | `S` | NULL | **DELETE TGFFIN** (veículo virou próprio na edição) |
| **E** | preenchido | `S` | NOT NULL | **BLOQUEIA** (mesma msg do C) |
| **F** | NULL | `S` | — | nada (preserva fluxo de próprio) |

Caso típico do operador: requisição antiga (pré-B1) sem TGFFIN ganha um automaticamente ao primeiro UPDATE (caso A).

### Exclusão (B3) — DELETE universal

`excluir_requisicao_combustivel_banco` deleta TGFFIN sempre que `NUFIN_GERADO` preenchido (interno terceiro **ou** externo). Trava NURENEG aplicada antes do DELETE. Sem alteração no fluxo de próprio.

### Cadastro pré-requisito

Antes de usar, operador deve cadastrar em `TGFVEI`:
- `PROPRIO = 'N'`
- `CODPARC` preenchido (freteiro/parceiro)

Sem CODPARC, IAgro bloqueia com erro humanizado `"Veículo X é de terceiro mas não tem parceiro cadastrado em TGFVEI. Atualize o cadastro antes de lançar."`. Vale igual pra Veículos e Maquinário terceiros.

---

## 📊 Média de consumo Diesel vs ARLA separada (Mai/2026 — 2026-05-26)

Antes, o cálculo de km/L misturava todos os abastecimentos do veículo na ordem cronológica. Como ARLA (codprod 1374) não move o veículo, qualquer ARLA entre 2 Diesels distorcia o cálculo (km dividido por qtd de ARLA = número absurdo). Agora tracking **independente por categoria**.

### Categorias

| Categoria | CODPRODs | km/L calculado |
|---|---|---|
| **DIESEL** | 392 (S10), 1373 (S500) | Entre 2 Diesels consecutivos do mesmo veículo |
| **ARLA** | 1374 | Entre 2 ARLAs consecutivos do mesmo veículo |
| **OUTRO** | Gasolina, óleo, etc | Não trackeia (só entra em `total_vlr`) |

### Métricas no resumo do detalhe do veículo

7 cards independentes:

| Diesel (verde) | ARLA (âmbar) |
|---|---|
| Diesel total (LT) | ARLA total (LT) |
| Consumo Diesel (km/L) — destaque | Consumo ARLA (km/L) |
|  | ARLA / Diesel (%) — esperado 3-5% |

Plus: Abastecimentos, Distância (km do Diesel), Valor total no período.

### Tabela Movimentações — célula "Média"

Cada linha mostra a média do abastecimento correspondente:
- **Linha Diesel**: `X km/L` em verde Agromil
- **Linha ARLA**: `X km/L⁽ARLA⁾` em âmbar (visualmente distinta)
- **Linha sem trackeio** (1º abastecimento de cada categoria, ou produtos OUTRO): `—`

### Tests cobrindo 3 cenários

- ARLA no meio NÃO interfere no km/L Diesel
- ARLAs consecutivos calculam km/L próprio (ignora Diesel no meio)
- Cenário só com Diesel: regressão, `total_arla=0`, `arla_pct=0%`, `consumo_medio_kmlt_arla=None`

---

## 🗓 Filtro de datas no card Movimentações (Mai/2026 — 2026-05-26)

Antes: filtro de período ficava no header do detalhe do veículo (select "Últimos N dias"). Agora vive no card Movimentações e serve **tanto** pra listagem geral **quanto** pro detalhe do veículo selecionado.

### Layout

```
[<<]  [Data Inicial]  a  [Data Final]  [>>]
```

- Setas `<<` `>>` recuam/avançam 1 dia em **ambos** os campos
- Ao digitar Data Inicial → replica **sempre** em Data Final (operador ajusta dataFim depois se quiser range maior)
- Default ao abrir: **mês atual** (dia 1 → hoje)

### Helpers JS

| Helper | Função |
|---|---|
| `_hojeIso()` | `YYYY-MM-DD` de hoje |
| `_primeiroDiaMesIso()` | `YYYY-MM-01` do mês corrente |
| `_shiftIso(iso, delta)` | Avança/recua N dias preservando timezone |

Padrão consolidado em [`conventions.md`](../conventions.md) → "Período data inicial → data final + navegação dia-a-dia".

---

## 🔍 Pesquisa de veículos + lista expandida (Mai/2026 — 2026-05-26)

### Header da lista de veículos — 1 linha

```
[🚚 Veículos]  [🔍 Buscar placa, modelo ou parceiro…]  [Frota | Maquinário]
```

Campo de pesquisa filtra (case/acento-insensitive, debounce 200ms):
- `TGFVEI.PLACA`
- `TGFVEI.MARCAMODELO`
- `TGFVEI.ESPECIETIPO`
- `TGFPAR.NOMEPARC` (do parceiro do veículo)

Empty state contextual: `"Nenhum veículo de frota bate com 'XYZ'."` quando filtro ativo.

### Lista expandida até o limite

Antes: `max-height: 320px` fixo cortava a lista na metade do card. Agora flex column com `flex: 1; min-height: 0; overflow: auto` no grid + ajustes nas wrappers pai (`.cb-veiculos-area`, `#veiculosListaWrap`, `.cb-col-estoque > .cb-card-body`). Scroll só no grid, header e tanques ficam fixos.

### Outros ajustes da sessão

- Filtro Status (`<select id="filtroStatus">`) removido do card Movimentações — operador raramente usava.
- Campo VLRUNIT do modal Nova Requisição virou **editável** (era readonly em internos). Auto-fill do último preço TOP 10 continua, mas operador pode sobrescrever.
- Tabela "Produtos inseridos" do modal de Entrada ganhou `<colgroup>` com larguras explícitas — coluna Avaria forn. expandida (input 95→120px), Produto fluida pega o resto.

---

## ⚠ Mudança crítica de TOP (Mai/2026, 2026-05-13)

**TOP 26 → TOP 53** em todo o módulo. TOP 26 é exclusiva da Classificação de mercadoria (hortifrúti); requisições internas e abastecimentos externos do módulo Combustível usam **TOP 53 — REQUISIÇÃO INTERNA** (`TIPMOV='Q'`, ativa).

Lugares afetados (todos atualizados):
- `criar_requisicao_combustivel_banco` / `editar_requisicao_combustivel_banco` / `excluir_requisicao_combustivel_banco`
- `criar_abastecimento_externo_banco`
- `obter_requisicao_combustivel`, `listar_requisicoes_combustivel`
- `listar_movimentacoes_combustivel` (WHERE comum agora `IN (10, 53)`)
- `consultar_consumo_por_veiculo`
- View `ANDRE_IAGRO_SALDO_COMBUSTIVEL` — perna `saidas` filtra `CODTIPOPER = 53`

Referências TOP 26 que **permaneceram intocadas**: módulo de Classificação (linhas com `CODAGREGACAO IS NOT NULL` + grupo hortifrúti).

---

## ⚠ Dois "grupos" distintos — NÃO confundir

| Tabela | Coluna | Código | Nome | Função |
|---|---|---|---|---|
| **TSIGRU** | `CODGRUPO` | **11** | `IAGRO_FROTA` | Grupo de **usuário** — usado por `@exige_grupo('combustivel')` em `decorators.py` |
| **TGFGRU** | `CODGRUPOPROD` | **200400** | `COMBUSTÍVEIS` | Grupo de **produto** — view `ANDRE_IAGRO_SALDO_COMBUSTIVEL` e `consultar_produtos_combustivel` |

Constante Python `CODGRUPOPROD_COMBUSTIVEL = 200400` em `oracle_conn.py`. Hierarquia: `200000 (MEF) → 200400 (COMBUSTÍVEIS)` [analítico, ativo].

---

## Escopo

### Entrada de combustível (compra) — `criar_entrada_combustivel_banco` (B13 refatorada Mai/2026)
- **Multi-itens**: payload aceita `itens=[{codprod, qtd, vlrunit}, ...]`. Compat retroativa: `codprod/qtd/vlrunit` avulsos viram lista de 1 item.
- **NUMNOTA do operador** (NF do fornecedor) — não mais MAX+1 sequencial. Aceita SERIENOTA também.
- INSERT atômico: TGFCAB TOP 10 `STATUSNOTA='L'` + N × TGFITE (`CODAGREGACAO=NULL`) + 1 TGFFIN (soma).
- CODNAT/CODTIPVENDA parametrizáveis (defaults 30070200/11). CODCENCUS obrigatório.
- TGFFIN **sempre nasce em aberto**: `VLRBAIXA=0`, `DHBAIXA=NULL`, `CODTIPOPERBAIXA=0`, `DHTIPOPERBAIXA=01/01/1998`, `ORIGEM='E'` (NUNOTA preenchido exige). Operador baixa pelo Sankhya quando paga (Sankhya cuida da TGFMBC).

### Editar entrada — `editar_entrada_combustivel_banco` (B14, Mai/2026)
- **UPDATE diferencial** dos itens (reusa SEQUENCIAs existentes, INSERT pros adicionais via `inserir_item_nota_banco`, DELETE excedentes). Evita ORA-00001 PK violation.
- UPDATE TGFCAB + UPDATE TGFFIN (preserva campos de baixa zerados).
- Bloqueia se DHBAIXA NOT NULL no TGFFIN ("Financeiro já baixado — estorne no Sankhya").

### Excluir entrada — `excluir_entrada_combustivel_banco` (B15, Mai/2026)
- DELETE físico cascateado: TGFFIN → TGFITE → TGFCAB. Mesma estratégia da B6/B12.
- **Não é mais acessível pela lixeira na linha** (Mai/2026). Botão `🗑 Excluir entrada` fica **dentro do modal de Editar Entrada** (rodapé esquerdo). Razão: evitar deletar nota inteira ao clicar em produto de nota multi-itens.

### Requisição interna (frota/maquinário/freteiro) — `criar_requisicao_combustivel_banco`
- INSERT TGFCAB TOP 53 (`STATUSNOTA=NULL` em aberto) + 1 TGFITE + AD_REQUISICAO_COMBUSTIVEL (sem TGFFIN).
- Single-item (frota = 1 caminhão com 1 combustível).
- Valida saldo via view `ANDRE_IAGRO_SALDO_COMBUSTIVEL`.

### Abastecimento externo (posto) — `criar_abastecimento_externo_banco` (B8 refatorada Mai/2026)
- **Multi-itens** (Mai/2026, 2026-05-13): aceita `itens=[...]` ou `codprod/qtd/vlrunit` avulsos. Caso de uso real: motorista para no posto e abastece caminhão com diesel + Arla numa mesma NF.
- INSERT TGFCAB TOP 53 `STATUSNOTA='L'` + N × TGFITE + AD_REQ (`TIPO='EXTERNA_POSTO'`) + TGFFIN despesa contra posto.
- **Não desconta tanque interno** — view `ANDRE_IAGRO_SALDO_COMBUSTIVEL` filtra `NOT EXISTS (...EXTERNA_POSTO)` na perna saídas.
- TGFFIN sempre em aberto (mesma regra da entrada).

### Editar requisição/externo — `editar_requisicao_combustivel_banco` (B11)
- Caminho **interno single**: UPDATE TGFCAB + UPDATE TGFITE (mesma SEQUENCIA), re-valida saldo "devolvendo" qtd antiga.
- Caminho **externo multi-itens** (Mai/2026): detecta `dados['itens']` + tipo EXTERNA_POSTO → UPDATE diferencial (igual editar entrada). UPDATE TGFFIN com soma.
- Edit/Excluir de EXTERNA_POSTO **funciona mesmo com STATUSNOTA='L'** (externo nasce confirmado; backend valida DHBAIXA).
- Não permite alternar entre Interno↔Externo (semântica diferente; operador exclui e recria).

### Excluir requisição — `excluir_requisicao_combustivel_banco` (B6/B12)
- DELETE físico (TGFCAB+TGFITE+AD_REQ, +TGFFIN se externo). Trigger Sankhya `TRG_UPD_TGFCAB` bloqueia UPDATE STATUSNOTA='E', então é DELETE.
- Bloqueia se TGFFIN baixado (no externo).

### Saldo — view `ANDRE_IAGRO_SALDO_COMBUSTIVEL`
- Fórmula: `GREATEST( Σ TOP 10 (STATUSNOTA<>'E') − Σ TOP 53 (STATUSNOTA<>'E' AND NOT EXTERNA_POSTO), 0 )`, agrupado por CODPROD.
- ⚠ **Não usar `QTD_DISPONIVEL` direto** quando há saldo inicial — calcular em Python (entrada+saldo_inicial−saída) pra não cortar negativo. Ver gotchas.md.

### Listagem unificada de movimentações
- `/api/movimentacoes/` retorna entradas + requisições com `TIPO_MOVIMENTO`. **1 linha por item** da TGFITE.
- Frontend (Mai/2026 — 2026-05-13): **9 colunas finais**: Mov · Data · Parceiro/Veículo · Produto · Qtd · Valor · **Total km** · **Média** · Ações.
- Removidas: NUNOTA, Status.
- Badge **`🌐 EXTERNA`** laranja na coluna MOV quando `req.tipo === 'EXTERNA_POSTO'` (single badge, sem o `📋 Requisição` adicional).
- **Total km + Média calculados client-side** (`_calcularConsumoMov`): agrupa por veículo, ordena ASC por data, calcula `km = hod[i] − hod[i−1]` e `kmlt = km / qtd[i−1]`. Funciona pra requisição interna E externa (ambas têm hodômetro).
- Botões ✏/🗑 só na linha de REQUISIÇÃO (interna ou externa). Entrada → ✏ apenas, exclusão pelo modal de edição.

### Lista de veículos + lightbox
- Card de Estoque mostra grid 2 colunas de veículos com thumbnail. Toggle **COM** (frota) / **MAQ** (maquinário) por palavras-chave em `ESPECIETIPO` (TRATOR/COLHEIT/MAQUINA/PULVERIZ/etc → MAQ; resto → COM).
- Click no card → modo detalhe: foto grande, relatório de consumo, movimentações filtradas pelo veículo.
- **Lightbox** (Mai/2026): click na foto grande → modal full-screen com imagem em resolução máxima. Fecha por Esc / click fora / botão ×.
- Endpoint `api_foto_veiculo` aceita `?size=thumb` — Pillow gera thumbnail 480×360 cacheado em `_cache/<PLACA>.jpg`. Invalida automaticamente via mtime. Aceita JPG/JPEG/PNG/WEBP (case-insensitive). Trata RGBA (PNG transparente). `_cache/` em `.gitignore`.

---

## URLs

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/combustivel/` | GET | Portal HTML |
| `/api/estoque/` | GET | Saldo por CODPROD (cards de tanque) |
| `/api/veiculos/` | GET | Typeahead TGFVEI |
| `/api/produtos/` | GET | Typeahead TGFPRO CODGRUPOPROD=200400 |
| `/api/movimentacoes/` | GET | Listagem unificada |
| `/api/relatorio/consumo/` | GET | Relatório por veículo (período + abastecimentos + km/L) |
| `/api/veiculo-foto/<placa>/` | GET | Foto do veículo. `?size=thumb` gera/cacheia thumbnail |
| `/api/requisicao/criar/` | POST | Cria requisição TOP 53 interna |
| `/api/requisicao/<n>/` | GET | Detalhe requisição |
| `/api/requisicao/<n>/editar/` | POST | Edita requisição (interna ou externa) |
| `/api/requisicao/<n>/excluir/` | POST | Exclui requisição (físico) |
| `/api/abastecimento-externo/criar/` | POST | Cria abast externo TOP 53 EXTERNA_POSTO + TGFFIN |
| `/api/entrada/criar/` | POST | Cria entrada TOP 10 + TGFFIN (multi-itens) |
| `/api/entrada/<n>/` | GET | Detalhe entrada (cab+itens+fin) |
| `/api/entrada/<n>/editar/` | POST | Edita entrada (multi-itens diferencial) |
| `/api/entrada/<n>/excluir/` | POST | Exclui entrada (cascata TGFFIN+TGFITE+TGFCAB) |
| `/api/ultimo-preco/?codprod=N` | GET | VLRUNIT do último abastecimento — auto-fill em requisições internas |
| `/api/prazo-tipvenda/?codtipvenda=N` | GET | Prazo do TGFTPV (BASEPRAZO + regex `\d+ DIAS` na DESCRTIPVENDA como fallback) |

**Acesso**: Grupos `1` (Diretoria), `6` (TI), `10` (IAGRO_ADMINISTRATIVO), `11` (IAGRO_FROTA). Decorator `@exige_grupo('combustivel')`. _Administrativo ganhou acesso em 2026-05-14 — faz lançamento de combustível também._

---

## Cenários de requisição

Discriminador em `AD_REQUISICAO_COMBUSTIVEL.TIPO`:

| Tipo | Quando | Veículo | Hodômetro | Horímetro | Doc | TGFFIN |
|---|---|:-:|:-:|:-:|:-:|:-:|
| `INTERNA_FROTA` | Caminhonete/caminhão próprio | PROPRIO='S' | obrig. | obrig. | — | — |
| `INTERNA_MAQUINARIO` | Trator, colheitadeira | PROPRIO='S' | opc. | opc. | — | — |
| `EXTERNA_FRETE` | Caminhão de freteiro desconta do frete | PROPRIO='N' | NULL | NULL | obrig. | — |
| `EXTERNA_POSTO` (Mai/2026) | Abastecimento no posto (Allianz/Semear/Agromil) | qualquer | obrig. | — | NF/boleto opc. | **CODPARC=posto, RECDESP=-1** |

---

## Frontend — Estados especiais (Mai/2026, 2026-05-13)

### Defaults pré-preenchidos no modal
| Campo | Default |
|---|---|
| Empresa | `1 — HORTIFRUTI SEMEAR` (nome puxado async via `/empresa/search/?q=1`) |
| Centro de Resultado | `10100 — COMERCIALIZAÇÃO` |
| Natureza | `30070200 — COMBUSTÍVEL` |
| Tipo de Negociação | `11 — A VISTA` (não "Compra de combustível" — bug corrigido) |

### Auto-fill VLRUNIT (requisições internas)
- `onSelect` do typeahead de combustível chama `/api/ultimo-preco/?codprod=N` e preenche `reqVlrUnit` com `toFixed(4)`.
- Campo `reqVlrUnit` fica **readonly** (fundo cinza, tooltip "*Preço travado*") em tipos internos.
- Em **EXTERNA_POSTO** não aplica auto-fill — operador edita na tabela de itens.

### Auto-cálculo DTVENC (entrada)
- `onSelect` do typeahead Tipo Negociação → `window._cbRecalcularDtVenc()` → fetch `/api/prazo-tipvenda/` → `DTVENC = DTNEG + prazo_dias`.
- Fonte do prazo: `TGFTPV.BASEPRAZO` (oficial) OU regex `(\d+)\s*DIAS?` na `DESCRTIPVENDA` como fallback (Agromil tem ~95% de tipos com BASEPRAZO=0 e prazo no nome, ex "BOL BB 30 DIAS"). Pega `DHALTER` mais recente quando há histórico.

### Modal Nova Entrada (CRUD completo)
Layout: Empresa+Fornecedor / NºNota+Série+DataEntrada / TipoNegociação+DataVencimento / Centro+Natureza / **Tabela de Itens dinâmica** (botão `+ Item`, typeahead por linha, recalculo reativo) / Histórico / **Total da Nota** (calculado live, R$ destacado em verde) / Observação.

Botão **`🗑 Excluir entrada`** no rodapé esquerdo do modal **só em modo edição** (vermelho).

### Modal Nova Requisição (single + multi)
- Internos (`INTERNA_FROTA`/`MAQUINARIO`/`EXTERNA_FRETE`) → form **single** (Combustível + Qtd + Valor unit. avulsos).
- **`EXTERNA_POSTO`** (Mai/2026) → **tabela multi-itens** (igual Entrada) + **Total da Nota** + posto/doc/datas.
- Toggle dinâmico em `atualizarExternoVisivel()`: alterna entre `reqProdutoSingleWrap` (interno) e `reqItensExternoWrap` + `reqExtTotalWrap` (externo).
- Estado JS: `reqExtItens[]` paralelo a `entItens[]` (`_addItemReqExt`, `_removerItemReqExt`, `_renderReqExtItens`, `_atualizarTotalReqExt`).
- Edit externo popula `reqExtItens` com todos os itens (loop direto + render explícito final pra evitar race com `atualizarExternoVisivel`).

---

## Tabela `AD_REQUISICAO_COMBUSTIVEL`

Aplicada via [`AD_REQUISICAO_COMBUSTIVEL.sql`](../../sankhya_integration/sql/AD_REQUISICAO_COMBUSTIVEL.sql) (B1) + migrations:
- B4 (Mai/2026): substituiu `MEDIDOR_ATUAL/MEDIDOR_TIPO` por `HODOMETRO_KM` + `HORIMETRO_H` separados.
- B7 (Mai/2026, [`AD_REQUISICAO_COMBUSTIVEL_MIGRATION_EXTERNO.sql`](../../sankhya_integration/sql/AD_REQUISICAO_COMBUSTIVEL_MIGRATION_EXTERNO.sql)): +3 colunas (`CATEGORIA`, `CODPARC`, `NUFIN_GERADO`) + CHECK ampliado pra `EXTERNA_POSTO`.

| Coluna | Tipo | Função |
|---|---|---|
| `ID` | NUMBER PK | Sequence `SEQ_AD_REQUISICAO_COMBUSTIVEL` |
| `NUNOTA` | NUMBER UNIQUE NOT NULL | FK lógica TGFCAB TOP 53 |
| `TIPO` | VARCHAR2(20) CHECK | `INTERNA_FROTA` / `INTERNA_MAQUINARIO` / `EXTERNA_FRETE` / `EXTERNA_POSTO` |
| `CATEGORIA` | VARCHAR2(20) DEFAULT 'COMBUSTIVEL' NOT NULL CHECK | `COMBUSTIVEL` / `MANUTENCAO` (preparado pro módulo futuro) |
| `CODVEICULO` | NUMBER NOT NULL | FK lógica TGFVEI |
| `CODPARC` | NUMBER NULL | Obrigatório se TIPO='EXTERNA_POSTO' (posto/fornecedor) |
| `NUFIN_GERADO` | NUMBER NULL | Audit do NUFIN criado (só em externo) |
| `HODOMETRO_KM` | NUMBER(15,2) | km do veículo |
| `HORIMETRO_H` | NUMBER(15,2) | h da bomba |
| `DOC_FRETE_REF` | VARCHAR2(50) | NF/boleto |
| `OBSERVACAO` | VARCHAR2(500) | Texto livre |
| `CODUSU`, `NOMEUSU`, `CRIADO_EM` | — | Audit |

Constraints (nomes ≤30 chars Oracle 11g):
- `CK_AD_REQ_COMBUST_TIPO` — TIPO IN (...)
- `CK_AD_REQ_COMBUST_EXTPOSTO` — TIPO<>'EXTERNA_POSTO' OR CODPARC IS NOT NULL
- `CK_AD_REQ_COMBUST_CATEG` — CATEGORIA IN ('COMBUSTIVEL','MANUTENCAO')

---

## Funções service principais (`oracle_conn.py`)

### Leitura
| Função | Operação |
|---|---|
| `consultar_saldo_combustivel(filtros)` | View + cálculo em Python (não usa GREATEST da view) |
| `consultar_veiculos_disponiveis(termo, tipo, somente_ativos, limite)` | TGFVEI + TGFPAR |
| `consultar_produtos_combustivel(termo, limite)` | TGFPRO CODGRUPOPROD=200400 |
| `consultar_consumo_por_veiculo(codveiculo, date_start, date_end)` | Abastecimentos + km/L ou L/h calculado entre consecutivos |
| `consultar_ultimo_preco_combustivel(codprod)` | VLRUNIT do TOP 10 mais recente (auto-fill) |
| `consultar_prazo_tipvenda(codtipvenda)` | BASEPRAZO ou regex na DESCRTIPVENDA |
| `listar_movimentacoes_combustivel(filtros, limite, offset)` | UNION TOP 10 ∪ TOP 53; 1 linha por item; `WHERE c.CODTIPOPER IN (10, 53)` no comum |
| `obter_requisicao_combustivel(nunota)` | Detalhe completo (cab+itens+req) |
| `obter_entrada_combustivel(nunota)` | Detalhe completo (cab+itens+fin) — pra edição |

### Escrita (Categoria B aprovada)
| Função | Operação |
|---|---|
| `criar_requisicao_combustivel_banco` (B2) | TGFCAB TOP 53 + TGFITE + AD_REQ |
| `editar_requisicao_combustivel_banco` (B5/B11) | UPDATE TGFCAB+TGFITE+AD_REQ; caminho externo com UPDATE diferencial multi-itens; UPDATE TGFFIN |
| `excluir_requisicao_combustivel_banco` (B6/B12) | DELETE físico em cascata (TGFFIN externo → TGFITE → TGFCAB → AD_REQ) |
| `criar_abastecimento_externo_banco` (B8 refatorada) | TGFCAB TOP 53 STATUSNOTA='L' + N × TGFITE + AD_REQ EXTERNA_POSTO + TGFFIN despesa. Multi-itens. |
| `criar_entrada_combustivel_banco` (B3/B13 refatorada) | TGFCAB TOP 10 + N × TGFITE + TGFFIN. Multi-itens. NUMNOTA do operador. SERIENOTA. |
| `editar_entrada_combustivel_banco` (B14) | UPDATE diferencial atômico TGFCAB+TGFITE+TGFFIN. Bloqueia se baixado |
| `excluir_entrada_combustivel_banco` (B15) | DELETE físico cascata (TGFFIN → TGFITE → TGFCAB). Bloqueia se baixado |

---

## Frontend — arquivos

- **Template:** `combustivel.html`
- **CSS:** `combustivel.css`
- **JS:** `combustivel.js`
- **Cache:** versionado via `?v=N` (atualizado a cada release de mudança no JS/CSS — pula `v=300` quando trocado)

### Defaults JS
```js
const DEFAULT_CODCENCUS  = 10100;     // COMERCIALIZAÇÃO
const DEFAULT_CODNAT     = 30070200;  // COMBUSTÍVEL
const DEFAULT_CODTIPVENDA = 11;       // A VISTA
```

### Helpers reusados de IAgro
`IAgro.attachTypeahead`, `IAgro.postJSON`, `IAgro.showToast`, `IAgro.confirmarAcao`, `IAgro.wireFilterAuto`.

---

## Tests

`test_views_combustivel.py` — **84 testes** mockados (zero dependência de Oracle real). Cobertura:
- Acesso/decorator (5)
- Saldo + regressão GREATEST (3) · veículos/produtos (3+1)
- CRUD requisição (criar B2 / editar B5 / excluir B6) + adaptações externo (B11/B12) — ~17 tests
- CRUD entrada (criar B13 multi-itens / editar B14 / excluir B15) — ~10 tests
- CRUD abastecimento externo (B8 single + multi + edit/excluir) — ~6 tests
- Listagem unificada (regressão multi-item, filtros) — 2
- Consumo por veículo (km/L, L/h, totais) — 3
- Views Django (200/400/404/sem sessão) — ~15

Smokes reais (`apply_*.py` ou inline via `manage.py shell`) feitos no Oracle de produção pra confirmar cada B antes de subir.

---

## Status final (Mai/2026, 2026-05-13)

| Item | Estado |
|---|---|
| B1 — DDL `AD_REQUISICAO_COMBUSTIVEL` | ✅ |
| B2 — criar_requisicao | ✅ |
| B3 — criar_entrada original | ✅ |
| B4 — ALTER HODOMETRO/HORIMETRO | ✅ |
| B5 — editar_requisicao | ✅ |
| B6 — excluir_requisicao | ✅ |
| B7 — ALTER CATEGORIA/CODPARC/NUFIN_GERADO + EXTERNA_POSTO | ✅ |
| B8 — criar_abastecimento_externo | ✅ (refatorada multi-itens 2026-05-13) |
| B11 — editar requisição adaptado externo + multi-itens | ✅ |
| B12 — excluir requisição cuida TGFFIN externo | ✅ |
| B13 — criar_entrada multi-itens + NUMNOTA/SERIENOTA | ✅ |
| B14 — editar_entrada (UPDATE diferencial) | ✅ |
| B15 — excluir_entrada (DELETE físico cascata) | ✅ |
| Mudança TOP 26 → 53 | ✅ |
| View ANDRE_IAGRO_SALDO_COMBUSTIVEL atualizada | ✅ |
| Lightbox foto + thumbnail Pillow | ✅ |
| Auto-fill VLRUNIT + auto-cálculo DTVENC | ✅ |
| Listagem 9 colunas (Total km + Média + EXTERNA badge) | ✅ |
| **B7 (2026-05-15) — Hodômetro/horímetro opcionais em TODOS os tipos + campo Data interna** | ✅ |
| **B8 (2026-05-15) — NUMNOTA do operador em TGFCAB+TGFFIN no externo (validação numérica estrita) + DTVENC auto** | ✅ |

### B7 + B8 — Mudanças Mai/2026 (2026-05-15)

**B7** removeu validações que tornavam hodômetro/horímetro obrigatórios:
- `criar_requisicao_combustivel_banco` (era forçado em INTERNA_FROTA)
- `editar_requisicao_combustivel_banco` (era forçado em INTERNA_FROTA + EXTERNA_POSTO)
- `criar_abastecimento_externo_banco` (era forçado em EXTERNA_POSTO)

Todos os tipos agora aceitam medidores opcionais. EXTERNA_FRETE continua zerando ambos automaticamente (veículo terceiro, sem rastreamento próprio).

Campo **Data** novo (`#reqDtNeg`) no modal de requisição interna (FROTA/MAQUINARIO/EXTERNA_FRETE) — em EXTERNA_POSTO já existia `reqExternoDtNeg`. Default = hoje; payload `dtneg='YYYY-MM-DD'` formatado pra `DD/MM/YYYY` antes de gravar `TGFCAB.DTNEG/DTMOV`. Edição lê `cab.DTNEG`. `atualizarDtNegInternaVisivel()` esconde o campo em modo externo (evita duplicação).

**B8** — NUMNOTA do operador no abastecimento externo:
- `reqExternoDoc` virou `<input type="number" inputmode="numeric">` com validação cliente `/^\d+$/`. Placeholder "Apenas números (ex: 12345)".
- Backend `criar_abastecimento_externo_banco` valida estritamente: texto como `"NF 12345"` retorna erro `"Nº da nota fiscal deve ser apenas números (digite 12345, não NF 12345)."`.
- Quando válido, prioriza o número do operador em vez de gerar sequencial `MAX(NUMNOTA)+1`. Grava em `TGFCAB.NUMNOTA` **e** `TGFFIN.NUMNOTA` (mesmo bind `:numnota`). Sem trava de colisão — Sankhya aceita números repetidos em TOP 53.
- `editar_requisicao_combustivel_banco` propaga alteração de NUMNOTA pra TGFCAB + TGFFIN (UPDATE direto antes do bloco de UPDATE TGFFIN dos valores).

**DTVENC auto no abastecimento externo** — função nova `_recalcularDtVencExterno` replica `_cbRecalcularDtVenc` da Entrada. Listener no `reqExternoDtNeg.change` + `onSelect` do typeahead `reqTipVendaVis` consulta `BASEPRAZO` via `/combustivel/api/prazo-tipvenda/` e calcula `DTVENC = DTNEG + prazo_dias`. À vista (prazo=0) → DTVENC=DTNEG.

### Pré-requisitos restantes (cadastro humano no Sankhya)
1. Atribuir usuários ao grupo TSIGRU=11 (IAGRO_FROTA) ⚠ aguarda
2. Cadastrar máquinas/tratores faltantes em TGFVEI (PROPRIO='S') ⚠ aguarda
3. Cadastrar veículos de freteiros em TGFVEI (PROPRIO='N') ⚠ aguarda
