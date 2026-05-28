# Pontos de Atenção (Armadilhas Técnicas)

Lista de pegadinhas que **já causaram bugs** ou que podem causar se tocadas sem cuidado. Tratar como avisos críticos.

---

## Página `compras/central/` foi removida — só ramo AJAX vivo (Mai/2026 — 2026-05-27)

A página `/sankhya/compras/central/` (template `compras_central.html`) foi **removida no início do projeto** quando o fluxo migrou pra modais no Portal. O template **não existe** no projeto, mas o código deixou referências mortas espalhadas em vários lugares — descoberto quando o redesign mobile da Entrada tentou redirecionar pra essa URL e quebrou com `TemplateDoesNotExist`.

**Limpeza aplicada (Mai/2026 — 2026-05-27):**
- `view_central_compras` (views.py) — agora retorna **410 Gone** quando acessada como página HTML; mantém só o ramo `?ajax_header=1` (JSON) que o desktop usa pra preencher o modal de edição de cabeçalho
- `api_salvar_novo_cabecalho` — removidos `redirect(/compras/central/?nunota=)` e `render(compras_central.html)` mortos; agora retorna JSON em todos os casos
- `entrada.html` — `<a id="btnNew" href="/sankhya/compras/central/?codtipoper=11">` → `<button id="btnNew" type="button">` (JS já interceptava o click e abria `#cabModal` direto)
- `entrada.html` — `data-central-url="..."` removido das `<tr class="row--click">`
- `entrada.js` — `CENTRAL_AJAX` removido do `API_URLS`. 3 navegações `window.location.href = API_URLS.CENTRAL_AJAX...` substituídas por `closeTopModal() + showCabModal()` direto. Mantém URL hardcoded `?ajax_header=1` pra fetch da edição
- `entrada_mobile.js` — handler do `m_btnCabecAbrirCentral` removido (botão "Abrir editor" do bottom sheet de cabeçalho substituído por edição inline com `?ajax_header=1`)
- `README.md` — linha `/sankhya/compras/central/` das rotas principais removida

**Endpoints que CONTINUAM funcionais e devem ser preservados:**
- `POST /sankhya/compras/central/salvar/` → `api_salvar_novo_cabecalho` — POST funcional usado pelo `entrada.js` (HEADER_SAVE), `classificacao.js`, `entrada_mobile.js` (sheet Nova Nota)
- `GET /sankhya/compras/central/?nunota=X&ajax_header=1` → retorna JSON com dados do cabeçalho pra preencher modais (paridade Entrada Desktop e Mobile)

**Lição**: ao remover features grandes, **fazer grep cego pelas referências** depois do refactor. Código morto pode ficar latente por meses até quebrar — o redesign mobile só revelou o bug porque tentou seguir a URL que o desktop interceptava via JS antes de navegar.

---

## Rastreio Mobile — bugs descobertos (Mai/2026 — 2026-05-28)

### Endpoint de lotes retorna `data.lotes`, não `data.itens`

Padrão dos endpoints de listagem do projeto varia:

- `api_rastreio_lotes_disponiveis` (em `views.py`) → retorna `{ok: True, lotes: [...]}`
- `api_rastreio_pedidos_abertos` → retorna `{ok: True, itens: [...]}`

Bug real: o mobile lia `data.itens` em ambos. Resultado: lista de lotes ficava sempre vazia ("Nenhum lote no período"). Fix: `data.lotes` em `carregarLotes`.

**Regra geral**: ao consumir endpoint novo, conferir o nome do array de retorno (`lotes`, `itens`, `vinculos`, `pedidos`, etc.) — não assumir padrão único.

### Endpoint de pedidos retorna `qtd_pedida`/`codagregacao_atual`, não `qtdneg`/`codagregacao`

`consultar_pedidos_abertos_para_atribuicao` define `cols`:
```python
cols = [
    'nunota', 'numnota', ...,
    'sequencia', 'codprod', 'descrprod',
    'qtd_pedida', 'codagregacao_atual', 'status_item',
    ...
]
```

Bug real: `agruparPedidos` no mobile lia `it.qtdneg` (do TGFITE raw) e `it.codagregacao` — ambos undefined. Cards mostravam `0,00 / 0,00 kg` em todos os pedidos. Fix com fallback robusto:

```js
const qtd = Number(it.qtd_pedida ?? it.qtdneg) || 0;
const codag = it.codagregacao_atual ?? it.codagregacao ?? null;
```

**Lição**: o backend cria aliases convenientes nos `cols` quando faz `dict(zip(cols, row))` — o nome enviado pra frontend não é necessariamente o da coluna Oracle.

### CSS `display: flex` sobrescreve atributo HTML `hidden`

Ao usar `display: flex/grid` na classe base + atributo `hidden` pra esconder dinamicamente:

```html
<div id="lista-a" class="m-ras-list"></div>
<div id="lista-b" class="m-ras-list" hidden></div>
```

```css
.m-ras-list { display: flex; flex-direction: column; }
```

→ User-agent stylesheet aplica `[hidden] { display: none }`, mas a regra customizada `.m-ras-list { display: flex }` é mais específica e vence. **Ambas as listas ficam visíveis sobrepostas**.

Fix obrigatório:
```css
.m-ras-list[hidden] { display: none !important; }
```

