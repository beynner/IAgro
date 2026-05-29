# Regras Permanentes de Desenvolvimento

Estas regras se aplicam a **todas** as sessões, sem exceção. Violar qualquer uma delas requer aprovação explícita do usuário.

> 🛑 **BLOQUEIO EXPLÍCITO — alteração de dados no banco (queries novas E antigas).**
> Qualquer código que vá **escrever no Oracle** — **nova ou já existente** — usando
> `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `ALTER`, `DROP`, `TRUNCATE` (em funções
> de service, DDL direta ou views Sankhya não-prefixadas por `AD_`/`ANDRE_IAGRO_`)
> **PARA** e exige aprovação ponto-a-ponto com plano detalhado:
> **o quê · como · por quê · o que afeta**.
>
> Vale para função aditiva nova *com* INSERT/UPDATE/DELETE também — não só
> alteração de query existente. Apenas funções de leitura pura (SELECT) e views
> custom `AD_*`/`ANDRE_IAGRO_*` ficam fora do bloqueio.
>
> Detalhes na regra #4 (Categoria B). Para histórico da versão anterior dessas
> regras, ver [`rules_v1_pre_loop_mode.md`](rules_v1_pre_loop_mode.md).

---

## 1. Reuso antes de criar

**Antes de criar qualquer função, método ou bloco de código novo**, verificar se existe algo reutilizável no projeto.

- Buscar por nomes similares em `oracle_conn.py`, `views.py`, `iagro_helpers.js`, `global.css`.
- Se houver lógica semelhante, apontar e sugerir consolidação em vez de duplicar.
- Helpers JS centrais ficam em `iagro_helpers.js` sob `window.IAgro`.
- Tokens de design ficam em `global.css` (variáveis com nomes em português).

---

## 2. Lógica de negócio e alteração de dados são intocáveis (sem aprovação ponto-a-ponto)

**NUNCA alterar sem aprovação explícita item-a-item:**

### Alteração de dados no banco — queries NOVAS e ANTIGAS

- Qualquer função em `oracle_conn.py` (ou qualquer outro service) que execute `INSERT`, `UPDATE`, `DELETE`, `MERGE` no Oracle — **seja função existente sendo modificada, seja função aditiva nova sendo criada**
- DDL direta aplicada no Oracle real (`ALTER TABLE`, `DROP TABLE`, `TRUNCATE`, `CREATE/REPLACE` em **tabelas Sankhya nativas**)
  - **Atualizado 2026-05-21:** `ALTER TABLE` em tabela Sankhya nativa **adicionando coluna `AD_<NOME>`** é PERMITIDO (continua exigindo aprovação Cat B ponto-a-ponto). Antes de propor, **ler** sempre se o dado já existe em campo nativo ou tabela auxiliar Sankhya (ex.: TGFVOA, TGFEXC). Detalhes da diretriz em `CLAUDE.md` → "Estratégia de produto"
- `CREATE TABLE` ou `CREATE SEQUENCE` mesmo que prefixados com `AD_` (DDL nova em produção)
- **Views Oracle não-prefixadas por `AD_` ou `ANDRE_IAGRO_`** (qualquer view Sankhya nativa)
- Rodar scripts smoke `_apply_*.py` que aplicam DDL em produção
- Operações destrutivas em git/produção (`git reset --hard`, `push --force`, deleção massiva, `rm -rf`)

### Lógica de negócio
- Cálculos financeiros (preço, total, recalculo de notas)
- Regras de precificação e negociação
- Fluxo de faturamento (TOP 34 → 35/37, geração de `NUMNOTA`, `CODNAT_POR_TOP`)
- Validações de saldo de lote, lock pessimista, atomicidade transacional
- Auto-cura de `AD_NUMPEDIDOORIG` em `inserir_item_nota_banco`
- Trigger Sankhya `TGFVAR` (escrever pode disparar cascata `TGMTRA` — gotcha conhecido; exceção documentada do módulo Devolução TOP 36)

Se a tarefa parece exigir mudança nesses pontos, **parar e perguntar** apresentando o formato da regra #4 → Categoria B.

### O que NÃO cai aqui (permitido em modo loop após plano aprovado)

- **Funções aditivas (novas) em `oracle_conn.py` que apenas LEEM** (SELECT puro — sem INSERT/UPDATE/DELETE/MERGE). Função nova que escreve é Categoria B mesmo sendo aditiva.
- **`CREATE OR REPLACE VIEW` em views Oracle prefixadas com `AD_` ou `ANDRE_IAGRO_`** (são nossas custom — ex: `ANDRE_IAGRO_SALDO_LOTE`). View custom é estrutura de consulta, não escrita de dados.
- Frontend (HTML/CSS/JS), tests, docs, comentários, refatoração que preserva comportamento, views Django, urls, decorators, helpers.

---

## 3. Plano antes de agir (sempre obrigatório)

Para qualquer alteração de código:

1. Apresentar **lista completa** dos arquivos que serão modificados.
2. Descrever **o que vai mudar** em cada arquivo (prosa curta ou bullets).
3. **Marcar quais itens caem em Categoria B** (exigem aprovação ponto-a-ponto — ver regra #2 e #4).
4. Aguardar aprovação explícita ("sim", "pode", "ok") **antes** de começar.
5. Não usar a palavra "vou" como se fosse permissão — esperar resposta humana.

---

## 4. Plano aprovado = duas modalidades de execução

### Categoria A — modo loop autônomo

Aplica-se a:

- Frontend (HTML, CSS, JS)
- Backend Python que não escreve no banco: `views.py`, `urls.py`, decorators, helpers, tests, docs
- **Funções aditivas (novas) em `oracle_conn.py` que apenas LEEM** (SELECT puro). Qualquer função nova que escreva no Oracle é Categoria B (mesmo sendo aditiva).
- `CREATE OR REPLACE VIEW` para views prefixadas com `AD_` ou `ANDRE_IAGRO_` (nossas custom)
- Refatoração que preserva comportamento, comentários, formatação

**Fluxo:** faz → testa (`manage.py check` + suíte relevante) → corrige erros → melhora → testa → finaliza. Apresenta resumo curto no final (arquivos tocados + validação rodada). **Sem reabrir aprovação a cada passo do plano.**

Pedido do usuário traduzido: *"quero pedir algo simples e receber algo extraordinário pronto, testado, tudo funcionando"* — em Categoria A, é assim que opero.

### Categoria B — pausa pra aprovação ponto-a-ponto

Aplica-se aos itens da regra #2 (alteração de dados no banco + lógica de negócio + operações destrutivas).

Em modalidade B, eu **paro no item específico** e apresento:

- **O quê** muda (descrição curta)
- **Como** (código exato ou SQL exato, em bloco formatado)
- **Por quê** (motivação ou caso de uso)
- **O que afeta** (blast radius — tabelas/queries/módulos impactados, volume estimado em produção quando aplicável)

E aguardo "sim" pra **cada item** antes de prosseguir. Múltiplos itens B em sequência exigem múltiplas aprovações — uma por item.

### Execução parcial sob demanda

Se o usuário pedir "execute até o passo X" / "faça só o backend", parar exatamente no limite indicado e relatar progresso antes de seguir.

### Pausas mesmo dentro de Categoria A

Pausar mesmo em modo loop se aparecer:

- Ação destrutiva inesperada não listada no plano
- Mudança que toca código fora do escopo do plano
- Erro que parece sintoma de regressão maior (não apenas bug pontual)
- Necessidade de rodar smoke contra o Oracle real (mesmo apenas leitura — comunicar antes)

Em dúvida se o passo era previsto, **perguntar**.

---

## 5. Reescrever, nunca apagar lógica sem substituir

- Pode reescrever para clarear: ✅
- Pode consolidar duplicatas mantendo a regra: ✅
- Pode reorganizar arquivos/pastas: ✅
- Pode melhorar nomenclatura: ✅
- **NUNCA** apagar uma regra/lógica/validação porque "parece desnecessária": ❌
- Se algo parece redundante, contraditório ou ambíguo: **sinalizar para decisão**, não remover por conta própria.

---

## 6. Arquivos sempre em UTF-8 SEM BOM

Aplica-se a **todos os arquivos**: `*.html`, `*.css`, `*.js`, `*.py`, `*.md`, `*.sql`, `*.txt`.

**Razão:** O BOM (`0xEF 0xBB 0xBF`) no início de um template Django propaga para o output HTML antes do `<!DOCTYPE html>`, colocando a página em **quirks mode** e causando bugs de layout invisíveis a ferramentas de busca/edição.

**Verificação:**
```bash
head -c 3 arquivo.html | od -c
# Correto: começa com o conteúdo (ex: '{   %' para templates Django)
# Errado: '357 273 277' (bytes do BOM em octal) → reescrever o arquivo
```

---

## 7. Nunca commitar arquivos sensíveis

`.env`, credenciais, tokens, chaves privadas, dumps de banco. O `.gitignore` já está configurado, mas **conferir antes de qualquer `git add`**.

---

## 8. Testes não dependem do Oracle

- Todos os testes **devem** rodar sem conexão real ao banco Oracle.
- Usar `unittest.mock.patch` ou manipulação de `sys.modules` para isolar dependências.
- Total atual do projeto: **229 testes**, todos passando, todos isolados.

---

## 9. Migrations nunca são removidas

- Migrations Django são **append-only**.
- Para reverter uma alteração, criar uma nova migration que desfaça — não editar/remover a migration original.
- A migration `0001_initial.py` cria `Simulation` + `RastreioAudit` juntos.

---

## 10. Idioma e tom

- **Idioma:** Português Brasileiro em toda comunicação, comentários e mensagens de erro humanizadas.
- **Tom:** direto e objetivo. Sem "vou tentar", "talvez", "se você quiser".
- **Erros ao operador:** sempre humanizados via `humanizar_erro_oracle()` — nunca vazar `ORA-XXXXX` ou stack trace.

---

## 11. Campo "Produto" — PERGUNTAR antes de criar/editar (Mai/2026)

O projeto tem **dois padrões diferentes** de pesquisa em campos rotulados "Produto":

- **Padrão A — Filtro por FABRICANTE** (texto LIKE em `pr.FABRICANTE`)
- **Padrão B — Filtro por PRODUTO específico** (CODPROD numérico)

Mesmo nome de campo, comportamentos diferentes. Escolher errado causa filtro silenciosamente inútil (operador acha que filtrou e não filtrou).

**Antes de criar ou alterar QUALQUER campo "Produto" (filtro lateral, modal de item, dashboard, etc), PARAR e PERGUNTAR ao usuário:**

> "Esse campo Produto vai filtrar por **fabricante** (texto, ex: pega tudo de "CENOURA") ou por **produto específico** (CODPROD, ex: só CENOURA IN NATURA)?"

Depois da resposta, aplicar o padrão correspondente (frontend + backend) conforme [`conventions.md`](conventions.md) → "Campo 'Produto' — dois padrões de filtragem".

**Não chutar.** Não copiar de outro módulo sem confirmar. Mesmo se aparenta óbvio pelo contexto, perguntar — porque a UI usa o mesmo rótulo nos dois casos.

### Exemplos de quando se aplica

- Adicionar filtro novo em listagem → perguntar
- Mover campo de uma tela pra outra → confirmar se o padrão original ainda faz sentido
- Refatorar typeahead existente que pareça "inconsistente" → confirmar antes
- Criar novo módulo com campo Produto → perguntar logo no plano

---

## 12. Templates mobile — partial `_m_header_interno.html` é OBRIGATÓRIO em telas internas (Mai/2026 — 2026-05-29)

**Toda `<section class="m-screen">` que NÃO seja a tela `lista` (ex: detalhe, item, cliente, viagem, lightbox, etc) DEVE usar o partial Django:**

```django
<section class="m-screen m-screen--detalhe" data-screen="detalhe">
    {% include "sankhya_integration/_m_header_interno.html"
       with modulo_nome="Entrada" subtela_nome="Nota" %}

    <div class="m-screen-body"> ... </div>
