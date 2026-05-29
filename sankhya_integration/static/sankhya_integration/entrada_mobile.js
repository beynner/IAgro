/* ==========================================================================
   ENTRADA MOBILE — redesign app-like (Mai/2026)
   Fase 2: navegação stack + hidratação da lista + tap em card → tela 2
   Fase 3 (próxima): tela 3 conferir item + salvar e próximo

   Convive com entrada.js (desktop) — só ativa em viewport ≤900px.
   ========================================================================== */
;(function () {
    'use strict';

    var mqMobile = window.matchMedia('(max-width: 900px)');
    var mob = document.querySelector('.entrada-mobile');

    if (!mob) return;

    // Se ainda não é mobile, ouve mudanças de viewport e ativa só quando precisa
    if (!mqMobile.matches) {
        try {
            mqMobile.addEventListener('change', function (e) {
                if (e.matches) location.reload();
            });
        } catch (e) { /* Safari antigo usa addListener */ }
        return;
    }

    /* ======================================================================
       STACK DE NAVEGAÇÃO entre telas
       ====================================================================== */
    var screens = {};
    mob.querySelectorAll('.m-screen').forEach(function (el) {
        screens[el.dataset.screen] = el;
    });
    var stack = ['lista'];

    function setActiveScreen(name) {
        // Ao sair da tela 'lista' (ou ao voltar pra ela), fecha qualquer swipe
        // aberto nos cards de nota — evita estado "preso" entre navegações
        fecharTodosSwipesNotas();
        Object.keys(screens).forEach(function (k) {
            screens[k].classList.toggle('is-active', k === name);
        });
        // Bottom nav reflete tela ativa (apenas lista é mapeado)
        mob.querySelectorAll('.m-bottom-nav__item').forEach(function (b) {
            b.classList.toggle('is-active', b.dataset.nav === 'lista' && name === 'lista');
        });
    }

    // Fecha qualquer card de nota que esteja com swipe aberto. Chamado em
    // transições de tela e ao abrir bottom sheets pra resetar o estado visual.
    function fecharTodosSwipesNotas() {
        document.querySelectorAll('#m_notasList .m-card-nota[data-swipe-open="1"]').forEach(function (card) {
            card.style.transform = '';
            card.dataset.swipeOpen = '0';
        });
    }

    function pushScreen(name) {
        if (!screens[name]) return;
        if (stack[stack.length - 1] === name) return;
        stack.push(name);
        setActiveScreen(name);
        try { history.pushState({ screen: name }, '', '#' + name); } catch (e) { }
    }

    function popScreen() {
        if (stack.length <= 1) return;
        stack.pop();
        setActiveScreen(stack[stack.length - 1]);
    }

    function popToRoot() {
        stack = ['lista'];
        setActiveScreen('lista');
    }

    // Botão back do Android volta pra tela anterior
    window.addEventListener('popstate', function () {
        if (stack.length > 1) popScreen();
    });

    // Botões "voltar" das telas
    mob.querySelectorAll('[data-back-to]').forEach(function (btn) {
        btn.addEventListener('click', function () { popScreen(); });
    });

    /* ======================================================================
       BOTTOM SHEETS (filtros e cabeçalho)
       ====================================================================== */
    var sheets = {};
    mob.querySelectorAll('.m-sheet').forEach(function (el) {
        sheets[el.dataset.sheet] = el;
    });

    function openSheet(name) {
        var s = sheets[name];
        if (!s) return;
        // Reseta swipes abertos da lista — qualquer abertura de sheet deve
        // limpar o estado visual prévio pra evitar "lixeira/lápis presos"
        if (typeof fecharTodosSwipesNotas === 'function') fecharTodosSwipesNotas();
        s.setAttribute('aria-hidden', 'false');
    }

    function closeSheet(sheetEl) {
        if (typeof sheetEl === 'string') sheetEl = sheets[sheetEl];
        if (sheetEl) sheetEl.setAttribute('aria-hidden', 'true');
    }

    mob.querySelectorAll('[data-open-sheet]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var nome = btn.dataset.openSheet;
            // Popula o sheet de cabeçalho com dados da nota corrente
            if (nome === 'cabec') popularSheetCabec();
            openSheet(nome);
        });
    });

    // Popula campos editáveis a partir do endpoint ajax_header (paridade
    // desktop entrada.js:1004). Empresa, Parceiro, TOP, Natureza, Centro
    // permanecem readonly; Data e Observação são editáveis.
    function popularSheetCabec() {
        if (!ESTADO_NOTA.nunota) return;
        var url = '/sankhya/compras/central/?nunota=' + encodeURIComponent(ESTADO_NOTA.nunota) + '&ajax_header=1';

        var setVal = function (id, v) { var el = document.getElementById(id); if (el) el.value = v || ''; };
        setVal('m_editEmpresa', 'Carregando…');
        setVal('m_editParceiro', ESTADO_NOTA.parc || '');
        setVal('m_editData', '');
        setVal('m_editTop', '');
        setVal('m_editNat', '');
        setVal('m_editCencus', '');
        setVal('m_editObs', '');

        fetch(url, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                var f = (j && j.form) ? j.form : {};
                var codemp = f.codemp || '10';
                var codparc = f.codparc || '';
                var nomparc = f.nomparc || f.nomeparc || '';
                var dtneg = f.dtneg || '';
                var topCode = f.codtipoper || '';
                var topDescr = f.codtipoper_descr || '';
                var natCode = f.codnat || '';
                var natDescr = f.codnat_descr || '';
                var cencusCode = f.codcencus || '';
                var cencusDescr = f.codcencus_descr || '';

                setVal('m_editEmpresa', codemp);
                setVal('m_editParceiro', codparc && nomparc ? (codparc + ' — ' + nomparc) : (codparc || ESTADO_NOTA.parc || ''));
                setVal('m_editData', dtneg);
                setVal('m_editTop', topCode ? (topCode + ' — ' + topDescr) : '11 — Pedido de Compra');
                setVal('m_editNat', natCode ? (natCode + ' — ' + natDescr) : '20010100 — Produtos para Venda');
                setVal('m_editCencus', cencusCode ? (cencusCode + ' — ' + cencusDescr) : '10100 — Comercialização');
                setVal('m_editObs', f.obs || '');
            })
            .catch(function () {
                setVal('m_editEmpresa', '10');
                mostrarToast('Falha ao carregar cabeçalho — alguns campos podem estar incompletos.', 'error');
            });
    }

    // Salvar edição do cabeçalho via POST /sankhya/header/update/
    var btnEditCabecSalvar = document.getElementById('m_btnEditCabecSalvar');
    if (btnEditCabecSalvar) {
        btnEditCabecSalvar.addEventListener('click', function () {
            if (!ESTADO_NOTA.nunota) return;
            var nun = parseInt(ESTADO_NOTA.nunota, 10);
            var dtnegEl = document.getElementById('m_editData');
            var obsEl = document.getElementById('m_editObs');
            var dtneg = dtnegEl ? dtnegEl.value : '';
            var obs = obsEl ? obsEl.value : '';

            if (!dtneg) {
                if (dtnegEl) dtnegEl.classList.add('is-invalid');
                mostrarToast('Informe a data da negociação.', 'error');
                return;
            }

            btnEditCabecSalvar.disabled = true;
            btnEditCabecSalvar.classList.add('is-loading');

            fetch('/sankhya/header/update/', {
                method: 'POST', credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrf(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    nunota: nun,
                    dtneg: dtneg,
                    dtmov: dtneg,
                    dtentsai: dtneg,
                    obs: obs
                })
            })
                .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
                .then(function (resp) {
                    btnEditCabecSalvar.disabled = false;
                    btnEditCabecSalvar.classList.remove('is-loading');
                    var j = resp.body;
                    if (!j || !j.executed) {
                        if (handleValeLockedError(resp.status, j)) return;
                        var erros = (j && j.errors) || [];
                        mostrarToast(erros[0] || (j && j.error) || 'Falha ao atualizar cabeçalho.', 'error');
                        return;
                    }
                    mostrarToast('Cabeçalho atualizado ✓', 'success');
                    closeSheet('cabec');
                })
                .catch(function () {
                    btnEditCabecSalvar.disabled = false;
                    btnEditCabecSalvar.classList.remove('is-loading');
                    mostrarToast('Falha de rede ao salvar cabeçalho.', 'error');
                });
        });

        ['m_editData', 'm_editObs'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('input', function () { el.classList.remove('is-invalid'); });
        });
    }

    mob.querySelectorAll('[data-close-sheet]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var sheetEl = btn.closest('.m-sheet');
            if (sheetEl) closeSheet(sheetEl);
        });
    });

    /* ======================================================================
       BOTTOM NAV
       ====================================================================== */
    mob.querySelectorAll('.m-bottom-nav__item').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var nav = btn.dataset.nav;
            if (nav === 'lista') {
                popToRoot();
            } else if (nav === 'buscar') {
                popToRoot();
                var search = document.getElementById('m_search');
                if (search) setTimeout(function () { search.focus(); }, 120);
            }
            // 'filtros' e 'mais' são tratados via data-open-sheet/data-sidebar-toggle
        });
    });

    /* ======================================================================
       SIDEBAR TOGGLE (hambúrguer abre sidebar IAgro global)
       ====================================================================== */
    mob.querySelectorAll('[data-sidebar-toggle]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var global = document.getElementById('btnSidebarToggleMobile');
            if (global) global.click();
        });
    });

    /* ======================================================================
       HIDRATAÇÃO — converte tabela desktop em cards mobile
       Reusa dados já renderizados server-side por entrada.html (.entrada-desktop)
       ====================================================================== */
    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[c];
        });
    }

    function fmtBr(n) {
        var v = parseFloat(n);
        if (isNaN(v)) return '0';
        return v.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    }

    // Estado da paginação infinita
    var pgInfinita = {
        page: 1,
        hasNext: false,
        carregando: false,
    };
    var buscaFetchToken = 0;   // pra ignorar respostas obsoletas em buscas concorrentes

    function lerEstadoPaginacao() {
        // Lê data-attrs do #notasList do desktop server-rendered
        var src = document.querySelector('.entrada-desktop #notasList');
        if (!src) return;
        pgInfinita.page = parseInt(src.dataset.currentPage || '1', 10) || 1;
        pgInfinita.hasNext = String(src.dataset.hasNext || '0') === '1';
    }

    function hidratarListaNotas() {
        var rows = document.querySelectorAll('.entrada-desktop #notasTable tbody tr.row--click');
        var lista = document.getElementById('m_notasList');
        var empty = document.getElementById('m_listaEmpty');
        if (!lista) return;

        lerEstadoPaginacao();

        if (!rows.length) {
            lista.innerHTML = '';
            if (empty) empty.hidden = false;
            return;
        }
        if (empty) empty.hidden = true;

        var html = '';
        rows.forEach(function (tr) {
            var nunota = tr.dataset.nunota || '';
            var cells = tr.querySelectorAll('td');
            if (cells.length < 3) return;
            var pedido = cells[0].textContent.trim();
            var data = cells[1].textContent.trim();
            var dataCurta = data.split('/').slice(0, 2).join('/');
            var parc = cells[2].textContent.trim();
            var letra = (parc.match(/[A-Za-zÀ-ÿ]/) || ['?'])[0].toUpperCase();

            html += '<div class="m-card-nota-wrap">' +
                '<button class="m-card-nota__swipe-edit" data-nunota="' + escapeHtml(nunota) + '" aria-label="Editar cabeçalho">' +
                    '<i class="ph ph-pencil-simple" aria-hidden="true"></i>' +
                '</button>' +
                '<button class="m-card-nota__swipe-del" data-nunota="' + escapeHtml(nunota) + '" aria-label="Excluir">' +
                    '<i class="ph ph-trash" aria-hidden="true"></i>' +
                '</button>' +
                '<article class="m-card-nota" data-nunota="' + escapeHtml(nunota) +
                    '" data-pedido="' + escapeHtml(pedido) +
                    '" data-data="' + escapeHtml(data) +
                    '" data-parc="' + escapeHtml(parc) + '">' +
                    '<div class="m-card-nota__avatar" data-letra="' + escapeHtml(letra) + '">' +
                        escapeHtml(letra) + '</div>' +
                    '<span class="m-card-nota__nome">' + escapeHtml(parc) + '</span>' +
                    '<span class="m-card-nota__pedido">Pedido ' + escapeHtml(pedido) + '</span>' +
                    '<span class="m-card-nota__data">' + escapeHtml(dataCurta) + '</span>' +
                    '<i class="ph ph-caret-right m-card-nota__chevron" aria-hidden="true"></i>' +
                '</article>' +
            '</div>';
            // Nota: status (verde/âmbar/vermelho) e % chegam na Fase 3 (precisa agregar itens)
        });
        lista.innerHTML = html;
        bindCardsNota();
        atualizarBadgeFiltros();
        renderSentinela();
    }

    // Sentinela no fim da lista (visual apenas — o disparo é via scroll listener)
    function renderSentinela() {
        var lista = document.getElementById('m_notasList');
        if (!lista) return;
        var sent = document.getElementById('m_listaSentinela');
        if (sent) sent.remove();
        if (!pgInfinita.hasNext) return;
        sent = document.createElement('div');
        sent.id = 'm_listaSentinela';
        sent.className = 'm-lista-sentinela';
        sent.innerHTML = '<i class="ph ph-spinner"></i><span>Carregando mais…</span>';
        lista.appendChild(sent);
    }

    // Scroll listener no container — dispara só em scroll real do operador.
    // IntersectionObserver caiu em loop infinito porque cada nova sentinela
    // aparecia dentro do viewport sem operador rolar (cards anexados acima
    // não pushavam a sentinela pra fora). Setup feito 1× no boot.
    function setupScrollPaginar() {
        var scrollArea = document.getElementById('m_listaScroll');
        if (!scrollArea) return;
        var lastScrollTop = 0;
        scrollArea.addEventListener('scroll', function () {
            if (pgInfinita.carregando || !pgInfinita.hasNext) return;
            var st = scrollArea.scrollTop;
            // Só dispara quando operador rola PARA BAIXO (delta positivo)
            if (st <= lastScrollTop) { lastScrollTop = st; return; }
            lastScrollTop = st;
            var threshold = scrollArea.scrollHeight - scrollArea.clientHeight - 200;
            if (st >= threshold) carregarMaisNotas();
        }, { passive: true });
    }

    function carregarMaisNotas() {
        if (pgInfinita.carregando || !pgInfinita.hasNext) return;
        pgInfinita.carregando = true;
        var proxima = pgInfinita.page + 1;
        // Preserva todos os filtros atuais da URL (que vieram do server-side)
        var url = window.location.pathname + window.location.search;
        url += (url.indexOf('?') >= 0 ? '&' : '?') + 'page=' + proxima;

        fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'text/html' } })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, 'text/html');
                var rows = doc.querySelectorAll('#notasTable tbody tr.row--click');
                var srcList = doc.querySelector('#notasList');
                if (srcList) {
                    pgInfinita.page = parseInt(srcList.dataset.currentPage || String(proxima), 10);
                    pgInfinita.hasNext = String(srcList.dataset.hasNext || '0') === '1';
                } else {
                    pgInfinita.page = proxima;
                    pgInfinita.hasNext = false;
                }
                // Libera flag ANTES do append — appendCardsNotas pode chamar
                // autoPaginarComBusca que verifica esta flag pra encadear
                pgInfinita.carregando = false;
                appendCardsNotas(rows);
            })
            .catch(function () {
                pgInfinita.carregando = false;
                // Falha — não tenta de novo automaticamente; usuário pode usar Atualizar
            });
    }

    function appendCardsNotas(rows) {
        var lista = document.getElementById('m_notasList');
        if (!lista || !rows.length) {
            renderSentinela();  // re-cria/remove conforme hasNext
            return;
        }
        var sent = document.getElementById('m_listaSentinela');
        var html = '';
        rows.forEach(function (tr) {
            var nunota = tr.dataset.nunota || '';
            var cells = tr.querySelectorAll('td');
            if (cells.length < 3) return;
            var pedido = cells[0].textContent.trim();
            var data = cells[1].textContent.trim();
            var dataCurta = data.split('/').slice(0, 2).join('/');
            var parc = cells[2].textContent.trim();
            var letra = (parc.match(/[A-Za-zÀ-ÿ]/) || ['?'])[0].toUpperCase();

            html += '<div class="m-card-nota-wrap">' +
                '<button class="m-card-nota__swipe-edit" data-nunota="' + escapeHtml(nunota) + '" aria-label="Editar cabeçalho">' +
                    '<i class="ph ph-pencil-simple" aria-hidden="true"></i>' +
                '</button>' +
                '<button class="m-card-nota__swipe-del" data-nunota="' + escapeHtml(nunota) + '" aria-label="Excluir">' +
                    '<i class="ph ph-trash" aria-hidden="true"></i>' +
                '</button>' +
                '<article class="m-card-nota" data-nunota="' + escapeHtml(nunota) +
                    '" data-pedido="' + escapeHtml(pedido) +
                    '" data-data="' + escapeHtml(data) +
                    '" data-parc="' + escapeHtml(parc) + '">' +
                    '<div class="m-card-nota__avatar" data-letra="' + escapeHtml(letra) + '">' + escapeHtml(letra) + '</div>' +
                    '<span class="m-card-nota__nome">' + escapeHtml(parc) + '</span>' +
                    '<span class="m-card-nota__pedido">Pedido ' + escapeHtml(pedido) + '</span>' +
                    '<span class="m-card-nota__data">' + escapeHtml(dataCurta) + '</span>' +
                    '<i class="ph ph-caret-right m-card-nota__chevron" aria-hidden="true"></i>' +
                '</article>' +
            '</div>';
        });
        // Insere antes da sentinela (que sempre fica no fim)
        if (sent) sent.insertAdjacentHTML('beforebegin', html);
        else lista.insertAdjacentHTML('beforeend', html);
        bindCardsNota();
        renderSentinela();  // recria pra observer pegar o novo final

    }

    // Busca server-side ágil — substituiu o auto-paginar client-side de Mai/2026.
    // Operador digita → debounce 250ms → fetch `?q=...` com filtros atuais →
    // server retorna apenas matches → replace cards (não append). Token previne
    // race quando operador digita rápido (response antiga descartada).
    function buscarServerSide(termo) {
        var meuToken = ++buscaFetchToken;
        var lista = document.getElementById('m_notasList');
        var sent = document.getElementById('m_listaSentinela');
        if (sent) sent.remove();

        // Monta URL: pathname atual + querystring atual com `q` substituído
        var params = new URLSearchParams(window.location.search);
        if (termo) params.set('q', termo);
        else params.delete('q');
        params.set('page', '1');
        var url = window.location.pathname + '?' + params.toString();

        // Feedback visual de "buscando" instantâneo (não espera response)
        if (lista) {
            var loader = document.createElement('div');
            loader.id = 'm_listaSentinela';
            loader.className = 'm-lista-sentinela';
            loader.innerHTML = '<i class="ph ph-spinner"></i><span>Buscando…</span>';
            lista.appendChild(loader);
        }

        fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'text/html' } })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                if (meuToken !== buscaFetchToken) return;   // resposta obsoleta — descarta
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, 'text/html');
                var rows = doc.querySelectorAll('#notasTable tbody tr.row--click');
                var srcList = doc.querySelector('#notasList');
                if (srcList) {
                    pgInfinita.page = parseInt(srcList.dataset.currentPage || '1', 10) || 1;
                    pgInfinita.hasNext = String(srcList.dataset.hasNext || '0') === '1';
                } else {
                    pgInfinita.page = 1;
                    pgInfinita.hasNext = false;
                }
                substituirCardsNotas(rows);
                atualizarBadgeFiltros();
            })
            .catch(function () {
                if (meuToken !== buscaFetchToken) return;
                var s = document.getElementById('m_listaSentinela');
                if (s) s.remove();
            });
    }

    // Substitui TODA a lista de cards mobile (usada após busca server-side)
    function substituirCardsNotas(rows) {
        var lista = document.getElementById('m_notasList');
        var empty = document.getElementById('m_listaEmpty');
        if (!lista) return;
        if (!rows.length) {
            lista.innerHTML = '';
            if (empty) {
                var temBusca = searchInput && searchInput.value.trim();
                empty.hidden = false;
                var p = empty.querySelector('p');
                if (p) p.textContent = temBusca ? ('Nenhuma nota com "' + searchInput.value.trim() + '".') : 'Nenhuma nota no período.';
            }
            return;
        }
        if (empty) empty.hidden = true;
        var html = '';
        rows.forEach(function (tr) {
            var nunota = tr.dataset.nunota || '';
            var cells = tr.querySelectorAll('td');
            if (cells.length < 3) return;
            var pedido = cells[0].textContent.trim();
            var data = cells[1].textContent.trim();
            var dataCurta = data.split('/').slice(0, 2).join('/');
            var parc = cells[2].textContent.trim();
            var letra = (parc.match(/[A-Za-zÀ-ÿ]/) || ['?'])[0].toUpperCase();
            html += '<div class="m-card-nota-wrap">' +
                '<button class="m-card-nota__swipe-edit" data-nunota="' + escapeHtml(nunota) + '" aria-label="Editar cabeçalho">' +
                    '<i class="ph ph-pencil-simple" aria-hidden="true"></i>' +
                '</button>' +
                '<button class="m-card-nota__swipe-del" data-nunota="' + escapeHtml(nunota) + '" aria-label="Excluir">' +
                    '<i class="ph ph-trash" aria-hidden="true"></i>' +
                '</button>' +
                '<article class="m-card-nota" data-nunota="' + escapeHtml(nunota) +
                    '" data-pedido="' + escapeHtml(pedido) +
                    '" data-data="' + escapeHtml(data) +
                    '" data-parc="' + escapeHtml(parc) + '">' +
                    '<div class="m-card-nota__avatar" data-letra="' + escapeHtml(letra) + '">' + escapeHtml(letra) + '</div>' +
                    '<span class="m-card-nota__nome">' + escapeHtml(parc) + '</span>' +
                    '<span class="m-card-nota__pedido">Pedido ' + escapeHtml(pedido) + '</span>' +
                    '<span class="m-card-nota__data">' + escapeHtml(dataCurta) + '</span>' +
                    '<i class="ph ph-caret-right m-card-nota__chevron" aria-hidden="true"></i>' +
                '</article>' +
            '</div>';
        });
        lista.innerHTML = html;
        bindCardsNota();
        renderSentinela();
    }

    // Atualiza visual do botão Filtros no bottom nav quando há filtros aplicados
    function atualizarBadgeFiltros() {
        var navBtn = document.querySelector('.m-bottom-nav__item[data-nav="filtros"]');
        if (!navBtn) return;
        var ativo = temFiltroAtivo();
        navBtn.classList.toggle('has-filtros-ativos', ativo);
    }

    function temFiltroAtivo() {
        // Lê dos inputs hidden do form desktop server-rendered
        var nomes = ['start', 'end', 'nunota_ini', 'codparc', 'fabricante'];
        for (var i = 0; i < nomes.length; i++) {
            var el = getDesktopFormInput(nomes[i]);
            if (el && el.value && String(el.value).trim() !== '') return true;
        }
        return false;
    }

    function bindCardsNota() {
        document.querySelectorAll('#m_notasList .m-card-nota').forEach(function (card) {
            // Click no card abre detalhe — mas só se NÃO está em modo swipe revelado
            card.addEventListener('click', function () {
                if (card.dataset.swipeOpen === '1') {
                    // Click "fora" reseta o swipe
                    fecharSwipe(card);
                    return;
                }
                var nunota = card.dataset.nunota;
                if (!nunota) return;
                abrirDetalheNota(card);
            });
        });
        // Botão excluir revelado pelo swipe
        document.querySelectorAll('#m_notasList .m-card-nota__swipe-del').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var nun = parseInt(btn.dataset.nunota, 10);
                if (!nun) return;
                excluirNotaPorId(nun, function () {
                    // Sucesso: reload pra atualizar lista
                    setTimeout(function () { window.location.reload(); }, 600);
                });
            });
        });
        // Botão editar cabeçalho revelado pelo swipe
        document.querySelectorAll('#m_notasList .m-card-nota__swipe-edit').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var wrap = btn.closest('.m-card-nota-wrap');
                var card = wrap ? wrap.querySelector('.m-card-nota') : null;
                if (!card) return;
                // Popula ESTADO_NOTA pra popularSheetCabec usar
                ESTADO_NOTA.nunota = card.dataset.nunota;
                ESTADO_NOTA.parc = card.dataset.parc || '';
                ESTADO_NOTA.pedido = card.dataset.pedido || '';
                ESTADO_NOTA.dataNota = card.dataset.data || '';
                popularSheetCabec();
                openSheet('cabec');
            });
        });
        setupSwipeNotasDelete();
    }

    // Swipe nos cards: arrasta pra esquerda revela botões escondidos
    // Nota tem 2 botões (editar + excluir) = 88px; Item tem 1 (excluir) = 44px
    var SWIPE_REVEAL_NOTAS = 88;    // 44 (edit) + 44 (del) — cards de NOTA
    var SWIPE_REVEAL_PX = 88;       // 44 (edit) + 44 (del) — cards de ITEM (paridade nota Mai/2026 — 2026-05-29)
    var SWIPE_TRIGGER_PX = 44;      // threshold pra abrir definitivo (50% de 88)
    function setupSwipeNotasDelete() {
        document.querySelectorAll('#m_notasList .m-card-nota').forEach(function (card) {
            var startX = 0, startY = 0, currentDx = 0, tracking = false, canceled = false;
            var REVEAL = SWIPE_REVEAL_NOTAS;

            card.addEventListener('touchstart', function (e) {
                if (e.touches.length !== 1) { canceled = true; return; }
                var t = e.touches[0];
                startX = t.clientX;
                startY = t.clientY;
                currentDx = 0;
                tracking = false;
                canceled = false;
            }, { passive: true });

            card.addEventListener('touchmove', function (e) {
                if (canceled) return;
                var t = e.touches[0];
                var dx = t.clientX - startX;
                var dy = t.clientY - startY;

                if (!tracking) {
                    if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
                    if (Math.abs(dy) > Math.abs(dx)) { canceled = true; return; }
                    var jaAberto = card.dataset.swipeOpen === '1';
                    if (dx > 0 && !jaAberto) { canceled = true; return; }
                    tracking = true;
                    card.classList.add('is-swiping');
                }

                var jaAberto = card.dataset.swipeOpen === '1';
                var base = jaAberto ? -REVEAL : 0;
                var translate = base + dx;
                if (translate < -REVEAL) translate = -REVEAL + (translate + REVEAL) * 0.2;
                if (translate > 0) translate = translate * 0.2;
                card.style.transform = 'translateX(' + translate + 'px)';
                currentDx = translate;
            }, { passive: true });

            card.addEventListener('touchend', function () {
                if (canceled || !tracking) {
                    canceled = false; tracking = false;
                    return;
                }
                card.classList.remove('is-swiping');
                // Threshold: precisa passar de 50% do total revelado pra abrir
                if (currentDx < -(REVEAL / 2)) {
                    card.style.transform = 'translateX(' + (-REVEAL) + 'px)';
                    card.dataset.swipeOpen = '1';
                } else {
                    fecharSwipe(card);
                }
                tracking = false;
            }, { passive: true });

            card.addEventListener('touchcancel', function () {
                card.classList.remove('is-swiping');
                fecharSwipe(card);
                tracking = false; canceled = false;
            }, { passive: true });
        });
    }

    function fecharSwipe(card) {
        card.style.transform = '';
        card.dataset.swipeOpen = '0';
    }

    // Função reusável: excluir nota com apenas_checar → confirm → POST.
    // onSuccess opcional pra customizar comportamento após sucesso.
    function excluirNotaPorId(nun, onSuccess) {
        fetch('/sankhya/nota/delete/', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ nunota: nun, apenas_checar: true })
        })
            .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
            .then(function (resp) {
                var jcheck = resp.body;
                if (!jcheck || !jcheck.ok) {
                    if (handleValeLockedError(resp.status, jcheck)) return;
                    mostrarToast((jcheck && jcheck.error) || 'Nota bloqueada.', 'error');
                    return;
                }
                if (!confirm('Confirma excluir a nota ' + nun + ' e todos os itens?')) return;
                fetch('/sankhya/nota/delete/', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                    body: JSON.stringify({ nunota: nun })
                })
                    .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
                    .then(function (resp2) {
                        var jdel = resp2.body;
                        if (!jdel || !jdel.ok || (jdel.deleted_cab || 0) === 0) {
                            if (handleValeLockedError(resp2.status, jdel)) return;
                            mostrarToast((jdel && jdel.error) || 'Falha ao excluir nota.', 'error');
                            return;
                        }
                        mostrarToast('Nota ' + nun + ' excluída com sucesso.', 'success');
                        if (onSuccess) onSuccess();
                    })
                    .catch(function () { mostrarToast('Falha de rede', 'error'); });
            })
            .catch(function () { mostrarToast('Falha de rede', 'error'); });
    }

    /* ======================================================================
       ESTADO DA NOTA CORRENTE
       ====================================================================== */
    var ESTADO_NOTA = {
        nunota: null,
        parc: '',
        pedido: '',
        items: [],          // array de itens (do /sankhya/item/list/)
        currentIdx: -1,     // índice do item ativo na tela 3
        conferidosSet: null // Set<seq> — itens marcados como conferidos NESTA sessão
    };

    /* ======================================================================
       TELA 2 — Detalhe (lista de itens)
       ====================================================================== */
    function abrirDetalheNota(cardEl) {
        var nunota = cardEl.dataset.nunota;
        var parc = cardEl.dataset.parc || '—';
        var pedido = cardEl.dataset.pedido || '—';

        ESTADO_NOTA.nunota = nunota;
        ESTADO_NOTA.parc = parc;
        ESTADO_NOTA.pedido = pedido;
        ESTADO_NOTA.dataNota = cardEl.dataset.data || '';
        ESTADO_NOTA.items = [];
        ESTADO_NOTA.currentIdx = -1;
        ESTADO_NOTA.conferidosSet = new Set();

        var nomeEl = document.getElementById('m_detalheNome');
        var metaEl = document.getElementById('m_detalheMeta');
        var listaItens = document.getElementById('m_itensList');

        if (nomeEl) nomeEl.textContent = parc;
        if (metaEl) metaEl.textContent = 'Pedido ' + pedido + ' · carregando…';
        if (listaItens) {
            listaItens.innerHTML = '<div class="m-empty-state"><i class="ph ph-spinner"></i><p>Carregando itens…</p></div>';
        }

        // Popula hero card (paridade com Classificação Mobile)
        var heroForn = document.getElementById('m_heroFornecedor');
        var heroPedidoData = document.getElementById('m_heroPedidoData');
        if (heroForn) heroForn.textContent = parc;
        if (heroPedidoData) {
            var dataTxt = cardEl.dataset.data || '';
            heroPedidoData.textContent = (pedido ? 'Pedido ' + pedido : '—') + (dataTxt ? ' · ' + dataTxt : '');
        }

        pushScreen('detalhe');
        carregarItens(nunota, pedido);
    }

    function carregarItens(nunota, pedido) {
        var metaEl = document.getElementById('m_detalheMeta');
        fetch('/sankhya/item/list/?nunota=' + encodeURIComponent(nunota), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                var items = (j && j.ok) ? (j.items || j.results || []) : [];
                ESTADO_NOTA.items = items;
                renderItens(items, nunota);
                if (metaEl) metaEl.textContent = 'Pedido ' + pedido + ' · ' + items.length + ' itens';
            })
            .catch(function () {
                renderItens([], nunota);
                if (metaEl) metaEl.textContent = 'Pedido ' + pedido + ' · falha ao carregar';
            });
    }

    function renderItens(items, nunota) {
        var lista = document.getElementById('m_itensList');
        if (!lista) return;

        if (!items.length) {
            lista.innerHTML = '<div class="m-empty-state"><i class="ph ph-tray" aria-hidden="true"></i><p>Nenhum item nesta nota.</p></div>';
            return;
        }
        var html = '';
        items.forEach(function (it, idx) {
            // negociada = QTDNEG (total em kg quando peso > 0).
            // qtdUnidades = quantidade na unidade do volume (caixas/sacas/etc).
            var negociadaKg = parseFloat(it.qtd || 0);
            var peso = parseFloat(it.peso || 0);
            var codvol = (it.codvolparc || it.codvol || 'KG').trim().toUpperCase();
            var qtdUnidades = peso > 0 ? (negociadaKg / peso) : negociadaKg;
            var seq = it.sequencia != null ? it.sequencia : it.seq;
            var marcadoNaSessao = ESTADO_NOTA.conferidosSet && ESTADO_NOTA.conferidosSet.has(seq);

            var clss = 'm-card-item--pendente';
            var statusIconHtml = '';
            if (marcadoNaSessao || (it.qtd_conferida != null && parseFloat(it.qtd_conferida) >= negociadaKg && negociadaKg > 0)) {
                clss = 'm-card-item--ok';
                statusIconHtml = '<i class="ph ph-check-circle m-card-item__status-icon" aria-hidden="true"></i>';
            }

            // Display "Qtd": <qtdUnidades> <codvol> / <negociadaKg> KG
            // Ex: "100 CX / 2.300 KG" pra Beterraba (vol=CX, peso=23, qtd=100)
            // Ex: "100 SC / 1.000 KG" pra Laranja Pera (vol=SC, peso=10, qtd=100)
            var qtdDisplay;
            if (peso > 0 && codvol !== 'KG') {
                qtdDisplay = fmtBr(qtdUnidades) + ' ' + escapeHtml(codvol) + ' / ' + fmtBr(negociadaKg) + ' KG';
            } else {
                qtdDisplay = fmtBr(negociadaKg) + ' KG';
            }

            // Label "Peso/<codvol>" dinâmico
            var pesoLabel = 'Peso/' + escapeHtml(codvol.toLowerCase());

            html += '<div class="m-card-item-wrap">' +
                '<button class="m-card-item__swipe-edit" data-nunota="' + escapeHtml(nunota) +
                    '" data-idx="' + idx + '" data-seq="' + escapeHtml(seq) + '" aria-label="Editar item">' +
                    '<i class="ph ph-pencil-simple" aria-hidden="true"></i>' +
                '</button>' +
                '<button class="m-card-item__swipe-del" data-nunota="' + escapeHtml(nunota) +
                    '" data-seq="' + escapeHtml(seq) + '" aria-label="Excluir item">' +
                    '<i class="ph ph-trash" aria-hidden="true"></i>' +
                '</button>' +
                '<article class="m-card-item ' + clss + '" data-idx="' + idx + '" data-seq="' + escapeHtml(seq) +
                    '" data-nunota="' + escapeHtml(nunota) + '">' +
                '<div class="m-card-item__head">' +
                    '<span class="m-card-item__nome">' + escapeHtml(it.descr || 'Sem descrição') + '</span>' +
                    statusIconHtml +
                '</div>' +
                '<div class="m-card-item__body">' +
                    '<div class="m-stat"><span class="m-stat-label">' + pesoLabel + '</span>' +
                        '<span class="m-stat-value">' + (peso > 0 ? fmtBr(peso) + ' kg' : '—') + '</span></div>' +
                    '<div class="m-stat m-stat--right"><span class="m-stat-label">Qtd</span>' +
                        '<span class="m-stat-value">' + qtdDisplay + '</span></div>' +
                '</div>' +
                (it.lote ? '<div class="m-card-item__lote">Lote ' + escapeHtml(it.lote) + '</div>' : '') +
                '</article>' +
            '</div>';
        });
        lista.innerHTML = html;
        bindCardsItem();
    }

    function bindCardsItem() {
        // Click no card SÓ fecha swipe aberto — edição agora vem do swipe-edit (lápis)
        // Mai/2026 — 2026-05-29: tap-to-edit desativado por feedback do operador
        document.querySelectorAll('#m_itensList .m-card-item').forEach(function (card) {
            card.addEventListener('click', function () {
                if (card.dataset.swipeOpen === '1') {
                    fecharSwipe(card);
                }
            });
        });

        // Botão editar revelado pelo swipe (lápis azul, paridade card de NOTA)
        document.querySelectorAll('#m_itensList .m-card-item__swipe-edit').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var idx = parseInt(btn.dataset.idx, 10);
                var it = !isNaN(idx) ? ESTADO_NOTA.items[idx] : null;
                if (!it || !ESTADO_NOTA.nunota) return;
                abrirSheetItens({
                    nunota: ESTADO_NOTA.nunota,
                    parc: ESTADO_NOTA.parc || '',
                    nova: false
                });
                setTimeout(function () { abrirEditItem(it); }, 60);
            });
        });

        // Botão excluir revelado pelo swipe (lixeira vermelha)
        document.querySelectorAll('#m_itensList .m-card-item__swipe-del').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var nun = parseInt(btn.dataset.nunota, 10);
                var seq = parseInt(btn.dataset.seq, 10);
                if (!nun || !seq) return;
                excluirItemPorSeq(nun, seq);
            });
        });
        setupSwipeItensDelete();
    }

    function setupSwipeItensDelete() {
        document.querySelectorAll('#m_itensList .m-card-item').forEach(function (card) {
            var startX = 0, startY = 0, currentDx = 0, tracking = false, canceled = false;
            card.addEventListener('touchstart', function (e) {
                if (e.touches.length !== 1) { canceled = true; return; }
                var t = e.touches[0];
                startX = t.clientX; startY = t.clientY;
                currentDx = 0; tracking = false; canceled = false;
            }, { passive: true });
            card.addEventListener('touchmove', function (e) {
                if (canceled) return;
                var t = e.touches[0];
                var dx = t.clientX - startX;
                var dy = t.clientY - startY;
                if (!tracking) {
                    if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
                    if (Math.abs(dy) > Math.abs(dx)) { canceled = true; return; }
                    var jaAberto = card.dataset.swipeOpen === '1';
                    if (dx > 0 && !jaAberto) { canceled = true; return; }
                    tracking = true;
                    card.classList.add('is-swiping');
                }
                var jaAberto = card.dataset.swipeOpen === '1';
                var base = jaAberto ? -SWIPE_REVEAL_PX : 0;
                var translate = base + dx;
                if (translate < -SWIPE_REVEAL_PX) translate = -SWIPE_REVEAL_PX + (translate + SWIPE_REVEAL_PX) * 0.2;
                if (translate > 0) translate = translate * 0.2;
                card.style.transform = 'translateX(' + translate + 'px)';
                currentDx = translate;
            }, { passive: true });
            card.addEventListener('touchend', function () {
                if (canceled || !tracking) { canceled = false; tracking = false; return; }
                card.classList.remove('is-swiping');
                if (currentDx < -SWIPE_TRIGGER_PX) {
                    card.style.transform = 'translateX(' + (-SWIPE_REVEAL_PX) + 'px)';
                    card.dataset.swipeOpen = '1';
                } else {
                    fecharSwipe(card);
                }
                tracking = false;
            }, { passive: true });
            card.addEventListener('touchcancel', function () {
                card.classList.remove('is-swiping');
                fecharSwipe(card);
                tracking = false; canceled = false;
            }, { passive: true });
        });
    }

    // Exclui item da tela 2 (detalhe da nota) com apenas_checar → confirm → POST.
    // Reusa /sankhya/item/delete/ com NUNOTA+SEQUENCIA. Paridade desktop entrada.js:1699.
    function excluirItemPorSeq(nun, seq) {
        fetch('/sankhya/item/delete/', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ nunota: nun, sequencia: seq, apenas_checar: true })
        })
            .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
            .then(function (resp) {
                var j = resp.body;
                if (handleValeLockedError(resp.status, j)) return;
                if (!j || !j.ok) { mostrarToast((j && j.error) || 'Erro ao verificar item', 'error'); return; }
                if (!confirm('Excluir este item?')) return;
                fetch('/sankhya/item/delete/', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                    body: JSON.stringify({ nunota: nun, sequencia: seq })
                })
                    .then(function (r2) { return r2.json().then(function (b2) { return { status: r2.status, body: b2 }; }); })
                    .then(function (resp2) {
                        var jdel = resp2.body;
                        if (!jdel || !jdel.ok) {
                            if (handleValeLockedError(resp2.status, jdel)) return;
                            mostrarToast((jdel && jdel.error) || 'Falha ao remover', 'error');
                            return;
                        }
                        mostrarToast(jdel.message || 'Item removido ✓', 'success');
                        if (jdel.cabecalho_excluido) {
                            // Último item — cabeçalho foi excluído pelo backend; volta pra tela 1
                            popScreen();
                            setTimeout(function () { window.location.reload(); }, 600);
                        } else {
                            // Recarrega itens da nota atual
                            carregarItens(ESTADO_NOTA.nunota, ESTADO_NOTA.pedido);
                        }
                    })
                    .catch(function () { mostrarToast('Falha de rede', 'error'); });
            })
            .catch(function () { mostrarToast('Falha de rede', 'error'); });
    }

    /* ======================================================================
       TELA 3 — Conferir Item
       ====================================================================== */
    function abrirTelaItem(idx) {
        var it = ESTADO_NOTA.items[idx];
        if (!it) return;
        ESTADO_NOTA.currentIdx = idx;

        var total = ESTADO_NOTA.items.length;
        var negociada = parseFloat(it.qtd || 0);
        var conferida = parseFloat(it.qtd_conferida != null ? it.qtd_conferida : it.qtd || 0);
        var peso = parseFloat(it.peso || 0);
        var codvol = (it.codvolparc || it.codvol || 'kg').trim();
        var descr = it.descr || 'Sem descrição';
        var letra = (descr.match(/[A-Za-zÀ-ÿ]/) || ['?'])[0].toUpperCase();

        var posEl = document.getElementById('m_conf_pos');
        var avatarEl = document.querySelector('.m-item-hero__avatar');
        var nomeEl = document.getElementById('m_conf_nome');
        var qtdNegEl = document.getElementById('m_conf_qtdneg');
        var loteEl = document.getElementById('m_conf_lote');
        var confEl = document.getElementById('m_conf_qtd');
        var pesoEl = document.getElementById('m_conf_peso');
        var avariaEl = document.getElementById('m_conf_avaria');
        var avariaBlock = document.querySelector('.m-field-block--avaria');

        if (posEl) posEl.textContent = 'Item ' + (idx + 1) + ' de ' + total;
        if (avatarEl) { avatarEl.textContent = letra; avatarEl.dataset.letra = letra; }
        if (nomeEl) nomeEl.textContent = descr;
        if (qtdNegEl) qtdNegEl.textContent = 'Negociada: ' + fmtBr(negociada) + ' ' + codvol;
        if (loteEl) loteEl.textContent = it.lote ? ('Lote ' + it.lote) : 'Sem lote';

        if (confEl) confEl.value = conferida > 0 ? String(conferida).replace('.', ',') : '';
        if (pesoEl) pesoEl.value = peso > 0 ? String(peso).replace('.', ',') : '';
        if (avariaEl) avariaEl.value = '';

        // Mostra avaria apenas em não-classificáveis
        var classificavel = it.geraproducao === 'S' || it.classifica === true;
        if (avariaBlock) avariaBlock.style.display = classificavel ? 'none' : '';

        // Toggle Classifica
        var classifica = it.classifica;
        document.querySelectorAll('.m-toggle-btn[data-classifica]').forEach(function (b) {
            b.classList.toggle('is-active', (b.dataset.classifica === 'S') === !!classifica);
        });

        pushScreen('item');
        setTimeout(function () {
            if (confEl) { confEl.focus(); try { confEl.select(); } catch (e) { } }
        }, 320);
    }

    // Toggle Classifica handlers
    document.querySelectorAll('.m-toggle-btn[data-classifica]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.m-toggle-btn[data-classifica]').forEach(function (b) {
                b.classList.toggle('is-active', b === btn);
            });
        });
    });

    function getClassificaSelecionada() {
        var ativo = document.querySelector('.m-toggle-btn[data-classifica].is-active');
        return ativo ? ativo.dataset.classifica : null;
    }

    function parseBR(s) {
        if (s == null) return null;
        s = String(s).trim().replace(',', '.');
        if (!s) return null;
        var v = parseFloat(s);
        return isNaN(v) ? null : v;
    }

    function mostrarToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) {
            IAgro.showToast(msg, tipo || 'success');
        } else {
            alert(msg);
        }
    }

    // Handler de Vale lock 409 — paridade desktop entrada.js:1210.
    // Retorna true se tratou (não precisa mostrar outro erro).
    function handleValeLockedError(status, body) {
        try {
            if (status === 409 && body && body.vale && body.vale.locked) {
                var reasons = Array.isArray(body.vale.lock_reasons)
                    ? body.vale.lock_reasons.filter(Boolean) : [];
                var detail = reasons.length
                    ? reasons.join(' | ')
                    : (body.error || 'Vale bloqueado por financeiro.');
                mostrarToast('Vale bloqueado: ' + detail, 'error');
                return true;
            }
        } catch (e) { /* fall-through */ }
        return false;
    }

    function salvarItemEProximo() {
        var idx = ESTADO_NOTA.currentIdx;
        if (idx < 0 || !ESTADO_NOTA.items[idx]) return;
        var it = ESTADO_NOTA.items[idx];

        var qtdConf = parseBR(document.getElementById('m_conf_qtd').value);
        var peso = parseBR(document.getElementById('m_conf_peso').value);
        var avariaEl = document.getElementById('m_conf_avaria');
        var avariaBlock = document.querySelector('.m-field-block--avaria');
        var avariaVisivel = avariaBlock && avariaBlock.style.display !== 'none';
        var avaria = avariaVisivel ? parseBR(avariaEl.value) : null;
        var classifica = getClassificaSelecionada();

        if (qtdConf == null || qtdConf < 0) {
            mostrarToast('Informe a quantidade conferida.', 'error');
            document.getElementById('m_conf_qtd').focus();
            return;
        }

        // Payload pra /sankhya/item/save/ — UPDATE via SEQUENCIA
        var payload = {
            NUNOTA: parseInt(ESTADO_NOTA.nunota, 10),
            SEQUENCIA: parseInt(it.sequencia != null ? it.sequencia : it.seq, 10),
            CODPROD: parseInt(it.cod || it.codprod, 10),
            QTDNEG: parseFloat(it.qtd || 0),
            QTDCONFERIDA: qtdConf,
            PESO: peso || 0,
            CODVOL: (it.codvolparc || it.codvol || 'KG').toUpperCase(),
            OBSERVACAO: it.obs || ''
        };
        if (classifica) payload.GERAPRODUCAO = classifica;

        // Botão visual loading
        var btn = document.getElementById('m_btnSalvarProximo');
        if (btn) { btn.disabled = true; btn.classList.add('is-loading'); }

        var promises = [];

        // 1) Salva o item principal
        promises.push(
            (window.IAgro && IAgro.postJSON
                ? IAgro.postJSON('/sankhya/item/save/', payload)
                    .then(function (resp) {
                        if (!resp.ok || !resp.body || !resp.body.ok) {
                            throw new Error((resp.body && resp.body.error) || 'Falha ao salvar item');
                        }
                        return resp.body;
                    })
                : fetch('/sankhya/item/save/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                    body: JSON.stringify(payload)
                }).then(function (r) { return r.json(); }).then(function (j) {
                    if (!j.ok) throw new Error(j.error || 'Falha ao salvar item');
                    return j;
                })
            )
        );

        // 2) Avaria do fornecedor (só se aplicável)
        if (avaria != null && avaria >= 0 && avariaVisivel) {
            promises.push(
                fetch('/sankhya/compras/api/avaria-fornecedor/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                    body: JSON.stringify({
                        nunota: payload.NUNOTA,
                        sequencia: payload.SEQUENCIA,
                        qtd: avaria
                    })
                }).then(function (r) { return r.json(); }).catch(function () { return { ok: false }; })
            );
        }

        Promise.all(promises)
            .then(function () {
                // Atualiza estado local pra refletir a conferência
                ESTADO_NOTA.items[idx].qtd_conferida = qtdConf;
                ESTADO_NOTA.items[idx].peso = peso || ESTADO_NOTA.items[idx].peso;
                ESTADO_NOTA.conferidosSet.add(it.sequencia != null ? it.sequencia : it.seq);

                if (btn) { btn.disabled = false; btn.classList.remove('is-loading'); }

                var proximo = encontrarProximoPendente(idx);
                if (proximo >= 0) {
                    mostrarToast('Item conferido ✓', 'success');
                    abrirTelaItem(proximo);
                } else {
                    mostrarToast('Nota completa ✓', 'success');
                    renderItens(ESTADO_NOTA.items, ESTADO_NOTA.nunota);
                    popScreen();
                }
            })
            .catch(function (err) {
                if (btn) { btn.disabled = false; btn.classList.remove('is-loading'); }
                mostrarToast(err && err.message || 'Falha ao salvar.', 'error');
            });
    }

    function encontrarProximoPendente(currentIdx) {
        var items = ESTADO_NOTA.items;
        // Procura primeiro depois do atual; se não achar, do início
        for (var i = currentIdx + 1; i < items.length; i++) {
            if (!ESTADO_NOTA.conferidosSet.has(items[i].sequencia != null ? items[i].sequencia : items[i].seq)) return i;
        }
        for (var j = 0; j < currentIdx; j++) {
            if (!ESTADO_NOTA.conferidosSet.has(items[j].sequencia != null ? items[j].sequencia : items[j].seq)) return j;
        }
        return -1;
    }

    function getCsrf() {
        if (window.IAgro && IAgro.getCookie) return IAgro.getCookie('csrftoken') || '';
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    var btnSalvarProximo = document.getElementById('m_btnSalvarProximo');
    if (btnSalvarProximo) btnSalvarProximo.addEventListener('click', salvarItemEProximo);

    /* ======================================================================
       FAB — Nova nota / Novo item
       ====================================================================== */
    // FAB secundário: Atualizar (hard refresh)
    var fabAtualizar = document.getElementById('m_fabAtualizar');
    if (fabAtualizar) {
        fabAtualizar.addEventListener('click', function () {
            fabAtualizar.classList.add('is-loading');
            // Pequeno delay pro spinner ser visível antes do reload
            setTimeout(function () {
                // Force reload — passa true em browsers que suportam pra bypass cache
                try { window.location.reload(true); } catch (e) { window.location.reload(); }
            }, 150);
        });
    }

    var fabNova = document.getElementById('m_fabNova');
    if (fabNova) {
        fabNova.addEventListener('click', function () {
            // Abre bottom sheet de "Nova nota" (página "compras central" foi
            // removida — fluxo agora 100% via bottom sheets)
            var dataInput = document.getElementById('m_novaData');
            if (dataInput && !dataInput.value) {
                var d = new Date();
                dataInput.value = d.getFullYear() + '-' +
                    String(d.getMonth() + 1).padStart(2, '0') + '-' +
                    String(d.getDate()).padStart(2, '0');
            }
            openSheet('nova-nota');
        });
    }

    var fabItem = document.getElementById('m_fabItem');
    if (fabItem) {
        fabItem.addEventListener('click', function () {
            if (!ESTADO_NOTA.nunota) return;
            abrirSheetItens({
                nunota: ESTADO_NOTA.nunota,
                parc: ESTADO_NOTA.parc || '',
                nova: false
            });
        });
    }

    // FAB secundário da tela 2: Atualizar itens (recarrega lista da nota atual)
    var fabAtualizarItens = document.getElementById('m_fabAtualizarItens');
    if (fabAtualizarItens) {
        fabAtualizarItens.addEventListener('click', function () {
            if (!ESTADO_NOTA.nunota) return;
            fabAtualizarItens.classList.add('is-loading');
            carregarItens(ESTADO_NOTA.nunota, ESTADO_NOTA.pedido);
            // Spinner por 600ms pra feedback visual mesmo se fetch for rápido
            setTimeout(function () { fabAtualizarItens.classList.remove('is-loading'); }, 600);
        });
    }

    // Excluir nota inteira (tela 2 — botão lixeira no header).
    // Paridade desktop (entrada.js:399-432): apenas_checar → confirm → POST.
    var btnExcluirNota = document.getElementById('m_btnExcluirNota');
    if (btnExcluirNota) {
        btnExcluirNota.addEventListener('click', function () {
            if (!ESTADO_NOTA.nunota) return;
            var nun = parseInt(ESTADO_NOTA.nunota, 10);

            fetch('/sankhya/nota/delete/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({ nunota: nun, apenas_checar: true })
            })
                .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
                .then(function (resp) {
                    var jcheck = resp.body;
                    if (!jcheck || !jcheck.ok) {
                        if (handleValeLockedError(resp.status, jcheck)) return;
                        mostrarToast((jcheck && jcheck.error) || 'Nota bloqueada.', 'error');
                        return; // ABORT antes do confirm
                    }
                    if (!confirm('Confirma excluir a nota ' + nun + ' e todos os itens?')) return;
                    fetch('/sankhya/nota/delete/', {
                        method: 'POST', credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                        body: JSON.stringify({ nunota: nun })
                    })
                        .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
                        .then(function (resp2) {
                            var jdel = resp2.body;
                            if (!jdel || !jdel.ok || (jdel.deleted_cab || 0) === 0) {
                                if (handleValeLockedError(resp2.status, jdel)) return;
                                mostrarToast((jdel && jdel.error) || 'Falha ao excluir nota.', 'error');
                                return;
                            }
                            mostrarToast('Nota ' + nun + ' excluída com sucesso.', 'success');
                            popScreen();
                            setTimeout(function () { window.location.reload(); }, 800);
                        })
                        .catch(function () { mostrarToast('Falha de rede', 'error'); });
                })
                .catch(function () { mostrarToast('Falha de rede', 'error'); });
        });
    }

    /* ======================================================================
       BOTTOM SHEET "NOVA NOTA"
       ====================================================================== */
    var DEFAULTS_NOVA = {
        codemp: 10,
        codtipoper: 11,
        codnat: 20010100,
        codcencus: 10100
    };

    // Typeahead de fornecedor
    setupTypeahead({
        inputId: 'm_novaParceiro',
        hiddenId: 'm_novaCodparcHidden',
        dropdownId: 'm_novaParceiroDropdown',
        url: '/sankhya/parceiros/search/?limit=15',
        label: function (it) {
            var cod = it.codparc || it.cod || '';
            var nome = it.nomeparc || it.descr || '';
            return cod ? (cod + ' — ' + nome) : nome;
        },
        sub: function (it) { return it.razaosocial || ''; },
        pickHidden: function (it) { return String(it.codparc || it.cod || ''); },
        pickVisible: function (it) {
            var cod = it.codparc || it.cod || '';
            var nome = it.nomeparc || it.descr || '';
            return cod ? (cod + ' — ' + nome) : nome;
        }
    });

    var btnNovaSalvar = document.getElementById('m_btnNovaSalvar');
    if (btnNovaSalvar) {
        btnNovaSalvar.addEventListener('click', function () {
            var codparc = $m('m_novaCodparcHidden').value.trim();
            var data = $m('m_novaData').value;
            var obs = $m('m_novaObs').value.trim();

            if (!codparc) {
                mostrarToast('Selecione o fornecedor.', 'error');
                $m('m_novaParceiro').focus();
                return;
            }
            if (!data) {
                mostrarToast('Informe a data da negociação.', 'error');
                $m('m_novaData').focus();
                return;
            }

            // Backend aceita data em ISO (YYYY-MM-DD) — _data_br_para_iso é tolerante
            var payload = {
                codemp: DEFAULTS_NOVA.codemp,
                codparc: parseInt(codparc, 10),
                codtipoper: DEFAULTS_NOVA.codtipoper,
                codnat: DEFAULTS_NOVA.codnat,
                codcencus: DEFAULTS_NOVA.codcencus,
                dtneg: data,
                dtmov: data,
                dtentsai: data,
                obs: obs || null
            };

            btnNovaSalvar.disabled = true;
            btnNovaSalvar.classList.add('is-loading');

            fetch('/sankhya/compras/central/salvar/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrf(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    btnNovaSalvar.disabled = false;
                    btnNovaSalvar.classList.remove('is-loading');
                    if (!j || !j.ok) {
                        throw new Error((j && j.error) || 'Falha ao criar nota');
                    }
                    var nunota = j.nunota || (j.plano && j.plano.nunota) || null;
                    if (!nunota) {
                        mostrarToast('Nota criada, mas sem NUNOTA — recarregando…', 'success');
                        setTimeout(function () { window.location.reload(); }, 800);
                        return;
                    }
                    mostrarToast('Nota ' + nunota + ' criada — adicione os itens', 'success');
                    closeSheet('nova-nota');
                    // Limpa campos do cabeçalho
                    ['m_novaParceiro', 'm_novaCodparcHidden', 'm_novaObs'].forEach(function (id) {
                        var el = $m(id); if (el) el.value = '';
                    });
                    // Abre o sheet de itens com a nota recém-criada
                    var parc = $m('m_novaParceiro').value || '';
                    abrirSheetItens({ nunota: nunota, parc: parc, nova: true });
                })
                .catch(function (err) {
                    btnNovaSalvar.disabled = false;
                    btnNovaSalvar.classList.remove('is-loading');
                    mostrarToast(err && err.message || 'Falha ao criar nota.', 'error');
                });
        });
    }

    /* ======================================================================
       BOTTOM SHEET "ITENS DA NOTA" — espelha #cabItemsCard desktop
       Fluxo: após criar nota, abre esse sheet pra inserir itens 1 a 1.
       ====================================================================== */
    var ESTADO_ITENS = {
        nunota: null,
        items: [],
        editandoSeq: null,
        // Mai/2026 — Paridade com desktop: rastreia cabeçalho recém-criado pra
        // excluir automático se operador fechar o sheet sem adicionar nenhum
        // item (evita cabeçalhos órfãos no banco). Equivale a cabRecemCriado
        // do entrada.js.
        cabRecemCriado: null,
    };

    function abrirSheetItens(meta) {
        ESTADO_ITENS.nunota = meta.nunota;
        ESTADO_ITENS.items = [];
        ESTADO_ITENS.editandoSeq = null;
        ESTADO_ITENS.cabRecemCriado = meta.nova ? meta.nunota : null;
        $m('m_itens_nunota').value = meta.nunota;
        $m('m_item_seq_edit').value = '';
        $m('m_itensSheetTitulo').textContent = 'Itens — Nota ' + meta.nunota;
        $m('m_itensSheetSub').textContent = meta.parc || (meta.nova ? 'Nota recém-criada' : '');
        limparFormItem();
        carregarItensInseridos();
        openSheet('itens-nota');
        setTimeout(function () { try { $m('m_itemProd').focus(); } catch (e) { } }, 320);
    }

    // Auto-cura ÓRFÃ — verifica antes de fechar o sheet de itens.
    // Se foi um cabeçalho recém-criado E nenhum item foi adicionado, exclui
    // o cabeçalho automaticamente (igual interceptarFechamentoCabecalho do
    // desktop em entrada.js:1072).
    function fecharSheetItens(opts) {
        opts = opts || {};
        var foiOrfa = false;

        function depoisDeFechar() {
            closeSheet('itens-nota');
            var nunSheet = ESTADO_ITENS.nunota;
            ESTADO_ITENS.cabRecemCriado = null;
            if (foiOrfa) {
                // Cabeçalho órfão excluído → não dá pra voltar pra tela 2 dessa nota;
                // recarrega tela 1 (lista de notas)
                setTimeout(function () { window.location.reload(); }, 700);
                return;
            }
            // Cenário comum: operador entrou na tela 2 e clicou + Item.
            // Volta pra tela 2 e recarrega itens. Sem reload.
            if (opts.reloadAposFechar && ESTADO_NOTA.nunota && String(ESTADO_NOTA.nunota) === String(nunSheet)) {
                carregarItens(ESTADO_NOTA.nunota, ESTADO_NOTA.pedido);
            } else if (opts.reloadAposFechar) {
                // Cenário "Nova nota" sem tela 2 carregada → reload pra atualizar lista
                setTimeout(function () { window.location.reload(); }, 700);
            }
        }

        var temItens = ESTADO_ITENS.items.length > 0;
        if (ESTADO_ITENS.cabRecemCriado && !temItens) {
            // Cabeçalho órfão — exclui antes de fechar
            var nun = parseInt(ESTADO_ITENS.cabRecemCriado, 10);
            foiOrfa = true;
            fetch('/sankhya/nota/delete/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({ nunota: nun })
            })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    if (j && j.ok) {
                        mostrarToast('Cabeçalho vazio cancelado.', 'info');
                    }
                })
                .catch(function () { /* ignora — vai recarregar mesmo */ })
                .finally(depoisDeFechar);
        } else {
            depoisDeFechar();
        }
    }

    function limparFormItem() {
        ['m_itemProd', 'm_itemProdHidden', 'm_itemQtd', 'm_itemPeso', 'm_itemTotal'].forEach(function (id) {
            var el = $m(id); if (el) el.value = '';
        });
        var vol = $m('m_itemVol'); if (vol) vol.value = 'CX';
        // Sai do modo edit: restaura Produto e toggles Classifica habilitados
        var prodEl = $m('m_itemProd');
        if (prodEl) {
            prodEl.disabled = false;
            prodEl.removeAttribute('title');
        }
        document.querySelectorAll('.m-toggle-btn[data-classifica-item]').forEach(function (b) {
            b.classList.remove('is-active');
            b.disabled = false;
            b.removeAttribute('title');
            b.style.opacity = '';
            b.style.cursor = '';
        });
        ESTADO_ITENS.editandoSeq = null;
        $m('m_item_seq_edit').value = '';
        var lbl = $m('m_itemAddBtnLabel');
        if (lbl) lbl.textContent = 'Adicionar';
    }

    function recalcTotalItem() {
        // Paridade desktop entrada.js:2171 — SEMPRE qtd × peso quando ambos > 0
        var qtd = parseBR($m('m_itemQtd').value) || 0;
        var peso = parseBR($m('m_itemPeso').value) || 0;
        var total = (qtd > 0 && peso > 0) ? (qtd * peso) : qtd;
        $m('m_itemTotal').value = total > 0 ? total.toLocaleString('pt-BR', { maximumFractionDigits: 3 }) : '';
    }
    ['m_itemQtd', 'm_itemPeso', 'm_itemVol'].forEach(function (id) {
        var el = $m(id);
        if (!el) return;
        el.addEventListener('input', recalcTotalItem);
        el.addEventListener('change', recalcTotalItem);
        el.addEventListener('blur', recalcTotalItem);
        el.addEventListener('keyup', recalcTotalItem);
    });

    // Vol != CX força peso=1 (paridade desktop checkVolumeClassification em entrada.js:2123)
    function aplicarRegraVolume() {
        var volEl = $m('m_itemVol');
        var pesoEl = $m('m_itemPeso');
        if (!volEl || !pesoEl) return;
        var vol = (volEl.value || '').trim().toUpperCase();
        if (vol && vol !== 'CX') {
            var peso = parseBR(pesoEl.value) || 0;
            if (!peso) {
                pesoEl.value = '1';
                recalcTotalItem();
            }
        }
    }
    var volElGlobal = $m('m_itemVol');
    if (volElGlobal) {
        volElGlobal.addEventListener('input', aplicarRegraVolume);
        volElGlobal.addEventListener('change', aplicarRegraVolume);
        // Blur no Vol vazio restaura "CX" (paridade desktop entrada.js:2158)
        volElGlobal.addEventListener('blur', function () {
            if (!this.value.trim()) this.value = 'CX';
            aplicarRegraVolume();
        });
    }

    // Typeahead Produto (Padrão B — CODPROD numérico, mostra "cod — descr")
    // Paridade desktop entrada.js:2065 — limit=400 + allow_in_natura=1
    setupTypeahead({
        inputId: 'm_itemProd',
        hiddenId: 'm_itemProdHidden',
        dropdownId: 'm_itemProdDropdown',
        url: '/sankhya/produtos/search/?limit=400&allow_in_natura=1',
        label: function (it) {
            var cod = it.cod || it.codprod || '';
            var descr = it.descr || it.descrprod || '';
            return cod ? (cod + ' — ' + descr) : descr;
        },
        pickHidden: function (it) { return String(it.cod || it.codprod || ''); },
        pickVisible: function (it) {
            var cod = it.cod || it.codprod || '';
            var descr = it.descr || it.descrprod || '';
            return cod ? (cod + ' — ' + descr) : descr;
        }
    });

    // Toggle Classifica
    document.querySelectorAll('.m-toggle-btn[data-classifica-item]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.m-toggle-btn[data-classifica-item]').forEach(function (b) {
                b.classList.toggle('is-active', b === btn);
            });
        });
    });

    function getClassificaItem() {
        var ativo = document.querySelector('.m-toggle-btn[data-classifica-item].is-active');
        return ativo ? ativo.dataset.classificaItem : null;
    }

    function carregarItensInseridos() {
        var nun = ESTADO_ITENS.nunota;
        if (!nun) return;
        fetch('/sankhya/item/list/?nunota=' + encodeURIComponent(nun), {
            credentials: 'same-origin', headers: { 'Accept': 'application/json' }
        })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                ESTADO_ITENS.items = (j && j.ok) ? (j.items || []) : [];
                renderItensInseridos();
            })
            .catch(function () { renderItensInseridos(); });
    }

    function renderItensInseridos() {
        var lista = $m('m_itensInseridosList');
        $m('m_itensCount').textContent = String(ESTADO_ITENS.items.length);
        if (!ESTADO_ITENS.items.length) {
            lista.innerHTML = '<div class="m-empty-state"><i class="ph ph-tray"></i><p>Nenhum item ainda.</p></div>';
            return;
        }
        // tap no card popula form pra editar — paridade com duplo-clique do desktop
        var html = ESTADO_ITENS.items.map(function (it) {
            var qtd = parseFloat(it.qtd || 0);
            var peso = parseFloat(it.peso || 0);
            var totalKg = qtd; // qtd já é o total kg (QTDNEG)
            var codvol = (it.codvolparc || it.codvol || '').trim();
            var seq = it.sequencia != null ? it.sequencia : it.seq;

            // Avaria do fornecedor — input editável SÓ em não-classificáveis
            // (paridade desktop entrada.js:1840). Auto-save no blur.
            var gpUpper = '';
            if (it.geraproducao != null) gpUpper = String(it.geraproducao).toUpperCase();
            else if (typeof it.classifica !== 'undefined') gpUpper = it.classifica ? 'S' : 'N';
            var classificavel = gpUpper === 'S';

            var avariaHtml = classificavel
                ? '<span class="m-iteminserido__avaria-disabled" title="Avaria gerenciada na Classificação">—</span>'
                : '<input type="number" step="0.001" min="0" ' +
                    'class="m-iteminserido__avaria" ' +
                    'data-seq="' + escapeHtml(seq) + '" ' +
                    'value="0" placeholder="Avaria" ' +
                    'title="Avaria do fornecedor (kg). Salva automaticamente ao sair do campo." />';

            return '<div class="m-iteminserido" data-seq="' + escapeHtml(seq) + '">' +
                '<div class="m-iteminserido__info">' +
                    '<div class="m-iteminserido__nome">' + escapeHtml(it.descr || '') + '</div>' +
                    '<div class="m-iteminserido__meta">' +
                        (it.lote ? 'Lote ' + escapeHtml(it.lote) + ' · ' : '') +
                        (peso > 0 ? fmtBr(peso) + ' kg/cx · ' : '') +
                        (classificavel ? 'Classifica' : 'Não classifica') +
                    '</div>' +
                    '<div class="m-iteminserido__avaria-wrap">' +
                        '<span class="m-iteminserido__avaria-label">Avaria forn.:</span>' +
                        avariaHtml +
                    '</div>' +
                '</div>' +
                '<div class="m-iteminserido__qtd">' +
                    fmtBr(totalKg) + ' kg' +
                    (peso > 0 && codvol && codvol.toUpperCase() !== 'KG'
                        ? '<small>' + fmtBr(qtd / peso) + ' ' + escapeHtml(codvol) + '</small>'
                        : '') +
                '</div>' +
                '<button type="button" class="m-iteminserido__del" data-seq="' + escapeHtml(seq) + '" aria-label="Remover">' +
                    '<i class="ph ph-trash"></i>' +
                '</button>' +
            '</div>';
        }).join('');
        lista.innerHTML = html;
        bindItemDeletes();
        bindItemEdits();
        bindAvariaInputs();
        carregarAvariasInline();
    }

    function bindAvariaInputs() {
        document.querySelectorAll('#m_itensInseridosList .m-iteminserido__avaria').forEach(function (inp) {
            // Não dispara editar item ao clicar no campo
            inp.addEventListener('click', function (e) { e.stopPropagation(); });
            inp.addEventListener('focus', function (e) { e.stopPropagation(); });
            inp.addEventListener('blur', function () { salvarAvariaInline(inp); });
            inp.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); inp.blur(); }
            });
        });
    }

    function carregarAvariasInline() {
        // Busca AD_QTDAVARIA da nota e popula os inputs (paridade desktop entrada.js:1990)
        var nun = parseInt(ESTADO_ITENS.nunota, 10);
        if (!nun) return;
        fetch('/sankhya/compras/api/avarias-fornecedor/?nunota=' + encodeURIComponent(nun), {
            credentials: 'same-origin', headers: { 'Accept': 'application/json' }
        })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                if (!j || !j.ok || !j.avarias) return;
                var inputs = document.querySelectorAll('#m_itensInseridosList .m-iteminserido__avaria');
                inputs.forEach(function (inp) {
                    var seq = inp.dataset.seq;
                    if (j.avarias[seq] != null) inp.value = j.avarias[seq];
                });
            })
            .catch(function () { /* silencioso — não bloqueia UX */ });
    }

    function salvarAvariaInline(inp) {
        var seq = parseInt(inp.dataset.seq, 10);
        var nun = parseInt(ESTADO_ITENS.nunota, 10);
        var qtd = parseBR(inp.value);
        if (!seq || !nun || qtd == null || qtd < 0) return;

        inp.classList.remove('m-iteminserido__avaria--saved', 'm-iteminserido__avaria--error');
        inp.classList.add('m-iteminserido__avaria--saving');

        fetch('/sankhya/compras/api/avaria-fornecedor/', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ nunota: nun, sequencia: seq, qtd: qtd })
        })
            .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
            .then(function (resp) {
                inp.classList.remove('m-iteminserido__avaria--saving');
                if (!resp.body || !resp.body.ok) {
                    if (handleValeLockedError(resp.status, resp.body)) {
                        inp.classList.add('m-iteminserido__avaria--error');
                        return;
                    }
                    inp.classList.add('m-iteminserido__avaria--error');
                    mostrarToast((resp.body && resp.body.error) || 'Falha ao salvar avaria', 'error');
                    return;
                }
                inp.classList.add('m-iteminserido__avaria--saved');
                setTimeout(function () { inp.classList.remove('m-iteminserido__avaria--saved'); }, 1500);
            })
            .catch(function () {
                inp.classList.remove('m-iteminserido__avaria--saving');
                inp.classList.add('m-iteminserido__avaria--error');
            });
    }

    function bindItemEdits() {
        document.querySelectorAll('#m_itensInseridosList .m-iteminserido').forEach(function (card) {
            card.addEventListener('click', function (e) {
                // Se o click foi na lixeira, não abre edição (lixeira tem handler próprio)
                if (e.target.closest('.m-iteminserido__del')) return;
                var seq = card.dataset.seq;
                var item = ESTADO_ITENS.items.find(function (it) {
                    return String(it.sequencia != null ? it.sequencia : it.seq) === String(seq);
                });
                if (item) abrirEditItem(item);
            });
        });
    }

    function abrirEditItem(item) {
        var seq = item.sequencia != null ? item.sequencia : item.seq;
        ESTADO_ITENS.editandoSeq = seq;
        $m('m_item_seq_edit').value = String(seq);

        // Produto (visível formato "cod — descr"; hidden recebe CODPROD)
        var cod = item.cod || item.codprod || '';
        var descr = item.descr || '';
        $m('m_itemProdHidden').value = String(cod);
        $m('m_itemProd').value = cod ? (cod + ' — ' + descr) : descr;

        // Paridade desktop entrada.js:1625-1634 — em modo edit, Produto e
        // Classifica não podem ser alterados (preserva rastreabilidade)
        var prodEl = $m('m_itemProd');
        if (prodEl) {
            prodEl.disabled = true;
            prodEl.title = 'Produto não pode ser alterado na edição.';
        }
        document.querySelectorAll('.m-toggle-btn[data-classifica-item]').forEach(function (b) {
            b.disabled = true;
            b.title = 'Classificação não pode ser alterada na edição.';
            b.style.opacity = '0.5';
            b.style.cursor = 'not-allowed';
        });

        // Vol e Peso — fallback 'KG' (paridade desktop entrada.js:1899)
        var vol = ((item.codvolparc || item.codvol || 'KG') + '').toUpperCase();
        $m('m_itemVol').value = vol;
        // Type=number rejeita string com vírgula → usa ponto e número JS
        var pesoNum = parseFloat(item.peso);
        if (isNaN(pesoNum)) pesoNum = 0;
        $m('m_itemPeso').value = pesoNum > 0 ? String(pesoNum) : '';

        // Qtd: backend guarda QTDNEG = qtd × peso (paridade desktop — sempre
        // multiplica quando peso > 0, inclusive em KG). Inverte pra exibir no
        // input "Qtd" em unidades.
        var qtdNeg = parseFloat(item.qtd);
        if (isNaN(qtdNeg)) qtdNeg = 0;
        var qtdExibida = pesoNum > 0 ? (qtdNeg / pesoNum) : qtdNeg;
        $m('m_itemQtd').value = qtdExibida > 0 ? String(qtdExibida) : '';
        recalcTotalItem();

        // Classifica toggle
        var gp = item.geraproducao != null
            ? String(item.geraproducao).toUpperCase()
            : (item.classifica ? 'S' : 'N');
        document.querySelectorAll('.m-toggle-btn[data-classifica-item]').forEach(function (b) {
            b.classList.toggle('is-active', b.dataset.classificaItem === gp);
        });

        // Muda label do botão Adicionar → Salvar
        var lbl = $m('m_itemAddBtnLabel');
        if (lbl) lbl.textContent = 'Salvar';

        // Scroll pro topo do sheet pro form ficar visível
        var sheetBody = document.querySelector('.m-sheet[data-sheet="itens-nota"] .m-sheet__body');
        if (sheetBody) sheetBody.scrollTop = 0;

        try { $m('m_itemQtd').focus(); $m('m_itemQtd').select(); } catch (e) { }
    }

    function bindItemDeletes() {
        document.querySelectorAll('#m_itensInseridosList .m-iteminserido__del').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var seq = btn.dataset.seq;
                if (!seq) return;
                var nun = parseInt(ESTADO_ITENS.nunota, 10);
                var seqInt = parseInt(seq, 10);

                // Paridade desktop (entrada.js:1699-1714):
                // 1) apenas_checar primeiro → trava do banco antes do confirm
                // 2) se TRAVA dispara → mostra erro e ABORTA (não exibe confirm)
                // 3) se passou → confirm
                // 4) se confirm OK → POST sem flag pra excluir real
                // 5) se cabecalho_excluido=true → fecha sheet + reload
                fetch('/sankhya/item/delete/', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                    body: JSON.stringify({ nunota: nun, sequencias: [seqInt], apenas_checar: true })
                })
                    .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
                    .then(function (resp) {
                        var jcheck = resp.body;
                        if (!jcheck || !jcheck.ok) {
                            if (handleValeLockedError(resp.status, jcheck)) return;
                            mostrarToast((jcheck && jcheck.error) || 'Item bloqueado.', 'error');
                            return; // ABORT antes do confirm
                        }
                        if (!confirm('Excluir o item sequência ' + seq + '?')) return;
                        fetch('/sankhya/item/delete/', {
                            method: 'POST', credentials: 'same-origin',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                            body: JSON.stringify({ nunota: nun, sequencias: [seqInt] })
                        })
                            .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
                            .then(function (resp2) {
                                var jdel = resp2.body;
                                if (!jdel || !jdel.ok) {
                                    if (handleValeLockedError(resp2.status, jdel)) return;
                                    mostrarToast((jdel && jdel.error) || 'Falha ao remover', 'error');
                                    return;
                                }
                                mostrarToast(jdel.message || 'Item removido ✓', 'success');
                                if (jdel.cabecalho_excluido) {
                                    // Último item — cabeçalho também foi excluído pelo backend
                                    closeSheet('itens-nota');
                                    ESTADO_ITENS.cabRecemCriado = null;
                                    setTimeout(function () { window.location.reload(); }, 700);
                                } else {
                                    carregarItensInseridos();
                                }
                            })
                            .catch(function () { mostrarToast('Falha de rede', 'error'); });
                    })
                    .catch(function () { mostrarToast('Falha de rede', 'error'); });
            });
        });
    }

    // Detecção de duplicação (CODPROD+CODVOL) — paridade desktop entrada.js:1756
    function hasDuplicateItemInList(codprod, codvol) {
        if (!codprod) return false;
        var cprod = String(codprod).trim();
        var cvol = String(codvol || '').trim().toUpperCase();
        for (var i = 0; i < ESTADO_ITENS.items.length; i++) {
            var it = ESTADO_ITENS.items[i];
            var seq = it.sequencia != null ? it.sequencia : it.seq;
            // Em modo edit, ignora a própria linha
            if (ESTADO_ITENS.editandoSeq && String(seq) === String(ESTADO_ITENS.editandoSeq)) continue;
            var rc = String(it.cod || it.codprod || '').trim();
            if (!rc || rc !== cprod) continue;
            if (cvol) {
                var rv = String(it.codvol || it.codvolparc || '').trim().toUpperCase();
                if (rv === cvol) return true;
            } else {
                return true;
            }
        }
        return false;
    }

    // Toggle row do sheet de Itens (escopa pra não pegar o da tela 3 Conferir item,
    // que compartilha a classe .m-toggle-row no DOM)
    function getToggleRowItens() {
        var btn = document.querySelector('.m-toggle-btn[data-classifica-item]');
        return btn ? btn.closest('.m-toggle-row') : null;
    }

    function limparInvalidItem() {
        ['m_itemProd', 'm_itemQtd', 'm_itemPeso', 'm_itemVol'].forEach(function (id) {
            var el = $m(id); if (el) el.classList.remove('is-invalid');
        });
        var toggleRow = getToggleRowItens();
        if (toggleRow) toggleRow.classList.remove('is-invalid');
    }
    // Limpa marca de invalid quando o operador edita o campo
    ['m_itemProd', 'm_itemQtd', 'm_itemPeso', 'm_itemVol'].forEach(function (id) {
        var el = $m(id);
        if (el) el.addEventListener('input', function () { el.classList.remove('is-invalid'); });
    });
    document.querySelectorAll('.m-toggle-btn[data-classifica-item]').forEach(function (b) {
        b.addEventListener('click', function () {
            var row = b.closest('.m-toggle-row');
            if (row) row.classList.remove('is-invalid');
        });
    });

    function salvarItem() {
        limparInvalidItem();

        var nun = parseInt(ESTADO_ITENS.nunota, 10);
        if (!nun) { mostrarToast('Nota não definida', 'error'); return; }

        var codprodRaw = $m('m_itemProdHidden').value.trim();
        if (!codprodRaw) {
            var txt = $m('m_itemProd').value.trim();
            var m = txt.match(/^(\d+)/);
            codprodRaw = m ? m[1] : '';
        }
        var codprod = parseInt(codprodRaw, 10);
        var qtd = parseBR($m('m_itemQtd').value);
        var peso = parseBR($m('m_itemPeso').value);
        var vol = ($m('m_itemVol').value || '').trim().toUpperCase();
        var classifica = getClassificaItem();

        // Marca todos os campos inválidos antes de abortar (paridade desktop entrada.js:2229)
        var invalidos = [];
        if (!codprod || isNaN(codprod)) invalidos.push($m('m_itemProd'));
        if (!qtd || qtd <= 0) invalidos.push($m('m_itemQtd'));
        if (!peso || peso <= 0) invalidos.push($m('m_itemPeso'));
        if (!vol) invalidos.push($m('m_itemVol'));
        var classificaInvalid = !classifica;

        if (invalidos.length || classificaInvalid) {
            invalidos.forEach(function (el) { if (el) el.classList.add('is-invalid'); });
            if (classificaInvalid) {
                var row = getToggleRowItens();
                if (row) row.classList.add('is-invalid');
            }
            mostrarToast('Preencha todos os campos obrigatórios (incluindo a Classificação).', 'error');
            try { (invalidos[0] || $m('m_itemProd')).focus(); } catch (e) { }
            return;
        }

        // Detecção de duplicação por (CODPROD + CODVOL) — paridade desktop
        // entrada.js:1756. Em modo edit ignora a própria linha.
        if (!ESTADO_ITENS.editandoSeq && hasDuplicateItemInList(codprod, vol)) {
            if (!confirm('Já existe um item com esse Produto e Volume na nota. Adicionar mesmo assim?')) return;
        }

        // Paridade desktop entrada.js:2269 — SEMPRE qtd × peso quando ambos > 0
        var totalKg = (qtd > 0 && peso > 0) ? (qtd * peso) : qtd;
        var payload = {
            NUNOTA: nun,
            CODPROD: codprod,
            QTDNEG: totalKg,
            QTDCONFERIDA: qtd,
            VLRUNIT: 0,
            CODVOL: vol,
            PESO: peso,
            GERAPRODUCAO: classifica,
            CODLOCALORIG: 101
        };

        var seqEdit = ESTADO_ITENS.editandoSeq;
        if (seqEdit) payload.SEQUENCIA = parseInt(seqEdit, 10);

        var btn = $m('m_itemAddBtn');
        if (btn) { btn.disabled = true; btn.classList.add('is-loading'); }

        fetch('/sankhya/item/save/', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify(payload)
        })
            .then(function (r) {
                return r.json().then(function (body) {
                    return { status: r.status, body: body };
                });
            })
            .then(function (resp) {
                if (btn) { btn.disabled = false; btn.classList.remove('is-loading'); }
                var j = resp.body;
                if (!j || !j.ok) {
                    if (handleValeLockedError(resp.status, j)) return;
                    throw new Error((j && j.error) || 'Falha ao salvar item');
                }
                mostrarToast(seqEdit ? 'Item atualizado ✓' : 'Item adicionado ✓', 'success');
                // Item inserido → não é mais cabeçalho órfão (paridade desktop)
                ESTADO_ITENS.cabRecemCriado = null;
                limparFormItem();
                carregarItensInseridos();
                try { $m('m_itemProd').focus(); } catch (e) { }
            })
            .catch(function (err) {
                if (btn) { btn.disabled = false; btn.classList.remove('is-loading'); }
                mostrarToast(err && err.message || 'Falha ao salvar item.', 'error');
            });
    }

    var btnItemAdd = $m('m_itemAddBtn');
    if (btnItemAdd) btnItemAdd.addEventListener('click', salvarItem);

    var btnItemClear = $m('m_itemClearForm');
    if (btnItemClear) btnItemClear.addEventListener('click', limparFormItem);

    // Enter nos campos numéricos + Produto dispara Adicionar (paridade desktop entrada.js:2179)
    ['m_itemQtd', 'm_itemPeso', 'm_itemProd'].forEach(function (id) {
        var el = $m(id);
        if (!el) return;
        el.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                salvarItem();
            }
        });
    });

    var btnItensFechar = $m('m_itensSheetFechar');
    if (btnItensFechar) {
        btnItensFechar.addEventListener('click', function () {
            fecharSheetItens({ reloadAposFechar: true });
        });
    }

    // Backdrop e X do sheet de itens — interceptam pra checar órfã
    mob.querySelectorAll('[data-close-itens-sheet]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            fecharSheetItens();
        });
    });

    /* ======================================================================
       SEARCH (filtragem client-side sobre cards já hidratados)
       ====================================================================== */
    var searchInput = document.getElementById('m_search');
    if (searchInput) {
        var t;
        searchInput.addEventListener('input', function () {
            clearTimeout(t);
            var termo = searchInput.value.trim();
            t = setTimeout(function () { buscarServerSide(termo); }, 250);
        });
    }

    // Mai/2026 (2026-05-27) — filtrarCards/normalizar removidos: busca agora
    // é server-side via buscarServerSide(), retorna só matches em 1 fetch
    // (ágil, sem progressivo). Trava de 90 dias no server-side limita o
    // universo por default — operador busca período maior abrindo filtro.

    /* ======================================================================
       FILTROS — mesmos da versão web (data ini/fim + pedido + produto + parceiro)
       ----------------------------------------------------------------------
       Estratégia: bottom sheet com os 4 filtros; ao Aplicar, copia valores
       pro form #filtersForm do .entrada-desktop e faz submit (recarrega
       a página com filtros aplicados server-side). Reusa o mesmo backend
       que o desktop — zero duplicação de lógica de filtragem.
       ====================================================================== */

    var DESKTOP_FORM_SEL = '.entrada-desktop #filtersForm';

    function $m(id) { return document.getElementById(id); }
    function getDesktopFormInput(name) {
        var f = document.querySelector(DESKTOP_FORM_SEL);
        if (!f) return null;
        return f.querySelector('input[name="' + name + '"]');
    }

    function syncFiltrosDesktopParaMobile() {
        // Lê valores que vieram renderizados no form desktop (server-side com filtros)
        var elStart = getDesktopFormInput('start');
        var elEnd = getDesktopFormInput('end');
        var elNunota = getDesktopFormInput('nunota_ini');
        var elFabHidden = getDesktopFormInput('fabricante');
        var elCodparcHidden = getDesktopFormInput('codparc');
        var elFabVisible = document.querySelector('.entrada-desktop #prodSearch');
        var elParcVisible = document.querySelector('.entrada-desktop #parcSearch');

        if (elStart && $m('m_filtroStart')) $m('m_filtroStart').value = elStart.value || '';
        if (elEnd && $m('m_filtroEnd')) $m('m_filtroEnd').value = elEnd.value || '';
        if (elNunota && $m('m_filtroPedido')) $m('m_filtroPedido').value = elNunota.value || '';
        if (elFabHidden && $m('m_filtroFabricanteHidden')) $m('m_filtroFabricanteHidden').value = elFabHidden.value || '';
        if (elFabVisible && $m('m_filtroProduto')) $m('m_filtroProduto').value = elFabVisible.value || '';
        if (elCodparcHidden && $m('m_filtroCodparcHidden')) $m('m_filtroCodparcHidden').value = elCodparcHidden.value || '';
        if (elParcVisible && $m('m_filtroParceiro')) $m('m_filtroParceiro').value = elParcVisible.value || '';
    }

    function aplicarFiltrosMobile() {
        var f = document.querySelector(DESKTOP_FORM_SEL);
        if (!f) return;
        var copy = function (mobId, formName) {
            var src = $m(mobId);
            var tgt = getDesktopFormInput(formName);
            if (src && tgt) tgt.value = src.value || '';
        };
        copy('m_filtroStart', 'start');
        copy('m_filtroEnd', 'end');
        copy('m_filtroPedido', 'nunota_ini');
        copy('m_filtroFabricanteHidden', 'fabricante');
        copy('m_filtroCodparcHidden', 'codparc');
        // Submete pelo método GET do form — Django recarrega página com filtros
        f.submit();
    }

    function limparFiltrosMobile() {
        // Zera campos do mobile
        ['m_filtroStart', 'm_filtroEnd', 'm_filtroPedido',
         'm_filtroFabricanteHidden', 'm_filtroProduto',
         'm_filtroCodparcHidden', 'm_filtroParceiro'].forEach(function (id) {
            var el = $m(id);
            if (el) el.value = '';
        });
        // Zera form desktop e submete (volta pra listagem sem filtros)
        var f = document.querySelector(DESKTOP_FORM_SEL);
        if (!f) return;
        ['start', 'end', 'nunota_ini', 'fabricante', 'codparc', 'days'].forEach(function (n) {
            var el = getDesktopFormInput(n);
            if (el) el.value = '';
        });
        f.submit();
    }

    // Botões << / >> — shift data ini E fim juntos
    function shiftFiltroDia(delta) {
        var inputIni = $m('m_filtroStart');
        if (!inputIni) return;
        var d = inputIni.value ? new Date(inputIni.value + 'T12:00:00') : new Date();
        if (isNaN(d.getTime())) d = new Date();
        d.setDate(d.getDate() + delta);
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dd = String(d.getDate()).padStart(2, '0');
        var iso = y + '-' + m + '-' + dd;
        inputIni.value = iso;
        var inputFim = $m('m_filtroEnd');
        if (inputFim) inputFim.value = iso;
    }

    function setupFiltrosBotoes() {
        var btnPrev = $m('m_btnPrevDay');
        var btnNext = $m('m_btnNextDay');
        var btnApl = $m('m_btnAplicarFiltros');
        var btnLim = $m('m_btnLimparFiltros');
        if (btnPrev) btnPrev.addEventListener('click', function () { shiftFiltroDia(-1); });
        if (btnNext) btnNext.addEventListener('click', function () { shiftFiltroDia(1); });
        if (btnApl) btnApl.addEventListener('click', function () { aplicarFiltrosMobile(); });
        if (btnLim) btnLim.addEventListener('click', function () { limparFiltrosMobile(); });

        // dataIni mudou → replica em dataFim SEMPRE (paridade convenção
        // "Período data inicial → data final" — operador olha 1 dia só por
        // default; quem quer range muda dataFim depois). No iPhone, `change`
        // em type=date só dispara quando o picker fecha; `input` cobre o caso
        // do usuário arrastando o spinner. Sem o "sempre" o iPhone não
        // replicava quando dataFim já tinha valor anterior.
        var inputIni = $m('m_filtroStart');
        var inputFim = $m('m_filtroEnd');
        if (inputIni && inputFim) {
            var replicar = function (e) {
                var v = (e && e.target ? e.target.value : inputIni.value) || '';
                if (v) inputFim.value = v;
            };
            inputIni.addEventListener('change', replicar);
            inputIni.addEventListener('input', replicar);
        }
    }

    /* ----------------------------------------------------------------------
       Typeaheads dos filtros (Produto via FABRICANTE + Parceiro)
       Reusa endpoints existentes do desktop:
         /sankhya/produtos/search/?q=X&fabricante=1  → [{fabricante}, ...]
         /sankhya/parceiros/search/?q=X              → [{codparc, nomeparc}, ...]
       ---------------------------------------------------------------------- */
    function setupTypeahead(opts) {
        var input = $m(opts.inputId);
        var hidden = $m(opts.hiddenId);
        var dd = $m(opts.dropdownId);
        if (!input || !dd) return;
        var debounceMs = opts.debounceMs || 280;
        var timer = null;
        var activeIdx = -1;
        var items = [];

        function close() {
            dd.hidden = true;
            dd.innerHTML = '';
            activeIdx = -1;
            items = [];
        }

        function render(results) {
            items = results || [];
            if (!items.length) {
                dd.innerHTML = '<div class="m-dropdown-empty">Nada encontrado</div>';
                dd.hidden = false;
                return;
            }
            dd.innerHTML = items.map(function (it, idx) {
                return '<div class="m-dropdown-item" data-idx="' + idx + '">' +
                    escapeHtml(opts.label(it)) +
                    (opts.sub ? '<span class="m-dropdown-item__sec">' + escapeHtml(opts.sub(it)) + '</span>' : '') +
                '</div>';
            }).join('');
            dd.hidden = false;
        }

        function pick(it) {
            if (hidden) hidden.value = opts.pickHidden(it);
            input.value = opts.pickVisible(it);
            close();
        }

        function fetchAndRender(q) {
            var url = opts.url + (opts.url.indexOf('?') >= 0 ? '&' : '?') + 'q=' + encodeURIComponent(q);
            fetch(url, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    var arr = j && (j.results || j.items || j) || [];
                    if (!Array.isArray(arr)) arr = [];
                    render(arr.slice(0, 15));
                })
                .catch(function () { close(); });
        }

        input.addEventListener('input', function () {
            clearTimeout(timer);
            var q = input.value.trim();
            // Quando o operador apaga, limpa o hidden também (sai do filtro)
            if (!q) {
                if (hidden) hidden.value = '';
                close();
                return;
            }
            timer = setTimeout(function () { fetchAndRender(q); }, debounceMs);
        });

        input.addEventListener('blur', function () {
            // Atraso pra permitir click no item
            setTimeout(close, 200);
        });

        dd.addEventListener('mousedown', function (e) {
            var item = e.target.closest('.m-dropdown-item');
            if (!item) return;
            e.preventDefault();
            var idx = parseInt(item.dataset.idx, 10);
            if (!isNaN(idx) && items[idx]) pick(items[idx]);
        });
        // touchstart pra responder rápido no mobile
        dd.addEventListener('touchstart', function (e) {
            var item = e.target.closest('.m-dropdown-item');
            if (!item) return;
            var idx = parseInt(item.dataset.idx, 10);
            if (!isNaN(idx) && items[idx]) pick(items[idx]);
        }, { passive: true });
    }

    function setupFiltrosTypeaheads() {
        // Produto — Padrão A (Fabricante, texto LIKE em pr.FABRICANTE)
        setupTypeahead({
            inputId: 'm_filtroProduto',
            hiddenId: 'm_filtroFabricanteHidden',
            dropdownId: 'm_filtroProdutoDropdown',
            url: '/sankhya/produtos/search/?fabricante=1&limit=15',
            label: function (it) { return (it.fabricante || it.descr || '').trim(); },
            pickHidden: function (it) { return (it.fabricante || it.descr || '').trim(); },
            pickVisible: function (it) { return (it.fabricante || it.descr || '').trim(); }
        });

        // Parceiro — Padrão B (CODPARC numérico)
        setupTypeahead({
            inputId: 'm_filtroParceiro',
            hiddenId: 'm_filtroCodparcHidden',
            dropdownId: 'm_filtroParceiroDropdown',
            url: '/sankhya/parceiros/search/?limit=15',
            label: function (it) {
                var cod = it.codparc || it.cod || '';
                var nome = it.nomeparc || it.descr || '';
                return cod ? (cod + ' — ' + nome) : nome;
            },
            sub: function (it) { return it.razaosocial || ''; },
            pickHidden: function (it) { return String(it.codparc || it.cod || ''); },
            pickVisible: function (it) {
                var cod = it.codparc || it.cod || '';
                var nome = it.nomeparc || it.descr || '';
                return cod ? (cod + ' — ' + nome) : nome;
            }
        });
    }

    /* ======================================================================
       SWIPE-TO-BACK — gesto touch da esquerda pra direita volta uma tela
       ----------------------------------------------------------------------
       - Funciona em telas que NÃO são a inicial (detalhe, item)
       - Decide horizontal vs vertical pelo eixo dominante nos primeiros 10px
         (se vertical ganha, libera scroll normal sem interferir)
       - Acompanha o dedo com translateX, com leve borracha
       - Se passou de 35% da largura OU velocidade > 0.5px/ms, completa o pop
       - Senão, volta animado pra origem
       ====================================================================== */
    function setupSwipeToBack() {
        var DISMISS_PCT = 0.35;
        var VELOCITY_THRESHOLD = 0.5;
        var EDGE_HINT = 24; // dica visual: arrastar do canto esquerdo é mais sensível

        Object.keys(screens).forEach(function (name) {
            if (name === 'lista') return; // tela inicial não tem back
            var screen = screens[name];
            var startX = 0, startY = 0, startT = 0;
            var lastX = 0;
            var tracking = false;
            var canceled = false;
            var width = 1;

            screen.addEventListener('touchstart', function (e) {
                if (e.touches.length !== 1) { canceled = true; return; }
                if (screen !== screens[stack[stack.length - 1]]) return; // só tela ativa
                var t = e.touches[0];
                startX = lastX = t.clientX;
                startY = t.clientY;
                startT = Date.now();
                width = window.innerWidth || document.documentElement.clientWidth;
                tracking = false;
                canceled = false;
            }, { passive: true });

            screen.addEventListener('touchmove', function (e) {
                if (canceled) return;
                var t = e.touches[0];
                var dx = t.clientX - startX;
                var dy = t.clientY - startY;

                if (!tracking) {
                    // Decisão: ainda não definiu eixo dominante
                    if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
                    // Vertical ganhou → libera scroll, ignora pelo resto do gesto
                    if (Math.abs(dy) > Math.abs(dx)) { canceled = true; return; }
                    // Horizontal pra esquerda → ignora (não é "voltar")
                    if (dx < 0) { canceled = true; return; }
                    tracking = true;
                    screen.style.transition = 'none';
                    screen.style.willChange = 'transform';
                }

                lastX = t.clientX;
                // Borracha leve depois de 80% da largura
                var translate = dx;
                if (translate > width * 0.8) {
                    translate = width * 0.8 + (translate - width * 0.8) * 0.3;
                }
                screen.style.transform = 'translateX(' + Math.max(0, translate) + 'px)';
            }, { passive: true });

            screen.addEventListener('touchend', function () {
                if (canceled || !tracking) {
                    canceled = false;
                    tracking = false;
                    return;
                }
                var dx = lastX - startX;
                var dt = Date.now() - startT;
                var velocity = dt > 0 ? dx / dt : 0;

                screen.style.transition = '';
                screen.style.willChange = '';

                if (dx > width * DISMISS_PCT || velocity > VELOCITY_THRESHOLD) {
                    // Completa pop: anima até fora da tela e dispara popScreen
                    screen.style.transform = 'translateX(100%)';
                    setTimeout(function () {
                        popScreen();
                        screen.style.transform = '';
                    }, 280);
                } else {
                    // Volta pra origem
                    screen.style.transform = '';
                }
                tracking = false;
            }, { passive: true });

            screen.addEventListener('touchcancel', function () {
                screen.style.transition = '';
                screen.style.transform = '';
                screen.style.willChange = '';
                tracking = false;
                canceled = false;
            }, { passive: true });
        });
    }

    /* ======================================================================
       BOOT
       ====================================================================== */
    setActiveScreen('lista');
    hidratarListaNotas();
    setupScrollPaginar();
    setupSwipeToBack();
    setupFiltrosBotoes();
    setupFiltrosTypeaheads();
    syncFiltrosDesktopParaMobile();

    // Hash-routing inicial (se URL tem #detalhe etc — preserva refresh)
    var hash = (location.hash || '').replace('#', '');
    if (hash && screens[hash] && hash !== 'lista') {
        // Fase 2 não persiste contexto da nota — volta pra lista
        try { history.replaceState(null, '', location.pathname + location.search); } catch (e) { }
    }
})();
