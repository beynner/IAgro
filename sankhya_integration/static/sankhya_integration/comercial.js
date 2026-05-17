/**
 * ============================================================================
 * 1. UTILS GLOBAIS
 * Funções de formatação e conversão usadas em todo o sistema.
 * ============================================================================
 */
window.ComercialUtils = {
    toNumber(v) {
        if (v === null || v === undefined) return NaN;
        if (typeof v === 'number') return isFinite(v) ? v : NaN;
        if (typeof v === 'string') {
            const cleaned = v.trim().replace(/\s+/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.');
            const n = Number(cleaned);
            return isFinite(n) ? n : NaN;
        }
        return NaN;
    },
    pickFirstPositive(...values) {
        for (const v of values) {
            const n = this.toNumber(v);
            if (!isNaN(n) && n > 0) return n;
        }
        return NaN;
    },
    formatQty(n, decimals = 3) {
        const num = this.toNumber(n);
        if (isNaN(num)) return '0';
        return num.toLocaleString('pt-BR', { maximumFractionDigits: decimals });
    },
    formatDate(s) {
        if (!s) return '';
        const str = String(s).trim();
        
        // 🚀 FIX: Captura direto do texto YYYY-MM-DD para driblar o fuso horário do Brasil
        let m = str.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (m) return `${m[3]}/${m[2]}`; // Retorna DD/MM
        
        m = str.match(/^(\d{2})\/(\d{2})$/);
        if (m) return `${m[1]}/${m[2]}`;
        m = str.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})$/);
        if (m) return `${String(m[1]).padStart(2, '0')}/${String(m[2]).padStart(2, '0')}`;
        
        // Fallback: Adiciona T12:00:00 para garantir que a data não recue 1 dia
        const d = new Date(str.includes('T') ? str : str + 'T12:00:00');
        if (!isNaN(d.getTime())) return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
        return str;
    },
    escapeHTML(str) {
        return String(str || '').replace(/[<>"'&]/g, c => ({ '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '&': '&amp;' }[c]));
    },

    // FUNÇÃO DO TOAST
    mostrarToast(mensagem, tipo = 'sucesso') {
        const toastAntigo = document.getElementById('agromilToast');
        if (toastAntigo) toastAntigo.remove();

        const toast = document.createElement('div');
        toast.id = 'agromilToast';
        
        const corFundo = tipo === 'sucesso' ? '#22c55e' : '#ef4444'; 
        const icone = tipo === 'sucesso' ? '<i class="ph ph-check"></i>' : '<i class="ph ph-warning"></i>';

        toast.style.cssText = `
            position: fixed; bottom: 24px; right: 24px;
            background: ${corFundo}; color: #ffffff;
            padding: 12px 20px; border-radius: 8px;
            font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 99999; display: flex; align-items: center; gap: 8px;
            opacity: 0; transform: translateY(20px); transition: all 0.3s ease;
        `;
        
        toast.innerHTML = `<span style="font-size:1.1rem">${icone}</span><span>${this.escapeHTML(mensagem)}</span>`;
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    isClassificavel(item) {
        if (!item) return false;
        try {
            const tipo = (item.tipo || '').toString().toLowerCase();
            if (tipo === 'classificavel') return true;
            if (tipo.includes('nao')) return false;
            const flag = item.classificavel;
            if (typeof flag === 'boolean') return flag;
            if (typeof flag === 'number') return flag === 1;
            if (typeof flag === 'string') {
                const base = typeof flag.normalize === 'function' ? flag.normalize('NFD') : flag;
                const normalized = base.replace(/[^\x00-\x7F]/g, '').trim().toUpperCase();
                if (['S', 'SIM', '1', 'TRUE', 'Y'].includes(normalized)) return true;
            }
        } catch (err) {}
        return false;
    }
};

window.__isClassificavelItem = window.ComercialUtils.isClassificavel;
window.__isNaoClassificavelItem = (item) => !window.ComercialUtils.isClassificavel(item);

/**
 * ============================================================================
 * 2. MÓDULO: LISTA PRINCIPAL (COM CONTADOR DE RESULTADOS)
 * ============================================================================
 */
window.ComercialLista = (function() {
    let DOM = {};
    const STATE = { limit: 150, offset: 0, loading: false, finished: false, rows: [], qsBase: '', viewMode: 'vale' };

    const resolveQuantidade = (row) => {
        if (!row) return { value: 0, unit: '', unitRaw: '' };
        
        const unitRaw = (row.__raw_codvol ?? row.codvol ?? '').toString().trim();
        const preferredUnit = (unitRaw || 'CX').toUpperCase();

        if (row.qtdconferida !== undefined && row.qtdconferida !== null) {
            return { value: window.ComercialUtils.toNumber(row.qtdconferida), unit: preferredUnit, unitRaw };
        }

        const qtdBase = window.ComercialUtils.pickFirstPositive(row.qtdneg_base, row.qtdneg);
        const pesoUnit = window.ComercialUtils.pickFirstPositive(row.peso, row.fator_conversao);
        
        if (qtdBase > 0 && pesoUnit > 0) return { value: qtdBase / pesoUnit, unit: preferredUnit, unitRaw };
        return { value: window.ComercialUtils.toNumber(row.qtdneg), unit: preferredUnit, unitRaw };
    };

    const renderTemplates = {
        loading: '<tr class="lista-status"><td colspan="5" style="padding:8px; color:#64748b; text-align:center;">Carregando…</td></tr>',
        empty: '<tr class="lista-status"><td colspan="5" style="padding:8px; color:#64748b; text-align:center;">Nenhum registro encontrado.</td></tr>',
        end: '<tr class="lista-status"><td colspan="5" style="padding:8px; color:#94a3b8; text-align:center;">Fim da lista.</td></tr>',
        error: (msg) => `<tr class="lista-status"><td colspan="5" style="padding:8px; color:#b91c1c; text-align:center;">${window.ComercialUtils.escapeHTML(msg)}</td></tr>`,
        itemRow: (r, isClassificavel) => {
            const prod = window.ComercialUtils.escapeHTML(r.produto || '');
            const qtyInfo = resolveQuantidade(r);
            const qtd = window.ComercialUtils.formatQty(qtyInfo.value);
            const unitHtml = qtyInfo.unit ? `<span class="list-unit"> ${qtyInfo.unit}</span>` : '';
            return `
                <tr data-classificavel="${isClassificavel ? '1' : '0'}" data-idx="${r._i}" class="lista-item-row" style="cursor:pointer; display:none; background:#fff;">
                    <td style="padding:6px 4px; color:#cbd5e1; text-align:center;">↳</td>
                    <td colspan="4" title="${prod}" style="padding:6px 8px; font-size:.78rem;">
                        <div class="list-prod-inner" style="display:flex; justify-content:space-between;">
                            <span class="list-name" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${prod}</span>
                            <span class="list-qty" style="font-weight:bold;">${qtd}${unitHtml}</span>
                        </div>
                    </td>
                </tr>`;
        },
        headerVale: (nun, arr) => {
            const rawParc = arr[0].parceiro || '';
            const parcEscaped = window.ComercialUtils.escapeHTML(rawParc);
            const dt = window.ComercialUtils.formatDate(arr[0].dtneg);
            const isFaturado = arr.some(x => x && x.nufin);
            const temPrecoZerado = arr.some(r => Number(r.precobase || r.preco_inicial || 0) <= 0);
            
            let bgStyle = ''; let cls = 'vale--aberto'; let fontWeight = 'normal'; let prefix = '';
            if (temPrecoZerado) { bgStyle = 'background-color:#fee2e2;'; fontWeight = 'bold'; }
            else if (isFaturado) { cls = 'vale--faturado'; prefix = '<span style="color:#16a34a; font-weight:bold; margin-right:4px;">$</span>'; }
            
            return `
            <tr class="vale-header ${cls}" data-expanded="false" style="cursor:pointer; ${bgStyle}">
                <td colspan="3" style="padding:6px 8px; font-size:.78rem; color:#334155; font-weight:${fontWeight};">
                    <span class="vale-head-inner"><span>${prefix}${parcEscaped}</span></span>
                </td>
                <td style="padding:6px 8px; font-size:.78rem; text-align:right;">
                    <span style="display:inline-flex; align-items:center; gap:6px;">
                        <span class="vale-head-nun" style="background:#475569; color:#fff; padding:1px 4px; border-radius:3px;">${nun}</span>
                        <span style="color:#64748b;">${dt}</span>
                    </span>
                </td>
                <td style="padding:6px 4px; text-align:right;">
                    <span class="lista-vale-ico" data-nunota="${nun}" role="button" 
                        style="cursor:pointer; color:#0ea5e9; display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:rgba(14,165,233,0.1);">
                        <i class="ph ph-shopping-cart-simple" style="pointer-events: none; font-size: 16px;" aria-hidden="true"></i>
                    </span>
                </td>
            </tr>`;
        }
    };

    const render = () => {
        if (!DOM.body) return;

        const filteredRows = STATE.rows;

        const counterEl = document.getElementById('agromilListCounter');
        if (counterEl) {
            const uniqueVales = new Set(filteredRows.map(r => r.nunota)).size;
            counterEl.innerHTML = `<span><i class="ph ph-clipboard-text"></i> <b>${uniqueVales}</b> Vale(s) exibido(s)</span>`;
        }

        if (!filteredRows.length) {
            DOM.body.innerHTML = STATE.loading ? renderTemplates.loading : renderTemplates.empty;
            return;
        }

        const htmlParts = [];
        const byNun = new Map();
        filteredRows.forEach(r => { 
            const k = String(r.nunota || ''); 
            if(k) { if(!byNun.has(k)) byNun.set(k, []); byNun.get(k).push(r); }
        });
        
        byNun.forEach((arr, nun) => {
            // 🚀 MÁGICA VISUAL: Esconde na lista o que não atende ao filtro da tela, 
            // mas arr (a Nota Inteira) continua salva pra memória do faturamento!
            const itensVisiveis = arr.filter(r => r.atende_filtro === 1 || r.atende_filtro === undefined);
            
            if (itensVisiveis.length > 0) {
                htmlParts.push(renderTemplates.headerVale(window.ComercialUtils.escapeHTML(nun), arr));
                itensVisiveis.forEach(r => htmlParts.push(renderTemplates.itemRow(r, window.ComercialUtils.isClassificavel(r))));
            }
        });

        DOM.body.innerHTML = htmlParts.join('') + (STATE.loading ? renderTemplates.loading : '');
        
        // 🚀 MÁGICA DA MEMÓRIA: Passa TUDO que veio do banco, sem ocultar nada, 
        // para que o ComercialImpressao e ModalFaturamento tenham 100% dos dados.
        window.__COM_LIST_ROWS = STATE.rows;
    };

    const fetchPage = async () => {
        if (STATE.loading || STATE.finished) return;
        STATE.loading = true; render();
        const url = `/sankhya/comercial/lista/?${STATE.qsBase}&offset=${STATE.offset}&limit=${STATE.limit}&_t=${Date.now()}`;
        try {
            const resp = await fetch(url, { cache: 'no-cache' });
            const data = await resp.json();
            const fetched = Array.isArray(data.rows) ? data.rows : [];
            fetched.forEach((row, idx) => row._i = STATE.rows.length + idx);
            STATE.rows.push(...fetched);
            STATE.offset = STATE.rows.length;
            
            if (fetched.length < STATE.limit) {
                STATE.finished = true;
            }

            // 🚀 FIX: O loop de 'setTimeout' que forçava a requisição repetida foi removido.
            // Agora o sistema só busca novos dados se o usuário realmente rolar a tela, 
            // poupando o servidor de bombardeios de requisições.

        } catch (err) { console.error(err); } finally { STATE.loading = false; render(); }
    };

    return {
        init: () => {
            DOM.body = document.getElementById('listaBody');
            DOM.wrap = document.getElementById('listaWrap');

            if (DOM.wrap) {
                DOM.wrap.addEventListener('scroll', () => {
                    if (STATE.loading || STATE.finished) return;
                    if (DOM.wrap.scrollHeight - (DOM.wrap.scrollTop + DOM.wrap.clientHeight) <= 120) fetchPage();
                });
            }

            if (DOM.body) {
                DOM.body.onclick = (ev) => {
                    const btnCarrinho = ev.target.closest('.lista-vale-ico');
                    
                    if (btnCarrinho) {
                        ev.stopPropagation(); 
                        const nunota = btnCarrinho.getAttribute('data-nunota');
                        
                        if (window.ComercialFinanceiro) {
                            window.ComercialFinanceiro.abrir(nunota);
                        }
                        return;
                    }
                    const header = ev.target.closest('tr.vale-header');
                    if (header) {
                        const isExp = header.getAttribute('data-expanded') === 'true';
                        header.setAttribute('data-expanded', isExp ? 'false' : 'true');
                        let next = header.nextElementSibling;
                        while (next && next.classList.contains('lista-item-row')) {
                            next.style.setProperty('display', isExp ? 'none' : 'table-row', 'important');
                            next = next.nextElementSibling;
                        }
                        return; 
                    }

                    const tr = ev.target.closest('tr.lista-item-row');
                    if (tr) {
                        DOM.body.querySelectorAll('tr.row--sel').forEach(el => {
                            el.classList.remove('row--sel');
                            el.style.backgroundColor = ''; 
                        });
                        tr.classList.add('row--sel');
                        tr.style.backgroundColor = '#fef3c7';

                        const idx = tr.dataset.idx;
                        const dadosDaLinha = window.__COM_LIST_ROWS[idx];
                        if (dadosDaLinha) {
                            if (window.ComercialEntrada) window.ComercialEntrada.preencher(dadosDaLinha);
                            
                            if (window.ComercialClassificacao) {
                                window.ComercialClassificacao.preencher(dadosDaLinha).then(pesosCategorias => {
                                    if (window.ComercialDistribuicao) {
                                        window.ComercialDistribuicao.preencher(dadosDaLinha, pesosCategorias);
                                    }
                                });
                            }
                        }
                    }
                };
            }
        },
        load: (queryString = '') => { STATE.qsBase = queryString; STATE.offset = 0; STATE.rows = []; STATE.finished = false; fetchPage(); },
        render: render
    };
})();

/**
 * ============================================================================
 * 3. MÓDULO: FILTROS E AUTOCOMPLETE (VERSÃO FINAL)
 * ============================================================================
 */
window.ComercialFiltros = (function() {
    let DOM = {};
    const STORAGE_KEY = 'agromil_comercial_filtros_v3';
    const INTERNAL_STATE = { pendentes: false, faturados: false, classificacao: '' }; 

    const debounce = (fn, ms = 400) => { 
        let timer; 
        return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); }; 
    };

    const saveState = () => {
        if (!DOM.form) return;
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            parceiroNome: DOM.parceiroInput?.value || '',
            parceiroCode: DOM.parceiroCode?.value || '',
            produtoNome: DOM.produtoInput?.value || '',
            dataCompra: DOM.dataCompra?.value || '',
            dataCompraFim: document.getElementById('fltDataCompraFim')?.value || '',
            nunota: DOM.nunota?.value || '',
            qf: INTERNAL_STATE
        }));
    };

    const loadState = () => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const state = JSON.parse(saved);
                if (DOM.parceiroInput) DOM.parceiroInput.value = state.parceiroNome || '';
                if (DOM.parceiroCode) DOM.parceiroCode.value = state.parceiroCode || '';
                if (DOM.produtoInput) DOM.produtoInput.value = state.produtoNome || '';
                if (DOM.dataCompra) DOM.dataCompra.value = state.dataCompra || '';
                const dtFim = document.getElementById('fltDataCompraFim');
                if (dtFim) dtFim.value = state.dataCompraFim || '';
                if (DOM.nunota) DOM.nunota.value = state.nunota || '';
                if (state.qf) Object.assign(INTERNAL_STATE, state.qf);
            }
        } catch (e) {}
    };

    const renderVisuals = () => {
        let container = document.getElementById('agromilActiveChips');
        if (!container) {
            container = document.createElement('div');
            container.id = 'agromilActiveChips';
            container.style = "display:flex; gap:8px; margin-top:6px; padding-top:6px; border-top:1px dashed #cbd5e1; flex-wrap:wrap;";
            DOM.form.appendChild(container);
        }

        const brownColor = '#42281E'; 
        const greenColor = '#166534'; 
        const redColor = '#991b1b';   
        const greyColor = '#64748b';  

        const getIconHtml = (color, isEmpty = false) => `
            <div style="width:12px; height:12px; background-color:${isEmpty ? 'transparent' : color}; border:2px solid ${color}; border-radius:50%; display:inline-block; margin-right:6px; flex-shrink:0;"></div>`;

        const createChip = (label, id, type) => `
            <span class="agromil-chip" style="background:#f1f5f9; border:1px solid #cbd5e1; color:#334155; padding:4px 10px; border-radius:12px; font-size:0.75rem; display:inline-flex; align-items:center; gap:4px; line-height:1;">
                ${label} 
                <b class="chip-close" data-clear="${id}" data-type="${type}" style="cursor:pointer; color:#ef4444; font-size:1.2rem; margin-left:4px;">&times;</b>
            </span>`;

        let html = '';
        if (DOM.parceiroInput?.value) {
            const partes = DOM.parceiroInput.value.split(' — ');
            html += createChip(partes.length > 1 ? partes[1] : partes[0], 'parceiro', 'input');
        }
        if (DOM.produtoInput?.value) html += createChip(DOM.produtoInput.value, 'produto', 'input');
        if (DOM.nunota?.value) html += createChip(`Vale: ${DOM.nunota.value}`, 'nunota', 'input');
        if (INTERNAL_STATE.pendentes) html += createChip(`${getIconHtml(redColor)} Sem preço`, 'pendentes', 'qf');
        if (INTERNAL_STATE.faturados) html += createChip(`${getIconHtml(greenColor)} Faturado`, 'faturados', 'qf');
        if (INTERNAL_STATE.classificacao === 'S') html += createChip(`${getIconHtml(brownColor)} Com Classif.`, 'classificacao', 'toggle');
        if (INTERNAL_STATE.classificacao === 'N') html += createChip(`${getIconHtml(greyColor, true)} Sem Classif.`, 'classificacao', 'toggle');
        
        container.innerHTML = html;
        container.style.display = html.trim() === '' ? 'none' : 'flex';

        container.querySelectorAll('.chip-close').forEach(btn => {
            btn.onclick = (e) => {
                const id = e.currentTarget.dataset.clear;
                const type = e.currentTarget.dataset.type;
                if (type === 'qf') INTERNAL_STATE[id] = false;
                if (type === 'toggle') INTERNAL_STATE.classificacao = '';
                if (id === 'parceiro') { if (DOM.parceiroInput) DOM.parceiroInput.value = ''; if (DOM.parceiroCode) DOM.parceiroCode.value = ''; }
                if (id === 'produto') { if (DOM.produtoInput) DOM.produtoInput.value = ''; }
                if (id === 'nunota' && DOM.nunota) DOM.nunota.value = '';
                dispararBusca();
            };
        });

        document.querySelectorAll('button[data-qf]').forEach(btn => {
            const type = btn.dataset.qf;
            btn.style.boxShadow = INTERNAL_STATE[type] ? `0 0 0 2px white, 0 0 0 4px ${type==='pendentes'?'#ef4444':'#22c55e'}` : 'none';
            btn.style.opacity = INTERNAL_STATE[type] ? '1' : '0.5';
        });

        document.querySelectorAll('#agromilToggleClassificacao button[data-classif]').forEach(btn => {
            const isSel = btn.dataset.classif === INTERNAL_STATE.classificacao;
            btn.style.background = isSel ? "#42281E" : "transparent"; 
            btn.style.color = isSel ? "#fff" : "#64748b";
        });
    };

    const buildQueryString = () => {
        const qs = new URLSearchParams();
        if (DOM.dataCompra?.value) {
            qs.set('start', DOM.dataCompra.value);
            qs.set('end', document.getElementById('fltDataCompraFim')?.value || DOM.dataCompra.value);
        } else { qs.set('days', '60'); }

        if (DOM.parceiroCode?.value) qs.set('codparc', DOM.parceiroCode.value);
        if (DOM.nunota?.value) qs.set('nunota', DOM.nunota.value.replace(/\D/g, ''));
        if (DOM.produtoInput?.value) qs.set('fabricante', DOM.produtoInput.value);
        
        const isP = INTERNAL_STATE.pendentes;
        const isF = INTERNAL_STATE.faturados;
        
        if (isP && isF) { qs.set('faturado', 'T'); qs.set('sem_preco', 'T'); } 
        else if (isP) { qs.set('faturado', 'N'); qs.set('sem_preco', '1'); } 
        else if (isF) { qs.set('faturado', 'S'); qs.set('sem_preco', '0'); } 
        else { qs.set('faturado', 'N'); qs.set('sem_preco', ''); }
        
        if (INTERNAL_STATE.classificacao) qs.set('classificacao', INTERNAL_STATE.classificacao);
        return qs.toString();
    };

    const dispararBusca = () => {
        saveState();
        renderVisuals();
        if (window.ComercialLista) window.ComercialLista.load(buildQueryString());
    };

    const dispararBuscaDebounced = debounce(dispararBusca, 400);

    // Mai/2026 — função local mantida porque o callback `onSelectFn` recebe
    // o objeto raw da API (não só cod/descr). Aplicadas melhorias UX padrão:
    // ↑/↓ com preventDefault, Esc fecha, debounce 400ms preservado.
    // Select-on-focus vem do IAgro.installAutoSelect global (base.html).
    const setupAutocomplete = (inputEl, dropEl, urlFn, renderFn, onSelectFn) => {
        if (!inputEl || !dropEl) return;
        let currentFocus = 0;

        const fetchResults = debounce(async () => {
            const q = inputEl.value.trim();
            if (q === '') {
                dropEl.style.display = 'none';
                if (inputEl.id === 'fltFornecedor' && DOM.parceiroCode) DOM.parceiroCode.value = '';
                dispararBusca();
                return;
            }

            try {
                const res = await fetch(urlFn(q));
                const data = await res.json();
                const arr = data.results || [];
                dropEl.innerHTML = '';

                if (arr.length) {
                    arr.forEach((it) => {
                        const div = document.createElement('div');
                        div.className = 'ac-item';
                        div.style = "padding:8px; cursor:pointer; border-bottom:1px solid #f1f5f9;";
                        div.innerHTML = renderFn(it);
                        div.onclick = () => { onSelectFn(it); dropEl.style.display = 'none'; dispararBusca(); };
                        dropEl.appendChild(div);
                    });
                    dropEl.style.display = 'block';
                    currentFocus = 0;
                    addActive(dropEl.getElementsByClassName('ac-item'));
                } else { dropEl.style.display = 'none'; }
            } catch (err) { dropEl.style.display = 'none'; }
        }, 400);

        inputEl.addEventListener('input', fetchResults);

        inputEl.onkeydown = (e) => {
            let items = dropEl.getElementsByClassName('ac-item');
            if (!items.length || dropEl.style.display === 'none') return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();   // Mai/2026 — evita scroll da página
                currentFocus++;
                addActive(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();   // Mai/2026 — evita scroll da página
                currentFocus--;
                addActive(items);
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                if (currentFocus > -1 && items[currentFocus]) { e.preventDefault(); items[currentFocus].click(); }
            } else if (e.key === 'Escape') {
                // Mai/2026 — Esc fecha dropdown sem selecionar (padrão IAgro)
                dropEl.style.display = 'none';
            }
        };

        const addActive = (items) => {
            if (!items) return;
            Array.from(items).forEach(i => i.style.backgroundColor = "");
            if (currentFocus >= items.length) currentFocus = 0;
            if (currentFocus < 0) currentFocus = (items.length - 1);
            items[currentFocus].style.backgroundColor = "#d6e6d1";
            items[currentFocus].scrollIntoView({ block: "nearest" });
        };

        document.addEventListener('click', (e) => { if (e.target !== inputEl && e.target !== dropEl) dropEl.style.display = 'none'; });
    };

    return {
        atualizar: dispararBusca, // 🚀 Expõe a função para recarregar a lista de fora
        init: () => {
            DOM = {
                form: document.getElementById('filtrosForm'),
                parceiroInput: document.getElementById('fltFornecedor'),
                parceiroCode: document.getElementById('fltFornecedorCode'),
                parceiroDrop: document.getElementById('fltFornecedorDropdown'),
                produtoInput: document.getElementById('fltProduto'),
                produtoDrop: document.getElementById('fltProdutoDropdown'),
                dataCompra: document.getElementById('fltDataCompra'),
                nunota: document.getElementById('fltNunota'),
                btnLimpar: document.getElementById('btnLimparFiltros')
            };

            if (!DOM.form) return;

            // Injeção de Botões
            if (!document.getElementById('agromilQuickFilters')) {
                const qfHtml = `
                    <div id="agromilQuickFilters" style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <button type="button" data-qf="pendentes" style="background:#fee2e2; color:#991b1b; border:none; padding:6px 16px; border-radius:20px; font-size:0.75rem; cursor:pointer; font-weight:bold;">Sem preço</button>
                            <button type="button" data-qf="faturados" style="background:#dcfce7; color:#166534; border:none; padding:6px 16px; border-radius:20px; font-size:0.75rem; cursor:pointer; font-weight:bold;">Faturado</button>
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: center;">
                            <label style="font-size: 0.65rem; color: #64748b; font-weight: 800; text-transform: uppercase; margin-bottom: 2px;">Classifica?</label>
                            <div id="agromilToggleClassificacao" style="display:flex; align-items:center; background:#f1f5f9; border-radius:20px; padding:2px; border:1px solid #e2e8f0;">
                                <button type="button" data-classif="S" style="padding:4px 12px; border-radius:18px; border:none; font-size:0.7rem; cursor:pointer; background:transparent; color:#64748b; font-weight:bold;">Sim</button>
                                <button type="button" data-classif="N" style="padding:4px 12px; border-radius:18px; border:none; font-size:0.7rem; cursor:pointer; background:transparent; color:#64748b; font-weight:bold;">Não</button>
                            </div>
                        </div>
                    </div>`;
                DOM.form.insertAdjacentHTML('afterbegin', qfHtml);

                document.getElementById('agromilQuickFilters').onclick = (e) => {
                    const bQf = e.target.closest('button[data-qf]');
                    const bCl = e.target.closest('button[data-classif]');
                    if (bQf) { INTERNAL_STATE[bQf.dataset.qf] = !INTERNAL_STATE[bQf.dataset.qf]; dispararBusca(); }
                    if (bCl) { INTERNAL_STATE.classificacao = (INTERNAL_STATE.classificacao === bCl.dataset.classif) ? '' : bCl.dataset.classif; dispararBusca(); }
                };
            }

            loadState();

            // Navegação de Datas - AGORA ABAIXO DA DATA INICIAL
            const wrapperDataIni = document.getElementById('wrapperDataIni');
            if (DOM.dataCompra && wrapperDataIni && !document.getElementById('agromilDateNav')) {
                DOM.dataCompra.onchange = () => { 
                    const df = document.getElementById('fltDataCompraFim'); 
                    if(df && !df.value) df.value = DOM.dataCompra.value; 
                    dispararBuscaDebounced(); 
                };
                
                wrapperDataIni.insertAdjacentHTML('beforeend', `
                    <div id="agromilDateNav" style="display:flex; gap:5px; margin-top:3px; width:100%;">
                        <button type="button" id="btnDataAnt" style="flex:1; height:18px; cursor:pointer; background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; font-size:0.65rem; font-weight:bold;"><<</button>
                        <button type="button" id="btnDataProx" style="flex:1; height:18px; cursor:pointer; background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; font-size:0.65rem; font-weight:bold;">>></button>
                    </div>`);

                const shiftDate = (n) => {
                    let d = DOM.dataCompra.value ? new Date(DOM.dataCompra.value + 'T00:00:00') : new Date();
                    d.setDate(d.getDate() + n);
                    const iso = d.toISOString().split('T')[0];
                    DOM.dataCompra.value = iso;
                    const df = document.getElementById('fltDataCompraFim'); 
                    if(df) df.value = iso;
                    dispararBusca();
                };
                document.getElementById('btnDataAnt').onclick = () => shiftDate(-1);
                document.getElementById('btnDataProx').onclick = () => shiftDate(1);
            }
            // Vincula o novo botão ATUALIZAR
            
            setupAutocomplete(DOM.parceiroInput, DOM.parceiroDrop, (q) => `/sankhya/parceiros/search/?q=${encodeURIComponent(q)}`, (it) => `${it.codparc} - ${it.nomeparc}`, (it) => { DOM.parceiroInput.value = `${it.codparc} — ${it.nomeparc}`; if (DOM.parceiroCode) DOM.parceiroCode.value = String(it.codparc); });
            setupAutocomplete(DOM.produtoInput, DOM.produtoDrop, (q) => `/sankhya/produtos/search/?q=${encodeURIComponent(q)}&fabricante=1`, (it) => it.fabricante || it.descr, (it) => { DOM.produtoInput.value = it.fabricante || it.descr; });
            
            document.getElementById('btnAtualizarFiltros')?.addEventListener('click', (e) => {
                e.preventDefault(); // 🚀 FIX: Trava de envio de formulário
                dispararBusca();
            });

            // Mai/2026 — filtros via IAgro.wireFilterAuto (500ms debounce padrão)
            IAgro.wireFilterAuto(['fltNunota', 'fltDataCompraFim'], dispararBusca);

            // Select-on-focus agora vem do IAgro.installAutoSelect global (base.html).
            // Removida a duplicação local. Opt-out via `data-no-select` em campo específico.

            DOM.btnLimpar?.addEventListener('click', (e) => {
                e.preventDefault(); // 🚀 FIX: Impede recarregamento da página (F5 fantasma) ao limpar
                DOM.form.reset();
                if (DOM.parceiroCode) DOM.parceiroCode.value = '';
                INTERNAL_STATE.pendentes = false; INTERNAL_STATE.faturados = false; INTERNAL_STATE.classificacao = '';
                
                // Limpa todos os cards da tela
                if (window.ComercialEntrada && window.ComercialEntrada.limpar) window.ComercialEntrada.limpar();
                if (window.ComercialClassificacao && window.ComercialClassificacao.limpar) window.ComercialClassificacao.limpar();
                if (window.ComercialDistribuicao && window.ComercialDistribuicao.limpar) window.ComercialDistribuicao.limpar();
                
                dispararBusca();
            });

            dispararBusca();
        }
    };
})();

