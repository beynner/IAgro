# CLAUDE.md — IAgro (NexusGTi)

> Referência principal para todas as sessões com o assistente.
> **Idioma de toda comunicação: Português Brasileiro.**

---

## Identidade

- **Nome:** IAgro
- **Versão:** 1.1.2
- **Tipo:** Sistema de gestão operacional integrado ao ERP Sankhya. **Em transição para produto independente (spin-off SaaS multi-tenant agro)** — ver [`dependencias_sankhya.md`](.claude/dependencias_sankhya.md) e [memory `spin_off_iagro_estrategia`](../../memory).
- **Organização:** NexusGTi / HF Semear (cliente atual: Agromil)
- **Domínio:** Central de beneficiamento de produtos agrícolas (antigo "Packing House") + rastreabilidade SafeTrace/IAgro

O sistema integra dados do Sankhya via Oracle e oferece **onze módulos operacionais** + **2 administrativos**:

| Fluxo | TOP | Descrição |
|---|---|---|
| **Painel (Dashboard)** | — | Home com 6 indicadores de saúde (pedidos sem lote, lotes aguardando classif., vales abertos, tanques críticos, prontos pra faturar, lotes envelhecidos). Polling 5min |
| Entrada | 11 | Recebimento e conferência de notas de compra com pesagem |
| Classificação | 26 | Triagem de lotes por qualidade, com controle de descartes. Header do card mostra **badge `LOTE NNNS01D260512`** ao lado do nome do produto (Mai/2026) |
| Comercial | 13 | Faturamento de vales, precificação, geração de financeiro. **Card "Margem Lote" preenchido** em runtime — `(RECEITA − DEVOLUÇÃO − CUSTO) / RECEITA × 100` com avaria informativa no tooltip. **"Últimas Vendas DESTE LOTE"** com toggle Lote/Produto + sparkline SVG de evolução de preço — **sparkline span 2 rows** (fix 2026-05-18) pra não desalinhar card Médio |
| Venda | 34 → 35/37 | Pedidos, edição de itens, faturamento (NFe ou s/ NFe), avaria (TOP 30) e devolução (TOP 36) |
| Rastreio (WMS) | — | Vínculo de lotes a pedidos com auditoria e lock pessimista. Suporta vínculo manual pedido↔nota órfã e pedido retroativo. **Etiquetas SafeTrace 100×50mm** com QR + EAN13 (Zebra ZD220). Peso da etiqueta vem da TOP 26 (classificação) automaticamente — operador só digita se for múltiplos pesos ou override manual (Mai/2026 — 2026-05-16). **Saldo materializado em `AD_SALDO_LOTE_CACHE` com refresh por cron 5min** + cache Django 60s + WITH clause na query de pedidos (Mai/2026 — 2026-05-19): tela carrega em ~700ms (vs 25s antes) |
| E-mail (importação) | 34 (após confirmação) | Coleta IMAP de pedidos com PDF anexo, parser via LLM local (Ollama), revisão humana |
| Combustível (Frota) | 10 → 53 | Entrada de combustível (TOP 10) e requisições internas (TOP 53 — frota/maquinário/freteiro/posto externo). Discrimina frota própria + maquinário + freteiros. Inclui abastecimento externo (não desconta tanque interno) |
| **Caixas** | — | Controle de vasilhame retornável (caixa plástica). Saldo por cliente derivado de vendas via `CEIL(QTDNEG/PESO)`; coletas/quebras/perdas/ajustes manuais em `AD_COLETA_CAIXAS`; tipo de caixa por produto em `AD_PRODUTO_CAIXA`. **Botão Atualizar faz backfill `[TEMPORÁRIO Mai/2026]`** via moda da TOP 26 enquanto IAgro não vira fluxo único. Acesso amplo (grupos 1/6/8/9/10/11). Mai/2026 — 2026-05-18 |
| **Relatórios** | — | Tela `/sankhya/relatorios/` (restrita Diretoria/Suporte/Comercial) com 5 sub-abas: Top Clientes/Produtos · Lotes Envelhecidos · Consumo por Veículo · Fluxo de Caixa · Margem por Venda. Lazy load + cache 5min na margem. Mai/2026 — 2026-05-17 |
| **Auditoria Universal** | — | Tela `/sankhya/auditoria/` (restrita Diretoria/Suporte) consolidando AD_AUDITORIA_GERAL — todo evento de escrita do IAgro com snapshot antes/depois em JSON. 36 funções instrumentadas. Tela tem diff inteligente "antes→depois" + JSON técnico. **Acessada via engrenagem no header → Configurações** (não mais na sidebar) |

### Hub de Configurações + Usuários (Mai/2026 — 2026-05-17/18)

- **Engrenagem ⚙ no header** (visível só pra grupos 1+6) → `/sankhya/configuracoes/` — hub com cards de subseções administrativas (Usuários + Auditoria por enquanto)
- **Tela Usuários** `/sankhya/usuarios/` — gestão TSIUSU/TSIGPU. **Cat A entregue**: listar + detalhe + grupos disponíveis + toggle "Mostrar inativos" (default só ativos). **Cat B pendente** (criar/editar/inativar/reativar/add+remove grupo) — endpoints retornam 501 com `pendente_cat_b=true` até serem aprovados ponto-a-ponto

### Layout v2 — Sidebar agrupada retrátil + Content (Mai/2026 — 2026-05-17/18)

Todas as telas autenticadas usam o **novo layout**: sidebar lateral fixa (200px expand / 56px collapse / off-canvas em ≤900px) + content-header (título + ações + **engrenagem ⚙** + user-badge + sair) + main-layout.

**Sidebar agrupada por departamento, retrátil tipo acordeão** (Mai/2026 — 2026-05-18):
- Painel no topo (todos)
- 4 departamentos ativos: **Packing House** (Entrada/Classificação/Rastreio) · **Comercial** (Comercial/Relatórios) · **Administrativo** (Venda/Importação) · **Frota** (Combustível)
- 3 placeholders esmaecidos (roadmap visual): **Financeiro · DP/RH · Produção** — opacity 0.5, "Em breve" itálico, não clicáveis
- Comportamento **acordeão**: 1 section aberta por vez. Click em outra fecha a anterior. Estado persistido em `localStorage:iagro:sidebar:section:v1`
- Departamento do módulo ativo abre automaticamente (pré-paint script inline no `base.html`)
- Auditoria **removida da sidebar** — agora vive no hub Configurações

**Responsivo aplicado a todos os módulos** com breakpoints `1024 / 900 / 520px` — vide [`conventions.md`](.claude/conventions.md) → "Responsivo".

### 🛡 Defesa contra fakes em Oracle (Mai/2026 — 2026-05-18)

