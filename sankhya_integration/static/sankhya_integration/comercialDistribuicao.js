window.ComercialDistribuicao = (function() {
    let DOM = {};
    let STATE = { nunotaOrigem: null, lote: null, pesos: null, qtdconferida: 0 }; 
    let isSimulacaoEventsBound = false; 

    const fmtBRL = (v) => window.ComercialUtils.toNumber(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const fmtPct = (v) => window.ComercialUtils.toNumber(v).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + '%';
    const fmtInt = (v) => Math.round(window.ComercialUtils.toNumber(v) || 0).toLocaleString('pt-BR');

    const initDOM = () => {
        DOM = {
            margemTotal: document.getElementById('distMargemTotal'),
            lucroAbsoluto: document.getElementById('distLucroAbsoluto'),
            totalKg: document.getElementById('distTotalKg'),
            totalCx: document.getElementById('distTotalCx'),
            custoKg: document.getElementById('distCustoKg'), 
            custoCx: document.getElementById('distCustoCx'), 
            vlrTotCompra: document.getElementById('distVlrTotCompra'),
            extraCusto: document.getElementById('extraCustoUnit'),
            extraVenda: document.getElementById('extraTicketVenda'),
            extraMargem: document.getElementById('extraMargemPct'),
            medioCusto: document.getElementById('medioCustoUnit'),
            medioVenda: document.getElementById('medioTicketVenda'),
            medioMargem: document.getElementById('medioMargemPct'),
            nomeParceiro: document.getElementById('distNomeParceiro'),
            nomeProduto: document.getElementById('distNomeProduto')
        };
    };

    const bindSimulacaoEvents = () => {
        if (isSimulacaoEventsBound) return;

        const exQty = document.getElementById('sim-extra-qty');
        const exUnit = document.getElementById('sim-extra-unit');
        const mdQty = document.getElementById('sim-medio-qty');
        const mdUnit = document.getElementById('sim-medio-unit');
        const quebraInp = document.getElementById('sim-quebra-input');
        
        const btnClear = document.getElementById('sim-btn-clear');
        const btnApply = document.getElementById('sim-btn-apply');
        const toggleAuto = document.getElementById('sim-toggle-auto');

        if (!exQty) return;

        // 🚀 O CÉREBRO FINANCEIRO (Roda sempre)
        const recalcular = () => {
            const qEx = window.ComercialUtils.toNumber(exQty.value || 0);
            const vEx = window.ComercialUtils.toNumber(exUnit.value || 0);
            const qMd = window.ComercialUtils.toNumber(mdQty.value || 0);
            const vMd = window.ComercialUtils.toNumber(mdUnit.value || 0);
            const qQb = window.ComercialUtils.toNumber(quebraInp.value || 0);

            const totEx = qEx * vEx;
            const totMd = qMd * vMd;
            const totGeral = totEx + totMd;
            const somaCx = qEx + qMd + qQb; 

            const elExTot = document.getElementById('sim-extra-total');
            const elMdTot = document.getElementById('sim-medio-total');
            const elGerTot = document.getElementById('sim-total-geral');
            const elSomaCx = document.getElementById('sim-soma-cx');

            if (elExTot) elExTot.textContent = fmtBRL(totEx);
            if (elMdTot) elMdTot.textContent = fmtBRL(totMd);
            if (elGerTot) elGerTot.textContent = fmtBRL(totGeral);
            
            if (elSomaCx) {
                elSomaCx.textContent = Math.round(somaCx).toString() + ' cx';
                // 🎨 UX: Se estiver fora do automático e a soma passar do total da nota, avisa em vermelho!
                if (somaCx > STATE.qtdconferida) {
                    elSomaCx.style.color = '#dc2626'; // Vermelho alerta
                } else {
                    elSomaCx.style.color = '#475569'; // Cor normal
                }
            }
        };

        // 🚀 O VERIFICADOR DA CHAVE
        const isAutoBalanceEnabled = () => {
            const t = document.getElementById('sim-toggle-auto');
            return t ? t.checked : true;
        };

        if (toggleAuto) {
            toggleAuto.addEventListener('change', async (e) => {
                const isChecked = e.target.checked;
                
                // 🚀 MÁGICA: Se religou a chave, força o recalculo usando o Extra como base
                if (isChecked) {
                    exQty.dispatchEvent(new Event('input'));
                }

                // 💾 Salvamento silencioso no banco (Mantém a escolha salva sem precisar clicar em Aplicar)
                if (!STATE.nunotaOrigem || !STATE.lote) return;
                try {
                    const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
                    await fetch('/sankhya/comercial/api/salvar-simulacao/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({
                            nunota: STATE.nunotaOrigem, 
                            lote: STATE.lote, 
                            sim_data: { 
                                q1: window.ComercialUtils.toNumber(exQty.value) || null, 
                                v1: window.ComercialUtils.toNumber(exUnit.value) || null, 
                                q2: window.ComercialUtils.toNumber(mdQty.value) || null, 
                                v2: window.ComercialUtils.toNumber(mdUnit.value) || null, 
                                desc: window.ComercialUtils.toNumber(quebraInp.value) || null,
                                auto: isChecked ? 'S' : 'N'
                            }
                        })
                    });
                    
                    // Atualiza a memória da tela para a próxima leitura
                    const linhaSelecionada = document.querySelector('tr.lista-item-row.row--sel');
                    if (linhaSelecionada && window.__COM_LIST_ROWS) {
                        window.__COM_LIST_ROWS[linhaSelecionada.dataset.idx].ad_simauto = isChecked ? 'S' : 'N';
                    }
                } catch(err) { console.error('Erro ao salvar estado do AUTO:', err); }
            });
        }

        // ⚖️ CASCATA 1: Extra
        exQty.addEventListener('input', () => {
            if (isAutoBalanceEnabled()) {
                const inNaturaCx = STATE.qtdconferida;
                let currentQuebra = window.ComercialUtils.toNumber(quebraInp.value || 0);
                let ex = window.ComercialUtils.toNumber(exQty.value || 0);
                
                // Trava para não estourar o Teto
                if (ex + currentQuebra > inNaturaCx) {
                    ex = inNaturaCx - currentQuebra;
                    exQty.value = Math.round(ex).toString();
                }
                
                const md = inNaturaCx - ex - currentQuebra;
                mdQty.value = Math.max(0, Math.round(md)).toString();
            }
            recalcular();
        });

        // ⚖️ CASCATA 2: Médio
        mdQty.addEventListener('input', () => {
            if (isAutoBalanceEnabled()) {
                const inNaturaCx = STATE.qtdconferida;
                let currentQuebra = window.ComercialUtils.toNumber(quebraInp.value || 0);
                let md = window.ComercialUtils.toNumber(mdQty.value || 0);

                if (md + currentQuebra > inNaturaCx) {
                    md = inNaturaCx - currentQuebra;
                    mdQty.value = Math.round(md).toString();
                }

                const ex = inNaturaCx - md - currentQuebra;
                exQty.value = Math.max(0, Math.round(ex)).toString();
            }
            recalcular();
        });

        // ⚖️ CASCATA 3: Quebra
        quebraInp.addEventListener('input', () => {
            if (isAutoBalanceEnabled()) {
                const inNaturaCx = STATE.qtdconferida;
                let currentQuebra = window.ComercialUtils.toNumber(quebraInp.value || 0);
                
                if (currentQuebra > inNaturaCx) {
                    currentQuebra = inNaturaCx;
                    quebraInp.value = Math.round(currentQuebra).toString();
                }
                
                const md = window.ComercialUtils.toNumber(mdQty.value || 0);
                let ex = inNaturaCx - md - currentQuebra;
                
                // Prioridade de desconto é o Extra. Se zerar, tira do Médio.
                if (ex < 0) {
                    ex = 0;
                    const mdAjustado = inNaturaCx - currentQuebra;
                    mdQty.value = Math.max(0, Math.round(mdAjustado)).toString();
                }
                exQty.value = Math.max(0, Math.round(ex)).toString();
            }
            recalcular();
        });

        // 💰 Formatação de Dinheiro
        [exUnit, mdUnit].forEach(el => { 
            if (el) {
                el.addEventListener('input', recalcular);
                el.addEventListener('blur', function() {
                    const val = window.ComercialUtils.toNumber(this.value);
                    if (val > 0) this.value = val.toFixed(2).replace('.', ',');
                });
            }
        });

        // Mai/2026 — Auto-select on focus agora vem do IAgro.installAutoSelect
        // global (base.html). Removida a duplicação local. Esses campos seguem
        // tendo o comportamento sem código adicional aqui.

        // 💾 Botão APLICAR
        if (btnApply) {
            btnApply.onclick = async () => {
                if (!STATE.nunotaOrigem || !STATE.lote) {
                    window.ComercialUtils.mostrarToast('Nenhum lote selecionado.', 'erro');
                    return;
                }

                const qEx = window.ComercialUtils.toNumber(exQty.value || 0);
                const vEx = window.ComercialUtils.toNumber(exUnit.value || 0);
                const qMd = window.ComercialUtils.toNumber(mdQty.value || 0);
                const vMd = window.ComercialUtils.toNumber(mdUnit.value || 0);
                const qQb = window.ComercialUtils.toNumber(quebraInp.value || 0);
                const isAuto = toggleAuto ? (toggleAuto.checked ? 'S' : 'N') : 'S';
                const totGeral = (qEx * vEx) + (qMd * vMd);

                btnApply.textContent = 'Salvando...';
                btnApply.disabled = true;

                try {
                    const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
                    const res = await fetch('/sankhya/comercial/api/salvar-simulacao/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ 
                            nunota: STATE.nunotaOrigem, 
                            lote: STATE.lote, 
                            sim_data: { q1: qEx, v1: vEx, q2: qMd, v2: vMd, desc: qQb, auto: isAuto } 
                        })
                    });
                    
                    const data = await res.json();
                    if (!data.ok) throw new Error(data.error);

                    window.ComercialUtils.mostrarToast('Simulação salva no banco e aplicada!', 'sucesso');
                    
                    const linhaSelecionada = document.querySelector('tr.lista-item-row.row--sel');
                    if (linhaSelecionada && window.__COM_LIST_ROWS) {
                        const idx = linhaSelecionada.dataset.idx;
                        const dadosDaLinha = window.__COM_LIST_ROWS[idx];
                        
                        dadosDaLinha.ad_simqtd1 = qEx > 0 ? qEx : null;
                        dadosDaLinha.ad_simvlr1 = vEx > 0 ? vEx : null;
                        dadosDaLinha.ad_simqtd2 = qMd > 0 ? qMd : null;
                        dadosDaLinha.ad_simvlr2 = vMd > 0 ? vMd : null;
                        dadosDaLinha.ad_simqtddesc = qQb > 0 ? qQb : null;
                        dadosDaLinha.ad_simauto = isAuto;

                        dadosDaLinha.vlrtot_simulado = totGeral;
                        dadosDaLinha.vlrtot_simulado_base = dadosDaLinha.vlrtot;
                        if (vEx > 0) dadosDaLinha.ratio_medio = vMd / vEx;
                        else dadosDaLinha.ratio_medio = 0.5;
                        
                        preencher(dadosDaLinha, STATE.pesos, true);
                    }
                } catch (e) {
                    window.ComercialUtils.mostrarToast('Erro ao aplicar: ' + e.message, 'erro');
                } finally {
                    btnApply.textContent = 'Aplicar';
                    btnApply.disabled = false;
                }
            };
        }

        // 🗑️ Botão LIMPAR
        if (btnClear) {
            btnClear.onclick = async () => {
                if (!STATE.nunotaOrigem || !STATE.lote) return;

                btnClear.textContent = 'Limpando...';
                btnClear.disabled = true;

                try {
                    const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
                    const res = await fetch('/sankhya/comercial/api/salvar-simulacao/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ 
                            nunota: STATE.nunotaOrigem, 
                            lote: STATE.lote, 
                            sim_data: { q1: null, v1: null, q2: null, v2: null, desc: null, auto: 'S' } 
                        })
                    });
                    
                    const data = await res.json();
                    if (!data.ok) throw new Error(data.error);

                    [exQty, exUnit, mdQty, mdUnit].forEach(el => { if (el) el.value = ''; });
                    if (toggleAuto) toggleAuto.checked = true; 
                    
                    const elAvaria = document.getElementById('resInservCx');
                    const avariaCx = window.ComercialUtils.toNumber(elAvaria ? elAvaria.textContent : 0);
                    quebraInp.value = avariaCx > 0 ? Math.round(avariaCx).toString() : '';
                    
                    recalcular();
                    window.ComercialUtils.mostrarToast('Dados de simulação excluídos!', 'sucesso');
                    
                    const linhaSelecionada = document.querySelector('tr.lista-item-row.row--sel');
                    if (linhaSelecionada && window.__COM_LIST_ROWS) {
                        const idx = linhaSelecionada.dataset.idx;
                        const dadosDaLinha = window.__COM_LIST_ROWS[idx];
                        
                        dadosDaLinha.ad_simqtd1 = null;
                        dadosDaLinha.ad_simvlr1 = null;
                        dadosDaLinha.ad_simqtd2 = null;
                        dadosDaLinha.ad_simvlr2 = null;
                        dadosDaLinha.ad_simqtddesc = null;
                        dadosDaLinha.ad_simauto = 'S'; 
                        delete dadosDaLinha.vlrtot_simulado;
                        delete dadosDaLinha.vlrtot_simulado_base;
                    }
                } catch (e) {
                    window.ComercialUtils.mostrarToast('Erro ao limpar: ' + e.message, 'erro');
                } finally {
                    btnClear.textContent = 'Limpar';
                    btnClear.disabled = false;
                }
            };
        }

        isSimulacaoEventsBound = true;
    };

    const preencher = async (dadosDaLinha, pesos, isSimulacao = false) => {
        if (!isSimulacao) {
            delete dadosDaLinha.vlrtot_simulado;
            delete dadosDaLinha.vlrtot_simulado_base;
            delete dadosDaLinha.ratio_medio; 
            
            const exQty = document.getElementById('sim-extra-qty');
            if (exQty) {
                document.getElementById('sim-extra-qty').value = '';
                document.getElementById('sim-extra-unit').value = '';
                document.getElementById('sim-medio-qty').value = '';
                document.getElementById('sim-medio-unit').value = '';
                document.getElementById('sim-extra-total').textContent = 'R$ 0,00';
                document.getElementById('sim-medio-total').textContent = 'R$ 0,00';
                document.getElementById('sim-total-geral').textContent = 'R$ 0,00';
            }
        }

        if (STATE.lote && STATE.lote !== dadosDaLinha.codagregacao) {
            STATE.pesos = null;
            const tagEx = document.querySelector('#distMiniExtra .class-tag');
            const tagMd = document.querySelector('#distMiniMedio .class-tag');
            if (tagEx) tagEx.textContent = 'EXTRA';
            if (tagMd) tagMd.textContent = 'MÉDIO';
        }

        initDOM();
        STATE.nunotaOrigem = dadosDaLinha.nunota;
        STATE.lote = dadosDaLinha.codagregacao;
        STATE.qtdconferida = window.ComercialUtils.toNumber(dadosDaLinha.qtdconferida || 0); 
        if (DOM.nomeParceiro) {
            DOM.nomeParceiro.textContent = dadosDaLinha.parceiro || 'Não informado';
            DOM.nomeParceiro.title = dadosDaLinha.parceiro || ''; 
        }
        if (DOM.nomeProduto) {
            const nomeProd = dadosDaLinha.fabricante || dadosDaLinha.produto || 'Não informado';
            DOM.nomeProduto.textContent = nomeProd;
            DOM.nomeProduto.title = nomeProd; 
        }
        
        const isFaturado = window.ComercialUtils.toNumber(dadosDaLinha.nufin) > 0;
        const temVale = window.ComercialUtils.toNumber(dadosDaLinha.nunota_13) > 0;
        
        const badgeDist = document.getElementById('badgeFaturadoDist');
        
        // Pegamos os botões individualmente para ter controle total sobre eles
        const btnSalvar = document.getElementById('btnDistSalvar');
        const btnZerar = document.getElementById('btnDistZerar');
        const btnDesmembrar = document.getElementById('btnDistDesmembrar');

        // 🚀 1. LÓGICA DO BOTÃO MOVIMENTAR LOTE (Substitui o antigo Desmembrar direto)
        // DICA: No seu HTML, procure o <button id="btnDistDesmembrar"> e mude o texto dele para "Movimentar Lote"
        if (btnDesmembrar) {
            if (STATE.nunotaOrigem) {
                btnDesmembrar.style.display = 'inline-block';
                if (temVale) {
                    btnDesmembrar.disabled = true;
                    btnDesmembrar.textContent = 'VALE SALVO';
                    btnDesmembrar.style.opacity = '0.6';
                    btnDesmembrar.style.cursor = 'not-allowed';
                    btnDesmembrar.title = 'Para movimentar, clique primeiro em "Zerar Negociação".';
                } else {
                    btnDesmembrar.disabled = false;
                    btnDesmembrar.textContent = 'Movimentar Lote'; // <-- Novo Nome!
                    btnDesmembrar.style.opacity = '1';
                    btnDesmembrar.style.cursor = 'pointer';
                    btnDesmembrar.title = 'Desmembrar para outro pedido ou Unificar';
                }
            } else {
                btnDesmembrar.style.display = 'none';
            }
            
            // Abre o Modal ao invés de fazer direto
            btnDesmembrar.onclick = () => window.ComercialDistribuicao.abrirModalMovimentacao(dadosDaLinha);
        }

        // 🚀 2. LÓGICA DO BOTÃO SALVAR (Texto Dinâmico)
        if (btnSalvar) {
            if (temVale) {
                btnSalvar.textContent = 'VALE SALVO';
                // Opcional: se quiser mudar a cor dele quando salvar, descomente a linha abaixo:
                // btnSalvar.style.backgroundColor = '#16a34a'; 
            } else {
                btnSalvar.textContent = 'Salvar';
                // btnSalvar.style.backgroundColor = ''; // Restaura a cor padrão
            }
        }

        // 🚀 3. LÓGICA DE TRAVAS (Faturado / Pago)
        if (isFaturado) {
            document.body.classList.add('vale-faturado');
            if (badgeDist) badgeDist.style.display = 'flex';
            
            const isPago = window.ComercialUtils.toNumber(dadosDaLinha.qtd_baixados) > 0;

            if (btnSalvar) {
                btnSalvar.disabled = true;
                btnSalvar.style.opacity = '0.5';
                btnSalvar.style.cursor = 'not-allowed';
            }
            if (btnZerar) {
                if (isPago) {
                    btnZerar.disabled = true;
                    btnZerar.style.opacity = '0.5';
                    btnZerar.style.cursor = 'not-allowed';
                    btnZerar.title = "Não é possível desfaturar: Título pago.";
                } else {
                    btnZerar.disabled = false;
                    btnZerar.style.opacity = '1';
                    btnZerar.style.cursor = 'pointer';
                    btnZerar.title = "";
                }
            }
        } else {
            document.body.classList.remove('vale-faturado');
            if (badgeDist) badgeDist.style.display = 'none';
            
            if (btnSalvar) {
                btnSalvar.disabled = false;
                btnSalvar.style.opacity = '1';
                btnSalvar.style.cursor = 'pointer';
            }
            if (btnZerar) {
                btnZerar.disabled = false;
                btnZerar.style.opacity = '1';
                btnZerar.style.cursor = 'pointer';
            }
        }

        STATE.pesos = pesos || STATE.pesos || { extraKg: 0, medioKg: 0, extraCodProd: null, medioCodProd: null }; 

        const tagExtra = document.querySelector('#distMiniExtra .class-tag');
        const tagMedio = document.querySelector('#distMiniMedio .class-tag');
        if (tagExtra) tagExtra.textContent = STATE.pesos.extraCodProd ? `EXTRA - ${STATE.pesos.extraCodProd}` : 'EXTRA';
        if (tagMedio) tagMedio.textContent = STATE.pesos.medioCodProd ? `MÉDIO - ${STATE.pesos.medioCodProd}` : 'MÉDIO';

        let itensFaturados = null;
        if (dadosDaLinha.nunota_13) {
            try {
                const resVale = await fetch(`/sankhya/comercial/api/detalhes-vale/?nunota_13=${dadosDaLinha.nunota_13}&lote=${dadosDaLinha.codagregacao}`);
                const jsonVale = await resVale.json();
                if (jsonVale.ok && jsonVale.itens && jsonVale.itens.length > 0) {
                    itensFaturados = jsonVale.itens;
                }
            } catch (e) { console.warn("Erro ao buscar detalhes", e); }
        }

        const pesoCx = window.ComercialUtils.toNumber(dadosDaLinha.qtdfixada || 20);

        let kgExtra = 0, custoExtraKg = 0, totalCustoExtra = 0;
        let kgMedio = 0, custoMedioKg = 0, totalCustoMedio = 0;
        let vlrTotal = 0;

        const temSimulacaoAtiva = dadosDaLinha.vlrtot_simulado !== undefined;

        if (itensFaturados && !temSimulacaoAtiva) {
            const ehInNaturaPuro = itensFaturados.length === 1 && Number(itensFaturados[0].selecionado) === 0;

            if (ehInNaturaPuro) {
                kgExtra = itensFaturados[0].qtdneg;
                custoExtraKg = itensFaturados[0].vlrunit;
                totalCustoExtra = itensFaturados[0].vlrtot;
            } else {
                let sumExtraKg = 0, sumExtraTot = 0;
                let sumMedioKg = 0, sumMedioTot = 0;

                itensFaturados.forEach(it => {
                    const sel = Number(it.selecionado);
                    const qtd = window.ComercialUtils.toNumber(it.qtdneg);
                    const tot = window.ComercialUtils.toNumber(it.vlrtot);

                    if (sel === 1) {
                        sumExtraKg += qtd;
                        sumExtraTot += tot;
                    } 
                    else if (sel !== 0) {
                        sumMedioKg += qtd;
                        sumMedioTot += tot;
                    }
                });

                kgExtra = sumExtraKg;
                totalCustoExtra = sumExtraTot;
                custoExtraKg = kgExtra > 0 ? (totalCustoExtra / kgExtra) : 0;

                kgMedio = sumMedioKg;
                totalCustoMedio = sumMedioTot;
                custoMedioKg = kgMedio > 0 ? (totalCustoMedio / kgMedio) : 0;
            }

            vlrTotal = totalCustoExtra + totalCustoMedio;
        } else {
            if (dadosDaLinha.vlrtot_simulado_base && dadosDaLinha.vlrtot !== dadosDaLinha.vlrtot_simulado_base) {
                delete dadosDaLinha.vlrtot_simulado;
                delete dadosDaLinha.vlrtot_simulado_base;
                delete dadosDaLinha.ratio_medio;
            }

            vlrTotal = window.ComercialUtils.toNumber(dadosDaLinha.vlrtot_simulado ?? dadosDaLinha.vlrtot ?? 0);
            
            kgExtra = window.ComercialUtils.toNumber(STATE.pesos.extraKg || 0);
            kgMedio = window.ComercialUtils.toNumber(STATE.pesos.medioKg || 0);
            
            if (kgExtra === 0 && kgMedio === 0 && dadosDaLinha.geraproducao !== 'S') {
                const qtdConf = window.ComercialUtils.pickFirstPositive(dadosDaLinha.qtdconferida, dadosDaLinha.qtdneg) || 0;
                const pesoIn = window.ComercialUtils.toNumber(dadosDaLinha.peso || 0);
                kgExtra = qtdConf * (pesoIn > 0 ? pesoIn : 1); 
            }

            const fatorMedio = dadosDaLinha.ratio_medio ?? 0.5;
            
            const pesoFinExtra = kgExtra;
            const pesoFinMedio = kgMedio * fatorMedio;
            const divisorPonderado = pesoFinExtra + pesoFinMedio;
            
            if (divisorPonderado > 0) {
                const calcTotalMedio = (pesoFinMedio / divisorPonderado) * vlrTotal;
                totalCustoMedio = parseFloat(calcTotalMedio.toFixed(2));
                totalCustoExtra = parseFloat((vlrTotal - totalCustoMedio).toFixed(2));
                custoExtraKg = kgExtra > 0 ? (totalCustoExtra / kgExtra) : 0;
                custoMedioKg = kgMedio > 0 ? (totalCustoMedio / kgMedio) : 0;
            } else {
                totalCustoExtra = 0; totalCustoMedio = 0;
                custoExtraKg = 0; custoMedioKg = 0;
            }
        }

        const kgTotalLote = kgExtra + kgMedio;
        const cxTotalLote = kgTotalLote > 0 ? (kgTotalLote / pesoCx) : 0;
        const custoGeralKg = kgTotalLote > 0 ? (vlrTotal / kgTotalLote) : 0;

        const volOrigem = (dadosDaLinha.codvol || 'cx').toLowerCase();
        const ehInNatura = (dadosDaLinha.geraproducao !== 'S');
        const tagFinal = ehInNatura ? volOrigem : 'cx';
        const isVolumeUnico = !['cx', 'sc'].includes(volOrigem);

        if (DOM.vlrTotCompra) {
            DOM.vlrTotCompra.textContent = fmtBRL(vlrTotal);
            DOM.vlrTotCompra.style.color = ''; 
            DOM.vlrTotCompra.style.borderBottom = 'none'; 
            DOM.vlrTotCompra.style.cursor = 'pointer';
            DOM.vlrTotCompra.title = 'Clique para alterar o Valor Total na tela';

            DOM.vlrTotCompra.onclick = function() {
                if (this.parentNode.querySelector('.input-simulacao-total')) return;

                const input = document.createElement('input');
                input.type = 'text';
                input.className = 'input-simulacao-total';
                input.value = vlrTotal.toFixed(2).replace('.', ',');
                input.style.cssText = 'width: 140px; text-align: center; font-size: 1.25rem; font-weight: 900; color: #1e293b; border: 2px solid #cbd5e1; border-radius: 6px; padding: 2px 4px; outline: none; background: #fff; margin-top: -4px;';
                
                this.style.display = 'none';
                this.parentNode.insertBefore(input, this.nextSibling);
                input.focus();
                input.select();

                const finalizar = () => {
                    let novoVal = window.ComercialUtils.toNumber(input.value);
                    let limpou = false;

                    if (isNaN(novoVal) || novoVal <= 0) {
                        novoVal = window.ComercialUtils.toNumber(dadosDaLinha.vlrtot);
                        delete dadosDaLinha.vlrtot_simulado;
                        delete dadosDaLinha.vlrtot_simulado_base;
                        limpou = true;
                    }
                    
                    input.remove();
                    this.style.display = '';

                    if (novoVal !== vlrTotal || limpou) {
                        delete dadosDaLinha.ratio_medio; 
                        if (!limpou) {
                            dadosDaLinha.vlrtot_simulado = novoVal;
                            dadosDaLinha.vlrtot_simulado_base = dadosDaLinha.vlrtot; 
                        } 
                        preencher(dadosDaLinha, STATE.pesos, true);
                    }
                };

                input.onblur = finalizar;
                input.onkeydown = (e) => {
                    if (e.key === 'Enter') input.blur();
                    if (e.key === 'Escape') { input.value = vlrTotal.toFixed(2).replace('.', ','); input.blur(); }
                };
            };
        }

        if (DOM.totalKg) {
            DOM.totalKg.textContent = isVolumeUnico ? '' : fmtInt(kgTotalLote);
            if (DOM.totalKg.nextElementSibling) DOM.totalKg.nextElementSibling.textContent = isVolumeUnico ? '' : 'kg';
        }

        if (DOM.custoKg) {
            DOM.custoKg.textContent = isVolumeUnico ? '' : custoGeralKg.toFixed(2).replace('.', ',');
            if (DOM.custoKg.nextElementSibling) DOM.custoKg.nextElementSibling.textContent = isVolumeUnico ? '' : '/kg';

            if (!isVolumeUnico && kgTotalLote > 0) {
                DOM.custoKg.style.cursor = 'pointer';
                DOM.custoKg.title = 'Clique para simular o Custo por KG';

                DOM.custoKg.onclick = function() {
                    if (this.parentNode.querySelector('.input-simulacao-kg')) return;

                    const input = document.createElement('input');
                    input.type = 'text';
                    input.className = 'input-simulacao-kg';
                    input.value = custoGeralKg.toFixed(2).replace('.', ',');
                    input.style.cssText = 'width: 70px; text-align: right; font-size: 1.1rem; font-weight: 800; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0 4px; outline: none; background: #fff; margin-right: 4px;';
                    
                    this.style.display = 'none';
                    this.parentNode.insertBefore(input, this);
                    input.focus();
                    input.select();

                    const finalizar = () => {
                        let novoCustoKg = window.ComercialUtils.toNumber(input.value);
                        let limpou = false, novoVlrTotal = vlrTotal;

                        if (isNaN(novoCustoKg) || novoCustoKg <= 0) {
                            novoVlrTotal = window.ComercialUtils.toNumber(dadosDaLinha.vlrtot);
                            delete dadosDaLinha.vlrtot_simulado; delete dadosDaLinha.vlrtot_simulado_base;
                            limpou = true;
                        } else { novoVlrTotal = novoCustoKg * kgTotalLote; }

                        input.remove(); this.style.display = '';

                        if (novoVlrTotal !== vlrTotal || limpou) {
                            delete dadosDaLinha.ratio_medio; 
                            if (!limpou) {
                                dadosDaLinha.vlrtot_simulado = novoVlrTotal;
                                dadosDaLinha.vlrtot_simulado_base = dadosDaLinha.vlrtot;
                            }
                            preencher(dadosDaLinha, STATE.pesos, true);
                        }
                    };

                    input.onblur = finalizar;
                    input.onkeydown = (e) => {
                        if (e.key === 'Enter') input.blur();
                        if (e.key === 'Escape') { input.value = custoGeralKg.toFixed(2).replace('.', ','); input.blur(); }
                    };
                };
            } else { DOM.custoKg.style.cursor = 'default'; DOM.custoKg.onclick = null; }
        }

        if (DOM.totalCx) {
             const qtdExibir = ehInNatura ? window.ComercialUtils.toNumber(dadosDaLinha.qtdconferida || 0) : cxTotalLote;
             DOM.totalCx.textContent = qtdExibir.toFixed(1).replace('.', ',');
             if (DOM.totalCx.nextElementSibling) DOM.totalCx.nextElementSibling.textContent = tagFinal;
        }

        if (DOM.custoCx) {
             const qtdParaCusto = ehInNatura ? window.ComercialUtils.toNumber(dadosDaLinha.qtdconferida || 0) : cxTotalLote;
             const custoExibir = qtdParaCusto > 0 ? (vlrTotal / qtdParaCusto) : 0;
             DOM.custoCx.textContent = custoExibir.toFixed(2).replace('.', ',');
             if (DOM.custoCx.nextElementSibling) DOM.custoCx.nextElementSibling.textContent = `/${tagFinal}`;
             DOM.custoCx.style.cursor = 'pointer';

             DOM.custoCx.onclick = function() {
                 if (this.parentNode.querySelector('.input-simulacao-custo')) return;

                 const input = document.createElement('input');
                 input.type = 'text';
                 input.className = 'input-simulacao-custo';
                 input.value = custoExibir.toFixed(2).replace('.', ',');
                 input.style.cssText = 'width: 75px; text-align: right; font-size: 1.1rem; font-weight: 800; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0 4px; outline: none; background: #fff; margin-right: 4px;';
                 
                 this.style.display = 'none';
                 this.parentNode.insertBefore(input, this); 
                 input.focus(); input.select();

                 const finalizar = () => {
                     let novoCusto = window.ComercialUtils.toNumber(input.value);
                     let limpou = false, novoVlrTotal = vlrTotal;

                     if (isNaN(novoCusto) || novoCusto <= 0) {
                         novoVlrTotal = window.ComercialUtils.toNumber(dadosDaLinha.vlrtot);
                         delete dadosDaLinha.vlrtot_simulado; delete dadosDaLinha.vlrtot_simulado_base;
                         limpou = true;
                     } else { novoVlrTotal = novoCusto * qtdParaCusto; }
                     
                     input.remove(); this.style.display = '';

                     if (novoVlrTotal !== vlrTotal || limpou) {
                         delete dadosDaLinha.ratio_medio; 
                         if (!limpou) {
                             dadosDaLinha.vlrtot_simulado = novoVlrTotal;
                             dadosDaLinha.vlrtot_simulado_base = dadosDaLinha.vlrtot; 
                         } 
                         preencher(dadosDaLinha, STATE.pesos, true);
                     }
                 };

                 input.onblur = finalizar;
                 input.onkeydown = (e) => {
                     if (e.key === 'Enter') input.blur();
                     if (e.key === 'Escape') { input.value = custoExibir.toFixed(2).replace('.', ','); input.blur(); }
                 };
             };
        }

        const setCol = (id, texto, sigla, apagar) => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = apagar ? '' : texto;
                if (el.nextElementSibling) el.nextElementSibling.textContent = apagar ? '' : sigla;
            }
        };

        if (ehInNatura) {
            ['extraQtdeKg', 'extraQtdeCx', 'extraCustoKg', 'extraCustoCx', 'VlrTotExtra',
             'medioQtdeKg', 'medioQtdeCx', 'medioCustoKg', 'medioCustoCx', 'VlrTotMed'].forEach(id => setCol(id, '', '', true));
             
            const exBar = document.getElementById('extraBarFill'); if(exBar) exBar.style.width = '0%';
            const exPct = document.getElementById('extraSharePct'); if(exPct) exPct.textContent = '0%';
            const mdBar = document.getElementById('medioBarFill'); if(mdBar) mdBar.style.width = '0%';
            const mdPct = document.getElementById('medioSharePct'); if(mdPct) mdPct.textContent = '0%';
        } else {
            const cxExtra = pesoCx > 0 ? (kgExtra / pesoCx) : 0;
            const cxMedio = pesoCx > 0 ? (kgMedio / pesoCx) : 0;
            
            setCol('extraQtdeKg', fmtInt(kgExtra), 'kg', false);
            setCol('extraQtdeCx', cxExtra.toFixed(1).replace('.', ','), 'cx', false);
            setCol('extraCustoKg', fmtBRL(custoExtraKg), '/kg', false);
            setCol('extraCustoCx', fmtBRL(custoExtraKg * pesoCx), '/cx', false);
            setCol('VlrTotExtra', fmtBRL(totalCustoExtra), '', false);

            setCol('medioQtdeKg', fmtInt(kgMedio), 'kg', false);
            setCol('medioQtdeCx', cxMedio.toFixed(1).replace('.', ','), 'cx', false);
            setCol('medioCustoKg', fmtBRL(custoMedioKg), '/kg', false);
            setCol('medioCustoCx', fmtBRL(custoMedioKg * pesoCx), '/cx', false);
            setCol('VlrTotMed', fmtBRL(totalCustoMedio), '', false);

            const totalClassificado = kgExtra + kgMedio;
            const pctExtra = totalClassificado > 0 ? (kgExtra / totalClassificado) * 100 : 0;
            const pctMedio = totalClassificado > 0 ? (kgMedio / totalClassificado) * 100 : 0;
            
            const exBar = document.getElementById('extraBarFill'); if(exBar) exBar.style.width = pctExtra + '%';
            const exPct = document.getElementById('extraSharePct'); if(exPct) exPct.textContent = pctExtra.toFixed(1).replace('.', ',') + '%';
            
            const mdBar = document.getElementById('medioBarFill'); if(mdBar) mdBar.style.width = pctMedio + '%';
            const mdPct = document.getElementById('medioSharePct'); if(mdPct) mdPct.textContent = pctMedio.toFixed(1).replace('.', ',') + '%';

            const divisorSimulacao = kgExtra + (kgMedio * 0.5);

            const aplicarSimulacaoExtra = (elId, valorExibir, isCx) => {
                const el = document.getElementById(elId);
                if (!el) return;
                el.style.cursor = 'pointer';

                el.onclick = function() {
                    if (this.parentNode.querySelector('.input-simulacao-custo')) return;

                    const input = document.createElement('input');
                    input.type = 'text'; input.className = 'input-simulacao-custo';
                    input.value = valorExibir.toFixed(2).replace('.', ',');
                    input.style.cssText = 'width: 70px; text-align: right; font-size: 0.95rem; font-weight: 800; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0 4px; outline: none; background: #fff; margin-right: 4px;';
                    
                    this.style.display = 'none'; this.parentNode.insertBefore(input, this);
                    input.focus(); input.select();

                    const finalizar = () => {
                        let novoValorInformado = window.ComercialUtils.toNumber(input.value);
                        let limpou = false, novoVlrTotal = vlrTotal;

                        if (isNaN(novoValorInformado) || novoValorInformado <= 0) {
                            novoVlrTotal = window.ComercialUtils.toNumber(dadosDaLinha.vlrtot);
                            delete dadosDaLinha.vlrtot_simulado; delete dadosDaLinha.vlrtot_simulado_base;
                            limpou = true;
                        } else {
                            let novoCustoKgExtra = isCx ? (novoValorInformado / pesoCx) : novoValorInformado;
                            novoVlrTotal = novoCustoKgExtra * divisorSimulacao;
                        }

                        input.remove(); this.style.display = '';

                        if (novoVlrTotal !== vlrTotal || limpou) {
                            delete dadosDaLinha.ratio_medio; 
                            if (!limpou) {
                                dadosDaLinha.vlrtot_simulado = novoVlrTotal;
                                dadosDaLinha.vlrtot_simulado_base = dadosDaLinha.vlrtot;
                            }
                            preencher(dadosDaLinha, STATE.pesos, true);
                        }
                    };

                    input.onblur = finalizar;
                    input.onkeydown = (e) => {
                        if (e.key === 'Enter') input.blur();
                        if (e.key === 'Escape') { input.value = valorExibir.toFixed(2).replace('.', ','); input.blur(); }
                    };
                };
            };

            const aplicarSimulacaoMedio = (elId, valorExibir, isCx) => {
                const el = document.getElementById(elId);
                if (!el) return;
                el.style.cursor = 'pointer';

                el.onclick = function() {
                    if (this.parentNode.querySelector('.input-simulacao-custo')) return;

                    const input = document.createElement('input');
                    input.type = 'text'; input.className = 'input-simulacao-custo';
                    input.value = valorExibir.toFixed(2).replace('.', ',');
                    input.style.cssText = 'width: 70px; text-align: right; font-size: 0.95rem; font-weight: 800; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0 4px; outline: none; background: #fff; margin-right: 4px;';
                    
                    this.style.display = 'none'; this.parentNode.insertBefore(input, this);
                    input.focus(); input.select();

                    const finalizar = () => {
                        let novoValorInformado = window.ComercialUtils.toNumber(input.value);
                        let limpou = false, novoVlrTotal = vlrTotal;

                        if (isNaN(novoValorInformado) || novoValorInformado <= 0) {
                            novoVlrTotal = window.ComercialUtils.toNumber(dadosDaLinha.vlrtot);
                            delete dadosDaLinha.vlrtot_simulado; delete dadosDaLinha.vlrtot_simulado_base;
                            delete dadosDaLinha.ratio_medio; limpou = true;
                        } else {
                            let novoCustoKgMedio = isCx ? (novoValorInformado / pesoCx) : novoValorInformado;
                            novoVlrTotal = (custoExtraKg * kgExtra) + (novoCustoKgMedio * kgMedio);
                            if (custoExtraKg > 0) dadosDaLinha.ratio_medio = novoCustoKgMedio / custoExtraKg;
                            else dadosDaLinha.ratio_medio = 1;
                        }

                        input.remove(); this.style.display = '';

                        if (novoVlrTotal !== vlrTotal || limpou) {
                            if (!limpou) {
                                dadosDaLinha.vlrtot_simulado = novoVlrTotal;
                                dadosDaLinha.vlrtot_simulado_base = dadosDaLinha.vlrtot;
                            }
                            preencher(dadosDaLinha, STATE.pesos, true);
                        }
                    };

                    input.onblur = finalizar;
                    input.onkeydown = (e) => {
                        if (e.key === 'Enter') input.blur();
                        if (e.key === 'Escape') { input.value = valorExibir.toFixed(2).replace('.', ','); input.blur(); }
                    };
                };
            };

            aplicarSimulacaoExtra('extraCustoKg', custoExtraKg, false);
            aplicarSimulacaoExtra('extraCustoCx', custoExtraKg * pesoCx, true);
            aplicarSimulacaoMedio('medioCustoKg', custoMedioKg, false);
            aplicarSimulacaoMedio('medioCustoCx', custoMedioKg * pesoCx, true);
        }

        const quebraInp = document.getElementById('sim-quebra-input');
        if (quebraInp && !isSimulacao) {
            const elAvariaKg = document.getElementById('resInservKg');
            const descarteKg = window.ComercialUtils.toNumber(elAvariaKg ? elAvariaKg.textContent : 0);
            const avariaCxReal = pesoCx > 0 ? (descarteKg / pesoCx) : 0;
            
            quebraInp.value = avariaCxReal > 0 ? Math.round(avariaCxReal).toString() : '';
            
            const elSomaCx = document.getElementById('sim-soma-cx');
            if (elSomaCx) elSomaCx.textContent = (avariaCxReal > 0 ? Math.round(avariaCxReal).toString() : '0') + ' cx';
        }

        bindSimulacaoEvents();

        if (!isSimulacao) {
            const exQty = document.getElementById('sim-extra-qty');
            if (exQty) {
                const q1 = window.ComercialUtils.toNumber(dadosDaLinha.ad_simqtd1);
                const v1 = window.ComercialUtils.toNumber(dadosDaLinha.ad_simvlr1);
                const q2 = window.ComercialUtils.toNumber(dadosDaLinha.ad_simqtd2);
                const v2 = window.ComercialUtils.toNumber(dadosDaLinha.ad_simvlr2);
                const descBanco = window.ComercialUtils.toNumber(dadosDaLinha.ad_simqtddesc);

                // 🚀 FIX: Carrega o status do Toggle da memória
                const autoStatus = dadosDaLinha.ad_simauto || 'S';
                const toggleAuto = document.getElementById('sim-toggle-auto');
                if (toggleAuto) toggleAuto.checked = (autoStatus === 'S');

                exQty.value = q1 > 0 ? Math.round(q1).toString() : '';
                document.getElementById('sim-extra-unit').value = v1 > 0 ? v1.toFixed(2).replace('.', ',') : '';
                document.getElementById('sim-medio-qty').value = q2 > 0 ? Math.round(q2).toString() : '';
                document.getElementById('sim-medio-unit').value = v2 > 0 ? v2.toFixed(2).replace('.', ',') : '';

                if (descBanco > 0 || q1 > 0 || q2 > 0) {
                    quebraInp.value = descBanco > 0 ? Math.round(descBanco).toString() : '';
                } else {
                    const elAvariaKg = document.getElementById('resInservKg');
                    const descarteKg = window.ComercialUtils.toNumber(elAvariaKg ? elAvariaKg.textContent : 0);
                    const avariaCxReal = pesoCx > 0 ? (descarteKg / pesoCx) : 0;
                    
                    quebraInp.value = avariaCxReal > 0 ? Math.round(avariaCxReal).toString() : '';
                }

                const exUnitEl = document.getElementById('sim-extra-unit');
                if (exUnitEl) exUnitEl.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }

        try {
            const resTkt = await fetch(`/sankhya/comercial/api/ticket-calculo/?lote=${dadosDaLinha.codagregacao}`);
            if (resTkt.ok) {
                const vendasTkt = await resTkt.json();
                const tktExtra = window.ComercialUtils.toNumber(vendasTkt.ticketExtra || 0);
                const tktMedio = window.ComercialUtils.toNumber(vendasTkt.ticketMedio || 0);

                if (DOM.extraVenda) DOM.extraVenda.textContent = fmtBRL(tktExtra);
                if (DOM.medioVenda) DOM.medioVenda.textContent = fmtBRL(tktMedio);

                const margExtra = tktExtra > 0 ? ((tktExtra - (custoExtraKg * pesoCx)) / tktExtra) * 100 : 0;
                if (DOM.extraMargem) DOM.extraMargem.textContent = fmtPct(margExtra);

                const margMedio = tktMedio > 0 ? ((tktMedio - (custoMedioKg * pesoCx)) / tktMedio) * 100 : 0;
                if (DOM.medioMargem) DOM.medioMargem.textContent = fmtPct(margMedio);
            }
        } catch (e) { console.warn("Aguardando Ticket.", e); }

        try {
            // Mai/2026: usar endpoint NOVO que filtra por CODAGREGACAO (lote
            // selecionado) em vez de "produtos que existem no lote". Devolve
            // o histórico real de saídas daquele lote — com dedup pedido↔nota.
            const resVendas = await fetch(`/sankhya/comercial/api/vendas-lote/?lote=${encodeURIComponent(dadosDaLinha.codagregacao)}`);
            if (resVendas.ok) {
                const vendas = await resVendas.json();
                const listaContainer = document.getElementById('listaUltimasVendas');
                if (listaContainer && vendas.ultimasVendas) {
                    listaContainer.innerHTML = '';

                    if (vendas.ultimasVendas.length === 0) {
                        listaContainer.innerHTML = '<div style="font-size: 0.7rem; color: #94a3b8; text-align: center; padding: 10px;">Sem vendas deste lote ainda.</div>';
                    } else {
                        vendas.ultimasVendas.forEach(v => {
                            const pCx = v.preco_cx !== undefined ? v.preco_cx : (v.preco_kg * pesoCx);
                            const pKg = v.preco_kg !== undefined ? v.preco_kg : 0;
                            const corBadge = v.tipo === 'EXTRA' ? '#2563eb' : (v.tipo === 'MÉDIO' ? '#ea580c' : (v.tipo === 'IN NATURA' ? '#16a34a' : '#64748b'));

                            listaContainer.innerHTML += `
                                <div style="font-size: 0.65rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px; margin-bottom: 3px;">
                                    <div style="display: flex; justify-content: space-between; font-weight: 700; color: #334155; margin-bottom: 1px;">
                                        <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;" title="${v.cliente_full || v.cliente}">${v.cliente}</span>
                                        <span style="color: #29292b; margin-left: 5px;">${v.data}</span>
                                    </div>
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <span style="background: ${corBadge}; color: white; padding: 1px 4px; border-radius: 4px; font-size: 0.55rem; font-weight: 800; letter-spacing: 0.5px;">${v.tipo}</span>
                                        <div style="text-align: right; display: flex; flex-direction: column; line-height: 1;">
                                            <span style="font-weight: 900; color: #505d70; font-size: 0.75rem; margin-top: 1px;">${fmtBRL(pKg)} <small style="font-size: 0.55rem; color: #94a3b8; font-weight: 500;">/kg</small></span>
                                            <span style="font-weight: 900; color: #505d70; font-size: 0.75rem;">${fmtBRL(pCx)} <small style="font-size: 0.55rem; color: #94a3b8; font-weight: 600;">/cx</small></span>
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                    }

                    // Alimenta o sparkline com os mesmos dados (1 fetch). Cronológico:
                    // o backend devolve DESC; aqui revertemos pra desenhar
                    // esquerda=antigo, direita=recente (leitura natural).
                    if (window.ComercialDistribuicao && typeof window.ComercialDistribuicao.renderSparkline === 'function') {
                        const pontos = [...vendas.ultimasVendas].reverse();
                        window.ComercialDistribuicao.renderSparkline(pontos);
                    }
                }
            }
        } catch (e) { console.warn("Aguardando vendas.", e); }
    };

    const limpar = () => {
        initDOM();
        Object.values(DOM).forEach(el => { if(el) el.textContent = '---'; });
        if (DOM.nomeParceiro) {
            DOM.nomeParceiro.textContent = '---';
            DOM.nomeParceiro.title = '---';
        }
        if (DOM.nomeProduto) {
            DOM.nomeProduto.textContent = '---';
            DOM.nomeProduto.title = '---';
        }
        ['extraQtdeKg', 'extraQtdeCx', 'extraCustoKg', 'extraCustoCx', 'VlrTotExtra',
         'medioQtdeKg', 'medioQtdeCx', 'medioCustoKg', 'medioCustoCx', 'VlrTotMed'].forEach(id => {
             const el = document.getElementById(id);
             if (el) {
                 el.textContent = '0';
                 if (id.includes('Custo') || id.includes('Vlr')) el.textContent = 'R$ 0,00';
             }
         });

        const extraBar = document.getElementById('extraBarFill'); if (extraBar) extraBar.style.width = '0%';
        const extraPct = document.getElementById('extraSharePct'); if (extraPct) extraPct.textContent = '0%';
        const medioBar = document.getElementById('medioBarFill'); if (medioBar) medioBar.style.width = '0%';
        const medioPct = document.getElementById('medioSharePct'); if (medioPct) medioPct.textContent = '0%';

        ['sim-extra-qty', 'sim-extra-unit', 'sim-medio-qty', 'sim-medio-unit', 'sim-quebra-input'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        ['sim-extra-total', 'sim-medio-total', 'sim-total-geral'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = 'R$ 0,00';
        });
        const somaCx = document.getElementById('sim-soma-cx');
        if (somaCx) somaCx.textContent = '0 cx';
        
        // 🚀 FIX: Reseta o visual do Toggle ao limpar
        const toggleAuto = document.getElementById('sim-toggle-auto');
        if (toggleAuto) toggleAuto.checked = true;

        document.body.classList.remove('vale-faturado');
        const badgeDist = document.getElementById('badgeFaturadoDist');
        if (badgeDist) badgeDist.style.display = 'none';
        ['btnDistSalvar', 'btnDistZerar'].forEach(id => {
            const btn = document.getElementById(id);
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; btn.style.cursor = 'pointer'; }
        });

        STATE = { nunotaOrigem: null, lote: null, pesos: null, qtdconferida: 0 };

        // Mai/2026: limpa sparkline + lista de vendas do lote (estado anterior)
        const sparkCard = document.getElementById('cardSparkVendas');
        if (sparkCard) sparkCard.style.display = 'none';
        const sparkSvg = document.getElementById('sparkSvg');
        if (sparkSvg) sparkSvg.innerHTML = '';
        const sparkStats = document.getElementById('sparkStats');
        if (sparkStats) sparkStats.textContent = '';
        const listaVendas = document.getElementById('listaUltimasVendas');
        if (listaVendas) {
            listaVendas.innerHTML = '<div style="font-size: 0.7rem; color: #94a3b8; text-align: center; padding: 10px;">Aguardando dados...</div>';
        }
    };

    const toggleVendas = () => {
        const painel = document.getElementById('painelUltimasVendas');
        const icone = document.getElementById('iconeBtnVendas');
        const btn = document.getElementById('btnToggleVendas');
        
        if (!painel || !icone || !btn) return;

        if (painel.style.opacity === '0' || painel.style.opacity === '') {
            painel.style.transform = 'translateX(0)'; painel.style.opacity = '1'; painel.style.pointerEvents = 'auto'; 
            icone.style.transform = 'rotate(0deg)'; btn.style.backgroundColor = '#2563eb';
        } else {
            painel.style.transform = 'translateX(20px)'; painel.style.opacity = '0'; painel.style.pointerEvents = 'none'; 
            icone.style.transform = 'rotate(90deg)'; btn.style.backgroundColor = '#1e293b'; 
        }
    };

    const salvar = async () => {
        const linhaSelecionada = document.querySelector('tr.lista-item-row.row--sel');
        if (!linhaSelecionada || !window.__COM_LIST_ROWS) {
            window.ComercialUtils.mostrarToast('Selecione um produto na lista.', 'erro'); return;
        }
        
        const dadosDaLinha = window.__COM_LIST_ROWS[linhaSelecionada.dataset.idx];
        const isClassificavel = dadosDaLinha.geraproducao === 'S';

        if (!STATE.nunotaOrigem) {
            window.ComercialUtils.mostrarToast('Nenhum pedido de origem selecionado.', 'erro'); return;
        }

        if (isClassificavel && !STATE.lote) {
            window.ComercialUtils.mostrarToast('Nenhum lote selecionado para classificação.', 'erro'); return;
        }

        const itensFaturar = [];

        // 🚀 LÓGICA BÁSICA ORIGINAL: Lê o que está impresso no HTML e manda pro Sankhya
        if (isClassificavel) {
            const kgExtra = window.ComercialUtils.toNumber(document.getElementById('extraQtdeKg').textContent);
            const custoExtraKg = window.ComercialUtils.toNumber(document.getElementById('extraCustoKg').textContent.replace('R$', ''));
            const totExtra = window.ComercialUtils.toNumber(document.getElementById('VlrTotExtra').textContent.replace('R$', ''));

            const kgMedio = window.ComercialUtils.toNumber(document.getElementById('medioQtdeKg').textContent);
            const custoMedioKg = window.ComercialUtils.toNumber(document.getElementById('medioCustoKg').textContent.replace('R$', ''));
            const totMedio = window.ComercialUtils.toNumber(document.getElementById('VlrTotMed').textContent.replace('R$', ''));

            if (STATE.pesos.extraCodProd && kgExtra > 0) {
                itensFaturar.push({ codprod: STATE.pesos.extraCodProd, qtdneg: kgExtra, vlrunit: custoExtraKg, vlrtot: totExtra });
            }
            if (STATE.pesos.medioCodProd && kgMedio > 0) {
                itensFaturar.push({ codprod: STATE.pesos.medioCodProd, qtdneg: kgMedio, vlrunit: custoMedioKg, vlrtot: totMedio });
            }
        } 
        else {
            const vlrTotal = window.ComercialUtils.toNumber(document.getElementById('distVlrTotCompra').textContent.replace('R$', ''));
            const qtd = window.ComercialUtils.toNumber(dadosDaLinha.qtdconferida || dadosDaLinha.qtdneg);
            const vlrunit = qtd > 0 ? vlrTotal / qtd : 0;
            
            if (qtd > 0) {
                itensFaturar.push({ 
                    codprod: dadosDaLinha.codprod, 
                    qtdneg: qtd, 
                    vlrunit: vlrunit, 
                    vlrtot: vlrTotal 
                });
            }
        }

        if (itensFaturar.length === 0) {
            window.ComercialUtils.mostrarToast('As quantidades estão zeradas ou sem produto.', 'erro'); return;
        }

        const btn = document.querySelector('button[onclick="window.ComercialDistribuicao.salvar()"]');
        const txtOriginal = btn ? btn.textContent : 'Salvar';
        if (btn) { btn.textContent = 'Gravando...'; btn.disabled = true; }

        try {
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            const res = await fetch('/sankhya/comercial/api/salvar-vale/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ nunota_origem: STATE.nunotaOrigem, lote: STATE.lote || '', itens_faturar: itensFaturar })
            });
            const data = await res.json();
            
            if (!data.ok) throw new Error(data.error || 'Erro desconhecido ao faturar no Oracle');

            window.ComercialUtils.mostrarToast(`Vale faturado com sucesso! (Nro. ${data.nunota_13})`, 'sucesso');
            
            if (linhaSelecionada && window.__COM_LIST_ROWS) {
                 const idx = linhaSelecionada.dataset.idx;
                 window.__COM_LIST_ROWS[idx].nunota_13 = data.nunota_13;
                 
                 if (window.ComercialEntrada) window.ComercialEntrada.preencher(window.__COM_LIST_ROWS[idx]);
                 linhaSelecionada.click();
            }
        } catch (err) { 
            window.ComercialUtils.mostrarToast(err.message, 'erro');
        } finally { 
            if (btn) { btn.textContent = txtOriginal; btn.disabled = false; }
        }
    };

    const zerarNegociacao = async () => {
        if (!STATE.nunotaOrigem || !STATE.lote) {
            window.ComercialUtils.mostrarToast('Nenhum lote selecionado.', 'erro'); return;
        }
        if (!confirm('Deseja realmente ZERAR o faturamento deste lote?')) return;

        const btn = document.querySelector('button[onclick="window.ComercialDistribuicao.zerarNegociacao()"]');
        const txtOriginal = btn ? btn.textContent : 'Zerar Negociação';
        if (btn) { btn.textContent = 'Zerando...'; btn.disabled = true; }

        try {
            const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
            const csrfToken = csrfMatch ? csrfMatch[1] : '';

            const res = await fetch('/sankhya/comercial/api/zerar-negociacao/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ nunota_origem: STATE.nunotaOrigem, lote: STATE.lote })
            });
            const data = await res.json();
            
            if (!data.ok) throw new Error(data.error || 'Erro ao zerar no Oracle');

            window.ComercialUtils.mostrarToast('Faturamento do lote zerado com sucesso!', 'sucesso');
            
            const linhaSelecionada = document.querySelector('tr.lista-item-row.row--sel');
            if (linhaSelecionada && window.__COM_LIST_ROWS) {
                 const idx = linhaSelecionada.dataset.idx;
                 if (data.acao === 'nota_excluida') {
                     window.__COM_LIST_ROWS[idx].nunota_13 = null; 
                     window.__COM_LIST_ROWS[idx].vlrtot_vale = null; 
                 }
                 linhaSelecionada.click(); 
            }
        } catch (err) { window.ComercialUtils.mostrarToast(err.message, 'erro');
        } finally { if (btn) { btn.textContent = txtOriginal; btn.disabled = false; } }
    };
    let pedidoDestinoSelecionado = null;

    const abrirModalMovimentacao = (dadosLinha) => {
        document.getElementById('movLoteBadge').textContent = `- Lote ${STATE.lote}`;
        document.getElementById('movParceiroNome').textContent = dadosLinha.parceiro;
        
        // Reseta o modal para o estado inicial (Desmembrar)
        const radios = document.getElementsByName('movMode');
        radios[0].checked = true; 
        pedidoDestinoSelecionado = null;
        STATE.codparcAtivo = dadosLinha.codparc; // Guarda o parceiro para a busca
        
        toggleMovMode(); // Ajusta a tela
        document.getElementById('modalMovimentarLote').style.display = 'flex';
    };

    const toggleMovMode = async () => {
        const mode = document.querySelector('input[name="movMode"]:checked').value;
        const areaDesmembrar = document.getElementById('movAreaDesmembrar');
        const areaUnificar = document.getElementById('movAreaUnificar');
        const btnConfirmar = document.getElementById('btnConfirmarMovimento');

        if (mode === 'desmembrar') {
            areaDesmembrar.style.display = 'block';
            areaUnificar.style.display = 'none';
            btnConfirmar.textContent = 'Confirmar Desmembramento';
            btnConfirmar.disabled = false;
        } else {
            areaDesmembrar.style.display = 'none';
            areaUnificar.style.display = 'block';
            btnConfirmar.textContent = 'Selecione um Pedido';
            btnConfirmar.disabled = true;
            
            // Carrega os pedidos do banco via Fetch
            const listaDiv = document.getElementById('movListaPedidos');
            listaDiv.innerHTML = '<div style="padding: 15px; text-align: center; color: #64748b;">Buscando pedidos abertos...</div>';
            
            try {
                // O JS só manda a nota atual, e o Python faz o resto!
                const res = await fetch(`/sankhya/comercial/api/listar-pedidos-unificacao/?nunota_atual=${STATE.nunotaOrigem}`);
                const data = await res.json();
                
                if (data.ok && data.pedidos.length > 0) {
                    listaDiv.innerHTML = '';
                    data.pedidos.forEach(p => {
                        const item = document.createElement('div');
                        item.style.cssText = 'padding: 10px 15px; border-bottom: 1px solid #e2e8f0; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.2s;';
                        item.innerHTML = `
                            <div><span style="font-weight: 800; color: #1e293b;">Pedido Nº ${p.nunota}</span> <br> <small style="color: #64748b;">Data: ${p.data}</small></div>
                            <div style="font-weight: 700; color: #0f172a;">R$ ${p.vlrnota.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                        `;
                        item.onclick = () => {
                            Array.from(listaDiv.children).forEach(c => c.style.backgroundColor = 'transparent');
                            item.style.backgroundColor = '#dbeafe'; 
                            pedidoDestinoSelecionado = p.nunota;
                            btnConfirmar.textContent = `Confirmar Unificação (Nº ${p.nunota})`;
                            btnConfirmar.disabled = false;
                        };
                        listaDiv.appendChild(item);
                    });
                } else if (!data.ok) {
                    // 🚀 FIX: Se der erro de banco, ele mostra o erro na tela!
                    listaDiv.innerHTML = `<div style="padding: 15px; text-align: center; color: #dc2626; font-weight: bold;">Erro interno: ${data.error}</div>`;
                } else {
                    // Só mostra que não achou se a busca do Oracle rodar lisa e retornar vazio
                    listaDiv.innerHTML = '<div style="padding: 15px; text-align: center; color: #dc2626; font-weight: bold;">Nenhum outro pedido aberto encontrado para este parceiro.</div>';
                }
            } catch (err) {
                listaDiv.innerHTML = `<div style="padding: 15px; text-align: center; color: #dc2626;">Erro na comunicação: ${err.message}</div>`;
            }
        }
    };

    const confirmarMovimento = async () => {
        const mode = document.querySelector('input[name="movMode"]:checked').value;
        const btnConfirmar = document.getElementById('btnConfirmarMovimento');
        const txtOriginal = btnConfirmar.textContent;
        
        btnConfirmar.textContent = 'Processando...';
        btnConfirmar.disabled = true;

        try {
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)[1];
            
            if (mode === 'desmembrar') {
                // A MESMA REQUISIÇÃO QUE FIZEMOS ANTES
                const res = await fetch('/sankhya/comercial/api/desmembrar-pedido-classificacao/', { 
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ nunota_origem: STATE.nunotaOrigem, lote: STATE.lote })
                });
                const data = await res.json();
                if (!data.ok) throw new Error(data.error);
                window.ComercialUtils.mostrarToast(`Desmembrado! Novo Pedido: ${data.novo_pedido}`, 'sucesso');
                
            } else if (mode === 'unificar') {
                // NOVA REQUISIÇÃO DE UNIFICAR
                if (!pedidoDestinoSelecionado) throw new Error('Selecione um pedido de destino.');
                
                const res = await fetch('/sankhya/comercial/api/unificar-pedido-classificacao/', { 
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ nunota_origem: STATE.nunotaOrigem, lote: STATE.lote, nunota_destino: pedidoDestinoSelecionado })
                });
                const data = await res.json();
                if (!data.ok) throw new Error(data.error);
                window.ComercialUtils.mostrarToast(`Lote unificado ao Pedido ${pedidoDestinoSelecionado}!`, 'sucesso');
            }

            document.getElementById('modalMovimentarLote').style.display = 'none'; // Fecha modal
            
            // Recarrega a lista
            if (window.ComercialFiltros && window.ComercialFiltros.atualizar) {
                window.ComercialFiltros.atualizar();
            }

        } catch (err) {
            window.ComercialUtils.mostrarToast(err.message, 'erro');
            btnConfirmar.textContent = txtOriginal;
            btnConfirmar.disabled = false;
        }
    };

    // ==========================================================================
    // Sparkline de evolução de preço (Mai/2026 — 2026-05-16)
    // Recebe array cronológico (mais antigo → mais recente) de pontos
    // { data, data_iso, cliente, cliente_full, tipo, qtd_kg, preco_kg, preco_cx }.
    // Desenha linha + pontos + média horizontal tracejada em SVG inline.
    // Sem dependências externas (Chart.js/D3) — mantém coerência com tanques
    // de combustível e gauge do comercial que já usam SVG inline.
    // ==========================================================================
    const renderSparkline = (pontos) => {
        const card    = document.getElementById('cardSparkVendas');
        const svg     = document.getElementById('sparkSvg');
        const stats   = document.getElementById('sparkStats');
        const tooltip = document.getElementById('sparkTooltip');
        if (!card || !svg) return;

        // Limpa estado anterior (cobre troca de lote + zerar)
        svg.innerHTML = '';
        if (tooltip) {
            tooltip.classList.add('hidden');
            tooltip.textContent = '';
        }

        if (!Array.isArray(pontos) || pontos.length === 0) {
            card.style.display = 'none';
            if (stats) stats.textContent = '';
            return;
        }
        card.style.display = '';

        // viewBox fixo — pontos são mapeados pra esse canvas e o SVG escala
        // proporcionalmente com o container (preserveAspectRatio="none").
        const W = 600, H = 120;
        const PAD_L = 44, PAD_R = 12, PAD_T = 14, PAD_B = 22;
        const plotW = W - PAD_L - PAD_R;
        const plotH = H - PAD_T - PAD_B;

        const precos = pontos.map(p => Number(p.preco_kg) || 0).filter(v => v > 0);
        if (precos.length === 0) {
            card.style.display = 'none';
            if (stats) stats.textContent = '';
            return;
        }
        const minP = Math.min(...precos);
        const maxP = Math.max(...precos);
        const avgP = precos.reduce((a, b) => a + b, 0) / precos.length;

        // Range Y com margem visual de 5% pra cada lado (linha não cola no topo/base)
        let yMin = minP, yMax = maxP;
        if (yMin === yMax) { yMin -= 0.5; yMax += 0.5; }   // 1 só ponto
        const margem = (yMax - yMin) * 0.10;
        yMin -= margem;
        yMax += margem;

        const xAt = (i) => {
            if (pontos.length === 1) return PAD_L + plotW / 2;
            return PAD_L + (i / (pontos.length - 1)) * plotW;
        };
        const yAt = (v) => PAD_T + (1 - (v - yMin) / (yMax - yMin)) * plotH;

        const fmtBRL = window.ComercialUtils && window.ComercialUtils.fmtBRL
            ? window.ComercialUtils.fmtBRL
            : (n) => 'R$ ' + Number(n || 0).toFixed(2).replace('.', ',');

        // SVG namespace pra createElement funcionar
        const NS = 'http://www.w3.org/2000/svg';
        const mk = (tag, attrs) => {
            const el = document.createElementNS(NS, tag);
            for (const k in attrs) el.setAttribute(k, attrs[k]);
            return el;
        };

        // Eixo Y — 3 linhas de grade (min, média, max)
        [yMin, avgP, yMax].forEach((v, idx) => {
            const y = yAt(v);
            const line = mk('line', {
                x1: PAD_L, x2: W - PAD_R, y1: y, y2: y,
                stroke: idx === 1 ? '#94a3b8' : '#e2e8f0',
                'stroke-width': 1,
                'stroke-dasharray': idx === 1 ? '4 4' : '',
            });
            svg.appendChild(line);
            const label = mk('text', {
                x: PAD_L - 6, y: y + 3,
                'text-anchor': 'end',
                'font-size': '10',
                fill: idx === 1 ? '#475569' : '#94a3b8',
                'font-weight': idx === 1 ? '700' : '500',
            });
            label.textContent = fmtBRL(v).replace('R$ ', '');
            svg.appendChild(label);
        });

        // Eixo X — primeira e última data (evita label denso)
        if (pontos.length > 0) {
            [0, pontos.length - 1].forEach((i, k) => {
                if (k === 1 && pontos.length === 1) return;   // 1 só ponto
                const label = mk('text', {
                    x: xAt(i), y: H - 6,
                    'text-anchor': i === 0 ? 'start' : 'end',
                    'font-size': '10',
                    fill: '#64748b',
                });
                label.textContent = pontos[i].data || '';
                svg.appendChild(label);
            });
        }

        // Linha conectando os pontos (só se >= 2 pontos)
        if (pontos.length >= 2) {
            const d = pontos.map((p, i) => {
                const x = xAt(i).toFixed(1);
                const y = yAt(Number(p.preco_kg) || 0).toFixed(1);
                return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
            }).join(' ');
            svg.appendChild(mk('path', {
                d, fill: 'none',
                stroke: '#5e7e4a',                  // verde Agromil
                'stroke-width': 2,
                'stroke-linejoin': 'round',
                'stroke-linecap': 'round',
            }));
        }

        // Pontos clicáveis (círculo + área transparente maior pra hit-test)
        pontos.forEach((p, i) => {
            const cx = xAt(i);
            const cy = yAt(Number(p.preco_kg) || 0);
            svg.appendChild(mk('circle', {
                cx, cy, r: 4, fill: '#5e7e4a',
                stroke: '#fff', 'stroke-width': 1.5,
            }));
            // Hit-test invisível (raio maior) — facilita hover em mobile/touch
            const hit = mk('circle', {
                cx, cy, r: 12, fill: 'transparent',
                'data-idx': i, style: 'cursor: pointer;',
            });
            svg.appendChild(hit);
            hit.addEventListener('mouseenter', (e) => {
                if (!tooltip) return;
                tooltip.innerHTML = `
                    <div style="font-weight:700;">${p.cliente || '—'}</div>
                    <div style="opacity:.85;">${p.data || '—'} · ${p.tipo || ''}</div>
                    <div style="font-weight:700; margin-top:2px;">${fmtBRL(p.preco_kg)} <span style="font-weight:400; opacity:.7;">/kg</span></div>
                `;
                tooltip.classList.remove('hidden');
                // Posiciona perto do cursor (coords relativas ao wrapper)
                const wrap = svg.parentElement;
                const rect = wrap.getBoundingClientRect();
                tooltip.style.left = (e.clientX - rect.left + 10) + 'px';
                tooltip.style.top  = (e.clientY - rect.top - 10)  + 'px';
            });
            hit.addEventListener('mouseleave', () => {
                if (tooltip) tooltip.classList.add('hidden');
            });
        });

        // Estatísticas: média · min · max · #vendas
        if (stats) {
            stats.innerHTML = `
                <span>Média <strong>${fmtBRL(avgP)}/kg</strong></span>
                <span class="spark-stats-sep">·</span>
                <span>Min ${fmtBRL(minP)}</span>
                <span class="spark-stats-sep">·</span>
                <span>Max ${fmtBRL(maxP)}</span>
                <span class="spark-stats-sep">·</span>
                <span>${precos.length} venda${precos.length === 1 ? '' : 's'}</span>
            `;
        }
    };

    return { preencher, limpar, toggleVendas, salvar, zerarNegociacao, abrirModalMovimentacao, toggleMovMode, confirmarMovimento, renderSparkline };
})();