/**
 * ============================================================================
 * 4. MÓDULO: GERENCIAMENTO DO CARD ENTRADA (MAPEAMENTO SANKHYA) - CORRIGIDO
 * ============================================================================
 */
window.ComercialEntrada = (function() {
    let DOM = {};

    const fmt = {
        moeda: (v) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        peso: (v) => v.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
        inteiro: (v) => Math.round(v).toLocaleString('pt-BR', { maximumFractionDigits: 0 }), 
        num: (v) => window.ComercialUtils.toNumber(v) || 0
    };

    const recalcularEntrada = () => {
        if (!DOM.card) return;
        const cx = fmt.num(DOM.card.dataset.qtdconferida); 
        const precoCx = fmt.num(DOM.card.dataset.vlrunit); 
        const pesoInNatura = fmt.num(DOM.card.dataset.peso); 

        const total = cx * precoCx;
        DOM.card.dataset.vlrtot = total; 
        if (DOM.totalIn) DOM.totalIn.textContent = fmt.moeda(total);

        const totalPesoAprox = pesoInNatura * cx;
        if (DOM.totalInn) DOM.totalInn.textContent = fmt.inteiro(totalPesoAprox); 

        const precoKg = totalPesoAprox > 0 ? (total / totalPesoAprox) : 0;
        if (DOM.precoKg) DOM.precoKg.textContent = fmt.moeda(precoKg);
    };

    const preencher = (dados) => {
        if (!DOM.card) initDOM();
        
        const isFaturado = window.ComercialUtils.toNumber(dados.nufin) > 0;
        if (isFaturado) document.body.classList.add('vale-faturado'); 
        else document.body.classList.remove('vale-faturado');
        
        const msgDist = document.getElementById('msgFaturadoDist');
        const btnZerar = document.getElementById('btnDistZerar');
        const btnSalvar = document.getElementById('btnDistSalvar');

        if (msgDist && btnZerar && btnSalvar) {
            if (isFaturado) {
                msgDist.style.display = 'block'; btnZerar.style.display = 'none'; btnSalvar.style.display = 'none';
            } else {
                msgDist.style.display = 'none'; btnZerar.style.display = 'block'; btnSalvar.style.display = 'block';
            }
        }
        
        Object.assign(DOM.card.dataset, dados);
        const unidadeReal = (dados.__raw_codvol ?? dados.codvol ?? 'CX').toString().trim().toUpperCase();
        if (DOM.unitLabel) DOM.unitLabel.textContent = unidadeReal;

        if (DOM.product) DOM.product.textContent = dados.produto || '—';
        if (DOM.partner) DOM.partner.textContent = dados.parceiro || '—';
        if (DOM.badgePedido) DOM.badgePedido.textContent = dados.nunota ? `PED. ${dados.nunota}` : '';
        if (DOM.badgeVale) {
            DOM.badgeVale.textContent = dados.nunota_13 ? `VALE ${dados.nunota_13}` : '';
            DOM.badgeVale.style.display = dados.nunota_13 ? 'inline-block' : 'none';
        }

        const qtdPrincipal = window.ComercialUtils.toNumber(dados.qtdconferida) || 0;
        if (DOM.quantidadeInn) DOM.quantidadeInn.textContent = window.ComercialUtils.formatQty(qtdPrincipal);
        
        const pesoInNatura = fmt.num(dados.peso);
        if (DOM.pesoInnDisplay) DOM.pesoInnDisplay.textContent = fmt.inteiro(pesoInNatura); 

        const vlu = fmt.num(dados.vlrunit);
        if (DOM.precoCxDisplay) DOM.precoCxDisplay.textContent = fmt.moeda(vlu);
        if (DOM.precoCxInput) DOM.precoCxInput.value = vlu > 0 ? vlu.toFixed(2).replace('.', ',') : '';

        const pClass = fmt.num(dados.qtdfixada);
        if (DOM.pesoClassDisplay) DOM.pesoClassDisplay.textContent = pClass > 0 ? fmt.inteiro(pClass) : '—';
        if (DOM.pesoClassInput) DOM.pesoClassInput.value = pClass > 0 ? Math.round(pClass).toString() : '';

        if (dados.nufin) DOM.card.classList.add('locked');
        else DOM.card.classList.remove('locked');

        recalcularEntrada();
        DOM.card.style.borderLeft = "6px solid #42281E"; 
    };

    const limpar = () => {
        if (!DOM.card) return;
        const resets = {
            'entProduct': '', 'entPartner': '', 'entBadgePedido': '', 'entBadgeVale13': '',
            'quantidadeInn': '0', 'entUnit': 'CX', 'entPrecoCxDisplay': '0,00',
            'entPrecoKg': '0,00', 'entTotalIn': '0,00', 'pesoClassificadoDisplay': '—',
            'pesoInnDisplay': '0,000', 'totalInn': '0,000'
        };
        Object.entries(resets).forEach(([id, val]) => {
            const el = document.getElementById(id); if (el) el.textContent = val;
        });
        document.querySelectorAll('#entradaCard .preco-input').forEach(i => i.value = '');
        if (DOM.badgeVale) DOM.badgeVale.style.display = 'none';
        DOM.card.classList.remove('editing', 'editing-cx', 'locked');
        DOM.card.style.borderLeft = "none";
        for (let key in DOM.card.dataset) { delete DOM.card.dataset[key]; }
    };

    const initDOM = () => {
        DOM = {
            card: document.getElementById('entradaCard'),
            product: document.getElementById('entProduct'),
            partner: document.getElementById('entPartner'),
            badgePedido: document.getElementById('entBadgePedido'),
            badgeVale: document.getElementById('entBadgeVale13'),
            quantidadeInn: document.getElementById('quantidadeInn'),
            unitLabel: document.getElementById('entUnit'),
            precoCxDisplay: document.getElementById('entPrecoCxDisplay'),
            precoCxInput: document.getElementById('entPrecoCxInput'),
            precoKg: document.getElementById('entPrecoKg'),
            totalIn: document.getElementById('entTotalIn'),
            pesoClassDisplay: document.getElementById('pesoClassificadoDisplay'),
            pesoClassInput: document.getElementById('pesoClassificadoInput'),
            pesoInnDisplay: document.getElementById('pesoInnDisplay'),
            totalInn: document.getElementById('totalInn')
        };
    };

    return {
        preencher, limpar,
        init: () => {
            initDOM();
            if (!DOM.card) return;

            const setupEdit = (displayId, inputId, attrName) => {
                const display = document.getElementById(displayId);
                const input = document.getElementById(inputId);
                if (!display || !input) return;

                display.onclick = (e) => {
                    e.stopPropagation();
                    if (DOM.card.classList.contains('locked')) {
                        window.ComercialUtils.mostrarToast("Este vale está faturado.", "aviso");
                        return;
                    }
                    display.style.visibility = 'hidden';
                    input.style.display = 'inline-block';
                    input.focus(); input.select();
                };

                input.onblur = async () => {
                    display.style.visibility = 'visible';
                    input.style.display = 'none';
                    
                    const novoVal = fmt.num(input.value);
                    const valorAntigo = fmt.num(DOM.card.dataset[attrName]);
                    
                    // Se não mudou nada, não faz nada
                    if (novoVal === valorAntigo) return; 

                    // 🚀 1. ATUALIZAÇÃO IMEDIATA DO "MEMORIAL" DO CARD
                    // Guardamos os dados da nota ANTES de qualquer refresh da lista
                    const snapshotDados = { ...DOM.card.dataset }; 
                    const selectedIdx = document.querySelector('tr.lista-item-row.row--sel')?.dataset?.idx;

                    DOM.card.dataset[attrName] = novoVal;
                    display.textContent = displayId.includes('Preco') ? fmt.moeda(novoVal) : fmt.inteiro(novoVal);
                    recalcularEntrada();

                    // Atualiza a memória global se ela ainda existir
                    if (selectedIdx !== undefined && window.__COM_LIST_ROWS?.[selectedIdx]) {
                        window.__COM_LIST_ROWS[selectedIdx][attrName] = novoVal;
                        if (attrName === 'vlrunit') window.__COM_LIST_ROWS[selectedIdx].precobase = novoVal;
                    }

                    const csrfToken = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
                    const urlApi = attrName === 'vlrunit' ? '/sankhya/comercial/api/atualizar-preco/' : '/sankhya/comercial/api/atualizar-peso/';
                    
                    const payload = {
                        nunota: parseInt(snapshotDados.nunota),
                        sequencia: parseInt(snapshotDados.sequencia),
                        [attrName === 'vlrunit' ? 'preco_inicial' : 'peso_classificado']: novoVal
                    };

                    if (attrName === 'vlrunit') {
                        payload.qtdconferida = fmt.num(snapshotDados.qtdconferida);
                        payload.geraproducao = snapshotDados.geraproducao || 'S';
                        payload.peso = fmt.num(snapshotDados.peso);
                    }

                    try {
                        const res = await fetch(urlApi, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                            body: JSON.stringify(payload)
                        });
                        const data = await res.json();
                        if (!data.ok) throw new Error(data.error || 'Erro ao salvar');

                        window.ComercialUtils.mostrarToast('Salvo com sucesso!', 'sucesso');

                        // 🚀 2. ATUALIZAÇÃO DOS OUTROS CARDS (Sem depender da lista lateral)
                        // Usamos o snapshot que tiramos no começo da função
                        if (window.ComercialClassificacao) {
                            // Atualizamos o valor no snapshot para os outros cards lerem o dado novo
                            snapshotDados[attrName] = novoVal; 
                            window.ComercialClassificacao.preencher(snapshotDados).then(pesos => {
                                window.ComercialDistribuicao?.preencher(snapshotDados, pesos);
                            });
                        }

                        // 🚀 3. ATUALIZAÇÃO DA BOLINHA NA LISTA (Se ela ainda estiver lá)
                        const row = document.querySelector(`tr.lista-item-row[data-idx="${selectedIdx}"]`);
                        if (row && attrName === 'vlrunit') {
                            const dot = row.querySelector('.status-dot');
                            if (dot) { dot.classList.remove('vermelho'); dot.classList.add('verde'); }
                        }

                        // 🚀 4. REFRESH GLOBAL (Mai/2026) — recarrega a lista lateral
                        // imediato após sucesso. Crítico em produto in natura: o
                        // Fast-Track cria/atualiza vale TOP 13 no backend, então a
                        // bolinha de status e o vale derivado precisam refletir o
                        // novo estado sem esperar F5. Sem setTimeout (era 500ms).
                        if (window.ComercialFiltros?.atualizar) {
                            window.ComercialFiltros.atualizar();
                        }

                    } catch (err) {
                        console.error("Erro ao salvar:", err);
                        window.ComercialUtils.mostrarToast("Erro ao salvar: " + err.message, "erro");
                        // Volta o valor antigo em caso de erro real de banco
                        DOM.card.dataset[attrName] = valorAntigo;
                        display.textContent = displayId.includes('Preco') ? fmt.moeda(valorAntigo) : fmt.inteiro(valorAntigo);
                        recalcularEntrada();
                    }
                };
                input.onkeydown = (e) => { if(e.key === 'Enter') input.blur(); };
            };

            setupEdit('entPrecoCxDisplay', 'entPrecoCxInput', 'vlrunit');
            setupEdit('pesoClassificadoDisplay', 'pesoClassificadoInput', 'qtdfixada');
        }
    };
})();