Padrão a aplicar sempre que misturar `display: flex/grid` com toggle via `hidden`. Em Mai/2026 — 2026-05-28 isso causou "lista de pedidos não aparece quando troca toggle no Rastreio Mobile".

### Refresh `AD_SALDO_LOTE_CACHE` em paralelo com queries de pedidos → 500

`POST /api/refresh-saldo/` faz **TRUNCATE + INSERT-SELECT** na tabela materializada (~12s). Durante essa janela, `consultar_pedidos_abertos_para_atribuicao` faz JOIN com `AD_SALDO_LOTE_CACHE` pra trazer origem do lote → query pode dar erro Oracle (transação concorrente) → endpoint retorna 500.

Bug real (Mai/2026 — 2026-05-28): após vínculo no mobile do Rastreio, eu disparava `refresh-saldo` em background + `carregarPedidos` em paralelo. 500 no console.

**Fix**: não disparar refresh-saldo **automático** após escritas. Usar **atualização local do estado JS** pra feedback imediato (subtrai qtd do lote vinculado no `ESTADO.lotesData`, remove da lista se zerou). Cron natural sincroniza em ≤5min. Operador força refresh manualmente via FAB Mais se quiser sincronizar antes.

**Padrão geral**: refresh-saldo é operação **manual**, dispara só por click explícito. Nunca em paralelo com outras queries que leem `AD_SALDO_LOTE_CACHE`.

### `opacity` em card com botão swipe atrás → vaza visualmente

Bug em cards "finalizados" do Rastreio Mobile: o card tinha `opacity: 0.85` pra indicar "completado". Mas a opacidade fazia o **botão azul de swipe (escondido atrás) aparecer através do card** — operador via olho ao lado do card sem ter feito swipe.

Fix: trocar `opacity: 0.85` por mudança de cor sutil (`background: #f6fbf4` verde bem claro + borda esquerda verde). Mantém indicação visual de "completo" sem transparência.

**Regra**: nunca usar `opacity < 1` em cards que tenham elementos `position: absolute` escondidos atrás (botões swipe, etc.). Use `background-color` ou `filter: brightness()` no lugar.

### Swipe bidirecional precisa 2 atributos de estado independentes (Mai/2026 — 2026-05-28)

Cards do Rastreio Mobile ganharam swipe-direita (avaria de ajuste) **em adição** ao swipe-esquerda existente (armar + olho). Tentativa inicial reaproveitou só `data-swipe-open="1"` pra ambos os lados — bug imediato: abrir esquerda + tentar abrir direita não funcionava (touchmove tratava o dx contrário como "fechando o swipe atual").

**Fix**: 2 atributos independentes no wrapper:
- `data-swipe-open="1"` → swipe-esquerda aberto (armar + olho 88px)
- `data-swipe-right="1"` → swipe-direita aberto (avaria 60px)

No `touchmove`, decide `translateX` lendo qual dos 2 está aberto. No `touchend`, decide com base no `dx` final qual atributo setar. **`fecharTodosSwipesLotes()` zera os dois**. Em `setActiveScreen` + `openSheet`, ambos zerados (mesma chamada).

**Regra geral**: ao adicionar swipe na outra direção num card que já tem swipe, criar **atributo de estado dedicado** (não reaproveitar o existente). Touchmove/touchend precisam ler ambos pra decidir o `translateX` correto. CSS pode reaproveitar a estrutura `position: absolute` — só os atributos JS é que são separados.

---

## Redesign Mobile — armadilhas conhecidas (Mai/2026 — 2026-05-27)

### Comentários Django `{# #}` são single-line — multi-line vaza no HTML

Comentário Django `{# ... #}` **só funciona em uma linha**. Quebrar em múltiplas linhas faz o Django parar de tratar como comment e vazar todo o texto literalmente no output HTML.

Já aconteceu **4+ vezes** neste projeto (`base.html` antes, e `entrada.html` durante o redesign mobile da Entrada). Operador sempre relata texto aleatório vazando no canto da tela. **REGRA DURA**:

- ❌ NUNCA escrever `{# ... #}` que abrange ≥ 2 linhas
- ✅ Pra documentação inline em template: usar `{% comment %}...{% endcomment %}`
- ✅ Pra notas curtas: `{# linha única #}` em uma única linha física
- ✅ Idealmente: **não documentar em template** — nomes de classes/IDs já indicam estrutura, e doc estruturada vive em `.claude/*.md`

**Validador automático** (rodar antes de cada PR mobile):

```bash
python -c "import re; txt=open('templates/.../X.html',encoding='utf-8').read(); p=re.compile(r'\{#.*?#\}', re.DOTALL); print([f'L{txt[:m.start()].count(chr(10))+1}: {m.group()[:60]}' for m in p.finditer(txt) if chr(10) in m.group()] or 'OK')"
```

### Override em `@media (max-width: 375px)` pode esconder compactação

Bug real durante o redesign mobile da Entrada: o bloco `@media (max-width: 375px)` no fim do `entrada.css` tinha valores **maiores** (`padding: 10px 12px`, `avatar 38px`, `font 14px`) que sobrescreviam toda a compactação principal. Como a maioria dos celulares (iPhone SE 375px, Galaxy 360px, iPhone 12 mini 375px) cai nessa media query, **ela vencia silenciosamente** e o operador via cards grandes mesmo após várias rodadas de "diminui mais".

