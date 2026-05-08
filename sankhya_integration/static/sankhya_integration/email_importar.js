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
    // UX: select-all-on-focus em todos os inputs DESTA tela.
    // Operador clica num campo já preenchido (ex: "456 — SENDAS"),
    // texto fica todo selecionado, basta digitar pra substituir.
    // Escopado via container .email-grid pra não vazar pra outras
    // telas (em modal-overlays incluídos por DOM-aninhamento).
    // Use data-no-select num input pra desabilitar caso a caso.
    // ============================================================
    const _TIPOS_AUTOSEL = new Set(['text', 'number', 'search', 'tel', 'email', 'url']);
    const _emailContainer = document.querySelector('.email-grid');
    if (_emailContainer) {
        _emailContainer.addEventListener('focusin', function (e) {
            const t = e.target;
            if (!t || t.dataset?.noSelect !== undefined) return;
            if (t.readOnly || t.disabled) return;
            if (t.tagName === 'INPUT' && _TIPOS_AUTOSEL.has(t.type)) {
                // setTimeout 0 evita que o click subsequente desfaça o select
                setTimeout(() => { try { t.select(); } catch (_) {} }, 0);
            } else if (t.tagName === 'TEXTAREA') {
                setTimeout(() => { try { t.select(); } catch (_) {} }, 0);
            }
        });
    }

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
    const restaurarTodosBtn = document.getElementById('emailRestaurarTodosBtn');
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

        function hide() {
            dd.style.display = 'none';
            dd.innerHTML = '';
            // Reseta posição inline aplicada pelo show()
            dd.style.position = '';
            dd.style.top = '';
            dd.style.left = '';
            dd.style.width = '';
            dd.style.zIndex = '';
        }
        function show(items) {
            if (!items || !items.length) { hide(); return; }
            dd.innerHTML = items.map((it, idx) => {
                const cod = it.cod || it.codparc || it.codemp || it.codtipvenda;
                const desc = it.descr || it.nomeparc || it.nomefantasia || it.descrtipvenda || '';
                return `<div class="dd-item${idx === 0 ? ' active' : ''}" data-cod="${cod}" data-descr="${desc}">${cod} — ${desc}</div>`;
            }).join('');
            // Position FIXED com coordenadas calculadas direto do input visível.
            // Ignora qualquer overflow:hidden / containing block instável em
            // ancestrais (problema clássico de dropdown dentro de <td>).
            // Move o dropdown pro <body> pra escapar de qualquer stacking
            // context que o pai possa ter criado.
            if (dd.parentElement !== document.body) {
                document.body.appendChild(dd);
            }
            const r = inp.getBoundingClientRect();
            dd.style.position = 'fixed';
            dd.style.top      = `${r.bottom}px`;
            dd.style.left     = `${r.left}px`;
            dd.style.width    = `${r.width}px`;
            dd.style.zIndex   = '10000';
            dd.style.display  = 'block';
            console.log(`[typeahead] show(${items.length}) -> #${dd.id}`,
                        `top=${r.bottom} left=${r.left} width=${r.width}`);
        }

        async function buscar() {
            const q = inp.value.trim();
            if (q.length < 1) { hide(); return; }
            // extraQuery permite repassar filtros adicionais ao endpoint
            // (ex: grupo_inicia_com=1 para limitar TGFPRO ao grupo 1xxxx,
            // mesmo filtro usado pela Venda — produtos vendáveis do
            // hortifrúti, sem insumos/mudas/embalagens).
            const extra = options && options.extraQuery ? `&${options.extraQuery}` : '';
            const fullUrl = `${url}?q=${encodeURIComponent(q)}&limit=${options.limit || 10}${extra}`;
            try {
                const r = await fetch(fullUrl, { credentials: 'same-origin' });
                if (!r.ok) {
                    console.warn(`[typeahead] ${fullUrl} -> HTTP ${r.status}`);
                    phToast(`Busca falhou (HTTP ${r.status})`, 'error');
                    hide();
                    return;
                }
                const data = await r.json();
                const items = data.results || data.items || data || [];
                console.log(`[typeahead] ${fullUrl} -> ${items.length} resultado(s)`, items);
                show(items);
            } catch (e) {
                console.error(`[typeahead] ${fullUrl} ->`, e);
                phToast('Erro de rede na busca: ' + (e.message || e), 'error');
                hide();
            }
        }

        inp.addEventListener('input', () => {
            clearTimeout(t);
            t = setTimeout(buscar, 250);
        });

        // Helper: aplica seleção do item ativo ao campo (mesmo fluxo do click).
        function selecionarItem(item) {
            hid.value = item.dataset.cod;
            inp.value = `${item.dataset.cod} — ${item.dataset.descr}`;
            hide();
            // Callback opcional: dispara após o usuário escolher no dropdown.
            if (options && typeof options.onChange === 'function') {
                options.onChange(item.dataset.cod, item.dataset.descr);
            }
        }

        dd.addEventListener('click', e => {
            const item = e.target.closest('.dd-item');
            if (item) selecionarItem(item);
        });

        // Navegação por teclado quando o dropdown está aberto:
        //   ↓ / ↑       — move o destaque entre os itens
        //   Enter / Tab — confirma a seleção do item ativo (Tab continua pro próximo campo)
        //   Escape      — fecha o dropdown sem selecionar
        inp.addEventListener('keydown', e => {
            if (dd.style.display === 'none') return;
            const items = Array.from(dd.querySelectorAll('.dd-item'));
            if (!items.length) return;
            let idx = items.findIndex(i => i.classList.contains('active'));
            if (idx < 0) idx = 0;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                idx = (idx + 1) % items.length;
                items.forEach(i => i.classList.remove('active'));
                items[idx].classList.add('active');
                items[idx].scrollIntoView({block: 'nearest'});
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                idx = (idx - 1 + items.length) % items.length;
                items.forEach(i => i.classList.remove('active'));
                items[idx].classList.add('active');
                items[idx].scrollIntoView({block: 'nearest'});
            } else if (e.key === 'Enter') {
                e.preventDefault();           // não submete o form / não fecha modal
                selecionarItem(items[idx]);
            } else if (e.key === 'Tab') {
                // Tab confirma e segue o fluxo natural — vai pro próximo campo
                selecionarItem(items[idx]);
                // sem preventDefault: Tab continua a navegação
            } else if (e.key === 'Escape') {
                hide();
            }
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
        // Atualiza contador no header. Cor depende do volume: verde até 5,
        // laranja 6-15, vermelho >15. Só mostra quando o filtro é PENDENTE.
        const contadorEl = document.getElementById('emailFilaContador');
        if (contadorEl) {
            if (statusAtual === 'PENDENTE_REVISAO' && rows.length > 0) {
                contadorEl.textContent = rows.length;
                contadorEl.className = 'email-fila-contador ' +
                    (rows.length <= 5 ? 'cont-baixo' :
                     rows.length <= 15 ? 'cont-medio' : 'cont-alto');
            } else {
                contadorEl.textContent = '';
                contadorEl.className = 'email-fila-contador';
            }
        }
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

        // Badge de origem da extração — distingue parser regex (rápido,
        // ~50ms) do LLM (~3min). Útil pra debug e pra operador entender
        // por que algumas revisões abrem na hora e outras demoram.
        const origemBadge = document.getElementById('emailOrigemBadge');
        if (origemBadge) {
            const modelo = (p.llm_modelo || '').toLowerCase();
            if (modelo.startsWith('regex_')) {
                origemBadge.textContent = '⚡ Regex';
                origemBadge.className = 'email-origem-badge email-origem-regex';
                origemBadge.title = `Extraído via parser regex (${p.llm_modelo})`;
                origemBadge.classList.remove('hidden');
            } else if (modelo) {
                origemBadge.textContent = '🧠 LLM';
                origemBadge.className = 'email-origem-badge email-origem-llm';
                origemBadge.title = `Extraído via LLM (${p.llm_modelo})`;
                origemBadge.classList.remove('hidden');
            } else {
                origemBadge.classList.add('hidden');
            }
        }

        // PDF original (IMAP) ou preview de texto (paste manual / WhatsApp).
        // Pedidos sem pdf_path são da origem TEXTO_LIVRE/WHATSAPP_API e não
        // têm arquivo — mostramos o PDF_TEXTO num <pre> em vez do iframe.
        const textoPreviewEl = document.getElementById('emailTextoPreview');
        const textoPreviewBody = document.getElementById('emailTextoPreviewBody');
        const textoOrigemEl = document.getElementById('emailTextoOrigem');
        const temPdf = !!p.pdf_path;
        if (temPdf) {
            pdfFrame.src = `/sankhya/venda/api/email/${p.id}/pdf/`;
            pdfFrame.classList.remove('hidden');
            if (textoPreviewEl) textoPreviewEl.classList.add('hidden');
        } else {
            pdfFrame.removeAttribute('src');
            pdfFrame.classList.add('hidden');
            if (textoPreviewEl) textoPreviewEl.classList.remove('hidden');
            if (textoPreviewBody) textoPreviewBody.textContent = p.pdf_texto || '(texto vazio)';
            if (textoOrigemEl) textoOrigemEl.textContent = p.origem ? `· ${p.origem}` : '';
        }

        // Cabeçalho — sugestões iniciais.
        // Pré-popula os inputs visíveis dos typeaheads no formato "cod — NOME"
        // (mesmo padrão do dropdown) usando o NOMEPARC/NOMEFANTASIA/DESCRTIPVENDA
        // que vêm do JOIN no obter_pedido_email_completo. Isso evita o operador
        // ver só "456" e não saber qual parceiro é.
        const fmtCodNome = (cod, nome) => (cod && nome) ? `${cod} — ${nome}` : (cod ? `${cod}` : '');
        codparcEl.value = p.codparc_sugerido || '';
        parcSearchEl.value = fmtCodNome(p.codparc_sugerido, p.codparc_sugerido_nome);

        // Empresa: usa o sugerido pelo matching; se não houver, cai no default 10.
        // Quando aplicamos o default, fazemos um lookup leve no typeahead pra
        // mostrar "10 — NOME FANTASIA" em vez de só "10" (operador confere
        // sem precisar clicar).
        const codempUsado = p.codemp_sugerido || 10;
        codempEl.value = codempUsado;
        empSearchEl.value = fmtCodNome(codempUsado, p.codemp_sugerido_nome);
        if (!p.codemp_sugerido_nome) {
            fetch(`/sankhya/empresa/search/?q=${codempUsado}&limit=1`, { credentials: 'same-origin' })
                .then(r => r.json())
                .then(data => {
                    const items = data.results || data.items || data || [];
                    const m = items[0];
                    if (m && empSearchEl.value === String(codempUsado)) {
                        empSearchEl.value = fmtCodNome(codempUsado, m.descr || m.nomefantasia || '');
                    }
                })
                .catch(() => {});
        }

        codtipvendaEl.value = p.codtipvenda_sugerido || '';
        tipvendaSearchEl.value = fmtCodNome(p.codtipvenda_sugerido, p.codtipvenda_sugerido_descr);

        // Hint canônico — mostra o NOMEPARC nosso ao lado do CODPARC sugerido,
        // pra operador conferir visualmente se o matching acertou o cliente
        const codparcNomeEl = document.getElementById('emailCodparcNome');
        if (codparcNomeEl) {
            const nomeCanonico = p.codparc_sugerido_nome || '';
            codparcNomeEl.textContent = nomeCanonico ? `Nosso cliente: ${nomeCanonico}` : '';
        }
        // Segundo hint: o que o LLM extraiu literalmente do PDF.
        // Útil quando o matching casou um CODPARC genérico mas o PDF
        // tinha info mais específica (ex: "SENDAS LJ176 PALMAS").
        const clienteExtraidoEl = document.getElementById('emailClienteExtraido');
        if (clienteExtraidoEl) {
            const lit = p.cliente_nome_extraido || '';
            clienteExtraidoEl.textContent = lit ? `📩 PDF: ${lit}` : '';
        }

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
        const footEl = document.getElementById('emailItensFoot');
        if (!itens.length) {
            itensBodyEl.innerHTML = '<tr><td colspan="7" class="ia-placeholder">Sem itens.</td></tr>';
            if (footEl) footEl.classList.add('hidden');
            return;
        }
        itensBodyEl.innerHTML = '';
        for (const it of itens) {
            const tr = document.createElement('tr');
            tr.dataset.itemId = it.id;
            const semProd = !it.codprod_final && !it.codprod_sugerido;
            if (semProd) tr.classList.add('alerta');

            // Nome canônico do nosso produto (vem do backend via JOIN com TGFPRO).
            // Prefere o final (escolhido pelo operador) sobre o sugerido.
            const nomeNosso = it.codprod_final_descr || it.codprod_sugerido_descr || '';
            const nomeNossoEsc = nomeNosso.replace(/[<>]/g, '');

            // Typeahead de produto por linha: IDs únicos baseados no item.id
            // pra reaproveitar attachTA (mesmo padrão da Venda).
            const visId = `email-it-prod-vis-${it.id}`;
            const hidId = `email-it-prod-hid-${it.id}`;
            const ddId  = `email-it-prod-dd-${it.id}`;
            const codprodAtual = it.codprod_final || it.codprod_sugerido || '';
            const visText = (codprodAtual && nomeNosso) ? `${codprodAtual} — ${nomeNossoEsc}` : '';

            // Badge de origem do match: alias (alta confiança, decisão histórica)
            // vs fuzzy (similaridade — pode estar errado). Quando o operador
            // já confirmou (codprod_final preenchido), mostramos só ✓ discreto.
            // Como o aprendizado por alias retorna confiança 1.00 e o fuzzy
            // raramente atinge 100, usamos isso como proxy.
            const conf = parseFloat(it.codprod_confianca) || 0;
            // Pill colorida no canto inferior direito da célula CODPROD,
            // sinalizando origem/confiança do match. Verde = decisão humana,
            // amarelo = fuzzy alta (confira), vermelho = fuzzy fraca.
            let badgeHtml = '';
            if (it.codprod_final) {
                badgeHtml = '<span class="email-match-badge confirmado" title="Confirmado pelo operador">✓</span>';
            } else if (it.codprod_sugerido) {
                if (conf >= 1.0) {
                    badgeHtml = '<span class="email-match-badge alias" title="Alias histórico — confirmado em pedido anterior. Se estiver errado, edite e confirme: o sistema sobrescreve.">alias</span>';
                } else if (conf >= 0.75) {
                    badgeHtml = `<span class="email-match-badge fuzzy-alta" title="Match por similaridade (${Math.round(conf*100)}%) — confira antes de confirmar.">~ ${Math.round(conf*100)}%</span>`;
                } else if (conf > 0) {
                    badgeHtml = `<span class="email-match-badge fuzzy-baixa" title="Match fraco (${Math.round(conf*100)}%) — atenção, alta chance de erro.">~ ${Math.round(conf*100)}%</span>`;
                }
            }

            // Texto do PDF combinado: "1042608 - MILHO VERDE C/5UN" (cod_cliente + descrição
            // em formato consistente com o typeahead de CODPROD). Quando o PDF não trouxe
            // cod_cliente, mostra só a descrição.
            const codCliente = (it.cod_cliente || '').toString().replace(/[<>]/g, '');
            const descricao  = (it.descricao_pdf || '').replace(/[<>]/g, '');
            const textoPdf   = codCliente ? `${codCliente} - ${descricao}` : descricao;

            tr.innerHTML = `
                <td title="Texto literal extraído do PDF">${textoPdf}</td>
                <td>
                    <span class="email-prod-wrap">
                        <input type="hidden" id="${hidId}" class="email-it-codprod" value="${codprodAtual}">
                        <input type="text" id="${visId}" class="email-it-codprod-vis" value="${visText}" placeholder="Cód. ou nome">
                        <div id="${ddId}" class="dropdown-abs"></div>
                        ${badgeHtml}
                    </span>
                </td>
                <td class="email-it-qtdvol">
                    <span class="qtdvol-wrap">
                        <input type="number" step="0.001" class="email-it-qtd" value="${it.qtd || ''}">
                        <input type="text" class="email-it-vol" value="${it.codvol || ''}" maxlength="10" title="Unidade de medida">
                    </span>
                </td>
                <td class="text-right"><input type="number" step="0.01" class="email-it-preco" value="${it.preco_unit || ''}"></td>
                <td class="text-right email-it-total" title="Qtd × Preço unitário">—</td>
                <td class="email-it-acoes">
                    <button type="button" class="email-restore-btn" title="Restaurar este item ao valor original do LLM" data-item-id="${it.id}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M3 12a9 9 0 1 0 3-6.7"></path>
                            <polyline points="3 4 3 10 9 10"></polyline>
                        </svg>
                    </button>
                    <button type="button" class="email-trash-btn" title="Remover item" data-item-id="${it.id}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                        </svg>
                    </button>
                </td>
            `;
            itensBodyEl.appendChild(tr);

            // Liga typeahead nesta linha. onChange dispara o save quando o
            // operador escolhe um produto novo no dropdown.
            // extraQuery 'grupo_inicia_com=1': mesma regra da Venda —
            // só produtos vendáveis do hortifrúti (CODGRUPOPROD começa
            // com 1), sem insumos/mudas/embalagens.
            attachTA(visId, hidId, ddId, '/sankhya/produtos/search/', {
                limit: 15,
                extraQuery: 'grupo_inicia_com=1',
                onChange: () => {
                    onCodprodChange(tr);
                    atualizarTotais();
                },
            });
        }

        // Liga handlers de edição inline (qtd/preco/vol — mas NÃO codprod, esse vai pelo typeahead)
        itensBodyEl.querySelectorAll('.email-it-qtd, .email-it-preco, .email-it-vol').forEach(inp => {
            inp.addEventListener('change', e => {
                onItemChange(e);
                atualizarTotais();   // recalcula ao editar qtd ou preço
            });
        });
        itensBodyEl.querySelectorAll('.email-trash-btn').forEach(btn => {
            btn.addEventListener('click', onItemRemove);
        });
        itensBodyEl.querySelectorAll('.email-restore-btn').forEach(btn => {
            btn.addEventListener('click', onItemRestaurar);
        });

        // Mostra rodapé com totais
        atualizarTotais();
        if (footEl) footEl.classList.remove('hidden');
    }

    /**
     * Calcula e exibe somatórios da tabela de itens:
     *   total_qtd   = Σ qtd
     *   total_valor = Σ (qtd × preco_unit)
     * Reage à edição inline — chamado em onChange dos inputs.
     */
    function atualizarTotais() {
        const trs = itensBodyEl.querySelectorAll('tr[data-item-id]');
        let totalQtd = 0;
        let totalValor = 0;
        let totalItens = 0;
        // Qtd total sem casa decimal (operador pediu): a maioria dos lotes vai
        // em KG inteiro; ver "4.230" é mais limpo que "4.230,00".
        // Valor mantém 2 casas (cents).
        const fmtQtd   = n => n.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        const fmtValor = n => n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        for (const tr of trs) {
            const qtd   = parseFloat(tr.querySelector('.email-it-qtd')?.value) || 0;
            const preco = parseFloat(tr.querySelector('.email-it-preco')?.value) || 0;
            const subTotal = qtd * preco;
            totalQtd   += qtd;
            totalValor += subTotal;
            totalItens += 1;
            // Atualiza a célula "Total" da linha — qtd × preço, formato BR.
            // Sem qtd ou sem preço, mostra "—" pra deixar claro que ainda
            // falta dado.
            const cellTotal = tr.querySelector('.email-it-total');
            if (cellTotal) {
                cellTotal.textContent = (qtd > 0 && preco > 0)
                    ? 'R$ ' + fmtValor(subTotal)
                    : '—';
            }
        }
        const elQtd   = document.getElementById('emailItensTotalQtd');
        const elValor = document.getElementById('emailItensTotalValor');
        if (elQtd)   elQtd.textContent   = fmtQtd(totalQtd);
        if (elValor) elValor.textContent = 'R$ ' + fmtValor(totalValor);

        // Conferência cruzada: compara totais calculados com os declarados
        // no PDF (extraídos do texto via regex). Se o PDF tinha "Total geral"
        // / "Total de itens", mostra linha-referência com chip ✓ ou ⚠.
        // Vale tanto pra registros parseados via regex quanto via LLM.
        const conferenciaRow = document.getElementById('emailConferenciaRow');
        if (!conferenciaRow) return;
        const totaisPdf = (pedidoAtual && pedidoAtual.totais_pdf) || null;
        if (!totaisPdf || (totaisPdf.total_geral == null && totaisPdf.total_itens == null)) {
            conferenciaRow.classList.add('hidden');
            return;
        }

        conferenciaRow.classList.remove('hidden');
        const elConfQtd   = document.getElementById('emailConferenciaQtd');
        const elConfValor = document.getElementById('emailConferenciaValor');
        const elChip      = document.getElementById('emailConferenciaChip');

        // Total de itens declarado: comparamos o COUNT, não o valor da qtd.
        // Operador edita qtd à vontade; o que valida o parser/LLM é o
        // "achei N itens, PDF dizia N itens".
        if (totaisPdf.total_itens != null) {
            elConfQtd.textContent = `${totaisPdf.total_itens} itens`;
        } else {
            elConfQtd.textContent = '—';
        }
        if (totaisPdf.total_geral != null) {
            elConfValor.textContent = 'R$ ' + fmtValor(totaisPdf.total_geral);
        } else {
            elConfValor.textContent = '—';
        }

        // Chip de status: ✓ se BOTH (qtd-itens e total-valor) batem; senão ⚠.
        // Tolerância de R$ 0,10 no valor (arredondamento na 4ª casa do
        // preço unit gera diferenças pequenas em pedidos grandes).
        let okItens = true, okValor = true, msg = [];
        if (totaisPdf.total_itens != null) {
            okItens = totalItens === totaisPdf.total_itens;
            if (!okItens) msg.push(`itens: ${totalItens} ≠ ${totaisPdf.total_itens}`);
        }
        if (totaisPdf.total_geral != null) {
            const diff = Math.abs(totalValor - totaisPdf.total_geral);
            okValor = diff <= 0.10;
            if (!okValor) msg.push(`valor: diff R$ ${fmtValor(diff)}`);
        }
        if (okItens && okValor) {
            elChip.textContent = '✓ Bate com PDF';
            elChip.className = 'email-conferencia-chip email-conferencia-ok';
            elChip.title = 'Totais calculados batem com os declarados no PDF';
        } else {
            elChip.textContent = '⚠ Diverge';
            elChip.className = 'email-conferencia-chip email-conferencia-diverge';
            elChip.title = msg.join(' · ');
        }
    }

    /**
     * Wrapper chamado pelo typeahead de produto (attachTA onChange).
     * Reusa onItemChange criando um evento sintético — o mesmo fluxo de save
     * que qtd/preco/vol passam por edição direta.
     */
    function onCodprodChange(tr) {
        // O typeahead já popula o input visível com "39 — PIMENTAO VERDE EXTRA",
        // então não precisamos de coluna espelho. Aqui só limpamos o destaque
        // de alerta (linha sem CODPROD ficava amarela) e disparamos o save.
        const hidEl = tr.querySelector('.email-it-codprod');
        if (hidEl && hidEl.value) tr.classList.remove('alerta');
        onItemChange({ target: hidEl });
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

    /**
     * Restaura UM item ao estado original do LLM_RESPOSTA + matching atual.
     * Não chama LLM. Faz UPDATE — preserva o ID. Útil pra desfazer edição
     * isolada sem afetar os outros 46 itens.
     */
    async function onItemRestaurar(e) {
        const btn = e.currentTarget;
        const itemId = parseInt(btn.dataset.itemId, 10);
        const ok = await phConfirm({
            titulo: 'Restaurar item',
            mensagem: 'Restaurar este item ao valor original extraído do PDF? Suas edições neste item serão perdidas.',
            tipo: 'aviso',
        });
        if (!ok) return;
        try {
            const r = await phPostJSON(`/sankhya/venda/api/email/item/${itemId}/restaurar/`, {});
            if (!r.ok || (r.body && !r.body.ok)) {
                phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                return;
            }
            phToast('Item restaurado.', 'success');
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

    /**
     * "Restaurar tudo": recria TODOS os itens a partir do JSON crú do LLM
     * já salvo no banco + matching atual. Não chama LLM (instantâneo).
     * Diferente do Reparser, que apaga e espera o worker rodar de novo.
     */
    if (restaurarTodosBtn) {
        restaurarTodosBtn.addEventListener('click', async () => {
            if (!pedidoSelecionadoId) return;
            const ok = await phConfirm({
                titulo: 'Restaurar tudo',
                mensagem: 'Restaurar TODOS os itens ao estado original extraído do PDF? Todas as edições serão perdidas (instantâneo, não chama LLM de novo).',
                tipo: 'aviso',
            });
            if (!ok) return;
            try {
                const r = await phPostJSON(`/sankhya/venda/api/email/${pedidoSelecionadoId}/restaurar/`, {});
                if (!r.ok || (r.body && !r.body.ok)) {
                    phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                    return;
                }
                phToast(r.body.mensagem || 'Itens restaurados.', 'success');
                await selecionar(pedidoSelecionadoId);
            } catch (e) { phToast('Erro: ' + e.message, 'error'); }
        });
    }

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
    // Modal: adicionar item manual
    // Útil quando o LLM esqueceu uma linha do PDF ou o operador
    // precisa incluir um item que não veio.
    // ============================================================
    const addItemModal   = document.getElementById('emailAddItemModal');
    const addItemBtn     = document.getElementById('emailAddItemBtn');
    const novoCodprodEl  = document.getElementById('emailNovoCodprod');
    const novoCodprodVis = document.getElementById('emailNovoCodprodVis');
    const novoQtdEl      = document.getElementById('emailNovoQtd');
    const novoVolEl      = document.getElementById('emailNovoVol');
    const novoPrecoEl    = document.getElementById('emailNovoPreco');
    const novoCancelBtn  = document.getElementById('emailNovoCancelBtn');
    const novoSalvarBtn  = document.getElementById('emailNovoSalvarBtn');

    // Liga o typeahead de produto no campo do modal (mesmo endpoint + filtro da Venda)
    attachTA('emailNovoCodprodVis', 'emailNovoCodprod', 'emailNovoCodprodDd',
             '/sankhya/produtos/search/',
             { limit: 15, extraQuery: 'grupo_inicia_com=1' });

    function abrirAddItemModal() {
        if (!pedidoSelecionadoId) return;
        novoCodprodEl.value  = '';
        novoCodprodVis.value = '';
        novoQtdEl.value      = '';
        novoVolEl.value      = 'KG';   // padrão de agro: maioria é em quilo
        novoPrecoEl.value    = '';
        addItemModal.classList.remove('hidden');
        setTimeout(() => novoCodprodVis.focus(), 50);
    }

    function fecharAddItemModal() {
        addItemModal.classList.add('hidden');
    }

    if (addItemBtn) addItemBtn.addEventListener('click', abrirAddItemModal);
    if (novoCancelBtn) novoCancelBtn.addEventListener('click', fecharAddItemModal);
    // Fecha ao clicar no overlay (fora do card)
    if (addItemModal) {
        addItemModal.addEventListener('click', e => {
            if (e.target === addItemModal) fecharAddItemModal();
        });
    }
    // Esc fecha; Enter no preço dispara salvar
    document.addEventListener('keydown', e => {
        if (addItemModal && !addItemModal.classList.contains('hidden')) {
            if (e.key === 'Escape') fecharAddItemModal();
            if (e.key === 'Enter' && document.activeElement === novoPrecoEl) {
                novoSalvarBtn.click();
            }
        }
    });

    if (novoSalvarBtn) {
        novoSalvarBtn.addEventListener('click', async () => {
            if (!pedidoSelecionadoId) { fecharAddItemModal(); return; }
            const codprod = parseInt(novoCodprodEl.value, 10) || null;
            const qtd     = parseFloat(novoQtdEl.value) || 0;
            const codvol  = (novoVolEl.value || '').trim().toUpperCase();
            const preco   = parseFloat(novoPrecoEl.value) || null;

            if (!codprod) { phToast('Selecione um produto.', 'warning'); novoCodprodVis.focus(); return; }
            if (qtd <= 0) { phToast('Informe a quantidade.', 'warning'); novoQtdEl.focus(); return; }

            try {
                const r = await phPostJSON(
                    `/sankhya/venda/api/email/${pedidoSelecionadoId}/item/criar/`,
                    { codprod, qtd, codvol, preco_unit: preco },
                );
                if (!r.ok || (r.body && !r.body.ok)) {
                    phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                    return;
                }
                phToast('Item adicionado.', 'success');
                fecharAddItemModal();
                await selecionar(pedidoSelecionadoId);
            } catch (e) { phToast('Erro: ' + e.message, 'error'); }
        });
    }

    // ============================================================
    // Modal: importar pedido por texto livre (WhatsApp / paste manual)
    // Cria registro com PDF_PATH=NULL e STATUS=AGUARDANDO_PARSER. O worker
    // vai detectar e rodar o LLM (layout=GENERICO) na próxima rodada.
    // ============================================================
    const importarTextoBtn   = document.getElementById('emailImportarTextoBtn');
    const importarModal      = document.getElementById('emailImportarTextoModal');
    const importarTextoEl    = document.getElementById('emailImportarTexto');
    const importarOrigemEl   = document.getElementById('emailImportarOrigem');
    const importarCountEl    = document.getElementById('emailImportarCount');
    const importarCancelBtn  = document.getElementById('emailImportarCancelBtn');
    const importarSalvarBtn  = document.getElementById('emailImportarSalvarBtn');

    function abrirImportarTextoModal() {
        if (importarTextoEl)  importarTextoEl.value = '';
        if (importarOrigemEl) importarOrigemEl.value = 'TEXTO_LIVRE';
        if (importarCountEl)  importarCountEl.textContent = '(0 caracteres)';
        if (importarModal)    importarModal.classList.remove('hidden');
        setTimeout(() => importarTextoEl && importarTextoEl.focus(), 50);
    }

    function fecharImportarTextoModal() {
        if (importarModal) importarModal.classList.add('hidden');
    }

    if (importarTextoBtn) importarTextoBtn.addEventListener('click', abrirImportarTextoModal);
    if (importarCancelBtn) importarCancelBtn.addEventListener('click', fecharImportarTextoModal);
    if (importarModal) {
        importarModal.addEventListener('click', e => {
            if (e.target === importarModal) fecharImportarTextoModal();
        });
    }
    if (importarTextoEl && importarCountEl) {
        importarTextoEl.addEventListener('input', () => {
            const n = importarTextoEl.value.length;
            importarCountEl.textContent = `(${n} caracteres${n < 30 ? ' — mín. 30' : ''})`;
        });
    }
    document.addEventListener('keydown', e => {
        if (importarModal && !importarModal.classList.contains('hidden') && e.key === 'Escape') {
            fecharImportarTextoModal();
        }
    });

    if (importarSalvarBtn) {
        importarSalvarBtn.addEventListener('click', async () => {
            const texto  = (importarTextoEl.value || '').trim();
            const origem = (importarOrigemEl.value || 'TEXTO_LIVRE');
            if (texto.length < 30) {
                phToast('Texto muito curto (mín. 30 caracteres).', 'warning');
                importarTextoEl.focus();
                return;
            }
            try {
                const r = await phPostJSON('/sankhya/venda/api/email/importar-texto/',
                                            { texto, origem });
                if (!r.ok || (r.body && !r.body.ok)) {
                    phToast('Erro: ' + ((r.body && r.body.error) || 'falha'), 'error');
                    return;
                }
                phToast(r.body.mensagem || 'Texto importado.', 'success');
                fecharImportarTextoModal();
                // Operador provavelmente quer ver o registro novo
                statusSelect.value = 'AGUARDANDO_PARSER';
                statusAtual = 'AGUARDANDO_PARSER';
                await carregarFila();
            } catch (e) { phToast('Erro: ' + e.message, 'error'); }
        });
    }

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
