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
