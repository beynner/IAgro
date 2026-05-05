# Regras Permanentes de Desenvolvimento

Estas regras se aplicam a **todas** as sessões, sem exceção. Violar qualquer uma delas requer aprovação explícita do usuário.

---

## 1. Reuso antes de criar

**Antes de criar qualquer função, método ou bloco de código novo**, verificar se existe algo reutilizável no projeto.

- Buscar por nomes similares em `oracle_conn.py`, `views.py`, `iagro_helpers.js`, `global.css`.
- Se houver lógica semelhante, apontar e sugerir consolidação em vez de duplicar.
- Helpers JS centrais ficam em `iagro_helpers.js` sob `window.IAgro`.
- Tokens de design ficam em `global.css` (variáveis com nomes em português).

---

## 2. Lógica de negócio é intocável

**NUNCA alterar sem aprovação explícita:**
- Queries SQL ao Oracle (qualquer função em `oracle_conn.py` que faça SELECT/INSERT/UPDATE/DELETE)
- Cálculos financeiros (preço, total, recalculo de notas)
- Regras de precificação e negociação
- Fluxo de faturamento (TOP 34 → 35/37, geração de NUMNOTA, CODNAT)
- Validações de saldo de lote, lock pessimista, atomicidade transacional

Se a tarefa parece exigir mudança nesses pontos, **parar e perguntar**.

---

## 3. Plano antes de agir

Para qualquer alteração de código:

1. Apresentar **lista completa** dos arquivos que serão modificados.
2. Descrever **o que vai mudar** em cada arquivo (em prosa curta ou bullets).
3. Aguardar aprovação explícita ("sim", "pode", "ok") **antes** de começar.
4. Não usar a palavra "vou" como se fosse permissão — esperar resposta humana.

---

## 4. Uma tarefa por vez

- Executar **uma alteração de cada vez**.
- Aguardar confirmação do usuário antes de avançar para a próxima.
- Não encadear múltiplas mudanças em uma única resposta sem pausa.

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
- Total atual do projeto: **174 testes**, todos passando, todos isolados.

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
