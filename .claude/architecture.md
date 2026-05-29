# Arquitetura

## Estrutura de Pastas

```
IAgro/
├── .env                         # Variáveis de ambiente (NÃO versionado)
├── .env.example                 # Template (versionado, sem valores reais)
├── CLAUDE.md                    # Documento raiz (lê .claude/*)
├── .claude/                     # Documentação modular para o Claude
├── README.md
├── manage.py
├── requirements.txt
├── db.sqlite3                   # Banco Django (sessões + Simulation + RastreioAudit)
│
├── IAgro/                       # Configuração Django
│   ├── settings.py
│   ├── urls.py                  # Raiz: /admin/, /sankhya/ → sankhya_integration.urls
│   ├── wsgi.py
│   └── asgi.py
│
├── sankhya_integration/         # Único app Django do projeto
│   ├── apps.py                  # AppConfig com ready() para registrar signals
│   ├── models.py                # Simulation + RastreioAudit
│   ├── views.py                 # ~2400 linhas — todas as views de todos os módulos
│   ├── urls.py                  # Todas as rotas do app (prefixo /sankhya/)
│   ├── decorators.py            # @exige_grupo, @check_vale_lock, GRUPOS_PERMITIDOS
│   ├── middleware.py            # ControleInatividadeMiddleware (timeout de sessão)
│   ├── context_processors.py    # app_version_processor, environment_badge
│   ├── admin.py                 # SimulationAdmin + RastreioAuditAdmin
│   ├── signals.py               # Audit log de Simulation via post_save/post_delete
│   ├── migrations/0001_initial.py
│   │
│   ├── services/
│   │   └── oracle_conn.py       # NÚCLEO CRÍTICO (~3350 linhas) — todas as queries SQL
│   │
│   ├── templates/sankhya_integration/
│   │   ├── base.html            # Template base (appbar, rodapé, scripts globais)
│   │   ├── home.html            # Tela inicial / login
│   │   ├── entrada.html
│   │   ├── classificacao.html
│   │   ├── comercial.html
│   │   ├── venda.html
│   │   ├── venda_modais.html    # Modais do portal de Venda
│   │   ├── rastreio.html
│   │   ├── relatorios.html      # 📊 Mai/2026 — 2026-05-17
│   │   └── logistica.html       # 🚚 Mai/2026 — módulo persistente (2026-05-29)
│   │
│   ├── static/sankhya_integration/
│   │   ├── global.css                       # Tokens de design + componentes globais
│   │   ├── iagro_helpers.js                 # window.IAgro (helpers reutilizáveis)
│   │   ├── home.css / home.js
│   │   ├── entrada.css / entrada.js
│   │   ├── entrada_mobile.js                # 📱 Redesign mobile-first Entrada (Mai/2026 — 2026-05-27)
│   │   ├── classificacao.css / classificacao.js
│   │   ├── classificacao_mobile.js          # 📱 Redesign mobile-first Classificação (Mai/2026 — 2026-05-26)
│   │   ├── comercial.css / comercial.js
│   │   ├── comercialDistribuicao.js         # Sub-módulo Comercial
│   │   ├── comercialFinanceiro.js           # Sub-módulo Comercial
│   │   ├── comercialImpressao.js            # Sub-módulo Comercial
│   │   ├── venda.css / venda.js
│   │   ├── rastreio.css / rastreio.js
│   │   ├── relatorios.css / relatorios.js   # 📊 Mai/2026 — 2026-05-17
│   │   ├── logistica.css / logistica.js     # 🚚 Mai/2026 — desktop (LogisticaApi REST)
│   │   └── logistica_mobile.js              # 🚚 Mai/2026 — mobile (LogisticaApi REST)
│   │
│   ├── sql/
│   │   ├── ANDRE_IAGRO_SALDO_LOTE.sql        # DDL da view do WMS (versionado)
│   │   └── ANDRE_IAGRO_SALDO_LOTE_teste.sql  # Queries de conferência manual
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_views_entrada.py
│       ├── test_views_comercial.py
│       ├── test_views_venda.py              # 90 testes
│       ├── test_rastreio.py                 # 53 testes (+24 desde Mai/2026)
│       ├── test_etiqueta_lote.py            # 27 testes (Rastreio etiquetas SafeTrace)
│       ├── test_vendas_lote.py              # 10 testes (Comercial vendas-do-lote)
│       ├── test_margem_lote.py              # 13 testes (Comercial card Margem)
│       ├── test_views_combustivel.py        # 84 testes
│       ├── test_views_email_pedidos.py      # 40+ testes
│       ├── test_relatorios.py               # 56 testes (Módulo Relatórios MVP)
│       └── test_logistica.py                # 42 testes (Módulo Logística persistente)
│
└── images/                      # Imagens (logo, etc.) — também em STATICFILES_DIRS
```