/**
 * ============================================================================
 * 5. MÓDULO: GERENCIAMENTO DO CARD CLASSIFICAÇÃO (BALANÇO DE MASSA)
 * ============================================================================
 */
window.ComercialClassificacao = (function() {
    let DOM = {};
    const fmtInt = (v) => Math.round(window.ComercialUtils.toNumber(v) || 0).toLocaleString('pt-BR');
    const fmtDec1 = (v) => window.ComercialUtils.toNumber(v).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

    const corInicio = '#42281E'; 
    const corFim = '#5E7D5E';    

    const interpolarCor = (p) => {
        const r1 = parseInt(corInicio.slice(1, 3), 16), g1 = parseInt(corInicio.slice(3, 5), 16), b1 = parseInt(corInicio.slice(5, 7), 16);
        const r2 = parseInt(corFim.slice(1, 3), 16), g2 = parseInt(corFim.slice(3, 5), 16), b2 = parseInt(corFim.slice(5, 7), 16);
        const r = Math.round(r1 + (r2 - r1) * (p / 100));
        const g = Math.round(g1 + (g2 - g1) * (p / 100));
        const b = Math.round(b1 + (b2 - b1) * (p / 100));
        return `rgb(${r}, ${g}, ${b})`;
    };

    const initDOM = () => {
        DOM = {
            inNatura: document.getElementById('resInnKg'),
            classificado: document.getElementById('resClassKg'), 
            descarte: document.getElementById('resInservKg'),
            aproveitado: document.getElementById('resAprovKg'),  
            gaugePct: document.getElementById('gPct'),
            gaugeArc: document.getElementById('gArc'),
            classBody: document.getElementById('classBody'),
            loteBadge: document.getElementById('classLoteBadge'),
            fabName: document.getElementById('classFabricanteName'),
            kpiEstoque: document.getElementById('kpiEstoque'),
            kpiEstoqueApprox: document.getElementById('kpiEstoqueApprox')
        };
    };

    const atualizarGauge = (pct) => {
        if (!DOM.gaugePct || !DOM.gaugeArc) return;
        const length = DOM.gaugeArc.getTotalLength ? DOM.gaugeArc.getTotalLength() : 282.74;
        DOM.gaugeArc.style.strokeDasharray = length;

        const realPct = window.ComercialUtils.toNumber(pct) || 0;
        const p = Math.max(0, Math.min(100, realPct)); 
        
        DOM.gaugePct.textContent = `${fmtDec1(realPct)}%`;
        
        const offset = length - (p / 100) * length;
        DOM.gaugeArc.style.strokeDashoffset = offset;
        DOM.gaugeArc.style.stroke = interpolarCor(p); 
    };

    const preencher = async (dadosDaLinha) => {
        initDOM();
        const lote = dadosDaLinha.codagregacao;
        const nunotaOrigem = dadosDaLinha.nunota;

        if (!lote) { limpar(); return; }

        if (DOM.gaugeArc) {
            const length = DOM.gaugeArc.getTotalLength ? DOM.gaugeArc.getTotalLength() : 282.74;
            DOM.gaugeArc.style.transition = 'none'; 
            DOM.gaugeArc.style.strokeDasharray = length; 
            DOM.gaugeArc.style.strokeDashoffset = length; 
            DOM.gaugeArc.getBoundingClientRect(); 
            DOM.gaugeArc.style.transition = 'stroke-dashoffset 1.5s ease-out, stroke 1.5s ease-out'; 
        }

        // Mai/2026 — 2026-05-17: badge do lote agora aparece de fato no
        // header (antes estava com display:none inline e só o textContent
        // era atualizado). Mostra/esconde via .hidden — coerente com limpar().
        if (DOM.loteBadge) {
            DOM.loteBadge.textContent = `LOTE ${lote}`;
            DOM.loteBadge.classList.remove('hidden');
        }
        if (DOM.fabName) DOM.fabName.textContent = dadosDaLinha.fabricante || dadosDaLinha.produto || '';

        try {
            const url = `/sankhya/lote/consultar/?lote=${encodeURIComponent(lote)}&nunota_origem=${nunotaOrigem}`;
            const res = await fetch(url);
            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            const resumo = data.resumo || {};
            const itens = data.classificacoes || []; 
            const pesoCxEntrada = window.ComercialUtils.toNumber(dadosDaLinha.qtdfixada || 0);
            
            const inNaturaKg = window.ComercialUtils.toNumber(resumo.in_natura || 0);
            const inNaturaCx = window.ComercialUtils.toNumber(dadosDaLinha.qtdconferida || 0);
            const apenasBomKg = itens.reduce((acc, curr) => acc + window.ComercialUtils.toNumber(curr.qtd || 0), 0);
            const apenasBomCx = pesoCxEntrada > 0 ? (apenasBomKg / pesoCxEntrada) : 0;
            const descarteKg = window.ComercialUtils.toNumber(resumo.descarte || 0);
            const descarteCx = pesoCxEntrada > 0 ? (descarteKg / pesoCxEntrada) : 0;

            const cardElement = document.getElementById('classCard');
            if (cardElement) {
                if (dadosDaLinha.pendente === 'N') { 
                    cardElement.classList.add('is-finalizado');
                    if (!cardElement.querySelector('.carimbo-finalizado')) {
                        const carimbo = document.createElement('div');
                        carimbo.className = 'carimbo-finalizado';
                        carimbo.textContent = 'FINALIZADO';
                        cardElement.appendChild(carimbo);
                    }
                } else {
                    cardElement.classList.remove('is-finalizado');
                }
            }

            const ehInNatura = (dadosDaLinha.geraproducao !== 'S');
            const volOrigem = (dadosDaLinha.codvol || 'cx').toLowerCase();

            const setBalanco = (idMain, valor, sigla, apagar) => {
                const el = document.getElementById(idMain);
                if (el) {
                    el.textContent = apagar ? '' : fmtInt(valor);
                    if (el.nextElementSibling) el.nextElementSibling.textContent = apagar ? '' : sigla;
                }
            };

            const totalPassouEsteiraKg = apenasBomKg + descarteKg;
            const totalPassouEsteiraCx = apenasBomCx + descarteCx;

            setBalanco('resInnKg', inNaturaKg, 'kg', ehInNatura);
            setBalanco('resInnCx', inNaturaCx, volOrigem, ehInNatura);
            
            setBalanco('resClassKg', totalPassouEsteiraKg, 'kg', ehInNatura);
            setBalanco('resClassCx', totalPassouEsteiraCx, volOrigem, ehInNatura);
            
            setBalanco('resInservKg', descarteKg, 'kg', ehInNatura);
            setBalanco('resInservCx', descarteCx, volOrigem, ehInNatura);
            
            setBalanco('resAprovKg', apenasBomKg, 'kg', ehInNatura);
            setBalanco('resAprovCx', apenasBomCx, volOrigem, ehInNatura);
            
            const gaugePctValue = inNaturaKg > 0 ? ((apenasBomKg + descarteKg) / inNaturaKg) * 100 : 0;
            const estoqueKg = inNaturaKg - (apenasBomKg + descarteKg);
            
            
            // 🚀 CÁLCULOS DO RENDIMENTO (QUEBRADO EM DUAS LINHAS)
            const rendimentoKg = inNaturaKg - (inNaturaCx * pesoCxEntrada) - descarteKg;
            const rendimentoCx = pesoCxEntrada > 0 ? ((inNaturaKg - descarteKg) / pesoCxEntrada) - inNaturaCx : 0;
            const rendimentoPct = inNaturaKg > 0 ? (rendimentoKg / inNaturaKg) * 100 : 0;

            const elRend = document.getElementById('kpiRendimento');
            if (elRend) {
                // Injeta HTML para quebrar a linha mantendo a formatação
                elRend.innerHTML = ehInNatura ? '' : `
                    <div style="font-weight: 900; color: #1e293b; line-height: 1.1;">${fmtInt(rendimentoKg)} kg</div>
                    <div style="font-size: 0.85rem; color: #1e293b; margin-top: 4px;">~ ${fmtDec1(rendimentoCx)} <small>${volOrigem}</small></div>
                `;
            }

            const elRendDetalhe = document.getElementById('kpiRendDetalhe');
            if (elRendDetalhe) {
                elRendDetalhe.textContent = ehInNatura ? '' : `${fmtDec1(rendimentoPct)}%`;
            }

            // =========================================================================
            // 🚀 MÁGICA DA QUEBRA INVISÍVEL (DIFERENÇA) vs ESTOQUE
            // =========================================================================
            const isFinalizado = (dadosDaLinha.pendente === 'N');
            const diferencaTotalKg = inNaturaKg - (apenasBomKg + descarteKg); 
            
            let estoqueKgParaMostrar = 0;
            let diferencaKgParaMostrar = 0;

            if (isFinalizado) {
                estoqueKgParaMostrar = 0; // Finalizado: Estoque zera
                diferencaKgParaMostrar = diferencaTotalKg; // Sobra vai pra Diferença
            } else {
                estoqueKgParaMostrar = diferencaTotalKg; // Aberto: Sobra é Estoque
                diferencaKgParaMostrar = 0; 
            }

            const cxInNaturaAPI = window.ComercialUtils.toNumber(resumo.cx_in_natura || 0);
            const pesoCaixaInNatura = cxInNaturaAPI > 0 ? (inNaturaKg / cxInNaturaAPI) : 0;
            const estoqueCxParaMostrar = pesoCaixaInNatura > 0 ? (estoqueKgParaMostrar / pesoCaixaInNatura) : 0;
            const diferencaCxParaMostrar = pesoCaixaInNatura > 0 ? (diferencaKgParaMostrar / pesoCaixaInNatura) : 0;

            // 1. INJEÇÃO DINÂMICA DA LINHA "DIFERENÇA" (ABAIXO DE APROVEITADO)
            let rowDif = document.getElementById('linha-diferenca-bm');
            
            if (!rowDif && !ehInNatura) {
                const elAproveitado = document.getElementById('resAprovKg');
                if (elAproveitado) {
                    let parentRow = elAproveitado;
                    // Sobe na árvore até achar o container da linha 'Aproveitado'
                    while(parentRow && !parentRow.textContent.includes('Aproveitado')) { parentRow = parentRow.parentElement; }
                    if (!parentRow || parentRow.tagName === 'BODY') parentRow = elAproveitado.parentElement.parentElement; 
                    
                    if (parentRow) {
                        rowDif = parentRow.cloneNode(true);
                        rowDif.id = 'linha-diferenca-bm';
                        rowDif.style.color = '#dc2626'; // Vermelho
                        
                        // Troca o texto Aproveitado para Diferença
                        const walker = document.createTreeWalker(rowDif, NodeFilter.SHOW_TEXT, null, false);
                        let node;
                        while (node = walker.nextNode()) {
                            if (/Aproveitado/i.test(node.nodeValue)) node.nodeValue = 'Diferença';
                        }
                        
                        // Atualiza IDs para injeção de valores
                        const kgEl = rowDif.querySelector('#resAprovKg'); if(kgEl) kgEl.id = 'resDifKg';
                        const cxEl = rowDif.querySelector('#resAprovCx'); if(cxEl) cxEl.id = 'resDifCx';
                        
                        // Insere DEPOIS da linha Aproveitado
                        parentRow.parentNode.insertBefore(rowDif, parentRow.nextSibling);
                    }
                }
            }

            if (document.getElementById('resDifKg')) {
                setBalanco('resDifKg', diferencaKgParaMostrar, 'kg', ehInNatura || diferencaKgParaMostrar === 0);
                setBalanco('resDifCx', diferencaCxParaMostrar, volOrigem, ehInNatura || diferencaKgParaMostrar === 0);
                if (rowDif) {
                    // Exibe a linha apenas se o lote estiver finalizado
                    rowDif.style.display = isFinalizado ? 'flex' : 'none'; 
                }
            }

            // 2. RESTAURAÇÃO E ATUALIZAÇÃO DO CARD ESTOQUE (LINHA ÚNICA)
            if (DOM.kpiEstoque) {
                DOM.kpiEstoque.textContent = ehInNatura ? '' : `${fmtInt(estoqueKgParaMostrar)} kg`;
                
                // Desfaz qualquer alteração de estilo feita pela versão anterior
                DOM.kpiEstoque.style.display = 'inline';
                DOM.kpiEstoque.style.fontSize = '';
                DOM.kpiEstoque.style.fontWeight = '';
                
                const gaugeBox = DOM.kpiEstoque.parentElement;
                if (gaugeBox) {
                    gaugeBox.style.color = ''; 
                    
                    // Restaura a palavra "ESTOQUE" caso tenha sido alterada
                    const walker = document.createTreeWalker(gaugeBox, NodeFilter.SHOW_TEXT, null, false);
                    let textNode;
                    while (textNode = walker.nextNode()) {
                        if (/DIFERENÇA \(TERRA\)/i.test(textNode.nodeValue)) {
                            textNode.nodeValue = 'ESTOQUE '; 
                        }
                    }
                    
                    // Restaura o CSS do label
                    const spanLabel = gaugeBox.querySelector('span');
                    if (spanLabel && spanLabel.textContent.includes('ESTOQUE')) {
                        spanLabel.style.display = 'inline';
                        spanLabel.style.fontSize = '';
                        spanLabel.style.marginBottom = '';
                        spanLabel.style.letterSpacing = '';
                    }
                }
            }
            
            if (DOM.kpiEstoqueApprox) {
                DOM.kpiEstoqueApprox.textContent = ehInNatura ? '' : ` ~ ${fmtDec1(estoqueCxParaMostrar)} ${volOrigem}`;
                DOM.kpiEstoqueApprox.style.display = 'inline';
                DOM.kpiEstoqueApprox.style.fontSize = '';
                DOM.kpiEstoqueApprox.style.color = '';
                DOM.kpiEstoqueApprox.style.marginTop = '';
            }

            let pesosParaDist = { extraKg: 0, medioKg: 0 }; 

            if (DOM.classBody) {
                // 🚀 FIX: Arrancamos a "muleta" de jogar inNaturaKg no ExtraKg. Se for de máquina, e não passou ainda, manda ZERADO!
                if (itens.length === 0 && descarteKg === 0) {
                    if (ehInNatura) {
                        pesosParaDist.extraKg = inNaturaKg;
                        DOM.classBody.innerHTML = '<div style="color:#94a3b8; padding:15px; text-align:center; font-size:0.75rem;">Sem classificação realizada</div>';
                    } else {
                        // Se o produto exige classificação, avisa visualmente e não chuta peso nenhum pro Extra!
                        pesosParaDist.extraKg = 0; 
                        DOM.classBody.innerHTML = '<div style="color:#ea580c; padding:15px; text-align:center; font-weight: bold; font-size:0.75rem;">Aguardando retorno da Máquina...</div>';
                    }
                } 
                else {
                    const agrupados = itens.reduce((acc, curr) => {
                        const nome = curr.descr || 'Outros';
                        if (!acc[nome]) acc[nome] = { nome: nome, total: 0 };
                        acc[nome].total += window.ComercialUtils.toNumber(curr.qtd || 0);
                        return acc;
                    }, {});

                    const baseTotalParaPct = apenasBomKg + descarteKg;
                    
                    let htmlFinal = Object.values(agrupados).map(it => {
                        const pct = baseTotalParaPct > 0 ? (it.total / baseTotalParaPct * 100) : 0;
                        const qtdCxIt = pesoCxEntrada > 0 ? (it.total / pesoCxEntrada) : 0;
                        return `
                            <div class="class-item-row" style="padding:4px 0; border-bottom:1px solid #f1f5f9;">
                                <div class="class-item-info" style="display:flex; justify-content:space-between; font-weight:700; color:#334155; font-size:0.7rem; margin-bottom:2px;">
                                    <span style="text-transform:uppercase;">${window.ComercialUtils.escapeHTML(it.nome)}</span>
                                    <span>${fmtInt(it.total)}<small style="color:#94a3b8; font-weight:400; margin-left:1px;">kg</small></span>
                                </div>
                                <div class="class-item-bar-wrapper" style="display:flex; align-items:center; gap:6px;">
                                    <span style="color:#475569; font-weight:800; font-size:0.65rem; min-width:32px; text-align:right;">${fmtDec1(pct)}%</span>
                                    <div style="flex-grow:1; height:4px; background:#f1f5f9; border-radius:4px; overflow:hidden;">
                                        <div style="height:100%; background:var(--accent); width:${Math.min(100, pct)}%"></div>
                                    </div>
                                    <span style="color:#64748b; font-weight:700; font-size:0.65rem; min-width:40px; text-align:right;">
                                        ${fmtDec1(qtdCxIt)}<small style="font-size:0.55rem; font-weight:400;">cx</small>
                                    </span>
                                </div>
                            </div>`;
                    }).join('');

                    if (descarteKg > 0) {
                        const pctAvaria = baseTotalParaPct > 0 ? (descarteKg / baseTotalParaPct * 100) : 0;
                        const qtdCxAvaria = pesoCxEntrada > 0 ? (descarteKg / pesoCxEntrada) : 0;
                        htmlFinal += `
                            <div class="class-item-row avaria-row" style="padding:6px 0 2px 0; margin-top:2px; border-top:1px dashed #e5e7eb;">
                                <div class="class-item-info" style="display:flex; justify-content:space-between; font-weight:700; color:#dc2626; font-size:0.7rem; margin-bottom:2px;">
                                    <span style="letter-spacing:-0.2px;">DESCARTE / AVARIA</span>
                                    <span style="color:#dc2626;">${fmtInt(descarteKg)}<small style="color:#94a3b8; margin-left:1px;">kg</small></span>
                                </div>
                                <div class="class-item-bar-wrapper" style="display:flex; align-items:center; gap:6px;">
                                    <span style="color:#dc2626; font-weight:800; font-size:0.65rem; min-width:32px; text-align:right;">${fmtDec1(pctAvaria)}%</span>
                                    <div style="flex-grow:1; height:4px; background:#fef2f2; border-radius:4px; overflow:hidden;">
                                        <div style="height:100%; background:#dc2626; width:${Math.min(100, pctAvaria)}%"></div>
                                    </div>
                                    <span style="color:#dc2626; font-weight:700; font-size:0.65rem; min-width:40px; text-align:right;">
                                        ${fmtDec1(qtdCxAvaria)}<small style="font-size:0.55rem; font-weight:400; color:#94a3b8;">cx</small>
                                    </span>
                                </div>
                            </div>`;
                    }
                    
                    DOM.classBody.innerHTML = htmlFinal;

                    pesosParaDist.extraKg = itens
                        .filter(it => Number(it.selecionado) === 1)
                        .reduce((acc, curr) => acc + window.ComercialUtils.toNumber(curr.qtd), 0);

                    pesosParaDist.medioKg = itens
                        .filter(it => Number(it.selecionado) !== 1)
                        .reduce((acc, curr) => acc + window.ComercialUtils.toNumber(curr.qtd), 0);

                    const itemExtra = itens.find(it => Number(it.selecionado) === 1);
                    const itemMedio = itens.find(it => it.caracteristicas && it.caracteristicas.includes('MEDIO')) 
                                   || itens.find(it => Number(it.selecionado) === 2) 
                                   || itens.find(it => Number(it.selecionado) !== 1);

                    pesosParaDist.extraCodProd = itemExtra ? (itemExtra.codprod || itemExtra.cod) : null;
                    pesosParaDist.medioCodProd = itemMedio ? (itemMedio.codprod || itemMedio.cod) : null;
                }
            }

            setTimeout(() => { 
                if (typeof atualizarGauge === 'function') atualizarGauge(gaugePctValue); 
            }, 50);

            return pesosParaDist; 

        } catch (err) {
            console.error("Erro ao buscar balanço do lote:", err);
            limpar();
            return { extraKg: 0, medioKg: 0 };
        }
    };

    const limpar = () => {
        initDOM();
        
        // 1. Limpa KG e CX do balanço de massa simultaneamente
        ['resInnKg', 'resInnCx', 'resClassKg', 'resClassCx', 'resInservKg', 'resInservCx', 'resAprovKg', 'resAprovCx'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '0';
        });
        
        // 2. Limpa Rendimento
        const elRend = document.getElementById('kpiRendimento'); if (elRend) elRend.textContent = '0%';
        const elRendDetalhe = document.getElementById('kpiRendDetalhe'); if (elRendDetalhe) elRendDetalhe.textContent = '0 kg ~ 0 cx';

        if (DOM.kpiEstoque) DOM.kpiEstoque.textContent = '-';
        if (DOM.kpiEstoqueApprox) DOM.kpiEstoqueApprox.textContent = '';
        if (DOM.classBody) DOM.classBody.innerHTML = '';
        if (DOM.loteBadge) {
            DOM.loteBadge.textContent = '';
            DOM.loteBadge.classList.add('hidden');
        }
        if (DOM.fabName) DOM.fabName.textContent = '';
        if (DOM.gaugeArc) atualizarGauge(0);

        // 3. Remove o carimbo FINALIZADO
        const cardElement = document.getElementById('classCard');
        if (cardElement) cardElement.classList.remove('is-finalizado');
    };

    return { init: initDOM, preencher, limpar };
})();

