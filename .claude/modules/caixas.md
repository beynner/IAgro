# Módulo Controle de Caixas (Vasilhame Retornável)

Controle de circulação de caixas plásticas entre Agromil e clientes. Saídas derivadas em runtime das vendas via `CEIL(QTDNEG / TGFITE.PESO)` quando peso populado; coletas/quebras/perdas registradas manualmente; ajustes excepcionais via motivo dedicado; produtos de papelão excluídos via cadastro explícito.

Lançado Mai/2026 (2026-05-18) — Cat A + Cat B (DDLs + B1/B2/B3 + AJUSTE_SALDO) **em produção**.

> **Decisão de Mai/2026 (2026-05-18)**: descoberto que `CODVOL='CX'` na Agromil **não** significa "QTDNEG é nº de caixas" — sempre kg. Tentamos tabela `AD_PESO_CAIXA_PRODUTO` pra cadastrar peso default por produto, mas peso varia por lote (tomate 20 ou 22 kg). Reverter e **esperar IAgro virar fluxo único** — assim vendas trazem PESO real do Rastreio.

---

## Premissa Arquitetural

**Saídas e devoluções não são persistidas.** São calculadas em runtime a partir de TGFITE TOP 35/37 'L' (saída) e TOP 36 'L' (devolução), usando `CEIL(QTDNEG / PESO)` por linha. Mesma fórmula da etiqueta SafeTrace — garante consistência: a quantidade de etiquetas que sai com o pedido é exatamente a quantidade que aparece como "caixas enviadas" no controle.

**Coletas, quebras e perdas vivem em `AD_COLETA_CAIXAS`.** Soft-delete via `ESTORNADO='S'` preserva audit. Operador estorna lançamentos errados sem perder histórico.

**Tipos de caixa em `AD_PRODUTO_CAIXA`.** Mapeamento CODPROD → `PLASTICA` (retornável) | `PAPELAO` (descartável). Produto SEM linha = `PLASTICA` por default. Operador cadastra só as exceções (mudas, embalagens pequenas).

---

## Escopo

- **Saldo por cliente**: lista clientes com caixas em campo, ordenado por saldo DESC
- **Timeline por cliente**: eventos cronológicos (saídas + devoluções + coletas/quebras/perdas/ajustes) DESC
- **Lançamento manual de coleta**: data, qtd, motivo (COLETA/QUEBRA/PERDA/AJUSTE_SALDO), observação
- **Ajuste de saldo**: motivo `AJUSTE_SALDO` permite qtd positiva (caixa apareceu / saldo inicial) **ou negativa** (caixa sumiu sem motivo registrado). Uso excepcional — saldo deve bater pela operação normal
- **Estorno de coleta**: soft-delete preservando audit
- **Cadastro de tipo de caixa por produto**: marca produtos de papelão pra não contar saldo
- **Indicadores agregados**: caixas em campo total, clientes com saldo, quebradas/perdidas

---

## URL e acesso

| Rota | Método | Propósito |
|---|---|---|
| `/sankhya/caixas/` | GET | Página HTML |
| `/sankhya/caixas/api/saldo/` | GET | Saldo por cliente (filtros: `q`, `apenas_saldo_positivo`, `codparc`) |
| `/sankhya/caixas/api/timeline/<codparc>/` | GET | Timeline cronológica do cliente (`?dias=N`, default 90, max 730) |
| `/sankhya/caixas/api/coletas/` | GET | Listagem paginada de coletas (filtros: codparc, motivo, datas) |
| `/sankhya/caixas/api/produtos/` | GET | Cadastro AD_PRODUTO_CAIXA (filtro `?tipo=PLASTICA\|PAPELAO`) |
| `/sankhya/caixas/api/coleta/criar/` | POST | **Cat B1 — stub 501** |
| `/sankhya/caixas/api/coleta/<id>/estornar/` | POST | **Cat B2 — stub 501** |
| `/sankhya/caixas/api/produto/upsert/` | POST | **Cat B3 — stub 501** |

**Acesso:** Grupos `1, 6, 8, 9, 10, 11` (decorator `@exige_grupo('caixas')`) — quase todos os grupos operacionais. Logística é multidisciplinar.

---

## Tabelas auxiliares

DDLs em `sankhya_integration/sql/`:
- [`AD_COLETA_CAIXAS.sql`](../../sankhya_integration/sql/AD_COLETA_CAIXAS.sql)
- [`AD_PRODUTO_CAIXA.sql`](../../sankhya_integration/sql/AD_PRODUTO_CAIXA.sql)

