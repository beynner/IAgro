/* =============================================================================
   Importação por E-mail — JS da tela de revisão
   Reusa helpers de window.IAgro (postJSON, confirmarAcao, debounce, showToast).
   Reusa typeaheads de empresa/parceiro/tipo de venda chamando os endpoints
   já existentes em /sankhya/empresa/search/, /parceiros/search/, /tipvenda/search/.
   ============================================================================= */
document.addEventListener('DOMContentLoaded', function () {
    const PH = window.IAgro || {};
    const phPostJSON = PH.postJSON;
    const phToast    = PH.showToast || function(m){ alert(m); };
    const phConfirm  = PH.confirmarAcao || (async (o) => Promise.resolve(window.confirm(o.mensagem)));

    // ============================================================
    // Estado
    // ============================================================
    let pedidoSelecionadoId = null;
    let pedidoAtual = null;       // payload completo carregado (cab + itens)
    let statusAtual = 'PENDENTE_REVISAO';

    // ============================================================
    // Refs
    // ============================================================
    const filaListaEl    = document.getElementById('emailFilaLista');
    const statusSelect   = document.getElementById('emailStatusFiltro');
    const refreshBtn     = document.getElementById('emailRefreshBtn');

    const detalheBody    = document.getElementById('emailDetalheBody');
    const emptyDetail    = detalheBody.querySelector('.email-empty-detail');
    const detalheConteudo= document.getElementById('emailDetalheConteudo');
    const detalheIdEl    = document.getElementById('emailDetalheId');
    const confiancaBadge = document.getElementById('emailConfiancaBadge');

    const pdfFrame       = document.getElementById('emailPdfFrame');

    const codparcEl      = document.getElementById('emailCodparc');
    const parcSearchEl   = document.getElementById('emailParcSearch');
    const parcDdEl       = document.getElementById('emailParcDropdown');

    const codempEl       = document.getElementById('emailCodemp');
    const empSearchEl    = document.getElementById('emailEmpSearch');
    const empDdEl        = document.getElementById('emailEmpDropdown');

    const codtipvendaEl  = document.getElementById('emailCodtipvenda');
    const tipvendaSearchEl = document.getElementById('emailTipvendaSearch');
    const tipvendaDdEl   = document.getElementById('emailTipvendaDropdown');
    const badgeTipvenda  = document.getElementById('emailBadgeTipvenda');

    const dtnegEl        = document.getElementById('emailDtneg');
    const observacaoEl   = document.getElementById('emailObservacao');

    const itensBodyEl    = document.getElementById('emailItensBody');
    const itensCountEl   = document.getElementById('emailItensCount');

    const llmDebugEl     = document.getElementById('emailLlmDebug');

    const descartarBtn   = document.getElementById('emailDescartarBtn');
    const reparserBtn    = document.getElementById('emailReparserBtn');
    const confirmarBtn   = document.getElementById('emailConfirmarBtn');

    // ============================================================
    // Typeahead genérico (mesmo pattern do venda.js)
    // ============================================================
    function attachTA(inpId, hidId, ddId, url, options) {
        const inp = document.getElementById(inpId);
        const hid = document.getElementById(hidId);
        const dd  = document.getElementById(ddId);
        if (!inp || !hid || !dd) return;
        let t = null;

        function hide() { dd.style.display = 'none'; dd.innerHTML = ''; }
        function show(items) {
            if (!items || !items.length) { hide(); return; }
            dd.innerHTML = items.map((it, idx) => {
                const cod = it.cod || it.codparc || it.codemp || it.codtipvenda;
                const desc = it.descr || it.nomeparc || it.nomefantasia || it.descrtipvenda || '';
                return `<div class="dd-item${idx === 0 ? ' active' : ''}" data-cod="${cod}" data-descr="${desc}">${cod} — ${desc}</div>`;
            }).join('');
            dd.style.display = 'block';
        }

        async function buscar() {
            const q = inp.value.trim();
            if (q.length < 1) { hide(); return; }
            try {
                const r = await fetch(`${url}?q=${encodeURIComponent(q)}&limit=${options.limit || 10}`,
                                     { credentials: 'same-origin' });
                const data = await r.json();
                show(data.results || data.items || data || []);
            } catch (e) { hide(); }
        }

        inp.addEventListener('input', () => {
            clearTimeout(t);
            t = setTimeout(buscar, 250);
        });

        dd.addEventListener('click', e => {
            const item = e.target.closest('.dd-item');
            if (!item) return;
            hid.value = item.dataset.cod;
            inp.value = `${item.dataset.cod} — ${item.dataset.descr}`;
            hide();
        });

        inp.addEventListener('blur', () => setTimeout(hide, 200));
    }

    attachTA('emailParcSearch',     'emailCodparc',     'emailParcDropdown',     '/sankhya/parceiros/search/', { limit: 15 });
    attachTA('emailEmpSearch',      'emailCodemp',      'emailEmpDropdown',      '/sankhya/empresa/search/',   { limit: 15 });
    attachTA('emailTipvendaSearch', 'emailCodtipvenda', 'emailTipvendaDropdown', '/sankhya/tipvenda/search/',  { limit: 15 });

    // ============================================================
    // Renderização da fila
    // ============================================================
    function classeConfianca(c) {
        const n = parseFloat(c) || 0;
        if (n >= 0.8) return 'alta';
        if (n >= 0.5) return 'media';
        return 'baixa';
    }

    function fmtData(s) {
        if (!s) return '—';
        const d = new Date(s);
        if (isNaN(d.getTime())) return s;
        return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
    }

    async function carregarFila() {
        filaListaEl.innerHTML = '<div class="email-empty">Carregando...</div>';
        try {
            const r = await fetch(`/sankhya/venda/api/email/listar/?status=${encodeURIComponent(statusAtual)}&limit=100`,
                                  { credentials: 'same-origin' });
            const data = await r.json();
            if (!data.ok) throw new Error(data.error || 'Falha listando');
            renderFila(data.rows || []);
        } catch (e) {
            filaListaEl.innerHTML = `<div class="email-empty" style="color:#dc2626">Erro: ${e.message}</div>`;
        }
    }

    function renderFila(rows) {
        if (!rows.length) {
            filaListaEl.innerHTML = '<div class="email-empty">Nenhum pré-pedido com este status.</div>';
            return;
        }
        filaListaEl.innerHTML = '';
        for (const r of rows) {
            const card = document.createElement('div');
            card.className = 'email-fila-card';
            if (r.id === pedidoSelecionadoId) card.classList.add('selected');
            card.dataset.id = r.id;
            const titulo = (r.remetente || '—').replace(/[<>]/g, '');
            const conf = parseFloat(r.llm_confianca_geral);
            const confTxt = isNaN(conf) ? '—' : `${Math.round(conf * 100)}%`;
            const confCls = isNaN(conf) ? 'baixa' : classeConfianca(conf);
            card.innerHTML = `
                <div class="email-fila-titulo" title="${titulo}">${titulo}</div>
                <div class="email-fila-meta">
                    <span class="email-fila-data">${fmtData(r.recebido_em)}</span>
                    <span class="email-confianca-pill ${confCls}">◐ ${confTxt}</span>
                </div>
            `;
            card.addEventListener('click', () => selecionar(r.id));
            filaListaEl.appendChild(card);
        }
    }

    // ============================================================
    // Renderização do detalhe
    // ============================================================
    async function selecionar(id) {
        pedidoSelecionadoId = id;
        // Marca card ativo
        filaListaEl.querySelectorAll('.email-fila-card').forEach(c => {
            c.classList.toggle('selected', String(c.dataset.id) === String(id));
        });
        emptyDetail.classList.add('hidden');
        detalheConteudo.classList.remove('hidden');
        detalheIdEl.textContent = '#' + id;
        try {
            const r = await fetch(`/sankhya/venda/api/email/${id}/`, { credentials: 'same-origin' });
            const data = await r.json();
            if (!data.ok) throw new Error(data.error || 'Falha obtendo detalhe');
            pedidoAtual = data.pedido;
            renderDetalhe(pedidoAtual);
        } catch (e) {
            phToast('Erro ao carregar detalhe: ' + e.message, 'error');
        }
    }

    function renderDetalhe(p) {
        // Confiança geral
        const conf = parseFloat(p.llm_confianca_geral);
        if (!isNaN(conf)) {
            const pct = Math.round(conf * 100);
            confiancaBadge.textContent = `◐ ${pct}%`;
            confiancaBadge.className = 'email-confianca-badge ' + classeConfianca(conf);
        } else {
            confiancaBadge.textContent = '';
            confiancaBadge.className = 'email-confianca-badge';
        }

        // PDF
        pdfFrame.src = `/sankhya/venda/api/email/${p.id}/pdf/`;

        // Cabeçalho — sugestões iniciais
        codparcEl.value = p.codparc_sugerido || '';
        parcSearchEl.value = p.codparc_sugerido ? `${p.codparc_sugerido}` : '';
        codempEl.value = p.codemp_sugerido || '';
        empSearchEl.value = p.codemp_sugerido ? `${p.codemp_sugerido}` : '';
        codtipvendaEl.value = p.codtipvenda_sugerido || '';
        tipvendaSearchEl.value = p.codtipvenda_sugerido ? `${p.codtipvenda_sugerido}` : '';

        // Badge "Sugerido — confirme" no tipo de venda
        if (p.codtipvenda_sugerido) {
            badgeTipvenda.classList.remove('hidden');
        } else {
            badgeTipvenda.classList.add('hidden');
        }

        // Data
        if (p.dtneg_sugerida) {
            dtnegEl.value = p.dtneg_sugerida.substring(0, 10);
        } else {
            dtnegEl.value = '';
        }

        // Observação
        observacaoEl.value = p.observacao_extraida || '';

        // Itens
        renderItens(p.itens || []);

        // Debug
        llmDebugEl.textContent = p.llm_resposta || '(sem resposta crua)';

        // Estado dos botões
        const bloqueado = (p.status === 'CONFIRMADO' || p.status === 'DESCARTADO');
        confirmarBtn.disabled = bloqueado;
        descartarBtn.disabled = bloqueado;
        reparserBtn.disabled  = (p.status === 'CONFIRMADO');
    }

    function renderItens(itens) {
        itensCountEl.textContent = `(${itens.length})`;
        if (!itens.length) {
            itensBodyEl.innerHTML = '<tr><td colspan="6" class="ia-placeholder">Sem itens.</td></tr>';
            return;
        }
        itensBodyEl.innerHTML = '';
        for (const it of itens) {
            const tr = document.createElement('tr');
            tr.dataset.itemId = it.id;
            const semProd = !it.codprod_final && !it.codprod_sugerido;
            if (semProd) tr.classList.add('alerta');

            tr.innerHTML = `
                <td>${(it.descricao_pdf || '').replace(/[<>]/g, '')}</td>
                <td><input type="number" class="email-it-codprod" value="${it.codprod_final || it.codprod_sugerido || ''}" placeholder="CODPROD" title="CODPROD"></td>
                <td class="text-right"><input type="number" step="0.001" class="email-it-qtd" value="${it.qtd || ''}"></td>
                <td><input type="text" class="email-it-vol" value="${it.codvol || ''}" maxlength="10"></td>
                <td class="text-right"><input type="number" step="0.01" class="email-it-preco" value="${it.preco_unit || ''}"></td>
                <td>
                    <button type="button" class="email-trash-btn" title="Remover item" data-item-id="${it.id}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                        </svg>
                    </button>
                </td>
            `;
            itensBodyEl.appendChild(tr);
        }

        // Liga handlers de edição inline
        itensBodyEl.querySelectorAll('input').forEach(inp => {
            inp.addEventListener('change', onItemChange);
        });
        itensBodyEl.querySelectorAll('.email-trash-btn').forEach(btn => {
            btn.addEventListener('click', onItemRemove);
        });
    }

    async function onItemChange(e) {
        const tr = e.target.closest('tr');
        const itemId = parseInt(tr.dataset.itemId, 10);
        const codprod = parseInt(tr.querySelector('.email-it-codprod').value, 10) || null;
        const qtd     = parseFloat(tr.querySelector('.email-it-qtd').value) || null;
        const vol     = (tr.querySelector('.email-it-vol').value || '').toUpperCase().trim() || null;
        const preco   = parseFloat(tr.querySelector('.email-it-preco').value) || null;

        try {
            const r = await phPostJSON(`/sankhya/venda/api/email/item/${itemId}/editar/`, {
                CODPROD_FINAL: codprod, QTD: qtd, CODVOL: vol, PRECO_UNIT: preco,
            });
            if (!r.ok || (r.body && !r.body.ok)) {
                phToast('Erro salvando item: ' + ((r.body && r.body.error) || 'falha'), 'error');
            } else {
                tr.classList.toggle('alerta', !codprod);
            }
        } catch (e) {
            phToast('Erro: ' + e.message, 'error');
        }
    }

    async function onItemRemove(e) {
        const btn = e.currentTarget;
        const itemId = parseInt(btn.dataset.itemId, 10);
        const ok = await phConfirm({
            titulo: 'Remover item',
            mensagem: 'Deseja remover este item do pré-pedido?',
            tipo: 'perigo',
        });
        if (!ok) return;
        try {
            const r = await phPostJSON(`/sankhya/venda/api/email/item/${itemId}/remover/`, {});
            if (!r.ok || (r.body && !r.body.ok)) {
                phToast('Erro removendo: ' + ((r.body && r.body.error) || 'falha'), 'error');
                return;
            }
            // recarrega o detalhe
            await selecionar(pedidoSelecionadoId);
        } catch (e) {
            phToast('Erro: ' + e.message, 'error');
        }
    }

    // ============================================================
    // Ações de cabeçalho: descartar / reparser / confirmar
    // ============================================================
    descartarBtn.addEventListener('click', async () => {
        if (!pedidoSelecionadoId) return;
        const motivo = window.prompt('Motivo do descarte (opcional):', '');
        if (motivo === null) return; // cancelou
        const ok = await phConfirm({
            titulo: 'Descartar pré-pedido',
            mensagem: 'Tem certeza? Esta ação não cria pedido na TGFCAB.',
            tipo: 'perigo',
        });
        if (!ok) return;
        try {
            const r = await phPostJSON(`/sankhya/venda/api/email/${pedidoSelecionadoId}/descartar/`, { motivo });
            if (!r.ok || (r.body && !r.body.ok)) {
                phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                return;
            }
            phToast('Pré-pedido descartado.', 'success');
            pedidoSelecionadoId = null;
            await carregarFila();
            emptyDetail.classList.remove('hidden');
            detalheConteudo.classList.add('hidden');
            detalheIdEl.textContent = '—';
            confiancaBadge.textContent = '';
        } catch (e) { phToast('Erro: ' + e.message, 'error'); }
    });

    reparserBtn.addEventListener('click', async () => {
        if (!pedidoSelecionadoId) return;
        const ok = await phConfirm({
            titulo: 'Reparser',
            mensagem: 'Re-rodar o parser LLM neste pré-pedido? Os itens atuais serão apagados e o worker recria na próxima rodada.',
            tipo: 'aviso',
        });
        if (!ok) return;
        try {
            const r = await phPostJSON(`/sankhya/venda/api/email/${pedidoSelecionadoId}/reparser/`, {});
            if (!r.ok || (r.body && !r.body.ok)) {
                phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                return;
            }
            phToast(r.body.mensagem || 'Reparser agendado.', 'success');
            await carregarFila();
        } catch (e) { phToast('Erro: ' + e.message, 'error'); }
    });

    confirmarBtn.addEventListener('click', async () => {
        if (!pedidoSelecionadoId) return;
        // Validação básica antes de chamar API de confirmação (E7)
        if (!codparcEl.value) { phToast('Selecione o cliente.', 'warning'); return; }
        if (!codempEl.value) { phToast('Selecione a empresa.', 'warning'); return; }
        if (!codtipvendaEl.value) { phToast('Selecione o tipo de negociação.', 'warning'); return; }
        if (!dtnegEl.value) { phToast('Informe a data de negociação.', 'warning'); return; }

        // Validação de itens
        const trs = itensBodyEl.querySelectorAll('tr[data-item-id]');
        if (!trs.length) { phToast('Nenhum item para confirmar.', 'warning'); return; }
        for (const tr of trs) {
            const codp = tr.querySelector('.email-it-codprod').value;
            if (!codp) {
                phToast('Existe item sem CODPROD definido.', 'warning');
                tr.classList.add('alerta');
                return;
            }
        }

        const ok = await phConfirm({
            titulo: 'Confirmar pré-pedido',
            mensagem: 'Vai criar pedido TOP 34 na TGFCAB com os dados acima. Confirma?',
            tipo: 'info',
        });
        if (!ok) return;

        const payload = {
            codparc:     parseInt(codparcEl.value, 10),
            codemp:      parseInt(codempEl.value, 10),
            codtipvenda: parseInt(codtipvendaEl.value, 10),
            dtneg:       dtnegEl.value,
            observacao:  observacaoEl.value || '',
        };
        try {
            const r = await phPostJSON(`/sankhya/venda/api/email/${pedidoSelecionadoId}/confirmar/`, payload);
            if (!r.ok || (r.body && !r.body.ok)) {
                phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                return;
            }
            phToast(`Pedido ${r.body.nunota} criado!`, 'success');
            pedidoSelecionadoId = null;
            await carregarFila();
            emptyDetail.classList.remove('hidden');
            detalheConteudo.classList.add('hidden');
            detalheIdEl.textContent = '—';
            confiancaBadge.textContent = '';
        } catch (e) { phToast('Erro: ' + e.message, 'error'); }
    });

    // ============================================================
    // Eventos gerais
    // ============================================================
    statusSelect.addEventListener('change', () => {
        statusAtual = statusSelect.value;
        pedidoSelecionadoId = null;
        emptyDetail.classList.remove('hidden');
        detalheConteudo.classList.add('hidden');
        detalheIdEl.textContent = '—';
        confiancaBadge.textContent = '';
        carregarFila();
    });
    refreshBtn.addEventListener('click', carregarFila);

    // ============================================================
    // Boot
    // ============================================================
    carregarFila();
});