**Total de testes:** ~512 (em maio/2026 com 56 testes do módulo Relatórios + 42 do módulo Logística — 2026-05-29), todos passando, todos sem dependência de Oracle real.

---

## Mapa de URLs

```
/                                       → redireciona para /sankhya/
/admin/                                 → Django Admin
/sankhya/                               → home (login)
/sankhya/health/                        → health check público (?deep=1 para checagem profunda)

# Módulos
/sankhya/compras/portal/                → Entrada (TOP 11)
/sankhya/compras/classificacao/         → Classificação (TOP 26)
/sankhya/comercial/                     → Comercial (TOP 13)
/sankhya/venda/portal/                  → Venda (TOP 34/35/37)
/sankhya/rastreio/                      → Rastreio / WMS
/sankhya/venda/email-importar/          → Importação por e-mail (TOP 34)
/sankhya/combustivel/                   → Controle de Combustível (TOP 10 → 26)

# APIs de Venda (POST, exige grupo 'venda')
/sankhya/venda/api/cabecalho/           → criar pedido TOP 34
/sankhya/venda/api/cabecalho/editar/    → atualizar cabeçalho (TOP 34, não-faturado)
/sankhya/venda/api/cabecalho/obter/     → obter cabeçalho (GET)
/sankhya/venda/api/item/                → adicionar item
/sankhya/venda/api/item/editar/         → editar item
/sankhya/venda/api/item/remover/        → remover item
/sankhya/venda/api/excluir/             → excluir pedido completo
/sankhya/venda/api/faturar/             → faturar TOP 34 → 35 (NFe) ou 37 (s/ NFe)

# APIs de Rastreio (POST, exige grupo 'rastreio')
/sankhya/rastreio/api/lotes-disponiveis/  → GET, paginado
/sankhya/rastreio/api/pedidos-abertos/    → GET, paginado por cabeçalho
/sankhya/rastreio/api/atribuir-lote/      → POST (lock pessimista, audit)
/sankhya/rastreio/api/desvincular-lote/   → POST (audit)
/sankhya/rastreio/api/fabricantes/        → GET typeahead
/sankhya/rastreio/api/lote-vinculos/      → GET pedidos/vendas que usam um lote

# APIs de Combustível (exige grupo 'combustivel': 1, 6, 11)
/sankhya/combustivel/api/estoque/             → GET saldo (view ANDRE_IAGRO_SALDO_COMBUSTIVEL)
/sankhya/combustivel/api/veiculos/            → GET typeahead TGFVEI por tipo
/sankhya/combustivel/api/produtos/            → GET typeahead TGFPRO CODGRUPOPROD=11
/sankhya/combustivel/api/requisicoes/         → GET listagem paginada
/sankhya/combustivel/api/requisicao/<nunota>/ → GET detalhe (cab + itens + metadata)
/sankhya/combustivel/api/requisicao/criar/    → POST (501 enquanto B2 não aprovada)

# APIs de Relatórios (Mai/2026 — 2026-05-17, exige grupo 'relatorios' = 1, 6, 9)
/sankhya/relatorios/                              → tela HTML com 5 sub-abas
/sankhya/relatorios/api/top-clientes-produtos/    → GET ranking clientes + produtos
/sankhya/relatorios/api/lotes-envelhecidos/       → GET lotes parados > N dias
/sankhya/relatorios/api/consumo-veiculos/         → GET ranking consumo combustível
/sankhya/relatorios/api/fluxo-caixa/              → GET TGFFIN projeção 30/60/90d
/sankhya/relatorios/api/margem-venda/             → GET margem por cliente/produto (cache 5min)

# APIs de Ajustes Administrativos (Mai/2026 — 2026-05-28, exige grupo 'ajustes' = 1, 6)
/sankhya/configuracoes/ajustes/                          → tela HTML com 2 sub-abas
/sankhya/configuracoes/api/ajustes/caixas/criar/         → POST AJUSTE_SALDO em AD_COLETA_CAIXAS
/sankhya/configuracoes/api/ajustes/caixas/listar/        → GET últimos AJUSTE_SALDO
/sankhya/configuracoes/api/ajustes/combustivel/criar/    → POST AJUSTE_AVULSO (TOP 10 se +, TOP 53 se −, sem veículo)
/sankhya/configuracoes/api/ajustes/combustivel/listar/   → GET últimos AJUSTE_AVULSO

# Logística (Mai/2026 — 2026-05-29, módulo persistente, exige grupo 'logistica' = 1, 6, 10)
/sankhya/logistica/                                      → tela HTML (LogisticaApi REST)
/sankhya/logistica/api/tipos-parceiro/                   → GET cadastro AD_TIPO_PARCEIRO
/sankhya/logistica/api/parceiros/?tipo=N&q=...           → GET typeahead via AD_PARCEIRO_TIPO N:N
/sankhya/logistica/api/veiculos/?q=...                   → GET typeahead TGFVEI
/sankhya/logistica/api/viagens/?data_de=...&data_ate=... → GET listagem paginada
/sankhya/logistica/api/viagem/<id>/                      → GET detalhe completo
/sankhya/logistica/api/viagem/<id>/ficha-pdf/            → GET PDF A6 vertical reportlab
/sankhya/logistica/api/viagem/criar/                     → POST cria viagem (atômica + lock)
/sankhya/logistica/api/viagem/<id>/editar/               → POST UPDATE diferencial
/sankhya/logistica/api/viagem/<id>/excluir/              → POST DELETE cascata + audit
```

