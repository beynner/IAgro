# CLAUDE.md — IAgro (NexusGTi)

> Este arquivo é a referência principal para todas as sessões futuras com o assistente.
> **Idioma padrão de toda comunicação: Português Brasileiro.**

---

## 1. Sobre o Projeto

**Nome:** IAgro
**Versão atual:** 1.1.0 beta
**Tipo:** Sistema interno de gestão operacional integrado ao ERP Sankhya
**Organização:** NexusGTi / HF Semear

### Objetivo

Sistema web para gerenciamento das operações do IAgro (central de beneficiamento de produtos agrícolas, antigo "Packing House"). Integra dados do ERP Sankhya via Oracle para controlar:

- **Entrada:** Recebimento e conferência de notas de compra (TOP 11) com pesagem e controle de itens
- **Classificação:** Triagem e classificação de lotes por qualidade com controle de descartes
- **Comercial:** Faturamento de vales de compra (TOP 13), precificação, negociação e geração de financeiro no Sankhya
- **Venda:** Criação, edição e listagem de pedidos de venda (TOP 34) — o faturamento (34 → 35/37) ainda é pendente

### Stack Principal

| Componente | Tecnologia |
|---|---|
| Framework web | Django 6.0.4 |
| Banco de dados ERP | Oracle (Sankhya ERP) via `oracledb` 3.4.2 |
| Banco de dados Django | SQLite (apenas sessões e modelo `Simulation`) |
| Driver Oracle | `oracledb` (python-oracledb moderno) — cx_Oracle é fallback, não instalado |
| Frontend | HTML + CSS + JavaScript puro (sem framework JS) |
| Autenticação | Sessão própria baseada no login do Sankhya (não usa django.contrib.auth) |
| Configuração | `python-dotenv` para leitura do `.env` |
| Relatórios | `reportlab` para geração de PDFs |
| Imagens | `pillow` |

---

## 2. Estado Atual — O Que Foi Feito e o Que Está Pendente

### Melhorias executadas (sessão de auditoria — abril 2026)

| # | Tarefa | Status |
|---|---|---|
| 1 | Credenciais Oracle movidas para `.env` (removidas do `oracle_conn.py` e `requirements.txt`) | ✅ Concluída |
| 2 | `SECRET_KEY` movida para `.env` | ✅ Concluída |
| 3 | `print()` de debug removidos de `context_processors.py` | ✅ Concluída |
| 4 | `DEBUG` e `ALLOWED_HOSTS` movidos para `.env` com valores seguros comentados para produção | ✅ Concluída |
| 5 | Detecção de ambiente por letra de drive substituída por variável `DJANGO_ENV` no `.env` | ✅ Concluída |
| 6 | Bloco `LOGGING` estruturado adicionado ao `settings.py`; todos os `print()` e `traceback.print_exc()` substituídos por `logger` adequado | ✅ Concluída |
| 7 | Cabeçalhos de segurança HTTPS (`SECURE_*`) adicionados ao `settings.py`, controlados por variáveis no `.env` | ✅ Concluída |
| 8 | Mapeamento de grupos Sankhya documentado em comentários no `decorators.py` | ✅ Concluída |
| 9 | Modelo `Simulation` registrado no Django Admin; audit log via signals Django (`post_save`/`post_delete`) | ✅ Concluída |
| 10 | Testes unitários criados: `test_views_entrada.py`, `test_views_comercial.py`, `test_faturamento.py` (68 testes no total) — posteriormente `test_faturamento.py` foi removido junto com o serviço `faturamento.py` (limpeza de 28/04/2026) | ✅ Concluída |
| 11 | Arquivos `_BKP` e código morto comentado removidos | ✅ Concluída |
| 12 | Migração SQLite → PostgreSQL | ❌ Cancelada (projeto usa Oracle; SQLite só para sessões/ORM, não há necessidade de troca) |

### Refatoração CSS — Design System (22 abr 2026)

Criação de um sistema de design tokens centralizado em `global.css`, com variáveis CSS em português e nomes explícitos. Todos os módulos foram migrados para usar aliases que apontam para os tokens globais, eliminando valores hardcoded duplicados.

| # | Arquivo | O que foi feito | Status |
|---|---|---|---|
| 1 | `comercial 260408.css` | Arquivo temporário/backup removido do repositório | ✅ Concluído |
| 2 | `global.css` | Reescrito do zero: 30+ tokens de cor, tipografia, espaçamento, borda e sombra com nomes em português; componentes globais (`.panel`, `.appbar`, `.home-btn`, `.status-dot`, `.modal-overlay`, `.modal-header`, `.modal-body`, `#toastContainer`, `.toast`, inputs, 6 keyframes); aliases de retrocompatibilidade para variáveis antigas | ✅ Concluído |
| 3 | `home.css` | `font-family`, `border-radius` e `transition` substituídos por tokens globais; paleta de cores própria mantida | ✅ Concluído |
| 4 | `entrada.css` | `:root` redirecionado: 10 variáveis locais viram aliases dos tokens globais; `body`, `.appbar`, `main`, `.panel`, `#filtersForm`, `.filters-footer`, `.modal-body`, `.icon-btn`, `#toastContainer`, `.filtro-input` migrados | ✅ Concluído |
| 5 | `classificacao.css` | `:root` redirecionado: 9 variáveis locais viram aliases; `body`, `.appbar`, `.layout`, `.rightcol`, `.bottom-row`, `.panel`, `.panel > header/content`, `.filters-grid`, inputs, `.btn-mini-nav`, `.icon-btn`, `.ia-selectable-table`, `.switch .slider`, `.resumo-item`, `#produtosClassificadosWatermark` migrados | ✅ Concluído |
| 6 | `comercial.css` | `:root` redirecionado: 8 variáveis viram aliases; `body`, `.panel`, `.layout`, `.zgrid`, `.appbar .home-btn`, `.section-head`, `#filtersCard`, `.lista-view-toggle`, `#listaTable`, `.lista-vale-ico`, `.dist-mini`, `.dist-class-card .bar-track`, `.dist-actions button`, `.badge`, `#classCard .class-table/.kpi/.extra/.percent-bar`, `#entradaCard .card`, `.modal-content`, `.resumo-card`, `.btn-faturar-final`, `.btn-print-outline`, `.print-option`, `.switch-slider`, `.switch-container` migrados | ✅ Concluído |
| 7 | `venda.css` | `:root` redirecionado: 7 variáveis viram aliases; `--cor-fundo-cabecalho-tabela`, `--cor-texto-primario-escuro`, `--cor-texto-secundario-cinza`, `--cor-borda-dropdown-ativa` mantidos como específicos; `.date-nav-buttons button`, `.icon-btn-venda` (border-radius e transition), `.dropdown-item` (transition) migrados | ✅ Concluído |
| 8 | `rastreio.css` | `:root` redirecionado: 5 variáveis viram aliases (`--bg-card`, `--bg-card-hover`, `--texto-secundario`, `--status-verde`, `--status-alerta`); `--cor-borda` local removida (global cobre); 5 específicos mantidos; `.list-panel`, `.rastreio-card`, `.rastreio-card:hover`, `.progress-container`, `.progress-bar`, `.huge-input`, `.group-toggle`, `.group-toggle label`, `.group-header` migrados | ✅ Concluído |

