# Ambiente e Execução

---

## Topologia de execução (a partir de Mai/2026)

**Cenário A confirmado** — todo o stack roda no servidor de produção. A máquina local do desenvolvedor vira apenas estação de RDP.

| Item | Detalhe |
|---|---|
| Servidor | Windows Server 2019 Standard, 2× Xeon E5-2680 v4 (28 cores / 56 threads), 64 GB RAM, 2× GeForce GTX 650 (apenas para monitores — Compute Capability 3.0, não usadas para LLM) |
| Path do projeto | `D:\TI\NexusGTi\IAgro\IAgro` (anteriormente acessado via `Z:\` mapeado da máquina local) |
| Usuário Windows do servidor | `ANDRE` (Ollama instalado em `C:\Users\ANDRE\AppData\Local\Programs\Ollama\`) |
| Stack rodando no servidor | Django (IAgro) + Ollama (LLM local) + Antigravity (IDE) + Python venv |
| Modelo LLM padrão | `qwen2.5:14b-instruct` (8.5 GB, baixado e validado em Mai/2026) |
| `OLLAMA_HOST` | `http://localhost:11434` (mesma máquina) |
| Máquina local (N95, 8 GB RAM) | Acessa via RDP — não roda código nem IDE |

**Implicações:**
- Não precisa expor a porta 11434 na rede (Ollama fica em `localhost`).
- Performance dos testes (`manage.py test` × 174 testes) e da IA do Antigravity é a do Xeon, não do N95.
- Filesystem é local (`D:\`), sem latência de SMB nas operações de grep/file watcher.
- `.env` na máquina local (caminhos `Z:\`) e no servidor (caminhos `D:\`) são diferentes — `.env` é gitignored, cada máquina tem o seu.

---

## Variáveis de `.env`

O arquivo `.env` fica na raiz do projeto e é carregado pelo `python-dotenv` no início de `settings.py`.

### Obrigatórias

| Variável | Descrição |
|---|---|
| `DJANGO_ENV` | Ambiente atual: `production` ou `homologacao` (padrão). Controla badge na navbar |
| `SECRET_KEY` | Chave de assinatura de sessões e CSRF do Django. **Nunca expor publicamente** |
| `DEBUG` | `True` em desenvolvimento, `False` em produção. **Cuidado:** `False` desativa servidor de arquivos estáticos do `runserver` |
| `ALLOWED_HOSTS` | Lista separada por vírgula. Ex: `127.0.0.1,localhost` em dev, hostname real em prod |
| `ORACLE_CLIENT_LIB_DIR` | Caminho para Oracle Instant Client (ex: `C:\oracle\instantclient_19_23`). Necessário para `oracledb` em modo thick |
| `SANKHYA_DB_HOST` | Host do servidor Oracle (ex: `hfsemear.ddns.net`) |
| `SANKHYA_DB_PORT` | Porta Oracle (padrão `1521`) |
| `SANKHYA_DB_SERVICE` | Service name (ex: `XE`) |
| `SANKHYA_DB_USER` | Usuário do Oracle |
| `SANKHYA_DB_PASSWORD` | Senha do Oracle |

### Opcionais (módulos novos — Mai/2026)

| Variável | Default | Descrição |
|---|---|---|
| `URL_RASTREIO_PUBLICA` | `http://localhost:8000/rastreio-publico/{lote}` | URL embarcada no QR code das etiquetas SafeTrace/IAgro. `{lote}` é substituído pelo CODAGREGACAO em runtime. Quando Agromil definir hostname público, ajustar aqui sem mexer em código |

### Opcionais (segurança HTTPS — produção)

| Variável | Descrição |
|---|---|
| `SECURE_SSL_REDIRECT` | `True` para redirecionar HTTP→HTTPS. **Ativar somente em produção com HTTPS configurado** |
| `SECURE_HSTS_SECONDS` | Duração do HSTS em segundos (ex: `31536000` = 1 ano) |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` para estender HSTS a subdomínios |
| `SECURE_HSTS_PRELOAD` | `True` para incluir no preload list do browser |
| `SESSION_COOKIE_SECURE` | `True` para transmitir cookie de sessão apenas via HTTPS |
| `CSRF_COOKIE_SECURE` | `True` para transmitir cookie CSRF apenas via HTTPS |

### Valores para Desenvolvimento

```dotenv
DJANGO_ENV=homologacao
DEBUG=True
ALLOWED_HOSTS=*
```

### Valores para Produção (com HTTPS)

```dotenv
DJANGO_ENV=production
DEBUG=False
ALLOWED_HOSTS=<hostname-real>
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

---

## Executando o Projeto

### Setup

```bash
# Ativar ambiente virtual
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Migrações (apenas para SQLite — Simulation + RastreioAudit)
python manage.py migrate

# Servidor de desenvolvimento
python manage.py runserver
```

### Acesso

| URL | Descrição |
|---|---|
| `http://127.0.0.1:8000/sankhya/` | Aplicação |
| `http://127.0.0.1:8000/admin/` | Django Admin |
| `http://127.0.0.1:8000/sankhya/health/` | Health check (público) |
| `http://127.0.0.1:8000/sankhya/health/?deep=1` | Health check profundo (Oracle + view + contagem TOP 34) |

---

## Testes

```bash
# Todos os testes (174)
python manage.py test sankhya_integration.tests

# Por módulo
python manage.py test sankhya_integration.tests.test_views_entrada
python manage.py test sankhya_integration.tests.test_views_comercial
python manage.py test sankhya_integration.tests.test_views_venda      # 90 testes
python manage.py test sankhya_integration.tests.test_rastreio         # 53 testes
```

**Regras:**
- Nenhum teste pode depender de Oracle real
- Usar `unittest.mock.patch` para isolar `oracle_conn`
- Para imports locais nas views (ex: `api_gerar_financeiro_banco`), patch deve apontar para o **módulo de origem** (`oracle_conn`), não para `views`
