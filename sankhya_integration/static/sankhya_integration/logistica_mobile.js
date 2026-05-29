/* =============================================================================
   Logística Mobile — Rotas de entrega (Mai/2026 — simulação UI v2)
   ---------------------------------------------------------------------------
   Usa window.LogisticaMock exposto pelo desktop. Mesmo modelo de dados.
   ============================================================================= */

(function () {
    'use strict';

    if (!document.body || document.body.getAttribute('data-active-module') !== 'logistica') return;
    if (!window.matchMedia('(max-width: 900px)').matches) return;

    const HOJE = new Date().toISOString().slice(0, 10);

    // -------------------------------------------------------------------------
    // ESTADO
    // -------------------------------------------------------------------------
    const ESTADO = {
        screen: 'lista',
        rotaSelecionadaId: null,
        rotaEditandoId: null,
        ajudantesEdit: [],
        destinosEdit: [],
        filtroDataIni: HOJE,
        filtroDataFim: HOJE,
        filtroBusca: '',
        filtroCodparcMotorista: 0,
        filtroCodveiculo: 0,
        _rotasCache: null,   // cache local após refetch; null = ainda usa LM().getRotas()
    };

    // -------------------------------------------------------------------------
    // HELPERS — proxies pra LogisticaMock
    // -------------------------------------------------------------------------
    function $(id) { return document.getElementById(id); }
    function LM() { return window.LogisticaMock; }
    function rotas() {
        if (ESTADO._rotasCache !== null) return ESTADO._rotasCache;
        return LM() ? LM().getRotas() : [];
    }

    function filtrosEstadoMobile() {
        return {
            data_de: ESTADO.filtroDataIni || '',
            data_ate: ESTADO.filtroDataFim || ESTADO.filtroDataIni || '',
            codparc_motorista: ESTADO.filtroCodparcMotorista || 0,
            codveiculo: ESTADO.filtroCodveiculo || 0,
            q: (ESTADO.filtroBusca || '').trim(),
        };
    }

    let _refetchTimerMobile = null;
    let _refetchTokenMobile = 0;
    async function refetchViagensMobile() {
        const Api = window.LogisticaApi;
        if (!Api || !Api.carregarViagens) {
            renderTudo();
            return;
        }
        const meuToken = ++_refetchTokenMobile;
        try {
            const rotasNovas = await Api.carregarViagens(filtrosEstadoMobile());
            if (meuToken !== _refetchTokenMobile) return;
            ESTADO._rotasCache = rotasNovas || [];
            renderTudo();
        } catch (e) {
            if (meuToken !== _refetchTokenMobile) return;
            console.error('Falha ao filtrar viagens (mobile):', e);
            mostrarToast('Erro ao filtrar: ' + e.message, 'error');
        }
    }
    function aplicarFiltrosBackendMobile(opts) {
        const debounceMs = (opts && typeof opts.debounceMs === 'number') ? opts.debounceMs : 250;
        if (_refetchTimerMobile) clearTimeout(_refetchTimerMobile);
        _refetchTimerMobile = setTimeout(function () { refetchViagensMobile(); }, debounceMs);
    }
    function parcs() { return LM() ? LM().getParceiros() : []; }
    function veics() { return LM() ? LM().getVeiculos() : []; }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function normalizar(s) {
        return (s || '').toString().toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '');
    }

    function mostrarToast(msg, tipo) {
        if (window.IAgro && IAgro.showToast) IAgro.showToast(msg, tipo || 'info');
    }

    // -------------------------------------------------------------------------
    // NAVEGAÇÃO STACK
    // -------------------------------------------------------------------------
    const screens = {
        lista: '.m-screen[data-screen="lista"]',
        detalhe: '.m-screen[data-screen="detalhe"]',
    };

    function setActiveScreen(name) {
        document.querySelectorAll('.logistica-mobile .m-screen').forEach(function (el) {
            el.classList.remove('is-active');
        });
        const sel = screens[name];
        if (!sel) return;
        const el = document.querySelector(sel);
        if (el) el.classList.add('is-active');
        ESTADO.screen = name;
    }

    function pushScreen(name) {
        try { history.pushState({ screen: name }, '', ''); } catch (e) {}
        setActiveScreen(name);
    }

    function popScreen() { setActiveScreen('lista'); }

    window.addEventListener('popstate', function () { setActiveScreen('lista'); });

    // Swipe-to-back: arrastar pra direita em telas internas volta pra lista (padrão IAgro Mobile)
    function setupSwipeToBack() {
        const TRIGGER_PCT = 0.35;
        const TRIGGER_VEL = 0.5;
        Object.keys(screens).forEach(function (name) {
            if (name === 'lista') return;
            const el = document.querySelector('.logistica-mobile ' + screens[name]);
            if (!el) return;
            let startX = 0, startY = 0, startT = 0;
            let dx = 0, dy = 0, axis = '';

            el.addEventListener('touchstart', function (e) {
                if (e.touches.length !== 1) return;
                const t = e.touches[0];
                startX = t.clientX; startY = t.clientY; startT = Date.now();
                dx = 0; dy = 0; axis = '';
            }, { passive: true });

            el.addEventListener('touchmove', function (e) {
                if (e.touches.length !== 1) return;
                const t = e.touches[0];
                dx = t.clientX - startX;
                dy = t.clientY - startY;
                if (!axis && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
                    axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                }
                if (axis === 'x' && dx > 0) {
                    el.style.transform = 'translateX(' + (dx * 0.5) + 'px)';
                }
            }, { passive: true });

            el.addEventListener('touchend', function () {
                el.style.transform = '';
                if (axis !== 'x' || dx <= 0) return;
                const w = window.innerWidth || 360;
                const vel = dx / Math.max(1, Date.now() - startT);
                if (dx / w >= TRIGGER_PCT || vel >= TRIGGER_VEL) {
                    popScreen();
                }
            });
        });
    }

    // -------------------------------------------------------------------------
    // SHEETS
    // -------------------------------------------------------------------------
    function openSheet(name) {
        const sheet = document.querySelector('.logistica-mobile .m-sheet[data-sheet="' + name + '"]');
        if (sheet) sheet.setAttribute('aria-hidden', 'false');
    }

    function closeSheet(name) {
        if (name) {
            const sheet = document.querySelector('.logistica-mobile .m-sheet[data-sheet="' + name + '"]');
            if (sheet) sheet.setAttribute('aria-hidden', 'true');
        } else {
            document.querySelectorAll('.logistica-mobile .m-sheet').forEach(function (s) {
                s.setAttribute('aria-hidden', 'true');
            });
        }
    }

    function setupSheets() {
        document.querySelectorAll('.logistica-mobile [data-close-sheet]').forEach(function (el) {
            el.addEventListener('click', function () {
                const sheet = el.closest('.m-sheet');
                if (sheet) sheet.setAttribute('aria-hidden', 'true');
            });
        });
    }

    // -------------------------------------------------------------------------
    // FILTRAGEM
    // -------------------------------------------------------------------------
    // Backend já entrega a lista filtrada quando _rotasCache foi populado.
    // Quando ainda não houve refetch (cache null), cai no fallback de LM().getRotas().
    function rotasFiltradas() {
        return rotas().slice().sort(function (a, b) {
            if (a.data !== b.data) return a.data < b.data ? 1 : -1;
            return (a.hora_saida || '').localeCompare(b.hora_saida || '');
        });
    }

    function temFiltroAtivo() {
        return (
            ESTADO.filtroDataIni !== HOJE ||
            ESTADO.filtroDataFim !== HOJE ||
            !!ESTADO.filtroBusca ||
            ESTADO.filtroCodparcMotorista !== 0 ||
            ESTADO.filtroCodveiculo !== 0
        );
    }

    function atualizarBadgeFiltros() {
        const item = document.querySelector('.logistica-mobile .m-bottom-nav__item[data-nav="filtros"]');
        if (!item) return;
        if (temFiltroAtivo()) item.classList.add('has-filtros-ativos');
        else item.classList.remove('has-filtros-ativos');
    }

    // -------------------------------------------------------------------------
    // RENDER
    // -------------------------------------------------------------------------
    function atualizarResumo() {
        const lista = rotasFiltradas();
        const total = lista.length;
        const caixas = lista.reduce(function (s, r) { return s + LM().totalCaixas(r); }, 0);
        const destinos = lista.reduce(function (s, r) { return s + (r.destinos || []).length; }, 0);
        const motoristas = new Set();
        lista.forEach(function (r) { if (r.codparc_motorista) motoristas.add(r.codparc_motorista); });

        $('m_lgResumoTotal').textContent = total;
        $('m_lgResumoCaixas').textContent = caixas.toLocaleString('pt-BR');
        $('m_lgResumoDestinos').textContent = destinos;
        $('m_lgResumoMotoristas').textContent = motoristas.size;
    }

    function renderLista() {
        const container = $('m_lg_rotasList');
        const lista = rotasFiltradas();

        if (!lista.length) {
            container.innerHTML = `
                <div class="m-empty-state">
                    <i class="ph ph-truck" aria-hidden="true"></i>
                    <span>Nenhuma viagem encontrada com os filtros atuais.</span>
                </div>
            `;
            return;
        }

        container.innerHTML = lista.map(function (r) {
            const pm = LM().placaModelo(r);
            const motorista = LM().nomeMotorista(r);
            const total = LM().totalCaixas(r);
            const destinosNomes = (r.destinos || []).map(function (d) { return LM().nomeDestino(d.codparc); }).join(' · ');

            return `
                <div class="m-lg-card" data-id="${r.id}">
                    <div class="m-lg-card-numviagem">
                        <span class="m-lg-card-num">${r.num_viagem}</span>
                        <span class="m-lg-card-num-label">Viagem</span>
                    </div>
                    <div class="m-lg-card-body">
                        <div class="m-lg-card-placa">${escapeHtml(pm.placa)}</div>
                        <div class="m-lg-card-motorista">
                            <i class="ph ph-steering-wheel"></i>
                            <span>${escapeHtml(motorista)}</span>
                        </div>
                        <div class="m-lg-card-hora">
                            <i class="ph ph-clock"></i>
                            <span>${escapeHtml(r.hora_saida)} · ${LM().fmtDataBR(r.data)}</span>
                        </div>
                        <div class="m-lg-card-destinos-mini">${escapeHtml(destinosNomes)}</div>
                    </div>
                    <div class="m-lg-card-direita">
                        <div class="m-lg-card-qtd">${total}<small>caixas</small></div>
                    </div>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.m-lg-card').forEach(function (card) {
            card.addEventListener('click', function () {
                const id = parseInt(card.dataset.id, 10);
                abrirDetalhe(id);
            });
        });
    }

    function renderTudo() {
        atualizarResumo();
        renderLista();
        atualizarBadgeFiltros();
    }

    // -------------------------------------------------------------------------
    // TELA 2 — DETALHE
    // -------------------------------------------------------------------------
    function abrirDetalhe(id) {
        const r = rotas().find(function (x) { return x.id === id; });
        if (!r) return;
        ESTADO.rotaSelecionadaId = id;

        const pm = LM().placaModelo(r);

        $('m_lg_detNumViagem').textContent = r.num_viagem;
        $('m_lg_detDataExtenso').textContent = LM().fmtDataExtenso(r.data);

        $('m_lg_detPlaca').textContent = pm.placa;
        $('m_lg_detModelo').textContent = pm.modelo;
        $('m_lg_detHora').textContent = r.hora_saida;

        $('m_lg_detMotorista').textContent = LM().nomeMotorista(r);
        $('m_lg_detAjudantes').textContent = LM().nomeAjudantes(r) || '—';

        // Destinos
        const total = LM().totalCaixas(r);
        $('m_lg_detTotalCaixas').textContent = total + ' cx';
        const olEl = $('m_lg_detDestinos');
        olEl.innerHTML = (r.destinos || []).map(function (d, idx) {
            const nome = LM().nomeDestino(d.codparc);
            const obsHtml = d.obs ? `<div class="m-lg-destino-obs">${escapeHtml(d.obs)}</div>` : '';
            return `
                <li>
                    <div class="m-lg-destino-num">${idx + 1}</div>
                    <div>
                        <div class="m-lg-destino-nome">${escapeHtml(nome)}</div>
                        ${obsHtml}
                    </div>
                    <div class="m-lg-destino-qtd">${d.qtd_caixas} cx</div>
                </li>
            `;
        }).join('');

        $('m_lg_detObs').textContent = r.observacao || '(sem observação)';

        pushScreen('detalhe');
    }

    // -------------------------------------------------------------------------
    // SHEET ROTA — NOVA/EDITAR
    // -------------------------------------------------------------------------
    function abrirSheetNova() {
        ESTADO.rotaEditandoId = null;
        ESTADO.ajudantesEdit = [];
        ESTADO.destinosEdit = [];

        $('m_lg_sheetTitulo').textContent = 'Nova viagem';
        $('m_lg_fSalvarLabel').textContent = 'Confirmar';

        $('m_lg_fVeiculo').value = '';
        $('m_lg_fCodVeiculo').value = '';
        $('m_lg_fData').value = HOJE;
        $('m_lg_fHora').value = '06:00';
        $('m_lg_fMotorista').value = '';
        $('m_lg_fCodMotorista').value = '';
        $('m_lg_fAjudanteInput').value = '';
        $('m_lg_fObs').value = '';
        renderChipsAjudantesMobile();
        renderDestinosEditMobile();
        limparMsgMobile();

        openSheet('rota');
    }

    function abrirSheetEditar(id) {
        const r = rotas().find(function (x) { return x.id === id; });
        if (!r) return;

        ESTADO.rotaEditandoId = id;
        ESTADO.ajudantesEdit = (r.ajudantes || []).slice();
        ESTADO.destinosEdit = (r.destinos || []).map(function (d) {
            return { ordem: d.ordem, codparc: d.codparc, qtd_caixas: d.qtd_caixas, obs: d.obs || '' };
        });

        $('m_lg_sheetTitulo').textContent = 'Editar viagem #' + r.num_viagem;
        $('m_lg_fSalvarLabel').textContent = 'Salvar';

        const pm = LM().placaModelo(r);
        $('m_lg_fVeiculo').value = pm.placa + ' — ' + pm.modelo;
        $('m_lg_fCodVeiculo').value = r.codveiculo || '';
        $('m_lg_fData').value = r.data;
        $('m_lg_fHora').value = r.hora_saida;
        $('m_lg_fMotorista').value = LM().nomeMotorista(r);
        $('m_lg_fCodMotorista').value = r.codparc_motorista || '';
        $('m_lg_fAjudanteInput').value = '';
        $('m_lg_fObs').value = r.observacao || '';
        renderChipsAjudantesMobile();
        renderDestinosEditMobile();
        limparMsgMobile();

        openSheet('rota');
    }

    function renderChipsAjudantesMobile() {
        const container = $('m_lg_fAjudantesChips');
        if (!container) return;
        if (!ESTADO.ajudantesEdit.length) {
            container.innerHTML = '';
            return;
        }
        container.innerHTML = ESTADO.ajudantesEdit.map(function (codparc, idx) {
            const p = LM().buscarParceiro(codparc);
            const nome = p ? p.nome : ('parc ' + codparc);
            return `
                <span class="lg-chip-pessoa">
                    ${escapeHtml(nome)}
                    <button type="button" class="lg-chip-remove" data-idx="${idx}" aria-label="Remover">×</button>
                </span>
            `;
        }).join('');
        container.querySelectorAll('.lg-chip-remove').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const idx = parseInt(btn.dataset.idx, 10);
                ESTADO.ajudantesEdit.splice(idx, 1);
                renderChipsAjudantesMobile();
            });
        });
    }

    function renderDestinosEditMobile() {
        const container = $('m_lg_fDestinosLista');
        if (!container) return;

        if (!ESTADO.destinosEdit.length) {
            container.innerHTML = '<div class="m-lg-destinos-edit-empty">Toque em "Adicionar destino" pra começar.</div>';
            return;
        }

        container.innerHTML = ESTADO.destinosEdit.map(function (d, idx) {
            const nome = d.codparc ? LM().nomeDestino(d.codparc) : '';
            return `
                <div class="m-lg-destino-edit-row" data-idx="${idx}">
                    <div class="m-lg-destino-edit-ordem">${idx + 1}</div>
                    <div style="position:relative">
                        <input type="text" class="m-lg-destino-cliente-input" placeholder="Cliente…"
                               value="${escapeHtml(nome)}" data-idx="${idx}" autocomplete="off">
                        <div class="dropdown-abs m-lg-destino-cliente-dd" data-idx="${idx}"></div>
                    </div>
                    <input type="number" class="m-lg-destino-edit-qtd" min="0" step="1" placeholder="0"
                           value="${d.qtd_caixas || 0}" data-idx="${idx}">
                    <button type="button" class="m-lg-destino-edit-remover" data-idx="${idx}" aria-label="Remover">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.m-lg-destino-cliente-input').forEach(function (inp) {
            const idx = parseInt(inp.dataset.idx, 10);
            const dd = container.querySelector('.m-lg-destino-cliente-dd[data-idx="' + idx + '"]');
            setupTypeaheadClienteMobile(inp, dd, idx);
        });

        container.querySelectorAll('.m-lg-destino-edit-qtd').forEach(function (inp) {
            inp.addEventListener('input', function () {
                const idx = parseInt(inp.dataset.idx, 10);
                ESTADO.destinosEdit[idx].qtd_caixas = parseInt(inp.value, 10) || 0;
            });
        });

        container.querySelectorAll('.m-lg-destino-edit-remover').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const idx = parseInt(btn.dataset.idx, 10);
                ESTADO.destinosEdit.splice(idx, 1);
                renderDestinosEditMobile();
            });
        });
    }

    function setupTypeaheadClienteMobile(input, dropdown, idx) {
        function buscar() {
            const termo = normalizar(input.value);
            const clientes = LM().parceirosPorTipo('CLIENTE');
            const results = clientes.filter(function (p) {
                return normalizar(p.nome).indexOf(termo) >= 0;
            }).slice(0, 6);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum cliente</div>';
            } else {
                dropdown.innerHTML = results.map(function (p) {
                    return `<div class="dd-item" data-cod="${p.codparc}" data-nome="${escapeHtml(p.nome)}">
                        ${escapeHtml(p.nome)}
                    </div>`;
                }).join('');
            }

            // Position fixed pra mobile dentro de sheet
            const r = input.getBoundingClientRect();
            dropdown.style.position = 'fixed';
            dropdown.style.top = (r.bottom + 4) + 'px';
            dropdown.style.left = r.left + 'px';
            dropdown.style.width = r.width + 'px';
            dropdown.style.zIndex = '50';
            dropdown.style.display = 'block';
            dropdown.style.background = '#fff';
            dropdown.style.border = '1px solid #e5e7eb';
            dropdown.style.borderRadius = '6px';
            dropdown.style.maxHeight = '200px';
            dropdown.style.overflowY = 'auto';
            dropdown.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)';

            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    const cp = parseInt(item.dataset.cod, 10);
                    ESTADO.destinosEdit[idx].codparc = cp;
                    input.value = item.dataset.nome;
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function adicionarDestinoMobile() {
        ESTADO.destinosEdit.push({
            ordem: ESTADO.destinosEdit.length + 1,
            codparc: 0,
            qtd_caixas: 0,
            obs: '',
        });
        renderDestinosEditMobile();
    }

    function setMsgMobile(texto, tipo) {
        const el = $('m_lg_fMsg');
        el.textContent = texto;
        el.hidden = false;
        el.classList.remove('m-lg-msg--success');
        if (tipo === 'success') el.classList.add('m-lg-msg--success');
    }

    function limparMsgMobile() {
        const el = $('m_lg_fMsg');
        el.textContent = '';
        el.hidden = true;
    }

    function coletarPayloadMobile() {
        const codveiculo = parseInt($('m_lg_fCodVeiculo').value, 10) || 0;
        const data = $('m_lg_fData').value;
        const hora = $('m_lg_fHora').value;
        const codparc_motorista = parseInt($('m_lg_fCodMotorista').value, 10) || 0;
        const observacao = $('m_lg_fObs').value.trim();

        if (!codveiculo) return { erro: 'Escolha um caminhão.' };
        if (!data) return { erro: 'Informe a data.' };
        if (!hora) return { erro: 'Informe a hora de saída.' };
        if (!codparc_motorista) return { erro: 'Escolha um motorista.' };
        if (!ESTADO.destinosEdit.length) return { erro: 'Adicione pelo menos um destino.' };

        const destinos = [];
        for (let i = 0; i < ESTADO.destinosEdit.length; i++) {
            const d = ESTADO.destinosEdit[i];
            if (!d.codparc) return { erro: 'Destino #' + (i + 1) + ' sem cliente selecionado.' };
            if (!d.qtd_caixas || d.qtd_caixas <= 0) return { erro: 'Destino #' + (i + 1) + ' precisa de qtd > 0.' };
            destinos.push({ ordem: i + 1, codparc: d.codparc, qtd_caixas: d.qtd_caixas, obs: d.obs || '' });
        }

        return {
            ok: true,
            codveiculo: codveiculo,
            data: data,
            hora_saida: hora,
            codparc_motorista: codparc_motorista,
            ajudantes: ESTADO.ajudantesEdit.slice(),
            destinos: destinos,
            observacao: observacao,
        };
    }

    async function salvarRotaMobile() {
        const payload = coletarPayloadMobile();
        if (payload.erro) { setMsgMobile(payload.erro, 'error'); return; }
        delete payload.ok;

        const editId = ESTADO.rotaEditandoId;
        const Api = window.LogisticaApi;
        if (!Api) {
            setMsgMobile('Erro: LogisticaApi indisponível. Refresh a página.', 'error');
            return;
        }

        try {
            setMsgMobile('Salvando…', 'info');
            const resp = editId
                ? await Api.editarViagem(editId, payload)
                : await Api.criarViagem(payload);

            if (!resp.ok) {
                setMsgMobile(resp.error || 'Falha ao salvar.', 'error');
                return;
            }

            mostrarToast('Viagem ' + (editId ? 'atualizada' : 'criada') + '.', 'success');
            await refetchViagensMobile();

            closeSheet('rota');
            if (LM().rerenderDesktop) LM().rerenderDesktop();
            renderTudo();

            // Após criar, navega pro detalhe da nova rota (operador vê o resultado)
            const novoId = editId || resp.viagem_id;
            if (novoId && ESTADO.screen === 'detalhe') {
                abrirDetalhe(novoId);
            }
        } catch (e) {
            setMsgMobile('Falha: ' + e.message, 'error');
        }
    }

    // -------------------------------------------------------------------------
    // FICHA — abre via print() do navegador (overlay desktop)
    // -------------------------------------------------------------------------
    function abrirFichaMobile(id) {
        // No mobile, dispara o overlay desktop oculto (que tem CSS de print)
        // Se não houver, mostra um modal simples inline
        const r = rotas().find(function (x) { return x.id === id; });
        if (!r) return;

        // Reutiliza o paper do desktop
        const paper = $('lgFichaPaper');
        if (paper) {
            renderFichaPaper(paper, r);
        }
        const overlay = $('lgFichaModal');
        if (overlay) {
            overlay.classList.remove('hidden');
            overlay.setAttribute('aria-hidden', 'false');

            // Click em backdrop fecha
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    overlay.classList.add('hidden');
                    overlay.setAttribute('aria-hidden', 'true');
                }
            }, { once: true });

            // Botão imprimir — usa PDF reportlab quando disponível, fallback window.print()
            const btnImp = $('lgFichaImprimirBtn');
            if (btnImp) {
                btnImp.onclick = function () {
                    const Api = window.LogisticaApi;
                    if (Api && Api.fichaPdfUrl && id) {
                        window.open(Api.fichaPdfUrl(id), '_blank');
                    } else {
                        window.print();
                    }
                };
            }

            // Fechar (X)
            overlay.querySelectorAll('[data-modal-close]').forEach(function (el) {
                el.onclick = function () {
                    overlay.classList.add('hidden');
                    overlay.setAttribute('aria-hidden', 'true');
                };
            });
        }
    }

    function renderFichaPaper(container, r) {
        const pm = LM().placaModelo(r);
        const motorista = LM().nomeMotorista(r);
        const ajudantes = LM().nomeAjudantes(r) || '—';
        const total = LM().totalCaixas(r);

        const destinosHTML = (r.destinos || []).map(function (d) {
            const obsHtml = d.obs ? `<small class="lg-ficha-destino-obs">${escapeHtml(d.obs)}</small>` : '';
            return `
                <li>
                    <span class="lg-ficha-destino-arrow">&gt;</span>
                    <span>
                        <span class="lg-ficha-destino-nome">${escapeHtml(LM().nomeDestino(d.codparc))}</span>
                        ${obsHtml}
                    </span>
                    <span class="lg-ficha-destino-qtd">${d.qtd_caixas} cx</span>
                </li>
            `;
        }).join('');

        container.innerHTML = `
            <header class="lg-ficha-cabecalho">
                <div class="lg-ficha-titulo">ROTA</div>
                <div class="lg-ficha-numviagem">VIAGEM Nº ${r.num_viagem}</div>
            </header>
            <div class="lg-ficha-data-bloco">
                <span class="lg-ficha-data-extenso">${LM().fmtDataExtenso(r.data)}</span>
                <span class="lg-ficha-saida">
                    Saída às <span class="lg-ficha-saida-hora">${escapeHtml(r.hora_saida)}</span>
                </span>
            </div>
            <div class="lg-ficha-pessoas">
                <div class="lg-ficha-linha">
                    <span class="lg-ficha-linha-label">Motorista</span>
                    <span class="lg-ficha-motorista">${escapeHtml(motorista)}</span>
                </div>
                <div class="lg-ficha-linha">
                    <span class="lg-ficha-linha-label">Ajudante(s)</span>
                    <span class="lg-ficha-ajudantes">${escapeHtml(ajudantes)}</span>
                </div>
            </div>
            <div class="lg-ficha-placa">
                <div class="lg-ficha-placa-valor">${escapeHtml(pm.placa)}</div>
                <div class="lg-ficha-placa-modelo">${escapeHtml(pm.modelo)}</div>
            </div>
            <div class="lg-ficha-destinos">
                <div class="lg-ficha-destinos-titulo">Destinos:</div>
                <ol class="lg-ficha-destinos-lista">${destinosHTML}</ol>
            </div>
            <div class="lg-ficha-total">
                <span>Total de caixas:</span>
                <span class="lg-ficha-total-valor">${total}</span>
            </div>
            <div class="lg-ficha-obs">
                <div class="lg-ficha-obs-titulo">Observação:</div>
                <div class="lg-ficha-obs-texto">${escapeHtml(r.observacao || '')}</div>
            </div>
            <div class="lg-ficha-rodape">IAgro · Logística</div>
        `;
    }

    // -------------------------------------------------------------------------
    // TYPEAHEADS DO SHEET
    // -------------------------------------------------------------------------
    function setupTypeaheadVeiculoMobile() {
        const input = $('m_lg_fVeiculo');
        const hidden = $('m_lg_fCodVeiculo');
        const dropdown = $('m_lg_fVeiculoDropdown');
        if (!input || !dropdown) return;

        function buscar() {
            const termo = normalizar(input.value);
            const results = veics().filter(function (v) {
                return normalizar(v.placa + ' ' + v.modelo).indexOf(termo) >= 0;
            }).slice(0, 6);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum veículo</div>';
            } else {
                dropdown.innerHTML = results.map(function (v) {
                    return `<div class="dd-item" data-cod="${v.codveiculo}" data-placa="${v.placa}" data-modelo="${v.modelo}">
                        <strong>${v.placa}</strong> — ${v.modelo}
                    </div>`;
                }).join('');
            }
            mostrarDropdownFloat(input, dropdown);

            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    input.value = item.dataset.placa + ' — ' + item.dataset.modelo;
                    hidden.value = item.dataset.cod;
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function setupTypeaheadMotoristaMobile() {
        const input = $('m_lg_fMotorista');
        const hidden = $('m_lg_fCodMotorista');
        const dropdown = $('m_lg_fMotoristaDropdown');
        if (!input || !dropdown) return;

        function buscar() {
            const termo = normalizar(input.value);
            const results = LM().parceirosPorTipo('MOTORISTA').filter(function (p) {
                return normalizar(p.nome).indexOf(termo) >= 0;
            }).slice(0, 6);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum motorista</div>';
            } else {
                dropdown.innerHTML = results.map(function (p) {
                    return `<div class="dd-item" data-cod="${p.codparc}" data-nome="${escapeHtml(p.nome)}">
                        <strong>${escapeHtml(p.nome)}</strong>
                    </div>`;
                }).join('');
            }
            mostrarDropdownFloat(input, dropdown);

            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    input.value = item.dataset.nome;
                    hidden.value = item.dataset.cod;
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function setupTypeaheadAjudanteMobile() {
        const input = $('m_lg_fAjudanteInput');
        const dropdown = $('m_lg_fAjudanteDropdown');
        if (!input || !dropdown) return;

        function buscar() {
            const termo = normalizar(input.value);
            const disponiveis = LM().parceirosPorTipo('AJUDANTE').filter(function (p) {
                return ESTADO.ajudantesEdit.indexOf(p.codparc) < 0;
            });
            const results = disponiveis.filter(function (p) {
                return normalizar(p.nome).indexOf(termo) >= 0;
            }).slice(0, 6);

            if (!results.length) {
                dropdown.innerHTML = '<div class="dd-item dd-empty">Nenhum ajudante disponível</div>';
            } else {
                dropdown.innerHTML = results.map(function (p) {
                    return `<div class="dd-item" data-cod="${p.codparc}" data-nome="${escapeHtml(p.nome)}">
                        ${escapeHtml(p.nome)}
                    </div>`;
                }).join('');
            }
            mostrarDropdownFloat(input, dropdown);

            dropdown.querySelectorAll('.dd-item[data-cod]').forEach(function (item) {
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    const cp = parseInt(item.dataset.cod, 10);
                    if (ESTADO.ajudantesEdit.indexOf(cp) < 0) {
                        ESTADO.ajudantesEdit.push(cp);
                        renderChipsAjudantesMobile();
                    }
                    input.value = '';
                    dropdown.style.display = 'none';
                });
            });
        }
        input.addEventListener('input', buscar);
        input.addEventListener('focus', buscar);
        input.addEventListener('blur', function () {
            setTimeout(function () { dropdown.style.display = 'none'; }, 200);
        });
    }

    function mostrarDropdownFloat(input, dropdown) {
        const r = input.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top = (r.bottom + 4) + 'px';
        dropdown.style.left = r.left + 'px';
        dropdown.style.width = r.width + 'px';
        dropdown.style.zIndex = '50';
        dropdown.style.display = 'block';
        dropdown.style.background = '#fff';
        dropdown.style.border = '1px solid #e5e7eb';
        dropdown.style.borderRadius = '6px';
        dropdown.style.maxHeight = '200px';
        dropdown.style.overflowY = 'auto';
        dropdown.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)';
    }

    // -------------------------------------------------------------------------
    // SHEET FILTROS
    // -------------------------------------------------------------------------
    function setupSheetFiltros() {
        const dataIni = $('m_lg_filtDataIni');
        const dataFim = $('m_lg_filtDataFim');
        const motoSel = $('m_lg_filtMotorista');
        const veicSel = $('m_lg_filtVeiculo');

        // Preenche selects
        const motoOpts = LM().parceirosPorTipo('MOTORISTA').slice()
            .sort(function (a, b) { return a.nome.localeCompare(b.nome); });
        motoSel.innerHTML = '<option value="">Todos</option>' + motoOpts.map(function (p) {
            return `<option value="${p.codparc}">${escapeHtml(p.nome)}</option>`;
        }).join('');
        veicSel.innerHTML = '<option value="">Todos</option>' + veics().map(function (v) {
            return `<option value="${v.codveiculo}">${escapeHtml(v.placa)} — ${escapeHtml(v.modelo)}</option>`;
        }).join('');

        function aplicarValoresFromEstado() {
            dataIni.value = ESTADO.filtroDataIni;
            dataFim.value = ESTADO.filtroDataFim;
            motoSel.value = ESTADO.filtroCodparcMotorista || '';
            veicSel.value = ESTADO.filtroCodveiculo || '';
        }

        function aplicarToEstado(opts) {
            ESTADO.filtroDataIni = dataIni.value;
            ESTADO.filtroDataFim = dataFim.value;
            ESTADO.filtroCodparcMotorista = parseInt(motoSel.value, 10) || 0;
            ESTADO.filtroCodveiculo = parseInt(veicSel.value, 10) || 0;
            aplicarFiltrosBackendMobile(opts);
        }

        const replicar = function () {
            const v = dataIni.value;
            if (v) dataFim.value = v;
        };
        dataIni.addEventListener('change', replicar);
        dataIni.addEventListener('input', replicar);

        const shift = function (delta) {
            let d = dataIni.value ? new Date(dataIni.value + 'T12:00:00') : new Date();
            if (isNaN(d.getTime())) d = new Date();
            d.setDate(d.getDate() + delta);
            const iso = d.toISOString().slice(0, 10);
            dataIni.value = iso;
            dataFim.value = iso;
            ESTADO.filtroDataIni = iso;
            ESTADO.filtroDataFim = iso;
            aplicarFiltrosBackendMobile({ debounceMs: 0 });
        };
        $('m_lg_filtPrevDay').addEventListener('click', function () { shift(-1); });
        $('m_lg_filtNextDay').addEventListener('click', function () { shift(1); });

        const sheet = document.querySelector('.logistica-mobile .m-sheet[data-sheet="filtros"]');
        if (sheet) {
            sheet.querySelector('.m-btn-primary').addEventListener('click', function () {
                aplicarToEstado({ debounceMs: 0 });
            });
        }

        $('m_lg_filtLimpar').addEventListener('click', function () {
            dataIni.value = HOJE;
            dataFim.value = HOJE;
            motoSel.value = '';
            veicSel.value = '';
            ESTADO.filtroDataIni = HOJE;
            ESTADO.filtroDataFim = HOJE;
            ESTADO.filtroBusca = '';
            ESTADO.filtroCodparcMotorista = 0;
            ESTADO.filtroCodveiculo = 0;
            const buscaInp = $('m_lg_busca');
            if (buscaInp) buscaInp.value = '';
            aplicarFiltrosBackendMobile({ debounceMs: 0 });
        });

        document.querySelectorAll('.logistica-mobile .m-bottom-nav__item[data-nav="filtros"]').forEach(function (b) {
            b.addEventListener('click', aplicarValoresFromEstado);
        });

        aplicarValoresFromEstado();
    }

    // -------------------------------------------------------------------------
    // BUSCA
    // -------------------------------------------------------------------------
    function setupBuscaMobile() {
        const input = $('m_lg_busca');
        if (!input) return;
        input.addEventListener('input', function () {
            ESTADO.filtroBusca = input.value;
            aplicarFiltrosBackendMobile({ debounceMs: 350 });
        });
    }

    // -------------------------------------------------------------------------
    // BOTTOM NAV
    // -------------------------------------------------------------------------
    function setupBottomNav() {
        document.querySelectorAll('.logistica-mobile .m-bottom-nav__item').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const nav = btn.dataset.nav;
                if (nav === 'rotas') {
                    if (ESTADO.screen !== 'lista') setActiveScreen('lista');
                } else if (nav === 'buscar') {
                    if (ESTADO.screen !== 'lista') setActiveScreen('lista');
                    const inp = $('m_lg_busca');
                    if (inp) inp.focus();
                } else if (nav === 'filtros') {
                    openSheet('filtros');
                } else if (nav === 'mais') {
                    openSheet('mais');
                }
            });
        });
    }

    // -------------------------------------------------------------------------
    // SHEET MAIS
    // -------------------------------------------------------------------------
    function setupSheetMais() {
        $('m_lg_maisAtualizar').addEventListener('click', function () {
            closeSheet('mais');
            renderTudo();
            mostrarToast('Lista atualizada.', 'info');
        });
        $('m_lg_maisNova').addEventListener('click', function () {
            closeSheet('mais');
            abrirSheetNova();
        });
    }

    // -------------------------------------------------------------------------
    // AÇÕES — botões fixos
    // -------------------------------------------------------------------------
    function setupAcoes() {
        document.querySelectorAll('.logistica-mobile .m-back-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                history.back();
                setTimeout(function () { popScreen(); }, 50);
            });
        });

        $('m_lg_footEditar').addEventListener('click', function () {
            if (ESTADO.rotaSelecionadaId) abrirSheetEditar(ESTADO.rotaSelecionadaId);
        });

        $('m_lg_footImprimir').addEventListener('click', function () {
            if (ESTADO.rotaSelecionadaId) abrirFichaMobile(ESTADO.rotaSelecionadaId);
        });

        $('m_lg_footExcluir').addEventListener('click', function () {
            if (!ESTADO.rotaSelecionadaId) return;
            const r = rotas().find(function (x) { return x.id === ESTADO.rotaSelecionadaId; });
            if (!r) return;

            const confirmar = window.IAgro && IAgro.confirmarAcao
                ? IAgro.confirmarAcao({
                    titulo: 'Excluir viagem',
                    mensagem: 'Confirmar exclusão da viagem #' + r.num_viagem + '?',
                    tipo: 'perigo',
                })
                : Promise.resolve(window.confirm('Excluir esta viagem?'));

            Promise.resolve(confirmar).then(async function (ok) {
                if (!ok) return;
                const Api = window.LogisticaApi;
                if (!Api) {
                    mostrarToast('Erro: LogisticaApi indisponível.', 'error');
                    return;
                }
                try {
                    const resp = await Api.excluirViagem(ESTADO.rotaSelecionadaId, '');
                    if (!resp.ok) {
                        mostrarToast('Erro ao excluir: ' + (resp.error || 'desconhecido'), 'error');
                        return;
                    }
                    await refetchViagensMobile();
                    if (LM().rerenderDesktop) LM().rerenderDesktop();
                    ESTADO.rotaSelecionadaId = null;
                    popScreen();
                    renderTudo();
                    mostrarToast('Viagem excluída.', 'success');
                } catch (e) {
                    mostrarToast('Falha: ' + e.message, 'error');
                }
            });
        });

        $('m_lg_fabNova').addEventListener('click', abrirSheetNova);

        $('m_lg_fabAtualizar').addEventListener('click', async function () {
            const fab = $('m_lg_fabAtualizar');
            fab.classList.add('is-loading');
            try {
                const Api = window.LogisticaApi;
                if (Api && Api.recarregarTudo) {
                    await Api.recarregarTudo();
                    await refetchViagensMobile();
                    mostrarToast('Lista atualizada.', 'info');
                } else {
                    renderTudo();
                }
            } finally {
                fab.classList.remove('is-loading');
            }
        });

        document.querySelectorAll('.logistica-mobile .m-sidebar-toggle').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const tg = document.getElementById('btnSidebarToggleMobile');
                if (tg) tg.click();
            });
        });

        $('m_lg_fSalvar').addEventListener('click', salvarRotaMobile);
        $('m_lg_fAddDestino').addEventListener('click', adicionarDestinoMobile);
    }

    // -------------------------------------------------------------------------
    // BOOT
    // -------------------------------------------------------------------------
    function boot() {
        setActiveScreen('lista');
        setupSheets();
        setupBottomNav();
        setupSheetMais();
        setupSheetFiltros();
        setupAcoes();
        setupBuscaMobile();
        setupTypeaheadVeiculoMobile();
        setupTypeaheadMotoristaMobile();
        setupTypeaheadAjudanteMobile();
        setupSwipeToBack();
        renderTudo();
        // Aguarda o LogisticaApi (boot do desktop) e dispara refetch com filtros do mobile
        setTimeout(function () {
            refetchViagensMobile().then(function () {
                // Deep-link: ?viagem=<id> abre direto o detalhe da viagem
                // Usado pelo módulo Caixas (swipe-to-transfer no card de Viagem)
                var urlParams = new URLSearchParams(window.location.search);
                var viagemId = parseInt(urlParams.get('viagem'), 10);
                if (viagemId) {
                    var rota = rotas().find(function (r) { return r.id === viagemId; });
                    if (rota) abrirDetalhe(viagemId);
                }
            });
        }, 500);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
