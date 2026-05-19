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

### Backlog planejado

- **Módulo Relatórios — MVP entregue em 2026-05-17** com 5 relatórios funcionando. Restam **20 relatórios** mapeados no backlog (6 eixos: Financeiro / Vendas / Compras-Estoque / Rastreio-WMS / Combustível-Frota / Auditoria-Produtividade) aguardando feedback operacional pra priorizar próximas iterações. Export Excel/PDF intencionalmente fora do MVP. Detalhes em [`roadmap.md`](.claude/roadmap.md) → "Módulo Relatórios — Backlog planejado" e em [`modules/relatorios.md`](.claude/modules/relatorios.md).

### Estratégia de produto (Mai/2026)

IAgro está sendo modelado pra virar **produto SaaS independente do Sankhya**, atendendo múltiplos clientes do agro com produtos diferentes (hortifrúti, grãos, carnes, defensivos, etc.). **Diretrizes:**

- **Schema núcleo permanece igual ao Sankhya** (TGFCAB, TGFITE, TGFPAR, TGFPRO, TSIEMP, etc.) — quando desacoplar, recriar mesmos nomes em banco próprio.
- **Tabelas auxiliares (`AD_*` ou `ANDRE_IAGRO_*`)** podem ser criadas livremente no banco atual — sem restrição.
- **Evitar adicionar colunas em tabelas Sankhya nativas** — preferir tabela auxiliar.
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
