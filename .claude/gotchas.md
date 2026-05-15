# Pontos de Atenção (Armadilhas Técnicas)

Lista de pegadinhas que **já causaram bugs** ou que podem causar se tocadas sem cuidado. Tratar como avisos críticos.

---

## Linter aponta `rapidfuzz` como módulo ausente — falso positivo

Quando o Antigravity (ou outro IDE) está com **interpreter setado para o Python do sistema** (ex: `C:\Users\ANDRE\AppData\Local\Programs\Python\Python313\`) ao invés do venv do projeto (`.venv\Scripts\python.exe`), o linter olha apenas as packages do Python sistema — onde `rapidfuzz` (e demais deps do `requirements.txt`) **não estão instaladas**.

Resultado: warning amarelo `Cannot find module 'rapidfuzz'` em [services/matching.py](sankhya_integration/services/matching.py). **Em runtime tudo funciona** — Django roda dentro da venv que tem rapidfuzz.

**Correção definitiva:** No Antigravity, `Ctrl+Shift+P` → `Python: Select Interpreter` → escolher `.\.venv\Scripts\python.exe`.

---

## Console Windows (cp1252) estoura em emoji/setas no `stdout.write()`

PowerShell em pt-BR roda com encoding **cp1252**. Quando um management command faz `self.stdout.write("→ Concluído")`, o caractere `→` (U+2192) não existe em cp1252 → `UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'`.

Caracteres que **já causaram crash** em commands deste projeto:

| Char | U+ | Substituir por |
|---|---|---|
| `→` (seta direita) | 2192 | `->` |
| `↪` (seta retorno) | 21AA | `->` |
| `✓` (check) | 2713 | `OK:` |
| `⚠` (atenção) | 26A0 | `[!]` |

**Regra:** em `self.stdout.write(...)` de qualquer management command, **só ASCII**. Em comentários e docstrings emojis são OK (não passam pelo encode do console).

**Solução alternativa** (caso queira manter emojis): adicionar no início do `handle()`:
```python
import sys
for s in (sys.stdout, sys.stderr):
    if hasattr(s, 'reconfigure'):
        try: s.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass
```
Mas pode falhar dependendo de como o subprocess foi invocado — preferimos ASCII direto.

---

## Bash tool tem teto de 10 min — worker LLM grande precisa rodar com `--max 1`

A ferramenta Bash da IDE limita execuções a `600000ms` (10 minutos). O worker `colher_pedidos_email` em modo padrão pode rodar muito mais que isso (cada chamada Ollama em CPU leva ~3-5 min × 3 retries × N records).

**Padrão pra processar manualmente sem ser morto pelo timeout:**
```powershell
python manage.py colher_pedidos_email --skip-imap --max 1
```
Processa 1 record por chamada. Repetir até a fila esvaziar. Em produção, o Task Scheduler (a cada 30 min) não tem esse limite — só vale para diagnóstico via Bash da IDE.

---

## CRÍTICO — `DEBUG=False` quebra arquivos estáticos em desenvolvimento

O `runserver` do Django **não serve arquivos estáticos** quando `DEBUG=False`. Definir `DEBUG=False` no `.env` em ambiente sem nginx/WhiteNoise faz todo JS/CSS parar de carregar, quebrando completamente as páginas.

**Regra:** Nunca alterar `DEBUG` no `.env` sem confirmar que existe servidor de arquivos estáticos configurado na frente do Django.

---

## `oracle_conn.py` — Núcleo crítico (~3350 linhas)

Contém **todas as queries SQL** ao Oracle. Ponto mais sensível do sistema.

- **Não refatorar sem aprovação explícita** — qualquer mudança pode quebrar produção.
- Funções aditivas (novas) são aceitáveis. Alteração de queries existentes **não**.
- `obter_conexao_oracle()` é context manager — gerencia commit/rollback.
- `is_write_enabled()` controla habilitação de operações de escrita.
- `perfis_banco` (`local`/`remote`) foi esvaziado — conexão usa exclusivamente `SANKHYA_DB_*` do `.env`.

---

## Bug do `DPY-1001` em escritas

`inserir_cabecalho_nota_banco` tem um `except` que tenta `rollback()` numa conexão **já fechada** pelo context manager. Isso substitui a exceção Oracle original com `DPY-1001: not connected to database`, mascarando o erro real.

**Workaround obrigatório em todas as views de escrita:**

```python
with obter_conexao_oracle() as conn:
    resultado = funcao_do_service(..., conexao_existente=conn)
    conn.commit()
```

A view passa a conn explicitamente para o service, evitando o caminho bugado.

---

## `atualizar_cabecalho_nota_banco` tem auto-cura específica

Tem auto-cura de `AD_NUMPEDIDOORIG` que é **específica da Entrada/Classificação**. **Venda e Rastreio NÃO usam** essa função:

- Venda usa `atualizar_cabecalho_venda_banco` (dedicado, sem auto-cura).
- Rastreio (atribuição de lote) atualiza `CODAGREGACAO` diretamente, **sem passar por `atualizar_item_nota_banco`** (que aceita `CODAGREGACAO` mas tem a mesma auto-cura).

---

## Trigger `SANKHYA.TRG_INC_TGFCAB` exige tupla coerente

INSERT em TGFCAB **rejeita** se `(CODTIPVENDA, DHTIPVENDA)` não estiverem coerentes. Erro: `ORA-20101: Verifique se o TIPO DE NEGOCIAÇÃO X está ativo...`.

**Solução aplicada:** `inserir_cabecalho_nota_banco` consulta a `DHALTER` mais recente da TGFTPV antes do INSERT e grava em `DHTIPVENDA`.

---

## Paginação Oracle — usar `ROW_NUMBER`, não `OFFSET FETCH`

Ambiente atual é Oracle 11g compatível. **`OFFSET ... FETCH NEXT` (12c+) explode com `ORA-00933`** em algumas queries do projeto.

**Padrão obrigatório:**

```sql
SELECT * FROM (
  SELECT t.*, ROW_NUMBER() OVER (ORDER BY ...) AS rn
  FROM ... t
)
WHERE rn BETWEEN :inicio AND :fim
```

---

## Retorno de tuplas, não dicts

Funções de `oracle_conn.py` retornam **listas de tuplas** (formato nativo do cursor Oracle). Views acessam por índice (`r[0]`, `r[1]`, etc.).

**Ao adicionar novas colunas a qualquer query, os índices das colunas seguintes mudam — verificar todos os usos antes de mexer.**

Ordem documentada em `schema.md` para as funções principais.

---

## `entrada.css` é carregado em todos os módulos

Por legado, o `base.html` carrega `entrada.css` para **todas as páginas**, não só Entrada. Qualquer regra adicionada lá vaza para outros módulos.

**Cuidado ao mexer em** `.appbar`, `.panel`, `.home-btn`, etc. dentro de `entrada.css`.

Pendência de refator: separar em `base-layout.css` (global) + `entrada.css` (específico).

### Conflito específico: `.modal-overlay { display: none }` em `entrada.css`

`entrada.css:272` define:
```css
.modal-overlay { display: none; ... }
.modal-overlay.visible { display: flex; }
```

Como `entrada.css` carrega **depois** de `global.css` (que define `.modal-overlay { display: flex; }` por padrão), o `display: none` vence. Módulo novo que segue o padrão "remove classe `.hidden` pra mostrar modal" **não funciona** — modal fica invisível mesmo após `classList.remove('hidden')`.

**Sintoma:** click no botão dispara o handler (visível com `console.log`), `classList.remove('hidden')` é executado, mas modal não aparece visualmente.

**Workaround:** módulos novos que usam `.modal-overlay` precisam adicionar regra própria no CSS:

```css
.modal-overlay:not(.hidden) {
    display: flex !important;
}
```

`rastreio.css` (linha 546) e `email_importar.css` já fazem isso. Padronize ao criar tela com modal.

---

## Arquivos sempre em UTF-8 SEM BOM

O BOM (`0xEF 0xBB 0xBF`) no início de um template Django propaga para o HTML final **antes do `<!DOCTYPE html>`**, colocando a página em **quirks mode** e causando bugs de layout invisíveis a ferramentas de busca/edição.

**Verificação:**
```bash
head -c 3 arquivo.html | od -c
# Correto: começa com o conteúdo do arquivo
# Errado: '357 273 277' → reescrever sem BOM
```

---

## `api_listar_vales_comercial` — endpoint sem autenticação

A view `api_listar_vales_comercial` (rota `comercial/lista/`) **não tem `@exige_grupo`**. Qualquer GET retorna dados sem sessão autenticada.

**Status:** documentado nos testes, mas não confirmado se é intencional. **Avaliar antes de qualquer release de produção.**

---

## Geração de NUMNOTA — `MAX(NUMNOTA) + 1`

`faturar_pedido_venda_banco` gera NUMNOTA via `MAX(NUMNOTA) + 1` por empresa.

- **Funciona no MVP** porque o lock pessimista no cabeçalho protege a janela de concorrência.
- **Atenção:** se o Sankhya começar a emitir NFe **paralelamente** ao IAgro, pode haver colisão.
- **Migração futura:** sequência Oracle nativa (`SEQUENCE`) seria mais robusta, mas exige criação no Sankhya.

---

## `RastreioAudit` é tolerante a falhas

Helper `_registrar_audit_rastreio()` em `views.py` engole exceções (apenas `logger.warning`).

**Razão:** a operação no Oracle já foi **commitada** e não pode ser revertida por causa de uma falha no audit.

**Não mudar para `raise`.** Audit é telemetria, não regra de negócio.

---

## `humanizar_erro_oracle` é UI-only

Sempre logar a exceção original com `logger.exception` **antes** de humanizar. Caso contrário, suporte fica sem trilha para diagnóstico.

```python
try:
    ...
except Exception as exc:
    logger.exception("Falha em api_xxx")          # 1º — preserva técnico
    return JsonResponse({                         # 2º — humaniza para usuário
        'ok': False,
        'error': humanizar_erro_oracle(exc),
    }, status=500)
```

---

## Dropdown de typeahead dentro de `<td>` precisa `position: fixed` + appendChild no `<body>`

`.dropdown-abs` posicionado com `position: absolute; top: 100%` num `<td class="pos-rel">` **não funciona de forma confiável** quando a tabela usa `border-collapse: collapse`. O Chrome ignora o `position: relative` do td em alguns cenários, então o dropdown é posicionado relativo ao `<html>` e some fora da viewport (mesmo com `display: block` e `width > 0`).

**Sintoma:** request de busca chega ao backend (200), JSON com resultados volta, `show()` é chamado, dropdown tem `display: block` — mas nada aparece visualmente.

**Solução aplicada no email_importar.js (Mai/2026):** o `attachTA` da tela de e-mail move o `<div class="dropdown-abs">` pro `<body>` antes de mostrar e usa `position: fixed` com coordenadas calculadas via `inp.getBoundingClientRect()`:

```js
function show(items) {
    if (dd.parentElement !== document.body) document.body.appendChild(dd);
    const r = inp.getBoundingClientRect();
    dd.style.position = 'fixed';
    dd.style.top      = `${r.bottom}px`;
    dd.style.left     = `${r.left}px`;
    dd.style.width    = `${r.width}px`;
    dd.style.zIndex   = '10000';
    dd.style.display  = 'block';
}
```

E o `hide()` reseta os styles inline pra deixar limpo.

**Quando reaproveitar:** qualquer typeahead novo cuja célula renderizadora seja `<td>` ou esteja dentro de `<table border-collapse: collapse>`. Se for fora de tabela (form normal), `position: absolute` no wrapper relativo basta — vide typeaheads do parceiro/empresa/tipo de venda no mesmo arquivo.

**Limitação:** com `position: fixed`, se o usuário rolar a página enquanto o dropdown está aberto, ele fica "preso" na coordenada antiga. Aceitável porque `blur` do input fecha o dropdown e a maioria das interações é click/Tab/Enter (que fecham antes de rolar).

---

## ORA-20101 é genérico — mascarava mensagem real do trigger

Antes de Mai/2026 (2026-05-13), `humanizar_erro_oracle()` mapeava `ORA-20101` → `"Tipo de negociação inativo ou inválido."` (mensagem fixa). Mas **ORA-20101 é o código de `RAISE_APPLICATION_ERROR` usado por dezenas de triggers Sankhya** — não só TIPVENDA. Mensagens reais que apareciam mascaradas em produção:

- "Baixa sem ligação com TGFMBC. Financeiro de Nro único: NNN."
- "Só é permitido preencher o NUNOTA para financeiros com origem 'E'."
- "Informe o valor da baixa e Código de operação de baixa simultaneamente..."
- "A TOP da Baixa deve ser informada."
- "A única atualização permitida para o Status da Nota é a passagem deste para L."

Operador caçava problema inexistente porque o erro real era encoberto.

**Fix em `humanizar_erro_oracle`**: case especial pra `ORA-20101` que extrai a mensagem real via regex (`ORA-20101:\s*(.+?)(?:\n|ORA-\d|$)`) **antes** de cair no fallback genérico. Quando o texto extraído tem ≤240 chars, repassa direto. Senão, fallback "Regra do banco rejeitou a operação. Verifique os dados informados."

Ao adicionar mapping novo de `ORA-XXXXX` em `_MAPA_ORA_HUMANIZADO`, **considere se o código é genérico (vários triggers) ou específico**. Códigos genéricos como 20101 devem deixar a mensagem original passar pra UI.

---

## TGFFIN nasce SEMPRE em aberto — 3 triggers Sankhya bloqueiam baixa automática

Ao criar TGFFIN via IAgro pra entrada de combustível (TOP 10) ou abastecimento externo (TOP 53), **NUNCA marcar baixa automática** (DHBAIXA, VLRBAIXA, CODTIPOPERBAIXA). 3 triggers Sankhya impedem em cascata, mascarados como ORA-20101:

| Trigger | Erro | Causa |
|---|---|---|
| `TRG_UPT_TGFFIN_NUBCO` | "Baixa sem ligação com TGFMBC" | INSERT com `DHBAIXA NOT NULL` mas sem registro paralelo em TGFMBC (movimentação bancária real). Sankhya nativo gera TGFMBC quando operador clica "Baixar" no painel. |
| `TRG_INC_TGFFIN` | "Só é permitido preencher NUNOTA para financeiros com origem 'E'" | INSERT com `NUNOTA` preenchido exige `ORIGEM='E'` (Entrada de Nota). `ORIGEM='F'` (Financeiro avulso) **não pode ter NUNOTA**. |
| `TRG_INC_TGFFIN` / `TRG_UPT_TGFFIN` | "Informe o valor da baixa e Código de operação de baixa simultaneamente" / "A TOP da Baixa deve ser informada" | `VLRBAIXA > 0` exige `CODTIPOPERBAIXA > 0`, e vice-versa. Ou os dois zerados ou os dois preenchidos. |

**Padrão correto** (aplicado em `criar_entrada_combustivel_banco` + `criar_abastecimento_externo_banco` + UPDATE TGFFIN em `editar_*`):

```python
# Modelo NUFIN em aberto (Mai/2026)
ORIGEM = 'E'                              # Sempre 'E' quando NUNOTA preenchido
VLRBAIXA = 0                              # Sempre 0
DHBAIXA = NULL                            # Sempre NULL
CODEMPBAIXA = NULL
CODUSUBAIXA = NULL
CODTIPOPERBAIXA = 0                       # Coerente com VLRBAIXA=0
DHTIPOPERBAIXA = TO_DATE('01/01/1998','DD/MM/YYYY')  # Padrão Sankhya em aberto
```

Operador baixa pelo Sankhya quando paga (Sankhya cria TGFMBC + preenche CODTIPOPERBAIXA corretamente).

**Como descobri**: smoke real após cada fix mostrou um trigger atrás do outro. Cada erro só aparece DEPOIS de corrigir o anterior — sem dump dos 3 triggers de uma vez, só sequencial.

---

## `gerar_proxima_sequencia_item` abria nova conexão — quebrava transações multi-INSERT

Função `gerar_proxima_sequencia_item(nunota)` (chamada por `inserir_item_nota_banco`) abria **conexão Oracle paralela** (`with obter_conexao_oracle() as conn:`). Em fluxos transacionais onde múltiplos `inserir_item_nota_banco` rodam antes do commit (ex: edição de entrada multi-itens em B14), a conexão paralela **não enxerga** os INSERTs anteriores nem o DELETE pendente da transação principal → SEQUENCIA duplicada → **ORA-00001 PK violation**.

**Fix em Mai/2026 (2026-05-13)**: assinatura ganhou `conexao_existente: Optional[Connection] = None`. Quando o caller passa, usa a mesma conexão (enxerga estado pendente).

```python
def gerar_proxima_sequencia_item(nunota, conexao_existente=None):
    sql = "SELECT NVL(MAX(SEQUENCIA),0) + 1 FROM TGFITE WHERE NUNOTA = :nunota"
    if conexao_existente is not None:
        cur = conexao_existente.cursor()
        cur.execute(sql, nunota=nunota)
        return int(cur.fetchone()[0])
    # fallback antigo (nova conexão)
    with obter_conexao_oracle() as conn:
        cur = conn.cursor()
        cur.execute(sql, nunota=nunota)
        return int(cur.fetchone()[0])
```

`inserir_item_nota_banco` passa `conexao_existente=conn` adiante. Backward-compat preservada: callers que não passam continuam funcionando.

**Estratégia complementar**: em edição de entrada/requisição multi-itens (B11/B14), o **UPDATE diferencial** reusa SEQUENCIAs existentes (UPDATE in-place) e só faz INSERT pros adicionais — minimiza chances de conflito.

---

## TOP 53 = REQUISIÇÃO INTERNA (não TOP 26)

Reservar **TOP 26 exclusivamente pro módulo de Classificação** (hortifrúti). Módulos novos que precisem de saída/requisição devem usar **TOP 53 — REQUISIÇÃO INTERNA** (`TIPMOV='Q'`, ativa). Antes de Mai/2026 (2026-05-13), o módulo Combustível usava TOP 26 — bug histórico corrigido em refator amplo (todas as funções de criar/editar/excluir + queries de leitura + view `ANDRE_IAGRO_SALDO_COMBUSTIVEL`).

⚠ **Cuidado com `where_comum` em queries UNION**: a `listar_movimentacoes_combustivel` tinha `where_comum = ["c.CODTIPOPER IN (10, 26)"]` que ficava AND-conjugado com `c.CODTIPOPER = 53` da perna de requisição → condição impossível, 0 resultados. Quando trocar TOP em queries UNION, conferir TODAS as listas de WHERE.

---

## Trigger `TRG_UPD_TGFCAB` bloqueia `UPDATE STATUSNOTA='E'` — exclusão é DELETE físico

Descoberto em Mai/2026 (2026-05-12) durante desenvolvimento do B6 do módulo Combustível (excluir requisição). A mensagem oficial do trigger Sankhya (linha 979):

> `ORA-20101: A única atualização permitida para o Status da Nota é a passagem deste para L. Nota de Nro único: NNNNN`

Significa que **não existe "exclusão lógica" via STATUSNOTA='E' no Sankhya**. Apesar do filtro `STATUSNOTA <> 'E'` aparecer em queries da view `ANDRE_IAGRO_SALDO_*` (sugerindo que 'E' é estado válido), o ERP **não permite criar esse estado via UPDATE manual**. As notas com STATUSNOTA='E' que aparecem em produção foram criadas por algum fluxo nativo do Sankhya (provavelmente exclusões via UI do ERP que disparam um path específico do trigger).

**Implicação prática**: pra "excluir" uma nota TGFCAB via IAgro, o caminho é **DELETE físico em cascata**:

```sql
DELETE FROM TGFITE WHERE NUNOTA = :n;   -- itens primeiro (FK)
DELETE FROM TGFCAB WHERE NUNOTA = :n;   -- cabeçalho depois
-- (dispara TRG_DLT_TGFCAB_* nativas do ERP que fazem auditoria/limpeza)
```

**Quando aplicar**:
- ✅ Requisição de combustível (TGFCAB TOP 26 do módulo Combustível) — B6 implementado assim
- ⚠ Outras TOP IAgro que precisem "cancelar" — pensar caso a caso. Pode haver triggers nativas de DELETE que disparam efeitos colaterais (financeiro, contábil, estoque)

**Quando NÃO aplicar**:
- ❌ TGFCAB com `STATUSNOTA='L'` (confirmada) — bloquear no IAgro e mandar operador estornar pelo Sankhya, que reverte financeiro/contábil corretamente
- ❌ TGFCAB com TGFFIN/TGMTRA já gerados — DELETE pode quebrar relações financeiras

**Auditoria**: como o DELETE apaga o registro, qualquer rastro de quem excluiu precisa ser preservado **antes** do DELETE. No B6 do Combustível, gravamos motivo+usuário em `logger.info` antes dos 3 DELETEs (AD_REQ → TGFITE → TGFCAB).

Test de regressão: `test_views_combustivel.py::ExcluirRequisicaoServiceTest::test_fluxo_feliz_delete_fisico` verifica explicitamente que o código não usa mais `UPDATE STATUSNOTA='E'`.

---

## View `ANDRE_IAGRO_SALDO_COMBUSTIVEL` — `GREATEST(0)` corrompe saldo quando saldo inicial > 0

Descoberto em Mai/2026 (2026-05-12). A view tem:

```sql
GREATEST(NVL(e.QTD_ENTRADA, 0) - NVL(s.QTD_SAIDA, 0), 0) AS QTD_DISPONIVEL
```

Quando o tanque tem `entrada_view = 0` (só saldo inicial — produto sem TOP 10 ainda no IAgro) + `saída > 0`, a view força QTD_DISPONIVEL=0 (cortando o saldo negativo). Se o código somar `SALDO_INICIAL_TANQUE` em cima de QTD_DISPONIVEL, ignora completamente a saída.

Exemplo: tanque com saldo_inicial=300, entrada_view=0, saída=100:
- View retorna QTD_DISPONIVEL = `max(0 - 100, 0)` = 0
- Código (errado) faria 0 + 300 = **300** (ignora saída!)
- Conta correta: 0 + 300 - 100 = **200**

**Fix** em `consultar_saldo_combustivel`: NÃO usar `QTD_DISPONIVEL` da view. Sempre calcular em Python:

```python
qtd_entrada_total = qtd_entrada_view + saldo_inicial
qtd_disponivel    = qtd_entrada_total - qtd_saida
if qtd_disponivel < 0:
    qtd_disponivel = 0.0
```

Test de regressão: `ConsultarSaldoCombustivelServiceTest.test_disponivel_desconta_saida_quando_entrada_view_zero`.

**Generalização pra views futuras**: ao introduzir "saldo inicial" externo somado fora da view, **NÃO usar campos com GREATEST 0 da view** — eles cortam matemática antes do offset entrar. Calcular tudo em Python ou ajustar a view pra aceitar saldo inicial como parâmetro.

---

## `int(dados.get(K, default))` quebra quando a chave existe com valor None

Padrão recorrente em código IAgro:

```python
codlocalorig = int(dados.get('CODLOCALORIG', 101))  # ❌ quebra se chave existe com None
```

Quando o caller passa explicitamente `'CODLOCALORIG': None` no dict, `dict.get(K, default)` **retorna None (não o default)** — `.get()` só usa o default quando a chave **não existe**. Aí `int(None)` levanta `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`.

**Manifestação real (Mai/2026)**: B2 `criar_requisicao_combustivel_banco` chamava `inserir_item_nota_banco` passando `'CODLOCALORIG': None` explícito → quebrou em produção com mensagem genérica `int() argument...`, mascarada como "Falha de conexão" no frontend (bug do `IAgro.postJSON`).

**Soluções**:
1. **Omitir a chave** do dict em vez de passar None (`inserir_item_nota_banco` usa default 101 quando ausente). Foi o fix aplicado em B2/B3 do Combustível
2. **Validar antes** do `int()`: `int(dados.get(K) or 101)` — funciona pra valores falsy
3. **Adicionar default no caller**: `dados.setdefault('CODLOCALORIG', 101)` antes do INSERT

Test de regressão: `CriarRequisicaoServiceTest.test_payload_inserir_item_nao_passa_codlocalorig_none` — valida que o payload do `inserir_item_nota_banco` NÃO tem `CODLOCALORIG=None`.

---

## `IAgro.postJSON` retorna `{ok, status, body}`, NÃO uma Response do fetch

Descoberto em Mai/2026 (2026-05-12) — chamadas a `IAgro.postJSON` nos modais do Combustível mascaravam erros HTTP 400 do backend como "Falha de conexão".

A função em `iagro_helpers.js:32`:

```js
async function postJSON(url, data) {
    try {
        const response = await fetch(url, { ... });
        const responseBody = await response.json();
        return { ok: response.ok, status: response.status, body: responseBody };
    } catch (error) {
        return { ok: false, status: 0, body: { error: 'Erro de comunicação' } };
    }
}
```

**Uso correto** no caller:

```js
const resp = await IAgro.postJSON(url, payload);
const data = resp.body || {};                     // ← body já é o JSON parseado
if (!resp.ok || !data.ok) {
    msg.textContent = data.error || `Erro ${resp.status}`;
}
```

**Uso ERRADO** (que gerou o bug):

```js
const resp = await IAgro.postJSON(url, payload);
const data = await resp.json();   // ❌ resp não é Response — não tem método .json()
                                   // TypeError → catch → "Falha de conexão"
```

Resultado: qualquer erro HTTP (400, 500, etc.) virava `"Falha de conexão"` no frontend, perdendo a mensagem real do backend.

**Convenção pra qualquer nova chamada**: sempre tratar como `{ok, status, body}`, NÃO como Response.

---

## `TGFVAR` é populada via trigger Sankhya — NÃO escrever direto (**exceção: devolução TOP 36 Mai/2026**)

A tabela `TGFVAR` é a **fonte canônica do vínculo entre notas geradas** no Sankhya (pedido↔nota, compra↔vale, devolução↔venda, etc). Estrutura: `NUNOTA, SEQUENCIA, NUNOTAORIG, SEQUENCIAORIG, QTDATENDIDA, ...`.

**Quem popula:** trigger interna do Sankhya, disparada no fluxo de faturamento / atendimento de pedido. **O IAgro nunca escreve em TGFVAR** — só lê.

### Por que isso importa

- ~211k linhas em produção (185k TOP 34↔35, 9k TOP 11↔13, etc.)
- Mantém consistência entre TGFITE de pedido e TGFITE de nota gerada (mesmo CODPROD, mesma QTDNEG, mesma estrutura — mas SEQUENCIA pode mudar entre os dois lados; Sankhya re-ordena geralmente por CODPROD)
- **Vínculo NÃO está em TGFCAB** — todos os 6 campos NUNOTA-* (`NUNOTAORIGCORTE`, `NUNOTAREC`, `NUNOTASUB`, `TIMNUNOTAMOD`, `NUNOTAPEDFRET`, `AD_NUMPEDIDOORIG`) estão NULL em 100% dos pedidos reais. Confirmado em 2026-05-09

### Onde o IAgro lê TGFVAR (Mai/2026 — final)

Apenas 2 lugares:

1. **`consultar_pedidos_abertos_para_atribuicao`** — subquery escalar correlacionada pra trazer `NUMNOTA` + `NUNOTA` da nota correlata (TOP 35/37) de cada pedido TOP 34 STATUSNOTA='L'. Frontend usa pra exibir badge `FATURADO Nota Y`.
2. **View `ANDRE_IAGRO_SALDO_LOTE`** — `NOT EXISTS` no UNION da perna `baixas_venda` pra desempatar quando o mesmo lote aparece tanto pelo lado do pedido (verdade IAgro) quanto pelo lado da nota (fallback Sankhya nativo).

### Por que NÃO escrevemos em TGFVAR — análise das 6 triggers

Em 2026-05-11 analisamos `TRG_INC_TGFVAR`, `TRG_UPT_TGFVAR`, `TRG_DLT_TGFVAR`, `TRG_DLT_TGFVAR_AFTER`, `TRG_INC_TGFVAR_BLOQ_SAFRA`, `TRG_INC_UPD_DEL_TGFVAR_CFIDEL`. Cascatas confirmadas:

- **`TRG_INC_TGFVAR`**: INSERT em TGMTRA (movimentação financeira/meta-orçamento, 2-N linhas por par) + UPDATE em `TGFITE.QTDENTREGUE`/`QTDFIXADA`. Usa funções internas `SNK_VERIFICA_PK_TGMTRA`, `STP_TROCA_NUMTRANSF` que podem renomear NUMTRANSF dinamicamente
- **`TRG_UPT_TGFVAR`**: simétrica — bloqueia mudança em NUNOTA/SEQUENCIA, DELETE + INSERT em TGMTRA pra recalcular compromissos
- **`TRG_DLT_TGFVAR_AFTER`**: subtrai `QTDATENDIDA` de TGFITE.QTDENTREGUE
- **`TRG_INC_TGFVAR_BLOQ_SAFRA`**: pode bloquear INSERT por `TGABDLC.BLOQUEAR='S'` em projetos
- **`TRG_INC_UPD_DEL_TGFVAR_CFIDEL`**: mexe em TGFCFM (cupons de fidelidade) só em devoluções com cupom fiscal — fora do nosso escopo

Resultado: INSERT manual em TGFVAR sem ambiente de homologação Sankhya pode duplicar movimentação financeira, quebrar metas/orçamento, e funções internas com auto-cura podem renomear PKs imprevisivelmente. Erros viram `ORA-20101` (mapeado pra "Tipo de negociação inativo" no IAgro — mensagem errada).

### Decisão arquitetural

A rastreabilidade do IAgro vive **só no pedido (TGFITE TOP 34)**, inclusive após faturamento. A nota TOP 35/37 não é tocada. Validado: NFe XML pra NCM 0706 hortifrúti não exige grupo `<rastro>`, então `CODAGREGACAO` é dado interno sem efeito fiscal. SPLIT em pedido faturado funciona porque TGFVAR fica intocada — só o TGFITE do pedido ganha SEQ novo.

### Não confundir com `AD_NUMPEDIDOORIG`

`AD_NUMPEDIDOORIG` é **convenção customizada da Agromil** em TGFCAB+TGFITE — não substitui TGFVAR. Veja gotcha "`atualizar_cabecalho_nota_banco` tem auto-cura específica" e schema.md §5.5.

### EXCEÇÃO documentada — devolução TOP 36 (Mai/2026)

O módulo de **Devolução TOP 36** do IAgro **escreve em TGFVAR** propositadamente, replicando fielmente o caminho do Sankhya nativo. **Não é trapaça**:

- Sankhya popula TGFVAR **JÁ NO INSERT** da TOP 36 (descoberto em investigação Mai/2026: 12 de 13 TOP 36 STATUSNOTA='A' já têm TGFVAR par)
- Estamos criando uma **devolução real**, do jeito que o ERP espera. A cascata em TGMTRA disparada por `TRG_INC_TGFVAR` aconteceria igualzinha se o operador criasse pelo módulo nativo
- Função: `criar_devolucao_top36_banco` em `oracle_conn.py`
- A TOP 36 é criada em `STATUSNOTA='A'` (em aberto). Operador confirma no Sankhya, que muda pra 'L' e dispara financeiro reverso + NFe

**Diferença vs Rastreio Fase 2 (aposentada):** lá queríamos criar **vínculo artificial de lote** numa nota faturada sem criar devolução — isso engana o ERP e foi descartado. Aqui criamos uma devolução **legítima**, que o ERP processa normalmente.

---

## Lock pessimista em `atribuir_lote_item_pedido`

`SELECT ... FOR UPDATE` **antes** da validação de saldo. Defesa contra:

- **Double-binding:** se item já tem `CODAGREGACAO` diferente, recusa com mensagem clara ("Desvincule antes de atribuir outro lote").
- **Race condition** entre operações concorrentes.

Qualquer mudança aqui exige reanálise do lock.

---

## Signals cobrem apenas `Simulation`

`signals.py` gera audit log via `post_save`/`post_delete` **somente para `Simulation`**. Operações financeiras e de estoque são escritas diretamente no Oracle e auditadas via `logger.info()` nas views.

`RastreioAudit` é gravado **explicitamente** pelo helper `_registrar_audit_rastreio()`, não por signal.

---

## Áreas frontend que precisam atenção

### `renderPedidos()` em `rastreio.js`

Função central que agrupa, ordena e renderiza pedidos. Mudanças aqui afetam **POR PARCEIRO** e **POR PRODUTO**. Sempre validar os 4 caminhos: parceiro/produto × com filtro/sem filtro.

### `pedidosColapsados` + `pedidosJaVistos` (Rastreio)

Duplicidade de `Set` é **intencional**. **Não consolidar em um único** — perderia a distinção "novo vs. já visto" que preserva escolha do usuário.

### `checksLotes` + `checksPorPedido` (Rastreio)

Não consolidar em estrutura única. **Eixos separados são premissa do filtro cruzado isolado** (decisão pedida pelo usuário).

### `limparTudo()` (Rastreio)

Toda nova feature de filtro/estado precisa adicionar reset aqui. Hoje reseta: typeaheads, datas, agrupamento, tipoLote, lote armado, isolamento, `pedidosColapsados`, `pedidosJaVistos`, `gruposProdutoColapsados`, `gruposProdutoJaVistos`, `checksLotes`, `checksPorPedido`, `somentePendentes`. **Esquecer um item deixa estado residual.**

### `renderFiltrosAtivos()` (Rastreio)

Popula apenas `#filtrosAtivosChips` (filho). O container externo `#filtrosAtivos` é estático no template (contém botões fixos `Limpar`/`Atualizar`). **Não voltar a sobrescrever `filtrosAtivosEl.innerHTML` inteiro** — destrói os botões.

### IDs `btnLimparTudo` / `btnAtualizar`

Preservados desde a primeira versão. Listeners JS dependem deles. **Não renomear sem atualizar JS.**

### Persistência de filtros em `localStorage` (Venda + Rastreio)

Chaves versionadas: `iagro:venda:filtros:v1` (Venda), `iagro:rastreio:prefs:v1` (Rastreio). Ao adicionar um campo novo, atualize `CAMPOS_FILTRO_PERSISTIDOS` (Venda) ou o objeto serializado (Rastreio). Ao mudar o **formato** de um valor existente, **bumpe a versão da chave** (`v2`) — não tente migrar in-place silenciosamente, porque preferências antigas voltariam corrompidas e o usuário não sabe limpar.

### `btnClear` da Venda — chamar `limparFiltrosNoLocalStorage()`

O reset visual dos campos não basta: o storage também precisa ser apagado, senão na próxima carga o estado "sujo" volta. Já está aplicado, mas **ao adicionar um novo botão de reset alternativo** (ex.: chip de período, "Voltar para hoje"), decidir explicitamente se ele apaga o storage ou só o campo.

---

## Lote = `CODAGREGACAO`, não `CONTROLE`

A documentação antiga (`.claude/schema.md` antes de Abr/2026) listava `CONTROLE` como o campo do lote-texto. **Estava errada** — todas as queries reais do projeto usam `CODAGREGACAO` (apesar do nome sugerir `NUMBER`, na prática é `VARCHAR2` com valores tipo `NUNOTAS123D260429`). A doc foi corrigida.

Ao escrever queries novas em `oracle_conn.py`, **usar `CODAGREGACAO`** — e tratar como string (`UPPER(CODAGREGACAO) LIKE :p`).

---

## `TGFPRO.FABRICANTE` na Agromil ≠ fornecedor real

Cadastro Sankhya da Agromil tem `TGFPRO.FABRICANTE` populado com **nome do produto** (LIMÃO, BATATA DOCE, REPOLHO BRANCO…), **não** com fabricante/fornecedor de verdade. Validado em Mai/2026 contra 102 valores distintos no banco real.

O **fornecedor real** do lote (DEBORA, BRUNO, JOSE DO ALHO, CLIONALDO…) está em `NOMEPARC_ORIGEM` da view `ANDRE_IAGRO_SALDO_LOTE` — vem do `TGFPAR.NOMEPARC` do parceiro da TOP 11 (compra de origem).

**Ao construir filtros/typeaheads que falam de "fornecedor" do lote**, usar `NOMEPARC_ORIGEM`. `TGFPRO.FABRICANTE` só vale se você realmente quer o que está cadastrado lá (nome do produto, na prática).

**Função do typeahead preserva nome legado:** `consultar_fabricantes_disponiveis` foi refatorada em Mai/2026 pra consultar `NOMEPARC_ORIGEM`, mas o nome de função e parâmetro `fabricante` foram mantidos por retrocompat. Semanticamente, o campo "fabricante" no IAgro virou sinônimo de "fornecedor do lote".

---

## CSS

### `:root` do `rastreio.css`

Define `--ras-*` (tokens locais do Rastreio). **Outros módulos não devem importá-los** — usar tokens globais do `global.css`.

### `!important` em `.btn-acao-linha`

Necessário porque a classe legada `.btn-olho` tem mesma especificidade. Ao remover regras antigas no futuro, **revisar e tirar os `!important`**.

### `:has()` CSS no Rastreio

Estilização dependente de checkbox. **Requer Chrome 105+, Safari 15.4+, Firefox 121+.** Consistente com público alvo (operadores em desktops corporativos), mas validar antes de aplicar em outros módulos.

---

## Phosphor font-icon dentro de `.btn-acao-linha` precisa `font-size` explícito

`.btn-acao-linha` em `rastreio.css` tem `font-size: 0` (legado pra zerar emojis antigos). SVGs (`.btn-armar svg`, `.btn-olho svg`) usam `width/height` próprios — escapam. **Phosphor font-icons (`<i class="ph ph-xxx">`) dependem de `font-size` pra renderizar** — caem no reset e ficam invisíveis.

**Fix aplicado (Mai/2026):**
```css
.btn-acao-linha .ph {
    font-size: 14px;
    line-height: 1;
}
.rastreio-card.compacto.linha-ativa .btn-acao-linha .ph,
.produto-linha.linha-ativa .btn-acao-linha .ph {
    font-size: 17px;
}
```

**Regra:** ao adicionar novo botão de ação na linha do Rastreio com Phosphor, garantir que o `.ph` herda font-size do bloco acima. Se for botão sempre visível (como `.btn-etiqueta`), sobrescrever `opacity: 1 !important` pra escapar do default oculto.

---

## QTDFIXADA em pedidos antigos é NULL — operador re-vincula com peso

Etiquetas SafeTrace/IAgro (Mai/2026) calculam nº de cópias via `qtdneg / qtdfixada`. Pedidos atribuídos **antes** do campo "Peso da caixa" existir no modal têm `TGFITE.QTDFIXADA = NULL` → backend retorna 400.

**Resolução operacional (pra cada pedido antigo):** desvincular o lote (lixeira no modal de vínculos) → re-armar o lote → re-vincular informando o peso. Função `atribuir_lote_item_pedido` agora aceita `qtdfixada` como parâmetro obrigatório do frontend.

**Backfill via SQL é possível mas é Cat B** — antes de rodar UPDATE em massa, abrir plano Cat B dedicado.

---

## Service Windows (NSSM) não recarrega Python automaticamente

Em produção, o IAgro roda como serviço Windows via NSSM. Quando código `.py` muda, **o serviço precisa restart explícito**:

```cmd
nssm.exe restart IAgro
```

Sintoma típico: mensagem de erro antiga continua aparecendo mesmo depois de "consertar" o código. Cobra restart antes de assumir que o fix não funcionou.

Mudanças em **HTML/CSS/JS** não exigem restart — só `Ctrl+F5` no navegador (alguns arquivos usam `?v=N` querystring que precisa ser bumpado quando muda).

---

## PESO × QTDFIXADA na TOP 11 — semântica e espelhamento

`TGFITE.PESO` (peso da caixa, digitado pelo operador da Entrada) e `TGFITE.QTDFIXADA` (peso classificado, "congelado" pra etiqueta/vale) são campos distintos mas **na Agromil carregam o mesmo valor** quando o produto é não-classificável (in natura direto, `GERAPRODUCAO ≠ 'S'`).

Mecanismos de espelhamento implementados em Mai/2026 (B1-B6 — vide [`modules/comercial.md`](modules/comercial.md) → "Fluxo do peso"):

- **B5** — `inserir_item_nota_banco`: espelha QTDFIXADA = PESO no INSERT quando GERAPRODUCAO≠'S' e PESO>0.
- **B4** — `salvar_vale_compra_banco`: ao salvar, se só um dos 2 campos da TOP 11 origem está preenchido, espelha bidirecional antes de propagar pra TOP 13.
- **B3** — `atualizar_peso_comercial_entrada`: alteração tardia da TOP 11 propaga PESO pra TOP 13 imediatamente.

**Bug latente corrigido**: SELECT inicial do B1 tinha filtro `GERAPRODUCAO='S'` que bloqueava o salvar vale de produto não-classificável mesmo com QTDFIXADA preenchida (in natura tem GERAPRODUCAO='N'). Filtro removido em B4 — agora lê qualquer linha do lote.

**Em produtos classificáveis (GERAPRODUCAO='S')**: PESO (entrada) e QTDFIXADA (classificação) podem legitimamente diferir. Espelhamento só age quando um dos 2 está vazio.

---

## TGFFIN.NUMNOTA é NUMBER — texto livre em campo de NF rejeita Oracle

Quando operador digita "NF 12345" ou "boleto Allianz" num campo destinado a `TGFFIN.NUMNOTA` (Sankhya define como NUMBER), o INSERT/UPDATE explode com `ORA-01722: invalid number`.

**Solução padrão** aplicada no abastecimento externo (Combustível, B8 — Mai/2026, 2026-05-15):

1. **Frontend**: `<input type="number" inputmode="numeric">` + validação JS `/^\d+$/` antes do submit.
2. **Backend**: parse numérico estrito; se falhar, retorna erro humanizado: `"Nº da nota fiscal deve ser apenas números (digite 12345, não NF 12345)."`.

Quando aplicar em outros módulos: qualquer campo `NUMNOTA` editável pelo operador (TGFCAB ou TGFFIN). `AD_REQUISICAO_COMBUSTIVEL.DOC_FRETE_REF` continua aceitando texto pra preservar auditoria — só o NUMNOTA real é restrito.

---

## Imagem de fundo das páginas — só no `.app-content`, não no `body`

A imagem `html-bg.png` (Mai/2026) é aplicada no `.app-content`, **não no body**. Razão: `body.app-shell` é display flex contendo sidebar + content; aplicar imagem no body cobriria a sidebar (que tem fundo escuro próprio) com renderização imprevisível.

Overlay branco-suave `rgba(244,246,244,0.92)` calibrado pra preservar legibilidade dos painéis. `background-attachment: fixed` evita "rolagem" da imagem ao scrollar painéis internos.

Pra trocar a imagem: substituir `html-bg.png` no mesmo path (`static/sankhya_integration/`). Pra ajustar intensidade do overlay: editar o `0.92` na regra `.app-content` (95% = mais discreta; 80% = mais visível). Pra desativar completamente, comentar a propriedade `background` mantendo só `background-color: var(--cor-content-bg)`.

---

## Mobile no iPhone Safari — `100vh` cobre o footer + `env(safe-area-inset)` exige `viewport-fit=cover`

Dois pegadinhas combinadas no Safari iOS (descobertas Mai/2026 — 2026-05-15):

### 1. `100vh` no iOS NÃO desconta a barra inferior do Safari

`100vh` é a altura TOTAL da viewport, **incluindo** a área coberta pela barra de navegação dinâmica (botões ←/→/+/abas). Modal `height: 100vh; display: flex; flex-direction: column` com header + body + footer empurra o footer pra **embaixo da barra**, invisível.

**Sintoma típico:** botão "Salvar" do modal de nova requisição/entrada do Combustível sumindo no iPhone. Operador rola dentro do body do modal e nunca chega no footer.

**Solução**: usar **`100dvh`** (dynamic viewport height — desconta barras dinâmicas) com fallback pra `100vh` em browsers antigos:

```css
.cb-modal-card {
    height: 100vh !important;       /* fallback */
    max-height: 100vh !important;
    height: 100dvh !important;      /* iOS Safari moderno */
    max-height: 100dvh !important;
}
```

`dvh` é suportado em iOS 15.4+ (universal hoje). Browsers antigos ignoram a 2ª regra e ficam com `100vh` (defeituoso mas não quebra).

### 2. `env(safe-area-inset-bottom)` retorna 0 sem `viewport-fit=cover` no meta

Por padrão, iOS Safari NÃO injeta os `safe-area-inset-*` no CSS. Pra ativar, o meta viewport precisa de `viewport-fit=cover`:

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

Sem isso, `padding-bottom: env(safe-area-inset-bottom, 0px)` adiciona 0 → home-indicator + barra Safari continuam cobrindo conteúdo. Aplicado em `base.html` e `home_login.html` em 2026-05-15.

### 3. Buffer de 90-100px no `.main-layout` e containers internos com scroll

Mesmo com `100dvh` e `viewport-fit=cover`, conteúdo dentro de containers com `overflow-y: auto` (`.entrada-grid`, `.classificacao-grid`, `.venda-grid`, `.rastreio-layout`, `.cb-layout`, `.layout` do Comercial) precisa de `padding-bottom: calc(90px + env(safe-area-inset-bottom, 0px))` em ≤900px e `100px+env` em ≤520px — caso contrário a barra Safari cobre os últimos elementos.

**Por que 90px fixos** (não só env)? `env(safe-area-inset-bottom)` retorna ~34px no iOS com home-indicator (PWA) ou 0 fora de PWA. A barra de navegação do Safari iOS comum tem ~80-90px que **não é refletida em env()** — daí o buffer fixo.

### Checklist pra qualquer página/modal nova

- Página vai estender `base.html` (já tem `viewport-fit=cover` desde 2026-05-15)?
- Container interno com `overflow-y: auto` tem `padding-bottom: calc(90px + env(safe-area-inset-bottom, 0px))` em ≤900px?
- Modal fullscreen mobile usa `100dvh` (não só `100vh`)?
- Modal flex column tem `flex-shrink: 0` no header e footer pra footer não ser empurrado pra fora?
- Algum `body.app-shell .main-layout { padding: 0 }` específico do módulo? Se sim, reaplicar safe-area dentro do `@media ≤900px` (caso do `home.css`).

---

## `dblclick` não dispara em iOS Safari/Chrome + DevTools mobile emulation

Limitação conhecida do **WebKit/WKWebView**: o evento `dblclick` é suprimido em touch screen em favor do gesto de double-tap-to-zoom. Vale pra:

- iPhone Safari (todas as versões)
- Chrome iOS, Firefox iOS, Edge iOS (todos usam WKWebView)
- Chrome DevTools com "Toggle device toolbar" ativado (emula touch)

**Sintoma:** linha de tabela com `addEventListener('dblclick', ...)` que abre modal de edição funciona em desktop, NÃO funciona no celular. Cliques simples viram seleção mas o duplo nunca dispara.

### Solução padrão — `IAgro.onDoubleActivate`

Helper em [`iagro_helpers.js`](../sankhya_integration/static/sankhya_integration/iagro_helpers.js) (Mai/2026 — 2026-05-15):

```js
IAgro.onDoubleActivate(element, handler, {
    delegateSelector: 'tr.row--click',   // opcional: event delegation
    tapWindowMs: 350,                     // opcional: janela do double-tap
});
```

Registra `dblclick` nativo + fallback manual via `click + timer` quando o device é touch-capable (`'ontouchstart' in window || pointer:coarse || maxTouchPoints>0`). Sem dedup necessário — desktop puro nunca recebe touch event, mobile nunca dispara `dblclick` nativo.

### Migração

Substituir:
```js
el.addEventListener('dblclick', (ev) => { ... });
```
Por:
```js
IAgro.onDoubleActivate(el, (ev, target) => { ... }, { delegateSelector: 'tr' });
```

Aplicado em 5 lugares (Mai/2026): `entrada.js` (notas e itens), `classificacao.js` (item-row e tabela dinâmica), `venda.js` (pedidos).