### Correções de regressão pós-refatoração CSS (22 abr 2026)

Após a migração dos módulos, foram identificados e corrigidos três problemas causados pela ausência do `global.css` na cadeia de carregamento:

| # | Arquivo | Problema | Correção | Status |
|---|---|---|---|---|
| 1 | `base.html` | `global.css` nunca era carregado em nenhum template — todos os tokens (`--cor-fundo-painel`, `--cor-borda`, `--espaco-entre-paineis`, etc.) ficavam indefinidos, quebrando styling de Entrada, Venda e Rastreio | Adicionado `<link rel="stylesheet" href="global.css">` como **primeiro CSS** no `<head>`, antes de `entrada.css` | ✅ Concluído |
| 2 | `global.css` | `.appbar` definia `background: var(--cor-fundo-painel)` (branco) e `position: sticky` — após global.css ser carregado, o appbar ficaria branco e o `h1 { color: #ffffff }` dos módulos ficaria invisível (branco sobre branco) | `.appbar` reduzido a propriedades puramente estruturais (`height`, `display`, `align-items`, `flex-shrink`); visual (fundo, borda, posição) fica a cargo de cada módulo | ✅ Concluído |
| 3 | `comercial.css` | Appbar com deslocamento horizontal: `entrada.css` aplica `padding: 0 16px` ao `.appbar` de todos os módulos; combinado com o `.wrap { padding: 8px }` do Comercial, o conteúdo ficava 24 px da borda em vez dos ~17 px das outras páginas | Adicionado `padding: 0` explícito na regra `.appbar` do Comercial para cancelar o padding herdado; o wrap já provê o espaço lateral | ✅ Concluído |

### Arquitetura de carregamento CSS (resultado final)

> **Atenção para futuras sessões:** `entrada.css` é carregado pelo `base.html` para TODOS os módulos (não apenas Entrada). Isso é legado — foi usado como base global antes da criação do design system. Como consequência, qualquer propriedade CSS definida em `entrada.css` para `.appbar`, `.panel`, `.home-btn`, etc. aplica-se a todos os módulos. Módulos que precisam de valores diferentes devem sobrescrever explicitamente.

Ordem de carregamento para todas as páginas:
1. `global.css` — tokens de design (cores, espaçamentos, bordas, sombras, transições)
2. `entrada.css` — base de layout e componentes (carregado pelo `base.html`)
3. CSS do módulo — via `{% block extra_css %}` em cada template

### Padronização de appbar, rodapé e layout-base (23 abr 2026)

Refatoração para centralizar em `base.html` + `global.css` tudo que é comum entre os módulos (appbar, rodapé, badge de usuário, badge de ambiente, estrutura `body`/`.wrap`/`.main-layout`). Os módulos agora herdam essa moldura e apenas preenchem `{% block content %}` com os cards específicos.

**Novos tokens em `global.css`:**
- `--cor-appbar-fundo`, `--cor-appbar-texto` — cor da appbar; alterar aqui muda em todos os módulos
- `--cor-rodape-fundo`, `--cor-rodape-borda`, `--cor-rodape-texto` — cor do rodapé

**Componentes movidos para `global.css`** (eram duplicados em cada módulo):
- `body` canônico (margin, background, altura, overflow)
- `.wrap` (container principal flex column)
- `.main-layout` (área de conteúdo entre appbar e rodapé; flex, gap, padding laterais)
- `.appbar` com fundo, padding, altura + `.appbar h1` com cor/tipografia
- `.appbar .home-btn` (ícone home na appbar — transparente com borda branca translúcida)
- `.env-badge` + `.env-badge--homologacao` + `.env-badge--producao`
- `.user-profile-badge` + `.logout-link` (antes estavam em `<style>` inline do `base.html`)
- `.ia-footer` + `.ia-footer-versao` (antes eram `style=""` inline no `<footer>`)

**Mudanças estruturais nos templates:**
| Arquivo | Mudança |
|---|---|
| `base.html` | `<main>` perdeu o `style="padding:20px; gap:20px; ..."` inline — agora só `class="main-layout"` (styling vem de `global.css`). Bloco `<style>` do `<head>` removido. `<footer>` perdeu `style=""` inline. |
| `classificacao.html` | `<main class="main-layout">` aninhado removido — `<aside>` e `<section>` ficam direto no `{% block content %}` |
| `venda.html` | `<div class="main-layout">` aninhado removido. Link duplicado de `entrada.css` removido (base já carrega). |
| `rastreio.html` | `<main class="rastreio-layout">` aninhado trocado por `<div class="rastreio-layout">` (main já está no base) |
| `entrada.html` e `comercial.html` | Sem mudança estrutural (já estavam limpos) |

**Limpeza nos CSS dos módulos** — `body`, `.wrap`, `.appbar` (estruturais), `.home-btn`, `.env-badge` e `main {}` genéricos foram removidos pois agora estão no `global.css`:
| CSS | O que sobrou |
|---|---|
| `entrada.css` | Aliases de tokens + `.appbar { justify-content: flex-start; margin-bottom }` + `.header-row` + regras de cards/forms/tabelas específicas |
| `classificacao.css` | Aliases + `.appbar { justify-content: space-between; margin-bottom }` + override `.main-layout { gap: 12px; padding-bottom: 40px }` + regras específicas |
| `comercial.css` | Aliases + `.appbar { ... }` + override `.main-layout { padding: 0 20px }` + regras específicas |
| `venda.css` | Aliases + override `.main-layout { gap: 12px; padding: 10px 20px }` + regras específicas |
| `rastreio.css` | Aliases + override `.main-layout { padding: 0; gap: 0 }` (rastreio gerencia seu próprio padding via `.rastreio-layout`) + regras específicas |

### Regra permanente — arquitetura base/módulo

> **Nenhum módulo (Entrada, Classificação, Comercial, Venda, Rastreio ou futuros) deve redefinir `body`, `.wrap`, `.appbar`, `.home-btn`, `.env-badge`, `.ia-footer`, nem adicionar `<main>` dentro do `{% block content %}`.** Essas peças vivem em `base.html` + `global.css`. Se o módulo precisa de um layout específico para seus cards, deve usar uma classe própria (ex: `.rastreio-layout`, `.layout` do Comercial) dentro do `{% block content %}`, ou sobrescrever `.main-layout` via CSS com valores específicos. Para mudar aparência de appbar/rodapé globalmente, altere os tokens `--cor-appbar-*` / `--cor-rodape-*` em `global.css` — efeito propaga para todos os módulos automaticamente.

### Arquitetura "moldura fixa + miolo do módulo" (23 abr 2026)

Consolidação do padrão de herança `base.html` → módulo, eliminando overrides ad-hoc do `.main-layout` por módulo. A ideia: a página base define a **moldura visual completa** (appbar, rodapé, margens laterais/topo/base) e o módulo só preenche o **miolo** com seus cards.

