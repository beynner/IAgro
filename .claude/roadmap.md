# Roadmap & Estado

Mapa vivo do projeto. Atualizar a cada marco.

---

## Módulos prontos para produção

Funcionam ponta-a-ponta. Tratáveis como concluídos após validação de `DEBUG=False` em ambiente real.

| Módulo | Estado | Notas |
|---|---|---|
| **Entrada (TOP 11)** | ✅ Concluído | Recebimento, conferência, pesagem, lote auto-gerado. Coberto em `test_views_entrada.py` |
| **Classificação (TOP 26)** | ✅ Concluído | Triagem por qualidade, descartes via `AD_QTDAVARIA`. **Sem cobertura dedicada** (pendência) |
| **Comercial (TOP 13)** | ✅ Concluído | Faturamento de vales, precificação, financeiro em TGFFIN, simulações em SQLite. Coberto em `test_views_comercial.py` |
| **Venda — núcleo (TOP 34)** | ✅ Concluído | Criar/editar/excluir cabeçalho; adicionar/editar/remover item. UX para não-tech (resumo, dedup, empty state, CODNAT dropdown). 90 testes |
| **Venda — faturamento (34→35/37)** | ✅ Concluído | Lock pessimista, validação de itens com lote, NUMNOTA por empresa, `CODNAT_POR_TOP`. **Não dispara emissão real de NFe** (decisão consciente — Sankhya cuida) |
| **Rastreio — atribuição/desvinculação** | ✅ Concluído | View `ANDRE_IAGRO_SALDO_LOTE` (5 pernas), filtros cruzados opt-in, lock pessimista, `RastreioAudit` em SQLite |
| **Rastreio — UI/UX** | ✅ Concluído | Paleta sóbria alinhada ao `home.css` (verde Agromil + marrom + accent) |
| **Robustez geral** | ✅ Concluído | `humanizar_erro_oracle()`, atomicidade transacional, `@ensure_csrf_cookie`, `IAgro.confirmarAcao()` |
| **Helpers JS reutilizáveis** | ✅ Concluído | `confirmarAcao`, `cachedFetch`, `postJSON`, `showToast`, `debounce`, `getCookie` |
| **Healthcheck profundo** | ✅ Concluído | `/sankhya/health/?deep=1` valida ping Oracle, view do WMS, contagem de TOP 34 |
| **Venda — UX dos filtros** (sessão Abr/2026) | ✅ Concluído | Card lateral `#cardFiltros` com todos os campos + chips de filtros ativos + typeahead de Empresa + persistência em `localStorage` (chave `iagro:venda:filtros:v1`) + refino cosmético no input de Lote (placeholder/title) |
| **Importação de pedidos por e-mail** (sessão Mai/2026) | ✅ Código concluído · ⚠ Setup quase completo | Worker IMAP (Titan), parser LLM local (Ollama + **Qwen 2.5 14B** — subido de 7B após confirmar hardware do servidor), 8 endpoints, tela de revisão e promoção para TGFCAB TOP 34 reusando APIs da Venda. **DDL aplicada, pastas IMAP criadas, Ollama 0.23.0 + 14B instalados no servidor (Cenário A — `OLLAMA_HOST=localhost:11434`).** Falta apenas: criar venv no servidor + `pip install`, preencher `EMAIL_IMAP_PASS`, agendar Task Scheduler. **56 testes novos (174 → 230).** |

---

## Módulos em andamento

Parcialmente implementados ou que dependem de decisão externa.

| Item | O que existe | O que falta | Próximo passo |
|---|---|---|---|
| **Emissão real de NFe (TOP 35)** | Pedido marcado faturado em TGFCAB com `STATUSNOTA='L'`, NUMNOTA gerado | Disparo real da emissão via webservice/API do Sankhya | **Decisão de negócio:** (a) automático após faturar, (b) manual no Sankhya (estado atual), (c) job batch periódico |
| **Vínculo lote ↔ item dentro do modal de Venda** | Item da Venda com `CODAGREGACAO=NULL`; vínculo no Rastreio | Typeahead dinâmico no modal de itens da Venda filtrando por saldo de lote | **Recomendação:** manter fluxo atual — Venda → Rastreio é suficiente |
| **Avaria interna como linha separada (Opção B)** | Perna D existe na view; UI mostra como badge inline vermelho (Opção A) | Renderizar como linha não-vendável separada | Trocar 1 filtro no front em `renderLotes` (~30 min) |
| **Cobertura services do Rastreio** | Indireta via mocks (53 testes) + diretos para `atribuir_lote_item_pedido` e `faturar_pedido_venda_banco` | Testes diretos de `consultar_vinculos_de_lote`, `consultar_fabricantes_disponiveis`, `desvincular_lote_item_pedido`, `consultar_saldo_lote_disponivel` | Replicar padrão do `AtribuirLoteServiceTest` |
| **WhiteNoise / `DEBUG=False` em produção** | Versão 1.2.0, healthcheck profundo, paleta visual fechada | Validar `collectstatic`, ativar WhiteNoise em `MIDDLEWARE`, configurar `STATIC_ROOT` | Subir em homologação com `DEBUG=False` e validar JS/CSS |
| **Typeahead de Lote no portal Venda** | Refino cosmético aplicado (placeholder "Código do lote" + title explicativo). Busca livre por `LIKE` com debounce 500ms | Typeahead real exigiria nova função em `oracle_conn.py` (`SELECT DISTINCT CODAGREGACAO FROM TGFITE WHERE...`) — bloqueado pela **regra crítica #4** | Decisão de negócio: vale o custo? `SELECT DISTINCT` em tabela grande sem índice dedicado pode ser caro |