---

## Autenticação

O sistema **não usa** `django.contrib.auth`. O login é feito via API HTTP do Sankhya (`hfsemear.ddns.net:8180`).

### Sessão Django

Após login bem-sucedido, ficam armazenados em `request.session`:

| Chave | Tipo | Descrição |
|---|---|---|
| `codusu` | int | ID do usuário no Sankhya |
| `nomeusu` | string | Nome de usuário (login) |
| `nome` | string | Nome completo |
| `grupos` | list[str] | IDs de grupo Sankhya: `['1']`, `['8', '9']`, etc. |

### Decorator `@exige_grupo`

Em `decorators.py`. Valida acesso por grupo antes de cada view protegida.

```python
@exige_grupo('venda')
def api_criar_cabecalho_venda(request):
    ...
```

### Mapeamento de grupos Sankhya

| Grupo | Nome (TSIGRU.NOMEGRUPO) | Acesso |
|---|---|---|
| `1` | DIRETORIA | Irrestrito a todos os módulos |
| `6` | SUPORTE | Irrestrito (manutenção e suporte) |
| `8` | IAGRO_PACKING | Entrada e Classificação (renomeado de IAGRO_ENTRADA em 2026-05-14) |
| `9` | IAGRO_COMERCIAL | Comercial |
| `10` | IAGRO_ADMINISTRATIVO | Vendas (renomeado de IAGRO_VENDAS em 2026-05-14) |
| `11` | IAGRO_FROTA | Combustível (Mai/2026 — renomeado de PACKING_FROTA em 2026-05-14) — ⚠ não confundir com TGFGRU.CODGRUPOPROD=200400 que é o grupo do **produto** combustível |

