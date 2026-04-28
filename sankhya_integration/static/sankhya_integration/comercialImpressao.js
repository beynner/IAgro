window.ComercialImpressao = (function() {
    let valeAtual = null;

    const abrir = () => {
        // 🚀 FIX: Ignora a lista do fundo. Puxa direto da memória blindada do ComercialFinanceiro!
        valeAtual = window.ComercialFinanceiro ? window.ComercialFinanceiro.getItens() : [];
        
        if (!valeAtual || valeAtual.length === 0) {
            return window.ComercialUtils.mostrarToast("Dados do vale não encontrados na memória.", "erro");
        }

        const notaInfo = valeAtual[0]; 
        document.getElementById('printParceiroNome').textContent = notaInfo.parceiro || '---';
        document.getElementById('printValeId').textContent = `Pedido: ${notaInfo.nunota}`;
        document.getElementById('modalImpressao').style.display = 'flex';
        
        renderizarPreview();
    };

    const fechar = () => {
        document.getElementById('modalImpressao').style.display = 'none';
        valeAtual = null;
    };

    const renderizarPreview = async () => {
        if (!valeAtual || valeAtual.length === 0) return;

        const tipoSelecionado = document.querySelector('input[name="printType"]:checked').value;
        const area = document.getElementById('printContentArea');
        const notaInfo = valeAtual[0];

        // 🚀 FORÇA A FONTE MONOSPACE NA TELA DE PREVIEW
        area.style.fontFamily = "monospace";

        document.querySelectorAll('.print-option').forEach(el => el.classList.remove('active'));
        document.querySelector(`input[name="printType"]:checked`).closest('.print-option').classList.add('active');

        const dataHj = new Date().toLocaleDateString('pt-BR') + ' ' + new Date().toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'});
        
        // 🚀 FORMATAÇÃO DA DATA DO PEDIDO
        let dataPedido = notaInfo.dtneg || '---';
        if (dataPedido.includes('-')) {
            dataPedido = dataPedido.split('-').reverse().join('/');
        }
        
        let rodapeMensagem = 'SEM VALOR FISCAL!'; 

        const extrairDadosDoVale = (tbodyId) => {
            const mapa = new Map();
            const linhas = document.querySelectorAll(`#${tbodyId} tr`);
            linhas.forEach(tr => {
                const tds = tr.querySelectorAll('td');
                if (tds.length >= 4) {
                    const nome = tds[0].innerText.trim();
                    if (nome.includes("Nenhum produto")) return;
                    const textoQtde = tds[1].innerText.split('\n')[0].trim();
                    const matchQtde = textoQtde.match(/^([\d,.]+)\s*(.*)$/);
                    const qtdeNum = matchQtde ? matchQtde[1] : textoQtde;
                    const unidade = matchQtde ? matchQtde[2].toLowerCase() : '';
                    let unitVlr = tds[2].innerText.split('\n')[0].replace(/R\$\s?/g, '').trim();
                    unitVlr = unitVlr.split('/')[0].trim(); 
                    const totalNum = parseFloat(tds[3].innerText.replace(/R\$\s?/g, '').replace(/\./g, '').replace(',', '.')) || 0;
                    mapa.set(nome, { qtde: qtdeNum, unitLabel: unidade, unitVlr, total: totalNum });
                }
            });
            return mapa;
        };

        const dadosValeClass = extrairDadosDoVale('listaFechamentoClass');
        const dadosValeDireto = extrairDadosDoVale('listaFechamentoDireto');

        // ==========================================
        // LAYOUT 1: IN NATURA
        // ==========================================
        if (tipoSelecionado === 'innatura') {
            let htmlFinal = '';
            let brutoTotal = 0;
            const itensInNatura = [...dadosValeClass.entries(), ...dadosValeDireto.entries()];

            itensInNatura.forEach(([k, v], index) => {
                if (index > 0) {
                    htmlFinal += `<tr><td colspan="4" style="border-bottom: 2px dashed #000; padding: 0;"></td></tr>`;
                }

                const estiloZerado = v.total === 0 ? 'background-color: #fee2e2;' : '';
                
                htmlFinal += `
                    <tr style="${estiloZerado}">
                        <td style="width:38%; padding: 4px 2px;">${k}</td>
                        <td style="width:17%; text-align:right;">${v.qtde}<small>${v.unitLabel}</small></td>
                        <td style="width:20%; text-align:right;">${v.unitVlr}</td>
                        <td style="width:25%; text-align:right; font-weight:bold;">${v.total.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                    </tr>`;
                brutoTotal += v.total;
            });

            const temInss = document.getElementById('chkInss')?.checked;
            const vlrInss = document.getElementById('vlrInssFechamento')?.innerText.replace(/R\$\s?/g, '').trim() || '0,00';
            const vlrLiquido = document.getElementById('vlrLiquidoFechamento')?.innerText.replace(/R\$\s?/g, '').trim() || '---';

            area.innerHTML = `
                <div style="text-align:center;margin-bottom:10px;border-bottom:2px dashed black;padding-bottom:5px;">
                    <h3 style="margin:0;font-size:14px;">VALE DE COMPRA IN NATURA</h3>
                    <p style="margin:2px 0;font-size:11px;font-weight:bold;">Pedido: ${notaInfo.nunota} | Vale: ${notaInfo.nunota_13 || '---'}</p>
                </div>
                <div style="margin-bottom:10px;">
                    <p style="margin:0;font-size:12px;font-weight:bold;">Parceiro: ${notaInfo.parceiro}</p>
                    <p style="margin:2px 0 0 0;font-size:11px;">Data do Pedido: ${dataPedido}</p>
                </div>
                <table class="print-table" style="width:100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="text-align:left; padding-bottom: 4px;">Produto</th>
                            <th class="txt-right" style="padding-bottom: 4px;">Qtde</th>
                            <th class="txt-right" style="padding-bottom: 4px;">Vlr Unit</th>
                            <th class="txt-right" style="padding-bottom: 4px;">Vlr Total</th>
                        </tr>
                        <tr><td colspan="4" style="border-bottom: 2px dashed #000; padding: 0;"></td></tr>
                    </thead>
                    <tbody>${htmlFinal}</tbody>
                </table>
                <div style="margin-top:10px;border-top:2px solid black;padding-top:5px;">
                    <div style="display:flex;justify-content:space-between;font-weight:bold;font-size:12px;"><span>Valor TotalBruto:</span><span>R$ ${brutoTotal.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                    ${temInss ? `<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:3px;"><span>Desconto INSS (1,63%):</span><span>- R$ ${vlrInss}</span></div>` : ''}
                    <div style="display:flex;justify-content:space-between;font-weight:bold;font-size:14px;margin-top:5px;"><span>Valor Total Líquido:</span><span>${vlrLiquido}</span></div>
                </div>`;

        // ==========================================
        // LAYOUT 2: SIMULAÇÃO
        // ==========================================
        } else if (tipoSelecionado === 'simulacao') {
            let htmlBlocos = '';
            let totalBrutoSimulado = 0;

            valeAtual.forEach((item, index) => {
                const produtoBase = (item.fabricante || item.produto || '---').trim();
                const isClassificavel = item.geraproducao === 'S';
                const volS = (item.codvolparc || item.codvol || 'CX').toLowerCase();

                let subTotalQtd = 0;
                let subTotalVlr = 0;

                if (index > 0) {
                    htmlBlocos += `<tr><td colspan="4" style="border-bottom: 2px dashed #000; padding: 0;"></td></tr>`;
                }

                htmlBlocos += `<tr><td colspan="4" style="padding: 4px 4px 0 0; font-weight: 800; font-size: 11px; text-transform: uppercase;">${produtoBase}</td></tr>`;

                const temSimulacao = isClassificavel && ((item.ad_simqtd1 > 0) || (item.ad_simqtd2 > 0));

                if (!temSimulacao) {
                    let doVale = null;
                    const todosItensTela = [...dadosValeClass.entries(), ...dadosValeDireto.entries()];
                    const matchExato = todosItensTela.find(([nome]) => nome.trim() === produtoBase);
                    
                    if (matchExato) {
                        doVale = matchExato[1];
                    } else {
                        const matchParcial = todosItensTela.find(([nome]) => nome.toUpperCase().includes(produtoBase.toUpperCase()) || produtoBase.toUpperCase().includes(nome.toUpperCase()));
                        if (matchParcial) doVale = matchParcial[1];
                    }

                    let qPortaria = window.ComercialUtils.toNumber(item.qtdconferida || item.qtdneg) || 0;
                    let unitCalc = window.ComercialUtils.toNumber(item.vlrunit || 0);
                    let vTotalVale = 0;

                    if (doVale) {
                        vTotalVale = doVale.total;
                        if (qPortaria === 0) qPortaria = window.ComercialUtils.toNumber(doVale.qtde) || 0;
                        unitCalc = qPortaria > 0 ? (vTotalVale / qPortaria) : window.ComercialUtils.toNumber(doVale.unitVlr.replace(',', '.'));
                    } else {
                        vTotalVale = qPortaria * unitCalc;
                    }

                    const estiloZerado = vTotalVale === 0 ? 'background-color: #fee2e2;' : '';
                    
                    totalBrutoSimulado += vTotalVale;
                    subTotalQtd += qPortaria;
                    subTotalVlr += vTotalVale;

                    htmlBlocos += `
                        <tr style="${estiloZerado}">
                            <td style="width:38%; padding-left: 12px; font-size: 11px; font-weight: bold; color: #000;">↳ In Natura</td>
                            <td style="width:17%; text-align:right; font-weight: bold; color: #000;">${qPortaria.toFixed(1)}<small>${volS}</small></td>
                            <td style="width:20%; text-align:right; font-weight: bold; color: #000;">${unitCalc.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                            <td style="width:25%; text-align:right; font-weight: 900; color: #000;">${vTotalVale.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                        </tr>`;
                        
                } else {
                    const renderSim = (label, qR, uR) => {
                        if (qR > 0) {
                            const q = window.ComercialUtils.toNumber(qR);
                            const u = window.ComercialUtils.toNumber(uR || 0);
                            const t = q * u;
                            
                            totalBrutoSimulado += t;
                            subTotalQtd += q;
                            subTotalVlr += t;
                            
                            const estiloZerado = t === 0 ? 'background-color: #fee2e2;' : '';
                            
                            htmlBlocos += `
                                <tr style="${estiloZerado}">
                                    <td style="width:38%; padding-left: 12px; font-size: 11px; font-weight: bold; color: #000;">↳ ${label}</td>
                                    <td style="width:17%; text-align:right; font-weight: bold; color: #000;">${q.toFixed(1)}<small>${volS}</small></td>
                                    <td style="width:20%; text-align:right; font-weight: bold; color: #000;">${u.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                                    <td style="width:25%; text-align:right; font-weight: 900; color: #000;">${t.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                                </tr>`;
                        }
                    };
                    renderSim('Extra', item.ad_simqtd1, item.ad_simvlr1);
                    renderSim('Médio', item.ad_simqtd2, item.ad_simvlr2);
                    
                    if (item.ad_simqtddesc > 0) {
                        const qQuebra = window.ComercialUtils.toNumber(item.ad_simqtddesc);
                        subTotalQtd += qQuebra;

                        htmlBlocos += `
                            <tr>
                                <td style="width:38%; padding-left: 12px; font-size: 10px; font-weight: bold; color: #000;">↳ QUEBRA</td>
                                <td style="width:17%; text-align:right; font-weight: bold; color: #000;">${qQuebra.toFixed(1)}<small>${volS}</small></td>
                                <td colspan="2"></td>
                            </tr>`;
                    }
                }

                if (subTotalQtd > 0 || subTotalVlr > 0) {
                    htmlBlocos += `
                        <tr>
                            <td style="width:38%; padding: 6px 0 2px 0; font-weight: bold; font-size: 11px; text-align: right; border-top: 1px dashed #ccc;">Subtotal:</td>
                            <td style="width:17%; text-align:right; font-weight: bold; padding: 6px 0 2px 0; border-top: 1px dashed #ccc;">${subTotalQtd.toFixed(1)}<small>${volS}</small></td>
                            <td style="width:20%; border-top: 1px dashed #ccc;"></td>
                            <td style="width:25%; text-align:right; font-weight:900; padding: 6px 0 2px 0; border-top: 1px dashed #ccc;">${subTotalVlr.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                        </tr>`;
                }
            });

            const temInss = document.getElementById('chkInss')?.checked || false;
            const vlrInssSim = temInss ? Math.round((totalBrutoSimulado * 0.0163) * 100) / 100 : 0;
            const vlrLiqSim = totalBrutoSimulado - vlrInssSim;

            area.innerHTML = `
                <div style="text-align:center;margin-bottom:10px;border-bottom:2px dashed black;padding-bottom:5px;">
                    <h3 style="margin:0;font-size:14px;">VALE DE COMPRA</h3>
                    <p style="margin:2px 0;font-size:11px;font-weight:bold;">Pedido: ${notaInfo.nunota} | Vale: ${notaInfo.nunota_13 || '---'}</p>
                </div>
                <div style="margin-bottom:10px;">
                    <p style="margin:0;font-size:12px;font-weight:bold;">Parceiro: ${notaInfo.parceiro}</p>
                    <p style="margin:2px 0 0 0;font-size:11px;">Data do Pedido: ${dataPedido}</p>
                </div>
                <table class="print-table" style="width:100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="text-align:left; padding-bottom: 4px;">Produto</th>
                            <th class="txt-right" style="padding-bottom: 4px;">Qtde</th>
                            <th class="txt-right" style="padding-bottom: 4px;">Vlr Unit</th>
                            <th class="txt-right" style="padding-bottom: 4px;">Vlr Total</th>
                        </tr>
                        <tr><td colspan="4" style="border-bottom: 2px dashed #000; padding: 0;"></td></tr>
                    </thead>
                    <tbody>${htmlBlocos}</tbody>
                </table>
                <div style="border-top:2px solid black; padding-top:5px; margin-top:2px;">
                    <div style="display:flex;justify-content:space-between;font-weight:bold;font-size:12px;"><span>Valor Total Bruto:</span><span>R$ ${totalBrutoSimulado.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                    ${temInss ? `<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:3px;"><span>INSS (1,63%):</span><span>- R$ ${vlrInssSim.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>` : ''}
                    <div style="display:flex;justify-content:space-between;font-weight:900;font-size:14px;margin-top:5px;"><span>Valor Total Líquido:</span><span>R$ ${vlrLiqSim.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span></div>
                </div>`;
        
        // ==========================================
        // LAYOUT 3: DISTRIBUIÇÃO
        // ==========================================
        } else if (tipoSelecionado === 'distribuicao') {
            rodapeMensagem = 'SEM VALOR FISCAL!!!';
            let htmlBlocos = '';
            let valesInclusos = false;

            const itensClassificaveis = valeAtual.filter(item => item.geraproducao === 'S');

            if (itensClassificaveis.length === 0) {
                htmlBlocos = `<div style="text-align: center; margin-top: 30px; font-weight: bold; color: #000;">Nenhum produto classificável distribuído neste vale.</div>`;
            } else {
                valesInclusos = true;
                
                // Percorre os itens que são "mãe" (In Natura) no Vale Atual
                for (let i = 0; i < itensClassificaveis.length; i++) {
                    const item = itensClassificaveis[i];
                    const produtoBase = (item.fabricante || item.produto || '---').trim();
                    const lote = item.codagregacao;
                    const volS = (item.codvolparc || item.codvol || 'CX').toLowerCase();

                    // 🚀 DADOS DE COMPRA ORIGINAL (COM PESOS)
                    const pesoIn = window.ComercialUtils.toNumber(item.peso || 0);
                    const pesoClass = window.ComercialUtils.toNumber(item.qtdfixada || 20);
                    const precoCaixaOrigin = window.ComercialUtils.toNumber(item.precobase || item.vlrunit);
                    const qtdCaixaOrigin = window.ComercialUtils.toNumber(item.qtdconferida || item.qtdneg);
                    const inNaturaKgTotal = qtdCaixaOrigin * pesoIn;
                    const precoKgOrigin = pesoIn > 0 ? precoCaixaOrigin / pesoIn : 0;
                    const totalGeralOrigem = precoCaixaOrigin * qtdCaixaOrigin;

                    const separadorGrossso = i > 0 ? 'margin-top: 10px; border-top: 3px solid #000; padding-top: 10px;' : '';

                    let subTotalDistVlr = 0;
                    let subTotalDistKg = 0;
                    let subTotalDistCx = 0;
                    let linhasDist = '';

                    // 🚀 CONSULTA A FONTE DA VERDADE (O VALE TOP 13)
                    if (item.nunota_13) {
                        try {
                            const resVale = await fetch(`/sankhya/comercial/api/detalhes-vale/?nunota_13=${item.nunota_13}&lote=${lote}`);
                            const jsonVale = await resVale.json();
                            
                            if (jsonVale.ok && jsonVale.itens && jsonVale.itens.length > 0) {
                                jsonVale.itens.forEach(itFaturado => {
                                    let nomeClass = "OUTROS";
                                    if (itFaturado.selecionado === 1) nomeClass = "EXTRA";
                                    else if (itFaturado.selecionado === 2 || (itFaturado.caracteristicas && itFaturado.caracteristicas.includes('MEDIO'))) nomeClass = "MÉDIO";
                                    else if (itFaturado.selecionado === 0) nomeClass = "IN NATURA";

                                    const vTotal = window.ComercialUtils.toNumber(itFaturado.vlrtot);
                                    const vKgs = window.ComercialUtils.toNumber(itFaturado.qtdneg);
                                    const vUnitKg = window.ComercialUtils.toNumber(itFaturado.vlrunit);

                                    const qtdCxDist = pesoClass > 0 ? (vKgs / pesoClass) : 0;
                                    const custoCxDist = vUnitKg * pesoClass;

                                    subTotalDistVlr += vTotal;
                                    subTotalDistKg += vKgs;
                                    subTotalDistCx += qtdCxDist;

                                    linhasDist += `
                                        <tr>
                                            <td style="width:38%; padding: 4px 0; text-transform: uppercase; font-weight: bold; font-size: 11px; vertical-align: top; color: #000;">
                                                ↳ ${nomeClass}
                                            </td>
                                            <td style="width:20%; text-align:right; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                                <div style="margin-bottom: 2px;">${vKgs.toLocaleString('pt-BR')}<small>kg</small></div>
                                                <div>${qtdCxDist.toLocaleString('pt-BR', {minimumFractionDigits: 1})}<small>cx</small></div>
                                            </td>
                                            <td style="width:18%; text-align:right; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                                <div style="margin-bottom: 2px;">${vUnitKg.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                                <div>${custoCxDist.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                            </td>
                                            <td style="width:24%; text-align:right; font-weight:bold; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                                ${vTotal.toLocaleString('pt-BR', {minimumFractionDigits: 2})}
                                            </td>
                                        </tr>`;
                                });
                            } else {
                                linhasDist = `<tr><td colspan="4" style="text-align:center; padding: 10px 0; font-style: italic; font-size: 11px; color: #000;">Itens não encontrados no vale.</td></tr>`;
                            }
                        } catch (err) {
                            linhasDist = `<tr><td colspan="4" style="text-align:center; padding: 10px 0; font-style: italic; font-size: 11px; color: #000;">Erro ao buscar distribuição.</td></tr>`;
                        }
                    } else {
                        linhasDist = `<tr><td colspan="4" style="text-align:center; padding: 10px 0; font-style: italic; font-size: 11px; color: #000;">Lote não faturado.</td></tr>`;
                    }

                    // 🚀 CONSULTA A CLASSIFICAÇÃO PARA PEGAR A AVARIA (DESCARTE) REAL
                    let descarteKg = 0;
                    try {
                        const resLote = await fetch(`/sankhya/lote/consultar/?lote=${encodeURIComponent(lote)}&nunota_origem=${item.nunota}`);
                        const jsonLote = await resLote.json();
                        if (jsonLote.ok && jsonLote.resumo) {
                            descarteKg = window.ComercialUtils.toNumber(jsonLote.resumo.descarte || 0);
                        }
                    } catch (err) { console.warn("Erro ao buscar descarte", err); }

                    // 🚀 A MATEMÁTICA DA QUEBRA
                    const quebraTotalKg = inNaturaKgTotal - subTotalDistKg;
                    const diferencaKg = quebraTotalKg - descarteKg;

                    const mediaDistCx = subTotalDistCx > 0 ? (subTotalDistVlr / subTotalDistCx) : 0;
                    const mediaDistKg = subTotalDistKg > 0 ? (subTotalDistVlr / subTotalDistKg) : 0;

                    // Monta as linhas de quebra condicionalmente
                    let linhasQuebraHtml = '';
                    if (descarteKg > 0 || diferencaKg !== 0) {
                        linhasQuebraHtml += `<tr><td colspan="4" style="border-top: 1px dashed #000; padding: 0;"></td></tr>`;
                        
                        if (descarteKg > 0) {
                            linhasQuebraHtml += `
                            <tr>
                                <td colspan="2" style="padding: 4px 0 1px 0; color: #000; font-size: 11px;">↳ Descarte / Avaria:</td>
                                <td colspan="2" style="text-align: right; padding: 4px 0 1px 0; color: #000; font-weight:bold; font-size: 11px;">${descarteKg.toLocaleString('pt-BR')} kg</td>
                            </tr>`;
                        }
                        if (diferencaKg !== 0) {
                            linhasQuebraHtml += `
                            <tr>
                                <td colspan="2" style="padding: 1px 0 4px 0; color: #000; font-size: 11px;">↳ Diferença (Terra/Balança):</td>
                                <td colspan="2" style="text-align: right; padding: 1px 0 4px 0; color: #000; font-weight:bold; font-size: 11px;">${diferencaKg.toLocaleString('pt-BR')} kg</td>
                            </tr>`;
                        }
                    }

                    htmlBlocos += `
                        <div style="${separadorGrossso}">
                            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                                <span style="font-weight: 800; font-size: 13px; text-transform: uppercase; color: #000;">${produtoBase}</span>
                                <span style="font-size: 11px; color: #000;">Lote: ${lote}</span>
                            </div>

                            <table class="print-table" style="width:100%; border-collapse: collapse; margin-bottom: 0;">
                                <thead>
                                    <tr>
                                        <th style="text-align:left; padding-bottom: 2px; color: #000;">Padrão Distribuído</th>
                                        <th class="txt-right" style="padding-bottom: 2px; color: #000;">Qtd(kg)</th>
                                        <th class="txt-right" style="padding-bottom: 2px; color: #000;">Vlr/Kg</th>
                                        <th class="txt-right" style="padding-bottom: 2px; color: #000;">Subtotal</th>
                                    </tr>
                                    <tr><td colspan="4" style="border-bottom: 2px solid #000; padding: 0;"></td></tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td style="width:38%; padding: 4px 0; text-transform: uppercase; font-weight: bold; font-size: 11px; vertical-align: top; color: #000;">
                                            ↳ ENTRADA IN NATURA
                                        </td>
                                        <td style="width:20%; text-align:right; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                            <div style="margin-bottom: 2px;">${inNaturaKgTotal.toLocaleString('pt-BR')}<small>kg</small></div>
                                            <div>${qtdCaixaOrigin.toLocaleString('pt-BR', {minimumFractionDigits: 1})}<small>cx</small></div>
                                        </td>
                                        <td style="width:18%; text-align:right; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                            <div style="margin-bottom: 2px;">${precoKgOrigin.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                            <div>${precoCaixaOrigin.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                        </td>
                                        <td style="width:24%; text-align:right; font-weight:bold; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                            ${totalGeralOrigem.toLocaleString('pt-BR', {minimumFractionDigits: 2})}
                                        </td>
                                    </tr>
                                    <tr><td colspan="4" style="border-bottom: 1px dashed #000; padding: 0;"></td></tr>
                                    
                                    ${linhasDist}
                                </tbody>
                                <tfoot>
                                    ${linhasQuebraHtml}

                                    <tr><td colspan="4" style="border-top: 1px dashed #000; padding: 0;"></td></tr>
                                    
                                    <tr>
                                        <td style="width:38%; padding: 4px 0; font-weight: bold; font-size: 11px; vertical-align: top; color: #000;">
                                            ↳ RESUMO RATEIO
                                        </td>
                                        <td style="width:20%; text-align:right; font-weight: bold; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                            <div style="margin-bottom: 2px;">${subTotalDistKg.toLocaleString('pt-BR')}<small>kg</small></div>
                                            <div>${subTotalDistCx.toLocaleString('pt-BR', {minimumFractionDigits: 1})}<small>cx</small></div>
                                        </td>
                                        <td style="width:18%; text-align:right; font-weight: bold; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                            <div style="margin-bottom: 2px;">${mediaDistKg.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                            <div>${mediaDistCx.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</div>
                                        </td>
                                        <td style="width:24%; text-align:right; font-weight:bold; font-size: 11px; vertical-align: top; padding: 4px 0; color: #000;">
                                        </td>
                                    </tr>
                                    <tr><td colspan="4" style="border-top: 2px solid #000; padding: 0;"></td></tr>
                                    
                                    <tr>
                                        <td colspan="2" style="padding: 4px 0; font-size: 12px; font-weight: bold; color: #000;">Total do Vale:</td>
                                        <td colspan="2" style="text-align: right; padding: 4px 0; font-size: 13px; font-weight: 900; color: #000;">R$ ${subTotalDistVlr.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>`;
                }
            }

            area.innerHTML = `
                <div style="text-align:center;margin-bottom:10px;border-bottom:2px dashed black;padding-bottom:5px;">
                    <h3 style="margin:0;font-size:14px;color:#000;">DISTRIBUIÇÃO DO LOTE</h3>
                    <p style="margin:2px 0;font-size:11px;font-weight:bold;color:#000;">Pedido: ${notaInfo.nunota} | Vale: ${notaInfo.nunota_13 || '---'}</p>
                </div>
                <div style="margin-bottom:10px;color:#000;">
                    <p style="margin:0;font-size:12px;font-weight:bold;">Parceiro: ${notaInfo.parceiro}</p>
                    <p style="margin:2px 0 0 0;font-size:11px;">Data do Pedido: ${dataPedido}</p>
                </div>
                ${htmlBlocos}
            `;


        // ==========================================
        // LAYOUT 4: CLASSIFICAÇÃO (BALANÇO DE MASSA)
        // ==========================================
        } else if (tipoSelecionado === 'classificacao') {
            rodapeMensagem = 'BALANÇO OPERACIONAL';
            area.innerHTML = `<div style="text-align: center; margin-top: 40px; color: #64748b;">Consultando a esteira de produção...</div>`;
            
            let htmlBlocos = '';
            const itensClassificaveis = valeAtual.filter(item => item.geraproducao === 'S');

            if (itensClassificaveis.length === 0) {
                htmlBlocos = `<div style="text-align: center; margin-top: 30px; font-weight: bold; color: #ef4444;">Nenhum produto classificável neste vale.</div>`;
            } else {
                for (let i = 0; i < itensClassificaveis.length; i++) {
                    const item = itensClassificaveis[i];
                    const produtoBase = (item.fabricante || item.produto || '---').trim();
                    const lote = item.codagregacao;
                    const pesoCxEntrada = window.ComercialUtils.toNumber(item.qtdfixada || 20);
                    const volS = (item.codvolparc || item.codvol || 'CX').toLowerCase();

                    try {
                        const url = `/sankhya/lote/consultar/?lote=${encodeURIComponent(lote)}&nunota_origem=${item.nunota}`;
                        const res = await fetch(url);
                        const data = await res.json();
                        
                        if (!data.ok) throw new Error(data.error);

                        const resumo = data.resumo || {};
                        const classificacoes = data.classificacoes || [];

                        const inNaturaKg = window.ComercialUtils.toNumber(resumo.in_natura || 0);
                        const inNaturaCx = window.ComercialUtils.toNumber(item.qtdconferida || 0);
                        const descarteKg = window.ComercialUtils.toNumber(resumo.descarte || 0);
                        
                        const apenasBomKg = classificacoes.reduce((acc, curr) => acc + window.ComercialUtils.toNumber(curr.qtd || 0), 0);
                        const baseTotalParaPct = inNaturaKg > 0 ? inNaturaKg : (apenasBomKg + descarteKg); 

                        let linhasTabela = '';
                        
                        if (classificacoes.length === 0 && descarteKg === 0) {
                            linhasTabela = `<tr><td colspan="4" style="text-align:center; padding: 10px 0; font-style: italic; font-size: 11px; color: #ef4444;">Sem classificação realizada no sistema</td></tr>`;
                        } else {
                            linhasTabela += `
                                <tr>
                                    <td style="width:38%; padding: 4px 2px; text-transform: uppercase; font-weight: 800;">${produtoBase} IN NATURA</td>
                                    <td style="width:22%; text-align:right; font-weight: bold;">${Math.round(inNaturaKg).toLocaleString('pt-BR')}<small>kg</small></td>
                                    <td style="width:20%; text-align:right; font-weight: bold;">100,0<small>%</small></td>
                                    <td style="width:20%; text-align:right; font-weight: bold;">${inNaturaCx.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1})}<small>${volS}</small></td>
                                </tr>`;

                            const agrupados = classificacoes.reduce((acc, curr) => {
                                const nome = curr.descr || 'Outros';
                                if (!acc[nome]) acc[nome] = { nome: nome, total: 0 };
                                acc[nome].total += window.ComercialUtils.toNumber(curr.qtd || 0);
                                return acc;
                            }, {});

                            const listaOrdenada = Object.values(agrupados).sort((a, b) => {
                                const aUp = a.nome.toUpperCase();
                                const bUp = b.nome.toUpperCase();
                                if (aUp.includes('EXTRA') && !bUp.includes('EXTRA')) return -1;
                                if (!aUp.includes('EXTRA') && bUp.includes('EXTRA')) return 1;
                                if (aUp.includes('MÉDIO') || aUp.includes('MEDIO')) { if (!bUp.includes('MÉDIO') && !bUp.includes('MEDIO')) return -1; }
                                if (bUp.includes('MÉDIO') || bUp.includes('MEDIO')) { if (!aUp.includes('MÉDIO') && !aUp.includes('MEDIO')) return 1; }
                                return 0;
                            });

                            listaOrdenada.forEach(it => {
                                const pct = baseTotalParaPct > 0 ? (it.total / baseTotalParaPct * 100) : 0;
                                const qtdCxIt = pesoCxEntrada > 0 ? (it.total / pesoCxEntrada) : 0;

                                linhasTabela += `
                                    <tr>
                                        <td style="width:38%; padding: 4px 2px 4px 12px; text-transform: uppercase; color:#334155;">↳ ${window.ComercialUtils.escapeHTML(it.nome)}</td>
                                        <td style="width:22%; text-align:right;">${Math.round(it.total).toLocaleString('pt-BR')}<small>kg</small></td>
                                        <td style="width:20%; text-align:right;">${pct.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits:1})}<small>%</small></td>
                                        <td style="width:20%; text-align:right; font-weight:bold;">${qtdCxIt.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1})}<small>${volS}</small></td>
                                    </tr>`;
                            });

                            if (descarteKg > 0) {
                                const pctAvaria = baseTotalParaPct > 0 ? (descarteKg / baseTotalParaPct * 100) : 0;
                                const qtdCxAvaria = pesoCxEntrada > 0 ? (descarteKg / pesoCxEntrada) : 0;
                                linhasTabela += `
                                    <tr>
                                        <td style="width:38%; padding: 4px 2px 4px 12px; font-weight: bold; color: #dc2626;">↳ DESCARTE / AVARIA</td>
                                        <td style="width:22%; text-align:right; font-weight: bold; color: #dc2626;">${Math.round(descarteKg).toLocaleString('pt-BR')}<small>kg</small></td>
                                        <td style="width:20%; text-align:right; font-weight: bold; color: #dc2626;">${pctAvaria.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits:1})}<small>%</small></td>
                                        <td style="width:20%; text-align:right; font-weight: bold; color: #dc2626;">${qtdCxAvaria.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1})}<small>${volS}</small></td>
                                    </tr>`;
                            }
                        }

                        const aproveitadoPct = baseTotalParaPct > 0 ? (apenasBomKg / baseTotalParaPct * 100) : 0;
                        const separadorGrossso = i > 0 ? 'margin-top: 10px; border-top: 5px solid #000; padding-top: 10px;' : '';

                        htmlBlocos += `
                            <div style="${separadorGrossso}">
                                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                                    <span style="font-weight: 800; font-size: 13px; text-transform: uppercase;">${produtoBase}</span>
                                    <span style="font-size: 9px; color: #64748b;">Lote: ${lote}</span>
                                </div>
                                <table class="print-table" style="width:100%; border-collapse: collapse; margin-bottom: 0;">
                                    <thead>
                                        <tr>
                                            <th style="text-align:left; padding-bottom: 4px;">Padrão</th>
                                            <th class="txt-right" style="padding-bottom: 4px;">Peso</th>
                                            <th class="txt-right" style="padding-bottom: 4px;">(%)</th>
                                            <th class="txt-right" style="padding-bottom: 4px;">Volume</th>
                                        </tr>
                                        <tr><td colspan="4" style="border-bottom: 2px dashed #000; padding: 0;"></td></tr>
                                    </thead>
                                    <tbody>
                                        ${linhasTabela}
                                    </tbody>
                                    <tfoot>
                                        <tr><td colspan="4" style="border-top: 2px dashed #000; padding: 0;"></td></tr>
                                        <tr>
                                            <td colspan="2" style="padding: 6px 0 2px 0; font-size: 11px;">Entrada Bruta:</td>
                                            <td colspan="2" style="text-align: right; padding: 6px 0 2px 0; font-size: 11px; font-weight: bold;">${Math.round(inNaturaKg).toLocaleString('pt-BR')} kg</td>
                                        </tr>
                                        <tr>
                                            <td colspan="2" style="padding: 2px 0 6px 0; font-size: 11px;">Total Aproveitado:</td>
                                            <td colspan="2" style="text-align: right; padding: 2px 0 6px 0; font-size: 11px; font-weight: bold;">
                                                <span style="color:#475569; font-weight:normal; margin-right: 4px;">(${aproveitadoPct.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1})}%)</span>
                                                ${Math.round(apenasBomKg).toLocaleString('pt-BR')} kg 
                                            </td>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        `;
                    } catch(e) {
                        htmlBlocos += `<div style="margin-top: 15px; color: #ef4444; font-size: 11px; text-align: center;">Erro ao carregar lote ${lote}</div>`;
                    }
                }
            }

            area.innerHTML = `
                <div style="text-align:center;margin-bottom:10px;border-bottom:2px dashed black;padding-bottom:5px;">
                    <h3 style="margin:0;font-size:14px;">RELATÓRIO DE CLASSIFICAÇÃO</h3>
                    <p style="margin:2px 0;font-size:11px;font-weight:bold;">Pedido: ${notaInfo.nunota} | Vale: ${notaInfo.nunota_13 || '---'}</p>
                </div>
                <div style="margin-bottom:10px;">
                    <p style="margin:0;font-size:12px;font-weight:bold;">Parceiro: ${notaInfo.parceiro}</p>
                    <p style="margin:2px 0 0 0;font-size:11px;">Data do Pedido: ${dataPedido}</p>
                </div>
                ${htmlBlocos}
            `;

        }

        // Rodapé comum a todos (com a frase variável)
        area.innerHTML += `
            <div style="margin-top:40px;text-align:center;">
                <div style="border-top:1px solid black;width:85%;margin:0 auto;padding-top:5px;font-size:10px;margin-bottom:15px;">Assinatura do Parceiro</div>
                <p style="font-size:12px;font-weight:bold;margin:4px 0;">${rodapeMensagem}</p>
                
                <p style="font-size:11px; font-style:italic; font-weight:bold; margin:12px 0; padding:0 5px; line-height:1.3;">
                    "Tenha paciência e continue firme.<br>Entre a plantação e a colheita,<br>é obrigatório o crescimento!!!"
                </p>
                
                <p style="font-size:9px; margin: 4px 0 0 0;">Emitido em ${dataHj}</p>
            </div>
            
            <style>
                #printContentArea * {
                    font-family: monospace !important;
                    color: #000 !important;
                }
            </style>
        `;
    };

    // 🚀 IMPRESSÃO ISOLADA VIA IFRAME (À PROVA DE FALHAS PARA BOBINA 80MM)
    const imprimir = () => {
        const area = document.getElementById('printContentArea');
        if (!area || area.innerHTML.trim() === '') return window.ComercialUtils.mostrarToast('Nada para imprimir.', 'erro');

        // 1. Cria o Iframe invisível
        const iframe = document.createElement('iframe');
        iframe.style.position = 'fixed';
        iframe.style.right = '0';
        iframe.style.bottom = '0';
        iframe.style.width = '0';
        iframe.style.height = '0';
        iframe.style.border = 'none';
        document.body.appendChild(iframe);

        // 2. Prepara o documento interno com o CSS exato da bobina térmica
        // 2. Prepara o documento interno com o CSS exato da bobina térmica
        const doc = iframe.contentWindow.document;
        doc.open();
        doc.write(`
            <html>
            <head>
                <title>Impressão Agromil</title>
                <style>
                    @page { margin: 0; size: 80mm auto; }
                    
                    /* 🚀 A MÁGICA NO PAPEL: Força fonte e cor em TUDO */
                    * { 
                        font-family: monospace !important; 
                        color: #000 !important; 
                    }
                    
                    body { 
                        font-size: 12px; 
                        margin: 0; padding: 4mm 2mm; width: 76mm; 
                    }
                    table { width: 100%; border-collapse: collapse; }
                    th { border-top: 1px dashed #000; border-bottom: 1px dashed #000; padding: 4px 0; text-align: left; font-size: 11px; font-weight: bold; }
                    td { padding: 4px 0; font-size: 11px; border-bottom: 1px dotted #ccc; }
                    .txt-right { text-align: right; }
                </style>
            </head>
            <body>
                ${area.innerHTML}
            </body>
            </html>
        `);
        doc.close();

        // 3. Aguarda renderizar e chama a impressão do Iframe
        iframe.contentWindow.focus();
        setTimeout(() => {
            iframe.contentWindow.print();
            setTimeout(() => document.body.removeChild(iframe), 500); // Limpa o iframe depois
        }, 250);
    };

    return { abrir, fechar, renderizarPreview, imprimir };
})();