**Lição**: ao usar `@media (max-width: 375px)` ou similar pra ajustar viewports estreitos, sempre verificar se os valores estão **MENORES** que os principais — caso contrário a regra vira override desnecessário. Idealmente nem ter esse bloco — deixa o mobile-first padrão valer pra todos os tamanhos.

### Campo removido do HTML mas JS ainda lê → `Cannot read properties of null`

Aconteceu no redesign mobile da Entrada: removi o campo `m_novaNF` do template (quando ajustei pra paridade exata com `#cabModal` desktop que não tem NF), mas esqueci de remover `var nf = $m('m_novaNF').value.trim();` no JS. O click no Salvar quebrava com `Cannot read properties of null (reading 'value')`.

**Padrão a aplicar**: quando remover um input do HTML, fazer **grep do ID** no JS e remover todas as referências. Não dá pra confiar só em "testar a página" porque o erro só aparece no fluxo de salvar (que ninguém testa toda vez).

### IDs duplicados no DOM mobile — `getElementById` retorna só o primeiro

Quando o template mobile tem **várias telas no DOM ao mesmo tempo** (cada `<section class="m-screen">`), é fácil duplicar IDs sem perceber porque só uma tela é visível por vez. `document.getElementById('m_itemPeso')` retorna **sempre o primeiro** do DOM — se for o de uma tela escondida, vai parecer que listeners não disparam, cálculo retorna 0, valor não popula, etc.

**Bugs reais dessa categoria** descobertos em 2026-05-27:
1. **`m_itemPeso` duplicado**: tela 3 "Conferir item" (oculta) + sheet "Itens-nota" (ativo). `recalcTotalItem` lia o oculto → peso=0 sempre → Total mostrava só Qtd
2. **`.m-toggle-row` querySelector**: pegava o primeiro do DOM (tela 3) → `.is-invalid` não aplicava no sheet de Itens visível → botões Sim/Não não ficavam vermelhos

**Convenção pra evitar**: prefixos por tela/contexto:
- `m_item*` → sheet de Itens (inserir/editar produto)
- `m_conf_*` → tela "Conferir item"
- `m_edit*` → sheet de Cabeçalho (editar nota)
- `m_filtro*` → sheet de Filtros
- `m_nova*` → sheet de Nova nota

Antes de adicionar campo novo, validar IDs duplicados:

```python
import re
from collections import Counter
with open('templates/.../arquivo.html', encoding='utf-8') as f:
    ids = re.findall(r'id="([^"]+)"', f.read())
dup = [(k,v) for k,v in Counter(ids).items() if v > 1]
print('Duplicados:', dup or '(nenhum)')
```

Pra coleções de classe (`.m-toggle-row`, `.m-card-item`, etc) usar **seletor escopado**: nunca `document.querySelector('.m-toggle-row')` direto, sempre âncora a partir de algo único da tela (ex: `document.querySelector('.m-toggle-btn[data-classifica-item]').closest('.m-toggle-row')`).

### iOS Safari faz zoom em inputs com `font-size < 16px`

Comportamento nativo do Safari iOS: ao focar input com `font-size` menor que 16px, browser dá zoom (acessibilidade). UX desagradável — operador vê a página "pular" toda vez que toca num campo.

**Fix**: `font-size: 16px` mínimo em `.m-field-input` e variantes. Mesmo que pareça grande visualmente, em mobile o cálculo de altura de linha + padding compensa.

Documentado em [`conventions.md`](conventions.md) → "iOS Safari — pegadinhas".

### `input[type=number]` rejeita strings com vírgula

Quando JS faz `input.value = '23,5'` num `type=number`, o browser **silenciosamente seta valor vazio** porque a vírgula não é separador decimal válido pra type=number (que segue padrão JS/JSON com `.`).

Bug real (2026-05-27): `abrirEditItem` no mobile preenchia Peso/Qtd com `String(num).replace('.', ',')` (legado de quando inputs eram type=text). Resultado: campos ficavam vazios em modo edit, operador via "só Produto e Vol preencheram".

**Fix**: sempre `String(num)` com ponto. Pra exibir formatado em pt-BR, usar `toLocaleString('pt-BR')` apenas em campos `type=text` (readonly de display, ex: "Total kg calculado").

### Swipe-to-edit/delete fica "preso" se não resetar entre navegações

Operador arrasta card pra revelar botões. Sem clicar nos botões, navega pra outra tela. Volta pra lista → cards continuam com `transform: translateX(...)` aplicado e `data-swipe-open="1"`. Visual quebrado.

**Fix**: função `fecharTodosSwipesNotas()` que itera todos `[data-swipe-open="1"]` e zera transform + dataset. Chamada em:
- `setActiveScreen(name)` — cobre push/pop/popToRoot
- `openSheet(name)` — cobre Nova Nota / Cabeçalho / Itens

Sem essas duas chamadas, swipes ficam "presos" entre navegações.

### Restart NSSM obrigatório após mudança no template Django

NSSM cacheia templates Django. Mudança no `.html` não reflete automaticamente — precisa `nssm.exe restart IAgro` (já documentado em outro gotcha mas vale reforçar pro contexto mobile, porque o operador testa hard refresh no celular e nada muda).

### iOS Safari — `change` em `<input type="date">` dispara só quando picker fecha