Consulta no Sankhya: `SELECT CODGRUPO, NOMEGRUPO FROM TSIGRU ORDER BY CODGRUPO`.

> **Atenção** — versões antigas do código/docs referenciavam as colunas
> como `CODGRU`/`DESCRGRU`. Em produção a TSIGRU usa **`CODGRUPO`/`NOMEGRUPO`**
> (validado em Mai/2026). Corrigido em `decorators.py`.

### Permissões por módulo

| Módulo | Grupos com acesso |
|---|---|
| Entrada | 1, 6, 8 |
| Classificação | 1, 6, 8 |
| Comercial | 1, 6, 9 |
| Venda | 1, 6, 10 |
| Rastreio | 1, 6, 8, 10 _(Comercial perdeu acesso em 2026-05-14)_ |
| Combustível | 1, 6, 10, 11 _(Administrativo ganhou acesso em 2026-05-14)_ |
| Relatórios | 1, 6, 9 |
| Configurações (hub) | 1, 6 |
| Usuários | 1, 6 |
| Ajustes Admin (caixas + combustível) | 1, 6 _(Mai/2026 — 2026-05-28)_ |
| Caixas | 1, 6, 8, 9, 10, 11 |
| Logística | 1, 6, 10 _(Mai/2026 — 2026-05-29, módulo persistente)_ |

---

## Padrão de Resposta de API

Todas as APIs JSON retornam:

```json
{ "ok": true, "...dados..." }       // sucesso
{ "ok": false, "error": "..." }     // falha (HTTP 400 ou 500)
```

Mensagens de erro **sempre passam por `humanizar_erro_oracle()`** antes de chegar ao cliente.

---

## Arquitetura "Moldura Fixa + Miolo do Módulo"

A `base.html` define a **moldura visual completa** (appbar, rodapé, margens). Cada módulo apenas preenche `{% block content %}` com seus cards.

### Carregamento de CSS (ordem para todas as páginas)

1. `global.css` — tokens de design (cores, espaçamentos, bordas, sombras, transições)
2. `entrada.css` — base de layout e componentes (carregado em todas as páginas pelo `base.html`, por legado)
3. CSS do módulo via `{% block extra_css %}`

### Regra permanente — base/módulo

**Nenhum módulo deve redefinir** `body`, `.wrap`, `.appbar`, `.home-btn`, `.env-badge`, `.ia-footer`, nem adicionar `<main>` dentro do `{% block content %}`. Essas peças vivem em `base.html` + `global.css`.

Para layouts específicos, criar classe própria no `{% block content %}`:

| Módulo | Container interno |
|---|---|
| Entrada | `.entrada-grid` (flex, aside 320px + rightcol) |
| Classificação | `.classificacao-grid` (flex, aside 320px + rightcol) |
| Comercial | `.layout` (grid 360px + 1fr — nome legado) |
| Venda | `.venda-grid` (flex, 3 colunas) |
| Rastreio | `.rastreio-layout` (grid 2 colunas iguais) |

Para mudar appbar/rodapé globalmente, alterar tokens `--cor-appbar-*` / `--cor-rodape-*` em `global.css`.

### Regra do `.appbar h1`

Usa `line-height: var(--altura-appbar)` (44px) em vez de `display: flex + align-items: center`. Isso elimina interação do line-box do `<h1>` com métricas de fontes filhas.

**Para elementos auxiliares ao lado do título** (ex: nome do fornecedor), usar `{% block header_extras %}{% endblock %}` da `base.html` — fica como **irmão** do `<h1>`, dentro do `.header-left`. **NUNCA colocar spans com fontes alternativas dentro do `<h1>`.**