---

## Pendências (ainda não iniciadas)

| # | Item | Esforço | Dependência |
|---|---|---|---|
| 1 | Manual operacional para usuários não-tech (fluxo de Venda + Rastreio com screenshots) | 1-2 dias | Tela final aprovada |
| 2 | Configuração formal de produção (`.env.dev` + `.env.prod`, nginx ou WhiteNoise, HTTPS, `SECURE_*`) | 1 dia | Servidor real disponível |
| 3 | Substituir `ControleInatividadeMiddleware` por timeout nativo (`SESSION_COOKIE_AGE` + `SESSION_SAVE_EVERY_REQUEST`) | 2 horas | — |
| 4 | Cobertura de testes da Classificação | 1 dia | — |
| 5 | Refator do CSS legado: separar `entrada.css` em `base-layout.css` (global) + `entrada.css` (específico) | 4 horas | Auditoria visual após split |
| 6 | Unificar `@keyframes` locais (`spin`, `iaspin`, `toastSlideIn/Out`) com nomes globais (`ia-girar`, `ia-toast-entrada/saida`) | 2 horas | Atualizar referências em JS |
| 7 | CSRF nas views POST com JSON: validar token sendo enviado corretamente pelo frontend | 2 horas | — |

---

## Ordem de Prioridade Recomendada

Sequência otimizada para chegar à produção rápido sem dívidas críticas.