</section>
```

**Onde aplica**:
- Toda tela interna mobile NOVA — sempre incluir o partial
- Toda tela interna mobile EXISTENTE que for refatorada — migrar pro partial se ainda tem header inline duplicado

**Estrutura renderizada** (padrão IAgro Mobile):
```
[← back]   Módulo / Sub-tela          [👤 USUÁRIO]  Sair
```

**NÃO duplicar inline** as classes `.m-breadcrumb*`, `.m-user-badge`, `.m-logout-link`. Elas vivem em `global.css` e são consumidas pelo partial. Qualquer instância nova de `<h1 class="m-screen-title">Nome fixo</h1>` em tela interna é violação dessa regra.

**Documentação obrigatória do partial**: use **`{% comment %}...{% endcomment %}`** (multi-line). NUNCA `{# ... #}` multi-linha — Django interpreta `{% block %}` literal dentro do texto e quebra com `TemplateSyntaxError: Unclosed tag`. Vide [`gotchas.md`](gotchas.md) → "Comentários Django `{# #}` são single-line".

**Exceção: tela `lista`**: já tem padrão próprio (hambúrguer da sidebar em vez de back). Hoje é declarada inline em cada módulo. Se aparecer demanda, criamos um segundo partial `_m_header_lista.html` — por ora é aceitável a duplicação porque varia menos.

**Exceção: telas com botões extras** (ex: lápis/lixeira no header): se houver ações específicas inadiáveis no header da tela interna, declarar inline preservando user-badge + Sair + breadcrumb + classes globais. Mas avaliar primeiro se essas ações não cabem melhor em:
- Bottom-nav "Mais"
- Footer fixo de ações (ver `.m-lg-detalhe-footer` da Logística)
- Swipe-actions do card

Detalhes da diretriz em [`conventions.md`](conventions.md) → "🧩 Partial `_m_header_interno.html`".

### Checklist obrigatório ao gerar tela mobile nova

1. Criou `<section class="m-screen" data-screen="X">`?
2. É a tela `lista` (raiz do módulo)? → header próprio com `m-sidebar-toggle`
3. É **qualquer outra** (detalhe, item, lightbox, etc)? → **partial `_m_header_interno.html`** com `modulo_nome` e `subtela_nome`
4. NUNCA copiar `<h1 class="m-screen-title">...</h1>` inline em tela interna sem o partial
5. NUNCA criar classes locais `.{modulo}-mobile .m-*-breadcrumb*` — usar globais

Falhar em qualquer item viola essa regra.

---

## 13. Templates mobile — partial `_m_fabs.html` é OBRIGATÓRIO pra FABs (Mai/2026 — 2026-05-29)

**Todo template mobile que precise de FAB (verde "adicionar" ou azul "atualizar") DEVE usar o partial:**

```django
{% include "sankhya_integration/_m_fabs.html"
   with fab_primario_id="m_xx_fabAdd"
        fab_primario_label="Adicionar X"
        fab_secundario_id="m_xx_fabRefresh"
        fab_secundario_label="Atualizar" %}
```

**Padrão visual fixo** (definido em `global.css`, não escopado):
- **FAB verde Agromil** 48px (`background: var(--m-primary)`) — ação POSITIVA (criar, adicionar, novo)
- **FAB azul info** 42px (`background: var(--m-info)`) — ATUALIZAR (refresh, recarregar)
- Posicionados em `position: absolute; right: 14px; bottom: <calc bottom-nav + safe-area>`
- Verde tem ícone `ph-plus` por default
- Azul tem ícone `ph-arrows-clockwise` (plural — 2 setas) por default

**Variantes**:
- Só verde: `with fab_secundario_ocultar=True`
- Só azul: `with fab_primario_ocultar=True`
- Ícone custom: `fab_primario_icone="ph-truck"` (qualquer Phosphor)

**Posição em telas internas**: o seletor global `.m-screen:not([data-screen="lista"]) .m-fab` ajusta o FAB pra base segura (sem bottom-nav) automaticamente. Não escrever override por módulo.

**NÃO duplicar inline** classe `.m-fab` ou `.m-fab--secondary` em template novo. Toda instância é violação dessa regra. Classes CSS vivem em `global.css` desde 2026-05-29 — qualquer redefinição local é dead code.

**NÃO criar variantes locais** `.{modulo}-mobile .m-fab*`. Se precisar customizar pra um caso específico (cor diferente, posição diferente), abrir conversa antes — é sinal de quebra de padrão.

Detalhes da diretriz em [`conventions.md`](conventions.md) → "🧩 Partial `_m_fabs.html`".

### Checklist obrigatório ao gerar tela mobile com FAB

1. Vai ter botão "+" (criar/adicionar)? → FAB verde via partial (parâmetro primário)
2. Vai ter botão "atualizar/refresh"? → FAB azul via partial (parâmetro secundário)
3. Vai ter ambos? → ambos params preenchidos
4. NUNCA escrever `<button class="m-fab">...</button>` inline
5. NUNCA criar `.m-fab` em CSS de módulo — a classe é global

Falhar em qualquer item viola essa regra.
