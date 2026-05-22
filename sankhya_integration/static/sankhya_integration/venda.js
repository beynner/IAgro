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
    // Lista canônica dos IDs de filtros — usada também pelo wireFilterAuto (Mai/2026)
    const IDS_FILTROS_VENDA = ['filtroTop', 'filtroPedido', 'filtroNF', 'filtroLote'];

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

    // Mai/2026 — listeners centralizados via IAgro.wireFilterAuto.
    // Debounce padrão 500ms (filtros de listagem pesados). Select dispara
    // change imediato. Datas têm lógica de sincronização própria (acima).
    IAgro.wireFilterAuto(IDS_FILTROS_VENDA, () => carregarVendas(false));

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
    // Mai/2026 — wrapper sobre IAgro.attachTypeahead.
    // Mantém assinatura legada (inpId, hidId, ddId, url, options). Default
    // onChange = recarregar lista. Debounce 400ms (consistente com o legado).
    function attachTA(inpId, hidId, ddId, url, options) {
        const onChangeCb = (options && typeof options.onChange === 'function')
            ? options.onChange
            : () => carregarVendas(false);
        return IAgro.attachTypeahead({
            inputId:    inpId,
            hiddenId:   hidId,
            dropdownId: ddId,
            url,
            limit:       (options && options.limit) || 10,
            debounceMs:  400,
            extraQuery:  options?.extraQuery,
            positionFixed: !!(options && options.positionFixed),
            pickCod:    (it) => it.cod ?? it.codparc,
            pickDescr:  (it) => it.descr ?? it.nomeparc ?? '',
            onSelect:   () => onChangeCb(),
            onClear:    () => onChangeCb(),
        });
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
            tbodyVendas.innerHTML = '<tr><td colspan="8" class="text-center ia-muted">Buscando no banco de dados...</td></tr>';
            document.getElementById('vendaItemsBody').innerHTML = '<tr><td colspan="4" class="ia-placeholder">Selecione uma venda</td></tr>';
            pedidoSelecionado = null;
            const btnDel = document.getElementById('btnDeleteVenda');
            if (btnDel) btnDel.disabled = true;
            // Mai/2026 — avaria/devolução exigem venda selecionada
            const btnAv  = document.getElementById('btnAvaria');
            const btnDev = document.getElementById('btnDevolucao');
            if (btnAv)  btnAv.disabled  = true;
            if (btnDev) btnDev.disabled = true;
            // B5 Mai/2026 — confirmar só pra TOP 34 ainda não confirmada
            const btnConf = document.getElementById('btnConfirmarVenda');
            if (btnConf) btnConf.disabled = true;
            const labelSel = document.getElementById('label_sel_nunota');
            if (labelSel) labelSel.textContent = '—';
            const subheader = document.getElementById('itensCardSubheader');
            if (subheader) subheader.textContent = '';
        } else {
            const trLoading = document.createElement('tr');
            trLoading.id = 'loading-row';
            trLoading.innerHTML = '<td colspan="8" class="text-center ia-muted">Carregando mais pedidos...</td>';
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
                const topLabel = topNum === 34 ? '34 - PDV' :
                                 topNum === 35 ? '35 - NFe' :
                                 topNum === 37 ? '37 - S/NFe' :
                                 topNum === 36 ? '36 - Dev' :
                                 topNum === 30 ? '30 - AVA' :
                                 String(topNum);
                const statusDot = `<span class="venda-status-dot venda-status-dot--${statusKey}" title="${statusTitulo}" aria-label="${statusTitulo}"></span>`;

                const obsTxt = (v.observacao || '').toString();
                const obsEscaped = obsTxt
                    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                const obsCell = obsTxt
                    ? `<span class="ia-truncate" title="${obsEscaped}">${obsEscaped}</span>`
                    : '<span class="ia-muted">—</span>';

                tr.innerHTML = `
                    <td>${statusDot}${v.nunota}</td>
                    <td>${v.numnota || '—'}</td>
                    <td>${v.emp}</td>
                    <td><span class="top-badge top-${topNum}">${topLabel}</span></td>
                    <td>${v.data ? v.data.substring(0,5) : ''}</td>
                    <td class="ia-truncate" title="${v.parceiro}">${v.parceiro}</td>
                    <td class="venda-obs-cell">${obsCell}</td>
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
                    pedidoSelecionado = {
                        nunota: v.nunota, top: topNum,
                        emp: v.emp, parceiro: v.parceiro,
                        numnota: v.numnota,
                    };
                    const btnDel = document.getElementById('btnDeleteVenda');
                    if (btnDel) btnDel.disabled = (topNum !== 34);  // só TOP 34 pode excluir
                    // Mai/2026 — avaria habilita pra qualquer TOP; devolução só pra venda faturada
                    const btnAv  = document.getElementById('btnAvaria');
                    const btnDev = document.getElementById('btnDevolucao');
                    if (btnAv)  btnAv.disabled  = false;
                    if (btnDev) btnDev.disabled = (topNum !== 35 && topNum !== 37);
                    // B5 Mai/2026 — confirmar habilita só pra TOP 34 STATUSNOTA != 'L'
                    const btnConf = document.getElementById('btnConfirmarVenda');
                    if (btnConf) btnConf.disabled = !(topNum === 34 && v.statusnota !== 'L');
                });
                // Double-click (mouse) + double-tap (touch) cross-device
                IAgro.onDoubleActivate(tr, function() {
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
            if (!append) tbodyVendas.innerHTML = `<tr><td colspan="8" class="text-center" style="color:#ef4444;">Erro: ${error.message}</td></tr>`;
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
            <tr><td colspan="8">
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
        IDS_FILTROS_VENDA.forEach(id => {
            const c = document.getElementById(id);
            if (c) c.value = c.tagName === 'SELECT' ? c.options[0].value : '';
        });
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
            const id = el.id || '';
            // `cabSave` fica fora da varredura: o próprio handler dele faz
            // disabled=true durante o salvamento e libera no `finally`. Se
            // entrasse aqui, o `dataset.wasDisabled='1'` (gravado enquanto
            // o handler ainda estava com disabled=true) faria o
            // `restaurarInputsCabecalho()` posterior travar o botão de
            // novo — fica latente até o próximo "Novo Pedido" abrir com
            // Salvar desativado. (Mai/2026 — 2026-05-20)
            if (id === 'cabSave') return;
            if (el.dataset.wasDisabled === undefined) {
                el.dataset.wasDisabled = el.disabled ? '1' : '0';
            }
            const preservar = id === 'cabCancel';
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
            '<tr><td colspan="7" class="ia-placeholder">Carregando itens...</td></tr>';
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
                codvol: it.codvol || 'KG',
            }));
            renderItensModal();
            atualizarResumoModal();
        } catch (e) {
            const tbody = document.getElementById('itemsListBody');
            tbody.innerHTML = `<tr><td colspan="7" class="ia-placeholder" style="color:#ef4444">Erro: ${e.message}</td></tr>`;
        }
    }

    function renderItensModal() {
        const tbody = document.getElementById('itemsListBody');
        const tfoot = document.getElementById('itemsListFoot');
        if (itensAtuais.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="ia-placeholder">Nenhum item inserido.</td></tr>';
            tfoot?.classList.add('hidden');
            return;
        }
        // Popula tfoot com totais (qtd com 2 decimais + separador milhar)
        if (tfoot) {
            const somaQtd = itensAtuais.reduce((s, it) => s + (it.qtd || 0), 0);
            const somaVlt = itensAtuais.reduce((s, it) => s + (it.vlt || 0), 0);
            document.getElementById('itemsTotalQtd').textContent =
                somaQtd.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            document.getElementById('itemsTotalValor').textContent =
                somaVlt.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            tfoot.classList.remove('hidden');
        }
        tbody.innerHTML = '';
        itensAtuais.forEach(item => {
            const qtd   = item.qtd.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            const preco = item.vlu.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            const total = item.vlt.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            const vol   = (item.codvol || '—').toString().toUpperCase();
            const tr = document.createElement('tr');
            tr.dataset.seq = item.seq;
            if (itemEditandoSeq === item.seq) tr.classList.add('selected');
            tr.innerHTML = `
                <td class="ia-truncate" title="${item.descr}">${item.descr}</td>
                <td>${item.lote || '—'}</td>
                <td class="text-center">${vol}</td>
                <td class="text-right">${qtd}</td>
                <td class="text-right">${preco}</td>
                <td class="text-right">${total}</td>
                <td class="text-center">
                    <button class="icon-btn-mini btn-edit-item" title="Editar item" data-seq="${item.seq}">
                        <i class="ph ph-pencil-simple" aria-hidden="true"></i>
                    </button>
                    <button class="icon-btn-mini btn-rm-item" title="Remover item" data-seq="${item.seq}">
                        <i class="ph ph-trash" aria-hidden="true"></i>
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
        document.getElementById('item_codvol').value      = item.codvol || 'KG';
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

    // B5 Mai/2026 (2026-05-22) — Confirmar pedido (STATUSNOTA → 'L').
    // Equivalente ao botão CONFIRMAR do Sankhya nativo. Passo obrigatório
    // antes do faturamento — sem CONFIRMAR, Sankhya bloqueia o atendimento.
    document.getElementById('btnConfirmarVenda')?.addEventListener('click', async () => {
        if (!pedidoSelecionado) return;
        if (pedidoSelecionado.top !== 34) {
            phToast('Apenas pedidos TOP 34 podem ser confirmados.', 'warning');
            return;
        }
        const ok = await phConfirmar({
            titulo:   'Confirmar pedido?',
            mensagem: `Confirmar o pedido <strong>${pedidoSelecionado.nunota}</strong>? Isso muda STATUSNOTA pra <strong>'L'</strong> (equivalente ao CONFIRMAR do Sankhya). Não cria financeiro nem NFe — esse é só o passo antes do faturamento.`,
            confirmarLabel: 'Confirmar',
            tipo: 'aviso',
        });
        if (!ok) return;

        const btn = document.getElementById('btnConfirmarVenda');
        btn.disabled = true; btn.classList.add('btn--loading');
        try {
            const res = await phPostJSON('/sankhya/venda/api/confirmar/', { nunota: pedidoSelecionado.nunota });
            if (res.ok && res.body?.ok) {
                phToast(`Pedido ${pedidoSelecionado.nunota} confirmado. Pode faturar no Sankhya agora.`, 'success');
                carregarVendas(false);
            } else {
                phToast(res.body?.error || 'Falha ao confirmar pedido.', 'error');
            }
        } catch (_) {
            phToast('Erro ao confirmar pedido.', 'error');
        } finally {
            btn.classList.remove('btn--loading');
            // O reload via carregarVendas vai re-habilitar/desabilitar conforme novo estado
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
    // Mai/2026 (2026-05-20) — Ao selecionar produto, puxa preço da tabela
    // do cliente (TGFPAR.CODTAB → TGFTAB.NUTAB ativa → TGFEXC.VLRVENDA).
    // Regra completa documentada em `.claude/tabela_precos_sankhya.md`.
    // Não sobrescreve se operador já digitou preço; silencioso se sem preço.
    // Estado da origem do preço do item em construção (Mai/2026 — 2026-05-20,
    // simplificado em 2026-05-21: chip MANUAL e campo de motivo removidos pra
    // desburocratizar — operador edita o preço livre = origem null = preço livre.
    // Backend só registra origem quando TABELA ou PROMOCAO foi aplicada via chip).
    const precoOrigemEstado = {
        origem: null,        // 'TABELA' | 'PROMOCAO' | null (livre)
        nutab: null,
        promocaoId: null,
        promocoes: [],       // todas vigentes pro par (codparc, codprod)
        tabelaPreco: null,   // preço da tabela
    };

    function resetarPrecoOrigem() {
        precoOrigemEstado.origem = null;
        precoOrigemEstado.nutab = null;
        precoOrigemEstado.promocaoId = null;
        precoOrigemEstado.promocoes = [];
        precoOrigemEstado.tabelaPreco = null;
        const bar = document.getElementById('precoOrigemBar');
        if (bar) bar.classList.add('hidden');
        document.querySelectorAll('.po-chip').forEach(c => c.classList.remove('is-active'));
    }

    function _fmtBRL(n) {
        return Number(n || 0).toFixed(2).replace('.', ',');
    }

    function aplicarChipOrigem(origem) {
        const inputPreco = document.getElementById('item_preco');
        if (!inputPreco) return;

        if (origem === 'TABELA' && precoOrigemEstado.tabelaPreco) {
            inputPreco.value = Number(precoOrigemEstado.tabelaPreco).toFixed(2);
            precoOrigemEstado.origem = 'TABELA';
            precoOrigemEstado.promocaoId = null;
        } else if (origem === 'PROMOCAO' && precoOrigemEstado.promocoes.length) {
            const promo = precoOrigemEstado.promocoes[0];  // mais recente
            inputPreco.value = Number(promo.vlrpromo).toFixed(2);
            precoOrigemEstado.origem = 'PROMOCAO';
            precoOrigemEstado.promocaoId = promo.id;
        }
        atualizarTotalItem();

        // Atualiza visual dos chips
        document.querySelectorAll('.po-chip').forEach(c => {
            c.classList.toggle('is-active', c.dataset.origem === precoOrigemEstado.origem);
        });
    }

    async function puxarPrecoTabela() {
        // Em modo edição, não pisa em preço já carregado da nota
        if (itemEditandoSeq > 0) return;

        const codparc = parseInt(document.getElementById('cab_codparc').value, 10);
        const codprod = parseInt(document.getElementById('item_prod_hidden').value, 10);
        if (!codparc || !codprod) {
            resetarPrecoOrigem();
            return;
        }

        const dtnegRaw = document.getElementById('cab_dtneg')?.value || '';
        let qsDtneg = '';
        if (/^\d{4}-\d{2}-\d{2}$/.test(dtnegRaw)) {
            const [y, m, d] = dtnegRaw.split('-');
            qsDtneg = `&dtneg=${d}/${m}/${y}`;
        }

        // Reset estado antes da nova busca
        resetarPrecoOrigem();

        try {
            const [resTab, resPromo] = await Promise.all([
                fetch(`/sankhya/venda/api/preco-tabela/?codparc=${codparc}&codprod=${codprod}${qsDtneg}`).then(r => r.json()),
                fetch(`/sankhya/venda/api/promocoes/vigentes/?codparc=${codparc}&codprod=${codprod}${qsDtneg}`).then(r => r.json()),
            ]);

            // Tabela
            if (resTab && resTab.ok && resTab.preco != null && resTab.preco > 0) {
                precoOrigemEstado.tabelaPreco = Number(resTab.preco);
                precoOrigemEstado.nutab = resTab.nutab || null;
            }
            // Promoções
            if (resPromo && resPromo.ok && Array.isArray(resPromo.promocoes)) {
                precoOrigemEstado.promocoes = resPromo.promocoes;
            }

            // Atualiza chips
            const bar = document.getElementById('precoOrigemBar');
            const chipTab = document.querySelector('.po-chip[data-origem="TABELA"]');
            const chipPromo = document.querySelector('.po-chip[data-origem="PROMOCAO"]');
            const valTab = document.getElementById('poChipTabelaValor');
            const valPromo = document.getElementById('poChipPromoValor');
            const extraPromo = document.getElementById('poChipPromoExtra');

            if (precoOrigemEstado.tabelaPreco) {
                if (valTab) valTab.textContent = `R$ ${_fmtBRL(precoOrigemEstado.tabelaPreco)}`;
                if (chipTab) chipTab.disabled = false;
            } else {
                if (valTab) valTab.textContent = '—';
                if (chipTab) chipTab.disabled = true;
            }
            if (precoOrigemEstado.promocoes.length) {
                const p = precoOrigemEstado.promocoes[0];
                if (valPromo) valPromo.textContent = `R$ ${_fmtBRL(p.vlrpromo)}`;
                if (extraPromo) {
                    const escopoTxt = p.escopo === 'TABELA' ? `Tabela ${p.codtab}` : 'só este cliente';
                    const dt = (p.dt_fim || '').split('-').reverse().join('/');
                    extraPromo.textContent = `(${escopoTxt} · até ${dt})`;
                }
                if (chipPromo) chipPromo.disabled = false;
            } else {
                if (valPromo) valPromo.textContent = '—';
                if (extraPromo) extraPromo.textContent = '';
                if (chipPromo) chipPromo.disabled = true;
            }
            if (bar) bar.classList.remove('hidden');

            // Aplica automaticamente o melhor preço (promoção tem prioridade visual,
            // tabela como fallback). Sem preço cadastrado: chips ficam disabled,
            // operador digita preço livre — preco_origem fica null, backend não
            // registra origem (livre, sem burocracia).
            const inputPreco = document.getElementById('item_preco');
            if (inputPreco && !(parseFloat(inputPreco.value) > 0)) {
                if (precoOrigemEstado.promocoes.length) {
                    aplicarChipOrigem('PROMOCAO');
                    const p = precoOrigemEstado.promocoes[0];
                    phToast(`🎁 Promoção R$ ${_fmtBRL(p.vlrpromo)} aplicada`, 'success');
                } else if (precoOrigemEstado.tabelaPreco) {
                    aplicarChipOrigem('TABELA');
                    const sufx = precoOrigemEstado.nutab ? ` (Tabela ${precoOrigemEstado.nutab})` : '';
                    phToast(`Preço R$ ${_fmtBRL(precoOrigemEstado.tabelaPreco)}${sufx}`, 'success');
                }
                // Sem tabela e sem promoção: bar continua visível (chips disabled),
                // operador digita preço livre. Sem toast obtrusivo.
            }
        } catch (e) {
            console.error('puxarPrecoTabela falhou', e);
            phToast('Erro ao consultar tabela de preços (rede/back).', 'error');
        }
    }

    // Listeners dos chips (apenas TABELA e PROMOCAO desde 2026-05-21)
    document.querySelectorAll('.po-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if (chip.disabled) return;
            aplicarChipOrigem(chip.dataset.origem);
        });
    });

    // Quando operador edita o preço manualmente, desativa o chip ativo
    // (origem fica null = preço livre, sem registrar nada no backend)
    document.getElementById('item_preco')?.addEventListener('input', () => {
        if (!precoOrigemEstado.origem) return;
        const precoAtual = parseFloat(document.getElementById('item_preco').value);
        const ehTabela   = precoOrigemEstado.tabelaPreco
            && Math.abs(precoAtual - precoOrigemEstado.tabelaPreco) < 0.001;
        const ehPromocao = precoOrigemEstado.promocoes[0]
            && Math.abs(precoAtual - Number(precoOrigemEstado.promocoes[0].vlrpromo)) < 0.001;
        if (!ehTabela && !ehPromocao) {
            precoOrigemEstado.origem = null;
            precoOrigemEstado.promocaoId = null;
            document.querySelectorAll('.po-chip').forEach(c => c.classList.remove('is-active'));
        }
    });

    attachTA('item_prod_vis', 'item_prod_hidden', 'item_prod_sugg', '/sankhya/produtos/search/',
             { limit: 15, extraQuery: 'grupo_inicia_com=1', onChange: puxarPrecoTabela });

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

    // Botão "Importar pedidos" — abre a tela de importação em aba nova.
    // O `window.open` retorna referência mesmo pra tab; usamos polling de
    // `closed` pra recarregar a lista de Vendas quando a aba é fechada
    // (reflete pedidos confirmados em TGFCAB durante a sessão).
    document.getElementById('btnImportarPedidos')?.addEventListener('click', () => {
        const aba = window.open('/sankhya/venda/email-importar/', '_blank');
        if (!aba) {
            // Bloqueador de pop-up ativo — fallback navega na mesma aba.
            window.location.href = '/sankhya/venda/email-importar/';
            return;
        }
        const _pollImportar = setInterval(() => {
            if (aba.closed) {
                clearInterval(_pollImportar);
                carregarVendas(false);
            }
        }, 500);
    });

    // ==========================================================================
    // AVARIA (TOP 30) + DEVOLUÇÃO (TOP 36) + HISTÓRICO DE LOTE — Mai/2026
    // ==========================================================================

    function _fmtNum(v, casas = 3) {
        const n = Number(v || 0);
        return n.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
    }
    function _fmtBRL(v) {
        const n = Number(v || 0);
        return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }
    function _hoje() {
        const d = new Date();
        const yy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yy}-${mm}-${dd}`;
    }

    function _abrirModal(id) {
        const m = document.getElementById(id);
        if (!m) return;
        m.classList.remove('hidden');
        m.style.display = 'flex';
    }
    function _fecharModal(id) {
        const m = document.getElementById(id);
        if (!m) return;
        m.classList.add('hidden');
        m.style.display = '';
    }

    // --------------------------------------------------------------------------
    // AVARIA — typeahead de lote pela view do WMS (Mai/2026: helper central)
    // Usa endpoint diferente (rastreio/lotes-disponiveis) e injeta extras
    // (codprod/codemp/saldo/fornecedor) via pickExtra — lidos no onSelect.
    // --------------------------------------------------------------------------
    IAgro.attachTypeahead({
        inputId:    'avaria_lote_search',
        hiddenId:   'avaria_codagregacao',
        dropdownId: 'avaria_lote_dropdown',
        url:        '/sankhya/rastreio/api/lotes-disponiveis/',
        limit:      15,
        debounceMs: 350,
        extraQuery: 'tipo=todos',
        pickItems:  (data) => data.lotes || [],
        pickCod:    (r) => r.codagregacao,
        pickDescr:  (r) => r.descrprod || '',
        pickExtra:  (r) => ({
            prod:     r.codprod,
            emp:      r.codemp,
            saldo:    r.qtd_disponivel || 0,
            vendedor: r.nomeparc_origem || '',
        }),
        renderItem: (r) =>
            `${r.codagregacao} — ${(r.descrprod || '').substring(0, 30)} · ${_fmtNum(r.qtd_disponivel)}`,
        onSelect: (_cod, _descr, item) => {
            document.getElementById('avaria_codprod').value     = item.dataset.prod;
            document.getElementById('avaria_codemp').value      = item.dataset.emp;
            document.getElementById('avaria_lote_produto').textContent    = item.dataset.descr || '—';
            document.getElementById('avaria_lote_fornecedor').textContent = item.dataset.vendedor || '—';
            document.getElementById('avaria_lote_saldo').textContent      = `${_fmtNum(item.dataset.saldo)} (mesma unidade)`;
            document.getElementById('avaria_lote_info').classList.remove('hidden');
        },
    });

    // Typeahead de parceiro no modal de avaria (reusa endpoint da Venda)
    attachTA('avaria_parcSearch', 'avaria_codparc', 'avaria_parcDropdown',
             '/sankhya/parceiros/search/', { limit: 15, onChange: () => {} });

    async function abrirModalAvaria() {
        if (!pedidoSelecionado) {
            phToast('Selecione uma venda na listagem primeiro', 'error');
            return;
        }

        // reset
        document.getElementById('avaria_lote_search').value = '';
        document.getElementById('avaria_codagregacao').value = '';
        document.getElementById('avaria_codprod').value = '';
        document.getElementById('avaria_codemp').value = '';
        document.getElementById('avaria_lote_info').classList.add('hidden');
        document.getElementById('avaria_parcSearch').value = '';
        document.getElementById('avaria_codparc').value = '';
        document.getElementById('avaria_numnota_ref').value = pedidoSelecionado.numnota || '';
        document.getElementById('avaria_qtdneg').value = '';
        document.getElementById('avaria_codvol').value = 'KG';
        document.getElementById('avaria_vlrunit').value = '';
        document.getElementById('avaria_dtneg').value = _hoje();
        document.getElementById('avaria_observacao').value = '';

        // Pré-popula cliente + empresa a partir do cabeçalho da venda selecionada
        try {
            const r = await fetch(`/sankhya/venda/api/cabecalho/obter/?nunota=${pedidoSelecionado.nunota}`);
            const d = await r.json();
            if (d.ok) {
                if (d.codparc) {
                    document.getElementById('avaria_codparc').value = d.codparc;
                    document.getElementById('avaria_parcSearch').value =
                        `${d.codparc} — ${d.nome_parc || pedidoSelecionado.parceiro || ''}`;
                }
                if (d.codemp) {
                    document.getElementById('avaria_codemp').value = d.codemp;
                }
            }
        } catch (_) { /* segue sem pré-população — operador preenche manualmente */ }

        _abrirModal('avariaModal');
    }

    document.getElementById('btnAvaria')?.addEventListener('click', abrirModalAvaria);
    document.getElementById('avariaCancelBtn')?.addEventListener('click', () => _fecharModal('avariaModal'));

    // --------------------------------------------------------------------------
    // B2 Mai/2026 — Avaria "a partir de nota" (TGFVAR inverso)
    // --------------------------------------------------------------------------
    let _avnNotaCarregada = null;
    let _avnSeqSelecionada = null;

    // Toggle entre modo AVULSO e modo NOTA
    document.querySelectorAll('input[name="av_modo"]').forEach(radio => {
        radio.addEventListener('change', (ev) => {
            const modo = ev.target.value;
            const ehNota = modo === 'NOTA';
            document.getElementById('avariaModoAvulso')?.classList.toggle('hidden', ehNota);
            document.getElementById('avariaModoNota')?.classList.toggle('hidden', !ehNota);
            // Quantidade única só faz sentido no modo AVULSO (no modo NOTA
            // a qtd vem das sub-linhas de lote)
            document.getElementById('avaria_qtd_wrap')?.classList.toggle('hidden', ehNota);
        });
    });

    // Carregar itens da nota — reusa endpoint da devolução
    document.getElementById('avn_btnCarregar')?.addEventListener('click', async () => {
        const nunota = parseInt(document.getElementById('avn_nunota_nota').value, 10);
        if (!nunota) { phToast('Informe o NUNOTA da nota', 'error'); return; }

        const btn = document.getElementById('avn_btnCarregar');
        btn.disabled = true; btn.textContent = 'Carregando...';
        try {
            const r = await fetch(`/sankhya/venda/api/devolucao/preparar/?nunota=${nunota}`);
            const d = await r.json();
            if (!r.ok || !d.ok) {
                phToast(d.error || 'Falha ao carregar nota', 'error');
                document.getElementById('avn_nota_info').classList.add('hidden');
                document.getElementById('avn_itens_wrap').classList.add('hidden');
                return;
            }

            _avnNotaCarregada = d;
            _avnSeqSelecionada = null;
            const cab = d.cabecalho;
            document.getElementById('avn_nota_cliente').textContent = cab.nomeparc || `CODPARC ${cab.codparc}`;
            document.getElementById('avn_nota_data').textContent = cab.dtneg || '—';
            document.getElementById('avn_nota_numnota').textContent = cab.numnota || '—';
            document.getElementById('avn_nota_info').classList.remove('hidden');

            // Auto-popula codemp + codparc do header (não precisa o operador refazer)
            document.getElementById('avaria_codemp').value = cab.codemp;
            document.getElementById('avaria_codparc').value = cab.codparc;
            const parcInp = document.getElementById('avaria_parcSearch');
            if (parcInp && cab.nomeparc) {
                parcInp.value = `${cab.codparc} — ${cab.nomeparc}`;
            }

            const body = document.getElementById('avn_itens_body');
            if (!d.itens.length) {
                body.innerHTML = '<tr><td colspan="5" class="ia-placeholder">Nota sem itens.</td></tr>';
            } else {
                body.innerHTML = d.itens.map(it => {
                    const lotesOrigem = Array.isArray(it.lotes_origem) ? it.lotes_origem : [];
                    const ehSplit = lotesOrigem.length >= 2;
                    let celulaLote;
                    if (ehSplit) {
                        const resumo = lotesOrigem
                            .map(l => `${l.codagregacao || '(sem lote)'} · ${_fmtNum(l.qtd_atendida, 2)} ${it.codvol}`)
                            .join('\n');
                        celulaLote = `<span class="dev-lotes-multi" title="Pedido origem dividido em ${lotesOrigem.length} lotes (SPLIT):\n${resumo}">${lotesOrigem.length} lotes ⚡</span>`;
                    } else if (lotesOrigem.length === 1 && lotesOrigem[0].codagregacao) {
                        celulaLote = lotesOrigem[0].codagregacao;
                    } else {
                        celulaLote = it.codagregacao || '—';
                    }

                    // Sub-linha com tabela editável (sempre — modo NOTA sempre
                    // divide por lote, mesmo com 1 lote único)
                    const linhasLote = (lotesOrigem.length ? lotesOrigem : [{
                        codagregacao: it.codagregacao || '',
                        qtd_atendida: it.qtdneg,
                    }]).map(l => {
                        const cod = l.codagregacao || '';
                        const atend = l.qtd_atendida || 0;
                        return `
                            <tr data-cod="${cod}">
                                <td class="dev-split-lote">${cod || '(sem lote)'}</td>
                                <td class="text-right">${_fmtNum(atend, 2)} ${it.codvol}</td>
                                <td>
                                    <input type="number" step="0.01" min="0" max="${atend}"
                                           class="avn-lote-qtd"
                                           data-cod="${cod}"
                                           data-atendido="${atend}"
                                           placeholder="0,00">
                                </td>
                            </tr>
                        `;
                    }).join('');

                    return `
                        <tr data-seq="${it.sequencia}"
                            data-codprod="${it.codprod}"
                            data-codvol="${it.codvol}"
                            data-max="${it.qtdneg}">
                            <td class="text-center">
                                <input type="radio" name="avn_item_sel" class="avn-radio" value="${it.sequencia}">
                            </td>
                            <td>${it.codprod} · ${(it.descrprod || '').substring(0, 35)}</td>
                            <td>${celulaLote}</td>
                            <td class="text-right">${_fmtNum(it.qtdneg, 2)}</td>
                            <td>
                                <div class="dev-qtd-resumo">
                                    <strong class="avn-qtd-total" data-max="${it.qtdneg}">0,00</strong>
                                    <span class="dev-qtd-tag">de ${_fmtNum(it.qtdneg, 2)}</span>
                                </div>
                            </td>
                        </tr>
                        <tr class="dev-split-row hidden" data-parent-seq="${it.sequencia}">
                            <td colspan="5">
                                <div class="dev-split-wrap">
                                    <div class="dev-split-titulo">Dividir entre lotes do pedido origem</div>
                                    <table class="dev-split-tabela">
                                        <thead>
                                            <tr>
                                                <th>Lote</th>
                                                <th class="text-right">Atendido</th>
                                                <th>Qtd avariada</th>
                                            </tr>
                                        </thead>
                                        <tbody>${linhasLote}</tbody>
                                    </table>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');
            }
            document.getElementById('avn_itens_wrap').classList.remove('hidden');
        } catch (e) {
            phToast('Erro de comunicação ao carregar nota', 'error');
        } finally {
            btn.disabled = false; btn.textContent = 'Carregar Itens';
        }
    });

    // Quando o operador escolhe 1 item (radio), revela sub-tabela do lote
    document.getElementById('avn_itens_body')?.addEventListener('change', (ev) => {
        if (!ev.target.classList.contains('avn-radio')) return;
        const seqEscolhida = ev.target.value;
        _avnSeqSelecionada = parseInt(seqEscolhida, 10);

        // Esconde todas as sub-linhas e mostra só a do item escolhido
        document.querySelectorAll('#avn_itens_body tr.dev-split-row').forEach(tr => {
            const parentSeq = tr.dataset.parentSeq;
            const ehEscolhido = parentSeq === seqEscolhida;
            tr.classList.toggle('hidden', !ehEscolhido);
            if (!ehEscolhido) {
                // Limpa inputs das sub-linhas não-selecionadas
                tr.querySelectorAll('.avn-lote-qtd').forEach(inp => { inp.value = ''; });
            }
        });
        _avnRecalcularTotal(_avnSeqSelecionada);
    });

    function _avnRecalcularTotal(seq) {
        if (!seq) return;
        const body = document.getElementById('avn_itens_body');
        const parent = body?.querySelector(`tr[data-seq="${seq}"]`);
        const splitRow = body?.querySelector(`tr.dev-split-row[data-parent-seq="${seq}"]`);
        if (!parent || !splitRow) return;
        const inputs = splitRow.querySelectorAll('.avn-lote-qtd');
        let soma = 0;
        inputs.forEach(inp => {
            const v = parseFloat(inp.value);
            if (!isNaN(v) && v > 0) soma += v;
        });
        const totalEl = parent.querySelector('.avn-qtd-total');
        if (totalEl) {
            totalEl.textContent = _fmtNum(soma, 2);
            const max = parseFloat(parent.dataset.max);
            totalEl.classList.toggle('dev-qtd-total--excede', soma > max + 1e-6);
        }
    }

    document.getElementById('avn_itens_body')?.addEventListener('input', (ev) => {
        if (!ev.target.classList.contains('avn-lote-qtd')) return;
        const splitRow = ev.target.closest('tr.dev-split-row');
        const parentSeq = splitRow?.dataset.parentSeq;
        if (parentSeq) _avnRecalcularTotal(parentSeq);
    });

    // Clamp automático no blur (avaria modo NOTA) — espelha a regra da devolução
    document.getElementById('avn_itens_body')?.addEventListener('blur', (ev) => {
        const t = ev.target;
        if (!t.classList?.contains('avn-lote-qtd')) return;
        const max = parseFloat(t.dataset.atendido);
        const v = parseFloat(t.value);
        if (!isNaN(max) && !isNaN(v) && v > max + 1e-6) {
            t.value = max.toFixed(2);
            phToast(`Ajustado pro máximo do lote: ${_fmtNum(max, 2)}`, 'info');
            t.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }, true);

    // Reset state ao reabrir o modal de avaria
    document.getElementById('btnAvaria')?.addEventListener('click', () => {
        _avnNotaCarregada = null;
        _avnSeqSelecionada = null;
        document.querySelector('input[name="av_modo"][value="AVULSO"]').checked = true;
        document.getElementById('avariaModoAvulso')?.classList.remove('hidden');
        document.getElementById('avariaModoNota')?.classList.add('hidden');
        document.getElementById('avaria_qtd_wrap')?.classList.remove('hidden');
        document.getElementById('avn_nota_info')?.classList.add('hidden');
        document.getElementById('avn_itens_wrap')?.classList.add('hidden');
        const nunInp = document.getElementById('avn_nunota_nota'); if (nunInp) nunInp.value = '';
    });

    document.getElementById('avariaConfirmBtn')?.addEventListener('click', async () => {
        const modo = document.querySelector('input[name="av_modo"]:checked')?.value || 'AVULSO';
        const codemp       = parseInt(document.getElementById('avaria_codemp').value, 10);
        const codparc      = parseInt(document.getElementById('avaria_codparc').value, 10);
        const codvol       = document.getElementById('avaria_codvol').value || 'KG';
        const vlrunitRaw   = document.getElementById('avaria_vlrunit').value;
        const vlrunit      = vlrunitRaw ? parseFloat(vlrunitRaw) : 0;
        const numnota_ref  = document.getElementById('avaria_numnota_ref').value.trim();
        const observacao   = document.getElementById('avaria_observacao').value.trim() || 'AVARIA';
        const dtnegISO     = document.getElementById('avaria_dtneg').value;
        const dtneg = dtnegISO ? dtnegISO.split('-').reverse().join('/') : null;

        // Validações comuns
        const erros = [];
        if (!codemp)  erros.push('Empresa não detectada');
        if (!codparc) erros.push('Selecione o cliente/parceiro');

        let payload;
        if (modo === 'AVULSO') {
            const codagregacao = document.getElementById('avaria_codagregacao').value.trim();
            const codprod      = parseInt(document.getElementById('avaria_codprod').value, 10);
            const qtdneg       = parseFloat(document.getElementById('avaria_qtdneg').value);
            if (!codagregacao) erros.push('Selecione um lote');
            if (!codprod)      erros.push('Lote sem produto associado');
            if (!qtdneg || qtdneg <= 0) erros.push('Quantidade obrigatória');
            if (erros.length) { phToast(erros.join(' · '), 'error'); return; }

            payload = {
                codemp, codparc, codagregacao, codprod, qtdneg,
                codvol, vlrunit, numnota_ref, observacao, dtneg,
            };
        } else {
            // Modo NOTA — coleta lotes da sub-linha selecionada
            if (!_avnNotaCarregada) erros.push('Carregue a nota primeiro');
            if (!_avnSeqSelecionada) erros.push('Marque o item da nota');
            if (erros.length) { phToast(erros.join(' · '), 'error'); return; }

            const parent = document.querySelector(`#avn_itens_body tr[data-seq="${_avnSeqSelecionada}"]`);
            const splitRow = document.querySelector(`#avn_itens_body tr.dev-split-row[data-parent-seq="${_avnSeqSelecionada}"]`);
            const codprod = parseInt(parent?.dataset.codprod, 10);
            const codvolItem = parent?.dataset.codvol || codvol;
            const maxItem = parseFloat(parent?.dataset.max);

            const inputs = Array.from(splitRow?.querySelectorAll('.avn-lote-qtd') || []);
            const lotes = [];
            let soma = 0;
            for (const inp of inputs) {
                const qtd = parseFloat(inp.value);
                if (!qtd || qtd <= 0) continue;
                const cod = inp.dataset.cod;
                const atend = parseFloat(inp.dataset.atendido) || 0;
                if (!cod) { phToast('Item sem CODAGREGACAO rastreável — use modo avulso', 'error'); return; }
                if (qtd > atend + 1e-6) {
                    phToast(`Lote ${cod}: qtd ${_fmtNum(qtd, 2)} excede atendido ${_fmtNum(atend, 2)}`, 'error');
                    return;
                }
                soma += qtd;
                lotes.push({ codagregacao: cod, qtd });
            }
            if (!lotes.length) { phToast('Informe quantidade em pelo menos 1 lote', 'error'); return; }
            if (soma > maxItem + 1e-6) {
                phToast(`Soma dos lotes (${_fmtNum(soma, 2)}) excede vendido (${_fmtNum(maxItem, 2)})`, 'error');
                return;
            }

            payload = {
                codemp, codparc, codprod,
                codvol: codvolItem, vlrunit, numnota_ref, observacao, dtneg,
                nunota_origem_nota: _avnNotaCarregada.cabecalho.nunota,
                sequencia_nota: _avnSeqSelecionada,
                lotes_avaria: lotes,
            };
        }

        const ok = await phConfirmar({
            titulo: 'Registrar avaria interna?',
            mensagem: modo === 'AVULSO'
                ? `Lote ${payload.codagregacao} · ${_fmtNum(payload.qtdneg)} ${payload.codvol}. Saldo do lote será descontado.`
                : `${payload.lotes_avaria.length} lote(s) da nota ${payload.nunota_origem_nota}. Saldo de cada lote será descontado.`,
            tipo: 'aviso',
        });
        if (!ok) return;

        const btn = document.getElementById('avariaConfirmBtn');
        btn.disabled = true; btn.classList.add('btn--loading');
        try {
            const res = await phPostJSON('/sankhya/venda/api/avaria/criar/', payload);
            if (!res.ok || !res.body?.ok) {
                phToast(res.body?.error || 'Falha ao registrar avaria', 'error');
                return;
            }
            const resumo = modo === 'AVULSO'
                ? `${_fmtNum(payload.qtdneg)} ${payload.codvol}`
                : `${payload.lotes_avaria.length} lote(s)`;
            phToast(`Avaria registrada · NUNOTA ${res.body.nunota} · ${resumo}`, 'success');
            _fecharModal('avariaModal');
            carregarVendas(false);
        } catch (e) {
            phToast('Erro de comunicação. Tente novamente.', 'error');
        } finally {
            btn.disabled = false; btn.classList.remove('btn--loading');
        }
    });

    // --------------------------------------------------------------------------
    // DEVOLUÇÃO — carrega itens da nota origem, monta tabela, valida qtd
    // --------------------------------------------------------------------------
    let _devNotaCarregada = null;

    function abrirModalDevolucao() {
        if (!pedidoSelecionado) {
            phToast('Selecione uma venda faturada (TOP 35/37) na listagem primeiro', 'error');
            return;
        }
        if (pedidoSelecionado.top !== 35 && pedidoSelecionado.top !== 37) {
            phToast('Devolução só de notas faturadas (TOP 35 ou 37)', 'error');
            return;
        }

        document.getElementById('dev_nunota_origem').value = pedidoSelecionado.nunota;
        document.getElementById('dev_nota_info').classList.add('hidden');
        document.getElementById('dev_itens_wrap').classList.add('hidden');
        document.getElementById('dev_itens_body').innerHTML =
            '<tr><td colspan="8" class="ia-placeholder">Carregando itens...</td></tr>';
        document.getElementById('dev_dtneg').value = _hoje();
        document.getElementById('dev_observacao').value = '';
        _devNotaCarregada = null;
        _abrirModal('devolucaoModal');

        // Auto-dispara o carregamento dos itens já que a nota foi pré-selecionada
        document.getElementById('dev_btnCarregar')?.click();
    }

    document.getElementById('btnDevolucao')?.addEventListener('click', abrirModalDevolucao);
    document.getElementById('devCancelBtn')?.addEventListener('click', () => _fecharModal('devolucaoModal'));

    document.getElementById('dev_btnCarregar')?.addEventListener('click', async () => {
        const nunota = parseInt(document.getElementById('dev_nunota_origem').value, 10);
        if (!nunota) { phToast('Informe o NUNOTA da nota', 'error'); return; }

        const btn = document.getElementById('dev_btnCarregar');
        btn.disabled = true; btn.textContent = 'Carregando...';
        try {
            const r = await fetch(`/sankhya/venda/api/devolucao/preparar/?nunota=${nunota}`);
            const d = await r.json();
            if (!r.ok || !d.ok) {
                phToast(d.error || 'Falha ao carregar nota', 'error');
                document.getElementById('dev_nota_info').classList.add('hidden');
                document.getElementById('dev_itens_wrap').classList.add('hidden');
                return;
            }

            _devNotaCarregada = d;
            const cab = d.cabecalho;
            document.getElementById('dev_nota_cliente').textContent = cab.nomeparc || `CODPARC ${cab.codparc}`;
            document.getElementById('dev_nota_data').textContent = cab.dtneg || '—';
            document.getElementById('dev_nota_total').textContent = _fmtBRL(cab.vlrnota);
            document.getElementById('dev_nota_numnota').textContent = cab.numnota || '—';
            document.getElementById('dev_nota_info').classList.remove('hidden');

            const body = document.getElementById('dev_itens_body');
            if (!d.itens.length) {
                body.innerHTML = '<tr><td colspan="7" class="ia-placeholder">Nota sem itens.</td></tr>';
            } else {
                body.innerHTML = d.itens.map(it => {
                    const sem_saldo = it.qtd_devolvivel <= 0;
                    const lotesOrigem = Array.isArray(it.lotes_origem) ? it.lotes_origem : [];
                    // Mai/2026 — Fase 2: navegação inversa TGFVAR + divisão editável
                    // 1 lote (ou nenhum): coluna mostra o lote da nota e input simples de qtd
                    // 2+ lotes: badge `N lotes ⚡` + sub-tabela editável com sugestão proporcional
                    const ehSplit = lotesOrigem.length >= 2;
                    let celulaLote;
                    if (ehSplit) {
                        const resumo = lotesOrigem
                            .map(l => `${l.codagregacao || '(sem lote)'} · ${_fmtNum(l.qtd_atendida, 2)} ${it.codvol}`)
                            .join('\n');
                        celulaLote = `<span class="dev-lotes-multi" title="Pedido origem dividido em ${lotesOrigem.length} lotes (SPLIT):\n${resumo}">${lotesOrigem.length} lotes ⚡</span>`;
                    } else if (lotesOrigem.length === 1 && lotesOrigem[0].codagregacao) {
                        celulaLote = lotesOrigem[0].codagregacao;
                    } else {
                        celulaLote = it.codagregacao || '—';
                    }

                    const colVol = it.codvol;
                    const colDevolvivel = it.qtd_devolvivel;

                    let celulaQtd;
                    if (ehSplit) {
                        celulaQtd = `
                            <div class="dev-qtd-resumo">
                                <strong class="dev-qtd-total" data-max="${colDevolvivel}">0,00</strong>
                                <span class="dev-qtd-tag">de ${_fmtNum(colDevolvivel, 2)}</span>
                            </div>
                        `;
                    } else {
                        celulaQtd = `
                            <input type="number" step="0.01" min="0" max="${colDevolvivel}"
                                   class="dev-qtd full-width" placeholder="0,00"
                                   ${sem_saldo ? 'disabled' : ''}>
                        `;
                    }

                    // Sub-linha com sub-tabela editável (só pra split)
                    let linhaSplit = '';
                    if (ehSplit) {
                        const linhasLote = lotesOrigem.map(l => {
                            const cod = l.codagregacao || '';
                            const atend = l.qtd_atendida || 0;
                            return `
                                <tr data-cod="${cod}">
                                    <td class="dev-split-lote">${cod}</td>
                                    <td class="text-right">${_fmtNum(atend, 2)} ${colVol}</td>
                                    <td>
                                        <input type="number" step="0.01" min="0" max="${atend}"
                                               class="dev-split-qtd"
                                               data-cod="${cod}"
                                               data-atendido="${atend}"
                                               placeholder="0,00"
                                               ${sem_saldo ? 'disabled' : ''}>
                                    </td>
                                </tr>
                            `;
                        }).join('');
                        linhaSplit = `
                            <tr class="dev-split-row hidden" data-parent-seq="${it.sequencia}">
                                <td colspan="7">
                                    <div class="dev-split-wrap">
                                        <div class="dev-split-titulo">Dividir entre lotes do pedido origem (SPLIT)</div>
                                        <table class="dev-split-tabela">
                                            <thead>
                                                <tr>
                                                    <th>Lote</th>
                                                    <th class="text-right">Atendido</th>
                                                    <th>Qtd devolver</th>
                                                </tr>
                                            </thead>
                                            <tbody>${linhasLote}</tbody>
                                        </table>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }

                    return `
                        <tr data-seq="${it.sequencia}" data-max="${colDevolvivel}"
                            data-split="${ehSplit ? '1' : '0'}"
                            class="${sem_saldo ? 'dev-item-zerado' : ''}">
                            <td class="text-center">
                                <input type="checkbox" class="dev-chk" ${sem_saldo ? 'disabled' : ''}>
                            </td>
                            <td>${it.codprod} · ${(it.descrprod || '').substring(0, 35)}</td>
                            <td>${celulaLote}</td>
                            <td class="text-right">${_fmtNum(it.qtdneg, 2)}</td>
                            <td class="text-right">${_fmtNum(it.qtd_ja_devolvida, 2)}</td>
                            <td class="text-right"><strong>${_fmtNum(colDevolvivel, 2)}</strong></td>
                            <td>${celulaQtd}</td>
                        </tr>
                        ${linhaSplit}
                    `;
                }).join('');
            }
            document.getElementById('dev_itens_wrap').classList.remove('hidden');
        } catch (e) {
            phToast('Erro de comunicação', 'error');
        } finally {
            btn.disabled = false; btn.textContent = 'Carregar Itens';
        }
    });

    // Helper: recalcula o total da linha-pai a partir das sub-linhas de split
    function _devRecalcularTotalSplit(parentSeq) {
        const body = document.getElementById('dev_itens_body');
        if (!body) return;
        const parent = body.querySelector(`tr[data-seq="${parentSeq}"]`);
        const splitRow = body.querySelector(`tr.dev-split-row[data-parent-seq="${parentSeq}"]`);
        if (!parent || !splitRow) return;
        const inputs = splitRow.querySelectorAll('.dev-split-qtd');
        let soma = 0;
        inputs.forEach(inp => {
            const v = parseFloat(inp.value);
            if (!isNaN(v) && v > 0) soma += v;
        });
        const totalEl = parent.querySelector('.dev-qtd-total');
        if (totalEl) totalEl.textContent = _fmtNum(soma, 2);
        const max = parseFloat(parent.dataset.max);
        if (totalEl) {
            totalEl.classList.toggle('dev-qtd-total--excede', soma > max + 1e-6);
        }
    }

    // Sugestão proporcional ao marcar checkbox em item com split (lotes_origem >= 2)
    function _devSugerirProporcional(parentSeq) {
        const body = document.getElementById('dev_itens_body');
        if (!body) return;
        const parent = body.querySelector(`tr[data-seq="${parentSeq}"]`);
        const splitRow = body.querySelector(`tr.dev-split-row[data-parent-seq="${parentSeq}"]`);
        if (!parent || !splitRow) return;
        const max = parseFloat(parent.dataset.max);  // qtd_devolvivel total
        const inputs = Array.from(splitRow.querySelectorAll('.dev-split-qtd'));
        const totalAtendido = inputs.reduce((acc, inp) => {
            return acc + (parseFloat(inp.dataset.atendido) || 0);
        }, 0);
        if (totalAtendido <= 0) {
            inputs.forEach(inp => { inp.value = ''; });
            return;
        }
        // Distribui proporcional a qtd_atendida de cada lote
        inputs.forEach(inp => {
            const atend = parseFloat(inp.dataset.atendido) || 0;
            const sugestao = max * (atend / totalAtendido);
            inp.value = sugestao.toFixed(2);
        });
        _devRecalcularTotalSplit(parentSeq);
    }

    // Quando o checkbox marca/desmarca, pré-preenche qtd_devolver
    document.getElementById('dev_itens_body')?.addEventListener('change', (ev) => {
        if (!ev.target.classList.contains('dev-chk')) return;
        const tr = ev.target.closest('tr');
        const seq = tr.dataset.seq;
        const ehSplit = tr.dataset.split === '1';

        if (ehSplit) {
            const splitRow = document.querySelector(`#dev_itens_body tr.dev-split-row[data-parent-seq="${seq}"]`);
            if (ev.target.checked) {
                splitRow?.classList.remove('hidden');
                _devSugerirProporcional(seq);
            } else {
                splitRow?.classList.add('hidden');
                splitRow?.querySelectorAll('.dev-split-qtd').forEach(inp => { inp.value = ''; });
                _devRecalcularTotalSplit(seq);
            }
        } else {
            const inp = tr.querySelector('.dev-qtd');
            if (ev.target.checked && !inp.value) {
                inp.value = tr.dataset.max;
            } else if (!ev.target.checked) {
                inp.value = '';
            }
        }
    });

    // Recalcula resumo do split conforme o operador edita as qtds por lote
    document.getElementById('dev_itens_body')?.addEventListener('input', (ev) => {
        if (!ev.target.classList.contains('dev-split-qtd')) return;
        const splitRow = ev.target.closest('tr.dev-split-row');
        const parentSeq = splitRow?.dataset.parentSeq;
        if (parentSeq) _devRecalcularTotalSplit(parentSeq);
    });

    // Clamp automático no blur: se operador digitar valor maior que o máximo
    // (qtd_devolvivel pra .dev-qtd / qtd_atendida do lote pra .dev-split-qtd),
    // ajusta automaticamente pro teto e mostra toast informativo. Backend e
    // submit já validam, mas isso elimina erro silencioso na UX.
    document.getElementById('dev_itens_body')?.addEventListener('blur', (ev) => {
        const t = ev.target;
        const ehSimples = t.classList?.contains('dev-qtd');
        const ehSplit   = t.classList?.contains('dev-split-qtd');
        if (!ehSimples && !ehSplit) return;
        const max = parseFloat(ehSimples
            ? (t.closest('tr')?.dataset.max)
            : (t.dataset.atendido));
        const v = parseFloat(t.value);
        if (!isNaN(max) && !isNaN(v) && v > max + 1e-6) {
            t.value = max.toFixed(2);
            phToast(`Ajustado pro máximo disponível: ${_fmtNum(max, 2)}`, 'info');
            // Re-dispara input pra reflexar no total
            t.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }, true);   // capture=true porque blur não bubbles

    document.getElementById('devConfirmBtn')?.addEventListener('click', async () => {
        if (!_devNotaCarregada) { phToast('Carregue a nota antes', 'error'); return; }

        const linhas = Array.from(document.querySelectorAll('#dev_itens_body tr[data-seq]'));
        const itens = [];
        for (const tr of linhas) {
            const chk = tr.querySelector('.dev-chk');
            if (!chk || !chk.checked) continue;
            const seq = parseInt(tr.dataset.seq, 10);
            const max = parseFloat(tr.dataset.max);
            const ehSplit = tr.dataset.split === '1';

            if (ehSplit) {
                // Formato NOVO: divisão por lote
                const splitRow = document.querySelector(`#dev_itens_body tr.dev-split-row[data-parent-seq="${seq}"]`);
                const inputs = Array.from(splitRow?.querySelectorAll('.dev-split-qtd') || []);
                const lotes = [];
                let soma = 0;
                for (const inp of inputs) {
                    const qtd = parseFloat(inp.value);
                    if (!qtd || qtd <= 0) continue;
                    const atend = parseFloat(inp.dataset.atendido) || 0;
                    if (qtd > atend + 1e-6) {
                        phToast(`SEQ ${seq} · lote ${inp.dataset.cod}: qtd ${_fmtNum(qtd, 2)} excede atendido ${_fmtNum(atend, 2)}`, 'error');
                        return;
                    }
                    soma += qtd;
                    lotes.push({ codagregacao: inp.dataset.cod, qtd });
                }
                if (!lotes.length) {
                    phToast(`SEQ ${seq}: informe a quantidade em pelo menos 1 lote`, 'error');
                    return;
                }
                if (soma > max + 1e-6) {
                    phToast(`SEQ ${seq}: soma dos lotes (${_fmtNum(soma, 2)}) excede saldo devolvível ${_fmtNum(max, 2)}`, 'error');
                    return;
                }
                itens.push({ sequencia_origem: seq, lotes_devolver: lotes });
            } else {
                // Formato ANTIGO: 1 qtd por item
                const qtd = parseFloat(tr.querySelector('.dev-qtd').value);
                if (!qtd || qtd <= 0) {
                    phToast(`SEQ ${seq}: informe a quantidade a devolver`, 'error');
                    return;
                }
                if (qtd > max + 1e-6) {
                    phToast(`SEQ ${seq}: quantidade ${_fmtNum(qtd, 2)} excede saldo devolvível ${_fmtNum(max, 2)}`, 'error');
                    return;
                }
                itens.push({ sequencia_origem: seq, qtd_devolver: qtd });
            }
        }

        if (!itens.length) {
            phToast('Marque ao menos 1 item para devolver', 'error');
            return;
        }

        const observacao = document.getElementById('dev_observacao').value.trim() || 'DEVOLUCAO';
        const dtnegISO   = document.getElementById('dev_dtneg').value;
        const dtneg = dtnegISO ? dtnegISO.split('-').reverse().join('/') : null;

        const ok = await phConfirmar({
            titulo: 'Criar devolução pendente de confirmação?',
            mensagem: `${itens.length} item(ns) da nota ${_devNotaCarregada.cabecalho.nunota}. ` +
                      `A devolução fica AGUARDANDO no Sankhya — abra o documento lá ` +
                      `e clique Confirmar pra liberar o financeiro reverso e a NFe de devolução.`,
            tipo: 'aviso',
        });
        if (!ok) return;

        const btn = document.getElementById('devConfirmBtn');
        btn.disabled = true; btn.classList.add('btn--loading');
        try {
            const res = await phPostJSON('/sankhya/venda/api/devolucao/criar/', {
                nunota_origem: _devNotaCarregada.cabecalho.nunota,
                itens, observacao, dtneg,
            });
            if (!res.ok || !res.body?.ok) {
                phToast(res.body?.error || 'Falha ao criar devolução', 'error');
                return;
            }
            phToast(`Devolução criada · NUNOTA ${res.body.nunota} · ${_fmtBRL(res.body.vlrnota)}. Confirme no Sankhya pra finalizar.`, 'success');
            _fecharModal('devolucaoModal');
            carregarVendas(false);
        } catch (e) {
            phToast('Erro de comunicação. Tente novamente.', 'error');
        } finally {
            btn.disabled = false; btn.classList.remove('btn--loading');
        }
    });

    // --------------------------------------------------------------------------
    // HISTÓRICO DO LOTE — timeline visual
    // --------------------------------------------------------------------------
    function abrirModalHistorico() {
        document.getElementById('hist_lote').value = '';
        document.getElementById('hist_resumo').classList.add('hidden');
        document.getElementById('hist_timeline').innerHTML =
            '<div class="ia-placeholder">Informe um lote acima e clique em Buscar.</div>';
        _abrirModal('historicoLoteModal');
    }

    document.getElementById('btnHistoricoLote')?.addEventListener('click', abrirModalHistorico);
    document.getElementById('histCloseBtn')?.addEventListener('click', () => _fecharModal('historicoLoteModal'));

    async function _buscarHistoricoLote() {
        const lote = document.getElementById('hist_lote').value.trim();
        if (!lote) { phToast('Informe o lote', 'error'); return; }

        const cont = document.getElementById('hist_timeline');
        cont.innerHTML = '<div class="ia-placeholder">Buscando...</div>';
        try {
            const r = await fetch(`/sankhya/venda/api/lote/historico/?lote=${encodeURIComponent(lote)}`);
            const d = await r.json();
            if (!r.ok || !d.ok) {
                cont.innerHTML = `<div class="ia-placeholder">${d.error || 'Erro'}</div>`;
                return;
            }
            const tl = d.timeline || [];
            document.getElementById('hist_lote_label').textContent = d.lote;
            document.getElementById('hist_count').textContent = tl.length;
            document.getElementById('hist_resumo').classList.remove('hidden');

            if (!tl.length) {
                cont.innerHTML = '<div class="ia-placeholder">Lote sem movimentações registradas.</div>';
                return;
            }
            cont.innerHTML = tl.map(ev => {
                const cls = ev.is_entrada ? 'hist-node-entrada'
                         : ev.is_devolucao ? 'hist-node-devolucao'
                         : ev.is_baixa ? 'hist-node-baixa'
                         : 'hist-node-default';
                const statusBadge = ev.statusnota === 'L' ? '<span class="hist-status hist-status-l">CONFIRMADO</span>'
                                  : ev.statusnota === 'A' ? '<span class="hist-status hist-status-a">EM ABERTO</span>'
                                  : '';
                return `
                    <div class="hist-event ${cls}">
                        <div class="hist-event-top">
                            <span class="hist-top-badge top-badge-${ev.codtipoper}">TOP ${ev.codtipoper}</span>
                            <strong class="hist-top-nome">${ev.top_nome}</strong>
                            ${statusBadge}
                            <span class="hist-date">${ev.dtneg}</span>
                        </div>
                        <div class="hist-event-body">
                            <div>
                                <strong>NUNOTA ${ev.nunota}</strong>${ev.numnota ? ' · Nota ' + ev.numnota : ''}
                                · ${ev.nomeparc || `CODPARC ${ev.codparc || '—'}`}
                            </div>
                            <div class="hist-event-prod">
                                ${ev.codprod} — ${(ev.descrprod || '').substring(0, 50)}
                                · <strong>${_fmtNum(ev.qtdneg)} ${ev.codvol}</strong>
                                ${ev.vlrtot ? ' · ' + _fmtBRL(ev.vlrtot) : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (e) {
            cont.innerHTML = '<div class="ia-placeholder">Erro de comunicação.</div>';
        }
    }

    document.getElementById('hist_btnBuscar')?.addEventListener('click', _buscarHistoricoLote);
    document.getElementById('hist_lote')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); _buscarHistoricoLote(); }
    });

    // Fechar modais com Esc / click fora
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        ['avariaModal', 'devolucaoModal', 'historicoLoteModal'].forEach(id => {
            const m = document.getElementById(id);
            if (m && !m.classList.contains('hidden')) _fecharModal(id);
        });
    });
    ['avariaModal', 'devolucaoModal', 'historicoLoteModal'].forEach(id => {
        const m = document.getElementById(id);
        if (m) m.addEventListener('click', (e) => {
            if (e.target === m) _fecharModal(id);
        });
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

    // Mai/2026 — Select-on-focus agora vem do IAgro.installAutoSelect global
    // (base.html). Removida a duplicação local. Pra opt-out em campo
    // específico, usar atributo `data-no-select`.

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
        // Mai/2026 (2026-05-20) — reset estado de origem do preço
        if (typeof resetarPrecoOrigem === 'function') resetarPrecoOrigem();
    }

    /** Monta payload de origem do preço pra incluir no POST do item. */
    function _coletarPrecoOrigemPayload() {
        // 2026-05-21 — só registra origem quando vier de TABELA ou PROMOCAO
        // (chip MANUAL e campo de motivo foram removidos pra desburocratizar).
        const out = {};
        if (!precoOrigemEstado.origem) return out;
        out.preco_origem = precoOrigemEstado.origem;
        if (precoOrigemEstado.origem === 'TABELA' && precoOrigemEstado.nutab) {
            out.nutab = precoOrigemEstado.nutab;
        }
        if (precoOrigemEstado.origem === 'PROMOCAO' && precoOrigemEstado.promocaoId) {
            out.promocao_id = precoOrigemEstado.promocaoId;
        }
        return out;
    }

    document.getElementById('itemAddBtn')?.addEventListener('click', async () => {
        const nunota  = parseInt(document.getElementById('items_nunota').value, 10);
        const codprod = parseInt(document.getElementById('item_prod_hidden').value, 10);
        const qtdneg  = parseFloat(document.getElementById('item_qtd').value);
        const vlrunit = parseFloat(document.getElementById('item_preco').value) || 0;
        const codvol  = document.getElementById('item_codvol').value || 'KG';
        const lote    = document.getElementById('item_lote').value.trim() || null;

        if (!nunota)            { phToast('Pedido não identificado.', 'error'); return; }
        if (!codprod)           { phToast('Selecione um produto.', 'warning'); return; }
        if (!qtdneg || qtdneg <= 0) { phToast('Informe uma quantidade válida.', 'warning'); return; }

        // Mai/2026 (2026-05-21) — origem do preço (sem mais validação de MANUAL;
        // origem null = preço livre, backend não obriga observação)
        const precoOrigemPayload = _coletarPrecoOrigemPayload();

        const btn = document.getElementById('itemAddBtn');
        btn.disabled = true;
        try {
            // Modo edição — chama endpoint de update
            if (itemEditandoSeq > 0) {
                const res = await phPostJSON('/sankhya/venda/api/item/editar/', {
                    nunota, sequencia: itemEditandoSeq,
                    codprod, qtdneg, vlrunit, codvol, codagregacao: lote,
                    ...precoOrigemPayload,
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
                        ...precoOrigemPayload,
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
                ...precoOrigemPayload,
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

    // 2026-05-21 — botão X (limpar campos) — pra trocar o lançamento antes de adicionar
    document.getElementById('itemClearBtn')?.addEventListener('click', () => {
        // Em modo edição, mantém o cancelar dedicado (que restaura valores originais).
        // Em modo novo, simplesmente zera os campos.
        if (itemEditandoSeq > 0) {
            cancelarEdicaoItem();
        } else {
            limparCamposItem();
            document.getElementById('item_codvol').value = 'KG'; // restaura default
            document.getElementById('item_prod_vis')?.focus();
        }
    });

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
                <strong><i class="ph ph-warning"></i> Não é possível faturar este pedido ainda.</strong><br>
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

    // ========================================================================
    // Mai/2026 (2026-05-21) — Modal de impressão de pedidos
    // ========================================================================
    const impState = {
        pedidos: [],              // lista do preview
        selecionados: new Set(),  // NUNOTAs selecionados
        modo: null,               // ASSAI_DF | ASSAI_PALMAS_ARAGUAINA | ASSAI_TODOS | DIA
        consolDebounce: null,
    };

    function _fmtBR(n, casas = 2) {
        return (Number(n) || 0).toLocaleString('pt-BR', {
            minimumFractionDigits: casas, maximumFractionDigits: casas
        });
    }
    function _fmtDataBR(s) {
        if (!s) return '';
        if (s.length === 10 && s[4] === '-') {
            const [y, m, d] = s.split('-'); return `${d}/${m}/${y}`;
        }
        return s;
    }
    function _escHtml(s) {
        return String(s ?? '').replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[ch]));
    }

    // Definição dos grupos disponíveis. Renderizados dinamicamente conforme
    // CODTABs detectados no preview do dia (modo DIA sem filtro de tabela).
    // Cada grupo só aparece se houver pelo menos 1 pedido no dia daquela tabela.
    const IMP_GRUPOS = [
        {
            modo:   'ASSAI_DF',
            label:  'Assaí DF',
            // Mostra se pelo menos 1 CODTAB 5 (Assaí DF) presente
            mostra: (tabs) => tabs.includes(5),
        },
        {
            modo:   'ASSAI_PALMAS_ARAGUAINA',
            label:  'Palmas + Araguaína',
            mostra: (tabs) => tabs.includes(17) || tabs.includes(18),
        },
        {
            modo:   'ASSAI_TODOS',
            label:  'Todos os Assaís',
            // Só se houver MAIS DE 1 grupo Assaí distinto (senão é igual ao chip do grupo único)
            mostra: (tabs) => {
                const assais = [5, 17, 18].filter(t => tabs.includes(t));
                return assais.length >= 2;
            },
        },
        {
            modo:   'ECONOMART',
            label:  'Economart',
            mostra: (tabs) => tabs.includes(6),
        },
        {
            modo:   'EXAL',
            label:  'Exal (Lundin)',
            mostra: (tabs) => tabs.includes(15),
        },
        {
            modo:   'JC',
            label:  'JC',
            mostra: (tabs) => tabs.includes(4),
        },
        {
            modo:   'VERDI',
            label:  'Verdi',
            mostra: (tabs) => tabs.includes(10),
        },
        {
            modo:   'NA_HORTA',
            label:  'Na Horta',
            mostra: (tabs) => tabs.includes(2),
        },
        // "Todos os pedidos do dia" sempre aparece (não filtra CODTAB)
        {
            modo:   'DIA',
            label:  'Todos os pedidos do dia',
            mostra: () => true,
        },
    ];

    // CODTAB → lista de CODTABs aplicáveis no backend
    const IMP_MODO_CODTABS = {
        'ASSAI_DF':                 [5],
        'ASSAI_PALMAS_ARAGUAINA':   [17, 18],
        'ASSAI_TODOS':              [5, 17, 18],
        'ECONOMART':                [6],
        'EXAL':                     [15],
        'JC':                       [4],
        'VERDI':                    [10],
        'NA_HORTA':                 [2],
        'DIA':                      [],  // sem filtro de tabela
    };

    function renderChipsDinamicos(codtabsDistintos) {
        const wrap = document.getElementById('impChipsDinamicos');
        if (!wrap) return;
        const aplicaveis = IMP_GRUPOS.filter(g => g.mostra(codtabsDistintos));
        if (!aplicaveis.length) {
            wrap.innerHTML = '<span class="ia-placeholder" style="font-size:11px;">Nenhum pedido no dia</span>';
            return;
        }
        wrap.innerHTML = aplicaveis.map(g => `
            <button type="button" class="imp-chip" data-modo="${g.modo}">${_escHtml(g.label)}</button>
        `).join('');
        // Re-anexa listeners
        wrap.querySelectorAll('.imp-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                wrap.querySelectorAll('.imp-chip').forEach(c => c.classList.remove('is-active'));
                chip.classList.add('is-active');
                impState.modo = chip.dataset.modo;
                carregarPreviewImpressao(impState.modo);
            });
        });
    }

    async function detectarGruposDoDia() {
        // Faz preview SEM modo (= todos os pedidos do dia) — usado pra:
        //   1) Descobrir quais CODTABs existem → chips dinâmicos
        //   2) Já popular a lista de pedidos com TUDO do dia (chip DIA default)
        const qs = new URLSearchParams();
        const dtIni = inputStart?.value || '';
        const dtFim = inputEnd?.value   || '';
        if (dtIni && dtFim && dtIni === dtFim) qs.set('dtneg', dtIni);
        else if (dtIni && dtFim) { qs.set('dtneg_de', dtIni); qs.set('dtneg_ate', dtFim); }
        try {
            const r = await fetch(`/sankhya/venda/api/imprimir/preview/?${qs.toString()}`);
            const d = await r.json();
            if (!d.ok) { renderChipsDinamicos([]); return; }
            renderChipsDinamicos(d.codtabs_distintos || []);
            // Auto-aplica "Todos os pedidos do dia" como default e popula a lista
            impState.pedidos = d.pedidos || [];
            impState.selecionados = new Set(impState.pedidos.map(p => p.nunota));
            impState.modo = 'DIA';
            const chipDia = document.querySelector('.imp-chip[data-modo="DIA"]');
            if (chipDia) chipDia.classList.add('is-active');
            renderImpPedidos();
            atualizarConsolDebounced();
        } catch (e) {
            console.error('detectarGruposDoDia', e);
            renderChipsDinamicos([]);
        }
    }

    function abrirImpressaoModal() {
        const m = document.getElementById('impressaoModal');
        if (!m) return;
        m.classList.remove('hidden');
        // Mostra Data única OU Período conforme filtro lateral
        const dtIni = inputStart?.value || '';
        const dtFim = inputEnd?.value   || '';
        let labelData = '';
        if (dtIni && dtFim && dtIni === dtFim) {
            labelData = `Data do filtro: ${_fmtDataBR(dtIni)}`;
        } else if (dtIni && dtFim) {
            labelData = `Período: ${_fmtDataBR(dtIni)} → ${_fmtDataBR(dtFim)}`;
        } else if (dtIni || dtFim) {
            labelData = `Data do filtro: ${_fmtDataBR(dtIni || dtFim)}`;
        } else {
            labelData = 'Sem data no filtro';
        }
        document.getElementById('impInfo').textContent = labelData;
        // Limpa estado anterior
        impState.pedidos = [];
        impState.selecionados.clear();
        impState.modo = null;
        renderImpPedidos();
        renderImpConsol(null);
        // Detecta grupos do dia → renderiza chips dinâmicos
        detectarGruposDoDia();
    }

    function fecharImpressaoModal() {
        document.getElementById('impressaoModal')?.classList.add('hidden');
    }

    async function carregarPreviewImpressao(modo) {
        const qs = new URLSearchParams();
        // Backend aceita `modo` legado (ASSAI_DF etc) OU `codtabs` lista direta.
        // Modos novos (ECONOMART, EXAL, JC...) não estão no backend ainda — pra
        // não criar duplicidade, mandamos CODTABs explícitos via querystring.
        const codtabs = IMP_MODO_CODTABS[modo] || [];
        if (codtabs.length === 0 && modo !== 'DIA') {
            // Fallback compatibilidade: passa modo direto (backend conhece)
            qs.set('modo', modo);
        } else if (codtabs.length > 0) {
            qs.set('codtabs', codtabs.join(','));
        }
        // Data do filtro vira filtro de DTNEG (sempre — em todos os modos)
        const dtIni = inputStart?.value || '';
        const dtFim = inputEnd?.value   || '';
        if (dtIni && dtFim && dtIni === dtFim) {
            qs.set('dtneg', dtIni);
        } else if (dtIni && dtFim) {
            qs.set('dtneg_de',  dtIni);
            qs.set('dtneg_ate', dtFim);
        }
        const lista = document.getElementById('impPedidosList');
        lista.innerHTML = '<div class="ia-placeholder">Carregando…</div>';
        try {
            const r = await fetch(`/sankhya/venda/api/imprimir/preview/?${qs.toString()}`);
            const d = await r.json();
            if (!d.ok) {
                lista.innerHTML = `<div class="ia-placeholder">${_escHtml(d.error || 'Erro')}</div>`;
                return;
            }
            impState.pedidos = d.pedidos || [];
            impState.selecionados = new Set(impState.pedidos.map(p => p.nunota));
            renderImpPedidos();
            atualizarConsolDebounced();
        } catch (e) {
            console.error('carregarPreviewImpressao', e);
            lista.innerHTML = '<div class="ia-placeholder">Erro de rede.</div>';
        }
    }

    function renderImpPedidos() {
        const lista = document.getElementById('impPedidosList');
        const ct = document.getElementById('impPedidosCount');
        ct.textContent = `${impState.selecionados.size} / ${impState.pedidos.length}`;
        if (!impState.pedidos.length) {
            lista.innerHTML = '<div class="ia-placeholder">Nenhum pedido encontrado.</div>';
            return;
        }
        const html = impState.pedidos.map(p => {
            const checked = impState.selecionados.has(p.nunota) ? 'checked' : '';
            const tab = p.codtab ? `<span class="imp-tab-badge">T${p.codtab}</span>` : '';
            return `
              <label class="imp-pedido-row" title="Pedido ${p.nunota} · R$ ${_fmtBR(p.vlrnota)}">
                <input type="checkbox" class="imp-ped-check" data-nunota="${p.nunota}" ${checked}>
                <span class="imp-ped-nome">${_escHtml(p.nomeparc)}</span>
                ${tab}
              </label>`;
        }).join('');
        lista.innerHTML = html;
        lista.querySelectorAll('.imp-ped-check').forEach(cb => {
            cb.addEventListener('change', (ev) => {
                const n = parseInt(ev.target.dataset.nunota, 10);
                if (ev.target.checked) impState.selecionados.add(n);
                else impState.selecionados.delete(n);
                ct.textContent = `${impState.selecionados.size} / ${impState.pedidos.length}`;
                atualizarConsolDebounced();
            });
        });
    }

    function atualizarConsolDebounced() {
        if (impState.consolDebounce) clearTimeout(impState.consolDebounce);
        impState.consolDebounce = setTimeout(carregarConsolidacao, 250);
    }

    async function carregarConsolidacao() {
        const sel = Array.from(impState.selecionados);
        if (!sel.length) { renderImpConsol(null); return; }
        const info = document.getElementById('impConsolInfo');
        info.textContent = 'Calculando…';
        try {
            const csrf = (window.IAgro?.getCookie?.('csrftoken')
                || document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1]
                || '');
            const r = await fetch('/sankhya/venda/api/imprimir/consolidacao/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf,
                },
                body: JSON.stringify({ nunotas: sel }),
            });
            const d = await r.json();
            if (!d.ok) {
                info.textContent = d.error || 'Erro';
                return;
            }
            renderImpConsol(d);
        } catch (e) {
            console.error('carregarConsolidacao', e);
            info.textContent = 'Erro de rede.';
        }
    }

    function renderImpConsol(d) {
        const body = document.getElementById('impConsolBody');
        const info = document.getElementById('impConsolInfo');
        const tQtd = document.getElementById('impTotalQtd');
        const tCx  = document.getElementById('impTotalCx');
        const tPed = document.getElementById('impTotalPed');
        if (!d) {
            body.innerHTML = '<tr><td colspan="6" class="ia-placeholder">Marque pedidos pra consolidar.</td></tr>';
            info.textContent = '—';
            tQtd.textContent = '0'; tCx.textContent = '0'; tPed.textContent = '0';
            return;
        }
        info.textContent = `${d.total_pedidos} pedido${d.total_pedidos !== 1 ? 's' : ''}, ${d.produtos.length} produto${d.produtos.length !== 1 ? 's' : ''} distinto${d.produtos.length !== 1 ? 's' : ''}`;
        if (!d.produtos.length) {
            body.innerHTML = '<tr><td colspan="6" class="ia-placeholder">Sem itens nos pedidos selecionados.</td></tr>';
            tQtd.textContent = '0'; tCx.textContent = '0'; tPed.textContent = '0';
            return;
        }
        body.innerHTML = d.produtos.map(p => `
          <tr>
            <td class="text-right">${p.codprod}</td>
            <td>${_escHtml(p.descrprod)}</td>
            <td class="text-center">${_escHtml(p.codvol)}</td>
            <td class="text-right">${_fmtBR(p.qtd_total, 0)}</td>
            <td class="text-right">${p.qtd_caixas || ''}</td>
            <td class="text-right">${p.n_pedidos}</td>
          </tr>`).join('');
        tQtd.textContent = _fmtBR(d.total_qtd, 0);
        tCx.textContent  = String(d.total_caixas);
        tPed.textContent = String(d.total_pedidos);
    }

    async function _imprimirPdf(modo) {
        const sel = Array.from(impState.selecionados);
        if (!sel.length) {
            phToast('Selecione pelo menos 1 pedido pra imprimir.', 'warning');
            return;
        }

        // Monta payload
        const payload = { nunotas: sel };
        let url;
        if (modo === 'consolidado') {
            const titulos = {
                'ASSAI_DF':              'CONSOLIDAÇÃO - ASSAÍ DF',
                'ASSAI_PALMAS_ARAGUAINA':'CONSOLIDAÇÃO - PALMAS + ARAGUAÍNA',
                'ASSAI_TODOS':           'CONSOLIDAÇÃO - TODOS OS ASSAÍS',
                'DIA':                   'CONSOLIDAÇÃO - PEDIDOS DO DIA',
            };
            if (impState.modo) payload.titulo = titulos[impState.modo] || 'CONSOLIDAÇÃO DE PEDIDOS';
            const dtIni = inputStart?.value || '';
            const dtFim = inputEnd?.value   || '';
            if (dtIni === dtFim && dtIni) payload.subtitulo = `Data: ${_fmtDataBR(dtIni)}`;
            else if (dtIni && dtFim)       payload.subtitulo = `Período: ${_fmtDataBR(dtIni)} → ${_fmtDataBR(dtFim)}`;
            url = '/sankhya/venda/api/imprimir/pdf-consolidado/';
        } else {
            url = '/sankhya/venda/api/imprimir/pdf-individual/';
        }

        // POST + blob → URL local → abre em aba nova (não estoura URL e
        // não precisa de form/target hack)
        const csrf = (window.IAgro?.getCookie?.('csrftoken')
            || document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1]
            || '');
        try {
            const r = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf,
                },
                body: JSON.stringify(payload),
            });
            if (!r.ok) {
                let msg = `Erro ${r.status}`;
                try {
                    const j = await r.json();
                    msg = j.error || msg;
                } catch (_) {}
                phToast(msg, 'error');
                return;
            }
            const blob = await r.blob();
            const blobUrl = URL.createObjectURL(blob);
            window.open(blobUrl, '_blank');
            // Libera memória depois de alguns segundos
            setTimeout(() => URL.revokeObjectURL(blobUrl), 30_000);
        } catch (e) {
            console.error('_imprimirPdf', e);
            phToast('Erro ao gerar PDF.', 'error');
        }
    }

    // Bind dos elementos do modal de impressão
    const btnPrint = document.getElementById('btnPrintVenda');
    if (btnPrint) {
        btnPrint.disabled = false;  // habilita (estava disabled no HTML)
        btnPrint.addEventListener('click', abrirImpressaoModal);
    }
    document.getElementById('impFechar')?.addEventListener('click', fecharImpressaoModal);
    document.getElementById('impCancelar')?.addEventListener('click', fecharImpressaoModal);

    // Chips de agrupamento
    document.querySelectorAll('.imp-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.imp-chip').forEach(c => c.classList.remove('is-active'));
            chip.classList.add('is-active');
            impState.modo = chip.dataset.modo;
            carregarPreviewImpressao(impState.modo);
        });
    });

    // Marcar/desmarcar todos
    document.getElementById('impMarcarTodos')?.addEventListener('click', () => {
        impState.selecionados = new Set(impState.pedidos.map(p => p.nunota));
        renderImpPedidos();
        atualizarConsolDebounced();
    });
    document.getElementById('impDesmarcarTodos')?.addEventListener('click', () => {
        impState.selecionados.clear();
        renderImpPedidos();
        renderImpConsol(null);
    });

    // Botões imprimir
    document.getElementById('impPdfIndividual')?.addEventListener('click', () => _imprimirPdf('individual'));
    document.getElementById('impPdfConsolidado')?.addEventListener('click', () => _imprimirPdf('consolidado'));

    // Fechar com Esc / click fora
    document.getElementById('impressaoModal')?.addEventListener('click', (ev) => {
        if (ev.target.id === 'impressaoModal') fecharImpressaoModal();
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
