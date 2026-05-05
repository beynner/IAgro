# Pontos de Atenção (Armadilhas Técnicas)

Lista de pegadinhas que **já causaram bugs** ou que podem causar se tocadas sem cuidado. Tratar como avisos críticos.

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

## CSS

### `:root` do `rastreio.css`

Define `--ras-*` (tokens locais do Rastreio). **Outros módulos não devem importá-los** — usar tokens globais do `global.css`.

### `!important` em `.btn-acao-linha`

Necessário porque a classe legada `.btn-olho` tem mesma especificidade. Ao remover regras antigas no futuro, **revisar e tirar os `!important`**.

### `:has()` CSS no Rastreio

Estilização dependente de checkbox. **Requer Chrome 105+, Safari 15.4+, Firefox 121+.** Consistente com público alvo (operadores em desktops corporativos), mas validar antes de aplicar em outros módulos.
