(function () {
    'use strict';
    let ultimaUrlFiltrada = '';
    let lotesExibidos = new Set();

    // Importa as ferramentas do Helpers
    const { getCookie, postJSON, showToast, debounce: debounceHelper } = window.IAgro || {};
    const URL_API_LOTES = "/sankhya/compras/classificacao/api/lotes/";

    // =================================================================
    // 1. ESTADO E CACHE
    // =================================================================
    let currentPage = 1;
    let isLoadingMore = false;
    let hasMoreRows = true;
    let currentAbortController = null;
    let state = {
        selectedLote: null,
        isLoading: false,
        editingItemSeq: null,
    };
    const lotesCache = {};

    // --- FUNÇÃO DE CARREGAMENTO DOS LOTES (AJAX) ---
    window.carregarTabelaLotes = async () => {
        const tbody = document.querySelector('#notasTable tbody') || document.querySelector('#notasTable');
        if (!tbody) return;

        // 1. Lendo os Checkboxes
        const statusVerde = document.getElementById('filterGreen')?.checked;
        const statusAmarelo = document.getElementById('filterYellow')?.checked;
        const statusRed = document.getElementById('filterRed')?.checked;

        // 2. Lendo os Campos de Texto e Data
        const txtLote = document.getElementById('loteHidden')?.value || '';
        const txtPedido = document.getElementById('pedidoHidden')?.value || '';
        const txtParceiro = document.getElementById('codparc')?.value || '';
        const txtFabricante = document.getElementById('fabricanteHidden')?.value || '';
        const txtStart = document.querySelector('input[name="start"]')?.value || '';
        const txtEnd = document.querySelector('input[name="end"]')?.value || '';

        // 3. Montando a URL
        let urlFetch = URL_API_LOTES + "?";
        if (statusAmarelo) urlFetch += "status=AMARELO&";
        if (statusRed) urlFetch += "status=VERMELHO&";
        if (statusVerde) urlFetch += "status=VERDE&";

        if (txtLote) urlFetch += `lote=${encodeURIComponent(txtLote)}&`;
        if (txtPedido) urlFetch += `nunota_ini=${encodeURIComponent(txtPedido)}&`;
        if (txtParceiro) urlFetch += `codparc=${encodeURIComponent(txtParceiro)}&`;
        if (txtFabricante) urlFetch += `fabricante=${encodeURIComponent(txtFabricante)}&`;
        if (txtStart) urlFetch += `date_start=${encodeURIComponent(txtStart)}&`;
        if (txtEnd) urlFetch += `date_end=${encodeURIComponent(txtEnd)}&`;

        currentPage = 1;
        hasMoreRows = true;
        if (typeof notasListDiv !== 'undefined' && notasListDiv) notasListDiv.scrollTop = 0;

        try {
            const response = await fetch(urlFetch);
            const data = await response.json();

            if (data.ok && data.lotes && data.lotes.length > 0) {
                tbody.innerHTML = data.lotes.map(item => {
                    const totalKg = item.qtd_cx * item.peso_unit;

                    return `
                        <tr class="row--click" data-nunota="${item.nunota_origem}">
                            <td style="width: 40px; text-align:center;"><span class="status-dot status-${item.status.toLowerCase()}"></span></td>
                            <td style="width: 80px;">${item.nunota_origem}</td>
                            <td style="width: 100px;">${item.data}</td>
                            <td style="width: 150px;">${item.parceiro}</td>
                            <td style="white-space: nowrap;">${item.produto}</td>
                            <td style="width: 110px; text-align:right;">${item.qtd_cx.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</td>
                            <td style="width: 110px; text-align:right;">${item.peso_unit.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</td>
                            <td style="width: 120px; text-align:right; font-weight: bold;">${totalKg.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} kg</td>
                            <td style="width: 160px; text-align:right; white-space: nowrap;">${item.lote}</td>
                        </tr>
                    `;
                }).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px;">Nenhum lote encontrado.</td></tr>`;
            }
        } catch (err) {
            console.error("🚨 Erro na busca:", err);
        }
    };

    window.ajustarDescarte = function (operacao) {
        if (window.PH_BLOQUEADO_COMERCIAL) {
            if (window.mostrarToast) window.mostrarToast("🔒 Lote bloqueado pelo Comercial!", "error");
            return;
        }

        if (window.PH_LOTE_FINALIZADO) {
            if (window.mostrarToast) window.mostrarToast("🔒 Lote finalizado! Ajuste de descarte bloqueado.", "error");
            return;
        }

        const lote = document.getElementById('cab_lote_text')?.textContent ||
            document.querySelector('#notasTable tr.selected td:nth-child(2)')?.textContent.trim();

        if (!lote || lote === '—') {
            window.mostrarToast("Erro: Selecione um lote na tabela antes de ajustar o descarte.", "error");
            return;
        }

        const modal = document.getElementById('modalDescarte');
        const inputField = document.getElementById('descarteInput');
        const title = document.getElementById('modalDescarteTitle');
        const btnConfirmar = document.getElementById('modalDescarteConfirmar');

        if (!modal || !inputField) return;

        title.textContent = operacao === 'soma' ? 'Adicionar Descarte ao Lote' : 'Remover Descarte do Lote';
        inputField.value = '';

        modal.style.display = 'flex';
        setTimeout(() => inputField.focus(), 100);

        document.getElementById('modalDescarteCancelar').onclick = () => { modal.style.display = 'none'; };

        btnConfirmar.onclick = async () => {
            const valor = parseFloat(inputField.value.replace(',', '.'));
            if (isNaN(valor) || valor <= 0) {
                window.mostrarToast("Insira um valor válido.", "error");
                return;
            }

            modal.style.display = 'none';
            if (window.IAOverlay) window.IAOverlay.show();

            try {
                const response = await postJSON('/sankhya/item/update_descarte_lote/', { lote, valor, operacao });

                if (response && response.ok) {
                    window.mostrarToast("Descarte do Lote atualizado!", "success");

                    const campoModal = document.getElementById('descarteTotal') ||
                        document.querySelector('[name="descarteTotal"]') ||
                        document.querySelector('.descarte-input');

                    const novoTotal = response.body ? response.body.novo_total_lote : response.novo_total_lote;

                    if (campoModal && novoTotal !== undefined) {
                        const valorFormatado = novoTotal.toLocaleString('pt-BR', {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1
                        });

                        campoModal.value = valorFormatado;
                    }

                    if (typeof lotesCache !== 'undefined') delete lotesCache[lote];
                    await window.loadClassifiedFor(lote, null);

                } else {
                    throw new Error(response.error || "Erro no servidor.");
                }
            } catch (e) {
                window.mostrarToast(e.message, "error");
            } finally {
                if (window.IAOverlay) window.IAOverlay.hide();
            }
        };
    };

    // =================================================================
    // COMPONENTE VISUAL: TOAST NOTIFICATION 
    // =================================================================
    window.mostrarToast = function (mensagem, tipo = 'success') {
        const oldToast = document.getElementById('ia-toast-global');
        if (oldToast) oldToast.remove();

        const toast = document.createElement('div');
        toast.id = 'ia-toast-global';
        toast.textContent = mensagem;

        const bgColor = tipo === 'success' ? '#28a745' : '#dc3545';

        Object.assign(toast.style, {
            position: 'fixed', bottom: '20px', right: '20px', backgroundColor: bgColor,
            color: '#fff', padding: '16px 24px', borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)', fontSize: '15px', fontWeight: 'bold',
            zIndex: '999999', opacity: '0', transform: 'translateY(20px)',
            transition: 'all 0.3s ease-out', fontFamily: 'sans-serif'
        });

        document.body.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '1'; toast.style.transform = 'translateY(0)'; }, 10);
        setTimeout(() => {
            toast.style.opacity = '0'; toast.style.transform = 'translateY(20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // =================================================================
    // 2. FUNÇÕES DE NEGÓCIO E FORMATADORES
    // =================================================================
    function formatNumber(value, digits = 1) {
        const num = Number(value);
        if (isNaN(num)) return (0).toLocaleString('pt-BR', { minimumFractionDigits: digits });
        return num.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }

    function parsePtBrNumber(value) {
        if (typeof value !== 'string' || !value.trim()) return null;
        try {
            const cleaned = value.replace(/\./g, '').replace(',', '.');
            const num = parseFloat(cleaned);
            return isNaN(num) ? null : num;
        } catch (e) {
            return null;
        }
    }

    function setClassificacaoFinalizada(isFinalizado) {
        const watermark = document.getElementById('produtosClassificadosWatermark');
        const panel = document.getElementById('produtosClassificadosPanel');
        if (watermark) watermark.classList.toggle('is-visible', isFinalizado);
        if (panel) panel.classList.toggle('is-finalizado', isFinalizado);
    }

    function updateResumoClassificacao(data) {
        if (!data) return;
        const totalInNaturaKg = (data.entradas || []).reduce((sum, item) => sum + (Number(item.qtd) || 0), 0);
        const totalClassificadoKg = (data.classificacoes || []).reduce((sum, item) => sum + (Number(item.qtd) || 0), 0);

        const totalDescarteKg = Number(data.qtdbatidas || data.descarte || (data.agregados && data.agregados.descarte) || (data.agregados && data.agregados.qtdbatidas) || 0);
        const estoqueKg = totalInNaturaKg - (totalClassificadoKg + totalDescarteKg);

        const pctClassificado = totalInNaturaKg > 0 ? (totalClassificadoKg / totalInNaturaKg) * 100 : 0;
        const pctDescarte = totalInNaturaKg > 0 ? (totalDescarteKg / totalInNaturaKg) * 100 : 0;
        const pctEstoque = totalInNaturaKg > 0 ? (estoqueKg / totalInNaturaKg) * 100 : 0;

        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        setVal('resumoInNatura', formatNumber(totalInNaturaKg));
        setVal('resumoClassificado', formatNumber(totalClassificadoKg));
        setVal('resumoDescarte', formatNumber(totalDescarteKg));
        setVal('resumoEstoque', formatNumber(estoqueKg));
        setVal('resumoClassificadoPct', `${formatNumber(pctClassificado, 0)}%`);
        setVal('resumoDescartePct', `${formatNumber(pctDescarte, 0)}%`);
        setVal('resumoEstoquePct', `${formatNumber(pctEstoque, 0)}%`);
    }

    // ==============================================================================
    // 🖱️ GERENCIAMENTO DE CLIQUES E DETALHES (PRODUTOS CLASSIFICADOS E RESUMO)
    // ==============================================================================
    window.loadClassifiedFor = async (lote, nunotaOrigem) => {
        const tbodyClassificados = document.getElementById('prodClassBody');
        if (!tbodyClassificados) return;

        tbodyClassificados.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:15px;">Carregando...</td></tr>';

        try {
            const url = `/sankhya/compras/classificacao/api/detalhes/?lote=${encodeURIComponent(lote)}&nunota_origem=${nunotaOrigem}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.ok) {
                // --- ATUALIZA TABELA DE ITENS ---
                if (data.itens && data.itens.length > 0) {
                    tbodyClassificados.innerHTML = data.itens.map(item => `
                        <tr>
                            <td>${item.lote}</td>
                            <td style="text-align:center;">${item.seq}</td>
                            <td>${item.produto}</td>
                            <td style="text-align:right;">${item.total_cx.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} cx</td>
                            <td style="text-align:right;">${item.peso.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</td>
                            <td style="text-align:right; font-weight:bold;">${item.total_kg.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} kg</td>
                        </tr>
                    `).join('');
                } else {
                    tbodyClassificados.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px;">Nenhum item classificado.</td></tr>';
                }

                // --- ATUALIZA RESUMO ---
                if (data.resumo) {
                    const r = data.resumo;
                    const setKg = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }); };
                    const setPct = (id, valKg) => { const el = document.getElementById(id); if (el) { const pct = r.in_natura > 0 ? (valKg / r.in_natura) * 100 : 0; el.innerText = pct.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%'; } };
                    const setCx = (id, valKg) => { const el = document.getElementById(id); if (el) { const cx = r.in_natura > 0 ? (valKg / r.in_natura) * r.cx_in_natura : 0; el.innerText = Math.round(cx).toLocaleString('pt-BR') + ' cx'; } };

                    setKg('resumoInNatura', r.in_natura);
                    setKg('resumoClassificado', r.classificado);
                    setKg('resumoEstoque', r.estoque);
                    setKg('resumoDescarte', r.descarte);
                    setPct('resumoClassificadoPct', r.classificado);
                    setPct('resumoEstoquePct', r.estoque);
                    setPct('resumoDescartePct', r.descarte);

                    const elInNaturaCx = document.getElementById('resumoInNaturaCx');
                    if (elInNaturaCx) elInNaturaCx.innerText = r.cx_in_natura.toLocaleString('pt-BR') + ' cx';
                    setCx('resumoClassificadoCx', r.classificado);
                    setCx('resumoEstoqueCx', r.estoque);

                    // 💾 GUARDA O FABRICANTE NA MEMÓRIA
                    window.PH_FABRICANTE = r.fabricante || '';
                    console.log("🏭 Fabricante do lote atual:", window.PH_FABRICANTE);

                    // 👇 NOVO: ATUALIZA O CARIMBO "FINALIZADO" NO RESUMO 👇
                    let isFinalizado = (data.pendente_class === 'N' || r.pendente === 'N');

                    // Fallback: Se o Python não mandar o status, lê a cor da bolinha verde na tabela
                    if (!isFinalizado) {
                        const linhasTabela = document.querySelectorAll('#notasTable tbody tr.row--click');
                        for (let lin of linhasTabela) {
                            // Mai/2026 — coluna Lote agora é a última (era cells[1])
                            if (lin.cells.length > 0 && lin.cells[lin.cells.length - 1].innerText.trim() === lote) {
                                if (lin.querySelector('.status-verde')) isFinalizado = true;
                                break;
                            }
                        }
                    }

                    if (typeof setClassificacaoFinalizada === 'function') {
                        setClassificacaoFinalizada(isFinalizado);
                    }
                } // fim do if (data.resumo)
            }
        } catch (err) {
            console.error("🚨 Erro:", err);
            tbodyClassificados.innerHTML = '<tr><td colspan="7" style="text-align:center; color:red;">Erro ao processar dados.</td></tr>';
        }
    };

    // =================================================================
    // 3. FLUXO DE SALVAMENTO ATÔMICO 
    // =================================================================
    window.saveItem = async function (event) {
        if (event) event.preventDefault();

        if (window.PH_BLOQUEADO_COMERCIAL) {
            if (window.mostrarToast) window.mostrarToast("🔒 Lote bloqueado pelo Comercial!", "error");
            return;
        }

        if (window.PH_LOTE_FINALIZADO) {
            if (window.mostrarToast) window.mostrarToast("🔒 Classificação finalizada! Inclusão e edição bloqueadas.", "error");
            return;
        }

        const btnClicked = event.target ? event.target.closest('button') : null;
        const isEditModal = btnClicked && btnClicked.id === 'itemModalSave';

        const ids = isEditModal ? {
            prod: 'itemProdHidden', vol: 'itemVol', totalKg: 'itemTotalKg',
            peso: 'itemPeso', obs: 'itemObs', seq: 'itemSeqHidden'
        } : {
            prod: 'item_prod_hidden', vol: 'item_vol', totalKg: 'item_total',
            peso: 'item_peso', obs: 'item_obs', seq: 'item_seq_edit'
        };

        const getVal = (id) => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };

        const codprod = getVal(ids.prod);
        const codvol = getVal(ids.vol) ? getVal(ids.vol).toUpperCase() : 'KG';
        const totalKgStr = getVal(ids.totalKg);
        const pesoStr = getVal(ids.peso);
        const obs = getVal(ids.obs);
        const seqStr = getVal(ids.seq);
        const isEdit = seqStr !== '';

        // 🎯 1. PEGA O LOTE ATUAL (Prioriza as variáveis do Modal)
        let loteAtual = window.LOTE_ATUAL_ABERTO || state.selectedLote;
        if (!loteAtual) {
            const rowActive = document.querySelector('#notasTable tr.row--active');
            if (rowActive) loteAtual = rowActive.dataset.nunota;
        }

        // 👇 NOVO: Remove TODOS os pontos de milhar antes de trocar a vírgula por ponto decimal
        let totalKg = 0;
        if (totalKgStr) totalKg = parseFloat(totalKgStr.replace(/\./g, '').replace(',', '.')) || 0;

        let peso = 0;
        if (pesoStr) peso = parseFloat(pesoStr.replace(/\./g, '').replace(',', '.')) || 0;

        // 👇 NOVO: Trava de Segurança "PESO CX" Obrigatório 👇
        if (peso <= 0 || isNaN(peso)) {
            if (window.mostrarToast) window.mostrarToast("O preenchimento do PESO CX é obrigatório!", "warning");

            // Dá um destaque visual no campo para o usuário ver onde errou
            const campoPeso = document.getElementById(ids.peso);
            if (campoPeso) {
                campoPeso.style.border = "2px solid #ef4444";
                campoPeso.focus();
                setTimeout(() => campoPeso.style.border = "1px solid #cbd5e1", 3000);
            }
            return; // 🛑 Interrompe a função aqui e não salva no banco!
        }

        if (!codprod || totalKg <= 0 || isNaN(totalKg)) {
            alert(`Validação Falhou!\nProduto Lido: '${codprod}'\nTotal KG Lido: '${totalKg}'`);
            return;
        }

        // 🎯 2. O GRANDE SEGREDO: Pega as notas direto da memória
        const activeRow = document.querySelector(`tr[data-nunota="${loteAtual}"]`);

        let nunotaPortal = window.NUNOTA_ORIGEM_ATUAL;
        let codparc = window.CODPARC_ATUAL;
        if (activeRow) {
            if (!nunotaPortal) nunotaPortal = activeRow.dataset.nunotaPortal;
            if (!codparc) codparc = activeRow.dataset.codparc;
        }

        // 🔧 nunotaClass vem SOMENTE de fontes específicas do lote atual (dataset → input hidden).
        // window.NUNOTA_CLASS_ATUAL é deliberadamente ignorada aqui — ela podia carregar a NUNOTA
        // do lote anterior e fazer o item do novo lote ser inserido na TGFCAB do lote anterior.
        let nunotaClass = (activeRow && activeRow.dataset.nunotaTop26) || '';
        if (!nunotaClass || nunotaClass === "undefined") {
            const hiddenInput = document.getElementById('items_nunota');
            if (hiddenInput && hiddenInput.value) nunotaClass = hiddenInput.value;
        }

        if (window.IAOverlay) window.IAOverlay.show();

        try {
            if (!nunotaClass || nunotaClass === "undefined" || nunotaClass === "") {
                const cabResponse = await postJSON('/sankhya/compras/central/salvar/', {
                    codemp: '10',
                    codparc: codparc || '0',
                    codtipoper: '26',
                    codnat: '20010100',
                    dtneg: new Date().toISOString().split('T')[0],
                    nunota_origem: nunotaPortal,
                    numnota: nunotaPortal,
                    codcencus: 10100
                });

                if (cabResponse.ok && cabResponse.body.nunota) {
                    nunotaClass = cabResponse.body.nunota;
                    if (activeRow) activeRow.dataset.nunotaTop26 = nunotaClass;
                    window.NUNOTA_CLASS_ATUAL = nunotaClass;
                    const hiddenInput = document.getElementById('items_nunota');
                    if (hiddenInput) hiddenInput.value = nunotaClass;
                } else {
                    throw new Error(cabResponse.body.error || "Falha ao criar cabeçalho TOP 26.");
                }
            }

            const payloadItem = {
                nunota: parseInt(nunotaClass, 10),
                sequencia: isEdit ? parseInt(seqStr, 10) : null,
                codprod: parseInt(codprod, 10),
                qtdneg: totalKg,
                vlrunit: "0",
                vlrtot: "0",
                codvol: codvol,
                peso: peso,
                obs: obs,
                codagregacao: loteAtual,
                geraproducao: 'N',
                codcencus: 10100,

                // Duplicado em maiúsculo por segurança (seu código original fazia isso)
                NUNOTA: parseInt(nunotaClass, 10),
                SEQUENCIA: isEdit ? parseInt(seqStr, 10) : null,
                CODPROD: parseInt(codprod, 10),
                QTDNEG: totalKg,
                VLRUNIT: "0",
                VLRTOT: "0",
                CODVOL: codvol,
                PESO: peso,
                OBS: obs,
                CODAGREGACAO: loteAtual,
                GERAPRODUCAO: 'N',
                CODCENCUS: 10100
            };

            const endpoint = '/sankhya/item/save/';
            const itemResponse = await (window.postJSON || postJSON)(endpoint, payloadItem);

            if (itemResponse && itemResponse.ok) {
                window.mostrarToast("Item Salvo com sucesso!", "success");

                // Limpa os campos
                document.getElementById(ids.prod).value = '';
                const prodVis = document.getElementById(isEditModal ? 'itemProdCod' : 'item_prod_vis');
                if (prodVis) prodVis.value = '';
                document.getElementById(ids.totalKg).value = '';
                document.getElementById(ids.peso).value = '';
                document.getElementById(ids.obs).value = '';

                const campoQtdPortal = document.getElementById('item_qtd');
                if (campoQtdPortal) campoQtdPortal.value = '';
                const campoQtdModal = document.getElementById('itemQtd');
                if (campoQtdModal) campoQtdModal.value = '';
                if (document.getElementById(ids.seq)) document.getElementById(ids.seq).value = '';

                // 🔄 1. Atualiza o resumo lateral instantaneamente
                if (typeof lotesCache !== 'undefined') delete lotesCache[loteAtual];
                await window.loadClassifiedFor(loteAtual, nunotaPortal);

                // 🔄 2. Redesenha a lista DE ITENS DENTRO DO MODAL puxando dados novos
                try {
                    const modalRes = await fetch(`/sankhya/lote/consultar/?lote=${encodeURIComponent(loteAtual)}&full=1`);
                    const modalData = await modalRes.json();
                    if (modalData.ok && typeof window.populateItemsModal === 'function') {
                        window.populateItemsModal(modalData);
                    }
                } catch (e) {
                    console.error('Erro ao atualizar tabela do modal:', e);
                }

                if (isEditModal) {
                    const closeBtn = document.getElementById('itemModalCancel');
                    if (closeBtn) closeBtn.click();
                }
            } else {
                const erroMsg = (itemResponse.body && itemResponse.body.error) ? itemResponse.body.error : itemResponse.error;
                throw new Error(erroMsg || 'Erro ao inserir o item no Sankhya.');
            }
        } catch (error) {
            console.error("🚨 ERRO:", error);
            window.mostrarToast("ERRO: " + error.message, "error");
        } finally {
            if (window.IAOverlay) window.IAOverlay.hide();
        }
    };

    // =================================================================
    // 4. INICIALIZAÇÃO DA TELA & GATILHOS (DOM Content Loaded)
    // =================================================================
    document.addEventListener('DOMContentLoaded', () => {
        // --- Delegação Global de Salvamento ---
        document.addEventListener('click', async function (event) {
            const btn = event.target.closest('#itemModalSave, #itemAddBtn');
            if (!btn) return;
            event.preventDefault();
            if (typeof window.saveItem === 'function') {
                await window.saveItem(event);
            }
        });

        // --- Botões de Descarte ---
        const btnMaisDescarte = document.querySelector('.btn-descarte-mais');
        const btnMenosDescarte = document.querySelector('.btn-descarte-menos');
        if (btnMaisDescarte) btnMaisDescarte.onclick = () => window.ajustarDescarte('soma');
        if (btnMenosDescarte) btnMenosDescarte.onclick = () => window.ajustarDescarte('subtrai');
        const addBtn = document.getElementById('btnDescarteAdd');
        const subBtn = document.getElementById('btnDescarteSub');
        if (addBtn) addBtn.onclick = () => window.ajustarDescarte('soma');
        if (subBtn) subBtn.onclick = () => window.ajustarDescarte('subtrai');

        // --- Recálculos de Item ---
        const itemQtdInput = document.getElementById('itemQtd');
        const itemPesoInput = document.getElementById('itemPeso');
        const itemTotalKgInput = document.getElementById('itemTotalKg');

        function recalcItemFields(source) {
            const qtd = parseFloat(itemQtdInput.value) || 0;
            const peso = parseFloat(itemPesoInput.value) || 0;
            const totalKg = parseFloat(itemTotalKgInput.value) || 0;
            setTimeout(() => {
                if ((source === 'total' || source === 'peso') && totalKg > 0 && peso > 0) {
                    if (itemQtdInput && document.activeElement !== itemQtdInput) itemQtdInput.value = Math.round(totalKg / peso);
                } else if (source === 'qtd' && qtd > 0 && totalKg > 0) {
                    if (itemPesoInput && document.activeElement !== itemPesoInput) itemPesoInput.value = (totalKg / qtd).toFixed(3);
                }
            }, 100);
        }
        if (itemQtdInput) itemQtdInput.addEventListener('input', () => recalcItemFields('qtd'));
        if (itemPesoInput) itemPesoInput.addEventListener('input', () => recalcItemFields('peso'));
        if (itemTotalKgInput) itemTotalKgInput.addEventListener('input', () => recalcItemFields('total'));

        // --- Tabela Lotes: Scroll Infinito ---
        const notasTable = document.getElementById('notasTable');
        const notasListDiv = document.getElementById('notasList');

        if (notasListDiv) {
            notasListDiv.addEventListener('scroll', async () => {
                const { scrollTop, scrollHeight, clientHeight } = notasListDiv;

                if (scrollHeight - scrollTop - clientHeight < 150 && !isLoadingMore && hasMoreRows) {
                    isLoadingMore = true;
                    currentPage++;

                    const apiUrl = '/sankhya/compras/classificacao/api/lotes/';
                    const params = new URLSearchParams();

                    params.set('page', currentPage);
                    params.set('codparc', document.getElementById('codparc')?.value || '');
                    params.set('lote', document.getElementById('loteHidden')?.value || '');
                    params.set('fabricante', document.getElementById('fabricanteHidden')?.value || '');
                    params.set('date_start', document.querySelector('input[name="start"]')?.value || '');
                    params.set('date_end', document.querySelector('input[name="end"]')?.value || '');

                    if (document.getElementById('filterGreen')?.checked) params.append('status', 'VERDE');
                    if (document.getElementById('filterYellow')?.checked) params.append('status', 'AMARELO');
                    if (document.getElementById('filterRed')?.checked) params.append('status', 'VERMELHO');

                    try {
                        const response = await fetch(`${apiUrl}?${params.toString()}`);
                        const data = await response.json();

                        if (data.ok && data.lotes && data.lotes.length > 0) {
                            // Mai/2026 — paginação dedup por LOTE (CODAGREGACAO),
                            // que é a chave funcional. Estrutura idêntica ao render
                            // principal (linha 67-79): 9 colunas na ordem
                            // Status · Pedido · Data · Parceiro · Produto · Qtde cx · Peso · Qtde Kg · Lote
                            const lotesNaTela = new Set(
                                Array.from(document.querySelectorAll('#notasTable tbody tr'))
                                    .map(tr => tr.querySelector('td:last-child')?.textContent?.trim())
                                    .filter(Boolean)
                            );
                            const novosLotes = data.lotes.filter(item => !lotesNaTela.has(item.lote));

                            if (novosLotes.length > 0) {
                                const html = novosLotes.map(item => {
                                    const totalKg = item.qtd_cx * item.peso_unit;
                                    return `
                                    <tr class="row--click" data-nunota="${item.nunota_origem}">
                                        <td style="width: 40px; text-align:center;"><span class="status-dot status-${item.status.toLowerCase()}"></span></td>
                                        <td style="width: 80px;">${item.nunota_origem}</td>
                                        <td style="width: 100px;">${item.data}</td>
                                        <td style="width: 150px;">${item.parceiro}</td>
                                        <td style="white-space: nowrap;">${item.produto}</td>
                                        <td style="width: 110px; text-align:right;">${item.qtd_cx.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</td>
                                        <td style="width: 110px; text-align:right;">${item.peso_unit.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</td>
                                        <td style="width: 120px; text-align:right; font-weight: bold;">${totalKg.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} kg</td>
                                        <td style="width: 160px; text-align:right; white-space: nowrap;">${item.lote}</td>
                                    </tr>
                                `;
                                }).join('');

                                notasTable.querySelector('tbody').insertAdjacentHTML('beforeend', html);
                            } else {
                                hasMoreRows = false;
                            }
                        } else {
                            hasMoreRows = false;
                        }
                    } catch (e) {
                        console.error("Erro no fetch:", e);
                        hasMoreRows = false;
                    } finally {
                        isLoadingMore = false;
                    }
                }
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
            if (document.activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
            e.preventDefault();
            const rows = Array.from(notasTable.querySelectorAll('tbody tr.row--click'));
            if (!rows.length) return;
            const curIdx = rows.findIndex(r => r.classList.contains('row--active'));
            const nextIdx = e.key === 'ArrowDown' ? (curIdx + 1) % rows.length : (curIdx - 1 + rows.length) % rows.length;
            if (rows[nextIdx]) {
                rows.forEach(r => r.classList.remove('row--active', 'selected'));
                rows[nextIdx].classList.add('row--active');
                rows[nextIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
        });

        // --- Modais de Cabeçalho e Itens ---
        const cabModal = document.getElementById('cabModal');
        const cabCard = document.getElementById('cabCard');
        const itemsModal = document.getElementById('cabItemsModal');
        const itemsCard = document.getElementById('cabItemsCard');

        window.showCabModal = () => { if (cabModal && cabCard) { cabModal.style.display = 'flex'; setTimeout(() => cabCard.style.left = '12px', 10); } };
        window.hideCabModal = () => { if (cabModal && cabCard) { cabCard.style.left = '-1200px'; setTimeout(() => cabModal.style.display = 'none', 300); } };
        window.showItemsModal = () => {
            if (itemsModal && itemsCard) {
                const camposParaLimpar = ['item_prod_vis', 'item_prod_hidden', 'item_total', 'item_peso', 'item_obs', 'item_seq_edit'];
                camposParaLimpar.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
                const volEl = document.getElementById('item_vol');
                if (volEl) volEl.value = 'KG';
                itemsModal.style.display = 'flex';
                setTimeout(() => itemsCard.style.left = '294px', 10);
            }
        };

        window.hideItemsModal = () => { if (itemsModal && itemsCard) { itemsCard.style.left = '100%'; setTimeout(() => itemsModal.style.display = 'none', 300); } };

        const hideAllModals = () => {
            window.hideItemsModal();
            window.hideCabModal();

            // 👇 NOVO: Atualiza a lista principal do fundo assim que o modal fechar
            if (typeof window.carregarTabelaLotes === 'function') {
                window.carregarTabelaLotes();
            }
        };

        ['cabClose', 'itemsClose', 'itemsCancel'].forEach(id => {
            const btn = document.getElementById(id);
            if (btn) btn.addEventListener('click', hideAllModals);
        }
        );

        // --- Modal de Edição ---
        const itemEditModal = document.getElementById('modalItemEdit');
        const itemModalTitle = document.getElementById('itemModalTitle');
        window.openItemModal = async function (data = {}) {
            if (!itemEditModal) return;
            const { lote, nunota, sequencia } = data;

            if (itemModalTitle) itemModalTitle.textContent = sequencia ? 'Editar Item' : 'Novo Item';
            ['itemProdHidden', 'itemProdCod', 'itemVolHidden', 'itemVol', 'itemQtd', 'itemPeso', 'itemTotalKg', 'itemVlr', 'itemObs'].forEach(id => {
                const el = document.getElementById(id); if (el) el.value = '';
            });
            const vlrEl = document.getElementById('itemVlr'); if (vlrEl) vlrEl.value = '0';
            if (itemEditModal) itemEditModal.removeAttribute('data-sequencia');

            if (sequencia) {
                itemEditModal.dataset.sequencia = sequencia;
                try {
                    let loteData = window.__LOTES_CACHE ? window.__LOTES_CACHE[lote] : null;
                    if (!loteData) {
                        const response = await fetch(`/sankhya/lote/consultar/?lote=${encodeURIComponent(lote)}&full=1`);
                        loteData = await response.json();
                        if (!loteData.ok) throw new Error('Falha ao carregar dados.');
                    }
                    const item = loteData.classificacoes.find(it => it.sequencia === sequencia && it.nunota === nunota);
                    if (item) {
                        const s = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
                        s('itemProdHidden', item.cod); s('itemProdCod', `${item.cod || ''} — ${item.descr || ''}`);
                        s('itemVol', item.codvol); s('itemQtd', item.qtd); s('itemPeso', item.peso);
                        s('itemTotalKg', item.total); s('itemVlr', item.vlu || '0'); s('itemObs', item.obs);
                    }
                } catch (e) { console.error(e); alert('Erro ao carregar item.'); return; }
            }
            itemEditModal.style.display = 'flex';
        };

        const closeItemModalBtn = document.getElementById('itemModalCancel');
        if (closeItemModalBtn) closeItemModalBtn.addEventListener('click', () => itemEditModal.style.display = 'none');

        window.populateCabecalho = function (loteData) {
            const { agregados, entradas, classificacoes } = loteData;
            let codOrigem = '';

            if (entradas && entradas.length > 0) {
                const primeiraEntrada = entradas[0];
                codOrigem = primeiraEntrada.codprod || primeiraEntrada.cod || primeiraEntrada.cod_prod || '';

                // 👇 NOVO: SALVA O CODPARC NA MEMÓRIA PARA PODER CRIAR A NOTA 👇
                window.CODPARC_ATUAL = primeiraEntrada.codparc || primeiraEntrada.CODPARC || '';
            }

            window.PH_INNATURA_CODPROD = codOrigem || loteData.prod_in_natura || '';
            window.PH_FABRICANTE = loteData.resumo?.fabricante || '';

            const setText = (selector, value, formatter) => { const el = document.querySelector(selector); if (el) el.textContent = formatter ? formatter(value) : (value || '—'); };
            const formatNumber = (val, dec = 1) => { const n = Number(val); return !isNaN(n) ? n.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec }) : '0'; };
            const formatDate = (dStr) => {
                if (!dStr) return '—';
                try { const d = new Date(dStr); d.setUTCDate(d.getUTCDate() + 1); return d.toLocaleDateString('pt-BR'); } catch (e) { return dStr; }
            };

            if (agregados) setText('#cab_lote_text', agregados.lote);

            if (entradas && entradas.length > 0) {
                const primeiraEntrada = entradas[0];
                setText('#cab_parc_text', primeiraEntrada.parceiro);
                setText('#cab_nunota_top11_text', primeiraEntrada.nunota);
                setText('#cab_dtneg_text', formatDate(primeiraEntrada.dtneg));
                const fabricantes = [...new Set(entradas.map(e => e.fabricante).filter(Boolean))];
                let produtoDescr = fabricantes.join(', ');
                if (fabricantes.length > 2) produtoDescr = `${fabricantes.slice(0, 2).join(', ')}...`;
                else if (fabricantes.length === 0) produtoDescr = primeiraEntrada.descr || '—';
                setText('#cab_prod_text', produtoDescr);
            }

            const totalInNaturaKg = (entradas || []).reduce((sum, item) => sum + (Number(item.qtd) || 0), 0);
            let possuiCaixas = false;
            let totalInNaturaCx = (entradas || []).reduce((sum, item) => {
                let cx = Number(item.qtdconferida || item.QTDCONFERIDA || 0);
                if (cx === 0 && Number(item.peso) > 0) cx = Number(item.qtd || 0) / Number(item.peso);
                if (cx > 0) possuiCaixas = true;
                return sum + cx;
            }, 0);

            if (totalInNaturaCx === 0) {
                totalInNaturaCx = (entradas || []).reduce((sum, item) => {
                    let cx = item.qtdconferida || item.QTDCONFERIDA || item.qtd_cx || 0;
                    if (typeof cx === 'string') cx = parseFloat(cx.replace(/\./g, '').replace(',', '.'));
                    return sum + (Number(cx) || 0);
                }, 0);
            }

            const totalClassificadoKg = (classificacoes || []).reduce((sum, item) => sum + (Number(item.qtd) || 0), 0);
            const totalDescarteKg = Number(loteData.qtdbatidas || loteData.descarte || (agregados && agregados.descarte) || (agregados && agregados.qtdbatidas) || 0);
            const estoqueKg = totalInNaturaKg - (totalClassificadoKg + totalDescarteKg);

            if (totalInNaturaCx > 0) setText('#cab_qtd_cx_text', totalInNaturaCx, (v) => formatNumber(v, 1) + ' cx');
            else { const elCx = document.querySelector('#cab_qtd_cx_text'); if (elCx) elCx.textContent = '-'; }

            setText('#cab_qtd_pedido_text', totalInNaturaKg, (v) => formatNumber(v) + ' kg');
            setText('#cab_class_count_text', totalClassificadoKg, (v) => formatNumber(v) + ' kg');
            setText('#cab_estoque_text', estoqueKg, (v) => formatNumber(v) + ' kg');
        };

        window.populateItemsModal = function (loteData) {
            const { classificacoes, nunota_class, agregados } = loteData;
            const itemsBody = document.getElementById('itemsListBody');
            const nunotaInput = document.getElementById('items_nunota');

            if (nunotaInput) nunotaInput.value = nunota_class || '';
            // 🔧 Sincroniza a global ao trocar de lote — evita vazamento da NUNOTA da TOP 26
            // entre lotes diferentes (causava itens de lotes distintos caírem no mesmo cabeçalho).
            window.NUNOTA_CLASS_ATUAL = nunota_class || '';
            if (!itemsBody) return;

            if (!classificacoes || classificacoes.length === 0) {
                itemsBody.innerHTML = '<tr><td colspan="5" style="padding:8px; color:var(--muted)">Nenhum item classificado para este lote.</td></tr>';
                return;
            }

            const formatQty = (val) => Number(val || 0).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
            const editSvg = `<i class="ph ph-pencil-simple icon" aria-hidden="true"></i>`;
            const trashSvg = `<i class="ph ph-trash icon" aria-hidden="true"></i>`;

            itemsBody.innerHTML = classificacoes.map(item => `
                <tr class="item-row" data-seq="${item.sequencia}" data-nunota="${item.nunota}" data-lote="${agregados ? agregados.lote : ''}" style="cursor: pointer; transition: background-color 0.2s;" title="Clique para selecionar, Duplo clique para editar">
                    <td style="padding:8px">${agregados ? agregados.lote : ''}</td>
                    <td>${item.cod} — ${item.descr}</td>
                    <td style="text-align:right">${formatQty(item.qtd)}</td>
                    <td style="text-align:right">${formatQty(item.peso)}</td>
                    
                    <td style="width: 90px; min-width: 90px; overflow: visible;">
                        <div style="display: flex; justify-content: flex-end; gap: 6px;">
                            <button class="icon-btn icon-btn--plain item-edit-btn" title="Editar item" style="display: none;">${editSvg}</button>
                            <button class="icon-btn icon-btn--plain item-delete-btn" title="Excluir item" style="display: none; color: #dc3545;">${trashSvg}</button>
                        </div>
                    </td>
                    
                </tr>
            `).join('');

            itemsBody.querySelectorAll('.item-row').forEach(row => {
                row.addEventListener('click', (ev) => {
                    itemsBody.querySelectorAll('.item-row').forEach(r => {
                        r.classList.remove('selected');
                        const bEdit = r.querySelector('.item-edit-btn');
                        const bDel = r.querySelector('.item-delete-btn');
                        if (bEdit) bEdit.style.display = 'none';
                        if (bDel) bDel.style.display = 'none';
                    });
                    row.classList.add('selected');
                    const currentEdit = row.querySelector('.item-edit-btn');
                    const currentDel = row.querySelector('.item-delete-btn');
                    // 👇 NOVO: Usando inline-flex para o SVG ficar centralizado no botão
                    if (currentEdit) currentEdit.style.display = 'inline-flex';
                    if (currentDel) currentDel.style.display = 'inline-flex';
                });
            });

            const puxarParaEdicao = (ev) => {
                if (window.PH_BLOQUEADO_COMERCIAL) {
                    ev.preventDefault(); ev.stopPropagation();
                    return;
                }
                if (window.PH_LOTE_FINALIZADO) {
                    ev.preventDefault(); ev.stopPropagation();
                    if (window.mostrarToast) window.mostrarToast("🔒 Lote finalizado! Edição bloqueada.", "error");
                    return;
                }
                ev.stopPropagation();
                const row = ev.currentTarget.closest('tr');
                const sequencia = Number(row.dataset.seq);
                const nunota = Number(row.dataset.nunota);

                const item = classificacoes.find(it => it.sequencia === sequencia && it.nunota === nunota);
                if (item) {
                    const s = (id, val) => { const el = document.getElementById(id); if (el) { el.value = val || ''; return true; } return false; };
                    s('item_prod_hidden', item.cod);
                    s('item_prod_vis', `${item.cod || ''} — ${item.descr || ''}`);
                    s('item_vol', item.codvol || 'KG');
                    s('item_total', item.qtd);
                    s('item_peso', item.peso);
                    s('item_obs', item.obs);

                    if (!s('item_qtd', item.qtd)) {
                        const modalInputs = document.querySelectorAll('#itemsModal input, .modal-content input');
                        if (modalInputs[3]) modalInputs[3].value = item.qtd;
                    }

                    let seqInput = document.getElementById('item_seq_edit');
                    if (!seqInput) {
                        seqInput = document.createElement('input');
                        seqInput.type = 'hidden'; seqInput.id = 'item_seq_edit';
                        document.body.appendChild(seqInput);
                    }
                    seqInput.value = item.sequencia;
                    if (window.mostrarToast) window.mostrarToast("Modo Edição Ativado", "success");
                }
            };

            itemsBody.querySelectorAll('.item-edit-btn').forEach(btn => btn.addEventListener('click', puxarParaEdicao));
            itemsBody.querySelectorAll('.item-row').forEach(row => row.addEventListener('dblclick', puxarParaEdicao));

            itemsBody.querySelectorAll('.item-delete-btn').forEach(btn => {
                btn.addEventListener('click', async (ev) => {
                    if (window.PH_BLOQUEADO_COMERCIAL) {
                        ev.preventDefault(); ev.stopPropagation();
                        return;
                    }
                    if (window.PH_LOTE_FINALIZADO) {
                        ev.preventDefault(); ev.stopPropagation();
                        if (window.mostrarToast) window.mostrarToast("🔒 Lote finalizado! Exclusão bloqueada.", "error");
                        return;
                    }
                    ev.stopPropagation();
                    const row = ev.currentTarget.closest('tr');
                    const sequencia = Number(row.dataset.seq);
                    const nunota = Number(row.dataset.nunota);
                    const loteAtual = row.dataset.lote;

                    if (confirm('Atenção: Tem certeza que deseja excluir este item?')) {
                        if (window.IAOverlay) window.IAOverlay.show();
                        try {
                            const deleteResponse = await (window.postJSON || postJSON)('/sankhya/item/delete/', {
                                nunota: nunota, sequencias: [sequencia], sequencia: sequencia,
                                NUNOTA: nunota, SEQUENCIAS: [sequencia], SEQUENCIA: sequencia
                            });

                            if (deleteResponse && deleteResponse.ok) {
                                if (window.mostrarToast) window.mostrarToast("Item excluído com sucesso!", "success");

                                if (deleteResponse.body && deleteResponse.body.cabecalho_excluido) {
                                    const nunotaInput = document.getElementById('items_nunota');
                                    if (nunotaInput) nunotaInput.value = '';
                                    const activeRow = document.querySelector(`tr[data-nunota="${loteAtual}"]`);
                                    if (activeRow) activeRow.dataset.nunotaTop26 = '';
                                    window.NUNOTA_CLASS_ATUAL = '';
                                }

                                // Atualiza a tabela do fundo
                                if (typeof lotesCache !== 'undefined') delete lotesCache[loteAtual];
                                await window.loadClassifiedFor(loteAtual, true);

                                // Atualiza a lista DENTRO DO MODAL
                                try {
                                    const modalRes = await fetch(`/sankhya/lote/consultar/?lote=${encodeURIComponent(loteAtual)}&full=1`);
                                    const modalData = await modalRes.json();
                                    if (modalData.ok && typeof window.populateItemsModal === 'function') {
                                        window.populateItemsModal(modalData);
                                    }
                                } catch (e) { }

                            } else { throw new Error(deleteResponse.body.error || 'Falha ao excluir o item no servidor.'); }
                        } catch (error) {
                            console.error("🚨 ERRO AO EXCLUIR:", error); alert("ERRO: " + error.message);
                        } finally {
                            if (window.IAOverlay) window.IAOverlay.hide();
                        }
                    }
                });
            });
        };

        // ==============================================================================
        // 🖱️ GERENCIAMENTO UNIFICADO DE CLIQUES (SIMPLES E DUPLO)
        // ==============================================================================
        let timerClique = null;
        const tabelaDinamica = document.getElementById('notasTable');

        if (tabelaDinamica) {
            tabelaDinamica.addEventListener('click', (e) => {
                const row = e.target.closest('tr.row--click');
                if (!row) return;

                clearTimeout(timerClique);

                timerClique = setTimeout(() => {
                    tabelaDinamica.querySelectorAll('tr.row--active').forEach(r => {
                        r.classList.remove('row--active');
                        r.style.backgroundColor = '';
                    });
                    row.classList.add('row--active');
                    row.style.backgroundColor = '#e8f5e9';

                    const nunotaOrigem = row.getAttribute('data-nunota');
                    // Mai/2026 — coluna Lote agora é a última (era cells[1])
                    const lote = row.cells[row.cells.length - 1].innerText.trim();

                    if (lote && nunotaOrigem && nunotaOrigem !== "undefined") {
                        if (typeof state !== 'undefined') state.selectedLote = lote;
                        window.LOTE_ATUAL_ABERTO = lote;
                        window.NUNOTA_ORIGEM_ATUAL = nunotaOrigem;
                        window.loadClassifiedFor(lote, nunotaOrigem);
                    }
                }, 250);
            });

            tabelaDinamica.addEventListener('dblclick', async (e) => {
                const row = e.target.closest('tr.row--click');
                if (!row) return;

                clearTimeout(timerClique);

                tabelaDinamica.querySelectorAll('tr.row--active').forEach(r => {
                    r.classList.remove('row--active');
                    r.style.backgroundColor = '';
                });
                row.classList.add('row--active');
                row.style.backgroundColor = '#e8f5e9';

                // Mai/2026 — coluna Lote agora é a última (era cells[1])
                const loteTexto = row.cells[row.cells.length - 1].innerText.trim();
                if (typeof state !== 'undefined') state.selectedLote = loteTexto;

                window.LOTE_ATUAL_ABERTO = loteTexto;
                window.NUNOTA_ORIGEM_ATUAL = row.getAttribute('data-nunota');

                // Manda carregar os cards do fundo em paralelo!
                window.loadClassifiedFor(loteTexto, window.NUNOTA_ORIGEM_ATUAL);

                const elLote = document.getElementById('cab_lote_text');
                const elProd = document.getElementById('cab_prod_text');
                const elItems = document.getElementById('itemsListBody');

                if (elLote) elLote.textContent = loteTexto;
                if (elProd) elProd.textContent = "Buscando dados no Oracle...";
                if (elItems) elItems.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 60px 20px;"><div class="spinner-border text-success" role="status"></div><h5>Sincronizando itens...</h5></td></tr>`;

                if (typeof window.showCabModal === 'function') window.showCabModal();
                if (typeof window.showItemsModal === 'function') window.showItemsModal();

                try {
                    const response = await fetch(`/sankhya/lote/consultar/?lote=${encodeURIComponent(loteTexto)}&full=1`);
                    const loteData = await response.json();

                    const inputDescarte = document.getElementById('descarteTotal');
                    if (inputDescarte && loteData.agregados && loteData.agregados.descarte !== undefined) {
                        inputDescarte.value = loteData.agregados.descarte.toLocaleString('pt-BR', {
                            minimumFractionDigits: 1, maximumFractionDigits: 1
                        });
                    }
                    if (loteData.resumo && loteData.resumo.fabricante) {
                        window.PH_FABRICANTE = loteData.resumo.fabricante;
                    } else if (loteData.agregados && loteData.agregados.fabricante) {
                        window.PH_FABRICANTE = loteData.agregados.fabricante;
                    }

                    if (typeof window.populateCabecalho === 'function') window.populateCabecalho(loteData);
                    if (typeof window.populateItemsModal === 'function') window.populateItemsModal(loteData);

                    // 👇 NOVO: LIGA/DESLIGA O TOGGLE DO MODAL E APLICA TRAVA 👇
                    let isFinalizadoModal = (loteData.pendente_class === 'N');
                    if (loteData.resumo && loteData.resumo.pendente === 'N') isFinalizadoModal = true;

                    window.PH_LOTE_FINALIZADO = isFinalizadoModal;
                    window.PH_BLOQUEADO_COMERCIAL = loteData.bloqueado_comercial || false; // 👈 LENDO A FLAG

                    const toggleBtn = document.getElementById('toggleStatusNota');
                    if (toggleBtn) toggleBtn.checked = isFinalizadoModal;

                    if (typeof window.aplicarTravaDeSeguranca === 'function') {
                        window.aplicarTravaDeSeguranca(isFinalizadoModal);
                    }

                    // 👇 NOVO: TRAVA SUPERIOR DO COMERCIAL 👇
                    if (window.PH_BLOQUEADO_COMERCIAL) {
                        if (toggleBtn) {
                            toggleBtn.disabled = true;
                            const label = toggleBtn.closest('label');
                            if (label) {
                                label.style.opacity = '0.6';
                                label.style.cursor = 'not-allowed';
                            }
                        }

                        // Congela os botões e inputs ignorando a chave de finalização
                        const elementosBloquear = document.querySelectorAll(`
                            .btn-primary, .btn-danger, .btn-success, .item-edit-btn, .item-delete-btn,
                            #itemAddBtn, #btnDescarteAdd, #btnDescarteSub,
                            #cabItemsCard input, #cabItemsCard select
                        `);
                        elementosBloquear.forEach(el => {
                            if (el.id === 'toggleStatusNota') return;
                            el.disabled = true;
                            if (el.tagName === 'BUTTON') {
                                el.classList.add('disabled');
                                el.style.pointerEvents = 'none';
                                el.style.opacity = '0.5';
                            }
                        });

                        window.mostrarToast("🔒 Lote possui negociação Comercial. Edições bloqueadas.", "warning");

                    } else {
                        // 👇 A CORREÇÃO ESTÁ AQUI: Desfazer o "fantasma" do Comercial no Toggle 👇
                        if (toggleBtn) {
                            toggleBtn.disabled = false;
                            const label = toggleBtn.closest('label');
                            if (label) {
                                label.style.opacity = '1';
                                label.style.cursor = 'pointer';
                            }
                        }
                    }

                } catch (error) {
                    console.error('Erro ao abrir modais:', error);
                    if (window.mostrarToast) window.mostrarToast('Não foi possível carregar os dados completos.', 'error');
                }
            });
        }
        const itemProdVis = document.getElementById('item_prod_vis');
        const itemProdHidden = document.getElementById('item_prod_hidden');
        const itemProdSugg = document.getElementById('item_prod_sugg');

        if (itemProdVis && itemProdHidden && itemProdSugg) {
            // Mai/2026 — typeahead via helper central. PH_FABRICANTE entra como extraQuery.
            const fab = window.PH_FABRICANTE || '';
            IAgro.attachTypeahead({
                inputId: 'item_prod_vis',
                hiddenId: 'item_prod_hidden',
                dropdownId: 'item_prod_sugg',
                url: '/sankhya/produtos/search/modal/',
                limit: 10,
                debounceMs: 400,  // legado da classificação (search modal mais pesada)
                extraQuery: fab ? `fabricante=${encodeURIComponent(fab)}` : undefined,
                pickItems: (data) => data.results || [],
                pickCod: (it) => it.cod || '',
                pickDescr: (it) => it.descr || '',
            });
        }

        const inputTotal = document.getElementById('item_total');
        const inputQtd = document.getElementById('item_qtd');
        const inputPeso = document.getElementById('item_peso');

        if (inputTotal && inputQtd && inputPeso) {
            const getVal = (el) => parseInt(el.value.replace(/\D/g, ''), 10) || 0;
            const setVal = (el, num) => el.value = num > 0 ? Math.round(num).toLocaleString('pt-BR') : '';
            const formatSelf = (el) => { let val = getVal(el); el.value = val > 0 ? val.toLocaleString('pt-BR') : ''; };

            inputTotal.addEventListener('input', () => {
                formatSelf(inputTotal);
                const total = getVal(inputTotal); const qtd = getVal(inputQtd); const peso = getVal(inputPeso);
                if (total > 0 && qtd > 0) setVal(inputPeso, total / qtd);
                else if (total > 0 && peso > 0) setVal(inputQtd, total / peso);
            });

            inputQtd.addEventListener('input', () => {
                formatSelf(inputQtd);
                const total = getVal(inputTotal); const qtd = getVal(inputQtd);
                if (total > 0 && qtd > 0) setVal(inputPeso, total / qtd);
            });

            inputPeso.addEventListener('input', () => {
                formatSelf(inputPeso);
                const total = getVal(inputTotal); const peso = getVal(inputPeso);
                if (total > 0 && peso > 0) setVal(inputQtd, total / peso);
            });
        }

        const toggleStatus = document.getElementById('toggleStatusNota');
        if (toggleStatus) {
            toggleStatus.onchange = async (e) => {
                const isChecked = e.target.checked;
                if (window.PH_BLOQUEADO_COMERCIAL) {
                    window.mostrarToast("🔒 Ação bloqueada pelo Comercial.", "error");
                    e.target.checked = !isChecked;
                    return;
                }
                const nunotaTop11 = document.getElementById('cab_nunota_top11_text')?.textContent;
                const nunotaClass = document.getElementById('items_nunota')?.value;
                const loteAtual = document.getElementById('cab_lote_text')?.textContent;

                if (!nunotaTop11 || nunotaTop11 === '—' || !nunotaClass) {
                    window.mostrarToast("Erro: Faltam dados das notas de origem ou classificação.", "error");
                    e.target.checked = !isChecked;
                    return;
                }

                if (isChecked && !confirm("Deseja marcar a classificação como FINALIZADA? Isso bloqueará edições.")) {
                    e.target.checked = false; return;
                }

                if (window.IAOverlay) window.IAOverlay.show();

                try {
                    const response = await postJSON('/sankhya/item/toggle_status/', {
                        nunota_origem: parseInt(nunotaTop11, 10), nunota_class: parseInt(nunotaClass, 10),
                        pendente: isChecked ? 'N' : 'S'
                    });

                    const _dbg = (response && (response.debug || (response.body && response.body.debug))) || null;
                    if (_dbg) {
                        console.warn('[FINALIZA_CLASS]', {
                            loteAlvoNoFront: loteAtual,
                            nunotaClass: _dbg.nunota_class,
                            pendente: _dbg.pendente,
                            qtdLotesNoCabecalho: _dbg.qtd_lotes_no_cab,
                            lotesAfetadosNoBanco: _dbg.lotes_afetados,
                            BUG_DETECTADO: _dbg.qtd_lotes_no_cab > 1,
                        });
                    } else {
                        console.warn('[FINALIZA_CLASS] response sem debug:', response);
                    }

                    if (response && response.ok) {
                        window.mostrarToast("Classificação finalizada com sucesso!", "success");
                        if (typeof window.aplicarTravaDeSeguranca === 'function') window.aplicarTravaDeSeguranca(isChecked);
                        if (typeof setClassificacaoFinalizada === 'function') setClassificacaoFinalizada(isChecked);
                        if (typeof window.atualizarStatusNaListaLateral === 'function') window.atualizarStatusNaListaLateral(loteAtual, isChecked);
                    } else { throw new Error(response.error || "Erro ao salvar no Sankhya."); }
                } catch (err) {
                    window.mostrarToast(err.message, "error");
                    e.target.checked = !isChecked;
                } finally {
                    if (window.IAOverlay) window.IAOverlay.hide();
                }
            };
        }

        // =================================================================
        // 🔥 LÓGICA DE FILTROS 
        // =================================================================
        const btnGreen = document.getElementById('filterGreen');
        const btnYellow = document.getElementById('filterYellow');
        const btnRed = document.getElementById('filterRed');

        if (btnGreen && btnYellow && btnRed) {
            btnGreen.checked = false; btnYellow.checked = true; btnRed.checked = true;

            [btnGreen, btnYellow, btnRed].forEach(item => {
                item.onchange = () => { window.carregarTabelaLotes(); };
            });
        }

        if (typeof configurarFiltroDireto === 'function') {
            configurarFiltroDireto('parcSearch', 'codparc');
            configurarFiltroDireto('fabricanteSearch', 'fabricanteHidden');
            configurarFiltroDireto('pedidoSearch', 'pedidoHidden');
            configurarFiltroDireto('loteSearch', 'loteHidden');
        }

        const btnPrev = document.getElementById('btnPrevDay');
        const btnNext = document.getElementById('btnNextDay');
        const inputStart = document.querySelector('input[name="start"]');
        const inputEnd = document.querySelector('input[name="end"]');

        if (btnPrev && btnNext && inputStart) {
            const navegar = (sentido) => {
                let dataRef = inputStart.value || new Date().toISOString().split('T')[0];
                let dataObj = new Date(dataRef + 'T00:00:00');
                dataObj.setDate(dataObj.getDate() + sentido);
                const novaDataStr = dataObj.toISOString().split('T')[0];
                inputStart.value = novaDataStr;
                if (inputEnd) inputEnd.value = novaDataStr;
                window.carregarTabelaLotes();
            };
            btnPrev.onclick = (e) => { e.preventDefault(); navegar(-1); };
            btnNext.onclick = (e) => { e.preventDefault(); navegar(1); };
        }

        document.getElementById('btnClear')?.addEventListener('click', (e) => {
            e.preventDefault(); location.reload();
        });

        /**
         * Mai/2026 — Renderiza chips de filtros ativos no #filtrosAtivosChips.
         * Click no × zera o(s) campo(s) correspondente(s) e chama
         * carregarTabelaLotes() — fluxo AJAX (sem reload).
         */
        function renderChipsFiltrosClassificacao() {
            const cont = document.getElementById('filtrosAtivosChips');
            if (!cont) return;
            cont.innerHTML = '';
            const chips = [];

            // Período (só se != hoje)
            const hoje = new Date().toISOString().split('T')[0];
            const startEl = document.querySelector('input[name="start"]');
            const endEl = document.querySelector('input[name="end"]');
            const ini = startEl?.value;
            const fim = endEl?.value;
            if (ini && fim && (ini !== hoje || fim !== hoje)) {
                const txt = ini === fim
                    ? new Date(ini + 'T12:00:00').toLocaleDateString('pt-BR')
                    : `${new Date(ini + 'T12:00:00').toLocaleDateString('pt-BR')} → ${new Date(fim + 'T12:00:00').toLocaleDateString('pt-BR')}`;
                chips.push({
                    rotulo: 'Período', valor: txt,
                    remover: () => {
                        if (startEl) startEl.value = hoje;
                        if (endEl) endEl.value = hoje;
                        window.carregarTabelaLotes();
                    },
                });
            }

            // Pedido
            const pedido = document.getElementById('pedidoHidden')?.value
                || document.getElementById('pedidoSearch')?.value || '';
            if (pedido) chips.push({
                rotulo: 'Pedido', valor: pedido,
                remover: () => {
                    const ph = document.getElementById('pedidoHidden');
                    const ps = document.getElementById('pedidoSearch');
                    if (ph) ph.value = '';
                    if (ps) ps.value = '';
                    window.carregarTabelaLotes();
                },
            });

            // Produto (Fabricante)
            const fab = document.getElementById('fabricanteHidden')?.value;
            if (fab) {
                const visivel = document.getElementById('fabricanteSearch')?.value || fab;
                chips.push({
                    rotulo: 'Produto', valor: visivel,
                    remover: () => {
                        document.getElementById('fabricanteHidden').value = '';
                        const vis = document.getElementById('fabricanteSearch');
                        if (vis) vis.value = '';
                        window.carregarTabelaLotes();
                    },
                });
            }

            // Parceiro
            const codparc = document.getElementById('codparc')?.value;
            if (codparc) {
                const visivel = document.getElementById('parcSearch')?.value || codparc;
                chips.push({
                    rotulo: 'Parceiro', valor: visivel,
                    remover: () => {
                        document.getElementById('codparc').value = '';
                        const vis = document.getElementById('parcSearch');
                        if (vis) vis.value = '';
                        window.carregarTabelaLotes();
                    },
                });
            }

            // Lote
            const lote = document.getElementById('loteHidden')?.value
                || document.getElementById('loteSearch')?.value || '';
            if (lote) chips.push({
                rotulo: 'Lote', valor: lote,
                remover: () => {
                    const lh = document.getElementById('loteHidden');
                    const ls = document.getElementById('loteSearch');
                    if (lh) lh.value = '';
                    if (ls) ls.value = '';
                    window.carregarTabelaLotes();
                },
            });

            chips.forEach(chip => {
                const el = document.createElement('span');
                el.className = 'iagro-filtro-chip';
                el.innerHTML = `
                    <span class="chip-rotulo">${chip.rotulo}:</span>
                    <span class="chip-valor" title="${chip.valor}">${chip.valor}</span>
                    <button type="button" class="chip-remover" title="Remover" aria-label="Remover">×</button>
                `;
                el.querySelector('.chip-remover').addEventListener('click', chip.remover);
                cont.appendChild(el);
            });
        }

        // Wrappa carregarTabelaLotes pra atualizar os chips no final de cada
        // chamada AJAX (typeahead onSelect, navegação de datas, etc).
        const _carregarOrig = window.carregarTabelaLotes;
        window.carregarTabelaLotes = async function (...args) {
            const res = await _carregarOrig.apply(this, args);
            try { renderChipsFiltrosClassificacao(); } catch (e) { console.warn('renderChipsFiltros falhou', e); }
            return res;
        };
        // Render inicial — antes mesmo da primeira carga AJAX
        try { renderChipsFiltrosClassificacao(); } catch (e) { }

        window.carregarTabelaLotes();
    }); // FIM DO DOMCONTENTLOADED

    // =================================================================
    // MÉTODOS DE TRAVA DE SEGURANÇA E STATUS
    // =================================================================
    window.atualizarStatusNaListaLateral = function (lote, isFinalizado) {
        if (!lote) return;

        // 1. Pega todas as linhas da tabela
        const linhas = document.querySelectorAll('#notasTable tbody tr.row--click');
        let linhaEncontrada = null;

        // 2. Procura exatamente a linha que tem o nome do lote na última coluna
        // (Mai/2026 — antes era cells[1] quando Lote era a 2ª coluna)
        for (let linha of linhas) {
            if (linha.cells.length > 0 && linha.cells[linha.cells.length - 1].innerText.trim() === lote) {
                linhaEncontrada = linha;
                break;
            }
        }

        if (linhaEncontrada) {
            // 3. Acha a bolinha dentro da linha
            const primeiraColuna = linhaEncontrada.querySelector('td:first-child');
            if (primeiraColuna) {
                const bolinha = primeiraColuna.querySelector('.status-dot') || primeiraColuna.querySelector('span, div, i');

                if (bolinha) {
                    // Limpa todas as possíveis classes antigas
                    bolinha.classList.remove('status-verde', 'status-amarelo', 'status-vermelho', 'bg-success', 'bg-warning');

                    // Adiciona a classe correta
                    bolinha.classList.add(isFinalizado ? 'status-verde' : 'status-amarelo');

                    // Força a cor no estilo (garantia dupla caso o CSS falhe)
                    bolinha.style.backgroundColor = isFinalizado ? '#28a745' : '#ffc107';
                    bolinha.style.borderColor = isFinalizado ? '#28a745' : '#ffc107';
                }
            }
        }
    };

    window.aplicarTravaDeSeguranca = function (isFinalizado) {
        window.PH_LOTE_FINALIZADO = isFinalizado;
        const toggle = document.getElementById('toggleStatusNota');
        if (toggle) toggle.checked = isFinalizado;

        const inputDescarte = document.getElementById('descarteTotal');
        if (inputDescarte) {
            inputDescarte.disabled = isFinalizado;
            inputDescarte.style.backgroundColor = isFinalizado ? '#e9ecef' : '';
        }

        const botoesAcao = document.querySelectorAll(`
            [data-bs-toggle="modal"], [data-target], [onclick*="editar"], [onclick*="excluir"],
            .btn-primary, .btn-danger, .btn-success, .item-edit-btn, .item-delete-btn,
            #itemAddBtn, #itemModalSave, #itemDeleteBtn, #btnDescarteAdd, #btnDescarteSub
        `);

        botoesAcao.forEach(btn => {
            if (btn.id === 'toggleStatusNota' || btn.closest('.form-switch')) return;
            btn.disabled = isFinalizado;
            if (isFinalizado) {
                btn.classList.add('disabled');
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.5';
            } else {
                btn.classList.remove('disabled');
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            }
        });

        const camposModal = document.querySelectorAll('.modal-content input, .modal-content select, .modal-content textarea, #cabItemsCard input');
        camposModal.forEach(campo => {
            if (campo.id === 'toggleStatusNota') return;
            campo.disabled = isFinalizado;
        });
    };

    // =================================================================
    // A FÁBRICA DE AUTOCOMPLETES (Mai/2026: helper central IAgro.attachTypeahead)
    // Mantém assinatura (inputId, hiddenId, dropdownId, urlBusca, mapearResultados).
    // Adiciona Esc handler + blur tolerante + select-on-focus globais. Debounce 300ms.
    // min 2 chars (mantido do legado — endpoints da classificação são pesados).
    // =================================================================
    function criarAutocomplete(inputId, hiddenId, dropdownId, urlBusca, mapearResultados) {
        // urlBusca legado vinha com "?limit=10&q=" no fim. Removemos pra deixar
        // o helper montar a query consistentemente.
        const baseUrl = urlBusca.replace(/[?&]q=$/, '').replace(/[?&]q$/, '');
        return IAgro.attachTypeahead({
            inputId, hiddenId, dropdownId,
            url: baseUrl,
            limit: 10,
            minChars: 2,
            debounceMs: 300,
            pickItems: (data) => data.results || [],
            pickCod: (it) => mapearResultados(it).busca,
            // Mai/2026 — o mapearResultados legado retorna `exibicao` no formato
            // completo "${busca} — ${nome}" (caso parceiro). Se removermos o
            // prefixo aqui, o helper central monta "cod — descr" sem duplicar.
            // Pra fabricante/pedido (exibicao === busca), retornamos exibicao
            // direto — o helper detecta cod===descr e mostra só uma vez.
            pickDescr: (it) => {
                const m = mapearResultados(it);
                const exib = String(m.exibicao || '');
                const busca = String(m.busca || '');
                const prefix = busca + ' — ';
                return exib.startsWith(prefix) ? exib.substring(prefix.length) : exib;
            },
            renderItem: (it) => mapearResultados(it).exibicao,
            onSelect: () => {
                window.carregarTabelaLotes();
                // Re-dispara após 50ms — preserva quirk legado da classificação
                // (alguns lotes só aparecem depois do segundo render).
                setTimeout(() => { window.carregarTabelaLotes(); }, 50);
            },
        });
    }

    criarAutocomplete('parcSearch', 'codparc', 'parcDropdown', '/sankhya/parceiros/search/', (it) => {
        return { exibicao: `${it.codparc} — ${it.nomeparc}`, busca: it.codparc };
    });

    criarAutocomplete('fabricanteSearch', 'fabricanteHidden', 'fabricanteDropdown', '/sankhya/produtos/search/fabricante/', (it) => {
        return { exibicao: it.fabricante, busca: it.fabricante };
    });

    criarAutocomplete('pedidoSearch', 'pedidoHidden', 'pedidoDropdown', '/sankhya/pedidos/search/', (it) => {
        return { exibicao: it.nunota, busca: it.nunota };
    });

    function configurarFiltroDireto(inputId, hiddenId) {
        const input = document.getElementById(inputId);
        const hidden = document.getElementById(hiddenId);
        if (!input) return;

        const disparar = () => {
            if (inputId.includes('Search') && !/^\d+$/.test(input.value.trim())) {
            } else {
                if (hidden) hidden.value = input.value.trim();
            }
            window.carregarTabelaLotes();
        };

        input.addEventListener('blur', (e) => {
            const dropdown = document.getElementById(inputId.replace('Search', 'Dropdown'));
            if (dropdown && dropdown.style.display === 'block') return;
            disparar();
        });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault(); disparar(); input.blur();
            }
        });
    }

    configurarFiltroDireto('loteSearch', 'loteHidden');

    // 👇 Puxando os inputs de data para esse bloco final
    const startFinal = document.querySelector('input[name="start"]');
    const endFinal = document.querySelector('input[name="end"]');

    if (startFinal && endFinal) {
        startFinal.addEventListener('change', () => {
            endFinal.value = startFinal.value;
            window.carregarTabelaLotes();
        });
        endFinal.addEventListener('change', () => {
            window.carregarTabelaLotes();
        });
    }
})(); // FIM DO ARQUIVO