Estrutura completa em `.claude/schema.md` §7.8.

**Pendente de aplicação no Oracle (Cat B):** as duas tabelas + sequence `SEQ_AD_COLETA_CAIXAS` + 2 índices. Backend funciona schema-resilient — `consultar_saldo_caixas` cai em fallback (só saídas − devoluções) enquanto AD_COLETA_CAIXAS não existir.

---

## Funções service (`oracle_conn.py`)

### Cat A — leituras (entregues)

| Função | Operação |
|---|---|
| `consultar_saldo_caixas(filtros)` | Saldo agregado por CODPARC. 3 SELECTs (saídas + devoluções + coletas) combinados em Python |
| `obter_timeline_caixas(codparc, dias)` | Timeline DESC. LISTAGG produtos por dia/NUNOTA |
| `listar_coletas_caixas(filtros, limite, offset)` | Paginação ROW_NUMBER + JOIN TGFPAR |
| `listar_produtos_caixa(tipo?)` | Cadastro com JOIN TGFPRO |

Todas tolerantes a falha do Oracle (retornam lista vazia + `logger.exception`) e schema-resilient via `_existe_coluna(cur, 'AD_COLETA_CAIXAS', 'ID')`.

### Cat B — escritas (pendentes)

| Função | Operação |
|---|---|
| `criar_coleta_caixas_banco(dados, codusu, nomeusu)` | INSERT em AD_COLETA_CAIXAS + audit. Valida codparc existe em TGFPAR, qtd > 0, motivo no enum |
| `estornar_coleta_caixas_banco(id_coleta, motivo, codusu, nomeusu)` | UPDATE ESTORNADO='S' (soft-delete) — preserva linha |
| `upsert_produto_caixa_banco(codprod, tipo_caixa, codusu, nomeusu)` | MERGE em AD_PRODUTO_CAIXA. Valida codprod existe em TGFPRO |

---

## Frontend

### Arquivos

| Arquivo | Função |
|---|---|
| `templates/sankhya_integration/caixas.html` | Layout 2 abas + 2 colunas + 2 modais |
| `static/sankhya_integration/caixas.css` | Tokens globais + paleta verde Agromil |
| `static/sankhya_integration/caixas.js` | IIFE com state, fetchers, renderers, modais |

### Layout

- **Header de resumo (topo)**: 4 cards (caixas em campo, clientes c/ caixa, quebradas 30d, perdidas 30d)
- **Abas**: Saldo por cliente (default) | Tipo de caixa por produto
- **Aba Saldo**: grid 2 colunas
  - Esquerda: filtros (busca + toggle "incluir zerados") + lista de cards `cliente / saldo`
  - Direita: detalhe do cliente selecionado — header com saldo grande + 5 stats (enviadas/devolvidas/coletadas/quebradas/perdidas) + timeline cronológica
- **Aba Produtos**: tabela com filtro de tipo + botão "Cadastrar produto" que abre modal com typeahead de produto + radio PLASTICA/PAPELAO

### Modais

1. **Lançar coleta** (B1 stub): typeahead parceiro + data + qtd + radio motivo (COLETA/QUEBRA/PERDA) + observação
2. **Cadastrar produto-caixa** (B3 stub): typeahead produto (hortifrúti, `grupo_inicia_com=1`) + radio PLASTICA/PAPELAO

Ambos tratam resposta 501 com `pendente_cat_b: true` exibindo mensagem amigável ("Backend de escrita ainda pendente. Aguarda aprovação Cat B.").

### Cores e ícones (Phosphor)

| Tipo | Cor | Ícone |
|---|---|---|
| Saída | `#5e7e4a` verde Agromil | `ph-arrow-up-right` |
| Devolução TOP 36 | `#0891b2` ciano | `ph-arrow-down-left` |
| Coleta | `#0891b2` ciano | `ph-truck` |
| Quebra | `#d97706` âmbar | `ph-warning` |
| Perda | `#dc2626` vermelho | `ph-x-circle` |
| Ajuste de saldo | `#6366f1` indigo | `ph-pencil-simple` |

---

## Decisões de regra de negócio

