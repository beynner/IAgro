/* =============================================================================
 * Rastreio — versão Mobile (Mai/2026 — 2026-05-27)
 *
 * App-like dual container. Só ativa em viewport ≤900px. Desktop preservado.
 *
 * Estrutura:
 *   - Tela `lista`: toggle Lotes ⇄ Pedidos + busca + barra do lote armado
 *   - Tela `detalheLote`: hero + ações + lista de pedidos/vendas usando o lote
 *   - Tela `detalhePedido`: hero + lista de produtos com qtd vinculada/falta
 *
 * Bottom sheets:
 *   - Filtros (datas Lotes/Pedidos + agrupamento + Pendente/Finalizado)
 *   - Vincular (qtd + peso opc)
 *   - Escolha de peso (etiqueta com 2+ pesos na TOP 26)
 *
 * Reusa endpoints do desktop. Zero novo endpoint.
 * ============================================================================= */
(function () {
    'use strict';

    if (!window.matchMedia('(max-width: 900px)').matches) return;

    // ===== Config =====
    const URLS = {
        lotes:           '/sankhya/rastreio/api/lotes-disponiveis/',
        pedidos:         '/sankhya/rastreio/api/pedidos-abertos/',
        atribuirLote:    '/sankhya/rastreio/api/atribuir-lote/',
        desvincularLote: '/sankhya/rastreio/api/desvincular-lote/',
        loteVinculos:    '/sankhya/rastreio/api/lote-vinculos/',
        zerarFracao:    '/sankhya/rastreio/api/zerar-fracao/',
        refreshSaldo:   '/sankhya/rastreio/api/refresh-saldo/',
        etiqueta:       '/sankhya/rastreio/api/etiqueta-pdf/',
        resolverPeso:   '/sankhya/rastreio/api/resolver-peso/',
        vinculoResolver: '/sankhya/rastreio/api/vinculo/resolver/',
    };

    const PAGE_SIZE        = 100;
    const DIAS_ALERTA_LOTE = 60;

    // ===== Estado =====
    const ESTADO = {
        listaAtiva: 'lotes',       // 'lotes' | 'pedidos'
        lotesData: [],
        pedidosData: [],           // linhas brutas TGFITE
        loteArmado: null,
        loteSelecionado: null,     // pra tela detalheLote
        pedidoSelecionado: null,   // pra tela detalhePedido (NUNOTA)
        produtoSelecionado: null,  // pra abrir sheet "vincular"
        agrupamentoLotes: 'produto',
        agrupamentoPedidos: 'produto',
        mostrarPendentes: true,
        mostrarFinalizados: false,
        dataIniLotes: '',
        dataFimLotes: '',
        dataIniPedidos: '',
        dataFimPedidos: '',
        textoBusca: '',
        carregandoLotes: false,
        carregandoPedidos: false,
        loteEscolhaPesoOverrides: null,
        // Grupos colapsados — default: TODOS colapsados ao 1º render.
        // gruposJaVistosLotes garante que isso só acontece na primeira
        // aparição (refresh subsequente preserva escolha do operador).
        gruposLotesColapsados: new Set(),
        gruposLotesJaVistos: new Set(),
        gruposPedidosColapsados: new Set(),
        gruposPedidosJaVistos: new Set(),
    };

    const screens = {
        lista: document.querySelector('.rastreio-mobile .m-screen--lista'),
        detalheLote: document.querySelector('.rastreio-mobile .m-screen--detalhe-lote'),
        detalhePedido: document.querySelector('.rastreio-mobile .m-screen--detalhe-pedido'),
    };
    if (!screens.lista) return;   // mobile container ausente — guard

    let telaAtiva = 'lista';
    const historyStack = ['lista'];

    // ===== Helpers =====
    function $m(id) { return document.getElementById(id); }
    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replaceAll('&', '&amp;').replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
    }
    function fmtQtd(v) {
        // Sem casas decimais (operador trabalha com kg inteiros na Agromil).
        return Math.round(Number(v) || 0).toLocaleString('pt-BR');
    }
    function fmtInt(v) { return Number(v || 0).toLocaleString('pt-BR'); }
    // Reduz "25/05/2026" → "25/05" (sem ano). Tolerante a entrada vazia.
    function fmtDataCurta(brDate) {
        if (!brDate) return '';
        const partes = String(brDate).split('/');
        return partes.length >= 2 ? `${partes[0]}/${partes[1]}` : String(brDate);
    }
    function getCsrf() {
        if (window.IAgro && IAgro.getCookie) return IAgro.getCookie('csrftoken');
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }
    function mostrarToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) IAgro.showToast(msg, tipo || 'info');
        else alert(msg);
    }
    async function postJSON(url, data) {
        if (window.IAgro && IAgro.postJSON) return IAgro.postJSON(url, data);
        const csrf = getCsrf();
        const r = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify(data || {}),
        });
        const body = await r.json().catch(() => ({}));
        return { ok: r.ok, status: r.status, body };
    }
    function debounce(fn, ms) {
        let t = null;
        return function () {
            const args = arguments;
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }
    function _hojeIso() {
        const d = new Date();
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${dd}`;
    }
    function _shiftIso(iso, delta) {
        if (!iso) return _hojeIso();
        const [y, m, d] = iso.split('-').map(Number);
        const dt = new Date(y, m - 1, d);
        dt.setDate(dt.getDate() + delta);
        const yy = dt.getFullYear();
        const mm = String(dt.getMonth() + 1).padStart(2, '0');
        const dd = String(dt.getDate()).padStart(2, '0');
        return `${yy}-${mm}-${dd}`;
    }
    function _ha7Dias() {
        return _shiftIso(_hojeIso(), -7);
    }
    function _idadeDiasFromBR(dataBR) {
        if (!dataBR) return 0;
        try {
            const [d, m, y] = dataBR.split('/').map(Number);
            if (!d || !m || !y) return 0;
            const dt = new Date(y, m - 1, d);
            return Math.floor((Date.now() - dt.getTime()) / 86400000);
        } catch (_) { return 0; }
    }

    // ===== Navegação stack =====
    function setActiveScreen(name) {
        // Fecha swipes pendentes — evita estado "preso" entre navegações
        // (padrão obrigatório documentado em conventions.md)
        if (typeof fecharTodosSwipesLotes === 'function') fecharTodosSwipesLotes();
        if (typeof fecharTodosSwipesPedidos === 'function') fecharTodosSwipesPedidos();
        if (typeof fecharTodosSwipesItens === 'function') fecharTodosSwipesItens();
        Object.entries(screens).forEach(([key, el]) => {
            if (!el) return;
            el.classList.toggle('is-active', key === name);
        });
        telaAtiva = name;
    }
    function pushScreen(name) {
        historyStack.push(name);
        setActiveScreen(name);
        try { history.pushState({ screen: name }, '', '#' + name); } catch (_) {}
    }
    function popScreen() {
        historyStack.pop();
        const prev = historyStack[historyStack.length - 1] || 'lista';
        setActiveScreen(prev);
    }
    function popToRoot() {
        historyStack.length = 0;
        historyStack.push('lista');
        setActiveScreen('lista');
    }

    window.addEventListener('popstate', () => {
        if (telaAtiva !== 'lista') popScreen();
    });

    // Swipe-to-back
    function setupSwipeToBack() {
        Object.entries(screens).forEach(([nome, el]) => {
            if (!el || nome === 'lista') return;
            let startX = 0, startY = 0, t0 = 0, ativo = false, eixoH = false;
            el.addEventListener('touchstart', (e) => {
                if (e.touches.length !== 1) return;
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                t0 = Date.now();
                ativo = true;
                eixoH = false;
            }, { passive: true });
            el.addEventListener('touchmove', (e) => {
                if (!ativo || e.touches.length !== 1) return;
                const dx = e.touches[0].clientX - startX;
                const dy = e.touches[0].clientY - startY;
                if (!eixoH && Math.abs(dx) + Math.abs(dy) < 10) return;
                if (!eixoH) {
                    if (Math.abs(dy) > Math.abs(dx)) {
                        ativo = false;
                        return;
                    }
                    eixoH = true;
                }
            }, { passive: true });
            el.addEventListener('touchend', (e) => {
                if (!ativo) return;
                ativo = false;
                if (!eixoH) return;
                const dx = e.changedTouches[0].clientX - startX;
                const dt = Date.now() - t0;
                const v = dx / Math.max(dt, 1);
                const thr = el.clientWidth * 0.35;
                if (dx > thr || v > 0.5) popScreen();
            }, { passive: true });
        });
    }

    // ===== Bottom sheets =====
    function openSheet(name) {
        // Fecha swipes pendentes ao abrir qualquer sheet
        if (typeof fecharTodosSwipesLotes === 'function') fecharTodosSwipesLotes();
        if (typeof fecharTodosSwipesPedidos === 'function') fecharTodosSwipesPedidos();
        if (typeof fecharTodosSwipesItens === 'function') fecharTodosSwipesItens();
        const sheet = document.querySelector(`.rastreio-mobile .m-sheet[data-sheet="${name}"]`);
        if (!sheet) return;
        sheet.setAttribute('aria-hidden', 'false');
    }
    function closeSheet(name) {
        const sheet = name
            ? document.querySelector(`.rastreio-mobile .m-sheet[data-sheet="${name}"]`)
            : null;
        if (sheet) {
            sheet.setAttribute('aria-hidden', 'true');
        } else {
            document.querySelectorAll('.rastreio-mobile .m-sheet').forEach(s => {
                s.setAttribute('aria-hidden', 'true');
            });
        }
    }
    function setupSheetClosers() {
        document.querySelectorAll('.rastreio-mobile [data-close-sheet]').forEach(el => {
            el.addEventListener('click', () => {
                const sheet = el.closest('.m-sheet');
                if (sheet) sheet.setAttribute('aria-hidden', 'true');
            });
        });
    }

    // ===== Filtros (Sheet) =====
    function inicializarFiltrosDefault() {
        const ini = _ha7Dias();
        const fim = _hojeIso();
        ESTADO.dataIniLotes = ini;
        ESTADO.dataFimLotes = fim;
        ESTADO.dataIniPedidos = ini;
        ESTADO.dataFimPedidos = fim;
        const iL = $m('m_ras_dataIniLotes');
        const fL = $m('m_ras_dataFimLotes');
        const iP = $m('m_ras_dataIniPedidos');
        const fP = $m('m_ras_dataFimPedidos');
        if (iL) iL.value = ini;
        if (fL) fL.value = fim;
        if (iP) iP.value = ini;
        if (fP) fP.value = fim;
    }
    function bindFiltrosSheet() {
        // Status chips (Pendente / Finalizado)
        document.querySelectorAll('.rastreio-mobile .m-status-chip[data-status]').forEach(chip => {
            chip.addEventListener('click', () => {
                const tipo = chip.dataset.status;
                if (tipo === 'pendente') {
                    ESTADO.mostrarPendentes = !ESTADO.mostrarPendentes;
                    chip.classList.toggle('is-on', ESTADO.mostrarPendentes);
                } else if (tipo === 'finalizado') {
                    ESTADO.mostrarFinalizados = !ESTADO.mostrarFinalizados;
                    chip.classList.toggle('is-on', ESTADO.mostrarFinalizados);
                }
                // Pelo menos 1 ligado
                if (!ESTADO.mostrarPendentes && !ESTADO.mostrarFinalizados) {
                    ESTADO.mostrarPendentes = true;
                    const cp = document.querySelector('.rastreio-mobile .m-status-chip[data-status="pendente"]');
                    if (cp) cp.classList.add('is-on');
                    mostrarToast('Pelo menos um status precisa estar ligado.', 'warning');
                }
            });
        });

        // Toggle agrupamento Lotes
        document.querySelectorAll('.rastreio-mobile .m-toggle-btn[data-grp-lotes]').forEach(btn => {
            btn.addEventListener('click', () => {
                const val = btn.dataset.grpLotes;
                ESTADO.agrupamentoLotes = val;
                document.querySelectorAll('.rastreio-mobile .m-toggle-btn[data-grp-lotes]').forEach(b => {
                    b.classList.toggle('is-active', b.dataset.grpLotes === val);
                });
            });
        });

        // Toggle agrupamento Pedidos
        document.querySelectorAll('.rastreio-mobile .m-toggle-btn[data-grp-pedidos]').forEach(btn => {
            btn.addEventListener('click', () => {
                const val = btn.dataset.grpPedidos;
                ESTADO.agrupamentoPedidos = val;
                document.querySelectorAll('.rastreio-mobile .m-toggle-btn[data-grp-pedidos]').forEach(b => {
                    b.classList.toggle('is-active', b.dataset.grpPedidos === val);
                });
            });
        });

        // Data shift (<<, >>)
        document.querySelectorAll('.rastreio-mobile .m-date-shift').forEach(btn => {
            btn.addEventListener('click', () => {
                const delta = parseInt(btn.dataset.shift, 10) || 0;
                const target = btn.dataset.target;
                if (target === 'lotes') {
                    const novo = _shiftIso(ESTADO.dataIniLotes || _hojeIso(), delta);
                    ESTADO.dataIniLotes = novo;
                    ESTADO.dataFimLotes = novo;
                    if ($m('m_ras_dataIniLotes')) $m('m_ras_dataIniLotes').value = novo;
                    if ($m('m_ras_dataFimLotes')) $m('m_ras_dataFimLotes').value = novo;
                } else {
                    const novo = _shiftIso(ESTADO.dataIniPedidos || _hojeIso(), delta);
                    ESTADO.dataIniPedidos = novo;
                    ESTADO.dataFimPedidos = novo;
                    if ($m('m_ras_dataIniPedidos')) $m('m_ras_dataIniPedidos').value = novo;
                    if ($m('m_ras_dataFimPedidos')) $m('m_ras_dataFimPedidos').value = novo;
                }
            });
        });

        // Date replica (Lotes)
        const iniL = $m('m_ras_dataIniLotes');
        const fimL = $m('m_ras_dataFimLotes');
        if (iniL && fimL) {
            const replicar = (e) => {
                const v = (e && e.target ? e.target.value : iniL.value) || '';
                if (v) fimL.value = v;
                ESTADO.dataIniLotes = iniL.value;
                ESTADO.dataFimLotes = fimL.value;
            };
            iniL.addEventListener('change', replicar);
            iniL.addEventListener('input', replicar);
            fimL.addEventListener('change', () => { ESTADO.dataFimLotes = fimL.value; });
        }
        // Date replica (Pedidos)
        const iniP = $m('m_ras_dataIniPedidos');
        const fimP = $m('m_ras_dataFimPedidos');
        if (iniP && fimP) {
            const replicar = (e) => {
                const v = (e && e.target ? e.target.value : iniP.value) || '';
                if (v) fimP.value = v;
                ESTADO.dataIniPedidos = iniP.value;
                ESTADO.dataFimPedidos = fimP.value;
            };
            iniP.addEventListener('change', replicar);
            iniP.addEventListener('input', replicar);
            fimP.addEventListener('change', () => { ESTADO.dataFimPedidos = fimP.value; });
        }

        // Aplicar / Limpar
        const btnApl = $m('m_ras_filtrosAplicar');
        if (btnApl) btnApl.addEventListener('click', () => {
            closeSheet('filtros');
            carregarAtual();
            atualizarBadgeFiltros();
        });
        const btnLimp = $m('m_ras_filtrosLimpar');
        if (btnLimp) btnLimp.addEventListener('click', () => {
            inicializarFiltrosDefault();
            ESTADO.mostrarPendentes = true;
            ESTADO.mostrarFinalizados = false;
            ESTADO.agrupamentoLotes = 'produto';
            ESTADO.agrupamentoPedidos = 'produto';
            // Reset de colapso — grupos voltam a ser tratados como "novos"
            // e serão colapsados na próxima renderização (default).
            ESTADO.gruposLotesColapsados.clear();
            ESTADO.gruposLotesJaVistos.clear();
            ESTADO.gruposPedidosColapsados.clear();
            ESTADO.gruposPedidosJaVistos.clear();
            document.querySelectorAll('.rastreio-mobile .m-status-chip').forEach(c => {
                const on = (c.dataset.status === 'pendente');
                c.classList.toggle('is-on', on);
            });
            document.querySelectorAll('.rastreio-mobile .m-toggle-btn[data-grp-lotes]').forEach(b => {
                b.classList.toggle('is-active', b.dataset.grpLotes === 'produto');
            });
            document.querySelectorAll('.rastreio-mobile .m-toggle-btn[data-grp-pedidos]').forEach(b => {
                b.classList.toggle('is-active', b.dataset.grpPedidos === 'produto');
            });
            closeSheet('filtros');
            carregarAtual();
            atualizarBadgeFiltros();
        });
    }

    // ===== Bottom nav =====
    function bindBottomNav() {
        document.querySelectorAll('.rastreio-mobile .m-bottom-nav__item').forEach(btn => {
            btn.addEventListener('click', () => {
                const nav = btn.dataset.nav;
                if (nav === 'lista') {
                    if (telaAtiva !== 'lista') popToRoot();
                } else if (nav === 'buscar') {
                    if (telaAtiva !== 'lista') popToRoot();
                    setTimeout(() => $m('m_ras_search')?.focus(), 80);
                } else if (nav === 'filtros') {
                    openSheet('filtros');
                } else if (nav === 'mais') {
                    refrescarSaldoEManter();
                }
            });
        });
    }

    function temFiltroAtivo() {
        const hoje = _hojeIso();
        const ha7 = _ha7Dias();
        const datasDefault = (ESTADO.dataIniLotes === ha7 && ESTADO.dataFimLotes === hoje
            && ESTADO.dataIniPedidos === ha7 && ESTADO.dataFimPedidos === hoje);
        const statusDefault = (ESTADO.mostrarPendentes && !ESTADO.mostrarFinalizados);
        const grpDefault = (ESTADO.agrupamentoLotes === 'produto' && ESTADO.agrupamentoPedidos === 'produto');
        return !(datasDefault && statusDefault && grpDefault);
    }
    function atualizarBadgeFiltros() {
        const navBtn = document.querySelector('.rastreio-mobile .m-bottom-nav__item[data-nav="filtros"]');
        if (!navBtn) return;
        navBtn.classList.toggle('has-filtros-ativos', temFiltroAtivo());
    }

    // ===== Toggle Lotes / Pedidos =====
    function setListaAtiva(lista) {
        ESTADO.listaAtiva = lista;
        document.querySelectorAll('.rastreio-mobile .m-ras-toggle-btn').forEach(b => {
            b.classList.toggle('is-active', b.dataset.list === lista);
            b.setAttribute('aria-selected', b.dataset.list === lista ? 'true' : 'false');
        });
        const lotesEl = $m('m_ras_lotesList');
        const pedidosEl = $m('m_ras_pedidosList');
        if (lotesEl) lotesEl.hidden = (lista !== 'lotes');
        if (pedidosEl) pedidosEl.hidden = (lista !== 'pedidos');
        // Atualiza placeholder da busca
        const search = $m('m_ras_search');
        if (search) {
            search.placeholder = (lista === 'lotes')
                ? 'Buscar lote, produto, fornecedor (últimos 7 dias)'
                : 'Buscar pedido/nota ou cliente (últimos 7 dias)';
        }
        // Sincroniza o toggle inline de agrupamento com a lista atual
        syncToggleAgrupamento();
    }
    function bindToggleLista() {
        document.querySelectorAll('.rastreio-mobile .m-ras-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const lista = btn.dataset.list;
                setListaAtiva(lista);
                carregarAtual();
            });
        });
    }

    // Toggle de agrupamento (Produto / Parceiro) — inline, sem abrir sheet
    function bindToggleAgrupamento() {
        document.querySelectorAll('.rastreio-mobile .m-ras-agrup-btn[data-agrup]').forEach(btn => {
            btn.addEventListener('click', () => {
                const val = btn.dataset.agrup;
                if (ESTADO.listaAtiva === 'lotes') ESTADO.agrupamentoLotes = val;
                else                                ESTADO.agrupamentoPedidos = val;
                // Reset de "já vistos" — grupos novos no critério ganham
                // default colapsado (caso comum quando alterna entre dimensões).
                if (ESTADO.listaAtiva === 'lotes') {
                    ESTADO.gruposLotesColapsados.clear();
                    ESTADO.gruposLotesJaVistos.clear();
                } else {
                    ESTADO.gruposPedidosColapsados.clear();
                    ESTADO.gruposPedidosJaVistos.clear();
                }
                // Atualiza estado visual + sincroniza com sheet de filtros
                document.querySelectorAll('.rastreio-mobile .m-ras-agrup-btn[data-agrup]').forEach(b => {
                    const on = (b.dataset.agrup === val);
                    b.classList.toggle('is-active', on);
                    b.setAttribute('aria-selected', on ? 'true' : 'false');
                });
                const dataAttr = (ESTADO.listaAtiva === 'lotes') ? 'data-grp-lotes' : 'data-grp-pedidos';
                document.querySelectorAll(`.rastreio-mobile .m-toggle-btn[${dataAttr}]`).forEach(b => {
                    b.classList.toggle('is-active', b.getAttribute(dataAttr) === val);
                });
                if (ESTADO.listaAtiva === 'lotes') renderLotesLista();
                else renderPedidosLista();
            });
        });
        const btnAgr = $m('m_ras_btnAgruparTudo');
        if (btnAgr) btnAgr.addEventListener('click', () => {
            if (ESTADO.listaAtiva === 'lotes') {
                // Agrupar tudo = colapsar todos os grupos visíveis
                const porProduto = ESTADO.agrupamentoLotes === 'produto';
                (ESTADO.lotesData || []).forEach(l => {
                    const c = porProduto ? (l.descrprod || '—') : (l.nomeparc_origem || '—');
                    ESTADO.gruposLotesColapsados.add(c);
                });
                renderLotesLista();
            } else {
                if (ESTADO.agrupamentoPedidos === 'parceiro') {
                    (ESTADO.pedidosData || []).forEach(p => {
                        ESTADO.gruposPedidosColapsados.add(p.nomeparc || '—');
                    });
                    renderPedidosLista();
                }
            }
        });
        const btnDesagr = $m('m_ras_btnDesagruparTudo');
        if (btnDesagr) btnDesagr.addEventListener('click', () => {
            if (ESTADO.listaAtiva === 'lotes') {
                ESTADO.gruposLotesColapsados.clear();
                renderLotesLista();
            } else {
                ESTADO.gruposPedidosColapsados.clear();
                renderPedidosLista();
            }
        });
    }

    // Sincroniza o toggle inline com o agrupamento atual da lista ativa
    function syncToggleAgrupamento() {
        const val = (ESTADO.listaAtiva === 'lotes')
            ? ESTADO.agrupamentoLotes
            : ESTADO.agrupamentoPedidos;
        document.querySelectorAll('.rastreio-mobile .m-ras-agrup-btn[data-agrup]').forEach(b => {
            const on = (b.dataset.agrup === val);
            b.classList.toggle('is-active', on);
            b.setAttribute('aria-selected', on ? 'true' : 'false');
        });
    }

    // ===== Bar Armado =====
    function atualizarBarArmado() {
        const bar = $m('m_ras_barArmado');
        const lab = $m('m_ras_barArmadoLote');
        const dis = $m('m_ras_barArmadoDisp');
        if (!bar) return;
        if (ESTADO.loteArmado) {
            bar.classList.remove('m-ras-bar-armado--off');
            // Linha 1: fornecedor + produto (sem mostrar CODAGREGACAO)
            const fornec = ESTADO.loteArmado.nomeparc_origem || '—';
            const produto = ESTADO.loteArmado.descrprod || '—';
            if (lab) lab.textContent = `${fornec} · ${produto}`;
            // Linha 2: disponível + data
            const data = ESTADO.loteArmado.dtneg_origem || '';
            const qtd = fmtQtd(ESTADO.loteArmado.qtd_disponivel);
            if (dis) dis.textContent = data
                ? `Disponível: ${qtd} kg · ${data}`
                : `Disponível: ${qtd} kg`;
        } else {
            bar.classList.add('m-ras-bar-armado--off');
            if (lab) lab.textContent = '—';
            if (dis) dis.textContent = '0 kg';
        }
    }
    function armarLote(lote) {
        ESTADO.loteArmado = lote;
        // Sempre volta pra tela principal + alterna pra Pedidos.
        // Operador vê DIRETO os pedidos compatíveis com o CODPROD do lote.
        if (telaAtiva !== 'lista') popToRoot();
        setListaAtiva('pedidos');
        atualizarBarArmado();
        // Recarrega pedidos com filtro de CODPROD (só compatíveis aparecem)
        carregarPedidos();
        renderLotesLista();
        if ($m('m_ras_btnArmar')) atualizarBtnArmarTela($m('m_ras_btnArmar'));
        mostrarToast(`Lote armado. Pedidos compatíveis listados.`, 'info');
    }
    function desarmarLote() {
        const tinhaArmado = !!ESTADO.loteArmado;
        ESTADO.loteArmado = null;
        atualizarBarArmado();
        // Volta pra lista de LOTES (operador armou → foi pra pedidos →
        // desarmou → volta pro contexto anterior). Sempre que possível,
        // garante que está na tela principal antes de alternar.
        if (telaAtiva !== 'lista') popToRoot();
        setListaAtiva('lotes');
        renderLotesLista();
        // Recarrega pedidos sem filtro (em background, pra contador ficar correto)
        if (tinhaArmado) carregarPedidos();
        else renderPedidosLista();
        if (telaAtiva === 'detalheLote') {
            const btnArm = $m('m_ras_btnArmar');
            if (btnArm) atualizarBtnArmarTela(btnArm);
        }
    }
    function atualizarBtnArmarTela(btn) {
        const lote = ESTADO.loteSelecionado;
        const isArmed = !!(lote && ESTADO.loteArmado
            && ESTADO.loteArmado.codagregacao === lote.codagregacao);
        btn.classList.toggle('is-armed', isArmed);
        btn.innerHTML = isArmed
            ? '<i class="ph ph-link-break"></i><span>Desarmar este lote</span>'
            : '<i class="ph ph-link"></i><span>Armar lote pra vincular</span>';
    }

    // ===== Fetch =====
    async function carregarAtual() {
        if (ESTADO.listaAtiva === 'lotes') {
            await carregarLotes();
        } else {
            await carregarPedidos();
        }
    }
    async function carregarLotes() {
        const container = $m('m_ras_lotesList');
        if (!container) return;
        if (ESTADO.carregandoLotes) return;
        ESTADO.carregandoLotes = true;
        container.innerHTML = renderSkeleton(4);

        const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: '0' });
        if (ESTADO.dataIniLotes) params.set('data_ini', ESTADO.dataIniLotes);
        if (ESTADO.dataFimLotes) params.set('data_fim', ESTADO.dataFimLotes);
        if (ESTADO.textoBusca && ESTADO.listaAtiva === 'lotes') params.set('q_lotes', ESTADO.textoBusca);
        try {
            const r = await fetch(URLS.lotes + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store',
            });
            const data = await r.json();
            // Endpoint retorna `lotes` (não `itens`).
            ESTADO.lotesData = (data.ok && data.lotes) ? data.lotes : [];
        } catch (err) {
            console.error('[ras-mobile] erro lotes', err);
            ESTADO.lotesData = [];
        } finally {
            ESTADO.carregandoLotes = false;
        }
        renderLotesLista();
        atualizarContadores();
    }
    async function carregarPedidos() {
        const container = $m('m_ras_pedidosList');
        if (!container) return;
        if (ESTADO.carregandoPedidos) return;
        ESTADO.carregandoPedidos = true;
        container.innerHTML = renderSkeleton(4);

        const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: '0' });
        if (ESTADO.dataIniPedidos) params.set('data_ini', ESTADO.dataIniPedidos);
        if (ESTADO.dataFimPedidos) params.set('data_fim', ESTADO.dataFimPedidos);
        // Sempre enviar 1/0 (paridade desktop). Se ambos false, backend devolve [].
        // Garantia: ao menos pendentes ligado por default.
        const flagPend = ESTADO.mostrarPendentes ? '1' : '0';
        const flagFin  = ESTADO.mostrarFinalizados ? '1' : '0';
        params.set('mostrar_pendentes', flagPend);
        params.set('mostrar_finalizados', flagFin);
        // Lote armado → filtra pedidos pelo CODPROD do lote (cross-filter).
        // Operador vê só os pedidos compatíveis pra atribuir esse lote.
        if (ESTADO.loteArmado && ESTADO.loteArmado.codprod) {
            params.set('codprods', String(ESTADO.loteArmado.codprod));
        }
        if (ESTADO.textoBusca && ESTADO.listaAtiva === 'pedidos') {
            const q = ESTADO.textoBusca.trim();
            if (/^\d+$/.test(q)) params.set('nunota', q);
            else params.set('q', q);
        }
        try {
            const r = await fetch(URLS.pedidos + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store',
            });
            const data = await r.json();
            ESTADO.pedidosData = (data.ok && data.itens) ? data.itens : [];
        } catch (err) {
            console.error('[ras-mobile] erro pedidos', err);
            ESTADO.pedidosData = [];
        } finally {
            ESTADO.carregandoPedidos = false;
        }
        renderPedidosLista();
        atualizarContadores();
    }
    function renderSkeleton(n) {
        let html = '';
        for (let i = 0; i < n; i++) {
            html += '<div class="m-ras-lote-card" style="opacity:.5"><div class="m-ras-lote-card__top">'
                  + '<div style="flex:1;height:14px;background:#e5e7eb;border-radius:4px;"></div></div>'
                  + '<div style="height:10px;background:#f1f5f9;border-radius:4px;margin-top:6px;"></div></div>';
        }
        return html;
    }
    function atualizarContadores() {
        const cL = $m('m_ras_countLotes');
        const cP = $m('m_ras_countPedidos');
        if (cL) cL.textContent = fmtInt(ESTADO.lotesData.length);
        // Contar pedidos distintos (agrupados por NUNOTA)
        const nuns = new Set();
        ESTADO.pedidosData.forEach(it => nuns.add(it.nunota));
        if (cP) cP.textContent = fmtInt(nuns.size);
    }

    // ===== Render: Lista de Lotes (agrupados) =====
    function renderLotesLista() {
        const container = $m('m_ras_lotesList');
        if (!container) return;
        const lotes = ESTADO.lotesData || [];
        if (!lotes.length) {
            container.innerHTML = `<div class="m-empty-state">
                <i class="ph ph-package"></i>
                <div class="m-empty-state__title">Nenhum lote no período</div>
                <div class="m-empty-state__msg">Ajuste os filtros pra ampliar a busca.</div>
            </div>`;
            return;
        }

        // Agrupamento
        const grupos = new Map();
        lotes.forEach(l => {
            const chave = ESTADO.agrupamentoLotes === 'produto'
                ? (l.descrprod || '—')
                : (l.nomeparc_origem || '—');
            if (!grupos.has(chave)) grupos.set(chave, []);
            grupos.get(chave).push(l);
        });
        const chaves = Array.from(grupos.keys()).sort((a, b) => a.localeCompare(b));

        let html = '';
        const porProduto = ESTADO.agrupamentoLotes === 'produto';

        // Default colapsado: cada grupo NOVO entra colapsado.
        // gruposLotesJaVistos garante que só aplica na 1ª aparição (refresh
        // posterior preserva o estado escolhido pelo operador).
        chaves.forEach(c => {
            if (!ESTADO.gruposLotesJaVistos.has(c)) {
                ESTADO.gruposLotesJaVistos.add(c);
                ESTADO.gruposLotesColapsados.add(c);
            }
        });

        chaves.forEach(chave => {
            const items = grupos.get(chave);
            const qtdTotal = items.reduce((s, l) => s + (Number(l.qtd_disponivel) || 0), 0);
            const colapsado = ESTADO.gruposLotesColapsados.has(chave);
            const icone = porProduto ? 'ph-package' : 'ph-user';
            html += `<div class="m-ras-grupo-header m-ras-grupo-header--${porProduto ? 'produto' : 'parceiro'} ${colapsado ? 'is-colapsado' : ''}"
                 data-grupo-lote="${escapeHtml(chave)}">
                <i class="ph ph-caret-down m-ras-grupo-header__chevron" aria-hidden="true"></i>
                <i class="ph ${icone} m-ras-grupo-header__icone" aria-hidden="true"></i>
                <span class="m-ras-grupo-header__nome">${escapeHtml(chave)}</span>
                <span class="m-ras-grupo-header__qtd">${fmtQtd(qtdTotal)} kg</span>
                <span class="m-ras-grupo-header__count">${items.length}</span>
            </div>`;
            if (!colapsado) {
                items.forEach(l => { html += renderLoteCard(l, porProduto); });
            }
        });
        container.innerHTML = html;

        // Bind click no header → alterna colapso
        container.querySelectorAll('.m-ras-grupo-header[data-grupo-lote]').forEach(h => {
            h.addEventListener('click', () => {
                const k = h.dataset.grupoLote;
                if (ESTADO.gruposLotesColapsados.has(k)) {
                    ESTADO.gruposLotesColapsados.delete(k);
                } else {
                    ESTADO.gruposLotesColapsados.add(k);
                }
                renderLotesLista();
            });
        });

        // Bind clicks nos cards + swipe-to-action (armar + olho)
        bindSwipeLoteCards(container);
    }

    // Constantes do swipe (paridade Entrada Mobile):
    // - Esquerda: 2 botões 44px = 88px (armar + olho)
    // - Direita (Mai/2026 — 2026-05-28): 1 botão 60px (avaria de ajuste / TOP 33)
    const SWIPE_REVEAL_LOTES = 88;        // swipe esquerda — armar + olho
    const SWIPE_REVEAL_AVARIA = 60;       // swipe direita  — avaria de ajuste
    const SWIPE_TRIGGER_PX   = 44;        // threshold pra abrir esquerda
    const SWIPE_TRIGGER_AVARIA_PX = 30;   // threshold pra abrir direita (50% do reveal)

    function fecharTodosSwipesLotes() {
        document.querySelectorAll('.rastreio-mobile .m-ras-lote-card-wrap[data-swipe-open], .rastreio-mobile .m-ras-lote-card-wrap[data-swipe-right="1"]')
            .forEach(w => {
                const card = w.querySelector('.m-ras-lote-card');
                if (card) card.style.transform = '';
                w.dataset.swipeOpen = '0';
                w.dataset.swipeRight = '0';
            });
    }

    function bindSwipeLoteCards(container) {
        container.querySelectorAll('.m-ras-lote-card-wrap').forEach(wrap => {
            const card = wrap.querySelector('.m-ras-lote-card');
            if (!card) return;
            let startX = 0, startY = 0, t0 = 0, ativo = false, eixoH = false, moveu = false;

            card.addEventListener('touchstart', (e) => {
                if (e.touches.length !== 1) return;
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                t0 = Date.now();
                ativo = true;
                eixoH = false;
                moveu = false;
                card.style.transition = 'none';
            }, { passive: true });

            card.addEventListener('touchmove', (e) => {
                if (!ativo || e.touches.length !== 1) return;
                const dx = e.touches[0].clientX - startX;
                const dy = e.touches[0].clientY - startY;
                if (!eixoH && Math.abs(dx) + Math.abs(dy) < 8) return;
                if (!eixoH) {
                    if (Math.abs(dy) > Math.abs(dx)) {
                        ativo = false;
                        return;
                    }
                    eixoH = true;
                }
                moveu = true;
                // Aceita swipe esquerda (dx < 0) → armar+olho
                // Aceita swipe direita (dx > 0)  → avaria de ajuste
                const abertoEsq = wrap.dataset.swipeOpen === '1';
                const abertoDir = wrap.dataset.swipeRight === '1';
                let translateX;
                if (abertoEsq) {
                    translateX = Math.min(0, -SWIPE_REVEAL_LOTES + Math.max(0, dx));
                } else if (abertoDir) {
                    translateX = Math.max(0, SWIPE_REVEAL_AVARIA + Math.min(0, dx));
                } else {
                    translateX = dx;   // segue dedo nas 2 direções
                }
                // Resistência elástica acima do reveal
                if (translateX < -SWIPE_REVEAL_LOTES) {
                    const over = -translateX - SWIPE_REVEAL_LOTES;
                    translateX = -SWIPE_REVEAL_LOTES - over * 0.3;
                } else if (translateX > SWIPE_REVEAL_AVARIA) {
                    const over = translateX - SWIPE_REVEAL_AVARIA;
                    translateX = SWIPE_REVEAL_AVARIA + over * 0.3;
                }
                card.style.transform = `translateX(${translateX}px)`;
            }, { passive: true });

            card.addEventListener('touchend', (e) => {
                if (!ativo) return;
                ativo = false;
                if (!eixoH || !moveu) {
                    card.style.transition = '';
                    return;
                }
                const dx = e.changedTouches[0].clientX - startX;
                const abertoEsq = wrap.dataset.swipeOpen === '1';
                const abertoDir = wrap.dataset.swipeRight === '1';
                card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';

                if (abertoEsq) {
                    if (dx > SWIPE_TRIGGER_PX) {
                        card.style.transform = '';
                        wrap.dataset.swipeOpen = '0';
                    } else {
                        card.style.transform = `translateX(-${SWIPE_REVEAL_LOTES}px)`;
                    }
                } else if (abertoDir) {
                    if (-dx > SWIPE_TRIGGER_AVARIA_PX) {
                        card.style.transform = '';
                        wrap.dataset.swipeRight = '0';
                    } else {
                        card.style.transform = `translateX(${SWIPE_REVEAL_AVARIA}px)`;
                    }
                } else {
                    // Fechado: decide direção
                    if (-dx > SWIPE_TRIGGER_PX) {
                        fecharTodosSwipesLotes();
                        card.style.transform = `translateX(-${SWIPE_REVEAL_LOTES}px)`;
                        wrap.dataset.swipeOpen = '1';
                    } else if (dx > SWIPE_TRIGGER_AVARIA_PX) {
                        fecharTodosSwipesLotes();
                        card.style.transform = `translateX(${SWIPE_REVEAL_AVARIA}px)`;
                        wrap.dataset.swipeRight = '1';
                    } else {
                        card.style.transform = '';
                    }
                }
            }, { passive: true });

            // Click no card: se swipe aberto (qualquer direção), FECHA o swipe.
            // Senão, NÃO FAZ NADA — operador usa swipe pra armar/visualizar/avariar.
            card.addEventListener('click', (e) => {
                if (moveu) return;
                if (wrap.dataset.swipeOpen === '1' || wrap.dataset.swipeRight === '1') {
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                    wrap.dataset.swipeRight = '0';
                }
            });

            // Botões absolutos: armar + olho + avariar
            wrap.querySelectorAll('[data-action]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const acao = btn.dataset.action;
                    const codag = wrap.dataset.codag;
                    const lote = ESTADO.lotesData.find(x => x.codagregacao === codag);
                    if (!lote) return;
                    // Fecha swipe após ação (qualquer direção)
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                    wrap.dataset.swipeRight = '0';
                    if (acao === 'armar') {
                        const isArmed = ESTADO.loteArmado && ESTADO.loteArmado.codagregacao === lote.codagregacao;
                        if (isArmed) {
                            desarmarLote();
                            mostrarToast('Lote desarmado.', 'info');
                        } else {
                            armarLote(lote);   // já troca lista + filtra pedidos
                        }
                    } else if (acao === 'olho') {
                        ESTADO.loteSelecionado = lote;
                        abrirDetalheLote(lote);
                    } else if (acao === 'avariar') {
                        avariaAjusteDoLote(lote);
                    }
                });
            });
        });
    }
    function renderLoteCard(l, porProduto) {
        const qtd = Number(l.qtd_disponivel) || 0;
        const isArmed = ESTADO.loteArmado && ESTADO.loteArmado.codagregacao === l.codagregacao;
        const isNaoClass = l.status_linha === 'NAO_CLASSIFICAVEL';
        const idade = _idadeDiasFromBR(l.dtneg_origem);

        const badges = [];
        // Badge N/C removido por pedido do operador (2026-05-28) — operador
        // identifica não-classificáveis por contexto, não precisa do badge.
        // Badge "fração" removido (2026-05-28) — trava de 1% foi removida,
        // operador decide manualmente quando avariar saldo.
        if (idade > DIAS_ALERTA_LOTE) {
            badges.push(`<span class="m-ras-badge m-ras-badge--envelhecido"><i class="ph ph-warning"></i> ${idade}d</span>`);
        }
        if (l.qtd_avaria_interna && Number(l.qtd_avaria_interna) > 0) {
            badges.push(`<span class="m-ras-badge m-ras-badge--avaria">avaria ${fmtQtd(l.qtd_avaria_interna)}</span>`);
        }
        const badgesHtml = badges.length
            ? `<div class="m-ras-lote-card__badges">${badges.join(' ')}</div>`
            : '';

        // Topo: destaque na dimensão que NÃO está no header do grupo
        //   - agrupado por PRODUTO → topo mostra FORNECEDOR (produto já está no header)
        //   - agrupado por PARCEIRO → topo mostra PRODUTO (parceiro já está no header)
        const topoLabel = porProduto
            ? escapeHtml(l.nomeparc_origem || '—')
            : escapeHtml(l.descrprod || '—');

        // Wrapper esconde botões absolutos atrás do card:
        //   Swipe ESQUERDA revela: [ARMAR · OLHO]  (88px total, 44px cada)
        //   Swipe DIREITA  revela: [AVARIA]        (60px, ph-broom)
        return `<div class="m-ras-lote-card-wrap" data-codag="${escapeHtml(l.codagregacao)}">
            <button type="button" class="m-ras-lote-card__swipe-avaria" data-action="avariar" aria-label="Avaria de ajuste">
                <i class="ph ph-broom" aria-hidden="true"></i>
            </button>
            <button type="button" class="m-ras-lote-card__swipe-armar" data-action="armar" aria-label="Armar lote">
                <i class="ph ph-link" aria-hidden="true"></i>
            </button>
            <button type="button" class="m-ras-lote-card__swipe-olho" data-action="olho" aria-label="Visualizar lote">
                <i class="ph ph-eye" aria-hidden="true"></i>
            </button>
            <div class="m-ras-lote-card ${isArmed ? 'is-armed' : ''} ${isNaoClass ? 'is-naoclass' : ''} ${porProduto ? 'agr-por-produto' : 'agr-por-parceiro'}"
                 data-codag="${escapeHtml(l.codagregacao)}">
                <div class="m-ras-lote-card__top">
                    <div class="m-ras-lote-card__produto">${topoLabel}</div>
                    <div class="m-ras-lote-card__qtd">${fmtQtd(qtd)} kg</div>
                </div>
                <div class="m-ras-lote-card__bottom">
                    <span class="m-ras-lote-card__data">${escapeHtml(l.dtneg_origem || '')}</span>
                    <span class="m-ras-lote-card__lote">${escapeHtml(l.codagregacao)}</span>
                </div>
                ${badgesHtml}
            </div>
        </div>`;
    }

    // ===== Avaria de Ajuste (TOP 33) =====
    // Mai/2026 (2026-05-28): trava de 1% removida. Operador decide quanto
    // avariar — prompt nativo pede qtd (default = saldo todo), confirmação
    // explicita parcial vs total, POST com qtd, atualização local imediata.
    async function avariaAjusteDoLote(lote) {
        if (!lote || !lote.codagregacao) return;
        const saldo = Number(lote.qtd_disponivel || 0);
        if (saldo <= 0) {
            mostrarToast('Lote já está zerado.', 'info');
            return;
        }
        const saldoTxt = fmtQtd(saldo);

        const entrada = window.prompt(
            `Avaria de ajuste — lote ${lote.codagregacao}\n` +
            `Produto: ${lote.descrprod}\n` +
            `Saldo disponível: ${saldoTxt} kg\n\n` +
            `Quantidade a avariar (em kg):`,
            String(saldo),
        );
        if (entrada === null) return;

        const qtdAvaria = parseFloat(String(entrada).trim().replace(',', '.'));
        if (!isFinite(qtdAvaria) || qtdAvaria <= 0) {
            mostrarToast('Quantidade inválida. Use número > 0.', 'error');
            return;
        }
        if (qtdAvaria > saldo + 0.001) {
            mostrarToast(`Quantidade ${fmtQtd(qtdAvaria)} excede o saldo ${saldoTxt}.`, 'error');
            return;
        }
        const qtdEfetiva = Math.min(qtdAvaria, saldo);
        const restante = saldo - qtdEfetiva;
        const ehParcial = restante > 0.001;

        const ok = await IAgro.confirmarAcao({
            titulo: 'Confirmar avaria de ajuste',
            mensagem:
                `Vai criar TGFCAB TOP 33 com <strong>${fmtQtd(qtdEfetiva)} kg</strong> ` +
                `de <strong>${escapeHtml(lote.descrprod || '')}</strong> ` +
                `(lote ${escapeHtml(lote.codagregacao)}).` +
                (ehParcial
                    ? `<br>Saldo restante: <strong>${fmtQtd(restante)} kg</strong>.`
                    : `<br>Lote vai sair da listagem (saldo zerado).`),
            tipo: 'aviso',
        });
        if (!ok) return;

        const res = await postJSON(URLS.zerarFracao, {
            codprod: lote.codprod,
            codagregacao: lote.codagregacao,
            qtd: qtdEfetiva,
        });
        if (!res.ok || !res.body || !res.body.ok) {
            mostrarToast((res.body && res.body.error) || 'Falha ao gerar avaria de ajuste.', 'error');
            return;
        }
        mostrarToast(
            ehParcial
                ? `Avaria de ${fmtQtd(qtdEfetiva)} kg criada. Saldo restante: ${fmtQtd(restante)} kg.`
                : 'Lote zerado (TOP 33 criada).',
            'success',
        );

        // Atualização local imediata (sem refresh-saldo automático — vide gotchas).
        const idx = ESTADO.lotesData.findIndex(x => x.codagregacao === lote.codagregacao);
        if (idx >= 0) {
            if (ehParcial) {
                ESTADO.lotesData[idx] = Object.assign({}, ESTADO.lotesData[idx], {
                    qtd_disponivel: restante,
                });
            } else {
                ESTADO.lotesData.splice(idx, 1);
                if (ESTADO.loteArmado && ESTADO.loteArmado.codagregacao === lote.codagregacao) {
                    desarmarLote();
                }
            }
        }

        // Se está na tela detalheLote, volta pra lista. Senão re-renderiza.
        const telaAtiva = document.querySelector('.rastreio-mobile .m-screen.is-active');
        if (telaAtiva && telaAtiva.dataset.screen === 'detalheLote') {
            popToRoot();
        } else {
            renderLotesLista();
        }
    }

    // ===== Render: Lista de Pedidos =====
    function agruparPedidos(linhas) {
        const porNunota = new Map();
        linhas.forEach(it => {
            const k = it.nunota;
            if (!porNunota.has(k)) {
                porNunota.set(k, {
                    nunota: it.nunota,
                    numnota: it.numnota,
                    tipo_linha: it.tipo_linha || 'PEDIDO',
                    vinculo_origem: it.vinculo_origem,
                    nota_numnota: it.nota_numnota,
                    nota_nunota: it.nota_nunota,
                    tem_candidato_pedido: it.tem_candidato_pedido,
                    statusnota: it.statusnota,
                    codtipoper: it.codtipoper,
                    nomeparc: it.nomeparc,
                    dtneg: it.dtneg,
                    produtos: new Map(),
                });
            }
            const ped = porNunota.get(k);
            const pK = it.codprod;
            if (!ped.produtos.has(pK)) {
                ped.produtos.set(pK, {
                    codprod: it.codprod,
                    descrprod: it.descrprod,
                    qtd_total: 0,
                    qtd_atribuida: 0,
                    qtd_falta: 0,
                    linhas_pendentes: [],
                    lotes_vinculados: [],
                });
            }
            const prod = ped.produtos.get(pK);
            // Backend retorna `qtd_pedida` e `codagregacao_atual`. Mantém
            // fallback pros nomes alternativos pra robustez.
            const qtd = Number(it.qtd_pedida ?? it.qtdneg) || 0;
            const codag = it.codagregacao_atual ?? it.codagregacao ?? null;
            prod.qtd_total += qtd;
            if (codag) {
                prod.qtd_atribuida += qtd;
                prod.lotes_vinculados.push({
                    sequencia: it.sequencia,
                    codagregacao: codag,
                    qtd,
                    lote_dtneg: it.lote_dtneg,
                    lote_nomeparc: it.lote_nomeparc,
                    descrprod: it.descrprod,
                });
            } else {
                prod.qtd_falta += qtd;
                prod.linhas_pendentes.push({ sequencia: it.sequencia, qtd });
            }
        });
        // Converte Maps em arrays
        const lista = Array.from(porNunota.values()).map(p => ({
            ...p,
            produtos: Array.from(p.produtos.values()),
        }));
        return lista;
    }
    function renderPedidosLista() {
        const container = $m('m_ras_pedidosList');
        if (!container) return;
        const pedidos = agruparPedidos(ESTADO.pedidosData || []);
        if (!pedidos.length) {
            container.innerHTML = `<div class="m-empty-state">
                <i class="ph ph-clipboard-text"></i>
                <div class="m-empty-state__title">Nenhum pedido no período</div>
                <div class="m-empty-state__msg">Ajuste os filtros ou ligue o status Finalizado.</div>
            </div>`;
            return;
        }

        // Agrupamento (parceiro / produto) — ambos com colapso default e
        // swipe-to-view. Por Produto agrupa POR DESCRPROD: cada card é
        // 1 produto dentro de 1 pedido (operador vê quem pediu o quê).
        let html = '';
        const porProduto = ESTADO.agrupamentoPedidos === 'produto';

        if (porProduto) {
            // Por produto: explode pedidos em (produto × pedido) e agrupa por nome
            const grupos = new Map();
            pedidos.forEach(p => {
                p.produtos.forEach(prod => {
                    const chave = prod.descrprod || '—';
                    if (!grupos.has(chave)) grupos.set(chave, []);
                    grupos.get(chave).push({ pedido: p, produto: prod });
                });
            });
            const chaves = Array.from(grupos.keys()).sort((a, b) => a.localeCompare(b));
            // Default colapsado (1ª aparição)
            chaves.forEach(c => {
                if (!ESTADO.gruposPedidosJaVistos.has(c)) {
                    ESTADO.gruposPedidosJaVistos.add(c);
                    ESTADO.gruposPedidosColapsados.add(c);
                }
            });
            chaves.forEach(c => {
                const items = grupos.get(c);
                const colapsado = ESTADO.gruposPedidosColapsados.has(c);
                const qtdTotal = items.reduce((s, x) => s + (Number(x.produto.qtd_total) || 0), 0);
                html += `<div class="m-ras-grupo-header m-ras-grupo-header--produto ${colapsado ? 'is-colapsado' : ''}"
                     data-grupo-pedido="${escapeHtml(c)}">
                    <i class="ph ph-caret-down m-ras-grupo-header__chevron" aria-hidden="true"></i>
                    <i class="ph ph-package m-ras-grupo-header__icone" aria-hidden="true"></i>
                    <span class="m-ras-grupo-header__nome">${escapeHtml(c)}</span>
                    <span class="m-ras-grupo-header__qtd">${fmtQtd(qtdTotal)} kg</span>
                    <span class="m-ras-grupo-header__count">${items.length}</span>
                </div>`;
                if (!colapsado) {
                    items.forEach(it => {
                        html += renderPedidoProdutoCard(it.pedido, it.produto);
                    });
                }
            });
        } else {
            // Por parceiro: cada PEDIDO é seu próprio grupo (chave = NUNOTA).
            // Operador não quer agregar múltiplos pedidos do mesmo parceiro num
            // único grupo. Vai aparecer "ASSAI ARAGUAINA" 2× se houver 2 pedidos.
            pedidos.forEach(p => {
                const chave = String(p.nunota);
                if (!ESTADO.gruposPedidosJaVistos.has(chave)) {
                    ESTADO.gruposPedidosJaVistos.add(chave);
                    ESTADO.gruposPedidosColapsados.add(chave);
                }
            });
            pedidos.forEach(p => {
                const chave = String(p.nunota);
                const colapsado = ESTADO.gruposPedidosColapsados.has(chave);
                // Agregação do pedido: qtd total + atribuída + falta
                let qtdTotal = 0, qtdAtrib = 0;
                p.produtos.forEach(prod => {
                    qtdTotal += Number(prod.qtd_total) || 0;
                    qtdAtrib += Number(prod.qtd_atribuida) || 0;
                });
                const qtdFalta = Math.max(qtdTotal - qtdAtrib, 0);
                const pct = qtdTotal > 0 ? Math.round((qtdAtrib / qtdTotal) * 100) : 0;
                const dataCurta = fmtDataCurta(p.dtneg);
                const ehOrfa = p.tipo_linha === 'NOTA_ORFA';
                // No header só o número (sem palavra "Pedido"/"Nota")
                const numCurto = ehOrfa
                    ? `Nº ${escapeHtml(p.numnota || p.nunota)}`
                    : `${escapeHtml(p.nunota)}`;
                // Badges de status migram pro subheader (não poluem o header)
                let statusBadge = '';
                if (ehOrfa) {
                    statusBadge = '<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--orfa">ÓRFÃ</span>';
                } else if (p.vinculo_origem === 'TGFVAR' && p.nota_numnota) {
                    statusBadge = `<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--faturado">NF ${escapeHtml(p.nota_numnota)}</span>`;
                } else if (p.vinculo_origem === 'MANUAL') {
                    statusBadge = '<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--manual">Manual</span>';
                } else if (p.vinculo_origem === 'RETROATIVO') {
                    statusBadge = '<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--retroativo">Retroativo</span>';
                }
                html += `<div class="m-ras-grupo-header m-ras-grupo-header--parceiro ${colapsado ? 'is-colapsado' : ''}"
                     data-grupo-pedido="${escapeHtml(chave)}">
                    <i class="ph ph-caret-down m-ras-grupo-header__chevron" aria-hidden="true"></i>
                    <i class="ph ph-user m-ras-grupo-header__icone" aria-hidden="true"></i>
                    <span class="m-ras-grupo-header__nome">${escapeHtml(p.nomeparc || '—')}</span>
                    ${dataCurta ? `<span class="m-ras-grupo-header__data">${escapeHtml(dataCurta)}</span>` : ''}
                    <span class="m-ras-grupo-header__pct">${pct}%</span>
                </div>`;
                if (!colapsado) {
                    // Subheader: número do pedido + qtd/falta + badges
                    const faltaTxt = qtdFalta > 0.001
                        ? `<span class="m-ras-pedido-subheader__falta">Falta ${fmtQtd(qtdFalta)}</span>`
                        : (pct === 100 ? '<span class="m-ras-pedido-subheader__ok">✓ Completo</span>' : '');
                    html += `<div class="m-ras-pedido-subheader" data-nunota="${p.nunota}">
                        <i class="ph ph-receipt" aria-hidden="true"></i>
                        <span class="m-ras-pedido-subheader__num">${numCurto}</span>
                        <span class="m-ras-pedido-subheader__qtd">${fmtQtd(qtdAtrib)} / ${fmtQtd(qtdTotal)} kg</span>
                        ${faltaTxt}
                        ${statusBadge}
                    </div>`;
                    p.produtos.forEach(prod => {
                        html += renderItemCardLote(p, prod);
                    });
                }
            });
        }
        container.innerHTML = html;

        // Bind alternar colapso
        container.querySelectorAll('.m-ras-grupo-header[data-grupo-pedido]').forEach(h => {
            h.addEventListener('click', () => {
                const k = h.dataset.grupoPedido;
                if (ESTADO.gruposPedidosColapsados.has(k)) {
                    ESTADO.gruposPedidosColapsados.delete(k);
                } else {
                    ESTADO.gruposPedidosColapsados.add(k);
                }
                renderPedidosLista();
            });
        });

        // Bind swipe + clicks
        bindSwipePedidoCards(container, pedidos);
    }

    // Card 1 produto×pedido (modo Por Produto)
    function renderPedidoProdutoCard(p, prod) {
        const qtdTotal = Number(prod.qtd_total) || 0;
        const qtdAtrib = Number(prod.qtd_atribuida) || 0;
        const qtdFalta = Number(prod.qtd_falta) || 0;
        const pct = qtdTotal > 0 ? Math.round((qtdAtrib / qtdTotal) * 100) : 0;
        const ehOrfa = p.tipo_linha === 'NOTA_ORFA';
        const ehFinalizado = qtdFalta < 0.001 && qtdTotal > 0;
        let progressClass = 'm-ras-pedido-card__progress--pendente';
        if (ehFinalizado) progressClass = 'm-ras-pedido-card__progress--ok';
        let cardCls = 'm-ras-pedido-card';
        if (ehOrfa) cardCls += ' m-ras-pedido-card--orfa';
        else if (ehFinalizado) cardCls += ' m-ras-pedido-card--finalizado';

        const numLabel = ehOrfa
            ? `Nota ${escapeHtml(p.numnota || p.nunota)}`
            : `Pedido ${escapeHtml(p.nunota)}`;

        return `<div class="m-ras-pedido-card-wrap" data-nunota="${p.nunota}" data-codprod="${prod.codprod}">
            <button type="button" class="m-ras-pedido-card__swipe-olho" data-action="ver-vinculos" aria-label="Ver lotes vinculados">
                <i class="ph ph-eye" aria-hidden="true"></i>
            </button>
            <div class="${cardCls}" data-nunota="${p.nunota}" data-codprod="${prod.codprod}">
                <div class="m-ras-pedido-card__top">
                    <div class="m-ras-pedido-card__cliente">${escapeHtml(p.nomeparc || '—')}</div>
                    <div class="m-ras-pedido-card__progress ${progressClass}">${pct}%</div>
                </div>
                <div class="m-ras-pedido-card__meta">
                    <span class="m-ras-pedido-card__num">${numLabel}</span>
                    <span>·</span>
                    <span>${escapeHtml(p.dtneg || '')}</span>
                    <span>·</span>
                    <span>${fmtQtd(qtdAtrib)} / ${fmtQtd(qtdTotal)} kg</span>
                </div>
            </div>
        </div>`;
    }

    // No modo Por Parceiro o card de pedido NÃO tem swipe externo —
    // cada item dentro tem swipe-to-view próprio (mais granular).
    function renderPedidoCardWrap(p) {
        return renderPedidoCard(p);
    }

    // Constantes do swipe — 1 botão 56px (só "olho"), threshold 28px
    const SWIPE_REVEAL_PEDIDO = 56;
    const SWIPE_TRIGGER_PEDIDO = 28;

    function fecharTodosSwipesPedidos() {
        document.querySelectorAll('.rastreio-mobile .m-ras-pedido-card-wrap[data-swipe-open="1"]')
            .forEach(w => {
                const card = w.querySelector('.m-ras-pedido-card');
                if (card) card.style.transform = '';
                w.dataset.swipeOpen = '0';
            });
    }

    function bindSwipePedidoCards(container, pedidos) {
        container.querySelectorAll('.m-ras-pedido-card-wrap').forEach(wrap => {
            const card = wrap.querySelector('.m-ras-pedido-card');
            if (!card) return;
            let startX = 0, startY = 0, t0 = 0, ativo = false, eixoH = false, moveu = false;

            card.addEventListener('touchstart', (e) => {
                if (e.touches.length !== 1) return;
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                t0 = Date.now();
                ativo = true; eixoH = false; moveu = false;
                card.style.transition = 'none';
            }, { passive: true });

            card.addEventListener('touchmove', (e) => {
                if (!ativo || e.touches.length !== 1) return;
                const dx = e.touches[0].clientX - startX;
                const dy = e.touches[0].clientY - startY;
                if (!eixoH && Math.abs(dx) + Math.abs(dy) < 8) return;
                if (!eixoH) {
                    if (Math.abs(dy) > Math.abs(dx)) { ativo = false; return; }
                    eixoH = true;
                }
                moveu = true;
                const aberto = wrap.dataset.swipeOpen === '1';
                let translateX = aberto
                    ? Math.min(0, -SWIPE_REVEAL_PEDIDO + Math.max(0, dx))
                    : Math.min(0, dx);
                if (translateX < -SWIPE_REVEAL_PEDIDO) {
                    const over = -translateX - SWIPE_REVEAL_PEDIDO;
                    translateX = -SWIPE_REVEAL_PEDIDO - over * 0.3;
                }
                card.style.transform = `translateX(${translateX}px)`;
            }, { passive: true });

            card.addEventListener('touchend', (e) => {
                if (!ativo) return;
                ativo = false;
                if (!eixoH || !moveu) { card.style.transition = ''; return; }
                const dx = e.changedTouches[0].clientX - startX;
                const aberto = wrap.dataset.swipeOpen === '1';
                card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                if (aberto) {
                    if (dx > SWIPE_TRIGGER_PEDIDO) {
                        card.style.transform = '';
                        wrap.dataset.swipeOpen = '0';
                    } else {
                        card.style.transform = `translateX(-${SWIPE_REVEAL_PEDIDO}px)`;
                    }
                } else {
                    if (-dx > SWIPE_TRIGGER_PEDIDO) {
                        fecharTodosSwipesPedidos();
                        card.style.transform = `translateX(-${SWIPE_REVEAL_PEDIDO}px)`;
                        wrap.dataset.swipeOpen = '1';
                    } else {
                        card.style.transform = '';
                    }
                }
            }, { passive: true });

            // Click no card: se swipe aberto, fecha (cancelar implícito)
            // Senão: atalho de vincular OU abre detalhe
            card.addEventListener('click', () => {
                if (moveu) return;
                if (wrap.dataset.swipeOpen === '1') {
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                    return;
                }
                const nu = Number(card.dataset.nunota);
                const ped = pedidos.find(p => p.nunota === nu);
                if (!ped) return;
                ESTADO.pedidoSelecionado = ped;

                // Atalho: lote armado + produto compatível → sheet Vincular
                if (ESTADO.loteArmado && ESTADO.loteArmado.codprod) {
                    const codArmado = Number(ESTADO.loteArmado.codprod);
                    // Se card é Por Produto, restringe ao CODPROD do card
                    const codCard = card.dataset.codprod ? Number(card.dataset.codprod) : null;
                    const compativeis = ped.produtos.filter(p =>
                        Number(p.codprod) === codArmado
                        && (codCard === null || Number(p.codprod) === codCard)
                    );
                    if (compativeis.length === 1) {
                        abrirSheetVincular(compativeis[0]);
                        return;
                    }
                    if (compativeis.length > 1) {
                        const primeiraPendente = compativeis.find(p => (Number(p.qtd_falta) || 0) > 0.001);
                        abrirSheetVincular(primeiraPendente || compativeis[0]);
                        return;
                    }
                    mostrarToast('Pedido não tem o produto do lote armado.', 'warning');
                }
                abrirDetalhePedido(ped);
            });

            // Botão olho — abre sheet com lotes vinculados
            const olhoBtn = wrap.querySelector('[data-action="ver-vinculos"]');
            if (olhoBtn) {
                olhoBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const nu = Number(wrap.dataset.nunota);
                    const ped = pedidos.find(p => p.nunota === nu);
                    if (!ped) return;
                    // Fecha swipe após ação
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                    // Se Por Produto, filtra só esse CODPROD
                    const codCard = wrap.dataset.codprod ? Number(wrap.dataset.codprod) : null;
                    abrirSheetVinculosPedido(ped, codCard);
                });
            }
        });

        // Binda swipe-to-view em cada CARD DE ITEM (modo Por Parceiro).
        // Cada item tem seu próprio wrapper independente do card de pedido.
        bindSwipeItemCards(container, pedidos);
    }

    // Swipe-to-view dos cards de item dentro do card de pedido (Por Parceiro)
    // 2 botões (link + olho) × 48px = 96px
    const SWIPE_REVEAL_ITEM = 96;
    const SWIPE_TRIGGER_ITEM = 48;

    function fecharTodosSwipesItens() {
        document.querySelectorAll('.rastreio-mobile .m-ras-item-card-wrap[data-swipe-open="1"]')
            .forEach(w => {
                const card = w.querySelector('.m-ras-item-card');
                if (card) card.style.transform = '';
                w.dataset.swipeOpen = '0';
            });
    }

    function bindSwipeItemCards(container, pedidos) {
        container.querySelectorAll('.m-ras-item-card-wrap').forEach(wrap => {
            const card = wrap.querySelector('.m-ras-item-card');
            if (!card) return;
            let startX = 0, startY = 0, ativo = false, eixoH = false, moveu = false;

            card.addEventListener('touchstart', (e) => {
                if (e.touches.length !== 1) return;
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                ativo = true; eixoH = false; moveu = false;
                card.style.transition = 'none';
            }, { passive: true });

            card.addEventListener('touchmove', (e) => {
                if (!ativo || e.touches.length !== 1) return;
                const dx = e.touches[0].clientX - startX;
                const dy = e.touches[0].clientY - startY;
                if (!eixoH && Math.abs(dx) + Math.abs(dy) < 8) return;
                if (!eixoH) {
                    if (Math.abs(dy) > Math.abs(dx)) { ativo = false; return; }
                    eixoH = true;
                }
                moveu = true;
                const aberto = wrap.dataset.swipeOpen === '1';
                let translateX = aberto
                    ? Math.min(0, -SWIPE_REVEAL_ITEM + Math.max(0, dx))
                    : Math.min(0, dx);
                if (translateX < -SWIPE_REVEAL_ITEM) {
                    const over = -translateX - SWIPE_REVEAL_ITEM;
                    translateX = -SWIPE_REVEAL_ITEM - over * 0.3;
                }
                card.style.transform = `translateX(${translateX}px)`;
            }, { passive: true });

            card.addEventListener('touchend', (e) => {
                if (!ativo) return;
                ativo = false;
                if (!eixoH || !moveu) { card.style.transition = ''; return; }
                const dx = e.changedTouches[0].clientX - startX;
                const aberto = wrap.dataset.swipeOpen === '1';
                card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                if (aberto) {
                    if (dx > SWIPE_TRIGGER_ITEM) {
                        card.style.transform = ''; wrap.dataset.swipeOpen = '0';
                    } else {
                        card.style.transform = `translateX(-${SWIPE_REVEAL_ITEM}px)`;
                    }
                } else {
                    if (-dx > SWIPE_TRIGGER_ITEM) {
                        fecharTodosSwipesItens();
                        card.style.transform = `translateX(-${SWIPE_REVEAL_ITEM}px)`;
                        wrap.dataset.swipeOpen = '1';
                    } else {
                        card.style.transform = '';
                    }
                }
            }, { passive: true });

            // Click no card: se swipe aberto, fecha (cancelar implícito).
            // Senão: atalho de vincular se há lote armado compatível.
            card.addEventListener('click', (e) => {
                if (moveu) return;
                e.stopPropagation();   // não propaga pro card de pedido
                if (wrap.dataset.swipeOpen === '1') {
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                    return;
                }
                const nu = Number(wrap.dataset.nunota);
                const cp = Number(wrap.dataset.codprod);
                const ped = pedidos.find(p => p.nunota === nu);
                if (!ped) return;
                ESTADO.pedidoSelecionado = ped;
                // Se lote armado bate com o CODPROD do item, abre Vincular
                if (ESTADO.loteArmado && Number(ESTADO.loteArmado.codprod) === cp) {
                    const prod = ped.produtos.find(p => Number(p.codprod) === cp);
                    if (prod) { abrirSheetVincular(prod); return; }
                }
                // Senão, abre sheet de vínculos pra visualizar
                abrirSheetVinculosPedido(ped, cp);
            });

            // Botão olho do item
            const olhoBtn = wrap.querySelector('[data-action="ver-item-vinculos"]');
            if (olhoBtn) {
                olhoBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const nu = Number(wrap.dataset.nunota);
                    const cp = Number(wrap.dataset.codprod);
                    const ped = pedidos.find(p => p.nunota === nu);
                    if (!ped) return;
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                    abrirSheetVinculosPedido(ped, cp);
                });
            }

            // Botão verde "vincular item" — usa lote armado se houver
            const vincBtn = wrap.querySelector('[data-action="vincular-item"]');
            if (vincBtn) {
                vincBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const nu = Number(wrap.dataset.nunota);
                    const cp = Number(wrap.dataset.codprod);
                    const ped = pedidos.find(p => p.nunota === nu);
                    if (!ped) return;
                    // Fecha swipe
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';

                    if (!ESTADO.loteArmado) {
                        mostrarToast('Arme um lote primeiro (tocar Lotes → arrastar lote → Armar).', 'warning');
                        return;
                    }
                    if (Number(ESTADO.loteArmado.codprod) !== cp) {
                        mostrarToast(`Lote armado é de outro produto (${ESTADO.loteArmado.descrprod}).`, 'warning');
                        return;
                    }
                    const prod = ped.produtos.find(p => Number(p.codprod) === cp);
                    if (!prod) return;
                    ESTADO.pedidoSelecionado = ped;
                    abrirSheetVincular(prod);
                });
            }
        });
    }

    // Sheet de Lotes vinculados (read-only)
    function abrirSheetVinculosPedido(ped, codprodFiltro) {
        const titulo = $m('m_ras_vinculosPedidoTitulo');
        const lista = $m('m_ras_vinculosPedidoLista');
        if (!titulo || !lista) return;

        const produtos = codprodFiltro != null
            ? ped.produtos.filter(p => Number(p.codprod) === codprodFiltro)
            : ped.produtos;

        const _rotuloPedido = ped.tipo_linha === 'NOTA_ORFA'
            ? `Nota ${ped.numnota || ped.nunota}`
            : `Pedido ${ped.nunota}`;
        titulo.textContent = `Lotes vinculados · ${_rotuloPedido}`;

        // Junta todos os lotes vinculados dos produtos filtrados
        const vinculos = [];
        produtos.forEach(prod => {
            (prod.lotes_vinculados || []).forEach(lv => {
                vinculos.push({
                    descrprod: prod.descrprod,
                    codagregacao: lv.codagregacao,
                    qtd: lv.qtd,
                    lote_dtneg: lv.lote_dtneg,
                    lote_nomeparc: lv.lote_nomeparc,
                    sequencia: lv.sequencia,
                });
            });
        });

        if (!vinculos.length) {
            // Nenhum lote vinculado ainda — informa qtd faltante por produto
            let html = '<div class="m-empty-state"><i class="ph ph-tray"></i>'
                     + '<div class="m-empty-state__title">Nenhum lote vinculado ainda</div>'
                     + '<div class="m-empty-state__msg">';
            produtos.forEach(prod => {
                const qf = Number(prod.qtd_falta) || 0;
                html += `<div>${escapeHtml(prod.descrprod)}: falta ${fmtQtd(qf)} kg</div>`;
            });
            html += '</div></div>';
            lista.innerHTML = html;
        } else {
            // Wrapper com botão lixeira escondido pra swipe-to-delete.
            // Só permite desvincular em pedido TOP 34 STATUSNOTA != 'E'
            const podeDesvincular = Number(ped.codtipoper) === 34 && ped.statusnota !== 'E';
            lista.innerHTML = vinculos.map(v => `<div class="m-ras-vinc-card-wrap"
                 data-nunota="${ped.nunota}"
                 data-seq="${v.sequencia}"
                 data-codag="${escapeHtml(v.codagregacao)}">
                ${podeDesvincular ? `
                    <button type="button" class="m-ras-vinc-card__swipe-del" data-action="desvincular" aria-label="Desvincular lote">
                        <i class="ph ph-trash" aria-hidden="true"></i>
                    </button>
                ` : ''}
                <div class="m-ras-vinc-card">
                    <div class="m-ras-vinc-card__top">
                        <span class="m-ras-vinc-card__num" style="font-family:monospace;">${escapeHtml(v.codagregacao)}</span>
                        <span class="m-ras-vinc-card__qtd">${fmtQtd(v.qtd)} kg</span>
                    </div>
                    <div class="m-ras-vinc-card__bottom">
                        <small>${escapeHtml(v.descrprod || '—')}</small>
                        ${v.lote_nomeparc ? `<small>·</small><small>${escapeHtml(v.lote_nomeparc)}</small>` : ''}
                        ${v.lote_dtneg ? `<small>·</small><small>${escapeHtml(v.lote_dtneg)}</small>` : ''}
                    </div>
                </div>
            </div>`).join('');

            if (podeDesvincular) bindSwipeVinculosCards(lista, ped);
        }

        openSheet('vinculos-pedido');
    }

    // Swipe-to-delete dos cards de lote vinculado (sheet vinculos-pedido).
    // Padrão similar aos lotes: arrastar esquerda revela botão vermelho.
    const SWIPE_REVEAL_VINC = 56;
    const SWIPE_TRIGGER_VINC = 28;

    function bindSwipeVinculosCards(container, ped) {
        container.querySelectorAll('.m-ras-vinc-card-wrap').forEach(wrap => {
            const card = wrap.querySelector('.m-ras-vinc-card');
            if (!card) return;
            let startX = 0, startY = 0, t0 = 0, ativo = false, eixoH = false, moveu = false;

            card.addEventListener('touchstart', (e) => {
                if (e.touches.length !== 1) return;
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                t0 = Date.now();
                ativo = true; eixoH = false; moveu = false;
                card.style.transition = 'none';
            }, { passive: true });

            card.addEventListener('touchmove', (e) => {
                if (!ativo || e.touches.length !== 1) return;
                const dx = e.touches[0].clientX - startX;
                const dy = e.touches[0].clientY - startY;
                if (!eixoH && Math.abs(dx) + Math.abs(dy) < 8) return;
                if (!eixoH) {
                    if (Math.abs(dy) > Math.abs(dx)) { ativo = false; return; }
                    eixoH = true;
                }
                moveu = true;
                const aberto = wrap.dataset.swipeOpen === '1';
                let translateX = aberto
                    ? Math.min(0, -SWIPE_REVEAL_VINC + Math.max(0, dx))
                    : Math.min(0, dx);
                if (translateX < -SWIPE_REVEAL_VINC) {
                    const over = -translateX - SWIPE_REVEAL_VINC;
                    translateX = -SWIPE_REVEAL_VINC - over * 0.3;
                }
                card.style.transform = `translateX(${translateX}px)`;
            }, { passive: true });

            card.addEventListener('touchend', (e) => {
                if (!ativo) return;
                ativo = false;
                if (!eixoH || !moveu) { card.style.transition = ''; return; }
                const dx = e.changedTouches[0].clientX - startX;
                const aberto = wrap.dataset.swipeOpen === '1';
                card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                if (aberto) {
                    if (dx > SWIPE_TRIGGER_VINC) {
                        card.style.transform = ''; wrap.dataset.swipeOpen = '0';
                    } else {
                        card.style.transform = `translateX(-${SWIPE_REVEAL_VINC}px)`;
                    }
                } else {
                    if (-dx > SWIPE_TRIGGER_VINC) {
                        // Fecha qualquer outro swipe aberto dentro do mesmo container
                        container.querySelectorAll('.m-ras-vinc-card-wrap[data-swipe-open="1"]').forEach(w => {
                            const c2 = w.querySelector('.m-ras-vinc-card');
                            if (c2) c2.style.transform = '';
                            w.dataset.swipeOpen = '0';
                        });
                        card.style.transform = `translateX(-${SWIPE_REVEAL_VINC}px)`;
                        wrap.dataset.swipeOpen = '1';
                    } else {
                        card.style.transform = '';
                    }
                }
            }, { passive: true });

            // Click no card em modo swipe-open → fecha (cancelar implícito)
            card.addEventListener('click', () => {
                if (moveu) return;
                if (wrap.dataset.swipeOpen === '1') {
                    card.style.transition = 'transform 0.22s cubic-bezier(0.25, 1, 0.5, 1)';
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';
                }
            });

            // Botão lixeira → desvincula
            const btnDel = wrap.querySelector('[data-action="desvincular"]');
            if (btnDel) {
                btnDel.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const nu = Number(wrap.dataset.nunota);
                    const seq = Number(wrap.dataset.seq);
                    const codag = wrap.dataset.codag;
                    const ok = await IAgro.confirmarAcao({
                        titulo: 'Desvincular lote',
                        mensagem: `Remover lote <strong>${escapeHtml(codag)}</strong> do Pedido ${nu}, SEQ ${seq}?`,
                        tipo: 'aviso',
                    });
                    if (!ok) return;
                    btnDel.disabled = true;
                    const res = await postJSON(URLS.desvincularLote, { nunota: nu, sequencia: seq });
                    if (!res.ok || !res.body || !res.body.ok) {
                        mostrarToast((res.body && res.body.error) || 'Falha ao desvincular.', 'error');
                        btnDel.disabled = false;
                        return;
                    }
                    mostrarToast(`Lote ${codag} desvinculado.`, 'success');
                    // Remove visualmente do sheet + recarrega pedidos em background
                    wrap.style.transition = 'opacity 0.18s ease, transform 0.22s ease';
                    wrap.style.opacity = '0';
                    wrap.style.transform = 'translateX(-100%)';
                    setTimeout(() => {
                        wrap.remove();
                        // Se ficou vazio, fecha sheet
                        if (!container.querySelector('.m-ras-vinc-card-wrap')) {
                            closeSheet('vinculos-pedido');
                            mostrarToast('Pedido sem lotes vinculados agora.', 'info');
                        }
                    }, 260);
                    // Recarrega pedidos pra refletir mudança nos cards principais
                    carregarPedidos();
                });
            }
        });
    }
    function renderPedidoCard(p) {
        const qtdTotal = p.produtos.reduce((s, x) => s + (Number(x.qtd_total) || 0), 0);
        const qtdAtrib = p.produtos.reduce((s, x) => s + (Number(x.qtd_atribuida) || 0), 0);
        const qtdFalta = Math.max(qtdTotal - qtdAtrib, 0);
        const pct = qtdTotal > 0 ? Math.round((qtdAtrib / qtdTotal) * 100) : 0;
        const ehOrfa = p.tipo_linha === 'NOTA_ORFA';
        const ehFinalizado = qtdFalta < 0.001 && qtdTotal > 0;

        let progressClass = 'm-ras-pedido-card__progress--pendente';
        if (ehFinalizado) progressClass = 'm-ras-pedido-card__progress--ok';

        let cardCls = 'm-ras-pedido-card';
        if (ehOrfa) cardCls += ' m-ras-pedido-card--orfa';
        else if (ehFinalizado) cardCls += ' m-ras-pedido-card--finalizado';

        const numLabel = ehOrfa
            ? `Nota ${escapeHtml(p.numnota || p.nunota)}`
            : `Pedido ${escapeHtml(p.nunota)}`;

        let badges = '';
        if (ehOrfa) {
            badges = `<span class="m-ras-pedido-badge m-ras-pedido-badge--orfa">ÓRFÃ</span>`;
        } else if (p.vinculo_origem === 'TGFVAR' && p.nota_numnota) {
            badges = `<span class="m-ras-pedido-badge m-ras-pedido-badge--faturado">Faturado · Nota ${escapeHtml(p.nota_numnota)}</span>`;
        } else if (p.vinculo_origem === 'MANUAL') {
            badges = `<span class="m-ras-pedido-badge m-ras-pedido-badge--manual">Vinculado manual</span>`;
        } else if (p.vinculo_origem === 'RETROATIVO') {
            badges = `<span class="m-ras-pedido-badge m-ras-pedido-badge--retroativo">Retroativo</span>`;
        }
        const badgesHtml = badges ? `<div class="m-ras-pedido-card__badges">${badges}</div>` : '';

        // Items como CARDS INDIVIDUAIS com swipe-to-view (cada um vê seus lotes)
        let itemsHtml = '';
        if (p.produtos && p.produtos.length) {
            itemsHtml = `<div class="m-ras-pedido-card__items">${
                p.produtos.map(prod => renderItemCardSwipe(p, prod)).join('')
            }</div>`;
        }

        // Subheader (meta) com Falta X kg quando há diferença
        const faltaTxt = qtdFalta > 0.001
            ? ` <span class="m-ras-pedido-card__falta">· Falta ${fmtQtd(qtdFalta)} kg</span>`
            : '';

        return `<div class="${cardCls}" data-nunota="${p.nunota}">
            <div class="m-ras-pedido-card__top">
                <div class="m-ras-pedido-card__cliente">${escapeHtml(p.nomeparc || '—')}</div>
                <div class="m-ras-pedido-card__progress ${progressClass}">${pct}%</div>
            </div>
            <div class="m-ras-pedido-card__meta">
                <span class="m-ras-pedido-card__num">${numLabel}</span>
                <span>·</span>
                <span>${fmtQtd(qtdAtrib)} / ${fmtQtd(qtdTotal)} kg</span>
                ${faltaTxt}
            </div>
            ${badgesHtml}
            ${itemsHtml}
        </div>`;
    }

    // Subheader compacto entre o header do parceiro e os cards de item.
    // Mostra os dados do pedido (Pedido N, qtd atrib/total, Falta) +
    // badges (faturado/manual/órfã). Sem swipe — apenas informativo.
    function renderPedidoSubheader(p) {
        const qtdTotal = p.produtos.reduce((s, x) => s + (Number(x.qtd_total) || 0), 0);
        const qtdAtrib = p.produtos.reduce((s, x) => s + (Number(x.qtd_atribuida) || 0), 0);
        const qtdFalta = Math.max(qtdTotal - qtdAtrib, 0);
        const ehOrfa = p.tipo_linha === 'NOTA_ORFA';
        const ehFinalizado = qtdFalta < 0.001 && qtdTotal > 0;
        const numLabel = ehOrfa
            ? `Nota ${escapeHtml(p.numnota || p.nunota)}`
            : `Pedido ${escapeHtml(p.nunota)}`;
        let badge = '';
        if (ehOrfa) {
            badge = `<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--orfa">ÓRFÃ</span>`;
        } else if (p.vinculo_origem === 'TGFVAR' && p.nota_numnota) {
            badge = `<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--faturado">NF ${escapeHtml(p.nota_numnota)}</span>`;
        } else if (p.vinculo_origem === 'MANUAL') {
            badge = `<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--manual">Manual</span>`;
        } else if (p.vinculo_origem === 'RETROATIVO') {
            badge = `<span class="m-ras-pedido-subheader__badge m-ras-pedido-subheader__badge--retroativo">Retroativo</span>`;
        }
        const faltaTxt = qtdFalta > 0.001
            ? `<span class="m-ras-pedido-subheader__falta">Falta ${fmtQtd(qtdFalta)}</span>`
            : (ehFinalizado ? '<span class="m-ras-pedido-subheader__ok">✓ Completo</span>' : '');
        return `<div class="m-ras-pedido-subheader" data-nunota="${p.nunota}">
            <i class="ph ph-receipt" aria-hidden="true"></i>
            <span class="m-ras-pedido-subheader__num">${numLabel}</span>
            <span class="m-ras-pedido-subheader__qtd">${fmtQtd(qtdAtrib)} / ${fmtQtd(qtdTotal)} kg</span>
            ${faltaTxt}
            ${badge}
        </div>`;
    }

    // Card de item no MESMO padrão dos cards de lote (Rastreio):
    //  - Linha 1: nome do produto + qtd em pílula
    //  - Linha 2: data + pedido em pílula + falta/check
    //  - Swipe esquerda: 2 botões (link verde "vincular" + olho azul "ver")
    function renderItemCardLote(ped, prod) {
        const qa = Number(prod.qtd_atribuida) || 0;
        const qt = Number(prod.qtd_total) || 0;
        const qf = Number(prod.qtd_falta) || 0;
        const completo = qf < 0.001 && qt > 0;
        const codArmado = ESTADO.loteArmado ? Number(ESTADO.loteArmado.codprod) : null;
        const compativel = codArmado !== null && codArmado === Number(prod.codprod);

        let badgeFalta = '';
        if (completo) {
            badgeFalta = '<span class="m-ras-item-card__check"><i class="ph ph-check"></i></span>';
        } else if (qf > 0.001) {
            badgeFalta = `<span class="m-ras-item-card__falta">Falta ${fmtQtd(qf)}</span>`;
        }

        return `<div class="m-ras-item-card-wrap ${compativel ? 'is-compativel' : ''}"
             data-nunota="${ped.nunota}" data-codprod="${prod.codprod}">
            <button type="button" class="m-ras-item-card__swipe-armar" data-action="vincular-item" aria-label="Vincular lote armado">
                <i class="ph ph-link" aria-hidden="true"></i>
            </button>
            <button type="button" class="m-ras-item-card__swipe-olho" data-action="ver-item-vinculos" aria-label="Ver lotes vinculados">
                <i class="ph ph-eye" aria-hidden="true"></i>
            </button>
            <div class="m-ras-item-card ${completo ? 'is-completo' : ''}">
                <div class="m-ras-item-card__top">
                    <span class="m-ras-item-card__nome">${escapeHtml(prod.descrprod || '—')}</span>
                    <span class="m-ras-item-card__qtd-badge ${completo ? 'is-completo' : ''}">${fmtQtd(qt)} kg</span>
                </div>
                <div class="m-ras-item-card__bottom">
                    <span class="m-ras-item-card__data">${escapeHtml(ped.dtneg || '')}</span>
                    <span class="m-ras-item-card__pedido-tag">Pedido ${escapeHtml(ped.nunota)}</span>
                    ${badgeFalta}
                </div>
            </div>
        </div>`;
    }

    // ===== Tela detalhe do Lote =====
    async function abrirDetalheLote(lote) {
        ESTADO.loteSelecionado = lote;
        // Preenche hero
        $m('m_ras_loteProduto').textContent = lote.descrprod || '—';
        $m('m_ras_loteFornecedor').textContent = lote.nomeparc_origem || '—';
        $m('m_ras_loteData').textContent = lote.dtneg_origem || '—';
        $m('m_ras_loteDisp').textContent = `${fmtQtd(lote.qtd_disponivel)} kg`;
        $m('m_ras_loteCodag').textContent = lote.codagregacao || '—';

        // Botão Avaria de Ajuste (TOP 33) — Mai/2026 (2026-05-28): sempre
        // disponível em lote com saldo > 0. Trava de 1% foi removida.
        const qtdLote = Number(lote.qtd_disponivel) || 0;
        const btnFracao = $m('m_ras_loteBtnFracao');
        if (btnFracao) btnFracao.hidden = qtdLote <= 0;

        const btnArm = $m('m_ras_btnArmar');
        if (btnArm) atualizarBtnArmarTela(btnArm);

        const cont = $m('m_ras_loteVinculos');
        if (cont) cont.innerHTML = '<div class="m-empty-state"><i class="ph ph-spinner"></i><div class="m-empty-state__msg">Carregando...</div></div>';

        pushScreen('detalheLote');

        // Carrega vínculos
        try {
            const params = new URLSearchParams({ codagregacao: lote.codagregacao });
            const r = await fetch(URLS.loteVinculos + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store',
            });
            const data = await r.json();
            renderLoteVinculos(data.vinculos || []);
        } catch (err) {
            console.error('[ras-mobile] vinculos lote', err);
            if (cont) cont.innerHTML = '<div class="m-empty-state"><i class="ph ph-warning"></i><div class="m-empty-state__msg">Falha ao carregar.</div></div>';
        }
    }
    function renderLoteVinculos(vinculos) {
        const cont = $m('m_ras_loteVinculos');
        if (!cont) return;
        if (!vinculos.length) {
            cont.innerHTML = '<div class="m-empty-state"><i class="ph ph-tray"></i><div class="m-empty-state__title">Nenhum pedido usa este lote ainda</div><div class="m-empty-state__msg">Lote disponível — arme e atribua a um pedido pendente.</div></div>';
            return;
        }
        let html = '';
        vinculos.forEach(v => {
            const top = Number(v.codtipoper);
            const ehNotaSankhya = top === 35 || top === 37;
            const podeDesvincular = top === 34 && v.statusnota !== 'E';
            const statusLabel = ehNotaSankhya
                ? 'NOTA SANKHYA'
                : v.statusnota === 'L' ? 'FATURADO' : 'ATRIBUÍDO';
            const podeDelHtml = podeDesvincular
                ? `<div class="m-ras-vinc-card__action">
                    <button type="button" class="m-ras-vinc-card__btn-del"
                        data-nunota="${escapeHtml(v.nunota)}"
                        data-seq="${escapeHtml(v.sequencia)}">
                        <i class="ph ph-trash"></i> Desvincular
                    </button>
                  </div>`
                : '';
            html += `<div class="m-ras-vinc-card">
                <div class="m-ras-vinc-card__top">
                    <span class="m-ras-vinc-card__num">Pedido ${escapeHtml(v.nunota)}</span>
                    <span class="m-ras-vinc-card__cliente">${escapeHtml(v.nomeparc || '—')}</span>
                    <span class="m-ras-vinc-card__qtd">${fmtQtd(v.qtdneg)}</span>
                </div>
                <div class="m-ras-vinc-card__bottom">
                    <small>${escapeHtml(v.dtneg || '—')}</small>
                    <small>·</small>
                    <small>${escapeHtml(statusLabel)}</small>
                </div>
                ${podeDelHtml}
            </div>`;
        });
        cont.innerHTML = html;

        // Bind desvincular
        cont.querySelectorAll('.m-ras-vinc-card__btn-del').forEach(btn => {
            btn.addEventListener('click', async () => {
                const nu = Number(btn.dataset.nunota);
                const seq = Number(btn.dataset.seq);
                const ok = await IAgro.confirmarAcao({
                    titulo: 'Desvincular lote',
                    mensagem: `Vai remover o vínculo do lote no Pedido ${nu}, SEQ ${seq}.`,
                    tipo: 'aviso',
                });
                if (!ok) return;
                btn.disabled = true;
                const res = await postJSON(URLS.desvincularLote, { nunota: nu, sequencia: seq });
                if (!res.ok || !res.body || !res.body.ok) {
                    mostrarToast((res.body && res.body.error) || 'Falha ao desvincular.', 'error');
                    btn.disabled = false;
                    return;
                }
                mostrarToast('Lote desvinculado.', 'success');
                if (ESTADO.loteSelecionado) abrirDetalheLote(ESTADO.loteSelecionado);
                carregarLotes();
            });
        });
    }

    function bindDetalheLote() {
        const btnArm = $m('m_ras_btnArmar');
        if (btnArm) {
            btnArm.addEventListener('click', () => {
                const lote = ESTADO.loteSelecionado;
                if (!lote) return;
                const isArmed = ESTADO.loteArmado && ESTADO.loteArmado.codagregacao === lote.codagregacao;
                if (isArmed) desarmarLote();
                else armarLote(lote);
            });
        }
        const btnEtiq = $m('m_ras_loteBtnEtiqueta');
        if (btnEtiq) {
            btnEtiq.addEventListener('click', async () => {
                const lote = ESTADO.loteSelecionado;
                if (!lote) return;
                // Imprime etiquetas dos pedidos que usam este lote (filtra por CODPROD).
                // No mobile abrimos uma escolha simples: usa o 1º vínculo encontrado.
                try {
                    const params = new URLSearchParams({ codagregacao: lote.codagregacao });
                    const r = await fetch(URLS.loteVinculos + '?' + params.toString(), {
                        credentials: 'same-origin', cache: 'no-store',
                    });
                    const data = await r.json();
                    const vinculos = (data.vinculos || []).filter(v => Number(v.codtipoper) === 34);
                    if (!vinculos.length) {
                        mostrarToast('Este lote ainda não foi vinculado a um pedido.', 'warning');
                        return;
                    }
                    // Pega o 1º pedido vinculado
                    const v = vinculos[0];
                    await abrirPdfEtiquetas(v.nunota, lote.codprod);
                } catch (err) {
                    mostrarToast('Falha ao buscar vínculos do lote.', 'error');
                }
            });
        }
        const btnFracao = $m('m_ras_loteBtnFracao');
        if (btnFracao) {
            btnFracao.addEventListener('click', () => {
                const lote = ESTADO.loteSelecionado;
                if (lote) avariaAjusteDoLote(lote);
            });
        }
        // Botão back genérico (data-back-to="lista")
        document.querySelectorAll('.rastreio-mobile [data-back-to]').forEach(btn => {
            btn.addEventListener('click', () => {
                popScreen();
            });
        });
    }

    // ===== Tela detalhe do Pedido =====
    function abrirDetalhePedido(ped) {
        ESTADO.pedidoSelecionado = ped;
        // Hero
        $m('m_ras_pedidoCliente').textContent = ped.nomeparc || '—';
        const ehOrfa = ped.tipo_linha === 'NOTA_ORFA';
        $m('m_ras_pedidoNumero').textContent = ehOrfa
            ? `Nota ${ped.numnota || ped.nunota}`
            : `${ped.nunota}`;
        $m('m_ras_pedidoData').textContent = ped.dtneg || '—';

        // Status row
        const statusRow = $m('m_ras_pedidoStatusRow');
        const badge = $m('m_ras_pedidoBadge');
        if (statusRow && badge) {
            if (ehOrfa) {
                statusRow.hidden = false;
                badge.className = 'm-ras-pedido-badge m-ras-pedido-badge--orfa';
                badge.textContent = 'NOTA ÓRFÃ';
            } else if (ped.vinculo_origem === 'TGFVAR' && ped.nota_numnota) {
                statusRow.hidden = false;
                badge.className = 'm-ras-pedido-badge m-ras-pedido-badge--faturado';
                badge.textContent = `Faturado · Nota ${ped.nota_numnota}`;
            } else if (ped.vinculo_origem === 'MANUAL') {
                statusRow.hidden = false;
                badge.className = 'm-ras-pedido-badge m-ras-pedido-badge--manual';
                badge.textContent = 'Vinculado manual';
            } else if (ped.vinculo_origem === 'RETROATIVO') {
                statusRow.hidden = false;
                badge.className = 'm-ras-pedido-badge m-ras-pedido-badge--retroativo';
                badge.textContent = 'Pedido retroativo';
            } else {
                statusRow.hidden = true;
            }
        }

        // Produtos
        renderProdutosPedido(ped.produtos);
        $m('m_ras_pedidoProdCount').textContent = String(ped.produtos.length);

        pushScreen('detalhePedido');
    }
    function renderProdutosPedido(produtos) {
        const cont = $m('m_ras_pedidoProdutos');
        if (!cont) return;
        if (!produtos.length) {
            cont.innerHTML = '<div class="m-empty-state"><i class="ph ph-package"></i><div class="m-empty-state__msg">Pedido sem itens.</div></div>';
            return;
        }
        let html = '';
        produtos.forEach((prod, idx) => {
            const completo = prod.qtd_falta < 0.001;
            const pct = prod.qtd_total > 0 ? Math.round((prod.qtd_atribuida / prod.qtd_total) * 100) : 0;
            const temArmado = ESTADO.loteArmado && Number(ESTADO.loteArmado.codprod) === Number(prod.codprod);
            const cls = `m-ras-prod-card ${completo ? 'is-completo' : 'is-pendente'} ${temArmado ? 'tem-armado' : ''}`;
            const cta = temArmado && !completo
                ? `<div class="m-ras-prod-card__cta"><i class="ph ph-link"></i> Toque pra vincular ${ESTADO.loteArmado.codagregacao}</div>`
                : '';
            html += `<div class="${cls}" data-idx="${idx}">
                <div class="m-ras-prod-card__top">
                    <div class="m-ras-prod-card__nome">${escapeHtml(prod.descrprod || '—')}</div>
                    <div class="m-ras-prod-card__progress">${pct}%</div>
                </div>
                <div class="m-ras-prod-card__qtd">
                    <span><strong>${fmtQtd(prod.qtd_atribuida)}</strong></span>
                    <span>de</span>
                    <span><strong>${fmtQtd(prod.qtd_total)}</strong> kg</span>
                    <span>· Falta <strong>${fmtQtd(prod.qtd_falta)}</strong></span>
                </div>
                <div class="m-ras-prod-card__bar">
                    <div class="m-ras-prod-card__bar-fill" style="width:${pct}%;"></div>
                </div>
                ${cta}
            </div>`;
        });
        cont.innerHTML = html;

        cont.querySelectorAll('.m-ras-prod-card').forEach(card => {
            card.addEventListener('click', () => {
                const idx = Number(card.dataset.idx);
                const prod = produtos[idx];
                if (!prod) return;
                if (prod.qtd_falta < 0.001) {
                    // Completo — mostra modal de vínculos (read-only)
                    abrirVinculosProduto(prod);
                    return;
                }
                if (!ESTADO.loteArmado) {
                    mostrarToast('Arme um lote primeiro tocando no card de lote desejado.', 'info');
                    setListaAtiva('lotes');
                    popToRoot();
                    return;
                }
                if (Number(ESTADO.loteArmado.codprod) !== Number(prod.codprod)) {
                    mostrarToast(`Lote armado é de outro produto (${ESTADO.loteArmado.descrprod}).`, 'warning');
                    return;
                }
                abrirSheetVincular(prod);
            });
        });
    }
    function bindDetalhePedido() {
        const btnEtiq = $m('m_ras_pedidoBtnEtiqueta');
        if (btnEtiq) {
            btnEtiq.addEventListener('click', async () => {
                const ped = ESTADO.pedidoSelecionado;
                if (!ped) return;
                await abrirPdfEtiquetas(ped.nunota);
            });
        }
    }

    // ===== Sheet Vincular =====
    function abrirSheetVincular(prod) {
        const lote = ESTADO.loteArmado;
        if (!lote) return;
        ESTADO.produtoSelecionado = prod;
        const ped = ESTADO.pedidoSelecionado;
        const dispLote = Number(lote.qtd_disponivel) || 0;
        const faltaProd = Number(prod.qtd_falta) || 0;
        // Qtd sugerida:
        //   - Falta > 0 → min(disp, falta)
        //   - Falta = 0 (item zerado/100% vinculado) → sugere disp do lote
        // Nunca sugerir 0 quando há lote disponível — operador precisa de
        // um valor de partida sensato pra editar/confirmar.
        const sugerida = faltaProd > 0.001
            ? Math.min(dispLote, faltaProd)
            : dispLote;

        // Mostra produto + lote em cima; destino = cliente + pedido + qtd a vincular
        $m('m_ras_vincLote').textContent = `${lote.descrprod} · ${lote.codagregacao}`;
        if (ped) {
            const partes = [ped.nomeparc || '—', `Pedido ${ped.nunota}`];
            if (faltaProd > 0.001) partes.push(`Falta ${fmtQtd(faltaProd)} kg`);
            $m('m_ras_vincDestino').textContent = partes.join(' · ');
        } else {
            $m('m_ras_vincDestino').textContent = '—';
        }
        $m('m_ras_vincMaxLote').textContent = fmtQtd(dispLote);
        $m('m_ras_vincMaxPedido').textContent = fmtQtd(faltaProd);
        // Type=number aceita só ponto decimal (não vírgula).
        $m('m_ras_vincQtd').value = String(sugerida.toFixed(2));
        $m('m_ras_vincPeso').value = '';

        openSheet('vincular');
        setTimeout(() => {
            const inp = $m('m_ras_vincQtd');
            if (inp) { inp.focus(); inp.select(); }
        }, 80);
    }
    async function confirmarVincular() {
        const lote = ESTADO.loteArmado;
        const prod = ESTADO.produtoSelecionado;
        const ped = ESTADO.pedidoSelecionado;
        if (!lote || !prod || !ped) return;

        const qtdEl = $m('m_ras_vincQtd');
        const pesoEl = $m('m_ras_vincPeso');
        let qtd = parseFloat((qtdEl?.value || '').toString().replace(',', '.'));
        if (!qtd || qtd <= 0) {
            mostrarToast('Informe uma quantidade válida.', 'warning');
            qtdEl?.focus();
            return;
        }
        const pesoRaw = (pesoEl?.value || '').toString().trim().replace(',', '.');
        let pesoPayload = null;
        if (pesoRaw) {
            const p = parseFloat(pesoRaw);
            if (!isFinite(p) || p <= 0) {
                mostrarToast('Peso da caixa precisa ser número maior que zero, ou em branco.', 'warning');
                pesoEl?.focus();
                return;
            }
            pesoPayload = p;
        }
        const dispLote = Number(lote.qtd_disponivel) || 0;
        const faltaProd = Number(prod.qtd_falta) || 0;
        if (qtd > dispLote + 1e-6) {
            mostrarToast(`Qtd maior que disponível (${fmtQtd(dispLote)}).`, 'warning');
            return;
        }
        if (qtd > faltaProd + 1e-6) {
            mostrarToast(`Qtd maior que faltante no pedido (${fmtQtd(faltaProd)}).`, 'warning');
            return;
        }

        const btn = $m('m_ras_btnConfirmarVinc');
        if (btn) btn.disabled = true;

        // Distribui entre linhas pendentes (igual desktop)
        const linhas = [...prod.linhas_pendentes];
        let restante = qtd;
        let totalOk = 0;
        let erro = null;
        for (const linha of linhas) {
            if (restante < 0.01) break;
            const qLinha = Number(linha.qtd) || 0;
            const qPraLinha = Math.min(restante, qLinha);
            if (qPraLinha <= 0) continue;
            const r = await postJSON(URLS.atribuirLote, {
                nunota: ped.nunota,
                sequencia: linha.sequencia,
                codagregacao: lote.codagregacao,
                qtd: qPraLinha,
                peso: pesoPayload,
            });
            if (!r.ok || !r.body || !r.body.ok) {
                erro = (r.body && r.body.error) || 'Falha ao atribuir lote.';
                break;
            }
            restante -= qPraLinha;
            totalOk += qPraLinha;
        }
        if (btn) btn.disabled = false;

        if (erro && totalOk === 0) {
            mostrarToast(erro, 'error');
            return;
        }
        if (erro) {
            mostrarToast(`Vinculado ${fmtQtd(totalOk)} antes do erro: ${erro}`, 'warning');
        } else {
            mostrarToast(`Lote ${lote.codagregacao} vinculado: ${fmtQtd(totalOk)} kg.`, 'success');
        }
        closeSheet('vincular');
        // Após vínculo bem-sucedido: SEMPRE volta pra lista de Lotes +
        // desarma. Ciclo completo (armar → vincular) finaliza e operador
        // escolhe próximo lote sem ruído de filtro residual ou tela vazia.
        ESTADO.loteArmado = null;
        atualizarBarArmado();
        if (telaAtiva !== 'lista') popToRoot();
        setListaAtiva('lotes');

        // Atualização local INSTANTÂNEA do estoque do lote (vinculado).
        // A tabela materializada AD_SALDO_LOTE_CACHE só atualiza por cron
        // a cada 5min, então sem isso o lote continua aparecendo na lista
        // com saldo antigo até o próximo refresh natural. Atualizar o
        // ESTADO em JS dá feedback imediato pro operador.
        //
        // ⚠ NÃO disparamos `POST /refresh-saldo/` aqui (TRUNCATE+INSERT
        // de ~12s) porque queries em paralelo que fazem JOIN nessa tabela
        // (ex: consultar_pedidos_abertos) dão 500 durante a janela do
        // refresh. Operador força refresh manual via FAB "Mais" se quiser
        // sincronizar com o cron antes dos 5min.
        const loteAfetado = ESTADO.lotesData.find(l => l.codagregacao === lote.codagregacao);
        if (loteAfetado) {
            loteAfetado.qtd_disponivel = Math.max(
                0, (Number(loteAfetado.qtd_disponivel) || 0) - totalOk
            );
            // Se zerou, remove do array (lista limpa)
            if ((Number(loteAfetado.qtd_disponivel) || 0) < 0.01) {
                ESTADO.lotesData = ESTADO.lotesData.filter(
                    l => l.codagregacao !== lote.codagregacao
                );
            }
        }
        renderLotesLista();   // reflete saldo atualizado de imediato
    }
    function bindSheetVincular() {
        const btn = $m('m_ras_btnConfirmarVinc');
        if (btn) btn.addEventListener('click', confirmarVincular);
        const qtdEl = $m('m_ras_vincQtd');
        if (qtdEl) {
            qtdEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); confirmarVincular(); }
            });
        }
    }

    // ===== Modal de vínculos de produto (read-only) =====
    function abrirVinculosProduto(prod) {
        // Reusa o modal de vínculos do desktop (já está renderizado em .rastreio-desktop)
        // mas como ele está dentro de .rastreio-desktop oculto, criamos via toast info
        if (!prod.lotes_vinculados.length) {
            mostrarToast('Sem vínculos pra mostrar.', 'info');
            return;
        }
        let txt = `Lotes vinculados:\n`;
        prod.lotes_vinculados.forEach(lv => {
            txt += `• ${lv.codagregacao}: ${fmtQtd(lv.qtd)} kg\n`;
        });
        alert(txt);
    }

    // ===== Etiquetas (PDF) com resolução de peso =====
    async function abrirPdfEtiquetas(nunota, codprod) {
        const baseUrl = `${URLS.etiqueta}?nunota=${encodeURIComponent(nunota)}`
            + (codprod ? `&codprod=${encodeURIComponent(codprod)}` : '');
        const resolverUrl = `${URLS.resolverPeso}?nunota=${encodeURIComponent(nunota)}`
            + (codprod ? `&codprod=${encodeURIComponent(codprod)}` : '');
        try {
            const r = await fetch(resolverUrl, { credentials: 'same-origin' });
            if (!r.ok) {
                let msg = `Erro ${r.status}`;
                try { const b = await r.json(); msg = b.error || msg; } catch (_) {}
                mostrarToast(msg, 'error');
                return;
            }
            const body = await r.json();
            if (!body.ok) {
                mostrarToast(body.error || 'Erro ao resolver peso.', 'error');
                return;
            }
            if (!body.precisa_escolha) {
                window.open(baseUrl, '_blank');
                return;
            }
            // Abre sheet de escolha de peso
            const overrides = await escolhaPesoSheet(body.itens);
            if (overrides === null) return;
            const partes = Object.entries(overrides).map(([seq, val]) => `${seq}:${val}`);
            window.open(baseUrl + '&pesos=' + encodeURIComponent(partes.join(',')), '_blank');
        } catch (err) {
            console.error('[ras-mobile] etiqueta', err);
            mostrarToast('Falha de rede ao preparar etiqueta.', 'error');
        }
    }
    function escolhaPesoSheet(itens) {
        return new Promise(resolve => {
            const lista = $m('m_ras_escolhaPesoLista');
            const btnOk = $m('m_ras_btnConfirmarEscolhaPeso');
            if (!lista || !btnOk) { resolve(null); return; }
            const pendentes = (itens || []).filter(it => it.precisa_escolha);
            lista.innerHTML = pendentes.map(it => {
                const pesos = (it.pesos_top26 || []).map((p, idx) => `
                    <button type="button" class="m-ras-escolha-item__peso ${idx === 0 ? 'is-active' : ''}"
                        data-seq="${it.sequencia}" data-peso="${p}">${fmtQtd(p)} kg</button>
                `).join('');
                return `<div class="m-ras-escolha-item" data-seq="${it.sequencia}">
                    <div class="m-ras-escolha-item__titulo">${escapeHtml(it.descrprod || '—')} · ${fmtQtd(it.qtdneg || 0)} kg</div>
                    <div class="m-ras-escolha-item__pesos">${pesos}</div>
                </div>`;
            }).join('');

            // Bind: 1 peso ativo por SEQ
            lista.querySelectorAll('.m-ras-escolha-item__peso').forEach(b => {
                b.addEventListener('click', () => {
                    const seq = b.dataset.seq;
                    lista.querySelectorAll(`.m-ras-escolha-item__peso[data-seq="${seq}"]`).forEach(o => o.classList.remove('is-active'));
                    b.classList.add('is-active');
                });
            });

            const onOk = () => {
                const out = {};
                pendentes.forEach(it => {
                    const sel = lista.querySelector(`.m-ras-escolha-item__peso[data-seq="${it.sequencia}"].is-active`);
                    if (sel) out[it.sequencia] = parseFloat(sel.dataset.peso);
                });
                btnOk.removeEventListener('click', onOk);
                document.querySelectorAll('.rastreio-mobile .m-sheet[data-sheet="escolhaPeso"] [data-close-sheet]')
                    .forEach(b => b.removeEventListener('click', onCanc));
                closeSheet('escolhaPeso');
                resolve(out);
            };
            const onCanc = () => {
                btnOk.removeEventListener('click', onOk);
                closeSheet('escolhaPeso');
                resolve(null);
            };
            btnOk.addEventListener('click', onOk);
            document.querySelectorAll('.rastreio-mobile .m-sheet[data-sheet="escolhaPeso"] [data-close-sheet]')
                .forEach(b => b.addEventListener('click', onCanc, { once: true }));

            openSheet('escolhaPeso');
        });
    }

    // ===== Refresh saldo =====
    async function refrescarSaldoEManter() {
        const fab = $m('m_ras_fabRefresh');
        if (fab) fab.classList.add('is-loading');
        try {
            const r = await postJSON(URLS.refreshSaldo, {});
            if (r.ok && r.body && r.body.ok) {
                mostrarToast(`Saldo atualizado: ${r.body.rows} lotes em ${r.body.duracao_s}s`, 'success');
            } else {
                mostrarToast((r.body && r.body.error) || 'Falha ao atualizar saldo.', 'error');
            }
        } catch (err) {
            mostrarToast('Erro de rede ao atualizar saldo.', 'error');
        } finally {
            if (fab) fab.classList.remove('is-loading');
            carregarAtual();
        }
    }

    // ===== Busca server-side =====
    const buscaDebouncedLotes = debounce(() => carregarLotes(), 280);
    const buscaDebouncedPedidos = debounce(() => carregarPedidos(), 280);
    function bindBusca() {
        const inp = $m('m_ras_search');
        if (!inp) return;
        inp.addEventListener('input', () => {
            ESTADO.textoBusca = (inp.value || '').trim();
            if (ESTADO.listaAtiva === 'lotes') buscaDebouncedLotes();
            else buscaDebouncedPedidos();
        });
    }

    // ===== Hambúrguer (abre sidebar global) =====
    function bindHamburger() {
        const btn = $m('m_ras_btnHamb');
        if (!btn) return;
        btn.addEventListener('click', () => {
            // Reusa o toggle global da sidebar via IAgro.setupSidebar
            const sb = document.getElementById('appSidebar');
            if (sb) sb.classList.add('open');
            // Backdrop genérico se houver
            const bd = document.getElementById('sidebarBackdrop');
            if (bd) bd.classList.add('show');
        });
    }

    // ===== FAB refresh =====
    function bindFabRefresh() {
        const fab = $m('m_ras_fabRefresh');
        if (!fab) return;
        fab.addEventListener('click', refrescarSaldoEManter);
    }

    // ===== Desarmar (bar armado) =====
    function bindBarArmadoDesarmar() {
        const btn = $m('m_ras_btnDesarmar');
        if (btn) btn.addEventListener('click', desarmarLote);
    }

    // ===== Boot =====
    function boot() {
        inicializarFiltrosDefault();
        bindFiltrosSheet();
        bindBottomNav();
        bindToggleLista();
        bindToggleAgrupamento();
        bindBusca();
        bindDetalheLote();
        bindDetalhePedido();
        bindSheetVincular();
        bindFabRefresh();
        bindBarArmadoDesarmar();
        bindHamburger();
        setupSheetClosers();
        setupSwipeToBack();
        setListaAtiva('lotes');
        carregarLotes();
        carregarPedidos();   // carrega pedidos em segundo plano pra contador
        atualizarBadgeFiltros();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