**Regras canônicas no `global.css`:**
```css
.main-layout {
  flex: 1;
  min-height: 0;
  padding: 14px 14px 40px 14px;   /* 14px nos lados e topo; 40px no bottom por conta do rodapé fixed */
  display: flex;
  box-sizing: border-box;
  overflow: hidden;
}
```
- Margem superior 14px: começa a contar **logo abaixo da appbar** (wrap é flex column)
- Margem inferior 40px: o `.ia-footer` é `position: fixed`, flutuando sobre o conteúdo — os 40px dão espaço suficiente para o rodapé (~24px) + respiro (14px)
- Alterar qualquer um desses valores afeta **todos os módulos** de uma vez

**Container interno por módulo** — cada módulo cria sua própria classe `<...>-grid` dentro do `{% block content %}`:
| Módulo | Container interno (HTML) | Layout interno (CSS) |
|---|---|---|
| Entrada | `<div class="entrada-grid">` | `flex` row, gap 14, aside 320px fixo + rightcol flex 1 |
| Classificação | `<div class="classificacao-grid">` | `flex` row, gap 12, aside 320px + rightcol flex 1 |
| Comercial | `<div class="layout">` (nome legado) | `grid` 360px + 1fr, `flex: 1` dentro do main-layout |
| Venda | `<div class="venda-grid">` | `flex` row 3 colunas (filtros 200px + central + itens) |
| Rastreio | `<div class="rastreio-layout">` | `grid` 2 colunas iguais |

**Regras do `.appbar h1` (resolve diferenças de fonte nos títulos):**
```css
.appbar h1 {
  height: var(--altura-appbar);    /* altura fixa de 44px */
  line-height: var(--altura-appbar); /* centraliza texto verticalmente sem flex */
  overflow: hidden;
  white-space: nowrap;
  /* ...demais tokens tipográficos */
}
```
- Uso de `line-height: 44px` (em vez de `display: flex + align-items: center`) **elimina a interação** do line-box do h1 com métricas de fontes dos filhos (ex: Courgette cursive). Importante para módulos que colocam spans com fontes diferentes dentro do título.
- Se o módulo quiser adicionar elementos auxiliares ao lado do título (como nome de fornecedor), deve usar o bloco `{% block header_extras %}{% endblock %}` definido na `base.html` — esse bloco fica **fora do `<h1>`**, como irmão dele, dentro do `.header-left`. **Nunca colocar spans com fontes alternativas dentro do h1.**

**Estrutura final do header em `base.html`:**
```html
<header class="appbar">
  <div class="header-row">
    <div class="header-left">
      <a class="home-btn">...</a>
      <h1>{% block header_title %}IAGRO{% endblock %}</h1>
      {% block header_extras %}{% endblock %}  <!-- para elementos auxiliares -->
    </div>
    <div class="user-profile-badge">...</div>
  </div>
</header>
```
Todas as classes (`.header-row`, `.header-left`, `.user-profile-badge`, `.user-profile-info`, `.user-profile-name`) têm estilos no `global.css` — **zero `style=""` inline** no header.

### Bug crítico corrigido — BOM no `comercial.html` (23 abr 2026)

Durante a refatoração, identificamos que o `comercial.html` estava salvo com um **UTF-8 Byte Order Mark (BOM)** — 3 bytes invisíveis (`0xEF 0xBB 0xBF`, caractere Unicode `U+FEFF`) no início do arquivo.

**Sintoma visual:** o home-btn e o texto "COMERCIAL" na appbar ficavam alguns pixels **mais abaixo** que os mesmos elementos na Classificação/Entrada/Venda, mesmo com CSS idêntico entre os módulos. Nenhum grep, leitura de código ou ajuste de CSS resolvia.

**Causa raiz:**
1. O BOM aparecia **antes** do `{% extends 'sankhya_integration/base.html' %}` no comercial.html
2. O Django renderizava o template normalmente, mas o BOM entrava no output HTML final **antes do `<!DOCTYPE html>`** herdado do base.html
3. O navegador encontrava o caractere invisível antes do DOCTYPE e entrava em **quirks mode**
4. Em quirks mode, cálculos de altura em flex containers se comportam diferente do standards mode → desalinhamento sutil do home-btn

**Como foi identificado:** inspecionando o DOM no DevTools — o usuário viu o texto `"﻿ "` (BOM) renderizado literalmente como primeiro filho do `<body>`, e a ausência da linha `<!DOCTYPE html>` no DOM do Comercial (enquanto Classificação tinha o DOCTYPE normalmente).

**Correção:** reescrever o arquivo `comercial.html` sem o BOM no início (usando o Write tool, que escreve o conteúdo literal sem adicionar BOM automático).

### Regra permanente — arquivos sempre em UTF-8 SEM BOM

> **Todos os arquivos de template Django (`*.html`), CSS (`*.css`), JS (`*.js`) e Python (`*.py`) devem ser salvos em UTF-8 SEM BOM.** O BOM no início de um template Django se propaga para o output HTML final antes do DOCTYPE, colocando a página em quirks mode e causando bugs de layout invisíveis a ferramentas de busca/edição normais. Se suspeitar de BOM em um arquivo, verifique os primeiros bytes com `head -c 3 arquivo.html | od -c` — o output correto começa com o primeiro caractere do conteúdo (ex: `{   %` para templates Django). Se aparecer `357 273 277` (bytes do BOM em octal), reescreva o arquivo.

### Módulo Venda — MVP de criação/edição de pedido TOP 34 (24 abr 2026)

Sessão focada em transformar o módulo Venda (que era apenas listagem + typeaheads de filtro) em ferramenta completa de criação, edição e exclusão de pedidos TOP 34.

