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
    };

    /* ====================== NAVEGAÇÃO ====================== */
    var screens = {};
    mob.querySelectorAll('.m-screen').forEach(function (el) {
        screens[el.dataset.screen] = el;
    });
    var stack = ['lista'];

    function setActiveScreen(name) {
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
    function openSheet(name) { var s = sheets[name]; if (s) s.setAttribute('aria-hidden', 'false'); }
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
    function carregarLotes() {
        var listaEl = $m('m_clss_lotesList');
        if (!listaEl) return;

        // Lê filtros do form desktop pra incluir como query params
        var form = document.querySelector('.classificacao-desktop #filtersForm');
        var params = new URLSearchParams();
        if (form) {
            var fStart = form.querySelector('input[name="start"]');
            var fEnd = form.querySelector('input[name="end"]');
            var fPed = form.querySelector('input[name="nunota_ini"]');
            var fFab = form.querySelector('input[name="fabricante"]');
            var fParc = form.querySelector('input[name="codparc"]');
            var fLote = form.querySelector('input[name="lote"]');
            if (fStart && fStart.value) params.set('date_start', fStart.value);
            if (fEnd && fEnd.value) params.set('date_end', fEnd.value);
            if (fPed && fPed.value) params.set('nunota_ini', fPed.value);
            if (fFab && fFab.value) params.set('fabricante', fFab.value);
            if (fParc && fParc.value) params.set('codparc', fParc.value);
            if (fLote && fLote.value) params.set('lote', fLote.value);
        }

        // Status: lê checkboxes do desktop (verde/amarelo/vermelho)
        var status = [];
        var cbG = document.querySelector('.classificacao-desktop #filterGreen');
        var cbY = document.querySelector('.classificacao-desktop #filterYellow');
        var cbR = document.querySelector('.classificacao-desktop #filterRed');
        if (cbG && cbG.checked) status.push('VERDE');
        if (cbY && cbY.checked) status.push('AMARELO');
        if (cbR && cbR.checked) status.push('VERMELHO');
        status.forEach(function (s) { params.append('status', s); });

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

        $m('m_clss_detalheLote').textContent = 'Lote ' + meta.lote;
        $m('m_clss_detalheMeta').textContent = 'Carregando…';

        // Reset visual
        $m('m_clss_fornecedor').textContent = meta.parc || '—';
        $m('m_clss_produto').textContent = meta.prod || '—';
        $m('m_clss_pedidoData').textContent = meta.nunota_origem ? ('Pedido ' + meta.nunota_origem) : '—';

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
        $m('m_clss_pedidoData').textContent = (entrada.nunota ? ('Pedido ' + entrada.nunota) : '—') + ' · ' + (entrada.dtneg || '');

        var inNatura = parseFloat(entrada.qtd || 0);
        var classKg = parseFloat(j.qtd_class_kg || 0);
        var descarte = parseFloat(j.qtd_descarte_kg || (j.agregados && j.agregados.descarte) || 0);
        var estoque = parseFloat(j.qtd_estoque_kg || (inNatura - classKg - descarte));

        $m('m_clss_resInNatura').textContent = fmtBr1(inNatura);
        $m('m_clss_resClassificado').textContent = fmtBr1(classKg);
        $m('m_clss_resDescarte').textContent = fmtBr1(descarte);
        $m('m_clss_resEstoque').textContent = fmtBr1(Math.max(0, estoque));

        var pct = function (v) { return inNatura > 0 ? Math.round((v / inNatura) * 100) + '%' : '0%'; };
        $m('m_clss_resClassificadoPct').textContent = pct(classKg);
        $m('m_clss_resDescartePct').textContent = pct(descarte);
        $m('m_clss_resEstoquePct').textContent = pct(Math.max(0, estoque));

        $m('m_clss_detalheMeta').textContent = entrada.parceiro ? entrada.parceiro.substring(0, 32) : '—';

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
        var html = items.map(function (it) {
            return '<article class="m-clss-class-card">' +
                '<div class="m-clss-class-card__head">' +
                    '<div class="m-clss-class-card__produto">' + escapeHtml(it.descr || '') + '</div>' +
                    '<div class="m-clss-class-card__meta">Seq ' + escapeHtml(it.sequencia) +
                    (it.peso ? (' · ' + fmtBr(it.peso) + ' kg/cx') : '') + '</div>' +
                '</div>' +
                '<div class="m-clss-class-card__qtd">' +
                    fmtBr(it.qtd) + ' kg' +
                    (it.peso ? '<small>' + fmtBr(Math.ceil((it.qtd || 0) / it.peso)) + ' cx</small>' : '') +
                '</div>' +
            '</article>';
        }).join('');
        listaCl.innerHTML = html;
    }

    /* ====================== TOGGLE FINALIZADA ====================== */
    var toggleStatus = $m('m_clss_toggleStatus');
    if (toggleStatus) {
        toggleStatus.addEventListener('change', function () {
            if (!ESTADO.dadosLote || !ESTADO.dadosLote.nunota_class) {
                mostrarToast('Lote ainda não tem classificação criada.', 'error');
                toggleStatus.checked = !toggleStatus.checked;
                return;
            }
            var nunota = ESTADO.dadosLote.nunota_class;
            var novoStatus = toggleStatus.checked ? 'N' : 'S';
            fetch('/sankhya/item/toggle_status/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({ nunota: nunota, status: novoStatus })
            })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    if (j && j.ok) {
                        mostrarToast(novoStatus === 'N' ? 'Classificação finalizada ✓' : 'Reaberta', 'success');
                        ESTADO.dadosLote.status_pendente = novoStatus;
                    } else {
                        mostrarToast(j && j.error || 'Falha ao mudar status', 'error');
                        toggleStatus.checked = !toggleStatus.checked;
                    }
                })
                .catch(function () {
                    mostrarToast('Falha de rede', 'error');
                    toggleStatus.checked = !toggleStatus.checked;
                });
        });
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

    var btnDescarteConf = $m('m_clss_btnDescarteConfirmar');
    if (btnDescarteConf) {
        btnDescarteConf.addEventListener('click', function () {
            if (!ESTADO.loteAtual || !ESTADO.dadosLote) return;
            var valor = parseBR($m('m_clss_descarteValor').value);
            if (valor == null || valor <= 0) {
                mostrarToast('Informe a quantidade.', 'error');
                return;
            }
            var atual = parseFloat(ESTADO.dadosLote.qtd_descarte_kg || (ESTADO.dadosLote.agregados && ESTADO.dadosLote.agregados.descarte) || 0);
            var novoTotal = ESTADO.descarteOp === 'add' ? atual + valor : Math.max(0, atual - valor);

            fetch('/sankhya/item/update_descarte_lote/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({ lote: ESTADO.loteAtual.lote, qtd_avaria: novoTotal })
            })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    if (j && j.ok) {
                        mostrarToast('Descarte atualizado ✓', 'success');
                        closeSheet('descarte');
                        // Re-fetch detalhes pra atualizar resumo
                        abrirDetalheLote(ESTADO.loteAtual);
                    } else {
                        mostrarToast(j && j.error || 'Falha ao atualizar descarte', 'error');
                    }
                })
                .catch(function () { mostrarToast('Falha de rede', 'error'); });
        });
    }

    /* ====================== FAB ADICIONAR CLASSIFICAÇÃO ====================== */
    var fabAdd = $m('m_clss_fabAdd');
    if (fabAdd) {
        fabAdd.addEventListener('click', function () {
            if (!ESTADO.loteAtual) return;
            // Redireciona pro editor desktop com o lote selecionado
            window.location.href = '/sankhya/compras/classificacao/?lote=' + encodeURIComponent(ESTADO.loteAtual.lote) + '&open=items&sel=' + encodeURIComponent(ESTADO.loteAtual.lote);
        });
    }

    /* ====================== FILTROS ====================== */
    function syncStatusChips() {
        var cbG = document.querySelector('.classificacao-desktop #filterGreen');
        var cbY = document.querySelector('.classificacao-desktop #filterYellow');
        var cbR = document.querySelector('.classificacao-desktop #filterRed');
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
        carregarLotes();
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
        carregarLotes();
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

    /* ====================== SEARCH BAR client-side ====================== */
    var searchInput = $m('m_clss_search');
    if (searchInput) {
        var t;
        searchInput.addEventListener('input', function () {
            clearTimeout(t);
            t = setTimeout(filtrarLotes, 220);
        });
    }
    function normaliz(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
    function filtrarLotes() {
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
    syncFiltrosDesktopParaMobile();
    carregarLotes();
})();