No iPhone, ao tocar num `<input type="date">` abre o picker nativo. Operador escolhe data. **`change` event** só dispara quando ele aperta "Pronto/OK" — não a cada rotação dos spinners. No DevTools mobile do Chrome (emulação), `change` dispara mais agressivamente, mascarando o bug.

Sintoma típico: handler que depende de `change` (ex: replicar data inicial em data final) funciona no simulador mas falha no iPhone real.

**Fix**: registrar `input` listener **além** de `change`:

```js
inputIni.addEventListener('change', replicar);
inputIni.addEventListener('input', replicar);
```

Mais broadly: pra inputs type=date/datetime-local no mobile, sempre combo `change + input`.

### IntersectionObserver em lista infinita faz cascata quando append não desloca scroll

Tentativa inicial de lista infinita usou `IntersectionObserver` com `rootMargin: '200px'` numa sentinela no fim da lista. Funciona em listas onde o append empurra a sentinela pra fora do viewport. Mas se o operador rola até o fim e a sentinela permanece visível (cards anexados acima dela não deslocam o scroll), **observer fica em loop**: detecta intersect → chama carregarMais → render append → nova sentinela cai dentro do viewport de novo → detecta intersect → carregarMais → ...

Bug real (2026-05-27): operador deixou aberto sem buscar, server tomou 94 requests `?page=2..94` em ~60s. Tive que parar o servidor.

**Fix**: substituir por **scroll listener tradicional** com comparação `lastScrollTop`:

```js
scrollArea.addEventListener('scroll', function () {
    if (pgInfinita.carregando || !pgInfinita.hasNext) return;
    var st = scrollArea.scrollTop;
    if (st <= lastScrollTop) { lastScrollTop = st; return; }   // ignora scroll pra cima
    lastScrollTop = st;
    var threshold = scrollArea.scrollHeight - scrollArea.clientHeight - 200;
    if (st >= threshold) carregarMaisNotas();
}, { passive: true });
```

Vantagens:
- Só dispara em scroll **real** do operador
- Ignora scroll pra cima (`st <= lastScrollTop`)
- Threshold recalculado a cada evento (não tem "trigger zone" permanente)
- Sem callback após append silencioso

E se for fazer auto-paginação com busca (loop sem scroll), adicionar `setTimeout` entre iterações + flag cancelável quando operador limpa busca:

```js
var autoPaginarTimer = null;
function autoPaginarComBusca() {
    if (autoPaginarTimer) clearTimeout(autoPaginarTimer);
    /* ... guards ... */
    autoPaginarIters++;
    autoPaginarTimer = setTimeout(function () {
        /* re-checa antes de disparar */
        carregarMaisNotas();
    }, 250);
}
```

### Filtro client-side esconde só o card — botões de swipe ficam pendurados

Cards com swipe-to-edit/delete têm estrutura wrapper > botões absolutos + article visível:

```html
<div class="m-card-nota-wrap">
    <button class="m-card-nota__swipe-edit">...</button>
    <button class="m-card-nota__swipe-del">...</button>
    <article class="m-card-nota">...</article>
</div>
```

Quando o filtro do campo de busca esconde via `card.style.display = 'none'`, **só o article some** — os botões absolutos (que vivem fora do article, dentro do wrapper) continuam visíveis no DOM, criando linhas de "lápis + lixeira" pendurados sem card por trás. Visual quebrado relatado em 2026-05-27.

**Fix**: sempre esconder o **wrapper inteiro**:

```js
var wrap = card.closest('.m-card-nota-wrap') || card;
wrap.style.display = match ? '' : 'none';
```

Vale pra qualquer filtro futuro (data, parceiro, status) que esconda linhas em lista com swipe.

### Cache de browser mobile — sempre bumpar `?v=N`

Mobile (especialmente iPhone Safari) agressivo no cache de CSS/JS. Sem `?v=N` bump explícito no template, browser pode servir arquivo velho mesmo após hard refresh.

Padrão obrigatório a cada PR:

```html
<link rel="stylesheet" href="{% static 'sankhya_integration/entrada.css' %}?v=35">
<script src="{% static 'sankhya_integration/entrada_mobile.js' %}?v=27" defer></script>
```

Sequência atual da Entrada Mobile (Mai/2026 — 2026-05-27): CSS `?v=35` · JS `?v=27`. Bumpar a cada mudança.

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

### Trigger `TRG_INC_UPD_TGFITE_PRODNFE` popula GTINNFE/GTINTRIBNFE automaticamente (Mai/2026 — 2026-05-27)

Os campos fiscais `GTINNFE` (EAN13 da NFe) e `GTINTRIBNFE` (EAN13 tributário) em TGFITE **não são preenchidos pelo IAgro** — são populados pela trigger nativa Sankhya `TRG_INC_UPD_TGFITE_PRODNFE` (BEFORE INSERT OR UPDATE).

Lógica do trigger:
```
TGFPRO.TIPGTINNFE = 0  → GTINNFE = NULL
TGFPRO.TIPGTINNFE = 1  → GTINNFE = CODPROD
TGFPRO.TIPGTINNFE = 3  → GTINNFE = TGFEST.CODBARRA[:14]
TGFPRO.TIPGTINNFE = 4  → GTINNFE = TGFVOA.CODBARRA[:14] OR TGFPRO.REFERENCIA[:14]
outros (2, 5...)       → GTINNFE = TGFPRO.REFERENCIA[:14]
```

