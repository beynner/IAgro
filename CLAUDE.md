# CLAUDE.md — IAgro (NexusGTi)

> Referência principal para todas as sessões com o assistente.
> **Idioma de toda comunicação: Português Brasileiro.**

---

## Identidade

- **Nome:** IAgro
- **Versão:** 1.1.0
- **Tipo:** Sistema interno de gestão operacional integrado ao ERP Sankhya
- **Organização:** NexusGTi / HF Semear
- **Domínio:** Central de beneficiamento de produtos agrícolas (antigo "Packing House")

O sistema integra dados do Sankhya via Oracle e oferece **nove módulos operacionais**:

| Fluxo | TOP | Descrição |
|---|---|---|
| **Painel (Dashboard)** | — | Home com 6 indicadores de saúde (pedidos sem lote, lotes aguardando classif., vales abertos, tanques críticos, prontos pra faturar, lotes envelhecidos). Polling 5min |
| Entrada | 11 | Recebimento e conferência de notas de compra com pesagem |
| Classificação | 26 | Triagem de lotes por qualidade, com controle de descartes |
| Comercial | 13 | Faturamento de vales, precificação, geração de financeiro |
| Venda | 34 → 35/37 | Pedidos, edição de itens, faturamento (NFe ou s/ NFe), avaria (TOP 30) e devolução (TOP 36) |
| Rastreio (WMS) | — | Vínculo de lotes a pedidos com auditoria e lock pessimista. Suporta vínculo manual pedido↔nota órfã e pedido retroativo. **Etiquetas SafeTrace 100×50mm** com QR + EAN13 (Mai/2026 — Zebra ZD220) |
| E-mail (importação) | 34 (após confirmação) | Coleta IMAP de pedidos com PDF anexo, parser via LLM local (Ollama), revisão humana |
| Combustível (Frota) | 10 → 53 | Entrada de combustível (TOP 10) e requisições internas (TOP 53 — frota/maquinário/freteiro/posto externo). Discrimina frota própria + maquinário + freteiros. Inclui abastecimento externo (não desconta tanque interno) |
| **Auditoria Universal** | — | Tela `/sankhya/auditoria/` (restrita Diretoria/Suporte) consolidando AD_AUDITORIA_GERAL — todo evento de escrita do IAgro com snapshot antes/depois em JSON. 36 funções instrumentadas. Tela tem diff inteligente "antes→depois" + JSON técnico |

### Layout v2 — Sidebar + Content (Mai/2026)

Todas as telas autenticadas usam o **novo layout**: sidebar lateral fixa (200px expand / 56px collapse / off-canvas em ≤900px) + content-header (título + ações + user-badge + sair) + main-layout (área de conteúdo). Tela de login é standalone (`home_login.html`).

**Responsivo aplicado a todos os módulos** com breakpoints `1024 / 900 / 520px` — vide [`conventions.md`](.claude/conventions.md) → "Responsivo".

### Backlog planejado

- **Módulo Relatórios** — tela `/sankhya/relatorios/` ainda não iniciada. Backlog mapeado com 6 eixos (Financeiro / Vendas / Compras-Estoque / Rastreio-WMS / Combustível-Frota / Auditoria-Produtividade) e MVP recomendado de 5 relatórios. Detalhes em [`roadmap.md`](.claude/roadmap.md) → "Módulo Relatórios — Backlog planejado".

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

Estas são as seis regras inegociáveis. Detalhes e regras complementares em [`.claude/rules.md`](./.claude/rules.md).

1. **NUNCA alterar lógica de negócio** (queries Oracle, cálculos financeiros, regras de precificação, fluxo de faturamento) sem aprovação explícita do usuário.
2. **🛑 BLOQUEIO EXPLÍCITO — alteração de dados no banco (queries NOVAS e ANTIGAS).** Qualquer código que vá escrever no Oracle — **nova ou já existente** — usando INSERT/UPDATE/DELETE/MERGE/ALTER/DROP/TRUNCATE (em funções de service, DDL direta, ou views Sankhya **não** prefixadas por `AD_`/`ANDRE_IAGRO_`) **PARA** e exige aprovação ponto-a-ponto com plano detalhado: **o quê · como · por quê · o que afeta**. Vale para função aditiva nova *com* INSERT/UPDATE/DELETE também — apenas SELECT puro fica fora. Detalhes em [`rules.md`](./.claude/rules.md) regras #2 e #4.
3. **SEMPRE apresentar plano antes de agir.** Para qualquer alteração, listar todos os arquivos afetados e aguardar "sim" antes de executar. Marcar quais itens caem em Categoria B (regra #2/#4).
4. **APÓS plano aprovado, executar em modalidades:** Categoria A (frontend, funções aditivas, views `AD_*`, tests, docs) roda em **modo loop autônomo** (faz → testa → corrige → finaliza) sem reabrir aprovação. Categoria B (alteração de dados no banco, lógica de negócio, operações destrutivas) exige **pausa ponto-a-ponto**. Execução parcial sob demanda quando solicitada.
5. **NUNCA refatorar `oracle_conn.py` queries existentes sem aprovação.** É o núcleo crítico (~3350 linhas) com todas as queries SQL. Funções aditivas (novas) que só LEEM são Categoria A. Funções aditivas que **escrevem** (INSERT/UPDATE/DELETE/MERGE) e alterações em queries existentes são **Categoria B**.
6. **NUNCA criar duplicatas.** Antes de criar função/método/bloco novo, verificar se já existe algo reutilizável no projeto.

---

## Documentação modular

Os arquivos abaixo são carregados automaticamente como parte deste documento.

@.claude/rules.md
@.claude/architecture.md
@.claude/schema.md
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
