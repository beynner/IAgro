# Convenções de Código

## CSS — Design System

### Tokens globais (`global.css`)

Variáveis CSS centralizadas com **nomes em português**. Nunca usar valores hardcoded em módulos — sempre referenciar tokens.

| Categoria | Tokens (exemplos) |
|---|---|
| Cores principais | `--cor-fundo-painel`, `--cor-borda`, `--cor-acao-primaria`, `--cor-acao-perigo` |
| Appbar/rodapé | `--cor-appbar-fundo`, `--cor-appbar-texto`, `--cor-rodape-fundo`, `--cor-rodape-borda`, `--cor-rodape-texto` |
| Tipografia | `--fonte-principal`, `--peso-titulo`, `--tamanho-titulo` |
| Espaçamento | `--espaco-entre-paineis`, `--altura-appbar` (44px) |
| Borda/sombra | `--raio-borda`, `--sombra-painel` |

### Componentes globais

Definidos em `global.css`, **não duplicar nos módulos**:

- `body`, `.wrap`, `.main-layout` — moldura visual
- `.appbar`, `.appbar h1`, `.home-btn` — cabeçalho
- `.env-badge`, `.env-badge--homologacao`, `.env-badge--producao` — badge de ambiente
- `.user-profile-badge`, `.logout-link` — badge de usuário
- `.ia-footer`, `.ia-footer-versao` — rodapé
- `.panel`, `.modal-overlay`, `.modal-header`, `.modal-body` — containers
- `#toastContainer`, `.toast` — feedback
- `.status-dot` — indicador de status
- 6 `@keyframes` para animações

### Aliases de retrocompatibilidade

Cada módulo redefine `:root` com aliases que apontam para tokens globais. Permitiu migração sem quebrar as classes legadas.

### Regras permanentes

1. **Não redefinir** `body`, `.wrap`, `.appbar`, `.home-btn`, `.env-badge`, `.ia-footer` em CSS de módulo.
2. **Não adicionar `<main>`** dentro de `{% block content %}` — o `<main class="main-layout">` já está em `base.html`.
3. **Layout interno do módulo** vai numa classe própria (`.entrada-grid`, `.rastreio-layout`, etc.) dentro do `{% block content %}`.
4. **Para mudar appbar/rodapé globalmente**, alterar tokens `--cor-appbar-*` / `--cor-rodape-*` em `global.css`.
5. **Header com elementos auxiliares:** usar `{% block header_extras %}{% endblock %}` da `base.html` — irmão do `<h1>`. **NUNCA colocar spans com fontes alternativas dentro do `<h1>`** (quebra `line-height: 44px`).

### Regra do `.main-layout` (canônico em `global.css`)

```css
.main-layout {
  flex: 1;
  min-height: 0;
  padding: 14px 14px 40px 14px;
  display: flex;
  box-sizing: border-box;
  overflow: hidden;
}
```

- 14px nos lados e topo (logo abaixo da appbar)
- 40px no bottom (rodapé é `position: fixed`, ~24px + 14px de respiro)

Mudar valores aqui afeta **todos os módulos** simultaneamente.

---

## JavaScript — Helpers

Tudo exposto sob `window.IAgro` em `iagro_helpers.js`.

| Helper | Assinatura | Descrição |
|---|---|---|
| `IAgro.getCookie(name)` | `(name) => string` | Lê cookie (usado para CSRF token) |
| `IAgro.postJSON(url, data)` | `async (url, data) => response` | Wrapper de `fetch` com content-type JSON e CSRF header |
| `IAgro.showToast(msg, type)` | `(msg, 'success'\|'error'\|'info'\|'warning')` | Toast de feedback |
| `IAgro.debounce(fn, ms)` | `(fn, ms) => debounced` | Debounce simples |
| `IAgro.confirmarAcao(opts)` | `async ({titulo, mensagem, tipo}) => boolean` | Modal custom — substitui `window.confirm`. Tipos: `'perigo'` (vermelho), `'aviso'` (laranja), `'info'` (azul). Suporta Esc/Enter |
| `IAgro.cachedFetch(url, opts)` | `async (url, {ttl: 60_000}) => body` | Cache TTL em memória para typeahead/listas semi-estáticas. Não cacheia respostas de erro |
| `IAOverlay.show()` / `IAOverlay.hide()` | — | Overlay de loading da página |

