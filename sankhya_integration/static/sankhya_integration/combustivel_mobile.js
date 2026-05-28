/* ============================================================================
   📱 Módulo Combustível — Frontend Mobile (Mai/2026 — 2026-05-28)
   Auto-ativa em viewport ≤900px. Reusa endpoints do desktop combustivel.js.
   ============================================================================ */
(function () {
    'use strict';

    // Só ativa em mobile
    if (!window.matchMedia('(max-width: 900px)').matches) return;

    // =========================================================================
    // Endpoints (mesmos do desktop)
    // =========================================================================
    const URL_ESTOQUE       = '/sankhya/combustivel/api/estoque/';
    const URL_VEICULOS      = '/sankhya/combustivel/api/veiculos/';
    const URL_PRODUTOS      = '/sankhya/combustivel/api/produtos/';
    const URL_MOVIMENTACOES = '/sankhya/combustivel/api/movimentacoes/';
    const URL_REQ_CRIAR     = '/sankhya/combustivel/api/requisicao/criar/';
    const URL_EXT_CRIAR     = '/sankhya/combustivel/api/abastecimento-externo/criar/';
    const URL_ENT_CRIAR     = '/sankhya/combustivel/api/entrada/criar/';
    const URL_RELATORIO     = '/sankhya/combustivel/api/relatorio/consumo/';
    const URL_CENCUS        = '/sankhya/cencus/search/';
    const URL_EMPRESAS      = '/sankhya/empresa/search/';
    const URL_PARCEIROS     = '/sankhya/parceiros/search/';
    const URL_NATUREZAS     = '/sankhya/natureza/search/';
    const URL_TIPVENDA      = '/sankhya/tipvenda/search/';
    const STATIC_VEICULOS   = '/static/sankhya_integration/img/veiculos/';

    const DEFAULT_CODCENCUS  = 10100;
    const DEFAULT_CODNAT     = 30070200;
    const DEFAULT_CODTIPVENDA = 11;

    const CODPRODS_DIESEL = new Set([392, 1373]);
    const CODPROD_ARLA = 1374;
    const PALAVRAS_MAQ = ['TRATOR','COLHEIT','MAQUINA','PULVERIZ','ROCADEIR','ROÇADEIR','PLANTADEIR'];

    const SWIPE_REVEAL = 88;    // 2 botões 44px (edit + del)
    const SWIPE_TRIGGER = 44;   // 50% do reveal

    const PREFS_KEY = 'iagro:combustivel:prefs:v1';

    // =========================================================================
    // Estado
    // =========================================================================
    const ESTADO = {
        ctx: 'estoque',                  // estoque | movimentacoes | veiculos
        screen: 'lista',                 // lista | detalheVeiculo | fotoLightbox

        // Estoque
        tanques: [],

        // Movimentações
        movItems: [],
        movDataIni: null,
        movDataFim: null,
        filtroMov: '',                   // '' | ENTRADA | REQUISICAO
        filtroTipo: '',                  // '' | INTERNA_FROTA | INTERNA_MAQUINARIO

        // Veículos
        veiculos: [],
        veiculosFiltro: 'COM',           // COM | MAQ
        veiculoTextoBusca: '',

        // Detalhe veículo
        detalheCodvei: null,
        detalheVeiculo: null,            // {placa, marcamodelo, especietipo, proprio, nomeparc}
        detalheAbastecimentos: [],

        // Requisição (sheet)
        reqEditandoNunota: null,
        reqExtItens: [],                 // [{_seq, codprod, descrprod, qtd, vlrunit, vlrtot}]
        _reqExtSeq: 0,

        // Entrada (sheet)
        entEditandoNunota: null,
        entItens: [],                    // [{_seq, codprod, descrprod, qtd, vlrunit}]
        _entSeq: 0,

        // Excluir (sheet compartilhado)
        excluirNunota: null,
        excluirTipo: null,               // 'req' | 'ent'

        // Lightbox
        lightboxPlaca: '',
        lightboxLegenda: '',

        // Navegação
        screenStack: ['lista'],
    };

    // =========================================================================
    // Helpers gerais
    // =========================================================================
    function $(id) { return document.getElementById(id); }
    function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

    function formatNumero(n, casas) {
        if (n === null || n === undefined || isNaN(n)) return '—';
        const c = casas !== undefined ? casas : 2;
        return Number(n).toLocaleString('pt-BR', { minimumFractionDigits: c, maximumFractionDigits: c });
    }

    function formatBRL(n) {
        if (n === null || n === undefined || isNaN(n) || n === 0) return '—';
        return Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function formatData(s) {
        if (!s) return '—';
        const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? `${m[3]}/${m[2]}/${m[1]}` : s;
    }

    function hoje() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    }

    function _hojeIso() { return hoje(); }
    function _primeiroDiaMesIso() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`;
    }
    function _shiftIso(iso, deltaDias) {
        try {
            let d = iso ? new Date(iso + 'T12:00:00') : new Date();
            if (isNaN(d.getTime())) d = new Date();
            d.setDate(d.getDate() + deltaDias);
            return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        } catch (_) { return iso || _hojeIso(); }
    }

    function _categoriaCombustivel(codprod) {
        const cp = parseInt(codprod, 10);
        if (CODPRODS_DIESEL.has(cp)) return 'DIESEL';
        if (cp === CODPROD_ARLA) return 'ARLA';
        return 'OUTRO';
    }

    function classificarVeiculo(v) {
        const esp = String(v.especietipo || '').toUpperCase();
        for (const palavra of PALAVRAS_MAQ) {
            if (esp.indexOf(palavra) >= 0) return 'MAQ';
        }
        return 'COM';
    }

    function pathFotoVeiculo(placa, tamanho) {
        if (!placa) return STATIC_VEICULOS + '_placeholder.svg';
        const p = String(placa).trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
        const qs = tamanho === 'thumb' ? '?size=thumb' : '';
        return `/sankhya/combustivel/api/veiculo-foto/${encodeURIComponent(p)}/${qs}`;
    }

    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function normalizar(s) {
        return String(s || '').toLowerCase().normalize('NFD')
            .replace(/[̀-ͯ]/g, '');
    }

    function mostrarToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) IAgro.showToast(msg, tipo || 'info');
        else alert(msg);
    }

    // Cálculo de consumo (km percorridos + km/L) — replica desktop linha 76
    function _calcularConsumoMov(items) {
        const grupos = {};
        items.forEach(it => {
            const r = it.requisicao || {};
            const cv = r.codveiculo;
            const hod = parseFloat(r.hodometro_km);
            if (!cv || !hod || hod <= 0) return;
            const categoria = _categoriaCombustivel(it.codprod);
            if (categoria === 'OUTRO') return;
            const key = `${cv}-${categoria}`;
            if (!grupos[key]) grupos[key] = { categoria, arr: [] };
            grupos[key].arr.push({
                chave: `${it.nunota}-${it.sequencia || 0}`,
                dtneg: it.dtneg || '',
                nunota: it.nunota,
                hod: hod,
                qtd: parseFloat(it.qtdneg_item) || 0,
            });
        });
        const out = {};
        Object.values(grupos).forEach(g => {
            g.arr.sort((a, b) => {
                if (a.dtneg !== b.dtneg) return a.dtneg.localeCompare(b.dtneg);
                return a.nunota - b.nunota;
            });
            for (let i = 1; i < g.arr.length; i++) {
                const km = g.arr[i].hod - g.arr[i - 1].hod;
                const qtdAnt = g.arr[i - 1].qtd;
                if (km > 0) {
                    out[g.arr[i].chave] = {
                        km_percorridos: km,
                        kmlt: qtdAnt > 0 ? (km / qtdAnt) : null,
                        categoria: g.categoria,
                    };
                }
            }
        });
        return out;
    }

    // Triangular qtd <-> vlrunit <-> vlrtot (EXTERNA_POSTO)
    function _recalcularItem(item, campoEditado) {
        const qt = parseFloat(item.qtd)     || 0;
        const vu = parseFloat(item.vlrunit) || 0;
        const vt = parseFloat(item.vlrtot)  || 0;
        if (campoEditado === 'qtd' || campoEditado === 'vlrunit') {
            if (qt > 0 && vu > 0) item.vlrtot = qt * vu;
        } else if (campoEditado === 'vlrtot') {
            if (qt > 0) item.vlrunit = vt / qt;
        }
    }

    // =========================================================================
    // Renderização de tanque SVG (copiado do desktop combustivel.js linha 158)
    // =========================================================================
    function _classesTanque(pct) {
        let fluido = 'cb-tanque-fluido--ok';
        let saldo = '';
        if (pct <= 0) { fluido = 'cb-tanque-fluido--zero'; saldo = 'cb-tanque-saldo--crit'; }
        else if (pct < 10) { fluido = 'cb-tanque-fluido--crit'; saldo = 'cb-tanque-saldo--crit'; }
        else if (pct < 30) { fluido = 'cb-tanque-fluido--aviso'; saldo = 'cb-tanque-saldo--aviso'; }
        return { fluido, saldo };
    }

    function renderTanqueSVG(it) {
        const formato = (it.formato || 'CILINDRO_HORIZONTAL').toUpperCase();
        if (formato === 'CAIXA_QUADRADA') return renderTanqueQuadradoSVG(it);
        return renderTanqueCilindricoSVG(it);
    }

    function renderTanqueCilindricoSVG(it) {
        const pct = Math.max(0, Math.min(100, Number(it.percentual || 0)));
        const capacidade = Number(it.capacidade_lt || 0);
        const codvol = it.codvol || 'LT';
        const { fluido: cls, saldo: saldoCls } = _classesTanque(pct);
        const TANK_X = 24, TANK_Y = 20, TANK_W = 252, TANK_H = 80, ELIPSE_RX = 10;
        const fluidoH = (TANK_H * pct) / 100;
        const fluidoY = TANK_Y + (TANK_H - fluidoH);
        const clipId = `clip-tanque-m-${it.codprod}`;
        const saldoSvgCls = saldoCls.replace('cb-tanque-saldo--', 'cb-tanque-saldo-svg--');
        return `
            <div class="cb-tanque" title="Capacidade: ${formatNumero(capacidade, 0)} ${codvol}">
                <div class="cb-tanque-cabeca">
                    <p class="cb-tanque-nome">${escapeHtml(it.descrprod || ('Produto ' + it.codprod))}</p>
                    <p class="cb-tanque-capacidade">capacidade ${formatNumero(capacidade, 0)} ${codvol}</p>
                </div>
                <div class="cb-tanque-svg">
                    <svg viewBox="0 0 300 120" preserveAspectRatio="none">
                        <defs><clipPath id="${clipId}">
                            <rect x="${TANK_X}" y="${TANK_Y}" width="${TANK_W}" height="${TANK_H}"/>
                        </clipPath></defs>
                        <rect x="${TANK_X}" y="${TANK_Y}" width="${TANK_W}" height="${TANK_H}" class="cb-tanque-corpo"/>
                        <rect class="cb-tanque-fluido ${cls}" x="${TANK_X}" y="${fluidoY}"
                              width="${TANK_W}" height="${fluidoH}" clip-path="url(#${clipId})"/>
                        <ellipse cx="${TANK_X}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="${ELIPSE_RX}" ry="${TANK_H / 2}" class="cb-tanque-elipse-frente"/>
                        <ellipse cx="${TANK_X + TANK_W}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="${ELIPSE_RX}" ry="${TANK_H / 2}" class="cb-tanque-elipse-frente"/>
                        <ellipse cx="${TANK_X + TANK_W / 3}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="3" ry="${TANK_H / 2}" class="cb-tanque-anel"/>
                        <ellipse cx="${TANK_X + 2 * TANK_W / 3}" cy="${TANK_Y + TANK_H / 2}"
                                 rx="3" ry="${TANK_H / 2}" class="cb-tanque-anel"/>
                        <rect x="${TANK_X + TANK_W / 2 - 10}" y="${TANK_Y - 6}" width="20" height="6" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W / 2 - 4}" y="${TANK_Y - 12}" width="8" height="6" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W}" y="${TANK_Y + TANK_H - 14}" width="${ELIPSE_RX + 4}" height="5" class="cb-tanque-valvula"/>
                        <path d="M ${TANK_X + 18} ${TANK_Y + TANK_H} L ${TANK_X + 8} ${TANK_Y + TANK_H + 10}
                                 L ${TANK_X + 50} ${TANK_Y + TANK_H + 10} L ${TANK_X + 40} ${TANK_Y + TANK_H} Z" class="cb-tanque-berco"/>
                        <path d="M ${TANK_X + TANK_W - 40} ${TANK_Y + TANK_H} L ${TANK_X + TANK_W - 50} ${TANK_Y + TANK_H + 10}
                                 L ${TANK_X + TANK_W - 8} ${TANK_Y + TANK_H + 10} L ${TANK_X + TANK_W - 18} ${TANK_Y + TANK_H} Z" class="cb-tanque-berco"/>
                        <rect x="${TANK_X - 5}" y="${TANK_Y + TANK_H + 10}" width="${TANK_W + 10}" height="2" class="cb-tanque-base"/>
                    </svg>
                    <div class="cb-tanque-overlay">
                        <div class="cb-tanque-saldo-svg ${saldoSvgCls}">
                            ${formatNumero(it.qtd_disponivel, 0)} ${codvol}
                        </div>
                        <div class="cb-tanque-pct-svg">${pct.toFixed(0)}%</div>
                    </div>
                </div>
                <div class="cb-tanque-rodape">
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--ent">
                        ↓ ent <strong>${formatNumero(it.qtd_entrada, 2)}</strong>
                    </span>
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--sai">
                        ↑ sai <strong>${formatNumero(it.qtd_saida, 2)}</strong>
                    </span>
                </div>
            </div>
        `;
    }

    function renderTanqueQuadradoSVG(it) {
        const pct = Math.max(0, Math.min(100, Number(it.percentual || 0)));
        const capacidade = Number(it.capacidade_lt || 0);
        const codvol = it.codvol || 'LT';
        const { fluido: cls, saldo: saldoCls } = _classesTanque(pct);
        const TANK_X = 80, TANK_Y = 14, TANK_W = 140, TANK_H = 100;
        const fluidoH = (TANK_H * pct) / 100;
        const fluidoY = TANK_Y + (TANK_H - fluidoH);
        const clipId = `clip-tanque-q-m-${it.codprod}`;
        const grade = [];
        for (let i = 1; i <= 3; i++) {
            const x = TANK_X + (TANK_W * i / 4);
            grade.push(`<line x1="${x}" y1="${TANK_Y}" x2="${x}" y2="${TANK_Y + TANK_H}" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="2,2"/>`);
        }
        for (let i = 1; i <= 3; i++) {
            const y = TANK_Y + (TANK_H * i / 4);
            grade.push(`<line x1="${TANK_X}" y1="${y}" x2="${TANK_X + TANK_W}" y2="${y}" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="2,2"/>`);
        }
        const saldoSvgCls = saldoCls.replace('cb-tanque-saldo--', 'cb-tanque-saldo-svg--');
        return `
            <div class="cb-tanque" title="Capacidade: ${formatNumero(capacidade, 0)} ${codvol}">
                <div class="cb-tanque-cabeca">
                    <p class="cb-tanque-nome">${escapeHtml(it.descrprod || ('Produto ' + it.codprod))}</p>
                    <p class="cb-tanque-capacidade">capacidade ${formatNumero(capacidade, 0)} ${codvol}</p>
                </div>
                <div class="cb-tanque-svg">
                    <svg viewBox="0 0 300 120" preserveAspectRatio="none">
                        <defs><clipPath id="${clipId}">
                            <rect x="${TANK_X}" y="${TANK_Y}" width="${TANK_W}" height="${TANK_H}" rx="3" ry="3"/>
                        </clipPath></defs>
                        <rect x="${TANK_X}" y="${TANK_Y}" width="${TANK_W}" height="${TANK_H}" rx="3" ry="3" class="cb-tanque-corpo"/>
                        <rect class="cb-tanque-fluido ${cls}" x="${TANK_X}" y="${fluidoY}"
                              width="${TANK_W}" height="${fluidoH}" clip-path="url(#${clipId})"/>
                        ${grade.join('')}
                        <rect x="${TANK_X + TANK_W / 2 - 12}" y="${TANK_Y - 8}" width="24" height="8" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W / 2 - 6}" y="${TANK_Y - 12}" width="12" height="4" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X + TANK_W - 6}" y="${TANK_Y + TANK_H - 14}" width="12" height="6" class="cb-tanque-valvula"/>
                        <rect x="${TANK_X - 6}" y="${TANK_Y + TANK_H}" width="${TANK_W + 12}" height="6" class="cb-tanque-base"/>
                    </svg>
                    <div class="cb-tanque-overlay">
                        <div class="cb-tanque-saldo-svg ${saldoSvgCls}">
                            ${formatNumero(it.qtd_disponivel, 0)} ${codvol}
                        </div>
                        <div class="cb-tanque-pct-svg">${pct.toFixed(0)}%</div>
                    </div>
                </div>
                <div class="cb-tanque-rodape">
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--ent">
                        ↓ ent <strong>${formatNumero(it.qtd_entrada, 2)}</strong>
                    </span>
                    <span class="cb-tanque-rodape-item cb-tanque-rodape-item--sai">
                        ↑ sai <strong>${formatNumero(it.qtd_saida, 2)}</strong>
                    </span>
                </div>
            </div>
        `;
    }

    // =========================================================================
    // Navegação entre telas
    // =========================================================================
    function setActiveScreen(name) {
        fecharTodosSwipes();
        $$('.combustivel-mobile .m-screen').forEach(el => {
            el.classList.toggle('is-active', el.dataset.screen === name);
        });
        ESTADO.screen = name;
    }

    function pushScreen(name) {
        ESTADO.screenStack.push(name);
        setActiveScreen(name);
        history.pushState({ screen: name }, '', '');
    }

    function popScreen() {
        if (ESTADO.screenStack.length > 1) {
            ESTADO.screenStack.pop();
            const prev = ESTADO.screenStack[ESTADO.screenStack.length - 1];
            setActiveScreen(prev);
        }
    }

    // =========================================================================
    // Bottom sheets
    // =========================================================================
    function openSheet(name) {
        fecharTodosSwipes();
        const sh = document.querySelector(`.combustivel-mobile .m-sheet[data-sheet="${name}"]`);
        if (!sh) return;
        sh.setAttribute('aria-hidden', 'false');
    }

    function closeSheet(name) {
        const sh = document.querySelector(`.combustivel-mobile .m-sheet[data-sheet="${name}"]`);
        if (!sh) return;
        sh.setAttribute('aria-hidden', 'true');
    }

    function closeAllSheets() {
        $$('.combustivel-mobile .m-sheet').forEach(sh => {
            sh.setAttribute('aria-hidden', 'true');
        });
    }

    // =========================================================================
    // Swipe gestures
    // =========================================================================
    function fecharTodosSwipes() {
        $$('.combustivel-mobile [data-swipe-open="1"]').forEach(wrap => {
            const card = wrap.querySelector('.m-cb-mov-card');
            if (card) card.style.transform = '';
            wrap.dataset.swipeOpen = '0';
        });
    }

    function attachSwipe(wrap, card, onEdit, onDelete) {
        let startX = 0, startY = 0, currentX = 0, axisLocked = null;
        let opened = false;

        function onTouchStart(e) {
            const t = e.touches ? e.touches[0] : e;
            startX = t.clientX;
            startY = t.clientY;
            currentX = wrap.dataset.swipeOpen === '1' ? -SWIPE_REVEAL : 0;
            axisLocked = null;
        }

        function onTouchMove(e) {
            const t = e.touches ? e.touches[0] : e;
            const dx = t.clientX - startX;
            const dy = t.clientY - startY;

            if (axisLocked === null) {
                if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
                    axisLocked = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                }
            }
            if (axisLocked !== 'x') return;

            e.preventDefault();
            let novoX = currentX + dx;
            if (novoX > 0) novoX = novoX * 0.3;   // elastic
            else if (novoX < -SWIPE_REVEAL) {
                const over = Math.abs(novoX) - SWIPE_REVEAL;
                novoX = -SWIPE_REVEAL - over * 0.3;
            }
            card.style.transform = `translateX(${novoX}px)`;
        }

        function onTouchEnd(e) {
            const t = (e.changedTouches && e.changedTouches[0]) || e;
            const dx = t.clientX - startX;
            const total = currentX + dx;
            if (total < -SWIPE_TRIGGER) {
                card.style.transform = `translateX(-${SWIPE_REVEAL}px)`;
                wrap.dataset.swipeOpen = '1';
            } else {
                card.style.transform = '';
                wrap.dataset.swipeOpen = '0';
            }
        }

        card.addEventListener('touchstart', onTouchStart, { passive: true });
        card.addEventListener('touchmove', onTouchMove, { passive: false });
        card.addEventListener('touchend', onTouchEnd, { passive: true });

        // Click no card já em swipe-open fecha o swipe ("cancelar implícito")
        card.addEventListener('click', (e) => {
            if (wrap.dataset.swipeOpen === '1') {
                card.style.transform = '';
                wrap.dataset.swipeOpen = '0';
                e.preventDefault();
                e.stopPropagation();
            }
        });
    }

    function setupSwipeToBack() {
        const telas = $$('.combustivel-mobile .m-screen');
        telas.forEach(tela => {
            if (tela.dataset.screen === 'lista') return;
            let startX = 0, startY = 0, axisLocked = null, startTime = 0;

            tela.addEventListener('touchstart', (e) => {
                const t = e.touches[0];
                startX = t.clientX;
                startY = t.clientY;
                startTime = Date.now();
                axisLocked = null;
            }, { passive: true });

            tela.addEventListener('touchmove', (e) => {
                const t = e.touches[0];
                const dx = t.clientX - startX;
                const dy = t.clientY - startY;
                if (axisLocked === null && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
                    axisLocked = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                }
            }, { passive: true });

            tela.addEventListener('touchend', (e) => {
                if (axisLocked !== 'x') return;
                const t = e.changedTouches[0];
                const dx = t.clientX - startX;
                const dt = Date.now() - startTime;
                const v = Math.abs(dx) / Math.max(dt, 1);
                if (dx > window.innerWidth * 0.35 || (dx > 50 && v > 0.5)) {
                    popScreen();
                }
            }, { passive: true });
        });
    }

    // =========================================================================
    // Carregamento de dados
    // =========================================================================
    async function carregarEstoque() {
        const wrap = $('m_cb_tanques');
        if (!wrap) return;
        wrap.innerHTML = '<div class="m-empty">Carregando…</div>';
        try {
            const resp = await fetch(URL_ESTOQUE, { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) {
                wrap.innerHTML = `<div class="m-empty">${escapeHtml(data.error || 'Falha ao carregar estoque.')}</div>`;
                return;
            }
            const items = data.items || [];
            if (items.length === 0) {
                wrap.innerHTML = '<div class="m-empty">Nenhum tanque mapeado.</div>';
                return;
            }
            ESTADO.tanques = items;
            wrap.innerHTML = items.map(renderTanqueSVG).join('');
        } catch (err) {
            wrap.innerHTML = '<div class="m-empty">Falha de conexão.</div>';
        }
    }

    async function carregarMovimentacoes() {
        // Em modo detalhe veículo: carrega o relatório do veículo
        if (ESTADO.screen === 'detalheVeiculo' && ESTADO.detalheCodvei) {
            return carregarDetalheVeiculo();
        }

        const wrap = $('m_cb_movList');
        if (!wrap) return;
        wrap.innerHTML = '<div class="m-empty">Carregando…</div>';

        const params = new URLSearchParams();
        if (ESTADO.filtroMov) params.set('mov', ESTADO.filtroMov);
        if (ESTADO.filtroTipo) params.set('tipo', ESTADO.filtroTipo);
        if (ESTADO.movDataIni) params.set('date_start', ESTADO.movDataIni);
        if (ESTADO.movDataFim) params.set('date_end', ESTADO.movDataFim);
        params.set('limit', '100');

        try {
            const resp = await fetch(`${URL_MOVIMENTACOES}?${params.toString()}`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) {
                wrap.innerHTML = `<div class="m-empty">${escapeHtml(data.error || 'Falha.')}</div>`;
                return;
            }
            const items = data.items || [];
            ESTADO.movItems = items;
            renderMovList(wrap, items);
            atualizarBadgeFiltros();
        } catch (err) {
            wrap.innerHTML = '<div class="m-empty">Falha de conexão.</div>';
        }
    }

    function renderMovList(wrap, items) {
        if (items.length === 0) {
            wrap.innerHTML = '<div class="m-empty">Nenhuma movimentação no período/filtros.</div>';
            return;
        }
        const consumoPorChave = _calcularConsumoMov(items);
        wrap.innerHTML = items.map(it => renderMovCard(it, consumoPorChave)).join('');
        bindMovCards(wrap);
    }

    function renderMovCard(it, consumoPorChave) {
        const r = it.requisicao || {};
        const ehReq = it.tipo_movimento === 'REQUISICAO';
        const ehExterno = ehReq && r.tipo === 'EXTERNA_POSTO';
        const parceiroOuVei = ehReq ? (r.placa || it.nomeparc || '—') : (it.nomeparc || '—');

        let iconeCls, ico;
        if (ehExterno) { iconeCls = 'm-cb-mov-icone--ext'; ico = 'ph-globe'; }
        else if (ehReq) { iconeCls = 'm-cb-mov-icone--req'; ico = 'ph-clipboard-text'; }
        else { iconeCls = 'm-cb-mov-icone--ent'; ico = 'ph-tray-arrow-down'; }

        let badge = '';
        if (ehExterno) badge = '<span class="m-cb-mov-badge m-cb-mov-badge--ext">EXTERNA</span>';
        else if (ehReq && r.tipo === 'INTERNA_FROTA') badge = '<span class="m-cb-mov-badge m-cb-mov-badge--frota">Interna</span>';
        else if (ehReq && r.tipo === 'INTERNA_MAQUINARIO') badge = '<span class="m-cb-mov-badge m-cb-mov-badge--maq">Máquina</span>';

        // Total km + Média
        const chave = `${it.nunota}-${it.sequencia || 0}`;
        const consumo = consumoPorChave[chave];
        let consumoHtml = '';
        if (consumo && consumo.kmlt) {
            const cls = consumo.categoria === 'ARLA' ? 'm-cb-mov-consumo--arla' : 'm-cb-mov-consumo--diesel';
            const sup = consumo.categoria === 'ARLA' ? '<sup>ARLA</sup>' : '';
            consumoHtml = `<span class="m-cb-mov-consumo ${cls}">${formatNumero(consumo.kmlt, 2)} km/L${sup}</span>`;
        }

        // Pode editar/excluir?
        const podeReqInterna = ehReq && !ehExterno && it.statusnota !== 'L' && it.statusnota !== 'E';
        const podeReqExterna = ehExterno && it.statusnota !== 'E';
        const podeReq = podeReqInterna || podeReqExterna;
        const podeEnt = !ehReq && it.statusnota !== 'E';
        const podeEditar = podeReq || podeEnt;
        const tipoAcao = ehReq ? 'req' : 'ent';
        const resumo = `${escapeHtml(it.descrprod || '')} · ${formatNumero(it.qtdneg_item, 2)} ${it.codvol || ''} · ${escapeHtml(r.placa || '')}`;

        let swipeBtns = '';
        if (podeEditar) {
            swipeBtns += `<button class="m-cb-mov-swipe m-cb-mov-swipe--edit" data-acao="editar"
                                  data-tipo="${tipoAcao}" data-nunota="${it.nunota}" title="Editar">
                            <i class="ph ph-pencil-simple"></i>
                          </button>`;
        }
        if (podeReq) {
            swipeBtns += `<button class="m-cb-mov-swipe m-cb-mov-swipe--del" data-acao="excluir"
                                  data-tipo="${tipoAcao}" data-nunota="${it.nunota}"
                                  data-resumo="${resumo}" title="Excluir">
                            <i class="ph ph-trash"></i>
                          </button>`;
        }

        return `
            <div class="m-cb-mov-card-wrap" data-swipe-open="0">
                ${swipeBtns}
                <div class="m-cb-mov-card" data-mov="${it.tipo_movimento}" data-tipo="${r.tipo || ''}">
                    <div class="m-cb-mov-row">
                        <span class="m-cb-mov-icone ${iconeCls}"><i class="ph ${ico}"></i></span>
                        <span class="m-cb-mov-parc">${escapeHtml(parceiroOuVei)}</span>
                        ${badge}
                        <span class="m-cb-mov-data">${formatData(it.dtneg)}</span>
                    </div>
                    <div class="m-cb-mov-row">
                        <span class="m-cb-mov-prod">${escapeHtml(it.descrprod || '—')}</span>
                        <span class="m-cb-mov-qtd">${formatNumero(it.qtdneg_item, 2)} ${it.codvol || ''}</span>
                    </div>
                    <div class="m-cb-mov-row">
                        <span class="m-cb-mov-vlr">${formatBRL(it.vlrtot_item)}</span>
                        ${consumoHtml}
                    </div>
                </div>
            </div>
        `;
    }

    function bindMovCards(container) {
        $$('.m-cb-mov-card-wrap', container).forEach(wrap => {
            const card = wrap.querySelector('.m-cb-mov-card');
            attachSwipe(wrap, card);

            // Botões de swipe
            wrap.querySelectorAll('.m-cb-mov-swipe').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const nunota = parseInt(btn.dataset.nunota, 10);
                    const tipo = btn.dataset.tipo;
                    const acao = btn.dataset.acao;
                    // Fecha swipe
                    card.style.transform = '';
                    wrap.dataset.swipeOpen = '0';

                    if (tipo === 'ent') {
                        if (acao === 'editar') abrirSheetEditarEntrada(nunota);
                        else if (acao === 'excluir') abrirSheetExcluir('ent', nunota, btn.dataset.resumo || '');
                    } else {
                        if (acao === 'editar') abrirSheetEditarReq(nunota);
                        else if (acao === 'excluir') abrirSheetExcluir('req', nunota, btn.dataset.resumo || '');
                    }
                });
            });
        });
    }

    // =========================================================================
    // VEÍCULOS — lista + detalhe
    // =========================================================================
    function _carregarPrefs() {
        try {
            const raw = localStorage.getItem(PREFS_KEY);
            if (raw) {
                const o = JSON.parse(raw);
                if (o && (o.veiculosFiltro === 'COM' || o.veiculosFiltro === 'MAQ')) {
                    ESTADO.veiculosFiltro = o.veiculosFiltro;
                }
            }
        } catch (_) {}
    }
    function _salvarPrefs() {
        try {
            localStorage.setItem(PREFS_KEY, JSON.stringify({ veiculosFiltro: ESTADO.veiculosFiltro }));
        } catch (_) {}
    }

    async function carregarVeiculos() {
        const wrap = $('m_cb_veiList');
        if (!wrap) return;
        wrap.innerHTML = '<div class="m-empty">Carregando…</div>';
        try {
            const params = new URLSearchParams({ limit: '500' });
            const resp = await fetch(`${URL_VEICULOS}?${params.toString()}`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!data.ok) {
                wrap.innerHTML = `<div class="m-empty">${escapeHtml(data.error || 'Falha.')}</div>`;
                return;
            }
            ESTADO.veiculos = (data.results || []).map(v => ({
                ...v,
                _categoria: classificarVeiculo(v),
            }));
            renderVeiculos();
        } catch (err) {
            wrap.innerHTML = '<div class="m-empty">Falha de conexão.</div>';
        }
    }

    function renderVeiculos() {
        const wrap = $('m_cb_veiList');
        if (!wrap) return;
        let lista = ESTADO.veiculos.filter(v => v._categoria === ESTADO.veiculosFiltro);
        const termo = (ESTADO.veiculoTextoBusca || '').trim();
        if (termo) {
            const t = normalizar(termo);
            lista = lista.filter(v =>
                normalizar(v.placa).includes(t)
                || normalizar(v.marcamodelo).includes(t)
                || normalizar(v.especietipo).includes(t)
                || normalizar(v.nomeparc).includes(t)
            );
        }
        if (lista.length === 0) {
            const rotulo = ESTADO.veiculosFiltro === 'MAQ' ? 'maquinário' : 'frota';
            const msg = termo
                ? `Nenhum ${rotulo} bate com "${escapeHtml(termo)}".`
                : `Nenhum veículo de ${rotulo} cadastrado.`;
            wrap.innerHTML = `<div class="m-empty">${msg}</div>`;
            return;
        }
        lista.sort((a, b) => String(a.placa || '').localeCompare(String(b.placa || '')));
        wrap.innerHTML = lista.map(v => {
            const fotoUrl = pathFotoVeiculo(v.placa, 'thumb');
            const placeholder = STATIC_VEICULOS + '_placeholder.svg';
            const propLabel = v.proprio === 'S' ? '' : ' (terceiro)';
            return `
                <div class="m-cb-vei-card" data-codveiculo="${v.codveiculo}">
                    <div class="m-cb-vei-foto"
                         style="background-image: url('${fotoUrl}'), url('${placeholder}');"></div>
                    <div class="m-cb-vei-info">
                        <div class="m-cb-vei-placa">${escapeHtml(v.placa || '—')}</div>
                        <div class="m-cb-vei-modelo">${escapeHtml(v.marcamodelo || v.especietipo || '')}</div>
                        <div class="m-cb-vei-tipo">${escapeHtml(v.especietipo || '')}${propLabel}</div>
                    </div>
                </div>
            `;
        }).join('');
        $$('.m-cb-vei-card', wrap).forEach(card => {
            card.addEventListener('click', () => {
                const cod = parseInt(card.dataset.codveiculo, 10);
                abrirDetalheVeiculo(cod);
            });
        });
    }

    async function abrirDetalheVeiculo(codveiculo) {
        ESTADO.detalheCodvei = codveiculo;
        ESTADO.detalheVeiculo = ESTADO.veiculos.find(v => v.codveiculo === codveiculo) || null;
        pushScreen('detalheVeiculo');
        // Popula datas no detalhe a partir do estado global de mov
        $('m_cb_detDataIni').value = ESTADO.movDataIni || _hojeIso();
        $('m_cb_detDataFim').value = ESTADO.movDataFim || ESTADO.movDataIni || _hojeIso();
        await carregarDetalheVeiculo();
    }

    async function carregarDetalheVeiculo() {
        if (!ESTADO.detalheCodvei) return;
        const inicio = ESTADO.movDataIni || _hojeIso();
        const fim = ESTADO.movDataFim || inicio;

        const fotoEl = $('m_cb_detFoto');
        const infoEl = $('m_cb_detInfo');
        const resumoEl = $('m_cb_detResumo');
        const tituloEl = $('m_cb_detTitulo');
        const movEl = $('m_cb_detMovList');

        infoEl.textContent = 'Carregando…';
        resumoEl.innerHTML = '';
        if (movEl) movEl.innerHTML = '<div class="m-empty">Carregando…</div>';

        const params = new URLSearchParams({
            codveiculo: String(ESTADO.detalheCodvei),
            date_start: inicio,
            date_end: fim,
        });

        try {
            const resp = await fetch(`${URL_RELATORIO}?${params.toString()}`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                infoEl.textContent = data.error || `Erro ${resp.status}`;
                return;
            }
            const v = data.veiculo || {};
            const tot = data.totais || {};
            const abast = data.abastecimentos || [];

            // Foto
            const fotoUrl = pathFotoVeiculo(v.placa);
            const placeholder = STATIC_VEICULOS + '_placeholder.svg';
            fotoEl.style.backgroundImage = `url('${fotoUrl}'), url('${placeholder}')`;
            fotoEl.onclick = () => abrirLightboxFoto(v.placa, `${v.placa} — ${v.marcamodelo || v.especietipo || ''}`);

            // Título
            tituloEl.textContent = v.placa || 'Detalhe';

            // Info
            const propLabel = v.proprio === 'S' ? 'Próprio' : (v.proprio === 'N' ? 'Terceiro' : '');
            infoEl.innerHTML = `
                <div><span class="m-cb-det-placa">${escapeHtml(v.placa || '—')}</span> — ${escapeHtml(v.marcamodelo || '—')}</div>
                <div class="m-cb-muted">
                    ${escapeHtml(v.especietipo || '')}${propLabel ? ' · ' + propLabel : ''}${v.nomeparc ? ' · ' + escapeHtml(v.nomeparc) : ''}
                    · ${formatData(data.periodo.inicio)} a ${formatData(data.periodo.fim)}
                </div>
            `;

            // 7 cards Diesel/ARLA
            const consumoDiesel = tot.consumo_medio_kmlt !== null && tot.consumo_medio_kmlt !== undefined
                ? formatNumero(tot.consumo_medio_kmlt, 2) + ' km/L'
                : (tot.consumo_medio_lth !== null && tot.consumo_medio_lth !== undefined
                    ? formatNumero(tot.consumo_medio_lth, 2) + ' L/h'
                    : '—');
            const consumoArla = tot.consumo_medio_kmlt_arla !== null && tot.consumo_medio_kmlt_arla !== undefined
                ? formatNumero(tot.consumo_medio_kmlt_arla, 2) + ' km/L' : '—';
            const arlaPct = tot.arla_pct_diesel !== null && tot.arla_pct_diesel !== undefined
                ? formatNumero(tot.arla_pct_diesel, 1) + '%' : '—';
            const totalDiesel = tot.total_diesel > 0 ? formatNumero(tot.total_diesel, 0) + ' LT' : '—';
            const totalArla = tot.total_arla > 0 ? formatNumero(tot.total_arla, 0) + ' LT' : '—';
            const distLabel = tot.km_total > 0
                ? formatNumero(tot.km_total, 0) + ' km'
                : (tot.h_total > 0 ? formatNumero(tot.h_total, 1) + ' h' : '—');

            resumoEl.innerHTML = `
                <div class="m-cb-det-metric">
                    <div class="m-cb-det-metric-label">Abastecimentos</div>
                    <div class="m-cb-det-metric-valor">${tot.qtd_abastecimentos || 0}</div>
                </div>
                <div class="m-cb-det-metric">
                    <div class="m-cb-det-metric-label">Distância</div>
                    <div class="m-cb-det-metric-valor">${distLabel}</div>
                </div>
                <div class="m-cb-det-metric">
                    <div class="m-cb-det-metric-label">Diesel total</div>
                    <div class="m-cb-det-metric-valor">${totalDiesel}</div>
                </div>
                <div class="m-cb-det-metric m-cb-det-metric--destaque">
                    <div class="m-cb-det-metric-label">Consumo Diesel</div>
                    <div class="m-cb-det-metric-valor">${consumoDiesel}</div>
                </div>
                <div class="m-cb-det-metric m-cb-det-metric--arla">
                    <div class="m-cb-det-metric-label">ARLA total</div>
                    <div class="m-cb-det-metric-valor">${totalArla}</div>
                </div>
                <div class="m-cb-det-metric m-cb-det-metric--arla">
                    <div class="m-cb-det-metric-label">Consumo ARLA</div>
                    <div class="m-cb-det-metric-valor">${consumoArla}</div>
                </div>
                <div class="m-cb-det-metric m-cb-det-metric--arla">
                    <div class="m-cb-det-metric-label">ARLA / Diesel</div>
                    <div class="m-cb-det-metric-valor">${arlaPct}</div>
                </div>
                <div class="m-cb-det-metric m-cb-det-metric--full">
                    <div class="m-cb-det-metric-label">Valor total no período</div>
                    <div class="m-cb-det-metric-valor">${formatBRL(tot.total_vlr) || 'R$ 0,00'}</div>
                </div>
            `;

            ESTADO.detalheVeiculo = v;
            ESTADO.detalheAbastecimentos = abast;
            renderDetalheMovList(v, abast);
        } catch (err) {
            infoEl.textContent = 'Falha de conexão.';
        }
    }

    function renderDetalheMovList(v, abast) {
        const wrap = $('m_cb_detMovList');
        if (!wrap) return;
        if (!abast || abast.length === 0) {
            wrap.innerHTML = `<div class="m-empty">Sem abastecimentos no período.</div>`;
            return;
        }
        wrap.innerHTML = abast.map(a => {
            const ehExterno = a.tipo === 'EXTERNA_POSTO';
            const iconeCls = ehExterno ? 'm-cb-mov-icone--ext' : 'm-cb-mov-icone--req';
            const ico = ehExterno ? 'ph-globe' : 'ph-clipboard-text';
            let badge = '';
            if (ehExterno) badge = '<span class="m-cb-mov-badge m-cb-mov-badge--ext">EXTERNA</span>';
            else if (a.tipo === 'INTERNA_FROTA') badge = '<span class="m-cb-mov-badge m-cb-mov-badge--frota">Interna</span>';
            else if (a.tipo === 'INTERNA_MAQUINARIO') badge = '<span class="m-cb-mov-badge m-cb-mov-badge--maq">Máquina</span>';

            const podeEditar = ehExterno ? a.statusnota !== 'E' : (a.statusnota !== 'L' && a.statusnota !== 'E');
            const resumo = `${escapeHtml(a.descrprod || '')} · ${formatNumero(a.qtd, 2)} ${a.codvol || ''} · ${escapeHtml(v.placa || '')}`;

            let consumoHtml = '';
            if (a.consumo_kmlt != null) {
                consumoHtml = `<span class="m-cb-mov-consumo m-cb-mov-consumo--diesel">${formatNumero(a.consumo_kmlt, 2)} km/L</span>`;
            } else if (a.consumo_lth != null) {
                consumoHtml = `<span class="m-cb-mov-consumo m-cb-mov-consumo--diesel">${formatNumero(a.consumo_lth, 2)} L/h</span>`;
            }

            let swipeBtns = '';
            if (podeEditar) {
                swipeBtns += `<button class="m-cb-mov-swipe m-cb-mov-swipe--edit" data-acao="editar"
                                      data-nunota="${a.nunota}" title="Editar">
                                <i class="ph ph-pencil-simple"></i>
                              </button>
                              <button class="m-cb-mov-swipe m-cb-mov-swipe--del" data-acao="excluir"
                                      data-nunota="${a.nunota}" data-resumo="${resumo}" title="Excluir">
                                <i class="ph ph-trash"></i>
                              </button>`;
            }

            return `
                <div class="m-cb-mov-card-wrap" data-swipe-open="0">
                    ${swipeBtns}
                    <div class="m-cb-mov-card" data-mov="REQUISICAO" data-tipo="${a.tipo || ''}">
                        <div class="m-cb-mov-row">
                            <span class="m-cb-mov-icone ${iconeCls}"><i class="ph ${ico}"></i></span>
                            <span class="m-cb-mov-parc">${escapeHtml(v.placa || '—')}</span>
                            ${badge}
                            <span class="m-cb-mov-data">${formatData(a.dtneg)}</span>
                        </div>
                        <div class="m-cb-mov-row">
                            <span class="m-cb-mov-prod">${escapeHtml(a.descrprod || '—')}</span>
                            <span class="m-cb-mov-qtd">${formatNumero(a.qtd, 2)} ${a.codvol || ''}</span>
                        </div>
                        <div class="m-cb-mov-row">
                            <span class="m-cb-mov-vlr">${formatBRL(a.vlrtot)}</span>
                            ${consumoHtml}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Bind swipe + ações
        $$('.m-cb-mov-card-wrap', wrap).forEach(w => {
            const card = w.querySelector('.m-cb-mov-card');
            attachSwipe(w, card);
            w.querySelectorAll('.m-cb-mov-swipe').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const nunota = parseInt(btn.dataset.nunota, 10);
                    card.style.transform = '';
                    w.dataset.swipeOpen = '0';
                    if (btn.dataset.acao === 'editar') abrirSheetEditarReq(nunota);
                    else if (btn.dataset.acao === 'excluir') abrirSheetExcluir('req', nunota, btn.dataset.resumo || '');
                });
            });
        });
    }

    // =========================================================================
    // Lightbox
    // =========================================================================
    function abrirLightboxFoto(placa, legenda) {
        ESTADO.lightboxPlaca = placa;
        ESTADO.lightboxLegenda = legenda;
        const img = $('m_cb_lbImg');
        const leg = $('m_cb_lbLegenda');
        const tit = $('m_cb_lbTitulo');
        if (img) img.src = pathFotoVeiculo(placa);
        if (leg) leg.textContent = legenda || '';
        if (tit) tit.textContent = placa || 'Foto';
        pushScreen('fotoLightbox');
    }

    // =========================================================================
    // Toggle de contexto na tela lista
    // =========================================================================
    function setCtx(ctx) {
        ESTADO.ctx = ctx;
        // Toggle top
        $$('.combustivel-mobile .m-cb-toggle-btn').forEach(b => {
            b.classList.toggle('is-active', b.dataset.ctx === ctx);
        });
        // Bottom nav
        $$('.combustivel-mobile .m-bottom-nav__item[data-ctx]').forEach(b => {
            b.classList.toggle('is-active', b.dataset.ctx === ctx);
        });
        // Containers
        $$('.combustivel-mobile .m-cb-ctx').forEach(c => {
            c.hidden = c.dataset.ctx !== ctx;
        });
        // FABs — Mai/2026 — 2026-05-28: 1 FAB único `+` (abrirSheetNovaReq)
        const showReq = ctx === 'movimentacoes' || ctx === 'estoque';
        const fabReq = $('m_cb_fabReq');
        if (fabReq) fabReq.hidden = !showReq;

        // Carga lazy
        if (ctx === 'estoque' && ESTADO.tanques.length === 0) carregarEstoque();
        else if (ctx === 'movimentacoes' && ESTADO.movItems.length === 0) carregarMovimentacoes();
        else if (ctx === 'veiculos' && ESTADO.veiculos.length === 0) carregarVeiculos();
    }

    // =========================================================================
    // BADGE filtros ativos
    // =========================================================================
    function temFiltroAtivo() {
        return Boolean(ESTADO.filtroMov || ESTADO.filtroTipo);
    }
    function atualizarBadgeFiltros() {
        const nav = document.querySelector('.combustivel-mobile .m-bottom-nav__item[data-nav="filtros"]');
        if (!nav) return;
        nav.classList.toggle('has-filtros-ativos', temFiltroAtivo());
    }

    // =========================================================================
    // SHEET REQUISIÇÃO — typeaheads, validação, salvar
    // =========================================================================
    function tipoReqSelecionado() {
        const r = document.querySelector('input[name="m_cb_reqTipo"]:checked');
        return r ? r.value : 'INTERNA_FROTA';
    }

    function atualizarVisivelReq() {
        const tipo = tipoReqSelecionado();
        const ehEntrada = tipo === 'ENTRADA';
        const ehInterno = tipo === 'INTERNA_FROTA';
        const ehExt = tipo === 'EXTERNA_POSTO';

        // Bloco ENTRADA — só visível quando tipo=ENTRADA
        $('m_cb_reqEntradaWrap').hidden = !ehEntrada;
        $('m_cb_reqEntradaAviso').hidden = !ehEntrada;

        // Bloco REQUISIÇÃO (Interno + Externo) — esconde quando ENTRADA
        $('m_cb_reqRequisicaoWrap').hidden = ehEntrada;

        // Aviso externo + posto + doc + datas externo — só EXTERNA_POSTO
        $('m_cb_reqPostoWrap').hidden = !ehExt;
        $('m_cb_reqExternoAviso').hidden = !ehExt;
        $('m_cb_reqExtDocWrap').hidden = !ehExt;
        $('m_cb_reqExtDatasWrap').hidden = !ehExt;

        // Single (INTERNO) vs Multi-itens (EXTERNA) dentro do bloco req
        $('m_cb_reqSingleWrap').hidden = !ehInterno;
        $('m_cb_reqItensExt').hidden = !ehExt;
        $('m_cb_reqDtNegWrap').hidden = !ehInterno;

        if (ehExt) {
            const h = hoje();
            if (!$('m_cb_reqExtDtNeg').value) $('m_cb_reqExtDtNeg').value = h;
            if (!$('m_cb_reqExtDtVenc').value) $('m_cb_reqExtDtVenc').value = h;
            if (ESTADO.reqExtItens.length === 0) _addItemReqExt();
            else _renderReqExtItens();
        } else if (!ehEntrada) {
            // Saiu de externo pra interno — limpa posto/doc
            $('m_cb_reqPostoVis').value = '';
            $('m_cb_reqPostoCod').value = '';
            $('m_cb_reqExtDoc').value = '';
        }

        // Garante 1 linha vazia na tabela de Itens da Entrada
        if (ehEntrada) {
            if (ESTADO.entItens.length === 0) _addItemEntrada();
            else _renderEntItens();
        }

        // Header + botão Excluir conforme estado
        _atualizarHeaderSheetReq();
    }

    // Libera/trava pills (em edição, só a pill do tipo atual fica habilitada).
    function _liberarPillsReq() {
        document.querySelectorAll('input[name="m_cb_reqTipo"]').forEach(r => {
            r.disabled = false;
            const pill = r.closest('.m-cb-pill');
            if (pill) pill.style.opacity = '';
        });
    }
    function _travarOutrasPillsReq(valorAtivo) {
        document.querySelectorAll('input[name="m_cb_reqTipo"]').forEach(r => {
            r.disabled = (r.value !== valorAtivo);
            const pill = r.closest('.m-cb-pill');
            if (pill) pill.style.opacity = r.disabled ? '0.45' : '';
        });
    }

    function _addItemReqExt(item) {
        ESTADO._reqExtSeq += 1;
        const qt = item ? (parseFloat(item.qtd) || 0) : 0;
        const vu = item ? (parseFloat(item.vlrunit) || 0) : 0;
        ESTADO.reqExtItens.push({
            _seq: ESTADO._reqExtSeq,
            codprod: item ? item.codprod : null,
            descrprod: item ? item.descrprod : '',
            qtd: qt,
            vlrunit: vu,
            vlrtot: qt * vu,
        });
        _renderReqExtItens();
    }

    function _removerItemReqExt(seq) {
        ESTADO.reqExtItens = ESTADO.reqExtItens.filter(it => it._seq !== seq);
        if (ESTADO.reqExtItens.length === 0) _addItemReqExt();
        _renderReqExtItens();
    }

    function _atualizarTotalReqExt() {
        let total = 0;
        ESTADO.reqExtItens.forEach(it => { total += parseFloat(it.vlrtot) || 0; });
        const lbl = $('m_cb_reqTotalExt');
        if (lbl) lbl.innerHTML = `Total: <strong>${formatBRL(total) || 'R$ 0,00'}</strong>`;
    }

    function _renderReqExtItens() {
        const container = $('m_cb_reqItensList');
        if (!container) return;
        const sozinho = ESTADO.reqExtItens.length === 1;
        container.innerHTML = ESTADO.reqExtItens.map(it => `
            <div class="m-cb-item-card" data-seq="${it._seq}">
                <button type="button" class="m-cb-item-rm" data-seq="${it._seq}"
                        ${sozinho ? 'disabled title="Pelo menos 1 item"' : 'title="Remover"'}>×</button>
                <div class="m-field" style="position: relative;">
                    <label class="m-field-label">Combustível *</label>
                    <input id="m_cb_reqExtProd_${it._seq}" type="text" class="m-field-input"
                           data-seq="${it._seq}" autocomplete="off"
                           value="${it.codprod ? escapeHtml(it.codprod + ' — ' + (it.descrprod || '')) : ''}"
                           placeholder="Buscar…" />
                    <input id="m_cb_reqExtProdCod_${it._seq}" type="hidden" value="${it.codprod || ''}" />
                    <div id="m_cb_reqExtProdDD_${it._seq}" class="m-cb-dropdown"></div>
                </div>
                <div class="m-cb-grid">
                    <div class="m-field">
                        <label class="m-field-label">Qtd (LT) *</label>
                        <input id="m_cb_reqExtQtd_${it._seq}" type="number" class="m-field-input m-cb-reqext-qtd"
                               data-seq="${it._seq}" step="0.01" min="0" value="${it.qtd || ''}" placeholder="0,00" />
                    </div>
                    <div class="m-field">
                        <label class="m-field-label">Valor unit. *</label>
                        <input id="m_cb_reqExtVlu_${it._seq}" type="number" class="m-field-input m-cb-reqext-vlu"
                               data-seq="${it._seq}" step="0.0001" min="0" value="${it.vlrunit || ''}" placeholder="0,0000" />
                    </div>
                </div>
                <div class="m-field">
                    <label class="m-field-label">Total *</label>
                    <input id="m_cb_reqExtTot_${it._seq}" type="number" class="m-field-input m-cb-reqext-tot"
                           data-seq="${it._seq}" step="0.01" min="0"
                           value="${it.vlrtot ? (Math.round(it.vlrtot * 100) / 100) : ''}"
                           placeholder="0,00" title="Edite qtd, vlrunit ou total — o terceiro recalcula" />
                </div>
            </div>
        `).join('');

        // Sincroniza inputs sem perder caret do foco
        function _sincronizarInputs(seq, campoEditado) {
            const item = ESTADO.reqExtItens.find(it => it._seq === seq);
            if (!item) return;
            const round = (n, casas) => {
                const m = Math.pow(10, casas);
                return Math.round((parseFloat(n) || 0) * m) / m;
            };
            const inpQtd = $(`m_cb_reqExtQtd_${seq}`);
            const inpVlu = $(`m_cb_reqExtVlu_${seq}`);
            const inpTot = $(`m_cb_reqExtTot_${seq}`);
            if (inpQtd && campoEditado !== 'qtd') inpQtd.value = round(item.qtd, 3) || '';
            if (inpVlu && campoEditado !== 'vlrunit') inpVlu.value = round(item.vlrunit, 4) || '';
            if (inpTot && campoEditado !== 'vlrtot') inpTot.value = round(item.vlrtot, 2) || '';
        }

        // Eventos qtd/vlrunit/vlrtot triangulares
        $$('.m-cb-reqext-qtd, .m-cb-reqext-vlu, .m-cb-reqext-tot', container).forEach(inp => {
            inp.addEventListener('input', (e) => {
                const seq = parseInt(e.target.dataset.seq, 10);
                const item = ESTADO.reqExtItens.find(it => it._seq === seq);
                if (!item) return;
                let campoEditado;
                if (e.target.classList.contains('m-cb-reqext-qtd')) {
                    item.qtd = parseFloat(e.target.value) || 0;
                    campoEditado = 'qtd';
                } else if (e.target.classList.contains('m-cb-reqext-vlu')) {
                    item.vlrunit = parseFloat(e.target.value) || 0;
                    campoEditado = 'vlrunit';
                } else {
                    item.vlrtot = parseFloat(e.target.value) || 0;
                    campoEditado = 'vlrtot';
                }
                _recalcularItem(item, campoEditado);
                _sincronizarInputs(seq, campoEditado);
                _atualizarTotalReqExt();
            });
        });

        // Lixeira
        $$('.m-cb-item-rm', container).forEach(btn => {
            btn.addEventListener('click', () => _removerItemReqExt(parseInt(btn.dataset.seq, 10)));
        });

        // Typeahead por linha
        ESTADO.reqExtItens.forEach(it => {
            const seq = it._seq;
            if (!window.IAgro || !IAgro.attachTypeahead) return;
            IAgro.attachTypeahead({
                inputId: `m_cb_reqExtProd_${seq}`,
                hiddenId: `m_cb_reqExtProdCod_${seq}`,
                dropdownId: `m_cb_reqExtProdDD_${seq}`,
                url: URL_PRODUTOS, limit: 30, debounceMs: 250, minChars: 0,
                positionFixed: true,
                pickItems: (data) => data.results || [],
                pickCod: (item) => item.codprod,
                pickDescr: (item) => item.descrprod,
                renderItem: (item) => `${item.codprod} — ${item.descrprod} <span style="color:#94a3b8;font-size:10px;">(${item.codvol})</span>`,
                onSelect: (cod, descr) => {
                    const i = ESTADO.reqExtItens.find(x => x._seq === seq);
                    if (i) { i.codprod = parseInt(cod, 10); i.descrprod = descr; }
                },
                onClear: () => {
                    const i = ESTADO.reqExtItens.find(x => x._seq === seq);
                    if (i) { i.codprod = null; i.descrprod = ''; }
                },
            });
        });

        _atualizarTotalReqExt();
    }

    function _limparSheetReq() {
        document.querySelector('input[name="m_cb_reqTipo"][value="INTERNA_FROTA"]').checked = true;
        ['m_cb_reqVeiVis','m_cb_reqVeiCod','m_cb_reqProdVis','m_cb_reqProdCod','m_cb_reqQtd',
         'm_cb_reqVlu','m_cb_reqHod','m_cb_reqHor','m_cb_reqCencusVis','m_cb_reqCencusCod','m_cb_reqObs',
         'm_cb_reqPostoVis','m_cb_reqPostoCod','m_cb_reqExtDoc','m_cb_reqExtDtNeg','m_cb_reqExtDtVenc',
         'm_cb_reqNatVis','m_cb_reqNatCod','m_cb_reqTipVis','m_cb_reqTipCod','m_cb_reqDtNeg']
            .forEach(id => { const el = $(id); if (el) el.value = ''; });
        ESTADO.reqExtItens = [];
        ESTADO._reqExtSeq = 0;
        const list = $('m_cb_reqItensList');
        if (list) list.innerHTML = '';
        const tot = $('m_cb_reqTotalExt');
        if (tot) tot.innerHTML = 'Total: <strong>R$ 0,00</strong>';
        // Defaults
        $('m_cb_reqCencusCod').value = DEFAULT_CODCENCUS;
        $('m_cb_reqCencusVis').value = `${DEFAULT_CODCENCUS} — COMERCIALIZAÇÃO`;
        $('m_cb_reqNatCod').value = DEFAULT_CODNAT;
        $('m_cb_reqNatVis').value = `${DEFAULT_CODNAT} — COMBUSTÍVEL`;
        $('m_cb_reqTipCod').value = DEFAULT_CODTIPVENDA;
        $('m_cb_reqTipVis').value = `${DEFAULT_CODTIPVENDA} — A VISTA`;
        $('m_cb_reqVeiHint').textContent = '';
        const msg = $('m_cb_reqMsg');
        if (msg) { msg.textContent = ''; msg.className = 'm-cb-msg'; }
    }

    function _atualizarHeaderSheetReq() {
        const h = $('m_cb_reqTitulo');
        const btn = $('m_cb_reqSalvar');
        const tipo = tipoReqSelecionado();
        const ehEntrada = tipo === 'ENTRADA';

        // Header
        if (ESTADO.reqEditandoNunota) {
            if (h) h.innerHTML = `<i class="ph ph-pencil-simple"></i> Editar requisição ${ESTADO.reqEditandoNunota}`;
        } else if (ESTADO.entEditandoNunota) {
            if (h) h.innerHTML = `<i class="ph ph-pencil-simple"></i> Editar entrada ${ESTADO.entEditandoNunota}`;
        } else {
            if (h) {
                if (ehEntrada) h.innerHTML = '<i class="ph ph-tray-arrow-down"></i> Nova entrada';
                else h.textContent = 'Novo lançamento';
            }
        }

        // Texto do botão Salvar
        if (btn) {
            const editing = ESTADO.reqEditandoNunota || ESTADO.entEditandoNunota;
            btn.querySelector('span').textContent = editing ? 'Salvar alterações' : 'Salvar';
        }
    }

    function abrirSheetNovaReq() {
        ESTADO.reqEditandoNunota = null;
        ESTADO.entEditandoNunota = null;
        // Default: pill INTERNA_FROTA
        const r = document.querySelector('input[name="m_cb_reqTipo"][value="INTERNA_FROTA"]');
        if (r) r.checked = true;
        _liberarPillsReq();
        _limparSheetReq();
        atualizarVisivelReq();
        if (!$('m_cb_reqDtNeg').value) $('m_cb_reqDtNeg').value = hoje();
        // Se o veículo de detalhe está aberto, pré-selecionar
        if (ESTADO.screen === 'detalheVeiculo' && ESTADO.detalheVeiculo) {
            const v = ESTADO.detalheVeiculo;
            $('m_cb_reqVeiCod').value = v.codveiculo;
            $('m_cb_reqVeiVis').value = `${v.codveiculo} — ${v.placa || ''}${v.marcamodelo ? ' — ' + v.marcamodelo : ''}`;
            if (v.codcencus) {
                $('m_cb_reqCencusCod').value = v.codcencus;
                $('m_cb_reqCencusVis').value = `${v.codcencus} (do veículo)`;
            }
            const hint = $('m_cb_reqVeiHint');
            if (hint && v.nomeparc) hint.textContent = `Parceiro: ${v.nomeparc}`;
        }
        openSheet('nova-req');
    }

    async function abrirSheetEditarReq(nunota) {
        ESTADO.reqEditandoNunota = nunota;
        ESTADO.entEditandoNunota = null;
        _limparSheetReq();
        openSheet('nova-req');
        try {
            const resp = await fetch(`/sankhya/combustivel/api/requisicao/${nunota}/`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                mostrarToast(data.error || 'Falha ao carregar requisição.', 'error');
                closeSheet('nova-req');
                return;
            }
            const cab = data.cabecalho || {};
            const req = data.requisicao || {};
            const itens = data.itens || [];
            const item = itens[0] || {};

            const tipo = req.TIPO || 'INTERNA_FROTA';
            const radio = document.querySelector(`input[name="m_cb_reqTipo"][value="${tipo}"]`);
            if (radio) radio.checked = true;
            // Trava pills (edição não troca tipo)
            _travarOutrasPillsReq(tipo);
            atualizarVisivelReq();

            if (tipo !== 'EXTERNA_POSTO' && cab.DTNEG) {
                const d = new Date(cab.DTNEG);
                $('m_cb_reqDtNeg').value = d.toISOString().slice(0, 10);
            }

            if (tipo === 'EXTERNA_POSTO') {
                if (req.CODPARC) {
                    $('m_cb_reqPostoCod').value = req.CODPARC;
                    $('m_cb_reqPostoVis').value = `${req.CODPARC} — ${cab.NOMEPARC || ''}`;
                }
                if (req.DOC_FRETE_REF) $('m_cb_reqExtDoc').value = req.DOC_FRETE_REF;
                if (cab.DTNEG) {
                    const d = new Date(cab.DTNEG);
                    $('m_cb_reqExtDtNeg').value = d.toISOString().slice(0, 10);
                }
            }

            if (req.CODVEICULO) {
                $('m_cb_reqVeiCod').value = req.CODVEICULO;
                const placa = req.PLACA || '';
                const modelo = req.MARCAMODELO || req.ESPECIETIPO || '';
                $('m_cb_reqVeiVis').value = `${req.CODVEICULO} — ${placa}${modelo ? ' — ' + modelo : ''}`;
            }

            if (tipo === 'EXTERNA_POSTO') {
                ESTADO.reqExtItens = [];
                ESTADO._reqExtSeq = 0;
                itens.forEach(it => {
                    ESTADO._reqExtSeq += 1;
                    const qt = parseFloat(it.QTDNEG) || 0;
                    const vu = parseFloat(it.VLRUNIT) || 0;
                    ESTADO.reqExtItens.push({
                        _seq: ESTADO._reqExtSeq,
                        codprod: it.CODPROD,
                        descrprod: it.DESCRPROD,
                        qtd: qt, vlrunit: vu, vlrtot: qt * vu,
                    });
                });
                if (ESTADO.reqExtItens.length === 0) _addItemReqExt();
                _renderReqExtItens();
            } else {
                if (item.CODPROD) {
                    $('m_cb_reqProdCod').value = item.CODPROD;
                    $('m_cb_reqProdVis').value = `${item.CODPROD} — ${item.DESCRPROD || ''}`;
                }
                if (item.QTDNEG != null) $('m_cb_reqQtd').value = item.QTDNEG;
                if (item.VLRUNIT) $('m_cb_reqVlu').value = item.VLRUNIT;
            }

            if (req.HODOMETRO_KM != null) $('m_cb_reqHod').value = req.HODOMETRO_KM;
            if (req.HORIMETRO_H != null) $('m_cb_reqHor').value = req.HORIMETRO_H;

            if (cab.CODCENCUS) {
                $('m_cb_reqCencusCod').value = cab.CODCENCUS;
                $('m_cb_reqCencusVis').value = String(cab.CODCENCUS);
            }
            if (cab.CODNAT) {
                $('m_cb_reqNatCod').value = cab.CODNAT;
                $('m_cb_reqNatVis').value = String(cab.CODNAT);
            }
            if (cab.OBSERVACAO) $('m_cb_reqObs').value = cab.OBSERVACAO;
        } catch (err) {
            mostrarToast('Falha de conexão.', 'error');
            closeSheet('nova-req');
        }
    }

    function validarReq() {
        const tipo = tipoReqSelecionado();
        // ENTRADA: delega pra validarEntrada
        if (tipo === 'ENTRADA') return validarEntrada();

        const erros = [];
        const ehExt = tipo === 'EXTERNA_POSTO';
        if (!$('m_cb_reqVeiCod').value) erros.push('Selecione um veículo.');
        if (!$('m_cb_reqCencusCod').value) erros.push('Centro de resultado obrigatório.');
        if (ehExt) {
            if (!$('m_cb_reqPostoCod').value) erros.push('Selecione o posto.');
            const numnotaRaw = ($('m_cb_reqExtDoc').value || '').trim();
            if (!numnotaRaw) erros.push('Nº NF / boleto obrigatório.');
            else if (!/^\d+$/.test(numnotaRaw)) erros.push('Nº NF deve ser apenas números.');
            const dtn = $('m_cb_reqExtDtNeg').value;
            const dtv = $('m_cb_reqExtDtVenc').value;
            if (dtn && dtv && dtv < dtn) erros.push('Vencimento anterior à data do abastecimento.');
            const validos = ESTADO.reqExtItens.filter(it =>
                it.codprod && (parseFloat(it.qtd) || 0) > 0
                && (parseFloat(it.vlrunit) || 0) > 0 && (parseFloat(it.vlrtot) || 0) > 0);
            const incompletos = ESTADO.reqExtItens.filter(it => it.codprod).filter(it =>
                (parseFloat(it.qtd) || 0) <= 0 || (parseFloat(it.vlrunit) || 0) <= 0 || (parseFloat(it.vlrtot) || 0) <= 0);
            if (validos.length === 0) erros.push('Adicione ao menos 1 item completo (qtd + vlrunit + total).');
            else if (incompletos.length > 0) erros.push('Há itens com qtd/vlrunit/total em branco.');
        } else {
            if (!$('m_cb_reqProdCod').value) erros.push('Selecione um combustível.');
            const qtd = parseFloat($('m_cb_reqQtd').value || '0');
            if (!qtd || qtd <= 0) erros.push('Informe a quantidade.');
        }
        return erros;
    }

    async function enviarRequisicao() {
        const tipo = tipoReqSelecionado();
        // ENTRADA: delega pra enviarEntrada
        if (tipo === 'ENTRADA') return enviarEntrada();

        const msg = $('m_cb_reqMsg');
        msg.textContent = ''; msg.className = 'm-cb-msg';
        const erros = validarReq();
        if (erros.length) { msg.textContent = erros.join(' '); return; }

        const ehExt = tipo === 'EXTERNA_POSTO';

        const payload = {
            codveiculo: parseInt($('m_cb_reqVeiCod').value, 10),
            tipo,
            hodometro_km: parseFloat($('m_cb_reqHod').value || '0') || null,
            horimetro_h: parseFloat($('m_cb_reqHor').value || '0') || null,
            codcencus: parseInt($('m_cb_reqCencusCod').value, 10),
            codnat: parseInt($('m_cb_reqNatCod').value || '0', 10) || null,
            codtipvenda: parseInt($('m_cb_reqTipCod').value || '0', 10) || null,
            observacao: $('m_cb_reqObs').value.trim() || null,
        };
        if (!ehExt) payload.dtneg = $('m_cb_reqDtNeg').value || null;

        if (ehExt) {
            payload.codparc = parseInt($('m_cb_reqPostoCod').value, 10);
            const numnotaRaw = ($('m_cb_reqExtDoc').value || '').trim();
            payload.numnota = numnotaRaw || null;
            payload.doc_frete_ref = numnotaRaw || null;
            payload.dtneg = $('m_cb_reqExtDtNeg').value || null;
            payload.dtvenc = $('m_cb_reqExtDtVenc').value || null;
            payload.itens = ESTADO.reqExtItens
                .filter(it => it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0)
                .map(it => ({
                    codprod: parseInt(it.codprod, 10),
                    qtd: parseFloat(it.qtd),
                    vlrunit: parseFloat(it.vlrunit),
                }));
        } else {
            payload.codprod = parseInt($('m_cb_reqProdCod').value, 10);
            payload.qtd = parseFloat($('m_cb_reqQtd').value);
            payload.vlrunit = parseFloat($('m_cb_reqVlu').value || '0') || null;
        }

        const btn = $('m_cb_reqSalvar');
        btn.disabled = true;
        const txt0 = btn.querySelector('span').textContent;
        btn.querySelector('span').textContent = 'Enviando…';
        try {
            let url;
            if (ESTADO.reqEditandoNunota) {
                url = `/sankhya/combustivel/api/requisicao/${ESTADO.reqEditandoNunota}/editar/`;
            } else if (ehExt) {
                url = URL_EXT_CRIAR;
            } else {
                url = URL_REQ_CRIAR;
            }
            const resp = await IAgro.postJSON(url, payload);
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || `Erro ${resp.status || ''}`;
                return;
            }
            const acao = ESTADO.reqEditandoNunota ? 'atualizada' : 'criada';
            const extras = (ehExt && data.nufin) ? ` · NUFIN ${data.nufin}` : '';
            mostrarToast(`Requisição ${data.nunota} ${acao}${extras}.`, 'success');
            closeSheet('nova-req');
            carregarMovimentacoes();
            carregarEstoque();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
        } finally {
            btn.disabled = false;
            btn.querySelector('span').textContent = txt0;
        }
    }

    // =========================================================================
    // SHEET ENTRADA — typeaheads, validação, salvar
    // =========================================================================
    async function _preencherNomeEmpresaDefault(codemp) {
        try {
            const r = await fetch(`${URL_EMPRESAS}?q=${codemp}&limit=10`,
                                  { credentials: 'same-origin' });
            const d = await r.json();
            const items = d.results || d.items || [];
            const match = items.find(it => String(it.cod || it.codemp) === String(codemp));
            const nome = match ? (match.descr || match.nomefantasia || match.razaosocial || '') : '';
            const inp = $('m_cb_entEmpresaVis');
            if (inp && nome) inp.value = `${codemp} — ${nome}`;
        } catch (_) {}
    }

    function _addItemEntrada(item) {
        ESTADO._entSeq += 1;
        ESTADO.entItens.push({
            _seq: ESTADO._entSeq,
            codprod: item ? item.codprod : null,
            descrprod: item ? item.descrprod : '',
            qtd: item ? item.qtd : 0,
            vlrunit: item ? item.vlrunit : 0,
        });
        _renderEntItens();
    }

    function _removerItemEntrada(seq) {
        ESTADO.entItens = ESTADO.entItens.filter(it => it._seq !== seq);
        if (ESTADO.entItens.length === 0) _addItemEntrada();
        _renderEntItens();
    }

    function _atualizarTotalEnt() {
        let total = 0;
        ESTADO.entItens.forEach(it => {
            const qt = parseFloat(it.qtd) || 0;
            const vu = parseFloat(it.vlrunit) || 0;
            total += qt * vu;
        });
        const lbl = $('m_cb_entTotalNota');
        if (lbl) lbl.innerHTML = `Total: <strong>${formatBRL(total) || 'R$ 0,00'}</strong>`;
    }

    function _renderEntItens() {
        const container = $('m_cb_entItensList');
        if (!container) return;
        const sozinho = ESTADO.entItens.length === 1;
        container.innerHTML = ESTADO.entItens.map(it => {
            const total = (parseFloat(it.qtd) || 0) * (parseFloat(it.vlrunit) || 0);
            return `
            <div class="m-cb-item-card" data-seq="${it._seq}">
                <button type="button" class="m-cb-item-rm" data-seq="${it._seq}"
                        ${sozinho ? 'disabled title="Pelo menos 1 item"' : 'title="Remover"'}>×</button>
                <div class="m-field" style="position: relative;">
                    <label class="m-field-label">Combustível *</label>
                    <input id="m_cb_entProd_${it._seq}" type="text" class="m-field-input"
                           data-seq="${it._seq}" autocomplete="off"
                           value="${it.codprod ? escapeHtml(it.codprod + ' — ' + (it.descrprod || '')) : ''}"
                           placeholder="Buscar combustível…" />
                    <input id="m_cb_entProdCod_${it._seq}" type="hidden" value="${it.codprod || ''}" />
                    <div id="m_cb_entProdDD_${it._seq}" class="m-cb-dropdown"></div>
                </div>
                <div class="m-cb-grid">
                    <div class="m-field">
                        <label class="m-field-label">Qtd (LT) *</label>
                        <input id="m_cb_entQtd_${it._seq}" type="number" class="m-field-input m-cb-ent-qtd"
                               data-seq="${it._seq}" step="0.01" min="0" value="${it.qtd || ''}" placeholder="0,00" />
                    </div>
                    <div class="m-field">
                        <label class="m-field-label">Valor unit. *</label>
                        <input id="m_cb_entVlu_${it._seq}" type="number" class="m-field-input m-cb-ent-vlu"
                               data-seq="${it._seq}" step="0.0001" min="0" value="${it.vlrunit || ''}" placeholder="0,0000" />
                    </div>
                </div>
                <div class="m-cb-item-total" data-seq="${it._seq}" style="text-align: right; font-weight: 700; color: var(--m-text); font-size: 13px;">
                    ${formatBRL(total) || 'R$ 0,00'}
                </div>
            </div>
            `;
        }).join('');

        // Eventos qtd/vlrunit (sem triangular — Entrada não tem campo Total editável)
        $$('.m-cb-ent-qtd, .m-cb-ent-vlu', container).forEach(inp => {
            inp.addEventListener('input', (e) => {
                const seq = parseInt(e.target.dataset.seq, 10);
                const item = ESTADO.entItens.find(it => it._seq === seq);
                if (!item) return;
                if (e.target.classList.contains('m-cb-ent-qtd')) item.qtd = parseFloat(e.target.value) || 0;
                else item.vlrunit = parseFloat(e.target.value) || 0;
                const cell = container.querySelector(`.m-cb-item-total[data-seq="${seq}"]`);
                if (cell) cell.textContent = formatBRL(item.qtd * item.vlrunit) || 'R$ 0,00';
                _atualizarTotalEnt();
            });
        });

        $$('.m-cb-item-rm', container).forEach(btn => {
            btn.addEventListener('click', () => _removerItemEntrada(parseInt(btn.dataset.seq, 10)));
        });

        ESTADO.entItens.forEach(it => {
            const seq = it._seq;
            if (!window.IAgro || !IAgro.attachTypeahead) return;
            IAgro.attachTypeahead({
                inputId: `m_cb_entProd_${seq}`,
                hiddenId: `m_cb_entProdCod_${seq}`,
                dropdownId: `m_cb_entProdDD_${seq}`,
                url: URL_PRODUTOS, limit: 30, debounceMs: 250, minChars: 0,
                positionFixed: true,
                pickItems: (data) => data.results || [],
                pickCod: (item) => item.codprod,
                pickDescr: (item) => item.descrprod,
                renderItem: (item) => `${item.codprod} — ${item.descrprod} <span style="color:#94a3b8;font-size:10px;">(${item.codvol})</span>`,
                onSelect: (cod, descr) => {
                    const i = ESTADO.entItens.find(x => x._seq === seq);
                    if (i) { i.codprod = parseInt(cod, 10); i.descrprod = descr; }
                },
                onClear: () => {
                    const i = ESTADO.entItens.find(x => x._seq === seq);
                    if (i) { i.codprod = null; i.descrprod = ''; }
                },
            });
        });

        _atualizarTotalEnt();
    }

    function abrirSheetNovaEntrada() {
        // Mai/2026 — 2026-05-28: abre sheet único (nova-req) com pill ENTRADA selecionada.
        ESTADO.entEditandoNunota = null;
        ESTADO.reqEditandoNunota = null;
        ESTADO.entItens = [];
        ESTADO._entSeq = 0;

        // Marca pill ENTRADA + libera as outras
        const r = document.querySelector('input[name="m_cb_reqTipo"][value="ENTRADA"]');
        if (r) r.checked = true;
        _liberarPillsReq();
        _limparSheetReq();

        // Limpa campos da Entrada
        ['m_cb_entEmpresaVis','m_cb_entEmpresaCod','m_cb_entFornVis','m_cb_entFornCod',
         'm_cb_entNumNota','m_cb_entSerie','m_cb_entCencusVis','m_cb_entCencusCod',
         'm_cb_entHist','m_cb_entObs','m_cb_entNatVis','m_cb_entNatCod',
         'm_cb_entTipVis','m_cb_entTipCod']
            .forEach(id => { const el = $(id); if (el) el.value = ''; });
        const h = hoje();
        $('m_cb_entDtNeg').value = h;
        $('m_cb_entDtVenc').value = h;
        $('m_cb_entEmpresaCod').value = '1';
        $('m_cb_entEmpresaVis').value = '1';
        _preencherNomeEmpresaDefault(1);
        $('m_cb_entCencusCod').value = DEFAULT_CODCENCUS;
        $('m_cb_entCencusVis').value = `${DEFAULT_CODCENCUS} — COMERCIALIZAÇÃO`;
        $('m_cb_entNatCod').value = DEFAULT_CODNAT;
        $('m_cb_entNatVis').value = `${DEFAULT_CODNAT} — COMBUSTÍVEL`;
        $('m_cb_entTipCod').value = DEFAULT_CODTIPVENDA;
        $('m_cb_entTipVis').value = `${DEFAULT_CODTIPVENDA} — A VISTA`;
        _addItemEntrada();
        const msg = $('m_cb_reqMsg');
        if (msg) { msg.textContent = ''; msg.className = 'm-cb-msg'; }
        atualizarVisivelReq();
        openSheet('nova-req');
    }

    async function abrirSheetEditarEntrada(nunota) {
        ESTADO.entEditandoNunota = nunota;
        ESTADO.reqEditandoNunota = null;
        ESTADO.entItens = [];
        ESTADO._entSeq = 0;

        // Marca pill ENTRADA + trava outras
        const r = document.querySelector('input[name="m_cb_reqTipo"][value="ENTRADA"]');
        if (r) r.checked = true;
        _travarOutrasPillsReq('ENTRADA');

        ['m_cb_entEmpresaVis','m_cb_entEmpresaCod','m_cb_entFornVis','m_cb_entFornCod',
         'm_cb_entNumNota','m_cb_entSerie','m_cb_entCencusVis','m_cb_entCencusCod',
         'm_cb_entHist','m_cb_entObs','m_cb_entNatVis','m_cb_entNatCod',
         'm_cb_entTipVis','m_cb_entTipCod','m_cb_entDtNeg','m_cb_entDtVenc']
            .forEach(id => { const el = $(id); if (el) el.value = ''; });
        _renderEntItens();
        atualizarVisivelReq();
        const msg = $('m_cb_reqMsg');
        msg.textContent = 'Carregando…'; msg.className = 'm-cb-msg m-cb-msg-info';
        openSheet('nova-req');
        try {
            const resp = await fetch(`/sankhya/combustivel/api/entrada/${nunota}/`,
                                     { credentials: 'same-origin' });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || 'Falha ao carregar.';
                msg.className = 'm-cb-msg';
                return;
            }
            const cab = data.cabecalho || {};
            const fin = data.financeiro || {};
            const itens = data.itens || [];
            if (cab.CODEMP) {
                $('m_cb_entEmpresaCod').value = cab.CODEMP;
                $('m_cb_entEmpresaVis').value = String(cab.CODEMP);
                _preencherNomeEmpresaDefault(cab.CODEMP);
            }
            if (cab.CODPARC) {
                $('m_cb_entFornCod').value = cab.CODPARC;
                $('m_cb_entFornVis').value = `${cab.CODPARC} — ${cab.NOMEPARC || ''}`;
            }
            if (cab.NUMNOTA) $('m_cb_entNumNota').value = cab.NUMNOTA;
            if (cab.SERIENOTA) $('m_cb_entSerie').value = cab.SERIENOTA;
            if (cab.DTNEG) $('m_cb_entDtNeg').value = cab.DTNEG;
            if (fin.DTVENC) $('m_cb_entDtVenc').value = fin.DTVENC;
            else if (cab.DTNEG) $('m_cb_entDtVenc').value = cab.DTNEG;
            if (cab.CODCENCUS) {
                $('m_cb_entCencusCod').value = cab.CODCENCUS;
                $('m_cb_entCencusVis').value = String(cab.CODCENCUS);
            }
            if (cab.CODNAT) {
                $('m_cb_entNatCod').value = cab.CODNAT;
                $('m_cb_entNatVis').value = String(cab.CODNAT);
            }
            if (cab.CODTIPVENDA) {
                $('m_cb_entTipCod').value = cab.CODTIPVENDA;
                $('m_cb_entTipVis').value = String(cab.CODTIPVENDA);
            }
            if (fin.HISTORICO) $('m_cb_entHist').value = fin.HISTORICO;
            if (cab.OBSERVACAO) $('m_cb_entObs').value = cab.OBSERVACAO;
            ESTADO.entItens = [];
            itens.forEach(it => _addItemEntrada({
                codprod: it.CODPROD, descrprod: it.DESCRPROD,
                qtd: it.QTDNEG, vlrunit: it.VLRUNIT,
            }));
            if (ESTADO.entItens.length === 0) _addItemEntrada();
            msg.textContent = ''; msg.className = 'm-cb-msg';
            // Atualiza header pra "Editar entrada NUNOTA X"
            _atualizarHeaderSheetReq();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
            msg.className = 'm-cb-msg';
        }
    }

    function validarEntrada() {
        const erros = [];
        if (!$('m_cb_entEmpresaCod').value) erros.push('Empresa obrigatória.');
        if (!$('m_cb_entFornCod').value) erros.push('Fornecedor obrigatório.');
        if (!$('m_cb_entCencusCod').value) erros.push('Centro obrigatório.');
        const numnota = parseInt($('m_cb_entNumNota').value || '0', 10);
        if (!numnota || numnota <= 0) erros.push('Nº Nota obrigatório.');
        const dtn = $('m_cb_entDtNeg').value;
        const dtv = $('m_cb_entDtVenc').value || dtn;
        if (dtv && dtn && dtv < dtn) erros.push('Vencimento anterior à data.');
        const validos = ESTADO.entItens.filter(it =>
            it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0);
        if (validos.length === 0) erros.push('Adicione ≥1 item com combustível, qtd e valor.');
        return erros;
    }

    async function enviarEntrada() {
        // Sheet único — msg/salvar compartilhados
        const msg = $('m_cb_reqMsg');
        msg.textContent = ''; msg.className = 'm-cb-msg';
        const erros = validarEntrada();
        if (erros.length) { msg.textContent = erros.join(' '); return; }
        const dtn = $('m_cb_entDtNeg').value || hoje();
        const dtv = $('m_cb_entDtVenc').value || dtn;
        const itens = ESTADO.entItens
            .filter(it => it.codprod && (parseFloat(it.qtd) || 0) > 0 && (parseFloat(it.vlrunit) || 0) > 0)
            .map(it => ({
                codprod: parseInt(it.codprod, 10),
                qtd: parseFloat(it.qtd),
                vlrunit: parseFloat(it.vlrunit),
            }));
        const payload = {
            codemp: parseInt($('m_cb_entEmpresaCod').value, 10),
            codparc: parseInt($('m_cb_entFornCod').value, 10),
            numnota: parseInt($('m_cb_entNumNota').value, 10),
            serienota: ($('m_cb_entSerie').value || '').trim() || null,
            itens,
            codcencus: parseInt($('m_cb_entCencusCod').value, 10),
            codnat: parseInt($('m_cb_entNatCod').value || '0', 10) || null,
            codtipvenda: parseInt($('m_cb_entTipCod').value || '0', 10) || null,
            dtneg: dtn, dtvenc: dtv,
            historico: $('m_cb_entHist').value.trim() || null,
            observacao: $('m_cb_entObs').value.trim() || null,
        };
        const btn = $('m_cb_reqSalvar');
        btn.disabled = true;
        const txt0 = btn.querySelector('span').textContent;
        btn.querySelector('span').textContent = 'Enviando…';
        try {
            const url = ESTADO.entEditandoNunota
                ? `/sankhya/combustivel/api/entrada/${ESTADO.entEditandoNunota}/editar/`
                : URL_ENT_CRIAR;
            const resp = await IAgro.postJSON(url, payload);
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || `Erro ${resp.status || ''}`;
                return;
            }
            const acao = ESTADO.entEditandoNunota ? 'atualizada' : 'criada';
            const extras = data.nufin ? ` · NUFIN ${data.nufin}` : '';
            mostrarToast(`Entrada ${data.nunota} · NF ${data.numnota} ${acao}${extras}.`, 'success');
            closeSheet('nova-req');
            carregarMovimentacoes();
            carregarEstoque();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
        } finally {
            btn.disabled = false;
            btn.querySelector('span').textContent = txt0;
        }
    }

    // =========================================================================
    // SHEET EXCLUIR (compartilhado req + ent)
    // =========================================================================
    function abrirSheetExcluir(tipo, nunota, resumo) {
        ESTADO.excluirTipo = tipo;
        ESTADO.excluirNunota = nunota;
        const titulo = $('m_cb_excTitulo');
        if (titulo) {
            titulo.innerHTML = tipo === 'ent'
                ? '<i class="ph ph-trash"></i> Excluir entrada'
                : '<i class="ph ph-trash"></i> Excluir requisição';
        }
        const resEl = $('m_cb_excResumo');
        if (resEl) resEl.textContent = `NUNOTA ${nunota}${resumo ? ' · ' + resumo : ''}`;
        $('m_cb_excMotivo').value = '';
        const msg = $('m_cb_excMsg');
        if (msg) { msg.textContent = ''; msg.className = 'm-cb-msg'; }
        openSheet('excluir');
    }

    async function confirmarExcluir() {
        const msg = $('m_cb_excMsg');
        msg.textContent = ''; msg.className = 'm-cb-msg';
        const motivo = ($('m_cb_excMotivo').value || '').trim();
        if (!motivo) { msg.textContent = 'Motivo obrigatório.'; return; }
        if (!ESTADO.excluirNunota) return;

        const btn = $('m_cb_excConfirmar');
        btn.disabled = true;
        const txt0 = btn.querySelector('span').textContent;
        btn.querySelector('span').textContent = 'Excluindo…';
        try {
            const nunota = ESTADO.excluirNunota;
            const url = ESTADO.excluirTipo === 'ent'
                ? `/sankhya/combustivel/api/entrada/${nunota}/excluir/`
                : `/sankhya/combustivel/api/requisicao/${nunota}/excluir/`;
            const resp = await IAgro.postJSON(url, { motivo });
            const data = resp.body || {};
            if (!resp.ok || !data.ok) {
                msg.textContent = data.error || `Erro ${resp.status || ''}`;
                return;
            }
            const label = ESTADO.excluirTipo === 'ent' ? 'Entrada' : 'Requisição';
            mostrarToast(`${label} ${data.nunota} excluída.`, 'success');
            closeSheet('excluir');
            // Se também havia sheet único aberto (excluindo de dentro do editar), fecha
            closeSheet('nova-req');
            carregarMovimentacoes();
            carregarEstoque();
        } catch (err) {
            msg.textContent = 'Falha de conexão.';
        } finally {
            btn.disabled = false;
            btn.querySelector('span').textContent = txt0;
        }
    }

    // =========================================================================
    // Typeaheads — montagem
    // =========================================================================
    function montarTypeaheads() {
        if (!window.IAgro || !IAgro.attachTypeahead) return;

        // === Req ===
        IAgro.attachTypeahead({
            inputId: 'm_cb_reqVeiVis', hiddenId: 'm_cb_reqVeiCod', dropdownId: 'm_cb_reqVeiDD',
            url: URL_VEICULOS, limit: 30, debounceMs: 250, minChars: 0,
            extraQuery: () => `tipo=${tipoReqSelecionado()}`,
            pickItems: (d) => d.results || [],
            pickCod: (it) => it.codveiculo,
            pickDescr: (it) => `${it.placa} — ${it.marcamodelo || it.especietipo || ''}`.trim(),
            pickExtra: (it) => ({
                codparc: it.codparc || '', nomeparc: it.nomeparc || '',
                codcencus: it.codcencus || '', proprio: it.proprio || '',
            }),
            renderItem: (it) => `
                <div style="display:flex; justify-content:space-between;">
                    <span><strong>${it.placa}</strong> — ${it.marcamodelo || it.especietipo || ''}</span>
                    <span style="font-size:10px; color:#94a3b8;">${it.proprio === 'S' ? 'Próprio' : 'Terceiro'}</span>
                </div>
            `,
            onSelect: (cod, descr, item) => {
                if (item.dataset.codcencus) {
                    $('m_cb_reqCencusCod').value = item.dataset.codcencus;
                    $('m_cb_reqCencusVis').value = `${item.dataset.codcencus} (do veículo)`;
                }
                const hint = $('m_cb_reqVeiHint');
                if (hint) hint.textContent = item.dataset.nomeparc ? `Parceiro: ${item.dataset.nomeparc}` : '';
            },
            onClear: () => {
                const hint = $('m_cb_reqVeiHint');
                if (hint) hint.textContent = '';
            },
        });

        IAgro.attachTypeahead({
            inputId: 'm_cb_reqProdVis', hiddenId: 'm_cb_reqProdCod', dropdownId: 'm_cb_reqProdDD',
            url: URL_PRODUTOS, limit: 30, debounceMs: 250, minChars: 0,
            pickItems: (d) => d.results || [],
            pickCod: (it) => it.codprod, pickDescr: (it) => it.descrprod,
            renderItem: (it) => `${it.codprod} — ${it.descrprod} <span style="color:#94a3b8;font-size:10px;">(${it.codvol})</span>`,
            onSelect: async (cod) => {
                if (tipoReqSelecionado() === 'EXTERNA_POSTO') return;
                try {
                    const r = await fetch(`/sankhya/combustivel/api/ultimo-preco/?codprod=${encodeURIComponent(cod)}`,
                                          { credentials: 'same-origin' });
                    if (!r.ok) return;
                    const j = await r.json();
                    if (j.ok && parseFloat(j.vlrunit || 0) > 0) {
                        $('m_cb_reqVlu').value = parseFloat(j.vlrunit).toFixed(4);
                    }
                } catch (_) {}
            },
        });

        IAgro.attachTypeahead({
            inputId: 'm_cb_reqCencusVis', hiddenId: 'm_cb_reqCencusCod', dropdownId: 'm_cb_reqCencusDD',
            url: URL_CENCUS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codcencus,
            pickDescr: (it) => it.descr || it.descrcencus || '',
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_reqNatVis', hiddenId: 'm_cb_reqNatCod', dropdownId: 'm_cb_reqNatDD',
            url: URL_NATUREZAS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codnat,
            pickDescr: (it) => it.descr || it.descrnat || '',
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_reqTipVis', hiddenId: 'm_cb_reqTipCod', dropdownId: 'm_cb_reqTipDD',
            url: URL_TIPVENDA, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codtipvenda,
            pickDescr: (it) => it.descr || it.descrtipvenda || '',
            onSelect: () => _recalcularDtVencExterno(),
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_reqPostoVis', hiddenId: 'm_cb_reqPostoCod', dropdownId: 'm_cb_reqPostoDD',
            url: URL_PARCEIROS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codparc,
            pickDescr: (it) => it.descr || it.nomeparc || '',
        });

        // === Entrada ===
        IAgro.attachTypeahead({
            inputId: 'm_cb_entEmpresaVis', hiddenId: 'm_cb_entEmpresaCod', dropdownId: 'm_cb_entEmpresaDD',
            url: URL_EMPRESAS, limit: 30, debounceMs: 250, minChars: 0,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codemp,
            pickDescr: (it) => it.descr || it.nomefantasia || it.razaosocial || '',
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_entFornVis', hiddenId: 'm_cb_entFornCod', dropdownId: 'm_cb_entFornDD',
            url: URL_PARCEIROS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codparc,
            pickDescr: (it) => it.descr || it.nomeparc || '',
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_entCencusVis', hiddenId: 'm_cb_entCencusCod', dropdownId: 'm_cb_entCencusDD',
            url: URL_CENCUS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codcencus,
            pickDescr: (it) => it.descr || it.descrcencus || '',
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_entNatVis', hiddenId: 'm_cb_entNatCod', dropdownId: 'm_cb_entNatDD',
            url: URL_NATUREZAS, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codnat,
            pickDescr: (it) => it.descr || it.descrnat || '',
        });
        IAgro.attachTypeahead({
            inputId: 'm_cb_entTipVis', hiddenId: 'm_cb_entTipCod', dropdownId: 'm_cb_entTipDD',
            url: URL_TIPVENDA, limit: 30, debounceMs: 250, minChars: 1,
            pickItems: (d) => d.results || d.items || [],
            pickCod: (it) => it.cod || it.codtipvenda,
            pickDescr: (it) => it.descr || it.descrtipvenda || '',
            onSelect: () => _recalcularDtVenc(),
        });
    }

    // Auto-cálculo DTVENC (entrada)
    async function _recalcularDtVenc() {
        const codtipv = parseInt($('m_cb_entTipCod').value || '0', 10);
        const dtn = $('m_cb_entDtNeg').value;
        if (!codtipv || !dtn) return;
        try {
            const r = await fetch(`/sankhya/combustivel/api/prazo-tipvenda/?codtipvenda=${codtipv}`,
                                  { credentials: 'same-origin' });
            const j = await r.json();
            if (!j.ok) return;
            const prazo = parseInt(j.prazo_dias || 0, 10);
            const d = new Date(dtn);
            d.setDate(d.getDate() + prazo);
            $('m_cb_entDtVenc').value = d.toISOString().slice(0, 10);
        } catch (_) {}
    }

    // Auto-cálculo DTVENC (externo)
    async function _recalcularDtVencExterno() {
        if (tipoReqSelecionado() !== 'EXTERNA_POSTO') return;
        const codtipv = parseInt($('m_cb_reqTipCod').value || '0', 10);
        const dtn = $('m_cb_reqExtDtNeg').value;
        if (!codtipv || !dtn) return;
        try {
            const r = await fetch(`/sankhya/combustivel/api/prazo-tipvenda/?codtipvenda=${codtipv}`,
                                  { credentials: 'same-origin' });
            const j = await r.json();
            if (!j.ok) return;
            const prazo = parseInt(j.prazo_dias || 0, 10);
            const d = new Date(dtn);
            d.setDate(d.getDate() + prazo);
            $('m_cb_reqExtDtVenc').value = d.toISOString().slice(0, 10);
        } catch (_) {}
    }

    // =========================================================================
    // Init
    // =========================================================================
    function init() {
        _carregarPrefs();

        // ===== Sidebar toggle (hambúrguer abre IAgro sidebar global) =====
        const sidebarToggle = document.querySelector('.combustivel-mobile .m-sidebar-toggle');
        if (sidebarToggle && window.IAgro && IAgro.toggleSidebar) {
            sidebarToggle.addEventListener('click', () => IAgro.toggleSidebar());
        } else if (sidebarToggle) {
            // Fallback simples — abre off-canvas via classe
            sidebarToggle.addEventListener('click', () => {
                document.body.classList.toggle('sidebar-mobile-open');
            });
        }

        // ===== Toggle de contexto (Estoque/Movs/Veículos) =====
        $$('.combustivel-mobile .m-cb-toggle-btn').forEach(b => {
            b.addEventListener('click', () => setCtx(b.dataset.ctx));
        });

        // ===== Bottom nav =====
        $$('.combustivel-mobile .m-bottom-nav__item').forEach(b => {
            b.addEventListener('click', () => {
                const ctx = b.dataset.ctx;
                const nav = b.dataset.nav;
                if (ctx) {
                    setActiveScreen('lista');
                    setCtx(ctx);
                } else if (nav === 'filtros') openSheet('filtros');
                else if (nav === 'mais') openSheet('mais');
            });
        });

        // ===== Filtro datas (mov) =====
        const movIni = $('m_cb_movDataIni');
        const movFim = $('m_cb_movDataFim');
        const movPrev = $('m_cb_movPrev');
        const movNext = $('m_cb_movNext');
        ESTADO.movDataIni = _primeiroDiaMesIso();
        ESTADO.movDataFim = _hojeIso();
        if (movIni) movIni.value = ESTADO.movDataIni;
        if (movFim) movFim.value = ESTADO.movDataFim;
        const replicarIni = () => {
            const v = movIni.value;
            if (!v) return;
            ESTADO.movDataIni = v;
            movFim.value = v;
            ESTADO.movDataFim = v;
            carregarMovimentacoes();
        };
        if (movIni) {
            movIni.addEventListener('change', replicarIni);
            movIni.addEventListener('input', replicarIni);   // iOS Safari
        }
        if (movFim) {
            movFim.addEventListener('change', () => {
                ESTADO.movDataFim = movFim.value;
                carregarMovimentacoes();
            });
        }
        const shiftMov = (delta) => {
            const novo = _shiftIso(ESTADO.movDataIni || _hojeIso(), delta);
            ESTADO.movDataIni = novo;
            ESTADO.movDataFim = novo;
            if (movIni) movIni.value = novo;
            if (movFim) movFim.value = novo;
            carregarMovimentacoes();
        };
        if (movPrev) movPrev.addEventListener('click', (e) => { e.preventDefault(); shiftMov(-1); });
        if (movNext) movNext.addEventListener('click', (e) => { e.preventDefault(); shiftMov(1); });

        // ===== Filtro datas (detalhe) — usa o MESMO estado global de mov =====
        const detIni = $('m_cb_detDataIni');
        const detFim = $('m_cb_detDataFim');
        const detPrev = $('m_cb_detPrev');
        const detNext = $('m_cb_detNext');
        const replicarDetIni = () => {
            const v = detIni.value;
            if (!v) return;
            ESTADO.movDataIni = v;
            detFim.value = v;
            ESTADO.movDataFim = v;
            // Sincronia com toolbar de mov
            if (movIni) movIni.value = v;
            if (movFim) movFim.value = v;
            carregarDetalheVeiculo();
        };
        if (detIni) {
            detIni.addEventListener('change', replicarDetIni);
            detIni.addEventListener('input', replicarDetIni);
        }
        if (detFim) {
            detFim.addEventListener('change', () => {
                ESTADO.movDataFim = detFim.value;
                if (movFim) movFim.value = detFim.value;
                carregarDetalheVeiculo();
            });
        }
        const shiftDet = (delta) => {
            const novo = _shiftIso(ESTADO.movDataIni || _hojeIso(), delta);
            ESTADO.movDataIni = novo;
            ESTADO.movDataFim = novo;
            if (detIni) detIni.value = novo;
            if (detFim) detFim.value = novo;
            if (movIni) movIni.value = novo;
            if (movFim) movFim.value = novo;
            carregarDetalheVeiculo();
        };
        if (detPrev) detPrev.addEventListener('click', (e) => { e.preventDefault(); shiftDet(-1); });
        if (detNext) detNext.addEventListener('click', (e) => { e.preventDefault(); shiftDet(1); });

        // ===== Pesquisa de veículo =====
        const inpBusca = $('m_cb_veiBusca');
        if (inpBusca && window.IAgro && IAgro.debounce) {
            const aplicar = IAgro.debounce((v) => {
                ESTADO.veiculoTextoBusca = (v || '').trim();
                renderVeiculos();
            }, 200);
            inpBusca.addEventListener('input', (e) => aplicar(e.target.value));
        }

        // ===== Toggle COM/MAQ =====
        $$('.combustivel-mobile .m-cb-vei-toggle-btn').forEach(b => {
            b.classList.toggle('is-active', b.dataset.filtro === ESTADO.veiculosFiltro);
            b.addEventListener('click', () => {
                ESTADO.veiculosFiltro = b.dataset.filtro;
                _salvarPrefs();
                $$('.combustivel-mobile .m-cb-vei-toggle-btn').forEach(x =>
                    x.classList.toggle('is-active', x.dataset.filtro === ESTADO.veiculosFiltro)
                );
                renderVeiculos();
            });
        });

        // ===== FABs =====
        $('m_cb_fabAtualizar').addEventListener('click', () => {
            const btn = $('m_cb_fabAtualizar');
            btn.classList.add('is-loading');
            const pendingPromises = [];
            if (ESTADO.ctx === 'estoque') pendingPromises.push(carregarEstoque());
            else if (ESTADO.ctx === 'movimentacoes') pendingPromises.push(carregarMovimentacoes());
            else if (ESTADO.ctx === 'veiculos') pendingPromises.push(carregarVeiculos());
            Promise.all(pendingPromises).finally(() => btn.classList.remove('is-loading'));
        });
        // Mai/2026 — 2026-05-28: 1 FAB único cobre os 3 tipos
        $('m_cb_fabReq').addEventListener('click', abrirSheetNovaReq);
        $('m_cb_fabReqDet').addEventListener('click', abrirSheetNovaReq);

        // ===== Voltar detalhe =====
        $('m_cb_detVoltar').addEventListener('click', popScreen);

        // ===== Lightbox voltar =====
        $('m_cb_lbVoltar').addEventListener('click', popScreen);

        // ===== Tipos req radios =====
        $$('input[name="m_cb_reqTipo"]').forEach(r => {
            r.addEventListener('change', () => {
                atualizarVisivelReq();
                const dt = $('m_cb_reqDtNeg');
                if (dt && !dt.value && tipoReqSelecionado() !== 'EXTERNA_POSTO') dt.value = hoje();
                $('m_cb_reqVeiVis').value = '';
                $('m_cb_reqVeiCod').value = '';
                $('m_cb_reqVeiHint').textContent = '';
            });
        });

        // ===== Botão + Item =====
        $('m_cb_reqAddItem').addEventListener('click', () => _addItemReqExt());
        $('m_cb_entAddItem').addEventListener('click', () => _addItemEntrada());

        // ===== Links rápidos posto =====
        $$('.combustivel-mobile .m-cb-link-posto').forEach(a => {
            a.addEventListener('click', async (e) => {
                e.preventDefault();
                const cp = a.dataset.codparc;
                if (!cp) return;
                try {
                    const resp = await fetch(`${URL_PARCEIROS}?q=${cp}&limit=5`,
                                             { credentials: 'same-origin' });
                    const data = await resp.json();
                    const items = data.results || data.items || [];
                    const match = items.find(it => String(it.cod || it.codparc) === String(cp));
                    const nome = match ? (match.descr || match.nomeparc || '') : '';
                    $('m_cb_reqPostoCod').value = cp;
                    $('m_cb_reqPostoVis').value = `${cp} — ${nome}`;
                } catch (_) {
                    $('m_cb_reqPostoCod').value = cp;
                    $('m_cb_reqPostoVis').value = String(cp);
                }
            });
        });

        // ===== Auto-recalcular DTVENC =====
        $('m_cb_entDtNeg').addEventListener('change', _recalcularDtVenc);
        $('m_cb_reqExtDtNeg').addEventListener('change', _recalcularDtVencExterno);

        // ===== Salvar =====
        // Mai/2026 — 2026-05-28: 1 botão único — enviarRequisicao roteia por tipo (incluindo ENTRADA)
        $('m_cb_reqSalvar').addEventListener('click', enviarRequisicao);
        $('m_cb_excConfirmar').addEventListener('click', confirmarExcluir);

        // ===== Sheet "Mais" =====
        $('m_cb_maisAtualizar').addEventListener('click', () => {
            closeSheet('mais');
            carregarEstoque();
            carregarMovimentacoes();
            carregarVeiculos();
        });
        $('m_cb_maisReq').addEventListener('click', () => {
            closeSheet('mais');
            abrirSheetNovaReq();
        });

        // ===== Sheet Filtros =====
        $('m_cb_filtrosAplicar').addEventListener('click', () => {
            ESTADO.filtroMov = $('m_cb_filtroMov').value;
            ESTADO.filtroTipo = $('m_cb_filtroTipo').value;
            atualizarBadgeFiltros();
            closeSheet('filtros');
            // Se está em movs, recarrega
            if (ESTADO.ctx === 'movimentacoes') carregarMovimentacoes();
        });

        // ===== Backdrop / close-sheet bindings =====
        $$('.combustivel-mobile [data-close-sheet]').forEach(el => {
            el.addEventListener('click', () => {
                const sh = el.closest('.m-sheet');
                if (sh) sh.setAttribute('aria-hidden', 'true');
            });
        });

        // ===== Typeaheads (req + entrada) =====
        montarTypeaheads();

        // ===== Swipe to back =====
        setupSwipeToBack();

        // ===== History (back button do Android volta tela) =====
        window.addEventListener('popstate', () => {
            if (ESTADO.screenStack.length > 1) {
                ESTADO.screenStack.pop();
                const prev = ESTADO.screenStack[ESTADO.screenStack.length - 1];
                setActiveScreen(prev);
            }
        });

        // ===== Carga inicial =====
        setCtx('estoque');
        // Não carrega Movs/Veículos no boot — só quando trocar de aba (lazy)
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
