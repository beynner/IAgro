/* =============================================================================
   Controle de Caixas — Mobile (Mai/2026 — 2026-05-28)

   Estratégia padrão (paridade Entrada/Classificação/Rastreio/Combustível):
   - HTML único com 2 containers paralelos (.caixas-desktop + .caixas-mobile)
   - JS auto-ativa só em viewport ≤900px (matchMedia)
   - 2 telas: lista de clientes + detalhe (hero + 5 stats + timeline)
   - 2 sheets: lançar coleta + mais (Atualizar saldo)
   - Reusa endpoints existentes do desktop
   ============================================================================= */

(function () {
    'use strict';

    if (!window.matchMedia('(max-width: 900px)').matches) return;

    const $  = (sel, ctx = document) => ctx.querySelector(sel);
    const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

    // -------------------- Estado --------------------
    const ESTADO = {
        clientes:        [],   // [{codparc, nomeparc, saldo, caixas_enviadas, ...}]
        clienteAtivo:    null, // codparc selecionado
        eventos:         [],   // timeline carregada
        incluirZerados:  false,
        buscaQ:          '',
        timelineDias:    90,
        prefillColeta:   null, // {codparc, nomeparc} ao abrir sheet a partir do detalhe
    };

    // -------------------- Helpers --------------------
    const fmtNum = (n) => new Intl.NumberFormat('pt-BR').format(Number(n) || 0);

    const fmtData = (iso) => {
        if (!iso) return '—';
        const [y, m, d] = iso.split('-');
        return `${d}/${m}/${y.slice(2)}`;
    };

    const escapeHtml = (s) => {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    };

    const normalizar = (s) => {
        if (!s) return '';
        return String(s).toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '');
    };

    const showToast = (msg, tipo) => {
        if (window.IAgro && window.IAgro.showToast) window.IAgro.showToast(msg, tipo || 'info');
        else alert(msg);
    };

    const setLoading = (btn, on) => {
        if (!btn) return;
        btn.classList.toggle('is-loading', !!on);
        btn.disabled = !!on;
    };

    // -------------------- Navegação entre telas --------------------
    const screens = {
        lista:           $('.caixas-mobile .m-screen[data-screen="lista"]'),
        detalheCliente:  $('.caixas-mobile .m-screen[data-screen="detalheCliente"]'),
    };

    let stack = ['lista'];

    function setActiveScreen(name) {
        fecharTodosSwipesEventos();
        Object.keys(screens).forEach(k => {
            const el = screens[k];
            if (!el) return;
            el.classList.toggle('is-active', k === name);
        });
    }

    function pushScreen(name) {
        if (stack[stack.length - 1] === name) return;
        stack.push(name);
        setActiveScreen(name);
        try { history.pushState({ screen: name }, '', '#' + name); } catch (e) {}
    }

    function popScreen() {
        if (stack.length <= 1) return false;
        stack.pop();
        setActiveScreen(stack[stack.length - 1]);
        return true;
    }

    window.addEventListener('popstate', () => {
        if (stack.length > 1) {
            stack.pop();
            setActiveScreen(stack[stack.length - 1]);
        }
    });

    // -------------------- Sheets --------------------
    function openSheet(name) {
        fecharTodosSwipesEventos();
        const sheet = $(`.caixas-mobile .m-sheet[data-sheet="${name}"]`);
        if (!sheet) return;
        sheet.setAttribute('aria-hidden', 'false');
    }

    function closeSheet(name) {
        const sheet = name
            ? $(`.caixas-mobile .m-sheet[data-sheet="${name}"]`)
            : $('.caixas-mobile .m-sheet[aria-hidden="false"]');
        if (!sheet) return;
        sheet.setAttribute('aria-hidden', 'true');
    }

    // -------------------- Swipe-to-back nas telas internas --------------------
    function setupSwipeToBack() {
        const TRIGGER_PCT = 0.35;
        const TRIGGER_VEL = 0.5;

        Object.keys(screens).forEach(name => {
            if (name === 'lista') return;
            const el = screens[name];
            if (!el) return;
            let touchStartX = 0, touchStartY = 0, touchStartT = 0;
            let dx = 0, dy = 0, axisLocked = '';

            el.addEventListener('touchstart', (e) => {
                if (e.touches.length !== 1) return;
                const t = e.touches[0];
                touchStartX = t.clientX;
                touchStartY = t.clientY;
                touchStartT = Date.now();
                dx = 0; dy = 0; axisLocked = '';
            }, { passive: true });

            el.addEventListener('touchmove', (e) => {
                if (e.touches.length !== 1) return;
                const t = e.touches[0];
                dx = t.clientX - touchStartX;
                dy = t.clientY - touchStartY;
                if (!axisLocked && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
                    axisLocked = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                }
                if (axisLocked === 'x' && dx > 0) {
                    el.style.transform = `translateX(${dx * 0.5}px)`;
                }
            }, { passive: true });

            el.addEventListener('touchend', () => {
                el.style.transform = '';
                if (axisLocked !== 'x' || dx <= 0) return;
                const w = window.innerWidth || 360;
                const vel = dx / Math.max(1, Date.now() - touchStartT);
                if (dx / w >= TRIGGER_PCT || vel >= TRIGGER_VEL) {
                    popScreen();
                }
            });
        });
    }

    // -------------------- Sidebar (hambúrguer) --------------------
    function setupSidebar() {
        const btn = $('.caixas-mobile .m-sidebar-toggle');
        if (!btn) return;
        btn.addEventListener('click', () => {
            const aside = document.querySelector('#appSidebar');
            if (aside) aside.classList.toggle('is-open');
            const bd = document.querySelector('.sidebar-backdrop');
            if (bd) bd.classList.toggle('is-visible');
        });
    }

    // -------------------- Carregar saldo (lista de clientes) --------------------
    async function carregarSaldo() {
        const lista = $('#m_cx_lista');
        lista.innerHTML = '<div class="m-empty-state"><i class="ph ph-spinner"></i><span>Carregando clientes…</span></div>';

        const params = new URLSearchParams();
        params.set('apenas_saldo_positivo', ESTADO.incluirZerados ? 'false' : 'true');
        if (ESTADO.buscaQ) params.set('q', ESTADO.buscaQ);

        try {
            const resp = await fetch(`/sankhya/caixas/api/saldo/?${params.toString()}`);
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'Falha ao carregar');

            ESTADO.clientes = data.linhas || [];
            renderResumo(data);
            renderClientes();
        } catch (err) {
            lista.innerHTML = `<div class="m-empty-state"><i class="ph ph-warning"></i><span>${escapeHtml(err.message)}</span></div>`;
            console.error('carregarSaldo mobile', err);
        }
    }

    function renderResumo(data) {
        $('#m_cx_resEmCampo').textContent  = fmtNum(data.total_caixas || 0);
        $('#m_cx_resClientes').textContent = fmtNum(data.total_clientes || 0);
        let q = 0, p = 0;
        for (const l of ESTADO.clientes) {
            q += l.caixas_quebradas || 0;
            p += l.caixas_perdidas  || 0;
        }
        $('#m_cx_resQuebradas').textContent = fmtNum(q);
        $('#m_cx_resPerdidas').textContent  = fmtNum(p);
    }

    function renderClientes() {
        const lista = $('#m_cx_lista');
        const filtrados = aplicarFiltroBusca(ESTADO.clientes);
        if (filtrados.length === 0) {
            const msg = ESTADO.buscaQ
                ? `Nenhum cliente bate com "${escapeHtml(ESTADO.buscaQ)}".`
                : 'Nenhum cliente com caixa em campo.';
            lista.innerHTML = `<div class="m-empty-state"><i class="ph ph-package"></i><span>${msg}</span></div>`;
            return;
        }
        const html = filtrados.map(c => {
            const zero = c.saldo === 0 ? 'm-cx-card-cliente--zero' : '';
            const ultima = c.ultima_saida || c.ultima_coleta;
            const metaUltima = ultima ? ` · ${fmtData(ultima)}` : '';
            return `
                <div class="m-cx-card-cliente ${zero}" data-codparc="${c.codparc}">
                    <div class="m-cx-card-cliente__info">
                        <div class="m-cx-card-cliente__nome">${escapeHtml(c.nomeparc)}</div>
                        <div class="m-cx-card-cliente__meta">${c.codparc}${metaUltima}</div>
                    </div>
                    <div class="m-cx-card-cliente__saldo">${fmtNum(c.saldo)}</div>
                    <i class="ph ph-caret-right m-cx-card-cliente__chevron"></i>
                </div>
            `;
        }).join('');
        lista.innerHTML = html;

        lista.querySelectorAll('.m-cx-card-cliente').forEach(card => {
            card.addEventListener('click', () => {
                const cp = parseInt(card.dataset.codparc, 10);
                abrirDetalheCliente(cp);
            });
        });
    }

    function aplicarFiltroBusca(linhas) {
        const q = normalizar(ESTADO.buscaQ);
        if (!q) return linhas;
        return linhas.filter(l =>
            normalizar(l.nomeparc).indexOf(q) >= 0 ||
            String(l.codparc).indexOf(q) >= 0,
        );
    }

    // -------------------- Tela detalhe --------------------
    async function abrirDetalheCliente(codparc) {
        ESTADO.clienteAtivo = codparc;
        const c = ESTADO.clientes.find(x => x.codparc === codparc);
        if (!c) return;

        $('#m_cx_detNome').textContent     = c.nomeparc;
        $('#m_cx_detCodparc').textContent  = `CODPARC ${c.codparc}`;
        $('#m_cx_detSaldo').textContent    = fmtNum(c.saldo);
        $('#m_cx_statEnv').textContent     = fmtNum(c.caixas_enviadas);
        $('#m_cx_statCol').textContent     = fmtNum(c.caixas_coletadas);
        $('#m_cx_statQue').textContent     = fmtNum(c.caixas_quebradas);
        $('#m_cx_statPer').textContent     = fmtNum(c.caixas_perdidas);
        $('#m_cx_timelineDias').textContent = ESTADO.timelineDias;

        $('#m_cx_timeline').innerHTML = '<div class="m-empty-state"><i class="ph ph-clock"></i><span>Carregando timeline…</span></div>';

        pushScreen('detalheCliente');

        try {
            const resp = await fetch(`/sankhya/caixas/api/timeline/${codparc}/?dias=${ESTADO.timelineDias}`);
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'Falha');
            ESTADO.eventos = data.eventos || [];
            renderTimeline();
        } catch (err) {
            $('#m_cx_timeline').innerHTML = `<div class="m-empty-state"><i class="ph ph-warning"></i><span>${escapeHtml(err.message)}</span></div>`;
            console.error('abrirDetalheCliente mobile', err);
        }
    }

    function renderTimeline() {
        const tl = $('#m_cx_timeline');
        if (!ESTADO.eventos.length) {
            tl.innerHTML = '<div class="m-empty-state"><i class="ph ph-clock"></i><span>Sem eventos no período.</span></div>';
            return;
        }

        const mapaTipo = {
            'VIAGEM':        { classe: 'm-cx-evento--viagem',    icone: 'ph-truck',            label: 'Viagem' },
            'COLETA':        { classe: 'm-cx-evento--coleta',    icone: 'ph-arrow-down-left',  label: 'Coleta' },
            'QUEBRA':        { classe: 'm-cx-evento--quebra',    icone: 'ph-warning',          label: 'Quebra' },
            'PERDA':         { classe: 'm-cx-evento--perda',     icone: 'ph-x-circle',         label: 'Perda' },
            'AJUSTE_SALDO':  { classe: 'm-cx-evento--ajuste',    icone: 'ph-pencil-simple',    label: 'Ajuste' },
            // Legado (eventos pre-2026-05-29):
            'SAIDA':         { classe: 'm-cx-evento--saida',     icone: 'ph-arrow-up-right',   label: 'Saída (legado)' },
            'DEVOLUCAO':     { classe: 'm-cx-evento--devolucao', icone: 'ph-arrow-down-left',  label: 'Devolução (legado)' },
        };

        const html = ESTADO.eventos.map((e, idx) => {
            const m = mapaTipo[e.tipo] || { classe: '', icone: 'ph-circle', label: e.tipo };
            const estornadoCls = e.estornado ? 'm-cx-evento--estornado' : '';
            const data = fmtData(e.data);

            let infoExtra = '';
            if (e.tipo === 'VIAGEM' && e.num_viagem) {
                const desc = e.descricao ? ` — ${escapeHtml(e.descricao)}` : '';
                infoExtra = `<div class="m-cx-evento__desc">Viagem #${e.num_viagem}${desc}</div>`;
                if (e.observacao) {
                    infoExtra += `<div class="m-cx-evento__obs">${escapeHtml(e.observacao)}</div>`;
                }
            } else if (e.nunota) {
                const notaLbl = e.numnota ? `Nota ${e.numnota}` : `NUNOTA ${e.nunota}`;
                infoExtra = `<div class="m-cx-evento__desc">${escapeHtml(notaLbl)}${e.descricao ? ' — ' + escapeHtml(e.descricao) : ''}</div>`;
            } else if (e.observacao) {
                infoExtra = `<div class="m-cx-evento__desc">${escapeHtml(e.observacao)}</div>`;
            }

            const usuario = (e.tipo === 'COLETA' && e.motorista_nome)
                ? ` · Motorista: ${escapeHtml(e.motorista_nome)}`
                : (e.nomeusu ? ` · ${escapeHtml(e.nomeusu)}` : '');
            const estornadoTag = e.estornado ? '<span class="m-cx-evento__estornado-tag">ESTORNADO</span>' : '';

            // Sinal: AJUSTE_SALDO pode ser negativo; VIAGEM/SAIDA é positivo; demais descontam
            let sinal, qtdExibida;
            if (e.tipo === 'AJUSTE_SALDO') {
                qtdExibida = Math.abs(e.qtd_caixas);
                sinal = e.qtd_caixas >= 0 ? '+' : '−';
            } else if (e.tipo === 'VIAGEM' || e.tipo === 'SAIDA') {
                qtdExibida = e.qtd_caixas;
                sinal = '+';
            } else {
                qtdExibida = e.qtd_caixas;
                sinal = '−';
            }

            const podeEstornar = e.id_coleta && !e.estornado;
            const swipeBtnEstornar = podeEstornar
                ? `<button type="button" class="m-cx-evento__swipe-estornar" data-id="${e.id_coleta}" aria-label="Estornar">
                       <i class="ph ph-arrow-counter-clockwise"></i>
                   </button>`
                : '';

            // Eventos do tipo VIAGEM podem ser "transferidos" pra Logística (swipe-direita)
            const podeTransferir = e.tipo === 'VIAGEM' && e.viagem_id;
            const swipeBtnTransferir = podeTransferir
                ? `<button type="button" class="m-cx-evento__swipe-transferir" data-viagem-id="${e.viagem_id}" aria-label="Abrir viagem na Logística">
                       <i class="ph ph-arrow-square-out"></i>
                   </button>`
                : '';

            const viagemIdAttr = podeTransferir ? ` data-viagem-id="${e.viagem_id}"` : '';

            return `
                <div class="m-cx-evento-wrap" data-idx="${idx}"${viagemIdAttr}>
                    ${swipeBtnEstornar}
                    ${swipeBtnTransferir}
                    <div class="m-cx-evento ${m.classe} ${estornadoCls}">
                        <div class="m-cx-evento__icone"><i class="ph ${m.icone}"></i></div>
                        <div class="m-cx-evento__corpo">
                            <div class="m-cx-evento__titulo">
                                ${m.label}${estornadoTag}
                                <small>${data}${usuario}</small>
                            </div>
                            ${infoExtra}
                        </div>
                        <div class="m-cx-evento__qtd">${sinal}${fmtNum(qtdExibida)}</div>
                    </div>
                </div>
            `;
        }).join('');
        tl.innerHTML = html;

        setupSwipeEventos();
    }

    // -------------------- Swipe nos eventos da timeline --------------------
    // Esquerda → estornar (coletas manuais)
    // Direita  → transferir pra Logística (cards de Viagem)
    const SWIPE_REVEAL_PX  = 56;
    const SWIPE_TRIGGER_PX = 28;

    function setupSwipeEventos() {
        const wraps = $$('.m-cx-evento-wrap');
        wraps.forEach(wrap => {
            const btnEstornar = wrap.querySelector('.m-cx-evento__swipe-estornar');
            const btnTransferir = wrap.querySelector('.m-cx-evento__swipe-transferir');
            const card = wrap.querySelector('.m-cx-evento');
            if (!card) return;
            if (!btnEstornar && !btnTransferir) return;   // card sem ações disponíveis

            const podeEstornar = !!btnEstornar;
            const podeTransferir = !!btnTransferir;

            let startX = 0, startY = 0, dx = 0, dy = 0, axisLocked = '';
            let starting = false;

            const onStart = (e) => {
                if (e.touches.length !== 1) return;
                const t = e.touches[0];
                startX = t.clientX;
                startY = t.clientY;
                dx = 0; dy = 0; axisLocked = '';
                starting = true;
            };

            const onMove = (e) => {
                if (!starting || e.touches.length !== 1) return;
                const t = e.touches[0];
                dx = t.clientX - startX;
                dy = t.clientY - startY;
                if (!axisLocked && (Math.abs(dx) > 6 || Math.abs(dy) > 6)) {
                    axisLocked = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                }
                if (axisLocked !== 'x') return;
                const abertoEsq = wrap.dataset.swipeOpen === '1';
                const abertoDir = wrap.dataset.swipeRight === '1';
                let base = 0;
                if (abertoEsq) base = -SWIPE_REVEAL_PX;
                else if (abertoDir) base = SWIPE_REVEAL_PX;
                let v = base + dx;
                // Resistência elástica nas pontas
                if (v < -SWIPE_REVEAL_PX) v = -SWIPE_REVEAL_PX + (v + SWIPE_REVEAL_PX) * 0.3;
                if (v > SWIPE_REVEAL_PX) v = SWIPE_REVEAL_PX + (v - SWIPE_REVEAL_PX) * 0.3;
                // Bloquear direção sem botão disponível
                if (v < 0 && !podeEstornar) v = v * 0.3;
                if (v > 0 && !podeTransferir) v = v * 0.3;
                card.style.transform = `translateX(${v}px)`;
            };

            const onEnd = () => {
                if (!starting) return;
                starting = false;
                if (axisLocked !== 'x') return;
                const abertoEsq = wrap.dataset.swipeOpen === '1';
                const abertoDir = wrap.dataset.swipeRight === '1';

                if (abertoEsq) {
                    // Aberto pra esquerda — só fecha se swipou pra direita forte
                    if (dx > SWIPE_TRIGGER_PX) {
                        wrap.dataset.swipeOpen = '0';
                        card.style.transform = '';
                    } else {
                        card.style.transform = `translateX(-${SWIPE_REVEAL_PX}px)`;
                    }
                } else if (abertoDir) {
                    // Aberto pra direita — só fecha se swipou pra esquerda forte
                    if (dx < -SWIPE_TRIGGER_PX) {
                        wrap.dataset.swipeRight = '0';
                        card.style.transform = '';
                    } else {
                        card.style.transform = `translateX(${SWIPE_REVEAL_PX}px)`;
                    }
                } else {
                    // Fechado — abrir conforme direção e disponibilidade
                    if (dx < -SWIPE_TRIGGER_PX && podeEstornar) {
                        fecharTodosSwipesEventos(wrap);
                        wrap.dataset.swipeOpen = '1';
                        card.style.transform = `translateX(-${SWIPE_REVEAL_PX}px)`;
                    } else if (dx > SWIPE_TRIGGER_PX && podeTransferir) {
                        fecharTodosSwipesEventos(wrap);
                        wrap.dataset.swipeRight = '1';
                        card.style.transform = `translateX(${SWIPE_REVEAL_PX}px)`;
                    } else {
                        card.style.transform = '';
                    }
                }
            };

            card.addEventListener('touchstart', onStart, { passive: true });
            card.addEventListener('touchmove',  onMove,  { passive: true });
            card.addEventListener('touchend',   onEnd);

            // Click no card aberto fecha qualquer swipe (cancelar implícito)
            card.addEventListener('click', () => {
                if (wrap.dataset.swipeOpen === '1' || wrap.dataset.swipeRight === '1') {
                    wrap.dataset.swipeOpen = '0';
                    wrap.dataset.swipeRight = '0';
                    card.style.transform = '';
                }
            });

            // Click no botão estornar
            if (btnEstornar) {
                btnEstornar.addEventListener('click', async (ev) => {
                    ev.stopPropagation();
                    const id = parseInt(btnEstornar.dataset.id, 10);
                    await estornarColeta(id);
                });
            }
            // Click no botão transferir → abrir Logística mobile na viagem
            if (btnTransferir) {
                btnTransferir.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    const viagemId = parseInt(btnTransferir.dataset.viagemId, 10);
                    if (!viagemId) return;
                    window.location.href = '/sankhya/logistica/?viagem=' + viagemId;
                });
            }
        });
    }

    function fecharTodosSwipesEventos(except) {
        $$('.m-cx-evento-wrap').forEach(wrap => {
            if (wrap === except) return;
            const abertoEsq = wrap.dataset.swipeOpen === '1';
            const abertoDir = wrap.dataset.swipeRight === '1';
            if (!abertoEsq && !abertoDir) return;
            wrap.dataset.swipeOpen = '0';
            wrap.dataset.swipeRight = '0';
            const card = wrap.querySelector('.m-cx-evento');
            if (card) card.style.transform = '';
        });
    }

    // -------------------- Estornar coleta (Opção B — confirmarAcao + prompt) --------------------
    async function estornarColeta(idColeta) {
        if (!idColeta) return;

        let motivo = '';
        if (window.IAgro && window.IAgro.confirmarAcao) {
            const ok = await window.IAgro.confirmarAcao({
                titulo:   'Estornar lançamento',
                mensagem: 'Este lançamento vai ser marcado como estornado. O saldo do cliente volta a contar. O registro fica preservado pra auditoria. Tem certeza?',
                tipo:     'aviso',
            });
            if (!ok) return;
        } else {
            if (!confirm('Estornar este lançamento?')) return;
        }

        motivo = prompt('Motivo do estorno (recomendado):', 'Lançamento incorreto') || 'Estornado pelo operador';

        try {
            const resp = await window.IAgro.postJSON(
                `/sankhya/caixas/api/coleta/${idColeta}/estornar/`,
                { motivo_estorno: motivo },
            );
            const body = resp.body || {};
            if (!resp.ok || !body.ok) {
                showToast(body.error || `Erro HTTP ${resp.status}`, 'error');
                return;
            }
            showToast('Lançamento estornado.', 'success');
            // Recarrega saldo + timeline atual SEM navegar (já está na tela detalhe)
            await carregarSaldo();
            if (ESTADO.clienteAtivo) {
                await recarregarDetalheSemNavegar(ESTADO.clienteAtivo);
            }
        } catch (err) {
            showToast('Falha de comunicação: ' + err.message, 'error');
        }
    }

    // -------------------- Sheet: Lançar coleta --------------------
    function aplicarVisibilidadeMotoristaCx() {
        const motivoEl = document.querySelector('input[name="m_cx_motivo"]:checked');
        const motivo = (motivoEl && motivoEl.value) || 'COLETA';
        const wrap = $('#m_cx_colMotoristaWrap');
        if (!wrap) return;
        // Motorista só faz sentido em COLETA (caixas voltando do cliente)
        wrap.style.display = (motivo === 'COLETA') ? '' : 'none';
        if (motivo !== 'COLETA') {
            $('#m_cx_colMotoristaCodparc').value = '';
            $('#m_cx_colMotorista').value = '';
        }
    }

    function abrirSheetColeta(prefillCodparc, prefillNome) {
        // Reset
        $('#m_cx_colCodparc').value = '';
        $('#m_cx_colCliente').value = '';
        $('#m_cx_colData').valueAsDate = new Date();
        $('#m_cx_colQtd').value = '';
        $('#m_cx_colObs').value = '';
        $('#m_cx_colMotorista').value = '';
        $('#m_cx_colMotoristaCodparc').value = '';
        const r = document.querySelector('input[name="m_cx_motivo"][value="COLETA"]');
        if (r) r.checked = true;
        aplicarVisibilidadeMotoristaCx();
        const msg = $('#m_cx_colMsg');
        msg.hidden = true;

        if (prefillCodparc) {
            $('#m_cx_colCodparc').value = prefillCodparc;
            $('#m_cx_colCliente').value = prefillNome || '';
        }

        openSheet('coleta');
    }

    function setupSheetColeta() {
        // Typeahead cliente
        if (window.IAgro && window.IAgro.attachTypeahead) {
            window.IAgro.attachTypeahead({
                inputId:    'm_cx_colCliente',
                hiddenId:   'm_cx_colCodparc',
                dropdownId: 'm_cx_colClienteDropdown',
                url:        '/sankhya/parceiros/search/',
                positionFixed: true,
                pickItems:  (data) => data.results || [],
                pickCod:    (it) => it.codparc,
                pickDescr:  (it) => it.nomeparc,
                renderItem: (it) => `${it.codparc} — ${it.nomeparc}`,
            });

            // Typeahead motorista — reusa endpoint da Logística (tipo=4=MOTORISTA)
            window.IAgro.attachTypeahead({
                inputId:    'm_cx_colMotorista',
                hiddenId:   'm_cx_colMotoristaCodparc',
                dropdownId: 'm_cx_colMotoristaDropdown',
                url:        '/sankhya/logistica/api/parceiros/?tipo=4',
                positionFixed: true,
                pickItems:  (data) => data.parceiros || [],
                pickCod:    (it) => it.codparc,
                pickDescr:  (it) => it.nomeparc,
                renderItem: (it) => `${it.codparc} — ${it.nomeparc}`,
            });
        }

        // Listener nos motivos: mostra/esconde motorista
        document.querySelectorAll('input[name="m_cx_motivo"]').forEach(el => {
            el.addEventListener('change', aplicarVisibilidadeMotoristaCx);
        });

        $('#m_cx_colSalvar').addEventListener('click', async () => {
            const msg = $('#m_cx_colMsg');
            const codparc = parseInt($('#m_cx_colCodparc').value || '0', 10);
            const qtd     = parseInt($('#m_cx_colQtd').value || '0', 10);
            const data    = $('#m_cx_colData').value;
            const motivo  = (document.querySelector('input[name="m_cx_motivo"]:checked') || {}).value || 'COLETA';
            const obs     = $('#m_cx_colObs').value.trim();
            const codparcMotorista = parseInt($('#m_cx_colMotoristaCodparc').value || '0', 10);

            if (!codparc || !data) {
                msg.textContent = 'Cliente e data são obrigatórios.';
                msg.className = 'm-cx-msg is-error';
                msg.hidden = false;
                return;
            }
            if (isNaN(qtd) || qtd < 1) {
                msg.textContent = 'Quantidade deve ser > 0.';
                msg.className = 'm-cx-msg is-error';
                msg.hidden = false;
                return;
            }
            if (motivo === 'COLETA' && !codparcMotorista) {
                msg.textContent = 'Motorista é obrigatório em coletas. Informe quem foi buscar as caixas.';
                msg.className = 'm-cx-msg is-error';
                msg.hidden = false;
                return;
            }

            try {
                const payload = {
                    codparc, qtd_caixas: qtd, data_coleta: data, motivo, observacao: obs,
                };
                if (codparcMotorista) payload.codparc_motorista = codparcMotorista;
                const resp = await window.IAgro.postJSON('/sankhya/caixas/api/coleta/criar/', payload);
                const body = resp.body || {};
                if (!resp.ok || !body.ok) {
                    msg.textContent = body.error || `Erro HTTP ${resp.status}`;
                    msg.className = 'm-cx-msg is-error';
                    msg.hidden = false;
                    return;
                }
                showToast('Coleta lançada.', 'success');
                closeSheet('coleta');
                await carregarSaldo();
                if (ESTADO.clienteAtivo) {
                    await recarregarDetalheSemNavegar(ESTADO.clienteAtivo);
                }
            } catch (err) {
                msg.textContent = 'Falha de comunicação: ' + err.message;
                msg.className = 'm-cx-msg is-error';
                msg.hidden = false;
            }
        });
    }

    // Recarrega o detalhe do cliente atual SEM navegar (sem pushScreen).
    // Usado pelo botão Atualizar da tela detalhe.
    async function recarregarDetalheSemNavegar(codparc) {
        const c = ESTADO.clientes.find(x => x.codparc === codparc);
        if (!c) return;
        $('#m_cx_detNome').textContent     = c.nomeparc;
        $('#m_cx_detCodparc').textContent  = `CODPARC ${c.codparc}`;
        $('#m_cx_detSaldo').textContent    = fmtNum(c.saldo);
        $('#m_cx_statEnv').textContent     = fmtNum(c.caixas_enviadas);
        $('#m_cx_statCol').textContent     = fmtNum(c.caixas_coletadas);
        $('#m_cx_statQue').textContent     = fmtNum(c.caixas_quebradas);
        $('#m_cx_statPer').textContent     = fmtNum(c.caixas_perdidas);
        try {
            const resp = await fetch(`/sankhya/caixas/api/timeline/${codparc}/?dias=${ESTADO.timelineDias}`);
            const data = await resp.json();
            if (data.ok) {
                ESTADO.eventos = data.eventos || [];
                renderTimeline();
            }
        } catch (err) {
            console.warn('recarregarDetalhe mobile falhou:', err);
        }
    }

    // Atualizar saldo da LISTA — não navega pra detalhe (Mai/2026 — 2026-05-29).
    async function atualizarSaldo() {
        const fab = $('#m_cx_fabAtualizar');
        const banner = $('#m_cx_banner');
        const bannerMsg = $('#m_cx_bannerMsg');
        setLoading(fab, true);
        if (banner) {
            bannerMsg.textContent = 'Atualizando saldo…';
            banner.hidden = false;
        }
        try {
            await window.IAgro.postJSON('/sankhya/caixas/api/refresh-pesos/', {});
        } catch (err) {
            console.warn('refresh-pesos mobile falhou:', err);
        } finally {
            if (banner) banner.hidden = true;
            setLoading(fab, false);
        }
        await carregarSaldo();
    }

    // Atualizar a partir da tela DETALHE — recarrega só o detalhe atual.
    async function atualizarDetalheAtual() {
        const fab = $('#m_cx_fabAtualizarDetalhe');
        setLoading(fab, true);
        try {
            await window.IAgro.postJSON('/sankhya/caixas/api/refresh-pesos/', {});
        } catch (err) {
            console.warn('refresh-pesos detalhe falhou:', err);
        }
        await carregarSaldo();   // mantém o array ESTADO.clientes em dia
        if (ESTADO.clienteAtivo) {
            await recarregarDetalheSemNavegar(ESTADO.clienteAtivo);
        }
        setLoading(fab, false);
    }

    // -------------------- Bottom nav --------------------
    function setupBottomNav() {
        const nav = $('.caixas-mobile .m-bottom-nav');
        if (!nav) return;
        nav.querySelectorAll('.m-bottom-nav__item').forEach(item => {
            item.addEventListener('click', () => {
                const acao = item.dataset.nav;
                nav.querySelectorAll('.m-bottom-nav__item').forEach(i => i.classList.toggle('is-active', i === item));
                if (acao === 'lista') {
                    while (stack.length > 1) stack.pop();
                    setActiveScreen('lista');
                } else if (acao === 'buscar') {
                    while (stack.length > 1) stack.pop();
                    setActiveScreen('lista');
                    setTimeout(() => {
                        const inp = $('#m_cx_search');
                        if (inp) { inp.focus(); inp.select(); }
                    }, 50);
                    nav.querySelectorAll('.m-bottom-nav__item').forEach(i => i.classList.toggle('is-active', i.dataset.nav === 'lista'));
                } else if (acao === 'mais') {
                    openSheet('mais');
                    nav.querySelectorAll('.m-bottom-nav__item').forEach(i => i.classList.toggle('is-active', i.dataset.nav === 'lista'));
                }
            });
        });
    }

    // -------------------- Sheet "Mais" --------------------
    function setupSheetMais() {
        $('#m_cx_maisAtualizar').addEventListener('click', () => {
            closeSheet('mais');
            atualizarSaldo();
        });
        $('#m_cx_maisColeta').addEventListener('click', () => {
            closeSheet('mais');
            const codparc = ESTADO.clienteAtivo;
            const c = codparc ? ESTADO.clientes.find(x => x.codparc === codparc) : null;
            abrirSheetColeta(codparc, c ? c.nomeparc : null);
        });
    }

    // -------------------- Botões globais (close sheets, back) --------------------
    function setupCloseSheets() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-close-sheet]');
            if (btn) {
                const sheet = btn.closest('.m-sheet');
                if (sheet) sheet.setAttribute('aria-hidden', 'true');
            }
        });
    }

    function setupBackButtons() {
        $$('.caixas-mobile .m-back-btn').forEach(btn => {
            btn.addEventListener('click', () => popScreen());
        });
    }

    // -------------------- Setup busca --------------------
    function setupBusca() {
        const inp = $('#m_cx_search');
        if (!inp) return;
        let t = null;
        inp.addEventListener('input', () => {
            clearTimeout(t);
            t = setTimeout(() => {
                ESTADO.buscaQ = inp.value.trim();
                renderClientes();
            }, 200);
        });
    }

    // -------------------- FABs --------------------
    function setupFabs() {
        // Tela LISTA: só FAB azul Atualizar (Mai/2026 — 2026-05-29: FAB verde removido)
        const fabAtualizar = $('#m_cx_fabAtualizar');
        if (fabAtualizar) {
            fabAtualizar.addEventListener('click', () => { atualizarSaldo(); });
        }

        // Tela DETALHE: FAB verde "+" (lançar coleta) + FAB azul Atualizar
        const fabColetaCliente = $('#m_cx_fabColetaCliente');
        if (fabColetaCliente) {
            fabColetaCliente.addEventListener('click', () => {
                const c = ESTADO.clienteAtivo
                    ? ESTADO.clientes.find(x => x.codparc === ESTADO.clienteAtivo)
                    : null;
                abrirSheetColeta(ESTADO.clienteAtivo, c ? c.nomeparc : null);
            });
        }
        const fabAtualizarDetalhe = $('#m_cx_fabAtualizarDetalhe');
        if (fabAtualizarDetalhe) {
            fabAtualizarDetalhe.addEventListener('click', () => { atualizarDetalheAtual(); });
        }
    }

    // -------------------- Boot --------------------
    function boot() {
        // Esconde header global desktop em mobile
        document.body.classList.add('m-caixas-active');

        setupSwipeToBack();
        setupSidebar();
        setupBottomNav();
        setupBackButtons();
        setupCloseSheets();
        setupBusca();
        setupFabs();
        setupSheetColeta();
        setupSheetMais();

        carregarSaldo();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