### Regras

- **`window.confirm` está banido** em ações destrutivas — usar `IAgro.confirmarAcao` com tipo `perigo`.
- **CSRF token** sempre enviado via header `X-CSRFToken` (helper `postJSON` já cuida).
- **Modal `IAgro.confirmarAcao`** retorna Promise: `if (await IAgro.confirmarAcao({...}))`.
- **Compatibilidade legada:** os módulos `compras_portal` (entrada) e `compras_classificacao` usam wrappers que preferem as funções centrais (`window.getCookie`, `window.postJSON`) com fallback local.

---

## Padrão de Resposta de API

Todas as APIs JSON retornam:

```json
{ "ok": true, "dados": "..." }      // sucesso
{ "ok": false, "error": "..." }     // falha (HTTP 400 ou 500)
```

**Erro sempre humanizado** via `humanizar_erro_oracle()`. Stack trace vai apenas para `logger.exception` — nunca para o cliente.

---

## Atomicidade Transacional (views de escrita)

Padrão obrigatório em todas as views que fazem INSERT/UPDATE/DELETE:

```python
@exige_grupo('venda')
def api_xxx(request):
    try:
        with obter_conexao_oracle() as conn:
            try:
                resultado = funcao_do_service(..., conexao_existente=conn)
                conn.commit()
                return JsonResponse({'ok': True, ...})
            except Exception as exc:
                conn.rollback()
                raise
    except Exception as exc:
        logger.exception("Falha em api_xxx")
        return JsonResponse({'ok': False, 'error': humanizar_erro_oracle(exc)}, status=500)
```

**Razões:**
- `conexao_existente=conn` evita o bug `DPY-1001` em `inserir_cabecalho_nota_banco`
- `rollback` explícito antes de re-raise garante consistência
- `humanizar_erro_oracle` na resposta esconde detalhes técnicos
- `logger.exception` preserva stack trace para suporte

---

## Decorators

| Decorator | Aplicação |
|---|---|
| `@exige_grupo('modulo')` | Valida que `request.session['grupos']` contém grupo permitido para o módulo |
| `@check_vale_lock` | Lock para evitar concorrência em edição de vales (Comercial) |
| `@ensure_csrf_cookie` | Garante que cookie CSRF chegue no primeiro response da página (necessário em portais SPA-like) |

---

## Imports locais (dentro do corpo da função)

Algumas views fazem imports **dentro do corpo**, não no topo:

- `api_gerar_financeiro_banco` → importa `gerar_financeiro_banco`
- `api_desfaturar_vale` → importa `desfaturar_comercial_banco`

**Consequência para testes:** o patch deve apontar para o **módulo de origem**, não para `views`:

```python
# CORRETO:
@patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco', ...)

# ERRADO (não funciona com import local):
@patch('sankhya_integration.views.gerar_financeiro_banco', ...)
```

---

## Logging

`settings.py` tem bloco `LOGGING` estruturado. Todos os `print()` e `traceback.print_exc()` foram substituídos por:

- `logger.debug(...)` — fluxo normal detalhado
- `logger.info(...)` — eventos importantes
- `logger.warning(...)` — algo inesperado mas não crítico (ex: audit falhou mas operação ok)
- `logger.exception(...)` — capturar exceção com stack trace (uso obrigatório antes de humanizar erro)

---

## Migrations

- **Append-only** — nunca editar migration existente.
- **Nunca remover** — para reverter, criar nova migration que desfaça.
- **`0001_initial.py`** cria `Simulation` + `RastreioAudit` juntos.
- Ambiente de produção precisa rodar `python manage.py migrate` ao deploy.
