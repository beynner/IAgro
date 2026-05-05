# CLAUDE.md — IAgro (NexusGTi)

> Referência principal para todas as sessões com o assistente.
> **Idioma de toda comunicação: Português Brasileiro.**

---

## Identidade

- **Nome:** IAgro
- **Versão:** 1.2.0
- **Tipo:** Sistema interno de gestão operacional integrado ao ERP Sankhya
- **Organização:** NexusGTi / HF Semear
- **Domínio:** Central de beneficiamento de produtos agrícolas (antigo "Packing House")

O sistema integra dados do Sankhya via Oracle para controlar cinco fluxos:

| Fluxo | TOP | Descrição |
|---|---|---|
| Entrada | 11 | Recebimento e conferência de notas de compra com pesagem |
| Classificação | 26 | Triagem de lotes por qualidade, com controle de descartes |
| Comercial | 13 | Faturamento de vales, precificação, geração de financeiro |
| Venda | 34 → 35/37 | Pedidos, edição de itens, faturamento (NFe ou s/ NFe) |
| Rastreio (WMS) | — | Vínculo de lotes a pedidos com auditoria e lock pessimista |
| E-mail (importação) | 34 (após confirmação) | Coleta IMAP de pedidos com PDF anexo, parser via LLM local (Ollama), revisão humana |

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

Estas são as cinco regras inegociáveis. Detalhes e regras complementares em [`.claude/rules.md`](./.claude/rules.md).

1. **NUNCA alterar lógica de negócio** (queries Oracle, cálculos financeiros, regras de precificação, fluxo de faturamento) sem aprovação explícita do usuário.
2. **SEMPRE apresentar plano antes de agir.** Para qualquer alteração, listar todos os arquivos afetados e aguardar "sim" antes de executar.
3. **EXECUTAR uma tarefa por vez** e aguardar confirmação antes de avançar.
4. **NUNCA refatorar `oracle_conn.py` sem aprovação.** É o núcleo crítico (~3350 linhas) com todas as queries SQL. Funções aditivas são aceitáveis; alteração de queries existentes pode quebrar produção.
5. **NUNCA criar duplicatas.** Antes de criar função/método/bloco novo, verificar se já existe algo reutilizável no projeto.

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