1. **Caixa = caixa plástica retornável.** Caixa de papelão é descartável e não entra no cálculo de saldo. Operador cadastra explicitamente os produtos que vão em papelão (mudas, etc).
2. **Default é PLASTICA**: produto SEM linha em `AD_PRODUTO_CAIXA` é tratado como plástica. Reduz custo de cadastro inicial (cadastra só exceções, ~5-10 produtos).
3. **Devolução TOP 36 desconta caixa do saldo automaticamente.** A devolução de mercadoria volta junto com a caixa — não precisa lançamento manual paralelo. Exceção: produtos PAPELAO não contam (caixa não voltaria mesmo).
4. **Granularidade por CODPARC, não por CODPARCMATRIZ.** Assaí Ceilândia (cliente A) e Assaí Taguatinga (cliente B) têm saldos separados — caixa fica na loja física específica.
5. **Quebra ≠ Perda, mas ambas descontam saldo.** Quebra é caixa que voltou mas foi descartada. Perda é caixa que não voltou. Operador escolhe o motivo no modal pra preservar a informação. Política de cobrança virá depois (precisamos dos dados primeiro pra decidir).
6. **Saídas calculadas em runtime, não persistidas.** Fórmula: `CEIL(QTDNEG / TGFITE.PESO)` quando `PESO > 0`. **Descoberto Mai/2026 (2026-05-18 — diagnóstico Nota 6361 UNIAO)**: `CODVOL='CX'` na Agromil NÃO significa "QTDNEG é nº de caixas". QTDNEG está sempre em kg (mesmo em vendas marcadas CX). Vendas IAgro recentes (via Rastreio) têm PESO populado no modal de vínculo → calcula automaticamente. Vendas legadas (faturadas direto no Sankhya, ~99% do volume hoje) ficam fora do cálculo → operador usa **AJUSTE_SALDO** pra controlar saldo de clientes importantes (Assaí/Sendas). Tentamos cadastro de peso default por produto (`AD_PESO_CAIXA_PRODUTO`) — descartado porque peso varia por lote (tomate 20 ou 22).
7. **AJUSTE_SALDO é motivo único pra correção excepcional.** Cobre saldo inicial (caixas que já estavam em campo quando o controle começou) E ajustes pontuais (saldo divergiu da realidade). Qtd pode ser positiva (caixa apareceu) ou negativa (caixa sumiu sem motivo). Não é pra uso diário — saldo deve bater pela operação normal. Observação obrigatória no frontend pra forçar audit explicativo.
8. **Soft-delete em coleta (ESTORNADO='S')**, não DELETE físico. Audit preservado pra investigar lançamentos suspeitos depois.
9. **Cliente sem vendas mas com AJUSTE_SALDO entra no resultado** — caso típico de "começou o controle hoje, esse cliente tem 80 caixas em campo do controle antigo". Resultado mostra `caixas_enviadas=0, caixas_ajuste=80, saldo=80`.
10. **Acesso amplo (1/6/8/9/10/11)**: caixa é logística transversal — Comercial precisa pra negociar, Administrativo pra coletar, Frota pra rotear, Packing pra preparar carga. Auditoria e cadastros restritos via Cat B (futuro: pode haver guard adicional pra estornar).
11. **Schema-resilient via `_existe_coluna`**: backend funciona antes de aplicar DDL. Quando AD_COLETA_CAIXAS não existe, retorna só saídas − devoluções (saldo "sujo" mas não quebra).

---

## Cat B pendente — plano de aprovação ponto-a-ponto

Para destravar escritas e fechar o módulo:

### B0 — Aplicar DDLs no Oracle

```sql
@AD_COLETA_CAIXAS.sql      -- tabela + sequence + 2 índices + 4 comentários
@AD_PRODUTO_CAIXA.sql      -- tabela + 3 comentários
```

**O que afeta:** zero impacto em queries existentes (tabelas isoladas). Necessário pra B1/B2/B3 funcionarem.

### B1 — `criar_coleta_caixas_banco(dados, codusu, nomeusu)`

INSERT em `AD_COLETA_CAIXAS` com `verificar_permissao_escrita()` no topo, validações (codparc existe em TGFPAR, qtd > 0, motivo no enum, data não-futura), audit via `registrar_auditoria`, retorna `{ok: True, id: <novo_id>}`.

### B2 — `estornar_coleta_caixas_banco(id_coleta, motivo_estorno, codusu, nomeusu)`

UPDATE `AD_COLETA_CAIXAS SET ESTORNADO='S', ESTORNADO_EM=SYSTIMESTAMP, ESTORNADO_POR=:codusu, MOTIVO_ESTORNO=:motivo WHERE ID=:id AND ESTORNADO='N'`. Audit via `registrar_auditoria`.

