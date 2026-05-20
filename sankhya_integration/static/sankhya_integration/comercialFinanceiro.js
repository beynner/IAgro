window.ComercialFinanceiro = (function () {
    let STATE = { bruto: 0, liquido: 0, dadosNota: null, itens: [] };

    // ──────────────────────────────────────────────────────────────────────────
    // Render puro (sem fetch) — reusado pelo toggle "Descontar avaria / Pagar total"
    // (Mai/2026 — 2026-05-20). Usa STATE.itensCalculados pre-populado pelo `abrir`.
    // ──────────────────────────────────────────────────────────────────────────
    function _renderListasFaturamento() {
        const listClass  = document.getElementById('listaFechamentoClass');
        const listDireto = document.getElementById('listaFechamentoDireto');
        if (!listClass || !listDireto) return;

        const nunota13Ativo = STATE.nunota13Ativo || 0;
        const nufinAtivo    = STATE.nufinAtivo || 0;
        const absorveuMap   = STATE.absorveuAvariaPorLote || {};

        let totalBruto = 0;
        let totalDescontoAvaria = 0;  // soma dos descontos visuais quando toggle = Descontar
        let temPendente = false;
        let temPendentePreco = false;
        let temPendenteClassificacao = false;
        let htmlClass = '';
        let htmlDireto = '';

        for (const data of (STATE.itensCalculados || [])) {
            const { item, isClassificavel, fabricante, lote, vlrTotal } = data;
            let { kgFisicoTotal } = data;
            totalBruto += vlrTotal;

            // Avaria desse lote
            const avariaLote   = (STATE.avariasPorLote || {})[String(lote)];
            const qtdAvariaKg  = avariaLote ? Number(avariaLote.qtd_avaria || 0) : 0;
            const temAvaria    = qtdAvariaKg > 0;
            // Mai/2026 (2026-05-20) — Default = Descontar quando há avaria na TOP 11.
            // Premissa: se o operador da Doca registrou avaria, presumivelmente
            // Comercial vai cobrar do fornecedor. Absorver é decisão explícita.
            // True só quando operador clicou pra Absorver explicitamente.
            const absorveu     = absorveuMap[String(lote)] === true;
            const loteEscapado = String(lote).replace(/'/g, "\\'");

            const avariaIconHtml = temAvaria
                ? `<button type="button" class="cf-avaria-badge"
                          title="Avaria do fornecedor: ${window.ComercialUtils.formatQty(qtdAvariaKg)} kg — clique pra detalhes"
                          onclick="window.ComercialFinanceiro.abrirAvariaDetalhe('${loteEscapado}')">
                     <i class="ph ph-warning" aria-hidden="true"></i>
                   </button>`
                : '';

            // Toggle Descontar / Absorver (apenas quando há avaria).
            // Mai/2026 (2026-05-20): segmented control com as 2 opções visíveis.
            // Default = Absorver. Click em uma opção define explicitamente o estado.
            // TGFCAB TOP 30 é criada/removida automaticamente ao FATURAR via B8.
            // Trava visual: se vale já tem TGFFIN (nufinAtivo > 0), opções viram disabled.
            const valeFaturado = (STATE.nufinAtivo || 0) > 0;
            const tooltipBase = absorveu
                ? 'Agromil absorve ' + window.ComercialUtils.formatQty(qtdAvariaKg) + ' kg (gera TOP 30 ao faturar)'
                : 'Repassando ' + window.ComercialUtils.formatQty(qtdAvariaKg) + ' kg ao fornecedor (sem TOP 30)';
            const tooltipFull = valeFaturado
                ? `${tooltipBase} — vale já faturado, desfature pra alterar`
                : tooltipBase;
            const onclickAbsorver = valeFaturado
                ? ''
                : `onclick="window.ComercialFinanceiro.setAbsorverAvaria('${loteEscapado}', true)"`;
            const onclickDescontar = valeFaturado
                ? ''
                : `onclick="window.ComercialFinanceiro.setAbsorverAvaria('${loteEscapado}', false)"`;
            const toggleHtml = temAvaria
                ? `<div class="cf-avaria-toggle ${valeFaturado ? 'is-readonly' : ''}"
                        title="${tooltipFull}">
                     <button type="button" class="cf-avaria-toggle__opt ${absorveu ? 'is-active' : ''}"
                             ${onclickAbsorver}
                             ${valeFaturado ? 'disabled' : ''}>
                       Absorver
                     </button>
                     <button type="button" class="cf-avaria-toggle__opt ${!absorveu ? 'is-active' : ''}"
                             ${onclickDescontar}
                             ${valeFaturado ? 'disabled' : ''}>
                       Descontar
                     </button>
                   </div>`
                : '';

            if (isClassificavel) {
                // Travas existentes (preço + classificação)
                if (vlrTotal <= 0) { temPendente = true; temPendentePreco = true; }
                if (item.pendente !== 'N') { temPendente = true; temPendenteClassificacao = true; }

                const qtdConf = window.ComercialUtils.toNumber(item.qtdconferida || item.qtdneg) || 0;
                if (kgFisicoTotal === 0) {
                    const pesoIn = window.ComercialUtils.toNumber(item.peso || 1);
                    kgFisicoTotal = qtdConf * pesoIn;
                }

                // Mai/2026 (2026-05-20) — visual volta a mostrar qtd BRUTA. O desconto
                // de avaria não é mais feito visualmente: quando o operador marca
                // "Absorver" no toggle, backend (Cat B B6 pendente) cria TOP 30 que
                // descontará do estoque via perna D da view. Vale TOP 13 fica intocado.
                const custoCx = qtdConf > 0 ? (vlrTotal / qtdConf) : 0;
                const custoKg = kgFisicoTotal > 0 ? (vlrTotal / kgFisicoTotal) : 0;

                htmlClass += `
                    <tr${temAvaria ? ' class="cf-row-tem-avaria"' : ''}>
                        <td class="val-main">${fabricante}${avariaIconHtml}</td>
                        <td class="txt-right">
                            <div class="val-main">${window.ComercialUtils.formatQty(qtdConf, 2) || '0.00'} cx</div>
                            <div class="val-sub">${window.ComercialUtils.formatQty(kgFisicoTotal) || '0.00'} kg</div>
                            ${toggleHtml}
                        </td>
                        <td class="txt-right">
                            <div class="val-main">R$ ${custoCx.toFixed(2) || '0.00'}/cx</div>
                            <div class="val-sub">R$ ${custoKg.toFixed(2) || '0.00'}/kg</div>
                        </td>
                        <td class="txt-right">
                            <div class="val-main">R$ ${vlrTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</div>
                        </td>
                        <td class="txt-center"><span class="status-dot ${vlrTotal > 0 ? 'verde' : 'vermelho'}"></span></td>
                    </tr>`;
            } else {
                // Não-classificável — Mai/2026 (2026-05-20).
                // 📌 Absorver (default): mostra qtd BRUTA + vlrTotal cheio. Ao faturar, backend
                //   cria TGFCAB TOP 30 que desconta estoque via perna D.
                // 📉 Descontar: mostra qtd LÍQUIDA + vlrTotal recalculado (= qtdLiq × vlrUnit).
                //   Financeiro também é descontado (STATE.bruto reflete). Sem TOP 30.
                const qtd       = window.ComercialUtils.toNumber(item.qtdconferida) || 0;
                const pesoIn    = window.ComercialUtils.toNumber(item.peso) || 0;
                const unidade   = (item.codvol || 'un').toLowerCase();
                const vlrUnit   = qtd > 0 ? (vlrTotal / qtd) : 0;
                const isFaturado = nufinAtivo > 0;

                // Conversão avaria kg → unidade do produto (mç, cx, kg)
                const qtdAvariaUnidade  = pesoIn > 0 ? (qtdAvariaKg / pesoIn) : qtdAvariaKg;
                const qtdLiquidaUnidade = Math.max(0, qtd - qtdAvariaUnidade);

                // Quando Descontar (absorveu=false) e há avaria → exibe líquido
                const exibirLiquido     = temAvaria && !absorveu;
                const qtdExibida        = exibirLiquido ? qtdLiquidaUnidade : qtd;
                const vlrTotalExibido   = exibirLiquido ? (qtdLiquidaUnidade * vlrUnit) : vlrTotal;

                if (exibirLiquido) {
                    totalDescontoAvaria += (vlrTotal - vlrTotalExibido);
                }

                if (vlrUnit <= 0 || vlrTotalExibido <= 0) {
                    temPendente = true;
                    temPendentePreco = true;
                }

                const campoEditavel = isFaturado
                    ? `<span>${vlrUnit.toFixed(2)}</span>`
                    : `<span class="editable" style="cursor:pointer;" onclick="window.ComercialFinanceiro.editarPreco(${item.nunota}, ${item.codprod}, ${nunota13Ativo}, this)">${vlrUnit.toFixed(2)}</span>`;

                let htmlQtde = '';
                let htmlVlr  = '';
                if (['cx', 'sc'].includes(unidade) && pesoIn > 0) {
                    const totalKgExibido = qtdExibida * pesoIn;
                    const custoKgExibido = totalKgExibido > 0 ? (vlrTotalExibido / totalKgExibido) : 0;
                    htmlQtde = `
                        <div class="val-main">${window.ComercialUtils.formatQty(qtdExibida, 2) || '0.00'} ${unidade}</div>
                        <div class="val-sub">${window.ComercialUtils.formatQty(totalKgExibido) || '0.00'} kg</div>
                        ${toggleHtml}`;
                    htmlVlr = `
                        <div class="val-main">R$ ${campoEditavel}/${unidade}</div>
                        <div class="val-sub">R$ ${custoKgExibido.toFixed(2) || '0.00'}/kg</div>`;
                } else {
                    htmlQtde = `<div class="val-main">${window.ComercialUtils.formatQty(qtdExibida) || '0'} ${unidade}</div>
                                ${toggleHtml}`;
                    htmlVlr = `<div class="val-main">R$ ${campoEditavel}/${unidade}</div>`;
                }

                const rowClass = exibirLiquido
                    ? ' class="cf-row-com-avaria"'
                    : (temAvaria ? ' class="cf-row-tem-avaria"' : '');

                htmlDireto += `
                    <tr${rowClass}>
                        <td class="val-main">${fabricante}${avariaIconHtml}</td>
                        <td class="txt-right">${htmlQtde}</td>
                        <td class="txt-right">${htmlVlr}</td>
                        <td class="txt-right">
                            <div class="val-main">R$ ${vlrTotalExibido.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</div>
                        </td>
                        <td class="txt-center"><span class="status-dot ${vlrTotalExibido > 0 && vlrUnit > 0 ? 'verde' : 'vermelho'}"></span></td>
                    </tr>`;
            }
        }

        listClass.innerHTML  = htmlClass  || '<tr><td colspan="5" class="txt-center val-sub" style="padding: 15px;">Nenhum produto classificável</td></tr>';
        listDireto.innerHTML = htmlDireto || '<tr><td colspan="5" class="txt-center val-sub" style="padding: 15px;">Nenhum produto direto</td></tr>';

        // Mai/2026 (2026-05-20) — Bruto reflete decisão por lote:
        //   📌 Absorver: vlrTotal cheio (TOP 30 desconta estoque no faturar)
        //   📉 Descontar: vlrTotal − (avaria × vlrUnit) — financeiro descontado, sem TOP 30
        STATE.bruto          = totalBruto;
        STATE.descontoAvaria = totalDescontoAvaria;
        STATE.brutoLiquido   = totalBruto - totalDescontoAvaria;
        const vlrBrutoEl = document.getElementById('vlrBrutoFechamento');
        if (totalDescontoAvaria > 0) {
            vlrBrutoEl.innerHTML = `
                <s class="cf-bruto-original">R$ ${totalBruto.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</s>
                <span class="cf-bruto-liquido">R$ ${STATE.brutoLiquido.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>`;
        } else {
            vlrBrutoEl.textContent = `R$ ${totalBruto.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
        }

        // Botão FATURAR — trava apenas por preço/classificação (avaria é decisão do operador via toggle)
        const carimbo = document.getElementById('carimboFaturado');
        if (carimbo) carimbo.style.display = nufinAtivo > 0 ? 'block' : 'none';

        const btnEfetivar = document.getElementById('btnEfetivarFaturamento');
        const isPago = window.ComercialUtils.toNumber(STATE.dadosNota?.qtd_baixados) > 0;

        if (nufinAtivo > 0) {
            btnEfetivar.textContent = "DESFATURAR";
            // Sem motivos exibidos no modo desfaturar
            const ulMotivos = document.getElementById('cfFaturarMotivos');
            if (ulMotivos) { ulMotivos.innerHTML = ''; ulMotivos.hidden = true; }
            if (isPago) {
                btnEfetivar.style.backgroundColor = "#9ca3af";
                btnEfetivar.style.color = "#ffffff";
                btnEfetivar.style.cursor = "not-allowed";
                btnEfetivar.disabled = true;
                btnEfetivar.title = "Não é possível desfaturar: Título já baixado no financeiro.";
                btnEfetivar.onclick = null;
            } else {
                btnEfetivar.style.backgroundColor = "#ef4444";
                btnEfetivar.style.color = "#ffffff";
                btnEfetivar.style.cursor = "pointer";
                btnEfetivar.disabled = false;
                btnEfetivar.title = "";
                btnEfetivar.onclick = () => window.ComercialFinanceiro.desfaturar(nunota13Ativo);
            }
        } else {
            // Mai/2026 (2026-05-20) — Motivos da trava também visíveis abaixo
            // do botão (não só no tooltip). Detecta "vale não salvo" (sem nunota_13)
            // como condição adicional.
            const temPendenteSemVale = !(nunota13Ativo > 0);
            const temPendenteTotal = temPendente || temPendenteSemVale;

            btnEfetivar.textContent = "FATURAR";
            btnEfetivar.style.backgroundColor = "";
            btnEfetivar.style.color = "";
            btnEfetivar.style.cursor = temPendenteTotal ? "not-allowed" : "pointer";
            btnEfetivar.disabled = temPendenteTotal;

            const motivos = [];
            if (temPendenteSemVale)        motivos.push('Vale ainda não foi salvo. Lance o preço de pelo menos um produto pra criar o vale.');
            if (temPendentePreco)          motivos.push('Há produto(s) sem preço definido.');
            if (temPendenteClassificacao)  motivos.push('Há lote(s) classificável(eis) com a classificação ainda não finalizada (finalize a TOP 26 antes).');

            btnEfetivar.title = motivos.join('\n');
            btnEfetivar.onclick = () => window.ComercialFinanceiro.faturar();

            const ulMotivos = document.getElementById('cfFaturarMotivos');
            if (ulMotivos) {
                if (motivos.length > 0) {
                    ulMotivos.innerHTML = motivos.map(
                        m => `<li><i class="ph ph-warning" aria-hidden="true"></i> ${m}</li>`
                    ).join('');
                    ulMotivos.hidden = false;
                } else {
                    ulMotivos.innerHTML = '';
                    ulMotivos.hidden = true;
                }
            }
        }
    }

    const abrir = async (nunota) => {
        const modal = document.getElementById('modalFaturamento');
        if (!modal) return;

        // 1. A BASE FÍSICA: Os produtos vêm da TOP 11 (Memória)
        let itensDaNota = (window.__COM_LIST_ROWS || []).filter(r => r.nunota == nunota);

        if (itensDaNota.length === 0) {
            // 🚀 FIX: Se a lista do fundo filtrou e sumiu com a nota, resgata do "cofre" do próprio Modal!
            if (STATE.itens && STATE.itens.length > 0 && STATE.itens[0].nunota == nunota) {
                itensDaNota = STATE.itens;
            } else {
                return;
            }
        }

        // Reset do toggle Descontar/Absorver ao trocar de pedido (Mai/2026 — 2026-05-20)
        // Default = false (descontar/cobra fornecedor). True = absorver (Agromil paga + TOP 30).
        const nunotaAnterior = STATE.dadosNota?.nunota;
        if (nunotaAnterior !== nunota) {
            STATE.absorveuAvariaPorLote = {};
        }
        STATE.absorveuAvariaPorLote = STATE.absorveuAvariaPorLote || {};

        STATE.itens = itensDaNota;
        STATE.dadosNota = itensDaNota[0];
        document.getElementById('fechamentoParceiro').textContent = STATE.dadosNota.parceiro || '---';

        // Mai/2026 (2026-05-19) — busca avarias do fornecedor pra exibir ⚠ na linha
        // do item cujo lote teve descarte registrado na TOP 11. Não bloqueia render.
        STATE.avariasPorLote = {};
        try {
            const resAv = await fetch(
                `/sankhya/comercial/api/avarias-fornecedor-pedido/?nunota=${encodeURIComponent(nunota)}`
            );
            const dataAv = await resAv.json();
            if (dataAv && dataAv.ok && dataAv.avarias_por_lote) {
                STATE.avariasPorLote = dataAv.avarias_por_lote;
            }
        } catch (e) {
            console.warn('Falha ao buscar avarias do fornecedor', e);
        }

        // Monta o subtítulo inicial com os dados da memória
        const memVale = window.ComercialUtils.toNumber(STATE.dadosNota.nunota_13);
        const memFin = window.ComercialUtils.toNumber(STATE.dadosNota.nufin);
        let subtitulo = `Pedido: ${nunota}`;
        if (memVale > 0) subtitulo += ` | Vale: ${memVale}`;
        if (memFin > 0) subtitulo += ` | Fin: ${memFin}`;
        document.getElementById('fechamentoPedido').textContent = subtitulo;

        // 🚀 FIX: Verifica se é uma atualização (modal já aberto) para evitar a "piscada"
        const isRefresh = modal.style.display === 'flex';
        modal.style.display = 'flex';

        // (Mai/2026) Desabilita o FATURAR imediatamente — só será reabilitado após
        // o loop processar todas as travas (preço + classificação). Evita o "flash"
        // de botão clicável antes da avaliação terminar.
        const btnEfetivarInit = document.getElementById('btnEfetivarFaturamento');
        if (btnEfetivarInit) {
            btnEfetivarInit.disabled = true;
            btnEfetivarInit.style.cursor = 'wait';
            btnEfetivarInit.title = 'Verificando travas...';
        }

        const listClass = document.getElementById('listaFechamentoClass');
        const listDireto = document.getElementById('listaFechamentoDireto');

        // Só mostra a mensagem de "Buscando..." se for a primeira vez abrindo
        if (!isRefresh) {
            listClass.innerHTML = '<tr><td colspan="5" class="txt-center val-sub">Buscando valores na TOP 13...</td></tr>';
            listDireto.innerHTML = '';
        }

        let totalBruto = 0;
        let totalDescontoAvaria = 0;         // soma dos descontos de avaria fornecedor (Opção B — Mai/2026)
        let temPendente = false;             // qualquer item bloqueando (preço OU classificação OU avaria)
        let temPendentePreco = false;        // algum item sem preço definido
        let temPendenteClassificacao = false;// algum classificável sem TOP 26 finalizada (PENDENTE != 'N')
        let temPendenteAvaria = false;       // algum lote tem avaria do fornecedor não refletida (Opção B)
        let htmlClass = '';
        let htmlDireto = '';

        // Pega o número do Vale (Se houver)
        const notaRef = itensDaNota.find(r => window.ComercialUtils.toNumber(r.nunota_13) > 0);
        const nunota13Ativo = notaRef ? window.ComercialUtils.toNumber(notaRef.nunota_13) : 0;

        let vlroutrosInicial = 0;
        let nufinAtivo = 0;
        if (nunota13Ativo > 0) {
            try {
                const resCab = await fetch(`/sankhya/comercial/api/detalhes-vale/?nunota_13=${nunota13Ativo}&lote=${STATE.dadosNota.codagregacao || ''}`);
                const dataCab = await resCab.json();
                vlroutrosInicial = window.ComercialUtils.toNumber(dataCab.vlroutros || 0);
                nufinAtivo = window.ComercialUtils.toNumber(dataCab.nufin || 0);
            } catch (e) { console.error("Erro ao carregar estado", e); }
        }
        STATE.dadosNota.nufin = nufinAtivo; // Guarda na memória se faturou

        // 🚀 Atualiza o subtítulo com os dados frescos da API
        let subtituloApi = `Pedido: ${nunota}`;
        if (nunota13Ativo > 0) subtituloApi += ` | Vale: ${nunota13Ativo}`;
        if (nufinAtivo > 0) subtituloApi += ` | Fin: ${nufinAtivo}`;
        document.getElementById('fechamentoPedido').textContent = subtituloApi;

        if (nufinAtivo > 0) {
            document.body.classList.add('vale-faturado');
        }

        // 2. PRÉ-CARREGA dados de cada item (fetches por lote no vale TOP 13 + balanço da classificação).
        // Resultado salvo em STATE.itensCalculados — re-usado pelo toggle Descontar/Pagar Total
        // (Mai/2026 — 2026-05-20) sem precisar refetch.
        STATE.itensCalculados = [];
        STATE.nunota13Ativo = nunota13Ativo;
        STATE.nufinAtivo = nufinAtivo;
        STATE.vlroutrosInicial = vlroutrosInicial;
        for (const item of itensDaNota) {
            const isClassificavel = item.geraproducao === 'S';
            const fabricante = item.fabricante || item.produto || 'PRODUTO';
            const pesoCx = window.ComercialUtils.toNumber(item.qtdfixada) || 20;
            const lote = item.codagregacao || '';

            let vlrTotal = 0;
            let vlrUnitDireto = 0;

            // Busca na TOP 13 filtrando pelo lote
            if (nunota13Ativo > 0) {
                try {
                    const resVale = await fetch(`/sankhya/comercial/api/detalhes-vale/?nunota_13=${nunota13Ativo}&lote=${lote}`);
                    const dataVale = await resVale.json();

                    if (dataVale.ok && dataVale.itens) {
                        for (const it of dataVale.itens) {
                            if (!isClassificavel && String(it.codprod) !== String(item.codprod)) {
                                continue;
                            }
                            vlrTotal += window.ComercialUtils.toNumber(it.vlrtot) || 0;
                            if (!isClassificavel) {
                                vlrUnitDireto = window.ComercialUtils.toNumber(it.vlrunit) || 0;
                            }
                        }
                    }
                } catch (e) { console.warn(`Erro ao buscar lote ${lote} na TOP 13`, e); }
            }

            let kgFisicoTotal = 0;
            if (isClassificavel) {
                try {
                    const resBal = await fetch(`/sankhya/lote/consultar/?lote=${lote}&nunota_origem=${item.nunota}`);
                    const dataBal = await resBal.json();
                    if (dataBal.ok && dataBal.classificacoes) {
                        kgFisicoTotal = dataBal.classificacoes
                            .filter(c => window.ComercialUtils.toNumber(c.selecionado) !== 0)
                            .reduce((acc, curr) => acc + window.ComercialUtils.toNumber(curr.qtd), 0);
                    }
                } catch (e) { console.warn("Erro ao buscar balanço", e); }
            }

            STATE.itensCalculados.push({
                item, isClassificavel, fabricante, pesoCx, lote,
                vlrTotal, vlrUnitDireto, kgFisicoTotal,
            });
        }

        // Render inicial (default: absorveuAvariaPorLote vazio → Descontar/cobra fornecedor)
        _renderListasFaturamento();
        recalcularLiquido();
    };

    // Decisão Absorver/Descontar por lote (Mai/2026 — 2026-05-20).
    // Segmented control com as 2 opções visíveis. Click define explicitamente.
    // Default visual = Absorver. Backend B8 reconcilia TGFCAB TOP 30 ao FATURAR.
    //
    // Quando o vale TOP 13 já existe (preço lançado), dispara endpoint B12
    // pra recalcular QTDNEG/VLRTOT conforme decisão imediatamente.
    const setAbsorverAvaria = async (lote, decisaoAbsorver) => {
        STATE.absorveuAvariaPorLote = STATE.absorveuAvariaPorLote || {};
        const chave = String(lote);
        const decisao = !!decisaoAbsorver;
        const valorAnterior = STATE.absorveuAvariaPorLote[chave];

        STATE.absorveuAvariaPorLote[chave] = decisao;
        _renderListasFaturamento();
        recalcularLiquido();

        // Se vale ainda não foi salvo (sem nunota13Ativo), só atualiza visual —
        // a flag será aplicada quando o operador editar o preço (B11).
        const nunota13Ativo = STATE.nunota13Ativo || 0;
        if (!nunota13Ativo) return;

        // Localiza item pra obter nunota_origem + codprod
        const itemData = (STATE.itensCalculados || []).find(
            d => String(d.lote) === chave && !d.isClassificavel
        );
        if (!itemData) return;

        try {
            const res = await window.IAgro.postJSON('/sankhya/comercial/api/avaria-modo-vale/', {
                nunota_origem: itemData.item.nunota,
                codprod: itemData.item.codprod,
                codagregacao: itemData.lote,
                absorver: decisao,
            });
            if (res.ok && res.body?.ok) {
                window.ComercialUtils.mostrarToast(
                    decisao ? 'Avaria absorvida — vale com qtd cheia.' : 'Avaria descontada — vale com qtd líquida.',
                    'sucesso',
                );
                // Reabre o modal pra refletir QTDNEG/VLRTOT atualizados do banco
                await abrir(STATE.dadosNota.nunota);
            } else {
                // Reverte visual + mostra erro
                STATE.absorveuAvariaPorLote[chave] = valorAnterior;
                _renderListasFaturamento();
                recalcularLiquido();
                const errMsg = res.body?.error || 'Falha ao alterar modo da avaria.';
                window.ComercialUtils.mostrarToast(errMsg, 'erro');
            }
        } catch (e) {
            console.error('setAbsorverAvaria falhou', e);
            STATE.absorveuAvariaPorLote[chave] = valorAnterior;
            _renderListasFaturamento();
            recalcularLiquido();
            window.ComercialUtils.mostrarToast('Falha de conexão ao alterar modo da avaria.', 'erro');
        }
    };

    const editarPreco = (nunotaOrigem, codprod, nunota13, spanElement) => {
        if (STATE.dadosNota && STATE.dadosNota.nufin > 0) {
            window.ComercialUtils.mostrarToast("Vale faturado. Desfature para editar preços.", "aviso");
            return;
        }

        const valorAtual = spanElement.innerText.trim();
        const input = document.createElement('input');
        input.type = 'text';
        input.value = valorAtual;
        input.className = 'preco-input';
        input.style.width = '60px';
        input.style.textAlign = 'right';

        spanElement.style.display = 'none';
        spanElement.parentNode.insertBefore(input, spanElement);
        input.focus();
        input.select();

        const salvar = async () => {
            const novoPreco = window.ComercialUtils.toNumber(input.value);
            if (isNaN(novoPreco) || novoPreco < 0) {
                input.remove(); spanElement.style.display = 'inline'; return;
            }

            input.disabled = true;
            try {
                const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
                const res = await fetch('/sankhya/comercial/api/atualizar-preco-modalFaturamento/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ nunota_origem: nunotaOrigem, codprod: codprod, nunota_13: nunota13, preco: novoPreco })
                });

                const data = await res.json();
                if (!data.ok) throw new Error(data.error);

                window.ComercialUtils.mostrarToast("Preço salvo com sucesso!", "sucesso");

                // 🚀 FIX: Ensina a memória do Javascript que o Vale agora existe!
                if (data.nunota_13 && window.__COM_LIST_ROWS) {
                    window.__COM_LIST_ROWS.forEach(r => {
                        if (r.nunota == nunotaOrigem) r.nunota_13 = data.nunota_13;
                    });
                }

                // Refresh global (Mai/2026 — B9 follow-up): recarrega lista
                // lateral do servidor. Crítico porque o backend B6 propaga
                // o preço pra TOP 11 (PRECOBASE/VLRUNIT/VLRTOT) — sem reload,
                // o card Entrada continua mostrando os valores antigos do
                // cache (`__COM_LIST_ROWS`). Após o refresh, reselecionamos a
                // linha do pedido pra reapresentar os cards atualizados.
                if (window.ComercialFiltros?.atualizar) {
                    window.ComercialFiltros.atualizar();
                }

                // Reabre o modal silenciosamente e reseleciona a linha pra
                // forçar redesenho dos cards Entrada/Classificação/Distribuição.
                abrir(nunotaOrigem);
                const linhaSel = document.querySelector('tr.lista-item-row.row--sel');
                if (linhaSel) linhaSel.click();

            } catch (e) {
                window.ComercialUtils.mostrarToast(e.message, "erro");
                input.remove(); spanElement.style.display = 'inline';
            }
        };

        input.addEventListener('blur', salvar);
        input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); });
    };

    // --- INÍCIO DO NOVO CÓDIGO ---
    const toggleInss = async (nunota13) => {
        const isChecked = document.getElementById('chkInss').checked;
        const valorDesconto = isChecked ? (STATE.bruto * 0.0163) : 0;

        try {
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/atualizar-desconto-inss/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ nunota_13: nunota13, valor: valorDesconto })
            });

            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            window.ComercialUtils.mostrarToast(isChecked ? "Desconto INSS aplicado!" : "Desconto removido!", "sucesso");
            recalcularLiquido();

        } catch (e) {
            window.ComercialUtils.mostrarToast("Erro ao salvar desconto: " + e.message, "erro");
            document.getElementById('chkInss').checked = !isChecked;
        }
    };
    // --- FIM DO NOVO CÓDIGO ---

    const recalcularLiquido = () => {
        const isChecked = document.getElementById('chkInss').checked;

        // Opção B (Mai/2026 — 2026-05-20): se há avaria, líquido parte do bruto descontado.
        // Quando não há avaria, STATE.brutoLiquido === STATE.bruto (sem efeito).
        const baseBruto = STATE.brutoLiquido !== undefined ? STATE.brutoLiquido : STATE.bruto;

        // 🚀 FIX: Arredondamento para 2 casas decimais (padrão monetário)
        // Usamos Math.round com multiplicador 100 para garantir que 235.515 vire 235.52
        const inss = isChecked ? Math.round((baseBruto * 0.0163) * 100) / 100 : 0;

        // O líquido deve ser a subtração exata dos dois valores já arredondados
        STATE.liquido = Math.round((baseBruto - inss) * 100) / 100;

        document.getElementById('vlrInssFechamento').textContent = `R$ ${inss.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        document.getElementById('vlrLiquidoFechamento').textContent = `R$ ${STATE.liquido.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    const faturar = async () => {
        const nunota13 = STATE.dadosNota.nunota_13;
        if (!nunota13) return window.ComercialUtils.mostrarToast("Erro: Vale não gerado.", "erro");

        if (!confirm(`Confirmar faturamento e geração de financeiro de R$ ${STATE.liquido.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}?`)) return;

        const btn = document.getElementById('btnEfetivarFaturamento');
        btn.disabled = true; btn.textContent = "PROCESSANDO...";

        try {
            const lote = STATE.dadosNota.codagregacao || 'S/L';
            const historico = `Faturamento via IAgro - Vale ${STATE.dadosNota.nunota}`.substring(0, 255);
            const usaInss = document.getElementById('chkInss').checked;
            const valorInss = usaInss ? (STATE.bruto * 0.0163) : 0;

            // Mai/2026 (2026-05-20) — coleta lotes marcados pra absorver avaria.
            // Default do toggle = Descontar (false). Só Absorver quando operador clicou.
            // Backend reconcilia TGFCAB TOP 30 antes de gerar TGFFIN (cria ou remove).
            const lotesAbsorverAvaria = [];
            const absorveuMap = STATE.absorveuAvariaPorLote || {};
            const avariasPorLote = STATE.avariasPorLote || {};
            for (const data of (STATE.itensCalculados || [])) {
                if (data.isClassificavel) continue;  // só não-classificáveis
                const lote = String(data.lote || '');
                if (!lote) continue;
                if (!(avariasPorLote[lote] && Number(avariasPorLote[lote].qtd_avaria || 0) > 0)) continue;
                // Default = false (Descontar). Só true se operador clicou em Absorver.
                if (absorveuMap[lote] === true) lotesAbsorverAvaria.push(lote);
            }

            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/efetivar-faturamento/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({
                    nunota_13: nunota13,
                    descontar_inss: usaInss,
                    historico: historico,
                    vlrinss: valorInss,
                    vlr_forcar_liquido: STATE.liquido, // 🚀 Manda o Líquido Exato (ex: 757.45)
                    vlr_forcar_bruto: STATE.bruto,     // 🚀 Manda o Bruto Exato (ex: 767.90)
                    lotes_absorver_avaria: lotesAbsorverAvaria, // ← Mai/2026 (2026-05-20)
                })
            });

            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            window.ComercialUtils.mostrarToast("Financeiro gerado com sucesso!", "sucesso");

            STATE.dadosNota.nufin = data.nufin || 1; // Atualiza a memória

            // 1. Recarrega o modal (usando await para não atropelar)
            await abrir(STATE.dadosNota.nunota);

            // 2. Atualiza TODOS os painéis do fundo para aplicar as travas
            if (window.ComercialEntrada) window.ComercialEntrada.preencher(STATE.dadosNota);
            if (window.ComercialClassificacao) {
                window.ComercialClassificacao.preencher(STATE.dadosNota).then(pesos => {
                    if (window.ComercialDistribuicao) window.ComercialDistribuicao.preencher(STATE.dadosNota, pesos);
                });
            }

            // 3. Atualiza a lista lateral
            if (window.ComercialFiltros && window.ComercialFiltros.atualizar) {
                window.ComercialFiltros.atualizar();
            }

        } catch (e) {
            window.ComercialUtils.mostrarToast("Falha ao faturar: " + e.message, "erro");
            btn.disabled = false; btn.textContent = "FATURAR";
        }
    };

    // --- NOVA FUNÇÃO DESFATURAR ---
    const desfaturar = async (nunota13) => {
        if (!confirm("Atenção: Isso excluirá o título financeiro para permitir novas edições. Deseja continuar?")) return;

        const btn = document.getElementById('btnEfetivarFaturamento');
        btn.disabled = true; btn.textContent = "EXCLUINDO...";

        try {
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/desfaturar-vale/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ nunota_13: nunota13 })
            });

            const data = await res.json();
            if (!data.ok) throw new Error(data.error);

            window.ComercialUtils.mostrarToast("Vale reaberto para edição!", "sucesso");

            STATE.dadosNota.nufin = 0; // Limpa a memória
            STATE.dadosNota.qtd_baixados = 0; // Garante destravamento completo

            // 1. Recarrega o modal (usando await para não atropelar)
            await abrir(STATE.dadosNota.nunota);

            // 2. Atualiza TODOS os painéis do fundo para remover as travas e o carimbo
            if (window.ComercialEntrada) window.ComercialEntrada.preencher(STATE.dadosNota);
            if (window.ComercialClassificacao) {
                window.ComercialClassificacao.preencher(STATE.dadosNota).then(pesos => {
                    if (window.ComercialDistribuicao) window.ComercialDistribuicao.preencher(STATE.dadosNota, pesos);
                });
            }

            // 3. Atualiza a lista lateral
            if (window.ComercialFiltros && window.ComercialFiltros.atualizar) {
                window.ComercialFiltros.atualizar();
            }

        } catch (e) {
            window.ComercialUtils.mostrarToast(e.message, "erro");
            btn.disabled = false; btn.textContent = "DESFATURAR";
        }
    };

    const fechar = () => {
        document.getElementById('modalFaturamento').style.display = 'none';
    };

    // Mai/2026 (2026-05-19) — mini-modal de detalhes da avaria do fornecedor.
    // Aciona ao clicar no ⚠ na linha do item. Renderiza fornecedor +
    // qtd entrada + avaria + líquido calculado, sem chamar API extra.
    const abrirAvariaDetalhe = (lote) => {
        const dados = (STATE.avariasPorLote || {})[String(lote)];
        if (!dados) return;

        let dlg = document.getElementById('avariaForncDetalheModal');
        if (!dlg) {
            dlg = document.createElement('div');
            dlg.id = 'avariaForncDetalheModal';
            dlg.className = 'modal-overlay';
            dlg.style.display = 'none';
            dlg.innerHTML = `
                <div class="cf-avaria-detalhe">
                    <div class="cf-avaria-detalhe__header">
                        <i class="ph ph-warning" aria-hidden="true"></i>
                        <strong>Avaria do fornecedor</strong>
                        <button type="button" class="close-modal" aria-label="Fechar">&times;</button>
                    </div>
                    <div class="cf-avaria-detalhe__body" id="cfAvariaDetalheBody"></div>
                </div>`;
            document.body.appendChild(dlg);
            dlg.querySelector('.close-modal').addEventListener('click', () => {
                dlg.style.display = 'none';
            });
            dlg.addEventListener('click', (ev) => {
                if (ev.target === dlg) dlg.style.display = 'none';
            });
        }

        const qtdEntrada = Number(dados.qtd_entrada || 0);
        const qtdAvaria  = Number(dados.qtd_avaria  || 0);
        const liquido    = qtdEntrada - qtdAvaria;
        const fmt = (n) => window.ComercialUtils.formatQty(n);
        const dt  = dados.dtneg_entrada ? new Date(dados.dtneg_entrada).toLocaleDateString('pt-BR') : '—';

        document.getElementById('cfAvariaDetalheBody').innerHTML = `
            <div class="cf-avaria-detalhe__lote">Lote <strong>${lote}</strong></div>
            <table class="cf-avaria-detalhe__tabela">
                <tr><td>Fornecedor:</td><td><strong>${dados.fornecedor || '—'}</strong></td></tr>
                <tr><td>Data entrada:</td><td>${dt}</td></tr>
                <tr><td>Qtd entrada:</td><td class="txt-right">${fmt(qtdEntrada)} kg</td></tr>
                <tr class="cf-avaria-detalhe__avaria">
                    <td>Avaria:</td>
                    <td class="txt-right"><strong>${fmt(qtdAvaria)} kg</strong></td>
                </tr>
                <tr class="cf-avaria-detalhe__separador"><td colspan="2"></td></tr>
                <tr class="cf-avaria-detalhe__liquido">
                    <td>Líquido:</td>
                    <td class="txt-right"><strong>${fmt(liquido)} kg</strong></td>
                </tr>
            </table>
            <p class="cf-avaria-detalhe__nota">
                A quantidade do vale (TOP 13) reflete o que foi recebido do fornecedor.
                Use o chip <strong>📉 Descontar / 📌 Absorver</strong> na linha do item:
                <br>• <strong>Descontar</strong> (padrão) — Agromil cobra ${window.ComercialUtils.formatQty(qtdAvaria)} kg
                do fornecedor (negociar no próximo pedido).
                <br>• <strong>Absorver</strong> — Agromil banca a perda. Backend gera TOP 30
                (avaria interna) que desconta ${window.ComercialUtils.formatQty(qtdAvaria)} kg do estoque automaticamente.
            </p>
        `;
        dlg.style.display = 'flex';
    };

    const getItens = () => STATE.itens;
    return { abrir, editarPreco, toggleInss, recalcularLiquido, faturar, desfaturar, fechar, getItens, abrirAvariaDetalhe, setAbsorverAvaria };
})();