/**
 * ============================================================================
 * GATILHO DE INICIALIZAÇÃO SEGURA (MASTER)
 * ============================================================================
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('%c[AGROMIL] DOM pronto. Iniciando módulos...', 'color: #0ea5e9; font-weight: bold;');
    
    // 1. Inicializa todos os módulos do sistema
    if (window.ComercialEntrada) window.ComercialEntrada.init();
    if (window.ComercialClassificacao) window.ComercialClassificacao.init();
    if (window.ComercialLista) window.ComercialLista.init();
    if (window.ComercialFiltros) window.ComercialFiltros.init();

    // ========================================================================
    // 2. FECHAMENTO DE MODAIS (ESC e Clique Fora) - Versão Inteligente
    // ========================================================================
    const modalIds = ['modalImpressao', 'modalFaturamento', 'fechamentoModal'];

    const fecharModalAdequadamente = (id) => {
        const modal = document.getElementById(id);
        if (!modal || window.getComputedStyle(modal).display === 'none') return false;

        if (id === 'modalImpressao' && window.ComercialImpressao) {
            window.ComercialImpressao.fechar();
        } else if ((id === 'modalFaturamento' || id === 'fechamentoModal') && window.ComercialFinanceiro && window.ComercialFinanceiro.fechar) {
            window.ComercialFinanceiro.fechar();
        } else {
            modal.style.display = 'none';
        }
        return true; // Retorna true se fechou algo
    };

    // Fechar com a tecla ESC - Um por vez (do topo para baixo)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Ordem de prioridade: tenta fechar o que está na frente primeiro
            // Se fechar a Impressão (que retornará true), o "||" para e não tenta fechar o Faturamento.
            fecharModalAdequadamente('modalImpressao') || 
            fecharModalAdequadamente('modalFaturamento') || 
            fecharModalAdequadamente('fechamentoModal');
        }
    });

    // Fechar clicando fora (no overlay escuro)
    document.addEventListener('click', (e) => {
        modalIds.forEach(id => {
            const modal = document.getElementById(id);
            if (modal && e.target === modal) {
                fecharModalAdequadamente(id);
            }
        });
    });
});