### B3 — `upsert_produto_caixa_banco(codprod, tipo_caixa, codusu, nomeusu)`

`MERGE INTO AD_PRODUTO_CAIXA USING DUAL ON (CODPROD=:c) WHEN MATCHED THEN UPDATE SET TIPO_CAIXA=:t, ATUALIZADO_EM=SYSTIMESTAMP, ATUALIZADO_POR=:codusu WHEN NOT MATCHED THEN INSERT (CODPROD, TIPO_CAIXA, CODUSU, NOMEUSU) VALUES (:c, :t, :codusu, :nomeusu)`. Audit via `registrar_auditoria`.

---

## Tests

`test_caixas.py` — **31 tests** mockados (zero dependência de Oracle real):

| Classe | Cobertura |
|---|---|
| `AcessoCaixasTest` | 6 grupos permitidos + 1 sem sessão |
| `ConsultarSaldoCaixasServiceTest` | Saldo básico + zerados + schema-resilient + falha Oracle + drill-down codparc |
| `ObterTimelineCaixasServiceTest` | Sem codparc → vazio + eventos combinados + falha Oracle |
| `ListarColetasCaixasServiceTest` | Lista paginada + sem tabela |
| `ListarProdutosCaixaServiceTest` | Filtro tipo + sem tabela |
| `ApiCaixasSaldoViewTest` | Padrão + codparc inválido 400 + sem sessão |
| `ApiCaixasTimelineViewTest` | Payload com dias + default 90 + clipado 730 |
| `ApiCaixasColetasListarViewTest` | Payload |
| `ApiCaixasProdutosListarViewTest` | Filtro tipo + tipo inválido vira None |
| `StubsCatBCaixasTest` | B1/B2/B3 retornam 501 com `pendente_cat_b: true` |

621 tests total na suíte, 15 falhas pré-existentes (= baseline antes do módulo = zero regressão).

---

## ⏸ Decisão pendente — embalagem variável por (produto × cliente)

**Levantado em 2026-05-18** após cliente operacional (Agromil) confirmar que **a embalagem da venda não é fixa por produto** — varia por combinação `(produto × cliente/região)` e ocasionalmente muda no dia (faltou madeira, saiu plástica).

### Casos reais conhecidos

- **REPOLHO BRANCO/ROXO** → Palmas Teotônio e Araguaína: **caixa de madeira** (não conta no saldo) · Assaí DF: **plástica** (conta)
- **ABÓBORA JAPONESA** → fora do DF: **saco** (não conta) · Assaí DF: **plástica** (conta)
- Outros produtos seguem default global (PLÁSTICA pra hortifrúti, PAPELÃO pra mudas)

O cadastro atual `AD_PRODUTO_CAIXA(CODPROD, TIPO_CAIXA)` é **global por produto** — não cobre essa variação por cliente.

### 3 caminhos propostos (com tradeoffs)

| Opção | Esforço | Precisão | Cobre exceção pontual? |
|---|---|---|---|
| **A — Cadastro `(produto × cliente)`** com prioridade sobre o global. Enum expandido pra `PLASTICA / PAPELAO / MADEIRA / SACO` | ~2h | Boa pra ~90% dos casos | Não — operador usa AJUSTE_SALDO |
| **B — Campo no modal de Venda** (select por item, default vindo de A) | ~3h | Boa quando preenchido | Sim, mas depende do operador lembrar (falha humana frequente) |
| **C — Confirmação na expedição** (tela bulk: "este pedido saiu com N caixas plásticas") | ~6h | Máxima — dado vem da operação física | Sim por design (operador conta caixas reais) |

### Recomendação atual

**Começar pela A**, observar 2-3 semanas. Se aparecer muito AJUSTE_SALDO manual recorrente, **escalar pra C**.

Desaconselhado **B**: select com default no modal é o "esquece" mais comum em qualquer sistema — operador clica avançar sem trocar.

### Estado de implementação

**Nenhum dos 3 caminhos implementado ainda.** Voltar a esse ponto quando o operador decidir qual opção quer começar. Por enquanto:
- Cadastros globais (`AD_PRODUTO_CAIXA`) cobrem só PLÁSTICA vs PAPELÃO
- Casos REPOLHO+Palmas/Araguaína e ABÓBORA JAPONESA fora do DF estão sendo contados erroneamente como plástica → operador precisa fazer AJUSTE_SALDO manual nos clientes afetados pra compensar
- Decisão pendente registrada aqui em 2026-05-18
