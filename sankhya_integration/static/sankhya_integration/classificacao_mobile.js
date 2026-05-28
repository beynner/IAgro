/* ==========================================================================
   CLASSIFICAÇÃO MOBILE — redesign app-like (Mai/2026)
   Estrutura espelha a Entrada Mobile. Convive com classificacao.js (desktop).
   Só ativa em viewport ≤900px.
   ========================================================================== */
;(function () {
    'use strict';

    var mqMobile = window.matchMedia('(max-width: 900px)');
    var mob = document.querySelector('.classificacao-mobile');
    if (!mob) return;

    if (!mqMobile.matches) {
        try {
            mqMobile.addEventListener('change', function (e) {
                if (e.matches) location.reload();
            });
        } catch (e) { }
        return;
    }

    /* ====================== HELPERS ====================== */
    function $m(id) { return document.getElementById(id); }
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
    function fmtBr1(n) {
        var v = parseFloat(n);
        if (isNaN(v)) return '0,0';
        return v.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    }
    function parseBR(s) {
        if (s == null) return null;
        s = String(s).trim().replace(',', '.');
        if (!s) return null;
        var v = parseFloat(s);
        return isNaN(v) ? null : v;
    }
    function getCsrf() {
        if (window.IAgro && IAgro.getCookie) return IAgro.getCookie('csrftoken') || '';
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }
    function mostrarToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) IAgro.showToast(msg, tipo || 'success');
        else alert(msg);
    }

    /* ====================== ESTADO ====================== */
    var ESTADO = {
        lotes: [],         // lista renderizada
        loteAtual: null,   // {lote, ...}
        dadosLote: null,   // resposta de /sankhya/lote/consultar/
        descarteOp: 'add', // 'add' | 'sub'
        itemEditando: null,        // {sequencia, codprod, descrprod, qtd, peso, codvol} quando swipe-to-edit
        itemRecemAdicionado: null, // {descr, qtd, peso} - feedback do último salvo no sheet
    };

    /* ====================== NAVEGAÇÃO ====================== */
    var screens = {};
    mob.querySelectorAll('.m-screen').forEach(function (el) {
        screens[el.dataset.screen] = el;
    });
    var stack = ['lista'];

    function setActiveScreen(name) {
        // Fecha qualquer swipe aberto antes de trocar de tela (paridade Entrada)
        if (typeof fecharTodosSwipesProdutos === 'function') fecharTodosSwipesProdutos();
        Object.keys(screens).forEach(function (k) {
            screens[k].classList.toggle('is-active', k === name);
        });
        mob.querySelectorAll('.m-bottom-nav__item').forEach(function (b) {
            b.classList.toggle('is-active', b.dataset.nav === 'lista' && name === 'lista');
        });
    }
    function pushScreen(name) {
        if (!screens[name] || stack[stack.length - 1] === name) return;
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
    window.addEventListener('popstate', function () { if (stack.length > 1) popScreen(); });
    mob.querySelectorAll('[data-back-to]').forEach(function (btn) {
        btn.addEventListener('click', function () { popScreen(); });
    });

    /* ====================== BOTTOM SHEETS ====================== */
    var sheets = {};
    mob.querySelectorAll('.m-sheet').forEach(function (el) { sheets[el.dataset.sheet] = el; });
    function openSheet(name) {
        // Fecha swipes abertos antes de abrir um sheet (paridade Entrada)
        if (typeof fecharTodosSwipesProdutos === 'function') fecharTodosSwipesProdutos();
        var s = sheets[name]; if (s) s.setAttribute('aria-hidden', 'false');
    }
    function closeSheet(el) { if (typeof el === 'string') el = sheets[el]; if (el) el.setAttribute('aria-hidden', 'true'); }

    mob.querySelectorAll('[data-open-sheet]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var nome = btn.dataset.openSheet;
            openSheet(nome);
        });
    });
    mob.querySelectorAll('[data-close-sheet]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var sheetEl = btn.closest('.m-sheet');
            if (sheetEl) closeSheet(sheetEl);
        });
    });

    /* ====================== BOTTOM NAV ====================== */
    mob.querySelectorAll('.m-bottom-nav__item').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var nav = btn.dataset.nav;
            if (nav === 'lista') popToRoot();
            else if (nav === 'buscar') {
                popToRoot();
                var s = $m('m_clss_search');
                if (s) setTimeout(function () { s.focus(); }, 120);
            }
        });
    });

    /* ====================== SIDEBAR TOGGLE ====================== */
    mob.querySelectorAll('[data-sidebar-toggle]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            var g = document.getElementById('btnSidebarToggleMobile');
            if (g) g.click();
        });
    });

    /* ====================== LISTA DE LOTES ====================== */
    // Mobile traz TODOS os lotes do filtro padrão (sem paginação, sem scroll infinito).
    // O filtro padrão (AMARELO + VERMELHO) já restringe o universo — operador raramente
    // tem >1000 lotes em "Classificando + A Classificar". Limit alto + datas amplas
    // garantem que todos cabem em 1 fetch.
    var MOBILE_LIMIT = 10000;

    function carregarLotes() {
        var listaEl = $m('m_clss_lotesList');
        if (!listaEl) return;

        // Lê filtros do form desktop pra incluir como query params
        var form = document.querySelector('.classificacao-desktop #filtersForm');
        var params = new URLSearchParams();
        var temDataStart = false;
        var temDataEnd = false;
        if (form) {
            var fStart = form.querySelector('input[name="start"]');
            var fEnd = form.querySelector('input[name="end"]');
            var fPed = form.querySelector('input[name="nunota_ini"]');
            var fFab = form.querySelector('input[name="fabricante"]');
            var fParc = form.querySelector('input[name="codparc"]');
            var fLote = form.querySelector('input[name="lote"]');
            if (fStart && fStart.value) { params.set('date_start', fStart.value); temDataStart = true; }
            if (fEnd && fEnd.value) { params.set('date_end', fEnd.value); temDataEnd = true; }
            if (fPed && fPed.value) params.set('nunota_ini', fPed.value);
            if (fFab && fFab.value) params.set('fabricante', fFab.value);
            if (fParc && fParc.value) params.set('codparc', fParc.value);
            if (fLote && fLote.value) params.set('lote', fLote.value);
        }

        // Sem filtro de data → manda janela super ampla pra desativar a trava de 60 dias
        // do backend (oracle_conn.py linha "AND t.DTNEG >= SYSDATE - 60").
        // Decisão alinhada com operador: filtro padrão (Classificando + A Classificar) já restringe.
        if (!temDataStart && !temDataEnd) {
            params.set('date_start', '2000-01-01');
            params.set('date_end', '2099-12-31');
        }

        // Status: lê checkboxes do desktop (verde/amarelo/vermelho)
        var status = [];
        var cbG = document.querySelector('.classificacao-desktop #filterGreen');
        var cbY = document.querySelector('.classificacao-desktop #filterYellow');
        var cbR = document.querySelector('.classificacao-desktop #filterRed');
        if (cbG && cbG.checked) status.push('VERDE');
        if (cbY && cbY.checked) status.push('AMARELO');
        if (cbR && cbR.checked) status.push('VERMELHO');
        // Se nenhuma checkbox estiver marcada, força default AMARELO + VERMELHO
        if (!status.length) { status.push('AMARELO'); status.push('VERMELHO'); }
        status.forEach(function (s) { params.append('status', s); });

        // Limit alto: traz TODOS os lotes em 1 fetch (sem paginação)
        params.set('limit', String(MOBILE_LIMIT));

        var url = '/sankhya/compras/classificacao/api/lotes/?' + params.toString();
        fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                if (j && j.ok) {
                    ESTADO.lotes = j.lotes || [];
                    renderLotes(ESTADO.lotes);
                } else {
                    listaEl.innerHTML = '<div class="m-empty-state"><i class="ph ph-warning"></i><p>Falha ao carregar lotes.</p></div>';
                }
            })
            .catch(function () {
                listaEl.innerHTML = '<div class="m-empty-state"><i class="ph ph-warning"></i><p>Falha ao carregar lotes.</p></div>';
            });
    }

    function classForStatus(status) {
        if (status === 'VERDE') return 'm-card-nota--ok';
        if (status === 'AMARELO') return 'm-card-nota--pendente';
        return 'm-card-nota--alerta'; // VERMELHO ou desconhecido
    }

    function renderLotes(lotes) {
        var listaEl = $m('m_clss_lotesList');
        if (!listaEl) return;
        if (!lotes.length) {
            listaEl.innerHTML = '<div class="m-empty-state"><i class="ph ph-tray"></i><p>Nenhum lote encontrado.</p></div>';
            return;
        }
        var html = '';
        lotes.forEach(function (l) {
            var letra = (String(l.parceiro || '?').match(/[A-Za-zÀ-ÿ]/) || ['?'])[0].toUpperCase();
            var dataCurta = (l.data || '').split('/').slice(0, 2).join('/');
            var nomeProd = l.produto || '';
            var nomeParc = l.parceiro || '';
            // Mostra produto como principal + parceiro/lote como secundário
            html += '<article class="m-card-nota ' + classForStatus(l.status) +
                    '" data-lote="' + escapeHtml(l.lote) +
                    '" data-parc="' + escapeHtml(nomeParc) +
                    '" data-prod="' + escapeHtml(nomeProd) +
                    '" data-nunota-origem="' + escapeHtml(l.nunota_origem) + '">' +
                '<div class="m-card-nota__avatar">' + escapeHtml(letra) + '</div>' +
                '<span class="m-card-nota__nome">' + escapeHtml(nomeProd) + '</span>' +
                '<span class="m-card-nota__sub">' + escapeHtml(nomeParc.substring(0, 18)) + '</span>' +
                '<span class="m-card-nota__data">' + escapeHtml(dataCurta) + '</span>' +
                '<i class="ph ph-caret-right m-card-nota__chevron"></i>' +
            '</article>';
        });
        listaEl.innerHTML = html;
        bindCardsLote();
    }

    function bindCardsLote() {
        document.querySelectorAll('#m_clss_lotesList .m-card-nota').forEach(function (card) {
            card.addEventListener('click', function () {
                var lote = card.dataset.lote;
                if (!lote) return;
                abrirDetalheLote({
                    lote: lote,
                    parc: card.dataset.parc || '',
                    prod: card.dataset.prod || '',
                    nunota_origem: card.dataset.nunotaOrigem || ''
                });
            });
        });
    }

    /* ====================== DETALHE DO LOTE ====================== */
    function abrirDetalheLote(meta) {
        ESTADO.loteAtual = meta;
        ESTADO.dadosLote = null;

        // Reset visual do hero
        $m('m_clss_fornecedor').textContent = meta.parc || '—';
        $m('m_clss_produto').textContent = meta.prod || '—';
        $m('m_clss_pedidoData').textContent = meta.nunota_origem ? ('Pedido ' + meta.nunota_origem) : '—';
        var heroLoteResetEl = $m('m_clss_heroLote');
        if (heroLoteResetEl) heroLoteResetEl.textContent = meta.lote || '—';

        ['m_clss_resInNatura', 'm_clss_resClassificado', 'm_clss_resDescarte', 'm_clss_resEstoque'].forEach(function (id) {
            var el = $m(id); if (el) el.textContent = '0,0';
        });
        ['m_clss_resClassificadoPct', 'm_clss_resDescartePct', 'm_clss_resEstoquePct'].forEach(function (id) {
            var el = $m(id); if (el) el.textContent = '0%';
        });

        var listaCl = $m('m_clss_classificadosList');
        if (listaCl) listaCl.innerHTML = '<div class="m-empty-state"><i class="ph ph-spinner"></i><p>Carregando…</p></div>';
        $m('m_clss_classCount').textContent = '0';

        pushScreen('detalhe');

        fetch('/sankhya/lote/consultar/?lote=' + encodeURIComponent(meta.lote), {
            credentials: 'same-origin', headers: { 'Accept': 'application/json' }
        })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                if (!j || !j.ok) {
                    mostrarToast(j && j.error || 'Falha ao consultar lote', 'error');
                    return;
                }
                ESTADO.dadosLote = j;
                renderDetalhe(j);
            })
            .catch(function () { mostrarToast('Falha de rede ao consultar lote', 'error'); });
    }

    function renderDetalhe(j) {
        var entrada = (j.entradas && j.entradas[0]) || {};
        var classificacoes = j.classificacoes || [];

        $m('m_clss_fornecedor').textContent = entrada.parceiro || '—';
        $m('m_clss_produto').textContent = entrada.descr || '—';
        // Lote único da classificação (CODAGREGACAO) — vem do loteAtual ou dos agregados
        var loteTxt = (ESTADO.loteAtual && ESTADO.loteAtual.lote) ||
                      (j.agregados && j.agregados.lote) || '—';
        var heroLote = $m('m_clss_heroLote');
        if (heroLote) heroLote.textContent = loteTxt;
        $m('m_clss_pedidoData').textContent = (entrada.nunota ? ('Pedido ' + entrada.nunota) : '—') + ' · ' + (entrada.dtneg || '');

        var inNatura = parseFloat(entrada.qtd || 0);
        var classKg = parseFloat(j.qtd_class_kg || 0);
        var descarte = parseFloat(j.qtd_descarte_kg || (j.agregados && j.agregados.descarte) || 0);
        var estoque = parseFloat(j.qtd_estoque_kg || (inNatura - classKg - descarte));

        $m('m_clss_resInNatura').textContent = fmtBr1(inNatura);
        $m('m_clss_resClassificado').textContent = fmtBr1(classKg);
        $m('m_clss_resDescarte').textContent = fmtBr1(descarte);
        $m('m_clss_resEstoque').textContent = fmtBr1(Math.max(0, estoque));

        // Descarte inline (abaixo do toggle Finalizada)
        var descInline = $m('m_clss_descarteAtualDetalhe');
        if (descInline) descInline.textContent = fmtBr1(descarte);

        var pct = function (v) { return inNatura > 0 ? Math.round((v / inNatura) * 100) + '%' : '0%'; };
        $m('m_clss_resClassificadoPct').textContent = pct(classKg);
        $m('m_clss_resDescartePct').textContent = pct(descarte);
        $m('m_clss_resEstoquePct').textContent = pct(Math.max(0, estoque));

        // Toggle Finalizada
        $m('m_clss_toggleStatus').checked = j.status_pendente === 'N';

        // Lista de classificações
        renderClassificacoes(classificacoes);
    }

    function renderClassificacoes(items) {
        var listaCl = $m('m_clss_classificadosList');
        $m('m_clss_classCount').textContent = String(items.length);
        if (!items.length) {
            listaCl.innerHTML = '<div class="m-empty-state"><i class="ph ph-tray"></i><p>Nenhuma classificação ainda.</p></div>';
            return;
        }
        // Cada card vem dentro de um wrapper com 2 botões swipe (editar + excluir) atrás.
        // Padrão idêntico ao da Entrada Mobile (cards de NOTA — 2 botões 44px = 88px total).
        var html = items.map(function (it) {
            var qtdNum = parseFloat(it.qtd) || 0;
            var pesoNum = parseFloat(it.peso) || 0;
            var codvolStr = String(it.codvol || 'KG');
            var codprodVal = it.codprod || it.cod || '';
            return '<div class="m-clss-class-card-wrap">' +
                '<button type="button" class="m-clss-class-card__swipe-edit" data-action="editar" data-seq="' + escapeHtml(it.sequencia) + '" aria-label="Editar item">' +
                    '<i class="ph ph-pencil-simple" aria-hidden="true"></i>' +
                '</button>' +
                '<button type="button" class="m-clss-class-card__swipe-del" data-action="excluir" data-seq="' + escapeHtml(it.sequencia) + '" aria-label="Excluir item">' +
                    '<i class="ph ph-trash" aria-hidden="true"></i>' +
                '</button>' +
                '<article class="m-clss-class-card" ' +
                    'data-seq="' + escapeHtml(it.sequencia) + '" ' +
                    'data-codprod="' + escapeHtml(codprodVal) + '" ' +
                    'data-descrprod="' + escapeHtml(it.descr || '') + '" ' +
                    'data-qtd="' + qtdNum + '" ' +
                    'data-peso="' + pesoNum + '" ' +
                    'data-codvol="' + escapeHtml(codvolStr) + '">' +
                    '<div class="m-clss-class-card__head">' +
                        '<div class="m-clss-class-card__produto">' + escapeHtml(it.descr || '') + '</div>' +
                        '<div class="m-clss-class-card__meta">Seq ' + escapeHtml(it.sequencia) +
                        (it.peso ? (' · ' + fmtBr(it.peso) + ' kg/cx') : '') + '</div>' +
                    '</div>' +
                    '<div class="m-clss-class-card__qtd">' +
                        fmtBr(it.qtd) + ' kg' +
                        (it.peso ? '<small>' + fmtBr(Math.ceil((it.qtd || 0) / it.peso)) + ' cx</small>' : '') +
                    '</div>' +
                '</article>' +
            '</div>';
        }).join('');
        listaCl.innerHTML = html;
        bindSwipeProdutosClassificados();
    }

    /* ====================== SWIPE-TO-EDIT+DELETE NOS CARDS DE PRODUTOS CLASSIFICADOS ====================== */
    // Padrão idêntico ao da Entrada Mobile (cards de NOTA). Reveal 88px (44 editar + 44 excluir).
    var SWIPE_REVEAL_CLSS = 88;     // 2 botões 44px
    var SWIPE_TRIGGER_CLSS = 44;    // 50% do reveal

    function fecharTodosSwipesProdutos() {
        document.querySelectorAll('#m_clss_classificadosList .m-clss-class-card[data-swipe-open="1"]').forEach(function (card) {
            card.style.transform = '';
            card.dataset.swipeOpen = '0';
        });
    }

    function bindSwipeProdutosClassificados() {
        document.querySelectorAll('#m_clss_classificadosList .m-clss-class-card-wrap').forEach(function (wrap) {
            var card = wrap.querySelector('.m-clss-class-card');
            if (!card || card.dataset.swipeBound === '1') return;
            card.dataset.swipeBound = '1';
            card.dataset.swipeOpen = '0';

            var startX = 0, startY = 0, lastX = 0;
            var tracking = false, canceled = false;

            card.addEventListener('touchstart', function (e) {
                if (e.touches.length !== 1) { canceled = true; return; }
                var t = e.touches[0];
                startX = lastX = t.clientX; startY = t.clientY;
                tracking = false; canceled = false;
            }, { passive: true });

            card.addEventListener('touchmove', function (e) {
                if (canceled) return;
                var t = e.touches[0];
                var dx = t.clientX - startX, dy = t.clientY - startY;
                if (!tracking) {
                    if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
                    if (Math.abs(dy) > Math.abs(dx)) { canceled = true; return; }
                    tracking = true;
                    card.style.transition = 'none';
                    // Fecha outros swipes abertos quando começa um novo
                    document.querySelectorAll('#m_clss_classificadosList .m-clss-class-card[data-swipe-open="1"]').forEach(function (o) {
                        if (o !== card) { o.style.transform = ''; o.dataset.swipeOpen = '0'; }
                    });
                }
                lastX = t.clientX;
                // Aceita swipe pra esquerda (revela botões) OU pra direita (fecha)
                var jaAberto = card.dataset.swipeOpen === '1';
                var translateBase = jaAberto ? -SWIPE_REVEAL_CLSS : 0;
                var translate = translateBase + dx;
                if (translate > 0) translate = translate * 0.3;            // resistência se passar do fechado
                if (translate < -SWIPE_REVEAL_CLSS) {
                    translate = -SWIPE_REVEAL_CLSS + (translate + SWIPE_REVEAL_CLSS) * 0.3;
                }
                card.style.transform = 'translateX(' + translate + 'px)';
            }, { passive: true });

            card.addEventListener('touchend', function () {
                if (canceled || !tracking) { canceled = false; tracking = false; return; }
                var dx = lastX - startX;
                card.style.transition = '';
                var jaAberto = card.dataset.swipeOpen === '1';
                var abrir;
                if (jaAberto) {
                    abrir = dx < SWIPE_TRIGGER_CLSS;  // só fecha se arrastou pra direita o suficiente
                } else {
                    abrir = -dx > SWIPE_TRIGGER_CLSS;  // só abre se arrastou pra esquerda o suficiente
                }
                if (abrir) {
                    card.style.transform = 'translateX(-' + SWIPE_REVEAL_CLSS + 'px)';
                    card.dataset.swipeOpen = '1';
                } else {
                    card.style.transform = '';
                    card.dataset.swipeOpen = '0';
                }
                tracking = false;
            }, { passive: true });

            card.addEventListener('touchcancel', function () {
                card.style.transition = '';
                card.style.transform = card.dataset.swipeOpen === '1' ? 'translateX(-' + SWIPE_REVEAL_CLSS + 'px)' : '';
                tracking = false; canceled = false;
            }, { passive: true });
        });

        // Handlers dos botões swipe (delegação no listaCl — uma vez)
        var listaCl = $m('m_clss_classificadosList');
        if (listaCl && listaCl.dataset.swipeHandlersBound !== '1') {
            listaCl.dataset.swipeHandlersBound = '1';
            listaCl.addEventListener('click', function (e) {
                var btnEdit = e.target.closest('.m-clss-class-card__swipe-edit');
                var btnDel = e.target.closest('.m-clss-class-card__swipe-del');
                if (btnEdit || btnDel) {
                    e.stopPropagation();
                    var wrap = (btnEdit || btnDel).closest('.m-clss-class-card-wrap');
                    if (!wrap) return;
                    var cardBtn = wrap.querySelector('.m-clss-class-card');
                    if (!cardBtn) return;
                    if (btnEdit) abrirItemEdit(cardBtn);
                    else if (btnDel) excluirItemClassificado(cardBtn);
                    return;
                }
                // Padrão swipe-to-edit+delete: click no card já em modo swipe-open fecha o swipe
                // (paridade Entrada Mobile — bindCardsNota em entrada_mobile.js:580).
                var cardClicado = e.target.closest('.m-clss-class-card');
                if (cardClicado && cardClicado.dataset.swipeOpen === '1') {
                    cardClicado.style.transform = '';
                    cardClicado.dataset.swipeOpen = '0';
                }
            });
        }
    }

    /* ====================== EDITAR ITEM CLASSIFICADO ====================== */
    function abrirItemEdit(card) {
        if (!ESTADO.dadosLote || !ESTADO.dadosLote.nunota_class) {
            mostrarToast('Lote sem TGFCAB TOP 26 carregada.', 'error');
            return;
        }
        if (ESTADO.dadosLote.bloqueado_comercial) {
            mostrarToast('🔒 Lote possui negociação Comercial. Edições bloqueadas.', 'error');
            return;
        }
        // Popula sheet com dados do card
        ESTADO.itemEditando = {
            sequencia: parseInt(card.dataset.seq, 10),
            codprod: card.dataset.codprod,
            descrprod: card.dataset.descrprod,
            qtd: parseFloat(card.dataset.qtd) || 0,
            peso: parseFloat(card.dataset.peso) || 0,
            codvol: card.dataset.codvol
        };
        ESTADO.itemRecemAdicionado = null;  // zera feedback ao começar edição
        $m('m_clss_itemProdHidden').value = ESTADO.itemEditando.codprod;
        $m('m_clss_itemProd').value = ESTADO.itemEditando.codprod + ' — ' + ESTADO.itemEditando.descrprod;
        $m('m_clss_itemTotalKg').value = ESTADO.itemEditando.qtd > 0 ? String(ESTADO.itemEditando.qtd) : '';
        $m('m_clss_itemPesoCx').value = ESTADO.itemEditando.peso > 0 ? String(ESTADO.itemEditando.peso) : '';
        // Recalcula CX
        if (ESTADO.itemEditando.qtd > 0 && ESTADO.itemEditando.peso > 0) {
            $m('m_clss_itemTotalCx').value = Math.ceil(ESTADO.itemEditando.qtd / ESTADO.itemEditando.peso);
        } else {
            $m('m_clss_itemTotalCx').value = '';
        }
        // Atualiza UI do botão "Adicionar" → "Salvar alterações" + lista visual
        var btn = $m('m_clss_btnAdicionarItem');
        if (btn) btn.innerHTML = '<i class="ph ph-check" aria-hidden="true"></i> Salvar alterações';
        // Render itens (mesma lista) + abre sheet
        renderSheetItens();
        openSheet('itens');
        // Foca em Total KG (campo mais comum de alterar)
        setTimeout(function () {
            var inp = $m('m_clss_itemTotalKg'); if (inp) inp.focus();
        }, 240);
        // Fecha swipe que estava aberto
        fecharTodosSwipesProdutos();
    }

    /* ====================== EXCLUIR ITEM CLASSIFICADO ====================== */
    function excluirItemClassificado(card) {
        if (!ESTADO.dadosLote || !ESTADO.dadosLote.nunota_class) {
            mostrarToast('Lote sem TGFCAB TOP 26 carregada.', 'error');
            return;
        }
        if (ESTADO.dadosLote.bloqueado_comercial) {
            mostrarToast('🔒 Lote possui negociação Comercial. Edições bloqueadas.', 'error');
            return;
        }
        var seq = parseInt(card.dataset.seq, 10);
        var descr = card.dataset.descrprod || ('Seq ' + seq);
        var nunotaClass = ESTADO.dadosLote.nunota_class;

        var doConfirm = function (cb) {
            if (window.IAgro && IAgro.confirmarAcao) {
                IAgro.confirmarAcao({
                    titulo: 'Excluir item',
                    mensagem: 'Confirma excluir "' + descr + '" da classificação?',
                    tipo: 'perigo'
                }).then(function (ok) { if (ok) cb(); });
            } else if (window.confirm('Excluir "' + descr + '"?')) {
                cb();
            }
        };

        doConfirm(function () {
            // Apenas checar trava primeiro (paridade com Entrada Mobile)
            fetch('/sankhya/item/delete/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({ nunota: nunotaClass, sequencias: [seq], apenas_checar: true })
            })
                .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
                .then(function (chk) {
                    if (!chk.ok || !chk.body || !chk.body.ok) {
                        throw new Error((chk.body && chk.body.error) || 'Bloqueado pelo Comercial.');
                    }
                    // Confirm definitivo
                    return fetch('/sankhya/item/delete/', {
                        method: 'POST', credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                        body: JSON.stringify({ nunota: nunotaClass, sequencias: [seq] })
                    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); });
                })
                .then(function (resp) {
                    if (!resp.ok || !resp.body || !resp.body.ok) {
                        throw new Error((resp.body && resp.body.error) || 'Falha ao excluir item');
                    }
                    mostrarToast('Item excluído ✓', 'success');
                    // Se cabeçalho TOP 26 foi removido (último item), zera nunota_class no estado
                    if (resp.body.cabecalho_excluido) {
                        ESTADO.dadosLote.nunota_class = null;
                        ESTADO.dadosLote.status_pendente = 'S';
                    }
                    // Re-fetch dados do lote
                    return fetch('/sankhya/lote/consultar/?lote=' + encodeURIComponent(ESTADO.loteAtual.lote), {
                        credentials: 'same-origin', headers: { 'Accept': 'application/json' }
                    }).then(function (r) { return r.json(); });
                })
                .then(function (j) {
                    if (j && j.ok) {
                        ESTADO.dadosLote = j;
                        renderDetalhe(j);
                    }
                })
                .catch(function (err) {
                    mostrarToast(err && err.message ? err.message : 'Falha ao excluir', 'error');
                });
        });
    }

    /* ====================== TOGGLE FINALIZADA ====================== */
    // Backend espera payload {nunota_class, pendente} — paridade com desktop classificacao.js
    function chamarToggleStatusBackend(toggleEl) {
        if (!ESTADO.dadosLote || !ESTADO.dadosLote.nunota_class) {
            mostrarToast('Lote ainda não tem classificação criada.', 'error');
            toggleEl.checked = !toggleEl.checked;
            return;
        }
        var nunotaClass = ESTADO.dadosLote.nunota_class;
        var novoStatus = toggleEl.checked ? 'N' : 'S';
        fetch('/sankhya/item/toggle_status/', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ nunota_class: nunotaClass, pendente: novoStatus })
        })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                if (j && j.ok) {
                    mostrarToast(novoStatus === 'N' ? 'Classificação finalizada ✓' : 'Reaberta', 'success');
                    ESTADO.dadosLote.status_pendente = novoStatus;
                    // Espelha no outro toggle (sheet ↔ tela detalhe)
                    var outro = (toggleEl.id === 'm_clss_toggleStatus') ? $m('m_clss_toggleStatusSheet') : $m('m_clss_toggleStatus');
                    if (outro) outro.checked = toggleEl.checked;
                } else {
                    mostrarToast(j && j.error || 'Falha ao mudar status', 'error');
                    toggleEl.checked = !toggleEl.checked;
                }
            })
            .catch(function () {
                mostrarToast('Falha de rede', 'error');
                toggleEl.checked = !toggleEl.checked;
            });
    }
    var toggleStatus = $m('m_clss_toggleStatus');
    if (toggleStatus) {
        toggleStatus.addEventListener('change', function () { chamarToggleStatusBackend(toggleStatus); });
    }

    /* ====================== DESCARTE (bottom sheet) ====================== */
    var btnDescarte = $m('m_clss_btnDescarte');
    if (btnDescarte) {
        btnDescarte.addEventListener('click', function () {
            if (!ESTADO.dadosLote) return;
            var atual = parseFloat(ESTADO.dadosLote.qtd_descarte_kg || (ESTADO.dadosLote.agregados && ESTADO.dadosLote.agregados.descarte) || 0);
            $m('m_clss_descarteCurrent').textContent = fmtBr1(atual) + ' kg';
            $m('m_clss_descarteValor').value = '';
            ESTADO.descarteOp = 'add';
            document.querySelectorAll('.m-toggle-btn[data-descarte-op]').forEach(function (b) {
                b.classList.toggle('is-active', b.dataset.descarteOp === 'add');
            });
            openSheet('descarte');
        });
    }

    document.querySelectorAll('.m-toggle-btn[data-descarte-op]').forEach(function (b) {
        b.addEventListener('click', function () {
            ESTADO.descarteOp = b.dataset.descarteOp;
            document.querySelectorAll('.m-toggle-btn[data-descarte-op]').forEach(function (x) {
                x.classList.toggle('is-active', x === b);
            });
        });
    });

    // Helper único pra atualizar descarte (paridade com desktop classificacao.js — payload {lote, valor, operacao})
    // operacao = 'soma' | 'subtrai'
    function chamarUpdateDescarteBackend(operacao, valor) {
        if (!ESTADO.loteAtual) return Promise.reject(new Error('Lote não selecionado'));
        if (valor == null || valor <= 0) {
            return Promise.reject(new Error('Informe a quantidade.'));
        }
        return fetch('/sankhya/item/update_descarte_lote/', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ lote: ESTADO.loteAtual.lote, valor: valor, operacao: operacao })
        }).then(function (r) { return r.json().then(function (j) {
            if (!r.ok || !j || !j.ok) throw new Error(j && j.error || 'Falha ao atualizar descarte');
            return j;
        }); });
    }

    var btnDescarteConf = $m('m_clss_btnDescarteConfirmar');
    if (btnDescarteConf) {
        btnDescarteConf.addEventListener('click', function () {
            if (!ESTADO.loteAtual || !ESTADO.dadosLote) return;
            var valor = parseBR($m('m_clss_descarteValor').value);
            if (valor == null || valor <= 0) {
                mostrarToast('Informe a quantidade.', 'error');
                return;
            }
            var operacao = (ESTADO.descarteOp === 'add') ? 'soma' : 'subtrai';
            chamarUpdateDescarteBackend(operacao, valor)
                .then(function () {
                    mostrarToast('Descarte atualizado ✓', 'success');
                    closeSheet('descarte');
                    abrirDetalheLote(ESTADO.loteAtual);
                })
                .catch(function (e) { mostrarToast(e && e.message || 'Falha de rede', 'error'); });
        });
    }

    /* ====================== FAB ADICIONAR CLASSIFICAÇÃO + BOTÃO LÁPIS HEADER ====================== */
    // FAB verde (+) e botão lápis (header) abrem o mesmo bottom sheet "Itens — Nota"
    function abrirSheetItensComGuards() {
        if (!ESTADO.loteAtual || !ESTADO.dadosLote) {
            mostrarToast('Carregue um lote antes de adicionar itens.', 'error');
            return;
        }
        if (ESTADO.dadosLote.bloqueado_comercial) {
            mostrarToast('🔒 Lote possui negociação Comercial. Edições bloqueadas.', 'error');
            return;
        }
        abrirSheetItens();
    }
    var fabAdd = $m('m_clss_fabAdd');
    if (fabAdd) fabAdd.addEventListener('click', abrirSheetItensComGuards);
    var btnEditarItensHeader = $m('m_clss_btnEditarItens');
    if (btnEditarItensHeader) btnEditarItensHeader.addEventListener('click', abrirSheetItensComGuards);

    /* ====================== BOTTOM SHEET "ITENS — NOTA" ====================== */
    // Espelha o modal #cabItemsModal do desktop. Endpoints reusados:
    //   POST /sankhya/compras/central/salvar/ (cria TGFCAB TOP 26 se não existe)
    //   POST /sankhya/item/save/ (cria TGFITE)
    //   POST /sankhya/item/update_descarte_lote/ (descarte +/-)
    //   POST /sankhya/item/toggle_status/ (toggle finalizada)
    //   GET  /sankhya/produtos/pesquisar-modal/?q=X&fabricante=Y (typeahead filtrado)
    //   GET  /sankhya/lote/consultar/?lote=X (re-fetch após salvar)

    function abrirSheetItens() {
        // Limpa form e estado de edição (modo "Adicionar item")
        ESTADO.itemEditando = null;
        ESTADO.itemRecemAdicionado = null;  // zera feedback ao abrir
        $m('m_clss_itemProd').value = '';
        $m('m_clss_itemProdHidden').value = '';
        $m('m_clss_itemTotalKg').value = '';
        $m('m_clss_itemTotalCx').value = '';
        $m('m_clss_itemPesoCx').value = '';
        // Restaura label do botão
        var btn = $m('m_clss_btnAdicionarItem');
        if (btn) btn.innerHTML = '<i class="ph ph-plus" aria-hidden="true"></i> Adicionar item';
        // Render itens classificados (vazio nesse momento — só recém-salvo aparece)
        renderSheetItens();
        openSheet('itens');
        // Foca no campo Produto pra agilizar (sem zoom — font-size 16px)
        setTimeout(function () {
            var p = $m('m_clss_itemProd');
            if (p) p.focus();
        }, 240);
    }

    function renderSheetItens() {
        var dados = ESTADO.dadosLote || {};
        var classificacoes = dados.classificacoes || [];
        // Contador sempre mostra o total real do lote
        var countEl = $m('m_clss_itemsSheetCount');
        if (countEl) countEl.textContent = String(classificacoes.length);

        // Lista detalha SOMENTE o último item salvo nesta sessão (feedback visual).
        // Ao abrir o sheet, lista volta a ficar vazia ("Nenhum produto adicionado nesta sessão").
        // Quando operador adiciona/edita, o card do item recém-salvo aparece pra validar o sucesso.
        var listaEl = $m('m_clss_itemsSheetList');
        if (!listaEl) return;
        var recente = ESTADO.itemRecemAdicionado;
        if (!recente) {
            listaEl.innerHTML = '<div class="m-empty-state"><i class="ph ph-tray"></i><p>Nenhum produto adicionado nesta sessão.</p></div>';
            return;
        }
        var qtdNum = parseFloat(recente.qtd) || 0;
        var pesoNum = parseFloat(recente.peso) || 0;
        var qtdLabel = fmtBr(qtdNum) + ' kg' +
            (pesoNum > 0 ? '<small style="display:block; font-size:9.5px; color:var(--m-text-muted); margin-top:-2px;">' + fmtBr(Math.ceil(qtdNum / pesoNum)) + ' cx</small>' : '');
        listaEl.innerHTML =
            '<div class="m-clss-item-card" data-seq="' + escapeHtml(recente.sequencia || '') + '">' +
                '<div class="m-clss-item-card__info">' +
                    '<div class="m-clss-item-card__produto">' + escapeHtml(recente.descr || '') + '</div>' +
                    '<div class="m-clss-item-card__meta">' +
                        (recente.sequencia ? 'Seq ' + escapeHtml(recente.sequencia) : 'Recém-salvo') +
                        (pesoNum > 0 ? ' · ' + fmtBr(pesoNum) + ' kg/cx' : '') +
                    '</div>' +
                '</div>' +
                '<div class="m-clss-item-card__qtd">' + qtdLabel + '</div>' +
            '</div>';
    }

    // Typeahead de produto — filtra pelo TGFPRO.FABRICANTE do in natura
    // (vem em dadosLote.resumo.fabricante — paridade com desktop PH_FABRICANTE)
    (function setupTypeaheadProdutoItem() {
        var input = $m('m_clss_itemProd');
        var hidden = $m('m_clss_itemProdHidden');
        var dd = $m('m_clss_itemProdDropdown');
        if (!input || !dd) return;
        var timer = null, items = [];
        function close() { dd.hidden = true; dd.innerHTML = ''; items = []; }
        function render(results) {
            items = results || [];
            if (!items.length) {
                dd.innerHTML = '<div class="m-dropdown-empty">Nada encontrado</div>'; dd.hidden = false; return;
            }
            dd.innerHTML = items.map(function (it, idx) {
                var cod = it.CODPROD || it.codprod || it.cod || '';
                var nome = it.DESCRPROD || it.descrprod || it.descr || '';
                return '<div class="m-dropdown-item" data-idx="' + idx + '">' + escapeHtml(cod + ' — ' + nome) + '</div>';
            }).join('');
            dd.hidden = false;
        }
        function pick(it) {
            var cod = it.CODPROD || it.codprod || it.cod || '';
            var nome = it.DESCRPROD || it.descrprod || it.descr || '';
            if (hidden) hidden.value = String(cod);
            input.value = cod + ' — ' + nome;
            close();
            // Foca no Total KG depois de escolher produto
            var nxt = $m('m_clss_itemTotalKg'); if (nxt) nxt.focus();
        }
        input.addEventListener('input', function () {
            clearTimeout(timer);
            var q = input.value.trim();
            if (!q) { if (hidden) hidden.value = ''; close(); return; }
            timer = setTimeout(function () {
                // Fabricante real vem de TGFPRO.FABRICANTE do produto in natura (e não do DESCRPROD).
                // Endpoint exige `fabricante` pra trazer só produtos da mesma família.
                // Paridade com desktop: window.PH_FABRICANTE = loteData.resumo.fabricante
                var fab = (ESTADO.dadosLote && ESTADO.dadosLote.resumo && ESTADO.dadosLote.resumo.fabricante)
                    ? String(ESTADO.dadosLote.resumo.fabricante).trim() : '';
                var url = '/sankhya/produtos/search/modal/?q=' + encodeURIComponent(q) +
                          '&fabricante=' + encodeURIComponent(fab) + '&limit=15';
                fetch(url, { credentials: 'same-origin' })
                    .then(function (r) { return r.json(); })
                    .then(function (j) {
                        var arr = (j && j.results) || [];
                        if (!Array.isArray(arr)) arr = [];
                        render(arr.slice(0, 15));
                    })
                    .catch(close);
            }, 250);
        });
        input.addEventListener('blur', function () { setTimeout(close, 200); });
        dd.addEventListener('mousedown', function (e) {
            var it = e.target.closest('.m-dropdown-item'); if (!it) return;
            e.preventDefault();
            var idx = parseInt(it.dataset.idx, 10);
            if (!isNaN(idx) && items[idx]) pick(items[idx]);
        });
        dd.addEventListener('touchstart', function (e) {
            var it = e.target.closest('.m-dropdown-item'); if (!it) return;
            var idx = parseInt(it.dataset.idx, 10);
            if (!isNaN(idx) && items[idx]) pick(items[idx]);
        }, { passive: true });
    })();

    // Recalcula Total CX automaticamente quando Total KG ou Peso CX mudam
    function recalcularTotalCx() {
        var totalKg = parseBR($m('m_clss_itemTotalKg').value) || 0;
        var peso = parseBR($m('m_clss_itemPesoCx').value) || 0;
        var inpCx = $m('m_clss_itemTotalCx');
        if (totalKg > 0 && peso > 0) {
            inpCx.value = Math.ceil(totalKg / peso);
        }
    }
    ['m_clss_itemTotalKg', 'm_clss_itemPesoCx'].forEach(function (id) {
        var el = $m(id);
        if (el) {
            el.addEventListener('input', recalcularTotalCx);
            el.addEventListener('blur', recalcularTotalCx);
        }
    });

    // Adicionar item — replica fluxo do desktop `saveItem`
    var btnAdicionarItem = $m('m_clss_btnAdicionarItem');
    if (btnAdicionarItem) {
        btnAdicionarItem.addEventListener('click', function () { salvarItemClassificacao(); });
    }

    function salvarItemClassificacao() {
        if (!ESTADO.loteAtual || !ESTADO.dadosLote) {
            mostrarToast('Lote não carregado.', 'error');
            return;
        }
        var codprod = ($m('m_clss_itemProdHidden').value || '').trim();
        var totalKg = parseBR($m('m_clss_itemTotalKg').value);
        var peso = parseBR($m('m_clss_itemPesoCx').value);

        // Validações (mesmas do desktop saveItem)
        if (!codprod) {
            mostrarToast('Escolha um produto.', 'error');
            $m('m_clss_itemProd').focus(); return;
        }
        if (!totalKg || totalKg <= 0) {
            mostrarToast('Informe o Total KG.', 'error');
            $m('m_clss_itemTotalKg').focus(); return;
        }
        if (!peso || peso <= 0) {
            mostrarToast('O preenchimento do PESO CX é obrigatório!', 'warning');
            $m('m_clss_itemPesoCx').focus(); return;
        }

        btnAdicionarItem.disabled = true;
        btnAdicionarItem.classList.add('is-loading');

        var entrada = (ESTADO.dadosLote.entradas && ESTADO.dadosLote.entradas[0]) || {};
        var nunotaPortal = entrada.nunota;
        var codparc = entrada.codparc;
        var nunotaClass = ESTADO.dadosLote.nunota_class;

        // Modo edição: ESTADO.itemEditando.sequencia preenchido → backend faz UPDATE
        var seqEdit = (ESTADO.itemEditando && ESTADO.itemEditando.sequencia) ? parseInt(ESTADO.itemEditando.sequencia, 10) : null;

        var inserirItem = function (nunotaClassFinal) {
            // Paridade com desktop: `showItemsModal` força `item_vol = 'KG'` ao abrir
            // o modal ([classificacao.js:672](../static/sankhya_integration/classificacao.js#L672)).
            // Sem isso, backend faz CX→KG no CODVOL e deixa CODVOLPARC='CX' (divergência registrada
            // em Mai/2026 — 2026-05-27 — TGFITE NUNOTA 113875 SEQ 1 vs SEQ 2).
            var payload = {
                nunota: parseInt(nunotaClassFinal, 10),
                sequencia: seqEdit,
                codprod: parseInt(codprod, 10),
                qtdneg: totalKg,
                vlrunit: '0',
                vlrtot: '0',
                codvol: 'KG',
                peso: peso,
                obs: '',
                codagregacao: ESTADO.loteAtual.lote,
                geraproducao: 'N',
                codcencus: 10100,
                // Duplicados em maiúsculo (paridade com desktop saveItem)
                NUNOTA: parseInt(nunotaClassFinal, 10),
                SEQUENCIA: seqEdit,
                CODPROD: parseInt(codprod, 10),
                QTDNEG: totalKg,
                VLRUNIT: '0',
                VLRTOT: '0',
                CODVOL: 'KG',
                PESO: peso,
                OBS: '',
                CODAGREGACAO: ESTADO.loteAtual.lote,
                GERAPRODUCAO: 'N',
                CODCENCUS: 10100
            };
            return fetch('/sankhya/item/save/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify(payload)
            }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); });
        };

        var fluxo;
        if (!nunotaClass) {
            // Cria TGFCAB TOP 26 primeiro (paridade com desktop)
            var dtNeg = new Date().toISOString().split('T')[0];
            fluxo = fetch('/sankhya/compras/central/salvar/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({
                    codemp: '10',
                    codparc: String(codparc || '0'),
                    codtipoper: '26',
                    codnat: '20010100',
                    dtneg: dtNeg,
                    nunota_origem: nunotaPortal,
                    numnota: nunotaPortal,
                    codcencus: 10100
                })
            })
                .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
                .then(function (resp) {
                    if (!resp.ok || !resp.body || !resp.body.nunota) {
                        throw new Error((resp.body && resp.body.error) || 'Falha ao criar cabeçalho TOP 26');
                    }
                    return inserirItem(resp.body.nunota);
                });
        } else {
            fluxo = inserirItem(nunotaClass);
        }

        fluxo
            .then(function (resp) {
                if (!resp.ok || !resp.body || !resp.body.ok) {
                    throw new Error((resp.body && resp.body.error) || 'Falha ao salvar item');
                }
                mostrarToast(seqEdit ? 'Alterações salvas ✓' : 'Item salvo ✓', 'success');
                // Captura snapshot do item recém-salvo (pra render como feedback visual)
                var prodVis = $m('m_clss_itemProd').value || '';
                var idxSep = prodVis.indexOf('—');
                var descrAtual = (idxSep >= 0 ? prodVis.slice(idxSep + 1) : prodVis).trim();
                var seqRetornada = (resp.body && (resp.body.sequencia || resp.body.nova_sequencia || resp.body.SEQUENCIA)) || seqEdit || '';
                ESTADO.itemRecemAdicionado = {
                    sequencia: seqRetornada,
                    descr: descrAtual,
                    qtd: totalKg,
                    peso: peso
                };
                // Limpa form e modo edição
                ESTADO.itemEditando = null;
                $m('m_clss_itemProd').value = '';
                $m('m_clss_itemProdHidden').value = '';
                $m('m_clss_itemTotalKg').value = '';
                $m('m_clss_itemTotalCx').value = '';
                $m('m_clss_itemPesoCx').value = '';
                btnAdicionarItem.innerHTML = '<i class="ph ph-plus" aria-hidden="true"></i> Adicionar item';
                return fetch('/sankhya/lote/consultar/?lote=' + encodeURIComponent(ESTADO.loteAtual.lote), {
                    credentials: 'same-origin', headers: { 'Accept': 'application/json' }
                }).then(function (r) { return r.json(); });
            })
            .then(function (j) {
                if (j && j.ok) {
                    ESTADO.dadosLote = j;
                    renderDetalhe(j);     // atualiza tela detalhe atrás do sheet
                    renderSheetItens();   // atualiza lista de itens dentro do sheet
                }
            })
            .catch(function (err) {
                mostrarToast(err && err.message ? err.message : 'Falha ao salvar item', 'error');
            })
            .finally(function () {
                btnAdicionarItem.disabled = false;
                btnAdicionarItem.classList.remove('is-loading');
                var p = $m('m_clss_itemProd');
                if (p) p.focus();
            });
    }

    // Descarte +/- inline na tela detalhe (abaixo do toggle Finalizada).
    // Pede a quantidade via prompt simples. Atualiza resumo + descarte inline + sheet (se aberto).
    function ajustarDescarteInline(op) {
        if (!ESTADO.loteAtual || !ESTADO.dadosLote) return;
        var msg = (op === 'soma') ? 'Adicionar quantos kg de descarte?' : 'Subtrair quantos kg de descarte?';
        var resposta = window.prompt(msg, '');
        if (resposta == null) return;
        var valor = parseBR(resposta);
        if (valor == null || valor <= 0) {
            mostrarToast('Quantidade inválida', 'error'); return;
        }
        chamarUpdateDescarteBackend(op, valor)
            .then(function () {
                mostrarToast('Descarte atualizado ✓', 'success');
                // Re-fetch dados do lote pra atualizar todos os displays
                return fetch('/sankhya/lote/consultar/?lote=' + encodeURIComponent(ESTADO.loteAtual.lote), {
                    credentials: 'same-origin', headers: { 'Accept': 'application/json' }
                }).then(function (r) { return r.json(); });
            })
            .then(function (j) {
                if (j && j.ok) {
                    ESTADO.dadosLote = j;
                    renderDetalhe(j);
                    // Se o sheet de Itens estiver aberto, atualiza a lista também
                    if (sheets.itens && sheets.itens.getAttribute('aria-hidden') === 'false') {
                        renderSheetItens();
                    }
                }
            })
            .catch(function (e) { mostrarToast(e && e.message || 'Falha de rede', 'error'); });
    }
    var btnDescAddDetalhe = $m('m_clss_btnDescarteAddDetalhe');
    var btnDescSubDetalhe = $m('m_clss_btnDescarteSubDetalhe');
    if (btnDescAddDetalhe) btnDescAddDetalhe.addEventListener('click', function () { ajustarDescarteInline('soma'); });
    if (btnDescSubDetalhe) btnDescSubDetalhe.addEventListener('click', function () { ajustarDescarteInline('subtrai'); });

    /* ====================== FABs AZUIS DE ATUALIZAR ====================== */
    // Lista — recarrega a listagem de lotes inteira
    var fabAtualizarLista = $m('m_clss_fabAtualizarLista');
    if (fabAtualizarLista) {
        fabAtualizarLista.addEventListener('click', function () {
            if (fabAtualizarLista.classList.contains('is-loading')) return;
            fabAtualizarLista.classList.add('is-loading');
            carregarLotes();
            // Spinner gira por 600ms mesmo se a chamada terminar antes (feedback visual)
            setTimeout(function () { fabAtualizarLista.classList.remove('is-loading'); }, 600);
        });
    }

    // Detalhe — recarrega só o lote atual (sem voltar pra lista)
    var fabAtualizarLote = $m('m_clss_fabAtualizarLote');
    if (fabAtualizarLote) {
        fabAtualizarLote.addEventListener('click', function () {
            if (!ESTADO.loteAtual) return;
            if (fabAtualizarLote.classList.contains('is-loading')) return;
            fabAtualizarLote.classList.add('is-loading');
            // Re-fetch dos dados do lote sem reset visual
            fetch('/sankhya/lote/consultar/?lote=' + encodeURIComponent(ESTADO.loteAtual.lote), {
                credentials: 'same-origin', headers: { 'Accept': 'application/json' }
            })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    if (j && j.ok) {
                        ESTADO.dadosLote = j;
                        renderDetalhe(j);
                        mostrarToast('Lote atualizado', 'success');
                    } else {
                        mostrarToast(j && j.error || 'Falha ao atualizar lote', 'error');
                    }
                })
                .catch(function () { mostrarToast('Falha de rede', 'error'); })
                .finally(function () { fabAtualizarLote.classList.remove('is-loading'); });
        });
    }

    /* ====================== FILTROS ====================== */
    function syncStatusChips() {
        var cbG = document.querySelector('.classificacao-desktop #filterGreen');
        var cbY = document.querySelector('.classificacao-desktop #filterYellow');
        var cbR = document.querySelector('.classificacao-desktop #filterRed');
        // Defesa: se TODOS os checkboxes desktop estão unchecked (estado anômalo
        // possível quando o template não recebe `params` com status, ou em pós-render
        // antes do JS desktop terminar), preserva o default do HTML mobile (Y+R ativos).
        var algumChecked = (cbG && cbG.checked) || (cbY && cbY.checked) || (cbR && cbR.checked);
        if (!algumChecked) return;
        document.querySelectorAll('.m-status-chip[data-status]').forEach(function (chip) {
            var s = chip.dataset.status;
            var ativo = false;
            if (s === 'VERDE') ativo = cbG && cbG.checked;
            else if (s === 'AMARELO') ativo = cbY && cbY.checked;
            else if (s === 'VERMELHO') ativo = cbR && cbR.checked;
            chip.classList.toggle('is-active', !!ativo);
        });
    }

    document.querySelectorAll('.m-status-chip[data-status]').forEach(function (chip) {
        chip.addEventListener('click', function () {
            chip.classList.toggle('is-active');
            atualizarBadgeFiltros();
        });
    });

    function syncFiltrosDesktopParaMobile() {
        var form = document.querySelector('.classificacao-desktop #filtersForm');
        if (!form) return;
        var v = function (name) {
            var el = form.querySelector('input[name="' + name + '"]');
            return el ? el.value : '';
        };
        if ($m('m_clss_filtroStart')) $m('m_clss_filtroStart').value = v('start');
        if ($m('m_clss_filtroEnd')) $m('m_clss_filtroEnd').value = v('end');
        if ($m('m_clss_filtroPedido')) $m('m_clss_filtroPedido').value = v('nunota_ini');
        if ($m('m_clss_filtroFabricanteHidden')) $m('m_clss_filtroFabricanteHidden').value = v('fabricante');
        if ($m('m_clss_filtroProduto')) {
            var fabVis = document.querySelector('.classificacao-desktop #fabricanteSearch');
            $m('m_clss_filtroProduto').value = (fabVis && fabVis.value) || v('fabricante');
        }
        if ($m('m_clss_filtroCodparcHidden')) $m('m_clss_filtroCodparcHidden').value = v('codparc');
        if ($m('m_clss_filtroParceiro')) {
            var pVis = document.querySelector('.classificacao-desktop #parcSearch');
            $m('m_clss_filtroParceiro').value = (pVis && pVis.value) || v('codparc');
        }
        if ($m('m_clss_filtroLote')) $m('m_clss_filtroLote').value = v('lote');
        syncStatusChips();
    }

    function aplicarFiltros() {
        var form = document.querySelector('.classificacao-desktop #filtersForm');
        if (!form) return;
        var setField = function (name, val) {
            var el = form.querySelector('input[name="' + name + '"]');
            if (el) el.value = val || '';
        };
        setField('start', $m('m_clss_filtroStart').value);
        setField('end', $m('m_clss_filtroEnd').value);
        setField('nunota_ini', $m('m_clss_filtroPedido').value);
        setField('fabricante', $m('m_clss_filtroFabricanteHidden').value || $m('m_clss_filtroProduto').value);
        setField('codparc', $m('m_clss_filtroCodparcHidden').value);
        setField('lote', $m('m_clss_filtroLote').value);

        // Status chips → checkboxes desktop
        var ativos = {};
        document.querySelectorAll('.m-status-chip.is-active').forEach(function (c) { ativos[c.dataset.status] = true; });
        var cbG = document.querySelector('.classificacao-desktop #filterGreen');
        var cbY = document.querySelector('.classificacao-desktop #filterYellow');
        var cbR = document.querySelector('.classificacao-desktop #filterRed');
        if (cbG) cbG.checked = !!ativos['VERDE'];
        if (cbY) cbY.checked = !!ativos['AMARELO'];
        if (cbR) cbR.checked = !!ativos['VERMELHO'];

        closeSheet('filtros');
        atualizarBadgeFiltros();
        carregarLotes();
    }

    /* ====================== BADGE FILTROS ATIVOS NO BOTTOM NAV ====================== */
    // Exibe bolinha vermelha + ícone fill no item Filtros quando algum filtro estiver aplicado
    function temFiltroAtivo() {
        // Datas
        var fim = $m('m_clss_filtroEnd');
        var ini = $m('m_clss_filtroStart');
        if ((ini && ini.value) || (fim && fim.value)) return true;
        // Outros campos
        var nomes = ['m_clss_filtroPedido', 'm_clss_filtroProduto', 'm_clss_filtroParceiro', 'm_clss_filtroLote'];
        for (var i = 0; i < nomes.length; i++) {
            var el = $m(nomes[i]);
            if (el && el.value && String(el.value).trim() !== '') return true;
        }
        // Status chips: default é AMARELO + VERMELHO ativos.
        // Se a combinação atual difere do default, considera filtro ativo.
        var chipG = document.querySelector('.m-status-chip[data-status="VERDE"]');
        var chipY = document.querySelector('.m-status-chip[data-status="AMARELO"]');
        var chipR = document.querySelector('.m-status-chip[data-status="VERMELHO"]');
        var gAtivo = chipG && chipG.classList.contains('is-active');
        var yAtivo = chipY && chipY.classList.contains('is-active');
        var rAtivo = chipR && chipR.classList.contains('is-active');
        // Default: G=false, Y=true, R=true. Qualquer divergência = filtro ativo
        if (!!gAtivo !== false || !!yAtivo !== true || !!rAtivo !== true) return true;
        return false;
    }
    function atualizarBadgeFiltros() {
        var navBtn = document.querySelector('.classificacao-mobile .m-bottom-nav__item[data-nav="filtros"]');
        if (!navBtn) return;
        navBtn.classList.toggle('has-filtros-ativos', temFiltroAtivo());
    }

    function limparFiltros() {
        ['m_clss_filtroStart', 'm_clss_filtroEnd', 'm_clss_filtroPedido',
         'm_clss_filtroFabricanteHidden', 'm_clss_filtroProduto',
         'm_clss_filtroCodparcHidden', 'm_clss_filtroParceiro',
         'm_clss_filtroLote'].forEach(function (id) {
            var el = $m(id); if (el) el.value = '';
        });
        // Status defaults: AMARELO + VERMELHO
        document.querySelectorAll('.m-status-chip[data-status]').forEach(function (chip) {
            chip.classList.toggle('is-active', chip.dataset.status !== 'VERDE');
        });
        var form = document.querySelector('.classificacao-desktop #filtersForm');
        if (form) {
            ['start', 'end', 'nunota_ini', 'fabricante', 'codparc', 'lote'].forEach(function (n) {
                var el = form.querySelector('input[name="' + n + '"]'); if (el) el.value = '';
            });
        }
        var cbG = document.querySelector('.classificacao-desktop #filterGreen');
        var cbY = document.querySelector('.classificacao-desktop #filterYellow');
        var cbR = document.querySelector('.classificacao-desktop #filterRed');
        if (cbG) cbG.checked = false;
        if (cbY) cbY.checked = true;
        if (cbR) cbR.checked = true;
        closeSheet('filtros');
        atualizarBadgeFiltros();
        carregarLotes();
    }

    /* ====================== iOS Safari: replicar data inicial → data final SEMPRE ====================== */
    // iPhone só dispara `change` quando picker fecha. Replicar sempre (sem comparar) + listener `input`.
    function setupDateReplica() {
        var inputIni = $m('m_clss_filtroStart');
        var inputFim = $m('m_clss_filtroEnd');
        if (!inputIni || !inputFim) return;
        var replicar = function (e) {
            var v = (e && e.target ? e.target.value : inputIni.value) || '';
            if (v) inputFim.value = v;
        };
        inputIni.addEventListener('change', replicar);
        inputIni.addEventListener('input', replicar);
    }

    function shiftFiltroDia(delta) {
        var ini = $m('m_clss_filtroStart');
        if (!ini) return;
        var d = ini.value ? new Date(ini.value + 'T12:00:00') : new Date();
        if (isNaN(d.getTime())) d = new Date();
        d.setDate(d.getDate() + delta);
        var iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
        ini.value = iso;
        var fim = $m('m_clss_filtroEnd'); if (fim) fim.value = iso;
    }

    if ($m('m_clss_btnPrevDay')) $m('m_clss_btnPrevDay').addEventListener('click', function () { shiftFiltroDia(-1); });
    if ($m('m_clss_btnNextDay')) $m('m_clss_btnNextDay').addEventListener('click', function () { shiftFiltroDia(1); });
    if ($m('m_clss_btnAplicarFiltros')) $m('m_clss_btnAplicarFiltros').addEventListener('click', aplicarFiltros);
    if ($m('m_clss_btnLimparFiltros')) $m('m_clss_btnLimparFiltros').addEventListener('click', limparFiltros);

    // Typeaheads (Produto via fabricante + Parceiro)
    function setupTypeahead(opts) {
        var input = $m(opts.inputId);
        var hidden = $m(opts.hiddenId);
        var dd = $m(opts.dropdownId);
        if (!input || !dd) return;
        var timer = null, items = [];
        function close() { dd.hidden = true; dd.innerHTML = ''; items = []; }
        function render(results) {
            items = results || [];
            if (!items.length) {
                dd.innerHTML = '<div class="m-dropdown-empty">Nada encontrado</div>'; dd.hidden = false; return;
            }
            dd.innerHTML = items.map(function (it, idx) {
                return '<div class="m-dropdown-item" data-idx="' + idx + '">' + escapeHtml(opts.label(it)) + '</div>';
            }).join('');
            dd.hidden = false;
        }
        function pick(it) {
            if (hidden) hidden.value = opts.pickHidden(it);
            input.value = opts.pickVisible(it);
            close();
        }
        input.addEventListener('input', function () {
            clearTimeout(timer);
            var q = input.value.trim();
            if (!q) { if (hidden) hidden.value = ''; close(); return; }
            timer = setTimeout(function () {
                var url = opts.url + (opts.url.indexOf('?') >= 0 ? '&' : '?') + 'q=' + encodeURIComponent(q);
                fetch(url, { credentials: 'same-origin' })
                    .then(function (r) { return r.json(); })
                    .then(function (j) {
                        var arr = j && (j.results || j.items || j) || [];
                        if (!Array.isArray(arr)) arr = [];
                        render(arr.slice(0, 15));
                    })
                    .catch(close);
            }, 280);
        });
        input.addEventListener('blur', function () { setTimeout(close, 200); });
        dd.addEventListener('mousedown', function (e) {
            var item = e.target.closest('.m-dropdown-item'); if (!item) return;
            e.preventDefault();
            var idx = parseInt(item.dataset.idx, 10);
            if (!isNaN(idx) && items[idx]) pick(items[idx]);
        });
        dd.addEventListener('touchstart', function (e) {
            var item = e.target.closest('.m-dropdown-item'); if (!item) return;
            var idx = parseInt(item.dataset.idx, 10);
            if (!isNaN(idx) && items[idx]) pick(items[idx]);
        }, { passive: true });
    }

    setupTypeahead({
        inputId: 'm_clss_filtroProduto', hiddenId: 'm_clss_filtroFabricanteHidden',
        dropdownId: 'm_clss_filtroProdutoDropdown',
        url: '/sankhya/produtos/search/?fabricante=1&limit=15',
        label: function (it) { return (it.fabricante || it.descr || '').trim(); },
        pickHidden: function (it) { return (it.fabricante || it.descr || '').trim(); },
        pickVisible: function (it) { return (it.fabricante || it.descr || '').trim(); }
    });
    setupTypeahead({
        inputId: 'm_clss_filtroParceiro', hiddenId: 'm_clss_filtroCodparcHidden',
        dropdownId: 'm_clss_filtroParceiroDropdown',
        url: '/sankhya/parceiros/search/?limit=15',
        label: function (it) {
            var cod = it.codparc || it.cod || ''; var nome = it.nomeparc || it.descr || '';
            return cod ? (cod + ' — ' + nome) : nome;
        },
        pickHidden: function (it) { return String(it.codparc || it.cod || ''); },
        pickVisible: function (it) {
            var cod = it.codparc || it.cod || ''; var nome = it.nomeparc || it.descr || '';
            return cod ? (cod + ' — ' + nome) : nome;
        }
    });

    /* ====================== SEARCH BAR client-side (filtra cards JÁ carregados) ====================== */
    // Operador digita produto/parceiro/lote → esconde cards que não dão match.
    // É client-side porque o filtro padrão do server (status AMARELO/VERMELHO) já trava o universo.
    // Debounce 250ms (mesmo padrão da Entrada).
    var searchInput = $m('m_clss_search');
    if (searchInput) {
        var t;
        searchInput.addEventListener('input', function () {
            clearTimeout(t);
            t = setTimeout(filtrarLotes, 250);
        });
    }
    function normaliz(s) {
        // toLowerCase + remove acentos (NFD + cortar marks)
        return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    }
    function filtrarLotes() {
        if (!searchInput) return;
        var q = normaliz(searchInput.value);
        document.querySelectorAll('#m_clss_lotesList .m-card-nota').forEach(function (card) {
            var alvo = normaliz((card.dataset.parc || '') + ' ' + (card.dataset.prod || '') + ' ' + (card.dataset.lote || ''));
            card.style.display = (!q || alvo.indexOf(q) >= 0) ? '' : 'none';
        });
    }

    /* ====================== SWIPE-TO-BACK ====================== */
    function setupSwipeToBack() {
        var DISMISS_PCT = 0.35, VELOCITY_THRESHOLD = 0.5;
        Object.keys(screens).forEach(function (name) {
            if (name === 'lista') return;
            var screen = screens[name];
            var startX = 0, startY = 0, startT = 0, lastX = 0;
            var tracking = false, canceled = false, width = 1;

            screen.addEventListener('touchstart', function (e) {
                if (e.touches.length !== 1) { canceled = true; return; }
                if (screen !== screens[stack[stack.length - 1]]) return;
                var t = e.touches[0];
                startX = lastX = t.clientX; startY = t.clientY;
                startT = Date.now();
                width = window.innerWidth || document.documentElement.clientWidth;
                tracking = false; canceled = false;
            }, { passive: true });

            screen.addEventListener('touchmove', function (e) {
                if (canceled) return;
                var t = e.touches[0];
                var dx = t.clientX - startX, dy = t.clientY - startY;
                if (!tracking) {
                    if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
                    if (Math.abs(dy) > Math.abs(dx)) { canceled = true; return; }
                    if (dx < 0) { canceled = true; return; }
                    tracking = true;
                    screen.style.transition = 'none'; screen.style.willChange = 'transform';
                }
                lastX = t.clientX;
                var translate = dx;
                if (translate > width * 0.8) translate = width * 0.8 + (translate - width * 0.8) * 0.3;
                screen.style.transform = 'translateX(' + Math.max(0, translate) + 'px)';
            }, { passive: true });

            screen.addEventListener('touchend', function () {
                if (canceled || !tracking) { canceled = false; tracking = false; return; }
                var dx = lastX - startX, dt = Date.now() - startT;
                var velocity = dt > 0 ? dx / dt : 0;
                screen.style.transition = ''; screen.style.willChange = '';
                if (dx > width * DISMISS_PCT || velocity > VELOCITY_THRESHOLD) {
                    screen.style.transform = 'translateX(100%)';
                    setTimeout(function () { popScreen(); screen.style.transform = ''; }, 280);
                } else {
                    screen.style.transform = '';
                }
                tracking = false;
            }, { passive: true });

            screen.addEventListener('touchcancel', function () {
                screen.style.transition = ''; screen.style.transform = ''; screen.style.willChange = '';
                tracking = false; canceled = false;
            }, { passive: true });
        });
    }

    /* ====================== BOOT ====================== */
    setActiveScreen('lista');
    setupSwipeToBack();
    setupDateReplica();
    syncFiltrosDesktopParaMobile();
    atualizarBadgeFiltros();
    carregarLotes();
})();
