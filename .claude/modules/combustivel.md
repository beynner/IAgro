# Módulo Controle de Combustível (TOP 10 entrada / TOP 53 requisição interna)

Controle integral de estoque de combustível: compra (TOP 10 + TGFFIN em aberto), requisição interna (TOP 53 — frota/maquinário/freteiro) e abastecimento externo (TOP 53 + TGFFIN contra posto, **não desconta tanque**). Visual de tanques SVG, lista de veículos com lightbox de foto, listagem unificada de movimentações com Total km/Média de consumo, CRUD completo (criar/editar/excluir) de entrada e requisição, relatório de consumo por veículo.

**Status (Mai/2026, 2026-05-13)**: ✅ ponta-a-ponta funcional em produção. Falta apenas atribuir usuários ao grupo TSIGRU=11 (IAGRO_FROTA) e cadastrar veículos faltantes em TGFVEI.

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

### Pré-requisitos restantes (cadastro humano no Sankhya)
1. Atribuir usuários ao grupo TSIGRU=11 (IAGRO_FROTA) ⚠ aguarda
2. Cadastrar máquinas/tratores faltantes em TGFVEI (PROPRIO='S') ⚠ aguarda
3. Cadastrar veículos de freteiros em TGFVEI (PROPRIO='N') ⚠ aguarda