#### Bugfix e faxina inicial
- **Paginação corrigida** — [views.py:1701](sankhya_integration/views.py#L1701): dict de filtros passava `"limit"` mas o service `listar_vendas_paginado` assina `limite`. Funcionava "por coincidência" (default 50 no JS coincidia com default no service). Quebraria silenciosamente se alguém mudasse o tamanho de página.
- **Código morto removido** de `view_portal_vendas`: variáveis `pagina`, `tamanho_pagina`, chave `"page"` do contexto, `vendas = []` e comentário obsoleto.

#### Endpoints novos (todos `@exige_grupo('venda')`)
| Rota | Método | Propósito |
|---|---|---|
| `venda/api/cabecalho/` | POST | Cria Pedido TOP 34 (INSERT em TGFCAB) |
| `venda/api/cabecalho/editar/` | POST | Atualiza cabeçalho existente (trava: só TOP 34) |
| `venda/api/cabecalho/obter/` | GET | Retorna cabeçalho + descrições (JOIN TSIEMP/TGFPAR/TGFTPV) |
| `venda/api/item/` | POST | Insere item em TGFITE + recalcula totais |
| `venda/api/excluir/` | POST | Exclui pedido completo (trava: só TOP 34) |
| `empresa/search/` | GET | Typeahead de empresas (TSIEMP) |
| `tipvenda/search/` | GET | Typeahead de tipos de negociação (TGFTPV) |

#### Funções novas em `oracle_conn.py` (aditivas, não afetam outros módulos)
- `consultar_empresas_oracle`, `consultar_tipos_negociacao_oracle`, `consultar_cabecalho_venda_oracle`
- `atualizar_cabecalho_venda_banco` — função dedicada da Venda. **Não reutiliza** `atualizar_cabecalho_nota_banco` porque esta tem "auto-cura de AD_NUMPEDIDOORIG" específica da Entrada/Classificação.

#### Alterações aprovadas explicitamente em `oracle_conn.py` (contornam a regra de intocabilidade, todas aditivas)
- `inserir_cabecalho_nota_banco` aceita `CODTIPVENDA` condicionalmente e consulta a `DHALTER` mais recente da TGFTPV para gravar `DHTIPVENDA`. **Exigência do trigger `SANKHYA.TRG_INC_TGFCAB`** (linhas 213-219): sem a tupla `(CODTIPVENDA, DHTIPVENDA)` coerente, Oracle rejeita com `ORA-20101: Verifique se o TIPO DE NEGOCIAÇÃO X está ativo...`.
- `inserir_item_nota_banco` ganhou o parâmetro `gerar_lote_auto: bool = True`. Default preserva o comportamento (Entrada continua gerando `NUNOTAS{SEQ}D{YYMMDD}`). Venda passa `False` — lote fica `NULL` por decisão de negócio (o lote só nasce na TOP 11; no futuro a Venda vai **selecionar** um lote existente para vincular estoque).

#### Armadilha importante descoberta em `oracle_conn.py`
- **`DPY-1001: not connected to database` mascara o erro real**: `inserir_cabecalho_nota_banco` tem um `except` que tenta `rollback()` numa conexão já fechada pelo context manager, substituindo a exceção Oracle original. **Workaround aplicado em todas as views de escrita da Venda**: view gerencia a conn com `with obter_conexao_oracle() as conn:` e passa `conexao_existente=conn` para o service, evitando o caminho bugado. Este workaround também dá acesso explícito a `commit()`/`rollback()` da view.

#### Frontend — fluxo completo
- **Novo pedido** (`btnNewVenda` da toolbar): `cabCard` dock-à-esquerda (padrão visual idêntico à Entrada, usando classes `offscreen-left` + `left:16px`). Campos: Empresa, Cliente, Tipo de Negociação, Data, Observação. Natureza (`10010100`) e C. Resultado (`10100`) são **labels carregados dinamicamente** do banco (fetch no `/natureza/search/` e `/cencus/search/` com o código hardcoded).
- **Ao salvar**: cabCard fica travado, `cabItemsCard` desliza da direita com formulário de item (produto typeahead, lote livre, volume, qtd, preço). Contador `itensInseridosCount` monitora se o pedido tem itens.
- **Fechar sem adicionar itens** dispara **auto-delete do cabeçalho órfão** (para não poluir TGFCAB). Detecção: `cab_nunota` setado + `itensInseridosCount === 0`. Delete paralelo à animação de slide.
- **Duplo clique numa linha da lista** (apenas TOP 34): abre os dois modais em modo edição — cabCard com os dados existentes (travado), cabItemsCard com os itens existentes carregados.
- **Botão "Editar Cabeçalho"** (substituiu o "Faturar Pedido" desabilitado): destrava cabCard e fecha o modal de itens. Cancelar restaura os valores originais via fetch.
- **Botão "Excluir"** da toolbar fica desabilitado até uma linha ser selecionada (click simples).

#### UX do cabCard
- `Enter` salva; `Esc` cancela. Ambos ignorados dentro de `<textarea>` (Observação) e enquanto houver dropdown de typeahead aberto.
- Campos obrigatórios ausentes ao salvar recebem borda vermelha (`#cabCard .ia-field-invalid`) e toast consolidado *"Preencha: Cliente, Tipo de negociação, Data."*.
- Inputs fazem `select()` ao receber foco (exceto `hidden`, `disabled` e `<textarea>`).
- `#cabCard.modal-card.small` tem largura reduzida a `380px` (só no módulo Venda, via `venda.css`).

#### Testes
65 testes no módulo Venda (antes: 0). Total do projeto: **68 → 133**. Classes:
`PortalVendasAcessoTest` (6) · `ApiListarVendasTest` (9) · `CriarCabecalhoVendaTest` (11) · `SalvarItemVendaTest` (12) · `ExcluirPedidoVendaTest` (7) · `ObterCabecalhoPedidoTest` (7) · `AtualizarCabecalhoVendaTest` (12).

#### Tabela CODNAT por TOP (referência para o futuro "Faturar" — C.4)

Quando o botão "Faturar" for implementado, a TOP muda de 34 para 35/37 e o CODNAT também muda. Tabela fornecida pelo usuário:

| TOP | CODNAT | Descrição |
|---|---|---|
| 34 | 10010100 | Pedido de Venda |
| 35 | 10010100 | Venda com NFe |
| 36 | 10020100 | (a confirmar) |
| 37 | 10010200 | Venda sem NFe |
| 99 | 10010400 | (a confirmar) |

No MVP atual (TOP 34 fixo), CODNAT é hardcoded em `10010100`. Quando C.4 chegar, transformar em dicionário `CODNAT_POR_TOP` em `api_faturar_pedido_venda` ou similar.

### Pendências do módulo Venda (ainda não implementadas)

- [ ] **C.4 — Botão "Faturar Pedido"**: hoje um placeholder foi substituído pelo "Editar Cabeçalho". Faturar requer:
  - Escolha TOP 35 (NFe) ou 37 (s/ NFe)
  - Aplicação da tabela `CODNAT_POR_TOP` acima
  - Possível disparo de emissão de NFe via serviço Sankhya
  - Trava para não permitir faturar pedido sem itens
  - Gerar título financeiro em TGFFIN (similar ao que o Comercial faz para TOP 13)
- [ ] **Vínculo Venda ↔ Compra (seleção de lote de estoque)**: hoje o item da Venda é inserido com `CODAGREGACAO=NULL`. A função "selecionar lote com saldo em TGFEST" precisa ser implementada (typeahead dinâmico filtrado por `codprod + codemp`). Tentativa iniciada e revertida nesta sessão (por faltar definição do fluxo). Quando implementar: também validar obrigatoriedade no backend `api_salvar_item_venda`.
- [ ] **Editar/remover item individualmente no modal de itens** (C.3 parcial): hoje o modal de itens só permite adicionar; editar ou remover uma linha já inserida ainda não está implementado.
- [ ] **CODNAT dropdown no cabeçalho**: para operações de revenda (além de venda de produção própria), promover o hardcoded `10010100` para dropdown consultando `/natureza/search/`, igual ao padrão do Comercial.

### Módulo Rastreio (WMS) — entrega completa (27 abr 2026)

Sessão dedicada ao módulo de Rastreabilidade que estava em estado de protótipo (mocks no JS). Hoje é uma feature completa de WMS com vinculação lote ↔ pedido de venda, sem tocar `TGFEST` nativa do Sankhya.

**Premissa arquitetural** — a alocação de lote a pedido é feita gravando `CODAGREGACAO` no `TGFITE` do pedido TOP 34. Saldos são lidos via uma view dedicada (`SANKHYA.ANDRE_IRIS_SALDO_LOTE`) que **não toca** `TGFEST` — toda a aritmética é derivada de `TGFITE`+`TGFCAB`. Triggers e cleanup do banco continuam sendo responsabilidade do Sankhya.

#### View `SANKHYA.ANDRE_IRIS_SALDO_LOTE` (5 pernas)

| # | STATUS_LINHA | Fonte | Vendável? |
|---|---|---|:-:|
| A | `CLASSIFICADO` | TOP 26 (lotes que têm classificação confirmada) | ✅ |
| B | `NAO_CLASSIFICAVEL` | TOP 13 (lotes que NÃO têm TOP 26) | ✅ |
| C | `AGUARDANDO_CLASSIFICACAO` | TOP 11 com `GERAPRODUCAO='S'` ainda sem TOP 26 (qtd pendente = QTDNEG − AD_QTDAVARIA − Σ TOP 26) | ❌ |
| D | `AVARIA_INTERNA` | TOP 30 (perda no estoque) | ❌ |
| E | `AVARIA_FORNECEDOR` | `AD_QTDAVARIA` da TOP 11 (descarte da classificação repassado ao fornecedor) | ❌ |

Fórmula: `QTD_DISPONIVEL = ENTRADA − Σ TOP 35/37 confirmadas − Σ TOP 30 confirmadas − Σ TOP 34 abertas`. As CTEs de baixa/reserva agregam por **`(CODPROD, CODAGREGACAO)` globalmente**, sem CODEMP — pra permitir vincular lote da empresa A em pedido da empresa B sem o saldo "ficar órfão" entre empresas. Discriminador A vs B: existência de TOP 26 confirmada.

Convenções de `STATUSNOTA`:
- Entradas (TOP 11/13/26): `STATUSNOTA <> 'E'` (não excluída)
- Baixas (TOP 35/37/30): `STATUSNOTA = 'L'` (liberada/confirmada)
- Reservas (TOP 34): `STATUSNOTA NOT IN ('L', 'E')` (em aberto)

Paginação compatível com Oracle 11g (`ROW_NUMBER() OVER ... BETWEEN`) — `OFFSET ... FETCH NEXT` foi tentado mas explode com ORA-00933 nesse ambiente.

#### Arquivos novos

| Arquivo | Papel |
|---|---|
| [sankhya_integration/sql/ANDRE_IRIS_SALDO_LOTE.sql](sankhya_integration/sql/ANDRE_IRIS_SALDO_LOTE.sql) | DDL da view (versionado) |
| [sankhya_integration/sql/ANDRE_IRIS_SALDO_LOTE_teste.sql](sankhya_integration/sql/ANDRE_IRIS_SALDO_LOTE_teste.sql) | 5 queries de conferência com `&p_lote` (DEFINE) |
| [sankhya_integration/tests/test_rastreio.py](sankhya_integration/tests/test_rastreio.py) | 25 testes mockados |

#### Funções novas em `oracle_conn.py` (todas aditivas)

- `consultar_saldo_lote_disponivel(filtros, limite=50, offset=0)` — lê da view, aceita `q`, `codprod`, `codprods` (lista IN), `codagregacao`, `fabricante`, `tipo` (`classificavel|nao_classificavel|todos`), `desde_dias`
- `consultar_pedidos_abertos_para_atribuicao(filtros, limite=50, offset=0)` — TOP 34 paginado por cabeçalho, com LEFT JOIN agrupado na TOP 11 trazendo origem do lote (data, NUNOTA, parceiro fornecedor)
- `atribuir_lote_item_pedido(nunota, sequencia, codagregacao, qtd=None)` — UPDATE simples se total, SPLIT (UPDATE qtd reduzida + INSERT nova linha) se parcial. Valida saldo somando entre empresas. Recalcula `VLRNOTA`/`QTDVOL` via `recalcular_totais_nota_banco`
- `desvincular_lote_item_pedido(nunota, sequencia)` — `UPDATE TGFITE SET CODAGREGACAO=NULL`. Bloqueia se pedido faturado/excluído
- `consultar_fabricantes_disponiveis(termo, limite=10)` — typeahead `SELECT DISTINCT FABRICANTE`
- `consultar_vinculos_de_lote(codagregacao)` — pedidos/vendas (TOP 34/35/37, sem TOP 13) que usam o lote
- Extensão de 4 linhas em `atualizar_item_nota_banco` aceita `CODAGREGACAO` no dict (mas a atribuição de pedido **não usa** essa função pra evitar a auto-cura de `AD_NUMPEDIDOORIG` que é específica da Entrada/Classificação)

#### Endpoints e rotas (todos `@exige_grupo('rastreio')`)

| Rota | Método | Função |
|---|---|---|
| `rastreio/` | GET | Página HTML (com decorator) |
| `rastreio/api/lotes-disponiveis/` | GET | Lista lotes paginada |
| `rastreio/api/pedidos-abertos/` | GET | Lista pedidos paginada |
| `rastreio/api/atribuir-lote/` | POST | Vincula lote a item |
| `rastreio/api/desvincular-lote/` | POST | Remove vínculo |
| `rastreio/api/fabricantes/` | GET | Typeahead distinct |
| `rastreio/api/lote-vinculos/` | GET | Pedidos/vendas que usam um lote |

`decorators.py` ganhou a chave `'rastreio': ['1', '6', '8', '9', '10']` (Diretoria, TI, Operação, Comercial, Vendas — "todos autenticados").

#### Frontend ([rastreio.js](sankhya_integration/static/sankhya_integration/rastreio.js) reescrito)

- **Cards compactos em 1 linha** — lote: `produto · parceiro · lote · data · qtd`; pedido (produto agregado por `(NUNOTA, CODPROD)`): `produto · vinculada/total · tag/falta`
- **Agrupamento por NUNOTA** com header `Parceiro | Data | Pedido NUNOTA`. Toggle PARCEIRO/PRODUTO troca o agrupador grosso
- **Filtros**:
  - Toggle TODOS / CLASSIFICÁVEIS / NÃO-CLASSIF de tipo de lote (radio)
  - Switch TRAVAR FILTRO (mantém filtro cruzado ao re-clicar)
  - Selects de Período: lotes (default 30d) e pedidos (default 10d) — janela `desde_dias`
  - Inputs de busca com **typeahead** (debounce 300ms, AbortController, ↑↓/Enter/Tab/Esc/clique fora)
    - Lotes: busca por **FABRICANTE** distinct
    - Pedidos: busca por NUNOTA (numérico) ou nome do parceiro
- **Filtro cruzado bidirecional** — estado `produtosFiltrados` (Set) + `pedidoIsolado` (NUNOTA):
  - Click no card de lote → filtra pedidos por aquele codprod
  - Click em produto-linha do pedido → filtra lotes por aquele codprod, e mostra só esse produto dentro do pedido
  - Click no header do pedido → ISOLA esse pedido (`?nunota=X` no fetch) + filtra lotes pelos N codprods dele. Em isolamento, ignora `desde_dias`/`codprods` pra não esconder o pedido alvo
  - Re-click → toggle limpa (a menos que TRAVAR FILTRO)
- **Drag&drop** lote → produto-linha:
  - Modal sugere `min(disp lote, qtd_falta total do produto)`
  - Trava do `max` no input impede vincular mais que o pedido pediu
  - Confirmação distribui qtd entre múltiplas linhas pendentes (split sequencial)
  - Recarrega ambos os painéis ao concluir
- **Modais de vínculos** (👁 nas linhas):
  - Lado lote (👁 do card): lista pedidos/vendas (TOP 34/35/37) com **DATA · NUNOTA · PARCEIRO (cliente) · PRODUTO · QTD**
  - Lado pedido (👁 do produto-linha): lista lotes vinculados com **DATA · NUNOTA · LOTE · PARCEIRO (fornecedor) · PRODUTO · QTD** (origem vem do JOIN direto com TGFITE+TGFCAB da TOP 11)
  - Click em linha mostra **botão lixeira** (com `confirm()`); confirma → POST desvincular → recarrega
  - Linhas TOP 35/37 (faturado) ficam sem botão — desvincular bloqueado
- **Scroll infinito** (50 por página, paginação por cabeçalho nos pedidos pra não cortar o pedido ao meio)

#### Templates e CSS

- [rastreio.html](sankhya_integration/templates/sankhya_integration/rastreio.html) — `{% block extra_js %}` (faltava!), 2 modais (`modalTransferencia`, `modalVinculos`), 2 selects de período, toggles, search-wraps
- [rastreio.css](sankhya_integration/static/sankhya_integration/rastreio.css) — 130 blocos: cards compactos (módulo 9), tags/badges/estados não-vendáveis (módulo 8), structure (módulo 7), typeahead dropdown (módulo 10), modal de vínculos com tabela responsiva, lixeira que aparece ao selecionar linha

#### Decisões de regra de negócio nesta sessão

1. **Listagem de pedidos ignora `STATUSNOTA = 'L'`** (mostra faturados na lista também) — só filtra `<> 'E'`. **Atribuição** ainda valida e bloqueia faturado.
2. **Multi-empresa não restritiva** — saldo do lote é somado entre empresas. Pode vincular lote da empresa A em pedido da empresa B (decisão explícita do usuário).
3. **In-natura pendente** (perna C) aparece como linha não-vendável (cinza tracejado), pra dar visibilidade ao operador.
4. **Avaria do fornecedor** (perna E, `AD_QTDAVARIA` da TOP 11) aparece como linha não-vendável separada — não some no card "in-natura pendente".
5. **Avaria interna** (perna D) aparece como **badge inline** vermelho `▼ Xkg` no card vendável (Opção A da arquitetura). Linha separada na view (Opção B) está pronta pra uso futuro.

#### Bugs corrigidos durante a sessão

- Template sem `{% block extra_js %}` → JS nunca carregava (tela branca)
- `OFFSET ... FETCH NEXT` (Oracle 12c+) → ORA-00933 → trocado por `ROW_NUMBER + BETWEEN` (Oracle 11g+)
- Loader "Carregando..." persistia → render movido pro `finally`
- Saldo não diminuía ao vincular cross-empresa → CTEs de baixas/reservas agora ignoram CODEMP
- Modal de pedidos com "—" em data/nunota/parceiro → JOIN substituído por subquery direta na TOP 11
- Modal de lotes mostrando fornecedor como cliente → TOP 13 removida do filtro

#### Pendências do Rastreio (não implementadas)

- [ ] **Distinguir visualmente FATURADO vs ATRIBUIDO** no card de pedido — hoje ambos viram "ATRIBUIDO" (verde). Pode ser badge "FATURADO" extra
- [ ] **Avaria interna como linha separada na UI** (Opção B) — perna D existe na view; UI hoje mostra só como badge. Trocar é só mudar o filtro do front
- [ ] **Cobertura de testes para os services novos** — `consultar_vinculos_de_lote`, `consultar_fabricantes_disponiveis`, `desvincular_lote_item_pedido`, `consultar_saldo_lote_disponivel`. Os endpoints estão cobertos via mock (25 testes); os services em si não
- [ ] **Janela temporal por padrão pode ser mais flexível** — hoje 30d (lotes) e 10d (pedidos) são fixos no HTML. Poderia ser persistido em `localStorage` por usuário
- [ ] **Audit log de atribuir/desvincular lote** — hoje só `logger.info`/`logger.exception`. Considerar tabela própria se compliance pedir
- [ ] **Documentação operacional** (manual do operador) — fluxo da tela, drag&drop, atribuição parcial, etc.

### Pendências identificadas na auditoria (ainda não implementadas)

- [ ] Separar `.env.dev` e `.env.prod` para evitar confusão entre `DEBUG=True` (dev) e `DEBUG=False` (prod)
- [ ] Configurar `collectstatic` e servidor de arquivos estáticos (nginx ou WhiteNoise) para ambiente de produção
- [ ] Substituir o middleware `ControleInatividadeMiddleware` por timeout de sessão nativo do Django (`SESSION_COOKIE_AGE`)
- [ ] Validação CSRF nas views que aceitam POST com JSON (verificar se o token está sendo enviado corretamente pelo frontend)
- [ ] Cobertura de testes para os módulos de Classificação e `oracle_conn.py` (Venda foi coberta na sessão de 24 abr 2026 — 65 testes)
- [ ] **CSS — avaliar separar `entrada.css` em dois arquivos:** `base-layout.css` (partes genuinamente globais) e `entrada.css` (específico do módulo Entrada), eliminando o carregamento implícito de estilos de Entrada em todos os módulos
- [ ] **CSS — avaliar unificação futura dos `@keyframes` locais** (`spin`, `iaspin`, `toastSlideIn/Out`) para os nomes globais (`ia-girar`, `ia-toast-entrada/saida`), o que exigirá atualizar as referências nos arquivos JS

---

## 3. Regras Permanentes de Desenvolvimento

> Estas regras se aplicam a **todas** as sessões futuras, sem exceção.

1. **Antes de criar qualquer função, método ou bloco de código novo**, verificar sempre se existe algo reutilizável no projeto. Nunca criar duplicatas — se houver lógica semelhante em outro lugar, apontar e sugerir consolidação.

2. **Nunca alterar lógica de negócio** (queries Oracle, cálculos financeiros, regras de precificação, fluxo de faturamento) sem aprovação explícita do usuário.

3. **Sempre apresentar um plano completo** com a lista de todos os arquivos que serão modificados antes de executar qualquer alteração. Aguardar aprovação ("sim") antes de começar.

4. **Executar uma tarefa por vez** e aguardar confirmação antes de passar para a próxima.

5. **Nunca alterar o `.env`** com valores que quebrem o ambiente de desenvolvimento (especialmente `DEBUG=False` — veja seção de Pontos de Atenção).

6. **Nunca commitar arquivos sensíveis**: `.env`, credenciais, tokens. O `.gitignore` já está configurado, mas conferir antes de qualquer `git add`.

7. **Testes novos não devem depender do Oracle**. Usar `unittest.mock.patch` ou `sys.modules` para isolar dependências de banco de dados.

---

## 4. Padrões do Projeto

### Estrutura de Pastas

```
IAgro/
├── .env                         # Variáveis de ambiente (não versionado)
├── .env.example                 # Template de variáveis (versionado, sem valores reais)
├── CLAUDE.md                    # Este arquivo
├── README.md
├── manage.py
├── requirements.txt
├── db.sqlite3                   # Banco Django (sessões + modelo Simulation)
│
├── IAgro/                       # Configuração Django (settings, urls raiz, wsgi/asgi)
│   ├── settings.py
│   ├── urls.py                  # Raiz: /admin/, /sankhya/ → sankhya_integration.urls
│   ├── wsgi.py
│   └── asgi.py
│
├── sankhya_integration/         # Único app Django do projeto
│   ├── apps.py                  # AppConfig com ready() para registrar signals
│   ├── models.py                # Apenas modelo Simulation (JSONField de simulações comerciais)
│   ├── views.py                 # Todas as views (~1850 linhas) — entrada, classificação, comercial, venda, rastreio
│   ├── urls.py                  # Todas as rotas do app (prefixo /sankhya/)
│   ├── decorators.py            # @exige_grupo, @check_vale_lock + GRUPOS_PERMITIDOS
│   ├── middleware.py            # ControleInatividadeMiddleware (timeout de sessão)
│   ├── context_processors.py   # app_version_processor, environment_badge
│   ├── admin.py                 # SimulationAdmin registrado
│   ├── signals.py               # Audit log de Simulation via post_save/post_delete
│   │
│   ├── services/
│   │   └── oracle_conn.py       # TODAS as queries Oracle (~2420 linhas) — núcleo do sistema
│   │
│   ├── templates/sankhya_integration/
│   │   ├── base.html            # Template base (navbar, scripts globais)
│   │   ├── home.html            # Tela inicial / login
│   │   ├── entrada.html         # Portal de Entrada (TOP 11)
│   │   ├── classificacao.html   # Portal de Classificação de Lotes
│   │   ├── comercial.html       # Painel Comercial (faturamento, vales, negociação)
│   │   ├── venda.html           # Portal de Vendas
│   │   ├── venda_modais.html    # Modais do portal de vendas
│   │   └── rastreio.html        # Rastreabilidade de lotes
│   │
│   ├── static/sankhya_integration/
│   │   ├── global.css                       # Tokens de design e componentes globais
│   │   ├── iagro_helpers.js                # Helpers JS reutilizáveis (getCookie, postJSON, etc.)
│   │   ├── entrada.css / entrada.js        # Módulo de Entrada
│   │   ├── classificacao.css / classificacao.js  # Módulo de Classificação
│   │   ├── comercial.css / comercial.js    # Módulo Comercial (painel principal)
│   │   ├── comercialDistribuicao.js        # Sub-módulo: distribuição de pesos
│   │   ├── comercialFinanceiro.js          # Sub-módulo: geração de financeiro
│   │   ├── comercialImpressao.js           # Sub-módulo: impressão de vales
│   │   ├── home.css / home.js              # Tela inicial
│   │   ├── venda.css / venda.js            # Módulo de Vendas
│   │   └── rastreio.css / rastreio.js      # Rastreabilidade
│   │
│   ├── sql/
│   │   ├── ANDRE_IRIS_SALDO_LOTE.sql       # DDL da view de saldo de lote (Rastreio/WMS)
│   │   └── ANDRE_IRIS_SALDO_LOTE_teste.sql # Queries de conferência manual da view
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_views_entrada.py           # Testes: Entrada, health, conversor de tipos
│       ├── test_views_comercial.py         # Testes: Comercial, faturamento, vales
│       ├── test_views_venda.py             # Testes: Venda (TOP 34) — 65 testes
│       └── test_rastreio.py                # Testes: Rastreio/WMS — 25 testes
│
└── images/                      # Imagens (logo, etc.) — também em STATICFILES_DIRS
```

### Responsabilidades por Módulo

| Módulo | Views | Template | JS Principal | Acesso (grupos) |
|---|---|---|---|---|
| Entrada | `view_portal_entradas`, `api_listar_itens_nota`, `item_save`, `item_finalize`, etc. | `entrada.html` | `entrada.js` | 1, 6, 8 |
| Classificação | `view_classificacao_lote`, `api_lotes_classificacao`, `api_detalhes_lote`, etc. | `classificacao.html` | `classificacao.js` | 1, 6, 8 |
| Comercial | `view_comercial_painel`, `api_gerar_financeiro_banco`, `api_salvar_vale_comercial`, etc. | `comercial.html` | `comercial.js` + sub-módulos | 1, 6, 9 |
| Venda | `view_venda_portal`, `api_listar_vendas` | `venda.html` | `venda.js` | 1, 6, 10 |
| Rastreio (WMS) | `api_rastreio_view`, `api_rastreio_lotes_disponiveis`, `api_rastreio_pedidos_abertos`, `api_rastreio_atribuir_lote`, `api_rastreio_desvincular_lote`, `api_rastreio_fabricantes`, `api_rastreio_lote_vinculos` | `rastreio.html` | `rastreio.js` | 1, 6, 8, 9, 10 |

### URL Base

```
/ → redireciona para /sankhya/
/admin/ → Django Admin
/sankhya/ → home (login)
/sankhya/compras/portal/ → Entrada
/sankhya/compras/classificacao/ → Classificação
/sankhya/comercial/ → Comercial
/sankhya/venda/portal/ → Venda
/sankhya/health/ → Health check (sem autenticação)
```

### Autenticação

O sistema **não usa** `django.contrib.auth`. O login é feito via API HTTP do Sankhya (`hfsemear.ddns.net:8180`). Os dados do usuário autenticado ficam na sessão Django:

```python
session['codusu']   # ID do usuário no Sankhya
session['nomeusu']  # Nome de usuário (login)
session['nome']     # Nome completo
session['grupos']   # Lista de strings com IDs de grupo: ['1'], ['8', '9'], etc.
```

O decorator `@exige_grupo('modulo')` em `decorators.py` valida o acesso por grupo antes de cada view protegida.

### Padrão de Resposta das APIs

Todas as APIs JSON do sistema retornam:

```json
{"ok": true, "...dados..."}     // sucesso
{"ok": false, "error": "..."}   // falha de negócio (400 ou 500)
```

### Helpers JavaScript

O arquivo `iagro_helpers.js` centraliza funções utilitárias usadas em todos os módulos:

- `getCookie(name)` — lê cookie (para CSRF token)
- `postJSON(url, data)` — wrapper de `fetch` com content-type JSON e CSRF header
- Outros utilitários de UI (toasts, modais)

**Os módulos `compras_portal` (entrada) e `compras_classificacao` usam wrappers de compatibilidade** que preferem as funções centrais (`window.getCookie`, `window.postJSON`) e fazem fallback local se não estiverem disponíveis.

---

## 5. Variáveis de Ambiente (`.env`)

O arquivo `.env` fica na raiz do projeto e é carregado pelo `python-dotenv` no início de `settings.py`.

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DJANGO_ENV` | Sim | Ambiente atual. Valores: `production` ou `homologacao` (padrão). Controla o badge de ambiente exibido na navbar. |
| `SECRET_KEY` | Sim | Chave secreta do Django para assinatura de sessões e CSRF. Nunca expor publicamente. |
| `DEBUG` | Sim | `True` em desenvolvimento, `False` em produção. **Atenção: `False` desativa o servidor de arquivos estáticos do `runserver`.** |
| `ALLOWED_HOSTS` | Sim | Lista de hosts permitidos separada por vírgula. Ex: `127.0.0.1,localhost` em dev, hostname real em prod. |
| `ORACLE_CLIENT_LIB_DIR` | Sim | Caminho para o Oracle Instant Client (ex: `C:\oracle\instantclient_19_23`). Necessário para o `oracledb` em modo thick. |
| `SANKHYA_DB_HOST` | Sim | Host do servidor Oracle do Sankhya (ex: `hfsemear.ddns.net`). |
| `SANKHYA_DB_PORT` | Sim | Porta Oracle (padrão: `1521`). |
| `SANKHYA_DB_SERVICE` | Sim | Service name do Oracle (ex: `XE`). |
| `SANKHYA_DB_USER` | Sim | Usuário do Oracle. |
| `SANKHYA_DB_PASSWORD` | Sim | Senha do Oracle. |
| `SECURE_SSL_REDIRECT` | Não | `True` para redirecionar HTTP→HTTPS. **Ativar somente em produção com HTTPS configurado.** |
| `SECURE_HSTS_SECONDS` | Não | Duração do HSTS em segundos (ex: `31536000` = 1 ano). Ativar após validar HTTPS. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Não | `True` para estender HSTS a subdomínios. |
| `SECURE_HSTS_PRELOAD` | Não | `True` para incluir no preload list do browser. |
| `SESSION_COOKIE_SECURE` | Não | `True` para transmitir cookie de sessão apenas via HTTPS. |
| `CSRF_COOKIE_SECURE` | Não | `True` para transmitir cookie CSRF apenas via HTTPS. |

### Valores para Desenvolvimento (padrão atual no `.env`)

```dotenv
DJANGO_ENV=homologacao
DEBUG=True
ALLOWED_HOSTS=*
```

### Valores para Produção (descomentar quando servidor tiver HTTPS)

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

## 6. Pontos de Atenção

### CRÍTICO — `DEBUG=False` quebra arquivos estáticos em desenvolvimento

O servidor de desenvolvimento do Django (`runserver`) **não serve arquivos estáticos** quando `DEBUG=False`. Definir `DEBUG=False` no `.env` em um ambiente sem nginx/WhiteNoise configurado fará com que todo JS e CSS pare de carregar, quebrando completamente as páginas de Entrada, Classificação e Comercial.

**Regra:** Nunca alterar `DEBUG` no `.env` sem confirmar que o usuário tem um servidor web de arquivos estáticos configurado na frente do Django.

---

### `oracle_conn.py` — Núcleo crítico (~2420 linhas)

Este arquivo contém **todas as queries SQL ao Oracle** e as funções de conexão/transação. É o ponto mais sensível do sistema.

- **Não refatorar sem aprovação explícita** — qualquer mudança pode quebrar queries de produção
- A função `obter_conexao_oracle()` é um context manager que gerencia commit/rollback
- A flag `is_write_enabled()` controla se operações de escrita (INSERT/UPDATE) estão habilitadas
- `perfis_banco` (`local`/`remote`) foi esvaziado; a conexão agora usa exclusivamente as variáveis `SANKHYA_DB_*` do `.env`

---

### Views com imports locais (dentro do corpo da função)

Algumas views em `views.py` fazem imports **dentro do corpo da função** (não no topo do arquivo):
- `api_gerar_financeiro_banco` — importa `gerar_financeiro_banco` de `oracle_conn`
- `api_desfaturar_vale` — importa `desfaturar_comercial_banco` de `oracle_conn`

**Consequência para testes:** O patch deve apontar para o módulo de origem:
```python
# CORRETO:
@patch('sankhya_integration.services.oracle_conn.gerar_financeiro_banco', ...)
# ERRADO (não funciona para imports locais):
@patch('sankhya_integration.views.gerar_financeiro_banco', ...)
```

---

### `api_listar_vales_comercial` — Endpoint sem autenticação

A view `api_listar_vales_comercial` (rota `comercial/lista/`) **não possui o decorator `@exige_grupo`**. Qualquer requisição GET retorna dados mesmo sem sessão autenticada. Este comportamento está documentado nos testes e deve ser avaliado se é intencional.

---

### Retorno de tuplas do Oracle (não dicts)

As funções de `oracle_conn.py` retornam dados como **listas de tuplas** (formato nativo do cursor Oracle), não como dicts. As views acessam os campos por índice (`r[0]`, `r[1]`, etc.).

Ordem das colunas para `listar_itens_por_nota`:
```
r[0]=lote, r[1]=seq, r[2]=codprod, r[3]=descr, r[4]=codvol,
r[5]=qtdneg, r[6]=peso, r[7]=vlu, r[8]=vlt, ..., r[11]=qtdconferida
```

Ao adicionar novas colunas a qualquer query, os índices de todas as colunas seguintes mudam — verificar todos os usos.

---

### Mapeamento de Grupos Sankhya

```
'1'  → Diretoria     — acesso irrestrito a todos os módulos
'6'  → Suporte TI    — acesso irrestrito para manutenção e suporte
'8'  → Operação      — acesso aos módulos de Entrada e Classificação
'9'  → Comercial     — acesso exclusivo ao módulo Comercial
'10' → Vendas        — acesso exclusivo ao módulo de Vendas
```

Para consultar os grupos no Sankhya: `SELECT CODGRU, DESCRGRU FROM TSIGRU ORDER BY CODGRU`

---

### Signals — Cobertura limitada ao modelo Simulation

Os signals Django (`signals.py`) geram audit log **apenas para o modelo `Simulation`** (único modelo ORM do projeto). Todas as operações financeiras e de estoque são escritas diretamente no Oracle via SQL — essas operações são auditadas pelos logs do Django (`logger.debug()`/`logger.info()`) nas views correspondentes.

---

## 7. Executando o Projeto

### Desenvolvimento

```bash
# Ativar ambiente virtual
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Migrações (apenas para SQLite/Simulation)
python manage.py migrate

# Servidor de desenvolvimento
python manage.py runserver
```

### Executar Testes

```bash
# Todos os testes
python manage.py test sankhya_integration.tests

# Módulo específico
python manage.py test sankhya_integration.tests.test_views_entrada
python manage.py test sankhya_integration.tests.test_views_comercial
python manage.py test sankhya_integration.tests.test_views_venda
python manage.py test sankhya_integration.tests.test_rastreio
```

### Acesso

- Aplicação: `http://127.0.0.1:8000/sankhya/`
- Admin Django: `http://127.0.0.1:8000/admin/`
- Health check: `http://127.0.0.1:8000/sankhya/health/`

---

## 8. Comunicação

- **Idioma:** Sempre responder em Português Brasileiro
- **Plano antes de agir:** Para qualquer alteração em código, apresentar primeiro o plano completo com os arquivos afetados e aguardar aprovação
- **Uma tarefa por vez:** Executar e confirmar antes de avançar
- **Sem lógica de negócio alterada:** Queries, cálculos e fluxos de dados são intocáveis sem aprovação explícita