| Prioridade | Item | Justificativa |
|:---:|---|---|
| **P0** | Decisão de NFe (módulo em andamento #1) | Bloqueia produção |
| **P0** | Configuração formal de produção (pendência #2) | Bloqueia produção |
| **P1** | Manual operacional (pendência #1) | Onboarding de operadores |
| **P1** | Cobertura services do Rastreio (em andamento #4) e Classificação (pendência #4) | Dívida de testes |
| **P2** | Avaria interna como linha separada (em andamento #3) | Pequena melhoria UX |
| **P2** | Substituir `ControleInatividadeMiddleware` (pendência #3) | Limpeza arquitetural |
| **P3** | Refator CSS legado (pendências #5 e #6) | Limpeza sem ganho funcional |

**Caminho mínimo para produção:** completar P0. Restante pode entrar em releases incrementais.

---

## Decisões Técnicas Tomadas (preservar)

Decisões debatidas e aprovadas. **Não revisar sem discussão prévia.**

### Arquitetura e dados

- **Filtro cruzado em dois eixos** (Rastreio): `checksLotes: Set<codprod>` + `checksPorPedido: Map<NUNOTA, Set<codprod>>`. Marcar produto X num pedido **não cascatea** para outros pedidos com o mesmo produto.
- **Filtro cruzado é opt-in via checkbox**, nunca por click direto na linha. Ações invasivas exigem gesto explícito.
- **`CODNAT_POR_TOP`** centralizado em `oracle_conn.py`: `{34: 10010100, 35: 10010100, 37: 10010200}`.
- **Audit log do Rastreio em SQLite (`RastreioAudit`)**, não em tabela Oracle — separa telemetria da base de produção do ERP.
- **`humanizar_erro_oracle`** intercepta `ORA-XXXXX` e devolve frase amigável. Operador nunca vê stack trace. Mensagem técnica vai para `logger.exception` somente.
- **Lock pessimista (`SELECT ... FOR UPDATE`)** em `atribuir_lote_item_pedido` e `faturar_pedido_venda_banco` — defesa contra race conditions.
- **Atomicidade transacional explícita** em todas as views de escrita: `try/except → conn.rollback() → raise` dentro do `with obter_conexao_oracle()`.
- **Não emitir NFe automaticamente** após faturar — apenas marca `STATUSNOTA='L'`. Emissão real é responsabilidade do Sankhya. **Mantém domínio do ERP intocado.**
- **Lote no IAgro vive em `CODAGREGACAO`** (VARCHAR2), nunca em `CONTROLE`. Auto-gerado na Entrada (`NUNOTAS{SEQ}D{YYMMDD}`); livre na Venda; NULL em item de Venda até atribuição pelo Rastreio. Doc `.claude/schema.md` foi corrigida em Abr/2026 (entrada `CONTROLE` removida).
- **Pré-pedidos vindos de e-mail vivem em tabelas auxiliares Oracle (`AD_PEDIDO_EMAIL_RECEBIDO` + `AD_PEDIDO_EMAIL_ITEM`), não em SQLite nem em TGFCAB com TOP novo** (Mai/2026). Razão: backup unificado, joinable com TGFCAB via `NUNOTA_GERADO`, mas sem poluir queries existentes. **TGFCAB recebe INSERT só após confirmação humana**, reusando 100% das APIs da Venda.
- **Parser de PDF de pedido roda em LLM local (Ollama + Qwen 2.5 14B)**, nunca em API cloud (Mai/2026). Razão: dados de cliente não saem da máquina (LGPD/privacidade). Trade-off aceito: ~82-90% acurácia vs ~90-95% do cloud, com operador corrigindo na revisão. **Decisão revista no mesmo mês**: subido de 7B → 14B após confirmar que o servidor de produção (Xeon E5-2680 v4 + 64GB RAM) comporta com folga. Custo de tempo irrelevante no volume típico (5 PDFs/dia × ~80s = 7 min/dia). 32B disponível como opção experimental sem trocar default — `ollama pull qwen2.5:32b-instruct` e ajustar `OLLAMA_MODELO` no `.env` temporariamente.
- **Conta IMAP de pedidos:** `comercial@agromilagrocomercial.com.br` (Titan/Hostinger). **Pastas com hífen** (`Pedidos-Entrada`, `Pedidos-Processados`, `Pedidos-Erros`) — Titan trata como literal, sem nesting.

### UX e visual

- **Paleta sóbria alinhada ao `home.css`:** `--ras-primary: #5e7e4a` (verde Agromil), `--ras-secondary: #825e38` (marrom), `--ras-accent: #38292c`. **Não usar gradientes saturados (azul→roxo).**
- **POR PARCEIRO ordenação:** data **ASC** + parceiro ASC (mostra "fila de pedidos a atender" cronologicamente).
- **POR PRODUTO ordenação:** data DESC + parceiro ASC.
- **Default colapsado:** todo grupo começa fechado. `pedidosJaVistos` / `gruposProdutoJaVistos` rastreiam quais já foram inicializados para preservar escolha do usuário em refresh/scroll.
- **Click na linha não marca o checkbox** — linha vira **selecionada** (revela botões 🔗/👁); checkbox tem listener próprio.
- **Botões de ação ocultos por padrão**, revelam-se com hover (opacity 0.55) ou seleção da linha (cresce de 26→32 com transition cubic-bezier "spring"). Reduz ruído visual em listas longas.
- **Bar "Lote armado"** no rodapé (`position: fixed; bottom: 36px`), não no topo. Visível durante scroll, fora do caminho de leitura.
- **Modais de confirmação custom** (`IAgro.confirmarAcao`) substituem `window.confirm()` em ações destrutivas.
- **Filtros da Venda vivem no card lateral `#cardFiltros`** (Abr/2026). Tentativa de mover para o header inline foi revertida por conflito visual: tirava espaço útil da tabela e poluía o cabeçalho. Padrão aprovado: form na lateral + chips de filtros ativos no rodapé do mesmo card + botões Atualizar/Limpar.

### Frontend

- **JS puro, sem framework.** Decisão histórica do projeto. Helpers em `iagro_helpers.js` cobrem o que precisaria de framework (cache, debounce, modal).
- **Avatar de fornecedor/produto com cor por hash do nome** — mesmo nome sempre mesma cor. Estável entre sessões e fácil de escanear visualmente.
- **`:has()` CSS** para estilização dependente de checkbox. Requer browser moderno (Chrome 105+, Safari 15.4+, Firefox 121+).
- **Persistência de preferências de filtro em `localStorage` com chave versionada** (Abr/2026). Venda usa `iagro:venda:filtros:v1`; Rastreio usa `iagro:rastreio:prefs:v1`. Padrão: salvar a cada `carregarVendas(false)` (ou equivalente), restaurar no boot, botão Limpar apaga o storage. Ao mudar formato de qualquer chave: **bumpar a versão** (`v2`) ou adicionar migração leve no carregar.
- **Typeahead de Lote no portal Venda foi descartado por agora** (Abr/2026). Refino apenas cosmético no input (placeholder "Código do lote" + title explicando `CODAGREGACAO` no formato `NUNOTAS{SEQ}D{YYMMDD}`). Razão: typeahead exigiria nova função em `oracle_conn.py`, bloqueada pela regra crítica #4.
