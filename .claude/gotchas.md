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