Após incidente onde tests rodados contra Oracle de produção poluíram TGFCAB/TGFITE/TGFFIN/AD_AUDITORIA com 843 fakes (CODUSU=1, NOMEUSU='Teste'), aplicada **defesa em 2 camadas**:

1. **FÍSICA** em `obter_conexao_oracle`: detecta `'test' in sys.argv` e levanta `RuntimeError` em vez de conectar Oracle real. Tests bem-mockados (`@patch('...obter_conexao_oracle')`) não chegam aqui; tests mal-mockados falham com erro visível.
2. **LÓGICA** via `IAgroTestRunner` ([tests/test_runner.py](sankhya_integration/tests/test_runner.py), configurado em `settings.TEST_RUNNER`): patcha `verificar_permissao_escrita` globalmente retornando True nos tests pra mocks funcionarem sem regressão.

**Resultado**: zero escritas no Oracle real durante tests + zero regressão de suíte existente. Bypass intencional via `IAGRO_TEST_REAL_DB=true` libera conexão real pra testes de integração reais. Detalhes em [memory `incidente_fakes_em_oracle_18_05_26`](../../memory/incidente_fakes_em_oracle_18_05_26.md).

Adicionalmente, **15 funções de escrita** ganharam guard `verificar_permissao_escrita()` antes do INSERT/UPDATE/DELETE — defesa em profundidade (combustível, email, alias, audit, etc).

### 🚀 Performance do Rastreio — materialização + cache em 3 camadas (Mai/2026 — 2026-05-19)

Antes: tela carregava em **25s** (lotes 12s + pedidos 14.5s rodando em paralelo). Operador travado a cada acesso. Pipeline final entrega **<1s** em uso típico — combinação de 3 técnicas complementares.

**1. Tabela materializada `SANKHYA.AD_SALDO_LOTE_CACHE` (Cat B aplicada)**

Espelho da view pesada `ANDRE_IAGRO_SALDO_LOTE` (5 CTEs com agregações sobre TGFITE/TGFCAB/TGFVAR — centenas de milhares de linhas). Estrutura: 19 colunas + `ATUALIZADO_EM`, PK `(CODEMP, CODPROD, CODAGREGACAO, STATUS_LINHA)`, 4 índices (`QTD_DISPONIVEL`, `DTNEG_ORIGEM DESC`, `CODPROD`, `VENDAVEL`). DDL em [`sankhya_integration/sql/AD_SALDO_LOTE_CACHE.sql`](sankhya_integration/sql/AD_SALDO_LOTE_CACHE.sql).

Função `refresh_saldo_lote_cache()` em `oracle_conn.py` faz **TRUNCATE + INSERT-SELECT** da view (~12s em background). Comando Django `python manage.py refresh_saldo_lote` é disparado pelo **Windows Task Scheduler a cada 5 min** + manualmente via `POST /sankhya/rastreio/api/refresh-saldo/` (botão **Atualizar** do header).

`consultar_saldo_lote_disponivel` agora aponta `FROM SANKHYA.AD_SALDO_LOTE_CACHE` em vez da view — leitura indexada **~80ms**. Outros consumidores da view (lock pessimista em `atribuir_lote_item_pedido`, relatórios, validações de saldo em escritas) **continuam usando a view real** pra integridade transacional.

**Coerência**: defasagem máxima de 5 min entre escrita e reflexo visual. Lock pessimista valida sempre na view real — não dá pra atribuir lote inexistente mesmo com cache atrasada.

**2. Refactor da query de pedidos com WITH clause (Cat A aplicada)**

`consultar_pedidos_abertos_para_atribuicao` tinha **2 subqueries escalares + 3 EXISTS correlacionados por linha** (NOTA_NUMNOTA, NOTA_NUNOTA, VINCULO_ORIGEM) — 5 operações em TGFVAR/AD_VINCULO_PEDIDO_NOTA scanned por cada cabeçalho de pedido. Em 347 pedidos = ~1700 scans em TGFVAR (211k linhas).

Refatorado pra **1 CTE única `notas_pedido`** que materializa o UNION ALL de TGFVAR + AD_VINCULO_PEDIDO_NOTA uma vez, com `MAX KEEP (DENSE_RANK FIRST ORDER BY PRIO)` resolvendo VINCULO_ORIGEM com prioridade (TGFVAR > RETROATIVO > MANUAL). Query externa faz LEFT JOIN simples.

Mais o `LEFT JOIN` agregado de origem do lote também trocado pra `AD_SALDO_LOTE_CACHE`.

Resultado: pedidos **14.5s → 590ms** (24× mais rápido).

**3. Cache Django (LocMemCache) com versionamento**

`oracle_conn.py:35-77` — TTL 60s + versionamento por `cache.set(_RASTREIO_CACHE_VER_KEY, time.time())`. Invalidação automática em **6 escritas** do Rastreio (atribuir, desvincular, inserir/remover vínculo manual, criar pedido retroativo, refresh manual). Chaves antigas viram inalcançáveis e expiram pelo TTL.

Segunda visita à tela em ≤60s = ~1ms (não toca Oracle).

**Resultado consolidado em prod**:

| Cenário | Antes | Depois |
|---|:-:|:-:|
| 1ª carga fresh | ~25s | **~700ms** |
| 2ª carga em <60s (cache Django) | ~25s | **~1ms** |
| Após atribuir/desvincular | ~25s | ~700ms (cache invalidado) |
| Botão Atualizar manual (refresh + reload) | ~25s | ~12-15s (refresh sincronizado) |