`GTINTRIBNFE` segue lógica análoga lendo `TGFVOA.TIPGTINNFE` + `TGFVOA.CODBARRA`. Sem `TGFVOA`, geralmente cai em `GTINTRIBNFE = GTINNFE`.

**Conclusão**: se um produto não tem `TGFPRO.REFERENCIA` cadastrado (ex: CHUCHU MÉDIO CODPROD 352), GTINNFE/GTINTRIBNFE ficam NULL na TGFITE — tanto INSERT via desktop quanto mobile. Não é bug de código IAgro — é cadastro fiscal do produto faltando no Sankhya.

**Diagnóstico do operador**: cadastrar EAN13 no campo "Referência" do produto via tela nativa Sankhya. Linhas TGFITE antigas não retroagem — operador edita manualmente se precisar.

### CODVOLPARC divergente — desktop força `item_vol = 'KG'` ao abrir modal (Mai/2026 — 2026-05-27)

Bug histórico: lançamento via mobile resultava em `TGFITE.CODVOLPARC='CX'`, enquanto via desktop ficava `'KG'`. Mesmo trigger Sankhya, mesmo endpoint backend.

**Causa**: o backend `api_salvar_item_nota` ([views.py:1069-1075](../sankhya_integration/views.py#L1069)) tem normalização condicional:
```python
vol_digitado = str(payload.get('CODVOL') or payload.get('VOL') or 'KG').strip().upper()
payload['CODVOLPARC'] = vol_digitado          # preserva o original
if vol_digitado in ('CX', 'SC'):
    payload['CODVOL'] = 'KG'                  # CODVOL vira KG
else:
    payload['CODVOL'] = vol_digitado          # CODVOL preserva
```

O desktop em `showItemsModal` ([classificacao.js:672](../sankhya_integration/static/sankhya_integration/classificacao.js#L672)) executa `volEl.value = 'KG'` ao abrir o modal, **sobrescrevendo o default 'CX' do HTML**. Mobile não fazia isso e mandava `codvol: 'CX'` (default da hidden), resultando em CODVOLPARC='CX' depois da normalização.

**Fix mobile**: payload de `salvarItemClassificacao` agora hardcode `codvol: 'KG'` na linha do payload — paridade desktop. Validado via comparação TGFITE NUNOTA 113878 (mobile) vs 113879 (web): `CODVOLPARC='KG'` em ambos.

### Trigger `TRG_UPT_TGFITE` exige `RESERVA`/`ATUALESTOQUE`/`USOPROD` em TOP de venda (Mai/2026 — 2026-05-20)

Pedido criado pelo IAgro (TOP 34) salva normalmente, mas ao abrir/imprimir no Sankhya o `STP_CONFIRMANOTA2` dispara UPDATE em TGFITE e o trigger rejeita:

```
ORA-20101: Reserva diferente da definicao na TOP.
ORA-06512: em "SANKHYA.TRG_UPT_TGFITE", line 734
ORA-06512: em "SANKHYA.STP_CONFIRMANOTA2", line 413
```

**Causa**: o trigger compara `NEW.RESERVA` com a definição de reserva da TOP. **TOP 34 espera `'S'`** (pedido reserva estoque); **TOP 35/37 espera `'N'`** (venda já efetivada, não reserva). INSERT do IAgro deixava `RESERVA='N'` em TOP 34 — daí o trigger rejeitar UPDATE posterior. INSERT em si passa (BEFORE INSERT mais permissivo), mas qualquer UPDATE posterior (impressão, faturamento, recálculo) bate na validação BEFORE UPDATE.

**Diagnóstico** (Mai/2026 — 2026-05-20): comparação direta TGFITE NUNOTA=113083 com 1 item IAgro vs 1 item Sankhya nativo identificou 3 campos divergindo de forma que aciona o trigger:

| Campo | TOP 34 esperado | TOP 35/37 esperado | Significado |
|---|---|---|---|
| `RESERVA` | `'S'` | `'N'` | Reserva estoque (pedido) vs já efetivado (nota) |
| `ATUALESTOQUE` | `1` | `-1` | `1` = "atualiza ao faturar", `-1` = "ignora" (TOP 35/37 já saiu da reserva pra estoque real) |
| `USOPROD` | `TGFPRO.USOPROD` (fallback `'R'`) | mesmo | Vem do cadastro do produto |

**Fix aplicado** em 2 caminhos distintos:
1. [`inserir_item_nota_banco`](../sankhya_integration/services/oracle_conn.py) (cria TGFITE de pedido TOP 34): SELECT da TGFCAB ganhou `CODTIPOPER`; quando TOP ∈ (34, 35, 37), INSERT preenche `RESERVA='S'`, `ATUALESTOQUE=1`, `USOPROD=<TGFPRO.USOPROD>` (fallback `'R'`). Schema-resilient (`if 'COL' in colunas_tabela`).
2. [`faturar_pedido_venda_banco`](../sankhya_integration/services/oracle_conn.py) (caminho C, cria TGFITE de nota TOP 35/37): após o INSERT espelhado, faz UPDATE setando `RESERVA='N'` e `ATUALESTOQUE=-1` — semântica de venda já efetivada. **Em TOP 35/37 esses valores são o correto**, NÃO bug.

**Escopo do fix**: só pedidos novos criados após 2026-05-20. Pedidos antigos criados antes do fix continuam com `RESERVA='N'` — qualquer impressão/faturamento dispara o erro. Solução pontual: operador pode UPDATE manual no Sankhya, ou criar script de backfill (Cat B). Como Agromil está começando a usar IAgro pra vendas agora (Mai/2026), o volume de pedidos antigos quebrados é pequeno — backfill não foi feito.

**Outras divergências menores** (NULL no IAgro vs `0.0`/valor no Sankhya): `NUTAB`, `CODTRIB`, `ALIQICMS`, `ALIQIPI`, `CUSTO`, `M3`, vários `VLR*MOE`, `BASEST*`, `INDREPDES`, `CODSIT08EFD`. Não disparam o trigger porque são opcionais/recalculáveis. Sankhya os preenche internamente quando precisa (ao confirmar, faturar, calcular impostos).

**Mesmo bug no SPLIT do Rastreio (Mai/2026 — 2026-05-25)**: `atribuir_lote_item_pedido` quando faz **SPLIT** (atribuição parcial, `qtd < QTDNEG`) cria linha nova via `INSERT INTO TGFITE ... SELECT ...` copiando do original — mas o INSERT antigo listava só 12 colunas e **não incluía `RESERVA`, `ATUALESTOQUE`, `USOPROD`**. Resultado: linha nova nascia com defaults Oracle (`RESERVA='N'`, etc) em pedido TOP 34, e na emissão da NFe pelo Sankhya o módulo Java rejeitava o item (trigger `TRG_UPT_TGFITE` no UPDATE de `STP_CONFIRMANOTA2`) — produto sumia da nota silenciosamente. Caminho **UPDATE total** (qtd == QTDNEG) preserva os campos da linha original e não tem o bug.

**Fix do SPLIT**: INSERT agora força `RESERVA='S'`, `ATUALESTOQUE=1`, `USOPROD = NVL((SELECT USOPROD FROM TGFPRO WHERE CODPROD = TGFITE.CODPROD), 'R')` (valores corretos pra TOP 34 — guard antes da função já garante que CODTIPOPER ∈ 34/35/37; na prática SPLIT só acontece em TOP 34, mas mesmo se chegasse em TOP 35/37 a TGFCAB nova do caminho C faz UPDATE pra `'N'`/`-1` depois). Cobre inclusive SPLIT de pedidos antigos pré-fix do `inserir_item_nota_banco` — a partir do SPLIT, a linha nova já sai correta.

**Backfill aplicado em produção (2026-05-25)**: 48 linhas TGFITE em pedidos TOP 34 STATUSNOTA='L' com `CODAGREGACAO IS NOT NULL` foram corrigidas via UPDATE direto — abrange os 2 cenários (INSERT pré-fix faixa antes-20/05 + SPLIT faixa 20-25/05). NUNOTA 113155 SEQ 34 (caso reportado pelo cliente — SALVIA cortada da NFe) incluída. Pedidos antigos TOP 35/37 já emitidos com produto cortado **não retroagem** — operador trata caso-a-caso no Sankhya se aparecer demanda.

### Filtro `cliente_q` quebrado pós-refator do cache de saldo (Mai/2026 — 2026-05-25)

Sub-consequência do refator de Mai/2026 — 2026-05-19 que trocou o `FROM` de `consultar_saldo_lote_disponivel` de `SANKHYA.ANDRE_IAGRO_SALDO_LOTE` (view) pra `SANKHYA.AD_SALDO_LOTE_CACHE` (tabela materializada). O `EXISTS` do filtro `cliente_q` (cross-filter Rastreio: digita cliente nos Pedidos → Lotes mostra só CODPRODs vendidos pra ele) ainda referenciava o nome legado no `WHERE` da subquery:

```sql
WHERE i_cli.CODPROD = ANDRE_IAGRO_SALDO_LOTE.CODPROD   -- ❌ tabela fora do FROM
```

Como a view não está no FROM da query principal, Oracle não consegue resolver o nome qualificado e levanta `ORA-00904: "ANDRE_IAGRO_SALDO_LOTE"."CODPROD": invalid identifier`. Frontend mostrava toast de erro rapidamente e o painel ficava vazio — operador via "card de lotes não filtra" sem entender. Fix de 1 linha: trocar referência pra `AD_SALDO_LOTE_CACHE.CODPROD`.

**Lição** pra refators futuros: ao trocar o FROM de uma função, fazer grep de **todas as referências qualificadas** no corpo da função (incluindo subqueries em EXISTS, NOT EXISTS, IN). Subquery correlacionada que aponta pra tabela do FROM principal é o padrão mais fácil de esquecer.

---

### `QTDCONFERIDA = QTDNEG` em TOP de venda quebra "atender pedido" (Mai/2026 — 2026-05-22)

Pedidos IAgro TOP 34 **sem lote vinculado** não conseguiam ser faturados pelo Sankhya — erro:

```
[CORE_E04678] Não existem produtos/quantidades disponíveis para essa operação.
```

**Causa**: `inserir_item_nota_banco` gravava `QTDCONFERIDA = QTDNEG` por default (`qtdconferida = dados.get('QTDCONFERIDA') or qtdneg`). Faz sentido pra **Entrada** (operador confere ao receber a mercadoria), mas é errado pra **TOP de venda** (34/35/37) — pedido novo não tem nada conferido/entregue. Sankhya interpreta `QTDCONFERIDA = QTDNEG` como "item já atendido" → bloqueia o atender pedido. Sankhya nativo grava `0.0` em pedido novo.

**Diagnóstico cirúrgico**: TGFITE 113264 (IAgro, erro) vs 113259 (Sankhya nativo OK, mesmo cliente/produto/dia/STATUSNOTA/PENDENTE) — única coluna divergente:

| Campo | IAgro (errado) | Sankhya nativo (certo) |
|---|:-:|:-:|
| QTDNEG | 1.0 | 1.0 |
| **QTDCONFERIDA** | **1.0** | **0.0** |
| QTDENTREGUE | 0.0 | 0.0 |

UPDATE só `QTDCONFERIDA=0.0` no 113264 (sem mexer em mais nada) destravou o faturamento, confirmando hipótese.

**Pedidos com `ATRIBUIR_LOTE`** no Rastreio funcionavam — provavelmente alguma rota interna do UPDATE em CODAGREGACAO ou trigger Sankhya zera QTDCONFERIDA ao vincular lote. Quem nunca tinha lote vinculado ficava quebrado.

**Fix aplicado** em [`inserir_item_nota_banco`](../sankhya_integration/services/oracle_conn.py): default condicional ao CODTIPOPER do cabeçalho:
- **TOP 34/35/37** (venda) → `QTDCONFERIDA = 0.0`
- **Outros TOPs** (11/13/26/30/36/10/53) → `QTDCONFERIDA = QTDNEG` (default histórico preservado)
- Payload com QTDCONFERIDA explícita continua respeitado, inclusive `0` em TOP 11 (o `or qtdneg` antigo ignorava 0)

**Lição do diagnóstico**: o erro foi inicialmente atribuído **erroneamente a `PENDENTE='S'`** — eu vi 733 pedidos nativos com PENDENTE='N' e 152 com 'S', e assumi que 'N' era o estado correto. Mas os 733 com 'N' eram pedidos **já atendidos** (Sankhya muda pra 'N' ao atender); os 152 com 'S' eram não-atendidos — mesmo estado dos pedidos IAgro. Fix errôneo deployed e revertido em ~1 hora (commits `29bfa59` → `b826024`). **Regra**: ao comparar IAgro vs Sankhya nativo pra inferir causa, garantir mesmo estado operacional (atendido vs não-atendido, faturado vs aberto).

**Pedidos antigos pré-fix** continuam com `QTDCONFERIDA = QTDNEG`. Operador faz `UPDATE TGFITE SET QTDCONFERIDA=0 WHERE NUNOTA=X` quando encontrar, ou backfill em massa (Cat B separado) se aparecer volume.

---

### Trigger `TRG_UPD_TGFCAB` exige trio CODTIPOPER+DHTIPOPER+TIPMOV sincronizados (Mai/2026 — 2026-05-22)

Ao mudar CODTIPOPER (caso típico: UPDATE in-place pedido TOP 34 → 35/37, caminho antigo de `faturar_pedido_venda_banco`), o trigger valida 2 invariantes em sequência:

| # | Validação | Erro se falhar |
|---|---|---|
| 1 | Par `(CODTIPOPER, DHTIPOPER)` bate com linha **ativa** em TGFTOP | `ORA-20101: Tipo de operação não esta ativo. Nota de Nro Único: NNNNN` |
| 2 | `NEW.TIPMOV` == `TGFTOP.TIPMOV` da nova TOP | `ORA-20101: Esta TOP X não pode ser lançada nesta opção` |

TOPs comuns: TOP 34 (PEDIDO) tem `TIPMOV='P'`; TOP 35 e TOP 37 (VENDA) têm `TIPMOV='V'`.

**Fix se realmente precisar mudar CODTIPOPER via UPDATE**: incluir os 3 campos juntos. Buscar DHTIPOPER + TIPMOV da nova TOP em TGFTOP `WHERE CODTIPOPER=:t AND ATIVO='S' ORDER BY DHALTER DESC FETCH FIRST 1` (ou ROWNUM=1 pra 11g compat). Aplicar no mesmo UPDATE.

**Alternativa preferível (Mai/2026)**: criar TGFCAB nova (caminho C) em vez de UPDATE in-place. A função `inserir_cabecalho_nota_banco` já cuida do trio corretamente no INSERT (busca DHTIPOPER da TGFTOP via subquery). Detalhes em [`modules/venda.md`](modules/venda.md) → "Faturamento (Caminho C)".

---

### Módulo Java do Sankhya não emite NFe quando TGFCAB é criada via Oracle direto (Mai/2026 — 2026-05-22)

**Smoke A1 confirmou empiricamente**: criar TGFCAB TOP 35 + TGFITE via INSERT direto no Oracle, ajustar SERIENOTA='1', RESERVA='N', ATUALESTOQUE=-1, NUMNOTA=0, chamar `STP_CONFIRMANOTA2(nunota, 'N', 1)` → STATUSNOTA vai pra 'L' mas **STATUSNFE permanece NULL** indefinidamente. Módulo Java não pega a nota.

**Mensagem do Sankhya**: `"Documento NNNNN: Nota sem status nfe. Ignorada na impressão"`.

**Causa**: o módulo Java do Sankhya processa apenas notas criadas pela **rotina nativa de faturamento** (painel ou STP específico do menu). Essa rotina popula dezenas de campos fiscais que o IAgro **não preenche** ao criar TGFCAB direto via Oracle:

| Categoria | Campos | Origem (Sankhya nativo) |
|---|---|---|
| Geo TGFCAB | `CODCIDORIGEM`, `CODCIDDESTINO`, `CODUFORIGEM`, `CODUFDESTINO` | JOIN TSIEMP/TGFPAR.CODCID + TSICID.UF (trigger Sankhya popula no INSERT) |
| Fiscal TGFCAB | `NATUREZAOPERDES`, `CLASSIFICMS`, `INDPRESNFCE`, `INDNEGMODAL`, `TPRETISS` | Rotina Java do painel |
| Fiscal TGFITE | `CODCFO`, `CODTRIB`, `IDALIQICMS`, `NUTAB`, `ORIGPROD`, `PRODUTONFE`, `GTINNFE`, `GTINTRIBNFE` | Rotina Java + cadastro fiscal (TGFTRB) |

Quando IAgro deixa esses campos vazios, o módulo Java rejeita com `CORE_E04895`:
> `O valor do campo natOp (Descrição da Natureza da Operação) informado não é valido.`
> `O valor do campo idDest (Identificador de Local de destino da operação...) informado não é valido.`
> `O valor do campo CFOP (Cfop) informado não é valido.`

**Tentativa A1 descartada**: replicar 100% da rotina Java do Sankhya via Oracle exigiria semanas/meses de engenharia reversa do cadastro fiscal. Inviável.

**Estratégia atual (caminho C)**: `faturar_pedido_venda_banco` cria TGFCAB nova e **herda campos fiscais da última TOP 35/37 emitida OK** do mesmo `(CODEMP, CODPARC, CODPROD)`. Pra Agromil, com volume histórico grande (>1000 NFe emitidas em 2026), praticamente sempre tem nota anterior pareável. Quando não tem (cliente novo + produto novo), o módulo Java rejeita e operador trata no Sankhya.

**Fluxo operacional**: IAgro cria a nota STATUSNOTA='P', operador abre Sankhya, clica CONFIRMAR → módulo Java emite NFe (Sankhya popula campos faltantes via sua rotina interna + chama SEFAZ).

Detalhes em [`modules/venda.md`](modules/venda.md) → "Faturamento (Caminho C)" + `CLAUDE.md` → "📑 Faturamento Caminho C".

---

### Variante: TGFCAB TOP 30 (avaria) exige CODTIPVENDA mesmo sem operação de venda (Mai/2026 — 2026-05-20)

Manifestação real: ao implementar `upsert_avaria_top30_lote` (geração automática de avaria interna no faturamento do Comercial), a primeira versão omitia `CODTIPVENDA` no dict do cabeçalho — TGFCAB TOP 30 é avaria interna, não tem negociação. Resultado: `ORA-20101: Campo Tipo de negociação obrigatório para a nota de Nro Único:NNNNN`.

Mesmo o cabeçalho sendo de avaria interna (CODNAT=20010200, STATUSNOTA='L' direto, sem TGFFIN/TGFVAR), o trigger continua exigindo CODTIPVENDA.

**Solução aplicada**: herdar `CODTIPVENDA` do TGFCAB TOP 11 origem (vem do recebimento original). Fallback pra 11 (mesma estratégia da função `criar_avaria_top30_banco` manual do módulo Venda):

```python
cur.execute("""
    SELECT c.CODEMP, c.CODPARC, c.CODCENCUS, c.DTNEG, c.CODTIPVENDA, i.CODVOL, NVL(i.PESO, 1)
      FROM TGFCAB c JOIN TGFITE i ON i.NUNOTA = c.NUNOTA
     WHERE c.NUNOTA = :n11 AND c.CODTIPOPER = 11 AND c.STATUSNOTA <> 'E'
       AND i.CODPROD = :prod AND i.CODAGREGACAO = :lote
""", ...)
codemp, codparc, codcencus, dtneg, codtipvenda_origem, codvol, peso = row

dados_cab_30 = {
    ...
    'CODTIPVENDA': int(codtipvenda_origem) if codtipvenda_origem else 11,
    ...
}
```

**Regra geral**: qualquer INSERT em TGFCAB (qualquer TOP) precisa de CODTIPVENDA válido. Avarias internas, devoluções, requisições — todos sujeitos à mesma trigger.

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

### `limparTudo()` (Rastreio)

Toda nova feature de filtro/estado precisa adicionar reset aqui. Hoje reseta: typeaheads, datas, agrupamento, tipoLote, lote armado, isolamento (`pedidoIsolado` + `codprodsIsolados`), `pedidosColapsados`, `pedidosJaVistos`, `gruposProdutoColapsados`, `gruposProdutoJaVistos`, `gruposLotesColapsados`, `mostrarPendentes/Finalizados`. **Esquecer um item deixa estado residual.**

> _Os checkboxes de filtro cruzado (`checksLotes` + `checksPorPedido`) foram **removidos em Mai/2026 — 2026-05-25**. Operador relatou que atrapalhavam mais que ajudavam — cross-filter agora vive só nos campos únicos `q_lotes` / `cliente_q` automaticamente disparados pelo backend._

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
