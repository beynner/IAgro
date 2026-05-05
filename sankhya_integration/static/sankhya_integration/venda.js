document.addEventListener('DOMContentLoaded', function() {
    // ==========================================
    // HELPERS GLOBAIS (postJSON, toast, debounce, confirmarAcao)
    // ==========================================
    const PH = window.IAgro || {};
    const phPostJSON = PH.postJSON || async function(url, body){
        const m = document.cookie.match(/(?:^|;)\s*csrftoken=([^;]+)/);
        const csrftoken = m ? decodeURIComponent(m[1]) : '';
        const r = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify(body),
        });
        let data = null;
        try { data = await r.json(); } catch(e) { data = null; }
        return { ok: r.ok, status: r.status, body: data };
    };
    const phToast = window.showToast || PH.showToast || function(msg){ alert(msg); };
    const phConfirmar = PH.confirmarAcao || (async (o) => Promise.resolve(window.confirm(o.mensagem || 'Confirmar?')));
    const phDebounce = PH.debounce || function(fn, wait) {
        let t;
        return function(...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), wait); };
    };

    // ==========================================
    // 1. ELEMENTOS DA TELA
    // ==========================================
    const formFiltros = document.getElementById('filtersForm');
    const btnUpdate = document.getElementById('btnUpdate');
    const btnClear = document.getElementById('btnClear');
    const tbodyVendas = document.getElementById('vendasTableBody');
    const listaContainer = document.getElementById('vendasList');

    // Campos do filtro: agora são filhos do header (não do <form>), conectados via
    // attribute form="filtersForm". FormData() coleta corretamente, mas para event-binding
    // pegamos os elementos pelos seus IDs específicos.
    const inputStart = document.getElementById('dataInicio');
    const inputEnd   = document.getElementById('dataFim');
    const camposFiltroEventBind = [
        'filtroTop', 'filtroPedido', 'filtroNF', 'filtroLote',
    ].map(id => document.getElementById(id)).filter(Boolean);

    // ==========================================
    // 2. VARIÁVEIS DE ESTADO
    // ==========================================
    let offsetAtual = 0;
    const limite = 50;
    let carregando = false;
    let temMaisRegistros = true;
    let dataFinalAlteradaManualmente = false;

    let pedidoSelecionado = null;
    let modoEdicao = false;
    let modoEdicaoCabecalho = false;
    // Cache local dos itens do pedido aberto no modal (drives resumo + edit)
    let itensAtuais = [];
    // Quando >= 0, está editando o item dessa SEQUENCIA
    let itemEditandoSeq = -1;
    // Cache do cabeçalho aberto (cliente, tipo neg) para resumo
    let cabecalhoAtual = { cliente: '', tipo: '' };
    // Acumulador de pedidos carregados (para totalizadores) — reset a cada nova busca
    let vendasAcumuladas = [];

    const dispararFiltroAutomatico = phDebounce(() => carregarVendas(false), 500);

    camposFiltroEventBind.forEach(campo => {
        campo.addEventListener('input', dispararFiltroAutomatico);
        campo.addEventListener('change', dispararFiltroAutomatico);
    });

    // ==========================================
    // 2.5 PERSISTÊNCIA DE FILTROS EM localStorage (B5)
    // ==========================================
    const STORAGE_KEY_FILTROS = 'iagro:venda:filtros:v1';
    const CAMPOS_FILTRO_PERSISTIDOS = [
        'dataInicio', 'dataFim',
        'filtroTop', 'filtroPedido', 'filtroNF', 'filtroLote',
        'filtroEmpresa', 'filtroEmpresaSearch',
        'codparc', 'parcSearch',
        'codprod', 'prodSearch',
    ];

    function salvarFiltrosNoLocalStorage() {
        try {
            const dados = {};
            CAMPOS_FILTRO_PERSISTIDOS.forEach(id => {
                const el = document.getElementById(id);
                if (el && el.value !== '' && el.value != null) dados[id] = el.value;
            });
            localStorage.setItem(STORAGE_KEY_FILTROS, JSON.stringify(dados));
        } catch (e) { /* localStorage indisponível: ignora silenciosamente */ }
    }

    function carregarFiltrosDoLocalStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY_FILTROS);
            if (!raw) return false;
            const dados = JSON.parse(raw);
            if (!dados || typeof dados !== 'object') return false;
            let aplicou = false;
            CAMPOS_FILTRO_PERSISTIDOS.forEach(id => {
                if (id in dados) {
                    const el = document.getElementById(id);
                    if (el && dados[id] != null) { el.value = dados[id]; aplicou = true; }
                }
            });
            return aplicou;
        } catch (e) { return false; }
    }

    function limparFiltrosNoLocalStorage() {
        try { localStorage.removeItem(STORAGE_KEY_FILTROS); } catch (e) {}
    }

    // ==========================================
    // 3. LÓGICA DE DATAS
    // ==========================================
    inputStart.addEventListener('change', function() {
        if (!dataFinalAlteradaManualmente) inputEnd.value = this.value;
        carregarVendas(false);
    });
    inputEnd.addEventListener('change', function() {
        dataFinalAlteradaManualmente = true;
        carregarVendas(false);
    });
    function deslocarDatas(dias) {
        let d1 = inputStart.value ? new Date(inputStart.value + 'T12:00:00') : new Date();
        d1.setDate(d1.getDate() + dias);
        const novaData = d1.toISOString().split('T')[0];
        inputStart.value = novaData;
        if (!dataFinalAlteradaManualmente) inputEnd.value = novaData;
        else if (!inputEnd.value) inputEnd.value = novaData;
        carregarVendas(false);
    }
    document.getElementById('btnPrevDate').addEventListener('click', () => deslocarDatas(-1));
    document.getElementById('btnNextDate').addEventListener('click', () => deslocarDatas(1));

    function inicializarDatas() {
        const hoje = new Date().toISOString().split('T')[0];
        inputStart.value = hoje;
        inputEnd.value = hoje;
        dataFinalAlteradaManualmente = false;
    }

    // ==========================================
    // 4. TYPEAHEAD GENÉRICO
    // ==========================================
    function attachTA(inpId, hidId, ddId, url, options) {
        try {
            const inp = document.getElementById(inpId);
            const hid = document.getElementById(hidId);
            const dd = document.getElementById(ddId);
            if (!inp || !hid || !dd) return;

            let t = null;

            function hide() { dd.style.display = 'none'; dd.innerHTML = ''; }
            function show(items) {
                if (!items || !items.length) { hide(); return; }
                dd.innerHTML = items.map((it, idx) =>
                    `<div class="dd-item${idx === 0 ? ' active' : ''}" data-cod="${it.cod || it.codparc}" data-descr="${it.descr || it.nomeparc}">${(it.cod || it.codparc)} — ${(it.descr || it.nomeparc)}</div>`
                ).join('');
                dd.style.display = 'block';
            }

            const lim = options && typeof options.limit === 'number' ? Math.floor(options.limit) : 10;
            const extraQuery = options && options.extraQuery ? options.extraQuery : '';
            const onChange = (options && typeof options.onChange === 'function')
                ? options.onChange
                : () => carregarVendas(false);

            function buildUrl(q) {
                const sep = url.includes('?') ? '&' : '?';
                let full = `${url}${sep}q=${encodeURIComponent(q)}&limit=${lim}`;
                if (extraQuery) full += `&${extraQuery}`;
                return full;
            }
            function fetchQ(q) {
                fetch(buildUrl(q)).then(r => r.json()).then(d => show(d.results || [])).catch(() => hide());
            }

            inp.addEventListener('input', (e) => {
                const raw = (e.target.value || '').trim();
                if (t) clearTimeout(t);
                if (raw) {
                    t = setTimeout(() => fetchQ(raw), 400);
                } else {
                    hide();
                    hid.value = '';
                    onChange();
                }
            });
            inp.addEventListener('keydown', (e) => {
                if (dd.style.display === 'none') return;
                const items = Array.from(dd.querySelectorAll('.dd-item'));
                if (!items.length) return;
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    let cur = items.findIndex(x => x.classList.contains('active'));
                    let nxt = (cur + 1) % items.length;
                    items.forEach(x => x.classList.remove('active'));
                    items[nxt].classList.add('active');
                    items[nxt].scrollIntoView({ block: 'nearest' });
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    let cur = items.findIndex(x => x.classList.contains('active'));
                    let nxt = (cur - 1 + items.length) % items.length;
                    items.forEach(x => x.classList.remove('active'));
                    items[nxt].classList.add('active');
                    items[nxt].scrollIntoView({ block: 'nearest' });
                } else if (e.key === 'Enter' || e.key === 'Tab') {
                    const el = dd.querySelector('.dd-item.active') || dd.querySelector('.dd-item');
                    if (el) {
                        e.preventDefault();
                        hid.value = el.dataset.cod;
                        inp.value = `${el.dataset.cod} — ${el.dataset.descr}`;
                        hide();
                        onChange();
                    }
                } else if (e.key === 'Escape') hide();
            });
            dd.addEventListener('click', (ev) => {
                const el = ev.target.closest('div[data-cod]');
                if (!el) return;
                hid.value = el.dataset.cod;
                inp.value = `${el.dataset.cod} — ${el.dataset.descr}`;
                hide();
                onChange();
            });
            document.addEventListener('click', (ev) => {
                if (!dd.contains(ev.target) && ev.target !== inp) hide();
            });
        } catch (e) {
            console.error('Erro no attachTA:', e);
        }
    }

    attachTA('parcSearch', 'codparc', 'parcDropdown', '/sankhya/parceiros/search/', { limit: 15 });
    attachTA('prodSearch', 'codprod', 'prodDropdown', '/sankhya/produtos/search/', {
        limit: 15, extraQuery: 'grupo_inicia_com=1'
    });
    attachTA('filtroEmpresaSearch', 'filtroEmpresa', 'filtroEmpresaDropdown', '/sankhya/empresa/search/', { limit: 15 });

    // ==========================================
    // 5. BUSCA DO CABEÇALHO
    // ==========================================
    async function carregarVendas(append = false) {
        if (carregando || (!temMaisRegistros && append)) return;

        if (!append) {
            offsetAtual = 0;
            temMaisRegistros = true;
            vendasAcumuladas = [];
            salvarFiltrosNoLocalStorage();
            atualizarResumoListagem();
            renderChipsFiltros();
            tbodyVendas.innerHTML = '<tr><td colspan="7" class="text-center ia-muted">Buscando no banco de dados...</td></tr>';
            document.getElementById('vendaItemsBody').innerHTML = '<tr><td colspan="4" class="ia-placeholder">Selecione uma venda</td></tr>';
            pedidoSelecionado = null;
            const btnDel = document.getElementById('btnDeleteVenda');
            if (btnDel) btnDel.disabled = true;
            const labelSel = document.getElementById('label_sel_nunota');
            if (labelSel) labelSel.textContent = '—';
            const subheader = document.getElementById('itensCardSubheader');
            if (subheader) subheader.textContent = '';
        } else {
            const trLoading = document.createElement('tr');
            trLoading.id = 'loading-row';
            trLoading.innerHTML = '<td colspan="7" class="text-center ia-muted">Carregando mais pedidos...</td>';
            tbodyVendas.appendChild(trLoading);
        }

        carregando = true;
        const formData = new FormData(formFiltros);
        formData.append('limit', limite);
        formData.append('offset', offsetAtual);
        const params = new URLSearchParams(formData);

        try {
            const response = await fetch(`/sankhya/venda/api/listar/?${params.toString()}`);
            const data = await response.json();

            if (!data.ok) throw new Error(data.error || 'Erro do Servidor');

            if (!append) tbodyVendas.innerHTML = '';
            else { document.getElementById('loading-row')?.remove(); }

            if (data.vendas.length === 0) {
                if (!append) renderEmptyStateLista();
                temMaisRegistros = false;
                carregando = false;
                atualizarResumoListagem();
                return;
            }
            if (data.vendas.length < limite) temMaisRegistros = false;

            vendasAcumuladas.push(...data.vendas);
            atualizarResumoListagem();

            data.vendas.forEach(v => {
                const tr = document.createElement('tr');
                const topNum = parseInt(v.top, 10) || 0;

                // Status do pedido (3 estados visuais distintos):
                //   FATURADO     — TOP 35/37 (já liberado, não editável)
                //   PENDENTE     — TOP 34 com algum item sem lote (não pode faturar)
                //   ABERTO       — TOP 34 com todos os itens com lote (pronto p/ faturar)
                let statusKey, statusTitulo;
                if (topNum === 35 || topNum === 37) {
                    statusKey = 'faturado';
                    statusTitulo = topNum === 35 ? 'Faturado com NFe' : 'Faturado sem NFe';
                } else if (v.status_lote === 'PENDENTE') {
                    statusKey = 'pendente';
                    statusTitulo = 'Pendente — itens sem lote vinculado';
                } else {
                    statusKey = 'aberto';
                    statusTitulo = 'Aberto — pronto para faturar';
                }
                tr.className = `row--click venda-row venda-status-${statusKey}`
                    + (statusKey === 'pendente' ? ' lote-alerta' : '')
                    + (statusKey === 'faturado' ? ' pedido-faturado' : '');
                tr.dataset.nunota = v.nunota;

                const valorFormatado = v.total.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                const topLabel = topNum === 34 ? '34' :
                                 topNum === 35 ? '35-NFe' :
                                 topNum === 37 ? '37-S/NFe' : String(topNum);
                const statusDot = `<span class="venda-status-dot venda-status-dot--${statusKey}" title="${statusTitulo}" aria-label="${statusTitulo}"></span>`;

                tr.innerHTML = `
                    <td>${statusDot}${v.nunota}</td>
                    <td>${v.numnota || '—'}</td>
                    <td>${v.emp}</td>
                    <td><span class="top-badge top-${topNum}">${topLabel}</span></td>
                    <td>${v.data ? v.data.substring(0,5) : ''}</td>
                    <td class="ia-truncate" title="${v.parceiro}">${v.parceiro}</td>
                    <td class="text-right">${valorFormatado}</td>
                `;

                tr.addEventListener('click', function() {
                    document.querySelectorAll('#vendasTableBody tr').forEach(l => l.classList.remove('selected'));
                    this.classList.add('selected');
                    document.getElementById('label_sel_nunota').textContent = v.nunota;
                    // Popula o subheader do card de itens com contexto do pedido
                    const sub = document.getElementById('itensCardSubheader');
                    if (sub) {
                        sub.innerHTML = `
                            <span class="top-badge top-${topNum}">${topLabel}</span>
                            <span class="vrh-sep">·</span>
                            <span>${v.data ? v.data.substring(0,5) : ''}</span>
                            <span class="vrh-sep">·</span>
                            <span class="venda-status-dot venda-status-dot--${statusKey}"></span>
                            <span title="${statusTitulo}">${statusKey === 'aberto' ? 'Aberto' : statusKey === 'pendente' ? 'Sem lote' : 'Faturado'}</span>
                        `;
                    }
                    carregarItens(v.nunota);
                    pedidoSelecionado = { nunota: v.nunota, top: topNum };
                    const btnDel = document.getElementById('btnDeleteVenda');
                    if (btnDel) btnDel.disabled = (topNum !== 34);  // só TOP 34 pode excluir
                });
                tr.addEventListener('dblclick', function() {
                    if (topNum !== 34) {
                        phToast('Apenas pedidos TOP 34 podem ser editados.', 'warning');
                        return;
                    }
                    abrirPedidoParaEdicao(v.nunota);
                });
                tbodyVendas.appendChild(tr);
            });

            offsetAtual += limite;
        } catch (error) {
            console.error("Erro Backend:", error);
            if (!append) tbodyVendas.innerHTML = `<tr><td colspan="7" class="text-center" style="color:#ef4444;">Erro: ${error.message}</td></tr>`;
        } finally {
            carregando = false;
        }
    }

    /** Renderiza chips de filtros ativos no card #filtrosAtivos. Cada chip tem botão × para remover. */
    function renderChipsFiltros() {
        const cont = document.getElementById('filtrosAtivosChips');
        if (!cont) return;

        const hoje = new Date().toISOString().split('T')[0];
        const chips = [];

        // Datas (só mostra chip se diferente de "hoje")
        const ini = inputStart?.value;
        const fim = inputEnd?.value;
        if (ini && fim && (ini !== hoje || fim !== hoje)) {
            const txt = ini === fim
                ? new Date(ini + 'T12:00:00').toLocaleDateString('pt-BR')
                : `${new Date(ini + 'T12:00:00').toLocaleDateString('pt-BR')} → ${new Date(fim + 'T12:00:00').toLocaleDateString('pt-BR')}`;
            chips.push({ rotulo: 'Período', valor: txt, remover: () => { inicializarDatas(); carregarVendas(false); renderChipsFiltros(); } });
        }

        const top = document.getElementById('filtroTop')?.value;
        if (top && top !== 'T') {
            const labels = { '34': '34 — Pedido', '35': '35 — NFe', '37': '37 — S/ NFe' };
            chips.push({ rotulo: 'TOP', valor: labels[top] || top, remover: () => { document.getElementById('filtroTop').value = 'T'; carregarVendas(false); } });
        }

        const codemp = document.getElementById('filtroEmpresa')?.value;
        if (codemp) {
            const visivel = document.getElementById('filtroEmpresaSearch')?.value || codemp;
            chips.push({ rotulo: 'Empresa', valor: visivel, remover: () => {
                document.getElementById('filtroEmpresa').value = '';
                document.getElementById('filtroEmpresaSearch').value = '';
                carregarVendas(false);
            }});
        }

        const nunota = document.getElementById('filtroPedido')?.value;
        if (nunota) chips.push({ rotulo: 'Pedido', valor: nunota, remover: () => { document.getElementById('filtroPedido').value = ''; carregarVendas(false); } });

        const nf = document.getElementById('filtroNF')?.value;
        if (nf) chips.push({ rotulo: 'Nota', valor: nf, remover: () => { document.getElementById('filtroNF').value = ''; carregarVendas(false); } });

        const lote = document.getElementById('filtroLote')?.value?.trim();
        if (lote) chips.push({ rotulo: 'Lote', valor: lote, remover: () => { document.getElementById('filtroLote').value = ''; carregarVendas(false); } });

        const codparc = document.getElementById('codparc')?.value;
        if (codparc) {
            const visivel = document.getElementById('parcSearch')?.value || codparc;
            chips.push({ rotulo: 'Parceiro', valor: visivel, remover: () => {
                document.getElementById('codparc').value = '';
                document.getElementById('parcSearch').value = '';
                carregarVendas(false);
            }});
        }

        const codprod = document.getElementById('codprod')?.value;
        if (codprod) {
            const visivel = document.getElementById('prodSearch')?.value || codprod;
            chips.push({ rotulo: 'Produto', valor: visivel, remover: () => {
                document.getElementById('codprod').value = '';
                document.getElementById('prodSearch').value = '';
                carregarVendas(false);
            }});
        }

        cont.innerHTML = '';
        chips.forEach((chip, idx) => {
            const el = document.createElement('span');
            el.className = 'vda-filtro-chip';
            el.innerHTML = `
                <span class="chip-rotulo">${chip.rotulo}:</span>
                <span class="chip-valor" title="${chip.valor}">${chip.valor}</span>
                <button type="button" class="chip-remover" data-idx="${idx}" title="Remover" aria-label="Remover">×</button>
            `;
            el.querySelector('.chip-remover').addEventListener('click', chip.remover);
            cont.appendChild(el);
        });
    }

    /** Recalcula contagem e somatório de pedidos visíveis e popula o header do card. */
    function atualizarResumoListagem() {
        const el = document.getElementById('vendasResumoHeader');
        if (!el) return;
        if (!vendasAcumuladas.length) { el.innerHTML = ''; return; }

        let abertos = 0, faturados = 0, pendentesLote = 0, totalGeral = 0;
        for (const v of vendasAcumuladas) {
            const top = parseInt(v.top, 10) || 0;
            totalGeral += parseFloat(v.total) || 0;
            if (top === 35 || top === 37) faturados++;
            else abertos++;
            if (v.status_lote === 'PENDENTE') pendentesLote++;
        }
        const valorFmt = totalGeral.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
        const sufMais = temMaisRegistros ? '+' : '';
        const partes = [
            `<span class="vrh-count">${vendasAcumuladas.length}${sufMais} pedidos</span>`,
            `<span class="vrh-sep">·</span>`,
            `<span class="vrh-total">R$ ${valorFmt}</span>`,
        ];
        if (abertos)        partes.push(`<span class="vrh-sep">·</span><span class="vrh-abertos">${abertos} abertos</span>`);
        if (faturados)      partes.push(`<span class="vrh-sep">·</span><span class="vrh-faturados">${faturados} faturados</span>`);
        if (pendentesLote)  partes.push(`<span class="vrh-sep">·</span><span class="vrh-pendentes">${pendentesLote} sem lote</span>`);
        el.innerHTML = partes.join(' ');
    }

    /** Empty state amigável quando o filtro não retorna nada. */
    function renderEmptyStateLista() {
        tbodyVendas.innerHTML = `
            <tr><td colspan="7">
                <div class="ia-empty-state">
                    <div class="ia-empty-titulo">Nenhum pedido encontrado</div>
                    <div class="ia-empty-msg">Tente ajustar a data ou os filtros, ou crie um novo pedido.</div>
                    <div class="ia-empty-actions">
                        <button type="button" class="btn btn-clear" id="emptyClearBtn">Limpar filtros</button>
                        <button type="button" class="btn btn-success" id="emptyNewBtn">+ Novo pedido</button>
                    </div>
                </div>
            </td></tr>`;
        document.getElementById('emptyClearBtn')?.addEventListener('click', () => btnClear.click());
        document.getElementById('emptyNewBtn')?.addEventListener('click', () => document.getElementById('btnNewVenda')?.click());
    }

    listaContainer.addEventListener('scroll', function() {
        if (listaContainer.scrollTop + listaContainer.clientHeight >= listaContainer.scrollHeight - 10) {
            carregarVendas(true);
        }
    });

    // ==========================================
    // 7. BUSCA DOS ITENS (painel direito)
    // ==========================================
    async function carregarItens(nunota) {
        const tbodyItens = document.getElementById('vendaItemsBody');
        tbodyItens.innerHTML = '<tr><td colspan="4" class="text-center ia-muted">Carregando itens...</td></tr>';

        try {
            const response = await fetch(`/sankhya/item/list/?nunota=${nunota}`);
            const data = await response.json();
            if (!data.ok) throw new Error(data.error);

            tbodyItens.innerHTML = '';
            if (data.items.length === 0) {
                tbodyItens.innerHTML = '<tr><td colspan="4" class="text-center ia-muted">Nota sem itens.</td></tr>';
                return;
            }
            data.items.forEach(item => {
                const tr = document.createElement('tr');
                if (!item.lote) tr.classList.add('item-sem-lote');
                const qtd = parseFloat(item.qtd).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                const total = parseFloat(item.vlt).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                tr.innerHTML = `
                    <td>${item.lote || '—'}</td>
                    <td class="ia-truncate" title="${item.descr}">${item.descr}</td>
                    <td class="text-right">${qtd}</td>
                    <td class="text-right">${total}</td>
                `;
                tbodyItens.appendChild(tr);
            });
        } catch (error) {
            tbodyItens.innerHTML = `<tr><td colspan="4" class="text-center" style="color:#ef4444;">Erro: ${error.message}</td></tr>`;
        }
    }

    // ==========================================
    // 8. BOTÕES DE FILTRO
    // ==========================================
    btnUpdate.addEventListener('click', () => carregarVendas(false));
    btnClear.addEventListener('click', () => {
        // Limpa todos os campos do filtro (agora estão fora do <form>, então .reset() não funciona)
        camposFiltroEventBind.forEach(c => { c.value = c.tagName === 'SELECT' ? c.options[0].value : ''; });
        ['codparc', 'parcSearch', 'codprod', 'prodSearch', 'filtroEmpresa', 'filtroEmpresaSearch'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        ['parcDropdown', 'prodDropdown', 'filtroEmpresaDropdown'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        // Datas voltam para hoje
        inicializarDatas();
        // Apaga preferências persistidas para que próxima sessão também comece limpa
        limparFiltrosNoLocalStorage();
        carregarVendas(false);
    });

    // ==========================================
    // 9. FLUXO DE CRIAÇÃO/EDIÇÃO DE PEDIDO
    // ==========================================
    const cabModal      = document.getElementById('cabModal');
    const cabCard       = document.getElementById('cabCard');
    const cabItemsModal = document.getElementById('cabItemsModal');
    const cabItemsCard  = document.getElementById('cabItemsCard');

    function dockCabecalhoEsquerda() {
        if (!cabModal || !cabCard) return;
        cabModal.style.display = 'block';
        cabCard.style.left    = '16px';
        cabCard.style.opacity = '1';
    }

    function travarInputsCabecalho() {
        if (!cabCard) return;
        cabCard.querySelectorAll('input, textarea, select, button').forEach(el => {
            if (el.dataset.wasDisabled === undefined) {
                el.dataset.wasDisabled = el.disabled ? '1' : '0';
            }
            const preservar = (el.id || '') === 'cabCancel';
            if (!preservar) el.disabled = true;
        });
    }
    function restaurarInputsCabecalho() {
        if (!cabCard) return;
        cabCard.querySelectorAll('input, textarea, select, button').forEach(el => {
            if (el.dataset && el.dataset.wasDisabled !== undefined) {
                el.disabled = el.dataset.wasDisabled === '1';
                delete el.dataset.wasDisabled;
            }
        });
    }
    function abrirItensAoLado() {
        if (!cabItemsModal || !cabItemsCard || !cabCard) return;
        travarInputsCabecalho();
        cabItemsModal.style.display = 'block';
        const cabRect = cabCard.getBoundingClientRect();
        const leftItens = Math.max(16 + cabRect.width + 8, cabRect.right + 8) + 'px';
        requestAnimationFrame(() => { cabItemsCard.style.left = leftItens; });
    }

    let itensInseridosCount = 0;

    async function fecharTudo() {
        const nunotaStr = document.getElementById('cab_nunota')?.value || '';
        const nunota    = parseInt(nunotaStr, 10);
        const precisaDeletar = !modoEdicao && nunota && itensInseridosCount === 0;

        if (document.getElementById('cab_nunota')) document.getElementById('cab_nunota').value = '';
        itensInseridosCount = 0;
        modoEdicao = false;
        modoEdicaoCabecalho = false;
        itensAtuais = [];
        itemEditandoSeq = -1;
        cabecalhoAtual = { cliente: '', tipo: '' };
        atualizarResumoModal();

        if (cabItemsCard) cabItemsCard.style.left = '100%';
        if (cabCard)      cabCard.style.left      = '-1200px';
        restaurarInputsCabecalho();
        setTimeout(() => {
            if (cabItemsModal) cabItemsModal.style.display = 'none';
            if (cabModal)      cabModal.style.display      = 'none';
        }, 320);

        if (precisaDeletar) {
            try {
                const res = await phPostJSON('/sankhya/venda/api/excluir/', { nunota });
                if (res.ok && res.body?.ok) {
                    phToast(`Pedido ${nunota} cancelado (nenhum item adicionado).`, 'info');
                } else {
                    phToast(res.body?.error || `Falha ao remover pedido ${nunota}.`, 'error');
                }
            } catch (_) {
                phToast(`Erro ao remover pedido ${nunota}.`, 'error');
            }
        }
    }

    async function abrirPedidoParaEdicao(nunota) {
        modoEdicao = true;
        itensInseridosCount = 0;
        limparMarcasInvalidas();
        limparCamposItem();
        itemEditandoSeq = -1;

        document.getElementById('cab_nunota').value = nunota;
        document.getElementById('cab_empSearch').value      = 'Carregando...';
        document.getElementById('cab_parcSearch').value     = 'Carregando...';
        document.getElementById('cab_tipvendaSearch').value = 'Carregando...';
        document.getElementById('cab_dtneg').value          = '';
        document.getElementById('cab_obs').value            = '';

        try {
            const rc = await fetch(`/sankhya/venda/api/cabecalho/obter/?nunota=${nunota}`);
            const dc = await rc.json();
            if (!dc.ok) throw new Error(dc.error || 'Erro ao obter cabeçalho');
            document.getElementById('cab_codemp').value         = dc.codemp ?? '';
            document.getElementById('cab_empSearch').value      = dc.codemp ? `${dc.codemp} — ${dc.nome_emp || ''}` : '';
            document.getElementById('cab_codparc').value        = dc.codparc ?? '';
            document.getElementById('cab_parcSearch').value     = dc.codparc ? `${dc.codparc} — ${dc.nome_parc || ''}` : '';
            document.getElementById('cab_codtipvenda').value    = dc.codtipvenda ?? '';
            document.getElementById('cab_tipvendaSearch').value = dc.codtipvenda ? `${dc.codtipvenda} — ${dc.descr_tipvenda || ''}` : '';
            document.getElementById('cab_dtneg').value          = dc.dtneg || '';
            document.getElementById('cab_obs').value            = dc.obs || '';

            cabecalhoAtual = {
                cliente: dc.nome_parc || '—',
                tipo:    dc.descr_tipvenda || '—',
            };
        } catch (e) {
            phToast(`Erro ao carregar cabeçalho: ${e.message}`, 'error');
            modoEdicao = false;
            return;
        }

        restaurarInputsCabecalho();
        dockCabecalhoEsquerda();
        document.getElementById('items_nunota').value = nunota;
        document.getElementById('items_nunota_display').textContent = nunota;
        document.getElementById('itemsListBody').innerHTML =
            '<tr><td colspan="6" class="ia-placeholder">Carregando itens...</td></tr>';
        abrirItensAoLado();
        setTimeout(() => document.getElementById('item_prod_vis')?.focus(), 160);

        await recarregarItensDoPedido(nunota);
    }

    /** Busca os itens do pedido aberto e popula a tabela do modal +
     *  o cache local + o resumo. Centraliza para reuso após add/edit/remove. */
    async function recarregarItensDoPedido(nunota) {
        try {
            const ri = await fetch(`/sankhya/item/list/?nunota=${nunota}`);
            const di = await ri.json();
            if (!di.ok) throw new Error(di.error || 'Erro ao carregar itens');
            itensAtuais = (di.items || []).map(it => ({
                seq:   parseInt(it.sequencia, 10),
                lote:  it.lote || '',
                cod:   parseInt(it.cod, 10),
                descr: it.descr || '',
                qtd:   parseFloat(it.qtd) || 0,
                vlu:   parseFloat(it.vlu) || 0,
                vlt:   parseFloat(it.vlt) || 0,
                codvol: it.codvol || 'CX',
            }));
            renderItensModal();
            atualizarResumoModal();
        } catch (e) {
            const tbody = document.getElementById('itemsListBody');
            tbody.innerHTML = `<tr><td colspan="6" class="ia-placeholder" style="color:#ef4444">Erro: ${e.message}</td></tr>`;
        }
    }

    function renderItensModal() {
        const tbody = document.getElementById('itemsListBody');
        if (itensAtuais.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="ia-placeholder">Nenhum item inserido.</td></tr>';
            return;
        }
        tbody.innerHTML = '';
        itensAtuais.forEach(item => {
            const qtd   = item.qtd.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            const preco = item.vlu.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            const total = item.vlt.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            const tr = document.createElement('tr');
            tr.dataset.seq = item.seq;
            if (itemEditandoSeq === item.seq) tr.classList.add('selected');
            tr.innerHTML = `
                <td class="ia-truncate" title="${item.descr}">${item.descr}</td>
                <td>${item.lote || '—'}</td>
                <td class="text-right">${qtd}</td>
                <td class="text-right">${preco}</td>
                <td class="text-right">${total}</td>
                <td class="text-center">
                    <button class="icon-btn-mini btn-edit-item" title="Editar item" data-seq="${item.seq}">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    </button>
                    <button class="icon-btn-mini btn-rm-item" title="Remover item" data-seq="${item.seq}">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.btn-edit-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                iniciarEdicaoItem(parseInt(btn.dataset.seq, 10));
            });
        });
        tbody.querySelectorAll('.btn-rm-item').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await removerItem(parseInt(btn.dataset.seq, 10));
            });
        });
    }

    /** Atualiza o resumo do header do modal com cliente, tipo, total e contagem. */
    function atualizarResumoModal() {
        const elCliente = document.getElementById('itemsResumoCliente');
        const elTipo    = document.getElementById('itemsResumoTipo');
        const elTotal   = document.getElementById('itemsResumoTotal');
        const elCount   = document.getElementById('itemsResumoCount');
        const elBadge   = document.getElementById('badge_lote_pendente');
        if (!elCliente || !elTotal) return;

        elCliente.textContent = cabecalhoAtual.cliente || '—';
        elTipo.textContent    = cabecalhoAtual.tipo || '—';
        const total = itensAtuais.reduce((s, it) => s + (it.vlt || 0), 0);
        elTotal.textContent = `R$ ${total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
        elCount.textContent = `(${itensAtuais.length} ${itensAtuais.length === 1 ? 'item' : 'itens'})`;
        const temPendente = itensAtuais.some(it => !it.lote);
        if (elBadge) elBadge.classList.toggle('hidden', !temPendente);
    }

    /** Coloca o formulário de item em modo edição: popula campos, troca botão. */
    function iniciarEdicaoItem(seq) {
        const item = itensAtuais.find(it => it.seq === seq);
        if (!item) return;
        itemEditandoSeq = seq;

        document.getElementById('item_prod_hidden').value = item.cod;
        document.getElementById('item_prod_vis').value    = item.descr;
        document.getElementById('item_lote').value        = item.lote || '';
        document.getElementById('item_codvol').value      = item.codvol || 'CX';
        document.getElementById('item_qtd').value         = item.qtd;
        document.getElementById('item_preco').value       = item.vlu;
        atualizarTotalItem();

        // Troca o botão "+" por "salvar edição" + mostra botão cancelar
        const btnAdd = document.getElementById('itemAddBtn');
        const btnCancelEdit = document.getElementById('itemEditCancel');
        if (btnAdd) btnAdd.title = 'Salvar Alterações';
        btnAdd?.classList.add('btn-edit-mode');
        btnCancelEdit?.classList.remove('hidden');
        renderItensModal();
        document.getElementById('item_qtd')?.focus();
        document.getElementById('item_qtd')?.select();
    }

    function cancelarEdicaoItem() {
        itemEditandoSeq = -1;
        const btnAdd = document.getElementById('itemAddBtn');
        const btnCancelEdit = document.getElementById('itemEditCancel');
        if (btnAdd) btnAdd.title = 'Adicionar Item (Enter)';
        btnAdd?.classList.remove('btn-edit-mode');
        btnCancelEdit?.classList.add('hidden');
        limparCamposItem();
        renderItensModal();
        document.getElementById('item_prod_vis')?.focus();
    }

    async function removerItem(seq) {
        const item = itensAtuais.find(it => it.seq === seq);
        if (!item) return;
        const nunota = parseInt(document.getElementById('items_nunota').value, 10);
        const ok = await phConfirmar({
            titulo:   'Remover item do pedido?',
            mensagem: `Remover <strong>${item.descr}</strong> (qtd ${item.qtd}, total R$ ${item.vlt.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}) do pedido <strong>${nunota}</strong>?`,
            confirmarLabel: 'Remover',
            tipo: 'perigo',
        });
        if (!ok) return;
        try {
            const res = await phPostJSON('/sankhya/venda/api/item/remover/', { nunota, sequencia: seq });
            if (!res.ok || !res.body?.ok) {
                phToast(res.body?.error || 'Falha ao remover item.', 'error');
                return;
            }
            phToast('Item removido.', 'success');
            // Se o pedido ficou vazio (cab_deleted), fecha o modal e recarrega lista
            if (res.body.cab_deleted) {
                phToast('Pedido sem itens — cabeçalho removido.', 'info');
                await fecharTudo();
                carregarVendas(false);
                return;
            }
            await recarregarItensDoPedido(nunota);
            if (itemEditandoSeq === seq) cancelarEdicaoItem();
        } catch (_) {
            phToast('Erro ao remover item.', 'error');
        }
    }

    document.getElementById('btnDeleteVenda')?.addEventListener('click', async () => {
        if (!pedidoSelecionado) return;
        if (pedidoSelecionado.top !== 34) {
            phToast('Apenas pedidos TOP 34 podem ser excluídos.', 'warning');
            return;
        }
        const ok = await phConfirmar({
            titulo:   'Excluir pedido?',
            mensagem: `Excluir o pedido <strong>${pedidoSelecionado.nunota}</strong>? Essa ação remove o cabeçalho e <strong>todos os itens</strong>.`,
            confirmarLabel: 'Excluir',
            tipo: 'perigo',
        });
        if (!ok) return;

        const btn = document.getElementById('btnDeleteVenda');
        btn.disabled = true;
        try {
            const res = await phPostJSON('/sankhya/venda/api/excluir/', { nunota: pedidoSelecionado.nunota });
            if (res.ok && res.body?.ok) {
                phToast(`Pedido ${pedidoSelecionado.nunota} excluído.`, 'success');
                pedidoSelecionado = null;
                carregarVendas(false);
            } else {
                phToast(res.body?.error || 'Falha ao excluir pedido.', 'error');
                btn.disabled = false;
            }
        } catch (_) {
            phToast('Erro ao excluir pedido.', 'error');
            btn.disabled = false;
        }
    });

    // --- Typeaheads dos modais ---
    const noop = () => {};
    attachTA('cab_empSearch', 'cab_codemp', 'cab_empDropdown', '/sankhya/empresa/search/',
             { limit: 15, onChange: noop });
    attachTA('cab_parcSearch', 'cab_codparc', 'cab_parcDropdown', '/sankhya/parceiros/search/',
             { limit: 15, onChange: noop });
    attachTA('cab_tipvendaSearch', 'cab_codtipvenda', 'cab_tipvendaDropdown', '/sankhya/tipvenda/search/',
             { limit: 15, onChange: () => {
                 // Atualiza resumo do modal quando muda o tipo
                 const v = document.getElementById('cab_tipvendaSearch').value;
                 cabecalhoAtual.tipo = v.split(' — ').slice(1).join(' — ') || v;
                 atualizarResumoModal();
             } });
    // Cliente também atualiza resumo
    document.getElementById('cab_parcSearch')?.addEventListener('change', () => {
        const v = document.getElementById('cab_parcSearch').value;
        cabecalhoAtual.cliente = v.split(' — ').slice(1).join(' — ') || v;
        atualizarResumoModal();
    });
    // CODNAT dropdown (Fase 2.6) — substituiu o label readonly
    attachTA('cab_natSearch', 'cab_codnat', 'cab_natDropdown', '/sankhya/natureza/search/',
             { limit: 15, onChange: noop });
    attachTA('item_prod_vis', 'item_prod_hidden', 'item_prod_sugg', '/sankhya/produtos/search/',
             { limit: 15, extraQuery: 'grupo_inicia_com=1', onChange: noop });

    // --- Labels de codigo fixo (Centro de Resultado: hardcoded como antes) ---
    async function carregarLabelFixo(codigo, url, inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        try {
            const r = await fetch(`${url}?q=${codigo}&limit=5`);
            const d = await r.json();
            const item = (d.results || []).find(x => String(x.cod) === String(codigo));
            input.value = item ? `${item.cod} — ${item.descr}` : `${codigo} — (não encontrado)`;
        } catch {
            input.value = `${codigo} — (erro ao carregar)`;
        }
    }
    carregarLabelFixo(10100, '/sankhya/cencus/search/', 'cab_cencus');
    // Pré-popular CODNAT padrão (10010100) no campo de busca
    (async () => {
        const inp = document.getElementById('cab_natSearch');
        if (!inp) return;
        try {
            const r = await fetch(`/sankhya/natureza/search/?q=10010100&limit=5`);
            const d = await r.json();
            const item = (d.results || []).find(x => String(x.cod) === '10010100');
            inp.value = item ? `${item.cod} — ${item.descr}` : '10010100';
            inp.placeholder = 'Natureza';
        } catch {
            inp.value = '10010100';
        }
    })();

    async function preencherTypeaheadPorCodigo(url, codigo, hidId, visId) {
        const hid = document.getElementById(hidId);
        const vis = document.getElementById(visId);
        if (!hid || !vis) return;
        hid.value = String(codigo);
        vis.value = `${codigo} — carregando...`;
        try {
            const r = await fetch(`${url}?q=${codigo}&limit=5`);
            const d = await r.json();
            const item = (d.results || []).find(x => String(x.cod) === String(codigo));
            vis.value = item ? `${item.cod} — ${item.descr}` : `${codigo}`;
        } catch {
            vis.value = `${codigo}`;
        }
    }

    document.getElementById('btnNewVenda')?.addEventListener('click', () => {
        modoEdicao = false;
        modoEdicaoCabecalho = false;
        itensAtuais = [];
        cabecalhoAtual = { cliente: '', tipo: '' };
        document.getElementById('cab_nunota').value   = '';
        document.getElementById('cab_codparc').value  = '';
        document.getElementById('cab_parcSearch').value = '';
        document.getElementById('cab_codtipvenda').value    = '';
        document.getElementById('cab_tipvendaSearch').value = '';
        document.getElementById('cab_dtneg').value    = new Date().toISOString().split('T')[0];
        document.getElementById('cab_obs').value      = '';
        // Reseta CODNAT para o default (10010100 — Pedido de Venda)
        document.getElementById('cab_codnat').value = '10010100';
        preencherTypeaheadPorCodigo('/sankhya/natureza/search/', 10010100, 'cab_codnat', 'cab_natSearch');
        preencherTypeaheadPorCodigo('/sankhya/empresa/search/', 10, 'cab_codemp', 'cab_empSearch');
        restaurarInputsCabecalho();
        limparMarcasInvalidas();
        dockCabecalhoEsquerda();
        setTimeout(() => document.getElementById('cab_parcSearch')?.focus(), 160);
    });

    document.getElementById('cabCancel')?.addEventListener('click', async () => {
        if (modoEdicaoCabecalho) {
            const nunota = parseInt(document.getElementById('cab_nunota').value, 10);
            modoEdicaoCabecalho = false;
            if (nunota) {
                try {
                    const rc = await fetch(`/sankhya/venda/api/cabecalho/obter/?nunota=${nunota}`);
                    const dc = await rc.json();
                    if (dc.ok) {
                        document.getElementById('cab_codemp').value         = dc.codemp ?? '';
                        document.getElementById('cab_empSearch').value      = dc.codemp ? `${dc.codemp} — ${dc.nome_emp || ''}` : '';
                        document.getElementById('cab_codparc').value        = dc.codparc ?? '';
                        document.getElementById('cab_parcSearch').value     = dc.codparc ? `${dc.codparc} — ${dc.nome_parc || ''}` : '';
                        document.getElementById('cab_codtipvenda').value    = dc.codtipvenda ?? '';
                        document.getElementById('cab_tipvendaSearch').value = dc.codtipvenda ? `${dc.codtipvenda} — ${dc.descr_tipvenda || ''}` : '';
                        document.getElementById('cab_dtneg').value          = dc.dtneg || '';
                        document.getElementById('cab_obs').value            = dc.obs || '';
                    }
                } catch (_) {}
            }
            limparMarcasInvalidas();
            abrirItensAoLado();
            return;
        }
        await fecharTudo();
        carregarVendas(false);
    });

    const CABCARD_CAMPOS_OBRIGATORIOS = [
        { hidden: 'cab_codparc',     visible: 'cab_parcSearch' },
        { hidden: 'cab_codtipvenda', visible: 'cab_tipvendaSearch' },
        { hidden: null,              visible: 'cab_dtneg' },
    ];
    function marcarCampoInvalido(inputId) {
        document.getElementById(inputId)?.classList.add('ia-field-invalid');
    }
    function limparMarcasInvalidas() {
        cabCard?.querySelectorAll('.ia-field-invalid').forEach(el => el.classList.remove('ia-field-invalid'));
    }
    CABCARD_CAMPOS_OBRIGATORIOS.forEach(({ visible }) => {
        document.getElementById(visible)?.addEventListener('input', function () {
            this.classList.remove('ia-field-invalid');
        });
    });

    cabCard?.querySelectorAll('input:not([type="hidden"])').forEach(el => {
        el.addEventListener('focus', function () {
            if (this.disabled || this.readOnly) return;
            setTimeout(() => { try { this.select(); } catch (_) {} }, 0);
        });
    });

    function hasDropdownCabAberto() {
        return Array.from(cabCard?.querySelectorAll('.dropdown-abs') || [])
            .some(dd => dd.style.display === 'block');
    }
    cabCard?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            if (e.target.tagName === 'TEXTAREA') return;
            if (hasDropdownCabAberto()) return;
            e.preventDefault();
            document.getElementById('cabSave')?.click();
        } else if (e.key === 'Escape') {
            if (hasDropdownCabAberto()) return;
            e.preventDefault();
            document.getElementById('cabCancel')?.click();
        }
    });

    document.getElementById('cabSave')?.addEventListener('click', async () => {
        const codparc     = parseInt(document.getElementById('cab_codparc').value, 10);
        const codtipvenda = parseInt(document.getElementById('cab_codtipvenda').value, 10);
        const dtneg       = document.getElementById('cab_dtneg').value;
        const codemp      = parseInt(document.getElementById('cab_codemp').value, 10) || 10;
        const obs         = document.getElementById('cab_obs').value.trim();

        limparMarcasInvalidas();
        const faltando = [];
        if (!codparc)     { marcarCampoInvalido('cab_parcSearch');     faltando.push('Cliente'); }
        if (!codtipvenda) { marcarCampoInvalido('cab_tipvendaSearch'); faltando.push('Tipo de negociação'); }
        if (!dtneg)       { marcarCampoInvalido('cab_dtneg');          faltando.push('Data'); }
        if (faltando.length) {
            phToast(`Preencha: ${faltando.join(', ')}.`, 'warning');
            return;
        }

        const btn = document.getElementById('cabSave');
        btn.disabled = true;
        try {
            if (modoEdicaoCabecalho) {
                const nunotaAtual = parseInt(document.getElementById('cab_nunota').value, 10);
                if (!nunotaAtual) { phToast('NUNOTA ausente.', 'error'); return; }
                const res = await phPostJSON('/sankhya/venda/api/cabecalho/editar/',
                    { nunota: nunotaAtual, codemp, codparc, codtipvenda, dtneg, obs });
                if (!res.ok || !res.body?.ok) {
                    phToast(res.body?.error || 'Falha ao atualizar cabeçalho.', 'error');
                    return;
                }
                modoEdicaoCabecalho = false;
                // Atualiza cache do cabeçalho para o resumo
                const parc = document.getElementById('cab_parcSearch').value;
                const tipo = document.getElementById('cab_tipvendaSearch').value;
                cabecalhoAtual.cliente = parc.split(' — ').slice(1).join(' — ') || parc;
                cabecalhoAtual.tipo    = tipo.split(' — ').slice(1).join(' — ') || tipo;
                atualizarResumoModal();
                abrirItensAoLado();
                phToast(`Cabeçalho do pedido ${nunotaAtual} atualizado.`, 'success');
            } else {
                const res = await phPostJSON('/sankhya/venda/api/cabecalho/',
                    { codemp, codparc, codtipvenda, dtneg, obs });
                if (!res.ok || !res.body?.ok) {
                    phToast(res.body?.error || 'Falha ao criar pedido.', 'error');
                    return;
                }
                const nunota = res.body.nunota;
                document.getElementById('cab_nunota').value        = nunota;
                document.getElementById('items_nunota').value      = nunota;
                document.getElementById('items_nunota_display').textContent = nunota;
                itensAtuais = [];
                renderItensModal();
                // Atualiza cache do cabeçalho
                const parc = document.getElementById('cab_parcSearch').value;
                const tipo = document.getElementById('cab_tipvendaSearch').value;
                cabecalhoAtual = {
                    cliente: parc.split(' — ').slice(1).join(' — ') || parc,
                    tipo:    tipo.split(' — ').slice(1).join(' — ') || tipo,
                };
                atualizarResumoModal();
                itensInseridosCount = 0;
                limparCamposItem();
                abrirItensAoLado();
                setTimeout(() => document.getElementById('item_prod_vis')?.focus(), 160);
                phToast(`Pedido ${nunota} criado. Adicione os itens.`, 'success');
            }
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById('btnEditCab')?.addEventListener('click', () => {
        if (!modoEdicao) return;
        modoEdicaoCabecalho = true;
        if (cabItemsCard) cabItemsCard.style.left = '100%';
        setTimeout(() => { if (cabItemsModal) cabItemsModal.style.display = 'none'; }, 320);
        restaurarInputsCabecalho();
        limparMarcasInvalidas();
        setTimeout(() => document.getElementById('cab_parcSearch')?.focus(), 160);
    });

    function atualizarTotalItem() {
        const q = parseFloat(document.getElementById('item_qtd').value) || 0;
        const p = parseFloat(document.getElementById('item_preco').value) || 0;
        document.getElementById('item_total_venda').value = (q * p).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
    }
    document.getElementById('item_qtd')?.addEventListener('input', atualizarTotalItem);
    document.getElementById('item_preco')?.addEventListener('input', atualizarTotalItem);

    function limparCamposItem() {
        document.getElementById('item_prod_hidden').value = '';
        document.getElementById('item_prod_vis').value    = '';
        document.getElementById('item_lote').value        = '';
        document.getElementById('item_qtd').value         = '';
        document.getElementById('item_preco').value       = '';
        document.getElementById('item_total_venda').value = '';
    }

    document.getElementById('itemAddBtn')?.addEventListener('click', async () => {
        const nunota  = parseInt(document.getElementById('items_nunota').value, 10);
        const codprod = parseInt(document.getElementById('item_prod_hidden').value, 10);
        const qtdneg  = parseFloat(document.getElementById('item_qtd').value);
        const vlrunit = parseFloat(document.getElementById('item_preco').value) || 0;
        const codvol  = document.getElementById('item_codvol').value || 'CX';
        const lote    = document.getElementById('item_lote').value.trim() || null;

        if (!nunota)            { phToast('Pedido não identificado.', 'error'); return; }
        if (!codprod)           { phToast('Selecione um produto.', 'warning'); return; }
        if (!qtdneg || qtdneg <= 0) { phToast('Informe uma quantidade válida.', 'warning'); return; }

        const btn = document.getElementById('itemAddBtn');
        btn.disabled = true;
        try {
            // Modo edição — chama endpoint de update
            if (itemEditandoSeq > 0) {
                const res = await phPostJSON('/sankhya/venda/api/item/editar/', {
                    nunota, sequencia: itemEditandoSeq,
                    codprod, qtdneg, vlrunit, codvol, codagregacao: lote,
                });
                if (!res.ok || !res.body?.ok) {
                    phToast(res.body?.error || 'Falha ao atualizar item.', 'error');
                    return;
                }
                phToast(`Item ${itemEditandoSeq} atualizado.`, 'success');
                cancelarEdicaoItem();
                await recarregarItensDoPedido(nunota);
                return;
            }

            // Modo inserção — verifica duplicação preventiva (mesmo CODPROD + LOTE)
            const dupl = itensAtuais.find(it =>
                it.cod === codprod &&
                ((it.lote || '') === (lote || ''))
            );
            if (dupl) {
                const ok = await phConfirmar({
                    titulo:   'Produto já existe no pedido',
                    mensagem: `O produto <strong>${dupl.descr}</strong> com lote <strong>${dupl.lote || '(sem lote)'}</strong> já está no pedido (qtd ${dupl.qtd}). Deseja somar a nova quantidade ao item existente?`,
                    confirmarLabel: 'Somar quantidades',
                    cancelarLabel:  'Inserir como novo item',
                    tipo: 'aviso',
                });
                if (ok) {
                    // Atualiza o item existente (qtd + nova)
                    const novaQtd = (dupl.qtd || 0) + qtdneg;
                    const res2 = await phPostJSON('/sankhya/venda/api/item/editar/', {
                        nunota, sequencia: dupl.seq,
                        codprod, qtdneg: novaQtd,
                        vlrunit: (vlrunit || dupl.vlu || 0),
                        codvol, codagregacao: lote,
                    });
                    if (!res2.ok || !res2.body?.ok) {
                        phToast(res2.body?.error || 'Falha ao somar quantidades.', 'error');
                        return;
                    }
                    phToast(`Quantidade somada — total agora ${novaQtd.toLocaleString('pt-BR')}.`, 'success');
                    limparCamposItem();
                    document.getElementById('item_prod_vis')?.focus();
                    await recarregarItensDoPedido(nunota);
                    return;
                }
                // user disse "inserir como novo" — segue fluxo normal
            }

            const res = await phPostJSON('/sankhya/venda/api/item/', {
                nunota, codprod, qtdneg, vlrunit, codvol, codagregacao: lote,
            });
            if (!res.ok || !res.body?.ok) {
                phToast(res.body?.error || 'Falha ao adicionar item.', 'error');
                return;
            }
            itensInseridosCount++;
            limparCamposItem();
            document.getElementById('item_prod_vis')?.focus();
            phToast(`Item ${res.body.sequencia} adicionado.`, 'success');
            await recarregarItensDoPedido(nunota);
        } finally {
            btn.disabled = false;
        }
    });

    document.getElementById('itemEditCancel')?.addEventListener('click', cancelarEdicaoItem);

    // Atalho — Enter no formulário de item dispara salvar (exceto em dropdown aberto)
    cabItemsCard?.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        // Apenas se foco está em campo do formulário de item, não na tabela
        const dentroDoFormItem = e.target.closest('.flex.gap-8.align-end');
        if (!dentroDoFormItem) return;
        // Não dispara se um dropdown estiver aberto (typeahead consome Enter)
        const dropAberto = Array.from(cabItemsCard.querySelectorAll('.dropdown-abs'))
            .some(dd => dd.style.display === 'block');
        if (dropAberto) return;
        e.preventDefault();
        document.getElementById('itemAddBtn')?.click();
    });
    cabItemsCard?.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && itemEditandoSeq > 0) {
            e.preventDefault();
            cancelarEdicaoItem();
        }
    });

    document.getElementById('itemsSave')?.addEventListener('click', async () => {
        await fecharTudo();
        carregarVendas(false);
    });

    // ==========================================
    // 10. FATURAR PEDIDO (Fase 4.1+4.2)
    // ==========================================
    const faturarModal     = document.getElementById('faturarModal');
    const faturarNunotaEl  = document.getElementById('faturarNunota');
    const faturarValidEl   = document.getElementById('faturarValidacao');

    function abrirFaturarModal() {
        const nunota = parseInt(document.getElementById('items_nunota').value, 10);
        if (!nunota) return;
        // Validações cliente: tem itens? todos com lote?
        if (itensAtuais.length === 0) {
            phToast('Pedido sem itens — adicione ao menos um produto antes de faturar.', 'warning');
            return;
        }
        const semLote = itensAtuais.filter(it => !it.lote);
        faturarValidEl.classList.add('hidden');
        if (semLote.length > 0) {
            faturarValidEl.classList.remove('hidden');
            faturarValidEl.innerHTML = `
                <strong>⚠ Não é possível faturar este pedido ainda.</strong><br>
                ${semLote.length} ${semLote.length === 1 ? 'item está' : 'itens estão'} sem lote vinculado.
                Vincule os lotes pelo módulo <strong>Rastreio</strong> antes de faturar.`;
            const btnConf = document.getElementById('btnConfirmarFaturar');
            if (btnConf) btnConf.disabled = true;
        } else {
            const btnConf = document.getElementById('btnConfirmarFaturar');
            if (btnConf) btnConf.disabled = false;
        }
        faturarNunotaEl.textContent = nunota;
        faturarModal.classList.remove('hidden');
        faturarModal.style.display = 'flex';
        setTimeout(() => document.querySelector('input[name="faturarTop"]:checked')?.focus(), 50);
    }
    function fecharFaturarModal() {
        if (!faturarModal) return;
        faturarModal.classList.add('hidden');
        faturarModal.style.display = 'none';
    }

    document.getElementById('btnFaturar')?.addEventListener('click', abrirFaturarModal);
    document.getElementById('btnCancelarFaturar')?.addEventListener('click', fecharFaturarModal);
    faturarModal?.addEventListener('click', (e) => {
        if (e.target === faturarModal) fecharFaturarModal();
    });
    document.getElementById('btnConfirmarFaturar')?.addEventListener('click', async () => {
        const nunota = parseInt(document.getElementById('items_nunota').value, 10);
        const top = parseInt(document.querySelector('input[name="faturarTop"]:checked')?.value, 10);
        if (!nunota || !top) return;

        const ok = await phConfirmar({
            titulo:   'Confirmar faturamento?',
            mensagem: `Faturar o pedido <strong>${nunota}</strong> como <strong>TOP ${top}</strong>?<br>Após faturado, o pedido <strong>não pode ser editado</strong>.`,
            confirmarLabel: 'Faturar',
            tipo: 'aviso',
        });
        if (!ok) return;

        const btn = document.getElementById('btnConfirmarFaturar');
        btn.disabled = true;
        try {
            const res = await phPostJSON('/sankhya/venda/api/faturar/', { nunota, top });
            if (!res.ok || !res.body?.ok) {
                phToast(res.body?.error || 'Falha ao faturar pedido.', 'error');
                btn.disabled = false;
                return;
            }
            phToast(`Pedido ${nunota} faturado como TOP ${top}. Nº Nota: ${res.body.numnota || '—'}.`, 'success');
            fecharFaturarModal();
            await fecharTudo();
            carregarVendas(false);
        } catch (_) {
            phToast('Erro ao faturar pedido.', 'error');
            btn.disabled = false;
        }
    });

    // Inicia: tenta restaurar filtros do localStorage; se vier sem datas, aplica "hoje".
    const filtrosRestaurados = carregarFiltrosDoLocalStorage();
    if (!inputStart.value || !inputEnd.value) {
        inicializarDatas();
    } else if (filtrosRestaurados && inputStart.value !== inputEnd.value) {
        // Período manual restaurado: respeita o intervalo (não deixa setas << >> resincronizarem)
        dataFinalAlteradaManualmente = true;
    }
    carregarVendas(false);
});