**Próxima evolução (registrada no roadmap #15)**: refresh on-demand (C2) — MERGE pontual na linha afetada após escrita, eliminando defasagem de 5min. Implementar **só se aparecer reclamação real** após 2 semanas de uso.

Detalhes completos em [`modules/rastreio.md`](.claude/modules/rastreio.md) "Materialização do saldo" + "Padrão de compactação visual".

### 🔓 Travas Classificação ↔ Comercial revisadas (Mai/2026 — 2026-05-19)

**Classificação só trava se TGFITE TOP 13 (Vale) existe** — vendas TOP 35/37 não bloqueiam mais. Pra destravar, Comercial usa `zerar_negociacao_banco` (DELETE em TGFITE TOP 13 do lote, preservando outros produtos). Regra aplicada em 3 lugares: abertura do modal de itens, salvar/editar item, excluir item. Sem filtro de STATUSNOTA — qualquer estado da TGFCAB conta. Detalhes em [`modules/classificacao.md`](.claude/modules/classificacao.md).

**Comercial faturar exige preço E classificação finalizada** (em produtos classificáveis):
- Trava 1: `vlrTotal > 0` no item TGFITE TOP 13 (já existia)
- Trava 2 (nova): TGFCAB TOP 26 com `PENDENTE = 'N'` pro lote
- Não-classificáveis (`GERAPRODUCAO != 'S'`): só preço importa
- Defesa em profundidade: backend em `gerar_financeiro_banco` valida via NOT EXISTS antes do INSERT TGFFIN
- Botão FATURAR começa **disabled** (`Verificando travas…`) — só libera após o loop de validação

Detalhes em [`modules/comercial.md`](.claude/modules/comercial.md) → "Travas do botão FATURAR".

### Bug fixes pontuais (Mai/2026 — 2026-05-19)

- **Descarte (`api_update_descarte_lote`)** não excluía após zerar negociação. SELECT sem filtro `CODTIPOPER` pegava linha errada (TOP 26 em vez de TOP 11). Forçado `c.CODTIPOPER = 11` no SELECT.
- **Cabeçalho do modal de classificação** mostrava cliente da venda em vez de fornecedor da compra. `MAX(NUNOTA)` filtrando só `GERAPRODUCAO='S'` pegava o NUNOTA mais recente — quase sempre venda. Forçado `c.CODTIPOPER = 11` em ambas as queries de `api_consultar_lote`.
- **Filtro fornecedor não limpava** ao remover chip. Case `'fabricante'` em `removerFiltro` (rastreio.js:566) limpava `inputFiltroLotes` em vez de `inputFiltroFabricante` — resquício do split de Mai/2026 quando os 2 inputs eram um só.
- **Aplicar simulação Comercial não distribuía Médio** quando Médio em branco. `ratio_medio = vMd / vEx = 0` zerava o lado do Médio. Fix: `if (vEx > 0 && vMd > 0)` mantém proporção, senão usa default `0.5`.

### ♻ Avaria do fornecedor — Absorver/Descontar com TOP 30 automática (Mai/2026 — 2026-05-20)

Produtos **não-classificáveis** (in natura direto pra TOP 13, sem passar pela Classificação) não tinham onde registrar avaria recebida do fornecedor — histórico era perdido. Agora há fluxo completo da Entrada ao Comercial.

**Entrada (TOP 11):**
- Modal de itens ganhou coluna **"Avaria forn."** entre Total kg e ações. Aparece **apenas em produtos não-classificáveis** (`GERAPRODUCAO ≠ 'S'`); classificáveis veem `—` (continuam usando a tela de Classificação).
- Auto-save no `blur`/Enter — sem botão dedicado. Feedback visual: borda âmbar enquanto salva, verde 1.5s ao confirmar, vermelha em erro.
- Endpoint dedicado `/sankhya/compras/api/avaria-fornecedor/` (POST) escapa da trava de edição de TOP 13/26. `atualizar_avaria_fornecedor_naoclass` (B10) trava se vale TOP 13 do pedido já tem TGFFIN — operador precisa desfaturar antes.
- Audit `AVARIA_FORNECEDOR` em `AD_AUDITORIA_GERAL` + invalida cache Rastreio.

**Comercial (modal Faturamento):**
- Ícone ⚠ âmbar no nome do produto com avaria + mini-modal explicativo (qtd entrada, fornecedor, data) ao clicar.
- **Segmented control** "Absorver | Descontar" (sem ícones — só texto) no item.
- **Default = Descontar** quando há avaria registrada na TOP 11 — premissa: operador da Doca já registrou, então provavelmente Comercial vai cobrar do fornecedor. Absorver é decisão explícita.
- **📌 Absorver**: Agromil banca. Ao FATURAR, backend reconciliação cria automaticamente **TGFCAB TOP 30** (Avaria Interna, CODNAT=20010200, STATUSNOTA='L') com `AD_NUMPEDIDOORIG = NUNOTA da TOP 11`. CODTIPVENDA herdada da TOP 11 (exigência do trigger `TRG_INC_TGFCAB`). TGFITE TOP 30 com VLRUNIT/VLRTOT documentando o custo da perda. Estoque desconta via perna D da view `ANDRE_IAGRO_SALDO_LOTE`.
- **📉 Descontar** (default): Comercial cobra do fornecedor. Vale TOP 13 fica com qtd LÍQUIDA (`qtd_cx − avaria_unidade × peso`) + vlrTotal recalculado. Sem TOP 30. Estoque coerente naturalmente.
- **Motivos da trava do FATURAR explícitos abaixo do botão** (lista amarela com ⚠): vale não salvo, sem preço, classificação não finalizada.

**Coerência idempotente (cobre refaturar):** ao FATURAR, `reconciliar_avaria_top30_no_faturamento` (B8) sincroniza tanto o vale TOP 13 quanto a TOP 30 com a decisão final do toggle. Múltiplas execuções (desfaturar→refaturar) não duplicam nem deixam órfãos.

**Backend (Cat B):**
| # | Função | Resumo |
|---|---|---|
| B6 | `upsert_avaria_top30_lote` | Cria TGFCAB TOP 30 se não existir (CODTIPVENDA herdada); DELETE+INSERT TGFITE idempotente |
| B7 | `remover_avaria_top30_lote` | DELETE TGFITE; apaga TGFCAB se ficou sem itens. Idempotente |
| B8 | `reconciliar_avaria_top30_no_faturamento` | Orquestrador. Sincroniza vale TOP 13 (via B11) + TOP 30 com decisão atual do toggle |
| B9 | `gerar_financeiro_banco(... lotes_absorver_avaria, codusu, nomeusu)` | Chama B8 ANTES do INSERT TGFFIN. Backward compat (None ignora) |
| B10 | `atualizar_avaria_fornecedor_naoclass` | Trava se vale tem TGFFIN |
| B11 | `upsert_preco_in_natura_modalFaturamento(... absorver_avaria_no_vale=True)` | Quando False, vale TOP 13 grava qtd líquida |
| B12 | `alternar_modo_avaria_vale_lote` | Endpoint dedicado pra alternar toggle sem editar preço — reaplica upsert com flag |

**TGFITE TOP 11 (Entrada) NUNCA modificada** — preserva documento original do recebimento do fornecedor. Toda diferença vai pro TGFITE TOP 13 (vale) ou pro TGFCAB/TGFITE TOP 30 (avaria interna).

**Performance do modal Faturamento (otimização Mai/2026 — 2026-05-20):**
- Antes do refactor: ~4s pra abrir modal (N fetches sequenciais).
- Agora: avarias + cabeçalho disparados em paralelo, loop de itens via `Promise.all`, cache local `cacheVale` evita re-fetch de lote repetido. ~1s típico.
- Ao faturar/desfaturar: estado visual do botão (FATURAR ↔ DESFATURAR + carimbo) aplicado **imediatamente** após a API responder. Refresh do modal vira fire-and-forget — não bloqueia feedback.

Detalhes técnicos em [`modules/comercial.md`](.claude/modules/comercial.md) → "Toggle Descontar/Absorver com avaria interna automática" e [`modules/entrada.md`](.claude/modules/entrada.md) → "Avaria do fornecedor em item NÃO-classificável".

### 💰 Preço automático da tabela do cliente na Venda (Mai/2026 — 2026-05-20)

Ao selecionar produto no modal de inserção/edição de item da Venda, IAgro **puxa preço automático** da tabela de preços do cliente. Operador continua livre pra sobrescrever.

**Regra resolvida via 3 tabelas Sankhya:**

```
TGFPAR.CODTAB do cliente
    → TGFTAB[CODTAB, MAX(DTVIGOR <= dtneg)] = NUTAB ativa
        → TGFEXC[NUTAB, CODPROD, TIPO='V'].VLRVENDA
```

Tipo de venda (`TGFTPV.CODTAB`) e cadastro de produto (`TGFPRO.CODTAB`) NÃO participam — todos NULL na Agromil. Validado via smoke real contra Oracle:

- Assaí Asa Norte + Tomate Salada Extra → R$ 8,50 ✅
- André Patrocinio (sem CODTAB) → silêncio + toast info ✅
- 4 formatos de `dtneg` (BR, ISO, inválido, omitido) → todos consistentes ✅

**Componentes (Cat A puro)**:

| Camada | Componente |
|---|---|
| Service | `consultar_preco_tabela(codparc, codprod, dtneg=None)` em [oracle_conn.py](sankhya_integration/services/oracle_conn.py) |
| Endpoint | `GET /sankhya/venda/api/preco-tabela/` |
| Frontend | `puxarPrecoTabela()` no `onChange` do typeahead `item_prod_vis` em [venda.js](sankhya_integration/static/sankhya_integration/venda.js) |

**Bug corrigido durante implementação**: conversão implícita de data Oracle. SQL inicial usava `WHERE DTVIGOR <= :d` com `:d` string `'21/05/2026'`. Oracle interpretava errado via `NLS_DATE_FORMAT` da sessão → WHERE inválido → NUTAB=NULL → cliente com tabela caía em SEM_PRECO silencioso. Fix: `TO_DATE(:d, 'DD/MM/YYYY' | 'YYYY-MM-DD')` explícito por detecção do separador.

**Pendência conhecida (Cat B futuro)**: IAgro não popula `TGFITE.NUTAB` no INSERT — perde paridade com Sankhya nativo. Não causa erro fiscal mas será adicionado no payload de `inserir_item_nota_banco` em sessão futura. Detalhes em [`.claude/tabela_precos_sankhya.md`](.claude/tabela_precos_sankhya.md) §8.

### 🖨 Impressão de pedidos PDV + Consolidação por grupo (Mai/2026 — 2026-05-21)

Botão impressora da Venda (`btnPrintVenda`, antes desabilitado) agora abre **modal de impressão** com 2 painéis: lista de pedidos do dia (com checkbox) + consolidação por CODPROD calculada server-side. 2 modos de saída: **PDF individual** (1 página por pedido, layout idêntico ao Sankhya) ou **PDF consolidado** (agregado por produto com totais).

**Agrupamentos rápidos via chips dinâmicos** — só aparecem os grupos com pedidos no dia (Assaí DF / Palmas + Araguaína / Todos os Assaís / Economart / Exal-Lundin / JC / Verdi / Na Horta / Todos do dia). Mapeamento por `TGFPAR.CODTAB` (5=Assaí DF, 17=Araguaína, 18=Palmas, 6=Economart, 15=Exal, etc). Default ao abrir: "Todos os pedidos do dia" — operador já vê tudo consolidado sem clicar em nada.

**Cascata de cálculo de caixas (3 camadas em 1 query única)** — pra produtos onde `TGFITE.PESO` da venda está em 0 ou 1:

```
PRIO 1: Moda PESO TOP 26 (Classificação)    ← peso real do lote (mais preciso)
PRIO 2: TGFVOA[CODPROD, 'CX', M].QUANTIDADE ← cadastro Sankhya nativo (NOVO)
PRIO 3: Moda PESO TOP 11 (Entrada)          ← último recurso
```

`consultar_pesos_referencia_por_codprods` em [oracle_conn.py](sankhya_integration/services/oracle_conn.py) faz **1 query Oracle** com CTEs unidas via `UNION ALL` + `MAX(PESO) KEEP DENSE_RANK FIRST ORDER BY PRIO ASC` — pega a camada mais prioritária que tenha dado pra cada CODPROD. Cobertura testada na Agromil: **97% dos produtos vendidos no último mês** têm fator resolvido automaticamente (sem cadastro adicional do operador).

**Casos resolvidos pela camada 2 (TGFVOA)** — produtos vendidos em unidade alternativa sem classificação:
- TOMATE GRAPE (372): venda em KG, `TGFVOA[CX]=20.0` → CEIL(40/20) = 2 caixas
- MILHO VERDE (61): venda em BD, `TGFVOA[CX]=10.0` → CEIL(500/10) = 50 caixas

Pra produtos não cobertos (~3%), orientação é cadastrar `(CODPROD, 'CX', 'M', X)` na tela nativa do Sankhya — fonte única da verdade, sem coluna `AD_*` paralela.

**Layout do PDF (idêntico ao Sankhya):**
- **Individual**: header com empresa + cliente (CNPJ, IE, endereço, fone) + tabela CÓDIGO / DESCRIÇÃO / UN / QTD (sem decimal) / VLR UNIT / CX + linha de TOTAIS destacada (verde Agromil + borda superior espessa) + bloco OBSERVAÇÃO/TOTAIS no rodapé. Coluna VENDEDOR e VALE 1/2 removidas (decisão Mai/2026 — IAgro não usa). CX preenchida via fallback (CEIL aplicado item-a-item antes de renderizar).
- **Consolidado**: header com título + período + N pedidos consolidados; tabela CÓDIGO / DESCRIÇÃO / UN / QTD TOTAL / CAIXAS / Nº PEDIDOS ordenada por CODPROD; linha de TOTAIS destacada; lista de pedidos consolidados ao final.

**Detalhes técnicos:**

| Componente | Cat | Onde |
|---|---|---|
| `obter_dados_pedido_completo_para_impressao(nunota)` | A (leitura) | [oracle_conn.py](sankhya_integration/services/oracle_conn.py) — JOIN TGFCAB+TGFPAR+TSIEMP+TGFITE+TGFPRO, schema-resilient |
| `listar_pedidos_para_impressao(filtros)` | A (leitura) | Lista TOP 34 ativos. Filtros: codtabs, dtneg/dtneg_de/dtneg_ate, codparc, nunotas |
| `consultar_pesos_referencia_por_codprods(codprods)` | A (leitura) | Cascata 3 camadas (TOP 26 / TGFVOA / TOP 11) |
| `gerar_pdf_pedidos_individual` + `gerar_pdf_pedidos_consolidado` | A | Novo módulo [pedido_venda_pdf.py](sankhya_integration/services/pedido_venda_pdf.py) com reportlab |
| 4 endpoints REST | A | `/sankhya/venda/api/imprimir/{preview,consolidacao,pdf-individual,pdf-consolidado}/` — PDFs aceitam POST com JSON body (evita URI Too Long com listas grandes) |
| Modal `#impressaoModal` + JS reativo | A | [venda_modais.html](sankhya_integration/templates/sankhya_integration/venda_modais.html) + [venda.js](sankhya_integration/static/sankhya_integration/venda.js) |

**Bug crítico corrigido durante implementação**: filtro `WHERE` em `listar_pedidos_para_impressao` tinha `STATUSNOTA <> 'E' OR STATUSNOTA IS NULL` **sem parênteses** — precedência do `OR` ignorava filtros de data, devolvendo histórico inteiro (14k pedidos). Fix: `(STATUSNOTA <> 'E' OR STATUSNOTA IS NULL)`.

### ⚙ Diretriz arquitetural revisada — colunas `AD_*` em tabelas Sankhya nativas (Mai/2026 — 2026-05-21)

A regra que proibia adicionar colunas em tabelas Sankhya nativas **foi relaxada**. Agora é permitido (com aprovação Cat B ponto-a-ponto), porque o schema do banco do spin-off futuro será réplica exata do Sankhya + nossas extensões `AD_*` — não cria dívida.

**Disciplina obrigatória** (registrada em [`CLAUDE.md`](CLAUDE.md) → "Estratégia de produto"):
- Prefixo `AD_<NOME>` (sem prefixo é reservado a campos nativos)
- **Ler antes de criar** — se o dado já existe em campo nativo ou tabela Sankhya, ler em vez de duplicar (zero risco de desencontro)
- DDL versionada em `sankhya_integration/sql/` + entrada em [`dependencias_sankhya.md`](.claude/dependencias_sankhya.md)
- Cat B obrigatório
- Tabela auxiliar `AD_*` ainda é preferível quando o dado é multi-row por entidade

**Inventário inicial das colunas `AD_*` em tabelas nativas** (já existiam — agora documentadas formalmente):

| Tabela | Coluna | Uso |
|---|---|---|
| `TGFCAB` | `AD_NUMPEDIDOORIG` | Rastreabilidade nota raiz via lote (Agromil) |
| `TGFITE` | `AD_NUMPEDIDOORIG` | Propagado do cabeçalho |
| `TGFITE` | `AD_QTDAVARIA` | Descarte da Classificação / Avaria fornecedor não-classificável |
| `TGFITE` | `AD_PESO` | Peso da pesagem na Entrada (legado — desde Mai/2026 IAgro usa `TGFITE.PESO` nativo) |
| `TGFITE` | `AD_QTDCONFERIDA` | Qtd conferida na Entrada |

Detalhes em [`dependencias_sankhya.md`](.claude/dependencias_sankhya.md) §5.5.

**Caso prático dessa sessão**: pra resolver cálculo de caixas do TOMATE GRAPE e MILHO VERDE, ao invés de criar coluna `TGFPRO.AD_FATOR_CAIXA`, descobrimos que o dado já existia em `TGFVOA` (volumes alternativos Sankhya nativo). Cobertura imediata de 62% dos produtos vendidos + 97% somando outras unidades alt. Operador cadastra os outliers via tela nativa do Sankhya — IAgro só lê.

### 🎁 Tabela de Preços + Promoções com escopo flexível (Mai/2026 — 2026-05-20/21)

Sessão grande dividida em 2 dias:

**2026-05-20** — primeira versão de Promoções (CODPARC obrigatório) + chips Tabela/Promoção/Manual no modal de item da Venda + tela `/sankhya/venda/promocoes/` com CRUD. Origem do preço registrada em `AD_ITEM_PRECO_ORIGEM` (TABELA / PROMOCAO / MANUAL — MANUAL exige observação obrigatória).

**2026-05-21** — refator pra **escopo flexível** + nova section "Tabela de Preços" na sidebar:

- **ALTER `AD_PROMOCAO`**: adicionou `CODTAB` nullable, tornou `CODPARC` nullable, novo `CHECK XOR` (exatamente 1 dos 2). Promoção agora pode ser por **grupo (CODTAB do Sankhya)** OU **parceiro individual** — refletindo o cenário real da Agromil onde lojas Assaí DF (7 lojas, CODTAB=5) compartilham tabela.
- **`consultar_promocoes_vigentes`** ganhou OR no WHERE: busca por CODPARC direto OU pelo CODTAB do parceiro. 1 cadastro afeta automaticamente todas as lojas do grupo.
- **Sidebar nova section "Tabela de Preços"** entre Comercial e Administrativo, com 2 sub-itens:
  - `Tabela` — visualização leitura dos preços vigentes de cada grupo (TGFEXC)
  - `Promoções` — CRUD (migrado de Administrativo)
- **Tela `/sankhya/venda/tabela-precos/`** (Cat A pura): sidebar com 11 grupos ativos (toggle "Mostrar inativas" libera +9), ordenados por nome. Conteúdo mostra clientes do grupo (chips), preços TGFEXC + flag de promoção vigente (linha amarela quando há).
- **Descoberta `TGFNTA`** — tabela mestre Sankhya com `NOMETAB` (nome humano: ASSAI, ECONOMART, EXAL, VERDI...). View `VGFTAB = TGFNTA INNER JOIN TGFTAB MAX(DTVIGOR)`. IAgro lê direto de TGFNTA pra evitar dependência da view.

**Mapa real CODTAB → Grupos Agromil**:

| CODTAB | NOMETAB (Sankhya) | Clientes |
|---|---|---|
| 5 | ASSAI | 9 lojas (7 Assaí DF + 2 BARÃO antigos) |
| 17 | ASSAI ARAGUAINA | 1 |
| 18 | ASSAI PALMAS | 2 |
| 6 | ECONOMART | 3 (Barreiras, LEM ativos + 1 antiga) |
| 15 | EXAL | 3 (AURA, LUNDIN + RAJA antigo) |
| 4 | JC | 4 |
| 10 | VERDI | 4 (3 Verdi + Pravoce) |
| 2 | NA HORTA | 2 |

**Componentes**:

| Camada | Componente |
|---|---|
| DDL aplicada | `AD_PROMOCAO` (com `CODTAB`+`CODPARC` XOR), `AD_ITEM_PRECO_ORIGEM`, `SEQ_AD_PROMOCAO`, índices `IDX_AD_PROMO_VIGENTE` + `IDX_AD_PROMO_CODTAB` |
| Services (Cat A) | `consultar_promocoes_vigentes`, `listar_promocoes_cadastradas`, `listar_tabelas_grupos`, `listar_precos_da_tabela`, `consultar_origem_preco_item` |
| Services (Cat B) | `criar_promocao_banco`, `editar_promocao_banco`, `excluir_promocao_banco`, `registrar_origem_preco_item` |
| Integração existente (Cat B) | `api_salvar_item_venda` + `api_atualizar_item_venda` aceitam `preco_origem`, `nutab`, `promocao_id`, `observacao_preco` no payload |
| Endpoints | 7 sob `/sankhya/venda/api/promocoes/*`, `/promocao/*`, `/tabelas-grupos/`, `/tabela-precos/`, `/origem-preco-item/` |
| Telas | `/sankhya/venda/promocoes/` (CRUD), `/sankhya/venda/tabela-precos/` (LEITURA) |
| Frontend | `puxarPrecoTabela()` no modal de item agora carrega tabela + promoções em paralelo, exibe chips, prioriza PROMOCAO sobre TABELA |

**Cobertura operacional validada via smoke**: Asa Norte (CODPARC=244, CODTAB=5) acha promoção CODTAB=5; Palmas (CODPARC=211, CODTAB=18) **não** acha (CODTAB diferente); SEM escopo / COM os 2 escopos rejeitados; ordenação por menor `VLRPROMO`. Detalhes em [`modules/venda.md`](.claude/modules/venda.md) → "Promoções com escopo flexível" e [`tabela_precos_sankhya.md`](.claude/tabela_precos_sankhya.md).

### 🛠 Fix TRG_UPT_TGFITE — RESERVA/ATUALESTOQUE/USOPROD em pedido de venda (Mai/2026 — 2026-05-20)

Pedido criado pelo IAgro (TOP 34) salvava normalmente, mas ao **abrir/imprimir no Sankhya** o `STP_CONFIRMANOTA2` disparava UPDATE em TGFITE e o trigger `TRG_UPT_TGFITE` rejeitava com `ORA-20101: Reserva diferente da definicao na TOP`. Operador não conseguia imprimir nem faturar pelo Sankhya.

Diagnóstico via comparação direta TGFITE NUNOTA=113083 (1 item IAgro vs 1 item Sankhya nativo) identificou 3 campos que o IAgro deixava com default ≠ do que a TOP 34 espera:

| Campo | IAgro (antes) | Sankhya nativo | Fix |
|---|---|---|---|
| `RESERVA` | `'N'` | `'S'` | Causa direta do trigger — grava `'S'` |
| `ATUALESTOQUE` | `-1` | `1` | Grava `1` (atualiza estoque ao faturar) |
| `USOPROD` | `'V'` (chute) | de `TGFPRO.USOPROD` | Lê do cadastro do produto (fallback `'R'`) |

[`inserir_item_nota_banco`](sankhya_integration/services/oracle_conn.py) ganhou `CODTIPOPER` no SELECT da TGFCAB e preenche os 3 campos quando `CODTIPOPER IN (34, 35, 37)`. Schema-resilient (`if 'COL' in colunas_tabela`). Outras divergências menores (NULL no IAgro vs `0.0` em `NUTAB/CODTRIB/ALIQICMS/CUSTO/M3` etc) **não** disparam o trigger — Sankhya recálcula internamente quando precisa.

**Escopo do fix**: só pedidos novos criados após 2026-05-20. Pedidos antigos pré-fix continuam com `RESERVA='N'` — operador faz UPDATE manual no Sankhya quando encontrar. Como Agromil está começando a usar IAgro pra vendas agora, volume é pequeno. Detalhes em [`gotchas.md`](.claude/gotchas.md), [`modules/venda.md`](.claude/modules/venda.md) e [`dependencias_sankhya.md`](.claude/dependencias_sankhya.md) §2.2.5.

### 🛠 Fix QTDCONFERIDA — `CORE_E04678` no faturamento Sankhya (Mai/2026 — 2026-05-22)

Pedidos TOP 34 criados pelo IAgro **sem lote vinculado** não conseguiam ser faturados pelo Sankhya — erro `[CORE_E04678] Não existem produtos/quantidades disponíveis para essa operação`.

**Causa**: `inserir_item_nota_banco` gravava `QTDCONFERIDA = QTDNEG` por default (`qtdconferida = dados.get('QTDCONFERIDA') or qtdneg`). Sankhya interpreta `QTDCONFERIDA = QTDNEG` como "item já conferido/entregue" → nada a atender → erro. Sankhya nativo grava `0.0` em pedido novo. Pedidos com `ATRIBUIR_LOTE` (Rastreio) funcionavam porque alguma rota/trigger zerava QTDCONFERIDA ao vincular o lote — pedidos sem lote ficavam quebrados.

Diagnóstico via comparação cirúrgica TGFITE de **113264 (IAgro, erro)** vs **113259 (Sankhya nativo, OK, mesmo cliente/produto/dia/STATUSNOTA/PENDENTE)** — única coluna divergente:

| Campo | IAgro | Sankhya nativo |
|---|:-:|:-:|
| QTDNEG | 1.0 | 1.0 |
| **QTDCONFERIDA** | **1.0** | **0.0** |
| QTDENTREGUE | 0.0 | 0.0 |
| PENDENTE (ambos) | S | S |

UPDATE cirúrgico em 113264 (`QTDCONFERIDA: 1.0 → 0.0`, sem mexer em mais nada) destravou o faturamento, confirmando hipótese.

**Fix em `inserir_item_nota_banco`** ([oracle_conn.py:1138](sankhya_integration/services/oracle_conn.py#L1138)): default condicional ao CODTIPOPER:
- **TOP 34/35/37** (venda) → `QTDCONFERIDA = 0.0`
- **Outros TOPs** (11/13/26/30/36/10/53) → `QTDCONFERIDA = QTDNEG` (default histórico preservado — faz sentido em Entrada onde operador confere ao receber)
- Payload com QTDCONFERIDA explícita continua respeitado (inclusive `0` em TOP 11)

**Pedidos antigos pré-fix** continuam com `QTDCONFERIDA = QTDNEG`. Operador faz `UPDATE TGFITE SET QTDCONFERIDA=0 WHERE NUNOTA=X` quando encontrar, ou aplica backfill em massa (Cat B separado se aparecer volume).

**Histórico do diagnóstico (importante registrar)**: o erro `CORE_E04678` foi inicialmente atribuído erroneamente a `PENDENTE='S'` (commit `29bfa59`, depois revertido em `b826024`). O Sankhya nativo grava `PENDENTE='S'` em pedido TOP 34 novo (vira 'N' apenas ao ser atendido) — o IAgro estava correto. O erro real é só QTDCONFERIDA. Lição: validar premissas com pedidos do mesmo estado (atendido vs não-atendido) antes de inferir causa.

**Tests novos**: 4 em `test_views_venda.py` cobrindo (a) TOP 34 grava QTDCONFERIDA=0, (b) TOP 11 preserva QTDNEG, (c) payload explícito é respeitado, (d) QTDCONFERIDA=0 explícito em TOP 11 (edge case do `or qtdneg` antigo que ignorava 0).

### 🔄 Navegação inversa TGFVAR — divisão por lote em Devolução + Avaria (Mai/2026 — 2026-05-21)

Quando o Sankhya fatura via "atender pedido", **consolida** múltiplas linhas TGFITE do pedido (cada uma com seu CODAGREGACAO) em 1 linha da nota. Ex.: pedido TOP 34 SEQ 5 com 500kg lote A + SEQ 6 com 500kg lote B vira nota TOP 35 SEQ 1 com 1000kg consolidado. Antes desta entrega, qualquer **devolução (TOP 36) ou avaria (TOP 30) a partir de uma nota faturada com SPLIT** colapsava no lote único da nota — saldo do outro lote nunca recuperava (devolução) nem descontava (avaria), perdendo coerência com a realidade física.

**Solução**: navegar TGFVAR no sentido inverso (`NUNOTA → NUNOTAORIG, SEQUENCIA → SEQUENCIAORIG`) pra recuperar todos os lotes do pedido origem que viraram aquela 1 linha da nota. UX permite dividir a qtd devolvida/avariada entre os lotes reais.

#### Fase 1 — Leitura pura (Cat A)

| Componente | Função |
|---|---|
| `consultar_lotes_origem_de_seq_nota(nunota_nota, sequencia_nota)` | Nova em [oracle_conn.py](sankhya_integration/services/oracle_conn.py). JOIN TGFVAR ← TGFITE do pedido. Retorna `[{seq_pedido, codagregacao, qtdneg_pedido, qtd_atendida, nunota_pedido}]` ordenado por SEQUENCIAORIG. Lista vazia = nota órfã |
| `consultar_nota_para_devolucao` | Refatorado: cada item ganha campo `lotes_origem: [...]`. Tolerante a falha (log + lista vazia) |
| `GET /sankhya/venda/api/lotes-de-item-nota/?nunota=X&sequencia=Y` | Endpoint REST compartilhado por Devolução + Avaria |
| Modal Devolução | Coluna Lote exibe badge âmbar `N lotes ⚡` com tooltip listando cada lote quando há 2+ lotes |

#### Fase 2 (Item B1, Cat B) — Devolução TOP 36 multi-lote

`criar_devolucao_top36_banco` aceita 2 formatos por item:
- **Antigo**: `{sequencia_origem, qtd_devolver, vlrunit?}` → 1 TGFITE TOP 36 (preservado)
- **Novo**: `{sequencia_origem, lotes_devolver: [{codagregacao, qtd, vlrunit?}]}` → N TGFITE TOP 36

**Semântica TGFVAR preservada (crítico)**: em AMBOS os formatos, `SEQUENCIAORIG = SEQ da nota TOP 35/37` (não do pedido). Espelha o que o Sankhya faz no faturamento de SPLIT inverso (N TGFVAR convergindo pra 1 SEQ na nota). A trava `consultar_devolucoes_anteriores_de_nota` que agrupa por SEQ da nota continua intacta.

**Frontend**: modal renderiza sub-tabela editável amarelada quando `lotes_origem.length >= 2`. Ao marcar checkbox: expande sub-linha + sugestão proporcional automática (`max × atendido_lote / total_atendido`). Resumo `0,00 de 1.000,00` reativo na linha-pai com cor vermelha se soma excede saldo.

#### Fase 3 (Item B2, Cat B) — Avaria TOP 30 multi-lote

`criar_avaria_top30_banco` aceita modo "a partir de nota" (detecção via presença de `lotes_avaria` no payload):

| Modo | Payload | Resultado |
|---|---|---|
| Avulso (preservado) | `codagregacao` + `qtdneg` únicos | 1 TGFCAB TOP 30 + 1 TGFITE |
| A partir de nota | `nunota_origem_nota` + `sequencia_nota` + `lotes_avaria: [{codagregacao, qtd}]` | 1 TGFCAB TOP 30 + N TGFITE (1 por lote) |

Saldo validado individualmente por lote — falha em 1 reverte tudo (atomicidade). **Sem TGFVAR criado** (política da avaria preservada — diferente da Devolução). Frontend ganha toggle no topo do modal (Avulsa vs A partir de nota) + radio button por item da nota + sub-tabela editável idêntica à devolução.

#### UX polish (Mai/2026 — 2026-05-21)

- **Clamp automático no blur**: input que recebe valor > saldo é ajustado pro teto + toast info `"Ajustado pro máximo disponível: X,XX"`. 3 camadas de defesa (HTML max + JS submit + backend) reforçadas com clamp visual.
- **Larguras das colunas** com `<colgroup>` priorizam Produto (flex 1); Dev. 36px; Lote 110px; numéricas 62px; Qtd 100px.
- **2 casas decimais** em todas as quantidades dos 2 modais (Devolução + Avaria) — operador Agromil trabalha sempre em kg com 2 decimais (3 casas era ruído visual).
- **Coluna Vendido sem unidade** — `1.500,00` em vez de `1.500,00 KG` (unidade já visível no input "Qtd devolver" + no toggle de Volume do modal de avaria).
- **Microcopy melhorada**: `"em aberto"` (jargão Sankhya) → `"pendente de confirmação"` + instrução explícita de abrir no Sankhya pra disparar financeiro reverso + NFe.

**Tests novos**: 22 tests cobrindo (a) função de navegação inversa pura, (b) propagação de `lotes_origem` em `consultar_nota_para_devolucao`, (c) endpoint REST, (d) B1 — TGFVAR.SEQUENCIAORIG aponta pro SEQ da nota, (e) B1 — N TGFITE com CODAGREGACAO correto + backward-compat, (f) B2 — 1 TGFCAB + N TGFITE + zero TGFVAR + atomicidade. Suíte de venda 141 tests, zero regressão.

Detalhes técnicos em [`modules/venda.md`](.claude/modules/venda.md).

### Backlog planejado

- **Módulo Relatórios — MVP entregue em 2026-05-17** com 5 relatórios funcionando. Restam **20 relatórios** mapeados no backlog (6 eixos: Financeiro / Vendas / Compras-Estoque / Rastreio-WMS / Combustível-Frota / Auditoria-Produtividade) aguardando feedback operacional pra priorizar próximas iterações. Export Excel/PDF intencionalmente fora do MVP. Detalhes em [`roadmap.md`](.claude/roadmap.md) → "Módulo Relatórios — Backlog planejado" e em [`modules/relatorios.md`](.claude/modules/relatorios.md).

### Estratégia de produto (Mai/2026 — atualizado 2026-05-21)

IAgro está sendo modelado pra virar **produto SaaS independente do Sankhya**, atendendo múltiplos clientes do agro com produtos diferentes (hortifrúti, grãos, carnes, defensivos, etc.). **Diretrizes:**

- **Schema núcleo permanece igual ao Sankhya** (TGFCAB, TGFITE, TGFPAR, TGFPRO, TSIEMP, etc.) — quando desacoplar, recriar mesmos nomes em banco próprio.
- **Tabelas auxiliares (`AD_*` ou `ANDRE_IAGRO_*`)** podem ser criadas livremente no banco atual — sem restrição.
- **Estender tabelas Sankhya nativas com colunas `AD_*` É PERMITIDO** (atualizado 2026-05-21). O spin-off vai recriar o schema do Sankhya **exatamente** com as mesmas tabelas e colunas + nossas extensões `AD_*` — então acoplar via coluna `AD_*` não cria dívida adicional. Disciplina obrigatória:
  - **Prefixo `AD_<NOME>`** obrigatório (sem prefixo é reservado a campos nativos Sankhya).
  - **Ler antes de criar:** se o dado já existe em campo nativo ou em tabela Sankhya, **ler** em vez de duplicar (zero risco de desencontro).
  - **DDL versionada** em `sankhya_integration/sql/` + entrada em [`dependencias_sankhya.md`](.claude/dependencias_sankhya.md).
  - **Categoria B (aprovação ponto-a-ponto)** continua exigida pra `ALTER TABLE` em tabela nativa.
  - **Tabela auxiliar `AD_*` ainda é preferível** quando o dado é multi-row por entidade (vários clientes por produto, histórico temporal). Coluna escalar única é candidato natural a coluna em tabela nativa.
- **Evitar criar triggers** no Oracle — conflito potencial com triggers nativas.
- **Dependências mapeadas** em [`dependencias_sankhya.md`](.claude/dependencias_sankhya.md) — atualizar a cada nova dependência descoberta (regra crítica #7).
- **Risco principal:** triggers Sankhya proprietárias fazem coisas invisíveis que IAgro herda. Quando desacoplar, lógica delas precisa ser reimplementada em código Python.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework web | Django 6.0.4 |
| Banco ERP | Oracle (Sankhya) via `oracledb` 3.4.2 |
| Banco Django | SQLite (sessões + modelos `Simulation` e `RastreioAudit`) |
| Frontend | HTML + CSS + JS puro (sem framework) |
| Autenticação | Sessão própria via API HTTP do Sankhya |
| Configuração | `python-dotenv` |
| Relatórios | `reportlab` |
| Imagens | `pillow` |

---

## Regras Críticas (sempre aplicar)

Estas são as sete regras inegociáveis. Detalhes e regras complementares em [`.claude/rules.md`](./.claude/rules.md).

1. **NUNCA alterar lógica de negócio** (queries Oracle, cálculos financeiros, regras de precificação, fluxo de faturamento) sem aprovação explícita do usuário.
2. **🛑 BLOQUEIO EXPLÍCITO — alteração de dados no banco (queries NOVAS e ANTIGAS).** Qualquer código que vá escrever no Oracle — **nova ou já existente** — usando INSERT/UPDATE/DELETE/MERGE/ALTER/DROP/TRUNCATE (em funções de service, DDL direta, ou views Sankhya **não** prefixadas por `AD_`/`ANDRE_IAGRO_`) **PARA** e exige aprovação ponto-a-ponto com plano detalhado: **o quê · como · por quê · o que afeta**. Vale para função aditiva nova *com* INSERT/UPDATE/DELETE também — apenas SELECT puro fica fora. Detalhes em [`rules.md`](./.claude/rules.md) regras #2 e #4.
3. **SEMPRE apresentar plano antes de agir.** Para qualquer alteração, listar todos os arquivos afetados e aguardar "sim" antes de executar. Marcar quais itens caem em Categoria B (regra #2/#4).
4. **APÓS plano aprovado, executar em modalidades:** Categoria A (frontend, funções aditivas, views `AD_*`, tests, docs) roda em **modo loop autônomo** (faz → testa → corrige → finaliza) sem reabrir aprovação. Categoria B (alteração de dados no banco, lógica de negócio, operações destrutivas) exige **pausa ponto-a-ponto**. Execução parcial sob demanda quando solicitada.
5. **NUNCA refatorar `oracle_conn.py` queries existentes sem aprovação.** É o núcleo crítico (~3350 linhas) com todas as queries SQL. Funções aditivas (novas) que só LEEM são Categoria A. Funções aditivas que **escrevem** (INSERT/UPDATE/DELETE/MERGE) e alterações em queries existentes são **Categoria B**.
6. **NUNCA criar duplicatas.** Antes de criar função/método/bloco novo, verificar se já existe algo reutilizável no projeto.
7. **MANTER `.claude/dependencias_sankhya.md` atualizado.** IAgro está sendo modelado pra virar produto independente (spin-off). Toda nova **tabela Sankhya consumida**, **trigger detectada** (geralmente via ORA-XXXXX), **função/sequence proprietária**, **view customizada**, **tabela auxiliar AD_***, **constante de domínio nova** (TOP/CODNAT/STATUSNOTA/CODGRUPO) ou **regra invisível descoberta** precisa ser inserida nesse arquivo **antes/junto da implementação**. Esse documento é o blueprint pra recriar o schema necessário quando o IAgro desacoplar.

---

## Documentação modular

Os arquivos abaixo são carregados automaticamente como parte deste documento.

@.claude/rules.md
@.claude/architecture.md
@.claude/schema.md
@.claude/dependencias_sankhya.md
@.claude/conventions.md
@.claude/environment.md
@.claude/gotchas.md
@.claude/roadmap.md
@.claude/modules/entrada.md
@.claude/modules/classificacao.md
@.claude/modules/comercial.md
@.claude/modules/venda.md
@.claude/modules/rastreio.md
@.claude/modules/email.md
@.claude/modules/combustivel.md
@.claude/modules/relatorios.md
@.claude/modules/caixas.md
