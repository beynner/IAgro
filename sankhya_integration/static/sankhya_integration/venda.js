document.addEventListener('DOMContentLoaded', function() {
    // ==========================================
    // UTILITÁRIO: DEBOUNCE (Importado de entrada.js)
    // ==========================================
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }

    // ==========================================
    // 1. ELEMENTOS DA TELA
    // ==========================================
    const formFiltros = document.getElementById('filtersForm');
    const btnUpdate = document.getElementById('btnUpdate');
    const btnClear = document.getElementById('btnClear');
    const tbodyVendas = document.getElementById('vendasTableBody');
    const listaContainer = document.getElementById('vendasList');
    
    const inputStart = formFiltros.querySelector('input[name="start"]');
    const inputEnd = formFiltros.querySelector('input[name="end"]');

    // ==========================================
    // 2. VARIÁVEIS DE ESTADO
    // ==========================================
    let offsetAtual = 0;
    const limite = 50;
    let carregando = false;
    let temMaisRegistros = true;
    let dataFinalAlteradaManualmente = false;

    // Seleção atual (null quando nenhuma linha selecionada)
    let pedidoSelecionado = null;
    // True quando o modal de itens está aberto para editar um pedido existente
    // (desativa o auto-delete de cabeçalho órfão em fecharTudo).
    let modoEdicao = false;
    // Subestado: usuário clicou "Editar Cabeçalho" — cabCard destravado, itens fechado.
    let modoEdicaoCabecalho = false;

    // Dispara a busca automaticamente (usado para campos textuais comuns)
    const dispararFiltroAutomatico = debounce(() => {
        carregarVendas(false);
    }, 500);

    // Aplica o filtro automático aos campos padrão (Empresa, Nota, Lote, TOP)
    const inputsNormais = formFiltros.querySelectorAll('input:not(#parcSearch):not(#codparc):not(#prodSearch):not(#codprod):not([name="start"]):not([name="end"]), select');
    inputsNormais.forEach(campo => {
        campo.addEventListener('input', dispararFiltroAutomatico);
        campo.addEventListener('change', dispararFiltroAutomatico);
    });

    // ==========================================
    // 3. LÓGICA DE DATAS (Navegação << e >> intacta)
    // ==========================================
    inputStart.addEventListener('change', function() {
        if (!dataFinalAlteradaManualmente) {
            inputEnd.value = this.value;
        }
        carregarVendas(false);
    });

    inputEnd.addEventListener('change', function() {
        dataFinalAlteradaManualmente = true;
        carregarVendas(false);
    });

    function deslocarDatas(dias) {
        let d1;
        if (inputStart.value) {
            d1 = new Date(inputStart.value + 'T12:00:00');
        } else {
            d1 = new Date();
        }
        
        d1.setDate(d1.getDate() + dias);
        const novaData = d1.toISOString().split('T')[0];
        
        inputStart.value = novaData;
        
        if (!dataFinalAlteradaManualmente) {
            inputEnd.value = novaData;
        } else if (!inputEnd.value) {
            inputEnd.value = novaData;
        }
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
    // 4. MÓDULO TYPEAHEAD (Clonado de entrada.js)
    // ==========================================
    function attachTA(inpId, hidId, ddId, url, options) {
        try {
            const inp = document.getElementById(inpId);
            const hid = document.getElementById(hidId);
            const dd = document.getElementById(ddId);
            if (!inp || !hid || !dd) return;

            let t = null;

            function hide() {
                dd.style.display = 'none';
                dd.innerHTML = '';
            }

            function show(items) {
                if (!items || !items.length) { hide(); return; }
                // Cria as divs exatamente como no entrada.js, aceitando codparc/cod ou nomeparc/descr
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
                fetch(buildUrl(q))
                    .then(r => r.json())
                    .then(d => show(d.results || []))
                    .catch(() => hide());
            }

            inp.addEventListener('input', (e) => {
                const raw = (e.target.value || '').trim();
                if (t) clearTimeout(t);
                if (raw) {
                    t = setTimeout(() => fetchQ(raw), 400);
                } else {
                    hide();
                    hid.value = ''; // Limpa o hidden se apagou tudo
                    onChange(); // Hook configurável (default: recarrega a lista)
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
                        onChange(); // Hook configurável após seleção por teclado
                    }
                } else if (e.key === 'Escape') {
                    hide();
                }
            });

            dd.addEventListener('click', (ev) => {
                const el = ev.target.closest('div[data-cod]');
                if (!el) return;
                hid.value = el.dataset.cod;
                inp.value = `${el.dataset.cod} — ${el.dataset.descr}`;
                hide();
                onChange(); // Hook configurável após seleção por clique
            });

            document.addEventListener('click', (ev) => {
                if (!dd.contains(ev.target) && ev.target !== inp) hide();
            });

        } catch (e) {
            console.error('Erro no attachTA:', e);
        }
    }

    // Inicializa o Typeahead para Parceiro e Produto
    attachTA('parcSearch', 'codparc', 'parcDropdown', '/sankhya/parceiros/search/', { limit: 15 });
    attachTA('prodSearch', 'codprod', 'prodDropdown', '/sankhya/produtos/search/', { 
        limit: 15,
        extraQuery: 'grupo_inicia_com=1' // 🟢 Nome claro e direto
    });


    // ==========================================
    // 5. BUSCA DO CABEÇALHO (Oracle) - Intacto
    // ==========================================
    async function carregarVendas(append = false) {
        if (carregando || (!temMaisRegistros && append)) return;

        if (!append) {
            offsetAtual = 0;
            temMaisRegistros = true;
            tbodyVendas.innerHTML = '<tr><td colspan="7" class="text-center ph-muted">Buscando no banco de dados...</td></tr>';
            document.getElementById('vendaItemsBody').innerHTML = '<tr><td colspan="4" class="ph-placeholder">Selecione uma venda</td></tr>';
            // Limpa seleção e desabilita ações dependentes dela
            pedidoSelecionado = null;
            const btnDel = document.getElementById('btnDeleteVenda');
            if (btnDel) btnDel.disabled = true;
            const labelSel = document.getElementById('label_sel_nunota');
            if (labelSel) labelSel.textContent = '--';
        } else {
            const trLoading = document.createElement('tr');
            trLoading.id = 'loading-row';
            trLoading.innerHTML = '<td colspan="7" class="text-center ph-muted">Carregando mais pedidos...</td>';
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
            else {
                const rowLoad = document.getElementById('loading-row');
                if (rowLoad) rowLoad.remove();
            }

            if (data.vendas.length === 0) {
                if (!append) tbodyVendas.innerHTML = '<tr><td colspan="7" class="text-center ph-muted">Nenhum pedido encontrado.</td></tr>';
                temMaisRegistros = false;
                carregando = false;
                return;
            }

            if (data.vendas.length < limite) {
                temMaisRegistros = false;
            }

            data.vendas.forEach(v => {
                const tr = document.createElement('tr');
                tr.className = `row--click ${v.status_lote === 'PENDENTE' ? 'lote-alerta' : ''}`;
                tr.dataset.nunota = v.nunota;
                
                const valorFormatado = v.total.toLocaleString('pt-BR', { minimumFractionDigits: 2 });

                tr.innerHTML = `
                    <td>${v.nunota}</td>
                    <td>${v.numnota}</td>
                    <td>${v.emp}</td>
                    <td>${v.top}</td>
                    <td>${v.data ? v.data.substring(0,5) : ''}</td>
                    <td class="ph-truncate" title="${v.parceiro}">${v.parceiro}</td>
                    <td class="text-right">${valorFormatado}</td>
                `;

                // CLIQUE NA LINHA: seleciona + habilita ações de toolbar
                tr.addEventListener('click', function() {
                    document.querySelectorAll('#vendasTableBody tr').forEach(l => l.classList.remove('selected'));
                    this.classList.add('selected');
                    document.getElementById('label_sel_nunota').textContent = v.nunota;
                    carregarItens(v.nunota);
                    pedidoSelecionado = { nunota: v.nunota, top: parseInt(v.top, 10) || 0 };
                    const btnDel = document.getElementById('btnDeleteVenda');
                    if (btnDel) btnDel.disabled = false;
                });

                // DUPLO CLIQUE: abre modal de itens em modo edição (somente TOP 34)
                tr.addEventListener('dblclick', function() {
                    const topNum = parseInt(v.top, 10) || 0;
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
            if (!append) tbodyVendas.innerHTML = `<tr><td colspan="7" class="text-center" style="color:#ef4444;">Erro Backend: ${error.message}</td></tr>`;
        } finally {
            carregando = false;
        }
    }

    // ==========================================
    // 6. SCROLL INFINITO - Intacto
    // ==========================================
    listaContainer.addEventListener('scroll', function() {
        if (listaContainer.scrollTop + listaContainer.clientHeight >= listaContainer.scrollHeight - 10) {
            carregarVendas(true);
        }
    });

    // ==========================================
    // 7. BUSCA DOS ITENS - Intacto
    // ==========================================
    async function carregarItens(nunota) {
        const tbodyItens = document.getElementById('vendaItemsBody');
        tbodyItens.innerHTML = '<tr><td colspan="4" class="text-center ph-muted">Carregando itens...</td></tr>';

        try {
            const response = await fetch(`/sankhya/item/list/?nunota=${nunota}`);
            const data = await response.json();
            if (!data.ok) throw new Error(data.error);

            tbodyItens.innerHTML = '';
            if (data.items.length === 0) {
                tbodyItens.innerHTML = '<tr><td colspan="4" class="text-center ph-muted">Nota sem itens.</td></tr>';
                return;
            }

            data.items.forEach(item => {
                const tr = document.createElement('tr');
                if (!item.lote) {
                    tr.classList.add('item-sem-lote');
                }

                const qtd = parseFloat(item.qtd).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                const total = parseFloat(item.vlt).toLocaleString('pt-BR', { minimumFractionDigits: 2 });

                tr.innerHTML = `
                    <td>${item.lote || '—'}</td>
                    <td class="ph-truncate" title="${item.descr}">${item.descr}</td>
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
    // 8. EVENTOS DE BOTÕES 
    // ==========================================
    btnUpdate.addEventListener('click', () => carregarVendas(false));
    
    btnClear.addEventListener('click', () => { 
        formFiltros.reset(); 
        dataFinalAlteradaManualmente = false;
        
        // Limpa os campos ocultos (value real pro banco) e zera as caixas
        document.getElementById('codparc').value = '';
        document.getElementById('parcSearch').value = '';
        document.getElementById('codprod').value = '';
        document.getElementById('prodSearch').value = '';

        document.getElementById('parcDropdown').style.display = 'none';
        document.getElementById('prodDropdown').style.display = 'none';

        carregarVendas(false); 
    });

    // ==========================================
    // 9. FLUXO DE CRIAÇÃO DE PEDIDO (C.1 MVP)
    //    Cria TGFCAB (TOP 34) + adiciona TGFITE.
    // ==========================================

    // --- Helpers reutilizáveis (postJSON, toast) ---
    const PH = window.PackingHouse || {};
    const phPostJSON = PH.postJSON || window.__postJSON || window.postJSON || async function(url, body){
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

    // --- Referências de modais e controles ---
    const cabModal      = document.getElementById('cabModal');
    const cabCard       = document.getElementById('cabCard');
    const cabItemsModal = document.getElementById('cabItemsModal');
    const cabItemsCard  = document.getElementById('cabItemsCard');

    // Dock do cabeçalho na borda esquerda (mesmo padrão de Entrada/Compra)
    function dockCabecalhoEsquerda() {
        if (!cabModal || !cabCard) return;
        cabModal.style.display = 'block';
        cabCard.style.left    = '16px';
        cabCard.style.opacity = '1';
    }

    // Bloqueia inputs do cabCard preservando o estado original em data-wasDisabled.
    // Mantém apenas cabCancel ativo para o usuário conseguir fechar.
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

    // Só age em inputs que passaram por travarInputsCabecalho — deixa em paz os
    // inputs originalmente disabled (cab_nunota, cab_top, cab_nat, cab_cencus).
    function restaurarInputsCabecalho() {
        if (!cabCard) return;
        cabCard.querySelectorAll('input, textarea, select, button').forEach(el => {
            if (el.dataset && el.dataset.wasDisabled !== undefined) {
                el.disabled = el.dataset.wasDisabled === '1';
                delete el.dataset.wasDisabled;
            }
        });
    }

    // Após salvar o cabeçalho: trava cab, abre itens ao lado direito do cabCard
    function abrirItensAoLado() {
        if (!cabItemsModal || !cabItemsCard || !cabCard) return;
        travarInputsCabecalho();
        cabItemsModal.style.display = 'block';
        // Dock cabCard garante posição conhecida antes de calcular o left dos itens
        const cabRect = cabCard.getBoundingClientRect();
        const leftItens = Math.max(16 + cabRect.width + 8, cabRect.right + 8) + 'px';
        requestAnimationFrame(() => { cabItemsCard.style.left = leftItens; });
    }

    // Contador de itens adicionados no pedido em curso. Reseta a cada cabSave bem-sucedido.
    let itensInseridosCount = 0;

    // Fecha os modais imediatamente. Só apaga cabeçalho órfão quando NÃO está
    // em modoEdicao (= pedido criado agora e fechado sem itens).
    async function fecharTudo() {
        const nunotaStr = document.getElementById('cab_nunota')?.value || '';
        const nunota    = parseInt(nunotaStr, 10);
        const precisaDeletar = !modoEdicao && nunota && itensInseridosCount === 0;

        // Reseta estado antes do await para evitar dupla-exclusão
        if (document.getElementById('cab_nunota')) document.getElementById('cab_nunota').value = '';
        itensInseridosCount = 0;
        modoEdicao = false;
        modoEdicaoCabecalho = false;

        // Animação de fechar (sempre imediata, ambos os cards)
        if (cabItemsCard) cabItemsCard.style.left = '100%';
        if (cabCard)      cabCard.style.left      = '-1200px';
        restaurarInputsCabecalho();
        setTimeout(() => {
            if (cabItemsModal) cabItemsModal.style.display = 'none';
            if (cabModal)      cabModal.style.display      = 'none';
        }, 320);

        // Exclusão em paralelo quando aplicável
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

    // Abre um pedido existente: mostra cabCard (travado, somente leitura) e
    // cabItemsCard ao lado (edição dos itens habilitada).
    async function abrirPedidoParaEdicao(nunota) {
        modoEdicao = true;
        itensInseridosCount = 0;
        limparMarcasInvalidas();
        limparCamposItem();

        // Placeholder enquanto o cabeçalho carrega
        document.getElementById('cab_nunota').value = nunota;
        document.getElementById('cab_empSearch').value      = 'Carregando...';
        document.getElementById('cab_parcSearch').value     = 'Carregando...';
        document.getElementById('cab_tipvendaSearch').value = 'Carregando...';
        document.getElementById('cab_dtneg').value          = '';
        document.getElementById('cab_obs').value            = '';

        // Fetch do cabeçalho para popular os campos
        try {
            const rc = await fetch(`/sankhya/venda/api/cabecalho/obter/?nunota=${nunota}`);
            const dc = await rc.json();
            if (!dc.ok) throw new Error(dc.error || 'Erro ao obter cabeçalho');
            document.getElementById('cab_codemp').value         = dc.codemp ?? '';
            document.getElementById('cab_empSearch').value      = dc.codemp
                ? `${dc.codemp} — ${dc.nome_emp || ''}` : '';
            document.getElementById('cab_codparc').value        = dc.codparc ?? '';
            document.getElementById('cab_parcSearch').value     = dc.codparc
                ? `${dc.codparc} — ${dc.nome_parc || ''}` : '';
            document.getElementById('cab_codtipvenda').value    = dc.codtipvenda ?? '';
            document.getElementById('cab_tipvendaSearch').value = dc.codtipvenda
                ? `${dc.codtipvenda} — ${dc.descr_tipvenda || ''}` : '';
            document.getElementById('cab_dtneg').value          = dc.dtneg || '';
            document.getElementById('cab_obs').value            = dc.obs || '';
        } catch (e) {
            phToast(`Erro ao carregar cabeçalho: ${e.message}`, 'error');
            modoEdicao = false;
            return;
        }

        // cabCard dock + trava de inputs, depois itens ao lado
        restaurarInputsCabecalho();   // limpa qualquer estado anterior
        dockCabecalhoEsquerda();
        document.getElementById('items_nunota').value = nunota;
        document.getElementById('items_nunota_display').textContent = nunota;
        document.getElementById('itemsListBody').innerHTML =
            '<tr><td colspan="6" class="ph-placeholder">Carregando itens...</td></tr>';
        abrirItensAoLado();
        setTimeout(() => document.getElementById('item_prod_vis')?.focus(), 160);

        // Fetch dos itens já existentes
        try {
            const ri = await fetch(`/sankhya/item/list/?nunota=${nunota}`);
            const di = await ri.json();
            const tbody = document.getElementById('itemsListBody');
            if (!di.ok) throw new Error(di.error || 'Erro ao carregar itens');

            if (!Array.isArray(di.items) || di.items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="ph-placeholder">Nenhum item inserido.</td></tr>';
                return;
            }
            tbody.innerHTML = '';
            di.items.forEach(item => {
                const qtd   = parseFloat(item.qtd || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                const preco = parseFloat(item.vlu || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                const total = parseFloat(item.vlt || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="ph-truncate" title="${item.descr || ''}">${item.descr || ''}</td>
                    <td>${item.lote || '—'}</td>
                    <td class="text-right">${qtd}</td>
                    <td class="text-right">${preco}</td>
                    <td class="text-right">${total}</td>
                    <td></td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            const tbody = document.getElementById('itemsListBody');
            tbody.innerHTML = `<tr><td colspan="6" class="ph-placeholder" style="color:#ef4444">Erro: ${e.message}</td></tr>`;
        }
    }

    // Handler do botão "Excluir" da toolbar
    document.getElementById('btnDeleteVenda')?.addEventListener('click', async () => {
        if (!pedidoSelecionado) return;
        if (pedidoSelecionado.top !== 34) {
            phToast('Apenas pedidos TOP 34 podem ser excluídos.', 'warning');
            return;
        }
        if (!confirm(`Excluir o pedido ${pedidoSelecionado.nunota}? Essa ação remove cabeçalho e todos os itens.`)) return;

        const btn = document.getElementById('btnDeleteVenda');
        btn.disabled = true;
        try {
            const res = await phPostJSON('/sankhya/venda/api/excluir/',
                                         { nunota: pedidoSelecionado.nunota });
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

    // --- Typeaheads dos modais (NÃO recarregam a lista ao selecionar) ---
    const noop = () => {};
    attachTA('cab_empSearch', 'cab_codemp', 'cab_empDropdown', '/sankhya/empresa/search/',
             { limit: 15, onChange: noop });
    attachTA('cab_parcSearch', 'cab_codparc', 'cab_parcDropdown', '/sankhya/parceiros/search/',
             { limit: 15, onChange: noop });
    attachTA('cab_tipvendaSearch', 'cab_codtipvenda', 'cab_tipvendaDropdown', '/sankhya/tipvenda/search/',
             { limit: 15, onChange: noop });
    attachTA('item_prod_vis', 'item_prod_hidden', 'item_prod_sugg', '/sankhya/produtos/search/',
             { limit: 15, extraQuery: 'grupo_inicia_com=1', onChange: noop });

    // --- Labels fixos do cabeçalho buscam a descrição real no banco ---
    async function carregarLabelFixo(codigo, url, inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        try {
            const r = await fetch(`${url}?q=${codigo}&limit=5`);
            const d = await r.json();
            const item = (d.results || []).find(x => String(x.cod) === String(codigo));
            input.value = item
                ? `${item.cod} — ${item.descr}`
                : `${codigo} — (não encontrado)`;
        } catch {
            input.value = `${codigo} — (erro ao carregar)`;
        }
    }
    carregarLabelFixo(10010100, '/sankhya/natureza/search/', 'cab_nat');
    carregarLabelFixo(10100,    '/sankhya/cencus/search/',   'cab_cencus');

    // Popula o par (hidden + visible) de um typeahead a partir de um código fixo.
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

    // --- Novo Pedido: prepara e abre o cabModal ---
    document.getElementById('btnNewVenda')?.addEventListener('click', () => {
        modoEdicao = false;
        modoEdicaoCabecalho = false;
        document.getElementById('cab_nunota').value   = '';
        document.getElementById('cab_codparc').value  = '';
        document.getElementById('cab_parcSearch').value = '';
        document.getElementById('cab_codtipvenda').value    = '';
        document.getElementById('cab_tipvendaSearch').value = '';
        document.getElementById('cab_dtneg').value    = new Date().toISOString().split('T')[0];
        document.getElementById('cab_obs').value      = '';
        preencherTypeaheadPorCodigo('/sankhya/empresa/search/', 10, 'cab_codemp', 'cab_empSearch');
        restaurarInputsCabecalho(); // garante inputs liberados em um novo pedido
        limparMarcasInvalidas();
        dockCabecalhoEsquerda();
        setTimeout(() => document.getElementById('cab_parcSearch')?.focus(), 160);
    });

    document.getElementById('cabCancel')?.addEventListener('click', async () => {
        // Se está cancelando a edição do cabeçalho de um pedido existente,
        // descarta alterações, recarrega valores do banco e volta ao modal de itens.
        if (modoEdicaoCabecalho) {
            const nunota = parseInt(document.getElementById('cab_nunota').value, 10);
            modoEdicaoCabecalho = false;
            if (nunota) {
                try {
                    const rc = await fetch(`/sankhya/venda/api/cabecalho/obter/?nunota=${nunota}`);
                    const dc = await rc.json();
                    if (dc.ok) {
                        document.getElementById('cab_codemp').value         = dc.codemp ?? '';
                        document.getElementById('cab_empSearch').value      = dc.codemp
                            ? `${dc.codemp} — ${dc.nome_emp || ''}` : '';
                        document.getElementById('cab_codparc').value        = dc.codparc ?? '';
                        document.getElementById('cab_parcSearch').value     = dc.codparc
                            ? `${dc.codparc} — ${dc.nome_parc || ''}` : '';
                        document.getElementById('cab_codtipvenda').value    = dc.codtipvenda ?? '';
                        document.getElementById('cab_tipvendaSearch').value = dc.codtipvenda
                            ? `${dc.codtipvenda} — ${dc.descr_tipvenda || ''}` : '';
                        document.getElementById('cab_dtneg').value          = dc.dtneg || '';
                        document.getElementById('cab_obs').value            = dc.obs || '';
                    }
                } catch (_) { /* silencioso: reabre itens mesmo com cab desatualizado */ }
            }
            limparMarcasInvalidas();
            abrirItensAoLado();
            return;
        }
        await fecharTudo();
        carregarVendas(false);
    });

    // --- UX: destaque visual de campos obrigatórios no cabCard ---
    const CABCARD_CAMPOS_OBRIGATORIOS = [
        { hidden: 'cab_codparc',     visible: 'cab_parcSearch' },
        { hidden: 'cab_codtipvenda', visible: 'cab_tipvendaSearch' },
        { hidden: null,              visible: 'cab_dtneg' },
    ];
    function marcarCampoInvalido(inputId) {
        document.getElementById(inputId)?.classList.add('ph-field-invalid');
    }
    function limparMarcasInvalidas() {
        cabCard?.querySelectorAll('.ph-field-invalid')
               .forEach(el => el.classList.remove('ph-field-invalid'));
    }
    // Limpa a marca assim que o usuário começa a corrigir o campo
    CABCARD_CAMPOS_OBRIGATORIOS.forEach(({ visible }) => {
        document.getElementById(visible)?.addEventListener('input', function () {
            this.classList.remove('ph-field-invalid');
        });
    });

    // --- UX: seleciona todo o conteúdo ao focar um input (exceto textarea) ---
    cabCard?.querySelectorAll('input:not([type="hidden"])').forEach(el => {
        el.addEventListener('focus', function () {
            if (this.disabled || this.readOnly) return;
            // setTimeout evita que o clique do mouse desfaça a seleção
            setTimeout(() => { try { this.select(); } catch (_) {} }, 0);
        });
    });

    // --- Atalhos de teclado no cabCard: Enter salva, Esc cancela ---
    //     Ignora Enter dentro do textarea (Observação) e enquanto houver dropdown aberto.
    function hasDropdownCabAberto() {
        return Array.from(cabCard?.querySelectorAll('.dropdown-abs') || [])
            .some(dd => dd.style.display === 'block');
    }
    cabCard?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            if (e.target.tagName === 'TEXTAREA') return;
            if (hasDropdownCabAberto()) return; // attachTA consome
            e.preventDefault();
            document.getElementById('cabSave')?.click();
        } else if (e.key === 'Escape') {
            if (hasDropdownCabAberto()) return; // deixa o typeahead fechar o dropdown primeiro
            e.preventDefault();
            document.getElementById('cabCancel')?.click();
        }
    });

    // --- Salva cabeçalho e avança para o modal de itens ---
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
                // --- UPDATE: pedido existente ---
                const nunotaAtual = parseInt(document.getElementById('cab_nunota').value, 10);
                if (!nunotaAtual) { phToast('NUNOTA ausente.', 'error'); return; }
                const res = await phPostJSON('/sankhya/venda/api/cabecalho/editar/',
                    { nunota: nunotaAtual, codemp, codparc, codtipvenda, dtneg, obs });
                if (!res.ok || !res.body?.ok) {
                    phToast(res.body?.error || 'Falha ao atualizar cabeçalho.', 'error');
                    return;
                }
                modoEdicaoCabecalho = false;
                abrirItensAoLado(); // trava inputs + reabre itens ao lado
                phToast(`Cabeçalho do pedido ${nunotaAtual} atualizado.`, 'success');
            } else {
                // --- INSERT: pedido novo ---
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
                document.getElementById('itemsListBody').innerHTML =
                    '<tr><td colspan="6" class="ph-placeholder">Nenhum item inserido.</td></tr>';
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

    // --- Botão "Editar Cabeçalho" (substitui o Faturar) ---
    //     Fecha o modal de itens e destrava os inputs do cabCard.
    document.getElementById('btnEditCab')?.addEventListener('click', () => {
        if (!modoEdicao) return; // só faz sentido com pedido já aberto
        modoEdicaoCabecalho = true;
        if (cabItemsCard) cabItemsCard.style.left = '100%';
        setTimeout(() => { if (cabItemsModal) cabItemsModal.style.display = 'none'; }, 320);
        restaurarInputsCabecalho();
        limparMarcasInvalidas();
        setTimeout(() => document.getElementById('cab_parcSearch')?.focus(), 160);
    });

    // --- Reativo: Qtd × Preço → Total ---
    function atualizarTotalItem() {
        const q = parseFloat(document.getElementById('item_qtd').value) || 0;
        const p = parseFloat(document.getElementById('item_preco').value) || 0;
        document.getElementById('item_total_venda').value =
            (q * p).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
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

    // --- Adicionar item ao pedido ---
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
            const res = await phPostJSON('/sankhya/venda/api/item/', {
                nunota, codprod, qtdneg, vlrunit, codvol, codagregacao: lote,
            });
            if (!res.ok || !res.body?.ok) {
                phToast(res.body?.error || 'Falha ao adicionar item.', 'error');
                return;
            }

            // Remove placeholder se presente, anexa linha nova
            const tbody = document.getElementById('itemsListBody');
            if (tbody.querySelector('.ph-placeholder')) tbody.innerHTML = '';
            const prodDescr = document.getElementById('item_prod_vis').value;
            const tr = document.createElement('tr');
            const total = (qtdneg * vlrunit).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            tr.innerHTML = `
                <td class="ph-truncate" title="${prodDescr}">${prodDescr}</td>
                <td>${lote || '—'}</td>
                <td class="text-right">${qtdneg.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                <td class="text-right">${vlrunit.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
                <td class="text-right">${total}</td>
                <td></td>
            `;
            tbody.appendChild(tr);
            itensInseridosCount++;

            limparCamposItem();
            document.getElementById('item_prod_vis')?.focus();
            phToast(`Item ${res.body.sequencia} adicionado.`, 'success');
        } finally {
            btn.disabled = false;
        }
    });

    // --- Fechar modais e atualizar a lista principal ---
    document.getElementById('itemsSave')?.addEventListener('click', async () => {
        await fecharTudo();
        carregarVendas(false);
    });

    // Inicia a tela
    inicializarDatas();
    carregarVendas(false);
});